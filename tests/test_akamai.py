"""Akamai DataStream 2 logs (parse_cdn.akamai, format akamai_json).

The fixture tests/fixtures/akamai_datastream2.jsonl holds the same seven requests as the
other CDN fixtures and is read by test_cdn_formats.py's shared tests (detection, figures,
countries). These are the reader's own rules. Addresses are RFC 5737, hosts example.com.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import doctor  # noqa: E402
from skald.accounts import site_configs  # noqa: E402
from skald.parse import AUTO_ORDER, PARSERS, ReadStats, read  # noqa: E402

UTC = timezone.utc
FIXTURES = Path(__file__).resolve().parent / "fixtures"
UA = ("Mozilla%2F5.0+%28Macintosh%3B+Intel+Mac+OS+X+10_15_7%29+AppleWebKit%2F537.36"
      "+%28KHTML%2C+like+Gecko%29+Chrome%2F129.0.0.0+Safari%2F537.36")
CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")


def akamai_line(**over) -> str:
    """A record shaped like Akamai's own JSON sample: every value a string."""
    row = {"version": "1", "streamId": "12345", "cp": "123456", "reqId": "1239f220",
           "reqTimeSec": "1791280800", "bytes": "4995", "cliIP": "192.0.2.10",
           "statusCode": "206", "proto": "HTTPS", "reqHost": "www.example.com",
           "reqMethod": "GET", "reqPath": "/path1/path2/file.ext", "reqPort": "443",
           "UA": UA, "queryStr": "param=value",
           "referer": "https%3A%2F%2Ftest.example.org%2Fen-US%2Fdocs",
           "turnAroundTimeMSec": "11", "transferTimeMSec": "125", "country": "IN",
           "cacheStatus": "1"}
    row.update(over)
    return json.dumps({k: v for k, v in row.items() if v is not None})


class Reader(unittest.TestCase):
    parse = staticmethod(PARSERS["akamai_json"])

    def test_akamais_sample_record(self):
        hit = self.parse(akamai_line())
        self.assertEqual(hit.when, datetime(2026, 10, 6, 10, tzinfo=UTC))
        self.assertEqual((hit.address, hit.host, hit.method), ("192.0.2.10", "www.example.com", "GET"))
        self.assertEqual((hit.url, hit.status), ("/path1/path2/file.ext?param=value", "206"))
        self.assertEqual(hit.user_agent, CHROME)
        self.assertEqual(hit.referrer, "https://test.example.org/en-US/docs")
        self.assertEqual((hit.country, hit.size), ("IN", 4995))
        self.assertAlmostEqual(hit.request_time, 0.011)
        self.assertEqual((hit.fmt, hit.rid), ("akamai_json", "1239f220"))

    def test_numbers_as_well_as_strings(self):
        hit = self.parse(akamai_line(statusCode=200, bytes=12, turnAroundTimeMSec=40,
                                     reqTimeSec=1791280800))
        self.assertEqual((hit.status, hit.size, hit.request_time), ("200", 12, 0.04))

    def test_timestamps(self):
        want = datetime(2026, 10, 6, 10, tzinfo=UTC)
        for stamp in ("1791280800", 1791280800, "1791280800000", 1791280800000,
                      "2026-10-06T10:00:00Z", "2026-10-06T10:00:00.000+00:00"):
            with self.subTest(stamp=stamp):
                self.assertEqual(self.parse(akamai_line(reqTimeSec=stamp)).when, want)
        frac = self.parse(akamai_line(reqTimeSec="1791280800.250")).when
        self.assertEqual(frac, datetime(2026, 10, 6, 10, 0, 0, 250000, tzinfo=UTC))

    def test_a_line_without_the_client_address_is_not_read(self):
        for address in (None, "", "-", "  "):
            with self.subTest(address=address):
                self.assertIsNone(self.parse(akamai_line(cliIP=address)))

    def test_needs_a_time_a_path_and_a_status(self):
        self.assertIsNone(self.parse(akamai_line(reqTimeSec=None)))
        self.assertIsNone(self.parse(akamai_line(reqTimeSec="yesterday")))
        self.assertIsNone(self.parse(akamai_line(reqPath=None)))
        self.assertIsNone(self.parse(akamai_line(reqPath="")))
        self.assertIsNone(self.parse(akamai_line(statusCode=None)))
        # 0: the client went away before any answer. No status to count.
        self.assertIsNone(self.parse(akamai_line(statusCode="0")))

    def test_path_query_and_host(self):
        self.assertEqual(self.parse(akamai_line(reqPath="a/b", queryStr=None)).url, "/a/b")
        self.assertEqual(self.parse(akamai_line(queryStr="?x=1")).url,
                         "/path1/path2/file.ext?x=1")
        self.assertEqual(self.parse(akamai_line(reqHost="WWW.example.com:8443")).host,
                         "www.example.com")
        self.assertEqual(self.parse(akamai_line(reqHost="[2001:db8::1]:443")).host,
                         "2001:db8::1")
        self.assertEqual(self.parse(akamai_line(reqHost=None)).host, "")

    def test_optional_fields_left_out_read_as_not_recorded(self):
        hit = self.parse(akamai_line(bytes=None, turnAroundTimeMSec=None, country=None,
                                     referer=None, UA=None, reqId=None))
        self.assertEqual((hit.size, hit.request_time, hit.country), (None, None, ""))
        self.assertEqual((hit.referrer, hit.user_agent, hit.rid), ("", "", ""))
        self.assertEqual(self.parse(akamai_line(reqId=None, reqID="abc")).rid, "abc")

    def test_a_plus_in_a_crawler_agent_survives(self):
        agent = "Mozilla/5.0 (compatible; GPTBot/1.2; +https://openai.com/gptbot)"
        encoded = agent.replace("+", "%2B").replace(" ", "+").replace("/", "%2F")
        self.assertEqual(self.parse(akamai_line(UA=encoded)).user_agent, agent)

    def test_a_country_must_be_a_code(self):
        self.assertEqual(self.parse(akamai_line(country="India")).country, "")
        self.assertEqual(self.parse(akamai_line(country="us")).country, "US")

    def test_websocket_and_midgress_lines_are_not_requests(self):
        self.assertIsNone(self.parse(akamai_line(recordTag="W")))
        for kind in ("2", "4", "6"):
            self.assertIsNone(self.parse(akamai_line(midgressType=kind)))
        self.assertIsNotNone(self.parse(akamai_line(recordTag="-", midgressType="-")))


class Wiring(unittest.TestCase):

    def test_registered_everywhere_a_format_is_named(self):
        self.assertIn("akamai_json", AUTO_ORDER)
        self.assertIn("akamai_json", site_configs.FORMATS)
        self.assertIn("akamai_json", doctor.NO_HEADERS)

    def test_no_other_reader_takes_an_akamai_line_and_it_takes_no_other(self):
        line = akamai_line()
        for name, parse in PARSERS.items():
            if name != "akamai_json":
                self.assertIsNone(parse(line), name)
        for fixture in ("fastly.jsonl", "cloudflare_logpush.jsonl", "caddy.jsonl"):
            for other in (FIXTURES / fixture).read_text().splitlines():
                self.assertIsNone(PARSERS["akamai_json"](other), fixture)

    def test_unreadable_lines_are_counted(self):
        good = (FIXTURES / "akamai_datastream2.jsonl").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text(good + akamai_line(cliIP=None) + "\n")
            stats = ReadStats()
            hits = list(read([path], "akamai_json", stats))
        self.assertEqual(len(hits), 7)
        self.assertEqual((stats.lines, stats.unparsed), (8, 1))

    def test_a_record_seen_twice_is_read_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text(akamai_line() + "\n" + akamai_line() + "\n")
            self.assertEqual(len(list(read([path], "auto"))), 1)


if __name__ == "__main__":
    unittest.main()
