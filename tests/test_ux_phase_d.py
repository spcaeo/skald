"""The UX rework, Phase D (2.42; docs/plans/ux-build-shots/phase-d/README.md): each new flow
run in node against a fake helper, with the address round trip, the who-step paths and the
old links that still open.

- tests/js/mail-ready.mjs: "Get the daily mail" with no mail server says so at once, with
  "Who will set it up?", and never waits for a confirm mail that cannot go.
- tests/js/export.mjs: Export asks "What do you need?" and shows only that path; dlg=report
  (the old report builder's links) opens it.
- tests/js/add-site.mjs: Add a site in two steps, the who-step and the old step numbers.
- tests/js/visitor-short.mjs: the visitor drawer, state first, then a short timeline.
- tests/js/help-guides.mjs: the guides' search, and every "Read the guide" lands on a part
  that exists.
"""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = ROOT / "tests" / "js"


def run(name: str) -> subprocess.CompletedProcess:
    return subprocess.run(["node", str(NODE / f"{name}.mjs")], capture_output=True, text=True,
                          timeout=120, cwd=ROOT)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class PhaseD(unittest.TestCase):
    def check(self, name: str):
        done = run(name)
        self.assertEqual(done.returncode, 0, done.stderr[-4000:])
        self.assertIn(f"{name}: all passed", done.stdout)

    def test_mail_with_no_mail_server(self):
        self.check("mail-ready")

    def test_export_asks_what_you_need(self):
        self.check("export")

    def test_add_a_site_in_two_steps(self):
        self.check("add-site")

    def test_the_visitor_drawer(self):
        self.check("visitor-short")

    def test_help_guides(self):
        self.check("help-guides")


if __name__ == "__main__":
    unittest.main()
