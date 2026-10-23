"""The one-command install link (kit/link.py, GET /traffic-kit/<code> on the
beacon helper, POST <page>/sites/link) and the set-up pack (kit/pack.py,
POST <page>/sites/pack and sites/packmail, kit_api.py).

The link's store never holds a usable token or the code; a code works once,
for curl or Wget only, and expires. The pack's zip holds the keys only when
asked. Mail goes through a stand-in for mailer.send. Test data: example.com
and RFC 5737 addresses; the tokens are made here.
"""
from __future__ import annotations

import http.client
import io
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer  # noqa: E402

from skald.accounts import apitokens, auditlog  # noqa: E402
from skald.kit import link, pack  # noqa: E402

IMAGE = "registry.example.com/skald:2"
TOKEN = "skald_ab12cd34_" + "Zq7Lm2Np9Rs4Tv8Wx1Yb5Cd3Fg6Hj0Kk2Mp7Qr9St4Uv"[:43]
FIELDS = {"url": "https://stats.example.com/traffic-ingest/example.com",
          "dashboard": "https://stats.example.com/traffic/example.com/",
          "help": "https://stats.example.com/traffic/example.com/#help",
          "image": IMAGE, "ship_path": "/opt/skald/tools/skald-ship.py",
          "base": "https://stats.example.com"}


def unzip(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return {i.filename: (z.read(i), (i.external_attr >> 16) & 0o7777) for i in z.infolist()}


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def test_the_store_holds_no_token_and_no_code(self):
        code, expires = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        self.assertGreaterEqual(len(code), 43)                   # 256 bits, URL-safe
        path = self.folder / link.FILE
        raw = path.read_text()
        self.assertNotIn(TOKEN, raw)
        self.assertNotIn(TOKEN[15:], raw)
        self.assertNotIn(code, raw)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertAlmostEqual(expires - time.time(), 24 * 3600, delta=5)

    def test_once_only(self):
        code, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        self.assertEqual(link.look(self.folder, code)[0], "ok")
        state, entry, token = link.take(self.folder, code)
        self.assertEqual((state, token), ("ok", TOKEN))
        self.assertEqual(entry["fields"]["url"], FIELDS["url"])
        self.assertEqual(link.take(self.folder, code)[0], "gone")
        self.assertIsNone(json.loads((self.folder / link.FILE).read_text())["links"]
                          [link.digest(code)]["sealed"], "the sealed token is wiped")

    def test_expiry_unknown_and_pruning(self):
        now = time.time()
        code, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS, now=now)
        self.assertEqual(link.take(self.folder, code, now=now + 24 * 3600 + 1)[0], "gone")
        self.assertEqual(link.take(self.folder, "x" * 43)[0], "unknown")
        self.assertEqual(link.take(self.folder, "../../etc/passwd")[0], "unknown")
        link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS, now=now + 25 * 3600)
        kept = json.loads((self.folder / link.FILE).read_text())["links"]
        self.assertNotIn(link.digest(code), kept, "an expired link is dropped on the next write")
        self.assertEqual(len(kept), 1)

    def test_a_wrong_code_never_opens_the_seal(self):
        code, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        sealed = json.loads((self.folder / link.FILE).read_text())["links"][link.digest(code)]["sealed"]
        self.assertEqual(link.unseal(sealed, code), TOKEN)
        self.assertNotEqual(link.unseal(sealed, "y" * 43), TOKEN)


class BeaconHelper(unittest.TestCase):
    """GET /traffic-kit/<code> through the beacon helper's own handler."""

    def setUp(self):
        from skald.beacon_server import Limiter, Sink, make_handler
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        config = {"site": {"name": "example.com", "hosts": ["example.com"]},
                  "history": {"db": str(self.folder / "history.sqlite")},
                  "access": {"base_url": "https://stats.example.com"}}
        config_path = self.folder / "config.yml"
        config_path.write_text("")
        sink = Sink(config, self.folder / "beacon")
        sink.config_path = config_path
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(sink, Limiter(), set()))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.n = 0

    def get(self, code, agent="curl/8.5.0", method="GET"):
        self.n += 1                     # each try from its own address: the limit is per address
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        conn.request(method, f"/traffic-kit/{code}",
                     headers={"User-Agent": agent, "X-Real-IP": f"198.51.100.{self.n}"})
        got = conn.getresponse()
        body = got.read().decode()
        conn.close()
        return got, body

    def test_curl_gets_the_installer_once(self):
        code, _ = link.make(self.folder, "example.com", TOKEN, "ab12cd34", FIELDS)
        got, body = self.get(code, agent="Mozilla/5.0 (link preview)")
        self.assertEqual(got.status, 200)
        self.assertIn(f"curl -fsSL https://stats.example.com/traffic-kit/{code} | sudo bash", body)
        self.assertNotIn(TOKEN, body)
        got, body = self.get(code, method="HEAD")
        self.assertEqual(got.status, 200)
        got, body = self.get(code)
        self.assertEqual(got.status, 200, body[:200])
        self.assertTrue(body.startswith("#!/bin/bash"))
        self.assertIn(f"KIT_TOKEN='{TOKEN}'", body)
        self.assertEqual(got.getheader("Cache-Control"), "no-store")
        self.assertIn("noindex", got.getheader("X-Robots-Tag"))
        got, body = self.get(code, agent="Wget/1.21.4")
        self.assertEqual(got.status, 200)       # curl -f would hide a 410's words
        self.assertIn("This install link was used or has expired. Make a new one in Skald: "
                      "https://stats.example.com/traffic/example.com/", body)
        self.assertIn("exit 1", body)
        self.assertNotIn(TOKEN, body)
        got, body = self.get(code, agent="Mozilla/5.0")
        self.assertEqual(got.status, 410)
        self.assertNotIn("exit 1", body)

    def test_unknown_code_and_the_limit(self):
        got, body = self.get("z" * 43)
        self.assertEqual(got.status, 200)
        self.assertIn("exit 1", body)
        self.assertIn("https://stats.example.com/traffic/", body)
        statuses = []
        for _ in range(8):
            conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
            conn.request("GET", "/traffic-kit/" + "z" * 43,
                         headers={"User-Agent": "curl/8", "X-Real-IP": "203.0.113.9"})
            statuses.append(conn.getresponse().status)
            conn.close()
        self.assertIn(429, statuses)


class Pack(unittest.TestCase):
    def build(self, **kw):
        args = dict(ingest_url=FIELDS["url"], lead_url="https://stats.example.com/traffic-hooks/"
                    "example.com/lead", dashboard=FIELDS["dashboard"], help_url=FIELDS["help"],
                    tag='<script src="https://stats.example.com/traffic-js/skald.js" '
                        'data-site="example.com" defer></script>', installer=b"#!/bin/bash\n")
        args.update(kw)
        return pack.files("example.com", **args)

    def test_without_keys(self):
        with mock.patch.object(pack, "lead_files", return_value=None):
            got = self.build()
        for name in ("START-HERE.md", "CLAUDE.md", "AGENTS.md", "secrets.env",
                     "logs/install-server.sh", "logs/cloudflare.md", "logs/vercel-netlify.md",
                     "tag/script-tag.html", "tag/README.md", "leads/README.md"):
            self.assertIn(name, got)
        env = got["secrets.env"].decode()
        self.assertIn("SKALD_INGEST_TOKEN=\n", env)
        self.assertIn("SKALD_LEAD_SECRET=\n", env)
        self.assertIn("Settings > Connections", env)
        self.assertIn("This folder holds no keys", got["START-HERE.md"].decode())
        self.assertEqual(got["AGENTS.md"], got["CLAUDE.md"])
        self.assertIn("Settings > Integrations", got["leads/README.md"].decode())
        for name, data in got.items():
            self.assertIsNone(pack.LEFT.search(data.decode()), name)
            self.assertNotIn(b"skald_", data.replace(b"skald_lead", b""), name)

    def test_with_keys_and_lead_files(self):
        files = {"skald-lead.php": b"<?php\n", "skald-lead.js": b"x\n", "README.md": b"# r\n"}
        with mock.patch.object(pack, "lead_files", return_value=files) as made:
            got = self.build(token=TOKEN, lead_secret="skh_" + "s" * 43, lead_note="included")
        made.assert_called_once()
        env = got["secrets.env"].decode()
        self.assertIn(f"SKALD_INGEST_TOKEN={TOKEN}\n", env)
        self.assertIn("SKALD_LEAD_SECRET=skh_", env)
        self.assertIn(TOKEN, got["logs/vercel-netlify.md"].decode())
        self.assertIn("This folder holds keys", got["START-HERE.md"].decode())
        self.assertIn("leads/skald-lead.js.txt", got, "a name mail filters block is renamed")
        self.assertNotIn("leads/skald-lead.js", got)
        self.assertIn("leads/RENAME-ME.md", got)
        zipped = unzip(pack.build("example.com", got))
        self.assertEqual(zipped["skald-setup-example.com/secrets.env"][1], 0o600)
        self.assertEqual(zipped["skald-setup-example.com/logs/install-server.sh"][1], 0o755)

    def test_recipients(self):
        self.assertEqual(pack.clean_recipients(["A@example.com", "a@example.com"]), ["a@example.com"])
        for bad in ([], ["no-at-sign"], ["a@example.com, b@example.com"],
                    [f"p{n}@example.com" for n in range(4)]):
            with self.assertRaises(ValueError):
                pack.clean_recipients(bad)


class Endpoints(TenantServer):
    def setUp(self):
        super().setUp()
        self.config["ingest"]["kit_image"] = IMAGE
        patcher = mock.patch.object(pack, "lead_files", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def audit(self, action):
        db = self.accounts_db()
        try:
            return auditlog.recent(db, self.alpha["id"], 50, action)
        finally:
            db.close()

    def test_the_link(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(f"/traffic/{A}/sites/link", {"site": A}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        body = got.json
        self.assertTrue(body["url"].startswith("https://www.example.com/traffic-kit/"))
        self.assertEqual(body["command"], f"curl -fsSL {body['url']} | sudo bash")
        self.assertTrue(body["expires_at"].endswith("Z"))
        db = self.accounts_db()
        try:
            ok, _, entry = apitokens.check(db, f"Bearer {body['token']}", A, "ingest")
        finally:
            db.close()
        self.assertTrue(ok)
        self.assertEqual(entry["id"], body["token_id"])
        self.assertTrue(entry["name"].startswith(f"Sending logs: {A}, "))
        raw = (self.live / link.FILE).read_text()
        self.assertNotIn(body["token"], raw)
        self.assertNotIn(body["url"].rsplit("/", 1)[1], raw)
        self.assertTrue(self.audit("kit.link"))
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(f"/traffic/{A}/sites/link", {"site": A}, cookie, csrf).status, 403)

    def test_the_one_file_download(self):
        cookie, csrf = self.session("owner@example.com")
        token = self.token(self.alpha, sites=[A])
        got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "server"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.raw[:200])
        self.assertIn(f'filename="skald-install-{A}.sh"', got.header("Content-Disposition"))
        self.assertIn("KIT_TOKEN=''", got.raw.decode())
        got = self.post(f"/traffic/{A}/sites/kit", {"site": A, "method": "server",
                                                   "include_token": True, "token": token},
                        cookie, csrf)
        self.assertIn(f"KIT_TOKEN='{token}'", got.raw.decode())

    def test_the_pack_download(self):
        cookie, csrf = self.session("owner@example.com")
        got = self.post(f"/traffic/{A}/sites/pack", {"site": A}, cookie, csrf)
        self.assertEqual(got.status, 200, got.raw[:200])
        self.assertIn(f'filename="skald-setup-{A}.zip"', got.header("Content-Disposition"))
        files = unzip(got.raw)
        env = files[f"skald-setup-{A}/secrets.env"][0].decode()
        self.assertIn("SKALD_INGEST_TOKEN=\n", env)
        self.assertIn(f"/traffic-hooks/{A}/lead", env)
        got = self.post(f"/traffic/{A}/sites/pack", {"site": A, "include_secrets": True},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.raw[:200])
        tid = got.header("X-Skald-Token-Id")
        self.assertTrue(tid)
        env = unzip(got.raw)[f"skald-setup-{A}/secrets.env"][0].decode()
        self.assertIn(f"SKALD_INGEST_TOKEN=skald_{tid}_", env)
        self.assertIn("SKALD_LEAD_SECRET=skh_", env, "a new lead secret, the site had none")
        got = self.post(f"/traffic/{A}/sites/pack", {"site": A, "include_secrets": True},
                        cookie, csrf)
        first = env.split("SKALD_LEAD_SECRET=", 1)[1].split("\n", 1)[0]
        env = unzip(got.raw)[f"skald-setup-{A}/secrets.env"][0].decode()
        self.assertIn(f"SKALD_LEAD_SECRET={first}\n", env,
                      "the site's existing lead secret is in the pack, not a new one (owner, 2026-10-23)")
        got = self.post(f"/traffic/{A}/sites/pack", {"site": A, "include_secrets": True,
                                                    "lead_secret": "skh_wrong"}, cookie, csrf)
        self.assertEqual(got.status, 400)

    def mail_on(self):
        self.config["mail"] = {"host": "smtp.example.com", "port": 587, "security": "starttls",
                               "from": "skald@example.com", "to": ["owner@example.com"]}

    def test_the_pack_by_mail(self):
        cookie, csrf = self.session("owner@example.com")
        body = {"site": A, "to": ["dev@example.com"], "include_secrets": True,
                "note": "From the owner"}
        got = self.post(f"/traffic/{A}/sites/packmail", body, cookie, csrf)
        self.assertEqual(got.status, 409, got.json)
        self.assertIn("Mail is not set up", got.json["error"])
        self.mail_on()
        with mock.patch("skald.mailer.send") as send:
            got = self.post(f"/traffic/{A}/sites/packmail", body, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["sent_to"], ["dev@example.com"])
        msg = send.call_args[0][0]
        self.assertEqual(msg["To"], "dev@example.com")
        self.assertIn(f"Set up Skald for {A}", msg["Subject"])
        names = [p.get_filename() for p in msg.iter_attachments()]
        self.assertEqual(names, [f"skald-setup-{A}.zip"])
        text = msg.get_body(("plain",)).get_content()
        self.assertIn("Set up Skald from CLAUDE.md", text)
        self.assertIn("delete it after the set-up", text)
        self.assertIn("From the owner", text)
        rows = self.audit("kit.packmail")
        self.assertIn("1 recipient(s); keys yes", rows[0]["detail"])
        self.assertNotIn("dev@example.com", json.dumps(rows))
        self.assertNotIn("skald_", rows[0]["detail"])

    def test_a_failed_mail_takes_the_token_back_and_the_limit(self):
        cookie, csrf = self.session("owner@example.com")
        self.mail_on()
        body = {"site": A, "to": ["dev@example.com"], "include_secrets": True}
        with mock.patch("skald.mailer.send", side_effect=OSError("refused")):
            got = self.post(f"/traffic/{A}/sites/packmail", body, cookie, csrf)
        self.assertEqual(got.status, 502, got.json)
        db = self.accounts_db()
        try:
            made = [t for t in apitokens.listing(db, self.alpha["id"])
                    if "(set-up pack)" in t["name"]]
        finally:
            db.close()
        self.assertTrue(made and all(t["revoked_at"] for t in made))
        body["include_secrets"] = False
        with mock.patch("skald.mailer.send"):
            codes = [self.post(f"/traffic/{A}/sites/packmail", body, cookie, csrf).status
                     for _ in range(10)]
        self.assertEqual(codes[:9], [200] * 9)                 # the failed one counted too
        self.assertEqual(codes[-1], 429)
        got = self.post(f"/traffic/{A}/sites/packmail", {"site": B, "to": ["x@example.com"]},
                        cookie, csrf)
        self.assertEqual(got.status, 404)


if __name__ == "__main__":
    unittest.main()
