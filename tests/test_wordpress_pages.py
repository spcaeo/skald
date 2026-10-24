"""A site's own page about WordPress is not a probe (2.31.1).

skaldanalytics.com's /integrations/wordpress/ (its WordPress plugin page) was read as a
WordPress probe: its readers' page views left the counts, and Security called its 200 a
possible exposure. The bare words `wordpress` and `wp` are a probe only at the start of
the path; WordPress's own names (wp-admin, wp-includes, xmlrpc...) are one anywhere."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.classify import PROBE  # noqa: E402
from skald.security_names import CATEGORIES  # noqa: E402

WORDPRESS = next(rx for key, _, rx in CATEGORIES if key == "wordpress")

PAGES = ["/integrations/wordpress/", "/blog/category/wordpress/", "/blog/category/wp/",
         "/docs/wordpress-plugin/", "/guides/wordpress.html", "/lead-attribution/wordpress-forms/"]
PROBES = ["/wordpress/", "/wordpress", "//wordpress/wp-includes/wlwmanifest.xml",
          "//wp/wp-includes/wlwmanifest.xml", "/wp/", "/wp-login.php", "/blog/wp-admin/",
          "/site/wp-includes/wlwmanifest.xml", "/xmlrpc.php", "/old/wp-content/x.php",
          "/wp-json/wp/v2/users", "/shop/wp-config.php.bak"]


class WordPressPages(unittest.TestCase):
    def test_a_page_about_wordpress_is_not_a_probe(self):
        for path in PAGES:
            self.assertIsNone(PROBE.search(path), path)
            self.assertIsNone(WORDPRESS.search(path), path)

    def test_scanner_paths_still_are(self):
        for path in PROBES:
            self.assertIsNotNone(PROBE.search(path), path)
            self.assertIsNotNone(WORDPRESS.search(path), path)


if __name__ == "__main__":
    unittest.main()
