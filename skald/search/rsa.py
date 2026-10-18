"""RS256 (RSASSA-PKCS1-v1_5 with SHA-256) in pure Python, for one job: signing
the JWT a Google service account trades for an access token.

The standard library has no RSA. Signing needs only the private key's
numbers and one modular power, so this file holds:

  a DER reader     just enough ASN.1 for a private key: SEQUENCE, INTEGER,
                   OCTET STRING, OBJECT IDENTIFIER, NULL; definite lengths only
  the key          a PKCS#8 "PRIVATE KEY" block (what Google's JSON key file
                   holds) or a PKCS#1 "RSA PRIVATE KEY" block: n, e, d, p, q,
                   dp, dq, qinv
  sign             EMSA-PKCS1-v1_5 (RFC 8017 9.2): 0x00 0x01 FF..FF 0x00,
                   then SHA-256's DigestInfo and the hash; then m^d mod n,
                   worked out by the Chinese remainder theorem (the same
                   number, about four times faster) and checked by raising it
                   back to e before it is returned
  verify           s^e mod n against the same encoding (used by the tests and
                   by `sign` itself)

PKCS#1 v1.5 signatures are deterministic: the same key and message always
give the same bytes, so the tests compare against `openssl dgst -sha256
-sign` byte for byte. Nothing here is a general crypto library: no
encryption, no key generation, no padding but this one. The key is never
logged; errors say what is wrong with the file, never what is in it.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import re

# DigestInfo for SHA-256 (RFC 8017 9.2, note 1).
SHA256_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
RSA_OID = "1.2.840.113549.1.1.1"
# The PEM armour, matched without spelling a whole key header in the source.
_ARMOUR = re.compile(r"-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----", re.S)
_KINDS = ("PRIVATE KEY", "RSA PRIVATE KEY")


class BadKey(ValueError):
    """The key file is not an RSA private key this module can read."""


# ------------------------------------------------------------ DER reader

def _read(data: bytes, at: int) -> tuple[int, bytes, int]:
    """(tag, contents, next offset) of the element at `at`."""
    if at + 2 > len(data):
        raise BadKey("the key is cut short")
    tag = data[at]
    length = data[at + 1]
    at += 2
    if length & 0x80:
        count = length & 0x7F
        if count == 0 or count > 4 or at + count > len(data):
            raise BadKey("the key has a length this reader does not take")
        length = int.from_bytes(data[at:at + count], "big")
        at += count
    end = at + length
    if end > len(data):
        raise BadKey("the key is cut short")
    return tag, data[at:end], end


def _items(data: bytes) -> list[tuple[int, bytes]]:
    """The elements inside one constructed element's contents."""
    out, at = [], 0
    while at < len(data):
        tag, body, at = _read(data, at)
        out.append((tag, body))
    return out


def _sequence(data: bytes) -> list[tuple[int, bytes]]:
    tag, body, end = _read(data, 0)
    if tag != 0x30:
        raise BadKey("the key does not start with a SEQUENCE")
    return _items(body)


def _int(item: tuple[int, bytes]) -> int:
    tag, body = item
    if tag != 0x02 or not body:
        raise BadKey("the key holds something else where a number belongs")
    return int.from_bytes(body, "big", signed=True)


def _oid(body: bytes) -> str:
    if not body:
        return ""
    parts = [body[0] // 40, body[0] % 40]
    value = 0
    for byte in body[1:]:
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            parts.append(value)
            value = 0
    return ".".join(str(p) for p in parts)


# ----------------------------------------------------------------- the key

class PrivateKey:
    """An RSA private key's numbers. repr never shows them."""

    __slots__ = ("n", "e", "d", "p", "q", "dp", "dq", "qinv")

    def __init__(self, n, e, d, p, q, dp, dq, qinv) -> None:
        self.n, self.e, self.d, self.p, self.q = n, e, d, p, q
        self.dp, self.dq, self.qinv = dp, dq, qinv

    def __repr__(self) -> str:
        return f"<RSA private key, {self.bits} bits>"

    @property
    def bits(self) -> int:
        return self.n.bit_length()

    @property
    def size(self) -> int:
        """The modulus in bytes: every signature is this long."""
        return (self.n.bit_length() + 7) // 8


def _pkcs1(der: bytes) -> PrivateKey:
    items = _sequence(der)
    if len(items) < 9:
        raise BadKey("the RSA key has too few parts")
    version, n, e, d, p, q, dp, dq, qinv = (_int(i) for i in items[:9])
    if version != 0:
        raise BadKey("only two-prime RSA keys are read")
    if n <= 0 or p * q != n:
        raise BadKey("the RSA key's numbers do not agree")
    return PrivateKey(n, e, d, p, q, dp, dq, qinv)


def _pkcs8(der: bytes) -> PrivateKey:
    items = _sequence(der)
    if len(items) < 3 or items[1][0] != 0x30 or items[2][0] != 0x04:
        raise BadKey("not a PKCS#8 private key")
    algorithm = _items(items[1][1])
    if not algorithm or algorithm[0][0] != 0x06 or _oid(algorithm[0][1]) != RSA_OID:
        raise BadKey("the private key is not an RSA key")
    return _pkcs1(items[2][1])


def load_pem(text: str) -> PrivateKey:
    """The RSA key in a PEM block (PKCS#8, or PKCS#1). Raises BadKey."""
    if not isinstance(text, str):
        raise BadKey("the private key is not text")
    found = _ARMOUR.search(text.replace("\\n", "\n"))
    if not found or found.group(1) not in _KINDS:
        raise BadKey("no private key block found")
    body = "".join(line.strip() for line in found.group(2).splitlines()
                   if line.strip() and ":" not in line)
    try:
        der = base64.b64decode(body, validate=True)
    except (binascii.Error, ValueError):
        raise BadKey("the private key block is not valid base64") from None
    return _pkcs8(der) if found.group(1) == "PRIVATE KEY" else _pkcs1(der)


# ------------------------------------------------------------ the signature

def encode(message: bytes, size: int) -> bytes:
    """EMSA-PKCS1-v1_5 of SHA-256(message), `size` bytes long."""
    t = SHA256_PREFIX + hashlib.sha256(message).digest()
    if size < len(t) + 11:
        raise BadKey("the key is too short for SHA-256 signatures")
    return b"\x00\x01" + b"\xff" * (size - len(t) - 3) + b"\x00" + t


def sign(key: PrivateKey, message: bytes) -> bytes:
    """The RS256 signature of `message`."""
    m = int.from_bytes(encode(message, key.size), "big")
    m1 = pow(m, key.dp, key.p)
    m2 = pow(m, key.dq, key.q)
    h = (key.qinv * (m1 - m2)) % key.p
    s = m2 + h * key.q
    if pow(s, key.e, key.n) != m:            # a wrong CRT part would leak the key
        s = pow(m, key.d, key.n)
        if pow(s, key.e, key.n) != m:
            raise BadKey("the private key's numbers do not make a valid signature")
    return s.to_bytes(key.size, "big")


def verify(n: int, e: int, message: bytes, signature: bytes) -> bool:
    """Does `signature` sign `message` for the public key (n, e)?"""
    size = (n.bit_length() + 7) // 8
    if len(signature) != size:
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    return pow(s, e, n).to_bytes(size, "big") == encode(message, size)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
