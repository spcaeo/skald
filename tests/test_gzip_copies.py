"""The gzip copy beside each data file (<name>.json.gz, files.write_atomic pack).

nginx sends the copy instead of the file to a browser that accepts gzip
(gzip_static, DEPLOY.md), so the copy must always hold the file's own bytes:
every run writes both, any later write of the file (a privacy redaction, an
older writer) refreshes or removes the copy, a crash leaves no copy rather
than an old one, and a small file gets none.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import files  # noqa: E402
from skald.files import GZ_MIN, packed, write_atomic  # noqa: E402

BIG = json.dumps({"rows": [{"path": f"/p{i}/", "n": i} for i in range(400)]})


def unpacked(path: Path) -> str:
    return gzip.decompress(packed(path).read_bytes()).decode("utf-8")


class WriteAtomic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data" / "pages.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_pack_writes_a_copy_equal_to_the_file(self):
        write_atomic(self.path, BIG, pack=True)
        self.assertEqual(unpacked(self.path), self.path.read_text())
        self.assertEqual(oct(packed(self.path).stat().st_mode & 0o777), "0o644")

    def test_the_same_bytes_give_the_same_copy(self):
        write_atomic(self.path, BIG, pack=True)
        first = packed(self.path).read_bytes()
        write_atomic(self.path, BIG, pack=True)
        self.assertEqual(packed(self.path).read_bytes(), first)

    def test_a_small_file_gets_no_copy(self):
        write_atomic(self.path, "{}", pack=True)
        self.assertFalse(packed(self.path).exists())
        self.assertLess(len("{}"), GZ_MIN)

    def test_a_file_that_shrinks_loses_its_copy(self):
        write_atomic(self.path, BIG, pack=True)
        write_atomic(self.path, "{}", pack=True)
        self.assertFalse(packed(self.path).exists())

    def test_a_writer_that_does_not_ask_still_refreshes_an_existing_copy(self):
        # privacy.py redacts a data file with a plain write_atomic: the copy follows.
        write_atomic(self.path, BIG, pack=True)
        other = BIG.replace("/p1/", "/(removed)/")
        write_atomic(self.path, other)
        self.assertEqual(unpacked(self.path), other)

    def test_no_copy_is_made_unasked(self):
        write_atomic(self.path, BIG)
        self.assertFalse(packed(self.path).exists())

    def test_a_crash_while_packing_leaves_no_old_copy(self):
        write_atomic(self.path, BIG, pack=True)
        new = BIG.replace("/p2/", "/q2/")
        with mock.patch.object(files.gzip, "compress", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                write_atomic(self.path, new, pack=True)
        self.assertEqual(self.path.read_text(), new)
        self.assertFalse(packed(self.path).exists(), "an old copy beside a new file")
        self.assertEqual([p.name for p in self.path.parent.iterdir() if p.name.endswith(".tmp")], [])

    def test_a_copy_of_bytes_another_writer_replaced_is_removed(self):
        # Two runs write the same file at once: the copy left must match the file, or be gone.
        mine = BIG.replace("/p3/", "/mine/")
        real = files._replace

        def theirs_in_between(path, data):
            inode = real(path, data)
            real(path, BIG.encode())           # another writer replaces the file just after
            return inode
        with mock.patch.object(files, "_replace", side_effect=theirs_in_between):
            write_atomic(self.path, mine, pack=True)
        self.assertEqual(self.path.read_text(), BIG)
        self.assertFalse(packed(self.path).exists())


class EveryDataFile(unittest.TestCase):
    """A real dashboard run: every data file of the site and of each view big
    enough to pack has its copy, and the copy is the file."""

    def test_the_dashboard_writes_matching_copies(self):
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
            checked = 0
            for path in sorted(site.rglob("data/*.json")):
                size = path.stat().st_size
                if path.name == "sites.json" or size < GZ_MIN:
                    continue
                with self.subTest(path=str(path.relative_to(site))):
                    self.assertTrue(packed(path).exists(), "no gzip copy")
                    self.assertEqual(unpacked(path), path.read_text())
                    checked += 1
            self.assertGreater(checked, 20)
            for gz in site.rglob("*.json.gz"):
                self.assertTrue(gz.with_suffix("").exists(), f"{gz.name} has no file beside it")
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
