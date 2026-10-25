"""Machine and utility addresses that are not pages (not_pages.py,
COUNTING-TRAPS.md trap 19, CLASSIFICATION.md "What decides a page view").

Found on the live sites, 2026-10-25, counted as people's page views:
?rest_route= and ?feed= probes on a site that is no longer WordPress (it
answers them with its home page), ?author=2 user-number lookups, and
Markdown copies of pages fetched by an AI agent (/okf/index.md).

Pinned here: each entry and a near miss, on both roads; the two roads agree
on awkward URLs; a request on the list stays a request in its group and
leaves the page views, readers and landings; a site can count an entry as
pages again and add its own; the audit recounts it and catches a main road
that does not apply it. Addresses are RFC 5737's.
"""
from __future__ import annotations

import ast
import random
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, audit, audit_not_pages, not_pages, settings_store  # noqa: E402
from skald.parse import Hit  # noqa: E402
from skald.store import History  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import CHROME, Sandbox, line  # noqa: E402

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 10, 23)
TODAY = "2026-10-24"
HOSTS = {"site": {"hosts": ["example.com"], "require_rendering": False}}

# entry -> (addresses it takes out, near misses it must leave as pages)
CASES = {
    "markdown": (["/okf/index.md", "/index.md", "/docs/guide.MD", "/a/b.mdx", "/notes.markdown",
                  "/x.md/", "/okf/index.md?_v=2"],
                 ["/integrations/markdown/", "/blog/what-is-md/", "/md", "/x.md.html",
                  "/blog/readme-md-tips/", "/x.mdown"]),
    "wp_rest": (["/?rest_route=/wp/v2/users", "/index.php?rest_route=/", "/wp-json/",
                 "/wp-json", "/wp-json/wp/v2/posts?per_page=1", "/blog/wp-json/oembed",
                 "/?a=1&REST_ROUTE=/x", "/?rest_route"],
                ["/blog/wp-json-guide/", "/?rest_routes=1", "/?my_rest_route=1",
                 "/rest_route/"]),
    "wp_files": (["/xmlrpc.php", "/wp-cron.php", "/wp-cron.php?doing_wp_cron=1",
                  "/wp-admin/admin-ajax.php", "/blog/xmlrpc.php"],
                 ["/xmlrpc", "/wp-cron/", "/blog/xmlrpc-php-explained/", "/admin-ajax.php.bak/x"]),
    "feeds": (["/feed/", "/feed", "/comments/feed/", "/blog/post-name/feed/", "/feed/rss2/",
               "/feed/atom", "/category/news/feed/rdf/", "/?feed=rss2", "/?p=1&feed=atom",
               "/?author=jane&feed=rss2", "/FEED/"],
              ["/blog/feed-the-world/", "/feeds/", "/newsfeed/", "/feed/me/", "/?feedback=1",
               "/rss/", "/atom/", "/podcast/feed-guide"]),
    "oembed": (["/oembed/1.0/embed?url=https://example.com/", "/oembed", "/x/oembed/"],
               ["/oembeds/", "/blog/oembed-explained/"]),
    "trackback": (["/post-name/trackback/", "/trackback", "/wp-trackback.php?p=1"],
                  ["/trackbacks/", "/blog/trackback-spam/"]),
    "author_number": (["/?author=1", "/?author=12&x=1", "/index.php?author=3"],
                      ["/?author=jane", "/?author=", "/?author=1x", "/author/1/",
                       "/?coauthor=1", "/?author=%31"]),
    "reply_to_comment": (["/post/?replytocom=12", "/?replytocom=1#respond"],
                         ["/post/?reply=12", "/post/replytocom/"]),
}


def both(url: str, config: dict | None = None) -> tuple[str, str]:
    path = url.split("?", 1)[0]
    main = not_pages.from_config(config).match(path, url)
    second = audit_not_pages.Marker(config)(path, url)
    return main, second


def at(hour, minute=0, second=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def count(lines, config=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(sorted(lines)))
        start, end = day_window(DAY, UTC)
        return analyse_window(config or HOSTS, start, end, paths=[path])


class TestEachEntry(unittest.TestCase):

    def test_every_default_entry_has_cases(self):
        self.assertEqual(set(CASES), set(not_pages.DEFAULT))

    def test_matches_on_both_roads(self):
        for name, (hits, _) in CASES.items():
            for url in hits:
                with self.subTest(name=name, url=url):
                    self.assertEqual(both(url), (name, name))

    def test_near_misses_on_both_roads(self):
        for name, (_, misses) in CASES.items():
            for url in misses:
                with self.subTest(name=name, url=url):
                    self.assertEqual(both(url), ("", ""))

    def test_the_judgement_calls_stay_pages(self):
        # A person opens these: an HTML sitemap page, search results, a cart,
        # a sign-in page, an app's dashboard, a thank-you page, short links.
        for url in ("/sitemap/", "/sitemap", "/site-map/", "/search/", "/?s=shoes", "/cart/",
                    "/checkout/", "/my-account/", "/sign-in", "/login/", "/dashboard",
                    "/thank-you/", "/?p=12", "/?page_id=7", "/status", "/embed/", "/amp/"):
            with self.subTest(url=url):
                self.assertEqual(both(url), ("", ""))

    def test_the_made_up_sitemap_matches_nothing(self):
        text = (ROOT / "tests" / "fixtures" / "site_paths.txt").read_text()
        site = [p.strip() for p in text.splitlines() if p.startswith("/")]
        self.assertGreater(len(site), 400)
        self.assertEqual([p for p in site if any(both(p))], [])

    def test_the_first_entry_in_list_order_names_it(self):
        self.assertEqual(both("/?author=1&feed=rss2"), ("feeds", "feeds"))
        self.assertEqual(both("/okf/index.md?rest_route=/"), ("markdown", "markdown"))

    def test_the_roads_agree_on_awkward_urls(self):
        # Case beyond ASCII (the Kelvin sign lowers to "k"), a second "?",
        # a fragment, empty parts, encodings: the same answer on both roads.
        fixed = ["/x.marKdown", "/a?b=1?feed=x", "/?a=1#&feed=1", "/feed#top", "/?&&feed",
                 "/?feed&x", "/?Author=1", "/?author=1=2", "/?author=١", "//feed//",
                 "/feed//rss2", "/%66eed/", "/?%72est_route=1", "/WP-JSON/x", "/x.md#a",
                 "", "?", "/?", "/.md", "feed", "/a/./feed/", "/a?replytocom", "/?amp;feed=1"]
        rnd = random.Random(19)
        parts = ["feed", "FEED", "rss2", "atom", "x.md", ".MD", "wp-json", "oembed",
                 "trackback", "xmlrpc.php", "a", "", "%2f", "K", "ſ", "#", "?"]
        keys = ["feed", "Feed", "author", "AUTHOR", "rest_route", "replytocom", "x", "", "s"]
        values = ["", "1", "12", "x", "1x", "١", "1&", "rss2"]
        for _ in range(3000):
            path = "/" + "/".join(rnd.choice(parts) for _ in range(rnd.randint(0, 4)))
            query = "&".join(rnd.choice(keys) + rnd.choice(["=", "", "=="]) + rnd.choice(values)
                             for _ in range(rnd.randint(0, 3)))
            fixed.append(path + ("?" + query if rnd.random() < 0.6 else ""))
        for url in fixed:
            a, b = both(url)
            self.assertEqual(a, b, url)
        for url in fixed[:300]:
            config = {"site": {"not_pages_extra": ["/okf/*", "/status", "?wpt-check", "/A/B/"]}}
            a, b = both(url + "&wpt-check" if "?" in url else url, config)
            self.assertEqual(a, b, url)


class TestTheSwitch(unittest.TestCase):

    def test_an_entry_switched_off_is_a_page_again(self):
        config = {"site": {"not_pages_off": ["markdown"]}}
        self.assertEqual(both("/okf/index.md", config), ("", ""))
        self.assertEqual(both("/feed/", config), ("feeds", "feeds"))

    def test_the_sites_own_entries(self):
        config = {"site": {"not_pages_extra": ["/okf/*", "/status", "?wpt-check"]}}
        self.assertEqual(both("/okf/index.html", config), ("own: /okf/*",) * 2)
        self.assertEqual(both("/OKF/a", config), ("own: /okf/*",) * 2)
        self.assertEqual(both("/okf", config), ("", ""))
        self.assertEqual(both("/status/", config), ("own: /status",) * 2)
        self.assertEqual(both("/statuses", config), ("", ""))
        self.assertEqual(both("/?wpt-check=1", config), ("own: ?wpt-check",) * 2)
        self.assertEqual(both("/okf/index.md", config), ("markdown", "markdown"))

    def test_an_unreadable_setting_is_the_default_on_both_roads(self):
        for site in ({"not_pages_off": ["nope"]}, {"not_pages_off": 5},
                     {"not_pages_extra": ["no-slash"]}, {"not_pages_extra": ["/"]},
                     {"not_pages_extra": [f"/p{k}" for k in range(21)]}):
            with self.subTest(site=site):
                config = {"site": site}
                self.assertEqual(both("/okf/index.md", config), ("markdown", "markdown"))
                self.assertEqual(both("/p1", config), ("", ""))

    def test_strings_from_config_yml(self):
        config = {"site": {"not_pages_off": "markdown, feeds", "not_pages_extra": "/a/* ?b"}}
        self.assertEqual(both("/x.md", config), ("", ""))
        self.assertEqual(both("/a/1", config), ("own: /a/*",) * 2)

    def test_the_settings_check(self):
        v = settings_store.validate
        self.assertEqual(v("site.not_pages_off", ["feeds", "markdown", "feeds"]),
                         ["markdown", "feeds"])
        self.assertEqual(v("site.not_pages_off", []), [])
        self.assertEqual(v("site.not_pages_extra", "/okf/*\n?preview /status"),
                         ["/okf/*", "?preview", "/status"])
        for name, bad in (("site.not_pages_off", ["sitemap"]), ("site.not_pages_off", 3),
                          ("site.not_pages_extra", ["/"]), ("site.not_pages_extra", ["/*"]),
                          ("site.not_pages_extra", ["okf"]), ("site.not_pages_extra", ["/a b"]),
                          ("site.not_pages_extra", ["/a*b"]), ("site.not_pages_extra", ["/a?b"]),
                          ("site.not_pages_extra", ["/../x"]), ("site.not_pages_extra", ["?a=b"]),
                          ("site.not_pages_extra", [f"/p{k}" for k in range(21)])):
            with self.subTest(name=name, bad=bad):
                with self.assertRaises(settings_store.Invalid):
                    v(name, bad)

    def test_apply_writes_it_where_both_roads_read_it(self):
        self.assertEqual(settings_store.SCHEMA["site.not_pages_off"].config,
                         ("site", "not_pages_off"))
        self.assertEqual(settings_store.SCHEMA["site.not_pages_extra"].config,
                         ("site", "not_pages_extra"))


class TestCounting(unittest.TestCase):

    def lines(self):
        reader = [line(at(9), "198.51.100.20", "/", CHROME),
                  line(at(9, 1), "198.51.100.20", "/pricing/", CHROME, "https://example.com/")]
        agent = [line(at(10, 0, k), "203.0.113.40", "/okf/index.md", CHROME) for k in range(3)]
        probes = [line(at(11), "203.0.113.41", "/?rest_route=/wp/v2/users", CHROME),
                  line(at(11, 0, 5), "203.0.113.41", "/?author=1", CHROME),
                  line(at(11, 0, 9), "203.0.113.41", "/feed/", CHROME, status=304)]
        return reader + agent + probes

    def test_requests_stay_in_their_group_and_leave_the_page_views(self):
        lines = self.lines()
        totals = count(lines)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual(sum(g.hits for g in totals.groups.values()), len(lines))
        self.assertEqual(people.hits, len(lines))
        self.assertEqual((people.views, people.readers), (2, 1))
        self.assertNotIn("/okf/index.md", people.pages)
        self.assertEqual(people.by["landing"], {"/": 1})
        self.assertEqual(totals.extras["quality"]["not_pages"],
                         {"markdown": {"requests": 3, "people": 3},
                          "wp_rest": {"requests": 1, "people": 1},
                          "author_number": {"requests": 1, "people": 1},
                          "feeds": {"requests": 1, "people": 1}})

    def test_switched_off_they_are_pages_again(self):
        config = {"site": {**HOSTS["site"], "not_pages_off": list(not_pages.DEFAULT)}}
        people = count(self.lines(), config).groups[Group.PEOPLE]
        self.assertEqual((people.views, people.readers), (8, 3))

    def test_a_hit_without_a_list_uses_the_built_in_one(self):
        hit = Hit(at(9), "198.51.100.1", "example.com", "GET", "/feed/", "200", "", CHROME)
        self.assertFalse(hit.is_page)
        self.assertEqual(hit.not_page_rule, "feeds")
        other = Hit(at(9), "198.51.100.1", "example.com", "GET", "/feed/", "404", "", CHROME)
        self.assertEqual(other.not_page_rule, "", "a 404 is no page view anyway")
        page = Hit(at(9), "198.51.100.1", "example.com", "GET", "/", "200", "", CHROME)
        self.assertTrue(page.is_page)
        self.assertEqual(page.not_page_rule, "")

    def test_the_requests_feed_says_why(self):
        from skald import requests_feed
        hit = Hit(at(9), "198.51.100.1", "example.com", "GET", "/okf/index.md", "200", "",
                  CHROME)
        self.assertEqual(requests_feed.kind_of(hit), "not_page")


class TestBothRoads(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.log(sorted(TestCounting.lines(self)))

    def collect_and_audit(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        return self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())

    def people(self):
        with History(self.box.db) as h:
            return h.db.execute("SELECT hits, views, readers FROM groups WHERE "
                                "site = ? AND day = ? AND grp = 'people'",
                                ("example.com", DAY.isoformat())).fetchone()

    def test_the_audit_agrees(self):
        code, out, err = self.collect_and_audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        self.assertEqual(self.people(), (8, 2, 1))

    def test_the_audit_agrees_with_a_site_setting(self):
        text = self.box.config.read_text().replace(
            "  require_rendering: false\n",
            "  require_rendering: false\n  not_pages_off: [markdown]\n"
            "  not_pages_extra: [/pricing/]\n")
        self.box.config.write_text(text)
        code, out, err = self.collect_and_audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        # The three .md requests are pages again (one more reader); /pricing/ is not.
        self.assertEqual(self.people(), (8, 4, 2))

    def test_the_audit_catches_a_main_road_without_the_list(self):
        with mock.patch.object(not_pages.Rules, "match", lambda self, path, url: ""):
            code, out, err = self.collect_and_audit()
        self.assertEqual(code, 1, out)
        self.assertIn("people", err)

    def test_the_audit_catches_a_main_road_that_ignores_the_setting(self):
        text = self.box.config.read_text().replace(
            "  require_rendering: false\n",
            "  require_rendering: false\n  not_pages_off: [markdown]\n")
        self.box.config.write_text(text)
        with mock.patch.object(not_pages, "from_config", lambda config: not_pages.STANDARD):
            code, out, err = self.collect_and_audit()
        self.assertEqual(code, 1, out)


class TestIndependence(unittest.TestCase):

    def test_the_audit_shares_only_the_name_lists(self):
        tree = ast.parse(Path(audit_not_pages.__file__).read_text())
        imported = {(n.module, a.name) for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(imported, {("not_pages", "DEFAULT"), ("not_pages", "OWN"),
                                    ("not_pages", "RULES")})
        self.assertNotIn("import re", Path(audit_not_pages.__file__).read_text())

    def test_the_lists_are_data(self):
        for name, (why, shapes) in not_pages.RULES.items():
            with self.subTest(name=name):
                self.assertTrue(why.endswith("."))
                self.assertLessEqual(set(shapes), {"ends", "tails", "segments", "keys", "numbers"})
                for words in shapes.values():
                    for w in words:
                        for part in (w if isinstance(w, tuple) else (w,)):
                            self.assertEqual(part, part.lower())
                            self.assertNotIn("/", part)

    def test_audit_is_page_uses_it(self):
        got = audit.line_hit(line(at(9), path="/okf/index.md"))
        self.assertFalse(audit.is_page(got))
        self.assertEqual(audit.not_page_entry(got), "markdown")


if __name__ == "__main__":
    unittest.main()
