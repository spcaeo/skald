"""Each reader's visit with its address, kept so a person can be followed.

One row per visit that read a page - exactly the journeys (visits.Journeys),
so a day's rows are its readers - with what the journey holds (start, end,
source, via, referrer, campaign, landing, exit, country, device, browser,
system, city when a city file named one (logs.city_db), pages in order with
their seconds) and what it does not: the
address, the user agent and the times of the visit's POSTs (a form sent).
In conversions.sqlite, tables `visits` and `visit_days` (store.PEOPLE_TABLES).

    written    the daily run, for each stored day (state "whole"), and every
               live run, for today so far (state "today", replaced each time)
    when       only while the site keeps addresses (policy.keep_ips) and the
               day is inside privacy.keep_days (395)
    shortened  with privacy.keep_ips "short" the address is kept shortened
               (policy.shorten: 203.0.113.57 as 203.0.113.0); the country
               and city were looked up from the full one before. Rows kept
               in full before the switch are shortened at the next nightly
               run (prune_kept)
    forgotten  an address on the forgotten list (privacy.py) is written as
               "(removed)", without user agent or referrer: the visit still
               counts, its person does not show
    pruned     each night, rows older than the site's keep_days; every row of
               a site that no longer keeps addresses
    deleted    `skald forget --ip` (privacy.py) deletes the address's rows,
               and on a site that shortens, the rows of its shortened form

The second count is audit_people.py: from the raw log, by its own road, the
readers and page views per address of each whole day, against these rows.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..conversions import store
from . import policy

REMOVED = "(removed)"
TRAIL = 50
FIELDS = ("source", "via", "campaign", "landing", "exit", "country", "device", "browser",
          "os", "city")


def path_for(config: dict, folder) -> Path | None:
    return store.path_for(config, folder)


def _stamp(when) -> str | None:
    if not isinstance(when, datetime):
        return None
    return store.stamp(when if when.tzinfo else when.replace(tzinfo=timezone.utc))


def rows(site: str, day: str, journeys: list, people: list, hidden=None,
         kept=str) -> list[tuple]:
    """The table's rows for one day: one per journey, with who it was.
    `kept` turns the full address into what is kept (policy.kept_ip); the
    forgotten list is asked about the full address, before."""
    out = []
    for seq, (j, who) in enumerate(zip(journeys, people)):
        who = who or {}
        ip = str(who.get("ip") or "")
        gone = not ip or (hidden is not None and hidden(ip))
        ip = ip if gone else kept(ip)
        offsets = list(j.get("at") or [])
        trail = [[p, how, offsets[i] if i < len(offsets) else None]
                 for i, (p, how) in enumerate((j.get("trail") or [])[:TRAIL])]
        out.append((
            site, day, seq, REMOVED if gone else ip[:64],
            None if gone else (str(who.get("user_agent") or "")[:400] or None),
            _stamp(who.get("first")) or "", _stamp(who.get("last")) or "",
            *[(str(j.get(f)) if j.get(f) not in (None, "") else None) for f in FIELDS[:2]],
            None if gone else (str(who.get("referrer") or "")[:300] or None),
            *[(str(j.get(f)) if j.get(f) not in (None, "") else None) for f in FIELDS[2:]],
            int(j.get("pages") or 0), j.get("seconds"),
            json.dumps(trail, separators=(",", ":")),
            json.dumps([_stamp(t) for t in (who.get("posts") or [])][:20],
                       separators=(",", ":"))))
    return out


COLUMNS = ("site, day, seq, ip, user_agent, start, end, source, via, referrer, campaign, "
           "landing, exit, country, device, browser, os, city, pages, seconds, trail, posts")


def write(db, site: str, day: str, journeys: list, people: list, state: str,
          hidden=None, now: datetime | None = None, kept=str) -> tuple[int, int]:
    """Replace a day's visits of `site`; (visits, pages) written."""
    got = rows(site, day, journeys, people, hidden, kept)
    with store.tx(db):
        db.execute("DELETE FROM visits WHERE site = ? AND day = ?", (site, day))
        db.executemany(f"INSERT INTO visits ({COLUMNS}) VALUES "
                       f"({', '.join('?' * len(COLUMNS.split(', ')))})", got)
        pages = sum(r[COLUMNS.split(", ").index("pages")] for r in got)
        db.execute("INSERT INTO visit_days (site, day, state, visits, pages, written_at) "
                   "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(site, day) DO UPDATE SET "
                   "state = excluded.state, visits = excluded.visits, pages = excluded.pages, "
                   "written_at = excluded.written_at",
                   (site, day, state, len(got), pages, store.stamp(now)))
    return len(got), pages


def record(config: dict, folder, site: str, day: date, totals, state: str = "whole",
           today: date | None = None, hidden=None) -> tuple[int, int] | None:
    """Keep `totals`' visits for `day` when the site keeps addresses; None
    when it does not, the day is past keep_days, or no visit was counted."""
    kept = policy.kept_ip(config, folder) if folder is not None else None
    if kept is None:
        return None
    journeys, people = getattr(totals, "journeys", None), getattr(totals, "people", None)
    if journeys is None or people is None or len(journeys) != len(people):
        return None
    today = today or date.today()
    if day < today - timedelta(days=policy.keep_days(config)):
        return None
    if hidden is None:
        from ..privacy import forgotten
        hidden = forgotten(Path(folder))
    db = store.connect(path_for(config, folder))
    try:
        return write(db, site, day.isoformat(), journeys, people, state, hidden, kept=kept)
    finally:
        db.close()


def keep_day(ctx, day: date, totals) -> None:
    """run-daily / collect / backfill: keep a stored day's visits (whole).
    A failure is said, never stops the run: the day's figures are stored."""
    import sqlite3
    try:
        record(ctx.config, Path(ctx.db_path).parent, ctx.site, day, totals, "whole",
               ctx.now.date())
    except (OSError, sqlite3.Error, RuntimeError) as why:
        ctx.err(f"{day}: visits with addresses not kept: {type(why).__name__}: {why}")
    from ..security_kept import keep_day as keep_scanners   # Security's addresses (2.21)
    keep_scanners(ctx, day, totals)


def keep_live(config: dict, db_path, site: str, day: date, totals) -> None:
    """Every live run: today's visits so far (state "today"). Never raises."""
    import sqlite3
    import sys
    if db_path is None:
        return
    try:
        record(config, Path(db_path).parent, site, day, totals, "today", day)
    except (OSError, sqlite3.Error, RuntimeError) as why:
        print(f"live: visits with addresses not kept: {type(why).__name__}: {why}",
              file=sys.stderr)
    from ..security_kept import keep_live as keep_scanners  # Security's addresses (2.21)
    keep_scanners(config, db_path, site, day, totals)


def shorten_kept(db, site: str) -> int:
    """Shorten every address of `site` still kept in full (a site switched
    from full to short; policy.shorten). Rows changed."""
    changed = 0
    found = [r[0] for r in db.execute("SELECT DISTINCT ip FROM visits WHERE site = ?", (site,))]
    with store.tx(db):
        for ip in found:
            short = policy.shorten(ip)
            if short != ip:
                changed += db.execute("UPDATE visits SET ip = ? WHERE site = ? AND ip = ?",
                                      (short, site, ip)).rowcount
    return changed


def prune(db, today: date, keep: int, own: dict | None = None,
          off: tuple = (), short: tuple = ()) -> int:
    """Delete visits older than `keep` days (a site in `own` by its own
    days), and every visit of a site in `off` (it no longer keeps
    addresses); shorten the full addresses of a site in `short`. Rows
    deleted."""
    gone = 0
    own = own or {}
    for site in short:
        shorten_kept(db, site)
    with store.tx(db):
        for site in off:
            gone += db.execute("DELETE FROM visits WHERE site = ?", (site,)).rowcount
            db.execute("DELETE FROM visit_days WHERE site = ?", (site,))
        sites = [r[0] for r in db.execute("SELECT DISTINCT site FROM visit_days")]
        for site in sites:
            cut = (today - timedelta(days=int(own.get(site, keep)))).isoformat()
            gone += db.execute("DELETE FROM visits WHERE site = ? AND day < ?",
                               (site, cut)).rowcount
            db.execute("DELETE FROM visit_days WHERE site = ? AND day < ?", (site, cut))
    return gone


def prune_kept(ctx) -> int | None:
    """The nightly prune (cli.prune_kept): privacy.keep_days per site, a
    site that turned privacy.keep_ips off loses its rows, and one that
    turned it to short has its full addresses shortened."""
    from ..settings_store import prune_plan
    folder = Path(ctx.db_path).parent
    path = path_for(ctx.config, folder)
    if path is None or not Path(path).is_file():
        return None
    keep, own = prune_plan(ctx.config, "privacy.keep_days", policy.keep_days(ctx.config))
    mode = policy.ip_mode(ctx.config, folder)
    off = (ctx.site,) if mode == policy.OFF else ()
    short = (ctx.site,) if mode == policy.SHORT else ()
    db = store.connect(path)
    try:
        gone = prune(db, ctx.now.date(), keep, own, off, short)
    finally:
        db.close()
    from ..security_kept import prune_kept as prune_scanners  # the same days (2.21)
    try:
        prune_scanners(ctx)
    except (OSError, sqlite3.Error, RuntimeError) as why:
        ctx.err(f"security prune: {type(why).__name__}: {why}")
    return gone


def preview(config: dict, folder, site: str, cutoff: str) -> tuple:
    """(rows, days, first, last) a smaller privacy.keep_days would remove."""
    import sqlite3
    path = path_for(config, folder) if folder is not None else None
    if path is None or not Path(path).is_file():
        return 0, 0, None, None
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    try:
        row = db.execute("SELECT COUNT(*), COUNT(DISTINCT day), MIN(day), MAX(day) FROM visits "
                         "WHERE site = ? AND day < ?", (site, cutoff)).fetchone()
    except sqlite3.Error:
        return 0, 0, None, None
    finally:
        db.close()
    return int(row[0] or 0), int(row[1] or 0), row[2], row[3]


def forget_ip(db, ip: str, dry_run: bool = False, short_sites: tuple = ()) -> int:
    """Delete every visit of `ip` (every site), and on each site in
    `short_sites` (it keeps addresses shortened) every visit of the
    shortened address too: those rows may be other people's as well, and
    cannot be told apart. Rows deleted (or found)."""
    where, args = "ip = ?", [ip]
    short = policy.shorten(ip)
    if short_sites and short != ip:
        where += f" OR (ip = ? AND site IN ({','.join('?' * len(short_sites))}))"
        args += [short, *short_sites]
    n = db.execute(f"SELECT COUNT(*) FROM visits WHERE {where}", args).fetchone()[0]
    if n and not dry_run:
        with store.tx(db):
            db.execute(f"DELETE FROM visits WHERE {where}", args)
    return int(n)


def of_ip(db, site: str, ip: str, limit: int = 2000, short: bool = False) -> list[dict]:
    """Every kept visit of an address, newest first; with `short`, the
    visits kept under its shortened form too."""
    forms = sorted({ip, policy.shorten(ip)}) if short else [ip]
    return [_row(r) for r in db.execute(
        f"SELECT * FROM visits WHERE site = ? AND ip IN ({','.join('?' * len(forms))}) "
        f"ORDER BY start DESC LIMIT ?", (site, *forms, limit))]


def posted_near(db, site: str, at: str, before: int = 120, after: int = 30) -> list[dict]:
    """Visits that sent a POST from `before` seconds before `at` to `after`
    after it: the visits that may have sent a lead's form. Matched by time,
    never certain: the page says so."""
    when = store.parse(at)
    lo = store.stamp(when - timedelta(seconds=before))
    hi = store.stamp(when + timedelta(seconds=after))
    out = []
    for r in db.execute("SELECT * FROM visits WHERE site = ? AND start <= ? AND end >= ? AND "
                        "posts IS NOT NULL AND posts <> '[]' ORDER BY start",
                        (site, hi, lo)):
        row = _row(r)
        if any(t and lo <= t <= hi for t in row["posts"]):
            out.append(row)
    return out


def _row(r) -> dict:
    row = dict(r)
    for key in ("trail", "posts"):
        try:
            row[key] = json.loads(row.get(key) or "[]")
        except ValueError:
            row[key] = []
    return row
