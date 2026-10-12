"""Alerts by email (release 2, batch 4): each rule fires on its condition and
not below it; one mail per alert, repeats to the daily digest, a resolved
line for outages; never mailed from a replay, another host or when off."""
from __future__ import annotations

import json
import os
import sys
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import alerts  # noqa: E402
from skald.classify import Group  # noqa: E402

from support import CHROME, SECRETS, UTC, Sandbox, line  # noqa: E402

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)
CFG = alerts.settings({"alerts": {"enabled": True}})


def signals(minutes=None, beats=(), newest=NOW, since=NOW - timedelta(hours=6)):
    return {"minutes": minutes or {}, "beats": list(beats), "newest": newest, "since": since}


def minute(ago: int) -> int:
    return int((NOW - timedelta(minutes=ago)).timestamp()) // 60


class NoHistory:
    def daily(self, site, first, last):
        return []


OK_SNAP = {"state": "ok", "ai": {}, "search": {}}


def found(sig, snap=OK_SNAP, known=(), history=None, heartbeat=False):
    return alerts.check(CFG, sig, snap, history or NoHistory(), "example.com", UTC, NOW,
                        set(known), heartbeat)


class TestRules(unittest.TestCase):
    def test_site_down_after_two_missed_beats(self):
        def causes(beats, heartbeat=True):
            return [f["cause"] for f in found(signals(beats=beats), heartbeat=heartbeat)]
        beats = [(NOW - timedelta(minutes=m), True) for m in (25, 20, 15, 10)]
        self.assertEqual(causes(beats), [])
        beats = [(NOW - timedelta(minutes=m), True) for m in (30, 25, 20, 15)]
        self.assertEqual(causes(beats), ["site_down"])
        failing = beats + [(NOW - timedelta(minutes=9), False), (NOW - timedelta(minutes=4), False)]
        self.assertEqual(causes(failing), ["site_down"])
        self.assertEqual(causes([]), ["site_down"])
        self.assertEqual(causes(beats, heartbeat=False), [])

    def test_logging_stopped(self):
        got = found(signals(newest=NOW - timedelta(minutes=16)))
        self.assertEqual([f["cause"] for f in got], ["logging_stopped"])
        self.assertEqual(found(signals(newest=NOW - timedelta(minutes=14))), [])

    def test_figure_rules_wait_for_a_reconciled_snapshot(self):
        sig = signals({minute(1): Counter({"all": 20, "5xx": 20})})
        self.assertEqual([f["cause"] for f in found(sig)], ["server_errors"])
        self.assertEqual(found(sig, snap={"state": "withheld"}), [])
        self.assertEqual(found(signals({minute(1): Counter({"all": 9, "5xx": 9})})), [])

    def test_crawler_burst_needs_share_and_volume(self):
        big = {minute(m): Counter({"all": 40, "name:meta-externalagent": 30}) for m in range(25)}
        got = found(signals(big), known=["meta-externalagent"])
        self.assertEqual([(f["cause"], f["subject"]) for f in got],
                         [("crawler_burst", "meta-externalagent")])
        small = {minute(1): Counter({"all": 100, "name:meta-externalagent": 90})}
        self.assertEqual(found(signals(small), known=["meta-externalagent"]), [])

    def test_404_surge_from_people(self):
        sig = signals({minute(5): Counter({"all": 30, "people_404": 12})})
        self.assertEqual([f["cause"] for f in found(sig)], ["not_found_surge"])
        self.assertEqual(found(signals({minute(5): Counter({"people_404": 9})})), [])

    def test_new_crawler_only_when_never_seen(self):
        snap = {"state": "ok", "ai": {"training": {"NewAIBot": 5}}, "search": {}}
        self.assertEqual([f["subject"] for f in found(signals(), snap=snap)], ["NewAIBot"])
        self.assertEqual(found(signals(), snap=snap, known=["NewAIBot"]), [])
        quiet = {"state": "ok", "ai": {"training": {"NewAIBot": 2}}, "search": {}}
        self.assertEqual(found(signals(), snap=quiet), [])

    def test_traffic_drop_only_on_whole_days_against_the_same_weekday(self):
        day = NOW.date() - timedelta(days=1)

        class History:
            def __init__(self, readers, state="ok"):
                self.readers, self.state = readers, state

            def daily(self, site, first, last):
                out = []
                d = first
                while d <= last:
                    r = self.readers.get(d)
                    out.append({"day": d, "state": self.state if r is not None else "missing",
                                "groups": {Group.PEOPLE: {"readers": r}}})
                    d += timedelta(days=1)
                return out

        weeks = {day - timedelta(weeks=w): 100 for w in range(1, 5)}
        cfg = CFG
        self.assertIsNotNone(alerts._traffic_drop(cfg, History({**weeks, day: 40}), "x", NOW.date()))
        self.assertIsNone(alerts._traffic_drop(cfg, History({**weeks, day: 60}), "x", NOW.date()))
        two = dict(list(weeks.items())[:2])
        self.assertIsNone(alerts._traffic_drop(cfg, History({**two, day: 10}), "x", NOW.date()))
        self.assertIsNone(alerts._traffic_drop(cfg, History({**weeks, day: 40}, "partial"),
                                               "x", NOW.date()))


class TestFatigue(unittest.TestCase):
    def finding(self, cause="site_down", subject=""):
        return alerts._finding(cause, subject, "t", "d", 1, 1)

    def test_one_mail_then_repeats_then_resolved(self):
        state = {}
        mail, done = alerts.apply(state, [self.finding()], NOW, CFG)
        self.assertEqual(len(mail), 1)
        mail[0]["mailed"], mail[0]["last_mailed_at"] = 1, NOW.isoformat()
        mail, done = alerts.apply(state, [self.finding()], NOW + timedelta(minutes=2), CFG)
        self.assertEqual((mail, state["alerts"][0]["repeats"]), ([], 1))
        mail, done = alerts.apply(state, [], NOW + timedelta(minutes=4), CFG)
        self.assertEqual([a["cause"] for a in done], ["site_down"])
        # Back within the cooldown: reopened, not mailed again.
        mail, done = alerts.apply(state, [self.finding()], NOW + timedelta(minutes=6), CFG)
        self.assertEqual((mail, len(state["alerts"])), ([], 1))
        self.assertIsNone(state["alerts"][0]["closed_at"])
        alerts.apply(state, [], NOW + timedelta(minutes=8), CFG)
        mail, _ = alerts.apply(state, [self.finding()], NOW + timedelta(hours=7), CFG)
        self.assertEqual(len(mail), 1)

    def test_each_subject_is_its_own_alert(self):
        state = {}
        mail, _ = alerts.apply(state, [self.finding("crawler_burst", "A"),
                                       self.finding("crawler_burst", "B")], NOW, CFG)
        self.assertEqual(len(mail), 2)


class TestRun(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.sent = []

    def tearDown(self):
        self.box.close()

    def ctx(self, extra: str = "", today=None):
        from skald import cli
        self.box.config.write_text(self.box.config.read_text() + extra)
        argv = ["--config", str(self.box.config)] + (["--today", today] if today else []) + ["live"]
        ctx = cli.Context(cli.parser().parse_args(argv))
        ctx.now = NOW
        ctx.out = ctx.err = lambda *a: None
        return ctx

    def send(self, config, subject, text, now):
        self.sent.append(subject)
        return None

    def burst(self):
        return signals({minute(1): Counter({"all": 30, "5xx": 30})})

    def test_off_by_default(self):
        ctx = self.ctx()
        self.assertEqual(alerts.run(ctx, OK_SNAP, self.burst(), self.send), 0)
        self.assertEqual(self.sent, [])
        self.assertFalse(alerts.state_path(ctx.live_dir).exists())

    def test_mailed_once_and_shown(self):
        ctx = self.ctx("alerts:\n  enabled: true\n")
        alerts.run(ctx, OK_SNAP, self.burst(), self.send)
        alerts.run(ctx, OK_SNAP, self.burst(), self.send)
        self.assertEqual(self.sent, ["ALERT: 30 server errors in 10 minutes"])
        page = SimpleNamespace(config=ctx.config, live_dir=ctx.live_dir)
        got = alerts.build(page)
        self.assertEqual((got["enabled"], got["mail"], len(got["open"])), (True, True, 1))
        self.assertEqual(got["open"][0]["repeats"], 1)
        self.assertEqual(len(got["rules"]), len(alerts.CAUSES))

    def test_never_mailed_on_another_host_or_from_a_replay(self):
        ctx = self.ctx("alerts:\n  enabled: true\n  only_on_host: not-this-machine\n")
        alerts.run(ctx, OK_SNAP, self.burst(), self.send)
        self.assertEqual(self.sent, [])
        self.assertFalse(alerts.load_state(ctx.live_dir)["mail"])
        box2 = Sandbox()
        try:
            self.box, old = box2, self.box
            ctx = self.ctx("alerts:\n  enabled: true\n", today="2026-10-06")
            alerts.run(ctx, OK_SNAP, self.burst(), self.send)
            self.assertEqual(self.sent, [])
        finally:
            self.box = old
            box2.close()

    def test_the_daily_digest_lists_repeats_once(self):
        ctx = self.ctx("alerts:\n  enabled: true\n  digest_hour: 0\n")
        alerts.run(ctx, OK_SNAP, self.burst(), self.send)       # mail + digest day marked
        state = alerts.load_state(ctx.live_dir)
        state["digest_sent_on"] = "2026-10-05"
        alerts.state_path(ctx.live_dir).write_text(json.dumps(state))
        alerts.run(ctx, OK_SNAP, self.burst(), self.send)
        alerts.run(ctx, OK_SNAP, self.burst(), self.send)
        self.assertEqual(self.sent, ["ALERT: 30 server errors in 10 minutes",
                                     "Alert digest: 1 repeated"])


class TestLiveRunsTheCheck(unittest.TestCase):
    def test_a_burst_of_errors_is_mailed_from_the_live_run(self):
        box = Sandbox()
        try:
            t = datetime(2026, 10, 6, 11, 55, tzinfo=UTC)
            box.log([line(t + timedelta(seconds=i), f"203.0.113.{i}", "/x", CHROME, status=502)
                     for i in range(12)])
            box.config.write_text(box.config.read_text() + "alerts:\n  enabled: true\n")
            with mock.patch.dict(os.environ, SECRETS), \
                    mock.patch("skald.mailer.smtplib.SMTP") as smtp, \
                    mock.patch("skald.cli._now", return_value=t + timedelta(minutes=1)):
                code, out, err = box.run("live")
            self.assertEqual(code, 0, err)
            self.assertIn("alert: 12 server errors", out)
            sent = smtp.return_value.send_message.call_args[0][0]
            self.assertIn("ALERT: 12 server errors in 10 minutes", sent["Subject"])
            got = json.loads((box.root / "www" / "example.com" / "data" / "alerts.json").read_text())
            self.assertEqual([a["cause"] for a in got["open"]], ["server_errors"])
            # The figures the check read are recounted from the raw log...
            with mock.patch("skald.cli._now", return_value=t + timedelta(minutes=1)):
                code, out, err = box.run("audit", "--live")
            self.assertEqual(code, 0, err)
            # ... and a wrong one is caught.
            state_file = box.root / alerts.STATE
            state = json.loads(state_file.read_text())
            state["figures"]["server_errors"]["n"] += 1
            state_file.write_text(json.dumps(state))
            with mock.patch("skald.cli._now", return_value=t + timedelta(minutes=1)):
                code, out, err = box.run("audit", "--live")
            self.assertEqual(code, 1)
            self.assertIn("alert check, server_errors in 10 minutes: 13 against 12", err)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
