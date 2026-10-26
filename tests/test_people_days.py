"""A lead's name and email kept no longer than the site's People days
(conversions/people_days.py): the identities, the rows a sync removed, the
hook spool and the upgrade copies, while every figure and the second count
stay the same. Hosts are example.com; the emails are made up."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conversions_hooks import T, Base, lead  # noqa: E402

from skald import conversions_data  # noqa: E402
from skald.conversions import jobs, people_days, spool, store  # noqa: E402
from skald.people import leadlist, lookup  # noqa: E402

UTC = timezone.utc
TODAY = date(2026, 10, 11)                  # T's day
DAY = 86400
OLD = T - 200 * DAY                         # 2026-03-25 12:00 UTC: past 180 days
CUT = "2026-04-14T00:00:00Z"                # 180 days before TODAY, midnight UTC
VID3, VID4, VID4B, VID5 = ("skv_" + c * 22 for c in "BCDE")


def at(stamp: int) -> str:
    return datetime.fromtimestamp(stamp, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class PeopleDays(Base):
    identity = "full"

    def setUp(self):
        super().setUp()
        self.config["privacy"] = {"keep_days": 180}
        self.config["report"] = {"timezone": "UTC"}

    def send(self, when: int, **kw):
        self.now = when
        got = self.post("lead", lead(**kw))
        self.assertEqual(got[0], 200, got)

    def deliver(self):
        # person 1: one old lead. Its identity goes blank.
        self.send(OLD, external_ref="L-1", email="one@example.com", name="Person One",
                  at=at(OLD - 7200), vid=None)
        # person 2: a lead of last week. Kept.
        self.send(T - 10 * DAY, external_ref="L-2", email="two@example.com", name="Person Two",
                  at=at(T - 10 * DAY), vid=None)
        # person 3: an old started and finished booking, and a lead yesterday:
        # the old rows move to a blank identity, the new one keeps the email.
        self.send(OLD, external_ref="L-3", stage="started", email="three@example.com",
                  name="Person Three", at=at(OLD - 4 * 3600), vid=VID3)
        self.send(OLD, external_ref="L-3", email="three@example.com", name="Person Three",
                  at=at(OLD - 3600), vid=None)
        self.send(T - DAY, external_ref="L-33", email="three@example.com",
                  name="Person Three", at=at(T - DAY), vid=None)
        # person 4: a start 10 hours before the edge, finished 5 hours after it
        # from another browser (matched by the identity only), and a lead long
        # before: the start stays with its finish, the lead long before moves.
        edge = int(datetime(2026, 4, 14, tzinfo=UTC).timestamp())
        self.send(edge - 9 * 3600, external_ref="L-4", stage="started",
                  email="four@example.com", name="Person Four", at=at(edge - 10 * 3600),
                  vid=VID4)
        self.send(edge + 6 * 3600, external_ref="L-4", email="four@example.com",
                  name="Person Four", at=at(edge + 5 * 3600), vid=VID4B)
        self.send(OLD - 30 * DAY, external_ref="L-44", email="four@example.com",
                  name="Person Four", at=at(OLD - 30 * DAY), vid=None)
        # person 5: an old abandoned start.
        self.send(OLD, external_ref="L-5", stage="started", email="five@example.com",
                  name="Person Five", at=at(OLD - 6 * 3600), vid=VID5)
        # person 6: an old lead a sync took away (kept whole in `removed`).
        self.send(OLD, external_ref="L-6", email="six@example.com", name="Person Six",
                  at=at(OLD - 5 * 3600), vid=None)
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            rid = db.execute("SELECT id FROM conversions WHERE external_ref = 'L-6'").fetchone()[0]
            store.remove(db, rid, "the lead is no longer in the lead database")
        finally:
            db.close()
        self.now = T

    # ------------------------------------------------------------ helpers

    def ctx(self, out=None, live_dir=None):
        out = out if out is not None else []
        return SimpleNamespace(config=self.config, db_path=self.folder / "history.sqlite",
                               site="example.com", now=datetime.fromtimestamp(T, tz=UTC),
                               live_dir=live_dir or self.folder, out=out.append,
                               err=out.append, tz=UTC)

    def emails(self) -> dict:
        """{external_ref and stage: the email its row shows}."""
        return {f"{r[0]}/{r[1]}": r[2] for r in self.rows(
            "SELECT c.external_ref, c.stage, i.email FROM conversions c LEFT JOIN identities i "
            "ON i.id = c.identity_id ORDER BY c.id")}

    def figures(self):
        db = store.connect(self.folder / "conversions.sqlite")
        try:
            got = conversions_data.figures(db, "example.com", UTC, date(2026, 1, 1), TODAY,
                                           store.stamp(datetime.fromtimestamp(T, tz=UTC)), 24)
            gone = store.abandoned(db, "example.com", "2026-01-01T00:00:00Z",
                                   "2026-10-12T00:00:00Z", 24, at(T))
        finally:
            db.close()
        return got, sorted(r["external_ref"] for r in gone)

    def blobs(self):
        """conversions.json for a day in April (the old rows in its 180 days)
        and for today, each with the second count run."""
        out = []
        for day in (date(2026, 4, 20), TODAY):
            now = datetime.combine(day, datetime.min.time(), tzinfo=UTC).replace(hour=12)
            out.append(conversions_data.blob(self.config, self.folder, "example.com", UTC,
                                             day, now))
        return out

    def spooled_all(self) -> str:
        return "".join(p.read_text() for p in sorted((self.folder / "hooks").glob("*.jsonl")))

    # -------------------------------------------------------------- tests

    def test_old_rows_lose_name_and_email_young_keep_them(self):
        self.deliver()
        before = self.emails()
        self.assertEqual(before["L-1/completed"], "one@example.com")
        got = people_days.run(self.ctx(), TODAY)
        self.assertEqual(got["example.com"]["days"], 180)
        after = self.emails()
        self.assertIsNone(after["L-1/completed"])
        self.assertIsNone(after["L-5/started"])
        self.assertEqual(after["L-2/completed"], "two@example.com")
        # Person 3: the old booking shows no email; yesterday's lead does.
        self.assertIsNone(after["L-3/started"])
        self.assertIsNone(after["L-3/completed"])
        self.assertEqual(after["L-33/completed"], "three@example.com")
        # Person 4: the start is chained to its young finish; the lead long before is not.
        self.assertEqual(after["L-4/started"], "four@example.com")
        self.assertEqual(after["L-4/completed"], "four@example.com")
        self.assertIsNone(after["L-44/completed"])
        # Nothing of the old emails or names is left in the file.
        db = sqlite3.connect(self.folder / "conversions.sqlite")
        try:
            dump = "\n".join(db.iterdump())
        finally:
            db.close()
        for gone in ("one@example.com", "five@example.com", "six@example.com", "Person One",
                     "Person Six"):
            self.assertNotIn(gone, dump)
        for kept in ("two@example.com", "three@example.com", "four@example.com"):
            self.assertIn(kept, dump)
        # The old email finds the person no more; a young one still does.
        self.assertEqual(lookup.person(self.config, self.folder, "example.com",
                                       "one@example.com")["conversions"], [])
        three = lookup.person(self.config, self.folder, "example.com", "three@example.com")
        self.assertEqual([c["external_ref"] for c in three["conversions"]], ["L-33"])
        # The lead list shows the old leads, without their names and emails.
        listed = leadlist.rows(self.config, self.folder, "example.com", date(2026, 1, 1),
                               TODAY, names=True)["rows"]
        by_ref = {r["ref"]: r for r in listed}
        self.assertIsNone(by_ref["L-1"]["email"])
        self.assertIsNone(by_ref["L-1"]["name"])
        self.assertEqual(by_ref["L-2"]["email"], "two@example.com")

    def test_figures_and_the_second_count_do_not_change(self):
        self.deliver()
        figures, blobs = self.figures(), self.blobs()
        self.assertEqual(figures[1], ["L-5"])           # the old abandoned start
        for blob in blobs:
            self.assertEqual(blob["withheld"], {})
        people_days.run(self.ctx(), TODAY)
        self.assertEqual(self.figures(), figures)
        self.assertEqual(self.blobs(), blobs)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM conversions"), [(9,)])

    def test_removed_rows_and_the_spool(self):
        self.deliver()
        self.assertIn("six@example.com", self.rows("SELECT row FROM removed")[0][0])
        self.assertIn("one@example.com", self.spooled_all())
        got = people_days.run(self.ctx(), TODAY)["example.com"]
        row = json.loads(self.rows("SELECT row FROM removed")[0][0])
        self.assertIsNone(row["email"])
        self.assertIsNone(row["name"])
        self.assertEqual(row["external_ref"], "L-6")
        self.assertEqual(got["removed"], 1)
        text = self.spooled_all()
        for gone in ("one@example.com", "five@example.com", "six@example.com",
                     "Person One"):
            self.assertNotIn(gone, text)
        # Lines younger than 180 days keep theirs, the edge's day included.
        self.assertIn("two@example.com", text)
        self.assertEqual(text.count("four@example.com"), 1)      # the finish's line only
        old = spool.read(self.folder / "hooks", date(2026, 3, 25))
        self.assertEqual({r["body"]["external_ref"] for r in old},
                         {"L-1", "L-3", "L-5", "L-6"})
        self.assertTrue(all("email" not in r["body"] and "name" not in r["body"] for r in old))
        self.assertEqual(got["spool"], 7)    # L-1, L-3 twice, L-5, L-6, L-44, L-4 started
        # once more: nothing left to clear, nothing said
        out = []
        self.assertEqual(people_days.run(self.ctx(out), TODAY), {})
        self.assertEqual(out, [])

    def test_counts_are_said_and_logged_never_values(self):
        self.deliver()
        out = []
        people_days.run(self.ctx(out), TODAY)
        self.assertEqual(len(out), 1)
        self.assertIn("example.com: names and emails older than 180 days cleared: 3 people",
                      out[0])
        log = (self.folder / "privacy.log").read_text()
        self.assertIn("people-days site=example.com days=180 people=3", log)
        for text in (out[0], log):
            self.assertNotIn("@", text)
            self.assertNotIn("Person", text)

    def test_no_shorter_promise_keeps_todays_default(self):
        self.deliver()
        cases = ({"keep_days": 400}, {"keep_days": 500}, {})       # leads 400 days
        for privacy in cases:
            with self.subTest(privacy=privacy):
                self.config["privacy"] = privacy
                self.assertEqual(people_days.run(self.ctx(), TODAY), {})
                self.assertEqual(self.emails()["L-1/completed"], "one@example.com")
        # Leads kept for good: a People days set is always shorter; none set, none.
        self.config["conversions"]["retention_days"] = 0
        self.config["privacy"] = {}
        self.assertEqual(people_days.run(self.ctx(), TODAY), {})
        self.config["privacy"] = {"keep_days": 3650}
        self.assertEqual(people_days.run(self.ctx(), TODAY), {})
        self.config["privacy"] = {"keep_days": 180}
        self.assertEqual(people_days.run(self.ctx(), TODAY)["example.com"]["people"], 3)

    def test_identity_days(self):
        self.assertEqual(people_days.identity_days(180, 400), 180)
        self.assertIsNone(people_days.identity_days(400, 400))
        self.assertIsNone(people_days.identity_days(500, 400))
        self.assertEqual(people_days.identity_days(500, 0), 500)    # leads kept for good
        self.assertEqual(people_days.kept_days({"privacy": {"keep_days": 180}}), 180)
        self.assertEqual(people_days.kept_days({}), 400)             # no promise set
        self.assertEqual(people_days.kept_days({"conversions": {"retention_days": 0}}), 0)

    def test_settings_rows_each_site_by_its_own(self):
        # A site's own row is its promise; the install's default (unset) is none.
        self.config["privacy"] = {}
        self.config["_settings"] = {"prune": {
            "privacy.keep_days": {"default": 395, "sites": {"example.com": 180}, "set": False},
            "conversions.retention_days": {"default": 0, "sites": {}, "set": True}}}
        days_of = people_days.windows(self.config)
        self.assertEqual(days_of("example.com"), 180)
        self.assertIsNone(days_of("other.example.com"))
        self.config["_settings"]["prune"]["privacy.keep_days"]["set"] = True
        self.assertEqual(people_days.windows(self.config)("other.example.com"), 395)

    def test_upgrade_copies_are_cleared_too(self):
        self.deliver()
        path = self.folder / "conversions.sqlite"
        db = store.connect(path)
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.close()
        bak = self.folder / "conversions.sqlite.v8.bak"
        shutil.copy(path, bak)
        got = people_days.run(self.ctx(), TODAY)["example.com"]
        self.assertGreater(got["backups"], 0)
        copy = sqlite3.connect(bak)
        try:
            dump = "\n".join(copy.iterdump())
        finally:
            copy.close()
        self.assertNotIn("one@example.com", dump)
        self.assertIn("two@example.com", dump)

    def test_once_after_the_upgrade_then_the_daily_prune(self):
        self.deliver()
        out = []
        ctx = self.ctx(out)
        self.assertFalse(people_days.swept(ctx))
        jobs.live(ctx)                       # the first live run after the upgrade
        self.assertTrue(people_days.swept(ctx))
        self.assertIsNone(self.emails()["L-1/completed"])
        self.assertTrue(any("people days: example.com" in line for line in out))
        self.assertIsNone(people_days.once(ctx), "once only")


class Command(unittest.TestCase):
    """`skald conversions prune` (the daily run's step) says the counts."""

    def test_prune_says_the_counts(self):
        from support import Sandbox
        box = Sandbox(mail=False)
        self.addCleanup(box.close)
        box.config.write_text(box.config.read_text() + "privacy:\n  keep_days: 30\n")
        db = store.connect(box.root / "conversions.sqlite")
        try:
            store.record_conversion(db, {
                "site": "example.com", "action": "demo", "stage": "completed",
                "at": "2026-01-02T10:00:00Z", "external_ref": "L-9", "tool": "lead",
                "identity": {"email": "nine@example.com", "name": "Person Nine"}})
        finally:
            db.close()
        code, out, err = box.run("--today", "2026-03-01", "conversions", "prune")
        self.assertEqual(code, 0, err)
        self.assertIn("names and emails older than 30 days cleared: 1 people, 1 lead row(s)",
                      out)
        self.assertNotIn("nine@example.com", out + err)
        self.assertNotIn("nine@example.com", (box.root / "privacy.log").read_text())


if __name__ == "__main__":
    unittest.main()
