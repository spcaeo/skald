"""One failing data file must not stop the redraw (builders.py): an optional
file is written as an error and listed in quality.json, the traceback is said
once, the rest are written; a core file still stops the run."""
from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import data_files, data_more  # noqa: E402

from support import Sandbox, day_lines  # noqa: E402


def broken(page):
    raise KeyError("people")


class TestOneFileFails(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.box.log(day_lines(date(2026, 10, 5), 3))
        assert self.box.run("--today", "2026-10-06", "collect")[0] == 0
        self.data = self.box.root / "www" / "example.com" / "data"

    def tearDown(self):
        self.box.close()

    def redraw(self, extra):
        real = data_more.builders()
        with mock.patch.object(data_more, "builders", return_value={**real, **extra}):
            return self.box.run("--today", "2026-10-06", "dashboard")

    def test_the_rest_is_written_and_quality_says_which(self):
        code, out, err = self.redraw({"robots": broken})
        self.assertEqual(code, 0, err)
        robots = json.loads((self.data / "robots.json").read_text())
        self.assertEqual((robots["state"], robots["error"]), ("error", "KeyError: 'people'"))
        self.assertIn("generated_at", robots)
        for name in ("overview", "bots", "leads", "funnels", "page_index"):
            self.assertNotEqual(json.loads((self.data / f"{name}.json").read_text()).get("state"),
                                "error", name)
        quality = json.loads((self.data / "quality.json").read_text())
        self.assertEqual([f["file"] for f in quality["builders_failing"]], ["robots.json"])
        self.assertIn("Traceback", err)
        # Said once: the same error on the next redraw stays quiet, keeps its "since".
        since = quality["builders_failing"][0]["since"]
        code, out, err = self.redraw({"robots": broken})
        self.assertNotIn("Traceback", err)
        again = json.loads((self.data / "quality.json").read_text())
        self.assertEqual(again["builders_failing"][0]["since"], since)
        # Fixed: it leaves the list.
        code, out, err = self.redraw({})
        self.assertEqual(json.loads((self.data / "quality.json").read_text())["builders_failing"],
                         [])
        self.assertNotEqual(json.loads((self.data / "robots.json").read_text()).get("state"),
                            "error")

    def test_a_core_file_still_stops_the_run(self):
        with mock.patch.dict(data_files.BUILDERS, {"overview": broken}):
            with self.assertRaises(KeyError):
                with redirect_stderr(io.StringIO()):
                    self.box.run("--today", "2026-10-06", "dashboard")


if __name__ == "__main__":
    unittest.main()


class TestOutsideNotSetUp(unittest.TestCase):
    def test_ours_says_no_outside_check(self):
        box = Sandbox()
        try:
            box.log(day_lines(date(2026, 10, 5), 2))
            self.assertEqual(box.run("--today", "2026-10-06", "collect")[0], 0)
            self.assertEqual(box.run("--today", "2026-10-06", "dashboard")[0], 0)
            ours = json.loads((box.root / "www" / "example.com" / "data" / "ours.json").read_text())
            self.assertIn("outside", ours)
            self.assertIsNone(ours["outside"])
        finally:
            box.close()
