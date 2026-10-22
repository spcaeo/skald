"""The beacon helper for several sites: each event goes to the site its
Origin names, into that site's own spool; skald.js is served with the
visitor-ID setting of the site whose page loads it; nginx's record of the
answers is counted per site. Addresses are RFC 5737; hosts example.com/.net.
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import beacon, events  # noqa: E402
from skald.beacon_server import Limiter, Sink, Sites, make_handler  # noqa: E402

CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
FIRST = "https://www.example.com"
SECOND = "https://second.example.net"


def body(**kw) -> bytes:
    out = {"e": "cta_click", "p": "/pricing/", "id": "hero"}
    out.update(kw)
    return json.dumps(out).encode()


class TwoSites(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        tz = {"report": {"timezone": "UTC"}}
        self.first = Sink({"site": {"name": "example.com", "hosts": ["www.example.com"]}, **tz},
                          root / "beacon")
        self.second = Sink({"site": {"name": "second.example.net",
                                     "hosts": ["second.example.net"]},
                            "beacon": {"visitor_ids": True}, **tz},
                           root / "sites" / "second.example.net" / "beacon")
        self.sites = Sites(self.first, {FIRST})
        # What Sites._load makes from a dashboard site: its own sink, by its hosts.
        self.sites.others = {"second.example.net": self.second}
        self.sites.by_origin[SECOND] = self.second
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            self.sites, Limiter(per_minute=600, burst=100)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, method, path, raw=None, **headers):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        h = {"User-Agent": CHROME, "X-Real-IP": "203.0.113.7", **headers}
        conn.request(method, path, body=raw, headers=h)
        got = conn.getresponse()
        out = (got.status, dict(got.getheaders()), got.read())
        conn.close()
        return out

    def post(self, origin, raw=None):
        return self.call("POST", "/traffic-beacon", raw or body(), Origin=origin,
                         **{"Content-Type": "text/plain", "Sec-Fetch-Site": "same-origin"})

    def test_each_event_goes_to_its_own_site(self):
        status, headers, _ = self.post(SECOND)
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("X-Skald-Site"), "second.example.net")
        status, headers, _ = self.post(FIRST)
        self.assertEqual((status, headers.get("X-Skald-Site")), (204, "example.com"))
        today = self.first.now().date()
        self.assertEqual(len(beacon.read_day(self.second.spool, today)), 1)
        self.assertEqual(len(beacon.read_day(self.first.spool, today)), 1)

    def test_an_origin_of_no_site_is_refused(self):
        status, headers, _ = self.post("https://elsewhere.example.org")
        self.assertEqual(status, 403)
        self.assertNotIn("X-Skald-Site", headers)

    def test_visitor_ids_follow_the_site(self):
        status, _, _ = self.post(SECOND, body(e="page_view", v="a" * 22))
        self.assertEqual(status, 204, "page_view counts where visitor IDs are on")
        status, _, _ = self.post(FIRST, body(e="page_view"))
        self.assertEqual(status, 202, "and not where they are off")
        # ...but its opening is kept as proof the page was drawn (2.10.1)
        rows = beacon.opens_file(self.first.spool, self.first.now().date()).read_text()
        got = [json.loads(l) for l in rows.splitlines()]
        self.assertEqual([(r["e"], r["p"], r["g"]) for r in got],
                         [("page_view", "/pricing/", "people")])
        self.assertEqual(beacon.read_day(self.first.spool, self.first.now().date()), [],
                         "and it is no event")

    def test_the_snippet_is_the_loading_page_s(self):
        _, h1, js1 = self.call("GET", "/traffic-js/skald.js",
                               Referer="https://second.example.net/pricing")
        _, h2, js2 = self.call("GET", "/traffic-js/skald.js", Referer=FIRST + "/")
        _, _, js3 = self.call("GET", "/traffic-js/skald.js")
        self.assertIn(b"IDS=1", js1)
        self.assertIn(b"IDS=0", js2)
        self.assertEqual(js3, js2, "no Referer: the first site's")
        self.assertNotEqual(h1["ETag"], h2["ETag"])
        self.assertEqual(h1.get("Vary"), "Referer")

    def test_one_site_with_its_origins_still_works(self):
        sink = Sink({"site": {"name": "example.com", "hosts": ["www.example.com"]},
                     "report": {"timezone": "UTC"}}, Path(self.tmp.name) / "solo")
        handler = make_handler(sink, Limiter(), {FIRST})
        self.assertTrue(callable(handler))


class Direct(TwoSites):
    """The plain tag loads skald.js from Skald, so its pages post to Skald
    directly: cross-site, with the page's own Origin. Taken only for an Origin
    in the map, answered with CORS for that Origin."""

    def direct(self, origin, fetch_site="cross-site", raw=None):
        h = {"Content-Type": "text/plain", "Sec-Fetch-Site": fetch_site}
        if origin:
            h["Origin"] = origin
        return self.call("POST", "/traffic-beacon", raw or body(), **h)

    def test_a_cross_site_post_goes_to_that_site_s_spool(self):
        status, headers, _ = self.direct(SECOND)
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("X-Skald-Site"), "second.example.net")
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), SECOND)
        self.assertEqual(headers.get("Vary"), "Origin")
        self.assertNotIn("Access-Control-Allow-Credentials", headers)
        today = self.first.now().date()
        self.assertEqual(len(beacon.read_day(self.second.spool, today)), 1)
        self.assertEqual(beacon.read_day(self.first.spool, today), [])
        # www. posting to app. of the same site is same-site: taken too
        status, headers, _ = self.direct(FIRST, "same-site")
        self.assertEqual((status, headers.get("Access-Control-Allow-Origin")), (204, FIRST))
        self.assertEqual(len(beacon.read_day(self.first.spool, today)), 1)

    def test_other_origins_and_no_origin_are_refused(self):
        for origin in ("https://elsewhere.example.org", "http://second.example.net",
                       "https://second.example.net.example.org", "null", None):
            status, headers, _ = self.direct(origin)
            self.assertEqual(status, 403, origin)
            self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, _, _ = self.direct(SECOND, "none")        # not a page's post
        self.assertEqual(status, 403)
        status, _, _ = self.direct(SECOND, "elsewhere")
        self.assertEqual(status, 403)
        today = self.first.now().date()
        self.assertEqual(beacon.read_day(self.second.spool, today), [])

    def test_refusals_for_a_known_origin_still_say_cors_and_keep_their_rules(self):
        status, headers, _ = self.direct(SECOND, raw=b"x" * 2000)
        self.assertEqual((status, headers.get("Access-Control-Allow-Origin")), (413, SECOND))
        status, _, _ = self.direct(SECOND, raw=body(e="nope"))
        self.assertEqual(status, 400)

    def test_no_preflight_and_the_probe(self):
        status, headers, _ = self.call("OPTIONS", "/traffic-beacon", Origin=SECOND)
        self.assertEqual(status, 405)
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        status, headers, _ = self.call("POST", "/traffic-beacon", b"", **{"X-Skald-Probe": "1"})
        self.assertEqual((status, headers.get("X-Skald-Beacon")), (200, "1"))
        self.assertNotIn("X-Skald-Site", headers)
        today = self.first.now().date()
        self.assertEqual(beacon.read_day(self.first.spool, today), [])
        self.assertEqual(self.first.stats, {}, "a probe is not counted, not even as refused")

    def test_direct_and_proxied_posts_are_counted_once_each_by_both_roads(self):
        """nginx logs each answer once, with the site the helper named: the
        audit's count of 204s matches the spool, whichever way a post came."""
        answers = [self.direct(SECOND), self.post(SECOND),             # direct, then proxied
                   self.direct(SECOND, raw=body(e="tel_click")), self.direct(FIRST),
                   self.direct("https://elsewhere.example.org"), self.direct(SECOND, "none")]
        at = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "skald-beacon.log"
            log.write_text("".join(f"{at} {s} {h.get('X-Skald-Site', '-')}\n"
                                   for s, h, _ in answers))
            start = datetime.now(timezone.utc) - timedelta(hours=1)
            end = start + timedelta(hours=2)
            nginx = events.count_answered([log], start, end, "second.example.net", False)
        today = self.second.now().date()
        people, ours, _, _ = events.recount_spool(beacon.day_file(self.second.spool, today))
        self.assertEqual(nginx, 3)
        self.assertEqual(sum(people.values()) + sum(ours.values()), 3)


class AnsweredPerSite(unittest.TestCase):

    def test_nginx_answers_are_counted_per_site(self):
        start = datetime(2026, 10, 18, tzinfo=timezone.utc)
        at = (start + timedelta(hours=1)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "skald-beacon.log"
            log.write_text(f"{at} 204\n"                         # before 2.9.0: the first site's
                           f"{at} 204 example.com\n"
                           f"{at} 204 second.example.net\n"
                           f"{at} 204 second.example.net\n"
                           f"{at} 403 second.example.net\n"
                           f"{at} 403 -\n")
            end = start + timedelta(days=1)
            self.assertEqual(events.count_answered([log], start, end), 4)
            self.assertEqual(events.count_answered([log], start, end, "example.com", True), 2)
            self.assertEqual(events.count_answered([log], start, end,
                                                   "second.example.net", False), 2)


if __name__ == "__main__":
    unittest.main()
