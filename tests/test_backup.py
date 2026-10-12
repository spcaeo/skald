"""skald backup: daily and weekly copies, pruning, and the restore test."""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import Sandbox, day_lines  # noqa: E402
from skald import backup  # noqa: E402
from skald.store import History  # noqa: E402


def _fill(db: Path) -> None:
    with History(db) as h:
        h.db.execute("INSERT INTO meta (key, value) VALUES ('test', 'x') "
                     "ON CONFLICT(key) DO NOTHING")
        h.db.commit()


class TestCopy(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        _fill(self.box.db)
        self.folder = self.box.root / "backups"

    def tearDown(self):
        self.box.close()

    def test_a_copy_is_restored_and_matches_the_source(self):
        written, problems = backup.make(self.box.db, self.folder, date(2026, 10, 7))
        self.assertEqual(problems, [])
        names = sorted(p.name for p in written)
        self.assertEqual(names, ["history-2026-10-07.sqlite",
                                 "history-weekly-2026-W41.sqlite.gz"])
        daily = self.folder / "history-2026-10-07.sqlite"
        self.assertEqual(os.stat(daily).st_mode & 0o777, 0o640)
        manifest = json.loads((self.folder / (daily.name + ".counts.json")).read_text())
        self.assertIn("days", manifest["tables"])
        self.assertIn("visitor_days", manifest["tables"])
        with gzip.open(self.folder / "history-weekly-2026-W41.sqlite.gz", "rb") as f:
            self.assertTrue(f.read(16).startswith(b"SQLite format 3"))

    def test_a_write_after_the_copy_does_not_fail_the_check(self):
        backup.make(self.box.db, self.folder, date(2026, 10, 7))
        db = sqlite3.connect(self.box.db)
        db.execute("INSERT INTO meta (key, value) VALUES ('later', 'y')")
        db.commit()
        db.close()
        self.assertEqual(backup.verify(backup.newest(self.folder)), [])

    def test_a_damaged_copy_fails_the_restore_test(self):
        backup.make(self.box.db, self.folder, date(2026, 10, 7))
        daily = self.folder / "history-2026-10-07.sqlite"
        db = sqlite3.connect(daily)
        db.execute("DELETE FROM meta")
        db.commit()
        db.close()
        problems = backup.verify(daily)
        self.assertTrue(any("table meta" in p for p in problems), problems)

    def test_garbage_is_not_a_backup(self):
        self.folder.mkdir()
        bad = self.folder / "history-2026-10-07.sqlite"
        bad.write_bytes(b"not a database at all" * 100)
        (self.folder / (bad.name + ".counts.json")).write_text('{"tables": {"meta": 1}}')
        self.assertTrue(backup.verify(bad))

    def test_daily_copies_are_pruned_with_their_counts(self):
        start = date(2026, 10, 1)
        for i in range(17):
            backup.make(self.box.db, self.folder, start + timedelta(days=i), keep=14,
                        weekly_keep=2)
        dailies = sorted(p.name for p in self.folder.glob("history-2*.sqlite"))
        self.assertEqual(len(dailies), 14)
        self.assertEqual(dailies[0], "history-2026-10-04.sqlite")
        self.assertFalse((self.folder / "history-2026-10-03.sqlite.counts.json").exists())
        self.assertEqual(len(list(self.folder.glob("history-weekly-*.gz"))), 2)

    def test_one_weekly_copy_per_week_refreshed_on_sunday(self):
        backup.make(self.box.db, self.folder, date(2026, 10, 6))     # Tuesday
        weekly = self.folder / "history-weekly-2026-W41.sqlite.gz"
        first = weekly.stat().st_mtime_ns
        written, _ = backup.make(self.box.db, self.folder, date(2026, 10, 7))
        self.assertNotIn(weekly, written)
        self.assertEqual(weekly.stat().st_mtime_ns, first)
        written, _ = backup.make(self.box.db, self.folder, date(2026, 10, 11))  # Sunday
        self.assertIn(weekly, written)


class TestCommand(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.box.log(day_lines(date(2026, 10, 6), 3))
        self.assertEqual(self.box.run("--today", "2026-10-07", "collect")[0], 0)

    def tearDown(self):
        self.box.close()

    def test_backup_verify_and_pull(self):
        code, out, err = self.box.run("--today", "2026-10-07", "backup")
        self.assertEqual(code, 0, err)
        self.assertIn("restore test ok", out)
        self.assertTrue((self.box.root / "backups" / "history-2026-10-07.sqlite").exists())
        runs = json.loads((self.box.root / "runs.json").read_text())
        self.assertEqual(runs["backup"]["last_exit"], 0)
        code, out, _ = self.box.run("--today", "2026-10-07", "backup", "--verify")
        self.assertEqual(code, 0)
        self.assertIn("row counts match", out)
        code, out, _ = self.box.run("backup", "--pull")
        self.assertEqual(code, 0)
        self.assertIn("scp -i ~/.ssh/<your-key> root@<server>:", out)
        self.assertIn("history-2026-10-07.sqlite ~/Downloads/", out)

    def test_accounts_and_conversions_are_copied_too(self):
        import sqlite3
        for stem in ("accounts", "conversions"):
            db = sqlite3.connect(self.box.root / f"{stem}.sqlite")
            db.execute("CREATE TABLE t (x)")
            db.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)])
            db.commit()
            db.close()
        code, out, err = self.box.run("--today", "2026-10-07", "backup")
        self.assertEqual(code, 0, err)
        for stem in ("accounts", "conversions"):
            copy = self.box.root / "backups" / f"{stem}-2026-10-07.sqlite"
            self.assertTrue(copy.exists(), stem)
            self.assertTrue((self.box.root / "backups" /
                             f"{stem}-weekly-2026-W41.sqlite.gz").exists(), stem)
            got = sqlite3.connect(copy).execute("SELECT COUNT(*) FROM t").fetchone()[0]
            self.assertEqual(got, 2)
        self.assertEqual(sorted(p.name for p in (self.box.root / "backups").glob("history-*.sqlite")),
                         ["history-2026-10-07.sqlite"])

    def test_without_them_only_the_history_is_copied(self):
        code, out, err = self.box.run("--today", "2026-10-07", "backup")
        self.assertEqual(code, 0, err)
        names = {p.name.split("-")[0] for p in (self.box.root / "backups").glob("*.sqlite")}
        self.assertEqual(names, {"history"})

    def test_pull_with_nothing_to_pull(self):
        code, _, err = self.box.run("backup", "--pull", "--dir", str(self.box.root / "none"))
        self.assertEqual(code, 1)
        self.assertIn("no backup", err)

    def test_a_failed_restore_test_exits_one_and_is_recorded(self):
        self.box.run("--today", "2026-10-07", "backup")
        daily = self.box.root / "backups" / "history-2026-10-07.sqlite"
        db = sqlite3.connect(daily)
        db.execute("DELETE FROM days")
        db.commit()
        db.close()
        code, _, err = self.box.run("backup", "--verify")
        self.assertEqual(code, 1)
        self.assertIn("table days", err)
        runs = json.loads((self.box.root / "runs.json").read_text())
        self.assertEqual(runs["backup"]["last_exit"], 1)

    def test_config_dir_and_host(self):
        text = self.box.config.read_text() + "backup:\n  dir: copies\n  ssh_host: 192.0.2.5\n"
        self.box.config.write_text(text)
        self.assertEqual(self.box.run("--today", "2026-10-07", "backup")[0], 0)
        self.assertTrue((self.box.root / "copies" / "history-2026-10-07.sqlite").exists())
        _, out, _ = self.box.run("backup", "--pull")
        self.assertIn("root@192.0.2.5:", out)


if __name__ == "__main__":
    unittest.main()
