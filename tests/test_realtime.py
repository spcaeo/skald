"""Real time: the live run's `realtime` part, the 15-second tail of the log,
the helper's route, the data file, their second counts, and the world map.

The people figures come from the day's tally (the people rule of every other
figure); the requests from the newest lines, unsorted. No address and no user
agent may reach either.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import realtime, realtime_api, realtime_tail  # noqa: E402

from support import ASKED, GOOGLEBOT, GPTBOT, Sandbox, line  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 7)
NOON = datetime(2026, 10, 7, 12, tzinfo=UTC)          # --today runs at local noon
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1")
ROOT = Path(__file__).resolve().parent.parent
WORLD = ROOT / "skald" / "webapp" / "vendor" / "world-110m.js"


def m(minutes: float) -> datetime:
    """`minutes` before noon."""
    return NOON - timedelta(minutes=minutes)


def morning() -> list[str]:
    """Readers' visits at various ages before noon, and machines."""
    return [
        line(m(180), "203.0.113.10", "/old", country="FR"),                 # not active
        line(m(25), "203.0.113.11", "/", country="CA", referrer="https://www.google.com/"),
        line(m(24), "203.0.113.11", "/pricing", country="CA"),
        line(m(20), "203.0.113.12", "/guides/alpha", IPHONE, country="GB"),
        line(m(19.9), "203.0.113.12", "/_next/static/app.js", IPHONE, country="GB"),
        line(m(3), "203.0.113.13", "/", country="US", referrer="https://chatgpt.com/"),
        line(m(2), "203.0.113.11", "/docs", country="CA"),                   # CA again, 22 min on
        line(m(40), "203.0.113.14", "/", country="DE"),                     # 40 min ago: not active
        line(m(10), "198.51.100.40", "/guides/alpha", GPTBOT),
        line(m(9), "198.51.100.41", "/guides/beta", ASKED),
        line(m(8), "198.51.100.42", "/", GOOGLEBOT),
        line(m(7), "198.51.100.52", "/.env", "curl/8.7.1", status=404),
        line(m(6), "198.51.100.53", "/", host="api.example.com"),           # another host
    ]


class Case(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.box.log(morning())
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


class TestSnapshotPart(Case):
    def test_people_now(self):
        rt = self.live()["realtime"]
        self.assertEqual(rt["visits_today"], 5)
        # CA (last at -2), GB (-19.9), US (-3) are active in 30 min; CA and US in 5.
        self.assertEqual(rt["active"], {"5": 2, "30": 3})
        self.assertEqual(rt["countries"]["CA"], {"visits": 1, "active": 1})
        self.assertEqual(rt["countries"]["FR"], {"visits": 1, "active": 0})
        self.assertEqual(rt["countries"]["DE"], {"visits": 1, "active": 0})
        self.assertEqual(sum(rt["devices"].values()), 3)
        self.assertEqual(rt["devices"].get("Mobile"), 1)
        self.assertEqual(sum(rt["sources"].values()), 3)
        # Page views in the last 30 minutes: /, /pricing, /guides/alpha, /, /docs.
        self.assertEqual(rt["page_views"], 5)
        self.assertEqual(rt["pages"]["/"], 2)
        self.assertEqual(rt["machines"]["answer_engines"], {"GPTBot": 1, "ChatGPT-User": 1})
        self.assertEqual(sum(rt["machines"]["search_engines"].values()), 1)
        self.assertEqual(rt["machines"]["bots"], 1)

    def test_per_minute(self):
        rt = self.live()["realtime"]
        rows = rt["per_minute"]
        self.assertEqual(len(rows), 30)
        self.assertEqual(rows[-1]["at"], "2026-10-07T11:59+00:00")
        by = {r["at"][11:16]: r for r in rows}
        self.assertEqual(by["11:35"]["started"], 1)        # the CA visit
        self.assertEqual(by["11:40"]["under_way"], 2)      # CA (11:35 to 11:58) and GB
        self.assertEqual(by["11:45"]["under_way"], 1)      # GB was over at 11:40
        self.assertEqual(by["11:57"]["started"], 1)        # the US visit
        self.assertEqual(by["11:50"]["requests"], {"answer_engines": 1})
        self.assertNotIn("excluded", json.dumps(by["11:54"]["requests"]))
        # 11:31 to 11:59: the 40-minute-old DE visit is not in any of them.
        self.assertEqual(sum(r["started"] for r in rows), 3)

    def test_no_address_no_agent(self):
        text = json.dumps(self.live()["realtime"])
        self.assertIsNone(re.search(r"\d+\.\d+\.\d+\.\d+", text))
        self.assertNotIn("Mozilla", text)
        newest = self.live()["realtime"]["newest"]
        self.assertEqual([v["country"] for v in newest[:2]], ["US", "GB"])
        self.assertEqual(newest[0]["active"], "5")
        self.assertEqual(set(newest[0]), {"start", "country", "city", "device", "browser",
                                          "source", "via", "landing", "pages", "in_app", "active",
                                          "first_touch", "seq"})
        self.assertEqual(newest[0]["city"], "", "no city file: no city")


class TestAudit(Case):
    def test_recount_matches(self):
        self.live()
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: live", out)

    def tamper(self, fn):
        path = self.box.root / "live-example.com.json"
        snap = json.loads(path.read_text())
        fn(snap["realtime"])
        path.write_text(json.dumps(snap))
        return self.audit()

    def test_active_tampered(self):
        self.live()
        code, _, err = self.tamper(lambda rt: rt["active"].update({"30": 4}))
        self.assertEqual(code, 1)
        self.assertIn("real time: visits active in the last 30 minutes", err)

    def test_minute_and_country_tampered(self):
        self.live()

        def change(rt):
            rt["per_minute"][-3]["under_way"] += 1
            rt["countries"]["FR"]["visits"] = 2
            rt["machines"]["bots"] = 0
        code, _, err = self.tamper(change)
        self.assertEqual(code, 1)
        self.assertIn("visits under way", err)
        self.assertIn("visits today from FR", err)
        self.assertIn("bot and scanner requests", err)

    def test_tail_recounted(self):
        self.live()
        got = realtime_tail.requests_now(self.config(), NOON)
        path = realtime_tail.tail_path(self.box.root, "example.com")
        path.write_text(json.dumps(got))
        code, out, err = self.audit()
        self.assertEqual(code, 0, err)
        got["per_minute"][str(int(m(3).timestamp()) // 60)] += 1
        got["total"] += 1
        path.write_text(json.dumps(got))
        code, _, err = self.audit()
        self.assertEqual(code, 1)
        self.assertIn("15-second count", err)

    def config(self):
        from skald.config import load_config
        return load_config(self.box.config)


class TestTail(Case):
    def config(self):
        from skald.config import load_config
        return load_config(self.box.config)

    def test_counts_every_request_of_the_site(self):
        got = realtime_tail.requests_now(self.config(), NOON)
        # 30 minutes: 11:30 to noon. In it, 12 lines of example.com (not FR at -180,
        # not DE at -40, not the api.example.com line).
        self.assertEqual(got["total"], 10)
        self.assertEqual(len(got["per_minute"]), 30)
        self.assertEqual(got["newest"], m(2).isoformat(timespec="seconds"))
        self.assertFalse(got["partial"])

    def test_reads_only_the_end(self):
        old = [line(m(300) + timedelta(seconds=i), "203.0.113.20", f"/p{i}") for i in range(3000)]
        self.box.log(old + morning()[1:])
        with mock.patch.object(realtime_tail, "BLOCK", 4096), \
                mock.patch.object(realtime_tail, "_split", wraps=realtime_tail._split) as split:
            got = realtime_tail.requests_now(self.config(), NOON)
        self.assertEqual(got["total"], 10)
        read = sum(len(c) for c in split.call_args[0][0])
        self.assertLess(read, 3000 * 100)
        with mock.patch.object(realtime_tail, "BLOCK", 512), \
                mock.patch.object(realtime_tail, "MAX_BYTES", 1024):
            short = realtime_tail.requests_now(self.config(), NOON)
        self.assertTrue(short["partial"])

    def test_cache(self):
        clock = iter([0.0, 5.0, 20.0, 20.0])
        with mock.patch.object(realtime_tail, "requests_now", return_value={"x": 1}) as now:
            realtime_tail._CACHE.clear()
            for _ in range(3):
                realtime_tail.cached("example.com", {}, None, clock=lambda: next(clock))
        self.assertEqual(now.call_count, 2)
        realtime_tail._CACHE.clear()


class TestRoute(Case):
    def test_answer(self):
        self.live()
        from skald.config import load_config
        realtime_tail._CACHE.clear()
        code, body = realtime_api.answer(load_config(self.box.config), self.box.root,
                                         "example.com", self.box.config, now=NOON)
        realtime_tail._CACHE.clear()
        self.assertEqual(code, 200)
        self.assertEqual(body["people_state"], "ok")
        self.assertEqual(body["people"]["active"], {"5": 2, "30": 3})
        self.assertEqual(body["requests"]["total"], 10)
        self.assertEqual(body["requests"]["per_minute"][-1]["at"], "2026-10-07T11:59+00:00")
        self.assertTrue(realtime_tail.tail_path(self.box.root, "example.com").exists())
        self.assertIsNone(re.search(r"\d+\.\d+\.\d+\.\d+", json.dumps(body)))

    def test_unknown_site(self):
        from skald.config import load_config
        code, _ = realtime_api.answer(load_config(self.box.config), self.box.root,
                                      "other.example.com", self.box.config, now=NOON)
        self.assertEqual(code, 404)

    def test_path(self):
        self.assertTrue(realtime_api.is_realtime("/traffic/example.com/api/realtime"))
        self.assertTrue(realtime_api.is_realtime("/traffic/example.com/blog/api/realtime?x=1"))
        self.assertFalse(realtime_api.is_realtime("/traffic/example.com/api/realtimes"))


class TestDataFile(unittest.TestCase):
    def page(self, snap, view=None, now=NOON):
        return SimpleNamespace(view=view, snap=snap, now=now)

    def test_states(self):
        part = {"until": (NOON - timedelta(minutes=1)).isoformat()}
        self.assertEqual(realtime.build(self.page({"state": "ok", "realtime": part}))["state"], "ok")
        self.assertEqual(realtime.build(self.page({"state": "ok", "realtime": part},
                                                  now=NOON + timedelta(minutes=20)))["state"],
                         "stale")
        self.assertEqual(realtime.build(self.page({"state": "withheld"}))["state"], "withheld")
        self.assertEqual(realtime.build(self.page(None))["state"], "empty")
        self.assertEqual(realtime.build(self.page({"state": "ok"}, view=object()))["state"], "site")


class TestWorldMap(unittest.TestCase):
    def test_vendored_map(self):
        text = WORLD.read_text()
        self.assertLess(len(text.encode()), 150 * 1024)
        self.assertIn("Natural Earth", text)
        data = json.loads(text.split("export const WORLD = ", 1)[1].rstrip().rstrip(";"))
        for code in ("US", "CA", "GB", "FR", "NO", "IN", "BR", "AU"):
            self.assertIn(code, data["paths"])
            self.assertIn(code, data["points"])
        self.assertNotIn("AQ", data["paths"])
        self.assertIn("SG", data["dots"])
        self.assertTrue(all(re.fullmatch(r"[A-Z]{2}", k) for k in data["paths"]))
        self.assertGreater(len(data["paths"]), 150)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_shading_steps(self):
        """The map's steps (js/tabs/rt-map.js) cover 1 to the top with no gap,
        five at most, and 0 is no step: a country with no visit is not shaded."""
        script = ('globalThis.addEventListener = () => {};'
                  'const m = await import(process.argv[1]);'
                  'console.log(JSON.stringify([17, 1, 0, 1000].map((v) => m.bins(v)).concat('
                  '[[m.binOf(0, m.bins(17)), m.binOf(5, m.bins(17)), m.binOf(17, m.bins(17))]])));')
        done = subprocess.run(["node", "--input-type=module", "-e", script,
                               (ROOT / "skald/webapp/js/tabs/rt-map.js").as_uri()],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        *lists, picks = json.loads(done.stdout)
        for top, got in zip((17, 1, 0, 1000), lists):
            self.assertLessEqual(len(got), 5)
            if top:
                self.assertEqual(got[0][0], 1)
                self.assertEqual(got[-1][1], top)
                self.assertTrue(all(b[0] == a[1] + 1 for a, b in zip(got, got[1:])))
            else:
                self.assertEqual(got, [])
        self.assertEqual(picks, [-1, 2, 4])

    def test_credit_in_about(self):
        about = (ROOT / "skald" / "webapp" / "js" / "tabs" / "about.js").read_text()
        self.assertTrue("Natural Earth" in about, "About credits Natural Earth")


if __name__ == "__main__":
    unittest.main()
