"""Settings > Organisations over real HTTP (orgs_api.py, sessions mode): every
route, the role checks, the last-owner guards, archive and restore, moving a
site in with its keys, and CSRF. Site access per member has its own file
(test_site_access.py). Addresses are example.com; no real secret anywhere."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, Server  # noqa: E402

from skald import accounts  # noqa: E402
from skald.accounts import apitokens, site_state  # noqa: E402

T = f"/traffic/{A}/"
OWNER, ADMIN, VIEWER, BOB = ("owner@example.com", "admin@example.com", "viewer@example.com",
                             "bob@example.com")


class Case(Server):
    def as_(self, email=OWNER):
        cookie, csrf = self.session(email)
        return cookie, csrf

    def get(self, act, cookie, **q):
        query = "&".join(f"{k}={v}" for k, v in q.items())
        return self.call("GET", T + act + (f"?{query}" if query else ""), cookie=cookie)

    def do(self, act, body, who=OWNER, path=T):
        cookie, csrf = self.as_(who)
        return self.post(path + act, body, cookie, csrf)

    def install_admin(self, email=OWNER):
        db = self.db()
        try:
            accounts.set_install_admin(db, self.uids[email], True, "cli")
        finally:
            db.close()

    def role(self, email, org):
        db = self.db()
        try:
            return accounts.role_in(db, self.uids[email], org["id"])
        finally:
            db.close()


class Reading(Case):
    def test_a_member_sees_only_their_own(self):
        cookie, _ = self.as_()
        got = self.get("orgs", cookie).json
        self.assertEqual([o["name"] for o in got["orgs"]], ["Alpha"])
        card = got["orgs"][0]
        self.assertEqual((card["sites"], card["members"], card["state"], card["privacy_class"],
                          card["plan"], card["role"]), ([A], 3, "active", "internal", None, "owner"))
        self.assertEqual(got["current"], self.alpha["id"])
        self.assertFalse(got["can_create"])

    def test_an_install_admin_sees_every_one(self):
        self.install_admin()
        cookie, _ = self.as_()
        got = self.get("orgs", cookie).json
        self.assertEqual([(o["name"], o["role"]) for o in got["orgs"]],
                         [("Alpha", "owner"), ("Beta", None)])
        self.assertTrue(got["can_create"])
        beta = self.get("orgs/show", cookie, org=self.beta["id"]).json
        self.assertEqual((beta["org"]["name"], beta["acts"], beta["role"]), ("Beta", "owner", None))
        self.assertTrue(beta["may"]["privacy"])

    def test_another_organisation_is_not_found(self):
        cookie, _ = self.as_()
        got = self.get("orgs/show", cookie, org=self.beta["id"])
        self.assertEqual(got.status, 404)
        self.assertNotIn("Beta", got.raw.decode())
        for bad in ("x", "", "999", "1%200"):
            self.assertEqual(self.get("orgs/show", cookie, org=bad).status, 404, bad)

    def test_a_viewer_reads_but_sees_no_invites_or_keys(self):
        db = self.db()
        try:
            apitokens.create(db, self.alpha["id"], "sheet", scopes=["read"])
        finally:
            db.close()
        self.do("orgs/member/invite", {"org": self.alpha["id"], "email": "new@example.com",
                                       "role": "viewer"})
        cookie, _ = self.as_(VIEWER)
        got = self.get("orgs/show", cookie, org=self.alpha["id"]).json
        self.assertEqual((got["invites"], got["keys"], got["movable"]), ([], [], []))
        self.assertFalse(got["may"]["members"])
        self.assertEqual(len(got["members"]), 3)
        self.assertEqual(self.get("orgs/auditlog", cookie, org=self.alpha["id"]).status, 403)
        admin, _ = self.as_(ADMIN)
        got = self.get("orgs/show", admin, org=self.alpha["id"]).json
        self.assertEqual([i["email"] for i in got["invites"]], ["new@example.com"])
        self.assertEqual([k["name"] for k in got["keys"]], ["sheet"])
        self.assertNotIn("org_id", got["keys"][0])

    def test_the_overview_withholds_what_the_history_does_not_hold(self):
        cookie, _ = self.as_()
        got = self.get("orgs/show", cookie, org=self.alpha["id"]).json["overview"]
        self.assertEqual((got["sites"], got["members"]), (1, 3))
        self.assertIsNone(got["requests_7d"])          # Not recorded, never 0
        self.assertIsNone(got["last_day"])

    def test_basic_mode_and_the_wrong_method(self):
        cookie, csrf = self.as_()
        self.assertEqual(self.post(T + "orgs", {}, cookie, csrf).status, 405)
        self.assertEqual(self.call("GET", T + "orgs/rename", cookie=cookie).status, 405)
        self.assertEqual(self.call("GET", T + "orgs").status, 401)
        self.config["access"]["mode"] = "basic"
        self.assertEqual(self.call("GET", T + "orgs", cookie=cookie).status, 404)

    def test_every_post_needs_the_csrf_value(self):
        cookie, csrf = self.as_()
        body = {"org": self.alpha["id"], "name": "Alpha Two"}
        for bad in (None, "wrong", csrf + "x"):
            self.assertEqual(self.post(T + "orgs/rename", body, cookie, bad).status, 403)
        self.assertEqual(self.post(T + "orgs/rename", body, cookie, csrf).status, 200)


class Organisation(Case):
    def test_only_an_install_admin_makes_one(self):
        body = {"name": "Kiwi Co", "privacy_class": "client", "owner": "me"}
        self.assertEqual(self.do("orgs/create", body).status, 403)
        self.install_admin()
        got = self.do("orgs/create", body)
        self.assertEqual(got.status, 200, got.json)
        org = got.json["org"]
        self.assertEqual((org["name"], org["privacy_class"], org["role"]),
                         ("Kiwi Co", "client", "owner"))
        db = self.db()
        try:
            actions = [e["action"] for e in accounts.auditlog.recent(db, org["id"])]
        finally:
            db.close()
        self.assertEqual(sorted(actions), ["member.add", "org.create", "org.privacy"])

    def test_the_first_owner_by_email_and_sites_moved_in(self):
        self.install_admin()
        got = self.do("orgs/create", {"name": "Bob Co", "owner": BOB, "sites": [B]})
        self.assertEqual(got.status, 200, got.json)
        db = self.db()
        try:
            new = got.json["org"]["id"]
            self.assertEqual(accounts.role_in(db, self.uids[BOB], new), "owner")
            self.assertIsNone(accounts.role_in(db, self.uids[OWNER], new))
            self.assertEqual(accounts.sites_of_org(db, new), [B])
        finally:
            db.close()
        # Someone with no account yet gets an invite (the link, without mail); no
        # site moves in before they join.
        got = self.do("orgs/create", {"name": "New Co", "owner": "new@example.com",
                                      "sites": [A]})
        self.assertEqual(got.status, 400)
        got = self.do("orgs/create", {"name": "New Co", "owner": "new@example.com"})
        self.assertEqual(got.status, 200, got.json)
        self.assertIn("/traffic-auth/invite?t=", got.json["link"])
        for bad in ({"name": ""}, {"name": "X", "privacy_class": "secret"},
                    {"name": "X", "owner": "not an email"}, {"name": "X", "sites": ["no.example"]}):
            self.assertEqual(self.do("orgs/create", bad).status, 400, bad)

    def test_rename_by_an_admin_not_a_viewer(self):
        org = self.alpha["id"]
        self.assertEqual(self.do("orgs/rename", {"org": org, "name": "Alpha Ltd"}, VIEWER).status,
                         403)
        got = self.do("orgs/rename", {"org": org, "name": "Alpha Ltd"}, ADMIN)
        self.assertEqual((got.status, got.json["name"]), (200, "Alpha Ltd"))
        self.assertEqual(self.do("orgs/rename", {"org": self.beta["id"], "name": "x"}).status,
                         404)

    def test_the_privacy_class_is_an_install_admins(self):
        body = {"org": self.alpha["id"], "privacy_class": "client"}
        self.assertEqual(self.do("orgs/privacy", body).status, 403)       # an owner only
        self.install_admin()
        got = self.do("orgs/privacy", body)
        self.assertEqual((got.status, got.json["privacy_class"]), (200, "client"))
        self.assertEqual(self.do("orgs/privacy", {**body, "privacy_class": "x"}).status, 400)
        db = self.db()
        try:
            self.assertEqual(accounts.orgs.privacy_class(db, self.alpha["id"]), "client")
            self.assertIn("org.privacy", [e["action"] for e in
                                          accounts.auditlog.recent(db, self.alpha["id"])])
        finally:
            db.close()

    def test_archive_and_restore(self):
        db = self.db()
        try:
            accounts.assign_site(db, "gamma.example", self.alpha["id"], "cli")
            site_state.pause(db, self.alpha["id"], "gamma.example", "cli")   # paused before
        finally:
            db.close()
        org = {"org": self.alpha["id"]}
        self.assertEqual(self.do("orgs/archive", org, ADMIN).status, 403)   # owners only
        got = self.do("orgs/archive", org)
        self.assertEqual((got.status, got.json["paused"]), (200, [A]))
        self.assertEqual(self.do("orgs/archive", org).status, 400)          # already
        db = self.db()
        try:
            self.assertTrue(site_state.get(db, A)["paused_at"])
            self.assertEqual(accounts.get_org(db, self.alpha["id"])["archived_at"] is not None,
                             True)
        finally:
            db.close()
        # Nothing is deleted: the site's files are all there, and members still read it.
        self.assertTrue((self.out / A / "data" / "overview.json").is_file())
        cookie, _ = self.as_()
        listed = self.get("orgs", cookie).json["orgs"][0]
        self.assertEqual(listed["state"], "archived")
        got = self.do("orgs/restore", org)
        self.assertEqual((got.status, got.json["resumed"]), (200, [A]))
        db = self.db()
        try:
            self.assertIsNone(site_state.get(db, A)["paused_at"])
            self.assertTrue(site_state.get(db, "gamma.example")["paused_at"])   # as it was
            self.assertIsNone(accounts.get_org(db, self.alpha["id"])["archived_at"])
            actions = [e["action"] for e in accounts.auditlog.recent(db, self.alpha["id"])]
        finally:
            db.close()
        self.assertIn("org.archive", actions)
        self.assertIn("org.restore", actions)
        self.assertEqual(self.do("orgs/restore", org).status, 400)          # not archived

    def test_settings_the_sign_in_rule_is_an_owners(self):
        org = self.alpha["id"]
        got = self.do("orgs/prefs", {"org": org, "require_totp": True}, ADMIN)
        self.assertEqual(got.status, 403)
        got = self.do("orgs/prefs", {"org": org, "mail_daily": False}, ADMIN)
        self.assertEqual((got.status, got.json["settings"]["mail_daily"]), (200, False))
        self.assertEqual(self.do("orgs/prefs", {"org": org, "mail_daily": "no"}).status, 400)
        self.assertEqual(self.do("orgs/prefs", {"org": org}).status, 400)
        got = self.do("orgs/prefs", {"org": org, "require_totp": True})
        self.assertTrue(got.json["settings"]["require_totp"])


class MoveSite(Case):
    def test_a_site_moves_in_with_its_keys_and_they_keep_working(self):
        db = self.db()
        try:      # bob, Beta's owner, made the site's shipper token
            token = apitokens.create(db, self.beta["id"], "shipper", sites=[B],
                                     scopes=["ingest"], actor=self.uids[BOB])
            accounts.add_member(db, self.beta["id"], self.uids[OWNER], "admin", "cli")
        finally:
            db.close()
        got = self.do("orgs/move-site", {"org": self.alpha["id"], "site": B})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual((got.json["from"], len(got.json["tokens"]), len(got.json["recredited"])),
                         ("Beta", 1, 1))
        db = self.db()
        try:
            self.assertEqual(accounts.sites_of_org(db, self.alpha["id"]), [A, B])
            ok, why, entry = apitokens.check(db, f"Bearer {token}", B, "ingest")
            self.assertTrue(ok, why)                     # creator_ok stays true
            self.assertEqual(entry["created_by"], str(self.uids[OWNER]))
        finally:
            db.close()

    def test_only_from_an_organisation_you_manage(self):
        got = self.do("orgs/move-site", {"org": self.alpha["id"], "site": B})
        self.assertEqual(got.status, 403)                # not an admin of Beta
        got = self.do("orgs/move-site", {"org": self.alpha["id"], "site": B}, VIEWER)
        self.assertEqual(got.status, 403)
        db = self.db()
        try:
            self.assertEqual(accounts.sites_of_org(db, self.beta["id"]), [B])
        finally:
            db.close()


class Members(Case):
    def test_invite_role_and_remove_by_id(self):
        org = self.alpha["id"]
        got = self.do("orgs/member/invite", {"org": org, "email": "new@example.com",
                                             "role": "viewer"}, ADMIN)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.do("orgs/member/invite", {"org": org, "email": "o@example.com",
                                                        "role": "owner"}, ADMIN).status, 403)
        viewer = self.uids[VIEWER]
        got = self.do("orgs/member/role", {"org": org, "user": viewer, "role": "admin"}, ADMIN)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.role(VIEWER, self.alpha), "admin")
        self.assertEqual(self.do("orgs/member/role", {"org": org, "user": viewer,
                                                      "role": "owner"}, ADMIN).status, 403)
        self.assertEqual(self.do("orgs/member/remove", {"org": org, "user": viewer},
                                 VIEWER).status, 200)    # now an admin
        self.assertIsNone(self.role(VIEWER, self.alpha))
        self.assertEqual(self.do("orgs/member/remove", {"org": org, "user": 9999}).status, 404)
        self.assertEqual(self.do("orgs/member/remove", {"org": org, "user": self.uids[BOB]}).status,
                         404)                            # not a member of Alpha

    def test_the_last_owner_is_never_removed_or_demoted(self):
        org, me = self.alpha["id"], self.uids[OWNER]
        got = self.do("orgs/member/remove", {"org": org, "user": me})
        self.assertEqual(got.status, 400)
        self.assertIn("only owner", got.json["error"])
        self.assertEqual(self.do("orgs/member/role", {"org": org, "user": me,
                                                      "role": "admin"}).status, 400)
        self.assertEqual(self.do("orgs/leave", {"org": org}).status, 400)
        self.assertEqual(self.role(OWNER, self.alpha), "owner")
        # An admin cannot touch an owner at all.
        self.assertEqual(self.do("orgs/member/remove", {"org": org, "user": me}, ADMIN).status,
                         403)

    def test_transfer_hands_the_ownership_on(self):
        org = self.alpha["id"]
        self.assertEqual(self.do("orgs/transfer", {"org": org, "user": self.uids[OWNER]},
                                 ADMIN).status, 403)
        self.assertEqual(self.do("orgs/transfer", {"org": org, "user": self.uids[OWNER]}).status,
                         400)                            # yourself
        got = self.do("orgs/transfer", {"org": org, "user": self.uids[ADMIN]})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual((self.role(ADMIN, self.alpha), self.role(OWNER, self.alpha)),
                         ("owner", "admin"))
        # Now the former owner may leave; the new one, the only owner, may not.
        self.assertEqual(self.do("orgs/leave", {"org": org}, ADMIN).status, 400)
        self.assertEqual(self.do("orgs/leave", {"org": org}).status, 200)
        self.assertIsNone(self.role(OWNER, self.alpha))

    def test_a_viewer_leaves(self):
        self.assertEqual(self.do("orgs/leave", {"org": self.alpha["id"]}, VIEWER).status, 200)
        self.assertIsNone(self.role(VIEWER, self.alpha))

    def test_invites_resend_and_cancel(self):
        org = self.alpha["id"]
        self.do("orgs/member/invite", {"org": org, "email": "new@example.com", "role": "viewer"})
        got = self.do("orgs/invite/resend", {"org": org, "email": "new@example.com"}, ADMIN)
        self.assertEqual(got.status, 200, got.json)
        self.assertIn("link", got.json)                  # no mail set up: the link back
        self.assertEqual(self.do("orgs/invite/resend", {"org": org, "email": "x@example.com"}
                                 ).status, 404)
        self.assertEqual(self.do("orgs/invite/cancel", {"org": org, "email": "new@example.com"},
                                 VIEWER).status, 403)
        self.assertEqual(self.do("orgs/invite/cancel", {"org": org, "email": "new@example.com"}
                                 ).status, 200)
        self.assertEqual(self.do("orgs/invite/cancel", {"org": org, "email": "new@example.com"}
                                 ).status, 404)

    def test_keys_revoke_and_the_audit(self):
        db = self.db()
        try:
            token = apitokens.create(db, self.alpha["id"], "sheet", scopes=["read"])
        finally:
            db.close()
        tid = token.split("_")[1]
        org = self.alpha["id"]
        self.assertEqual(self.do("orgs/token-revoke", {"org": org, "id": tid}, VIEWER).status,
                         403)
        self.assertEqual(self.do("orgs/token-revoke", {"org": org, "id": tid}, ADMIN).status,
                         200)
        self.assertEqual(self.do("orgs/token-revoke", {"org": self.beta["id"], "id": tid}).status,
                         404)
        cookie, _ = self.as_(ADMIN)
        got = self.get("orgs/auditlog", cookie, org=org).json["entries"]
        self.assertEqual(got[0]["action"], "token.revoke")


if __name__ == "__main__":
    unittest.main()
