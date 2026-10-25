"""The dashboard never shows a control or a figure that is not true for the tab:
a tab with its own period shows a fixed chip instead of the period picker, a filter
a tab cannot apply is said in a banner with the way to the filtered figures, and
what the site never sent is "not set up", never 0 (tests/js/notset.mjs for the rules)."""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "skald" / "webapp" / "js"


def tab_line(section: str, key: str) -> str:
    for line in (JS / "tabs" / f"s-{section}.js").read_text().splitlines():
        if line.strip().startswith(f'["{key}",'):
            return line
    raise AssertionError(f"{section}/{key} not found")


class OwnPeriod(unittest.TestCase):
    # Tabs whose figures keep a period of their own: no picker, a chip with the period.
    OWN = [("overview", "realtime"), ("overview", "insights"), ("site", "alerts"), ("site", "requests"), ("ai", "rules")]

    def test_own_period_tabs_hide_the_picker_and_say_their_period(self):
        for section, key in self.OWN:
            line = tab_line(section, key)
            self.assertIn("ranged: false", line, f"{section}/{key} shows a picker it ignores")
            self.assertRegex(line, r"period: ", f"{section}/{key} does not say its own period")

    def test_bar_draws_the_chip_where_the_picker_was(self):
        main = (JS / "main.js").read_text()
        self.assertIn("ranged ? range : periodChip(s)", main)
        # Settings pages are forms: no period, page group or filters.
        self.assertRegex(main, r"const noData = \(s\) => .*S\.inSettings\(s\.tab\)")

    def test_request_log_chip_names_its_hours(self):
        src = (JS / "tabs" / "si-requests.js").read_text()
        self.assertIn("export const logPeriod", src)
        self.assertIn('#bar .period-chip b', src)


class Filters(unittest.TestCase):
    def test_unapplied_filter_banner_links_to_the_filtered_view(self):
        main = (JS / "main.js").read_text()
        self.assertIn("filterBanner(s)].filter(Boolean)", main)
        self.assertIn("rulesBanner(model, s)", main)
        # The banner and the chips live in filterpanel.js since the advanced filters (2.13).
        panel = (JS / "filterpanel.js").read_text()
        self.assertIn("This tab shows all visitors", panel)
        self.assertIn("S.set({ dd: encodeDrill([[k, v]]) })", panel)
        self.assertIn("each visit, on Traffic › Visitors", panel)

    def test_country_chip_shows_the_full_name(self):
        panel = (JS / "filterpanel.js").read_text()
        # Flag and three-letter code on the chip; the full name in its tooltip.
        self.assertIn('x.dim === "country" ? x.vals.map(countryName).join(", ")', panel)
        self.assertIn("[flagEl(x.vals[0]), country(x.vals[0])]", panel)


class NotSetUp(unittest.TestCase):
    def test_pages_use_the_shared_rules(self):
        uses = {"events.js": "everSent", "leads.js": "neverRecorded", "funnels.js": "neverRecorded",
                "uptime.js": "heartbeatOn", "quality.js": "quietLimit"}
        for name, fn in uses.items():
            src = (JS / "tabs" / name).read_text()
            self.assertRegex(src, rf'import \{{[^}}]*\b{fn}\b[^}}]*\}} from "\.\./notset\.js"', name)

    def test_no_zero_share_for_a_row_without_visitors(self):
        src = (JS / "tabs" / "leadfigs.js").read_text()
        self.assertNotIn("share(x.v || 0, sum)", src)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_rules(self):
        got = subprocess.run(["node", str(ROOT / "tests" / "js" / "notset.mjs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("notset: ok", got.stdout)


class LeadSources(unittest.TestCase):
    def test_overview_lead_tiles_name_their_count(self):
        # Summary's tiles moved to ov-tiles.js (release 2); the Leads tile still names its count.
        src = (JS / "tabs" / "ov-tiles.js").read_text()
        self.assertIn("function leadSource", src)
        self.assertIn('lsrc: tools ? "all" : ""', src)

    def test_pipeline_tools_says_overviews_figure_from_the_same_sum(self):
        src = (JS / "tabs" / "sa-pipeline.js").read_text()
        self.assertIn("const got = leadsOn(m,", src)
        # 2.20: Summary's Leads number (Pipeline's line until 2.18) says it is Overview's figure.
        self.assertIn("The same figure as Overview's Leads tile.", src)
        # 2.23: Leads counts the same sum over the file its filters narrow (sa-filters.js figureFile).
        self.assertIn("leadsOn(fm, daysOf(m, r))", (JS / "tabs" / "sa-leads.js").read_text())
        # Overview's tiles sum with the same function.
        self.assertIn("leadsOn(m, r.kind", (JS / "tabs" / "ov-tiles.js").read_text())

    def test_bookings_collapse_breakdowns_never_recorded(self):
        src = (JS / "tabs" / "conversions.js").read_text()
        self.assertIn("unrecordedNote(blank)", src)
        self.assertTrue(re.search(r"function unrecorded\(dim, t, acts\)", src))


if __name__ == "__main__":
    unittest.main()
