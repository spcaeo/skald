"""AI readiness per page (2.35): what AI got back by address (ai_status.py, its
recount audit_ai_status.py), robots.txt read the RFC 9309 way (robots_match.py),
ai_ready.json (ai_ready.py) and its second count (audit_ai_ready.py).

Example data only: RFC 5737 addresses, example.com, made-up paths."""
from __future__ import annotations

import json
import random
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import ai_ready, ai_status, audit_ai_ready, robots_match, sitemap  # noqa: E402
from skald.store import History  # noqa: E402

from support import ASKED, GPTBOT, UTC, Sandbox, line  # noqa: E402

CLAUDEBOT = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0)"
PERPLEXITY = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"
D1, D2 = date(2026, 10, 4), date(2026, 10, 5)
ROBOTS = ("User-agent: *\nDisallow: /signup/\n\nUser-agent: GPTBot\nDisallow: /private/\n"
          "Allow: /private/open$\n\nUser-agent: Google-Extended\nDisallow: /\n")


def _line(when, path, agent, status=200, secs=0.004, ip="198.51.100.40"):
    return (f'{when.isoformat()} {ip} example.com "GET {path} HTTP/2.0" {status} '
            f'512 "-" "{agent}" {secs} cc=US ray=0000000000000000-LHR\n')


def _keep(root: Path, day: str, paths: list[str]) -> str:
    got = {"paths": sorted(paths), "sources": ["https://example.com/sitemap.xml"],
           "skipped": 0, "truncated": False}
    return sitemap.keep(root, date.fromisoformat(day), got, f"{day}T06:00:00+00:00")["list"]


def day_lines(d: date) -> list[str]:
    t = datetime(d.year, d.month, d.day, 9, tzinfo=UTC)
    m = lambda k: t + timedelta(minutes=k)   # noqa: E731
    return [
        _line(m(0), "/guide/", GPTBOT),
        _line(m(1), "/guide", ASKED, status=301),            # the plugin sends AI to the copy
        _line(m(2), "/guide.md", ASKED, status=404),
        _line(m(3), "/guide/index.md", ASKED, status=404),
        _line(m(4), "/pricing/", CLAUDEBOT, status=503),
        _line(m(5), "/pricing/", PERPLEXITY, status=403),
        _line(m(6), "/features/", ASKED, secs=1.5),
        _line(m(7), "/blog/one.md", GPTBOT),
        _line(m(8), "/gone/", PERPLEXITY, status=404),
        _line(m(9), "/private/notes/", GPTBOT),
        line(m(10), "203.0.113.5", "/pricing/"),
        # not pages: an image resizer, a scanner's probe, a sitemap with a "/" added
        _line(m(11), "/_next/image?url=%2Fa.png&w=64", GPTBOT, status=429),
        _line(m(12), "/.env", PERPLEXITY, status=404, ip="198.51.100.41"),
        _line(m(13), "/sitemap_index.xml/", PERPLEXITY, status=404),
        _line(m(14), "/old/", PERPLEXITY, status=302),       # only a redirect: said, not listed
    ]


# ------------------------------------------------------------ robots.txt

class Robots(unittest.TestCase):
    def rules(self, text, token):
        return robots_match.rules_for(robots_match.groups(text), token)["rules"]

    def test_the_longest_rule_wins_not_the_first(self):
        r = self.rules("User-agent: *\nDisallow: /\nAllow: /blog/\n", "ClaudeBot")
        self.assertEqual(robots_match.decide(r, "/blog/post/"), (True, ["allow", "/blog/"]))
        self.assertEqual(robots_match.decide(r, "/about/")[0], False)
        # Not urllib.robotparser: before Python 3.14 it took the first rule and shut /blog/ out.

    def test_wildcards_end_anchor_and_a_tie(self):
        r = [["disallow", "/*.pdf$"], ["allow", "/docs/*"], ["disallow", "/docs/*"]]
        self.assertFalse(robots_match.decide(r, "/files/a.pdf")[0])
        self.assertTrue(robots_match.decide(r, "/files/a.pdfx")[0])
        self.assertTrue(robots_match.decide(r, "/docs/x")[0], "an Allow wins a tie")
        self.assertTrue(robots_match.decide([], "/anything")[0])

    def test_the_group_is_the_tokens_own_else_star(self):
        g = robots_match.groups(ROBOTS)
        self.assertEqual(robots_match.rules_for(g, "gptbot")["agents"], ["GPTBot"])
        self.assertEqual(robots_match.rules_for(g, "ClaudeBot")["agents"], ["*"])
        self.assertEqual(robots_match.rules_for(g, "Google-Extended")["rules"], [["disallow", "/"]])
        # an empty Disallow closes the agent lines and allows everything
        g = robots_match.groups("User-agent: GPTBot\nDisallow:\n\nUser-agent: *\nDisallow: /\n")
        self.assertEqual(robots_match.rules_for(g, "GPTBot")["rules"], [])
        self.assertTrue(robots_match.decide([], "/x")[0])
        # two groups naming one crawler are one
        g = robots_match.groups("User-agent: GPTBot\nDisallow: /a\n\nUser-agent: GPTBot/1.0\nDisallow: /b\n")
        self.assertEqual(robots_match.rules_for(g, "GPTBot")["rules"], [["disallow", "/a"], ["disallow", "/b"]])

    def test_percent_encoding_is_compared_cleaned(self):
        self.assertEqual(robots_match.clean("/café/%7euser/%2f"), "/caf%C3%A9/~user/%2F")
        self.assertFalse(robots_match.decide([["disallow", "/café/"]], "/caf%C3%A9/menu")[0])
        self.assertFalse(robots_match.decide([["disallow", "/%7Euser/"]], "/~user/x")[0])

    def test_the_audit_reads_robots_txt_the_same_way(self):
        """A thousand made-up files and paths: the audit's regular expressions and the main
        road's own matching give the same group and the same verdict."""
        rnd = random.Random(7)
        bits = ["/", "/blog", "/blog/", "/a*", "*.php", "/x$", "/%7Eu", "/café", "/b*c$", "*", "/docs/*/v1"]
        agents = ["*", "GPTBot", "gptbot/1.1", "ClaudeBot", "Other"]
        paths = ["/", "/blog/x", "/a1/b", "/index.php", "/x", "/xy", "/~u/1", "/caf%C3%A9", "/bxc", "/docs/a/v1/z"]
        for _ in range(1000):
            lines = []
            for _g in range(rnd.randint(1, 3)):
                lines += [f"User-agent: {rnd.choice(agents)}" for _a in range(rnd.randint(1, 2))]
                lines += [f"{rnd.choice(['Allow', 'Disallow'])}: {rnd.choice(bits + [''])}"
                          for _r in range(rnd.randint(1, 3))]
                if rnd.random() < 0.3:
                    lines.append("Crawl-delay: 5")
            text = "\n".join(lines)
            for token in ("GPTBot", "ClaudeBot"):
                mine = robots_match.rules_for(robots_match.groups(text), token)
                agents_a, rules_a = audit_ai_ready.crawler_rules(audit_ai_ready.groups_of(text), token)
                self.assertEqual(mine["agents"], agents_a, text)
                self.assertEqual([tuple(r) for r in mine["rules"]], rules_a, text)
                for p in paths:
                    self.assertEqual(robots_match.decide(mine["rules"], p)[0],
                                     audit_ai_ready.may(rules_a, p), (text, token, p))


# ------------------------------------------------------------------ units

class Units(unittest.TestCase):
    def test_registered(self):
        from skald import audit_more, data_more, day_more, store_extras
        self.assertEqual(day_more.KINDS["ai_status"], "ai_status")
        self.assertIn("ai_status", store_extras.KINDS)
        self.assertEqual(audit_more.RECOUNTS["ai_status"], "audit_ai_status")
        self.assertEqual(audit_more.DAILY["ai_ready"], "audit_ai_ready")
        self.assertEqual(data_more.FILES["ai_ready"], "ai_ready")

    def test_a_markdown_copy_is_its_pages(self):
        for path, page in (("/a/b.md", "/a/b/"), ("/a/b/index.md", "/a/b/"), ("/a/b/.md", "/a/b/"),
                           ("/index.md", "/"), ("/.md", "/"), ("/A/B.MD/", "/A/B/"), ("/x.mdx", "/x/"),
                           ("/Index.markdown", "/")):
            self.assertEqual(ai_ready.page_of(path), (page, True), path)
            self.assertEqual(audit_ai_ready.page_and_copy(path), (page, True), path)
        for path in ("/blog", "/blog/", "/blog/?x=1", "/notes.mdown"):
            self.assertFalse(ai_ready.page_of(path)[1], path)
            self.assertEqual(ai_ready.page_of(path), audit_ai_ready.page_and_copy(path))
        self.assertTrue(ai_status.is_copy("/a/B.Md/"))


# ------------------------------------------------------------- collected

class Collected(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.log(day_lines(D1) + day_lines(D2))
        (self.box.root / "robots.txt").write_text(ROBOTS)
        (self.box.root / "robots-state.json").write_text(json.dumps(
            {"ok": True, "error": None, "url": "https://example.com/robots.txt",
             "tried_at": "2026-10-06T06:00:00+00:00", "fetched_at": "2026-10-06T06:00:00+00:00"}))
        _keep(self.box.root, "2026-10-03", ["/", "/guide/", "/pricing/", "/private/notes/", "/private/open"])
        for today in ("2026-10-05", "2026-10-06"):
            self.assertEqual(self.box.run("--today", today, "collect")[0], 0)

    def stored(self, day="2026-10-05") -> dict:
        with sqlite3.connect(self.box.db) as db:
            return json.loads(db.execute("SELECT data FROM day_extras WHERE site = 'example.com' "
                                         "AND kind = 'ai_status' AND day = ?", (day,)).fetchone()[0])

    def config(self):
        return {"site": {"hosts": ["example.com"]}, "_resolved": {"live_dir": str(self.box.root)}}

    def test_the_day_kind_and_its_recount(self):
        blob = self.stored()
        a = blob["answers"]
        self.assertEqual(a["/guide"], {"ChatGPT-User": {"301": 1}})
        self.assertEqual(a["/guide.md"], {"ChatGPT-User": {"404": 1}})
        self.assertEqual(a["/blog/one.md"], {"GPTBot": {"200": 1}}, "a copy is listed whatever it answered")
        self.assertEqual(a["/pricing/"], {"ClaudeBot": {"503": 1}, "PerplexityBot": {"403": 1}})
        self.assertNotIn("/guide/", a, "a plain 200 is counted by name only")
        self.assertEqual(blob["plain"], {"ChatGPT-User": 1, "GPTBot": 2})
        self.assertEqual(blob["slow"], {"/features/": {"ChatGPT-User": 1}})
        self.assertEqual(blob["timed"]["ChatGPT-User"], 4)
        self.assertEqual(blob["folded"], {"answers": 0, "slow": 0})
        self.assertNotIn("203.0.113", json.dumps(blob))
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err)

    def test_the_recount_catches_a_nudge(self):
        blob = self.stored()
        blob["answers"]["/guide.md"]["ChatGPT-User"]["404"] = 2
        blob["plain"]["GPTBot"] = 1
        with sqlite3.connect(self.box.db) as db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'ai_status' AND day = '2026-10-05'",
                       (json.dumps(blob),))
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_status /guide.md: ChatGPT-User 404", err)
        self.assertIn("ai_status plain: GPTBot", err)

    def test_the_folded_tail_is_recounted(self):
        with mock.patch.object(ai_status, "KEEP", 2):
            self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        blob = self.stored()
        self.assertIn(ai_status.OTHER, blob["answers"])
        self.assertEqual(len(blob["answers"]), 3)
        self.assertGreater(blob["folded"]["answers"], 0)
        self.assertEqual(self.box.run("--today", "2026-10-06", "audit")[0], 0)

    def test_verify_holds_the_sums(self):
        from skald import Classifier, read
        from skald.aggregate import summarise_views
        from skald.verify import check
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("".join(day_lines(D1)))
            totals, views = summarise_views(read([path]), Classifier([]), 30, hosts=["example.com"],
                                            views={"blog": lambda h: h.path.startswith("/blog")})
        self.assertEqual(check(totals), [])
        self.assertNotIn("ai_status", views["blog"].extras, "the whole site's only")
        totals.extras["ai_status"]["plain"]["GPTBot"] += 1
        self.assertTrue(any(p.what == "ai_status" or "ai_status" in str(p) for p in check(totals)))

    def figures(self, history):
        return ai_ready.figures(history, "example.com", history.daily("example.com", D2 - timedelta(days=29), D2),
                                D2, D2 + timedelta(days=1), self.config(), self.box.root)

    def test_the_file(self):
        with History(self.box.db) as h:
            got = self.figures(h)
        self.assertEqual(got["window"], {"days": 30, "first": "2026-09-06", "last": "2026-10-05", "of": 2,
                                         "recorded": 2, "since": "2026-10-04", "folded": 0})
        guide = got["pages"]["/guide/"]
        self.assertEqual(guide["self"], {"ChatGPT-User": {"301": 2}})
        self.assertEqual(guide["copies"], {"/guide.md": {"ChatGPT-User": {"404": 2}},
                                           "/guide/index.md": {"ChatGPT-User": {"404": 2}}})
        self.assertEqual(got["pages"]["/features/"]["slow"], {"ChatGPT-User": 2})
        r = got["robots"]
        self.assertTrue(r["ok"])
        self.assertFalse(r["crawlers"]["Google-Extended"]["root"])
        self.assertEqual(r["crawlers"]["GPTBot"]["rules"], [["disallow", "/private/"], ["allow", "/private/open$"]])
        self.assertEqual(got["sitemap"]["pages"], {"/": None, "/guide/": None, "/pricing/": None,
                                                   "/private/notes/": None, "/private/open/": None})
        rows = {x["path"]: x for x in got["attention"]["rows"]}
        self.assertEqual(rows["/guide/"]["copy_errors"], 4)
        self.assertEqual(rows["/guide/"]["copy_404"], 4)
        self.assertEqual(rows["/guide/"]["redirects"], 2)
        self.assertEqual(rows["/pricing/"]["server_errors"], 2)
        self.assertEqual(rows["/pricing/"]["blocked"], 2)
        self.assertEqual(rows["/gone/"]["not_found"], 2)
        self.assertIs(rows["/gone/"]["listed"], False)
        # the path rule shuts GPTBot out (Google-Extended is out of the whole site: said once)
        self.assertEqual(rows["/private/notes/"]["robots"], ["GPTBot"])
        self.assertNotIn("/blog/one/", rows, "a copy that answered 200 needs nothing")
        for path in ("/_next/image", "/.env", "/sitemap_index.xml/"):
            self.assertNotIn(path, got["pages"], "not shaped like a page")
        self.assertEqual(got["pages"]["/old/"]["self"], {"PerplexityBot": {"302": 2}})
        self.assertNotIn("/old/", rows, "a redirect alone is no need")
        self.assertEqual([x["path"] for x in got["attention"]["rows"]][:2], ["/guide/", "/pricing/"])
        self.assertEqual(got["attention"]["total"], len(rows))

    def test_the_recount_agrees_and_catches_a_change(self):
        with History(self.box.db) as h:
            got = self.figures(h)
            self.assertEqual(audit_ai_ready.recheck(h.db, "example.com", D2, D2 + timedelta(days=1),
                                                    self.config(), self.box.root, got), [])
            got["pages"]["/guide/"]["copies"]["/guide.md"]["ChatGPT-User"]["404"] = 1
            got["attention"]["rows"][1]["blocked"] = 0
            got["robots"]["crawlers"]["GPTBot"]["root"] = False
            problems = audit_ai_ready.recheck(h.db, "example.com", D2, D2 + timedelta(days=1),
                                              self.config(), self.box.root, got)
        self.assertTrue(any("ai readiness /guide/" in p for p in problems), problems)
        self.assertTrue(any("needs /pricing/" in p for p in problems), problems)
        self.assertTrue(any("GPTBot's robots.txt" in p for p in problems), problems)

    def test_daily_from_run_dailys_context(self):
        ctx = SimpleNamespace(site="example.com", config=self.config(), live_dir=str(self.box.root),
                              out=lambda *_: None, history=lambda: History(self.box.db))
        self.assertEqual(audit_ai_ready.daily(ctx, D2), [])

    def test_robots_not_kept_is_not_known_and_a_404_is_none(self):
        (self.box.root / "robots.txt").unlink()
        (self.box.root / "robots-state.json").write_text(json.dumps({"ok": False, "error": "TimeoutError: timed out"}))
        with History(self.box.db) as h:
            got = self.figures(h)
            self.assertIsNone(got["robots"]["crawlers"])
            self.assertFalse(got["robots"]["missing"])
            self.assertTrue(all(r["robots"] == [] for r in got["attention"]["rows"]))
            self.assertEqual(audit_ai_ready.recheck(h.db, "example.com", D2, D2 + timedelta(days=1),
                                                    self.config(), self.box.root, got), [])
        (self.box.root / "robots-state.json").write_text(json.dumps({"ok": False, "error": "HTTPError: HTTP Error 404: Not Found"}))
        with History(self.box.db) as h:
            got = self.figures(h)
            self.assertTrue(got["robots"]["missing"])
            self.assertEqual(audit_ai_ready.recheck(h.db, "example.com", D2, D2 + timedelta(days=1),
                                                    self.config(), self.box.root, got), [])

    def test_no_sitemap_kept_is_null(self):
        import shutil
        shutil.rmtree(self.box.root / "sitemaps")
        with History(self.box.db) as h:
            got = self.figures(h)
            self.assertIsNone(got["sitemap"]["pages"])
            self.assertTrue(all(r["listed"] is None for r in got["attention"]["rows"]))
            self.assertEqual(audit_ai_ready.recheck(h.db, "example.com", D2, D2 + timedelta(days=1),
                                                    self.config(), self.box.root, got), [])

    def test_written_by_the_dashboard(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "dashboard")[0], 0)
        got = json.loads((self.box.root / "www" / "example.com" / "data" / "ai_ready.json").read_text())
        self.assertEqual(got["schema_version"], 1)
        self.assertEqual(got["attention"]["rows"][0]["path"], "/guide/")

    def test_a_day_before_it_was_kept_is_not_recorded(self):
        with sqlite3.connect(self.box.db) as db:
            db.execute("DELETE FROM day_extras WHERE kind = 'ai_status' AND day = '2026-10-04'")
        with History(self.box.db) as h:
            got = self.figures(h)
            self.assertEqual((got["window"]["of"], got["window"]["recorded"], got["window"]["since"]),
                             (2, 1, "2026-10-05"))
            self.assertEqual(got["pages"]["/guide/"]["self"], {"ChatGPT-User": {"301": 1}})
            self.assertEqual(audit_ai_ready.recheck(h.db, "example.com", D2, D2 + timedelta(days=1),
                                                    self.config(), self.box.root, got), [])

    def test_a_view_gets_the_whole_sites_note(self):
        self.assertEqual(ai_ready.build(SimpleNamespace(view=object())), {"whole_site_only": True})


if __name__ == "__main__":
    unittest.main()
