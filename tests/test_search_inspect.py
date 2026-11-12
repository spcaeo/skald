"""URL Inspection after a Search Console sync (search/inspect.py, 2.48).

Against the fake Search Console in search_support (no test calls Google). Pinned:
Google's answer is kept as given (status read from its verdict and coverage
words, nothing invented), one row per page and Pacific day; pages never asked
come first, a page asked in the last 20 hours is not asked again; the daily
budget holds; a refusal is kept in the state file and never fails the sync;
several pages are asked at once and the answers kept a batch at a time, so a job
stopped part-way keeps what came in (2.48.1, #49)."""
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import search_support as ss  # noqa: E402

from skald.conversions import secrets_store  # noqa: E402
from skald.search import bing, google, http, inspect, state, sync  # noqa: E402
from skald.store import History  # noqa: E402

SITE = "alpha.example"
NOW = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)
NEWEST = date(2026, 10, 16)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.db_path = self.folder / "history.sqlite"
        History(self.db_path).close()
        self.config = {"site": {"name": SITE, "hosts": [SITE, f"www.{SITE}"]},
                       "search_console": {"property": f"sc-domain:{SITE}"},
                       "history": {"db": str(self.db_path)},
                       "_resolved": {"history_db": str(self.db_path)}}
        secrets_store.put(self.folder / "secrets.json", google.SECRET,
                          google.compact(ss.service_key()))
        secrets_store.put(self.folder / "secrets.json", bing.ENV, ss.BING_KEY)
        self.engines = ss.Engines()
        self.addCleanup(self.engines.stop)
        self.engines.data = ss.records(NEWEST - timedelta(days=40), NEWEST)
        self.engines.incomplete = "2026-10-15"
        self.said = []

    def job(self, now=NOW):
        return sync.Job(self.config, SITE, self.folder, self.db_path, now,
                        out=self.said.append, err=self.said.append, sleep=lambda s: None,
                        send=lambda msg, cfg: None, api=self.engines.api())

    def rows(self):
        with History(self.db_path) as h:
            return h.db.execute("SELECT url, path, day, status, verdict, coverage, last_crawl, "
                                "google_canonical, user_canonical FROM search_inspect "
                                "ORDER BY url").fetchall()

    def inspected(self):
        return [c for c in self.engines.calls if c[1] == "/v1/urlInspection/index:inspect"]


class StatusWords(unittest.TestCase):
    def test_status_is_read_from_googles_own_words(self):
        self.assertEqual(inspect.status_of("PASS", "Submitted and indexed"), "indexed")
        self.assertEqual(inspect.status_of("NEUTRAL", "Crawled - currently not indexed"),
                         "crawled_not_indexed")
        self.assertEqual(inspect.status_of("NEUTRAL", "Discovered - currently not indexed"),
                         "discovered_not_indexed")
        self.assertEqual(inspect.status_of("NEUTRAL", "URL is unknown to Google"),
                         "unknown_to_google")
        self.assertEqual(inspect.status_of("NEUTRAL", "Excluded by 'noindex' tag"), "excluded")
        self.assertEqual(inspect.status_of(None, None), "not_known")

    def test_a_missing_field_stays_none(self):
        row = inspect.row_of(SITE, "https://www.alpha.example/a", "sc-domain:alpha.example",
                             {"inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}},
                             NOW)
        self.assertEqual(row["status"], "indexed")
        self.assertIsNone(row["last_crawl"])
        self.assertIsNone(row["google_canonical"])
        self.assertEqual(row["day"], "2026-10-18")           # Pacific: 08:00 on the 18th


class AfterTheSync(Base):
    def test_a_good_sync_asks_about_the_pages_and_keeps_googles_answers(self):
        pages = sorted({r["page"] for d in self.engines.data.values() for r in d})
        first = pages[0]
        self.engines.inspect[first] = {
            "verdict": "PASS", "coverageState": "Submitted and indexed",
            "lastCrawlTime": "2026-10-17T03:04:05Z", "googleCanonical": first,
            "userCanonical": first, "crawledAs": "MOBILE"}
        self.assertEqual(sync.run(self.job(), "google"), 0)
        got = {r[0]: r for r in self.rows()}
        self.assertEqual(set(got), set(pages))
        self.assertEqual(got[first][3:7], ("indexed", "PASS", "Submitted and indexed",
                                           "2026-10-17T03:04:05Z"))
        other = got[pages[-1]]
        self.assertEqual(other[3], "unknown_to_google")
        self.assertIsNone(other[6])
        part = state.load(self.folder, SITE)["google"]["inspect"]
        self.assertEqual((part["asked"], part["kept"], part["error"]),
                         (len(pages), len(pages), None))
        # Asked again within 20 hours: nothing is asked again.
        before = len(self.inspected())
        sync.run(self.job(NOW + timedelta(hours=6)), "google")
        self.assertEqual(len(self.inspected()), before)
        # A day later: asked again, a second row for the new day.
        sync.run(self.job(NOW + timedelta(days=1)), "google")
        self.assertEqual(len(self.rows()), 2 * len(pages))

    def test_the_daily_budget_holds(self):
        self.config["search_console"]["inspect_per_day"] = 2
        sync.run(self.job(), "google")
        self.assertEqual(len(self.inspected()), 2)
        sync.run(self.job(NOW + timedelta(hours=1)), "google")
        self.assertEqual(len(self.inspected()), 2)            # today's 2 are used

    def test_zero_turns_it_off(self):
        self.config["search_console"]["inspect_per_day"] = 0
        sync.run(self.job(), "google")
        self.assertEqual(self.inspected(), [])

    def test_a_refusal_is_kept_and_never_fails_the_sync(self):
        self.config["search_console"]["inspect_per_day"] = 0
        self.assertEqual(sync.run(self.job(), "google"), 0)   # pages stored, none asked
        self.config["search_console"]["inspect_per_day"] = 5
        job = self.job()
        client = sync.google_client(job)
        got = inspect.run(job, client, "sc-domain:other.example")
        self.assertEqual(got["kept"], 0)
        self.assertIn("no access", got["error"])

    def test_a_job_on_another_api_never_asks_google(self):
        job = self.job()
        job.api = {k: v for k, v in job.api.items() if k != "google_inspect"}
        got = inspect.run(job, object(), "sc-domain:alpha.example")
        self.assertEqual(got, {"asked": 0, "kept": 0, "error": None})


class FakeInspect:
    """A URL Inspection client: counts the calls in flight; refuses the addresses in `refuse`."""
    def __init__(self, refuse=()):
        self.refuse, self.asked, self.lock = set(refuse), [], threading.Lock()
        self.flying = self.most = 0

    def token(self):
        return "token"

    def call_url(self, method, url, body):
        with self.lock:
            self.flying += 1
            self.most = max(self.most, self.flying)
            self.asked.append(body["inspectionUrl"])
        try:
            time.sleep(0.05)
            if body["inspectionUrl"] in self.refuse:
                raise http.Failed(429, "Quota exceeded for the day")
            return {"inspectionResult": {"indexStatusResult": {
                "verdict": "PASS", "coverageState": "Submitted and indexed"}}}
        finally:
            with self.lock:
                self.flying -= 1


class AtOnceAndInBatches(Base):
    def setUp(self):
        super().setUp()
        self.config["search_console"]["inspect_per_day"] = 0
        sync.run(self.job(), "google")                    # pages stored, none asked
        self.config["search_console"]["inspect_per_day"] = 200
        with History(self.db_path) as h:
            self.todo = inspect.candidates(h.db, SITE, self.config, NOW)
        self.assertGreaterEqual(len(self.todo), 3)

    def test_several_pages_are_asked_at_once(self):
        client = FakeInspect()
        got = inspect.run(self.job(), client, f"sc-domain:{SITE}")
        self.assertEqual((got["asked"], got["kept"], got["error"]),
                         (len(self.todo), len(self.todo), None))
        self.assertGreater(client.most, 1)
        self.assertLessEqual(client.most, inspect.WORKERS)

    def test_a_stop_part_way_keeps_the_batches_already_in(self):
        old = inspect.BATCH
        inspect.BATCH = 1
        self.addCleanup(setattr, inspect, "BATCH", old)
        client = FakeInspect(refuse={self.todo[1]})
        got = inspect.run(self.job(), client, f"sc-domain:{SITE}")
        self.assertIn("Quota", got["error"])
        self.assertEqual((got["asked"], got["kept"]), (2, 1))   # the 2nd batch refused
        self.assertEqual(len(self.rows()), 1)
        self.assertNotIn(self.todo[2], client.asked)            # no page asked after the refusal
        with History(self.db_path) as h:                        # the kept ones count today
            self.assertEqual(inspect.asked_today(h.db, SITE, NOW), 1)


class PageCountries(Base):
    def test_the_sync_keeps_each_page_with_its_country(self):
        self.config["search_console"]["inspect_per_day"] = 0
        self.assertEqual(sync.run(self.job(), "google"), 0)
        from skald.search import days as sd
        with History(self.db_path) as h:
            got, _ = sd.read(h.db, SITE, "google", NEWEST - timedelta(days=5), NEWEST,
                             kinds=("page", "page_country"))
        day = got[(NEWEST - timedelta(days=5)).isoformat()]
        rows = {r[0]: r[1:3] for r in day["page_country"]["rows"]}
        self.assertEqual(rows["https://www.alpha.example/blog/ai\tdeu"], [2, 40])
        self.assertEqual(rows["https://www.alpha.example/blog/ai\tgbr"], [1, 30])
        self.assertEqual(day["page_country"]["total"], day["page"]["total"])


class Reading(Base):
    def test_latest_names_the_change_and_counts_take_each_pages_newest(self):
        rows = []
        for n, (status, cov) in enumerate([("crawled_not_indexed", "Crawled - currently not indexed"),
                                            ("indexed", "Submitted and indexed")]):
            when = NOW + timedelta(days=n)
            rows.append({**inspect.row_of(SITE, "https://www.alpha.example/a",
                                          "sc-domain:alpha.example",
                                          {"inspectionResult": {"indexStatusResult": {
                                              "verdict": "PASS" if n else "NEUTRAL",
                                              "coverageState": cov,
                                              "googleCanonical": "https://www.alpha.example/a",
                                              "userCanonical": "https://www.alpha.example/a/"}}},
                                          when)})
        rows.append(inspect.row_of(SITE, "https://www.alpha.example/b", "sc-domain:alpha.example",
                                   {"inspectionResult": {"indexStatusResult": {
                                       "verdict": "NEUTRAL",
                                       "coverageState": "Discovered - currently not indexed"}}},
                                   NOW))
        with History(self.db_path) as h:
            inspect.write(h.db, rows, NOW + timedelta(days=1))
            a = inspect.latest(h.db, SITE, "/a")
            c = inspect.counts(h.db, SITE)
            self.assertIsNone(inspect.latest(h.db, SITE, "/never"))
        self.assertEqual(a["status"], "indexed")
        self.assertEqual(a["before"]["status"], "crawled_not_indexed")
        self.assertIs(a["canonical_match"], False)
        self.assertEqual(c["pages"], 2)
        self.assertEqual(c["by_status"], {"indexed": 1, "discovered_not_indexed": 1})
        self.assertEqual([r["path"] for r in c["not_indexed"]], ["/b"])


if __name__ == "__main__":
    unittest.main()
