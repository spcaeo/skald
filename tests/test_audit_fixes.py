"""Fixes from the independent audit of a real site's logs (2026-10-07).

Each test reproduces one finding as it was found - the wrong figure first -
so it cannot come back. Addresses are RFC 5737 documentation ranges;
tests/fixtures/site_paths.txt is a made-up sitemap of the same size and shape
as the audited site's (sections, guides, a glossary, Canadian English and
French copies), whose page names carry the words scanners hunt for.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from support import line  # noqa: E402

UTC = timezone.utc
OWN = "192.0.2.10"


def at(hour, minute=0, second=0, day=6):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=UTC)


def run_report(config: str, log_lines: list[str], *args):
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "config.yml"
        cfg.write_text(config)
        log = Path(tmp) / "access.log"
        log.write_text("".join(log_lines))
        return subprocess.run([sys.executable, str(ROOT / "report.py"), "--config",
                               str(cfg), "--log", str(log), "--json", *args],
                              capture_output=True, text=True, timeout=120)


class TestOneClassifierForEveryEntryPoint(unittest.TestCase):
    """Finding 2: report.py's --days/--log mode built its own Classifier
    without ours.addresses, so the owner's browsing - and their own click on
    a citation - counted as readers (people 1,624 against 989)."""

    CONFIG = ("site:\n  hosts: [example.com]\n  require_rendering: false\n"
              "ours:\n  user_agents: []\n"
              f"  addresses: [{OWN}]\nreport:\n  timezone: UTC\n")

    def test_the_glance_report_honours_ours_addresses(self):
        import json
        lines = [line(at(9), OWN, "/", referrer="https://www.perplexity.ai/"),
                 line(at(9, 1), "203.0.113.5", "/pricing")]
        for extra in ((), ("--day", "2026-10-06")):
            with self.subTest(mode=extra or "whole file"):
                done = run_report(self.CONFIG, lines, *extra)
                self.assertEqual(done.returncode, 0, done.stderr)
                groups = json.loads(done.stdout)["groups"]
                self.assertEqual(groups["ours"]["hits"], 1)
                self.assertEqual(groups["people"]["hits"], 1)
                self.assertEqual(groups["people"]["citedVisits"], 0)

    def test_nothing_builds_a_classifier_any_other_way(self):
        for path in [*(ROOT / "skald").glob("*.py"), ROOT / "report.py",
                     ROOT / "bin/skald"]:
            if path.name == "classify.py":
                continue
            with self.subTest(path=path.name):
                self.assertNotIn("Classifier(", path.read_text())


class TestVisitsAcrossARotation(unittest.TestCase):
    """Finding 6: files were read newest first, so a reader whose visit ran
    across the rotation was counted as two visits."""

    def setUp(self):
        import os
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # One reader, a page every 20 minutes, the log rotated at 10:25.
        older = [line(at(10, 0), "203.0.113.9", "/a"), line(at(10, 20), "203.0.113.9", "/b")]
        newer = [line(at(10, 40), "203.0.113.9", "/c"), line(at(11, 0), "203.0.113.9", "/d")]
        (self.dir / "access.log.1").write_text("".join(older))
        (self.dir / "access.log").write_text("".join(newer))
        for name, when in (("access.log.1", at(10, 25)), ("access.log", at(11, 1))):
            os.utime(self.dir / name, (when.timestamp(), when.timestamp()))
        self.config = {"logs": {"dir": str(self.dir), "base": "access.log", "days": 2},
                       "site": {"require_rendering": False}}

    def tearDown(self):
        self._tmp.cleanup()

    def test_one_reader_twenty_minutes_apart_is_one_visit_across_the_boundary(self):
        from skald import Group, analyse
        from skald.window import analyse_window, day_window
        from datetime import date
        start, end = day_window(date(2026, 10, 6), UTC)
        for name, totals in (
                ("exact day", analyse_window(self.config, start, end,
                                             now=at(12))),
                ("glance report", analyse(self.config))):
            with self.subTest(name):
                people = totals.groups[Group.PEOPLE]
                self.assertEqual((people.hits, people.views, people.visits), (4, 4, 1))

    def test_rotations_are_read_oldest_first_whatever_order_they_are_named(self):
        from skald.parse import oldest_first
        names = ["access.log", "access.log.1", "access.log.3.gz", "access.log.2.gz"]
        self.assertEqual([p.name for p in oldest_first([self.dir / n for n in names])],
                         ["access.log.3.gz", "access.log.2.gz", "access.log.1", "access.log"])


class TestTiers(unittest.TestCase):
    """Finding 7: index crawlers were filed as "someone just asked"."""

    def tier(self, agent):
        from skald import Classifier, Group
        from skald.parse import Hit
        verdict = Classifier()(Hit(at(9), "198.51.100.1", "example.com", "GET", "/",
                                   "200", "", agent))
        self.assertIs(verdict.group, Group.ANSWER_ENGINE, agent)
        return verdict.tier.value

    def test_index_crawlers_are_training_or_index(self):
        for agent in ("Mozilla/5.0 (compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot)",
                      "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
                      "PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"):
            with self.subTest(agent=agent):
                self.assertEqual(self.tier(agent), "training")

    def test_fetchers_for_a_live_question_are_asked(self):
        for agent in ("Mozilla/5.0 (compatible; ChatGPT-User/1.0; +https://openai.com/bot)",
                      "Mozilla/5.0 (compatible; Claude-User/1.0; +Claude-User@anthropic.com)",
                      "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
                      "Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)",
                      "meta-externalfetcher/1.1 (+https://developers.facebook.com/docs/"
                      "sharing/webmasters/crawler)"):
            with self.subTest(agent=agent):
                self.assertEqual(self.tier(agent), "asked")

    def test_google_extended_is_never_an_engine(self):
        from skald.classify import AI_ASKED, AI_TRAINING
        self.assertIsNone(AI_TRAINING.search("Google-Extended"))
        self.assertIsNone(AI_ASKED.search("Google-Extended"))


class TestProbesAreShapesNotWords(unittest.TestCase):
    """Finding 4: PROBE matched the bare word "backup", so a real page whose
    name held it (here: /guides/backup-and-restore-your-schedules/) and its
    /ca/ copy, and every person who read them, were filed as a credential
    scanner."""

    SITE = [p.strip() for p in (ROOT / "tests" / "fixtures" / "site_paths.txt").open()
            if p.startswith("/")]

    def verdict(self, url, agent=None, status="200"):
        from support import CHROME
        from skald import Classifier
        from skald.parse import Hit
        return Classifier()(Hit(at(9), "203.0.113.5", "example.com", "GET", url,
                                status, "", agent or CHROME))

    def test_no_page_of_a_realistic_site_is_a_probe(self):
        from skald import Group
        self.assertEqual(len(self.SITE), 475)
        # Pages named with the words scanners hunt for, or the fixture proves nothing.
        for word in ("backup", "admin", "config", "sql", "env", "keys", "login", "wordpress",
                     "database", "github"):
            self.assertTrue(any(word in p for p in self.SITE), word)
        for path in self.SITE:
            got = self.verdict(path)
            if got.probe or got.group is not Group.PEOPLE:
                self.fail(f"{path} filed as {got.group.value}, probe={got.probe}")

    def test_words_that_merely_appear_in_a_page_name_are_not_probes(self):
        for path in ("/guides/backup-and-restore-your-schedules/",
                     "/administration-guide/", "/admin-tips/", "/blog/wp-alternatives",
                     "/secrets-management/", "/credential-rotation/", "/configuration/",
                     "/environment/", "/github/", "/sdk-docs/", "/database-alerts/",
                     "/sitemap.xml.gz",
                     "/_next/image?url=%2Fimages%2Fbackup-and-restore.png&w=640"):
            with self.subTest(path=path):
                self.assertFalse(self.verdict(path).probe)

    def test_the_things_scanners_hunt_for_still_are(self):
        for path in ("/.env", "/.env.local", "/app/.env", "/.git/config", "/wp-login.php",
                     "/wp-admin/install.php", "/admin", "/phpmyadmin/", "/backup.zip",
                     "/db.sql", "/dump.sql.gz", "/backup/", "/config.json",
                     "/credentials.json", "/secrets.yml", "/service-account-key.json",
                     "/docker-compose.yml", "/id_rsa", "/server.key", "/terraform.tfstate",
                     "/.aws/credentials", "/_ignition/execute-solution", "/actuator/env",
                     "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php",
                     "/cgi-bin/luci", "/HNAP1/", "/owa/auth/logon.aspx", "/env.js",
                     "/api/config", "/xmlrpc.php", "/.DS_Store", "/telescope/requests",
                     "/laravel/.env", "/phpinfo", "/key.json"):
            with self.subTest(path=path):
                self.assertTrue(self.verdict(path, status="404").probe)

    def test_attacks_in_the_query_string_are_probes(self):
        for url in ("/?file=../../etc/passwd", "/search?q=${jndi:ldap://x}",
                    "/?XDEBUG_SESSION_START=1", "/p?id=1+UNION+SELECT+1"):
            with self.subTest(url=url):
                self.assertTrue(self.verdict(url).probe)


NEXUS = ("Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/153.0.8010.52 Mobile Safari/537.36")


class TestMisfiledAgentsAndReferrers(unittest.TestCase):
    """Finding 8: agents and referrers in the wrong group. User agents are
    the ones in the audited log."""

    def verdict(self, agent, referrer="", url="/"):
        from skald import Classifier
        from skald.parse import Hit
        return Classifier()(Hit(at(9), "203.0.113.5", "example.com", "GET", url,
                                "200", referrer, agent))

    def test_tools_with_a_browser_prefix_are_bots(self):
        from skald import Group
        for agent in ("Mozilla/5.0 (compatible; ctwatch/0.1)",
                      "Mozilla/5.0 (compatible; jSystem3-metadata-indexer/0.1)",
                      NEXUS,
                      "Mozilla/5.0 (compatible; ExampleBot/4.0; +https://example.com/)",
                      "Mozilla/5.0 (compatible; FooBot/2.1)"):
            with self.subTest(agent=agent):
                self.assertIs(self.verdict(agent).group, Group.BOTS)

    def test_bots_are_listed_by_a_name_a_person_can_read(self):
        """279 of the audited day's bot requests were listed as 'Mozilla'."""
        from skald.aggregate import _short_agent
        self.assertEqual(_short_agent("Mozilla/5.0 (compatible; ctwatch/0.1)"), "ctwatch")
        self.assertEqual(_short_agent(NEXUS), "Googlebot template, no Googlebot")
        self.assertEqual(_short_agent("Mozilla/5.0 (X11; Linux) Chrome/1"), "browser-like agent")
        self.assertEqual(_short_agent("curl/8.7.1"), "curl")

    def test_the_real_googlebot_template_is_still_search(self):
        from skald import Group
        got = self.verdict(NEXUS + " (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
        self.assertIs(got.group, Group.SEARCH_ENGINE)
        self.assertEqual(got.engine, "Googlebot")

    def test_a_cubot_phone_is_a_person(self):
        from skald import Group
        agent = ("Mozilla/5.0 (Linux; Android 10; CUBOT X30) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
        self.assertIs(self.verdict(agent).group, Group.PEOPLE)

    def test_a_citation_is_matched_on_the_referrer_host(self):
        from support import CHROME
        from skald.classify import cited_by
        cases = {
            "https://www.perplexity.ai/": "perplexity.ai",
            "https://perplexity.ai/search/x": "perplexity.ai",
            "https://chat.openai.com/": "chatgpt.com",
            "https://chatgpt.com/": "chatgpt.com",
            "https://you.com/search?q=x": "you.com",
            "https://www.bing.com/chat?q=x": "copilot.microsoft.com",
            "https://thank-you.com/": "",
            "https://notperplexity.ai/": "",
            "https://example.org/?ref=chatgpt.com": "",
            "https://www.bing.com/search?q=x": "",
            "https://www.google.com/": "",
            "chatgpt.com": "chatgpt.com",
            "": "",
        }
        for referrer, expected in cases.items():
            with self.subTest(referrer=referrer):
                self.assertEqual(cited_by(referrer), expected)
        self.assertIsNone(self.verdict(CHROME, "https://thank-you.com/").tier)


class TestAdsQualityChecks(unittest.TestCase):
    """Finding 8: AdsBot-Google (54 of 142 search requests on the audited
    day) was counted as indexing. It stays in the search group - Google's,
    and wanted - but on its own line, out of the indexing figure."""

    LINES = [
        line(at(9), "198.51.100.1", "/", "AdsBot-Google (+http://www.google.com/adsbot.html)"),
        line(at(9, 1), "198.51.100.1", "/pricing",
             NEXUS + " (compatible; AdsBot-Google-Mobile; +http://www.google.com/mobile/adsbot.html)"),
        line(at(9, 2), "198.51.100.2", "/",
             NEXUS + " (compatible; Google-Adwords-Instant-Mobile; +http://www.google.com/adsbot.html)"),
        line(at(9, 3), "198.51.100.3", "/",
             "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    ]

    def totals(self):
        from support import totals_for
        return totals_for(self.LINES)

    def test_they_are_search_engines_counted_apart(self):
        from skald import Group
        from skald.classify import ads_checks
        from skald.kpi import KPIS
        totals = self.totals()
        search = totals.groups[Group.SEARCH_ENGINE]
        self.assertEqual(search.hits, 4)
        self.assertEqual(dict(search.engines), {"AdsBot-Google": 2, "Google-Adwords-Instant": 1,
                                                "Googlebot": 1})
        self.assertEqual(ads_checks(search.engines), 3)
        indexing = next(k for k in KPIS if k.key == "search").value(totals)
        self.assertEqual(indexing, 1)

    def test_every_report_shows_them_on_their_own_line(self):
        from skald import Group, as_html, as_text
        totals = self.totals()
        text = as_text(totals, [Group.SEARCH_ENGINE])
        self.assertIn("Indexing       1 fetches by search crawlers", text)
        self.assertIn("Ads checks     3 ads quality checks", text)
        self.assertIn("Ads quality checks", as_html(totals, [Group.SEARCH_ENGINE], "t"))

    def test_export_marks_them(self):
        from skald import export
        rows = export._engine_rows({}, {"AdsBot-Google": 2, "Googlebot": 1},
                                   export.Filters())
        self.assertEqual(rows, [("search_engines", "ads", "AdsBot-Google", 2),
                                ("search_engines", "", "Googlebot", 1)])


class TestCountriesCountVisits(unittest.TestCase):
    """Finding 8: the country card counted requests, so one reader loading
    forty assets made their country look forty times as big."""

    def test_one_reader_with_many_requests_is_one_visit_from_one_country(self):
        from support import totals_for
        from skald import Group, as_text
        lines = [line(at(9, 0, i), "203.0.113.5", f"/_next/static/{i}.js", country="CA")
                 for i in range(40)]
        lines += [line(at(9, 1), "203.0.113.5", "/", country="CA"),
                  line(at(9, 2), "203.0.113.6", "/", country="US")]
        totals = totals_for(lines)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual(people.hits, 42)
        self.assertEqual(dict(people.countries), {"CA": 1, "US": 1})
        # Shown as readers, one each, in the readers card.
        self.assertIn("CAN 1 (50%), \U0001F1FA\U0001F1F8 USA 1 (50%)",
                      as_text(totals, [Group.PEOPLE]))

    def test_history_files_the_visits_under_their_own_name(self):
        """Rows written before held requests under people_country; they are
        never read back as visits."""
        from support import totals_for
        from skald.store import History
        from datetime import date
        with tempfile.TemporaryDirectory() as tmp, History(Path(tmp) / "h") as h:
            day = date(2026, 10, 6)
            h.record("example.com", day, totals_for([line(at(9), country="CA")]), "UTC", [])
            h.db.execute("INSERT INTO counts VALUES ('example.com', '2026-10-06', "
                         "'people_country', 'CA', 40)")
            got = h.period("example.com", day, day).totals
        from skald import Group
        self.assertEqual(dict(got.groups[Group.PEOPLE].countries), {"CA": 1})


class TestUnreadableLines(unittest.TestCase):
    """Finding 5: lines no format parsed were dropped without a count. A
    format that quietly stops matching looks exactly like a quiet day."""

    def write(self, good: int, bad: int) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "access.log"
        path.write_text("".join(line(at(9, 0, i % 60), f"203.0.113.{i % 200}")
                                for i in range(good))
                        + "this is not a log line\n" * bad + "\n\n")
        return path

    def tearDown(self):
        if hasattr(self, "_tmp"):
            self._tmp.cleanup()

    def test_they_are_counted_and_stated(self):
        from skald import Group, as_html, as_text, check
        from skald.window import analyse_paths
        totals = analyse_paths({}, [self.write(1000, 5)])
        self.assertEqual((totals.lines_read, totals.unparsed), (1005, 5))
        self.assertEqual(check(totals), [])
        self.assertIn("Unreadable lines: 5 of 1,005", as_text(totals, [Group.PEOPLE]))
        self.assertIn("Unreadable lines: 5 of 1,005", as_html(totals, [Group.PEOPLE], "t"))

    def test_above_the_limit_the_figures_are_withheld(self):
        from skald import check
        from skald.window import analyse_paths
        path = self.write(1000, 20)
        totals = analyse_paths({}, [path])
        self.assertIn("too many unreadable lines", [p.what for p in check(totals)])
        relaxed = analyse_paths({"report": {"max_unparsed_percent": "5"}}, [path])
        self.assertEqual(check(relaxed), [])

    def test_a_request_with_no_request_line_is_a_request_not_an_unreadable_line(self):
        """The audited log's 2 'unreadable' lines were clients that connected
        and sent nothing ("" 400). The server answered them: they are
        requests - bots, with no agent - and the count must include them."""
        from skald import Group, check
        from skald.window import analyse_paths
        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "access.log"
        path.write_text(
            '198.51.100.9 - - [06/Oct/2026:22:27:33 +0000] "" 400 0 "-" "-"\n'
            '198.51.100.9 - - [06/Oct/2026:22:27:34 +0000] "\\x16\\x03\\x01\\x02" 400 157 "-" "-"\n'
            'notatime 198.51.100.9 example.com "GET / HTTP/1.1" 200 1 "-" "-" 0.1 cc=US ray=-\n'
            + line(at(22, 30), "203.0.113.1", "/"))
        totals = analyse_paths({"site": {"require_rendering": False}}, [path])
        self.assertEqual((totals.lines_read, totals.unparsed, totals.parsed), (4, 1, 3))
        self.assertEqual(totals.groups[Group.BOTS].hits, 2)
        self.assertEqual([p.what for p in check(totals)], ["too many unreadable lines"])

    def test_history_keeps_the_count_and_the_command_line_says_it(self):
        from support import Sandbox
        box = Sandbox()
        try:
            box.log([line(at(9, 0, i), f"203.0.113.{i}") for i in range(50)]
                    + ["garbage\n"])
            code, out, err = box.run("--today", "2026-10-07", "collect")
            self.assertEqual(code, 1, out)       # 1 of 51 is 2%: over 1%
            self.assertIn("too many unreadable lines", err)
            from skald.store import History
            with History(box.db) as h:
                row = h.db.execute("SELECT lines_read, unparsed, verified FROM days").fetchone()
            self.assertEqual(row, (51, 1, 0))
        finally:
            box.close()


class TestBrowserUACrawlers(unittest.TestCase):
    """Finding 1: on the audited day, 7 sessions sending Chrome user agents
    fetched robots.txt, sitemaps and ads.txt and made 111 of 182 "people"
    page views; 91 of 119 visits read no page at all."""

    def analyse(self, lines):
        from skald.window import analyse_paths, analyse_window, day_window
        from datetime import date
        self._tmp = tempfile.TemporaryDirectory()
        path = Path(self._tmp.name) / "access.log"
        path.write_text("".join(lines))
        start, end = day_window(date(2026, 10, 6), UTC)
        legacy = {"site": {"require_rendering": False}}   # page-only readers
        return {"exact day": analyse_window(legacy, start, end, paths=[path]),
                "glance report": analyse_paths(legacy, [path])}

    def tearDown(self):
        if hasattr(self, "_tmp"):
            self._tmp.cleanup()

    def test_a_session_that_fetches_a_crawler_file_is_a_bot_in_every_request(self):
        from skald import Group, check
        from skald.classify import CRAWLER_SESSION
        for crawler_file in ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml",
                             "/post-sitemap.xml.gz", "/ads.txt",
                             "/.well-known/security.txt", "/security.txt"):
            lines = [
                # Pages first, the crawler file last: the rule must still see it.
                line(at(9), "203.0.113.50", "/pricing"),
                line(at(9, 0, 5), "203.0.113.50", "/"),
                line(at(9, 0, 9), "203.0.113.50", crawler_file),
                # Same address, another browser: a different person.
                line(at(9, 1), "203.0.113.50", "/", "Mozilla/5.0 (iPhone) Safari/604.1"),
                line(at(9, 2), "203.0.113.51", "/about"),
            ]
            for mode, totals in self.analyse(lines).items():
                with self.subTest(file=crawler_file, mode=mode):
                    self.assertEqual(totals.groups[Group.PEOPLE].hits, 2)
                    bots = totals.groups[Group.BOTS]
                    self.assertEqual(bots.hits, 3)
                    self.assertEqual(dict(bots.agents), {CRAWLER_SESSION: 3})
                    self.assertEqual(check(totals), [])
            self.tearDown()

    def test_a_named_crawler_fetching_robots_txt_keeps_its_name(self):
        from skald import Group
        lines = [line(at(9), "198.51.100.1", "/robots.txt",
                      "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
                 line(at(9, 1), "198.51.100.1", "/",
                      "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")]
        totals = self.analyse(lines)["exact day"]
        self.assertEqual(totals.groups[Group.SEARCH_ENGINE].hits, 2)


class TestReadersAreTheHeadline(unittest.TestCase):
    """Finding 1b: the headline counted sessions, and most sessions read no
    page. "Real people" is now visits with at least one page view; all
    browser sessions stay as the second figure."""

    LINES = [
        line(at(9), "203.0.113.1", "/"),                      # reads a page
        line(at(9, 0, 1), "203.0.113.1", "/_next/static/a.js"),
        line(at(9, 0, 5), "203.0.113.2", "/_next/static/a.js"),  # assets only
        line(at(9, 0, 6), "203.0.113.3", "/old", status=301),    # a redirect only
        line(at(9, 0, 7), "203.0.113.4", "/a"),                  # two pages, one visit
        line(at(9, 5), "203.0.113.4", "/b"),
        line(at(11), "203.0.113.4", "/c"),                       # a second visit
    ]

    def test_a_reader_is_a_visit_with_a_page_view(self):
        from support import totals_for
        from skald import Group, check
        totals = totals_for(self.LINES)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.visits, people.readers, people.views), (5, 3, 4))
        self.assertEqual(check(totals), [])

    def test_every_report_leads_with_readers(self):
        from support import totals_for
        from skald import Group, as_html, as_text
        from skald.kpi import KPIS
        totals = totals_for(self.LINES)
        self.assertEqual(KPIS[0].key, "people_readers")
        self.assertEqual(KPIS[0].value(totals), 3)
        text = as_text(totals, [Group.PEOPLE])
        self.assertLess(text.index("Readers"), text.index("Visits"))
        self.assertIn("5 browser sessions in all, 2 without a page view", text)
        self.assertIn("visits that read at least one page", as_html(totals, [Group.PEOPLE], "t"))

    def test_more_readers_than_visits_is_caught(self):
        from support import totals_for
        from skald import Group, check
        totals = totals_for(self.LINES)
        totals.groups[Group.PEOPLE].readers = 9
        self.assertIn("people: more readers than visits or page views",
                      [p.what for p in check(totals)])


class TestPartialDays(unittest.TestCase):
    """Finding 3, and re-audit (b): a day is whole only if its own lines run
    from within `coverage_gap_minutes` (default 60) of its local midnight to
    within it of the next. Anything else - the log began mid-day, it stopped,
    a multi-day hole, or the day is not over - is a partial day: stored,
    shown labelled, left out of every comparison, mailed as "partial day,
    data from HH:MM". Older log files no longer count as proof: one written
    before midnight said nothing about a hole after it."""

    def setUp(self):
        from support import Sandbox
        self.box = Sandbox(tz="America/New_York", coverage_gap=60)
        self.ny = __import__("zoneinfo").ZoneInfo("America/New_York")

    def tearDown(self):
        self.box.close()

    def ny_at(self, day, hour, minute=0):
        return datetime(2026, 10, day, hour, minute, tzinfo=self.ny)

    def log_from(self, day, hour, minute, people=3):
        """People from hour:minute, then a monitor every 20 minutes to the
        end of the day, so the day's end is covered."""
        first = self.ny_at(day, hour, minute)
        lines = [line(first + timedelta(minutes=i), f"203.0.113.{i + 1}", "/")
                 for i in range(people)]
        t = first + timedelta(minutes=20)
        while t.date() == first.date():
            lines.append(line(t, "198.51.100.200", "/", "UptimeRobot/2.0"))
            t += timedelta(minutes=20)
        return lines

    def test_a_log_that_starts_mid_day_makes_a_partial_day(self):
        from skald.store import History
        from datetime import date
        self.box.log(self.log_from(6, 14, 5))
        code, out, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertEqual(code, 0, err)
        self.assertIn("PARTIAL day (data from 14:05)", out)
        with History(self.box.db) as h:
            self.assertEqual(h.state("example.com", date(2026, 10, 6)), "partial")
            period = h.period("example.com", date(2026, 10, 6), date(2026, 10, 6))
        self.assertEqual(period.recorded, [])            # out of every comparison
        self.assertEqual(period.partial, [date(2026, 10, 6)])
        self.assertEqual(period.totals.hits, 0)

    def test_the_dashboard_labels_it_and_leaves_it_out_of_the_kpis(self):
        self.box.log(self.log_from(6, 14, 5))
        self.box.run("--today", "2026-10-07", "collect")
        self.box.run("--today", "2026-10-07", "dashboard")
        page = (self.box.root / "www" / "example.com" / "index.html").read_text()
        self.assertIn("partial day, data from 14:05", page)
        self.assertIn("partial, so left out", page)
        self.assertIn('<td>Yesterday</td><td class="v">-</td>', page)

    def test_its_daily_mail_says_so_and_the_weekly_refuses_it(self):
        import os
        from unittest import mock
        from support import SECRETS
        from skald import mailer
        self.box.log(self.log_from(6, 14, 5))
        self.box.run("--today", "2026-10-07", "collect")
        with mock.patch.dict(os.environ, SECRETS):
            code, out, err = self.box.run("--today", "2026-10-07", "mail", "--daily",
                                          "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("daily traffic, Tue 6 Oct 2026 - partial day, data from 14:05", out)
        self.assertIn("Not a whole day, and not used in any comparison.", out)
        self.assertIn("each day was checked against the limit when collected",
                      " ".join(out.split()))
        self.assertNotIn("above 100%", out)
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", "2026-10-07", "mail", "--weekly")
        self.assertEqual(code, 1)
        self.assertIn("partial day(s) 2026-10-06", err)
        smtp.assert_not_called()

    def state_of(self, day):
        from skald.store import History
        from datetime import date
        with History(self.box.db) as h:
            return h.state("example.com", date(2026, 10, day))

    def test_a_log_running_midnight_to_midnight_is_whole(self):
        """Including one that starts exactly at local midnight."""
        self.box.log(self.log_from(6, 0, 0))
        code, out, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertNotIn("PARTIAL", out)
        self.assertEqual(self.state_of(6), "ok")

    def test_a_log_that_stops_early_is_partial_until_its_last_line(self):
        lines = [l for l in self.log_from(6, 0, 10) if "T21:" not in l and "T22:" not in l
                 and "T23:" not in l]
        self.box.log(lines)
        code, out, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertIn("PARTIAL day (data until 20:50)", out)
        self.assertEqual(self.state_of(6), "partial")

    def test_a_hole_of_days_is_partial_whatever_older_files_say(self):
        """Old code took any rotation last written before midnight as proof
        the day was whole, so a three-day hole still gave a whole day."""
        import os
        old = self.box.root / "logs" / "access.log.1"
        old.write_text(line(self.ny_at(3, 2, 0), "203.0.113.1", "/"))
        os.utime(old, (self.ny_at(3, 2, 1).timestamp(),) * 2)
        self.box.log(self.log_from(6, 9, 0))
        code, out, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertIn("PARTIAL day (data from 09:00)", out)
        self.assertEqual(self.state_of(6), "partial")

    def test_the_tolerance_is_configurable(self):
        self.box.config.write_text(self.box.config.read_text().replace(
            "coverage_gap_minutes: 60", "coverage_gap_minutes: 600"))
        self.box.log(self.log_from(6, 9, 0))
        code, out, err = self.box.run("--today", "2026-10-07", "collect")
        self.assertEqual(self.state_of(6), "ok")

    def test_a_day_that_is_not_over_is_partial_until_now(self):
        from skald.store import History
        from datetime import date
        import os
        log = self.box.log([line(self.ny_at(6, 23, 0), "203.0.113.9", "/")]
                           + self.log_from(7, 9, 0))
        stamp = self.ny_at(7, 11, 59).timestamp()      # written this morning
        os.utime(log, (stamp, stamp))
        code, out, err = self.box.run("--today", "2026-10-07", "collect", "--day", "today")
        self.assertIn("data until 12:00", out)
        with History(self.box.db) as h:
            self.assertEqual(h.state("example.com", date(2026, 10, 7)), "partial")

    def test_export_marks_it_and_backfill_collects_it_again(self):
        self.box.log(self.log_from(6, 14, 5))
        self.box.run("--today", "2026-10-07", "collect")
        code, out, _ = self.box.run("--today", "2026-10-07", "export", "--from",
                                    "2026-10-06", "--to", "2026-10-06", "--group", "people")
        self.assertIn("2026-10-06,partial,people", out)
        code, out, _ = self.box.run("--today", "2026-10-07", "backfill", "--days", "1")
        self.assertIn("ok 1", out)
        self.assertNotIn("skipped 1", out)


class TestLiveAndViewsInheritTheFixes(unittest.TestCase):
    """The auditor's point: the live panel and the path views must apply
    finding 1 (crawler sessions) and finding 6 (a visit across the rotation)
    exactly as collect does. One log, read by all three."""

    def setUp(self):
        import os
        from support import Sandbox
        self.box = Sandbox(views=["{name: Guides, path_prefix: /guides/}"])
        logs = self.box.root / "logs"
        reader, crawler = "203.0.113.20", "203.0.113.30"
        # Rotated at 10:25: a reader either side of it, 20 minutes apart, and
        # a Chrome-agent crawler that fetches robots.txt after its pages.
        older = [line(at(10, 0, day=7), reader, "/guides/a"),
                 line(at(10, 20, day=7), reader, "/guides/b"),
                 line(at(10, 21, day=7), crawler, "/guides/a")]
        newer = [line(at(10, 40, day=7), reader, "/guides/c"),
                 line(at(10, 41, day=7), crawler, "/guides/b"),
                 line(at(10, 42, day=7), crawler, "/robots.txt")]
        (logs / "access.log.1").write_text("".join(older))
        (logs / "access.log").write_text("".join(newer))
        (logs / "access.log.2.gz").write_bytes(__import__("gzip").compress(b""))
        for name, when in (("access.log.2.gz", at(0, 0, day=1)),
                           ("access.log.1", at(10, 25, day=7)),
                           ("access.log", at(11, 59, day=7))):
            os.utime(logs / name, (when.timestamp(), when.timestamp()))

    def tearDown(self):
        self.box.close()

    def check(self, people, bots, crawler_hits):
        from skald.classify import CRAWLER_SESSION
        self.assertEqual((people["hits"], people["visits"], people["readers"]), (3, 1, 1))
        self.assertEqual(bots["hits"], crawler_hits)
        self.assertEqual(bots["agents"], {CRAWLER_SESSION: crawler_hits})

    def test_the_live_panel(self):
        import json
        code, _, err = self.box.run("--today", "2026-10-07", "live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["groups"]["people"], 3)
        self.assertEqual(snap["groups"]["bots"], 3)
        self.assertEqual((snap["people"]["visits"], snap["people"]["readers"]), (1, 1))

    def test_the_whole_site_and_its_view(self):
        from datetime import date
        from skald import Group
        from skald.store import History, view_key
        code, out, err = self.box.run("--today", "2026-10-08", "collect", "--day",
                                      "2026-10-07")
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            # The view holds the crawler's two /guides/ pages - still bots,
            # though the robots.txt that gave it away is outside the view.
            for key, crawler_hits in (("example.com", 3),
                                      (view_key("example.com", "guides"), 2)):
                with self.subTest(key=key):
                    t = h.period(key, date(2026, 10, 7), date(2026, 10, 7)).totals
                    people, bots = t.groups[Group.PEOPLE], t.groups[Group.BOTS]
                    self.check({"hits": people.hits, "visits": people.visits,
                                "readers": people.readers},
                               {"hits": bots.hits, "agents": dict(bots.agents)},
                               crawler_hits)



class TestNoStateInTheRepository(unittest.TestCase):
    """Re-audit (f): an empty history.sqlite.schema-v2.bak was committed. A
    history file or its backup is state, never source."""

    def test_no_history_or_backup_file_is_tracked(self):
        import shutil
        if not shutil.which("git") or not (ROOT / ".git").exists():
            self.skipTest("not a git checkout")
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                                 text=True, check=True).stdout.split()
        stray = [f for f in tracked if f.endswith((".bak", ".sqlite", ".sqlite-journal"))]
        self.assertEqual(stray, [])
        ignored = (ROOT / ".gitignore").read_text().split()
        for pattern in ("*.sqlite", "*.bak"):
            self.assertIn(pattern, ignored)


class TestCompatibleWithoutAnEngine(unittest.TestCase):
    """Re-audit (c): "Mozilla/5.0 (compatible; SomeNewBot)" - no version, no
    URL - passed as a person. A "compatible;" agent with no browser engine
    in it is a bot; Internet Explorer, which says "compatible;" too, names
    its engine (Trident) and stays a person."""

    def group(self, agent):
        from skald import Classifier
        from skald.parse import Hit
        return Classifier()(Hit(at(9), "203.0.113.5", "example.com", "GET", "/",
                                "200", "", agent)).group.value

    def test_an_unnamed_engine_compatible_agent_is_a_bot(self):
        for agent in ("Mozilla/5.0 (compatible; SomeNewBot)",
                      "Mozilla/5.0 (compatible; Fetcher)",
                      "Mozilla/5.0 (compatible; Barkrowler/0.9; +https://x.example)"):
            with self.subTest(agent=agent):
                self.assertEqual(self.group(agent), "bots")

    def test_browsers_that_say_compatible_and_name_an_engine_are_people(self):
        for agent in ("Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.1; Trident/6.0)",
                      "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 "
                      "Firefox/128.0",
                      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"):
            with self.subTest(agent=agent):
                self.assertEqual(self.group(agent), "people")


class TestOneNamePerAssistant(unittest.TestCase):
    """Re-audit (d): the same assistant had different names by signal -
    "chatgpt" from a UTM tag, "chatgpt.com" from a referrer, and
    "chat.openai.com" from the old host - and so was split across rows."""

    def source(self, referrer="", url="/"):
        from support import CHROME
        from skald import Classifier
        from skald.parse import Hit
        return Classifier()(Hit(at(9), "203.0.113.5", "example.com", "GET", url,
                                "200", referrer, CHROME)).engine

    def test_every_signal_for_one_assistant_gives_one_name(self):
        cases = {
            "chatgpt.com": [("https://chatgpt.com/", "/"), ("https://chat.openai.com/c/x", "/"),
                            ("", "/?utm_source=chatgpt.com"), ("", "/?utm_source=openai")],
            "perplexity.ai": [("https://www.perplexity.ai/", "/"),
                              ("", "/?utm_source=perplexity")],
            "copilot.microsoft.com": [("https://copilot.microsoft.com/", "/"),
                                      ("https://www.bing.com/chat?q=x", "/"),
                                      ("", "/?utm_source=copilot")],
            "claude.ai": [("https://claude.ai/chat/x", "/"), ("", "/?utm_source=claude.ai")],
        }
        for name, signals in cases.items():
            for referrer, url in signals:
                with self.subTest(name=name, referrer=referrer, url=url):
                    self.assertEqual(self.source(referrer, url), name)

    def test_history_written_with_the_old_names_reads_back_as_one(self):
        from datetime import date
        from support import totals_for
        from skald import Group
        from skald.store import History
        day = date(2026, 10, 6)
        with tempfile.TemporaryDirectory() as tmp, History(Path(tmp) / "h") as h:
            h.record("example.com", day, totals_for([line(at(9))]), "UTC", [])
            h.db.executemany("INSERT INTO counts VALUES ('example.com', '2026-10-06', "
                             "'cited_by', ?, ?)", [("chatgpt", 2), ("chatgpt.com", 3),
                                                   ("chat.openai.com", 1)])
            got = h.period("example.com", day, day).totals.groups[Group.PEOPLE].cited_by
        self.assertEqual(dict(got), {"chatgpt.com": 6})


class TestUnreadableShareIsPerWindow(unittest.TestCase):
    """Re-audit (e): the unreadable share was per file, so five junk lines in
    a quiet day were diluted by a busy neighbour in the same file - and
    charged to that neighbour too. A line has no timestamp of its own, so it
    is placed by the readable line just before it (or after it, at the start
    of a file)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "access.log"
        busy = [line(at(10, i // 60, i % 60, day=5), f"203.0.113.{i % 200}")
                for i in range(1000)]
        quiet = [line(at(10, 0, i, day=6), "203.0.113.7", "/") for i in range(50)]
        junk = ["this is not a log line\n"] * 5
        self.path.write_text("".join(busy + quiet[:25] + junk + quiet[25:]))

    def tearDown(self):
        self._tmp.cleanup()

    def window(self, day):
        from datetime import date
        from skald.window import analyse_window, day_window
        start, end = day_window(date(2026, 10, day), UTC)
        return analyse_window({}, start, end, paths=[self.path])

    def test_the_junk_counts_against_the_day_it_sits_in(self):
        from skald import check
        quiet, busy = self.window(6), self.window(5)
        self.assertEqual((quiet.unparsed, quiet.lines_read), (5, 55))
        self.assertIn("too many unreadable lines", [p.what for p in check(quiet)])
        self.assertEqual((busy.unparsed, busy.lines_read), (0, 1000))
        self.assertEqual(check(busy), [])

    def test_the_whole_file_glance_still_counts_the_file(self):
        from skald.window import analyse_paths
        totals = analyse_paths({}, [self.path])
        self.assertEqual((totals.unparsed, totals.lines_read), (5, 1055))


class TestCrawlerRuleIsNarrow(unittest.TestCase):
    """Re-audit (a): the crawler rule marked an address+agent for the whole
    window and on any host, so a person's reading could become bots. It now
    holds only for the 30-minute visit that fetched the crawler file, on the
    site's own hosts, and never for a visit that loaded the site's own
    scripts, styles or payloads for its pages - a browser does, a crawler
    does not. Real shape kept: a crawler with 99 pages and 2 assets."""

    READER = "203.0.113.40"
    SITE = "https://example.com"

    def page(self, when, path, address=None, host="example.com", referrer="-"):
        return line(when, address or self.READER, path, host=host, referrer=referrer)

    def reading(self, when, path="/guides/a", address=None):
        """A page as a browser loads it: the page, then its own JS and CSS."""
        ref = self.SITE + path
        return [self.page(when, path, address),
                self.page(when + timedelta(seconds=1), "/_next/static/app.js", address,
                          referrer=ref),
                self.page(when + timedelta(seconds=1), "/_next/static/app.css", address,
                          referrer=ref)]

    def people(self, lines):
        from skald import Group, check
        from skald.window import analyse_paths
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(lines))
            totals = analyse_paths({"site": {"hosts": ["example.com"],
                                             "require_rendering": False}}, [path])
        self.assertEqual(check(totals), [])
        people = totals.groups.get(Group.PEOPLE)
        bots = totals.groups.get(Group.BOTS)
        return (people.hits if people else 0, people.readers if people else 0,
                bots.hits if bots else 0)

    def test_a_reader_who_opens_robots_txt_hours_later_stays_a_reader(self):
        lines = self.reading(at(9)) + [self.page(at(14), "/robots.txt")]
        self.assertEqual(self.people(lines), (3, 1, 1))

    def test_an_seo_extension_fetching_robots_txt_from_the_page_is_still_a_person(self):
        ref = self.SITE + "/guides/a"
        lines = self.reading(at(9)) + [self.page(at(9, 0, 2), "/robots.txt", referrer=ref),
                                       self.page(at(9, 0, 3), "/sitemap.xml", referrer=ref)]
        self.assertEqual(self.people(lines), (5, 1, 0))

    def test_an_office_sharing_one_address_and_browser_keeps_its_readers(self):
        lines = self.reading(at(9)) + self.reading(at(9, 5), "/pricing") + [
            self.page(at(9, 6), "/robots.txt"), self.page(at(9, 7), "/about")]
        self.assertEqual(self.people(lines)[1], 1)
        self.assertEqual(self.people(lines)[2], 0)

    def test_robots_txt_on_another_host_does_not_count(self):
        lines = [self.page(at(9), "/robots.txt", host="api.example.com"),
                 self.page(at(9, 1), "/guides/a"), self.page(at(9, 2), "/pricing")]
        self.assertEqual(self.people(lines), (2, 1, 0))

    def test_a_crawler_with_a_couple_of_assets_is_still_a_crawler(self):
        """The audited day's largest crawler session: 99 pages, 2 assets."""
        address = "203.0.113.41"
        lines = [self.page(at(9, 0, i), f"/p{i}", address) for i in range(20)]
        lines += [self.page(at(9, 0, 30), "/_next/static/app.css", address,
                            referrer=self.SITE + "/p1"),
                  self.page(at(9, 1), "/robots.txt", address)]
        self.assertEqual(self.people(lines), (0, 0, 22))


if __name__ == "__main__":
    unittest.main()
