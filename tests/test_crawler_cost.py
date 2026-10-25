"""What each crawler costs (crawler_cost.py) and its second count
(audit_crawler_cost.py).

What is pinned:
- the day kind on a synthetic day: requests, bytes and the lines with a size,
  response times (sum, count, p90 by nearest rank), statuses, distinct paths,
  the top pages, countries and agents, the last time, per name in the three
  machine groups; a scanner probe is "(scanner probes)";
- a name none of whose lines logged a size has bytes None (not recorded),
  one with some has a partial sum and says over how many lines; no time
  logged: ms and p90 None;
- a group with more names than TOP folds the rest into "(all others)", and
  the group still adds up;
- every sum is checked by verify, and a planted error is caught;
- the audit rebuilds every figure from the raw lines (nginx extended,
  combined with and without a response time, Netlify drain records) and a
  tampered stored figure fails it; the live audit compares it too;
- the audit's own line readers find the same size and time as the parser;
  its own short bot name agrees with aggregate._short_agent;
- crawler_cost.json carries the days, the detail lists for the last 30 days
  only, and today;
- the range sums in costsum.js (node): bytes not recorded stays null, partial
  is flagged, the mean is weighted by request, p90 only for one day;
- the recount shares only classify.py's names.
"""
from __future__ import annotations

import ast
import json
import shutil
import sqlite3
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import GOOGLEBOT, GPTBOT, Sandbox, totals_for  # noqa: E402

from skald import audit, audit_crawler_cost, crawler_cost, extras  # noqa: E402
from skald.aggregate import _short_agent  # noqa: E402
from skald.parse import PARSERS  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
JS = Path(__file__).resolve().parent.parent / "skald" / "webapp" / "js"
AHREFS = "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)"


def at(hour: int, minute: int, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def ext(when, address, path, agent, status=200, size="512", rt="0.004", cc="US",
        host="example.com") -> str:
    """An nginx_extended line with a chosen size and response time."""
    tail = f" {rt}" if rt is not None else ""
    return (f'{when.isoformat()} {address} {host} "GET {path} HTTP/1.1" {status} {size} '
            f'"-" "{agent}"{tail} cc={cc}\n')


def combined(when, address, path, agent, status=200, size="300", rt=None) -> str:
    """A combined line, with an optional response time after the agent."""
    stamp = when.strftime("%d/%b/%Y:%H:%M:%S +0000")
    tail = f" {rt}" if rt is not None else ""
    return (f'{address} - - [{stamp}] "GET {path} HTTP/1.1" {status} {size} "-" '
            f'"{agent}"{tail} "example.com"\n')


def synthetic(day: date = DAY) -> list[str]:
    return [
        ext(at(9, 0, day), "198.51.100.40", "/a", GPTBOT, size="1000", rt="0.010"),
        ext(at(9, 1, day), "198.51.100.40", "/a?x=1", GPTBOT, size="-", rt="0.020"),
        ext(at(9, 2, day), "198.51.100.40", "/b", GPTBOT, status=404, size="200", rt="0.300",
            cc="DE"),
        ext(at(9, 3, day), "198.51.100.40", "/c", GPTBOT, status=503, size="0", rt="-"),
        # Googlebot: no size on any line, so its bytes are not recorded.
        ext(at(10, 0, day), "198.51.100.42", "/", GOOGLEBOT, size="-", rt="0.050"),
        ext(at(10, 5, day), "198.51.100.42", "/", GOOGLEBOT, size="-", rt="0.070"),
        # A bot named by its agent, and a scanner probe.
        ext(at(11, 0, day), "198.51.100.50", "/x", AHREFS, size="2048", rt="0.001", cc="-"),
        ext(at(11, 1, day), "198.51.100.52", "/.env", "curl/8.7.1", status=404, size="153"),
        # A person: never in this kind.
        ext(at(12, 0, day), "203.0.113.10", "/", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
    ]


class TestTheDay(unittest.TestCase):

    def test_the_synthetic_day(self):
        totals = totals_for(synthetic())
        blob = totals.extras["crawler_cost"]["groups"]
        self.assertEqual(extras.check(totals), [])
        gpt = blob["answer_engines"]["GPTBot"]
        self.assertEqual((gpt["requests"], gpt["bytes"], gpt["sized"]), (4, 1200, 3))
        self.assertEqual((gpt["ms"], gpt["timed"], gpt["p90_ms"]), (330, 3, 300))
        self.assertEqual(gpt["status"], {"2xx": 2, "4xx": 1, "5xx": 1})
        self.assertEqual((gpt["paths"], gpt["pages"]), (3, {"/a": 2, "/b": 1, "/c": 1}))
        self.assertEqual(gpt["countries"], {"US": 3, "DE": 1})
        self.assertEqual(gpt["agents"], {GPTBOT: 4})
        self.assertEqual(gpt["last"], "2026-10-05T09:03:00+00:00")
        google = blob["search_engines"]["Googlebot"]
        self.assertEqual((google["bytes"], google["sized"]), (None, 0))  # not recorded
        self.assertEqual((google["ms"], google["timed"], google["p90_ms"]), (120, 2, 70))
        self.assertEqual(set(blob["bots"]), {"AhrefsBot", "(scanner probes)"})
        self.assertEqual(blob["bots"]["AhrefsBot"]["countries"], {"Unknown": 1})
        probe = blob["bots"]["(scanner probes)"]
        self.assertEqual((probe["ms"], probe["timed"], probe["p90_ms"]), (4, 1, 4))
        # A probe's string may be a person's browser: not kept. A named bot's is.
        self.assertIsNone(probe["agents"])
        self.assertEqual(blob["bots"]["AhrefsBot"]["agents"], {AHREFS: 1})
        self.assertNotIn("people", blob)

    def test_nearest_rank_p90(self):
        self.assertIsNone(crawler_cost.p90([]))
        self.assertEqual(crawler_cost.p90([5]), 5)
        self.assertEqual(crawler_cost.p90(list(range(1, 11))), 9)
        self.assertEqual(crawler_cost.p90(list(range(1, 12))), 10)
        for n in range(1, 40):
            values = [(i * 37) % 101 for i in range(n)]
            self.assertEqual(crawler_cost.p90(values), audit_crawler_cost._ninetieth(values))

    def test_a_busy_group_folds_its_tail_and_still_adds_up(self):
        lines = [ext(at(8, i % 60), f"198.51.100.{i % 200}", f"/p{i}",
                     f"Robot{i:03d}/1.0", size="10" if i % 2 else "-")
                 for i in range(crawler_cost.TOP + 7)]
        totals = totals_for(lines)
        bots = totals.extras["crawler_cost"]["groups"]["bots"]
        self.assertEqual(len(bots), crawler_cost.TOP + 1)
        fold = bots[crawler_cost.OTHER]
        self.assertEqual((fold["names"], fold["requests"], fold["paths"]), (7, 7, None))
        self.assertEqual(sum(e["requests"] for e in bots.values()), crawler_cost.TOP + 7)
        self.assertEqual(extras.check(totals), [])

    def test_planted_errors_are_caught(self):
        def problems(change):
            totals = totals_for(synthetic())
            change(totals.extras["crawler_cost"]["groups"])
            return [f"{p.what}: {p.detail}" for p in extras.check(totals)]
        got = problems(lambda g: g["answer_engines"]["GPTBot"].update(requests=5))
        self.assertTrue(any("answer_engines requests by name" in p for p in got), got)
        got = problems(lambda g: g["search_engines"]["Googlebot"].update(bytes=0))
        self.assertTrue(any("bytes recorded without a sized line" in p for p in got), got)
        got = problems(lambda g: g["answer_engines"]["GPTBot"]["countries"].update(FR=1))
        self.assertTrue(any("GPTBot: requests by countries" in p for p in got), got)
        got = problems(lambda g: g["bots"].pop("AhrefsBot"))
        self.assertTrue(any("bots requests by name" in p for p in got), got)


class TestTheAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic() + [
            combined(at(13, 0), "198.51.100.60", "/c1", "Mozilla/5.0 (compatible; SeoBot/2)",
                     rt="0.123"),
            combined(at(13, 1), "198.51.100.60", "/c2", "Mozilla/5.0 (compatible; SeoBot/2)",
                     size="-"),
        ])

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]["crawler_cost"]

    def tamper(self, blob):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'crawler_cost'",
                       (json.dumps(blob),))
        db.close()

    def audit(self):
        return self.box.run("--today", TODAY, "audit")

    def test_the_recount_matches_and_planted_errors_are_caught(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.audit()
        self.assertEqual(code, 0, err)
        seo = self.stored()["groups"]["bots"]["SeoBot"]
        self.assertEqual((seo["requests"], seo["bytes"], seo["sized"], seo["ms"], seo["timed"]),
                         (2, 300, 1, 123, 1))
        for change, words in (
                (lambda b: b["groups"]["answer_engines"]["GPTBot"].update(bytes=1201),
                 "crawler_cost: answer_engines GPTBot: bytes: history has 1,201, the recount "
                 "finds 1,200"),
                (lambda b: b["groups"]["answer_engines"]["GPTBot"].update(ms=331),
                 "GPTBot: milliseconds: history has 331"),
                (lambda b: b["groups"]["answer_engines"]["GPTBot"].update(p90_ms=20),
                 "GPTBot: p90 milliseconds: history has 20, the recount finds 300"),
                (lambda b: b["groups"]["search_engines"]["Googlebot"].update(bytes=0, sized=0),
                 "Googlebot: bytes are recorded, the recount finds 0 lines with a size"),
                (lambda b: b["groups"]["bots"]["SeoBot"]["status"].update({"2xx": 1, "4xx": 1}),
                 "SeoBot: 4xx responses: history has 1, the recount finds 0"),
                (lambda b: b["groups"]["answer_engines"]["GPTBot"].update(paths=4),
                 "GPTBot: distinct paths: history has 4, the recount finds 3"),
                (lambda b: b["groups"]["bots"].pop("AhrefsBot"),
                 "crawler_cost: bots (all others): requests: history has 0, the recount finds 1"),
                (lambda b: b["groups"]["answer_engines"]["GPTBot"].update(
                    last="2026-10-05T09:04:00+00:00"),
                 "GPTBot: last seen 2026-10-05T09:04:00+00:00"),
                (lambda b: b["groups"]["bots"]["(scanner probes)"].update(
                    agents={"curl/8.7.1": 1}),
                 "(scanner probes): user agents are kept, and must not be")):
            with self.subTest(words=words):
                self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
                blob = self.stored()
                change(blob)
                self.tamper(blob)
                code, _, err = self.audit()
                self.assertEqual(code, 1, err)
                self.assertIn(words, err)

    def test_the_live_audit_compares_it_too(self):
        import os
        stamp = at(23, 0).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self.assertEqual(self.box.run("--today", DAY.isoformat(), "live")[0], 0)
        code, _, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["extras"]["crawler_cost"]["groups"]["answer_engines"]["GPTBot"]
                         ["requests"], 4)

    def test_the_data_file(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        got = json.loads((self.box.root / "www" / "example.com" / "data" / "crawler_cost.json")
                         .read_text())
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        gpt = day["names"]["answer_engines"]["GPTBot"]
        self.assertEqual((gpt["tier"], gpt["requests"], gpt["bytes"], gpt["p90_ms"]),
                         ("training", 4, 1200, 300))
        self.assertEqual(gpt["pages"], {"/a": 2, "/b": 1, "/c": 1})
        self.assertIsNone(day["names"]["search_engines"]["Googlebot"]["bytes"])
        before = next(d for d in got["days"] if d["state"] in ("before", "missing"))
        self.assertNotIn("names", before)
        self.assertEqual(got["detail_days"], 30)


class TestDetailDays(unittest.TestCase):

    def test_lists_only_for_the_last_30_days(self):
        old, new = {"groups": {"bots": {"x": {"requests": 1, "pages": {"/": 1}}}}}, None
        self.assertNotIn("pages", crawler_cost._compact(old, False)["bots"]["x"])
        self.assertEqual(crawler_cost._compact(old, True)["bots"]["x"]["pages"], {"/": 1})
        self.assertIsNone(crawler_cost._compact(new, True))


class TestTheLineReaders(unittest.TestCase):
    """The audit's own readers find the size and the time the parser finds."""

    def test_size_and_time_agree(self):
        netlify = json.dumps({"log_type": "traffic", "timestamp": "2026-10-05T10:00:00Z",
                              "client_ip": "198.51.100.9", "status_code": 200,
                              "url": "https://example.com/n", "method": "GET",
                              "user_agent": GPTBOT, "response_size": 812, "duration": 37})
        vercel = json.dumps({"proxy": {"timestamp": 1791194400000, "clientIp": "198.51.100.8",
                                       "path": "/v", "statusCode": 200, "host": "example.com",
                                       "method": "GET", "userAgent": [GPTBOT],
                                       "responseByteSize": "640"}})
        caddy = json.dumps({"ts": 1791194400.5, "status": 200, "size": 91,
                            "request": {"client_ip": "198.51.100.7", "host": "example.com",
                                        "method": "GET", "uri": "/k",
                                        "headers": {"User-Agent": [GPTBOT]}}})
        cases = [
            ("nginx_extended", ext(at(9, 0), "198.51.100.1", "/", GPTBOT, size="77", rt="0.125")),
            ("nginx_extended", ext(at(9, 0), "198.51.100.1", "/", GPTBOT, size="-", rt=None)),
            ("nginx_extended", ext(at(9, 0), "198.51.100.1", "/", GPTBOT, size="5", rt="-")),
            ("nginx_combined", combined(at(9, 0), "198.51.100.2", "/", GPTBOT, rt="1.5")),
            ("nginx_combined", combined(at(9, 0), "198.51.100.2", "/", GPTBOT, size="-")),
            ("nginx_combined", combined(at(9, 0), "198.51.100.2", "/", GPTBOT, rt="1.")),
            ("netlify_json", netlify + "\n"),
            ("vercel_json", vercel + "\n"),
            ("caddy_json", caddy + "\n"),
        ]
        for fmt, raw in cases:
            with self.subTest(fmt=fmt, raw=raw[:60]):
                hit = PARSERS[fmt](raw.rstrip("\n"))
                mine = audit.line_hit(raw)
                self.assertIsNotNone(hit)
                self.assertIsNotNone(mine)
                self.assertEqual(mine.size, hit.size)
                self.assertEqual(mine.seconds, hit.request_time)

    def test_the_short_bot_name_agrees(self):
        agents = ["", "curl/8.7.1", AHREFS, "Mozilla/5.0 (compatible; Foo Bar/1.0)",
                  "Mozilla/5.0 (compatible;  ;x)", "Mozilla/5.0 (compatible;;compatible; Zed)",
                  "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P)",
                  "Mozilla/5.0 (X11; Linux x86_64)", "compatible; x", "python-requests/2.32",
                  "Mozilla/5.0 (compatible; " + "a" * 40 + "/1)", "Wget", " lead space"]
        for agent in agents:
            with self.subTest(agent=agent):
                self.assertEqual(audit_crawler_cost.short_name(agent), _short_agent(agent))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestTheRangeSums(unittest.TestCase):

    def sums(self, file, r, name=None):
        script = ("const m = await import(process.argv[1]);"
                  "const [f, r, name] = JSON.parse(process.argv[2]);"
                  "const got = name ? m.detailOf(f, r, name) : m.sumCosts(f, r);"
                  "if (got.perDay) got.perDay = Object.fromEntries(got.perDay);"
                  "console.log(JSON.stringify(got));")
        done = subprocess.run(["node", "--input-type=module", "-e", script,
                               (JS / "tabs" / "costsum.js").as_uri(), json.dumps([file, r, name])],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_ranges(self):
        def entry(requests, bytes_, sized, ms, timed, p90, paths, **more):
            return {"requests": requests, "bytes": bytes_, "sized": sized, "ms": ms,
                    "timed": timed, "p90_ms": p90, "status": {"2xx": requests - 1, "4xx": 1},
                    "paths": paths, "last": "2026-10-0%dT10:00:00+00:00" % requests, **more}
        file = {"days": [
            {"day": "2026-10-03", "state": "ok", "names": None},          # before it was counted
            {"day": "2026-10-04", "state": "ok", "names": {"bots": {
                "x": entry(4, None, 0, 40, 4, 20, 2, pages={"/": 4}),
                "y": entry(2, 100, 2, None, 0, None, 1)}}},
            {"day": "2026-10-05", "state": "ok", "names": {"bots": {
                "x": entry(6, 300, 3, 600, 2, 500, 3, pages={"/": 5, "/b": 1})}}},
            {"day": "2026-10-06", "state": "withheld"},
        ], "today": None}
        got = self.sums(file, {"kind": "history", "first": "2026-10-03", "last": "2026-10-06"})
        self.assertEqual((got["days"], got["unrecorded"], got["single"]), (2, 1, False))
        x = next(r for r in got["rows"] if r["name"] == "x")
        self.assertEqual((x["requests"], x["bytes"], x["sized"], x["partial"]), (10, 300, 3, True))
        self.assertEqual(x["mean_ms"], 640 / 6)          # weighted by request, not a mean of means
        self.assertIsNone(x["p90_ms"])                   # a range: no p90
        self.assertEqual((x["errors"], x["paths"], x["recrawl"]), (2, 5, 2.0))
        y = next(r for r in got["rows"] if r["name"] == "y")
        self.assertEqual((y["bytes"], y["partial"], y["mean_ms"]), (100, False, None))
        one = self.sums(file, {"kind": "history", "first": "2026-10-04", "last": "2026-10-04"})
        x1 = next(r for r in one["rows"] if r["name"] == "x")
        self.assertEqual((x1["bytes"], x1["p90_ms"]), (None, 20))     # not recorded, one day
        detail = self.sums(file, {"kind": "history", "first": "2026-10-03", "last": "2026-10-06"},
                           "y")
        self.assertEqual(detail["perDay"], {"2026-10-04": 2, "2026-10-05": 0})
        detail = self.sums(file, {"kind": "history", "first": "2026-10-03", "last": "2026-10-06"},
                           "x")
        self.assertEqual((detail["lists"]["pages"], detail["listed"]), ({"/": 9, "/b": 1}, 2))


class TestIndependence(unittest.TestCase):

    def test_the_recount_shares_only_classify_names(self):
        tree = ast.parse(Path(audit_crawler_cost.__file__).read_text())
        got = {(n.module, a.name) for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(got, {("classify", "CRAWLER_SESSION"), ("classify", "LINK_PREVIEW"),
                               ("classify", "NOT_RENDERED"), ("classify", "SCANNER"),
                               ("classify", "TOO_FAST"), ("classify", "SWEEP"),
                               ("classify", "LINK_CHECKER")})


if __name__ == "__main__":
    unittest.main()
