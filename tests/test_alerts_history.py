"""Citation and crawler alerts (alerts_history.py) and their second count
(audit_alerts.py): the first citation from an assistant and of a page, visits
from AI answers against the same weekday's median, a crawler gone silent.
Whole days only; visits and requests never mixed. Real history files, made-up
paths and example.com hosts."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import alerts, alerts_history as ah, audit_alerts  # noqa: E402
from skald.store import History  # noqa: E402
from skald.store_extras import record_milestones  # noqa: E402

UTC = timezone.utc
SITE = "example.com"
DAY = date(2026, 10, 11)                       # the last whole day (a Sunday)
NOW = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
CFG = ah.settings({})


def at(d: date, hm: str = "14:05") -> str:
    return f"{d.isoformat()}T{hm}:00+00:00"


class Store:
    """A history file with whole days written row by row."""

    def __init__(self, folder: Path, span: int = 60, last: date = DAY):
        self.h = History(folder / "history.sqlite")
        for i in range(span):
            self.day(last - timedelta(days=i))
            self.extra(last - timedelta(days=i), "page_firsts", {})

    def day(self, d: date, state: str = "ok", breakdowns: int | None = 1) -> None:
        self.h.db.execute("DELETE FROM days WHERE site = ? AND day = ?", (SITE, d.isoformat()))
        self.h.db.execute(
            "INSERT INTO days (site, day, timezone, collected_at, verified, parsed, hits, "
            "other_hosts, cited_visits, partial_until, breakdowns) VALUES "
            "(?, ?, 'UTC', ?, ?, 0, 0, 0, 0, ?, ?)",
            (SITE, d.isoformat(), NOW.isoformat(), 0 if state == "withheld" else 1,
             f"{d.isoformat()}T23:00:00+00:00" if state == "partial" else None, breakdowns))

    def count(self, d: date, kind: str, name: str, n: int) -> None:
        self.h.db.execute("INSERT OR REPLACE INTO counts (site, day, kind, name, n) VALUES "
                          "(?, ?, ?, ?, ?)", (SITE, d.isoformat(), kind, name, n))

    def extra(self, d: date, kind: str, blob) -> None:
        self.h.db.execute("INSERT OR REPLACE INTO day_extras (site, day, kind, data) VALUES "
                          "(?, ?, ?, ?)", (SITE, d.isoformat(), kind, json.dumps(blob)))

    def cited(self, d: date, path: str, who: str, hm: str = "14:05", n: int = 1) -> None:
        """A visit from `who`'s citation landing on `path`, as collect keeps it."""
        got = self.h.db.execute("SELECT data FROM day_extras WHERE site = ? AND day = ? AND "
                                "kind = 'page_firsts'", (SITE, d.isoformat())).fetchone()
        firsts = json.loads(got[0]) if got else {}
        firsts.setdefault(path, {})[f"from_ai|{who}"] = [at(d, hm), who]
        self.extra(d, "page_firsts", firsts)
        record_milestones(self.h.db, SITE, firsts)
        for kind, name in (("cited_by", who), ("cited_page", path)):
            old = self.h.db.execute("SELECT n FROM counts WHERE site = ? AND day = ? AND kind = ? "
                                    "AND name = ?", (SITE, d.isoformat(), kind, name)).fetchone()
            self.count(d, kind, name, (old[0] if old else 0) + n)

    def crawl(self, d: date, **names) -> None:
        blob = {name.replace("_", "-"): {"group": group, "requests": n, "paths": {"/": n}}
                for name, (group, n) in names.items()}
        self.extra(d, "crawler_paths", blob)


def run(s: Store, cfg=CFG, day=DAY, tz=UTC):
    return ah.evaluate(cfg, s.h, SITE, day, tz)


def causes(got):
    return [(f["cause"], f["subject"]) for f in got["found"]]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.s = Store(self.dir)
        self.addCleanup(self.s.h.close)
        for i in range(60):                      # every day has its crawlers
            self.s.crawl(DAY - timedelta(days=i))

    def recheck(self, got):
        return audit_alerts.recheck(self.s.h.db, SITE, got)


class FirstCitation(Base):
    def test_a_new_assistant_and_a_new_page_fire_with_visits(self):
        self.s.cited(DAY - timedelta(days=10), "/b/", "chatgpt.com")
        self.s.cited(DAY, "/a/", "claude.ai", n=2)
        self.s.cited(DAY, "/b/", "chatgpt.com")
        got = run(self.s)
        self.assertEqual(causes(got), [("ai_first_citation", "claude.ai"),
                                       ("ai_first_cited_page", "/a/")])
        first = got["found"][0]
        self.assertEqual((first["figure"], first["unit"]), (2, "visits"))
        self.assertIn("14:05", first["detail"])
        self.assertIn("never the assistant's fetches", first["detail"])
        self.assertEqual(first["data"]["path"], "/a/")
        self.assertEqual(got["found"][1]["data"]["pages"][0]["visits"], 2)
        self.assertEqual(self.recheck(got), [])

    def test_an_earlier_count_or_spelling_means_not_a_first(self):
        self.s.count(DAY - timedelta(days=40), "cited_by", "perplexity.ai", 1)   # before firsts
        self.s.count(DAY - timedelta(days=40), "cited_page", "/c", 1)
        self.s.cited(DAY, "/c/", "perplexity.ai")
        self.assertEqual(run(self.s)["found"], [])

    def test_the_day_in_the_sites_zone(self):
        ny = ZoneInfo("America/New_York")
        self.s.cited(DAY + timedelta(days=1), "/a/", "claude.ai", hm="02:00")   # 22:00 on DAY
        self.assertEqual(causes(run(self.s, tz=ny))[0], ("ai_first_citation", "claude.ai"))
        self.assertEqual(run(self.s, tz=UTC)["found"], [])

    def test_waits_on_a_day_not_whole_and_on_a_young_history(self):
        self.s.cited(DAY, "/a/", "claude.ai")
        self.s.day(DAY, "withheld")
        got = run(self.s)
        self.assertEqual(got["found"], [])
        self.assertEqual(got["rules"]["first_citation"]["waiting_on"], [DAY.isoformat()])
        self.s.day(DAY)
        young = Store(self.dir / "young", span=10)
        self.addCleanup(young.h.close)
        young.cited(DAY, "/a/", "claude.ai")
        got = run(young)
        self.assertEqual(got["found"], [])
        self.assertEqual(got["rules"]["first_cited_page"]["state"], "waiting")
        self.assertIn("fewer than 28 days", got["rules"]["first_cited_page"]["why"])

    def test_many_pages_are_one_alert_and_the_audit_counts_them(self):
        self.s.cited(DAY - timedelta(days=3), "/old/", "chatgpt.com")
        for i in range(7):
            self.s.cited(DAY, f"/p{i}/", "chatgpt.com", hm=f"10:0{i}")
        got = run(self.s)
        self.assertEqual(causes(got), [("ai_first_cited_page", "pages")])
        self.assertEqual(got["found"][0]["figure"], 7)
        self.assertEqual(self.recheck(got), [])
        got["found"][0]["figure"] = 6
        self.assertTrue(any("7 recounted" in p for p in self.recheck(got)))

    def test_the_audit_finds_a_figure_history_does_not_give(self):
        self.s.cited(DAY, "/a/", "claude.ai", n=2)
        got = run(self.s, cfg={**CFG, "first_cited_page": False})
        got["found"][0]["data"]["visits"] = 3
        self.assertEqual(len(self.recheck(got)), 1)
        # An earlier first the milestones lost: the audit's own road sees it.
        self.s.extra(DAY - timedelta(days=5), "page_firsts",
                     {"/z/": {"from_ai|claude.ai": [at(DAY - timedelta(days=5)), "claude.ai"]}})
        self.assertTrue(any("already had one" in p for p in self.recheck(got)))


class CitedVisits(Base):
    def visits(self, d: date, n: int) -> None:
        if n:
            self.s.count(d, "reader_source", "AI assistant", n)

    def weeks(self, *values):
        for w, n in enumerate(values, start=1):
            self.visits(DAY - timedelta(weeks=w), n)

    def test_rose_against_the_same_weekdays_median(self):
        self.weeks(8, 9, 10, 11, 12, 10)
        self.visits(DAY, 25)
        self.visits(DAY - timedelta(days=1), 500)            # another weekday: not looked at
        got = run(self.s)
        self.assertEqual(causes(got), [("ai_cited_visits", "rose")])
        f = got["found"][0]
        self.assertEqual((f["figure"], f["threshold"], f["unit"]), (25, 20.0, "visits"))
        self.assertIn("Usual for a Sunday: 10", f["detail"])
        self.assertIn("at least 2 times the usual and at least 10 visits", f["detail"])
        self.assertIn("bot and AI fetcher requests are never in this figure", f["detail"])
        self.assertEqual(self.recheck(got), [])
        f["data"]["weeks"][0]["visits"] = 99
        self.assertTrue(self.recheck(got))

    def test_fell_too_few_and_steady(self):
        self.weeks(10, 10, 12, 10, 9, 11)
        self.visits(DAY, 5)
        self.assertEqual(causes(run(self.s)), [("ai_cited_visits", "fell")])
        self.assertEqual(self.recheck(run(self.s)), [])
        self.visits(DAY, 8)
        got = run(self.s)
        self.assertEqual((got["found"], got["rules"]["cited_visits"]["verdict"]), ([], "steady"))

    def test_minimum_volume(self):
        self.weeks(3, 2, 4, 3, 1, 3)
        self.visits(DAY, 9)                                   # 3x the usual, under 10
        got = run(self.s)
        self.assertEqual((got["found"], got["rules"]["cited_visits"]["verdict"]),
                         ([], ah.TOO_FEW))
        self.visits(DAY, 10)                                  # at the minimum: rose
        self.assertEqual(causes(run(self.s)), [("ai_cited_visits", "rose")])
        self.s.h.db.execute("DELETE FROM counts WHERE kind = 'reader_source' AND day = ?",
                            (DAY.isoformat(),))
        self.weeks(12, 12, 12, 12, 12, 12)
        got = run(self.s)                                     # no row on a counted day: 0
        self.assertEqual(got["found"][0]["figure"], 0)

    def test_missing_weeks_are_left_out_or_make_it_wait(self):
        self.weeks(10, 10, 10, 10, 10, 10)
        self.visits(DAY, 30)
        self.s.day(DAY - timedelta(weeks=2), "withheld")
        self.s.day(DAY - timedelta(weeks=5), breakdowns=None)
        got = run(self.s)
        self.assertEqual(got["found"][0]["data"]["skipped"],
                         [(DAY - timedelta(weeks=2)).isoformat(),
                          (DAY - timedelta(weeks=5)).isoformat()])
        self.assertIn("not counted, so left out", got["found"][0]["detail"])
        self.assertEqual(self.recheck(got), [])
        self.s.day(DAY - timedelta(weeks=3), "partial")
        got = run(self.s)                                     # 3 of 6: fewer than 4
        self.assertEqual((got["found"], got["rules"]["cited_visits"]["state"]), ([], "waiting"))
        self.s.day(DAY, breakdowns=None)
        self.assertEqual(run(self.s)["rules"]["cited_visits"]["waiting_on"], [DAY.isoformat()])

    def test_weeks_from_the_config(self):
        cfg = ah.settings({"alerts": {"cited_weeks": 20, "cited_min_weeks": 9,
                                      "cited_spike_factor": "3", "cited_minimum": "x"}})
        self.assertEqual((cfg["cited_weeks"], cfg["cited_min_weeks"], cfg["cited_spike_factor"],
                          cfg["cited_minimum"]), (8, 8, 3, 10))


class CrawlerSilent(Base):
    def setUp(self):
        super().setUp()
        for i in range(60):
            d = DAY - timedelta(days=i)
            names = {"Googlebot": ("search_engines", 40)}
            if i >= 7 and i % 2:                             # GPTBot: every other day, then none
                names["GPTBot"] = ("answer_engines", 3)
            if i in (20, 30):                                 # ClaudeBot: twice, too rarely
                names["ClaudeBot"] = ("answer_engines", 5)
            if i >= 7:
                names["UptimeRobot"] = ("bots", 9)            # not a crawler of ours
            self.s.crawl(d, **names)

    def test_a_regular_crawler_gone_quiet_fires_in_requests(self):
        got = run(self.s)
        self.assertEqual(causes(got), [("crawler_silent", "GPTBot")])
        f = got["found"][0]
        self.assertEqual((f["unit"], f["data"]["active_days"], f["data"]["requests"]),
                         ("requests", 14, 42))
        self.assertIn("Requests, not visits", f["detail"])
        self.assertEqual(f["data"]["last_seen"], (DAY - timedelta(days=7)).isoformat())
        self.assertEqual(self.recheck(got), [])
        f["data"]["requests"] = 41
        self.assertTrue(self.recheck(got))

    def test_a_withheld_day_or_a_missing_blob_waits(self):
        self.s.day(DAY - timedelta(days=3), "withheld")
        got = run(self.s)
        self.assertEqual((got["found"], got["rules"]["crawler_silent"]["state"]), ([], "waiting"))
        self.s.day(DAY - timedelta(days=3))
        self.s.h.db.execute("DELETE FROM day_extras WHERE kind = 'crawler_paths' AND day = ?",
                            ((DAY - timedelta(days=20)).isoformat(),))
        self.assertEqual(run(self.s)["rules"]["crawler_silent"]["waiting_on"],
                         [(DAY - timedelta(days=20)).isoformat()])

    def test_off_and_days_from_the_config(self):
        self.assertEqual(run(self.s, cfg={**CFG, "crawler_silent": False})["found"], [])
        cfg = ah.settings({"alerts": {"silent_days": 10}})
        self.assertEqual(run(self.s, cfg=cfg)["found"], [])   # seen 7 days ago


class ThroughTheMachinery(unittest.TestCase):
    """Opened once, mailed once with its unit, queued as alert.opened, shown
    in alerts.json, rechecked by run-daily's recount."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.s = Store(self.dir)
        self.s.cited(DAY, "/a/", "claude.ai", n=2)
        self.s.h.db.commit()
        self.s.h.close()
        alerts.state_path(self.dir).write_text(json.dumps({"known_names": []}))
        self.sent = []

    def ctx(self, today=None):
        @contextmanager
        def hist():
            h = History(self.dir / "history.sqlite")
            try:
                yield h
            finally:
                h.close()
        return SimpleNamespace(config={"alerts": {"enabled": True, "first_cited_page": False}},
                               live_dir=self.dir, now=NOW, tz=UTC, site=SITE,
                               args=SimpleNamespace(today=today), history=hist,
                               db_path=self.dir / "history.sqlite", out=lambda *a: None,
                               err=lambda *a: None)

    def send(self, config, subject, text, now):
        self.sent.append((subject, text))

    def signals(self):
        return {"minutes": {}, "beats": [], "newest": NOW, "since": NOW - timedelta(hours=6)}

    def test_end_to_end(self):
        with mock.patch("skald.conversions.outgoing.notify", return_value=1) as hook, \
                mock.patch.object(ah, "evaluate", wraps=ah.evaluate) as ev:
            alerts.run(self.ctx(), None, self.signals(), self.send)
            alerts.run(self.ctx(), None, self.signals(), self.send)
        self.assertEqual(ev.call_count, 1)                    # once per last whole day
        self.assertEqual([s for s, _ in self.sent],
                         ["ALERT: First visit ever from a citation in claude.ai"])
        self.assertIn("Figure: 2 visits", self.sent[0][1])
        opened = [c[0] for c in hook.call_args_list if c[0][3] == "alert.opened"]
        self.assertEqual(len(opened), 1)
        body = opened[0][5]
        self.assertEqual(set(body), {"event", "site", "alert", "text", "figures", "at"})
        self.assertEqual((body["site"], body["alert"]["cause"], body["figures"]["unit"],
                          body["figures"]["figure"]), (SITE, "ai_first_citation", "visits", 2))
        self.assertTrue(body["text"].startswith("[example.com] First visit ever"))
        got = alerts.build(SimpleNamespace(config=self.ctx().config, live_dir=self.dir))
        self.assertEqual(got["open"][0]["unit"], "visits")
        self.assertEqual(got["history"]["rules"]["first_citation"]["found"], 1)
        self.assertIn("ai_cited_visits", [r["cause"] for r in got["rules"]])
        # run-daily's recount: matches; a doctored figure does not.
        self.assertTrue(audit_alerts.set_up(self.ctx()))
        self.assertEqual(audit_alerts.daily(self.ctx(), DAY), [])
        state = json.loads(alerts.state_path(self.dir).read_text())
        state["history"]["found"][0]["data"]["at"] = at(DAY, "09:00")
        alerts.state_path(self.dir).write_text(json.dumps(state))
        self.assertEqual(len(audit_alerts.daily(self.ctx(), DAY)), 1)

    def test_a_replay_sends_nothing_and_no_state_means_no_recount(self):
        with mock.patch("skald.conversions.outgoing.notify") as hook:
            alerts.run(self.ctx(today="2026-10-12"), None, self.signals(), self.send)
        self.assertEqual((self.sent, hook.call_count), ([], 0))
        alerts.state_path(self.dir).unlink()
        self.assertIsNone(audit_alerts.daily(self.ctx(), DAY))


if __name__ == "__main__":
    unittest.main()
