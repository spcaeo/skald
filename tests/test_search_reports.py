"""Traffic > Search's reports (search/reports.py): new and lost queries on whole
days only, position tracking by bucket, opportunities linked to their page,
each period's coverage; the query_page kind the sync now keeps; and the
second road (audit_search_reports.py) matching, then catching a planted error.

The rows are recorded fake Search Console answers (RECORDS below, as the
Search Analytics API gives them), answered by a stand-in client handed to the
real sync: no network, not even 127.0.0.1. Example hosts only."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skald import audit_search_reports as audit  # noqa: E402
from skald.search import data, days, reports, sync  # noqa: E402
from skald.store import History  # noqa: E402

SITE = "alpha.example"
HOST = "https://www.alpha.example"
FIRST = date(2026, 8, 1)
NEWEST = date(2026, 10, 16)
INCOMPLETE = "2026-10-15"               # 10-15 and 10-16 are provisional
LAST_FINAL = date(2026, 10, 14)
NOW = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)


def rec(query, page, clicks, shown, position):
    return {"query": query, "page": HOST + page, "country": "usa", "device": "DESKTOP",
            "appearance": None, "clicks": clicks, "impressions": shown, "position": position}


def records(first=FIRST, last=NEWEST) -> dict:
    """{day: [record]}: what Google holds, one record per query, page and day."""
    out = {}
    for k in range((last - first).days + 1):
        d = first + timedelta(days=k)
        back = (LAST_FINAL - d).days
        rows = [rec("server log analytics", "/", 8, 200, round(4.0 - k * 0.02, 2)),
                rec("ai crawler log", "/blog/ai", 0, 40, 4.0),
                rec("ai crawler log", "/", 0, 20, 5.5),
                rec("nginx log format", "/guides/nginx", 1, 40, 12.0),
                rec(None, "/", 1, 30, 9.0)]                 # anonymised: in no query row
        if back <= 3:
            rows.append(rec("log file viewer", "/tools/viewer", 1, 15, 6.0))
        if back >= 8:
            rows.append(rec("old feature name", "/old", 1, 10, 2.0))
        if k % 2 == 0:
            rows.append(rec("rare query", "/", 0, 1, 30.0))
        out[d.isoformat()] = rows
    return out


KEY = {"query": "query", "page": "page", "country": "country", "device": "device",
       "searchAppearance": "appearance"}


class FakeGoogle:
    """query(property, body) -> (rows, meta), as google.Client answers it."""

    def __init__(self, recs: dict):
        self.recs, self.calls, self.bodies = recs, 0, []

    def query(self, prop, body):
        self.calls += 1
        self.bodies.append(body)
        dims = body.get("dimensions") or []
        groups = defaultdict(list)
        for day, rows in self.recs.items():
            if not body["startDate"] <= day <= body["endDate"]:
                continue
            for r in rows:
                keys = []
                for dim in dims:
                    v = day if dim == "date" else r[KEY[dim]]
                    if v is None:
                        break
                    keys.append(v)
                else:
                    groups[tuple(keys)].append(r)
        out = []
        for k, rows in sorted(groups.items()):
            c, i = sum(r["clicks"] for r in rows), sum(r["impressions"] for r in rows)
            out.append({"keys": list(k), "clicks": float(c), "impressions": float(i),
                        "ctr": c / i if i else 0,
                        "position": sum(r["position"] * r["impressions"] for r in rows) / i})
        return out, {"first_incomplete_date": INCOMPLETE}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.db_path = self.folder / "history.sqlite"
        History(self.db_path).close()
        self.config = {"site": {"name": SITE, "hosts": [SITE, f"www.{SITE}"]},
                       "search_console": {"property": f"sc-domain:{SITE}"}}
        self.client = FakeGoogle(records())
        job = sync.Job(self.config, SITE, self.folder, self.db_path, NOW,
                       out=lambda *_: None, err=lambda *_: None)
        self.assertEqual(sync.run(job, "google", client=self.client, backfill_months=3), 0)

    def history(self):
        return History(self.db_path)

    def got(self):
        with self.history() as h:
            return reports.for_site(h.db, SITE)


class QueryPage(Base):
    def test_the_sync_keeps_each_query_with_its_page(self):
        asked = [b["dimensions"] for b in self.client.bodies]
        self.assertIn(["date", "query", "page"], asked)
        with self.history() as h:
            stored, _ = days.read(h.db, SITE, "google", date(2026, 10, 1), date(2026, 10, 1))
        blob = stored["2026-10-01"]["query_page"]
        keys = {r[0]: r[1:3] for r in blob["rows"]}
        self.assertEqual(keys[f"ai crawler log\t{HOST}/blog/ai"], [0, 40])
        self.assertEqual(keys[f"ai crawler log\t{HOST}/"], [0, 20])
        # Counted by page, as Google counts a table with the page: the page table's total.
        self.assertEqual(blob["total"], stored["2026-10-01"]["page"]["total"])
        # The anonymised query is in the total, in no row.
        self.assertEqual(blob["unattributed"], {"clicks": 1, "impressions": 30})
        self.assertEqual(days.sums_hold(blob), [])


class Coverage(Base):
    def test_days_stored_before_the_history_and_provisional(self):
        got = self.got()
        week = got["7"]["coverage"]
        self.assertEqual((week["days"], week["stored"], week["before_history"]), (7, 7, 0))
        self.assertEqual(week["provisional"], ["2026-10-15", "2026-10-16"])
        self.assertEqual(week["missing"], [])
        self.assertFalse(week["empty"])
        q = got["90"]["coverage"]
        self.assertEqual((q["stored"], q["before_history"], q["history_first"]),
                         (77, 13, "2026-08-01"))

    def test_a_day_missing_inside_the_history_is_listed_never_zero(self):
        with self.history() as h, h.db:
            h.db.execute("DELETE FROM search_days WHERE day = '2026-10-10'")
        got = self.got()
        self.assertEqual(got["7"]["coverage"]["missing"], ["2026-10-10"])
        self.assertEqual(got["7"]["coverage"]["stored"], 6)
        # New and lost needs whole days: the gap stops it, plainly.
        self.assertEqual(got["7"]["changes"]["state"], "short")

    def test_no_impressions_at_all_is_said(self):
        with self.history() as h, h.db:
            for (d, blob) in list(h.db.execute("SELECT day, data FROM search_days WHERE "
                                               "kind = 'total'")):
                b = json.loads(blob)
                b["total"].update(impressions=0, clicks=0)
                b["rows"] = [["(all)", 0, 0, None]]
                h.db.execute("UPDATE search_days SET data = ? WHERE day = ? AND kind = 'total'",
                             (json.dumps(b), d))
        self.assertTrue(self.got()["7"]["coverage"]["empty"])

    def test_nothing_stored_is_nothing(self):
        with self.history() as h, h.db:
            h.db.execute("DELETE FROM search_days")
        self.assertEqual(self.got(), {})


class Changes(Base):
    def test_new_and_lost_on_whole_days_only(self):
        ch = self.got()["7"]["changes"]
        self.assertEqual(ch["state"], "ok")
        # Ends at the newest final day: the two provisional days are left out.
        self.assertEqual(ch["now"], {"first": "2026-10-08", "last": "2026-10-14"})
        self.assertEqual(ch["before"], {"first": "2026-10-01", "last": "2026-10-07"})
        self.assertEqual(ch["new"]["rows"], [["log file viewer", 4, 60, 0.0667, 6.0]])
        self.assertEqual((ch["new"]["count"], ch["new"]["clicks"], ch["new"]["impressions"]),
                         (1, 4, 60))
        self.assertEqual(ch["lost"]["rows"], [["old feature name", 6, 60, 0.1, 2.0]])
        self.assertNotIn("rare query", json.dumps(ch), "every other day is in both windows")
        self.assertEqual(ch["folded_days"], 0)

    def test_a_longer_period(self):
        ch = self.got()["28"]["changes"]
        self.assertEqual(ch["before"]["first"], "2026-08-20")
        self.assertEqual([r[0] for r in ch["new"]["rows"]], ["log file viewer"])
        self.assertEqual(ch["lost"]["count"], 0)

    def test_not_enough_history_or_too_long(self):
        got = self.got()
        self.assertEqual(got["90"]["changes"]["state"], "short")
        self.assertEqual(got["90"]["changes"]["need_from"], "2026-04-18")
        self.assertEqual(got["90"]["changes"]["history_first"], "2026-08-01")
        self.assertEqual(got["480"]["changes"], {"state": "too_long"})

    def test_no_final_day(self):
        with self.history() as h, h.db:
            h.db.execute("UPDATE search_days SET final = 0")
        self.assertEqual(self.got()["7"]["changes"], {"state": "no_final"})


class Positions(Base):
    def test_weighted_by_impressions_with_gaps_left_empty(self):
        pos = self.got()["28"]["positions"]
        self.assertEqual(pos["size"], 1)
        self.assertEqual(len(pos["buckets"]), 28)
        self.assertEqual(pos["buckets"][-1], {"first": "2026-10-16", "last": "2026-10-16",
                                              "days": 1, "provisional": True})
        rows = {r["key"]: r for r in pos["query"]["rows"]}
        sla = rows["server log analytics"]
        self.assertEqual(sla["points"][0], round(4.0 - 49 * 0.02, 2))
        self.assertEqual(sla["last"], round(4.0 - 76 * 0.02, 2))
        self.assertEqual(sla["change"], round(27 * 0.02, 2), "positive: moved up")
        # Two pages for one query: their positions weighted by impressions.
        self.assertEqual(rows["ai crawler log"]["position"], 4.5)
        # A day the query had no row is empty, never 0.
        rare = rows["rare query"]["points"]
        self.assertIn(None, rare)
        self.assertNotIn(0, rare)
        self.assertEqual(rows["rare query"]["shown"][rare.index(None)], None)
        pages = {r["key"]: r for r in pos["page"]["rows"]}
        self.assertIn(f"{HOST}/guides/nginx", pages)
        self.assertEqual(pos["page"]["keys"], len(pages))

    def test_buckets_of_a_week_the_oldest_short(self):
        pos = self.got()["90"]["positions"]
        self.assertEqual((pos["size"], len(pos["buckets"])), (7, 13))
        self.assertEqual(pos["buckets"][0], {"first": "2026-07-19", "last": "2026-07-24",
                                             "days": 0, "provisional": False})
        sla = next(r for r in pos["query"]["rows"] if r["key"] == "server log analytics")
        self.assertIsNone(sla["points"][0], "before the history: no position, never 0")
        self.assertEqual(len(sla["points"]), 13)

    def test_only_the_most_shown_are_tracked(self):
        with mock.patch.object(reports, "TRACK", 2):
            pos = self.got()["28"]["positions"]
        self.assertEqual([r["key"] for r in pos["query"]["rows"]],
                         ["server log analytics", "ai crawler log"])
        self.assertEqual(pos["query"]["keys"], 6)


class Opportunities(Base):
    def test_the_two_rules_and_the_page(self):
        opp = self.got()["28"]["opportunities"]
        self.assertEqual(opp["rules"], {"many": 140, "some": 30, "low_ctr": 0.01, "high": 8.0,
                                        "near": [8.0, 20.0]})
        self.assertEqual(opp["by_rule"], {"low_ctr": 1, "near": 1})
        first, second = opp["rows"]
        self.assertEqual((first["query"], first["rule"], first["impressions"], first["clicks"],
                          first["position"]), ("ai crawler log", "low_ctr", 1680, 0, 4.5))
        self.assertEqual((first["page"], first["pages"], first["page_share"]),
                         (f"{HOST}/blog/ai", 2, 0.6667))
        self.assertEqual((second["query"], second["rule"], second["position"], second["page"]),
                         ("nginx log format", "near", 12.0, f"{HOST}/guides/nginx"))
        self.assertEqual(opp["pages_from"], "2026-09-19")

    def test_floors_scale_with_the_days(self):
        week = self.got()["7"]["opportunities"]
        self.assertEqual((week["rules"]["many"], week["rules"]["some"]), (100, 30))
        self.assertEqual(week["days"], 7)
        # nginx: 280 impressions in 7 days, over the floor of 30
        self.assertEqual([r["query"] for r in week["rows"]], ["ai crawler log", "nginx log format"])
        self.assertEqual(reports.rule_of(29, 0, 12.0, 100, 30), None, "under the floor")
        self.assertEqual(reports.rule_of(30, 0, 20.0, 100, 30), "near")
        self.assertEqual(reports.rule_of(500, 0.0099, 7.99, 100, 30), "low_ctr")
        self.assertEqual(reports.rule_of(500, 0.01, 7.99, 100, 30), None, "1% is not under 1%")
        self.assertEqual(reports.rule_of(500, 0.0, 21.0, 100, 30), None, "past page two")
        self.assertEqual(reports.rule_of(500, 0.0, None, 100, 30), None)

    def test_days_synced_before_query_pages_have_no_page(self):
        with self.history() as h, h.db:
            h.db.execute("DELETE FROM search_days WHERE kind = 'query_page' AND day < '2026-10-10'")
        opp = self.got()["28"]["opportunities"]
        self.assertEqual((opp["pages_from"], opp["pages_days"]), ("2026-10-10", 7))
        self.assertEqual(opp["rows"][0]["page"], f"{HOST}/blog/ai", "known from the days it has")
        with self.history() as h, h.db:
            h.db.execute("DELETE FROM search_days WHERE kind = 'query_page'")
        opp = self.got()["28"]["opportunities"]
        self.assertIsNone(opp["pages_from"])
        self.assertEqual([(r["page"], r["pages"], r["page_share"]) for r in opp["rows"]],
                         [(None, 0, None), (None, 0, None)])


class SearchJson(Base):
    def test_the_periods_carry_the_reports_bing_only_coverage(self):
        with self.history() as h:
            p = SimpleNamespace(history=h)
            google = data.engine_part(p, SITE, "google", "sc-domain:alpha.example", None)
            period = google["periods"]["28"]
            for k in ("coverage", "changes", "positions", "opportunities", "query", "totals"):
                self.assertIn(k, period)
            t = {"clicks": 3, "impressions": 30, "position": None}
            days.write(h.db, SITE, "bing", {date(2026, 10, 10): {
                "total": days.fold([["(all)", 3, 30, None]], t, 1)}}, {}, "https://x.example/")
            bing = data.engine_part(p, SITE, "bing", "https://x.example/", None)
        self.assertEqual(set(bing["periods"]["7"]) & {"changes", "positions", "opportunities"},
                         set())
        self.assertEqual(bing["periods"]["7"]["coverage"]["stored"], 1)
        self.assertEqual(reports.PERIODS, data.PERIODS)
        # The file stays small enough to load with the page.
        self.assertLess(len(json.dumps(google)), 400_000)


class SecondRoad(Base):
    def test_the_recount_matches(self):
        with self.history() as h:
            self.assertEqual(audit.check(h.db, SITE), [])

    def test_it_matches_with_gaps_and_no_query_pages(self):
        with self.history() as h, h.db:
            h.db.execute("DELETE FROM search_days WHERE day = '2026-10-10'")
            h.db.execute("DELETE FROM search_days WHERE kind = 'query_page' AND day < '2026-10-01'")
        with self.history() as h:
            self.assertEqual(audit.check(h.db, SITE), [])

    def test_it_catches_a_rule_changed_in_the_main_code(self):
        with mock.patch.object(reports, "LOW_CTR", 0.05), self.history() as h:
            problems = audit.check(h.db, SITE)
        self.assertTrue(any("opportunities" in p for p in problems), problems)

    def test_it_catches_a_row_dropped_by_the_sums(self):
        real = reports.sums

        def short(stored, days_, kind):
            got = real(stored, days_, kind)
            got.pop("old feature name", None)
            return got

        with mock.patch.object(reports, "sums", short), self.history() as h:
            problems = audit.check(h.db, SITE)
        self.assertTrue(any("lost" in p for p in problems), problems)
        self.assertTrue(any("positions query" in p for p in problems), problems)

    def test_it_catches_buckets_cut_from_the_wrong_end(self):
        def from_the_start(first, last, n):     # the short bucket last, not first
            span = reports._span(first, last)
            size = reports.BUCKET[n]
            return [span[i:i + size] for i in range(0, len(span), size)]

        with mock.patch.object(reports, "buckets", from_the_start), self.history() as h:
            problems = audit.check(h.db, SITE)
        self.assertTrue(any("90 days: positions query" in p and "points" in p
                            for p in problems), problems)

    def test_audit_search_runs_it(self):
        from skald import audit_search
        ctx = SimpleNamespace(config=self.config, site=SITE, db_path=self.db_path, now=NOW,
                              out=lambda *_: None, err=lambda *_: None,
                              history=lambda: History(self.db_path))
        with mock.patch.object(audit_search, "refetch", lambda *a: []), \
                mock.patch.object(reports, "HIGH", 3.0):
            problems = audit_search.daily(ctx, NOW.date())
        self.assertTrue(any("search reports" in p for p in problems), problems)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class ThePage(unittest.TestCase):
    def test_the_page_draws_the_reports(self):
        got = subprocess.run(["node", str(ROOT / "tests" / "js" / "search-reports.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr + got.stdout)
        self.assertIn("search reports: all passed", got.stdout)


if __name__ == "__main__":
    unittest.main()
