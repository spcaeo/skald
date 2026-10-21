"""A site marks its own leads as test (2.19): `test` in the lead body
(adapters/lead.py, store.TEST_SENT) and the signed
POST /traffic-hooks/<site>/leads/test (conversions/marks.py). The rows stay,
are listed, are never counted, and the second count still agrees after a
mark and after an unmark. Hosts are example.com; the secret is made up."""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import sys
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, FakeHandler  # noqa: E402
from test_conversions_hooks import T, Base, lead  # noqa: E402

from skald import audit_conversions, conversions_data  # noqa: E402
from skald.conversions import marks, secrets_store, store  # noqa: E402
from skald.conversions.adapters.lead import TEST_NOTE, record, sign_get  # noqa: E402
from skald.conversions.hooks import Receiver  # noqa: E402
from skald.people import lookup  # noqa: E402

UTC = timezone.utc
PATH = "/traffic-hooks/example.com/leads/test"


def signed(body: bytes, at: float, secret: str = SECRET) -> dict:
    """The header a sender builds by hand: HMAC-SHA256(secret, "<t>.<raw body>")."""
    sig = hmac.new(secret.encode(), f"{int(at)}.".encode() + body, hashlib.sha256).hexdigest()
    return {"X-Skald-Signature": f"t={int(at)},v1={sig}"}


class Mixin:
    def mark(self, payload=None, site: str = "example.com", secret: str | None = SECRET,
             at: float | None = None, raw: bytes | None = None, command: str = "POST",
             headers: dict | None = None):
        body = raw if raw is not None else json.dumps(payload).encode()
        sig = {} if secret is None else signed(body, self.now if at is None else at, secret)
        path = f"/traffic-hooks/{site}/leads/test"
        return self.rx.http(FakeHandler(path, body, {**sig, **(headers or {})}, command))

    def stored(self, ref: str | None = None) -> list:
        where = f" WHERE external_ref = '{ref}'" if ref else ""
        return self.rows(f"SELECT external_ref, tool, stage, test FROM conversions{where} "
                         f"ORDER BY id")

    def keep(self, ref, tool="lead", stage="completed", site="example.com"):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.record_conversion(db, {"site": site, "action": "contact", "stage": stage,
                                         "tool": tool, "external_ref": ref,
                                         "at": "2026-10-11T09:00:00Z"})
        finally:
            db.close()


class BodyTest(Mixin, Base):
    """`test` in the lead body."""

    def test_the_rule(self):
        for raw, want in ((True, (True, False)), (False, (False, False)),
                          (None, (False, False))):
            got = record({"external_ref": "x", "action": "contact", "test": raw})
            self.assertEqual((got["test"], got["test_dropped"]), want, raw)
        got = record({"external_ref": "x", "action": "contact"})
        self.assertEqual((got["test"], got["test_dropped"]), (False, False), "absent")
        for bad in ("true", "yes", 1, 0, [True], {"a": 1}):
            got = record({"external_ref": "x", "action": "contact", "test": bad})
            self.assertEqual((got["test"], got["test_dropped"]), (False, True), bad)

    def test_true_is_kept_listed_and_never_counted(self):
        status, answer = self.post("lead", lead(external_ref="T-1", action="contact",
                                                test=True))
        self.assertEqual((status, answer), (200, {"ok": True, "recorded": 1, "duplicates": 0}))
        self.assertEqual(self.stored(), [("T-1", "lead", "completed", store.TEST_SENT)])
        self.assertIn('"test":true', self.spooled(), "the spool keeps what was sent")
        rows = lookup.conversions_listing(self.config, self.folder, "example.com", "test",
                                          True)["rows"]
        self.assertEqual([r["external_ref"] for r in rows], ["T-1"], "listed under Left out")

    def test_false_and_absent_are_real(self):
        self.post("lead", lead(external_ref="F-1", test=False))
        self.post("lead", lead(external_ref="F-2"))
        self.assertEqual([r[3] for r in self.stored()], [0, 0])
        self.assertIsNone(self.rows("SELECT error FROM deliveries ORDER BY id")[0][0])

    def test_invalid_is_ignored_with_a_note(self):
        status, answer = self.post("lead", lead(external_ref="B-1", test="yes"))
        self.assertEqual((status, answer["recorded"], answer["notes"]), (200, 1, [TEST_NOTE]))
        self.assertEqual(self.stored()[0][3], 0, "kept as a real lead")
        outcome, error = self.rows("SELECT outcome, error FROM deliveries")[0]
        self.assertEqual((outcome, error), ("recorded", TEST_NOTE))
        # Both notes at once, and a dry run (X-Skald-Test) says it too.
        _, answer = self.post("lead", lead(external_ref="B-2", test=1, label="Not OK!"))
        self.assertEqual(len(answer["notes"]), 2)
        _, answer = self.post("lead", lead(external_ref="B-3", test=True),
                              extra={"X-Skald-Test": "1"})
        self.assertEqual(answer["read"][0]["test"], True)
        self.assertEqual(self.stored("B-3"), [], "a dry run keeps nothing")

    def test_each_delivery_says_for_itself(self):
        self.post("lead", lead(external_ref="S-1", stage="started", test=True))
        self.post("lead", lead(external_ref="S-1", stage="completed"))
        self.assertEqual([r[3] for r in self.stored("S-1")], [store.TEST_SENT, 0],
                         "an earlier stage sent as test makes no later one test")

    def test_a_resend_differing_only_in_test_flips_nothing(self):
        self.post("lead", lead(external_ref="R-1"))
        _, answer = self.post("lead", lead(external_ref="R-1", test=True))
        self.assertEqual((answer["recorded"], answer["duplicates"]), (0, 1))
        self.assertEqual(self.stored("R-1")[0][3], 0)
        self.post("lead", lead(external_ref="R-2", test=True))
        self.post("lead", lead(external_ref="R-2", test=False))
        self.assertEqual(self.stored("R-2")[0][3], store.TEST_SENT)

    def test_a_marked_ref_passes_it_on(self):
        self.post("lead", lead(external_ref="M-1", stage="started"))
        self.assertEqual(self.mark({"refs": ["M-1"]})[0], 200)
        self.post("lead", lead(external_ref="M-1", stage="completed"))
        self.post("lead", lead(external_ref="M-1", stage="won", test=False))
        self.assertEqual([r[3] for r in self.stored("M-1")], [store.TEST_MARKED] * 3,
                         "later stages of a marked ref follow it")
        # A row only sent as test becomes marked, and then passes it on.
        self.post("lead", lead(external_ref="M-2", stage="started", test=True))
        _, got = self.mark({"refs": ["M-2"]})
        self.assertEqual((got["marked"], got["already"]), (0, 1))
        self.post("lead", lead(external_ref="M-2", stage="completed"))
        self.assertEqual([r[3] for r in self.stored("M-2")], [store.TEST_MARKED] * 2)
        # Unmarked: the next stage counts again.
        self.mark({"refs": ["M-1"], "test": False})
        self.post("lead", lead(external_ref="M-1", stage="paid"))
        self.assertEqual([r[3] for r in self.stored("M-1")], [0, 0, 0, 0])


class MarkCall(Mixin, Base):
    """POST /traffic-hooks/<site>/leads/test."""

    def setUp(self):
        super().setUp()
        quiet = redirect_stderr(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def test_signature_over_the_raw_body(self):
        self.post("lead", lead(external_ref="L-1"))
        body = b'{"refs":["L-1"],"test":true}'
        status, got = self.mark(raw=body)
        self.assertEqual((status, got), (200, {"ok": True, "test": True, "marked": 1,
                                               "already": 0, "not_found": []}))
        # The lead adapter's own signer makes the same header.
        from skald.conversions.adapters.lead import sign
        self.assertEqual(sign(body, SECRET, self.now), signed(body, self.now))
        self.assertEqual(self.mark(raw=body, secret="another-secret")[0], 401)
        self.assertEqual(self.mark(raw=body, secret=None)[0], 401, "no signature")
        # Signed over one body, another sent.
        sig = signed(b'{"refs":["L-1"],"test":false}', self.now)
        self.assertEqual(self.rx.http(FakeHandler(PATH, body, sig))[0], 401)
        # A GET signature (method and path) is not a POST one.
        sig = sign_get(PATH, SECRET, self.now)
        self.assertEqual(self.rx.http(FakeHandler(PATH, body, sig))[0], 401)
        self.assertEqual(self.stored("L-1")[0][3], store.TEST_MARKED, "only the good one acted")

    def test_the_clock_window(self):
        self.post("lead", lead(external_ref="L-1"))
        body = {"refs": ["L-1"]}
        self.assertEqual(self.mark(body, at=T - 299)[0], 200)
        self.assertEqual(self.mark(body, at=T + 299)[0], 200)
        self.assertEqual(self.mark(body, at=T - 301)[0], 401, "signed over 5 minutes ago")
        self.assertEqual(self.mark(body, at=T + 301)[0], 401, "over 5 minutes ahead")

    def test_404_the_same_for_an_unknown_site_and_no_secret(self):
        unknown = self.mark({"refs": ["L-1"]}, site="other.example.com")
        self.assertEqual(unknown, (404, {"error": "not found"}))
        path = secrets_store.path_for(self.config, self.folder)
        data = json.loads(path.read_text())
        del data["hooks/example.com/lead"]
        path.write_text(json.dumps(data))
        self.assertEqual(self.mark({"refs": ["L-1"]}), unknown)
        self.assertFalse((self.folder / "conversions.sqlite").exists(), "nothing logged")

    def test_methods_and_lengths(self):
        self.assertEqual(self.mark({"refs": ["L-1"]}, command="GET")[0], 405)
        no_length = FakeHandler(PATH, b"{}", {}, "POST")
        del no_length.headers["Content-Length"]
        self.assertEqual(self.rx.http(no_length)[0], 411)
        big = json.dumps({"refs": ["x" * 120] * 600}).encode()
        self.assertEqual(self.mark(raw=big)[0], 413)

    def test_bad_bodies_are_400(self):
        bad = [b"not json", b"[]", b'"refs"', b"{}", b'{"refs": []}', b'{"refs": "L-1"}',
               b'{"refs": [""]}', b'{"refs": ["  "]}', b'{"refs": [null]}',
               b'{"refs": [{"a": 1}]}', b'{"refs": [true]}', b'{"refs": ["L-1"], "test": "yes"}',
               b'{"refs": ["L-1"], "test": 1}', b'{"refs": ["L-1"], "test": null}',
               b'{"refs": ["L-1"], "tset": false}', b'\xff\xfe']
        for raw in bad:
            with self.subTest(raw=raw):
                status, got = self.mark(raw=raw)
                self.assertEqual(status, 400)
                self.assertTrue(got["error"])
        outcomes = {r[0] for r in self.rows("SELECT outcome FROM deliveries")}
        self.assertEqual(outcomes, {"bad_body"})

    def test_at_most_100_refs(self):
        refs = [f"L-{i}" for i in range(101)]
        status, got = self.mark({"refs": refs})
        self.assertEqual((status, got["error"]), (400, "at most 100 refs in one call"))
        status, got = self.mark({"refs": refs[:100]})
        self.assertEqual((status, len(got["not_found"])), (200, 100))
        # A ref given twice counts once; numbers are read as the lead body reads them.
        self.post("lead", lead(external_ref="42"))
        _, got = self.mark({"refs": [42, "42", " 42 "]})
        self.assertEqual((got["marked"], got["not_found"]), (1, []))

    def test_unknown_refs(self):
        self.post("lead", lead(external_ref="L-1"))
        _, got = self.mark({"refs": ["L-1", "NOPE", "L-2"]})
        self.assertEqual(got, {"ok": True, "test": True, "marked": 1, "already": 0,
                               "not_found": ["NOPE", "L-2"]})

    def test_only_this_sites_lead_tool_rows_every_stage(self):
        self.keep("X-1", stage="started")
        self.keep("X-1", stage="completed")
        self.keep("X-1", tool="json")
        self.keep("X-1", tool="calendly")
        self.keep("X-1", tool="leads")
        self.keep("X-1", site="other.example.com")
        _, got = self.mark({"refs": ["X-1"]})
        self.assertEqual((got["marked"], got["already"]), (2, 0))
        marked = self.rows("SELECT site, tool, stage FROM conversions WHERE test <> 0 "
                           "ORDER BY id")
        self.assertEqual(marked, [("example.com", "lead", "started"),
                                  ("example.com", "lead", "completed")])
        # A ref only another tool has is unknown to this call.
        self.keep("J-only", tool="json")
        self.assertEqual(self.mark({"refs": ["J-only"]})[1]["not_found"], ["J-only"])

    def test_mark_then_unmark(self):
        self.post("lead", lead(external_ref="L-1", stage="started"))
        self.post("lead", lead(external_ref="L-1", stage="completed"))
        self.post("lead", lead(external_ref="L-2"))
        _, got = self.mark({"refs": ["L-1", "L-2"], "test": True})
        self.assertEqual((got["test"], got["marked"], got["already"]), (True, 3, 0))
        _, got = self.mark({"refs": ["L-1", "L-2"]})
        self.assertEqual((got["marked"], got["already"]), (0, 3), "test defaults to true")
        _, got = self.mark({"refs": ["L-1"], "test": False})
        self.assertEqual((got["test"], got["marked"], got["already"]), (False, 2, 0))
        _, got = self.mark({"refs": ["L-1"], "test": False})
        self.assertEqual((got["marked"], got["already"]), (0, 2))
        self.assertEqual([(r[0], r[3]) for r in self.stored()],
                         [("L-1", 0), ("L-1", 0), ("L-2", store.TEST_MARKED)])
        # A row only sent as test can be unmarked too.
        self.post("lead", lead(external_ref="L-3", test=True))
        _, got = self.mark({"refs": ["L-3"], "test": False})
        self.assertEqual(got["marked"], 1)
        self.assertEqual(self.stored("L-3")[0][3], 0)

    def test_the_delivery_log(self):
        self.post("lead", lead(external_ref="SECRET-REF-1"))
        self.mark({"refs": ["SECRET-REF-1", "NOPE"]})
        self.mark({"refs": ["SECRET-REF-1"], "test": False})
        rows = self.rows("SELECT tool, outcome, http_status, error, external_ref FROM "
                         "deliveries ORDER BY id")[1:]
        self.assertEqual(rows, [
            ("lead", marks.MARKED, 200, "2 ref(s): 1 row(s) changed, 0 already, 1 not found",
             None),
            ("lead", marks.UNMARKED, 200, "1 ref(s): 1 row(s) changed, 0 already, 0 not found",
             None)])
        self.assertNotIn("SECRET-REF-1", json.dumps(rows), "never a ref in the log")

    def test_the_audit_log_without_accounts(self):
        self.post("lead", lead(external_ref="L-1"))
        self.mark({"refs": ["L-1", "NOPE"]})
        self.mark({"refs": ["L-1"], "test": False})
        lines = (self.folder / "privacy.log").read_text().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("conversions.test site=example.com detail=1 row(s) marked, 0 already, "
                      "1 not found; refs=L-1,NOPE by=hook:lead", lines[0])
        self.assertIn("conversions.untest site=example.com detail=1 row(s) unmarked", lines[1])

    def test_the_audit_log_with_accounts(self):
        from skald.accounts import auditlog, connect
        connect(self.folder / "accounts.sqlite").close()
        self.post("lead", lead(external_ref="L-1"))
        self.mark({"refs": ["L-1"]})
        db = connect(self.folder / "accounts.sqlite")
        try:
            got = [e for e in auditlog.recent(db, None) if e["action"] == "conversions.test"]
        finally:
            db.close()
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["actor"], got[0]["target"]), ("hook:lead", "example.com"))
        self.assertEqual(got[0]["detail"], "1 row(s) marked, 0 already, 0 not found; refs=L-1")
        self.assertFalse((self.folder / "privacy.log").exists())

    def test_rate_limited_per_site(self):
        self.config["hooks"].update({"leads_per_minute": 1, "leads_burst": 2})
        self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)
        codes = [self.mark({"refs": ["L-1"]})[0] for _ in range(4)]
        self.assertEqual(codes, [200, 200, 429, 429])
        # The GET's bucket and the lead POST's are apart.
        target = "/traffic-hooks/example.com/leads"
        self.assertEqual(self.rx.http(FakeHandler(target, b"", sign_get(target, SECRET, T),
                                                  "GET"))[0], 200)
        self.assertEqual(self.post("lead", lead())[0], 200)

    def test_an_unsigned_flood_cannot_spend_the_sites_bucket(self):
        self.config["hooks"].update({"leads_per_minute": 1, "leads_burst": 1})
        self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)
        for _ in range(5):
            self.assertIn(self.mark({"refs": ["L-1"]}, secret="wrong")[0], (401, 429))
        self.assertEqual(self.mark({"refs": ["L-1"]})[0], 200)

    def test_the_get_shows_it_at_once(self):
        self.post("lead", lead(external_ref="L-1"))
        self.post("lead", lead(external_ref="L-2", test=True))
        target = "/traffic-hooks/example.com/leads"

        def get():
            got = self.rx.http(FakeHandler(target, b"", sign_get(target, SECRET, self.now),
                                           "GET"))[1]
            return [(r["external_ref"], r["test"]) for r in got["rows"]]
        self.assertEqual(get(), [("L-1", False), ("L-2", True)])
        self.mark({"refs": ["L-1"]})
        self.assertEqual(get(), [("L-1", True), ("L-2", True)])
        self.mark({"refs": ["L-1", "L-2"], "test": False})
        self.assertEqual(get(), [("L-1", False), ("L-2", False)])

    def test_the_audits_cached_days_are_dropped(self):
        cache = self.folder / audit_conversions.CACHE
        cache.write_text("{}")
        self.mark({"refs": ["NOPE"]})
        self.assertFalse(cache.exists())


class Figures(Mixin, Base):
    """conversions.json and the second count after a mark and an unmark."""

    TODAY = date(2026, 10, 11)
    NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)

    def setUp(self):
        super().setUp()
        quiet = redirect_stderr(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)
        for ref, at in (("A", "2026-10-09T10:00:00Z"), ("B", "2026-10-09T11:00:00Z"),
                        ("C", "2026-10-11T09:00:00Z")):
            self.post("lead", lead(external_ref=ref, action="contact", vid=None, at=at))
        self.post("lead", lead(external_ref="C", action="contact", stage="won", vid=None,
                               at="2026-10-11T10:00:00Z"))
        self.post("lead", lead(external_ref="D", action="contact", vid=None, test=True,
                               at="2026-10-11T09:30:00Z"))                # sent as test
        self.post("lead", lead(external_ref="E", action="contact", vid=None,
                               stage="started", test=True, at="2026-10-11T08:00:00Z"))
        self.post("lead", lead(external_ref="E", action="contact", vid=None,
                               at="2026-10-11T08:05:00Z"))                # E's own: counted

    def blob(self):
        return conversions_data.blob(self.config, self.folder, "example.com", UTC,
                                     self.TODAY, self.NOW)

    def stages(self, got, day):
        return next(x for x in got["days"] if x["day"] == day)["stages"].get("contact", {})

    def audit(self):
        return audit_conversions.findings(self.config, self.folder, "example.com", UTC,
                                          date(2026, 10, 1), self.TODAY, today=self.TODAY,
                                          refresh=False)

    def check(self, old, new):
        got = self.blob()
        self.assertEqual(got["withheld"], {}, "the second count agrees")
        self.assertEqual(self.audit(), {}, "store and spool agree")
        self.assertEqual(self.stages(got, "2026-10-09"), old)
        self.assertEqual(self.stages(got, "2026-10-11"), new)
        return got

    def test_counts_follow_a_mark_and_an_unmark(self):
        got = self.check({"completed": 2}, {"completed": 2, "won": 1})
        self.assertEqual(got["today"]["tests"], 2)
        self.assertEqual(self.mark({"refs": ["A", "C"]})[1]["marked"], 3)
        got = self.check({"completed": 1}, {"completed": 1})
        self.assertEqual(got["today"]["tests"], 4)
        self.assertEqual(self.mark({"refs": ["A", "C", "D"], "test": False})[1]["marked"], 4)
        got = self.check({"completed": 2}, {"completed": 3, "won": 1})
        self.assertEqual(got["today"]["tests"], 1, "E's start, sent as test")

    def test_a_main_road_counting_a_marked_row_is_caught(self):
        self.mark({"refs": ["A"]})
        real = store.day_counts

        def counts_tests_too(db, site, tz, first, last, tools=None):
            db.execute("UPDATE conversions SET test = 0 WHERE external_ref = 'A'")
            try:
                return real(db, site, tz, first, last, tools)
            finally:
                db.execute("UPDATE conversions SET test = 1 WHERE external_ref = 'A'")
        from unittest import mock
        with mock.patch.object(store, "day_counts", counts_tests_too):
            found = self.audit()
        self.assertEqual(list(found), ["2026-10-09"], "the day is withheld")
        self.assertEqual(self.audit(), {})

    def test_a_stage_sent_as_test_leaves_the_others_counted_in_both_roads(self):
        skip = audit_conversions.test_keys(self.folder / "conversions.sqlite", "example.com")
        self.assertEqual(skip, {("lead", "D", "completed"), ("lead", "E", "started")})


if __name__ == "__main__":
    unittest.main()
