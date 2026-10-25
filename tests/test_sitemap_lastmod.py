"""The sitemap's <lastmod> change dates (sitemap.py, sitemap_dates.py), how the
page lifecycle uses them (lifecycle.py: the website's own dates win, a
lastmod is a change date, never a publish date), and their second count
(audit_lastmod.py)."""
from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_lastmod, lifecycle, sitemap, sitemap_dates  # noqa: E402

from support import CHROME, GOOGLEBOT, Sandbox, line  # noqa: E402
from test_crawl_health import _Server  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NY = ZoneInfo("America/New_York")
UTC = timezone.utc

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{base}/sitemap-pages.xml</loc><lastmod>2026-10-01T00:00:00+00:00</lastmod></sitemap>
  <sitemap><loc>{base}/sitemap-blog.xml.gz</loc></sitemap>
</sitemapindex>"""
PAGES = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url><loc>{base}/</loc><lastmod>2026-10-04</lastmod></url>
  <url><loc>{base}/pricing/</loc><lastmod>2026-10-05T02:30:00Z</lastmod>
       <image:image><image:loc>{base}/img/p.png</image:loc></image:image></url>
  <url><loc>{base}/features/</loc></url>
  <url id="x"><loc>{base}/team/</loc><lastmod>last tuesday</lastmod></url>
  <url><loc>{base}/soon/</loc><lastmod>2027-01-01</lastmod></url>
</urlset>"""
BLOG = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/blog/one</loc><lastmod>2026-10-03T23:10:00.123-04:00</lastmod></url>
  <url><loc>{base}/blog/two</loc><lastmod> 2026-09-30 </lastmod></url>
</urlset>"""


class Parse(unittest.TestCase):
    def test_w3c_forms_to_the_sites_day(self):
        cases = {
            "2026-10-13": date(2026, 10, 13),              # a date stands as it is
            "2026-10-13T02:00:00Z": date(2026, 10, 12),    # still 12 Oct in New York
            "2026-10-13T02:00Z": date(2026, 10, 12),
            "2026-10-13T12:00:00+05:30": date(2026, 10, 13),
            "2026-10-13T01:00:00+05:30": date(2026, 10, 12),
            "2026-10-12T23:30:00.5-04:00": date(2026, 10, 12),
            "2026-10-12T23:30:00-0400": date(2026, 10, 12),
            "2026-10-13T02:00:00": date(2026, 10, 13),     # no zone: the site's own time
            " 2026-10-13 ": date(2026, 10, 13),
        }
        for raw, want in cases.items():
            self.assertEqual(sitemap_dates.day_of(raw, NY), want, raw)
        self.assertEqual(sitemap_dates.day_of("2026-10-13T02:00:00Z", UTC), date(2026, 10, 13))
        for bad in ("2026", "2026-10", "2026-02-30", "13/10/2026", "yesterday", "", None,
                    "1989-12-31", "2026-10-13T25:00Z", "2026-10-13T10:61:00Z",
                    "2026-10-13T10:00:00+25:00", "2026-10-13junk"):
            self.assertIsNone(sitemap_dates.day_of(bad, NY), bad)

    def test_counted_once_per_path(self):
        paths = ["/a", "/b", "/c", "/d", "/e"]
        raws = {"/a": ["2026-10-01", "2026-10-03"],      # two spellings: the latest
                "/b": ["not a date"], "/c": ["2026-12-01"],
                "/d": ["2026-12-01", "2026-10-02"]}      # the future one is ignored
        found, counts = sitemap_dates.dates(paths, raws, NY, date(2026, 10, 5))
        self.assertEqual(found, {"/a": "2026-10-03", "/d": "2026-10-02"})
        self.assertEqual(counts, {"dated": 2, "missing": 1, "invalid": 1, "future": 1})
        self.assertEqual(sum(counts.values()), len(paths))

    def test_read_entries_keeps_the_url_list_as_it_was(self):
        body = PAGES.format(base="https://example.com").encode()
        kind, urls, stamps = sitemap.read_entries(body, "t")
        self.assertEqual((kind, urls), sitemap.read_body(body, "t"))
        self.assertEqual(kind, "urlset")
        self.assertNotIn("https://example.com/img/p.png", urls)
        self.assertEqual(dict(stamps), {"https://example.com/": "2026-10-04",
                                        "https://example.com/pricing/": "2026-10-05T02:30:00Z",
                                        "https://example.com/team/": "last tuesday",
                                        "https://example.com/soon/": "2027-01-01"})
        kind, _, stamps = sitemap.read_entries(INDEX.format(base="https://example.com")
                                               .encode(), "i")
        self.assertEqual((kind, stamps), ("index", []))   # a child file's date is no page's
        self.assertEqual(sitemap.read_entries(b"https://example.com/a\n", "t")[2], [])


class Fetch(unittest.TestCase):
    """The same fetch as Crawl health: an index, a gzip child, odd dates."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.server = _Server({})
        self.base = self.server.base
        self.serve(PAGES, BLOG)
        self.config = {"site": {"hosts": ["127.0.0.1"]},
                       "report": {"timezone": "America/New_York"},
                       "crawl_health": {"sitemaps": [f"{self.base}/sitemap_index.xml"]}}

    def serve(self, pages: str, blog: str) -> None:
        base = self.base
        self.server.files.update({
            "/robots.txt": (200, b"", {}),
            "/sitemap_index.xml": (200, INDEX.format(base=base).encode(), {}),
            "/sitemap-pages.xml": (200, pages.format(base=base).encode(), {}),
            "/sitemap-blog.xml.gz": (200, gzip.compress(blog.format(base=base).encode()), {}),
        })

    def tearDown(self):
        self.server.close()
        self.tmp.cleanup()

    def days(self) -> dict:
        return json.loads((self.dir / "sitemaps" / "days.json").read_text())

    def test_one_fetch_the_list_unchanged_dates_kept(self):
        now = datetime(2026, 10, 6, 12, tzinfo=UTC)
        state = sitemap.refresh(self.config, self.dir, now)
        self.assertTrue(state["ok"], state)
        # the same fetch, nothing more: the index and its two files once each
        self.assertEqual(sorted(p for p, _ in self.server.asked),
                         ["/sitemap-blog.xml.gz", "/sitemap-pages.xml", "/sitemap_index.xml"])
        entry = self.days()["2026-10-06"]
        paths = sitemap.load_list(self.dir, entry["list"])
        # the list Crawl health is judged by is the list without any lastmod
        bare = sitemap.collect(self.config, None, lambda u: _strip(self.server, u))
        self.assertEqual(paths, bare["paths"])
        self.assertEqual(entry["list"], sitemap.list_id(bare["paths"]))
        self.assertEqual(entry["lastmod"]["version"], 1)
        self.assertEqual({k: entry["lastmod"][k] for k in ("dated", "missing", "invalid",
                                                            "future")},
                         {"dated": 4, "missing": 1, "invalid": 1, "future": 1})
        self.assertEqual(state["lastmod"]["dated"], 4)
        got = sitemap_dates.load(self.dir)
        self.assertEqual({p: e["now"] for p, e in got.items()},
                         {"/": "2026-10-04", "/pricing/": "2026-10-04",   # 02:30 UTC = 4 Oct NY
                          "/blog/one": "2026-10-03", "/blog/two": "2026-09-30"})
        self.assertEqual(got["/pricing/"]["seen"], [["2026-10-04", "2026-10-06"]])

    def test_changes_across_days_capped_and_kept_by_the_clean_up(self):
        day = datetime(2026, 10, 6, 12, tzinfo=UTC)
        sitemap.refresh(self.config, self.dir, day)
        sitemap.refresh(self.config, self.dir, day + timedelta(days=1))   # nothing changed
        self.serve(PAGES.replace("<lastmod>2026-10-04</lastmod>", "<lastmod>2026-10-08</lastmod>")
                   .replace("<url><loc>{base}/features/</loc></url>", ""), BLOG)
        sitemap.refresh(self.config, self.dir, day + timedelta(days=2))
        got = sitemap_dates.load(self.dir)
        self.assertEqual(got["/"]["seen"], [["2026-10-04", "2026-10-06"],
                                            ["2026-10-08", "2026-10-08"]])
        self.assertEqual(got["/blog/two"]["seen"], [["2026-09-30", "2026-10-06"]])
        # the list changed (a page left it): the old list file is removed, the dates stay
        self.assertTrue(sitemap_dates.path_of(self.dir).is_file())
        self.assertEqual(len(self.days()), 3)
        # a path the day's sitemap no longer dates keeps its history, now null
        found = {"/blog/one": "2026-10-03"}
        self.assertTrue(sitemap_dates.merge(self.dir, date(2026, 10, 9), found))
        self.assertFalse(sitemap_dates.merge(self.dir, date(2026, 10, 9), found))  # once a day
        got = sitemap_dates.load(self.dir)
        self.assertIsNone(got["/"]["now"])
        self.assertEqual(got["/"]["last"], "2026-10-08")
        for k in range(sitemap_dates.CAP + 5):
            d = date(2026, 10, 10) + timedelta(days=k)
            sitemap_dates.merge(self.dir, d, {"/blog/one": d.isoformat()})
        self.assertEqual(len(sitemap_dates.load(self.dir)["/blog/one"]["seen"]),
                         sitemap_dates.CAP)
        far = date(2026, 10, 9) + timedelta(days=sitemap_dates.KEEP_DAYS + 30)
        sitemap_dates.merge(self.dir, far, {"/blog/one": "2026-11-01"})
        self.assertEqual(sorted(sitemap_dates.load(self.dir)), ["/blog/one"])

    def test_a_sitemap_without_any_lastmod(self):
        self.serve(PAGES.replace("<lastmod>", "<x>").replace("</lastmod>", "</x>"),
                   "<urlset><url><loc>{base}/blog/one</loc></url></urlset>")
        sitemap.refresh(self.config, self.dir, datetime(2026, 10, 6, 12, tzinfo=UTC))
        entry = self.days()["2026-10-06"]
        self.assertEqual((entry["lastmod"]["dated"], entry["lastmod"]["missing"]), (0, 6))
        self.assertEqual(sitemap_dates.load(self.dir), {})
        self.assertEqual(lifecycle.page_dates({}, self.dir), {})


def _strip(server, url: str) -> bytes:
    """The served file with every <lastmod> taken out."""
    import re
    import urllib.request
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = resp.read()
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return re.sub(rb"<lastmod>[^<]*</lastmod>", b"", body)


def _history(folder: Path, day: str, pages: dict, listed: list[str], seen=None) -> None:
    """A kept day: its list, its days.json entry and the lastmod history."""
    got = {"paths": sorted(listed), "sources": ["https://example.com/sitemap.xml"],
           "skipped": 0, "truncated": False,
           "lastmod": {p: [d] for p, d in pages.items()}}
    sitemap.keep(folder, date.fromisoformat(day), got, f"{day}T06:00:00+00:00", UTC)


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        meta = self.dir / "pages.json"
        meta.write_text(json.dumps({"generated": "2026-10-08", "pages": [
            {"path": "/launch/", "published": "2026-10-03", "updated": "2026-10-05"},
            {"path": "/old/", "published": "2026-01-03"}]}))
        self.config = {"report": {"pages_meta": str(meta)},
                       "_resolved": {"live_dir": str(self.dir)}}
        listed = ["/launch/", "/old/", "/blog/a", "/blog/a/", "/only-in-sitemap/"]
        _history(self.dir, "2026-10-06", {"/launch/": "2026-10-06", "/old/": "2026-10-01",
                                          "/blog/a": "2026-10-02", "/blog/a/": "2026-10-04",
                                          "/only-in-sitemap/": "2026-09-01"}, listed)
        _history(self.dir, "2026-10-07", {"/launch/": "2026-10-06", "/old/": "2026-10-07",
                                          "/blog/a": "2026-10-02", "/blog/a/": "2026-10-04",
                                          "/only-in-sitemap/": "2026-09-01"}, listed)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_websites_dates_win_and_the_sitemap_fills_in(self):
        got = lifecycle.page_dates(self.config, self.dir)
        # pages_meta gives /launch/ an updated date: it stands, the lastmod is still shown
        self.assertEqual((got["/launch/"]["updated"], got["/launch/"]["updated_source"],
                          got["/launch/"]["lastmod"]), ("2026-10-05", "website", "2026-10-06"))
        # pages_meta gives /old/ no updated date: the sitemap's change date fills it
        self.assertEqual((got["/old/"]["updated"], got["/old/"]["updated_source"]),
                         ("2026-10-07", "sitemap"))
        self.assertEqual(got["/old/"]["lastmod_seen"], [["2026-10-01", "2026-10-06"],
                                                        ["2026-10-07", "2026-10-07"]])
        # two spellings of one page are one page; the latest date wins
        self.assertEqual(got["/blog/a/"]["lastmod"], "2026-10-04")
        self.assertEqual(got["/blog/a/"]["lastmod_seen"], [["2026-10-02", "2026-10-06"],
                                                           ["2026-10-04", "2026-10-06"]])
        self.assertNotIn("/blog/a", got)
        # switched off: no change date is shown
        off = {**self.config, "crawl_health": {"sitemap": False}}
        self.assertEqual({p: v["lastmod"] for p, v in lifecycle.page_dates(off, self.dir)
                          .items()}, {"/launch/": None, "/old/": None})

    def test_the_audit_agrees_and_catches_a_nudge(self):
        ctx = SimpleNamespace(live_dir=self.dir, config=self.config, out=lambda *_: None)
        self.assertTrue(audit_lastmod.set_up(ctx))
        self.assertEqual(audit_lastmod.daily(ctx, date(2026, 10, 7)), [])
        shown = lifecycle.page_dates(self.config, self.dir)
        shown["/old/"]["updated"] = "2026-10-01"
        problems = audit_lastmod.recheck(self.config, self.dir, shown)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("/old/: updated", problems[0])
        # the history file rewritten after the day: its digest no longer matches
        path = sitemap_dates.path_of(self.dir)
        kept = json.loads(path.read_text())
        kept["paths"]["/old/"]["seen"][-1][0] = "2026-10-06"
        kept["paths"]["/old/"]["now"] = "2026-10-06"
        path.write_text(json.dumps(kept))
        problems = audit_lastmod.daily(ctx, date(2026, 10, 7))
        self.assertTrue(any("digest" in p for p in problems), problems)
        self.assertIsNone(audit_lastmod.daily(SimpleNamespace(live_dir=self.dir / "none",
                                                              config={}, out=print), None))


class Story(unittest.TestCase):
    """End to end: the logs, a kept sitemap day, `skald page` and page_index.json."""

    def setUp(self):
        self.box = Sandbox()
        t = datetime(2026, 10, 4, 14, tzinfo=UTC)
        self.box.log([line(t, "198.51.100.41", "/guide/", GOOGLEBOT),
                      line(t + timedelta(hours=1), "203.0.113.5", "/guide/", CHROME)])
        code, _, err = self.box.run("--today", "2026-10-06", "backfill", "--days", "2")
        self.assertEqual(code, 0, err)
        _history(self.box.root, "2026-10-06", {"/guide/": "2026-10-02",
                                               "/new/": "2026-10-05"}, ["/guide/", "/new/"])

    def tearDown(self):
        self.box.close()

    def test_published_stays_first_seen_and_changed_comes_from_the_sitemap(self):
        code, out, err = self.box.run("--today", "2026-10-06", "page", "/guide/", "--json")
        self.assertEqual(code, 0, err)
        got = json.loads(out)
        self.assertEqual((got["published"], got["date_source"]), ("2026-10-04", "first seen"))
        self.assertEqual((got["updated"], got["updated_source"], got["lastmod"]),
                         ("2026-10-02", "sitemap", "2026-10-02"))
        # a page only the sitemap lists has a story too, with no publish date
        code, out, _ = self.box.run("--today", "2026-10-06", "page", "/new/", "--json")
        got = json.loads(out)
        self.assertEqual((code, got["published"], got["updated"], got["days"]),
                         (0, None, "2026-10-05", []))
        code, out, _ = self.box.run("--today", "2026-10-06", "page", "/guide/")
        self.assertIn("changed 2026-10-02 (from the sitemap)", out)
        out_dir = self.box.root / "out"
        code, _, err = self.box.run("--today", "2026-10-06", "dashboard", "--out", str(out_dir))
        self.assertEqual(code, 0, err)
        index = json.loads(next(out_dir.rglob("page_index.json")).read_text())
        rows = {r["path"]: r for r in index["pages"]}
        self.assertEqual(rows["/new/"]["lastmod_seen"], [["2026-10-05", "2026-10-06"]])
        self.assertIsNone(rows["/new/"]["published"])
        self.assertEqual(index["meta"]["lastmod"]["day"], "2026-10-06")
        self.assertEqual(index["meta"]["lastmod"]["dated"], 2)

    def test_run_daily_rechecks_them(self):
        code, out, err = self.box.run("--today", "2026-10-05", "run-daily")
        self.assertIn("sitemap_lastmod: ok, the recount matches", out, err)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class Page(unittest.TestCase):
    def test_the_pages_tab_says_changed_from_your_sitemap(self):
        got = subprocess.run(["node", str(ROOT / "tests" / "js" / "page-dates.mjs")],
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        self.assertIn("page dates: ok", got.stdout)


if __name__ == "__main__":
    unittest.main()
