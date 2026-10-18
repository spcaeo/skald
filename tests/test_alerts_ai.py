"""AI alerts (issue #5, alerts_ai.py): an assistant starts or stops reading a
page, and AI answers start or stop sending people. Whole days only: a
withheld, missing or not-recorded day makes a rule wait, never fire. The
rules read figures already checked twice (crawler_paths, ai_likely) and say
so. Paths and hosts are made up (example.com)."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import alerts, alerts_ai  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 11)                     # the last whole day
NOW = datetime(2026, 10, 12, 15, 0, tzinfo=UTC)
SITE = "example.com"


def crawl(**names) -> dict:
    """A crawler_paths blob: crawl(GPTBot={"/a/": 2})."""
    out = {}
    for name, paths in names.items():
        name = name.replace("_", "-")
        out[name] = {"group": "answer_engines", "requests": sum(paths.values()),
                     "paths": dict(paths)}
    return out


class FakeHistory:
    """daily() and extras() over a dict of days: {date: {"state", kinds...}}."""

    def __init__(self, days: dict, first: date | None = None):
        self.days = days
        self.first = first or min(days)

    def daily(self, site, first, last):
        out, d = [], first
        while d <= last:
            got = self.days.get(d)
            state = got["state"] if got else ("before" if d < self.first else "missing")
            out.append({"day": d, "state": state})
            d += timedelta(days=1)
        return out

    def extras(self, site, first, last, kinds):
        out = {}
        for d, got in self.days.items():
            if first <= d <= last:
                blobs = {k: got[k] for k in kinds if k in got}
                if blobs:
                    out[d.isoformat()] = blobs
        return out


def history(span=40, base=None, last=None, likely=None, state=None, pages=None):
    """`span` ok days ending DAY: `base` crawl blob on the earlier days, `last`
    on DAY; likely: {day offset: by_assistant}; state: {offset: state}."""
    days = {}
    for i in range(span):
        d = DAY - timedelta(days=i)
        blob = (last if i == 0 else base) or {}
        by = (likely or {}).get(i, (likely or {}).get("rest", {}))
        days[d] = {"state": (state or {}).get(i, "ok"), "crawler_paths": blob,
                   "ai_likely": {"by_assistant": by, "likely": sum(by.values())},
                   "pages": pages if pages is not None else {
                       p: {"ai_asked": 0, "ai_training": 1}
                       for c in (last or {}).values() for p in c["paths"]}}
    return FakeHistory(days)


CFG = alerts_ai.settings({})


def run(h, cfg=CFG, day=DAY):
    return alerts_ai.evaluate(cfg, h, SITE, day)


def causes(review):
    return [(f["cause"], f["subject"]) for f in review["found"]]


class StartedReading(unittest.TestCase):
    def test_a_page_new_to_its_owner_fires_and_names_the_numbers(self):
        h = history(base=crawl(GPTBot={"/about/": 3}),
                    last=crawl(GPTBot={"/about/": 1, "/pricing/": 4, "/logo.png": 9}))
        got = run(h)
        self.assertEqual(causes(got), [("ai_started_reading", "OpenAI: /pricing/")])
        f = got["found"][0]
        self.assertEqual((f["figure"], f["threshold"]), (4, 0))
        self.assertIn("2026-10-11", f["detail"])
        self.assertIn("2026-09-13 to 2026-10-10", f["detail"])
        self.assertIn("checked twice", f["detail"])
        self.assertEqual(f["data"]["assistant"], "OpenAI")
        self.assertEqual(f["data"]["pages"], [{"path": "/pricing/", "n": 4}])

    def test_another_crawler_of_the_same_owner_counts_as_read(self):
        h = history(base=crawl(OAI_SearchBot={"/pricing/": 1}),
                    last=crawl(ChatGPT_User={"/pricing/": 2}))
        self.assertEqual(run(h)["found"], [])

    def test_a_path_not_answered_as_a_page_is_left_out(self):
        h = history(base=crawl(ClaudeBot={"/a/": 1}), last=crawl(ClaudeBot={"/gone/": 2}),
                    pages={"/a/": {"ai_training": 1}})
        self.assertEqual(run(h)["found"], [])

    def test_a_withheld_or_missing_day_makes_it_wait(self):
        for state in ("withheld", "partial"):
            h = history(base=crawl(GPTBot={"/a/": 1}), last=crawl(GPTBot={"/b/": 1}),
                        state={12: state})
            got = run(h)
            self.assertEqual(got["found"], [])
            rule = got["rules"]["started_reading"]
            self.assertEqual((rule["state"], rule["waiting_on"]), ("waiting", ["2026-09-29"]))
        short = history(span=10, base=crawl(GPTBot={"/a/": 1}), last=crawl(GPTBot={"/b/": 1}))
        self.assertEqual(run(short)["rules"]["started_reading"]["state"], "waiting")
        self.assertEqual(run(short)["found"], [])

    def test_hidden_paths_mean_not_judged(self):
        h = history(base=crawl(GPTBot={"/a/": 1, "(all others)": 5}),
                    last=crawl(GPTBot={"/b/": 1}))
        got = run(h)
        self.assertEqual(got["found"], [])
        self.assertEqual(got["rules"]["started_reading"]["unjudged"], ["OpenAI"])

    def test_many_pages_are_one_alert(self):
        pages = {f"/p{i}/": 1 for i in range(8)}
        h = history(base=crawl(ClaudeBot={"/a/": 1}), last=crawl(ClaudeBot=pages))
        got = run(h)
        self.assertEqual(causes(got), [("ai_started_reading", "Anthropic: pages")])
        self.assertEqual(got["found"][0]["figure"], 8)
        self.assertIn("/p0/", got["found"][0]["detail"])

    def test_off_and_thresholds_from_the_config(self):
        h = history(base=crawl(GPTBot={"/a/": 1}), last=crawl(GPTBot={"/b/": 1}))
        off = alerts_ai.settings({"alerts": {"ai": {"started_reading": False}}})
        self.assertEqual(run(h, off)["found"], [])
        self.assertEqual(run(h, off)["rules"]["started_reading"]["state"], "off")
        short = alerts_ai.settings({"alerts": {"ai": {"started_days": "7", "max_pages": "x"}}})
        self.assertEqual((short["started_days"], short["max_pages"]), (7, 5))
        # The flat keys the standard-library config reader takes win over the mapping.
        flat = alerts_ai.settings({"alerts": {"ai_started_reading": "false",
                                              "ai": {"started_reading": True}}})
        self.assertFalse(flat["started_reading"])


class StoppedReading(unittest.TestCase):
    def days(self, weeks_with: set, recent=False):
        days = {}
        for i in range(40):
            d = DAY - timedelta(days=i)
            week = i // 7                    # 0 = the last 7 days, 1..4 = the 4 weeks before
            on = (week == 0 and recent) or (week in weeks_with and i % 7 == 3)
            blob = crawl(ClaudeBot={"/docs/": 2, "/a/": 1}) if on else crawl(ClaudeBot={"/a/": 1})
            days[d] = {"state": "ok", "crawler_paths": blob, "ai_likely": {"by_assistant": {}},
                       "pages": {"/a/": {"ai_training": 1}}}
        return FakeHistory(days)

    def test_read_three_of_four_weeks_then_nothing_for_seven_days(self):
        got = run(self.days({1, 2, 4}))
        self.assertEqual(causes(got), [("ai_stopped_reading", "Anthropic: /docs/")])
        f = got["found"][0]
        self.assertEqual((f["figure"], f["threshold"]), (3, 3))
        self.assertIn("2026-10-05 to 2026-10-11", f["detail"])

    def test_not_when_read_recently_or_too_rarely(self):
        self.assertEqual(run(self.days({1, 2, 3}, recent=True))["found"], [])
        self.assertEqual(run(self.days({2, 4}))["found"], [])

    def test_hidden_recent_paths_mean_not_judged(self):
        h = self.days({1, 2, 3, 4})
        h.days[DAY]["crawler_paths"]["ClaudeBot"]["paths"]["(all others)"] = 3
        got = run(h)
        self.assertEqual(got["found"], [])
        self.assertEqual(got["rules"]["stopped_reading"]["unjudged"], ["Anthropic"])


class SendingPeople(unittest.TestCase):
    def test_jumped_vanished_and_too_few_to_judge(self):
        h = history(base=crawl(GPTBot={"/a/": 1}), last=crawl(GPTBot={"/a/": 1}),
                    likely={0: {"chatgpt.com": 20, "perplexity.ai": 2},
                            "rest": {"chatgpt.com": 5, "claude.ai": 6, "(more than one)": 3}})
        got = run(h)
        self.assertEqual(sorted(causes(got)), [("ai_sending_people", "chatgpt.com: jumped"),
                                               ("ai_sending_people", "claude.ai: vanished")])
        verdicts = {r["assistant"]: r["verdict"] for r in got["rules"]["sending_people"]["assistants"]}
        self.assertEqual(verdicts, {"chatgpt.com": "jumped", "claude.ai": "vanished",
                                    "perplexity.ai": "too few to judge"})
        jumped = next(f for f in got["found"] if f["subject"] == "chatgpt.com: jumped")
        self.assertEqual((jumped["figure"], jumped["threshold"]), (20, 15.0))
        self.assertIn("likely", jumped["detail"].lower())

    def test_steady_and_a_day_not_recorded_waits(self):
        h = history(likely={0: {"chatgpt.com": 6}, "rest": {"chatgpt.com": 5}})
        self.assertEqual(run(h)["found"], [])
        h.days[DAY - timedelta(days=3)]["ai_likely"] = None
        got = run(h)
        self.assertEqual(got["rules"]["sending_people"]["state"], "waiting")
        self.assertEqual(got["rules"]["sending_people"]["waiting_on"], ["2026-10-08"])


class Weekly(unittest.TestCase):
    def test_the_week_lists_changes_and_respects_the_mail_switch(self):
        h = history(span=50, base=crawl(GPTBot={"/a/": 1}), last=crawl(GPTBot={"/new/": 3}))
        on = {"alerts": {"enabled": True, "mail": True}}
        text, html = alerts_ai.weekly(on, h, SITE, DAY - timedelta(days=6), DAY)
        self.assertIn("AI READING CHANGES", text)
        self.assertIn("OpenAI started reading /new/", text)
        self.assertIn("checked twice", text)
        self.assertIn("/new/", html)
        for off in ({"alerts": {"enabled": True, "mail": False}},
                    {"alerts": {"enabled": False, "mail": True}},
                    {"alerts": {"enabled": True, "mail": True, "ai": {"weekly_mail": False}}}):
            self.assertEqual(alerts_ai.weekly(off, h, SITE, DAY - timedelta(days=6), DAY),
                             ("", ""))


class WeeklyMail(unittest.TestCase):
    def test_the_section_is_in_the_weekly_mail_only_with_alert_mail_on(self):
        import os
        import re

        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from support import SECRETS, Sandbox, day_lines, totals_for

        from skald import mailer
        from skald.config import load_config
        from skald.store import History
        box = Sandbox()
        history = History(box.db)
        try:
            anchor = date(2026, 10, 5)
            for i in range(14):
                d = anchor - timedelta(days=i)
                history.record(SITE, d, totals_for(day_lines(d, 3)), "UTC", [])
            now = datetime(2026, 10, 6, 9, tzinfo=UTC)
            plain = box.config.read_text()

            def html(extra):
                box.config.write_text(plain + extra)
                with mock.patch.dict(os.environ, SECRETS):
                    msg = mailer.build("weekly", load_config(box.config), history, UTC, now)
                return (msg.get_body(("plain",)).get_content(),
                        re.sub(r"\s+", " ", msg.get_body(("html",)).get_content()))
            text, page = html("alerts:\n  enabled: true\n  mail: true\n")
            self.assertIn("AI reading changes", page)
            self.assertIn("waiting for whole days", page)       # 14 days: not enough
            self.assertIn("AI READING CHANGES", text)
            text, page = html("alerts:\n  enabled: true\n  mail: false\n")
            self.assertNotIn("AI reading changes", page)
            self.assertNotIn("AI READING CHANGES", text)
        finally:
            history.close()
            box.close()


class ThroughTheAlertMachinery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.sent = []
        self.h = history(base=crawl(GPTBot={"/a/": 1}), last=crawl(GPTBot={"/new/": 3}))
        alerts.state_path(self.dir).write_text(json.dumps({"known_names": []}))

    def ctx(self, extra=None, today=None):
        @contextmanager
        def hist():
            yield self.h
        config = {"alerts": {"enabled": True, **(extra or {})}}
        return SimpleNamespace(config=config, live_dir=self.dir, now=NOW, tz=UTC, site=SITE,
                               args=SimpleNamespace(today=today), history=hist,
                               db_path=self.dir / "history.sqlite", out=lambda *a: None,
                               err=lambda *a: None)

    def send(self, config, subject, text, now):
        self.sent.append(subject)

    def signals(self):
        return {"minutes": {}, "beats": [], "newest": NOW, "since": NOW - timedelta(hours=6)}

    def test_opened_once_mailed_once_shown_and_sent_to_webhooks(self):
        with mock.patch("skald.conversions.outgoing.notify", return_value=1) as hook, \
                mock.patch.object(alerts_ai, "evaluate", wraps=alerts_ai.evaluate) as ev:
            alerts.run(self.ctx(), None, self.signals(), self.send)
            alerts.run(self.ctx(), None, self.signals(), self.send)
        self.assertEqual(ev.call_count, 1)          # once per last whole day
        self.assertEqual(self.sent, ["ALERT: OpenAI started reading /new/"])
        # One ai.reading_changed and one alert.opened, each once.
        self.assertEqual(sorted(c[0][3] for c in hook.call_args_list),
                         ["ai.reading_changed", "alert.opened"])
        call = next(c for c in hook.call_args_list if c[0][3] == "ai.reading_changed")
        event, ref, body = call[0][3:6]
        self.assertEqual(event, "ai.reading_changed")
        self.assertEqual((body["cause"], body["assistant"], body["day"]),
                         ("ai_started_reading", "OpenAI", "2026-10-11"))
        self.assertEqual(body["pages"], [{"path": "/new/", "n": 3}])
        got = alerts.build(SimpleNamespace(config=self.ctx().config, live_dir=self.dir))
        self.assertEqual([a["cause"] for a in got["open"]], ["ai_started_reading"])
        self.assertEqual(got["open"][0]["severity"], "low")
        self.assertIn("ai_stopped_reading", [r["cause"] for r in got["rules"]])
        self.assertEqual(got["ai"]["day"], "2026-10-11")
        self.assertEqual(got["ai"]["rules"]["started_reading"]["state"], "ok")

    def test_a_replay_sends_nothing(self):
        with mock.patch("skald.conversions.outgoing.notify") as hook:
            alerts.run(self.ctx(today="2026-10-12"), None, self.signals(), self.send)
        self.assertEqual((self.sent, hook.call_count), ([], 0))

    def test_a_broken_ai_check_never_stops_the_other_alerts(self):
        errors = []
        ctx = self.ctx()
        ctx.err = errors.append
        sig = self.signals()
        sig["newest"] = NOW - timedelta(minutes=30)
        with mock.patch.object(alerts_ai, "evaluate", side_effect=RuntimeError("boom")):
            alerts.run(ctx, None, sig, self.send)
        self.assertEqual(self.sent, ["ALERT: No log line for 30 minutes"])
        self.assertTrue(any("boom" in e for e in errors))


class OutgoingEvent(unittest.TestCase):
    def test_queued_only_for_webhooks_that_want_it(self):
        from skald.conversions import outgoing, store
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = {"integrations": {"allow_private_urls": True}}
            self.assertIn("ai.reading_changed", outgoing.EVENTS)
            self.assertEqual(outgoing.notify(config, folder, SITE, "ai.reading_changed", "x",
                                             {"cause": "c"}, NOW), 0)     # no file: nothing
            db = store.connect(folder / "conversions.sqlite")
            try:
                outgoing.add(db, config, folder, SITE, "http://127.0.0.1:9/a",
                             ["ai.reading_changed"], "owner@example.com", NOW)
                outgoing.add(db, config, folder, SITE, "http://127.0.0.1:9/b",
                             ["lead.won"], "owner@example.com", NOW)
            finally:
                db.close()
            body = {"cause": "ai_started_reading", "assistant": "OpenAI"}
            self.assertEqual(outgoing.notify(config, folder, SITE, "ai.reading_changed", "a1",
                                             body, NOW), 1)
            self.assertEqual(outgoing.notify(config, folder, SITE, "ai.reading_changed", "a1",
                                             body, NOW), 0)               # once per alert
            db = store.connect(folder / "conversions.sqlite")
            try:
                rows = db.execute("SELECT event, ref, body FROM outbox").fetchall()
            finally:
                db.close()
            self.assertEqual([(r[0], r[1]) for r in rows], [("ai.reading_changed", "a1")])
            sent = json.loads(rows[0][2])
            self.assertEqual((sent["event"], sent["site"], sent["assistant"]),
                             ("ai.reading_changed", SITE, "OpenAI"))


if __name__ == "__main__":
    unittest.main()
