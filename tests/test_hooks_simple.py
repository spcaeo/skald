"""2.4.0's hook fixes: the Calendly and Cal.com event-type filter, a time
without an offset read in the site's zone (and the second count agreeing),
a test that shows what a real delivery keeps, one lead from two tools, each
hook's state in words, and `hooks secret` printing the real address.
Hosts are example.com; the secrets are made up."""
from __future__ import annotations

import json
import sys
import threading
import unittest
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import VID  # noqa: E402
from support import Sandbox  # noqa: E402
from test_conversions_hooks import T, Base, lead  # noqa: E402

from skald import audit_conversions, settings_store  # noqa: E402
from skald.config import load_config  # noqa: E402
from skald.conversions import event_types, roads, store  # noqa: E402
from skald.conversions.adapters import adapter, naive, when  # noqa: E402
from skald.conversions.hooks import handle  # noqa: E402

TYPE_A = "https://api.calendly.com/event_types/AAAA1111"
TYPE_B = "https://api.calendly.com/event_types/BBBB2222"
NY = ZoneInfo("America/New_York")


def booked(invitee: str, kind: str = TYPE_A, name: str = "Product demo", event="invitee.created"):
    return {"event": event, "created_at": "2026-10-11T11:00:00Z",
            "payload": {"uri": invitee, "scheduled_event": {"event_type": kind, "name": name}}}


def calcom(uid: str, type_id=1234, slug="30min", trigger="BOOKING_CREATED"):
    return {"triggerEvent": trigger, "createdAt": "2026-10-11T11:00:00Z",
            "payload": {"uid": uid, "eventTypeId": type_id, "type": slug}}


class EventTypes(Base):
    def keep(self, tool: str, items: list):
        self.config["hooks"][f"{tool}_event_types"] = items

    def outcomes(self):
        return self.rows("SELECT outcome, error FROM deliveries ORDER BY id")

    def test_empty_keeps_every_event(self):
        self.assertEqual(self.post("calendly", booked("I-1", TYPE_B))[1]["recorded"], 1)

    def test_other_types_are_answered_and_not_kept(self):
        self.keep("calendly", [TYPE_A])
        status, answer = self.post("calendly", booked("I-1", TYPE_B))
        self.assertEqual((status, answer["recorded"], answer["outcome"]),
                         (200, 0, "ignored: other event type"))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 0)
        self.assertEqual(self.spooled(), "", "not even in the spool")
        outcome, error = self.outcomes()[-1]
        self.assertEqual(outcome, "ignored")
        self.assertIn(TYPE_B, error, "the log names the type, so it can be copied")
        self.assertEqual(self.post("calendly", booked("I-2", TYPE_A))[1]["recorded"], 1)
        self.assertIn("I-2", self.spooled())

    def test_a_uuid_or_a_slug_matches_too(self):
        self.keep("calendly", ["AAAA1111"])
        self.assertEqual(self.post("calendly", booked("I-1"))[1]["recorded"], 1)
        self.keep("calendly", ["https://calendly.com/acme/product-demo"])
        self.assertEqual(self.post("calendly", booked("I-2", TYPE_B))[1]["recorded"], 1)
        self.assertEqual(self.post("calendly", booked("I-3", TYPE_B, "Sales call"))[1]
                         .get("outcome"), "ignored: other event type")

    def test_a_no_show_follows_its_stored_booking(self):
        self.keep("calendly", [TYPE_A])
        self.post("calendly", booked("I-1"))
        self.post("calendly", booked("I-9", TYPE_B))                      # not kept
        for invitee, kept in (("I-1", 1), ("I-9", 0)):
            show = {"event": "invitee_no_show.created", "created_at": "2026-10-11T11:30:00Z",
                    "payload": {"invitee": invitee, "uri": "https://api.calendly.com/x"}}
            self.assertEqual(self.post("calendly", show)[1]["recorded"], kept, invitee)
        self.assertEqual(self.rows("SELECT external_ref, stage FROM conversions ORDER BY id"),
                         [("I-1", "completed"), ("I-1", "no_show")])

    def test_calcom_by_id_or_slug(self):
        self.keep("calcom", ["1234"])
        self.assertEqual(self.post("calcom", calcom("B-1"))[1]["recorded"], 1)
        self.assertEqual(self.post("calcom", calcom("B-2", 99, "other"))[1]["recorded"], 0)
        self.keep("calcom", ["https://cal.com/acme/30min"])
        self.assertEqual(self.post("calcom", calcom("B-3", 77))[1]["recorded"], 1)
        cancelled = calcom("B-3", trigger="BOOKING_CANCELLED")
        del cancelled["payload"]["eventTypeId"], cancelled["payload"]["type"]
        self.assertEqual(self.post("calcom", cancelled)[1]["recorded"], 1, "its booking is kept")

    def test_the_nested_config_form(self):
        self.config["hooks"]["calendly"] = {"event_types": [TYPE_A]}
        self.assertEqual(event_types.from_config(self.config, "calendly"), [TYPE_A])
        self.assertEqual(self.post("calendly", booked("I-1", TYPE_B))[1]["recorded"], 0)

    def test_a_test_says_what_a_real_one_keeps(self):
        self.keep("calendly", [TYPE_A])
        sample = adapter("calendly").sample("example.com", T)
        status, got = self.post("calendly", sample, extra={"X-Skald-Test": "1"})
        self.assertEqual((status, got["records"], got["would_keep"], got["read"]), (200, 1, 0, []))
        self.assertIn("ignored: other event type", " ".join(got["notes"]))
        self.assertEqual(self.outcomes()[-1][0], "test")

    def test_settings_check_the_list(self):
        key = "hooks.calendly.event_types"
        self.assertEqual(settings_store.validate(key, f"{TYPE_A}, demo demo"), [TYPE_A, "demo"])
        self.assertIsNone(settings_store.validate(key, []))
        with self.assertRaises(settings_store.Invalid):
            settings_store.validate(key, ["two words"])
        with self.assertRaises(settings_store.Invalid):
            settings_store.validate(key, [str(i) for i in range(51)])
        self.keep("calendly", ["demo"])
        got = settings_store.explain(self.config, "example.com")[key]
        self.assertEqual((got["value"], got["source"]), (["demo"], "config"))


class VisitorIdsOffTest(Base):
    visitor_ids = False

    def test_the_test_drops_the_visitor_id_as_the_real_path_does(self):
        status, got = self.post("lead", lead(), extra={"X-Skald-Test": "1"})
        self.assertEqual(status, 200)
        self.assertIsNone(got["read"][0]["vid"])
        self.assertIn("visitor IDs are off", " ".join(got["notes"]))


class SiteZone(Base):
    def setUp(self):
        super().setUp()
        self.config["report"] = {"timezone": "America/New_York"}

    def test_a_time_without_an_offset_is_the_sites(self):
        self.assertTrue(naive("2026-10-10") and naive("2026-10-10T08:00:00"))
        self.assertFalse(naive("2026-10-10T08:00:00Z") or naive("1791720000") or naive(5))
        self.assertEqual(when("2026-10-10", NY), "2026-10-10T04:00:00Z")
        self.assertEqual(when("2026-10-10"), "2026-10-10T00:00:00Z", "no zone given: UTC")
        self.post("lead", lead(external_ref="L-1", at="2026-10-10"))
        self.post("lead", lead(external_ref="L-2", at="2026-10-10T08:00:00",
                               first_touch={"landing": "/", "at": "2026-10-01T09:00:00"}))
        self.post("lead", lead(external_ref="L-3", at="2026-10-10T08:00:00Z"))
        got = self.rows("SELECT external_ref, at, first_touch_at FROM conversions ORDER BY id")
        self.assertEqual(got, [("L-1", "2026-10-10T04:00:00Z", None),
                               ("L-2", "2026-10-10T12:00:00Z", "2026-10-01T13:00:00Z"),
                               ("L-3", "2026-10-10T08:00:00Z", None)])
        notes = [e for _, e in self.rows("SELECT outcome, error FROM deliveries ORDER BY id")]
        self.assertIn("America/New_York", notes[0])
        self.assertIsNone(notes[2])
        lines = [json.loads(x) for x in self.spooled().splitlines()]
        self.assertEqual([x.get("zone") for x in lines], ["America/New_York"] * 2 + [None])

    def test_the_second_count_reads_each_line_as_it_was_kept(self):
        self.post("lead", lead(external_ref="L-1", at="2026-10-10"))
        self.assertEqual(audit_conversions.findings(self.config, self.folder, "example.com", NY,
                                                    date(2026, 10, 1), date(2026, 10, 11)), {})
        day = audit_conversions.recount(self.folder / "hooks", "example.com", NY,
                                        date(2026, 10, 9), date(2026, 10, 10))
        self.assertEqual(day, {"2026-10-10": {("demo", "completed"): 1}})
        # An old line without a zone is read as UTC, as it was kept then.
        old = {"received_at": "2026-10-11T12:00:00Z", "site": "example.com", "tool": "lead",
               "body": {"external_ref": "OLD", "action": "demo", "at": "2026-10-10"}}
        self.assertEqual(audit_conversions._read("lead", old["body"],
                                                 audit_conversions._zone_of(old))[0][3],
                         datetime(2026, 10, 10, tzinfo=timezone.utc))


class States(Base):
    def states(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            return {s["tool"]: s for s in roads.hook_states(
                self.config, self.folder, "example.com", db,
                datetime.fromtimestamp(T + 7200, timezone.utc), "skald", "https://x.example.com")}
        finally:
            db.close()

    def test_never_ready_received_and_refused(self):
        got = self.states()
        self.assertEqual((got["lead"]["state"], got["lead"]["attention"]), ("never", True))
        self.assertIn("skald hooks test example.com lead", got["lead"]["fix"])
        self.post("lead", lead(), extra={"X-Skald-Test": "1"})
        self.assertEqual(self.states()["lead"]["state"], "ready")
        self.post("lead", lead())
        got = self.states()["lead"]
        self.assertEqual((got["state"], got["attention"]), ("received", False))
        self.assertEqual(got["words"], "last received 2 h ago (kept)")
        self.post("lead", lead(), secret="not-the-secret")
        got = self.states()["lead"]
        self.assertTrue(got["attention"])
        self.assertIn("the signature did not match", got["words"])
        self.assertIn("hooks secret example.com lead", got["fix"])

    def test_one_lead_from_two_tools(self):
        self.post("lead", lead(external_ref="L-9"))
        self.post("json", {"records": [lead(external_ref="L-9"), lead(external_ref="L-10")]})
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            got = roads.duplicates(db, "example.com")
        finally:
            db.close()
        self.assertEqual([(d["ref"], d["tools"]) for d in got], [("L-9", ["json", "lead"])])


class Commands(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox(mail=False)

    def tearDown(self):
        self.box.close()

    def serve(self):
        config = load_config(self.box.config)
        folder = self.box.root

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                handle(self, config, folder)

            def log_message(self, *a):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_secret_prints_the_real_address(self):
        _, out, _ = self.box.run("hooks", "secret", "example.com", "lead")
        self.assertIn("address: https://<your site>/traffic-hooks/example.com/lead", out)
        self.assertIn("set access.base_url", out)
        self.box.config.write_text(self.box.config.read_text()
                                   + "access:\n  base_url: https://stats.example.com/\n")
        _, out, _ = self.box.run("hooks", "secret", "example.com", "lead")
        self.assertIn("address: https://stats.example.com/traffic-hooks/example.com/lead", out)

    def test_test_shows_what_is_kept(self):
        self.box.run("hooks", "secret", "example.com", "lead")
        url = self.serve()
        code, out, err = self.box.run("hooks", "test", "example.com", "lead", "--url", url)
        self.assertEqual(code, 0, out + err)
        self.assertIn("a real one would keep 1 of 1 record(s):", out)
        self.assertIn("action demo, stage completed", out)
        self.assertIn("visitor ID none", out, "visitor IDs are off by default")
        self.assertIn("note: visitor IDs are off for this site", out)
        self.assertNotIn(VID, out)


if __name__ == "__main__":
    unittest.main()
