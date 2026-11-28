"""RiverBot, River's AI training crawler (SKALD-50, 2026-11-26).

It was noticed on 2026-11-23 as `RiverBot/1.0 (+https://river.ai/bot)`
and had been counted under "Other bots and scanners": no name list held it. River
publishes its addresses (river.ai/riverbot.json). Pinned here: the name is an AI
training crawler on both roads, it is checked against River's list (a fake is
"claims to be RiverBot"), its list's addresses are RiverBot's alone (rule 5b), and
it is in the AI crawler controls.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import alerts_ai, audit, bot_policy, bot_verify  # noqa: E402
from skald.classify import AI_TRAINING, OTHER_BOT, Classifier, Group, Tier  # noqa: E402
from skald.parse import Hit  # noqa: E402

from support import CHROME, Sandbox, line  # noqa: E402
from test_release2 import ranges  # noqa: E402

UTC = timezone.utc
NOON = datetime(2026, 10, 5, 12, tzinfo=UTC)
DAY = date(2026, 10, 5)
RIVERBOT = "RiverBot/1.0 (+https://river.ai/bot)"   # the agent seen on 2026-11-23
RIVER = "198.51.100.70"          # inside the test river list (198.51.100.64/28)
FAKE = "203.0.113.77"            # outside every list


def hit(url="/", agent=RIVERBOT, address=RIVER) -> Hit:
    return Hit(NOON, address, "example.com", "GET", url, "200", "", agent)


def river_list(folder: Path, fetched=None) -> None:
    ranges(folder, fetched, river=["198.51.100.64/28"])


class Names(unittest.TestCase):

    def test_it_is_an_ai_training_crawler_owned_by_river(self):
        self.assertEqual(AI_TRAINING.search(RIVERBOT).group(0), "RiverBot")
        crawler = bot_policy.match(RIVERBOT)
        self.assertEqual((crawler.name, crawler.owner, crawler.tier),
                         ("RiverBot", "River", "training"))

    def test_checked_against_rivers_published_list(self):
        self.assertEqual(bot_verify.vendor_of("RiverBot"), "river")
        self.assertEqual(bot_verify.LISTS["river"], "https://river.ai/riverbot.json")
        self.assertEqual(bot_verify.VENDORS["river"], (("river",), ()))
        self.assertEqual(bot_verify.method_of("river"), "ranges")
        self.assertEqual(bot_verify.CRAWLER_ADDRESSES["river"], "RiverBot")

    def test_every_vendor_has_an_owner_name_for_the_ai_alerts(self):
        self.assertEqual(alerts_ai.owner("RiverBot"), "River")
        self.assertLessEqual(set(bot_verify.VENDORS), set(alerts_ai.VENDORS))

    def test_rivers_list_format_is_read(self):
        raw = (b'{"creationTime": "2026-10-28T00:29:39", "prefixes": '
               b'[{"ipv4Prefix": "198.51.100.64/32"}, {"ipv4Prefix": "198.51.100.65/32"}]}')
        self.assertEqual(bot_verify.parse_list(raw), ["198.51.100.64/32", "198.51.100.65/32"])

    def test_without_the_name_it_was_only_an_other_bot(self):
        """What happened before: the agent matched only the generic bot words."""
        self.assertTrue(OTHER_BOT.search(RIVERBOT))


class Classified(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def classifier(self) -> Classifier:
        c = Classifier()
        c.verifier = bot_verify.Verifier(self.dir)
        return c

    def test_without_a_list_it_is_named_and_unverified(self):
        v = Classifier()(hit())
        self.assertEqual((v.group, v.tier, v.engine), (Group.ANSWER_ENGINE, Tier.TRAINING,
                                                       "RiverBot"))
        v = self.classifier()(hit())
        self.assertEqual((v.group, v.engine, v.verified),
                         (Group.ANSWER_ENGINE, "RiverBot", "unverified"))

    def test_with_the_list_the_real_one_counts_and_a_fake_is_a_bot_that_lied(self):
        river_list(self.dir)
        c = self.classifier()
        real = c(hit("/install/"))
        self.assertEqual((real.group, real.tier, real.engine, real.verified),
                         (Group.ANSWER_ENGINE, Tier.TRAINING, "RiverBot", "verified"))
        fake = c(hit("/install/", address=FAKE))
        self.assertEqual((fake.group, fake.engine, fake.claim),
                         (Group.BOTS, "claims to be RiverBot", "RiverBot"))

    def test_a_stale_list_says_nothing(self):
        river_list(self.dir, datetime.now(UTC) - timedelta(days=30))
        v = self.classifier()(hit(address=FAKE))
        self.assertEqual((v.group, v.engine, v.verified),
                         (Group.ANSWER_ENGINE, "RiverBot", "unverified"))

    def test_a_browser_agent_from_rivers_list_is_riverbot(self):
        """Rule 5b: every address on River's list is RiverBot's."""
        river_list(self.dir)
        c = self.classifier()
        self.assertEqual(c.verifier.crawler_at(RIVER), "RiverBot")
        self.assertEqual(c.verifier.crawler_at(FAKE), "")
        v = c(hit(agent=CHROME))
        self.assertEqual((v.group, v.tier, v.engine, v.verified),
                         (Group.ANSWER_ENGINE, Tier.TRAINING, "RiverBot", "verified"))
        self.assertEqual(c(hit(agent=CHROME, address=FAKE)).group, Group.PEOPLE)

    def test_the_second_road_reads_the_same_name(self):
        self.assertTrue(audit.AI_TRAINING.search(RIVERBOT))


class DayBothRoads(unittest.TestCase):
    """The visit of 2026-11-23 (robots.txt, /, /install/) plus a fake, collected
    and audited, with River's list and without."""

    def day(self, with_list: bool) -> tuple[dict, dict]:
        box = Sandbox()
        self.addCleanup(box.close)
        if with_list:
            folder = box.root / "ranges"
            river_list(folder)
            ranges(folder, hosting=[])
            box.config.write_text(box.config.read_text() + f"bots:\n  ranges_dir: {folder}\n")
        t = datetime(2026, 10, 5, 8, 27, tzinfo=UTC)
        box.log([
            line(t, "203.0.113.20", "/", CHROME),
            line(t + timedelta(seconds=1), RIVER, "/robots.txt", RIVERBOT),
            line(t + timedelta(seconds=3), RIVER, "/", RIVERBOT),
            line(t + timedelta(seconds=5), RIVER, "/install/", RIVERBOT),
            line(t + timedelta(seconds=9), FAKE, "/pricing/", RIVERBOT),
            # A browser agent from River's address: RiverBot with the list (rule 5b).
            line(t + timedelta(seconds=11), RIVER, "/features/", CHROME),
        ])
        code, out, err = box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)
        code, out, err = box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        with sqlite3.connect(box.db) as db:
            groups = dict(db.execute("SELECT grp, hits FROM groups WHERE day = ?",
                                     (DAY.isoformat(),)).fetchall())
            training = dict(db.execute("SELECT name, n FROM counts WHERE day = ? AND "
                                       "kind = 'engine_training'", (DAY.isoformat(),)).fetchall())
        return groups, training

    def test_with_the_list(self):
        groups, training = self.day(True)
        # River's three requests and the browser agent from its address are an AI
        # crawler (rule 5b, on both roads); the fake one is a bot.
        self.assertEqual((groups.get("answer_engines"), groups.get("bots")), (4, 1))
        self.assertEqual(training, {"RiverBot": 4})
        self.assertEqual(groups.get("people"), 1)

    def test_without_the_list(self):
        groups, training = self.day(False)
        # No list: every RiverBot line is named, unverified; the browser is a person.
        self.assertEqual(groups.get("answer_engines"), 4)
        self.assertNotIn("bots", groups)
        self.assertEqual(training, {"RiverBot": 4})
        self.assertEqual(groups.get("people"), 2)


if __name__ == "__main__":
    unittest.main()
