"""#40: a search sync that stopped says so (search/health.py, search/sync.py's mails,
todos.search_todos, audit_search_sync.py).

A Search Console sync failed for twelve days and nobody was told. The rule: connected,
worked before, and since the last good sync every try failed, for a day or
health.STOPPED_TRIES tries in a row. Then a to-do on Overview > Insights, the state on
Settings and the Search tab, one mail when it stops and one when it is back, and a second
count from the kept tries. The fake engines of search_support.py answer the good syncs; a
failing try is a client that raises, as Google and Bing do. Example data only."""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import test_search_sync as tss  # noqa: E402

from skald import audit_more, audit_search_sync, todos  # noqa: E402
from skald.mcp import tools_search  # noqa: E402
from skald.search import bing, google, health, http, state, sync  # noqa: E402
from skald.store import History  # noqa: E402

SITE = tss.SITE
START = datetime(2026, 11, 1, 12, 40, tzinfo=timezone.utc)
DELETED = "Project #000000000000 has been deleted."     # Google's words, a made-up number


def frozen(at: datetime):
    """sync.py's clock at `at`: when a try ends (last_sync, last_ok, the tries)."""
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return at if tz else at.replace(tzinfo=None)
    return mock.patch.object(sync, "datetime", Clock)


class Refusing:
    """A client whose every call is refused, as the engine refuses it."""

    def __init__(self, engine: str):
        self.engine = engine

    def _no(self, *a, **k):
        if self.engine == "google":
            raise http.Failed(403, google.words_for(http.Failed(403, "HTTP 403", DELETED),
                                                    "robot@example.com"), DELETED)
        raise http.Failed(401, bing.words_for(http.Failed(401, "HTTP 401",
                                                          "The API key is not valid.")))

    query = traffic = stats = _no


class Case(tss.Base):
    engine = "google"

    def good(self, at: datetime) -> int:
        with frozen(at):
            return sync.run(self.job(at), self.engine)

    def bad(self, at: datetime) -> int:
        with frozen(at):
            return sync.run(self.job(at), self.engine, client=Refusing(self.engine))

    def health(self) -> dict:
        saved = state.load(self.folder, SITE)
        return health.of(saved, self.engine, sync.connected(self.config)[self.engine])

    def todos(self) -> tuple[list, list]:
        p = SimpleNamespace(config=self.config, key=SITE, history=None)
        return todos.search_todos(p)

    def audit(self) -> list[str] | None:
        ctx = SimpleNamespace(config=self.config, site=SITE, db_path=self.db_path)
        return audit_search_sync.daily(ctx, START.date())

    def subjects(self) -> list[str]:
        return [m["Subject"].removeprefix("[Skald] ") for m in self.mails]

    def tries(self, n: int, first: datetime, every=timedelta(hours=sync.EVERY_HOURS)):
        for i in range(n):
            self.assertEqual(self.bad(first + i * every), 1)


class Google(Case):
    def test_the_number_of_tries_is_a_day_of_the_scheduler(self):
        self.assertEqual(health.STOPPED_TRIES, 24 // sync.EVERY_HOURS)
        self.assertIn("search_sync", audit_more.DAILY)

    def test_never_worked_is_no_warning(self):
        self.tries(health.STOPPED_TRIES + 2, START)
        st = self.health()
        self.assertEqual(st["state"], "not_answering")
        self.assertFalse(st["stopped"])
        self.assertEqual(self.todos(), ([], []))
        self.assertEqual(len(self.mails), 1, "the old first-failure mail, once")
        self.assertIn("sync failing", self.mails[0]["Subject"])
        self.assertEqual(self.audit(), [])
        self.assertEqual(tools_search.state_words({**self.state(), "engine": "google"},
                                                  "sc-domain:x"), "never answered")

    def test_under_a_day_and_under_the_tries_is_no_warning(self):
        self.assertEqual(self.good(START), 0, self.said)
        self.tries(health.STOPPED_TRIES - 1, START + timedelta(hours=6))
        st = self.health()
        self.assertEqual((st["state"], st["fails"]), ("failing", health.STOPPED_TRIES - 1))
        self.assertEqual(self.todos(), ([], []))
        self.assertEqual(self.mails, [])
        self.assertEqual(self.audit(), [])
        self.assertEqual(tools_search.WORDS[st["state"]], "last try failed")

    def test_a_day_of_failures_warns_with_googles_reason(self):
        self.good(START)
        self.tries(2, START + timedelta(hours=1), every=timedelta(hours=23))   # 1 h, 24 h
        st = self.health()
        self.assertTrue(st["stopped"], st)
        self.assertEqual(st["fails"], 2, "the day, not the tries")
        self.assertEqual(st["reason"], f"Google said: {DELETED[:-1]}")
        self.assertIn("Google Cloud project behind Skald's robot key", st["advice"])
        got, gone = self.todos()
        self.assertEqual(gone, [])
        self.assertEqual(len(got), 1)
        t = got[0]
        self.assertEqual((t["id"], t["kind"], t["state"], t["agent"]),
                         ("search-sync-google", "search", "open", False))
        self.assertIn("since 1 Nov 2026 12:40 UTC", t["proof"])
        self.assertIn(DELETED[:-1], t["proof"])
        self.assertEqual(t["figures"]["since"], self.state()["last_ok"])
        self.assertEqual(t["open"], {"tab": "settings/site/leads", "tool": "search",
                                     "name": "Settings > Leads & tools > Search Console & Bing"})
        self.assertEqual(self.subjects(), [f"Search Console sync stopped for {SITE}"])
        body = self.mails[0].get_content()
        self.assertIn(DELETED[:-1], body)
        self.assertIn("What to do:", body)
        self.assertEqual(self.audit(), [])
        self.assertEqual(tools_search.WORDS[st["state"]], "stopped answering")

    def test_n_tries_in_a_row_warn_within_the_day(self):
        self.good(START)
        self.tries(health.STOPPED_TRIES, START + timedelta(minutes=10), every=timedelta(hours=1))
        st = self.health()
        self.assertTrue(st["stopped"])
        self.assertLess(st["hours"], health.STOPPED_HOURS)
        self.assertEqual(len(self.todos()[0]), 1)

    def test_mailed_once_then_back_once(self):
        self.good(START)
        self.tries(health.STOPPED_TRIES + 6, START + timedelta(hours=6))
        self.assertEqual(self.subjects(), [f"Search Console sync stopped for {SITE}"],
                         "once, not on every try")
        self.assertIsNotNone(self.state()["stopped_mailed"])
        self.assertEqual(self.good(START + timedelta(days=4)), 0)
        self.assertEqual(self.subjects()[1:], [f"Search Console sync back for {SITE}"])
        self.assertIn("no good sync from 1 Nov 2026 12:40 UTC", self.mails[1].get_content())
        st = self.health()
        self.assertEqual((st["state"], st["stopped"], st["fails"]), ("answering", False, 0))
        self.assertEqual(self.todos(), ([], []), "the warning goes")
        self.assertIsNone(self.state()["stopped_mailed"])
        self.assertEqual(self.good(START + timedelta(days=4, hours=6)), 0)
        self.assertEqual(len(self.mails), 2, "back: one mail, not one per good sync")
        self.assertEqual(self.audit(), [])

    def test_a_mail_that_cannot_go_is_tried_again(self):
        self.good(START)
        self.config["mail"] = {}
        self.tries(health.STOPPED_TRIES, START + timedelta(hours=6))
        self.assertIsNone(self.state().get("stopped_mailed"))
        self.config["mail"] = {"host": "smtp.example.com", "from": "skald@example.com",
                               "to": ["owner@example.com"]}
        self.tries(2, START + timedelta(days=2))
        self.assertEqual(len(self.mails), 1)

    def test_not_connected_is_never_stopped(self):
        self.good(START)
        self.tries(health.STOPPED_TRIES, START + timedelta(hours=6))
        del self.config["search_console"]
        self.assertEqual(self.health()["state"], "off")
        self.assertEqual(self.todos(), ([], []))
        self.assertEqual(self.audit(), [])

    def test_the_audit_agrees_then_catches_a_planted_change(self):
        self.good(START)
        self.tries(health.STOPPED_TRIES, START + timedelta(hours=6))
        self.assertEqual(self.audit(), [])
        part = self.state()
        state.update(self.folder, SITE, "google", fails=1,
                     last_sync=part["last_ok"])          # the summary says: one try, just now
        problems = self.audit()
        self.assertTrue(problems and "the tries say stopped" in problems[0], problems)
        got, gone = self.todos()
        self.assertEqual(got, [], "the summary says not stopped: no to-do; the audit says why")
        state.update(self.folder, SITE, "google", fails=part["fails"] + 1,
                     last_sync=part["last_sync"])
        problems = self.audit()
        self.assertTrue(any("failed in a row" in p for p in problems), problems)
        got, gone = self.todos()
        self.assertEqual(got, [])
        self.assertEqual([g["id"] for g in gone], ["search-sync-google"])
        self.assertIn("failed in a row", gone[0]["why"])

    def test_tries_are_kept_short_with_the_last_good_one(self):
        self.good(START)
        self.tries(health.KEEP_TRIES + 5, START + timedelta(hours=1), every=timedelta(hours=1))
        tries = self.state()["tries"]
        self.assertEqual(len(tries), health.KEEP_TRIES)
        self.assertTrue(tries[0]["ok"])
        self.assertEqual(tries[0]["at"], self.state()["last_ok"])
        self.assertEqual(self.audit(), [], "a cut list: the count is not compared")

    def test_a_state_file_from_before_starts_from_its_last_good_sync(self):
        state.update(self.folder, SITE, "google", ok=True, source="sc-domain:alpha.example",
                     last_sync="2026-10-30T00:00:00+00:00", last_ok="2026-10-30T00:00:00+00:00")
        self.assertIsNone(self.audit() or None)
        self.bad(START)
        self.assertTrue(self.health()["stopped"], "two days since its last good sync")
        self.assertTrue(self.state()["tries"][0].get("seeded"))
        self.assertEqual(self.audit(), [])


class Bing(Case):
    engine = "bing"

    def setUp(self):
        super().setUp()
        self.engines.bing["traffic"] = [("2026-10-01", 7, 90)]

    def test_the_same_for_bing(self):
        self.assertEqual(self.good(START), 0, self.said)
        self.tries(health.STOPPED_TRIES - 1, START + timedelta(hours=6))
        self.assertFalse(self.health()["stopped"])
        self.assertEqual(self.mails, [])
        self.tries(1, START + timedelta(days=1))
        st = self.health()
        self.assertTrue(st["stopped"])
        self.assertEqual(st["reason"], "Bing said: The API key is not valid", "Bing's own words")
        self.assertIn("Check the Bing API key", st["advice"])
        got, _ = self.todos()
        self.assertEqual([t["id"] for t in got], ["search-sync-bing"])
        self.assertEqual(self.subjects(), [f"Bing Webmaster Tools sync stopped for {SITE}"])
        self.tries(3, START + timedelta(days=2))
        self.assertEqual(len(self.mails), 1)
        self.assertEqual(self.audit(), [])
        self.good(START + timedelta(days=3))
        self.assertEqual(self.subjects()[1:], [f"Bing Webmaster Tools sync back for {SITE}"])
        self.assertEqual(self.todos(), ([], []))


class Words(unittest.TestCase):
    def test_reason_and_advice(self):
        self.assertEqual(health.reason("Search Console refused: x. (Google said: Project #1 has "
                                       "been deleted.)", "google"),
                         "Google said: Project #1 has been deleted")
        self.assertEqual(health.reason("Could not reach Google: timed out. More.", "google"),
                         "Could not reach Google: timed out")
        self.assertIn("service-account key", health.advice(
            "Google refused the service account's key: it may have been deleted", "google"))
        self.assertIn("Users and permissions", health.advice(
            "Search Console refused: robot@example.com has no access to this property.", "google"))
        self.assertIn("Sync now", health.advice("something new", "bing"))

    def test_status_without_tries(self):
        self.assertEqual(health.status({}, None)["state"], "off")
        self.assertEqual(health.status({}, "sc-domain:example.com")["state"], "waiting")
        old = {"engine": "google", "ok": False, "last_ok": "2026-11-01T00:00:00+00:00",
               "last_sync": "2026-11-02T00:00:00+00:00", "error": "HTTP 500"}
        self.assertTrue(health.status(old, "sc-domain:example.com")["stopped"],
                        "a day of failures, even with no count of tries")


class Page(Case):
    """search.json and Settings carry the same state as the to-do."""

    def test_search_json_and_settings(self):
        from skald.search import data as sdata
        self.good(START)
        self.tries(health.STOPPED_TRIES, START + timedelta(hours=6))
        with History(self.db_path) as h:
            p = SimpleNamespace(history=h, config=self.config, key=SITE)
            part = sdata.engine_part(p, SITE, "google", "sc-domain:alpha.example", self.folder)
        self.assertTrue(part["health"]["stopped"])
        self.assertNotIn("tries", part["status"], "the tries stay on the server")
        self.assertEqual(part["health"]["since"], self.todos()[0][0]["figures"]["since"])


if __name__ == "__main__":
    unittest.main()
