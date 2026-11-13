"""#55: every time-ordered list shows the newest on top (the owner's rule, 12 Nov), and a
list cut to a limit keeps the NEWEST rows, never the oldest. One test per list:

- Find a person: the pages seen by its visitor IDs, its conversions, its visits, the
  visits at a lead's time (people/lookup.py, people/visits.posted_near);
- the Conversions lists' journeys (lookup.conversions_listing);
- a visit's page-script visits (people/timeline._script);
- a lead's own visits (people/lead_visits.path), where they first came from still the earliest;
- the open security items of the page and the summary mail (security_notify.py, summary_mail.py).

The pending invites and the recorded sessions are tested beside their own tests
(test_accounts_invites.py, test_recorded_journeys.py), the lead profile and the closed
alerts in node (tests/js/lead-profile.mjs, tests/js/closed-alerts.mjs).
Addresses are RFC 5737; the site is example.com; visitor IDs made up."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import security_notify, summary_mail  # noqa: E402
from skald.conversions import store  # noqa: E402
from skald.people import lead_visits, lookup, timeline, visits  # noqa: E402

SITE = "example.com"
VID = "skv_" + "N" * 22
IP = "203.0.113.55"
AGENT = "Mozilla/5.0 (example)"
CONFIG = {"privacy": {"keep_ips": "full"}, "conversions": {"identity": "full"}}


def stamp(day: int, hour: int = 10, minute: int = 0, second: int = 0) -> str:
    return f"2026-10-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z"


class Store(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.db = store.connect(self.folder / store.FILE)
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row

    def view(self, at: str, path: str, vid: str = VID):
        self.db.execute("INSERT INTO journeys (vid, site, at, path, source_type) VALUES "
                        "(?, ?, ?, ?, 'Search engine')", (vid, SITE, at, path))

    def conv(self, n: int, at: str, vid: str | None = VID, test: int = 0, ref=None):
        self.db.execute("INSERT INTO conversions (site, action, stage, at, vid, external_ref, "
                        "tool, received_at, test) VALUES (?, 'demo', 'completed', ?, ?, ?, "
                        "'lead', ?, ?)", (SITE, at, vid, ref or f"ref-{n}", at, test))

    def visit(self, seq: int, start: str, end: str, landing: str, posts=(), ip=IP, day="2026-10-05"):
        self.db.execute("INSERT INTO visits (site, day, seq, ip, user_agent, start, end, landing, "
                        "pages, trail, posts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                        (SITE, day, seq, ip, AGENT, start, end, landing,
                         json.dumps([[landing, "page", 0]]), json.dumps(list(posts))))

    def find(self, q):
        self.db.commit()
        return lookup.person(CONFIG, self.folder, SITE, q, None)


class FindAPerson(Store):
    def test_pages_seen_by_its_visitor_ids_keep_the_newest(self):
        for day in range(1, 6):
            self.view(stamp(day), f"/p{day}/")
        self.view(stamp(4), "/other/", vid="skv_" + "O" * 22)     # another browser: not its
        with mock.patch.object(lookup, "LIMIT", 3):
            got = self.find(VID)
        self.assertEqual([j["path"] for j in got["journeys"]], ["/p5/", "/p4/", "/p3/"],
                         "newest on top; the oldest two are the ones left out")

    def test_its_conversions_keep_the_newest(self):
        for day in range(1, 6):
            self.conv(day, stamp(day))
        with mock.patch.object(lookup, "LIMIT", 3):
            got = self.find(VID)
        self.assertEqual([c["external_ref"] for c in got["conversions"]],
                         ["ref-5", "ref-4", "ref-3"])

    def test_its_visits_keep_the_newest(self):
        for seq, day in enumerate((2, 5, 3, 1)):
            self.visit(seq, stamp(day), stamp(day, 10, 5), f"/v{day}/", day=f"2026-10-{day:02d}")
        with mock.patch.object(lookup, "LIMIT", 2):
            got = self.find(IP)
        self.assertEqual([v["landing"] for v in got["visits"]], ["/v5/", "/v3/"])

    def test_visits_at_a_lead_time_newest_first(self):
        at = stamp(5, 12, 0, 0)
        self.visit(1, stamp(5, 11, 50), stamp(5, 12, 0, 10), "/older/", posts=[stamp(5, 11, 59, 40)])
        self.visit(2, stamp(5, 11, 58), stamp(5, 12, 0, 20), "/newer/", posts=[stamp(5, 11, 59, 50)],
                   ip="198.51.100.7")
        self.db.commit()
        got = visits.posted_near(self.db, SITE, at)
        self.assertEqual([v["landing"] for v in got], ["/newer/", "/older/"])

    def test_the_conversions_list_journey_keeps_the_newest_200(self):
        self.conv(1, stamp(20), test=1)
        for i in range(205):
            self.view(f"2026-10-{1 + i // 24:02d}T{i % 24:02d}:00:00Z", f"/j{i}/")
        self.db.commit()
        rows = lookup.conversions_listing(CONFIG, self.folder, SITE, "test", True)["rows"]
        journey = [j["path"] for j in rows[0]["journey"]]
        self.assertEqual(len(journey), 200)
        self.assertEqual((journey[0], journey[-1]), ("/j5/", "/j204/"),
                         "the newest 200 kept (the 5 oldest left out), read as a path in time order")


class VisitAndLead(Store):
    def test_page_script_visits_keep_the_newest(self):
        for day in range(1, 6):
            self.view(stamp(day), f"/s{day}/")          # a day apart: one visit each
        self.db.commit()
        with mock.patch.object(timeline, "LIMIT", 3):
            got = timeline._script(self.db, SITE, {VID}, [])
        self.assertEqual(sorted(v["landing"] for v in got), ["/s3/", "/s4/", "/s5/"])

    def test_a_lead_visits_keep_the_newest_and_the_first_stays_the_earliest(self):
        # The proven visit sent the form; three later visits from the same address and browser.
        self.visit(0, stamp(5, 9), stamp(5, 9, 5), "/proven/", posts=[stamp(5, 9, 2)])
        for seq, hour in ((1, 12), (2, 15), (3, 18)):
            self.visit(seq, stamp(5, hour), stamp(5, hour, 5), f"/likely-{hour}/")
        self.db.commit()
        lead = [{"at": stamp(5, 9, 2, 3), "action": "demo", "stage": "completed", "tool": "lead"}]
        with mock.patch.object(lead_visits, "LIMIT", 2):
            got = lead_visits.path(self.db, SITE, lead)
        self.assertEqual([v["landing"] for v in got["visits"]],
                         ["/likely-18/", "/likely-15/", "/proven/"],
                         "newest on top; the limit keeps the newest likely ones")
        self.assertEqual(got["first"]["landing"], "/proven/", "first came from: the earliest")


class SecurityItems(unittest.TestCase):
    def test_open_items_newest_first_on_the_page_and_in_the_mail(self):
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        security_notify._ready(db)
        for item, first, closed in (("a", stamp(1), None), ("c", stamp(9), None),
                                    ("b", stamp(5), None), ("z", stamp(12), stamp(13))):
            db.execute("INSERT INTO security_items (site, item, kind, title, todo, first_at, "
                       "last_seen_at, closed_at) VALUES (?, ?, 'exposure', ?, 'fix it', ?, ?, ?)",
                       (SITE, item, f"item {item}", first, first, closed))
        self.assertEqual([i["item"] for i in security_notify.open_items(db, SITE)], ["c", "b", "a"])
        self.assertEqual([i["item"] for i in security_notify.public(db, SITE)["open"]],
                         ["c", "b", "a"])
        self.assertEqual([i["item"] for i in summary_mail.security_part(db, SITE, {})],
                         ["c", "b", "a"], "the summary mail too; the closed one is not listed")


if __name__ == "__main__":
    unittest.main()
