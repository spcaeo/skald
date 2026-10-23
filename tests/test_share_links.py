""""Share with your developer" links (share_links.py, share_api.py,
share_page.py): made by an admin, opened with no sign-in, only that one task
for that one site, the secret made and shown once, expiry, revoke, the rate
limit, the audit rows, and no token or address written anywhere.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, SAME  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import ingest, share_api  # noqa: E402
from skald.accounts import auditlog  # noqa: E402


class Shared(TenantServer):
    def setUp(self):
        super().setUp()
        share_api._BUCKET = None
        self.config["ingest"]["kit_image"] = "registry.example.com/skald:2"

    def make(self, task="send", method="docker", days=7, who="admin@example.com", site=A):
        cookie, csrf = self.session(who)
        return self.post(f"/traffic/{A}/sites/share", {"site": site, "task": task, "method": method,
                                                       "days": days}, cookie, csrf)

    def link(self, **kw) -> str:
        got = self.make(**kw)
        self.assertEqual(got.status, 200, got.json)
        self.assertTrue(got.json["link"].startswith("https://www.example.com/traffic-auth/setup/"))
        return "/" + got.json["link"].split("/", 3)[3]

    def audit(self, action):
        db = self.accounts_db()
        try:
            return auditlog.recent(db, self.alpha["id"], action=action)
        finally:
            db.close()

    def test_the_page_opens_without_sign_in_for_one_task_and_site(self):
        path = self.link()
        page = self.call("GET", path)
        self.assertEqual(page.status, 200)
        self.assertIn(b"share-page.js", page.raw)
        self.assertIn("noindex", page.header("X-Robots-Tag"))
        info = self.call("GET", path + "/info").json
        self.assertEqual((info["site"], info["task"], info["method"]), (A, "send", "docker"))
        self.assertEqual(info["send_url"], f"https://www.example.com/traffic-ingest/{A}")
        self.assertFalse(info["shown"])
        # Only that site: no parameter points it elsewhere, and nothing of the dashboard opens.
        self.assertEqual(self.call("GET", path + "/info?site=" + B).json["site"], A)
        self.assertEqual(self.call("GET", f"/traffic/{A}/sites").status, 401)
        self.assertEqual(self.call("GET", path + "/status").status, 200)
        self.assertEqual(len(self.audit("share.view")), 1)
        self.assertEqual(len(self.audit("share.create")), 1)

    def test_the_secret_is_made_and_shown_once(self):
        path = self.link()
        got = self.call("POST", path + "/reveal", {}, SAME)
        self.assertEqual(got.status, 200, got.json)
        token = got.json["secret"]
        self.assertTrue(token.startswith("skald_"))
        self.assertEqual(self.ship(A, token, lines(2)).status, 200)       # it sends for A
        self.assertEqual(self.ship(B, token, lines(1)).status, 403)       # and nothing else
        again = self.call("POST", path + "/reveal", {}, SAME)
        self.assertEqual(again.status, 410)
        self.assertIn("already", again.json["error"])
        self.assertTrue(self.call("GET", path + "/info").json["shown"])
        self.assertEqual(len(self.audit("share.reveal")), 1)
        # The kit can carry it, only when asked and only that token.
        zipped = self.call("POST", path + "/kit", {"method": "docker", "include_token": True, "token": token}, SAME)
        self.assertEqual(zipped.status, 200)
        self.assertIn(b"ship-token", zipped.raw)
        # The token is in no audit row, and the status file holds no address.
        db = self.accounts_db()
        try:
            rows = " ".join(str(dict(r)) for r in db.execute("SELECT * FROM audit"))
            links = " ".join(str(dict(r)) for r in db.execute("SELECT * FROM share_links"))
        finally:
            db.close()
        self.assertNotIn(token, rows)
        self.assertNotIn(token, links)
        self.assertNotIn(path.rsplit("/", 1)[1], links)                    # only the id's hash is kept
        self.assertNotIn("192.0.2.", self.call("GET", path + "/status").raw.decode())

    def test_a_server_link_gives_every_server_kit(self):
        # 2.30: a "server" link offers the one file, and the zips under "Other ways" too.
        path = self.link(method="server")
        one = self.call("POST", path + "/kit", {"method": "server"}, SAME)
        self.assertEqual(one.status, 200)
        self.assertTrue(one.raw.startswith(b"#!"))
        for method in ("docker", "systemd"):
            got = self.call("POST", path + "/kit", {"method": method}, SAME)
            self.assertEqual(got.status, 200, method)
            self.assertTrue(got.raw.startswith(b"PK"), method)
        self.assertEqual(self.call("POST", path + "/kit", {"method": "cloudflare"}, SAME).status, 400)

    def test_expiry_and_revoke(self):
        path = self.link(days=1)
        self.tick(86400 + 1)
        self.assertEqual(self.call("GET", path + "/info").status, 410)
        self.assertEqual(self.call("GET", path).status, 410)
        made = self.make(days=30)
        path = "/" + made.json["link"].split("/", 3)[3]
        ref = self.make(days=30)
        cookie, csrf = self.session("owner@example.com")
        shares = self.call("GET", f"/traffic/{A}/sites/shares", cookie=cookie).json["shares"]
        self.assertEqual({s["state"] for s in shares}, {"expired", "open"})
        got = self.post(f"/traffic/{A}/sites/unshare", {"ref": made.json["ref"]}, cookie, csrf)
        self.assertEqual(got.json["state"], "revoked")
        self.assertEqual(self.call("GET", path + "/info").status, 410)
        self.assertEqual(self.call("POST", path + "/reveal", {}, SAME).status, 410)
        self.assertEqual(len(self.audit("share.revoke")), 1)
        self.assertEqual(ref.status, 200)

    def test_who_may_make_one(self):
        self.assertEqual(self.make(who="viewer@example.com").status, 403)
        self.assertEqual(self.make(site=B).status, 404)
        self.assertEqual(self.make(task="send", method="fax").status, 400)
        self.assertEqual(self.make(days=3).status, 400)
        cookie, _ = self.session("admin@example.com")
        self.assertEqual(self.post(f"/traffic/{A}/sites/share", {"site": A, "task": "script", "days": 7},
                                   cookie, None).status, 403)                  # no CSRF value
        cookie, csrf = self.session("bob@example.com")
        self.assertEqual(self.call("GET", f"/traffic/{A}/sites/shares", cookie=cookie).status, 403)

    def test_the_public_routes_refuse_what_they_should(self):
        path = self.link(task="script", method="")
        self.assertEqual(self.call("POST", path + "/reveal", {}, SAME).status, 400)   # no secret
        self.assertEqual(self.call("POST", path + "/reveal", {}).status, 403)         # not same-origin
        self.assertEqual(self.call("GET", "/traffic-auth/setup/" + "a" * 22 + "/info").status, 410)
        self.assertEqual(self.call("POST", path + "/kit", {"method": "docker"}, SAME).status, 400)
        js = self.call("GET", "/traffic-auth/app/js/tabs/share-page.js")
        self.assertEqual(js.status, 200)
        self.assertIn("javascript", js.header("Content-Type"))
        self.assertEqual(self.call("GET", "/traffic-auth/app/css/connections.css").status, 200)
        for bad in ("/traffic-auth/app/js/../../config.py", "/traffic-auth/app/js/nothing.js",
                    "/traffic-auth/app/index.html"):
            self.assertIn(self.call("GET", bad).status, (401, 403, 404), bad)

    def test_every_stylesheet_the_page_needs_is_linked_and_served(self):
        # 2.27: without urlactions.css the copy/open icons of an address drew page-sized.
        page = self.call("GET", self.link(task="hook", method="json"))
        html = page.raw.decode()
        for css in ("app.css", "screens.css", "features.css", "css/connections.css", "css/urlactions.css"):
            self.assertIn(f'href="/traffic-auth/app/{css}"', html, css)
            self.assertEqual(self.call("GET", f"/traffic-auth/app/{css}").status, 200, css)

    def test_every_module_the_page_imports_is_served_without_sign_in(self):
        import re
        seen, todo = set(), ["/traffic-auth/app/js/tabs/share-page.js"]
        while todo:
            url = todo.pop()
            if url in seen:
                continue
            seen.add(url)
            got = self.call("GET", url)
            self.assertEqual(got.status, 200, url)
            for spec in re.findall(r'(?m)^import .*? from "(\.[^"]+)";', got.raw.decode()):
                out = []
                for part in (url.rsplit("/", 1)[0] + "/" + spec).split("/"):
                    if part == "..":
                        out.pop()
                    elif part != ".":
                        out.append(part)
                todo.append("/".join(out))
        self.assertGreater(len(seen), 10)

    def test_the_rate_limit(self):
        path = self.link()
        share_api._BUCKET = ingest.Bucket(1, 3)
        codes = [self.call("GET", path + "/info").status for _ in range(5)]
        self.assertEqual(codes[:3], [200, 200, 200])
        self.assertEqual(codes[-1], 429)

    def test_a_lead_hook_link(self):
        path = self.link(task="hook", method="lead")
        info = self.call("GET", path + "/info").json
        self.assertEqual(info["hook_url"], f"https://www.example.com/traffic-hooks/{A}/lead")
        self.assertEqual(info["secret"], "hook secret")
        self.assertEqual(self.call("POST", path + "/test", {}, SAME).status, 409)     # no secret yet
        got = self.call("POST", path + "/reveal", {}, SAME)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["kind"], "hook secret")
        tested = self.call("POST", path + "/test", {}, SAME)
        self.assertEqual(tested.status, 200, tested.json)
        self.assertLess(tested.json["status"], 300, tested.json)
        status = self.call("GET", path + "/status").json
        self.assertTrue(status["deliveries"], status)
        self.assertTrue(all("test" in str(d.get("outcome")) for d in status["deliveries"]), status)
        self.assertNotIn(got.json["secret"], str(status))

    def test_a_nextjs_link(self):
        """The log_format line for a Next.js site: no method, no secret, and a
        Test that reads the doctor's Next.js line for that site's log."""
        path = self.link(task="nextjs", method="docker")
        info = self.call("GET", path + "/info").json
        self.assertEqual((info["task"], info["method"], info["secret"]), ("nextjs", None, None))
        self.assertEqual(self.call("POST", path + "/reveal", {}, SAME).status, 400)
        self.assertEqual(self.call("POST", path + "/kit", {"method": "docker"}, SAME).status, 400)
        self.assertEqual(self.call("POST", path + "/test", {}, SAME).status, 400)
        self.assertEqual(self.call("GET", path + "/status").json["state"], "")   # no payload yet
        logs = Path(self.config["logs"]["dir"])
        logs.mkdir(parents=True, exist_ok=True)
        raw = ('203.0.113.5 - - [08/Oct/2026:12:00:00 +0000] "GET /pricing/?_rsc=1x2y HTTP/2.0" '
               '200 512 "https://www.example.com/" "Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0"')
        (logs / "access.log").write_text(raw + "\n")
        got = self.call("GET", path + "/status").json
        self.assertEqual(got["state"], "NEEDS ATTENTION", got)
        self.assertNotIn("203.0.113.", str(got))
        (logs / "access.log").write_text(raw + " rsc_prefetch=-\n")
        self.assertEqual(self.call("GET", path + "/status").json["state"], "OK")


if __name__ == "__main__":
    unittest.main()
