"""The accounts file: organisations, people, sessions, tokens, the audit log.

`accounts.sqlite` sits beside the history (`access.accounts` to move it),
kept apart from `history.sqlite` so figures and people never mix. Opened
with `connect(path)`, once per call site: a connection is never shared
between threads and never kept at module level. Autocommit; a write that
spans several statements runs inside `with tx(db):`.

Nothing secret is stored as given: session cookies, reset and invite links,
API tokens and recovery codes are kept as SHA-256; addresses and rate-limit
keys only as an HMAC with a per-install key (meta `hash_key`, made on first
use), so the file holds no raw address.

`now()` is the one clock every module reads, so tests can move it.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..files import own_like_folder

SCHEMA_VERSION = 4
STAMP = "%Y-%m-%dT%H:%M:%SZ"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orgs (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL, plan TEXT, plan_status TEXT NOT NULL DEFAULT 'none',
  trial_ends_at TEXT, stripe_customer TEXT, stripe_subscription TEXT,
  created_via TEXT NOT NULL DEFAULT 'cli', past_due_since TEXT);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL DEFAULT '',
  pw_hash TEXT, install_admin INTEGER NOT NULL DEFAULT 0,
  totp_secret TEXT, totp_pending TEXT, totp_last_step INTEGER,
  created_at TEXT NOT NULL, last_seen TEXT, disabled_at TEXT,
  must_reset INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS members (
  org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'viewer')),
  added_by TEXT, added_at TEXT NOT NULL, PRIMARY KEY (org_id, user_id));
CREATE INDEX IF NOT EXISTS members_user ON members (user_id);
CREATE TABLE IF NOT EXISTS sites (
  name TEXT PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id));
CREATE TABLE IF NOT EXISTS sessions (
  id_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL, created_at TEXT NOT NULL, last_seen TEXT NOT NULL,
  expires_at TEXT NOT NULL, ip_hash TEXT, agent TEXT,
  ttl_seconds INTEGER NOT NULL DEFAULT 1209600);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id);
CREATE TABLE IF NOT EXISTS invites (
  token_hash TEXT PRIMARY KEY,
  org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  email TEXT NOT NULL, role TEXT NOT NULL, invited_by TEXT, created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL, used_at TEXT, handed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS resets (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT);
CREATE TABLE IF NOT EXISTS recovery (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code_hash TEXT NOT NULL, used_at TEXT, PRIMARY KEY (user_id, code_hash));
CREATE TABLE IF NOT EXISTS tokens (
  id TEXT PRIMARY KEY, org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
  name TEXT NOT NULL, sha256 TEXT NOT NULL, sites TEXT, private INTEGER NOT NULL DEFAULT 0,
  scopes TEXT NOT NULL, created_by TEXT, created_at TEXT NOT NULL, last_used TEXT,
  revoked_at TEXT);
CREATE TABLE IF NOT EXISTS settings (
  scope TEXT NOT NULL, key TEXT NOT NULL, value TEXT, updated_by TEXT, updated_at TEXT,
  PRIMARY KEY (scope, key));
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, org_id INTEGER, actor TEXT NOT NULL,
  action TEXT NOT NULL, target TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS audit_org ON audit (org_id, id);
CREATE TABLE IF NOT EXISTS attempts (key TEXT NOT NULL, at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS attempts_key ON attempts (key, at);
CREATE TABLE IF NOT EXISTS signups (
  token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL, used_at TEXT, ip_hash TEXT);
CREATE INDEX IF NOT EXISTS signups_email ON signups (email, created_at);
CREATE TABLE IF NOT EXISTS billing_events (
  event_id TEXT PRIMARY KEY, type TEXT NOT NULL, org_id INTEGER, created INTEGER,
  received_at TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT '');
"""

# version -> statements that bring a file from version-1 up to it.
# 2: users.must_reset (an account made from an invite link that was shown to
#    the admin, not mailed, must choose a new password at its first sign-in)
#    and invites.handed (that link was shown on screen).
# 3: the organisation's plan and billing state (saas/, off by default):
#    plan, plan_status (trialing, active, past_due, canceled, none),
#    trial_ends_at, stripe_customer, stripe_subscription, created_via (cli,
#    invite, signup) and past_due_since (the grace period counts from it).
#    The signups and billing_events tables are made by SCHEMA.
# Each statement is applied only when its column is missing, so a file made
# by any older SCHEMA comes out the same.
UPGRADES: dict[int, list[str]] = {
    2: ["ALTER TABLE users ADD COLUMN must_reset INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE invites ADD COLUMN handed INTEGER NOT NULL DEFAULT 0"],
    3: ["ALTER TABLE orgs ADD COLUMN plan TEXT",
        "ALTER TABLE orgs ADD COLUMN plan_status TEXT NOT NULL DEFAULT 'none'",
        "ALTER TABLE orgs ADD COLUMN trial_ends_at TEXT",
        "ALTER TABLE orgs ADD COLUMN stripe_customer TEXT",
        "ALTER TABLE orgs ADD COLUMN stripe_subscription TEXT",
        "ALTER TABLE orgs ADD COLUMN created_via TEXT NOT NULL DEFAULT 'cli'",
        "ALTER TABLE orgs ADD COLUMN past_due_since TEXT"],
    # 4: each session keeps its own length ("Keep me signed in": 14 days, else 12 hours).
    4: ["ALTER TABLE sessions ADD COLUMN ttl_seconds INTEGER NOT NULL DEFAULT 1209600"],
}


def path_for(config: dict, live_dir: Path | None) -> Path | None:
    """`access.accounts`, else accounts.sqlite beside the history."""
    raw = ((config or {}).get("access") or {}).get("accounts")
    if raw:
        return Path(str(raw))
    return Path(live_dir) / "accounts.sqlite" if live_dir is not None else None


def now() -> str:
    """UTC now, ISO seconds: "2026-10-11T14:00:00Z". The one clock."""
    return datetime.now(timezone.utc).strftime(STAMP)


def parse(stamp: str) -> datetime:
    return datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc)


def shift(seconds: float) -> str:
    """now() moved by `seconds` (negative for the past)."""
    return (parse(now()) + timedelta(seconds=seconds)).strftime(STAMP)


def epoch() -> int:
    """now() as Unix seconds, for TOTP."""
    return int(parse(now()).timestamp())


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def connect(path: Path | str) -> sqlite3.Connection:
    """Open (creating or upgrading) the accounts file. The caller closes it."""
    memory = str(path) == ":memory:"
    if not memory:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # Made 0640 before SQLite writes a byte; the WAL files follow its mode.
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
        db.executescript(SCHEMA)
        _upgrade(db)
    except BaseException:
        db.close()
        raise
    return db


def _upgrade(db: sqlite3.Connection) -> None:
    row = db.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    found = int(row[0]) if row else None
    if found is not None and found > SCHEMA_VERSION:
        raise RuntimeError(
            f"accounts file is schema {found}, this code understands "
            f"{SCHEMA_VERSION}; upgrade skald before reading it")
    if found == SCHEMA_VERSION:
        return
    with tx(db):
        for version in range((found or SCHEMA_VERSION) + 1, SCHEMA_VERSION + 1):
            for sql in UPGRADES.get(version, []):
                _apply(db, sql)
        db.execute("INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                   "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                   (str(SCHEMA_VERSION),))


def _apply(db: sqlite3.Connection, sql: str) -> None:
    """One upgrade statement; an ADD COLUMN whose column is there already is skipped."""
    words = sql.split()
    if words[:2] == ["ALTER", "TABLE"] and words[3:5] == ["ADD", "COLUMN"]:
        have = {r[1] for r in db.execute(f"PRAGMA table_info({words[2]})")}
        if words[5] in have:
            return
    db.execute(sql)


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


def _hash_key(db: sqlite3.Connection) -> bytes:
    row = db.execute("SELECT value FROM meta WHERE key = 'hash_key'").fetchone()
    if row is None:
        db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('hash_key', ?)",
                   (secrets.token_hex(32),))
        row = db.execute("SELECT value FROM meta WHERE key = 'hash_key'").fetchone()
    return bytes.fromhex(row[0])


def keyed_hash(db: sqlite3.Connection, value: str) -> str:
    """HMAC-SHA256 of `value` with the install's key: for addresses and limit keys."""
    return hmac.new(_hash_key(db), str(value).encode(), hashlib.sha256).hexdigest()


def one(db: sqlite3.Connection, sql: str, args=()) -> dict | None:
    row = db.execute(sql, args).fetchone()
    return dict(row) if row is not None else None


def rows(db: sqlite3.Connection, sql: str, args=()) -> list[dict]:
    return [dict(r) for r in db.execute(sql, args)]
