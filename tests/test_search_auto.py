"""Search Console connects by itself (2.44: search/auto.py), the owner's case of 27 Oct:
the agent reported the domain property, Skald's robot was on the address property, and
Google refused the connect.

  - Connect (and Apply) asks Google which properties the robot sees and uses the one that
    covers the site, saying so in one line;
  - none yet: the answer is "waiting" in plain words, never a failure; Skald keeps the want,
    looks again (at most once a minute unless pressed) and connects once Google shows it,
    with the 16-month history;
  - sites/arrived "search" says the same words, and a press looks now.
"""
from __future__ import annotations

import dataclasses
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import search_support as ss  # noqa: E402
import test_search_api as tsa  # noqa: E402
from auth_support import A  # noqa: E402

from skald import settings_store  # noqa: E402
from skald.search import auto, state  # noqa: E402

T = f"/traffic/{A}/"
MAKE_JOB = auto._job


class Auto(tsa.Base):
    def setUp(self):
        super().setUp()
        self.admin(email="admin@example.com")
        self.do("googlekey", {"key": ss.service_key()}, "admin@example.com")
        self.started = []
        patch = mock.patch.object(auto, "spawn", lambda cp, folder, site, args: self.started.append((site, args)) or True)
        patch.start()
        self.addCleanup(patch.stop)

    def job(self):
        return dataclasses.replace(MAKE_JOB(self.config, None, self.live, A), api=self.engines.api())

    def setting(self):
        db = self.db()
        try:
            return settings_store.explain(self.config, A, db)["search.google_property"]["value"]
        finally:
            db.close()

    def run_auto(self, force=True):
        db = self.db()
        try:
            return auto.run(self.config, None, self.live, db, A, force=force, job=self.job())
        finally:
            db.close()

    def test_the_property_the_robot_sees_is_used_and_said(self):
        self.engines.props = {f"https://{A}/": "siteRestrictedUser"}
        got = self.do("connect", {"engine": "google", "source": f"sc-domain:{A}", "backfill_months": 16})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["source"], f"https://{A}/")
        self.assertEqual(got.json["note"], f"Your agent named sc-domain:{A}, but Skald's robot is on "
                                           f"https://{A}/: Skald uses that one.")
        self.assertEqual(self.setting(), f"https://{A}/")

    def test_not_visible_yet_waits_then_connects_by_itself(self):
        self.engines.props = {"https://www.beta.example/": "siteFullUser"}
        got = self.do("connect", {"engine": "google", "source": f"sc-domain:{A}", "backfill_months": 16})
        self.assertEqual(got.status, 200, got.json)
        self.assertTrue(got.json["waiting"])
        self.assertTrue(got.json["words"].startswith(
            f"Waiting for Google: Skald's robot address is not on a {A} property yet."))
        self.assertIsNone(self.setting(), "nothing saved while Google does not show it")
        self.assertEqual(state.load(self.live, A)["auto"]["state"], "waiting")
        self.assertEqual(self.get().json["auto"]["state"], "waiting", "the page reads it")
        part = self.run_auto()
        self.assertEqual(part["state"], "waiting")
        # Not pressed and looked a moment ago: no new look.
        calls = len(self.engines.calls)
        self.assertEqual(self.run_auto(force=False)["state"], "waiting")
        self.assertEqual(len(self.engines.calls), calls, "at most one look a minute")
        # The person adds the robot: the next look connects, with the history.
        self.engines.props[f"sc-domain:{A}"] = "siteRestrictedUser"
        part = self.run_auto()
        self.assertEqual(part["state"], "connected")
        self.assertEqual(part["words"], "Connected. Skald is getting Google's history: the last 16 months.")
        self.assertEqual(self.setting(), f"sc-domain:{A}")
        self.assertEqual(self.started[-1], (A, ["search-console", "sync", "--backfill-months", "16"]))
        self.assertEqual(state.load(self.live, A)["google"]["backfill"]["state"], "queued")
        self.assertEqual(self.run_auto()["state"], "connected", "done: nothing more")

    def test_the_test_button_says_waiting_for_google(self):
        self.engines.props = {}
        auto.want(self.live, A, f"sc-domain:{A}", "ai-agent")
        with mock.patch.object(auto, "_job", lambda *a: self.job()):
            cookie, csrf = self.session("owner@example.com")
            got = self.post(T + "sites/arrived", {"site": A, "what": "search", "press": True}, cookie, csrf)
            self.assertEqual(got.status, 200, got.json)
            t = got.json["test"]
            self.assertEqual(t["verdict"], "wait")
            self.assertTrue(t["head"].startswith("Waiting for Google:"), t)
            self.engines.props = {f"sc-domain:{A}": "siteRestrictedUser"}
            t = self.post(T + "sites/arrived", {"site": A, "what": "search", "press": True}, cookie, csrf).json["test"]
            self.assertEqual(t["verdict"], "ok")
            self.assertTrue(t["head"].startswith("Connected."), t["head"])

    def test_it_stops_looking_after_a_week(self):
        auto.want(self.live, A, None, "ai-agent")
        old = (datetime.now(timezone.utc) - timedelta(days=auto.KEEP_DAYS + 1)).isoformat()
        state.update(self.live, A, "auto", since=old)
        self.assertEqual(self.run_auto()["state"], "gave_up")

    def test_the_agents_report_gets_what_skald_sees(self):
        import re
        from skald.kit import agent
        cookie, csrf = self.session("owner@example.com")
        got = self.post(T + "sites/agentlink", {"site": A, "jobs": ["search"]}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        code = re.search(r"use code ([A-Za-z0-9_-]{43}) ", got.json["line"]).group(1)
        self.engines.props = {f"https://{A}/": "siteRestrictedUser"}
        report = {"search": {"google_property": f"sc-domain:{A}", "robot_added": True}}
        with mock.patch.object(auto, "_job", lambda *a: self.job()):
            said = agent._search_now(self.live, code, report, self.config, None)
        self.assertEqual(said["search"]["state"], "connected", said)
        self.assertIn(f"Skald's robot is on https://{A}/", said["search"]["note"])
        self.assertEqual(self.setting(), f"https://{A}/")
        self.assertEqual(agent._search_now(self.live, code, {}, self.config, None), {}, "no property: nothing")


if __name__ == "__main__":
    unittest.main()
