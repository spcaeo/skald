"""The second count of the lost pages and the to-dos (2.35: lost_pages.py, todos.py).

lost_pages.py and todos.py add up what the history's day blobs hold, in Python,
from the Page's loaded days. This module counts the same figures again by its own
road: its own SQL over history.sqlite (the `days`, `day_extras`, `counts` and
`journeys` tables), its own reading of each blob, its own path rules written again
from DATA-CONTRACT.md, and its own reading of the sitemap files beside the history.
It shares only the name lists in lost_pages.py (MACHINE, OURS, PAGE_ENDINGS,
MARKDOWN_ENDINGS, WHO), the thresholds in todos.py (LIMITS), and one rule,
closest_page.closest (does an old address have a live page like it? #23).

  check_lost    lost_pages.json: every lost address and its people, search and AI
                asks; the Markdown asks split by whether the page is live; the totals
  check_todos   todos.json: each to-do's figures, and each re-check's figures after
                the day it was marked done, the addresses it names as still failing,
                and the status the Insights card shows (open, checking, failed, passed)

A figure the recount does not find the same is withheld, never shown: the list is
replaced by the reasons (lost_pages.json `withheld`), a to-do is left out and named
(todos.json `withheld`).
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .todos import LIMITS, STILL_MOST
from .closest_page import Live, closest
from .lost_pages import MACHINE, MARKDOWN_ENDINGS, OURS, PAGE_ENDINGS, WHO

ERRORS_KIND = "server_error_page"     # history's counts: 5xx by path (DATA-CONTRACT.md)
OTHER = "(all others)"                # a folded tail: real requests, no one address
GROUPS = ("people", "answer_engines", "search_engines", "bots", "ours")


# ------------------------------------------------------------------ reading history

def verified_days(db, key: str, first: str | None, last: str | None) -> list[str]:
    """The days in [first, last] whose figures stand (verified: whole or partial)."""
    if not first or not last:
        return []
    return [r[0] for r in db.execute("SELECT day FROM days WHERE site = ? AND day >= ? AND day <= ? "
                                     "AND verified = 1 ORDER BY day", (key, first, last))]


def _blobs(db, key: str, days: list[str], kind: str) -> dict[str, object]:
    if not days:
        return {}
    marks = ",".join("?" * len(days))
    out = {}
    for d, data in db.execute(f"SELECT day, data FROM day_extras WHERE site = ? AND kind = ? "
                              f"AND day IN ({marks})", (key, kind, *days)):
        try:
            out[d] = json.loads(data)
        except ValueError:
            continue
    return out


def _sort(path: str) -> str | None:
    """This module's own reading of an address: page, markdown, sitemap or None."""
    if not path or path[0] != "/" or path[:2] == "//":
        return None
    bare = path.partition("?")[0].lower()
    first = "/" + bare[1:].split("/")[0]
    if first in OURS:                  # Skald's own addresses (#16), with or without a slash
        return None
    last = [s for s in bare.split("/") if s]
    name = last[-1] if last else ""
    if name.find("sitemap") >= 0 and (name[-4:] == ".xml" or name[-7:] == ".xml.gz"):
        return "sitemap"
    for start in MACHINE:
        if bare[:len(start)] == start:
            return None
    for end in MARKDOWN_ENDINGS:
        if name[-len(end):] == end:
            return "markdown"
    if "." in name:
        dot = name[name.rindex("."):]
        if 1 < len(dot) <= 9 and dot[1:].isascii() and dot[1:].isalnum() and dot not in PAGE_ENDINGS:
            return None
    return "page"


def asks(db, key: str, days: list[str]) -> dict[str, dict]:
    """{path: {"people", "search", "ai", "ai_asked", "ai_training", "last", "gone"}} of the
    days' 404 rows, probes left out; "gone" is the last day of a 410 (2.38.0: an answer
    given on purpose, never an ask), "last" the last day of a 404."""
    out: dict[str, dict] = {}
    for d, rows in sorted(_blobs(db, key, days, "not_found").items()):
        for r in rows if isinstance(rows, list) else []:
            status = int(r.get("status") or 0)
            if r.get("probe") is True or status not in (404, 410):
                continue
            slot = out.setdefault(r["path"], {"people": 0, "search": 0, "ai": 0, "ai_asked": 0,
                                              "ai_training": 0, "last": "", "gone": ""})
            if status == 410:
                slot["gone"] = d if d > slot["gone"] else slot["gone"]
                continue
            who = WHO.get(r.get("group"))
            if who is not None:
                slot[who] += int(r["n"])
            if r.get("group") in ("ai_asked", "ai_training"):
                slot[r["group"]] += int(r["n"])
            slot["last"] = d if d > slot["last"] else slot["last"]
    return out


def served(db, key: str, days: list[str]) -> dict[str, str]:
    """{path: the last of the days it was served as a page}, from the pages blobs."""
    out: dict[str, str] = {}
    for d, pages in _blobs(db, key, days, "pages").items():
        for path, v in (pages or {}).items():
            if sum(int(v.get(k) or 0) for k in ("views", "search", "ai_asked", "ai_training")):
                out[path] = max(out.get(path, ""), d)
    return out


def sitemap(live_dir, day: str | None) -> frozenset | None:
    """The sitemap's paths kept for `day` or the latest day before it, read from
    sitemaps/days.json and the list it names; None when none is kept."""
    if live_dir is None or not day:
        return None
    folder = Path(live_dir) / "sitemaps"
    try:
        days = json.loads((folder / "days.json").read_text())
        kept = max(d for d in days if d <= day)
        paths = json.loads((folder / f"{days[kept]['list']}.json").read_text())["paths"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return frozenset(paths)


def _same(what: str, mine, theirs, out: list) -> None:
    if mine != theirs:
        out.append(f"{what}: the second count finds {mine}, the list says {theirs}")


# ------------------------------------------------------------------ lost pages

def recount_lost(db, key: str, first, last, live_dir, anchor: str | None) -> dict:
    """The lost addresses and the Markdown asks, counted by this module's road."""
    days = verified_days(db, key, first, last)
    found = asks(db, key, days)
    seen = served(db, key, days)
    listed = sitemap(live_dir, anchor) or frozenset()
    live = set(seen) | set(listed)
    lower = {p.lower().rstrip("/") or "/": p for p in live}
    lost, md_live, md_other = {}, {}, {}
    for path, f in found.items():
        kind = _sort(path)
        if kind == "page" and f["people"] + f["search"] + f["ai"] and path not in listed \
                and seen.get(path, "") < f["last"] and not (f["gone"] and f["gone"] >= f["last"]):
            lost[path] = (f["people"], f["search"], f["ai"])
        elif kind == "markdown" and f["ai"]:
            stem = path.partition("?")[0]
            stem = stem[:stem.lower().rindex(".md")]
            if stem.lower()[-6:] == "/index":
                stem = stem[:-6] or "/"
            page = lower.get(stem.lower().rstrip("/") or "/")
            (md_live if page else md_other)[path] = f["ai"]
    return {"lost": lost, "md_live": md_live, "md_other": md_other}


def check_lost(db, key: str, first, last, body: dict, found=None, live_dir=None,
               anchor: str | None = None) -> list[str]:
    """Problems with lost_pages.json's figures (empty: they match)."""
    if found is not None:
        live_dir, anchor = live_dir or getattr(found, "live_dir", None), anchor or getattr(found, "anchor", None)
    got = recount_lost(db, key, first, last, live_dir, anchor)
    out: list[str] = []
    theirs = {r["path"]: (r["people"], r["search"], r["ai"]) for r in body.get("lost") or []}
    _same("lost addresses", len(got["lost"]), len(theirs), out)
    for path in sorted(set(got["lost"]) | set(theirs))[:2000]:
        if got["lost"].get(path) != theirs.get(path):
            out.append(f"{path}: the second count finds {got['lost'].get(path)} (people, search, AI), "
                       f"the list says {theirs.get(path)}")
            if len(out) > 5:
                break
    md = body.get("markdown") or {}
    for part, name in (("live", "md_live"), ("other", "md_other")):
        mine = {r["path"]: r["ai"] for r in md.get(part) or []}
        _same(f"Markdown asks ({part})", got[name], mine, out)
    t = body.get("totals") or {}
    _same("people's asks", sum(v[0] for v in got["lost"].values()), t.get("people"), out)
    _same("search engines' asks", sum(v[1] for v in got["lost"].values()), t.get("search"), out)
    _same("AI's asks", sum(v[2] for v in got["lost"].values()), t.get("ai"), out)
    return out[:6]


# ------------------------------------------------------------------ the to-dos

def errors(db, key: str, days: list[str]) -> tuple[int, Counter, Counter]:
    """(5xx responses, by path, by group) over the days, from history's counts rows."""
    if not days:
        return 0, Counter(), Counter()
    marks = ",".join("?" * len(days))
    by_path = Counter({name: n for name, n in db.execute(
        f"SELECT name, SUM(n) FROM counts WHERE site = ? AND kind = ? AND day IN ({marks}) "
        f"GROUP BY name", (key, ERRORS_KIND, *days))})
    by_group = Counter()
    for g in GROUPS:
        row = db.execute(f"SELECT SUM(n) FROM counts WHERE site = ? AND kind = ? AND name = '5xx' "
                         f"AND day IN ({marks})", (key, f"status_{g}", *days)).fetchone()
        by_group[g] = int(row[0] or 0)
    return sum(by_path.values()), by_path, by_group


def landings(db, key: str, days: list[str], path: str) -> dict:
    """The visits that started on `path` over the days, from the stored journeys:
    {"visits", "one_page", "posted", "sources": Counter}."""
    out = {"visits": 0, "one_page": 0, "posted": 0, "sources": Counter()}
    if not days:
        return out
    marks = ",".join("?" * len(days))
    for (data,) in db.execute(f"SELECT data FROM journeys WHERE site = ? AND day IN ({marks})",
                              (key, *days)):
        try:
            j = json.loads(data)
        except ValueError:
            continue
        if j.get("landing") != path:
            continue
        out["visits"] += 1
        out["one_page"] += int(j.get("pages") or 0) == 1
        out["posted"] += bool(j.get("posted"))
        out["sources"][j.get("source") or ""] += 1
    return out


def _after(day: str, days: list[str]) -> list[str]:
    return [d for d in days if d > day]


def figures_of(db, key: str, todo: dict, days: list[str], live_dir=None, anchor=None,
               before: list[str] | None = None) -> dict:
    """A to-do's figures over `days`, this module's way. `before`: for a re-check of the
    old addresses, the days before the mark that name which addresses they were."""
    kind = todo["kind"]
    if kind == "lost":
        if before is not None:
            old = {p for p, f in asks(db, key, before).items()
                   if _sort(p) == "page" and f["people"] + f["search"] + f["ai"]}
            now = asks(db, key, days)
            return {"asked": sum(f["people"] + f["search"] + f["ai"] for p, f in now.items() if p in old)}
        got = recount_lost(db, key, days[0] if days else None, days[-1] if days else None,
                           live_dir, anchor)["lost"]
        return {"paths": len(got), "people": sum(v[0] for v in got.values()),
                "search": sum(v[1] for v in got.values()), "ai": sum(v[2] for v in got.values())}
    if kind == "markdown":
        got = recount_lost(db, key, days[0] if days else None, days[-1] if days else None,
                           live_dir, anchor)
        return {"pages": len(got["md_live"]), "asks": sum(got["md_live"].values())} if before is None \
            else {"asked": sum(got["md_live"].values()) + sum(got["md_other"].values())}
    if kind == "sitemap":
        mine = {p: f for p, f in asks(db, key, days).items() if _sort(p) == "sitemap"
                and (before is not None or not (f["gone"] and f["gone"] >= f["last"]))}
        got = {p: f["search"] + f["ai"] for p, f in mine.items() if f["search"] + f["ai"]}
        return {"paths": len(got), "asked": sum(got.values()),
                "search": sum(f["search"] for f in mine.values())} if before is None else \
            {"asked": sum(got.values())}
    if kind == "errors":
        total, by_path, by_group = errors(db, key, days)
        named = [k for k in by_path if k != OTHER]
        return {"errors": total, "paths": len(named), "people": by_group["people"]} if before is None \
            else {"errors": total}
    if kind == "leave":
        got = landings(db, key, days, todo["subject"])
        return {"visits": got["visits"], "one_page": got["one_page"], "posted": got["posted"]}
    return {}


def still_of(db, key: str, todo: dict, after: list[str], before: list[str], live_dir=None, anchor=None) -> dict:
    """{address: asks or errors on the days after the mark}, this module's way: the addresses
    a failed fix's card names (#5, #6)."""
    kind = todo["kind"]
    if kind == "lost":
        old = {p for p, f in asks(db, key, before).items()
               if _sort(p) == "page" and f["people"] + f["search"] + f["ai"]}
        got = {p: f["people"] + f["search"] + f["ai"] for p, f in asks(db, key, after).items() if p in old}
    elif kind == "markdown":
        both = recount_lost(db, key, after[0] if after else None, after[-1] if after else None, live_dir, anchor)
        got = {**both["md_live"], **both["md_other"]}
    elif kind == "sitemap":
        got = {p: f["search"] + f["ai"] for p, f in asks(db, key, after).items() if _sort(p) == "sitemap"}
    elif kind == "errors":
        got = dict(errors(db, key, after)[1])
    else:
        return {}
    return {p: n for p, n in got.items() if n}


def bots_only_of(db, key: str, still: dict, after: list[str], days: list[str], live_dir=None,
                 anchor=None) -> list[str]:
    """The still-failing old addresses only bots ask for (#23), this module's way: no person
    asked on the days after the mark (its own SQL), and no live page like them, the live
    pages read by its own road (the pages blobs over the to-do's days and the kept sitemap).
    It shares one rule with the main count: closest_page.closest, which says whether an old
    address has a live page like it, as it shares LIMITS and the name lists."""
    people = {p: f["people"] for p, f in asks(db, key, after).items()}
    live = Live(set(served(db, key, days)) | set(sitemap(live_dir, anchor) or ()))
    return sorted(p for p in still if not people.get(p) and closest(p, live)[0] is None)


def own_status(todo: dict, again: dict | None) -> str:
    """The card's status from this module's recount: never from the list's own verdict."""
    state = todo.get("state")
    if state in ("open", "notnow"):
        return state
    if not again:
        return "checking"
    if todo["kind"] == "leave":
        if again["visits"] < LIMITS["leave_min_visits"]:
            return "checking"
        held = again["one_page"] / again["visits"] >= LIMITS["leave_share"] and not again["posted"]
        return "failed" if held else "passed"
    if todo["kind"] == "lost":
        return "failed" if again.get("left", sum(again.values())) else "passed"
    return "failed" if sum(again.values()) else "passed"


def check_todos(db, key: str, todos: list[dict], live_dir=None, anchor: str | None = None) -> dict[str, str]:
    """{to-do id: why} for each to-do whose figures, or whose re-check's, the second
    count does not find the same."""
    out: dict[str, str] = {}
    for t in todos:
        w = t.get("window") or {}
        days = verified_days(db, key, w.get("first"), w.get("last"))
        mine = figures_of(db, key, t, days, live_dir, anchor)
        if mine != t.get("figures"):
            out[t["id"]] = f"the second count finds {mine}, the list says {t.get('figures')}"
            continue
        r = t.get("recheck")
        again = None
        if r and r.get("days"):
            after = verified_days(db, key, r["first"], r["last"])
            before = verified_days(db, key, w.get("first"), r["marked_day"])
            if t["kind"] == "leave":
                again = figures_of(db, key, t, after, live_dir, anchor)
            else:
                again = figures_of(db, key, t, after, live_dir, anchor, before=before)
            if again != r.get("figures"):
                out[t["id"]] = f"the re-check: the second count finds {again}, the list says {r.get('figures')}"
                continue
            if t["kind"] != "leave":
                got = still_of(db, key, t, after, before, live_dir, anchor)
                mine = sorted(got.items(), key=lambda kv: (-kv[1], kv[0]))[:STILL_MOST]
                theirs = [tuple(x) for x in r.get("still") or []]
                if len(got) != r.get("still_total") or mine != theirs:
                    out[t["id"]] = (f"the re-check's addresses: the second count finds {len(got)} still failing "
                                    f"{mine[:3]}, the list says {r.get('still_total')} {theirs[:3]}")
                    continue
                if t["kind"] == "lost":
                    bots = bots_only_of(db, key, got, after, days, live_dir, anchor)
                    if bots != (r.get("bots_only") or []):
                        out[t["id"]] = (f"the re-check's addresses only bots ask for: the second count finds "
                                        f"{bots[:3]} ({len(bots)}), the list says {(r.get('bots_only') or [])[:3]}")
                        continue
                    again = {**again, "left": sum(v for p, v in got.items() if p not in set(bots))}
        if "status" in t and own_status(t, again) != t["status"]:
            out[t["id"]] = f"the status: the second count finds {own_status(t, again)}, the list says {t['status']}"
    return out
