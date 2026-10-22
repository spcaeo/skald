"""2.26: Find a person (people/lookup.person, the API's people?q=, MCP find_person)
finds a lead by its reference whatever its length. Before, any 8 to 80 characters of
[A-Za-z0-9_.:-] were read as a visitor ID, so u-1234567 was never found by its ref.

Made-up refs (u-1001, u-1234567), example.com, an RFC 5737 address.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from skald.conversions import store
from skald.people import lookup

SITE = "example.com"
VID = "skv_" + "A" * 22


def rec(ref: str, stage: str = "completed", vid=None, email=None, at="2026-10-20T14:30:00Z",
        tool: str = "lead") -> dict:
    out = {"site": SITE, "action": "signup", "stage": stage, "at": at, "vid": vid,
           "external_ref": ref, "tool": tool}
    if email:
        out["identity"] = {"email": email, "name": "Pat Example"}
    return out


class ByReference(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.config = {"site": {"name": SITE}, "report": {"timezone": "UTC"},
                       "conversions": {"identity": "full"}}
        db = store.connect(store.path_for(self.config, self.folder))
        try:
            store.record_conversion(db, rec("u-1234567"))
            store.record_conversion(db, rec("u-1234567", "won", at="2026-10-21T09:00:00Z"))
            store.record_conversion(db, rec("u-1001", email="pat@example.com"))
            store.record_conversion(db, rec("u-2002", vid=VID))
            # A site's own visitor ID (not skv_): still found as one.
            store.record_conversion(db, rec("u-3003", vid="sess-abcdefgh12"))
        finally:
            db.close()

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def find(self, q):
        return lookup.person(self.config, self.folder, SITE, q)

    def test_kinds(self):
        self.assertEqual(lookup.kind_of("u-1234567"), ("lead", "u-1234567"))
        self.assertEqual(lookup.kind_of("u-1001"), ("lead", "u-1001"))
        self.assertEqual(lookup.kind_of(VID), ("vid", VID))
        self.assertEqual(lookup.kind_of("skv_short"), ("lead", "skv_short"), "not the vid shape")
        self.assertEqual(lookup.kind_of("Pat@Example.com"), ("email", "pat@example.com"))
        self.assertEqual(lookup.kind_of("192.0.2.7"), ("ip", "192.0.2.7"))

    def test_a_long_reference_is_found(self):
        got = self.find("u-1234567")
        self.assertEqual(got["query"]["kind"], "lead")
        self.assertEqual(sorted(r["stage"] for r in got["conversions"]), ["completed", "won"])
        self.assertEqual(got["keys"]["leads"], ["u-1234567"])
        self.assertEqual(got["keys"]["vids"], [], "not a visitor ID: not listed as one")

    def test_a_short_reference_is_found(self):
        got = self.find("u-1001")
        self.assertEqual([r["external_ref"] for r in got["conversions"]], ["u-1001"])

    def test_a_real_visitor_id(self):
        got = self.find(VID)
        self.assertEqual(got["query"]["kind"], "vid")
        self.assertEqual([r["external_ref"] for r in got["conversions"]], ["u-2002"])

    def test_a_sites_own_visitor_id_is_still_found(self):
        got = self.find("sess-abcdefgh12")
        self.assertEqual([r["external_ref"] for r in got["conversions"]], ["u-3003"])
        self.assertIn("sess-abcdefgh12", got["keys"]["vids"])

    def test_an_email(self):
        got = self.find("pat@example.com")
        self.assertEqual([r["external_ref"] for r in got["conversions"]], ["u-1001"])

    def test_nothing_found_is_empty_not_an_error(self):
        self.assertEqual(self.find("u-9999999")["conversions"], [])


if __name__ == "__main__":
    unittest.main()
