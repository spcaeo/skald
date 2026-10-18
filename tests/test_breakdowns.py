"""Breakdowns: readers by country, browser, system, device, source, campaign,
landing page and hour; requests by status; 404s, 5xx, speed and posts.

The rule under test is the package's own: each breakdown adds up to the
figure it breaks down, a day where one does not is withheld, history keeps
labels only (never an address, agent or referrer URL), and a period that
includes a day collected before the breakdowns shows none rather than a
partial sum.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, check, countries, dashboard, dimensions as dim  # noqa: E402
from skald.aggregate import READER_DIMS  # noqa: E402
from skald.parse import PARSERS  # noqa: E402
from skald.store import SCHEMA_VERSION, History  # noqa: E402

from support import (CHROME, GPTBOT, NY, UTC, Sandbox, day_lines, line,  # noqa: E402
                     totals_for)

IPHONE_SAFARI = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
                 "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1")
LINKEDIN_APP = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
                "(KHTML, like Gecko) Mobile/15E148 [LinkedInApp]/9.31")
SAMSUNG_TABLET = ("Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 (KHTML, like "
                  "Gecko) SamsungBrowser/26.0 Chrome/122.0.0.0 Safari/537.36")
EDGE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0")
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0"
CHROMEBOOK = ("Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like "
              "Gecko) Chrome/154.0.0.0 Safari/537.36")
FB_ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 (KHTML, like "
              "Gecko) Version/4.0 Chrome/154.0 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/480.0;]")

DAY = date(2026, 10, 5)


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def mixed() -> list[str]:
    """Eight readers on different browsers, devices and sources, plus a
    browser session that read nothing, a 404, a 5xx, a slow page, a post,
    and the usual machines from day_lines."""
    out = day_lines(DAY, 2)
    out += [
        line(at(13, 0), "203.0.113.30", "/pricing/", IPHONE_SAFARI, "https://www.google.com/",
             country="CA"),
        line(at(13, 1), "203.0.113.31", "/?utm_source=LinkedIn&utm_medium=social&utm_campaign=Launch",
             LINKEDIN_APP, country="CA"),
        line(at(13, 2), "203.0.113.32", "/guides/alpha", SAMSUNG_TABLET,
             "https://news.example.org/story", country="DE"),
        line(at(14, 0), "203.0.113.33", "/", EDGE, "https://mail.google.com/", country="-"),
        line(at(14, 1), "203.0.113.34", "/?gclid=abc", FIREFOX_LINUX, country="FR"),
        line(at(15, 0), "203.0.113.35", "/guides/beta", CHROMEBOOK, "https://example.com/",
             country="US"),
        line(at(15, 1), "203.0.113.36", "/", FB_ANDROID, "https://l.facebook.com/", country="BR"),
        # a browser that only fetched an asset: a session, not a reader
        line(at(16, 0), "203.0.113.37", "/_next/static/app.js", CHROME),
        # a person meets a 404, the server errors on someone, a post
        line(at(13, 10), "203.0.113.30", "/old-page", IPHONE_SAFARI, status=404, country="CA"),
        line(at(16, 2), "198.51.100.60", "/api/boom", GPTBOT, status=502),
    ]
    post = (f'{at(14, 10).isoformat()} 203.0.113.33 example.com "POST /contact HTTP/2.0" '
            f'303 0 "https://example.com/contact" "{EDGE}" 0.120 cc=US ray=-\n')
    slow = (f'{at(15, 5).isoformat()} 203.0.113.35 example.com "GET /guides/slow HTTP/2.0" '
            f'200 900 "https://example.com/" "{CHROMEBOOK}" 2.400 cc=US ray=-\n')
    return out + [post, slow]


class TestLabels(unittest.TestCase):

    def test_browsers_systems_and_devices(self):
        cases = {
            CHROME: ("Chrome", "macOS", "Desktop"),
            IPHONE_SAFARI: ("Safari", "iOS", "Mobile"),
            LINKEDIN_APP: ("LinkedIn app", "iOS", "Mobile"),
            SAMSUNG_TABLET: ("Samsung Internet", "Android", "Tablet"),
            EDGE: ("Edge", "Windows", "Desktop"),
            FIREFOX_LINUX: ("Firefox", "Linux", "Desktop"),
            CHROMEBOOK: ("Chrome", "ChromeOS", "Desktop"),
            FB_ANDROID: ("Facebook app", "Android", "Mobile"),
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Mobile/15E148": ("In-app browser (iOS)", "iOS", "Mobile"),
            "Opera/9.80 (Windows NT 6.1) Presto/2.12": ("Opera", "Windows", "Desktop"),
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) GSA/390.0 Mobile/15E148 Safari/604.1":
                ("Google app", "iOS", "Mobile"),
        }
        for agent, want in cases.items():
            with self.subTest(agent=agent[:50]):
                self.assertEqual(dim.agent_labels(agent), want)

    def test_sources(self):
        own = {"example.com", "www.example.com"}
        self.assertEqual(dim.source_type("https://chatgpt.com/", "/", True, own), "AI assistant")
        self.assertEqual(dim.source_type("https://www.google.ca/", "/", False, own), "Search engine")
        self.assertEqual(dim.source_type("https://www.bing.com/search?q=x", "/", False, own),
                         "Search engine")
        self.assertEqual(dim.source_type("https://lnkd.in/abc", "/", False, own), "Social media")
        self.assertEqual(dim.source_type("android-app://com.linkedin.android/", "/", False, own),
                         "Social media")
        self.assertEqual(dim.source_type("https://outlook.live.com/", "/", False, own), "Email")
        self.assertEqual(dim.source_type("https://www.example.com/a", "/", False, own), "This site")
        self.assertEqual(dim.source_type("https://other.example.org/", "/", False, own),
                         "Other website")
        self.assertEqual(dim.source_type("", "/?utm_source=newsletter", False, own), "Email")
        self.assertEqual(dim.source_type("", "/?utm_source=partner", False, own), "Tagged link")
        self.assertEqual(dim.source_type("", "/?gclid=1", False, own), "Search engine")
        self.assertEqual(dim.source_type("", "/", False, own), "Direct or unknown")

    def test_campaigns_and_click_ids(self):
        self.assertEqual(dim.campaign("/?utm_source=LinkedIn&utm_campaign=Q4"),
                         "linkedin / - / q4")
        self.assertEqual(dim.campaign("/?gclid=xyz"), "google / cpc / (gclid)")
        self.assertEqual(dim.campaign("/pricing/"), dim.NO_CAMPAIGN)

    def test_country_labels(self):
        self.assertEqual(countries.label("CA"), "\U0001F1E8\U0001F1E6 Canada")
        self.assertEqual(countries.label("Unknown"), "Not recorded")
        self.assertEqual(countries.label(""), "Not recorded")
        self.assertEqual(countries.label(dim.OTHER), dim.OTHER)
        self.assertEqual(countries.flag("1x"), "")

    def test_fold_keeps_the_total(self):
        counter = Counter({f"/p{i}": i + 1 for i in range(60)})
        folded = dim.fold(counter, 50)
        self.assertEqual(len(folded), 50)
        self.assertEqual(sum(folded.values()), sum(counter.values()))
        self.assertIn(dim.OTHER, folded)

    def test_request_time_is_read_and_junk_is_none(self):
        parse = PARSERS["nginx_extended"]
        hit = parse(line(at(9), status=200))
        self.assertAlmostEqual(hit.request_time, 0.004)
        no_time = parse(f'{at(9).isoformat()} 203.0.113.1 example.com "GET / HTTP/1.1" '
                        f'200 1 "-" "{CHROME}" cc=US ray=-\n')
        self.assertIsNone(no_time.request_time)


class TestTallies(unittest.TestCase):

    def setUp(self):
        self.totals = totals_for(mixed())
        self.people = self.totals.groups[Group.PEOPLE]

    def test_every_breakdown_adds_up_to_the_readers(self):
        self.assertEqual(check(self.totals), [])
        self.assertEqual(self.people.readers, 9)
        self.assertEqual(self.people.visits, 10)
        for name in READER_DIMS:
            with self.subTest(dimension=name):
                self.assertEqual(sum(self.people.by[name].values()), self.people.readers)

    def test_the_labels(self):
        by = self.people.by
        self.assertEqual(by["country"]["CA"], 2)
        self.assertEqual(by["country"]["Unknown"], 1)
        self.assertEqual(by["device"], Counter({"Desktop": 5, "Mobile": 3, "Tablet": 1}))
        self.assertEqual(by["source"]["AI assistant"], 1)
        self.assertEqual(by["source"]["Search engine"], 2)   # google, gclid
        self.assertEqual(by["source"]["Social media"], 2)    # utm linkedin, facebook
        self.assertEqual(by["source"]["Email"], 1)
        self.assertEqual(by["source"]["This site"], 1)
        self.assertEqual(by["source"]["Other website"], 1)
        self.assertEqual(by["referrer"]["news.example.org"], 1)
        self.assertEqual(by["referrer"]["(this site)"], 1)
        self.assertEqual(by["campaign"]["linkedin / social / launch"], 1)
        self.assertEqual(by["hour"]["13"], 3)

    def test_status_404_5xx_speed_and_posts(self):
        self.assertEqual(self.people.statuses["404"], 1)
        self.assertEqual(dict(self.people.not_found), {"/old-page": 1})
        self.assertEqual(self.totals.groups[Group.ANSWER_ENGINE].statuses["5xx"], 1)
        self.assertEqual(dict(self.totals.server_errors), {"/api/boom": 1})
        self.assertEqual(self.people.posts, 1)
        self.assertEqual(dict(self.people.post_pages), {"/contact": 1})
        self.assertEqual(self.people.speeds["1 to 3 s"], 1)
        self.assertEqual(dict(self.people.slow_pages), {"/guides/slow": 1})
        for g, stats in self.totals.groups.items():
            self.assertEqual(sum(stats.statuses.values()), stats.hits, g)

    def test_hours_are_in_the_report_zone(self):
        from skald import Classifier, read, summarise
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(mixed()))
            ny = summarise(read([path]), Classifier(), 30, top=50,
                           hosts=["example.com"], tz=NY)
        self.assertEqual(ny.groups[Group.PEOPLE].by["hour"]["09"], 3)   # 13 UTC

    def test_a_breakdown_that_does_not_add_up_is_caught(self):
        self.people.by["browser"]["Chrome"] += 1
        problems = check(self.totals)
        self.assertEqual([p.what for p in problems], ["readers by browser does not sum"])
        self.totals.groups[Group.BOTS].statuses["2xx"] += 1
        self.assertIn("bots: requests by status does not sum",
                      [p.what for p in check(self.totals)])


class TestHistory(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.history = History(Path(self._tmp.name) / "h.sqlite")
        self.history.record("example.com", DAY, totals_for(mixed()), "UTC", [])
        self.history.record("example.com", DAY + timedelta(days=1),
                            totals_for(day_lines(DAY + timedelta(days=1), 4)), "UTC", [])

    def tearDown(self):
        self.history.close()
        self._tmp.cleanup()

    def test_a_period_rebuilds_the_breakdowns_and_they_verify(self):
        period = self.history.period("example.com", DAY, DAY + timedelta(days=1))
        totals = period.totals
        self.assertTrue(totals.breakdowns)
        self.assertEqual(check(totals), [])
        people = totals.groups[Group.PEOPLE]
        self.assertEqual(people.readers, 13)
        self.assertEqual(sum(people.by["country"].values()), 13)
        self.assertEqual(people.posts, 1)

    def test_a_day_from_before_the_breakdowns_turns_them_off_for_the_period(self):
        self.history.db.execute("UPDATE days SET breakdowns = NULL WHERE day = ?",
                                (DAY.isoformat(),))
        period = self.history.period("example.com", DAY, DAY + timedelta(days=1))
        self.assertFalse(period.totals.breakdowns)
        self.assertEqual(period.unmeasured_breakdowns, [DAY])
        self.assertEqual(period.totals.groups[Group.PEOPLE].by, {})
        self.assertEqual(check(period.totals), [])
        page = dashboard.render(self.history, "example.com", UTC,
                                datetime(2026, 10, 7, 12, tzinfo=UTC))
        self.assertIn("collected before the breakdowns existed", page)

    def test_history_holds_labels_only(self):
        # crawler_cost keeps a named crawler's own user-agent strings, never a
        # person's (test_crawler_cost); everything else holds labels only.
        dump = "\n".join(x for x in self.history.db.iterdump() if "'crawler_cost'" not in x)
        for secret in ("203.0.113.", "198.51.100.", "Mozilla/5.0", "AppleWebKit",
                       "https://", "gclid=abc"):
            self.assertNotIn(secret, dump)
        from support import PERSONS
        for (cost,) in self.history.db.execute(
                "SELECT data FROM day_extras WHERE kind = 'crawler_cost'"):
            for secret in PERSONS + ("gclid=abc",):
                self.assertNotIn(secret, cost)

    def test_an_older_file_is_upgraded_from_6_with_a_copy_kept(self):
        path = Path(self._tmp.name) / "old.sqlite"
        db = sqlite3.connect(path)
        History(path).close()
        db.execute("ALTER TABLE days DROP COLUMN breakdowns")
        db.execute("UPDATE meta SET value = '6' WHERE key = 'schema_version'")
        db.commit()
        db.close()
        with History(path) as h:
            self.assertEqual(h.schema_version, SCHEMA_VERSION)
            self.assertEqual(h.migrated_from, 6)
        self.assertTrue((Path(self._tmp.name) / "old.sqlite.schema-v6.bak").exists())


class TestDashboardAndLive(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox(views=["{name: Guides, path_prefix: /guides/}"])

    def tearDown(self):
        self.box.close()

    def test_the_page_has_the_sections_and_a_csv_for_each_table(self):
        self.box.log(mixed())
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        self.assertEqual(self.box.run("--today", "2026-10-06", "dashboard")[0], 0)
        page = (self.box.root / "www" / "example.com" / "index.html").read_text()
        for words in ("Who the readers were", "Countries (", "\U0001F1E8\U0001F1E6 Canada",
                      "Devices (", "Browsers (", "Operating systems (", "Traffic sources (",
                      "Referring sites (", "Campaigns (", "Landing pages (", "Hour of day (",
                      "Site health", "Responses by status", "Pages not found, seen by real people",
                      "Server errors, 5xx", "How fast people", "Form posts"):
            self.assertIn(words, page)
        exports = self.box.root / "www" / "example.com" / "exports"
        for name in dashboard.EXPORTS:
            self.assertTrue((exports / name).exists(), name)
            self.assertIn(f'href="exports/{name}"', page) if name.startswith(
                ("readers-", "statuses", "not-found", "server-errors", "posts", "speed")) else None
        csv = (exports / "readers-country-30d.csv").read_text()
        self.assertIn("country,CA,2", csv)
        self.assertNotIn("<script", page)

    def test_live_carries_breakdowns_for_the_site_and_each_view(self):
        today = date(2026, 10, 7)
        noon = datetime(2026, 10, 7, 11, tzinfo=UTC)
        self.box.log([line(noon, "203.0.113.50", "/guides/alpha", IPHONE_SAFARI, country="CA"),
                      line(noon + timedelta(minutes=1), "203.0.113.51", "/", EDGE, country="US")])
        stamp = noon.timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        code, _, err = self.box.run("--today", today.isoformat(), "live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["breakdowns"]["by"]["country"], {"CA": 1, "US": 1})
        guides = snap["views"]["guides"]
        self.assertEqual(guides["state"], "ok")
        self.assertEqual(guides["breakdowns"]["by"]["device"], {"Mobile": 1})
        view_page = (self.box.root / "www" / "example.com" / "guides" / "index.html").read_text()
        self.assertIn("Today so far", view_page)
        self.assertIn("Who the readers were today", view_page)
        self.assertTrue((self.box.root / "www" / "example.com" / "exports" /
                         "today-readers-country.csv").exists())
