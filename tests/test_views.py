"""Path views: pre-built dashboard pages for a slice of the site.

A view is the same counting rules over fewer lines, so everything that holds
for the site must hold for each view - groups reconcile, nothing identifies
a visitor - and views that partition the paths must add up to the site.
"""
from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, check  # noqa: E402
from skald.config import View, tiny_yaml, views  # noqa: E402
from skald.store import History, view_key  # noqa: E402

from support import ASKED, GPTBOT, Sandbox, line  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 6)
VIEWS = ["{name: US English, exclude_prefix: /ca/}",
         "{name: Canada English, path_prefix: /ca/, exclude_prefix: /ca/fr/}",
         "{name: Canada French, path_prefix: /ca/fr/}"]
KEYS = ["us-english", "canada-english", "canada-french"]


def at(hour, minute=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=UTC)


def mixed_day() -> list[str]:
    """US: 2 people, GPTBot, a probe. Canada English: 1 person on /ca, one on
    /ca/pricing, ChatGPT-User. Canada French: 1 person cited from chatgpt."""
    return [
        line(at(9), "203.0.113.1", "/"),
        line(at(9, 5), "203.0.113.2", "/pricing"),
        line(at(9, 10), "198.51.100.40", "/guides/alpha", GPTBOT),
        line(at(9, 15), "198.51.100.52", "/.env", "curl/8.7.1", status=404),
        line(at(10), "203.0.113.3", "/ca"),
        line(at(10, 5), "203.0.113.4", "/ca/pricing"),
        line(at(10, 10), "198.51.100.41", "/ca/guides", ASKED),
        line(at(11), "203.0.113.5", "/ca/fr/", referrer="https://chatgpt.com/"),
    ]


class TestViewRules(unittest.TestCase):

    def test_a_trailing_slash_prefix_also_matches_the_bare_path(self):
        canada = View("Canada English", "/ca/", ("/ca/fr/",))
        self.assertTrue(canada.matches("/ca"))
        self.assertTrue(canada.matches("/ca/"))
        self.assertTrue(canada.matches("/ca/pricing"))
        self.assertFalse(canada.matches("/ca/fr"))
        self.assertFalse(canada.matches("/cat"))
        self.assertFalse(canada.matches("/CA/pricing"))

    def test_the_example_views_partition_every_path(self):
        found = views(tiny_yaml((Path(__file__).resolve().parent.parent
                                 / "config.example.yml").read_text()))
        self.assertEqual([v.slug for v in found], KEYS)
        for path in ("/", "/ca", "/ca/", "/ca/x", "/ca/fr", "/ca/fr/x", "/cat",
                     "/.env", "/fr/ca/", "*", ""):
            with self.subTest(path=path):
                self.assertEqual(sum(v.matches(path) for v in found), 1)

    def test_a_view_without_a_name_or_a_duplicate_is_refused(self):
        with self.assertRaises(ValueError):
            views({"dashboard": {"views": [{"path_prefix": "/a/"}]}})
        with self.assertRaises(ValueError):
            views({"dashboard": {"views": [{"name": "A b"}, {"name": "a-b"}]}})

    def test_several_exclusions_separated_by_spaces(self):
        got = views({"dashboard": {"views": [
            {"name": "Rest", "exclude_prefix": "/ca/ /blog/"}]}})[0]
        self.assertEqual(got.exclude, ("/ca/", "/blog/"))
        self.assertFalse(got.matches("/blog/x"))


class ViewCase(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox(views=VIEWS)
        self.box.log(mixed_day())

    def tearDown(self):
        self.box.close()

    def collect(self, *extra):
        return self.box.run("--today", "2026-10-07", "collect", *extra)


class TestCollectedViews(ViewCase):

    def test_each_view_is_stored_with_its_rule_and_reconciles(self):
        code, out, err = self.collect()
        self.assertEqual(code, 0, err)
        self.assertIn("and 3 views", out)
        with History(self.box.db) as h:
            self.assertEqual(h.sites(), ["example.com"])
            scopes = dict(h.db.execute("SELECT site, scope FROM days"))
            self.assertIsNone(scopes["example.com"])
            self.assertEqual(scopes["example.com::canada-english"],
                             "paths under /ca/ except under /ca/fr/")
            for key in KEYS:
                totals = h.period(view_key("example.com", key), DAY, DAY).totals
                self.assertEqual(check(totals), [], key)

    def test_views_that_partition_the_paths_add_up_to_the_site(self):
        self.collect()
        with History(self.box.db) as h:
            site = h.period("example.com", DAY, DAY).totals
            parts = [h.period(view_key("example.com", k), DAY, DAY).totals for k in KEYS]
        self.assertEqual(sum(p.hits for p in parts), site.hits)
        for g in Group:
            self.assertEqual(
                sum(p.groups[g].hits for p in parts if g in p.groups),
                site.groups[g].hits if g in site.groups else 0, g)
        us, ca_en, ca_fr = parts
        self.assertEqual(us.groups[Group.PEOPLE].visits, 2)
        self.assertEqual(us.groups[Group.BOTS].probes, 1)
        self.assertEqual(ca_en.groups[Group.PEOPLE].views, 2)
        self.assertEqual(dict(ca_en.groups[Group.ANSWER_ENGINE].tiers), {"asked": 1})
        self.assertEqual(ca_fr.groups[Group.PEOPLE].cited_visits, 1)

    def test_a_view_nobody_visited_is_a_verified_zero_not_withheld(self):
        self.box.log(mixed_day()[:4])            # nothing under /ca/ at all
        code, out, err = self.collect()
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            self.assertIs(h.status("example.com::canada-french", DAY), True)
            self.assertEqual(
                h.period("example.com::canada-french", DAY, DAY).totals.hits, 0)

    def test_backfill_recollects_a_day_stored_before_views_existed(self):
        plain = Sandbox()
        try:
            plain.log(mixed_day())
            plain.run("--today", "2026-10-07", "collect")
            self.box.db.write_bytes(plain.db.read_bytes())
        finally:
            plain.close()
        code, out, err = self.box.run("--today", "2026-10-07", "backfill", "--days", "1")
        self.assertEqual(code, 0, err)
        self.assertIn("ok 1", out)
        with History(self.box.db) as h:
            self.assertIs(h.status("example.com::canada-french", DAY), True)
        code, out, _ = self.box.run("--today", "2026-10-07", "backfill", "--days", "1")
        self.assertIn("skipped 1", out)


class TestViewPages(ViewCase):

    def setUp(self):
        super().setUp()
        self.collect()
        code, out, err = self.box.run("--today", "2026-10-07", "dashboard")
        self.assertEqual(code, 0, err)
        self.www = self.box.root / "www" / "example.com"

    def test_one_page_per_view_linked_from_every_page(self):
        main = (self.www / "index.html").read_text()
        self.assertIn('<a href="./" aria-current="page">All</a>', main)
        for key in KEYS:
            self.assertIn(f'href="{key}/"', main)
            page = (self.www / key / "index.html").read_text()
            self.assertIn('<a href="../">All</a>', page)
            self.assertIn(f'href="../{key}/" aria-current="page"', page)

    def test_a_view_page_shows_its_own_figures_and_rule(self):
        page = (self.www / "canada-french" / "index.html").read_text()
        self.assertIn("Traffic: example.com - Canada French", page)
        self.assertIn("requests for paths under /ca/fr/", page)
        self.assertIn('<td>Yesterday</td><td class="v">1</td>', page)
        self.assertIn("chatgpt.com", page)
        self.assertNotIn("/pricing", page)
        for forbidden in ("<script", "203.0.113.", "Mozilla/", "http-equiv"):
            self.assertNotIn(forbidden, page)

    def test_the_site_index_does_not_list_views_as_sites(self):
        index = (self.box.root / "www" / "index.html").read_text()
        self.assertIn('href="example.com/"', index)
        self.assertNotIn("::", index)


class TestViewsWithoutConfig(unittest.TestCase):

    def test_no_views_means_no_nav_and_no_view_rows(self):
        box = Sandbox()
        try:
            box.log(mixed_day())
            box.run("--today", "2026-10-07", "collect")
            box.run("--today", "2026-10-07", "dashboard")
            page = (box.root / "www" / "example.com" / "index.html").read_text()
            self.assertNotIn('aria-label="Views"', page)
            with History(box.db) as h:
                self.assertEqual(
                    [r[0] for r in h.db.execute("SELECT site FROM days")],
                    ["example.com"])
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
