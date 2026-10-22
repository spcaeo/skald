"""Settings > Sites > Views: filling a new page group's past days from the raw
log (views_fill.py, views_fill_api.py, cli_views.py, audit_views.py).

  * a save of sites.views answers which groups it added, changed or removed;
  * the fill recounts only the whole days the raw log still holds, the views
    only (the site's own days are left as they are), and says its progress;
  * each filled day is recounted by the audit's own road and agrees; a day
    that does not is withheld;
  * one fill at a time per install; owners and admins only, same-origin and
    CSRF, written to the audit log;
  * the page offers the fill, starts it by default and shows its progress
    (tests/js/views-fill.mjs, with mocked answers).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_views, views_fill, views_fill_api  # noqa: E402
from skald.config import load_config, setting  # noqa: E402
from skald.store import History, view_key  # noqa: E402

from auth_support import A, B, Server  # noqa: E402
from support import Sandbox, config_text, day_lines, line  # noqa: E402
from test_views import DAY, VIEWS, mixed_day  # noqa: E402

UTC = timezone.utc
SITE = "example.com"
KEYS = ["us-english", "canada-english", "canada-french"]
FIRST = date(2026, 10, 1)


def days_of(first: date, n: int, people: int = 3, midnight: bool = True) -> list[str]:
    """`n` days of traffic from `first`, each with a line just after midnight
    (so each day is whole) and the mixed paths of test_views."""
    out = []
    for i in range(n):
        d = first + timedelta(days=i)
        if midnight:
            out.append(line(datetime(d.year, d.month, d.day, 0, 0, 5, tzinfo=UTC),
                            "203.0.113.99", "/ca/fr/"))
        out += [x.replace(DAY.isoformat(), d.isoformat()) for x in mixed_day()]
        out += day_lines(d, people)
    return out


class Changes(unittest.TestCase):

    def test_added_changed_renamed_and_removed(self):
        old = [{"name": "Blog", "path_prefix": "/blog/"},
               {"name": "Docs", "path_prefix": "/docs/", "exclude_prefix": "/docs/old/"},
               {"name": "Shop", "path_prefix": "/shop/"}]
        new = [{"name": "Blog", "path_prefix": "/blog/"},                      # same
               {"name": "Docs", "path_prefix": "/docs/", "exclude_prefix": "/docs/v1/"},
               {"name": "Store", "path_prefix": "/shop/"},                    # renamed
               {"name": "Security pages", "path_prefix": "/security/"}]
        added, gone = views_fill.changed(old, new)
        self.assertEqual([v["slug"] for v in added], ["docs", "store", "security-pages"])
        self.assertEqual(gone, [{"slug": "shop", "name": "Shop"}])
        self.assertEqual(views_fill.changed(new, new), ([], []))
        self.assertEqual(views_fill.changed(None, []), ([], []))
        # The same rule written with its exclusions in another order is no change.
        a = [{"name": "X", "exclude_prefix": "/a/ /b/"}]
        self.assertEqual(views_fill.changed(a, [{"name": "X", "exclude_prefix": "/b/  /a/"}]),
                         ([], []))


class Reach(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.now = datetime(2026, 10, 7, 12, tzinfo=UTC)

    def reach(self, gap=60):
        cfg = load_config(self.box.config)
        cfg["report"]["coverage_gap_minutes"] = gap
        return views_fill.reach(cfg, UTC, self.now)

    def test_whole_days_from_the_oldest_line_to_yesterday(self):
        self.box.log(days_of(FIRST, 6))
        got = self.reach()
        self.assertEqual((got["days"], got["first"], got["last"]), (6, "2026-10-01", "2026-10-06"))
        self.assertEqual(got["kept_days"], 7)

    def test_a_first_day_the_log_starts_late_in_is_not_whole(self):
        self.box.log(days_of(FIRST, 6, midnight=False))        # first line at 09:00
        got = self.reach()
        self.assertEqual((got["days"], got["first"]), (5, "2026-10-02"))

    def test_the_oldest_rotation_decides(self):
        self.box.log(days_of(FIRST + timedelta(days=3), 3), "access.log")
        self.box.log(days_of(FIRST + timedelta(days=1), 2), "access.log.1")
        self.box.log(days_of(FIRST, 1), "access.log.2.gz")
        self.assertEqual(self.reach()["first"], "2026-10-01")

    def test_no_log_is_no_day(self):
        got = self.reach()
        self.assertEqual((got["days"], got["first"], got["kept_days"]), (0, None, 0))


class Job(unittest.TestCase):
    """`skald views refresh` on a sandbox: history of the site from a log that
    has since lost its oldest days, then views added."""

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        # Six days collected while the log held them all...
        self.box.log(days_of(FIRST, 6))
        code, _, err = self.run_("backfill", "--days", "6")
        self.assertEqual(code, 0, err)
        # ...then the log rotated: only 4 Oct onwards is left.
        self.box.log(days_of(FIRST + timedelta(days=3), 3))
        self.box.config.write_text(config_text(self.box.root, views=VIEWS))

    def run_(self, *argv):
        return self.box.run("--today", "2026-10-07", *argv)

    def rows(self):
        with History(self.box.db) as h:
            return {(s, d): (v, c) for s, d, v, c in h.db.execute(
                "SELECT site, day, verified, collected_at FROM days")}

    def test_it_fills_only_the_days_the_raw_log_holds(self):
        before = {k: v for k, v in self.rows().items() if k[0] == SITE}
        code, out, err = self.run_("views", "refresh")
        self.assertEqual(code, 0, err)
        self.assertIn("the raw log holds 3 whole day(s), 2026-10-04 to 2026-10-06", out)
        self.assertIn("views refresh: 3 filled and audited, 0 withheld", out)
        rows = self.rows()
        for key in KEYS:
            got = sorted(d for s, d in rows if s == view_key(SITE, key))
            self.assertEqual(got, ["2026-10-04", "2026-10-05", "2026-10-06"], key)
            self.assertTrue(all(rows[(view_key(SITE, key), d)][0] == 1 for d in got))
        # The site's own days are left exactly as they were.
        self.assertEqual({k: v for k, v in rows.items() if k[0] == SITE}, before)
        state = json.loads((self.box.root / views_fill.STATE).read_text())
        self.assertEqual({k: state[k] for k in ("state", "days", "done", "filled", "withheld",
                                                "empty", "first", "last", "before", "by")},
                         {"state": "done", "days": 3, "done": 3, "filled": 3, "withheld": 0,
                          "empty": 0, "first": "2026-10-04", "last": "2026-10-06",
                          "before": "2026-10-04", "by": "cli"})
        # The page's data: the view's days before 4 Oct are "before" (not recorded), never 0.
        over = json.loads((self.box.root / "www" / SITE / "canada-french" / "data"
                           / "overview.json").read_text())
        states = {d["day"]: d["state"] for d in over["days"]}
        self.assertEqual(states["2026-10-03"], "before")
        self.assertNotIn("groups", next(d for d in over["days"] if d["day"] == "2026-10-03"))
        self.assertEqual(states["2026-10-04"], "ok")

    def test_one_view_and_n_days_from_the_shell(self):
        code, out, err = self.run_("views", "refresh", "--days", "2", "--view", "canada-french")
        self.assertEqual(code, 0, err)
        sites = {s for s, _ in self.rows()}
        self.assertIn(view_key(SITE, "canada-french"), sites)
        self.assertNotIn(view_key(SITE, "us-english"), sites)
        self.assertEqual(self.run_("views", "refresh", "--view", "nope")[0], 2)
        code, out, _ = self.run_("views", "list")
        self.assertIn("canada-french\tCanada French\tpaths under /ca/fr/\tfrom 2026-10-05", out)

    def test_the_audits_road_agrees_with_what_was_stored(self):
        self.assertEqual(self.run_("views", "refresh")[0], 0)
        cfg = load_config(self.box.config)
        for d in ("2026-10-04", "2026-10-05", "2026-10-06"):
            figures = audit_views.recount(cfg, date.fromisoformat(d), UTC,
                                          setting(cfg, "dashboard", "views"))
            self.assertEqual(figures["canada-english"]["groups"]["answer_engines"], 1)
            with History(self.box.db) as h:
                self.assertEqual(audit_views.compare(figures, h, SITE, date.fromisoformat(d)),
                                 {k: [] for k in KEYS})

    def test_a_day_the_audit_does_not_match_is_withheld(self):
        real = audit_views.recount

        def off_by_one(*a, **k):
            got = real(*a, **k)
            got["canada-french"]["requests"] += 1
            return got
        with mock.patch.object(audit_views, "recount", off_by_one):
            code, out, err = self.run_("views", "refresh", "--days", "1")
        self.assertEqual(code, 1)
        self.assertIn("withheld: 2026-10-06: Canada French: requests: history has", err)
        with History(self.box.db) as h:
            self.assertIs(h.status(view_key(SITE, "canada-french"), date(2026, 10, 6)), False)
            self.assertIs(h.status(view_key(SITE, "canada-english"), date(2026, 10, 6)), True)
        state = json.loads((self.box.root / views_fill.STATE).read_text())
        self.assertEqual((state["filled"], state["withheld"]), (0, 1))

    def test_progress_is_written_day_by_day(self):
        seen = []
        real = views_fill.save

        def spy(folder, fresh=False, **fields):
            got = real(folder, fresh, **fields)
            seen.append((got.get("state"), got.get("done"), got.get("current")))
            return got
        with mock.patch.object(views_fill, "save", spy):
            self.assertEqual(self.run_("views", "refresh")[0], 0)
        self.assertEqual(seen[0], ("running", 0, None))
        self.assertIn(("running", 0, "2026-10-04"), seen)
        self.assertIn(("running", 1, "2026-10-04"), seen)
        self.assertIn(("running", 2, "2026-10-05"), seen)
        self.assertEqual(seen[-1], ("done", 3, None))

    def test_one_fill_at_a_time(self):
        with views_fill.lock(self.box.root):
            code, _, err = self.run_("views", "refresh")
        self.assertEqual(code, 3)
        self.assertIn("another fill is running", err)
        self.assertFalse((self.box.root / views_fill.STATE).exists())


class States(unittest.TestCase):

    def test_a_job_that_vanished_reads_as_failed_and_a_new_one_as_queued(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            now = datetime(2026, 10, 7, 12, tzinfo=UTC)
            views_fill.save(tmp, state="queued", asked_at=(now - timedelta(seconds=30))
                            .isoformat())
            self.assertEqual(views_fill_api.current(Path(tmp), now)["state"], "queued")
            self.assertEqual(views_fill_api.current(Path(tmp), now + timedelta(minutes=5))
                             ["state"], "failed")
            views_fill.save(tmp, state="running", started_at=now.isoformat())
            self.assertEqual(views_fill_api.current(Path(tmp), now)["state"], "failed")
            with views_fill.lock(tmp):          # the job holds its lock: running
                self.assertEqual(views_fill_api.current(Path(tmp), now)["state"], "running")


T = f"/traffic/{A}/"


class Api(Server):

    def setUp(self):
        super().setUp()
        logs = self.live.parent / "logs"
        logs.mkdir()
        today = datetime.now(UTC).date()
        (logs / "access.log").write_text("".join(days_of(today - timedelta(days=9), 10)))
        self.config["logs"] = {"dir": str(logs), "base": "access.log"}
        self.spawned = []
        patch = mock.patch.object(views_fill_api, "spawn",
                                  lambda c, args, log: self.spawned.append((c.site, args)))
        patch.start()
        self.addCleanup(patch.stop)

    def save(self, views, who="owner@example.com"):
        cookie, csrf = self.session(who)
        return self.post(T + "settings/save", {"sites.views": views}, cookie, csrf)

    def test_the_save_answer_names_the_changed_views(self):
        got = self.save([{"name": "Security pages", "path_prefix": "/security/"},
                         {"name": "Free check", "path_prefix": "/check/"}])
        self.assertEqual(got.status, 200, got.json)
        v = got.json["views"]
        self.assertEqual([x["slug"] for x in v["changed"]], ["security-pages", "free-check"])
        self.assertEqual(v["removed"], [])
        self.assertTrue(v["can_fill"])
        self.assertEqual(v["reach"]["days"], 9)
        self.assertEqual(v["reach"]["kept_days"], 10)
        self.assertIsNone(v["fill"])
        got = self.save([{"name": "Security pages", "path_prefix": "/security/"}],
                        "admin@example.com")
        self.assertEqual(got.json["views"]["changed"], [])
        self.assertEqual(got.json["views"]["removed"], [{"slug": "free-check",
                                                        "name": "Free check"}])
        # A save of anything else says nothing about views.
        cookie, csrf = self.session()
        got = self.post(T + "settings/save", {"sites.timezone": "Europe/London"}, cookie, csrf)
        self.assertNotIn("views", got.json)

    def test_an_admin_starts_it_in_the_background_once(self):
        self.save([{"name": "Security pages", "path_prefix": "/security/"}])
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "settings/views-fill-start", {"views": ["security-pages"]},
                        cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["fill"]["state"], "queued")
        self.assertEqual(got.json["fill"]["days"], 9)
        self.assertEqual(self.spawned, [(A, ["views", "refresh", "--days", "9", "--by",
                                             "admin@example.com", "--view", "security-pages"])])
        # One at a time: a second press while it is queued is refused.
        again = self.post(T + "settings/views-fill-start", {}, cookie, csrf)
        self.assertEqual(again.status, 409)
        self.assertEqual(len(self.spawned), 1)
        # The audit log has who started it, for which days and groups.
        db = self.db()
        try:
            row = db.execute("SELECT actor, target, detail FROM audit WHERE action = "
                             "'views.fill'").fetchone()
        finally:
            db.close()
        self.assertEqual(row["target"], A)
        self.assertIn("9 days", row["detail"])
        self.assertIn("Security pages", row["detail"])
        # Its progress, for this site in full...
        status = self.call("GET", T + "settings/views-fill", cookie=cookie)
        self.assertEqual(status.status, 200, status.json)
        self.assertEqual(status.json["fill"]["site"], A)
        self.assertEqual(status.json["reach"]["days"], 9)
        # ...and for another organisation's site only "busy", never the name.
        bob, _ = self.session("bob@example.com")
        other = self.call("GET", f"/traffic/{B}/settings/views-fill", cookie=bob)
        self.assertEqual(other.json["fill"], {"state": "busy"})

    def test_roles_and_csrf(self):
        self.save([{"name": "Security pages", "path_prefix": "/security/"}])
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(T + "settings/views-fill-start", {}, cookie, csrf).status, 403)
        self.assertEqual(self.call("GET", T + "settings/views-fill", cookie=cookie).status, 403)
        cookie, csrf = self.session("owner@example.com")
        self.assertEqual(self.post(T + "settings/views-fill-start", {}, cookie, "wrong").status,
                         403)
        self.assertEqual(self.call("POST", T + "settings/views-fill-start", {},
                                   cookie=cookie, csrf=csrf).status, 403)   # no same-origin
        self.assertEqual(self.call("GET", T + "settings/views-fill-start", cookie=cookie,
                                   csrf=csrf).status, 405)
        bob, bcsrf = self.session("bob@example.com")
        self.assertEqual(self.post(T + "settings/views-fill-start", {}, bob, bcsrf).status, 403)
        self.assertEqual(self.spawned, [])
        got = self.post(T + "settings/views-fill-start", {"views": ["nope"]}, cookie, csrf)
        self.assertEqual(got.status, 400)
        got = self.post(T + "settings/views-fill-start", {}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.spawned[0][1][-2:], ["--view", "security-pages"])

    def test_nothing_to_fill_without_a_whole_day(self):
        self.config["logs"]["dir"] = str(self.live.parent / "nowhere")
        got = self.save([{"name": "Security pages", "path_prefix": "/security/"}])
        self.assertEqual(got.json["views"]["reach"]["days"], 0)
        cookie, csrf = self.session()
        got = self.post(T + "settings/views-fill-start", {}, cookie, csrf)
        self.assertEqual(got.status, 409)
        self.assertIn("nothing to fill", got.json["error"])
        self.assertEqual(self.spawned, [])


class Page(unittest.TestCase):

    def test_the_page_offers_the_fill_and_shows_its_progress(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        js = Path(__file__).resolve().parent / "js" / "views-fill.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ))
        self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
        self.assertIn("views-fill: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
