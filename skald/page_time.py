"""Time on page from the server log, per page (#46): the page story's
`time_on_page`, per day and over its whole days
(docs/DATA-CONTRACT-PAGE-LIFECYCLE.md).

Read from the day's `pages` blob (extras.py), which visits._page_figures
fills from each people visit's trail - every page it loaded and every
in-app move seen from a later request's referrer, each with the time it
was seen:

  time    {seconds bucket: n}: for each trail entry that has a next one in
          the same visit, the seconds from it to the next, bucketed by
          visits.seconds_bucket (to the second under a minute, 10 s under
          ten minutes, the minute under an hour, then 10 minutes)
  exits   the visits whose last trail entry was this page: nothing comes
          after them, so they have no time ("not measured, last page of the
          visit")

So `measured` + `not_measured_last_page` is every time the page was seen in
a visit. The median is withheld (null) under MIN_MEASURED measured views;
an old blob without the times is not recorded at all (None). The audit
recounts each day's times per page from the raw log
(audit_visits.compare_pages) and this figure from its own seconds.
"""
from __future__ import annotations

MIN_MEASURED = 5          # no median over fewer measured views than this


def median_bucket(hist: dict) -> int | None:
    """The middle value of a {bucket: n} histogram (the lower middle of an
    even count), None when empty."""
    total = sum(int(n) for n in hist.values())
    if not total:
        return None
    middle = (total - 1) // 2
    for value, n in sorted((int(k), int(n)) for k, n in hist.items()):
        if middle < n:
            return value
        middle -= n
    return None


def merge(rows: list[dict]) -> tuple[dict, int] | None:
    """({bucket: n}, last-page views) of page-blob rows (both spellings of a
    path, or several days); no row at all is a page nobody visited (zero);
    None when there are rows and none recorded the times."""
    if rows and not any(isinstance(r, dict) and isinstance(r.get("time"), dict)
                        for r in rows):
        return None
    hist: dict[str, int] = {}
    last = 0
    for r in rows:
        if not isinstance(r, dict) or not isinstance(r.get("time"), dict):
            continue
        for k, n in r["time"].items():
            hist[str(k)] = hist.get(str(k), 0) + int(n)
        last += int(r.get("exits", 0))
    return hist, last


def figure(rows: list[dict]) -> dict | None:
    """{"median_s", "measured", "not_measured_last_page"} of page-blob rows,
    the median null under MIN_MEASURED; None when the times were not recorded.
    The caller passes the rows of stored days only: a day with no figures
    is null in the story, never this."""
    got = merge(rows)
    if got is None:
        return None
    hist, last = got
    measured = sum(hist.values())
    return {"median_s": median_bucket(hist) if measured >= MIN_MEASURED else None,
            "measured": measured, "not_measured_last_page": last}
