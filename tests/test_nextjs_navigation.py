"""Next.js App Router navigations as page views (COUNTING-TRAPS.md trap 10,
CLASSIFICATION.md "What decides a page view", docs/INGEST.md).

A tap on a link inside a Next.js site sends no HTML request: only
GET /path?_rsc=<hash>. Next.js sends the same URL to prefetch links in view,
with the request header Next-Router-Prefetch. A log that records the header
(the trailing rsc_prefetch= field; Caddy's logged headers) lets Skald count a
navigation as a page view of its path, and never a prefetch. Without the
field nothing changes.

Pinned: every format with and without the field, on both roads (parse.py and
the audit's own reader); prefetch vs navigation; one click logged as an HTML
page and a navigation within 2 seconds is one page view; POST and HEAD are
never one; a visit of navigations alone counts as people; the audit agrees,
and catches a main road that would count differently.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, audit, parse  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import CHROME, UTC, Sandbox  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
CONFIG = {"site": {"hosts": ["example.com"]}}


def at(hour, minute=0, second=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def combined(path="/pricing/?_rsc=1x2y", *, rt=False, host=False, field=None,
             where="end", method="GET", status=200, when=None):
    """A combined line; `field` is the rsc_prefetch value (None: no field),
    `where` puts it at the end or before the quoted host."""
    stamp = (when or at(10)).strftime("%d/%b/%Y:%H:%M:%S +0000")
    out = (f'203.0.113.10 - - [{stamp}] "{method} {path} HTTP/1.1" {status} 512 '
           f'"https://example.com/" "{CHROME}"')
    tail = []
    if rt:
        tail.append("0.012")
    prefetch = f"rsc_prefetch={field}" if field is not None else None
    if host:
        if prefetch and where == "before":
            tail.append(prefetch)
        tail.append('"example.com"')
        if prefetch and where != "before":
            tail.append(prefetch)
    elif prefetch:
        tail.append(prefetch)
    return out + "".join(" " + t for t in tail) + "\n"


def extended(path="/pricing/?_rsc=1x2y", *, field=None, where="end", rid=True,
             method="GET", status=200, when=None, address="203.0.113.10", agent=CHROME):
    """An nginx_extended line, as the reference servers write it."""
    out = (f'{(when or at(10)).isoformat()} {address} example.com "{method} {path} HTTP/2.0" '
           f'{status} 512 "https://example.com/" "{agent}" 0.004 cc=US ray=-')
    prefetch = f" rsc_prefetch={field}" if field is not None else ""
    # Each request its own id (a repeated one is the same request written twice).
    own = hashlib.md5(out.encode()).hexdigest() if rid else ""
    if rid and where == "before":
        return out + prefetch + f" rid={own}\n"
    return out + (f" rid={own}" if rid else "") + prefetch + "\n"


def caddy(path="/pricing/?_rsc=1x2y", header=None, headers=True):
    req = {"client_ip": "203.0.113.10", "host": "example.com", "method": "GET", "uri": path}
    if headers:
        req["headers"] = {"User-Agent": [CHROME], "Referer": ["https://example.com/"]}
        if header is not None:
            req["headers"]["Next-Router-Prefetch"] = [header]
    return json.dumps({"ts": at(10).timestamp(), "status": 200, "size": 512, "request": req})


def main(raw):
    for name in parse.AUTO_ORDER:
        hit = parse.PARSERS[name](raw)
        if hit is not None:
            return hit
    return None


class TestEveryFormat(unittest.TestCase):

    def assert_same_elsewhere(self, with_field, without):
        """The field changes nothing else the line says, on either road."""
        a, b = main(with_field), main(without)
        for name in ("when", "address", "host", "method", "url", "status", "referrer",
                     "user_agent", "country", "request_time", "size", "rid"):
            self.assertEqual(getattr(a, name), getattr(b, name), name)
        x, y = audit.line_hit(with_field), audit.line_hit(without)
        for name in ("when", "address", "host", "method", "url", "status", "referrer",
                     "agent", "country", "rid", "size", "seconds"):
            self.assertEqual(getattr(x, name), getattr(y, name), name)

    def test_combined_in_every_layout(self):
        for rt in (False, True):
            for host in (False, True):
                for where in ("end", "before"):
                    for value in ("-", "1"):
                        with self.subTest(rt=rt, host=host, where=where, value=value):
                            raw = combined(rt=rt, host=host, field=value, where=where)
                            hit, line = main(raw), audit.line_hit(raw)
                            self.assertEqual(hit.rsc_prefetch, value)
                            self.assertEqual(line.prefetch, value)
                            self.assertEqual(hit.host, "example.com" if host else "")
                            self.assertEqual(line.host, hit.host)
                            self.assertEqual(hit.request_time, 0.012 if rt else None)
                            self.assertEqual(line.seconds, hit.request_time)
                            self.assert_same_elsewhere(raw, combined(rt=rt, host=host))
                raw = combined(rt=rt, host=host)
                self.assertIsNone(main(raw).rsc_prefetch)
                self.assertIsNone(audit.line_hit(raw).prefetch)

    def test_extended_with_and_without_the_request_id(self):
        for rid in (True, False):
            for where in ("end", "before"):
                with self.subTest(rid=rid, where=where):
                    raw = extended(field="-", where=where, rid=rid)
                    hit, line = main(raw), audit.line_hit(raw)
                    self.assertEqual((hit.fmt, hit.rsc_prefetch, len(hit.rid)),
                                     ("nginx_extended", "-", 32 if rid else 0))
                    self.assertEqual((line.prefetch, line.rid), ("-", hit.rid))
                    self.assertEqual(hit.country, "US")
                    self.assert_same_elsewhere(raw, extended(rid=rid))
        self.assertIsNone(main(extended()).rsc_prefetch)
        self.assertIsNone(audit.line_hit(extended()).prefetch)

    def test_a_word_that_only_ends_in_the_token_is_not_it(self):
        raw = extended().replace(" ray=-", " ray=-xrsc_prefetch=-")
        self.assertIsNone(main(raw).rsc_prefetch)
        self.assertIsNone(audit.line_hit(raw).prefetch)

    def test_caddy_reads_the_header_whatever_its_case(self):
        sent, absent = caddy(header="1"), caddy()
        self.assertEqual(main(sent).rsc_prefetch, "1")
        self.assertEqual(audit.line_hit(sent).prefetch, "1")
        self.assertTrue(main(absent).soft_navigation)
        self.assertTrue(audit.navigation(audit.line_hit(absent)))
        lower = json.loads(absent)
        lower["request"]["headers"]["next-router-prefetch"] = ["1"]
        self.assertFalse(main(json.dumps(lower)).soft_navigation)
        self.assertFalse(audit.navigation(audit.line_hit(json.dumps(lower))))
        # A record without its headers cannot tell.
        bare = caddy(headers=False)
        self.assertIsNone(main(bare).rsc_prefetch)
        self.assertIsNone(audit.line_hit(bare).prefetch)

    def test_drains_carry_no_request_headers(self):
        vercel = json.dumps({"id": "a1", "proxy": {
            "timestamp": int(at(10).timestamp() * 1000), "method": "GET", "host": "example.com",
            "path": "/pricing/?_rsc=1", "userAgent": [CHROME], "referer": "https://example.com/",
            "statusCode": 200, "clientIp": "203.0.113.10"}})
        edge = json.dumps({"ts": at(10).isoformat(), "ip": "203.0.113.10", "method": "GET",
                           "host": "example.com", "path": "/pricing/?_rsc=1", "status": 200,
                           "ua": CHROME, "id": "r1"})
        for raw in (vercel, edge):
            self.assertIsNone(main(raw).rsc_prefetch)
            self.assertFalse(main(raw).is_page)
            self.assertFalse(audit.is_page(audit.line_hit(raw)))


class TestWhatIsAPage(unittest.TestCase):

    def both(self, raw):
        return main(raw).is_page, audit.is_page(audit.line_hit(raw))

    def test_a_navigation_is_a_page_view_and_a_prefetch_is_not(self):
        self.assertEqual(self.both(extended(field="-")), (True, True))
        self.assertEqual(self.both(extended("/x?page=2&_rsc=9", field="-")), (True, True))
        self.assertEqual(self.both(extended(field="")), (True, True))
        for value in ("1", "2", "4"):       # Next.js's prefetch values
            self.assertEqual(self.both(extended(field=value)), (False, False))
        self.assertEqual(self.both(extended()), (False, False))   # no field: trap 10

    def test_a_cached_navigation_counts_an_error_does_not(self):
        self.assertEqual(self.both(extended(field="-", status=304)), (True, True))
        self.assertEqual(self.both(extended(field="-", status=404)), (False, False))
        self.assertEqual(self.both(extended(field="-", status=308)), (False, False))

    def test_post_and_head_are_never_page_views(self):
        self.assertEqual(self.both(extended("/pricing/?_rsc=1", field="-", method="POST")),
                         (False, False))
        self.assertEqual(self.both(extended("/pricing/", field="-", method="POST")),
                         (False, False))
        self.assertEqual(self.both(extended(field="-", method="HEAD")), (False, False))

    def test_other_payloads_and_assets_stay_out(self):
        self.assertEqual(self.both(extended("/x?_data=routes", field="-")), (False, False))
        self.assertEqual(self.both(extended("/_next/static/a.js?_rsc=1", field="-")),
                         (False, False))
        self.assertEqual(self.both(extended("/api/x?_rsc=1", field="-")), (False, False))

    def test_the_field_changes_nothing_for_an_html_page(self):
        self.assertEqual(self.both(extended("/pricing/", field="1")), (True, True))


def pages_of(raws, when_sorted=True):
    """Page views on both roads, de-duplicated the way each count reads them."""
    hits = [main(r) for r in raws]
    one = [h for h in parse.one_click(parse.in_time_order(iter(hits))) if h.is_page]
    two = [l for l in audit.same_click(audit.in_time_order([audit.line_hit(r) for r in raws]))
           if audit.is_page(l)]
    return [(h.when, h.path) for h in one], [(l.when, l.path) for l in two]


class TestOneClick(unittest.TestCase):

    def test_html_then_navigation_within_two_seconds_is_one_page_view(self):
        raws = [extended("/pricing/", field="-", when=at(10)),
                extended("/pricing/?_rsc=a", field="-", when=at(10, 0, 2))]
        one, two = pages_of(raws)
        self.assertEqual(one, [(at(10), "/pricing/")])
        self.assertEqual(two, one)

    def test_navigation_then_html_is_one_too(self):
        # A soft navigation that falls back to loading the page.
        raws = [extended("/pricing/?_rsc=a", field="-", when=at(10)),
                extended("/pricing/", field="-", when=at(10, 0, 1))]
        one, two = pages_of(raws)
        self.assertEqual(one, [(at(10), "/pricing/")])
        self.assertEqual(two, one)

    def test_out_of_order_lines_still_pair(self):
        raws = [extended("/pricing/?_rsc=a", field="-", when=at(10, 0, 1)),
                extended("/pricing/", field="-", when=at(10))]
        one, two = pages_of(raws)
        self.assertEqual(one, [(at(10), "/pricing/")])
        self.assertEqual(two, one)

    def test_three_seconds_another_path_or_another_visit_are_two(self):
        cases = [
            [extended("/pricing/", field="-", when=at(10)),
             extended("/pricing/?_rsc=a", field="-", when=at(10, 0, 3))],
            [extended("/pricing/", field="-", when=at(10)),
             extended("/about/?_rsc=a", field="-", when=at(10, 0, 1))],
            [extended("/pricing/", field="-", when=at(10)),
             extended("/pricing/?_rsc=a", field="-", when=at(10, 0, 1), address="203.0.113.11")],
            # Two of the same kind are two page views, as two HTML loads are.
            [extended("/pricing/?_rsc=a", field="-", when=at(10)),
             extended("/pricing/?_rsc=b", field="-", when=at(10, 0, 1))],
        ]
        for raws in cases:
            one, two = pages_of(raws)
            self.assertEqual(len(one), 2)
            self.assertEqual(two, one)

    def test_a_prefetch_never_pairs(self):
        raws = [extended("/pricing/?_rsc=a", field="1", when=at(10)),
                extended("/pricing/", field="1", when=at(10, 0, 1))]
        one, two = pages_of(raws)
        self.assertEqual(one, [(at(10, 0, 1), "/pricing/")])
        self.assertEqual(two, one)


def asset(when, address="203.0.113.10"):
    return extended("/_next/static/chunks/app/pricing/page-1a2b.js", field="-", when=when,
                    address=address)


def count(raws, config=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(raws))
        start, end = day_window(DAY, UTC)
        return analyse_window(config or CONFIG, start, end, paths=[path])


class TestCounted(unittest.TestCase):

    def test_a_tab_left_open_counts_as_people_with_its_pages(self):
        """The owner's phone: an open tab, two taps, page chunks loaded, no HTML."""
        raws = [extended("/services/?_rsc=a", field="-", when=at(10)),
                asset(at(10, 0, 1)),
                extended("/contact/?_rsc=b", field="1", when=at(10, 0, 5)),     # prefetch
                extended("/contact/?_rsc=b", field="-", when=at(10, 0, 40)),
                asset(at(10, 0, 41))]
        totals = count(raws)
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.hits, people.visits, people.readers, people.views),
                         (5, 1, 1, 2))
        self.assertNotIn(Group.BOTS, totals.groups)

    def test_without_the_field_it_stays_as_before(self):
        raws = [extended("/services/?_rsc=a", when=at(10)), asset(at(10, 0, 1)),
                extended("/contact/?_rsc=b", when=at(10, 0, 40))]
        totals = count(raws)
        self.assertNotIn(Group.PEOPLE, totals.groups)
        self.assertEqual(totals.groups[Group.BOTS].hits, 3)

    def test_a_landing_page_and_its_clicks(self):
        raws = [extended("/", field="-", when=at(10)), asset(at(10, 0, 1)),
                extended("/pricing/?_rsc=a", field="1", when=at(10, 0, 2)),    # prefetch
                extended("/pricing/?_rsc=a", field="-", when=at(10, 1)),       # the tap
                extended("/pricing/", field="-", when=at(10, 1, 1))]           # its fallback
        people = count(raws).groups[Group.PEOPLE]
        self.assertEqual((people.visits, people.views), (1, 2))


class TestAuditAgrees(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        text = self.box.config.read_text().replace("  require_rendering: false\n", "")
        self.box.config.write_text(text)
        self.box.log([
            extended("/", field="-", when=at(10)), asset(at(10, 0, 1)),
            extended("/pricing/?_rsc=a", field="1", when=at(10, 0, 2)),
            extended("/pricing/?_rsc=a", field="-", when=at(10, 1)),
            extended("/pricing/", field="-", when=at(10, 1, 2)),
            extended("/pricing/?_rsc=c", field="-", method="POST", when=at(10, 1, 9)),
            # A tab left open: navigations and a chunk only.
            extended("/guides/alpha?_rsc=d", field="-", when=at(11), address="203.0.113.20"),
            asset(at(11, 0, 1), "203.0.113.20"),
            extended("/guides/beta?_rsc=e", field="-", when=at(11, 2), address="203.0.113.20"),
        ])

    def tearDown(self):
        self.box.close()

    def collect(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)

    def audit(self):
        return self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())

    def stored(self):
        from skald.store import History
        with History(self.box.db) as h:
            return h.db.execute("SELECT hits, visits, readers, views FROM groups WHERE site = ? "
                                "AND day = ? AND grp = 'people'",
                                ("example.com", DAY.isoformat())).fetchone()

    def test_both_roads_count_the_same(self):
        self.collect()
        self.assertEqual(tuple(self.stored()), (9, 2, 2, 4))
        code, out, err = self.audit()
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_a_main_road_that_keeps_both_halves_of_a_click_is_caught(self):
        with mock.patch("skald.window.one_click", lambda hits: hits):
            self.collect()
        self.assertEqual(self.stored()[3], 5)
        code, out, err = self.audit()
        self.assertEqual(code, 1, out)

    def test_a_main_road_that_counts_prefetches_is_caught(self):
        with mock.patch.object(parse, "NAVIGATION_VALUES", ("-", "", "1")):
            self.collect()
        code, out, err = self.audit()
        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
