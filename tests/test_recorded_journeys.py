"""Recorded journeys (recorded/, 2.43): the signed receiver, consent, privacy at the
door, duplicates, withdrawal, retention with keep-everything, the queries and the
second count (audit_journeys.py). Addresses are RFC 5737; hosts example.com; the
secret is made up for the tests and protects nothing."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
import uuid as uuidlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conversions_support import FakeHandler  # noqa: E402

from skald import audit_journeys  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.conversions import store as cstore  # noqa: E402
from skald.recorded import contract, queries, receive, store  # noqa: E402

SECRET = "journey-test-secret-not-real"
T = 1791720000          # 2026-10-11 12:00 UTC
NOW = datetime.fromtimestamp(T, tz=timezone.utc)
VISITOR = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SESSION = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def at(seconds: int = 0) -> str:
    return (NOW + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


O = -5000               # QueriesAndAudit's session starts this many seconds before now


def event(name: str = "page_view", seconds: int = 0, **kw) -> dict:
    out = {"schema_version": 1, "event_id": str(uuidlib.uuid4()), "event_name": name,
           "occurred_at": at(seconds), "visitor_id": VISITOR, "session_id": SESSION,
           "path": "/pricing", "consent": {"analytics": "granted", "notice_version": "v1"}}
    out.update(kw)
    return out


class Base(unittest.TestCase):
    keep_ips = "full"
    identity = "full"
    keep_everything = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": "example.com", "hosts": ["example.com"]},
                       "history": {"db": str(self.folder / "history.sqlite")},
                       "privacy": {"keep_ips": self.keep_ips},
                       "conversions": {"identity": self.identity},
                       "retention": {"keep_everything": self.keep_everything}}
        path = secrets_store.path_for(self.config, self.folder)
        secrets_store.put(path, secrets_store.key("example.com", "journey"), SECRET)
        receive._LIMITS.clear()

    def tearDown(self):
        from skald.conversions import hooks
        hooks._RECEIVERS.clear()
        self.tmp.cleanup()

    def post(self, payload, *, path="/traffic-hooks/example.com/journey", secret=SECRET,
             stamp=None, raw=None, headers=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        stamp = str(T if stamp is None else stamp)
        h = {"Content-Type": "application/json", "X-Skald-Timestamp": stamp,
             "X-Skald-Signature": receive.sign(secret, stamp, body), **(headers or {})}
        return receive.answer(FakeHandler(path, body, h), self.config, None, clock=lambda: T)

    def db(self):
        return sqlite3.connect(self.folder / "conversions.sqlite")

    def rows(self, sql: str, args=()) -> list:
        db = self.db()
        try:
            return db.execute(sql, args).fetchall()
        finally:
            db.close()


class Receiver(Base):
    def test_a_signed_event_is_kept_raw_once(self):
        e = event("session_started", touch={"landing_path": "/pricing/",
                                             "referrer": {"host": "Search.Example.com"},
                                             "utm_source": "newsletter"})
        status, body, _ = self.post(e)
        self.assertEqual(status, 201, body)
        self.assertEqual(self.post(e)[0], 200, "the same body again is a duplicate")
        row = self.rows("SELECT event_name, path, raw FROM recorded_events")
        self.assertEqual(len(row), 1)
        raw = json.loads(row[0][2])
        self.assertEqual(raw["touch"]["landing_path"], "/pricing")
        self.assertEqual(raw["touch"]["referrer"], {"host": "search.example.com", "path": "/"})
        changed = dict(e, path="/other")
        self.assertEqual(self.post(changed)[0], 409, "the same ID with another body")

    def test_signature_window_and_secret(self):
        self.assertEqual(self.post(event(), secret="another-secret-not-real")[0], 401)
        self.assertEqual(self.post(event(), stamp=T - 400)[0], 401, "outside the window")
        e = event()
        body = json.dumps(e).encode()
        h = {"X-Skald-Timestamp": str(T), "X-Skald-Signature": "0" * 64}
        got = receive.answer(FakeHandler("/traffic-hooks/example.com/journey", body, h),
                             self.config, None, clock=lambda: T)
        self.assertEqual(got[0], 401)
        self.assertFalse(self.rows("SELECT 1 FROM sqlite_master WHERE name = 'recorded_events'"))

    def test_unknown_site_no_secret_get_and_size(self):
        self.assertEqual(self.post(event(), path="/traffic-hooks/other.example.com/journey")[0], 404)
        got = receive.answer(FakeHandler("/traffic-hooks/example.com/journey", b"", {},
                                         command="GET"), self.config, None, clock=lambda: T)
        self.assertEqual(got[0], 405)
        self.assertEqual(self.post(None, raw=b"x" * 20000)[0], 413)
        path = secrets_store.path_for(self.config, self.folder)
        secrets_store.delete(path, [secrets_store.key("example.com", "journey")])
        self.assertEqual(self.post(event())[0], 404, "no secret: not set up")

    def test_consent_is_required(self):
        for consent in (None, {"analytics": "denied"}, {"analytics": "pending"}, {}):
            e = event()
            if consent is None:
                del e["consent"]
            else:
                e["consent"] = consent
            status, body, _ = self.post(e)
            self.assertEqual(status, 400, consent)
            self.assertEqual(body["field"], "consent")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM recorded_events")[0][0], 0)
        self.assertEqual(self.rows("SELECT n FROM recorded_log WHERE what = 'refused_consent'")[0][0], 4)

    def test_contract_refusals(self):
        bad = [event(name="purchase"), event(path="/pricing?email=x"), event(extra=1),
               event(label="call me on 555 123 4567 0"), event(label="person@example.com"),
               event(email="person@example.com"), event(touch={"landing_path": "/"}),
               event(skald_vid="nope"), event(ip="not-an-ip"), event(visitor_id="ABC"),
               event(occurred_at=at(3600)), event(occurred_at=at(-8 * 86400)),
               event(path="/a/../b"), event(label="203.0.113.7")]
        for e in bad:
            self.assertEqual(self.post(e)[0], 400, e)
        repeated = b'{"schema_version":1,"schema_version":1}'
        self.assertEqual(self.post(None, raw=repeated)[0], 400)

    def test_rate_limit_per_visitor(self):
        self.config["journeys"] = {"visitor_per_minute": 2}
        receive._LIMITS.clear()
        codes = [self.post(event(seconds=i))[0] for i in range(70)]
        self.assertIn(429, codes)


class Privacy(Base):
    def test_full_keeps_address_and_email(self):
        self.post(event("form_sent", ip="203.0.113.57", email="Person@Example.com"))
        self.assertEqual(self.rows("SELECT ip, email FROM recorded_events")[0],
                         ("203.0.113.57", "person@example.com"))


class PrivacyShortAnonymous(Base):
    keep_ips = "short"
    identity = "anonymous"

    def test_short_address_and_no_email(self):
        status, body, _ = self.post(event("form_sent", ip="203.0.113.57", email="p@example.com"))
        self.assertEqual(status, 201)
        self.assertEqual(len(body["notes"]), 2)
        ip, email, raw = self.rows("SELECT ip, email, raw FROM recorded_events")[0]
        self.assertEqual((ip, email), ("203.0.113.0", None))
        self.assertNotIn("email", json.loads(raw), "the raw event never held it")


class PrivacyOff(Base):
    keep_ips = "off"

    def test_no_address(self):
        self.post(event(ip="203.0.113.57"))
        self.assertEqual(self.rows("SELECT ip FROM recorded_events")[0][0], None)


class Withdrawal(Base):
    def withdraw(self, visitor=VISITOR, analytics="withdrawn"):
        return self.post({"schema_version": 1, "visitor_id": visitor, "occurred_at": at(),
                          "consent": {"analytics": analytics}},
                         path="/traffic-hooks/example.com/journey/withdraw")

    def test_withdrawal_deletes_and_refuses_retries(self):
        late = event(seconds=5)
        for e in (event(), event(seconds=2)):
            self.post(e)
        self.assertEqual(self.withdraw(analytics="granted")[0], 400)
        status, body, _ = self.withdraw()
        self.assertEqual((status, body["removed"]), (200, 2))
        self.assertEqual(self.post(late)[0], 202, "a late retry is ignored")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM recorded_events")[0][0], 0)
        stones = self.rows("SELECT digest FROM recorded_tombstones")
        self.assertNotIn(VISITOR, json.dumps(stones), "never the ID itself")


class Forget(Base):
    """`skald forget` (a person's deletion request) takes their recorded sessions whole: by
    the address, the email or the script tag's visitor ID; a dry run counts each event once."""

    def test_by_address_email_and_visitor_id(self):
        other = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        vid = "skv_" + "A" * 22
        self.post(event(ip="203.0.113.57"))
        self.post(event("form_sent", seconds=3, ip="203.0.113.57", email="p@example.com",
                        skald_vid=vid))
        self.post(event(seconds=4, session_id=other, ip="198.51.100.9"))
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            self.assertEqual(store.forget(db, "example.com", email="P@example.com",
                                          vids=[vid], dry_run=True), 2, "each event once")
            self.assertEqual(store.forget(db, "example.org", email="p@example.com"), 0,
                             "another site's only")
            self.assertEqual(store.forget(db, None, ip=("203.0.113.57",)), 2)
            self.assertEqual(store.forget(db, None, ip=("203.0.113.57",)), 0)
            self.assertEqual(store.forget(db, None), 0, "nothing named: nothing goes")
        finally:
            db.close()
        self.assertEqual(self.rows("SELECT session_id FROM recorded_events"), [(other,)])


class Retention(Base):
    def fill(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            for days, sid in ((40, "cccccccc-cccc-4ccc-8ccc-cccccccccccc"), (10, SESSION)):
                e = contract.validate(event(seconds=-days * 86400 + 60, session_id=sid,
                                            ip="203.0.113.7"), NOW - timedelta(days=days))
                store.record(db, "example.com", e, NOW)
        finally:
            db.close()

    def prune(self, spare=None):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            return store.prune(db, NOW.date(), 30, {}, 7, {}, spare)
        finally:
            db.close()

    def test_vid_days_and_people_days(self):
        self.fill()
        got = self.prune()
        self.assertEqual((got["events"], got["cleared"]), (1, 1))
        ip, raw = self.rows("SELECT ip, raw FROM recorded_events")[0]
        self.assertIsNone(ip)
        self.assertNotIn("ip", json.loads(raw))

    def test_keep_everything_loses_nothing(self):
        self.fill()
        got = self.prune(spare=lambda site: True)
        self.assertEqual((got["events"], got["cleared"]), (0, 0))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM recorded_events WHERE ip IS NOT NULL")[0][0], 2)


class QueriesAndAudit(Base):
    def setUp(self):
        super().setUp()
        other = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
        events = [event("session_started", O, touch={"landing_path": "/", "utm_source": "x"},
                        ip="203.0.113.9"),
                  event("page_view", O + 1, path="/"), event("page_view", O + 30, path="/pricing"),
                  event("cta_click", O + 40, label="Book a demo"), event("booking_made", O + 90),
                  event("page_view", O + 4000, session_id=other, path="/blog")]
        for e in events:
            self.assertEqual(self.post(e)[0], 201)
        self.span = (at(O - 3600), at(60))

    def test_sessions_and_figures(self):
        db = self.db()
        try:
            figs = queries.figures(db, "example.com", *self.span)
            got = queries.sessions(db, "example.com", *self.span)
            one = queries.session(db, "example.com", got[-1]["ref"], private=True)
            self.assertEqual(audit_journeys.check(db, "example.com", *self.span, figs), [])
        finally:
            db.close()
        self.assertEqual((figs["sessions"], figs["visitors"], figs["page_views"], figs["actions"]),
                         (2, 1, 3, 2))
        first = got[-1]
        self.assertEqual((first["pages"], first["ended"], first["landing"]), (2, "booking_made", "/"))
        self.assertEqual(first["touch"], {"source": "x"})
        self.assertTrue(got[0]["returning"])
        self.assertNotIn("ip", first, "only owners and admins see the address")
        self.assertEqual(one["ip"], "203.0.113.9")
        self.assertRegex(first["ref"], r"^s[0-9a-f]{12}$")

    def test_audit_withholds_a_changed_column(self):
        db = self.db()
        try:
            db.execute("UPDATE recorded_events SET event_name = 'page_view' WHERE event_name = 'cta_click'")
            db.commit()
            figs = queries.figures(db, "example.com", *self.span)
            problems = audit_journeys.check(db, "example.com", *self.span, figs)
        finally:
            db.close()
        self.assertTrue(any("event_name column" in p for p in problems), problems)

    def test_audit_catches_a_wrong_figure(self):
        db = self.db()
        try:
            figs = queries.figures(db, "example.com", *self.span)
            figs["sessions"] += 1
            self.assertTrue(audit_journeys.check(db, "example.com", *self.span, figs))
        finally:
            db.close()

    def test_linked_to_a_kept_log_visit_by_address_and_time(self):
        db = cstore.connect(self.folder / "conversions.sqlite")
        try:
            db.execute("INSERT INTO visits (site, day, seq, ip, start, end, source, landing, pages, "
                       "trail) VALUES ('example.com', '2026-10-11', 3, '203.0.113.9', ?, ?, "
                       "'Search', '/', 2, '[]')",
                       (at(O - 5), at(O + 100)))
            found = queries.for_visit(db, "example.com", {"start": at(O - 5), "end": at(O + 100),
                                                          "ip": "203.0.113.9"})
            ref = found[0]["ref"]
            back = queries.log_visits(db, "example.com", ref)
            nobody = queries.for_visit(db, "example.com", {"start": at(O - 5), "end": at(O + 100),
                                                           "ip": "198.51.100.1"})
        finally:
            db.close()
        self.assertEqual([s["linked_by"] for s in found], ["address"])
        self.assertEqual([(v["day"], v["seq"]) for v in back], [("2026-10-11", 3)])
        self.assertEqual(nobody, [], "another address: never linked")


class Daily(Base):
    def test_daily_audit_matches(self):
        self.post(event("session_started", 0))
        self.post(event("page_view", 1))

        class Ctx:
            config = self.config
            site = "example.com"
            db_path = str(self.folder / "history.sqlite")
            now = NOW
            said: list = []

            def out(self, line):
                self.said.append(line)
        ctx = Ctx()
        self.assertTrue(audit_journeys.set_up(ctx))
        self.assertEqual(audit_journeys.daily(ctx, date(2026, 10, 11)), [])
        self.assertIn("1 session(s)", ctx.said[0])


if __name__ == "__main__":
    unittest.main()
