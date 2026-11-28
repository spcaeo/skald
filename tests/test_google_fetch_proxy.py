"""SKALD-51: Google's fetch proxy, named, never counted as an AI read.

On 23 Nov 2026 Gemini, asked to open a page live, fetched it once with the bare user agent
"Google" from rate-limited-proxy-<ip>.google.com, an address on none of Google's published
crawler lists. The same proxy fetches for Sheets (IMPORTXML, IMPORTDATA), Apps Script and feed
readers, so the request cannot say it was Gemini. It was an unnamed bot. Palak's choice
(2026-11-26): keep it in bots, under a name of its own, checked by reverse DNS like Googlebot:

  * reverse DNS in google.com that resolves back (or no answer yet): "Google fetch proxy
    (Gemini, Sheets, Apps Script)"
  * reverse DNS that is not Google's: "claims to be Google fetch proxy (...)"
  * a scanner probe or a scanner's address stays a scanner, as before

Both counting roads (classify.py and the audit's Judge) give the same name, and verify-bots
looks up the addresses. Test data: 192.0.2.0/24 and 203.0.113.0/24 (RFC 5737).
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_release2, bot_verify  # noqa: E402
from skald.classify import (GOOGLE_PROXY, GOOGLE_PROXY_AGENT, Classifier,  # noqa: E402
                                   Group)
from skald.parse import Hit  # noqa: E402

from support import UTC, Sandbox, line  # noqa: E402

PROXY = "192.0.2.195"        # reverse DNS: Google's (stored answer "verified")
FAKE = "203.0.113.9"         # reverse DNS: not Google's (stored answer "spoofed")
NEW = "203.0.113.20"         # no answer yet
SCAN = "192.0.2.77"          # asked for /.env too: a scanner on every line that day
DAY = date(2026, 11, 23)
TODAY = "2026-11-24"
FAKED = "claims to be " + GOOGLE_PROXY


def dns_folder(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "dns.json").write_text(json.dumps({"answers": {
        f"google-proxy|{PROXY}": {"result": "verified",
                                  "name": "rate-limited-proxy-192-0-2-195.google.com"},
        f"google-proxy|{FAKE}": {"result": "spoofed", "name": "host.example.com"}}}))
    return folder


def hit(address: str, agent: str = "Google", path: str = "/install/") -> Hit:
    return Hit(datetime(2026, 11, 23, 8, 59, tzinfo=timezone.utc), address, "example.com",
               "GET", path, "200", "-", agent)


class TheName(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.judge = Classifier()
        self.judge.verifier = bot_verify.Verifier(dns_folder(Path(self.tmp.name)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_bare_agent_from_google_is_the_named_proxy(self):
        got = self.judge(hit(PROXY))
        self.assertEqual((got.group, got.engine, got.verified), (Group.BOTS, GOOGLE_PROXY, "verified"))
        self.assertIsNone(got.tier, "a bot, never an AI read")

    def test_not_checked_yet_keeps_the_name(self):
        got = self.judge(hit(NEW))
        self.assertEqual((got.group, got.engine, got.verified), (Group.BOTS, GOOGLE_PROXY, "unverified"))

    def test_no_lists_at_all_keeps_the_name(self):
        got = Classifier()(hit(NEW))
        self.assertEqual((got.group, got.engine, got.verified), (Group.BOTS, GOOGLE_PROXY, None))

    def test_not_google_is_a_bot_that_lied(self):
        got = self.judge(hit(FAKE))
        self.assertEqual((got.group, got.engine, got.verified), (Group.BOTS, FAKED, "spoofed"))
        # Not a crawler claim: it never enters the crawler checks table (bots.json).
        self.assertEqual(got.claim, "")

    def test_a_probe_is_still_a_probe(self):
        got = self.judge(hit(PROXY, path="/.env"))
        self.assertEqual((got.group, got.engine, got.probe), (Group.BOTS, "", True))

    def test_only_the_bare_word(self):
        self.assertEqual(GOOGLE_PROXY_AGENT, "Google")
        for agent in ("Google Chrome", "GoogleBot", "google", "Mozilla/5.0 Google",
                      "Google-Read-Aloud", "FeedFetcher-Google"):
            with self.subTest(agent=agent):
                self.assertNotIn(GOOGLE_PROXY, self.judge(hit(PROXY, agent)).engine)


class BothChecks(unittest.TestCase):
    def test_the_main_check_and_the_audits_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = dns_folder(Path(tmp))
            main = bot_verify.Verifier(folder)
            audit = audit_release2.Checks({"bots": {"ranges_dir": str(folder)}},
                                          datetime.now(timezone.utc))
            for check in (main.status, audit.verdict):
                with self.subTest(road=check.__qualname__):
                    self.assertEqual(check("Google", PROXY, "Google"), "verified")
                    self.assertEqual(check("Google", FAKE, "Google"), "spoofed")
                    self.assertEqual(check("Google", NEW, "Google"), "unverified")

    def test_a_cdn_edge_keeps_the_name_on_both_roads(self):
        # An edge's reverse DNS is the CDN's, never Google's: no proof either way (SKALD-17).
        from test_cdn_addresses import EDGE, lists
        with tempfile.TemporaryDirectory() as tmp:
            folder = lists(Path(tmp))
            (folder / "dns.json").write_text(json.dumps({"answers": {
                f"google-proxy|{EDGE}": {"result": "spoofed"}}}))
            audit = audit_release2.Checks({"bots": {"ranges_dir": str(folder)}},
                                          datetime.now(timezone.utc))
            self.assertEqual(audit.verdict("Google", EDGE, "Google"), "cdn")
            judge = Classifier()
            judge.verifier = bot_verify.Verifier(folder)
            got = judge(hit(EDGE))
            self.assertEqual((got.engine, got.verified), (GOOGLE_PROXY, "cdn"))

    def test_the_proxy_is_looked_up_after_the_real_crawlers(self):
        # A run looks up at most 200 addresses: many proxy ones never crowd out YandexBot.
        wanted = {("google-proxy", f"198.51.100.{i}") for i in range(1, 201)}
        wanted |= {("google-proxy", "203.0.113.1"), ("yandex", "203.0.113.2")}
        asked = []
        with tempfile.TemporaryDirectory() as tmp:
            bot_verify.resolve(Path(tmp), wanted, budget_s=5,
                               lookup=lambda a, s: (asked.append(a), ("verified", "x"))[1])
        self.assertEqual(len(asked), 200)
        self.assertIn("203.0.113.2", asked)

    def test_checked_by_reverse_dns_in_google_com(self):
        self.assertEqual(bot_verify.method_of(bot_verify.vendor_of("Google")), "dns")
        lists, suffixes = bot_verify.VENDORS["google-proxy"]
        self.assertEqual((lists, suffixes), ((), ("google.com",)))

    def test_the_proxys_reverse_name_passes_and_others_do_not(self):
        real_by_addr, real_info = bot_verify.socket.gethostbyaddr, bot_verify.socket.getaddrinfo
        names = {PROXY: "rate-limited-proxy-192-0-2-195.google.com.", FAKE: "host.example.com"}
        bot_verify.socket.gethostbyaddr = lambda a: (names[a], [], [a])
        bot_verify.socket.getaddrinfo = lambda n, p: [(2, 1, 6, "", (PROXY, 0))]
        try:
            suffixes = bot_verify.VENDORS["google-proxy"][1]
            self.assertEqual(bot_verify._reverse_forward(PROXY, suffixes),
                             ("verified", "rate-limited-proxy-192-0-2-195.google.com"))
            self.assertEqual(bot_verify._reverse_forward(FAKE, suffixes)[0], "spoofed")
        finally:
            bot_verify.socket.gethostbyaddr = real_by_addr
            bot_verify.socket.getaddrinfo = real_info

    def test_verify_bots_looks_the_addresses_up(self):
        box = Sandbox()
        try:
            folder = Path(box.root / "ranges")
            folder.mkdir()
            box.config.write_text(box.config.read_text() + f"bots:\n  ranges_dir: {folder}\n")
            now = datetime.now(timezone.utc).replace(microsecond=0)
            box.log([line(now - timedelta(minutes=5), PROXY, "/", "Google"),
                     line(now - timedelta(minutes=4), FAKE, "/", "Google Chrome")])
            asked = []
            real = bot_verify.resolve
            bot_verify.resolve = lambda folder, wanted, now, budget: (
                asked.extend(sorted(wanted)), {})[1]
            try:
                code, out, err = box.run("verify-bots", "--dns-only")
            finally:
                bot_verify.resolve = real
            self.assertEqual(code, 0, err)
            self.assertEqual(asked, [("google-proxy", PROXY)])
        finally:
            box.close()


class BothRoads(unittest.TestCase):
    def test_counted_under_its_name_and_the_audit_agrees(self):
        box = Sandbox()
        try:
            folder = dns_folder(box.root / "ranges")
            box.config.write_text(box.config.read_text() + f"bots:\n  ranges_dir: {folder}\n")
            at = datetime(DAY.year, DAY.month, DAY.day, 8, 59, tzinfo=UTC)
            box.log([line(at, PROXY, "/install/?probe=gm-k3x9", "Google"),
                     line(at + timedelta(minutes=1), PROXY, "/pricing/", "Google"),
                     line(at + timedelta(minutes=2), NEW, "/", "Google"),
                     line(at + timedelta(minutes=3), FAKE, "/", "Google"),
                     line(at + timedelta(minutes=4), SCAN, "/.env", "Google", status=404),
                     line(at + timedelta(minutes=5), SCAN, "/", "Google")])
            code, _, err = box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err)
            db = sqlite3.connect(str(box.db))
            try:
                def blob(kind):
                    return json.loads(db.execute(
                        "SELECT data FROM day_extras WHERE site = ? AND day = ? AND kind = ?",
                        ("example.com", DAY.isoformat(), kind)).fetchone()[0])
                bots = blob("crawler_cost")["groups"]["bots"]
                checks = blob("bots")["verification"]
            finally:
                db.close()
            self.assertEqual(bots[GOOGLE_PROXY]["requests"], 3)
            self.assertEqual(bots[FAKED]["requests"], 1)
            self.assertEqual(bots["(scanner probes)"]["requests"], 1)
            self.assertEqual(bots["scanner (asked for secret or config files)"]["requests"], 1)
            self.assertNotIn("Google", bots, "no unnamed short-name row left")
            for name in ("Google", GOOGLE_PROXY, FAKED):
                self.assertNotIn(name, checks, "not a crawler claim in the checks table")
            code, out, err = box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err + out)
            self.assertIn("all match", out)
        finally:
            box.close()


class TheAlerts(unittest.TestCase):
    def test_no_new_assistant_alert_for_the_proxy(self):
        # Its name says Gemini, but it is a bot by choice: "add it to the name lists" is wrong.
        from skald.alerts import _named
        got = _named({}, {"minutes": {"08:59": {"name:" + GOOGLE_PROXY: 5,
                                                 "name:Gemini-Helper": 4}}})
        self.assertEqual(got, {"Gemini-Helper": 4})


class TheIcon(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_googles_mark_not_geminis(self):
        js = Path(__file__).resolve().parent / "js" / "google-proxy-icon.mjs"
        got = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=120)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        self.assertIn("google-proxy-icon: all passed", got.stdout)


class TheFeed(unittest.TestCase):
    def test_recent_requests_say_the_rule(self):
        from skald.requests_feed import rule_of
        got = Classifier()(hit(NEW))
        self.assertEqual(rule_of(hit(NEW), got, "page"), f"bot: {GOOGLE_PROXY}")


if __name__ == "__main__":
    unittest.main()
