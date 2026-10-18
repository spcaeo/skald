"""Finding and moving in the web app (2.13), run in node: the whole-row drill
every table builder attaches (tests/js/rows.mjs), the palette's search in the
figures (finder.mjs), Insights' order and folding (insights.mjs) and the
first-run checklist's items (setup.mjs), every table's sort, column filters,
column chooser and export (tables.mjs) and the advanced filters' rules (rules.mjs). tests/test_demo.py runs finder.mjs and
insights.mjs again on the demo's own files."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

JS = Path(__file__).resolve().parent / "js"


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Node(unittest.TestCase):
    def run_js(self, name: str, *args: str) -> str:
        done = subprocess.run(["node", str(JS / name), *args], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def test_every_table_builder_attaches_the_row_drill(self):
        self.assertIn("rows: all passed", self.run_js("rows.mjs"))

    def test_the_palette_finds_names_in_the_figures(self):
        self.assertIn("finder: all passed", self.run_js("finder.mjs"))

    def test_insights_biggest_first_one_card_per_subject(self):
        self.assertIn("insights: all passed", self.run_js("insights.mjs"))

    def test_the_first_run_checklist(self):
        self.assertIn("setup: all passed", self.run_js("setup.mjs"))

    def test_every_table_sorts_filters_chooses_columns_and_exports_what_it_shows(self):
        self.assertIn("tables: all passed", self.run_js("tables.mjs"))

    def test_the_advanced_filters_rules_and_their_address(self):
        self.assertIn("rules: all passed", self.run_js("rules.mjs"))


if __name__ == "__main__":
    unittest.main()
