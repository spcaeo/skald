"""Leads and bookings everywhere (2.5.0): the parts of conversions.json and
insights.json that put leads beside the visitors, from the same rows the
Conversions tab counts.

A lead is a finished (completed or paid) conversion of one of
conversions.LEAD_ACTIONS: a form sent or a demo booked; DEMO_ACTIONS are
also shown on their own, as demos booked. A row marked test is never a
lead: it is listed, marked, and never counted.

    today_block    conversions.json `today`: today's rows of the lead
                   actions (every stage), newest first, test rows marked.
                   A listing; withheld with today's day
    insights       lead findings for insights.json, from conversions.json's
                   `ok` days only, by insights.py's rules (whole periods,
                   min_after, min_change, confidence)

Counted here in Python from plain SELECTs and the file's own days.
audit_conversions_leads.py counts the same again by SQL GROUP BY over the
file opened read-only; a listing or an insight it disagrees with is
withheld (the listing) or left out and named (an insight).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from .conversions import DEMO_ACTIONS, FINISHED, LEAD_ACTIONS, UNKNOWN

TODAY_ROWS = 100
# subject kind -> (conversions.json `by` dimension, the filter field the app applies)
SUBJECTS = {"source": ("source_type", "source"), "page": ("landing", "path"),
            "country": ("country", "country")}
NOT_A_SUBJECT = {UNKNOWN, "(none)", "(this site)", "(all others)", "(no campaign tag)"}
TOP_KINDS = ("page", "source")


# ------------------------------------------------------------- today

def today_block(db, site: str, tz, today: date, held: set) -> dict:
    """Today's rows of the lead actions, every stage, newest first (at most
    TODAY_ROWS): {"day","state":"ok","total","tests","rows"} or, when today
    is withheld, {"day","state":"withheld","why"}. Anonymous: no visitor ID,
    no name, no email."""
    from .conversions_data import _local, _stamp
    day = today.isoformat()
    if day in held:
        return {"day": day, "state": "withheld",
                "why": "today's conversions are withheld: the second count disagrees"}
    lo, hi = _stamp(today, tz), _stamp(today + timedelta(days=1), tz)
    found = [r for r in db.execute("SELECT * FROM conversions WHERE site = ? AND at >= ? AND "
                                   "at < ? ORDER BY at DESC, id DESC", (site, lo, hi))
             if r["action"] in LEAD_ACTIONS]
    rows = [{"at": _local(r["at"], tz), "action": r["action"], "stage": r["stage"],
             "tool": r["tool"], "source": r["source_type"], "first_source": r["first_source"],
             "campaign": r["campaign"], "landing": r["landing"], "country": r["country"],
             "device": r["device"], "test": bool(r["test"])} for r in found[:TODAY_ROWS]]
    return {"day": day, "state": "ok", "total": len(found),
            "tests": sum(1 for r in found if r["test"]), "rows": rows}


# ---------------------------------------------------------- insights

def day_leads(day: dict) -> int:
    """A conversions.json `ok` day's leads: finished rows of the lead actions."""
    return sum(n for action, per in (day.get("stages") or {}).items()
               if action in LEAD_ACTIONS for stage, n in per.items() if stage in FINISHED)


def day_demos(day: dict) -> int:
    return sum(n for action, per in (day.get("stages") or {}).items()
               if action in DEMO_ACTIONS for stage, n in per.items() if stage in FINISHED)


def day_by(day: dict, dim: str) -> Counter:
    out: Counter = Counter()
    for action, per in ((day.get("by") or {}).get(dim) or {}).items():
        if action in LEAD_ACTIONS:
            out.update(per)
    return out


class Days:
    """conversions.json's days, read for sums over whole periods."""

    def __init__(self, blob: dict) -> None:
        self.at = {d["day"]: d for d in blob.get("days") or [] if isinstance(d, dict)}

    def whole(self, first: date, last: date) -> bool:
        d = first
        while d <= last:
            if (self.at.get(d.isoformat()) or {}).get("state") != "ok":
                return False
            d += timedelta(days=1)
        return True

    def _each(self, first: date, last: date):
        d = first
        while d <= last:
            yield self.at[d.isoformat()]
            d += timedelta(days=1)

    def leads(self, first: date, last: date) -> int:
        return sum(day_leads(e) for e in self._each(first, last))

    def by(self, dim: str, first: date, last: date) -> Counter:
        out: Counter = Counter()
        for e in self._each(first, last):
            out.update(day_by(e, dim))
        return out


def _title(kind: str, name: str) -> str:
    if kind == "site":
        return "Leads"
    if kind == "page":
        return f"Leads that started on {name}"
    return f"Leads from {name}"


def insights(blob: dict | None, anchor: date, config: dict) -> list[dict]:
    """Lead findings, by insights.py's rules: working, dropped and gone over
    7 and 30 days against the span before (both whole: every day `ok` in
    conversions.json), for all leads and per source (last touch), landing
    page and country; and the source and landing page that sent the most
    leads over the last 30 whole days, when one leads alone with at least
    min_after. Sorted by the caller."""
    from .insights import _insight, _pct, settings
    if not blob or not blob.get("available"):
        return []
    cfg = settings(config)
    days = Days(blob)
    floor = cfg["min_after"]
    out = []
    for span in (7, 30):
        after = (anchor - timedelta(days=span - 1), anchor)
        before = (after[0] - timedelta(days=span), after[0] - timedelta(days=1))
        if not (days.whole(*after) and days.whole(*before)):
            continue
        words = "week on week" if span == 7 else f"{span} days on the {span} before"
        period = ([after[0].isoformat(), after[1].isoformat()],
                  [before[0].isoformat(), before[1].isoformat()])
        tables = [("site", "leads", {"leads": days.leads(*after)}, {"leads": days.leads(*before)})]
        for kind, (dim, _) in SUBJECTS.items():
            tables.append((kind, dim, days.by(dim, *after), days.by(dim, *before)))
        for kind, dim, now, then in tables:
            for name in sorted(set(now) | set(then)):     # sorted: the same order every run
                if name in NOT_A_SUBJECT:
                    continue
                a, b = int(now.get(name, 0)), int(then.get(name, 0))
                change = _pct(b, a)
                subject = {"kind": kind, "name": name}
                filt = {} if kind == "site" else {SUBJECTS[kind][1]: name}
                title = _title(kind, name)
                got = None
                if b >= floor and a == 0 and kind == "source":
                    got = _insight("gone", f"{title}: none in the last {span} days (was {b:,})",
                                   "leads", subject, b, a, after[0].isoformat(), period, filt,
                                   floor)
                elif change is not None and a >= floor and change >= cfg["min_change"]:
                    got = _insight("working", f"{title} up {change:.0f}% {words} ({b:,} to "
                                   f"{a:,})", "leads", subject, b, a, after[0].isoformat(),
                                   period, filt, floor)
                elif change is not None and b >= floor and change <= -cfg["min_change"]:
                    got = _insight("dropped", f"{title} down {-change:.0f}% {words} ({b:,} to "
                                   f"{a:,})", "leads", subject, b, a, after[0].isoformat(),
                                   period, filt, floor)
                if got is not None:
                    out.append(got)
    first = anchor - timedelta(days=29)
    if days.whole(first, anchor):
        period = ([first.isoformat(), anchor.isoformat()], None)
        for kind in TOP_KINDS:
            dim, field = SUBJECTS[kind]
            got = Counter({k: v for k, v in days.by(dim, first, anchor).items()
                           if k not in NOT_A_SUBJECT and v})
            ranked = sorted(got.items(), key=lambda kv: (-kv[1], kv[0]))
            if not ranked or ranked[0][1] < floor or (len(ranked) > 1 and
                                                      ranked[1][1] == ranked[0][1]):
                continue
            name, a = ranked[0]
            whole = days.leads(first, anchor)
            what = "the page that started" if kind == "page" else "the source that sent"
            item = _insight("working", f"{name} is {what} the most leads: {a:,} of {whole:,} "
                            f"in 30 days", "leads", {"kind": kind, "name": name}, None, a,
                            first.isoformat(), period, {field: name}, floor)
            item["of"] = whole
            item["top"] = True
            out.append(item)
    return out


def add_to(found: dict, blob: dict | None, anchor: date, config: dict, path, site: str,
           tz) -> dict:
    """insights.json with the lead findings added, each checked by the
    second count (audit_conversions_leads.check_insights); one it disagrees
    with is left out and named in `leads_withheld`. Sorted as insights.py
    sorts: type, size of the change, title."""
    from .insights import ORDER
    items = insights(blob, anchor, config)
    held: list[str] = []
    if items:
        from . import audit_conversions_leads
        try:
            bad = audit_conversions_leads.check_insights(path, site, tz, items)
        except Exception as why:        # noqa: BLE001 - unchecked findings are left out
            bad = {i: [f"the recount could not run: {type(why).__name__}: {why}"]
                   for i in range(len(items))}
        held = [f"{items[i]['title']}: {'; '.join(p)}" for i, p in sorted(bad.items())]
        items = [x for i, x in enumerate(items) if i not in bad]
    out = dict(found)
    out["insights"] = sorted([*found.get("insights", []), *items], key=lambda i: (
        ORDER[i["type"]], -abs((i["after"] or 0) - (i["before"] or 0)), i["title"]))
    out["leads_withheld"] = held
    return out
