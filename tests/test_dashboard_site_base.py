"""A dashboard site's config: what it takes from the install's, and what not.

Pinned: the first site's `site:` section (asset prefixes, rendering rule,
legacy paths) never reaches a dashboard site, whose own name and hosts are
all it has there; the install's logs settings (the GeoIP file) do.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.accounts.site_configs import as_config  # noqa: E402
from skald.multisite import merged, tenant_base  # noqa: E402
from skald.rendering import ASSET_PREFIXES, asset_prefixes  # noqa: E402

INSTALL = {
    "site": {"name": "first.example", "hosts": ["first.example"],
             "asset_prefixes": ["/style.css", "/img/"], "require_rendering": False,
             "legacy_paths": ["/old/"]},
    "logs": {"dir": "/logs", "base": "first.log", "format": "nginx_extended",
             "country_db": "/geoip/country.mmdb"},
    "report": {"timezone": "UTC"},
}


class TestTenantBase(unittest.TestCase):

    def site(self) -> dict:
        entry = {"name": "second.example", "hosts": ["second.example", "www.second.example"],
                 "log_dir": "/ingest/second.example", "log_base": "access.log",
                 "format": "auto"}
        return merged(tenant_base(INSTALL), as_config(entry))

    def test_the_first_site_s_page_rules_stay_its_own(self):
        got = self.site()
        self.assertEqual(got["site"]["name"], "second.example")
        for key in ("asset_prefixes", "require_rendering", "legacy_paths"):
            self.assertNotIn(key, got["site"])
        self.assertEqual(asset_prefixes(got), ASSET_PREFIXES)

    def test_the_install_s_country_file_is_shared(self):
        got = self.site()
        self.assertEqual(got["logs"]["country_db"], "/geoip/country.mmdb")
        self.assertEqual(got["logs"]["dir"], "/ingest/second.example")
        self.assertEqual(got["logs"]["format"], "auto")

    def test_the_install_s_own_config_is_untouched(self):
        self.site()
        self.assertEqual(INSTALL["site"]["asset_prefixes"], ["/style.css", "/img/"])


if __name__ == "__main__":
    unittest.main()
