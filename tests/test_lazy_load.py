"""The big files load when first needed (2.41): a site opens on its key figures
without not_found, pages, page_index or page_trends.

  * in node, on a real dashboard run's files: the page opens without them, a
    tab is drawn with the ones it names, a panel waits on its own, the refresh
    reads again only those already fetched (tests/js/lazy-load.mjs);
  * every module that reads one of them from the model is known, and each is
    drawn only after the file is asked for: a new reader must be added here and
    given its tab's `needs` (or a panel's `later`), else it would show "no data".
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "skald" / "webapp" / "js"
LAZY = ("not_found", "pages", "page_index", "page_trends")

# Each module that reads a big file from the model, and where it is drawn: a tab whose
# `needs` or `file` names the file, a panel that waits (later), or an action that asks first.
READERS = {
    "tabs/tr-pages.js": "Traffic › Pages: needs pages, page_index, page_trends",
    "tabs/pagedetail.js": "the page leaderboard, on Traffic › Pages",
    "tabs/pagestory.js": "a page's story, on Traffic › Pages",
    "tabs/pagechange.js": "Did my change work?, on Traffic › Pages (its dialog opens there only)",
    "tabs/aiready.js": "a page's AI readiness, on Traffic › Pages",
    "tabs/readers.js": "an older Pages renderer no tab draws now; Traffic › Pages' needs if one did",
    "page-figs.js": "change dates' first day: Traffic › Pages, and the filter panel asks first",
    "tabs/ov-work.js": "Overview › Summary: a panel that waits (later)",
    "tabs/ov-fresh.js": "Overview › Summary: a panel that waits (later)",
    "tabs/ai-trend.js": "AI & bots › Assistants: needs page_trends",
    "tabs/funnels.js": "Leads & sales › Funnels: needs pages",
    "tabs/si-notfound.js": "Site › Not found: its file",
}
READ = re.compile(r"\.x\??\.(" + "|".join(LAZY) + r")\b")


class Readers(unittest.TestCase):
    def test_every_reader_is_known(self):
        found = set()
        for path in JS.rglob("*.js"):
            if READ.search(path.read_text(encoding="utf-8")):
                found.add(str(path.relative_to(JS)))
        self.assertEqual(found, set(READERS), "a module reads a big file the page fetches only when "
                         "asked: give its tab `needs` (or its panel later()), then list it here")

    def test_the_tabs_name_their_files(self):
        text = {name: (JS / "tabs" / name).read_text() for name in
                ("s-traffic.js", "s-ai.js", "s-sales.js", "s-overview.js", "s-site.js")}
        self.assertRegex(text["s-traffic.js"], r'\["pages", "Pages", pages, \{ needs: \["pages", "page_index", "page_trends"\]')
        self.assertRegex(text["s-ai.js"], r'\["assistants", "Assistants", assistants, \{ needs: \["page_trends"\]')
        self.assertRegex(text["s-sales.js"], r'\["funnels", "Funnels", funnels, \{ file: "funnels", needs: \["pages"\]')
        self.assertRegex(text["s-overview.js"], r'later: \["page_trends", "page_index"\]')
        self.assertRegex(text["s-site.js"], r'file: "not_found"')
        summary = (JS / "tabs" / "ov-summary.js").read_text()
        self.assertIn('later(m, ["page_trends"], () => workCard(', summary)
        self.assertIn('later(m, ["page_trends", "page_index"], () => freshCard(', summary)
        self.assertIn('await need(m, ["page_trends"])', (JS / "filterpanel.js").read_text())
        self.assertIn("tabFiles(t, next, { panels: true })", (JS / "report.js").read_text())


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class InNode(unittest.TestCase):
    def test_load_need_later_and_the_refresh(self):
        from support import Sandbox
        from test_views import VIEWS, mixed_day
        box = Sandbox(views=VIEWS)
        try:
            box.config.write_text(box.config.read_text().replace("  app: false\n", "  app: true\n"))
            box.log(mixed_day())
            self.assertEqual(box.run("--today", "2026-10-07", "collect")[0], 0)
            code, _, err = box.run("--today", "2026-10-07", "dashboard")
            self.assertEqual(code, 0, err)
            site = box.root / "www" / "example.com"
            done = subprocess.run(["node", str(ROOT / "tests" / "js" / "lazy-load.mjs"), str(site)],
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("lazy-load: all passed", done.stdout)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
