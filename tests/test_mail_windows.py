""""What changed" says its window (SKALD-12, GitHub #70).

The daily mail shows the same insights as the weekly one: week-on-week lines
and ideas from the last 30 days. The idea lines did not say their window, so
in a mail about one Sunday "/beta/: 16 visits started here" read as that day.
What is pinned:

  * the "visits started here" and "404 from a link" ideas say "in the last
    30 days" (the AI-fetches idea already said "in 30 days");
  * a page where no visit went on says "none went on", not "almost none went
    on (0 more pages)";
  * the mail's What changed card and its text part say which window each
    kind of line covers: comparisons say theirs, while a spike, a drop or a
    "New" line is about the mail's last day, which the note names.
"""
from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import insights  # noqa: E402
from skald.mail_html import windows  # noqa: E402

ANCHOR = date(2026, 10, 5)
CFG = insights.settings({})


def source(pages: dict, not_found: list | None = None):
    """A Source with one verified day inside the 30-day window."""
    day = (ANCHOR - timedelta(days=3)).isoformat()
    return SimpleNamespace(states={day: {"state": "ok"}},
                           extras={day: {"pages": pages, "not_found": not_found or []}})


def titles(src) -> list[str]:
    return [i["title"] for i in insights.opportunities(src, ANCHOR, CFG)]


class IdeaWindows(unittest.TestCase):

    def test_none_went_on(self):
        got = titles(source({"/beta/": {"readers": 16, "entries": 16, "after_pages": 0}}))
        self.assertEqual(got, ["/beta/: 16 visits started here in the last 30 days, "
                               "and none went on"])

    def test_almost_none_went_on_names_the_pages(self):
        got = titles(source({"/beta/": {"readers": 16, "entries": 16, "after_pages": 2}}))
        self.assertEqual(got, ["/beta/: 16 visits started here in the last 30 days, "
                               "and almost none went on (2 more pages)"])

    def test_a_404_from_a_link_says_its_window(self):
        rows = [{"path": "/old/", "group": "people", "probe": False, "source": "news.example.org",
                 "n": 3}]
        got = titles(source({}, rows))
        self.assertEqual(got, ["/old/: 3 people reached this 404 from a link elsewhere "
                               "in the last 30 days - redirect it"])

    def test_the_note_says_each_kind_of_line_its_window(self):
        note = windows(date(2026, 11, 15))
        # The comparisons' own words (insights.compare, opportunities).
        self.assertIn("week on week, 30 days on the 30 before, or the last 30 days", note)
        # Spikes, drops and "New" lines count the mail's last day, named here.
        self.assertIn('a spike, a drop or a "New" line is about Sun 15 Nov alone', note)
        # The first note said no line was about one day alone: false for these.
        self.assertNotIn("not about one day alone", note)

    def test_the_card_names_the_mail_day_under_a_new_line(self):
        from skald import mail_html
        card = mail_html._insights([{"type": "new", "title": "New source: news.example.org "
                                     "(5 visitors)"}], ANCHOR)
        self.assertIn("New source: news.example.org (5 visitors)", card)
        self.assertIn("is about Mon 05 Oct alone", card)
        self.assertEqual(mail_html._insights([], ANCHOR), "")


if __name__ == "__main__":
    unittest.main()
