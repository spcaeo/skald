"""`audit --live` while the log rotates or shrinks under it.

Seen live (2026-10-27) on a site whose logs are shipped: the shipped
`access.log` moved to `access.log.1` (the first batch of a new UTC day), or
was cut back, between the live run and its recount. The same file name then
held other bytes, and the audit reported a mismatch neither count had made.

Now the snapshot records which file it read (`read_ids`, the inode) beside
how far (`read_upto`). The audit looks before and after its recounts: a file
replaced, shrunk, gone or new means "skipped: the log rotated during the
check; run it again". With the files unchanged, every figure is compared as
before, so a real mismatch still fails.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit, log_moved, realtime_tail  # noqa: E402

from support import line  # noqa: E402
from test_realtime import NOON, Case, m  # noqa: E402


def fresh(n: int = 2) -> str:
    """Lines written to the new log after a rotation."""
    return "".join(line(m(1 - i * 0.1), "203.0.113.60", f"/after/{i}", country="NL")
                   for i in range(n))


class TestRotation(Case):
    @property
    def logs(self) -> Path:
        return self.box.root / "logs"

    @property
    def access(self) -> Path:
        return self.logs / "access.log"

    def stamp(self, *paths: Path) -> None:
        for path in paths:
            at = NOON.timestamp() - 30
            os.utime(path, (at, at))

    def rotate(self, text: str) -> None:
        """What ingest_log.Writer.rotate and logrotate do: the log moves to
        .1, and the next lines go to a new access.log."""
        os.replace(self.access, self.logs / "access.log.1")
        self.access.write_text(text)
        self.stamp(self.access, self.logs / "access.log.1")

    def snap_path(self) -> Path:
        return self.box.root / "live-example.com.json"

    def test_snapshot_records_which_file(self):
        snap = self.live()
        self.assertEqual(snap["read_ids"], {"access.log": self.access.stat().st_ino})

    def test_rotation_after_the_live_run_is_skipped_not_a_mismatch(self):
        self.live()
        self.rotate(fresh())
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit skipped: live", out)
        self.assertIn("the log rotated during the check", out)
        self.assertIn("run it again", out)
        self.assertNotIn("DOES NOT MATCH", err)

    def test_without_the_check_the_same_rotation_was_a_false_mismatch(self):
        """What happened before: the recount read the new file under the old name."""
        self.live()
        self.rotate(fresh())
        with mock.patch.object(log_moved, "moved", return_value=None):
            code, _, err = self.audit()
        self.assertEqual(code, 1)
        self.assertIn("DOES NOT MATCH", err)

    def test_new_file_larger_than_the_old_is_caught_by_its_inode(self):
        old = self.access.stat().st_size
        self.live()
        self.rotate(fresh(40))
        self.assertGreater(self.access.stat().st_size, old)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("access.log is a new file", out)

    def test_truncated_in_place_is_caught_by_its_size(self):
        """A crashed ingest append cut back (ingest_log.Writer._recover)."""
        self.live()
        with open(self.access, "r+b") as handle:
            handle.truncate(self.access.stat().st_size // 2)
        self.stamp(self.access)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("access.log shrank from", out)

    def test_rotation_while_the_audit_recounts(self):
        """Between the audit's own reads: the check after the recounts sees it."""
        self.live()
        real = audit.recount

        def then_rotate(*args, **kwargs):
            got = real(*args, **kwargs)
            self.rotate(fresh())
            return got
        with mock.patch.object(audit, "recount", then_rotate):
            code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit skipped: live", out)
        self.assertNotIn("DOES NOT MATCH", err)

    def test_a_real_mismatch_is_still_reported(self):
        snap = self.live()
        snap["requests"] += 1
        self.snap_path().write_text(json.dumps(snap))
        code, out, err = self.audit()
        self.assertEqual(code, 1)
        self.assertIn("requests for this site", err)
        self.assertNotIn("skipped", out)

    def test_appended_lines_are_not_a_rotation(self):
        self.live()
        with open(self.access, "a") as handle:
            handle.write(fresh())
        self.stamp(self.access)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: live", out)

    def test_older_snapshot_without_inodes(self):
        """No `read_ids`: a shrink, or a rotation that left a new name, still shows."""
        snap = self.live()
        del snap["read_ids"]
        self.snap_path().write_text(json.dumps(snap))
        self.rotate(fresh())
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit skipped: live", out)

    def test_older_snapshot_unchanged_files_still_audited(self):
        snap = self.live()
        del snap["read_ids"]
        self.snap_path().write_text(json.dumps(snap))
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: live", out)

    def test_tail_read_before_a_rotation_is_skipped(self):
        """The helper read the old file; the live run came after the rotation."""
        from skald.config import load_config
        got = realtime_tail.requests_now(load_config(self.box.config), NOON)
        self.assertEqual(got["read_ids"], {"access.log": self.access.stat().st_ino})
        realtime_tail.tail_path(self.box.root, "example.com").write_text(json.dumps(got))
        self.rotate(fresh())
        self.live()
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("real time requests (15-second count): skipped (the log rotated", out)
        self.assertIn("audit ok: live", out)


class TestMoved(unittest.TestCase):
    """The three signs, on their own."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "access.log"
        self.log.write_text("one\ntwo\n")

    def tearDown(self):
        self.tmp.cleanup()

    def record(self):
        return {"access.log": self.log.stat().st_size}, log_moved.ids([self.log])

    def test_unchanged_and_grown(self):
        upto, seen = self.record()
        self.assertIsNone(log_moved.moved(upto, seen, [self.log]))
        with open(self.log, "a") as handle:
            handle.write("three\n")
        self.assertIsNone(log_moved.moved(upto, seen, [self.log]))

    def test_no_record_checks_nothing(self):
        self.assertIsNone(log_moved.moved(None, None, [self.log]))
        self.assertIsNone(log_moved.moved({}, None, [self.log]))

    def test_gone_and_appeared(self):
        upto, seen = self.record()
        one = self.dir / "access.log.1"
        os.replace(self.log, one)
        self.assertEqual(log_moved.moved(upto, seen, [one]), "access.log is gone")
        self.log.write_text("x\n")
        self.assertIn("new file", log_moved.moved(upto, seen, [one, self.log]))
        self.assertEqual(log_moved.moved(upto, None, [one, self.log]), "access.log shrank "
                         "from 8 to 2 bytes")

    def test_an_operators_log_list_is_not_a_whole_set(self):
        """`--log` names some files: one missing or one extra is not a rotation."""
        upto, seen = self.record()
        other = self.dir / "copy.log"
        other.write_text("a\n")
        self.assertIsNone(log_moved.moved({**upto, "access.log.1": 5}, seen,
                                          [self.log, other], whole_set=False))
        self.assertEqual(log_moved.moved(upto, seen, [self.log, other]), "copy.log appeared")

    def test_compressed_rotations_are_not_looked_at(self):
        upto, seen = self.record()
        gz = self.dir / "access.log.2.gz"
        gz.write_bytes(b"")
        self.assertIsNone(log_moved.moved(upto, seen, [self.log, gz]))


if __name__ == "__main__":
    unittest.main()
