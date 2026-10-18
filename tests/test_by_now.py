"""Yesterday at this hour (2.13): the live snapshot's `by_now` (by_now.py) and
conversions.json today.by_now (conversions_leads.by_now), each against its second
count (audit_by_now.py through `audit --live`; audit_conversions_leads.check_by_now),
and the page's own reading of them (tests/js/by-now.mjs). Addresses are RFC 5737;
hosts example.com."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_conversions_leads, by_now, conversions_leads  # noqa: E402
from skald.conversions import store  # noqa: E402

from support import GPTBOT, Sandbox, line  # noqa: E402

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
DAY = date(2026, 10, 7)
NOON = datetime(2026, 10, 7, 12, tzinfo=UTC)          # --today runs at local noon
Y = NOON - timedelta(days=1)


def at(base: datetime, hours: float) -> datetime:
    return base.replace(hour=0) + timedelta(hours=hours)


def lines() -> list[str]:
    return [
        # Yesterday before noon: two readers (one sent by ChatGPT), three pages, a crawler.
        line(at(Y, 8), "203.0.113.20", "/"),
        line(at(Y, 8.02), "203.0.113.20", "/pricing"),
        line(at(Y, 9.5), "203.0.113.21", "/", referrer="https://chatgpt.com/"),
        line(at(Y, 10), "198.51.100.40", "/guides/alpha", GPTBOT),
        # Yesterday after noon: never in "yesterday at this hour".
        line(at(Y, 13), "203.0.113.22", "/"),
        line(at(Y, 15), "203.0.113.23", "/", referrer="https://perplexity.ai/"),
        # Today: three readers, one sent by an assistant twice, an hour apart (two visits).
        line(at(NOON, 7), "203.0.113.30", "/"),
        line(at(NOON, 9), "203.0.113.31", "/", referrer="https://chatgpt.com/"),
        line(at(NOON, 10.5), "203.0.113.31", "/docs", referrer="https://chatgpt.com/"),
        line(at(NOON, 11), "203.0.113.32", "/pricing"),
        line(at(NOON, 11.1), "203.0.113.32", "/signup"),
    ]


class Live(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.box.log(lines())
        stamp = NOON.timestamp() - 60
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))

    def tearDown(self):
        self.box.close()

    def live(self):
        code, out, err = self.box.run("--today", DAY.isoformat(), "live")
        self.assertEqual(code, 0, err)
        return json.loads((self.box.root / "live-example.com.json").read_text())

    def audit(self):
        return self.box.run("--today", DAY.isoformat(), "audit", "--live")

    def test_yesterday_to_the_same_time(self):
        snap = self.live()
        part = snap["by_now"]
        self.assertEqual((part["day"], part["state"], part["history"]), ("2026-10-06", "ok", None))
        self.assertTrue(part["until"].startswith("2026-10-06T12:00"), part["until"])
        self.assertEqual((part["visitors"], part["pages"], part["ai_visitors"]), (2, 3, 1))
        hours = part["hours"]
        self.assertEqual((hours["visitors"][8], hours["visitors"][9], sum(hours["visitors"])), (1, 1, 2))
        self.assertEqual((hours["pages"][8], hours["pages"][9]), (2, 1))
        self.assertEqual(hours["ai_visitors"][9], 1)
        self.assertEqual(sum(hours["visitors"][12:]), 0, "nothing after the time of day")

    def test_today_by_hour_adds_up_to_today(self):
        snap = self.live()
        th = snap["by_now"]["today_hours"]
        people = snap["people"]
        self.assertEqual(sum(th["visitors"]), people["readers"])
        self.assertEqual(sum(th["pages"]), people["views"])
        self.assertEqual(sum(th["ai_visitors"]), people["cited_visits"])
        self.assertEqual((th["ai_visitors"][9], th["ai_visitors"][10]), (1, 1), "a new one after the gap")

    def test_audit_recounts_it(self):
        self.live()
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: live", out)

    def tamper(self, fn):
        path = self.box.root / "live-example.com.json"
        snap = json.loads(path.read_text())
        fn(snap["by_now"])
        path.write_text(json.dumps(snap))
        return self.audit()

    def test_a_tampered_figure_is_found(self):
        self.live()
        code, _, err = self.tamper(lambda p: p.update(visitors=3))
        self.assertEqual(code, 1)
        self.assertIn("yesterday at this hour", err)
        self.assertIn("visitors", err)

    def test_a_tampered_hour_is_found(self):
        self.live()

        def move(p):
            p["hours"]["pages"][8] -= 1
            p["hours"]["pages"][7] += 1
            p["today_hours"]["ai_visitors"][9] += 1
        code, _, err = self.tamper(move)
        self.assertEqual(code, 1)
        self.assertIn("pages at 07:00", err)
        self.assertIn("today by hour: ai_visitors at 09:00", err)

    def test_withheld_or_partial_yesterday_carries_no_figures(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE days (site TEXT, day TEXT, verified INTEGER, partial_from TEXT, partial_until TEXT)")
        for verified, frm, want in ((0, None, "withheld"), (1, "2026-10-06T09:00", "partial")):
            db.execute("DELETE FROM days")
            db.execute("INSERT INTO days VALUES ('example.com', '2026-10-06', ?, ?, NULL)", (verified, frm))
            got = by_now.part({}, "example.com", UTC, NOON, NOON, None, db)
            self.assertEqual(got["state"], want)
            self.assertIsNone(got["visitors"])
            self.assertIsNone(got["hours"])


class Leads(unittest.TestCase):
    """Leads at this hour: finished forms and bookings, test rows never counted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "conversions.sqlite"
        db = store.connect(self.path)
        rows = [("contact", "completed", Y.replace(hour=8), 0), ("demo", "completed", Y.replace(hour=11, minute=30), 0),
                ("demo", "started", Y.replace(hour=10), 0), ("signup", "completed", Y.replace(hour=14), 0),
                ("contact", "completed", Y.replace(hour=9), 1),
                ("contact", "completed", NOON.replace(hour=7), 0), ("demo", "completed", NOON.replace(hour=11, minute=50), 0)]
        for i, (action, stage, when, test) in enumerate(rows):
            store.record_conversion(db, {"site": "example.com", "action": action, "stage": stage,
                                         "at": store.stamp(when), "external_ref": f"r{i}", "tool": "json"})
            if test:
                rid = db.execute("SELECT id FROM conversions WHERE external_ref = ?", (f"r{i}",)).fetchone()[0]
                store.mark_test(db, "example.com", [rid])
        db.close()

    def tearDown(self):
        self.tmp.cleanup()

    def part(self, held=(), since="2026-09-01"):
        db = store.connect(self.path)
        try:
            return conversions_leads.by_now(db, "example.com", UTC, DAY, NOON, set(held), since)
        finally:
            db.close()

    def test_counts_to_the_same_time(self):
        got = self.part()
        self.assertEqual((got["state"], got["leads"]), ("ok", 2), "08:00 and 11:30; not 14:00, not the test, not a start")
        self.assertEqual((got["hours"][8], got["hours"][11], got["hours"][14]), (1, 1, 0))
        self.assertEqual((got["today_hours"][7], got["today_hours"][11], sum(got["today_hours"])), (1, 1, 2))
        self.assertEqual(audit_conversions_leads.check_by_now(self.path, "example.com", UTC, DAY, got), [])

    def test_tampered_is_found(self):
        got = self.part()
        got["leads"] = 3
        got["today_hours"][7] = 0
        problems = audit_conversions_leads.check_by_now(self.path, "example.com", UTC, DAY, got)
        self.assertTrue(any("yesterday's leads to 12:00" in p for p in problems), problems)
        self.assertTrue(any("today's leads by hour" in p for p in problems), problems)

    def test_not_recorded_or_withheld(self):
        self.assertEqual(self.part(since="2026-10-07")["state"], "not_recorded")
        self.assertEqual(self.part(held={"2026-10-06"})["state"], "withheld")
        self.assertIsNone(self.part(held={"2026-10-06"})["leads"])


class Page(unittest.TestCase):
    def test_the_page_reads_it(self):
        got = subprocess.run(["node", str(ROOT / "tests" / "js" / "by-now.mjs")], capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr + got.stdout)

    def test_live_mode_has_one_place_per_answer(self):
        js = ROOT / "skald" / "webapp" / "js" / "tabs"
        summary = (js / "ov-summary.js").read_text()
        self.assertIn('if (isLive(s)) return today(m, s, o);', summary)
        for gone in ("rightNow", "leadsToday", "realtimeBlock", "thisHour"):
            self.assertNotIn(gone, summary)
        today = (js / "ov-today.js").read_text() + (js / "ov-today-cards.js").read_text()
        self.assertEqual(today.count('"Pause live"'), 1, "one Pause for the whole page")
        self.assertEqual(today.count('"Newest visits"'), 1)
        self.assertIn("openNewest", today, "a newest visit opens the visitor drawer")
        css = (ROOT / "skald" / "webapp" / "css" / "today.css").read_text()
        self.assertIn("@media (prefers-reduced-motion: no-preference)", css)
        motion = css.split("@media (prefers-reduced-motion: no-preference)")[1].split("@keyframes")[0]
        self.assertNotIn("animation", css.split("@media (prefers-reduced-motion: no-preference)")[0],
                         "every animation sits under no-preference")
        self.assertIn("td-ping", motion)
        self.assertIn('href="../_app/css/today.css"', (ROOT / "skald" / "webapp" / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()
