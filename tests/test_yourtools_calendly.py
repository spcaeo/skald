"""Calendly history (skald/yourtools/tool_calendly.py), with recorded-shape
answers (tests/fixtures/yourtools/calendly.json) through a fake opener: no network.

  * the key: a personal access token, its scopes said (users:read,
    scheduled_events:read), shown again only by its last four characters
  * the calls: GET only; users/me, then every page of scheduled_events (the user's,
    or the organisation's), 90 days back to 60 ahead; the invitees of past meetings
    and of the newest bookings
  * the figures: bookings, upcoming, past, canceled, no-shows, booked in the last 7
    days and the 7 before, each event type's; NULL when not every page was read
  * kept: only the fields Skald reads; names and emails as the People settings say
    (none when the site keeps no identity; none past the People days)
  * the webhook: "N the webhook also has, M it does not", matched on the meeting's
    address and counted twice; Skald's leads untouched
  * the recheck: a changed count, a planted extra row, all found; the tool withheld
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import yourtools  # noqa: E402
from skald.conversions import store as conv_store  # noqa: E402
from skald.yourtools import api, recount, store, sync, tool_calendly  # noqa: E402
from skald.yourtools.base import BadKey, Unreachable  # noqa: E402
from skald.yourtools.tool_calendly import ADAPTER as CAL  # noqa: E402

SITE = "example.com"
TOKEN = "eyJraWQiOiJ0ZXN0In0.eyJ0ZXN0Ijp0cnVlfQ.c2lnbmF0dXJlLXRlc3Q"
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "yourtools" /
                      "calendly.json").read_text())
EV = "https://api.calendly.com/scheduled_events/"


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeCalendly:
    def __init__(self, fail=None, endless=False):
        self.fail, self.endless, self.asked = fail, endless, []

    def __call__(self, request, timeout=None):
        assert request.get_method() == "GET" and request.data is None
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        url = urllib.parse.urlsplit(request.full_url)
        assert url.netloc == "api.calendly.com"
        q = dict(urllib.parse.parse_qsl(url.query))
        self.asked.append((url.path, q))
        if self.fail:
            raise urllib.error.HTTPError(request.full_url, self.fail, "no", {}, io.BytesIO(
                b'{"title": "Unauthenticated", "message": "The access token is invalid"}'))
        if url.path == "/users/me":
            return Reply(json.dumps(FIXTURE["me"]).encode())
        if url.path == "/scheduled_events":
            if self.endless:
                page = json.loads(json.dumps(FIXTURE["events_page1"]))
                page["pagination"]["next_page_token"] = f"T{len(self.asked)}"
                return Reply(json.dumps(page).encode())
            page = FIXTURE["events_page2" if q.get("page_token") == "TOK2" else "events_page1"]
            return Reply(json.dumps(page).encode())
        event = url.path.split("/")[2]
        assert url.path == f"/scheduled_events/{event}/invitees", url.path
        return Reply(json.dumps({"collection": [FIXTURE["invitees"][event]],
                                 "pagination": {"next_page_token": None}}).encode())


class Base(unittest.TestCase):
    identity = "full"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}, "history": {"db": str(self.folder / "h.sqlite")},
                       "conversions": {"identity": self.identity},
                       "privacy": {"keep_days": 395}}

    def connect(self, **options):
        return sync.connect(self.config, self.folder, SITE, "calendly", options, "cli",
                            key=TOKEN)

    def run_sync(self, opener):
        out = []
        job = sync.Job(self.config, SITE, self.folder, NOW, out.append, out.append,
                       opener=opener, sleep=lambda s: None, send=lambda *a: None)
        return sync.run(job), out

    def stored(self) -> dict:
        db = sqlite3.connect(self.folder / store.FILE)
        try:
            return json.loads(db.execute("SELECT body FROM answers WHERE tool = 'calendly'")
                              .fetchone()[0])
        finally:
            db.close()

    def figures(self) -> dict:
        db = store.reader(self.folder)
        try:
            got = store.latest(db, SITE, "calendly")[0]["figures"]
        finally:
            db.close()
        return {(f["name"], f["dim"]): f["value"] for f in got}


class Key(unittest.TestCase):
    def test_found_and_its_scopes_said(self):
        self.assertIs(yourtools.get("calendly"), CAL)
        self.assertIn("users:read", CAL.permission)
        self.assertIn("scheduled_events:read", CAL.permission)
        self.assertEqual(CAL.check_key(TOKEN)["who"], f"a Calendly token ending ...{TOKEN[-4:]}")

    def test_wrong_shape_refused_without_echo(self):
        for bad in ("two words here and more words", "short"):
            with self.assertRaises(BadKey) as got:
                CAL.check_key(bad)
            self.assertNotIn(bad, str(got.exception))

    def test_scope_option(self):
        self.assertEqual(CAL.clean_options({}), {})
        self.assertEqual(CAL.clean_options({"scope": "organization"}), {"scope": "organization"})
        with self.assertRaises(ValueError):
            CAL.clean_options({"scope": "everyone"})


class Calls(unittest.TestCase):
    def fetch(self, opener=None, **options):
        return CAL.fetch(TOKEN, options, NOW, opener=opener or FakeCalendly(),
                         sleep=lambda s: None)

    def test_the_calls(self):
        fake = FakeCalendly()
        got = self.fetch(fake)
        self.assertEqual(len(got), 1)
        paths = [p for p, _ in fake.asked]
        self.assertEqual(paths[:3], ["/users/me", "/scheduled_events", "/scheduled_events"])
        first = fake.asked[1][1]
        self.assertEqual(first["user"], "https://api.calendly.com/users/USER1")
        self.assertEqual(first["min_start_time"], "2026-07-29T00:00:00.000000Z")
        self.assertEqual(first["max_start_time"], "2026-12-27T00:00:00.000000Z")
        self.assertEqual(fake.asked[2][1]["page_token"], "TOK2")
        invitees = {p.split("/")[2] for p in paths[3:]}
        self.assertEqual(invitees, {"EV1", "EV2", "EV3", "EV4", "EV5"})
        self.assertEqual((got[0].start, got[0].end), ("2026-07-29", "2026-12-26"))

    def test_the_organisation(self):
        fake = FakeCalendly()
        self.fetch(fake, scope="organization")
        self.assertEqual(fake.asked[1][1]["organization"],
                         "https://api.calendly.com/organizations/ORG1")
        self.assertNotIn("user", fake.asked[1][1])

    def test_figures(self):
        got = {(f.name, f.dim): f.value for f in CAL.figures(self.fetch()[0])}
        self.assertEqual(got, {("bookings", None): 5, ("upcoming", None): 2, ("past", None): 2,
                               ("canceled", None): 1, ("no_shows", None): 1,
                               ("booked_7d", None): 3, ("booked_prev_7d", None): 1,
                               ("bookings", "Intro call"): 3, ("bookings", "Demo"): 2})
        head = CAL.headline(CAL.figures(self.fetch()[0]))
        self.assertEqual([f.name for f in head], ["booked_7d", "upcoming", "canceled"])

    def test_only_the_fields_skald_reads_are_kept(self):
        body = self.fetch()[0].body
        text = json.dumps(body)
        for gone in ("questions_and_answers", "text_reminder_number", "A clash, sorry",
                     "owner@example.com", "event_memberships", "tracking"):
            self.assertNotIn(gone, text)
        self.assertEqual(body["events"][2]["cancellation"],
                         {"canceler_type": "invitee", "created_at": "2026-10-23T08:00:00.000000Z"})

    def test_not_every_page_read_is_null(self):
        got = self.fetch(FakeCalendly(endless=True))[0]
        self.assertTrue(got.flags["incomplete"])
        figs = CAL.figures(got)
        self.assertTrue(all(f.value is None for f in figs))
        self.assertFalse([f for f in figs if f.dim is not None])

    def test_refusals(self):
        for code, words in ((401, "revoked"), (403, "read scope"), (429, "rate limit")):
            with self.assertRaises(Unreachable) as got:
                self.fetch(FakeCalendly(fail=code))
            self.assertIn(words, str(got.exception))
            self.assertNotIn(TOKEN, str(got.exception))

    def test_a_meeting_off_the_api_is_not_followed(self):
        with self.assertRaises(Unreachable):
            CAL._invitees("https://evil.example.com/scheduled_events/EV1", TOKEN,
                          FakeCalendly(), lambda s: None)


class People(Base):
    def test_names_kept_when_the_site_keeps_them(self):
        self.connect()
        self.run_sync(FakeCalendly())
        names = {i.get("name") for i in self.stored()["invitees"]}
        self.assertIn("Bea Example", names)

    def test_none_past_the_people_days(self):
        self.config["privacy"]["keep_days"] = 10
        self.connect()
        self.run_sync(FakeCalendly())
        kept = {i["uri"].rsplit("/", 1)[1]: i.get("email") for i in self.stored()["invitees"]}
        self.assertIsNone(kept["IN4"])                 # booked 26 days ago
        self.assertEqual(kept["IN5"], "eve@example.com")


class Anonymous(Base):
    identity = "anonymous"

    def test_no_name_or_email_is_kept(self):
        self.connect()
        self.run_sync(FakeCalendly())
        text = json.dumps(self.stored())
        self.assertNotIn("@example.com", text)
        self.assertNotIn("Example", text.replace("example", ""))
        view = api.view(self.config, self.folder, SITE, admin=True, now=NOW)
        mine = [t for t in view["tools"] if t["id"] == "calendly"][0]
        self.assertTrue(any("No names or emails" in line for line in mine["more"]["lines"]))
        self.assertFalse([p for p in mine["more"]["people"] if p["name"] or p["email"]])


class Webhook(Base):
    def leads(self, *refs):
        path = conv_store.path_for(self.config, self.folder)
        db = conv_store.connect(path)
        with db:
            for ref in refs:
                db.execute("INSERT INTO conversions (site, action, stage, at, external_ref, tool,"
                           " received_at) VALUES (?, 'demo', 'completed', ?, ?, 'calendly', ?)",
                           (SITE, "2026-10-20T10:00:00Z", ref, "2026-10-20T10:00:01Z"))
        db.close()
        return path

    def test_matched_on_the_meeting_and_counted_twice(self):
        path = self.leads(EV + "EV1/invitees/IN1", EV + "EV3/invitees/IN3",
                          "https://api.calendly.com/scheduled_events/OTHER/invitees/X")
        before = sqlite3.connect(path).execute("SELECT COUNT(*) FROM conversions").fetchone()
        self.connect()
        self.run_sync(FakeCalendly())
        view = api.view(self.config, self.folder, SITE, admin=True, now=NOW)
        mine = [t for t in view["tools"] if t["id"] == "calendly"][0]
        line = mine["more"]["lines"][0]
        self.assertIn("Of these 5 bookings, 2 reached Skald by the webhook too", line)
        self.assertIn("3 did not", line)
        uris = [EV + f"EV{i}" for i in range(1, 6)]
        self.assertEqual(recount.webhook_match(path, SITE, uris), 2)
        after = sqlite3.connect(path).execute("SELECT COUNT(*) FROM conversions").fetchone()
        self.assertEqual(before, after)          # never a lead made or changed
        self.assertEqual(mine["more"]["people"][0]["email"], "eve@example.com")

    def test_two_counts_that_differ_withhold_the_line(self):
        self.leads(EV + "EV1/invitees/IN1")
        self.connect()
        self.run_sync(FakeCalendly())
        real = recount.webhook_match
        recount.webhook_match = lambda *a: 99
        self.addCleanup(setattr, recount, "webhook_match", real)
        mine = [t for t in api.view(self.config, self.folder, SITE, admin=True, now=NOW)["tools"]
                if t["id"] == "calendly"][0]
        self.assertIn("withheld", mine["more"]["lines"][0])

    def test_no_webhook_yet(self):
        self.connect()
        self.run_sync(FakeCalendly())
        line = tool_calendly.webhook_line({"config": self.config, "folder": self.folder,
                                           "site": SITE}, [EV + "EV1"])
        self.assertIn("none of these 1 bookings", line)

    def test_members_see_no_people(self):
        self.connect()
        self.run_sync(FakeCalendly())
        mine = api.view(self.config, self.folder, SITE, admin=False, now=NOW)["tools"][0]
        self.assertNotIn("more", mine)
        self.assertNotIn("@example.com", json.dumps(mine))


class Recheck(Base):
    def test_matches_then_a_changed_count_and_an_extra_row(self):
        self.connect()
        code, out = self.run_sync(FakeCalendly())
        self.assertEqual(code, 0, out)
        self.assertEqual(self.figures()[("canceled", None)], 1)
        self.assertTrue(recount.check(self.folder, SITE, "calendly")["calendly"]["ok"])
        db = sqlite3.connect(self.folder / store.FILE)
        db.execute("UPDATE figures SET value = 4 WHERE name = 'canceled'")
        aid = db.execute("SELECT id FROM answers").fetchone()[0]
        db.execute("INSERT INTO figures (answer_id, name, label, dim, value, rank) VALUES "
                   "(?, 'bookings', 'Bookings', 'Workshop', 3, 2)", (aid,))
        db.commit()
        db.close()
        problems = recount.check(self.folder, SITE, "calendly")["calendly"]["problems"]
        self.assertTrue(any("canceled" in p and "says 1" in p for p in problems), problems)
        self.assertTrue(any("Workshop" in p for p in problems), problems)

    def test_a_count_where_the_answer_has_none_is_found(self):
        self.connect()
        self.run_sync(FakeCalendly(endless=True))
        db = sqlite3.connect(self.folder / store.FILE)
        db.execute("UPDATE figures SET value = 0 WHERE name = 'bookings'")
        db.commit()
        db.close()
        problems = recount.check(self.folder, SITE, "calendly")["calendly"]["problems"]
        self.assertTrue(any("bookings" in p and "says None" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
