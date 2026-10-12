"""Password hashes (scrypt) and the password rules.

Stored as "scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>": n=2^15, r=8, p=1, a
16-byte salt, a 64-byte hash. Checked in constant time. A stored value
that is not of that shape never matches, and its cost numbers are bounded
so a bad row cannot make the helper burn memory.

Every check costs one scrypt, whatever happens: an empty password, a
malformed stored value or (in users.authenticate) an unknown or disabled
account each run `burn`, so the answer's timing tells nothing.

At most SLOTS scrypt runs at once in the process (each takes 32 MiB and
tens of milliseconds): a caller waits up to SLOT_WAIT seconds for a slot,
then gets `Busy`, which the helper answers with 503 and Retry-After.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
import threading

MIN_LENGTH = 12
MAX_LENGTH = 1024
N, R, P = 2 ** 15, 8, 1
SALT_BYTES, HASH_BYTES = 16, 64
MAXMEM = 64 * 1024 * 1024
SLOTS = 2               # scrypt runs at once, in the whole process
SLOT_WAIT = 3.0         # seconds a caller waits for a slot before Busy
_slots = threading.BoundedSemaphore(SLOTS)


class Busy(RuntimeError):
    """Every scrypt slot stayed taken for SLOT_WAIT seconds: try again soon."""

# Common passwords long enough to pass the length rule, plus short classics
# (so a user who pads one gets a clear answer). Compared lowercased.
COMMON = frozenset("""
123456789012 1234567890123 12345678901234 123456789123 111111111111 000000000000
123123123123 121212121212 112233445566 987654321098 098765432109 147258369147
password1234 password12345 password123456 password2024 password2025 password2026
password1234! password123! passwordpassword password1password p@ssw0rd1234
p@ssword1234 passw0rd1234 mypassword123 thisismypassword changeme1234 changeme123!
welcome12345 welcome123456 welcome2024! welcome2025! letmein12345 letmein123456
qwertyuiop12 qwertyuiop123 qwerty123456 qwertyuiopasdf qwertyuiopasdfgh 1qaz2wsx3edc
1q2w3e4r5t6y 1q2w3e4r5t6y7u8i qazwsxedcrfv zaq12wsxcde3 asdfghjkl123 zxcvbnm12345
iloveyou1234 iloveyou123456 sunshine1234 princess1234 football1234 baseball1234
superman1234 starwars1234 dragon123456 monkey123456 master123456 shadow123456
trustno11234 administrator admin1234567 admin12345678 administrator1 rootpassword
abcdefghijkl abcdefgh1234 abc123456789 abcd12345678 aaaaaaaaaaaa abcabcabcabc
correcthorsebatterystaple correct-horse-battery-staple 1234qwerasdfzxcv
football123! baseball123! michael12345 jennifer1234 charlie12345 jordan234567
whatever1234 freedom12345 computer1234 internet1234 secret123456 secretpassword
summer2024!! summer2025!! winter2024!! winter2025!! spring2025!! autumn2025!!
default12345 guest1234567 test12345678 testtest1234 temppassword temp12345678
skald1234567 skaldpassword analytics123 dashboard123 welcome1welcome
""".split()) | frozenset({"123456", "password", "12345678", "qwerty", "123456789",
                          "12345", "1234567890", "iloveyou", "letmein", "admin"})

# A real hash of nothing anyone knows, for doing the same work when there
# is no stored hash to check (an unknown email at sign-in).
_DUMMY_SALT = b"skald-dummy-salt"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _scrypt(pw: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    if not _slots.acquire(timeout=SLOT_WAIT):
        raise Busy("The server is busy checking passwords. Try again in a moment.")
    try:
        return hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                              maxmem=MAXMEM, dklen=dklen)
    finally:
        _slots.release()


def hash_password(pw: str) -> str:
    salt = os.urandom(SALT_BYTES)
    digest = _scrypt(pw, salt, N, R, P, HASH_BYTES)
    return f"scrypt${N}${R}${P}${_b64(salt)}${_b64(digest)}"


def _parse(stored) -> tuple[int, int, int, bytes, bytes] | None:
    if not isinstance(stored, str):
        return None
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        digest = base64.b64decode(parts[5], validate=True)
    except (ValueError, binascii.Error):
        return None
    if not (2 <= n <= 2 ** 17 and n & (n - 1) == 0 and 1 <= r <= 16 and 1 <= p <= 4):
        return None
    if 128 * r * n > MAXMEM // 2 or not salt or not 16 <= len(digest) <= 128:
        return None
    return n, r, p, salt, digest


def verify_password(pw: str, stored: str) -> bool:
    """True only when `pw` matches `stored`; False for "" or a malformed hash.
    Every way out costs one scrypt (a `burn` when there is nothing to check)."""
    if not isinstance(pw, str) or not pw or len(pw) > MAX_LENGTH:
        return burn(pw if isinstance(pw, str) else "")
    parsed = _parse(stored)
    if parsed is None:
        return burn(pw)
    n, r, p, salt, digest = parsed
    try:
        got = _scrypt(pw, salt, n, r, p, len(digest))
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(got, digest)


def burn(pw: str) -> bool:
    """The work of one check, against nothing. Always False."""
    _scrypt(str(pw or "")[:MAX_LENGTH], _DUMMY_SALT, N, R, P, HASH_BYTES)
    return False


def password_problem(pw: str, email: str = "") -> str | None:
    """None if the password is fine, else the reason in plain words."""
    if not isinstance(pw, str):
        return "Type a password."
    if len(pw) < MIN_LENGTH:
        return f"Use at least {MIN_LENGTH} characters."
    if len(pw) > MAX_LENGTH:
        return f"Use at most {MAX_LENGTH} characters."
    low = pw.lower()
    if len(set(low)) < 3:
        return "Use more than one or two different characters."
    address = (email or "").strip().lower()
    local = address.split("@", 1)[0]
    if address and (low == address or address in low or (len(local) >= 3 and local in low)):
        return "Do not use your email address in the password."
    if low in COMMON or low.rstrip("!0123456789") in COMMON:
        return "This password is too common. Choose another."
    return None
