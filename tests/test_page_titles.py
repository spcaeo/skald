"""Each page's title (SKALD-70): read with its dates from the page's HTML
(page_dates_html.py: <title>, else og:title, else the JSON-LD headline), kept in
history beside the dates (page_dates kind "title"), shown in page_index.json
and the story (the website's own list still wins), read once more for a page
read before titles were kept, and held by audit_page_dates.py. Also app.json's
`hosts`, which a table search reads an address of the site by. Hosts are
example.com; nothing here touches the network."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import audit_page_dates, dashboard_webapp, lifecycle, page_dates, sitemap  # noqa: E402
from skald.page_dates_html import TITLE_MAX, clean_title, parse  # noqa: E402
from skald.site_fetch import Answer  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
SITE = "www.example.com"
CONFIG = {"site": {"name": SITE, "hosts": [SITE, "example.com"], "page_dates": True},
          "report": {"timezone": "America/New_York"}}


def title(html: str):
    return parse(html, "/guide/", NOW)["title"]


class Read(unittest.TestCase):
    def test_the_title_tag_with_entities_and_spaces(self):
        self.assertEqual(title("<head><title>\n  How to Export Data from Salesforce (2026):\n"
                               "  Every Method &amp; Tool &#8211; Example</title></head>"),
                         ("How to Export Data from Salesforce (2026): Every Method & Tool – "
                          "Example", "html"))

    def test_an_icons_title_is_never_the_pages(self):
        self.assertEqual(title('<body><svg><title>Menu</title></svg><title>The guide</title>'),
                         ("The guide", "html"))
        self.assertIsNone(title('<svg viewBox="0 0 1 1"><title>Menu</title></svg>'))

    def test_og_title_then_the_jsonld_headline(self):
        self.assertEqual(title('<title>   </title><meta property="og:title" content="From OG &amp; co">'),
                         ("From OG & co", "meta"))
        html = ('<script type="application/ld+json">{"@type":"BlogPosting",'
                '"url":"https://www.example.com/guide/","headline":"From &amp; JSON-LD"}</script>')
        self.assertEqual(title(html), ("From & JSON-LD", "jsonld"))
        # a related post's headline, nested and not the page, is never the page's
        nested = ('<script type="application/ld+json">{"@type":"CollectionPage","url":'
                  '"https://www.example.com/guide/","hasPart":[{"@type":"BlogPosting",'
                  '"url":"https://www.example.com/other/","headline":"Other post"}]}</script>')
        self.assertIsNone(title(nested))

    def test_a_long_title_is_cut_at_a_word(self):
        long = "Word " * 120
        got = clean_title(long)
        self.assertLessEqual(len(got), TITLE_MAX)
        self.assertTrue(got.endswith("Word…"), got[-12:])
        self.assertEqual(clean_title("x" * 400)[-1], "…")
        self.assertIsNone(clean_title(" \n\t "))
        self.assertIsNone(clean_title(None))

    def test_the_odd_cases(self):
        # an <svg> left open before the head's title, and a title with tags inside it
        self.assertEqual(title('<html><svg><path></path><head><title>Head <b>title</b></title></head>'),
                         ("Head title", "html"))
        self.assertIsNone(clean_title("\u200b \ufeff"), "zero-width characters alone are no title")
        self.assertTrue(clean_title("-" * 400).startswith("---"), "a title of dashes is not cut to nothing")

    def test_written_angle_brackets_stay(self):
        # review of the release merge: "&lt;video&gt;" is text, not a tag, on every road
        self.assertEqual(title("<head><title>The HTML &lt;video&gt; tag &amp; you</title></head>"),
                         ("The HTML <video> tag & you", "html"))
        self.assertEqual(title('<meta property="og:title" content="The &lt;head&gt; tag">'),
                         ("The <head> tag", "meta"))
        html = ('<script type="application/ld+json">{"@type":"BlogPosting","url":'
                '"https://www.example.com/guide/","headline":"The &lt;head&gt; <b>tag</b>"}</script>')
        self.assertEqual(title(html), ("The <head> tag", "jsonld"))

    def test_an_icon_in_the_head_is_not_the_title(self):
        self.assertEqual(title("<head><svg><title>icon</title></svg><title>Real</title></head>"),
                         ("Real", "html"))

    def test_a_title_alone_is_not_a_dated_page(self):
        got = page_dates.read_page(f"https://{SITE}/guide/", [SITE], NOW, lambda url, d: Answer(
            200, {"content-type": ["text/html"]}, b"<title>Just a title</title>"))
        self.assertEqual((got["outcome"], got["dates"]["title"]), ("not_given", ("Just a title", "html")))


class Kept(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.history = History(self.dir / "history.sqlite")
        self.db = self.history.db

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def read(self, path, html, now):
        got = page_dates.read_page(f"https://{SITE}{path}", [SITE], now, lambda url, d: Answer(
            200, {"content-type": ["text/html"]}, html.encode()))
        page_dates.record(self.db, SITE, path, got, None, now)

    def test_every_title_is_kept_and_the_latest_shown(self):
        self.read("/guide/", "<title>First title</title>", NOW - timedelta(days=3))
        self.read("/guide/", "<title>Second title</title>", NOW)
        titles = sorted(v for p, k, v, s, _ in page_dates.rows(self.db, SITE)[0] if k == "title")
        self.assertEqual(titles, ["First title", "Second title"])
        self.assertEqual(page_dates.view(self.db, SITE, NY)["/guide/"]["title"],
                         {"text": "Second title", "from": "html"})
        shown = lifecycle.page_dates(CONFIG, self.dir, self.history, SITE)
        self.assertEqual((shown["/guide/"]["title"], shown["/guide/"]["title_from"]),
                         ("Second title", "html"))
        self.assertEqual(audit_page_dates.recheck(self.db, SITE, NY, shown, NOW), [])
        # the website's own list wins
        meta = self.dir / "pages.json"
        meta.write_text(json.dumps({"pages": [{"path": "/guide/", "title": "From the website"}]}))
        config = {**CONFIG, "report": {**CONFIG["report"], "pages_meta": str(meta)}}
        shown = lifecycle.page_dates(config, self.dir, self.history, SITE)
        self.assertEqual((shown["/guide/"]["title"], shown["/guide/"]["title_from"]),
                         ("From the website", "website"))
        self.assertEqual(audit_page_dates.recheck(self.db, SITE, NY, shown, NOW, meta_file=meta), [])

    def test_a_title_that_goes_back_is_shown_again(self):
        for i, text in enumerate(("Best tools", "Best tools (2026)", "Best tools")):
            self.read("/guide/", f"<title>{text}</title>", NOW - timedelta(days=60 - 30 * i))
        self.assertEqual(page_dates.view(self.db, SITE, NY)["/guide/"]["title"]["text"], "Best tools")
        shown = lifecycle.page_dates(CONFIG, self.dir, self.history, SITE)
        self.assertEqual(audit_page_dates.recheck(self.db, SITE, NY, shown, NOW), [])

    def test_the_second_count_catches_a_wrong_title_and_a_bad_row(self):
        self.read("/guide/", "<title>Kept title</title>", NOW)
        shown = lifecycle.page_dates(CONFIG, self.dir, self.history, SITE)
        shown["/guide/"]["title"] = "Another title"
        problems = audit_page_dates.recheck(self.db, SITE, NY, shown, NOW)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("title shown", problems[0])
        with self.db:
            self.db.execute("INSERT INTO page_dates VALUES (?, '/guide/', 'title', 'Two\nlines', "
                            "'html', '2026-11-27T11:00:00Z')", (SITE,))
            self.db.execute("INSERT INTO page_dates VALUES (?, '/guide/', 'title', 'From time', "
                            "'time', '2026-11-27T11:00:00Z')", (SITE,))
            self.db.execute("INSERT INTO page_dates VALUES (?, '/guide/', 'modified', '2026-11-20', "
                            "'html', '2026-11-27T11:00:00Z')", (SITE,))
        dates, checks = audit_page_dates._rows(self.db, SITE)
        self.assertEqual(len(audit_page_dates.check_rows(dates, checks, NOW)), 3)

    def test_a_page_read_before_titles_is_read_once_more(self):
        listed = ["/a/", "/b/"]
        sitemap.keep(self.dir, date(2026, 11, 27), {"paths": listed, "sources": ["s"],
                                                     "skipped": 0, "truncated": False,
                                                     "lastmod": {}}, "x", NY)
        # both read yesterday, before titles were kept: no title row
        for p in listed:
            page_dates.record(self.db, SITE, p, {"outcome": "dated", "status": 200, "error": None,
                                                 "dates": {"modified": ("2026-11-20", "meta")}},
                              None, NOW - timedelta(days=1))
        asked = []

        def fetch(url, deadline):
            asked.append(url)
            return Answer(200, {"content-type": ["text/html"]},
                          b"<title>T</title>" if url.endswith("/a/") else b"<p>no title</p>")
        run = lambda now: page_dates.refresh(CONFIG, self.dir, self.history, SITE, now=now,  # noqa: E731
                                             fetch=fetch, sitemap_fetch=lambda u: b"<urlset/>",
                                             sleep=lambda s: None)
        run(NOW)
        self.assertEqual(sorted(asked), [f"https://{SITE}/a/", f"https://{SITE}/b/"])
        asked.clear()
        run(NOW + timedelta(minutes=2))          # /b/ has no title: not read again for it
        self.assertEqual(asked, [])
        # the state file lost: the oldest title kept says when titles began, no endless re-read
        (self.dir / page_dates.STATE).unlink()
        run(NOW + timedelta(minutes=4))
        self.assertEqual(asked, [])


class AppHosts(unittest.TestCase):
    def test_app_json_lists_the_sites_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = History(Path(tmp) / "h.sqlite")
            try:
                dashboard_webapp.write(Path(tmp) / "www", history, SITE, NY, NOW.astimezone(NY),
                                       None, config={"site": {"hosts": ["WWW.Example.com",
                                                                        "example.com"]}})
            finally:
                history.db.close()
            got = json.loads((Path(tmp) / "www" / SITE / "data" / "app.json").read_text())
        self.assertEqual(got["hosts"], ["www.example.com", "example.com"])


if __name__ == "__main__":
    unittest.main()
