"""Recorded journeys (2.43), the JavaScript side: the page helper
(webapp/snippet/journeys.js) and the Next.js relay example (kit/journeys/), each
run in node with every event checked by Skald's own contract and receiver."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "skald" / "kit" / "journeys"


def node(name: str) -> subprocess.CompletedProcess:
    script = ROOT / "tests" / "js" / name
    return subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=120,
                          cwd=ROOT)


class Journeys(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_page_helper_in_a_fake_page(self):
        """tests/js/journeys-snippet.mjs: nothing before consent, then the contract's events."""
        got = node("journeys-snippet.mjs")
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_nextjs_relay_signs_as_skald_checks(self):
        """tests/js/journeys-relay.mjs: the relay's signature passes receive.signed()."""
        got = node("journeys-relay.mjs")
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)

    def test_kit_files_have_no_placeholder_marks(self):
        """The kit is embedded in a template that reads two underscores as a placeholder."""
        files = [p for p in KIT.rglob("*") if p.is_file()]
        self.assertTrue(files)
        for path in files:
            self.assertNotIn("_" * 2, path.read_text(encoding="utf-8"), path.name)

    def test_helper_never_sends_an_address_or_reads_a_secret(self):
        text = (ROOT / "skald" / "webapp" / "snippet" / "journeys.js").read_text()
        self.assertNotIn("ip:", text)
        self.assertNotIn("secret", text.lower())
        for word in ("doNotTrack", "globalPrivacyControl", "keepalive", "same-origin"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
