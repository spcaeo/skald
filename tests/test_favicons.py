"""Referrer favicons: fetched from each site itself, kept same-origin.

Pinned: ico and png are stored, favicons.json lists only stored hosts; SVG,
HTML, oversize and fake images are refused; IPs, private names, app ids and
the site's own hosts are never fetched; the per-run limit holds; icons are
fetched again after 30 days (failures after 7); a redirect to another site is
refused. No network: the fetch is a fake.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import favicons  # noqa: E402

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
ICO = b"\x00\x00\x01\x00" + b"\x01" * 40
CONFIG = {"site": {"hosts": ["example.com", "www.example.com"]}}


class Fake:
    """url -> (status, content type, body); records what was asked."""

    def __init__(self, pages: dict) -> None:
        self.pages, self.asked = pages, []

    def __call__(self, url, timeout, limit):
        self.asked.append(url)
        if url not in self.pages:
            raise urllib.error.URLError("no route")
        status, ctype, body = self.pages[url]
        return status, ctype, body[:limit + 1]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.out, self.live = self.root / "www", self.root / "lib"
        self.live.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def run_it(self, hosts, fake, now=NOW, limit=10):
        return favicons.refresh(CONFIG, self.out, "example.com", hosts, now, limit=limit,
                                fetch=fake, live_dir=self.live, convert=False)

    @property
    def data(self) -> Path:
        return self.out / "example.com" / "data"

    def manifest(self) -> dict:
        return json.loads((self.data / "favicons.json").read_text())


class TestStore(Base):
    def test_ico_and_png_are_stored_and_listed(self):
        fake = Fake({"https://news.example.org/favicon.ico": (200, "image/x-icon", ICO),
                     "https://blog.example.net/favicon.ico": (404, "text/html", b""),
                     "https://blog.example.net/": (200, "text/html",
                                                   b'<link rel="icon" href="/i/fav.png">'),
                     "https://blog.example.net/i/fav.png": (200, "image/png", PNG)})
        got = self.run_it(["news.example.org", "blog.example.net", "gone.example.com"], fake)
        self.assertEqual(got, {"fetched": 2, "failed": 1, "skipped": 0, "cached": 0})
        self.assertEqual((self.data / "favicons" / "news.example.org.ico").read_bytes(), ICO)
        self.assertEqual((self.data / "favicons" / "blog.example.net.png").read_bytes(), PNG)
        m = self.manifest()
        self.assertEqual(m["schema_version"], 1)
        self.assertEqual(m["hosts"]["news.example.org"], "favicons/news.example.org.ico")
        self.assertEqual(m["hosts"]["www.news.example.org"], "favicons/news.example.org.ico")
        self.assertNotIn("gone.example.com", m["hosts"])

    def test_bad_icons_are_refused(self):
        big = b"\x89PNG\r\n\x1a\n" + b"\x00" * 60_000
        fake = Fake({"https://a.example.org/favicon.ico": (200, "image/svg+xml", b"<svg/>"),
                     "https://b.example.org/favicon.ico": (200, "text/html", b"<html>"),
                     "https://c.example.org/favicon.ico": (200, "image/png", big),
                     "https://d.example.org/favicon.ico": (200, "image/png", b"GIF8nope....")})
        got = self.run_it(["a.example.org", "b.example.org", "c.example.org", "d.example.org"],
                          fake)
        self.assertEqual((got["fetched"], got["failed"]), (0, 4))
        self.assertEqual(self.manifest()["hosts"], {})

    def test_page_icons_on_other_sites_or_svg_are_ignored(self):
        html = (b'<link rel="icon" href="https://cdn.other.net/f.png">'
                b'<link rel="shortcut icon" href="/f.svg">'
                b'<link rel="apple-touch-icon" href="https://www.e.example.org/t.png">')
        self.assertEqual(favicons.icon_links(html.decode(), "https://e.example.org/"),
                         ["https://www.e.example.org/t.png"])


class TestWhoIsAsked(Base):
    def test_ips_private_names_app_ids_and_our_own_hosts_are_never_fetched(self):
        fake = Fake({})
        got = self.run_it(["203.0.113.4", "[2001:db8::1]", "localhost", "intranet",
                           "printer.local", "nas.home", "com.google.android.gm",
                           "example.com", "www.example.com", "bad_host.com", "(none)"], fake)
        self.assertEqual(fake.asked, [])
        self.assertEqual(got["skipped"], 11)

    def test_the_limit_holds_and_the_rest_wait(self):
        fake = Fake({f"https://s{i}.example.org/favicon.ico": (200, "image/png", PNG)
                     for i in range(5)})
        got = self.run_it([f"s{i}.example.org" for i in range(5)], fake, limit=2)
        self.assertEqual(got["fetched"], 2)
        got = self.run_it([f"s{i}.example.org" for i in range(5)], fake, limit=2)
        self.assertEqual((got["fetched"], got["cached"]), (2, 2))

    def test_fetched_again_after_a_month_failures_after_a_week(self):
        ok = Fake({"https://n.example.org/favicon.ico": (200, "image/png", PNG)})
        self.run_it(["n.example.org", "x.example.org"], ok)
        self.assertEqual(self.run_it(["n.example.org", "x.example.org"], ok,
                                     NOW + timedelta(days=6))["fetched"], 0)
        later = self.run_it(["x.example.org"], ok, NOW + timedelta(days=8))
        self.assertEqual(later["failed"], 1)            # tried again after a week
        month = self.run_it(["n.example.org"], ok, NOW + timedelta(days=31))
        self.assertEqual(month["fetched"], 1)

    def test_it_never_raises(self):
        def broken(*a):
            raise RuntimeError("boom")
        got = favicons.refresh(CONFIG, self.out, "example.com", ["n.example.org"], NOW,
                               fetch=broken, live_dir=self.live)
        self.assertEqual(got["failed"], 1)


class TestRedirects(unittest.TestCase):
    def follow(self, start: str, to: str):
        handler = favicons.SameSiteRedirects(start)
        req = urllib.request.Request(f"https://{start}/favicon.ico")
        return handler.redirect_request(req, None, 301, "Moved", {}, to)

    def test_only_the_www_twin_over_https(self):
        self.assertIsNotNone(self.follow("linkedin.com", "https://www.linkedin.com/favicon.ico"))
        with self.assertRaises(urllib.error.HTTPError):
            self.follow("linkedin.com", "https://static.licdn.com/favicon.ico")
        with self.assertRaises(urllib.error.HTTPError):
            self.follow("linkedin.com", "http://www.linkedin.com/favicon.ico")
        self.assertEqual(favicons.SameSiteRedirects.max_redirections, 2)


class TestHosts(unittest.TestCase):
    def test_hosts_from_the_snapshot(self):
        snap = {"breakdowns": {"by": {"referrer": {"google.com": 3, "(none)": 9,
                                                   "(this site)": 2}}},
                "extras": {"campaigns": {"rows": {"ref_host": [{"name": "news.example.org"},
                                                               {"name": "(none)"}]}}}}
        self.assertEqual(favicons.hosts_from(snap), ["google.com", "news.example.org"])


if __name__ == "__main__":
    unittest.main()
