"""Each page's own published and modified dates (SKALD-64): page_dates_html.py
reads them from the HTML, page_dates.py fetches the pages (which, when, how
many) and keeps every value in history (schema 16), lifecycle.py shows them,
and audit_page_dates.py (with audit_lastmod.py's `updated` rule) is their
second count. Hosts are example.com; nothing here touches the network."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import (audit_lastmod, audit_page_dates, classify, lifecycle,  # noqa: E402
                          page_dates, settings_store, sitemap)
from skald.page_dates_html import local_day, normalise, parse  # noqa: E402
from skald.site_fetch import Answer, Unreachable  # noqa: E402
from skald.store import SCHEMA_VERSION, History  # noqa: E402

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
SITE = "www.example.com"
CONFIG = {"site": {"name": SITE, "hosts": [SITE, "example.com"], "page_dates": True},
          "report": {"timezone": "America/New_York"}}
ARTICLE = """<!doctype html><html><head>
<meta property="article:published_time" content="2024-11-05T06:42:00.000Z">
<meta property="article:modified_time" content="2026-11-26T05:42:14.000Z">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[
 {"@type":"Organization","name":"Example","foundingDate":"2001-01-01"},
 {"@type":"WebPage","@id":"https://www.example.com/guide/#webpage","url":"https://www.example.com/guide/",
  "datePublished":"2024-11-05T06:42:00+00:00","dateModified":"2026-11-26T05:42:14+00:00"},
 {"@type":"BlogPosting","@id":"https://www.example.com/guide/#post",
  "datePublished":"2024-11-05T06:42:00+00:00","dateModified":"2026-11-26T05:42:14+00:00",
  "comment":[{"@type":"Comment","dateCreated":"2026-11-25T10:00:00Z"}]}]}</script>
</head><body><time datetime="2026-11-19T23:42:44Z">a related post</time></body></html>"""


def dates(html: str, path: str, now: datetime) -> dict:
    """parse() without the title (SKALD-70): the dates alone."""
    got = parse(html, path, now)
    got.pop("title", None)
    return got


def page(html: str, status: int = 200, ctype: str = "text/html; charset=utf-8", **headers):
    hd = {"content-type": [ctype], **{k.replace("_", "-"): [v] for k, v in headers.items()}}
    return Answer(status, hd, html.encode("utf-8"))


class Normalise(unittest.TestCase):
    def test_the_forms_kept(self):
        cases = {"2024-11-05": "2024-11-05",
                 "2024-11-05T06:42:00.000Z": "2024-11-05T06:42:00Z",
                 "2026-11-26T00:42:14-05:00": "2026-11-26T05:42:14Z",
                 "2026-11-26T05:42+0000": "2026-11-26T05:42:00Z",
                 "2026-11-26 07:30:00": "2026-11-26T07:30:00",
                 " 2026-11-25T10:00:00Z ": "2026-11-25T10:00:00Z"}
        for raw, want in cases.items():
            self.assertEqual(normalise(raw, NOW), want, raw)

    def test_what_is_never_a_date(self):
        for raw in ("", None, "last tuesday", "2026-02-30", "1989-12-31", "2026-11", "2026",
                    "2026-11-26T25:00:00Z", "2026-11-27T12:00:00Z", "2026-12-01",
                    "2026-11-26T05:42:14+25:00"):
            self.assertIsNone(normalise(raw, NOW), raw)

    def test_the_local_day(self):
        self.assertEqual(local_day("2026-11-26T03:00:00Z", NY), "2026-11-25")
        self.assertEqual(local_day("2026-11-26T05:42:14Z", NY), "2026-11-26")
        self.assertEqual(local_day("2026-11-26T01:00:00", NY), "2026-11-26")
        self.assertEqual(local_day("2024-11-05", NY), "2024-11-05")


class Html(unittest.TestCase):
    def test_an_articles_jsonld_wins(self):
        got = dates(ARTICLE, "/guide/", NOW)
        self.assertEqual(got, {"published": ("2024-11-05T06:42:00Z", "jsonld"),
                               "modified": ("2026-11-26T05:42:14Z", "jsonld")})

    def test_an_article_comes_before_a_web_page_and_the_page_itself_first(self):
        html = """<script type="application/ld+json">[
          {"@type":"WebPage","datePublished":"2020-01-01"},
          {"@type":"Article","url":"https://www.example.com/other/","datePublished":"2021-01-01"},
          {"@type":["Article"],"mainEntityOfPage":{"@id":"https://www.example.com/guide"},
           "datePublished":"2022-01-01","dateModified":["2023-01-01"]}]</script>"""
        self.assertEqual(dates(html, "/guide/", NOW),
                         {"published": ("2022-01-01", "jsonld"), "modified": ("2023-01-01", "jsonld")})

    def test_meta_tags_when_there_is_no_jsonld(self):
        html = """<meta property="article:published_time" content="2025-03-01T10:00:00+01:00">
                  <meta property="og:updated_time" content="2026-11-20T08:00:00Z">"""
        self.assertEqual(dates(html, "/a/", NOW),
                         {"published": ("2025-03-01T09:00:00Z", "meta"),
                          "modified": ("2026-11-20T08:00:00Z", "meta")})

    def test_a_marked_time_tag_but_never_a_bare_one(self):
        html = """<time datetime="2026-11-01">related</time>
                  <time class="entry-date published" datetime="2025-06-01">1 Jun</time>
                  <span itemprop="dateModified" content="2026-11-02"></span>"""
        self.assertEqual(dates(html, "/a/", NOW),
                         {"published": ("2025-06-01", "time"), "modified": ("2026-11-02", "meta")})
        self.assertEqual(dates("<time datetime='2026-11-01'>x</time>", "/a/", NOW),
                         {"published": None, "modified": None})

    def test_a_listings_own_node_beats_a_related_post_inside_it(self):
        html = """<script type="application/ld+json">{"@type":"CollectionPage",
          "url":"https://www.example.com/blog/","datePublished":"2020-01-01","dateModified":"2026-11-20",
          "hasPart":[{"@type":"BlogPosting","url":"https://www.example.com/blog/post-a/",
          "datePublished":"2026-11-25","dateModified":"2026-11-25"}]}</script>"""
        self.assertEqual(dates(html, "/blog/", NOW),
                         {"published": ("2020-01-01", "jsonld"), "modified": ("2026-11-20", "jsonld")})
        # the related post alone, nested and not the page: never read
        only = html.replace('"datePublished":"2020-01-01","dateModified":"2026-11-20",', "")
        self.assertEqual(dates(only, "/blog/", NOW), {"published": None, "modified": None})

    def test_broken_or_future_values_fall_through(self):
        html = """<script type="application/ld+json">{not json</script>
                  <script type="application/ld+json">{"@type":"Article","datePublished":"soon",
                   "dateModified":"2027-01-01"}</script>
                  <meta property="article:modified_time" content="2026-11-10">"""
        self.assertEqual(dates(html, "/a/", NOW),
                         {"published": None, "modified": ("2026-11-10", "meta")})


class ReadPage(unittest.TestCase):
    HOSTS = [SITE, "example.com"]

    def read(self, *answers):
        queue = list(answers)
        asked = []

        def fetch(url, deadline):
            asked.append(url)
            got = queue.pop(0)
            if isinstance(got, Exception):
                raise got
            return got
        out = page_dates.read_page(f"https://{SITE}/guide/", self.HOSTS, NOW, fetch)
        return out, asked

    def test_a_page_with_dates(self):
        got, _ = self.read(page(ARTICLE))
        self.assertEqual((got["outcome"], got["status"]), ("dated", 200))
        self.assertEqual(got["dates"]["modified"], ("2026-11-26T05:42:14Z", "jsonld"))

    def test_a_page_without_dates_a_file_and_errors(self):
        self.assertEqual(self.read(page("<p>hi</p>"))[0]["outcome"], "not_given")
        self.assertEqual(self.read(page("%PDF", ctype="application/pdf"))[0]["outcome"], "not_html")
        got = self.read(page("<p>Just a moment</p>challenge", 403, cf_mitigated="challenge"))[0]
        self.assertEqual((got["outcome"], got["status"]), ("blocked", 403))
        got = self.read(page("oops", 500))[0]
        self.assertEqual((got["outcome"], got["status"], got["error"]),
                         ("failed", 500, "the page answered 500"))
        got = self.read(Unreachable("it did not answer in time"))[0]
        self.assertEqual((got["outcome"], got["error"]), ("failed", "it did not answer in time"))

    def test_redirects_on_the_site_only(self):
        got, asked = self.read(page("", 301, location="https://example.com/guide/"), page(ARTICLE))
        self.assertEqual(got["outcome"], "dated")
        self.assertEqual(asked, [f"https://{SITE}/guide/", "https://example.com/guide/"])
        got, asked = self.read(page("", 302, location="https://elsewhere.example.net/"))
        self.assertEqual(got["outcome"], "redirected")
        self.assertEqual(len(asked), 1)


class Due(unittest.TestCase):
    def test_the_order_and_the_waits(self):
        hour = timedelta(hours=1)
        checks = {
            "/changed/": {"checked_at": "2026-11-26T10:00:00Z", "outcome": "dated", "sitemap": "2026-11-20"},
            "/same/": {"checked_at": "2026-11-26T10:00:00Z", "outcome": "dated", "sitemap": "2026-11-25"},
            "/old/": {"checked_at": (NOW - 31 * 24 * hour).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "outcome": "not_given", "sitemap": None},
            "/failed-now/": {"checked_at": "2026-11-26T11:00:00Z", "outcome": "failed", "sitemap": None},
            "/failed-before/": {"checked_at": "2026-11-25T11:00:00Z", "outcome": "blocked",
                                "sitemap": None},
        }
        latest = {"/changed/": "2026-11-26T05:42:14Z", "/same/": "2026-11-25",
                  "/failed-now/": "2026-11-26"}
        paths = ["/new/", "/old/", "/same/", "/failed-now/", "/failed-before/", "/changed/"]
        self.assertEqual(page_dates.due(paths, checks, latest, NOW),
                         [("/changed/", "changed"), ("/new/", "new"),
                          ("/failed-before/", "retry"), ("/old/", "monthly")])


class Live(unittest.TestCase):
    """refresh() as a live run calls it, on a history file and a live folder."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.history = History(self.dir / "history.sqlite")
        # The day's sitemap list, its dates kept since 24 Nov (sitemap.keep writes both).
        listed = ["/", "/guide/", "/blog/one", "/feed/"]
        for day, stamps in ((date(2026, 11, 24), {"/guide/": ["2026-11-20"]}),
                            (date(2026, 11, 25), {"/guide/": ["2026-11-25T10:00:00Z"]}),
                            (date(2026, 11, 26), {"/guide/": ["2026-11-25T10:00:00Z"],
                                                  "/": ["2026-11-01"]})):
            sitemap.keep(self.dir, day, {"paths": listed, "sources": ["s"], "skipped": 0,
                                         "truncated": False, "lastmod": stamps},
                         f"{day}T05:00:00+00:00", NY)
        (self.dir / "robots.txt").write_text(f"Sitemap: https://{SITE}/sitemap.xml\n")
        self.asked = []
        self.sleeps = []

    def tearDown(self):
        self.history.db.close()
        self.tmp.cleanup()

    def fetch(self, url, deadline):
        self.asked.append(url)
        if url.endswith("/guide/"):
            return page(ARTICLE)
        if url.endswith("/blog/one"):
            return page("<p>no dates</p>")
        return page("down", 503)

    def sitemap_fetch(self, url):
        return (f'<urlset><url><loc>https://{SITE}/guide/</loc>'
                f'<lastmod>2026-11-26T05:42:14Z</lastmod></url>'
                f'<url><loc>https://{SITE}/</loc><lastmod>2026-11-01</lastmod></url></urlset>').encode()

    def run_once(self, now=NOW, config=CONFIG):
        return page_dates.refresh(config, self.dir, self.history, SITE, now=now, fetch=self.fetch,
                                  sitemap_fetch=self.sitemap_fetch, sleep=self.sleeps.append)

    def test_off_does_nothing(self):
        off = {**CONFIG, "site": {**CONFIG["site"], "page_dates": False}}
        self.assertEqual(self.run_once(config=off), {"on": False})
        self.assertEqual(page_dates.rows(self.history.db, SITE), ([], []))

    def test_a_first_run_imports_reads_the_sitemap_and_a_few_pages(self):
        got = self.run_once()
        self.assertTrue(got["on"])
        self.assertEqual(got["imported"], 3)        # 2 dates of /guide/ over the days, 1 of /
        self.assertEqual(got["read"], 3)            # every page of the list but the feed: all new
        self.assertEqual(self.sleeps, [page_dates.GAP] * 2)
        dates, checks = page_dates.rows(self.history.db, SITE)
        own = {(p, k, v, s) for p, k, v, s, _ in dates if s != "sitemap"}
        self.assertEqual(own, {("/guide/", "published", "2024-11-05T06:42:00Z", "jsonld"),
                               ("/guide/", "modified", "2026-11-26T05:42:14Z", "jsonld")})
        outcomes = {p: o for p, _, o, *_ in checks}
        self.assertEqual(outcomes, {"/guide/": "dated", "/blog/one": "not_given", "/": "failed"})
        # the sitemap's value with its time, beside the imported dates
        sm = sorted(v for p, k, v, s, _ in dates if s == "sitemap" and p == "/guide/")
        self.assertEqual(sm, ["2026-11-20", "2026-11-25", "2026-11-26T05:42:14Z"])
        st = page_dates.state(self.dir)
        self.assertEqual((st["day"], st["fetched"]), ("2026-11-26", 3))

    def test_the_next_runs_read_only_what_changed_and_wait_for_failures(self):
        self.run_once()
        self.asked.clear()
        got = self.run_once(NOW + timedelta(minutes=2))
        self.assertEqual((got["read"], self.asked, got["sitemap"]), (0, [], None))
        # 7 hours on: the sitemap is read again; /guide/ changed since its last read
        later = NOW + timedelta(hours=7)

        def moved(url):
            return self.sitemap_fetch(url).replace(b"2026-11-26T05:42:14Z", b"2026-11-26T18:00:00Z")
        got = page_dates.refresh(CONFIG, self.dir, self.history, SITE, now=later,
                                 fetch=self.fetch, sitemap_fetch=moved, sleep=self.sleeps.append)
        self.assertEqual(self.asked, [f"https://{SITE}/guide/"])
        # a day later the failed pages are tried again (the sitemap still says 18:00)
        self.sitemap_fetch = moved
        self.asked.clear()
        self.run_once(NOW + timedelta(hours=25))
        self.assertEqual(self.asked, [f"https://{SITE}/"])

    def test_the_batch_and_the_day_cap(self):
        st = {"day": "2026-11-26", "fetched": page_dates.DAY_CAP - 1, "imported": "x",
              "sitemap_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ")}
        (self.dir / page_dates.STATE).write_text(json.dumps(st))
        self.assertEqual(self.run_once()["read"], 1)
        self.assertEqual(self.run_once()["read"], 0)
        # the next day the count starts again, at most BATCH a run
        many = [f"/p{i}/" for i in range(20)]
        sitemap.keep(self.dir, date(2026, 11, 27), {"paths": many, "sources": ["s"],
                                                     "skipped": 0, "truncated": False,
                                                     "lastmod": {}}, "x", NY)
        got = self.run_once(NOW + timedelta(days=1))
        self.assertEqual(got["read"], page_dates.BATCH)

    def test_the_days_sitemap_list_never_removes_the_state(self):
        self.run_once()
        before = page_dates.state(self.dir)
        sitemap.keep(self.dir, date(2026, 11, 26), {"paths": ["/"], "sources": ["s"], "skipped": 0,
                                                     "truncated": False, "lastmod": {}}, "x", NY)
        self.assertEqual(page_dates.state(self.dir), before)
        again = self.run_once(NOW + timedelta(minutes=2))
        self.assertNotIn("imported", again)              # not copied in a second time
        self.assertIsNone(again["sitemap"])               # nor the sitemap read again

    def test_one_page_that_raises_never_stops_the_others(self):
        def fetch(url, deadline):
            self.asked.append(url)
            if url.endswith("/guide/"):
                raise UnicodeEncodeError("ascii", "café", 3, 4, "ordinal not in range")
            return page("<p>x</p>")
        got = page_dates.refresh(CONFIG, self.dir, self.history, SITE, now=NOW, fetch=fetch,
                                 sitemap_fetch=self.sitemap_fetch, sleep=self.sleeps.append)
        self.assertEqual(got["read"], 3)
        checks = {p: (o, e) for p, _, o, _, e, _ in page_dates.rows(self.history.db, SITE)[1]}
        self.assertEqual(checks["/guide/"][0], "failed")
        self.assertIn("UnicodeEncodeError", checks["/guide/"][1])
        self.assertEqual(page_dates.state(self.dir)["fetched"], 3)

    def test_a_locked_history_ends_the_share_but_the_state_is_kept(self):
        import sqlite3
        from unittest import mock
        with mock.patch.object(page_dates, "record",
                               side_effect=sqlite3.OperationalError("database is locked")):
            got = self.run_once()
        self.assertIn("database is locked", got["error"])
        st = page_dates.state(self.dir)
        self.assertTrue(st.get("imported") and st.get("sitemap_at"))
        self.assertEqual(st["last_run"]["error"], got["error"])

    def test_a_path_with_other_characters_is_encoded(self):
        sitemap.keep(self.dir, date(2026, 11, 26), {"paths": ["/café/"], "sources": ["s"],
                                                     "skipped": 0, "truncated": False,
                                                     "lastmod": {}}, "x", NY)
        self.run_once()
        self.assertEqual(self.asked, [f"https://{SITE}/caf%C3%A9/"])

    def test_a_sitemap_that_stamps_its_build_time_keeps_nothing(self):
        many = [f"/p{i}/" for i in range(30)]

        def build(stamp=None):
            return lambda url: ("<urlset>" + "".join(
                f"<url><loc>https://{SITE}{p}</loc><lastmod>{stamp or f'2026-11-{i % 20 + 1:02d}'}"
                "</lastmod></url>" for i, p in enumerate(many)) + "</urlset>").encode()
        # real edits: many values changing at once is fine when they differ
        self.assertEqual(page_dates.read_sitemap(self.history.db, SITE, CONFIG, self.dir, NOW,
                                                 build()), 30)
        later = NOW + timedelta(hours=6)
        got = page_dates.read_sitemap(self.history.db, SITE, CONFIG, self.dir, later,
                                      build("2026-11-26T12:00:00Z"))
        self.assertEqual(got, "build_times")
        values = {v for p, k, v, s, _ in page_dates.rows(self.history.db, SITE)[0] if p in many}
        self.assertEqual(len(values), 20)
        self.assertNotIn("2026-11-26T12:00:00Z", values)
        # a value going back to an earlier one (A, B, A) is the latest again, seen now
        db = self.history.db

        def one(value):
            return lambda url: (f"<urlset><url><loc>https://{SITE}/p0/</loc><lastmod>{value}"
                                "</lastmod></url></urlset>").encode()
        for i, value in enumerate(("2026-11-20", "2026-11-21", "2026-11-20")):
            page_dates.read_sitemap(db, SITE, CONFIG, self.dir, later + timedelta(hours=i),
                                    one(value))
        self.assertEqual(page_dates.sitemap_now(page_dates.rows(db, SITE)[0])["/p0/"], "2026-11-20")

    def test_pages_people_read_that_the_sitemap_does_not_list(self):
        blob = {"/unlisted/": {"views": 3, "readers": 2}, "/wp-json/x": {"views": 1, "readers": 1},
                "/guide": {"views": 9, "readers": 5}, "/nobody/": {"views": 1, "readers": 0}}
        with self.history.db as db:
            db.execute("INSERT INTO day_extras VALUES (?, '2026-11-25', 'pages', ?)",
                       (SITE, json.dumps(blob)))
        got = page_dates.candidates(CONFIG, self.dir, self.history, SITE, date(2026, 11, 26))
        self.assertEqual(got, ["/", "/guide/", "/blog/one", "/unlisted/"])


class Shown(unittest.TestCase):
    """What lifecycle shows from the rows, and the second count."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.history = History(self.dir / "history.sqlite")
        db = self.history.db
        rows = [("/guide", "published", "2024-11-05T06:42:00Z", "jsonld", "2026-11-25T08:00:00Z"),
                ("/guide/", "modified", "2026-11-25T10:00:00Z", "jsonld", "2026-11-25T11:00:00Z"),
                ("/guide/", "modified", "2026-11-26T05:42:14Z", "jsonld", "2026-11-26T06:00:00Z"),
                ("/guide/", "modified", "2026-11-26T05:42:14Z", "sitemap", "2026-11-26T06:00:00Z"),
                ("/guide/", "modified", "2026-11-20", "sitemap", "2026-11-24T05:00:00Z"),
                ("/only-sitemap/", "modified", "2026-11-03", "sitemap", "2026-11-24T05:00:00Z")]
        with db:
            db.executemany("INSERT INTO page_dates VALUES (?, ?, ?, ?, ?, ?)",
                           [(SITE, *r) for r in rows])
            db.executemany("INSERT INTO page_checks VALUES (?, ?, ?, ?, ?, ?, ?)", [
                (SITE, "/guide", "2026-11-25T08:00:00Z", "dated", 200, None, None),
                (SITE, "/guide/", "2026-11-26T06:00:00Z", "dated", 200, None, "2026-11-26T05:42:14Z"),
                (SITE, "/down/", "2026-11-26T06:00:00Z", "blocked", 403, "a bot check stopped the request", None)])

    def tearDown(self):
        self.history.db.close()
        self.tmp.cleanup()

    def test_the_page_says_published_and_updated_and_every_update_is_listed(self):
        got = lifecycle.page_dates(CONFIG, self.dir, self.history, SITE)
        g = got["/guide/"]
        self.assertEqual((g["updated"], g["updated_source"], g["updated_at"]),
                         ("2026-11-26", "page", "2026-11-26T05:42:14Z"))
        self.assertEqual((g["published_at"], g["published_from"]), ("2024-11-05T06:42:00Z", "jsonld"))
        self.assertEqual(g["changes"], [
            {"day": "2026-11-20", "at": "2026-11-20", "sources": ["sitemap"]},
            {"day": "2026-11-25", "at": "2026-11-25T10:00:00Z", "sources": ["jsonld"]},
            {"day": "2026-11-26", "at": "2026-11-26T05:42:14Z", "sources": ["jsonld", "sitemap"]}])
        self.assertEqual(g["check"]["at"], "2026-11-26T06:00:00Z")
        # a page with only sitemap rows: no updated date from the page
        self.assertEqual(got["/only-sitemap/"]["updated_source"], None)
        self.assertEqual(got["/down/"]["check"]["outcome"], "blocked")
        # without history (an older caller): the sitemap's rule, nothing of the page's
        self.assertNotIn("/down/", lifecycle.page_dates(CONFIG, self.dir))

    def test_published_from_the_page_beats_first_seen(self):
        own = lifecycle.own_dates(self.history, SITE, NY)
        self.assertEqual(lifecycle._published("/guide/", {}, {"/guide/": "2026-10-29"}, own),
                         ("2024-11-05", None, "page"))
        self.assertEqual(lifecycle._published("/other/", {}, {"/other/": "2026-10-29"}, own),
                         ("2026-10-29", None, "first seen"))
        meta = {"/guide/": {"published": "2024-01-01"}}
        self.assertEqual(lifecycle._published("/guide/", meta, {}, own)[2], "website")

    def test_the_second_count_agrees_and_catches_a_nudge(self):
        shown = lifecycle.page_dates(CONFIG, self.dir, self.history, SITE)
        self.assertEqual(audit_page_dates.recheck(self.history.db, SITE, NY, shown, NOW), [])
        shown["/guide/"]["changes"] = shown["/guide/"]["changes"][1:]
        shown["/guide/"]["updated_at"] = "2026-11-25T10:00:00Z"
        problems = audit_page_dates.recheck(self.history.db, SITE, NY, shown, NOW)
        self.assertEqual(len(problems), 2, problems)
        # audit_lastmod's `updated` takes the page's own day before the sitemap's
        own = audit_page_dates.own_modified(self.history.db, SITE, NY)
        self.assertEqual(own, {"/guide/": "2026-11-26"})
        want = audit_lastmod.expected({"cap": 20, "paths": {
            "/guide/": {"seen": [["2026-11-20", "2026-11-24"]]}}}, None, own)
        self.assertEqual((want["/guide/"]["updated"], want["/guide/"]["updated_source"]),
                         ("2026-11-26", "page"))

    def test_the_second_count_holds_the_published_date_and_its_source(self):
        shown = lifecycle.page_dates(CONFIG, self.dir, self.history, SITE)
        self.assertEqual((shown["/guide/"]["published"], shown["/guide/"]["date_source"]),
                         ("2024-11-05", "page"))
        shown["/guide/"]["date_source"] = "first seen"
        shown["/guide/"]["updated_source"] = "sitemap"
        problems = audit_page_dates.recheck(self.history.db, SITE, NY, shown, NOW)
        self.assertEqual(len(problems), 2, problems)
        # the website's own list wins, in the page and in the recount
        meta = self.dir / "pages.json"
        meta.write_text(json.dumps({"pages": [{"path": "/guide/", "published": "2024-01-01"}]}))
        config = {**CONFIG, "report": {**CONFIG["report"], "pages_meta": str(meta)}}
        shown = lifecycle.page_dates(config, self.dir, self.history, SITE)
        self.assertEqual(shown["/guide/"]["date_source"], "website")
        self.assertEqual(audit_page_dates.recheck(self.history.db, SITE, NY, shown, NOW,
                                                  meta_file=meta), [])

    def test_the_second_count_reads_the_rows_themselves(self):
        with self.history.db as db:
            db.execute("INSERT INTO page_dates VALUES (?, '/x/', 'modified', '2026-13-01', "
                       "'jsonld', '2026-11-26T06:00:00Z')", (SITE,))
            db.execute("INSERT INTO page_dates VALUES (?, '/y/', 'published', '2026-11-26T09:00:00Z',"
                       " 'nowhere', '2026-11-26T06:00:00Z')", (SITE,))
        dates, checks = audit_page_dates._rows(self.history.db, SITE)
        problems = audit_page_dates.check_rows(dates, checks, NOW)
        self.assertEqual(len(problems), 3, problems)   # bad value, no read of /x/, bad source


class Schema(unittest.TestCase):
    def test_version_16_adds_the_tables_to_an_older_file(self):
        import sqlite3
        self.assertEqual(SCHEMA_VERSION, 16)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.sqlite"
            History(path).db.close()
            db = sqlite3.connect(path)
            db.execute("DROP TABLE page_dates")
            db.execute("DROP TABLE page_checks")
            db.execute("UPDATE meta SET value = '15' WHERE key = 'schema_version'")
            db.commit()
            db.close()
            h = History(path)
            try:
                self.assertEqual(h.migrated_from, 15)
                names = {r[0] for r in h.db.execute("SELECT name FROM sqlite_master")}
                self.assertTrue({"page_dates", "page_checks"} <= names)
            finally:
                h.db.close()
            self.assertTrue((Path(tmp) / "history.sqlite.schema-v15.bak").exists())

    def test_a_reader_without_the_tables_shows_no_page_dates(self):
        import sqlite3
        db = sqlite3.connect(":memory:")
        self.assertEqual(page_dates.rows(db, SITE), ([], []))
        self.assertEqual(page_dates.view(db, SITE, NY), {})


class Wiring(unittest.TestCase):
    def test_skalds_own_request_is_never_a_visitor(self):
        self.assertIn((page_dates.AGENT_TOKEN, "Skald (page dates)"), classify.OWN_AGENTS)
        self.assertIn(page_dates.AGENT_TOKEN, page_dates.AGENT)

    def test_the_setting_is_off_by_default_and_per_site(self):
        key = settings_store.SCHEMA["site.page_dates"]
        self.assertEqual((key.kind, key.default, key.scopes, key.config),
                         ("bool", False, ("site",), ("site", "page_dates")))
        self.assertFalse(page_dates.enabled({}))
        self.assertTrue(page_dates.enabled({"site": {"page_dates": "on"}}))

    def test_the_live_run_step_says_a_failed_refresh(self):
        from unittest import mock
        said = []

        class Opened:
            def __enter__(self):
                return SimpleNamespace(db=None)

            def __exit__(self, *a):
                return False
        ctx = SimpleNamespace(config=CONFIG, live_dir="/nowhere", site=SITE, err=said.append,
                              history=Opened)
        with mock.patch.object(page_dates, "refresh", side_effect=RuntimeError("boom")):
            page_dates.live_step(ctx)
        self.assertEqual(said, ["page dates: RuntimeError: boom"])

    def test_the_live_run_step_never_raises(self):
        said = []
        ctx = SimpleNamespace(config=CONFIG, live_dir=None, site=SITE, err=said.append,
                              history=lambda: (_ for _ in ()).throw(OSError("disk")))
        page_dates.live_step(ctx)
        self.assertEqual(said, ["page dates: OSError: disk"])


if __name__ == "__main__":
    unittest.main()
