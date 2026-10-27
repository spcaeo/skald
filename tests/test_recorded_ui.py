"""Recorded journeys on the dashboard (2.43, js/tabs/recorded.js): tests/js/recorded-ui.mjs
in node. The card on Traffic › Visitors, the session drawer (rj=), the visitor drawer's fold,
Settings › Leads & tools' row, Connect (rjc=connect) and its three paths."""
import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent / "js"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class RecordedUi(unittest.TestCase):
    def test_the_card_the_drawers_the_row_and_connect(self):
        done = subprocess.run(["node", str(JS / "recorded-ui.mjs")], capture_output=True,
                              text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("recorded-ui: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
