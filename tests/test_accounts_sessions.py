"""Sessions: start, resolve, slide, expire, end, and the rate limiter."""
from __future__ import annotations

import hashlib
import unittest

from accounts_support import AccountsCase

from skald.accounts import limits, sessions, users


class SessionTest(AccountsCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = users.create_user(self.db, "ann@example.com", "Ann", install_admin=True)

    def test_start_and_resolve(self) -> None:
        cookie, csrf = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        self.assertGreaterEqual(len(cookie), 40)
        self.assertNotEqual(cookie, csrf)
        got = sessions.resolve(self.db, cookie)
        self.assertEqual(got["user_id"], self.user["id"])
        self.assertEqual(got["email"], "ann@example.com")
        self.assertEqual(got["name"], "Ann")
        self.assertTrue(got["install_admin"])
        self.assertEqual(got["csrf"], csrf)
        self.assertIn("session_id", got)
        self.assertIn("session.start", self.audit_actions())

    def test_only_hashes_stored(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        row = self.db.execute("SELECT id_hash, ip_hash FROM sessions").fetchone()
        self.assertEqual(row[0], hashlib.sha256(cookie.encode()).hexdigest())
        dump = "\n".join(self.db.iterdump())
        self.assertNotIn(cookie, dump)
        self.assertNotIn("203.0.113.10", dump)

    def test_unknown(self) -> None:
        for cookie in (None, "", "nonsense", "x" * 5000):
            self.assertIsNone(sessions.resolve(self.db, cookie))

    def test_expiry(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        self.tick(days=13, hours=23)
        self.assertIsNotNone(sessions.resolve(self.db, cookie))
        self.tick(days=14, hours=1)
        self.assertIsNone(sessions.resolve(self.db, cookie))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)

    def test_a_short_session_lasts_12_hours_from_its_last_use(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox",
                                   remember=False)
        for _ in range(3):           # used every 10 hours: it slides by 12 hours each time
            self.tick(hours=10)
            self.assertIsNotNone(sessions.resolve(self.db, cookie))
        self.tick(hours=12, minutes=1)
        self.assertIsNone(sessions.resolve(self.db, cookie))

    def test_expires_without_use(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        self.tick(days=14)
        self.assertIsNone(sessions.resolve(self.db, cookie))

    def test_slides(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        for _ in range(4):
            self.tick(days=10)
            self.assertIsNotNone(sessions.resolve(self.db, cookie))
        row = self.db.execute("SELECT last_seen, expires_at FROM sessions").fetchone()
        self.assertEqual(row[0], "2026-11-20T14:00:00Z")
        self.assertEqual(row[1], "2026-12-04T14:00:00Z")

    def test_no_write_inside_the_hour(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        self.tick(minutes=30)
        sessions.resolve(self.db, cookie)
        row = self.db.execute("SELECT last_seen FROM sessions").fetchone()
        self.assertEqual(row[0], "2026-10-11T14:00:00Z")
        self.tick(minutes=31)
        sessions.resolve(self.db, cookie)
        row = self.db.execute("SELECT last_seen FROM sessions").fetchone()
        self.assertEqual(row[0], "2026-10-11T15:01:00Z")
        self.assertEqual(users.find_user(self.db, user_id=self.user["id"])["last_seen"],
                         "2026-10-11T15:01:00Z")

    def test_disabled_user(self) -> None:
        cookie, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        self.db.execute("UPDATE users SET disabled_at = 'x'")
        self.assertIsNone(sessions.resolve(self.db, cookie))
        with self.assertRaises(ValueError):
            sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")

    def test_end_and_end_all(self) -> None:
        one, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        two, _ = sessions.start(self.db, self.user["id"], "203.0.113.11", "Safari")
        three, _ = sessions.start(self.db, self.user["id"], "203.0.113.12", "Chrome")
        listed = sessions.list_for(self.db, self.user["id"])
        self.assertEqual(len(listed), 3)
        self.assertNotIn("ip_hash", listed[0])
        sessions.end(self.db, one)
        self.assertIsNone(sessions.resolve(self.db, one))
        keep = sessions.resolve(self.db, two)["session_id"]
        self.assertEqual(sessions.end_all(self.db, self.user["id"], except_session=keep), 1)
        self.assertIsNotNone(sessions.resolve(self.db, two))
        self.assertIsNone(sessions.resolve(self.db, three))
        self.assertEqual(sessions.end_all(self.db, self.user["id"]), 1)
        self.assertIsNone(sessions.resolve(self.db, two))
        sessions.end(self.db, None)

    def test_end_one_by_id(self) -> None:
        one, _ = sessions.start(self.db, self.user["id"], "203.0.113.10", "Firefox")
        other = users.create_user(self.db, "bob@example.com", "Bob")
        sid = sessions.resolve(self.db, one)["session_id"]
        self.assertFalse(sessions.end_id(self.db, other["id"], sid))
        self.assertIsNotNone(sessions.resolve(self.db, one))
        self.assertTrue(sessions.end_id(self.db, self.user["id"], sid))
        self.assertIsNone(sessions.resolve(self.db, one))

    def test_long_agent_cut(self) -> None:
        sessions.start(self.db, self.user["id"], "203.0.113.10", "A" * 5000)
        self.assertLessEqual(len(sessions.list_for(self.db, self.user["id"])[0]["agent"]), 200)


class LimitTest(AccountsCase):
    def test_five_in_fifteen_minutes(self) -> None:
        key = "login:ip:203.0.113.10"
        for _ in range(4):
            limits.note_failure(self.db, key)
        self.assertFalse(limits.too_many(self.db, key))
        limits.note_failure(self.db, key)
        self.assertTrue(limits.too_many(self.db, key))
        self.assertFalse(limits.too_many(self.db, "login:ip:203.0.113.11"))
        self.tick(minutes=16)
        self.assertFalse(limits.too_many(self.db, key))

    def test_clear(self) -> None:
        for _ in range(5):
            limits.note_failure(self.db, "k")
        limits.clear(self.db, "k")
        self.assertFalse(limits.too_many(self.db, "k"))

    def test_keys_are_hashed_and_old_rows_pruned(self) -> None:
        limits.note_failure(self.db, "login:ip:203.0.113.10")
        self.assertNotIn("203.0.113.10", "\n".join(self.db.iterdump()))
        self.tick(days=2)
        limits.note_failure(self.db, "other")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM attempts").fetchone()[0], 1)

    def test_custom_limit(self) -> None:
        for _ in range(3):
            limits.note_failure(self.db, "reset")
        self.assertTrue(limits.too_many(self.db, "reset", limit=3, minutes=60))
        self.assertFalse(limits.too_many(self.db, "reset", limit=4, minutes=60))


if __name__ == "__main__":
    unittest.main()
