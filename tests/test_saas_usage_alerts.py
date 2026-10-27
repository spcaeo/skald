"""Usage alerts (skald/saas/usage_alerts.py): a mail to an organisation's owners
and admins when this month's requests reach 80, 90 and 100 % of its plan's
requests_month. Each mark once a month (state written before the send, kept across a
restart and a recount), one mail for a jump past several, a new month starts again, a
bigger plan starts from the new limit's marks not yet passed, viewers never mailed, the
link opens the organisation's own dashboard, saas off or no limit: nothing.

Addresses are example.com; no real secret anywhere.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402

from skald import accounts  # noqa: E402
from skald.accounts import auditlog  # noqa: E402
from skald.accounts import db as base  # noqa: E402
from skald.saas import limits, mails, plans, usage_alerts  # noqa: E402
from skald.store import SCHEMA as HISTORY_SCHEMA  # noqa: E402

SITE, OTHER = "a.example.com", "b.example.com"
PLANS = {"small": {"requests_month": 1000}, "big": {"requests_month": 2000},
         "bit_bigger": {"requests_month": 1100}, "open": {"sites": 3}}
MAIL = {"host": "smtp.example.com", "from": "skald@example.com"}


def config(**extra) -> dict:
    return {"access": {"mode": "sessions", "base_url": "https://dash.example.com"},
            "mail": dict(MAIL),
            "saas": {"enabled": True, "plans": PLANS, "default_plan": "small", **extra}}


class Case(AccountsCase):
    def setUp(self):
        super().setUp()
        self.at("2026-10-20T12:00:00Z")
        self.cfg = config()
        self.hist = self.dir / "history.sqlite"
        h = __import__("sqlite3").connect(self.hist)
        h.executescript(HISTORY_SCHEMA)
        h.commit()
        h.close()
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        accounts.assign_site(self.db, SITE, self.org["id"], "cli")
        plans.set_plan(self.db, self.org["id"], "small", "active", "cli")
        self.owner = self.member("owner@example.com", "owner")
        self.admin = self.member("admin@example.com", "admin")
        self.viewer = self.member("viewer@example.com", "viewer")
        self.member("pending@example.com", "admin", confirmed=False)
        self.sent: list = []

    def member(self, email, role, confirmed=True, org=None):
        user = accounts.create_user(self.db, email, "x")
        accounts.add_member(self.db, (org or self.org)["id"], user["id"], role, "cli")
        if confirmed:
            self.db.execute("UPDATE users SET pw_hash = 'set' WHERE id = ?", (user["id"],))
        return user

    def send(self, msg, config, to):
        self.sent.append((to, msg))

    def day(self, day: str, hits: int, site: str = SITE) -> None:
        """Store (or recount) one day of `hits` requests, with its groups adding up."""
        h = __import__("sqlite3").connect(self.hist)
        h.execute("DELETE FROM days WHERE site = ? AND day = ?", (site, day))
        h.execute("DELETE FROM groups WHERE site = ? AND day = ?", (site, day))
        h.execute("INSERT INTO days (site, day, timezone, collected_at, verified, parsed, hits, "
                  "other_hosts, cited_visits) VALUES (?, ?, 'UTC', 'x', 1, ?, ?, 0, 0)",
                  (site, day, hits, hits))
        h.execute("INSERT INTO groups (site, day, grp, hits, views, visits, probes) "
                  "VALUES (?, ?, 'people', ?, 0, 0, 0)", (site, day, hits))
        h.commit()
        h.close()

    def check(self, cfg=None, org=None, link="https://dash.example.com/traffic/a.example.com/"
              "#settings/org/billing"):
        return usage_alerts.check(self.db, (org or self.org)["id"], cfg or self.cfg, self.hist,
                                  force=True, link=link, send=self.send)

    def mailed(self) -> list[str]:
        got = sorted(to for to, _ in self.sent)
        self.sent.clear()
        return got

    def rows(self, org=None):
        return [tuple(r) for r in self.db.execute(
            "SELECT requests_limit, mark, state FROM usage_alerts WHERE org_id = ? "
            "ORDER BY requests_limit, mark", ((org or self.org)["id"],))]

    def alerts_logged(self, org=None):
        return [e for e in auditlog.recent(self.db, (org or self.org)["id"])
                if e["action"] == "billing.usage_alert"]


class Marks(Case):
    def test_each_mark_once_to_owners_and_admins_only(self):
        self.day("2026-10-01", 700)
        self.assertIsNone(self.check())
        self.assertEqual(self.mailed(), [])
        self.day("2026-10-02", 100)                       # 800: 80 %
        got = self.check()
        self.assertEqual((got["mark"], got["used"], got["limit"], got["sent"]), (80, 800, 1000, 2))
        # Viewers, unconfirmed and disabled accounts are never mailed.
        self.assertEqual(self.mailed(), ["admin@example.com", "owner@example.com"])
        self.assertIsNone(self.check())                   # the same mark again: nothing
        self.day("2026-10-03", 50)                        # 850: still 80
        self.assertIsNone(self.check())
        self.day("2026-10-04", 50)                        # 900: 90
        self.assertEqual(self.check()["mark"], 90)
        self.assertEqual(len(self.mailed()), 2)
        self.day("2026-10-05", 100)                       # 1,000: 100
        self.assertEqual(self.check()["mark"], 100)
        self.assertEqual(len(self.mailed()), 2)
        self.day("2026-10-06", 500)                       # past it: no fourth mail
        self.assertIsNone(self.check())
        self.assertEqual(self.mailed(), [])
        self.assertEqual(self.rows(), [(1000, 80, "sent"), (1000, 90, "sent"), (1000, 100, "sent")])
        logged = self.alerts_logged()
        self.assertEqual([e["target"] for e in logged], ["100%", "90%", "80%"])
        self.assertIn("800 of 1,000 requests in 2026-10 (80%)", logged[-1]["detail"])
        self.assertIn("mailed 2 of 2 owners and admins", logged[-1]["detail"])
        for e in logged:                                  # never an address in the row
            self.assertNotIn("@", e["target"] + e["detail"])
            self.assertEqual(e["actor"], "skald")

    def test_a_disabled_owner_gets_nothing(self):
        self.db.execute("UPDATE users SET disabled_at = 'x' WHERE id = ?", (self.admin["id"],))
        self.day("2026-10-01", 800)
        self.check()
        self.assertEqual(self.mailed(), ["owner@example.com"])

    def test_a_jump_past_two_marks_sends_one_mail_for_the_highest(self):
        self.day("2026-10-01", 950)
        got = self.check()
        self.assertEqual(got["mark"], 90)
        self.assertEqual(len(self.mailed()), 2)           # one each, not two each
        self.assertEqual(self.rows(), [(1000, 80, "skipped"), (1000, 90, "sent")])
        self.assertEqual(len(self.alerts_logged()), 1)

    def test_a_recount_down_then_up_never_repeats(self):
        self.day("2026-10-01", 850)
        self.check()
        self.mailed()
        self.day("2026-10-01", 300)                       # a recount lowers the day
        self.assertIsNone(self.check())
        self.day("2026-10-01", 850)                       # and back
        self.assertIsNone(self.check())
        self.assertEqual(self.mailed(), [])

    def test_a_new_month_starts_again(self):
        self.day("2026-10-01", 850)
        self.check()
        self.assertEqual(len(self.mailed()), 2)
        self.at("2026-11-03T08:00:00Z")
        self.assertIsNone(self.check())                   # nothing stored for November yet
        self.day("2026-11-01", 820)
        self.assertEqual(self.check()["month"], "2026-11")
        self.assertEqual(len(self.mailed()), 2)

    def test_state_survives_a_restart(self):
        self.day("2026-10-01", 820)
        self.check()
        self.mailed()
        self.db.close()
        self.db = base.connect(self.path)                 # a new process
        self.assertIsNone(self.check())
        self.assertEqual(self.mailed(), [])

    def test_a_failed_send_is_noted_and_not_retried(self):
        def broken(msg, config, to):
            raise OSError("no route")
        self.day("2026-10-01", 820)
        got = usage_alerts.check(self.db, self.org["id"], self.cfg, self.hist, force=True,
                                 send=broken)
        self.assertEqual((got["sent"], got["failed"]), (0, 2))
        self.assertEqual(self.rows(), [(1000, 80, "failed")])
        self.assertIn("not sent: OSError", self.alerts_logged()[0]["detail"])
        self.assertIsNone(self.check())


class PlanChange(Case):
    def test_a_bigger_plan_counts_from_its_own_marks(self):
        self.day("2026-10-01", 950)
        self.check()                                      # 90 % of 1,000
        self.mailed()
        plans.set_plan(self.db, self.org["id"], "big", "active", "cli")
        self.assertIsNone(self.check())                   # 47 % of 2,000
        self.day("2026-10-02", 650)                       # 1,600: 80 % of 2,000
        self.assertEqual(self.check()["mark"], 80)
        self.assertEqual(len(self.mailed()), 2)
        self.assertEqual(self.rows(), [(1000, 80, "skipped"), (1000, 90, "sent"),
                                       (2000, 80, "sent")])

    def test_marks_the_new_limit_had_already_passed_are_not_mailed(self):
        self.day("2026-10-01", 950)
        self.check()
        self.mailed()
        plans.set_plan(self.db, self.org["id"], "bit_bigger", "active", "cli")
        self.assertIsNone(self.check())                   # 86 % of 1,100: passed before
        self.assertEqual(self.mailed(), [])
        self.day("2026-10-02", 50)                        # 1,000: 90 % of 1,100
        self.assertEqual(self.check()["mark"], 90)
        self.assertEqual(len(self.mailed()), 2)

    def test_back_to_the_old_plan_repeats_nothing(self):
        self.day("2026-10-01", 950)
        self.check()
        plans.set_plan(self.db, self.org["id"], "big", "active", "cli")
        self.check()
        plans.set_plan(self.db, self.org["id"], "small", "active", "cli")
        self.mailed()
        self.assertIsNone(self.check())
        self.assertEqual(self.mailed(), [])


class Nothing(Case):
    def test_saas_off_does_nothing(self):
        self.day("2026-10-01", 1500)
        off = {**self.cfg, "saas": {**self.cfg["saas"], "enabled": False}}
        self.assertIsNone(self.check(off))
        self.assertEqual(usage_alerts.run(self.db, off, self.hist, send=self.send), [])
        basic = {**self.cfg, "access": {"mode": "basic"}}
        self.assertIsNone(self.check(basic))
        self.assertEqual(self.mailed(), [])
        self.assertEqual(self.alerts_logged(), [])
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master")}
        self.assertNotIn("usage_alerts", tables)          # not even a table made

    def test_the_switch_turns_the_mails_and_the_mark_off(self):
        self.day("2026-10-01", 900)
        for value in (False, "false", "off"):
            cfg = config(usage_alerts=value)
            self.assertFalse(usage_alerts.on(cfg))
            self.assertIsNone(self.check(cfg))
            got = limits.summary(self.db, self.org["id"], cfg, self.hist)
            self.assertEqual((got["usage"]["percent"], got["usage"]["mark"]), (90, None))
        self.assertTrue(usage_alerts.on(config()))
        self.assertTrue(usage_alerts.on(config(usage_alerts=True)))
        self.assertEqual(self.mailed(), [])

    def test_no_plan_or_no_requests_limit(self):
        self.day("2026-10-01", 5000)
        plans.set_plan(self.db, self.org["id"], None, "none", "cli")
        self.assertIsNone(self.check())
        plans.set_plan(self.db, self.org["id"], "open", "active", "cli")   # no requests_month
        self.assertIsNone(self.check())
        self.assertEqual(self.mailed(), [])

    def test_unknown_or_withheld_usage_never_alerts(self):
        self.assertIsNone(self.check())                   # no day stored: not known, not 0
        h = __import__("sqlite3").connect(self.hist)
        h.execute("INSERT INTO days (site, day, timezone, collected_at, verified, parsed, hits, "
                  "other_hosts, cited_visits) VALUES (?, '2026-10-01', 'UTC', 'x', 1, 900, 900, "
                  "0, 0)", (SITE,))                       # its groups do not add up
        h.commit()
        h.close()
        self.assertIsNone(self.check())
        self.assertEqual(self.mailed(), [])

    def test_at_most_one_check_per_organisation_every_few_minutes(self):
        self.day("2026-10-01", 500)
        calls = []
        real = limits.usage

        def counted(*a, **kw):
            calls.append(1)
            return real(*a, **kw)
        limits.usage = counted
        try:
            usage_alerts.check(self.db, self.org["id"], self.cfg, self.hist, send=self.send)
            self.tick(60)
            usage_alerts.check(self.db, self.org["id"], self.cfg, self.hist, send=self.send)
            self.assertEqual(len(calls), 1)               # the second was skipped
            self.tick(usage_alerts.CHECK_MINUTES * 60)
            usage_alerts.check(self.db, self.org["id"], self.cfg, self.hist, send=self.send)
            self.assertEqual(len(calls), 2)
            usage_alerts.check(self.db, self.org["id"], self.cfg, self.hist, force=True,
                               send=self.send)             # run-daily: always
            self.assertEqual(len(calls), 3)
        finally:
            limits.usage = real


class TheMail(Case):
    def test_what_it_says(self):
        msg = mails.usage_mail(self.cfg, "owner@example.com", "Alpha", "small", 850, 1000,
                               "2026-10", 80, "https://dash.example.com/traffic/"
                               "a.example.com/#settings/org/billing")
        self.assertIn("Alpha has reached 80% of this month's requests", msg["Subject"])
        text = msg.get_body(("plain",)).get_content()
        self.assertIn("Alpha has used 850 of the 1,000 requests its small plan allows this month "
                      "(85%)", text)
        self.assertIn("The count starts again on 1 November 2026.", text)
        self.assertIn("Skald's shipper keeps them and sends them again later", text)
        self.assertIn("Lines from a Cloudflare Worker are lost", text)
        self.assertIn("https://dash.example.com/traffic/a.example.com/#settings/org/billing", text)
        html = msg.get_body(("html",)).get_content()
        self.assertIn('href="https://dash.example.com/traffic/a.example.com/#settings/org/billing"',
                      html)
        self.assertIn("Open Billing", html)
        full = mails.usage_mail(self.cfg, "owner@example.com", "Alpha", "small", 1000, 1000,
                                "2026-12", 100, None)
        self.assertIn("Alpha has used all of this month's requests", full["Subject"])
        self.assertIn("1 January 2027", full.get_body(("plain",)).get_content())
        self.assertNotIn("Open Billing", full.get_body(("html",)).get_content())   # no link

    def test_the_link_is_the_organisations_own_dashboard(self):
        beta = accounts.create_org(self.db, "Beta", "cli")
        accounts.assign_site(self.db, OTHER, beta["id"], "cli")
        plans.set_plan(self.db, beta["id"], "small", "active", "cli")
        self.member("beta-owner@example.com", "owner", org=beta)
        self.day("2026-10-01", 900)
        self.day("2026-10-01", 900, OTHER)
        urls = {SITE: "https://dash.example.com/traffic/a.example.com/",
                OTHER: "https://dash.example.com/traffic/b.example.com/#overview"}
        got = usage_alerts.run(self.db, self.cfg, self.hist, urls, force=True, send=self.send)
        self.assertEqual(len(got), 2)
        links = {}
        for to, msg in self.sent:
            text = msg.get_body(("plain",)).get_content()
            links[to] = [w for w in text.split() if w.startswith("https://")][0]
        self.assertEqual(links["owner@example.com"],
                         "https://dash.example.com/traffic/a.example.com/#settings/org/billing")
        self.assertEqual(links["beta-owner@example.com"],
                         "https://dash.example.com/traffic/b.example.com/#settings/org/billing")
        # No dashboard.url for the site: the install's base address and its own folder.
        self.assertEqual(usage_alerts.billing_link([OTHER], {}, self.cfg),
                         "https://dash.example.com/traffic/b.example.com/#settings/org/billing")
        self.assertIsNone(usage_alerts.billing_link([OTHER], {}, {}))

    def test_after_a_run(self):
        """summary_mail.after_run's call: the accounts file beside the history, run-daily
        always checks, and nothing at all with saas off."""
        out = []
        ctx = SimpleNamespace(site=SITE, live_dir=self.dir, out=out.append, err=out.append,
                              config={**self.cfg, "_resolved": {"history_db": str(self.hist)},
                                      "dashboard": {"url": "https://dash.example.com/traffic/"
                                                           "a.example.com/"}})
        self.day("2026-10-01", 820)
        self.db.commit()
        got = usage_alerts.after_run([ctx], "run-daily", send=self.send)
        self.assertEqual([a["mark"] for a in got], [80])
        self.assertEqual(len(self.mailed()), 2)
        self.assertIn("reached 80%", out[0])
        self.assertNotIn("@", out[0])
        off = SimpleNamespace(**{**vars(ctx), "config": {**ctx.config, "saas": {}}})
        self.assertEqual(usage_alerts.after_run([off], "run-daily", send=self.send), [])


class Summary(Case):
    def test_the_plan_block_has_the_percent_the_mark_and_the_reset_day(self):
        self.day("2026-10-01", 912)
        got = limits.summary(self.db, self.org["id"], self.cfg, self.hist)["usage"]
        self.assertEqual((got["requests"], got["percent"], got["mark"], got["resets_on"]),
                         (912, 91, 90, "1 November 2026"))
        self.day("2026-10-01", 799)
        got = limits.summary(self.db, self.org["id"], self.cfg, self.hist)["usage"]
        self.assertEqual((got["percent"], got["mark"]), (79, None))

    def test_marks_are_whole_and_rounded_down(self):
        self.assertEqual(usage_alerts.passed(799, 1000), [])
        self.assertEqual(usage_alerts.passed(800, 1000), [80])
        self.assertEqual(usage_alerts.passed(1000, 1000), [80, 90, 100])
        self.assertEqual(usage_alerts.percent(999, 1000), 99)
        self.assertIsNone(usage_alerts.percent(None, 1000))
        self.assertEqual(usage_alerts.resets_on("2026-12"), "1 January 2027")


if __name__ == "__main__":
    unittest.main()
