"""Copilot's new host, Meta AI, DeepSeek, Grok and OAI-AdsBot (2026-10-25).

The referrers and tags each assistant sends, the name a reader sees, the
second road's reading of the same lists, and rule 2b: a claimed crawler that
scans and is not proven its owner's stays in bots, with lists and without.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit, audit_funnels, audit_release2, bot_policy, bot_verify  # noqa: E402
from skald import visits  # noqa: E402
from skald.audit import Line  # noqa: E402
from skald.classify import (AI_TRAINING, AI_UTM, SCANNER, Classifier, Group,  # noqa: E402
                                   Tier, assistant_name, cited_by)
from skald.parse import Hit  # noqa: E402

from support import ASKED, CHROME, GOOGLEBOT, Sandbox, line  # noqa: E402
from test_release2 import openai_lists, ranges  # noqa: E402

UTC = timezone.utc
NOON = datetime(2026, 10, 5, 12, tzinfo=UTC)
DAY = date(2026, 10, 5)
ADSBOT = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-AdsBot/1.0; "
          "+https://openai.com/adsbot")
OPENAI_ADS = "198.51.100.50"     # inside the test adsbot list (198.51.100.48/28)
FAKE = "203.0.113.77"            # outside every list

# referrer -> the assistant it names
CITED = {
    "https://copilot.com/": "copilot.microsoft.com",
    "https://www.copilot.com/chats/abc": "copilot.microsoft.com",
    "https://www.meta.ai/": "meta.ai",
    "https://chat.deepseek.com/a/chat/s/1": "deepseek.com",
    "https://grok.com/": "grok.com",
    "https://x.com/i/grok?conversation=1": "grok.com",
    "android-app://com.deepseek.chat/": "deepseek.com",
    "android-app://ai.x.grok/": "grok.com",
    "android-app://com.facebook.stella/": "meta.ai",
}
# referrers that are not a citation
NOT_CITED = ("https://x.com/home", "https://x.com/someone/status/1", "https://t.co/abc",
             "https://platform.deepseek.com/", "https://api-docs.deepseek.com/",
             "https://notgrok.com/", "https://facebook.com/meta.ai")


def hit(url="/", agent=CHROME, address="203.0.113.5", referrer="") -> Hit:
    return Hit(NOON, address, "example.com", "GET", url, "404", referrer, agent)


def audit_line(referrer: str, url: str = "/") -> Line:
    return Line(when=NOON, address="203.0.113.5", host="example.com", method="GET", url=url,
                status="200", referrer=referrer, agent=CHROME, country="US")


class TestReferrers(unittest.TestCase):
    def test_each_new_assistant_is_named_by_its_referrer(self):
        for referrer, name in CITED.items():
            with self.subTest(referrer=referrer):
                self.assertEqual(cited_by(referrer), name)

    def test_x_itself_and_the_other_hosts_are_not_assistants(self):
        for referrer in NOT_CITED:
            with self.subTest(referrer=referrer):
                self.assertEqual(cited_by(referrer), "")

    def test_the_tags(self):
        for url, name in (("/?utm_source=deepseek", "deepseek.com"),
                          ("/?utm_source=grok.com", "grok.com"),
                          ("/?utm_source=meta.ai", "meta.ai"),
                          ("/?utm_source=copilot.com", "copilot.microsoft.com")):
            with self.subTest(url=url):
                self.assertEqual(assistant_name(AI_UTM.search(url).group(1)), name)

    def test_a_bare_meta_tag_is_an_ad_not_meta_ai(self):
        # utm_source=meta is how advertisers tag Facebook and Instagram ads.
        self.assertIsNone(AI_UTM.search("/?utm_source=meta&utm_medium=paid_social"))

    def test_a_reader_sees_the_assistants_name(self):
        for name, shown in (("copilot.microsoft.com", "Copilot"), ("meta.ai", "Meta AI"),
                            ("deepseek.com", "DeepSeek"), ("grok.com", "Grok")):
            self.assertEqual(visits.assistant_label(name), shown)
            self.assertEqual(audit_funnels.SHOWN[name], shown)

    def test_the_dashboard_table_matches_visits_assistants(self):
        js = (Path(visits.__file__).parent / "webapp" / "js" / "labels.js").read_text()
        block = js.split("export const ASSISTANTS = {", 1)[1].split("};", 1)[0]
        self.assertEqual(dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block)), visits.ASSISTANTS)

    def test_a_person_from_one_is_a_cited_visit(self):
        c = Classifier()
        for referrer, name in CITED.items():
            v = c(Hit(NOON, "203.0.113.5", "example.com", "GET", "/", "200", referrer, CHROME))
            self.assertEqual((v.group, v.tier, v.engine), (Group.PEOPLE, Tier.CITED, name))


class TestSecondRoad(unittest.TestCase):
    """The audits read the same lists with their own code and agree."""

    def test_the_audit_counts_the_same_citations(self):
        for referrer in CITED:
            with self.subTest(referrer=referrer):
                self.assertTrue(audit._cited(audit_line(referrer)))
        for referrer in NOT_CITED:
            with self.subTest(referrer=referrer):
                self.assertFalse(audit._cited(audit_line(referrer)))
        self.assertTrue(audit._cited(audit_line("", "/?utm_source=grok")))

    def test_the_audits_name_the_same_assistant(self):
        for referrer, name in CITED.items():
            with self.subTest(referrer=referrer):
                self.assertEqual(audit_release2.assistant_of(audit_line(referrer)), name)
                self.assertEqual(audit_funnels._assistant(audit_line(referrer)),
                                 visits.assistant_label(name))


class TestAdsBot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ranges"

    def tearDown(self):
        self.tmp.cleanup()

    def classifier(self, scanners=()) -> Classifier:
        c = Classifier()
        c.verifier = bot_verify.Verifier(self.dir)
        c.scanners = set(scanners)
        return c

    def test_it_is_named_as_openais_and_checked_against_its_list(self):
        self.assertEqual(AI_TRAINING.search(ADSBOT).group(0), "OAI-AdsBot")
        self.assertEqual(bot_verify.vendor_of("OAI-AdsBot"), "openai")
        self.assertIn("openai-adsbot", bot_verify.VENDORS["openai"][0])
        self.assertEqual(bot_verify.LISTS["openai-adsbot"], "https://openai.com/adsbot.json")
        crawler = bot_policy.match(ADSBOT)
        self.assertEqual((crawler.name, crawler.owner, crawler.tier),
                         ("OAI-AdsBot", "OpenAI", "index"))

    def test_with_lists_the_real_one_counts_and_a_fake_is_a_bot_that_lied(self):
        openai_lists(self.dir)
        c = self.classifier()
        real = c(hit("/landing", ADSBOT, OPENAI_ADS))
        self.assertEqual((real.group, real.tier, real.engine, real.verified),
                         (Group.ANSWER_ENGINE, Tier.TRAINING, "OAI-AdsBot", "verified"))
        fake = c(hit("/.env", ADSBOT, FAKE))
        self.assertEqual((fake.group, fake.engine, fake.claim),
                         (Group.BOTS, "claims to be OAI-AdsBot", "OAI-AdsBot"))

    def test_without_lists_a_scanning_claim_stays_in_bots(self):
        """Rule 2b. No list, or a stale one: nothing proves it OpenAI's."""
        for fetched in (None, datetime.now(UTC) - timedelta(days=30)):
            with self.subTest(lists="stale" if fetched else "none"):
                if fetched:
                    openai_lists(self.dir, fetched)
                c = self.classifier(scanners={(FAKE, ADSBOT)})
                probe = c(hit("/.env.local", ADSBOT, FAKE))
                self.assertEqual((probe.group, probe.probe, probe.tier),
                                 (Group.BOTS, True, None))
                # Its other requests that day are a scanner's (rule 6b).
                home = c(hit("/", ADSBOT, FAKE))
                self.assertEqual((home.group, home.engine), (Group.BOTS, SCANNER))
                # One that never scanned is still OAI-AdsBot, unverified.
                calm = c(hit("/landing", ADSBOT, "203.0.113.78"))
                self.assertEqual((calm.group, calm.engine, calm.verified),
                                 (Group.ANSWER_ENGINE, "OAI-AdsBot", "unverified"))

    def test_a_proven_crawler_that_hits_a_probe_path_stays_its_engine(self):
        openai_lists(self.dir)
        v = self.classifier()(hit("/wp-login.php", ADSBOT, OPENAI_ADS))
        self.assertEqual((v.group, v.probe, v.verified), (Group.ANSWER_ENGINE, True, "verified"))

    def test_a_fake_googlebot_or_chatgpt_user_asking_for_env(self):
        """Rule 2b for the names scanners rotate through, with lists and without."""
        for lists in (False, True):
            if lists:
                openai_lists(self.dir)
                ranges(self.dir, google_common=["192.0.2.0/28"])
            c = self.classifier()
            for agent, with_list in ((GOOGLEBOT, (Group.BOTS, "", None)),
                                     (ASKED, (Group.BOTS, "claims to be ChatGPT-User", "spoofed"))):
                with self.subTest(agent=agent, lists=lists):
                    v = c(hit("/.env", agent, FAKE))
                    want = with_list if lists else (Group.BOTS, "", None)
                    self.assertEqual((v.group, v.engine, v.verified), want)
                    self.assertTrue(v.probe)
        # The real Googlebot following a link to a probe path is Googlebot.
        real = c(hit("/wp-login.php", GOOGLEBOT, "192.0.2.4"))
        self.assertEqual((real.group, real.probe, real.verified),
                         (Group.SEARCH_ENGINE, True, "verified"))

    def test_the_rule_holds_for_every_claimed_crawler(self):
        c = Classifier()                                  # no verifier at all
        for agent in (GOOGLEBOT, "Claude-Web/1.0"):
            with self.subTest(agent=agent):
                v = c(hit("/.git/config", agent))
                self.assertEqual((v.group, v.probe), (Group.BOTS, True))


class TestDayBothRoads(unittest.TestCase):
    """A day with a fake OAI-AdsBot scanning collects and audits clean, with
    lists and without."""

    def day(self, with_lists: bool) -> dict:
        box = Sandbox()
        self.addCleanup(box.close)
        if with_lists:
            folder = box.root / "ranges"
            openai_lists(folder)
            ranges(folder, hosting=[], google_common=["192.0.2.0/28"])
            box.config.write_text(box.config.read_text() + f"bots:\n  ranges_dir: {folder}\n")
        t = datetime(2026, 10, 5, 15, tzinfo=UTC)
        box.log([
            line(t, "203.0.113.20", "/", CHROME),
            line(t + timedelta(seconds=1), FAKE, "/", ADSBOT),
            line(t + timedelta(seconds=2), FAKE, "/.env.local", ADSBOT, status=404),
            line(t + timedelta(seconds=3), FAKE, "/firebase-service-account.json", ADSBOT,
                 status=404),
            line(t + timedelta(seconds=4), OPENAI_ADS, "/landing", ADSBOT),
            line(t + timedelta(seconds=5), "203.0.113.21", "/", CHROME,
                 referrer="https://x.com/i/grok"),
            # Scanners that rotate crawler names, and the real Googlebot
            # following a link to a probe path.
            line(t + timedelta(seconds=6), "203.0.113.90", "/.env", GOOGLEBOT, status=404),
            line(t + timedelta(seconds=7), "203.0.113.91", "/.env", ASKED, status=404),
            line(t + timedelta(seconds=8), "192.0.2.4", "/wp-login.php", GOOGLEBOT, status=404),
        ])
        code, out, err = box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)
        code, out, err = box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        with sqlite3.connect(box.db) as db:
            groups = dict(db.execute("SELECT grp, hits FROM groups WHERE day = ?",
                                     (DAY.isoformat(),)).fetchall())
            cited = dict(db.execute("SELECT name, n FROM counts WHERE day = ? AND "
                                    "kind = 'cited_by'", (DAY.isoformat(),)).fetchall())
        self.assertEqual(cited, {"grok.com": 1})
        return groups

    def test_with_lists(self):
        groups = self.day(True)
        # The three fake OAI-AdsBot requests and the two fake /.env are bots;
        # the real OAI-AdsBot is an AI crawler, the real Googlebot a search engine.
        self.assertEqual((groups["bots"], groups["answer_engines"], groups["search_engines"]),
                         (5, 1, 1))

    def test_without_lists(self):
        # Nothing proves the Googlebot on /wp-login.php Google's: a bot too.
        groups = self.day(False)
        self.assertEqual((groups["bots"], groups["answer_engines"]), (6, 1))
        self.assertNotIn("search_engines", groups)


if __name__ == "__main__":
    unittest.main()
