"""Per-day counts for the bots tab: verified crawlers, link previews, fake browsers.

Built in the tally pass (extras.Extras offers it every counted hit) into the
day's "bots" extras blob (DATA-CONTRACT.md, bots.json):

  verification   per named assistant or search crawler: the group it counts
                 in, how it can be checked, and its requests verified,
                 unverified and spoofed (the spoofed ones are in bots)
  link_previews  link-preview fetches by app
  fake_browsers  people's requests carrying a fake-browser flag, and from
                 how many addresses (a count, never the addresses)
  blocked        403 answers per AI crawler of bot_policy.CATALOG, by the
                 token its user agent carries: what the AI crawler settings
                 refused (any other 403 to that crawler counts too)
  not_rendered   browser-like requests moved to bots because their visit
                 never rendered a page (rendering.py): requests, page views,
                 and readers - the visits among them that read a page, which
                 would otherwise have been counted as visitors

`check()` holds the sums: verified + unverified add up to each crawler
group's requests; spoofed and link previews are inside bots; flagged
requests are inside people.
"""
from __future__ import annotations

from collections import Counter

from .bot_policy import match as policy_crawler
from .bot_verify import method_of, vendor_of
from datetime import timedelta

from .classify import (AI_ASKED, AI_TRAINING, FAKE_BROWSER_FLAGS, LINK_PREVIEW, NOT_RENDERED,
                       Group)


def claim_group(name: str) -> str:
    """Where a crawler name counts when its claim holds."""
    return (Group.ANSWER_ENGINE.value if AI_ASKED.fullmatch(name) or AI_TRAINING.fullmatch(name)
            else Group.SEARCH_ENGINE.value)


class BotCounts:
    def __init__(self, gap_minutes: int = 30) -> None:
        self.gap = timedelta(minutes=gap_minutes)
        # (address, agent) -> [(when, is_page)] of requests that never rendered.
        self.unrendered: dict[tuple, list] = {}
        self.checks: dict[str, Counter] = {}
        self.groups: dict[str, str] = {}
        self.previews: Counter = Counter()
        self.flagged: dict[str, Counter] = {f: Counter() for f in FAKE_BROWSER_FLAGS}
        self.addresses: dict[str, set] = {f: set() for f in FAKE_BROWSER_FLAGS}
        self.blocked: Counter = Counter()

    def add(self, hit, verdict) -> None:
        if hit.status == "403":
            crawler = policy_crawler(hit.user_agent)
            if crawler is not None:
                self.blocked[crawler.name] += 1
        group = verdict.group
        if group in (Group.ANSWER_ENGINE, Group.SEARCH_ENGINE) and verdict.engine:
            name = verdict.engine
            self.groups.setdefault(name, group.value)
            self.checks.setdefault(name, Counter())[
                "verified" if verdict.verified == "verified" else "unverified"] += 1
        elif group is Group.BOTS:
            if verdict.verified == "spoofed" and verdict.claim:
                self.groups.setdefault(verdict.claim, claim_group(verdict.claim))
                self.checks.setdefault(verdict.claim, Counter())["spoofed"] += 1
            elif verdict.engine.startswith(LINK_PREVIEW):
                self.previews[verdict.engine[len(LINK_PREVIEW):]] += 1
            elif verdict.engine == NOT_RENDERED:
                self.unrendered.setdefault((hit.address, hit.user_agent), []).append(
                    (hit.when, hit.is_page))
        elif group is Group.PEOPLE:
            for flag in verdict.flags:
                self.flagged[flag]["requests"] += 1
                self.addresses[flag].add(hit.address)

    def finish(self) -> dict:
        return {
            "verification": {
                name: {"group": self.groups[name], "method": method_of(vendor_of(name)),
                       **{k: int(c.get(k, 0)) for k in ("verified", "unverified", "spoofed")}}
                for name, c in sorted(self.checks.items())},
            "link_previews": dict(self.previews.most_common()),
            "fake_browsers": {f: {"requests": int(self.flagged[f]["requests"]),
                                  "addresses": len(self.addresses[f])}
                              for f in FAKE_BROWSER_FLAGS},
            "blocked": dict(sorted(self.blocked.items())),
            "not_rendered": self._not_rendered(),
        }

    def _not_rendered(self) -> dict:
        requests = pages = readers = 0
        for seen in self.unrendered.values():
            seen.sort(key=lambda e: e[0])
            read, last = False, None
            for when, page in seen:
                if last is not None and when - last > self.gap:
                    readers += read
                    read = False
                last = when
                requests += 1
                pages += page
                read = read or page
            readers += read
        return {"requests": requests, "pages": pages, "readers": readers}


def check(totals, blob: dict | None, differs, problems: list) -> None:
    """The sums a bots blob promises, against its own day's totals."""
    from .verify import Problem
    if not blob:
        return
    ver = blob.get("verification") or {}
    for group in (Group.ANSWER_ENGINE, Group.SEARCH_ENGINE):
        stats = totals.groups.get(group)
        got = sum(v["verified"] + v["unverified"] for v in ver.values()
                  if v["group"] == group.value)
        differs(f"{group.value}: verified and unverified requests", got,
                stats.hits if stats else 0, "requests in the group")
    bots = totals.groups.get(Group.BOTS)
    inside = sum(v["spoofed"] for v in ver.values()) + sum(
        (blob.get("link_previews") or {}).values())
    if inside > (bots.hits if bots else 0):
        problems.append(Problem("spoofed crawlers and link previews",
                                f"{inside:,} is more than the {bots.hits if bots else 0:,} "
                                f"bot requests they are part of"))
    moved = (blob.get("not_rendered") or {}).get("requests", 0)
    if moved > (bots.hits if bots else 0):
        problems.append(Problem("browser-like requests that never rendered",
                                f"{moved:,} is more than the {bots.hits if bots else 0:,} "
                                f"bot requests they are part of"))
    people = totals.groups.get(Group.PEOPLE)
    for flag, got in (blob.get("fake_browsers") or {}).items():
        if got["requests"] > (people.hits if people else 0):
            problems.append(Problem(f"fake browsers ({flag})",
                                    "more flagged requests than people's requests"))
