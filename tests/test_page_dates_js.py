"""A page's own dates in the page (SKALD-64): js/page-dates.js's words, the marks on a
chart and the line for a page Skald could not read (tests/js/page-own-dates.mjs)."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent / "js" / "page-own-dates.mjs"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestPageDatesJs(unittest.TestCase):
    def test_the_words_and_the_marks(self):
        done = subprocess.run(["node", str(JS)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("page-dates: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
