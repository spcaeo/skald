"""The security review's fixes over real HTTP (sessions mode, auth_support.Server):

  1  the nginx check refuses addresses nginx would read differently, and the
     raw address and nginx's own path must name the same site
  2  install-wide settings (bot policy, funnels, internal addresses) need an
     install admin; the address list shows each admin only what is theirs
  4  forty sign-ins at once after the limit get at most one real check;
     a busy password checker answers 503 with Retry-After
  5  the helper takes identity and role from the session cookie, never from
     X-Skald-User / X-Skald-Role; X-Real-IP only from the proxy; a Unix socket
  6  handed invite links, two-step needs the password, sites.json per org

Addresses are example.com and RFC 5737; no real secret anywhere.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, PW, SAME, Answer, Server  # noqa: E402

from skald import accounts, auth_api, ours_store, refresh_server  # noqa: E402
from skald.accounts import passwords  # noqa: E402

T = f"/traffic/{A}/"
NEW_PW = "a fresh long passphrase"


def install_admin(case, email):
    db = case.db()
    try:
        accounts.set_install_admin(db, case.uids[email], True, "cli")
    finally:
        db.close()


# ------------------------------------------------------------------ 1

class CheckReadsTheAddressLikeNginx(Server):
    def test_tricks_that_nginx_would_resolve_to_another_site_are_refused(self):
        cookie = self.login().cookie                     # a member of alpha only
        for uri in (f"/traffic//{B}/data/overview.json",
                    f"/traffic/_app/%2e%2e/{B}/data/overview.json",
                    f"/traffic/_app/..%2f{B}/data/overview.json",
                    f"/traffic/{A}/%2e%2e/{B}/",
                    f"/traffic/{A}/%2E%2E/{B}/",
                    f"/traffic/%61lpha.example/",
                    f"/traffic/_app/../{B}/",
                    f"/traffic/./{B}/",
                    f"/traffic/{A}/..\\{B}/",
                    f"/traffic/_app\\..\\{B}/",
                    f"/traffic/{A}#/../../{B}/",
                    f"/traffic/{A}/ /",
                    "/traffic/ALPHA.EXAMPLE/", "/traffic/_APP/app.js", "/Traffic/_app/x",
                    "/traffic/_App/%2e%2e/beta.example/"):
            got = self.check(uri, cookie, path=f"/traffic/{A}/")
            self.assertEqual(got.status, 403, uri)

    def test_the_raw_address_and_nginxs_path_must_name_the_same_site(self):
        cookie = self.login().cookie
        self.assertEqual(self.check(T, cookie, path=f"/traffic/{B}/").status, 403)
        self.assertEqual(self.check("/traffic/_app/x.js", cookie, path=f"/traffic/{B}/").status,
                         403)
        self.assertEqual(self.check(T, cookie, path="").status, 403)       # header missing
        self.assertEqual(self.check(T, cookie, path=f"/traffic/{A}/x/../").status, 403)

    def test_plain_addresses_still_work(self):
        cookie = self.login().cookie
        for uri, path in ((T, T + "index.html"), ("/traffic/", "/traffic/index.html"),
                          (T + "data/overview.json?range=7d&q=%20x%2F",
                           T + "data/overview.json"),
                          ("/traffic/_app/app.css?v=3", "/traffic/_app/app.css"),
                          ("/traffic/sites.json", "/traffic/sites.json"),
                          ("/traffic", "/traffic")):
            self.assertEqual(self.check(uri, cookie, path=path).status, 200, uri)

    def test_unit_parse(self):
        self.assertIsNone(auth_api.strict_path("/traffic/a/%2e%2e/b/"))
        self.assertIsNone(auth_api.strict_path("/traffic//b/"))
        self.assertEqual(auth_api.strict_path("/traffic/a/?x=%2e%2e"), "/traffic/a/")
        self.assertEqual(auth_api.site_of_uri("/traffic/sites.json"), "")


# ------------------------------------------------------------------ 2

class InstallWideSettings(Server):
    def setUp(self):
        super().setUp()
        self.config["ours"]["addresses"] = [{"ip": "192.0.2.50", "label": "office"}]
        self.config["bot_policy"] = {"file": str(self.live / "bot-policy.json"),
                                     "status": str(self.live / "bot-policy-applied.json")}

    def test_owner_who_is_not_install_admin_cannot_change_them(self):
        cookie, csrf = self.session()
        for path, body in (("ours/add", {"ip": "203.0.113.5", "label": "x"}),
                           ("ours/remove", {"ip": "192.0.2.50"}),
                           ("ours/add-mine", {"label": "x"}),
                           ("funnels/save", {"name": "f", "steps": "/a\n/b"}),
                           ("funnels/delete", {"name": "f"}),
                           ("bot-policy", {"owners": {}, "crawlers": {}})):
            got = self.post(T + path, body, cookie, csrf)
            self.assertEqual(got.status, 403, path)
            self.assertIn("install admin", got.json["error"], path)

    def test_an_install_admin_can(self):
        install_admin(self, "owner@example.com")
        cookie, csrf = self.session()
        got = self.post(T + "ours/add", {"ip": "203.0.113.5", "label": "Lab"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        entry = ours_store.load(ours_store.path_of(self.config))[0]
        self.assertEqual((entry["ip"], entry["site"]), ("203.0.113.5", A))
        self.assertEqual(self.post(T + "bot-policy", {"owners": {}, "crawlers": {}}, cookie,
                                   csrf).status, 200)

    def write_ours(self):
        path = ours_store.path_of(self.config)
        path.write_text(json.dumps({"entries": [
            {"ip": "203.0.113.1", "label": "alpha lab", "added_at": "2026-10-01T00:00:00+00:00",
             "added_from": "page", "site": A},
            {"ip": "203.0.113.2", "label": "beta lab", "added_at": "2026-10-01T00:00:00+00:00",
             "added_from": "page", "site": B},
            {"ip": "203.0.113.3", "label": "old", "added_at": "2026-10-01T00:00:00+00:00",
             "added_from": "page"}]}))

    def ips(self, answer):
        return sorted(e["ip"] for e in answer.json["entries"])

    def test_the_list_shows_each_admin_only_their_own(self):
        self.write_ours()
        viewer = self.login("viewer@example.com").cookie
        self.assertEqual(self.call("GET", T + "ours", headers=SAME, cookie=viewer).status, 403)
        admin = self.login("admin@example.com").cookie
        got = self.call("GET", T + "ours", headers=SAME, cookie=admin)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.ips(got), ["203.0.113.1"])           # no config, no beta's
        bob = self.login("bob@example.com").cookie
        self.assertEqual(self.ips(self.call("GET", f"/traffic/{B}/ours", headers=SAME, cookie=bob)),
                         ["203.0.113.2"])
        install_admin(self, "owner@example.com")
        owner = self.login().cookie
        self.assertEqual(self.ips(self.call("GET", T + "ours", headers=SAME, cookie=owner)),
                         ["192.0.2.50", "203.0.113.1", "203.0.113.2", "203.0.113.3"])


# ------------------------------------------------------------------ 4

class ParallelSignIns(Server):
    def test_forty_at_once_after_the_limit_get_at_most_one_real_check(self):
        for _ in range(5):
            self.assertEqual(self.login("bob@example.com", "wrong password here").status, 401)
        self.tick(31)
        real = accounts.authenticate
        checks = []

        def counted(*a, **k):
            checks.append(1)
            return real(*a, **k)
        statuses, gate = [], threading.Barrier(40)

        def one(i):
            gate.wait()
            statuses.append(self.call(
                "POST", "/traffic-auth/login",
                {"email": "bob@example.com", "password": f"guess-{i}-aaaaaaa"},
                {**SAME, "X-Real-IP": f"203.0.113.{i}"}).status)
        with mock.patch.object(auth_api.accounts, "authenticate", side_effect=counted):
            threads = [threading.Thread(target=one, args=(i,)) for i in range(40)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)
        self.assertLessEqual(len(checks), 1)
        self.assertEqual(statuses.count(429), 40 - len(checks))

    def test_the_failure_is_counted_even_if_the_check_never_ends(self):
        with mock.patch.object(auth_api.accounts, "authenticate", side_effect=passwords.Busy):
            got = self.login("bob@example.com", "anything long enough")
        self.assertEqual(got.status, 503)
        self.assertTrue(got.header("Retry-After"))
        db = self.db()
        try:
            self.assertEqual(accounts.limits.count(db, "login:email:bob@example.com"), 1)
        finally:
            db.close()

    def test_a_good_sign_in_clears_its_own_try(self):
        for _ in range(4):
            self.login("bob@example.com", "wrong password here")
        self.assertEqual(self.login("bob@example.com").status, 200)
        for _ in range(4):
            self.assertEqual(self.login("bob@example.com").status, 200)


# ------------------------------------------------------------------ 5

FORGED = {"X-Skald-User": "owner@example.com", "X-Skald-Role": "owner"}


class IdentityFromTheCookieOnly(Server):
    def test_no_session_no_answer_on_every_helper_route(self):
        for method, path in (("GET", T + "me"), ("GET", T + "funnels"),
                             ("GET", T + "api/v1/"), ("GET", T + "api/v1/overview"),
                             ("GET", T + "api/compare?a=x&b=y"), ("GET", T + "api/page?path=/"),
                             ("GET", T + "bot-policy"), ("GET", T + "ours"),
                             ("GET", "/traffic/sites.json"), ("GET", T + "data/sites.json"),
                             ("POST", T + "refresh"), ("POST", T + "ours/add"),
                             ("POST", T + "funnels/save"), ("POST", T + "bot-policy")):
            got = self.call(method, path, {} if method == "POST" else None,
                            {**SAME, **FORGED})
            self.assertEqual(got.status, 401, (method, path))
        self.assertEqual(self.runner.calls, [])

    def test_forged_headers_change_nothing(self):
        cookie, csrf = self.session("viewer@example.com")
        me = self.call("GET", T + "me", headers=FORGED, cookie=cookie).json
        self.assertEqual((me["user"], me["role"]), ("viewer@example.com", "viewer"))
        got = self.post(T + "ours/add", {"ip": "203.0.113.6", "label": "x"}, cookie, csrf,
                        FORGED)
        self.assertEqual(got.status, 403)

    def test_another_orgs_site_is_refused_whatever_the_headers(self):
        cookie, csrf = self.session()
        for method, path in (("GET", f"/traffic/{B}/api/v1/overview"),
                             ("GET", f"/traffic/{B}/me"), ("GET", f"/traffic/{B}/funnels"),
                             ("POST", f"/traffic/{B}/refresh")):
            got = self.call(method, path, {} if method == "POST" else None,
                            {**SAME, **FORGED, "X-Skald-CSRF": csrf}, cookie=cookie)
            self.assertEqual(got.status, 403, path)
        self.assertEqual(self.call("GET", T + "api/v1/overview", cookie=cookie).status, 200)
        self.assertEqual(self.call("POST", T + "refresh", None, SAME, cookie=cookie).status, 303)

    def test_token_routes_still_need_no_session(self):
        db = self.db()
        try:
            token = accounts.apitokens.create(db, self.alpha["id"], "script", actor="cli")
        finally:
            db.close()
        got = self.call("GET", f"/traffic-api/v1/{A}/overview",
                        headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(got.status, 200)

    def test_access_functions_ignore_the_headers(self):
        from skald import access
        cookie = self.login("viewer@example.com").cookie
        headers = {**FORGED, "Cookie": f"skald_session={cookie}"}
        self.assertEqual(access.user_from(headers, "127.0.0.1", self.config, self.live),
                         "viewer@example.com")
        self.assertEqual(access.role_of(self.config, self.live, None, headers, "127.0.0.1", A),
                         "viewer")
        self.assertEqual(access.user_from(FORGED, "127.0.0.1", self.config, self.live), "")
        self.assertEqual(access.role_of(self.config, self.live, None, FORGED, "127.0.0.1", A),
                         "")


class FakeHandler:
    def __init__(self, peer, headers):
        self.client_address = (peer, 1)
        self.headers = headers


class ProxyAddress(unittest.TestCase):
    def test_x_real_ip_only_from_the_proxy_and_only_when_trusted(self):
        hdr = {"X-Real-IP": "203.0.113.9"}
        self.assertEqual(auth_api.client_ip(FakeHandler("127.0.0.1", hdr), {}), "203.0.113.9")
        self.assertEqual(auth_api.client_ip(FakeHandler("198.51.100.1", hdr), {}),
                         "198.51.100.1")
        off = {"access": {"trust_proxy_ip": False}}
        self.assertEqual(auth_api.client_ip(FakeHandler("127.0.0.1", hdr), off), "127.0.0.1")
        self.assertIsNone(refresh_server.caller_address(hdr, "127.0.0.1", off))
        self.assertEqual(refresh_server.caller_address(hdr, "127.0.0.1", {}), "203.0.113.9")


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost", timeout=10)
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)


class UnixSocket(Server):
    def test_the_helper_can_listen_on_a_unix_socket_only(self):
        import grp
        import shutil
        folder = Path(tempfile.mkdtemp(prefix="sk", dir="/tmp"))
        self.addCleanup(shutil.rmtree, folder, True)
        sock = folder / "helper.sock"
        config = {**self.config, "refresh": {"socket": str(sock),
                                             "socket_group": grp.getgrgid(os.getgid()).gr_name}}
        handler = refresh_server.make_handler(self.runner, set(), config, self.out, self.live)
        server = refresh_server.make_server(config, handler, port=0)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, args=(0.02,), daemon=True).start()
        self.addCleanup(server.shutdown)
        self.assertEqual(server.address_family, socket.AF_UNIX)
        self.assertEqual(stat.S_IMODE(os.stat(sock).st_mode), 0o660)
        install_admin(self, "owner@example.com")
        cookie, csrf = self.session()

        def call(method, path, body=None, headers=None):
            conn = UnixConnection(str(sock))
            try:
                data = json.dumps(body).encode() if body is not None else None
                conn.request(method, path, body=data, headers={
                    "Content-Type": "application/json", "Cookie": f"skald_session={cookie}",
                    **(headers or {})})
                got = conn.getresponse()
                return Answer(got.status, dict(got.getheaders()), got.read())
            finally:
                conn.close()
        got = call("GET", "/traffic-auth/check", headers={"X-Original-URI": T,
                                                          "X-Original-Path": T})
        self.assertEqual(got.status, 200)                   # the socket's peer is the proxy
        got = call("POST", T + "ours/add-mine", {"label": "Mine"},
                   {**SAME, "X-Skald-CSRF": csrf, "X-Real-IP": "203.0.113.77"})
        self.assertEqual(got.status, 200, got.json)
        self.assertIn("203.0.113.77", [e["ip"] for e in got.json["entries"]])

    def test_without_the_setting_it_is_tcp_on_127_0_0_1(self):
        handler = refresh_server.make_handler(self.runner, set(), self.config, self.out,
                                              self.live)
        server = refresh_server.make_server(self.config, handler, port=0)
        self.addCleanup(server.server_close)
        self.assertEqual(server.server_address[0], "127.0.0.1")


# ------------------------------------------------------------------ 6

class HandedInviteLinks(Server):
    def test_an_account_from_a_shown_link_must_choose_a_new_password(self):
        cookie, csrf = self.session("admin@example.com")
        link = self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"},
                         cookie, csrf).json["link"]
        token = link.split("t=", 1)[1]
        got = self.call("POST", "/traffic-auth/invite",
                        {"token": token, "name": "New", "password": PW}, SAME)
        self.assertEqual(got.status, 200, got.json)
        self.assertIsNone(got.cookie)                       # the link holder is not signed in
        self.assertFalse(got.json["signed_in"])
        first = self.login("new@example.com")
        self.assertEqual((first.status, first.json.get("must_change")), (200, True))
        self.assertIsNone(first.cookie)
        same = self.login("new@example.com", new_password=PW)
        self.assertEqual(same.status, 400)
        weak = self.login("new@example.com", new_password="short")
        self.assertEqual(weak.status, 400)
        done = self.login("new@example.com", new_password=NEW_PW)
        self.assertEqual(done.status, 200, done.json)
        self.assertEqual(self.check(T, done.cookie).status, 200)
        self.assertEqual(self.login("new@example.com", NEW_PW).status, 200)
        self.assertEqual(self.login("new@example.com", PW).status, 401)

    def test_a_mailed_link_signs_in_at_once(self):
        self.mail_on()
        cookie, csrf = self.session("admin@example.com")
        self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"}, cookie,
                  csrf)
        text = self.sent[0][1].get_body(("plain",)).get_content()
        token = text.split("invite?t=", 1)[1].split()[0]
        got = self.call("POST", "/traffic-auth/invite",
                        {"token": token, "name": "New", "password": PW}, SAME)
        self.assertIsNotNone(got.cookie)


class TwoStepNeedsThePassword(Server):
    def test_start_needs_the_current_password(self):
        cookie, csrf = self.session()
        self.assertEqual(self.post(T + "account/totp/start", {}, cookie, csrf).status, 403)
        self.assertEqual(self.post(T + "account/totp/start", {"password": "wrong one here"},
                                   cookie, csrf).status, 403)
        got = self.post(T + "account/totp/start", {"password": PW}, cookie, csrf)
        self.assertEqual(got.status, 200)
        self.assertTrue(got.json["uri"].startswith("otpauth://"))


class SitesListPerOrg(Server):
    def setUp(self):
        super().setUp()
        listed = [{"name": s, "slug": s, "path": f"{s}/", "views": []} for s in (A, B)]
        for where, current in ((self.out / "sites.json", None),
                               (self.out / A / "data" / "sites.json", A),
                               (self.out / B / "data" / "sites.json", B)):
            where.write_text(json.dumps({"schema_version": 1, "sites": listed,
                                         "current": current}))

    def names(self, answer):
        return [s["name"] for s in answer.json["sites"]]

    def test_each_org_sees_only_its_own_site_names(self):
        alice = self.login().cookie
        bob = self.login("bob@example.com").cookie
        got = self.call("GET", "/traffic/sites.json", cookie=alice)
        self.assertEqual((got.status, self.names(got)), (200, [A]))
        self.assertNotIn(B, got.raw.decode())
        got = self.call("GET", "/traffic/sites.json", cookie=bob)
        self.assertEqual(self.names(got), [B])
        self.assertNotIn(A, got.raw.decode())
        got = self.call("GET", T + "data/sites.json", cookie=alice)
        self.assertEqual((self.names(got), got.json["current"]), ([A], A))
        self.assertEqual(self.call("GET", T + "data/sites.json", cookie=bob).status, 403)

    def test_the_root_index_lists_only_the_callers_sites(self):
        bob = self.login("bob@example.com").cookie
        for path in ("/traffic/", "/traffic/index.html"):
            got = self.call("GET", path, cookie=bob)
            self.assertEqual(got.status, 200, path)
            self.assertIn(B, got.raw.decode())
            self.assertNotIn(A, got.raw.decode())


if __name__ == "__main__":
    unittest.main()
