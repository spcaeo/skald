"""Tests for skald. Standard library only: python3 -m unittest.

Every test here exists because the thing it checks was once wrong in a report
that went out. The fixtures in tests/fixtures are hand-built so the expected
numbers can be stated exactly rather than approximately; COUNTING-TRAPS.md
explains what each one is reproducing.

All addresses are in the RFC 5737 documentation ranges (203.0.113.0/24 and
198.51.100.0/24) and the host is example.com. There is no real traffic in
this directory.
"""
from __future__ import annotations

import gzip
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import (Classifier, Group, Tier, check,  # noqa: E402
                          log_files, read, summarise)
from skald.aggregate import GroupStats  # noqa: E402
from skald.parse import PARSERS, Hit, detect  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
GPTBOT = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
          "GPTBot/1.2; +https://openai.com/gptbot")
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
WHEN = datetime(2026, 10, 6, 10, 0, 0, tzinfo=timezone.utc)


def hit(url="/guides/alpha", status="200", method="GET", agent=CHROME,
        referrer="", address="203.0.113.10", when=WHEN, country="US") -> Hit:
    """One request, for the rules that only need one."""
    return Hit(when=when, address=address, host="example.com", method=method,
               url=url, status=status, referrer=referrer, user_agent=agent,
               country=country)


def analyse(fixture: str, our_agents=None, gap=30):
    """Summarise one fixture file the way the command line would."""
    return summarise(
        read([FIXTURES / fixture], "auto"),
        Classifier(our_agents),
        gap,
    )


# --------------------------------------------------------------------- parsing

class TestParsers(unittest.TestCase):
    """Every format in PARSERS must produce the same Hit from the same request.

    Nothing downstream knows which web server wrote the line, so a format that
    silently drops a field - the country in particular - makes a whole card
    disappear with no error anywhere.
    """

    def test_nginx_extended_round_trips_every_field(self):
        line = (
            '2026-10-06T10:00:00+00:00 203.0.113.10 example.com '
            '"GET /guides/alpha?page=2 HTTP/2.0" 200 4096 '
            f'"https://chatgpt.com/" "{CHROME}" 0.004 cc=GB '
            'ray=0000000000000000-LHR'
        )
        got = PARSERS["nginx_extended"](line)
        self.assertIsNotNone(got)
        self.assertEqual(got.when, datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(got.address, "203.0.113.10")
        self.assertEqual(got.host, "example.com")
        self.assertEqual(got.method, "GET")
        self.assertEqual(got.url, "/guides/alpha?page=2")
        self.assertEqual(got.path, "/guides/alpha")
        self.assertEqual(got.status, "200")
        self.assertEqual(got.referrer, "https://chatgpt.com/")
        self.assertEqual(got.user_agent, CHROME)
        self.assertEqual(got.country, "GB")

    def test_nginx_extended_empty_fields_become_empty_strings(self):
        """A dash is nginx for "there was nothing here", not a value."""
        line = ('2026-10-06T10:00:00+00:00 203.0.113.10 example.com '
                '"GET / HTTP/2.0" 200 4096 "-" "-" 0.004 cc=XX ray=x')
        got = PARSERS["nginx_extended"](line)
        self.assertEqual(got.referrer, "")
        self.assertEqual(got.user_agent, "")
        # XX is Cloudflare for "could not tell", so it is not a country.
        self.assertEqual(got.country, "")

    def test_nginx_extended_needs_the_request_time_before_cc(self):
        """The country is read from the position the reference format puts it.

        The pattern allows exactly one field between the user agent and cc=.
        Logging cc= without $request_time in front of it parses, but the
        country is lost rather than reported wrongly. If your log_format has
        no $request_time, put a literal placeholder there - see SOP.md.
        """
        with_rt = ('2026-10-06T10:00:00+00:00 203.0.113.10 example.com '
                   '"GET / HTTP/2.0" 200 4096 "-" "-" 0.004 cc=GB')
        without_rt = ('2026-10-06T10:00:00+00:00 203.0.113.10 example.com '
                      '"GET / HTTP/2.0" 200 4096 "-" "-" cc=GB')
        self.assertEqual(PARSERS["nginx_extended"](with_rt).country, "GB")
        self.assertEqual(PARSERS["nginx_extended"](without_rt).country, "")

    def test_nginx_combined_round_trips(self):
        line = ('203.0.113.11 - - [06/Oct/2026:10:00:00 +0000] '
                '"GET /pricing HTTP/1.1" 200 4096 '
                f'"https://www.perplexity.ai/" "{CHROME}"')
        got = PARSERS["nginx_combined"](line)
        self.assertIsNotNone(got)
        self.assertEqual(got.when, datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(got.address, "203.0.113.11")
        self.assertEqual(got.url, "/pricing")
        self.assertEqual(got.status, "200")
        self.assertEqual(got.referrer, "https://www.perplexity.ai/")
        self.assertEqual(got.user_agent, CHROME)
        # The combined format has no country field, so there is no country.
        self.assertEqual(got.country, "")
        self.assertEqual(got.host, "")

    def test_apache_combined_is_the_same_parser(self):
        self.assertIs(PARSERS["apache_combined"], PARSERS["nginx_combined"])

    def test_caddy_json_round_trips_including_the_country_header(self):
        line = (
            '{"ts":1791280800.0,"request":{"remote_ip":"198.51.100.23",'
            '"host":"example.com","method":"GET","uri":"/docs/intro",'
            '"headers":{"User-Agent":["%s"],"Referer":["https://claude.ai/"],'
            '"Cf-Ipcountry":["GB"]}},"status":200}' % CHROME
        )
        got = PARSERS["caddy_json"](line)
        self.assertIsNotNone(got)
        self.assertEqual(got.when, datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(got.address, "198.51.100.23")
        self.assertEqual(got.host, "example.com")
        self.assertEqual(got.url, "/docs/intro")
        self.assertEqual(got.status, "200")
        self.assertEqual(got.referrer, "https://claude.ai/")
        self.assertEqual(got.user_agent, CHROME)
        self.assertEqual(got.country, "GB")

    def test_caddy_json_returns_none_for_a_line_that_is_not_json(self):
        self.assertIsNone(PARSERS["caddy_json"]("203.0.113.10 - - [06/Oct/2026"))

    def test_detect_prefers_the_format_with_a_country(self):
        """auto picks the richest format that parses, not the first that does."""
        self.assertEqual(detect([
            '2026-10-06T10:00:00+00:00 203.0.113.10 example.com '
            '"GET / HTTP/2.0" 200 4096 "-" "-" 0.004 cc=GB ray=x'
        ]), "nginx_extended")
        self.assertEqual(detect([
            '203.0.113.10 - - [06/Oct/2026:10:00:00 +0000] "GET / HTTP/1.1" '
            f'200 4096 "-" "{CHROME}"'
        ]), "nginx_combined")

    def test_unparsable_lines_are_skipped_not_fatal(self):
        """Logs contain truncated writes. One bad line is not a reason to stop."""
        hits = list(read([FIXTURES / "unparsable.log"], "nginx_extended"))
        self.assertEqual(hits, [])

    def test_reads_gzipped_rotations(self):
        """Rotations past the second are gzipped, and carry most of the history."""
        line = ('2026-10-06T10:00:00+00:00 203.0.113.10 example.com '
                f'"GET / HTTP/2.0" 200 4096 "-" "{CHROME}" 0.004 cc=US ray=x\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log.2.gz"
            with gzip.open(path, "wt") as handle:
                handle.write(line)
            hits = list(read([path], "nginx_extended"))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].path, "/")


class TestLogFiles(unittest.TestCase):
    """Which files a window covers. Two uncompressed files is not two days."""

    def test_days_maps_to_base_plus_rotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in ("access.log", "access.log.1", "access.log.2.gz",
                         "access.log.3.gz", "access.log.4.gz"):
                (directory / name).write_text("")
            self.assertEqual(
                [p.name for p in log_files(directory, "access.log", 1)],
                ["access.log"])
            self.assertEqual(
                [p.name for p in log_files(directory, "access.log", 2)],
                ["access.log", "access.log.1"])
            self.assertEqual(
                [p.name for p in log_files(directory, "access.log", 4)],
                ["access.log", "access.log.1", "access.log.2.gz",
                 "access.log.3.gz"])

    def test_missing_rotations_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "access.log").write_text("")
            self.assertEqual(
                [p.name for p in log_files(directory, "access.log", 14)],
                ["access.log"])


# ---------------------------------------------------------------- what a page is

class TestPageViews(unittest.TestCase):
    """Hit.is_page decides what "someone read a page" means.

    This is the property that turned one visitor into "56 people" when it did
    not exist. A page is something a person could look at; everything a
    browser fetches on their behalf is not.
    """

    def test_a_plain_html_get_is_a_page(self):
        self.assertTrue(hit(url="/guides/alpha").is_page)
        self.assertTrue(hit(url="/guides/alpha?page=2").is_page)
        self.assertTrue(hit(url="/", method="HEAD").is_page)

    def test_framework_payload_fetches_are_not_pages(self):
        """?_rsc= is Next.js fetching the page you clicked. One click, one row."""
        self.assertFalse(hit(url="/guides/alpha?_rsc=1f3ab").is_page)
        self.assertFalse(hit(url="/guides/alpha?page=2&_rsc=1f3ab").is_page)
        self.assertFalse(hit(url="/guides/alpha?_data=routes%2Findex").is_page)

    def test_assets_are_not_pages(self):
        for url in ("/_next/static/chunks/main-7c1d.js",
                    "/static/app.css",
                    "/assets/hero.webp",
                    "/images/logo.svg",
                    "/favicon.ico",
                    "/fonts/inter-latin.woff2",
                    "/sitemap.xml",
                    "/robots.txt"):
            with self.subTest(url=url):
                self.assertFalse(hit(url=url).is_page)

    def test_analytics_beacons_are_not_pages(self):
        """A beacon is evidence of a visit, never a visit of its own."""
        for url in ("/api/events", "/api/analytics", "/collect", "/beacon"):
            with self.subTest(url=url):
                self.assertFalse(hit(url=url).is_page)
                self.assertFalse(hit(url=url, method="POST").is_page)

    def test_only_a_two_hundred_or_a_304_is_a_page(self):
        """A 301 is not read, and the page it lands on is logged separately.

        Counting the redirect as well counts that one read twice. On the
        reference log this was 3,993 of 15,727 claimed views. A 304 is no
        redirect: the browser shows its cached copy, a page read.
        """
        self.assertTrue(hit(status="200").is_page)
        self.assertTrue(hit(status="206").is_page)
        self.assertTrue(hit(status="304").is_page)
        for status in ("301", "302", "308", "404", "410", "500"):
            with self.subTest(status=status):
                self.assertFalse(hit(status=status).is_page)

    def test_only_a_read_method_is_a_page(self):
        for method in ("POST", "PUT", "DELETE", "PATCH", "OPTIONS"):
            with self.subTest(method=method):
                self.assertFalse(hit(method=method).is_page)

    def test_ok_still_means_answered_without_an_error(self):
        """ok is broader than is_page on purpose: a 301 was answered."""
        self.assertTrue(hit(status="200").ok)
        self.assertTrue(hit(status="301").ok)
        self.assertFalse(hit(status="404").ok)


# ----------------------------------------------------------------- classifying

class TestClassifier(unittest.TestCase):
    """Order of the rules, which is where the old report's sums went wrong."""

    def setUp(self):
        self.classify = Classifier(["MyCompanyCrawler"], ["tool.example.net"])

    def test_a_browser_with_nothing_else_is_a_person(self):
        verdict = self.classify(hit())
        self.assertIs(verdict.group, Group.PEOPLE)
        self.assertIsNone(verdict.tier)

    def test_a_scanner_sending_a_browser_user_agent_is_a_bot(self):
        """probe sits above people: a Chrome string is not a reader.

        /_ignition/execute-solution is a Laravel remote-code-execution probe.
        It was counted as a person for 28 requests in a real log because it
        sends a Chrome user agent and no pattern matched the path.
        """
        verdict = self.classify(hit(url="/_ignition/execute-solution",
                                    status="404"))
        self.assertIs(verdict.group, Group.BOTS)
        self.assertTrue(verdict.probe)

    def test_more_scanner_paths_that_send_browser_user_agents(self):
        for url in ("/.env", "/wp-login.php", "/.git/config",
                    "/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php",
                    "/actuator/env", "/.aws/credentials"):
            with self.subTest(url=url):
                verdict = self.classify(hit(url=url, status="404"))
                self.assertIs(verdict.group, Group.BOTS)
                self.assertTrue(verdict.probe)

    def test_an_engine_asking_for_a_probe_path_stays_an_engine(self):
        """probe sits below the named engines, and that is deliberate.

        Filing this under scanners removes it from the engine group total
        while the tier counters still see it. That is exactly how the old
        report's tiers ended up 82 higher than their own group.
        """
        verdict = self.classify(hit(url="/wp-login.php", status="404",
                                    agent=GPTBOT))
        self.assertIs(verdict.group, Group.ANSWER_ENGINE)
        self.assertIs(verdict.tier, Tier.TRAINING)
        self.assertTrue(verdict.probe)

    def test_asked_wins_over_training_for_the_same_request(self):
        """Both lists can match one agent. "Someone is waiting" is the fact
        worth reporting, so AI_ASKED is tested first."""
        asked = self.classify(hit(agent="Mozilla/5.0 (compatible; ChatGPT-User/1.0)"))
        self.assertIs(asked.group, Group.ANSWER_ENGINE)
        self.assertIs(asked.tier, Tier.ASKED)
        training = self.classify(hit(agent=GPTBOT))
        self.assertIs(training.tier, Tier.TRAINING)

    def test_search_crawlers_are_not_filed_under_bots(self):
        verdict = self.classify(hit(agent=GOOGLEBOT))
        self.assertIs(verdict.group, Group.SEARCH_ENGINE)
        self.assertEqual(verdict.engine, "Googlebot")

    def test_google_extended_is_not_a_user_agent_and_applebot_is_split(self):
        """Google-Extended is a robots.txt token: no request carries it, so a
        "user agent" claiming it is not an assistant. Applebot indexes,
        Applebot-Extended trains."""
        self.assertIsNot(self.classify(hit(agent="Google-Extended")).group,
                         Group.ANSWER_ENGINE)
        self.assertIs(self.classify(hit(agent="Mozilla/5.0 (compatible; Applebot/0.1)")).group,
                      Group.SEARCH_ENGINE)
        self.assertIs(self.classify(hit(agent="Applebot-Extended")).group,
                      Group.ANSWER_ENGINE)

    def test_a_citation_click_is_a_person_not_a_crawler(self):
        """The person stays in PEOPLE and the citation is a property of them.

        Adding them to the answer-engine group as well is double counting, and
        is how the old report's tiers over-summed by 56.
        """
        verdict = self.classify(hit(referrer="https://chatgpt.com/"))
        self.assertIs(verdict.group, Group.PEOPLE)
        self.assertIs(verdict.tier, Tier.CITED)
        self.assertEqual(verdict.engine, "chatgpt.com")

    def test_a_tagged_link_counts_as_a_citation_without_a_referrer(self):
        verdict = self.classify(hit(url="/guides/alpha?utm_source=perplexity"))
        self.assertIs(verdict.group, Group.PEOPLE)
        self.assertIs(verdict.tier, Tier.CITED)
        self.assertEqual(verdict.engine, "perplexity.ai")

    def test_an_ordinary_google_referrer_is_not_a_citation(self):
        """An AI Overview click is indistinguishable from a search click."""
        verdict = self.classify(hit(referrer="https://www.google.com/"))
        self.assertIs(verdict.group, Group.PEOPLE)
        self.assertIsNone(verdict.tier)

    def test_libraries_monitors_and_unfurlers_are_bots(self):
        for agent in ("curl/8.7.1", "python-requests/2.32.3", "Go-http-client/2.0",
                      "Mozilla/5.0 (compatible; AhrefsBot/7.0)", "UptimeRobot/2.0",
                      "WhatsApp/2.24", "node-fetch/1.0"):
            with self.subTest(agent=agent):
                self.assertIs(self.classify(hit(agent=agent)).group, Group.BOTS)

    def test_no_user_agent_at_all_is_a_bot(self):
        self.assertIs(self.classify(hit(agent="")).group, Group.BOTS)

    def test_our_own_traffic_is_neither_people_nor_bots(self):
        self.assertIs(self.classify(hit(agent="MyCompanyCrawler/1.0")).group,
                      Group.OURS)
        self.assertIs(self.classify(hit(referrer="https://tool.example.net/x")).group,
                      Group.OURS)

    def test_our_own_traffic_wins_over_a_citation_referrer(self):
        """Ours is first for a reason: it would otherwise inflate the number
        that matters most."""
        verdict = self.classify(hit(agent="MyCompanyCrawler/1.0",
                                    referrer="https://chatgpt.com/"))
        self.assertIs(verdict.group, Group.OURS)

    def test_an_empty_config_matches_nothing(self):
        """No "ours" patterns must not mean every request is ours."""
        bare = Classifier(None, None)
        self.assertIs(bare(hit()).group, Group.PEOPLE)
        self.assertIs(bare(hit(agent="MyCompanyCrawler/1.0")).group, Group.BOTS)


# ------------------------------------------------------------------ aggregating

class TestOneSessionTrap(unittest.TestCase):
    """The failure this package was built to stop.

    tests/fixtures/one_session.log is one address, one browser, fifty-one
    seconds: 21 ?_rsc= payload fetches, 26 assets, 8 analytics beacons, every
    one carrying the same chatgpt.com referrer, and not a single HTML page
    among them. The report this replaces called it "56 people".
    """

    def setUp(self):
        self.totals = analyse("one_session.log")
        self.people = self.totals.groups[Group.PEOPLE]

    def test_the_whole_file_is_one_visitor(self):
        self.assertEqual(self.totals.parsed, 55)
        self.assertEqual(self.people.hits, 55)
        self.assertEqual(self.people.visits, 1)

    def test_citations_are_counted_once_per_visitor(self):
        self.assertEqual(self.people.cited_visits, 1)
        self.assertEqual(dict(self.people.cited_by), {"chatgpt.com": 1})

    def test_counting_requests_instead_would_have_said_fifty_five(self):
        """The naive count, written out, so the gap is visible in a test."""
        classify = Classifier()
        per_request = sum(
            1 for h in read([FIXTURES / "one_session.log"], "auto")
            if classify(h).tier is Tier.CITED
        )
        self.assertEqual(per_request, 55)
        self.assertEqual(self.people.cited_visits, 1)

    def test_nobody_read_a_page(self):
        """55 requests, zero views. A citation with no page view is a session
        that bounced, or a client-side navigation whose HTML came from a cache.
        Either way it is not 55 readers."""
        self.assertEqual(self.people.views, 0)

    def test_a_second_visitor_after_the_gap_is_a_second_visit(self):
        """The fix must not go the other way and collapse real visitors."""
        classify = Classifier()
        later = WHEN + timedelta(hours=2)
        hits = [
            hit(referrer="https://chatgpt.com/"),
            hit(referrer="https://chatgpt.com/", when=WHEN + timedelta(seconds=10)),
            hit(referrer="https://chatgpt.com/", when=later),
            hit(referrer="https://chatgpt.com/", address="203.0.113.99"),
        ]
        people = summarise(hits, classify, 30).groups[Group.PEOPLE]
        self.assertEqual(people.hits, 4)
        self.assertEqual(people.cited_visits, 3)

    def test_the_figures_reconcile(self):
        self.assertEqual(check(self.totals), [])


class TestMixedLog(unittest.TestCase):
    """The five groups against a file whose composition is known line by line."""

    def setUp(self):
        self.totals = analyse("mixed_extended.log", ["MyCompanyCrawler"])

    def test_groups_add_up_to_the_log_exactly(self):
        """The invariant. Not "roughly": exactly."""
        summed = sum(s.hits for s in self.totals.groups.values())
        self.assertEqual(self.totals.parsed, 16)
        self.assertEqual(summed, self.totals.hits)
        self.assertEqual(check(self.totals), [])

    def test_every_group_holds_what_it_should(self):
        counts = {g.value: s.hits for g, s in self.totals.groups.items()}
        self.assertEqual(counts, {"people": 6, "answer_engines": 4,
                                  "search_engines": 1, "bots": 4, "ours": 1})

    def test_tiers_partition_the_answer_engine_group(self):
        engines = self.totals.groups[Group.ANSWER_ENGINE]
        # OAI-SearchBot indexes ahead of any question, so it is training too.
        self.assertEqual(dict(engines.tiers), {"training": 4})
        self.assertEqual(sum(engines.tiers.values()), engines.hits)
        self.assertEqual(dict(engines.engines), {"GPTBot": 3, "OAI-SearchBot": 1})

    def test_a_citation_click_is_not_in_the_engine_tiers(self):
        """Cited is on the people card. It is a person, counted once."""
        engines = self.totals.groups[Group.ANSWER_ENGINE]
        self.assertNotIn("cited", engines.tiers)
        self.assertEqual(self.totals.groups[Group.PEOPLE].cited_visits, 1)

    def test_a_probing_engine_is_counted_in_both_its_group_and_the_probes(self):
        engines = self.totals.groups[Group.ANSWER_ENGINE]
        self.assertEqual(engines.probes, 1)
        self.assertLessEqual(engines.probes, engines.hits)

    def test_views_exclude_payloads_assets_and_redirects(self):
        people = self.totals.groups[Group.PEOPLE]
        self.assertEqual(people.hits, 6)
        # /, /pricing and /guides/alpha. Not the two ?_rsc= fetches, and not
        # the 301 on /guides.
        self.assertEqual(people.views, 3)
        self.assertEqual(sorted(people.pages), ["/", "/guides/alpha", "/pricing"])

    def test_visits_are_sessions_not_addresses_or_requests(self):
        people = self.totals.groups[Group.PEOPLE]
        # Three addresses, four visits: 203.0.113.10's /pricing came from
        # google.com after a direct first page, so it starts a visit of its own.
        self.assertEqual(people.visits, 4)
        self.assertLess(people.visits, people.hits)

    def test_countries_come_from_the_logged_header(self):
        people = self.totals.groups[Group.PEOPLE]
        self.assertEqual(dict(people.countries), {"US": 3, "GB": 1})

    def test_scanners_are_counted_whatever_agent_they_send(self):
        bots = self.totals.groups[Group.BOTS]
        self.assertEqual(bots.hits, 4)
        self.assertEqual(bots.probes, 2)
        # The two that are not probes: curl, and one with no user agent.
        self.assertEqual(sorted(bots.agents), ["(no user agent)", "curl"])

    def test_the_window_is_the_first_and_last_hit(self):
        self.assertEqual(self.totals.first,
                         datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(self.totals.last,
                         datetime(2026, 10, 6, 10, 2, 20, tzinfo=timezone.utc))


class TestOtherFormatsEndToEnd(unittest.TestCase):
    """auto-detection and the whole pipeline, per format."""

    def test_combined_format_file(self):
        totals = analyse("combined.log")
        self.assertEqual(totals.parsed, 3)
        self.assertEqual(sum(s.hits for s in totals.groups.values()), 3)
        self.assertEqual(totals.groups[Group.PEOPLE].cited_visits, 1)
        self.assertEqual(dict(totals.groups[Group.PEOPLE].cited_by),
                         {"perplexity.ai": 1})
        self.assertEqual(totals.groups[Group.BOTS].probes, 1)
        # No country field in this format, so no country is claimed.
        self.assertEqual(dict(totals.groups[Group.PEOPLE].countries), {})
        self.assertEqual(check(totals), [])

    def test_caddy_json_file(self):
        totals = analyse("caddy.jsonl")
        self.assertEqual(totals.parsed, 2)
        self.assertEqual(dict(totals.groups[Group.PEOPLE].countries), {"GB": 1})
        self.assertEqual(dict(totals.groups[Group.PEOPLE].cited_by),
                         {"claude.ai": 1})
        # PerplexityBot builds Perplexity's index ahead of any question.
        self.assertEqual(dict(totals.groups[Group.ANSWER_ENGINE].tiers),
                         {"training": 1})
        self.assertEqual(check(totals), [])


# ---------------------------------------------------------------------- verify

class TestVerify(unittest.TestCase):
    """The checks that refuse to send. Each one maps to a real bad report."""

    def setUp(self):
        self.totals = analyse("mixed_extended.log", ["MyCompanyCrawler"])

    def test_a_clean_run_has_no_problems(self):
        self.assertEqual(check(self.totals), [])

    def test_categories_that_do_not_sum_are_caught(self):
        """The 51,763-against-55,539 failure: a 3,776 gap, 7% of the total,
        because only three of six buckets were shown and nothing subtracted.

        Simulated the way it actually happened - a category losing requests
        under a total that stayed right - rather than by inflating the total,
        which is a state the parser cannot produce and which would also trip
        the host-filter check.
        """
        # A hit landing in two groups, which is one of the two ways the real
        # gap arose. Chosen over shrinking a group or inflating the total:
        # either of those also breaks a group's own sub-invariants, or claims
        # more hits than lines were read, and then one defect reports as
        # several and the real one is buried.
        self.totals.groups[Group.BOTS].hits += 3
        # A request counted twice is counted twice everywhere, its status too.
        self.totals.groups[Group.BOTS].statuses["2xx"] += 3
        _count_twice_by_hour(self.totals, Group.BOTS, 3)
        problems = check(self.totals)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].what, "groups do not sum")
        # The message states both sides, so the reader can see which moved.
        self.assertIn("across 5 groups", str(problems[0]))
        self.assertIn("16", str(problems[0]))

    def test_a_group_dropped_from_the_report_is_caught(self):
        """Same failure from the other direction: a bucket going missing."""
        del self.totals.groups[Group.BOTS]
        problems = check(self.totals)
        self.assertTrue(any(p.what == "groups do not sum" for p in problems))

    def test_tiers_that_over_sum_are_caught(self):
        """The 34,495-against-34,357 failure: tiers 138 over their own group,
        from counting probes in the tiers and citations in the crawler group."""
        self.totals.groups[Group.ANSWER_ENGINE].tiers["cited"] = 138
        problems = check(self.totals)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].what, "answer-engine tiers do not sum")
        self.assertIn("+138", str(problems[0]))

    def test_citations_counted_per_request_again_are_caught(self):
        """The check that would have caught "56 people followed a citation"."""
        people = self.totals.groups[Group.PEOPLE]
        people.cited_visits = people.visits + 1
        problems = check(self.totals)
        self.assertEqual(len(problems), 1)
        self.assertEqual(problems[0].what, "more citations than visits")

    def test_a_child_cannot_exceed_its_parent(self):
        for field, what in (("views", "more views than hits"),
                            ("visits", "more visits than hits"),
                            ("probes", "more probes than hits")):
            with self.subTest(field=field):
                totals = analyse("mixed_extended.log", ["MyCompanyCrawler"])
                stats = totals.groups[Group.PEOPLE]
                setattr(stats, field, stats.hits + 1)
                problems = check(totals)
                self.assertTrue(any(p.what.endswith(what) for p in problems),
                                [str(p) for p in problems])

    def test_an_empty_parse_is_a_problem_not_a_calm_zero(self):
        """A wrong log format gives every card a confident zero."""
        totals = analyse("unparsable.log")
        self.assertEqual(totals.parsed, 0)
        problems = check(totals)
        self.assertEqual([p.what for p in problems], ["nothing parsed"])

    def test_report_or_die_raises_on_a_bad_report(self):
        from skald import report_or_die
        self.assertEqual(report_or_die(self.totals), [])
        self.totals.groups[Group.PEOPLE].hits += 1
        self.totals.groups[Group.PEOPLE].statuses["2xx"] += 1
        _count_twice_by_hour(self.totals, Group.PEOPLE, 1)
        with self.assertRaises(AssertionError) as raised:
            report_or_die(self.totals)
        self.assertIn("do not reconcile", str(raised.exception))
        self.assertEqual(len(report_or_die(self.totals, strict=False)), 1)


def _count_twice_by_hour(totals, group, n):
    """A request counted twice is counted twice in its hour too (extras.py)."""
    hour = next(iter(totals.extras["hourly"]))
    totals.extras["hourly"][hour][group.value] += n
    totals.extras["ours"]["hours"][hour]["requests"] += n
    utc = totals.extras.get("hourly_utc")
    if utc:                                  # and in its UTC hour
        utc[next(iter(utc))][group.value] += n
    names = ((totals.extras.get("crawler_cost") or {}).get("groups") or {}).get(group.value)
    if names:                                # and by its crawler's name (crawler_cost.py)
        entry = next(iter(names.values()))
        entry["requests"] += n
        for key in ("status", "pages", "countries", "agents"):
            if entry.get(key):
                entry[key][next(iter(entry[key]))] += n


# ---------------------------------------------------------------------- render

class TestRendering(unittest.TestCase):
    """Both renderers read the same Totals, so they cannot print different
    numbers. They used to be built separately, and they drifted."""

    def setUp(self):
        self.totals = analyse("mixed_extended.log", ["MyCompanyCrawler"])
        self.cards = [Group.PEOPLE, Group.ANSWER_ENGINE, Group.SEARCH_ENGINE,
                      Group.BOTS, Group.OURS]

    def test_text_states_the_counts_it_was_given(self):
        from skald import as_text
        out = as_text(self.totals, self.cards)
        self.assertIn("16  requests reached the server", out)
        # 203.0.113.10 opens / directly, then /pricing from google.com: two
        # visits by the source rule (SOP.md, "What a visit is").
        self.assertIn("3 visits that read at least one page", out)
        self.assertIn("4 browser sessions in all, 1 without a page view", out)
        self.assertIn("1 arrived by following a citation", out)

    def test_html_is_self_contained_and_has_no_remote_references(self):
        from skald import as_html
        page = as_html(self.totals, self.cards, "Traffic report")
        self.assertTrue(page.startswith("<!doctype html>"))
        for forbidden in ("<img", "src=", "<link", "googleapis", "http://", "https://"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, page)

    def test_html_and_text_agree_on_the_citation_count(self):
        from skald import as_html, as_text
        self.assertIn("1", as_text(self.totals, self.cards))
        page = as_html(self.totals, self.cards, "Traffic report")
        self.assertIn("counted once per visitor", page)
        self.assertIn("not measurable", page)  # the AI Overview caveat

    def test_a_group_with_no_hits_renders_no_card(self):
        from skald import as_text
        totals = analyse("caddy.jsonl")
        out = as_text(totals, self.cards)
        self.assertNotIn("BOTS AND SCANNERS", out)

    def test_an_empty_group_does_not_divide_by_zero(self):
        from skald import as_html, as_text
        totals = analyse("mixed_extended.log", ["MyCompanyCrawler"])
        totals.groups[Group.BOTS] = GroupStats(hits=1)
        totals.hits = sum(s.hits for s in totals.groups.values())
        as_text(totals, self.cards)
        as_html(totals, self.cards, "Traffic report")


class TestCommandLine(unittest.TestCase):
    """The command line, run as a user runs it.

    The exit code is the whole point of --check: it is what a cron job or a
    send script tests before it mails anything.
    """

    ROOT = Path(__file__).resolve().parent.parent

    def run_cli(self, *args, env_extra=None):
        env = dict(os.environ)
        env.update(env_extra or {})
        return subprocess.run(
            [sys.executable, str(self.ROOT / "report.py"), *args],
            cwd=self.ROOT, capture_output=True, text=True, env=env, timeout=120,
        )

    def test_check_exits_zero_when_the_figures_reconcile(self):
        done = self.run_cli("--config", "config.example.yml",
                            "--log", "tests/fixtures/mixed_extended.log",
                            "--check")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("16 requests, every category reconciles", done.stdout)

    def test_check_exits_one_when_nothing_parsed(self):
        done = self.run_cli("--config", "config.example.yml",
                            "--log", "tests/fixtures/unparsable.log",
                            "--check")
        self.assertEqual(done.returncode, 1)
        self.assertIn("FIGURES DO NOT RECONCILE", done.stderr)
        self.assertIn("nothing parsed", done.stderr)

    def test_a_log_directory_with_nothing_in_it_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "config.yml"
            config.write_text(f"logs:\n  dir: {tmp}\n  base: access.log\n")
            done = self.run_cli("--config", str(config))
        self.assertEqual(done.returncode, 2)
        self.assertIn("no log files found", done.stderr)

    def test_a_misspelled_log_path_fails_loudly(self):
        """It is not the tidy message above - --log is taken at its word and
        the open fails - but it is non-zero and it is not a calm zero."""
        done = self.run_cli("--config", "config.example.yml",
                            "--log", "tests/fixtures/not-a-file.log")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("FileNotFoundError", done.stderr)

    def test_html_goes_to_stdout_or_a_named_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.html"
            done = self.run_cli("--config", "config.example.yml",
                                "--log", "tests/fixtures/mixed_extended.log",
                                "--html", str(out))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue(out.read_text().startswith("<!doctype html>"))

    def test_it_runs_with_no_pyyaml_installed(self):
        """PyYAML is optional, so the fallback parser has to handle the
        config that ships with the package. It did not: "hosts:" opening a
        block list left a dict that the next line tried to append to."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "yaml.py").write_text(
                'raise ImportError("PyYAML hidden for this test")\n')
            done = self.run_cli("--config", "config.example.yml",
                                "--log", "tests/fixtures/mixed_extended.log",
                                "--check", env_extra={"PYTHONPATH": tmp})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("every category reconciles", done.stdout)

    def test_the_fallback_parser_agrees_with_the_example_config(self):
        spec = importlib.util.spec_from_file_location(
            "skald_cli", self.ROOT / "report.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        parsed = cli._tiny_yaml((self.ROOT / "config.example.yml").read_text())
        self.assertEqual(parsed["site"]["hosts"],
                         ["example.com", "www.example.com"])
        self.assertEqual(parsed["ours"]["user_agents"],
                         ["MyCompanyCrawler", "MyCompany-e2e",
                          {"agent": "acme-server-audit", "label": "server audit"}])
        self.assertEqual(parsed["ours"]["referrers"], [])
        self.assertEqual(parsed["report"]["cards"],
                         ["people", "answer_engines", "search_engines",
                          "bots", "ours"])
        # Numbers come back as strings; every caller wraps them in int().
        self.assertEqual(int(parsed["logs"]["days"]), 2)
        self.assertEqual(int(parsed["report"]["session_gap_minutes"]), 30)


if __name__ == "__main__":
    unittest.main()
