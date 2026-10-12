"""conversions.sqlite, the country lookup, the secrets file and the spool."""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import VID, mmdb  # noqa: E402

from skald.conversions import geo, secrets_store, spool, store  # noqa: E402

VID2 = "skv_" + "R" * 22


def conv(**kw) -> dict:
    out = {"site": "example.com", "tool": "lead", "action": "demo", "stage": "completed",
           "at": "2026-10-10T12:00:00Z", "external_ref": "L-1", "vid": VID}
    out.update(kw)
    return out


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "conversions.sqlite"
        self.db = store.connect(self.path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_schema_and_mode(self):
        self.assertEqual(store.schema_version(self.db), store.SCHEMA_VERSION)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master "
                                                "WHERE type = 'table'")}
        self.assertTrue({"conversions", "journeys", "identities", "deliveries", "meta"} <= tables)

    def test_newer_schema_is_refused(self):
        self.db.execute("UPDATE meta SET value = '9' WHERE key = 'schema_version'")
        with self.assertRaises(RuntimeError):
            store.connect(self.path)

    def test_path(self):
        self.assertEqual(store.path_for({}, Path("/var/x")), Path("/var/x/conversions.sqlite"))
        self.assertEqual(store.path_for({"conversions": {"db": "/srv/c.sqlite"}}, Path("/x")),
                         Path("/srv/c.sqlite"))

    def test_idempotent_on_site_tool_ref_stage(self):
        self.assertTrue(store.record_conversion(self.db, conv()))
        self.assertFalse(store.record_conversion(self.db, conv(at="2026-10-11T00:00:00Z")))
        self.assertTrue(store.record_conversion(self.db, conv(stage="cancelled")))
        self.assertTrue(store.record_conversion(self.db, conv(tool="json")))
        self.assertTrue(store.record_conversion(self.db, conv(site="shop.example.com")))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM conversions").fetchone()[0], 4)
        first = self.db.execute("SELECT at FROM conversions WHERE stage = 'completed' AND "
                                "tool = 'lead' AND site = 'example.com'").fetchone()[0]
        self.assertEqual(first, "2026-10-10T12:00:00Z", "the first delivery wins")

    def test_refuses_a_bad_record(self):
        with self.assertRaises(ValueError):
            store.record_conversion(self.db, conv(stage="booked"))
        with self.assertRaises(ValueError):
            store.record_conversion(self.db, conv(external_ref=""))

    def test_identity_only_when_given(self):
        store.record_conversion(self.db, conv())
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM identities").fetchone()[0], 0)
        store.record_conversion(self.db, conv(external_ref="L-2",
                                              identity={"email": "A@Example.com", "name": "A"}))
        store.record_conversion(self.db, conv(external_ref="L-3",
                                              identity={"email": "a@example.com"}))
        rows = self.db.execute("SELECT email, email_hash FROM identities").fetchall()
        self.assertEqual(len(rows), 1, "one person, matched by keyed hash")
        self.assertNotIn("example", rows[0][1])

    def test_abandoned(self):
        store.record_conversion(self.db, conv(stage="started", at="2026-10-10T10:00:00Z"))
        store.record_conversion(self.db, conv(stage="completed", at="2026-10-10T11:00:00Z"))
        store.record_conversion(self.db, conv(stage="started", vid=VID2, external_ref="L-2",
                                              at="2026-10-10T10:00:00Z"))
        store.record_conversion(self.db, conv(stage="completed", vid=VID2, external_ref="L-3",
                                              at="2026-10-12T10:00:00Z"))
        store.record_conversion(self.db, conv(stage="started", vid=None, external_ref="L-4",
                                              at="2026-10-10T10:00:00Z"))
        store.record_conversion(self.db, conv(stage="started", vid="skv_late", external_ref="L-5",
                                              at="2026-10-10T23:00:00Z"))
        got = store.abandoned(self.db, "example.com", "2026-10-10T00:00:00Z",
                              "2026-10-11T00:00:00Z", 24, now="2026-10-11T12:00:00Z")
        self.assertEqual([r["vid"] for r in got], [VID2],
                         "finished in time, no visitor ID, and still open are left out")

    def test_journey_of(self):
        store.record_page_view(self.db, "example.com", VID, "2026-10-09T10:00:00Z", "/", "Search engine")
        store.record_page_view(self.db, "example.com", VID, "2026-10-10T10:00:00Z", "/pricing/", None)
        store.record_conversion(self.db, conv())
        got = store.journey_of(self.db, "example.com", VID)
        self.assertEqual([p["path"] for p in got["pages"]], ["/", "/pricing/"])
        self.assertEqual(len(got["conversions"]), 1)

    def test_prune_keeps_converted_journeys(self):
        for vid in (VID, VID2):
            store.record_page_view(self.db, "example.com", vid, "2026-08-01T10:00:00Z", "/", None)
        store.record_conversion(self.db, conv())
        store.log_delivery(self.db, "example.com", "lead", "recorded", 200,
                           received_at="2026-01-01T00:00:00Z")
        got = store.prune(self.db, date(2026, 10, 11), vid_days=30, retention_days=400)
        self.assertEqual(got["journeys"], 1)
        self.assertEqual(got["deliveries"], 1)
        left = [r[0] for r in self.db.execute("SELECT vid FROM journeys")]
        self.assertEqual(left, [VID])
        got = store.prune(self.db, date(2028, 1, 1), vid_days=30, retention_days=400)
        self.assertEqual((got["conversions"], got["journeys"]), (1, 1))

    def test_forget_by_email_vid_and_lead(self):
        store.record_conversion(self.db, conv(identity={"email": "a@example.com"}))
        store.record_conversion(self.db, conv(external_ref="L-9", stage="started"))
        store.record_page_view(self.db, "example.com", VID, "2026-10-10T10:00:00Z", "/", None)
        store.record_conversion(self.db, conv(external_ref="L-2", vid=VID2))
        store.log_delivery(self.db, "example.com", "lead", "recorded", 200, external_ref="L-1")
        dry = store.forget(self.db, None, email="A@example.com", dry_run=True)
        self.assertEqual((dry["conversions"], dry["journeys"], dry["identities"]), (2, 1, 1))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM conversions").fetchone()[0], 3)
        got = store.forget(self.db, None, email="a@example.com")
        self.assertEqual((got["conversions"], got["deliveries"]), (2, 1))
        left = [r[0] for r in self.db.execute("SELECT vid FROM conversions")]
        self.assertEqual(left, [VID2])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM journeys").fetchone()[0], 0)
        self.assertEqual(store.forget(self.db, None, external_ref="L-2")["conversions"], 1)
        store.record_page_view(self.db, "example.com", VID2, "2026-10-10T10:00:00Z", "/", None)
        self.assertEqual(store.forget(self.db, "example.com", vid=VID2)["journeys"], 1)

    def test_day_counts_in_local_days(self):
        store.record_conversion(self.db, conv(at="2026-10-10T03:00:00Z"))     # 9th in NY
        store.record_conversion(self.db, conv(at="2026-10-10T15:00:00Z", external_ref="L-2"))
        got = store.day_counts(self.db, "example.com", ZoneInfo("America/New_York"),
                               date(2026, 10, 9), date(2026, 10, 10))
        self.assertEqual(got, {"2026-10-09": {("demo", "completed"): 1},
                               "2026-10-10": {("demo", "completed"): 1}})


class Geo(unittest.TestCase):
    def test_lookups(self):
        nets = {"192.0.2.0/24": "CA", "198.51.100.0/25": "US", "2001:db8::/32": "DE",
                "203.0.113.0/24": "ZZ"}
        with tempfile.TemporaryDirectory() as tmp:
            for version, size in ((6, 24), (6, 28), (6, 32), (4, 24)):
                path = Path(tmp) / f"c-{version}-{size}.mmdb"
                path.write_bytes(mmdb({k: v for k, v in nets.items()
                                       if version == 6 or ":" not in k}, version, size))
                where = f"v{version}/{size}"
                self.assertEqual(geo.country(path, "192.0.2.77"), "CA", where)
                self.assertEqual(geo.country(path, "198.51.100.5"), "US", where)
                self.assertIsNone(geo.country(path, "198.51.100.200"), where)
                self.assertIsNone(geo.country(path, "203.0.113.1"), "ZZ is unknown")
                self.assertIsNone(geo.country(path, "not an address"), where)
                if version == 6:
                    self.assertEqual(geo.country(path, "2001:db8::1"), "DE", where)
                else:
                    self.assertIsNone(geo.country(path, "2001:db8::1"), where)
            self.assertIsNone(geo.country(Path(tmp) / "missing.mmdb", "192.0.2.1"))
            self.assertIsNone(geo.country(None, "192.0.2.1"))
            junk = Path(tmp) / "junk.mmdb"
            junk.write_bytes(b"not a database")
            self.assertIsNone(geo.country(junk, "192.0.2.1"))


class Secrets(unittest.TestCase):
    def test_file_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = secrets_store.path_for({}, folder)
            self.assertEqual(secrets_store.find({}, folder, "example.com", "lead"), (None, ""))
            secrets_store.put(path, secrets_store.key("example.com", "lead"), "s1")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(secrets_store.find({}, folder, "example.com", "lead"), ("s1", "file"))
            nested = {"hooks": {"example.com": {"lead": {"secret_env": "TI_TEST_HOOK"}}}}
            flat = {"hooks": {"example.com/lead": "TI_TEST_HOOK"}}
            with mock.patch.dict(os.environ, {"TI_TEST_HOOK": "from-env"}):
                for config in (nested, flat):
                    self.assertEqual(secrets_store.find(config, folder, "example.com", "lead"),
                                     ("from-env", "env TI_TEST_HOOK"))
            os.chmod(path, 0o644)
            with self.assertRaises(secrets_store.Exposed):
                secrets_store.find({}, folder, "example.com", "lead")
            self.assertTrue(secrets_store.make().startswith("skh_"))


class Spool(unittest.TestCase):
    def test_append_read_scrub_prune(self):
        with tempfile.TemporaryDirectory() as tmp:
            where = Path(tmp) / "hooks"
            day = date(2026, 10, 10)
            spool.append(where, day, spool.line_for("t", "example.com", "lead",
                                                    {"vid": VID, "email": "a@example.com"}, False))
            spool.append(where, day, spool.line_for("t", "example.com", "lead",
                                                    {"vid": VID2}, False))
            self.assertEqual(stat.S_IMODE(spool.day_file(where, day).stat().st_mode), 0o640)
            rows = spool.read(where, day)
            self.assertEqual(rows[0]["body"], {"vid": VID}, "email taken out")
            gone = spool.scrub(where, lambda row, texts: VID.lower() in texts)
            self.assertEqual(gone, 1)
            self.assertEqual([r["body"]["vid"] for r in spool.read(where, day)], [VID2])
            self.assertEqual(spool.prune(where, date(2028, 1, 1)), 1)
            self.assertFalse(spool.day_file(where, day).exists())
            json.dumps(rows)


if __name__ == "__main__":
    unittest.main()
