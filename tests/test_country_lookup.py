"""A line's country from the GeoIP file when the log carries none, on both
roads, and the audit's own reader of Caddy's JSON log.

What is pinned: a combined or Caddy line gets its address's country from
`logs.country_db`; a country the line carries itself always wins; an address
the file does not know stays Unknown; the audit recounts a Caddy site and
agrees with the main road, countries included; `logs.country_db` serves
lead hooks too, and `conversions.country_db` still works alone.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import audit_drains  # noqa: E402
from skald.conversions import geo  # noqa: E402
from skald.parse import PARSERS, read  # noqa: E402

from conversions_support import mmdb  # noqa: E402
from support import CHROME, UTC, Sandbox, line  # noqa: E402

DAY = date(2026, 10, 5)
TODAY = "2026-10-06"
NOON = datetime(DAY.year, DAY.month, DAY.day, 12, tzinfo=UTC)
NETS = {"203.0.113.0/24": "CA", "198.51.100.0/24": "DE"}


def combined(when: datetime, address: str, path: str = "/", referrer: str = "-") -> str:
    return (f'{address} - - [{when:%d/%b/%Y:%H:%M:%S +0000}] "GET {path} HTTP/1.1" 200 '
            f'512 "{referrer}" "{CHROME}"\n')


def caddy(when: datetime, address: str, path: str = "/", status=200, referrer: str = "",
          client_ip: str = "", country: str = "") -> str:
    headers = {"User-Agent": [CHROME]}
    if referrer:
        headers["Referer"] = [referrer]
    if country:
        headers["Cf-Ipcountry"] = [country]
    request = {"remote_ip": address, "remote_port": "51234", "proto": "HTTP/2.0",
               "method": "GET", "host": "example.com", "uri": path, "headers": headers}
    if client_ip:
        request["client_ip"] = client_ip
    return json.dumps({"level": "info", "ts": when.timestamp(), "logger": "http.log.access",
                       "msg": "handled request", "request": request, "status": status,
                       "size": 512}) + "\n"


class Case(unittest.TestCase):

    def setUp(self):
        self.box = Sandbox()
        self.db = self.box.root / "country.mmdb"
        self.db.write_bytes(mmdb(NETS))
        text = self.box.config.read_text()
        self.box.config.write_text(text.replace(
            "  format: auto\n", f"  format: auto\n  country_db: {self.db}\n", 1))

    def tearDown(self):
        self.box.close()

    def countries(self) -> dict:
        db = sqlite3.connect(str(self.box.db))
        try:
            return dict(db.execute(
                "SELECT name, n FROM counts WHERE site = 'example.com' AND day = ? "
                "AND kind = 'people_country_visits'", (DAY.isoformat(),)).fetchall())
        finally:
            db.close()

    def collect_and_audit(self):
        code, out, err = self.box.run("--today", TODAY, "collect")
        self.assertEqual(code, 0, err + out)
        code, out, err = self.box.run("--today", TODAY, "audit")
        self.assertEqual(code, 0, err + out)
        return out


class TestReader(Case):

    def test_a_line_without_a_country_gets_its_address_country(self):
        path = self.box.log([combined(NOON, "203.0.113.7"),
                             combined(NOON, "198.51.100.9"),
                             combined(NOON, "192.0.2.5")])
        got = [h.country for h in read([path], "auto", geo=str(self.db))]
        self.assertEqual(got, ["CA", "DE", ""])

    def test_the_line_s_own_country_wins(self):
        path = self.box.log([line(NOON, "203.0.113.7", country="US")])
        self.assertEqual([h.country for h in read([path], "auto", geo=str(self.db))],
                         ["US"])

    def test_without_a_file_nothing_is_looked_up(self):
        path = self.box.log([combined(NOON, "203.0.113.7")])
        self.assertEqual([h.country for h in read([path], "auto")], [""])
        missing = str(self.box.root / "nowhere.mmdb")
        self.assertEqual([h.country for h in read([path], "auto", geo=missing)], [""])


class TestCaddyMainRoad(unittest.TestCase):

    def test_client_ip_is_the_client_when_caddy_has_trusted_proxies(self):
        hit = PARSERS["caddy_json"](caddy(NOON, "198.51.100.1", client_ip="203.0.113.7"))
        self.assertEqual(hit.address, "203.0.113.7")

    def test_a_record_without_a_three_digit_status_or_uri_is_not_a_request(self):
        self.assertIsNone(PARSERS["caddy_json"](caddy(NOON, "203.0.113.7", status=0)))
        self.assertIsNone(PARSERS["caddy_json"](caddy(NOON, "203.0.113.7", path="")))

    def test_an_empty_header_list_is_no_value(self):
        raw = json.loads(caddy(NOON, "203.0.113.7"))
        raw["request"]["headers"]["Referer"] = []
        self.assertEqual(PARSERS["caddy_json"](json.dumps(raw)).referrer, "")


class TestCaddyAuditRoad(unittest.TestCase):

    def test_the_audit_reads_a_caddy_line_by_its_own_code(self):
        got = audit_drains.fields(caddy(NOON, "203.0.113.7", "/docs?x=1",
                                        referrer="https://www.google.com/", country="gb"))
        self.assertEqual(got["address"], "203.0.113.7")
        self.assertEqual(got["url"], "/docs?x=1")
        self.assertEqual(got["status"], "200")
        self.assertEqual(got["referrer"], "https://www.google.com/")
        self.assertEqual(got["agent"], CHROME)
        self.assertEqual(got["country"], "GB")
        self.assertEqual(got["when"], NOON.astimezone(timezone.utc))

    def test_the_two_roads_agree_on_what_is_not_a_request(self):
        for raw in (caddy(NOON, "203.0.113.7", status=0), caddy(NOON, "203.0.113.7", path=""),
                    caddy(NOON, "", path="/")):
            self.assertIsNone(audit_drains.fields(raw))
            self.assertIsNone(PARSERS["caddy_json"](raw))


class TestEndToEnd(Case):

    def test_a_combined_log_site_stores_countries_and_the_audit_agrees(self):
        self.box.log([combined(NOON + timedelta(minutes=i), f"203.0.113.{10 + i}",
                               referrer="https://www.google.com/") for i in range(3)]
                     + [combined(NOON, "198.51.100.20"), combined(NOON, "192.0.2.30")])
        self.collect_and_audit()
        # History keeps known countries only; the rest is shown as Unknown.
        self.assertEqual(self.countries(), {"CA": 3, "DE": 1})

    def test_a_caddy_site_is_audited_and_agrees(self):
        self.box.log([caddy(NOON + timedelta(minutes=i), f"203.0.113.{10 + i}", "/guide",
                            referrer="https://www.bing.com/") for i in range(2)]
                     + [caddy(NOON, "198.51.100.20", country="FR"),
                        caddy(NOON + timedelta(minutes=5), "192.0.2.30", "/about")])
        out = self.collect_and_audit()
        self.assertNotIn("caddy_json", out)
        # The logged CF-IPCountry wins over the file's DE; 192.0.2.30 is Unknown.
        self.assertEqual(self.countries(), {"CA": 2, "FR": 1})


class TestDatabaseSetting(unittest.TestCase):

    def test_logs_wins_then_conversions(self):
        self.assertEqual(geo.database({"logs": {"country_db": "/a.mmdb"},
                                       "conversions": {"country_db": "/b.mmdb"}}), "/a.mmdb")
        self.assertEqual(geo.database({"conversions": {"country_db": "/b.mmdb"}}), "/b.mmdb")
        self.assertIsNone(geo.database({"logs": {"country_db": ""}}))
        self.assertIsNone(geo.database({}))


if __name__ == "__main__":
    unittest.main()


class TestHostFields(unittest.TestCase):
    """A combined layout may end with "$host"; Caddy may log host:port."""

    def combined_with(self, tail: str) -> str:
        return (f'203.0.113.7 - - [{NOON:%d/%b/%Y:%H:%M:%S +0000}] "GET / HTTP/1.1" 200 512 '
                f'"-" "{CHROME}"{tail}\n')

    def test_the_trailing_host_is_read_on_both_roads(self):
        from skald import audit
        cases = {' 0.010 0.010 "www.example.com"': "www.example.com",
                 ' 0.000 - "Example.com:8080"': "example.com",
                 ' 0.000 - "198.51.100.1"': "",          # an address: not a host name
                 ' "198.51.100.1, 10.0.0.2"': "",         # an X-Forwarded-For list
                 ' 0.004 - "-"': "",
                 '': ""}
        for tail, want in cases.items():
            raw = self.combined_with(tail)
            self.assertEqual(PARSERS["nginx_combined"](raw).host, want, tail)
            self.assertEqual(audit.line_hit(raw).host, want, tail)

    def test_the_response_time_after_the_agent_is_read(self):
        self.assertEqual(PARSERS["nginx_combined"](
            self.combined_with(' 0.010 0.010 "www.example.com"')).request_time, 0.010)

    def test_a_caddy_port_is_dropped_on_both_roads(self):
        raw = json.loads(caddy(NOON, "203.0.113.7"))
        raw["request"]["host"] = "example.com:443"
        raw = json.dumps(raw)
        self.assertEqual(PARSERS["caddy_json"](raw).host, "example.com")
        self.assertEqual(audit_drains.fields(raw)["host"], "example.com")


class TestNotModified(Case):
    """A 304 is the browser showing its cached copy: a page view."""

    def test_a_cached_landing_page_keeps_the_visit_s_source(self):
        from skald import audit
        t = NOON
        raw = [line(t, "203.0.113.40", "/", referrer="https://www.google.com/", country="GB"),
               line(t + timedelta(seconds=1), "203.0.113.40", "/_next/static/app.js",
                    referrer="https://example.com/", country="GB"),
               line(t + timedelta(minutes=1), "203.0.113.40", "/pricing",
                    referrer="https://example.com/", country="GB")]
        raw[0] = raw[0].replace('" 200 512 ', '" 304 0 ')
        self.assertTrue(PARSERS["nginx_extended"](raw[0]).is_page)
        self.assertTrue(audit.is_page(audit.line_hit(raw[0])))
        self.box.log(raw)
        self.collect_and_audit()
        db = sqlite3.connect(str(self.box.db))
        try:
            got = dict(db.execute(
                "SELECT name, n FROM counts WHERE day = ? AND kind = 'reader_source'",
                (DAY.isoformat(),)).fetchall())
        finally:
            db.close()
        self.assertEqual(got, {"Search engine": 1})

    def test_a_redirect_is_still_not_a_page(self):
        raw = line(NOON, "203.0.113.41", "/old").replace('" 200 512 ', '" 301 0 ')
        self.assertFalse(PARSERS["nginx_extended"](raw).is_page)


class TestCredit(unittest.TestCase):
    """DB-IP's free file asks for its credit wherever its countries show."""

    def test_a_dbip_file_gets_dbip_s_credit_unless_one_is_set(self):
        import tempfile
        from skald.config import country_credit
        with tempfile.TemporaryDirectory() as tmp:
            dbip = Path(tmp) / "dbip.mmdb"
            dbip.write_bytes(mmdb(NETS, kind="DBIP-Country-Lite"))
            other = Path(tmp) / "other.mmdb"
            other.write_bytes(mmdb(NETS))
            self.assertEqual(country_credit({"logs": {"country_db": str(dbip)}}),
                             ("IP Geolocation by DB-IP", "https://db-ip.com"))
            self.assertIsNone(country_credit({"logs": {"country_db": str(other)}}))
            self.assertIsNone(country_credit({}))
            own = {"logs": {"country_db": str(dbip)},
                   "report": {"country_credit": "Countries: our CDN"}}
            self.assertEqual(country_credit(own), ("Countries: our CDN", None))


class TestOwnFetcher(Case):
    """Skald's hourly robots.txt fetch is our own traffic on both roads."""

    def test_the_robots_check_is_ours_not_a_bot(self):
        self.box.log([line(NOON, "203.0.113.60", "/robots.txt", agent="site-version-check/1"),
                      line(NOON, "203.0.113.61", "/", referrer="https://www.google.com/")])
        self.collect_and_audit()
        db = sqlite3.connect(str(self.box.db))
        try:
            got = dict(db.execute("SELECT grp, hits FROM groups WHERE day = ?",
                                  (DAY.isoformat(),)).fetchall())
        finally:
            db.close()
        self.assertEqual(got.get("ours"), 1)
        self.assertEqual(got.get("bots", 0), 0)
