"""SKALD-67 (GitHub #116): Traffic › Events says Form sent counts presses of a form's send
button, puts Leads & sales' own checked leads of the same days beside it, and says what the
tag counted before the version that leaves out a pop-up's close button, pickers and quizzes.
The tag's side is in tests/test_snippet.py and tests/js/skald-snippet.mjs."""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "tests" / "js" / "form-events-67.mjs"
EVENTS = ROOT / "skald" / "webapp" / "js" / "tabs" / "events.js"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class FormNotes(unittest.TestCase):
    def test_events_tab_in_node(self):
        done = subprocess.run(["node", str(JS)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("form-events-67: all passed", done.stdout)


class FormsSince(unittest.TestCase):
    def test_the_version_named_is_after_the_last_that_counted_close_buttons(self):
        """FORMS_SINCE names the release that ships the new form rule, never 2.59.0 or before
        (the note would clear days the old tag counted). The releaser sets it to the version."""
        since = re.search(r'export const FORMS_SINCE = "([0-9.]+)"', EVENTS.read_text(encoding="utf-8"))
        self.assertIsNotNone(since)
        want = tuple(int(x) for x in since.group(1).split("."))
        self.assertGreater(want, (2, 59, 0), "2.59.0 and before counted the close buttons")


class SameVersionEverywhere(unittest.TestCase):
    def test_the_docs_and_the_release_name_the_version_the_page_names(self):
        """The help, docs/BEACON.md and the CHANGELOG name the same version as FORMS_SINCE, and
        once a release section holds SKALD-67 its heading is that version: the releaser who
        picks another number changes them together, or this fails."""
        since = re.search(r'export const FORMS_SINCE = "([0-9.]+)"', EVENTS.read_text(encoding="utf-8")).group(1)
        help_text = (ROOT / "docs" / "help" / "tracking-script.md").read_text(encoding="utf-8")
        self.assertIn(f"Before Skald {since}, Form started and Form sent", help_text)
        beacon = (ROOT / "docs" / "BEACON.md").read_text(encoding="utf-8")
        self.assertIn(f"from {since})", beacon)
        # public/CHANGELOG.md here; CHANGELOG.md at the root of the public copy (make-public).
        log = next(p for p in (ROOT / "public" / "CHANGELOG.md", ROOT / "CHANGELOG.md")
                   if p.exists()).read_text(encoding="utf-8")
        self.assertIn(f"before {since} Form started and Form sent", log)
        for head, body in re.findall(r"^## (\d+\.\d+\.\d+)[^\n]*\n(.*?)(?=^## )", log, re.S | re.M):
            if "SKALD-67" in body:
                self.assertEqual(head, since, "the release that ships SKALD-67 is the version the page names")


if __name__ == "__main__":
    unittest.main()
