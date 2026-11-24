"""Google Analytics 4 (skald/yourtools/tool_ga4.py), with recorded-shape
answers (tests/fixtures/yourtools/ga4-runreport.json) through a fake opener: no
network, no real property.

  * the key: a service account (its robot address shown again, never the key),
    an OAuth "authorized_user" file, anything else refused in plain words
  * the calls: a token for analytics.readonly (the JWT's scope checked), one
    runReport body per report (GA4's own last 28 days, the 28 before for
    "previous", the top 10, GA4's TOTAL, ordered by each metric in turn)
  * the figures: GA4's strings as numbers, users never added up (GA4's TOTAL),
    a metric GA4 did not give is NULL, an empty answer is NULL, never 0; the
    window in the property's own time zone; thresholding and sampling kept
  * the sync and the recheck: every figure matches; a changed figure, a row
    left out or a 0 for nothing is a mismatch and withholds Google Analytics
  * refusals in plain words: no access (Viewer), no such property, a deleted key,
    a revoked refresh token; no token or secret in any of them
  * the install's Search Console key used for GA4 (key=search)
  * SKALD-55: the totals' new figures (shares, seconds), the 28 days before, four
    more tables; an answer kept before Skald asked for more still rechecks by
    what it asked then; the figures' units, rows and report names for the screen
  * what the site check found on the page: the G- measurement ID, a suggestion

Test data: example.com names; the keys are test keys made here.
"""
from __future__ import annotations

import base64
import io
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from search_support import service_key  # noqa: E402

from skald import yourtools  # noqa: E402
from skald.conversions import secrets_store  # noqa: E402
from skald.search import google  # noqa: E402
from skald.yourtools import api, conn, recount, store, sync  # noqa: E402
from skald.yourtools.base import BadKey, Unreachable  # noqa: E402
from skald.yourtools.tool_ga4 import ADAPTER as GA4, SCOPE  # noqa: E402

SITE = "example.com"
PROP = "123456789"
NOW = datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)      # 26 Oct, 23:00 in New York
FIXTURE = json.loads((Path(__file__).resolve().parent / "fixtures" / "yourtools" /
                      "ga4-runreport.json").read_text())
# Each report with a dimension, by its dimension (names.GA4_REPORTS).
DIMS = {"landing": "landingPage", "sources": "sessionSourceMedium",
        "channels": "sessionDefaultChannelGroup", "devices": "deviceCategory",
        "countries": "country", "events": "eventName"}
REPORTS = ["totals", "previous", *DIMS]
SIGN_IN = json.dumps({"type": "authorized_user", "client_id": "123-abc.apps.example.com",
                      "client_secret": "test-client-secret-xyz", "refresh_token": "1//test-refresh"})


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Google:
    """A fake opener: Google's token address and runReport, from the fixture."""

    def __init__(self, answers=None, fail=None, token_fail=None):
        self.answers = answers or {**{"": FIXTURE["totals"], "": FIXTURE["totals"]},
                                   **{dim: FIXTURE[r] for r, dim in DIMS.items()}}
        self.fail, self.token_fail = fail, token_fail
        self.asked, self.tokens = [], []

    def __call__(self, request, timeout=None):
        url = request.full_url
        body = request.data.decode() if request.data else ""
        if url == google.TOKEN_URL:
            self.tokens.append(dict(urllib.parse.parse_qsl(body)))
            if self.token_fail:
                raise urllib.error.HTTPError(url, self.token_fail, "no", {},
                                             io.BytesIO(b'{"error": "invalid_grant"}'))
            return Answer(b'{"access_token": "test-access-token", "expires_in": 3600}')
        assert url == f"https://analyticsdata.googleapis.com/v1beta/properties/{PROP}:runReport", url
        assert request.get_header("Authorization") == "Bearer test-access-token"
        ask = json.loads(body)
        self.asked.append(ask)
        if self.fail:
            raise urllib.error.HTTPError(url, self.fail, "no", {}, io.BytesIO(json.dumps(
                {"error": {"code": self.fail, "message": "User does not have sufficient "
                           "permissions for this property."}}).encode()))
        dim = (ask.get("dimensions") or [{}])[0].get("name", "")
        if not dim and ask["dateRanges"][0]["startDate"] == "56daysAgo":
            return Answer(json.dumps(self.answers.get("previous", FIXTURE["previous"])).encode())
        return Answer(json.dumps(self.answers[dim]).encode())


def claims(token_request: dict) -> dict:
    part = token_request["assertion"].split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.config = {"site": {"name": SITE}, "history": {"db": str(self.folder / "h.sqlite")}}

    def run_sync(self, opener):
        out = []
        job = sync.Job(self.config, SITE, self.folder, NOW, out.append, out.append,
                       opener=opener, sleep=lambda s: None, send=lambda *a: None)
        return sync.run(job), out

    def connect(self, key=None, **options):
        return sync.connect(self.config, self.folder, SITE, "ga4",
                            {"property": PROP, **options}, "cli",
                            key=service_key() if key is None else key)


class Key(unittest.TestCase):
    def test_found_by_its_file_name(self):
        self.assertIs(yourtools.get("ga4"), GA4)
        self.assertEqual(GA4.name, "Google Analytics")

    def test_a_service_account_a_sign_in_or_nothing(self):
        self.assertEqual(GA4.check_key(service_key()), {"who": "robot@example.com"})
        self.assertEqual(GA4.check_key(SIGN_IN), {"who": "a Google sign-in (OAuth client ...123-abc)"})
        cases = {"not json": "not JSON", json.dumps({"type": "external_account"}): "neither",
                 json.dumps({"type": "authorized_user", "client_id": "x"}): "no client_secret",
                 service_key(token_uri="https://evil.example.com/t"): "not Google's", "": "empty"}
        for text, words in cases.items():
            with self.subTest(words=words), self.assertRaises(BadKey) as no:
                GA4.check_key(text)
            self.assertIn(words, str(no.exception))
            self.assertNotIn("test-client-secret", str(no.exception))

    def test_the_property_is_digits_not_the_measurement_id(self):
        self.assertEqual(GA4.clean_options({"property": PROP}), {"property": PROP})
        with self.assertRaises(ValueError) as no:
            GA4.clean_options({"property": "G-AB12CD34EF"})
        self.assertIn("not the G- measurement ID", str(no.exception))
        self.assertEqual(GA4.clean_options({"property": PROP, "key": "search"}),
                         {"property": PROP, "key": "search"})

    def test_what_the_site_check_found_is_a_suggestion(self):
        self.assertEqual(GA4.suggest({"tags": {"ga4": ["G-AB12CD34EF"]}}),
                         {"measurement_id": "G-AB12CD34EF"})
        self.assertEqual(GA4.suggest(None), {})
        self.assertIn("add robot@example.com with the role Viewer", GA4.grant("robot@example.com"))


class Fetch(Base):
    def test_every_report_read_only_ga4s_own_days(self):
        g = Google()
        answers = GA4.fetch(service_key(), {"property": PROP}, NOW, opener=g, sleep=lambda s: None)
        self.assertEqual(len(g.tokens), 1, "one token for every call")
        self.assertEqual(claims(g.tokens[0])["scope"], SCOPE)
        self.assertEqual(SCOPE, "https://www.googleapis.com/auth/analytics.readonly")
        self.assertEqual([a.report for a in answers], REPORTS)
        for report, ask in zip(REPORTS, g.asked):
            want = ({"startDate": "56daysAgo", "endDate": "29daysAgo"} if report == "previous"
                    else {"startDate": "28daysAgo", "endDate": "yesterday"})
            self.assertEqual(ask["dateRanges"], [want], report)
        self.assertNotIn("dimensions", g.asked[0])
        self.assertNotIn("dimensions", g.asked[1])
        self.assertEqual((g.asked[2]["limit"], g.asked[2]["metricAggregations"]), (10, ["TOTAL"]))
        self.assertEqual(g.asked[3]["dimensions"], [{"name": "sessionSourceMedium"}])
        events = g.asked[REPORTS.index("events")]
        self.assertEqual([o["metric"]["metricName"] for o in events["orderBys"]],
                         ["keyEvents", "eventCount"], "key events first, then the most fired")
        before = answers[1]
        self.assertEqual((before.start, before.end), ("2026-08-31", "2026-09-27"),
                         "the 28 days before the last 28")
        first = answers[0]
        self.assertEqual((first.start, first.end), ("2026-09-28", "2026-10-25"),
                         "New York's today is 26 October: its last 28 whole days")
        self.assertEqual(first.period, "2026-09-28..2026-10-25")
        self.assertIn("America/New_York", first.note)
        self.assertEqual(first.flags["subjectToThresholding"], True)
        self.assertEqual(answers[REPORTS.index("sources")].flags["samplingMetadatas"], True)
        self.assertNotIn("test-access-token", json.dumps(first.request))

    def test_figures_numbers_from_strings_totals_from_ga4(self):
        answers = GA4.fetch(service_key(), {"property": PROP}, NOW, opener=Google())
        totals = {f.name: f for f in GA4.figures(answers[0])}
        self.assertEqual({k: f.value for k, f in totals.items()},
                         {"sessions": 1234, "totalUsers": 980, "newUsers": 812,
                          "engagedSessions": 701, "engagementRate": 0.5680713128,
                          "averageSessionDuration": 94.27, "screenPageViews": 3105,
                          "keyEvents": 37, "sessionKeyEventRate": 0.0218800648})
        self.assertEqual(totals["totalUsers"].src, "/rows/0/metricValues/1/value")
        self.assertEqual(totals["totalUsers"].label, "Users")
        landing = GA4.figures(answers[REPORTS.index("landing")])
        top = [(f.name, f.dim, f.value) for f in landing]
        self.assertIn(("sessions", None, 1234), top, "the total is GA4's TOTAL")
        self.assertIn(("keyEvents", "(not set)", 1.5), top)
        self.assertIn(("keyEvents", "/blog/server-logs/", 0), top, "GA4 said 0: 0")
        self.assertEqual([f.dim for f in landing if f.name == "sessions" and f.dim],
                         ["/", "/pricing/", "/blog/server-logs/", "(not set)"], "GA4's order")
        self.assertEqual([f.label for f in GA4.headline(GA4.figures(answers[0]))],
                         ["Sessions", "Users", "New users", "Engagement rate", "Average session",
                          "Key events"])
        events = [(f.name, f.dim, f.value) for f in GA4.figures(answers[REPORTS.index("events")])]
        self.assertIn(("keyEvents", "generate_lead", 22), events)
        self.assertIn(("eventCount", None, 6420), events, "GA4's TOTAL of every event")

    def test_nothing_answered_is_null_never_zero(self):
        g = Google({"": FIXTURE["empty"], "previous": FIXTURE["empty"],
                    **{dim: {"metricHeaders": [{"name": "sessions"}]} for dim in DIMS.values()},
                    "landingPage": {**FIXTURE["landing"], "rows": [], "totals": []}})
        answers = GA4.fetch(service_key(), {"property": PROP}, NOW, opener=g)
        figs = [f for a in answers for f in GA4.figures(a)]
        self.assertTrue(figs)
        self.assertEqual({f.value for f in figs}, {None})
        self.assertEqual({f.src for f in figs}, {None})
        self.assertIn("Europe/Berlin", answers[0].note)

    def test_refusals_in_plain_words_without_a_token(self):
        cases = {403: "add it as a Viewer", 404: "not the G- measurement ID",
                 429: "quota is used up"}
        for code, words in cases.items():
            with self.subTest(code=code), self.assertRaises(Unreachable) as no:
                GA4.fetch(service_key(), {"property": PROP}, NOW, opener=Google(fail=code),
                          sleep=lambda s: None)
            self.assertIn(words, str(no.exception))
            self.assertEqual(no.exception.code, code)
            self.assertNotIn("test-access-token", str(no.exception))
        with self.assertRaises(Unreachable) as no:
            GA4.fetch(service_key(), {"property": PROP}, NOW, opener=Google(token_fail=400))
        self.assertIn("refused the service account's key", str(no.exception))
        with self.assertRaises(Unreachable) as no:
            GA4.fetch(service_key(), {}, NOW, opener=Google())
        self.assertIn("property ID", str(no.exception))

    def test_the_refresh_token_road(self):
        g = Google()
        answers = GA4.fetch(SIGN_IN, {"property": PROP}, NOW, opener=g)
        self.assertEqual(len(answers), len(REPORTS))
        self.assertEqual(g.tokens[0]["grant_type"], "refresh_token")
        self.assertEqual(g.tokens[0]["refresh_token"], "1//test-refresh")
        with self.assertRaises(Unreachable) as no:
            GA4.fetch(SIGN_IN, {"property": PROP}, NOW, opener=Google(token_fail=400))
        self.assertIn("refresh token was revoked", str(no.exception))
        for secret in ("test-client-secret-xyz", "1//test-refresh"):
            self.assertNotIn(secret, str(no.exception))


class SyncAndAudit(Base):
    def test_every_figure_rechecked_and_shown_labelled(self):
        self.assertEqual(self.connect()["who"], "robot@example.com")
        code, out = self.run_sync(Google())
        self.assertEqual(code, 0, out)
        part = conn.load(self.folder, SITE)["ga4"]
        self.assertTrue(part["audit"]["ok"], part["audit"])
        rows = {r: len(FIXTURE[r]["rows"]) for r in DIMS}
        self.assertEqual(part["audit"]["figures"], 9 + 9 + sum(2 + 2 * n for n in rows.values()))
        got = api.view(self.config, self.folder, SITE, admin=False, now=NOW)["tools"][0]
        self.assertEqual((got["state"], got["counted_from"]), ("answering",
                                                              "Counted from: Google Analytics"))
        self.assertEqual([(f["label"], f["value"]) for f in got["headline"]],
                         [("Sessions", 1234), ("Users", 980), ("New users", 812),
                          ("Engagement rate", 0.5680713128), ("Average session", 94.27),
                          ("Key events", 37)])
        # SKALD-55: the 28 days before, each figure's unit, the rows in GA4's order, the names.
        self.assertEqual(got["before"]["sessions"], 1100)
        self.assertEqual(got["before_period"], {"start": "2026-08-31", "end": "2026-09-27"})
        self.assertEqual([f.get("unit") for f in got["headline"]],
                         [None, None, None, "share", "seconds", None])
        channels = got["reports"]["channels"]
        self.assertEqual(channels["title"], "Channels")
        self.assertEqual([f["dim"] for f in channels["figures"] if f["name"] == "sessions" and f["dim"]],
                         ["Organic Search", "Direct", "Referral", "Organic Social", "Unassigned"])
        self.assertEqual(next(f for f in channels["figures"] if f["dim"])["rank"], 0, "GA4's first row")
        self.assertEqual(got["period"]["end"], "2026-10-25")
        self.assertIn("Thresholded: Google hid some small numbers", got["reports"]["totals"]["flags"])
        self.assertIn("Sampled: Google counted part of the data", got["reports"]["sources"]["flags"])

    def test_a_changed_figure_a_missing_row_or_a_zero_for_nothing_withholds(self):
        self.connect()
        self.assertEqual(self.run_sync(Google())[0], 0)
        db = sqlite3.connect(store.path_for(self.folder))
        with db:
            db.execute("UPDATE figures SET value = 1300 WHERE name = 'sessions' AND dim IS NULL "
                       "AND answer_id = (SELECT id FROM answers WHERE report = 'totals')")
            db.execute("DELETE FROM figures WHERE dim = 'chatgpt.com / referral' "
                       "AND name = 'keyEvents'")
        db.close()
        problems = recount.check(self.folder, SITE)["ga4"]["problems"]
        self.assertTrue(any("shown 1300" in p for p in problems), problems)
        self.assertTrue(any("chatgpt.com / referral: GA4 gave 5, not shown" in p
                            for p in problems), problems)

    def test_a_share_and_seconds_read_the_same_in_the_mail(self):
        """SKALD-55: a share as a percent, seconds as minutes, in the Monday mail's rows as on
        the card (api.shown); nothing given is Not given, never 0."""
        self.assertEqual([api.shown(v, u) for v, u in ((0.5680713128, "share"), (94.27, "seconds"),
                                                       (42, "seconds"), (1234, None), (None, "share"))],
                         ["56.8%", "1m 34s", "42s", "1,234", "Not given"])
        self.connect()
        self.assertEqual(self.run_sync(Google())[0], 0)
        from skald import mail_marketing
        t = api.view(self.config, self.folder, SITE, admin=False, now=NOW)["tools"][0]
        rows = dict(mail_marketing._tool_lines(t)[0])
        self.assertEqual((rows["Engagement rate"], rows["Average session"], rows["Sessions"]),
                         ("56.8%", "1m 34s", "1,234"))

    def test_an_answer_kept_before_skald_asked_for_more_still_rechecks(self):
        """SKALD-55: GA4 keeps an answer a day. One kept by the older code (four metrics
        asked, four figures) is judged by what it asked then, not withheld; a stored
        request naming a metric Skald never asks for is a problem."""
        self.connect()
        self.assertEqual(self.run_sync(Google())[0], 0)
        old = {"dimensionHeaders": [], "metricHeaders": [{"name": m, "type": "TYPE_INTEGER"} for m in
                                                         ("sessions", "totalUsers", "engagedSessions", "keyEvents")],
               "rows": [{"metricValues": [{"value": v} for v in ("900", "700", "500", "20")]}],
               "rowCount": 1, "metadata": {"timeZone": "America/New_York"}}
        asked = {"property": PROP, "dateRanges": [{"startDate": "28daysAgo", "endDate": "yesterday"}],
                 "metrics": [{"name": m} for m in ("sessions", "totalUsers", "engagedSessions", "keyEvents")]}
        from skald.yourtools.base import Answer as Kept
        answer = Kept(report="totals", period="2026-09-01..2026-09-28", start="2026-09-01",
                      end="2026-09-28", request=asked, body=old, flags={}, note="")
        db = store.connect(self.folder)
        with db:
            # The older code's four figures: the five metrics it never asked for left out.
            store.keep(db, SITE, "ga4", answer, [f for f in GA4.figures(answer) if f.value is not None],
                       "2026-09-29T00:00:00Z")
        db.close()
        got = recount.check(self.folder, SITE)["ga4"]
        self.assertTrue(got["ok"], got["problems"])
        db = sqlite3.connect(store.path_for(self.folder))
        with db:
            db.execute("UPDATE answers SET request = ? WHERE period = '2026-09-01..2026-09-28'",
                       (json.dumps({**asked, "metrics": [*asked["metrics"], {"name": "bounceRate"}]}),))
        db.close()
        problems = recount.check(self.folder, SITE)["ga4"]["problems"]
        self.assertTrue(any("never asks GA4 for 'bounceRate'" in p for p in problems), problems)

    def test_a_failure_keeps_the_figures_and_says_what_to_do(self):
        self.connect()
        self.assertEqual(self.run_sync(Google())[0], 0)
        code, out = self.run_sync(Google(fail=403))
        self.assertEqual(code, 1)
        part = conn.load(self.folder, SITE)["ga4"]
        self.assertIn("Property access management", part["error"])
        self.assertEqual(conn.status(part, True, NOW)["state"], "failing")
        got = api.view(self.config, self.folder, SITE, admin=False, now=NOW)["tools"][0]
        self.assertEqual(got["headline"][0]["value"], 1234, "the last good figures stay")

    def test_the_search_console_key_serves_ga4_too(self):
        path = secrets_store.path_for(self.config, self.folder)
        secrets_store.put(path, google.SECRET, service_key("search-robot@example.com"))
        got = sync.connect(self.config, self.folder, SITE, "ga4", {"property": PROP, "key": "search"},
                           "cli")
        self.assertEqual(got["who"], None)
        view = api.view(self.config, self.folder, SITE, admin=True, now=NOW)["tools"]
        ga = next(t for t in view if t["id"] == "ga4")
        self.assertEqual((ga["key"]["where"], ga["key"]["who"]),
                         ("search console key", "search-robot@example.com"))
        g = Google()
        self.assertEqual(self.run_sync(g)[0], 0)
        self.assertEqual(claims(g.tokens[0])["iss"], "search-robot@example.com")
        self.assertIsNone(secrets_store.load(path).get(f"tools/{SITE}/ga4"), "no copy kept")


class SiteCheck(unittest.TestCase):
    def test_tags_read_from_the_page_already_fetched(self):
        from skald import site_detect
        html = ('<script async src="https://www.googletagmanager.com/gtag/js?id=G-AB12CD34EF">'
                "</script><script>gtag('config', 'G-AB12CD34EF');</script>"
                '<a href="https://calendly.com/acme/demo">Book</a> G-NOTATAG')
        self.assertEqual(site_detect.tags_of(html), {"ga4": ["G-AB12CD34EF"],
                                                     "calendly": ["calendly.com/acme/demo"]})
        self.assertEqual(site_detect.tags_of(""), {})
        kept = site_detect.clean_found({"tags": {"ga4": ["G-AB12CD34EF", "<b>"], "x": ["y"]}})
        self.assertEqual(kept["tags"], {"ga4": ["G-AB12CD34EF"]})


if __name__ == "__main__":
    unittest.main()
