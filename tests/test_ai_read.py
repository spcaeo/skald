"""What the AI read before it sent this visitor (ai_read.py) and its second
count (audit_ai_likely.py).

What is pinned:
- a cited visit lists the pages its own assistant's user fetcher fetched in
  the window before its first request, nearest first; the landing page among
  them counts as "same page";
- window edges: the same minute and exactly the window before are in, one
  minute more and any fetch after the visit are out;
- training crawlers (GPTBot) and another assistant's fetches are never listed;
- a citation from an assistant with no user fetcher is left out, not 0;
- a likely visit lists the fetches of the assistants that made it likely;
- at most 10 paths a visit, the rest counted in `more`;
- every sum is checked and a planted error caught; the audit rebuilds the
  blob from the raw lines and a tampered one fails it;
- visits.json and ai_activity.json carry it.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, GPTBOT, Sandbox, line, totals_for  # noqa: E402

from skald import extras  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
PERPLEXITY = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
              "Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)")
CLAUDE = "Claude-User/1.0 (+Claude-User@anthropic.com)"
BOT = "198.51.100.40"


def at(hour: int, minute: int) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=UTC)


def synthetic() -> list[str]:
    return [
        # ChatGPT: two pages before a visit from a ChatGPT citation at 10:05.
        line(at(10, 0), BOT, "/pricing/", ASKED),
        line(at(10, 1), BOT, "/docs", ASKED),
        line(at(10, 2), "198.51.100.50", "/blog", GPTBOT),             # training: never
        line(at(10, 3), "198.51.100.41", "/about", PERPLEXITY),        # another assistant
        line(at(10, 5), "203.0.113.10", "/pricing/", referrer="https://chatgpt.com/"),
        line(at(10, 6), BOT, "/later", ASKED),                         # after the visit
        # Perplexity: window edges for a cited visit at 12:30 landing on /faq.
        line(at(12, 14), "198.51.100.41", "/too-early", PERPLEXITY),   # 16 min: out
        line(at(12, 15), "198.51.100.41", "/edge", PERPLEXITY),        # 15 min: in
        line(at(12, 30), "198.51.100.41", "/same-minute", PERPLEXITY),  # 0 min: in
        line(at(12, 30), "203.0.113.11", "/faq", referrer="https://www.perplexity.ai/search"),
        # Claude, by a utm tag: twelve pages, so the list is cut at ten.
        *[line(at(14, 0), "198.51.100.42", f"/p{i:02d}", CLAUDE) for i in range(12)],
        line(at(14, 5), "203.0.113.12", "/p03?utm_source=claude"),
        # A citation from an assistant with no user fetcher: left out.
        line(at(15, 0), "203.0.113.13", "/pricing/", referrer="https://you.com/"),
        # A likely visit: direct, on a page ChatGPT fetched 2 minutes before.
        line(at(16, 0), BOT, "/guide", ASKED),
        line(at(16, 1), BOT, "/setup", ASKED),
        line(at(16, 2), "203.0.113.14", "/guide"),
    ]


WANT = {"window_minutes": 15, "cited": 3, "likely": 1, "marked": 4, "listed": 16, "beyond": 2,
        "by_assistant": {
            "chatgpt.com": {"cited": 1, "fetched": 1, "same_page": 1, "likely": 1},
            "claude.ai": {"cited": 1, "fetched": 1, "same_page": 1, "likely": 0},
            "perplexity.ai": {"cited": 1, "fetched": 1, "same_page": 0, "likely": 0}}}


def reads(totals) -> dict:
    return {j["start"][11:16]: j.get("ai_read") for j in totals.journeys}


class TestTheDay(unittest.TestCase):

    def setUp(self):
        self.totals = totals_for(synthetic())

    def test_the_day_figure_and_its_sums(self):
        self.assertEqual(self.totals.extras["ai_read"], WANT)
        self.assertEqual(extras.check(self.totals), [])

    def test_a_cited_visit_lists_what_its_assistant_fetched_before(self):
        got = reads(self.totals)["10:05"]
        self.assertEqual((got["how"], got["name"], got["window_minutes"]),
                         ("cited", "chatgpt.com", 15))
        # Nearest first; GPTBot's /blog, Perplexity's /about and the fetch after are not there.
        self.assertEqual(got["paths"], [["/docs", "chatgpt.com", 4],
                                        ["/pricing/", "chatgpt.com", 5]])
        self.assertEqual(got["more"], 0)

    def test_window_edges(self):
        got = reads(self.totals)["12:30"]
        self.assertEqual(got["paths"], [["/same-minute", "perplexity.ai", 0],
                                        ["/edge", "perplexity.ai", 15]])

    def test_the_window_setting_is_honoured(self):
        from tempfile import TemporaryDirectory
        from skald import Classifier, read
        from skald.aggregate import summarise_views
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(synthetic()))
            totals = summarise_views(read([path]), Classifier([]), 30, top=50,
                                     hosts=["example.com"],
                                     options={"attribution": {"on": True, "window": 4}})[0]
        got = reads(totals)
        self.assertEqual(got["10:05"]["paths"], [["/docs", "chatgpt.com", 4]])
        self.assertEqual(got["12:30"]["paths"], [["/same-minute", "perplexity.ai", 0]])
        self.assertEqual(totals.extras["ai_read"]["by_assistant"]["chatgpt.com"]["same_page"], 0)
        self.assertEqual(extras.check(totals), [])

    def test_at_most_ten_paths_a_visit(self):
        got = reads(self.totals)["14:05"]
        self.assertEqual(len(got["paths"]), 10)
        self.assertEqual(got["more"], 2)
        self.assertEqual(got["paths"][0], ["/p00", "claude.ai", 5])

    def test_no_fetcher_no_list_and_a_likely_visit(self):
        got = reads(self.totals)
        self.assertIsNone(got["15:00"])
        self.assertEqual(got["16:02"]["how"], "likely")
        self.assertEqual(got["16:02"]["paths"], [["/setup", "chatgpt.com", 1],
                                                 ["/guide", "chatgpt.com", 2]])

    def test_planted_errors_are_caught(self):
        for change, what in (
                (lambda b: b.update(cited=4), "ai_read: cited visits by assistant does not sum"),
                (lambda b: b.update(marked=5), "ai_read: visits with pages read before does not sum"),
                (lambda b: b["by_assistant"]["claude.ai"].update(same_page=2), "ai_read: claude.ai"),
                (lambda b: b.update(listed=17), "ai_read: paths listed does not sum")):
            with self.subTest(what=what):
                totals = totals_for(synthetic())
                change(totals.extras["ai_read"])
                self.assertIn(what, [p.what for p in extras.check(totals)])

    def test_off_means_not_recorded(self):
        from tempfile import TemporaryDirectory
        from skald import Classifier, read
        from skald.aggregate import summarise_views
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(synthetic()))
            totals = summarise_views(read([path]), Classifier([]), 30, top=50,
                                     hosts=["example.com"],
                                     options={"attribution": {"on": False, "window": 15}})[0]
        self.assertNotIn("ai_read", totals.extras)
        self.assertFalse(any(j.get("ai_read") for j in totals.journeys))


class TestTheAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic())

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]

    def test_main_and_audit_agree_and_a_tampered_figure_fails(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        got = self.stored()["ai_read"]
        self.assertEqual(got, WANT)
        got["by_assistant"]["perplexity.ai"]["same_page"] = 1
        got["beyond"] = 0
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'ai_read'", (json.dumps(got),))
        db.close()
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_read: same_page for perplexity.ai: history has 1, the recount finds 0",
                      err)
        self.assertIn("ai_read: beyond: history has 0, the recount finds 2", err)

    def test_the_data_files_carry_it(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        self.assertEqual(self.box.run("--today", TODAY, "dashboard")[0], 0)
        data = self.box.root / "www" / "example.com" / "data"
        day = next(d for d in json.loads((data / "ai_activity.json").read_text())["days"]
                   if d["day"] == DAY.isoformat())
        self.assertEqual(day["ai_read"], WANT)
        visits = json.loads((data / "visits.json").read_text())["journeys"]
        listed = {j["start"][11:16]: len(j["ai_read"]["paths"]) for j in visits if j.get("ai_read")}
        self.assertEqual(listed, {"10:05": 2, "12:30": 2, "14:05": 10, "16:02": 2})


if __name__ == "__main__":
    unittest.main()
