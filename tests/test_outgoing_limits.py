"""Outgoing webhooks, second security review (docs/INTEGRATIONS.md):

  * a receiver that answers one byte every two seconds (a tarpit) is cut
    off at the delivery's deadline, not after every byte
  * one run spends at most its budget on deliveries; the rest wait
  * the live and daily runs only queue per site; deliveries are one pass
    after every site (jobs.deliver)
  * removing another site's webhook changes nothing of that site
  * the address filter refuses IPv4 hidden in IPv6 (mapped, compatible,
    6to4, NAT64, Teredo), and any bad address among several
  * secrets.json is changed under a lock

Hosts are example.com and RFC 5737 addresses; the secrets are made up."""
from __future__ import annotations

import fcntl
import socket
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_outgoing import Catcher, conv  # noqa: E402

from skald.conversions import jobs, outgoing, secrets_store, store  # noqa: E402

NOW = datetime(2026, 10, 11, 14, 0, tzinfo=timezone.utc)
OPEN = {"integrations": {"allow_private_urls": True}}


def tarpit() -> tuple[socket.socket, int]:
    """A server that sends a status line, then one byte every 2 seconds."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)

    def serve():
        while True:
            try:
                c, _ = srv.accept()
            except OSError:
                return
            c.recv(65536)
            try:
                c.sendall(b"HTTP/1.1 200 OK\r\n")
                for _ in range(60):
                    c.sendall(b"X")
                    time.sleep(2)
            except OSError:
                pass
            finally:
                c.close()

    threading.Thread(target=serve, daemon=True).start()
    return srv, srv.getsockname()[1]


class Deadline(unittest.TestCase):
    def test_a_tarpit_is_cut_off_at_the_deadline(self):
        srv, port = tarpit()
        self.addCleanup(srv.close)
        got = {}

        def go():
            got["r"] = outgoing.post(f"http://127.0.0.1:{port}/h", b"{}", "s", OPEN,
                                     time.time())
        started = time.monotonic()
        with mock.patch.object(outgoing, "DEADLINE", 1.5):
            th = threading.Thread(target=go, daemon=True)
            th.start()
            th.join(8)
        self.assertFalse(th.is_alive(), "post() still blocked by a tarpit after 8 s")
        self.assertLess(time.monotonic() - started, 5)
        status, error = got["r"]
        self.assertEqual(status, 0)
        self.assertIn("time", error.lower())

    def test_get_reads_a_page_within_the_deadline(self):
        catcher = Catcher()
        self.addCleanup(catcher.stop)
        status, body, error = outgoing.get(catcher.url, OPEN, max_bytes=1000, seconds=3)
        self.assertEqual((status, error), (501, "HTTP 501"))   # the catcher answers POST only


class Budget(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.db = store.connect(self.folder / "conversions.sqlite")
        self.addCleanup(self.db.close)
        outgoing.add(self.db, OPEN, self.folder, "example.com", "http://127.0.0.1:9/h",
                     ["conversion.completed"], "owner@example.com", NOW)
        for n in range(5):
            conv(self.db, external_ref=f"r{n}")
        outgoing.enqueue(self.db, OPEN, "example.com", NOW)

    def test_a_run_stops_at_its_budget_and_leaves_the_rest_due(self):
        def slow(*a, **k):
            time.sleep(0.3)
            return 200, None
        with mock.patch.object(outgoing, "post", side_effect=slow):
            got = outgoing.deliver_pass({"example.com": OPEN}, self.folder, NOW, budget=0.5)
        self.assertEqual(got["sent"], 2, got)
        due = self.db.execute("SELECT COUNT(*) FROM outbox WHERE state = 'pending' AND "
                              "next_at <= ?", (store.stamp(NOW),)).fetchone()[0]
        self.assertEqual(due, 3)            # not held: the next run sends them

    def test_each_delivery_gets_at_most_what_is_left(self):
        seen = []

        def note(url, body, secret, config, now, seconds=None):
            seen.append(seconds)
            return 200, None
        with mock.patch.object(outgoing, "post", side_effect=note):
            outgoing.deliver_pass({"example.com": OPEN}, self.folder, NOW, budget=4)
        self.assertTrue(seen and all(s is not None and s <= 4 for s in seen), seen)


class LiveOnlyQueues(unittest.TestCase):
    def test_live_queues_and_the_one_pass_after_every_site_sends(self):
        catcher = Catcher()
        self.addCleanup(catcher.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        db = store.connect(folder / "conversions.sqlite")
        self.addCleanup(db.close)
        outgoing.add(db, OPEN, folder, "example.com", catcher.url, ["conversion.completed"],
                     "owner@example.com", NOW)
        conv(db, external_ref="x1")
        errs = []
        ctx = SimpleNamespace(config=OPEN, db_path=str(folder / "history.sqlite"),
                              site="example.com", now=NOW, err=errs.append,
                              out=lambda *_: None)
        with mock.patch("skald.conversions.from_leads.run", return_value=None):
            jobs.live(ctx)
        self.assertEqual(catcher.got, [], "the per-site live step must not deliver")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM outbox").fetchone()[0], 1)
        jobs.deliver([ctx])
        self.assertEqual(len(catcher.got), 1, errs)


class RemoveIsPerSite(unittest.TestCase):
    def test_another_sites_rows_are_untouched(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = Path(tmp.name)
        db = store.connect(folder / "c.sqlite")
        self.addCleanup(db.close)
        hook, _ = outgoing.add(db, OPEN, folder, "victim.example.com", "https://example.com/h",
                               ["conversion.completed"])
        db.execute("INSERT INTO outbox (webhook_id, site, event, ref, body, created_at, "
                   "next_at) VALUES (?,?,?,?,?,?,?)",
                   (hook["id"], "victim.example.com", "conversion.completed", "c1", "{}",
                    "2026-10-11T00:00:00Z", "2026-10-11T00:00:00Z"))
        self.assertFalse(outgoing.remove(db, OPEN, folder, "attacker.example.com", hook["id"]))
        row = db.execute("SELECT state, error FROM outbox").fetchone()
        self.assertEqual((row[0], row[1]), ("pending", None))


class Addresses(unittest.TestCase):
    BAD = ("::ffff:192.0.2.1", "::ffff:8.8.8.8", "::8.8.8.8", "2002:808:808::1",
           "64:ff9b::808:808", "64:ff9b:1::808:808", "2001:0:4136:e378:8000:63bf:3fff:fdd2",
           "fe80::1", "fc00::1", "198.51.100.7", "0.0.0.0")

    def test_ipv4_inside_ipv6_is_refused(self):
        for raw in self.BAD:
            fam = socket.AF_INET6 if ":" in raw else socket.AF_INET
            answer = [(fam, 1, 6, "", (raw, 443))]
            with mock.patch("socket.getaddrinfo", return_value=answer):
                with self.assertRaises(outgoing.Refused, msg=raw):
                    outgoing.public_address("hooks.example.com", 443, {})

    def test_one_bad_address_among_good_ones_refuses(self):
        answer = [(2, 1, 6, "", ("8.8.8.8", 443)), (10, 1, 6, "", ("::ffff:10.0.0.1", 443))]
        with mock.patch("socket.getaddrinfo", return_value=answer):
            with self.assertRaises(outgoing.Refused):
                outgoing.public_address("hooks.example.com", 443, {})
        with mock.patch("socket.getaddrinfo", return_value=[(10, 1, 6, "",
                                                             ("2606:4700::1111", 443))]):
            self.assertEqual(outgoing.public_address("hooks.example.com", 443, {}),
                             "2606:4700::1111")


class SecretsLock(unittest.TestCase):
    def test_put_and_delete_wait_for_the_lock(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "secrets.json"
        secrets_store.put(path, "hooks/example.com/lead", "a")
        for step in (lambda: secrets_store.put(path, "hooks/example.com/json", "b"),
                     lambda: secrets_store.delete(path, ["hooks/example.com/lead"])):
            with open(secrets_store.lock_path(path), "a+") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                th = threading.Thread(target=step, daemon=True)
                th.start()
                th.join(0.4)
                self.assertTrue(th.is_alive(), "changed secrets.json without the lock")
                fcntl.flock(held, fcntl.LOCK_UN)
            th.join(5)
            self.assertFalse(th.is_alive())
        self.assertEqual(secrets_store.load(path), {"hooks/example.com/json": "b"})

    def test_many_writers_lose_nothing(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "secrets.json"
        threads = [threading.Thread(target=lambda n=n: [
            secrets_store.put(path, f"hooks/s{n}.example.com/k{i}", "v") for i in range(15)])
            for n in range(6)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(len(secrets_store.load(path)), 90)


if __name__ == "__main__":
    unittest.main()
