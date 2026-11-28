"""SKALD-69 (GitHub #118): "Hidden referral", split out of Direct by the
browser's Sec-Fetch-Site header.

A page view with no referrer and no tag whose request carried
`Sec-Fetch-Site: cross-site` is a Hidden referral; `none`, any other value
and a line without the header stay "Direct or unknown". Covered here: the
field read from every log shape on both roads (parse.py and the audit's own
reader), the label on both roads, only a page view's header counting, no
visit split inside the gap, "likely sent by an AI assistant" looking at both,
"Direct, likely" at Direct only, and a collected day whose audit agrees.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import (ai_likely, audit, audit_labels, audit_lines,  # noqa: E402
                          dimensions as dim, ingest_drain, parse)
from skald.hidden_names import CROSS_SITE, HIDDEN  # noqa: E402

from support import ASKED, CHROME, Sandbox, totals_for  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
DIRECT = "Direct or unknown"
OWN = {"example.com"}
RID = "0123456789abcdef0123456789abcdef"


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=UTC)


def nav(when: datetime, address: str = "203.0.113.10", path: str = "/",
        site: str | None = None, referrer: str = "-", agent: str = CHROME,
        rid: str = "", status: int = 200) -> str:
    """One nginx extended line, with ` sec_fetch_site=<site>` before rid=
    when `site` is given ("-": the header was not sent)."""
    tail = f" sec_fetch_site={site}" if site is not None else ""
    tail += f" rid={rid}" if rid else ""
    return (f'{when.isoformat()} {address} example.com "GET {path} HTTP/2.0" {status} 512 '
            f'"{referrer}" "{agent}" 0.004 cc=US ray=0000000000000000-LHR{tail}\n')


def combined(site: str | None, host_last: bool = True) -> str:
    field = f" sec_fetch_site={site}" if site is not None else ""
    head = ('203.0.113.20 - - [05/Oct/2026:10:00:00 +0000] "GET /a HTTP/1.1" 200 10 "-" '
            f'"{CHROME}" 0.010')
    return head + (field + ' "example.com"' if host_last else ' "example.com"' + field) + "\n"


def caddy(headers: dict | None) -> str:
    req = {"client_ip": "203.0.113.30", "host": "example.com", "method": "GET", "uri": "/"}
    if headers is not None:
        req["headers"] = headers
    return json.dumps({"ts": at(10).timestamp(), "status": 200, "size": 10,
                       "request": req}) + "\n"


def edge(**extra) -> str:
    row = {"ts": "2026-10-05T10:00:00Z", "ip": "203.0.113.40", "method": "GET",
           "host": "example.com", "path": "/", "status": 200, "bytes": 10, "referer": "",
           "ua": CHROME, "cache": "HIT", "id": "abc-LHR"}
    row.update(extra)
    return json.dumps(row) + "\n"


def main_hit(raw: str) -> parse.Hit:
    for name in parse.AUTO_ORDER:
        got = parse.PARSERS[name](raw)
        if got is not None:
            return got
    raise AssertionError("no parser read " + raw)


class TheField(unittest.TestCase):
    """Both roads read the header from every log shape that can carry it."""

    CASES = [
        ("extended cross-site", nav(at(10), site="cross-site", rid=RID), "cross-site"),
        ("extended none", nav(at(10), site="none"), "none"),
        ("extended not sent", nav(at(10), site="-", rid=RID), ""),
        ("extended upper case", nav(at(10), site="Cross-Site"), "cross-site"),
        ("extended without the field", nav(at(10), rid=RID), None),
        ("combined, host last", combined("cross-site"), "cross-site"),
        ("combined, field last", combined("same-origin", host_last=False), "same-origin"),
        ("combined without", combined(None), None),
        ("caddy with the header", caddy({"Sec-Fetch-Site": ["cross-site"]}), "cross-site"),
        ("caddy, header not sent", caddy({"User-Agent": [CHROME]}), ""),
        ("caddy without headers", caddy(None), None),
        ("edge with fetch_site", edge(fetch_site="cross-site"), "cross-site"),
        ("edge, header not sent", edge(fetch_site=""), ""),
        ("edge from an older Worker", edge(), None),
    ]

    def test_both_roads_read_the_same_value(self):
        for name, raw, want in self.CASES:
            with self.subTest(name):
                self.assertEqual(main_hit(raw).fetch_site, want)
                self.assertEqual(audit_lines.line_hit(raw).fetch_site, want)

    def test_the_other_trailing_fields_still_read(self):
        raw = nav(at(10), site="cross-site", rid=RID)
        hit, mine = main_hit(raw), audit_lines.line_hit(raw)
        self.assertEqual((hit.rid, mine.rid), (RID, RID))
        self.assertEqual((hit.request_time, mine.seconds), (0.004, 0.004))
        for host_last in (True, False):
            raw = combined("cross-site", host_last)
            self.assertEqual(main_hit(raw).host, "example.com")
            self.assertEqual(audit_lines.line_hit(raw).host, "example.com")
        raw = ('203.0.113.20 - - [05/Oct/2026:10:00:00 +0000] "GET /a?_rsc=1 HTTP/1.1" 200 10 "-" '
               f'"{CHROME}" rsc_prefetch=- sec_fetch_site=same-origin request_length=900\n')
        hit, mine = main_hit(raw), audit_lines.line_hit(raw)
        self.assertEqual((hit.rsc_prefetch, hit.request_length, hit.fetch_site),
                         ("-", 900, "same-origin"))
        self.assertEqual((mine.prefetch, mine.length, mine.fetch_site), ("-", 900, "same-origin"))

    def test_an_odd_caddy_header_value_is_read_as_text_on_both_roads(self):
        raw = caddy({"Sec-Fetch-Site": [5]})
        self.assertEqual(main_hit(raw).fetch_site, "5")
        self.assertEqual(audit_lines.line_hit(raw).fetch_site, "5")

    def test_the_ingest_endpoint_keeps_the_workers_field(self):
        kind, kept = ingest_drain.keep(json.loads(edge(fetch_site="cross-site")), "edge")
        self.assertEqual(kind, "line")
        self.assertEqual(json.loads(kept)["fetch_site"], "cross-site")
        self.assertEqual(main_hit(kept + "\n").fetch_site, "cross-site")

    def test_the_worker_scripts_send_it(self):
        root = Path(__file__).resolve().parent.parent / "deploy"
        for script in ("cloudflare-worker/skald-edge.js", "netlify-edge-function/skald-edge.js"):
            self.assertIn('fetch_site: request.headers.get("sec-fetch-site") || ""',
                          (root / script).read_text())


class TheLabel(unittest.TestCase):
    """dimensions.source_type and audit_labels.source_of agree on every case."""

    CASES = [
        # (referrer, url, cited, fetch_site, want)
        ("", "/", False, CROSS_SITE, HIDDEN),
        ("", "/", False, "none", DIRECT),
        ("", "/", False, "same-origin", DIRECT),
        ("", "/", False, "same-site", DIRECT),
        ("", "/", False, "", DIRECT),
        ("", "/", False, None, DIRECT),
        ("https://www.google.com/", "/", False, CROSS_SITE, "Search engine"),
        ("https://example.com/a", "/", False, CROSS_SITE, "This site"),
        ("https://checkout.stripe.com/", "/", False, CROSS_SITE, "Returned from payment"),
        ("", "/?utm_source=newsletter&utm_medium=email", False, CROSS_SITE, "Email"),
        ("", "/?utm_source=foo", False, CROSS_SITE, "Tagged link"),
        ("", "/?gclid=abc", False, CROSS_SITE, "Search engine"),
        ("https://chatgpt.com/", "/", True, CROSS_SITE, "AI assistant"),
    ]

    def test_both_roads(self):
        for referrer, url, cited, site, want in self.CASES:
            with self.subTest(referrer=referrer, url=url, site=site):
                self.assertEqual(dim.source_type(referrer, url, cited, OWN, site), want)
                line = audit_lines.line_hit(nav(at(10), path=url, referrer=referrer or "-",
                                                site=site if site is not None else None))
                if site == "":
                    line.fetch_site = ""
                self.assertEqual(audit_labels.source_of(line, cited, OWN), want)

    def test_only_a_page_views_header_counts(self):
        page = main_hit(nav(at(10), "/guide", site=CROSS_SITE))
        image = main_hit(nav(at(10), path="/logo.png", site=CROSS_SITE))
        api = main_hit(nav(at(10), path="/api/x", site=CROSS_SITE))
        self.assertEqual(page.navigation_site, CROSS_SITE)
        self.assertIsNone(image.navigation_site)
        self.assertIsNone(api.navigation_site)
        self.assertIsNone(main_hit(nav(at(10), status=301, site=CROSS_SITE)).navigation_site)

    def test_a_visit_says_where_it_came_from(self):
        from skald import visits
        self.assertEqual(visits.came_from({"source": HIDDEN}),
                         "a click from a site that hid its address (no referrer, no tag)")
        self.assertEqual(visits.came_from({"source": DIRECT}), "direct (no referrer, no tag)")

    def test_it_is_a_source_type_and_an_inside_one(self):
        self.assertIn(HIDDEN, dim.SOURCE_TYPES)
        self.assertIn(HIDDEN, dim.INSIDE_SOURCES)
        self.assertEqual(ai_likely.NO_REFERRER, (DIRECT, HIDDEN))

    def test_it_never_opens_a_visit_on_either_road(self):
        came = dim.page_origin("https://www.google.com/", "/", False, OWN, None)
        here = dim.page_origin("", "/b", False, OWN, CROSS_SITE)
        self.assertEqual(here[0], HIDDEN)
        self.assertFalse(dim.new_source(here, came))
        self.assertFalse(audit._elsewhere((HIDDEN, "(none)", "(no campaign tag)"),
                                          ("Search engine", "google.com", "(no campaign tag)")))


class TheDay(unittest.TestCase):
    """A day tallied in memory: readers, visits and the inferred figures."""

    def lines(self):
        return [
            nav(at(9), "203.0.113.10", "/a", site=CROSS_SITE),           # Hidden referral
            nav(at(9, 5), "203.0.113.10", "/b", site=CROSS_SITE),        # same visit
            nav(at(9, 6), "203.0.113.10", "/logo.png", site=CROSS_SITE),
            nav(at(9, 1), "203.0.113.11", "/a", site="none"),            # Direct
            nav(at(9, 2), "203.0.113.12", "/a"),                         # Direct, no field
            nav(at(9, 3), "203.0.113.13", "/a", site=CROSS_SITE,
                referrer="https://www.google.com/"),                     # Search engine
            # A Direct visit, then a hidden click 10 minutes later: still one visit.
            nav(at(11), "203.0.113.14", "/c", site="none"),
            nav(at(11, 10), "203.0.113.14", "/d", site=CROSS_SITE),
            # An image another site shows: no page view, no reader.
            nav(at(12), "203.0.113.15", "/hero.jpg", site=CROSS_SITE),
        ]

    def test_readers_and_visits_by_source(self):
        totals = totals_for(self.lines())
        sources = [j["source"] for j in totals.journeys]
        self.assertEqual(sorted(sources), sorted([HIDDEN, DIRECT, DIRECT, "Search engine",
                                                  DIRECT]))
        self.assertEqual(len(totals.journeys), 5)       # the hidden click split nothing

    def test_the_same_lines_without_the_field_count_the_same_visits(self):
        bare = [ln.replace(f" sec_fetch_site={CROSS_SITE}", "").replace(" sec_fetch_site=none", "")
                for ln in self.lines()]
        with_field, without = totals_for(self.lines()), totals_for(bare)
        self.assertEqual(len(with_field.journeys), len(without.journeys))
        self.assertEqual([j["source"] for j in without.journeys].count(HIDDEN), 0)

    def test_likely_ai_looks_at_hidden_referrals_and_likely_direct_does_not(self):
        lines = [nav(at(10), "198.51.100.40", "/pricing/", agent=ASKED),
                 nav(at(10, 3), "203.0.113.10", "/pricing/", site=CROSS_SITE),
                 nav(at(10, 4), "203.0.113.11", "/pricing/", site="none"),
                 nav(at(10, 5), "203.0.113.12", "/?session_id=cs_test_1", site=CROSS_SITE)]
        totals = totals_for(lines)
        likely = totals.extras["ai_likely"]
        self.assertEqual((likely["direct"], likely["likely"]), (3, 2))
        marked = {j["start"][11:16]: (j["source"], j.get("likely_ai")) for j in totals.journeys}
        self.assertEqual(marked["10:03"][0], HIDDEN)
        self.assertEqual(marked["10:03"][1]["name"], "chatgpt.com")
        self.assertEqual(marked["10:04"][1]["name"], "chatgpt.com")
        direct = totals.extras["direct_likely"]
        self.assertEqual(direct["direct"], 1)           # the "none" visit only
        self.assertEqual(direct["reasons"]["checkout"], 0)

    def test_a_lead_or_sale_after_a_hidden_referral_can_be_likely_ai(self):
        from skald import audit_conversions_figures, conversions_data
        row = {"first_source": HIDDEN, "first_touch_at": "2026-10-05T10:03:00Z",
               "landing": "/pricing/", "filled": None, "vid": None}
        for source, want in ((HIDDEN, "chatgpt.com"), (DIRECT, "chatgpt.com"),
                             ("Search engine", "(none)")):
            got = conversions_data.likely_label(None, dict(row, first_source=source),
                                                None, UTC)
            mine = audit_conversions_figures._likely(source, None, "/pricing/", None, 15, UTC)
            with self.subTest(source=source):
                # Both roads ask the fetches only for a visit with no referrer.
                self.assertEqual(got == "(none)", want == "(none)")
                self.assertEqual(mine == "(none)", want == "(none)")


class CollectAndAudit(unittest.TestCase):
    """A day collected with the field: stored right, and the audit's own road agrees."""

    def setUp(self):
        self.box = Sandbox()
        self.box.log(TheDay().lines()
                     + [nav(at(13), "198.51.100.40", "/pricing/", agent=ASKED),
                        nav(at(13, 2), "203.0.113.20", "/pricing/", site=CROSS_SITE)])

    def tearDown(self):
        self.box.close()

    def stored(self, kind: str) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return dict(db.execute("SELECT name, n FROM counts WHERE site = 'example.com' "
                                   "AND day = ? AND kind = ?", (DAY.isoformat(), kind)))
        finally:
            db.close()

    def test_collected_and_audited(self):
        code, _, err = self.box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err)
        self.assertEqual(self.stored("reader_source"),
                         {HIDDEN: 2, DIRECT: 3, "Search engine": 1})
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)

    def test_a_planted_label_is_caught(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect", "--day",
                                      DAY.isoformat())[0], 0)
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE counts SET name = ? WHERE kind = 'reader_source' AND name = ?",
                       (DIRECT + " x", HIDDEN))
        db.close()
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertNotEqual(code, 0, out)

    def quality(self, change) -> None:
        db = sqlite3.connect(str(self.box.db))
        with db:
            row = db.execute("SELECT data FROM day_extras WHERE site = 'example.com' AND day = ? "
                             "AND kind = 'quality'", (DAY.isoformat(),)).fetchone()
            blob = json.loads(row[0])
            change(blob)
            db.execute("UPDATE day_extras SET data = ? WHERE site = 'example.com' AND day = ? "
                       "AND kind = 'quality'", (json.dumps(blob), DAY.isoformat()))
        db.close()

    def test_a_day_stored_before_the_rule_is_audited_as_it_was_counted(self):
        # A Caddy log held the header before Skald read it: a day the older release
        # counted has no Hidden referral and no marker, and must still match.
        with mock.patch.object(dim, "CROSS_SITE", "(not read)"):
            self.assertEqual(self.box.run("--today", TODAY, "collect", "--day",
                                          DAY.isoformat())[0], 0)
        self.assertNotIn(HIDDEN, self.stored("reader_source"))
        self.quality(lambda q: q.pop("hidden_referral"))
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertEqual(code, 0, err + out)
        # The marker is what lets it pass: with it, the audit reads the header and disagrees.
        self.quality(lambda q: q.update(hidden_referral=True))
        code, out, err = self.box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
        self.assertNotEqual(code, 0, out)

    def test_a_new_day_carries_the_marker(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect", "--day",
                                      DAY.isoformat())[0], 0)
        got = {}
        self.quality(got.update)
        self.assertIs(got["hidden_referral"], True)
        self.assertTrue(audit_labels.hidden_counted(got))
        self.assertFalse(audit_labels.hidden_counted({"lines": 3}))
        self.assertFalse(audit_labels.hidden_counted(None))
        self.assertTrue(audit_labels.stored_hidden(self.box.db, "example.com", DAY))
        self.assertTrue(audit_labels.stored_hidden(self.box.db, "example.com", date(2026, 1, 1)))

    def test_the_live_snapshot_is_audited_too(self):
        code, _, err = self.box.run("--today", DAY.isoformat(), "live")
        self.assertEqual(code, 0, err)
        code, out, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err + out)


if __name__ == "__main__":
    unittest.main()
