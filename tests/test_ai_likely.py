"""Likely sent by an AI assistant (ai_likely.py, ai_fetches.py) and its
second counts (audit_ai_likely.py, audit_leads.py, audit_conversions_figures).

What is pinned:
- the day kind on a synthetic day: a ChatGPT-User fetch of /pricing/ at
  10:00 and a direct visit landing on /pricing/ at 10:03 is one likely
  ChatGPT visit; a direct visit at 10:40 is not; a tagged visit is not; a
  visit from a referrer is not; two assistants in the window count once,
  under "(more than one)"; the window and the switch are honoured;
- every sum the blob promises is checked, and a planted error is caught;
- the audit rebuilds the figure and the fetch records from the raw lines and
  a tampered stored figure fails it (the live audit too);
- ai_activity.json carries the day's blob and the method;
- leads.json's attribution rows carry likely_ai for a direct first touch,
  "(none)" outside the window or for a tagged touch, "(not recorded)" when
  the fetches of the touch's window were not kept; audit_leads agrees, and
  a wrong label is caught;
- conversions.json's likely_ai per day, from a lead's first touch and from a
  beacon browser's first journey row; the SQL recount agrees;
- the recount shares only classify.py's name lists.
"""
from __future__ import annotations

import ast
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, Sandbox, line, totals_for  # noqa: E402
from test_leads import SCHEMA, touch  # noqa: E402

from skald import (ai_likely, audit_ai_likely, audit_leads, classify,  # noqa: E402
                          conversions_data, extras, leads)
from skald.conversions import from_leads, store  # noqa: E402
from skald.conversions.normalise import row as make_row  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
PERPLEXITY = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
              "Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)")
CLAUDE = "Claude-User/1.0 (+Claude-User@anthropic.com)"


def at(hour: int, minute: int, day: date = DAY) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def synthetic(day: date = DAY) -> list[str]:
    return [
        line(at(10, 0, day), "198.51.100.40", "/pricing/", ASKED),
        line(at(10, 3, day), "203.0.113.10", "/pricing/"),                      # likely
        line(at(10, 5, day), "203.0.113.11",
             "/pricing/?utm_source=newsletter&utm_medium=email"),               # tagged
        line(at(10, 6, day), "203.0.113.14", "/pricing/",
             referrer="https://www.google.com/"),                               # search
        line(at(10, 40, day), "203.0.113.12", "/pricing/"),                     # too late
        line(at(11, 10, day), "198.51.100.41", "/docs", PERPLEXITY),
        line(at(11, 12, day), "198.51.100.42", "/docs/", CLAUDE),
        line(at(11, 14, day), "203.0.113.13", "/docs"),                         # both
    ]


WANT = {"window_minutes": 15, "chance_limit": 0.25, "by_chance": {},
        "visits": 5, "direct": 3, "likely": 2,
        "by_assistant": {"(more than one)": 1, "chatgpt.com": 1},
        "pages": {"/docs": 1, "/pricing/": 1},
        "fetches": {"chatgpt.com": 1, "claude.ai": 1, "perplexity.ai": 1},
        "followed": {"chatgpt.com": 1, "claude.ai": 1, "perplexity.ai": 1},
        "reads": {"chatgpt.com": 1, "claude.ai": 1, "perplexity.ai": 1},
        "reads_followed": {"chatgpt.com": 1, "claude.ai": 1, "perplexity.ai": 1}}


def tally(lines, attribution=None):
    if attribution is None:
        return totals_for(lines)
    from skald import Classifier, read
    from skald.aggregate import summarise_views
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        return summarise_views(read([path]), Classifier(["MyCompanyCrawler"]), 30, top=50,
                               hosts=["example.com"],
                               options={"attribution": attribution})[0]


class TestTheDay(unittest.TestCase):

    def test_the_synthetic_day(self):
        totals = totals_for(synthetic())
        self.assertEqual(totals.extras["ai_likely"], WANT)
        self.assertEqual(extras.check(totals), [])
        marked = {j["start"][11:16]: j.get("likely_ai") for j in totals.journeys}
        self.assertEqual(marked["10:03"], {"name": "chatgpt.com", "names": ["chatgpt.com"],
                                           "minutes": 3})
        self.assertIsNone(marked["10:40"])          # 40 minutes after the fetch
        self.assertIsNone(marked["10:05"])          # tagged
        self.assertIsNone(marked["10:06"])          # came from a search engine
        self.assertEqual(marked["11:14"]["name"], classify.AI_LIKELY_MANY)
        self.assertEqual(marked["11:14"]["names"], ["claude.ai", "perplexity.ai"])
        self.assertEqual(totals.extras["ai_fetches"], {"rows": [
            ["2026-10-05T10:00", "chatgpt.com", "/pricing/", 1, 1],
            ["2026-10-05T11:10", "perplexity.ai", "/docs", 1, 1],
            ["2026-10-05T11:12", "claude.ai", "/docs/", 1, 1]]})

    def test_only_the_three_lines_of_the_brief(self):
        lines = [line(at(10, 0), "198.51.100.40", "/pricing/", ASKED),
                 line(at(10, 3), "203.0.113.10", "/pricing/"),
                 line(at(10, 40), "203.0.113.12", "/pricing/"),
                 line(at(10, 4), "203.0.113.11", "/pricing/?utm_source=x&utm_medium=cpc")]
        got = totals_for(lines).extras["ai_likely"]
        self.assertEqual((got["likely"], got["by_assistant"], got["direct"]),
                         (1, {"chatgpt.com": 1}, 2))

    def test_the_window_is_configurable_and_the_figure_can_be_off(self):
        got = tally(synthetic(), {"on": True, "window": 2}).extras["ai_likely"]
        # 10:03 is 3 minutes after ChatGPT's fetch; 11:14 is 2 after Claude's, 4 after Perplexity's.
        self.assertEqual(got["by_assistant"], {"claude.ai": 1})
        self.assertEqual(got["window_minutes"], 2)
        off = tally(synthetic(), {"on": False, "window": 15}).extras
        self.assertNotIn("ai_likely", off)
        self.assertNotIn("ai_fetches", off)

    def test_settings(self):
        self.assertEqual(ai_likely.settings({}), {"on": True, "window": 15})
        self.assertEqual(ai_likely.settings({"attribution": {"ai_likely": False,
                                                             "ai_window_minutes": "30"}}),
                         {"on": False, "window": 30})

    def test_a_visit_before_the_fetch_is_not_counted(self):
        lines = [line(at(10, 5), "198.51.100.40", "/pricing/", ASKED),
                 line(at(10, 3), "203.0.113.10", "/pricing/")]
        got = totals_for(lines).extras["ai_likely"]
        self.assertEqual((got["likely"], got["followed"]), (0, {"chatgpt.com": 0}))

    def test_planted_errors_are_caught(self):
        for change, what in (
                (lambda b: b["by_assistant"].update({"claude.ai": 1}),
                 "ai_likely: likely visits by assistant does not sum"),
                (lambda b: b["pages"].update({"/x": 1}),
                 "ai_likely: likely visits by landing page does not sum"),
                (lambda b: b["fetches"].update({"claude.ai": 2}),
                 "ai_likely: user fetches by assistant does not sum"),
                (lambda b: b.update({"visits": 7}), "ai_likely: visits does not sum")):
            totals = totals_for(synthetic())
            change(totals.extras["ai_likely"])
            self.assertIn(what, [p.what for p in extras.check(totals)])
        totals = totals_for(synthetic())
        totals.extras["ai_likely"]["followed"]["claude.ai"] = 2
        self.assertIn("ai_likely: claude.ai", [p.what for p in extras.check(totals)])
        totals = totals_for(synthetic())
        totals.extras["ai_fetches"]["rows"].pop()
        self.assertIn("ai_fetches: user fetches by minute does not sum",
                      [p.what for p in extras.check(totals)])

    def test_every_user_fetcher_has_an_owner(self):
        names = classify.AI_ASKED.pattern.split("|")
        self.assertEqual({n.lower() for n in names}, set(classify.AI_FETCHER_OWNERS))


class TestTheAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic())

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]

    def tamper(self, kind, blob):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = ?", (json.dumps(blob), kind))
        db.close()

    def test_the_recount_matches_and_planted_errors_are_caught(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        got = self.stored()
        self.assertEqual(got["ai_likely"], WANT)
        wrong = dict(got["ai_likely"], by_assistant={"chatgpt.com": 2})
        self.tamper("ai_likely", wrong)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_likely: likely from chatgpt.com: history has 2, the recount finds 1",
                      err)
        self.assertIn("ai_likely: likely from (more than one): history has 0, the recount "
                      "finds 1", err)

    def test_a_tampered_fetch_record_fails_the_audit(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        rows = self.stored()["ai_fetches"]["rows"]
        rows[0][0] = "2026-10-05T09:59"
        self.tamper("ai_fetches", {"rows": rows})
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_fetches: chatgpt.com on /pricing/ at 2026-10-05T09:59: history has 1, "
                      "the recount finds 0", err)

    def test_the_stored_window_is_the_one_recounted(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        text = self.box.config.read_text() + "attribution:\n  ai_window_minutes: 1\n"
        self.box.config.write_text(text)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)

    def test_the_live_audit_compares_it_too(self):
        stamp = at(23, 0).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self.assertEqual(self.box.run("--today", DAY.isoformat(), "live")[0], 0)
        code, _, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["extras"]["ai_likely"]["likely"], 2)

    def test_ai_activity_json_carries_the_day_and_the_method(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "dashboard")
        self.assertEqual(code, 0, err)
        got = json.loads((self.box.root / "www" / "example.com" / "data" / "ai_activity.json")
                         .read_text())
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day["ai_likely"], WANT)
        self.assertEqual(got["likely_ai"]["window_minutes"], 15)
        self.assertIn("Likely, never certain", got["likely_ai"]["method"])
        visits = json.loads((self.box.root / "www" / "example.com" / "data" / "visits.json")
                            .read_text())
        marked = [j["likely_ai"]["name"] for j in visits["journeys"] if j.get("likely_ai")]
        self.assertEqual(sorted(marked), ["(more than one)", "chatgpt.com"])


# ------------------------------------------------------- leads, conversions

def lead_db(path: Path, rows) -> Path:
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    for i, (made, first, last) in enumerate(rows, 1):
        db.execute("INSERT INTO submissions (id, type, email, fields, locale, updated_at, "
                   "created_at, status, page, first_touch, last_touch) VALUES "
                   "(?, 'signup', ?, '{}', 'en-us', ?, ?, 'new', '/signup/', ?, ?)",
                   (i, f"person{i}@example.com", made, made, first, last))
    db.commit()
    db.close()
    return path


def direct(when: str, page: str = "/pricing", **kw) -> str:
    return touch(at=when, landingPath=page, **kw)


LEADS = [
    # made, first touch, last touch
    ("2026-10-05T12:00:00.000Z", direct("2026-10-05T10:03:20.000Z"),             # ChatGPT
     direct("2026-10-05T10:40:00.000Z")),                                        # too late
    ("2026-10-05T12:30:00.000Z", direct("2026-10-05T10:04:00.000Z", utmCampaign="spring"),
     direct("2026-10-05T11:20:00.000Z", page="/docs/")),                         # tagged; both
    ("2026-10-06T09:00:00.000Z", direct("2026-10-06T08:00:00.000Z"),             # not kept
     touch(at="2026-10-05T10:03:00.000Z", referrerHost="www.google.com",
           landingPath="/pricing/")),                                            # search
]


class TestLeadsAndConversions(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic())
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        self.leads = lead_db(self.box.root / "payload.db", LEADS)
        self.config = {"site": {"name": "example.com"}, "leads": {"db": str(self.leads)}}
        self.today = date(2026, 10, 6)

    def tearDown(self):
        self.box.close()

    def built(self, config=None):
        with History.reader(self.box.db) as history:
            return leads.blob(config or self.config, UTC, self.today, [], self.today,
                              audited=False, history=history)

    def recount(self, config=None):
        return audit_leads.audit_leads(self.leads, UTC, self.today - timedelta(days=179),
                                       self.today, config=config or self.config,
                                       history=self.box.db)

    def likely(self, got) -> dict:
        cols = got["attribution_columns"]
        return {(r[0], r[cols.index("touch")], r[cols.index("landing")]): r[cols.index(
            "likely_ai")] for r in got["attribution_rows"] if r[cols.index("type")] == "signup"}

    def test_lead_touches(self):
        got = self.built()
        self.assertEqual(got["attribution_columns"][-2:], ["likely_ai", "n"])
        rows = {(r[0], r[3], r[11], r[9]) for r in got["attribution_rows"]}
        self.assertEqual(rows, {
            ("2026-10-05", "first", "chatgpt.com", "/pricing"),
            ("2026-10-05", "last", "(none)", "/pricing"),           # 40 minutes later
            ("2026-10-05", "first", "(none)", "/pricing"),          # utm_campaign
            ("2026-10-05", "last", "(more than one)", "/docs/"),    # 11:20, 10 and 8 min
            ("2026-10-06", "first", "(not recorded)", "/pricing"),  # the 6th is not kept
            ("2026-10-06", "last", "(none)", "/pricing/"),          # from a search engine
        })
        self.assertEqual(got["likely_ai"]["window_minutes"], 15)
        self.assertEqual(audit_leads.compare(got, self.recount()), [])

    def test_a_wrong_label_is_caught(self):
        got = self.built()
        for r in got["attribution_rows"]:
            if r[11] == "chatgpt.com":
                r[11] = "claude.ai"
        self.assertTrue(any("attribution_rows" in p
                            for p in audit_leads.compare(got, self.recount())))

    def test_off_or_without_history_is_not_recorded(self):
        off = dict(self.config, attribution={"ai_likely": False})
        got = self.built(off)
        labels = {r[11] for r in got["attribution_rows"]}
        self.assertEqual(labels, {"(none)", "(not recorded)"})
        self.assertEqual(audit_leads.compare(got, self.recount(off)), [])
        bare = leads.blob(self.config, UTC, self.today, [], self.today, audited=False)
        self.assertNotIn("chatgpt.com", {r[11] for r in bare["attribution_rows"]})

    def test_conversions(self):
        folder = self.box.root / "conv"
        config = dict(self.config, conversions={"db": str(folder / "conversions.sqlite")})
        db = store.connect(folder / "conversions.sqlite")
        try:
            from_leads.sync(db, self.leads, "example.com")
            vid = "browser-0001"
            store.record_page_view(db, "example.com", vid, "2026-10-05T11:14:30Z", "/docs",
                                   "Direct or unknown")
            row = make_row({"action": "demo", "stage": "completed", "at": "2026-10-05T11:30:00Z",
                            "vid": vid, "external_ref": "b1", "source_type": "Direct or unknown",
                            "landing": "/docs"}, "example.com", "beacon",
                           "2026-10-05T11:30:00Z", set(), False)
            store.record_conversion(db, row)
        finally:
            db.close()
        now = datetime(2026, 10, 6, 12, tzinfo=UTC)
        # The beacon row was written here, not spooled: the stage recount
        # (audit_conversions.findings) is not what this test is about.
        spool = mock.patch("skald.audit_conversions.findings", return_value={})
        with spool, History.reader(self.box.db) as history:
            got = conversions_data.blob(config, folder, "example.com", UTC, self.today, now,
                                        history=history)
        self.assertEqual(got["withheld"], {})
        day = next(d for d in got["days"] if d["day"] == "2026-10-05")
        # A conversion row keeps its first touch's source, not its utm_campaign:
        # the second lead's campaign-only tag still reads as Direct here.
        self.assertEqual(day["likely_ai"], {"signup": {"chatgpt.com": 2},
                                            "demo": {"(more than one)": 1}})
        later = next(d for d in got["days"] if d["day"] == "2026-10-06")
        self.assertEqual(later["likely_ai"], {"signup": {"Unknown": 1}})
        # A miscount is withheld by the SQL recount.
        with mock.patch("skald.conversions_data.likely_label", return_value="(none)"):
            with spool, History.reader(self.box.db) as history:
                got = conversions_data.blob(config, folder, "example.com", UTC, self.today, now,
                                            history=history)
        self.assertIn("days/2026-10-05", got["withheld"])


class TestTheApp(unittest.TestCase):

    def test_the_apps_journey_keeps_likely_ai(self):
        # The visitor drawer's "Likely AI" line reads it from app.json.
        from skald import dashboard_webapp
        mark = {"name": "chatgpt.com", "names": ["chatgpt.com"], "minutes": 3}
        got = dashboard_webapp.journey({"start": "2026-10-05T10:00", "trail": [["/pricing/", "page"]],
                                        "likely_ai": mark})
        self.assertEqual(got["likely_ai"], mark)
        self.assertNotIn("likely_ai", dashboard_webapp.journey({"start": "2026-10-05T10:00", "trail": []}))


class TestIndependence(unittest.TestCase):

    def test_the_recount_shares_only_classify_lists(self):
        # The name lists (classify, ai_read_names) and the audit's own reading
        # of reads (audit_ai_reads, on the audit's road): nothing of the main road.
        tree = ast.parse(Path(audit_ai_likely.__file__).read_text())
        got = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level}
        self.assertEqual(got, {"classify", "ai_read_names", "audit_ai_reads"})


if __name__ == "__main__":
    unittest.main()
