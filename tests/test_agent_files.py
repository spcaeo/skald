"""Files made for machines and who fetched them (agent_files.py, SKALD-56)
and its second count (audit_agent_files.py).

What is pinned:
- the path rule: Markdown copies, OKF bundles, llms.txt, /.well-known/ agent
  and MCP cards, robots.txt and sitemaps; case, trailing "/", query string;
  a page or an asset is none of them; the audit's own rule agrees;
- the day kind on a synthetic day: per kind requests, statuses and who (AI
  asked, AI training, search engines, bots, people), names per who, the
  files with their statuses, who, names and last request; our own requests
  never count;
- a busy day keeps the KEEP files and TOP names and folds the rest, and
  still adds up; every sum is checked by verify, and planted errors are caught;
- the audit rebuilds every figure from the raw lines, and a tampered stored
  figure fails it;
- agent_files.json: the days, files only for the last 30 days, today; a
  view says whole site only;
- the range sums in agent-files-sum.js (node);
- the recount shares only agent_files' name lists and classify's names.
"""
from __future__ import annotations

import ast
import json
import shutil
import sqlite3
import subprocess
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, CHROME, GOOGLEBOT, GPTBOT, Sandbox, totals_for  # noqa: E402

from skald import agent_files, audit_agent_files, extras  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "skald" / "webapp" / "js"
CLAUDEBOT = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0)"
AHREFS = "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)"
CURL = "curl/8.7.1"


def at(hour: int, minute: int, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def ext(when, address, path, agent, status=200) -> str:
    return (f'{when.isoformat()} {address} example.com "GET {path} HTTP/1.1" {status} 512 '
            f'"-" "{agent}" 0.004 cc=US\n')


def synthetic(day: date = DAY) -> list[str]:
    return [
        ext(at(9, 0, day), "198.51.100.40", "/data-migration.md", GPTBOT),
        ext(at(9, 5, day), "198.51.100.41", "/data-migration.md", ASKED),
        ext(at(9, 6, day), "198.51.100.41", "/Guide/README.MD/", ASKED, status=301),
        ext(at(9, 10, day), "198.51.100.43", "/okf/index.md", CLAUDEBOT),
        ext(at(9, 11, day), "198.51.100.43", "/okf/blog.md?x=1", CLAUDEBOT, status=404),
        ext(at(10, 0, day), "198.51.100.42", "/llms.txt", GOOGLEBOT),
        ext(at(10, 1, day), "198.51.100.42", "/docs/llms-full.txt", GOOGLEBOT, status=404),
        ext(at(10, 2, day), "198.51.100.42", "/robots.txt", GOOGLEBOT),
        ext(at(10, 3, day), "198.51.100.42", "/sitemap_index.xml", GOOGLEBOT),
        ext(at(11, 0, day), "198.51.100.50", "/.well-known/agent-card.json", AHREFS, status=404),
        ext(at(11, 1, day), "198.51.100.51", "/.well-known/mcp/server-card.json", CURL, status=404),
        ext(at(11, 2, day), "198.51.100.51", "/llms.txt", CURL),
        # Not files for machines: a page, an asset, another .well-known file.
        ext(at(12, 0, day), "198.51.100.40", "/about/", GPTBOT),
        ext(at(12, 1, day), "198.51.100.40", "/assets/app.css", GPTBOT),
        ext(at(12, 2, day), "198.51.100.51", "/.well-known/security.txt", CURL),
        # A person reading a page, then its Markdown copy.
        ext(at(13, 0, day), "203.0.113.10", "/pricing/", CHROME),
        ext(at(13, 0, day), "203.0.113.10", "/assets/app.css", CHROME),
        ext(at(13, 1, day), "203.0.113.10", "/pricing.md", CHROME),
    ]


class TestThePathRule(unittest.TestCase):

    CASES = {
        "/a.md": "markdown", "/a/b/index.md": "markdown", "/A/B.MD/": "markdown",
        "/x.mdx": "markdown", "/x.markdown": "markdown", "/okf/index.md": "okf",
        "/docs/okf/a.md": "okf", "/okf.md": "markdown", "/okf/": None, "/okf/logo.png": None,
        "/llms.txt": "llms_txt", "/LLMS-FULL.TXT": "llms_txt", "/docs/llms.txt": "llms_txt",
        "/llms.txt?v=2": "llms_txt", "/robots.txt": "robots_txt", "/a/robots.txt": None,
        "/sitemap.xml": "sitemap", "/sitemap_index.xml": "sitemap", "/blog/sitemap-1.xml.gz": "sitemap",
        "/feed.xml": None, "/.well-known/agent-card.json": "agent_card",
        "/.well-known/agent.json": "agent_card", "/.well-known/mcp.json": "agent_card",
        "/.well-known/mcp/server-card.json": "agent_card", "/.well-known/ai-plugin.json": "agent_card",
        "/.well-known/ai-catalog.json": "agent_card", "/.well-known/security.txt": None,
        "/.well-known/": None, "/x/.well-known/agent.json": None, "/": None, "/pricing/": None,
        "/notes.txt": None, "/a.md#top": "markdown",
    }

    def test_the_main_rule(self):
        for path, kind in self.CASES.items():
            with self.subTest(path=path):
                self.assertEqual(agent_files.kind_of(path), kind)

    def test_the_audit_rule_agrees(self):
        for path, kind in self.CASES.items():
            with self.subTest(path=path):
                self.assertEqual(audit_agent_files.kind_of(path), kind)

    def test_only_ascii_letters_are_made_small(self):
        # The Kelvin sign lowers to "k" in Python; neither rule may read it as one.
        odd = "/.well-Known/agent.json"
        self.assertIsNone(agent_files.kind_of(odd))
        self.assertIsNone(audit_agent_files.kind_of(odd))


class TestTheDay(unittest.TestCase):

    def test_the_synthetic_day(self):
        totals = totals_for(synthetic())
        self.assertEqual(extras.check(totals), [])
        blob = totals.extras["agent_files"]
        k = blob["kinds"]
        self.assertEqual(list(k), ["markdown", "okf", "llms_txt", "agent_card", "robots_txt", "sitemap"])
        self.assertEqual(k["markdown"]["requests"], 4)
        self.assertEqual(k["markdown"]["who"]["ai_asked"], 2)
        self.assertEqual(k["markdown"]["who"]["ai_training"], 1)
        self.assertEqual(k["markdown"]["status"], {"2xx": 3, "3xx": 1})
        self.assertEqual(k["okf"], {"requests": 2, "status": {"2xx": 1, "4xx": 1}, "who": {"ai_training": 2}})
        self.assertEqual(k["llms_txt"]["who"], {"bots": 1, "search_engines": 2})
        self.assertEqual(k["agent_card"]["requests"], 2)
        self.assertEqual(blob["names"]["ai_training"]["ClaudeBot"], {"okf": 2})
        self.assertEqual(blob["names"]["search_engines"]["Googlebot"],
                         {"llms_txt": 2, "robots_txt": 1, "sitemap": 1})
        f = blob["files"]["/data-migration.md"]
        self.assertEqual((f["kind"], f["requests"], f["status"]), ("markdown", 2, {"200": 2}))
        self.assertEqual(f["who"], {"ai_asked": 1, "ai_training": 1})
        self.assertEqual(f["names"], {"ChatGPT-User": 1, "GPTBot": 1})
        self.assertEqual(f["last"], "2026-10-05T09:05:00Z")
        self.assertEqual(blob["files"]["/okf/blog.md"]["status"], {"404": 1})   # query cut
        self.assertIn("/Guide/README.MD/", blob["files"])                        # case kept
        for path in ("/about/", "/assets/app.css", "/.well-known/security.txt", "/pricing/"):
            self.assertNotIn(path, blob["files"])
        self.assertEqual(blob["rest"], {})
        self.assertEqual(blob["folded"], {"names": {w: 0 for w in blob["names"]}, "files": 0})

    def test_a_busy_day_folds_and_still_adds_up(self):
        lines = [ext(at(8, i % 60), f"198.51.100.{i % 200}", f"/p{i}.md", f"Robot{i:03d}/1.0")
                 for i in range(agent_files.KEEP + 7)]
        totals = totals_for(lines)
        blob = totals.extras["agent_files"]
        self.assertEqual(len(blob["files"]), agent_files.KEEP)
        self.assertEqual(blob["rest"], {"markdown": {"files": 7, "requests": 7}})
        bots = blob["names"]["bots"]
        self.assertEqual(len(bots), agent_files.TOP + 1)
        self.assertEqual(blob["folded"]["names"]["bots"], agent_files.KEEP + 7 - agent_files.TOP)
        self.assertEqual(extras.check(totals), [])

    def test_planted_errors_are_caught(self):
        def problems(change):
            totals = totals_for(synthetic())
            change(totals.extras["agent_files"])
            return [f"{p.what}: {p.detail}" for p in extras.check(totals)]
        got = problems(lambda b: b["kinds"]["markdown"].update(requests=5))
        self.assertTrue(any("markdown by who" in p for p in got), got)
        got = problems(lambda b: b["files"]["/llms.txt"]["status"].update({"200": 3}))
        self.assertTrue(any("/llms.txt by status" in p for p in got), got)
        got = problems(lambda b: b["files"].pop("/robots.txt"))
        self.assertTrue(any("robots_txt by file" in p for p in got), got)
        got = problems(lambda b: b["names"]["search_engines"]["Googlebot"].update(sitemap=2))
        self.assertTrue(any("search_engines's names, sitemap" in p for p in got), got)
        got = problems(lambda b: b["folded"].update(files=3))
        self.assertTrue(any("a rest without folded paths" in p for p in got), got)


class TestTheAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic())

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]["agent_files"]

    def tamper(self, blob):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'agent_files'", (json.dumps(blob),))
        db.close()

    def test_the_recount_matches_and_planted_errors_are_caught(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.stored()["kinds"]["okf"]["requests"], 2)
        for change, words in (
                (lambda b: b["kinds"]["llms_txt"].update(requests=4),
                 "agent_files llms_txt: requests: history has 4, the recount finds 3"),
                (lambda b: b["kinds"]["okf"]["who"].update(ai_training=1, ai_asked=1),
                 "agent_files okf who: ai_asked: history has 1, the recount finds 0"),
                (lambda b: b["names"]["ai_training"]["ClaudeBot"].update(okf=1, markdown=1),
                 "agent_files ai_training ClaudeBot: markdown: history has 1"),
                (lambda b: b["files"]["/okf/blog.md"]["status"].update({"200": 1, "404": 0}),
                 "agent_files /okf/blog.md status: 200: history has 1, the recount finds 0"),
                (lambda b: b["files"]["/llms.txt"].update(last="2026-10-05T11:03:00Z"),
                 "/llms.txt last fetched 2026-10-05T11:03:00Z"),
                (lambda b: b["files"]["/robots.txt"].update(kind="sitemap"),
                 "/robots.txt kept as sitemap, the recount reads robots_txt"),
                (lambda b: b["files"].pop("/sitemap_index.xml"),
                 "agent_files sitemap beyond the kept files: files: history has 0, the recount finds 1")):
            with self.subTest(words=words):
                self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
                blob = self.stored()
                change(blob)
                self.tamper(blob)
                code, _, err = self.box.run("--today", TODAY, "audit")
                self.assertEqual(code, 1, err)
                self.assertIn(words, err)

    def test_long_paths_of_two_kinds_stay_apart(self):
        """Review of SKALD-56: two paths longer than 200 characters that start alike, one
        llms.txt and one Markdown, were one file of one kind, so the kinds' files did not add
        up and the day was withheld. A cut path now ends with its kind."""
        long = "/" + "a" * 250
        self.box.log([ext(at(14, 0), "198.51.100.42", long + "/llms.txt", GOOGLEBOT, status=404),
                      ext(at(14, 1), "198.51.100.42", long + "/x.md", GOOGLEBOT, status=404)])
        code, _, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)
        files = self.stored()["files"]
        cut = "/" + "a" * 199
        self.assertEqual(files[cut + " (llms_txt)"]["kind"], "llms_txt")
        self.assertEqual(files[cut + " (markdown)"]["kind"], "markdown")
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)

    def test_the_data_file(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        got = json.loads((self.box.root / "www" / "example.com" / "data" / "agent_files.json").read_text())
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day["files"]["kinds"]["markdown"]["requests"], 4)
        self.assertEqual(day["files"]["files"]["/data-migration.md"]["requests"], 2)
        before = next(d for d in got["days"] if d["state"] in ("before", "missing"))
        self.assertNotIn("files", before)
        self.assertEqual((got["detail_days"], got["kinds"][0], got["who"][0]), (30, "markdown", "ai_asked"))


class TestDetailAndViews(unittest.TestCase):

    def test_files_only_for_the_last_30_days(self):
        blob = {"kinds": {"markdown": {"requests": 1}}, "names": {}, "files": {"/a.md": {}}, "rest": {}}
        self.assertNotIn("files", agent_files._compact(blob, False))
        self.assertIn("files", agent_files._compact(blob, True))
        self.assertIsNone(agent_files._compact(None, True))

    def test_a_view_is_whole_site_only(self):
        class P:
            view = object()
        self.assertEqual(agent_files.build(P()), {"whole_site_only": True})


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestTheRangeSums(unittest.TestCase):

    def test_ranges(self):
        script = (ROOT / "tests" / "js" / "agent-files-sum.mjs")
        out = subprocess.run(["node", str(script)], capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(out.returncode, 0, out.stderr + out.stdout)
        self.assertIn("ok", out.stdout)


class TestTheRecountStandsApart(unittest.TestCase):

    def test_it_shares_only_the_name_lists(self):
        tree = ast.parse((ROOT / "skald" / "audit_agent_files.py").read_text())
        allowed = {"agent_files": {"KINDS", "LLMS_NAMES", "MARKDOWN_ENDS", "OKF_SEGMENT", "PEOPLE",
                                   "WELL_KNOWN", "WHO"},
                   "audit_crawler_cost": {"_name"}, "classify": {"AI_ASKED"}}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                names = {a.name for a in node.names}
                self.assertIn(node.module, allowed)
                self.assertLessEqual(names, allowed[node.module], node.module)


if __name__ == "__main__":
    unittest.main()
