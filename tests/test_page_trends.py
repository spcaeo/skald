"""page_trends.json (page_trends.py): each page's visits and AI reads by day,
the pages changed lately with what happened since, the "dates look like
build times" note, and its second count (audit_page_trends.py) matching and
catching a planted error."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from support import ASKED, Sandbox, line  # noqa: E402

from skald import audit_more, audit_page_trends, data_more, page_trends  # noqa: E402
from skald.audit_lastmod import expected  # noqa: E402
from skald.store import History  # noqa: E402

D1, D2 = date(2026, 10, 4), date(2026, 10, 5)


def noon(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 12, tzinfo=timezone.utc)


def day_lines(d: date, pricing_search: int) -> list[str]:
    out = []
    for i in range(pricing_search):
        out.append(line(noon(d) + timedelta(minutes=i), f"203.0.113.{30 + i}", "/pricing/",
                        referrer="https://www.google.com/"))
    out.append(line(noon(d) + timedelta(minutes=20), "203.0.113.60", "/guides/alpha"))
    out.append(line(noon(d) + timedelta(minutes=21), "203.0.113.60", "/pricing/"))
    out.append(line(noon(d) + timedelta(minutes=30), "198.51.100.41", "/guides/alpha", ASKED))
    out.append(line(noon(d) + timedelta(minutes=31), "198.51.100.41", "/guides/alpha", ASKED))
    return out


class Units(unittest.TestCase):
    def test_registered(self):
        self.assertIn("page_trends", data_more.builders())
        self.assertIn("page_trends", audit_more._modules(audit_more.DAILY))

    def test_key(self):
        self.assertEqual(page_trends.key("/a?x=1"), "/a/")
        self.assertEqual(page_trends.key("/a/"), "/a/")
        self.assertEqual(page_trends.key("/"), "/")

    def test_fetches_fold_by_path_and_assistant(self):
        rows = [["2026-10-05T10:00", "chatgpt.com", "/a", 2], ["2026-10-05T10:01", "claude.ai", "/a", 1],
                ["2026-10-05T10:02", "chatgpt.com", "/b", 1]]
        # Rows stored before reads were counted (four columns): reads not recorded.
        self.assertEqual(page_trends.fold_fetches(rows),
                         {"paths": {"/a": {"chatgpt.com": 2, "claude.ai": 1}, "/b": {"chatgpt.com": 1}},
                          "folded": 0, "reads": None})
        # With the reads column: requests and reads apart; a file (no read) is in requests only.
        rows = [r + [1] for r in rows] + [["2026-10-05T10:02", "chatgpt.com", "/app.css", 1, 0]]
        got = page_trends.fold_fetches(rows)
        self.assertEqual(got["reads"], {"/a": {"chatgpt.com": 1, "claude.ai": 1}, "/b": {"chatgpt.com": 1}})
        self.assertEqual(got["paths"]["/app.css"], {"chatgpt.com": 1})
        many = [["m", "chatgpt.com", f"/p{i:03d}", 1] for i in range(page_trends.FETCH_TOP + 3)]
        got = page_trends.fold_fetches(many)
        self.assertEqual(got["folded"], 3)
        self.assertEqual(got["paths"][page_trends.OTHER], {"chatgpt.com": 3})

    def test_same_day_dates_look_like_build_times(self):
        dates = {f"/p{i}/": {"lastmod": "2026-10-06"} for i in range(9)}
        dates.update({f"/q{i}/": {"lastmod": f"2026-09-{10 + i}"} for i in range(3)})
        self.assertEqual(page_trends.same_day(dates), {"day": "2026-10-06", "pages": 9, "of": 12})
        self.assertEqual(page_trends.same_day(dict(list(dates.items())[:5])), None)   # under 10
        half = {f"/p{i}/": {"lastmod": "2026-10-06" if i < 5 else f"2026-09-{10 + i}"} for i in range(10)}
        self.assertIsNone(page_trends.same_day(half))                                 # not more than half

    def test_changed_counts_from_the_change_date(self):
        def blob(rows, folded=0):
            return {"pages": rows, "folded": folded}
        days = [{"day": "2026-10-01", "ok": True, "landings": blob({"/a/": [5, 5, 5, 5, 0]}), "crawl": None},
                {"day": "2026-10-02", "ok": False, "landings": None, "crawl": None},
                {"day": "2026-10-03", "ok": True, "landings": blob({"/a": [2, 1, 3, 0, 0], "/b/": [1, 1, 1, 1, 0]}),
                 "crawl": {"crawlers": {"Google": {"paths": {"/a": [1] + [0] * 13}}}}},
                {"day": "2026-10-04", "ok": True, "landings": blob({"/a/": [1, 1, 1, 1, 0]}, folded=2), "crawl": None}]
        dates = {"/a/": {"updated": "2026-10-02", "updated_source": "sitemap"},
                 "/b/": {"updated": "2026-10-04", "updated_source": "website"},
                 "/old/": {"updated": "2026-08-01"}}
        got = page_trends.changed(dates, days, date(2026, 10, 4))
        rows = {r["path"]: r for r in got["pages"]}
        self.assertNotIn("/old/", rows)
        a = rows["/a/"]
        self.assertEqual((a["visits"], a["search"], a["first_search"]), (3, 1, "2026-10-04"))
        self.assertEqual((a["counted_from"], a["unmeasured"], a["google"], a["google_last"]),
                         ("2026-10-03", 1, True, "2026-10-03"))
        b = rows["/b/"]
        self.assertEqual((b["visits"], b["at_least"], b["google"]), (0, True, None))
        self.assertEqual(got["counts"], {"pages": 2, "measured": 2, "visited": 1, "searched": 1,
                                         "none": 1, "google": 1})


class Built(unittest.TestCase):
    """Two collected days, the website's change dates, the file and its recount."""

    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.close)
        self.box.log(day_lines(D1, 2) + day_lines(D2, 3))
        for today in ("2026-10-05", "2026-10-06"):
            self.assertEqual(self.box.run("--today", today, "collect")[0], 0)
        meta = self.box.root / "pages.json"
        meta.write_text(json.dumps({"pages": [{"path": "/pricing/", "updated": "2026-10-05"},
                                              {"path": "/guides/alpha/", "updated": "2026-10-04"}]}))
        self.config = {"report": {"pages_meta": str(meta)}, "site": {"hosts": ["example.com"]}}

    def shown(self, history):
        return page_trends.figures(history, "example.com", history.daily("example.com", D2 - timedelta(days=179), D2),
                                   D2, self.config, None)

    def test_the_file_and_its_recount_agree(self):
        with History(self.box.db) as h:
            got = self.shown(h)
            by_day = {d["day"]: d for d in got["days"]}
            self.assertEqual(by_day["2026-10-05"]["landings"]["pages"]["/pricing/"], [3, 3, 3, 3, 0])
            self.assertEqual(by_day["2026-10-05"]["fetches"]["paths"], {"/guides/alpha": {"chatgpt.com": 2}})
            self.assertEqual(got["first_day"], "2026-10-04")
            rows = {r["path"]: r for r in got["changed"]["pages"]}
            self.assertEqual((rows["/pricing/"]["visits"], rows["/pricing/"]["search"]), (3, 3))
            self.assertEqual(rows["/guides/alpha/"]["visits"], 2)
            self.assertEqual(rows["/guides/alpha/"]["first_search"], None)
            dates = expected({}, self.config["report"]["pages_meta"])
            self.assertEqual(audit_page_trends.recheck(h.db, "example.com", D2, dates, got), [])
            got["changed"]["pages"][0]["visits"] += 1
            got["days"][-1]["fetches"]["paths"]["/guides/alpha"]["chatgpt.com"] = 9
            problems = audit_page_trends.recheck(h.db, "example.com", D2, dates, got)
            self.assertTrue(any("fetches by page and assistant do not match" in p for p in problems))
            self.assertTrue(any(": visits shown" in p for p in problems))

    def test_daily_runs_from_run_dailys_context(self):
        ctx = SimpleNamespace(site="example.com", config=self.config, live_dir=None, out=lambda *_: None,
                              history=lambda: History(self.box.db))
        self.assertEqual(audit_page_trends.daily(ctx, D2), [])

    def test_a_view_gets_the_whole_sites_note(self):
        self.assertEqual(page_trends.build(SimpleNamespace(view=object())), {"whole_site_only": True})


if __name__ == "__main__":
    unittest.main()
