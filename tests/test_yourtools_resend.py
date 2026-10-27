"""Resend (skald/yourtools/tool_resend.py), with recorded-shape answers
(tests/fixtures/yourtools/resend.json) through a fake opener: no network.

  * the key: re_..., shown again only by its last four characters; what the key can
    do said plainly (full access: a sending-only key cannot read)
  * the calls: GET only, every page of contacts (`after`, `has_more`), the segments
    and each one's contacts, the newest emails; a pause between calls (two a second)
  * the figures: contacts, subscribed, unsubscribed; each segment's contacts; the
    emails' last events; NULL when not every page was read
  * kept: ids, times and states; addresses only for the newest, as the People
    settings say; never a name or a subject
  * a sending-only key refused in plain words; the key never in a message
  * the recheck: matches; a changed state count and a planted segment found
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
from skald.yourtools import api, recount, store, sync, tool_resend  # noqa: E402
from skald.yourtools.base import BadKey, Unreachable  # noqa: E402
from skald.yourtools.tool_resend import ADAPTER as RESEND  # noqa: E402

SITE = "example.com"
KEY = "re_TestKey_AbCdEfGh1234"
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "yourtools" /
                      "resend.json").read_text())


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeResend:
    def __init__(self, fail=None, detail="", endless=False):
        self.fail, self.detail, self.endless, self.asked = fail, detail, endless, []

    def __call__(self, request, timeout=None):
        assert request.get_method() == "GET" and request.data is None
        assert request.get_header("Authorization") == f"Bearer {KEY}"
        url = urllib.parse.urlsplit(request.full_url)
        assert url.netloc == "api.resend.com"
        q = dict(urllib.parse.parse_qsl(url.query))
        self.asked.append((url.path, q))
        if self.fail:
            raise urllib.error.HTTPError(request.full_url, self.fail, "no", {}, io.BytesIO(
                json.dumps({"statusCode": self.fail, "name": "restricted_api_key",
                            "message": self.detail}).encode()))
        if url.path == "/contacts" and "segment_id" in q:
            got = FIXTURE[f"segment_{q['segment_id']}"]
        elif url.path == "/contacts":
            if self.endless:
                got = json.loads(json.dumps(FIXTURE["contacts_page1"]))
                got["data"][-1]["id"] = f"c-{len(self.asked)}"
            else:
                got = FIXTURE["contacts_page2" if q.get("after") == "c2" else "contacts_page1"]
        elif url.path == "/segments":
            got = FIXTURE["segments"]
        else:
            assert url.path == "/emails" and q["limit"] == "100"
            got = FIXTURE["emails"]
        return Reply(json.dumps(got).encode())


class Base(unittest.TestCase):
    identity = "full"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}, "history": {"db": str(self.folder / "h.sqlite")},
                       "conversions": {"identity": self.identity},
                       "privacy": {"keep_days": 395}}

    def run_sync(self, opener):
        sync.connect(self.config, self.folder, SITE, "resend", {}, "cli", key=KEY)
        out = []
        job = sync.Job(self.config, SITE, self.folder, NOW, out.append, out.append,
                       opener=opener, sleep=lambda s: None, send=lambda *a: None)
        return sync.run(job), out

    def stored(self) -> str:
        db = sqlite3.connect(self.folder / store.FILE)
        try:
            return "\n".join(r[0] for r in db.execute("SELECT body FROM answers"))
        finally:
            db.close()


def fetch(opener=None, waits=None):
    return RESEND.fetch(KEY, {}, NOW, opener=opener or FakeResend(),
                        sleep=(waits.append if waits is not None else lambda s: None))


class Key(unittest.TestCase):
    def test_key_and_what_it_can_do(self):
        self.assertIs(yourtools.get("resend"), RESEND)
        self.assertEqual(RESEND.check_key(KEY)["who"], "a Resend key ending ...1234")
        self.assertIn("sending-only key cannot read", RESEND.permission)
        with self.assertRaises(BadKey) as got:
            RESEND.check_key("sk_live_notresend")
        self.assertNotIn("sk_live_notresend", str(got.exception))


class Calls(unittest.TestCase):
    def test_the_calls_and_the_pause(self):
        fake, waits = FakeResend(), []
        got = fetch(fake, waits)
        self.assertEqual([a.report for a in got], ["totals", "segments", "emails"])
        self.assertEqual([p for p, _ in fake.asked],
                         ["/contacts", "/contacts", "/segments", "/contacts", "/contacts",
                          "/emails"])
        self.assertEqual(fake.asked[1][1]["after"], "c2")
        self.assertEqual(len([w for w in waits if w == tool_resend.GAP]), len(fake.asked))

    def test_figures(self):
        got = {a.report: a for a in fetch()}
        self.assertEqual({f.name: f.value for f in RESEND.figures(got["totals"])},
                         {"contacts": 3, "subscribed": 2, "unsubscribed": 1})
        self.assertEqual([(f.dim, f.value) for f in RESEND.figures(got["segments"])],
                         [("Newsletter", 2), ("Customers", 1)])
        emails = [(f.dim, f.value) for f in RESEND.figures(got["emails"])]
        self.assertEqual(emails, [(None, 4), ("delivered", 2), ("bounced", 1), ("opened", 1)])
        self.assertTrue(got["emails"].flags["recent_only"])
        self.assertEqual((got["emails"].start, got["emails"].end), ("2026-10-02", "2026-10-26"))

    def test_kept_fields(self):
        text = json.dumps([a.body for a in fetch()])
        for gone in ("first_name", "Welcome, Cy", "subject", "message_id"):
            self.assertNotIn(gone, text)
        self.assertIn("cy@example.com", text)          # the newest, before the People rule

    def test_not_every_page_is_null(self):
        got = {a.report: a for a in fetch(FakeResend(endless=True))}
        self.assertTrue(got["totals"].flags["incomplete"])
        self.assertEqual({f.name: f.value for f in RESEND.figures(got["totals"])},
                         {"contacts": None, "subscribed": None, "unsubscribed": None})

    def test_a_sending_only_key(self):
        with self.assertRaises(Unreachable) as got:
            fetch(FakeResend(fail=401, detail="This API key is restricted to only send emails"))
        self.assertIn("can only send emails", str(got.exception))
        self.assertIn("full-access", str(got.exception))
        self.assertNotIn(KEY, str(got.exception))


class People(Base):
    def test_old_addresses_go_new_ones_stay(self):
        self.config["privacy"]["keep_days"] = 5
        code, out = self.run_sync(FakeResend())
        self.assertEqual(code, 0, out)
        bodies = [json.loads(t) for t in self.stored().split("\n")]
        contacts = {c["id"]: c.get("email") for c in bodies[0]["contacts"]}
        self.assertEqual(contacts, {"c3": "cy@example.com", "c2": None, "c1": None})
        emails = {e["id"]: e.get("to") for e in bodies[2]["emails"]}
        self.assertEqual(emails, {"e4": ["cy@example.com"], "e3": ["bo@example.com"],
                                  "e2": None, "e1": None})     # 7 days old: gone


class Anonymous(Base):
    identity = "anonymous"

    def test_no_address_kept(self):
        self.run_sync(FakeResend())
        self.assertNotIn("@example.com", self.stored())
        mine = [t for t in api.view(self.config, self.folder, SITE, admin=True, now=NOW)["tools"]
                if t["id"] == "resend"][0]
        self.assertTrue(mine["more"]["people"])
        self.assertFalse([p for p in mine["more"]["people"] if p.get("email")])


class Recheck(Base):
    def test_matches_then_planted_errors(self):
        code, out = self.run_sync(FakeResend())
        self.assertEqual(code, 0, out)
        self.assertTrue(recount.check(self.folder, SITE, "resend")["resend"]["ok"])
        view = api.view(self.config, self.folder, SITE, admin=False, now=NOW)["tools"][0]
        self.assertEqual([(h["name"], h["value"]) for h in view["headline"]],
                         [("contacts", 3), ("subscribed", 2), ("unsubscribed", 1)])
        db = sqlite3.connect(self.folder / store.FILE)
        db.execute("UPDATE figures SET value = 3 WHERE dim = 'bounced'")
        aid = db.execute("SELECT id FROM answers WHERE report = 'segments'").fetchone()[0]
        db.execute("INSERT INTO figures (answer_id, name, label, dim, value, rank) VALUES "
                   "(?, 'contacts', 'Contacts', 'VIP', 9, 2)", (aid,))
        db.commit()
        db.close()
        problems = recount.check(self.folder, SITE, "resend")["resend"]["problems"]
        self.assertTrue(any("bounced" in p and "says 1" in p for p in problems), problems)
        self.assertTrue(any("VIP" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
