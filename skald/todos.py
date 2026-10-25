"""todos.json (2.35): Overview > Insights' to-do list, worst leak first.

Each to-do is a problem the site has now, with its proof (the figure and the
window), the rows behind it (for "Show the list" and the CSV), what to do, and
how Skald will know it worked. Built only from figures Skald already counts
and checks; a to-do appears only when its data is there and passes its
threshold (LIMITS, below). Nothing is guessed:

  lost-pages      old page addresses people, search engines or AI still ask for
                  that answer 404 or 410 (lost_pages.py: the day kind not_found)
  server-errors   5xx answers, by address (history's counts, server_error_page,
                  and each group's 5xx: the breakdowns the audit recounts)
  ai-markdown     the Markdown copies (.md) AI fetchers asked for, of pages that
                  are live, that answered 404 (lost_pages.py)
  sitemap         a sitemap address (a file named *sitemap*.xml) search engines or AI
                  crawlers asked for that answered 404
  leave-<id>      a page many visits started on, where nearly every one of them
                  left after that page and no form was sent (the stored journeys,
                  kept report.journey_days days; one to-do per page, at most
                  LIMITS["leave_pages"]; the id is an opaque hash of the page)

The window: lost_pages.WINDOW_DAYS days with figures ending yesterday (the
journeys: the days of it they are kept for).

Marks (todo_marks.py, accounts.sqlite): "done" moves a to-do to "Done, and did
it work?", where it is re-checked on every whole day after the day it was marked,
with the same measure that raised it ("Fixed: 0 not-found answers since 25 Oct",
or "Not yet: ..."); "not now" folds it away until someone puts it back. Without
accounts nothing can be marked (`marks: false`).

Second count: audit_todos.check_todos, for every figure and every re-check; a
to-do it disagrees with is left out and named in `withheld`.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import date

from . import lost_pages

# ---- every threshold, in one place (audit_todos.py reads the same) -------------------
LIMITS = {
    "lost_min_asks": 10,        # old addresses: people, search engines and AI, together
    "markdown_min_asks": 5,     # AI asks for the .md copy of live pages
    "sitemap_min_asks": 3,      # crawlers' asks (search + AI) for a sitemap not there
    "errors_min": 5,            # 5xx answers
    "leave_min_visits": 20,     # visits that started on the page
    "leave_share": 0.8,         # of them, at least this share left after that one page
    "leave_pages": 3,           # at most this many such pages, the most visited first
}
ROWS_MOST = 1000                # rows a to-do carries for its list and CSV
OTHER = "(all others)"
GROUPS = ("people", "answer_engines", "search_engines", "bots", "ours")
ORDER = ("lost", "errors", "markdown", "sitemap", "leave")
TAB_NAMES = {"site/notfound": "Site > Not found", "site/health": "Site > Health",
             "traffic/pages": "Traffic > Pages"}


def _short(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%b}"


def _span(first: str | None, last: str | None) -> str:
    return f"{_short(first)} to {_short(last)}" if first != last else _short(first)


def _n(v: int) -> str:
    return f"{v:,}"


def _times(v: int) -> str:
    return "once" if v == 1 else f"{_n(v)} times"


def leave_id(site: str, path: str) -> str:
    return "leave-" + hashlib.sha256(f"{site}|{path}".encode()).hexdigest()[:8]


class Days:
    """The days a to-do and its re-check are counted over."""

    def __init__(self, p, found) -> None:
        self.window = found.days
        self.all = [e["day"].isoformat() for e in p.daily if p.has_figures(e)]

    def after(self, day: str) -> list[str]:
        return [d for d in self.all if d > day]

    def upto(self, day: str) -> list[str]:
        return [d for d in self.window if d <= day]


# ------------------------------------------------------------------ the to-dos

def _lost(found, cols) -> dict | None:
    rows = found.lost()
    if not rows:
        return None
    fig = {"paths": len(rows), "people": sum(r["people"] for r in rows),
           "search": sum(r["search"] for r in rows), "ai": sum(r["ai"] for r in rows)}
    asked = fig["people"] + fig["search"] + fig["ai"]
    return {"id": "lost-pages", "kind": "lost", "subject": None, "tag": "Lost traffic", "tone": "bad",
            "title": "Send old pages somewhere useful",
            "proof": f"{_n(fig['paths'])} old page address{'es' if fig['paths'] != 1 else ''} answered "
                     f"'not found' from {_span(found.first, found.last)}: people asked {_times(fig['people'])}, "
                     f"search engines {_times(fig['search'])}, AI {_times(fig['ai'])}.",
            "todo": "Redirect each to the closest live page, or answer 410 gone. Site > Not found suggests "
                    "the page and gives the server line to copy, most asked first.",
            "check": "the not-found answers to the same addresses, on the days after you mark it done",
            "figures": fig, "qualifies": asked >= LIMITS["lost_min_asks"],
            "columns": cols(("path", "Old address", "path"), ("people", "People"), ("search", "Search engines"),
                            ("ai", "AI"), ("target", "Closest live page", "path"), ("match", "How close", "text")),
            "rows": [{k: r[k] for k in ("path", "people", "search", "ai", "target", "match")} for r in rows],
            "file": "old-pages.csv", "open": {"tab": "site/notfound", "nfk": "lost"}}


def _markdown(found, cols) -> dict | None:
    md = found.markdown()["live"]
    if not md:
        return None
    fig = {"pages": len(md), "asks": sum(r["ai"] for r in md)}
    return {"id": "ai-markdown", "kind": "markdown", "subject": None, "tag": "AI", "tone": "warn",
            "title": "Give AI the Markdown copies it asks for",
            "proof": f"AI fetchers asked for the Markdown copy (.md) of {_n(fig['pages'])} page"
                     f"{'s' if fig['pages'] != 1 else ''} you have, {_times(fig['asks'])} from "
                     f"{_span(found.first, found.last)}, and got 'not found'.",
            "todo": "Serve a Markdown copy of each page at its .md address, or redirect .md to the page. "
                    "One server rule covers all of them.",
            "check": "AI's not-found answers for .md addresses, on the days after you mark it done",
            "figures": fig, "qualifies": fig["asks"] >= LIMITS["markdown_min_asks"],
            "columns": cols(("path", "Asked for", "path"), ("ai", "AI asks"), ("page", "The page", "path")),
            "rows": [{k: r[k] for k in ("path", "ai", "page")} for r in md],
            "file": "markdown-asks.csv", "open": {"tab": "site/notfound", "nfk": "md"}}


def _sitemap(found, cols) -> dict | None:
    rows = found.sitemaps()
    if not rows:
        return None
    fig = {"paths": len(rows), "asked": sum(r["search"] + r["ai"] for r in rows),
           "search": sum(r["search"] for r in rows)}
    one = rows[0]["path"] if len(rows) == 1 else None
    have = sorted(found.sitemap or ())
    return {"id": "sitemap", "kind": "sitemap", "subject": None, "tag": "Search", "tone": "info",
            "title": "Fix the sitemap address crawlers ask for",
            "proof": (f"{one} was" if one else f"{_n(fig['paths'])} sitemap addresses were") +
                     f" asked for {_times(fig['asked'])} from {_span(found.first, found.last)}"
                     f" (search engines {_times(fig['search'])}, AI crawlers "
                     f"{_times(fig['asked'] - fig['search'])}), and answered 'not found'.",
            "todo": "Publish the sitemap there, or redirect it to the one you have"
                    + (" (Skald reads yours)." if have else "."),
            "check": "crawlers' not-found answers for sitemap addresses, on the days after you mark it done",
            "figures": fig, "qualifies": fig["asked"] >= LIMITS["sitemap_min_asks"],
            "columns": cols(("path", "Address", "path"), ("search", "Search engines"), ("ai", "AI crawlers"),
                            ("status", "Answer", "text")),
            "rows": [{"path": r["path"], "search": r["search"], "ai": r["ai"],
                      "status": " ".join(f"{k} ({v})" for k, v in sorted(r["statuses"].items()))} for r in rows],
            "file": "sitemap-asks.csv", "open": {"tab": "site/notfound", "path": "sitemap"}}


def errors_of(p, days: list[str]) -> tuple[int, Counter, Counter]:
    """(5xx answers, by path, by group) over the days, from the history's counts."""
    by_path, by_group = Counter(), Counter()
    want = set(days)
    for d, kind, name, n in p.history.count_rows(p.key, ["server_error_page"] + [f"status_{g}" for g in GROUPS], days):
        if d not in want:
            continue
        if kind == "server_error_page":
            by_path[name] += int(n)
        elif name == "5xx":
            by_group[kind[7:]] += int(n)
    return sum(by_path.values()), by_path, by_group


def _errors(p, found, cols) -> dict | None:
    total, by_path, by_group = errors_of(p, found.days)
    if not total:
        return None
    named = [k for k in by_path if k != OTHER]
    fig = {"errors": total, "paths": len(named), "people": by_group["people"]}
    top = ", ".join(k for k, _ in by_path.most_common(3) if k != OTHER)
    return {"id": "server-errors", "kind": "errors", "subject": None, "tag": "Broken", "tone": "bad",
            "title": "Fix the server errors",
            "proof": f"{_n(total)} server error{'s' if total != 1 else ''} (5xx) from {_span(found.first, found.last)}"
                     f"{', on ' + top if top else ''}. People got {_n(fig['people'])} of them.",
            "todo": "Send the list to your developer or host: these addresses failed for whoever asked.",
            "check": "the server errors on the days after you mark it done",
            "figures": fig, "qualifies": total >= LIMITS["errors_min"],
            "columns": cols(("path", "Address", "path"), ("errors", "Server errors")),
            "rows": [{"path": k, "errors": v} for k, v in by_path.most_common()],
            "file": "server-errors.csv", "open": {"tab": "site/health"}}


def landings_of(p, days: list[str]) -> tuple[dict[str, dict], list[str]]:
    """{landing page: {"visits", "one_page", "posted", "sources"}} from the stored journeys
    of the days, and the days that had journeys."""
    out: dict[str, dict] = {}
    seen = set()
    if not days:
        return out, []
    want = set(days)
    for j in p.history.journeys(p.key, date.fromisoformat(days[0]), date.fromisoformat(days[-1])):
        if j.get("day") not in want:
            continue
        seen.add(j["day"])
        got = out.setdefault(j.get("landing") or "", {"visits": 0, "one_page": 0, "posted": 0,
                                                      "sources": Counter()})
        got["visits"] += 1
        got["one_page"] += 1 if int(j.get("pages") or 0) == 1 else 0
        got["posted"] += 1 if j.get("posted") else 0
        got["sources"][j.get("source") or ""] += 1
    return out, sorted(seen)


def _leave_one(site, path, got, jdays, cols) -> dict:
    fig = {"visits": got["visits"], "one_page": got["one_page"], "posted": got["posted"]}
    share = got["one_page"] / got["visits"] if got["visits"] else 0
    ok = (got["visits"] >= LIMITS["leave_min_visits"] and share >= LIMITS["leave_share"]
          and not got["posted"])
    return {"id": leave_id(site, path), "kind": "leave", "subject": path, "tag": "Leaving", "tone": "warn",
            "title": f"Make {path} lead somewhere",
            "proof": f"{_n(got['visits'])} visit{'s' if got['visits'] != 1 else ''} started on {path} from "
                     f"{_span(jdays[0] if jdays else None, jdays[-1] if jdays else None)} and {_n(got['one_page'])} of them "
                     f"({round(share * 100)}%) left after that one page. "
                     + ("No form was sent from them." if not got["posted"] else
                        f"{_n(got['posted'])} sent a form."),
            "todo": "Give the page a clear next step (a link to what they came for, a form or a call to act), "
                    "and check that the links bringing people here promise what the page has.",
            "check": "the share of visits that leave after this one page, on the days after you mark it done",
            "figures": fig, "qualifies": ok, "journey_days": jdays,
            "columns": cols(("source", "Came from", "text"), ("visits", "Visits")),
            "rows": [{"source": k or "Not recorded", "visits": v} for k, v in got["sources"].most_common()],
            "file": "landing-visits.csv", "open": {"tab": "traffic/pages", "page": path}}


def _leaving(p, found, marks, cols) -> list[dict]:
    site = p.key.split("::", 1)[0]
    pages, jdays = landings_of(p, found.days)
    wanted = {k for k, v in (marks or {}).items() if k.startswith("leave-")}
    out = []
    ranked = sorted(((k, v) for k, v in pages.items() if k), key=lambda kv: (-kv[1]["visits"], kv[0]))
    picked = 0
    for path, got in ranked:
        todo = _leave_one(site, path, got, jdays, cols)
        if todo["qualifies"] and picked < LIMITS["leave_pages"]:
            picked += 1
            out.append(todo)
        elif todo["id"] in wanted:
            out.append(todo)
    if out:
        days = jdays
        for t in out:
            t["window"] = {"first": days[0] if days else None, "last": days[-1] if days else None,
                           "days": len(days)}
    return out


# ------------------------------------------------------------------ re-checks

def recheck(p, found, todo: dict, mark: dict, span: Days) -> dict:
    """The same measure on the whole days after the day the to-do was marked done."""
    since = mark["first_day"]
    after = span.after(since)
    out = {"marked_day": since, "days": len(after), "first": after[0] if after else None,
           "last": after[-1] if after else None, "figures": None, "verdict": "waiting"}
    if not after:
        out["words"] = f"Marked done {_short(since)}. Re-checked once a whole day has passed after it."
        return out
    kind = todo["kind"]
    words = {"lost": "not-found answer", "markdown": "not-found answer for .md", "sitemap": "not-found answer",
             "errors": "server error"}
    if kind == "leave":
        pages, _ = landings_of(p, after)
        got = pages.get(todo["subject"]) or {"visits": 0, "one_page": 0, "posted": 0}
        out["figures"] = {"visits": got["visits"], "one_page": got["one_page"], "posted": got["posted"]}
        if got["visits"] < LIMITS["leave_min_visits"]:
            out["words"] = f"{_n(got['visits'])} visits started there since {_short(since)}: too few to judge yet."
            return out
        share = got["one_page"] / got["visits"]
        out["verdict"] = "fixed" if share < LIMITS["leave_share"] or got["posted"] else "not_yet"
        out["words"] = (f"{'Fixed' if out['verdict'] == 'fixed' else 'Not yet'}: {round(share * 100)}% of "
                        f"{_n(got['visits'])} visits left after this page since {_short(since)}.")
        return out
    if kind == "lost":
        old = {path for path, g in lost_pages.tally([(d, found_blob(p, d)) for d in span.upto(since)]).items()
               if lost_pages.kind_of(path) == "page" and g["people"] + g["search"] + g["ai"]}
        now = lost_pages.tally([(d, found_blob(p, d)) for d in after])
        n = sum(g["people"] + g["search"] + g["ai"] for path, g in now.items() if path in old)
        out["figures"] = {"asked": n}
    elif kind in ("markdown", "sitemap"):
        now = lost_pages.tally([(d, found_blob(p, d)) for d in after])
        if kind == "markdown":
            n = sum(g["ai"] for path, g in now.items() if lost_pages.kind_of(path) == "markdown")
        else:
            n = sum(g["search"] + g["ai"] for path, g in now.items() if lost_pages.kind_of(path) == "sitemap")
        out["figures"] = {"asked": n}
    else:
        n = errors_of(p, after)[0]
        out["figures"] = {"errors": n}
    out["verdict"] = "not_yet" if n else "fixed"
    unit = words[kind]
    out["words"] = (f"Fixed: 0 {unit}s since {_short(since)}." if not n else
                    f"Not yet: {_n(n)} {unit}{'s' if n != 1 else ''} since {_short(since)}.")
    return out


def found_blob(p, d: str):
    return (p.extras.get(d) or {}).get("not_found")


# ------------------------------------------------------------------ the file

def _cols(*spec) -> list[dict]:
    out = []
    for s in spec:
        key, label, kind = (s + (None,))[:3]
        col = {"key": key, "label": label}
        if kind == "path":
            col["path"] = True
        elif kind is None:
            col["num"] = True
        out.append(col)
    return out


def build(p) -> dict:
    """todos.json's body (DATA-CONTRACT.md)."""
    from . import audit_todos, todo_marks
    found = lost_pages.Found(p)
    site = p.key.split("::", 1)[0]
    marks = todo_marks.read(p.config, site, p.live_dir)
    span = Days(p, found)
    made = [t for t in (_lost(found, _cols), _errors(p, found, _cols), _markdown(found, _cols),
                        _sitemap(found, _cols)) if t]
    for t in made:
        t["window"] = {"first": found.first, "last": found.last, "days": len(found.days)}
    made += _leaving(p, found, marks, _cols)
    todos = []
    for t in made:
        mark = (marks or {}).get(t["id"])
        t["state"] = mark["state"] if mark and mark["state"] in ("done", "notnow") else "open"
        t["marked"] = mark if t["state"] != "open" else None
        t["recheck"] = recheck(p, found, t, mark, span) if t["state"] == "done" else None
        if t["state"] == "open" and not t["qualifies"]:
            continue                     # under its threshold and not marked: not a to-do
        t["rows_total"] = len(t["rows"])
        t["rows"] = t["rows"][:ROWS_MOST]
        t["open"]["name"] = TAB_NAMES.get(t["open"]["tab"], t["open"]["tab"])
        todos.append(t)
    todos.sort(key=lambda t: (ORDER.index(t["kind"]), -t["figures"].get("visits", 0), t["id"]))
    # The second count: a to-do it does not find the same is left out, and named.
    held = audit_todos.check_todos(p.history.db, p.key, todos, p.live_dir, p.anchor.isoformat())
    withheld = [{"id": t["id"], "title": t["title"], "why": held[t["id"]]} for t in todos if t["id"] in held]
    todos = [t for t in todos if t["id"] not in held]
    return {"window": {"first": found.first, "last": found.last, "days": len(found.days),
                       "of": lost_pages.WINDOW_DAYS},
            "limits": LIMITS, "marks": marks is not None, "todos": todos, "withheld": withheld}
