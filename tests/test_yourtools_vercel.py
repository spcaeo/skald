"""Vercel Web Analytics (skald/yourtools/tool_vercel.py), with recorded-shape
answers (tests/fixtures/yourtools/vercel.json) through a fake opener: no network.

  * the key: a token, shown again only by its last four characters; a wrong shape
    refused in plain words, never echoing it
  * the calls: GET only, Bearer, the project and team, 28 whole UTC days, the
    documented count and aggregate endpoints, the top 10
  * the figures: Vercel's own visitors from visits/count (never added up from rows),
    each row's visitors and page views, "Others" kept as Vercel's own row, a direct
    visit's empty referrer as "(none)", a missing value NULL, never 0
  * the sync and the recheck: every figure matches; a changed figure or a stored
    answer changed is a mismatch and withholds the tool; only the newest window kept
  * refusals in plain words, never the token; an answer not in the documented shape
  * the drawer's notes: the log drain is Skald's count; tokens cannot be read-only
"""
from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import yourtools  # noqa: E402
from skald.yourtools import api, recount, store, sync  # noqa: E402
from skald.yourtools.base import BadKey, Unreachable  # noqa: E402
from skald.yourtools.tool_vercel import ADAPTER as VERCEL  # noqa: E402

SITE = "example.com"
TOKEN = "AbCdEfGhIjKlMnOpQrStUv12"
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "yourtools" /
                      "vercel.json").read_text())


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeVercel:
    def __init__(self, fail=None, answers=None):
        self.fail, self.asked = fail, []
        self.answers = answers or FIXTURE

    def __call__(self, request, timeout=None):
        assert request.get_method() == "GET" and request.data is None
        assert request.get_header("Authorization") == f"Bearer {TOKEN}"
        url = urllib.parse.urlsplit(request.full_url)
        assert url.netloc == "api.vercel.com", url
        q = dict(urllib.parse.parse_qsl(url.query))
        self.asked.append((url.path, q))
        if self.fail:
            raise urllib.error.HTTPError(request.full_url, self.fail, "no", {}, io.BytesIO(
                json.dumps({"error": {"code": "forbidden", "message": "Not authorized"}})
                .encode()))
        key = "count" if url.path.endswith("/count") else q["by"]
        return Reply(json.dumps(self.answers[key]).encode())


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}, "history": {"db": str(self.folder / "h.sqlite")}}

    def connect(self, **options):
        return sync.connect(self.config, self.folder, SITE, "vercel",
                            {"project": "prj_Demo123", "team": "team_Demo456", **options},
                            "cli", key=TOKEN)

    def run_sync(self, opener, now=NOW):
        out = []
        job = sync.Job(self.config, SITE, self.folder, now, out.append, out.append,
                       opener=opener, sleep=lambda s: None, send=lambda *a: None)
        return sync.run(job), out

    def figures(self):
        db = store.reader(self.folder)
        try:
            return {r["report"]: r for r in store.latest(db, SITE, "vercel")}
        finally:
            db.close()


class Key(unittest.TestCase):
    def test_found_by_its_file_name(self):
        self.assertIs(yourtools.get("vercel"), VERCEL)
        self.assertEqual(VERCEL.name, "Vercel Web Analytics")

    def test_who_is_the_last_four_only(self):
        self.assertEqual(VERCEL.check_key(TOKEN)["who"], "a Vercel token ending ...Uv12")

    def test_wrong_shape_refused_without_echo(self):
        for bad in ("short", "has space in it 1234567890", "x" * 500):
            with self.assertRaises(BadKey) as got:
                VERCEL.check_key(bad)
            self.assertNotIn(bad, str(got.exception))

    def test_the_key_cannot_be_read_only_and_says_so(self):
        self.assertIn("cannot be made read-only", VERCEL.permission)
        self.assertTrue(any("log drain" in n for n in VERCEL.notes))
        self.assertTrue(any("never" in n and "added" in n for n in VERCEL.notes))

    def test_options(self):
        clean = VERCEL.clean_options({"project": "prj_Abc", "team": "team_Xyz"})
        self.assertEqual(clean, {"project": "prj_Abc", "team": "team_Xyz"})
        self.assertEqual(VERCEL.clean_options({"project": "my-site"}), {"project": "my-site"})
        with self.assertRaises(ValueError):
            VERCEL.clean_options({"project": "prj_Abc", "team": "acme"})
        with self.assertRaises(ValueError):
            VERCEL.clean_options({})


class Calls(unittest.TestCase):
    def test_four_documented_get_calls_over_28_utc_days(self):
        fake = FakeVercel()
        got = VERCEL.fetch(TOKEN, {"project": "prj_Demo123", "team": "team_Demo456"}, NOW,
                           opener=fake, sleep=lambda s: None)
        self.assertEqual([a.report for a in got], ["totals", "pages", "referrers", "countries"])
        paths = [p for p, _ in fake.asked]
        self.assertEqual(paths[0], "/v1/query/web-analytics/visits/count")
        self.assertEqual(set(paths[1:]), {"/v1/query/web-analytics/visits/aggregate"})
        for _, q in fake.asked:
            self.assertEqual((q["projectId"], q["teamId"], q["since"], q["until"]),
                             ("prj_Demo123", "team_Demo456", "2026-09-29", "2026-10-26"))
        self.assertEqual([q.get("by") for _, q in fake.asked],
                         [None, "requestPath", "referrerHostname", "country"])
        self.assertEqual({q.get("limit") for _, q in fake.asked[1:]}, {"10"})
        self.assertEqual((got[0].start, got[0].end), ("2026-09-29", "2026-10-26"))
        self.assertIn("UTC", got[0].note)
        self.assertNotIn(TOKEN, json.dumps([a.request for a in got]))

    def test_personal_project_sends_no_team(self):
        fake = FakeVercel()
        VERCEL.fetch(TOKEN, {"project": "my-site"}, NOW, opener=fake, sleep=lambda s: None)
        self.assertTrue(all("teamId" not in q for _, q in fake.asked))

    def test_figures(self):
        got = VERCEL.fetch(TOKEN, {"project": "prj_Demo123"}, NOW, opener=FakeVercel(),
                           sleep=lambda s: None)
        totals = {f.name: f.value for f in VERCEL.figures(got[0])}
        self.assertEqual(totals, {"visitors": 1870, "pageviews": 5230})
        pages = VERCEL.figures(got[1])
        self.assertEqual([(f.dim, f.value) for f in pages if f.name == "visitors"],
                         [("/", 900), ("/pricing", 410), ("/blog/server-logs", 300),
                          ("Others", 760)])
        self.assertTrue(got[1].flags["others"])
        refs = [f for f in VERCEL.figures(got[2]) if f.name == "visitors"]
        self.assertEqual(refs[0].dim, "(none)")
        self.assertIsNone(refs[0].dim_src)
        # Visitors are never added up: the total is visits/count's, not the rows' sum.
        self.assertNotEqual(totals["visitors"], sum(f.value for f in pages if f.name == "visitors"))
        head = VERCEL.headline(VERCEL.figures(got[0]))
        self.assertEqual([f.name for f in head], ["visitors", "pageviews"])

    def test_a_missing_value_is_null(self):
        answers = json.loads(json.dumps(FIXTURE))
        del answers["count"]["data"]["visitors"]
        answers["country"]["data"][1]["pageviews"] = None
        got = VERCEL.fetch(TOKEN, {"project": "p"}, NOW, opener=FakeVercel(answers=answers),
                           sleep=lambda s: None)
        totals = {f.name: f for f in VERCEL.figures(got[0])}
        self.assertIsNone(totals["visitors"].value)
        self.assertIsNone(totals["visitors"].src)
        de = [f for f in VERCEL.figures(got[3]) if f.dim == "DE" and f.name == "pageviews"][0]
        self.assertIsNone(de.value)

    def test_an_answer_not_in_the_documented_shape(self):
        answers = json.loads(json.dumps(FIXTURE))
        answers["requestPath"] = {"version": 1, "error": "changed"}
        with self.assertRaises(Unreachable) as got:
            VERCEL.fetch(TOKEN, {"project": "p"}, NOW, opener=FakeVercel(answers=answers),
                         sleep=lambda s: None)
        self.assertIn("documentation", str(got.exception))

    def test_refusals_in_plain_words(self):
        for code, words in ((403, "refused the token"), (404, "no such project"),
                            (402, "paid plan"), (429, "rate limit")):
            with self.assertRaises(Unreachable) as got:
                VERCEL.fetch(TOKEN, {"project": "p"}, NOW, opener=FakeVercel(fail=code),
                             sleep=lambda s: None)
            self.assertIn(words, str(got.exception))
            self.assertNotIn(TOKEN, str(got.exception))
            self.assertEqual(got.exception.code, code)


class SyncAndAudit(Base):
    def test_sync_keeps_figures_and_the_recheck_matches(self):
        self.connect()
        code, out = self.run_sync(FakeVercel())
        self.assertEqual(code, 0, out)
        got = self.figures()
        self.assertEqual(set(got), {"totals", "pages", "referrers", "countries"})
        check = recount.check(self.folder, SITE, "vercel")["vercel"]
        self.assertTrue(check["ok"], check["problems"])
        view = api.view(self.config, self.folder, SITE, admin=False, now=NOW)["tools"][0]
        self.assertEqual(view["counted_from"], "Counted from: Vercel Web Analytics")
        self.assertEqual([(h["name"], h["value"]) for h in view["headline"]],
                         [("visitors", 1870), ("pageviews", 5230)])
        self.assertIn("The rest are folded into Others, as the tool does",
                      view["reports"]["pages"]["flags"])

    def test_a_changed_figure_is_found_and_withheld(self):
        self.connect()
        self.run_sync(FakeVercel())
        db = sqlite3.connect(self.folder / store.FILE)
        db.execute("UPDATE figures SET value = 999 WHERE name = 'visitors' AND dim = '/pricing'")
        db.commit()
        db.close()
        check = recount.check(self.folder, SITE, "vercel")["vercel"]
        self.assertFalse(check["ok"])
        self.assertTrue(any("/pricing" in p and "999" in p for p in check["problems"]))

    def test_a_planted_extra_row_and_a_changed_answer(self):
        self.connect()
        self.run_sync(FakeVercel())
        db = sqlite3.connect(self.folder / store.FILE)
        aid = db.execute("SELECT id FROM answers WHERE report = 'countries'").fetchone()[0]
        db.execute("INSERT INTO figures (answer_id, name, label, dim, value, rank) VALUES "
                   "(?, 'visitors', 'Visitors', 'FR', 12, 7)", (aid,))
        db.execute("UPDATE answers SET body = replace(body, '1100', '1101') "
                   "WHERE report = 'countries'")
        db.commit()
        db.close()
        problems = recount.check(self.folder, SITE, "vercel")["vercel"]["problems"]
        self.assertTrue(any("FR" in p and "not in Vercel's answer" in p for p in problems))
        self.assertTrue(any("changed since it came" in p for p in problems))

    def test_only_the_newest_window_is_kept(self):
        self.connect()
        self.run_sync(FakeVercel())
        self.run_sync(FakeVercel(), now=NOW + timedelta(days=1))
        db = sqlite3.connect(self.folder / store.FILE)
        periods = {r[0] for r in db.execute("SELECT period FROM answers WHERE tool = 'vercel'")}
        orphans = db.execute("SELECT COUNT(*) FROM figures WHERE answer_id NOT IN "
                             "(SELECT id FROM answers)").fetchone()[0]
        db.close()
        self.assertEqual(periods, {"2026-09-30..2026-10-27"})
        self.assertEqual(orphans, 0)

    def test_a_refusal_keeps_the_last_figures(self):
        self.connect()
        self.run_sync(FakeVercel())
        code, out = self.run_sync(FakeVercel(fail=401))
        self.assertEqual(code, 1)
        self.assertNotIn(TOKEN, "\n".join(out))
        view = api.view(self.config, self.folder, SITE, admin=True, now=NOW)["tools"]
        mine = [t for t in view if t["id"] == "vercel"][0]
        self.assertEqual(mine["state"], "failing")
        self.assertEqual(mine["headline"][0]["value"], 1870)


if __name__ == "__main__":
    unittest.main()
