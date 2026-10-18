"""RS256 in pure Python (search/rsa.py) and the service-account key check
(search/google.py): byte-for-byte against openssl's signature, a fixed test
vector, a key made by openssl on the spot when openssl is installed, and
plain words for every broken key. Keys here are TEST ONLY."""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import search_support as ss  # noqa: E402

from skald.search import google, rsa  # noqa: E402


class Vector(unittest.TestCase):
    def test_signature_matches_openssl_byte_for_byte(self):
        key = rsa.load_pem(ss.pem())
        got = rsa.sign(key, ss.VECTOR["message"].encode())
        self.assertEqual(got.hex(), ss.VECTOR["signature_hex"])
        self.assertTrue(rsa.verify(key.n, key.e, ss.VECTOR["message"].encode(), got))
        self.assertFalse(rsa.verify(key.n, key.e, b"another message", got))
        self.assertEqual(len(got), key.size)

    def test_key_never_shown(self):
        key = rsa.load_pem(ss.pem())
        self.assertEqual(repr(key), "<RSA private key, 1024 bits>")
        self.assertNotIn(str(key.d), repr(key))

    def test_escaped_newlines_as_in_a_json_key_file(self):
        flat = ss.pem().replace("\n", "\\n")
        self.assertEqual(rsa.load_pem(flat).n, rsa.load_pem(ss.pem()).n)

    def test_broken_keys_in_plain_words(self):
        kind = "PRIVATE " + "KEY"
        for text, words in (
                ("", "no private key block"),
                ("hello", "no private key block"),
                (f"-----BEGIN {kind}-----\n!!!!\n-----END {kind}-----", "base64"),
                (f"-----BEGIN {kind}-----\n" + base64.b64encode(b"\x30\x03\x02\x01").decode()
                 + f"\n-----END {kind}-----", "cut short")):
            with self.assertRaises(rsa.BadKey) as caught:
                rsa.load_pem(text)
            self.assertIn(words, str(caught.exception))

    def test_der_lengths(self):
        self.assertEqual(rsa._read(b"\x02\x01\x05", 0), (2, b"\x05", 3))
        long = b"\x04\x81\x80" + b"x" * 128
        self.assertEqual(rsa._read(long, 0)[1], b"x" * 128)
        with self.assertRaises(rsa.BadKey):
            rsa._read(b"\x04\x85\x00\x00\x00\x00\x01", 0)


@unittest.skipUnless(shutil.which("openssl"), "openssl not installed")
class Openssl(unittest.TestCase):
    """A 2048-bit key made now, as Google makes them, in PKCS#8 and PKCS#1."""

    def test_fresh_key_both_encodings(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            one = folder / "k1.pem"
            eight = folder / "k8.pem"
            message = folder / "m.txt"
            message.write_bytes(b'{"alg":"RS256"}.{"iss":"robot@example.com"}')
            run = lambda *a: subprocess.run(a, check=True, capture_output=True)  # noqa: E731
            try:
                run("openssl", "genrsa", "-out", str(one), "2048")
                run("openssl", "pkcs8", "-topk8", "-nocrypt", "-in", str(one), "-out", str(eight))
                run("openssl", "dgst", "-sha256", "-sign", str(eight), "-out",
                    str(folder / "sig"), str(message))
            except (subprocess.CalledProcessError, OSError) as why:
                self.skipTest(f"openssl failed: {why}")
            want = (folder / "sig").read_bytes()
            for path in (eight, one):
                key = rsa.load_pem(path.read_text())
                self.assertEqual(key.bits, 2048)
                self.assertEqual(rsa.sign(key, message.read_bytes()), want, path.name)


class ServiceKey(unittest.TestCase):
    def test_a_good_key(self):
        info = google.check_key(ss.service_key())
        self.assertEqual(info["client_email"], ss.EMAIL)
        self.assertEqual(info["project_id"], "example-project")
        self.assertNotIn("private", json.dumps(info))

    def test_refusals(self):
        for text, words in (
                ("", "empty"), ("{", "not JSON"),
                (json.dumps({"type": "authorized_user"}), "not a service-account key"),
                (ss.service_key(email=""), "client_email"),
                (ss.service_key(token_uri="https://evil.example/token"), "not Google's"),
                (ss.service_key(private_key="nope"), "cannot be read"),
                ("x" * 30000, "too big")):
            with self.assertRaises(google.BadKey) as caught:
                google.check_key(text)
            self.assertIn(words, str(caught.exception))
            self.assertNotIn(ss.VECTOR["pkcs8_der_base64"][:40], str(caught.exception))

    def test_assertion_is_a_signed_jwt(self):
        client = google.Client(ss.service_key(), clock=lambda: 1_700_000_000)
        head, claims, sig = client.assertion().split(".")
        pad = lambda t: t + "=" * (-len(t) % 4)      # noqa: E731
        self.assertEqual(json.loads(base64.urlsafe_b64decode(pad(head)))["alg"], "RS256")
        body = json.loads(base64.urlsafe_b64decode(pad(claims)))
        self.assertEqual(body, {"iss": ss.EMAIL, "scope": google.SCOPE, "aud": google.TOKEN_URL,
                                "iat": 1_700_000_000, "exp": 1_700_003_600})
        n, e = ss.public()
        self.assertTrue(rsa.verify(n, e, f"{head}.{claims}".encode(),
                                   base64.urlsafe_b64decode(pad(sig))))
        self.assertEqual(repr(client), f"<Search Console client {ss.EMAIL}>")


if __name__ == "__main__":
    unittest.main()
