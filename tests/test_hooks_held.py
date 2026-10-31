"""Refused hook deliveries, told apart, held 24 hours and taken in by a key saved
later (2.44.1: conversions/held.py, key_check.py, hook_keys.py, audit_hooks_held.py).

A site's Calendly sent real bookings that Skald refused while every Test of
Skald's own passed: the Test is signed with the key Skald has, so it proves only
the address. Here:

  - every adapter: no signature header at all is `unsigned`, a wrong one
    `bad_signature`, each in the tool's own word for its key;
  - a refused delivery is held (0600 in a 0700 folder, only the headers that
    verify it), never a test of Skald's own nor a plain-key lead; capped per
    hook; purged past 24 hours;
  - a key saved later takes in what it verifies, with the time each first came,
    once; a wrong key leaves them held; an unsigned one says so;
  - a deletion request removes held bodies holding the person's email;
  - the tools list's key fields, and connect_check good only after a real
    delivery accepted since the key was saved;
  - the audit's own road over the hold.

Hosts are example.com; the keys are made up and protect nothing.
"""
from __future__ import annotations

import json
import stat
import sqlite3
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A  # noqa: E402
from conversions_support import FakeHandler  # noqa: E402
from ingest_support import TenantServer  # noqa: E402
from test_conversions_hooks import Base, T, lead  # noqa: E402

from skald.conversions.hooks import Receiver  # noqa: E402

from skald import audit_hooks_held  # noqa: E402
from skald.conversions import TOOLS, held, key_check, roads, secrets_store, store  # noqa: E402
from skald.conversions.adapters import adapter  # noqa: E402

SITE = "example.com"
CALENDLY_KEY = "calendly-own-signing-key-made-up"       # the key "Calendly" signs with


def booking(n: int, email: str = "person@example.com") -> dict:
    uri = f"https://api.calendly.com/scheduled_events/E{n}/invitees/I{n}"
    return {"event": "invitee.created", "created_at": "2026-10-11T11:00:00Z",
            "payload": {"uri": uri, "email": email, "name": "A Person"}}


class HeldBase(Base):
    identity = "full"

    def setUp(self):
        super().setUp()
        # Every refusal here comes from one sender: no pre-auth bucket in the way.
        self.config["hooks"].update(preauth_per_minute=6000, preauth_burst=1000)
        self.rx = Receiver(self.config, self.folder, clock=lambda: self.now)

    def states(self, db):
        at = datetime.fromtimestamp(self.now, tz=timezone.utc)
        return {s["tool"]: s for s in roads.hook_states(self.config, self.folder, SITE, db, at)}

    def save(self, key):
        secrets_store.put(secrets_store.path_for(self.config, self.folder),
                          secrets_store.key(SITE, "calendly"), key)
        return key_check.check(self.config, self.folder, None, SITE, "calendly", key,
                               now=T + 3600)

    def refuse_three(self):
        self.post("calendly", booking(1), secret=CALENDLY_KEY)
        self.now = T + 600
        self.post("calendly", booking(2), secret=CALENDLY_KEY)
        self.now = T + 1200
        self.post("calendly", booking(1), secret=CALENDLY_KEY)      # Calendly sent it again

    def unsigned(self, tool, payload, extra=None):
        body = json.dumps(payload).encode()
        path = f"/traffic-hooks/{SITE}/{tool}"
        return self.rx.http(FakeHandler(path, body, {"Host": "www.example.com",
                                                     "Content-Type": "application/json",
                                                     **(extra or {})}))

    def outcomes(self, tool=None):
        sql = "SELECT tool, outcome FROM deliveries" + (f" WHERE tool = '{tool}'" if tool else "")
        return self.rows(sql + " ORDER BY id")

    def files(self, tool):
        where = held.root(self.folder) / SITE / tool
        return sorted(p for p in where.iterdir() if p.is_file()) if where.is_dir() else []


class Held(HeldBase):
    # --------------------------------------------------------- told apart

    def test_every_adapter_tells_unsigned_from_a_bad_signature(self):
        for tool in TOOLS:
            with self.subTest(tool=tool):
                sample = adapter(tool).sample(SITE, self.now)
                got = self.unsigned(tool, sample)
                self.assertEqual(got, (401, {"error": "no signature"}))
                self.now += 61
                self.assertEqual(self.post(tool, sample, secret="not-the-key-at-all")[0], 401)
                self.now += 61
                self.assertEqual([o for _, o in self.outcomes(tool)], ["unsigned", "bad_signature"])

    def test_words_and_fixes_name_the_tools_key(self):
        self.unsigned("calendly", booking(1))
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            got = self.states(db)
            self.assertIn("Calendly sent no signature: the webhook was made without a signing key",
                          got["calendly"]["words"])
            self.assertIn("Make the Calendly webhook again with the signing key Skald gives",
                          got["calendly"]["fix"])
            self.assertIn("1 refused delivery is held for 24 h", got["calendly"]["words"])
            self.now += 61
            self.post("calendly", booking(2), secret=CALENDLY_KEY)
            got = self.states(db)
            self.assertIn("the signing key Calendly signs with is not the one saved in Skald",
                          got["calendly"]["words"])
            self.assertIn("paste the right one, or make the webhook again with Skald's",
                          got["calendly"]["fix"])
            self.assertEqual(got["calendly"]["held"], 2)
            self.post("stripe", adapter("stripe").sample(SITE, self.now), secret="whsec_wrong1")
            got = self.states(db)
            self.assertIn("signing secret Stripe signs with", got["stripe"]["words"])
        finally:
            db.close()

    def test_old_rows_stay_readable(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            store.log_delivery(db, SITE, "calendly", "bad_signature", 401, "3 refused")
            db.commit()
            self.assertEqual(roads.since_saved(db, SITE, "calendly", "2000-01-01T00:00:00Z"),
                             {"accepted": 0, "refused": 3, "unsigned": 0})
            self.assertIn("the signature did not match",
                          roads.last_real(db, SITE, "calendly")["words"])
        finally:
            db.close()

    # --------------------------------------------------------------- hold

    def test_a_refusal_is_held_privately_with_only_what_verifies_it(self):
        self.post("calendly", booking(1), secret=CALENDLY_KEY,
                  extra={"Cookie": "a=b", "User-Agent": "Calendly"})
        (path,) = self.files("calendly")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        for d in (held.root(self.folder), path.parent.parent, path.parent):
            self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700, d)
        got = held.read(path)
        self.assertEqual(sorted(got["headers"]), [":method", ":uri",
                                                  "calendly-webhook-signature"])
        self.assertEqual(got["why"], "bad_signature")
        self.assertEqual(json.loads(got["body"])["payload"]["email"], "person@example.com")
        self.assertEqual(got["received_at"], "2026-10-11T12:00:00Z")
        self.assertEqual(self.spooled(), "", "held, never spooled")

    def test_tests_and_plain_keys_are_never_held(self):
        self.post("calendly", booking(1), secret="wrong-key-0001", extra={"X-Skald-Test": "1"})
        self.assertEqual(self.files("calendly"), [])
        self.assertEqual([o for _, o in self.outcomes()], ["test_failed"])
        self.unsigned("lead", lead(), extra={"Authorization": "Bearer not-the-key-0001"})
        self.assertEqual(self.files("lead"), [], "the key it sent is never kept")
        self.now += 61
        self.unsigned("lead", lead())
        self.assertEqual(len(self.files("lead")), 1, "a lead with no key at all is held")

    def test_cap_and_purge_at_24_hours(self):
        with mock.patch.object(held, "CAP", 3):
            for n in range(5):
                self.now = T + n
                self.post("calendly", booking(n), secret=CALENDLY_KEY)
            kept = [json.loads(held.read(p)["body"])["payload"]["uri"][-2:]
                    for p in self.files("calendly")]
            self.assertEqual(kept, ["I2", "I3", "I4"], "the oldest go first")
        self.assertEqual(held.count(self.folder, SITE, "calendly", T + 10), 3)
        self.assertEqual(held.count(self.folder, SITE, "calendly", T + 86400 + 10), 0)
        self.now = T + 86400 + 10
        self.post("calendly", booking(9), secret=CALENDLY_KEY)
        self.assertEqual(len(self.files("calendly")), 1, "a write purges the hook")
        self.assertEqual(held.purge(self.folder, T + 3 * 86400), 1)
        self.assertEqual(self.files("calendly"), [])

    # ----------------------------------------------------------- take in

    def test_the_right_key_takes_them_in_with_their_times_once(self):
        self.refuse_three()
        got = self.save(CALENDLY_KEY)
        self.assertEqual(got["verdict"], "matches")
        self.assertEqual((got["held"], got["matched"], got["taken"], got["recorded"]), (3, 3, 3, 2))
        self.assertFalse(got["unsigned"])
        self.assertEqual(got["refused_last_at"], "2026-10-11T12:20:00Z")
        rows = self.rows("SELECT external_ref, received_at FROM conversions ORDER BY id")
        self.assertEqual([r[1] for r in rows], ["2026-10-11T12:00:00Z", "2026-10-11T12:10:00Z"],
                         "kept with the time each first came")
        self.assertEqual(self.rows("SELECT COUNT(*) FROM deliveries WHERE outcome = "
                                   "'accepted_held'"), [(3,)])
        self.assertEqual(self.files("calendly"), [], "out of the hold")
        again = self.save(CALENDLY_KEY)
        self.assertEqual((again["verdict"], again["held"], again["taken"]), ("none_held", 0, 0))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions"), [(2,)])
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            self.assertEqual(roads.since_saved(db, SITE, "calendly", "2026-10-11T13:00:00Z"),
                             {"accepted": 3, "refused": 0, "unsigned": 0},
                             "taken in by the save: counted since it")
            self.assertEqual(roads.last_real(db, SITE, "calendly")["outcome"], "accepted_held")
        finally:
            db.close()
        self.assertEqual(audit_hooks_held.findings(self.config, self.folder, SITE, now=T + 3700), [])

    def test_a_held_event_skald_does_not_count_still_leaves_the_others_counted(self):
        self.post("calendly", booking(1), secret=CALENDLY_KEY)
        self.now = T + 600
        self.post("calendly", {"event": "routing_form_submission.created",
                               "payload": {"uri": "x"}}, secret=CALENDLY_KEY)
        got = self.save(CALENDLY_KEY)
        self.assertEqual((got["matched"], got["taken"]), (2, 1))
        self.assertEqual([o for _, o in self.outcomes()],
                         ["bad_signature", "bad_signature", "accepted_held", "ignored"])
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            self.assertEqual(roads.since_saved(db, SITE, "calendly", "2026-10-11T13:00:00Z"),
                             {"accepted": 2, "refused": 0, "unsigned": 0})
        finally:
            db.close()
        self.assertEqual(audit_hooks_held.findings(self.config, self.folder, SITE, now=T + 3700), [])

    def test_a_wrong_key_leaves_them_held(self):
        self.refuse_three()
        got = self.save("another-made-up-key-0001")
        self.assertEqual((got["verdict"], got["held"], got["matched"], got["taken"]),
                         ("no_match", 3, 0, 0))
        self.assertEqual(len(self.files("calendly")), 3)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions"), [(0,)])

    def test_unsigned_says_no_key_can_match(self):
        self.unsigned("calendly", booking(1))
        got = self.save(CALENDLY_KEY)
        self.assertEqual((got["verdict"], got["unsigned"], got["matched"]), ("unsigned", True, 0))

    def test_a_signature_far_from_when_it_came_is_not_taken(self):
        body = json.dumps(booking(1)).encode()
        headers = {k.lower(): v for k, v in
                   adapter("calendly").sign(body, CALENDLY_KEY, T - 3600).items()}
        held.keep(self.folder, SITE, "calendly", headers, body, T, "bad_signature")
        self.assertEqual(self.save(CALENDLY_KEY)["verdict"], "no_match")

    def test_a_deletion_request_removes_their_held_bodies(self):
        self.post("calendly", booking(1, "person@example.com"), secret=CALENDLY_KEY)
        self.now += 1
        self.post("calendly", booking(2, "other@example.com"), secret=CALENDLY_KEY)
        self.assertEqual(held.forget(self.folder, {"Person@Example.com"}, dry_run=True), 1)
        self.assertEqual(len(self.files("calendly")), 2)
        self.assertEqual(held.forget(self.folder, {"person@example.com"}, SITE), 1)
        (left,) = self.files("calendly")
        self.assertIn(b"other@example.com", held.read(left)["body"])


class Audit(HeldBase):
    def test_the_audits_own_road(self):
        self.refuse_three()
        self.assertEqual(audit_hooks_held.findings(self.config, self.folder, SITE, now=T + 60), [])
        self.assertTrue(any("past 24 hours" in p for p in audit_hooks_held.findings(
            self.config, self.folder, SITE, now=T + 2 * 86400)))
        body = json.dumps(booking(7)).encode()
        held.keep(self.folder, SITE, "calendly", {}, body, T + 5000, "unsigned")
        self.assertTrue(any("no refusal in the delivery log" in p for p in
                            audit_hooks_held.findings(self.config, self.folder, SITE, now=T + 5000)))

    def test_a_keep_everything_site_keeps_them_and_the_audit_agrees(self):
        # 2.45.2: on 31 Oct one site's held deliveries, kept as the rule says,
        # made run-daily fail as "past 24 hours".
        self.refuse_three()
        self.config.setdefault("retention", {})["keep_everything"] = True
        later = T + 2 * 86400
        self.assertEqual(held.purge(self.folder, later, keeps=lambda site: True), 0)
        self.assertEqual(len(self.files("calendly")), 3)
        self.assertEqual(audit_hooks_held.findings(self.config, self.folder, SITE, now=later), [])
        with mock.patch.object(audit_hooks_held, "KEEP_ALL_CAP", 1):
            self.assertEqual(audit_hooks_held.findings(self.config, self.folder, SITE, now=later),
                             ["hooks held: example.com/calendly: 3 held deliveries, more than 1"])
        # The rule off again: the age is the finding, as before.
        self.config["retention"]["keep_everything"] = False
        self.assertTrue(any("past 24 hours" in p for p in audit_hooks_held.findings(
            self.config, self.folder, SITE, now=later)))

    def test_accepted_held_recounted_from_the_spool(self):
        self.refuse_three()
        self.save(CALENDLY_KEY)
        self.assertEqual(audit_hooks_held.findings(self.config, self.folder, SITE, now=T + 3700), [])
        db = sqlite3.connect(self.folder / "conversions.sqlite")
        try:
            db.execute("DELETE FROM deliveries WHERE id = (SELECT MAX(id) FROM deliveries "
                       "WHERE outcome = 'accepted_held')")
            db.commit()
        finally:
            db.close()
        got = audit_hooks_held.findings(self.config, self.folder, SITE, now=T + 3700)
        self.assertEqual(got, ["hooks held: example.com/calendly: 2 taken in by the delivery "
                               "log, 3 held lines in the spool"])

    def test_held_spool_lines_say_so(self):
        self.refuse_three()
        self.save(CALENDLY_KEY)
        lines = [json.loads(x) for f in sorted((self.folder / "hooks").glob("*.jsonl"))
                 for x in f.read_text().splitlines()]
        self.assertEqual([(x.get("held"), x["received_at"]) for x in lines],
                         [(True, "2026-10-11T12:00:00Z"), (True, "2026-10-11T12:10:00Z"),
                          (True, "2026-10-11T12:20:00Z")])


class ForgetCommand(unittest.TestCase):
    def test_forget_email_removes_held_bodies(self):
        from support import Sandbox
        box = Sandbox()
        self.addCleanup(box.close)
        body = json.dumps(booking(1, "person@example.com")).encode()
        held.keep(box.root, SITE, "calendly", {}, body, time.time(), "unsigned")
        held.keep(box.root, SITE, "calendly", {}, json.dumps(booking(2, "x@example.com")).encode(),
                  time.time(), "unsigned")
        code, out, err = box.run("forget", "--email", "person@example.com")
        self.assertEqual(code, 0, err)
        self.assertIn("held deliveries: deleted 1 refused delivery", out)
        self.assertEqual(held.count(box.root, SITE, "calendly", time.time()), 1)


class Screens(TenantServer):
    """The tools list, the paste and secret answers, the Test's answer, and
    connect_check, over real HTTP."""

    def setUp(self):
        super().setUp()
        self.s, self.A = self, A
        self.cookie, self.csrf = self.session("owner@example.com")

    def do(self, act, body):
        return self.s.post(f"/traffic/{self.A}/integrations/{act}", {"site": self.A, **body},
                           self.cookie, self.csrf)

    def tool(self, name):
        got = self.s.call("GET", f"/traffic/{self.A}/integrations", cookie=self.cookie)
        self.assertEqual(got.status, 200, got.json)
        return next(t for t in got.json["tools"] if t["tool"] == name)

    def arrived(self, what):
        got = self.s.post(f"/traffic/{self.A}/sites/arrived", {"site": self.A, "what": what},
                          self.cookie, self.csrf)
        self.assertEqual(got.status, 200, got.json)
        return got.json["test"]

    def log(self, outcome, at=None, error=None):
        db = store.connect(self.s.live / "conversions.sqlite")
        try:
            store.log_delivery(db, self.A, "calendly", outcome, 200 if outcome != "unsigned"
                               else 401, error, None, at)
            db.commit()
        finally:
            db.close()

    def test_tools_list_fields_and_the_paste_check(self):
        t = self.tool("calendly")
        self.assertEqual((t["key_word"], t["saved_at"], t["saved_by"], t["saved_how"],
                          t["last_real"], t["since_saved"], t["held"]),
                         ("signing key", None, None, None, None, None, 0))
        self.assertEqual(self.tool("stripe")["key_word"], "signing secret")
        self.assertEqual(self.tool("hubspot")["key_word"], "client secret")
        # A booking refused before the key was saved, held:
        self.log("bad_signature", "2026-10-11T13:59:00Z", "1 refused")
        body = json.dumps(booking(1)).encode()
        now = time.time()
        headers = {k.lower(): v for k, v in
                   adapter("calendly").sign(body, CALENDLY_KEY, now).items()}
        held.keep(self.s.live, self.A, "calendly", headers, body, now, "bad_signature")
        self.assertEqual(self.tool("calendly")["held"], 1)
        got = self.do("hooks/paste", {"tool": "calendly", "secret": CALENDLY_KEY})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["check"], {"held": 1, "matched": 1, "taken": 1, "recorded": 1,
                                             "refused_last_at": "2026-10-11T13:59:00Z",
                                             "unsigned": False, "verdict": "matches"})
        self.assertNotIn(CALENDLY_KEY, json.dumps(got.json))
        t = self.tool("calendly")
        self.assertEqual((t["saved_at"], t["saved_by"], t["saved_how"], t["held"]),
                         ("2026-10-11T14:00:00Z", "Owner", "pasted", 0))
        self.assertEqual(t["since_saved"], {"accepted": 1, "refused": 0, "unsigned": 0})
        self.assertEqual(t["last_real"]["outcome"], "accepted_held")
        self.assertNotIn("@", json.dumps({k: t[k] for k in ("saved_by", "last_real")}))
        got = self.do("secret", {"tool": "calendly"})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["check"]["verdict"], "none_held")
        self.assertEqual(self.tool("calendly")["saved_how"], "made by Skald")

    def test_the_test_proves_the_address_and_connect_check_waits_for_a_real_one(self):
        self.assertEqual(self.do("secret", {"tool": "calendly"}).status, 200)
        got = self.do("test", {"tool": "calendly"})
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual((got.json["proves"], got.json["last_real"]), ("address", None))
        t = self.arrived("hook:calendly")
        self.assertEqual(t["verdict"], "wait", "a passing Test alone is not good")
        self.assertIn("Only a real Calendly event proves the signing key", t["says"])
        self.log("unsigned", error="2 refused")
        t = self.arrived("hook:calendly")
        self.assertEqual(t["verdict"], "bad")
        self.assertIn("Calendly sent no signature", t["says"])
        self.assertIn("Make the Calendly webhook again", t["fix"])
        self.log("recorded")
        t = self.arrived("hook:calendly")
        self.assertEqual(t["verdict"], "ok", t)
        self.assertEqual({s["id"]: s["done"] for s in t["steps"]},
                         {"secret": True, "test": True, "real": True})
        got = self.do("test", {"tool": "calendly"})
        self.assertEqual(got.json["last_real"]["outcome"], "recorded")


if __name__ == "__main__":
    unittest.main()
