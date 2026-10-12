"""Passwords: scrypt hashes, constant-time checks, and the policy."""
from __future__ import annotations

import base64
import unittest

import accounts_support  # noqa: F401  (puts the repo on the path)

from skald.accounts import passwords as pw


class HashTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stored = pw.hash_password("correct horse battery staple")

    def test_format(self) -> None:
        parts = self.stored.split("$")
        self.assertEqual(parts[:4], ["scrypt", "32768", "8", "1"])
        self.assertEqual(len(base64.b64decode(parts[4])), 16)
        self.assertEqual(len(base64.b64decode(parts[5])), 64)

    def test_verify(self) -> None:
        self.assertTrue(pw.verify_password("correct horse battery staple", self.stored))
        self.assertFalse(pw.verify_password("correct horse battery stapl", self.stored))
        self.assertFalse(pw.verify_password("", self.stored))

    def test_salted(self) -> None:
        self.assertNotEqual(pw.hash_password("correct horse battery staple"), self.stored)

    def test_malformed(self) -> None:
        for bad in ("", None, "scrypt", "bcrypt$1$2$3$4$5", "scrypt$x$8$1$AA==$AA==",
                    "scrypt$32768$8$1$!!!$AA==", "scrypt$3$8$1$AAAA$AAAA",
                    "scrypt$1073741824$8$1$AAAA$AAAA", "$2y$05$abcdefghijklmnopqrstuv",
                    self.stored + "$extra"):
            self.assertFalse(pw.verify_password("correct horse battery staple", bad), bad)

    def test_unicode(self) -> None:
        stored = pw.hash_password("Пароль-очень-длинный")
        self.assertTrue(pw.verify_password("Пароль-очень-длинный", stored))

    def test_burn_runs(self) -> None:
        self.assertFalse(pw.burn("anything at all"))


class PolicyTest(unittest.TestCase):
    def test_fine(self) -> None:
        self.assertIsNone(pw.password_problem("correct horse battery staple", "ann@example.com"))

    def test_short(self) -> None:
        self.assertIn("12", pw.password_problem("short1!", ""))
        self.assertEqual(pw.MIN_LENGTH, 12)

    def test_email(self) -> None:
        self.assertIsNotNone(pw.password_problem("annabelle.smith", "annabelle.smith@example.com"))
        self.assertIsNotNone(pw.password_problem("xxAnnabelle.Smith99", "annabelle.smith@example.com"))
        self.assertIsNotNone(pw.password_problem("annabelle.smith@example.com",
                                                 "Annabelle.Smith@example.com"))

    def test_common(self) -> None:
        for common in ("password1234", "Password1234", "123456789012", "qwertyuiop123"):
            self.assertIsNotNone(pw.password_problem(common), common)
        self.assertGreaterEqual(len(pw.COMMON), 90)

    def test_one_character(self) -> None:
        self.assertIsNotNone(pw.password_problem("aaaaaaaaaaaaaaaa"))

    def test_too_long(self) -> None:
        self.assertIsNotNone(pw.password_problem("x" * 2000))

    def test_not_text(self) -> None:
        self.assertIsNotNone(pw.password_problem(None))


if __name__ == "__main__":
    unittest.main()
