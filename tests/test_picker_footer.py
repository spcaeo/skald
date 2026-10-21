"""The site picker's footer line, as every dashboard page has it (brand.release_line)."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skald import brand, site_picker  # noqa: E402

BUILT = {"name": "Skald", "version": "2.16.0", "tagline": "Every visit, truly told.", "release": 31,
         "commit": "ceffe30", "deployed_at": "2026-10-21T12:56:20Z"}
NOW = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)


class ReleaseLine(unittest.TestCase):
    def test_in_the_sites_zone_else_utc(self):
        self.assertEqual(brand.release_line("America/New_York", BUILT),
                         ("Live · v2.16.0 · released 21 Oct 2026 08:56 EDT",
                          "Skald v2.16.0 · release 31 · ceffe30"))
        self.assertEqual(brand.release_line(None, BUILT)[0], "Live · v2.16.0 · released 21 Oct 2026 12:56 UTC")
        self.assertEqual(brand.release_line("Not/AZone", BUILT)[0], "Live · v2.16.0 · released 21 Oct 2026 12:56 UTC")

    def test_without_a_deploy_time_or_a_version(self):
        self.assertEqual(brand.release_line(None, {**BUILT, "deployed_at": None})[0], "Live · v2.16.0")
        self.assertEqual(brand.release_line(None, {**BUILT, "version": ""}), ("", ""))


class Picker(unittest.TestCase):
    def page(self, zones):
        sites = [{"name": f"s{i}.example.com", "path": f"s{i}/", "today": {"timezone": z}} for i, z in enumerate(zones)]
        with mock.patch.object(brand, "load", lambda *a, **k: BUILT):
            return site_picker.render(sites, NOW)

    def test_the_picker_shows_it_in_the_one_zone_of_its_sites(self):
        html = self.page(["America/New_York", "America/New_York"])
        self.assertIn('<p class="pk-build" title="Skald v2.16.0 · release 31 · ceffe30">'
                      "Live · v2.16.0 · released 21 Oct 2026 08:56 EDT</p>", html)

    def test_sites_in_several_zones_get_utc(self):
        self.assertIn("released 21 Oct 2026 12:56 UTC", self.page(["America/New_York", "Asia/Kolkata"]))


if __name__ == "__main__":
    unittest.main()
