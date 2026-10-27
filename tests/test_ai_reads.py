"""An assistant's reads (ai_reads.py) and their second count (audit_ai_reads.py).

What is pinned:
- the pattern seen on a live site: Google NotebookLM asks for a page twice within a few
  seconds, then for the page's style sheet (304) and script with the page as referrer.
  That is one read, four requests, one repeat and two files, both with their page;
- two reads of the same page two minutes apart are two reads; a different page inside
  the window is a read of its own;
- a file is known by its extension, the site's asset prefixes, a Next.js folder or query,
  or a same-site referrer pointing at a page the assistant just read;
- every sum the blob promises is checked, and the audit recounts it from the raw lines;
  a tampered blob, or a tampered reads column in ai_fetches, fails the audit;
- ai_fetches rows carry the reads, ai_likely its reads and reads_followed;
- requests.json says a file is "AI page file", never "AI asked", and names its read;
- app.json carries the day's ai_reads; the mail says reads, with requests beside them;
- the recount shares only ai_read_names.py's lists and classify.py's names.
"""
from __future__ import annotations

import ast
import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, Sandbox, line, totals_for  # noqa: E402

from skald import ai_reads, audit_ai_reads, mail_html, requests_feed  # noqa: E402
from skald.ai_read_names import WINDOW_SECONDS  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
NOTEBOOK = "Mozilla/5.0 (compatible; Google-NotebookLM)"
PAGE = "/blog/best-online-quiz-makers"
ROOT = Path(__file__).resolve().parent.parent


def at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def notebook(start: datetime, page: str = PAGE) -> list[str]:
    """The owner's sample: page, page again, its CSS (304) and JS, 5 seconds in all."""
    ref = "https://example.com" + page
    return [line(start, "198.51.100.53", page, NOTEBOOK),
            line(start + timedelta(seconds=2), "198.51.100.53", page, NOTEBOOK),
            line(start + timedelta(seconds=4), "198.51.100.53", "/css/global-custom.css", NOTEBOOK,
                 referrer=ref, status=304),
            line(start + timedelta(seconds=5), "198.51.100.53",
                 "/_next/static/chunks/app-4f1c.js", NOTEBOOK, referrer=ref)]


def synthetic() -> list[str]:
    return (notebook(at(10, 0))
            + [line(at(11, 0), "198.51.100.40", "/pricing/", ASKED),       # two reads,
               line(at(11, 2), "198.51.100.40", "/pricing/", ASKED),       # 2 minutes apart
               line(at(12, 0), "198.51.100.40", "/docs/", ASKED),          # a page, then
               line(at(12, 0, 10), "198.51.100.40", "/guides/a", ASKED)])  # another inside the window


class TestRoles(unittest.TestCase):

    def roles(self, rows, prefixes=ai_reads.DEFAULT_PREFIXES):
        r = ai_reads.Roles(prefixes)
        return [r("gemini.google.com", p, p, ref, "example.com", when) for when, p, ref in rows]

    def test_the_notebooklm_pattern_is_one_read(self):
        ref = "https://example.com" + PAGE
        got = self.roles([(at(10, 0), PAGE, "-"), (at(10, 0, 2), PAGE, "-"),
                          (at(10, 0, 4), "/css/global-custom.css", ref),
                          (at(10, 0, 5), "/_next/static/chunks/app.js", ref)])
        self.assertEqual(got, [("read", PAGE), ("repeat", PAGE), ("file", PAGE), ("file", PAGE)])

    def test_the_window(self):
        self.assertEqual(WINDOW_SECONDS, 30)
        got = self.roles([(at(10, 0), "/a", "-"), (at(10, 0, 30), "/a/", "-"),
                          (at(10, 2), "/a", "-"), (at(10, 2, 5), "/b", "-")])
        # The trailing slash is the same page; 2 minutes later is a new read; /b is its own.
        self.assertEqual([x[0] for x in got], ["read", "repeat", "read", "read"])

    def test_what_a_file_is(self):
        self.assertTrue(ai_reads.is_file("/x/logo.SVG"))
        self.assertTrue(ai_reads.is_file("/_nuxt/entry"))
        self.assertTrue(ai_reads.is_file("/media/a", prefixes=("/media/",)))
        self.assertTrue(ai_reads.is_file("/a", "/a?_rsc=1x2"))
        self.assertFalse(ai_reads.is_file("/blog/a.html"))
        self.assertFalse(ai_reads.is_file("/llms.txt"))
        # A page the referrer names, read just before: its file, whatever it looks like.
        got = self.roles([(at(10, 0), "/a", "-"), (at(10, 0, 3), "/api/data", "https://example.com/a")])
        self.assertEqual(got[1], ("file", "/a"))
        # Another site's referrer, or a page not read in the window: not a file.
        got = self.roles([(at(10, 0), "/a", "-"), (at(10, 0, 3), "/b", "https://other.example.net/a"),
                          (at(10, 5), "/c", "https://example.com/a")])
        self.assertEqual([x[0] for x in got], ["read", "read", "read"])


class TestTheDay(unittest.TestCase):

    def test_the_blob(self):
        totals = totals_for(synthetic())
        blob = totals.extras["ai_reads"]
        self.assertEqual({k: blob[k] for k in ai_reads.FIELDS},
                         {"requests": 8, "reads": 5, "repeats": 1, "files": 2, "files_with_page": 2})
        self.assertEqual(blob["window_seconds"], 30)
        self.assertEqual(blob["by_name"]["Google-NotebookLM"],
                         {"requests": 4, "reads": 1, "repeats": 1, "files": 2, "files_with_page": 2})
        self.assertEqual(blob["pages"]["Google-NotebookLM"], {PAGE: {"reads": 1, "files": 2}})
        self.assertEqual(blob["pages"]["ChatGPT-User"]["/pricing/"], {"reads": 2, "files": 0})

    def test_a_wrong_sum_is_caught(self):
        from skald import extras
        totals = totals_for(synthetic())
        self.assertEqual(extras.check(totals), [])
        totals.extras["ai_reads"]["by_name"]["ChatGPT-User"]["reads"] += 1
        self.assertIn("ai_reads: reads by name does not sum", [p.what for p in extras.check(totals)])
        totals = totals_for(synthetic())
        totals.extras["ai_reads"]["reads"] += 1
        self.assertIn("ai_reads: reads, repeats and files does not sum", [p.what for p in extras.check(totals)])
        totals = totals_for(synthetic())
        totals.extras["ai_fetches"]["rows"][0][4] += 1
        self.assertTrue([p for p in extras.check(totals) if "reads" in p.what])


class TestTheAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic())
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]

    def tamper(self, kind, blob):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = ?", (json.dumps(blob), kind))
        db.close()

    def test_the_recount_matches(self):
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        got = self.stored()
        self.assertEqual(got["ai_reads"]["reads"], 5)
        rows = got["ai_fetches"]["rows"]
        self.assertTrue(all(len(r) == 5 for r in rows))
        self.assertEqual(sum(r[4] for r in rows), 5)                 # reads
        self.assertEqual(sum(r[3] for r in rows), 8)                 # requests
        css = [r for r in rows if r[2] == "/css/global-custom.css"]
        self.assertEqual([r[4] for r in css], [0])                   # a file: no read
        self.assertEqual(got["ai_likely"]["reads"]["gemini.google.com"], 1)
        self.assertEqual(got["ai_likely"]["fetches"]["gemini.google.com"], 4)

    def test_a_tampered_blob_fails(self):
        blob = self.stored()["ai_reads"]
        blob["reads"], blob["repeats"] = 4, 2
        self.tamper("ai_reads", blob)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_reads", err)

    def test_a_tampered_reads_column_fails(self):
        rows = self.stored()["ai_fetches"]["rows"]
        for r in rows:
            if r[2] == "/css/global-custom.css":
                r[4] = 1
        self.tamper("ai_fetches", {"rows": rows})
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("reads", err)

    def test_app_json_carries_the_reads(self):
        text = self.box.config.read_text().replace("  app: false\n", "  app: true\n")
        self.box.config.write_text(text)
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        app = json.loads((self.box.root / "www" / "example.com" / "data" / "app.json").read_text())
        day = next(d for d in app["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day["ai_reads"]["reads"], 5)


class TestTheFeed(unittest.TestCase):

    def test_a_file_is_never_ai_asked(self):
        from skald import cli
        box = Sandbox()
        try:
            box.log(notebook(at(22, 0)))
            args = cli.parser().parse_args(["--config", str(box.config), "live"])
            ctx = cli.Context(args)
            ctx.now = at(23, 0)
            ctx.out = ctx.err = lambda *a: None
            self.assertEqual(cli.cmd_live(ctx), 0)
            feed = requests_feed.load(requests_feed.path_for(ctx.live_dir, "example.com"))
            rows = sorted(feed["rows"], key=lambda r: r["at"])          # the feed is newest first
            got = [(r["path"], r["ai_role"], r["ai_of"], r["rule"]) for r in rows]
            self.assertEqual([x[1:3] for x in got],
                             [("read", PAGE), ("repeat", PAGE), ("file", PAGE), ("file", PAGE)])
            for path, role, _, rule in got:
                if role == "file":
                    self.assertEqual(rule, f"AI page file: Google-NotebookLM, loaded by {PAGE}", path)
                    self.assertNotIn("asked", rule)
        finally:
            box.close()


class TestTheMail(unittest.TestCase):

    def test_reads_then_requests(self):
        totals = totals_for(synthetic())
        self.assertIn("5 page reads because someone asked an AI (8 requests)",
                      mail_html._crawlers(totals, 5))
        # A period with a day counted before reads were: requests, said so.
        self.assertIn("8 requests because someone asked an AI", mail_html._crawlers(totals, None))


class TestTheDashboard(unittest.TestCase):

    def test_the_fold_and_the_drawer(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        got = subprocess.run(["node", str(ROOT / "tests" / "js" / "ai-reads.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("ai-reads: all passed", got.stdout)


class TestIndependence(unittest.TestCase):

    def test_the_recount_shares_only_the_name_lists(self):
        tree = ast.parse((ROOT / "skald" / "audit_ai_reads.py").read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                names.add((node.module or "").split(".")[0])
        self.assertEqual(names, {"ai_read_names", "classify"})


if __name__ == "__main__":
    unittest.main()
