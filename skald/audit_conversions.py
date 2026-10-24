"""The second count of conversions: straight from the hook spool.

The main road is hooks.py -> adapters/ -> normalise.py -> conversions.sqlite.
This road reads the spool files (<history folder>/hooks/<day>.jsonl) with
its own line parsing, its own reading of each tool's body, its own time
parser, its own de-duplication on (site, tool, external ref, stage) - the
first delivery wins - and counts conversions per local day by action and
stage; a lead finished twice (completed and paid) counts once, at its first
finished stage (2.26), and a line whose row was soft-removed is left out. It shares only the name lists in conversions/__init__.py (the
stages, the tool events, the action shape) and the file locations.

A day where the two disagree is withheld: `daily` (run-daily's step,
registered in audit_more.DAILY) reports it, and `findings` says which days
a report must leave out.

The beacon spool joins this count (build step 2): `recount_beacon` reads
people's lines that carry a visitor ID, maps the events with the shared
BEACON_ACTIONS list, and keeps one per (visitor ID, action, stage) within
BEACON_REPEAT_SECONDS of the last one kept, with its own JSON reading, its
own ID check and its own time parser - nothing from beacon.py or
from_beacon.py. The store's tool "beacon" rows are compared with it.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .conversions import (ACTION, ALIASES, BEACON_ACTIONS, BEACON_REPEAT_SECONDS, BEACON_TOOL,
                          EVENTS, FINISHED, FUTURE_SLACK, HUBSPOT_MEETING, LEAD_ACTIONS,
                          LEAD_EXCLUDED, LEAD_OUTCOMES, LEAD_TYPES, LEADS_TOOL, STAGES, TOOLS)

AUDIT_DAYS = 30


class _Bad(Exception):
    """A spooled body the main road refuses too (it answered 400)."""


# ------------------------------------------------------------ own readers

def _instant(value, naive_zone=timezone.utc) -> datetime | None:
    """A time; ISO text without an offset is taken in `naive_zone` (the zone
    the spool line names, else UTC as before 2.4.0)."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    try:
        if isinstance(value, (int, float)):
            n = float(value)
            if n > 1e10:
                n /= 1000.0
            return datetime.fromtimestamp(int(n) if n == int(n) else n, tz=timezone.utc
                                          ).replace(microsecond=0)
        s = str(value).strip()
        if s[-1:] in ("Z", "z"):
            s = s[:-1] + "+00:00"
        got = datetime.fromisoformat(s)
    except (ValueError, OverflowError, OSError):
        return None
    if got.tzinfo is None:
        got = got.replace(tzinfo=naive_zone)
    return got.astimezone(timezone.utc).replace(microsecond=0)


def _txt(value, limit: int) -> str:
    if value is None or isinstance(value, (dict, list, bool)):
        return ""
    return str(value).strip()[:limit]


def _obj(value) -> dict:
    return value if isinstance(value, dict) else {}


def _lead(item, naive_zone=timezone.utc) -> tuple:
    if not isinstance(item, dict):
        raise _Bad
    ref = _txt(item.get("external_ref"), 120)
    action = str(item.get("action") or "").strip().lower()
    action = ALIASES.get(action, action)
    stage = str(item.get("stage") or "completed").strip().lower()
    if not ref or not ACTION.match(action) or stage not in STAGES:
        raise _Bad
    at = None
    if item.get("at") not in (None, ""):
        at = _instant(item.get("at"), naive_zone)
        if at is None:
            raise _Bad
    return action, stage, ref, at


def _read(tool: str, body, naive_zone=timezone.utc) -> list[tuple]:
    """[(action, stage, ref, at or None)] for one spooled body."""
    if tool == "lead":
        return [_lead(body, naive_zone)]
    if tool == "json":
        items = body.get("records") if isinstance(body, dict) and "records" in body else body
        items = [items] if isinstance(items, dict) else items
        if not isinstance(items, list) or not 0 < len(items) <= 100:
            raise _Bad
        return [_lead(i, naive_zone) for i in items]
    if tool == "calendly":
        inner = body.get("payload") if isinstance(body, dict) else None
        if not isinstance(inner, dict):
            raise _Bad
        name = str(body.get("event") or "")
        if name == "invitee.canceled" and inner.get("rescheduled") is True:
            name = "invitee.canceled+rescheduled"
        if name not in EVENTS["calendly"]:
            return []
        who = inner.get("invitee")
        ref = _txt(who if isinstance(who, str) and who else inner.get("uri"), 300)
        if not ref:
            raise _Bad
        at = _instant(body.get("created_at")) or _instant(inner.get("created_at"))
        return [(*EVENTS["calendly"][name], ref, at)]
    if tool == "calcom":
        inner = body.get("payload") if isinstance(body, dict) else None
        if not isinstance(inner, dict):
            raise _Bad
        name = str(body.get("triggerEvent") or "")
        if name not in EVENTS["calcom"]:
            return []
        ref = _txt(inner.get("uid"), 120)
        if not ref:
            raise _Bad
        return [(*EVENTS["calcom"][name], ref, _instant(body.get("createdAt")))]
    if tool == "stripe":
        if not isinstance(body, dict) or body.get("object") != "event":
            raise _Bad
        data = _obj(body.get("data")).get("object")
        if not isinstance(data, dict):
            raise _Bad
        name = str(body.get("type") or "")
        if name == "checkout.session.completed" and data.get("payment_status") == "unpaid":
            name = "checkout.session.completed+unpaid"
        if name == "invoice.paid":
            name += "+" + str(data.get("billing_reason") or "")
        if name not in EVENTS["stripe"]:
            return []
        ref = _txt(data.get("id"), 120)
        if not ref:
            raise _Bad
        return [(*EVENTS["stripe"][name], ref, _instant(body.get("created")))]
    if tool == "typeform":
        if not isinstance(body, dict):
            raise _Bad
        if str(body.get("event_type") or "") not in EVENTS["typeform"]:
            return []
        answer = body.get("form_response")
        if not isinstance(answer, dict) or not _txt(answer.get("token"), 120):
            raise _Bad
        return [(*EVENTS["typeform"][str(body["event_type"])], _txt(answer["token"], 120),
                 _instant(answer.get("submitted_at")))]
    if tool == "hubspot":
        return _hubspot(body)
    raise _Bad


def _hubspot(body) -> list[tuple]:
    def value(props, key):
        got = props.get(key)
        return got.get("value") if isinstance(got, dict) else got
    if isinstance(body, list):
        if len(body) > 100:
            raise _Bad
        out = []
        for item in body:
            if not isinstance(item, dict):
                raise _Bad
            name = str(item.get("subscriptionType") or "")
            if (name == "deal.propertyChange" and item.get("propertyName") == "dealstage"
                    and item.get("propertyValue") == "closedwon"):
                name = "deal.propertyChange+closedwon"
            if name == "object.creation" and \
                    str(item.get("objectTypeId") or "") == HUBSPOT_MEETING:
                name = "object.creation+" + HUBSPOT_MEETING
            if name not in EVENTS["hubspot"]:
                continue
            action, stage = EVENTS["hubspot"][name]
            oid = _txt(item.get("objectId"), 40)
            if not oid:
                raise _Bad
            out.append((action, stage, f"{action}:{oid}", _instant(item.get("occurredAt"))))
        return out
    if not isinstance(body, dict):
        raise _Bad
    props = _obj(body.get("properties"))
    oid = _txt(body.get("objectId") or value(props, "hs_object_id"), 40)
    if not oid:
        raise _Bad
    at = _instant(value(props, "createdate")) or _instant(body.get("occurredAt"))
    action, stage = EVENTS["hubspot"]["workflow"]
    asked = value(props, "skald_action")
    if isinstance(asked, str):
        asked = asked.strip().lower()
        asked = ALIASES.get(asked, asked)
        if asked and ACTION.match(asked):
            action = asked
    return [(action, stage, f"workflow:{oid}", at)]


# --------------------------------------------------------------- recount

def _zone_of(line: dict):
    """The zone a line says its times without an offset are in; UTC for a
    line without one (or one this server does not know)."""
    name = line.get("zone")
    if not isinstance(name, str) or not name:
        return timezone.utc
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except (ValueError, KeyError, OSError):
        return timezone.utc

def _lines(spool: Path):
    """Every spooled line, oldest file first, in the order written."""
    files = []
    for path in Path(spool).glob("*.jsonl"):
        try:
            files.append((date.fromisoformat(path.name[:10]), path))
        except ValueError:
            continue
    for _, path in sorted(files):
        with open(path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                try:
                    got = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(got, dict):
                    yield got


def test_keys(db_path: Path, site: str) -> frozenset:
    """{(tool, external ref, stage)} of the rows marked test (`conversions
    mark-test`, POST .../leads/test, or a lead body's `test: true`: that
    stage only), by this road's own SQL over the file opened read-only. A
    test row stays in the spools; this road leaves it out of its count."""
    import sqlite3
    if not Path(db_path).is_file():
        return frozenset()
    db = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        cols = {r[1] for r in db.execute("PRAGMA table_info(conversions)")}
        if "test" not in cols:
            return frozenset()
        return frozenset(db.execute("SELECT DISTINCT tool, external_ref, stage FROM "
                                    "conversions WHERE site = ? AND test <> 0",
                                    (site,)).fetchall())
    finally:
        db.close()


def removed_keys(db_path: Path, site: str) -> dict:
    """{(tool, external ref, stage): when it was last taken away} for the rows
    in `removed` (`conversions remove`, a lead-database sync), by this road's
    own SQL over the file opened read-only. Their spool lines stay; this road
    leaves out the lines received before the row went (a later resend made a
    new row, and counts)."""
    import sqlite3
    if not Path(db_path).is_file():
        return {}
    db = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                          "name = 'removed'").fetchone():
            return {}
        rows = db.execute("SELECT tool, external_ref, stage, MAX(removed_at) FROM removed "
                          "WHERE site = ? GROUP BY 1, 2, 3", (site,)).fetchall()
    finally:
        db.close()
    out = {}
    for tool, ref, stage, when in rows:
        at = _instant(when)
        if at is not None:
            out[(tool, ref, stage)] = at
    return out


def recount(spool: Path, site: str, tz, first: date, last: date,
            skip: frozenset = frozenset(), removed: dict | None = None,
            removals: list | None = None) -> dict:
    """{local day: {(action, stage): n}} from the spool, first..last; a
    (tool, ref, stage) in `skip` (test_keys) is not counted, nor a line
    received before its row was taken away (`removed`, removed_keys).

    One lead counts once (2.26): of the finished stages (FINISHED) of a lead
    action (LEAD_ACTIONS) under one tool, ref and action, only the earliest
    (by its time, then the stage's name) is counted; a `paid` sent after a
    `completed` for the same sign-up is not a second lead.

    Refunds (2.32) are the rows audit_revenue.replay keeps: one per sale, a
    refund that came before its sale moved onto it, as the store does, each
    removal (`removals`, audit_revenue._removals; else `removed`) replayed at
    its time."""
    removed = removed or {}
    seen: set = set()
    kept: list[tuple] = []
    refunds = False
    for line in _lines(spool):
        tool = line.get("tool")
        if line.get("site") != site or tool not in TOOLS:
            continue
        received = _instant(line.get("received_at"))
        if received is None:
            continue
        try:
            found = _read(tool, line.get("body"), _zone_of(line))
            found = [(a, s, r, at or received) for a, s, r, at in found]
            if any(at > received + timedelta(seconds=FUTURE_SLACK) for *_, at in found):
                raise _Bad
        except _Bad:
            continue
        for action, stage, ref, at in found:
            if stage == "refunded":
                refunds = True
                continue
            key = (tool, ref, stage)
            if key in seen:
                continue
            gone = removed.get(key)
            if gone is not None and received <= gone:
                continue                  # taken away after it came: neither kept nor seen
            seen.add(key)
            if key not in skip:
                kept.append((tool, ref, action, stage, at))
    if refunds:
        from .audit_revenue import replay
        for key, r in replay(spool, site, removed if removals is None else removals).items():
            if key[2] == "refunded" and key not in skip:
                kept.append((key[0], key[1], r["action"], "refunded", r["at"]))
    lead_first: dict = {}
    for tool, ref, action, stage, at in kept:
        if action in LEAD_ACTIONS and stage in FINISHED:
            mine = (at, stage)
            if lead_first.get((tool, ref, action), mine) >= mine:
                lead_first[(tool, ref, action)] = mine
    out: dict = {}
    for tool, ref, action, stage, at in kept:
        if action in LEAD_ACTIONS and stage in FINISHED and \
                lead_first[(tool, ref, action)] != (at, stage):
            continue                      # the same lead finished again: not a second one
        day = at.astimezone(tz).date()
        if first <= day <= last:
            per = out.setdefault(day.isoformat(), {})
            per[(action, stage)] = per.get((action, stage), 0) + 1
    return out


_BEACON_VID = re.compile(r"\Askv_[A-Za-z0-9_-]{22}\Z")


def recount_beacon(spool: Path, tz, first: date, last: date,
                   files_from: date | None = None, skip: frozenset = frozenset()) -> dict:
    """{local day: {(action, stage): n}} of beacon conversions, first..last,
    from the beacon spool's own lines. Every file up to the day after `last`
    (and from `files_from`, when given: two days before `first` is enough,
    a repeat is judged within 30 minutes) is read, oldest first, so a repeat
    is judged against the same earlier lines the helper saw."""
    files = []
    for path in Path(spool).glob("*.jsonl"):
        try:
            day = date.fromisoformat(path.name[:10])
        except ValueError:
            continue
        if day <= last + timedelta(days=1) and (files_from is None or day >= files_from):
            files.append((day, path))
    kept: dict = {}
    out: dict = {}
    for _, path in sorted(files):
        with open(path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                if '"v":' not in raw:
                    continue
                try:
                    got = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(got, dict) or got.get("g") != "people":
                    continue
                pair = BEACON_ACTIONS.get(got.get("e"))
                vid = got.get("v")
                if pair is None or not isinstance(vid, str) or not _BEACON_VID.match(vid):
                    continue
                at = _instant(got.get("at"))
                if at is None:
                    continue
                key = (vid, *pair)
                last_kept = kept.get(key)
                if last_kept is not None and \
                        last_kept > at - timedelta(seconds=BEACON_REPEAT_SECONDS):
                    continue
                kept[key] = at if last_kept is None else max(at, last_kept)
                day = at.astimezone(tz).date()
                ref = f"{vid}:{pair[0]}:{pair[1]}:{at.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                if ("beacon", ref, pair[1]) not in skip and first <= day <= last:
                    per = out.setdefault(day.isoformat(), {})
                    per[pair] = per.get(pair, 0) + 1
    return out


def _leads_on(config: dict) -> Path | None:
    """The lead DB when conversions are taken from it, else None."""
    from .config import setting
    raw = setting(config or {}, "leads", "db")
    if not raw or setting(config or {}, "conversions", "from_leads", True) in (False, "false"):
        return None
    return Path(str(raw)).expanduser()


def recount_leads(path: Path, tz, first: date, last: date,
                  skip: frozenset = frozenset()) -> dict:
    """{local day: {(action, stage): n}} of the lead DB's leads, first..last,
    by SQL over the file opened read-only; a lead id in `skip` (marked test)
    is left out."""
    import sqlite3
    from datetime import time as clock
    db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    try:
        cols = {r[1] for r in db.execute("PRAGMA table_info(submissions)")}
        status = ("COALESCE(NULLIF(LOWER(TRIM(status)), ''), 'new')" if "status" in cols
                  else "'new'")
        bounds, args = [], []
        day = first
        while day <= last:
            lo = datetime.combine(day, clock(0), tzinfo=tz).astimezone(timezone.utc)
            hi = datetime.combine(day + timedelta(days=1), clock(0), tzinfo=tz
                                  ).astimezone(timezone.utc)
            bounds.append("(?, ?, ?)")
            args += [day.isoformat(), lo.strftime("%Y-%m-%d %H:%M:%S"),
                     hi.strftime("%Y-%m-%d %H:%M:%S")]
            day += timedelta(days=1)
        rows = db.execute(
            f"WITH b(day, lo, hi) AS (VALUES {', '.join(bounds)}) "
            f"SELECT b.day, LOWER(TRIM(COALESCE(s.type, ''))), {status}, COUNT(*) "
            f"FROM submissions s JOIN b ON julianday(s.created_at) >= julianday(b.lo) "
            f"AND julianday(s.created_at) < julianday(b.hi) "
            f"WHERE s.id IS NOT NULL{_not_in(skip)} GROUP BY 1, 2, 3",
            [*args, *sorted(skip)]).fetchall()
    finally:
        db.close()
    out: dict = {}
    for day, kind, state, n in rows:
        if state in LEAD_EXCLUDED:
            continue
        if kind in LEAD_TYPES:
            action, stage = LEAD_TYPES[kind]
        else:
            action, stage = ALIASES.get(kind, kind), "completed"
        if not ACTION.match(action):
            continue
        per = out.setdefault(day, {})
        per[(action, stage)] = per.get((action, stage), 0) + n
        if stage == "completed" and state in LEAD_OUTCOMES:
            per[(action, state)] = per.get((action, state), 0) + n
    return out


def _not_in(ids: frozenset) -> str:
    return f" AND CAST(s.id AS TEXT) NOT IN ({','.join('?' * len(ids))})" if ids else ""


def _beacon_spool(config: dict, folder: Path) -> Path:
    """Where the beacon helper writes: the path the CLI resolved, else
    `beacon.spool`, else <history folder>/beacon."""
    from .config import setting
    resolved = (config.get("_resolved") or {}).get("beacon_spool")
    if resolved:
        return Path(resolved)
    raw = setting(config, "beacon", "spool")
    return Path(str(raw)).expanduser() if raw else Path(folder) / "beacon"


def _beacon_site(config: dict, site: str) -> bool:
    """The helper files every beacon conversion under the config's own site."""
    from .config import site_name
    return site == site_name(config)


def _merge(a: dict, b: dict) -> dict:
    out = {day: dict(per) for day, per in a.items()}
    for day, per in b.items():
        mine = out.setdefault(day, {})
        for pair, n in per.items():
            mine[pair] = mine.get(pair, 0) + n
    return out


def compare(stored: dict, counted: dict, first: date, last: date) -> dict[str, list[str]]:
    """{day: problems} for every day the two counts disagree."""
    out: dict[str, list[str]] = {}
    day = first
    while day <= last:
        key = day.isoformat()
        a, b = stored.get(key, {}), counted.get(key, {})
        for pair in sorted(set(a) | set(b)):
            if a.get(pair, 0) != b.get(pair, 0):
                out.setdefault(key, []).append(
                    f"{key} {pair[0]} {pair[1]}: stored {a.get(pair, 0)}, "
                    f"recounted from the spool {b.get(pair, 0)}")
        day += timedelta(days=1)
    return out


def findings(config: dict, folder: Path, site: str, tz, first: date, last: date,
             today: date | None = None, refresh: bool = True) -> dict[str, list[str]] | None:
    """The days first..last to withhold, with why. None when conversions are
    not set up (no store and no spool). The beacon's counts of whole days
    before `today` come from the audit's own cache unless `refresh`
    (beacon_counts)."""
    from .conversions import spool as spool_mod
    from .conversions import store
    db_path = store.path_for(config, folder)
    spool = spool_mod.spool_dir(config, folder)
    beacons = _beacon_spool(config, folder)
    with_beacon = beacons.exists() and _beacon_site(config, site)
    leads = _leads_on(config)
    if not db_path.exists() and not spool.exists() and not _ids_on(config) and leads is None:
        return None
    tools = TOOLS + (BEACON_TOOL,) + ((LEADS_TOOL,) if leads is not None else ())
    stored: dict = {}
    if db_path.exists():
        db = store.connect(db_path)
        try:
            stored = store.day_counts(db, site, tz, first, last, tools=tools)
        finally:
            db.close()
    skip = test_keys(db_path, site)
    from .audit_revenue import _removals
    counted = recount(spool, site, tz, first, last, skip, removed_keys(db_path, site),
                      _removals(db_path, site) if db_path.exists() else None)
    if with_beacon:
        counted = _merge(counted, beacon_counts(beacons, folder, tz, first, last, today,
                                                refresh, skip, store.keep_days(config)))
    if leads is not None and leads.is_file():
        counted = _merge(counted, recount_leads(
            leads, tz, first, last, frozenset(r for t, r, _ in skip if t == LEADS_TOOL)))
    return compare(stored, counted, first, last)


# ------------------------------------------------- the beacon's day cache

CACHE = "conversions-audit.json"
CACHE_DAYS = 400


def _load_cache(folder: Path, tz) -> dict:
    try:
        got = json.loads((Path(folder) / CACHE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(got, dict) or got.get("tz") != str(tz) or \
            not isinstance(got.get("days"), dict):
        return {}
    return got


def _save_cache(folder: Path, tz, days: dict, keep_days: int = CACHE_DAYS) -> None:
    """The last `keep_days` days' counts (at least CACHE_DAYS); every day when
    conversions are kept for good (0): the beacon spool is kept only
    beacon.keep_days, so an old day's beacon rows are checked against the
    count this audit made while the spool still held it."""
    from .files import write_atomic
    most = None if keep_days == 0 else max(CACHE_DAYS, int(keep_days))
    keep = dict(sorted(days.items())[-most:]) if most else dict(sorted(days.items()))
    try:
        write_atomic(Path(folder) / CACHE, json.dumps({"tz": str(tz), "days": keep},
                                                      separators=(",", ":")))
    except OSError:
        pass


def forget_cache(folder: Path) -> None:
    """After `conversions forget` or `mark-test`: count again."""
    (Path(folder) / CACHE).unlink(missing_ok=True)


def beacon_counts(spool: Path, folder: Path, tz, first: date, last: date,
                  today: date | None = None, refresh: bool = True,
                  skip: frozenset = frozenset(), keep_days: int = CACHE_DAYS) -> dict:
    """recount_beacon over first..last, reading only the files it needs: the
    counts of whole days before `today` are kept in CACHE beside the history
    (the audit's own file) and read back unless `refresh`; the days not in
    it are recounted from two days before them."""
    cache = {} if today is None else _load_cache(folder, tz)
    days = dict(cache.get("days") or {})
    out: dict = {}
    run: list[date] = []
    changed = False

    def count(span: list[date]) -> None:
        nonlocal changed
        got = recount_beacon(spool, tz, span[0], span[-1], span[0] - timedelta(days=2), skip)
        for d in span:
            key = d.isoformat()
            per = got.get(key) or {}
            if per:
                out[key] = per
            if today is not None and d < today:
                days[key] = [[a, s, n] for (a, s), n in sorted(per.items())]
                changed = True

    day = first
    while day <= last:
        key = day.isoformat()
        if not refresh and today is not None and day < today and key in days:
            if run:
                count(run)
                run = []
            per = {(a, s): n for a, s, n in days[key]}
            if per:
                out[key] = per
        else:
            run.append(day)
        day += timedelta(days=1)
    if run:
        count(run)
    if changed:
        _save_cache(folder, tz, days, keep_days)
    return out


def set_up(ctx) -> bool:
    """Whether this install takes conversions at all (audit_more.DAILY)."""
    from .conversions import spool as spool_mod
    from .conversions import store
    folder = ctx.db_path.parent
    return store.path_for(ctx.config, folder).exists() or \
        spool_mod.spool_dir(ctx.config, folder).exists() or _ids_on(ctx.config) or \
        _leads_on(ctx.config) is not None


def _ids_on(config: dict) -> bool:
    """`beacon.visitor_ids`: the beacon makes conversions, so they are counted."""
    from .config import setting
    return setting(config or {}, "beacon", "visitor_ids", False) in (True, "true")


def daily(ctx, day: date) -> list[str] | None:
    """run-daily's step (audit_more.DAILY): the last `conversions.audit_days`
    (default 30) days up to `day`, store against spool."""
    from .config import setting
    days = int(setting(ctx.config, "conversions", "audit_days", AUDIT_DAYS))
    first = day - timedelta(days=days - 1)
    found = findings(ctx.config, ctx.db_path.parent, ctx.site, ctx.tz, first, day,
                     today=day + timedelta(days=1), refresh=True)
    if found is None:
        return None
    return [p for key in sorted(found) for p in found[key]]



# ------------------------------------------------- conversions.json's check

def check_file(config: dict, folder: Path, site: str, tz, first: date, last: date,
               now: str, hours: float, blob: dict, history=None) -> dict[str, list[str]]:
    """Every figure conversions.json shows, against the second counts:
    the stages against the spools and the lead DB (findings), and every
    day's figures and the pages block against audit_conversions_figures'
    SQL, and the revenue and ltv against audit_revenue.py. {"days/<day>",
    "pages_before" or "ltv": problems}."""
    from . import audit_conversions_figures as figures
    from .conversions import store
    out: dict[str, list[str]] = {}
    for day, problems in (findings(config, folder, site, tz, first, last, today=last,
                                   refresh=False) or {}).items():
        out.setdefault(f"days/{day}", []).extend(problems)
    path = store.path_for(config, folder)
    problems = figures.check_since(path, site, tz, _leads_on(config), blob.get("since"))
    if problems:
        return {"*": problems}
    for day, problems in figures.check_days(path, site, tz, first, last, now, hours,
                                            blob["days"], history, config).items():
        out.setdefault(f"days/{day}", []).extend(problems)
    # 2.32: revenue and lifetime value, by SQL and from the spool (audit_revenue.py).
    from . import audit_revenue
    for key, problems in audit_revenue.check(config, folder, site, tz, first, last,
                                             blob).items():
        out.setdefault(key, []).extend(problems)
    period = blob.get("period") or {}
    if period:
        problems = figures.check_pages(path, site, tz, date.fromisoformat(period["first"]),
                                       date.fromisoformat(period["last"]),
                                       blob.get("pages_before"))
        if problems:
            out["pages_before"] = problems
    return out
