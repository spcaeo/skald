"""History files written by older code are upgraded in place on open."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, check, dashboard  # noqa: E402
from skald.store import SCHEMA_VERSION, History  # noqa: E402

from support import UTC, day_lines, totals_for  # noqa: E402


SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS days (
    site TEXT NOT NULL, day TEXT NOT NULL, timezone TEXT NOT NULL,
    collected_at TEXT NOT NULL, verified INTEGER NOT NULL,
    problems TEXT NOT NULL DEFAULT '', parsed INTEGER NOT NULL,
    hits INTEGER NOT NULL, other_hosts INTEGER NOT NULL,
    cited_visits INTEGER NOT NULL, first_seen TEXT, last_seen TEXT,
    PRIMARY KEY (site, day));
CREATE TABLE IF NOT EXISTS groups (
    site TEXT NOT NULL, day TEXT NOT NULL, grp TEXT NOT NULL,
    hits INTEGER NOT NULL, views INTEGER NOT NULL, visits INTEGER NOT NULL,
    probes INTEGER NOT NULL, PRIMARY KEY (site, day, grp));
CREATE TABLE IF NOT EXISTS counts (
    site TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL,
    name TEXT NOT NULL, n INTEGER NOT NULL,
    PRIMARY KEY (site, day, kind, name));
INSERT INTO meta VALUES ('schema_version', '1');
INSERT INTO days VALUES ('example.com', '2026-10-05', 'UTC',
    '2026-10-06T07:15:00+00:00', 1, '', 8, 7, 1, 1,
    '2026-10-05T12:00:00+00:00', '2026-10-05T13:04:00+00:00');
INSERT INTO groups VALUES
    ('example.com', '2026-10-05', 'people', 3, 3, 3, 0),
    ('example.com', '2026-10-05', 'answer_engines', 2, 2, 2, 0),
    ('example.com', '2026-10-05', 'search_engines', 1, 1, 1, 0),
    ('example.com', '2026-10-05', 'bots', 1, 0, 1, 1);
INSERT INTO counts VALUES
    ('example.com', '2026-10-05', 'engine_tier', 'training', 1),
    ('example.com', '2026-10-05', 'engine_tier', 'asked', 1),
    ('example.com', '2026-10-05', 'cited_by', 'chatgpt.com', 1),
    ('example.com', '2026-10-05', 'people_page', '/', 2);
"""


class TestSchemaUpgrade(unittest.TestCase):
    """A history file written by older code is upgraded in place on open:
    columns added, data untouched, a copy kept, all or nothing."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "history.sqlite"
        old = sqlite3.connect(str(self.path))
        old.executescript(SCHEMA_V1)
        old.close()
        self.day = date(2026, 10, 5)

    def tearDown(self):
        self._tmp.cleanup()

    def columns(self, path):
        db = sqlite3.connect(str(path))
        try:
            return {r[1] for r in db.execute("PRAGMA table_info(days)")}
        finally:
            db.close()

    def test_a_version_1_file_opens_and_is_upgraded(self):
        with History(self.path) as h:
            self.assertEqual(h.migrated_from, 1)
            self.assertEqual(h.schema_version, SCHEMA_VERSION)
            self.assertEqual(h.sites(), ["example.com"])
        self.assertTrue({"unfiltered", "scope"} <= self.columns(self.path))

    def test_the_old_rows_survive_and_the_new_count_is_unknown_not_zero(self):
        with History(self.path) as h:
            row = h.db.execute(
                "SELECT parsed, hits, other_hosts, unfiltered, cited_visits "
                "FROM days WHERE day = '2026-10-05'").fetchone()
            self.assertEqual(row, (8, 7, 1, None, 1))
            period = h.period("example.com", self.day, self.day)
            page = dashboard.render(h, "example.com", UTC,
                                    datetime(2026, 10, 6, 12, tzinfo=UTC))
        self.assertEqual(period.recorded, [self.day])
        self.assertEqual(period.unmeasured, [self.day])
        self.assertEqual(check(period.totals), [])
        self.assertEqual(period.totals.groups[Group.PEOPLE].visits, 3)
        self.assertIn("collected by an older version", page)

    def test_new_days_can_be_written_after_the_upgrade(self):
        """The failure seen on the server: record() into a v1 file said
        "table days has no column named unfiltered"."""
        later = date(2026, 10, 6)
        with History(self.path) as h:
            h.record("example.com", later, totals_for(day_lines(later, 2)), "UTC", [])
            period = h.period("example.com", self.day, later)
            stored = h.db.execute(
                "SELECT unfiltered FROM days WHERE day = '2026-10-06'").fetchone()[0]
        self.assertEqual(period.recorded, [self.day, later])
        self.assertEqual(period.unmeasured, [self.day])
        self.assertEqual(stored, 0)
        self.assertEqual(check(period.totals), [])

    def test_a_copy_of_the_old_file_is_kept_and_never_overwritten(self):
        History(self.path).close()
        backup = self.path.with_name("history.sqlite.schema-v1.bak")
        self.assertTrue(backup.exists())
        self.assertNotIn("unfiltered", self.columns(backup))
        before = backup.stat().st_mtime_ns
        with History(self.path) as h:
            self.assertIsNone(h.migrated_from)
        self.assertEqual(backup.stat().st_mtime_ns, before)

    def test_a_file_stamped_1_that_already_has_the_columns_is_only_restamped(self):
        """Files written between a column arriving and the version bump."""
        from skald.store import ADDED_COLUMNS, ADDED_TABLES
        db = sqlite3.connect(str(self.path))
        for _, table, column, definition in ADDED_COLUMNS:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        for _, _, sql in ADDED_TABLES:      # and the tables added since
            db.execute(sql)
        db.execute("UPDATE days SET unfiltered = 0")
        db.commit()
        db.close()
        with History(self.path) as h:
            self.assertEqual(h.migrated_from, 1)
            self.assertEqual(h.schema_version, SCHEMA_VERSION)
        self.assertFalse(self.path.with_name("history.sqlite.schema-v1.bak").exists())

    def test_a_failed_upgrade_changes_nothing(self):
        from skald import store
        broken = store.ADDED_COLUMNS + [(2, "days", "broken", "NOT VALID SQL (")]
        with mock.patch.object(store, "ADDED_COLUMNS", broken):
            with self.assertRaises(sqlite3.OperationalError):
                History(self.path)
        self.assertNotIn("unfiltered", self.columns(self.path))
        db = sqlite3.connect(str(self.path))
        try:
            self.assertEqual(db.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()[0], "1")
        finally:
            db.close()
        with History(self.path) as h:  # and a good upgrade still works after
            self.assertEqual(h.schema_version, SCHEMA_VERSION)




class TestSchemaUpgradeFromV2(unittest.TestCase):
    """Version 2 (90cb011 to 22deffa): unfiltered, no scope. Every row in it
    is a whole-site row, and must still be one after the upgrade."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "history.sqlite"
        old = sqlite3.connect(str(self.path))
        old.executescript(SCHEMA_V1.replace(
            "'schema_version', '1'", "'schema_version', '2'"))
        old.execute("ALTER TABLE days ADD COLUMN unfiltered INTEGER")
        old.execute("UPDATE days SET unfiltered = 0")
        old.commit()
        old.close()
        self.day = date(2026, 10, 5)

    def tearDown(self):
        self._tmp.cleanup()

    def test_it_upgrades_to_the_current_version_keeping_every_row(self):
        with History(self.path) as h:
            self.assertEqual(h.migrated_from, 2)
            self.assertEqual(h.schema_version, SCHEMA_VERSION)
            self.assertEqual(h.sites(), ["example.com"])
            row = h.db.execute("SELECT hits, unfiltered, scope FROM days").fetchone()
            self.assertEqual(row, (7, 0, None))
            period = h.period("example.com", self.day, self.day)
        self.assertEqual(period.unmeasured, [])
        self.assertEqual(check(period.totals), [])
        self.assertTrue(self.path.with_name("history.sqlite.schema-v2.bak").exists())

    def test_view_rows_written_after_it_are_not_sites(self):
        from skald.store import view_key
        with History(self.path) as h:
            h.record(view_key("example.com", "canada-french"), self.day,
                     totals_for(day_lines(self.day, 1)), "UTC", [],
                     scope="paths under /ca/fr/")
            self.assertEqual(h.sites(), ["example.com"])
            got = h.period(view_key("example.com", "canada-french"), self.day, self.day)
        self.assertEqual(got.recorded, [self.day])


if __name__ == "__main__":
    unittest.main()
