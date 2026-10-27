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
        self.sent, self.fail = [], fail

    def __call__(self, msg, cfg):
        if self.fail:
            raise ConnectionRefusedError("test")
        self.sent.append((cfg["to"][0], msg["Subject"], msg.get_body(("plain",)).get_content()))


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
        self.assertEqual(subject, "[Skald] 7 things to look at on 4 sites")
        for site in SITES:
            self.assertIn(f"== {site} ==", text)
        self.assertIn("New: Possible exposure on a.example.com", text)
        self.assertIn("#threats/exposed?item=x", text)
        self.assertIn("#overview/insights?todo=lost-0", text)
        self.assertNotIn("lost-1", text, "marked not now: left out")
        self.assertLess(text.index("Security"), text.index("To-dos to fix") if "To-dos" in text else 10**9)
        other = self.mail_to("other@example.com")
        self.assertEqual(len(other), 1)
        self.assertIn("1 site", other[0][1].replace("sites", "site"))
        self.assertNotIn("== a.example.com ==", other[0][2], "only the sites of their organisation")
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
        self.assertIn("Still open: Possible exposure", text)
        self.assertNotIn("New: ", text)

    def test_a_failed_send_is_retried(self):
        self.open_on("a.example.com")
        got = self.summarise(box=Mailbox(fail=True))
        self.assertEqual((got["sent"], got["failed"]), (0, 2))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM summary_sends").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM security_sends").fetchone()[0], 0,
                         "not recorded: still new next time")
        self.assertEqual(self.summarise(now=NOW + timedelta(hours=1))["sent"], 2, "the next run retries")
        self.assertIn("New: ", self.mail_to("owner@example.com")[0][2])

    def test_at_most_ten_lines_then_and_more(self):
        self.todos("b.example.com", 13)
        self.summarise()
        text = self.mail_to("owner@example.com")[0][2]
        self.assertEqual(text.count("Open it: https://stats.example.com/traffic/b.example.com/#overview/insights?todo="), 10)
        self.assertEqual(text.count("&fix=1&by=agent"), 10, "each with its Fix this link, never a code")
        self.assertIn("- and 3 more: https://stats.example.com/traffic/b.example.com/#overview/insights", text)
        self.assertIn("13 things", self.mail_to("owner@example.com")[0][1])

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
        self.assertEqual(text.count("Disk: 0.5 GB free"), 1, "install-wide: once per mail")
        self.assertIn("Set-up problems (2)", text)
        self.assertNotIn("== b.example.com ==", text, "nothing else there: no section")
        self.assertIn("#settings/site/leads", text)
        self.assertIn("Where: on the server", text)

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
        self.assertTrue(any("Subject: [Skald] 2 things to look at on 1 site" in p for p in self.printed))
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
