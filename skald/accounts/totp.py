"""Two-step sign-in: time-based one-time codes (RFC 6238) and recovery codes.

SHA-1, 30-second steps, 6 digits, one step of drift either way. A code is
accepted once: the step of the last good code is kept per user, and a code
from that step or an earlier one is refused. Turning it on is two steps:
`begin` keeps a pending secret, `confirm` checks a code from the app and
answers the 10 recovery codes (shown once; only their hashes are kept).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode

from . import auditlog
from . import db as base

STEP = 30
DIGITS = 6
RECOVERY_COUNT = 10
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes | None:
    text = "".join(str(secret or "").split()).upper().rstrip("=")
    try:
        return base64.b32decode(text + "=" * (-len(text) % 8))
    except (binascii.Error, ValueError):
        return None


def _code(key: bytes, counter: int, digits: int) -> str:
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    number = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10 ** digits).zfill(digits)


def code_at(secret, t: int, digits: int = DIGITS) -> str:
    key = _key(secret)
    if key is None:
        raise ValueError("not a base32 secret")
    return _code(key, int(t) // STEP, digits)


def matching_step(secret, code, t=None, window: int = 1) -> int | None:
    """The time step `code` belongs to, within `window` steps of `t`, or None."""
    code = "".join(str(code or "").split())
    key = _key(secret)
    if key is None or len(code) != DIGITS or not code.isdigit():
        return None
    now_step = int(base.epoch() if t is None else t) // STEP
    found = None
    for step in range(now_step - window, now_step + window + 1):
        if hmac.compare_digest(_code(key, step, DIGITS), code):
            found = step
    return found


def verify(secret, code, t=None, window: int = 1) -> bool:
    return matching_step(secret, code, t, window) is not None


def provisioning_uri(secret, email, issuer: str = "Skald") -> str:
    label = quote(f"{issuer}:{email}", safe=":")
    query = urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1",
                       "digits": DIGITS, "period": STEP})
    return f"otpauth://totp/{label}?{query}"


def _clean_code(code) -> str:
    return "".join(ch for ch in str(code or "").lower() if ch.isalnum())


def code_hash(code) -> str:
    return base.sha256(_clean_code(code))


def recovery_codes() -> tuple[list[str], list[str]]:
    """(the codes to show once, the hashes to store)."""
    shown = []
    while len(shown) < RECOVERY_COUNT:
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        code = f"{raw[:5]}-{raw[5:]}"
        if code not in shown:
            shown.append(code)
    return shown, [code_hash(c) for c in shown]


def begin(db, user_id) -> tuple[str, str]:
    """A new pending secret and its otpauth:// link; not on until confirmed."""
    row = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("There is no such user.")
    secret = new_secret()
    db.execute("UPDATE users SET totp_pending = ? WHERE id = ?", (secret, user_id))
    return secret, provisioning_uri(secret, row["email"])


def confirm(db, user_id, code, actor, t=None) -> list[str]:
    """Turn two-step sign-in on with a code from the app; the recovery codes."""
    row = db.execute("SELECT email, totp_pending FROM users WHERE id = ?",
                     (user_id,)).fetchone()
    if row is None or not row["totp_pending"]:
        raise ValueError("Start setting up two-step sign-in first.")
    step = matching_step(row["totp_pending"], code, t)
    if step is None:
        raise ValueError("That code is not right. Check the time on your phone and try again.")
    shown, hashes = recovery_codes()
    with base.tx(db):
        db.execute("UPDATE users SET totp_secret = totp_pending, totp_pending = NULL, "
                   "totp_last_step = ? WHERE id = ?", (step, user_id))
        db.execute("DELETE FROM recovery WHERE user_id = ?", (user_id,))
        db.executemany("INSERT INTO recovery (user_id, code_hash) VALUES (?, ?)",
                       [(user_id, h) for h in hashes])
        auditlog.record(db, None, actor, "totp.on", row["email"])
    return shown


def disable(db, user_id, actor) -> None:
    row = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ValueError("There is no such user.")
    with base.tx(db):
        db.execute("UPDATE users SET totp_secret = NULL, totp_pending = NULL, "
                   "totp_last_step = NULL WHERE id = ?", (user_id,))
        db.execute("DELETE FROM recovery WHERE user_id = ?", (user_id,))
        auditlog.record(db, None, actor, "totp.off", row["email"])


def check_user(db, user_id, code, t=None) -> bool:
    """A sign-in code: a fresh app code, or an unused recovery code (used up)."""
    row = db.execute("SELECT email, totp_secret, totp_last_step FROM users WHERE id = ?",
                     (user_id,)).fetchone()
    if row is None or not row["totp_secret"]:
        return False
    step = matching_step(row["totp_secret"], code, t)
    if step is not None:
        cur = db.execute("UPDATE users SET totp_last_step = ? WHERE id = ? AND "
                         "(totp_last_step IS NULL OR totp_last_step < ?)",
                         (step, user_id, step))
        return bool(cur.rowcount)
    if len(_clean_code(code)) != 10:
        return False
    with base.tx(db):
        cur = db.execute("UPDATE recovery SET used_at = ? WHERE user_id = ? AND code_hash = ? "
                         "AND used_at IS NULL", (base.now(), user_id, code_hash(code)))
        if cur.rowcount:
            left = db.execute("SELECT COUNT(*) FROM recovery WHERE user_id = ? "
                              "AND used_at IS NULL", (user_id,)).fetchone()[0]
            auditlog.record(db, None, user_id, "totp.recovery_used", row["email"],
                            f"{left} left")
        return bool(cur.rowcount)
