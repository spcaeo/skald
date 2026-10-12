"""conversions.json (conversions_data.py) and its second count
(audit_conversions.check_file, audit_conversions_figures.py): exact
figures from beacon events with visitor IDs and a lead DB, a planted
miscount withheld, the beacon day cache. Addresses are RFC 5737; hosts
example.com; names and emails made up."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_beacon import DAY, T, VID, VID2, Server, body  # noqa: E402
from test_conversions_from_leads import add  # noqa: E402
from test_leads import SCHEMA  # noqa: E402

from skald import audit_conversions, conversions_data  # noqa: E402
from skald.conversions import from_leads, store  # noqa: E402

UTC = timezone.utc
TODAY = DAY + timedelta(days=2)
NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


class Data(Server):
    def setUp(self):
        super().setUp()
        import sqlite3
        self.leads = self.folder / "leads.db"
        db = sqlite3.connect(self.leads)
        db.executescript(SCHEMA)
        add(db, 1, "2026-10-11T15:00:00.000Z", "2026-10-11T15:00:00.000Z", "demo_booked", "won",
            json.dumps({"referrerHost": "www.google.com", "landingPath": "/pricing/",
                        "at": "2026-10-09T15:00:00.000Z"}), None, 2, "CA", None)
        add(db, 2, "2026-10-11T16:00:00.000Z", "2026-10-11T16:00:00.000Z", "contact", "spam",
            None, None, None, None, None)
        db.commit()
        db.close()
        self.config["leads"] = {"db": str(self.leads)}
        # VID: Google two days before, then pricing, then books a demo.
        self.now = T - 2 * 86400
        self.post(body(e="page_view", p="/", id=None, r="google.com"))
        self.now = T - 3600
        self.post(body(e="page_view", p="/pricing/", id=None))
        self.now = T
        self.post(body(e="calendly_open", p="/pricing/"))
        self.post(body(e="calendly_booked", p="/pricing/"), after=60)
        # VID2: reads the blog, starts the contact form, never sends it.
        self.now = T - 7200
        self.post(body(e="page_view", p="/blog/", id=None, v=VID2))
        self.post(body(e="form_start", p="/contact/", v=VID2), after=100)
        db = store.connect(self.db_path)
        try:
            from_leads.sync(db, self.leads, "example.com")
        finally:
            db.close()

    def blob(self, **kw):
        return conversions_data.blob(self.config, self.folder, "example.com", UTC, TODAY, NOW,
                                     **kw)

    def day(self, got, d=DAY):
        return next(x for x in got["days"] if x["day"] == d.isoformat())

    def test_figures(self):
        got = self.blob()
        self.assertTrue(got["available"])
        self.assertEqual(got["withheld"], {})
        self.assertEqual(got["since"], "2026-10-11")
        self.assertEqual(self.day(got, DAY - timedelta(days=1))["state"], "before")
        d = self.day(got)
        self.assertEqual(d["state"], "ok")
        self.assertEqual(d["stages"], {"demo": {"started": 1, "completed": 2, "won": 1},
                                       "contact": {"started": 1}})
        self.assertEqual(d["abandoned"], {"contact": 1})
        self.assertEqual(d["by"]["tool"], {"demo": {"beacon": 1, "site": 1}})
        self.assertEqual(d["by"]["country"]["demo"], {"CA": 2})
        self.assertEqual(d["by"]["device"]["demo"], {"Desktop": 1, "Unknown": 1})
        self.assertEqual(d["by"]["campaign"]["demo"], {"Unknown": 1, "(no campaign tag)": 1})
        self.assertEqual(d["by"]["first_source"]["demo"], {"Unknown": 1, "Search engine": 1})
        self.assertEqual(d["visits_before"]["demo"], {"unknown": 1, "2": 1})
        self.assertEqual(d["time_to_convert"]["demo"], {"unknown": 1, "1-7d": 1})
        # The booking's own source is the visit's; Google came before it.
        self.assertEqual(d["assisted"], {"demo": {"Search engine": 1}})
        empty = self.day(got, TODAY)
        self.assertEqual((empty["state"], empty["stages"]), ("ok", {}))
        pages = got["pages_before"]
        self.assertEqual((pages["converting"], pages["other"]), (1, 1))
        self.assertEqual(pages["pages"], [["/", 1, 0], ["/pricing/", 1, 0], ["/blog/", 0, 1]])
        self.assertEqual(got["set_up"]["leads_db"], True)
        self.assertEqual(got["set_up"]["visitor_ids"], True)

    def test_timeline_is_anonymous(self):
        got = self.blob()
        dump = json.dumps(got)
        for secret in (VID, VID2, "person1@example.com", "Person 1"):
            self.assertNotIn(secret, dump)
        first = got["timeline"][0]
        self.assertEqual((first["action"], first["tool"], first["browser"]),
                         ("demo", "site", False))
        self.assertEqual([s["stage"] for s in first["steps"]], ["completed", "won"])
        booked = got["timeline"][1]
        self.assertEqual(booked["tool"], "beacon")
        self.assertEqual([v["paths"] for v in booked["visits"]], [["/"], ["/pricing/"]])
        self.assertEqual([s["stage"] for s in booked["steps"]], ["started", "completed"])

    def test_a_planted_miscount_is_withheld(self):
        real = conversions_data._label
        with mock.patch.object(conversions_data, "_label",
                               lambda dim, v: "Elsewhere" if dim == "country" and v
                               else real(dim, v)):
            got = self.blob()
        self.assertEqual(self.day(got)["state"], "withheld")
        self.assertIn("SQL recount", self.day(got)["why"])
        self.assertEqual(self.day(got, TODAY)["state"], "ok")
        self.assertEqual(got["timeline"], [], "nothing from a withheld day")
        with mock.patch.object(conversions_data, "PAGES", 1):
            got = self.blob()
        self.assertEqual(got["pages_before"]["state"], "withheld")

    def test_a_lost_row_is_withheld(self):
        db = store.connect(self.db_path)
        db.execute("DELETE FROM conversions WHERE tool = 'site' AND stage = 'won'")
        db.close()
        got = self.blob()
        self.assertIn("demo won: stored 0", self.day(got)["why"])

    def test_not_set_up(self):
        self.db_path.unlink()
        got = conversions_data.blob({}, self.folder / "none", "example.com", UTC, TODAY, NOW)
        self.assertFalse(got["available"])
        self.assertEqual(got["set_up"]["hooks"], [])

    def test_beacon_cache(self):
        spool = self.folder / "beacon"
        first = DAY - timedelta(days=3)
        full = audit_conversions.beacon_counts(spool, self.folder, UTC, first, TODAY, TODAY)
        self.assertEqual(full[DAY.isoformat()], {("demo", "started"): 1,
                                                 ("demo", "completed"): 1,
                                                 ("contact", "started"): 1})
        cache = json.loads((self.folder / audit_conversions.CACHE).read_text())
        self.assertIn(DAY.isoformat(), cache["days"])
        for f in spool.glob("*.jsonl"):        # whole past days are read back from the cache
            f.rename(f.with_suffix(".old"))
        again = audit_conversions.beacon_counts(spool, self.folder, UTC, first, TODAY, TODAY,
                                                refresh=False)
        self.assertEqual(again, full)
        self.assertEqual(audit_conversions.beacon_counts(spool, self.folder, UTC, first, TODAY,
                                                         TODAY, refresh=True), {})
        audit_conversions.forget_cache(self.folder)
        self.assertFalse((self.folder / audit_conversions.CACHE).exists())

    def test_daily_and_build(self):
        ctx = SimpleNamespace(config=self.config, db_path=self.folder / "history.sqlite",
                              site="example.com", tz=UTC)
        self.assertEqual(audit_conversions.daily(ctx, TODAY - timedelta(days=1)), [])
        page = SimpleNamespace(key="example.com::fr", config=self.config, tz=UTC, today=TODAY,
                               now=NOW, live_dir=self.folder)
        one = conversions_data.build(page)
        self.assertIs(conversions_data.build(page), one, "once per run")
        self.assertEqual(one["withheld"], {})


if __name__ == "__main__":
    unittest.main()
