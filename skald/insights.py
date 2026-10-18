"""Findings worked out from history: what is working, what dropped, what is new.

Recomputed on every daily run and every live run, from the same totals the
dashboard shows, so every number in an insight is a sum of stored figures
(tests/test_insights.py recomputes them). Six kinds:

  working      rising pages, sources, countries, assistants, campaigns,
               referring sites: week on week and 30 days on 30
  dropped      the same, falling
  new          first seen in all of history: pages read, referring sites,
               assistants and crawlers, countries, campaigns, 404 paths
  gone         sources that sent readers before and none now
  anomaly      yesterday against the 14 days before it (median and MAD, so
               one odd day does not move the baseline): readers, AI
               fetches, bots, search crawls, 5xx; and crawler surges
  opportunity  pages assistants fetch often that few people reach; landing
               pages people leave at once; 404s people reach from a real
               link (worth a redirect)

Only whole, verified days are compared: a period with a withheld, missing
or partial day is not compared at all. Thresholds (`insights:` in the
config) keep small numbers out: min_after (default 5), min_change (20%);
"new" needs min_history_days (7) of stored days before it.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from statistics import median

from .labels import shown_text

ORDER = {"anomaly": 0, "opportunity": 1, "working": 2, "dropped": 3, "new": 4, "gone": 5}

# subject kind -> (counts kind or extras source, metric, filter field)
SUBJECTS = {
    "page": ("pages.readers", "readers", "path"),
    "source": ("reader_source", "readers", "source"),
    "country": ("reader_country", "readers", "country"),
    "referrer": ("reader_referrer", "readers", "referrer"),
    "assistant": ("cited_by", "readers", "assistant"),
    "campaign": ("campaigns.utm_campaign", "visits", "utm_campaign"),
    "crawler": ("engines", "ai_fetches", "assistant"),
}
NOT_A_SUBJECT = {"(none)", "(this site)", "(all others)", "Unknown", "(no campaign tag)"}


def settings(config: dict) -> dict:
    got = (config or {}).get("insights") or {}
    return {"min_after": int(got.get("min_after", 5)),
            "min_change": float(got.get("min_change", 20)),
            "min_new": int(got.get("min_new", 3)),
            "min_history_days": int(got.get("min_history_days", 7))}


class Source:
    """Per-day counters for a history key, read once."""

    def __init__(self, history, key: str, first: date, last: date) -> None:
        self.history, self.key = history, key
        self.states = {e["day"].isoformat(): e for e in history.daily(key, first, last)}
        days = [d for d, e in self.states.items() if e["state"] in ("ok", "partial")]
        kinds = ["reader_source", "reader_country", "reader_referrer", "cited_by",
                 "engine_training", "engine_asked", "status_people", "status_bots"]
        kinds += [f"status_{g}" for g in ("answer_engines", "search_engines", "ours")]
        self.counts: dict[str, dict[str, Counter]] = {}
        for d, kind, name, n in history.count_rows(key, kinds, days):
            self.counts.setdefault(d, {}).setdefault(kind, Counter())[name] = n
        self.extras = history.extras(key, first, last, ("pages", "campaigns", "not_found"))

    def whole(self, first: date, last: date) -> bool:
        d = first
        while d <= last:
            e = self.states.get(d.isoformat())
            if e is None or e["state"] != "ok":
                return False
            d += timedelta(days=1)
        return True

    def counter(self, what: str, d: str) -> Counter:
        if what == "pages.readers":
            pages = (self.extras.get(d) or {}).get("pages") or {}
            return Counter({p: v.get("readers", 0) for p, v in pages.items()})
        if what == "campaigns.utm_campaign":
            rows = ((self.extras.get(d) or {}).get("campaigns") or {}).get("rows") or {}
            return Counter({r["name"]: r["visits"] for r in rows.get("utm_campaign", [])})
        if what == "engines":
            c = self.counts.get(d, {})
            return c.get("engine_training", Counter()) + c.get("engine_asked", Counter())
        return Counter(self.counts.get(d, {}).get(what, Counter()))

    def total(self, what: str, first: date, last: date) -> Counter:
        out = Counter()
        d = first
        while d <= last:
            out.update(self.counter(what, d.isoformat()))
            d += timedelta(days=1)
        return out

    def day_metric(self, metric: str, d: str) -> int | None:
        e = self.states.get(d)
        if e is None or e["state"] != "ok":
            return None
        g = e["groups"]
        from .classify import Group
        if metric == "readers":
            return g[Group.PEOPLE]["readers"]
        if metric == "ai_fetches":
            return g[Group.ANSWER_ENGINE]["hits"]
        if metric == "bots":
            return g[Group.BOTS]["hits"]
        if metric == "search":
            return g[Group.SEARCH_ENGINE]["hits"]
        if metric == "server_errors":
            c = self.counts.get(d, {})
            return sum(int(c.get(f"status_{x}", {}).get("5xx", 0)) for x in
                       ("people", "answer_engines", "search_engines", "bots", "ours"))
        return None


def _pct(before: float, after: float) -> float | None:
    return round((after - before) / before * 100, 1) if before else None


def _confidence(before: float, after: float, floor: int) -> str:
    low = min(before, after) if before else after
    return "high" if low >= 4 * floor else "medium" if low >= 2 * floor else "low"


def _insight(kind, title, metric, subject, before, after, since, period, filt, floor):
    # The title is for a person: a stored label in it is said as shown (labels.py).
    return {"type": kind, "title": shown_text(title), "metric": metric,
            "subject": subject, "before": before, "after": after,
            "change_pct": _pct(before or 0, after or 0) if before is not None else None,
            "confidence": _confidence(before or 0, after or 0, floor),
            "filter": filt, "since": since,
            "period": {"after": period[0], "before": period[1]}}


def compare(src: Source, anchor: date, span: int, cfg: dict) -> list[dict]:
    """Working, dropped and gone over `span` days against the span before."""
    after = (anchor - timedelta(days=span - 1), anchor)
    before = (after[0] - timedelta(days=span), after[0] - timedelta(days=1))
    if not (src.whole(*after) and src.whole(*before)):
        return []
    words = "week on week" if span == 7 else f"{span} days on the {span} before"
    period = ([after[0].isoformat(), after[1].isoformat()],
              [before[0].isoformat(), before[1].isoformat()])
    out = []
    for kind, (what, metric, field) in SUBJECTS.items():
        now, then = src.total(what, *after), src.total(what, *before)
        for name in sorted(set(now) | set(then)):   # sorted: the same order every run
            if name in NOT_A_SUBJECT:
                continue
            a, b = int(now.get(name, 0)), int(then.get(name, 0))
            change = _pct(b, a)
            subject = {"kind": kind, "name": name}
            filt = {field: name}
            if b >= cfg["min_after"] and a == 0 and kind in ("source", "referrer", "assistant",
                                                             "campaign"):
                out.append(_insight("gone", f"{name}: no {metric} in the last {span} days "
                                    f"(was {b:,})", metric, subject, b, a,
                                    after[0].isoformat(), period, filt, cfg["min_after"]))
            elif change is not None and a >= cfg["min_after"] and change >= cfg["min_change"]:
                out.append(_insight("working", f"{name}: {metric} up {change:.0f}% {words} "
                                    f"({b:,} to {a:,})", metric, subject, b, a,
                                    after[0].isoformat(), period, filt, cfg["min_after"]))
            elif change is not None and b >= cfg["min_after"] and change <= -cfg["min_change"]:
                out.append(_insight("dropped", f"{name}: {metric} down {-change:.0f}% {words} "
                                    f"({b:,} to {a:,})", metric, subject, b, a,
                                    after[0].isoformat(), period, filt, cfg["min_after"]))
    return out


def new_things(src: Source, day: date, first_day: date, cfg: dict,
               today: dict | None = None) -> list[dict]:
    """Subjects with at least min_new on `day` (or today so far) never seen
    on any stored day before it."""
    out = []
    labels = dict(SUBJECTS)
    labels["404 path"] = ("not_found", "requests", "path")
    seen: dict[str, set] = {k: set() for k in labels}
    d, known = first_day, 0
    while d < day:
        known += 1 if (src.states.get(d.isoformat()) or {}).get("state") in ("ok", "partial") else 0
        for kind, (what, _, _) in labels.items():
            seen[kind] |= set(_day_counter(src, what, d.isoformat()))
        d += timedelta(days=1)
    if known < cfg["min_history_days"]:
        return []                       # too little history: everything would be "new"
    for kind, (what, metric, field) in labels.items():
        got = (today or {}).get(what) if today is not None else _day_counter(src, what,
                                                                             day.isoformat())
        for name, n in Counter(got or {}).items():
            if name in NOT_A_SUBJECT or name in seen[kind] or n < cfg["min_new"]:
                continue
            out.append(_insight("new", f"New {kind}: {name} ({n:,} {metric})", metric,
                                {"kind": kind, "name": name}, None, int(n), day.isoformat(),
                                ([day.isoformat(), day.isoformat()], None), {field: name},
                                cfg["min_new"]))
    return out


def _day_counter(src: Source, what: str, d: str) -> Counter:
    if what == "not_found":
        rows = (src.extras.get(d) or {}).get("not_found") or []
        return Counter({r["path"]: r["n"] for r in rows
                        if r["group"] == "people" and not r["probe"]})
    return src.counter(what, d)


def anomalies(src: Source, day: date, cfg: dict) -> list[dict]:
    """`day` against the 14 days before it, median and MAD; whole days only."""
    out = []
    for metric in ("readers", "ai_fetches", "bots", "search", "server_errors"):
        x = src.day_metric(metric, day.isoformat())
        base = [v for v in (src.day_metric(metric, (day - timedelta(days=i)).isoformat())
                            for i in range(1, 15)) if v is not None]
        if x is None or len(base) < 7:
            continue
        med = median(base)
        mad = median(abs(v - med) for v in base) * 1.4826 or 1.0
        if abs(x - med) >= max(cfg["min_after"], 3 * mad):
            word = "spike" if x > med else "drop"
            out.append(_insight("anomaly", f"{metric.replace('_', ' ')}: {word} on {day:%a %d %b}, "
                                f"{x:,} against a usual {med:,.0f}", metric,
                                {"kind": "site", "name": metric}, round(med, 1), x,
                                day.isoformat(), ([day.isoformat()] * 2,
                                                  [(day - timedelta(days=14)).isoformat(),
                                                   (day - timedelta(days=1)).isoformat()]),
                                {}, cfg["min_after"]))
    return out


def opportunities(src: Source, anchor: date, cfg: dict) -> list[dict]:
    first = anchor - timedelta(days=29)
    period = ([first.isoformat(), anchor.isoformat()], None)
    pages: dict[str, Counter] = {}
    d = first
    while d <= anchor:
        e = src.states.get(d.isoformat())
        if e is not None and e["state"] == "ok":
            for path, v in ((src.extras.get(d.isoformat()) or {}).get("pages") or {}).items():
                pages.setdefault(path, Counter()).update(
                    {k: int(v.get(k, 0)) for k in ("readers", "ai_asked", "ai_training",
                                                   "entries", "after_pages")})
        d += timedelta(days=1)
    out = []
    floor = cfg["min_after"]
    for path, c in pages.items():
        ai = c["ai_asked"] + c["ai_training"]
        if ai >= 4 * floor and c["readers"] <= max(1, ai // 50):
            out.append(_insight("opportunity", f"{path}: assistants fetched it {ai:,} times in "
                                f"30 days, {c['readers']:,} people read it", "ai_fetches",
                                {"kind": "page", "name": path}, ai, c["readers"],
                                first.isoformat(), period, {"path": path}, floor))
        if c["entries"] >= 2 * floor and c["after_pages"] * 5 <= c["entries"]:
            out.append(_insight("opportunity", f"{path}: {c['entries']:,} visits started here "
                                f"and almost none went on ({c['after_pages']:,} more pages)",
                                "entries", {"kind": "page", "name": path}, c["entries"],
                                c["after_pages"], first.isoformat(), period, {"path": path}, floor))
    linked = Counter()
    for day, blobs in src.extras.items():
        if first.isoformat() <= day <= anchor.isoformat():
            for r in blobs.get("not_found") or []:
                if r["group"] == "people" and not r["probe"] and r["source"] not in (
                        "(none)", "(this site)"):
                    linked[r["path"]] += r["n"]
    for path, n in linked.items():
        if n >= 2:
            out.append(_insight("opportunity", f"{path}: {n:,} people reached this 404 from a "
                                f"link elsewhere - redirect it", "not_found",
                                {"kind": "path", "name": path}, None, n, first.isoformat(),
                                period, {"path": path}, 2))
    return out


def compute(history, key: str, anchor: date, config: dict, snap: dict | None = None) -> dict:
    """{"insights": [...], "today": [...]} for a history key."""
    cfg = settings(config)
    first_day = history.first_day(key)
    if first_day is None:
        return {"insights": [], "today": []}
    first = max(first_day, anchor - timedelta(days=89))
    src = Source(history, key, first, anchor)
    found = compare(src, anchor, 7, cfg) + compare(src, anchor, 30, cfg)
    found += new_things(src, anchor, first, cfg) + anomalies(src, anchor, cfg)
    found += opportunities(src, anchor, cfg)
    # The title breaks ties, so equal insights come out in the same order every run.
    found.sort(key=lambda i: (ORDER[i["type"]], -abs((i["after"] or 0) - (i["before"] or 0)),
                              i["title"]))
    today = []
    if snap and snap.get("state") == "ok":
        extras = snap.get("extras") or {}
        people = snap.get("people") or {}
        by = (snap.get("breakdowns") or {}).get("by") or {}
        live = {"pages.readers": {p: v.get("readers", 0) for p, v in
                                  (extras.get("pages") or {}).items()},
                "reader_source": by.get("source"), "reader_country": by.get("country"),
                "reader_referrer": by.get("referrer"), "cited_by": people.get("cited_by"),
                "engines": {**(snap.get("ai") or {}).get("training", {}),
                            **(snap.get("ai") or {}).get("asked", {})},
                "campaigns.utm_campaign": {r["name"]: r["visits"] for r in
                                           ((extras.get("campaigns") or {}).get("rows") or {})
                                           .get("utm_campaign", [])},
                "not_found": {r["path"]: r["n"] for r in extras.get("not_found") or []
                              if r["group"] == "people" and not r["probe"]}}
        today = new_things(src, anchor + timedelta(days=1), first, cfg, live)
        for i in today:
            i["confidence"] = "low"
    return {"insights": found, "today": today}


def top_lines(result: dict, n: int) -> list[str]:
    return [f"{i['type'].upper():<12} {i['title']}" for i in result.get("insights", [])[:n]]
