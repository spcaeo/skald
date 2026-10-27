"""AI & bots, Traffic, Leads & sales and Security to the UX audit's rules (2.42, docs/UI-RULES.md).

- tests/js/phase-c.mjs: "Show all (N)", a fold kept in the address, the pages AI can't read
  well by what to do.
- AI & bots › Assistants opens on three figures, two short lists and one card with the
  screen's one primary button (Let AI read the site better, fixit=airead); the tables,
  charts and logs are under one fold kept in the address (ai_view=open). Crawlers folds its
  details the same way.
- A screen's Fix (tabs/fixit.js) is a route key of its own, restored from the address, and
  offers My AI agent only through a job the agent already has.
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
    def test_shared_pieces_in_node(self):
        done = subprocess.run(["node", str(ROOT / "tests" / "js" / "phase-c.mjs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("phase-c: all passed", done.stdout)


class AiAndBots(unittest.TestCase):
    def test_assistants_answers_first(self):
        src = code(TABS / "ai-assistants.js")
        top = src.split("export default function assistants", 1)[1].split("function details", 1)[0]
        for part in ("aiTiles(", "Which assistant sent people", "Which assistant read for someone", "readCard(", 'urlFold("ai"'):
            self.assertIn(part, top)
        # The tables and charts are drawn only inside the fold.
        for part in ("tierChart(", "byName(", "costSection(", "formatsSection(", "notReadWell(", "aiChanges("):
            self.assertNotIn(part, top)
            self.assertIn(part, src.split("function details", 1)[1])

    def test_one_primary_on_assistants(self):
        card = code(TABS / "aiready.js").split("export function readCard", 1)[1]
        self.assertEqual(card.count("primary("), 1)
        self.assertIn('"Let AI read the site better"', card)

    def test_crawlers_fold_their_details(self):
        src = code(TABS / "ai-crawlers.js")
        self.assertIn('urlFold("crawl"', src)
        fold = src.split('urlFold("crawl"', 1)[1]
        for part in ("formatsSection(", "costSection(", "verifySection("):
            self.assertIn(part, fold)


class Traffic(unittest.TestCase):
    def test_visitors_list_first_with_a_switch_in_the_address(self):
        src = code(TABS / "tr-visitors.js")
        self.assertIn('subView("vis")', src)
        main = src.split("export default function visitors", 1)[1]
        self.assertLess(main.index("listOrFlow("), main.index("newReturningCard("), "the visits before the cards")
        self.assertIn('urlFold("visx"', main)
        self.assertIn("Where visits ended", main.split('urlFold("visx"', 1)[1])
        self.assertIn('limit: 12, sortKey: "start"', (TABS / "visitlist.js").read_text())

    def test_sources_grid_first_notes_behind_help(self):
        src = code(TABS / "tr-sources.js").split("export default function sources", 1)[1]
        self.assertIn('help("Sources"', src)
        fold = src.split('urlFold("srcx"', 1)[1]
        for part in ("directPanel(", "firstTouch(", "campaignParts("):
            self.assertIn(part, fold)
        # The method notes go into the "?" (the about list), not under the grid.
        about, after = src.split("const about", 1)[1].split("out.push(", 1)
        for part in ("compareNote(c)", "socialNote(social)", "leadNote(lb, TOUCH)"):
            self.assertIn(part, about)
            self.assertNotIn(part, after)

    def test_pages_landing_grid_first_and_one_primary_in_a_story(self):
        src = code(TABS / "tr-pages.js").split("export default function pages", 1)[1]
        self.assertIn('urlFold("pgx"', src)
        self.assertLess(src.index('ns: "lp"'), src.index('urlFold("pgx"'))
        self.assertIn("details.push(", src)
        story = code(TABS / "pagestory.js")
        self.assertNotIn('class: "btn primary"', story, "Mark a change is the story's one primary")


class SameWordsForTwoFigures(unittest.TestCase):
    def test_leads_and_summary_say_why_they_differ(self):
        live = code(TABS / "sa-period.js").split("export function liveNote", 1)[1]
        self.assertIn("so their figures differ", live)
        self.assertIn("no demos booked", live)
        leads = code(TABS / "leads.js")
        self.assertIn("otherFigure(s, r)", leads)
        self.assertIn('tab: "sales/leads"', leads.split("function otherFigure", 1)[1])

    def test_retention_tile_names_the_weeks_of_the_chip(self):
        src = code(TABS / "tr-retention.js")
        self.assertIn("seenIn(file, g, cohorts, counted)", src)
        self.assertIn("before what is kept begins", src.split("export function seenIn", 1)[1])


class Security(unittest.TestCase):
    def test_exposed_has_one_fix_only_when_there_is_one(self):
        src = code(TABS / "sec-exposed.js")
        self.assertEqual(src.count("primary("), 1)
        self.assertIn('openFixit("exposed"', src)
        self.assertIn("e.possible ? fixButton(m) : null", src)
        self.assertIn('urlFold("sxx"', src)

    def test_block_list_has_block_them(self):
        src = code(TABS / "sec-block.js")
        self.assertEqual(src.count("primary("), 1)
        self.assertIn('openFixit("block"', src)
        self.assertIn('class: "btn", onclick: () => download', src, "the downloads stay plain buttons")


class Polish(unittest.TestCase):
    def test_period_options_have_one_place_each(self):
        # 2.43: Include today is one press, a switch on Summary's and Pages' period line; the
        # More menu no longer has it. Compare stays the top bar's menu only.
        line = code(JS / "period-line.js")
        self.assertEqual(line.count('role: "switch"'), 1)
        self.assertIn('S.set({ inc: on ? "" : "1" })', line)
        self.assertNotIn("cmp:", line, "Compare is not switched here")
        more = code(JS / "main.js").split("function rangeMore", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("Include today", more)
        self.assertNotIn("inc:", more)

    def test_the_trail_line_is_the_back_link_alone(self):
        draw = code(JS / "crumbs.js").split("function draw(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("cr-back", draw)
        self.assertNotIn('h("ol"', draw)

    def test_summary_folds_the_rest(self):
        src = code(TABS / "ov-summary.js")
        self.assertIn('urlFold("ovx"', src)
        self.assertIn("out = foldTheRest(out);", src)


class Fixit(unittest.TestCase):
    def test_fixit_is_a_route_key_restored_from_the_address(self):
        self.assertIn('key: "fixit", kind: "overlay"', (JS / "routekeys.js").read_text())
        overlays = code(JS / "overlays.js")
        self.assertIn('"fixit"', overlays.split("const STEPPED", 1)[1].split("\n", 1)[0])
        self.assertIn("fixit: async", overlays)
        self.assertIn("| `fixit` |", (ROOT / "docs" / "ROUTES.md").read_text())

    def test_agent_only_through_jobs_it_has(self):
        src = code(TABS / "fixit.js")
        self.assertNotIn("agentPath(", src, "no new agent line: the to-dos' own Fix this")
        self.assertIn('by: "agent"', src.split("async function airead", 1)[1].split("async function period", 1)[0])
        for name in ("exposed", "block"):
            body = src.split(f"async function {name}(", 1)[1].split("\n}\n", 1)[0]
            self.assertNotIn("agent", body.replace("whoDialog", ""), f"{name}: no agent job, so no My AI agent")


if __name__ == "__main__":
    unittest.main()
