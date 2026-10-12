"""The report data files: not_found, ai_activity, campaigns, pages, insights.

The companions of data_files.py (same Page object, same envelope, same
day rules; see DATA-CONTRACT.md).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from .campaigns import merge
from .redirects import RedirectMap


def _blob(p, d: str, kind: str):
    return (p.extras.get(d) or {}).get(kind)


def _live_blob(p, kind: str):
    return ((p.snap or {}).get("extras") or {}).get(kind) if p.live_ok else None


def _totals(rows: list[dict]) -> dict:
    return {"all": sum(r["n"] for r in rows),
            "people": sum(r["n"] for r in rows if r["group"] == "people"),
            "probes": sum(r["n"] for r in rows if r["probe"])}


def not_found(p) -> dict:
    days = p.per_day(lambda d, e: ({"rows": _blob(p, d, "not_found"),
                                    "totals": _totals(_blob(p, d, "not_found"))}
                                   if _blob(p, d, "not_found") is not None
                                   else {"rows": None, "totals": None}))
    today = p.today_block()
    live_rows = _live_blob(p, "not_found")
    if today is not None and live_rows is not None:
        today.update({"rows": live_rows, "totals": _totals(live_rows)})
    # By path over the last 30 days and today.
    first = (p.anchor - timedelta(days=29)).isoformat()
    spans = [(r["day"], r.get("rows")) for r in days if r["day"] >= first and r.get("rows")]
    if live_rows is not None:
        spans.append((p.today.isoformat(), live_rows))
    paths: dict[str, dict] = {}
    for d, rows in spans:
        for r in rows:
            got = paths.setdefault(r["path"], {
                "path": r["path"], "n": 0, "people": 0, "probe": r["probe"],
                "statuses": Counter(), "groups": Counter(), "sources": Counter(),
                "first_day": d, "last_day": d, "trend": Counter()})
            got["n"] += r["n"]
            got["people"] += r["n"] if r["group"] == "people" else 0
            got["probe"] = got["probe"] or r["probe"]
            got["statuses"][str(r["status"])] += r["n"]
            got["groups"][r["group"]] += r["n"]
            got["sources"][r["source"]] += r["n"]
            got["first_day"] = min(got["first_day"], d)
            got["last_day"] = max(got["last_day"], d)
            got["trend"][d] += r["n"]
    redirects = RedirectMap.load(((p.config or {}).get("report") or {}).get("redirect_map"))
    served = _served_after(p, spans)
    out = []
    for path, got in paths.items():
        state, to = redirects.state(path)
        fix = {"fix": state or "open"}
        if state == "redirected":
            fix["fix_to"] = to
        elif not state and served.get(path, "") > got["last_day"]:
            fix = {"fix": "fixed", "fix_status": "2xx"}
        out.append({**{k: (dict(v) if isinstance(v, Counter) else v) for k, v in got.items()},
                    **fix})
    out.sort(key=lambda r: (r["probe"], -r["people"], -r["n"], r["path"]))
    return {"days": days, "today": today, "paths": out}


def _served_after(p, spans) -> dict[str, str]:
    """The last day each path was served as a page to anyone (pages extras)."""
    last: dict[str, str] = {}
    for d, blobs in p.extras.items():
        for path, v in (blobs.get("pages") or {}).items():
            if v.get("views") or v.get("ai_asked") or v.get("ai_training") or v.get("search"):
                last[path] = max(last.get(path, ""), d)
    for path, v in (_live_blob(p, "pages") or {}).items():
        if v.get("views") or v.get("search") or v.get("ai_asked") or v.get("ai_training"):
            last[path] = p.today.isoformat()
    return last


def ai_activity(p) -> dict:
    kinds = ["engine_training", "engine_asked", "cited_by"]
    counts = p.counts(kinds)
    visitors = _visitor_days(p)

    def figures(d, e):
        c = counts.get(d, {})
        by_name = {}
        for kind, tier in (("engine_training", "training"), ("engine_asked", "asked"),
                           ("cited_by", "referred")):
            for name, n in c.get(kind, {}).items():
                by_name[name] = {"kind": tier, "events": int(n)}
        # Likely sent by an AI assistant (ai_likely.py): inferred, apart
        # from the counts above; null on a day it was not recorded.
        return {"by_name": by_name, "by_kind": visitors.get(d),
                "ai_likely": _blob(p, d, "ai_likely")}

    today = None
    if p.ai is not None:
        events = p.ai.get("events") or []
        if p.view is not None:
            events = [e for e in events if p.view.matches(e.get("path", ""))]
        today = {"events": events, "total": int(p.ai.get("total", 0)) if p.view is None
                 else len(events), "by_name": p.ai.get("by_name") if p.view is None else None,
                 "ai_likely": _live_blob(p, "ai_likely")}
    return {"repeat_window_days": 30, "repeat_counts": "days", "likely_ai": likely_note(p.config),
            "days": p.per_day(figures), "today": today}


def likely_note(config: dict | None) -> dict:
    """What a page says beside a likely-AI figure: on or off, the window, the method."""
    from .ai_likely import METHOD, settings
    got = settings(config)
    return {"on": got["on"], "window_minutes": got["window"],
            "method": METHOD.format(w=got["window"])}


def _visitor_days(p) -> dict[str, dict]:
    """{day: {kind: {"visitors", "repeat_visitors"}}} from the keyed hashes
    (whole site only; a view reads the site's)."""
    site = p.key.split("::", 1)[0]
    rows = p.history.db.execute(
        "SELECT day, visitor, kind FROM visitor_days WHERE site = ? ORDER BY day",
        (site,)).fetchall()
    seen: dict[tuple, list[str]] = {}
    for d, v, kind in rows:
        seen.setdefault((v, kind), []).append(d)
    out: dict[str, dict] = {}
    for (v, kind), days in seen.items():
        for i, d in enumerate(days):
            slot = out.setdefault(d, {}).setdefault(kind, {"visitors": 0, "repeat_visitors": 0})
            slot["visitors"] += 1
            earlier = [x for x in days[:i]
                       if date.fromisoformat(x) >= date.fromisoformat(d) - timedelta(days=29)]
            slot["repeat_visitors"] += 1 if earlier else 0
    return out


def campaigns(p) -> dict:
    def figures(d, e):
        blob = _blob(p, d, "campaigns")
        # Tag hygiene (utm_hygiene.py): null on a day it was not counted.
        hygiene = {"utm_hygiene": _blob(p, d, "utm_hygiene")}
        if blob is None:
            return {"rows": None, "tagged": None, "first_touch": None, **hygiene}
        return {"rows": blob.get("rows"), "tagged": blob.get("tagged"),
                "first_touch": blob.get("first_touch"), **hygiene}

    today = p.today_block()
    blob = _live_blob(p, "campaigns")
    if today is not None and blob is not None:
        today.update({"rows": blob.get("rows"), "tagged": blob.get("tagged"),
                      "first_touch": blob.get("first_touch"),
                      "utm_hygiene": _live_blob(p, "utm_hygiene")})
    days = p.per_day(figures)
    first = (p.anchor - timedelta(days=29)).isoformat()
    month = merge([r for r in days if r["day"] >= first and r["state"] == "ok"
                   and r.get("rows") is not None])
    return {"days": days, "today": today, "last_30_days": month}


PAGE_SUMS = ("views", "readers", "visits", "entries", "exits", "after_pages", "not_found_from",
             "posts_from", "ai_asked", "ai_training", "search")


def _merge_pages(blobs: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for pages in blobs:
        for path, v in (pages or {}).items():
            got = out.setdefault(path, {**{k: 0 for k in PAGE_SUMS}, "time": Counter(),
                                        "sources": Counter(), "assistants": Counter(),
                                        "countries": Counter()})
            for k in PAGE_SUMS:
                got[k] += int(v.get(k, 0))
            for k in ("time", "sources", "assistants", "countries"):
                got[k].update({a: int(b) for a, b in (v.get(k) or {}).items()})
    return out


def _median_bucket(hist: Counter) -> int | None:
    total = sum(hist.values())
    if not total:
        return None
    middle = (total - 1) // 2
    for value, n in sorted((int(k), n) for k, n in hist.items()):
        if middle < n:
            return value
        middle -= n
    return None


MIN_RATE = 10             # no rate over fewer than this many visits (DATA-CONTRACT.md)


def _figures(v: dict) -> dict:
    return {**{k: v[k] for k in PAGE_SUMS},
            "after_pages": round(v["after_pages"] / v["entries"], 2) if v["entries"] else None,
            # The share of this page's visits that ended on it. Both halves
            # are recounted per page by the audit (audit_visits.compare_pages).
            "exit_rate": round(v["exits"] / v["visits"], 4) if v["visits"] >= MIN_RATE
            else None,
            "time_on_page_s": _median_bucket(v["time"]), "time_estimate": True,
            "sources": dict(v["sources"]), "assistants": dict(v["assistants"]),
            "countries": dict(v["countries"])}


def pages(p) -> dict:
    def span(first: date, last: date):
        days = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
        complete = all((p.states.get(d) or {}).get("state") == "ok" for d in days)
        blobs = [_blob(p, d, "pages") for d in days
                 if (p.states.get(d) or {}).get("state") == "ok"]
        return _merge_pages([b for b in blobs if b is not None]), complete, len(days)

    last = p.anchor
    first = last - timedelta(days=29)
    now, complete, n = span(first, last)
    prev, prev_complete, _ = span(first - timedelta(days=30), first - timedelta(days=1))
    daily: dict[str, dict] = {}
    for d in [(last - timedelta(days=i)).isoformat() for i in range(89, -1, -1)]:
        for path, v in (_blob(p, d, "pages") or {}).items():
            daily.setdefault(path, {})[d] = int(v.get("views", 0))
    rows = []
    for path, v in now.items():
        row = {"path": path, **_figures(v)}
        before = prev.get(path)
        row["prev"] = _figures(before) if before and prev_complete else None
        row["change_pct"] = (round((v["views"] - before["views"]) / before["views"] * 100, 1)
                             if before and before["views"] and complete and prev_complete
                             else None)
        row["daily"] = daily.get(path, {})
        rows.append(row)
    rows.sort(key=lambda r: (-r["views"], -r["ai_asked"] - r["ai_training"], r["path"]))
    today = p.today_block()
    blob = _live_blob(p, "pages")
    if today is not None and blob is not None:
        today["pages"] = sorted(({"path": k, **{f: int(v.get(f, 0)) for f in
                                               ("views", "readers", "entries", "ai_asked",
                                                "ai_training", "search")}}
                                 for k, v in blob.items()), key=lambda r: -r["views"])
    return {"period": {"first": first.isoformat(), "last": last.isoformat(), "days": n,
                       "complete": complete},
            "prev_period": {"first": (first - timedelta(days=30)).isoformat(),
                            "last": (first - timedelta(days=1)).isoformat(),
                            "complete": prev_complete},
            "pages": rows, "today": today}


def insights(p) -> dict:
    from .insights import compute
    return compute(p.history, p.key, p.anchor, p.config, p.snap)


BUILDERS = {"not_found": not_found, "ai_activity": ai_activity, "campaigns": campaigns,
            "pages": pages, "insights": insights}
