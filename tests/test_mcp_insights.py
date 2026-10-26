"""The 2.35 MCP tools: what_changed, todos, lost_pages, page_changes, ai_readiness
and changed_pages (skald/mcp/tools_insights.py, tools_pages.py).

A small dashboard folder written by hand (example.com, whole days 2026-10-01 to
2026-10-14) with the files the dashboard reads: overview.json and breakdowns.json
for what_changed, and todos.json, lost_pages.json, page_changes.json,
ai_ready.json and page_trends.json in the shapes their builders write
(DATA-CONTRACT-TODOS.md, -PAGE-CHANGES.md, -AI-READY.md, -TRACKING.md). Each tool
reads them as the page does, names what is withheld or not recorded, never
turns it into 0, and keeps to the sites the caller may read.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.mcp import tools  # noqa: E402
from skald.mcp.data import Context  # noqa: E402

SITE = "example.com"
FIRST = date(2026, 10, 1)


def days(n=14):
    return [(FIRST + timedelta(days=i)).isoformat() for i in range(n)]


def ov_day(day, readers, state="ok"):
    if state != "ok":
        return {"day": day, "state": state, "problems": "planted"}
    return {"day": day, "state": "ok", "groups": {"people": {"readers": readers, "views": 2 * readers,
                                                              "hits": 3 * readers}}}


def br_day(day, source, landing, state="ok"):
    if state != "ok":
        return {"day": day, "state": state}
    return {"day": day, "state": "ok", "readers_by": {"source": source, "landing": landing}}


TODOS = {
    "window": {"first": "2026-09-15", "last": "2026-10-14", "days": 30, "of": 30},
    "limits": {"lost_min_asks": 10}, "marks": True,
    "todos": [
        {"id": "lost-pages", "kind": "lost", "subject": None, "title": "Send old pages somewhere useful",
         "proof": "2 old page addresses answered 'not found'.", "todo": "Redirect each.",
         "check": "the not-found answers to the same addresses", "figures": {"paths": 2},
         "columns": [{"key": "path", "label": "Old address", "path": True},
                     {"key": "people", "label": "People", "num": True}],
         "rows": [{"path": "/old-a/", "people": 7}, {"path": "/old-b/", "people": 3}],
         "rows_total": 2, "open": {"tab": "site/notfound", "name": "Site > Not found"},
         "state": "open", "marked": None, "recheck": None},
        {"id": "server-errors", "kind": "errors", "subject": None, "title": "Fix the server errors",
         "proof": "9 server errors.", "todo": "Send the list.", "check": "the server errors",
         "figures": {"errors": 9}, "columns": [], "rows": [], "rows_total": 0,
         "open": {"tab": "site/health", "name": "Site > Health"}, "state": "done",
         "marked": {"state": "done", "day": "2026-10-10", "at": "x", "first_day": "2026-10-10"},
         "recheck": {"marked_day": "2026-10-10", "days": 4, "verdict": "fixed",
                     "words": "Fixed: 0 server errors since 10 Oct."}},
        {"id": "sitemap", "kind": "sitemap", "subject": None, "title": "Fix the sitemap address",
         "proof": "p", "todo": "t", "check": "c", "figures": {}, "columns": [], "rows": [],
         "rows_total": 0, "open": {"tab": "site/notfound", "name": "Site > Not found"},
         "state": "notnow", "marked": {"state": "notnow"}, "recheck": None}],
    "withheld": [{"id": "ai-markdown", "title": "Give AI the Markdown copies",
                  "why": "the second count finds 4, the list says 5"}]}

LOST = {
    "window": {"first": "2026-09-15", "last": "2026-10-14", "days": 29, "of": 30,
               "not_recorded": ["2026-09-20"]},
    "live": {"sitemap": 10, "sitemap_day": "2026-10-14", "served": 12, "pages": 14}, "marks": True,
    "totals": {"paths": 2, "people": 7, "search": 4, "ai": 2, "md_paths": 1, "md_live": 1,
               "md_asks": 6, "md_live_asks": 6},
    "lost": [{"path": "/old-a/", "people": 7, "search": 3, "ai": 1, "bots": 0, "n": 11,
              "target": "/new-a/", "match": "exact", "why": "w",
              "nginx": "location = /old-a/ { return 301 /new-a/; }",
              "apache": "Redirect 301 /old-a/ /new-a/", "gone": None, "marked": None},
             {"path": "/old-b/", "people": 0, "search": 1, "ai": 1, "bots": 0, "n": 2,
              "target": None, "match": None, "why": "w",
              "nginx": "location = /old-b/ { return 410; }", "apache": "Redirect gone /old-b/",
              "gone": None, "marked": "2026-10-12"}],
    "markdown": {"live": [{"path": "/guide.md", "ai": 6, "ai_asked": 2, "ai_training": 4,
                           "people": 0, "search": 0, "page": "/guide",
                           "nginx": "location = /guide.md { return 301 /guide; }",
                           "apache": "Redirect 301 /guide.md /guide"}], "other": []},
    "fixed": [{"path": "/old-b/", "marked_day": "2026-10-12", "days": 2, "people": 0, "search": 0,
               "ai": 0, "bots": 0, "served": 0, "verdict": "fixed", "today": None}],
    "withheld": []}

FIG = {"key": "visits", "better": "up", "before": {"days": 14, "total": 70, "per_day": 5.0,
                                                   "at_least": False},
       "after": {"days": 14, "total": 140, "per_day": 10.0, "at_least": False},
       "unequal": False, "change": {"per_day": 5.0, "pct": 100}, "verdict": "up"}
CHANGES = {"min_days": 14, "max_days": 28, "rules": {"days": "the same number of whole days"},
           "measures": [{"key": "visits", "label": "Visits that started on the page", "better": "up"}],
           "marks": True,
           "changes": [{"id": "c12345678", "path": "/pricing/", "day": "2026-09-20", "kind": "title",
                        "note": "New title", "status": "ready", "days_after": 14,
                        "verdict_on": "2026-10-05", "before": {"first": "2026-09-06",
                                                               "last": "2026-09-19"},
                        "after": {"first": "2026-09-21", "last": "2026-10-04"},
                        "figures": [FIG], "leads_why": None},
                       {"id": "c87654321", "path": "/blog/x", "day": "2026-10-12", "kind": "content",
                        "note": "", "status": "waiting", "days_after": 0, "verdict_on": "2026-10-27",
                        "before": {}, "after": {},
                        "figures": [{**FIG, "before": None, "after": None, "change": None,
                                     "verdict": "waiting"}], "leads_why": None}],
           "withheld": [{"id": "c00000000", "path": "/about/", "day": "2026-10-01",
                         "why": ["a lead the second count does not find"]}]}

CRAWLERS = [["GPTBot", "training"], ["Google-Extended", "training"]]
READY = {
    "crawlers": CRAWLERS,
    "robots": {"url": "https://www.example.com/robots.txt", "fetched_at": "2026-10-14T10:00:00+00:00",
               "ok": True, "error": None, "missing": False,
               "crawlers": {"GPTBot": {"agents": ["*"], "rules": [["disallow", "/private/"]], "root": True},
                            "Google-Extended": {"agents": ["Google-Extended"],
                                                "rules": [["disallow", "/guides/"]], "root": True}}},
    "sitemap": {"enabled": True, "day": "2026-10-14", "fetched_at": "x", "count": 2,
                "pages": {"/guides/webhooks/": "2026-09-08", "/pricing/": None}},
    "window": {"days": 30, "first": "2026-09-15", "last": "2026-10-14", "of": 30, "recorded": 30,
               "since": "2026-09-15", "folded": 0},
    "pages": {"/guides/webhooks/": {"self": {}, "slow": {},
                                    "copies": {"/guides/webhooks.md": {"GPTBot": {"404": 9}}}}},
    "attention": {"total": 2, "rows": [
        {"path": "/guides/webhooks/", "listed": True, "copy_errors": 9, "copy_404": 9, "not_found": 0,
         "server_errors": 0, "blocked": 0, "robots": ["Google-Extended"], "redirects": 0, "slow": 0,
         "by": ["GPTBot"]},
        {"path": "/old/", "listed": False, "copy_errors": 0, "copy_404": 0, "not_found": 3,
         "server_errors": 0, "blocked": 0, "robots": [], "redirects": 0, "slow": 0, "by": ["GPTBot"]}]}}

TRENDS = {
    "fields": ["visits", "one_page", "views", "search", "ai"], "first_day": "2026-10-01",
    "days": [{"day": d, "state": "ok", "landings": None,
              "fetches": {"paths": {"/guides/webhooks.md": {"ChatGPT-User": 1},
                                    "/guides/webhooks": {"Claude-User": 2}} if d == "2026-10-13" else {},
                          "folded": 0}} for d in days()],
    "today": None,
    "changed": {"days": 30, "since": "2026-09-15", "until": "2026-10-14", "rules": {},
                "counts": {"pages": 2, "measured": 2, "visited": 1, "searched": 1, "none": 1,
                           "google": 1},
                "pages": [{"path": "/pricing/", "changed": "2026-10-10", "source": "sitemap",
                           "visits": 30, "search": 8, "first_search": "2026-10-10",
                           "counted_from": "2026-10-10", "unmeasured": 0, "at_least": False,
                           "google": True, "google_last": "2026-10-13"},
                          {"path": "/about/", "changed": "2026-10-13", "source": "website",
                           "visits": None, "search": None, "first_search": None,
                           "counted_from": None, "unmeasured": 1, "at_least": False,
                           "google": None, "google_last": None}]},
    "same_day": {"day": "2026-10-01", "pages": 9, "of": 12}}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / SITE / "data"
        self.data.mkdir(parents=True)
        self.overview()
        self.ctx = Context(self.tmp, checker=lambda s: (True, "", False))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, name, doc):
        (self.data / f"{name}.json").write_text(json.dumps(doc))

    def overview(self, states=None, before=None):
        """Days 1-7 the period before, 8-14 the period looked at (anchor 14 Oct)."""
        states = states or {}
        ov, br = [], []
        for i, d in enumerate(days()):
            later = i >= 7
            src = ({"Search engine": 30, "Direct or unknown": 10, "Email": 2} if later
                   else {"Search engine": 20, "Direct or unknown": 9, "Email": 2})
            land = ({"/": 25, "/pricing/": 17} if later else {"/": 21, "/pricing/": 10})
            readers = sum(src.values())
            if before and not later:
                land = dict(land, **before)
            ov.append(ov_day(d, readers, states.get(d, "ok")))
            br.append(br_day(d, src, land, states.get(d, "ok")))
        self.write("overview", {"anchor": "2026-10-14", "today": "2026-10-15", "timezone": "UTC",
                                "first_day": "2026-10-01", "days": ov})
        self.write("breakdowns", {"timezone": "UTC", "days": br})

    def run_tool(self, name, **args):
        got = tools.call(self.ctx, name, args)
        self.assertIs(got["isError"], False, got["content"][0]["text"])
        return got["content"][0]["text"], got["structuredContent"]

    def error(self, name, **args):
        got = tools.call(self.ctx, name, args)
        self.assertIs(got["isError"], True)
        return got["content"][0]["text"]


class WhatChanged(Base):
    def test_both_periods_whole_are_compared(self):
        text, s = self.run_tool("what_changed")
        self.assertTrue(s["compared"])
        self.assertEqual((s["now"]["from"], s["now"]["to"]), ("2026-10-08", "2026-10-14"))
        self.assertEqual((s["before"]["from"], s["before"]["to"]), ("2026-10-01", "2026-10-07"))
        self.assertEqual((s["now"]["visits"], s["before"]["visits"]), (42 * 7, 31 * 7))
        rows = {r["label"]: r for r in s["sources"]}
        self.assertEqual((rows["Search engine"]["now"], rows["Search engine"]["before"]), (210, 140))
        self.assertEqual(rows["Email"]["change"], 0)
        self.assertTrue(rows["Email"]["about_the_same"])
        self.assertIn("Direct", rows)                       # shown words, never "or unknown"
        self.assertIn("Biggest rise: Search engine (140 to 210)", text)
        self.assertIn("about the same", text)

    def test_a_withheld_day_stops_the_comparison_and_is_named(self):
        self.overview(states={"2026-10-03": "withheld"})
        text, s = self.run_tool("what_changed")
        self.assertFalse(s["compared"])
        self.assertIsNone(s["sources"])
        self.assertIn("2026-10-03", text)
        self.assertIn("Not compared", text)

    def test_a_period_before_the_first_day_is_not_measured(self):
        text, s = self.run_tool("what_changed", **{"from": "2026-10-01", "to": "2026-10-07"})
        self.assertFalse(s["compared"])
        self.assertIn("not measured", text)

    def test_lists_that_do_not_add_up_are_withheld(self):
        self.overview(before={"/extra/": 5})                # landings over the visits
        text, s = self.run_tool("what_changed")
        self.assertFalse(s["compared"])
        self.assertIn("would not add up", text)


class Todos(Base):
    def setUp(self):
        super().setUp()
        self.write("todos", TODOS)

    def test_the_list_by_state_with_the_withheld_one_named(self):
        text, s = self.run_tool("todos")
        self.assertEqual([t["id"] for t in s["todos"]], ["lost-pages", "server-errors", "sitemap"])
        self.assertEqual([t["state_words"] for t in s["todos"]],
                         ["to do", "marked done", "marked not now"])
        self.assertNotIn("rows", s["todos"][0])
        self.assertIn("Fixed: 0 server errors since 10 Oct.", text)
        self.assertIn("Marked not now", text)
        self.assertIn("Give AI the Markdown copies (the second count finds 4", text)

    def test_one_todo_gives_its_rows(self):
        text, s = self.run_tool("todos", id="lost-pages", limit=1)
        self.assertEqual(s["rows"], [{"path": "/old-a/", "people": 7}])
        self.assertEqual(s["rows_total"], 2)
        self.assertIn("/old-a/ | 7", text)

    def test_unknown_and_withheld_ids_are_plain_errors(self):
        self.assertIn("no to-do", self.error("todos", id="nope"))
        self.assertIn("withheld", self.error("todos", id="ai-markdown"))

    def test_without_accounts_it_says_nothing_can_be_marked(self):
        self.write("todos", {**TODOS, "marks": False})
        text, _ = self.run_tool("todos")
        self.assertIn("no accounts", text)


class LostPages(Base):
    def setUp(self):
        super().setUp()
        self.write("lost_pages", LOST)

    def test_lost_pages_with_the_closest_page_and_the_line(self):
        text, s = self.run_tool("lost_pages")
        self.assertEqual(s["rows_total"], 2)
        self.assertIn("/old-a/: people 7", text)
        self.assertIn("closest live page /new-a/ (the same page)", text)
        self.assertIn("location = /old-a/ { return 301 /new-a/; }", text)
        self.assertIn("no good match: answer 410 gone; marked fixed 2026-10-12", text)
        self.assertIn("2026-09-20", text)                  # the day not recorded is named

    def test_apache_lines_and_the_markdown_part(self):
        text, s = self.run_tool("lost_pages", part="markdown", server="apache")
        self.assertEqual(s["rows"][0]["page"], "/guide")
        self.assertIn("Redirect 301 /guide.md /guide", text)

    def test_fixed_part(self):
        text, s = self.run_tool("lost_pages", part="fixed")
        self.assertEqual(s["rows"][0]["verdict"], "fixed")
        self.assertIn("/old-b/: marked fixed 2026-10-12; fixed", text)

    def test_withheld_is_null_never_zero(self):
        self.write("lost_pages", {**LOST, "withheld": ["the second count finds 3 paths"],
                                  "totals": None, "lost": None, "markdown": None})
        text, s = self.run_tool("lost_pages")
        self.assertIsNone(s["rows"])
        self.assertIsNone(s["totals"])
        self.assertIn("Withheld", text)


class PageChanges(Base):
    def setUp(self):
        super().setUp()
        self.write("page_changes", CHANGES)

    def test_the_changes_with_their_verdicts(self):
        text, s = self.run_tool("page_changes")
        self.assertEqual(len(s["changes"]), 2)
        self.assertIn("/pricing/ changed 2026-09-20 (title) \"New title\": ready", text)
        self.assertIn("before 70 over 14 days (5.0 a day), after 140 over 14 days (10.0 a day), "
                      "+100% per day: up (better)", text)
        self.assertIn("waiting: no whole day after the change yet", text)
        self.assertIn("before not recorded, after not recorded", text)
        self.assertIn("/about/ 2026-10-01 (a lead the second count does not find)", text)

    def test_a_path_with_or_without_its_slash(self):
        _, s = self.run_tool("page_changes", path="/blog/x/")
        self.assertEqual([c["id"] for c in s["changes"]], ["c87654321"])
        _, s = self.run_tool("page_changes", path="/pricing")
        self.assertEqual([c["id"] for c in s["changes"]], ["c12345678"])

    def test_without_accounts(self):
        self.write("page_changes", {**CHANGES, "marks": False, "changes": []})
        text, _ = self.run_tool("page_changes")
        self.assertIn("only with accounts", text)


class AiReadiness(Base):
    def setUp(self):
        super().setUp()
        self.write("ai_ready", READY)
        self.write("page_trends", TRENDS)

    def test_the_list_and_its_filter(self):
        text, s = self.run_tool("ai_readiness")
        self.assertEqual([r["path"] for r in s["rows"]], ["/guides/webhooks/", "/old/"])
        self.assertIn("its Markdown copy failed 9 times (9 of them 404 or 410)", text)
        _, s = self.run_tool("ai_readiness", need="404")
        self.assertEqual([r["path"] for r in s["rows"]], ["/old/"])

    def test_one_page(self):
        text, s = self.run_tool("ai_readiness", path="/guides/webhooks")
        self.assertEqual(s["page"], "/guides/webhooks/")
        shut = [r["crawler"] for r in s["robots"] if not r["allowed"]]
        self.assertEqual(shut, ["Google-Extended"])
        self.assertIn("Disallow: /guides/", text)
        self.assertEqual(s["needs"]["copy_404"], 9)
        self.assertTrue(s["sitemap"]["listed"])
        self.assertEqual(s["sitemap"]["lastmod"], "2026-09-08")
        self.assertEqual(s["reads"]["last_30_days"], 2)    # its .md copy is not the page
        self.assertEqual(s["reads"]["last_day"], "2026-10-13")
        self.assertIsNone(s["reads"]["before_30_days"])    # those days are not recorded

    def test_robots_not_known_without_a_copy(self):
        self.write("ai_ready", {**READY, "robots": {**READY["robots"], "ok": False,
                                                    "crawlers": None, "error": "timed out"}})
        text, s = self.run_tool("ai_readiness", path="/pricing/")
        self.assertIsNone(s["robots"])
        self.assertIn("robots.txt: not known", text)
        self.assertIn("Markdown copy: AI asked for none", text)

    def test_a_page_not_in_the_sitemap(self):
        text, s = self.run_tool("ai_readiness", path="/old/")
        self.assertIs(s["sitemap"]["listed"], False)
        self.assertIn("Sitemap: not listed", text)

    def test_a_bad_path_is_a_plain_error(self):
        self.assertIn("starts with /", self.error("ai_readiness", path="pricing"))


class ChangedPages(Base):
    def test_changed_pages_and_the_build_time_note(self):
        self.write("page_trends", TRENDS)
        text, s = self.run_tool("changed_pages")
        self.assertEqual(s["pages_total"], 2)
        self.assertIn("/pricing/: changed 2026-10-10 (from the sitemap); 30 visits, 8 from search",
                      text)
        self.assertIn("/about/: changed 2026-10-13 (from the website); not recorded", text)
        self.assertIn("look like build times", text)

    def test_a_view_has_none(self):
        self.write("page_trends", {"whole_site_only": True})
        self.assertIn("whole site only", self.error("changed_pages"))


class Rights(Base):
    def test_a_site_the_caller_may_not_read_is_refused_by_every_new_tool(self):
        for name in ("todos", "lost_pages", "page_changes", "ai_readiness", "changed_pages",
                     "what_changed"):
            self.write(name if name != "ai_readiness" else "ai_ready", {})
        self.ctx = Context(self.tmp, checker=lambda s: (False, "not your organisation", False))
        for name in ("what_changed", "todos", "lost_pages", "page_changes", "ai_readiness",
                     "changed_pages"):
            got = tools.call(self.ctx, name, {"site": SITE})
            self.assertIs(got["isError"], True, name)
            self.assertIn("You may not read example.com", got["content"][0]["text"])

    def test_every_new_tool_is_read_only(self):
        for name in ("what_changed", "todos", "lost_pages", "page_changes", "ai_readiness",
                     "changed_pages"):
            self.assertTrue(tools.TOOLS[name]["annotations"]["readOnlyHint"])
            self.assertFalse(tools.TOOLS[name]["annotations"]["destructiveHint"])


if __name__ == "__main__":
    unittest.main()
