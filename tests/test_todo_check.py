"""Overview > Insights' "Check again" (2.44): todo_check.py, todo_checks.py,
audit_todo_checks.py, todo_api.py's settings/todo-check, and the check after an AI
agent's "done" report.

Pinned, per kind, with fake fetches (no network):
  - lost: fixed (a redirect to a live page, 410, the page back), partly ("3 of 12 still
    answer 404", those rows), not fixed, a redirect to another host never followed
  - markdown, sitemap: fixed only on a 2xx at the end; errors: fixed under 500, asked by GET
  - a site that does not answer: "Could not check", nothing marked; the time budget stops
    a check and leaves the rest for the next page
  - at most CAP addresses a check, "Check the next 50", the sweep fixed only once every
    row was asked; a stale page is refused
  - a visits to-do (leave) is never asked: "Can't check now", or what the last update found
  - the newest log lines since the fix, Skald's own asks left out
  - a fixed sweep marks the to-do fixed (kind "checked"); a later failing check puts back
    the mark before; the second count re-derives each fixed mark and finds a forged one
  - limits: one start a minute a to-do, 30 checks an hour a site
  - the route: owners and admins, CSRF, a viewer sees the result, an audit row; and the
    check that runs after an agent's "done" report
  - Skald's own user agent is ours, never a visitor or a bot
Test data: example.com, RFC 5737 addresses.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import audit_todo_checks, site_fetch, todo_check, todo_checks, todo_marks  # noqa: E402

SITE = "example.com"
CFG = {"site": {"name": SITE, "hosts": ["example.com", "www.example.com"], "timezone": "UTC"}}
NOW = datetime(2026, 10, 27, 14, 30, tzinfo=timezone.utc)


def answer(status, location=None):
    return site_fetch.Answer(status, {"location": [location]} if location else {}, b"", "", "")


class FakeSite:
    """The site, as a dict of path -> (status, location) or an exception; records each ask."""

    def __init__(self, pages: dict, default=(404, None)):
        self.pages, self.default, self.asked = pages, default, []

    def __call__(self, url, method, deadline):
        path = re.sub(r"^https://[^/]+", "", url)
        self.asked.append((method, url))
        got = self.pages.get(path, self.default)
        if isinstance(got, Exception):
            raise got
        return answer(*got)


def todo(kind="lost", n=3, **more):
    rows = [{"path": f"/old-{i}/", "people": 10 - i if i < 10 else 1, "target": f"/new-{i}/"} for i in range(n)]
    base = {"id": {"lost": "lost-pages", "markdown": "ai-markdown", "sitemap": "sitemap",
                   "errors": "server-errors"}.get(kind, "leave-0a1b2c3d"), "kind": kind, "rows": rows,
            "subject": "/landing/" if kind == "leave" else None, "window": {"last": "2026-10-26"}}
    base.update(more)
    return base


class Base(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.now = NOW
        self.clock = iter(range(0, 100000)).__next__

    def run_check(self, t, site, start=0, now=None, reader=None, by_who="person", clock=None):
        return todo_check.check(self.db, CFG, SITE, t, start, 7, by_who, fetch=site,
                                reader=reader or (lambda *a: {"read": False}), now=now or self.now,
                                today="2026-10-27", clock=clock or (lambda: 0.0), sleep=lambda s: None)

    def mark(self, item):
        return todo_marks.current(self.db, SITE).get(item)


class Lost(Base):
    def test_fixed_marks_it_fixed(self):
        site = FakeSite({"/old-0/": (301, "/new-0/"), "/old-1/": (301, "https://www.example.com/new-1/"),
                         "/old-2/": (410, None), "/new-0/": (200, None), "/new-1/": (200, None)})
        got = self.run_check(todo(), site)
        self.assertEqual(got["verdict"], "fixed")
        self.assertIn("Fixed: all 3 addresses now work", got["words"])
        self.assertIn("(2 to the suggested page)", got["words"])
        self.assertEqual(self.mark("lost-pages")["state"], "fixed")
        self.assertEqual(todo_marks.fixed_marks(self.db, SITE)["lost-pages"]["by_user"], 7)
        self.assertEqual(audit_todo_checks.verify(self.db, SITE), {})
        self.assertTrue(all(m == "HEAD" for m, _ in site.asked), "HEAD: no body is ever read")

    def test_all_redirects_say_so_in_one_line(self):
        site = FakeSite({f"/old-{i}/": (301, f"/new-{i}/") for i in range(12)}, default=(200, None))
        got = self.run_check(todo(n=12), site)
        self.assertTrue(got["words"].startswith("Fixed: all 12 addresses now answer 301 to a live page"), got["words"])

    def test_partly_names_the_rows_left(self):
        pages = {f"/old-{i}/": (301, f"/new-{i}/") for i in range(9)}
        site = FakeSite(pages, default=(200, None))
        site.pages.update({f"/old-{i}/": (404, None) for i in range(9, 12)})
        got = self.run_check(todo(n=12), site)
        self.assertEqual(got["verdict"], "partly")
        self.assertTrue(got["words"].startswith("3 of 12 addresses still answer 404"), got["words"])
        self.assertEqual([r["path"] for r in got["bad"]], ["/old-9/", "/old-10/", "/old-11/"])
        self.assertIsNone(self.mark("lost-pages"), "not fixed: no mark")

    def test_not_fixed(self):
        got = self.run_check(todo(), FakeSite({}))
        self.assertEqual(got["verdict"], "not_fixed")
        self.assertIn("Not fixed yet: all 3 addresses still answer 404", got["words"])

    def test_a_redirect_to_another_host_is_never_followed(self):
        site = FakeSite({f"/old-{i}/": (301, "https://elsewhere.example.net/x/") for i in range(3)})
        got = self.run_check(todo(), site)
        self.assertEqual(got["verdict"], "fixed")
        self.assertEqual(len(site.asked), 3, "one ask an address: the other host is never asked")
        self.assertIn("to another site", got["words"])

    def test_a_redirect_with_no_address_is_not_fixed(self):
        got = self.run_check(todo(n=1), FakeSite({}, default=(301, None)))
        self.assertEqual(got["verdict"], "not_fixed")
        self.assertIn("301 with no address to go to", got["words"])

    def test_a_redirect_to_a_404_is_not_fixed(self):
        site = FakeSite({f"/old-{i}/": (301, "/nowhere/") for i in range(3)})
        got = self.run_check(todo(), site)
        self.assertEqual(got["verdict"], "not_fixed")
        self.assertIn("301 to a page that answers 404", got["words"])

    def test_broken_again_puts_back_the_mark_before(self):
        todo_marks.mark(self.db, SITE, "lost-pages", "done", "2026-10-27", 7, now=NOW - timedelta(hours=1))
        good = FakeSite({}, default=(410, None))
        self.run_check(todo(), good)
        self.assertEqual(self.mark("lost-pages")["state"], "fixed")
        self.run_check(todo(), FakeSite({}), now=NOW + timedelta(minutes=2))
        self.assertEqual(self.mark("lost-pages")["state"], "done", "the mark it had before")
        rows = self.db.execute("SELECT state, kind FROM todo_marks ORDER BY rowid").fetchall()
        self.assertEqual(rows, [("done", None), ("fixed", "checked"), ("done", "checked")], "nothing rewritten")

    def test_a_person_cannot_mark_a_todo_fixed_by_hand(self):
        with self.assertRaises(ValueError):
            todo_marks.mark(self.db, SITE, "lost-pages", "fixed", "2026-10-27", 7)


class OtherKinds(Base):
    def test_markdown_needs_a_2xx_at_the_end(self):
        site = FakeSite({"/old-0/": (200, None), "/old-1/": (301, "/new-1/"), "/new-1/": (200, None),
                         "/old-2/": (410, None)})
        got = self.run_check(todo("markdown"), site)
        self.assertEqual(got["verdict"], "partly")
        self.assertEqual([r["path"] for r in got["bad"]], ["/old-2/"], "410 is not a Markdown copy")

    def test_sitemap_fixed(self):
        site = FakeSite({"/old-0/": (301, "/sitemap.xml")}, default=(200, None))
        self.assertEqual(self.run_check(todo("sitemap"), site)["verdict"], "fixed")

    def test_errors_fixed_under_500_asked_by_get(self):
        site = FakeSite({"/old-0/": (200, None), "/old-1/": (403, None), "/old-2/": (502, None)})
        got = self.run_check(todo("errors"), site)
        self.assertEqual(got["verdict"], "partly")
        self.assertEqual({m for m, _ in site.asked}, {"GET"})
        self.assertEqual([r["path"] for r in got["bad"]], ["/old-2/"])

    def test_the_folded_tail_is_never_asked(self):
        t = todo("errors", n=1)
        t["rows"].append({"path": "(all others)", "errors": 3})
        site = FakeSite({}, default=(200, None))
        self.assertEqual(self.run_check(t, site)["total"], 1)

    def test_head_refused_asks_with_get(self):
        site = FakeSite({}, default=(405, None))
        calls = []

        def fetch(url, method, deadline):
            calls.append(method)
            return answer(405 if method == "HEAD" else 200)
        self.run_check(todo("sitemap", n=1), fetch)
        self.assertEqual(calls, ["HEAD", "GET"])
        del site


class Network(Base):
    def test_a_site_that_does_not_answer_changes_nothing(self):
        site = FakeSite({}, default=site_fetch.Unreachable("it did not answer in time"))
        got = self.run_check(todo(), site)
        self.assertEqual(got["verdict"], "error")
        self.assertIn("did not answer (it did not answer in time)", got["words"])
        self.assertIsNone(self.mark("lost-pages"))

    def test_the_time_budget_leaves_the_rest_for_the_next_page(self):
        ticks = iter([0, 1, 1, 2, 2, todo_check.BUDGET] + [todo_check.BUDGET] * 50)
        got = self.run_check(todo(n=5), FakeSite({}, default=(410, None)), clock=lambda: next(ticks))
        self.assertEqual((got["verdict"], got["checked"], got["next"]), ("more", 2, 2))
        self.assertIn("to stay polite", got["words"])

    def test_a_refused_address_stops(self):
        site = FakeSite({}, default=site_fetch.Refused("example.com points to a private address, which Skald does not fetch."))
        got = self.run_check(todo(), site)
        self.assertEqual(got["verdict"], "error")
        self.assertEqual(len(site.asked), 1)

    def test_reserved_names_are_never_asked_for_real(self):
        with self.assertRaises(todo_check.Refused):
            todo_check.check(self.db, CFG, SITE, todo(), 0, 7, now=NOW)


class Pages(Base):
    def test_capped_then_the_next_50(self):
        t = todo(n=120)
        site = FakeSite({}, default=(410, None))
        got = self.run_check(t, site)
        self.assertEqual((got["verdict"], got["checked"], got["next"], len(site.asked)), ("more", 50, 50, 50))
        self.assertIn("Check the next 50", got["words"])
        self.assertIsNone(self.mark("lost-pages"), "not every row asked yet")
        got = self.run_check(t, site, start=50, now=NOW + timedelta(seconds=5))
        self.assertEqual((got["checked"], got["next"]), (100, 100))
        self.assertIn("Check the next 20", got["words"])
        got = self.run_check(t, site, start=100, now=NOW + timedelta(seconds=10))
        self.assertEqual((got["verdict"], got["checked"]), ("fixed", 120))
        self.assertEqual(self.mark("lost-pages")["state"], "fixed")
        self.assertEqual(audit_todo_checks.verify(self.db, SITE), {})

    def test_a_stale_page_is_refused(self):
        t = todo(n=60)
        self.run_check(t, FakeSite({}))
        with self.assertRaises(todo_check.Refused) as no:
            self.run_check(t, FakeSite({}), start=10)
        self.assertEqual(no.exception.status, 409)

    def test_limits(self):
        t = todo(n=1)
        self.run_check(t, FakeSite({}))
        with self.assertRaises(todo_check.Refused) as no:
            self.run_check(t, FakeSite({}), now=NOW + timedelta(seconds=20))
        self.assertEqual(no.exception.status, 429)
        self.assertIn("Check it again in 41 s", str(no.exception))
        for i in range(1, todo_checks.LIMIT_HOUR):
            self.run_check(t, FakeSite({}), now=NOW + timedelta(seconds=61 * i))
        with self.assertRaises(todo_check.Refused) as no:
            self.run_check(todo("sitemap", n=1), FakeSite({}), now=NOW + timedelta(seconds=61 * 30))
        self.assertIn("At most 30 checks an hour", str(no.exception))


class LogOnly(Base):
    def test_a_visits_todo_is_never_asked(self):
        site = FakeSite({})
        got = self.run_check(todo("leave"), site)
        self.assertEqual((got["verdict"], got["mode"], site.asked), ("waiting", "log", []))
        self.assertIn("Can't check now: this to-do comes from visits", got["words"])
        self.assertIn("The last data update counted up to 2026-10-26", got["words"])

    def test_what_the_last_update_found(self):
        t = todo("leave", recheck={"verdict": "fixed", "days": 3, "words": "Fixed: 40% of 50 visits left after this page since 24 Oct.",
                                   "figures": {"visits": 50, "one_page": 20, "posted": 1}})
        got = self.run_check(t, FakeSite({}))
        self.assertEqual(got["verdict"], "fixed")
        self.assertIsNone(self.mark(t["id"]), "a visits to-do is never marked fixed by a check")


class LogSince(Base):
    def test_the_log_line_since_the_mark(self):
        todo_marks.mark(self.db, SITE, "lost-pages", "done", "2026-10-27", 7, now=NOW - timedelta(minutes=20))
        seen = []

        def reader(cfg, paths, since, now, bad):
            seen.append((sorted(paths), since, bad("404"), bad("301")))
            return {"read": True, "lines": 4, "failed": 0, "newest": None, "partial": False}
        got = self.run_check(todo(), FakeSite({}, default=(410, None)), reader=reader)
        self.assertEqual(seen[0][1], NOW - timedelta(minutes=20))
        self.assertEqual(seen[0][2:], (True, False))
        self.assertIn("In the log since 14:10: none of these addresses answered 404 (4 asks).", got["words"])

    def test_no_mark_no_log_line(self):
        got = self.run_check(todo(), FakeSite({}, default=(410, None)))
        self.assertNotIn("In the log", got["words"])

    def test_read_log_counts_the_lines_and_leaves_out_skald(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {**CFG, "logs": {"dir": tmp, "base": "access.log", "format": "nginx_extended"}}
            lines = [
                ('2026-10-27T14:12:00+00:00', "/old-0/", 404, "Mozilla/5.0 (X11; Linux x86_64)"),
                ('2026-10-27T14:13:00+00:00', "/old-0/", 404, todo_check.AGENT),
                ('2026-10-27T14:14:00+00:00', "/old-1/", 301, "Googlebot/2.1"),
                ('2026-10-27T13:00:00+00:00', "/old-1/", 404, "Mozilla/5.0"),
                ('2026-10-27T14:15:00+00:00', "/other/", 404, "Mozilla/5.0"),
            ]
            lines.sort()
            Path(tmp, "access.log").write_text("".join(
                f'{w} 192.0.2.10 example.com "GET {p} HTTP/1.1" {s} 0 "-" "{ua}"\n' for w, p, s, ua in lines))
            got = todo_check.read_log(cfg, {"/old-0/", "/old-1/"}, NOW - timedelta(minutes=20), NOW,
                                      lambda s: s == "404")
        self.assertEqual((got["read"], got["lines"], got["failed"], got["newest"]), (True, 2, 1, "2026-10-27T14:12:00Z"))


class SecondCount(Base):
    def test_a_forged_fixed_mark_is_found(self):
        self.run_check(todo(), FakeSite({}))
        todo_marks._ready(self.db)
        self.db.execute("INSERT INTO todo_marks (site, item, state, day, at, kind) VALUES (?, 'lost-pages', 'fixed', "
                        "'2026-10-27', '2026-10-27T15:00:00Z', 'checked')", (SITE,))
        self.assertIn("lost-pages", audit_todo_checks.verify(self.db, SITE))

    def test_a_kept_answer_changed_after_is_found(self):
        self.run_check(todo(), FakeSite({}, default=(410, None)))
        rows = json.loads(self.db.execute("SELECT rows FROM todo_checks").fetchone()[0])
        rows[0]["status"] = 404               # a row whose "ok" no longer follows from its answer
        self.db.execute("UPDATE todo_checks SET rows = ?", (json.dumps(rows),))
        self.assertIn("2 of 3", audit_todo_checks.verify(self.db, SITE)["lost-pages"])

    def test_a_fixed_visits_todo_is_never_right(self):
        todo_marks._ready(self.db)
        self.db.execute("INSERT INTO todo_marks (site, item, state, day, at, kind) VALUES (?, 'leave-0a1b2c3d', "
                        "'fixed', '2026-10-27', '2026-10-27T15:00:00Z', 'checked')", (SITE,))
        self.assertIn("leave-0a1b2c3d", audit_todo_checks.verify(self.db, SITE))


class TheList(unittest.TestCase):
    """todos.json: a fixed mark shows the to-do Fixed; one the second count does not bear
    out shows it done, with why."""

    def setUp(self):
        from test_todos import ANCHOR, SITE as TSITE, Fixture, nf, served
        self.f = Fixture()
        self.site = TSITE
        for i in range(3):
            self.f.day(ANCHOR - timedelta(days=2 - i), [nf("/old-pricing/", 3), nf("/old-post/", 2, "search_engines")],
                       {"/": served(views=10)})

    def tearDown(self):
        self.f.close()

    def build(self):
        from skald import todos
        return {t["id"]: t for t in todos.build(self.f.page())["todos"]}

    def test_fixed_then_forged(self):
        db = self.f.accounts()
        lost = self.build()["lost-pages"]
        cfg = {"site": {"name": self.site, "hosts": [self.site]}}
        todo_check.check(db, cfg, self.site, lost, 0, 1, fetch=FakeSite({}, default=(410, None)), now=NOW,
                         reader=lambda *a: {"read": False}, sleep=lambda s: None)
        db.commit()
        got = self.build()["lost-pages"]
        self.assertEqual((got["state"], got["marked"]["state"]), ("fixed", "fixed"))
        self.assertIsNotNone(got["recheck"], "the daily re-check still runs")
        db.execute("UPDATE todo_checks SET rows = '[]'")
        db.commit()
        db.close()
        got = self.build()["lost-pages"]
        self.assertEqual(got["state"], "done")
        self.assertIn("the second count finds 0 of 2", got["fixed_withheld"])


class OwnAgent(unittest.TestCase):
    def test_skalds_ask_is_ours(self):
        from skald.classify import OWN_AGENTS
        self.assertTrue(any(tok in todo_check.AGENT for tok, _ in OWN_AGENTS))
        self.assertNotIn("skald", todo_check.AGENT.lower(), "no product name in skald/")


if __name__ == "__main__":
    unittest.main()
