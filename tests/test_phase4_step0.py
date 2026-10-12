"""Phase 4, step 0: the shared hooks the four lanes build on.

What is pinned:
- a funnel on a view never counts journeys from a withheld day (the bug in
  funnels._view_journeys; the whole-site path already left them out);
- day_more: a registered collect-time kind is computed in extras.finish,
  checked in extras.check, stored by store_extras.write, and a module not
  written yet is skipped;
- audit_more: a registered recount is fed every people visit with its
  labels during audit.recount and compared in the audit; a mismatch is
  caught;
- run-daily: the registered daily recounts and the leads recount run as
  steps that never stop the run, and a mismatch ends it "withheld" (by
  design, like the audit's), a crash "failed".
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import types
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import (audit_more, cli, day_more, extras, funnels, mailer,  # noqa: E402
                          runs, store_extras)
from skald.classify import Group  # noqa: E402

from support import SECRETS, Sandbox, day_lines, line, totals_for  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"


def fake_module(name: str, **attrs) -> dict:
    """A module `skald.<name>` for mock.patch.dict(sys.modules, ...)."""
    mod = types.ModuleType(f"skald.{name}")
    for key, value in attrs.items():
        setattr(mod, key, value)
    return {mod.__name__: mod}


# ---------------------------------------------------------------- the bug

class FakeHistory:
    def __init__(self, journeys):
        self._journeys = journeys

    def journeys(self, key, first, last):
        return [j for j in self._journeys if first.isoformat() <= j["day"] <= last.isoformat()]


class TestViewJourneys(unittest.TestCase):

    def page(self, live_ok=False):
        stored = [{"day": "2026-10-05", "landing": "/a"}, {"day": "2026-10-06", "landing": "/b"},
                  {"day": "2026-10-07", "landing": "/c"}]
        return SimpleNamespace(
            config={}, today=date(2026, 10, 8), anchor=date(2026, 10, 7),
            key="example.com::blog", history=FakeHistory(stored), live_ok=live_ok,
            snap={"journeys": [{"day": "2026-10-08", "landing": "/d"}]},
            states={"2026-10-05": {"state": "ok"}, "2026-10-06": {"state": "withheld"},
                    "2026-10-07": {"state": "partial"}})

    def test_a_withheld_days_journeys_are_left_out(self):
        got, first = funnels._view_journeys(self.page())
        self.assertEqual([j["landing"] for j in got], ["/a", "/c"])
        self.assertEqual(first, date(2026, 10, 1))

    def test_today_comes_from_a_good_snapshot_only(self):
        got, _ = funnels._view_journeys(self.page(live_ok=True))
        self.assertEqual([j["landing"] for j in got], ["/a", "/c", "/d"])

    def test_the_view_and_the_whole_site_keep_the_same_journeys(self):
        from skald.leads import _page_journeys
        p = self.page(live_ok=True)
        self.assertEqual(funnels._view_journeys(p), _page_journeys(p))


# --------------------------------------------------------------- day_more

def _people_readers(totals) -> int:
    people = totals.groups.get(Group.PEOPLE)        # absent on a day with no people
    return people.readers if people is not None else 0


def kind_module(offset: int = 0) -> dict:
    def finish(ex, totals, journeys, page_visits, readers_by_hour):
        return {"readers": _people_readers(totals) + offset, "journeys": len(journeys)}

    def check(totals, blob, differs, problems):
        differs("fake: readers", blob["readers"], _people_readers(totals), "readers")
    return fake_module("_fake_kind", finish=finish, check=check)


class TestDayMore(unittest.TestCase):

    def test_the_planned_kinds_are_stored_kinds(self):
        for kind in ("funnels", "engagement", "utm_hygiene"):
            self.assertIn(kind, store_extras.KINDS)
            self.assertIn(kind, day_more.KINDS)
        self.assertLessEqual(set(day_more.KINDS), set(store_extras.KINDS))

    def test_a_module_not_written_yet_is_skipped(self):
        with mock.patch.dict(day_more.KINDS, {"utm_hygiene": "_no_such_module_yet"},
                             clear=True):
            self.assertEqual(day_more.modules(), {})
            totals = totals_for(day_lines(DAY, 3))
        self.assertNotIn("utm_hygiene", totals.extras)
        self.assertEqual(extras.check(totals), [])

    def test_a_registered_kind_is_finished_and_checked(self):
        with mock.patch.dict(sys.modules, kind_module()), \
                mock.patch.dict(day_more.KINDS, {"fake": "_fake_kind"}, clear=True):
            totals = totals_for(day_lines(DAY, 3))
            self.assertEqual(totals.extras["fake"], {"readers": 3, "journeys": 3})
            self.assertEqual(extras.check(totals), [])

    def test_its_check_catches_a_figure_that_does_not_add_up(self):
        with mock.patch.dict(sys.modules, kind_module(offset=1)), \
                mock.patch.dict(day_more.KINDS, {"fake": "_fake_kind"}, clear=True):
            totals = totals_for(day_lines(DAY, 3))
            problems = extras.check(totals)
        self.assertEqual([p.what for p in problems], ["fake: readers does not sum"])


# -------------------------------------------------------------- audit_more

class FakeRecount:
    seen: list = []

    def __init__(self, config, day, tz, own):
        self.readers = 0
        FakeRecount.seen.append((day, sorted(own)))

    def visit(self, lines, is_page, labels):
        if labels is not None:
            self.readers += 1
            assert any(is_page(line) for line in lines)
            assert labels["source"] and labels["device"]

    def compare(self, stored, same, problems):
        if "fake" in stored:
            same("fake: readers", stored["fake"]["readers"], self.readers)


class TestAuditMore(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(day_lines(DAY, 3))
        FakeRecount.seen = []
        self.patches = [mock.patch.dict(sys.modules, {**kind_module(),
                                                      **fake_module("_fake_audit",
                                                                    Recount=FakeRecount)}),
                        mock.patch.dict(day_more.KINDS, {"fake": "_fake_kind"}, clear=True),
                        mock.patch.object(store_extras, "KINDS", store_extras.KINDS + ("fake",)),
                        mock.patch.dict(audit_more.RECOUNTS, {"fake": "_fake_audit",
                                                              "gone": "_not_written_yet"},
                                        clear=True)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.box.close()

    def test_a_registered_recount_is_fed_and_compared(self):
        code, _, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        self.assertEqual(FakeRecount.seen, [(DAY, ["example.com"])])

    def test_a_planted_error_is_caught(self):
        code, _, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'fake'",
                       (json.dumps({"readers": 4, "journeys": 3}),))
        db.close()
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("fake: readers: history has 4, the recount finds 3", err)

    def test_the_live_audit_compares_it_too(self):
        live = Sandbox()
        try:
            ten = datetime(2026, 10, 7, 10, tzinfo=timezone.utc)      # before --today's noon
            live.log([line(ten + timedelta(minutes=i), f"203.0.113.{20 + i}", "/") for i in range(3)])
            stamp = datetime(2026, 10, 7, 23, tzinfo=timezone.utc).timestamp()
            os.utime(live.root / "logs" / "access.log", (stamp, stamp))
            self.assertEqual(live.run("--today", "2026-10-07", "live")[0], 0)
            code, out, err = live.run("--today", "2026-10-07", "audit", "--live")
            self.assertEqual(code, 0, err)
            snap = live.root / "live-example.com.json"
            got = json.loads(snap.read_text())
            self.assertEqual(got["extras"]["fake"]["readers"], 3)
            got["extras"]["fake"]["readers"] = 5
            snap.write_text(json.dumps(got))
            code, out, err = live.run("--today", "2026-10-07", "audit", "--live")
            self.assertEqual(code, 1)
            self.assertIn("fake: readers: the snapshot has 5, the recount finds 3", err)
        finally:
            live.close()


# --------------------------------------------------------------- run-daily

def daily_module(result) -> dict:
    def daily(ctx, day):
        if isinstance(result, Exception):
            raise result
        return result
    return fake_module("_fake_daily", daily=daily)


class RunDailyCase(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(day_lines(DAY, 3))

    def tearDown(self):
        self.box.close()

    def run_daily(self):
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", TODAY, "run-daily")
        return code, out, err, smtp.return_value.send_message.call_count

    def names(self):
        parsed = cli.parser().parse_args(["--config", str(self.box.config), "--today", TODAY,
                                          "run-daily"])
        return [n for n, _ in cli.daily_steps(cli.Context(parsed))]

    def outcome(self):
        return runs.load(self.box.root)["run-daily"]["last_outcome"]


class TestDailyRecounts(RunDailyCase):

    def test_none_registered_adds_no_step(self):
        with mock.patch.dict(audit_more.DAILY, {"gone": "_not_written_yet"}, clear=True):
            self.assertNotIn("recounts", self.names())

    def test_a_registered_recount_runs_after_the_audit(self):
        with mock.patch.dict(sys.modules, daily_module([])), \
                mock.patch.dict(audit_more.DAILY, {"fake": "_fake_daily"}, clear=True):
            names = self.names()
            code, out, err, mails = self.run_daily()
        self.assertEqual(names[names.index("audit") + 1], "recounts")
        self.assertEqual(code, 0, err)
        self.assertIn("fake: ok", out)
        self.assertEqual(self.outcome(), "ok")

    def test_a_mismatch_is_withheld_by_design_and_stops_nothing(self):
        with mock.patch.dict(sys.modules, daily_module(["fake figure: 2 against 3"])), \
                mock.patch.dict(audit_more.DAILY, {"fake": "_fake_daily"}, clear=True):
            code, out, err, mails = self.run_daily()
        self.assertEqual(code, 1)
        self.assertIn("fake figure: 2 against 3", err)
        self.assertEqual(mails, 1)                  # the daily mail still went
        self.assertEqual(self.outcome(), "withheld")

    def test_a_crash_is_a_failure(self):
        with mock.patch.dict(sys.modules, daily_module(RuntimeError("broken"))), \
                mock.patch.dict(audit_more.DAILY, {"fake": "_fake_daily"}, clear=True):
            code, out, err, mails = self.run_daily()
        self.assertEqual(code, 2)
        self.assertIn("RuntimeError: broken", err)
        self.assertEqual(mails, 1)
        self.assertEqual(self.outcome(), "failed")


class TestLeadsInRunDaily(RunDailyCase):

    def setUp(self):
        super().setUp()
        from test_leads import make_db
        make_db(self.box.root / "payload.db")
        with open(self.box.config, "a") as handle:
            handle.write(f"leads:\n  db: {self.box.root / 'payload.db'}\n")

    def test_the_leads_recount_is_a_step(self):
        names = self.names()
        self.assertEqual(names[names.index("audit") + 1], "leads audit")
        code, out, err, _ = self.run_daily()
        self.assertEqual(code, 0, err)
        self.assertIn("leads audit: ok", out)

    def test_a_leads_mismatch_is_counted_like_the_audits(self):
        with mock.patch("skald.audit_leads.compare", return_value=["planted"]):
            code, out, err, mails = self.run_daily()
        self.assertEqual(code, 1)
        self.assertIn("planted", err)
        self.assertEqual(mails, 1)
        self.assertEqual(self.outcome(), "withheld")

    def test_not_set_up_adds_no_step(self):
        self.box.config.write_text(self.box.config.read_text().split("leads:")[0])
        self.assertNotIn("leads audit", self.names())


if __name__ == "__main__":
    unittest.main()
