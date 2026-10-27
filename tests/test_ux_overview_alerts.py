"""Overview and Site › Alerts to the UX audit's mockups (2.41, docs/UI-RULES.md).

- tests/js/si-alerts.mjs: alerts in groups, one count of what needs you (badge, bell and
  page agree), one primary Fix, Fix opens "Who will do it?" with the kind's steps, kept
  in the address; tests/js/ov-setup.mjs: the set-up line reads the checklist's words.
- The live Summary opens on the figures: the map, the visitors now and the flow are on
  Real time only, the set-up checklist is one line, the footnote is behind the "?".
- The top bar: 7, 30, 90 days and More; one search; Refresh, saved views and export in
  More; Help only in the menu.
- Every "Who will do it?" question is the shared one (ui/who.js).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "skald" / "webapp" / "js"
TABS = JS / "tabs"


def code(path: Path) -> str:
    """The file without its comments, so a comment naming a thing is not the thing."""
    text = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    return "\n".join(line.split("//")[0] if not line.strip().startswith("//") else "" for line in text.splitlines())


class Node(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_alerts_and_setup_line_in_node(self):
        for name in ("si-alerts", "ov-setup"):
            done = subprocess.run(["node", str(ROOT / "tests" / "js" / f"{name}.mjs")], capture_output=True, text=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn(f"{name}: all passed", done.stdout)


class Layout(unittest.TestCase):
    def test_live_summary_has_the_figures_and_links_to_real_time(self):
        today = code(TABS / "ov-today.js")
        for gone in ("placesCard", "doingCard", "flowCard", "setupChecklist", "td-foot"):
            self.assertNotIn(gone, today)
        self.assertIn("setupStrip(m)", today)
        self.assertIn('hrefTo("overview/realtime")', today)
        self.assertIn('help("Today so far"', today)
        self.assertIn("setupStrip(m)", code(TABS / "ov-summary.js"))
        self.assertNotIn("setupChecklist", code(TABS / "ov-summary.js"))
        rt = code(TABS / "realtime.js")
        self.assertIn("flowCard(m)", rt, "the flow is on Real time")
        self.assertIn("worldMap(", rt, "and the map")

    def test_site_alerts_is_the_grouped_page(self):
        site = code(TABS / "s-site.js")
        self.assertIn('import alerts from "./si-alerts.js"', site)
        self.assertIn("needsYou(", site)
        self.assertIn("needsYou(", code(JS / "extras.js"), "the bell")
        self.assertIn("needsYou(", code(JS / "main.js"), "the Site badge in the menu")
        self.assertIn('"alfix"', code(JS / "overlays.js"))

    def test_the_top_bar(self):
        main = code(JS / "main.js")
        bar = main[main.index("function drawBar"):main.index("function fitBar") if "function fitBar" in main else len(main)]
        self.assertIn('MAIN_RANGES = ["7d", "30d", "90d"]', main)
        for gone in ("help-btn", "exportMenu(", "searchBox(", "saved()", '"btn refresh"'):
            self.assertNotIn(gone, bar)
        more = main[main.index("function moreMenu"):main.index("async function doRefresh")]
        # 2.42: one Export, which asks what you need (export-dialog.js), in place of four items.
        for item in ("Recount today now", "Saved views", 'item("Export"'):
            self.assertIn(item, more)
        for gone in ("Tables on this tab (ZIP)", "Print this tab", "Report builder"):
            self.assertNotIn(gone, more)
        self.assertNotIn("narrow-only", more, "in More at every width")
        # The approved mockup's seven (2.43): title, period, Compare, filter, search, alerts, More.
        # The period's More is the group's last button; the filter is on the right, an icon.
        self.assertIn('"Date range", more.toggle)', bar)
        self.assertNotIn("mid.push(filtersButton", bar)
        self.assertLess(bar.index("filtersButton(model, s)"), bar.index("ui-search"), "the filter comes before the search")
        self.assertIn(".bar .fp-btn .f-l { display: none; }", (JS.parent / "css" / "ui.css").read_text())

    def test_one_who_question(self):
        for f in sorted(JS.rglob("*.js")):
            if f.name in ("who.js", "help-data.js", "about-data.js"):
                continue
            text = code(f)
            self.assertNotIn('"Who will do it?"', text, f"{f.name} asks it itself: use ui/who.js")
        self.assertIn("whoStep(", code(TABS / "todo-fix.js"))
        self.assertIn("whoDialog(", code(TABS / "si-alerts.js"))


if __name__ == "__main__":
    unittest.main()
