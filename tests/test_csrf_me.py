"""SKALD-40: the page asks <page>/me (role, menu, CSRF value) whether or not the site's
funnels file exists yet, and a request the helper refuses as "out of date" asks /me again
and tries once more (tests/js/csrf-me.mjs).

The page knows that refusal by its first words (js/tabs/ipmanager.js OUT_OF_DATE). Every
helper module that checks the CSRF value must refuse with those words, or the page would
show the message without trying again."""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "tests" / "js"
CODE = ROOT / "skald"


class RefusalWords(unittest.TestCase):
    def test_every_csrf_check_refuses_with_the_words_the_page_knows(self):
        js = (CODE / "webapp" / "js" / "tabs" / "ipmanager.js").read_text(encoding="utf-8")
        words = re.search(r'export const OUT_OF_DATE = "([^"]+)";', js).group(1)
        self.assertEqual(words, "The page is out of date.")
        checking = [p for p in CODE.rglob("*.py")
                    if "csrf_ok(" in p.read_text(encoding="utf-8") and p.name != "auth_api.py"]
        self.assertGreater(len(checking), 10)
        for path in checking:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIn(words, path.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Page(unittest.TestCase):
    def test_me_without_funnels_and_one_more_try(self):
        done = subprocess.run(["node", str(JS / "csrf-me.mjs")], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("csrf-me: ok", done.stdout)


if __name__ == "__main__":
    unittest.main()
