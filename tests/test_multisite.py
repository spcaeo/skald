"""Several sites in one install (multisite.py): a second site from its own
config file, collected, drawn and listed beside the first; --site picks one;
each keeps its own views and its own live files."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald.store import History  # noqa: E402

from support import CHROME, UTC, Sandbox, day_lines, line  # noqa: E402

DAY = date(2026, 10, 5)


class TestTwoSites(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(views=["{name: Guides, path_prefix: /guides/}"])
        (self.box.root / "shop.yml").write_text(
            "site:\n  name: shop.example\n  hosts: [shop.example]\n"
            "logs:\n  base: shop.log\n"
            "mail:\n  to:\n    - shop-owner@example.com\n")
        self.box.config.write_text(self.box.config.read_text() + "sites:\n  - shop.yml\n")
        self.box.log(day_lines(DAY, 3))
        noon = datetime(2026, 10, 5, 12, tzinfo=UTC)
        self.box.log([line(noon + timedelta(minutes=i), f"203.0.113.{60 + i}", "/cart",
                           CHROME, host="shop.example") for i in range(5)], "shop.log")

    def tearDown(self):
        self.box.close()

    def test_collected_drawn_and_listed_side_by_side(self):
        code, out, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            self.assertEqual(h.sites(), ["example.com", "shop.example"])
            shop = h.period("shop.example", DAY, DAY).totals
            self.assertEqual((shop.hits, shop.groups[next(iter(shop.groups))].hits), (5, 5))
            # The first site's view is not laid over the second.
            keys = {r[0] for r in h.db.execute("SELECT DISTINCT site FROM days")}
            self.assertEqual(keys, {"example.com", "example.com::guides", "shop.example"})
        self.assertEqual(self.box.run("--today", "2026-10-06", "audit")[0], 0)
        code, out, err = self.box.run("--today", "2026-10-06", "live")
        self.assertEqual(code, 0, err)
        www = self.box.root / "www"
        self.assertTrue((www / "shop.example" / "data" / "overview.json").exists())
        self.assertTrue((www / "example.com" / "guides" / "data" / "overview.json").exists())
        self.assertFalse((www / "shop.example" / "guides").exists())
        index = (www / "index.html").read_text()
        self.assertIn('href="example.com/"', index)
        self.assertIn('href="shop.example/"', index)
        sites = json.loads((www / "sites.json").read_text())
        self.assertEqual([s["name"] for s in sites["sites"]], ["example.com", "shop.example"])
        self.assertEqual(sites["sites"][0]["views"], [{"slug": "guides", "name": "Guides"}])
        mine = json.loads((www / "shop.example" / "data" / "sites.json").read_text())
        self.assertEqual(mine["current"], "shop.example")
        # Each site's live files are its own.
        self.assertTrue((self.box.root / "live-example.com.json").exists())
        self.assertTrue((self.box.root / "sites" / "shop.example" /
                         "live-shop.example.json").exists())

    def test_site_picks_one(self):
        code, out, err = self.box.run("--today", "2026-10-06", "--site", "shop.example",
                                      "collect")
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            self.assertEqual(h.sites(), ["shop.example"])
        self.assertEqual(self.box.run("--site", "nope", "collect")[0], 2)

    def test_a_missing_site_file_is_said(self):
        self.box.config.write_text(self.box.config.read_text() + "  - missing.yml\n")
        with self.assertRaises(SystemExit):
            self.box.run("--today", "2026-10-06", "collect")


if __name__ == "__main__":
    unittest.main()


class TestSmallYamlTopLevelList(unittest.TestCase):
    def test_sites_list_without_pyyaml(self):
        from skald.config import tiny_yaml
        got = tiny_yaml("site:\n  name: a\nsites:\n  - shop.yml\n  - 'blog.yml'\n")
        self.assertEqual(got["sites"], ["shop.yml", "blog.yml"])
        self.assertEqual(got["site"], {"name": "a"})


class TestSiteFlagBesideTokenSite(unittest.TestCase):
    def test_token_site_is_not_the_global_site(self):
        box = Sandbox()
        try:
            code, out, err = box.run("token", "create", "a script", "--site", "example.com")
            self.assertEqual(code, 0, err)
            self.assertTrue(out.startswith("skald_"))
        finally:
            box.close()
