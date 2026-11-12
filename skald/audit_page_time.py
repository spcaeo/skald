"""The audit's own count of time on page (#46): part of audit.py's second road.

audit_visits.VisitRecount walks each people visit again from the raw lines
(its own trail rule: pages loaded and in-app moves seen from a later
request's referrer, nothing from visits.py) and keeps, per page, the whole
seconds from each trail entry to the next (`page_seconds`). Here they are
bucketed by the audit's own rule (audit_visits._bucket, SOP.md "Visits")
and compared with the day's stored `pages` blob:

  every bucket     the stored `time` {bucket: views} of every page
  the figure       what the page story shows (page_time.figure on the stored
                   row): views measured, views not measured (the visit's last
                   page: the recount's exits), and the median, taken here as
                   the middle of the sorted bucketed seconds, withheld under
                   page_time.MIN_MEASURED (the one value shared)

A blob from before the times were kept has none: nothing is compared.
"""
from __future__ import annotations

from collections import Counter

from .audit_visits import _bucket
from .page_time import MIN_MEASURED, figure


def compare(pages: dict | None, got: dict, same) -> None:
    pages = pages or {}
    if not any(isinstance(r, dict) and "time" in r for r in pages.values()):
        return
    seconds = got.get("page_seconds") or {}
    exits = got.get("exits") or Counter()
    for path in sorted(set(pages) | set(seconds) | set(exits)):
        _page(path, pages.get(path) or {}, seconds.get(path) or [], exits.get(path, 0), same)


def _page(path: str, row: dict, seconds: list[int], last: int, same) -> None:
    mine = Counter(str(_bucket(s)) for s in seconds)
    kept = Counter({str(k): int(n) for k, n in (row.get("time") or {}).items()})
    for b in sorted(set(mine) | set(kept), key=int):
        same(f"page {path}: time on page, views of {b} s", kept.get(b, 0), mine.get(b, 0))
    shown = figure([row]) or {}
    ordered = sorted(_bucket(s) for s in seconds)
    middle = ordered[(len(ordered) - 1) // 2] if len(ordered) >= MIN_MEASURED else None
    same(f"page {path}: time on page, views measured", shown.get("measured", 0), len(ordered))
    same(f"page {path}: time on page, not measured (last page of the visit)",
         shown.get("not_measured_last_page", 0), last)
    same(f"page {path}: time on page, median seconds (-1: withheld)",
         -1 if shown.get("median_s") is None else shown["median_s"],
         -1 if middle is None else middle)
