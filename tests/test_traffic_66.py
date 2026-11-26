"""SKALD-66 on Traffic: chart markers said plainly, why the Retention curve moves, the Time
tab's busiest and quietest hours, and an Events page that shows every event the site sends.
The browser side runs in node (tests/js/traffic-66.mjs); the Search tab's change against the
days before is in tests/test_search_reports.py and tests/js/search-reports.mjs."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent / "js"
ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TrafficTabs(unittest.TestCase):
    def test_markers_retention_time_and_events(self):
        done = subprocess.run(["node", str(JS / "traffic-66.mjs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("traffic-66: all passed", done.stdout)


class EveryEvent(unittest.TestCase):
    def test_the_page_knows_every_event_the_beacon_takes(self):
        """A new beacon event gets its plain words on the Events page, or this fails."""
        from skald.beacon import EVENTS, PAGE_VIEW
        src = (ROOT / "skald" / "webapp" / "js" / "tabs" / "events.js").read_text()
        start = src.index("export const MEANING")
        block = src[start:src.index("};", start)]
        for e in (*EVENTS, PAGE_VIEW):
            self.assertRegex(block, rf'(?:^|[\s{{,])"?{e}"?:', e)


if __name__ == "__main__":
    unittest.main()
