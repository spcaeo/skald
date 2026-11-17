"""The daily summary (summary_mail.py) and the right-away security mail (security_notify):
one mail per person a day across every site they look after, nothing when nothing is open,
never twice the same day, a failed send retried, right away as one mail per run, the old
daily step mailing nobody, and the container scheduler's job at SKALD_SUMMARY_AT."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import accounts, security_notify as sn, summary_mail as sm, todo_marks  # noqa: E402
from skald.accounts import orgs, users  # noqa: E402

NOW = datetime(2026, 10, 26, 5, 0, tzinfo=timezone.utc)        # 01:00 in New York
DAY = "2026-10-26"
ZONE = ZoneInfo("America/New_York")
SITES = ("a.example.com", "b.example.com", "c.example.com", "d.example.com")
STACK = {"matches": [{"advisory": "php-2026-10-21", "product": "php", "host": "media.example.com",
                      "version": "8.3.10", "state": "update_needed"}]}


def exposure(site: str) -> dict:
    return {"rules": {"exposure_rule": 2}, "exposure": {"rows": [
        {"host": site, "path": "/.env.production", "status": "200", "size": 1873,
         "verdict": "possible", "category": "secrets"}]}}


class Mailbox:
    def __init__(self, fail: bool = False):
        self.sent, self.msgs, self.fail = [], [], fail

    def __call__(self, msg, cfg):
        if self.fail:
            raise ConnectionRefusedError("test")
        self.sent.append((cfg["to"][0], msg["Subject"], msg.get_body(("plain",)).get_content()))
        self.msgs.append(msg)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "accounts.sqlite"
        self.db = accounts.connect(self.path)
        one = orgs.create_org(self.db, "One", "test")["id"]
        two = orgs.create_org(self.db, "Two", "test")["id"]
        self.orgs = {"one": one, "two": two}
        for site in SITES[:3]:
            orgs.assign_site(self.db, site, one, "test")
        orgs.assign_site(self.db, SITES[3], two, "test")
        self.ids = {}
        for email, org, role in (("owner@example.com", one, "owner"),
                                 ("admin@example.com", one, "admin"),
                                 ("other@example.com", two, "owner")):
            u = users.create_user(self.db, email, "x", actor="test")
            # Confirmed (a password set) without the slow hash: only "set or not" is read here.
            self.db.execute("UPDATE users SET pw_hash = 'test' WHERE id = ?", (u["id"],))
            users.add_member(self.db, org, u["id"], role, "test")
            self.ids[email] = u["id"]
        users.add_member(self.db, two, self.ids["owner@example.com"], "admin", "test")
        self.out = self.dir / "out"
        self.sites = [self.site(s) for s in SITES]
        self.box = Mailbox()
        self.printed = []

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def config(self, site: str) -> dict:
        return {"site": {"name": site},
                "dashboard": {"url": f"https://stats.example.com/traffic/{site}/"},
                "mail": {"host": "smtp.example.com", "port": 587, "from": "skald@example.com",
                         "to": []},
                "access": {"mode": "sessions", "accounts": str(self.path)},
                "report": {"timezone": "America/New_York"}}

    def site(self, site: str) -> dict:
        return {"site": site, "config": self.config(site), "live_dir": self.dir,
                "history": self.dir / "history.sqlite", "out": self.out, "config_path": None}

    def open_on(self, *sites):
        for site in sites:
            sn.track(self.db, site, sn.items({}, site, [exposure(site)], STACK), NOW)

    def todos(self, site: str, n: int):
        folder = self.out / site / "data"
        folder.mkdir(parents=True, exist_ok=True)
        todos = [{"id": f"lost-{i}", "kind": "lost", "state": "open", "title": f"Fix thing {i}",
                  "proof": f"{i} old addresses answered not found.", "todo": "Redirect each."}
                 for i in range(n)]
        (folder / "todos.json").write_text(json.dumps({"todos": todos}))

    def summarise(self, now=NOW, day=DAY, box=None, setup=None, dry=False):
        return sm.run(self.db, self.sites, now, day, send=box or self.box, dry_run=dry,
                      out=self.printed.append, setup=setup or (lambda s, now: []))

    def mail_to(self, email):
        return [m for m in self.box.sent if m[0] == email]


class Summary(Base):
    def test_one_mail_per_person_across_sites(self):
        self.open_on("a.example.com", "c.example.com", "d.example.com")
        self.todos("b.example.com", 2)
        todo_marks.mark(self.db, "b.example.com", "lost-1", "notnow", "2026-10-25")
        got = self.summarise()
        self.assertEqual(got["sent"], 3)
        mine = self.mail_to("owner@example.com")
        self.assertEqual(len(mine), 1, "one mail for all four sites")
        _, subject, text = mine[0]
        self.assertEqual(subject, "[Skald] 6 to act on, 1 to-do on 4 sites")
        overview = text[text.index("OVERVIEW"):]
        for site in SITES:
            self.assertIn(site, overview, "a row per site in the overview")
        self.assertIn("- [New] a.example.com · Possible exposure\n"
                      "  https://stats.example.com/traffic/a.example.com/#threats/exposed?item=x", text)
        self.assertNotIn(".env.production", text, "#68: a name and a link, never the address")
        self.assertNotIn("Fix thing", text, "#68: to-dos are counted, never listed")
        self.assertRegex(overview, r"(?m)^  b\.example\.com +- +1 +- +https://stats\.example\.com/"
                         r"traffic/b\.example\.com/$", "lost-1 marked not now: one to-do left")
        self.assertLess(text.index("ACT NOW"), text.index("OVERVIEW"))
        self.assertNotIn("TO-DOS BY SITE", text)
        other = self.mail_to("other@example.com")
        self.assertEqual(len(other), 1)
        self.assertIn("1 site", other[0][1].replace("sites", "site"))
        self.assertNotRegex(other[0][2], r"(?m)^  a\.example\.com |\] a\.example\.com ·",
                            "only the sites of their organisation")
        audit = self.db.execute("SELECT org_id, target, detail FROM audit WHERE action = "
                                "'summary.sent' ORDER BY id").fetchall()
        owner = [r for r in audit if r[1] == "owner@example.com"]
        self.assertEqual(sorted(r[0] for r in owner), sorted(self.orgs.values()),
                         "a row in each organisation the mail covered")
        self.assertFalse(any(".env" in r[2] or "Fix thing" in r[2] for r in audit), "never the content")

    def test_nothing_open_sends_nothing(self):
        got = self.summarise()
        self.assertEqual((got["sent"], got["nothing"]), (0, 3))
        self.assertEqual(self.box.sent, [])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM summary_sends").fetchone()[0], 0)

    def test_not_twice_the_same_day(self):
        self.open_on("a.example.com")
        self.assertEqual(self.summarise()["sent"], 2)
        again = self.summarise(now=NOW + timedelta(hours=3))
        self.assertEqual((again["sent"], again["already"]), (0, 2), "a restart sends nothing")
        self.assertEqual(len(self.box.sent), 2)
        nxt = self.summarise(now=NOW + timedelta(days=1), day="2026-10-27")
        self.assertEqual(nxt["sent"], 2, "the next day: again, while it stays open")
        text = self.mail_to("owner@example.com")[-1][2]
        self.assertIn("[Still open] a.example.com · Possible exposure", text)
        self.assertNotIn("[New]", text)

    def test_a_failed_send_is_retried(self):
        self.open_on("a.example.com")
        got = self.summarise(box=Mailbox(fail=True))
        self.assertEqual((got["sent"], got["failed"]), (0, 2))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM summary_sends").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM security_sends").fetchone()[0], 0,
                         "not recorded: still new next time")
        self.assertEqual(self.summarise(now=NOW + timedelta(hours=1))["sent"], 2, "the next run retries")
        self.assertIn("[New] ", self.mail_to("owner@example.com")[0][2])

    def test_to_dos_are_counted_never_listed(self):
        self.todos("b.example.com", 13)
        self.summarise()
        _, subject, text = self.mail_to("owner@example.com")[0]
        self.assertEqual(subject, "[Skald] 13 to-dos on 1 site", "every to-do counted")
        self.assertNotIn("Fix thing", text)
        self.assertNotIn("&fix=1", text, "never a to-do's link, never a code")
        self.assertRegex(text, r"(?m)^  b\.example\.com +- +13 +- ")
        msg = self.box.msgs[[m[0] for m in self.box.sent].index("owner@example.com")]
        html = msg.get_body(("html",)).get_content()
        self.assertIn('href="https://stats.example.com/traffic/b.example.com/#overview/insights"',
                      html, "the to-dos figure links to the list")

    def test_at_most_ten_act_now_lines_a_site_then_and_more(self):
        def setup(s, now):
            if s["site"] != "a.example.com":
                return []
            return [{"item": f"setup:check{i}", "title": f"Check {i}: needs attention",
                     "todo": "Fix it.", "where": None,
                     "link": "https://stats.example.com/traffic/a.example.com/#settings/todo"}
                    for i in range(13)]
        self.summarise(setup=setup)
        _, subject, text = self.mail_to("owner@example.com")[0]
        self.assertEqual(subject, "[Skald] 13 to act on on 1 site")
        self.assertEqual(text.count("- a.example.com · Set-up: Check "), 10)
        self.assertIn("- and 3 more on a.example.com: "
                      "https://stats.example.com/traffic/a.example.com/#threats/exposed", text)

    def test_set_up_lines_and_install_wide_once(self):
        def setup(s, now):
            got = [{"item": "setup:disk", "title": "Disk: 0.5 GB free", "todo": "Free some space.",
                    "link": None, "where": "on the server: `./bin/skald doctor`"}]
            if s["site"] == "a.example.com":
                got.append({"item": "setup:script", "title": "Script tag: no event has arrived yet",
                            "todo": "Put the tag on every page.",
                            "link": "https://stats.example.com/traffic/a.example.com/#settings/site/leads",
                            "where": None})
            return got
        self.summarise(setup=setup)
        text = self.mail_to("owner@example.com")[0][2]
        self.assertEqual(text.count("Set-up: Disk"), 1, "install-wide: once per mail")
        self.assertIn("ACT NOW (2)", text)
        self.assertNotIn("b.example.com", text, "nothing else there: no section")
        self.assertIn("#settings/site/leads", text)
        self.assertIn("(on the server: `./bin/skald doctor`)", text)

    def test_the_real_set_up_checks_never_use_the_network(self):
        s = self.sites[0]
        s["config"]["logs"] = {"dir": str(self.dir / "logs"), "base": "access.log"}
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")), \
                mock.patch("skald.conversions.roads.helper", side_effect=AssertionError("helper")):
            got = sm.setup_part(s, NOW)
        self.assertTrue(got, "a fresh folder has things to set up")
        for it in got:
            self.assertTrue(it["item"].startswith("setup:"))
            self.assertTrue(it["title"] and it["todo"])
            self.assertNotIn("could not check", it["title"])

    def test_dry_run_prints_and_records_nothing(self):
        self.open_on("a.example.com")
        got = self.summarise(dry=True)
        self.assertEqual(got["sent"], 0)
        self.assertEqual(self.box.sent, [])
        self.assertTrue(any("Subject: [Skald] 2 to act on on 1 site" in p for p in self.printed))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM summary_sends").fetchone()[0], 0)

    def test_the_command_waits_for_after(self):
        ctx = SimpleNamespace(config=self.config("a.example.com"), all_configs=[s["config"] for s in self.sites],
                              tz=ZONE, now=NOW - timedelta(minutes=30), live_dir=self.dir,
                              db_path=self.dir / "history.sqlite", config_path=self.dir / "config.yml",
                              args=SimpleNamespace(dry_run=False, after="01:00", only_site=None),
                              out=self.printed.append)
        self.open_on("a.example.com")
        self.assertEqual(sm.cmd_summary_mail(ctx, send=self.box), 0)
        self.assertEqual(self.box.sent, [], "00:30: not yet")
        self.assertIn("not before 01:00", self.printed[-1])


class Layout(Base):
    """#68: act now first, an overview, look-alikes folded, version checks as notes, the last
    day counted, and a branded HTML part made from the same digest as the text."""

    def open_many(self, site: str, n: int, stack=None):
        rows = [{"host": site, "path": f"/wp-json/wp/v2/pages/{1000 + i}", "status": "200",
                 "size": 38000 + i, "verdict": "possible", "category": "cms"} for i in range(n)]
        blob = {"rules": {"exposure_rule": 2}, "exposure": {"rows": rows}}
        sn.track(self.db, site, sn.items({}, site, [blob], stack), NOW)

    def test_look_alikes_fold_into_one_line_and_every_item_is_recorded(self):
        self.open_many("a.example.com", 62)
        self.summarise()
        _, subject, text = self.mail_to("owner@example.com")[0]
        self.assertEqual(subject, "[Skald] 1 to act on on 1 site", "one line to act on, not 62")
        self.assertIn("- [New] a.example.com · Possible exposure (62)\n"
                      "  https://stats.example.com/traffic/a.example.com/#threats/exposed\n", text,
                      "one line, one link to the whole list")
        self.assertNotIn("/wp-json/", text, "no addresses")
        uid = self.ids["owner@example.com"]
        rows = self.db.execute("SELECT COUNT(*) FROM summary_items WHERE user_id = ? AND "
                               "part = 'security'", (uid,)).fetchone()[0]
        self.assertEqual(rows, 62, "folded, but every item carried and recorded")
        sent = self.db.execute("SELECT items FROM summary_sends WHERE user_id = ?", (uid,)).fetchone()[0]
        self.assertEqual(sent, 62)
        self.summarise(now=NOW + timedelta(days=1), day="2026-10-27")
        self.assertIn("[Still open] a.example.com · Possible exposure (62)",
                      self.mail_to("owner@example.com")[-1][2], "the next day: still open, folded")

    def test_two_of_one_name_are_one_line_and_one_stays_plain(self):
        self.open_many("a.example.com", 2)
        self.open_many("c.example.com", 1)
        self.summarise()
        _, subject, text = self.mail_to("owner@example.com")[0]
        self.assertEqual(subject, "[Skald] 2 to act on on 2 sites")
        self.assertIn("a.example.com · Possible exposure (2)\n", text)
        self.assertIn("c.example.com · Possible exposure\n", text)

    def test_version_checks_are_notes_not_acts(self):
        stack = {"matches": [{"advisory": f"node-{h}", "product": "nodejs", "host": h,
                              "version": None, "state": "check_version"}
                             for h in ("a.example.com", "cms.a.example.com")]}
        sn.track(self.db, "a.example.com", sn.items({}, "a.example.com", [], stack), NOW)
        self.todos("a.example.com", 1)
        self.summarise()
        _, subject, text = self.mail_to("owner@example.com")[0]
        self.assertEqual(subject, "[Skald] 1 to-do on 1 site", "notes stay out of the subject")
        self.assertNotIn("ACT NOW", text)
        self.assertNotIn("NOTES", text, "#68: notes are counted, never listed")
        self.assertRegex(text, r"(?m)^  a\.example\.com +- +1 +2 ")
        self.assertIn("0 to act on now · 1 to-do · 2 notes · 1 site", text,
                      "the notes count is the overview's column, not the sites with notes")

    def test_only_notes_still_mails_and_says_so(self):
        stack = {"matches": [{"advisory": "php-x", "product": "php", "host": "a.example.com",
                              "version": None, "state": "check_version"}]}
        sn.track(self.db, "a.example.com", sn.items({}, "a.example.com", [], stack), NOW)
        self.summarise()
        self.assertEqual(self.mail_to("owner@example.com")[0][1], "[Skald] 1 note on 1 site")

    def test_the_last_day_counted_is_said(self):
        self.todos("b.example.com", 1)
        path = self.out / "b.example.com" / "data" / "todos.json"
        body = json.loads(path.read_text())
        body["window"] = {"first": "2026-09-25", "last": "2026-10-24", "days": 30, "of": 30}
        path.write_text(json.dumps(body))
        self.summarise()
        text = self.mail_to("owner@example.com")[0][2]
        self.assertTrue(text.startswith("Skald daily summary · Mon 26 Oct 2026\n"
                                        "Figures up to Sat 24 Oct 2026, the last whole day counted."))

    def test_the_html_part_is_the_short_layout_from_the_same_digest(self):
        self.open_on("a.example.com")
        self.todos("b.example.com", 2)
        self.summarise()
        msg = self.box.msgs[[m[0] for m in self.box.sent].index("owner@example.com")]
        html = msg.get_body(("html",)).get_content()
        self.assertNotIn("<pre", html, "no longer the text in a <pre>")
        self.assertIn("Act now (2)", html)
        self.assertIn("Overview", html)
        for gone in ("to-dos (2)", "Fix with your AI agent", "Fix thing", ".env.production",
                     "display:none"):
            self.assertNotIn(gone, html, "#68: short, no descriptions, no hidden text")
        self.assertIn('href="https://stats.example.com/traffic/a.example.com/"', html,
                      "the site's name links to its dashboard")
        self.assertIn('href="https://stats.example.com/traffic/a.example.com/#threats/exposed?item=x',
                      html)
        self.assertIn('name="color-scheme"', html)
        text = msg.get_body(("plain",)).get_content()
        self.assertIn("2 to act on now · 2 to-dos · 0 notes · 2 sites", text)
        if "cid:skald-mark" in html:
            parts = [p.get("Content-ID") for p in msg.walk()]
            self.assertIn("<skald-mark>", parts, "the mark is sent inside the mail")

    def test_every_count_is_counted_from_the_open_items(self):
        """The counts, the subject and the overview change with the data: nothing is
        written in by hand, and each count is the sum of its overview column."""
        stack = {"matches": [{"advisory": f"node-{h}", "product": "nodejs", "host": h,
                              "version": None, "state": "check_version"}
                             for h in ("c.example.com", "cms.c.example.com", "x.c.example.com")]}
        self.open_many("a.example.com", 5)
        sn.track(self.db, "c.example.com", sn.items({}, "c.example.com", [], stack), NOW)
        self.todos("b.example.com", 4)
        self.todos("c.example.com", 7)
        self.summarise()
        _, subject, text = self.mail_to("owner@example.com")[0]
        rows = text[text.index("OVERVIEW"):].splitlines()[2:]
        rows = [r.split() for r in rows if r.startswith("  ") and "example.com" in r]
        sums = [sum(int(r[k]) if r[k] != "-" else 0 for r in rows) for k in (1, 2, 3)]
        self.assertEqual(sums, [1, 11, 3])
        self.assertIn(f"{sums[0]} to act on now · {sums[1]} to-dos · {sums[2]} notes · "
                      f"{len(rows)} sites", text)
        self.assertEqual(subject, "[Skald] 1 to act on, 11 to-dos on 3 sites")

    def test_the_mail_stays_small(self):
        """Gmail clips a mail over about 102 KB; a busy install's mail stays far below."""
        self.open_many("a.example.com", 62)
        for site in SITES[1:3]:
            self.open_on(site)
            self.todos(site, 40)
        self.summarise()
        msg = self.box.msgs[[m[0] for m in self.box.sent].index("owner@example.com")]
        self.assertLess(len(msg.as_bytes()), 30_000)

    def test_dry_run_writes_the_html_part_when_asked(self):
        self.open_on("a.example.com")
        sm.run(self.db, self.sites, NOW, DAY, send=self.box, dry_run=True, out=self.printed.append,
               setup=lambda s, now: [], html_dir=self.dir)
        page = self.dir / f"summary-{self.ids['owner@example.com']}.html"
        self.assertTrue(page.is_file())
        self.assertIn("Act now (2)", page.read_text())
        self.assertEqual(self.box.sent, [], "nothing sent")


class RightAway(Base):
    def ctx(self, site):
        return SimpleNamespace(site=site, config=self.config(site), live_dir=self.dir, now=NOW,
                               out=self.printed.append, err=self.printed.append)

    def test_one_mail_per_person_per_run(self):
        for site in SITES[:2]:
            sn.set_prefs(self.db, self.ids["owner@example.com"], site, True, "now")
        self.open_on(*SITES)
        got = sn.right_away([self.ctx(s) for s in SITES], send=self.box)
        self.assertEqual(len(self.box.sent), 1, "one mail, never one per item or per site")
        to, subject, text = self.box.sent[0]
        self.assertEqual((to, subject), ("owner@example.com", "[Skald] Security: 4 items on 2 sites"))
        self.assertEqual(len(got), 4)
        self.assertNotIn("c.example.com", text, "the summary is that site's choice")
        self.assertEqual(sn.right_away([self.ctx(s) for s in SITES], send=self.box), [], "once")

    def test_the_old_daily_step_mails_nobody(self):
        sn.set_prefs(self.db, self.ids["owner@example.com"], SITES[0], True, "daily")
        ctx = self.ctx(SITES[0])
        ctx.tz, ctx.history = ZONE, (lambda: mock.MagicMock())
        found = sn.items({}, SITES[0], [exposure(SITES[0])], STACK)
        with mock.patch.object(sn, "_found", return_value=found):
            self.assertEqual(sn.daily(ctx, send=self.box), 0)
        self.assertEqual(self.box.sent, [])
        self.assertEqual(len(sn.open_items(self.db, SITES[0])), 2, "still tracked")
        self.assertIn("2 open", self.printed[-1])


class Scheduler(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "docker"))
        import scheduler
        self.s = scheduler

    def test_the_job_and_its_time(self):
        sch = self.s.Scheduler("/tmp/config.yml", "America/New_York", 2, "07:15", "03:30",
                               summary_at="01:00")
        job = next(j for j in sch.jobs if j.name == "summary-mail")
        self.assertEqual(job.args[-1], "summary-mail")
        after = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(job.due_after(after), datetime(2026, 10, 26, 5, 0, tzinfo=timezone.utc),
                         "01:00 in New York (summer time)")

    def test_the_default_and_off(self):
        self.assertEqual(self.s.summary_time(None), "01:00")
        self.assertEqual(self.s.summary_time("13:30"), "13:30")
        self.assertIsNone(self.s.summary_time("off"))
        with self.assertRaises(ValueError):
            self.s.summary_time("25:00")
        sch = self.s.Scheduler("/tmp/config.yml", "UTC", 2, "07:15", "03:30", summary_at=None)
        self.assertNotIn("summary-mail", [j.name for j in sch.jobs])


if __name__ == "__main__":
    unittest.main()
