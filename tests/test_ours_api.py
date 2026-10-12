"""Internal addresses managed from the page (ours_store.py, refresh_server.py).

What is pinned: input is validated (addresses, ranges, labels, limits);
a range matches its addresses; an address added on the page counts as ours
only from when it was added, so a stored day is never rewritten; the
helper answers only same-origin requests, and "add mine" believes the
X-Real-IP header only from 127.0.0.1; every change is logged; and the
addresses stay out of the data files.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import ours_store  # noqa: E402
from skald.classify import Classifier, Group  # noqa: E402
from skald.parse import Hit  # noqa: E402
from skald.refresh_server import (caller_address, make_handler, ours_action,  # noqa: E402
                                         parse_body)

from support import CHROME, UTC  # noqa: E402

NOW = datetime(2026, 10, 7, 15, tzinfo=UTC)


class Store(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.config = {"ours": {"addresses": [{"ip": "192.0.2.10", "label": "Office"}],
                                "file": str(root / "ours.json"),
                                "change_log": str(root / "ours-changes.log")}}
        self.log = root / "ours-changes.log"

    def tearDown(self):
        self._tmp.cleanup()

    def test_validation(self):
        for bad in ("", "not-an-ip", "300.1.1.1", "10.0.0.0/8", "2001:db8::/16", "1" * 70):
            with self.subTest(bad=bad):
                with self.assertRaises(ours_store.Invalid):
                    ours_store.add(self.config, bad, "x", now=NOW)
        for label in ("", "x" * 61, "a\x07b"):
            with self.assertRaises(ours_store.Invalid):
                ours_store.add(self.config, "203.0.113.5", label, now=NOW)
        self.assertEqual(ours_store.normal("2001:DB8::1"), "2001:db8::1")
        self.assertEqual(ours_store.normal("203.0.113.0/24"), "203.0.113.0/24")
        self.assertEqual(ours_store.normal("203.0.113.9/32"), "203.0.113.9")

    def test_add_remove_list_and_log(self):
        ours_store.add(self.config, "203.0.113.5", "Home laptop", now=NOW)
        with self.assertRaises(ours_store.Invalid):
            ours_store.add(self.config, "203.0.113.5", "again", now=NOW)
        with self.assertRaises(ours_store.Invalid):
            ours_store.add(self.config, "192.0.2.10", "config one", now=NOW)
        entries = ours_store.listing(self.config)
        self.assertEqual([(e["ip"], e["source"], e["editable"]) for e in entries],
                         [("192.0.2.10", "config", False), ("203.0.113.5", "file", True)])
        with self.assertRaises(ours_store.Invalid):
            ours_store.remove(self.config, "192.0.2.10")
        ours_store.remove(self.config, "203.0.113.5", now=NOW)
        lines = self.log.read_text().splitlines()
        self.assertEqual([l.split("\t")[1] for l in lines], ["add", "remove"])
        self.assertIn("Home laptop", lines[0])

    def test_the_limit(self):
        for i in range(ours_store.LIMIT - 1):
            ours_store.add(self.config, f"198.51.100.{i}", f"n{i}", now=NOW)
        with self.assertRaises(ours_store.Full):
            ours_store.add(self.config, "203.0.113.200", "one too many", now=NOW)

    def test_a_range_matches_and_only_from_when_it_was_added(self):
        ours_store.add(self.config, "203.0.113.0/24", "Office range", now=NOW)
        c = Classifier.from_config(self.config)
        before = Hit(NOW - timedelta(hours=1), "203.0.113.77", "example.com", "GET", "/",
                     "200", "", CHROME)
        after = Hit(NOW + timedelta(minutes=1), "203.0.113.77", "example.com", "GET", "/",
                    "200", "", CHROME)
        self.assertEqual(c(before).group, Group.PEOPLE)
        self.assertEqual((c(after).group, c(after).engine), (Group.OURS, "Office range"))
        config_hit = Hit(NOW - timedelta(days=9), "192.0.2.10", "example.com", "GET", "/",
                         "200", "", CHROME)
        self.assertEqual(c(config_hit).engine, "Office")


class FakeRunner:
    def __init__(self):
        self.calls = []

    def refresh(self, force=False):
        self.calls.append(force)
        return "ran"


class Helper(Store):

    def request(self, method, path, headers=None, body=b"", peer="127.0.0.1"):
        runner = FakeRunner()
        handler = make_handler(runner, {"https://www.example.com"}, self.config)
        raw = (f"{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n"
               + "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items())
               + "\r\n").encode() + body

        out = io.BytesIO()

        class Socket:
            def makefile(self, mode, *a, **k):
                return io.BytesIO(raw)

            def sendall(self, data):
                out.write(data)

        handler(Socket(), (peer, 5555), None)
        head, _, data = out.getvalue().partition(b"\r\n\r\n")
        code = int(head.split()[1])
        return code, (json.loads(data) if data.startswith(b"{") else None), runner

    def test_paths_and_parsing(self):
        self.assertEqual(ours_action("/traffic/example.com/ours"), "list")
        self.assertEqual(ours_action("/traffic/example.com/us-english/ours/add-mine"), "add-mine")
        self.assertIsNone(ours_action("/traffic/example.com/ours/drop"))
        self.assertIsNone(ours_action("/traffic/../ours"))
        self.assertEqual(parse_body(b'{"ip": "192.0.2.34"}', "application/json"), {"ip": "192.0.2.34"})
        self.assertEqual(parse_body(b"ip=192.0.2.34&label=x", ""), {"ip": "192.0.2.34", "label": "x"})

    def test_same_origin_only(self):
        same = {"Sec-Fetch-Site": "same-origin"}
        code, body, _ = self.request("GET", "/traffic/example.com/ours", {"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(code, 403)
        code, body, _ = self.request("GET", "/traffic/example.com/ours", same)
        self.assertEqual((code, body["limit"]), (200, 50))
        code, body, runner = self.request(
            "POST", "/traffic/example.com/ours/add", {**same, "Content-Type": "application/json"},
            json.dumps({"ip": "203.0.113.5", "label": "Home"}).encode())
        self.assertEqual(code, 200, body)
        self.assertEqual(runner.calls, [True])
        code, body, _ = self.request("POST", "/traffic/example.com/ours/add",
                                     {**same, "Content-Type": "application/x-www-form-urlencoded"},
                                     b"ip=nope&label=x")
        self.assertEqual((code, body["ok"]), (400, False))

    def test_add_mine_trusts_the_header_from_localhost_only(self):
        self.assertEqual(caller_address({"X-Real-IP": "203.0.113.9"}, "127.0.0.1"), "203.0.113.9")
        self.assertIsNone(caller_address({"X-Real-IP": "203.0.113.9"}, "198.51.100.1"))
        same = {"Sec-Fetch-Site": "same-origin", "X-Real-IP": "203.0.113.9"}
        code, body, _ = self.request("POST", "/traffic/example.com/ours/add-mine", same,
                                     b"label=My+laptop", peer="198.51.100.1")
        self.assertEqual(code, 400)
        code, body, _ = self.request("POST", "/traffic/example.com/ours/add-mine", same,
                                     b"label=My+laptop")
        self.assertEqual(code, 200, body)
        self.assertIn("203.0.113.9", [e["ip"] for e in body["entries"]])


if __name__ == "__main__":
    unittest.main()
