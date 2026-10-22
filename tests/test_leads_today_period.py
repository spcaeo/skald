"""2.27: Leads & sales > Leads counts 7 days as today so far and the 6 whole days before
(30 and 90 the same way), and compares like for like: the period before, its whole days,
then its last day to the same time of day (conversions.json `today.same_time`,
conversions_leads.same_time), recounted by audit_conversions_leads.check_same_time.

The owner, 2026-10-22: "if you are looking at 7 days it should also show today ... today is
1 + last 6 = 7 days". The page's own reading is tests/js/leads-period.mjs. Refs are made up,
hosts example.com.
"""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_hooks import Base, lead  # noqa: E402

from skald import audit_conversions_leads, conversions_data, conversions_leads  # noqa: E402
from skald.conversions import store  # noqa: E402
from skald.people import leadlist  # noqa: E402

UTC = timezone.utc
SITE = "example.com"
TODAY = date(2026, 10, 22)
NOW = datetime(2026, 10, 22, 14, 0, tzinfo=UTC)


def sent(ref, at, action="signup", stage="completed", **kw):
    return lead(external_ref=ref, action=action, stage=stage, at=at, vid=None, **kw)


class TodayAndSixDays(Base):
    def setUp(self):
        super().setUp()
        self.now = NOW.timestamp()
        quiet = redirect_stderr(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        for body in (
                # The 7 days before (9 to 15 Oct): 14 Oct whole; 15 Oct before and after 14:00.
                sent("u-14", "2026-10-14T09:00:00Z"),
                sent("u-15a", "2026-10-15T09:00:00Z"),                       # before 14:00
                sent("u-15a", "2026-10-15T12:00:00Z", stage="paid"),         # its repeat: a step
                sent("u-15b", "2026-10-15T16:00:00Z", action="contact"),     # after 14:00
                sent("u-15t", "2026-10-15T10:00:00Z", test=True),            # test: never
                sent("u-15s", "2026-10-15T11:00:00Z", action="demo", stage="started"),
                # The period: 16 Oct to today (22 Oct, so far).
                sent("u-16", "2026-10-16T00:30:00Z"),
                sent("u-18", "2026-10-18T10:00:00Z", action="contact"),
                sent("u-22a", "2026-10-22T08:00:00Z"),
                sent("u-22b", "2026-10-22T11:00:00Z", action="demo"),
                sent("u-22t", "2026-10-22T12:00:00Z", test=True)):
            status, answer = self.post("lead", body)
            self.assertEqual((status, answer["recorded"]), (200, 1), answer)
        self.path = self.folder / store.FILE

    def blob(self):
        return conversions_data.blob(self.config, self.folder, SITE, UTC, TODAY, NOW)

    @staticmethod
    def leads(got, first, last):
        return sum(n for d in got["days"] if d.get("state") == "ok" and first <= d["day"] <= last
                   for a, per in (d.get("stages") or {}).items() if a in got["lead_actions"]
                   for s, n in per.items() if s in got["finished"])

    def sql(self, first, last):
        db = store.connect(self.path)
        try:
            return audit_conversions_leads.range_counts(db, SITE, UTC, first, last, None)["leads"]
        finally:
            db.close()

    def test_the_period_is_today_and_the_six_whole_days_before(self):
        got = self.blob()
        self.assertEqual(got["withheld"], {}, "every second count agrees")
        days = [d["day"] for d in got["days"]]
        self.assertEqual(days[-7:], [(TODAY - timedelta(days=6 - i)).isoformat() for i in range(7)],
                         "the file's days end today: the period's 7 are all in it")
        self.assertEqual(self.leads(got, "2026-10-16", "2026-10-22"), 4, "16, 18 and today's two")
        self.assertEqual(self.leads(got, "2026-10-22", "2026-10-22"), 2, "today so far, test left out")
        # The second road counts the same days, today's rows included.
        self.assertEqual(self.sql("2026-10-16", "2026-10-22"), 4)

    def test_the_list_holds_todays_rows_newest_first(self):
        got = leadlist.rows(self.config, self.folder, SITE, date(2026, 10, 16), TODAY, False)
        mine = [r for r in got["rows"] if not r["left_out"]]
        self.assertEqual([r["ref"] for r in mine], ["u-22b", "u-22a", "u-18", "u-16"])
        self.assertEqual([r["at"][:10] for r in got["rows"] if r["left_out"]], ["2026-10-22"],
                         "today's test row: listed, marked, never counted")
        self.assertEqual(len(mine), self.leads(self.blob(), "2026-10-16", "2026-10-22"),
                         "the list and the figure hold the same leads")
        # The server's own bounds: today is the last day a period may name.
        self.assertEqual(leadlist.span("2026-10-16", "2026-10-25", TODAY), (date(2026, 10, 16), TODAY))

    def test_the_period_before_to_the_same_hour(self):
        got = self.blob()
        part = got["today"]["same_time"]
        self.assertEqual(part["time"], "14:00:00")
        self.assertEqual([e["back"] for e in part["days"]], [7, 30, 90])
        week = part["days"][0]
        self.assertEqual((week["day"], week["until"], week["state"]),
                         ("2026-10-15", "2026-10-15T14:00:00+00:00", "ok"))
        self.assertEqual((week["leads"], week["actions"]), (1, {"signup": 1}),
                         "09:00 only: not its repeat paid, not 16:00, not the test, not a start")
        # Like for like: 9 to 14 Oct whole, then 15 Oct to 14:00, against the SQL's own count.
        before = self.leads(got, "2026-10-09", "2026-10-14") + week["leads"]
        self.assertEqual(before, 2)
        self.assertEqual(self.sql("2026-10-09", "2026-10-14") + 1, before)
        self.assertEqual(self.leads(got, "2026-10-09", "2026-10-15"), 3,
                         "the whole 7 days before would hold 3: the contact form at 16:00 too")
        self.assertEqual(audit_conversions_leads.check_same_time(self.path, SITE, UTC, TODAY, part), [])

    def test_a_tampered_figure_is_found_and_withheld(self):
        part = self.blob()["today"]["same_time"]
        part["days"][0]["leads"] = 2
        part["days"][0]["actions"] = {"signup": 1, "contact": 1}
        problems = audit_conversions_leads.check_same_time(self.path, SITE, UTC, TODAY, part)
        self.assertTrue(any("2026-10-15 to 14:00: file 2 leads, SQL recount 1" in p for p in problems), problems)
        self.assertTrue(any("2026-10-15 by action" in p for p in problems), problems)
        # The main road counting the repeat finish: the second count withholds today's block.
        real = conversions_leads.same_time

        def wrong(*a, **kw):
            out = real(*a, **kw)
            out["days"][0]["leads"] += 1
            return out
        conversions_leads.same_time = wrong
        try:
            got = self.blob()
        finally:
            conversions_leads.same_time = real
        self.assertEqual(got["today"]["state"], "withheld")
        self.assertIn("same time 2026-10-15", got["withheld"]["today"])

    def test_withheld_or_not_recorded_days_carry_no_figure(self):
        db = store.connect(self.path)
        try:
            held = conversions_leads.same_time(db, SITE, UTC, TODAY, NOW, {"2026-10-15"}, "2026-09-01")
            young = conversions_leads.same_time(db, SITE, UTC, TODAY, NOW, set(), "2026-10-01")
        finally:
            db.close()
        self.assertEqual((held["days"][0]["state"], held["days"][0]["leads"]), ("withheld", None))
        self.assertEqual([e["state"] for e in young["days"]], ["ok", "not_recorded", "not_recorded"],
                         "30 and 90 days before: before the leads' first day")


if __name__ == "__main__":
    unittest.main()
