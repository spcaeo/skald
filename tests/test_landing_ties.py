"""Visits by entry page and readers by landing page fold the same way.

Seen live on 2026-10-26: a day's snapshot was withheld with "visits by
entries do not match readers by landing" although both roads chose the same
first page for every visitor. More landing pages than the breakdown keeps
(25) had one reader each, and the fold kept the first ones it met: the
readers road meets a landing page when the page is read, the visits road
when the visit began (its first request, here an asset fetched minutes
before the page). One visitor in the tie was kept by one road and folded
into "(all others)" by the other.

What is pinned: dimensions.fold keeps, among labels with the same count,
the same ones whatever order they were counted in (the first by name), and
the shape above reconciles.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Classifier, check  # noqa: E402
from skald.aggregate import summarise  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.dimensions import OTHER, fold  # noqa: E402
from skald.parse import read  # noqa: E402

from support import UTC, line  # noqa: E402

T = datetime(2026, 10, 26, 10, 43, 50, tzinfo=UTC)
# Longer than the 70 characters a page is kept to: both roads cut it alike.
LONG = "/software-development/portfolio/dental-practice-management-system-case-study/"


def tie_day() -> list[str]:
    """Visitor A's visit opens with an asset at T and reads its one page
    ~6.5 minutes later; 26 other readers each read one other page in
    between. 27 landing pages, one reader each."""
    out = [line(T, "192.0.2.10", "/_next/static/chunks/main.js")]
    for i in range(26):
        out.append(line(T + timedelta(minutes=1, seconds=10 * i), f"203.0.113.{20 + i}",
                        f"/page-{i:02d}/"))
    out.append(line(T + timedelta(seconds=396), "192.0.2.10", LONG))
    return sorted(out)


def totals(lines: list[str], top: int = 20):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        return summarise(read([path]), Classifier([]), 30, top=top, hosts=["example.com"])


class TestLandingTies(unittest.TestCase):

    def test_a_tie_at_the_fold_reconciles(self):
        got = totals(tie_day())
        people = got.groups[Group.PEOPLE]
        self.assertEqual(people.readers, 27)
        self.assertEqual(got.visits.visits, 27)
        self.assertEqual(Counter(got.visits.entries), Counter(people.by["landing"]))
        self.assertEqual(people.by["landing"][OTHER], 3)
        self.assertEqual(check(got), [])

    def test_fold_keeps_the_same_labels_in_any_order(self):
        names = [f"/p{i:02d}/" for i in range(30)]
        forward = Counter({n: 1 for n in names})
        backward = Counter({n: 1 for n in reversed(names)})
        forward["/big/"] = backward["/big/"] = 5
        self.assertEqual(fold(forward, 25), fold(backward, 25))
        kept = fold(backward, 25)
        self.assertEqual(kept["/big/"], 5)
        self.assertEqual(kept[OTHER], 7)
        self.assertIn("/p00/", kept)
        self.assertNotIn("/p29/", kept)
        # Largest first, then by name: the order a list shows them in.
        self.assertEqual(list(kept)[:3], ["/big/", "/p00/", "/p01/"])

    def test_fold_still_keeps_the_sum(self):
        c = Counter({"b": 2, "a": 2, "c": 1, "d": 1})
        self.assertEqual(fold(c, 3), Counter({"a": 2, "b": 2, OTHER: 2}))
        self.assertEqual(sum(fold(c, 3).values()), sum(c.values()))
        self.assertEqual(fold(c, 4), c)


if __name__ == "__main__":
    unittest.main()
