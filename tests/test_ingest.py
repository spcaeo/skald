"""The log ingest endpoint (ingest.py) and its log writer (ingest_log.py)."""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile
import types
import unittest
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B  # noqa: E402
from ingest_support import TenantServer, lines  # noqa: E402

from skald import ingest, ingest_log  # noqa: E402
from skald.accounts import site_configs  # noqa: E402
from skald.parse import log_files, read  # noqa: E402
from skald.window import files_for  # noqa: E402

DAY = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc).timestamp()


class Clock:
    def __init__(self, t=DAY):
        self.t = t

    def __call__(self):
        return self.t


class WriterCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.folder = Path(self._tmp.name) / "site"
        self.clock = Clock()
        self.w = ingest_log.Writer(self.folder, keep=3, max_mb=1, clock=self.clock)

    def touch(self, path, t):
        os.utime(path, (t, t))

    def test_appends_and_records_the_batch(self):
        self.assertEqual(self.w.append("s1", 1, b"a\nb\n", 2, 1), "stored")
        self.assertEqual(self.w.log.read_bytes(), b"a\nb\n")
        state = ingest_log.read_state(self.folder)
        self.assertEqual(state["shippers"]["s1"]["seq"], 1)
        self.assertEqual(state["totals"]["accepted"], 2)
        self.assertEqual(state["totals"]["rejected"], 1)
        self.assertIsNone(state["pending"])

    def test_a_repeated_batch_is_not_written_twice(self):
        self.w.append("s1", 1, b"a\n", 1)
        self.assertEqual(self.w.append("s1", 1, b"a\n", 1), "duplicate")
        self.assertEqual(self.w.append("s1", 0, b"z\n", 1), "duplicate")
        self.assertEqual(self.w.append("s2", 1, b"b\n", 1), "stored")
        self.assertEqual(self.w.log.read_bytes(), b"a\nb\n")
        self.assertTrue(self.w.seen("s1", 1))
        self.assertFalse(self.w.seen("s1", 2))

    def test_a_missing_newline_is_added(self):
        self.w.append("s1", 1, b"a", 1)
        self.w.append("s1", 2, b"b\n", 1)
        self.assertEqual(self.w.log.read_bytes(), b"a\nb\n")

    def test_bad_shipper_ids_are_refused(self):
        for bad in ("", "a/b", "x" * 65, "a:b"):
            with self.assertRaises(ValueError):
                self.w.append(bad, 1, b"a\n")

    def test_rotates_on_a_new_day_into_the_layout_run_daily_reads(self):
        for day in range(5):
            self.clock.t = DAY + day * 86400
            self.w.append("s1", day + 1, f"day{day}\n".encode(), 1)
            self.touch(self.w.log, self.clock.t)
        names = sorted(p.name for p in self.folder.iterdir() if not p.name.startswith("."))
        self.assertEqual(names, ["access.log", "access.log.1", "access.log.2.gz",
                                 "access.log.3.gz"])           # keep=3: day0 dropped
        self.assertEqual(self.w.log.read_bytes(), b"day4\n")
        self.assertEqual((self.folder / "access.log.1").read_bytes(), b"day3\n")
        self.assertEqual(gzip.decompress((self.folder / "access.log.2.gz").read_bytes()),
                         b"day2\n")
        # Modification times are kept, so the window reader picks the right files.
        got = [int(p.stat().st_mtime) for p in log_files(self.folder, "access.log", 9)]
        self.assertEqual(got, [int(DAY + d * 86400) for d in (4, 3, 2, 1)])
        start = datetime.fromtimestamp(DAY + 3 * 86400, timezone.utc).replace(hour=0)
        chosen = files_for(log_files(self.folder, "access.log", 9), start,
                           start + timedelta(days=1))
        self.assertIn(self.folder / "access.log.1", chosen)

    def test_keep_everything_moves_the_oldest_day_to_the_archive(self):
        w = ingest_log.Writer(self.folder, keep=3, max_mb=1, clock=self.clock, archive=True)
        for day in range(6):
            self.clock.t = DAY + day * 86400
            w.append("s1", day + 1, f"day{day}\n".encode(), 1)
            self.touch(w.log, self.clock.t)
        names = sorted(p.name for p in self.folder.iterdir() if not p.name.startswith("."))
        self.assertEqual(names, ["access.log", "access.log.1", "access.log.2.gz",
                                 "access.log.3.gz", "archive"])  # run-daily's layout unchanged
        shelf = self.folder / ingest_log.ARCHIVE
        self.assertEqual(sorted(p.name for p in shelf.iterdir()),
                         ["access.log.2026-10-11.gz", "access.log.2026-10-12.gz"])
        self.assertEqual(gzip.decompress((shelf / "access.log.2026-10-11.gz").read_bytes()),
                         b"day0\n")                            # nothing dropped
        self.assertNotIn(shelf, log_files(self.folder, "access.log", 99))

    def test_never_more_than_one_rotation_a_day(self):
        self.w.append("s1", 1, b"a\n", 1)
        self.touch(self.w.log, DAY)
        self.clock.t = DAY + 3600
        self.w.append("s1", 2, b"b\n", 1)
        self.assertFalse((self.folder / "access.log.1").exists())

    def test_a_full_day_is_refused_with_the_wait(self):
        big = b"x" * (600 * 1024) + b"\n"
        self.w.append("s1", 1, big, 1)
        with self.assertRaises(ingest_log.Full) as got:
            self.w.append("s1", 2, big, 1)
        self.assertGreater(got.exception.retry_after, 0)
        self.assertFalse(self.w.seen("s1", 2))              # the shipper sends it again

    def test_a_complete_append_before_a_crash_is_kept_once(self):
        self.w.append("s1", 1, b"a\n", 1)
        state = ingest_log.read_state(self.folder)
        state["pending"] = {"shipper": "s1", "seq": 2, "start": 2, "length": 2,
                            "accepted": 1, "rejected": 0, "at": "x"}
        ingest_log._write_json(self.folder / ingest_log.STATE, state)
        with open(self.w.log, "ab") as f:
            f.write(b"b\n")
        self.assertEqual(self.w.append("s1", 2, b"b\n", 1), "duplicate")
        self.assertEqual(self.w.log.read_bytes(), b"a\nb\n")

    def test_a_partial_append_before_a_crash_is_cut_off(self):
        self.w.append("s1", 1, b"a\n", 1)
        state = ingest_log.read_state(self.folder)
        state["pending"] = {"shipper": "s1", "seq": 2, "start": 2, "length": 6,
                            "accepted": 3, "rejected": 0, "at": "x"}
        ingest_log._write_json(self.folder / ingest_log.STATE, state)
        with open(self.w.log, "ab") as f:
            f.write(b"b\nc")                                  # cut short
        self.assertEqual(self.w.append("s1", 2, b"b\nc\nd\n", 3), "stored")
        self.assertEqual(self.w.log.read_bytes(), b"a\nb\nc\nd\n")

    def test_summary(self):
        self.w.append("s1", 1, b"a\n", 1, 2)
        got = ingest_log.summary(self.folder)
        self.assertEqual((got["batches"], got["accepted"], got["rejected"], got["shippers"]),
                         (1, 1, 2, 1))


class Lines(unittest.TestCase):
    def test_lines_are_checked_in_the_sites_format(self):
        body = lines(3) + b"not a log line\n\n" + b'{"no":"format"}\n'
        data, ok, bad = ingest.split(body, "nginx_combined")
        self.assertEqual((ok, bad), (3, 2))
        self.assertNotIn(b"not a log line", data)
        self.assertTrue(data.endswith(b"\n"))
        _, ok, bad = ingest.split(body, "caddy_json")
        self.assertEqual((ok, bad), (0, 5))
        _, ok, bad = ingest.split(body, "auto")
        self.assertEqual((ok, bad), (3, 2))

    def test_w3c_headers_only_for_cloudfront_or_auto(self):
        head = b"#Version: 1.0\n"
        self.assertEqual(ingest.split(head, "auto")[1:], (1, 0))
        self.assertEqual(ingest.split(head, "nginx_combined")[1:], (0, 1))

    def test_long_lines_and_nul_bytes_are_rejected(self):
        line = lines(1).rstrip(b"\n")
        self.assertEqual(ingest.split(line + b"\x00\n", "auto")[1:], (0, 1))
        self.assertEqual(ingest.split(line + b"x" * 70000 + b"\n", "auto")[1:], (0, 1))

    def test_unpack(self):
        self.assertEqual(ingest.unpack(gzip.compress(b"abc"), "gzip"), b"abc")
        self.assertEqual(ingest.unpack(b"abc", ""), b"abc")
        with self.assertRaises(LookupError):
            ingest.unpack(b"abc", "br")
        with self.assertRaises(ValueError):
            ingest.unpack(b"not gzip", "gzip")
        with self.assertRaises(ValueError):
            ingest.unpack(gzip.compress(b"a" * 1000)[:20], "gzip")
        bomb = gzip.compress(b"\n" * (ingest.MAX_BODY + 10), 9)
        with self.assertRaises(OverflowError):
            ingest.unpack(bomb, "gzip")

    def test_bucket(self):
        t = [0.0]
        b = ingest.Bucket(60, 2, clock=lambda: t[0])
        self.assertEqual(b.take("x"), 0)
        self.assertEqual(b.take("x"), 0)
        self.assertGreater(b.take("x"), 0)
        self.assertEqual(b.take("y"), 0)
        t[0] += 1.0
        self.assertEqual(b.take("x"), 0)


class Endpoint(TenantServer):
    def test_a_batch_is_stored_and_counted(self):
        token = self.token(self.beta)
        got = self.ship(B, token, lines(5) + b"garbage\n")
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json, {"ok": True, "accepted": 5, "rejected": 1,
                                    "duplicate": False})
        kept = self.stored(B)
        self.assertEqual(kept.count(b"\n"), 5)
        self.assertNotIn(b"garbage", kept)
        hits = list(read([self.ingest_root / B / "access.log"], "nginx_combined"))
        self.assertEqual(len(hits), 5)

    def test_plain_bodies_work_too(self):
        got = self.ship(B, self.token(self.beta), lines(2), gz=False)
        self.assertEqual((got.status, got.json["accepted"]), (200, 2))

    def test_the_config_site_takes_lines_as_well(self):
        got = self.ship(A, self.token(self.alpha), lines(2))
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(self.stored(A).count(b"\n"), 2)

    def test_a_repeated_batch_is_acknowledged_and_skipped(self):
        token = self.token(self.beta)
        self.assertEqual(self.ship(B, token, lines(3), batch="abc:7").status, 200)
        again = self.ship(B, token, lines(3), batch="abc:7")
        self.assertEqual(again.status, 200)
        self.assertTrue(again.json["duplicate"])
        self.assertEqual(self.stored(B).count(b"\n"), 3)
        self.assertFalse(self.ship(B, token, lines(1), batch="abc:8").json["duplicate"])

    def test_tokens_that_may_not_ship(self):
        cases = [
            ("no token", None, 401),
            ("read scope only", self.token(self.beta, scopes=("read",)), 403),
            ("another organisation's", self.token(self.alpha), 403),
            ("for another site", None, 403),
            ("revoked", "revoke", 401),
        ]
        for label, token, code in cases:
            with self.subTest(label):
                if label == "for another site":
                    db = self.db()
                    try:
                        site_configs.create(db, self.beta["id"], "gamma.example", "cli")
                    finally:
                        db.close()
                    token = self.token(self.beta, sites=["gamma.example"])
                if token == "revoke":
                    token = self.token(self.beta)
                    db = self.db()
                    try:
                        from skald.accounts import apitokens
                        apitokens.revoke(db, self.beta["id"], token, "cli")
                    finally:
                        db.close()
                hdrs = {} if token else {"Authorization": ""}
                got = self.ship(B, token or "", lines(1), headers=hdrs)
                self.assertEqual(got.status, code, got.json)
        self.assertEqual(self.stored(B), b"")

    def test_an_unknown_site_looks_like_another_organisations(self):
        token = self.token(self.beta)
        self.assertEqual(self.ship("nowhere.example", token, lines(1)).status, 403)
        self.assertEqual(self.ship(A, token, lines(1)).status, 403)

    def test_a_removed_site_is_gone(self):
        token = self.token(self.beta)
        db = self.db()
        try:
            site_configs.remove(db, self.beta["id"], B, "cli")
        finally:
            db.close()
        self.assertEqual(self.ship(B, token, lines(1)).status, 410)

    def test_bad_requests(self):
        token = self.token(self.beta)
        self.assertEqual(self.ship(B, token, lines(1), batch=None).status, 400)
        self.assertEqual(self.ship(B, token, lines(1), batch="a b:1").status, 400)
        self.assertEqual(self.ship(B, token, b"\x1f\x8b broken", gz=False,
                                   headers={"Content-Encoding": "gzip"}).status, 400)
        self.assertEqual(self.ship(B, token, lines(1), gz=False,
                                   headers={"Content-Encoding": "br"}).status, 415)
        big = self.call("POST", f"/traffic-ingest/{B}",
                        headers={"Authorization": f"Bearer {token}", "X-Skald-Batch": "s:1",
                                 "Content-Length": str(ingest.MAX_BODY + 1)}, raw=b"")
        self.assertEqual(big.status, 413)
        self.assertEqual(self.call("GET", f"/traffic-ingest/{B}").status, 405)
        self.assertEqual(self.stored(B), b"")

    def test_rate_limit_per_site(self):
        self.config["ingest"].update(per_minute=1, burst=2)
        ingest._BUCKETS.clear()
        token = self.token(self.beta)
        codes = [self.ship(B, token, lines(1), batch=f"s:{i}").status for i in range(1, 4)]
        self.assertEqual(codes, [200, 200, 429])
        got = self.ship(B, token, lines(1), batch="s:9")
        self.assertTrue(int(got.header("Retry-After")) >= 1)
        # Another site's bucket is its own.
        self.assertEqual(self.ship(A, self.token(self.alpha), lines(1)).status, 200)

    def test_the_plan_quota_when_saas_limits_exists(self):
        seen = []

        def over_limit(org_id, site, lines):
            seen.append((org_id, site, lines))
            return (True, "This month's requests are used up.") if lines > 2 else None
        fake = types.ModuleType("skald.saas.limits")
        fake.over_limit = over_limit
        pkg = types.ModuleType("skald.saas")
        pkg.limits = fake
        with mock.patch.dict(sys.modules, {"skald.saas": pkg,
                                           "skald.saas.limits": fake}):
            token = self.token(self.beta)
            self.assertEqual(self.ship(B, token, lines(2), batch="s:1").status, 200)
            got = self.ship(B, token, lines(3), batch="s:2")
        self.assertEqual(got.status, 429)
        self.assertEqual(got.json["error"], "This month's requests are used up.")
        self.assertEqual(seen, [(self.beta["id"], B, 2), (self.beta["id"], B, 3)])
        self.assertEqual(self.stored(B).count(b"\n"), 2)

    def test_the_quota_as_saas_limits_reports_it(self):
        seen = []

        def over_limit(db, org_id, config, history_path=None, month=None):
            seen.append(history_path)
            return ["requests_month"] if len(seen) > 1 else []
        fake = types.ModuleType("skald.saas.limits")
        fake.over_limit = over_limit
        pkg = types.ModuleType("skald.saas")
        pkg.limits = fake
        with mock.patch.dict(sys.modules, {"skald.saas": pkg,
                                           "skald.saas.limits": fake}):
            token = self.token(self.beta)
            self.assertEqual(self.ship(B, token, lines(1), batch="s:1").status, 200)
            got = self.ship(B, token, lines(1), batch="s:2")
        self.assertEqual(got.status, 429)
        self.assertIn("plan", got.json["error"])
        self.assertEqual(seen[0], self.live / "history.sqlite")

    def test_off_by_default(self):
        self.config["ingest"]["enabled"] = False
        self.assertEqual(self.ship(B, self.token(self.beta), lines(1)).status, 404)

    def test_answers_never_echo_a_rejected_line(self):
        secret = b"192.0.2.99 my-private-thing\n"
        got = self.ship(B, self.token(self.beta), secret)
        self.assertNotIn(b"private", got.raw)
        self.assertEqual(got.json["rejected"], 1)


class EndToEnd(TenantServer):
    """The real shipper (tools/skald-ship.py) against the real helper."""

    def test_the_shipper_and_the_endpoint_agree(self):
        import contextlib
        import importlib.util
        import io
        spec = importlib.util.spec_from_file_location(
            "skald_ship_e2e", Path(__file__).resolve().parent.parent / "tools" / "skald-ship.py")
        ship = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ship)
        token_file = self.root / "token"
        token_file.write_text(self.token(self.beta) + "\n")
        os.chmod(token_file, 0o600)
        log = self.root / "access.log"
        log.write_bytes(lines(5) + b"not a log line\n" + lines(3, start=40))
        state = self.root / "state.json"
        url = f"http://127.0.0.1:{self.server.server_address[1]}/traffic-ingest/{B}"
        argv = ["--url", url, "--token-file", str(token_file), "--log", str(log),
                "--state", str(state), "--batch-lines", "4", "--once"]
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(ship.main(argv), 0, err.getvalue())
        self.assertEqual(self.stored(B).count(b"\n"), 8)
        self.assertNotIn(b"not a log line", self.stored(B))
        self.assertIn("1 rejected", err.getvalue())
        self.assertNotIn(token_file.read_text().strip(), err.getvalue())
        # Run again: nothing new, nothing sent twice; then new lines only.
        with contextlib.redirect_stderr(io.StringIO()):
            ship.main(argv)
        self.assertEqual(self.stored(B).count(b"\n"), 8)
        with open(log, "ab") as f:
            f.write(lines(2, start=90))
        with contextlib.redirect_stderr(io.StringIO()):
            ship.main(argv)
        self.assertEqual(self.stored(B).count(b"\n"), 10)
        hits = list(read([self.ingest_root / B / "access.log"], "nginx_combined"))
        self.assertEqual(len(hits), 10)


class Compressed(unittest.TestCase):
    def test_zlib_bomb_guard_does_not_inflate_everything(self):
        raw = zlib.compress(b"a" * 10)
        with self.assertRaises(ValueError):
            ingest.unpack(raw, "gzip")


if __name__ == "__main__":
    unittest.main()
