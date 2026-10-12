"""skald forget --ip: the private lists, the visitor hashes, the forgotten list."""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import Sandbox  # noqa: E402
from skald import privacy, visitors  # noqa: E402
from skald.store import History  # noqa: E402

GONE = "192.0.2.7"
KEPT = "198.51.100.9"
KEY = "test-visitor-key"


def _events(ip_a: str, ip_b: str) -> dict:
    return {"version": 1, "day": "2026-10-07",
            "events": [{"name": "GPTBot", "ip": ip_a}, {"name": "chatgpt.com", "ip": ip_b},
                       {"name": "GPTBot", "ip": ip_a}]}


class TestForget(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)
        root = self.box.root
        ai = root / "live-example.com-ai.json"
        ai.write_text(json.dumps(_events(GONE, KEPT), indent=1) + "\n")
        os.chmod(ai, 0o640)
        (root / "live-example.com-requests.json").write_text(
            json.dumps({"rows": [{"ip": GONE, "path": "/"}, {"ip": KEPT, "path": "/a"}]}))
        for page in ("www/example.com/data", "www/example.com/us-english/data"):
            (root / page).mkdir(parents=True)
            (root / page / "ai_activity.json").write_text(
                json.dumps({"today": _events(GONE, KEPT)}, separators=(",", ":")) + "\n")
            (root / page / "requests.json").write_text(
                json.dumps({"rows": [{"ip": GONE}, {"ip": KEPT}]}) + "\n")
            (root / page / "overview.json").write_text('{"ip": "%s"}\n' % GONE)
        with History(self.box.db) as h:
            visitors.record(h.db, "example.com", date(2026, 10, 6), {
                (visitors.visitor_hash(KEY.encode(), GONE, "Chrome/macOS"), "reader"): [1, ""],
                (visitors.visitor_hash(KEY.encode(), GONE, "GPTBot"), "training"): [3, ""],
                (visitors.visitor_hash(KEY.encode(), KEPT, "Chrome/macOS"), "reader"): [1, ""],
            })
            h.db.commit()

    def tearDown(self):
        self.box.close()

    def _rows(self) -> int:
        with History(self.box.db) as h:
            return h.db.execute("SELECT COUNT(*) FROM visitor_days").fetchone()[0]

    def test_forget_removes_the_address_everywhere_it_is_kept(self):
        with mock.patch.dict(os.environ, {visitors.ENV: KEY}):
            code, out, err = self.box.run("forget", "--ip", GONE)
        self.assertEqual(code, 0, err)
        root = self.box.root
        ai = root / "live-example.com-ai.json"
        got = json.loads(ai.read_text())
        self.assertEqual([e["ip"] for e in got["events"]], ["(removed)", KEPT, "(removed)"])
        self.assertEqual(os.stat(ai).st_mode & 0o777, 0o640)
        for page in ("www/example.com/data", "www/example.com/us-english/data"):
            text = (root / page / "requests.json").read_text()
            self.assertNotIn(GONE, text)
            self.assertIn(KEPT, text)
            self.assertNotIn(GONE, (root / page / "ai_activity.json").read_text())
            # Only the private lists are touched.
            self.assertIn(GONE, (root / page / "overview.json").read_text())
        self.assertEqual(self._rows(), 1)
        self.assertIn("2 row(s) deleted", out)
        self.assertNotIn(KEPT, out)
        self.assertNotIn(GONE, out)
        for name in ("forgotten.json", "privacy.log"):
            text = (root / name).read_text()
            self.assertNotIn(GONE, text)
        self.assertIn(privacy.digest(GONE)[:12], (root / "privacy.log").read_text())

    def test_the_next_runs_keep_it_removed(self):
        self.box.run("forget", "--ip", GONE)
        test = privacy.forgotten(self.box.root)
        self.assertTrue(test(GONE))
        self.assertFalse(test(KEPT))
        later = datetime.now(timezone.utc) + timedelta(days=privacy.KEEP_DAYS + 1)
        self.assertFalse(privacy.forgotten(self.box.root, later)(GONE))

    def test_without_the_key_hashes_are_not_matched(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(visitors.ENV, None)
            code, out, _ = self.box.run("forget", "--ip", GONE)
        self.assertEqual(code, 0)
        self.assertIn("no visitor key", out)
        self.assertEqual(self._rows(), 3)

    def test_dry_run_changes_nothing(self):
        before = (self.box.root / "live-example.com-requests.json").read_text()
        with mock.patch.dict(os.environ, {visitors.ENV: KEY}):
            code, out, _ = self.box.run("forget", "--ip", GONE, "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("2 row(s) found", out)
        self.assertEqual((self.box.root / "live-example.com-requests.json").read_text(), before)
        self.assertEqual(self._rows(), 3)
        self.assertFalse((self.box.root / "forgotten.json").exists())

    def test_not_an_address(self):
        self.assertEqual(self.box.run("forget", "--ip", "not-an-ip")[0], 2)


class TestForgottenList(unittest.TestCase):
    def test_no_list_forgets_nothing(self):
        self.assertFalse(privacy.forgotten(None)(GONE))
        self.assertFalse(privacy.forgotten(Path("/nonexistent"))(GONE))

    def test_remember_twice_keeps_one_entry(self):
        with _Tmp() as tmp:
            privacy.remember(tmp, GONE)
            privacy.remember(tmp, GONE)
            entries = json.loads((tmp / privacy.FORGOTTEN).read_text())["entries"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["sha256"], privacy.digest(GONE))


class _Tmp:
    def __enter__(self) -> Path:
        import tempfile
        self._t = tempfile.TemporaryDirectory()
        return Path(self._t.name)

    def __exit__(self, *exc) -> None:
        self._t.cleanup()


if __name__ == "__main__":
    unittest.main()
