"""The People-days sweep of the tools' stored answers (yourtools/people_days.py).

  * names and emails past the site's People days go from the stored answers
    (Calendly invitees, Resend contacts and recipients), the younger ones stay
  * even for a tool that stopped answering: the sweep needs no sync
  * the figures stay, row for row; the answer's sha256 is made again, so the
    second road (recount.check) still matches after a cut, and a change
    made any other way is still found
  * a site that keeps everything (keep_everything.Keeper) loses nothing; the
    daily prune runs the sweep; counts only in the output, never a value
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald.yourtools import conn, people_days, recount, store, sync  # noqa: E402

from test_yourtools_calendly import TOKEN as CAL_TOKEN, FakeCalendly  # noqa: E402
from test_yourtools_resend import KEY as RESEND_KEY, FakeResend  # noqa: E402

SITE = "example.com"
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
LATER = date(2026, 10, 30)          # 10 People days back: 20 Oct


class Both:
    """Calendly and Resend answering through one fake connection."""

    def __init__(self):
        self.c, self.r = FakeCalendly(), FakeResend()

    def __call__(self, request, timeout=None):
        return (self.c if "calendly" in request.full_url else self.r)(request, timeout)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}, "history": {"db": str(self.folder / "h.sqlite")},
                       "conversions": {"identity": "full"}, "privacy": {"keep_days": 395}}
        sync.connect(self.config, self.folder, SITE, "calendly", {}, "cli", key=CAL_TOKEN)
        sync.connect(self.config, self.folder, SITE, "resend", {}, "cli", key=RESEND_KEY)
        job = sync.Job(self.config, SITE, self.folder, NOW, lambda *a: None, lambda *a: None,
                       opener=Both(), sleep=lambda s: None, send=lambda *a: None)
        self.assertEqual(sync.run(job), 0)
        self.out = []

    def ctx(self, days=10):
        self.config["privacy"]["keep_days"] = days
        return SimpleNamespace(config=self.config, db_path=str(self.folder / "h.sqlite"),
                               now=NOW, out=self.out.append, err=self.out.append, live_dir=None)

    def bodies(self) -> dict:
        db = sqlite3.connect(self.folder / store.FILE)
        try:
            return {(t, r): json.loads(b) for t, r, b in
                    db.execute("SELECT tool, report, body FROM answers")}
        finally:
            db.close()

    def figures(self) -> list:
        db = sqlite3.connect(self.folder / store.FILE)
        try:
            return sorted(map(repr, db.execute(
                "SELECT a.tool, a.report, f.name, f.dim, f.value, f.rank, f.src FROM figures f "
                "JOIN answers a ON a.id = f.answer_id")))
        finally:
            db.close()

    def emails(self) -> dict:
        b = self.bodies()
        return {"calendly": {i["uri"].rsplit("/", 1)[1]: i.get("email")
                             for i in b[("calendly", "totals")]["invitees"]},
                "contacts": {c["id"]: c.get("email") for c in b[("resend", "totals")]["contacts"]},
                "emails": {e["id"]: e.get("to") for e in b[("resend", "emails")]["emails"]}}


class Sweep(Base):
    def test_old_names_go_young_stay_figures_kept_and_rechecked(self):
        before = self.figures()
        got = people_days.run(self.ctx(), LATER)
        self.assertEqual(got, {SITE: {"answers": 2, "values": 5, "days": 10}})
        e = self.emails()
        self.assertEqual(e["calendly"], {"IN1": None, "IN2": "ann@example.com",
                                         "IN3": "cal@example.com", "IN4": None,
                                         "IN5": "eve@example.com"})
        names = {i["uri"].rsplit("/", 1)[1]: i.get("name")
                 for i in self.bodies()[("calendly", "totals")]["invitees"]}
        self.assertEqual((names["IN1"], names["IN4"], names["IN5"]), (None, None, "Eve Example"))
        self.assertEqual(e["contacts"], {"c3": "cy@example.com", "c2": "bo@example.com",
                                         "c1": None})        # c1: cut when it came
        self.assertEqual(e["emails"], {"e4": ["cy@example.com"], "e3": ["bo@example.com"],
                                       "e2": ["al@example.com"], "e1": None})
        self.assertEqual(self.figures(), before)                 # every figure as it was
        for tool in ("calendly", "resend"):
            self.assertTrue(recount.check(self.folder, SITE, tool)[tool]["ok"], tool)
        self.assertEqual(len(self.out), 1)
        self.assertIn("5 value(s) in 2 answer(s); figures kept", self.out[0])
        self.assertNotIn("@", self.out[0])
        self.assertEqual(people_days.run(self.ctx(), LATER), {})     # nothing more to cut

    def test_a_tool_that_stopped_answering_is_swept_too(self):
        conn.update(self.folder, SITE, "calendly", last_ok="2026-10-01T00:00:00+00:00",
                    last_try="2026-10-29T00:00:00+00:00", ok=False, error="refused")
        people_days.run(self.ctx(), LATER)
        self.assertIsNone(self.emails()["calendly"]["IN1"])

    def test_a_change_made_any_other_way_is_still_found(self):
        people_days.run(self.ctx(), LATER)
        db = sqlite3.connect(self.folder / store.FILE)
        with db:
            db.execute("UPDATE answers SET body = replace(body, 'eve@example.com', "
                       "'x@example.com') WHERE tool = 'calendly'")
        db.close()
        problems = recount.check(self.folder, SITE, "calendly")["calendly"]["problems"]
        self.assertTrue(any("changed since it came" in p for p in problems), problems)

    def test_within_the_days_nothing_changes(self):
        before = self.bodies()
        self.assertEqual(people_days.run(self.ctx(days=395), LATER), {})
        self.assertEqual(self.bodies(), before)


class KeepEverything(Base):
    def test_a_keep_everything_site_loses_nothing(self):
        before = self.bodies()
        ctx = self.ctx()
        self.config["retention"] = {"keep_everything": True}
        self.assertEqual(people_days.run(ctx, LATER), {})
        self.assertEqual(self.bodies(), before)

    def test_the_daily_prune_runs_it(self):
        src = (Path(__file__).resolve().parent.parent / "skald" / "cli_conversions.py")
        self.assertIn("tools_people_days.run(ctx, today)", src.read_text())


if __name__ == "__main__":
    unittest.main()
