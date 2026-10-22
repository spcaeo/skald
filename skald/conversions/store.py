"""conversions.sqlite: every conversion, the journeys behind them,
identities (name and email; on unless a site sets `conversions.identity:
anonymous`), the log of hook deliveries, the outgoing webhooks with their
outbox (conversions/outgoing.py), and - since 2.4.0 - the people's visits
with their address (people/visits.py, `visits` and `visit_days`), the rows
a sync removed (`removed`) and the `test` mark on a conversion; since 2.18
a lead's `label` (the lead hook's optional token; each row its own, a later
stage never takes an earlier one's) and `hook_rows`, a hook's rows in the
order they arrived (GET /traffic-hooks/<site>/leads, reconcile.py).

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
from . import ALIASES, FINISHED, STAGES

SCHEMA_VERSION = 8
STAMP = "%Y-%m-%dT%H:%M:%SZ"
FILE = "conversions.sqlite"
VID_DAYS = 30
RETENTION_DAYS = 400
DELIVERY_DAYS = 90
REPLAY_DAYS = 30         # a Cal.com/Typeform body's hash is kept this long
ABANDON_HOURS = 24
TEST_MARKED = 1          # marked (CLI or leads/test): later deliveries of the ref follow
TEST_SENT = 2            # the delivery itself said test: true; that row only

CONVERSIONS_V2 = """CREATE TABLE IF NOT EXISTS {name} (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, action TEXT NOT NULL,
  stage TEXT NOT NULL CHECK (stage IN ('started', 'completed', 'cancelled',
                                       'rescheduled', 'no_show', 'paid', 'won', 'lost')),
  at TEXT NOT NULL, vid TEXT, external_ref TEXT NOT NULL, tool TEXT NOT NULL,
  source_type TEXT, first_source TEXT, campaign TEXT, landing TEXT, country TEXT,
  device TEXT, first_touch_at TEXT, visits_before INTEGER, identity_id INTEGER
    REFERENCES identities(id) ON DELETE SET NULL,
  received_at TEXT NOT NULL,
  UNIQUE (site, tool, external_ref, stage));
"""
# Schema 4: `test` (1: kept and listed, never counted), added by ALTER to an
# older file, part of the table for a new one.
# Schema 7 (2.18): `label`, the lead hook's optional token (conversions.LABEL;
# NULL: none), added the same way.
CONVERSIONS = CONVERSIONS_V2.replace(
    "  received_at TEXT NOT NULL,\n",
    "  received_at TEXT NOT NULL, test INTEGER NOT NULL DEFAULT 0, label TEXT,\n")
INDEXES = """
CREATE INDEX IF NOT EXISTS conversions_at ON conversions (site, at);
CREATE INDEX IF NOT EXISTS conversions_vid ON conversions (site, vid);
"""
# Schema 7: a hook's rows in the order Skald got them (GET .../leads, reconcile.py).
RECEIVED_INDEX = ("CREATE INDEX IF NOT EXISTS conversions_received ON conversions "
                  "(site, tool, received_at, id)")

# Schema 4 (2.4.0): each reader's visit with its address and user agent
# (people/visits.py; written only while the site keeps them), the days
# written, and the rows a sync removed, kept whole.
PEOPLE_TABLES = """CREATE TABLE IF NOT EXISTS visits (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, day TEXT NOT NULL, seq INTEGER NOT NULL,
  ip TEXT NOT NULL, user_agent TEXT, start TEXT NOT NULL, end TEXT NOT NULL,
  source TEXT, via TEXT, referrer TEXT, campaign TEXT, landing TEXT, exit TEXT,
  country TEXT, device TEXT, browser TEXT, os TEXT, pages INTEGER NOT NULL,
  seconds INTEGER, trail TEXT NOT NULL, posts TEXT, city TEXT, UNIQUE (site, day, seq));
CREATE INDEX IF NOT EXISTS visits_ip ON visits (site, ip, start);
CREATE INDEX IF NOT EXISTS visits_day ON visits (day);
CREATE TABLE IF NOT EXISTS visit_days (
  site TEXT NOT NULL, day TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('whole', 'today')),
  visits INTEGER NOT NULL, pages INTEGER NOT NULL, written_at TEXT NOT NULL,
  PRIMARY KEY (site, day));
CREATE TABLE IF NOT EXISTS removed (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, removed_at TEXT NOT NULL, why TEXT NOT NULL,
  conversion_id INTEGER, tool TEXT, external_ref TEXT, vid TEXT, action TEXT, stage TEXT,
  at TEXT, row TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS removed_site ON removed (site, removed_at);
CREATE INDEX IF NOT EXISTS removed_ref ON removed (site, external_ref);
"""

# Schema 8 (2.21): the addresses behind Security's suspect rows (security_kept.py;
# written only while the site keeps addresses): one row per (day, seq) of the
# day kind `security`'s `who` list, and the days written.
SECURITY_TABLES = """CREATE TABLE IF NOT EXISTS security_rows (
  site TEXT NOT NULL, day TEXT NOT NULL, seq INTEGER NOT NULL, ip TEXT NOT NULL,
  user_agent TEXT, PRIMARY KEY (site, day, seq));
CREATE INDEX IF NOT EXISTS security_rows_ip ON security_rows (ip);
CREATE TABLE IF NOT EXISTS security_days (
  site TEXT NOT NULL, day TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('whole', 'today')),
  rows INTEGER NOT NULL, written_at TEXT NOT NULL, PRIMARY KEY (site, day));
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
""" + CONVERSIONS.format(name="conversions") + INDEXES + RECEIVED_INDEX + """;
CREATE TABLE IF NOT EXISTS journeys (
  vid TEXT NOT NULL, site TEXT NOT NULL, at TEXT NOT NULL, path TEXT NOT NULL,
  source_type TEXT, via TEXT);
CREATE INDEX IF NOT EXISTS journeys_vid ON journeys (site, vid, at);
CREATE INDEX IF NOT EXISTS journeys_at ON journeys (at);
CREATE INDEX IF NOT EXISTS journeys_site_at ON journeys (site, at);
CREATE TABLE IF NOT EXISTS identities (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, email_hash TEXT NOT NULL,
  email TEXT, name TEXT, created_at TEXT NOT NULL, UNIQUE (site, email_hash));
CREATE TABLE IF NOT EXISTS deliveries (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, tool TEXT NOT NULL,
  received_at TEXT NOT NULL, outcome TEXT NOT NULL, http_status INTEGER NOT NULL,
  error TEXT, external_ref TEXT);
CREATE INDEX IF NOT EXISTS deliveries_tool ON deliveries (site, tool, id);
CREATE TABLE IF NOT EXISTS webhooks (
  id INTEGER PRIMARY KEY, site TEXT NOT NULL, url TEXT NOT NULL, events TEXT NOT NULL,
  created_at TEXT NOT NULL, created_by TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY, webhook_id INTEGER NOT NULL
    REFERENCES webhooks(id) ON DELETE CASCADE,
  site TEXT NOT NULL, event TEXT NOT NULL, ref TEXT NOT NULL, body TEXT NOT NULL,
  created_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_at TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'sent', 'failed')),
  http_status INTEGER, error TEXT, sent_at TEXT, UNIQUE (webhook_id, event, ref));
CREATE INDEX IF NOT EXISTS outbox_due ON outbox (state, next_at);
CREATE TABLE IF NOT EXISTS hook_replays (
  site TEXT NOT NULL, digest TEXT NOT NULL, received_at TEXT NOT NULL,
  PRIMARY KEY (site, digest));
""" + PEOPLE_TABLES + SECURITY_TABLES

# Schema 2 (Phase 4b step 3): the stages "won" and "lost" (a CHECK cannot be
# changed in place, so the table is copied into a new one), one name per
# action (ALIASES; Stripe's unpaid checkout is a payment started, HubSpot's
# deal won is "won"), and the outgoing webhooks' tables (made by SCHEMA).
_V2_COLUMNS = ("id, site, action, stage, at, vid, external_ref, tool, source_type, "
               "first_source, campaign, landing, country, device, first_touch_at, "
               "visits_before, identity_id, received_at")
UPGRADES: dict[int, list[str]] = {2: [
    CONVERSIONS_V2.format(name="conversions_v2"),
    f"INSERT INTO conversions_v2 ({_V2_COLUMNS}) SELECT {_V2_COLUMNS} FROM conversions",
    "DROP TABLE conversions",
    "ALTER TABLE conversions_v2 RENAME TO conversions",
    "UPDATE conversions SET stage = 'started' WHERE tool = 'stripe' AND action = 'checkout' "
    "AND stage = 'completed'",
    "UPDATE conversions SET stage = 'won' WHERE tool = 'hubspot' AND action = 'deal' "
    "AND stage = 'paid'",
    *(f"UPDATE conversions SET action = '{new}' WHERE action = '{old}'"
      for old, new in ALIASES.items()),
    *INDEXES.strip().splitlines(),
],
    # 3: a site's journeys by time (pages before converting, the audit's
    # recount): a range in one site, not every journey of the site.
    3: ["CREATE INDEX IF NOT EXISTS journeys_site_at ON journeys (site, at)"],
    # 4: the test mark, the people's visits, the removed rows (PEOPLE_TABLES).
    4: ["ALTER TABLE conversions ADD COLUMN test INTEGER NOT NULL DEFAULT 0",
        *[sql.strip() + ";" for sql in PEOPLE_TABLES.split(";\n") if sql.strip()]],
    # 5: each kept visit's city, when a city file named one (logs.city_db).
    5: ["ALTER TABLE visits ADD COLUMN city TEXT"],
    # 6: the page view's referring host (the beacon's `r`; "" none, NULL a
    # row from before): a visitor ID's first touch (firsttouch.py).
    6: ["ALTER TABLE journeys ADD COLUMN via TEXT"],
    # 7 (2.18): a lead's label (NULL for every older row: none was sent), and
    # a hook's rows in the order received (GET /traffic-hooks/<site>/leads).
    7: ["ALTER TABLE conversions ADD COLUMN label TEXT", RECEIVED_INDEX],
    # 8 (2.21): the addresses behind Security's suspect rows (SECURITY_TABLES).
    8: [sql.strip() + ";" for sql in SECURITY_TABLES.split(";\n") if sql.strip()]}

# The SCHEMA this code set a file up with (see accounts/db.py): a file
# stamped with it at SCHEMA_VERSION skips the script on connect.
SCHEMA_STAMP = hashlib.sha256(SCHEMA.encode()).hexdigest()[:16]

COLUMNS = ("action", "stage", "at", "vid", "external_ref", "tool", "source_type",
           "first_source", "campaign", "landing", "country", "device", "first_touch_at",
           "visits_before", "label")


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

def record_conversion(db: sqlite3.Connection, rec: dict) -> bool:
    """Keep one conversion. Idempotent on (site, tool, external_ref, stage):
    the first delivery wins, a repeat changes nothing and returns False.

    `rec` holds COLUMNS plus `site`, optional `received_at`, optional
    `test` (True: the delivery said so, TEST_SENT) and optional `identity`
    {email, name}: pass it only when the site's identity is full."""
    if rec.get("stage") not in STAGES:
        raise ValueError(f"stage {rec.get('stage')!r} is not one of {STAGES}")
    for need in ("site", "action", "at", "external_ref", "tool"):
        if not rec.get(need):
            raise ValueError(f"a conversion needs {need}")
    with tx(db):
        hit = db.execute("SELECT 1 FROM conversions WHERE site = ? AND tool = ? AND "
                         "external_ref = ? AND stage = ?",
                         (rec["site"], rec["tool"], rec["external_ref"], rec["stage"])
                         ).fetchone()
        if hit:
            return False
        identity_id = _identity(db, rec["site"], rec.get("identity"))
        values = [rec.get(c) for c in COLUMNS]
        # A later stage of a booking or lead marked test is test too; one an
        # earlier delivery only sent as test passes nothing on.
        marked = db.execute("SELECT 1 FROM conversions WHERE site = ? AND tool = ? AND "
                            "external_ref = ? AND test = ? LIMIT 1",
                            (rec["site"], rec["tool"], rec["external_ref"], TEST_MARKED)
                            ).fetchone()
        test = TEST_MARKED if marked else TEST_SENT if rec.get("test") is True else 0
        db.execute(f"INSERT INTO conversions (site, {', '.join(COLUMNS)}, identity_id, "
                   f"received_at, test) VALUES ({', '.join('?' * (len(COLUMNS) + 4))})",
                   [rec["site"], *values, identity_id, rec.get("received_at") or stamp(),
                    int(test)])
    return True


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
    sql = ("SELECT id, external_ref, action, stage, at, label, test, received_at FROM "
           "conversions WHERE site = ? AND tool = ?")
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

def prune(db, today: date, vid_days: int = VID_DAYS,
          retention_days: int = RETENTION_DAYS) -> dict:
    """Delete what is past its time: journeys after vid_days unless their ID
    converted (kept as long as conversions), conversions after
    retention_days, identities nothing points to, deliveries after 90 days."""
    def edge(days: int) -> str:
        return stamp(datetime.combine(today - timedelta(days=days), time(0),
                                      tzinfo=timezone.utc))
    with tx(db):
        conv = db.execute("DELETE FROM conversions WHERE at < ?",
                          (edge(retention_days),)).rowcount
        db.execute("DELETE FROM removed WHERE removed_at < ?", (edge(retention_days),))
        old = db.execute("DELETE FROM journeys WHERE at < ?", (edge(retention_days),)).rowcount
        short = db.execute("DELETE FROM journeys WHERE at < ? AND NOT EXISTS ("
                           "SELECT 1 FROM conversions c WHERE c.site = journeys.site "
                           "AND c.vid = journeys.vid)", (edge(vid_days),)).rowcount
        ids = db.execute("DELETE FROM identities WHERE id NOT IN (SELECT identity_id FROM "
                         "conversions WHERE identity_id IS NOT NULL) AND id NOT IN (SELECT "
                         "CAST(json_extract(row, '$.identity_id') AS INTEGER) FROM removed "
                         "WHERE json_extract(row, '$.identity_id') IS NOT NULL)").rowcount
        dels = db.execute("DELETE FROM deliveries WHERE received_at < ?",
                          (edge(DELIVERY_DAYS),)).rowcount
        db.execute("DELETE FROM hook_replays WHERE received_at < ?", (edge(REPLAY_DAYS),))
    return {"conversions": conv, "journeys": old + short, "identities": ids,
            "deliveries": dels}


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
