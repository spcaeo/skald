"""Crawl health (sitemap.py, crawl_health.py, audit_crawl_health.py): the
site's sitemaps read from a fake server, kept once per day; each crawler's
fetches beside the list, the problems it hit, verified, recounted by the
audit, and written to crawl_health.json."""
from __future__ import annotations

import gzip
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import crawl_health, sitemap  # noqa: E402

from support import ASKED, GOOGLEBOT, GPTBOT, UTC, Sandbox, line  # noqa: E402

BING = "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"
DAY = date(2026, 10, 5)
NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{base}/sitemap-pages.xml</loc></sitemap>
  <sitemap><loc>{base}/sitemap-blog.xml.gz</loc></sitemap>
  <sitemap><loc>https://cdn.example.net/sitemap-other.xml</loc></sitemap>
</sitemapindex>"""
PAGES = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/</loc></url>
  <url><loc>{base}/pricing/?ref=sitemap&amp;x=1</loc></url>
  <url><loc> {base}/features/ </loc></url>
  <url><loc>https://elsewhere.example.org/not-ours</loc></url>
</urlset>"""
BLOG = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/blog/one</loc></url><url><loc>{base}/blog/two</loc></url>
</urlset>"""


class _Server:
    """A local site that serves sitemaps and counts what it was asked for."""

    def __init__(self, files: dict[str, tuple[int, bytes, dict]]) -> None:
        self.files, self.asked = files, []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):          # noqa: N802
                outer.asked.append((self.path, self.headers.get("User-Agent")))
                code, body, headers = outer.files.get(self.path, (404, b"no", {}))
                self.send_response(code)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                return

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


class TestFetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.server = _Server({})
        base = self.server.base
        self.server.files.update({
            "/robots.txt": (200, f"User-agent: *\nSitemap: {base}/sitemap_index.xml\n".encode(), {}),
            "/sitemap_index.xml": (200, INDEX.format(base=base).encode(), {}),
            "/sitemap-pages.xml": (200, PAGES.format(base=base).encode(), {}),
            "/sitemap-blog.xml.gz": (200, gzip.compress(BLOG.format(base=base).encode()), {}),
        })
        self.config = {"site": {"hosts": ["127.0.0.1"]}, "report": {"timezone": "UTC"},
                       "crawl_health": {"sitemaps": [f"{base}/sitemap_index.xml"]}}
        (self.dir / "robots.txt").write_text(
            self.server.files["/robots.txt"][1].decode())

    def tearDown(self):
        self.server.close()
        self.tmp.cleanup()

    def test_index_gzip_and_only_the_sites_own_hosts(self):
        state = sitemap.refresh(self.config, self.dir, NOW)
        self.assertTrue(state["ok"], state)
        days = json.loads((self.dir / "sitemaps" / "days.json").read_text())
        entry = days["2026-10-06"]
        paths = sitemap.load_list(self.dir, entry["list"])
        self.assertEqual(paths, ["/", "/blog/one", "/blog/two", "/features/", "/pricing/"])
        # the CDN sitemap and the other host's page are skipped, never fetched
        self.assertEqual(entry["skipped"], 2)
        self.assertTrue(all(agent == sitemap.AGENT for _, agent in self.server.asked))
        self.assertNotIn("/sitemap-other.xml", [p for p, _ in self.server.asked])
        self.assertEqual(entry["list"], sitemap.list_id(paths))

    def test_one_list_a_day_hourly_retries_and_the_last_good_copy(self):
        sitemap.refresh(self.config, self.dir, NOW)
        asked = len(self.server.asked)
        # the day's list stands: no fetch again that day, even hours later
        sitemap.refresh(self.config, self.dir, NOW + timedelta(hours=5))
        self.assertEqual(len(self.server.asked), asked)
        # the next day the server is down: tried, failed, the old list judges it
        self.server.files.clear()
        later = NOW + timedelta(days=1)
        state = sitemap.refresh(self.config, self.dir, later)
        self.assertFalse(state["ok"])
        sitemap.refresh(self.config, self.dir, later + timedelta(minutes=20))
        tries = len(self.server.asked)
        sitemap.refresh(self.config, self.dir, later + timedelta(minutes=40))
        self.assertEqual(len(self.server.asked), tries)     # not inside the hour
        cfg = {**self.config, "_resolved": {"live_dir": str(self.dir)}}
        got = sitemap.for_day(cfg, date(2026, 10, 7))
        self.assertEqual(got["day"], "2026-10-06")
        self.assertIn("/blog/two", got["paths"])
        self.assertIsNone(sitemap.for_day(cfg, date(2026, 10, 5)))

    def test_refused_doctype_off_site_redirect_and_switch_off(self):
        base = self.server.base
        self.server.files["/sitemap_index.xml"] = (
            200, b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><urlset>&a;</urlset>', {})
        self.server.files["/robots.txt"] = (200, b"", {})
        (self.dir / "robots.txt").write_text("")
        self.server.files["/sitemap.xml"] = (302, b"", {"Location": "https://example.org/x.xml"})
        cfg = {**self.config, "crawl_health": {"sitemaps": [f"{base}/sitemap_index.xml",
                                                            f"{base}/sitemap.xml"]}}
        state = sitemap.refresh(cfg, self.dir, NOW)
        self.assertFalse(state["ok"])
        self.assertIn("DOCTYPE", state["error"])
        self.assertIn("off the site", state["error"])
        self.assertNotIn("example.org", [p for p, _ in self.server.asked])
        off = {**self.config, "crawl_health": {"sitemap": False}}
        before = len(self.server.asked)
        sitemap.refresh(off, Path(self.tmp.name) / "x", NOW)
        self.assertEqual(len(self.server.asked), before)

    def test_a_plain_text_sitemap(self):
        kind, urls = sitemap.read_body(b"https://example.com/a\nhttps://example.com/b?x=1\n# c\n",
                                       "t")
        self.assertEqual((kind, urls), ("text", ["https://example.com/a",
                                                 "https://example.com/b?x=1"]))


def _keep(root: Path, day: str, paths: list[str]) -> str:
    got = {"paths": sorted(paths), "sources": ["https://example.com/sitemap.xml"],
           "skipped": 0, "truncated": False}
    return sitemap.keep(root, date.fromisoformat(day), got, f"{day}T06:00:00+00:00")["list"]


def _line(when, path, agent, status=200, size=512, secs=0.004):
    return (f'{when.isoformat()} 198.51.100.40 example.com "GET {path} HTTP/2.0" {status} '
            f'{size} "-" "{agent}" {secs} cc=US ray=0000000000000000-LHR\n')


class TestDay(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        t = datetime(2026, 10, 5, 8, tzinfo=UTC)
        self.box.log([
            _line(t, "/", GOOGLEBOT),
            _line(t + timedelta(minutes=1), "/pricing/", GOOGLEBOT),
            _line(t + timedelta(minutes=2), "/pricing/", GOOGLEBOT, secs=1.5),
            _line(t + timedelta(minutes=3), "/old-page", GOOGLEBOT, status=404),
            _line(t + timedelta(minutes=4), "/moved", GOOGLEBOT, status=301),
            _line(t + timedelta(minutes=5), "/not-listed/", GOOGLEBOT),
            _line(t + timedelta(minutes=6), "/big.pdf", GOOGLEBOT, size=2_500_000),
            _line(t + timedelta(minutes=7), "/", BING, status=503),
            _line(t + timedelta(minutes=8), "/blog/one", GPTBOT),
            _line(t + timedelta(minutes=9), "/llms.txt", GPTBOT),
            _line(t + timedelta(minutes=10), "/not-listed/", ASKED),
            line(t + timedelta(minutes=11), "203.0.113.5", "/features/"),
        ])
        self.lid = _keep(self.box.root, "2026-10-04", ["/", "/pricing/", "/features/",
                                                       "/blog/one", "/blog/two"])

    def tearDown(self):
        self.box.close()

    def stored(self) -> dict:
        with sqlite3.connect(self.box.db) as db:
            return json.loads(db.execute(
                "SELECT data FROM day_extras WHERE site = 'example.com' AND "
                "kind = 'crawl_health'").fetchone()[0])

    def put(self, blob: dict) -> None:
        with sqlite3.connect(self.box.db) as db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'crawl_health' AND "
                       "site = 'example.com'", (json.dumps(blob),))

    def test_counted_against_the_sitemap_and_audited(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        blob = self.stored()
        self.assertEqual(blob["sitemap"], {"day": "2026-10-04", "list": self.lid, "paths": 5})
        g = blob["crawlers"]["Google"]
        self.assertEqual((g["kind"], g["requests"], g["listed"]), ("search", 7, 2))
        # /not-listed/ is a page outside the sitemap; /big.pdf is no page
        self.assertEqual((g["unlisted"], g["unlisted_requests"]), (1, 1))
        self.assertEqual((g["not_found"], g["redirects"], g["slow"], g["large"]), (1, 1, 1, 1))
        i = {f: k for k, f in enumerate(crawl_health.FIELDS)}
        row = g["paths"]["/pricing/"]
        self.assertEqual((row[i["requests"]], row[i["listed"]], row[i["slow"]],
                          row[i["ms"]]), (2, 1, 1, 1504))
        self.assertEqual(g["paths"]["/big.pdf"][i["max_bytes"]], 2_500_000)
        self.assertEqual(blob["crawlers"]["Bing"]["server_errors"], 1)
        self.assertEqual(blob["crawlers"]["GPTBot"]["kind"], "ai_training")
        self.assertEqual(blob["crawlers"]["ChatGPT-User"]["kind"], "ai_asked")
        self.assertNotIn("people", json.dumps(blob))
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err)

    def test_the_audit_catches_a_nudge_and_a_changed_list(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        blob = self.stored()
        i = crawl_health.FIELDS.index("not_found")
        blob["crawlers"]["Google"]["paths"]["/old-page"][i] = 0
        blob["crawlers"]["Google"]["not_found"] = 0
        self.put(blob)
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("crawl_health: Google /old-page: not_found", err)
        # the stored list edited by hand: it no longer hashes to its name
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        (self.box.root / "sitemaps" / f"{self.lid}.json").write_text(
            json.dumps({"paths": ["/", "/pricing/", "/features/", "/blog/one", "/x"]}))
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("does not hash to its name", err)

    def test_no_sitemap_is_not_recorded_never_zero(self):
        import shutil
        shutil.rmtree(self.box.root / "sitemaps")
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        blob = self.stored()
        self.assertIsNone(blob["sitemap"])
        g = blob["crawlers"]["Google"]
        self.assertEqual((g["listed"], g["unlisted"], g["unlisted_requests"]), (None, None, None))
        self.assertEqual(g["not_found"], 1)
        self.assertEqual(self.box.run("--today", "2026-10-06", "audit")[0], 0)
        self.assertEqual(self.box.run("--today", "2026-10-06", "dashboard")[0], 0)
        got = json.loads((self.box.root / "www" / "example.com" / "data" /
                          "crawl_health.json").read_text())
        self.assertIsNone(got["pages"])
        self.assertIsNone(got["sitemap"]["paths"])
        g = next(c for c in got["windows"]["30"]["crawlers"] if c["name"] == "Google")
        self.assertIsNone(g["coverage"])

    def test_the_folded_tail_is_recounted(self):
        with mock.patch.object(crawl_health, "KEEP", 1):
            self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        g = self.stored()["crawlers"]["Google"]
        self.assertEqual(g["folded"], 3)
        self.assertIn(crawl_health.OTHER, g["paths"])
        self.assertIn("/", g["paths"])           # a sitemap path is never folded
        self.assertEqual(self.box.run("--today", "2026-10-06", "audit")[0], 0)

    def test_the_data_file(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        _keep(self.box.root, "2026-10-06", ["/", "/pricing/", "/features/", "/blog/one",
                                            "/blog/two", "/new/"])
        self.assertEqual(self.box.run("--today", "2026-10-06", "dashboard")[0], 0)
        got = json.loads((self.box.root / "www" / "example.com" / "data" /
                          "crawl_health.json").read_text())
        self.assertEqual(got["sitemap"]["paths"], 6)
        w = got["windows"]["30"]
        g = next(c for c in w["crawlers"] if c["name"] == "Google")
        # judged by today's list: / and /pricing/ of 6
        self.assertEqual((g["listed"], g["orphans"], g["coverage"]), (2, 4, round(2 / 6, 4)))
        self.assertEqual(g["per_page"], 1.5)
        self.assertEqual(w["unlisted"]["rows"][0]["path"], "/not-listed/")
        self.assertEqual(w["unlisted"]["rows"][0]["by"], {"ChatGPT-User": 1, "Google": 1})
        self.assertEqual(w["problems"]["not_found"]["rows"][0],
                         {"path": "/old-page", "n": 1, "requests": 1, "by": {"Google": 1},
                          "last": "2026-10-05T08:03:00+00:00", "listed": False})
        self.assertEqual(w["problems"]["slow"]["rows"][0]["mean_ms"], 752)
        self.assertEqual(w["problems"]["large"]["rows"][0]["max_bytes"], 2_500_000)
        self.assertEqual(w["problems"]["server_errors"]["rows"][0]["by"], {"Bing": 1})
        pages = {r["path"]: r for r in got["pages"]["rows"]}
        self.assertEqual(pages["/pricing/"]["crawls"]["Google"],
                         [2, 2, "2026-10-05T08:02:00+00:00"])
        self.assertEqual(pages["/new/"]["crawls"], {})
        day = next(d for d in got["days"] if d["day"] == "2026-10-05")
        self.assertEqual(day["crawlers"]["Google"]["listed"], 2)
        self.assertEqual(day["crawlers"]["Google"]["sitemap"], 5)
        # 7 days: the 5th is within anchor-6 .. anchor
        self.assertEqual(got["windows"]["7"]["days"], 1)

    def test_the_live_audit_compares_it_too(self):
        import os
        stamp = datetime(2026, 10, 5, 23, tzinfo=UTC).timestamp()
        os.utime(self.box.root / "logs" / "access.log", (stamp, stamp))
        with mock.patch.object(sitemap, "_getter", lambda hosts: (lambda url: b"")):
            self.assertEqual(self.box.run("--today", "2026-10-05", "live")[0], 0)
        code, _, err = self.box.run("--today", "2026-10-05", "audit", "--live")
        self.assertEqual(code, 0, err)
        snap = json.loads((self.box.root / "live-example.com.json").read_text())
        self.assertEqual(snap["extras"]["crawl_health"]["crawlers"]["Google"]["listed"], 2)

    def test_verify_holds_the_sums(self):
        from skald.aggregate import summarise_views
        from skald import Classifier, read
        from skald.verify import check
        t = datetime(2026, 10, 5, 12, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text(_line(t, "/", GOOGLEBOT) + _line(t, "/a", GPTBOT))
            totals = summarise_views(read([path]), Classifier([]), 30, hosts=["example.com"],
                                     options={"sitemap": {"day": "2026-10-05", "list": "x",
                                                          "paths": frozenset({"/"})}})[0]
        self.assertEqual(check(totals), [])
        blob = totals.extras["crawl_health"]
        blob["crawlers"]["Google"]["listed"] = 0
        self.assertTrue(any(p.what == "crawl_health" for p in check(totals)))
        blob["crawlers"]["Google"]["listed"] = 1
        blob["crawlers"]["GPTBot"]["requests"] += 1
        self.assertTrue(check(totals))

    def test_a_view_has_none(self):
        from skald.aggregate import summarise_views
        from skald import Classifier, read
        t = datetime(2026, 10, 5, 12, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text(_line(t, "/blog/x", GOOGLEBOT))
            whole, views = summarise_views(read([path]), Classifier([]), 30,
                                           hosts=["example.com"],
                                           views={"blog": lambda h: h.path.startswith("/blog")})
        self.assertIn("crawl_health", whole.extras)
        self.assertNotIn("crawl_health", views["blog"].extras)


if __name__ == "__main__":
    unittest.main()
