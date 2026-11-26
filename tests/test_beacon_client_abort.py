"""SKALD-15: a page that closes before the beacon helper answers must still be logged with
the helper's 204 and site, or the events audit finds the spool a few lines ahead of nginx
and withholds the day (two live sites, every day from 16 Nov 2026).
`proxy_ignore_client_abort on` makes nginx wait for the helper. Checked by hand against a
real nginx in the image: today's setting logged "499 -" for each early close the helper
kept; with it, "204 <site>"."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def beacon_location(text: str) -> str:
    m = re.search(r"location = /traffic-beacon \{(.*?)\n\s*\}", text, re.S)
    assert m, "no beacon location"
    return m.group(1)


class ClientAbort(unittest.TestCase):
    def test_the_image_waits_for_the_helper(self):
        loc = beacon_location((ROOT / "docker" / "nginx.conf").read_text())
        self.assertRegex(loc, r"\n\s*proxy_ignore_client_abort on;")
        self.assertIn("access_log /var/log/nginx/skald-beacon.log skald_beacon;", loc)

    def test_the_documented_setups_say_the_same(self):
        for doc in ("docs/BEACON.md", "DEPLOY.md"):
            with self.subTest(doc=doc):
                self.assertRegex(beacon_location((ROOT / doc).read_text()), r"\n\s*proxy_ignore_client_abort on;")

    def test_only_the_beacon_waits(self):
        """The rest of the site still lets a closed page go: only the counted beacon waits."""
        text = (ROOT / "docker" / "nginx.conf").read_text()
        self.assertEqual(text.count("proxy_ignore_client_abort on;"), 1)


if __name__ == "__main__":
    unittest.main()
