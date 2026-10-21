"""The independent recount: a stored day counted again from the raw log by a
separate road, and compared with history.

What is pinned: a collected day recounts exactly, breakdowns included; a
stored figure nudged by one is caught; --withhold and run-daily then keep the
day off the dashboard and out of the mail; and the audit's own output names
no address and no user agent.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit, mailer  # noqa: E402
from skald.store import History  # noqa: E402

from support import CHROME, SECRETS, UTC, Sandbox, day_lines, line  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"

IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/26.0 Mobile/15E148 Safari/604.1")
ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like "
           "Gecko) Chrome/129.0.0.0 Mobile Safari/537.36")
FIREFOX = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0"


def busy_day() -> list[str]:
    """The standard day, plus readers on three more devices, a visit split by
    a long gap, a 404, a form post, a server error, a campaign, and an old
    combined-format line with no host and no country."""
    t = datetime(DAY.year, DAY.month, DAY.day, 15, tzinfo=UTC)
    out = day_lines(DAY, 4)
    out += [
        line(t, "203.0.113.50", "/pricing", IPHONE, "https://www.google.com/", country="CA"),
        line(t + timedelta(minutes=1), "203.0.113.50", "/_next/static/a.js", IPHONE,
             "https://example.com/pricing", country="CA"),
        line(t + timedelta(minutes=2), "203.0.113.51",
             "/?utm_source=LinkedIn&utm_medium=social&utm_campaign=Launch", ANDROID,
             country="DE"),
        line(t + timedelta(minutes=3), "203.0.113.52", "/guides/alpha", FIREFOX,
             "https://news.example.org/post", country="-"),
        # The same reader 2 hours later: a second visit, a second reader.
        line(t + timedelta(hours=2), "203.0.113.52", "/guides/beta", FIREFOX, country="-"),
        line(t + timedelta(minutes=4), "203.0.113.53", "/missing", CHROME, status=404),
        line(t + timedelta(minutes=5), "203.0.113.54", "/broken", CHROME, status=502),
        (f'{(t + timedelta(minutes=6)).isoformat()} 203.0.113.55 example.com '
         f'"POST /contact HTTP/2.0" 303 0 "https://example.com/contact" "{CHROME}" '
         f'0.120 cc=US ray=-\n'),
        (f'203.0.113.56 - - [{(t + timedelta(minutes=7)):%d/%b/%Y:%H:%M:%S +0000}] '
         f'"GET /old HTTP/1.1" 200 10 "-" "{CHROME}"\n'),
    ]
    return out


class AuditCase(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.box.log(busy_day())

    def tearDown(self):
        self.box.close()

    def collect(self):
        code, out, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err)

    def tamper(self, sql: str, *args):
        db = sqlite3.connect(str(self.box.db))
        with db:
            db.execute(sql, args)
        db.close()


class TestRecountMatches(AuditCase):

    def test_a_collected_day_recounts_exactly(self):
        self.collect()
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok: 2026-10-05", out)
        self.assertIn("all match", out)

    def test_the_recount_sees_the_breakdowns(self):
        from skald.config import load_config
        from support import UTC as zone
        figures = audit.recount(load_config(self.box.config), DAY, zone,
                                [self.box.root / "logs" / "access.log"])
        by = figures["by"]
        self.assertEqual(figures["readers"], sum(by["country"].values()))
        self.assertEqual(by["country"]["CA"], 1)
        self.assertEqual(by["country"]["Unknown"], 3)      # "-" twice, no cc= once
        self.assertEqual(by["browser"]["Safari"], 1)
        self.assertEqual(by["browser"]["Firefox"], 2)
        self.assertEqual(by["device"]["Mobile"], 2)
        self.assertEqual(by["source"]["Search engine"], 1)
        self.assertEqual(by["campaign"]["linkedin / social / launch"], 1)
        self.assertEqual(figures["statuses"]["people"]["404"], 1)
        self.assertEqual(figures["server_errors"], 1)
        self.assertEqual(figures["posts"]["people"], 1)

    def test_an_ai_tag_behind_a_search_referrer_is_an_assistant_on_both_roads(self):
        # CLASSIFICATION.md rule 10: the referrer's host is an assistant's, OR
        # AI_UTM matches the URL. A link tagged utm_source=chatgpt that arrives
        # with a google.com referrer is a citation, in the count and the audit.
        from skald.config import load_config
        t = datetime(DAY.year, DAY.month, DAY.day, 18, tzinfo=UTC)
        self.box.log(busy_day() + [
            line(t, "203.0.113.90", "/guides/gamma?utm_source=chatgpt.com", CHROME,
                 "https://www.google.com/", country="FR"),
            line(t + timedelta(minutes=1), "203.0.113.91", "/?utm_source=perplexity", CHROME,
                 "https://example.com/", country="FR")])
        self.collect()
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        self.assertIn("all match", out)
        figures = audit.recount(load_config(self.box.config), DAY, UTC,
                                [self.box.root / "logs" / "access.log"])
        ai = figures["by"]["source"]["AI assistant"]
        with History(self.box.db) as h:
            stored = dict(h.db.execute(
                "SELECT name, n FROM counts WHERE site = 'example.com' AND day = ? AND "
                "kind = 'reader_source'", (DAY.isoformat(),)).fetchall())
        self.assertEqual(stored.get("AI assistant"), ai)
        self.box.log(busy_day())                 # the same day without the two tagged visits
        figures = audit.recount(load_config(self.box.config), DAY, UTC,
                                [self.box.root / "logs" / "access.log"])
        self.assertEqual(figures["by"]["source"]["AI assistant"], ai - 2)

    def test_a_day_not_collected_is_said_so(self):
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("not stored", err)

    def test_a_day_from_before_the_breakdowns_audits_what_it_has(self):
        self.collect()
        self.tamper("UPDATE days SET breakdowns = NULL")
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err)
        self.assertIn("breakdowns not recorded", out)


class TestMismatchesAreCaught(AuditCase):

    def test_a_country_one_off_is_caught(self):
        self.collect()
        self.tamper("UPDATE counts SET n = n + 1 WHERE kind = 'reader_country' "
                    "AND name = 'CA' AND site = 'example.com'")
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        self.assertIn("readers by country: CA", err)
        self.assertIn("rows sum to", err)
        with History(self.box.db) as h:       # without --withhold, untouched
            self.assertEqual(h.state("example.com", DAY), "ok")

    def test_a_group_one_off_is_caught_and_withheld(self):
        self.collect()
        self.tamper("UPDATE groups SET hits = hits + 1 WHERE grp = 'bots' "
                    "AND site = 'example.com'")
        code, out, err = self.box.run("--today", TODAY, "audit", "--withhold")
        self.assertEqual(code, 1)
        self.assertIn("bots: requests", err)
        self.assertIn("now withheld", err)
        with History(self.box.db) as h:
            self.assertEqual(h.state("example.com", DAY), "withheld")
            problems = h.db.execute("SELECT problems FROM days").fetchone()[0]
        self.assertIn("audit: bots: requests", problems)
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", TODAY, "mail", "--daily")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED", err)
        smtp.assert_not_called()

    def test_its_output_names_no_address_and_no_agent(self):
        self.collect()
        self.tamper("UPDATE counts SET n = n + 5 WHERE kind LIKE 'reader_%'")
        self.tamper("UPDATE groups SET visits = visits + 1")
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 1)
        for text in (out, err):
            self.assertNotIn("203.0.113.", text)
            self.assertNotIn("198.51.100.", text)
            self.assertNotIn("Mozilla", text)


class TestRunDaily(AuditCase):

    def test_a_good_day_passes_the_audit_and_is_mailed(self):
        with mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", TODAY, "run-daily")
        self.assertEqual(code, 0, err)
        self.assertIn("audit ok", out)
        self.assertEqual(smtp.return_value.send_message.call_count, 1)

    def test_a_mismatch_stops_before_the_dashboard_and_the_mail(self):
        real = audit.recount

        def off_by_one(*args, **kwargs):
            figures = real(*args, **kwargs)
            figures["by"]["browser"]["Firefox"] += 1
            return figures

        with mock.patch.object(audit, "recount", off_by_one), \
                mock.patch.dict(os.environ, SECRETS), \
                mock.patch.object(mailer.smtplib, "SMTP") as smtp:
            code, out, err = self.box.run("--today", TODAY, "run-daily")
        self.assertEqual(code, 1)
        self.assertIn("stopped at 'audit'", err)
        self.assertIn("readers by browser: Firefox", err)
        self.assertFalse((self.box.root / "www").exists())
        smtp.assert_not_called()
        with History(self.box.db) as h:
            self.assertEqual(h.state("example.com", DAY), "withheld")


class TestIndependence(AuditCase):
    """The recount is a second implementation, not a second call of the first."""

    def test_it_shares_only_the_name_lists(self):
        import ast
        source = Path(audit.__file__).read_text()
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.level:
                imported |= {(node.module, a.name) for a in node.names}
        allowed = {("classify", n) for n in ("AI_ASKED", "AI_REFERRER_HOSTS", "AI_TRAINING",
                                             "AI_UTM", "OTHER_BOT", "OWN_AGENTS", "PROBE", "PROBE_QUERY",
                                             "SEARCH_ENGINE")}
        allowed |= {("store", "History"), ("store", "READER_KINDS")}
        # The audit's own visits recount, itself independent (test_visits_audit).
        allowed |= {(None, "audit_visits"), (None, "audit_extras")}
        # Release 2's recount (crawler checks, quality), tested the same way
        # in test_release2_audit.
        allowed |= {(None, "audit_release2")}
        # Its own rendering rule, tested the same way in test_rendering.
        allowed |= {(None, "audit_rendered")}
        # Its own speed rule, tested the same way in test_too_fast.
        allowed |= {(None, "audit_too_fast")}
        # Its own labels, moved out whole (below), and the phase 4 recounts'
        # registry (audit_more.py), whose modules follow the same rule.
        allowed |= {("audit_labels", n) for n in (
            "_bare", "_host_of", "browser_of", "campaign_of", "device_of", "referrer_of",
            "source_of", "status_of", "system_of")}
        allowed |= {(None, "audit_more")}
        # Its own reader of Vercel and Netlify drain lines, which imports
        # nothing from the package (test_drains).
        allowed |= {(None, "audit_drains")}
        # The GeoIP file is data, like the name lists: a line with no country
        # of its own gets the one the file has for its address, on both roads.
        # The MaxMind-format reader is tested against its own fixtures
        # (test_conversions_store) and, live, against nginx's cc= field.
        allowed |= {("conversions.geo", "country"), ("conversions.geo", "database")}
        # Its own city of a visit (logs.city_db), which shares only the
        # file's reader (test_city_lookup).
        allowed |= {(None, "audit_cities")}
        # Its own line reader, moved out whole (audit_lines.py, below).
        allowed |= {("audit_lines", n) for n in (
            "_COMBINED", "_EXTENDED", "_LAST_QUOTED", "_OWN", "_PREFETCH_KEY", "_REQUEST",
            "_RID", "Line", "_byte_count", "_line", "_named_host", "_prefetch", "_read",
            "_secs", "_tail_seconds", "line_hit", "log_files", "raw_lines")}
        self.assertLessEqual(imported, allowed)

    def test_its_line_reader_imports_only_its_drain_reader(self):
        import ast
        from skald import audit_lines
        tree = ast.parse(Path(audit_lines.__file__).read_text())
        imported = {(n.module, a.name) for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(imported, {(None, "audit_drains")})

    def test_its_cities_share_only_the_file_reader(self):
        import ast
        from skald import audit_cities
        tree = ast.parse(Path(audit_cities.__file__).read_text())
        imported = {(n.module, a.name) for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(imported, {("conversions.geo", "reader")})

    def test_its_labels_import_nothing_from_the_package(self):
        import ast
        from skald import audit_labels
        tree = ast.parse(Path(audit_labels.__file__).read_text())
        imported = {(n.module, a.name) for n in ast.walk(tree)
                    if isinstance(n, ast.ImportFrom) and n.level for a in n.names}
        self.assertEqual(imported, {("audit", "Line")})        # a type, under TYPE_CHECKING

    def test_its_labels_agree_with_the_package_on_known_agents(self):
        from skald import dimensions
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import test_breakdowns as tb
        agents = [CHROME, IPHONE, ANDROID, FIREFOX, tb.IPHONE_SAFARI, tb.LINKEDIN_APP,
                  tb.SAMSUNG_TABLET, tb.EDGE, tb.FIREFOX_LINUX, tb.CHROMEBOOK,
                  tb.FB_ANDROID, "Opera/9.80 (Windows NT 6.1) Presto/2.12", "",
                  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"]
        for agent in agents:
            with self.subTest(agent=agent[:40]):
                self.assertEqual((audit.browser_of(agent), audit.system_of(agent),
                                  audit.device_of(agent)), dimensions.agent_labels(agent))

    def test_the_breakdown_fixture_recounts_exactly(self):
        import test_breakdowns as tb
        box = Sandbox()
        try:
            box.log(tb.mixed())
            self.assertEqual(box.run("--today", "2026-10-06", "collect")[0], 0)
            code, out, err = box.run("--today", "2026-10-06", "audit")
            self.assertEqual(code, 0, err)
            self.assertIn("all match", out)
        finally:
            box.close()

    def test_mask_hides_addresses(self):
        self.assertEqual(audit.mask("from 203.0.113.9 and 2001:db8::1 ok"),
                         "from [address] and [address] ok")


class TestLive(AuditCase):

    def test_today_so_far_recounts_the_snapshot(self):
        from support import NY  # noqa: F401
        today = date(2026, 10, 7)
        box = Sandbox()
        try:
            noon = datetime(2026, 10, 7, 11, tzinfo=UTC)
            box.log(day_lines(today, 5) + [
                line(noon, "203.0.113.70", "/pricing", IPHONE, "https://lnkd.in/x", country="CA"),
                line(noon + timedelta(minutes=1), "203.0.113.71", "/nope", ANDROID,
                     status=404, country="DE")])
            stamp = datetime(2026, 10, 7, 23, tzinfo=UTC).timestamp()
            os.utime(box.root / "logs" / "access.log", (stamp, stamp))
            self.assertEqual(box.run("--today", "2026-10-07", "live")[0], 0)
            code, out, err = box.run("--today", "2026-10-07", "audit", "--live")
            self.assertEqual(code, 0, err)
            self.assertIn("audit ok: live", out)
            snap = box.root / "live-example.com.json"
            text = snap.read_text().replace('"CA": 1', '"CA": 2')
            snap.write_text(text)
            code, out, err = box.run("--today", "2026-10-07", "audit", "--live")
            self.assertEqual(code, 1)
            self.assertIn("readers by country: CA", err)
        finally:
            box.close()


if __name__ == "__main__":
    unittest.main()
