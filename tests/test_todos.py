"""Overview > Insights' to-dos and Site > Not found's lost pages (2.35).

closest_page.py: the closest live page for an old address (exact, likely, guess, none)
and the server lines to copy. lost_pages.py and todos.py: what each figure is made of,
the thresholds, the marks (done, not now, fixed) and the re-check after a to-do was
marked done; and that their second count (audit_todos.py) agrees with them, and
withholds what it does not find the same. todo_api.py: the CSV and the mail.

Every history row here is written by SQL into a real history file, so the second count
reads the same file by its own road. Hosts are example.com; no address anywhere.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import audit_todos, closest_page, lost_pages, todo_api, todo_marks, todos  # noqa: E402
from skald.closest_page import EXACT, GUESS, LIKELY, Live, closest, rules  # noqa: E402
from skald.data_files import Page  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 25, 15, tzinfo=UTC)
ANCHOR = date(2026, 10, 24)
SITE = "example.com"

LIVE = ["/", "/about-us/", "/contact-us/", "/pricing/", "/blog/", "/blog/how-to-track-ai-visits/",
        "/guides/", "/guides/server-log-analytics-for-wordpress/", "/guides/setup/",
        "/features/ai-crawler-reports/", "/features/", "/docs/install/", "/docs/"]


class Matcher(unittest.TestCase):
    def setUp(self):
        self.live = Live(LIVE)

    def test_exact(self):
        for old, want in [("/Pricing/", "/pricing/"), ("/pricing", "/pricing/"),
                          ("/pricing/](https:/www.example.com/pricing/", "/pricing/"),
                          ("/blog/how-to-track-ai-visits/&sessionid=abc/", "/blog/how-to-track-ai-visits/"),
                          ("/pricing-2/", "/pricing/"), ("/home/", "/"), ("/docs/install/index.html", "/docs/install/"),
                          # the same three-word slug under another section: moved
                          ("/blog/server-log-analytics-for-wordpress/", "/guides/server-log-analytics-for-wordpress/")]:
            target, how, why = closest(old, self.live)
            self.assertEqual((target, how), (want, EXACT), (old, why))

    def test_likely(self):
        for old, want in [("/blog/ai-crawler-reports-explained/", "/features/ai-crawler-reports/"),
                          ("/about/", "/about-us/"), ("/contact/", "/contact-us/"),
                          ("/blog/page/3/", "/blog/")]:
            target, how, why = closest(old, self.live)
            self.assertEqual((target, how), (want, LIKELY), (old, why))

    def test_guess_is_the_live_section_never_the_home_page(self):
        target, how, _ = closest("/guides/old-checklist/", self.live)
        self.assertEqual((target, how), ("/guides/", GUESS))
        # One word in common is not a guess, and the home page is never the section.
        self.assertEqual(closest("/ai-for-retail/", self.live)[:2], (None, None))

    def test_no_match(self):
        for old in ("/sovereign-vendor-checklist/", "/careers/old-role/", "/x/"):
            self.assertEqual(closest(old, self.live)[:2], (None, None), old)

    def test_a_short_slug_is_not_a_moved_page(self):
        live = Live(["/features/setup/", "/docs/"])
        # "/setup/" under another section could be any page's: not "the same page".
        self.assertNotEqual(closest("/blog/setup/", live)[1], EXACT)

    def test_the_server_lines(self):
        self.assertEqual(rules("/old/", "/new/"), {"nginx": "location = /old/ { return 301 /new/; }",
                                                   "apache": "Redirect 301 /old/ /new/"})
        self.assertEqual(rules("/old/", None), {"nginx": "location = /old/ { return 410; }",
                                                "apache": "Redirect gone /old/"})
        # Decoded first; a character a rule would need escaped: written by hand.
        self.assertEqual(rules("/old%2Dpage/", None)["apache"], "Redirect gone /old-page/")
        self.assertEqual(rules("/a b/", "/new/"), {"nginx": None, "apache": None})
        self.assertEqual(rules("/old/;rm", None), {"nginx": None, "apache": None})


def nf(path, n, group="people", probe=False, status=404, source="(none)"):
    return {"path": path, "status": status, "group": group, "probe": probe, "source": source,
            "source_kind": "Direct or unknown", "utm_source": "", "n": n, "first": "09:00", "last": "10:00"}


def served(views=0, search=0, asked=0, training=0):
    return {"views": views, "readers": views, "visits": views, "entries": 0, "exits": 0, "after_pages": 0,
            "not_found_from": 0, "posts_from": 0, "ai_asked": asked, "ai_training": training, "search": search,
            "time": {}, "sources": {}, "assistants": {}, "countries": {}}


class Fixture:
    """A history file and the folder beside it, filled by SQL."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "history.sqlite"
        History(self.path).db.close()
        self.db = sqlite3.connect(self.path)
        self.config = {"site": {"name": SITE, "hosts": [SITE]}, "report": {"timezone": "UTC"},
                       "_resolved": {"history_db": str(self.path), "live_dir": str(self.dir)}}

    def day(self, d: date, not_found=(), pages=None, counts=(), journeys=(), verified=1):
        iso = d.isoformat()
        self.db.execute("INSERT OR REPLACE INTO days (site, day, timezone, collected_at, verified, parsed, hits, "
                        "other_hosts, cited_visits, extras) VALUES (?, ?, 'UTC', ?, ?, 0, 0, 0, 0, 1)",
                        (SITE, iso, NOW.isoformat(), verified))
        for kind, blob in (("not_found", list(not_found)), ("pages", pages or {})):
            self.db.execute("INSERT OR REPLACE INTO day_extras (site, day, kind, data) VALUES (?, ?, ?, ?)",
                            (SITE, iso, kind, json.dumps(blob)))
        for kind, name, n in counts:
            self.db.execute("INSERT OR REPLACE INTO counts (site, day, kind, name, n) VALUES (?, ?, ?, ?, ?)",
                            (SITE, iso, kind, name, n))
        for i, j in enumerate(journeys):
            self.db.execute("INSERT INTO journeys (site, day, seq, data) VALUES (?, ?, ?, ?)",
                            (SITE, iso, i, json.dumps(j)))
        self.db.commit()

    def sitemap(self, paths):
        from skald import sitemap
        folder = self.dir / "sitemaps"
        folder.mkdir(exist_ok=True)
        lid = sitemap.list_id(sorted(paths))
        (folder / f"{lid}.json").write_text(json.dumps({"paths": sorted(paths)}))
        (folder / "days.json").write_text(json.dumps({ANCHOR.isoformat(): {"list": lid, "paths": len(paths)}}))

    def page(self, now=NOW):
        return Page(History(self.path), SITE, SITE, None, UTC, now, None, self.config, live_dir=self.dir)

    def accounts(self):
        """An accounts file beside the history (sessions mode's), for the marks."""
        db = sqlite3.connect(self.dir / "accounts.sqlite")
        return db

    def close(self):
        self.db.close()
        self.tmp.cleanup()


def visit(landing, pages=1, posted=0, source="Search engine"):
    return {"landing": landing, "pages": pages, "posted": posted, "source": source}


class LostPages(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.f.sitemap(["/", "/pricing/", "/guides/", "/guides/setup/"])
        d1, d2 = ANCHOR - timedelta(days=1), ANCHOR
        self.f.day(d1, [nf("/old-pricing/", 3), nf("/old-pricing/", 4, "search_engines"),
                        nf("/.env", 9, "bots", probe=True), nf("/only-bots/", 5, "bots"),
                        nf("/guides/old/", 2, "ai_training"), nf("/guides/setup.md", 6, "ai_asked"),
                        nf("/ancient/post.md", 2, "ai_training"), nf("/sitemap_index.xml", 4, "search_engines"),
                        nf("/came-back/", 2), nf("/wp-json/wp/v2/posts", 3), nf("/logo.png", 3)],
                   {"/": served(views=10), "/came-back/": served(views=1)})
        self.f.day(d2, [nf("/old-pricing/", 1, "ai_asked"), nf("/Pricing", 2)],
                   {"/": served(views=8), "/came-back/": served(views=2)})
        # A withheld day is never summed.
        self.f.day(ANCHOR - timedelta(days=2), [nf("/old-pricing/", 500)], verified=0)

    def tearDown(self):
        self.f.close()

    def test_what_is_lost_and_what_is_not(self):
        body = lost_pages.build(self.f.page())
        self.assertEqual(body["withheld"], [])
        rows = {r["path"]: r for r in body["lost"]}
        # Probes, bots only, assets, APIs, sitemaps and Markdown are not lost pages; an address
        # served again after it failed is live.
        self.assertEqual(set(rows), {"/old-pricing/", "/guides/old/", "/Pricing"})
        old = rows["/old-pricing/"]
        self.assertEqual((old["people"], old["search"], old["ai"]), (3, 4, 1))
        self.assertEqual(old["target"], "/pricing/")
        self.assertEqual(rows["/Pricing"]["match"], "exact")
        self.assertEqual(rows["/guides/old/"]["target"], "/guides/")
        self.assertEqual(rows["/guides/old/"]["nginx"], "location = /guides/old/ { return 301 /guides/; }")
        self.assertEqual(body["totals"], {"paths": 3, "people": 5, "search": 4, "ai": 3, "md_paths": 2,
                                          "md_live": 1, "md_asks": 8, "md_live_asks": 6})
        self.assertEqual([r["path"] for r in body["markdown"]["live"]], ["/guides/setup.md"])
        self.assertEqual(body["markdown"]["live"][0]["page"], "/guides/setup/")
        # A suggested redirect also offers 410 gone; a .md copy of a live page its own line.
        self.assertEqual(rows["/guides/old/"]["gone"], {"nginx": "location = /guides/old/ { return 410; }",
                                                        "apache": "Redirect gone /guides/old/"})
        self.assertEqual(body["markdown"]["live"][0]["apache"], "Redirect 301 /guides/setup.md /guides/setup/")
        self.assertEqual(body["window"]["days"], 2)
        self.assertFalse(body["marks"])                 # no accounts: nothing can be marked

    def test_the_second_count_agrees_and_withholds_what_it_does_not(self):
        p = self.f.page()
        body = lost_pages.build(p)
        found = lost_pages.Found(p)
        self.assertEqual(audit_todos.check_lost(p.history.db, SITE, found.first, found.last, body, found), [])
        body["lost"][0]["people"] += 1
        why = audit_todos.check_lost(p.history.db, SITE, found.first, found.last, body, found)
        self.assertTrue(why and "second count" in why[0], why)

    def test_after_the_fix(self):
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "path:/old-pricing/", "fixed", (ANCHOR - timedelta(days=1)).isoformat())
        db.close()
        body = lost_pages.build(self.f.page())
        self.assertTrue(body["marks"])
        fixed = {r["path"]: r for r in body["fixed"]}
        # Marked on the first day: only the day after counts, and it still failed for AI.
        self.assertEqual((fixed["/old-pricing/"]["days"], fixed["/old-pricing/"]["ai"]), (1, 1))
        self.assertEqual(fixed["/old-pricing/"]["verdict"], "not_yet")
        self.assertEqual({r["path"]: r["marked"] for r in body["lost"]}["/old-pricing/"],
                         (ANCHOR - timedelta(days=1)).isoformat())


class Todos(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.f.sitemap(["/", "/pricing/", "/guides/", "/guides/setup/"])
        for i in range(3):
            d = ANCHOR - timedelta(days=2 - i)
            self.f.day(d, [nf("/old-pricing/", 3), nf("/old-post/", 2, "search_engines"),
                           nf("/guides/setup.md", 2, "ai_asked"), nf("/sitemap_index.xml", 1, "search_engines")],
                       {"/": served(views=10)},
                       counts=[("server_error_page", "/", 2), ("status_people", "5xx", 1),
                               ("status_bots", "5xx", 1)],
                       journeys=[visit("/landing/") for _ in range(9)] + [visit("/", pages=3)])

    def tearDown(self):
        self.f.close()

    def build(self, now=NOW):
        return todos.build(self.f.page(now))

    def test_each_todo_from_its_figures_over_its_threshold(self):
        body = self.build()
        self.assertEqual(body["withheld"], [])
        got = {t["id"]: t for t in body["todos"]}
        self.assertEqual(list(got)[:4], ["lost-pages", "server-errors", "ai-markdown", "sitemap"])
        self.assertEqual(got["lost-pages"]["figures"], {"paths": 2, "people": 9, "search": 6, "ai": 0})
        self.assertIn("2 old page addresses answered 'not found' from 22 Oct to 24 Oct", got["lost-pages"]["proof"])
        self.assertEqual(got["server-errors"]["figures"], {"errors": 6, "paths": 1, "people": 3})
        self.assertEqual(got["ai-markdown"]["figures"], {"pages": 1, "asks": 6})
        self.assertEqual(got["sitemap"]["figures"], {"paths": 1, "asked": 3, "search": 3})
        leave = [t for t in body["todos"] if t["kind"] == "leave"]
        self.assertEqual(len(leave), 1)
        self.assertEqual(leave[0]["figures"], {"visits": 27, "one_page": 27, "posted": 0})
        self.assertEqual(leave[0]["open"], {"tab": "traffic/pages", "page": "/landing/", "name": "Traffic > Pages"})
        self.assertNotIn("/landing/", leave[0]["id"])     # an opaque id, never the page
        self.assertEqual(got["lost-pages"]["rows"][0]["path"], "/old-pricing/")

    def test_under_the_threshold_there_is_no_todo(self):
        old = dict(todos.LIMITS)
        try:
            todos.LIMITS.update(lost_min_asks=100, errors_min=100, markdown_min_asks=100,
                                sitemap_min_asks=100, leave_min_visits=100)
            self.assertEqual(self.build()["todos"], [])
        finally:
            todos.LIMITS.clear()
            todos.LIMITS.update(old)

    def test_done_is_rechecked_on_the_days_after(self):
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "server-errors", "done", ANCHOR.isoformat())
        todo_marks.mark(db, SITE, "sitemap", "notnow", ANCHOR.isoformat())
        db.close()
        got = {t["id"]: t for t in self.build()["todos"]}
        self.assertEqual(got["server-errors"]["state"], "done")
        self.assertEqual(got["server-errors"]["recheck"]["verdict"], "waiting")
        self.assertEqual(got["sitemap"]["state"], "notnow")
        # A whole day after the mark with no server error: fixed.
        day = ANCHOR + timedelta(days=1)
        self.f.day(day, [], {"/": served(views=4)})
        got = {t["id"]: t for t in self.build(NOW + timedelta(days=1))["todos"]}
        r = got["server-errors"]["recheck"]
        self.assertEqual((r["verdict"], r["figures"], r["days"]), ("fixed", {"errors": 0}, 1))
        self.assertEqual(r["words"], "Fixed: 0 server errors since 24 Oct.")

    def test_a_done_lost_pages_todo_counts_the_same_addresses_again(self):
        db = self.f.accounts()
        todo_marks.mark(db, SITE, "lost-pages", "done", (ANCHOR - timedelta(days=1)).isoformat())
        db.close()
        got = {t["id"]: t for t in self.build()["todos"]}
        r = got["lost-pages"]["recheck"]
        self.assertEqual((r["verdict"], r["figures"]), ("not_yet", {"asked": 5}))
        self.assertEqual(r["words"], "Not yet: 5 not-found answers since 23 Oct.")

    def test_the_second_count_withholds_a_todo_it_does_not_find_the_same(self):
        p = self.f.page()
        body = todos.build(p)
        t = next(x for x in body["todos"] if x["id"] == "server-errors")
        t["figures"]["errors"] += 1
        held = audit_todos.check_todos(p.history.db, SITE, body["todos"], p.live_dir, p.anchor.isoformat())
        self.assertEqual(list(held), ["server-errors"])


class Marks(unittest.TestCase):
    def test_items_states_and_history_kept(self):
        self.assertTrue(todo_marks.valid_item("lost-pages"))
        self.assertTrue(todo_marks.valid_item("path:/old/"))
        for bad in ("Lost", "path:old", "path:/a\nb", "x" * 41, None, "path:/" + "a" * 300):
            self.assertFalse(todo_marks.valid_item(bad), bad)
        db = sqlite3.connect(":memory:")
        todo_marks.mark(db, SITE, "lost-pages", "done", "2026-10-20")
        todo_marks.mark(db, SITE, "lost-pages", "done", "2026-10-22")
        self.assertEqual(todo_marks.current(db, SITE)["lost-pages"]["first_day"], "2026-10-20")
        todo_marks.mark(db, SITE, "lost-pages", "open", "2026-10-23")
        self.assertEqual(todo_marks.current(db, SITE), {})
        self.assertEqual(db.execute("SELECT COUNT(*) FROM todo_marks").fetchone()[0], 3)   # never deleted
        with self.assertRaises(ValueError):
            todo_marks.mark(db, SITE, "lost-pages", "fixed", "2026-10-23")
        with self.assertRaises(ValueError):
            todo_marks.mark(db, SITE, "path:/old/", "done", "2026-10-23")


class Mail(unittest.TestCase):
    TODO = {"id": "server-errors", "title": "Fix the server errors", "proof": "6 server errors.",
            "todo": "Send the list.", "check": "the server errors", "file": "server-errors.csv",
            "columns": [{"key": "path", "label": "Address"}, {"key": "errors", "label": "Server errors"}],
            "rows": [{"path": "/", "errors": 6}, {"path": "=cmd()", "errors": 1}], "rows_total": 2}

    def test_the_csv_guards_formulas(self):
        self.assertEqual(todo_api.rows_csv(self.TODO), "Address,Server errors\r\n/,6\r\n'=cmd(),1\r\n")

    def test_no_mail_server_no_dialog(self):
        state = todo_api.mail_state({"site": {"name": SITE}})
        self.assertFalse(state["ready"])
        self.assertIn("Settings > Mail", state["why"])

    def test_one_mail_with_the_csv_and_the_link(self):
        cfg = {"site": {"name": SITE}, "dashboard": {"url": "https://stats.example.com/traffic/example.com/"},
               "mail": {"host": "smtp.example.com", "from": "skald@example.com"}}
        sent = []
        self.assertIsNone(todo_api.send_one(cfg, SITE, self.TODO, "dev@example.com", "owner@example.com",
                                            send=lambda msg, c: sent.append((msg, c))))
        msg, c = sent[0]
        self.assertEqual(c["to"], ["dev@example.com"])
        files = [part.get_filename() for part in msg.iter_attachments()]
        self.assertEqual(files, ["server-errors.csv"])
        text = msg.get_body(("plain",)).get_content()
        self.assertIn("https://stats.example.com/traffic/example.com/#overview/insights?todo=server-errors", text)
        self.assertIn("not available to you", text)


if __name__ == "__main__":
    unittest.main()
