"""Recorded journeys' tables, in conversions.sqlite beside the leads.

    recorded_events      one row per accepted event: `raw` is the event as kept (the
                         site's privacy settings applied at the door, receive.py), its
                         columns a projection of it (COLUMNS) that the second count
                         (audit_journeys.py) checks against the raw JSON
    recorded_tombstones  a withdrawn visitor: a keyed digest of its ID (never the ID)
                         and when the refusal of its late retries ends
    recorded_log         per site and day, how many events were withdrawn, refused for
                         consent or ignored for a withdrawn visitor: counts only

Never mixed into the log's figures: nothing else reads these tables. Retention
(`prune`, the daily run): an event goes after the site's visitor-page days
(`journeys.vid_days`), and its address and email after the People days
(`privacy.keep_days`) when those are shorter. A site that keeps everything
(keep_everything.py) loses nothing. A withdrawal is the person's own deletion: it
deletes on every site, like `skald forget`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import date, datetime, time, timedelta, timezone

from ..conversions import store as cstore
from . import COLUMNS, TOMBSTONE_DAYS

SCHEMA = """
CREATE TABLE IF NOT EXISTS recorded_events (
  site TEXT NOT NULL, event_id TEXT NOT NULL, event_name TEXT NOT NULL,
  occurred_at TEXT NOT NULL, received_at TEXT NOT NULL, visitor_id TEXT NOT NULL,
  session_id TEXT NOT NULL, ref TEXT NOT NULL, path TEXT NOT NULL, skald_vid TEXT,
  ip TEXT, email TEXT, raw TEXT NOT NULL, PRIMARY KEY (site, event_id));
CREATE INDEX IF NOT EXISTS recorded_events_at ON recorded_events (site, occurred_at);
CREATE INDEX IF NOT EXISTS recorded_events_ref ON recorded_events (site, ref);
CREATE INDEX IF NOT EXISTS recorded_events_visitor ON recorded_events (site, visitor_id);
CREATE TABLE IF NOT EXISTS recorded_tombstones (
  site TEXT NOT NULL, digest TEXT NOT NULL, expires_at TEXT NOT NULL,
  PRIMARY KEY (site, digest));
CREATE TABLE IF NOT EXISTS recorded_log (
  site TEXT NOT NULL, day TEXT NOT NULL, what TEXT NOT NULL, n INTEGER NOT NULL,
  PRIMARY KEY (site, day, what));
"""
LOGGED = ("withdrawn", "refused_consent", "ignored_withdrawn")


class Conflict(ValueError):
    """The same event ID came again with another body."""


def connect(path):
    """conversions.sqlite, opened (cstore.connect: made or upgraded) with these tables."""
    db = cstore.connect(path)
    try:
        if not present(db):
            db.executescript(SCHEMA)
    except BaseException:
        db.close()
        raise
    return db


def present(db) -> bool:
    got = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                     "AND name LIKE 'recorded_%'")}
    return {"recorded_events", "recorded_tombstones", "recorded_log"} <= got


def encoded(event: dict) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def ref_of(site: str, session_id: str) -> str:
    """The session's opaque id for the address and the API: s and 12 hex."""
    return "s" + hashlib.sha256(f"{site}\0{session_id}".encode()).hexdigest()[:12]


def digest(db, site: str, visitor_id: str) -> str:
    """A withdrawn visitor's tombstone: HMAC-SHA256 with this file's own key."""
    row = db.execute("SELECT value FROM meta WHERE key = 'recorded_hash_key'").fetchone()
    if row is None:
        db.execute("INSERT OR IGNORE INTO meta (key, value) VALUES ('recorded_hash_key', ?)",
                   (secrets.token_hex(32),))
        row = db.execute("SELECT value FROM meta WHERE key = 'recorded_hash_key'").fetchone()
    return hmac.new(row[0].encode(), f"{site}\0{visitor_id}".encode(), hashlib.sha256).hexdigest()


def tombstoned(db, site: str, visitor_id: str, at: datetime) -> bool:
    return db.execute("SELECT 1 FROM recorded_tombstones WHERE site = ? AND digest = ? AND "
                      "expires_at > ?", (site, digest(db, site, visitor_id),
                                         cstore.stamp(at))).fetchone() is not None


def log(db, site: str, at: datetime, what: str, n: int = 1) -> None:
    if what not in LOGGED or n <= 0:
        return
    day = at.astimezone(timezone.utc).date().isoformat()
    db.execute("INSERT INTO recorded_log (site, day, what, n) VALUES (?, ?, ?, ?) "
               "ON CONFLICT(site, day, what) DO UPDATE SET n = n + excluded.n",
               (site, day, what, int(n)))


def record(db, site: str, event: dict, received_at: datetime) -> str:
    """Keep one validated event: "created", "duplicate" (the same body again) or
    "withdrawn" (its visitor withdrew: nothing kept, counted). Conflict when its ID
    came before with another body."""
    raw = encoded(event)
    with cstore.tx(db):
        if tombstoned(db, site, event["visitor_id"], received_at):
            log(db, site, received_at, "ignored_withdrawn")
            return "withdrawn"
        prior = db.execute("SELECT raw FROM recorded_events WHERE site = ? AND event_id = ?",
                           (site, event["event_id"])).fetchone()
        if prior is not None:
            if prior[0] != raw:
                raise Conflict("the event ID came before with another body")
            return "duplicate"
        db.execute("INSERT INTO recorded_events (site, event_id, event_name, occurred_at, "
                   "received_at, visitor_id, session_id, ref, path, skald_vid, ip, email, raw) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (site, event["event_id"], event["event_name"], event["occurred_at"],
                    cstore.stamp(received_at), event["visitor_id"], event["session_id"],
                    ref_of(site, event["session_id"]), event["path"], event.get("skald_vid"),
                    event.get("ip"), event.get("email"), raw))
    return "created"


def withdraw(db, site: str, visitor_id: str, at: datetime) -> int:
    """Delete every event of the visitor on this site only (consent is given per site,
    so it is withdrawn per site), and refuse its late retries here for TOMBSTONE_DAYS.
    How many events went."""
    with cstore.tx(db):
        key = digest(db, site, visitor_id)
        until = cstore.stamp(at + timedelta(days=TOMBSTONE_DAYS))
        db.execute("INSERT INTO recorded_tombstones (site, digest, expires_at) VALUES (?, ?, ?) "
                   "ON CONFLICT(site, digest) DO UPDATE SET expires_at = "
                   "MAX(expires_at, excluded.expires_at)", (site, key, until))
        gone = db.execute("DELETE FROM recorded_events WHERE site = ? AND visitor_id = ?",
                          (site, visitor_id)).rowcount
        log(db, site, at, "withdrawn", gone)
    return gone


def forget(db, site: str | None = None, ip=(), email: str | None = None, vids=(),
           dry_run: bool = False) -> int:
    """A person's deletion request (`skald forget`): every recorded event kept with one of
    those addresses (the full and the shortened form), that email or one of those script
    tag visitor IDs; their whole sessions go, so nothing of them is left half. The count of
    events, or what would go (each event once)."""
    if not present(db):
        return 0
    want = [("ip", v) for v in ip or () if v] + [("skald_vid", v.strip()) for v in vids or () if v]
    if email:
        want.append(("email", email.strip().lower()))
    if not want:
        return 0
    where = " OR ".join(f"{col} = ?" for col, _ in want)
    args = [v for _, v in want]
    scope = " AND site = ?" if site else ""
    refs = db.execute(f"SELECT DISTINCT site, ref FROM recorded_events WHERE ({where}){scope}",
                      args + ([site] if site else [])).fetchall()
    n = 0
    for s, ref in refs:
        n += db.execute("SELECT COUNT(*) FROM recorded_events WHERE site = ? AND ref = ?",
                        (s, ref)).fetchone()[0]
        if not dry_run:
            db.execute("DELETE FROM recorded_events WHERE site = ? AND ref = ?", (s, ref))
    if not dry_run:
        db.commit()
    return n


def last_received(db, site: str) -> str | None:
    if not present(db):
        return None
    row = db.execute("SELECT MAX(received_at) FROM recorded_events WHERE site = ?",
                     (site,)).fetchone()
    return row[0] if row else None


def counts(db, site: str, since: str) -> dict:
    """{what: n} of recorded_log since a day (YYYY-MM-DD)."""
    if not present(db):
        return {}
    return {r[0]: int(r[1]) for r in db.execute(
        "SELECT what, SUM(n) FROM recorded_log WHERE site = ? AND day >= ? GROUP BY what",
        (site, since))}


# ------------------------------------------------------------------- retention

def _edge(today: date, days: int) -> str:
    return cstore.stamp(datetime.combine(today - timedelta(days=int(days)), time(0),
                                         tzinfo=timezone.utc))


def without_person(raw: str) -> str:
    event = json.loads(raw)
    event.pop("ip", None)
    event.pop("email", None)
    return encoded(event)


def prune(db, today: date, vid_days: int, own_vid: dict | None = None,
          people_days: int | None = None, own_people: dict | None = None,
          spare=None) -> dict:
    """Retention for every site with recorded events: {"events", "cleared"}.
    `vid_days` / `own_vid`: journeys.vid_days, every site's and each site's own;
    `people_days` / `own_people`: privacy.keep_days the same way; `spare(site)`
    True: the site keeps everything (keep_everything.Keeper), nothing goes."""
    if not present(db):
        return {"events": 0, "cleared": 0, "tombstones": 0}
    own_vid, own_people = own_vid or {}, own_people or {}
    spare = spare or (lambda site: False)
    gone = cleared = 0
    with cstore.tx(db):
        sites = [r[0] for r in db.execute("SELECT DISTINCT site FROM recorded_events")]
        for site in sorted(sites):
            if spare(site):
                continue
            keep = max(1, int(own_vid.get(site, vid_days)))
            gone += db.execute("DELETE FROM recorded_events WHERE site = ? AND occurred_at < ?",
                               (site, _edge(today, keep))).rowcount
            people = own_people.get(site, people_days)
            if people is None or int(people) >= keep:
                continue
            for row in db.execute("SELECT event_id, raw FROM recorded_events WHERE site = ? AND "
                                  "occurred_at < ? AND (ip IS NOT NULL OR email IS NOT NULL)",
                                  (site, _edge(today, max(1, int(people))))).fetchall():
                db.execute("UPDATE recorded_events SET ip = NULL, email = NULL, raw = ? "
                           "WHERE site = ? AND event_id = ?",
                           (without_person(row[1]), site, row[0]))
                cleared += 1
        # A tombstone holds no data about anyone: it only stops refusing once it ends.
        stones = db.execute("DELETE FROM recorded_tombstones WHERE expires_at <= ?",
                            (cstore.stamp(datetime.combine(today, time(0), tzinfo=timezone.utc)),)
                            ).rowcount
    return {"events": gone, "cleared": cleared, "tombstones": stones}


def run_prune(ctx, folder, today: date) -> dict:
    """The daily run's step (cli_conversions.cmd_prune): each site by its own days."""
    from ..keep_everything import of
    from ..people.policy import keep_days
    from ..settings_store import prune_plan
    path = cstore.path_for(ctx.config, folder)
    if path is None or not path.exists():
        return {"events": 0, "cleared": 0, "tombstones": 0}
    vid_days, own_vid = prune_plan(ctx.config, "journeys.vid_days", cstore.vid_days(ctx.config))
    people, own_people = prune_plan(ctx.config, "privacy.keep_days", keep_days(ctx.config))
    db = cstore.connect(path)
    try:
        return prune(db, today, vid_days, own_vid, people, own_people, of(ctx))
    finally:
        db.close()

