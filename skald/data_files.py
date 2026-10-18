"""The JSON files beside each dashboard page (DATA-CONTRACT.md).

`write(folder, history, key, ...)` writes <page>/data/<name>.json for the
whole site or one view, from history (per day, 180 days ending yesterday)
and the live snapshot (today). This file builds overview, live, visits,
hourly, breakdowns, health, bots and ours; data_reports.py builds
not_found, ai_activity, campaigns, pages and insights.

Everything here is a total or a label read back from history or the
snapshot - no address, user agent or visitor key - except the AI events'
addresses in ai_activity.json, which the owner asked to see on the private
page (see ai_activity.py).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from statistics import mean

from .classify import Group, ads_checks
from .files import write_atomic
from .visits import VisitStats, sentence

SCHEMA_VERSION = 1
DAYS = 180
GROUPS = [g.value for g in Group]
FILES = ("overview", "live", "visits", "hourly", "breakdowns", "health", "bots", "ours",
         "not_found", "ai_activity", "campaigns", "pages", "insights")


# Day kinds a builder never reads from Page.extras: each has its own reader
# (history.extras or SQL) in its own module, and they are the largest blobs.
# Leaving them out of the Page saves parsing them once per page per run
# (docs/PERFORMANCE.md); asking a Page for one is an error, never a null.
OWN_READERS = frozenset({"ai_fetches", "page_firsts", "crawler_paths", "cube",
                         "visit_cube", "page_counts", "crawler_cost",
                         "crawl_health"})


class _Day(dict):
    """One day's blobs on a Page. A kind in OWN_READERS was not loaded, so
    asking for it raises rather than reading as "not recorded"."""

    def _loaded(self, kind) -> None:
        if kind in OWN_READERS:
            raise KeyError(f"{kind} is not loaded on a Page; read it with history.extras")

    def get(self, kind, default=None):
        self._loaded(kind)
        return super().get(kind, default)

    def __getitem__(self, kind):
        self._loaded(kind)
        return super().__getitem__(kind)

    def __contains__(self, kind) -> bool:
        self._loaded(kind)
        return super().__contains__(kind)


def page_extras(history, key: str, first: date, last: date) -> dict[str, dict]:
    """{day: blobs} of every day kind but OWN_READERS."""
    from .store_extras import KINDS
    kinds = tuple(k for k in KINDS if k not in OWN_READERS)
    return {d: _Day(blobs) for d, blobs in history.extras(key, first, last, kinds).items()}


class Page:
    """What every builder needs to know about the page it writes for."""

    def __init__(self, history, key: str, site: str, view, tz, now: datetime,
                 snap: dict | None, config: dict, views=(), ai: dict | None = None,
                 refresh: bool = False, credit=None, live_dir=None) -> None:
        self.history, self.key, self.site, self.view = history, key, site, view
        # Where the live snapshot, private files and job state live (beside
        # the history); None when the caller has none.
        self.live_dir = Path(live_dir) if live_dir is not None else None
        self.tz, self.now, self.config, self.views = tz, now.astimezone(tz), config, views
        self.refresh, self.credit = refresh, credit
        self.today = self.now.date()
        self.anchor = self.today - timedelta(days=1)
        self.first = self.anchor - timedelta(days=DAYS - 1)
        current = bool(snap and snap.get("day") == self.today.isoformat())
        self.snap = snap if current else None
        self.live_ok = bool(self.snap and self.snap.get("state") == "ok")
        self.ai = ai if (ai and ai.get("day") == self.today.isoformat()) else None
        self.daily = history.daily(key, self.first, self.anchor)
        self.states = {e["day"].isoformat(): e for e in self.daily}
        self.extras = page_extras(history, key, self.first, self.anchor)

    def envelope(self) -> dict:
        view = ({"slug": self.view.slug, "name": self.view.name, "rule": self.view.describe()}
                if self.view else None)
        return {"schema_version": SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).astimezone(self.tz)
                .isoformat(timespec="seconds"),
                "site": self.site, "view": view, "timezone": str(self.tz)}

    def day_entry(self, entry: dict) -> dict:
        out = {"day": entry["day"].isoformat(), "state": entry["state"]}
        if entry["state"] == "partial":
            for k in ("partial_from", "partial_until"):
                out[k] = entry[k].isoformat() if entry.get(k) else None
        if entry["state"] == "withheld":
            out["problems"] = entry.get("problems", "")
        return out

    def has_figures(self, entry: dict) -> bool:
        return entry["state"] in ("ok", "partial")

    def counted_days(self) -> list[str]:
        return [e["day"].isoformat() for e in self.daily if self.has_figures(e)]

    def today_block(self) -> dict | None:
        if not self.snap:
            return None
        return {"state": self.snap.get("state"), "from": self.snap.get("from"),
                "until": self.snap.get("until")}

    def per_day(self, figures) -> list[dict]:
        """One entry per day: the state, and `figures(day, entry)` merged in
        when the day has figures."""
        out = []
        for e in self.daily:
            row = self.day_entry(e)
            if self.has_figures(e):
                row.update(figures(e["day"].isoformat(), e))
            out.append(row)
        return out

    def counts(self, kinds: list[str]) -> dict[str, dict[str, Counter]]:
        """{day: {kind: Counter}} for the counted days."""
        out: dict[str, dict[str, Counter]] = {}
        for d, kind, name, n in self.history.count_rows(self.key, kinds, self.counted_days()):
            out.setdefault(d, {}).setdefault(kind, Counter())[name] = n
        return out


# ------------------------------------------------------------------ builders

def overview(p: Page) -> dict:
    kinds = ["engine_tier", "search_engine", "status_people"] + [f"status_{g}" for g in GROUPS]
    counts = p.counts(kinds)
    visit_stats = _visit_stats(p)
    measured = p.history.breakdown_days(p.key, p.first, p.anchor)

    def figures(d, e):
        c = counts.get(d, {})
        stats = visit_stats.get(d)
        ret = (p.extras.get(d) or {}).get("returning")
        search = c.get("search_engine", Counter())
        return {
            "groups": {g.value: e["groups"][g] for g in Group},
            "cited_visits": e["cited_visits"],
            "ai_tiers": {t: int(c.get("engine_tier", {}).get(t, 0)) for t in ("training", "asked")},
            "search_indexing": int(e["groups"][Group.SEARCH_ENGINE]["hits"] - ads_checks(search)),
            "ads_checks": int(ads_checks(search)),
            "not_found_people": (int(c.get("status_people", {}).get("404", 0))
                                 if d in measured else None),
            "server_errors": (sum(int(c.get(f"status_{g}", {}).get("5xx", 0)) for g in GROUPS)
                              if d in measured else None),
            "visits": _visit_summary(stats),
            "returning": ({"readers": ret["readers"], "returning": ret["returning"]}
                          if ret else None),
        }

    credit = {"text": p.credit[0], "url": p.credit[1]} if p.credit else None
    from .store_visits import journey_days
    first = p.history.first_day(p.key)
    return {"anchor": p.anchor.isoformat(), "today": p.today.isoformat(),
            "first_day": first.isoformat() if first else None,
            "views": [{"slug": v.slug, "name": v.name, "rule": v.describe()} for v in p.views],
            "refresh_button": p.refresh, "credit": credit,
            "journey_days": journey_days(p.config), "files": [f + ".json" for f in files()],
            "days": p.per_day(figures)}


def _visit_summary(stats: VisitStats | None) -> dict | None:
    if stats is None:
        return None
    return {"visits": stats.visits, "views": stats.views(), "one_page": stats.one_page(),
            "median_seconds": stats.median_seconds(), "in_app": stats.flags.get("in_app", 0),
            "not_found": stats.flags.get("not_found", 0), "posted": stats.flags.get("posted", 0)}


def _visit_stats(p: Page) -> dict[str, VisitStats]:
    from .export_visits import _day_stats
    measured = p.history.visit_days(p.key, p.first, p.anchor)
    days = [d for d in p.counted_days() if d in measured]
    return _day_stats(p.history, p.key, days)


def stats_dict(stats: VisitStats | None) -> dict | None:
    if stats is None:
        return None
    out = stats.as_dict()
    out.update({"views": stats.views(), "per_visit": stats.per_visit(),
                "one_page": stats.one_page(), "median_seconds": stats.median_seconds()})
    return out


def _with_summary(journeys: list[dict]) -> list[dict]:
    return [{**j, "summary": sentence(j)} for j in journeys]


def live(p: Page) -> dict:
    if p.snap is None:
        return {"stale": True, "state": None}
    drop = {"journeys", "extras", "views", "version", "site", "timezone", "ai_activity"}
    return {"stale": False, **{k: v for k, v in p.snap.items() if k not in drop}}


def visits(p: Page) -> dict:
    from .store_visits import journey_days
    stats = _visit_stats(p)
    keep = journey_days(p.config)
    stored = p.history.journeys(p.key, p.today - timedelta(days=keep), p.anchor)
    today = None
    if p.snap:
        today = {"state": p.snap.get("state"), "stats": None, "journeys": [],
                 "journeys_total": 0}
        today.update(_engagement(None, None))
        if p.live_ok:
            today.update(stats=stats_dict(VisitStats.from_dict(p.snap.get("visits"))),
                         journeys=_with_summary(p.snap.get("journeys") or []),
                         journeys_total=int(p.snap.get("journeys_total", 0)),
                         **_engagement((p.snap.get("extras") or {}).get("engagement"),
                                       p.snap.get("returning")))
    return {"journey_days": keep,
            "days": p.per_day(lambda d, e: {"stats": stats_dict(stats.get(d)), **_engagement(
                (p.extras.get(d) or {}).get("engagement"), (p.extras.get(d) or {}).get("returning"))}),
            "journeys": _with_summary(stored), "today": today}


def _engagement(blob: dict | None, ret: dict | None) -> dict:
    """A day's engagement rows (engagement.py) and returning readers by this
    visit's source (visitors.annotate), each null when not recorded."""
    by = ret.get("by_source") if isinstance(ret, dict) else None
    return {"engagement": blob,
            "returning_by_source": None if by is None else
            {"by_source": by, "warming_up": bool(ret.get("warming_up"))}}


HOUR_KEYS = GROUPS + ["readers", "ai_asked", "ai_training", "server_errors"]
HOURS = [f"{h:02d}" for h in range(24)]


def _full_hours(hours: dict | None) -> dict | None:
    if hours is None:
        return None
    return {h: {k: int((hours.get(h) or {}).get(k, 0)) for k in HOUR_KEYS} for h in HOURS}


def hourly(p: Page) -> dict:
    days = p.per_day(lambda d, e: {
        "hours": _full_hours((p.extras.get(d) or {}).get("hourly")),
        "hours_utc": (p.extras.get(d) or {}).get("hourly_utc")})
    averages, busiest = {}, {}
    for span in (7, 30):
        first = (p.anchor - timedelta(days=span - 1)).isoformat()
        whole = [r["hours"] for r in days if r["state"] == "ok" and r["day"] >= first
                 and r.get("hours") is not None]
        hours = ({h: {k: round(mean(x[h][k] for x in whole), 2) for k in HOUR_KEYS}
                  for h in HOURS} if whole else {})
        averages[f"{span}d"] = {"days": len(whole), "hours": hours}
        busiest[f"{span}d"] = _busiest({h: v["readers"] for h, v in hours.items()})
    today = p.today_block()
    if today is not None:
        today["hours"] = (_full_hours((p.snap.get("extras") or {}).get("hourly"))
                          if p.live_ok else None)
        today["hours_utc"] = ((p.snap.get("extras") or {}).get("hourly_utc")
                              if p.live_ok else None)
        busiest["today"] = _busiest({h: v["readers"] for h, v in (today["hours"] or {}).items()})
    return {"days": days, "today": today, "averages": averages, "busiest": busiest}


def _busiest(readers: dict) -> list[dict]:
    ranked = sorted(((h, v) for h, v in readers.items() if v), key=lambda kv: (-kv[1], kv[0]))
    return [{"hour": h, "readers": v} for h, v in ranked[:3]]


def breakdowns(p: Page) -> dict:
    from .export import _history_breakdowns
    measured = p.history.breakdown_days(p.key, p.first, p.anchor)
    per = _history_breakdowns(p.history, p.key, [d for d in p.counted_days() if d in measured])
    kinds = ["people_page", "engine_page", "cited_by", "engine_training", "engine_asked",
             "search_engine"]
    counts = p.counts(kinds)

    def lists(c: dict) -> dict:
        return {"pages": dict(c.get("people_page", {})), "ai_pages": dict(c.get("engine_page", {})),
                "cited_by": dict(c.get("cited_by", {})),
                "engines": {"training": dict(c.get("engine_training", {})),
                            "asked": dict(c.get("engine_asked", {}))},
                "search": dict(c.get("search_engine", {}))}

    days = p.per_day(lambda d, e: {"readers_by": (per.get(d) or {}).get("by") if d in measured
                                   else None, **lists(counts.get(d, {}))})
    today = p.today_block()
    if today is not None and p.live_ok:
        s = p.snap
        people = s.get("people") or {}
        today.update({"readers_by": (s.get("breakdowns") or {}).get("by"),
                      "pages": people.get("pages", {}), "ai_pages": s.get("ai_pages", {}),
                      "cited_by": people.get("cited_by", {}), "engines": s.get("ai", {}),
                      "search": s.get("search", {})})
    return {"days": days, "today": today}


def health(p: Page) -> dict:
    from .export import _history_breakdowns
    measured = p.history.breakdown_days(p.key, p.first, p.anchor)
    per = _history_breakdowns(p.history, p.key, [d for d in p.counted_days() if d in measured])
    fields = ("statuses", "not_found", "server_errors", "speeds", "slow_pages", "posts")

    def figures(d, e):
        got = per.get(d) if d in measured else None
        return {f: (got or {}).get(f, {}) if got is not None else None for f in fields}

    today = p.today_block()
    if today is not None and p.live_ok:
        b = p.snap.get("breakdowns") or {}
        today.update({f: b.get(f) for f in fields})
    return {"days": p.per_day(figures), "today": today}


BOT_FIELDS = ("link_previews", "verification", "fake_browsers", "blocked")


def bots(p: Page) -> dict:
    from .bot_verify import from_config
    counts = p.counts(["bot_agent", "status_bots"])

    def release2(blob: dict | None) -> dict:
        return {k: (blob or {}).get(k) if blob is not None else None for k in BOT_FIELDS}

    days = p.per_day(lambda d, e: {
        "requests": e["groups"][Group.BOTS]["hits"], "probes": e["groups"][Group.BOTS]["probes"],
        "agents": dict(counts.get(d, {}).get("bot_agent", {})),
        "statuses": dict(counts.get(d, {}).get("status_bots", {})),
        **release2((p.extras.get(d) or {}).get("bots"))})
    today = p.today_block()
    if today is not None and p.live_ok:
        b = p.snap.get("bots") or {}
        today.update({"requests": b.get("requests", 0), "probes": b.get("probes", 0),
                      "agents": None,
                      "statuses": ((p.snap.get("breakdowns") or {}).get("statuses") or {})
                      .get("bots", {}),
                      **release2((p.snap.get("extras") or {}).get("bots"))})
    verifier = from_config(p.config)
    return {"days": days, "today": today,
            "ranges": verifier.lists_summary() if verifier else {},
            "dns_cache": verifier.dns_summary() if verifier else
            {"addresses": 0, "checked_at": None},
            # The AI crawler settings route, only once the owner says nginx has
            # it (bot_policy.enabled): the page fetches nothing before that.
            "api": {"bot_policy": "bot-policy"}
            if ((p.config or {}).get("bot_policy") or {}).get("enabled") is True else None}


def _heartbeat(beat: dict | None, start: datetime, end: datetime, tz) -> dict | None:
    """Uptime over [start, end) from a day's heartbeat blob: expected one
    beat per 5 minutes; gaps over 10 minutes, the window's edges included."""
    if beat is None:
        return None
    expected = int((end - start).total_seconds() // 300)
    gaps = list(beat.get("gaps") or [])
    day = start.astimezone(tz).date()

    def at(hhmm: str) -> datetime:
        return datetime.combine(day, time.fromisoformat(hhmm), tzinfo=tz)

    if beat.get("first") is None:
        if expected:
            gaps = [{"from": start.astimezone(tz).strftime("%H:%M"),
                     "to": end.astimezone(tz).strftime("%H:%M"),
                     "minutes": int((end - start).total_seconds() // 60)}]
    else:
        lead = (at(beat["first"]) - start).total_seconds() / 60
        tail = (end - at(beat["last"])).total_seconds() / 60
        if lead > 10:
            gaps.insert(0, {"from": start.astimezone(tz).strftime("%H:%M"),
                            "to": beat["first"], "minutes": int(lead)})
        if tail > 10:
            gaps.append({"from": beat["last"], "to": end.astimezone(tz).strftime("%H:%M"),
                         "minutes": int(tail)})
    ok = int(beat.get("ok", 0))
    return {"expected": expected, "seen": int(beat.get("seen", 0)), "ok": ok,
            "failed": int(beat.get("failed", 0)),
            "uptime_pct": round(min(100.0, ok / expected * 100), 2) if expected else None,
            "gaps": gaps}


def ours(p: Page) -> dict:
    from .config import ours_rules, setting
    from .window import day_window

    def figures(d, e):
        blob = (p.extras.get(d) or {}).get("ours")
        if blob is None:
            return {"labels": None, "heartbeat": None, "hours": None}
        start, end = day_window(date.fromisoformat(d), p.tz)
        return {"labels": blob.get("labels", {}), "hours": blob.get("hours", {}),
                "heartbeat": _heartbeat(blob.get("heartbeat"), start, end, p.tz)}

    today = p.today_block()
    if today is not None and p.live_ok:
        blob = (p.snap.get("extras") or {}).get("ours") or {}
        start = datetime.fromisoformat(p.snap["from"])
        end = datetime.fromisoformat(p.snap.get("until") or p.snap["generated_at"])
        today.update({"labels": blob.get("labels", {}), "hours": blob.get("hours", {}),
                      "heartbeat": _heartbeat(blob.get("heartbeat"), start, end, p.tz)})
    return {"rules": ours_rules(p.config),
            "heartbeat_label": str(setting(p.config, "report", "heartbeat_label", "heartbeat")),
            "api": {"list": "ours", "add": "ours/add", "remove": "ours/remove",
                    "add_mine": "ours/add-mine", "pause": "ours/pause",
                    "resume": "ours/resume", "edit": "ours/edit"},
            # An outside uptime check (from another server) is not set up:
            # null says so, beside our own heartbeat (DATA-CONTRACT.md).
            "outside": None,
            "days": p.per_day(figures), "today": today}


BUILDERS = {"overview": overview, "live": live, "visits": visits, "hourly": hourly,
            "breakdowns": breakdowns, "health": health, "bots": bots, "ours": ours}


def files() -> tuple[str, ...]:
    """Every data file written beside a page: FILES and release 2's."""
    from . import data_more
    return FILES + tuple(n for n in data_more.FILES if n in data_more.builders())


def write(folder: Path, page: Page) -> list[Path]:
    """Every data file for one page, into <folder>/data/. Paths written.

    An optional file whose builder fails is written as an error and the rest
    go on (builders.py); quality.json, written last, lists the failures."""
    from . import data_more, data_reports
    from .builders import Failures, build_one
    builders = {**BUILDERS, **data_reports.BUILDERS, **data_more.builders()}
    failures = Failures(page.live_dir)
    page.failures = failures
    names = [n for n in files() if n != "quality"] + ["quality"]
    written = []
    for name in names:
        body = {**page.envelope(), **build_one(name, builders[name], page, failures)}
        path = Path(folder) / "data" / f"{name}.json"
        write_atomic(path, json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n")
        written.append(path)
    failures.save()
    return written
