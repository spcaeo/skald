"""The usage alerts in the dashboard, over real HTTP: /me's plan block carries this
month's percent, the mark (80, 90, 100) and the reset day; GET billing answers owners and
admins (admins read only); then tests/js/billing-usage.mjs draws the banner and the bar
from those answers (an owner and an admin see them, a viewer sees nothing).

Addresses are example.com; no real secret anywhere.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, Server  # noqa: E402

from skald.saas import plans  # noqa: E402
from skald.store import SCHEMA as HISTORY_SCHEMA  # noqa: E402

T = f"/traffic/{A}/"
PLANS = {"small": {"sites": 5, "members": 10, "requests_month": 1000, "price_id": "price_x"}}


class UsagePage(Server):
    def setUp(self):
        super().setUp()
        self.config["saas"] = {"enabled": True, "billing": "stripe", "plans": PLANS,
                               "default_plan": "small"}
        db = self.db()
        try:
            plans.set_plan(db, self.alpha["id"], "small", "active", "cli")
        finally:
            db.close()
        h = sqlite3.connect(self.live / "history.sqlite")
        h.executescript(HISTORY_SCHEMA)
        h.execute("INSERT INTO days (site, day, timezone, collected_at, verified, parsed, hits, "
                  "other_hosts, cited_visits) VALUES (?, '2026-10-02', 'UTC', 'x', 1, 850, 850, "
                  "0, 0)", (A,))
        h.execute("INSERT INTO groups (site, day, grp, hits, views, visits, probes) "
                  "VALUES (?, '2026-10-02', 'people', 850, 0, 0, 0)", (A,))
        h.commit()
        h.close()

    def answers(self) -> dict:
        out = {}
        for who in ("owner", "admin", "viewer"):
            cookie, _ = self.session(f"{who}@example.com")
            me = self.call("GET", T + "me", cookie=cookie).json
            got = self.call("GET", T + "billing", cookie=cookie)
            out[who] = {"me": me, "billing": got.json if got.status == 200 else None,
                        "billing_status": got.status}
        return out

    def test_me_has_the_percent_and_the_mark(self):
        got = self.answers()
        usage = got["owner"]["me"]["plan"]["usage"]
        self.assertEqual((usage["requests"], usage["percent"], usage["mark"],
                          usage["resets_on"]), (850, 85, 80, "1 November 2026"))
        self.assertEqual(got["admin"]["billing_status"], 200)
        self.assertEqual(got["viewer"]["billing_status"], 403)
        self.config["saas"]["usage_alerts"] = False
        cookie, _ = self.session()
        usage = self.call("GET", T + "me", cookie=cookie).json["plan"]["usage"]
        self.assertEqual((usage["percent"], usage["mark"]), (85, None))

    def test_the_page_draws_the_banner_and_the_bar(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        got = self.answers()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "answers.json"
            path.write_text(json.dumps(got))
            js = Path(__file__).resolve().parent / "js" / "billing-usage.mjs"
            done = subprocess.run(["node", str(js)], capture_output=True, text=True,
                                  timeout=60, env={**os.environ, "BILLING_JSON": str(path)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("billing-usage: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
