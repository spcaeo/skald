"""The request id (rid=, nginx's $request_id) at the end of a log line.

A line repeating an earlier line's request id is the same request written
twice: it is dropped and counted as "duplicates removed". Lines without one
(written before the field was added) are kept and their exact repeats are
flagged as before. The package's reader and the independent audit agree.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import UTC, Sandbox, line  # noqa: E402

from skald import audit, audit_release2  # noqa: E402
from skald.parse import PARSERS, ReadStats, read  # noqa: E402

RID_A = "0123456789abcdef0123456789abcdef"
RID_B = "fedcba9876543210fedcba9876543210"
NOON = datetime(2026, 10, 5, 12, tzinfo=UTC)


def with_rid(raw: str, rid: str) -> str:
    return raw.rstrip("\n") + f" rid={rid}\n"


class TestParsing(unittest.TestCase):

    def test_new_lines_carry_the_request_id(self):
        got = PARSERS["nginx_extended"](with_rid(line(NOON), RID_A))
        self.assertEqual((got.rid, got.country, got.request_time), (RID_A, "US", 0.004))

    def test_old_lines_have_none_and_read_as_before(self):
        old = PARSERS["nginx_extended"](line(NOON))
        new = PARSERS["nginx_extended"](with_rid(line(NOON), RID_A))
        self.assertEqual(old.rid, "")
        self.assertEqual((old.url, old.status, old.user_agent, old.country, old.size),
                         (new.url, new.status, new.user_agent, new.country, new.size))

    def test_the_live_servers_layout(self):
        raw = ('2026-10-08T11:40:01+00:00 192.0.2.7 www.example.com "GET / HTTP/2.0" 200 5 '
               f'"-" "curl/8" 0.001 cc=US ray=- rid={RID_A}')
        self.assertEqual(PARSERS["nginx_extended"](raw).rid, RID_A)
        self.assertEqual(audit.line_hit(raw).rid, RID_A)

    def test_an_empty_country_does_not_lose_it(self):
        raw = with_rid(line(NOON).replace("cc=US", "cc="), RID_A)
        self.assertEqual(PARSERS["nginx_extended"](raw).rid, RID_A)
        self.assertEqual(audit.line_hit(raw).rid, RID_A)

    def test_the_audit_reads_old_lines_too(self):
        self.assertEqual(audit.line_hit(line(NOON)).rid, "")


class TestDropping(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "access.log"

    def tearDown(self):
        self._tmp.cleanup()

    def read(self, lines):
        self.path.write_text("".join(lines))
        stats = ReadStats()
        return list(read([self.path], stats=stats)), stats

    def test_a_repeated_request_id_is_dropped_and_counted(self):
        first = with_rid(line(NOON), RID_A)
        hits, stats = self.read([first, first, with_rid(line(NOON), RID_B)])
        self.assertEqual([h.rid for h in hits], [RID_A, RID_B])
        self.assertEqual((stats.lines, len(stats.removed)), (3, 1))
        self.assertEqual(stats.removed_in(NOON, NOON + timedelta(seconds=1)), 1)
        self.assertEqual(stats.removed_in(NOON + timedelta(seconds=1), NOON + timedelta(hours=1)), 0)

    def test_the_same_id_in_a_later_file_is_still_a_repeat(self):
        other = Path(self._tmp.name) / "access.log.1"
        other.write_text(with_rid(line(NOON), RID_A))
        self.path.write_text(with_rid(line(NOON), RID_A))
        stats = ReadStats()
        self.assertEqual(len(list(read([other, self.path], stats=stats))), 1)
        self.assertEqual(len(stats.removed), 1)

    def test_a_real_repeat_has_its_own_id_and_stays(self):
        hits, stats = self.read([with_rid(line(NOON), RID_A), with_rid(line(NOON), RID_B)])
        self.assertEqual(len(hits), 2)
        self.assertEqual(stats.removed, [])

    def test_lines_without_an_id_are_all_kept(self):
        hits, stats = self.read([line(NOON), line(NOON)])
        self.assertEqual(len(hits), 2)
        self.assertEqual(stats.removed, [])

    def test_the_audits_reader_drops_the_same_lines(self):
        first = with_rid(line(NOON), RID_A)
        self.path.write_text("".join([first, first, line(NOON), line(NOON)]))
        self.assertEqual(len(list(audit._read([self.path]))), 3)
        got = audit_release2.quality([self.path], NOON, NOON + timedelta(hours=1),
                                     audit.line_hit)
        self.assertEqual((got["parsed"], got["duplicates_removed"], got["duplicates"]),
                         (3, 1, 1))


class TestDayFigures(unittest.TestCase):
    """A day with a doubled request, a real repeat and two old identical
    lines: one line dropped, the rest counted, and the audit agrees."""

    def test_collect_audit_and_quality_json(self):
        box = Sandbox()
        try:
            doubled = with_rid(line(NOON, "203.0.113.20", "/"), RID_A)
            box.log([line(NOON - timedelta(hours=1), "203.0.113.30", "/old"),
                     line(NOON - timedelta(hours=1), "203.0.113.30", "/old"),
                     doubled, doubled,
                     with_rid(line(NOON, "203.0.113.20", "/"), RID_B),
                     with_rid(line(NOON + timedelta(hours=1), "203.0.113.21", "/a"),
                              "00000000000000000000000000000001")])
            code, out, err = box.run("--today", "2026-10-06", "collect")
            self.assertEqual(code, 0, err)
            with sqlite3.connect(box.db) as db:
                q = json.loads(db.execute(
                    "SELECT data FROM day_extras WHERE site = 'example.com' AND day = "
                    "'2026-10-05' AND kind = 'quality'").fetchone()[0])
                lines = db.execute("SELECT lines_read FROM days WHERE site = 'example.com' "
                                   "AND day = '2026-10-05'").fetchone()[0]
            self.assertEqual((q["parsed"], q["duplicates_removed"], q["duplicates"]), (5, 1, 1))
            self.assertEqual(lines, 6)
            code, out, err = box.run("--today", "2026-10-06", "audit")
            self.assertEqual(code, 0, out + err)
            code, out, err = box.run("--today", "2026-10-06", "live")
            data = json.loads((box.root / "www" / "example.com" / "data" / "quality.json")
                              .read_text())
            day = next(d for d in data["days"] if d["day"] == "2026-10-05")
            self.assertEqual((day["duplicates_removed"], day["duplicates"]), (1, 1))
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
