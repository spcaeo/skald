"""Signing in over real HTTP (auth_api.py on the refresh helper, sessions mode):
the sign-in pages, the nginx check, login with its limits and two-step codes,
logout, forgot and reset, invites, and basic mode staying as it was."""
from __future__ import annotations

import io
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, PW, SAME, FakeRunner, Server  # noqa: E402

from skald import accounts, auth_api  # noqa: E402
from skald.accounts import auditlog, sessions, totp  # noqa: E402
from skald.refresh_server import make_handler  # noqa: E402


class Pages(Server):
    def test_the_pages_and_their_files_come_with_the_dashboard_csp(self):
        for name, kind in (("login", "text/html"), ("forgot", "text/html"),
                           ("reset", "text/html"), ("invite", "text/html"),
                           ("auth.js", "text/javascript"), ("auth.css", "text/css")):
            got = self.call("GET", f"/traffic-auth/{name}?t=abc")
            self.assertEqual(got.status, 200, name)
            self.assertTrue(got.header("Content-Type").startswith(kind), name)
            self.assertEqual(got.header("Content-Security-Policy"), auth_api.CSP)
            self.assertEqual(got.header("Cache-Control"), "no-store")
        page = self.call("GET", "/traffic-auth/login").raw.decode()
        self.assertIn('data-page="login"', page)

    def test_nothing_outside_the_allow_list(self):
        for path in ("/traffic-auth/login.html", "/traffic-auth/../access.py",
                     "/traffic-auth/__init__.py", "/traffic-auth/", "/traffic-auth/x/login"):
            self.assertEqual(self.call("GET", path).status, 404, path)


class Login(Server):
    def test_sign_in_sets_the_session_cookie(self):
        got = self.login()
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json, {"ok": True, "next": "/traffic/"})
        cookie = got.header("Set-Cookie")
        for part in ("HttpOnly", "Secure", "SameSite=Lax", "Path=/", "Max-Age=1209600"):
            self.assertIn(part, cookie)
        self.assertEqual(self.check(f"/traffic/{A}/", got.cookie).status, 200)

    def test_without_keep_me_signed_in_the_cookie_ends_with_the_browser(self):
        got = self.login(remember=False)
        self.assertEqual(got.status, 200, got.json)
        cookie = got.header("Set-Cookie")
        self.assertNotIn("Max-Age", cookie)
        for part in ("HttpOnly", "Secure", "SameSite=Lax", "Path=/"):
            self.assertIn(part, cookie)
        self.assertEqual(self.check(f"/traffic/{A}/", got.cookie).status, 200)
        self.tick(13 * 3600)     # past 12 hours without use: the server has ended it too
        self.assertEqual(self.check(f"/traffic/{A}/", got.cookie).status, 401)

    def test_keep_me_signed_in_lasts_days(self):
        got = self.login(remember=True)
        self.assertIn("Max-Age=1209600", got.header("Set-Cookie"))
        self.tick(13 * 3600)
        self.assertEqual(self.check(f"/traffic/{A}/", got.cookie).status, 200)

    def test_wrong_password_and_unknown_email_get_the_same_answer(self):
        wrong = self.login(password="not the password at all")
        nobody = self.login("nobody@example.com")
        self.assertEqual((wrong.status, nobody.status), (401, 401))
        self.assertEqual(wrong.json, nobody.json)
        self.assertIsNone(wrong.cookie)
        db = self.db()
        try:
            rows = [e for e in auditlog.recent(db, None) if e["action"] == "login.fail"]
            mine = [e for e in auditlog.recent(db, self.alpha["id"]) if e["action"] == "login.fail"]
        finally:
            db.close()
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(mine), 1)       # the owner of the account sees it in their org
        self.assertNotIn(PW, str(rows))

    def test_429_after_five_failures_then_one_try_each_30_seconds(self):
        for _ in range(5):
            self.assertEqual(self.login(password="wrong password here").status, 401)
        got = self.login()                    # even the right password waits
        self.assertEqual(got.status, 429)
        self.assertEqual(got.header("Retry-After"), "30")
        self.assertIn("30 seconds", got.json["error"])
        self.tick(31)
        self.assertEqual(self.login().status, 200)

    def test_the_address_limit_covers_many_emails(self):
        for n in range(5):
            self.login(f"nobody{n}@example.com")
        self.assertEqual(self.login("viewer@example.com").status, 429)

    def test_two_step_code_needed_then_checked(self):
        db = self.db()
        try:
            uid = self.uids["owner@example.com"]
            secret, _ = totp.begin(db, uid)
            t = accounts.db.epoch()
            shown = totp.confirm(db, uid, totp.code_at(secret, t - 30), uid)
        finally:
            db.close()
        got = self.login()
        self.assertEqual((got.status, got.json), (200, {"ok": True, "needs_code": True}))
        self.assertIsNone(got.cookie)
        self.assertEqual(self.login(code="000000").status, 401)
        got = self.login(code=totp.code_at(secret, accounts.db.epoch()))
        self.assertEqual(got.status, 200)
        self.assertIsNotNone(got.cookie)
        got = self.login(code=shown[0])        # a recovery code, once
        self.assertEqual(got.status, 200)
        self.assertEqual(self.login(code=shown[0]).status, 401)

    def test_next_only_a_path_under_traffic(self):
        good = f"/traffic/{A}/?range=7d&view=x"
        self.assertEqual(self.login(next=good).json["next"], good)
        for bad in ("//evil.example/traffic/", "https://evil.example/traffic/",
                    "/traffic-auth/login", "/traffic/../etc", "/\\evil.example",
                    "/traffic//evil.example", "javascript:alert(1)", "/traffic/\nx", 42):
            self.assertEqual(self.login(next=bad).json["next"], "/traffic/", bad)

    def test_cross_site_and_oversized_posts_refused(self):
        got = self.call("POST", "/traffic-auth/login", {"email": "owner@example.com",
                                                        "password": PW},
                        {"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(got.status, 403)
        big = self.call("POST", "/traffic-auth/login",
                        {"email": "owner@example.com", "password": "x" * 5000}, SAME)
        self.assertEqual(big.status, 413)


class Check(Server):
    def test_members_only_and_each_org_apart(self):
        cookie = self.login().cookie
        got = self.check(f"/traffic/{A}/us/data/overview.json?x=1", cookie)
        self.assertEqual(got.status, 200)
        self.assertEqual((got.header("X-Skald-User"), got.header("X-Skald-Role"),
                          got.header("X-Skald-Org")), ("owner@example.com", "owner", "alpha"))
        self.assertEqual(self.check(f"/traffic/{B}/", cookie).status, 403)
        self.assertEqual(self.check("/traffic/nosuch.example/", cookie).status, 403)
        bob = self.login("bob@example.com").cookie
        self.assertEqual(self.check(f"/traffic/{B}/", bob).status, 200)
        self.assertEqual(self.check(f"/traffic/{A}/", bob).status, 403)
        viewer = self.login("viewer@example.com").cookie
        self.assertEqual(self.check(f"/traffic/{A}/", viewer).header("X-Skald-Role"), "viewer")

    def test_the_switcher_for_anyone_signed_in(self):
        bob = self.login("bob@example.com").cookie
        for uri in ("/traffic/", "/traffic/index.html", "/traffic/_app/app.css?v=3"):
            self.assertEqual(self.check(uri, bob).status, 200, uri)
            self.assertEqual(self.check(uri).status, 401, uri)

    def test_build_json_for_anyone_signed_in(self):
        # Every page reads ../build.json for its footer; a member of any
        # organisation may read it, nobody signed out may.
        for who in ("owner@example.com", "bob@example.com", "viewer@example.com"):
            self.assertEqual(self.check("/traffic/build.json", self.login(who).cookie).status,
                             200, who)
        self.assertEqual(self.check("/traffic/build.json").status, 401)

    def test_no_session_bad_session_expired_or_removed(self):
        self.assertEqual(self.check(f"/traffic/{A}/").status, 401)
        self.assertEqual(self.check(f"/traffic/{A}/", "made-up").status, 401)
        cookie = self.login("viewer@example.com").cookie
        db = self.db()
        try:
            accounts.remove_member(db, self.alpha["id"], self.uids["viewer@example.com"], "cli")
        finally:
            db.close()
        self.assertEqual(self.check(f"/traffic/{A}/", cookie).status, 403)
        cookie = self.login().cookie
        self.tick(15 * 86400)
        self.assertEqual(self.check(f"/traffic/{A}/", cookie).status, 401)

    def test_check_answers_nginx_only(self):
        handler = make_handler(FakeRunner(), set(), self.config, self.out, self.live)
        raw = (f"GET /traffic-auth/check HTTP/1.1\r\nHost: x\r\nX-Original-URI: /traffic/{A}/"
               f"\r\nCookie: skald_session={self.login().cookie}\r\n\r\n").encode()
        out = io.BytesIO()

        class Socket:
            def makefile(self, mode, *a, **k):
                return io.BytesIO(raw)

            def sendall(self, data):
                out.write(data)

        handler(Socket(), ("198.51.100.9", 5555), None)
        self.assertEqual(int(out.getvalue().split()[1]), 403)


class SharedCodePass(Server):
    """The app's code: a session that passed the full check in the last 30 s goes
    through again without the accounts database; a site's files never do."""

    def setUp(self):
        super().setUp()
        auth_api._shared.clear()
        self.now = [1000.0]
        patcher = mock.patch.object(auth_api.time, "monotonic", lambda: self.now[0])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(auth_api._shared.clear)

    def end_elsewhere(self, cookie):
        db = self.db()
        try:
            sessions.end(db, cookie)
        finally:
            db.close()

    def test_code_passes_for_a_while_a_site_file_never(self):
        cookie = self.login("bob@example.com").cookie
        code = "/traffic/_app/js/main.js?v=0a1b2c3d4e5f"
        self.assertEqual(self.check(code, cookie).status, 200)
        self.end_elsewhere(cookie)                       # e.g. signed out on another device
        got = self.check(code, cookie)
        self.assertEqual(got.status, 200)
        self.assertEqual(got.header("X-Skald-User"), "bob@example.com")
        self.assertEqual(self.check(f"/traffic/{B}/data/overview.json", cookie).status, 401)
        self.now[0] += auth_api.SHARED_SECONDS
        self.assertEqual(self.check(code, cookie).status, 401)

    def test_no_pass_without_a_full_check_first(self):
        cookie = self.login("bob@example.com").cookie
        self.assertEqual(self.check(f"/traffic/{B}/", cookie).status, 200)   # a site page
        self.end_elsewhere(cookie)
        self.assertEqual(self.check("/traffic/_app/app.css?v=3", cookie).status, 401)
        self.assertEqual(self.check("/traffic/_app/app.css?v=3").status, 401)
        self.assertEqual(self.check("/traffic/_app/app.css?v=3", "made-up").status, 401)

    def test_signing_out_here_ends_the_pass_at_once(self):
        cookie = self.login().cookie
        self.assertEqual(self.check("/traffic/_app/app.css?v=3", cookie).status, 200)
        self.call("POST", "/traffic-auth/logout", None, SAME, cookie=cookie)
        self.assertEqual(self.check("/traffic/_app/app.css?v=3", cookie).status, 401)

    def test_the_pass_is_kept_by_a_hash_never_the_cookie(self):
        cookie = self.login().cookie
        self.check("/traffic/build.json", cookie)
        self.assertTrue(auth_api._shared)
        self.assertNotIn(cookie, auth_api._shared)


class Logout(Server):
    def test_logout_ends_the_session_and_clears_the_cookie(self):
        cookie = self.login().cookie
        got = self.call("POST", "/traffic-auth/logout", None, SAME, cookie=cookie)
        self.assertEqual(got.status, 303)
        self.assertEqual(got.header("Location"), "/traffic-auth/login")
        self.assertIn("Max-Age=0", got.header("Set-Cookie"))
        self.assertEqual(self.check(f"/traffic/{A}/", cookie).status, 401)


class ForgotAndReset(Server):
    def test_forgot_always_the_same_answer(self):
        self.mail_on()
        known = self.call("POST", "/traffic-auth/forgot", {"email": "owner@example.com"}, SAME)
        unknown = self.call("POST", "/traffic-auth/forgot", {"email": "nobody@example.com"},
                            SAME)
        broken = self.call("POST", "/traffic-auth/forgot", {"email": "not an address"}, SAME)
        self.assertEqual({known.status, unknown.status, broken.status}, {200})
        self.assertEqual(known.raw, unknown.raw)
        self.assertEqual(known.raw, broken.raw)
        auth_api.drain()
        self.assertEqual([to for to, _ in self.sent], ["owner@example.com"])
        msg = self.sent[0][1]
        self.assertEqual(msg["Subject"], "[Skald] Reset your password")
        self.assertEqual(msg["To"], "owner@example.com")
        self.assertIn("https://www.example.com/traffic-auth/reset?t=",
                      msg.get_body(("plain",)).get_content())

    def test_no_mail_set_up_sends_nothing_and_says_the_same(self):
        got = self.call("POST", "/traffic-auth/forgot", {"email": "owner@example.com"}, SAME)
        auth_api.drain()
        self.assertEqual(got.status, 200)
        self.assertEqual(self.sent, [])

    def test_a_reset_link_works_once_and_signs_out_everywhere(self):
        old = self.login().cookie
        db = self.db()
        try:
            token = accounts.request_reset(db, "owner@example.com")
        finally:
            db.close()
        new_pw = "a brand new long passphrase"
        got = self.call("POST", "/traffic-auth/reset", {"token": token, "password": new_pw}, SAME)
        self.assertEqual((got.status, got.json["next"]), (200, "/traffic-auth/login"))
        again = self.call("POST", "/traffic-auth/reset", {"token": token, "password": new_pw},
                          SAME)
        self.assertEqual(again.status, 400)
        self.assertIn("already used", again.json["error"])
        self.assertEqual(self.check(f"/traffic/{A}/", old).status, 401)
        self.assertEqual(self.login(password=new_pw).status, 200)
        weak = self.call("POST", "/traffic-auth/reset", {"token": "x" * 40, "password": "short"},
                         SAME)
        self.assertEqual(weak.status, 400)


class Invites(Server):
    def make_invite(self, email, role="viewer", org=None):
        db = self.db()
        try:
            return accounts.invite(db, (org or self.alpha)["id"], email, role,
                                   self.uids["owner@example.com"])
        finally:
            db.close()

    def test_a_new_person_joins_and_is_signed_in(self):
        token = self.make_invite("new@example.com", "admin")
        info = self.call("GET", f"/traffic-auth/invite-info?t={token}")
        self.assertEqual(info.json, {"ok": True, "org": "Alpha", "email": "new@example.com",
                                     "role": "admin", "has_account": False})
        got = self.call("POST", "/traffic-auth/invite",
                        {"token": token, "name": "New Person", "password": "short"}, SAME)
        self.assertEqual(got.status, 400)
        got = self.call("POST", "/traffic-auth/invite",
                        {"token": token, "name": "New Person", "password": PW}, SAME)
        self.assertEqual((got.status, got.json["next"]), (200, f"/traffic/{A}/"))
        check = self.check(f"/traffic/{A}/", got.cookie)
        self.assertEqual((check.status, check.header("X-Skald-Role")), (200, "admin"))
        used = self.call("POST", "/traffic-auth/invite", {"token": token, "password": PW}, SAME)
        self.assertEqual(used.status, 400)
        self.assertEqual(self.call("GET", f"/traffic-auth/invite-info?t={token}").status, 400)

    def test_an_existing_account_joins_but_must_sign_in_itself(self):
        token = self.make_invite("bob@example.com")
        info = self.call("GET", f"/traffic-auth/invite-info?t={token}")
        self.assertTrue(info.json["has_account"])
        got = self.call("POST", "/traffic-auth/invite", {"token": token}, SAME)
        self.assertEqual(got.status, 200)
        self.assertIsNone(got.cookie)          # the link alone never signs an account in
        bob = self.login("bob@example.com").cookie
        self.assertEqual(self.check(f"/traffic/{A}/", bob).status, 200)
        self.assertEqual(self.check(f"/traffic/{B}/", bob).status, 200)


class BasicMode(Server):
    MODE = "basic"

    def test_the_new_routes_are_not_there(self):
        for method, path in (("GET", "/traffic-auth/login"), ("GET", "/traffic-auth/check"),
                             ("POST", "/traffic-auth/login"), ("GET", f"/traffic/{A}/team"),
                             ("GET", f"/traffic/{A}/account"),
                             ("POST", f"/traffic/{A}/tokens/create")):
            got = self.call(method, path, {} if method == "POST" else None, SAME)
            self.assertEqual(got.status, 404, path)

    def test_me_is_as_before(self):
        got = self.call("GET", f"/traffic/{A}/me", headers={"X-Skald-User": "morgan"})
        self.assertEqual(got.json, {"ok": True, "user": "morgan", "role": "admin"})


if __name__ == "__main__":
    unittest.main()
