"""`skald org show|archive|restore|privacy|transfer` and `skald member sites`
(cli_orgs.py), through skald's own parser and Context (support.Sandbox).
Addresses are example.com; no real secret anywhere."""
from __future__ import annotations

import unittest

from test_cli_accounts import OWNER, Case

from skald import accounts
from skald.accounts import site_state, users


class Orgs(Case):
    def setUp(self):
        super().setUp()
        code, _, err = self.init()
        self.assertEqual(code, 0, err)
        db = self.db()
        org = accounts.list_orgs(db)[0]
        self.slug = org["slug"]
        sam = accounts.create_user(db, "sam@example.com", "Sam", "correct horse battery staple")
        accounts.add_member(db, org["id"], sam["id"], "viewer", "cli")
        self.org_id, self.sam = org["id"], sam["id"]

    def test_show(self):
        code, out, err = self.run_ti("org", "show", self.slug)
        self.assertEqual(code, 0, err)
        self.assertIn("state: active", out)
        self.assertIn("plan: internal", out)
        self.assertIn("privacy class: internal", out)
        self.assertIn("sites: example.com, shop.example", out)
        self.assertRegex(out, r"sam@example.com\s+viewer\s+sees every site")
        self.assertEqual(self.run_ti("org", "show", "nope")[0], 1)

    def test_archive_and_restore(self):
        code, out, err = self.run_ti("org", "archive", self.slug)
        self.assertEqual(code, 0, err)
        self.assertIn("2 sites paused", out)
        self.assertIn("nothing is deleted", out)
        db = self.db()
        self.assertTrue(site_state.get(db, "shop.example")["paused_at"])
        self.assertEqual(self.run_ti("org", "archive", self.slug)[0], 1)   # already
        code, out, err = self.run_ti("org", "restore", self.slug)
        self.assertEqual(code, 0, err)
        self.assertIn("2 sites collect again", out)
        self.assertIsNone(site_state.get(db, "shop.example")["paused_at"])

    def test_privacy(self):
        code, out, err = self.run_ti("org", "privacy", self.slug, "client")
        self.assertEqual(code, 0, err)
        self.assertIn("follow their own retention settings", out)
        self.assertEqual(accounts.orgs.privacy_class(self.db(), self.org_id), "client")
        with self.assertRaises(SystemExit) as stop:      # argparse: not a choice
            self.run_ti("org", "privacy", self.slug, "public")
        self.assertEqual(stop.exception.code, 2)

    def test_transfer(self):
        code, out, err = self.run_ti("org", "transfer", self.slug, "sam@example.com")
        self.assertEqual(code, 0, err)
        db = self.db()
        owner = accounts.find_user(db, email=OWNER)
        self.assertEqual(accounts.role_in(db, self.sam, self.org_id), "owner")
        self.assertEqual(accounts.role_in(db, owner["id"], self.org_id), "admin")
        self.assertIn("org.transfer", [e["action"] for e in accounts.auditlog.recent(db, self.org_id)])

    def test_member_sites(self):
        code, out, err = self.run_ti("member", "sites", "sam@example.com", "shop.example")
        self.assertEqual(code, 0, err)
        self.assertIn("now sees shop.example", out)
        db = self.db()
        self.assertEqual(users.site_access(db, self.org_id, self.sam), ["shop.example"])
        code, out, _ = self.run_ti("member", "sites", "sam@example.com")
        self.assertIn("sees shop.example of", out)
        self.assertEqual(self.run_ti("member", "sites", "sam@example.com", "no.example")[0], 1)
        self.assertEqual(self.run_ti("member", "sites", "sam@example.com", "shop.example",
                                     "--all")[0], 2)
        code, out, _ = self.run_ti("member", "sites", "sam@example.com", "--all")
        self.assertIn("now sees every site", out)
        self.assertEqual(self.run_ti("member", "sites", OWNER, "shop.example")[0], 1)   # an owner


if __name__ == "__main__":
    unittest.main()

