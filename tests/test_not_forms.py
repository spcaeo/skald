"""A page's own script is not "sent a form" (form_names.py).

The owner's case (docomatic.ai, 30 Oct): one page, then four seconds later
POST /api/events answered 204 with 0 bytes, referrer that page. The site's
own event script, sent by every page view; the visit read "sent a form".

What is pinned: that POST is no form, on both roads; a real form POST (200 or
303 to a page path) still is; the shared list, the 204 rule and the site's
own list (site.script_posts); the suggestion rule (half of the visits that
sent a POST, a fifth of all visits, on 3 days); the audit road agrees and
shares only the name lists; a recount (backfill --force) rebuilds the stored
figures, and a day stored before the rule says so until it is recounted.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit, audit_visits, form_names, not_pages, settings_store  # noqa: E402
from skald.classify import Classifier  # noqa: E402
from skald.parse import PARSERS  # noqa: E402
from skald.visits import Journeys  # noqa: E402

from support import CHROME, UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 10, 24)
TODAY = "2026-10-25"
NOON = datetime(DAY.year, DAY.month, DAY.day, 12, tzinfo=UTC)
PAGE = "/deadline/us/ca/counties/sutter"


def post(when: datetime, address: str, path: str, status: int = 204, size: str = "0",
         referrer: str = f"https://example.com{PAGE}") -> str:
    """One nginx_extended POST line."""
    return (f'{when.isoformat()} {address} example.com "POST {path} HTTP/2.0" {status} {size} '
            f'"{referrer}" "{CHROME}" 0.004 cc=US ray=0000000000000000-LHR\n')


def hit(raw: str, config: dict | None = None):
    got = PARSERS["nginx_extended"](raw)
    if config is not None:
        got.page_rules = not_pages.from_config(config)
    return got


def both(raw: str, config: dict | None = None) -> tuple[bool, bool]:
    """(main road: a form, audit road: a form) for one line."""
    main = hit(raw, config).is_form_post
    other = audit_visits.NotForm(config).form(audit.line_hit(raw))
    return main, other


class TestTheOwnersVisit(unittest.TestCase):

    def test_api_events_204_after_a_page_is_no_form(self):
        raw = post(NOON + timedelta(seconds=4), "203.0.113.30", "/api/events")
        self.assertEqual(both(raw), (False, False))
        self.assertEqual(hit(raw).script_post, "204")

    def test_the_visit_is_not_marked(self):
        lines = [line(NOON, "203.0.113.30", PAGE),
                 post(NOON + timedelta(seconds=4), "203.0.113.30", "/api/events")]
        journeys = Journeys(own_hosts={"example.com"})
        c = Classifier()
        for raw in lines:
            h = PARSERS["nginx_extended"](raw)
            journeys.add(h, c(h))
        got, stats = journeys.finish(50)
        self.assertEqual(got[0]["posted"], 0)
        self.assertEqual(got[0]["forms"], form_names.FORMS_RULE)
        self.assertEqual(stats.flags.get("posted", 0), 0)
        self.assertEqual(journeys.people[0]["posts"], [])

    def test_a_real_form_post_still_is_one(self):
        for status, size in ((200, "5120"), (303, "0"), (302, "-")):
            raw = post(NOON, "203.0.113.31", "/contact", status, size)
            with self.subTest(status=status):
                self.assertEqual(both(raw), (True, True))
        lines = [line(NOON, "203.0.113.31", "/contact"),
                 post(NOON + timedelta(seconds=20), "203.0.113.31", "/contact", 303, "0")]
        journeys = Journeys(own_hosts={"example.com"})
        c = Classifier()
        for raw in lines:
            h = PARSERS["nginx_extended"](raw)
            journeys.add(h, c(h))
        got, stats = journeys.finish(50)
        self.assertEqual(got[0]["posted"], 1)
        self.assertEqual(stats.flags["posted"], 1)
        self.assertEqual(len(journeys.people[0]["posts"]), 1)
        # Only a 2xx answer goes into the paths the suggestions read.
        self.assertEqual(dict(stats.post_paths), {})


class TestTheList(unittest.TestCase):

    def test_each_entry_and_its_shape(self):
        cases = {"/api/events": False, "/API/Events/": False, "/api/event": False,
                 "/api/analytics": False, "/api/collect": False, "/api/track": False,
                 "/api/sentry": False, "/api/sentry-tunnel": False, "/monitoring": False,
                 "/_vercel/insights/view": False, "/_vercel/speed-insights/vitals": False,
                 "/cdn-cgi/rum": False, "/ingest/e/": False,
                 # Still forms: not on the list, or only like an entry.
                 "/api/eventsx": True, "/api/events/123": True, "/api/contact": True,
                 "/contact": True, "/monitoring/x": True, "/ingest": True,
                 "/wp-admin/admin-ajax.php": True, "/wp-json/batch/v1": True}
        for path, form in cases.items():
            with self.subTest(path=path):
                self.assertEqual(both(post(NOON, "203.0.113.32", path, 200, "31")), (form, form))

    def test_every_entry_is_a_valid_own_entry_too(self):
        self.assertEqual(form_names.clean(list(form_names.SCRIPT_POSTS)),
                         list(form_names.SCRIPT_POSTS))

    def test_a_get_is_never_a_form(self):
        self.assertFalse(hit(line(NOON, "203.0.113.33", "/contact")).is_form_post)
        self.assertEqual(hit(line(NOON, "203.0.113.33", "/api/events")).script_post, "")


class TestARefusedPost(unittest.TestCase):
    """Rule 3: a POST the site refused is no form (the owner's 24 Oct: every
    visit still "sent a form" was a scanner's POST answered 301, 404, 405, 444)."""

    def test_refused_answers_are_no_form_on_both_roads(self):
        for status in (301, 307, 308, 404, 405, 410, 444, 501):
            for path in ("/graphql", "/xmlrpc.php", "/", "/contact"):
                with self.subTest(status=status, path=path):
                    self.assertEqual(both(post(NOON, "203.0.113.34", path, status, "162")),
                                     (False, False))

    def test_a_form_taken_failed_or_answered_with_a_reason_still_counts(self):
        for status in (200, 201, 302, 303, 400, 403, 422, 429, 500, 502, 503):
            with self.subTest(status=status):
                self.assertEqual(both(post(NOON, "203.0.113.34", "/contact", status, "162")),
                                 (True, True))

    def test_the_scanner_s_visit_is_not_marked(self):
        lines = [line(NOON, "203.0.113.35", PAGE),
                 post(NOON + timedelta(seconds=9), "203.0.113.35", "/graphql", 404, "162"),
                 post(NOON + timedelta(seconds=10), "203.0.113.35", "/api/graphql", 405, "162"),
                 post(NOON + timedelta(seconds=11), "203.0.113.35", "/v1/graphql", 301, "162")]
        journeys = Journeys(own_hosts={"example.com"})
        c = Classifier()
        for raw in lines:
            h = PARSERS["nginx_extended"](raw)
            journeys.add(h, c(h))
        got, stats = journeys.finish(50)
        self.assertEqual(got[0]["posted"], 0)
        self.assertEqual(stats.flags.get("posted", 0), 0)
        self.assertEqual(journeys.people[0]["posts"], [])

    def test_recent_requests_say_refused(self):
        from skald import requests_feed
        from skald.parse import Hit
        h = Hit(NOON, "203.0.113.36", "example.com", "POST", "/graphql", "405",
                f"https://example.com{PAGE}", CHROME)
        got = requests_feed.row(h, Classifier()(h), UTC, lambda ip: False, False)
        self.assertEqual(got["kind"], "refused_post")
        self.assertIn("not a form", got["rule"])
        h = Hit(NOON, "203.0.113.36", "example.com", "POST", "/contact", "303",
                f"https://example.com{PAGE}", CHROME)
        self.assertEqual(requests_feed.row(h, Classifier()(h), UTC, lambda ip: False,
                                           False)["kind"], "post")


class TestThe204Rule(unittest.TestCase):

    def test_any_path_answered_204_with_no_body(self):
        for size in ("0", "-"):
            with self.subTest(size=size):
                self.assertEqual(both(post(NOON, "203.0.113.34", "/contact", 204, size)),
                                 (False, False))

    def test_a_204_with_a_body_is_not_the_rule(self):
        self.assertEqual(both(post(NOON, "203.0.113.34", "/contact", 204, "12")), (True, True))

    def test_admin_ajax_stays_a_form_unless_answered_204(self):
        path = "/wp-admin/admin-ajax.php"
        self.assertEqual(both(post(NOON, "203.0.113.35", path, 200, "45")), (True, True))
        self.assertEqual(both(post(NOON, "203.0.113.35", path, 204, "0")), (False, False))

    def test_skald_s_own_endpoints_stay_out(self):
        self.assertEqual(both(post(NOON, "203.0.113.36", "/traffic-beacon", 200, "2")),
                         (False, False))
        self.assertEqual(hit(post(NOON, "203.0.113.36", "/traffic-beacon", 200, "2")).script_post,
                         form_names.SKALD)


class TestTheSitesOwnList(unittest.TestCase):

    CONFIG = {"site": {"script_posts": ["/landing/ping", "/hooks/*"]}}

    def test_its_entries_are_no_form_on_both_roads(self):
        for path, form in (("/landing/ping", False), ("/Landing/Ping/", False),
                           ("/hooks/a/b", False), ("/landing/pingx", True), ("/hook", True)):
            with self.subTest(path=path):
                self.assertEqual(both(post(NOON, "203.0.113.37", path, 200, "9"), self.CONFIG),
                                 (form, form))
        self.assertEqual(hit(post(NOON, "203.0.113.37", "/hooks/x", 200, "9"),
                             self.CONFIG).script_post, "site: /hooks/*")

    def test_without_it_they_are_forms(self):
        self.assertEqual(both(post(NOON, "203.0.113.37", "/landing/ping", 200, "9"), {}),
                         (True, True))

    def test_an_unreadable_list_is_none_on_both_roads(self):
        for raw in (["no-slash"], ["/"], ["/a*b"], ["/a?b"], ["/a b"],
                    [f"/p{k}" for k in range(21)], 7):
            config = {"site": {"script_posts": raw + ["/landing/ping"]
                               if isinstance(raw, list) else raw}}
            with self.subTest(raw=str(raw)[:30]):
                self.assertEqual(both(post(NOON, "203.0.113.38", "/landing/ping", 200, "9"),
                                      config), (True, True))

    def test_the_setting_is_checked_in_plain_words(self):
        v = settings_store.validate
        self.assertEqual(v("site.script_posts", "/a /b/* /a"), ["/a", "/b/*"])
        for bad in (["/"], ["/*"], ["a"], ["/a?b"], ["/a*b"], ["/../x"],
                    [f"/p{k}" for k in range(21)]):
            with self.subTest(bad=str(bad)[:30]), self.assertRaises(settings_store.Invalid):
                v("site.script_posts", bad)
        self.assertEqual(settings_store.SCHEMA["site.script_posts"].config,
                         ("site", "script_posts"))


class TestSuggestions(unittest.TestCase):
    """A path sent (2xx) by half the visits that sent a POST and a fifth of
    all visits, on 3 of the last 14 stored days."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.executescript(
            "CREATE TABLE days (site TEXT, day TEXT, verified INTEGER);"
            "CREATE TABLE counts (site TEXT, day TEXT, kind TEXT, name TEXT, n INTEGER);")

    def day(self, d: date, visits: int, posting: int, paths: dict, verified: int = 1):
        self.db.execute("INSERT INTO days VALUES ('example.com', ?, ?)", (d.isoformat(), verified))
        rows = [("visit_pages", "1", visits), ("visit_flag", "posted", posting)]
        rows += [("visit_post", p, n) for p, n in paths.items()]
        self.db.executemany("INSERT INTO counts VALUES ('example.com', ?, ?, ?, ?)",
                            [(d.isoformat(), *r) for r in rows])

    def test_three_days_make_a_suggestion(self):
        for i, (visits, posting, n) in enumerate(((34, 29, 29), (28, 18, 18), (30, 20, 10))):
            self.day(DAY - timedelta(days=i), visits, posting, {"/api/beat": n, "/contact": 1})
        got = form_names.suggest(self.db, "example.com", DAY)
        self.assertEqual([g["path"] for g in got], ["/api/beat"])
        self.assertEqual({k: got[0][k] for k in ("days", "visits", "of_posting", "of_all", "day")},
                         {"days": 3, "visits": 29, "of_posting": 29, "of_all": 34,
                          "day": DAY.isoformat()})

    def test_two_days_are_not_enough(self):
        for i in range(2):
            self.day(DAY - timedelta(days=i), 30, 20, {"/api/beat": 20})
        self.day(DAY - timedelta(days=2), 30, 20, {"/api/beat": 9})     # under half
        self.assertEqual(form_names.suggest(self.db, "example.com", DAY), [])

    def test_a_sites_only_form_is_not_most_page_views(self):
        # Every visit that posted sent /contact, but 3 of 100 visits: under a fifth.
        for i in range(5):
            self.day(DAY - timedelta(days=i), 100, 3, {"/contact": 3})
        self.assertEqual(form_names.suggest(self.db, "example.com", DAY), [])

    def test_older_withheld_and_listed_days_do_not_count(self):
        for i in range(3):
            self.day(DAY - timedelta(days=20 + i), 30, 20, {"/api/beat": 20})
        self.day(DAY, 30, 20, {"/api/beat": 20}, verified=0)
        self.assertEqual(form_names.suggest(self.db, "example.com", DAY), [])
        for i in range(1, 4):
            self.day(DAY - timedelta(days=i), 30, 20, {"/api/beat": 20})
        self.assertEqual(len(form_names.suggest(self.db, "example.com", DAY)), 1)
        self.assertEqual(form_names.suggest(self.db, "example.com", DAY, ["/api/*"]), [])

    def test_the_same_rows_give_the_same_answer(self):
        for i in range(4):
            self.day(DAY - timedelta(days=i), 30, 20, {"/b": 20, "/a": 20})
        first = form_names.suggest(self.db, "example.com", DAY)
        self.assertEqual([g["path"] for g in first], ["/a", "/b"])
        self.assertEqual(first, form_names.suggest(self.db, "example.com", DAY))


class TestTheAuditSharesOnlyTheLists(unittest.TestCase):

    def test_audit_visits_imports_only_form_names_lists(self):
        tree = ast.parse(Path(audit_visits.__file__).read_text())
        got = {(n.module, a.name) for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(got, {("form_names", "BEACON_STATUS"), ("form_names", "ENTRY_LIMIT"),
                               ("form_names", "MAX_OWN"), ("form_names", "REFUSED"),
                               ("form_names", "SCRIPT_POSTS")})


def site_day(sandbox_lines_at=NOON) -> list[str]:
    """Four people visits: two with the event script only, one that also sent a
    real form (303), one with the site's own ping; a bot's POST."""
    out = []
    for i, addr in enumerate(("203.0.113.40", "203.0.113.41", "203.0.113.42")):
        at = sandbox_lines_at + timedelta(minutes=5 * i)
        out += [line(at, addr, PAGE, referrer="https://www.google.com/"),
                post(at + timedelta(seconds=4), addr, "/api/events")]
    at = sandbox_lines_at + timedelta(minutes=20)
    out += [post(at, "203.0.113.42", "/contact", 303, "0", "https://example.com/contact")]
    at = sandbox_lines_at + timedelta(minutes=30)
    out += [line(at, "203.0.113.43", "/pricing"),
            post(at + timedelta(seconds=2), "203.0.113.43", "/landing/ping", 200, "2",
                 "https://example.com/pricing"),
            # Refused (rule 3): a POST to an address that takes none.
            post(at + timedelta(seconds=9), "203.0.113.43", "/graphql", 405, "162",
                 "https://example.com/pricing")]
    return sorted(out)


class TestCollectAuditAndRecount(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        text = self.box.config.read_text()
        self.box.config.write_text(text.replace(
            "  require_rendering: false\n",
            "  require_rendering: false\n  script_posts: [/landing/ping]\n", 1))
        self.box.log(site_day())

    def tearDown(self):
        self.box.close()

    def rows(self, kind: str) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return dict(db.execute("SELECT name, n FROM counts WHERE site = 'example.com' "
                                   "AND day = ? AND kind = ?", (DAY.isoformat(), kind)))
        finally:
            db.close()

    def journeys(self) -> list[dict]:
        db = sqlite3.connect(str(self.box.db))
        try:
            return [json.loads(d) for (d,) in db.execute(
                "SELECT data FROM journeys WHERE day = ? ORDER BY seq", (DAY.isoformat(),))]
        finally:
            db.close()

    def test_stored_figures_and_the_audit_agree(self):
        code, out, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err + out)
        self.assertEqual(self.rows("visit_flag").get("posted"), 1)
        # The real form only, in Form posts; a 303 is no 2xx, so no path for the suggestions.
        self.assertEqual(self.rows("post_total"), {"people": 1})
        self.assertEqual(self.rows("post_page_people"), {"/contact": 1})
        self.assertEqual(self.rows("visit_post"), {})
        self.assertEqual(self.rows("visit_rule"), {"forms": form_names.FORMS_RULE})
        self.assertEqual(sorted(j["posted"] for j in self.journeys()), [0, 0, 0, 1])
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_an_audit_of_a_day_whose_log_is_gone_leaves_it_alone(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        empty = self.box.root / "gone.log"
        empty.write_text("")
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat(),
                                      "--log", str(empty), "--withhold")
        self.assertEqual(code, 2, err + out)
        self.assertIn("no log lines", err)
        self.assertNotIn("withheld", err + out)
        db = sqlite3.connect(str(self.box.db))
        try:
            self.assertEqual(db.execute("SELECT verified, coalesce(problems, '') FROM days "
                                        "WHERE day = ?", (DAY.isoformat(),)).fetchone(), (1, ""))
        finally:
            db.close()

    def test_the_audit_sees_a_wrong_posted_figure(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE counts SET n = 4 WHERE kind = 'visit_flag' AND name = 'posted'")
        db.close()
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("posted", err + out)

    def test_backfill_force_rebuilds_a_day_stored_before_the_rule(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        # The day as the old rule stored it: every POST but Skald's own a form.
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE counts SET n = 4 WHERE kind = 'visit_flag' AND name = 'posted'")
            db.execute("DELETE FROM counts WHERE kind IN ('visit_rule', 'visit_post')")
            db.execute("UPDATE counts SET n = 5 WHERE kind = 'post_total' AND name = 'people'")
            for seq, data in db.execute("SELECT seq, data FROM journeys").fetchall():
                j = json.loads(data)
                j.update(posted=1)
                j.pop("forms", None)
                db.execute("UPDATE journeys SET data = ? WHERE seq = ?", (json.dumps(j), seq))
        db.close()
        from skald import dashboard_webapp, store_visits
        from skald.store import History
        h = History(self.box.db)
        try:
            self.assertEqual(store_visits.forms_old_days(h.db, "example.com", DAY, DAY),
                             [DAY.isoformat()])
            got = dashboard_webapp.build(h, "example.com", "example.com", UTC,
                                         datetime(2026, 10, 25, 9, tzinfo=UTC), None)
        finally:
            h.close()
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day.get("forms_old"), 1, "the page says the day is counted the old way")
        self.assertTrue(all("posted_old" in j["flags"] and "posted" not in j["flags"]
                            for j in got["journeys"]))
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1, "the old count does not match the raw log")
        # The recount.
        code, out, err = self.box.run("--today", TODAY, "backfill", "--days", "1", "--force")
        self.assertEqual(code, 0, err + out)
        self.assertEqual(self.rows("visit_flag").get("posted"), 1)
        self.assertEqual(self.rows("visit_rule"), {"forms": form_names.FORMS_RULE})
        self.assertEqual(self.rows("post_total"), {"people": 1})
        self.assertEqual(sorted(j["posted"] for j in self.journeys()), [0, 0, 0, 1])
        self.assertTrue(all(j.get("forms") == form_names.FORMS_RULE for j in self.journeys()))
        h = History(self.box.db)
        try:
            self.assertEqual(store_visits.forms_old_days(h.db, "example.com", DAY, DAY), [])
        finally:
            h.close()
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_the_doctor_names_old_days_until_recounted(self):
        from skald import doctor
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        now = datetime(2026, 10, 25, 9, tzinfo=UTC)
        got = doctor.form_posts({}, self.box.db, "example.com", UTC, now, "skald")
        self.assertEqual(got["state"], doctor.OK, got)
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("DELETE FROM counts WHERE kind = 'visit_rule'")
        db.close()
        got = doctor.form_posts({}, self.box.db, "example.com", UTC, now, "skald")
        self.assertEqual(got["state"], doctor.ATTENTION)
        self.assertIn(DAY.isoformat(), got["says"])
        self.assertIn("backfill --days 1 --force", got["fix"])


class TestTheDoctorNamesASuggestionOnce(unittest.TestCase):

    def test_one_line_with_the_path_and_its_figures(self):
        from skald import doctor
        box = Sandbox()
        try:
            # Three days: each page view sends POST /api/beat (200: not the 204 rule).
            lines = []
            for k in range(3):
                noon = NOON - timedelta(days=k)
                for i in range(4):
                    at, addr = noon + timedelta(minutes=5 * i), f"203.0.113.{50 + i}"
                    lines += [line(at, addr, PAGE),
                              post(at + timedelta(seconds=4), addr, "/api/beat", 200, "2")]
            box.log(sorted(lines))
            code, out, err = box.run("--today", TODAY, "backfill", "--days", "3")
            self.assertEqual(code, 0, err + out)
            now = datetime(2026, 10, 25, 9, tzinfo=UTC)
            got = doctor.form_posts({}, box.db, "example.com", UTC, now, "skald")
            self.assertEqual(got["state"], doctor.ATTENTION)
            self.assertEqual(got["says"].count("POST /api/beat"), 1)
            self.assertIn("4 of the 4 visits that sent a POST", got["says"])
            self.assertIn("Settings > Data > What counts > Not forms", got["fix"])
            config = {"site": {"script_posts": ["/api/beat"]}}
            self.assertEqual(doctor.form_posts(config, box.db, "example.com", UTC, now,
                                               "skald")["state"], doctor.OK)
        finally:
            box.close()


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestTheSettingsCard(unittest.TestCase):

    def test_add_a_suggestion_and_remove_a_saved_one(self):
        js = Path(__file__).resolve().parent / "js" / "not-forms.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=120,
                              env=dict(os.environ))
        self.assertEqual(done.returncode, 0, done.stderr[-4000:] + done.stdout[-2000:])
        self.assertIn("not-forms: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
