"""What AI fetches asked for (day kind `ai_formats`, ai_formats.py, second
count audit_ai_formats.py) and Google's AI Mode referrer label (dimensions
and audit_labels).

What is pinned:
- both path rules give the same format for every path below, edge cases too;
- the day's blob on a synthetic day, per tier and per name, and its sums;
  a planted error is caught by verify;
- names past the top list fold into "(all others)", and the audit agrees;
- collect + audit match, a tampered blob fails the audit (the live one too);
- app.json carries the day's blob (and today's from the snapshot);
- the recount imports nothing from the package;
- udm=50 on a Google search referrer (or the landing URL, with a Google
  referrer) labels the referrer "google.com (AI Mode)", still a search
  engine; never without the parameter, never for another host; both roads
  agree, and a collected day's audit matches.
"""
from __future__ import annotations

import ast
import json
import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support import ASKED, GPTBOT, Sandbox, line, totals_for  # noqa: E402

from skald import (ai_formats, audit_ai_formats, audit_labels, dashboard_webapp,  # noqa: E402
                          dimensions, extras)
from skald.audit import Line  # noqa: E402
from skald.store import History  # noqa: E402

UTC = timezone.utc
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
CLAUDEBOT = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0)"

PATHS = {
    "/": "Page", "/pricing/": "Page", "/blog/next.js-guide": "Page", "/about.html": "Page",
    "/llms.txt": "llms.txt", "/LLMS.TXT": "llms.txt", "/llms-full.txt": "llms.txt",
    "/docs/llms.txt": "Text", "/robots.txt": "robots.txt", "/docs/robots.txt": "Text",
    "/notes.txt": "Text", "/ads.txt": "Text", "/guide.md": "Markdown",
    "/docs/intro.MDX": "Markdown", "/index.html.md": "Markdown",
    "/sitemap.xml": "Sitemap", "/sitemap_index.xml": "Sitemap", "/blog/sitemap-1.xml": "Sitemap",
    "/sitemap.xml.gz": "Other file", "/feed.xml": "Other file", "/logo.png": "Other file",
    "/app.js": "Other file", "/report.pdf": "Other file", "/_next/static/chunk": "Other file",
    "/api/search": "Other file", "/api": "Other file", "/apis": "Page",
}


def at(hour: int, minute: int) -> datetime:
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=UTC)


def synthetic() -> list[str]:
    return [
        line(at(10, 0), "198.51.100.40", "/pricing/", ASKED),
        line(at(10, 1), "198.51.100.40", "/llms.txt", ASKED),
        line(at(10, 2), "198.51.100.40", "/docs/guide.md", ASKED),
        line(at(10, 3), "198.51.100.40", "/missing.md", ASKED, status=404),
        line(at(11, 0), "198.51.100.41", "/robots.txt", GPTBOT),
        line(at(11, 1), "198.51.100.41", "/sitemap.xml", GPTBOT),
        line(at(11, 2), "198.51.100.41", "/", GPTBOT),
        line(at(11, 3), "198.51.100.41", "/llms-full.txt?x=1", GPTBOT),
        line(at(11, 4), "198.51.100.42", "/logo.png", CLAUDEBOT),
        line(at(11, 5), "198.51.100.42", "/notes.txt", CLAUDEBOT),
        line(at(12, 0), "203.0.113.10", "/pricing/"),                 # a person: not counted
    ]


WANT = {
    "asked": {"formats": {"Markdown": 2, "Page": 1, "llms.txt": 1},
              "by_name": {"ChatGPT-User": {"Markdown": 2, "Page": 1, "llms.txt": 1}}},
    "training": {"formats": {"Other file": 1, "Page": 1, "Sitemap": 1, "Text": 1,
                             "llms.txt": 1, "robots.txt": 1},
                 "by_name": {"GPTBot": {"Page": 1, "Sitemap": 1, "llms.txt": 1, "robots.txt": 1},
                             "ClaudeBot": {"Other file": 1, "Text": 1}}},
}


class TestPathRules(unittest.TestCase):

    def test_both_roads_read_every_path_the_same(self):
        for path, want in PATHS.items():
            with self.subTest(path=path):
                self.assertEqual(ai_formats.format_of(path), want)
                self.assertEqual(audit_ai_formats.kind_of(path, path), want)

    def test_a_framework_payload_is_a_file_on_both_roads(self):
        url = "/pricing?_rsc=abc"
        self.assertEqual(ai_formats.format_of("/pricing", url), "Other file")
        self.assertEqual(audit_ai_formats.kind_of("/pricing", url), "Other file")

    def test_every_format_is_named(self):
        self.assertEqual(set(PATHS.values()), set(ai_formats.FORMATS))


class TestTheDay(unittest.TestCase):

    def test_the_synthetic_day(self):
        totals = totals_for(synthetic())
        self.assertEqual(totals.extras["ai_formats"], WANT)
        self.assertEqual(extras.check(totals), [])

    def test_a_day_without_ai_has_both_tiers_empty(self):
        totals = totals_for([line(at(12, 0), "203.0.113.10", "/")])
        self.assertEqual(totals.extras["ai_formats"],
                         {t: {"formats": {}, "by_name": {}} for t in ai_formats.TIERS})
        self.assertEqual(extras.check(totals), [])

    def test_planted_errors_are_caught(self):
        totals = totals_for(synthetic())
        totals.extras["ai_formats"]["asked"]["formats"]["Page"] = 2
        whats = [p.what for p in extras.check(totals)]
        self.assertIn("ai_formats: asked fetches by format does not sum", whats)
        self.assertIn("ai_formats: asked Page by name does not sum", whats)
        totals = totals_for(synthetic())
        totals.extras["ai_formats"]["training"]["by_name"]["GPTBot"]["Text"] = 1
        self.assertIn("ai_formats: training Text by name does not sum",
                      [p.what for p in extras.check(totals)])

    def test_names_past_the_top_fold_and_keep_the_sums(self):
        with mock.patch.object(ai_formats, "TOP", 1):
            got = totals_for(synthetic())
        training = got.extras["ai_formats"]["training"]["by_name"]
        self.assertEqual(training, {"GPTBot": {"Page": 1, "Sitemap": 1, "llms.txt": 1,
                                               "robots.txt": 1},
                                    "(all others)": {"Other file": 1, "Text": 1}})
        self.assertEqual(extras.check(got), [])


class TestTheAudit(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(synthetic())

    def tearDown(self):
        self.box.close()

    def stored(self):
        with History(self.box.db) as h:
            return h.extras("example.com", DAY, DAY)[DAY.isoformat()]

    def tamper(self, blob):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'ai_formats'",
                       (json.dumps(blob),))
        db.close()

    def test_the_recount_matches_and_a_tampered_blob_fails(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        got = self.stored()["ai_formats"]
        self.assertEqual(got, WANT)
        got["training"]["formats"]["Sitemap"] = 2
        got["training"]["by_name"]["ClaudeBot"] = {"Page": 1, "Text": 1}
        self.tamper(got)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_formats: training Sitemap: history has 2, the recount finds 1", err)
        self.assertIn("ai_formats: training ClaudeBot Other file: history has 0, the recount "
                      "finds 1", err)

    def test_a_folded_day_recounts_exactly(self):
        with mock.patch.object(ai_formats, "TOP", 1):
            self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        self.assertIn("(all others)", self.stored()["ai_formats"]["training"]["by_name"])
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        got = self.stored()["ai_formats"]
        got["training"]["by_name"]["(all others)"] = {"Text": 2}
        self.tamper(got)
        code, _, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("ai_formats: training (all others) Text: history has 2, the recount "
                      "finds 1", err)

    def test_the_live_audit_compares_it_too(self):
        stamp = at(23, 0).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        self.assertEqual(self.box.run("--today", DAY.isoformat(), "live")[0], 0)
        code, _, err = self.box.run("--today", DAY.isoformat(), "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["extras"]["ai_formats"], WANT)
        self.assertEqual(dashboard_webapp.from_snapshot(snap)["ai_formats"], WANT)

    def test_app_json_carries_the_day(self):
        self.assertEqual(self.box.run("--today", TODAY, "collect")[0], 0)
        now = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
        with History(self.box.db) as h:
            got = dashboard_webapp.build(h, "example.com", "example.com", UTC, now, None)
        day = next(d for d in got["days"] if d["day"] == DAY.isoformat())
        self.assertEqual(day["ai_formats"], WANT)


class TestIndependence(unittest.TestCase):

    def test_the_recount_imports_nothing_from_the_package(self):
        tree = ast.parse(Path(audit_ai_formats.__file__).read_text())
        imported = {(n.module, a.name) for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(imported, set())


# ------------------------------------------------------------ Google AI Mode

OWN = {"example.com"}
CASES = [
    # (referrer, landing URL, label)
    ("https://www.google.com/search?q=skald&udm=50", "/", "google.com (AI Mode)"),
    ("https://www.google.de/search?udm=50", "/", "google.de (AI Mode)"),
    ("https://www.google.co.uk/", "/pricing?udm=50", "google.co.uk (AI Mode)"),
    ("https://www.google.com/search?UDM=%2050", "/", "google.com (AI Mode)"),
    ("https://www.google.com/", "/", "google.com"),
    ("https://www.google.com/search?udm=5", "/?udm=500", "google.com"),
    ("https://www.google.com/search?udm=14", "/", "google.com"),
    ("https://www.bing.com/search?udm=50", "/", "bing.com"),
    ("https://mail.google.com/?udm=50", "/", "mail.google.com"),
    ("https://notgoogle.com/?udm=50", "/", "notgoogle.com"),
    ("-", "/?udm=50", "(none)"),
    ("https://example.com/a?udm=50", "/", "(this site)"),
]


def audit_line(referrer: str, url: str) -> Line:
    return Line(when=at(10, 0), address="203.0.113.10", host="example.com", method="GET",
                url=url, status="200", referrer="" if referrer == "-" else referrer,
                agent="x", country="US")


class TestGoogleAIMode(unittest.TestCase):

    def test_both_roads_label_it_only_when_present(self):
        for referrer, url, want in CASES:
            with self.subTest(referrer=referrer, url=url):
                ref = "" if referrer == "-" else referrer
                self.assertEqual(dimensions.referrer_label(ref, OWN, url), want)
                self.assertEqual(audit_labels.referrer_of(audit_line(referrer, url), OWN), want)

    def test_it_stays_a_search_engine(self):
        ref = "https://www.google.com/search?udm=50"
        self.assertEqual(dimensions.source_type(ref, "/", False, OWN), "Search engine")
        self.assertEqual(audit_labels.source_of(audit_line(ref, "/"), False, OWN),
                         "Search engine")

    def test_a_collected_day_recounts_exactly(self):
        box = Sandbox()
        try:
            box.log([line(at(10, 0), "203.0.113.10", "/",
                          referrer="https://www.google.com/search?q=x&udm=50"),
                     line(at(10, 5), "203.0.113.11", "/", referrer="https://www.google.com/"),
                     line(at(10, 9), "203.0.113.12", "/pricing?udm=50",
                          referrer="https://www.google.com/")])
            self.assertEqual(box.run("--today", TODAY, "collect")[0], 0)
            code, _, err = box.run("--today", TODAY, "audit")
            self.assertEqual(code, 0, err)
            with History(box.db) as h:
                rows = dict((name, n) for _, _, name, n in h.count_rows(
                    "example.com", ["reader_referrer"], [DAY.isoformat()]))
            self.assertEqual(rows, {"google.com (AI Mode)": 2, "google.com": 1})
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
