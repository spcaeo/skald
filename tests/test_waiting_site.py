"""A site added from the dashboard before its first log line: run-daily and
live report it as "waiting for its first log lines", never as a failure of
the whole install (no non-zero exit, so no failure mail). Once lines arrive
it is collected, audited and checked like any site; a config-file site with
no log is still a failure."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import CHROME, SECRETS, UTC, Sandbox, day_lines, line  # noqa: E402

from skald import accounts  # noqa: E402
from skald.accounts import site_configs  # noqa: E402
from skald.store import History  # noqa: E402

SHOP = "shop.example.com"
D1, D2, D3 = date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)
WAITING = f"{SHOP}: waiting for its first log lines"


def shop_lines(day: date, n: int = 4) -> list[str]:
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    return [line(noon + timedelta(minutes=i), f"203.0.113.{80 + i}", "/cart", CHROME,
                 host=SHOP) for i in range(n)]


class FreshDashboardSite(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        env = mock.patch.dict("os.environ", SECRETS)
        env.start()
        self.addCleanup(env.stop)
        db = accounts.connect(self.box.root / "accounts.sqlite")
        try:
            org = accounts.create_org(db, "Org", "cli")
            site_configs.create(db, org["id"], SHOP, "cli")
        finally:
            db.close()
        self.box.log(day_lines(D1, 3) + day_lines(D2, 3) + day_lines(D3, 3))
        self.shop_state = self.box.root / "sites" / SHOP

    def runs(self, folder: Path) -> dict:
        return json.loads((folder / "runs.json").read_text())["run-daily"]

    def test_run_daily_reports_waiting_and_exits_zero(self):
        code, out, err = self.box.run("--today", "2026-10-06", "run-daily", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn(WAITING, out)
        self.assertNotIn("stopped at", err)
        self.assertNotIn("FIGURES DO NOT RECONCILE", err)
        self.assertEqual(self.runs(self.box.root)["last_outcome"], "ok")
        self.assertEqual(self.runs(self.shop_state)["last_outcome"], "waiting")
        self.assertEqual(self.runs(self.shop_state)["last_exit"], 0)
        with History(self.box.db) as h:
            self.assertIsNotNone(h.first_day("example.com"))
            self.assertIsNone(h.first_day(SHOP))       # nothing stored, no zeroes
        # The switcher lists it, with no day yet.
        sites = json.loads((self.box.root / "www" / "sites.json").read_text())["sites"]
        shop = [s for s in sites if s["name"] == SHOP][0]
        self.assertIsNone(shop["last_day"])
        self.assertTrue(shop["waiting"])

    def test_live_reports_waiting(self):
        code, out, err = self.box.run("--today", "2026-10-06", "live")
        self.assertEqual(code, 0, err)
        self.assertIn(WAITING, out)
        live_runs = json.loads((self.shop_state / "runs.json").read_text())
        self.assertNotIn("alerts", live_runs, "no alerts for a site with no line yet")
        self.assertIn("alerts", json.loads((self.box.root / "runs.json").read_text()))

    def test_once_lines_arrive_it_is_any_site(self):
        folder = self.box.root / "ingest" / SHOP
        folder.mkdir(parents=True)
        # Lines from the 6th only: the run on the 6th still waits (none in
        # yesterday's window), the run on the 7th collects and audits the 6th.
        (folder / "access.log").write_text("".join(shop_lines(D2)))
        code, out, err = self.box.run("--today", "2026-10-06", "run-daily", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn(WAITING, out)
        code, out, err = self.box.run("--today", "2026-10-07", "run-daily", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertNotIn(WAITING, out)
        self.assertIn("audit ok: 2026-10-06: 4 requests", out)
        self.assertEqual(self.runs(self.shop_state)["last_outcome"], "ok")
        with History(self.box.db) as h:
            self.assertEqual(h.first_day(SHOP), D2)
        code, out, err = self.box.run("--today", "2026-10-07", "live")
        self.assertNotIn(WAITING, out)
        # From now on a day with no line is a failure, as for any site.
        code, out, err = self.box.run("--today", "2026-10-08", "run-daily", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("nothing parsed", err)
        self.assertEqual(self.runs(self.shop_state)["last_outcome"], "failed")

    def test_a_config_file_site_with_no_log_still_fails(self):
        (self.box.root / "other.yml").write_text(
            "site:\n  name: other.example\n  hosts: [other.example]\n"
            "logs:\n  base: other.log\n")
        self.box.config.write_text(self.box.config.read_text() + "sites:\n  - other.yml\n")
        code, out, err = self.box.run("--today", "2026-10-06", "run-daily", "--dry-run")
        self.assertEqual(code, 1)
        self.assertIn(WAITING, out)                     # the dashboard site still waits
        self.assertIn("nothing parsed", err)


if __name__ == "__main__":
    unittest.main()
