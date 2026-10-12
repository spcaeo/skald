"""The security review's fixes in the accounts library (no HTTP):

  3  one scrypt on every early return of a password check (no timing tell)
  4  sign-in tries taken atomically before the check; at most 2 scrypt at once
  6a an invite whose link was handed to the admin makes a must-reset account
  6c a token stops when its creator is disabled or no longer an admin
  6d the last active owner of an organisation cannot be disabled
  and the library gaps: resets.issue_for, users.set_install_admin, counts.

Addresses are example.com; no real secret anywhere.
"""
from __future__ import annotations

import threading
import time
import unittest
from unittest import mock

from accounts_support import GOOD_PW, OTHER_PW, AccountsCase

from skald import accounts
from skald.accounts import apitokens, auditlog, counts, invites, limits, passwords
from skald.accounts import resets, users


class CountScrypt:
    """Counts the real scrypt runs (and, separately, the burns)."""

    def __init__(self, case):
        self.runs = 0
        real = passwords._scrypt

        def counted(*a, **k):
            self.runs += 1
            return real(*a, **k)
        p = mock.patch.object(passwords, "_scrypt", side_effect=counted)
        p.start()
        case.addCleanup(p.stop)
        self.burn = mock.patch.object(passwords, "burn", wraps=passwords.burn)
        self.burns = self.burn.start()
        case.addCleanup(self.burn.stop)


class Cheap(AccountsCase):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(passwords, "N", 2 ** 10)
        p.start()
        self.addCleanup(p.stop)


# ------------------------------------------------------------------ 3

class TimingEveryPathBurns(Cheap):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        self.user = accounts.create_user(self.db, "user@example.com", "User", GOOD_PW)
        self.stored = users.find_user(self.db, user_id=self.user["id"], secrets=True)["pw_hash"]

    def test_verify_burns_on_each_early_return(self):
        for pw, stored, why in (("", self.stored, "empty password"),
                                (None, self.stored, "not a string"),
                                ("x" * 2000, self.stored, "too long"),
                                (GOOD_PW, "scrypt$bad", "malformed hash"),
                                (GOOD_PW, None, "no hash"),
                                (GOOD_PW, "scrypt$32768$8$1$AAAA$AAAA", "hash too short")):
            c = CountScrypt(self)
            self.assertFalse(passwords.verify_password(pw, stored), why)
            self.assertEqual(c.burns.call_count, 1, why)
            self.assertEqual(c.runs, 1, why)
            c.burn.stop()

    def test_a_real_check_is_one_scrypt_too(self):
        c = CountScrypt(self)
        self.assertTrue(passwords.verify_password(GOOD_PW, self.stored))
        self.assertEqual((c.runs, c.burns.call_count), (1, 0))

    def test_authenticate_spends_one_scrypt_on_every_path(self):
        accounts.create_user(self.db, "nopw@example.com", "No Pw")
        off = accounts.create_user(self.db, "off@example.com", "Off", GOOD_PW)
        users.disable_user(self.db, off["id"], "cli")
        for email, pw, why in (("nobody@example.com", GOOD_PW, "unknown"),
                               ("not an address", GOOD_PW, "malformed email"),
                               ("off@example.com", GOOD_PW, "disabled"),
                               ("nopw@example.com", GOOD_PW, "no password yet"),
                               ("user@example.com", "", "empty password"),
                               ("user@example.com", OTHER_PW, "wrong password")):
            c = CountScrypt(self)
            self.assertIsNone(accounts.authenticate(self.db, email, pw), why)
            self.assertEqual(c.runs, 1, why)
            if why != "wrong password":
                self.assertGreaterEqual(c.burns.call_count, 1, why)
            c.burn.stop()


# ------------------------------------------------------------------ 4

class TriesTakenFirst(Cheap):
    KEYS = ("login:email:user@example.com", "login:ip:x")

    def test_take_counts_before_the_check_and_forgets_on_success(self):
        got = limits.take(self.db, self.KEYS, 5, 15, 30)
        self.assertIsNotNone(got)
        self.assertEqual(limits.count(self.db, self.KEYS[0]), 1)
        limits.forget(self.db, got)
        self.assertEqual(limits.count(self.db, self.KEYS[1]), 0)

    def test_after_the_limit_one_try_each_wait(self):
        for _ in range(5):
            self.assertIsNotNone(limits.take(self.db, self.KEYS, 5, 15, 30))
        self.assertIsNone(limits.take(self.db, self.KEYS, 5, 15, 30))
        self.tick(31)
        self.assertIsNotNone(limits.take(self.db, self.KEYS, 5, 15, 30))
        self.assertIsNone(limits.take(self.db, self.KEYS, 5, 15, 30))

    def test_forty_parallel_tries_after_the_limit_let_one_through(self):
        for _ in range(5):
            limits.take(self.db, self.KEYS, 5, 15, 30)
        self.tick(31)
        passed, gate = [], threading.Barrier(40)

        def one(i):
            db = accounts.connect(self.path)
            try:
                gate.wait()
                if limits.take(db, ("login:email:user@example.com", f"login:ip:{i}"),
                               5, 15, 30) is not None:
                    passed.append(i)
            finally:
                db.close()
        threads = [threading.Thread(target=one, args=(i,)) for i in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(len(passed), 1)


class ScryptSlots(unittest.TestCase):
    def test_at_most_two_at_once_and_the_rest_told_busy(self):
        live, peak, lock = [0], [0], threading.Lock()
        real = passwords.hashlib.scrypt

        def slow(*a, **k):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.3)
            with lock:
                live[0] -= 1
            return real(b"x", salt=b"y" * 16, n=2, r=1, p=1, dklen=k.get("dklen", 64))
        results = []

        def one():
            try:
                passwords.burn("guess")
                results.append("done")
            except passwords.Busy:
                results.append("busy")
        with mock.patch.object(passwords.hashlib, "scrypt", side_effect=slow), \
                mock.patch.object(passwords, "SLOT_WAIT", 0.1):
            threads = [threading.Thread(target=one) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(10)
        self.assertLessEqual(peak[0], passwords.SLOTS)
        self.assertEqual(passwords.SLOTS, 2)
        self.assertEqual(results.count("done"), 2)
        self.assertEqual(results.count("busy"), 6)


# ----------------------------------------------------------------- 6a

class HandedInvites(Cheap):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Alpha", "cli")

    def test_a_mailed_invite_makes_a_normal_account(self):
        token = invites.invite(self.db, self.org["id"], "new@example.com", "viewer", "cli")
        user = invites.accept(self.db, token, "New", GOOD_PW)
        self.assertFalse(user["must_reset"])

    def test_a_handed_invite_makes_a_must_reset_account_until_the_password_changes(self):
        token = invites.invite(self.db, self.org["id"], "new@example.com", "viewer", "cli")
        invites.mark_handed(self.db, token)
        user = invites.accept(self.db, token, "New", GOOD_PW)
        self.assertTrue(user["must_reset"])
        self.assertTrue(users.find_user(self.db, user_id=user["id"])["must_reset"])
        self.assertIn("invite.accept", self.audit_actions(self.org["id"]))
        users.set_password(self.db, user["id"], OTHER_PW, user["id"])
        self.assertFalse(users.find_user(self.db, user_id=user["id"])["must_reset"])

    def test_a_reset_link_clears_it_too(self):
        token = invites.invite(self.db, self.org["id"], "new@example.com", "viewer", "cli")
        invites.mark_handed(self.db, token)
        user = invites.accept(self.db, token, "New", GOOD_PW)
        link = resets.issue_for(self.db, user["id"], "cli")
        accounts.use_reset(self.db, link, OTHER_PW)
        self.assertFalse(users.find_user(self.db, user_id=user["id"])["must_reset"])

    def test_an_existing_account_is_not_flagged(self):
        old = accounts.create_user(self.db, "old@example.com", "Old", GOOD_PW)
        token = invites.invite(self.db, self.org["id"], "old@example.com", "viewer", "cli")
        invites.mark_handed(self.db, token)
        invites.accept(self.db, token, "", "")
        self.assertFalse(users.find_user(self.db, user_id=old["id"])["must_reset"])


class SchemaTwo(unittest.TestCase):
    def test_a_version_one_file_gains_the_new_columns(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from skald.accounts import db as base
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accounts.sqlite"
            old = sqlite3.connect(path)
            old.executescript(base.SCHEMA.replace(
                ",\n  must_reset INTEGER NOT NULL DEFAULT 0", "").replace(
                ", handed INTEGER NOT NULL DEFAULT 0", ""))
            old.execute("INSERT INTO meta VALUES ('schema_version', '1')")
            old.execute("INSERT INTO users (email, created_at) VALUES ('a@example.com', 'x')")
            old.commit()
            self.assertNotIn("must_reset", [r[1] for r in old.execute("PRAGMA table_info(users)")])
            old.close()
            db = base.connect(path)
            try:
                self.assertEqual(base.schema_version(db), base.SCHEMA_VERSION)
                self.assertEqual(db.execute("SELECT must_reset FROM users").fetchone()[0], 0)
                self.assertIn("handed", [r[1] for r in db.execute("PRAGMA table_info(invites)")])
            finally:
                db.close()


# ----------------------------------------------------------------- 6c

class TokenCreator(Cheap):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        accounts.assign_site(self.db, "alpha.example", self.org["id"], "cli")
        self.owner = accounts.create_user(self.db, "owner@example.com", "Owner", GOOD_PW)
        accounts.add_member(self.db, self.org["id"], self.owner["id"], "owner", "cli")
        self.admin = accounts.create_user(self.db, "admin@example.com", "Admin", GOOD_PW)
        accounts.add_member(self.db, self.org["id"], self.admin["id"], "admin", "cli")
        self.token = apitokens.create(self.db, self.org["id"], "script", actor=self.admin["id"])

    def ok(self, token=None):
        return apitokens.check(self.db, f"Bearer {token or self.token}", "alpha.example")[0]

    def test_created_by_is_stored(self):
        self.assertEqual(apitokens.listing(self.db, self.org["id"])[0]["created_by"],
                         str(self.admin["id"]))
        self.assertTrue(self.ok())

    def test_creator_disabled_stops_the_token(self):
        users.disable_user(self.db, self.admin["id"], "cli")
        self.assertFalse(self.ok())
        users.enable_user(self.db, self.admin["id"], "cli")
        self.assertTrue(self.ok())

    def test_creator_demoted_or_removed_stops_the_token(self):
        users.set_role(self.db, self.org["id"], self.admin["id"], "viewer", "cli")
        self.assertFalse(self.ok())
        users.set_role(self.db, self.org["id"], self.admin["id"], "admin", "cli")
        self.assertTrue(self.ok())
        users.remove_member(self.db, self.org["id"], self.admin["id"], "cli")
        self.assertFalse(self.ok())

    def test_server_made_tokens_are_not_tied_to_a_person(self):
        cli = apitokens.create(self.db, self.org["id"], "cron", actor="cli")
        self.assertTrue(self.ok(cli))

    def test_mcp_endpoint_check_follows_the_same_rule(self):
        from skald.mcp import http as mcp_http
        mcp = apitokens.create(self.db, self.org["id"], "agent", scopes=["mcp"],
                               actor=self.admin["id"])
        self.assertTrue(mcp_http._valid(self.db, f"Bearer {mcp}")[0])
        users.disable_user(self.db, self.admin["id"], "cli")
        self.assertFalse(mcp_http._valid(self.db, f"Bearer {mcp}")[0])


# ----------------------------------------------------------------- 6d

class LastOwnerStays(Cheap):
    def test_disable_refuses_the_last_active_owner_of_any_org(self):
        a = accounts.create_org(self.db, "Alpha", "cli")
        b = accounts.create_org(self.db, "Beta", "cli")
        one = accounts.create_user(self.db, "one@example.com", "One", GOOD_PW)
        two = accounts.create_user(self.db, "two@example.com", "Two", GOOD_PW)
        accounts.add_member(self.db, a["id"], one["id"], "owner", "cli")
        accounts.add_member(self.db, a["id"], two["id"], "owner", "cli")
        accounts.add_member(self.db, b["id"], one["id"], "owner", "cli")
        with self.assertRaisesRegex(ValueError, "only owner"):
            users.disable_user(self.db, one["id"], "cli")
        self.assertIsNone(users.find_user(self.db, user_id=one["id"])["disabled_at"])
        users.disable_user(self.db, two["id"], "cli")         # one still owns Alpha
        accounts.add_member(self.db, b["id"], two["id"], "admin", "cli")
        users.enable_user(self.db, two["id"], "cli")
        users.set_role(self.db, b["id"], two["id"], "owner", "cli")
        users.disable_user(self.db, one["id"], "cli")         # two owns both now


# --------------------------------------------------------- library gaps

class Gaps(Cheap):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        self.user = accounts.create_user(self.db, "user@example.com", "User", GOOD_PW,
                                         install_admin=True)
        accounts.add_member(self.db, self.org["id"], self.user["id"], "owner", "cli")

    def test_issue_for_is_not_rate_limited_and_is_audited(self):
        links = [resets.issue_for(self.db, self.user["id"], "cli") for _ in range(5)]
        self.assertEqual(len(set(links)), 5)
        self.assertEqual(self.audit_actions().count("reset.issue"), 5)
        accounts.use_reset(self.db, links[-1], OTHER_PW)
        other = accounts.create_user(self.db, "x@example.com", "X", GOOD_PW)
        users.disable_user(self.db, other["id"], "cli")
        with self.assertRaises(ValueError):
            resets.issue_for(self.db, other["id"], "cli")
        with self.assertRaises(ValueError):
            resets.issue_for(self.db, 9999, "cli")

    def test_set_install_admin_keeps_one(self):
        two = accounts.create_user(self.db, "two@example.com", "Two", GOOD_PW)
        users.set_install_admin(self.db, two["id"], True, "cli")
        self.assertTrue(users.find_user(self.db, user_id=two["id"])["install_admin"])
        users.set_install_admin(self.db, self.user["id"], False, "cli")
        with self.assertRaisesRegex(ValueError, "last install admin"):
            users.set_install_admin(self.db, two["id"], False, "cli")
        actions = [(e["action"], e["detail"]) for e in auditlog.recent(self.db, None)]
        self.assertIn(("user.install_admin", "on"), actions)
        self.assertIn(("user.install_admin", "off"), actions)

    def test_counts(self):
        accounts.sessions.start(self.db, self.user["id"], "192.0.2.1", "test")
        invites.invite(self.db, self.org["id"], "new@example.com", "viewer", "cli")
        accounts.assign_site(self.db, "alpha.example", self.org["id"], "cli")
        apitokens.create(self.db, self.org["id"], "script", actor="cli")
        got = counts.install(self.db)
        self.assertEqual({k: got[k] for k in ("people", "disabled", "install_admins",
                                               "sessions", "orgs", "must_reset")},
                         {"people": 1, "disabled": 0, "install_admins": 1, "sessions": 1,
                          "orgs": 1, "must_reset": 0})
        org = counts.org(self.db, self.org["id"])
        self.assertEqual({k: org[k] for k in ("members", "owners", "invites", "tokens",
                                               "revoked", "sites")},
                         {"members": 1, "owners": 1, "invites": 1, "tokens": 1, "revoked": 0,
                          "sites": ["alpha.example"]})


if __name__ == "__main__":
    unittest.main()
