"""Second security review, findings 4 and 5.

4. `skald site purge` leaves nothing of the site: conversions.sqlite rows of
   every table with a site column, its outbox cursor, its hook spool lines and
   its secrets (hooks/<site>/*, outgoing/<site>/*). The name is then held for
   30 days: re-adding it needs the install admin's --allow-reuse.
5. A site made by sign-up (or from Settings > Sites with saas on) waits for
   its domain to be verified - a DNS TXT record or a <meta> tag on its home
   page - and collects nothing until then: ingest, hooks and the beacon
   refuse it. Sign-up cannot claim a config-file site or a reserved name.

Addresses are RFC 5737, names example.com/.org.
"""
from __future__ import annotations

import http.client
import io
import json
import socket
import struct
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402
from auth_support import PW, SAME  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import accounts, site_verify  # noqa: E402
from skald.accounts import site_configs  # noqa: E402
from skald.conversions import outgoing, secrets_store, spool, store  # noqa: E402

SHOP, MAIN = "shop.example.com", "main.example"


# ------------------------------------------------------------------ purge

class Purge(AccountsCase):
    def run_ti(self, *argv):
        from skald import cli
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--config", str(self.cfg_path), *argv])
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Org", "cli")
        self.cfg_path = self.dir / "config.yml"
        self.cfg_path.write_text(json.dumps({
            "site": {"name": MAIN}, "history": {"db": str(self.dir / "history.sqlite")},
            "dashboard": {"out": str(self.dir / "www")}, "access": {"mode": "sessions"}}))
        self.secrets = self.dir / "secrets.json"
        self.spool = self.dir / "hooks"

    def seed_conversions(self, site: str) -> None:
        db = store.connect(self.dir / "conversions.sqlite")
        try:
            at = "2026-10-10T10:00:00Z"
            db.execute("INSERT INTO conversions (site, action, stage, at, external_ref, tool, "
                       "received_at) VALUES (?, 'demo', 'completed', ?, ?, 'calendly', ?)",
                       (site, at, f"ref-{site}", at))
            db.execute("INSERT INTO journeys (vid, site, at, path) VALUES ('skv_x', ?, ?, '/')",
                       (site, at))
            db.execute("INSERT INTO identities (site, email_hash, created_at) VALUES (?, 'h', ?)",
                       (site, at))
            db.execute("INSERT INTO deliveries (site, tool, received_at, outcome, http_status) "
                       "VALUES (?, 'calendly', ?, 'recorded', 200)", (site, at))
            wid = db.execute("INSERT INTO webhooks (site, url, events, created_at) VALUES "
                             "(?, 'https://example.com/h', 'conversion.completed', ?)",
                             (site, at)).lastrowid
            db.execute("INSERT INTO outbox (webhook_id, site, event, ref, body, created_at, "
                       "next_at) VALUES (?, ?, 'conversion.completed', 'c1', '{}', ?, ?)",
                       (wid, site, at, at))
            db.execute("INSERT INTO meta (key, value) VALUES (?, '1')",
                       (f"outbox_cursor:{site}",))
        finally:
            db.close()
        spool.append(self.spool, date(2026, 10, 10),
                     spool.line_for("2026-10-10T10:00:00Z", site, "calendly", {"a": 1}, False))
        secrets_store.put(self.secrets, f"hooks/{site}/calendly", f"skh_old_{site}")
        secrets_store.put(self.secrets, f"outgoing/{site}/{wid}", f"skw_old_{site}")

    def sites_in(self) -> dict:
        db = store.connect(self.dir / "conversions.sqlite")
        try:
            got = {t: sorted({r[0] for r in db.execute(f"SELECT site FROM {t}")})
                   for t in ("conversions", "journeys", "identities", "deliveries", "webhooks",
                             "outbox")}
            got["meta"] = sorted(r[0] for r in db.execute(
                "SELECT key FROM meta WHERE key LIKE 'outbox_cursor:%'"))
            return got
        finally:
            db.close()

    def purge_shop(self):
        code, _, err = self.run_ti("site", "add", SHOP, "--org", self.org["slug"])
        self.assertEqual(code, 0, err)
        self.seed_conversions(SHOP)
        self.seed_conversions(MAIN)
        site_configs.remove(self.db, self.org["id"], SHOP, "cli")
        code, out, err = self.run_ti("site", "purge", SHOP, "--yes")
        self.assertEqual(code, 0, err)
        return out

    def test_purge_leaves_no_conversions_spool_lines_or_secrets(self):
        self.purge_shop()
        got = self.sites_in()
        for table in ("conversions", "journeys", "identities", "deliveries", "webhooks",
                      "outbox"):
            self.assertEqual(got[table], [MAIN], table)
        self.assertEqual(got["meta"], [f"outbox_cursor:{MAIN}"])
        kept = spool.read(self.spool, date(2026, 10, 10))
        self.assertEqual([r["site"] for r in kept], [MAIN])
        left = secrets_store.load(self.secrets)
        self.assertEqual(sorted(k.split("/")[1] for k in left), [MAIN, MAIN])

    def test_a_purged_name_waits_30_days_unless_allow_reuse(self):
        self.purge_shop()
        code, _, err = self.run_ti("site", "add", SHOP, "--org", self.org["slug"])
        self.assertEqual(code, 1)
        self.assertIn("--allow-reuse", err)
        with self.assertRaises(ValueError):
            site_configs.create(self.db, self.org["id"], SHOP, "web")
        code, _, err = self.run_ti("site", "add", SHOP, "--org", self.org["slug"],
                                   "--allow-reuse")
        self.assertEqual(code, 0, err)
        # The new site sees nothing of the old one, and no old secret works.
        got = self.sites_in()
        self.assertTrue(all(SHOP not in v for k, v in got.items() if k != "meta"), got)
        self.assertNotIn(f"outbox_cursor:{SHOP}", got["meta"])
        self.assertEqual(secrets_store.find({}, self.dir, SHOP, "calendly"), (None, ""))
        db = store.connect(self.dir / "conversions.sqlite")
        try:
            self.assertEqual(outgoing.active(db, SHOP), [])
        finally:
            db.close()

    def test_after_30_days_the_name_is_free(self):
        self.purge_shop()
        self.tick(days=31)
        code, _, err = self.run_ti("site", "add", SHOP, "--org", self.org["slug"])
        self.assertEqual(code, 0, err)


# ------------------------------------------------------------- verifying

def dns_answer(query: bytes, records: list[str], rcode: int = 0) -> bytes:
    """A DNS response to `query` with TXT `records`, names compressed."""
    ident = query[:2]
    question = query[12:]
    head = ident + struct.pack(">HHHHH", 0x8180 | rcode, 1, len(records), 0, 0)
    out = head + question
    for text in records:
        raw = text.encode()
        chunks = b"".join(bytes([len(raw[i:i + 255])]) + raw[i:i + 255]
                          for i in range(0, len(raw), 255))
        out += b"\xc0\x0c" + struct.pack(">HHIH", 16, 1, 300, len(chunks)) + chunks
    return out


class FakeDns:
    def __init__(self, records):
        self.records, self.asked = records, []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                data, peer = self.sock.recvfrom(512)
            except OSError:
                return
            self.asked.append(data)
            self.sock.sendto(dns_answer(data, self.records), peer)

    def close(self):
        self.sock.close()


class Dns(unittest.TestCase):
    def test_a_txt_query_over_udp(self):
        long = "skald-verify=" + "a" * 300           # two character-strings
        dns = FakeDns(["v=spf1 -all", "skald-verify=abc123", long])
        self.addCleanup(dns.close)
        got = site_verify.dns_txt("shop.example.com", nameserver=("127.0.0.1", dns.port))
        self.assertEqual(got, ["v=spf1 -all", "skald-verify=abc123", long])
        q = dns.asked[0]
        self.assertIn(b"\x04shop\x07example\x03com\x00\x00\x10\x00\x01", q)

    def test_the_system_resolver_from_resolv_conf(self):
        text = "# comment\nsearch example.com\nnameserver 192.0.2.53\nnameserver 2001:db8::53\n"
        self.assertEqual(site_verify.nameservers(text), ["192.0.2.53", "2001:db8::53"])
        self.assertEqual(site_verify.nameservers("search x\n"), [])

    def test_meta_tags(self):
        page = (b'<html><head><meta name="description" content="x">'
                b'<META NAME="skald-verify" CONTENT="tok1"></head></html>')
        self.assertEqual(site_verify.meta_tokens(page), ["tok1"])


class Verify(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Org", "cli")
        accounts.assign_site(self.db, SHOP, self.org["id"], "cli")
        self.token = site_verify.start(self.db, SHOP)

    def test_a_site_without_a_row_counts_as_verified(self):
        self.assertFalse(site_verify.pending(self.db, "old.example.com"))
        self.assertTrue(site_verify.pending(self.db, SHOP))

    def test_dns_txt_verifies(self):
        wrong = site_verify.check(self.db, SHOP, {}, "u1", resolver=lambda h: ["skald-verify=x"],
                                  fetcher=lambda h, c: (200, b"", None))
        self.assertFalse(wrong["verified"])
        self.assertTrue(site_verify.pending(self.db, SHOP))
        asked = []
        got = site_verify.check(self.db, SHOP, {}, "u1",
                                resolver=lambda h: asked.append(h) or
                                [f"skald-verify={self.token}"],
                                fetcher=lambda h, c: self.fail("not needed"))
        self.assertEqual((got["verified"], got["method"]), (True, "dns"))
        self.assertEqual(asked, [SHOP])
        self.assertFalse(site_verify.pending(self.db, SHOP))

    def test_a_meta_tag_on_the_home_page_verifies(self):
        page = f'<meta name="skald-verify" content="{self.token}">'.encode()
        seen = []
        got = site_verify.check(self.db, SHOP, {}, "u1", resolver=lambda h: [],
                                fetcher=lambda h, c: seen.append(h) or (200, page, None))
        self.assertEqual((got["verified"], got["method"]), (True, "meta"))
        self.assertEqual(seen, [SHOP])

    def test_a_failed_fetch_says_why(self):
        got = site_verify.check(self.db, SHOP, {}, "u1", resolver=lambda h: [],
                                fetcher=lambda h, c: (0, b"", "a private address"))
        self.assertFalse(got["verified"])
        self.assertIn("skald-verify", got["error"])


class Signup(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["saas"] = {"enabled": True, "signup": True,
                               "plans": {"pro": {"sites": 5}}, "default_plan": "pro"}
        self.mail_on()
        site_verify.clear_cache()
        self.addCleanup(site_verify.clear_cache)

    def token_for(self, email="carol@example.com"):
        from skald import auth_api
        import re
        self.call("POST", "/traffic-auth/signup", {"email": email},
                  {**SAME, "X-Real-IP": "192.0.2.10"})
        auth_api.drain()
        for to, msg in self.sent:
            found = re.search(r"signup-finish\?t=([A-Za-z0-9_-]+)",
                              msg.get_body(("plain",)).get_content())
            if to == email and found:
                return found.group(1)
        self.fail("no link mailed")

    def finish(self, host):
        return self.call("POST", "/traffic-auth/signup-finish",
                         {"token": self.token_for(), "name": "Carol", "password": PW,
                          "org": "Carol Co", "host": host}, SAME)

    def test_a_config_file_site_cannot_be_claimed(self):
        db = self.db()
        try:
            db.execute("DELETE FROM sites WHERE name = ?", ("alpha.example",))
        finally:
            db.close()
        self.config["site"]["name"] = "alpha.example.org"   # a config site with no org yet
        got = self.finish("alpha.example.org")
        self.assertEqual(got.status, 400, got.json)
        db = self.db()
        try:
            self.assertIsNone(accounts.org_of_site(db, "alpha.example.org"))
        finally:
            db.close()

    def test_a_reserved_name_cannot_be_claimed(self):
        db = self.db()
        try:
            site_verify.reserve(db, "gone.example.com", "cli")
        finally:
            db.close()
        got = self.finish("gone.example.com")
        self.assertEqual(got.status, 400, got.json)

    def test_the_new_site_waits_for_verification(self):
        got = self.finish("carol.example.com")
        self.assertEqual(got.status, 200, got.json)
        db = self.db()
        try:
            self.assertTrue(site_verify.pending(db, "carol.example.com"))
        finally:
            db.close()
        listed = self.call("GET", "/traffic/carol.example.com/sites", cookie=got.cookie)
        self.assertEqual(listed.status, 200, listed.json)
        entry = listed.json["sites"][0]
        self.assertEqual(entry["verify"]["state"], "pending")
        self.assertTrue(entry["verify"]["txt"].startswith("skald-verify="))
        csrf = self.call("GET", "/traffic/carol.example.com/me", cookie=got.cookie).json["csrf"]
        with mock.patch.object(site_verify, "dns_txt", return_value=[entry["verify"]["txt"]]):
            done = self.post("/traffic/carol.example.com/sites/verify",
                             {"name": "carol.example.com"}, got.cookie, csrf)
        self.assertEqual(done.status, 200, done.json)
        self.assertTrue(done.json["verified"])
        db = self.db()
        try:
            self.assertFalse(site_verify.pending(db, "carol.example.com"))
        finally:
            db.close()


class Collecting(TenantServer):
    """A pending dashboard site: ingest, hooks and the beacon refuse it."""

    def setUp(self):
        super().setUp()
        self.config["saas"] = {"enabled": True, "plans": {"pro": {"sites": 5}}}
        site_verify.clear_cache()
        self.addCleanup(site_verify.clear_cache)
        cookie, csrf = self.session("admin@example.com")
        got = self.post("/traffic/alpha.example/sites/add", {"host": SHOP}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.ship_token = got.json["token"]
        self.assertEqual(got.json["verify"]["state"], "pending")

    def verify(self):
        db = self.db()
        try:
            site_verify.mark(db, SHOP, "cli", "cli")
        finally:
            db.close()
        site_verify.clear_cache()

    def test_ingest_refuses_until_verified(self):
        got = self.ship(SHOP, self.ship_token, lines(2))
        self.assertEqual(got.status, 403, got.json)
        self.assertIn("verif", got.json["error"])
        self.assertEqual(self.stored(SHOP), b"")
        self.verify()
        self.assertEqual(self.ship(SHOP, self.ship_token, lines(2), batch="s1:2").status, 200)

    def test_hooks_refuse_until_verified(self):
        from skald.conversions import hooks
        secrets_store.put(self.live / "secrets.json", f"hooks/{SHOP}/json", "skh_test")
        rec = hooks.Receiver(self.config, self.live, self.config_path)
        self.assertIsNone(rec.secret(SHOP, "json"))
        self.verify()
        self.assertEqual(rec.secret(SHOP, "json"), "skh_test")

    def test_the_beacon_refuses_until_verified(self):
        from skald.beacon_server import Limiter, Sink, make_handler
        cfg = {**self.config, "site": {"name": SHOP, "hosts": [f"www.{SHOP}"]}}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sink = Sink(cfg, Path(tmp.name) / "beacon")
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            sink, Limiter(per_minute=6000, burst=1000), {f"https://www.{SHOP}"}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        def beacon():
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            conn.request("POST", "/traffic-beacon",
                         json.dumps({"e": "form_start", "p": "/contact/", "id": "c"}).encode(),
                         {"Origin": f"https://www.{SHOP}", "Content-Type": "text/plain",
                          "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0"})
            status = conn.getresponse().status
            conn.close()
            return status

        self.assertEqual(beacon(), 403)
        self.verify()
        self.assertEqual(beacon(), 204)

    def test_the_install_admin_verifies_by_cli(self):
        from skald import cli
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--config", str(self.config_path), "site", "verify", SHOP])
        self.assertEqual(code, 0, err.getvalue())
        db = self.db()
        try:
            self.assertFalse(site_verify.pending(db, SHOP))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
