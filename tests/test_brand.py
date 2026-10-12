"""The brand (NAME, VERSION, TAGLINE, build.json) in what readers see: the
mail's sender name, subject prefix and footer, the report header."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import brand, mailer  # noqa: E402
from skald.store import History  # noqa: E402

from support import SECRETS, UTC, Sandbox, day_lines, totals_for  # noqa: E402

SKALD = {"name": "Skald", "version": "1.0.0", "tagline": "Every visit, truly told.",
         "release": 57, "commit": "abc1234", "deployed_at": "2026-10-07T20:30:00Z"}


class TestSource(unittest.TestCase):
    def test_files_then_build_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(brand.load(root)["name"], "skald")
            brand.load.cache_clear()
            for name, text in (("NAME", "Skald\n"), ("VERSION", "1.0.0\n"),
                               ("TAGLINE", "Every visit, truly told.\n")):
                (root / name).write_text(text)
            got = brand.load(root)
            self.assertEqual((got["name"], got["version"], got["release"]), ("Skald", "1.0.0", None))
            self.assertEqual(brand.line(got), "Skald v1.0.0 · Every visit, truly told.")
            brand.load.cache_clear()
            (root / "build.json").write_text(json.dumps({"name": "Skald", "version": "1.0.1",
                                                         "release": 57, "commit": "abc1234"}))
            got = brand.load(root)
            self.assertEqual(brand.line(got), "Skald v1.0.1 · release 57 · Every visit, truly told.")
            brand.load.cache_clear()


class TestMail(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.history = History(self.box.db)
        day = date(2026, 10, 5)
        self.history.record("example.com", day, totals_for(day_lines(day, 3)), "UTC", [])
        self.patch = mock.patch("skald.brand.load", return_value=SKALD)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.history.close()
        self.box.close()

    def build(self, text_change=("", "")):
        from skald.config import load_config
        self.box.config.write_text(self.box.config.read_text().replace(*text_change))
        with mock.patch.dict(os.environ, SECRETS):
            return mailer.build("daily", load_config(self.box.config), self.history, UTC,
                                datetime(2026, 10, 6, 9, tzinfo=UTC))

    def test_sender_subject_and_footer(self):
        msg = self.build(('  subject_prefix: "[traffic]"\n', ""))
        self.assertEqual(msg["From"], "Skald <traffic@example.com>")
        self.assertEqual(msg["Subject"], "[Skald] example.com: daily traffic, Mon 5 Oct 2026")
        text = msg.get_body(("plain",)).get_content()
        self.assertTrue(text.rstrip().endswith(
            "-- \nSkald v1.0.0 · release 57 · Every visit, truly told."))
        self.assertIn("Every visit, truly told.", msg.get_body(("html",)).get_content())

    def test_the_config_can_still_name_its_own(self):
        msg = self.build(("  from: traffic@example.com\n",
                          "  from: Ops <traffic@example.com>\n  from_name: Acme traffic\n"))
        self.assertEqual(msg["From"], "Acme traffic <traffic@example.com>")
        self.assertTrue(msg["Subject"].startswith("[traffic] "))


class TestReportAndCommand(unittest.TestCase):
    def test_report_header_and_version(self):
        box = Sandbox()
        try:
            with History(box.db) as h:
                for i in range(7):
                    d = date(2026, 10, 5) - timedelta(days=i)
                    h.record("example.com", d, totals_for(day_lines(d, 2)), "UTC", [])
            out = box.root / "r.html"
            with mock.patch("skald.brand.load", return_value=SKALD):
                self.assertEqual(box.run("--today", "2026-10-06", "report", "--out", str(out))[0], 0)
                code, text, err = box.run("version")
            self.assertIn("Skald v1.0.0 · release 57 · Every visit, truly told.", out.read_text())
            self.assertEqual(code, 0)
            self.assertIn("Skald v1.0.0 · release 57", text)
            self.assertIn("commit abc1234", text)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
