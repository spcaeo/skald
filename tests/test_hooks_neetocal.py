"""SKALD-54: NeetoCal bookings, read from the bodies a real test booking sent
(tests/fixtures/neetocal/: create, update with reschedule_details, cancel).
The signature (raw and HTML-escaped body), each kind of event, the visitor ID
from the hidden `skv` question, the other answers never kept, a replay
refused, another business's scheduling link filtered out, and the second
count agreeing. Hosts are example.com; the secrets are made up."""
from __future__ import annotations

import copy
import hmac
import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, VID  # noqa: E402
from test_conversions_hooks import T, Base  # noqa: E402

from skald import audit_conversions  # noqa: E402
from skald.conversions import EVENTS, event_types, store  # noqa: E402
from skald.conversions.adapters import Invalid, adapter, signed  # noqa: E402
from skald.conversions.adapters import neetocal  # noqa: E402
from skald.conversions.hooks import refusal  # noqa: E402

UTC = timezone.utc
FIX = Path(__file__).resolve().parent / "fixtures" / "neetocal"
FIXTURE_VID = "skv_" + "Q" * 22
NOW = int(datetime(2026, 11, 25, 7, 0, tzinfo=timezone.utc).timestamp())   # after the booking


def real(name: str, sid: str | None = None, **changes) -> dict:
    """A real NeetoCal body (fixtures), with another booking sid and fields."""
    body = json.loads((FIX / f"{name}.json").read_text())
    if sid:
        body["webhook"]["sid"] = sid
    body["webhook"].update(changes)
    return body


def with_answers(body: dict, **codes) -> dict:
    body = copy.deepcopy(body)
    for code, value in codes.items():
        body["webhook"]["details"].append({"field": code, "question_label_at_booking": code,
                                           "value": value, "type": "text", "field_code": code})
    return body


class Adapter(unittest.TestCase):
    mod = adapter("neetocal")

    def headers(self, body, secret=SECRET):
        return {k.lower(): v for k, v in self.mod.sign(body, secret, T).items()}

    def test_signature_raw_and_escaped(self):
        body = json.dumps(with_answers(real("create"), note="a <b> & c")).encode()
        self.assertTrue(self.mod.verify(self.headers(body), body, SECRET, T))
        escaped = neetocal.escaped(body)
        self.assertNotEqual(escaped, body)
        on_escaped = {"x-neeto-webhook-signature": "sha256=" + hmac.new(
            SECRET.encode(), escaped, "sha256").hexdigest()}
        self.assertTrue(self.mod.verify(on_escaped, body, SECRET, T),
                        "NeetoCal's help signs the HTML-escaped body")
        self.assertFalse(self.mod.verify(self.headers(body, "another-secret"), body, SECRET, T))
        self.assertFalse(self.mod.verify({}, body, SECRET, T))
        self.assertFalse(self.mod.verify(self.headers(body), body + b" ", SECRET, T))

    def test_unsigned_is_told_apart(self):
        self.assertEqual(refusal("neetocal", {}), "unsigned")
        self.assertEqual(refusal("neetocal", {"x-neeto-webhook-signature": "sha256=00"}),
                         "bad_signature")
        self.assertFalse(signed("neetocal", {}))
        body = json.dumps(real("create")).encode()
        value = self.mod.sign(body, SECRET, T)["X-Neeto-Webhook-Signature"]
        self.assertTrue(self.mod.verify({"x-neeto-hook-secret-sha-256": value}, body, SECRET, T),
                        "NeetoCal's second header carries the same signature")

    def test_the_real_bodies(self):
        made = self.mod.to_records(neetocal.prepare(real("create")))[0]
        self.assertEqual((made["action"], made["stage"], made["external_ref"], made["at"],
                          made["vid"]),
                         ("demo", "completed", "y83xfzs", "2026-11-25T06:29:48Z", FIXTURE_VID))
        moved = self.mod.to_records(neetocal.prepare(real("update-rescheduled")))[0]
        self.assertEqual((moved["stage"], moved["external_ref"], moved["at"]),
                         ("rescheduled", "y83xfzs", None), "a change: Skald's receiving time")
        gone = self.mod.to_records(neetocal.prepare(real("cancel")))[0]
        self.assertEqual((gone["stage"], gone["external_ref"], gone["vid"]),
                         ("cancelled", "y83xfzs", None))

    def test_each_kind(self):
        b = neetocal.booking_of
        self.assertEqual(neetocal.kind(b(real("create"))), "create")
        self.assertEqual(neetocal.kind(b(real("create", status="awaiting_approval"))),
                         "create+awaiting_approval")
        self.assertEqual(neetocal.kind(b(real("update-rescheduled"))), "update+rescheduled")
        self.assertEqual(neetocal.kind(b(real("create", method="update"))), "update",
                         "notes, host or place changed: not a step")
        self.assertEqual(neetocal.kind(b(real("create", method="update",
                                              meeting_outcome="No show"))), "update+no_show")
        self.assertEqual(neetocal.kind(b(real("create", method="update", status="rejected"))),
                         "update+cancelled")
        self.assertEqual(neetocal.kind(b(real("cancel"))), "cancel")
        for name, (action, stage) in EVENTS["neetocal"].items():
            self.assertEqual(action, "demo", name)
        self.assertEqual(self.mod.to_records(real("create", method="update")), [])
        self.assertEqual(self.mod.to_records(real("create", method="start")), [])

    def test_not_a_body(self):
        for body in ({"hello": 1}, {"webhook": {"sid": "x"}}, [], "text"):
            with self.assertRaises(Invalid):
                self.mod.to_records(body)
        with self.assertRaises(Invalid):
            self.mod.to_records({"webhook": {"method": "create", "status": "confirmed"}})
        bare = real("create")["webhook"]
        self.assertEqual(self.mod.to_records(bare)[0]["external_ref"], "y83xfzs",
                         "the booking without its webhook wrapper")

    def test_visitor_id_and_touch(self):
        got = self.mod.to_records(with_answers(real("create"), utm_source="linkedin",
                                               utm_campaign="spring"))[0]
        self.assertEqual(got["vid"], FIXTURE_VID)
        self.assertEqual(got["last_touch"], {"utm_source": "linkedin", "utm_campaign": "spring"})
        body = real("create")
        body["webhook"]["details"] = [d for d in body["webhook"]["details"] if d["field_code"] != "skv"]
        self.assertIsNone(self.mod.to_records(body)[0]["vid"], "no hidden question: no journey")
        self.assertIsNone(self.mod.to_records(
            with_answers(body, skv="not-an-id"))[0]["vid"])

    def test_prepare_keeps_only_skv_utm_name_email(self):
        body = with_answers(real("create"), phone="+1 555 0100", company="Example Co",
                            utm_source="linkedin")
        got = neetocal.prepare(body)["webhook"]
        self.assertNotIn("details", got)
        self.assertEqual(set(got["form_responses_as_hash"]),
                         {"name", "email", "skv", "utm_source"})

    def test_the_link(self):
        link = neetocal.meeting_of(neetocal.booking_of(real("create")))
        self.assertEqual((link["sid"], link["slug"]), ("h2crxjx", "meeting-with-host-person"))
        self.assertEqual(neetocal.meeting_of(neetocal.booking_of(real("cancel"))),
                         {"id": None, "sid": None, "slug": None, "name": None})

    def test_sample_is_taken(self):
        got = self.mod.to_records(self.mod.sample("example.com", T))
        self.assertEqual((got[0]["stage"], got[0]["vid"]), ("completed", "skv_" + "A" * 22))


class Receiver(Base):
    def setUp(self):
        super().setUp()
        self.now = NOW

    def test_one_booking_three_steps(self):
        for name in ("create", "update-rescheduled", "cancel"):
            status, answer = self.post("neetocal", real(name))
            self.assertEqual((status, answer["recorded"]), (200, 1), name)
        rows = self.rows("SELECT stage, external_ref, vid, tool FROM conversions ORDER BY id")
        self.assertEqual(rows, [("completed", "y83xfzs", FIXTURE_VID, "neetocal"),
                                ("rescheduled", "y83xfzs", FIXTURE_VID, "neetocal"),
                                ("cancelled", "y83xfzs", None, "neetocal")])

    def test_other_updates_are_answered_and_not_kept(self):
        status, answer = self.post("neetocal", real("create", method="update"))
        self.assertEqual((status, answer["recorded"]), (200, 0))
        self.assertEqual(self.rows("SELECT outcome FROM deliveries"), [("ignored",)])

    def test_bad_signature_refused(self):
        self.assertEqual(self.post("neetocal", real("create"), secret="wrong")[0], 401)
        self.assertEqual(self.rows("SELECT outcome FROM deliveries"), [("bad_signature",)])

    def test_other_answers_and_hosts_never_kept(self):
        self.post("neetocal", with_answers(real("create"), phone="+1 555 0100",
                                           company="Example Co"))
        kept = self.spooled()
        for word in ("555 0100", "Example Co", "host@example.com", "Host Person", "jitsi",
                     "admin_booking_url", "skald.test@example.com"):
            self.assertNotIn(word, kept)
        self.assertIn(FIXTURE_VID, kept)

    def test_replay_refused(self):
        body = real("create")
        self.assertEqual(self.post("neetocal", body)[1]["recorded"], 1)
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.forget(db, "example.com", external_ref="y83xfzs")
        finally:
            db.close()
        lines = len(self.spooled())
        self.now = NOW + 3600
        status, answer = self.post("neetocal", body)
        self.assertEqual((status, answer["recorded"], answer["duplicates"]), (200, 0, 1))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 0,
                         "a replay does not bring back a forgotten booking")
        self.now = NOW
        self.assertEqual(len(self.spooled()), lines, "a replay is not spooled again")
        self.assertEqual(self.rows("SELECT outcome FROM deliveries ORDER BY id")[-1][0], "replay")

    def test_other_business_link_filtered(self):
        self.config["hooks"]["neetocal_event_types"] = ["https://example.neetocal.com/demo"]
        status, answer = self.post("neetocal", real("create"))
        self.assertEqual((status, answer["recorded"], answer["outcome"]),
                         (200, 0, event_types.IGNORED))
        self.assertEqual(self.spooled(), "", "not even in the spool")
        log = self.rows("SELECT outcome, error FROM deliveries")[-1]
        self.assertEqual(log[0], "ignored")
        self.assertIn("meeting-with-host-person", log[1])
        self.assertEqual(self.post("neetocal", real("cancel"))[1]["recorded"], 0,
                         "a cancellation names no link: its booking was not kept")
        self.config["hooks"]["neetocal_event_types"] = ["h2crxjx"]
        self.assertEqual(self.post("neetocal", real("create", "kept-1"))[1]["recorded"], 1,
                         "the link's sid")
        self.assertEqual(self.post("neetocal", real("cancel", "kept-1"))[1]["recorded"], 1,
                         "its cancellation: kept, its booking is")
        self.config["hooks"]["neetocal_event_types"] = [
            "https://example.neetocal.com/meeting-with-host-person"]
        self.assertEqual(self.post("neetocal", real("create", "kept-2"))[1]["recorded"], 1,
                         "the link's address")

    def test_visitor_ids_off(self):
        self.config["beacon"]["visitor_ids"] = False
        self.rx = type(self.rx)(self.config, self.folder, clock=lambda: self.now)
        self.post("neetocal", real("create"))
        self.assertEqual(self.rows("SELECT vid FROM conversions"), [(None,)])
        self.assertNotIn(FIXTURE_VID, self.spooled())

    def test_the_second_count_agrees(self):
        self.post("neetocal", real("create"))
        self.post("neetocal", real("update-rescheduled"))
        self.post("neetocal", real("cancel"))
        self.post("neetocal", real("create", "waits-1", status="awaiting_approval"))
        self.post("neetocal", real("create", "x-1", method="update"))
        counted = audit_conversions.recount(self.folder / "hooks", "example.com", UTC,
                                            date(2026, 10, 1), date(2026, 11, 30))
        self.assertEqual(counted["2026-11-25"], {("demo", "completed"): 1, ("demo", "started"): 1,
                                                 ("demo", "rescheduled"): 1,
                                                 ("demo", "cancelled"): 1},
                         "a change counts on the day it arrived")
        self.assertEqual(audit_conversions.findings(self.config, self.folder, "example.com", UTC,
                                                    date(2026, 10, 1), date(2026, 11, 30)), {})


if __name__ == "__main__":
    unittest.main()
