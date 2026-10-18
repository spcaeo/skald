"""The in-page event beacon: what it accepts, the helper, collect, verify,
audit and events.json. Addresses are RFC 5737; the host is example.com."""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import beacon, events  # noqa: E402
from skald.beacon_server import Limiter, Sink, make_handler  # noqa: E402
from skald.config import View  # noqa: E402
from skald.store import History  # noqa: E402

CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
GPTBOT = "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)"
ORIGIN = "https://www.example.com"
NY = ZoneInfo("America/New_York")


def body(**kw) -> bytes:
    out = {"e": "cta_click", "p": "/pricing/", "id": "signup_hero"}
    out.update(kw)
    return json.dumps({k: v for k, v in out.items() if v is not None}).encode()


class Validate(unittest.TestCase):
    def test_a_good_beacon(self):
        got = beacon.validate(body(r="WWW.Google.com", u="Newsletter", vw="lg", t=12.7))
        self.assertEqual(got, {"e": "cta_click", "p": "/pricing/", "id": "signup_hero",
                               "r": "google.com", "u": "newsletter", "vw": "lg", "t": 12})

    def test_refused(self):
        for raw, reason in [
                (b"x" * 1025, "body"), (b"not json", "body"), (b"[1]", "body"),
                (body(e="purchase"), "event"), (body(e="page_view"), "event"),
                (body(p="pricing"), "path"), (body(p="/a?email=x@y.z"), "path"),
                (body(p="/a#b"), "path"), (body(p="/../etc"), "path"),
                (body(ip="203.0.113.9"), "field"), (body(user="u1"), "field"),
                (body(vw="huge"), "field"), (body(t=-1), "field"), (body(t=True), "field"),
                (body(t=90000), "field")]:
            with self.assertRaises(beacon.Refused, msg=raw[:60]) as caught:
                beacon.validate(raw)
            self.assertEqual(caught.exception.reason, reason, raw[:60])

    def test_free_text_is_dropped_not_kept(self):
        got = beacon.validate(body(id="Hello world!", r="not a host", u="a b"))
        self.assertEqual((got["id"], got["r"], got["u"]), ("", "", ""))

    def test_page_view_only_in_beacon_only_mode(self):
        on = beacon.allowed_events({"beacon": {"page_views": True}})
        self.assertEqual(beacon.validate(body(e="page_view"), on)["e"], "page_view")


class Source(unittest.TestCase):
    OWN = {"www.example.com", "example.com"}

    def test_types(self):
        self.assertEqual(beacon.source_of("google.com", "", self.OWN), ("Search engine", ""))
        self.assertEqual(beacon.source_of("chatgpt.com", "", self.OWN),
                         ("AI assistant", "chatgpt.com"))
        self.assertEqual(beacon.source_of("", "chatgpt.com", self.OWN)[0], "AI assistant")
        self.assertEqual(beacon.source_of("", "newsletter", self.OWN)[0], "Email")
        self.assertEqual(beacon.source_of("", "", self.OWN), ("Direct or unknown", ""))
        self.assertEqual(beacon.source_of("example.com", "", self.OWN)[0], "This site")


class Server(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.spool = Path(self.tmp.name) / "beacon"
        ours = Path(self.tmp.name) / "ours.json"
        self.config = {"site": {"name": "example.com", "hosts": ["www.example.com"]},
                       "report": {"timezone": "America/New_York"},
                       "ours": {"addresses": ["198.51.100.99"], "file": str(ours)}}
        self.sink = Sink(self.config, self.spool)
        self.limiter = Limiter(per_minute=60, burst=3)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0),
                                          make_handler(self.sink, self.limiter, {ORIGIN}))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def post(self, raw=None, origin=ORIGIN, ip="203.0.113.7", agent=CHROME, path="/traffic-beacon",
             **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        h = {"Content-Type": "text/plain", "User-Agent": agent, "X-Real-IP": ip, **headers}
        if origin:
            h["Origin"] = origin
        conn.request("POST", path, body=raw if raw is not None else body(), headers=h)
        status = conn.getresponse().status
        conn.close()
        return status

    def lines(self):
        today = self.sink.now().date()
        return beacon.read_day(self.spool, today)

    def test_counted_event_is_spooled_without_the_address(self):
        self.assertEqual(self.post(body(r="google.com")), 204)
        rows = self.lines()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["e"], rows[0]["g"], rows[0]["s"]),
                         ("cta_click", "people", "Search engine"))
        text = beacon.day_file(self.spool, self.sink.now().date()).read_text()
        self.assertNotIn("203.0.113.7", text)
        self.assertNotIn("Chrome", text)

    def test_origin_rules(self):
        self.assertEqual(self.post(origin=None), 403)
        self.assertEqual(self.post(origin="https://evil.example"), 403)
        self.assertEqual(self.post(**{"Sec-Fetch-Site": "cross-site"}), 403)
        self.assertEqual(self.post(**{"Sec-Fetch-Site": "same-origin"}), 204)
        self.assertEqual(len(self.lines()), 1)

    def test_body_rules(self):
        self.assertEqual(self.post(b"x" * 2000), 413)
        self.assertEqual(self.post(body(e="nope")), 400)
        self.assertEqual(self.post(path="/elsewhere"), 404)
        self.assertEqual(self.lines(), [])

    def test_privacy_signals_and_bots_keep_nothing(self):
        self.assertEqual(self.post(DNT="1"), 202)
        self.assertEqual(self.post(**{"Sec-GPC": "1"}), 202)
        self.assertEqual(self.post(agent=GPTBOT, ip="203.0.113.8"), 202)
        self.assertEqual(self.lines(), [])
        self.sink.close()
        stats = beacon.read_stats(self.spool, self.sink.now().date())
        self.assertEqual((stats["declined"], stats["not_people"]), (2, 1))

    def test_our_own_address_is_marked(self):
        self.assertEqual(self.post(ip="198.51.100.99"), 204)
        self.assertEqual(self.lines()[0]["g"], "ours")

    def test_rate_limit_per_address(self):
        got = [self.post() for _ in range(5)]
        self.assertEqual(got, [204, 204, 204, 429, 429])
        self.assertEqual(self.post(ip="203.0.113.50"), 204)


class LimiterClock(unittest.TestCase):
    def test_refills_with_time(self):
        t = [0.0]
        lim = Limiter(per_minute=60, burst=2, site_per_second=100, clock=lambda: t[0])
        self.assertEqual([lim.allow("a") for _ in range(3)], [True, True, False])
        t[0] += 1.0
        self.assertTrue(lim.allow("a"))

    def test_site_wide_cap(self):
        lim = Limiter(per_minute=6000, burst=100, site_per_second=1, clock=lambda: 0.0)
        got = [lim.allow(f"203.0.113.{i}") for i in range(8)]
        self.assertEqual(got.count(True), 5)


DAY = date(2026, 10, 7)


def spool_line(event="cta_click", path="/pricing/", group="people", source="Direct or unknown",
               at="2026-10-07T12:00:00-04:00", label="signup_hero", ai=""):
    row = {"at": at, "e": event, "p": path, "g": group, "s": source, "id": label,
           "r": "", "u": "", "vw": "lg", "t": 3}
    if ai:
        row["ai"] = ai
    return json.dumps(row, separators=(",", ":"), sort_keys=True)


class Collect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.spool = self.dir / "beacon"
        self.spool.mkdir()
        self.history = History(self.dir / "history.sqlite")
        self.config = {"beacon": {"enabled": True, "log": str(self.dir / "skald-beacon.log")},
                       "report": {"timezone": "America/New_York"}}

    def tearDown(self):
        self.history.close()
        self.tmp.cleanup()

    def write(self, lines):
        beacon.day_file(self.spool, DAY).write_text("\n".join(lines) + "\n")

    def nginx(self, n, status=204, at="2026-10-07T16:00:00+00:00"):
        with open(self.dir / "skald-beacon.log", "a") as out:
            for _ in range(n):
                out.write(f"{at} {status}\n")

    def test_counts_by_event_label_path_source(self):
        self.write([spool_line(), spool_line(), spool_line(event="scroll_75", label=""),
                    spool_line(group="ours"),
                    spool_line(source="AI assistant", ai="chatgpt.com"), "torn{"])
        got = events.collect(self.history, self.config, "example.com", self.spool, DAY)
        self.assertEqual((got["state"], got["events"], got["ours"]), ("ok", 4, 1))
        rows = sorted(self.history.db.execute(
            "SELECT event, label, path, source, n FROM event_counts"))
        self.assertEqual(rows, [("cta_click", "signup_hero", "/pricing/", "AI assistant", 1),
                                ("cta_click", "signup_hero", "/pricing/", "Direct or unknown", 2),
                                ("scroll_75", "", "/pricing/", "Direct or unknown", 1)])
        kinds = [a["kind"] for a in got["anomalies"]]
        self.assertIn("unchecked", kinds)      # no log day stored: bounds not checked
        self.assertIn("spool", kinds)          # the torn line

    def test_collect_twice_replaces(self):
        self.write([spool_line()])
        events.collect(self.history, self.config, "example.com", self.spool, DAY)
        events.collect(self.history, self.config, "example.com", self.spool, DAY)
        n = self.history.db.execute("SELECT SUM(n) FROM event_counts").fetchone()[0]
        self.assertEqual(n, 1)

    def test_audit_matches_spool_and_nginx(self):
        self.write([spool_line(), spool_line(group="ours")])
        self.nginx(2)
        self.nginx(3, status=429)
        events.collect(self.history, self.config, "example.com", self.spool, DAY)
        got = events.audit(self.history, self.config, "example.com", self.spool, DAY, NY)
        self.assertEqual((got["state"], got["nginx"], got["spool"]), ("ok", 2, 2))

    def test_audit_mismatch_withholds(self):
        self.write([spool_line()])
        self.nginx(1)
        events.collect(self.history, self.config, "example.com", self.spool, DAY)
        with open(beacon.day_file(self.spool, DAY), "a") as out:   # written after the count
            out.write(spool_line() + "\n")
        got = events.audit(self.history, self.config, "example.com", self.spool, DAY, NY)
        self.assertEqual(got["state"], "mismatch")
        self.assertEqual(len(got["problems"]), 2)   # history and nginx both disagree
        state = self.history.db.execute("SELECT state FROM event_days").fetchone()[0]
        self.assertEqual(state, "withheld")

    def test_midnight_edge_is_allowed(self):
        self.write([spool_line(at="2026-10-07T23:59:59-04:00")])
        self.nginx(0)                              # nginx filed it on the next day
        events.collect(self.history, self.config, "example.com", self.spool, DAY)
        got = events.audit(self.history, self.config, "example.com", self.spool, DAY, NY)
        self.assertEqual(got["state"], "ok")

    def test_prune_keeps_400_days(self):
        old = beacon.day_file(self.spool, DAY - timedelta(days=401))
        old.write_text(spool_line() + "\n")
        beacon.stats_file(self.spool, DAY - timedelta(days=401)).write_text("{}")
        self.write([spool_line()])
        self.assertEqual(beacon.prune(self.spool, DAY), 2)
        self.assertTrue(beacon.day_file(self.spool, DAY).exists())


class Bounds(unittest.TestCase):
    def test_path_past_its_bound_is_an_anomaly(self):
        people = Counter({("cta_click", "x", "/pricing/", "Direct or unknown"): 31,
                          ("cta_click", "x", "/", "Direct or unknown"): 5})
        pages = {"/pricing/": {"views": 1, "visits": 0}, "/": {"views": 3, "visits": 4}}
        anomalies, problems = events.bounds(people, pages, [], 100)
        self.assertEqual(problems, [])
        self.assertEqual([(a["path"], a["limit"]) for a in anomalies], [("/pricing/", 30)])

    def test_day_past_its_bound_is_withheld(self):
        people = Counter({("copy_text", "", "/", "Direct or unknown"): 151})
        _, problems = events.bounds(people, {}, [], 10)
        self.assertEqual(len(problems), 1)

    def test_404_view_against_people_404s(self):
        people = Counter({("404_view", "", "/old/", "Direct or unknown"): 14})
        nf = [{"path": "/old/", "group": "people", "n": 1},
              {"path": "/old/", "group": "bots", "n": 50}]
        anomalies, _ = events.bounds(people, {}, nf, 10)
        self.assertEqual([(a["kind"], a["limit"]) for a in anomalies], [("404", 13)])


class EventsJson(unittest.TestCase):
    def test_site_and_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            live_dir = Path(tmp)
            spool = live_dir / "beacon"
            spool.mkdir()
            config = {"beacon": {"enabled": True}, "report": {"timezone": "America/New_York"}}
            history = History(live_dir / "history.sqlite")
            beacon.day_file(spool, DAY).write_text("\n".join([
                spool_line(), spool_line(path="/ca/pricing/"), spool_line(group="ours")]) + "\n")
            events.collect(history, config, "example.com", spool, DAY)
            today = DAY + timedelta(days=1)
            beacon.day_file(spool, today).write_text(
                spool_line(event="demo_booked", at="2026-10-08T09:00:00-04:00") + "\n")

            def page(view=None):
                return SimpleNamespace(key="example.com" + (f"::{view.slug}" if view else ""),
                                       view=view, config=config, anchor=DAY, today=today,
                                       history=history, live_dir=live_dir, snap=None)

            site = events.build(page())
            self.assertEqual(len(site["days"]), 400)
            last = site["days"][-1]
            self.assertEqual((last["state"], last["events"], last["ours"]),
                             ("ok", {"cta_click": 2}, {"cta_click": 1}))
            self.assertEqual(site["days"][-2]["state"], "before")
            self.assertEqual(len(site["rows"]), 2)
            self.assertEqual(site["today"]["events"], {"demo_booked": 1})
            # Every event ever recorded, with its last day: the page says "not set up" for the rest.
            self.assertEqual(site["sent"], {"cta_click": DAY.isoformat(), "demo_booked": today.isoformat()})
            self.assertNotIn("signup_submit", site["sent"])
            us = events.build(page(View("US English", "", ("/ca/",))))
            self.assertEqual(us["days"][-1]["events"], {"cta_click": 1})
            self.assertIsNone(us["days"][-1]["ours"])
            self.assertEqual([r[3] for r in us["rows"]], ["/pricing/"])
            json.dumps(site)
            history.close()


class SkaldJs(unittest.TestCase):
    JS = Path(__file__).resolve().parent.parent / "beacon" / "skald.js"

    def test_small_and_sends_only_beacon_fields(self):
        text = self.JS.read_text()
        self.assertLessEqual(len(text.encode()), 1024)
        self.assertIn('send("page_view")', text)
        self.assertIn("doNotTrack", text)
        self.assertIn("globalPrivacyControl", text)
        for key in ("b.id", "b.r", "b.u"):
            self.assertIn(key, text)
        self.assertNotIn("cookie", text.split("*/", 1)[1])
        self.assertNotIn("localStorage", text)


class HooksOnly(unittest.TestCase):
    """No allowed origin: the helper takes the signed hooks only (2.2.2). The
    beacon and the script tag answer 404, so no site can send events yet."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config = {"site": {"name": "example.com", "hosts": ["www.example.com"]},
                  "report": {"timezone": "UTC"}}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            Sink(config, Path(self.tmp.name) / "beacon"), Limiter(per_minute=60, burst=3), set()))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def ask(self, method, path, raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        conn.request(method, path, body=raw, headers={"Origin": ORIGIN, "User-Agent": CHROME,
                                                      "Content-Type": "text/plain"})
        status = conn.getresponse().status
        conn.close()
        return status

    def test_beacon_and_script_tag_are_off(self):
        self.assertEqual(self.ask("POST", "/traffic-beacon", body()), 404)
        self.assertEqual(self.ask("GET", "/traffic-js/skald.js"), 404)

    def test_hooks_still_reach_the_receiver(self):
        seen = []

        def handle(h, *args):
            seen.append(h.path)
            h.send_response(200)
            h.send_header("Content-Length", "0")
            h.end_headers()
        with mock.patch("skald.conversions.hooks.handle", handle):
            self.assertEqual(self.ask("POST", "/traffic-hooks/example.com/lead", b"{}"), 200)
        self.assertEqual(seen, ["/traffic-hooks/example.com/lead"])

if __name__ == "__main__":
    unittest.main()
