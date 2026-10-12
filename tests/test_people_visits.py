"""2.4.0: visits kept with their address, the upgrade rule, and their audit.

Addresses are RFC 5737; the host is example.com.
"""
from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import Sandbox, day_lines  # noqa: E402

from skald import migrations, store as history_store  # noqa: E402
from skald.conversions import store  # noqa: E402
from skald.people import policy  # noqa: E402

DAY = date(2026, 10, 6)


def visits(box: Sandbox, sql: str = "SELECT ip, pages, day FROM visits ORDER BY seq"):
    db = sqlite3.connect(box.root / "conversions.sqlite")
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


class Policy(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.config = {"history": {"db": str(self.box.db)}}

    def tearDown(self):
        self.box.close()

    def test_a_new_install_keeps_addresses_and_emails(self):
        self.assertFalse(policy.legacy(self.config))
        self.assertTrue(policy.keep_ips(self.config))
        self.assertTrue(policy.identity_full(self.config))
        history_store.History(self.box.db).close()          # a new file at schema 13
        self.assertFalse(policy.legacy(self.config))
        self.assertEqual(policy.keep_days(self.config), 395)

    def test_an_upgraded_install_keeps_what_it_did(self):
        history_store.History(self.box.db).close()
        db = sqlite3.connect(self.box.db)
        db.execute("UPDATE meta SET value = '12' WHERE key = 'schema_version'")
        db.commit()
        db.close()
        # Before the upgrade has run (a hook arriving first): already legacy.
        self.assertTrue(policy.legacy(self.config))
        h = history_store.History(self.box.db)               # the upgrade to 13
        self.assertEqual(h.migrated_from, 12)
        self.assertIsNotNone(h.db.execute("SELECT value FROM meta WHERE key = "
                                          "'privacy_legacy'").fetchone())
        h.close()
        self.assertTrue(policy.legacy(self.config))
        self.assertFalse(policy.keep_ips(self.config))
        self.assertFalse(policy.identity_full(self.config))
        on = {**self.config, "privacy": {"keep_ips": True},
              "conversions": {"identity": "full"}}
        self.assertTrue(policy.keep_ips(on))
        self.assertTrue(policy.identity_full(on))
        self.assertFalse(policy.keep_ips({**self.config, "privacy": {"keep_ips": "false"}}))

    def test_migrate_check_names_the_step(self):
        self.assertIn("v13: add meta privacy_legacy", migrations.steps("history", 12, 13))
        self.assertTrue(any("ADD COLUMN test" in s for s in migrations.steps("conversions", 3)))

    def test_settings_say_upgrade(self):
        from skald import settings_store
        history_store.History(self.box.db).close()
        db = sqlite3.connect(self.box.db)
        db.execute("INSERT INTO meta (key, value) VALUES ('privacy_legacy', 'x')")
        db.commit()
        db.close()
        got = settings_store.explain(self.config, "example.com", live_dir=self.box.root)
        self.assertEqual(got["privacy.keep_ips"], {"value": False, "source": "upgrade",
                                                   "locked": False})
        self.assertEqual(got["conversions.identity"]["value"], "anonymous")
        self.assertEqual(got["privacy.keep_days"]["value"], 395)

    def test_docker_env(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docker"))
        import entrypoint
        self.assertNotIn("privacy", entrypoint.render_config({}))
        got = entrypoint.render_config({"SKALD_KEEP_IPS": "0", "SKALD_IDENTITY": "anonymous"})
        self.assertEqual(got["privacy"], {"keep_ips": False})
        self.assertEqual(got["conversions"], {"identity": "anonymous"})
        with self.assertRaises(SystemExit):
            entrypoint.render_config({"SKALD_IDENTITY": "everything"})


class KeptVisits(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        self.box.log(day_lines(DAY, 4))

    def tearDown(self):
        self.box.close()

    def collect(self, *extra):
        code, out, err = self.box.run("--today", "2026-10-07", *extra, "collect")
        self.assertEqual(code, 0, err)

    def test_one_row_per_reader_with_its_address(self):
        self.collect()
        got = visits(self.box)
        self.assertEqual([r[0] for r in got], [f"203.0.113.{10 + i}" for i in range(4)])
        self.assertEqual({r[2] for r in got}, {"2026-10-06"})
        row = visits(self.box, "SELECT state, visits, pages FROM visit_days")[0]
        self.assertEqual(row, ("whole", 4, 4))
        ua = visits(self.box, "SELECT user_agent, source, trail FROM visits WHERE seq = 0")[0]
        self.assertIn("Chrome", ua[0])
        self.assertEqual(ua[1], "AI assistant")

    def test_the_audit_matches_then_catches_a_changed_row(self):
        self.collect()
        code, out, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-06")
        self.assertEqual(code, 0, out + err)
        db = sqlite3.connect(self.box.root / "conversions.sqlite")
        db.execute("UPDATE visits SET ip = '203.0.113.99' WHERE seq = 1")
        db.commit()
        db.close()
        code, out, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-06")
        self.assertEqual(code, 1)
        self.assertIn("addresses whose kept visits differ", err)
        self.assertNotIn("203.0.113", err, "no address in a problem")

    def test_the_audit_catches_a_missing_visit(self):
        self.collect()
        db = sqlite3.connect(self.box.root / "conversions.sqlite")
        db.execute("DELETE FROM visits WHERE seq = 3")
        db.commit()
        db.close()
        code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-06")
        self.assertEqual(code, 1)
        self.assertIn("visits kept with an address", err)

    def test_nothing_kept_when_the_site_says_no(self):
        self.box.config.write_text(self.box.config.read_text() + "privacy:\n  keep_ips: false\n")
        self.collect()
        self.assertFalse((self.box.root / "conversions.sqlite").exists())

    def test_forget_deletes_the_address_and_hides_it_later(self):
        self.collect()
        code, out, err = self.box.run("forget", "--ip", "203.0.113.11")
        self.assertEqual(code, 0, err)
        self.assertIn("1 kept visit", out)
        self.assertNotIn(("203.0.113.11",), visits(self.box, "SELECT ip FROM visits"))
        self.collect()                       # collected again: the address stays hidden
        ips = [r[0] for r in visits(self.box, "SELECT ip FROM visits ORDER BY seq")]
        self.assertEqual(ips[1], "(removed)")
        code, out, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-06")
        self.assertEqual(code, 0, out + err)

    def test_pruned_after_keep_days_and_when_turned_off(self):
        self.collect()
        self.box.config.write_text(self.box.config.read_text() + "privacy:\n  keep_days: 1\n")
        self.box.log(day_lines(DAY, 4) + day_lines(date(2026, 10, 7), 1))
        code, _, err = self.box.run("--today", "2026-10-08", "collect")
        self.assertEqual(code, 0, err)
        self.assertEqual({r[0] for r in visits(self.box, "SELECT day FROM visits")},
                         {"2026-10-07"})
        self.box.config.write_text(self.box.config.read_text().replace(
            "keep_days: 1", "keep_days: 1\n  keep_ips: false"))
        code, _, err = self.box.run("--today", "2026-10-08", "collect")
        self.assertEqual(visits(self.box, "SELECT COUNT(*) FROM visits"), [(0,)])


class ConversionsSchema4(unittest.TestCase):
    def test_a_v3_file_gets_the_test_mark_and_the_tables(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conversions.sqlite"
            db = store.connect(path)
            db.executescript("DROP TABLE visits; DROP TABLE visit_days; DROP TABLE removed;")
            db.execute("CREATE TABLE c2 AS SELECT id, site, action, stage, at, vid, "
                       "external_ref, tool, source_type, first_source, campaign, landing, "
                       "country, device, first_touch_at, visits_before, identity_id, "
                       "received_at FROM conversions")
            db.executescript("DROP TABLE conversions; ALTER TABLE c2 RENAME TO conversions;")
            db.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
            db.execute("DELETE FROM meta WHERE key = 'schema_stamp'")
            db.close()
            db = store.connect(path)
            try:
                self.assertEqual(store.schema_version(db), 4)
                cols = {r[1] for r in db.execute("PRAGMA table_info(conversions)")}
                self.assertIn("test", cols)
                have = {r[0] for r in db.execute("SELECT name FROM sqlite_master")}
                self.assertTrue({"visits", "visit_days", "removed"} <= have)
            finally:
                db.close()
            self.assertTrue((Path(tmp) / "conversions.sqlite.v3.bak").exists())


if __name__ == "__main__":
    unittest.main()
