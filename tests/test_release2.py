"""Release 2, batches 1-3: the Recent requests feed, the counting fixes the
real log showed, and crawler verification with fake-browser flags.

Every new rule has a "moves" test and a "stays" test, and the independent
audit recounts each new figure from the raw log (a day with every case in
it collects and audits clean; a stored figure nudged by one is caught).
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

from skald import bot_verify, requests_feed  # noqa: E402
from skald.classify import Classifier, Group, Tier  # noqa: E402
from skald.parse import PARSERS, Hit  # noqa: E402

from support import CHROME, GOOGLEBOT, GPTBOT, UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 10, 5)
NOON = datetime(2026, 10, 5, 12, tzinfo=UTC)
IMESSAGE = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/601.2.4 (KHTML, "
            "like Gecko) Version/9.0.1 Safari/601.2.4 facebookexternalhit/1.1 Facebot "
            "Twitterbot/1.0")
SLACK = "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)"
CLAUDE_CODE = "Claude-User (claude-code/2.1.292; +https://support.anthropic.com/)"
CLAUDE_USER = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0)"


def hit(url="/", agent=CHROME, address="203.0.113.5", status="200", method="GET",
        referrer="", when=NOON) -> Hit:
    return Hit(when, address, "example.com", method, url, status, referrer, agent)


def ranges(folder: Path, fetched: datetime | None = None, **lists) -> None:
    """Write stored lists as bot_verify keeps them."""
    folder.mkdir(parents=True, exist_ok=True)
    fetched = (fetched or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    for name, nets in lists.items():
        (folder / f"{name.replace('_', '-')}.json").write_text(json.dumps(
            {"source": "test", "fetched": fetched, "networks": nets, "error": None}))


def openai_lists(folder: Path, fetched=None) -> None:
    ranges(folder, fetched, openai_gptbot=["198.51.100.0/28"], openai_searchbot=["198.51.100.16/28"],
           openai_chatgpt_user=["198.51.100.32/28"])


# ------------------------------------------------------------- the parser

class TestParser(unittest.TestCase):
    def test_bytes_and_layout_are_read(self):
        got = PARSERS["nginx_extended"](line(NOON, path="/a"))
        self.assertEqual((got.size, got.fmt), (512, "nginx_extended"))
        old = PARSERS["nginx_combined"](
            '203.0.113.9 - - [05/Oct/2026:12:00:00 +0000] "GET / HTTP/1.1" 200 - "-" "x"')
        self.assertEqual((old.size, old.fmt), (None, "nginx_combined"))


class TestCountingFixes(unittest.TestCase):
    def test_files_that_are_not_pages(self):
        for path in ("/sitemap.xsl", "/guide.pdf", "/feed.rss", "/clip.mp4", "/data.csv"):
            with self.subTest(path=path):
                self.assertFalse(hit(path).is_page)
        self.assertTrue(hit("/pricing/").is_page)

    def test_a_next_payload_is_never_a_page_view(self):
        for url in ("/pricing/?_rsc=abc", "/?x=1&_rsc=1x", "/ca/fr/?_rsc=z"):
            with self.subTest(url=url):
                self.assertFalse(hit(url).is_page)

    def test_old_site_images_are_not_scanner_probes_when_listed(self):
        c = Classifier()
        c.legacy = ("/wp-content/uploads/",)
        v = c(hit("/wp-content/uploads/2025/09/x.png", referrer="https://images.google.com/"))
        self.assertEqual((v.group, v.probe, v.legacy), (Group.PEOPLE, False, True))
        self.assertTrue(c(hit("/wp-admin/install.php")).probe)
        self.assertTrue(c(hit("/wp-content/plugins/x.php")).probe)
        self.assertTrue(Classifier()(hit("/wp-content/uploads/x.png")).probe)

    def test_link_previews_are_bots_by_app(self):
        c = Classifier()
        for agent, app in ((IMESSAGE, "iMessage"), (SLACK, "Slack"),
                           ("facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
                            "Facebook"),
                           ("LinkedInBot/1.0 (compatible; Mozilla/5.0; Apache-HttpClient +http://www.linkedin.com)",
                            "LinkedIn"),
                           ("Twitterbot/1.0", "X (Twitter)"),
                           ("Mozilla/5.0 (Windows NT 6.1; WOW64) SkypeUriPreview Preview/0.5 "
                            "skype-url-preview@microsoft.com", "Microsoft Teams"),
                           ("WhatsApp/2.23.20.0 A", "WhatsApp")):
            with self.subTest(app=app):
                v = c(hit(agent=agent))
                self.assertEqual((v.group, v.engine), (Group.BOTS, f"link preview: {app}"))

    def test_page_speed_testers_are_bots(self):
        lighthouse = ("Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36 Chrome-Lighthouse")
        self.assertEqual(Classifier()(hit(agent=lighthouse)).group, Group.BOTS)
        self.assertEqual(Classifier()(hit(agent=CHROME)).group, Group.PEOPLE)


# --------------------------------------------------------- verification

class TestVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "ranges"

    def tearDown(self):
        self.tmp.cleanup()

    def classifier(self) -> Classifier:
        c = Classifier()
        c.verifier = bot_verify.Verifier(self.dir)
        return c

    def test_in_range_is_verified_and_out_of_range_is_a_bot_that_lied(self):
        openai_lists(self.dir)
        c = self.classifier()
        good = c(hit(agent=GPTBOT, address="198.51.100.3"))
        self.assertEqual((good.group, good.tier, good.verified),
                         (Group.ANSWER_ENGINE, Tier.TRAINING, "verified"))
        bad = c(hit(agent=GPTBOT, address="203.0.113.77"))
        self.assertEqual((bad.group, bad.engine, bad.verified, bad.claim),
                         (Group.BOTS, "claims to be GPTBot", "spoofed", "GPTBot"))

    def test_a_missing_or_stale_list_never_moves_a_fetch(self):
        c = self.classifier()           # no lists at all
        self.assertEqual(c(hit(agent=GPTBOT, address="203.0.113.77")).verified, "unverified")
        openai_lists(self.dir, datetime.now(timezone.utc) - timedelta(days=30))
        c = self.classifier()
        v = c(hit(agent=GPTBOT, address="203.0.113.77"))
        self.assertEqual((v.group, v.verified), (Group.ANSWER_ENGINE, "unverified"))

    def test_dns_decides_for_search_crawlers_outside_the_lists(self):
        ranges(self.dir, google_common=["192.0.2.0/28"])
        (self.dir / "dns.json").write_text(json.dumps({"answers": {
            "google|203.0.113.9": {"result": "spoofed", "name": "x.example.net",
                                   "checked": "2026-10-05T00:00:00+00:00"},
            "google|203.0.113.10": {"result": "verified", "name": "crawl.googlebot.com",
                                    "checked": "2026-10-05T00:00:00+00:00"}}}))
        c = self.classifier()
        self.assertEqual(c(hit(agent=GOOGLEBOT, address="192.0.2.4")).verified, "verified")
        self.assertEqual(c(hit(agent=GOOGLEBOT, address="203.0.113.10")).verified, "verified")
        self.assertEqual(c(hit(agent=GOOGLEBOT, address="203.0.113.11")).verified, "unverified")
        spoof = c(hit(agent=GOOGLEBOT, address="203.0.113.9"))
        self.assertEqual((spoof.group, spoof.engine), (Group.BOTS, "claims to be Googlebot"))

    def test_claude_code_runs_on_the_askers_machine_so_it_cannot_be_checked(self):
        ranges(self.dir, anthropic=["192.0.2.0/28"])
        c = self.classifier()
        self.assertEqual(c(hit(agent=CLAUDE_CODE, address="203.0.113.4")).verified, "unverified")
        self.assertEqual(c(hit(agent=CLAUDE_USER, address="203.0.113.4")).group, Group.BOTS)

    def test_no_owner_list_means_no_verdict(self):
        c = self.classifier()
        v = c(hit(agent="Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)"))
        self.assertEqual((v.group, v.verified), (Group.ANSWER_ENGINE, None))

    def test_hosting_network_browsers_are_flagged_not_moved(self):
        ranges(self.dir, hosting=["198.51.100.0/24"])
        c = self.classifier()
        v = c(hit(address="198.51.100.200"))
        self.assertEqual((v.group, v.flags), (Group.PEOPLE, ("hosting_network",)))
        self.assertEqual(c(hit(address="203.0.113.1")).flags, ())
        self.assertEqual(c(hit(agent="Mozilla/5.0")).flags, ("bare_mozilla",))

    def test_list_parsing_takes_vendor_and_ripe_shapes(self):
        self.assertEqual(bot_verify.parse_list(json.dumps(
            {"prefixes": [{"ipv4Prefix": "192.0.2.0/24"}, {"ipv6Prefix": "2001:db8::/32"}]})),
            ["192.0.2.0/24", "2001:db8::/32"])
        self.assertEqual(bot_verify.parse_list(json.dumps(
            {"data": {"prefixes": [{"prefix": "198.51.100.0/24"}]}})), ["198.51.100.0/24"])
        with self.assertRaises(ValueError):
            bot_verify.parse_list(b"<html>")

    def test_a_failed_fetch_keeps_the_last_good_list(self):
        def good(url):
            return json.dumps({"prefixes": [{"ipv4Prefix": "192.0.2.0/24"}]}).encode()

        def bad(url):
            raise OSError("unreachable")
        bot_verify.refresh_lists(self.dir, fetch=good, hosting=False)
        bot_verify.refresh_lists(self.dir, fetch=bad, hosting=False)
        kept = bot_verify.load_list(self.dir, "openai-gptbot")
        self.assertEqual(kept["networks"], ["192.0.2.0/24"])
        self.assertIn("unreachable", kept["error"])

    def test_dns_lookups_run_in_the_background_and_are_kept(self):
        added = bot_verify.resolve(self.dir, {("yandex", "192.0.2.1"), ("yandex", "192.0.2.2")},
                                   lookup=lambda a, s: ("verified", "x.yandex.ru")
                                   if a.endswith(".1") else ("spoofed", ""))
        self.assertEqual(added, {"verified": 1, "spoofed": 1})
        again = bot_verify.resolve(self.dir, {("yandex", "192.0.2.1")},
                                   lookup=lambda a, s: self.fail("looked up twice"))
        self.assertEqual(again, {})


class TestFanOut(unittest.TestCase):
    def burst(self, n: int, seconds: float = 0.5):
        from skald.classify import FanOut
        fan = FanOut()
        for i in range(n):
            fan(hit(address=f"192.0.2.{i + 1}", when=NOON + timedelta(seconds=i * seconds)))
        return fan.pairs()

    def test_ten_addresses_in_ten_seconds_are_flagged(self):
        self.assertEqual(len(self.burst(10)), 10)

    def test_nine_or_spread_out_are_not(self):
        self.assertEqual(self.burst(9), set())
        self.assertEqual(self.burst(10, seconds=2), set())


# ------------------------------------------------------- the feed rows

class TestFeedRows(unittest.TestCase):
    def test_personal_query_values_are_replaced(self):
        q = requests_feed.clean_query(
            "/x?utm_source=LinkedIn&email=a@b.co&gclid=Cj0KCQ123&_rsc=1x2y&id=12345678&step=1")
        self.assertEqual(q, "utm_source=LinkedIn&email=…&gclid=(id)&_rsc=1x2y&id=…&step=1")
        self.assertEqual(requests_feed.clean_path("/u/a@b.co/x"), "/u/…/x")

    def test_rules_in_words(self):
        c = Classifier(["MyCompanyCrawler"])
        cases = [
            (hit("/pricing/"), "people: page view", "page", True),
            (hit("/_next/static/a.js"), "people: asset", "asset", False),
            (hit("/pricing/?_rsc=1"), "people: Next.js payload (_rsc)", "rsc", False),
            (hit("/", referrer="https://chatgpt.com/"), "people: page view from ChatGPT",
             "page", True),
            (hit("/.env", status="404"), "bot: scanner probe", "not_found", False),
            (hit(agent=SLACK), "bot: link preview: Slack", "page", True),
            (hit(agent=GPTBOT), "AI training: GPTBot", "page", True),
            (hit(agent="MyCompanyCrawler/1"), "ours: MyCompanyCrawler", "page", True),
        ]
        for h, rule, kind, page in cases:
            with self.subTest(rule=rule):
                got = requests_feed.row(h, c(h), UTC, lambda ip: False, False)
                self.assertEqual((got["rule"], got["kind"], got["page_view"]), (rule, kind, page))
        excluded = requests_feed.row(hit(), None, UTC, lambda ip: False, False)
        self.assertEqual((excluded["group"], excluded["rule"]), ("excluded", "excluded: other host"))
        hidden = requests_feed.row(hit(), c(hit()), UTC, lambda ip: True, False)
        self.assertEqual(hidden["ip"], "(removed)")

    def test_the_feed_keeps_the_newest_and_counts_the_whole_window(self):
        c = Classifier()
        feed = requests_feed.Feed(NOON, cap=3)
        for i in range(-2, 5):
            h = hit(f"/p{i}", when=NOON + timedelta(minutes=i))
            feed(h, c(h))
        feed.excluded(hit("/api", when=NOON + timedelta(minutes=6)))
        got = feed.result(UTC, lambda ip: False, NOON, NOON + timedelta(hours=1), 6, 3, "x")
        self.assertEqual(got["total"], 6)
        self.assertEqual(got["by_group"], {"people": 5, "excluded": 1})
        self.assertEqual([r["path"] for r in got["rows"]], ["/api", "/p4", "/p3"])


# ------------------------------------------------- end to end, audited

class TestReleaseTwoDay(unittest.TestCase):
    """A day with every new case collects, verifies and audits clean."""

    def setUp(self):
        self.box = Sandbox()
        self.dir = self.box.root / "ranges"
        openai_lists(self.dir)
        ranges(self.dir, hosting=["192.0.2.128/25"])
        text = self.box.config.read_text().replace(
            "site:\n  name: example.com\n",
            "site:\n  name: example.com\n  legacy_paths: [/wp-content/uploads/]\n")
        self.box.config.write_text(text + f"bots:\n  ranges_dir: {self.dir}\n")
        t = datetime(2026, 10, 5, 15, tzinfo=UTC)
        lines = [
            line(t, "203.0.113.20", "/", CHROME),
            line(t, "203.0.113.20", "/", CHROME),                     # duplicate
            line(t + timedelta(seconds=5), "198.51.100.3", "/a", GPTBOT),        # verified
            line(t + timedelta(seconds=6), "203.0.113.99", "/b", GPTBOT),        # spoofed
            line(t + timedelta(seconds=7), "203.0.113.30", "/", SLACK),
            line(t + timedelta(seconds=8), "203.0.113.31", "/", IMESSAGE),
            line(t + timedelta(seconds=9), "203.0.113.32", "/wp-content/uploads/2025/x.png",
                 CHROME, status=404),
            line(t + timedelta(seconds=10), "192.0.2.200", "/pricing", CHROME),  # hosting
            line(t + timedelta(seconds=11), "203.0.113.40", "/sitemap.xsl", CHROME),
            line(t + timedelta(minutes=40), "203.0.113.41", "/", "Mozilla/5.0"),
            (f'203.0.113.56 - - [{(t + timedelta(minutes=50)):%d/%b/%Y:%H:%M:%S +0000}] '
             f'"GET /old HTTP/1.1" 200 10 "-" "{CHROME}"\n'),
        ]
        lines += [line(t + timedelta(hours=1, seconds=i), f"203.0.113.{100 + i}", "/", CHROME)
                  for i in range(10)]                                  # fan-out
        self.box.log(lines)

    def tearDown(self):
        self.box.close()

    def stored(self, kind: str) -> dict:
        with sqlite3.connect(self.box.db) as db:
            got = db.execute("SELECT data FROM day_extras WHERE site = 'example.com' AND "
                             "day = ? AND kind = ?", (DAY.isoformat(), kind)).fetchone()
        return json.loads(got[0])

    def test_collect_counts_and_the_audit_agrees(self):
        code, out, err = self.box.run("--today", "2026-10-06", "collect")
        self.assertEqual(code, 0, err)
        bots = self.stored("bots")
        self.assertEqual(bots["verification"]["GPTBot"],
                         {"group": "answer_engines", "method": "ranges", "verified": 1,
                          "unverified": 0, "spoofed": 1})
        self.assertEqual(bots["link_previews"], {"Slack": 1, "iMessage": 1})
        self.assertEqual(bots["fake_browsers"]["hosting_network"], {"requests": 1, "addresses": 1})
        self.assertEqual(bots["fake_browsers"]["bare_mozilla"], {"requests": 1, "addresses": 1})
        self.assertEqual(bots["fake_browsers"]["fan_out"], {"requests": 10, "addresses": 10})
        quality = self.stored("quality")
        self.assertEqual((quality["duplicates"], quality["old_format"]), (1, 1))
        self.assertEqual(len(quality["gaps"]), 1)
        nf = self.stored("not_found")
        self.assertFalse(next(r for r in nf if r["path"].startswith("/wp-content"))["probe"])
        with sqlite3.connect(self.box.db) as db:
            pages = dict(db.execute("SELECT name, n FROM counts WHERE site = 'example.com' "
                                    "AND kind = 'people_page'").fetchall())
        self.assertNotIn("/sitemap.xsl", pages)
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        self.assertEqual(self.stored("audit")["state"], "ok")

    def test_the_audit_catches_a_nudged_crawler_check(self):
        self.assertEqual(self.box.run("--today", "2026-10-06", "collect")[0], 0)
        bots = self.stored("bots")
        bots["verification"]["GPTBot"]["verified"] += 1
        with sqlite3.connect(self.box.db) as db:
            db.execute("UPDATE day_extras SET data = ? WHERE kind = 'bots' AND "
                       "site = 'example.com'", (json.dumps(bots),))
        code, out, err = self.box.run("--today", "2026-10-06", "audit")
        self.assertEqual(code, 1)
        self.assertIn("GPTBot: verified", err)
        self.assertEqual(self.stored("audit")["state"], "mismatch")


class TestFeedAcrossMidnight(unittest.TestCase):
    """Before 06:00 the window reaches into yesterday, judged over yesterday's
    whole day: a browser that read robots.txt at 23:50 is a crawler from its
    first request."""

    def test_yesterdays_part_is_judged_like_collect(self):
        from skald import cli
        box = Sandbox()
        try:
            late = datetime(2026, 10, 5, 23, 40, tzinfo=UTC)
            box.log([line(late - timedelta(hours=6), "203.0.113.70", "/early", CHROME),
                     line(late, "203.0.113.70", "/a", CHROME),
                     line(late + timedelta(minutes=10), "203.0.113.70", "/robots.txt", CHROME),
                     line(late + timedelta(minutes=30), "203.0.113.71", "/b", CHROME)])
            args = cli.parser().parse_args(["--config", str(box.config), "live"])
            ctx = cli.Context(args)
            ctx.now = datetime(2026, 10, 6, 0, 30, tzinfo=UTC)
            ctx.out = ctx.err = lambda *a: None
            self.assertEqual(cli.cmd_live(ctx), 0)
            feed = requests_feed.load(requests_feed.path_for(ctx.live_dir, "example.com"))
            rules = {r["path"]: r["rule"] for r in feed["rows"]}
            self.assertNotIn("/early", rules)
            self.assertTrue(rules["/a"].startswith("bot: browser-like crawler"))
            self.assertEqual(rules["/b"], "people: page view")
            self.assertEqual(feed["by_group"], {"bots": 2, "people": 1})
            got = json.loads((box.root / "www" / "example.com" / "data" /
                              "requests.json").read_text())
            self.assertEqual((got["state"], got["total"], got["shown"]), ("ok", 3, 3))
            code, out, err = box.run("audit", "--live")
            self.assertEqual(code, 0, err)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()


class TestQualityAndViews(unittest.TestCase):
    """quality.json holds the day's input checks, the audit's verdict and the
    jobs' last runs; a view's requests.json holds its own paths only."""

    def test_quality_file_and_view_feed(self):
        from unittest import mock
        box = Sandbox(views=["{name: Guides, path_prefix: /guides/}"])
        try:
            day = datetime(2026, 10, 5, 12, tzinfo=UTC)
            today = datetime(2026, 10, 6, 11, 0, tzinfo=UTC)
            box.log([line(day, "203.0.113.20", "/"), line(day, "203.0.113.20", "/"),
                     line(day + timedelta(hours=2), "203.0.113.21", "/guides/a"),
                     line(today - timedelta(minutes=30), "203.0.113.22", "/guides/b"),
                     line(today - timedelta(minutes=20), "203.0.113.23", "/pricing")])
            self.assertEqual(box.run("--today", "2026-10-06", "collect")[0], 0)
            self.assertEqual(box.run("--today", "2026-10-06", "audit")[0], 0)
            with mock.patch("skald.cli._now", return_value=today):
                code, out, err = box.run("live")
            self.assertEqual(code, 0, err)
            data = box.root / "www" / "example.com"
            q = json.loads((data / "data" / "quality.json").read_text())
            d = next(x for x in q["days"] if x["day"] == "2026-10-05")
            self.assertEqual((d["duplicates"], d["lines"], d["audit"]["state"]), (1, 3, "ok"))
            self.assertEqual(len(d["gaps"]), 1)
            self.assertEqual(q["today"]["lines"], 2)
            self.assertIsNotNone(q["today"]["clock_skew_s"])
            self.assertIsNotNone(q["runs"]["live"]["last_ok"])
            self.assertEqual(q["runs"]["run-daily"]["expected_every_min"], 1440)
            whole = json.loads((data / "data" / "requests.json").read_text())
            view = json.loads((data / "guides" / "data" / "requests.json").read_text())
            self.assertEqual((whole["total"], view["total"]), (2, 1))
            self.assertEqual([r["path"] for r in view["rows"]], ["/guides/b"])
            self.assertEqual(sum(view["by_group"].values()), view["total"])
        finally:
            box.close()


class TestSmallYaml(unittest.TestCase):
    def test_false_is_false_without_pyyaml(self):
        from skald.config import tiny_yaml
        got = tiny_yaml("alerts:\n  enabled: false\n  mail: true\n  only_on_host: \"\"\n")
        self.assertEqual(got["alerts"], {"enabled": False, "mail": True, "only_on_host": ""})
