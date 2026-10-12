"""Leads everywhere (2.5.0): conversions.json's `today` listing and lead
lists, the lead findings in insights.json (conversions_leads.py), and their
second count (audit_conversions_leads.py): exact rows, test rows marked and
never counted, a tampered listing or finding withheld. Addresses are
RFC 5737; hosts example.com."""
from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_conversions_data as base  # noqa: E402
from test_conversions_beacon import T, VID2, body  # noqa: E402

from skald import audit_conversions_leads, conversions_leads  # noqa: E402
from skald.conversions import LEAD_ACTIONS, store  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 11)
TODAY = base.TODAY


def own_tests(cls):
    """The fixture's own tests are run in their module, not again here."""
    for name in dir(base.Data):
        if name.startswith("test") and name not in cls.__dict__:
            setattr(cls, name, None)
    return cls


@own_tests
class Today(base.Data):
    def setUp(self):
        super().setUp()
        # VID2 comes back today and sends the contact form; a third browser books a demo.
        self.now = T + 2 * 86400 - 3600
        self.post(body(e="form_submit", p="/contact/", v=VID2))
        self.now = T + 2 * 86400 - 1800
        self.post(body(e="calendly_booked", p="/pricing/", v="skv_" + "Z" * 22))

    def mark_demo_test(self):
        db = store.connect(self.db_path)
        try:
            cid = db.execute("SELECT id FROM conversions WHERE action = 'demo' AND at >= ?",
                             ("2026-10-13",)).fetchone()[0]
            store.mark_test(db, "example.com", [cid])
        finally:
            db.close()

    def test_lists_and_lead_actions(self):
        got = self.blob()
        self.assertEqual(got["lead_actions"], list(LEAD_ACTIONS))
        self.assertEqual(got["demo_actions"], ["demo"])
        block = got["today"]
        self.assertEqual((block["day"], block["state"], block["total"], block["tests"]),
                         (TODAY.isoformat(), "ok", 2, 0))
        self.assertEqual([(r["action"], r["stage"]) for r in block["rows"]],
                         [("demo", "completed"), ("contact", "completed")], "newest first")
        self.assertTrue(all(r["at"].startswith(TODAY.isoformat()) for r in block["rows"]))
        self.assertNotIn(VID2, str(block), "anonymous")
        self.assertEqual(self.day(got, TODAY)["stages"],
                         {"contact": {"completed": 1}, "demo": {"completed": 1}})

    def test_test_rows_are_listed_and_never_counted(self):
        self.mark_demo_test()
        got = self.blob()
        block = got["today"]
        self.assertEqual((block["state"], block["total"], block["tests"]), ("ok", 2, 1))
        self.assertEqual([r["test"] for r in block["rows"]], [True, False])
        self.assertEqual(self.day(got, TODAY)["stages"], {"contact": {"completed": 1}})

    def test_a_tampered_listing_is_withheld(self):
        real = conversions_leads.today_block

        def lose_one(*a, **k):
            got = real(*a, **k)
            got["rows"] = got["rows"][1:]
            got["total"] -= 1
            return got
        with mock.patch.object(conversions_leads, "today_block", lose_one):
            got = self.blob()
        self.assertEqual(got["today"]["state"], "withheld")
        self.assertIn("SQL recount", got["today"]["why"])
        self.assertIn("today", got["withheld"])

    def test_a_withheld_day_withholds_its_listing(self):
        db = store.connect(self.db_path)
        try:
            got = conversions_leads.today_block(db, "example.com", UTC, TODAY,
                                                {TODAY.isoformat()})
        finally:
            db.close()
        self.assertEqual(got["state"], "withheld")
        self.assertNotIn("rows", got)

    def test_not_audited_is_not_checked(self):
        got = self.blob(audited=False)
        self.assertEqual(got["today"]["state"], "ok")


@own_tests
class Recount(base.Data):
    def item(self, kind, name, after, before=None, **more):
        return {"subject": {"kind": kind, "name": name}, "after": after, "before": before,
                "period": {"after": [DAY.isoformat(), DAY.isoformat()],
                           "before": (None if before is None else
                                      [(DAY - timedelta(days=1)).isoformat()] * 2)},
                "title": f"{kind} {name}", "type": "working", **more}

    def test_findings_against_sql(self):
        # The fixture's day: two demos booked (one landed on /pricing/, one not recorded).
        good = [self.item("site", "leads", 2, 0), self.item("country", "CA", 2, 0),
                self.item("page", "/pricing/", 1, None, top=True, of=2)]
        self.assertEqual(audit_conversions_leads.check_insights(self.db_path, "example.com",
                                                                UTC, good), {})
        bad = [self.item("site", "leads", 3, 0), self.item("country", "CA", 2, 1),
               self.item("page", "/", 2, None, top=True, of=2), self.item("referrer", "x", 1)]
        got = audit_conversions_leads.check_insights(self.db_path, "example.com", UTC, bad)
        self.assertEqual(sorted(got), [0, 1, 2, 3])
        self.assertIn("SQL recount 2", got[0][0])
        self.assertIn("leader is '/pricing/'", got[2][0])

    def test_add_to_leaves_out_and_names(self):
        items = [self.item("site", "leads", 2, 0), self.item("site", "leads", 9, 0)]
        items[1]["title"] = "planted"
        with mock.patch.object(conversions_leads, "insights", lambda *a: items):
            got = conversions_leads.add_to({"insights": [], "today": []}, {"available": True},
                                           DAY, {}, self.db_path, "example.com", UTC)
        self.assertEqual([i["title"] for i in got["insights"]], ["site leads"])
        self.assertEqual(len(got["leads_withheld"]), 1)
        self.assertTrue(got["leads_withheld"][0].startswith("planted:"))


def _blob(per_day: dict, first: date, last: date, held=()) -> dict:
    """A conversions.json with `ok` days first..last; per_day {day: {source: leads}}."""
    days = []
    d = first
    while d <= last:
        src = per_day.get(d, {})
        if d.isoformat() in held:
            days.append({"day": d.isoformat(), "state": "withheld", "why": "x"})
        else:
            n = sum(src.values())
            days.append({"day": d.isoformat(), "state": "ok",
                         "stages": {"contact": {"completed": n, "started": 4},
                                    "paid": {"paid": 7}} if n else {"paid": {"paid": 7}},
                         "by": {"source_type": {"contact": dict(src), "paid": {"Email": 7}},
                                "landing": {"contact": {"/pricing/": n}} if n else {},
                                "country": {"contact": {"Unknown": n}} if n else {}}})
        d += timedelta(days=1)
    return {"available": True, "days": days}


class Findings(unittest.TestCase):
    anchor = date(2026, 10, 12)

    def week(self, before: dict, after: dict) -> dict:
        per = {}
        for i in range(7):
            per[self.anchor - timedelta(days=13 - i)] = before if i == 0 else {}
            per[self.anchor - timedelta(days=6 - i)] = after if i == 0 else {}
        return per

    def test_week_on_week_by_source(self):
        per = self.week({"AI assistant": 5, "Search engine": 6}, {"AI assistant": 8})
        got = conversions_leads.insights(_blob(per, self.anchor - timedelta(days=13),
                                               self.anchor), self.anchor, {})
        titles = sorted(i["title"] for i in got)
        self.assertIn("Leads from AI assistant up 60% week on week (5 to 8)", titles)
        self.assertIn("Leads from Search engine: none in the last 7 days (was 6)", titles)
        self.assertIn("Leads down 27% week on week (11 to 8)", titles)
        self.assertFalse(any("Email" in t for t in titles), "payments are not leads")
        self.assertFalse(any("Unknown" in t for t in titles), "Unknown is not a subject")
        one = next(i for i in got if i["title"].startswith("Leads from AI"))
        self.assertEqual((one["type"], one["metric"], one["filter"], one["confidence"]),
                         ("working", "leads", {"source": "AI assistant"}, "low"))
        again = conversions_leads.insights(_blob(per, self.anchor - timedelta(days=13),
                                                 self.anchor), self.anchor, {})
        self.assertEqual(got, again, "the same order every run")

    def test_only_whole_periods_and_the_floor(self):
        per = self.week({"AI assistant": 5}, {"AI assistant": 9})
        held = {(self.anchor - timedelta(days=10)).isoformat()}
        got = conversions_leads.insights(_blob(per, self.anchor - timedelta(days=13),
                                               self.anchor, held), self.anchor, {})
        self.assertEqual(got, [], "a withheld day: nothing compared")
        per = self.week({"AI assistant": 2}, {"AI assistant": 4})
        got = conversions_leads.insights(_blob(per, self.anchor - timedelta(days=13),
                                               self.anchor), self.anchor, {})
        self.assertEqual(got, [], "under min_after (5)")

    def test_the_page_that_started_the_most(self):
        first = self.anchor - timedelta(days=29)
        per = {first: {"AI assistant": 3}, self.anchor: {"Search engine": 3}}
        got = conversions_leads.insights(_blob(per, first, self.anchor), self.anchor, {})
        top = [i for i in got if i.get("top")]
        self.assertEqual([i["title"] for i in top],
                         ["/pricing/ is the page that started the most leads: 6 of 6 in 30 days"],
                         "two sources tie at 3: no leading source")
        self.assertEqual((top[0]["filter"], top[0]["of"]), ({"path": "/pricing/"}, 6))

    def test_not_available(self):
        self.assertEqual(conversions_leads.insights({"available": False}, self.anchor, {}), [])
        self.assertEqual(conversions_leads.insights(None, self.anchor, {}), [])


if __name__ == "__main__":
    unittest.main()
