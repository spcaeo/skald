"""A sender that hangs up before Skald's answer (SKALD-36, part 2).

On live (19 Nov 2026, 02:10-02:30 UTC) a log drain closed its connections
while Skald was still answering. The batch was kept; the 200 "accepted"
answer could not be written (BrokenPipeError). ingest.handle took it for a
failure: "ingest: failed", a 500 answer on the same closed connection, which
raised again and left a double traceback, and the site's status noted a
refusal for a batch that was accepted. What is pinned:

  * a hang-up (broken pipe, reset, abort) is one line naming the site: no
    500 attempt, no exception out of handle, no refusal in the status, and
    the accepted batch stays noted;
  * another error still answers 500 and notes it; if the sender is gone by
    then, that is one more line, not an exception;
  * a refused connection elsewhere (not the sender) is still a failure.

Addresses and hosts are example.com.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import ingest, ingest_status  # noqa: E402

SITE = "drain.example.com"


class Gone(io.RawIOBase):
    """The socket's writer once the sender has closed the connection."""

    def __init__(self, error=BrokenPipeError):
        self.error, self.tried = error, 0

    def write(self, data):
        self.tried += 1
        raise self.error(32, "Broken pipe")


class Handler:
    """Enough of BaseHTTPRequestHandler for ingest._answer and ingest_status.note."""

    def __init__(self, wfile):
        self.headers, self.sent, self.wfile, self.close_connection = {}, [], wfile, False
        self.command, self.path = "POST", f"/traffic-ingest/{SITE}"

    def send_response(self, code):
        self.sent.append(code)

    def send_header(self, *_):
        pass

    def end_headers(self):
        pass


class HangUp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        ingest_status._LAST_REFUSAL.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def run_with(self, inner, wfile):
        """ingest.handle with _handle replaced by `inner(h)`; (handler, stderr)."""
        h, err = Handler(wfile), io.StringIO()

        def fake(h, *_):
            h._skald_ingest = {"base": self.base, "site": SITE, "known": lambda: True,
                               "shipper": "vercel"}
            return inner(h)
        with mock.patch.object(ingest, "_handle", fake), redirect_stderr(err):
            ingest.handle(h, {}, None)          # must not raise
        return h, err.getvalue()

    def status(self) -> dict:
        path = ingest_status.path_for(self.base, SITE)
        return json.loads(path.read_text()) if path.exists() else {}

    def test_a_hang_up_while_answering_a_kept_batch(self):
        accepted = {"ok": True, "accepted": 120, "rejected": 0, "skipped": 0, "duplicate": False}
        for error in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            with self.subTest(error=error.__name__):
                wfile = Gone(error)
                h, said = self.run_with(lambda h: ingest._answer(h, 200, accepted), wfile)
                self.assertEqual(h.sent, [200], "no 500 after the 200 that could not be sent")
                self.assertEqual(wfile.tried, 1)
                self.assertTrue(h.close_connection)
                self.assertEqual(said, f"ingest: {SITE}: the sender closed the connection "
                                       f"before the answer\n", "one line, no traceback")
                got = self.status()
                self.assertEqual(got["last_batch"]["lines"], 120, "the kept batch stays noted")
                self.assertNotIn("last_refusal", got, "an accepted batch is no refusal")

    def test_a_failure_whose_500_cannot_be_sent(self):
        def broken(h):
            raise ValueError("a bug")
        h, said = self.run_with(broken, Gone())
        self.assertEqual(h.sent, [500])
        self.assertEqual(said.splitlines(), [
            "ingest: failed (ValueError)",
            f"ingest: {SITE}: the sender closed the connection before the answer"])
        self.assertEqual(self.status()["last_refusal"]["code"], 500, "a real failure is noted")

    def test_a_failure_with_the_sender_still_there_answers_500(self):
        def broken(h):
            raise ValueError("a bug")
        h, said = self.run_with(broken, io.BytesIO())
        self.assertEqual(h.sent, [500])
        self.assertEqual(said, "ingest: failed (ValueError)\n")

    def test_a_refused_connection_elsewhere_is_still_a_failure(self):
        def refused(h):
            raise ConnectionRefusedError(111, "Connection refused")
        h, said = self.run_with(refused, io.BytesIO())
        self.assertEqual(h.sent, [500], "not the sender's hang-up: a 500, as before")
        self.assertEqual(said, "ingest: failed (ConnectionRefusedError)\n")


if __name__ == "__main__":
    unittest.main()
