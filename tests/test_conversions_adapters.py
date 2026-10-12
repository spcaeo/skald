"""Each tool's signature check and its mapping to conversion records.

The fixed vectors below were made once with Python's hmac module from the
made-up secret in conversions_support (it protects nothing)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, VID  # noqa: E402

from skald.conversions import strip  # noqa: E402
from skald.conversions.adapters import Invalid, adapter, pairs, when  # noqa: E402

T = 1760000000
BODY = b'{"a":1}'
TIMED_HEX = "0e9016e805185d447fb24c972e91174aae86f44ab402365b2d9e7c02c69754f1"
PLAIN_HEX = "73672428e9f171610d5b61c790952f4a04751f5688f629b1ae4cabfce403bb8b"
PLAIN_B64 = "c2ckKOnxcWENW2HHkJUvSgR1H1aI9imxrkyr/OQDu4s="
HUB_URI = "https://www.example.com/traffic-hooks/example.com/hubspot"
HUB_B64 = "KIH7FihnGkATgtx+w9n02I82GZWMeosuhE5oKxONE4Q="


def lower(headers: dict) -> dict:
    return {k.lower(): v for k, v in headers.items()}


class TimedSchemes(unittest.TestCase):
    """Skald's own (lead, json), Calendly and Stripe: t=,v1= over "<t>.<body>"."""

    HEADERS = {"lead": "x-skald-signature", "json": "x-skald-signature",
               "calendly": "calendly-webhook-signature", "stripe": "stripe-signature"}

    def test_known_vector(self):
        for tool, name in self.HEADERS.items():
            mod = adapter(tool)
            h = {name: f"t={T},v1={TIMED_HEX}"}
            self.assertTrue(mod.verify(h, BODY, SECRET, T + 10), tool)
            self.assertEqual(lower(mod.sign(BODY, SECRET, T)), h, tool)

    def test_refused(self):
        for tool, name in self.HEADERS.items():
            mod = adapter(tool)
            good = {name: f"t={T},v1={TIMED_HEX}"}
            self.assertFalse(mod.verify(good, b'{"a":2}', SECRET, T), f"{tool} tampered body")
            self.assertFalse(mod.verify(good, BODY, "another-secret", T), f"{tool} wrong secret")
            self.assertFalse(mod.verify(good, BODY, SECRET, T + 301), f"{tool} replay, late")
            self.assertFalse(mod.verify(good, BODY, SECRET, T - 301), f"{tool} from the future")
            self.assertFalse(mod.verify({name: f"t={T + 1},v1={TIMED_HEX}"}, BODY, SECRET, T),
                             f"{tool} moved timestamp")
            self.assertFalse(mod.verify({}, BODY, SECRET, T), f"{tool} no header")
            self.assertFalse(mod.verify({name: "garbage"}, BODY, SECRET, T), tool)
            self.assertFalse(mod.verify(good, BODY, "", T), f"{tool} no secret")

    def test_stripe_rolled_secret_sends_two(self):
        h = {"stripe-signature": f"t={T},v1={'0' * 64},v1={TIMED_HEX},v0=abc"}
        self.assertTrue(adapter("stripe").verify(h, BODY, SECRET, T))

    def test_pairs(self):
        self.assertEqual(pairs("t=1, v1=a,v1=b"), {"t": ["1"], "v1": ["a", "b"]})


class PlainSchemes(unittest.TestCase):
    def test_calcom_hex_of_body(self):
        mod = adapter("calcom")
        self.assertTrue(mod.verify({"x-cal-signature-256": PLAIN_HEX}, BODY, SECRET, 0))
        self.assertEqual(lower(mod.sign(BODY, SECRET, 0)), {"x-cal-signature-256": PLAIN_HEX})
        self.assertFalse(mod.verify({"x-cal-signature-256": PLAIN_HEX}, b'{"a":2}', SECRET, 0))
        self.assertFalse(mod.verify({"x-cal-signature-256": PLAIN_HEX}, BODY, "nope", 0))
        self.assertFalse(mod.verify({}, BODY, SECRET, 0))

    def test_typeform_base64_of_body(self):
        mod = adapter("typeform")
        good = {"typeform-signature": "sha256=" + PLAIN_B64}
        self.assertTrue(mod.verify(good, BODY, SECRET, 0))
        self.assertEqual(lower(mod.sign(BODY, SECRET, 0)), good)
        self.assertFalse(mod.verify(good, b'{"a":2}', SECRET, 0))
        self.assertFalse(mod.verify(good, BODY, "nope", 0))
        self.assertFalse(mod.verify({"typeform-signature": PLAIN_B64}, BODY, SECRET, 0))

    def test_hubspot_v3(self):
        mod = adapter("hubspot")
        good = {"x-hubspot-signature-v3": HUB_B64,
                "x-hubspot-request-timestamp": str(T * 1000), ":method": "POST", ":uri": HUB_URI}
        self.assertTrue(mod.verify(good, BODY, SECRET, T + 5))
        signed = lower(mod.sign(BODY, SECRET, T, "POST", HUB_URI))
        self.assertEqual(signed["x-hubspot-signature-v3"], HUB_B64)
        self.assertFalse(mod.verify(good, b'{"a":2}', SECRET, T), "tampered")
        self.assertFalse(mod.verify(good, BODY, "nope", T), "wrong secret")
        self.assertFalse(mod.verify(good, BODY, SECRET, T + 301), "replay")
        self.assertFalse(mod.verify({**good, ":uri": HUB_URI + "x"}, BODY, SECRET, T), "uri")
        self.assertFalse(mod.verify({**good, ":method": "PUT"}, BODY, SECRET, T), "method")
        # HubSpot signs with some escapes decoded: %3A in the path is ":".
        escaped = {**good, ":uri": HUB_URI.replace("https://", "https%3A//", 1)}
        self.assertTrue(mod.verify(escaped, BODY, SECRET, T))


class Mapping(unittest.TestCase):
    def test_lead(self):
        got = adapter("lead").to_records({
            "external_ref": "L-1", "action": "Demo", "at": "2026-10-10T14:00:00.5+02:00",
            "vid": VID, "first_touch": {"referrer": "https://www.google.com/", "landing": "/",
                                        "at": 1760000000, "junk": "x"},
            "country": "ca", "ip": "192.0.2.1", "email": "a@example.com", "visits_before": 3})
        self.assertEqual(len(got), 1)
        r = got[0]
        self.assertEqual((r["action"], r["stage"], r["external_ref"], r["at"]),
                         ("demo", "completed", "L-1", "2026-10-10T12:00:00Z"))
        self.assertEqual(r["first_touch"], {"referrer": "https://www.google.com/",
                                            "landing": "/", "at": "2025-10-09T08:53:20Z"})
        self.assertEqual(r["visits_before"], 3)

    def test_lead_refused(self):
        lead = adapter("lead")
        for bad in ({"action": "demo"}, {"external_ref": "x", "action": "Book a demo!"},
                    {"external_ref": "x", "action": "demo", "stage": "booked"},
                    {"external_ref": "x", "action": "demo", "at": "yesterday"}, ["x"]):
            with self.assertRaises(Invalid, msg=bad):
                lead.to_records(bad)

    def test_json_takes_lists(self):
        mod = adapter("json")
        one = {"external_ref": "a", "action": "trial"}
        self.assertEqual(len(mod.to_records(one)), 1)
        self.assertEqual(len(mod.to_records([one, {**one, "external_ref": "b"}])), 2)
        self.assertEqual(len(mod.to_records({"records": [one]})), 1)
        with self.assertRaises(Invalid):
            mod.to_records({"records": [one] * 101})

    def test_calendly(self):
        mod = adapter("calendly")
        uri = "https://api.calendly.com/scheduled_events/E/invitees/I"
        base = {"created_at": "2026-10-10T10:00:00.000000Z",
                "payload": {"uri": uri, "tracking": {"utm_content": VID, "utm_source": "x"}}}
        made = mod.to_records({**base, "event": "invitee.created"})[0]
        self.assertEqual((made["stage"], made["external_ref"], made["vid"], made["at"]),
                         ("completed", uri, VID, "2026-10-10T10:00:00Z"))
        self.assertEqual(made["last_touch"], {"utm_source": "x", "utm_content": VID})
        gone = mod.to_records({**base, "event": "invitee.canceled"})[0]
        self.assertEqual(gone["stage"], "cancelled")
        moved = mod.to_records({**base, "event": "invitee.canceled",
                                "payload": {**base["payload"], "rescheduled": True}})[0]
        self.assertEqual(moved["stage"], "rescheduled")
        no_show = mod.to_records({"event": "invitee_no_show.created", "payload": {
            "uri": "https://api.calendly.com/invitee_no_shows/N", "invitee": uri}})[0]
        self.assertEqual((no_show["stage"], no_show["external_ref"]), ("no_show", uri))
        self.assertEqual(mod.to_records({"event": "routing_form_submission.created",
                                         "payload": {}}), [])
        other = mod.to_records({**base, "event": "invitee.created", "payload": {
            "uri": uri, "tracking": {"utm_content": "spring-sale"}}})[0]
        self.assertIsNone(other["vid"], "not a Skald id")

    def test_calcom(self):
        mod = adapter("calcom")
        body = {"triggerEvent": "BOOKING_RESCHEDULED", "createdAt": "2026-10-10T10:00:00Z",
                "payload": {"uid": "B1", "responses": {"skv": {"value": VID}}}}
        r = mod.to_records(body)[0]
        self.assertEqual((r["action"], r["stage"], r["external_ref"], r["vid"]),
                         ("demo", "rescheduled", "B1", VID))
        self.assertEqual(mod.to_records({**body, "triggerEvent": "MEETING_ENDED"}), [])

    def test_stripe(self):
        mod = adapter("stripe")
        body = {"object": "event", "type": "checkout.session.completed", "created": T,
                "data": {"object": {"id": "cs_1", "payment_status": "paid",
                                    "client_reference_id": VID}}}
        r = mod.to_records(body)[0]
        self.assertEqual((r["action"], r["stage"], r["external_ref"], r["vid"]),
                         ("paid", "paid", "cs_1", VID))
        body["data"]["object"]["payment_status"] = "unpaid"
        self.assertEqual(mod.to_records(body)[0]["stage"], "started")
        self.assertEqual(mod.to_records({**body, "type": "invoice.paid"}), [])
        with self.assertRaises(Invalid):
            mod.to_records({"type": "checkout.session.completed"})

    def test_typeform(self):
        r = adapter("typeform").to_records({"event_type": "form_response", "form_response": {
            "token": "tok", "submitted_at": "2026-10-10T10:00:00Z", "hidden": {"skv": VID}}})[0]
        self.assertEqual((r["action"], r["stage"], r["external_ref"], r["vid"]),
                         ("contact", "completed", "tok", VID))

    def test_hubspot(self):
        mod = adapter("hubspot")
        got = mod.to_records([
            {"subscriptionType": "contact.creation", "objectId": 5, "occurredAt": T * 1000},
            {"subscriptionType": "deal.propertyChange", "objectId": 9,
             "propertyName": "dealstage", "propertyValue": "closedwon"},
            {"subscriptionType": "deal.propertyChange", "objectId": 9,
             "propertyName": "amount", "propertyValue": "5"}])
        self.assertEqual([(r["action"], r["stage"], r["external_ref"]) for r in got],
                         [("contact", "completed", "contact:5"), ("deal", "won", "deal:9")])
        flow = mod.to_records({"objectId": 7, "properties": {"skv": {"value": VID}}})[0]
        self.assertEqual((flow["external_ref"], flow["vid"]), ("workflow:7", VID))

    def test_every_sample_maps(self):
        from skald.conversions import TOOLS
        for tool in TOOLS:
            mod = adapter(tool)
            got = mod.to_records(json.loads(json.dumps(mod.sample("example.com", T))))
            self.assertGreaterEqual(len(got), 1, tool)


class Helpers(unittest.TestCase):
    def test_when(self):
        self.assertEqual(when(1760000000), "2025-10-09T08:53:20Z")
        self.assertEqual(when(1760000000123), "2025-10-09T08:53:20Z")
        self.assertEqual(when("1760000000"), "2025-10-09T08:53:20Z")
        self.assertEqual(when("2026-10-10T10:00:00"), "2026-10-10T10:00:00Z")
        self.assertIsNone(when("soon"))
        self.assertIsNone(when(True))

    def test_strip(self):
        body = {"payload": {"email": "a@example.com", "name": "A", "ip": "192.0.2.1",
                            "uri": "u", "invitee": "https://x/invitees/I",
                            "tracking": {"utm_source": "s"},
                            "questions_and_answers": [{"answer": "secret plans"}]},
                "list": [{"user_agent": "Mozilla", "keep": 1}]}
        # An allow-list: keys no adapter or audit reads ("list", "keep") go too.
        self.assertEqual(strip(body, False, "calendly"),
                         {"payload": {"uri": "u", "invitee": "https://x/invitees/I",
                                      "tracking": {"utm_source": "s"}}})
        full = strip(body, True, "calendly")
        self.assertEqual(full["payload"]["name"], "A")
        self.assertNotIn("questions_and_answers", full["payload"])
        full = strip(body, True)
        self.assertEqual(full["payload"]["email"], "a@example.com")
        self.assertNotIn("ip", full["payload"])
        self.assertNotIn("list", full)


if __name__ == "__main__":
    unittest.main()
