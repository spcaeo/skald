"""Settings > Organisation > Organisations in the browser (tests/js/orgs.mjs): the cards,
the search and order in the address, a card's drawer and its tabs (org=, otab=), a link to
an organisation not yours, New organisation, Archive asking first, a member's sites and
the "Organisation: <name> · Switch" line."""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE.parent / "skald" / "webapp" / "js"


class Page(unittest.TestCase):
    def test_the_page_its_drawer_and_the_address(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        done = subprocess.run(["node", str(HERE / "js" / "orgs.mjs")], capture_output=True, text=True,
                              timeout=60, env=dict(os.environ))
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertIn("orgs: all passed", done.stdout)

    def test_each_file_parses_and_stays_short(self):
        files = [JS / "tabs" / f"{n}.js" for n in ("orgs", "org-drawer", "org-members", "org-words", "org-line")]
        for path in files:
            with self.subTest(path=path.name):
                self.assertLess(len(path.read_text().splitlines()), 1000)
                if shutil.which("node"):
                    got = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True, timeout=60)
                    self.assertEqual(got.returncode, 0, got.stderr)


if __name__ == "__main__":
    unittest.main()
