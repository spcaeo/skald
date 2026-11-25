"""SKALD-60: a security item is closed only when what would show it gone was read.

Exposures come from today so far (the live snapshot) and the last whole day (run-daily
stores yesterday about 07:15 in the site's zone). Between local midnight and that run,
yesterday is not stored: an exposure seen only yesterday used to close at 00:00, so the
01:00 summary missed it, and it came back after run-daily. Now it stays open until the
whole day is stored, and closes then if the day does not have it. Held the same: a withheld
day, a withheld live count, no stack check to read (advisories). run-daily reads the saved
live snapshot when it is today's, so an item seen only today does not close at 07:15.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import live, security_notify as sn, stack, summary_mail  # noqa: E402

SITE = "example.com"
NY = ZoneInfo("America/New_York")
RULES = {"exposure_rule": 2}
ENV = {"host": "example.com", "path": "/.env.production", "status": "200", "size": 1873,
       "verdict": "possible", "category": "secrets"}
SQL = {"host": "example.com", "path": "/backup.sql", "status": "200", "size": 52000,
       "verdict": "possible", "category": "dumps"}
UPDATE = {"advisory": "php-2026-10-21", "product": "php", "host": "example.com",
          "version": "8.3.10", "state": "update_needed"}


def blob(*rows) -> dict:
    return {"rules": RULES, "exposure": {"rows": list(rows)}}


def snap(day: str, *rows, state: str = "ok") -> dict:
    return {"version": live.LIVE_VERSION, "site": SITE, "day": day, "state": state,
            "extras": {"security": blob(*rows)}}


def at(text: str) -> datetime:
    """A New York wall-clock time, as the runs see it."""
    return datetime.fromisoformat(text).replace(tzinfo=NY)


class History:
    """What alerts_security._whole reads: the days table and the security day kind."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE days (site TEXT, day TEXT, verified INTEGER, "
                        "partial_from TEXT, partial_until TEXT)")
        self.db.execute("CREATE TABLE day_extras (site TEXT, day TEXT, kind TEXT, data TEXT)")

    def store(self, day: str, *rows, verified: bool = True, partial: str | None = None) -> None:
        self.db.execute("INSERT INTO days VALUES (?, ?, ?, ?, NULL)", (SITE, day, int(verified), partial))
        self.db.execute("INSERT INTO day_extras VALUES (?, ?, 'security', ?)",
                        (SITE, day, json.dumps(blob(*rows))))


class Midnight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.history = History()
        self.config = {"access": {"mode": "sessions"},
                       "_resolved": {"history_db": str(self.dir / "history.sqlite")},
                       "dashboard": {"url": "https://stats.example.com/traffic/example.com/"}}
        self.errors = []
        self.said = []
        self.advisories([])

    def tearDown(self):
        self.tmp.cleanup()

    def advisories(self, matches) -> None:
        stack.path_for({}, self.dir, SITE).write_text(json.dumps(
            {"days": {"2026-11-24": {"read": {"matches": matches}}}}))

    def ctx(self, when: datetime):
        @contextmanager
        def history():
            yield self.history
        return SimpleNamespace(config=self.config, live_dir=self.dir, site=SITE, now=when, tz=NY,
                               history=history, err=self.errors.append, out=self.said.append)

    def live_run(self, when: str, s: dict) -> None:
        sn.live(self.ctx(at(when)), s)
        self.assertEqual(self.errors, [])

    def daily_run(self, when: str) -> None:
        sn.daily(self.ctx(at(when)))
        self.assertEqual(self.errors, [])

    def open_paths(self) -> list[str]:
        db = sqlite3.connect(self.dir / "accounts.sqlite")
        try:
            return sorted(t.split(": ", 1)[1].split(" answered")[0]
                          for t, in db.execute("SELECT title FROM security_items WHERE "
                                               "closed_at IS NULL AND kind = 'exposure'"))
        finally:
            db.close()

    def summary(self) -> list[str]:
        """What the 01:00 summary would list for the site (summary_mail.security_part)."""
        db = sqlite3.connect(self.dir / "accounts.sqlite")
        try:
            return [p["title"] for p in summary_mail.security_part(db, SITE, self.config)]
        finally:
            db.close()

    def test_seen_yesterday_stays_open_until_yesterday_is_stored(self):
        self.history.store("2026-11-23")
        self.live_run("2026-11-24T15:00", snap("2026-11-24", ENV))
        self.assertEqual(self.open_paths(), ["example.com/.env.production"])
        # 00:30, before run-daily: today has no such line yet and 24 Nov is not stored.
        self.live_run("2026-11-25T00:30", snap("2026-11-25"))
        self.assertEqual(self.open_paths(), ["example.com/.env.production"],
                         "not closed at midnight: nothing yet shows it gone")
        self.assertEqual(len(self.summary()), 1, "the 01:00 summary lists yesterday's item")
        # run-daily stores 24 Nov with the line: still open, and every run after it agrees.
        self.history.store("2026-11-24", ENV)
        self.daily_run("2026-11-25T07:20")
        self.live_run("2026-11-25T09:00", snap("2026-11-25"))
        self.assertEqual(self.open_paths(), ["example.com/.env.production"])
        # Fixed on 24 Nov afternoon: 25 Nov is stored without it, and only then it closes.
        self.live_run("2026-11-26T00:30", snap("2026-11-26"))
        self.assertEqual(self.open_paths(), ["example.com/.env.production"], "held again")
        self.history.store("2026-11-25")
        self.daily_run("2026-11-26T07:20")
        self.assertEqual(self.open_paths(), [], "the whole day has it gone: closed")
        self.live_run("2026-11-26T09:00", snap("2026-11-26"))
        self.assertEqual(self.open_paths(), [])
        self.assertEqual(self.summary(), [])

    def test_gone_when_both_sources_are_read(self):
        self.history.store("2026-11-23", ENV)
        self.live_run("2026-11-24T10:00", snap("2026-11-24", SQL))
        self.assertEqual(self.open_paths(), ["example.com/.env.production", "example.com/backup.sql"])
        self.live_run("2026-11-24T11:00", snap("2026-11-24", SQL))
        self.assertEqual(self.open_paths(), ["example.com/.env.production", "example.com/backup.sql"])
        self.history.db.execute("DELETE FROM day_extras")
        self.history.store("2026-11-23")
        self.live_run("2026-11-24T12:00", snap("2026-11-24", SQL))
        self.assertEqual(self.open_paths(), ["example.com/backup.sql"],
                         "today and the whole day both read: what neither has closes")

    def test_a_withheld_day_or_count_closes_nothing(self):
        self.history.store("2026-11-23", ENV)
        self.live_run("2026-11-24T10:00", snap("2026-11-24"))
        self.history.store("2026-11-24", verified=False)
        self.live_run("2026-11-25T10:00", snap("2026-11-25"))
        self.assertEqual(self.open_paths(), ["example.com/.env.production"], "24 Nov withheld")
        self.daily_run("2026-11-25T10:05")
        self.assertEqual(self.open_paths(), ["example.com/.env.production"])
        self.assertIn("kept open", self.said[-1])
        self.history.db.execute("DELETE FROM days WHERE day = '2026-11-24'")
        self.history.store("2026-11-24")
        self.live_run("2026-11-25T11:00", snap("2026-11-25", state="withheld"))
        self.assertEqual(self.open_paths(), ["example.com/.env.production"],
                         "a live count that does not reconcile shows nothing gone")
        sn.live(self.ctx(at("2026-11-25T11:02")), None)
        self.assertEqual(self.open_paths(), ["example.com/.env.production"], "no live count at all")
        self.live_run("2026-11-25T11:05", {**snap("2026-11-25"), "state": "empty", "extras": {}})
        self.assertEqual(self.open_paths(), [], "no line today yet is a true nothing: closed")

    def test_a_partial_day_is_read(self):
        """A quiet site's day is partial when its first or last hour has no request: still
        read, so its items neither close at midnight nor stay open for ever."""
        self.history.store("2026-11-23")
        self.live_run("2026-11-24T10:00", snap("2026-11-24", ENV))
        self.history.store("2026-11-24", ENV, partial="2026-11-24T06:10:00Z")
        self.live_run("2026-11-25T10:00", snap("2026-11-25"))
        self.assertEqual(self.open_paths(), ["example.com/.env.production"], "the partial day has it")
        self.history.store("2026-11-25", partial="2026-11-25T06:10:00Z")
        self.live_run("2026-11-26T10:00", snap("2026-11-26"))
        self.assertEqual(self.open_paths(), [], "the partial day lacks it: closed")

    def test_run_daily_keeps_what_today_has(self):
        self.history.store("2026-11-24")
        self.live_run("2026-11-25T06:00", snap("2026-11-25", SQL))
        self.assertEqual(self.open_paths(), ["example.com/backup.sql"])
        live.save(live.path_for(self.dir, SITE), snap("2026-11-25", SQL))
        self.daily_run("2026-11-25T07:20")
        self.assertEqual(self.open_paths(), ["example.com/backup.sql"],
                         "run-daily reads today's saved count: no close-and-reopen at 07:15")
        live.save(live.path_for(self.dir, SITE), snap("2026-11-25", state="withheld"))
        self.daily_run("2026-11-25T07:22")
        self.assertEqual(self.open_paths(), ["example.com/backup.sql"],
                         "today's saved count did not reconcile: nothing gone")
        live.save(live.path_for(self.dir, SITE), snap("2026-11-24", SQL))
        self.daily_run("2026-11-25T07:25")
        self.assertEqual(self.open_paths(), [],
                         "yesterday's snapshot is not today's: the whole day alone judges")

    def test_advisories_wait_for_a_stack_check(self):
        self.history.store("2026-11-24")
        self.advisories([UPDATE])
        self.live_run("2026-11-25T10:00", snap("2026-11-25"))
        self.assertEqual(len(self.summary()), 1)
        stack.path_for({}, self.dir, SITE).unlink()
        self.live_run("2026-11-25T10:05", snap("2026-11-25"))
        self.assertEqual(len(self.summary()), 1, "no stack check to read: the advisory stays")
        self.advisories([{**UPDATE, "version": "8.4.30", "state": "fixed"}])
        self.live_run("2026-11-25T10:10", snap("2026-11-25"))
        self.assertEqual(self.summary(), [], "the check says fixed: closed")


class RealRuns(unittest.TestCase):
    """The same on a real install: `collect` stores the days, live.build counts today, the
    leak of security_support (/.env.production, 5 Oct 04:00 New York) is the item."""

    def test_midnight_to_run_daily(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from security_support import day_lines, ln
        from support import Sandbox
        from skald.config import load_config
        from skald.store import History
        b = Sandbox(mail=False, tz="America/New_York")
        self.addCleanup(b.close)
        b.config.write_text(b.config.read_text().replace(
            "hosts: [example.com]", "hosts: [example.com, app.example.com]") + "access:\n  mode: sessions\n")
        b.log(day_lines() + [ln(datetime(2026, 10, 6, 15, tzinfo=timezone.utc), "203.0.113.5", "/")])
        config = load_config(b.config)
        config["_resolved"] = {"history_db": str(b.db)}
        errors = []

        def ctx(when):
            @contextmanager
            def history():
                h = History(b.db)
                try:
                    yield h
                finally:
                    h.close()
            return SimpleNamespace(config=config, live_dir=b.root, site=SITE, now=when, tz=NY,
                                   history=history, err=errors.append, out=lambda s: None)

        def live_run(when):
            sn.live(ctx(at(when)), live.build(config, SITE, NY, at(when), db_path=b.db))

        def closed():
            db = sqlite3.connect(b.root / "accounts.sqlite")
            try:
                return db.execute("SELECT closed_at FROM security_items WHERE kind = 'exposure'").fetchall()
            finally:
                db.close()

        live_run("2026-10-05T12:00")
        self.assertEqual(closed(), [(None,)])
        live_run("2026-10-06T00:30")
        self.assertEqual(closed(), [(None,)], "5 Oct not stored yet: open at 00:30")
        self.assertEqual(b.run("--today", "2026-10-06", "collect")[0], 0)
        sn.daily(ctx(at("2026-10-06T07:20")))
        live_run("2026-10-06T12:00")
        self.assertEqual(closed(), [(None,)], "5 Oct stored with the leak")
        live_run("2026-10-07T00:30")
        self.assertEqual(closed(), [(None,)], "6 Oct not stored yet: open at 00:30")
        self.assertEqual(b.run("--today", "2026-10-07", "collect")[0], 0)
        sn.daily(ctx(at("2026-10-07T07:20")))
        self.assertEqual(closed(), [("2026-10-07T11:20:00Z",)], "6 Oct stored without it: closed")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
