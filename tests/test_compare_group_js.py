"""Compare by page group (SKALD-63), run in node: a page group asks its own group's compare
(tests/js/compare-group.mjs); the server's side is in tests/test_compare.py."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent / "js"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class CompareGroup(unittest.TestCase):
    def test_a_page_group_asks_its_own_compare_and_the_demo_never_asks_the_helper(self):
        done = subprocess.run(["node", str(JS / "compare-group.mjs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("compare-group: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
