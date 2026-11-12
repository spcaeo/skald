"""The second count of a lead's own visits (people/lead_visits.py, #30, 2.46.5).

Find a person lists a person's visits, each marked proven or likely. This
road re-derives, for every finished conversion of the day (stage completed
or paid, not test), which visit is proven for it, by its own SQL and its own
reading of each visit's `posts` (a JSON list of UTC stamps), sharing only
the table names, the documented rule and PROVEN_SECONDS with the main code:

    proven   exactly one kept visit of the site whose posts hold a stamp no
             more than PROVEN_SECONDS before or after the conversion's time

and sets that against lead_visits.path(...) for the same conversion:

  * the main road proves the same visit (its day and seq), or none when
    this road finds none or more than one;
  * every visit the main road marks likely has the same address and the
    same browser line as one of its proven visits, an address that is not
    "(removed)", and starts from AROUND_HOURS before a proven visit to
    AROUND_HOURS after its end (or the conversion, when later).

The visits table itself is recounted from the raw log by audit_people.py.
Nothing here is a figure, so a finding withholds no figure; it ends
run-daily with exit 1 (audit_more.DAILY) so the links are looked at. No
address is ever written into a problem.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

PROVEN_SECONDS = 10             # the rule people/lead_visits.py documents
AROUND_HOURS = 24
REMOVED = "(removed)"
FMT = "%Y-%m-%dT%H:%M:%SZ"
LIMIT = 2000                    # conversions checked a day


def _when(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def proven_by_own_road(db, site: str, at: str) -> list[tuple]:
    """[(day, seq)] of the visits whose posts hold a stamp within
    PROVEN_SECONDS of `at`: this road's own reading."""
    when = _when(at)
    if when is None:
        return []
    lo, hi = when - timedelta(seconds=PROVEN_SECONDS), when + timedelta(seconds=PROVEN_SECONDS)
    out = []
    # A visit can only have posted inside [start, end]; read every visit that
    # overlaps the window, then its posts.
    for day, seq, posts in db.execute(
            "SELECT day, seq, posts FROM visits WHERE site = ? AND start <= ? AND end >= ?",
            (site, hi.strftime(FMT), lo.strftime(FMT))):
        try:
            stamps = json.loads(posts or "[]")
        except ValueError:
            continue
        if any((t := _when(s)) is not None and lo <= t <= hi for s in stamps or []):
            out.append((day, seq))
    return out


def check(db, site: str, a: str, b: str) -> tuple[int, list[str]]:
    """(conversions checked, problems) for the conversions at in [a, b)."""
    from .people.lead_visits import path
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM conversions WHERE site = ? AND test = 0 AND stage IN ('completed', "
        "'paid') AND at >= ? AND at < ? ORDER BY at LIMIT ?", (site, a, b, LIMIT))]
    problems = []
    for c in rows:
        own = proven_by_own_road(db, site, c["at"])
        want = own[0] if len(own) == 1 else None
        got = path(db, site, [c])
        proven = [(v["day"], v["seq"]) for v in got["visits"] if v["link"] == "proven"]
        if proven != ([want] if want else []):
            problems.append(f"lead visits: {site}: conversion {c['id']} ({c['action']} "
                            f"{c['stage']}): {len(proven)} proven visit(s) shown, this road "
                            f"finds {'one' if want else 'none'}"
                            f"{' other' if want and proven else ''}")
            continue
        keys = {(v["ip"], v.get("user_agent") or "") for v in got["visits"] if v["link"] == "proven"}
        spans = [(_when(v["start"]), max(_when(v["end"]), _when(c["at"])))
                 for v in got["visits"] if v["link"] == "proven"]
        slack = timedelta(hours=AROUND_HOURS)
        for v in got["visits"]:
            if v["link"] != "likely":
                continue
            ok = (v["ip"] and v["ip"] != REMOVED and v.get("user_agent")
                  and (v["ip"], v.get("user_agent") or "") in keys)
            t = _when(v["start"])
            near = t is not None and any(lo - slack <= t <= hi + slack for lo, hi in spans)
            if not (ok and near):
                problems.append(f"lead visits: {site}: conversion {c['id']}: a likely visit "
                                f"({v['day']} #{v['seq']}) is not the same address and "
                                "browser near a proven one")
    return len(rows), problems


def _path(ctx) -> Path | None:
    from .conversions import store
    got = store.path_for(ctx.config, ctx.db_path.parent)
    return got if got is not None and Path(got).is_file() else None


def set_up(ctx) -> bool:
    """True when the site keeps visits and conversions."""
    path = _path(ctx)
    if path is None:
        return False
    try:
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
        try:
            have = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            return {"visits", "conversions"} <= have
        finally:
            db.close()
    except sqlite3.Error:
        return False


def daily(ctx, day) -> list[str] | None:
    """The day's conversions (in the site's zone), each link re-derived."""
    from .window import zone
    path = _path(ctx)
    if path is None or not set_up(ctx):
        return None
    tz = zone(ctx.config)
    start = datetime.combine(day, time(0), tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=tz).astimezone(timezone.utc)
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        n, problems = check(db, ctx.site, start.strftime(FMT), end.strftime(FMT))
    finally:
        db.close()
    ctx.out(f"lead visits: {n} conversion(s), each proven visit found again by its own road")
    return problems
