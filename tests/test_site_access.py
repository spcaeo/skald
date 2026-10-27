"""Site access per member (accounts schema 6, accounts/users.py): an admin or a
viewer limited to some of the organisation's sites sees only those, everywhere
a member's sites are decided: nginx's session check, /me and every helper
route, the switcher's sites.json, the tokens they make (and their use, MCP's
too), and the mails. A limit cannot be dodged by the address. Hosts are
example.com/.example; client addresses RFC 5737."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, Server  # noqa: E402

from skald import access, accounts, security_notify, todo_api  # noqa: E402
from skald.accounts import apitokens, invites, users  # noqa: E402

G = "gamma.example"                     # Alpha's second site
OWNER, ADMIN, VIEWER = "owner@example.com", "admin@example.com", "viewer@example.com"


class Limited(Server):
    def seed(self):
        super().seed()
        db = self.db()
        try:
            accounts.assign_site(db, G, self.alpha["id"], "cli")
        finally:
            db.close()
        data = self.out / G / "data"
        data.mkdir(parents=True)
        listed = {"schema_version": 1, "current": None,
                  "sites": [{"name": s, "slug": s, "path": f"{s}/"} for s in (A, B, G)]}
        (self.out / "sites.json").write_text(json.dumps(listed))
        for s in (A, G):
            (self.out / s / "data" / "sites.json").write_text(json.dumps({**listed, "current": s}))

    def limit(self, email, sites, actor="cli"):
        db = self.db()
        try:
            return users.set_site_access(db, self.alpha["id"], self.uids[email], sites, actor)
        finally:
            db.close()

    # ------------------------------------------------------------ the rules

    def test_the_default_is_every_site(self):
        db = self.db()
        try:
            self.assertIsNone(users.site_access(db, self.alpha["id"], self.uids[VIEWER]))
            self.assertEqual(users.visible_sites(db, self.alpha["id"], self.uids[VIEWER]), [A, G])
            self.assertEqual(users.site_role(db, self.uids[VIEWER], G)[0], "viewer")
        finally:
            db.close()

    def test_a_limit_is_checked_and_audited(self):
        self.assertEqual(self.limit(VIEWER, [A]), [A])
        db = self.db()
        try:
            role, org = users.site_role(db, self.uids[VIEWER], G)
            self.assertEqual((role, org["name"]), (None, "Alpha"))
            self.assertEqual(users.site_role(db, self.uids[VIEWER], A)[0], "viewer")
            for bad in ([], [B], ["nope.example"], "alpha.example", [1]):
                with self.assertRaises(ValueError, msg=bad):
                    users.set_site_access(db, self.alpha["id"], self.uids[VIEWER], bad, "cli")
            with self.assertRaises(ValueError):          # an owner sees every site
                users.set_site_access(db, self.alpha["id"], self.uids[OWNER], [A], "cli")
            rows = [e for e in accounts.auditlog.recent(db, self.alpha["id"])
                    if e["action"] == "member.sites"]
            self.assertEqual(rows[0]["detail"], f"every site -> {A}")
            # Made an owner, the limit goes.
            users.set_role(db, self.alpha["id"], self.uids[VIEWER], "owner", "cli")
            self.assertIsNone(users.site_access(db, self.alpha["id"], self.uids[VIEWER]))
        finally:
            db.close()

    # ------------------------------------------------ the session and the URL

    def test_the_session_check_refuses_the_other_site(self):
        self.limit(VIEWER, [A])
        cookie, _ = self.session(VIEWER)
        self.assertEqual(self.check(f"/traffic/{A}/", cookie).status, 200)
        for uri in (f"/traffic/{G}/", f"/traffic/{G}/data/overview.json",
                    f"/traffic/{G}/blog/data/overview.json", f"/traffic/{G}/me",
                    f"/traffic/{G}/index.html?x=/traffic/{A}/"):
            self.assertEqual(self.check(uri, cookie).status, 403, uri)
        # The address cannot dodge it: tricks are refused before any site is read.
        for uri, path in ((f"/traffic/{A}/../{G}/", f"/traffic/{G}/"),
                          (f"/traffic/{A}/%2e%2e/{G}/", f"/traffic/{G}/"),
                          (f"/traffic//{G}/", f"/traffic/{G}/"),
                          (f"/traffic/{A}/", f"/traffic/{G}/"),
                          (f"/traffic/{G.upper()}/", f"/traffic/{G.upper()}/")):
            self.assertEqual(self.check(uri, cookie, path).status, 403, uri)

    def test_me_and_every_route_on_the_other_site(self):
        self.limit(VIEWER, [A])
        cookie, csrf = self.session(VIEWER)
        self.assertEqual(self.call("GET", f"/traffic/{A}/me", cookie=cookie).status, 200)
        for path in ("me", "team", "settings", "orgs", "sites", "account"):
            got = self.call("GET", f"/traffic/{G}/{path}", cookie=cookie)
            self.assertEqual(got.status, 403, path)
        got = self.post(f"/traffic/{G}/account/name", {"name": "X"}, cookie, csrf)
        self.assertEqual(got.status, 403)

    def test_the_switcher_lists_only_their_sites(self):
        self.limit(VIEWER, [A])
        cookie, _ = self.session(VIEWER)
        for path in ("/traffic/sites.json", f"/traffic/{A}/data/sites.json"):
            got = self.call("GET", path, cookie=cookie).json["sites"]
            self.assertEqual([s["name"] for s in got], [A], path)
        page = self.call("GET", "/traffic/", cookie=cookie).raw.decode()
        self.assertNotIn(G, page)
        who = access.session_caller(self.config, self.live, {"Cookie": f"skald_session={cookie}"})
        self.assertEqual(who["member_sites"], [A])
        self.assertEqual(who["orgs"], [{"name": "Alpha", "sites": [A]}])
        # The organisations page shows them only their site too.
        orgs = self.call("GET", f"/traffic/{A}/orgs", cookie=cookie).json["orgs"]
        self.assertEqual(orgs[0]["sites"], [A])

    # ------------------------------------------------------------ tokens

    def test_tokens_they_make_stay_inside_their_sites(self):
        self.limit(ADMIN, [A])
        cookie, csrf = self.session(ADMIN)
        got = self.post(f"/traffic/{A}/tokens/create", {"name": "sheet"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["sites"], [A])         # "all sites" made for theirs
        got = self.post(f"/traffic/{A}/tokens/create", {"name": "x", "sites": [G]}, cookie, csrf)
        self.assertEqual(got.status, 400)
        self.assertIn(G, got.json["error"])

    def test_a_limit_set_later_binds_their_older_tokens_and_mcp(self):
        db = self.db()
        try:
            token = apitokens.create(db, self.alpha["id"], "all", scopes=["read", "mcp"],
                                     actor=self.uids[ADMIN])
            server = apitokens.create(db, self.alpha["id"], "server", scopes=["read"])
            self.assertTrue(apitokens.check(db, f"Bearer {token}", G)[0])
        finally:
            db.close()
        self.limit(ADMIN, [A])
        db = self.db()
        try:
            self.assertTrue(apitokens.check(db, f"Bearer {token}", A)[0])
            ok, why, _ = apitokens.check(db, f"Bearer {token}", G)
            self.assertEqual((ok, why), (False, "this token is not for that site"))
            self.assertFalse(apitokens.check(db, f"Bearer {token}", G, scope="mcp")[0])
            self.assertTrue(apitokens.check(db, f"Bearer {server}", G)[0])   # made on the server
        finally:
            db.close()
        from skald.mcp import http as mcp_http
        self.config["mcp"] = {"enabled": True}
        check = mcp_http.accounts_checker(self.config, self.live)
        self.assertTrue(check(f"Bearer {token}", A)[0])
        self.assertFalse(check(f"Bearer {token}", G)[0])

    # ------------------------------------------------------------- mails

    def test_the_mails_go_only_to_people_who_see_the_site(self):
        self.limit(VIEWER, [A])
        db = self.db()
        try:
            for fn in (security_notify.recipients, todo_api.team):
                on_g = {p["email"] for p in fn(db, G)}
                on_a = {p["email"] for p in fn(db, A)}
                self.assertNotIn(VIEWER, on_g, fn.__name__)
                self.assertIn(OWNER, on_g, fn.__name__)
                if fn is todo_api.team:              # alerts depend on each person's choice
                    self.assertIn(VIEWER, on_a)
        finally:
            db.close()

    # ------------------------------------------------- invites and the API

    def test_an_invite_carries_the_limit(self):
        db = self.db()
        try:
            token = invites.invite(db, self.alpha["id"], "client@example.com", "viewer", "cli",
                                   sites=[G])
            self.assertEqual(invites.pending(db, self.alpha["id"])[0]["sites"], [G])
            user = invites.accept(db, token, "Client", "correct horse battery staple")
            self.assertEqual(users.site_access(db, self.alpha["id"], user["id"]), [G])
            self.assertIsNone(users.site_role(db, user["id"], A)[0])
            with self.assertRaises(ValueError):
                invites.invite(db, self.alpha["id"], "c2@example.com", "viewer", "cli", sites=[B])
        finally:
            db.close()

    def test_the_api_sets_it_by_member_id(self):
        cookie, csrf = self.session(OWNER)
        org, viewer = self.alpha["id"], self.uids[VIEWER]
        got = self.post(f"/traffic/{A}/orgs/member/sites", {"org": org, "user": viewer,
                                                             "sites": [G]}, cookie, csrf)
        self.assertEqual((got.status, got.json.get("sites")), (200, [G]), got.json)
        show = self.call("GET", f"/traffic/{A}/orgs/show?org={org}", cookie=cookie).json
        self.assertEqual({m["email"]: m["sites"] for m in show["members"]}[VIEWER], [G])
        got = self.post(f"/traffic/{A}/orgs/member/sites", {"org": org, "user": viewer,
                                                             "sites": None}, cookie, csrf)
        self.assertEqual((got.status, got.json["sites"]), (200, None))
        # An admin cannot limit themselves (another admin does it); a viewer cannot at all.
        acookie, acsrf = self.session(ADMIN)
        got = self.post(f"/traffic/{A}/orgs/member/sites", {"org": org, "user": self.uids[ADMIN],
                                                             "sites": [A]}, acookie, acsrf)
        self.assertEqual(got.status, 400)
        vcookie, vcsrf = self.session(VIEWER)
        got = self.post(f"/traffic/{A}/orgs/member/sites", {"org": org, "user": viewer,
                                                             "sites": [A]}, vcookie, vcsrf)
        self.assertEqual(got.status, 403)


if __name__ == "__main__":
    unittest.main()
