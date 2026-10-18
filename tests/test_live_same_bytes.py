"""The live run and `audit --live` count the same bytes.

The shipper appends to the live log every few seconds. A live run records
each plain file's size at its start (`read_upto`) and reads only that far;
the live audit, run later, reads only as far too. So lines appended between
the two - even ones stamped before the snapshot's `until` - change neither
side, and a line still being written at the limit is read by neither.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit, parse, realtime_tail  # noqa: E402

from support import line  # noqa: E402
from test_realtime import IPHONE, NOON, Case, m  # noqa: E402


def late() -> list[str]:
    """Lines written after the snapshot, all stamped before its `until`."""
    return [
        line(m(1), "203.0.113.30", "/late", IPHONE, country="JP"),
        line(m(0.5), "203.0.113.30", "/late/two", IPHONE, country="JP"),
        line(m(0.2), "203.0.113.11", "/docs/more", country="CA"),
        line(m(4), "198.51.100.43", "/robots.txt", "curl/8.7.1"),
    ]


class TestSameBytes(Case):
    @property
    def access(self) -> Path:
        return self.box.root / "logs" / "access.log"

    def append(self, text: str) -> None:
        with open(self.access, "a") as handle:
            handle.write(text)
        stamp = NOON.timestamp() - 30
        os.utime(self.access, (stamp, stamp))

    def snapshot(self) -> dict:
        return json.loads((self.box.root / "live-example.com.json").read_text())

    def test_snapshot_records_the_sizes(self):
        size = self.access.stat().st_size
        snap = self.live()
        self.assertEqual(snap["read_upto"], {"access.log": size})
        feed = json.loads((self.box.root / "live-example.com-requests.json").read_text())
        self.assertEqual(feed["read_upto"], {"access.log": size})

    def test_lines_appended_after_the_snapshot_are_not_recounted(self):
        before = self.live()
        self.append("".join(late()))
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: live", out)
        # The next run reads them, and its audit agrees too.
        after = self.live()
        self.assertEqual(after["requests"], before["requests"] + 4)
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)

    def test_without_the_limit_the_appended_lines_disagree(self):
        """What happened before: the audit read the grown file whole."""
        self.live()
        self.append("".join(late()))
        path = self.box.root / "live-example.com.json"
        snap = self.snapshot()
        del snap["read_upto"]
        path.write_text(json.dumps(snap))
        code, _, err = self.audit()
        self.assertEqual(code, 1)
        self.assertIn("requests for this site", err)

    def test_partial_last_line_is_read_by_neither(self):
        whole = line(m(1.5), "203.0.113.31", "/half", country="NL")
        cut = len(whole) // 2
        self.append(whole[:cut])                    # still being written
        snap = self.live()
        self.assertEqual(snap["read_upto"]["access.log"], self.access.stat().st_size)
        self.assertNotIn("NL", json.dumps(snap["realtime"]["countries"]))
        self.assertEqual(snap["unparsed"], 0)
        self.append(whole[cut:] + "".join(late()))   # finished, and more after it
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        # The next run reads the finished line.
        snap = self.live()
        self.assertIn("NL", snap["realtime"]["countries"])

    def test_older_snapshot_without_limits_reads_whole_files(self):
        self.live()
        for name in ("live-example.com.json", "live-example.com-requests.json"):
            path = self.box.root / name
            data = json.loads(path.read_text())
            del data["read_upto"]
            path.write_text(json.dumps(data))
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: live", out)

    def test_tail_count_reads_the_same_bytes(self):
        from skald.config import load_config
        self.live()
        got = realtime_tail.requests_now(load_config(self.box.config), NOON)
        self.assertEqual(got["read_upto"], {"access.log": self.access.stat().st_size})
        realtime_tail.tail_path(self.box.root, "example.com").write_text(json.dumps(got))
        self.append("".join(late()))
        code, _, err = self.audit()
        self.assertEqual(code, 0, err)


class TestReaders(unittest.TestCase):
    """Both roads' readers, each on its own: whole lines inside the limit."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "access.log"
        self.lines = [line(NOON - timedelta(seconds=i), "203.0.113.40", f"/p{i}")
                      for i in range(3)]
        self.path.write_text("".join(self.lines) + self.lines[0][:20])

    def tearDown(self):
        self.tmp.cleanup()

    def test_limits(self):
        size = self.path.stat().st_size
        whole = len("".join(self.lines).encode())
        for limit, n in ((size, 3), (whole, 3), (whole - 1, 2), (0, 0),
                         (len(self.lines[0]), 1)):
            upto = {"access.log": limit}
            self.assertEqual(len(list(parse.lines_of(self.path, upto))), n, limit)
            self.assertEqual(len(list(audit.raw_lines(self.path, upto))), n, limit)
            self.assertEqual(len(list(parse.read([self.path], upto=upto))), n, limit)
            self.assertEqual(len(list(audit._read([self.path], upto))), n, limit)

    def test_no_limit_reads_everything(self):
        # The cut line at the end is read (and does not parse), as before.
        self.assertEqual(len(list(parse.lines_of(self.path))), 4)
        self.assertEqual(len(list(audit.raw_lines(self.path, {"other.log": 5}))), 4)

    def test_sizes_skip_compressed(self):
        gz = Path(self.tmp.name) / "access.log.2.gz"
        gz.write_bytes(b"")
        self.assertEqual(parse.sizes([self.path, gz]),
                         {"access.log": self.path.stat().st_size})

    def test_tail_drops_the_cut_line(self):
        size = self.path.stat().st_size
        lines, short = realtime_tail.tail_lines(self.path, NOON - timedelta(hours=1), size)
        self.assertEqual(len(lines), 3)
        self.assertFalse(short)
        whole = len("".join(self.lines).encode())
        lines, _ = realtime_tail.tail_lines(self.path, NOON - timedelta(hours=1), whole - 5)
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
