"""conversions.sqlite: every conversion, the journeys behind them,
identities (name and email; on unless a site sets `conversions.identity:
anonymous`), the log of hook deliveries, the outgoing webhooks with their
outbox (conversions/outgoing.py), and - since 2.4.0 - the people's visits
with their address (people/visits.py, `visits` and `visit_days`), the rows
a sync removed (`removed`) and the `test` mark on a conversion; since 2.18
a lead's `label` (the lead hook's optional token; each row its own, a later
stage never takes an earlier one's) and `hook_rows`, a hook's rows in the
order they arrived (GET /traffic-hooks/<site>/leads, reconcile.py); since
2.32 (schema 9, the tables in schema.py) a row's money: `value_minor` in
`currency`, the sender's `customer_ref` and `tags`, Stripe's `pay_ref`, and
the stage `refunded` (one row per sale, record_conversion).

Beside the history (`conversions.db` to move it), apart from it because it
may hold personal data. 0640. Opened with `connect(path)` once per call
site; never shared between threads. Autocommit; a multi-statement write runs
inside `with tx(db):`.

Times are UTC, "2026-10-11T14:00:00Z". A figure not recorded is NULL.
A conversion row holds no address and no user agent; an email is kept only
in `identities`, and found again by a keyed hash (meta `hash_key`). The
address and user agent of a visit are in `visits` only, and only while the
site keeps them (people/policy.py, `privacy.keep_ips`; with `short` the
address is kept shortened, policy.shorten).

A row marked `test` is kept and listed, but left out of every figure; the
second count leaves it out by its own SQL. `test` is 0 (counted), TEST_MARKED
(1: `skald conversions mark-test`, or the site's own POST .../leads/test,
marks.py; a later delivery of the same ref is test too) or TEST_SENT (2,
since 2.19: the lead body's own `test: true`; that row only, nothing passes
on). Read it as "test <> 0"; only the inheritance tells 1 from 2.
Rows a lead-database sync takes away are copied whole into `removed` first
(`remove`), so nothing disappears unseen; only `forget` deletes for good.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from ..config import setting
from ..files import own_like_folder
from . import FINISHED, REFUNDED, STAGES
from .money import REFUND_CURRENCY_NOTE, REFUND_OVER_NOTE
# The tables and their upgrades (schema.py, split out in 2.32), re-exported.
from .schema import (COLUMNS, CONVERSIONS, CONVERSIONS_V2, CONVERSIONS_V8,  # noqa: F401
                     CONVERSIONS_V9, INDEXES, MONEY_INDEXES, MONEY_TABLES, PEOPLE_TABLES,
                     RECEIVED_INDEX,
                     SCHEMA, SCHEMA_STAMP, SCHEMA_VERSION, SECURITY_TABLES, UPGRADES)

STAMP = "%Y-%m-%dT%H:%M:%SZ"
FILE = "conversions.sqlite"
VID_DAYS = 30
RETENTION_DAYS = 400
DELIVERY_DAYS = 90
REPLAY_DAYS = 30         # a Cal.com/Typeform body's hash is kept this long
ABANDON_HOURS = 24
TEST_MARKED = 1          # marked (CLI or leads/test): later deliveries of the ref follow
TEST_SENT = 2            # the delivery itself said test: true; that row only


def path_for(config: dict, folder: Path | None) -> Path | None:
    """`conversions.db`, else conversions.sqlite in the history's folder."""
    raw = setting(config or {}, "conversions", "db")
    if raw:
        return Path(str(raw)).expanduser()
    return Path(folder) / FILE if folder is not None else None


def stamp(when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    return when.astimezone(timezone.utc).strftime(STAMP)


def parse(text: str) -> datetime:
    return datetime.strptime(text, STAMP).replace(tzinfo=timezone.utc)


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating or upgrading) the file. The caller closes it."""
    memory = str(path) == ":memory:"
    if not memory:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            fd = os.open(path, os.O_CREAT | os.O_WRONLY, 0o640)
            os.close(fd)
            os.chmod(path, 0o640)
            own_like_folder(path)
    db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout = 10000")
        if not memory:
            db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA foreign_keys = ON")
        if not _set_up(db):
            db.executescript(SCHEMA)
            _upgrade(db, None if memory else path)
            db.executescript(MONEY_INDEXES)
            db.execute("INSERT INTO meta (key, value) VALUES ('schema_stamp', ?) "
                       "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (SCHEMA_STAMP,))
    except BaseException:
        db.close()
        raise
    return db


def _set_up(db: sqlite3.Connection) -> bool:
    """True when this file was set up by this SCHEMA at SCHEMA_VERSION."""
    try:
        got = {r[0]: r[1] for r in db.execute(
            "SELECT key, value FROM meta WHERE key IN ('schema_version', 'schema_stamp')")}
    except sqlite3.OperationalError:             # a new file: no meta table yet
        return False
    return got.get("schema_version") == str(SCHEMA_VERSION) and \
        got.get("schema_stamp") == SCHEMA_STAMP


def _upgrade(db: sqlite3.Connection, path: Path | None = None) -> None:
    """Bring an older file up to SCHEMA_VERSION, a copy of it kept first
    beside it (conversions.sqlite.v<old>.bak, 0640). Never drops a row."""
    row = db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    found = int(row[0]) if row else None
    if found is not None and found > SCHEMA_VERSION:
        raise RuntimeError(f"conversions file is schema {found}, this code understands "
                           f"{SCHEMA_VERSION}; upgrade skald before reading it")
    if found == SCHEMA_VERSION:
        return
    if found is not None and path is not None:
        _copy(db, Path(path).with_name(f"{Path(path).name}.v{found}.bak"))
    with tx(db):
        for version in range((found or SCHEMA_VERSION) + 1, SCHEMA_VERSION + 1):
            for sql in UPGRADES.get(version, []):
                if _have_column(db, sql):
                    continue
                db.execute(sql)
        db.execute("INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                   "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                   (str(SCHEMA_VERSION),))


def _have_column(db: sqlite3.Connection, sql: str) -> bool:
    """An "ALTER TABLE t ADD COLUMN c" whose column is there already (a file
    stamped older than it is): skipped, so the upgrade still runs."""
    words = sql.split()
    if len(words) < 6 or [w.upper() for w in words[:2] + words[3:5]] != \
            ["ALTER", "TABLE", "ADD", "COLUMN"]:
        return False
    return words[5] in {r[1] for r in db.execute(f"PRAGMA table_info({words[2]})")}


def _copy(db: sqlite3.Connection, target: Path) -> None:
    """A consistent copy of the open file (sqlite's backup), 0640."""
    if target.exists():
        return
    fd = os.open(target, os.O_CREAT | os.O_WRONLY, 0o640)
    os.close(fd)
    os.chmod(target, 0o640)
    copy = sqlite3.connect(str(target))
    try:
        db.backup(copy)
    finally:
        copy.close()
    own_like_folder(target)


def schema_version(db: sqlite3.Connection) -> int:
    return int(db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0])


@contextmanager
def tx(db: sqlite3.Connection):
    """One write transaction; nested uses join the outer one."""
    if db.in_transaction:
        yield db
        return
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
    except BaseException:
        db.execute("ROLLBACK")
        raise
    db.execute("COMMIT")


def email_hash(db: sqlite3.Connection, email: str) -> str:
    """HMAC-SHA256 of the lower-cased email with this file's own key."""
    row = db.execute("SELECT value FROM meta WHERE key = 'hash_key'").fetchone()
    if row is None:
        db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('hash_key', ?)",
                   (secrets.token_hex(32),))
        row = db.execute("SELECT value FROM meta WHERE key = 'hash_key'").fetchone()
    return hmac.new(bytes.fromhex(row[0]), email.strip().lower().encode(),
                    hashlib.sha256).hexdigest()


# ------------------------------------------------------------------ writes

def record_conversion(db: sqlite3.Connection, rec: dict, notes: list | None = None) -> bool:
    """Keep one conversion. Idempotent on (site, tool, external_ref, stage):
    the first delivery wins, a repeat changes nothing and returns False.

    `rec` holds COLUMNS plus `site`, optional `received_at`, optional
    `test` (True: the delivery said so, TEST_SENT) and optional `identity`
    {email, name}: pass it only when the site's identity is full.

    A `refunded` row (2.32) is the one exception: one per sale, its amount the
    total refunded so far. A later delivery with a larger amount in the same
    currency raises it (Stripe's amount_refunded is cumulative) and returns
    True; anything else changes nothing. Each rise is kept in refund_parts
    with its own time, so it counts on the day it came. `refund_of` (Stripe's
    payment intent and invoice, and what pay_links joins them to) names the
    sale: the refund takes that row's external_ref. A refund sent without a
    value (`value_sent` False) is the whole sale's value; one whose value
    could not be read keeps none (not money). When its sale is known, a refund
    is never more than the sale (cut to it) nor in another currency (kept
    without a value); `notes` gets the note for each. A refund that came
    before its sale is moved onto the sale when the sale comes (_claim)."""
    if rec.get("stage") not in STAGES:
        raise ValueError(f"stage {rec.get('stage')!r} is not one of {STAGES}")
    for need in ("site", "action", "at", "external_ref", "tool"):
        if not rec.get(need):
            raise ValueError(f"a conversion needs {need}")
    with tx(db):
        if rec["stage"] == REFUNDED:
            rec = _refund(db, rec, notes if notes is not None else [])
        hit = db.execute("SELECT id, value_minor, currency FROM conversions WHERE site = ? AND "
                         "tool = ? AND external_ref = ? AND stage = ?",
                         (rec["site"], rec["tool"], rec["external_ref"], rec["stage"])
                         ).fetchone()
        if hit:
            return rec["stage"] == REFUNDED and _raise_refund(db, hit, rec)
        identity_id = _identity(db, rec["site"], rec.get("identity"))
        values = [rec.get(c) for c in COLUMNS]
        # A later stage of a booking or lead marked test is test too; one an
        # earlier delivery only sent as test passes nothing on.
        marked = db.execute("SELECT 1 FROM conversions WHERE site = ? AND tool = ? AND "
                            "external_ref = ? AND test = ? LIMIT 1",
                            (rec["site"], rec["tool"], rec["external_ref"], TEST_MARKED)
                            ).fetchone()
        test = TEST_MARKED if marked else TEST_SENT if rec.get("test") is True else 0
        got = db.execute(f"INSERT INTO conversions (site, {', '.join(COLUMNS)}, identity_id, "
                         f"received_at, test) VALUES ({', '.join('?' * (len(COLUMNS) + 4))})",
                         [rec["site"], *values, identity_id, rec.get("received_at") or stamp(),
                          int(test)])
        if rec["stage"] == REFUNDED:
            if rec.get("value_minor") is not None or rec.get("whole_later"):
                _part(db, got.lastrowid, rec, rec.get("value_minor"))
        elif rec["stage"] in FINISHED and rec.get("value_minor") is not None:
            _claim(db, rec["site"], rec["tool"], rec["external_ref"])
    return True


def sale_of(db, site: str, tool: str, ref: str):
    """The sale of one (tool, external ref): its `paid` row when that carries a
    value, else its `completed` row with one; None. (A `paid` after a
    `completed` is one lead, store.repeat_finishes, but the paid row is the
    sale: conversions_revenue.py.)"""
    return db.execute("SELECT id, value_minor, currency FROM conversions WHERE site = ? AND "
                      "tool = ? AND external_ref = ? AND stage IN ('paid', 'completed') AND "
                      "value_minor IS NOT NULL AND currency IS NOT NULL ORDER BY "
                      "stage = 'paid' DESC LIMIT 1", (site, tool, ref)).fetchone()


def _linked(db, site: str, tool: str, keys) -> list[str]:
    """`keys` (payment intents, invoices, refs) and what pay_links joins them to."""
    keys = sorted({k for k in keys if k})
    if not keys:
        return []
    marks = ",".join("?" * len(keys))
    more = {k for r in db.execute(
        f"SELECT invoice, payment FROM pay_links WHERE site = ? AND tool = ? AND (invoice IN "
        f"({marks}) OR payment IN ({marks}))", (site, tool, *keys, *keys)) for k in r}
    return sorted(set(keys) | more)


def _refund(db, rec: dict, notes: list) -> dict:
    """A refund's sale found by `refund_of` (its external ref taken); its whole
    value when none was sent; checked against the sale when there is one."""
    rec = dict(rec)
    keys = _linked(db, rec["site"], rec["tool"], rec.get("refund_of") or ())
    if keys:
        marks = ",".join("?" * len(keys))
        got = db.execute(f"SELECT external_ref FROM conversions WHERE site = ? AND tool = ? "
                         f"AND stage IN ('paid', 'completed') AND (pay_ref IN ({marks}) OR "
                         f"external_ref IN ({marks})) ORDER BY at, id LIMIT 1",
                         (rec["site"], rec["tool"], *keys, *keys)).fetchone()
        if got:
            rec["external_ref"] = got[0]
    sale = sale_of(db, rec["site"], rec["tool"], rec["external_ref"])
    if rec.get("value_minor") is None and rec.get("value_sent") is False:
        if sale is not None:
            rec["value_minor"], rec["currency"] = sale[1], sale[2]
        else:
            rec["whole_later"] = True       # filled in when the sale comes (_claim)
    elif rec.get("value_minor") is not None and sale is not None:
        if rec.get("currency") != sale[2]:
            rec["value_minor"] = rec["currency"] = None
            notes.append(REFUND_CURRENCY_NOTE)
        elif int(rec["value_minor"]) > int(sale[1]):
            rec["value_minor"] = int(sale[1])
            notes.append(REFUND_OVER_NOTE)
    return rec


def _part(db, row_id: int, rec: dict, value) -> None:
    """One part of a refund (None: a whole one, its value when the sale comes);
    a part of 0 is no refund and is not kept."""
    if value is not None and int(value) == 0:
        return
    db.execute("INSERT INTO refund_parts (conversion_id, at, value_minor, received_at) VALUES "
               "(?, ?, ?, ?)", (row_id, rec["at"], value, rec.get("received_at") or stamp()))


def _raise_refund(db, hit, rec: dict) -> bool:
    """A repeat refund: the larger amount in the same currency wins, its rise
    kept as a part of its own time."""
    new, cur = rec.get("value_minor"), rec.get("currency")
    if new is None and rec.get("whole_later") and hit[1] is None:
        # A whole refund after one whose value could not be read: it waits for
        # the sale's value, as if it had come first (never a duplicate).
        if db.execute("SELECT 1 FROM refund_parts WHERE conversion_id = ? AND value_minor IS "
                      "NULL", (hit[0],)).fetchone():
            return False
        _part(db, hit[0], rec, None)
        return True
    if new is None or not cur:
        return False
    if hit[1] is not None and (hit[2] != cur or int(new) <= int(hit[1])):
        return False
    db.execute("DELETE FROM refund_parts WHERE conversion_id = ? AND value_minor IS NULL",
               (hit[0],))
    db.execute("UPDATE conversions SET value_minor = ?, currency = ? WHERE id = ?",
               (int(new), cur, hit[0]))
    _part(db, hit[0], rec, int(new) - int(hit[1] or 0))
    return True


def _claim(db, site: str, tool: str, ref: str) -> None:
    """A sale was kept: the refunds that came before it (on its ref, its
    payment, or what pay_links joins them to) are moved onto it and fitted to
    it: a whole one takes its value, one in another currency keeps none, one
    over it is cut to it, its latest parts first. A refund already on the
    sale wins; the other stays where it is (a refund without a sale)."""
    sale = sale_of(db, site, tool, ref)
    if sale is None:
        return
    pays = [r[0] for r in db.execute("SELECT pay_ref FROM conversions WHERE site = ? AND "
                                     "tool = ? AND external_ref = ? AND pay_ref IS NOT NULL",
                                     (site, tool, ref))]
    keys = _linked(db, site, tool, [ref, *pays])
    marks = ",".join("?" * len(keys))
    for rid, their in db.execute(
            f"SELECT id, external_ref FROM conversions WHERE site = ? AND tool = ? AND stage = "
            f"'refunded' AND (external_ref IN ({marks}) OR pay_ref IN ({marks})) ORDER BY id",
            (site, tool, *keys, *keys)).fetchall():
        if their != ref:
            # Another sale's own refund, or the sale has one already: left where it is.
            busy = db.execute("SELECT 1 FROM conversions WHERE site = ? AND tool = ? AND ((("
                              "external_ref = ? AND stage IN ('completed', 'paid')) OR ("
                              "external_ref = ? AND stage = 'refunded'))) LIMIT 1",
                              (site, tool, their, ref)).fetchone()
            if busy:
                continue
            marked = db.execute("SELECT 1 FROM conversions WHERE site = ? AND tool = ? AND "
                                "external_ref = ? AND test = ? LIMIT 1",
                                (site, tool, ref, TEST_MARKED)).fetchone()
            db.execute("UPDATE conversions SET external_ref = ?" +
                       (", test = ?" if marked else "") + " WHERE id = ?",
                       (ref, TEST_MARKED, rid) if marked else (ref, rid))
        _fit(db, rid, sale)


def _fit(db, rid: int, sale) -> None:
    """One refund row fitted to its sale (_claim)."""
    value, cur = db.execute("SELECT value_minor, currency FROM conversions WHERE id = ?",
                            (rid,)).fetchone()
    parts = db.execute("SELECT id, value_minor FROM refund_parts WHERE conversion_id = ? "
                       "ORDER BY at, id", (rid,)).fetchall()
    whole, top = int(sale[1]), sale[2]
    if value is None:
        pending = [p for p in parts if p[1] is None]
        if pending:
            db.execute("UPDATE refund_parts SET value_minor = ? WHERE id = ?", (whole, pending[0][0]))
            db.execute("DELETE FROM refund_parts WHERE conversion_id = ? AND (value_minor IS NULL "
                       "OR value_minor = 0)", (rid,))
            db.execute("UPDATE conversions SET value_minor = ?, currency = ? WHERE id = ?",
                       (whole, top, rid))
        return
    if cur != top:
        db.execute("DELETE FROM refund_parts WHERE conversion_id = ?", (rid,))
        db.execute("UPDATE conversions SET value_minor = NULL, currency = NULL WHERE id = ?",
                   (rid,))
        return
    if int(value) <= whole:
        return
    left = whole
    for pid, part in parts:
        keep = min(int(part or 0), left)
        left -= keep
        if keep:
            db.execute("UPDATE refund_parts SET value_minor = ? WHERE id = ?", (keep, pid))
        else:
            db.execute("DELETE FROM refund_parts WHERE id = ?", (pid,))
    db.execute("UPDATE conversions SET value_minor = ? WHERE id = ?", (whole, rid))


def link_payments(db, site: str, tool: str, links, received_at: str) -> int:
    """Keep Stripe's (invoice, payment intent) links (invoice_payment.paid) and
    move onto their sale the refunds that were waiting for one. The new ones."""
    new = 0
    with tx(db):
        for invoice, payment in links:
            new += db.execute("INSERT OR IGNORE INTO pay_links (site, tool, invoice, payment, "
                              "received_at) VALUES (?, ?, ?, ?, ?)",
                              (site, tool, invoice, payment, received_at)).rowcount
            for (ref,) in db.execute(
                    "SELECT DISTINCT external_ref FROM conversions WHERE site = ? AND tool = ? "
                    "AND stage IN ('completed', 'paid') AND value_minor IS NOT NULL AND "
                    "(external_ref IN (?, ?) OR pay_ref IN (?, ?))",
                    (site, tool, invoice, payment, invoice, payment)).fetchall():
                _claim(db, site, tool, ref)
    return new


def remove(db, row_id: int, why: str) -> int:
    """Delete one conversion, its whole row (and its identity's email and
    name, when it had one) copied into `removed` first with when and why:
    a sync that takes a row away leaves it visible. 1, or 0 when gone."""
    import json
    row = db.execute("SELECT c.*, i.email AS email, i.name AS name FROM conversions c "
                     "LEFT JOIN identities i ON i.id = c.identity_id WHERE c.id = ?",
                     (row_id,)).fetchone()
    if row is None:
        return 0
    kept = dict(row)
    parts = [dict(p) for p in db.execute("SELECT at, value_minor, received_at FROM refund_parts "
                                         "WHERE conversion_id = ? ORDER BY at, id", (row_id,))]
    if parts:
        kept["refund_parts"] = parts            # gone with the row (CASCADE), kept here
    with tx(db):
        db.execute("INSERT INTO removed (site, removed_at, why, conversion_id, tool, "
                   "external_ref, vid, action, stage, at, row) VALUES "
                   "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (kept["site"], stamp(), str(why)[:200], kept["id"], kept["tool"],
                    kept["external_ref"], kept["vid"], kept["action"], kept["stage"],
                    kept["at"], json.dumps(kept, sort_keys=True)))
        db.execute("DELETE FROM conversions WHERE id = ?", (row_id,))
    return 1


def mark_test(db, site: str, ids, on: bool = True) -> list[dict]:
    """Mark conversions (by id) as test, or not (`on` False). Every row of
    the same booking or lead (site, tool, external ref) is marked with it,
    so its later stages are test too (TEST_MARKED; a row only sent as
    test becomes marked). The rows changed: {id, tool, external_ref,
    action, stage, at}. Raises ValueError for an id that is not this site's."""
    out = []
    to = TEST_MARKED if on else 0
    with tx(db):
        for cid in ids:
            row = db.execute("SELECT tool, external_ref FROM conversions WHERE id = ? AND "
                             "site = ?", (int(cid), site)).fetchone()
            if row is None:
                raise ValueError(f"no conversion {cid} on {site}")
            for r in db.execute("SELECT id, tool, external_ref, action, stage, at FROM "
                                "conversions WHERE site = ? AND tool = ? AND external_ref = ? "
                                "AND test != ?", (site, row[0], row[1], to)).fetchall():
                db.execute("UPDATE conversions SET test = ? WHERE id = ?", (to, r[0]))
                out.append(dict(r))
    return out


def mark_refs(db, site: str, tool: str, refs, on: bool = True) -> dict:
    """Mark every stage of each external ref of one site and tool as test
    (TEST_MARKED, so later deliveries of the ref follow), or not (`on`
    False). {"changed": rows whose counting changed, "already": rows that
    were so already, "not_found": refs with no row}. A row only sent as test
    (TEST_SENT) that is marked becomes TEST_MARKED and counts as already."""
    changed = already = 0
    unknown: list[str] = []
    with tx(db):
        for ref in refs:
            rows = db.execute("SELECT id, test FROM conversions WHERE site = ? AND tool = ? "
                              "AND external_ref = ?", (site, tool, ref)).fetchall()
            if not rows:
                unknown.append(ref)
                continue
            for rid, test in rows:
                if bool(test) == on:
                    already += 1
                else:
                    changed += 1
                if test != (TEST_MARKED if on else 0):
                    db.execute("UPDATE conversions SET test = ? WHERE id = ?",
                               (TEST_MARKED if on else 0, rid))
    return {"changed": changed, "already": already, "not_found": unknown}


def _identity(db, site: str, identity: dict | None) -> int | None:
    email = str((identity or {}).get("email") or "").strip()
    if not email:
        return None
    digest = email_hash(db, email)
    name = str((identity or {}).get("name") or "").strip()[:200] or None
    row = db.execute("SELECT id FROM identities WHERE site = ? AND email_hash = ?",
                     (site, digest)).fetchone()
    if row:
        if name:
            db.execute("UPDATE identities SET name = ? WHERE id = ?", (name, row[0]))
        return row[0]
    return db.execute("INSERT INTO identities (site, email_hash, email, name, created_at) "
                      "VALUES (?, ?, ?, ?, ?)",
                      (site, digest, email[:320], name, stamp())).lastrowid


def record_page_view(db, site: str, vid: str, at: str, path: str,
                     source_type: str | None, via: str | None = None) -> None:
    db.execute("INSERT INTO journeys (vid, site, at, path, source_type, via) "
               "VALUES (?, ?, ?, ?, ?, ?)", (vid, site, at, path, source_type, via))


def log_delivery(db, site: str, tool: str, outcome: str, http_status: int,
                 error: str | None = None, external_ref: str | None = None,
                 received_at: str | None = None) -> None:
    """One row of the delivery log. Never a body: only what happened."""
    db.execute("INSERT INTO deliveries (site, tool, received_at, outcome, http_status, error, "
               "external_ref) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (site, tool, received_at or stamp(), outcome, int(http_status),
                (error or None) and str(error)[:200], external_ref))


# ------------------------------------------------------------------- reads

def replayed(db, site: str, digest: str, since: str) -> bool:
    """Was this body (its hash, hooks.replay_digest) accepted since `since`?"""
    return db.execute("SELECT 1 FROM hook_replays WHERE site = ? AND digest = ? AND "
                      "received_at >= ?", (site, digest, since)).fetchone() is not None


def keep_replay(db, site: str, digest: str, received_at: str) -> None:
    """Remember an accepted body's hash (never the body). `forget` leaves it,
    so replaying a forgotten person's body cannot bring the row back."""
    db.execute("INSERT INTO hook_replays (site, digest, received_at) VALUES (?, ?, ?) "
               "ON CONFLICT(site, digest) DO UPDATE SET received_at = excluded.received_at",
               (site, digest, received_at))


def _rows(db, sql: str, args=()) -> list[dict]:
    return [dict(r) for r in db.execute(sql, args)]


def deliveries(db, site: str, tool: str | None = None, limit: int = 50) -> list[dict]:
    if tool:
        return _rows(db, "SELECT * FROM deliveries WHERE site = ? AND tool = ? "
                         "ORDER BY id DESC LIMIT ?", (site, tool, limit))
    return _rows(db, "SELECT * FROM deliveries WHERE site = ? ORDER BY id DESC LIMIT ?",
                 (site, limit))


def hook_rows(db, site: str, tool: str, since: str | None = None, after=None,
              at_since: str | None = None, at_until: str | None = None,
              limit: int = 200) -> list[dict]:
    """One hook's rows in the order Skald got them (received_at, then id),
    test rows too: received at or after `since`, after `after` (the
    (received_at, id) of a page's last row), with `at` in [at_since,
    at_until). Only what a sender may see again: never a visitor ID, a
    source, an identity. At most `limit`."""
    sql = ("SELECT id, external_ref, action, stage, at, label, test, received_at, value_minor, "
           "currency, customer_ref, tags FROM conversions WHERE site = ? AND tool = ?")
    args: list = [site, tool]
    if since:
        sql += " AND received_at >= ?"
        args.append(since)
    if after:
        sql += " AND (received_at > ? OR (received_at = ? AND id > ?))"
        args += [after[0], after[0], int(after[1])]
    if at_since:
        sql += " AND at >= ?"
        args.append(at_since)
    if at_until:
        sql += " AND at < ?"
        args.append(at_until)
    return _rows(db, sql + " ORDER BY received_at, id LIMIT ?", (*args, int(limit)))


def abandoned(db, site: str, since: str, until: str, hours: float = ABANDON_HOURS,
              now: str | None = None) -> list[dict]:
    """Starts in [since, until) with a visitor ID and no completed or paid
    for the same action within `hours`, by the same visitor ID or, when the
    start has one, the same identity (a booking made later from another
    browser or session is a finish, not a second lead). A start whose window
    is still open at `now` is left out: it is not abandoned yet. A start
    without a visitor ID cannot be matched and is left out too."""
    cutoff = stamp(parse(now or stamp()) - timedelta(hours=hours))
    marks = ",".join("?" * len(FINISHED))
    starts = _rows(db, "SELECT c.*, i.email AS email FROM conversions c "
                       "LEFT JOIN identities i ON i.id = c.identity_id "
                       "WHERE c.site = ? AND c.stage = 'started' AND c.vid IS NOT NULL "
                       "AND c.test = 0 "
                       "AND c.at >= ? AND c.at < ? AND c.at <= ? ORDER BY c.at",
                   (site, since, until, cutoff))
    out = []
    for row in starts:
        end = stamp(parse(row["at"]) + timedelta(hours=hours))
        done = db.execute(f"SELECT 1 FROM conversions WHERE site = ? AND (vid = ? OR "
                          f"(? IS NOT NULL AND identity_id = ?)) AND "
                          f"action = ? AND stage IN ({marks}) AND at >= ? AND at <= ? "
                          f"AND test = 0",
                          (site, row["vid"], row["identity_id"], row["identity_id"],
                           row["action"], *FINISHED, row["at"], end)).fetchone()
        if not done:
            out.append(row)
    return out


def journey_of(db, site: str, vid: str) -> dict:
    """A visitor ID's page views and conversions, in time order."""
    return {"vid": vid,
            "pages": _rows(db, "SELECT at, path, source_type FROM journeys "
                               "WHERE site = ? AND vid = ? ORDER BY at", (site, vid)),
            "conversions": _rows(db, "SELECT action, stage, at, tool, source_type, campaign, "
                                     "landing, country, device, test FROM conversions "
                                     "WHERE site = ? AND vid = ? ORDER BY at, id",
                                 (site, vid))}


def repeat_finishes(db, site: str) -> set[int]:
    """The ids of the rows that finish a lead again (2.26). One lead is one
    (site, tool, external_ref, action) of a lead action (LEAD_ACTIONS): of its
    finished rows (FINISHED), test ones left out, the earliest (by `at`, then
    the stage's name) is the lead; another (a `paid` after a `completed`) stays
    a row, listed among the lead's steps, and is never counted. Before 2.26
    each finished row was a lead, so such a ref was two."""
    from . import LEAD_ACTIONS
    rows = db.execute(f"SELECT id, tool, external_ref, action, stage, at FROM conversions "
                      f"WHERE site = ? AND test = 0 AND stage IN "
                      f"({','.join('?' * len(FINISHED))}) AND action IN "
                      f"({','.join('?' * len(LEAD_ACTIONS))})",
                      (site, *FINISHED, *LEAD_ACTIONS)).fetchall()
    leads: dict = {}
    for rid, tool, ref, action, stage, at in rows:
        leads.setdefault((tool, ref, action), []).append((at, stage, rid))
    out: set[int] = set()
    for found in leads.values():
        if len(found) > 1:
            out.update(rid for _, _, rid in sorted(found)[1:])
    return out


def day_counts(db, site: str, tz, first: date, last: date,
               tools=None) -> dict[str, dict[tuple[str, str], int]]:
    """{local day: {(action, stage): n}} for conversions whose `at` falls on
    first..last in `tz`, a lead's repeat finish (repeat_finishes) left out.
    Days with none are left out."""
    lo = datetime.combine(first, time(0), tzinfo=tz)
    hi = datetime.combine(last + timedelta(days=1), time(0), tzinfo=tz)
    sql = ("SELECT at, action, stage, id FROM conversions WHERE site = ? AND at >= ? AND "
           "at < ? AND test = 0")
    args = [site, stamp(lo), stamp(hi)]
    if tools:
        sql += f" AND tool IN ({','.join('?' * len(tools))})"
        args += list(tools)
    again = repeat_finishes(db, site)
    out: dict = {}
    for at, action, stage, rid in db.execute(sql, args):
        if rid in again:
            continue
        day = parse(at).astimezone(tz).date().isoformat()
        per = out.setdefault(day, {})
        per[(action, stage)] = per.get((action, stage), 0) + 1
    return out


# --------------------------------------------------------- prune and forget

FOREVER = 0              # conversions.retention_days 0: kept for good (2.29)
FOREVER_WORDS = ("forever", "for good", "for_good")


def keep_days_of(raw, default: int = RETENTION_DAYS) -> int:
    """conversions.retention_days as days: 0 (FOREVER) for 0, "forever" or
    "for good"; the default when unset or not a whole number of days."""
    if raw is None or isinstance(raw, bool):
        return default
    if isinstance(raw, str) and raw.strip().lower() in FOREVER_WORDS:
        return FOREVER
    try:
        n = int(str(raw).strip())
    except ValueError:
        return default
    return n if n >= 0 else default


def keep_days(config: dict) -> int:
    """How long leads, their removed rows, the pages their IDs read and the
    hook spool are kept: `conversions.retention_days` (400); 0 for good."""
    return keep_days_of(setting(config or {}, "conversions", "retention_days"))


def vid_days(config: dict) -> int:
    """`journeys.vid_days` (30): how long an ID's page views are kept while
    the ID has no conversion; at least 1."""
    try:
        return max(1, int(setting(config or {}, "journeys", "vid_days", VID_DAYS)))
    except (TypeError, ValueError):
        return VID_DAYS


def prune(db, today: date, vid_days: int = VID_DAYS,
          retention_days: int = RETENTION_DAYS, own_vid: dict | None = None,
          own_keep: dict | None = None) -> dict:
    """Delete what is past its time, per site (a site in `own_keep` /
    `own_vid` by its own days): conversions, removed rows and journeys after
    retention_days - never when it is 0 (FOREVER); the journeys of an ID with
    no conversion after vid_days; identities nothing points to; deliveries
    after DELIVERY_DAYS whatever the site keeps."""
    def edge(days: int) -> str:
        return stamp(datetime.combine(today - timedelta(days=days), time(0),
                                      tzinfo=timezone.utc))
    own_vid, own_keep = own_vid or {}, own_keep or {}
    conv = old = short = 0
    with tx(db):
        sites = {r[0] for t in ("conversions", "removed", "journeys")
                 for r in db.execute(f"SELECT DISTINCT site FROM {t}")}
        for site in sorted(sites):
            keep = int(own_keep.get(site, retention_days))
            if keep != FOREVER:
                cut = edge(keep)
                conv += db.execute("DELETE FROM conversions WHERE site = ? AND at < ?",
                                   (site, cut)).rowcount
                db.execute("DELETE FROM removed WHERE site = ? AND removed_at < ?", (site, cut))
                old += db.execute("DELETE FROM journeys WHERE site = ? AND at < ?",
                                  (site, cut)).rowcount
            short += db.execute("DELETE FROM journeys WHERE site = ? AND at < ? AND NOT EXISTS "
                                "(SELECT 1 FROM conversions c WHERE c.site = journeys.site AND "
                                "c.vid = journeys.vid)",
                                (site, edge(max(1, int(own_vid.get(site, vid_days)))))).rowcount
        ids = db.execute("DELETE FROM identities WHERE id NOT IN (SELECT identity_id FROM "
                         "conversions WHERE identity_id IS NOT NULL) AND id NOT IN (SELECT "
                         "CAST(json_extract(row, '$.identity_id') AS INTEGER) FROM removed "
                         "WHERE json_extract(row, '$.identity_id') IS NOT NULL)").rowcount
        dels = db.execute("DELETE FROM deliveries WHERE received_at < ?",
                          (edge(DELIVERY_DAYS),)).rowcount
        db.execute("DELETE FROM hook_replays WHERE received_at < ?", (edge(REPLAY_DAYS),))
        for site in sorted(sites):
            keep = int(own_keep.get(site, retention_days))
            if keep != FOREVER:
                db.execute("DELETE FROM pay_links WHERE site = ? AND received_at < ?",
                           (site, edge(keep)))
    return {"conversions": conv, "journeys": old + short, "identities": ids,
            "deliveries": dels}


def prune_preview(path, site: str, name: str, cutoff: str) -> tuple:
    """(rows, days, first, last) a shorter conversions.retention_days (its
    conversions, removed rows and journeys) or journeys.vid_days (the page
    views of IDs with no conversion) would remove for `site`: rows before
    `cutoff` (a day), the file opened read-only."""
    import sqlite3
    if path is None or not Path(path).is_file():
        return 0, 0, None, None
    parts = ["SELECT substr(at, 1, 10) AS d FROM journeys WHERE site = ? AND at < ?" + (
        "" if name == "conversions.retention_days" else
        " AND NOT EXISTS (SELECT 1 FROM conversions c WHERE c.site = journeys.site AND "
        "c.vid = journeys.vid)")]
    if name == "conversions.retention_days":
        parts += ["SELECT substr(at, 1, 10) FROM conversions WHERE site = ? AND at < ?",
                  "SELECT substr(removed_at, 1, 10) FROM removed WHERE site = ? AND "
                  "removed_at < ?"]
    sql = ("SELECT COUNT(*), COUNT(DISTINCT d), MIN(d), MAX(d) FROM ("
           + " UNION ALL ".join(parts) + ")")
    try:
        db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        try:
            row = db.execute(sql, [site, cutoff] * len(parts)).fetchone()
        finally:
            db.close()
    except sqlite3.Error:
        return 0, 0, None, None
    return int(row[0] or 0), int(row[1] or 0), row[2], row[3]


def forget(db, site: str | None, email: str | None = None, vid: str | None = None,
           external_ref: str | None = None, dry_run: bool = False) -> dict:
    """Delete everything for an email, a visitor ID or a lead (external ref):
    its conversions, the journeys of every visitor ID they carry, the other
    conversions of those IDs, the removed rows of any of them, its identity
    and its delivery rows. Counts.
    The hashes in hook_replays stay: they hold nothing of the person."""
    where_site, args_site = ("site = ? AND ", [site]) if site else ("", [])
    with tx(db):
        ids: set[int] = set()
        vids: set[str] = set()
        refs: set[str] = set()
        if email:
            digest = email_hash(db, email)
            ids |= {r[0] for r in db.execute(
                f"SELECT id FROM identities WHERE {where_site}email_hash = ?",
                [*args_site, digest])}
        if vid:
            vids.add(vid)
        if external_ref:
            refs.add(external_ref)
        conv: set[int] = set()
        gone: set[int] = set()
        for _ in range(3):        # IDs lead to conversions lead to more IDs
            before = (len(conv), len(vids), len(ids))
            for column, values in (("identity_id", ids), ("vid", vids),
                                   ("external_ref", refs)):
                for value in list(values):
                    for row in db.execute(f"SELECT id, vid, identity_id, external_ref FROM "
                                          f"conversions WHERE {where_site}{column} = ?",
                                          [*args_site, value]).fetchall():
                        conv.add(row[0])
                        if row[1]:
                            vids.add(row[1])
                        if row[2]:
                            ids.add(row[2])
                        refs.add(row[3])
            if (len(conv), len(vids), len(ids)) == before:
                break
        for row in db.execute(f"SELECT id, vid, external_ref, row FROM removed WHERE "
                              f"{where_site}1 = 1", args_site).fetchall():
            ident = _row_identity(row[3])
            if row[1] in vids or row[2] in refs or (ident is not None and ident in ids):
                gone.add(row[0])
                if row[1]:
                    vids.add(row[1])
        counts = {"conversions": len(conv), "identities": len(ids), "journeys": 0,
                  "deliveries": 0, "removed": len(gone), "vids": sorted(vids),
                  "refs": sorted(refs)}
        for v in vids:
            counts["journeys"] += db.execute(
                f"SELECT COUNT(*) FROM journeys WHERE {where_site}vid = ?",
                [*args_site, v]).fetchone()[0]
        for r in refs:
            counts["deliveries"] += db.execute(
                f"SELECT COUNT(*) FROM deliveries WHERE {where_site}external_ref = ?",
                [*args_site, r]).fetchone()[0]
        if not dry_run:
            for cid in conv:
                db.execute("DELETE FROM conversions WHERE id = ?", (cid,))
            for v in vids:
                db.execute(f"DELETE FROM journeys WHERE {where_site}vid = ?", [*args_site, v])
            for r in refs:
                db.execute(f"DELETE FROM deliveries WHERE {where_site}external_ref = ?",
                           [*args_site, r])
            for rid in gone:
                db.execute("DELETE FROM removed WHERE id = ?", (rid,))
            for i in ids:
                db.execute("DELETE FROM identities WHERE id = ?", (i,))
    return counts


def _row_identity(text) -> int | None:
    import json
    try:
        got = json.loads(text).get("identity_id")
    except (TypeError, ValueError, AttributeError):
        return None
    return int(got) if isinstance(got, int) else None
