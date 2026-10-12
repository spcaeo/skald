"""The About page's content is built from the docs: it must match them."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AboutData(unittest.TestCase):
    def test_the_built_file_matches_the_docs(self):
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "build-about.py"), "--check"], capture_output=True)
        self.assertEqual(done.returncode, 0, "skald/webapp/js/about-data.js is stale: run tools/build-about.py")

    def test_no_markup_from_the_docs_reaches_the_page(self):
        text = (ROOT / "skald" / "webapp" / "js" / "about-data.js").read_text(encoding="utf-8")
        for bad in ("<script", "<style", "javascript:", "<sub>", "<br"):
            self.assertNotIn(bad, text)

    def test_the_rename_checklist_stays_internal(self):
        text = (ROOT / "skald" / "webapp" / "js" / "about-data.js").read_text(encoding="utf-8")
        self.assertNotIn("Rename plan", text)


if __name__ == "__main__":
    unittest.main()
