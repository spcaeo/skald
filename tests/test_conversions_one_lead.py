"""2.26: one lead counts once, and the admin's commands by reference.

A ref sent under a lead action as both `completed` and `paid` was two leads. Now one
(site, tool, external_ref, action) is one lead: its first finished row (earliest `at`,
then the stage's name); the other is a step of it, listed and never counted. Both roads
agree: the main road (store.repeat_finishes, conversions_data.figures, the Leads list,
today's listing) and the second counts (the spool recount, audit_conversions_figures,
audit_conversions_leads, audit_client_reports).

And `conversions mark-test SITE --ref REF` and `conversions remove SITE --ref REF --why`
(cli_conversions.py): every stage of a ref marked, or soft-removed into `removed`, with
the second count still agreeing. Refs are made up (u-1001), hosts are example.com.
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_hooks import Base, lead  # noqa: E402

from skald import (audit_client_reports, audit_conversions,  # noqa: E402
                          audit_conversions_leads, cli_conversions, conversions_data)
from skald.conversions import store  # noqa: E402
from skald.people import leadlist, lookup  # noqa: E402

UTC = timezone.utc
SITE = "example.com"
TODAY = date(2026, 10, 11)
NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)
FIRST, LAST = date(2026, 10, 1), TODAY


def sent(ref, stage, at, action="signup", **kw):
    return lead(external_ref=ref, action=action, stage=stage, at=at, vid=None, **kw)


class Rows(Base):
    """The rows each test starts from: four sign-ups sent twice or once."""

    def setUp(self):
        super().setUp()
        quiet = redirect_stderr(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        for body in (sent("u-1234567", "completed", "2026-10-09T10:00:00Z"),
                     sent("u-1234567", "paid", "2026-10-09T11:00:00Z"),      # same day
                     sent("u-1001", "completed", "2026-10-09T12:00:00Z"),
                     sent("u-1001", "paid", "2026-10-10T09:00:00Z"),         # the next day
                     sent("u-2002", "paid", "2026-10-10T10:00:00Z"),         # paid only
                     sent("u-3003", "paid", "2026-10-11T08:00:00Z"),         # paid first
                     sent("u-3003", "completed", "2026-10-11T09:00:00Z"),
                     sent("u-4004", "completed", "2026-10-11T07:00:00Z", test=True),
                     sent("u-4004", "paid", "2026-10-11T07:30:00Z"),         # first counted
                     sent("o-1", "paid", "2026-10-11T07:45:00Z", action="paid"),
                     sent("o-1", "completed", "2026-10-11T07:50:00Z", action="paid")):
            status, answer = self.post("lead", body)
            self.assertEqual((status, answer["recorded"]), (200, 1), answer)

    def blob(self):
        return conversions_data.blob(self.config, self.folder, SITE, UTC, TODAY, NOW)

    def stages(self, got, day, action="signup"):
        return next(x for x in got["days"] if x["day"] == day)["stages"].get(action, {})

    def findings(self):
        return audit_conversions.findings(self.config, self.folder, SITE, UTC, FIRST, LAST,
                                          today=TODAY, refresh=False)

    def agreed(self):
        got = self.blob()
        self.assertEqual(got["withheld"], {}, "the second counts agree")
        self.assertEqual(self.findings(), {}, "store and spool agree")
        return got

    def leads(self) -> int:
        got = self.blob()
        return sum(n for d in got["days"] if d.get("state") == "ok"
                   for a, per in (d.get("stages") or {}).items() if a in got["lead_actions"]
                   for s, n in per.items() if s in got["finished"])


class OneLeadOnce(Rows):
    def test_figures_count_each_lead_once_and_both_roads_agree(self):
        got = self.agreed()
        self.assertEqual(self.stages(got, "2026-10-09"), {"completed": 2})
        self.assertEqual(self.stages(got, "2026-10-10"), {"paid": 1}, "u-1001's paid is a step")
        self.assertEqual(self.stages(got, "2026-10-11"), {"paid": 2},
                         "u-3003 paid first; u-4004's test completed leaves its paid the lead")
        self.assertEqual(self.leads(), 5)
        self.assertEqual(self.stages(got, "2026-10-11", "paid"), {"paid": 1, "completed": 1},
                         "not a lead action: every row counts, as before")

    def test_the_second_roads_alone(self):
        path = self.folder / store.FILE
        self.assertEqual(audit_client_reports.recount_leads(path, SITE, UTC, FIRST, LAST),
                         {"signup": 5})
        self.assertEqual(audit_conversions_leads.range_counts(
            store.connect(path), SITE, UTC, FIRST.isoformat(), LAST.isoformat(), None),
            {"leads": 5})
        db = store.connect(path)
        try:
            day = store.day_counts(db, SITE, UTC, FIRST, LAST)
        finally:
            db.close()
        self.assertEqual(day["2026-10-10"], {("signup", "paid"): 1})

    def test_a_main_road_counting_the_repeat_is_caught(self):
        real = store.repeat_finishes
        store.repeat_finishes = lambda db, site: set()
        try:
            got = self.blob()
        finally:
            store.repeat_finishes = real
        self.assertIn("days/2026-10-09", got["withheld"])
        self.assertIn("days/2026-10-10", got["withheld"])

    def test_the_lead_list_has_one_row_per_lead_with_both_steps(self):
        got = leadlist.rows(self.config, self.folder, SITE, FIRST, LAST, False)
        mine = [r for r in got["rows"] if not r["left_out"]]
        self.assertEqual(sorted(r["ref"] for r in mine),
                         ["u-1001", "u-1234567", "u-2002", "u-3003", "u-4004"])
        one = next(r for r in mine if r["ref"] == "u-1001")
        self.assertEqual([s["stage"] for s in one["steps"]], ["completed", "paid"])
        self.assertEqual(next(r for r in mine if r["ref"] == "u-3003")["stage"], "paid")

    def test_today_marks_the_repeat_and_by_hour_counts_once(self):
        got = self.agreed()
        today = got["today"]
        self.assertEqual(today["state"], "ok", today)
        flags = {(r["ref"], r["stage"]): r["repeat"] for r in today["rows"]
                 if r["action"] == "signup"}
        self.assertEqual(flags[("u-3003", "completed")], True)
        self.assertEqual(flags[("u-3003", "paid")], False)
        self.assertEqual(flags[("u-4004", "paid")], False)
        self.assertEqual(sum(today["by_now"]["today_hours"]), 2)


def ctx_for(case, *argv):
    """Parse argv as `skald` would and run it; (code, out lines, err lines)."""
    ap = argparse.ArgumentParser()
    cli_conversions.add_command(ap.add_subparsers(dest="command"))
    args = ap.parse_args(list(argv))
    args.only_site = None
    out, err = [], []
    ctx = SimpleNamespace(args=args, config=case.config, db_path=case.folder / "history.sqlite",
                          out=out.append, err=err.append)
    return args.run(ctx), out, err


class ByReference(Rows):
    def log(self) -> str:
        path = self.folder / "privacy.log"
        return path.read_text() if path.exists() else ""

    def stages_of(self, ref):
        return self.rows(f"SELECT stage, test FROM conversions WHERE external_ref = '{ref}' "
                         f"ORDER BY id")

    def test_mark_test_by_ref_marks_every_stage_and_unmarks(self):
        code, out, _ = ctx_for(self, "conversions", "mark-test", SITE, "--ref", "u-1001",
                               "--ref", "u-2002", "--ref", "u-9999")
        self.assertEqual(code, 0)
        self.assertIn("3 row(s) marked test", out[-1])
        self.assertIn("not found: u-9999", out[-1])
        self.assertEqual([t for _, t in self.stages_of("u-1001")], [store.TEST_MARKED] * 2)
        self.assertEqual(self.leads(), 3)
        self.agreed()
        self.assertIn("conversions.test", self.log())
        self.assertIn("refs=u-1001,u-2002,u-9999", self.log())
        code, out, _ = ctx_for(self, "conversions", "mark-test", SITE, "--ref", "u-1001",
                               "--unmark")
        self.assertIn("2 row(s) unmarked", out[-1])
        self.assertEqual(self.leads(), 4)
        self.agreed()

    def test_mark_test_needs_ids_or_a_ref(self):
        code, _, err = ctx_for(self, "conversions", "mark-test", SITE)
        self.assertEqual(code, 2)
        self.assertIn("--ref", err[0])

    def test_remove_needs_why(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            ctx_for(self, "conversions", "remove", SITE, "--ref", "u-1001")
        code, _, err = ctx_for(self, "conversions", "remove", SITE, "--ref", "u-1001",
                               "--why", "  ")
        self.assertEqual(code, 2)
        self.assertEqual(len(self.stages_of("u-1001")), 2, "nothing changed")

    def test_dry_run_lists_and_changes_nothing(self):
        code, out, _ = ctx_for(self, "conversions", "remove", SITE, "--ref", "u-1001",
                               "--stage", "paid", "--why", "sent twice", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(len(out), 2)
        self.assertIn("signup paid", out[0])
        self.assertIn("would remove 1 row(s)", out[1])
        self.assertEqual(len(self.stages_of("u-1001")), 2)
        self.assertNotIn("conversions.remove", self.log())

    def test_remove_keeps_each_row_with_why_out_of_every_count(self):
        code, out, _ = ctx_for(self, "conversions", "remove", SITE, "--ref", "u-1234567",
                               "--why", "a staff account")
        self.assertEqual(code, 0, out)
        self.assertIn("2 row(s) of u-1234567 removed", out[-1])
        self.assertEqual(self.stages_of("u-1234567"), [])
        gone = lookup.conversions_listing(self.config, self.folder, SITE, "removed", True)["rows"]
        self.assertEqual(sorted(r["stage"] for r in gone), ["completed", "paid"])
        self.assertTrue(all("a staff account" in r["why"] for r in gone))
        got = self.agreed()                    # the spool still holds its lines
        self.assertEqual(self.stages(got, "2026-10-09"), {"completed": 1})
        self.assertIn("conversions.remove", self.log())
        self.assertIn("why=a staff account", self.log())
        # The app sends it again, corrected: a new row, counted on both roads.
        self.now = time.time() + 60            # after the removal (stamped by the real clock)
        status, answer = self.post("lead", sent("u-1234567", "completed",
                                                "2026-10-09T10:30:00Z"))
        self.assertEqual(answer["recorded"], 1)
        got = self.agreed()
        self.assertEqual(self.stages(got, "2026-10-09"), {"completed": 2})

    def test_remove_one_stage_and_an_unknown_ref(self):
        code, _, _ = ctx_for(self, "conversions", "remove", SITE, "--ref", "u-1001",
                             "--stage", "completed", "--why", "wrong stage")
        self.assertEqual(code, 0)
        self.assertEqual(self.stages_of("u-1001"), [("paid", 0)])
        got = self.agreed()
        self.assertEqual(self.stages(got, "2026-10-10"), {"paid": 2}, "its paid is the lead now")
        code, _, err = ctx_for(self, "conversions", "remove", SITE, "--ref", "u-9999",
                               "--why", "x")
        self.assertEqual(code, 1)
        self.assertIn("no row", err[0])


if __name__ == "__main__":
    unittest.main()
