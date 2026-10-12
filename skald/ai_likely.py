"""Likely sent by an AI assistant: the day kind `ai_likely` (an inferred
figure, never part of the real counts), and the fetch records it rests on.

A person who clicks a link in a ChatGPT, Perplexity, Claude, Copilot or
Gemini answer often arrives with no referrer, so the visit lands in "Direct
or unknown". But when the person asked, the assistant's user fetcher
(classify.AI_ASKED: ChatGPT-User, Perplexity-User, Claude-User, ...) fetched
the page from the server at that moment. So:

  A visit is "likely referred by" an assistant when it came with no
  referrer and no campaign tag (source "Direct or unknown", no utm_ tag,
  no ad click id), and that assistant's user fetcher fetched the page the
  visit landed on in the same minute as the visit's first request or up to
  `attribution.ai_window_minutes` (default 15) minutes before it. Times are
  compared to the minute, in UTC. Two or more assistants in the window: the
  visit counts once, under classify.AI_LIKELY_MANY.

It is an estimate, labelled as one wherever it shows: a fetch can be for a
person who never clicked, and a click can come from someone else. It is
never added to the AI assistant source or to any real count. A visit in the
first minutes of a day cannot see the fetches of the day before, so it is a
floor, like citations.

The blob (kind `ai_likely`; None when `attribution.ai_likely` is false or
the visits were not counted - "not recorded", never 0):

  window_minutes  the window the day was counted with
  visits          the day's visits (journeys)
  direct          of which direct and untagged: what the figure can explain
  likely          of which likely referred by an assistant
  by_assistant    {assistant or "(more than one)": visits}, adds up to likely
  pages           {landing page: likely visits}, the TOP largest and
                  "(all others)", adds up to likely
  fetches         {assistant: user-fetch requests that day}, adds up to the
                  answer-engine group's "asked" requests
  followed        {assistant: those fetches followed, within the window, by
                  a direct untagged visit landing on the same page} - a
                  fetch-side figure: a visit two assistants fetched for
                  follows a fetch of each

Each likely visit's journey carries `likely_ai`: {"name", "names",
"minutes"} (the assistant or "(more than one)", every assistant in the
window, and the minutes from the nearest fetch to the visit).

The kind `ai_fetches` (ai_fetches.py) keeps the day's user fetches as
[minute, assistant, path, n] rows - no address, no user agent - for
FETCH_DAYS, so leads and conversions can look back at the fetch before a
lead's first or last touch (`fetch_index`, `likely_for`).

Second count: audit_ai_likely.py, from the raw lines with its own code; it
shares only classify.py's name lists.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from .classify import AI_FETCHER_OWNERS, AI_LIKELY_MANY, Group, Tier

WINDOW = 15
FETCH_DAYS = 180
TOP = 20
OTHER = "(all others)"
DIRECT = "Direct or unknown"
NOT_RECORDED = "(not recorded)"
NONE = "(none)"
METHOD = ("Inferred, not counted: a visit with no referrer and no campaign tag that landed "
          "on a page an AI assistant's user fetcher (ChatGPT-User, Perplexity-User, "
          "Claude-User, ...) had fetched in the same minute or up to {w} minutes before. "
          "Likely, never certain.")


def settings(config: dict | None) -> dict:
    """{"on", "window"} from `attribution.ai_likely` (default true) and
    `attribution.ai_window_minutes` (default 15, at least 0)."""
    got = (config or {}).get("attribution") or {}
    on = got.get("ai_likely", True) not in (False, "false", "no", "off", 0)
    try:
        window = max(0, int(got.get("ai_window_minutes", WINDOW)))
    except (TypeError, ValueError):
        window = WINDOW
    return {"on": on, "window": window}


def owner(engine: str) -> str:
    """The assistant a user fetcher belongs to."""
    low = (engine or "").lower()
    return AI_FETCHER_OWNERS.get(low, low)


def page_key(path: str) -> str:
    """A page as the window compares it: no query, 70 characters (as
    journeys keep it), no trailing slash."""
    bare = str(path or "").split("?", 1)[0].split("#", 1)[0][:70]
    return bare.rstrip("/") or "/"


def minute(when: datetime) -> int:
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    return int(when.timestamp()) // 60


def _stored_minute(at: str) -> int:
    """minute() of a stored "%Y-%m-%dT%H:%M" (UTC). The usual shape is read
    by position, which is what strptime would give, at a tenth of its cost;
    anything else goes to strptime, which accepts or refuses it as before."""
    digits = at[:4] + at[5:7] + at[8:10] + at[11:13] + at[14:]
    if len(at) == 16 and at[4] == at[7] == "-" and at[10] == "T" and at[13] == ":" \
            and digits.isascii() and digits.isdigit():
        when = datetime(int(at[:4]), int(at[5:7]), int(at[8:10]), int(at[11:13]),
                        int(at[14:]), tzinfo=timezone.utc)
    else:
        when = datetime.strptime(at, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    return minute(when)


def minute_iso(m: int) -> str:
    return datetime.fromtimestamp(m * 60, timezone.utc).strftime("%Y-%m-%dT%H:%M")


class Fetches:
    """The tally pass's user fetches (extras.Extras offers it every hit)."""

    def __init__(self) -> None:
        self.rows: list[tuple[int, str, str]] = []      # (minute, assistant, path)

    def add(self, hit, verdict) -> None:
        if verdict.group is Group.ANSWER_ENGINE and verdict.tier is Tier.ASKED:
            self.rows.append((minute(hit.when), owner(verdict.engine), hit.path[:70]))


def direct_untagged(j: dict) -> bool:
    """A visit with no referrer and no campaign tag (no utm_ tag, no click id)."""
    return j.get("source") == DIRECT and not j.get("utm") and not j.get("paid")


def _fold(paths: Counter) -> dict:
    ordered = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))
    out = dict(ordered[:TOP])
    rest = sum(n for _, n in ordered[TOP:])
    if rest:
        out[OTHER] = rest
    return out


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    conf = getattr(extras, "attribution", None) or {}
    on, window = conf.get("on", True), int(conf.get("window", WINDOW))
    firsts = getattr(extras, "visit_firsts", None)
    fetched = getattr(extras, "ai_fetches", None)
    if not on or journeys is None or firsts is None or fetched is None \
            or len(firsts) != len(journeys):
        return None
    by_page: dict[str, list] = {}
    for m, who, path in fetched.rows:
        by_page.setdefault(page_key(path), []).append((m, who))
    for got in by_page.values():
        got.sort()
    direct = 0
    by_assistant: Counter = Counter()
    pages: Counter = Counter()
    landed: dict[str, list[int]] = {}
    for j, first in zip(journeys, firsts):
        if not direct_untagged(j):
            continue
        direct += 1
        m, key = minute(first), page_key(j.get("landing") or "")
        landed.setdefault(key, []).append(m)
        near: dict[str, int] = {}
        for fm, who in by_page.get(key, ()):
            if 0 <= m - fm <= window:
                near[who] = min(near.get(who, m - fm), m - fm)
        if not near:
            continue
        name = next(iter(near)) if len(near) == 1 else AI_LIKELY_MANY
        by_assistant[name] += 1
        pages[str(j.get("landing") or "")] += 1
        j["likely_ai"] = {"name": name, "names": sorted(near), "minutes": min(near.values())}
    for got in landed.values():
        got.sort()
    fetches: Counter = Counter()
    followed: Counter = Counter()
    for m, who, path in fetched.rows:
        fetches[who] += 1
        seen = landed.get(page_key(path), [])
        if bisect_right(seen, m + window) > bisect_left(seen, m):
            followed[who] += 1
    return {"window_minutes": window, "visits": len(journeys), "direct": direct,
            "likely": int(sum(by_assistant.values())),
            "by_assistant": dict(sorted(by_assistant.items())), "pages": _fold(pages),
            "fetches": dict(sorted(fetches.items())),
            "followed": {k: int(followed.get(k, 0)) for k in sorted(fetches)}}


def check(totals, blob, differs, problems) -> None:
    from .verify import Problem
    likely = int(blob.get("likely", 0))
    differs("ai_likely: likely visits by assistant",
            sum(int(v) for v in (blob.get("by_assistant") or {}).values()), likely, "visits")
    differs("ai_likely: likely visits by landing page",
            sum(int(v) for v in (blob.get("pages") or {}).values()), likely, "visits")
    stats = getattr(totals, "visits", None)
    if stats is not None:
        differs("ai_likely: visits", int(blob.get("visits", 0)), int(stats.visits), "visits")
    if not likely <= int(blob.get("direct", 0)) <= int(blob.get("visits", 0)):
        problems.append(Problem("ai_likely", "likely visits are not within the direct "
                                             "visits, or the direct within the visits"))
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    differs("ai_likely: user fetches by assistant",
            sum(int(v) for v in (blob.get("fetches") or {}).values()),
            int(engines.tiers.get("asked", 0)) if engines else 0, "asked fetches")
    for who, n in (blob.get("followed") or {}).items():
        if int(n) > int((blob.get("fetches") or {}).get(who, 0)):
            problems.append(Problem(f"ai_likely: {who}", "more fetches followed than fetches"))
    journeys = getattr(totals, "journeys", None)
    if journeys is not None:
        differs("ai_likely: journeys marked likely",
                sum(1 for j in journeys if j.get("likely_ai")), likely, "likely visits")


# ------------------------------------------- leads and conversions (later)

def fetch_index(history, site: str, first: date, last: date) -> dict:
    """The stored user fetches of the verified, whole days in [first, last]:
    {"days": {local day}, "pages": {page_key: [(minute, assistant)]}}.
    A day not in "days" was not recorded: a touch whose window reaches into
    it is "(not recorded)", never "none"."""
    days = {e["day"].isoformat() for e in history.daily(site, first, last)
            if e.get("state") == "ok"}
    pages: dict[str, list] = {}
    kept: set = set()
    for day, blobs in history.extras(site, first, last, ("ai_fetches",)).items():
        rows = (blobs.get("ai_fetches") or {}).get("rows")
        if day not in days or rows is None:
            continue
        kept.add(day)
        for at, who, path, _n in rows:
            pages.setdefault(page_key(path), []).append((_stored_minute(at), who))
    for got in pages.values():
        got.sort()
    return {"days": kept, "pages": pages}


def likely_for(index: dict | None, path: str, at: datetime | None, window: int, tz) -> str:
    """A touch's likely assistant: its name, "(more than one)", "(none)", or
    "(not recorded)" when the fetches of its window were not kept (or the
    touch has no page or time)."""
    if index is None or at is None or not path:
        return NOT_RECORDED
    m = minute(at)
    for edge in (m - window, m):
        moment = datetime.fromtimestamp(edge * 60, timezone.utc)
        if moment.astimezone(tz).date().isoformat() not in index["days"]:
            return NOT_RECORDED
    near = {who for fm, who in index["pages"].get(page_key(path), ()) if 0 <= m - fm <= window}
    if not near:
        return NONE
    return next(iter(near)) if len(near) == 1 else AI_LIKELY_MANY

