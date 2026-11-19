"""SKALD-41: a page Chrome's prefetch proxy fetched, drawn by the phone.

Google Search on Android Chrome fetches a result's HTML through Chrome's
private prefetch proxy, from Google's network. When the person opens it, the
browser fetches the page's files from its own address. The render test
(rendering.py) joins a page and its files on one address and agent, so
neither half rendered and the whole visit went to bots (a live site, 18 Nov
2026).

Pinned here: with Google's published proxy list (bot_verify, stored like the
crawler lists), a page line from a proxy address joins the same agent's files
fetched from another address within the render window, when those files name
that page as their referrer. The page then counts as that browser's: one
visit, one reader, the browser's own country. A proxy page nobody opened,
another browser's files, files for another page, or files too late stay as
they were. Both counting roads (window.py and audit.py) agree.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, bot_verify  # noqa: E402
from skald.window import analyse_window, day_window  # noqa: E402

from support import UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
ANDROID = ("Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/142.0.0.0 Mobile Safari/537.36")
DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/142.0.0.0 Safari/537.36")
PROXY = "2001:db8:7:805::6"          # inside the test list below
PHONE = "2001:db8:1::5"
GOOGLE = "https://www.google.com/"
GEOFEED = (b"# <pre>\n# Chrome Prefetch Proxy Geofeed (test copy)\n#\n"
           b"2001:db8:7:805::/64,IN,,,\n192.0.2.128/28,JP,,,\n# </pre>")


def at(hour, minute=0, second=0):
    return datetime(DAY.year, DAY.month, DAY.day, hour, minute, second, tzinfo=UTC)


def files(when, address=PHONE, page="https://example.com/", agent=ANDROID, country="IN"):
    """The page's own files, as the browser fetches them: referrer = the page."""
    return [line(when, address, "/_next/static/css/app.css", agent, page, country=country),
            line(when, address, "/_next/static/chunks/main.js", agent, page, country=country)]


def proxied(when, path="/", agent=ANDROID):
    """The page's HTML, fetched by the proxy (its country is the proxy's)."""
    return line(when, PROXY, path, agent, GOOGLE, country="US")


def ranges(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    bot_verify.refresh_lists(folder, datetime(2026, 10, 5, tzinfo=timezone.utc),
                             fetch=lambda url: GEOFEED if "prefetch" in url else b"{}",
                             hosting=False)
    return folder


def count(lines, with_list=True):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "access.log"
        path.write_text("".join(lines))
        config = {"site": {"hosts": ["example.com"]}}
        if with_list:
            config["bots"] = {"ranges_dir": str(ranges(Path(tmp) / "ranges"))}
        start, end = day_window(DAY, UTC)
        return analyse_window(config, start, end, paths=[path])


def people(totals):
    g = totals.groups.get(Group.PEOPLE)
    return (g.hits, g.visits, g.readers) if g else (0, 0, 0)


def bots(totals):
    g = totals.groups.get(Group.BOTS)
    return g.hits if g else 0


class TheList(unittest.TestCase):

    def test_the_geofeed_is_read_and_kept_like_the_crawler_lists(self):
        self.assertEqual(bot_verify.parse_list(GEOFEED), ["2001:db8:7:805::/64", "192.0.2.128/28"])
        with tempfile.TemporaryDirectory() as tmp:
            folder = ranges(Path(tmp))
            stored = json.loads((folder / "chrome-prefetch-proxy.json").read_text())
            self.assertIn("gstatic.com/chrome/prefetchproxy/", stored["source"])
            check = bot_verify.Verifier(folder)
            self.assertTrue(check.prefetch_proxy(PROXY))
            self.assertTrue(check.prefetch_proxy("192.0.2.130"))
            self.assertFalse(check.prefetch_proxy(PHONE))
            # Not a crawler list: no claim is checked against it.
            self.assertEqual(check.crawler_at(PROXY), "")

    def test_an_error_page_is_no_list_and_the_last_good_copy_stays(self):
        with self.assertRaises(ValueError):
            bot_verify.parse_list(b"<html><body>Service unavailable</body></html>")
        with self.assertRaises(ValueError):
            bot_verify.parse_list(b"# only comments\n")
        with tempfile.TemporaryDirectory() as tmp:
            folder = ranges(Path(tmp))
            bot_verify.refresh_lists(folder, fetch=lambda url: b"<html>oops</html>",
                                     hosting=False)
            self.assertTrue(bot_verify.Verifier(folder).prefetch_proxy(PROXY))


class OneVisit(unittest.TestCase):

    def test_the_proxys_page_and_the_phones_files_are_one_visit(self):
        totals = count([proxied(at(8, 13, 43)), *files(at(8, 13, 44))])
        self.assertEqual(people(totals), (3, 1, 1))
        self.assertEqual(bots(totals), 0)
        # Counted as the phone's: its country, not the proxy's.
        self.assertEqual(dict(totals.groups[Group.PEOPLE].countries), {"IN": 1})

    def test_without_the_list_both_halves_stay_bots(self):
        totals = count([proxied(at(8, 13, 43)), *files(at(8, 13, 44))], with_list=False)
        self.assertEqual(people(totals), (0, 0, 0))
        self.assertEqual(bots(totals), 3)

    def test_a_page_the_proxy_fetched_and_nobody_opened_stays_a_bot(self):
        # The phone opened another result: its own page and files, for "/".
        totals = count([proxied(at(9), "/pricing/"),
                        line(at(9, 0, 1), PHONE, "/", ANDROID, GOOGLE, country="IN"),
                        *files(at(9, 0, 2))])
        self.assertEqual(people(totals), (3, 1, 1))
        self.assertEqual(bots(totals), 1)

    def test_a_browser_that_fetched_the_page_itself_does_not_take_the_proxys(self):
        # Someone else, same agent, opened "/" on their own a second later:
        # its files are that page's, and the proxy's "/" stays a bot.
        totals = count([proxied(at(9)),
                        line(at(9, 0, 1), PHONE, "/", ANDROID, GOOGLE, country="IN"),
                        *files(at(9, 0, 2))])
        self.assertEqual(people(totals), (3, 1, 1))
        self.assertEqual(bots(totals), 1)

    def test_another_browsers_files_do_not_join(self):
        totals = count([proxied(at(9)), *files(at(9, 0, 1), agent=DESKTOP)])
        self.assertEqual(people(totals), (0, 0, 0))

    def test_files_too_late_or_from_another_proxy_address_do_not_join(self):
        totals = count([proxied(at(9)), *files(at(9, 2))])                 # two minutes on
        self.assertEqual(people(totals), (0, 0, 0))
        totals = count([proxied(at(10)), *files(at(10, 0, 1), address="192.0.2.131")])
        self.assertEqual(people(totals), (0, 0, 0))


class BothRoads(unittest.TestCase):

    def test_the_day_is_stored_and_the_audit_agrees(self):
        box = Sandbox()
        try:
            text = box.config.read_text().replace("  require_rendering: false\n", "")
            folder = ranges(box.root / "ranges")
            box.config.write_text(text + f"bots:\n  ranges_dir: {folder}\n")
            box.log([proxied(at(8, 13, 43)), *files(at(8, 13, 44)),
                     proxied(at(11), "/pricing/"),                     # never opened
                     line(at(12), "203.0.113.10", "/", DESKTOP, country="GB"),
                     *files(at(12, 0, 1), "203.0.113.10", agent=DESKTOP, country="GB")])
            code, _, err = box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err)
            import sqlite3
            db = sqlite3.connect(str(box.db))
            try:
                row = db.execute("SELECT hits, visits, readers FROM groups WHERE site = ? "
                                 "AND day = ? AND grp = 'people'",
                                 ("example.com", DAY.isoformat())).fetchone()
            finally:
                db.close()
            self.assertEqual(tuple(row), (6, 2, 2))
            code, out, err = box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err + out)
            self.assertIn("all match", out)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
