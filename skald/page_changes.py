"""page_changes.json: "did my change work?" for the pages someone marked changed
(Traffic > Pages > a page, and Overview > Insights' "Done, and did it work?").

A mark (todo_marks.py: "I changed this page on <day>", with what changed and a
note) is compared over the same number of whole days before and after it. The day
of the change is in neither side (it changed during that day). The after side is
the whole days from the day after the change to yesterday, at most MAX_DAYS; the
before side the same number of days just before the change. Until MIN_DAYS whole
days have passed the verdict is "too early to tell", with the day it comes.

Nothing new is counted here: each day's figure is a stored, audited day figure
put side by side, for the page (every spelling of it: with or without the
trailing slash or a query, page_trends.key):

  visits   visits that started on the page (day kind `landings`, "visits")
  left     of them, the share that left at once, one page view (`landings`,
           "one_page" over "visits"); a lower figure is better
  search   of the visits, from a search engine (`landings`, "search")
  ai       of the visits, from an AI assistant, a proven citation (`landings`, "ai")
  reads    AI reads: assistants answering a user reading the page (day kind
           `ai_fetches`, the reads column of every row of the page; a page
           asked for again within ai_read_names.WINDOW_SECONDS is one read,
           ai_reads.py). A day stored before reads were counted: not recorded
  leads    finished leads and conversions whose landing page is the page
           (conversions.json's audited days, `by.landing`, every action)

A day counts for a figure only when it is a whole, verified day ("ok") with that
figure recorded; anything else is not recorded (null, never 0). A day whose
landings keep their top pages only, without this page, is a floor (`at_least`).
When the two sides have a figure on a different number of days, they are compared
per day and the file says so (`unequal`). Per side: the days with the figure, the
total and the figure per day (left at once: the visits, the one-page visits and
the share).

The verdict, per figure, once MIN_DAYS have passed: "not_recorded" (a side has no
day with it), "not_enough_days" (a side has fewer than MIN_SIDE), "too_few" (the two
sides count fewer than MIN_TOTAL together; left at once: a side with fewer than
MIN_VISITS visits), "no_clear_change" (the difference per day is within the
day-to-day swing: SWING standard errors of the two sides' daily figures), else
"up" or "down".

A page group (view) gets {"whole_site_only": true}: the marks are the whole site's.
Second count: audit_page_changes.py, by its own SQL over history.sqlite,
conversions.sqlite and the marks; a change it does not find the same is left out
and named in `withheld`.
"""
from __future__ import annotations

from datetime import date, timedelta
from math import sqrt

from .page_trends import OTHER, key

MIN_DAYS = 14           # whole days after the change before a verdict
MAX_DAYS = 28           # at most this many whole days on each side
MIN_SIDE = 7            # a side needs the figure on at least this many days
MIN_TOTAL = 10          # a count: both sides together at least this many
MIN_VISITS = 10         # left at once: each side at least this many visits
SWING = 2.0             # a clear change: more than this many standard errors
# (key, what it is, which way is better)
MEASURES = (("visits", "Visits that started on the page", "up"),
            ("leads", "Leads and conversions that landed on it", "up"),
            ("search", "Visits from a search engine", "up"),
            ("ai", "Visits from an AI assistant", "up"),
            ("reads", "AI reads (assistants fetching it live for a user)", "up"),
            ("left", "Left at once (one page, then gone)", "down"))
COUNTS = ("visits", "leads", "search", "ai", "reads")
RULES = {
    "days": f"the same number of whole days before and after the change, at most {MAX_DAYS}; "
            "the day of the change is in neither",
    "too_early": f"too early to tell until {MIN_DAYS} whole days have passed after the change",
    "clear": f"a change is clear when the difference per day is more than {SWING:g} standard "
             "errors of the two sides' daily figures (the normal day-to-day swing)",
    "few": f"too few: under {MIN_TOTAL} on both sides together (left at once: under "
           f"{MIN_VISITS} visits on a side); not enough days: a side with the figure on fewer "
           f"than {MIN_SIDE} days",
}


def _iso(d: date) -> str:
    return d.isoformat()


def windows(day: date, anchor: date) -> tuple[list[date], list[date]]:
    """(before, after): the whole days on each side of a change on `day`."""
    n = max(0, min(MAX_DAYS, (anchor - day).days))
    after = [day + timedelta(days=i) for i in range(1, n + 1)]
    before = [day - timedelta(days=i) for i in range(n, 0, -1)]
    return before, after


def leads_by_day(conv: dict | None) -> tuple[dict, str | None]:
    """({day: {"state", "landing": {page key: n}}}, why not) from conversions.json's body."""
    if not conv or not conv.get("available"):
        return {}, "no conversions are recorded for this site"
    out = {}
    for d in conv.get("days") or []:
        if d.get("state") != "ok":
            out[d["day"]] = {"state": d.get("state"), "landing": None}
            continue
        per: dict[str, int] = {}
        for _action, pages in ((d.get("by") or {}).get("landing") or {}).items():
            for path, n in pages.items():
                if str(path).startswith("/"):
                    per[key(path)] = per.get(key(path), 0) + int(n)
        out[d["day"]] = {"state": "ok", "landing": per}
    return out, None


def day_row(k: str, d: str, state: str, landings, fetches, conv_day, conv_off: bool) -> dict:
    """One day's figures for the page whose key is `k`."""
    row = {"day": d, "state": state, "visits": None, "one_page": None, "search": None, "ai": None,
           "reads": None, "leads": None, "at_least": False}
    ok = state == "ok"
    if ok and landings is not None:
        pages = landings.get("pages") or {}
        mine = [r for p, r in pages.items() if p != OTHER and key(p) == k]
        got = [sum(int(r[i]) for r in mine) for i in range(5)]
        row.update(visits=got[0], one_page=got[1], search=got[3], ai=got[4])
        row["at_least"] = bool(not mine and int(landings.get("folded") or 0))
    if ok and fetches is not None:
        rows = fetches.get("rows") or []
        mine = [r for r in rows if key(r[2]) == k]
        # Reads (ai_reads.py), not requests; a day stored before they were
        # counted has rows of four columns: not recorded, never 0.
        row["reads"] = sum(int(r[4]) for r in mine) if all(len(r) > 4 for r in rows) else None
    if conv_off:
        row["leads_state"] = "off"
    elif conv_day is None:
        row["leads_state"] = "not_kept"
    elif conv_day["state"] != "ok":
        row["leads_state"] = conv_day["state"]
    else:
        row["leads"] = int(conv_day["landing"].get(k, 0))
    return row


def _var(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    return sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)


def side(rows: list[dict], m: str) -> dict:
    """One side's figure: days with it, total, per day (left: visits, one-page, share)."""
    if m == "left":
        got = [r for r in rows if r["visits"] is not None]
        visits = sum(r["visits"] for r in got)
        one = sum(r["one_page"] for r in got)
        return {"days": len(got), "visits": visits if got else None, "one_page": one if got else None,
                "share": round(one / visits, 4) if visits else None,
                "at_least": any(r["at_least"] for r in got)}
    vals = [r[m] for r in rows if r[m] is not None]
    total = sum(vals)
    return {"days": len(vals), "total": total if vals else None,
            "per_day": round(total / len(vals), 4) if vals else None,
            "at_least": m in ("visits", "search", "ai") and any(r["at_least"] for r in rows if r[m] is not None)}


def daily(rows: list[dict], m: str) -> list[float]:
    if m == "left":
        return [r["one_page"] / r["visits"] for r in rows if r["visits"]]
    return [float(r[m]) for r in rows if r[m] is not None]


def verdict(m: str, n: int, b: dict, a: dict, bv: list[float], av: list[float]) -> str:
    if n < MIN_DAYS:
        return "too_early"
    if not b["days"] or not a["days"]:
        return "not_recorded"
    if b["days"] < MIN_SIDE or a["days"] < MIN_SIDE:
        return "not_enough_days"
    if m == "left":
        if b["visits"] < MIN_VISITS or a["visits"] < MIN_VISITS:
            return "too_few"
        diff = a["one_page"] / a["visits"] - b["one_page"] / b["visits"]
    else:
        if b["total"] + a["total"] < MIN_TOTAL:
            return "too_few"
        diff = a["total"] / a["days"] - b["total"] / b["days"]
    se = sqrt((_var(bv) / len(bv) if bv else 0.0) + (_var(av) / len(av) if av else 0.0))
    if diff == 0 or abs(diff) <= SWING * se:
        return "no_clear_change"
    return "up" if diff > 0 else "down"


def change_of(m: str, b: dict, a: dict) -> dict | None:
    if m == "left":
        if b.get("share") is None or a.get("share") is None:
            return None
        return {"points": round((a["share"] - b["share"]) * 100, 1)}
    if b.get("per_day") is None or a.get("per_day") is None:
        return None
    diff = a["per_day"] - b["per_day"]
    return {"per_day": round(diff, 4),
            "pct": round(diff / b["per_day"] * 100) if b["per_day"] else None}


def compare(mark: dict, rows: list[dict], anchor: date) -> dict:
    """One change: its windows, its days and each figure before and after."""
    day = date.fromisoformat(mark["day"])
    before, after = windows(day, anchor)
    n = len(after)
    b_days = {_iso(d) for d in before}
    a_days = {_iso(d) for d in after}
    for r in rows:
        r["side"] = "before" if r["day"] in b_days else "after" if r["day"] in a_days else "change"
    br = [r for r in rows if r["side"] == "before"]
    ar = [r for r in rows if r["side"] == "after"]
    figures = []
    for m, _words, better in MEASURES:
        b, a = side(br, m), side(ar, m)
        figures.append({"key": m, "better": better, "before": b, "after": a,
                        "unequal": b["days"] != a["days"],
                        "change": change_of(m, b, a),
                        "verdict": verdict(m, n, b, a, daily(br, m), daily(ar, m))})
    status = "waiting" if n == 0 else "too_early" if n < MIN_DAYS else "ready"
    return {**mark, "days_after": n, "status": status,
            "verdict_on": _iso(day + timedelta(days=MIN_DAYS + 1)),
            "complete": n == MAX_DAYS,
            "before": {"first": _iso(before[0]) if before else None,
                       "last": _iso(before[-1]) if before else None, "days": n,
                       "whole": sum(1 for r in br if r["state"] == "ok")},
            "after": {"first": _iso(after[0]) if after else None,
                      "last": _iso(after[-1]) if after else None, "days": n,
                      "whole": sum(1 for r in ar if r["state"] == "ok")},
            "days": rows, "figures": figures}


def figures(history, site_key: str, anchor: date, marks: list[dict], conv: dict | None) -> list[dict]:
    """Every change, compared. `marks`: todo_marks.changes(); `conv`: conversions.json's body."""
    if not marks:
        return []
    spans = []
    for mk in marks:
        d = date.fromisoformat(mk["day"])
        before, after = windows(d, anchor)
        spans.append((mk, before[0] if before else d, after[-1] if after else d))
    lo, hi = min(s[1] for s in spans), max(s[2] for s in spans)
    states = {_iso(e["day"]): e["state"] for e in history.daily(site_key, lo, hi)}
    stored = history.extras(site_key, lo, hi, ("landings", "ai_fetches"))
    per_conv, why = leads_by_day(conv)
    out = []
    for mk, first, last in spans:
        k = key(mk["path"])
        rows, d = [], first
        while d <= last:
            i = _iso(d)
            blobs = stored.get(i) or {}
            rows.append(day_row(k, i, states.get(i, "missing"), blobs.get("landings"),
                                blobs.get("ai_fetches"), per_conv.get(i), why is not None))
            d += timedelta(days=1)
        got = compare(mk, rows, anchor)
        got["leads_why"] = why
        out.append(got)
    return out


def build(p) -> dict:
    """page_changes.json's body (docs/DATA-CONTRACT-PAGE-CHANGES.md)."""
    if p.view is not None:
        return {"whole_site_only": True}
    from . import audit_page_changes, todo_marks
    site = p.key.split("::", 1)[0]
    marks = todo_marks.read_changes(p.config, site, p.live_dir)
    head = {"min_days": MIN_DAYS, "max_days": MAX_DAYS, "rules": RULES,
            "measures": [{"key": m, "label": w, "better": b} for m, w, b in MEASURES]}
    if marks is None:
        return {**head, "marks": False, "changes": [], "withheld": []}
    conv = None
    if marks:
        from . import conversions_data
        try:
            conv = conversions_data.build(p)
        except Exception:                   # noqa: BLE001 - conversions.json says why itself
            conv = None
    found = figures(p.history, p.key, p.anchor, marks, conv)
    # The second count: a change it does not find the same is left out, and named.
    held = audit_page_changes.check(p, found, conv)
    withheld = [{"id": c["id"], "path": c["path"], "day": c["day"], "why": held[c["id"]]}
                for c in found if c["id"] in held]
    return {**head, "marks": True, "changes": [c for c in found if c["id"] not in held],
            "withheld": withheld}
