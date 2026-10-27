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

  Unless chance explains it (2026-10-25). An assistant that fetches a page
  all day long covers so many minutes that ordinary direct visits land in
  them anyway: on one site ChatGPT-User fetched the home page 78 times in
  four days, its windows covered 12 to 29 % of each day, and of the 15 to 38
  direct home-page visits a day, 25 in all were "likely ChatGPT", where
  chance alone gives about 19. So for each assistant and page of the day:

    covered   the minutes in which a visit would match: every minute from
              one of its fetches of the page to `window` minutes after it,
              each minute once
    chance    the day's direct untagged visits landing on the page x
              covered / 1440: the visits expected in those minutes if those
              visits came at random times through the day
    by chance chance >= CHANCE_LIMIT (a quarter of a visit): its fetches of
              that page that day are no evidence, and a visit there is not
              made likely by that assistant

  At a quarter, one such page in five or fewer gets a chance visit (1 -
  e^-0.25). The direct visits counted include the real ones, so the rule
  errs towards saying nothing. A rarely visited page (one direct visit, a
  few fetches) stays well under it; the home page of a site people type in
  does not. No page is named: a page is weak evidence only when its own
  figures say so. The home page's Markdown copy (/index.md) is not the home
  page: a fetch of it never made a visit to / likely.

It is an estimate, labelled as one wherever it shows: a fetch can be for a
person who never clicked, and a click can come from someone else. It is
never added to the AI assistant source or to any real count. A visit in the
first minutes of a day cannot see the fetches of the day before, so it is a
floor, like citations.

The blob (kind `ai_likely`; None when `attribution.ai_likely` is false or
the visits were not counted - "not recorded", never 0):

  window_minutes  the window the day was counted with
  chance_limit    the limit the day was counted with (absent: counted
                  before the rule, with none)
  by_chance       {assistant: [pages]} (page as the window compares it)
                  whose fetches that day were no evidence; leads and
                  conversions leave the same fetches out (fetch_index)
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
  reads           {assistant: its reads that day} (ai_reads.py: a page asked
                  for again within the read's window, or a file the page
                  loaded, is no read); adds up to the day's ai_reads reads.
                  Absent on a day counted before reads were
  reads_followed  {assistant: those reads followed the same way}

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
CHANCE_LIMIT = 0.25          # visits chance alone may put in the windows
DAY_MINUTES = 1440
FETCH_DAYS = 180
TOP = 20
OTHER = "(all others)"
DIRECT = "Direct or unknown"
NOT_RECORDED = "(not recorded)"
NONE = "(none)"
METHOD = ("Inferred, not counted: a visit with no referrer and no campaign tag that landed "
          "on a page an AI assistant's user fetcher (ChatGPT-User, Perplexity-User, "
          "Claude-User, ...) had fetched in the same minute or up to {w} minutes before, "
          "unless that assistant fetched the page so often that day that direct visits "
          "would land after its fetches by chance. Likely, never certain.")


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
        # (minute, assistant, path) -> the reads that began there (ai_reads.py)
        self.started: Counter = Counter()
        self.reads: list[tuple[int, str, str]] = []     # the rows that began a read

    def add(self, hit, verdict, role: str | None = None) -> None:
        if verdict.group is Group.ANSWER_ENGINE and verdict.tier is Tier.ASKED:
            row = (minute(hit.when), owner(verdict.engine), hit.path[:70])
            self.rows.append(row)
            if role == "read":
                self.started[row] += 1
                self.reads.append(row)


def direct_untagged(j: dict) -> bool:
    """A visit with no referrer and no campaign tag (no utm_ tag, no click id)."""
    return j.get("source") == DIRECT and not j.get("utm") and not j.get("paid")


def by_chance(by_page: dict, direct: Counter, window: int,
              limit: float = CHANCE_LIMIT) -> set:
    """The (assistant, page) pairs whose fetches of the day are no evidence
    (see the module's note): {page: [(minute, assistant)]} of the fetches,
    {page: direct untagged visits landing on it}."""
    out = set()
    for key, got in by_page.items():
        if not direct.get(key):
            continue
        covered: dict[str, set] = {}
        for fm, who in got:
            covered.setdefault(who, set()).update(range(fm, fm + window + 1))
        for who, minutes in covered.items():
            if direct[key] * len(minutes) / DAY_MINUTES >= limit:
                out.add((who, key))
    return out


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
    directs = [(j, minute(first), page_key(j.get("landing") or ""))
               for j, first in zip(journeys, firsts) if direct_untagged(j)]
    direct = len(directs)
    chance = by_chance(by_page, Counter(key for _, _, key in directs), window)
    by_assistant: Counter = Counter()
    pages: Counter = Counter()
    landed: dict[str, list[int]] = {}
    for j, m, key in directs:
        landed.setdefault(key, []).append(m)
        near: dict[str, int] = {}
        for fm, who in by_page.get(key, ()):
            if 0 <= m - fm <= window and (who, key) not in chance:
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
    # The same for reads (ai_reads.py): a page asked for again in its read's
    # window, or a file it loaded, is no second chance to be followed.
    reads: Counter = Counter()
    reads_followed: Counter = Counter()
    for m, who, path in getattr(fetched, "reads", ()):
        reads[who] += 1
        seen = landed.get(page_key(path), [])
        if bisect_right(seen, m + window) > bisect_left(seen, m):
            reads_followed[who] += 1
    ruled: dict[str, list] = {}
    for who, key in sorted(chance):
        ruled.setdefault(who, []).append(key)
    return {"window_minutes": window, "chance_limit": CHANCE_LIMIT, "by_chance": ruled,
            "visits": len(journeys), "direct": direct,
            "likely": int(sum(by_assistant.values())),
            "by_assistant": dict(sorted(by_assistant.items())), "pages": _fold(pages),
            "fetches": dict(sorted(fetches.items())),
            "followed": {k: int(followed.get(k, 0)) for k in sorted(fetches)},
            "reads": {k: int(reads.get(k, 0)) for k in sorted(fetches)},
            "reads_followed": {k: int(reads_followed.get(k, 0)) for k in sorted(fetches)}}


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
    for who, n in (blob.get("reads") or {}).items():
        if not int((blob.get("reads_followed") or {}).get(who, 0)) <= int(n) \
                <= int((blob.get("fetches") or {}).get(who, 0)):
            problems.append(Problem(f"ai_likely: {who}", "reads followed, reads and fetches "
                                                         "do not nest"))
    reads = ((getattr(totals, "extras", None) or {}).get("ai_reads") or {}).get("reads")
    if blob.get("reads") is not None and reads is not None:
        differs("ai_likely: reads by assistant", sum(int(v) for v in blob["reads"].values()),
                int(reads), "reads (ai_reads)")
    journeys = getattr(totals, "journeys", None)
    if journeys is not None:
        differs("ai_likely: journeys marked likely",
                sum(1 for j in journeys if j.get("likely_ai")), likely, "likely visits")


# ------------------------------------------- leads and conversions (later)

def fetch_index(history, site: str, first: date, last: date) -> dict:
    """The stored user fetches of the verified, whole days in [first, last]:
    {"days": {local day}, "pages": {page_key: [(minute, assistant)]}}.
    A day not in "days" was not recorded: a touch whose window reaches into
    it is "(not recorded)", never "none". A day's fetches its `ai_likely`
    blob calls "by chance" are left out, as they are for the day's visits."""
    days = {e["day"].isoformat() for e in history.daily(site, first, last)
            if e.get("state") == "ok"}
    pages: dict[str, list] = {}
    kept: set = set()
    for day, blobs in history.extras(site, first, last, ("ai_fetches", "ai_likely")).items():
        rows = (blobs.get("ai_fetches") or {}).get("rows")
        if day not in days or rows is None:
            continue
        kept.add(day)
        ruled = {(who, key) for who, keys in
                 ((blobs.get("ai_likely") or {}).get("by_chance") or {}).items() for key in keys}
        for at, who, path, *_n in rows:
            if (who, page_key(path)) not in ruled:
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

