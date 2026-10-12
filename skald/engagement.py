"""Engagement by source type and by device: day kind `engagement` (phase 4).

The site-wide visit figures (visits.VisitStats) split two ways: by the
source type of each visit (its first page, as the readers are labelled)
and by its device. Each row is counts only, so any range of days sums
them, and the page reads its rates from the sums:

    {"by_source": {source type: Row}, "by_device": {device: Row}}
    Row = {"visits": int,        people's visits (readers)
           "views": int,         pages they loaded (pages per visit = views / visits)
           "one_page": int,      visits that loaded one page
           "seconds": {bucket: visits}}   by length, visits.seconds_bucket
                                          (the median is read from it)

From the day's people visits (the journeys extras.finish is given). A day
with no people has two empty maps: zero visits counted, not "not
recorded". None when the visits were not counted at all.

Checked here (check): every map sums to the day's visits, pages loaded and
one-page visits, each row's lengths to its visits, and the rows equal the
visits by source and device. Counted again by audit_engagement.py, which
labels and buckets the raw lines with the audit's own code.
"""
from __future__ import annotations

from collections import Counter

from .visits import seconds_bucket

DIMS = (("by_source", "source"), ("by_device", "device"))


def _row() -> dict:
    return {"visits": 0, "views": 0, "one_page": 0, "seconds": {}}


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    """The day's rows (day_more.py), or None when visits were not counted."""
    if journeys is None:
        return None
    out: dict = {name: {} for name, _ in DIMS}
    for j in journeys:
        pages = int(j.get("pages") or 0)
        bucket = str(seconds_bucket(int(j.get("seconds") or 0)))
        for name, label in DIMS:
            row = out[name].setdefault(str(j.get(label) or "Unknown"), _row())
            row["visits"] += 1
            row["views"] += pages
            row["one_page"] += 1 if pages == 1 else 0
            row["seconds"][bucket] = row["seconds"].get(bucket, 0) + 1
    return out


def check(totals, blob: dict, differs, problems: list) -> None:
    """Every sum DATA-CONTRACT.md promises for the blob (day_more.py)."""
    from .classify import Group
    from .verify import Problem
    stats = getattr(totals, "visits", None)
    people = (getattr(totals, "groups", None) or {}).get(Group.PEOPLE)
    if stats is not None:
        visits = stats.visits
    else:
        visits = people.readers if people is not None and people.readers is not None else 0
    views = people.views if people is not None else 0
    for name, label in DIMS:
        rows = blob.get(name) or {}
        what = f"engagement by {label}"
        differs(f"{what}: visits", sum(r["visits"] for r in rows.values()), visits, "visits")
        differs(f"{what}: pages loaded", sum(r["views"] for r in rows.values()), views,
                "page views by people")
        for key, r in sorted(rows.items()):
            differs(f"{what}: {key}: visits by length", sum(r["seconds"].values()),
                    r["visits"], "visits")
            if not r["one_page"] <= r["visits"] <= r["views"]:
                problems.append(Problem(f"{what}: {key}",
                                        f"{r['one_page']:,} one-page visits, {r['visits']:,} "
                                        f"visits and {r['views']:,} pages do not fit together"))
        if stats is None:
            continue
        differs(f"{what}: one-page visits", sum(r["one_page"] for r in rows.values()),
                stats.one_page(), "one-page visits")
        lengths: Counter = Counter()
        for r in rows.values():
            lengths.update({k: int(v) for k, v in r["seconds"].items()})
        if +lengths != +Counter(stats.seconds):
            problems.append(Problem(f"{what}: visits by length",
                                    "do not match the day's visits by length"))
        mine = Counter({k: r["visits"] for k, r in rows.items()})
        theirs = getattr(stats, label, None)
        if theirs and +mine != +Counter(theirs):
            problems.append(Problem(f"{what}: visits do not match visits by {label}",
                                    f"{sum(mine.values()):,} against "
                                    f"{sum(theirs.values()):,}, or a label differs"))
