"""Mark as test / Not a test from a lead's drawer (2.25, people/marktest.py, POST
<page>/people/mark-test): owners and admins only, with the page's CSRF value (basic mode:
same-origin); every stage of that (tool, reference) marked as the CLI's `conversions
mark-test` marks it (TEST_MARKED, so a later stage follows); one audit row with the user
and the row ids, never the reference; the second count still agrees. And the lead list's
`ref` and its steps. Hosts are example.com; the CSRF value is made up."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_lead_test_marks as hook  # noqa: E402

from skald.conversions import store  # noqa: E402
from skald.people import api, leadlist, marktest  # noqa: E402

SITE = "example.com"
PATH = f"/traffic/{SITE}/people/mark-test"
CSRF = "c" * 32
REF = "u-119797"


def same_origin(headers, allowed) -> bool:          # refresh_server.same_origin's rule
    site = headers.get("Sec-Fetch-Site")
    return site == "same-origin" if site is not None else headers.get("Origin") in allowed


class Handler:
    def __init__(self, path, role, body, headers=None, who=None):
        self.path, self.role, self.who, self.sent = path, role, who, None
        self.headers = {"Sec-Fetch-Site": "same-origin"} if headers is None else headers
        self.raw = json.dumps(body).encode() if not isinstance(body, bytes) else body

    def _user(self):
        return "pat", self.role

    def _body(self):
        try:
            return json.loads(self.raw.decode() or "{}")
        except ValueError:
            self._json(400, {"ok": False, "error": "a JSON object, please"})
            return None

    def _json(self, code, body):
        self.sent = (code, body)


class MarkFromDrawer(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.history = self.root / "history.sqlite"
        self.config = {"site": {"name": SITE}, "report": {"timezone": "UTC"},
                       "access": {"mode": "basic"}}
        db = store.connect(self.root / store.FILE)
        try:
            for stage, at in (("started", "2026-10-11T08:58:00Z"), ("completed", "2026-10-11T09:00:00Z"),
                              ("won", "2026-10-12T10:00:00Z")):
                store.record_conversion(db, {"site": SITE, "action": "signup", "stage": stage,
                                             "tool": "lead", "external_ref": REF, "at": at})
            store.record_conversion(db, {"site": SITE, "action": "signup", "stage": "completed",
                                         "tool": "lead", "external_ref": "u-2", "at": "2026-10-11T11:00:00Z"})
            self.id = db.execute("SELECT id FROM conversions WHERE external_ref = ? AND stage = "
                                 "'completed'", (REF,)).fetchone()[0]
        finally:
            db.close()
        self.redraws = 0

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def refresh(self):
        self.redraws += 1
        return "ran"

    def post(self, body, role="admin", headers=None, who=None, path=PATH):
        h = Handler(path, role, body, headers, who)
        self.assertTrue(marktest.is_mark(path))
        marktest.handle(h, self.config, self.root, self.history, None, sessions_mode=who is not None,
                        origins=set(), same_origin=same_origin, refresh=self.refresh)
        return h.sent

    def marks_of(self, ref=REF):
        db = sqlite3.connect(self.root / store.FILE)
        try:
            return [r[0] for r in db.execute("SELECT test FROM conversions WHERE external_ref = ? "
                                             "ORDER BY id", (ref,))]
        finally:
            db.close()

    def log(self) -> str:
        path = self.root / "privacy.log"
        return path.read_text() if path.exists() else ""

    # ---------------------------------------------------------------- the mark
    def test_an_admin_marks_every_stage_and_unmarks_them(self):
        code, body = self.post({"id": self.id, "test": True})
        self.assertEqual(code, 200, body)
        self.assertEqual((body["changed"], body["tool"], body["ref"], body["test"]), (3, "lead", REF, True))
        self.assertEqual(self.marks_of(), [store.TEST_MARKED] * 3, "every stage of the reference")
        self.assertEqual(self.marks_of("u-2"), [0], "another reference is untouched")
        self.assertTrue(body["redrawn"])
        self.assertEqual(self.redraws, 1, "the page's files are drawn again")
        code, body = self.post({"id": self.id, "test": False})
        self.assertEqual((code, body["changed"]), (200, 3))
        self.assertEqual(self.marks_of(), [0, 0, 0])

    def test_a_later_stage_of_a_marked_reference_is_test_too(self):
        self.post({"id": self.id, "test": True})
        db = store.connect(self.root / store.FILE)
        try:
            store.record_conversion(db, {"site": SITE, "action": "signup", "stage": "lost", "tool": "lead",
                                         "external_ref": REF, "at": "2026-10-13T10:00:00Z"})
        finally:
            db.close()
        self.assertEqual(self.marks_of(), [store.TEST_MARKED] * 4, "the same mark as the CLI's")

    def test_the_audit_row_names_the_user_and_ids_never_the_reference(self):
        self.post({"id": self.id, "test": True})
        log = self.log()
        self.assertIn("conversions.test site=example.com by=pat", log)
        self.assertIn("3 row(s) marked test from the dashboard, tool=lead ids=", log)
        self.assertNotIn(REF, log, "never the reference")
        self.post({"id": self.id, "test": False})
        self.assertIn("conversions.untest site=example.com by=pat", self.log())

    def test_a_mark_again_changes_nothing_and_draws_nothing(self):
        self.post({"id": self.id, "test": True})
        code, body = self.post({"id": self.id, "test": True})
        self.assertEqual((code, body["changed"], body["redrawn"]), (200, 0, False))
        self.assertEqual(self.redraws, 1)

    # ---------------------------------------------------------------- who may
    def test_viewers_and_editors_are_refused(self):
        for role in ("viewer", "editor", ""):
            code, body = self.post({"id": self.id, "test": True}, role=role)
            self.assertEqual(code, 403, role)
        self.assertEqual(self.marks_of(), [0, 0, 0], "nothing changed")
        self.assertEqual(self.log(), "")
        code, _ = self.post({"id": self.id, "test": True}, role="owner")
        self.assertEqual(code, 200, "an owner counts as an admin")

    def test_the_page_itself_only_csrf_and_same_origin(self):
        code, _ = self.post({"id": self.id}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(code, 403, "basic mode: same-origin only")
        code, _ = self.post({"id": self.id}, headers={})
        self.assertEqual(code, 403, "no Sec-Fetch-Site and no known Origin")
        who = {"role": "admin", "csrf": CSRF, "org": None, "user_id": 1, "email": "pat@example.com",
               "install_admin": False}
        code, body = self.post({"id": self.id}, headers={"Sec-Fetch-Site": "same-origin"}, who=who)
        self.assertEqual(code, 403, "sessions: no CSRF value")
        self.assertIn("out of date", body["error"])
        code, _ = self.post({"id": self.id}, who={**who, "role": "viewer"},
                            headers={"Sec-Fetch-Site": "same-origin", "X-Skald-CSRF": CSRF})
        self.assertEqual(code, 403, "sessions: a viewer, even with the value")
        self.assertEqual(self.marks_of(), [0, 0, 0])
        code, body = self.post({"id": self.id}, who=who,
                               headers={"Sec-Fetch-Site": "same-origin", "X-Skald-CSRF": CSRF})
        self.assertEqual((code, body["changed"]), (200, 3))

    def test_bad_bodies_and_unknown_rows(self):
        for bad in ({}, {"id": "12"}, {"id": True}, {"id": self.id, "test": "yes"},
                    {"id": self.id, "ref": REF}, {"id": -1}):
            code, _ = self.post(bad)
            self.assertEqual(code, 400, bad)
        code, _ = self.post({"id": 99999})
        self.assertEqual(code, 404)
        self.assertFalse(marktest.is_mark(f"/traffic/{SITE}/people/mark-test/../x"))
        self.assertFalse(api.is_people(PATH), "a GET to it is not a people listing")

    # ---------------------------------------------------------------- the lead list
    def test_a_lead_that_paid_later_says_paid_as_its_stage_now(self):
        db = store.connect(self.root / store.FILE)
        try:
            store.record_conversion(db, {"site": SITE, "action": "signup", "stage": "paid",
                                         "tool": "lead", "external_ref": "u-2", "at": "2026-10-11T11:20:00Z"})
        finally:
            db.close()
        got = leadlist.rows(self.config, self.root, SITE, date(2026, 10, 11), date(2026, 10, 12), False)
        row = next(r for r in got["rows"] if r["ref"] == "u-2")
        self.assertEqual((row["stage"], row["now"]), ("completed", "paid"))
        self.assertEqual(len([r for r in got["rows"] if r["ref"] == "u-2"]), 1, "still one lead")

    def test_the_lead_list_carries_the_reference_and_a_test_leads_steps(self):
        got = leadlist.rows(self.config, self.root, SITE, date(2026, 10, 11), date(2026, 10, 12), False)
        row = next(r for r in got["rows"] if r["ref"] == REF)
        self.assertEqual(row["now"], "won")
        self.assertEqual([s["stage"] for s in row["steps"]], ["started", "completed", "won"])
        self.post({"id": self.id, "test": True})
        got = leadlist.rows(self.config, self.root, SITE, date(2026, 10, 11), date(2026, 10, 12), False)
        row = next(r for r in got["rows"] if r["ref"] == REF)
        self.assertEqual(row["left_out"], "test", "listed under Show left out")
        self.assertEqual([s["stage"] for s in row["steps"]], ["started", "completed", "won"],
                         "a test lead's drawer still lists its steps")
        self.assertTrue(all(s["test"] for s in row["steps"]))
        counted = [r for r in got["rows"] if not r["left_out"]]
        self.assertEqual([r["ref"] for r in counted], ["u-2"], "it leaves the counted rows")


class ScriptTagReference(MarkFromDrawer):
    """The page script's reference is made from the visitor ID (from_beacon.py): only owners
    and admins see it; every other member, and conversions.json, get null."""

    VID = "skv_" + "A" * 22

    def setUp(self):
        super().setUp()
        db = store.connect(self.root / store.FILE)
        try:
            store.record_conversion(db, {"site": SITE, "action": "contact", "stage": "completed", "tool": "beacon",
                                         "external_ref": f"{self.VID}:contact:completed:2026-10-11T12:00:00Z",
                                         "vid": self.VID, "at": "2026-10-11T12:00:00Z"})
        finally:
            db.close()

    def test_only_owners_and_admins_get_it(self):
        from skald.conversions_leads import today_block
        from skald.people import lookup
        from zoneinfo import ZoneInfo
        span = (date(2026, 10, 11), date(2026, 10, 12))
        member = leadlist.rows(self.config, self.root, SITE, *span, False)
        admin = leadlist.rows(self.config, self.root, SITE, *span, False, private=True)
        pick = lambda got: next(r for r in got["rows"] if r["tool"] == "beacon")  # noqa: E731
        self.assertIsNone(pick(member)["ref"])
        self.assertTrue(pick(admin)["ref"].startswith(self.VID))
        self.assertNotIn(self.VID, json.dumps(member))
        self.assertIn(REF, [r["ref"] for r in member["rows"] if r["tool"] == "lead"],
                         "another tool's reference: every member")
        db = store.connect(self.root / store.FILE)
        try:
            block = today_block(db, SITE, ZoneInfo("UTC"), date(2026, 10, 11), set())
        finally:
            db.close()
        self.assertNotIn(self.VID, json.dumps(block), "conversions.json never holds it")
        self.post({"id": next(r["id"] for r in admin["rows"] if r["tool"] == "beacon"), "test": True})
        listed = lookup.conversions_listing(self.config, self.root, SITE, "test", False)
        self.assertNotIn(self.VID, json.dumps(listed), "the Conversions lists for a member")
        listed = lookup.conversions_listing(self.config, self.root, SITE, "test", True)
        self.assertIn(self.VID, json.dumps(listed))

    for _name in [n for n in dir(MarkFromDrawer) if n.startswith("test_")]:
        locals()[_name] = None
    del _name


class FiguresAfterADrawerMark(hook.Figures):
    """conversions.json and the second count after a mark and an unmark from a drawer:
    the same rows and checks as the signed call's (test_lead_test_marks.Figures)."""

    # The signed call's own tests run in their own module.
    test_counts_follow_a_mark_and_an_unmark = None
    test_a_main_road_counting_a_marked_row_is_caught = None
    test_a_stage_sent_as_test_leaves_the_others_counted_in_both_roads = None

    def drawer(self, ref, on):
        db = sqlite3.connect(self.folder / store.FILE)
        try:
            rid = db.execute("SELECT MIN(id) FROM conversions WHERE external_ref = ?", (ref,)).fetchone()[0]
        finally:
            db.close()
        h = Handler(PATH, "admin", {"id": rid, "test": on})
        marktest.handle(h, self.config, self.folder, self.folder / "history.sqlite", None, False,
                        set(), same_origin)
        self.assertEqual(h.sent[0], 200, h.sent)
        return h.sent[1]

    def test_counts_and_the_second_count_follow_a_drawer_mark(self):
        self.check({"completed": 2}, {"completed": 2, "won": 1})
        self.assertEqual(self.drawer("A", True)["changed"], 1)
        self.assertEqual(self.drawer("C", True)["changed"], 2, "both of C's stages")
        got = self.check({"completed": 1}, {"completed": 1})
        self.assertEqual(got["today"]["tests"], 4)
        self.drawer("A", False)
        self.drawer("C", False)
        self.check({"completed": 2}, {"completed": 2, "won": 1})


if __name__ == "__main__":
    unittest.main()
