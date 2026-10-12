"""Two-step sign-in: RFC 6238 codes, the window, replay, recovery codes."""
from __future__ import annotations

import base64
import unittest
from urllib.parse import parse_qs, urlparse

from accounts_support import GOOD_PW, AccountsCase

from skald.accounts import totp, users

# RFC 6238 appendix B, SHA1, seed "12345678901234567890".
SEED = base64.b32encode(b"12345678901234567890").decode()
VECTORS = [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"),
           (1234567890, "89005924"), (2000000000, "69279037"), (20000000000, "65353130")]


class CodeTest(unittest.TestCase):
    def test_rfc_vectors_8_digits(self) -> None:
        for t, want in VECTORS:
            self.assertEqual(totp.code_at(SEED, t, digits=8), want, t)

    def test_rfc_vectors_6_digits(self) -> None:
        for t, want in VECTORS:
            self.assertEqual(totp.code_at(SEED, t), want[-6:], t)

    def test_window(self) -> None:
        t = 1234567890
        self.assertTrue(totp.verify(SEED, totp.code_at(SEED, t), t))
        self.assertTrue(totp.verify(SEED, totp.code_at(SEED, t - 30), t))
        self.assertTrue(totp.verify(SEED, totp.code_at(SEED, t + 30), t))
        self.assertFalse(totp.verify(SEED, totp.code_at(SEED, t - 60), t))
        self.assertFalse(totp.verify(SEED, totp.code_at(SEED, t + 60), t))
        self.assertFalse(totp.verify(SEED, totp.code_at(SEED, t - 30), t, window=0))

    def test_bad_input(self) -> None:
        for code in ("", None, "12345", "1234567", "abcdef"):
            self.assertFalse(totp.verify(SEED, code, 59), code)
        self.assertFalse(totp.verify("not base32 !!", "123456", 59))
        self.assertTrue(totp.verify(SEED, " 287 082 ", 59))

    def test_secret_shapes(self) -> None:
        secret = totp.new_secret()
        self.assertRegex(secret, r"^[A-Z2-7]{32}$")
        self.assertEqual(totp.code_at(secret.lower(), 59), totp.code_at(secret, 59))

    def test_uri(self) -> None:
        uri = totp.provisioning_uri(SEED, "ann@example.com")
        got = urlparse(uri)
        self.assertEqual(got.scheme, "otpauth")
        self.assertEqual(got.netloc, "totp")
        self.assertIn("ann%40example.com", got.path)
        q = parse_qs(got.query)
        self.assertEqual(q["secret"], [SEED])
        self.assertEqual(q["issuer"], ["Skald"])

    def test_recovery_codes(self) -> None:
        shown, hashes = totp.recovery_codes()
        self.assertEqual(len(shown), 10)
        self.assertEqual(len(set(shown)), 10)
        self.assertEqual(hashes, [totp.code_hash(c) for c in shown])
        self.assertNotIn(shown[0], hashes)


class UserTotpTest(AccountsCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = users.create_user(self.db, "ann@example.com", "Ann", GOOD_PW)
        self.at("2026-10-11T14:00:00Z")
        self.t = 1791727200  # 2026-10-11T14:00:00Z

    def test_begin_confirm_check(self) -> None:
        secret, uri = totp.begin(self.db, self.user["id"])
        self.assertIn(secret, uri)
        self.assertFalse(users.find_user(self.db, user_id=self.user["id"])["totp_on"])
        with self.assertRaises(ValueError):
            totp.confirm(self.db, self.user["id"], "000000", actor=self.user["id"], t=self.t)
        codes = totp.confirm(self.db, self.user["id"], totp.code_at(secret, self.t),
                             actor=self.user["id"], t=self.t)
        self.assertEqual(len(codes), 10)
        self.assertTrue(users.find_user(self.db, user_id=self.user["id"])["totp_on"])
        self.assertIn("totp.on", self.audit_actions())
        # The code used to confirm cannot be used again to sign in.
        self.assertFalse(totp.check_user(self.db, self.user["id"],
                                         totp.code_at(secret, self.t), t=self.t))
        nxt = self.t + 30
        self.assertTrue(totp.check_user(self.db, self.user["id"], totp.code_at(secret, nxt), t=nxt))
        self.assertFalse(totp.check_user(self.db, self.user["id"], totp.code_at(secret, nxt), t=nxt))
        # An older step, though inside the window, is refused once a newer one was used.
        self.assertFalse(totp.check_user(self.db, self.user["id"],
                                         totp.code_at(secret, self.t), t=nxt))

    def test_recovery_code_once(self) -> None:
        secret, _ = totp.begin(self.db, self.user["id"])
        codes = totp.confirm(self.db, self.user["id"], totp.code_at(secret, self.t),
                             actor=self.user["id"], t=self.t)
        self.assertTrue(totp.check_user(self.db, self.user["id"], codes[0].upper(), t=self.t))
        self.assertFalse(totp.check_user(self.db, self.user["id"], codes[0], t=self.t))
        self.assertIn("totp.recovery_used", self.audit_actions())

    def test_no_totp_means_no_code_passes(self) -> None:
        self.assertFalse(totp.check_user(self.db, self.user["id"], "123456", t=self.t))

    def test_disable(self) -> None:
        secret, _ = totp.begin(self.db, self.user["id"])
        totp.confirm(self.db, self.user["id"], totp.code_at(secret, self.t),
                     actor=self.user["id"], t=self.t)
        totp.disable(self.db, self.user["id"], actor="cli")
        found = users.find_user(self.db, user_id=self.user["id"], secrets=True)
        self.assertFalse(found["totp_on"])
        self.assertIsNone(found["totp_secret"])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM recovery").fetchone()[0], 0)
        self.assertIn("totp.off", self.audit_actions())

    def test_confirm_without_begin(self) -> None:
        with self.assertRaises(ValueError):
            totp.confirm(self.db, self.user["id"], "123456", actor="cli", t=self.t)


if __name__ == "__main__":
    unittest.main()
