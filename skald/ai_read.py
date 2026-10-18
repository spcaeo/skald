"""What the AI read before it sent this visitor: the day kind `ai_read`, and
each AI visit's `ai_read` list of the pages its assistant fetched first.

An AI visit is one of two kinds, never mixed:

  cited   the visit followed a citation (source "AI assistant", from the
          referrer or an assistant's utm_source tag), from an assistant that
          has a user fetcher (classify.AI_FETCHER_OWNERS: ChatGPT, Claude,
          Perplexity, Gemini, Copilot, Mistral, Meta AI). A citation from an
          assistant with no known user fetcher (You.com, Phind, Poe) is left
          out: what it fetched cannot be seen, so it is not recorded, never 0.
  likely  the visit carries `likely_ai` (ai_likely.py): its assistant or
          assistants are the ones whose fetch made it likely.

Its assistant's user fetcher (classify.AI_ASKED only: ChatGPT-User,
Perplexity-User, Claude-User, ...; never a training or search crawler) may
have fetched pages in the window before the visit's first request: the same
minute or up to `attribution.ai_window_minutes` (default 15) minutes before,
compared to the minute in UTC, as ai_likely.py does. Those pages are context
("fetched by ChatGPT in the 15 minutes before"), never a count of people: a
fetch can be for someone else.

A visit with at least one such page carries `ai_read`:

  {"how": "cited" | "likely", "name": assistant or "(more than one)",
   "names": [assistants looked at], "window_minutes": int,
   "paths": [[path, assistant, minutes before the visit], ...] at most KEEP,
   "more": how many more (path, assistant) pairs were left out}

nearest first (then path, then assistant), each (path, assistant) once at its
nearest fetch. Paths as the fetch records keep them (no query, 70 characters).

The blob (kind `ai_read`; None when `attribution.ai_likely` is false or the
visits were not counted - "not recorded", never 0):

  window_minutes  the window the day was counted with
  cited           cited visits from an assistant with a user fetcher
  likely          likely visits (the `ai_likely` kind's `likely`)
  marked          visits that carry `ai_read`
  listed          paths listed over those visits (at most KEEP each)
  beyond          paths left out by the cap
  by_assistant    {assistant: {"cited", "fetched", "same_page", "likely"}}:
                  cited visits from it; of which it fetched a page in the
                  window before; of which the landing page was among those
                  pages ("fetch -> visit to the same page"); and likely
                  visits under its name (all land on a page it fetched: that
                  is the rule). "(more than one)" has only `likely`.

Second count: audit_ai_likely.py, from the raw lines with its own code.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter

from .ai_likely import WINDOW, minute, page_key
from .classify import AI_FETCHER_OWNERS
from .visits import ASSISTANTS

KEEP = 10
CITED = "AI assistant"
FETCHERS = frozenset(AI_FETCHER_OWNERS.values())
_BY_LABEL = {label: name for name, label in ASSISTANTS.items()}
FIELDS = ("cited", "fetched", "same_page", "likely")


def cited_name(j: dict) -> str:
    """The assistant a cited visit followed, by its citation name, or ""
    (not cited, or an assistant with no known user fetcher)."""
    if j.get("source") != CITED:
        return ""
    via = str(j.get("via") or "")
    name = _BY_LABEL.get(via, via)
    return name if name in FETCHERS else ""


def read_before(index: dict, names, at: int, window: int) -> list:
    """[[path, assistant, minutes before]] fetched by `names` in the window
    before minute `at`, nearest first, each (path, assistant) once. `index`
    is {assistant: (sorted minutes, their paths)}."""
    near: dict[tuple, int] = {}
    for who in names:
        minutes, paths = index.get(who) or ([], [])
        lo, hi = bisect_left(minutes, at - window), bisect_right(minutes, at)
        for fm, path in zip(minutes[lo:hi], paths[lo:hi]):
            key = (path, who)
            gap = at - fm
            if gap < near.get(key, gap + 1):
                near[key] = gap
    return sorted(([p, w, g] for (p, w), g in near.items()), key=lambda x: (x[2], x[0], x[1]))


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    conf = getattr(extras, "attribution", None) or {}
    on, window = conf.get("on", True), int(conf.get("window", WINDOW))
    firsts = getattr(extras, "visit_firsts", None)
    fetched = getattr(extras, "ai_fetches", None)
    if not on or journeys is None or firsts is None or fetched is None \
            or len(firsts) != len(journeys):
        return None
    rows: dict[str, list] = {}
    for m, who, path in fetched.rows:
        rows.setdefault(who, []).append((m, path))
    index = {}
    for who, got in rows.items():
        got.sort()
        index[who] = ([m for m, _ in got], [p for _, p in got])
    by: dict[str, Counter] = {}
    marked = listed = beyond = 0
    for j, first in zip(journeys, firsts):
        j.pop("ai_read", None)
        likely = j.get("likely_ai")
        if likely:
            how, name, names = "likely", likely["name"], list(likely.get("names") or [])
        else:
            name = cited_name(j)
            if not name:
                continue
            how, names = "cited", [name]
        got = read_before(index, names, minute(first), window)
        row = by.setdefault(name, Counter())
        if how == "likely":
            row["likely"] += 1
        else:
            row["cited"] += 1
            if got:
                row["fetched"] += 1
                landing = page_key(j.get("landing") or "")
                if any(page_key(p) == landing for p, _, _ in got):
                    row["same_page"] += 1
        if not got:
            continue
        marked += 1
        listed += min(len(got), KEEP)
        beyond += max(0, len(got) - KEEP)
        j["ai_read"] = {"how": how, "name": name, "names": sorted(names),
                        "window_minutes": window, "paths": got[:KEEP],
                        "more": max(0, len(got) - KEEP)}
    return {"window_minutes": window,
            "cited": int(sum(r["cited"] for r in by.values())),
            "likely": int(sum(r["likely"] for r in by.values())),
            "marked": marked, "listed": listed, "beyond": beyond,
            "by_assistant": {k: {f: int(by[k][f]) for f in FIELDS} for k in sorted(by)}}


def check(totals, blob, differs, problems) -> None:
    from .verify import Problem
    by = blob.get("by_assistant") or {}

    def total(field: str) -> int:
        return sum(int((v or {}).get(field, 0)) for v in by.values())

    differs("ai_read: cited visits by assistant", total("cited"), int(blob.get("cited", 0)),
            "cited visits")
    differs("ai_read: likely visits by assistant", total("likely"), int(blob.get("likely", 0)),
            "likely visits")
    differs("ai_read: visits with pages read before", total("fetched") + total("likely"),
            int(blob.get("marked", 0)), "marked visits")
    for who, row in by.items():
        if not int(row.get("same_page", 0)) <= int(row.get("fetched", 0)) <= int(row.get("cited", 0)):
            problems.append(Problem(f"ai_read: {who}", "same page above fetched, or fetched "
                                                        "above cited"))
    if int(blob.get("listed", 0)) > KEEP * int(blob.get("marked", 0)):
        problems.append(Problem("ai_read", f"more than {KEEP} paths listed for a visit"))
    likely = ((getattr(totals, "extras", None) or {}).get("ai_likely") or {}).get("likely")
    if likely is not None:
        differs("ai_read: likely visits", int(blob.get("likely", 0)), int(likely), "ai_likely")
    journeys = getattr(totals, "journeys", None)
    if journeys is not None:
        reads = [j["ai_read"] for j in journeys if j.get("ai_read")]
        differs("ai_read: journeys marked", len(reads), int(blob.get("marked", 0)),
                "marked visits")
        differs("ai_read: paths listed", sum(len(r.get("paths") or []) for r in reads),
                int(blob.get("listed", 0)), "listed paths")
        differs("ai_read: cited visits", sum(1 for j in journeys if cited_name(j)
                                             and not j.get("likely_ai")),
                int(blob.get("cited", 0)), "cited visits")
        if any(len(r.get("paths") or []) > KEEP for r in reads):
            problems.append(Problem("ai_read", f"a visit lists more than {KEEP} paths"))
