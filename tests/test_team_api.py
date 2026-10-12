"""The signed-in Settings routes over real HTTP (team_api.py, sessions mode):
/me, CSRF on every POST, roles per organisation, the team, your account,
API tokens and the audit log; and the token API reading accounts.sqlite."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, PW, SAME, Server  # noqa: E402

from skald import accounts  # noqa: E402
from skald.accounts import totp  # noqa: E402

T = f"/traffic/{A}/"


class Me(Server):
    def test_me_gives_the_contract_fields(self):
        cookie = self.login().cookie
        got = self.call("GET", T + "me", cookie=cookie,
                        headers={"X-Skald-User": "owner@example.com", "X-Skald-Role": "owner"})
        body = got.json
        self.assertEqual({k: body[k] for k in ("user", "name", "role", "org", "mode",
                                               "install_admin", "totp_on")},
                         {"user": "owner@example.com", "name": "Owner", "role": "owner",
                          "org": "Alpha", "mode": "sessions", "install_admin": False,
                          "totp_on": False})
        db = self.db()
        try:
            self.assertEqual(body["csrf"], accounts.sessions.resolve(db, cookie)["csrf"])
        finally:
            db.close()

    def test_the_role_comes_from_the_session_and_an_owner_is_an_admin(self):
        # The X-Skald-* headers are never believed in sessions mode (security
        # review, finding 5): the role is the session's, on the site's org.
        cookie, csrf = self.session()
        viewer = {"X-Skald-User": "viewer@example.com", "X-Skald-Role": "viewer"}
        me = self.call("GET", T + "me", headers=viewer, cookie=cookie).json
        self.assertEqual((me["user"], me["role"]), ("owner@example.com", "owner"))
        db = self.db()
        try:
            accounts.set_install_admin(db, self.uids["owner@example.com"], True, "cli")
        finally:
            db.close()
        got = self.post(T + "ours/add", {"ip": "203.0.113.5", "label": "Office"}, cookie, csrf,
                        viewer)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.call("GET", T + "ours", headers=SAME, cookie=cookie).status, 200)
        vcookie, vcsrf = self.session("viewer@example.com")
        owner = {"X-Skald-User": "owner@example.com", "X-Skald-Role": "owner"}
        got = self.post(T + "ours/add", {"ip": "203.0.113.6", "label": "x"}, vcookie, vcsrf,
                        owner)
        self.assertEqual(got.status, 403)


class Csrf(Server):
    def test_missing_or_wrong_csrf_is_refused(self):
        cookie, csrf = self.session()
        body = {"email": "new@example.com", "role": "viewer"}
        for bad in (None, "wrong", csrf + "x"):
            got = self.post(T + "team/invite", body, cookie, bad)
            self.assertEqual(got.status, 403, bad)
        self.assertEqual(self.post(T + "team/invite", body, cookie, csrf).status, 200)

    def test_another_sessions_csrf_does_not_count(self):
        cookie, _ = self.session()
        _, other = self.session("admin@example.com")
        self.assertEqual(self.post(T + "account/name", {"name": "X"}, cookie, other).status, 403)

    def test_the_old_routes_need_it_too(self):
        db = self.db()
        try:      # an install admin, so only the missing CSRF value refuses these
            accounts.set_install_admin(db, self.uids["owner@example.com"], True, "cli")
        finally:
            db.close()
        cookie, csrf = self.session()
        hdr = {"X-Skald-User": "owner@example.com", "X-Skald-Role": "owner"}
        for path, body in (("ours/add", {"ip": "203.0.113.5", "label": "x"}),
                           ("funnels/save", {"name": "f", "steps": "/a\n/b"}),
                           ("bot-policy", {"owners": {}, "crawlers": {}})):
            got = self.post(T + path, body, cookie, None, hdr)
            self.assertEqual(got.status, 403, path)
            self.assertIn("out of date", got.json["error"], path)

    def test_cross_site_post_refused_and_no_session_is_401(self):
        cookie, csrf = self.session()
        got = self.call("POST", T + "account/name", {"name": "X"},
                        {"Sec-Fetch-Site": "cross-site"}, cookie=cookie, csrf=csrf)
        self.assertEqual(got.status, 403)
        self.assertEqual(self.call("GET", T + "account").status, 401)


class Team(Server):
    def test_viewers_read_the_team_but_cannot_change_it(self):
        cookie, csrf = self.session("viewer@example.com")
        got = self.call("GET", T + "team", cookie=cookie)
        self.assertEqual(got.status, 200)
        emails = [m["email"] for m in got.json["members"]]
        self.assertEqual(emails, ["admin@example.com", "owner@example.com",
                                  "viewer@example.com"])
        self.assertEqual(set(got.json["members"][0]) >= {"email", "name", "role", "last_seen",
                                                          "totp_on"}, True)
        got = self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"},
                        cookie, csrf)
        self.assertEqual(got.status, 403)
        for path in ("tokens", "audit"):
            self.assertEqual(self.call("GET", T + path, cookie=cookie).status, 403, path)

    def test_other_orgs_are_out_of_reach(self):
        cookie, csrf = self.session()
        self.assertEqual(self.call("GET", f"/traffic/{B}/team", cookie=cookie).status, 403)
        got = self.post(f"/traffic/{B}/team/invite", {"email": "x@example.com", "role": "owner"},
                        cookie, csrf)
        self.assertEqual(got.status, 403)

    def test_invite_without_mail_gives_the_link(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertTrue(got.json["link"].startswith(
            "https://www.example.com/traffic-auth/invite?t="))
        team = self.call("GET", T + "team", cookie=cookie).json
        self.assertEqual([(i["email"], i["role"]) for i in team["invites"]],
                         [("new@example.com", "viewer")])
        self.assertTrue({"invited_by", "expires_at"} <= set(team["invites"][0]))
        again = self.post(T + "team/resend", {"email": "new@example.com"}, cookie, csrf)
        self.assertNotEqual(again.json["link"], got.json["link"])
        gone = self.post(T + "team/cancel", {"email": "new@example.com"}, cookie, csrf)
        self.assertEqual(gone.status, 200)
        self.assertEqual(self.call("GET", T + "team", cookie=cookie).json["invites"], [])

    def test_invite_with_mail_sends_it(self):
        self.mail_on()
        cookie, csrf = self.session()
        for email in ("new@example.com", "bob@example.com"):    # a new and an existing account
            got = self.post(T + "team/invite", {"email": email, "role": "viewer"}, cookie, csrf)
            self.assertEqual((got.status, got.json.get("link")), (200, None), got.json)
        self.assertEqual([to for to, _ in self.sent], ["new@example.com", "bob@example.com"])
        msg = self.sent[0][1]
        self.assertEqual(msg["Subject"], "[Skald] You are invited to Alpha")
        self.assertIn("/traffic-auth/invite?t=", msg.get_body(("plain",)).get_content())
        self.assertIn("/traffic-auth/invite?t=", msg.get_body(("html",)).get_content())
        dup = self.post(T + "team/invite", {"email": "viewer@example.com", "role": "viewer"},
                        cookie, csrf)
        self.assertEqual(dup.status, 400)

    def test_only_an_owner_makes_or_touches_an_owner(self):
        cookie, csrf = self.session("admin@example.com")
        for path, body in (("team/invite", {"email": "x@example.com", "role": "owner"}),
                           ("team/role", {"email": "viewer@example.com", "role": "owner"}),
                           ("team/role", {"email": "owner@example.com", "role": "viewer"}),
                           ("team/remove", {"email": "owner@example.com"})):
            self.assertEqual(self.post(T + path, body, cookie, csrf).status, 403, (path, body))
        got = self.post(T + "team/role", {"email": "viewer@example.com", "role": "admin"},
                        cookie, csrf)
        self.assertEqual(got.status, 200)

    def test_the_last_owner_cannot_be_removed_or_demoted(self):
        cookie, csrf = self.session()
        got = self.post(T + "team/remove", {"email": "owner@example.com"}, cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertIn("only owner", got.json["error"])
        got = self.post(T + "team/role", {"email": "owner@example.com", "role": "admin"},
                        cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertEqual(self.post(T + "team/remove", {"email": "bob@example.com"}, cookie,
                                   csrf).status, 404)

    def test_a_removed_member_loses_access_at_once(self):
        vcookie, _ = self.session("viewer@example.com")
        cookie, csrf = self.session()
        got = self.post(T + "team/remove", {"email": "viewer@example.com"}, cookie, csrf)
        self.assertEqual(got.status, 200)
        self.assertEqual(self.call("GET", T + "account", cookie=vcookie).status, 403)
        self.assertEqual(self.check(T, vcookie).status, 403)


class Account(Server):
    def test_account_lists_sessions_and_signout_all_keeps_this_one(self):
        other, _ = self.session()
        cookie, csrf = self.session()
        got = self.call("GET", T + "account", cookie=cookie).json
        self.assertEqual((got["email"], got["name"], got["totp_on"]),
                         ("owner@example.com", "Owner", False))
        self.assertEqual(len(got["sessions"]), 2)
        self.assertEqual(sum(s["current"] for s in got["sessions"]), 1)
        self.assertTrue({"agent", "created_at", "last_seen"} <= set(got["sessions"][0]))
        out = self.post(T + "account/signout-all", {}, cookie, csrf)
        self.assertEqual(out.json["ended"], 1)
        self.assertEqual(self.check(T, cookie).status, 200)
        self.assertEqual(self.check(T, other).status, 401)

    def test_name_and_password(self):
        cookie, csrf = self.session()
        self.assertEqual(self.post(T + "account/name", {"name": " New  Name "}, cookie,
                                   csrf).json["name"], "New Name")
        got = self.post(T + "account/password", {"current": "wrong one", "new": "x" * 20},
                        cookie, csrf)
        self.assertEqual(got.status, 403)
        got = self.post(T + "account/password", {"current": PW, "new": "short"}, cookie, csrf)
        self.assertEqual(got.status, 400)
        new_pw = "another long passphrase"
        got = self.post(T + "account/password", {"current": PW, "new": new_pw}, cookie, csrf)
        self.assertEqual(got.status, 200)
        self.assertEqual(self.check(T, cookie).status, 401)          # old session ended
        self.assertEqual(self.check(T, got.cookie).status, 200)      # this browser stays in
        self.assertNotEqual(got.json["csrf"], csrf)
        self.assertEqual(self.login(password=new_pw).status, 200)

    def test_two_step_on_and_off(self):
        cookie, csrf = self.session()
        start = self.post(T + "account/totp/start", {"password": PW}, cookie, csrf).json
        self.assertTrue(start["uri"].startswith("otpauth://totp/"))
        bad = self.post(T + "account/totp/confirm", {"code": "000000"}, cookie, csrf)
        self.assertEqual(bad.status, 400)
        code = totp.code_at(start["secret"], accounts.db.epoch())
        got = self.post(T + "account/totp/confirm", {"code": code}, cookie, csrf)
        self.assertEqual(len(got.json["recovery_codes"]), 10)
        self.assertTrue(self.call("GET", T + "account", cookie=cookie).json["totp_on"])
        self.assertEqual(self.login().json, {"ok": True, "needs_code": True})
        self.assertEqual(self.post(T + "account/totp/off", {"password": "nope"}, cookie,
                                   csrf).status, 403)
        self.assertEqual(self.post(T + "account/totp/off", {"password": PW}, cookie,
                                   csrf).status, 200)
        self.assertIsNotNone(self.login().cookie)


class Tokens(Server):
    def api(self, name, token, site=A):
        return self.call("GET", f"/traffic-api/v1/{site}/{name}",
                         headers={"Authorization": f"Bearer {token}"})

    def test_create_shows_once_scopes_stored_revoke_works(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "tokens/create", {"name": "Agent", "sites": [A],
                                              "scopes": ["read", "mcp"], "private": False},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        token = got.json["token"]
        self.assertTrue(token.startswith(f"skald_{got.json['id']}_"))
        self.assertEqual(got.json["scopes"], ["read", "mcp"])
        listing = self.call("GET", T + "tokens", cookie=cookie)
        self.assertNotIn(token.split("_", 2)[2], listing.raw.decode())
        entry = listing.json["tokens"][0]
        self.assertEqual((entry["name"], entry["sites"], entry["scopes"], entry["private"]),
                         ("Agent", [A], ["read", "mcp"], False))
        self.assertEqual(self.api("overview", token).status, 200)
        self.assertEqual(self.api("requests", token).status, 401)       # addresses: no
        self.assertEqual(self.api("overview", token, B).status, 401)     # another org: no
        rv = self.post(T + "tokens/revoke", {"id": entry["id"]}, cookie, csrf)
        self.assertEqual(rv.status, 200)
        self.assertEqual(self.api("overview", token).status, 401)
        self.assertTrue(self.call("GET", T + "tokens", cookie=cookie).json["tokens"][0]
                        ["revoked_at"])

    def test_bad_token_requests(self):
        cookie, csrf = self.session()
        for body in ({"name": "", "scopes": ["read"]}, {"name": "x", "scopes": ["write"]},
                     {"name": "x", "sites": [B]}, {"name": "x", "sites": "all"}):
            self.assertEqual(self.post(T + "tokens/create", body, cookie, csrf).status, 400, body)
        self.assertEqual(self.post(T + "tokens/revoke", {"id": "nope"}, cookie, csrf).status, 404)
        viewer, vcsrf = self.session("viewer@example.com")
        self.assertEqual(self.post(T + "tokens/create", {"name": "x"}, viewer, vcsrf).status, 403)


class Audit(Server):
    def test_admins_read_their_orgs_log(self):
        cookie, csrf = self.session()
        self.post(T + "team/invite", {"email": "new@example.com", "role": "viewer"}, cookie, csrf)
        got = self.call("GET", T + "audit?action=invite.send&limit=5", cookie=cookie)
        self.assertEqual([e["action"] for e in got.json["entries"]], ["invite.send"])
        everything = self.call("GET", T + "audit", cookie=cookie).json["entries"]
        self.assertNotIn("Beta", str(everything))
        self.assertTrue(all(e["org_id"] == self.alpha["id"] for e in everything))


if __name__ == "__main__":
    unittest.main()
