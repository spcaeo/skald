"""The mails' Top pages are the period's true reads per page (SKALD-12, GitHub #70).

History keeps each day's top 50 pages in `counts`. The weekly mail summed
those, so a page read once on several busy days, never in a day's top 50,
was missing from the week or short. The skaldanalytics.com weekly mail for
9-15 Nov 2026 showed /self-host/render/ with 6 reads; the true count was 8.
What is pinned:

  * the weekly mail (HTML and text part) lists a page by every read, from
    each day's full page counts (day_extras page_counts, the list Compare in
    the dashboard and `skald compare` read; the dashboard's other page lists
    are summed top 50s);
  * those counts add up to the people's page views, and page_counts holds
    the same views as the `pages` blob that audit_extras recounts per page;
  * a day without page counts (collected by older code) keeps the summed top
    lists, and the card says they may miss pages.

Addresses are RFC 5737, hosts example.com.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import mailer  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.store import History  # noqa: E402

from support import SECRETS, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402
from test_mail_html import BRAND  # noqa: E402

LAST = date(2026, 10, 5)
NOW = datetime(2026, 10, 6, 9, tzinfo=UTC)
TAIL = "/tail/"
BUSY = (date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3))   # /tail/ not in the top 50
QUIET = date(2026, 10, 4)                                           # /tail/ in the top 50


def busy_lines(day: date) -> list[str]:
    """55 pages read twice each, and /tail/ once: /tail/ is not in the day's top 50."""
    start = datetime(day.year, day.month, day.day, 8, tzinfo=UTC)
    out = [line(start + timedelta(minutes=3 * (k * 2 + r)), f"192.0.2.{(k * 2 + r) % 40 + 10}",
                f"/fill-{day.day}-{k:02d}/") for k in range(55) for r in range(2)]
    return out + [line(start + timedelta(hours=7), "192.0.2.99", TAIL)]


def tail_line(day: date) -> str:
    return line(datetime(day.year, day.month, day.day, 16, tzinfo=UTC), "192.0.2.98", TAIL)


class Week(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.history = History(self.box.db)
        self.patch = mock.patch("skald.brand.load", return_value=BRAND)
        self.patch.start()
        for i in range(14):
            day = LAST - timedelta(days=i)
            lines = day_lines(day, 3)
            if day in BUSY:
                lines += busy_lines(day)
            elif day == QUIET:
                lines.append(tail_line(day))
            self.history.record("example.com", day, totals_for(lines), "UTC", [])

    def tearDown(self):
        self.patch.stop()
        self.history.close()
        self.box.close()

    def build(self, kind="weekly"):
        with mock.patch.dict(os.environ, SECRETS):
            msg = mailer.build(kind, load_config(self.box.config), self.history, UTC, NOW)
        html = msg.get_body(("html",)).get_content()
        text = msg.get_body(("plain",)).get_content()
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)), text

    def top_pages(self, flat: str) -> str:
        return flat.split("Top pages", 1)[1].split("Countries", 1)[0]

    def test_the_fixture_drops_the_tail_from_three_days_top_50(self):
        week = self.history.period("example.com", LAST - timedelta(days=6), LAST)
        self.assertEqual(week.totals.groups[Group.PEOPLE].pages[TAIL], 1)

    def test_the_weekly_mail_counts_every_read(self):
        flat, text = self.build()
        card = self.top_pages(flat)
        self.assertRegex(card, r"/ 14 .*/guides/alpha 7 .*/tail/ 4 ")
        self.assertNotIn("may be missing", card)
        self.assertRegex(text, r"\n +4  /tail/\n")

    def test_the_whole_counts_add_up_to_pages_read(self):
        week = self.history.period("example.com", LAST - timedelta(days=6), LAST)
        self.assertTrue(mailer.whole_pages(self.history, "example.com", week))
        people = week.totals.groups[Group.PEOPLE]
        self.assertEqual(sum(people.pages.values()), people.views)
        self.assertEqual(people.pages[TAIL], 4)

    def test_page_counts_hold_the_audited_page_views(self):
        """audit_extras recounts the `pages` blob's views per page; page_counts
        must hold the same views, so the mail's list rests on an audited figure."""
        for day in (*BUSY, QUIET):
            rows = dict(self.history.db.execute(
                "SELECT kind, data FROM day_extras WHERE site = ? AND day = ? "
                "AND kind IN ('pages', 'page_counts')", ("example.com", day.isoformat())))
            pages, counts = json.loads(rows["pages"]), json.loads(rows["page_counts"])
            self.assertEqual({p: v["views"] for p, v in pages.items() if v["views"]},
                             {p: v[0] for p, v in counts.items() if v[0]})

    def test_a_day_without_page_counts_keeps_the_summed_tops_and_says_so(self):
        self.history.db.execute("DELETE FROM day_extras WHERE site = ? AND day = ? AND "
                                "kind = 'page_counts'", ("example.com", BUSY[0].isoformat()))
        self.history.db.commit()
        flat, text = self.build()
        card = self.top_pages(flat)
        self.assertIn("may be missing", card)
        self.assertNotRegex(card, r"/tail/ 4 ")
        self.assertIn("may be missing", text)
        # Compare reads page_counts; the dashboard's other page lists are summed
        # top 50s too, so the note must not send the reader there (SKALD-12 review).
        self.assertIn("Compare in the dashboard counts every read", card)
        self.assertNotIn("dashboard has the whole list", card)

    def test_the_daily_mail_is_unchanged_for_one_day(self):
        flat, _ = self.build("daily")
        card = self.top_pages(flat)
        self.assertRegex(card, r"/ 2 .*/guides/alpha 1 ")
        self.assertNotIn("may be missing", card)


if __name__ == "__main__":
    unittest.main()
