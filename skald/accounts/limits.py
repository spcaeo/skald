"""Counting failed tries: sign-ins per email and per address, reset mails.

A key such as "login:ip:203.0.113.10" is kept only as a keyed hash, so the
table holds no address or email. Rows older than a day are dropped as new
ones come in. Nothing is ever locked: the caller decides what "too many"
means (wait 30 s, send no mail).

Sign-in uses `take`: in one write transaction it checks every key and, when
none is held back, writes a try for each BEFORE the password is checked.
So forty tries sent at once cannot all slip past the check: the first one's
row is there when the second looks. A try counts as a failure until a
success `forget`s it.
"""
from __future__ import annotations

from . import db as base

KEEP_SECONDS = 86400


def note_failure(db, key: str) -> None:
    with base.tx(db):
        db.execute("DELETE FROM attempts WHERE at < ?", (base.shift(-KEEP_SECONDS),))
        db.execute("INSERT INTO attempts (key, at) VALUES (?, ?)",
                   (base.keyed_hash(db, key), base.now()))


def take(db, keys, limit: int, minutes: int, wait: float) -> list[int] | None:
    """Row ids of one try noted for each key, or None (nothing written) when
    any key had `limit` or more tries in `minutes` and one in the last `wait`
    seconds. Atomic: two callers cannot both pass on the same last slot."""
    with base.tx(db):
        for key in keys:
            if too_many(db, key, limit, minutes) and count(db, key, minutes=wait / 60) > 0:
                return None
        db.execute("DELETE FROM attempts WHERE at < ?", (base.shift(-KEEP_SECONDS),))
        stamp = base.now()
        return [db.execute("INSERT INTO attempts (key, at) VALUES (?, ?)",
                           (base.keyed_hash(db, key), stamp)).lastrowid for key in keys]


def forget(db, row_ids) -> None:
    """Drop the tries `take` noted (the sign-in worked)."""
    for row_id in row_ids or ():
        db.execute("DELETE FROM attempts WHERE rowid = ?", (row_id,))


def count(db, key: str, minutes: int = 15) -> int:
    return db.execute("SELECT COUNT(*) FROM attempts WHERE key = ? AND at > ?",
                      (base.keyed_hash(db, key), base.shift(-minutes * 60))).fetchone()[0]


def too_many(db, key: str, limit: int = 5, minutes: int = 15) -> bool:
    return count(db, key, minutes) >= limit


def clear(db, key: str) -> None:
    db.execute("DELETE FROM attempts WHERE key = ?", (base.keyed_hash(db, key),))
