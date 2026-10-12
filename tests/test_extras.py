"""Day extras (schema 9) and the data files beside the dashboard.

What is pinned: hours add up to the day; the 404 report reconciles with
the 404s people met, keeps probes apart and knows the site's own redirect
map; campaigns keep the five UTM tags, the ad network (never the click
id) and the ref= value and drop every other query parameter; pages add up
to page views and visits; the heartbeat yields uptime and gaps; every
contract file is written with its envelope; and no address reaches any of
them except the AI events the owner asked to see.
"""
from __future__ import annotations

import json
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import check, data_files  # noqa: E402
from skald.campaigns import fields  # noqa: E402
from skald.redirects import RedirectMap  # noqa: E402
from skald.store import History  # noqa: E402

from support import CHROME, GPTBOT, UTC, Sandbox, day_lines, line, totals_for  # noqa: E402
from test_visits import DAY, T, journey_day  # noqa: E402

LEGACY = '''export const LEGACY_REDIRECTS: Record<string, string> = {
  "/old-terms/": "/terms/", // same document
};
export const LEGACY_GONE: string[] = [
  "/blog/gone-post/",
];
export const LEGACY_GONE_PREFIXES: string[] = ["/author/"];
'''


def campaign_lines() -> list[str]:
    return [
        line(T, "203.0.113.80", "/pricing/?utm_source=LinkedIn&utm_medium=social&utm_campaign="
             "Launch&utm_term=sms&utm_content=a&email=x%40y.com&gclid=SECRET123", CHROME),
        line(T + timedelta(minutes=1), "203.0.113.81", "/?ref=producthunt", CHROME,
             "https://blog.example.org/best-tools/?x=1"),
        line(T + timedelta(minutes=2), "203.0.113.82", "/", CHROME,
             "https://www.google.com/search?q=sms+alerts"),
        line(T + timedelta(minutes=3), "203.0.113.83", "/old-terms/", CHROME,
             "https://forum.example.net/t/1", status=404),
        line(T + timedelta(minutes=4), "198.51.100.90", "/wp-login.php", CHROME, status=404),
        line(T + timedelta(minutes=5), "198.51.100.91", "/blog/gone-post/", GPTBOT, status=410),
    ]


class TestDayExtras(unittest.TestCase):

    def setUp(self):
        self.totals = totals_for(day_lines(DAY, 3) + journey_day() + campaign_lines())
        self.ex = self.totals.extras

    def test_everything_reconciles(self):
        self.assertEqual(check(self.totals), [])

    def test_hours_add_up(self):
        hourly = self.ex["hourly"]
        for group, stats in self.totals.groups.items():
            self.assertEqual(sum(h[group.value] for h in hourly.values()), stats.hits)

    def test_the_404_report(self):
        rows = self.ex["not_found"]
        people = [r for r in rows if r["group"] == "people" and r["status"] == 404]
        self.assertEqual(sum(r["n"] for r in people),
                         self.totals.groups[next(g for g in self.totals.groups
                                                 if g.value == "people")].statuses["404"])
        probe = next(r for r in rows if r["path"] == "/wp-login.php")
        self.assertTrue(probe["probe"])
        self.assertEqual(probe["group"], "bots")
        gone = next(r for r in rows if r["status"] == 410)
        self.assertEqual(gone["group"], "ai_training")
        linked = next(r for r in rows if r["path"] == "/old-terms/")
        self.assertEqual((linked["source"], linked["source_kind"]),
                         ("forum.example.net", "Other website"))

    def test_campaign_fields_keep_only_what_is_useful(self):
        got = fields("/p/?utm_source=LinkedIn&utm_campaign=Launch&email=x%40y.com&gclid=ID9",
                     "", "Social media")
        self.assertEqual(got["utm"], {"source": "linkedin", "campaign": "launch"})
        self.assertEqual(got["paid"], "Google Ads")
        self.assertNotIn("ID9", json.dumps(got))
        self.assertNotIn("x@y.com", json.dumps(got))
        other = fields("/", "https://blog.example.org/best-tools/?x=1", "Other website")
        self.assertEqual(other["ref_page"], "blog.example.org/best-tools/")
        search = fields("/", "https://www.google.com/search?q=sms+alerts", "Search engine")
        self.assertEqual((search["ref_host"], search["ref_page"], search["search_terms"]),
                         ("google.com", "", "sms alerts"))

    def test_campaign_rows_add_up_to_visits(self):
        rows = self.ex["campaigns"]["rows"]
        for d, items in rows.items():
            self.assertEqual(sum(r["visits"] for r in items), self.totals.visits.visits, d)
        self.assertEqual({r["name"] for r in rows["paid"]}, {"Google Ads", "(none)"})
        self.assertIn("producthunt", {r["name"] for r in rows["ref_param"]})
        self.assertNotIn("SECRET123", json.dumps(self.ex))

    def test_pages_add_up(self):
        pages = self.ex["pages"]
        people = next(s for g, s in self.totals.groups.items() if g.value == "people")
        self.assertEqual(sum(p["views"] for p in pages.values()), people.views)
        self.assertEqual(sum(p["entries"] for p in pages.values()), self.totals.visits.visits)
        self.assertEqual(pages["/compare/x/"]["assistants"], {"ChatGPT": 1})
        self.assertEqual(pages["/compare/x/"]["time"], {"40": 1})     # to the in-app page

    def test_redirect_map(self):
        m = RedirectMap.load(None)
        self.assertEqual(m.state("/x/"), ("", ""))
        tmp = Path(self.id().replace(".", "_") + ".ts")
        try:
            tmp.write_text(LEGACY)
            m = RedirectMap.load(tmp)
        finally:
            tmp.unlink()
        self.assertEqual(m.state("/old-terms"), ("redirected", "/terms/"))
        self.assertEqual(m.state("/blog/gone-post/"), ("gone", ""))
        self.assertEqual(m.state("/author/bob/"), ("gone", ""))


class TestDataFiles(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox(views=["{name: Guides, path_prefix: /guides/}"])
        legacy = self.box.root / "legacy-urls.ts"
        legacy.write_text(LEGACY)
        text = self.box.config.read_text().replace(
            "ours:\n  user_agents: [MyCompanyCrawler]\n",
            "ours:\n  user_agents:\n    - MyCompanyCrawler\n"
            "    - {agent: skald-heartbeat, label: heartbeat}\n")
        self.box.config.write_text(text.replace(
            "report:\n", f"report:\n  redirect_map: {legacy}\n"))
        beats = [line(datetime(2026, 10, 5, 4 + i // 12, (i % 12) * 5, tzinfo=UTC),
                      "198.51.100.200", "/robots.txt", "skald-heartbeat")
                 for i in range(36)]
        self.box.log(day_lines(DAY, 3) + journey_day() + campaign_lines() + beats)
        code, _, err = self.box.run("--today", "2026-10-06", "collect", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        with mock.patch("skald.cli._now", return_value=datetime(2026, 10, 6, 9, tzinfo=UTC)):
            code, _, err = self.box.run("dashboard")
        self.assertEqual(code, 0, err)
        self.data = self.box.root / "www" / "example.com" / "data"

    def tearDown(self):
        self.box.close()

    def load(self, name: str, view: str | None = None) -> dict:
        folder = self.data if view is None else self.data.parent / view / "data"
        return json.loads((folder / f"{name}.json").read_text())

    def test_every_file_has_its_envelope(self):
        for view in (None, "guides"):
            for name in data_files.files():
                got = self.load(name, view)
                self.assertEqual(got["schema_version"], 1, name)
                for key in ("generated_at", "site", "timezone", "view"):
                    self.assertIn(key, got, name)
        self.assertEqual(self.load("overview", "guides")["view"]["slug"], "guides")

    def test_no_address_in_any_file(self):
        for path in list(self.data.glob("*.json")) + list(
                (self.data.parent / "guides" / "data").glob("*.json")):
            text = path.read_text()
            for secret in ("203.0.113.", "198.51.100.", "Mozilla", "SECRET123", "x%40y"):
                self.assertNotIn(secret, text, f"{path.name}: {secret}")

    def test_day_rows(self):
        overview = self.load("overview")
        day = next(d for d in overview["days"] if d["day"] == "2026-10-05")
        self.assertIn(day["state"], ("ok", "partial"))
        self.assertEqual(day["visits"]["visits"], day["groups"]["people"]["readers"])
        hourly = next(d for d in self.load("hourly")["days"] if d["day"] == "2026-10-05")
        self.assertEqual(sum(h["people"] for h in hourly["hours"].values()),
                         day["groups"]["people"]["hits"])
        self.assertEqual(len(hourly["hours"]), 24)

    def test_heartbeat_uptime_and_gaps(self):
        day = next(d for d in self.load("ours")["days"] if d["day"] == "2026-10-05")
        beat = day["heartbeat"]
        self.assertEqual((beat["seen"], beat["ok"], beat["expected"]), (36, 36, 288))
        self.assertEqual(beat["uptime_pct"], 12.5)
        self.assertEqual(beat["gaps"][0]["from"], "00:00")
        self.assertEqual(day["labels"]["heartbeat"], 36)

    def test_not_found_paths_know_their_fix(self):
        paths = {r["path"]: r for r in self.load("not_found")["paths"]}
        self.assertEqual(paths["/old-terms/"]["fix"], "redirected")
        self.assertEqual(paths["/blog/gone-post/"]["fix"], "gone")
        self.assertTrue(paths["/wp-login.php"]["probe"])

    def test_the_audit_recounts_the_extras(self):
        code, out, err = self.box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 0, err)
        with History(self.box.db) as h:
            h.db.execute("UPDATE day_extras SET data = replace(data, '\"people\": 1', "
                         "'\"people\": 2') WHERE kind = 'hourly' AND site = 'example.com'")
            h.db.commit()
        code, _, err = self.box.run("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        self.assertEqual(code, 1)
        self.assertIn("people", err)

    def bump_page(self, path: str, key: str, by: int) -> None:
        where = "kind = 'pages' AND site = 'example.com' AND day = '2026-10-05'"
        with History(self.box.db) as h:
            (raw,) = h.db.execute(f"SELECT data FROM day_extras WHERE {where}").fetchone()
            pages = json.loads(raw)
            pages[path][key] += by
            h.db.execute(f"UPDATE day_extras SET data = ? WHERE {where}", (json.dumps(pages),))
            h.db.commit()

    def test_the_audit_recounts_each_pages_visits_and_exits(self):
        # pages.json's exit rate is exits / visits per page: both are recounted.
        stored = self.load("pages")
        features = next(p for p in stored["pages"] if p["path"] == "/features/")
        self.assertEqual((features["visits"], features["views"]), (1, 0))     # in-app only
        audit = ("--today", "2026-10-06", "audit", "--day", "2026-10-05")
        code, _, err = self.box.run(*audit)
        self.assertEqual(code, 0, err)
        for path, key in (("/features/", "visits"), ("/pricing/", "exits")):
            with self.subTest(key=key):
                self.bump_page(path, key, 1)
                code, _, err = self.box.run(*audit)
                self.assertEqual(code, 1)
                self.assertIn(f"page {path}: {key}", err)
                self.bump_page(path, key, -1)
                code, _, err = self.box.run(*audit)
                self.assertEqual(code, 0, err)

if __name__ == "__main__":
    unittest.main()
