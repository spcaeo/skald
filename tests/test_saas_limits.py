"""Phase 5a, plans and limits (skald/saas/): the accounts schema 3
columns, the plans in the config, an organisation's limits, members and
sites it may add, the retention cap, the month's usage from the history (and
its second count, audit_usage.py), the grace period and saas switched off.

Addresses are example.com; no real secret anywhere.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402

from skald import accounts, audit_usage, saas, settings_store  # noqa: E402
from skald.accounts import db as base  # noqa: E402
from skald.saas import limits, plans  # noqa: E402
from skald.store import SCHEMA as HISTORY_SCHEMA  # noqa: E402

PLANS = {"free": {"sites": 1, "requests_month": 1000, "retention_days_max": 90, "members": 2,
                  "trial_days": 0},
         "pro": {"sites": 5, "requests_month": 100000, "retention_days_max": 400,
                 "members": 10, "price_id": "price_pro_test", "trial_days": 14,
                 "label": "Pro, 9 a month"}}


def config(**saas_extra) -> dict:
    return {"access": {"mode": "sessions"},
            "saas": {"enabled": True, "plans": PLANS, "default_plan": "pro", **saas_extra}}


def history(path: Path, rows) -> None:
    """rows: (site, day, hits, {group: hits})."""
    db = sqlite3.connect(path)
    db.executescript(HISTORY_SCHEMA)
    for site, day, hits, groups in rows:
        db.execute("INSERT INTO days (site, day, timezone, collected_at, verified, parsed, hits, "
                   "other_hosts, cited_visits) VALUES (?, ?, 'UTC', 'x', 1, ?, ?, 0, 0)",
                   (site, day, hits, hits))
        for grp, n in groups.items():
            db.execute("INSERT INTO groups (site, day, grp, hits, views, visits, probes) "
                       "VALUES (?, ?, ?, ?, 0, 0, 0)", (site, day, grp, n))
    db.commit()
    db.close()


class Schema(unittest.TestCase):
    def test_a_version_two_file_gains_the_plan_columns_and_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "accounts.sqlite"
            old = sqlite3.connect(path)
            two = base.SCHEMA.replace(
                ", plan TEXT, plan_status TEXT NOT NULL DEFAULT 'none',\n"
                "  trial_ends_at TEXT, stripe_customer TEXT, stripe_subscription TEXT,\n"
                "  created_via TEXT NOT NULL DEFAULT 'cli', past_due_since TEXT", "")
            two = two.split("CREATE TABLE IF NOT EXISTS signups")[0]
            old.executescript(two)
            old.execute("INSERT INTO meta VALUES ('schema_version', '2')")
            old.execute("INSERT INTO orgs (name, slug, created_at) VALUES ('A', 'a', 'x')")
            old.commit()
            self.assertNotIn("plan", [r[1] for r in old.execute("PRAGMA table_info(orgs)")])
            old.close()
            db = base.connect(path)
            try:
                self.assertEqual(base.schema_version(db), base.SCHEMA_VERSION)
                row = db.execute("SELECT plan, plan_status, created_via FROM orgs").fetchone()
                self.assertEqual(tuple(row), (None, "none", "cli"))
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master")}
                self.assertTrue({"signups", "billing_events"} <= tables)
                cols = [r[1] for r in db.execute("PRAGMA table_info(signups)")]
                self.assertEqual(cols, ["token_hash", "email", "created_at", "expires_at",
                                        "used_at", "ip_hash"])
            finally:
                db.close()


class Config(unittest.TestCase):
    def test_off_by_default_and_needs_sessions_mode(self):
        self.assertFalse(saas.enabled({}))
        self.assertFalse(saas.enabled({"saas": {"enabled": True}}))
        self.assertTrue(saas.enabled(config()))
        self.assertFalse(saas.enabled({"access": {"mode": "sessions"},
                                       "saas": {"enabled": "false"}}))
        self.assertFalse(saas.signup_on(config()))
        self.assertTrue(saas.signup_on(config(signup=True)))
        self.assertFalse(saas.billing_on(config()))
        self.assertTrue(saas.billing_on(config(billing="stripe")))
        self.assertEqual(saas.grace_days(config()), 7)
        self.assertEqual(saas.grace_days(config(grace_days="3")), 3)

    def test_plans_as_a_mapping_or_as_the_small_parsers_flow_list(self):
        got = plans.plans(config())
        self.assertEqual(got["pro"]["members"], 10)
        self.assertEqual(got["pro"]["price_id"], "price_pro_test")
        self.assertIsNone(got["free"]["price_id"])
        flat = {"access": {"mode": "sessions"}, "saas": {"enabled": True, "plans": [
            {"name": "free", "sites": "1", "requests_month": "1000", "members": "unlimited"}]}}
        got = plans.plans(flat)
        self.assertEqual(got["free"]["sites"], 1)
        self.assertIsNone(got["free"]["members"])          # no limit
        self.assertIsNone(got["free"]["retention_days_max"])
        self.assertEqual(plans.default_plan(flat), "free")  # the first, when none is named
        self.assertEqual(plans.plan_by_price(config(), "price_pro_test"), "pro")
        with self.assertRaises(ValueError):
            plans.plans({"saas": {"plans": {"x": {"sites": "many"}}}})


class Limits(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        self.cfg = config()

    def member(self, email, role="viewer"):
        user = accounts.create_user(self.db, email, "x")
        accounts.add_member(self.db, self.org["id"], user["id"], role, "cli")
        return user

    def test_an_org_without_a_plan_has_no_limits(self):
        self.assertIsNone(limits.limits_for(self.db, self.org["id"], self.cfg))
        self.assertEqual(limits.can_add_member(self.db, self.org["id"], self.cfg), (True, ""))
        self.assertIsNone(limits.retention_cap(self.db, self.org["id"], self.cfg))

    def test_saas_off_means_no_limits_even_with_a_plan(self):
        plans.set_plan(self.db, self.org["id"], "free", "active", "cli")
        off = {"access": {"mode": "sessions"}, "saas": {"enabled": False, "plans": PLANS}}
        self.assertIsNone(limits.limits_for(self.db, self.org["id"], off))
        for _ in range(3):
            self.member(f"p{_}@example.com")
        self.assertTrue(limits.can_add_member(self.db, self.org["id"], off)[0])
        self.assertTrue(limits.can_add_site(self.db, self.org["id"], off)[0])
        self.assertIsNone(limits.read_only(self.db, self.org["id"], off))
        self.assertEqual(limits.over_limit(self.db, self.org["id"], off), [])

    def test_members_count_open_invites_too(self):
        plans.set_plan(self.db, self.org["id"], "free", "active", "cli")
        self.member("owner@example.com", "owner")
        self.assertTrue(limits.can_add_member(self.db, self.org["id"], self.cfg)[0])
        accounts.invite(self.db, self.org["id"], "new@example.com", "viewer", "cli")
        ok, why = limits.can_add_member(self.db, self.org["id"], self.cfg)
        self.assertFalse(ok)
        self.assertIn("2 members", why)
        # Resending the open invite is not one more.
        self.assertTrue(limits.can_add_member(self.db, self.org["id"], self.cfg,
                                              email="new@example.com")[0])
        self.tick(days=8)                                 # an expired invite is not counted
        self.assertTrue(limits.can_add_member(self.db, self.org["id"], self.cfg)[0])

    def test_sites(self):
        plans.set_plan(self.db, self.org["id"], "free", "active", "cli")
        self.assertTrue(limits.can_add_site(self.db, self.org["id"], self.cfg)[0])
        accounts.assign_site(self.db, "a.example.com", self.org["id"], "cli")
        ok, why = limits.can_add_site(self.db, self.org["id"], self.cfg)
        self.assertFalse(ok)
        self.assertIn("1 site", why)

    def test_retention_cap_and_the_settings_check(self):
        plans.set_plan(self.db, self.org["id"], "free", "active", "cli")
        cap = limits.retention_cap(self.db, self.org["id"], self.cfg)
        self.assertEqual(cap, 90)
        self.assertEqual(settings_store.validate("report.retention_days", 90, cap=cap), 90)
        with self.assertRaises(settings_store.Invalid) as got:
            settings_store.validate("report.retention_days", 91, cap=cap)
        self.assertIn("90", str(got.exception))
        # A key whose own floor is above the cap keeps its floor.
        self.assertEqual(settings_store.validate("beacon.keep_days", 30, cap=10), 30)
        # Not a retention key: the cap does not apply.
        self.assertEqual(settings_store.validate("backup.daily", 14, cap=1), 14)

    def test_an_unknown_plan_name_takes_the_default_plans_limits(self):
        plans.set_plan(self.db, self.org["id"], "gone", "active", "cli")
        got = limits.limits_for(self.db, self.org["id"], self.cfg)
        self.assertEqual((got["plan"], got["known"], got["members"]), ("gone", False, 10))

    def test_trial(self):
        plans.start_trial(self.db, self.org["id"], self.cfg, "cli")
        state = plans.org_state(self.db, self.org["id"])
        self.assertEqual((state["plan"], state["plan_status"], state["created_via"]),
                         ("pro", "trialing", "signup"))
        self.assertEqual(state["trial_ends_at"], "2026-10-25T14:00:00Z")
        self.assertEqual(limits.limits_for(self.db, self.org["id"], self.cfg)["trial_days_left"],
                         14)
        free = config(default_plan="free")
        other = accounts.create_org(self.db, "Beta", "cli")
        plans.start_trial(self.db, other["id"], free, "cli")
        self.assertEqual(plans.org_state(self.db, other["id"])["plan_status"], "active")

    def test_grace_period_then_read_only_never_deleted(self):
        plans.set_plan(self.db, self.org["id"], "pro", "active", "stripe")
        plans.set_plan(self.db, self.org["id"], "pro", "past_due", "stripe")
        self.assertEqual(plans.org_state(self.db, self.org["id"])["past_due_since"],
                         "2026-10-11T14:00:00Z")
        self.tick(days=7)
        self.assertIsNone(limits.read_only(self.db, self.org["id"], self.cfg))
        # Another failed payment does not move the start of the grace period.
        plans.set_plan(self.db, self.org["id"], "pro", "past_due", "stripe")
        self.tick(seconds=1)
        self.assertIn("payment", limits.read_only(self.db, self.org["id"], self.cfg))
        plans.set_plan(self.db, self.org["id"], "pro", "active", "stripe")
        self.assertIsNone(limits.read_only(self.db, self.org["id"], self.cfg))
        self.assertIsNone(plans.org_state(self.db, self.org["id"])["past_due_since"])
        plans.set_plan(self.db, self.org["id"], "pro", "canceled", "stripe")
        self.assertIsNotNone(limits.read_only(self.db, self.org["id"], self.cfg))
        self.assertIn("billing.plan", self.audit_actions(self.org["id"]))

    def test_an_ended_trial_locks_only_with_billing_on(self):
        plans.start_trial(self.db, self.org["id"], self.cfg, "cli")
        self.tick(days=14 + 8)
        self.assertIsNone(limits.read_only(self.db, self.org["id"], self.cfg))
        self.assertIn("trial", limits.read_only(self.db, self.org["id"],
                                                config(billing="stripe")))

    def test_bad_status_is_refused(self):
        with self.assertRaises(ValueError):
            plans.set_plan(self.db, self.org["id"], "pro", "late", "cli")


class Usage(AccountsCase):
    def setUp(self):
        super().setUp()
        self.hist = self.dir / "history.sqlite"
        history(self.hist, [
            ("a.example.com", "2026-10-01", 600, {"people": 400, "crawlers": 200}),
            ("a.example.com", "2026-10-02", 500, {"people": 500}),
            ("a.example.com::ca", "2026-10-02", 50, {"people": 50}),    # a view's row
            ("a.example.com", "2026-09-30", 999, {"people": 999}),      # last month
            ("b.example.com", "2026-10-01", 7, {"people": 7}),           # another org
        ])

    def test_the_months_requests_from_the_daily_totals(self):
        got = limits.usage(self.hist, ["a.example.com"], "2026-10")
        self.assertEqual((got["requests"], got["days"], got["withheld"]), (1100, 2, None))
        both = limits.usage(self.hist, ["a.example.com", "b.example.com"], "2026-10")
        self.assertEqual(both["requests"], 1107)

    def test_the_second_road_agrees(self):
        self.assertEqual(audit_usage.recount(self.hist, ["a.example.com"], "2026-10"),
                         (1100, 2))

    def test_no_day_recorded_is_unknown_not_zero(self):
        got = limits.usage(self.hist, ["a.example.com"], "2026-11")
        self.assertEqual((got["requests"], got["days"]), (None, 0))
        self.assertIsNone(limits.usage(self.dir / "none.sqlite", ["x.example"], "2026-10")
                          ["requests"])

    def test_a_disagreement_is_withheld(self):
        db = sqlite3.connect(self.hist)
        db.execute("UPDATE groups SET hits = 401 WHERE grp = 'people' AND day = '2026-10-01'")
        db.commit()
        db.close()
        got = limits.usage(self.hist, ["a.example.com"], "2026-10")
        self.assertIsNone(got["requests"])
        self.assertIn("do not add up", got["withheld"])

    def test_over_the_request_limit(self):
        org = accounts.create_org(self.db, "Alpha", "cli")
        accounts.assign_site(self.db, "a.example.com", org["id"], "cli")
        cfg = config()
        plans.set_plan(self.db, org["id"], "free", "active", "cli")
        self.assertEqual(limits.over_limit(self.db, org["id"], cfg, self.hist), ["requests_month"])
        got = limits.summary(self.db, org["id"], cfg, self.hist)
        self.assertEqual(got["name"], "free")
        self.assertEqual(got["usage"]["requests"], 1100)
        self.assertEqual(got["limits"]["requests_month"], 1000)
        self.assertEqual(got["over"], ["requests_month"])
        self.assertFalse(got["read_only"])
        plans.set_plan(self.db, org["id"], "pro", "active", "cli")
        self.assertEqual(limits.over_limit(self.db, org["id"], cfg, self.hist), [])


if __name__ == "__main__":
    unittest.main()
