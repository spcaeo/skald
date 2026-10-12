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

The window is the one the stored day says it used, so a later change of
`attribution.ai_window_minutes` never makes an old day disagree. Only
classify.py's name lists are shared.
"""
from __future__ import annotations

import re
from collections import Counter
from urllib.parse import parse_qsl

from .classify import AI_FETCHER_OWNERS, AI_LIKELY_MANY, CLICK_ID_PARAMS

UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")
REST = "(all others)"
_CUT = re.compile(r"[?#]")


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
        if first is None or labels["source"] != "Direct or unknown" or _tagged(first.url):
            return
        start = min(x.when for x in lines)
        self.direct.append((int(start.timestamp()) // 60, _page(labels["landing"]),
                            labels["landing"]))

    def _count(self, window: int) -> dict:
        assistants: Counter = Counter()
        pages: Counter = Counter()
        for stamp, page, landing in self.direct:
            who = {w for m, w, p in self.fetches if p == page and m <= stamp <= m + window}
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
        if blob is None:
            return
        got = self._count(int(blob.get("window_minutes", 0)))
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
