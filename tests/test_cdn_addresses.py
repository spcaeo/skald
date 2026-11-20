"""SKALD-17 and SKALD-21: a CDN's own addresses in a site's log.

A site behind Cloudflare whose server logs Cloudflare's address (not CF-Connecting-IP) has
the edge's address on every line. Found 17 Nov 2026: on two live sites 98.5% and 98.9% of
lines were Cloudflare's. Skald did not know those addresses, so:

  * a real crawler coming through Cloudflare (OAI-SearchBot, meta-externalagent, and
    Googlebot by DNS) failed its owner's address check and was judged "spoofed": moved to
    bots as "claims to be ...", out of the crawler's own figures;

Now Skald keeps the CDN's published ranges with the crawler lists (bot_verify CDN_LISTS,
"cdn-cloudflare", replaced only when both files arrive), and a crawler claim from a CDN
address its owner's list does not hold is checked "cdn": counted as the crawler, neither
verified nor called an impostor, on both counting roads; and no DNS lookup is spent on it.

Test data: 198.51.100.0/24 and 2001:db8:cf::/48 (documentation ranges) stand in for the CDN.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_release2, bot_verify  # noqa: E402

from support import UTC, Sandbox, line  # noqa: E402

CDN_V4 = b"198.51.100.0/24\n"
CDN_V6 = b"2001:db8:cf::/48\n"
EDGE = "198.51.100.7"                     # a CDN edge in the fake range
OWN = "192.0.2.5"                         # inside the crawler owners' fake lists
ELSEWHERE = "203.0.113.9"                 # neither
DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
SEARCHBOT = ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; "
             "OAI-SearchBot/1.0; +https://openai.com/searchbot")
GOOGLEBOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


def fetcher(v4=CDN_V4, v6=CDN_V6):
    def fetch(url):
        if url.endswith("ips-v4"):
            if isinstance(v4, Exception):
                raise v4
            return v4
        if url.endswith("ips-v6"):
            if isinstance(v6, Exception):
                raise v6
            return v6
        return json.dumps({"prefixes": [{"ipv4Prefix": "192.0.2.0/28"}]}).encode()
    return fetch


def lists(folder: Path, when: datetime | None = None) -> Path:
    """Every crawler list fresh (192.0.2.0/28), and the CDN's ranges."""
    folder.mkdir(parents=True, exist_ok=True)
    bot_verify.refresh_lists(folder, when or datetime.now(timezone.utc), fetch=fetcher(),
                             hosting=False)
    return folder


class TheList(unittest.TestCase):
    def test_both_files_make_one_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = lists(Path(tmp))
            got = json.loads((folder / "cdn-cloudflare.json").read_text())
            self.assertEqual(got["networks"], ["198.51.100.0/24", "2001:db8:cf::/48"])
            self.assertIn("cloudflare.com/ips-v4", got["source"])
            check = bot_verify.Verifier(folder)
            self.assertEqual(check.cdn(EDGE), "Cloudflare")
            self.assertEqual(check.cdn("2001:db8:cf::1"), "Cloudflare")
            self.assertEqual(check.cdn(ELSEWHERE), "")
            self.assertIn("cdn-cloudflare", bot_verify.ALL_LISTS)

    def test_half_a_list_never_replaces_the_good_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = lists(Path(tmp))
            done = bot_verify.refresh_lists(folder, fetch=fetcher(v6=OSError("timed out")),
                                            hosting=False)
            self.assertTrue(done["cdn-cloudflare"].startswith("failed"))
            self.assertEqual(bot_verify.Verifier(folder).cdn("2001:db8:cf::1"), "Cloudflare")

    def test_no_list_no_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(bot_verify.Verifier(Path(tmp)).cdn(EDGE), "")
            self.assertIsNone(bot_verify.Verifier(Path(tmp)).cdn_known())


class TheCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = lists(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_crawler_through_the_cdn_cannot_be_checked_on_both_roads(self):
        main = bot_verify.Verifier(self.folder)
        audit = audit_release2.Checks({"bots": {"ranges_dir": str(self.folder)}}, datetime.now(timezone.utc))
        for check in (main.status, audit.verdict):
            with self.subTest(road=check.__qualname__):
                self.assertEqual(check("OAI-SearchBot", EDGE, SEARCHBOT), "cdn")
                self.assertEqual(check("OAI-SearchBot", OWN, SEARCHBOT), "verified")
                self.assertEqual(check("OAI-SearchBot", ELSEWHERE, SEARCHBOT), "spoofed")

    def test_a_cdn_address_beats_a_dns_answer_for_it(self):
        # Reverse DNS of an edge is the CDN's name, never googlebot.com: not a lie by the crawler.
        (self.folder / "dns.json").write_text(json.dumps({"answers": {
            f"google|{EDGE}": {"result": "spoofed"}, f"google|{ELSEWHERE}": {"result": "spoofed"}}}))
        main = bot_verify.Verifier(self.folder)
        audit = audit_release2.Checks({"bots": {"ranges_dir": str(self.folder)}}, datetime.now(timezone.utc))
        for check in (main.status, audit.verdict):
            with self.subTest(road=check.__qualname__):
                self.assertEqual(check("Googlebot", EDGE, GOOGLEBOT), "cdn")
                self.assertEqual(check("Googlebot", ELSEWHERE, GOOGLEBOT), "spoofed")

    def test_no_dns_lookup_is_spent_on_a_cdn_address(self):
        box = Sandbox()
        try:
            text = box.config.read_text()
            box.config.write_text(text + f"bots:\n  ranges_dir: {self.folder}\n")
            now = datetime.now(timezone.utc).replace(microsecond=0)
            box.log([line(now - timedelta(minutes=5), EDGE, "/", GOOGLEBOT),
                     line(now - timedelta(minutes=4), ELSEWHERE, "/", GOOGLEBOT)])
            asked = []
            real = bot_verify.resolve
            bot_verify.resolve = lambda folder, wanted, now, budget: (
                asked.extend(sorted(wanted)), {})[1]
            try:
                code, out, err = box.run("verify-bots", "--dns-only")
            finally:
                bot_verify.resolve = real
            self.assertEqual(code, 0, err)
            self.assertEqual(asked, [("google", ELSEWHERE)])
        finally:
            box.close()


class TheAssistants(unittest.TestCase):
    """AI & bots > Assistants: Repeat and visitors are not known through a CDN edge."""

    def test_repeat_and_visitors_are_not_known_through_a_cdn(self):
        from skald.ai_activity import AIEvents
        from skald.classify import Group, Tier, Verdict
        from skald.parse import Hit
        events = AIEvents(b"k" * 32, cdn=lambda ip: "Cloudflare" if ip == EDGE else "")
        at = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
        for i, ip in enumerate((EDGE, EDGE, ELSEWHERE)):
            hit = Hit(at + timedelta(minutes=i), ip, "example.com", "GET", f"/p{i}", "200", "-",
                      "Mozilla/5.0 ChatGPT-User/1.0")
            events(hit, Verdict(Group.ANSWER_ENGINE, Tier.ASKED, "ChatGPT-User"))
        with tempfile.TemporaryDirectory() as tmp:
            db = sqlite3.connect(str(Path(tmp) / "h.sqlite"))
            from skald import visitors
            db.executescript(visitors.SCHEMA)
            got = events.result(timezone.utc, db, "example.com", date(2026, 10, 5))
            db.close()
        by_ip = {e["ip"]: e for e in got["events"]}
        self.assertEqual((by_ip[EDGE]["repeat"], by_ip[EDGE]["first_seen"], by_ip[EDGE]["cdn"]),
                         (None, None, "Cloudflare"))
        self.assertIs(by_ip[ELSEWHERE]["repeat"], False)
        self.assertNotIn("cdn", by_ip[ELSEWHERE])
        self.assertEqual((got["by_name"]["ChatGPT-User"]["visitors"],
                          got["by_name"]["ChatGPT-User"]["repeat"]), (None, None))


class BothRoads(unittest.TestCase):
    def test_the_real_crawler_through_the_cdn_is_counted_as_itself_and_the_audit_agrees(self):
        box = Sandbox()
        try:
            folder = lists(box.root / "ranges")
            box.config.write_text(box.config.read_text() + f"bots:\n  ranges_dir: {folder}\n")
            at = datetime(DAY.year, DAY.month, DAY.day, 9, tzinfo=UTC)
            box.log([line(at + timedelta(minutes=i), EDGE, f"/p{i}", SEARCHBOT) for i in range(5)]
                    + [line(at + timedelta(hours=1), ELSEWHERE, "/x", SEARCHBOT)])
            code, _, err = box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err)
            db = sqlite3.connect(str(box.db))
            try:
                blob = json.loads(db.execute(
                    "SELECT data FROM day_extras WHERE site = ? AND day = ? AND kind = 'bots'",
                    ("example.com", DAY.isoformat())).fetchone()[0])
            finally:
                db.close()
            got = blob["verification"]["OAI-SearchBot"]
            self.assertEqual((got["cdn"], got["unverified"], got["verified"], got["spoofed"]),
                             (5, 0, 0, 1), "5 through the CDN counted as the crawler, 1 impostor")
            code, out, err = box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err + out)
            self.assertIn("all match", out)
        finally:
            box.close()


class OldDays(unittest.TestCase):
    def test_crawler_claims_counted_without_the_list_are_audited_without_it(self):
        # 2.55 counted these as "claims to be OAI-SearchBot"; once the list exists, an audit
        # of that stored day must still match (it was counted without the rule).
        box = Sandbox()
        try:
            folder = lists(box.root / "ranges")
            (folder / "cdn-cloudflare.json").unlink()
            box.config.write_text(box.config.read_text() + f"bots:\n  ranges_dir: {folder}\n")
            at = datetime(DAY.year, DAY.month, DAY.day, 9, tzinfo=UTC)
            box.log([line(at + timedelta(minutes=i), EDGE, f"/p{i}", SEARCHBOT) for i in range(5)])
            code, _, err = box.run("--today", TODAY, "collect", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err)
            lists(folder)
            code, out, err = box.run("--today", TODAY, "audit", "--day", DAY.isoformat())
            self.assertEqual(code, 0, err + out)
            self.assertIn("all match", out)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
