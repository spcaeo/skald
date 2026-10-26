"""The addresses behind Security's suspect rows, kept like the visits are.

History's day kind `security` (security.py) holds no address: each suspect row
(scanner, attacker, fake browser) carries only a sequence number. This module
keeps the address and user agent behind each number in conversions.sqlite,
tables `security_rows` and `security_days` (conversions/store.py, schema 8),
under the same rules as the visits kept with an address (people/visits.py):

    written    the daily run, for each stored day (state "whole"), and every
               live run, for today so far (state "today", replaced each time)
    when       only while the site keeps addresses (privacy.keep_ips) and the
               day is inside privacy.keep_days
    shortened  with privacy.keep_ips "short" (policy.shorten): the dashboard
               then shows networks, never an address
    forgotten  an address on the forgotten list is "(removed)", no agent
    pruned     with the kept visits: older than keep_days, every row of a site
               that stopped keeping addresses, full ones shortened
    deleted    `skald forget --ip` deletes the address's rows

Who may read them: owners and admins only, through the helper's
`people/security` (people/api.py), each read written to the audit log. The
second count is audit_security.py (each kept row against its own ranking).
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .conversions import store
from .people import policy

REMOVED = "(removed)"
MAX_DAYS = 400


def rows(site: str, day: str, kept: list, hidden=None, keep=str) -> list[tuple]:
    out = []
    for seq, address, agent in kept:
        ip = str(address or "")
        gone = not ip or (hidden is not None and hidden(ip))
        out.append((site, day, int(seq), REMOVED if gone else keep(ip)[:64],
                    None if gone else (str(agent or "")[:400] or None)))
    return out


def write(db, site: str, day: str, kept: list, state: str, hidden=None, keep=str,
          now: datetime | None = None) -> int:
    got = rows(site, day, kept, hidden, keep)
    with store.tx(db):
        db.execute("DELETE FROM security_rows WHERE site = ? AND day = ?", (site, day))
        db.executemany("INSERT INTO security_rows (site, day, seq, ip, user_agent) "
                       "VALUES (?, ?, ?, ?, ?)", got)
        db.execute("INSERT INTO security_days (site, day, state, rows, written_at) "
                   "VALUES (?, ?, ?, ?, ?) ON CONFLICT(site, day) DO UPDATE SET "
                   "state = excluded.state, rows = excluded.rows, "
                   "written_at = excluded.written_at",
                   (site, day, state, len(got), store.stamp(now)))
    return len(got)


def record(config: dict, folder, site: str, day: date, totals, state: str = "whole",
           today: date | None = None, hidden=None) -> int | None:
    """Keep the day's suspect addresses when the site keeps addresses; None when
    it does not, the day is past keep_days, or the day kind was not counted."""
    keep = policy.kept_ip(config, folder) if folder is not None else None
    kept = getattr(totals, "security_kept", None)
    if keep is None or kept is None:
        return None
    today = today or date.today()
    if day < today - timedelta(days=policy.keep_days(config)):
        return None
    if hidden is None:
        from .privacy import forgotten
        hidden = forgotten(Path(folder))
    db = store.connect(store.path_for(config, folder))
    try:
        return write(db, site, day.isoformat(), kept, state, hidden, keep)
    finally:
        db.close()


def keep_day(ctx, day: date, totals) -> None:
    """run-daily / collect / backfill: a stored day's rows (whole). Never stops the run."""
    try:
        record(ctx.config, Path(ctx.db_path).parent, ctx.site, day, totals, "whole",
               ctx.now.date())
    except (OSError, sqlite3.Error, RuntimeError) as why:
        ctx.err(f"{day}: scanner addresses not kept: {type(why).__name__}: {why}")


def keep_live(config: dict, db_path, site: str, day: date, totals) -> None:
    """Every live run: today's rows so far (state "today"). Never raises."""
    import sys
    if db_path is None:
        return
    try:
        record(config, Path(db_path).parent, site, day, totals, "today", day)
    except (OSError, sqlite3.Error, RuntimeError) as why:
        print(f"live: scanner addresses not kept: {type(why).__name__}: {why}",
              file=sys.stderr)


def prune(db, today: date, keep: int, own: dict | None = None, off: tuple = (),
          short: tuple = (), spare=None) -> int:
    """Rows older than `keep` days (a site in `own` by its own), every row of a
    site in `off`; the full addresses of a site in `short` shortened. A site
    `spare` names (keep_everything) loses and changes nothing."""
    gone = 0
    own = own or {}
    spare = spare or (lambda site: False)
    off = tuple(s for s in off if not spare(s))
    short = tuple(s for s in short if not spare(s))
    with store.tx(db):
        for site in short:
            for (ip,) in db.execute("SELECT DISTINCT ip FROM security_rows WHERE site = ?",
                                    (site,)).fetchall():
                cut = policy.shorten(ip)
                if cut != ip:
                    db.execute("UPDATE security_rows SET ip = ? WHERE site = ? AND ip = ?",
                               (cut, site, ip))
        for site in off:
            gone += db.execute("DELETE FROM security_rows WHERE site = ?", (site,)).rowcount
            db.execute("DELETE FROM security_days WHERE site = ?", (site,))
        for (site,) in db.execute("SELECT DISTINCT site FROM security_days").fetchall():
            if spare(site):
                continue
            edge = (today - timedelta(days=int(own.get(site, keep)))).isoformat()
            gone += db.execute("DELETE FROM security_rows WHERE site = ? AND day < ?",
                               (site, edge)).rowcount
            db.execute("DELETE FROM security_days WHERE site = ? AND day < ?", (site, edge))
    return gone


def forget_ip(db, ip: str, dry_run: bool = False, short_sites: tuple = ()) -> int:
    """Delete every kept row of `ip` (and, on a site that shortens, of its
    shortened form). Rows deleted (or found)."""
    where, args = "ip = ?", [ip]
    cut = policy.shorten(ip)
    if short_sites and cut != ip:
        where += f" OR (ip = ? AND site IN ({','.join('?' * len(short_sites))}))"
        args += [cut, *short_sites]
    try:
        n = db.execute(f"SELECT COUNT(*) FROM security_rows WHERE {where}", args).fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    if n and not dry_run:
        with store.tx(db):
            db.execute(f"DELETE FROM security_rows WHERE {where}", args)
    return int(n)


def listing(config: dict, folder, site: str, first: date, last: date) -> dict:
    """people/security: the addresses behind the period's rows, for an owner
    or admin. {ok, mode, rows: [{day, seq, ip, user_agent}], kept_from}."""
    mode = policy.ip_mode(config, folder)
    out = {"ok": True, "mode": mode, "keep_days": policy.keep_days(config), "rows": [],
           "kept_from": None, "days": []}
    if mode == policy.OFF:
        return out
    path = store.path_for(config, folder) if folder is not None else None
    if path is None or not Path(path).is_file():
        return out
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    try:
        try:
            got = db.execute("SELECT day, seq, ip, user_agent FROM security_rows WHERE "
                             "site = ? AND day >= ? AND day <= ? ORDER BY day, seq",
                             (site, first.isoformat(), last.isoformat())).fetchall()
            days = db.execute("SELECT day, state FROM security_days WHERE site = ? AND "
                              "day >= ? AND day <= ? ORDER BY day",
                              (site, first.isoformat(), last.isoformat())).fetchall()
            low = db.execute("SELECT MIN(day) FROM security_days WHERE site = ?",
                             (site,)).fetchone()
        except sqlite3.OperationalError:
            return out
    finally:
        db.close()
    out["rows"] = [{"day": d, "seq": s, "ip": ip, "user_agent": ua} for d, s, ip, ua in got]
    out["days"] = [{"day": d, "state": st} for d, st in days]
    out["kept_from"] = low[0] if low else None
    return out


def span(first: str, last: str, today: date) -> tuple[date, date]:
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    if b < a or b > today or (b - a).days > MAX_DAYS:
        raise ValueError(f"first and last are days, first <= last <= today, at most "
                         f"{MAX_DAYS} days apart")
    return a, b


def prune_kept(ctx) -> int | None:
    """The nightly prune (cli.prune_kept), with the visits' own plan."""
    from .settings_store import prune_plan
    folder = Path(ctx.db_path).parent
    path = store.path_for(ctx.config, folder)
    if path is None or not Path(path).is_file():
        return None
    keep, own = prune_plan(ctx.config, "privacy.keep_days", policy.keep_days(ctx.config))
    mode = policy.ip_mode(ctx.config, folder)
    from .keep_everything import of
    db = store.connect(path)
    try:
        return prune(db, ctx.now.date(), keep, own,
                     (ctx.site,) if mode == policy.OFF else (),
                     (ctx.site,) if mode == policy.SHORT else (), of(ctx))
    finally:
        db.close()
