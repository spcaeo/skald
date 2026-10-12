"""Phase 5a commands (saas/cli.py): `skald plan list`, `plan set ORG PLAN
[--status]`, `usage [--org] [--month]` and `billing secret key|webhook`,
run through their own argparse parser on a made-up context.
Addresses are example.com; no real secret anywhere.
"""
from __future__ import annotations

import argparse
import importlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accounts_support import AccountsCase  # noqa: E402
from test_saas_limits import config, history  # noqa: E402

from skald import accounts  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.saas import cli, plans  # noqa: E402


class Commands(AccountsCase):
    def setUp(self):
        super().setUp()
        self.org = accounts.create_org(self.db, "Alpha", "cli")
        accounts.assign_site(self.db, "a.example.com", self.org["id"], "cli")
        self.hist = self.dir / "history.sqlite"
        history(self.hist, [("a.example.com", "2026-10-01", 1500, {"people": 1500})])
        self.lines, self.errors = [], []
        self.cfg = config()

    def run_cli(self, *argv) -> int:
        parser = argparse.ArgumentParser()
        cli.add_command(parser.add_subparsers(dest="cmd", required=True))
        args = parser.parse_args(list(argv))
        ctx = SimpleNamespace(args=args, config=self.cfg, db_path=self.hist, live_dir=self.dir,
                              out=self.lines.append, err=self.errors.append)
        return args.run(ctx)

    def test_registers_by_its_module_name(self):
        module = importlib.import_module(".saas.cli", "skald")
        self.assertTrue(callable(module.add_command))

    def test_plan_set_and_list(self):
        self.assertEqual(self.run_cli("plan", "set", "alpha", "free"), 0)
        self.assertEqual(plans.org_state(self.db, self.org["id"])["plan"], "free")
        self.assertEqual(self.run_cli("plan", "set", "Alpha", "pro", "--status", "past_due"), 0)
        state = plans.org_state(self.db, self.org["id"])
        self.assertEqual((state["plan"], state["plan_status"]), ("pro", "past_due"))
        self.assertEqual(self.run_cli("plan", "list"), 0)
        text = "\n".join(self.lines)
        self.assertIn("pro (default): sites 5", text)
        self.assertIn("alpha: pro past_due", text)
        self.assertEqual(self.run_cli("plan", "set", "alpha", "none"), 0)
        self.assertIsNone(plans.org_state(self.db, self.org["id"])["plan"])
        self.assertIn("billing.plan", self.audit_actions(self.org["id"]))

    def test_plan_set_refuses_unknown_names(self):
        self.assertEqual(self.run_cli("plan", "set", "nobody", "free"), 1)
        self.assertEqual(self.run_cli("plan", "set", "alpha", "gold"), 1)
        with self.assertRaises(SystemExit), mock.patch.object(sys, "stderr", io.StringIO()):
            self.run_cli("plan", "set", "alpha", "free", "--status", "late")

    def test_trial_days(self):
        self.assertEqual(self.run_cli("plan", "set", "alpha", "pro", "--trial-days", "3"), 0)
        state = plans.org_state(self.db, self.org["id"])
        self.assertEqual((state["plan_status"], state["trial_ends_at"]),
                         ("trialing", "2026-10-14T14:00:00Z"))

    def test_usage(self):
        plans.set_plan(self.db, self.org["id"], "free", "active", "cli")
        self.assertEqual(self.run_cli("usage", "--month", "2026-10"), 0)
        self.assertIn("alpha 2026-10: 1,500 requests over 1 days; limit 1,000", self.lines[0])
        self.assertIn("over: requests_month", self.lines[1])
        self.lines.clear()
        self.assertEqual(self.run_cli("usage", "--org", "alpha", "--month", "2026-11"), 0)
        self.assertIn("no day recorded", self.lines[0])
        self.assertEqual(self.run_cli("usage", "--month", "October"), 2)

    def test_billing_secret_goes_to_secrets_json_and_is_not_printed(self):
        with mock.patch.object(sys, "stdin", io.StringIO("sk_test_madeup\n")):
            self.assertEqual(self.run_cli("billing", "secret", "key"), 0)
        self.assertEqual(secrets_store.load(self.dir / "secrets.json")["billing/stripe_key"],
                         "sk_test_madeup")
        self.assertNotIn("sk_test_madeup", "\n".join(self.lines + self.errors))


if __name__ == "__main__":
    unittest.main()
