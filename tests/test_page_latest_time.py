"""A page's latest Googlebot and Bingbot fetch (#44) and its time on page
from the log (#46): lifecycle.py, page_time.py, store_extras.py, the audit.

Pinned: the latest fetch is the newest verified-crawler page view of the
page, with the status it got, kept for good in page_milestones (a later
backfill of an earlier day never moves it back; a 404 or a redirect is no
page view, so it never counts); a page the crawler never fetched is null.
Time on page per page per day: the median of the seconds from each view to
the visit's next view, the views measured, and the views that were the
visit's last page (not measured); withheld (null) under page_time.MIN_MEASURED.
The audit recounts both from the raw log and catches a changed figure.
Addresses are RFC 5737; the host is example.com."""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import lifecycle, page_time  # noqa: E402
from skald.store import History  # noqa: E402

from support import CHROME, GOOGLEBOT, UTC, Sandbox, line  # noqa: E402

BINGBOT = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
SITE = "example.com"


def at(day: date, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=UTC)


D4, D5, D6 = date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6)


def story(box, path: str) -> dict:
    with History(box.db) as h:
        return lifecycle.story(h, SITE, path, {}, UTC, date(2026, 10, 7))


def tamper(box, day: date, kind: str, change) -> None:
    with sqlite3.connect(box.db) as db:
        blob = json.loads(db.execute("SELECT data FROM day_extras WHERE kind = ? AND day = ? "
                                     "AND site = ?", (kind, day.isoformat(), SITE))
                          .fetchone()[0])
        change(blob)
        db.execute("UPDATE day_extras SET data = ? WHERE kind = ? AND day = ? AND site = ?",
                   (json.dumps(blob), kind, day.isoformat(), SITE))


class LatestFetch(unittest.TestCase):
    """Googlebot fetches /launch/ on Oct 4 (200, then 304) and Oct 5 (200,
    then a 404 and a 301, which are no page views); Bingbot once on Oct 4."""

    def setUp(self):
        self.box = Sandbox()
        self.box.log([
            line(at(D4, 9), "198.51.100.41", "/launch/", GOOGLEBOT),
            line(at(D4, 11), "198.51.100.42", "/launch/", BINGBOT),
            line(at(D4, 15), "198.51.100.41", "/launch/", GOOGLEBOT, status=304),
            line(at(D5, 8), "198.51.100.41", "/launch/", GOOGLEBOT),
            line(at(D5, 10), "198.51.100.41", "/launch/", GOOGLEBOT, status=404),
            line(at(D5, 10, 30), "198.51.100.41", "/launch/", GOOGLEBOT, status=301),
            line(at(D6, 9), "198.51.100.41", "/other/", GOOGLEBOT),
            line(at(D6, 12), "203.0.113.5", "/other/", CHROME),
        ])
        code, _, err = self.box.run("--today", "2026-10-07", "backfill", "--days", "3")
        assert code == 0, err

    def tearDown(self):
        self.box.close()

    def test_latest_beside_the_first(self):
        m = story(self.box, "/launch")["milestones"]
        self.assertEqual(m["googlebot"]["at"], "2026-10-04T09:00:00+00:00")
        self.assertEqual(m["googlebot_latest"], {"at": "2026-10-05T08:00:00+00:00",
                                                 "status": 200})
        self.assertEqual(m["bingbot_latest"], {"at": "2026-10-04T11:00:00+00:00",
                                               "status": 200})
        other = story(self.box, "/other/")["milestones"]
        self.assertEqual(other["googlebot_latest"]["at"], "2026-10-06T09:00:00+00:00")
        self.assertIsNone(other["bingbot_latest"])          # never fetched: null, not 0

    def test_a_304_is_the_latest_when_it_is_the_newest(self):
        with History(self.box.db) as h:
            got = [r for r in h.milestones(SITE, "/launch/") if r[1] == "googlebot_latest"]
        self.assertEqual(len(got), 1)
        with sqlite3.connect(self.box.db) as db:
            blob = json.loads(db.execute("SELECT data FROM day_extras WHERE kind = 'page_firsts'"
                                         " AND day = '2026-10-04'").fetchone()[0])
        self.assertEqual(blob["/launch/"]["googlebot_latest"],
                         ["2026-10-04T15:00:00+00:00", "304"])

    def test_kept_when_an_earlier_day_is_collected_again(self):
        code, _, err = self.box.run("--today", "2026-10-05", "backfill", "--days", "1", "--force")
        self.assertEqual(code, 0, err)
        m = story(self.box, "/launch/")["milestones"]
        self.assertEqual(m["googlebot_latest"]["at"], "2026-10-05T08:00:00+00:00")
        # The stored days pruned (log rotation, retention): the table keeps it.
        with sqlite3.connect(self.box.db) as db:
            db.execute("DELETE FROM day_extras WHERE kind = 'page_firsts'")
        m = story(self.box, "/launch/")["milestones"]
        self.assertEqual(m["googlebot_latest"]["at"], "2026-10-05T08:00:00+00:00")

    def test_the_audit_recounts_the_latest_fetch(self):
        code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        tamper(self.box, D5, "page_firsts",
               lambda b: b["/launch/"]["googlebot_latest"].__setitem__(1, "500"))
        code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 1)
        self.assertIn("googlebot_latest", err)

    def test_a_day_kept_before_the_latest_fetch_is_not_a_mismatch(self):
        # Found on a copy of live data (12 Nov): days kept by 2.47 have no
        # "<crawler>_latest"; that is not recorded (unknown), never a mismatch.
        def old(blob):
            for keys in blob.values():
                for k in [k for k in keys if k.endswith("_latest")]:
                    del keys[k]
        tamper(self.box, D5, "page_firsts", old)
        code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)

    def test_the_command_line_says_it(self):
        code, out, err = self.box.run("--today", "2026-10-07", "page", "/launch/")
        self.assertEqual(code, 0, err)
        self.assertIn("googlebot_latest", out)
        self.assertIn("status 200", out)


class TimeOnPage(unittest.TestCase):
    """Oct 5: five visits read /launch/ then /pricing/ after 10, 20, 30, 40
    and 75 s, and one reads /launch/ only. Oct 6: two visits, 5 and 15 s."""

    def setUp(self):
        self.box = Sandbox()
        lines = []
        for i, gap in enumerate((10, 20, 30, 40, 75)):
            start = at(D5, 12, i * 2)
            lines += [line(start, f"203.0.113.{10 + i}", "/launch/"),
                      line(start + timedelta(seconds=gap), f"203.0.113.{10 + i}", "/pricing/",
                           referrer="https://example.com/launch/")]
        lines.append(line(at(D5, 14), "203.0.113.30", "/launch/"))
        for i, gap in enumerate((5, 15)):
            start = at(D6, 12, i * 2)
            lines += [line(start, f"203.0.113.{40 + i}", "/launch/"),
                      line(start + timedelta(seconds=gap), f"203.0.113.{40 + i}", "/pricing/",
                           referrer="https://example.com/launch/")]
        self.box.log(sorted(lines))
        code, _, err = self.box.run("--today", "2026-10-07", "backfill", "--days", "2")
        assert code == 0, err

    def tearDown(self):
        self.box.close()

    def test_per_day_median_measured_and_last_page(self):
        got = story(self.box, "/launch/")
        days = {d["day"]: d for d in got["days"]}
        self.assertEqual(days["2026-10-05"]["time_on_page"],
                         {"median_s": 30, "measured": 5, "not_measured_last_page": 1})
        # Two measured views: under the minimum, so no median (withheld, not 0).
        self.assertEqual(days["2026-10-06"]["time_on_page"],
                         {"median_s": None, "measured": 2, "not_measured_last_page": 0})
        # Over the whole days: 5, 10, 15, 20, 30, 40, 70 (75 s kept to 10 s).
        self.assertEqual(got["time_on_page"], {"median_s": 20, "measured": 7,
                                               "not_measured_last_page": 1,
                                               "min_measured": page_time.MIN_MEASURED,
                                               "days": 2})
        pricing = {d["day"]: d for d in story(self.box, "/pricing/")["days"]}
        self.assertEqual(pricing["2026-10-05"]["time_on_page"],
                         {"median_s": None, "measured": 0, "not_measured_last_page": 5})

    def test_the_figure(self):
        # A stored day the page had no row in: nobody was on it (zero, no median).
        self.assertEqual(page_time.figure([]),
                         {"median_s": None, "measured": 0, "not_measured_last_page": 0})
        self.assertIsNone(page_time.figure([{"views": 3}]))         # an old blob, no times
        self.assertEqual(page_time.figure([{"time": {"12": 3}, "exits": 1},
                                           {"time": {"12": 1, "40": 2}, "exits": 0}]),
                         {"median_s": 12, "measured": 6, "not_measured_last_page": 1})

    def test_the_audit_recounts_time_on_page(self):
        code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        tamper(self.box, D5, "pages", lambda b: b["/launch/"]["time"].update({"30": 2}))
        code, _, err = self.box.run("--today", "2026-10-07", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 1)
        self.assertIn("time on page", err)

    def test_the_audit_shares_only_the_threshold(self):
        """audit_page_time buckets and takes the median with its own code: from
        the package only the audit's bucket rule, the minimum and the figure
        it checks."""
        import ast
        from skald import audit_page_time
        tree = ast.parse(Path(audit_page_time.__file__).read_text())
        got = {(n.module, a.name) for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(got, {("audit_visits", "_bucket"), ("page_time", "MIN_MEASURED"),
                               ("page_time", "figure")})


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class OnThePage(unittest.TestCase):
    def test_the_page_story_says_both(self):
        got = subprocess.run(["node", str(Path(__file__).resolve().parent / "js" /
                                          "page-latest.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("page latest: ok", got.stdout)


if __name__ == "__main__":
    unittest.main()
