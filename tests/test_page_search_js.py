"""Finding a page by its full address or its title in the tables (SKALD-70):
js/search-words.js and the titles in js/page-dates.js (tests/js/page-search-words.mjs)."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent / "js" / "page-search-words.mjs"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestPageSearchJs(unittest.TestCase):
    def test_addresses_titles_and_a_site_without_titles(self):
        done = subprocess.run(["node", str(JS)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("page search: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
