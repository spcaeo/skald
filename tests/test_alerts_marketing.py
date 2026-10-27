"""Marketing alerts (skald/alerts_marketing.py): each rule on its own, with its
switch, its threshold and its silence when the figure is not there.

  * tool_stopped: a connected tool with no good answer for 26 hours, one alert per
    tool; a tool answering, paused or never connected: none
  * leads_drop: the dashboard's leads (mail_html._leads, the same function the mails
    and the Overview tile use) over the last 7 whole days against the 7 before;
    under the minimum, or not recorded (None): silent
  * bookings_drop: Calendly's own booked_7d against booked_prev_7d, read through
    yourtools.api (only while the tool's recheck matches); withheld: silent
  * ga4_log_gap: GA4's sessions against the log's visits over GA4's own dates, off
    by default; "different counting", never "wrong"; a day of the log not whole or
    not verified: silent
  * the daily rules are worked out once per day and settings; tool_stopped every run
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import alerts, alerts_marketing as M, mail_html, settings_store  # noqa: E402
from skald.classify import Group  # noqa: E402
from skald.yourtools import conn, store, sync  # noqa: E402

from test_yourtools_calendly import TOKEN as CAL_TOKEN, FakeCalendly  # noqa: E402
from test_yourtools_ga4 import PROP, Google, service_key  # noqa: E402

SITE = "example.com"
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
TZ = ZoneInfo("America/New_York")


@dataclass
class People:
    visits: int


@dataclass
class Totals:
    groups: dict = field(default_factory=dict)


@dataclass
class Period:
    first: date
    last: date
    totals: Totals
    complete: bool = True
    unmeasured_visits: int = 0


class FakeHistory:
    """period() as store.History gives it: whole verified days, the log's visits."""

    def __init__(self, visits, complete=True):
        self.visits, self.complete, self.asked = visits, complete, []

    def period(self, site, first, last):
        self.asked.append((first, last))
        return Period(first, last, Totals({Group.PEOPLE: People(self.visits)}), self.complete)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}, "history": {"db": str(self.folder / "h.sqlite")},
                       "conversions": {"identity": "full"}, "alerts": {}}
        self.leads = {}
        real = mail_html._leads
        mail_html._leads = lambda config, history, site, tz, first, last: self.leads.get(first)
        self.addCleanup(setattr, mail_html, "_leads", real)

    def cfg(self, **over):
        self.config["alerts"].update(over)
        return M.settings(self.config)

    def sync(self, opener):
        job = sync.Job(self.config, SITE, self.folder, NOW, lambda *a: None, lambda *a: None, opener=opener,
                       sleep=lambda s: None, send=lambda *a: None)
        return sync.run(job)


class Settings(unittest.TestCase):
    def test_defaults_and_switches(self):
        got = M.settings({})
        self.assertEqual((got["tool_stopped"], got["leads_drop"], got["bookings_drop"],
                          got["ga4_log_gap"]), (True, True, True, False))
        self.assertEqual(M.settings({"alerts": {"ga4_log_gap": "yes", "ga4_gap_factor": 1,
                                                "leads_drop_percent": 300}})
                         ["ga4_gap_factor"], 2)
        for cause in M.CAUSES:
            key = settings_store.SCHEMA[alerts.SETTING[cause]]
            self.assertEqual(key.config, ("alerts", cause))
            self.assertEqual(key.default, cause != "ga4_log_gap")
        self.assertEqual([r["cause"] for r in M.rules(M.settings({}))], list(M.CAUSES))
        self.assertIn("not an error", M.rules(M.settings({}))[3]["threshold"])


class ToolStopped(Base):
    def test_one_alert_per_stopped_tool(self):
        sync.connect(self.config, self.folder, SITE, "calendly", {}, "cli", key=CAL_TOKEN)
        self.assertEqual(M.stopped(self.config, self.folder, SITE, NOW), [])      # waiting
        conn.update(self.folder, SITE, "calendly", last_try="2026-10-27T02:00:00+00:00",
                    last_ok="2026-10-25T23:00:00+00:00", ok=False,
                    error="Calendly refused the token: it is expired or was revoked.")
        got = M.stopped(self.config, self.folder, SITE, NOW)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["cause"], got[0]["subject"], got[0]["figure"]),
                         ("tool_stopped", "calendly", 28))
        self.assertIn("Skald's own counts are not touched", got[0]["detail"])
        self.assertIn("expired or was revoked", got[0]["detail"])
        self.assertNotIn(CAL_TOKEN, str(got))
        conn.update(self.folder, SITE, "calendly", last_ok="2026-10-26T23:00:00+00:00")
        self.assertEqual(M.stopped(self.config, self.folder, SITE, NOW), [])      # 4 hours
        conn.update(self.folder, SITE, "calendly", on=False, last_ok=None)
        self.assertEqual(M.stopped(self.config, self.folder, SITE, NOW), [])      # paused


class LeadsDrop(Base):
    day = date(2026, 10, 26)

    def week(self, now_n, before_n):
        self.leads = {date(2026, 10, 20): now_n, date(2026, 10, 13): before_n}

    def test_a_fall_below_the_percent(self):
        self.week(3, 10)
        got = M.leads(self.cfg(), self.config, None, SITE, TZ, self.day)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["title"], got[0]["figure"], got[0]["threshold"]),
                         ("Leads down 70%: 3 in 7 days", 3, 5.0))
        self.assertIn("20 Oct to 26 Oct against 10", got[0]["detail"])

    def test_silent_at_the_percent_under_the_minimum_or_not_recorded(self):
        for now_n, before_n in ((5, 10), (0, 4), (None, 10), (3, None)):
            self.week(now_n, before_n)
            self.assertEqual(M.leads(self.cfg(), self.config, None, SITE, TZ, self.day), [],
                             (now_n, before_n))
        self.week(0, 4)
        self.assertEqual(len(M.leads(self.cfg(leads_drop_minimum=3), self.config, None, SITE,
                                     TZ, self.day)), 1)


class BookingsDrop(Base):
    def calendly(self):
        sync.connect(self.config, self.folder, SITE, "calendly", {}, "cli", key=CAL_TOKEN)
        self.assertEqual(self.sync(FakeCalendly()), 0)

    def test_calendly_figures_compared(self):
        self.calendly()                     # booked_7d 3, booked_prev_7d 1
        self.assertEqual(M.bookings(self.cfg(), self.config, self.folder, SITE, NOW), [])
        got = M.bookings(self.cfg(bookings_drop_minimum=1, bookings_drop_percent=99),
                         self.config, self.folder, SITE, NOW)
        self.assertEqual(got, [])           # 3 is more than 1: no fall
        db = sqlite3.connect(self.folder / store.FILE)
        with db:
            db.execute("UPDATE figures SET value = 0 WHERE name = 'booked_7d'")
        db.close()
        conn.update(self.folder, SITE, "calendly", audit={"ok": True})
        got = M.bookings(self.cfg(bookings_drop_minimum=1), self.config, self.folder, SITE, NOW)
        self.assertEqual((got[0]["title"], got[0]["figure"]),
                         ("Calendly bookings down 100%: 0 in 7 days", 0))
        self.assertTrue(got[0]["detail"].startswith("Counted from: Calendly."))

    def test_withheld_or_not_connected_is_silent(self):
        self.assertEqual(M.bookings(self.cfg(bookings_drop_minimum=1), self.config,
                                    self.folder, SITE, NOW), [])
        self.calendly()
        conn.update(self.folder, SITE, "calendly", audit={"ok": False})
        self.assertEqual(M.bookings(self.cfg(bookings_drop_minimum=1), self.config,
                                    self.folder, SITE, NOW), [])


class GA4Gap(Base):
    def ga4(self):
        sync.connect(self.config, self.folder, SITE, "ga4", {"property": PROP}, "cli",
                     key=service_key())
        self.assertEqual(self.sync(Google()), 0)            # 1,234 sessions

    def test_far_apart_either_way_and_said_as_different(self):
        self.ga4()
        cfg = self.cfg(ga4_log_gap=True)
        history = FakeHistory(500)
        got = M.ga4_gap(cfg, self.config, self.folder, history, SITE, NOW)
        self.assertEqual(history.asked[0][1], date(2026, 10, 25))      # GA4's own dates
        self.assertEqual((got[0]["cause"], got[0]["figure"]), ("ga4_log_gap", 2.47))
        self.assertIn("2.5 to 1", got[0]["title"])
        self.assertIn("neither is wrong", got[0]["detail"])
        self.assertEqual(got[0]["detail"].count("wrong"), 1)          # "neither is wrong"
        got = M.ga4_gap(cfg, self.config, self.folder, FakeHistory(3000), SITE, NOW)
        self.assertIn("1 to 2.4", got[0]["title"])
        self.assertIn("fewer in Google Analytics", got[0]["detail"])
        self.assertEqual(M.ga4_gap(cfg, self.config, self.folder, FakeHistory(800), SITE, NOW),
                         [])

    def test_silent_without_whole_verified_days_or_ga4(self):
        cfg = self.cfg(ga4_log_gap=True)
        self.assertEqual(M.ga4_gap(cfg, self.config, self.folder, FakeHistory(100), SITE, NOW),
                         [])
        self.ga4()
        self.assertEqual(M.ga4_gap(cfg, self.config, self.folder,
                                   FakeHistory(100, complete=False), SITE, NOW), [])

    def test_off_by_default(self):
        self.ga4()
        state = {}
        got = M.findings(state, self.config, FakeHistory(100), SITE, self.folder, TZ, NOW)
        self.assertFalse([f for f in got if f["cause"] == "ga4_log_gap"])
        self.config["alerts"]["ga4_log_gap"] = True
        got = M.findings(state, self.config, FakeHistory(100), SITE, self.folder, TZ, NOW)
        self.assertTrue([f for f in got if f["cause"] == "ga4_log_gap"])


class Daily(Base):
    def test_worked_out_once_a_day_and_again_for_new_settings(self):
        self.leads = {date(2026, 10, 19): 1, date(2026, 10, 12): 10}     # 19-25 Oct, 12-18 Oct
        state = {}
        first = M.findings(state, self.config, None, SITE, self.folder, TZ, NOW)
        self.assertEqual([f["cause"] for f in first], ["leads_drop"])
        self.leads = {}
        again = M.findings(state, self.config, None, SITE, self.folder, TZ,
                           NOW - timedelta(hours=1))
        self.assertEqual(again, first)                       # the same day: kept
        self.config["alerts"]["leads_drop"] = False
        self.assertEqual(M.findings(state, self.config, None, SITE, self.folder, TZ, NOW), [])

    def test_through_apply_one_alert_opened_once(self):
        self.leads = {date(2026, 10, 19): 1, date(2026, 10, 12): 10}
        state = {}
        cfg = alerts.settings({"alerts": {"enabled": True}})
        found = M.findings(state, self.config, None, SITE, self.folder, TZ, NOW)
        to_mail, _ = alerts.apply(state, found, NOW, cfg)
        self.assertEqual([(a["cause"], a["severity"], a["unit"]) for a in to_mail],
                         [("leads_drop", "medium", "leads")])
        to_mail, _ = alerts.apply(state, found, NOW + timedelta(minutes=10), cfg)
        self.assertEqual(to_mail, [])
        self.leads = {date(2026, 10, 20): 1, date(2026, 10, 13): 10}      # the next day
        found = M.findings(state, self.config, None, SITE, self.folder, TZ,
                           NOW + timedelta(days=1))
        to_mail, _ = alerts.apply(state, found, NOW + timedelta(days=1), cfg)
        self.assertEqual(to_mail, [], "still open: not mailed again")
        self.assertEqual(len([a for a in state["alerts"] if a["closed_at"] is None]), 1)

    def test_a_failure_keeps_the_last_findings(self):
        state = {"marketing": {"found": [{"cause": "leads_drop", "subject": "x"}]}}
        errors = []

        class Ctx:
            config, site, db_path, tz = {"alerts": "broken"}, SITE, str(self.folder / "h.sqlite"), TZ
            err = errors.append
        self.assertEqual(M.run(Ctx, state, None, NOW), [{"cause": "leads_drop",
                                                         "subject": "x"}])
        self.assertTrue(errors[0].startswith("alerts: marketing rules:"))


if __name__ == "__main__":
    unittest.main()
