"""API tokens per org: scopes, sites, revoking, and the move from tokens.json."""
from __future__ import annotations

import unittest

from accounts_support import AccountsCase

from skald import tokens as old_tokens
from skald.accounts import apitokens, auditlog, orgs


class TokenTest(AccountsCase):
    def setUp(self) -> None:
        super().setUp()
        self.org = orgs.create_org(self.db, "A", actor="cli")
        self.other = orgs.create_org(self.db, "B", actor="cli")
        for site in ("a.example.com", "shop.example.com"):
            orgs.assign_site(self.db, site, self.org["id"], actor="cli")
        orgs.assign_site(self.db, "b.example.com", self.other["id"], actor="cli")

    def bearer(self, token: str) -> str:
        return f"Bearer {token}"

    def test_create_and_check(self) -> None:
        token = apitokens.create(self.db, self.org["id"], "a script")
        self.assertRegex(token, r"^skald_[0-9a-f]{8}_[A-Za-z0-9_-]+$")
        self.assertNotIn(token, "\n".join(self.db.iterdump()))
        ok, why, entry = apitokens.check(self.db, self.bearer(token), "a.example.com",
                                         name="overview")
        self.assertTrue(ok, why)
        self.assertEqual(entry["org_id"], self.org["id"])
        self.assertEqual(entry["scopes"], ["read"])
        self.assertNotIn("sha256", entry)
        self.assertIn("token.create", self.audit_actions(self.org["id"]))

    def test_bad_headers(self) -> None:
        for header in (None, "", "Basic abc", "Bearer ", "Bearer skald_x", "Bearer foo_1_2",
                       "Bearer skald_deadbeef_nope"):
            ok, why, entry = apitokens.check(self.db, header, "a.example.com")
            self.assertFalse(ok, header)
            self.assertTrue(why)
            self.assertIsNone(entry)

    def test_wrong_secret(self) -> None:
        token = apitokens.create(self.db, self.org["id"], "a script")
        ok, _, _ = apitokens.check(self.db, self.bearer(token[:-2] + "zz"), "a.example.com")
        self.assertFalse(ok)

    def test_other_org_site(self) -> None:
        token = apitokens.create(self.db, self.org["id"], "a script")
        ok, why, _ = apitokens.check(self.db, self.bearer(token), "b.example.com")
        self.assertFalse(ok)
        self.assertIn("site", why)
        ok, _, _ = apitokens.check(self.db, self.bearer(token), "unassigned.example.com")
        self.assertFalse(ok)

    def test_per_site(self) -> None:
        token = apitokens.create(self.db, self.org["id"], "shop only", sites=["shop.example.com"])
        self.assertTrue(apitokens.check(self.db, self.bearer(token), "shop.example.com")[0])
        self.assertFalse(apitokens.check(self.db, self.bearer(token), "a.example.com")[0])
        with self.assertRaises(ValueError):
            apitokens.create(self.db, self.org["id"], "x", sites=["b.example.com"])

    def test_scopes(self) -> None:
        plain = apitokens.create(self.db, self.org["id"], "plain")
        private = apitokens.create(self.db, self.org["id"], "ops", private=True)
        mcp = apitokens.create(self.db, self.org["id"], "agent", scopes=("read", "mcp"))
        for name in old_tokens.PRIVATE:
            self.assertFalse(apitokens.check(self.db, self.bearer(plain), "a.example.com",
                                             name=name)[0])
            self.assertTrue(apitokens.check(self.db, self.bearer(private), "a.example.com",
                                            name=name)[0])
        self.assertFalse(apitokens.check(self.db, self.bearer(plain), "a.example.com",
                                         scope="mcp")[0])
        self.assertTrue(apitokens.check(self.db, self.bearer(mcp), "a.example.com",
                                        scope="mcp")[0])
        self.assertTrue(apitokens.check(self.db, self.bearer(private), "a.example.com",
                                        scope="read_private")[0])
        with self.assertRaises(ValueError):
            apitokens.create(self.db, self.org["id"], "x", scopes=("write",))

    def test_revoke(self) -> None:
        token = apitokens.create(self.db, self.org["id"], "a script")
        tid = token.split("_")[1]
        with self.assertRaises(ValueError):
            apitokens.revoke(self.db, self.other["id"], tid, actor="cli")
        self.assertTrue(apitokens.check(self.db, self.bearer(token), "a.example.com")[0])
        apitokens.revoke(self.db, self.org["id"], tid, actor="cli")
        ok, why, _ = apitokens.check(self.db, self.bearer(token), "a.example.com")
        self.assertFalse(ok)
        self.assertIn("revoked", why)
        listed = apitokens.listing(self.db, self.org["id"])
        self.assertIsNotNone(listed[0]["revoked_at"])
        self.assertEqual(apitokens.listing(self.db, self.other["id"]), [])
        self.assertIn("token.revoke", self.audit_actions(self.org["id"]))

    def test_last_used_once_a_minute(self) -> None:
        token = apitokens.create(self.db, self.org["id"], "a script")
        apitokens.check(self.db, self.bearer(token), "a.example.com")
        first = apitokens.listing(self.db, self.org["id"])[0]["last_used"]
        self.assertEqual(first, "2026-10-11T14:00:00Z")
        self.tick(seconds=30)
        apitokens.check(self.db, self.bearer(token), "a.example.com")
        self.assertEqual(apitokens.listing(self.db, self.org["id"])[0]["last_used"], first)
        self.tick(seconds=31)
        apitokens.check(self.db, self.bearer(token), "a.example.com")
        self.assertEqual(apitokens.listing(self.db, self.org["id"])[0]["last_used"],
                         "2026-10-11T14:01:01Z")

    def test_import_json(self) -> None:
        path = self.dir / "tokens.json"
        plain = old_tokens.create(path, "a script")
        private = old_tokens.create(path, "ops", sites=["shop.example.com"], private=True)
        gone = old_tokens.create(path, "old")
        stored = old_tokens.load(path)
        stored[gone.split("_")[1]]["revoked_at"] = "2026-01-01T00:00:00+00:00"
        old_tokens._save(path, stored)

        self.assertEqual(apitokens.import_json(self.db, path, self.org["id"]), 3)
        self.assertEqual(apitokens.import_json(self.db, path, self.org["id"]), 0)
        self.assertTrue(apitokens.check(self.db, self.bearer(plain), "a.example.com")[0])
        self.assertFalse(apitokens.check(self.db, self.bearer(plain), "a.example.com",
                                         name="requests")[0])
        self.assertTrue(apitokens.check(self.db, self.bearer(private), "shop.example.com",
                                        name="requests")[0])
        self.assertFalse(apitokens.check(self.db, self.bearer(private), "a.example.com")[0])
        self.assertFalse(apitokens.check(self.db, self.bearer(gone), "a.example.com")[0])
        names = {e["name"] for e in apitokens.listing(self.db, self.org["id"])}
        self.assertEqual(names, {"a script", "ops", "old"})
        self.assertIn("token.import", self.audit_actions(self.org["id"]))

    def test_import_missing_file(self) -> None:
        self.assertEqual(apitokens.import_json(self.db, self.dir / "none.json", self.org["id"]), 0)


class AuditTest(AccountsCase):
    def test_record_and_recent(self) -> None:
        org = orgs.create_org(self.db, "A", actor="cli")
        for i in range(5):
            auditlog.record(self.db, org["id"], "cli", "test.thing", target=f"t{i}", detail="d")
        auditlog.record(self.db, None, "cli", "install.thing")
        got = auditlog.recent(self.db, org["id"], limit=3)
        self.assertEqual([e["target"] for e in got], ["t4", "t3", "t2"])
        self.assertEqual(set(got[0]) >= {"at", "org_id", "actor", "action", "target",
                                         "detail"}, True)
        self.assertEqual(len(auditlog.recent(self.db, org["id"], action="org.create")), 1)
        self.assertEqual(len(auditlog.recent(self.db, None)), 7)

    def test_actor_email(self) -> None:
        from skald.accounts import users
        ann = users.create_user(self.db, "ann@example.com", "Ann", actor="cli")
        org = orgs.create_org(self.db, "A", actor=ann["id"])
        self.assertEqual(auditlog.recent(self.db, org["id"])[0]["actor_email"], "ann@example.com")


if __name__ == "__main__":
    unittest.main()
