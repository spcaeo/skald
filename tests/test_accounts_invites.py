"""Invites and password resets: once only, expiry, limits, sessions ended."""
from __future__ import annotations

import hashlib
import unittest

from accounts_support import GOOD_PW, OTHER_PW, AccountsCase

from skald.accounts import invites, orgs, resets, sessions, users


class InviteTest(AccountsCase):
    def setUp(self) -> None:
        super().setUp()
        self.org = orgs.create_org(self.db, "A", actor="cli")
        self.owner = users.create_user(self.db, "owner@example.com", "Owner")
        users.add_member(self.db, self.org["id"], self.owner["id"], "owner", actor="cli")

    def test_new_user(self) -> None:
        token = invites.invite(self.db, self.org["id"], " New@Example.com", "admin",
                               actor=self.owner["id"])
        self.assertNotIn(token, "\n".join(self.db.iterdump()))
        self.assertEqual(self.db.execute("SELECT token_hash FROM invites").fetchone()[0],
                         hashlib.sha256(token.encode()).hexdigest())
        info = invites.invite_info(self.db, token)
        self.assertEqual(info, {"org_id": self.org["id"], "org": "A", "email": "new@example.com",
                                "role": "admin", "has_account": False})
        self.assertEqual([p["email"] for p in invites.pending(self.db, self.org["id"])],
                         ["new@example.com"])
        with self.assertRaises(ValueError):
            invites.accept(self.db, token, "New", "short")
        got = invites.accept(self.db, token, "New Person", GOOD_PW)
        self.assertTrue(got["new"])
        self.assertEqual(got["email"], "new@example.com")
        self.assertEqual(got["org_id"], self.org["id"])
        self.assertEqual(users.role_in(self.db, got["id"], self.org["id"]), "admin")
        self.assertIsNotNone(users.authenticate(self.db, "new@example.com", GOOD_PW))
        self.assertEqual(invites.pending(self.db, self.org["id"]), [])
        self.assertEqual(self.audit_actions(self.org["id"])[:3],
                         ["invite.accept", "member.add", "invite.send"])

    def test_existing_user_keeps_password(self) -> None:
        other = orgs.create_org(self.db, "B", actor="cli")
        bob = users.create_user(self.db, "bob@example.com", "Bob", GOOD_PW)
        users.add_member(self.db, other["id"], bob["id"], "owner", actor="cli")
        token = invites.invite(self.db, self.org["id"], "bob@example.com", "viewer",
                               actor=self.owner["id"])
        self.assertTrue(invites.invite_info(self.db, token)["has_account"])
        got = invites.accept(self.db, token, "Ignored", "")
        self.assertFalse(got["new"])
        self.assertEqual(got["id"], bob["id"])
        self.assertEqual(got["name"], "Bob")
        self.assertEqual(users.role_in(self.db, bob["id"], self.org["id"]), "viewer")
        self.assertEqual(users.role_in(self.db, bob["id"], other["id"]), "owner")
        self.assertIsNotNone(users.authenticate(self.db, "bob@example.com", GOOD_PW))

    def test_reused(self) -> None:
        token = invites.invite(self.db, self.org["id"], "new@example.com", "viewer", actor="cli")
        invites.accept(self.db, token, "New", GOOD_PW)
        with self.assertRaisesRegex(ValueError, "already used"):
            invites.accept(self.db, token, "New", GOOD_PW)
        self.assertIsNone(invites.invite_info(self.db, token))

    def test_expired(self) -> None:
        token = invites.invite(self.db, self.org["id"], "new@example.com", "viewer", actor="cli")
        self.tick(days=invites.INVITE_DAYS, seconds=1)
        with self.assertRaisesRegex(ValueError, "expired"):
            invites.accept(self.db, token, "New", GOOD_PW)
        self.assertTrue(invites.pending(self.db, self.org["id"])[0]["expired"])

    def test_unknown(self) -> None:
        for token in ("", None, "nonsense"):
            with self.assertRaisesRegex(ValueError, "not valid"):
                invites.accept(self.db, token, "X", GOOD_PW)

    def test_cancel_and_resend(self) -> None:
        first = invites.invite(self.db, self.org["id"], "new@example.com", "viewer", actor="cli")
        second = invites.invite(self.db, self.org["id"], "new@example.com", "admin", actor="cli")
        with self.assertRaises(ValueError):
            invites.accept(self.db, first, "New", GOOD_PW)
        self.assertEqual(len(invites.pending(self.db, self.org["id"])), 1)
        self.assertEqual(invites.cancel(self.db, self.org["id"], "NEW@example.com", actor="cli"), 1)
        with self.assertRaises(ValueError):
            invites.accept(self.db, second, "New", GOOD_PW)
        self.assertIn("invite.cancel", self.audit_actions(self.org["id"]))

    def test_refusals(self) -> None:
        with self.assertRaises(ValueError):
            invites.invite(self.db, self.org["id"], "not-an-email", "viewer", actor="cli")
        with self.assertRaises(ValueError):
            invites.invite(self.db, self.org["id"], "x@example.com", "boss", actor="cli")
        with self.assertRaisesRegex(ValueError, "already a member"):
            invites.invite(self.db, self.org["id"], "owner@example.com", "viewer", actor="cli")
        with self.assertRaises(ValueError):
            invites.invite(self.db, 999, "x@example.com", "viewer", actor="cli")

    def test_disabled_existing_user(self) -> None:
        bob = users.create_user(self.db, "bob@example.com", "Bob", GOOD_PW)
        token = invites.invite(self.db, self.org["id"], "bob@example.com", "viewer", actor="cli")
        users.disable_user(self.db, bob["id"], actor="cli")
        with self.assertRaises(ValueError):
            invites.accept(self.db, token, "", "")
        self.assertIsNone(users.role_in(self.db, bob["id"], self.org["id"]))


class ResetTest(AccountsCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = users.create_user(self.db, "ann@example.com", "Ann", GOOD_PW)

    def test_use_once_and_end_sessions(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        token = resets.request_reset(self.db, " ANN@example.com")
        self.assertIsNotNone(token)
        self.assertNotIn(token, "\n".join(self.db.iterdump()))
        with self.assertRaises(ValueError):
            resets.use_reset(self.db, token, "ann@example.com")
        got = resets.use_reset(self.db, token, OTHER_PW)
        self.assertEqual(got["id"], self.user["id"])
        self.assertIsNone(sessions.resolve(self.db, cookie))
        self.assertIsNotNone(users.authenticate(self.db, "ann@example.com", OTHER_PW))
        with self.assertRaisesRegex(ValueError, "already used"):
            resets.use_reset(self.db, token, GOOD_PW)
        self.assertEqual(self.audit_actions()[:2], ["reset.use", "session.end_all"])

    def test_new_link_voids_older(self) -> None:
        first = resets.request_reset(self.db, "ann@example.com")
        second = resets.request_reset(self.db, "ann@example.com")
        resets.use_reset(self.db, second, OTHER_PW)
        with self.assertRaises(ValueError):
            resets.use_reset(self.db, first, GOOD_PW)

    def test_expiry(self) -> None:
        token = resets.request_reset(self.db, "ann@example.com")
        self.tick(minutes=resets.RESET_MINUTES, seconds=1)
        with self.assertRaisesRegex(ValueError, "expired"):
            resets.use_reset(self.db, token, OTHER_PW)

    def test_unknown_and_disabled(self) -> None:
        self.assertIsNone(resets.request_reset(self.db, "nobody@example.com"))
        self.assertIsNone(resets.request_reset(self.db, "not an email"))
        self.assertIsNone(resets.request_reset(self.db, ""))
        users.disable_user(self.db, self.user["id"], actor="cli")
        self.assertIsNone(resets.request_reset(self.db, "ann@example.com"))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM resets").fetchone()[0], 0)

    def test_disabled_after_request(self) -> None:
        token = resets.request_reset(self.db, "ann@example.com")
        users.disable_user(self.db, self.user["id"], actor="cli")
        with self.assertRaises(ValueError):
            resets.use_reset(self.db, token, OTHER_PW)

    def test_three_per_hour(self) -> None:
        for _ in range(3):
            self.assertIsNotNone(resets.request_reset(self.db, "ann@example.com"))
        self.assertIsNone(resets.request_reset(self.db, "ann@example.com"))
        self.tick(minutes=61)
        self.assertIsNotNone(resets.request_reset(self.db, "ann@example.com"))

    def test_bad_tokens(self) -> None:
        for token in ("", None, "nonsense"):
            with self.assertRaisesRegex(ValueError, "not valid"):
                resets.use_reset(self.db, token, OTHER_PW)

    def test_user_without_password_can_set_one(self) -> None:
        new = users.create_user(self.db, "bob@example.com", "Bob")
        token = resets.request_reset(self.db, "bob@example.com")
        resets.use_reset(self.db, token, OTHER_PW)
        self.assertEqual(users.authenticate(self.db, "bob@example.com", OTHER_PW)["id"], new["id"])


if __name__ == "__main__":
    unittest.main()
