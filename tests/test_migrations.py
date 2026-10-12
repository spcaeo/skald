"""Database migrations made explicit (migrations.py): `migrate --check`, the
steps read from each database's own upgrade code, `migrate` after a
restore-tested copy, the record, and the newer-schema guard on all three
databases. The expected steps come from the schema modules themselves, so a
new schema version elsewhere does not break these tests."""
from __future__ import annotations

import io
import json
import sqlite3
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import migrations, store  # noqa: E402
from skald.accounts import db as accounts_db  # noqa: E402
from skald.conversions import store as conversions_store  # noqa: E402
from skald.store import History  # noqa: E402

from support import Sandbox  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent


def migrate(box: Sandbox, *argv: str) -> tuple[int, str, str]:
    """`skald migrate ...` as skald runs it: before any other command code."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = migrations.main(["--config", str(box.config), "migrate", *argv])
    return code, out.getvalue(), err.getvalue()


def stamp(path: Path, version: int) -> None:
    db = sqlite3.connect(path)
    db.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'", (str(version),))
    db.commit()
    db.close()


def make_all(folder: Path) -> dict[str, Path]:
    paths = {"history": folder / "history.sqlite", "accounts": folder / "accounts.sqlite",
             "conversions": folder / "conversions.sqlite"}
    History(paths["history"]).close()
    accounts_db.connect(paths["accounts"]).close()
    conversions_store.connect(paths["conversions"]).close()
    return paths


class Inspect(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.paths = make_all(self.box.root)

    def tearDown(self):
        self.box.close()

    def rows(self):
        return {r["name"]: r for r in migrations.inspect({}, self.paths["history"])}

    def test_all_current(self):
        rows = self.rows()
        self.assertEqual(set(rows), {"history", "accounts", "conversions"})
        for name, row in rows.items():
            self.assertEqual(row["state"], "current", name)
            self.assertEqual(row["found"], row["code"])
        self.assertEqual(rows["history"]["code"], store.SCHEMA_VERSION)
        self.assertEqual(rows["accounts"]["code"], accounts_db.SCHEMA_VERSION)
        self.assertEqual(rows["conversions"]["code"], conversions_store.SCHEMA_VERSION)

    def test_absent_files(self):
        self.paths["conversions"].unlink()
        self.assertEqual(self.rows()["conversions"]["state"], "absent")

    def test_steps_come_from_each_databases_own_upgrade_code(self):
        for name, module in (("accounts", accounts_db), ("conversions", conversions_store)):
            code = module.SCHEMA_VERSION
            stamp(self.paths[name], code - 1)
            row = self.rows()[name]
            self.assertEqual((row["state"], row["found"]), ("pending", code - 1))
            expected = module.UPGRADES.get(code) or ["new version stamp"]
            self.assertEqual(len(row["steps"]), len(expected))
            self.assertTrue(all(s.startswith(f"v{code}: ") for s in row["steps"]))
            self.assertIn(" ".join(expected[0].split())[:40], row["steps"][0])

    def test_history_steps_from_store_lists(self):
        stamp(self.paths["history"], 8)
        row = self.rows()["history"]
        self.assertEqual(row["state"], "pending")
        self.assertIn("v9: add column days.extras", row["steps"])
        self.assertIn("v10: add table page_speed", row["steps"])
        self.assertIn("v11: add table page_milestones", row["steps"])
        versions = {int(s.split(":")[0][1:]) for s in row["steps"]}
        self.assertEqual(versions, set(range(9, store.SCHEMA_VERSION + 1)))

    def test_check_command_output(self):
        stamp(self.paths["accounts"], accounts_db.SCHEMA_VERSION - 1)
        code, out, _ = migrate(self.box, "--check")
        self.assertEqual(code, 0)
        self.assertRegex(out, rf"(?m)^history +schema {store.SCHEMA_VERSION} "
                              rf"\(code {store.SCHEMA_VERSION}\)  up to date")
        self.assertRegex(out, rf"(?m)^accounts +schema {accounts_db.SCHEMA_VERSION - 1} "
                              rf"\(code {accounts_db.SCHEMA_VERSION}\)  steps pending")
        self.assertRegex(out, rf"(?m)^    v{accounts_db.SCHEMA_VERSION}: ")
        code, out, _ = migrate(self.box, "--check", "--json")
        got = {r["name"]: r["state"] for r in json.loads(out)["databases"]}
        self.assertEqual(got["accounts"], "pending")


    def test_ti_py_sends_migrate_here_before_anything_opens_the_accounts(self):
        stamp(self.paths["accounts"], accounts_db.SCHEMA_VERSION - 1)
        got = subprocess.run([sys.executable, str(ROOT / "bin/skald"), "--config", str(self.box.config),
                              "migrate", "--check"], capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("steps pending", got.stdout)
        self.assertEqual(migrations.file_version(self.paths["accounts"]),
                         accounts_db.SCHEMA_VERSION - 1, "--check only looks")

    def test_command_of(self):
        self.assertEqual(migrations.command_of(["--config", "c.yml", "migrate", "--check"]), "migrate")
        self.assertEqual(migrations.command_of(["--today", "2026-10-01", "live"]), "live")
        self.assertEqual(migrations.command_of(["mark-deploy", "--label", "migrate"]), "mark-deploy")
        self.assertIsNone(migrations.command_of(["--config", "c.yml"]))


class Apply(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.paths = make_all(self.box.root)

    def tearDown(self):
        self.box.close()

    def test_migrate_copies_first_then_upgrades_and_records(self):
        code_version = accounts_db.SCHEMA_VERSION
        stamp(self.paths["accounts"], code_version - 1)
        code, out, err = migrate(self.box)
        self.assertEqual(code, 0, err)
        self.assertIn("copied and restore-tested every database", out)
        self.assertIn(f"accounts: schema {code_version - 1} -> {code_version}", out)
        self.assertEqual(migrations.file_version(self.paths["accounts"]), code_version)
        copies = list((self.box.root / "backups").glob("pre-migrate-*/accounts.sqlite"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(migrations.file_version(copies[0]), code_version - 1)
        record = migrations.history_of(self.box.root)
        self.assertEqual([(r["db"], r["from"], r["to"]) for r in record],
                         [("accounts", code_version - 1, code_version)])
        self.assertIn("at", record[0])
        code, out, _ = migrate(self.box)
        self.assertEqual((code, out.strip()), (0, "every database is up to date: nothing to do"))

    def test_snapshot_and_restore(self):
        folder = self.box.root / "snap"
        self.paths["conversions"].unlink()
        taken, problems = migrations.snapshot({}, self.paths["history"], folder)
        self.assertEqual(problems, [])
        self.assertEqual({t["name"]: t["copy"] is None for t in taken},
                         {"history": False, "accounts": False, "conversions": True})
        db = sqlite3.connect(self.paths["history"])
        db.execute("INSERT INTO meta (key, value) VALUES ('after', 'the copy')")
        db.commit()
        db.close()
        conversions_store.connect(self.paths["conversions"]).close()    # made by "new code"
        self.assertEqual(migrations.restore(taken), [])
        db = sqlite3.connect(self.paths["history"])
        self.assertIsNone(db.execute("SELECT 1 FROM meta WHERE key = 'after'").fetchone())
        db.close()
        self.assertFalse(self.paths["conversions"].exists())


class NewerSchemaGuard(unittest.TestCase):
    """Old code never opens a file a newer Skald wrote: each database says so."""

    def setUp(self):
        self.box = Sandbox(mail=False)
        self.paths = make_all(self.box.root)

    def tearDown(self):
        self.box.close()

    def test_each_database_refuses_a_newer_file(self):
        opens = {"history": lambda p: History(p).close(),
                 "accounts": lambda p: accounts_db.connect(p).close(),
                 "conversions": lambda p: conversions_store.connect(p).close()}
        for name, module in (("history", store), ("accounts", accounts_db),
                             ("conversions", conversions_store)):
            stamp(self.paths[name], module.SCHEMA_VERSION + 1)
            with self.assertRaisesRegex(RuntimeError, "upgrade skald before reading it"):
                opens[name](self.paths[name])
            self.assertEqual(migrations.file_version(self.paths[name]), module.SCHEMA_VERSION + 1)

    def test_migrate_refuses_and_changes_nothing(self):
        newer = conversions_store.SCHEMA_VERSION + 1
        stamp(self.paths["conversions"], newer)
        stamp(self.paths["accounts"], accounts_db.SCHEMA_VERSION - 1)
        self.assertEqual(len(migrations.guard({}, self.paths["history"])), 1)
        code, out, _ = migrate(self.box, "--check")
        self.assertEqual(code, 1)
        self.assertIn("NEWER than this code", out)
        self.assertIn(f"conversions.sqlite is schema {newer}", out)
        code, _, err = migrate(self.box)
        self.assertEqual(code, 1)
        self.assertIn("migrate REFUSED: nothing was changed", err)
        self.assertEqual(migrations.file_version(self.paths["accounts"]),
                         accounts_db.SCHEMA_VERSION - 1, "nothing opened, nothing upgraded")
        done, problems = migrations.apply({}, self.paths["history"],
                                          datetime(2026, 10, 21, tzinfo=timezone.utc))
        self.assertEqual(done, [])
        self.assertTrue(problems)


class ReadOnlyGuard(unittest.TestCase):
    """The helper's read-only opener refuses a history newer than the code too."""

    def test_reader_refuses_a_newer_history(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.sqlite"
            store.History(path).db.close()
            db = sqlite3.connect(path)
            db.execute("UPDATE meta SET value = ? WHERE key = 'schema_version'",
                       (str(store.SCHEMA_VERSION + 1),))
            db.commit()
            db.close()
            with self.assertRaises(RuntimeError):
                store.History.reader(path)

    def test_reader_opens_a_current_history(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.sqlite"
            store.History(path).db.close()
            store.History.reader(path).db.close()


if __name__ == "__main__":
    unittest.main()
