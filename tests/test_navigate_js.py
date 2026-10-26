"""Finding and moving in the web app (2.13), run in node: the whole-row drill
every table builder attaches (tests/js/rows.mjs), the palette's search in the
figures (finder.mjs), Insights' order and folding (insights.mjs) and the
first-run checklist's items (setup.mjs), every table's sort, column filters,
column chooser and export (tables.mjs), the advanced filters' rules (rules.mjs) and
Leads & sales > Leads (sales-leads.mjs). tests/test_demo.py runs finder.mjs and
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

    def test_leads_list_names_for_admins_only_views_and_drawer(self):
        """Leads & sales > Leads (2.20): Name and Email columns only in an answer that holds
        them, a viewer never asks; Show left out; the board; a row opens the drawer."""
        self.assertIn("sales-leads: all passed", self.run_js("sales-leads.mjs"))

    def test_leads_period_all_time_empty_state_and_one_filter_row(self):
        """2.23: Leads & sales opens on 7 days unless the address names a period (Overview's
        Today is not carried in); All time from the first day with data; a period with no
        lead says how many the last 30 days or all time hold, counted from the same figure;
        one Filtered by line with every filter, Clear all; each filter checked against the
        rows and the figure; the top bar's chips no longer greyed on tabs that apply them."""
        self.assertIn("leads-period: all passed", self.run_js("leads-period.mjs"))

    def test_add_a_site_with_your_ai_agent(self):
        """2.31 (js/tabs/agent-setup.js, agent-watch.js): the agent tiles, one line per site
        with its code hidden and never in the address, the watch that ticks itself and stops
        when the dialog closes or the line runs out, the chat-only command, reloads."""
        self.assertIn("agent-setup: all passed", self.run_js("agent-setup.mjs"))

    def test_your_ai_agent_in_every_set_up_job(self):
        """2.39 (js/tabs/agent-first.js, agent-recs.js, checklist.js): each set-up dialog with
        an agent job and the MCP dialog open on Your AI agent or By hand; the line carries that
        job (sites/agentlink jobs); the checklist's one line for everything left, in the
        contract's order; the watch without logs ends on the report; Apply makes the by-hand
        saves and nothing is saved without it; the address round trip; the MCP guide button."""
        self.assertIn("agent-jobs: all passed", self.run_js("agent-jobs.mjs"))

    def test_the_period_dates_include_today_and_not_measured(self):
        """Release 2 (js/period-dates.js, data.js withToday): on 15 Jan, 7 days including
        today are 9-15 Jan against 2-8 Jan and 7 whole days 8-14 Jan against 1-7 Jan; a period
        before history says "before: not measured" and the first full comparison, never 0 or a
        rise; a change of 3 or fewer is about the same; inc and psort in the address, Back and
        Forward."""
        self.assertIn("period: all passed", self.run_js("period.mjs"))

    def test_page_figures_work_on_the_page_and_new_pages(self):
        """Release 2 (js/page-figs.js and the Summary cards): sums over whole days only, the
        work lists and their thresholds, the sorts, AI reads now against before, the new and
        updated pages card with its build-times note, the key figures and What changed."""
        self.assertIn("page-work: all passed", self.run_js("page-work.mjs"))

    def test_every_state_is_in_the_address_and_no_address_is(self):
        """2.21 (js/routekeys.js, js/overlays.js): each drawer and dialog writes its key,
        a link reopens it, Back closes it, a link to what is not kept opens the page with
        one plain line, and no value in the address is an IP address or holds an @."""
        self.assertIn("routes: all passed", self.run_js("routes.mjs"))

    def test_copy_and_open_on_every_url(self):
        """2.21 (js/urlactions.js): copy (the full URL, a tick, then hidden; a failure said)
        and open in a new tab on every path and URL; every page column draws them."""
        self.assertIn("urlactions: all passed", self.run_js("urlactions.mjs"))

    def test_copy_on_every_value_to_paste(self):
        """2.35 (the owner's rule, 2026-10-25): an IP address, a user agent, an email, a name,
        a crawler, a search term, a campaign or a reason gets the copy icon (a URL copy and
        open); tables, bar lists and drawers drawn with sample data; none on a blank or a
        number; no raw address, email or user agent in a cell, no second copy helper."""
        self.assertIn("copy-values: all passed", self.run_js("copy-values.mjs"))

    def test_what_visitors_are_doing_now(self):
        """Overview, Live (2.20): the newest visitors' paths, folded; the live diff; the pages
        read beside them; the drill-down narrowing the list, and its line when it cannot."""
        self.assertIn("live-doing: all passed", self.run_js("live-doing.mjs"))

    def test_security_sums_verdict_addresses_block_list_and_tabs(self):
        """Security (2.21): the period's sums, the verdict, rows joined to addresses (an admin
        asks, a viewer never does), the block list and its three exports by privacy mode, and
        every tab drawn with nothing null appended."""
        self.assertIn("security: all passed", self.run_js("security.mjs"))

    def test_lead_reference_steps_and_mark_as_test_in_every_drawer(self):
        """2.25 (js/tabs/leadref.js): the lead's own reference with its copy icon and its
        tool, every step, Mark as test / Not a test for owners and admins only (never a
        viewer or an editor), its confirm step, the POST and the toast; the same part in
        Leads' drawer, the visitor drawer, Find a person, the Conversions lists and
        Calendar bookings' rows."""
        self.assertIn("leadref: all passed", self.run_js("leadref.mjs"))

    def test_revenue_per_currency_withheld_days_address_and_drawer(self):
        """2.32.0 (js/tabs/sa-revenue.js, revfigs.js): money per currency in minor units by the
        file's decimals, never converted or added across; withheld days said in the
        conversions' words; currency, breakdown and tag in the address; copy and open on
        landing pages; the how-to when no value was ever sent; the lead drawer's sale facts."""
        self.assertIn("revenue: all passed", self.run_js("revenue.mjs"))

    def test_insights_todos_and_lost_pages(self):
        """2.35 (js/tabs/todos.js, todo-marks.js, todo-send.js, nf-lost.js): the to-dos from
        todos.json, Show the list and Copy link in the address, marks only with accounts,
        Send to team only with a mail server and a team, the lost pages' tabs and server
        lines, and the copy icons on every path, line and word value."""
        self.assertIn("todos: all passed", self.run_js("todos.mjs"))

    def test_page_change_tracker(self):
        """T8 (js/tabs/pagechange.js): Did my change work? on a page's view: the figures'
        words, too early with the verdict's day, unequal coverage and leads not recorded said,
        the sitemap's hint, the dialog's keys and POST (the note never in the address), and
        Insights' list with copy + open on every page."""
        self.assertIn("pagechange: all passed", self.run_js("pagechange.mjs"))

    def test_breadcrumbs_back_forward_and_scroll(self):
        """T9 (js/crumbs.js): the trail of places, cut back, sideways and capped; the line and
        Back to with a browser-like history (Back, Forward, a crumb), each step's scroll put
        back; a reload keeps the trail, a copied address starts its own."""
        self.assertIn("crumbs: all passed", self.run_js("crumbs.mjs"))


if __name__ == "__main__":
    unittest.main()
