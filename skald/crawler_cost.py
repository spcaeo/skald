"""What each crawler costs: the day kind `crawler_cost` and crawler_cost.json.

Per crawler, assistant or bot name, per day: what it asked the server for
and what that took. Built in the tally pass (extras.Extras offers every
counted hit to Costs.add) for the three machine groups classify.py gives:

  answer_engines   by the assistant's name (verdict.engine)
  search_engines   by the crawler's name (verdict.engine)
  bots             by the name the bots list uses (verdict.engine, else the
                   short name its user agent announces, aggregate._short_agent);
                   a scanner probe with no other name is "(scanner probes)"

Per name (DATA-CONTRACT.md, "crawler_cost"):

  requests   every request it made
  bytes      the body bytes sent, summed over the lines that logged a size;
             None (not recorded) when none of its lines had one
  sized      how many of its lines had a size: below `requests`, `bytes` is
             a partial sum and is labelled so
  ms, timed  the response times in whole milliseconds, summed, over the
             `timed` lines that logged one; ms None when timed is 0
  p90_ms     the 90th percentile of those times (nearest rank: the smallest
             time at least 90% of its timed lines took no longer than);
             None when timed is 0
  status     requests by status class ("2xx", "3xx", "4xx", "5xx", ...)
  paths      distinct paths (no query string, first 200 characters)
  pages      its top PAGES paths and "(all others)": adds up to requests
  countries  its requests by the line's country (cc= or the GeoIP file),
             "Unknown" for none; top LISTS and "(all others)"
  agents     the user-agent strings it sent, top AGENTS and "(all others)":
             a named crawler's own strings only. None (not kept) for the
             names whose strings may be a person's browser: scanner probes,
             link previews (iMessage sends the sender's Safari string),
             browser-like crawler sessions, visits that never rendered, and
             the short names "browser-like agent" and the Googlebot template
  last       its last request of the day, UTC ISO 8601

Each group keeps its TOP names by requests; the rest are folded into one
"(all others)" entry per group with the summable figures (requests, bytes,
sized, ms, timed, status) and `names`, how many were folded. So each group's
entries add up to that group's requests (check()). No address is kept.

The second count is audit_crawler_cost.py.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta, timezone

from .classify import AI_ASKED, CRAWLER_SESSION, LINK_PREVIEW, NOT_RENDERED, Group

TOP = 50
PAGES = 10
LISTS = 10
AGENTS = 5
OTHER = "(all others)"
PROBES = "(scanner probes)"
NO_AGENT = "(no user agent)"
UNKNOWN = "Unknown"
GROUPS = (Group.ANSWER_ENGINE, Group.SEARCH_ENGINE, Group.BOTS)
SUMMED = ("requests", "bytes", "sized", "ms", "timed")
# Bots whose user-agent strings are not kept: they may be a person's browser.
NO_AGENTS = (PROBES, NOT_RENDERED, CRAWLER_SESSION, "browser-like agent",
             "Googlebot template, no Googlebot")


def keeps_agents(group: str, name: str) -> bool:
    return group != Group.BOTS.value or not (name in NO_AGENTS or name.startswith(LINK_PREVIEW))


def name_of(hit, verdict) -> str:
    """The name a request is filed under (its group is the verdict's)."""
    if verdict.engine:
        return verdict.engine
    if verdict.group is Group.BOTS:
        if verdict.probe:
            return PROBES
        from .aggregate import _short_agent
        return _short_agent(hit.user_agent)
    return "(unnamed)"


def p90(values: list[int]) -> int | None:
    """Nearest rank: the value at position ceil(0.9 n) of the sorted list."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[-(-9 * len(ordered) // 10) - 1]


def _fold(counter: Counter, keep: int) -> dict:
    kept = dict(counter.most_common(keep))
    rest = sum(counter.values()) - sum(kept.values())
    if rest:
        kept[OTHER] = kept.get(OTHER, 0) + rest
    return {str(k): int(v) for k, v in kept.items()}


class _Name:
    __slots__ = ("requests", "bytes", "sized", "ms", "status", "pages", "countries",
                 "agents", "last")

    def __init__(self) -> None:
        self.requests = self.bytes = self.sized = 0
        self.ms: list[int] = []
        self.status: Counter = Counter()
        self.pages: Counter = Counter()
        self.countries: Counter = Counter()
        self.agents: Counter = Counter()
        self.last = None


class Costs:
    """Fed every counted hit (extras.Extras.add)."""

    def __init__(self) -> None:
        self.per: dict[tuple[str, str], _Name] = {}

    def add(self, hit, verdict) -> None:
        if verdict.group not in GROUPS:
            return
        key = (verdict.group.value, name_of(hit, verdict))
        got = self.per.get(key)
        if got is None:
            got = self.per[key] = _Name()
        got.requests += 1
        if hit.size is not None:
            got.sized += 1
            got.bytes += int(hit.size)
        if hit.request_time is not None:
            got.ms.append(int(round(hit.request_time * 1000)))
        got.status[f"{hit.status[:1]}xx"] += 1
        got.pages[hit.path[:200]] += 1
        got.countries[(hit.country or "").upper() or UNKNOWN] += 1
        got.agents[(hit.user_agent or NO_AGENT)[:200]] += 1
        when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
        if got.last is None or when > got.last:
            got.last = when

    def finish(self) -> dict:
        groups: dict[str, dict] = {}
        for g in GROUPS:
            mine = {name: got for (grp, name), got in self.per.items() if grp == g.value}
            if not mine:
                continue
            ranked = sorted(mine, key=lambda n: (-mine[n].requests, n))
            out = {name: _entry(mine[name], keeps_agents(g.value, name))
                   for name in ranked[:TOP]}
            rest = ranked[TOP:]
            if rest:
                fold = {k: 0 for k in SUMMED}
                status: Counter = Counter()
                last = None
                for name in rest:
                    e = mine[name]
                    fold["requests"] += e.requests
                    fold["bytes"] += e.bytes
                    fold["sized"] += e.sized
                    fold["ms"] += sum(e.ms)
                    fold["timed"] += len(e.ms)
                    status.update(e.status)
                    last = e.last if last is None or e.last > last else last
                out[OTHER] = {**fold, "bytes": fold["bytes"] if fold["sized"] else None,
                              "ms": fold["ms"] if fold["timed"] else None, "p90_ms": None,
                              "status": dict(status), "paths": None, "names": len(rest),
                              "last": _iso(last)}
            groups[g.value] = out
        return {"groups": groups}


def _iso(when) -> str | None:
    return when.astimezone(timezone.utc).isoformat(timespec="seconds") if when else None


def _entry(e: _Name, agents: bool) -> dict:
    return {"requests": e.requests, "bytes": e.bytes if e.sized else None, "sized": e.sized,
            "ms": sum(e.ms) if e.ms else None, "timed": len(e.ms), "p90_ms": p90(e.ms),
            "status": dict(e.status), "paths": len(e.pages),
            "pages": _fold(e.pages, PAGES), "countries": _fold(e.countries, LISTS),
            "agents": _fold(e.agents, AGENTS) if agents else None, "last": _iso(e.last)}


# ---------------------------------------------------- day_more registry

def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    costs = getattr(extras, "crawler_cost", None)
    return None if costs is None else costs.finish()


def check(totals, blob, differs, problems) -> None:
    """Each group's names add up to the group's requests; each name's
    statuses, pages, countries and agents add up to its requests; a figure
    with no line behind it is None, never 0."""
    from .verify import Problem
    groups = blob.get("groups") or {}
    for g in GROUPS:
        stats = totals.groups.get(g)
        differs(f"crawler_cost: {g.value} requests by name",
                sum(int(e["requests"]) for e in (groups.get(g.value) or {}).values()),
                stats.hits if stats else 0, "requests")
    for grp, names in groups.items():
        for name, e in names.items():
            n = int(e["requests"])
            differs(f"crawler_cost: {name}: requests by status",
                    sum(int(v) for v in (e.get("status") or {}).values()), n, "requests")
            for key in ("pages", "countries", "agents"):
                if name != OTHER and (key != "agents" or keeps_agents(grp, name)):
                    differs(f"crawler_cost: {name}: requests by {key}",
                            sum(int(v) for v in (e.get(key) or {}).values()), n, "requests")
            bad = []
            if name != OTHER and (e.get("agents") is not None) != keeps_agents(grp, name):
                bad.append("user agents kept where they must not be, or missing")
            if not 0 <= int(e["sized"]) <= n or not 0 <= int(e["timed"]) <= n:
                bad.append("more lines with a size or a time than requests")
            if (e.get("bytes") is None) != (int(e["sized"]) == 0):
                bad.append("bytes recorded without a sized line, or 0 for none")
            if (e.get("ms") is None) != (int(e["timed"]) == 0):
                bad.append("a time recorded without a timed line, or 0 for none")
            if name != OTHER and (e.get("p90_ms") is None) != (int(e["timed"]) == 0):
                bad.append("p90 without a timed line")
            if name != OTHER and not (len([p for p in e.get("pages") or {} if p != OTHER])
                                      <= int(e["paths"]) <= n):
                bad.append("distinct paths outside its pages and requests")
            for why in bad:
                problems.append(Problem("crawler_cost", f"{grp} {name}: {why}"))


# ---------------------------------------------------- crawler_cost.json

DETAIL_DAYS = 30
COMPACT = ("requests", "bytes", "sized", "ms", "timed", "p90_ms", "status", "paths", "last")


def _compact(blob: dict | None, detail: bool) -> dict | None:
    """{group: {name: figures}}: every figure; the lists only on `detail` days."""
    if blob is None:
        return None
    out: dict[str, dict] = {}
    for grp, names in (blob.get("groups") or {}).items():
        for name, e in names.items():
            row = {k: e.get(k) for k in COMPACT}
            if grp == Group.ANSWER_ENGINE.value and name != OTHER:
                row["tier"] = "asked" if AI_ASKED.fullmatch(name) else "training"
            if name == OTHER:
                row["names"] = e.get("names")
            elif detail:
                row.update({k: e.get(k) for k in ("pages", "countries", "agents")})
            out.setdefault(grp, {})[name] = row
    return out


def build(p) -> dict:
    """crawler_cost.json: per day (180 days) every name's figures, with its
    pages, countries and agents for the last DETAIL_DAYS days and today."""
    blobs = p.history.extras(p.key, p.first, p.anchor, ("crawler_cost",))
    since = (p.anchor - timedelta(days=DETAIL_DAYS - 1)).isoformat()
    days = []
    for e in p.daily:
        row = p.day_entry(e)
        if p.has_figures(e):
            d = e["day"].isoformat()
            row["names"] = _compact((blobs.get(d) or {}).get("crawler_cost"), d >= since)
        days.append(row)
    today = p.today_block()
    if today is not None and p.live_ok:
        today["names"] = _compact((p.snap.get("extras") or {}).get("crawler_cost"), True)
    return {"days": days, "today": today, "detail_days": DETAIL_DAYS,
            "top": TOP, "lists": {"pages": PAGES, "countries": LISTS, "agents": AGENTS}}
