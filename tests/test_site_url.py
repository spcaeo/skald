"""Each site's mails link to its own dashboard (2.36.1): a site with no dashboard.url of
its own used the first site's, so every link in its security, summary and daily mails
opened the first site."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skald import multisite  # noqa: E402

FIRST = {"site": {"name": "example.com"},
         "dashboard": {"url": "https://stats.example.com/traffic/example.com/"}}


def other(name, **dash):
    got = multisite.merged(FIRST, {"site": {"name": name}, **({"dashboard": dash} if dash else {})})
    return multisite.own_url(FIRST, got)["dashboard"].get("url")


class OwnUrl(unittest.TestCase):
    def test_an_inherited_url_names_the_site(self):
        self.assertEqual(other("example.org"), "https://stats.example.com/traffic/example.org/")

    def test_a_site_of_its_own_keeps_it(self):
        self.assertEqual(other("example.org", url="https://example.org/stats/"),
                         "https://example.org/stats/")

    def test_a_url_not_ending_in_the_first_site_is_left(self):
        first = {"site": {"name": "example.com"}, "dashboard": {"url": "https://stats.example.com/"}}
        got = multisite.merged(first, {"site": {"name": "example.org"}})
        self.assertEqual(multisite.own_url(first, got)["dashboard"]["url"],
                         "https://stats.example.com/")

    def test_the_first_site_and_no_url_are_left(self):
        self.assertEqual(multisite.own_url(FIRST, dict(FIRST)), FIRST)
        bare = {"site": {"name": "example.com"}}
        self.assertEqual(multisite.own_url(bare, {"site": {"name": "example.org"}}),
                         {"site": {"name": "example.org"}})

    def test_the_first_site_is_not_changed(self):
        other("example.net")
        self.assertEqual(FIRST["dashboard"]["url"], "https://stats.example.com/traffic/example.com/")


if __name__ == "__main__":
    unittest.main()
