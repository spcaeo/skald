"""SKALD-34: posts refused at the log endpoint are counted and said, not lost in silence.

On 18 Nov 2026 nginx refused 1,157 posts from one site's Cloudflare Worker (a scanner
burst over its 5-a-second limit per address); a Worker never sends a refused post again,
so those records were lost, and nothing in Skald said so. nginx now leaves Worker posts to
Skald's own per-site edge limit (tests/test_nginx_ingest_limit.py), and Skald:

  * gives an edge post refused by that limit its own reason ("edge_limited"), whose words
    say the records are lost, not that "the shipper catches up";
  * counts every refusal per UTC quarter hour and reason (ingest_status `refused`), not only
    the last one at most once a second, and keeps 35 days of it;
  * shows the count per site day under Data quality (quality.json `intake_refused`;
    None, "not recorded", before counting began or past the 35 days kept); a day with lost
    records (a Worker's) is "worth a look", even one with no figures at all.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_support import TenantServer  # noqa: E402

from skald import ingest, ingest_drain, ingest_status, quality  # noqa: E402
from skald.accounts import site_configs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "tests" / "js"
SITE = "edge.example.org"


def at(text: str) -> float:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc).timestamp()


class Words(unittest.TestCase):
    def test_an_edge_post_refused_by_the_rate_limit_has_its_own_reason(self):
        self.assertEqual(ingest_status.reason(429, ingest_drain.EDGE_LIMIT_WORDS), "edge_limited")
        self.assertIn("lost", ingest_status.REASONS["edge_limited"])
        # The shipper's own limit keeps its words: it waits and sends again.
        self.assertEqual(ingest_status.reason(429, "too many batches for this site; slow down"),
                         "rate_limited")

    def test_the_page_has_a_fix_for_it(self):
        words = (ROOT / "skald" / "webapp" / "js" / "tabs" / "conn-words.js").read_text()
        self.assertIn("edge_limited:", words)


class Counting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        ingest_status._LAST_REFUSAL.clear()
        ingest_status._PENDING.clear()

    def tearDown(self):
        ingest_status.flush_all()
        self.tmp.cleanup()

    def test_every_refusal_is_counted_though_the_file_is_written_once_a_second(self):
        now = at("2026-11-18T00:51:10")
        for i in range(50):
            ingest_status.refused(self.base, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS,
                                  now=now + i * 0.01)
        ingest_status.refused(self.base, SITE, 401, "unrecognised or revoked token", now=now + 0.6)
        ingest_status.flush(self.base, SITE)
        got = ingest_status.read(self.base, SITE)
        self.assertEqual(got["refused"], {"2026-11-18T00:45": {"edge_limited": 50, "bad_token": 1}})
        # The last refusal is still the first of its second, as before.
        self.assertEqual(got["last_refusal"]["reason"], "edge_limited")
        self.assertEqual(got["counting_since"], "2026-11-18T00:51:10Z")

    def test_hours_add_up_and_old_ones_are_dropped(self):
        old = at("2026-10-01T10:00:00")
        ingest_status.refused(self.base, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS, now=old)
        later = at("2026-11-18T03:55:00")
        ingest_status.refused(self.base, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS, now=later)
        ingest_status.refused(self.base, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS, now=later + 2)
        ingest_status.flush(self.base, SITE)
        got = ingest_status.read(self.base, SITE)["refused"]
        self.assertEqual(got, {"2026-11-18T03:45": {"edge_limited": 2}})   # 1 Oct is past 35 days

    def test_a_site_this_install_does_not_know_is_not_written(self):
        h = type("H", (), {"_skald_ingest": {"base": self.base, "site": "nobody.example",
                                              "known": lambda: False}, "headers": {}})()
        ingest_status.note(h, 429, {"error": ingest_drain.EDGE_LIMIT_WORDS})
        ingest_status.flush_all()
        self.assertFalse(ingest_status.path_for(self.base, "nobody.example").exists())

    def test_a_late_flush_never_makes_a_folder_that_is_gone(self):
        ingest_status.refused(self.base, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS, now=at("2026-11-18T00:00:00"))
        ingest_status.refused(self.base, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS, now=at("2026-11-18T00:00:00"))
        gone = Path(self.base) / "history"
        ingest_status.refused(gone, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS)
        ingest_status.flush_all()
        self.assertFalse(gone.exists())

    def test_accepted_batches_start_the_count_too(self):
        ingest_status.accepted(self.base, SITE, 3, 0, "edge", now=at("2026-11-20T06:00:00"))
        self.assertEqual(ingest_status.read(self.base, SITE)["counting_since"], "2026-11-20T06:00:00Z")


class EdgeEndpoint(TenantServer):
    def setUp(self):
        super().setUp()
        ingest_status._LAST_REFUSAL.clear()
        ingest_status._PENDING.clear()
        db = self.db()
        try:
            site_configs.create(db, self.beta["id"], SITE, "cli", fmt="edge_json")
        finally:
            db.close()

    def test_the_edge_limit_refuses_with_its_words_and_every_refusal_is_counted(self):
        self.config["ingest"].update({"edge_per_minute": 60, "edge_burst": 2})
        ingest._BUCKETS.clear()
        token = self.token(self.beta, sites=[SITE])
        hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
        codes = []
        for i in range(6):
            body = json.dumps({"ts": "2026-11-20T06:00:00Z", "id": f"r-{i}", "ip": "192.0.2.7",
                               "method": "GET", "host": SITE, "path": "/", "status": 200,
                               "bytes": 10, "ua": "Mozilla/5.0", "referer": "", "cache": "MISS"})
            got = self.call("POST", f"/traffic-ingest/{SITE}?format=edge", headers=hdrs,
                            raw=body.encode())
            codes.append(got.status)
            if got.status == 429:
                self.assertEqual(got.json["error"], ingest_drain.EDGE_LIMIT_WORDS)
        self.assertEqual(codes, [200, 200, 429, 429, 429, 429])
        ingest_status.flush_all()
        got = ingest_status.read(self.live, SITE)
        self.assertEqual(sum(v.get("edge_limited", 0) for v in got["refused"].values()), 4)
        self.assertEqual(got["last_refusal"]["reason"], "edge_limited")


class DataQuality(unittest.TestCase):
    NY = ZoneInfo("America/New_York")

    NOW = datetime(2026, 11, 20, 6, tzinfo=timezone.utc)

    def test_quarter_hours_are_added_up_by_the_sites_own_day(self):
        status = {"counting_since": "2026-11-17T12:00:00Z",
                  "refused": {"2026-11-18T00:45": {"edge_limited": 775},  # 17 Nov, 19:45 New York
                              "2026-11-18T03:45": {"edge_limited": 382},  # 17 Nov, 22:45 New York
                              "2026-11-18T05:00": {"rate_limited": 2, "edge_limited": 1}}}
        days = [date(2026, 11, d) for d in (16, 17, 18, 19)]
        got = quality.intake_days(status, self.NY, days, self.NOW)
        self.assertIsNone(got["2026-11-16"], "before counting began: not recorded")
        self.assertEqual(got["2026-11-17"], {"edge_limited": 1157})
        self.assertEqual(got["2026-11-18"], {"rate_limited": 2, "edge_limited": 1})
        self.assertEqual(got["2026-11-19"], {}, "counted, none refused")

    def test_no_status_file_is_not_recorded(self):
        got = quality.intake_days({}, self.NY, [date(2026, 11, 18)], self.NOW)
        self.assertEqual(got, {"2026-11-18": None})

    def test_a_half_hour_time_zone_gets_exactly_its_own_day(self):
        # Kolkata is UTC+5:30: 18:30 UTC is midnight there.
        status = {"counting_since": "2026-11-15T00:00:00Z",
                  "refused": {"2026-11-18T18:15": {"edge_limited": 4},    # 23:45 on the 18th
                              "2026-11-18T18:30": {"edge_limited": 9}}}   # 00:00 on the 19th
        got = quality.intake_days(status, ZoneInfo("Asia/Kolkata"),
                                  [date(2026, 11, 18), date(2026, 11, 19)], self.NOW)
        self.assertEqual(got, {"2026-11-18": {"edge_limited": 4}, "2026-11-19": {"edge_limited": 9}})

    def test_days_past_what_the_file_keeps_are_not_recorded(self):
        # Counting began long ago, but the file keeps 35 days: older days are unknown, not 0.
        status = {"counting_since": "2026-08-01T00:00:00Z", "refused": {}}
        days = [date(2026, 10, 1), date(2026, 10, 20), date(2026, 11, 19)]
        got = quality.intake_days(status, self.NY, days, self.NOW)
        self.assertEqual(got, {"2026-10-01": None, "2026-10-20": {}, "2026-11-19": {}})

    def test_a_day_with_no_figures_still_says_what_was_refused(self):
        entry = {"day": date(2026, 11, 19), "state": "missing"}
        row = quality._day(None, entry, {}, {"2026-11-19": {"edge_limited": 90}})
        self.assertEqual(row, {"day": "2026-11-19", "state": "missing",
                               "intake_refused": {"edge_limited": 90}})
        self.assertEqual(quality._day(None, entry, {}, {"2026-11-19": None}),
                         {"day": "2026-11-19", "state": "missing"})

    def test_a_damaged_file_is_nothing_recorded(self):
        days = [date(2026, 11, 18)]
        for bad in ({"counting_since": "yesterday"}, {"counting_since": 5},
                    {"counting_since": "2026-11-17T12:00:00Z", "refused": [1, 2]},
                    {"counting_since": "2026-11-17T12:00:00Z", "refused": {"x": {"a": 1}, "2026-11-18T05:00": 7}},
                    []):
            with self.subTest(bad=bad):
                got = quality.intake_days(bad, self.NY, days, self.NOW)
                self.assertIn(got["2026-11-18"], (None, {}))

    def test_every_site_reads_the_install_wide_counts_not_only_the_first(self):
        # The endpoint runs in the server, whose folder is the history's: it writes
        # <history>/ingest-status/<site>.json for every site. A page for the install's
        # second site onward is built with that site's own folder (multisite.state_dir,
        # <history>/sites/<slug>) as live_dir, and must still read the counts there
        # (the review of the combined release found every such site said "not recorded").
        from types import SimpleNamespace
        from skald import multisite
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            when = datetime(2026, 11, 20, 5, tzinfo=timezone.utc).timestamp()
            ingest_status.accepted(base, SITE, 1, 0, "edge", when - 3600)
            ingest_status.refused(base, SITE, 429, ingest_drain.EDGE_LIMIT_WORDS, when)
            ingest_status.flush(base, SITE, when)
            for name, live in (("first site", base), ("another site", multisite.state_dir(base, SITE))):
                with self.subTest(name):
                    page = SimpleNamespace(config={}, live_dir=live, site=SITE, tz=self.NY,
                                           today=date(2026, 11, 20), daily=[],
                                           now=datetime(2026, 11, 20, 6, tzinfo=timezone.utc),
                                           history=SimpleNamespace(path=base / "history.sqlite"))
                    self.assertEqual(quality._intake(page), {"2026-11-20": {"edge_limited": 1}})


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Screen(unittest.TestCase):
    def test_a_day_with_refused_posts_is_worth_a_look(self):
        done = subprocess.run(["node", str(JS / "quality-intake.mjs")], capture_output=True,
                              text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("quality-intake: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
