"""A lead's name and email kept no longer than the site's People days (after 2.38.0).

A site promises in Settings > Data retention > People how long it keeps what
names a person: `privacy.keep_days` ("Visits with addresses", 395 by
default). Before this, a lead's name and email lived as long as the lead
(`conversions.retention_days`, 400, or for good), so a site that promised 180
days kept emails for 400 days or more. Now each copy of a name or an email
goes once it is older than the People days, when the site set them (a
settings row or config.yml: `windows`) and they are shorter than the lead's
own days (`identity_days`). A site that set none, or whose People days are
not shorter, keeps today's default: the lead's own prune takes them with
the lead.

Where a name or an email is kept, and what goes (per site, a row by its
`at`, a spool line by its day):

    identities   one whose rows (conversions, removed rows) are all older:
                 email and name NULL, email_hash a random "cleared:" value,
                 so the email finds it no more and a new form makes a new one
    split        one with a younger row keeps its email for that row; its
                 older rows move to a new blank identity (no email, no name),
                 so an old lead shows none. An older row within the
                 abandonment window (`gap_hours`) of a kept one stays with it,
                 chained: no started row ever loses the finish that matched it
    removed      the copy of a row a sync took away: its "email" and "name"
                 set to null (and its identity_id moved like its rows)
    spool        a hook line's name and primary email (conversions.IDENTITY,
                 at any depth): the line an anonymous site would have written
    backups      the same in each conversions.sqlite.v<N>.bak a schema
                 upgrade left beside the file

Nothing else changes. No row is deleted and no row changes its day, stage,
visitor ID or the identity it is matched by (only which blank id it is), so
every figure - leads, stages, abandoned starts, revenue - and the second
count (audit_conversions.py, which reads the spool for counts only) stay
the same; tests/test_people_days.py checks both roads before and after.

Runs in the daily prune (cli_conversions.cmd_prune) and once on the first
live run after the upgrade (jobs.live, the meta row MARK), for the rows
already past the promise. Each site's counts go to the run's output, to
privacy.log and to the audit log ("privacy.cleared"): never a value.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from . import IDENTITY, store
from . import spool as spool_mod

MARK = "people_days_swept"          # meta row: the sweep after the upgrade ran
CLEARED = "cleared:"                # email_hash of an identity whose email went
KEYS = ("people", "rows", "removed", "spool", "backups")


def identity_days(people_days: int, lead_days: int) -> int | None:
    """Days a lead's name and email are kept apart from the lead: the People
    days when shorter than the lead's own (0 = for good); None when they are
    not, and the lead's own prune takes them with it (today's default)."""
    people_days = max(1, int(people_days))
    if int(lead_days) == store.FOREVER or people_days < int(lead_days):
        return people_days
    return None


def kept_days(config: dict) -> int:
    """How long this site (`config` as settings_store.apply made it for the
    site) keeps a lead's name and email, as the privacy notice says it: the
    People days when the site set them and they are shorter, else the lead's
    own days (0: for good)."""
    from ..config import setting
    from ..people import policy
    lead = store.keep_days(config)
    if setting(config or {}, "privacy", "keep_days") is None:
        return lead                     # no promise set: today's default
    got = identity_days(policy.keep_days(config), lead)
    return lead if got is None else got


def windows(config: dict, spare=None):
    """site -> its identity_days; None for a site that set no People days
    (its own settings row, else the install's row or config.yml: a promise
    is a value someone set, never the code's 395), whose People days are
    not shorter than its leads' (settings_store.prune_plan), or that keeps
    everything (`spare`, keep_everything.Keeper)."""
    from ..people import policy
    from ..settings_store import promised, prune_plan
    people, own_people = prune_plan(config, "privacy.keep_days", policy.keep_days(config))
    lead, own_lead = prune_plan(config, "conversions.retention_days", store.keep_days(config))
    said = promised(config, "privacy.keep_days")

    def days_of(site: str) -> int | None:
        if site not in own_people and not said:
            return None
        if spare is not None and spare(site):
            return None
        return identity_days(own_people.get(site, people), own_lead.get(site, lead))
    return days_of


def gap_hours(config: dict) -> float:
    """The longest a started row waits for its finish (abandoned starts)."""
    from .from_beacon import abandon_hours
    try:
        return max(float(store.ABANDON_HOURS), float(abandon_hours(config)))
    except (TypeError, ValueError):
        return float(store.ABANDON_HOURS)


def edge(today: date, days: int) -> str:
    """The first moment kept: midnight UTC `days` days before `today` (as
    store.prune cuts)."""
    return store.stamp(datetime.combine(today - timedelta(days=int(days)), time(0),
                                        tzinfo=timezone.utc))


# ------------------------------------------------------------ the store

def clear(db, today: date, days_of, gap: float = store.ABANDON_HOURS) -> dict:
    """Clear the names and emails past each site's days in one conversions
    file (`days_of(site)`: identity_days, None leaves the site as it is).
    {site: {"people", "rows", "removed"}} for the sites with any."""
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not {"identities", "conversions"} <= tables:
        return {}
    has_removed = "removed" in tables
    out: dict = {}
    with store.tx(db):
        sites = {r[0] for r in db.execute("SELECT DISTINCT site FROM identities")}
        if has_removed:
            sites |= {r[0] for r in db.execute("SELECT DISTINCT site FROM removed")}
        for site in sorted(sites):
            days = days_of(site)
            if days is None:
                continue
            cut = edge(today, days)
            got = {"people": 0, "rows": 0, "removed": 0}
            moved = _identities(db, site, cut, gap, has_removed, got)
            if has_removed:
                _removed(db, site, cut, moved, got)
            if any(got.values()):
                out[site] = got
    return out


def _removed_by_identity(db, site: str) -> dict[int, list[tuple[int, str]]]:
    out: dict = {}
    for rid, at, ident in db.execute(
            "SELECT id, at, CAST(json_extract(row, '$.identity_id') AS INTEGER) FROM removed "
            "WHERE site = ? AND json_extract(row, '$.identity_id') IS NOT NULL", (site,)):
        out.setdefault(int(ident), []).append((rid, at or ""))
    return out


def _identities(db, site: str, cut: str, gap: float, has_removed: bool, got: dict) -> dict:
    """Blank or split each identity of `site` with a name or an email.
    {identity id: its blank twin} for the identities split."""
    removed = _removed_by_identity(db, site) if has_removed else {}
    linked: dict = {}                   # one read of the site's rows, not one per identity
    for ident, cid, at in db.execute(
            "SELECT identity_id, id, at FROM conversions WHERE identity_id IN (SELECT id FROM "
            "identities WHERE site = ?) ORDER BY at, id", (site,)):
        linked.setdefault(ident, []).append((cid, at or ""))
    twins: dict = {}
    for ident, created in db.execute(
            "SELECT id, created_at FROM identities WHERE site = ? AND (email IS NOT NULL OR "
            "name IS NOT NULL)", (site,)).fetchall():
        rows = linked.get(ident, [])
        gone = removed.get(ident, [])
        young = any(at >= cut for _, at in rows) or any(at >= cut for _, at in gone)
        if not young:
            if rows or gone or (created or "") < cut:
                db.execute("UPDATE identities SET email = NULL, name = NULL, email_hash = ? "
                           "WHERE id = ?", (_cleared(), ident))
                got["people"] += 1
                got["rows"] += len(rows)
            continue
        old = _detached(rows, cut, gap)
        if not old and not any(at < cut for _, at in gone):
            continue
        twin = db.execute("INSERT INTO identities (site, email_hash, email, name, created_at) "
                          "VALUES (?, ?, NULL, NULL, ?)",
                          (site, _cleared(), store.stamp())).lastrowid
        twins[ident] = twin
        db.executemany("UPDATE conversions SET identity_id = ? WHERE id = ?",
                       [(twin, cid) for cid in old])
        got["rows"] += len(old)
    return twins


def _detached(rows, cut: str, gap: float) -> list[int]:
    """The ids of the older rows (`at` before `cut`) that no younger row is
    chained to: rows sorted by time, each within `gap` hours of the next one
    stays with it. Every row when none is younger."""
    first = next((i for i, (_, at) in enumerate(rows) if at >= cut), None)
    if first is None:
        return [cid for cid, _ in rows]
    j = first - 1
    while j >= 0 and _hours(rows[j][1], rows[j + 1][1]) <= gap:
        j -= 1
    return [cid for cid, _ in rows[:j + 1]]


def _hours(a: str, b: str) -> float:
    try:
        return (store.parse(b) - store.parse(a)).total_seconds() / 3600
    except (TypeError, ValueError):
        return 0.0                      # not a time: kept together, never split


def _removed(db, site: str, cut: str, twins: dict, got: dict) -> None:
    """The removed rows older than `cut`: no email, no name, and the identity
    of a split moved to its twin."""
    for rid, text in db.execute("SELECT id, row FROM removed WHERE site = ? AND at < ?",
                                (site, cut)).fetchall():
        try:
            row = json.loads(text)
        except (TypeError, ValueError):
            continue
        if not isinstance(row, dict):
            continue
        changed = False
        for key in ("email", "name"):
            if row.get(key) is not None:
                row[key] = None
                changed = True
        ident = row.get("identity_id")
        if isinstance(ident, int) and ident in twins:
            row["identity_id"] = twins[ident]
        elif not changed:
            continue
        db.execute("UPDATE removed SET row = ? WHERE id = ?",
                   (json.dumps(row, sort_keys=True), rid))
        got["removed"] += int(changed)


def _cleared() -> str:
    return CLEARED + secrets.token_hex(16)


def backups(path: Path) -> list[Path]:
    """The copies a schema upgrade left beside the file (store._upgrade)."""
    path = Path(path)
    return sorted(path.parent.glob(f"{path.name}.v*.bak"))


def clear_backup(path: Path, today: date, days_of, gap: float) -> dict:
    """`clear` on one upgrade copy, opened as it is (never upgraded)."""
    db = sqlite3.connect(str(path), isolation_level=None, timeout=10)
    try:
        return clear(db, today, days_of, gap)
    finally:
        db.close()


# ------------------------------------------------------------ the spool

def without_identity(value):
    """A copy of a spooled body without the IDENTITY keys, at any depth."""
    if isinstance(value, dict):
        return {k: without_identity(v) for k, v in value.items() if str(k) not in IDENTITY}
    if isinstance(value, list):
        return [without_identity(v) for v in value]
    return value


def clear_spool(spool: Path, today: date, days_of) -> dict[str, int]:
    """Drop the name and email from every spool line older than its site's
    days; the rest of each line as it was. {site: lines changed}."""
    out: dict[str, int] = {}
    known: dict = {}

    def days(site):
        if site not in known:
            known[site] = days_of(site) if isinstance(site, str) else None
        return known[site]

    for day in spool_mod.days(spool):
        path = spool_mod.day_file(spool, day)
        lines, changed = [], 0
        with open(path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                lines.append(raw)
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                n = days(row.get("site"))
                if n is None or not day < today - timedelta(days=n):
                    continue
                body = without_identity(row.get("body"))
                if body == row.get("body"):
                    continue
                row["body"] = body
                lines[-1] = json.dumps(row, separators=(",", ":"), sort_keys=True) + \
                    ("\n" if raw.endswith("\n") else "")
                changed += 1
                out[row["site"]] = out.get(row["site"], 0) + 1
        if changed:
            spool_mod._rewrite(path, "".join(lines))
    return out


# ------------------------------------------------------------ the steps

def run(ctx, today: date | None = None) -> dict:
    """Every place of this install's conversions file (and its spool and
    upgrade copies): {site: {"days", "people", "rows", "removed", "spool",
    "backups"}} for the sites with anything cleared. Marks the sweep done."""
    from ..keep_everything import of
    spare = of(ctx)
    if spare.all:                     # the install keeps everything: nothing is opened
        return {}
    folder = Path(ctx.db_path).parent
    path = store.path_for(ctx.config, folder)
    days_of = windows(ctx.config, spare)
    gap = gap_hours(ctx.config)
    today = today or ctx.now.date()
    out: dict = {}

    def add(site: str, key: str, n: int) -> None:
        if n:
            got = out.setdefault(site, {"days": days_of(site), **{k: 0 for k in KEYS}})
            got[key] += n

    if path is not None and Path(path).exists():
        db = store.connect(path)
        try:
            for site, got in clear(db, today, days_of, gap).items():
                for key, n in got.items():
                    add(site, key, n)
            db.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO "
                       "UPDATE SET value = excluded.value", (MARK, store.stamp()))
        finally:
            db.close()
        for bak in backups(path):
            try:
                for site, got in clear_backup(bak, today, days_of, gap).items():
                    add(site, "backups", sum(got.values()))
            except sqlite3.Error as why:
                ctx.err(f"people days: {bak.name}: {type(why).__name__}: {why}")
    spool = spool_mod.spool_dir(ctx.config, folder)
    if Path(spool).is_dir():
        for site, n in clear_spool(spool, today, days_of).items():
            add(site, "spool", n)
    note(ctx, out)
    return out


def swept(ctx) -> bool:
    """Whether the sweep has run on this install's conversions file (or there
    is none to sweep)."""
    path = store.path_for(ctx.config, Path(ctx.db_path).parent)
    if path is None or not Path(path).exists():
        return True
    db = store.connect(path)
    try:
        return db.execute("SELECT 1 FROM meta WHERE key = ?", (MARK,)).fetchone() is not None
    finally:
        db.close()


def once(ctx) -> dict | None:
    """The first live run after the upgrade: the rows already past their
    site's days, at once rather than at the next daily run."""
    if swept(ctx):
        return None
    return run(ctx)


def words(site: str, got: dict) -> str:
    """One line of counts: never a value."""
    return (f"{site}: names and emails older than {got['days']} days cleared: "
            f"{got['people']} people, {got['rows']} lead row(s), {got['removed']} removed "
            f"row(s), {got['spool']} hook line(s), {got['backups']} in upgrade copies")


def note(ctx, out: dict) -> None:
    """The run's output, privacy.log and the audit log: counts only."""
    if not out:
        return
    from ..privacy import LOG
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = []
    for site, got in sorted(out.items()):
        ctx.out(f"people days: {words(site, got)}")
        lines.append(f"{now} people-days site={site} days={got['days']} "
                     + " ".join(f"{k}={got[k]}" for k in KEYS) + "\n")
    live_dir = getattr(ctx, "live_dir", None)
    if live_dir is not None:
        try:
            import os
            log = Path(live_dir) / LOG
            with open(log, "a", encoding="utf-8") as handle:
                handle.write("".join(lines))
            os.chmod(log, 0o640)
        except OSError as why:
            ctx.err(f"people days: privacy.log: {why}")
    _audit(ctx, out)


def _audit(ctx, out: dict) -> None:
    """One audit row per site, in its organisation's log (Settings > Audit)."""
    try:
        from ..accounts import auditlog, connect
        from ..settings_store import _org_of, accounts_file
        path = accounts_file(ctx.config, getattr(ctx, "live_dir", None))
        if path is None:
            return
        db = connect(path)
        try:
            for site, got in sorted(out.items()):
                auditlog.record(db, _org_of(db, site), "skald", "privacy.cleared", site,
                                words(site, got).split(": ", 1)[1])
        finally:
            db.close()
    except Exception as why:            # noqa: BLE001 - bookkeeping never stops a run
        ctx.err(f"people days: audit log: {type(why).__name__}: {why}")
