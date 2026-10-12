"""conversions.json `since` (2.5.1): a lead DB that was read but holds only
spam and duplicates makes no conversion row, yet its days are recorded:
from the lead DB's first lead on, a day with no counted lead is an `ok`
day with 0, never "before" (not recorded). The second count
(audit_conversions_figures.check_since) finds the same day by its own SQL;
a wrong `since` withholds every day. Hosts example.com; names made up."""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_from_leads import add  # noqa: E402
from test_leads import SCHEMA  # noqa: E402

from skald import audit_conversions_figures, conversions_data  # noqa: E402
from skald.conversions import from_leads, store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SITE = "example.com"
UTC = timezone.utc
TODAY = date(2026, 10, 13)
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
# (id, created_at, updated_at, type, status): every one left out
SPAM = [(1, "2026-10-09T15:00:00.000Z", "2026-10-09T15:00:00.000Z", "contact", "spam"),
        (2, "2026-10-12T08:00:00.000Z", "2026-10-12T08:00:00.000Z", "demo_booked", "duplicate")]


def leads_ok(day: dict) -> tuple[int, int]:
    """A day's leads and demos booked, as leadfigs.js dayLeads sums them."""
    from skald.conversions_leads import day_demos, day_leads
    return day_leads(day), day_demos(day)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.leads = self.folder / "leads.db"
        db = sqlite3.connect(self.leads)
        db.executescript(SCHEMA)
        for i, made, updated, kind, status in SPAM:
            add(db, i, made, updated, kind, status, None, None, None, None, None)
        db.commit()
        db.close()
        self.config = {"leads": {"db": str(self.leads)}, "site": {"name": SITE}}
        self.path = store.path_for(self.config, self.folder)

    def tearDown(self):
        self.tmp.cleanup()

    def sync(self):
        db = store.connect(self.path)
        try:
            got = from_leads.sync(db, self.leads, SITE)
        finally:
            db.close()
        self.assertEqual(got["added"], 0, "spam and duplicates make no row")

    def blob(self):
        return conversions_data.blob(self.config, self.folder, SITE, UTC, TODAY, NOW)

    def day(self, got, d: str) -> dict:
        return next(x for x in got["days"] if x["day"] == d)


class RecordedSince(Fixture):
    def test_only_spam_read_is_zero_not_unknown(self):
        self.sync()
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["since"], "2026-10-09")
        self.assertEqual(self.day(got, "2026-10-08")["state"], "before")
        for d in ("2026-10-09", "2026-10-12", TODAY.isoformat()):
            self.assertEqual(self.day(got, d)["state"], "ok", d)
            self.assertEqual(leads_ok(self.day(got, d)), (0, 0), d)
        self.assertEqual(got["today"]["state"], "ok")
        self.assertEqual(got["today"]["total"], 0)

    def test_not_read_yet_is_not_recorded(self):
        # The store exists but the lead DB was never read into it: no sync mark.
        store.connect(self.path).close()
        got = self.blob()
        self.assertIsNone(got["since"])
        self.assertEqual({d["state"] for d in got["days"]}, {"before"})

    def test_lead_road_off_is_not_recorded(self):
        self.sync()
        self.config["conversions"] = {"from_leads": False}
        got = self.blob()
        self.assertIsNone(got["since"])
        self.assertEqual(got["withheld"], {})

    def test_a_removed_row_counts_as_recorded(self):
        # A real lead read, then marked spam: its row is taken away, its day still recorded.
        db = sqlite3.connect(self.leads)
        add(db, 3, "2026-10-05T10:00:00.000Z", "2026-10-05T10:00:00.000Z", "contact", "new",
            None, None, None, None, None)
        db.commit()
        self.sync_added()
        db.execute("UPDATE submissions SET status = 'spam', updated_at = ? WHERE id = 3",
                   ("2026-10-13T09:00:00.000Z",))
        db.commit()
        db.close()
        sdb = store.connect(self.path)
        try:
            self.assertEqual(from_leads.sync(sdb, self.leads, SITE)["removed"], 1)
            self.assertEqual(sdb.execute("SELECT COUNT(*) FROM conversions").fetchone()[0], 0)
        finally:
            sdb.close()
        got = self.blob()
        self.assertEqual(got["since"], "2026-10-05")
        self.assertEqual(got["withheld"], {})
        self.assertEqual(leads_ok(self.day(got, "2026-10-06")), (0, 0))

    def sync_added(self):
        db = store.connect(self.path)
        try:
            self.assertEqual(from_leads.sync(db, self.leads, SITE)["added"], 1)
        finally:
            db.close()

    def test_the_second_count_agrees_and_catches(self):
        self.sync()
        self.assertEqual(audit_conversions_figures.recount_since(self.path, SITE, UTC, self.leads),
                         "2026-10-09")
        self.assertIsNone(audit_conversions_figures.recount_since(self.path, SITE, UTC, None))
        # A `since` one day early would turn an unread day into 0: every day is withheld.
        with mock.patch.object(conversions_data, "recorded_since", return_value="2026-10-08"):
            got = self.blob()
        self.assertTrue(got["withheld"])
        self.assertNotIn("ok", {d["state"] for d in got["days"]})
        self.assertIn("recorded from: file 2026-10-08, SQL recount 2026-10-09",
                      self.day(got, "2026-10-12")["why"])

    def test_local_day(self):
        # 2026-10-09T15:00Z is still the 9th in New York; 2026-10-09T02:00Z is the 8th there.
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
        db = sqlite3.connect(self.leads)
        add(db, 4, "2026-10-09T02:00:00.000Z", "2026-10-09T02:00:00.000Z", "signup", "spam",
            None, None, None, None, None)
        db.commit()
        db.close()
        self.sync()
        sdb = store.connect(self.path)
        try:
            self.assertEqual(conversions_data.recorded_since(self.config, sdb, SITE, ny),
                             "2026-10-08")
        finally:
            sdb.close()
        self.assertEqual(audit_conversions_figures.recount_since(self.path, SITE, ny, self.leads),
                         "2026-10-08")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Tiles(Fixture):
    """leadfigs.js leadsOn, the sum the Leads and Demos booked tiles show,
    run by node (its imports stubbed) over the file Python writes: 0 on a
    day read with every lead left out, null ("-") only with no day read."""

    def leads_on(self, blob: dict, days: list[str]) -> dict:
        src = (ROOT / "skald" / "webapp" / "js" / "tabs" / "leadfigs.js").read_text()
        src = re.sub(r"^import .*$", "", src, flags=re.M)
        src = ("const h = () => null, n = String, pct1 = () => '', share = () => '', "
               "table = () => null, link = () => null;\n" + src
               + f"\nconsole.log(JSON.stringify(leadsOn({{ x: {{ conversions: {json.dumps(blob)} }} }}, "
               + f"{json.dumps(days)})));")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "leadfigs.mjs"
            path.write_text(src)
            got = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30)
        self.assertEqual(got.returncode, 0, got.stderr)
        return json.loads(got.stdout)

    def test_zero_when_read_unknown_when_not(self):
        self.sync()
        week = ["2026-10-09", "2026-10-10", "2026-10-11", "2026-10-12", TODAY.isoformat()]
        got = self.leads_on(self.blob(), week)
        self.assertEqual((got["leads"], got["demos"], got["ok"], got["of"]), (0, 0, 5, 5))
        self.assertEqual(got["before"], [])
        # Before the sync mark: nothing read, so no day counts ("-").
        self.config["conversions"] = {"from_leads": False}
        got = self.leads_on(self.blob(), week)
        self.assertEqual((got["ok"], len(got["before"])), (0, 5))
        # Withheld stays its own state, never 0.
        self.config.pop("conversions")
        with mock.patch.object(conversions_data, "recorded_since", return_value="2026-10-08"):
            got = self.leads_on(self.blob(), week)
        self.assertEqual((got["ok"], len(got["held"])), (0, 5))


if __name__ == "__main__":
    unittest.main()
