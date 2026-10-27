"""User fetchers: one list on the server and the page, and NotebookLM's address check.

What is pinned:
- the page's FETCHERS (webapp/js/labels.js) is classify.AI_FETCHER_OWNERS, and every
  name AI_ASKED matches is in it: a list, not a "-User" ending, says which bot is a
  user fetcher, so Google-NotebookLM and BingPreview get the "user fetcher" tag;
- fetcherOf() names the assistant for a fetcher, any case, and null for a crawler;
- Google-NotebookLM is checked against Google's user-triggered fetcher lists:
  an address in them is verified, one outside them is not.
Addresses are RFC 5737.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import bot_verify  # noqa: E402
from skald.classify import AI_ASKED, AI_FETCHER_OWNERS  # noqa: E402

LABELS = ROOT / "skald" / "webapp" / "js" / "labels.js"


def js_table() -> dict:
    body = re.search(r"export const FETCHERS = \{(.*?)\};", LABELS.read_text(), re.S).group(1)
    return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', body))


class OneList(unittest.TestCase):

    def test_the_page_list_is_the_servers(self):
        self.assertEqual(js_table(), AI_FETCHER_OWNERS)

    def test_every_name_ai_asked_matches_is_listed(self):
        names = AI_ASKED.pattern.split("|")
        self.assertEqual({n.lower() for n in names}, set(AI_FETCHER_OWNERS))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class FetcherOf(unittest.TestCase):

    def test_names_the_assistant_for_a_fetcher_only(self):
        script = (f'import {{ fetcherOf }} from "{LABELS.as_uri()}";\n'
                  'const names = ["ChatGPT-User", "Google-NotebookLM", "google-notebooklm", "BingPreview",'
                  ' "Amzn-User", "Perplexity-User", "GPTBot", "Googlebot", "Some-User", "", null];\n'
                  'process.stdout.write(JSON.stringify(names.map(fetcherOf)));\n')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.mjs"
            path.write_text(script)
            got = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertEqual(json.loads(got.stdout),
                         ["ChatGPT", "Gemini", "Gemini", "Copilot", "alexa.amazon.com", "Perplexity",
                          None, None, None, None, None])

    def test_drill_takes_it_from_labels(self):
        drill = (LABELS.parent / "drill.js").read_text()
        self.assertIn("fetcherOf } from \"./labels.js\"", drill)
        self.assertNotIn("-User$/", drill)


class NotebookLMCheck(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        fetched = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for name, nets in (("google-common", ["192.0.2.0/28"]), ("google-special", ["192.0.2.16/28"]),
                           ("google-user", ["192.0.2.32/28"]), ("google-user-google", ["198.51.100.0/28"])):
            (self.dir / f"{name}.json").write_text(json.dumps(
                {"source": "test", "fetched": fetched, "networks": nets, "error": None}))

    def test_it_is_a_google_claim(self):
        self.assertEqual(bot_verify.vendor_of("Google-NotebookLM"), "google")
        self.assertEqual(bot_verify.method_of(bot_verify.vendor_of("Google-NotebookLM")), "ranges")

    def test_an_address_in_googles_user_fetcher_list_is_verified(self):
        v = bot_verify.Verifier(self.dir)
        self.assertEqual(v.status("Google-NotebookLM", "198.51.100.5"), "verified")
        self.assertEqual(v.status("Google-NotebookLM", "192.0.2.40"), "verified")
        self.assertEqual(v.status("Google-NotebookLM", "203.0.113.9"), "unverified")


if __name__ == "__main__":
    unittest.main()
