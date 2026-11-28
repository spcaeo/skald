"""SKALD-59: harmless answers are no "possible exposure", and a checked one can be closed.

The 25 Nov 2026 daily mail listed about 240 possible exposures on six WordPress sites; almost
all were public images, theme CSS/JS, WordPress's own cron and a home page served for a .php
name. Exposure rule 3 calls those harmless on both counts (security.py, audit_security.py), and
an owner or admin marks a checked one "Not a problem" (security_marks.py): no item, mail or
site alert while the answer stays the same; a changed answer, or "Check it again", ends it.
Documentation addresses and example.com hosts only."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import accounts, alerts_security, security_api, security_marks as sm  # noqa: E402
from skald import site_data  # noqa: E402
from skald import security_names as N, security_notify as sn  # noqa: E402
from skald.accounts import auditlog, orgs, sessions, users  # noqa: E402

from security_support import box, ln, put, stored  # noqa: E402
from test_security_notify import CONFIG, Fake  # noqa: E402

UTC = timezone.utc
T = datetime(2026, 10, 5, 9, tzinfo=UTC)
BOT = "Mozilla/5.0 (compatible; Examplebot/1.0; +https://bot.example.net/)"
SITE = "example.com"


def day() -> list[str]:
    out = [ln(T, "203.0.113.5", "/", size=59_472),                     # the home page, twice
           ln(T + timedelta(hours=2), "203.0.113.6", "/", size=59_510)]
    at = iter(T + timedelta(minutes=5, seconds=i) for i in range(100))
    probe = lambda path, size, agent=BOT, status=200, method="GET": out.append(  # noqa: E731
        ln(next(at), "198.51.100.20", path, agent, status, size, method=method))
    probe("/wp-content/uploads/2026/02/Copper.svg", 842)                       # static
    probe("/wp-content/themes/child/style.css", 3_000)                         # static
    probe("/wp-content/uploads/2025/09/Terraform.svg", 455)                    # static (cloud word)
    for name in ("a", "b", "c"):                                               # static, and
        probe(f"/wp-content/uploads/{name}.png", 5_000)                        # never a shell
    probe("/wp-content/debug.log", 5_000)                                      # possible
    probe("/env.js", 300)                                                      # secrets: possible
    probe("/wp-cron.php?doing_wp_cron=1", 31, "WordPress/6.9; https://wp.example.com",
          method="POST")                                                       # own
    probe("/wp-cron.php", 31, "WordPress/6.9; https://shop.example.net")       # possible
    probe("/index.php", 59_567)                                                # home
    probe("/backup-index.php", 70_000)                                         # possible
    # The review's holes (all must stay possible): a script run through PATH_INFO, a secret
    # file, a server build file, the cron's path elsewhere or without its POST, and a dump or
    # log the size of a search page (a search page echoes the query, so its size is chosen).
    for i, path in enumerate(("/phpinfo.php/x.css", "/wp-config.php/a.js",
                              "/_next/server/app/page.js", "/.github/workflows/x.js")):
        probe(path, 7_000 + 500 * i)              # sizes of their own: no fallback size
    probe("/wp-content/uploads/wp-cron.php", 400, "WordPress/6.9; https://wp.example.com",
          method="POST")
    probe("/wp-cron.php", 800, "WordPress/6.9; https://wp.example.com")
    for i in range(40):                                                        # /?s= pages
        out.append(ln(T + timedelta(hours=3, seconds=i), "203.0.113.7", f"/?s=term{i}",
                      size=30_000 + 2_000 * i))
    probe("/backup.sql", 45_123)
    probe("/wp-content/debug.log", 88_000)
    # The second review's: an encoded slash, a double extension, a cloud word outside
    # WordPress's folders, the cron under wp-content, a dump the size of the home page.
    for i, path in enumerate(("/wp-content/plugins/x/info.php%2fa.css",
                              "/wp-content/uploads/shell.php.png", "/phpmyadmin/js/helmet.js")):
        probe(path, 11_000 + 700 * i)
    probe("/wp-content/wp-cron.php", 1_200, "WordPress/6.9; https://wp.example.com", method="POST")
    probe("/wp-content/backup-db.sql", 59_480)
    return sorted(out)


class HarmlessAnswers(unittest.TestCase):
    def setUp(self):
        self.box = box(day())
        code, _, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        self.box.close()

    def test_static_own_and_home_are_harmless_and_the_rest_stays_possible(self):
        b = stored(self.box)
        e = b["exposure"]
        self.assertEqual(b["rules"]["exposure_rule"], 3)
        self.assertEqual((e["static"], e["own"], e["home"]), (6, 1, 1))
        self.assertEqual(sorted({r["path"] for r in e["rows"]}),
                         ["/.github/workflows/x.js", "/_next/server/app/page.js", "/backup-index.php",
                          "/backup.sql", "/env.js", "/phpinfo.php/x.css", "/phpmyadmin/js/helmet.js",
                          "/wp-config.php/a.js", "/wp-content/backup-db.sql", "/wp-content/debug.log",
                          "/wp-content/plugins/x/info.php%2fa.css", "/wp-content/uploads/shell.php.png",
                          "/wp-content/uploads/wp-cron.php", "/wp-content/wp-cron.php", "/wp-cron.php"],
                         "a log, secrets, a foreign or misplaced cron call, an odd .php, a script "
                         "behind a static name and a search-page-sized dump all stay possible")
        self.assertEqual(e["hosts"]["example.com"]["shell_sizes"], [],
                         "three images of one size never make a fallback page")
        self.assertEqual(sum(e[v] for v in N.VERDICTS), e["answered"])

    def test_both_roads_agree_and_a_changed_verdict_is_caught(self):
        code, _, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err)
        b = stored(self.box)
        b["exposure"]["static"] -= 1
        b["exposure"]["possible"] += 1
        put(self.box, b)
        code, _, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("exposure", err)


def blob(size=184, status="200", rule=3):
    return {"rules": {"exposure_rule": rule, "tolerance": 16}, "exposure": {"rows": [
        {"host": "www.example.com", "path": "/wp-links-opml.php", "status": status, "size": size,
         "at": "2026-11-25T05:22:00+00:00", "verdict": "possible", "category": "wordpress",
         "shell_size": None}]}}


ITEM = sn.item_id("exposure", SITE, "www.example.com", "/wp-links-opml.php")


class Marks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = accounts.connect(self.dir / "accounts.sqlite")
        org = orgs.create_org(self.db, "Example", "test")
        self.org = org["id"]
        orgs.assign_site(self.db, SITE, self.org, "test")
        self.cookies, self.ids = {}, {}
        for email, role in (("admin@example.com", "admin"), ("viewer@example.com", "viewer")):
            u = users.create_user(self.db, email, "x", password="pw-long-enough-1", actor="test")
            users.add_member(self.db, self.org, u["id"], role, "test")
            self.cookies[role] = sessions.start(self.db, u["id"], "", "test")
            self.ids[role] = u["id"]
        self.now = datetime(2026, 11, 26, 6, tzinfo=UTC)
        sn.track(self.db, SITE, sn.items(CONFIG, SITE, [blob()], None), self.now)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def open_items(self):
        return [it["item"] for it in sn.open_items(self.db, SITE)]

    def ask(self, role, body=None, act="security-mark"):
        cookie, csrf = self.cookies[role]
        h = Fake(f"/traffic/{SITE}/settings/{act}", cookie, csrf, body)
        security_api.handle(h, body is not None, CONFIG, self.dir, [], lambda *_: True)
        self.db.close()
        self.db = accounts.connect(self.dir / "accounts.sqlite")
        return h.sent

    def test_a_mark_closes_the_item_until_the_answer_changes(self):
        self.assertEqual(self.open_items(), [ITEM])
        sm.mark(self.db, SITE, ITEM, "200", 184, self.ids["admin"], self.org, "admin@example.com",
                self.now)
        self.assertEqual(self.open_items(), [], "closed at once, not at the next run")
        for size in (184, 190, 200):              # within the day's tolerance of 16 bytes
            found = sn.items(CONFIG, SITE, [blob(size)], None, sm.of_site(self.db, SITE))
            self.assertEqual(found, [], f"{size} bytes: still the answer that was checked")
        marks = sm.of_site(self.db, SITE)
        self.assertEqual([it["item"] for it in sn.items(CONFIG, SITE, [blob(2_176)], None, marks)],
                         [ITEM], "the file changed: judged again")
        self.assertEqual([it["item"] for it in sn.items(CONFIG, SITE, [blob(184, "206")], None,
                                                        marks)], [ITEM], "another status too")
        self.assertEqual(marks[ITEM][0]["by"], "admin@example.com")
        sm.unmark(self.db, SITE, ITEM, self.org, "admin@example.com")
        self.assertEqual(len(sn.items(CONFIG, SITE, [blob()], None, sm.of_site(self.db, SITE))), 1,
                         "Check it again: the next run opens it")
        actions = [r["action"] for r in auditlog.recent(self.db, self.org)]
        self.assertIn("security.item.not_a_problem", actions)
        self.assertIn("security.item.check_again", actions)

    def test_one_path_two_answers_each_marked_on_its_own(self):
        both = {"rules": {"exposure_rule": 3, "tolerance": 16}, "exposure": {"rows": [
            {**blob()["exposure"]["rows"][0]}, {**blob(626)["exposure"]["rows"][0]}]}}
        sm.mark(self.db, SITE, ITEM, "200", 184, self.ids["admin"], self.org, "admin@example.com")
        self.assertEqual(len(sn.items(CONFIG, SITE, [both], None, sm.of_site(self.db, SITE))), 1,
                         "the uncompressed answer was never checked")
        sm.mark(self.db, SITE, ITEM, "200", 626, self.ids["admin"], self.org, "admin@example.com")
        self.assertEqual(sn.items(CONFIG, SITE, [both], None, sm.of_site(self.db, SITE)), [])
        self.assertEqual(len(sm.of_site(self.db, SITE)[ITEM]), 2)
        sm.unmark(self.db, SITE, ITEM, self.org, "admin@example.com")
        self.assertEqual(sm.of_site(self.db, SITE), {}, "Check it again takes back both")

    def test_the_runs_read_the_marks_from_the_accounts_file(self):
        """The live run (security_notify.live) and the site alert (alerts_security.findings)
        find the marks themselves; a wiring slip would only show as alerts on marked items."""
        class History:
            class db:                              # noqa: N801 - no stored day yet
                @staticmethod
                def execute(*a):
                    return type("R", (), {"fetchone": staticmethod(lambda: None)})()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        ctx = type("Ctx", (), {"config": CONFIG, "live_dir": self.dir, "site": SITE,
                               "now": self.now, "tz": UTC, "history": lambda self: History(),
                               "err": lambda self, m: self.errors.append(m), "errors": []})()
        snap = {"state": "ok", "extras": {"security": blob()}}
        sm.mark(self.db, SITE, ITEM, "200", 184, self.ids["admin"], self.org, "admin@example.com")
        sn.live(ctx, snap)
        self.assertEqual(ctx.errors, [])
        self.db.close()
        self.db = accounts.connect(self.dir / "accounts.sqlite")
        self.assertEqual(self.open_items(), [], "the live run did not open it again")
        found = alerts_security.findings({}, {**CONFIG, "alerts": {"security_exposure": True}},
                                         snap, History(), SITE, self.now.date(), self.dir)
        self.assertEqual([f for f in found if f.get("cause") == "security_exposure"], [])

    def test_a_site_holds_at_most_so_many_marks(self):
        old, sm.MAX_MARKS = sm.MAX_MARKS, 2
        try:
            for size in (1, 2):
                sm.mark(self.db, SITE, ITEM, "200", size, self.ids["admin"], self.org, "a@example.com")
            with self.assertRaises(ValueError):
                sm.mark(self.db, SITE, ITEM, "200", 3, self.ids["admin"], self.org, "a@example.com")
            sm.mark(self.db, SITE, ITEM, "200", 2, self.ids["admin"], self.org, "a@example.com")
        finally:
            sm.MAX_MARKS = old

    def test_clear_and_purge_take_the_marks(self):
        self.assertIn("security_marks", site_data.ACCOUNTS_DATA)

    def test_the_site_alert_skips_a_marked_answer(self):
        self.assertEqual(len(alerts_security.exposures([("today", blob())], SITE)), 1)
        sm.mark(self.db, SITE, ITEM, "200", 184, self.ids["admin"], self.org, "admin@example.com")
        marks = sm.of_site(self.db, SITE)
        self.assertEqual(alerts_security.exposures([("today", blob())], SITE, marks), [])
        self.assertEqual(len(alerts_security.exposures([("today", blob(9_000))], SITE, marks)), 1)

    def test_a_day_counted_with_rule_2_is_read_by_no_alert(self):
        self.assertEqual(sn.items(CONFIG, SITE, [blob(rule=2)], None), [],
                         "static files may be in it as possible: recount it first")
        self.assertEqual(alerts_security.exposures([("2026-11-24", blob(rule=2))], SITE), [])

    def test_the_route_by_role(self):
        self.assertTrue(security_api.is_security(f"/traffic/{SITE}/settings/security-mark"))
        mark = {"item": ITEM, "status": "200", "size": 184}
        self.assertEqual(self.ask("viewer", mark)[0], 403, "owners and admins only")
        self.assertEqual(self.ask("admin")[0], 405, "a POST only")
        for bad in ({**mark, "item": "x../../etc"}, {**mark, "status": "ok"},
                    {**mark, "size": "184"}, {**mark, "size": -1}):
            self.assertEqual(self.ask("admin", bad)[0], 400, bad)
        for bad in ({**mark, "status": "200\n"}, {**mark, "status": 200}, {**mark, "item": ITEM + "\n"}):
            self.assertEqual(self.ask("admin", bad)[0], 400, bad)
        other = sn.item_id("exposure", SITE, "www.example.com", "/older-than-the-items.php")
        self.assertEqual(self.ask("admin", {**mark, "item": other})[0], 200,
                         "a row older than the tracked items can be marked too")
        code, got = self.ask("admin", mark)
        self.assertEqual((code, got["marks"][ITEM][0]["size"]), (200, 184))
        self.assertEqual(self.open_items(), [])
        code, got = self.ask("viewer", None, "security-prefs")
        self.assertEqual((code, sorted(got["marks"])), (200, sorted([ITEM, other])),
                         "every member sees the marks")
        self.assertNotIn("user_id", got["marks"][ITEM][0])
        code, got = self.ask("admin", {"item": ITEM, "undo": True})
        self.assertEqual((code, list(got["marks"])), (200, [other]))


if __name__ == "__main__":
    unittest.main()
