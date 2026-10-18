"""A suggested /llms.txt (llms_txt.py): the llmstxt.org format, built from the
pages people and AI assistants read most over the last 90 whole days.

Only recorded ("ok") days are summed; the others are named. Private paths,
paths robots.txt keeps every crawler from, redirected or gone pages, pages
that 404 now and paths cut short in history are left out. Titles come from
the website's page list when there is one. Nothing is written to the website.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import llms_txt, robots  # noqa: E402
from skald.data_files import Page  # noqa: E402

from support import ASKED, Sandbox, line  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 12, 9, tzinfo=UTC)
ANCHOR = date(2026, 10, 11)                      # yesterday: the last whole day
FIRST = ANCHOR - timedelta(days=89)              # the first of the 90


def page(views=0, asked=0, training=0, search=0) -> dict:
    return {"views": views, "readers": views, "ai_asked": asked, "ai_training": training,
            "search": search}


class FakeHistory:
    """history.daily / history.extras over a dict {day: (state, blobs)}."""

    def __init__(self, days: dict[date, tuple[str, dict]], start: date | None = None):
        self.days, self.start = days, start

    def daily(self, key, first, last):
        out, d = [], first
        while d <= last:
            if d in self.days:
                state = self.days[d][0]
            else:
                state = "before" if self.start and d < self.start else "missing"
            out.append({"day": d, "state": state})
            d += timedelta(days=1)
        return out

    def extras(self, key, first, last, kinds=None):
        return {d.isoformat(): blobs for d, (state, blobs) in self.days.items()
                if first <= d <= last}


LINK = re.compile(r"^- \[(?:\\.|[^\]\\\n])+\]\(https?://[^)\s]+\)(: .+)?$")


def well_formed(test, text: str) -> None:
    """The llmstxt.org shape: H1, blockquote, then H2 sections of link items."""
    lines = text.split("\n")
    test.assertTrue(lines[0].startswith("# ") and not lines[0].startswith("## "))
    test.assertEqual(lines[1], "")
    test.assertTrue(lines[2].startswith("> "))
    test.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))
    for ln in lines[3:]:
        if ln == "" or ln.startswith("## "):
            continue
        test.assertRegex(ln, LINK)
    test.assertEqual(sum(1 for ln in lines if ln.startswith("# ")), 1)


class TestSuggest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.config = {"site": {"name": "example.com",
                                "hosts": ["example.com", "www.example.com"]}}

    def tearDown(self):
        self.tmp.cleanup()

    def suggest(self, days, start=None):
        p = Page(FakeHistory(days, start), "example.com", "example.com", None, UTC, NOW, None,
                 self.config, live_dir=self.dir)
        return llms_txt.suggest(p)

    def fixture(self) -> dict:
        ok = {"pages": {
            "/": page(views=50),
            "/pricing": page(views=20),
            "/blog/": page(views=5),
            "/blog/ai-answers": page(views=4, asked=30),     # read most by assistants
            "/blog/ai-answers/": page(views=1),              # the same page
            "/blog/second": page(views=6),
            "/docs/start": page(views=8),
            "/traffic/x": page(views=99),                     # Skald's own
            "/admin/users": page(views=99),                   # private
            "/members/notes": page(views=99),                 # robots.txt: Disallow
            "/old-page": page(views=40),                      # gone later (404)
            "/moved": page(views=40),                         # in the redirect map
            "/only-crawled": page(training=500, search=500),  # nobody read it
            "/" + "x" * 69: page(views=99),                   # cut short at 70
        }}
        days = {FIRST + timedelta(days=i): ("ok", ok) for i in range(90)}
        # A withheld day's figures are never summed, and the day is named.
        days[ANCHOR - timedelta(days=3)] = ("withheld", {"pages": {"/pricing": page(views=10**6)}})
        days[ANCHOR - timedelta(days=4)] = ("missing", {})
        # The 91st day back is outside the 90.
        days[FIRST - timedelta(days=1)] = ("ok", {"pages": {"/ancient": page(views=10**6)}})
        # /old-page answered 404 after it was last served.
        last_ok = ANCHOR - timedelta(days=5)
        for d in (ANCHOR - timedelta(days=2), ANCHOR - timedelta(days=1), ANCHOR):
            days[d] = ("ok", {"pages": {k: v for k, v in ok["pages"].items() if k != "/old-page"},
                              "not_found": [{"path": "/old-page", "status": 404,
                                             "group": "people", "probe": False, "n": 3}]})
        self.assertEqual(days[last_ok][0], "ok")
        (self.dir / robots.TEXT).write_text("User-agent: *\nDisallow: /members/\n")
        legacy = self.dir / "legacy-urls.ts"
        legacy.write_text('export const LEGACY_REDIRECTS: Record<string, string> = {\n'
                          '  "/moved": "/pricing",\n};\n')
        self.config["report"] = {"redirect_map": str(legacy)}
        return days

    def test_the_file_and_what_is_left_out(self):
        got = self.suggest(self.fixture())
        self.assertTrue(got["ok"], got)
        text = got["text"]
        well_formed(self, text)
        self.assertTrue(text.startswith("# example.com\n\n> "))
        paths = [r["path"] for r in got["pages"]]
        for gone in ("/traffic/x", "/admin/users", "/members/notes", "/old-page", "/moved",
                     "/only-crawled", "/" + "x" * 69, "/ancient"):
            self.assertNotIn(gone, paths)
            self.assertNotIn(gone + ")", text)
        # Ranked by people's views plus assistants' fetches for a question.
        self.assertEqual(paths[:3], ["/", "/blog/ai-answers", "/pricing"])
        # One page whatever its trailing slash; the spelling read most is used.
        self.assertEqual(paths.count("/blog/ai-answers"), 1)
        self.assertNotIn("/blog/ai-answers/", paths)
        # Absolute links on the site's host; titles are paths without a page list.
        self.assertIn("- [/blog/ai-answers](https://www.example.com/blog/ai-answers)", text)
        self.assertEqual(got["titles"], "paths")
        # Grouped by top-level section: /blog/ and its pages together.
        self.assertIn("## Blog\n\n- [/blog/ai-answers]", text)
        self.assertIn("- [/blog/]", text.split("## Blog", 1)[1].split("##", 1)[0])
        self.assertIn("## Main pages\n\n- [/](https://www.example.com/)", text)
        period = got["period"]
        self.assertEqual((period["first"], period["last"], period["days"]),
                         (FIRST.isoformat(), ANCHOR.isoformat(), 90))
        self.assertEqual(period["counted"], 88)
        self.assertEqual(period["left_out"],
                         [{"day": (ANCHOR - timedelta(days=4)).isoformat(), "state": "missing"},
                          {"day": (ANCHOR - timedelta(days=3)).isoformat(), "state": "withheld"}])
        out = got["left_out_paths"]
        self.assertEqual((out["private"], out["robots_txt"], out["redirected_or_gone"],
                          out["cut_short"], out["not_read"]), (2, 1, 2, 1, 1))
        # No figure is published: the file is links, the ranking their only use.
        self.assertFalse(re.search(r"\d+ (views|reads|fetches)", text))

    def test_titles_and_the_page_list(self):
        days = self.fixture()
        meta = self.dir / "pages.json"
        meta.write_text(json.dumps({"generated": "2026-10-10", "pages": [
            {"path": "/", "title": "Example: alerts that reach people",
             "description": "Example sends alerts by text message."},
            {"path": "/blog/ai-answers/", "title": "How [AI] answers\nwork",
             "description": "What assistants read."},
            {"path": "/pricing", "title": "Pricing"},
        ]}))
        self.config["report"]["pages_meta"] = str(meta)
        got = self.suggest(days)
        text = got["text"]
        well_formed(self, text)
        self.assertEqual(got["titles"], "website")
        # Only the website's own pages, with their titles; a page description is the note.
        self.assertEqual(sorted(r["path"] for r in got["pages"]),
                         ["/", "/blog/ai-answers", "/pricing"])
        self.assertIn("- [How \\[AI\\] answers work](https://www.example.com/blog/ai-answers): "
                      "What assistants read.", text)
        self.assertIn("> Example sends alerts by text message.", text)
        self.assertGreater(got["left_out_paths"]["not_in_page_list"], 0)

    def test_optional_section_after_the_limit(self):
        ok = {"pages": {f"/p{i:02d}": page(views=200 - i) for i in range(60)}}
        days = {FIRST + timedelta(days=i): ("ok", ok) for i in range(90)}
        got = self.suggest(days)
        text = got["text"]
        well_formed(self, text)
        main, optional = text.split("## Optional\n", 1)
        self.assertEqual(main.count("\n- ["), llms_txt.LIMIT)
        self.assertEqual(optional.count("- ["), llms_txt.OPTIONAL)
        self.assertIn("/p00)", main)
        self.assertIn(f"/p{llms_txt.LIMIT:02d})", optional)
        self.assertNotIn(f"/p{llms_txt.LIMIT + llms_txt.OPTIONAL:02d})", text)
        self.assertTrue(text.rstrip().split("\n")[-1].startswith("- ["))

    def test_markdown_copies_are_grouped_after_the_pages(self):
        # /post.md is a copy of /post, not a page: the copies sit together under their
        # own heading after the pages and take no page's place in the limit.
        ok = {"pages": {**{f"/p{i:02d}": page(views=200 - i) for i in range(60)},
                        **{f"/p{i:02d}.md": page(views=300 - i, asked=50) for i in range(3)}}}
        days = {FIRST + timedelta(days=i): ("ok", ok) for i in range(90)}
        got = self.suggest(days)
        text = got["text"]
        well_formed(self, text)
        head, rest = text.split(f"## {llms_txt.COPIES}\n", 1)
        copies, optional = rest.split("## Optional\n", 1)
        self.assertNotIn(".md)", head)
        self.assertEqual(head.count("\n- ["), llms_txt.LIMIT)
        self.assertEqual(copies.count("- ["), 3)
        self.assertNotIn(".md)", optional)
        self.assertEqual({r["path"] for r in got["pages"] if r["section"] == llms_txt.COPIES},
                         {"/p00.md", "/p01.md", "/p02.md"})

    def test_no_recorded_day_no_file(self):
        got = self.suggest({ANCHOR: ("withheld", {"pages": {"/": page(views=5)}})})
        self.assertFalse(got["ok"])
        self.assertIsNone(got["text"])
        self.assertIn("recorded", got["why"])
        got = self.suggest({}, start=ANCHOR + timedelta(days=1))
        self.assertFalse(got["ok"])
        self.assertEqual(got["period"]["left_out"], [])

    def test_link_text_and_urls_are_safe(self):
        ok = {"pages": {"/a b(c)": page(views=9), "/ok": page(views=8)}}
        got = self.suggest({ANCHOR: ("ok", ok)})
        well_formed(self, got["text"])
        self.assertIn("(https://www.example.com/a%20b%28c%29)", got["text"])

    def test_never_writes_to_the_website(self):
        source = (Path(llms_txt.__file__)).read_text()
        self.assertNotIn("urlopen", source)
        self.assertNotIn("urllib.request", source)


class TestMcpResource(unittest.TestCase):
    """skald://sites/<site>/llms.txt: the text of llms_txt.json, or not found."""

    class Ctx:
        def __init__(self, doc, allowed=True):
            self.doc, self.allowed = doc, allowed

        def site(self, given):
            from skald.mcp.data import Refused
            if not self.allowed:
                raise Refused(f"You may not read {given}")
            return given

        def load(self, site, view, name):
            assert name == "llms_txt"
            return self.doc

    def test_read(self):
        from skald.mcp import resources
        uri = "skald://sites/example.com/llms.txt"
        got = resources.read(self.Ctx({"ok": True, "text": "# example.com\n"}), uri)
        self.assertEqual(got, [{"uri": uri, "mimeType": "text/markdown",
                                "text": "# example.com\n"}])
        for ctx in (self.Ctx({"ok": False, "text": None}), self.Ctx({}, allowed=False)):
            with self.assertRaises(resources.Missing):
                resources.read(ctx, uri)
        with self.assertRaises(resources.Missing):
            resources.read(self.Ctx({"ok": True, "text": "x"}), "skald://sites/../llms.txt")
        self.assertIn("skald://sites/{site}/llms.txt",
                      [t["uriTemplate"] for t in resources.templates()])


class TestEndToEnd(unittest.TestCase):
    """A collected day, the data file beside the dashboard, and the command."""

    def setUp(self):
        self.box = Sandbox()
        t = datetime(2026, 10, 5, 12, tzinfo=UTC)
        lines = [line(t + timedelta(minutes=i), f"203.0.113.{10 + i}", "/guides/alpha")
                 for i in range(3)]
        lines += [line(t + timedelta(minutes=10 + i), f"203.0.113.{40 + i}", "/")
                  for i in range(2)]
        lines += [line(t + timedelta(minutes=20 + i), "198.51.100.41", "/guides/beta", ASKED)
                  for i in range(4)]
        lines += [line(t + timedelta(minutes=30), "203.0.113.60", "/logo.png"),
                  line(t + timedelta(minutes=31), "203.0.113.61", "/gone", status=404),
                  line(t + timedelta(minutes=32), "203.0.113.62", "/old", status=301)]
        self.box.log(lines)
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)

    def tearDown(self):
        self.box.close()

    def test_data_file_and_command(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "dashboard")[0], 0)
        got = json.loads((self.box.root / "www" / "example.com" / "data" /
                          "llms_txt.json").read_text())
        self.assertTrue(got["ok"], got)
        self.assertEqual(got["schema_version"], 1)
        self.assertEqual([r["path"] for r in got["pages"]],
                         ["/guides/beta", "/guides/alpha", "/"])
        well_formed(self, got["text"])
        for absent in ("/logo.png", "/gone", "/old"):
            self.assertNotIn(absent, got["text"])
        self.assertIn("## Guides", got["text"])

        code, out, err = self.box.run("--today", "2026-10-06", "llms-txt")
        self.assertEqual(code, 0, err)
        self.assertEqual(out, got["text"])
        self.assertIn("2026-10-05", err)

        target = self.box.root / "suggested-llms.txt"
        code, out, err = self.box.run("--today", "2026-10-06", "llms-txt",
                                      "--site", "example.com", "--out", str(target))
        self.assertEqual(code, 0, err)
        self.assertEqual(target.read_text(), got["text"])
        self.assertEqual(out, "")

        code, out, err = self.box.run("--today", "2026-10-06", "llms-txt", "--site", "other")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
