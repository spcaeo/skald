"""The app's slim copies of the biggest data files (slim.py, audit_slim.py):

  * each leaves out only the parts the app never draws, keeps every row in
    order and every value it keeps is the full file's;
  * the audit catches a copy that changes, adds or drops anything, and then
    no copy is written (the app reads the full file);
  * a real dashboard run writes them for the site and each view, with their
    gzip copies, lists them in app.json, and they reconcile with the files.
"""
from __future__ import annotations

import copy
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_slim, slim  # noqa: E402
from skald.files import packed  # noqa: E402

copy_of = copy.deepcopy
ENVELOPE = {"schema_version": 1, "generated_at": "2026-10-07T12:00:00Z", "site": "example.com",
            "view": None, "timezone": "UTC"}


def pages_body():
    row = lambda p, v: {  # noqa: E731
        "path": p, "views": v, "readers": v - 1, "entries": 2, "exits": 1, "exit_rate": None,
        "ai_asked": 1, "time_estimate": False, "change_pct": 0.5,
        "daily": {"2026-10-05": v - 1, "2026-10-06": 1}, "sources": {"Search engine": 2},
        "countries": {"US": 2}, "assistants": {"ChatGPT": 1},
        "prev": {"views": v // 2, "readers": 1, "sources": {"Direct or unknown": 1}, "countries": {}}}
    return {**ENVELOPE, "period": {"first": "2026-09-08", "last": "2026-10-07", "days": 30},
            "pages": [row("/a/", 9), row("/b/", 4), row("/a/", 1)],
            "today": {"state": "ok", "pages": [{"path": "/a/", "views": 3}]}}


def not_found_body():
    rows = [{"path": "/old/", "n": 3, "group": "people", "status": 404}]
    return {**ENVELOPE,
            "days": [{"day": "2026-10-06", "state": "ok", "rows": rows, "totals": {"all": 3, "people": 3}},
                     {"day": "2026-10-05", "state": "missing"}],
            "today": {"state": "ok", "rows": rows, "totals": {"all": 3}},
            "paths": [{"path": "/old/", "n": 3, "trend": {"2026-10-06": 3}}]}


def page_index_body():
    return {**ENVELOPE, "meta": {"source": "website"},
            "pages": [{"path": "/a/", "published": "2026-09-01", "updated": None, "views_30d": 9,
                       "lastmod_seen": [["2026-09-01", "2026-09-02"]],
                       "milestones": {"googlebot": "2026-09-02T01:00:00", "human": None,
                                      "bingbot": "2026-09-03T01:00:00", "lead": None}}]}


class Projections(unittest.TestCase):
    def test_pages_keeps_every_row_and_count(self):
        full = pages_body()
        copy, left = slim.pages(full)
        self.assertEqual([r["path"] for r in copy["pages"]], ["/a/", "/b/", "/a/"])
        for r, f in zip(copy["pages"], full["pages"]):
            for gone in slim.PAGE_PARTS:
                self.assertNotIn(gone, r)
                self.assertNotIn(gone, r["prev"])
            for k in ("views", "readers", "entries", "exits", "exit_rate", "ai_asked", "change_pct"):
                self.assertEqual(r[k], f[k])
            self.assertEqual(r["prev"]["views"], f["prev"]["views"])
        self.assertEqual(copy["today"], full["today"])
        self.assertEqual(copy["period"], full["period"])
        self.assertIn("pages[].daily", left)
        self.assertIn("daily", full["pages"][0], "the full file was changed")
        self.assertEqual(audit_slim.problems(full, {**copy, "slim": {}}), [])

    def test_not_found_keeps_the_totals_and_the_paths(self):
        full = not_found_body()
        copy, _ = slim.not_found(full)
        self.assertEqual(copy["days"], [{"day": "2026-10-06", "state": "ok", "totals": {"all": 3, "people": 3}},
                                        {"day": "2026-10-05", "state": "missing"}])
        self.assertEqual(copy["paths"], full["paths"])
        self.assertEqual(copy["today"], full["today"])
        self.assertEqual(audit_slim.problems(full, {**copy, "slim": {}}), [])

    def test_page_index_keeps_what_the_table_shows(self):
        full = page_index_body()
        copy, _ = slim.page_index(full)
        row = copy["pages"][0]
        self.assertNotIn("lastmod_seen", row)
        self.assertEqual(row["milestones"], {"googlebot": "2026-09-02T01:00:00", "human": None})
        self.assertEqual((row["published"], row["updated"], row["views_30d"]), ("2026-09-01", None, 9))
        self.assertEqual(copy["meta"], full["meta"])
        self.assertEqual(audit_slim.problems(full, {**copy, "slim": {}}), [])


class Audit(unittest.TestCase):
    def ok(self):
        full = pages_body()
        return full, copy_of({**slim.pages(full)[0], "slim": {"of": "pages.json"}})

    def test_a_changed_figure(self):
        full, copy = self.ok()
        copy["pages"][1]["views"] += 1
        self.assertTrue(audit_slim.problems(full, copy))

    def test_a_dropped_row(self):
        full, copy = self.ok()
        copy["pages"].pop()
        self.assertTrue(audit_slim.problems(full, copy))

    def test_rows_reordered(self):
        full, copy = self.ok()
        copy["pages"].reverse()
        self.assertTrue(audit_slim.problems(full, copy))

    def test_an_added_key_or_a_number_turned_text(self):
        full, copy = self.ok()
        copy["pages"][0]["extra"] = 1
        self.assertTrue(audit_slim.problems(full, copy))
        full, copy = self.ok()
        copy["pages"][0]["views"] = "9"
        self.assertTrue(audit_slim.problems(full, copy))
        full, copy = self.ok()
        copy["pages"][0]["time_estimate"] = 0     # False is not 0
        self.assertTrue(audit_slim.problems(full, copy))

    def test_a_changed_day_total(self):
        full = not_found_body()
        copy = copy_of({**slim.not_found(full)[0], "slim": {}})
        copy["days"][0]["totals"]["people"] = 2
        self.assertTrue(audit_slim.problems(full, copy))

    def test_no_note(self):
        full = pages_body()
        self.assertEqual(audit_slim.problems(full, slim.pages(full)[0]), ["no slim note"])


class Write(unittest.TestCase):
    def test_written_with_its_gzip_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            full = pages_body()
            path = slim.write(Path(tmp), "pages", full)
            self.assertEqual(path, Path(tmp) / "data" / "slim" / "pages.json")
            got = json.loads(path.read_text())
            self.assertEqual(got["slim"]["of"], "pages.json")
            self.assertEqual(audit_slim.problems(full, got), [])
            self.assertEqual(slim.listed(Path(tmp) / "data"), ["pages"])

    def test_a_copy_that_does_not_match_is_not_written_and_the_old_one_goes(self):
        with tempfile.TemporaryDirectory() as tmp:
            big = {**pages_body(), "pages": pages_body()["pages"] * 40}
            path = slim.write(Path(tmp), "pages", big)
            self.assertTrue(packed(path).exists())
            with mock.patch.object(audit_slim, "problems", return_value=["a test"]):
                self.assertIsNone(slim.write(Path(tmp), "pages", big))
            self.assertFalse(path.exists())
            self.assertFalse(packed(path).exists())
            self.assertEqual(slim.listed(Path(tmp) / "data"), [])

    def test_a_failed_file_has_no_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = slim.write(Path(tmp), "pages", pages_body())
            self.assertIsNone(slim.write(Path(tmp), "pages", {**ENVELOPE, "state": "error", "error": "x"}))
            self.assertFalse(path.exists())


class RealRun(unittest.TestCase):
    """A dashboard run: the copies beside the site's and each view's files."""

    def test_the_run_writes_copies_that_reconcile(self):
        from support import Sandbox
        from test_views import VIEWS, mixed_day
        box = Sandbox(views=VIEWS)
        try:
            box.config.write_text(box.config.read_text().replace("  app: false\n", "  app: true\n"))
            box.log(mixed_day())
            self.assertEqual(box.run("--today", "2026-10-07", "collect")[0], 0)
            code, _, err = box.run("--today", "2026-10-07", "dashboard")
            self.assertEqual(code, 0, err)
            site = box.root / "www" / "example.com"
            folders = [p.parent for p in site.rglob("data/app.json")]
            self.assertGreater(len(folders), 1, "no view folders")
            for data in folders:
                app = json.loads((data / "app.json").read_text())
                self.assertEqual(app["slim"], sorted(slim.NAMES), data)
                for name in slim.NAMES:
                    with self.subTest(folder=str(data.relative_to(site)), name=name):
                        full = json.loads((data / f"{name}.json").read_text())
                        copy_path = data / "slim" / f"{name}.json"
                        copy = json.loads(copy_path.read_text())
                        self.assertEqual(audit_slim.problems(full, copy), [])
                        self.assertEqual(copy["slim"]["of"], f"{name}.json")
                        # Never bigger than the file, but for its own note.
                        note = len(json.dumps({"slim": copy["slim"]}, ensure_ascii=False, separators=(",", ":")))
                        self.assertLessEqual(copy_path.stat().st_size, (data / f"{name}.json").stat().st_size + note)
                        if packed(copy_path).exists():
                            self.assertEqual(gzip.decompress(packed(copy_path).read_bytes()),
                                             copy_path.read_bytes())
            # The API's names stay the files' own: no slim copy is listed among them.
            self.assertNotIn("slim", json.loads((site / "data" / "app.json").read_text())["files"])
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
