"""AI answers (skald/answers/, audit_ai_answers.py): each provider's
request (the place passed in the API's location field, or written into the
question for Gemini; the language), each answer read with its citations in
order, retries with backoff and no key in a reason, Gemini's redirects
resolved, the brand found as a whole word with its rank, own pages and
competitors, tracking profiles checked, versioned, paused, duplicated and
deleted (never erased), a run asked through a fake transport (never a real
API), the daily cap stopping a run that goes on the next day, figures
written and recounted by the second road (a tampered answer or figure is
withheld), the estimate, and ai_answers.json with the cited -> read -> sent
-> leads chain. Hosts are example.com / example.org; keys are made up."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import answers, audit_ai_answers  # noqa: E402
from skald.answers import data, match, profiles, providers, run, store  # noqa: E402

KEY = "sk-made-up-0123456789"
UTC = timezone.utc
TZ = ZoneInfo("America/Toronto")
WHERE = {"city": "Toronto", "region": "Ontario", "country": "CA", "lat": 43.65, "lon": -79.38,
         "timezone": "America/Toronto", "language": "fr-CA"}
BRANDS = ["Example Analytics", "example.com"]
COMPETITORS = ["Northwind Analytics", "contoso.example.org"]
OWN = ["example.com"]


def openai_answer(text, urls):
    return {"output": [{"type": "web_search_call", "id": "ws_1", "status": "completed"},
                       {"type": "message", "content": [{"type": "output_text", "text": text,
                        "annotations": [{"type": "url_citation", "url": u, "title": "t",
                                         "start_index": 0, "end_index": 1} for u in urls]}]}]}


def perplexity_answer(text, results):
    return {"object": "response", "status": "completed", "output": [
        {"type": "search_results", "results": [{"id": i, "url": u, "title": "t"}
                                               for i, u in enumerate(results, 1)]},
        {"type": "message", "role": "assistant", "content": [
            {"type": "output_text", "text": text, "annotations": []}]}]}


def gemini_answer(text, chunks):
    return {"candidates": [{"content": {"parts": [{"text": text}]}, "groundingMetadata": {
        "groundingChunks": [{"web": {"uri": u, "title": t}} for u, t in chunks]}}]}


def claude_answer(text, urls, stop="end_turn"):
    return {"stop_reason": stop, "content": [
        {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "q"}},
        {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": []},
        {"type": "text", "text": text, "citations": [
            {"type": "web_search_result_location", "url": u, "title": "t", "cited_text": "c"}
            for u in urls]}]}


TEXT = ("Northwind Analytics is popular. Example Analytics reads your server logs, "
        "and contoso.example.org is another choice.")


class Fake:
    """A transport: one canned answer per provider host, every call recorded."""

    def __init__(self, status=None):
        self.calls, self.status = [], status or {}

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, headers, json.loads(body) if body else None))
        host = url.split("/")[2]
        if method == "HEAD":
            return 302, {"Location": "https://www.example.com/pricing/?ref=g"}, b""
        if host in self.status:
            code = self.status[host].pop(0) if self.status[host] else 200
            if code != 200:
                return code, {"Retry-After": "1"}, b'{"error": {"message": "slow down"}}'
        if host == "api.openai.com":
            got = openai_answer(TEXT, ["https://example.com/pricing/", "https://example.org/x"])
        elif host == "api.perplexity.ai":
            got = perplexity_answer("A tool [2] and " + TEXT + " [1]",
                                    ["https://www.example.com/docs/", "https://example.org/"])
        elif host == "generativelanguage.googleapis.com":
            got = gemini_answer("Nothing about us here.", [
                ("https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "example.com")])
        else:
            got = claude_answer(TEXT, ["https://other.example.org/", "https://example.com/"])
        return 200, {}, json.dumps(got).encode()


class Requests(unittest.TestCase):
    def test_location_and_language_per_provider(self):
        url, headers, body = providers.request("openai", "gpt-4.1-mini", "Best tool?", WHERE, KEY)
        self.assertEqual(url, "https://api.openai.com/v1/responses")
        self.assertEqual(headers["Authorization"], f"Bearer {KEY}")
        tool = body["tools"][0]
        self.assertEqual(tool["type"], "web_search")
        self.assertEqual(tool["user_location"], {"type": "approximate", "city": "Toronto",
                                                 "region": "Ontario", "country": "CA",
                                                 "timezone": "America/Toronto"})
        self.assertTrue(body["input"].endswith("Answer in fr-CA."))
        _, _, body = providers.request("perplexity", "fast", "Best tool?", WHERE, KEY)
        self.assertEqual(body["preset"], "fast")
        self.assertEqual(body["language_preference"], "fr")
        self.assertEqual(body["tools"][0]["user_location"]["latitude"], 43.65)
        self.assertEqual(body["input"], "Best tool?")
        _, _, body = providers.request("perplexity", "openai/gpt-5.5", "Q?", WHERE, KEY)
        self.assertEqual(body["model"], "openai/gpt-5.5")
        url, headers, body = providers.request("gemini", "gemini-2.5-flash", "Best tool?", WHERE, KEY)
        self.assertIn("models/gemini-2.5-flash:generateContent", url)
        self.assertEqual(headers, {"x-goog-api-key": KEY})
        self.assertEqual(body["tools"], [{"google_search": {}}])
        self.assertIn("I am in Toronto, Ontario, CA.", body["contents"][0]["parts"][0]["text"])
        _, headers, body = providers.request("anthropic", "claude-haiku-4-5", "Q?", WHERE, KEY)
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(body["tools"][0]["type"], "web_search_20250305")
        self.assertEqual(body["tools"][0]["user_location"]["city"], "Toronto")
        english = dict(WHERE, language="en")
        self.assertEqual(providers.question_text("openai", "Q?", english), "Q?")

    def test_answers_read_with_citations_in_order(self):
        got = providers.parse("openai", openai_answer("Hi", ["https://a.example.org/", "https://a.example.org/"]))
        self.assertEqual(got, {"text": "Hi", "citations": [{"url": "https://a.example.org/", "title": "t"}]})
        got = providers.parse("perplexity", perplexity_answer("x [2] y [web:1]", ["https://one.example/", "https://two.example/"]))
        self.assertEqual([c["url"] for c in got["citations"]], ["https://two.example/", "https://one.example/"])
        sonar = {"choices": [{"message": {"content": "old"}}], "citations": ["https://s.example/"]}
        self.assertEqual(providers.parse("perplexity", sonar)["citations"][0]["url"], "https://s.example/")
        got = providers.parse("anthropic", claude_answer("A", ["https://c.example/"]))
        self.assertEqual(got["citations"][0]["url"], "https://c.example/")

    def test_gemini_redirects_resolved_or_kept_by_domain(self):
        fake = Fake()
        got = providers.ask("gemini", KEY, "gemini-2.5-flash", "Q?", WHERE, fake, sleep=lambda s: None)
        self.assertEqual(got["citations"][0]["url"], "https://www.example.com/pricing/?ref=g")
        self.assertEqual(fake.calls[-1][0], "HEAD")
        broken = lambda m, u, h, b, t: (404, {}, b"") if m == "HEAD" else Fake()(m, u, h, b, t)  # noqa: E731
        got = providers.ask("gemini", KEY, "gemini-2.5-flash", "Q?", WHERE, broken, sleep=lambda s: None)
        self.assertEqual(got["citations"][0]["domain"], "example.com")

    def test_retries_backoff_and_no_key_in_reasons(self):
        waits = []
        fake = Fake({"api.openai.com": [429, 503]})
        got = providers.ask("openai", KEY, "m", "Q?", WHERE, fake, sleep=waits.append)
        self.assertTrue(got["text"])
        self.assertEqual(len(waits), 2)
        self.assertGreaterEqual(waits[1], waits[0])
        bad = lambda m, u, h, b, t: (401, {}, json.dumps({"error": {"message": f"bad key {KEY}"}}).encode())  # noqa: E731
        with self.assertRaises(providers.Failed) as caught:
            providers.ask("openai", KEY, "m", "Q?", WHERE, bad, sleep=waits.append)
        self.assertNotIn(KEY, str(caught.exception))
        self.assertIn("HTTP 401", str(caught.exception))
        self.assertEqual(len(waits), 2, "a 401 is not tried again")

    def test_claude_pause_turn_is_finished(self):
        answers_ = [claude_answer("", [], "pause_turn"), claude_answer("Done", ["https://example.com/"])]
        sent = []

        def t(m, u, h, b, timeout):
            sent.append(json.loads(b))
            return 200, {}, json.dumps(answers_.pop(0)).encode()
        got = providers.ask("anthropic", KEY, "m", "Q?", WHERE, t, sleep=lambda s: None)
        self.assertEqual(got["text"], "Done")
        self.assertEqual(sent[1]["messages"][1]["role"], "assistant")


class Reading(unittest.TestCase):
    def test_brand_rank_pages_and_competitors(self):
        cites = [{"url": "https://other.example.org/"}, {"url": "https://www.example.com/pricing/?a=1#x"},
                 {"url": "https://contoso.example.org/p"}]
        got = match.analyse(TEXT, cites, BRANDS, COMPETITORS, OWN)
        self.assertEqual(got, {"mentioned": True, "mention_rank": 2, "own_pages": ["/pricing/"],
                               "cite_rank": 2, "competitors": ["Northwind Analytics", "contoso.example.org"]})
        self.assertFalse(match.analyse("Example Analyticsville", [], BRANDS, [], OWN)["mentioned"])
        self.assertTrue(match.analyse("use EXAMPLE ANALYTICS's plan", [], BRANDS, [], OWN)["mentioned"])
        gem = match.analyse("x", [{"url": "https://r.example/", "domain": "example.com"}], BRANDS, [], OWN)
        self.assertEqual(gem["own_pages"], [match.UNKNOWN_PAGE])
        for text in (TEXT, "Example Analyticsville", "plan: example.com.", "C++ and Example Analytics_x"):
            for c in ([], cites):
                plan = {"brands": BRANDS + ["C++"], "competitors": COMPETITORS, "own_hosts": OWN}
                self.assertEqual(audit_ai_answers.reread(text, c, plan),
                                 match.analyse(text, c, plan["brands"], COMPETITORS, OWN), text)


def profile_body(**over):
    body = {"name": "Toronto", "city": "Toronto", "region": "Ontario", "country": "ca",
            "language": "en", "questions": ["Best server log analytics?", "Analytics without cookies?"],
            "brands": BRANDS, "competitors": COMPETITORS,
            "providers": ["openai", "perplexity", "gemini", "anthropic"], "frequency": "weekly",
            "repeats": 2, "cap": 5}
    body.update(over)
    return profiles.check(body)


class Profiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = store.connect(Path(self.tmp.name) / store.FILE)
        self.addCleanup(self.db.close)

    def test_checked(self):
        body = profile_body()
        self.assertEqual(body["country"], "CA")
        self.assertIsNone(body["gbp_location_id"])
        for bad in ({"country": "CAN"}, {"language": "not a lang"}, {"repeats": 6}, {"cap": 0},
                    {"providers": ["bard"]}, {"frequency": "hourly"}, {"lat": 10},
                    {"questions": ["x" * 301]}, {"name": ""}, {"timezone": "Mars/Base"}):
            with self.assertRaises(profiles.Invalid, msg=bad):
                profile_body(**bad)

    def test_versions_pause_duplicate_delete_never_erased(self):
        now = datetime(2026, 10, 12, 10, tzinfo=UTC)
        pid = profiles.create(self.db, "example.com", profile_body(), "admin", now)
        self.assertEqual(profiles.update(self.db, "example.com", pid, profile_body(repeats=3), "admin", now), 2)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM profile_versions").fetchone()[0], 2)
        self.assertTrue(profiles.pause(self.db, "example.com", pid, True, "admin", now))
        self.assertFalse(profiles.pause(self.db, "example.com", pid, True, "admin", now))
        p = profiles.one(self.db, "example.com", pid)
        self.assertTrue(profiles.is_paused(p, now + timedelta(hours=1)))
        self.assertIsNone(profiles.due(p, None, now.astimezone(TZ), {}))
        profiles.pause(self.db, "example.com", pid, False, "admin", now + timedelta(hours=2))
        p = profiles.one(self.db, "example.com", pid)
        self.assertTrue(profiles.is_paused(p, now + timedelta(hours=1)), "the pause is kept")
        self.assertFalse(profiles.is_paused(p, now + timedelta(hours=3)))
        copy = profiles.duplicate(self.db, "example.com", pid, "admin", now)
        self.assertEqual(profiles.one(self.db, "example.com", copy)["name"], "Toronto (copy)")
        profiles.delete(self.db, "example.com", pid, "admin", now)
        self.assertEqual([x["id"] for x in profiles.listed(self.db, "example.com")], [copy])
        self.assertIsNotNone(profiles.one(self.db, "example.com", pid)["removed_at"])

    def test_due(self):
        p = profile_body()
        at = datetime(2026, 10, 12, 7, tzinfo=TZ)
        self.assertEqual(profiles.due(p, None, at, {}), "schedule")
        self.assertIsNone(profiles.due(p, None, at.replace(hour=5), {}))
        self.assertIsNone(profiles.due(p, "2026-10-08", at, {}))
        self.assertEqual(profiles.due(p, "2026-10-05", at, {}), "schedule")
        self.assertEqual(profiles.due({**p, "run_requested_at": "x"}, "2026-10-12", at, {}), "requested")

    def test_estimate(self):
        got = answers.estimate(profile_body(), 2, {}, {"openai": True, "gemini": True})
        self.assertEqual(got["answers"], 2 * 2 * 2)
        self.assertAlmostEqual(got["per_run"], 4 * (answers.PRICE["openai"] + answers.PRICE["gemini"]))
        self.assertAlmostEqual(got["per_month"], round(got["per_run"] * 4.3, 2))
        self.assertTrue(got["fits"])
        small = answers.estimate({**profile_body(), "cap": 0.1}, 2, {}, None)
        self.assertFalse(small["fits"])
        self.assertGreater(small["days"], 1)


class Runs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": "example.com", "hosts": ["example.com", "www.example.com"]}}
        env = mock.patch.dict(os.environ, {"SKALD_OPENAI_API_KEY": KEY, "SKALD_PERPLEXITY_API_KEY": KEY,
                                           "SKALD_GEMINI_API_KEY": KEY, "SKALD_ANTHROPIC_API_KEY": KEY})
        env.start()
        self.addCleanup(env.stop)
        self.config["history"] = {"db": str(self.folder / "history.sqlite")}
        with store.opened(self.folder) as db:
            self.pid = profiles.create(db, "example.com", profile_body(), "admin")
        self.lines = []

    def go(self, now, fake=None, **kw):
        fake = fake or Fake()
        got = run.run_site(self.folder, "example.com", self.config, TZ, now, None,
                           transport=fake, sleep=lambda s: None, out=self.lines.append,
                           err=self.lines.append, **kw)
        return got, fake

    def test_a_run_stored_figured_and_verified(self):
        got, fake = self.go(datetime(2026, 10, 12, 12, tzinfo=UTC))
        self.assertEqual((got["asked"], got["done"], got["withheld"]), (16, 1, 0))
        self.assertFalse(any(KEY in line for line in self.lines))
        with store.opened(self.folder) as db:
            figs = {f["provider"]: f for f in store.figures(db, "example.com")}
            self.assertEqual(figs["openai"]["asked"], 4)
            self.assertEqual(figs["openai"]["mentioned"], 4)
            self.assertEqual(figs["openai"]["cited"], 4)
            self.assertEqual(figs["openai"]["competitor_mentions"], 8)
            self.assertEqual((figs["openai"]["rank_sum"], figs["openai"]["rank_n"]), (4, 4))
            self.assertEqual((figs["anthropic"]["rank_sum"], figs["gemini"]["mentioned"]), (8, 0))
            self.assertEqual(figs["gemini"]["cited"], 4, "the resolved redirect is an own page")
            self.assertTrue(all(f["verified"] == 1 for f in figs.values()))
            run_id = figs["openai"]["run_id"]
            self.assertEqual(audit_ai_answers.recheck_run(db, run_id), [])
            # A tampered reading or figure: the second road says so.
            # providers run at once, so pick an answer that does mention the site
            db.execute("UPDATE answers SET mentioned = 0 WHERE id = (SELECT MIN(id) FROM answers WHERE mentioned = 1)")
            db.execute("UPDATE figures SET cited = 1 WHERE provider = 'perplexity'")
            db.commit()
            problems = audit_ai_answers.recheck_run(db, run_id)
            self.assertEqual(len(problems), 2, problems)
        # Not due again within the week; asked to run now, it is.
        got, _ = self.go(datetime(2026, 10, 13, 12, tzinfo=UTC))
        self.assertEqual(got["runs"], 0)
        with store.opened(self.folder) as db:
            profiles.request_run(db, "example.com", self.pid)
        got, _ = self.go(datetime(2026, 10, 13, 12, tzinfo=UTC))
        self.assertEqual(got["done"], 1)

    def test_the_daily_cap_stops_and_the_run_goes_on_tomorrow(self):
        with store.opened(self.folder) as db:
            profiles.update(db, "example.com", self.pid, profile_body(cap=0.3), "admin")
        got, _ = self.go(datetime(2026, 10, 12, 12, tzinfo=UTC))
        self.assertEqual((got["capped"], got["done"]), (1, 0))
        with store.opened(self.folder) as db:
            self.assertLessEqual(store.spent(db, "example.com", self.pid, date(2026, 10, 12)), 0.3 + 1e-9)
        days = 0
        while True:
            days += 1
            got, _ = self.go(datetime(2026, 10, 12, 12, tzinfo=UTC) + timedelta(days=days))
            if got["done"]:
                break
            self.assertLess(days, 10)
        with store.opened(self.folder) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM answers").fetchone()[0], 16)
            self.assertTrue(all(f["verified"] == 1 for f in store.figures(db, "example.com")))

    def test_no_key_left_out_and_failures_kept(self):
        with mock.patch.dict(os.environ, {"SKALD_GEMINI_API_KEY": "", "SKALD_ANTHROPIC_API_KEY": ""}):
            got, fake = self.go(datetime(2026, 10, 12, 12, tzinfo=UTC),
                                Fake({"api.perplexity.ai": [500] * 20}))
        self.assertTrue(any("no API key for gemini, anthropic" in x for x in self.lines))
        self.assertEqual(got["asked"], 8)
        self.assertEqual(got["failed"], 4)
        hosts = {c[1].split("/")[2] for c in fake.calls}
        self.assertNotIn("api.anthropic.com", hosts)
        with store.opened(self.folder) as db:
            failed = db.execute("SELECT error FROM answers WHERE ok = 0").fetchall()
            self.assertTrue(all("HTTP 500" in r[0] for r in failed))
            self.assertEqual(audit_ai_answers.daily(SimpleNamespace(
                db_path=self.folder / "history.sqlite", site="example.com"), date(2026, 10, 12)), [])


class DataFile(Runs):
    def page(self, extras, conversions=None):
        history = SimpleNamespace(path=self.folder / "history.sqlite",
                                  extras=lambda site, first, last, kinds: extras)
        if conversions:
            db = sqlite3.connect(self.folder / "conversions.sqlite")
            db.execute("CREATE TABLE conversions (site, stage, at, landing, first_source, test)")
            db.executemany("INSERT INTO conversions VALUES (?,?,?,?,?,?)", conversions)
            db.commit()
            db.close()
        today = date(2026, 10, 20)
        return SimpleNamespace(site="example.com", key="example.com", tz=TZ, config=self.config,
                               live_dir=None, history=history, today=today,
                               anchor=today - timedelta(days=1),
                               counted_days=lambda: list(extras))

    def test_not_set_up_then_the_chain(self):
        empty = DataFile.page(self, {})
        with mock.patch.object(store, "path_for", lambda folder: Path(folder) / "none.sqlite"):
            got = data.build(empty)
        self.assertEqual(got["state"], "not set up")
        self.go(datetime(2026, 10, 12, 12, tzinfo=UTC))
        extras = {"2026-10-12": {
            "ai_fetches": {"rows": [["2026-10-12T10:00", "chatgpt.com", "/pricing", 3, 2],
                                   ["2026-10-12T10:01", "claude.ai", "/pricing/", 9, 1]]},
            "cube": {"rows": [["CA", "/pricing/", "AI assistant", "chatgpt.com", "desktop", 2],
                              ["CA", "/pricing/", "Search engine", "", "desktop", 7]]},
            "ai_likely": {"pages": {"/pricing/": 1}}}}
        got = data.build(self.page(extras, [("example.com", "completed", "2026-10-12T11:00:00Z",
                                             "/pricing/", "AI assistant", 0),
                                            ("example.com", "completed", "2026-10-12T11:00:00Z",
                                             "/pricing/", "AI assistant", 1)]))
        self.assertEqual(got["state"], "ok")
        chain = next(c for c in got["chain"] if c["provider"] == "openai")
        self.assertEqual((chain["page"], chain["cited"], chain["of"]), ("/pricing/", 4, 4))
        self.assertEqual((chain["read"], chain["requests"], chain["sent"], chain["likely"], chain["leads"]),
                         (2, 3, 2, 1, 1))
        self.assertIsNone(got["reads_from"])
        # A day stored before reads were counted (rows of four): reads unknown, never 0.
        older = {**extras, "2026-10-11": {"ai_fetches": {"rows": [
            ["2026-10-11T09:00", "chatgpt.com", "/pricing/", 4]]}}}
        old = data.build(self.page(older))
        chain = next(c for c in old["chain"] if c["provider"] == "openai")
        self.assertEqual((chain["read"], chain["requests"]), (None, 7))
        self.assertEqual(old["reads_from"], "2026-10-12")
        prof = got["profiles"][0]
        self.assertEqual(prof["estimate"]["answers"], 16)
        last = got["last"][str(self.pid)]
        self.assertEqual(last["questions"][0]["by"]["openai"]["mentioned"], 2)
        self.assertEqual(last["questions"][0]["by"]["openai"]["line"]["mark"], "Example Analytics")
        self.assertEqual(got["trend"][0]["providers"]["openai"]["avg_rank"], 1.0)
        names = [c["name"] for c in got["competitors"][str(self.pid)]]
        self.assertIn("Northwind Analytics", names)
        self.assertNotIn(KEY, json.dumps(got))
        # A run whose recount disagrees is withheld: no figures, no answers shown.
        with store.opened(self.folder) as db:
            db.execute("UPDATE figures SET verified = 0, problems = 'x'")
            db.commit()
        got = data.build(self.page(extras))
        self.assertTrue(got["trend"][0]["withheld"])
        self.assertEqual(got["trend"][0]["providers"], {})
        self.assertEqual(got["last"], {})
        self.assertEqual(got["chain"], [])


class ChainRecount(unittest.TestCase):
    """The chain's reads and requests summed again from the history file."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "history.sqlite"
        db = sqlite3.connect(self.path)
        db.execute("CREATE TABLE day_extras (site TEXT, day TEXT, kind TEXT, data TEXT, "
                   "PRIMARY KEY (site, day, kind))")
        for day, rows in (("2026-10-12", [["2026-10-12T10:00", "chatgpt.com", "/pricing?x=1", 3, 2],
                                          ["2026-10-12T10:05", "chatgpt.com", "/pricing/", 1, 1],
                                          ["2026-10-12T10:01", "claude.ai", "/pricing/", 9, 1]]),
                          ("2026-10-11", [["2026-10-11T09:00", "chatgpt.com", "/pricing", 4]])):
            db.execute("INSERT INTO day_extras VALUES (?, ?, 'ai_fetches', ?)",
                       ("example.com", day, json.dumps({"rows": rows})))
        db.execute("INSERT INTO day_extras VALUES ('other.example.com', '2026-10-12', 'ai_fetches', ?)",
                   (json.dumps({"rows": [["2026-10-12T10:00", "chatgpt.com", "/pricing", 50, 50]]}),))
        db.commit()
        db.close()

    def chain(self, read, requests, page="/pricing/"):
        return [{"provider": "openai", "page": page, "read": read, "requests": requests}]

    def test_reads_and_requests_agree_on_the_new_days(self):
        days = ["2026-10-12"]
        self.assertEqual(audit_ai_answers.recount_chain(self.path, "example.com", days,
                                                        self.chain(3, 4)), [])
        found = audit_ai_answers.recount_chain(self.path, "example.com", days, self.chain(4, 4))
        self.assertEqual(found, ["chain openai /pricing/: read 4 against 3"])
        # A page no assistant fetched: 0 of each; a page not known: none.
        self.assertEqual(audit_ai_answers.recount_chain(self.path, "example.com", days,
                                                        self.chain(0, 0, "/about/")), [])
        self.assertEqual(audit_ai_answers.recount_chain(self.path, "example.com", days,
                                                        self.chain(None, None, "(page not known)")), [])

    def test_an_old_day_makes_the_reads_unknown_never_zero(self):
        days = ["2026-10-11", "2026-10-12"]
        self.assertEqual(audit_ai_answers.recount_chain(self.path, "example.com", days,
                                                        self.chain(None, 8)), [])
        self.assertTrue(audit_ai_answers.recount_chain(self.path, "example.com", days,
                                                       self.chain(3, 8)))

    def test_a_disagreeing_chain_is_withheld_on_the_page(self):
        extras = {"2026-10-12": {"ai_fetches": {"rows": [
            ["2026-10-12T10:00", "chatgpt.com", "/pricing", 9, 9]]}}}
        p = SimpleNamespace(history=SimpleNamespace(path=self.path, extras=lambda *a: extras),
                            counted_days=lambda: list(extras), config={})
        db = sqlite3.connect(":memory:")
        db.executescript("CREATE TABLE answers (provider, own_pages, run_id, site, ok, day);"
                         "CREATE TABLE figures (run_id, provider, verified);"
                         "INSERT INTO answers VALUES ('openai', '[\"/pricing/\"]', 1, 'example.com', 1, '2026-10-12');"
                         "INSERT INTO figures VALUES (1, 'openai', 1);")
        with mock.patch.object(data, "_leads", lambda *a: None):
            out, reads_from = data._chain(p, db, "example.com", date(2026, 10, 1), date(2026, 10, 12))
        self.assertEqual((out[0]["read"], out[0]["requests"], reads_from), (None, None, None))


if __name__ == "__main__":
    unittest.main()
