"""2.18: a lead's optional `label` (adapters/lead.py, conversions.LABEL), kept
with the conversion (schema 7), counted per day in conversions.json and
counted again by the second count; and the signed, read-only
GET /traffic-hooks/<site>/leads (conversions/reconcile.py) a site's server
uses to check that Skald has every lead it sent. Hosts are example.com; the
secret is made up; addresses RFC 5737."""
from __future__ import annotations

import http.client
import io
import json
import sqlite3
import sys
import threading
import time
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import SECRET, VID, FakeHandler  # noqa: E402
from test_conversions_hooks import T, Base, lead  # noqa: E402

from skald import conversions_data  # noqa: E402
from skald.conversions import reconcile, secrets_store, store  # noqa: E402
from skald.conversions.adapters.lead import (LABEL_NOTE, label_of, record,  # noqa: E402
                                                    sign_get, verify_get)
from skald.people import lookup  # noqa: E402

UTC = timezone.utc
PII = ("email", "name", "ip", "user_agent", "vid", "source_type", "first_source", "landing",
       "country", "device", "campaign", "identity_id")


class Label(Base):
    def stored(self, ref="L-1"):
        return self.rows(f"SELECT stage, label FROM conversions WHERE external_ref = '{ref}' "
                         f"ORDER BY id")

    def test_the_rule(self):
        self.assertEqual(label_of("sales"), ("sales", False))
        self.assertEqual(label_of("  Support "), ("support", False), "trimmed, lower-cased")
        self.assertEqual(label_of("partner-ship_2"), ("partner-ship_2", False))
        self.assertEqual(label_of("a" * 40), ("a" * 40, False))
        for absent in (None, "", "   "):
            self.assertEqual(label_of(absent), (None, False), absent)
        for bad in ("a" * 41, "-sales", "sales team", "sales!", "ventes.fr", 7, True, ["x"],
                    {"a": 1}):
            self.assertEqual(label_of(bad), (None, True), bad)
        self.assertEqual(record({"external_ref": "x", "action": "contact",
                                 "label": "Sales"})["label"], "sales")

    def test_valid_is_kept(self):
        status, answer = self.post("lead", lead(action="contact", label="sales"))
        self.assertEqual((status, answer), (200, {"ok": True, "recorded": 1, "duplicates": 0}))
        self.assertEqual(self.stored(), [("completed", "sales")])
        self.assertIn('"label":"sales"', self.spooled(), "the spool keeps it too")
        self.assertIsNone(self.rows("SELECT error FROM deliveries")[0][0])

    def test_absent_is_none_and_says_nothing(self):
        self.assertEqual(self.post("lead", lead(action="contact"))[0], 200)
        self.assertEqual(self.stored(), [("completed", None)])
        self.assertIsNone(self.rows("SELECT error FROM deliveries")[0][0])

    def test_invalid_is_none_never_refused_and_logged(self):
        status, answer = self.post("lead", lead(action="contact", label="Sales Team!"))
        self.assertEqual((status, answer["recorded"], answer["notes"]), (200, 1, [LABEL_NOTE]))
        self.assertEqual(self.stored(), [("completed", None)])
        outcome, error = self.rows("SELECT outcome, error FROM deliveries")[0]
        self.assertEqual((outcome, error), ("recorded", LABEL_NOTE))
        self.assertNotIn("Sales Team", error, "the log never repeats what was sent")
        # A time without an offset and a bad label: both notes, one row.
        self.post("lead", lead(external_ref="L-2", label=5, at="2026-10-11T08:00:00"))
        error = self.rows("SELECT error FROM deliveries ORDER BY id DESC")[0][0]
        self.assertIn("without an offset", error)
        self.assertIn(LABEL_NOTE, error)

    def test_a_test_delivery_says_so(self):
        status, answer = self.post("lead", lead(label="??"), extra={"X-Skald-Test": "1"})
        self.assertEqual(status, 200)
        self.assertIn(LABEL_NOTE, answer["notes"])
        _, answer = self.post("lead", lead(label="support"), extra={"X-Skald-Test": "1"})
        self.assertEqual(answer["read"][0]["label"], "support")

    def test_each_stage_its_own_label(self):
        self.post("lead", lead(action="contact", stage="started", label="sales"))
        self.post("lead", lead(action="contact", stage="completed", label="support"))
        self.post("lead", lead(action="contact", stage="won"))
        self.assertEqual(self.stored(), [("started", "sales"), ("completed", "support"),
                                         ("won", None)])
        # A resend of the same ref and stage changes nothing, its label neither.
        _, answer = self.post("lead", lead(action="contact", stage="completed", label="other"))
        self.assertEqual((answer["recorded"], answer["duplicates"]), (0, 1))
        self.assertEqual(self.stored()[1], ("completed", "support"))

    def test_json_tool_reads_it_too(self):
        body = {"records": [lead(external_ref="J-1", label="sales"),
                            lead(external_ref="J-2", label="NOT OK")]}
        self.assertEqual(self.post("json", body)[1]["recorded"], 2)
        self.assertEqual(self.rows("SELECT external_ref, label FROM conversions ORDER BY id"),
                         [("J-1", "sales"), ("J-2", None)])

    def test_lists_carry_it(self):
        self.post("lead", lead(external_ref="L-7", action="contact", label="sales"))
        got = lookup.person(self.config, self.folder, "example.com", "L-7")
        self.assertEqual([c["label"] for c in got["conversions"]], ["sales"])
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.mark_test(db, "example.com", [db.execute(
                "SELECT id FROM conversions").fetchone()[0]])
        finally:
            db.close()
        rows = lookup.conversions_listing(self.config, self.folder, "example.com", "test",
                                          True)["rows"]
        self.assertEqual([r["label"] for r in rows], ["sales"])


class Migration(unittest.TestCase):
    """A schema 6 file (before labels) opens as 7: a copy kept first, every
    row kept with no label, new rows take one."""

    def test_old_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conversions.sqlite"
            old = store.CONVERSIONS.replace(" label TEXT,", "")
            self.assertNotIn("label", old)
            db = sqlite3.connect(path)
            db.executescript("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
                             + old.format(name="conversions"))
            db.execute("INSERT INTO conversions (site, action, stage, at, external_ref, tool, "
                       "received_at) VALUES ('example.com', 'contact', 'completed', "
                       "'2026-10-10T10:00:00Z', 'OLD-1', 'lead', '2026-10-10T10:00:00Z')")
            db.execute("INSERT INTO meta VALUES ('schema_version', '6')")
            db.commit()
            db.close()
            db = store.connect(path)
            try:
                self.assertEqual(store.schema_version(db), store.SCHEMA_VERSION)
                cols = {r[1] for r in db.execute("PRAGMA table_info(conversions)")}
                self.assertIn("label", cols)
                self.assertIn("conversions_received", {r[1] for r in db.execute(
                    "PRAGMA index_list(conversions)")})
                self.assertEqual([tuple(r) for r in db.execute(
                    "SELECT external_ref, label FROM conversions")], [("OLD-1", None)])
                store.record_conversion(db, {"site": "example.com", "action": "contact",
                                             "stage": "completed", "at": "2026-10-11T10:00:00Z",
                                             "external_ref": "NEW-1", "tool": "lead",
                                             "label": "sales"})
                self.assertEqual(db.execute("SELECT label FROM conversions WHERE external_ref "
                                            "= 'NEW-1'").fetchone()[0], "sales")
            finally:
                db.close()
            self.assertTrue((Path(tmp) / "conversions.sqlite.v6.bak").exists())
            # Opened again: nothing runs twice.
            store.connect(path).close()


class Figures(Base):
    """conversions.json's `labels` and `labels_abandoned`, and the second
    count (audit_conversions_figures) that recounts them by SQL."""

    TODAY = date(2026, 10, 11)
    NOW = datetime(2026, 10, 11, 18, 0, tzinfo=UTC)

    def setUp(self):
        super().setUp()
        self.post("lead", lead(external_ref="A", action="contact", stage="started",
                               at="2026-10-09T10:00:00Z", label="sales"))       # abandoned
        self.post("lead", lead(external_ref="B", action="contact", label="sales",
                               vid=None, at="2026-10-11T09:00:00Z"))
        self.post("lead", lead(external_ref="C", action="contact", label="support",
                               vid=None, at="2026-10-11T10:00:00Z"))
        self.post("lead", lead(external_ref="D", action="contact", vid=None,
                               at="2026-10-11T11:00:00Z"))                      # no label
        self.post("lead", lead(external_ref="E", action="demo", label="sales", vid=None,
                               at="2026-10-11T11:30:00Z"))
        self.post("lead", lead(external_ref="F", action="demo", label="sales", vid=None,
                               at="2026-10-11T11:40:00Z"))
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            fid = db.execute("SELECT id FROM conversions WHERE external_ref = 'F'").fetchone()[0]
            store.mark_test(db, "example.com", [fid])                         # never counted
        finally:
            db.close()

    def blob(self):
        return conversions_data.blob(self.config, self.folder, "example.com", UTC,
                                     self.TODAY, self.NOW)

    def day(self, got, d):
        return next(x for x in got["days"] if x["day"] == d)

    def test_counted_and_recounted(self):
        got = self.blob()
        self.assertEqual(got["withheld"], {})
        today = self.day(got, "2026-10-11")
        self.assertEqual(today["labels"], {"contact": {"sales": {"completed": 1},
                                                       "support": {"completed": 1}},
                                           "demo": {"sales": {"completed": 1}}})
        self.assertEqual(today["stages"]["contact"], {"completed": 3}, "the unlabelled one too")
        before = self.day(got, "2026-10-09")
        self.assertEqual(before["labels"], {"contact": {"sales": {"started": 1}}})
        self.assertEqual(before["labels_abandoned"], {"contact": {"sales": 1}})
        self.assertEqual(before["abandoned"], {"contact": 1})
        labelled = [x for x in got["timeline"] if x["label"]]
        self.assertEqual({x["label"] for x in labelled}, {"sales", "support"})
        self.assertTrue(all("label" in s for x in got["timeline"] for s in x["steps"]))

    def test_a_planted_label_miscount_is_withheld(self):
        real = conversions_data._add_label
        with mock.patch.object(conversions_data, "_add_label",
                               lambda f, a, label, s: real(f, a, "elsewhere" if label == "support"
                                                           else label, s)):
            got = self.blob()
        today = self.day(got, "2026-10-11")
        self.assertEqual(today["state"], "withheld")
        self.assertIn("labels contact", today["why"])
        self.assertEqual(self.day(got, "2026-10-09")["state"], "ok")

    def test_a_planted_abandoned_miscount_is_withheld(self):
        real = conversions_data._add

        def wrong(table, a, b):
            real(table, a, "other" if b == "sales" and table is not None else b)
        with mock.patch.object(conversions_data, "_add", wrong):
            got = self.blob()
        self.assertEqual(self.day(got, "2026-10-09")["state"], "withheld")


class Reconcile(Base):
    """GET /traffic-hooks/<site>/leads."""

    def setUp(self):
        super().setUp()
        quiet = redirect_stderr(io.StringIO())      # the helper's log lines
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def get(self, query: str = "", site: str = "example.com", secret: str = SECRET,
            sign_as: str | None = None, at: float | None = None, headers: dict | None = None,
            command: str = "GET"):
        target = f"/traffic-hooks/{site}/leads" + (f"?{query}" if query else "")
        signed = {} if secret is None else sign_get(sign_as or target, secret,
                                                     self.now if at is None else at)
        return self.rx.http(FakeHandler(target, b"", {**signed, **(headers or {})}, command))

    def keep(self, ref, stage="completed", tool="lead", received=None, at=None, label=None):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.record_conversion(db, {"site": "example.com", "action": "contact",
                                         "stage": stage, "tool": tool, "external_ref": ref,
                                         "at": at or "2026-10-11T09:00:00Z", "label": label,
                                         "vid": VID, "source_type": "Search engine",
                                         "received_at": received, "country": "CA",
                                         "identity": {"email": "person@example.com",
                                                      "name": "A Person"}})
        finally:
            db.close()

    def test_signature_over_method_path_and_query(self):
        target = "/traffic-hooks/example.com/leads?limit=5"
        headers = {"x-skald-signature": sign_get(target, SECRET, T)["X-Skald-Signature"]}
        self.assertTrue(verify_get(headers, target, SECRET, T))
        self.assertFalse(verify_get(headers, target.replace("5", "6"), SECRET, T))
        self.assertFalse(verify_get(headers, target, "another-secret", T))
        self.assertTrue(verify_get(headers, target, SECRET, T + 299))
        self.assertFalse(verify_get(headers, target, SECRET, T + 301), "5-minute window")
        self.assertFalse(verify_get(headers, target, SECRET, T - 301))
        # The same string a sender builds by hand: "<t>.GET <path>?<query>".
        import hashlib
        import hmac
        want = hmac.new(SECRET.encode(), f"{T}.GET {target}".encode(), hashlib.sha256).hexdigest()
        self.assertEqual(headers["x-skald-signature"], f"t={T},v1={want}")

    def test_answers_401_404_405(self):
        self.post("lead", lead())
        self.assertEqual(self.get()[0], 200)
        self.assertEqual(self.get(secret=None)[0], 401, "no signature")
        self.assertEqual(self.get(secret="wrong")[0], 401)
        self.assertEqual(self.get("limit=2", sign_as="/traffic-hooks/example.com/leads?limit=1"
                                  )[0], 401, "a changed query")
        self.assertEqual(self.get("limit=2", sign_as="/traffic-hooks/example.com/leads")[0], 401,
                         "a query added")
        self.assertEqual(self.get(at=T - 400)[0], 401, "signed 400 s ago")
        unknown = self.get(site="other.example.com")
        self.assertEqual(unknown, (404, {"error": "not found"}))
        path = secrets_store.path_for(self.config, self.folder)
        data = json.loads(path.read_text())
        del data["hooks/example.com/lead"]
        path.write_text(json.dumps(data))
        self.assertEqual(self.get(), unknown, "no lead secret: the same answer")
        self.assertEqual(self.get(command="HEAD")[0], 405)
        # Every other hook still takes POST only, and POST /leads is no hook.
        got = self.rx.http(FakeHandler("/traffic-hooks/example.com/calendly", command="GET"))
        self.assertEqual(got[0], 405)
        self.assertEqual(self.rx.http(FakeHandler("/traffic-hooks/example.com/leads", b"{}"))[0],
                         404)
        self.assertEqual(self.rows("SELECT outcome FROM deliveries"), [("recorded",)],
                         "a GET writes no delivery row")

    def test_only_lead_rows_and_nothing_personal(self):
        self.keep("L-1", label="sales")
        self.keep("J-1", tool="json")
        self.keep("C-1", tool="calendly")
        self.keep("B-1", tool="beacon")
        status, got = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(set(got), {"ok", "site", "since", "at_since", "at_until", "limit",
                                    "rows", "next_cursor"})
        self.assertEqual([r["external_ref"] for r in got["rows"]], ["L-1"])
        row = got["rows"][0]
        self.assertEqual(set(row), set(reconcile.ROW_KEYS))
        self.assertEqual((row["action"], row["stage"], row["label"], row["test"]),
                         ("contact", "completed", "sales", False))
        dump = json.dumps(got)
        for word in ("person@example.com", "A Person", VID, "Search engine", '"CA"'):
            self.assertNotIn(word, dump)
        for key in PII:
            self.assertNotIn(key, row)

    def test_test_rows_are_in_it_flagged(self):
        self.keep("L-1")
        self.keep("L-2")
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            rid = db.execute("SELECT id FROM conversions WHERE external_ref = 'L-2'").fetchone()[0]
            store.mark_test(db, "example.com", [rid])
        finally:
            db.close()
        got = self.get()[1]
        self.assertEqual([(r["external_ref"], r["test"]) for r in got["rows"]],
                         [("L-1", False), ("L-2", True)])

    def test_paging_while_new_rows_arrive(self):
        for i in range(5):
            self.keep(f"L-{i}", received=f"2026-10-11T10:00:0{i}Z")
        self.keep("L-same", received="2026-10-11T10:00:04Z")       # the same second: by id
        seen, cursor, pages = [], None, 0
        while True:
            query = urlencode({"limit": 2, **({"cursor": cursor} if cursor else {})})
            status, got = self.get(query)
            self.assertEqual(status, 200)
            seen += [r["external_ref"] for r in got["rows"]]
            pages += 1
            if pages == 1:                 # new leads arrive between two pages
                self.keep("L-new1", received="2026-10-11T11:00:00Z")
                self.keep("L-new2", received="2026-10-11T11:00:00Z")
            cursor = got["next_cursor"]
            if cursor is None:
                break
            self.assertLess(pages, 10)
        self.assertEqual(seen, ["L-0", "L-1", "L-2", "L-3", "L-4", "L-same", "L-new1", "L-new2"])
        self.assertEqual(len(seen), len(set(seen)), "never twice")
        self.assertEqual(self.get("limit=500")[1]["next_cursor"], None)

    def test_since_is_when_skald_got_it(self):
        # A lead backfilled today about a day long ago: its `at` is old, its received_at new.
        self.keep("OLD-BUT-NEW", at="2026-01-05T09:00:00Z", received="2026-10-11T11:00:00Z")
        self.keep("EARLIER", at="2026-10-10T09:00:00Z", received="2026-10-10T09:00:05Z")
        got = self.get(urlencode({"since": "2026-10-11T00:00:00Z"}))[1]
        self.assertEqual([r["external_ref"] for r in got["rows"]], ["OLD-BUT-NEW"])
        self.assertEqual(got["since"], "2026-10-11T00:00:00Z")
        got = self.get(urlencode({"since": "2026-10-10T20:00:00-05:00"}))[1]   # an offset
        self.assertEqual([r["external_ref"] for r in got["rows"]], ["OLD-BUT-NEW"])
        got = self.get(urlencode({"at_since": "2026-10-01T00:00:00Z"}))[1]
        self.assertEqual([r["external_ref"] for r in got["rows"]], ["EARLIER"])
        got = self.get(urlencode({"at_until": "2026-10-01T00:00:00Z"}))[1]
        self.assertEqual([r["external_ref"] for r in got["rows"]], ["OLD-BUT-NEW"])
        got = self.get(urlencode({"since": int(T) - 3600}))[1]                  # Unix seconds
        self.assertEqual([r["external_ref"] for r in got["rows"]], ["OLD-BUT-NEW"])

    def test_bad_parameters_are_400(self):
        for query in ("limit=0", "limit=501", "limit=x", "since=yesterday", "cursor=bm9wZQ",
                      "cursor=%%%", "page=2", "limit=1&limit=2", "since"):
            with self.subTest(query=query):
                status, got = self.get(query)
                self.assertEqual(status, 400)
                self.assertTrue(got["error"])
        self.assertEqual(self.get("limit=500")[0], 200)
        self.assertEqual(self.get()[1]["limit"], 200, "the default")

    def test_rate_limited_per_site(self):
        self.config["hooks"].update({"leads_per_minute": 1, "leads_burst": 2})
        from skald.conversions.hooks import Receiver
        self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)
        codes = [self.get()[0] for _ in range(4)]
        self.assertEqual(codes, [200, 200, 429, 429])
        # The POST hook's own bucket is apart.
        self.assertEqual(self.post("lead", lead())[0], 200)

    def test_unsigned_flood_cannot_spend_the_sites_bucket(self):
        self.config["hooks"].update({"leads_per_minute": 1, "leads_burst": 1})
        from skald.conversions.hooks import Receiver
        self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)
        for _ in range(5):
            self.get(secret="wrong")
        self.assertEqual(self.get()[0], 200)

    def test_the_log_says_site_outcome_and_count_only(self):
        self.keep("L-1", label="sales")
        out = io.StringIO()
        with redirect_stderr(out):
            self.get(urlencode({"since": "2026-10-01T00:00:00Z", "limit": 7}))
            self.get(secret="wrong")
        said = out.getvalue()
        self.assertIn("hooks: GET leads example.com ok rows=1 params=limit,since", said)
        self.assertIn("example.com bad_signature", said)
        for word in (SECRET, "2026-10-01", "=7", "L-1", "sales"):
            self.assertNotIn(word, said)

    def test_resend_what_is_missing(self):
        """The daily reconcile the guide suggests: send every ref the answer
        lacks again; a ref Skald has is a duplicate and changes nothing."""
        self.post("lead", lead(external_ref="R-1"))
        sent = ("R-1", "R-2")                  # the site's own list: R-2 never arrived
        refs = {r["external_ref"] for r in self.get()[1]["rows"]}
        self.assertEqual(set(sent) - refs, {"R-2"})
        answers = [self.post("lead", lead(external_ref=ref))[1] for ref in sent]
        self.assertEqual([(a["recorded"], a["duplicates"]) for a in answers], [(0, 1), (1, 0)],
                         "resending one Skald has is harmless")
        got = self.get()[1]["rows"]
        self.assertEqual(sorted(r["external_ref"] for r in got), ["R-1", "R-2"])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions")[0][0], 2)

    def test_through_the_beacon_helper(self):
        from skald.beacon_server import Limiter, Sink, make_handler
        config_path = self.folder / "config.yml"
        config_path.write_text("")
        sink = Sink(self.config, self.folder / "beacon")
        sink.config_path = config_path
        server = ThreadingHTTPServer(("127.0.0.1", 0),
                                     make_handler(sink, Limiter(), {"https://www.example.com"}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            self.keep("L-1")
            target = "/traffic-hooks/example.com/leads?limit=10"
            conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            conn.request("GET", target, headers=sign_get(target, SECRET, time.time()))
            answer = conn.getresponse()
            self.assertEqual(answer.status, 200)
            self.assertEqual(answer.getheader("Cache-Control"), "no-store")
            self.assertEqual([r["external_ref"] for r in json.loads(answer.read())["rows"]],
                             ["L-1"])
            conn.request("GET", "/traffic-hooks/example.com/lead")
            answer = conn.getresponse()
            answer.read()
            self.assertEqual(answer.status, 405, "any other GET as before")
            conn.request("GET", target)
            answer = conn.getresponse()
            answer.read()
            self.assertEqual(answer.status, 401)
        finally:
            server.shutdown()
            server.server_close()


class Page(unittest.TestCase):
    """The tag and Pipeline's Label option, run in node (tests/js/pipeline-label.mjs)."""

    def test_label_tag_and_option(self):
        import shutil
        import subprocess
        if not shutil.which("node"):
            self.skipTest("node is not installed")
        js = Path(__file__).resolve().parent / "js" / "pipeline-label.mjs"
        done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("pipeline-label: all passed", done.stdout)


class Cursor(unittest.TestCase):
    def test_round_trip_and_refusals(self):
        c = reconcile.cursor_for("2026-10-11T10:00:00Z", 42)
        self.assertNotIn("=", c)
        self.assertEqual(reconcile.read_cursor(c), ("2026-10-11T10:00:00Z", 42))
        for bad in ("", "x", reconcile.cursor_for("not a time", 1)):
            with self.assertRaises(reconcile.BadQuery):
                reconcile.read_cursor(bad)
        with self.assertRaises(reconcile.BadQuery):
            reconcile.read_query("/traffic-hooks/example.com/leads?x=1")
        self.assertEqual(reconcile.read_query("/traffic-hooks/example.com/leads")["limit"], 200)


if __name__ == "__main__":
    unittest.main()
