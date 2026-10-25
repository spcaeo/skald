"""What AI crawlers and assistants got back, by address: the day kind `ai_status`
(2.35, AI readiness per page: ai_ready.py).

Every request of an AI crawler or assistant: the answer engines classify.py
names, both tiers ("asked", a fetch for someone's question; "training", a
crawler collecting), as crawl_health.py follows them (a name and a tier). By
the path (no query string, first 200 characters) and the name:

  answers   {path: {name: {status: n}}}: every request answered with any
            status but 200 and 304 (a redirect, a 404, a 403, a 5xx, ...),
            and every request for a Markdown copy of a page (a path that ends
            ".md", ".mdx" or ".markdown", trailing slashes aside: the
            not-a-page list's "markdown" entry, not_pages.RULES), whatever
            it was answered. The status as the log writes it.
  slow      {path: {name: n}}: requests the server took SLOW_MS or more to
            answer (crawl_health.SLOW_MS), whatever the status
  plain     {name: n}: the rest, a 200 or 304 for an address that is no
            Markdown copy; listed by name only, so the blob stays small
  timed     {name: n}: requests whose line records the server's time; slow is
            measured on those only (a log without the time: timed 0, and
            "slow" is not recorded, never 0)

`answers` and `slow` each keep their KEEP paths with most requests (ties by
path) and sum the rest into one "(all others)" path per name; `folded` says
how many paths each summed (0: every path is listed). So every sum holds:
per name, its answers and its plain requests are that name's requests (the
day's engine counts), and over the names the answer engines' requests; per
name, slow <= timed <= its requests.

The second count is audit_ai_status.py (audit_more.RECOUNTS), from the raw
lines with its own reading of the path and the status.
"""
from __future__ import annotations

import string
from collections import Counter

from .classify import Group
from .crawl_health import SLOW_MS
from .not_pages import RULES

KEEP = 1000
OTHER = "(all others)"
PLAIN = ("200", "304")
COPY_ENDS = tuple(RULES["markdown"][1]["ends"])
ASCII_LOWER = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)


def is_copy(path: str) -> bool:
    """A Markdown copy of a page: the path, trailing slashes aside, ends with
    one of COPY_ENDS (ASCII letters in any case)."""
    return (path or "").rstrip("/").translate(ASCII_LOWER).endswith(COPY_ENDS)


class Collector:
    """Fed every counted hit of the whole site (extras.Extras.add)."""

    def __init__(self) -> None:
        self.answers: dict[str, dict[str, Counter]] = {}
        self.slow: dict[str, Counter] = {}
        self.plain: Counter = Counter()
        self.timed: Counter = Counter()

    def add(self, hit, verdict) -> None:
        if verdict.group is not Group.ANSWER_ENGINE or not verdict.engine or not verdict.tier:
            return
        name, path, status = verdict.engine, hit.path[:200], hit.status
        if status in PLAIN and not is_copy(path):
            self.plain[name] += 1
        else:
            self.answers.setdefault(path, {}).setdefault(name, Counter())[status] += 1
        if hit.request_time is not None:
            self.timed[name] += 1
            if int(round(hit.request_time * 1000)) >= SLOW_MS:
                self.slow.setdefault(path, Counter())[name] += 1

    def finish(self) -> dict:
        answers, a_fold = _keep(self.answers, lambda per: sum(sum(c.values()) for c in per.values()),
                                _fold_answers)
        slow, s_fold = _keep(self.slow, lambda per: sum(per.values()), _fold_slow)
        return {"slow_ms": SLOW_MS, "keep": KEEP,
                "answers": {p: {n: dict(sorted(c.items())) for n, c in sorted(per.items())}
                            for p, per in answers.items()},
                "slow": {p: dict(sorted(per.items())) for p, per in slow.items()},
                "plain": dict(sorted(self.plain.items())),
                "timed": dict(sorted(self.timed.items())),
                "folded": {"answers": a_fold, "slow": s_fold}}


def _fold_answers(rows) -> dict:
    out: dict[str, Counter] = {}
    for per in rows:
        for name, c in per.items():
            out.setdefault(name, Counter()).update(c)
    return out


def _fold_slow(rows) -> Counter:
    out: Counter = Counter()
    for per in rows:
        out.update(per)
    return out


def _keep(paths: dict, size, fold) -> tuple[dict, int]:
    """The KEEP paths with most requests (ties by path), sorted by path, and
    the rest folded into OTHER; with how many paths were folded."""
    ranked = sorted(paths, key=lambda p: (-size(paths[p]), p))
    kept = {p: paths[p] for p in sorted(ranked[:KEEP])}
    rest = ranked[KEEP:]
    if rest:
        kept[OTHER] = fold(paths[p] for p in rest)
    return kept, len(rest)


# ---------------------------------------------------- day_more registry

def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    got = getattr(extras, "ai_status", None)
    return None if got is None else got.finish()


def check(totals, blob, differs, problems) -> None:
    """Per name, its answers and plain requests are its requests; over the
    names, the answer engines' requests; slow within timed within requests;
    a fold only with folded paths."""
    from .verify import Problem
    stats = totals.groups.get(Group.ANSWER_ENGINE)
    engines = stats.engines if stats else Counter()
    per: Counter = Counter()
    for got in (blob.get("answers") or {}).values():
        for name, c in got.items():
            per[name] += sum(int(v) for v in c.values())
    for name, n in (blob.get("plain") or {}).items():
        per[name] += int(n)
    differs("ai_status: AI requests by address and answer", sum(per.values()),
            stats.hits if stats else 0, "AI requests")
    for name in sorted(per):
        differs(f"ai_status: {name}'s requests by answer", per[name], int(engines.get(name, 0)),
                f"{name}'s requests")
    slow: Counter = Counter()
    for got in (blob.get("slow") or {}).values():
        slow.update({k: int(v) for k, v in got.items()})
    timed = {k: int(v) for k, v in (blob.get("timed") or {}).items()}
    for name in sorted(set(slow) | set(timed)):
        if slow[name] > timed.get(name, 0) or timed.get(name, 0) > per[name]:
            problems.append(Problem("ai_status", f"{name}: {slow[name]:,} slow, "
                                    f"{timed.get(name, 0):,} timed, {per[name]:,} requests"))
    folded = blob.get("folded") or {}
    for part in ("answers", "slow"):
        if (OTHER in (blob.get(part) or {})) != (int(folded.get(part) or 0) > 0):
            problems.append(Problem("ai_status", f"{part}: a fold without folded paths, or "
                                    "folded paths without a fold"))
