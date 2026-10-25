"""The second count of "likely sent by an AI assistant" (day kinds
`ai_likely` and `ai_fetches`).

Registered in audit_more.RECOUNTS. It sees every line the audit judged
(`hit`) and every people visit (`visit`), and rebuilds the figure from them
with its own code, written apart from ai_likely.py:

  a user fetch      a line the audit put in "answer_engines" whose agent
                    matched classify.AI_ASKED; its assistant from
                    classify.AI_FETCHER_OWNERS; its minute is the line's
                    epoch seconds // 60
  a direct visit    a visit that read a page whose source (the audit's own
                    label) is "Direct or unknown" and whose first page's
                    query string (urllib.parse.parse_qsl here) has no utm_
                    tag with something in it and no ad click id
                    (classify.CLICK_ID_PARAMS)
  the same page     both paths cut at "?" or "#", to 70 characters, with
                    any trailing "/" taken off ("/" stays "/")
  likely            a fetch of the visit's page whose minute is the visit's
                    first minute or up to the window before it; two or more
                    assistants make it "(more than one)"
  by chance         an assistant's fetches of a page are left out of
                    "likely" when the day's direct visits landing on that
                    page, times the distinct minutes its fetches of it reach
                    (each fetch's minute and the window after), come to
                    the stored day's chance_limit x 24 x 60 or more (no
                    chance_limit stored: the day was counted before the
                    rule, and nothing is left out)

The window is the one the stored day says it used, so a later change of
`attribution.ai_window_minutes` never makes an old day disagree. Only
classify.py's name lists are shared.

The day kind `ai_read` (what an AI visit's assistant fetched before it) is
rebuilt here too:

  a cited visit     a visit whose source (the audit's label) is "AI
                    assistant"; its assistant read here from the first
                    page's referrer host (classify.AI_REFERRER_HOSTS, the
                    bing.com/chat path) or its utm_source tag
                    (classify.AI_UTM), named by classify.ASSISTANT_ALIASES;
                    kept only when that assistant has a user fetcher (a
                    value of classify.AI_FETCHER_OWNERS)
  its assistants    the cited one; for a likely visit, every assistant that
                    made it likely
  read before       the distinct (path as fetched, assistant) pairs those
                    assistants' user fetches made in the visit's first minute
                    or up to the window before it; at most 10 listed
  same page         the landing page (the rule above) is one of those paths
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import parse_qsl, urlsplit

from .classify import (AI_FETCHER_OWNERS, AI_LIKELY_MANY, AI_REFERRER_HOSTS,
                       AI_REFERRER_PATHS, AI_UTM, ASSISTANT_ALIASES, CLICK_ID_PARAMS)

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
REST = "(all others)"
_CUT = re.compile(r"[?#]")
LISTED = 10                                     # paths a visit's list keeps
_HAS_FETCHER = set(AI_FETCHER_OWNERS.values())


def _sent_by(line) -> str:
    """The assistant whose citation this page view followed, or ""."""
    ref = line.referrer or ""
    try:
        parts = urlsplit(ref if "//" in ref else "//" + ref)
        host = (parts.hostname or "").lower().rstrip(".") if ref else ""
    except ValueError:
        parts, host = None, ""
    if host:
        for domain in AI_REFERRER_HOSTS:
            if host == domain or host.endswith("." + domain):
                return ASSISTANT_ALIASES.get(domain, domain)
        for domain, prefix in AI_REFERRER_PATHS.items():
            if (host == domain or host.endswith("." + domain)) and \
                    parts.path.startswith(prefix):
                return ASSISTANT_ALIASES.get(domain + prefix, domain + prefix)
    tagged = AI_UTM.search(line.url or "")
    if tagged:
        raw = tagged.group(1).strip().lower()
        return ASSISTANT_ALIASES.get(raw, raw)
    return ""


def _page(path: str) -> str:
    got = _CUT.split(path or "", 1)[0][:70]
    while got.endswith("/") and len(got) > 1:
        got = got[:-1]
    return got or "/"


def _tagged(url: str) -> bool:
    query = url.split("?", 1)[1] if "?" in url else ""
    try:
        pairs = parse_qsl(query)[:60]
    except ValueError:
        return False
    seen: dict[str, str] = {}
    for key, value in pairs:
        seen[key.lower()] = value
    return any(seen.get(k, "").strip() for k in UTM_KEYS) or \
        any(seen.get(k) for k in CLICK_ID_PARAMS)


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.fetches: list[tuple[int, str, str]] = []      # (minute, assistant, page)
        self.raw: Counter = Counter()                       # (minute, assistant, path)
        self.visits = 0
        self.direct: list[tuple[int, str, str]] = []       # (minute, page, landing)
        self.cited: list[tuple[int, str, str]] = []        # (minute, assistant, page)

    def hit(self, line, group, tier, name) -> None:
        if group != "answer_engines" or tier != "asked":
            return
        who = AI_FETCHER_OWNERS.get(name.lower(), name.lower())
        stamp = int(line.when.timestamp()) // 60
        self.fetches.append((stamp, who, _page(line.path)))
        self.raw[(stamp, who, line.path[:70])] += 1

    def visit(self, lines, is_page, labels) -> None:
        if labels is None:
            return
        self.visits += 1
        first = next((x for x in lines if is_page(x)), None)
        if first is None:
            return
        start = int(min(x.when for x in lines).timestamp()) // 60
        if labels["source"] == "AI assistant":
            who = _sent_by(first)
            if who in _HAS_FETCHER:
                self.cited.append((start, who, _page(labels["landing"])))
            return
        if labels["source"] != "Direct or unknown" or _tagged(first.url):
            return
        self.direct.append((start, _page(labels["landing"]), labels["landing"]))

    def _weak(self, window: int, limit) -> set:
        """The (assistant, page) pairs whose fetches chance explains."""
        if limit is None:
            return set()
        landings = Counter(page for _, page, _ in self.direct)
        reach: dict[tuple, set] = {}
        for m, w, p in self.fetches:
            if landings[p]:
                reach.setdefault((w, p), set()).update(range(m, m + window + 1))
        return {pair for pair, minutes in reach.items()
                if landings[pair[1]] * len(minutes) >= float(limit) * 24 * 60}

    def _read(self, window: int, weak: set = frozenset()) -> dict:
        """The `ai_read` figures, from the visits and the raw fetch rows."""
        rows = {"cited": Counter(), "fetched": Counter(), "same_page": Counter(),
                "likely": Counter()}
        marked = listed = beyond = 0
        visits = [("cited", stamp, who, {who}, page) for stamp, who, page in self.cited]
        for stamp, page, _ in self.direct:
            near = {w for m, w, p in self.fetches
                    if p == page and m <= stamp <= m + window and (w, p) not in weak}
            if near:
                one = next(iter(near)) if len(near) == 1 else AI_LIKELY_MANY
                visits.append(("likely", stamp, one, near, page))
        for how, stamp, who, near, page in visits:
            pairs = {(path, w) for (m, w, path) in self.raw
                     if w in near and m <= stamp <= m + window}
            rows[how][who] += 1
            if how == "cited" and pairs:
                rows["fetched"][who] += 1
                if any(_page(path) == page for path, _ in pairs):
                    rows["same_page"][who] += 1
            if pairs:
                marked += 1
                listed += min(LISTED, len(pairs))
                beyond += max(0, len(pairs) - LISTED)
        return {"rows": rows, "marked": marked, "listed": listed, "beyond": beyond}

    def _compare_read(self, blob, same, limit) -> None:
        window = int(blob.get("window_minutes", 0))
        got = self._read(window, self._weak(window, limit))
        rows = got["rows"]
        same("ai_read: cited visits", int(blob.get("cited", 0)), sum(rows["cited"].values()))
        same("ai_read: likely visits", int(blob.get("likely", 0)), sum(rows["likely"].values()))
        for key in ("marked", "listed", "beyond"):
            same(f"ai_read: {key}", int(blob.get(key, 0)), got[key])
        mine = blob.get("by_assistant") or {}
        names = set(mine) | {w for c in rows.values() for w, n in c.items() if n}
        for who in sorted(names):
            for field in ("cited", "fetched", "same_page", "likely"):
                same(f"ai_read: {field} for {who}", int((mine.get(who) or {}).get(field, 0)),
                     rows[field][who])

    def _count(self, window: int, weak: set = frozenset()) -> dict:
        assistants: Counter = Counter()
        pages: Counter = Counter()
        for stamp, page, landing in self.direct:
            who = {w for m, w, p in self.fetches
                   if p == page and m <= stamp <= m + window and (w, p) not in weak}
            if who:
                assistants[who.pop() if len(who) == 1 else AI_LIKELY_MANY] += 1
                pages[landing] += 1
        fetched: Counter = Counter()
        followed: Counter = Counter()
        for m, w, p in self.fetches:
            fetched[w] += 1
            if any(page == p and m <= stamp <= m + window for stamp, page, _ in self.direct):
                followed[w] += 1
        return {"assistants": assistants, "pages": pages, "fetched": fetched,
                "followed": followed}

    def compare(self, stored, same, problems) -> None:
        rows = stored.get("ai_fetches")
        if rows is not None:
            kept = Counter()
            for at, who, path, n in rows.get("rows") or []:
                kept[(at, who, path)] += int(n)
            from datetime import datetime, timezone
            counted = Counter()
            for (stamp, who, path), n in self.raw.items():
                at = datetime.fromtimestamp(int(stamp) * 60, timezone.utc)
                counted[(at.strftime("%Y-%m-%dT%H:%M"), who, path)] += n
            for key in sorted(set(kept) | set(counted)):
                same(f"ai_fetches: {key[1]} on {key[2]} at {key[0]}", kept[key], counted[key])
        blob = stored.get("ai_likely")
        limit = (blob or {}).get("chance_limit")
        if stored.get("ai_read") is not None:
            self._compare_read(stored["ai_read"], same, limit)
        if blob is None:
            return
        window = int(blob.get("window_minutes", 0))
        weak = self._weak(window, limit)
        kept = {(w, p) for w, ps in (blob.get("by_chance") or {}).items() for p in ps}
        for w, p in sorted(kept | weak):
            same(f"ai_likely: {w}'s fetches of {p} by chance", int((w, p) in kept),
                 int((w, p) in weak))
        got = self._count(window, weak)
        same("ai_likely: visits", int(blob.get("visits", 0)), self.visits)
        same("ai_likely: direct untagged visits", int(blob.get("direct", 0)), len(self.direct))
        same("ai_likely: likely visits", int(blob.get("likely", 0)),
             sum(got["assistants"].values()))
        mine = {k: int(v) for k, v in (blob.get("by_assistant") or {}).items()}
        for who in sorted(set(mine) | set(got["assistants"])):
            same(f"ai_likely: likely from {who}", mine.get(who, 0), got["assistants"][who])
        kept = {k: int(v) for k, v in (blob.get("pages") or {}).items()}
        for path in sorted(k for k in kept if k != REST):
            same(f"ai_likely: likely visits landing on {path}", kept[path], got["pages"][path])
        listed = sum(got["pages"][k] for k in kept if k != REST)
        same(f"ai_likely: likely visits landing on {REST}", kept.get(REST, 0),
             sum(got["pages"].values()) - listed)
        for name, key in (("fetches", "fetched"), ("followed", "followed")):
            mine = {k: int(v) for k, v in (blob.get(name) or {}).items()}
            for who in sorted(set(mine) | set(got[key])):
                if mine.get(who, 0) or got[key][who]:
                    same(f"ai_likely: {name} by {who}", mine.get(who, 0), got[key][who])
