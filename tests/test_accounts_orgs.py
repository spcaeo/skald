"""Organisations, sites, users and members: roles, the last owner, isolation."""
from __future__ import annotations

import unittest

from accounts_support import GOOD_PW, OTHER_PW, AccountsCase

from skald.accounts import orgs, passwords, sessions, users


class OrgTest(AccountsCase):
    def test_create_and_list(self) -> None:
        a = orgs.create_org(self.db, "Acme Demo", actor="cli")
        b = orgs.create_org(self.db, "Acme Demo", actor="cli")
        self.assertEqual(set(a), {"id", "name", "slug", "created_at", "privacy_class",
                                  "archived_at"})
        self.assertEqual((a["privacy_class"], a["archived_at"]), ("internal", None))
        self.assertEqual(a["slug"], "acme-demo")
        self.assertNotEqual(a["slug"], b["slug"])
        self.assertEqual([o["id"] for o in orgs.list_orgs(self.db)], [a["id"], b["id"]])
        self.assertEqual(self.audit_actions(a["id"]), ["org.create"])

    def test_blank_name(self) -> None:
        with self.assertRaises(ValueError):
            orgs.create_org(self.db, "  ", actor="cli")

    def test_rename(self) -> None:
        a = orgs.create_org(self.db, "Old", actor="cli")
        orgs.rename_org(self.db, a["id"], "New", actor="cli")
        self.assertEqual(orgs.get_org(self.db, a["id"])["name"], "New")

    def test_sites(self) -> None:
        a = orgs.create_org(self.db, "A", actor="cli")
        b = orgs.create_org(self.db, "B", actor="cli")
        orgs.assign_site(self.db, "example.com", a["id"], actor="cli")
        orgs.assign_site(self.db, "shop.example.com", a["id"], actor="cli")
        orgs.assign_site(self.db, "other.example.com", b["id"], actor="cli")
        self.assertEqual(orgs.sites_of_org(self.db, a["id"]), ["example.com", "shop.example.com"])
        self.assertEqual(orgs.org_of_site(self.db, "other.example.com")["id"], b["id"])
        self.assertIsNone(orgs.org_of_site(self.db, "nowhere.example.com"))
        orgs.assign_site(self.db, "example.com", b["id"], actor="cli")
        self.assertEqual(orgs.org_of_site(self.db, "example.com")["id"], b["id"])
        self.assertIn("site.assign", self.audit_actions(b["id"]))
        with self.assertRaises(ValueError):
            orgs.assign_site(self.db, "example.com", 999, actor="cli")

    def test_a_sites_own_tokens_move_with_it(self) -> None:
        """2.38.0: a token reads only its organisation's sites, so moving a site
        used to cut off its log shipper (kiwiform.com, 26 Oct 2026)."""
        from skald.accounts import apitokens
        a = orgs.create_org(self.db, "A", actor="cli")
        b = orgs.create_org(self.db, "B", actor="cli")
        for site in ("example.com", "shop.example.com"):
            orgs.assign_site(self.db, site, a["id"], actor="cli")
        own = apitokens.create(self.db, a["id"], "ship example.com", sites=["example.com"],
                               scopes=("ingest",))
        both = apitokens.create(self.db, a["id"], "two sites",
                                sites=["example.com", "shop.example.com"])
        every = apitokens.create(self.db, a["id"], "all of A")
        orgs.assign_site(self.db, "example.com", b["id"], actor="cli")
        self.assertTrue(apitokens.check(self.db, f"Bearer {own}", "example.com", "ingest")[0])
        for token in (both, every):
            self.assertFalse(apitokens.check(self.db, f"Bearer {token}", "example.com")[0])
            self.assertTrue(apitokens.check(self.db, f"Bearer {token}",
                                            "shop.example.com")[0])
        self.assertIn("token.move", self.audit_actions(b["id"]))
        orgs.assign_site(self.db, "example.com", b["id"], actor="cli")      # same org: no-op
        self.assertEqual(self.audit_actions(b["id"]).count("token.move"), 1)

    def test_a_sites_settings_and_setup_move_with_it(self) -> None:
        """2.38.0: a site made from the dashboard and moved kept its settings and
        set-up progress in the old organisation: the old Settings > Sites listed it,
        and its wizard said "There is no such site in this organisation" (26 Oct 2026)."""
        from skald.accounts import site_configs, site_setup
        a = orgs.create_org(self.db, "A", actor="cli")
        b = orgs.create_org(self.db, "B", actor="cli")
        site_configs.create(self.db, a["id"], "example.com", "cli")
        site_setup.save(self.db, a["id"], "example.com", "cli", step=4)
        orgs.assign_site(self.db, "example.com", b["id"], actor="cli")
        self.assertEqual([r["name"] for r in site_configs.listing(self.db, a["id"])], [])
        self.assertEqual([r["name"] for r in site_configs.listing(self.db, b["id"])],
                         ["example.com"])
        self.assertEqual(site_setup.save(self.db, b["id"], "example.com", "cli", step=5)["step"], 5)
        with self.assertRaises(ValueError):
            site_setup.save(self.db, a["id"], "example.com", "cli", step=5)
        self.assertEqual(self.audit_actions(b["id"]).count("site.move"), 2)
        # A move made before 2.38.0 (the site moved, its rows not): assigning it again mends it.
        site_configs.create(self.db, a["id"], "shop.example.com", "cli")
        site_setup.save(self.db, a["id"], "shop.example.com", "cli", step=3)
        self.db.execute("UPDATE sites SET org_id = ? WHERE name = ?", (b["id"], "shop.example.com"))
        orgs.assign_site(self.db, "shop.example.com", b["id"], actor="cli")
        self.assertEqual(site_setup.for_org(self.db, b["id"])["shop.example.com"]["step"], 3)
        self.assertEqual(sorted(r["name"] for r in site_configs.listing(self.db, b["id"])),
                         ["example.com", "shop.example.com"])


class UserTest(AccountsCase):
    def test_create_and_find(self) -> None:
        u = users.create_user(self.db, "  Ann@Example.COM ", "Ann", GOOD_PW, install_admin=True)
        self.assertEqual(u["email"], "ann@example.com")
        self.assertTrue(u["install_admin"])
        self.assertNotIn("pw_hash", u)
        self.assertNotIn("totp_secret", u)
        self.assertEqual(users.find_user(self.db, email="ANN@example.com")["id"], u["id"])
        full = users.find_user(self.db, user_id=u["id"], secrets=True)
        self.assertTrue(passwords.verify_password(GOOD_PW, full["pw_hash"]))
        self.assertIsNone(users.find_user(self.db, email="nobody@example.com"))
        self.assertIn("user.create", self.audit_actions())

    def test_bad_email_and_duplicate(self) -> None:
        for bad in ("", "ann", "ann@", "@example.com", "a b@example.com", "ann@example",
                    "x" * 250 + "@example.com"):
            with self.assertRaises(ValueError, msg=bad):
                users.create_user(self.db, bad, "X")
        users.create_user(self.db, "ann@example.com", "Ann")
        with self.assertRaises(ValueError):
            users.create_user(self.db, "ANN@example.com", "Ann again")

    def test_weak_password_refused(self) -> None:
        with self.assertRaises(ValueError):
            users.create_user(self.db, "ann@example.com", "Ann", "password1234")

    def test_without_password(self) -> None:
        u = users.create_user(self.db, "ann@example.com", "Ann")
        self.assertFalse(u["has_password"])
        self.assertIsNone(users.authenticate(self.db, "ann@example.com", ""))

    def test_authenticate(self) -> None:
        u = users.create_user(self.db, "ann@example.com", "Ann", GOOD_PW)
        self.assertEqual(users.authenticate(self.db, "ANN@example.com", GOOD_PW)["id"], u["id"])
        self.assertIsNone(users.authenticate(self.db, "ann@example.com", OTHER_PW))
        self.assertIsNone(users.authenticate(self.db, "bob@example.com", GOOD_PW))
        self.assertIsNone(users.authenticate(self.db, "not an email", GOOD_PW))
        users.disable_user(self.db, u["id"], actor="cli")
        self.assertIsNone(users.authenticate(self.db, "ann@example.com", GOOD_PW))

    def test_set_password_ends_sessions(self) -> None:
        u = users.create_user(self.db, "ann@example.com", "Ann", GOOD_PW)
        cookie, _ = sessions.start(self.db, u["id"], "203.0.113.10", "test")
        with self.assertRaises(ValueError):
            users.set_password(self.db, u["id"], "short", actor=u["id"])
        self.assertIsNotNone(sessions.resolve(self.db, cookie))
        users.set_password(self.db, u["id"], OTHER_PW, actor=u["id"])
        self.assertIsNone(sessions.resolve(self.db, cookie))
        self.assertIsNotNone(users.authenticate(self.db, "ann@example.com", OTHER_PW))
        self.assertIn("user.password", self.audit_actions())

    def test_disable_enable(self) -> None:
        u = users.create_user(self.db, "ann@example.com", "Ann", GOOD_PW)
        cookie, _ = sessions.start(self.db, u["id"], "203.0.113.10", "test")
        users.disable_user(self.db, u["id"], actor="cli")
        self.assertIsNotNone(users.find_user(self.db, user_id=u["id"])["disabled_at"])
        self.assertIsNone(sessions.resolve(self.db, cookie))
        users.enable_user(self.db, u["id"], actor="cli")
        self.assertIsNone(users.find_user(self.db, user_id=u["id"])["disabled_at"])
        self.assertEqual(self.audit_actions()[:2], ["user.enable", "user.disable"])

    def test_set_name(self) -> None:
        u = users.create_user(self.db, "ann@example.com", "Ann")
        users.set_name(self.db, u["id"], "  Ann B  ", actor=u["id"])
        self.assertEqual(users.find_user(self.db, user_id=u["id"])["name"], "Ann B")


class MemberTest(AccountsCase):
    def setUp(self) -> None:
        super().setUp()
        self.org = orgs.create_org(self.db, "A", actor="cli")
        self.other = orgs.create_org(self.db, "B", actor="cli")
        self.ann = users.create_user(self.db, "ann@example.com", "Ann")
        self.bob = users.create_user(self.db, "bob@example.com", "Bob")
        users.add_member(self.db, self.org["id"], self.ann["id"], "owner", actor="cli")

    def test_roles(self) -> None:
        users.add_member(self.db, self.org["id"], self.bob["id"], "viewer", actor=self.ann["id"])
        self.assertEqual(users.role_in(self.db, self.bob["id"], self.org["id"]), "viewer")
        users.set_role(self.db, self.org["id"], self.bob["id"], "admin", actor=self.ann["id"])
        self.assertEqual(users.role_in(self.db, self.bob["id"], self.org["id"]), "admin")
        got = users.members(self.db, self.org["id"])
        self.assertEqual([m["email"] for m in got], ["ann@example.com", "bob@example.com"])
        self.assertEqual(set(got[0]) >= {"id", "email", "name", "role", "added_at",
                                         "last_seen", "totp_on"}, True)
        self.assertEqual(self.audit_actions(self.org["id"])[:2], ["member.role", "member.add"])

    def test_bad_role_and_duplicate(self) -> None:
        with self.assertRaises(ValueError):
            users.add_member(self.db, self.org["id"], self.bob["id"], "god", actor="cli")
        users.add_member(self.db, self.org["id"], self.bob["id"], "viewer", actor="cli")
        with self.assertRaises(ValueError):
            users.add_member(self.db, self.org["id"], self.bob["id"], "viewer", actor="cli")
        with self.assertRaises(ValueError):
            users.set_role(self.db, self.org["id"], self.bob["id"], "root", actor="cli")

    def test_last_owner(self) -> None:
        with self.assertRaisesRegex(ValueError, "only owner"):
            users.remove_member(self.db, self.org["id"], self.ann["id"], actor="cli")
        with self.assertRaisesRegex(ValueError, "only owner"):
            users.set_role(self.db, self.org["id"], self.ann["id"], "admin", actor="cli")
        users.add_member(self.db, self.org["id"], self.bob["id"], "owner", actor="cli")
        users.set_role(self.db, self.org["id"], self.ann["id"], "admin", actor="cli")
        with self.assertRaisesRegex(ValueError, "only owner"):
            users.remove_member(self.db, self.org["id"], self.bob["id"], actor="cli")

    def test_disabled_owner_does_not_count(self) -> None:
        users.add_member(self.db, self.org["id"], self.bob["id"], "owner", actor="cli")
        users.disable_user(self.db, self.bob["id"], actor="cli")
        with self.assertRaisesRegex(ValueError, "only owner"):
            users.remove_member(self.db, self.org["id"], self.ann["id"], actor="cli")

    def test_remove(self) -> None:
        users.add_member(self.db, self.org["id"], self.bob["id"], "viewer", actor="cli")
        users.remove_member(self.db, self.org["id"], self.bob["id"], actor="cli")
        self.assertIsNone(users.role_in(self.db, self.bob["id"], self.org["id"]))
        with self.assertRaises(ValueError):
            users.remove_member(self.db, self.org["id"], self.bob["id"], actor="cli")

    def test_isolation(self) -> None:
        orgs.assign_site(self.db, "a.example.com", self.org["id"], actor="cli")
        orgs.assign_site(self.db, "b.example.com", self.other["id"], actor="cli")
        users.add_member(self.db, self.other["id"], self.bob["id"], "owner", actor="cli")
        self.assertIsNone(users.role_in(self.db, self.ann["id"], self.other["id"]))
        self.assertIsNone(users.role_in(self.db, self.bob["id"], self.org["id"]))
        self.assertEqual([o["id"] for o in orgs.list_orgs(self.db, self.ann["id"])],
                         [self.org["id"]])
        self.assertEqual(orgs.list_orgs(self.db, self.bob["id"])[0]["role"], "owner")
        self.assertEqual([m["email"] for m in users.members(self.db, self.other["id"])],
                         ["bob@example.com"])
        from skald.accounts import auditlog
        self.assertEqual({e["org_id"] for e in auditlog.recent(self.db, self.org["id"])},
                         {self.org["id"]})
        site_org = orgs.org_of_site(self.db, "b.example.com")["id"]
        self.assertIsNone(users.role_in(self.db, self.ann["id"], site_org))
        self.assertEqual(users.site_role(self.db, self.bob["id"], "b.example.com"),
                         ("owner", self.other))
        self.assertEqual(users.site_role(self.db, self.ann["id"], "b.example.com"),
                         (None, self.other))
        self.assertEqual(users.site_role(self.db, self.ann["id"], "x.example.com"), (None, None))


if __name__ == "__main__":
    unittest.main()
