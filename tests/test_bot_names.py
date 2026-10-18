"""The names added to classify.py's lists on 2026-10-18, from the dev-time
check against Crawler-Detect's corpus (tools/check-bot-names.py).

What is pinned: each new name lands in its intended group, tier and name on
the counting road (classify.Classifier) and in the same group on the audit's
road (audit.Judge, which shares only the name lists); a collected day full
of them recounts with "all match"; and current real browsers, in-app
browsers and phones named "... bot" stay people.
"""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit  # noqa: E402
from skald.classify import (AI_FETCHER_OWNERS, Classifier, Group,  # noqa: E402
                                   Tier)
from skald.config import load_config  # noqa: E402
from skald.parse import Hit  # noqa: E402

from support import UTC, Sandbox, day_lines, line  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
G = "https://developers.google.com/crawling/docs/crawlers-fetchers/"

# (user agent, group, tier, the name the counting road reports)
ADDED = (
    # AI, asked: a person's request is behind the fetch.
    ("Mozilla/5.0 (Linux; arm_64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/119.0.0.0 Safari/537.36 claude-web", Group.ANSWER_ENGINE, Tier.ASKED, "claude-web"),
    ("Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, "
     "like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36 (compatible; Google-Agent; +"
     + G + "google-agent)", Group.ANSWER_ENGINE, Tier.ASKED, "Google-Agent"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
     "Google-Agent; +" + G + "google-agent) Chrome/140.0.0.0 Safari/537.36",
     Group.ANSWER_ENGINE, Tier.ASKED, "Google-Agent"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
     "GoogleAgent-Mariner) Chrome/149.0.7827.196 Safari/537.36",
     Group.ANSWER_ENGINE, Tier.ASKED, "GoogleAgent-Mariner"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 "
     "Safari/537.36 (compatible; Google-GeminiNotebook; +" + G + "google-gemininotebook)",
     Group.ANSWER_ENGINE, Tier.ASKED, "Google-GeminiNotebook"),
    ("Mozilla/5.0 (compatible; Google-NotebookLM)", Group.ANSWER_ENGINE, Tier.ASKED,
     "Google-NotebookLM"),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amzn-User/0.1) "
     "Chrome/119.0.6045.214 Safari/537.36", Group.ANSWER_ENGINE, Tier.ASKED, "Amzn-User"),
    # AI, training or indexing: nobody is waiting.
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amzn-SearchBot/0.1) "
     "Chrome/119.0.6045.214 Safari/537.36", Group.ANSWER_ENGINE, Tier.TRAINING,
     "Amzn-SearchBot"),
    ("Mozilla/5.0 (compatible; Google-CloudVertexBot)", Group.ANSWER_ENGINE, Tier.TRAINING,
     "Google-CloudVertexBot"),
    ("cohere-training-data-crawler/1.0", Group.ANSWER_ENGINE, Tier.TRAINING,
     "cohere-training-data-crawler"),
    # Search engines.
    ("Mozilla/5.0 (compatible; SeznamBot/4.0; +https://o-seznam.cz/)",
     Group.SEARCH_ENGINE, None, "SeznamBot"),
    ("Mozilla/5.0 (compatible; Yeti/1.1; +https://naver.me/spd)", Group.SEARCH_ENGINE, None,
     "Yeti"),
    ("Mozilla/5.0 (compatible; coccocbot-web/1.0; +http://help.coccoc.com/searchengine)",
     Group.SEARCH_ENGINE, None, "coccocbot"),
    ("Mozilla/5.0 (compatible; Qwantbot/1.0; +https://help.qwant.com/bot/)",
     Group.SEARCH_ENGINE, None, "Qwantbot"),
    ("Mozilla/5.0 (compatible; Qwantify/2.3w; +https://www.qwant.com/)/2.3w",
     Group.SEARCH_ENGINE, None, "Qwantify"),
    ("Mozilla/5.0 (compatible; MojeekBot/0.11; +https://www.mojeek.com/bot.html)",
     Group.SEARCH_ENGINE, None, "MojeekBot"),
    ("Sogou web spider/4.0(+http://www.sogou.com/docs/help/webmasters.htm#07)",
     Group.SEARCH_ENGINE, None, "Sogou"),
    # A link preview.
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/123.0.0.0 Safari/537.36 GoogleMessages/15.1", Group.BOTS, None,
     "link preview: Google Messages"),
    # Other bots: a browser agent with a service's name on it, people before.
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/103.0.5060.114 Safari/537.36 DatadogSynthetics", Group.BOTS, None, ""),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/133.0.0.0 Safari/537.36 DebugBear", Group.BOTS, None, ""),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/127.0.6533.99 Safari/537.36 RuxitSynthetic/1.0 v1 t2", Group.BOTS, None, ""),
    ("Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0 Ghost Inspector",
     Group.BOTS, None, ""),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko; Google Page "
     "Speed Insights) Chrome/27.0.1453 Safari/537.36", Group.BOTS, None, ""),
    ("Mozilla/5.0 AppleWebKit/537.36 Chrome/114.0.5735.179 Safari/537.36 "
     "Google-Ads-Conversions", Group.BOTS, None, ""),
    ("Mozilla/5.0 (Windows NT 5.1; rv:11.0) Gecko Firefox/11.0 (via ggpht.com "
     "GoogleImageProxy)", Group.BOTS, None, ""),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "WordPress.com mShots Safari/537.36", Group.BOTS, None, ""),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.34 (KHTML, like Gecko) wkhtmltopdf "
     "Safari/534.34", Group.BOTS, None, ""),
    ("Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0; PTST 2.385)",
     Group.BOTS, None, ""),
    ("Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0) LinkCheck by "
     "Siteimprove.com", Group.BOTS, None, ""),
    ("Mozilla/5.0 zgrab/0.x", Group.BOTS, None, ""),
    ("fasthttp, Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/53.0.2785.101 Safari/537.36", Group.BOTS, None, ""),
)

# Current browsers that must stay people, whatever is added to the lists.
PEOPLE = (
    # Chrome on Windows, Mac, Android; Edge; Firefox; Safari on Mac and iPhone.
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:143.0) Gecko/20100101 Firefox/143.0",
    "Mozilla/5.0 (Android 15; Mobile; rv:143.0) Gecko/143.0 Firefox/143.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/26.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) CriOS/141.0.7390.96 Mobile/15E148 Safari/604.1",
    # Samsung Internet, Opera, Brave-on-Android (Chrome's agent), UC on Android.
    "Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) "
    "SamsungBrowser/28.0 Chrome/130.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36 OPR/124.0.0.0",
    # In-app browsers: Instagram, Facebook, LinkedIn, Google app, TikTok.
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
    "like Gecko) Mobile/15E148 Instagram 400.0.0.40.80 (iPhone15,2; iOS 18_6; en_US; en; "
    "scale=3.00; 1179x2556; 812345678)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
    "like Gecko) Mobile/15E148 [FBAN/FBIOS;FBAV/530.0.0.40.110;FBBV/812345678;"
    "FBDV/iPhone15,2;FBMD/iPhone;FBSN/iOS;FBSV/18.6;FBSS/3;FBCR/;FBID/phone;FBLC/en_US;FBOP/5]",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/AP2A.240905.003; wv) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/141.0.7390.70 Mobile Safari/537.36 "
    "[FB_IAB/FB4A;FBAV/530.0.0.48.74;]",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
    "like Gecko) Mobile/15E148 [LinkedInApp]/9.31.1234",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, "
    "like Gecko) GSA/390.0.812345678 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-A546B Build/UP1A.231005.007; wv) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/141.0.7390.70 Mobile Safari/537.36 "
    "trill_400003 JsSdk/1.0 NetType/WIFI Channel/googleplay AppName/musical_ly "
    "app_version/40.0.3 ByteLocale/en ByteFullLocale/en Region/US",
    # Phones whose model name ends with "bot", and Sogou's own phone browser.
    "Mozilla/5.0 (Linux; Android 7.0; M bot 60 Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, "
    "like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0; POWER BOT Build/MRA58K) AppleWebKit/537.36 (KHTML, "
    "like Gecko) Chrome/54.0.2840.85 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; U; Android 5.1; zh-cn; 1501_M02 Build/LMY47D) AppleWebKit/534.30 "
    "(KHTML, like Gecko) Version/4.0 Mobile Safari/534.30 SogouMSE,SogouMobileBrowser/4.1.0",
)


def verdict(agent: str):
    return Classifier()(Hit(datetime(2026, 10, 5, 9, tzinfo=UTC), "203.0.113.5",
                            "example.com", "GET", "/", "200", "", agent))


class TheCountingRoad(unittest.TestCase):

    def test_each_added_name_lands_where_intended(self):
        for agent, group, tier, name in ADDED:
            with self.subTest(agent=agent):
                v = verdict(agent)
                self.assertIs(v.group, group)
                self.assertIs(v.tier, tier)
                self.assertEqual(v.engine, name)

    def test_current_browsers_stay_people(self):
        for agent in PEOPLE:
            with self.subTest(agent=agent):
                self.assertIs(verdict(agent).group, Group.PEOPLE)

    def test_new_user_fetchers_have_an_owner(self):
        self.assertEqual(AI_FETCHER_OWNERS["claude-web"], "claude.ai")
        self.assertEqual(AI_FETCHER_OWNERS["google-agent"], "gemini.google.com")
        self.assertEqual(AI_FETCHER_OWNERS["amzn-user"], "alexa.amazon.com")

    def test_robots_only_tokens_are_not_crawlers(self):
        from skald.classify import AI_ASKED, AI_TRAINING, SEARCH_ENGINE
        for token in ("Google-Extended",):
            for pattern in (AI_ASKED, AI_TRAINING, SEARCH_ENGINE):
                self.assertIsNone(pattern.search(token))

    def test_a_bot_word_still_counts_outside_a_model_name(self):
        for agent in ("Mozilla/5.0 (compatible; Example bot; +https://example.com/)",
                      "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/141.0.0.0 Mobile Safari/537.36 bot"):
            with self.subTest(agent=agent):
                self.assertIs(verdict(agent).group, Group.BOTS)


class BothRoads(unittest.TestCase):
    """A day of the new names: the audit's road files each line in the same
    group, and the collected day recounts with all match."""

    def setUp(self):
        self.box = Sandbox()
        t = datetime(DAY.year, DAY.month, DAY.day, 14, tzinfo=UTC)
        extra = [line(t + timedelta(minutes=i), f"203.0.113.{100 + i}",
                      "/guides/alpha" if i % 2 else "/", agent)
                 for i, (agent, *_rest) in enumerate(ADDED)]
        extra += [line(t + timedelta(hours=1, minutes=i), f"203.0.113.{200 + i}", "/", agent)
                  for i, agent in enumerate(PEOPLE)]
        # Each person loads the page's script, so no browser is "never rendered".
        extra += [line(t + timedelta(hours=1, minutes=i, seconds=5), f"203.0.113.{200 + i}",
                       "/_next/static/a.js", agent, "https://example.com/")
                  for i, agent in enumerate(PEOPLE)]
        self.lines = day_lines(DAY, 3) + extra
        self.box.log(self.lines)

    def tearDown(self):
        self.box.close()

    def test_the_audit_files_each_line_in_the_same_group(self):
        config = load_config(self.box.config)
        start = datetime(DAY.year, DAY.month, DAY.day, tzinfo=UTC)
        groups = {}
        for got, group in audit.judged(config, UTC, start, start + timedelta(days=1),
                                       [self.box.root / "logs" / "access.log"]):
            if got.path in ("/", "/guides/alpha"):
                groups[got.agent] = group
        for agent, group, _tier, _name in ADDED:
            with self.subTest(agent=agent):
                self.assertEqual(groups[agent], group.value)
        for agent in PEOPLE:
            with self.subTest(agent=agent):
                self.assertEqual(groups[agent], "people")

    def test_a_collected_day_of_them_recounts_exactly(self):
        code, out, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)


if __name__ == "__main__":
    unittest.main()
