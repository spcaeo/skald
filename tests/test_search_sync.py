"""The search sync (search/sync.py, days.py, google.py, bing.py, state.py)
against a fake Google and Bing on 127.0.0.1 (search_support.py): the token
flow, paging, retries, the first sync and the next one re-fetching the last
days and the provisional ones, sums that hold, one mail per run of failures,
the lock, the host check, Bing's tables, and the second road
(audit_search.py) catching a planted error. No real API is ever called."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import search_support as ss  # noqa: E402

from skald import audit_search  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.search import bing, days, google, http, state, sync  # noqa: E402
from skald.store import History  # noqa: E402

SITE = "alpha.example"
NOW = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)     # 08:00 in Pacific Time
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
                       "bing": {"site_url": f"https://www.{SITE}/"},
                       "history": {"db": str(self.db_path)},
                       "mail": {"host": "smtp.example.com", "from": "skald@example.com",
                                "to": ["owner@example.com"]},
                       "_resolved": {"history_db": str(self.db_path)}}
        secrets_store.put(self.folder / "secrets.json", google.SECRET,
                          google.compact(ss.service_key()))
        secrets_store.put(self.folder / "secrets.json", bing.ENV, ss.BING_KEY)
        self.engines = ss.Engines()
        self.addCleanup(self.engines.stop)
        self.engines.data = ss.records(date(2026, 8, 1), NEWEST)
        self.engines.incomplete = "2026-10-15"
        self.mails, self.said, self.sleeps = [], [], []

    def job(self, now=NOW):
        return sync.Job(self.config, SITE, self.folder, self.db_path, now,
                        out=self.said.append, err=self.said.append,
                        sleep=self.sleeps.append, send=lambda msg, cfg: self.mails.append(msg),
                        api=self.engines.api())

    def stored(self, engine="google", first=date(2026, 1, 1), last=date(2026, 12, 31)):
        with History(self.db_path) as h:
            return days.read(h.db, SITE, engine, first, last)

    def state(self, engine="google"):
        return state.load(self.folder, SITE).get(engine) or {}


class Google(Base):
    def test_first_sync(self):
        self.assertEqual(sync.run(self.job(), "google"), 0, self.said)
        got, finals = self.stored()
        self.assertEqual(sorted(got)[0], (NEWEST - timedelta(days=27)).isoformat())
        self.assertEqual(sorted(got)[-1], NEWEST.isoformat())
        self.assertEqual(len(got), 28)
        self.assertEqual([d for d, f in finals.items() if not f], ["2026-10-15", "2026-10-16"])
        day = got["2026-10-01"]
        self.assertEqual(set(day), set(days.KINDS))
        want = ss.records(date(2026, 8, 1), NEWEST)["2026-10-01"]
        self.assertEqual(day["total"]["total"]["clicks"], sum(r["clicks"] for r in want))
        self.assertEqual(day["total"]["total"]["impressions"], sum(r["impressions"] for r in want))
        query = day["query"]
        self.assertEqual([r[0] for r in query["rows"]],
                         ["server log analytics", "ai crawler log", "skald"])
        # The anonymised query is in the total, in no row: unattributed, never hidden.
        self.assertEqual(query["unattributed"], {"clicks": 1, "impressions": 30})
        self.assertFalse(query["complete"])
        self.assertTrue(day["country"]["complete"])
        self.assertEqual({r[0] for r in day["country"]["rows"]}, {"usa", "deu", "gbr"})
        # Search appearance was refused with the date: asked one day at a time.
        self.assertEqual(day["appearance"]["rows"][0][:3], ["AMP_BLUE_LINK", 2, 40])
        self.assertEqual(day["appearance"]["unattributed"]["clicks"],
                         sum(r["clicks"] for r in want) - 2)
        for d, kinds in got.items():
            for kind, blob in kinds.items():
                self.assertEqual(days.sums_hold(blob), [], (d, kind))
        s = self.state()
        self.assertTrue(s["ok"])
        self.assertEqual((s["days"], s["last"], s["provisional"]), (28, NEWEST.isoformat(), 2))
        self.assertIsNone(s["error"])
        # The next sync is EVERY_HOURS after the last one (both from the sync's end, state.py).
        last = datetime.fromisoformat(s["last_sync"])
        self.assertEqual(s["next_sync"], (last + timedelta(hours=sync.EVERY_HOURS)).isoformat(timespec="seconds"))
        # The token: a JWT signed RS256, checked by the fake token endpoint.
        self.assertEqual(self.engines.claims[0]["iss"], ss.EMAIL)
        self.assertEqual(self.engines.claims[0]["scope"], google.SCOPE)
        self.assertEqual(len(self.engines.claims), 1, "one token for the whole sync")

    def test_a_complete_day_is_final_only_when_three_days_old(self):
        # 31 Oct: Google named no incomplete day, 30 Oct was stored final, and asking for
        # its final figures got 0 / 0 (run-daily's search recount failed).
        self.engines.incomplete = None
        self.assertEqual(sync.run(self.job(), "google"), 0, self.said)
        got, finals = self.stored()
        self.assertEqual([d for d, f in finals.items() if not f], ["2026-10-16"])
        self.assertTrue(finals["2026-10-15"], "3 days before the 18th, complete: final")

    def test_next_sync_refetches_last_days_and_provisional(self):
        sync.run(self.job(), "google")
        first = len(self.engines.calls)
        # Google finishes 10-15 and 10-16 with other figures, adds 10-17.
        self.engines.data = ss.records(date(2026, 8, 1), date(2026, 10, 17), scale=2)
        self.engines.incomplete = "2026-10-17"
        self.assertEqual(sync.run(self.job(NOW + timedelta(hours=6)), "google"), 0, self.said)
        asked = [c[2] for c in self.engines.calls[first:] if c[1].endswith("/query")
                 and c[2].get("aggregationType") == "byPage"]
        self.assertEqual((asked[0]["startDate"], asked[-1]["endDate"]),
                         ("2026-10-13", "2026-10-17"))
        got, finals = self.stored()
        self.assertEqual(len(got), 29)
        # 10-16 is complete but 2 days old on the 18th (days.GOOGLE_FINAL_DAYS).
        self.assertEqual([d for d, f in finals.items() if not f], ["2026-10-16", "2026-10-17"])
        new = ss.records(date(2026, 8, 1), date(2026, 10, 17), scale=2)
        for d in ("2026-10-13", "2026-10-15", "2026-10-16"):
            self.assertEqual(got[d]["total"]["total"]["clicks"], sum(r["clicks"] for r in new[d]))
        old = ss.records(date(2026, 8, 1), NEWEST)
        self.assertEqual(got["2026-10-12"]["total"]["total"]["clicks"],
                         sum(r["clicks"] for r in old["2026-10-12"]), "older days left alone")

    def test_backfill_with_progress(self):
        self.assertEqual(sync.run(self.job(), "google", backfill_months=3), 0, self.said)
        got, _ = self.stored()
        self.assertEqual(len(got), (NEWEST - date(2026, 8, 1)).days + 1)
        self.assertEqual(min(got), "2026-08-01", "nothing Google has not got is stored")
        back = self.state()["backfill"]
        self.assertEqual((back["state"], back["done"], back["of"]), ("done", 14, 14))

    def test_empty_day_inside_the_range_is_zero(self):
        del self.engines.data["2026-10-10"]
        sync.run(self.job(), "google")
        got, _ = self.stored()
        self.assertEqual(got["2026-10-10"]["total"]["total"],
                         {"clicks": 0, "impressions": 0, "position": None})

    def test_paging(self):
        with mock.patch.object(google, "ROW_LIMIT", 2):
            sync.run(self.job(), "google")
        got, _ = self.stored()
        self.assertEqual(len(got["2026-10-01"]["query"]["rows"]), 3)

    def test_retry_then_ok(self):
        self.engines.fail = [429, 503]
        self.assertEqual(sync.run(self.job(), "google"), 0, self.said)
        self.assertEqual(self.sleeps[:2], [1.0, 2.0])

    def test_permission_removed_mails_once(self):
        sync.run(self.job(), "google")
        del self.engines.props[f"sc-domain:{SITE}"]
        self.assertEqual(sync.run(self.job(), "google"), 1)
        s = self.state()
        self.assertFalse(s["ok"])
        self.assertIn("has no access to this property", s["error"])
        self.assertIn(ss.EMAIL, s["error"])
        self.assertNotIn(ss.TOKEN, s["error"])
        self.assertEqual(len(self.mails), 1)
        self.assertIn("Search Console sync failing", self.mails[0]["Subject"])
        self.assertEqual(sync.run(self.job(), "google"), 1)
        self.assertEqual(len(self.mails), 1, "one mail per run of failures")
        self.assertEqual(s["days"], 28, "what was synced stays")
        self.engines.props[f"sc-domain:{SITE}"] = "siteRestrictedUser"
        self.assertEqual(sync.run(self.job(), "google"), 0)
        self.assertIsNone(self.state()["error_mailed"])
        del self.engines.props[f"sc-domain:{SITE}"]
        sync.run(self.job(), "google")
        self.assertEqual(len(self.mails), 2, "a new run of failures mails again")

    def test_lock(self):
        with state.lock(self.folder, SITE):
            self.assertEqual(sync.run(self.job(), "google"), 3)
        self.assertEqual(self.engines.calls, [])

    def test_property_must_cover_the_sites_hosts(self):
        self.config["search_console"]["property"] = "https://www.beta.example/"
        self.assertEqual(sync.run(self.job(), "google"), 1)
        self.assertIn("does not cover this site's host names", self.state()["error"])
        self.assertEqual(self.engines.calls, [])

    def test_no_key(self):
        secrets_store.delete(self.folder / "secrets.json", [google.SECRET])
        self.assertEqual(sync.run(self.job(), "google"), 1)
        self.assertIn("No service-account key", self.state()["error"])

    def test_not_connected_does_nothing(self):
        del self.config["search_console"]
        self.assertEqual(sync.run(self.job(), "google"), 0)
        self.assertEqual(self.engines.calls, [])

    def test_wizard_test_stores_nothing(self):
        got = sync.test(self.job(), "google", f"sc-domain:{SITE}")
        self.assertTrue(got["ok"])
        self.assertEqual(got["days"], ["2026-10-14", "2026-10-15", "2026-10-16"])
        want = ss.records(date(2026, 8, 1), NEWEST)
        self.assertEqual(got["clicks"], sum(r["clicks"] for d in got["days"] for r in want[d]))
        self.assertEqual(self.stored()[0], {})


class Bing(Base):
    def setUp(self):
        super().setUp()
        self.engines.bing["traffic"] = [("2026-10-01", 7, 90), ("2026-10-12", 3, 50)]
        self.engines.bing["query"] = [("2026-10-01", "skald", 4, 50, 2.0),
                                      ("2026-10-01", "log analytics", 2, 30, -1),
                                      ("2026-10-12", "skald", 3, 20, 1.5)]
        self.engines.bing["page"] = [("2026-10-01", "https://www.alpha.example/", 5, 60, 3.0)]

    def test_sync(self):
        self.assertEqual(sync.run(self.job(), "bing"), 0, self.said)
        got, finals = self.stored("bing")
        self.assertEqual(sorted(got), ["2026-10-01", "2026-10-12"])
        self.assertEqual(finals, {"2026-10-01": True, "2026-10-12": False})
        self.assertEqual(got["2026-10-01"]["total"]["total"]["clicks"], 7)
        query = got["2026-10-01"]["query"]
        self.assertEqual(query["rows"], [["skald", 4, 50, 2.0], ["log analytics", 2, 30, None]])
        self.assertEqual(query["total"]["clicks"], 6, "Bing's top rows: their own sum")
        self.assertTrue(query["complete"])

    def test_bad_key_scrubbed(self):
        secrets_store.put(self.folder / "secrets.json", bing.ENV, "X" * 32)
        self.assertEqual(sync.run(self.job(), "bing"), 1)
        error = self.state("bing")["error"]
        self.assertIn("Bing refused the API key", error)
        self.assertNotIn("X" * 32, error)
        self.assertNotIn("X" * 32, " ".join(map(str, self.said)))

    def test_dates(self):
        self.assertEqual(bing.parse_date("/Date(1316156400000-0700)/"), date(2011, 9, 16))
        self.assertEqual(bing.parse_date("/Date(1316156400000)/"), date(2011, 9, 16))
        self.assertIsNone(bing.parse_date("yesterday"))


class SecondRoad(Base):
    def ctx(self):
        return SimpleNamespace(config=self.config, site=SITE, db_path=self.db_path,
                               now=NOW, out=self.said.append, err=self.said.append,
                               history=lambda: History(self.db_path))

    def test_matches_then_catches_a_planted_error(self):
        sync.run(self.job(), "google")
        with mock.patch.object(sync, "job_of", lambda ctx: self.job()):
            self.assertEqual(audit_search.daily(self.ctx(), NOW.date()), [])
            self.assertTrue(self.state()["audit"]["ok"])
            with History(self.db_path) as h:
                row = h.db.execute("SELECT data FROM search_days WHERE site = ? AND day = ? "
                                   "AND kind = 'query'", (SITE, "2026-10-01")).fetchone()
                blob = json.loads(row[0])
                blob["rows"][0][1] += 1
                with h.db:
                    h.db.execute("UPDATE search_days SET data = ? WHERE site = ? AND day = ? "
                                 "AND kind = 'query'", (json.dumps(blob), SITE, "2026-10-01"))
            problems = audit_search.daily(self.ctx(), NOW.date())
            self.assertEqual(len(problems), 1, problems)
            self.assertIn("2026-10-01 query: clicks", problems[0])
            self.assertFalse(self.state()["audit"]["ok"])

    def test_refetch_catches_a_changed_figure(self):
        sync.run(self.job(), "google")
        self.engines.data["2026-10-14"][0]["clicks"] += 5
        with mock.patch.object(sync, "job_of", lambda ctx: self.job()):
            problems = audit_search.daily(self.ctx(), NOW.date())
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("2026-10-14", problems[0])
        self.assertIn("the engine now says", problems[0])

    def test_unreachable_is_not_a_mismatch(self):
        sync.run(self.job(), "google")
        with mock.patch.object(sync, "job_of", lambda ctx: self.job()), \
                mock.patch.object(sync, "google_client",
                                  side_effect=http.Failed(0, "could not reach Google")):
            self.assertEqual(audit_search.daily(self.ctx(), NOW.date()), [])
        self.assertTrue(any("not checked today" in str(s) for s in self.said))

    def test_not_connected(self):
        del self.config["search_console"], self.config["bing"]
        self.assertIsNone(audit_search.daily(self.ctx(), NOW.date()))
        self.assertFalse(audit_search.set_up(self.ctx()))


class Fold(unittest.TestCase):
    def test_top_others_unattributed_add_up(self):
        rows = [[f"q{i}", i, 10 * i, float(i)] for i in range(1, 8)]
        blob = days.fold(rows, {"clicks": 40, "impressions": 300, "position": 4.0}, 3)
        self.assertEqual([r[0] for r in blob["rows"]], ["q7", "q6", "q5"])
        self.assertEqual(blob["others"]["rows"], 4)
        self.assertEqual(blob["others"]["clicks"], 1 + 2 + 3 + 4)
        self.assertEqual(blob["unattributed"], {"clicks": 12, "impressions": 20})
        self.assertEqual(days.sums_hold(blob), [])

    def test_overlap_is_negative_never_hidden(self):
        blob = days.fold([["A", 5, 50, 1.0], ["B", 4, 40, 2.0]],
                         {"clicks": 6, "impressions": 60, "position": 1.5}, 10)
        self.assertEqual(blob["unattributed"], {"clicks": -3, "impressions": -30})
        self.assertEqual(days.sums_hold(blob), [])

    def test_write_refuses_what_does_not_add_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            with History(Path(tmp) / "h.sqlite") as h:
                bad = days.fold([["a", 1, 1, 1.0]], None, 5)
                bad["total"]["clicks"] = 9
                with self.assertRaises(ValueError):
                    days.write(h.db, SITE, "google", {date(2026, 10, 1): {"query": bad}},
                               {}, "sc-domain:alpha.example", NOW)
                self.assertEqual(h.db.execute("SELECT COUNT(*) FROM search_days").fetchone()[0],
                                 0)


class Command(unittest.TestCase):
    def test_commands_registered_and_quiet_when_not_connected(self):
        from support import Sandbox
        box = Sandbox()
        try:
            for args in (("search", "sync"), ("search-console", "import"), ("bing", "sync")):
                code, out, err = box.run(*args)
                self.assertEqual(code, 0, err)
            code, out, _ = box.run("search-console", "status")
            self.assertEqual(code, 0)
            self.assertIn("Search Console example.com: not connected", out)
        finally:
            box.close()


class Scheduler(unittest.TestCase):
    def test_every_six_hours_from_0140(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docker"))
        import scheduler
        after = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)     # 08:00 in New York
        got = scheduler.next_hours(after, "01:40", 6, "America/New_York")
        self.assertEqual(got, datetime(2026, 10, 18, 17, 40, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            scheduler.next_hours(after, "01:40", 5, "UTC")


if __name__ == "__main__":
    unittest.main()
