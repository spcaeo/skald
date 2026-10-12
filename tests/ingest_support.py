"""A sessions-mode helper with two tenants of different kinds, for the ingest,
Sites and isolation tests. Not a test module itself.

auth_support.Server's two organisations, with a difference: Alpha's site
(alpha.example) is the config file's own site, Beta's (beta.example) is a
site made from the dashboard (a site_config row in accounts.sqlite). The
helper is started with the config file's path, so it sees both, and with
`ingest: {enabled: true}`. Log lines use RFC 5737 addresses and example.com.
"""
from __future__ import annotations

import gzip
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_support import A, B, ORIGIN, Server  # noqa: E402

from skald import accounts, ingest  # noqa: E402
from skald.accounts import apitokens, site_configs  # noqa: E402
from skald.refresh_server import make_handler  # noqa: E402

LINE = ('192.0.2.{n} - - [11/Oct/2026:13:{m:02d}:36 +0000] "GET /page-{n} HTTP/1.1" 200 512 '
        '"https://www.example.com/" "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0"')


def lines(count: int, start: int = 1) -> bytes:
    return "".join(LINE.format(n=(start + i) % 250 + 1, m=(start + i) % 60) + "\n"
                   for i in range(count)).encode()


class TenantServer(Server):
    """Server, restarted with a config file: config site A, dashboard site B."""

    def setUp(self):
        super().setUp()
        root = Path(self._tmp.name)
        self.root = root
        self.ingest_root = self.live / "ingest"
        self.config.update({
            "site": {"name": A, "hosts": [A]},
            "history": {"db": str(self.live / "history.sqlite")},
            # No free-disk floor: the endpoint must not depend on this machine's disk
            # (a small /tmp answered 507 and the shipper waited). The guard has its
            # own test with a patched disk_usage (test_ingest_caps.DiskAndPlan).
            "ingest": {"enabled": True, "per_minute": 6000, "burst": 1000, "min_free_gb": 0},
            "logs": {"dir": str(root / "alpha-logs"), "format": "nginx_combined"},
        })
        self.config_path = root / "config.yml"
        self.config_path.write_text(json.dumps(self.config))    # JSON is YAML
        ingest._BUCKETS.clear()
        self.server.shutdown()
        self.server.server_close()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), make_handler(self.runner, {ORIGIN}, self.config, self.out,
                                           self.live, None, self.config_path))
        threading.Thread(target=self.server.serve_forever, args=(0.02,), daemon=True).start()

    def seed(self):
        super().seed()
        db = self.db()
        try:
            db.execute("DELETE FROM sites WHERE name = ?", (B,))
            site_configs.create(db, self.beta["id"], B, "cli", fmt="nginx_combined",
                                log_dir=str(self.live / "ingest" / B))
        finally:
            db.close()

    def token(self, org, scopes=("ingest",), sites=None, name="shipper") -> str:
        db = self.db()
        try:
            return apitokens.create(db, org["id"], name, sites=sites, scopes=scopes)
        finally:
            db.close()

    def ship(self, site, token, body: bytes, batch="s1:1", gz=True, headers=None):
        hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "text/plain"}
        if batch is not None:
            hdrs["X-Skald-Batch"] = batch
        if gz:
            body = gzip.compress(body)
            hdrs["Content-Encoding"] = "gzip"
        hdrs.update(headers or {})
        return self.call("POST", f"/traffic-ingest/{site}", headers=hdrs, raw=body)

    def stored(self, site) -> bytes:
        path = self.ingest_root / site / "access.log"
        return path.read_bytes() if path.exists() else b""

    def accounts_db(self):
        return accounts.connect(accounts.path_for(self.config, self.live))
