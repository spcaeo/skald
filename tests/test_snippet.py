"""skald.js, the one-line install (skald/webapp/snippet/skald.js):
small, self-contained, no way to run code from a string, and its behaviour
(tests/js/skald-snippet.mjs, a tiny fake DOM) when node is installed."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "skald" / "webapp" / "snippet" / "skald.js"
BEHAVIOUR = ROOT / "tests" / "js" / "skald-snippet.mjs"
EVENTS_TAB = ROOT / "skald" / "webapp" / "js" / "tabs" / "events.js"
# The budget: 5 KB until 2026-10-11, 6 KB since the tag sends scroll_75,
# copy_text, 404_view, contact/waitlist submits and adopts an ID from your
# other domains; 6.5 KB since it asks the beacon once a day whether Skald
# shares the ID across subdomains (beacon.share_subdomains).
BUDGET = 6656
# Events the tag builds from two parts: "<data-skald or form>_<start|submit>",
# "calendly_" + the CAL map's value.
COMPOSED = {"form_start", "form_submit", "signup_start", "signup_submit", "contact_submit",
            "waitlist_submit", "calendly_open", "calendly_time_selected", "calendly_booked"}
# The only URLs in the file: the embed origins whose window messages it reads.
ORIGINS = {"https://calendly.com", "https://app.cal.com"}

sys.path.insert(0, str(ROOT))

from skald import beacon  # noqa: E402


class Snippet(unittest.TestCase):
    def setUp(self):
        self.text = JS.read_text(encoding="utf-8")

    def test_under_the_size_budget(self):
        self.assertLess(len(self.text.encode()), BUDGET)

    def test_no_external_urls(self):
        found = set(re.findall(r"https?://[A-Za-z0-9.\-]+", self.text))
        self.assertLessEqual(found, ORIGINS)
        self.assertNotIn("//cdn", self.text)
        self.assertNotIn("import(", self.text)
        self.assertNotRegex(self.text, r"createElement\(\s*['\"]script")

    def test_nothing_that_runs_strings_or_writes_html(self):
        for bad in ("eval(", "innerHTML", "outerHTML", "insertAdjacentHTML", "new Function",
                    "document.write", "setTimeout(\"", "setTimeout('"):
            self.assertNotIn(bad, self.text)

    def test_never_reads_a_field_value(self):
        self.assertNotRegex(self.text, r"\.value\b")
        self.assertNotIn("FormData", self.text)
        self.assertNotIn("elements", self.text)

    def test_served_switch_and_privacy_signals(self):
        self.assertEqual(self.text.count("IDS=1"), 1)
        for word in ("doNotTrack", "globalPrivacyControl", "sendBeacon", "keepalive",
                     "skald.vid", "utm_content", "link-domains", "share-subdomains",
                     "accept-id", "replaceState"):
            self.assertIn(word, self.text)

    def test_sends_only_events_the_beacon_takes(self):
        named = set(re.findall(r'"((?:[a-z]+_)+(?:start|submit|open|selected|booked|click|view))"',
                               self.text))
        named.discard("time_selected")          # the CAL map's value; "calendly_" is added
        named |= {"calendly_" + x for x in ("open", "time_selected", "booked")}
        named |= COMPOSED | {"scroll_75", "copy_text", "404_view"}
        self.assertGreaterEqual(len(named), 20)
        self.assertLessEqual(named, set(beacon.EVENTS) | {beacon.PAGE_VIEW})

    def test_every_event_is_sent_by_the_tag_or_named_as_your_own_code(self):
        """The Events page and the guide list each event; the tag sends every
        one but beacon.CODE_ONLY, which only the site's own code sends."""
        for event in beacon.EVENTS:
            literal = f'"{event}"' in self.text
            if event in beacon.CODE_ONLY:
                self.assertFalse(literal or event in COMPOSED, event)
            else:
                self.assertTrue(literal or event in COMPOSED, f"skald.js never sends {event}")
        for part in ("(contact|waitlist)", '"signup"', '"calendly_"', '[data-skald="404"]'):
            self.assertIn(part, self.text)
        tab = re.search(r"const CODE_ONLY = \[([^\]]*)\]", EVENTS_TAB.read_text(encoding="utf-8"))
        self.assertIsNotNone(tab, "events.js names the events only your own code sends")
        self.assertEqual(tuple(re.findall(r'"([a-z0-9_]+)"', tab.group(1))), beacon.CODE_ONLY)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_node_check(self):
        got = subprocess.run(["node", "--check", str(JS)], capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_behaviour_in_a_fake_dom(self):
        got = subprocess.run(["node", str(BEHAVIOUR)], capture_output=True, text=True,
                             timeout=120)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)


if __name__ == "__main__":
    unittest.main()
