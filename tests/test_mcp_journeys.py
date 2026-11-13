"""MCP page_journeys (2.49, #51): how people reach pages and where they go next.

Against example journeys in a fixture history. Pinned: a visit counts once per
page however often it read it; it landed on the page only when that was its
first page view, else it came from the page just before; next is the page just
after the last reading, or left the site; new / returning and lead / customer
come from the visit; the newest visits come first; days before the oldest kept
journey are named as not kept, never 0; a day with no counted visits is named;
the second count (audit_page_journeys.py) agrees and catches a planted change."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_mcp_support import SITE, Fixture  # noqa: E402
from skald import audit_page_journeys  # noqa: E402
from skald.mcp import protocol, tools_journeys  # noqa: E402
from skald.store import History  # noqa: E402

DAYS = ["2026-10-02", "2026-10-03", "2026-10-04"]       # 10-01 not kept; 10-05 not counted


def visit(day, seq, start, pages, source="Search engine", via="google.com", returning=False,
          country="CA", device="Desktop", extra=()):
    trail = [[p, "page"] for p in pages] + [list(x) for x in extra]
    return {"day": day, "seq": seq, "start": f"{day}T{start}", "trail": trail, "pages": len(pages),
            "source": source, "via": via, "ref_host": via, "returning": returning,
            "country": country, "device": device, "landing": pages[0], "exit": pages[-1],
            "seconds": 60}


VISITS = [
    visit(DAYS[0], 0, "09:00", ["/", "/pricing/", "/demo/"]),
    visit(DAYS[0], 1, "10:00", ["/pricing/"], source="AI assistant", via="chatgpt.com"),
    visit(DAYS[1], 0, "08:00", ["/blog/", "/pricing/", "/blog/", "/pricing/", "/demo/"],
          returning=True, country="US"),
    visit(DAYS[2], 0, "11:00", ["/pricing/", "/"], source="Direct or unknown", via="",
          device="Mobile", extra=[("/pricing/", "app")]),
    visit(DAYS[2], 1, "11:00", ["/about/"]),
]


def setUpModule():
    global FX
    FX = Fixture()
    with History(FX.box.db) as h:
        # This module's own visits only: the shared fixture's are set aside.
        h.db.execute("DELETE FROM journeys WHERE site = ?", (SITE,))
        h.db.execute("UPDATE days SET journeys = NULL WHERE site = ?", (SITE,))
        for v in VISITS:
            data = {k: v[k] for k in v if k != "day"}
            h.db.execute("INSERT INTO journeys (site, day, seq, data) VALUES (?, ?, ?, ?)",
                         (SITE, v["day"], v["seq"], json.dumps(data)))
        for d in DAYS:
            h.db.execute("INSERT OR REPLACE INTO days (site, day, timezone, collected_at, verified, "
                         "parsed, hits, other_hosts, cited_visits, journeys) "
                         "VALUES (?, ?, 'UTC', '2026-10-06T00:00:00+00:00', 1, 1, 1, 0, 0, 1)",
                         (SITE, d))
        h.db.commit()


def tearDownModule():
    FX.close()


def call(**args):
    got = protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "page_journeys", "arguments": args}},
                          FX.context(default_site=SITE))
    return got["result"]


class PageJourneys(unittest.TestCase):
    def ok(self, **args):
        r = call(**args)
        self.assertIs(r["isError"], False, r["content"][0]["text"])
        return r["structuredContent"], r["content"][0]["text"]

    def pages(self, s):
        return {p["path"]: p for p in s["pages"]}

    def test_how_people_reach_the_page_and_where_they_go(self):
        s, text = self.ok(paths=["/pricing/", "/demo/"], **{"from": "2026-10-01", "to": "2026-10-05"})
        p = self.pages(s)["/pricing/"]
        self.assertEqual(p["visits"], 4)                        # read twice in one visit: once
        self.assertEqual(p["arrived"]["landed_here"], 2)
        self.assertEqual({x["value"]: x["visits"] for x in p["arrived"]["landed_from"]},
                         {"AI assistant: chatgpt.com": 1, "Direct": 1})   # the MCP says Direct
        self.assertEqual({x["value"]: x["visits"] for x in p["arrived"]["from_page"]},
                         {"/": 1, "/blog/": 1})                  # the first reading's page before
        self.assertEqual({x["value"]: x["visits"] for x in p["next"]},
                         {"/demo/": 2, "/": 1, tools_journeys.LEFT: 1})   # after the last reading
        self.assertEqual(p["left"], 1)
        self.assertEqual((p["who"]["new"], p["who"]["returning"]), (3, 1))
        self.assertEqual([v["day"] for v in p["latest"]], ["2026-10-04", "2026-10-03",
                                                           "2026-10-02", "2026-10-02"])
        self.assertEqual(p["latest"][0]["pages"], ["/pricing/", "/"])   # the app step is no page
        self.assertEqual(self.pages(s)["/demo/"]["visits"], 2)
        self.assertIn("/pricing/: 4 visit(s).", text)

    def test_days_not_kept_and_not_counted_are_named_never_zero(self):
        s, text = self.ok(paths=["/pricing/"], **{"from": "2026-10-01", "to": "2026-10-05"})
        self.assertEqual(s["kept_from"], "2026-10-02")
        self.assertEqual(s["not_kept"], ["2026-10-01"])
        self.assertEqual(s["missing_days"], ["2026-10-05"])
        self.assertIn("not kept (not counted, not 0)", text)

    def test_a_page_nobody_read_is_zero_over_kept_days(self):
        s, _ = self.ok(paths=["/nobody/"], **{"from": "2026-10-02", "to": "2026-10-04"})
        self.assertEqual(self.pages(s)["/nobody/"]["visits"], 0)
        self.assertEqual(s["not_kept"], [])

    def test_the_default_range_ends_on_the_newest_counted_day(self):
        s, _ = self.ok(paths=["/"])
        self.assertEqual((s["from"], s["to"]), ("2026-09-28", "2026-10-04"))

    def test_bad_asks_are_refused(self):
        for args in ({"paths": ["pricing"]}, {"paths": []},
                     {"paths": ["/"], "from": "2026-10-05", "to": "2026-10-01"}):
            r = call(**args)
            self.assertIs(r["isError"], True, args)


class SecondCount(unittest.TestCase):
    def test_the_audit_agrees(self):
        with History(FX.box.db) as h:
            problems, n = audit_page_journeys.check(h.db, SITE)
        self.assertEqual(problems, [])
        self.assertGreater(n, 0)

    def test_the_audit_catches_a_changed_figure(self):
        real = tools_journeys.one_page

        def off_by_one(path, js, latest=tools_journeys.LATEST):
            got = real(path, js, latest)
            if path == "/pricing/":
                got["visits"] += 1
            return got
        tools_journeys.one_page = off_by_one
        try:
            with History(FX.box.db) as h:
                problems, _ = audit_page_journeys.check(h.db, SITE)
        finally:
            tools_journeys.one_page = real
        self.assertTrue(any("/pricing/" in p and "visits" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
