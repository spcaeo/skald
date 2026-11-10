"""Crawlers in a browser's clothes (#4, CLASSIFICATION.md rules 5b and 9c).

Found on taskrhino's 31 Oct: 99 pages read by a Mac Chrome from addresses on
OpenAI's published OAI-SearchBot list, and 170 pages read 2 to 7 seconds
apart by a Linux Chrome from a cloud network. Both were counted as people,
and their page scripts sent about 400 scroll events.

Pinned here (the owner's choices, 2026-11-09):
  * rule 5b: a browser agent from a crawler-only list is that crawler,
    verified; a user-triggered list (a person asked) stays people, and a
    non-browser agent from the same addresses stays a bot;
  * rule 9c: a visit from a hosting network with 20 page views or more, at
    10 seconds a page or faster on average, is "too fast to be a person";
    19 pages, a slower pace, or the same pace from an ordinary network stay
    people, and `site.cloud_fast_pages: 0` turns it off;
  * both rules are recounted by the audit's own road ("all match"), and a
    nudged figure is caught.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import bot_verify  # noqa: E402
from skald.classify import TOO_FAST, Classifier, Group, Tier  # noqa: E402
from skald.parse import Hit  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import CHROME, UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 10, 31)
TODAY = "2026-11-01"
NOON = datetime(2026, 10, 31, 12, tzinfo=UTC)
MAC = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
LINUX = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
         "Chrome/131.0.0.0 Safari/537.36")
SEARCHBOT = "198.51.100.20"      # on the OAI-SearchBot list
ASKED = "198.51.100.40"          # on the ChatGPT-User list: a person asked
GOOGLE = "198.51.100.70"         # on Google's common crawlers list
CLOUD = "192.0.2.200"            # a hosting network
HOME = "203.0.113.50"            # an ordinary network


def ranges(folder: Path, **named) -> None:
    """Write stored lists as bot_verify keeps them, fetched now."""
    folder.mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for name, nets in named.items():
        (folder / f"{name.replace('_', '-')}.json").write_text(json.dumps(
            {"source": "test", "fetched": fetched, "networks": nets, "error": None}))


def lists(folder: Path) -> None:
    ranges(folder, openai_gptbot=["198.51.100.0/28"], openai_searchbot=["198.51.100.16/28"],
           openai_chatgpt_user=["198.51.100.32/28"], openai_adsbot=["198.51.100.48/28"],
           google_common=["198.51.100.64/28"], hosting=["192.0.2.128/25"])


def hit(address, agent=CHROME, url="/") -> Hit:
    return Hit(NOON, address, "example.com", "GET", url, "200", "", agent)


def reading(address, start, gaps, agent=LINUX):
    """A page view after each gap (seconds), the first page's stylesheet
    with it, so the visit rendered."""
    out, when = [], start
    for i, gap in enumerate(gaps):
        when += timedelta(seconds=gap)
        out.append(line(when, address, f"/p{i}/", agent))
        if i == 0:
            out.append(line(when, address, "/_next/static/css/app.css", agent,
                            "https://example.com/p0/"))
    return out


class RuleFiveB(unittest.TestCase):
    """A browser agent from a crawler's own published addresses."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ranges"
        lists(self.dir)
        self.c = Classifier.from_config({"bots": {"ranges_dir": str(self.dir)}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_browser_from_the_searchbot_list_is_oai_searchbot(self):
        v = self.c(hit(SEARCHBOT, MAC))
        self.assertEqual((v.group, v.tier, v.engine, v.verified),
                         (Group.ANSWER_ENGINE, Tier.TRAINING, "OAI-SearchBot", "verified"))

    def test_a_browser_from_googles_crawler_list_is_googlebot(self):
        v = self.c(hit(GOOGLE))
        self.assertEqual((v.group, v.engine, v.verified),
                         (Group.SEARCH_ENGINE, "Googlebot", "verified"))

    def test_a_person_behind_an_assistant_stays_a_person(self):
        self.assertEqual(self.c(hit(ASKED)).group, Group.PEOPLE)

    def test_an_ordinary_address_stays_a_person(self):
        self.assertEqual(self.c(hit(HOME)).group, Group.PEOPLE)

    def test_a_script_from_the_same_addresses_stays_a_bot(self):
        v = self.c(hit(SEARCHBOT, "python-requests/2.32"))
        self.assertEqual((v.group, v.engine), (Group.BOTS, ""))

    def test_without_lists_nothing_moves(self):
        self.assertEqual(Classifier()(hit(SEARCHBOT, MAC)).group, Group.PEOPLE)

    def test_only_crawler_lists_and_known_names(self):
        self.assertTrue(set(bot_verify.CRAWLER_ADDRESSES) <= set(bot_verify.LISTS))
        for left_out in ("google-user", "google-user-google", "openai-chatgpt-user",
                         "perplexity-user", "anthropic", "meta"):
            self.assertNotIn(left_out, bot_verify.CRAWLER_ADDRESSES)
        for name in bot_verify.CRAWLER_ADDRESSES.values():
            self.assertIsNotNone(bot_verify.vendor_of(name), name)


class RuleNineC(unittest.TestCase):
    """A fast reader from a hosting network."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ranges"
        lists(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def count(self, lines, **site):
        config = {"site": {"hosts": ["example.com"], **site},
                  "bots": {"ranges_dir": str(self.dir)}}
        path = Path(self.tmp.name) / "access.log"
        path.write_text("".join(lines))
        start, end = day_window(DAY, UTC)
        return analyse_window(config, start, end, paths=[path])

    def people_visits(self, totals) -> int:
        g = totals.groups.get(Group.PEOPLE)
        return g.visits if g else 0

    def test_the_live_case_moves_whole(self):
        gaps = [0] + [2, 7, 4, 5, 3, 6, 2, 7, 5, 4] * 17    # 171 pages, 2 to 7 s apart
        totals = self.count(reading(CLOUD, NOON, gaps))
        self.assertEqual(self.people_visits(totals), 0)
        self.assertEqual(totals.groups[Group.BOTS].agents.get(TOO_FAST), 172)

    def test_the_edge_and_what_stays(self):
        cases = {
            "20 pages at 10 s": (CLOUD, [0] + [10] * 19, 0),
            "19 pages at 1 s": (CLOUD, [0] + [1] * 18, 1),
            "20 pages, 11 s a page": (CLOUD, [0] + [11] * 19, 1),
            "same pace from home": (HOME, [0] + [5] * 30, 1),
        }
        for name, (address, gaps, visits) in cases.items():
            with self.subTest(name):
                self.assertEqual(self.people_visits(self.count(reading(address, NOON, gaps))),
                                 visits)

    def test_switched_off(self):
        lines = reading(CLOUD, NOON, [0] + [3] * 40)
        self.assertEqual(self.people_visits(self.count(lines, cloud_fast_pages=0)), 1)
        self.assertEqual(self.people_visits(self.count(lines, cloud_fast_seconds=2)), 1)


class BothRoads(unittest.TestCase):
    """collect, then the audit's own road."""

    def setUp(self):
        self.box = Sandbox()
        self.dir = self.box.root / "ranges"
        lists(self.dir)
        self.box.config.write_text(self.box.config.read_text()
                                   + f"bots:\n  ranges_dir: {self.dir}\n")
        self.box.log(
            reading(SEARCHBOT, NOON, [0, 3, 4, 2], MAC)                      # rule 5b
            + reading(GOOGLE, NOON + timedelta(minutes=5), [0, 2, 2])         # rule 5b
            + reading(CLOUD, NOON + timedelta(hours=1), [0] + [4] * 24)      # rule 9c
            + reading("192.0.2.201", NOON + timedelta(hours=2), [0, 40, 90])  # VPN reader
            + reading(HOME, NOON + timedelta(hours=3), [0] + [4] * 24))      # home reader

    def tearDown(self):
        self.box.close()

    def stored(self, kind: str) -> dict:
        with sqlite3.connect(self.box.db) as db:
            got = db.execute("SELECT data FROM day_extras WHERE site = 'example.com' AND "
                             "day = ? AND kind = ?", (DAY.isoformat(), kind)).fetchone()
        return json.loads(got[0])

    def collect(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)

    def test_collect_counts_and_the_audit_agrees(self):
        self.collect()
        bots = self.stored("bots")
        self.assertEqual(bots["verification"]["OAI-SearchBot"]["verified"], 5)
        self.assertEqual(bots["verification"]["Googlebot"]["verified"], 4)
        self.assertEqual(bots["too_fast"], {"requests": 26, "pages": 25, "readers": 1})
        self.assertEqual(bots["fake_browsers"]["hosting_network"]["addresses"], 1)
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_the_audit_catches_a_nudged_figure(self):
        self.collect()
        db = sqlite3.connect(str(self.box.db))
        with db:
            blob = self.stored("bots")
            blob["too_fast"]["pages"] -= 1
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'bots'", (json.dumps(blob),))
        db.close()
        code, _, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 1)
        self.assertIn("too fast to be a person: pages", err)


if __name__ == "__main__":
    unittest.main()
