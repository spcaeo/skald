"""The accounts file: created with its tables, reopened, refused when newer."""
from __future__ import annotations

import os
import sqlite3
import stat
import unittest
from pathlib import Path

from accounts_support import AccountsCase

from skald.accounts import db as base


class SchemaTest(AccountsCase):
    def test_tables_and_version(self) -> None:
        names = {r[0] for r in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table in ("meta", "orgs", "users", "members", "sites", "sessions", "invites",
                      "resets", "tokens", "settings", "audit", "attempts", "recovery"):
            self.assertIn(table, names)
        self.assertEqual(base.schema_version(self.db), base.SCHEMA_VERSION)

    def test_wal_and_foreign_keys(self) -> None:
        self.assertEqual(self.db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_file_is_0640(self) -> None:
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o640)

    def test_reopen_keeps_rows(self) -> None:
        self.db.execute("INSERT INTO orgs (name, slug, created_at) VALUES ('A', 'a', 'x')")
        self.db.close()
        self.db = base.connect(self.path)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 1)
        self.assertEqual(base.schema_version(self.db), base.SCHEMA_VERSION)

    def test_newer_file_is_refused(self) -> None:
        self.db.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
        self.db.close()
        with self.assertRaises(RuntimeError):
            base.connect(self.path)
        self.db = base.connect(self.dir / "other.sqlite")

    def test_install_key_made_once(self) -> None:
        one = base.keyed_hash(self.db, "203.0.113.10")
        self.db.close()
        self.db = base.connect(self.path)
        self.assertEqual(base.keyed_hash(self.db, "203.0.113.10"), one)
        self.assertNotIn("203.0.113.10", one)
        self.assertNotEqual(base.keyed_hash(self.db, "203.0.113.11"), one)

    def test_now_shape(self) -> None:
        self.assertRegex(base.now(), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(base.shift(3600), "2026-10-11T15:00:00Z")

    def test_path_for(self) -> None:
        self.assertEqual(base.path_for({}, Path("/srv/h")), Path("/srv/h/accounts.sqlite"))
        self.assertEqual(base.path_for({"access": {"accounts": "/x/a.sqlite"}}, None),
                         Path("/x/a.sqlite"))

    def test_tx_rolls_back(self) -> None:
        with self.assertRaises(ZeroDivisionError):
            with base.tx(self.db):
                self.db.execute("INSERT INTO orgs (name, slug, created_at) VALUES ('A','a','x')")
                1 / 0
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 0)
        self.assertIsInstance(self.db, sqlite3.Connection)


if __name__ == "__main__":
    unittest.main()
