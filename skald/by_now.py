"""Yesterday at this hour: what Overview > Summary in Live mode compares today with.

"Today so far" is never compared with a whole day: a partial day against a
whole one is a fall that did not happen. So the live run counts yesterday
again, from local midnight up to the same local time of day as today's
`until`, by the very same tally (window.analyse_window, verify.check) as
every figure here, and keeps it beside today's in the snapshot:

  by_now        {"day": yesterday, "from", "until": yesterday's cut,
                 "state": "ok" | "withheld" | "partial" | "empty",
                 "history": yesterday's stored state or None (not collected yet),
                 "visitors", "pages", "ai_visitors",
                 "hours": {"visitors", "pages", "ai_visitors"}: yesterday by local
                          hour to the cut (24 numbers each) or null,
                 "today_hours": the same three for today so far, or null}

  visitors      readers: visits that read a page (Overview's Visitors)
  pages         people's page views (Pages read)
  ai_visitors   visits sent by an AI assistant's answer (Visitors from AI),
                counted per visitor and gap exactly as the tally counts them

Unknown stays unknown: yesterday stored as withheld or partial in history,
a recount that does not verify, or no line in the window carries no figures
(the page says "not recorded"). A series whose hours do not add up to its
figure is left out (null), never drawn.

The hours: readers by the hour of their first page (the tally's own `hour`
breakdown); page views and AI-sent visits by the hour of the request that
counted them (Hours, an observer of the same pass). Leads at this hour are
conversions.json's (conversions_leads.by_now). audit_by_now.py counts every
one of these again from the raw lines (`skald audit --live`).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from . import dimensions as dim
from .classify import Group, Tier

VERSION = 1
HOURS = [f"{h:02d}" for h in range(24)]
KEYS = ("visitors", "pages", "ai_visitors")


class Hours:
    """An observer of the tally: people's page views, and the visits an AI
    assistant sent (per address and user agent, a new one after the visit
    gap, as aggregate.Tally counts cited_visits), by local hour."""

    def __init__(self, tz, gap_minutes: int) -> None:
        self.tz = tz
        self.gap = timedelta(minutes=gap_minutes)
        self.pages: Counter = Counter()
        self.ai: Counter = Counter()
        self.last: dict = {}

    def __call__(self, hit, verdict) -> None:
        if verdict.group is not Group.PEOPLE:
            return
        hour = dim.hour(hit.when, self.tz)
        if hit.is_page:
            self.pages[hour] += 1
        if verdict.tier is Tier.CITED:
            key = (hit.address, hit.user_agent)
            previous = self.last.get(key)
            self.last[key] = hit.when
            if previous is None or abs(hit.when - previous) > self.gap:
                self.ai[hour] += 1


def figures(totals) -> dict:
    people = totals.groups.get(Group.PEOPLE)
    return {"visitors": people.readers if people else 0,
            "pages": people.views if people else 0,
            "ai_visitors": people.cited_visits if people else 0}


def series(totals, hours: Hours) -> dict | None:
    """The three figures by local hour, or None when one does not add up."""
    people = totals.groups.get(Group.PEOPLE)
    by_hour = Counter((people.by.get("hour") if people else None) or {})
    out = {"visitors": [int(by_hour.get(h, 0)) for h in HOURS],
           "pages": [int(hours.pages.get(h, 0)) for h in HOURS],
           "ai_visitors": [int(hours.ai.get(h, 0)) for h in HOURS]}
    whole = figures(totals)
    if any(sum(out[k]) != whole[k] for k in KEYS):
        return None
    return out


def cut_of(day, until_local: datetime, tz) -> datetime:
    """`day` at the same local time of day as `until_local`, as aware UTC."""
    t = until_local.astimezone(tz)
    at = datetime(day.year, day.month, day.day, t.hour, t.minute, t.second, tzinfo=tz)
    return at.astimezone(timezone.utc)


def stored_state(db, site: str, day) -> str | None:
    """Yesterday's state in history (store.History.state's rule), None when
    it is not collected yet (the daily run collects it in the morning)."""
    if db is None:
        return None
    try:
        row = db.execute("SELECT verified, partial_from, partial_until FROM days "
                         "WHERE site = ? AND day = ?", (site, day.isoformat())).fetchone()
    except Exception:            # noqa: BLE001 - an older history: not known
        return None
    if row is None:
        return None
    if not row[0]:
        return "withheld"
    return "partial" if (row[1] or row[2]) else "ok"


def part(config: dict, site: str, tz, until: datetime, now: datetime, upto: dict | None,
         db=None, today=None, today_hours: Hours | None = None) -> dict:
    """The snapshot's `by_now`: yesterday from midnight to `until`'s time of
    day. `today` (Totals) and `today_hours` give today's series."""
    from .verify import check
    from .window import analyse_window_views, day_window
    from .live import TOP
    day = until.astimezone(tz).date() - timedelta(days=1)
    start, end = day_window(day, tz)
    cut = min(end, max(start, cut_of(day, until, tz)))
    out = {"version": VERSION, "day": day.isoformat(),
           "from": start.astimezone(tz).isoformat(), "until": cut.astimezone(tz).isoformat(),
           "state": "empty", "history": stored_state(db, site, day), "problems": [],
           **{k: None for k in KEYS}, "hours": None, "today_hours": None}
    if today is not None and today_hours is not None:
        out["today_hours"] = series(today, today_hours)
    if out["history"] in ("withheld", "partial"):
        out["state"] = out["history"]
        return out
    gap = int(((config.get("report") or {}).get("session_gap_minutes")) or 30)
    hours = Hours(tz, gap)
    # The plain files only as far as the live run read them (`upto`, window.plain_sizes).
    totals = analyse_window_views(config, start, cut, now=now, top=TOP, observe=hours,
                                  upto=upto)[0]
    if totals.parsed == 0:
        return out
    problems = check(totals)
    if problems:
        out.update(state="withheld", problems=[str(p) for p in problems])
        return out
    out.update(state="ok", **figures(totals), hours=series(totals, hours))
    return out
