"""Internal traffic: Active / Paused, edit and delete (2026-10-18).

What is pinned: an entry keeps its pauses ([from, to-or-null]) so a stored
day re-collected later gives the same answer; the main road (classify.py)
and the audit's own reading (audit_visits.page_added, ours_applies) agree at
every moment; a day with a pause in the middle collects and audits "all
match", live too; an edit ends the old entry and starts a new one, and a
delete keeps the entry in the file with `removed_at`, so a day before either
recounts the same; the live server's entry shape reads as paused; an old
ours.json without `paused` still works; the helper and the CLI take the new
actions, with the same permissions as add; and no address is printed.
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_visits, ours_store  # noqa: E402
from skald.classify import Classifier, Group  # noqa: E402
from skald.parse import Hit  # noqa: E402
from skald.refresh_server import make_handler, ours_action  # noqa: E402

from support import CHROME, UTC, Sandbox, day_lines, line  # noqa: E402

NOW = datetime(2026, 10, 7, 15, tzinfo=UTC)
OFFICE, LAPTOP, NEW = "192.0.2.88", "192.0.2.89", "198.51.100.40"


def hit(when, address=OFFICE):
    return Hit(when, address, "example.com", "GET", "/", "200", "", CHROME)


def audit_label(config, address, when):
    """The audit's road: the first page-added entry holding the address that
    applies at `when` (audit_visits only, nothing from classify)."""
    import ipaddress
    ip = ipaddress.ip_address(address)
    for value, label, since, until, stops in audit_visits.page_added(config):
        if ip in ipaddress.ip_network(value, strict=False) and \
                audit_visits.ours_applies(since, until, stops, when):
            return label
    return ""


class Base(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.file = self.root / "ours.json"
        self.config = {"ours": {"addresses": [{"ip": "192.0.2.10", "label": "Config office"}],
                                "file": str(self.file),
                                "change_log": str(self.root / "ours-changes.log")}}

    def tearDown(self):
        self._tmp.cleanup()

    def actions(self):
        return [l.split("\t")[1] for l in
                (self.root / "ours-changes.log").read_text().splitlines()]

    def both_roads(self, address, when):
        main = Classifier.from_config(self.config)._ours_address(address, when)
        self.assertEqual(main, audit_label(self.config, address, when), (address, when))
        return main


class Store(Base):

    def test_pause_and_resume_keep_every_interval(self):
        ours_store.add(self.config, OFFICE, "Office Mac", now=NOW, by="owner")
        ours_store.pause(self.config, "office mac", now=NOW + timedelta(hours=1), by="owner")
        with self.assertRaises(ours_store.Invalid):
            ours_store.pause(self.config, OFFICE, now=NOW + timedelta(hours=1, minutes=5))
        row = ours_store.listing(self.config)[1]
        self.assertEqual((row["active"], row["paused_since"], row["pausable"]),
                         (False, "2026-10-07T16:00:00+00:00", True))
        ours_store.resume(self.config, OFFICE, now=NOW + timedelta(hours=2))
        with self.assertRaises(ours_store.Invalid):
            ours_store.resume(self.config, OFFICE)
        ours_store.pause(self.config, OFFICE, now=NOW + timedelta(hours=3))
        entry = ours_store.load(self.file)[0]
        self.assertEqual(entry["paused"], [["2026-10-07T16:00:00+00:00", "2026-10-07T17:00:00+00:00"],
                                           ["2026-10-07T18:00:00+00:00", None]])
        # A save keeps who added it.
        self.assertEqual(entry["added_by"], "owner")
        self.assertEqual(self.actions(), ["add", "pause", "resume", "pause"])
        expected = {-1: "", 0: "Office Mac", 59: "Office Mac", 60: "", 119: "", 120: "Office Mac",
                    179: "Office Mac", 180: "", 600: ""}
        for minutes, label in expected.items():
            with self.subTest(minutes=minutes):
                self.assertEqual(self.both_roads(OFFICE, NOW + timedelta(minutes=minutes)), label)
        # The verdict itself: paused means a visitor.
        c = Classifier.from_config(self.config)
        self.assertEqual(c(hit(NOW + timedelta(minutes=90))).group, Group.PEOPLE)
        self.assertEqual(c(hit(NOW + timedelta(minutes=150))).group, Group.OURS)

    def test_the_live_servers_entry_reads_as_paused_from_that_time(self):
        self.file.write_text(json.dumps({"entries": [
            {"ip": OFFICE, "label": "Office Mac (Morgan)", "added_at": "2026-10-12T00:00:00+00:00",
             "added_from": "page", "added_by": "owner",
             "paused": [["2026-10-18T17:23:36+00:00", None]]}]}))
        row = ours_store.listing(self.config)[1]
        self.assertEqual((row["active"], row["paused_since"]),
                         (False, "2026-10-18T17:23:36+00:00"))
        at = datetime(2026, 10, 18, 17, 23, 36, tzinfo=UTC)
        self.assertEqual(self.both_roads(OFFICE, at - timedelta(seconds=1)), "Office Mac (Morgan)")
        self.assertEqual(self.both_roads(OFFICE, at), "")
        self.assertEqual(self.both_roads(OFFICE, at + timedelta(days=3)), "")
        ours_store.resume(self.config, "Office Mac (Morgan)", now=at + timedelta(hours=1))
        self.assertEqual(self.both_roads(OFFICE, at + timedelta(hours=1)), "Office Mac (Morgan)")
        self.assertEqual(self.both_roads(OFFICE, at + timedelta(minutes=30)), "")
        kept = json.loads(self.file.read_text())["entries"][0]
        self.assertEqual(kept["added_by"], "owner")

    def test_an_old_file_without_pauses_still_works(self):
        self.file.write_text(json.dumps({"entries": [
            {"ip": OFFICE, "label": "Home", "added_at": "2026-10-01T08:00:00+00:00",
             "added_from": "page"}]}))
        row = ours_store.listing(self.config)[1]
        self.assertEqual((row["active"], row["paused_since"]), (True, None))
        self.assertEqual(self.both_roads(OFFICE, NOW), "Home")
        self.assertEqual(self.both_roads(OFFICE, datetime(2026, 9, 30, tzinfo=UTC)), "")
        # Unreadable pairs are skipped the same way by both roads.
        self.file.write_text(json.dumps({"entries": [
            {"ip": OFFICE, "label": "Home", "added_at": "2026-10-01T08:00:00+00:00",
             "paused": [["not a time", None], ["2026-10-07T14:00:00+00:00"], 7]}]}))
        self.assertEqual(self.both_roads(OFFICE, NOW), "Home")

    def test_config_entries_cannot_be_paused_edited_or_deleted(self):
        ours_store.add(self.config, OFFICE, "Office Mac", now=NOW)
        for act in (lambda k: ours_store.pause(self.config, k),
                    lambda k: ours_store.resume(self.config, k),
                    lambda k: ours_store.edit(self.config, k, label="x"),
                    lambda k: ours_store.remove(self.config, k)):
            for key in ("192.0.2.10", "Config office"):
                with self.assertRaises(ours_store.Invalid) as got:
                    act(key)
                self.assertIn("config.yml", str(got.exception))
        self.assertFalse(ours_store.listing(self.config)[0]["pausable"])
        # Two entries with one label: name it by its address.
        ours_store.add(self.config, LAPTOP, "office mac", now=NOW)
        with self.assertRaises(ours_store.Invalid):
            ours_store.pause(self.config, "Office Mac")
        ours_store.pause(self.config, LAPTOP, now=NOW)

    def test_edit_ends_the_old_entry_and_starts_a_new_one(self):
        ours_store.add(self.config, OFFICE, "Office Mac", now=NOW)
        ours_store.pause(self.config, OFFICE, now=NOW + timedelta(hours=1))
        edit_at = NOW + timedelta(hours=2)
        with self.assertRaises(ours_store.Invalid):
            ours_store.edit(self.config, OFFICE, now=edit_at)          # nothing to change
        with self.assertRaises(ours_store.Invalid):
            ours_store.edit(self.config, OFFICE, ip="192.0.2.10", now=edit_at)  # listed
        ours_store.edit(self.config, OFFICE, label="Office", ip=NEW, now=edit_at, by="owner")
        rows = ours_store.listing(self.config)
        self.assertEqual([(r["ip"], r["label"], r["active"]) for r in rows[1:]],
                         [(NEW, "Office", False)])      # the open pause carries over
        old, new = ours_store.load(self.file)
        self.assertEqual((old["removed_at"], old["replaced_by"]), (edit_at.isoformat(), NEW))
        self.assertEqual(new["paused"], [[edit_at.isoformat(), None]])
        ours_store.resume(self.config, "Office", now=edit_at + timedelta(hours=1))
        for when, address, label in ((NOW, OFFICE, "Office Mac"), (edit_at, OFFICE, ""),
                                     (edit_at + timedelta(hours=1), NEW, "Office"),
                                     (NOW, NEW, ""), (edit_at, NEW, "")):
            self.assertEqual(self.both_roads(address, when), label, (when, address))
        self.assertEqual(self.actions(), ["add", "pause", "edit", "resume"])
        log = (self.root / "ours-changes.log").read_text().splitlines()[2].split("\t")
        self.assertEqual(log[2], "Office Mac -> Office")
        # The old address may be added again: it is no longer listed.
        ours_store.add(self.config, OFFICE, "Back again", now=edit_at + timedelta(hours=3))

    def test_delete_stays_in_the_file_for_the_days_before(self):
        ours_store.add(self.config, OFFICE, "Office Mac", now=NOW)
        ours_store.remove(self.config, "Office Mac", now=NOW + timedelta(hours=1), by="owner")
        self.assertEqual([r["source"] for r in ours_store.listing(self.config)], ["config"])
        self.assertEqual(ours_store.load(self.file)[0]["removed_at"],
                         (NOW + timedelta(hours=1)).isoformat())
        self.assertEqual(self.both_roads(OFFICE, NOW + timedelta(minutes=30)), "Office Mac")
        self.assertEqual(self.both_roads(OFFICE, NOW + timedelta(hours=1)), "")
        with self.assertRaises(ours_store.Invalid):
            ours_store.remove(self.config, OFFICE)
        # Deleted entries do not hold places in the list.
        for i in range(ours_store.LIMIT - 1):
            ours_store.add(self.config, f"203.0.113.{i}", f"n{i}", now=NOW)
        # The dashboard's box lists what applies; a paused one says so.
        from skald.config import ours_rules
        ours_store.pause(self.config, "n0", now=NOW)
        rules = {r["label"]: r for r in ours_rules(self.config) if r["source"] == "file"}
        self.assertNotIn("Office Mac", rules)
        self.assertTrue(rules["n0"]["paused"])
        self.assertFalse(rules["n1"]["paused"])


class Helper(Base):

    def request(self, path, body):
        runner = type("R", (), {"calls": [], "refresh": lambda self, force=False: None})()
        handler = make_handler(runner, {"https://www.example.com"}, self.config)
        data = json.dumps(body).encode()
        raw = (f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {len(data)}\r\n"
               "Sec-Fetch-Site: same-origin\r\nContent-Type: application/json\r\n\r\n").encode() + data
        out = io.BytesIO()

        class Socket:
            def makefile(self, mode, *a, **k):
                return io.BytesIO(raw)

            def sendall(self, chunk):
                out.write(chunk)

        handler(Socket(), ("127.0.0.1", 5555), None)
        head, _, rest = out.getvalue().partition(b"\r\n\r\n")
        return int(head.split()[1]), json.loads(rest)

    def test_pause_resume_edit_delete_through_the_helper(self):
        for act in ("pause", "resume", "edit"):
            self.assertEqual(ours_action(f"/traffic/example.com/ours/{act}"), act)
        T = "/traffic/example.com/ours/"
        self.assertEqual(self.request(T + "add", {"ip": OFFICE, "label": "Office Mac"})[0], 200)
        code, body = self.request(T + "pause", {"ip": OFFICE})
        self.assertEqual(code, 200, body)
        row = [e for e in body["entries"] if e["ip"] == OFFICE][0]
        self.assertFalse(row["active"])
        self.assertTrue(row["paused_since"])
        code, body = self.request(T + "pause", {"ip": OFFICE})
        self.assertEqual(code, 400)
        self.assertIn("already paused", body["error"])
        code, body = self.request(T + "resume", {"ip": OFFICE})
        self.assertTrue([e for e in body["entries"] if e["ip"] == OFFICE][0]["active"])
        code, body = self.request(T + "edit", {"ip": OFFICE, "label": "Office", "new_ip": NEW})
        self.assertEqual(code, 200, body)
        self.assertEqual([e["label"] for e in body["entries"] if e["ip"] == NEW], ["Office"])
        code, body = self.request(T + "pause", {"ip": "192.0.2.10"})
        self.assertEqual(code, 400)
        code, body = self.request(T + "remove", {"ip": NEW})
        self.assertEqual(code, 200)
        self.assertEqual([e["source"] for e in body["entries"]], ["config"])
        self.assertEqual(self.actions(), ["add", "pause", "resume", "edit", "remove"])


class BothRoadsOnADay(unittest.TestCase):
    """A day with a pause in the middle collects and audits "all match"; an
    edit and a delete afterwards leave that day recounting the same."""

    DAY = "2026-10-05"
    T = datetime(2026, 10, 5, 15, tzinfo=UTC)

    def setUp(self):
        self.box = Sandbox()
        T = self.T
        (self.box.root / "ours.json").write_text(json.dumps({"entries": [
            {"ip": OFFICE, "label": "Office Mac", "added_at": "2026-10-01T00:00:00+00:00",
             "added_from": "page",
             "paused": [[(T - timedelta(hours=1)).isoformat(), (T + timedelta(hours=1)).isoformat()]]},
            {"ip": LAPTOP, "label": "Test laptop", "added_at": "2026-10-01T00:00:00+00:00",
             "added_from": "page", "paused": [[(T + timedelta(hours=1)).isoformat(), None]]}]}))
        from datetime import date
        self.box.log(day_lines(date(2026, 10, 5), 3) + [
            line(T - timedelta(hours=2), OFFICE, "/", CHROME),     # ours
            line(T, OFFICE, "/guides/beta", CHROME),               # paused: a visitor
            line(T + timedelta(hours=2), OFFICE, "/", CHROME),     # ours again
            line(T - timedelta(minutes=30), LAPTOP, "/", CHROME),  # ours
            line(T + timedelta(hours=3), LAPTOP, "/pricing", CHROME),  # paused: a visitor
        ])

    def tearDown(self):
        self.box.close()

    def stored(self):
        db = sqlite3.connect(self.box.db)
        try:
            return sorted(db.execute("SELECT kind, name, n FROM counts WHERE day = ?",
                                     (self.DAY,)))
        finally:
            db.close()

    def labels(self):
        return {name: n for kind, name, n in self.stored() if kind == "ours_label"}

    def audit(self):
        code, out, err = self.box.run("--today", "2026-10-06", "audit", "--day", self.DAY)
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)

    def test_a_pause_in_the_middle_counts_and_audits(self):
        code, _, err = self.box.run("--today", "2026-10-06", "collect", "--day", self.DAY)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.labels(), {"Office Mac": 2, "Test laptop": 1})
        self.audit()
        before = self.stored()
        # Edit, then delete, long after the day: the day recounts the same.
        code, out, err = self.box.run("ours", "edit", "Office Mac", "--label", "Office",
                                      "--address", NEW)
        self.assertEqual(code, 0, err)
        self.audit()
        code, out, err = self.box.run("ours", "delete", "Test laptop", "--yes")
        self.assertEqual(code, 0, err)
        self.audit()
        code, _, err = self.box.run("--today", "2026-10-06", "collect", "--day", self.DAY)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.stored(), before)
        self.audit()

    def test_live_with_a_pause_recounts_exactly(self):
        now = self.T + timedelta(hours=5)
        with mock.patch("skald.cli._now", return_value=now):
            self.assertEqual(self.box.run("live")[0], 0)
            code, out, err = self.box.run("audit", "--live")
        self.assertEqual(code, 0, err)
        self.assertIn("all match", out)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["ours_labels"], {"Office Mac": 2, "Test laptop": 1})


class Cli(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.config.write_text(self.box.config.read_text().replace(
            "ours:\n  user_agents: [MyCompanyCrawler]\n",
            "ours:\n  user_agents: [MyCompanyCrawler]\n"
            "  addresses:\n    - {ip: 192.0.2.10, label: Config office}\n"))
        (self.box.root / "ours.json").write_text(json.dumps({"entries": [
            {"ip": OFFICE, "label": "Office Mac", "added_at": "2026-10-01T00:00:00+00:00",
             "added_from": "page"}]}))

    def tearDown(self):
        self.box.close()

    def test_list_pause_resume_edit_delete(self):
        code, out, err = self.box.run("ours", "list")
        self.assertEqual(code, 0, err)
        self.assertIn("Config office\tconfig.yml\talways on", out)
        self.assertIn("Office Mac\tpage\tactive", out)
        code, out, err = self.box.run("ours", "pause", "Office Mac")
        self.assertEqual(code, 0, err)
        self.assertIn("Paused Office Mac", out)
        self.assertIn("Office Mac\tpage\tpaused since 20", self.box.run("ours", "list")[1])
        self.assertEqual(self.box.run("ours", "pause", OFFICE)[0], 1)
        self.assertEqual(self.box.run("ours", "resume", OFFICE)[0], 0)
        code, _, err = self.box.run("ours", "pause", "Config office")
        self.assertEqual(code, 1)
        self.assertIn("config.yml", err)
        self.assertEqual(self.box.run("ours", "edit", "Office Mac")[0], 2)
        self.assertEqual(self.box.run("ours", "edit", "Office Mac", "--label", "Office")[0], 0)
        code, _, err = self.box.run("ours", "delete", "Office")
        self.assertEqual(code, 2)
        self.assertIn("--yes", err)
        code, out, err = self.box.run("ours", "delete", "Office", "--yes")
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("ours", "list")
        self.assertNotIn("Office\tpage", out)
        # Nothing printed names an address.
        everything = out + err
        for args in (("list",), ("pause", "nobody")):
            got = self.box.run("ours", *args)
            everything += got[1] + got[2]
        for address in (OFFICE, "192.0.2.10"):
            self.assertNotIn(address, everything)


if __name__ == "__main__":
    unittest.main()
