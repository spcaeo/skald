"""SKALD-23: Data quality says when a site's log holds a CDN's addresses, not the visitors'.

The day's quality blob counts the lines whose address is a CDN edge's (`cdn_lines`, by the
CDN list bot_verify keeps; None when no list is kept), the audit counts them again from the
raw lines with its own list, and quality.json carries them for the Data quality page (which
warns at half the lines or more: tests/js/cdn-screens.mjs). A day stored before the figure
existed is not compared, so it is never withheld for it.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import UTC, Sandbox, line  # noqa: E402
from test_cdn_addresses import EDGE, lists  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
VISITOR = "203.0.113.20"


class TheDay(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        folder = lists(self.box.root / "ranges")
        self.box.config.write_text(self.box.config.read_text()
                                   + f"bots:\n  ranges_dir: {folder}\n")
        at = datetime(DAY.year, DAY.month, DAY.day, 10, tzinfo=UTC)
        self.box.log([line(at + timedelta(minutes=i), EDGE, f"/p{i}") for i in range(9)]
                     + [line(at + timedelta(minutes=30), VISITOR, "/")])

    def tearDown(self):
        self.box.close()

    def blob(self) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return json.loads(db.execute(
                "SELECT data FROM day_extras WHERE site = ? AND day = ? AND kind = 'quality'",
                ("example.com", DAY.isoformat())).fetchone()[0])
        finally:
            db.close()

    def audit(self):
        return self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())

    def test_the_cdn_lines_are_counted_and_the_audit_agrees(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        self.assertEqual(self.blob()["cdn_lines"], 9)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_a_disagreeing_count_is_a_mismatch(self):
        self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self._store(cdn_lines=3)
        code, out, err = self.audit()
        self.assertEqual(code, 1)
        self.assertIn("lines from a CDN's addresses: history has 3, the recount finds 9", out + err)

    def test_a_day_stored_before_the_figure_is_not_withheld_for_it(self):
        self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self._store(cdn_lines=None, drop=True)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def _store(self, cdn_lines=None, drop=False):
        db = sqlite3.connect(str(self.box.db))
        try:
            blob = self.blob()
            if drop:
                blob.pop("cdn_lines", None)
            else:
                blob["cdn_lines"] = cdn_lines
            db.execute("UPDATE day_extras SET data = ? WHERE site = ? AND day = ? AND kind = 'quality'",
                       (json.dumps(blob), "example.com", DAY.isoformat()))
            db.commit()
        finally:
            db.close()


class TheDoctor(unittest.TestCase):
    """`skald doctor` and the Set-up list: "Visitor addresses" (doctor.visitor_addresses)."""

    def run_doctor(self, lines_, with_list=True):
        from skald import doctor
        from skald.config import load_config
        box = Sandbox()
        try:
            if with_list:
                folder = lists(box.root / "ranges")
                box.config.write_text(box.config.read_text() + f"bots:\n  ranges_dir: {folder}\n")
            box.log(lines_)
            return doctor.visitor_addresses(load_config(box.config), datetime.now(UTC))
        finally:
            box.close()

    def at(self, i):
        return datetime(DAY.year, DAY.month, DAY.day, 10, tzinfo=UTC) + timedelta(seconds=i)

    def test_mostly_cdn_needs_attention_with_the_fix(self):
        got = self.run_doctor([line(self.at(i), EDGE, "/") for i in range(9)]
                              + [line(self.at(9), VISITOR, "/")])
        self.assertEqual(got["state"], "NEEDS ATTENTION")
        self.assertIn("90% of the log's last 10 lines carry Cloudflare's address", got["says"])
        self.assertIn("real_ip_header CF-Connecting-IP", got["fix"])

    def test_mostly_visitors_is_ok(self):
        got = self.run_doctor([line(self.at(i), VISITOR, "/") for i in range(9)]
                              + [line(self.at(9), EDGE, "/")])
        self.assertEqual(got["state"], "OK")

    def test_no_list_is_off(self):
        got = self.run_doctor([line(self.at(0), EDGE, "/")], with_list=False)
        self.assertEqual(got["state"], "OFF")


class WithoutTheList(unittest.TestCase):
    def test_not_recorded_not_zero(self):
        box = Sandbox()
        try:
            at = datetime(DAY.year, DAY.month, DAY.day, 10, tzinfo=UTC)
            box.log([line(at, EDGE, "/")])
            code, _, err = box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err)
            db = sqlite3.connect(str(box.db))
            try:
                blob = json.loads(db.execute(
                    "SELECT data FROM day_extras WHERE kind = 'quality'").fetchone()[0])
            finally:
                db.close()
            self.assertIsNone(blob["cdn_lines"])
        finally:
            box.close()


@unittest.skipUnless(__import__("shutil").which("node"), "node is not installed")
class Screens(unittest.TestCase):
    """tests/js/cdn-screens.mjs: Data quality, the block list, the crawler check, scanners."""

    def test_the_screens(self):
        import subprocess
        js = Path(__file__).resolve().parent / "js" / "cdn-screens.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("cdn-screens: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
