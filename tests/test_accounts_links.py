"""One address for the links in account mails (accounts/links.py), the same
for the CLI (`skald accounts`) and the helper: --base-url when the CLI is
given one, else access.base_url, else dashboard.base_url, else the scheme
and host of dashboard.url (the helper: else its first --origin)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import auth_api  # noqa: E402
from skald.accounts import links  # noqa: E402

ALL = {"access": {"base_url": "https://a.example.com/"},
       "dashboard": {"base_url": "https://b.example.com", "url": "https://c.example.com/stats/"}}


def without(config, section, key):
    return {**config, section: {k: v for k, v in config[section].items() if k != key}}


class TestOrder(unittest.TestCase):

    def test_each_in_turn(self):
        self.assertEqual(links.base_url(ALL), "https://a.example.com")
        cfg = without(ALL, "access", "base_url")
        self.assertEqual(links.base_url(cfg), "https://b.example.com")
        cfg = without(cfg, "dashboard", "base_url")
        self.assertEqual(links.base_url(cfg), "https://c.example.com")
        cfg = without(cfg, "dashboard", "url")
        self.assertIsNone(links.base_url(cfg))
        self.assertEqual(links.base_url(cfg, allowed={"https://d.example.com"}),
                         "https://d.example.com")

    def test_the_cli_flag_overrides_the_config(self):
        self.assertEqual(links.base_url(ALL, override="https://e.example.com/"),
                         "https://e.example.com")
        self.assertIsNone(links.base_url(ALL, override="e.example.com"))   # not an address

    def test_not_an_address_is_skipped(self):
        cfg = {"access": {"base_url": "ftp://a.example.com"},
               "dashboard": {"base_url": "b.example.com", "url": "http://c.example.com:8080/x"}}
        self.assertEqual(links.base_url(cfg), "http://c.example.com:8080")

    def test_the_helper_uses_the_same_order(self):
        cfg = without(ALL, "access", "base_url")
        self.assertEqual(auth_api.base_url(cfg), "https://b.example.com")
        self.assertEqual(auth_api.link(cfg, None, "reset", "tok"),
                         "https://b.example.com/traffic-auth/reset?t=tok")


if __name__ == "__main__":
    unittest.main()
