"""tools/skald-ship.py: the customer-side log shipper.

A fake ingest endpoint on 127.0.0.1 records every batch (gzip body, the
X-Skald-Batch header) and can be told to fail, answer 413 or 429, or keep
a batch and drop the answer. The shipper's sleep is replaced by a recorder,
so nothing here waits for real. Log lines use RFC 5737 addresses and
example.com.
"""
from __future__ import annotations

import gzip
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("skald_ship", ROOT / "tools" / "skald-ship.py")
ship = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ship)

TOKEN = "skald_abcd1234_not-a-real-token-only-for-tests"


def line(n: int) -> str:
    return (f'192.0.2.{n % 250 + 1} - - [11/Oct/2026:14:00:{n % 60:02d} +0000] '
            f'"GET /page/{n} HTTP/1.1" 200 512 "https://www.example.com/" "Mozilla/5.0"\n')


class FakeIngest:
    """Records batches. `plan` is a list of actions, one per request:
    "ok", ("status", code[, retry_after]), "drop" (keep the batch, then close
    the connection without an answer). An empty plan means "ok"."""

    def __init__(self):
        self.plan: list = []
        self.max_lines = None          # answer 413 above this many lines
        self.last: dict[str, int] = {}
        self.stored: list[str] = []     # every kept line, in order
        self.requests: list[dict] = []
        self.lock = threading.Lock()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                outer.handle(self)

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, args=(0.02,), daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/traffic-ingest/www.example.com"

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def _answer(self, h, code, body, headers=None):
        raw = json.dumps(body).encode()
        h.send_response(code)
        for k, v in (headers or {}).items():
            h.send_header(k, v)
        h.send_header("Content-Type", "application/json")
        h.send_header("Content-Length", str(len(raw)))
        h.end_headers()
        h.wfile.write(raw)

    def handle(self, h):
        length = int(h.headers.get("Content-Length") or 0)
        raw = h.rfile.read(length)
        body = gzip.decompress(raw) if h.headers.get("Content-Encoding") == "gzip" else raw
        lines = body.decode().splitlines(keepends=True)
        batch = h.headers.get("X-Skald-Batch", "")
        with self.lock:
            self.requests.append({"batch": batch, "lines": lines,
                                  "auth": h.headers.get("Authorization"),
                                  "count": h.headers.get("X-Skald-Lines"),
                                  "ctype": h.headers.get("Content-Type")})
            action = self.plan.pop(0) if self.plan else "ok"
        if isinstance(action, tuple):
            code = action[0]
            headers = {"Retry-After": str(action[1])} if len(action) > 1 else {}
            return self._answer(h, code, {"ok": False, "error": f"refused {code}"}, headers)
        if self.max_lines is not None and len(lines) > self.max_lines:
            return self._answer(h, 413, {"ok": False, "error": "too large"})
        shipper, _, seq = batch.partition(":")
        seq = int(seq)
        with self.lock:
            if seq <= self.last.get(shipper, 0):
                dup = True
            else:
                dup = False
                self.last[shipper] = seq
                self.stored.extend(lines)
        if action == "drop":
            h.close_connection = True
            return
        rejected = sum(1 for x in lines if "BROKEN" in x) if not dup else 0
        self._answer(h, 200, {"ok": True, "accepted": 0 if dup else len(lines) - rejected,
                              "rejected": rejected, "duplicate": dup})


class ShipCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.log = self.dir / "access.log"
        self.state = self.dir / "state" / "state.json"
        self.ingest = FakeIngest()
        self.addCleanup(self.ingest.close)
        self.waits: list[float] = []
        self.err = io.StringIO()
        self.n = 0

    def write(self, count, path=None, partial=""):
        with open(path or self.log, "a") as f:
            for _ in range(count):
                self.n += 1
                f.write(line(self.n))
            f.write(partial)

    def shipper(self, **kw) -> "ship.Shipper":
        opts = dict(url=self.ingest.url, token=TOKEN, log=str(self.log), state=str(self.state),
                    batch_lines=kw.pop("batch_lines", 2000), interval=kw.pop("interval", 10),
                    sleep=self.waits.append, err=self.err)
        opts.update(kw)
        got = ship.Shipper(**opts)
        self.addCleanup(got.close)
        return got

    def stored(self):
        return [int(x.split("/page/")[1].split()[0]) for x in self.ingest.stored]

    def saved(self):
        return json.loads(self.state.read_text())


class Basics(ShipCase):
    def test_sends_gzip_lines_with_headers_and_saves_state_after_2xx(self):
        self.write(5)
        s = self.shipper()
        self.assertEqual(s.run(once=True), 0)
        req = self.ingest.requests[0]
        self.assertEqual(req["auth"], f"Bearer {TOKEN}")
        self.assertEqual(req["count"], "5")
        self.assertTrue(req["ctype"].startswith("text/plain"))
        shipper, _, seq = req["batch"].partition(":")
        self.assertEqual(seq, "1")
        self.assertRegex(shipper, r"^[0-9a-f]{16}$")
        self.assertEqual(self.stored(), [1, 2, 3, 4, 5])
        st = self.saved()
        self.assertEqual((st["shipper"], st["seq"]), (shipper, 1))
        self.assertEqual(st["offset"], self.log.stat().st_size)
        self.assertEqual(st["ino"], self.log.stat().st_ino)
        self.assertIn("sent batch 1: 5 lines, 5 accepted, 0 rejected", self.err.getvalue())

    def test_batches_respect_batch_lines(self):
        self.write(7)
        self.shipper(batch_lines=3).run(once=True)
        self.assertEqual([len(r["lines"]) for r in self.ingest.requests], [3, 3, 1])
        self.assertEqual([r["batch"].split(":")[1] for r in self.ingest.requests], ["1", "2", "3"])
        self.assertEqual(self.stored(), list(range(1, 8)))

    def test_state_not_saved_without_2xx(self):
        self.write(2)
        self.ingest.plan = [(500,)]
        s = self.shipper()
        s.stopping = True          # one try only, then stop
        s.run(once=True)
        self.assertFalse(self.state.exists() and self.saved().get("seq"))
        self.assertEqual(self.ingest.stored, [])

    def test_rejected_lines_are_counted_on_stderr(self):
        with open(self.log, "w") as f:
            f.write(line(1) + "BROKEN line\n")
        self.shipper().run(once=True)
        self.assertIn("1 accepted, 1 rejected", self.err.getvalue())

    def test_partial_last_line_waits(self):
        self.write(2, partial='198.51.100.7 - - [11/Oct/2026:14:01:00 +0000] "GET /par')
        s = self.shipper()
        s.run(once=True)
        self.assertEqual(len(self.ingest.stored), 2)
        size_before = self.saved()["offset"]
        with open(self.log, "a") as f:
            f.write('tial HTTP/1.1" 200 1 "-" "curl"\n')
        s.run(once=True)
        self.assertEqual(len(self.ingest.stored), 3)
        self.assertTrue(self.ingest.stored[-1].startswith("198.51.100.7"))
        self.assertIn("/partial ", self.ingest.stored[-1])
        self.assertGreater(self.saved()["offset"], size_before)

    def test_long_line_is_cut(self):
        with open(self.log, "w") as f:
            f.write("203.0.113.9 " + "x" * (ship.MAX_LINE + 500) + "\n")
            f.write(line(1))
        self.shipper().run(once=True)
        self.assertEqual(len(self.ingest.stored), 2)
        self.assertEqual(len(self.ingest.stored[0]), ship.MAX_LINE + 1)
        self.assertIn("cut", self.err.getvalue())
        self.assertEqual(self.saved()["offset"], self.log.stat().st_size)

    def test_token_never_in_stderr(self):
        self.write(1)
        self.ingest.plan = [(401,), (403,), "ok"]
        self.shipper().run(once=True)
        out = self.err.getvalue()
        self.assertIn("HTTP 401", out)
        self.assertNotIn(TOKEN, out)
        self.assertNotIn(TOKEN.split("_")[2], out)


class Retries(ShipCase):
    def test_backoff_grows_with_full_jitter_and_never_drops(self):
        self.write(3)
        self.ingest.plan = [(503,), (500,), (502,), (500,), "ok"]
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), [1, 2, 3])
        self.assertEqual(len(self.waits), 4)
        for i, w in enumerate(self.waits):
            self.assertGreaterEqual(w, 0)
            self.assertLessEqual(w, min(ship.BACKOFF_CAP, ship.BACKOFF_BASE * 2 ** i))
        self.assertIn("retry in", self.err.getvalue())
        # Every try carried the same batch.
        self.assertEqual({r["batch"] for r in self.ingest.requests}, {self.ingest.requests[0]["batch"]})

    def test_backoff_is_capped(self):
        s = self.shipper()
        for n in range(30):
            self.assertLessEqual(s.backoff(n), ship.BACKOFF_CAP)

    def test_retry_after_is_honoured_and_capped(self):
        self.write(1)
        self.ingest.plan = [(429, 7), (503, 99999), "ok"]
        self.shipper(patience=(10, 10 ** 6)).run(once=True)      # the service's patience
        self.assertEqual(self.waits[:2], [7, ship.RETRY_AFTER_CAP])
        self.assertEqual(self.stored(), [1])

    def test_once_gives_up_on_a_full_disk_and_keeps_the_lines(self):
        # The server's 507 says Retry-After: 600, more than --once waits in all.
        self.write(3)
        self.ingest.plan = [(507, 600)] * 50
        self.assertEqual(self.shipper().run(once=True), 1)
        self.assertEqual((len(self.ingest.requests), self.waits), (1, []))
        self.assertIn("giving up for now after 1 try (HTTP 507", self.err.getvalue())
        self.assertIn("Nothing is lost", self.err.getvalue())
        self.assertEqual(self.saved().get("seq"), 0)
        # The next run sends the same lines, none lost and none twice.
        self.ingest.plan = []
        self.assertEqual(self.shipper().run(once=True), 0)
        self.assertEqual(self.stored(), [1, 2, 3])

    def test_once_gives_up_after_five_tries(self):
        self.write(2)
        self.ingest.plan = [(500,)] * 50
        self.assertEqual(self.shipper().run(once=True), 1)
        self.assertEqual(len(self.ingest.requests), ship.ONCE_TRIES)
        self.assertEqual(len(self.waits), ship.ONCE_TRIES - 1)
        self.assertIn("after 5 tries", self.err.getvalue())

    def test_once_gives_up_when_the_time_runs_out(self):
        self.write(1)
        self.ingest.plan = [(503, 40)] * 50
        self.assertEqual(self.shipper().run(once=True), 1)
        # 40 s fits in 60 s once; a second 40 s would pass it.
        self.assertEqual(self.waits, [40])

    def test_the_service_retries_for_ever(self):
        self.write(1)
        self.ingest.plan = [(500,)] * 8 + ["ok"]
        s = self.shipper()
        s.start()
        s.poll(s._want())
        self.assertEqual(s.send_next(force=True), "sent")
        self.assertEqual(len(self.waits), 8)

    def test_network_error_retries(self):
        self.write(2)
        s = self.shipper(url="http://127.0.0.1:9/traffic-ingest/www.example.com")
        s.stopping = True
        s.run(once=True)
        self.assertIn("network error", self.err.getvalue())
        self.assertEqual(self.saved().get("seq"), 0)

    def test_413_splits_the_batch(self):
        self.write(8)
        self.ingest.max_lines = 3
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), list(range(1, 9)))
        kept = [len(r["lines"]) for r in self.ingest.requests if len(r["lines"]) <= 3]
        self.assertEqual(sum(kept), 8)
        seqs = [int(r["batch"].split(":")[1]) for r in self.ingest.requests
                if len(r["lines"]) <= 3]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(self.saved()["seq"], max(seqs))

    def test_lost_answer_resend_is_idempotent(self):
        self.write(4)
        self.ingest.plan = ["drop", "ok"]
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), [1, 2, 3, 4])
        self.assertEqual(len(self.ingest.requests), 2)
        self.assertEqual(self.ingest.requests[0]["batch"], self.ingest.requests[1]["batch"])
        self.assertIn("already received", self.err.getvalue())
        self.write(1)
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), [1, 2, 3, 4, 5])
        self.assertTrue(self.ingest.requests[-1]["batch"].endswith(":2"))

    def test_crash_after_commit_rebuilds_the_same_batch(self):
        # The server kept batch 1, the answer was lost, the shipper died.
        self.write(3)
        self.ingest.plan = ["drop"]
        s = self.shipper()
        s.stopping = True
        s.run(once=True)
        self.assertEqual(self.saved().get("seq", 0), 0)
        self.assertIsNotNone(self.saved().get("inflight"))
        self.write(2)             # more lines arrive while it is down
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), [1, 2, 3, 4, 5])
        self.assertEqual(self.saved()["seq"], 2)


class Rotation(ShipCase):
    def test_rename_rotation_while_running(self):
        self.write(3)
        s = self.shipper()
        s.run(once=True)
        self.write(2, partial="203.0.113.5 - - [11/Oct/2026:14:02:00 +0000] \"GET /tail")
        os.rename(self.log, str(self.log) + ".1")
        self.write(2)
        s.run(once=True)
        got = self.ingest.stored
        self.assertEqual(len(got), 3 + 2 + 1 + 2)
        self.assertEqual(got[5], "203.0.113.5 - - [11/Oct/2026:14:02:00 +0000] \"GET /tail\n")
        del self.ingest.stored[5]
        self.assertEqual(self.stored(), [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(self.saved()["ino"], self.log.stat().st_ino)
        self.assertIn("rotated", self.err.getvalue())

    def test_rotation_while_down_resumes_from_dot_one(self):
        self.write(3)
        self.shipper().run(once=True)
        self.write(2)                        # not sent: the shipper is down
        os.rename(self.log, str(self.log) + ".1")
        self.write(3)
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), list(range(1, 9)))

    def test_rotation_while_down_with_compressed_file_says_so(self):
        self.write(3)
        self.shipper().run(once=True)
        self.write(2)
        rotated = Path(str(self.log) + ".1")
        os.rename(self.log, rotated)
        rotated.unlink()                      # compressed away: gone by inode
        self.write(2)
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), [1, 2, 3, 6, 7])
        self.assertIn("could not resume", self.err.getvalue())

    def test_truncation_restarts_at_zero(self):
        self.write(5)
        s = self.shipper()
        s.run(once=True)
        with open(self.log, "w"):
            pass
        self.write(2)
        s.run(once=True)
        self.assertEqual(self.stored(), [1, 2, 3, 4, 5, 6, 7])
        self.assertIn("truncated", self.err.getvalue())

    def test_truncation_while_down(self):
        self.write(5)
        self.shipper().run(once=True)
        with open(self.log, "w"):
            pass
        self.write(1)
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), [1, 2, 3, 4, 5, 6])


class Restart(ShipCase):
    def test_resume_from_state_sends_nothing_twice(self):
        self.write(4)
        self.shipper().run(once=True)
        first = self.saved()
        self.write(3)
        self.shipper().run(once=True)
        self.assertEqual(self.stored(), list(range(1, 8)))
        self.assertEqual(self.saved()["shipper"], first["shipper"])
        self.assertEqual(self.saved()["seq"], 2)

    def test_lost_state_file_gets_a_new_shipper_id(self):
        self.write(1)
        self.shipper().run(once=True)
        old = self.saved()["shipper"]
        self.state.unlink()
        self.shipper().run(once=True)
        self.assertNotEqual(self.saved()["shipper"], old)

    def test_from_end_skips_old_lines(self):
        self.write(4)
        s = self.shipper(from_end=True)
        s.run(once=True)
        self.assertEqual(self.ingest.stored, [])
        self.write(1)
        s.run(once=True)
        self.assertEqual(self.stored(), [5])

    def test_state_written_atomically(self):
        self.write(1)
        self.shipper().run(once=True)
        leftovers = [p for p in self.state.parent.iterdir() if p.name != "state.json"]
        self.assertEqual(leftovers, [])
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)


class Stopping(ShipCase):
    def test_sigterm_stops_after_one_last_try(self):
        self.write(2)
        self.ingest.plan = [(503,), (503,), "ok"]
        s = self.shipper()
        s.sleep = lambda secs: s.on_signal(15, None)   # SIGTERM arrives while waiting
        self.assertEqual(s.run(), 0)
        self.assertEqual(len(self.ingest.requests), 2)    # the try, then one last try
        self.assertEqual(self.ingest.stored, [])
        self.assertFalse(self.saved().get("seq"))
        self.assertIn("stopping", self.err.getvalue())

    def test_sigterm_with_last_try_succeeding_saves(self):
        self.write(2)
        self.ingest.plan = [(503,), "ok"]
        s = self.shipper()
        s.sleep = lambda secs: s.on_signal(15, None)
        self.assertEqual(s.run(), 0)
        self.assertEqual(self.stored(), [1, 2])
        self.assertEqual(self.saved()["seq"], 1)

    def test_interval_sends_a_part_batch_in_the_loop(self):
        self.write(2)
        clock = [0.0]
        s = self.shipper(interval=5, clock=lambda: clock[0])

        def tick(secs):
            clock[0] += max(secs, 1)
            if clock[0] > 20:
                s.stopping = True
        s.sleep = tick
        s.run()
        self.assertEqual(self.stored(), [1, 2])


class Cli(unittest.TestCase):
    def test_plain_http_only_for_loopback(self):
        self.assertIsNone(ship.url_problem("https://www.example.com/traffic-ingest/x"))
        self.assertIsNone(ship.url_problem("http://127.0.0.1:8080/traffic-ingest/x"))
        self.assertIsNone(ship.url_problem("http://localhost/traffic-ingest/x"))
        self.assertIsNotNone(ship.url_problem("http://www.example.com/traffic-ingest/x"))
        self.assertIsNotNone(ship.url_problem("ftp://www.example.com/x"))

    def test_token_file_warns_only_when_open_to_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "token"
            path.write_text(TOKEN + "\n")
            os.chmod(path, 0o644)
            err = io.StringIO()
            self.assertEqual(ship.read_token(str(path), err), TOKEN)
            self.assertIn("open to others", err.getvalue())
            self.assertNotIn(TOKEN, err.getvalue())
            for quiet in (0o600, 0o640, 0o400, 0o440):
                os.chmod(path, quiet)
                err = io.StringIO()
                ship.read_token(str(path), err)
                self.assertEqual(err.getvalue(), "", oct(quiet))
            os.chmod(path, 0o660)
            err = io.StringIO()
            ship.read_token(str(path), err)
            self.assertIn("open to others", err.getvalue())

    def test_main_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            ingest = FakeIngest()
            try:
                log = Path(tmp) / "access.log"
                log.write_text(line(1) + line(2))
                tok = Path(tmp) / "token"
                tok.write_text(TOKEN)
                os.chmod(tok, 0o600)
                old = sys.stderr
                sys.stderr = io.StringIO()
                try:
                    code = ship.main(["--url", ingest.url, "--token-file", str(tok), "--log",
                                      str(log), "--state", str(Path(tmp) / "s.json"), "--once"])
                finally:
                    sys.stderr = old
                self.assertEqual(code, 0)
                self.assertEqual(len(ingest.stored), 2)
            finally:
                ingest.close()

    def test_main_once_against_a_full_disk_returns_at_once(self):
        import time
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            ingest = FakeIngest()
            try:
                ingest.plan = [(507, 600)] * 50 + [(500,)] * 50
                log = Path(tmp) / "access.log"
                log.write_text(line(1) + line(2))
                tok = Path(tmp) / "token"
                tok.write_text(TOKEN)
                os.chmod(tok, 0o600)
                argv = ["--url", ingest.url, "--token-file", str(tok), "--log", str(log),
                        "--state", str(Path(tmp) / "s.json"), "--once"]
                err = io.StringIO()
                started = time.monotonic()
                with mock.patch.object(ship.Shipper, "_sleep", lambda self, s: None), \
                        mock.patch.object(sys, "stderr", err):
                    code = ship.main(argv)
                self.assertEqual(code, 1)
                self.assertLess(time.monotonic() - started, 5)
                self.assertIn("giving up for now", err.getvalue())
                self.assertEqual(ingest.stored, [])
            finally:
                ingest.close()


if __name__ == "__main__":
    unittest.main()
