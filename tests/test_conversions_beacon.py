"""Phase 4b step 2: the visitor ID on the beacon, beacon events made into
conversions and journeys, abandonment, pruning, the second count from the
beacon spool, forget, and the snippet's route. Addresses are RFC 5737;
hosts example.com."""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import mmdb  # noqa: E402

from skald import audit_conversions, beacon  # noqa: E402
from skald.beacon_server import Limiter, Sink, make_handler  # noqa: E402
from skald.conversions import BEACON_ACTIONS, from_beacon, store  # noqa: E402

UTC = timezone.utc
T = 1791720000          # 2026-10-11 12:00 UTC
DAY = date(2026, 10, 11)
VID = "skv_" + "A" * 22
VID2 = "skv_" + "b-_" * 7 + "c"
ORIGIN = "https://www.example.com"
CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def body(**kw) -> bytes:
    out = {"e": "form_start", "p": "/contact/", "id": "contact", "v": VID}
    out.update(kw)
    return json.dumps({k: v for k, v in out.items() if v is not None}).encode()


class Validate(unittest.TestCase):
    def test_visitor_id_kept_only_in_its_shape(self):
        self.assertEqual(beacon.validate(body())["v"], VID)
        self.assertEqual(beacon.validate(body(v=VID2))["v"], VID2)
        for bad in ("skv_short", "skv_" + "A" * 23, "abc_" + "A" * 22, "skv_" + "A" * 21 + "!", VID + "\n",
                    123, None, "person@example.com"):
            self.assertNotIn("v", beacon.validate(body(v=bad)), bad)

    def test_new_events_and_old_ones(self):
        for name in ("form_start", "form_submit", "calendly_open", "calendly_time_selected",
                     "calendly_booked", "cal_open", "cal_booked", "hubspot_meeting_booked",
                     "signup_start", "signup_submit", "tel_click", "mailto_click", "cta_click",
                     "outbound_click", "book_demo_open", "demo_booked", "scroll_75"):
            self.assertEqual(beacon.validate(body(e=name))["e"], name)
            self.assertIn(name, beacon.LABELS)
        with self.assertRaises(beacon.Refused):
            beacon.validate(body(e="page_view"))

    def test_page_view_with_visitor_ids(self):
        self.assertIn("page_view", beacon.allowed_events({"beacon": {"visitor_ids": True}}))
        self.assertNotIn("page_view", beacon.allowed_events({}))
        self.assertFalse(beacon.visitor_ids({}))
        self.assertTrue(beacon.visitor_ids({"beacon": {"visitor_ids": "true"}}))

    def test_every_mapped_event_is_a_beacon_event(self):
        for name, (action, stage) in BEACON_ACTIONS.items():
            self.assertIn(name, beacon.EVENTS)
            self.assertIn(stage, ("started", "completed"))
        self.assertEqual({a for a, _ in BEACON_ACTIONS.values()},
                         {"contact", "signup", "waitlist", "demo", "call", "email", "cta"})
        self.assertEqual(BEACON_ACTIONS["calendly_booked"], ("demo", "completed"))
        self.assertEqual(BEACON_ACTIONS["tel_click"], ("call", "completed"))


class Server(unittest.TestCase):
    ids = True

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.spool = self.folder / "beacon"
        (self.folder / "country.mmdb").write_bytes(mmdb({"203.0.113.0/24": "CA"}))
        self.db_path = self.folder / "conversions.sqlite"
        self.config = {"site": {"name": "example.com", "hosts": ["www.example.com"]},
                       "report": {"timezone": "UTC"},
                       "history": {"db": str(self.folder / "history.sqlite")},
                       "ours": {"addresses": ["198.51.100.99"],
                                "file": str(self.folder / "ours.json")},
                       "beacon": {"visitor_ids": self.ids},
                       "conversions": {"country_db": str(self.folder / "country.mmdb")}}
        self.now = T
        self.sink = Sink(self.config, self.spool, clock=lambda: self.now)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            self.sink, Limiter(per_minute=6000, burst=1000), {ORIGIN}))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, method, path, raw=b"", **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        conn.request(method, path, body=raw or None, headers=headers)
        got = conn.getresponse()
        out = (got.status, dict(got.getheaders()), got.read())
        conn.close()
        return out

    def post(self, raw=None, ip="203.0.113.7", agent=CHROME, after=0):
        self.now += after
        return self.request("POST", "/traffic-beacon", raw if raw is not None else body(),
                            **{"Origin": ORIGIN, "User-Agent": agent, "X-Real-IP": ip,
                               "Content-Type": "text/plain"})[0]

    def lines(self):
        return beacon.read_day(self.spool, DAY)

    def rows(self, sql="SELECT * FROM conversions ORDER BY id"):
        db = store.connect(self.db_path)
        try:
            return [dict(r) for r in db.execute(sql)]
        finally:
            db.close()


class VisitorIdsOn(Server):
    def test_page_view_makes_a_journey(self):
        self.assertEqual(self.post(body(e="page_view", p="/pricing/", id=None, r="google.com")),
                         204)
        self.assertEqual(self.lines()[0]["v"], VID)
        pages = self.rows("SELECT * FROM journeys")
        self.assertEqual([(p["vid"], p["path"], p["source_type"], p["at"]) for p in pages],
                         [(VID, "/pricing/", "Search engine", "2026-10-11T12:00:00Z")])
        self.assertEqual(self.rows(), [])

    def test_a_start_is_a_conversion_with_country_and_device_not_address(self):
        self.post(body(e="page_view", p="/", id=None))
        self.post(body(e="page_view", p="/contact/", id=None), after=60)
        self.assertEqual(self.post(after=30), 204)
        self.assertEqual(self.post(body(e="calendly_booked"), ip="203.0.113.9", agent=IPHONE),
                         204)
        got = self.rows()
        self.assertEqual([(r["action"], r["stage"], r["tool"], r["vid"]) for r in got],
                         [("contact", "started", "beacon", VID),
                          ("demo", "completed", "beacon", VID)])
        self.assertEqual((got[0]["country"], got[0]["device"], got[1]["device"]),
                         ("CA", "Desktop", "Mobile"))
        self.assertEqual(got[0]["landing"], "/")
        self.assertEqual(got[0]["at"], "2026-10-11T12:01:30Z")
        everything = json.dumps(self.rows("SELECT * FROM conversions")) + \
            beacon.day_file(self.spool, DAY).read_text()
        for secret in ("203.0.113.7", "203.0.113.9", "Chrome", "iPhone"):
            self.assertNotIn(secret, everything)

    def test_one_per_visitor_action_and_stage_per_30_minutes(self):
        self.post()
        self.post(after=600)                      # 10 min: a repeat
        self.post(body(e="calendly_open"))        # another action
        self.post(body(e="form_start", v=VID2))   # another browser
        self.post(after=1300)                     # 31m40s after the first kept one
        got = self.rows()
        self.assertEqual(len(got), 4)
        self.assertEqual(len(self.lines()), 5)    # every event still in the spool

    def test_ours_and_no_id_and_page_events_make_no_conversion(self):
        self.post(ip="198.51.100.99")
        self.post(body(v=None))
        self.post(body(e="scroll_75", id=None))
        self.post(body(e="outbound_click", id="calendly.com"))
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.rows("SELECT * FROM journeys"), [])
        self.assertEqual(len(self.lines()), 4)

    def test_abandoned_by_the_configured_hours(self):
        self.post()                               # contact started, never sent
        self.post(body(v=VID2))
        self.post(body(e="form_submit", v=VID2), after=600)
        self.config["conversions"]["abandon_hours"] = 2
        db = store.connect(self.db_path)
        try:
            early = from_beacon.abandoned(db, self.config, "example.com",
                                          "2026-10-11T00:00:00Z", "2026-10-12T00:00:00Z",
                                          now="2026-10-11T13:00:00Z")
            late = from_beacon.abandoned(db, self.config, "example.com",
                                         "2026-10-11T00:00:00Z", "2026-10-12T00:00:00Z",
                                         now="2026-10-11T14:30:00Z")
        finally:
            db.close()
        self.assertEqual(early, [])
        self.assertEqual([(r["vid"], r["action"]) for r in late], [(VID, "contact")])
        self.assertEqual(from_beacon.abandon_hours({}), 24)

    def test_journeys_pruned_unless_the_id_converted(self):
        self.post(body(e="page_view", id=None))
        self.post(body(e="page_view", id=None, v=VID2))
        self.post(body(e="form_submit", v=VID2))
        db = store.connect(self.db_path)
        try:
            store.prune(db, DAY + timedelta(days=31), from_beacon.vid_days({}))
            left = [r[0] for r in db.execute("SELECT vid FROM journeys")]
        finally:
            db.close()
        self.assertEqual(left, [VID2])
        self.assertEqual(from_beacon.vid_days({"journeys": {"vid_days": 7}}), 7)

    def test_snippet_route(self):
        status, headers, raw = self.request("GET", "/traffic-js/skald.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])
        self.assertIn("max-age=", headers["Cache-Control"])
        self.assertIn(b"IDS=1", raw)
        tag = headers["ETag"]
        status, headers, raw = self.request("GET", "/traffic-js/skald.js?x=1",
                                            **{"If-None-Match": tag})
        self.assertEqual((status, raw), (304, b""))
        self.assertEqual(self.request("HEAD", "/traffic-js/skald.js")[0], 200)
        self.assertEqual(self.request("GET", "/traffic-js/other.js")[0], 404)
        self.assertEqual(self.request("GET", "/traffic-beacon")[0], 405)

    def test_second_count_agrees_and_catches_a_lost_row(self):
        self.post(body(e="page_view", id=None))
        self.post()
        self.post(after=600)
        self.post(after=1300)
        self.post(body(e="calendly_booked"))
        self.post(body(e="tel_click", id=None), ip="198.51.100.99")     # ours
        self.now = T + 12 * 3600 - 5                                      # 23:59:55
        self.post(body(e="cal_open"))
        found = audit_conversions.findings(self.config, self.folder, "example.com", UTC,
                                           DAY - timedelta(days=3), DAY + timedelta(days=1))
        self.assertEqual(found, {})
        counted = audit_conversions.recount_beacon(self.spool, UTC, DAY, DAY)
        self.assertEqual(counted[DAY.isoformat()], {("contact", "started"): 2,
                                                    ("demo", "completed"): 1,
                                                    ("demo", "started"): 1})
        db = store.connect(self.db_path)
        db.execute("DELETE FROM conversions WHERE action = 'demo' AND stage = 'completed'")
        db.close()
        found = audit_conversions.findings(self.config, self.folder, "example.com", UTC,
                                           DAY, DAY)
        self.assertIn("demo completed: stored 0, recounted from the spool 1",
                      found[DAY.isoformat()][0])
        ctx = SimpleNamespace(config=self.config, db_path=self.folder / "history.sqlite",
                              site="example.com", tz=UTC)
        self.assertTrue(audit_conversions.daily(ctx, DAY))

    def test_second_count_reads_its_own_spool_line_too(self):
        self.post()
        line = {"at": "2026-10-11T12:40:00+00:00", "e": "signup_start", "g": "people",
                "id": "", "p": "/", "r": "", "s": "Direct or unknown", "t": 0, "u": "",
                "v": VID, "vw": ""}
        with open(beacon.day_file(self.spool, DAY), "a") as out:
            out.write(json.dumps(line) + "\n")
        found = audit_conversions.findings(self.config, self.folder, "example.com", UTC,
                                           DAY, DAY)
        self.assertIn("signup started: stored 0", found[DAY.isoformat()][0])

    def test_forget_takes_the_id_out_of_the_beacon_spool(self):
        self.post(body(e="page_view", id=None))
        self.post()
        self.post(body(v=VID2))
        gone = from_beacon.scrub_spool(self.spool, {VID.lower()}, dry_run=True)
        self.assertEqual(gone, 2)
        self.assertEqual(sum(1 for r in self.lines() if r.get("v") == VID), 2)
        self.assertEqual(from_beacon.scrub_spool(self.spool, {VID.lower()}), 2)
        rows = self.lines()
        self.assertEqual(len(rows), 3)                 # the events stay, for the event audit
        self.assertEqual([r.get("v") for r in rows], [None, None, VID2])


class ForgetCommand(unittest.TestCase):
    def test_forget_vid_clears_it_from_the_beacon_spool(self):
        from support import Sandbox
        box = Sandbox(mail=False)
        try:
            spool = box.root / "beacon"
            spool.mkdir()
            line = {"at": "2026-10-11T12:00:00+00:00", "e": "form_start", "g": "people",
                    "id": "", "p": "/", "r": "", "s": "Direct or unknown", "t": 0, "u": "",
                    "v": VID, "vw": ""}
            beacon.day_file(spool, DAY).write_text(json.dumps(line) + "\n")
            db = store.connect(box.root / "conversions.sqlite")
            store.record_page_view(db, "example.com", VID, "2026-10-11T12:00:00Z", "/", None)
            db.close()
            code, out, _ = box.run("conversions", "forget", "--vid", VID)
            self.assertEqual(code, 0)
            self.assertIn("1 page view(s)", out)
            self.assertIn("1 spool line(s)", out)
            self.assertNotIn(VID, beacon.day_file(spool, DAY).read_text())
            self.assertEqual(len(beacon.read_day(spool, DAY)), 1)
        finally:
            box.close()


class VisitorIdsOff(Server):
    ids = False

    def test_default_keeps_todays_behaviour(self):
        self.assertEqual(self.post(), 204)
        self.assertNotIn("v", self.lines()[0])
        self.assertEqual(self.post(body(e="page_view", id=None)), 202)   # quietly not kept
        self.assertEqual(len(self.lines()), 1)
        self.assertFalse(self.db_path.exists())
        self.sink.close()
        self.assertEqual(beacon.read_stats(self.spool, DAY)["page_view_off"], 1)

    def test_snippet_served_without_ids(self):
        status, _headers, raw = self.request("GET", "/traffic-js/skald.js")
        self.assertEqual(status, 200)
        self.assertIn(b"IDS=0", raw)
        self.assertNotIn(b"IDS=1", raw)


if __name__ == "__main__":
    unittest.main()
