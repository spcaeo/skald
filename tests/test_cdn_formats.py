"""CDN logs: Cloudflare Logpush, CloudFront standard logs and Fastly JSON.

A CDN log counts the pages the CDN served from its cache, which the origin
never saw. Each fixture holds the same seven requests: a person (Chrome)
reading /, an asset and a cached /pricing?plan=pro; a second person cited
from chatgpt.com; GPTBot; Googlebot; and a scanner's 404. So every format
must give the same figures: 7 requests, people 4 hits, 3 views, 2 visits.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import Classifier, Group, check, summarise  # noqa: E402
from skald.parse import (AUTO_ORDER, PARSERS, ReadStats, detect,  # noqa: E402
                                read)
from skald.parse_cdn import CLOUDFRONT_FIELDS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
UTC = timezone.utc
CHROME = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
CDN = {"cloudflare_logpush.jsonl": "cloudflare_json",
       "cloudfront.log": "cloudfront_w3c",
       "fastly.jsonl": "fastly_json"}


def cloudflare_line(**over) -> str:
    row = {"ClientIP": "203.0.113.10", "ClientRequestHost": "example.com",
           "ClientRequestMethod": "GET", "ClientRequestURI": "/pricing?plan=pro",
           "ClientRequestReferer": "https://chatgpt.com/",
           "ClientRequestUserAgent": CHROME, "ClientCountry": "us",
           "EdgeResponseStatus": 200, "EdgeResponseBytes": 4096,
           "EdgeStartTimestamp": "2026-10-06T10:00:00Z",
           "EdgeTimeToFirstByteMs": 120}
    row.update(over)
    return json.dumps({k: v for k, v in row.items() if v is not None})


def fastly_line(**over) -> str:
    row = {"timestamp": "2026-10-06T12:00:00+0200", "client_ip": "198.51.100.7",
           "geo_country": "de", "host": "example.com", "url": "/guides/alpha?x=1",
           "request_method": "GET", "request_referer": "https://www.google.com/",
           "request_user_agent": CHROME, "response_status": 200,
           "response_body_size": 7340, "time_elapsed": 250000}
    row.update(over)
    return json.dumps({k: v for k, v in row.items() if v is not None})


def cloudfront_line(**over) -> str:
    values = dict.fromkeys(CLOUDFRONT_FIELDS, "-")
    values.update({
        "date": "2026-10-06", "time": "23:59:58", "x-edge-location": "LHR50-P1",
        "sc-bytes": "5420", "c-ip": "203.0.113.30", "cs-method": "GET",
        "cs(Host)": "d111111abcdef8.cloudfront.net", "cs-uri-stem": "/pricing",
        "sc-status": "200", "cs(Referer)": "https://www.perplexity.ai/search%3Fq%3Dx",
        "cs(User-Agent)": CHROME.replace(" ", "%20"), "cs-uri-query": "plan=pro",
        "x-edge-result-type": "Hit", "x-edge-request-id": "EXAMPLEid",
        "x-host-header": "www.example.com", "time-taken": "0.082",
    })
    values.update(over)
    return "\t".join(values[name] for name in CLOUDFRONT_FIELDS) + "\n"


def analyse(path: Path):
    stats = ReadStats()
    totals = summarise(read([path], "auto", stats), Classifier(["MyCompanyCrawler"]), 30)
    return totals, stats


# ---------------------------------------------------------------- cloudflare

class TestCloudflare(unittest.TestCase):

    parse = staticmethod(PARSERS["cloudflare_json"])

    def test_field_mapping(self):
        hit = self.parse(cloudflare_line())
        self.assertEqual(hit.when, datetime(2026, 10, 6, 10, tzinfo=UTC))
        self.assertEqual((hit.address, hit.host, hit.method),
                         ("203.0.113.10", "example.com", "GET"))
        self.assertEqual(hit.url, "/pricing?plan=pro")
        self.assertEqual(hit.path, "/pricing")
        self.assertEqual((hit.status, hit.size), ("200", 4096))
        self.assertEqual(hit.referrer, "https://chatgpt.com/")
        self.assertEqual(hit.user_agent, CHROME)
        self.assertEqual(hit.country, "US")           # Logpush writes "us"
        self.assertEqual(hit.request_time, 0.12)      # milliseconds -> seconds
        self.assertEqual(hit.fmt, "cloudflare_json")

    def test_every_logpush_timestamp_format(self):
        """rfc3339 / rfc3339ms / unix / unixnano, and a float."""
        want = datetime(2026, 10, 6, 10, tzinfo=UTC)
        epoch = int(want.timestamp())
        for stamp, expected in (
                ("2026-10-06T10:00:00Z", want),
                ("2026-10-06T10:00:00.250Z", want + timedelta(milliseconds=250)),
                (epoch, want),
                (epoch * 10**9 + 123456789, want + timedelta(microseconds=123456)),
                (epoch + 0.5, want + timedelta(milliseconds=500)),
                (str(epoch * 10**9), want)):
            with self.subTest(stamp=stamp):
                self.assertEqual(self.parse(cloudflare_line(EdgeStartTimestamp=stamp)).when,
                                 expected)

    def test_origin_time_when_no_time_to_first_byte(self):
        hit = self.parse(cloudflare_line(EdgeTimeToFirstByteMs=None,
                                         OriginResponseDurationMs=480))
        self.assertEqual(hit.request_time, 0.48)
        hit = self.parse(cloudflare_line(EdgeTimeToFirstByteMs=None))
        self.assertIsNone(hit.request_time)

    def test_unknown_countries_are_no_country(self):
        for code in ("xx", "XX", "", "zz"):
            with self.subTest(code=code):
                self.assertEqual(self.parse(cloudflare_line(ClientCountry=code)).country, "")

    def test_missing_optional_fields_are_fine(self):
        line = json.dumps({"ClientRequestURI": "/", "EdgeStartTimestamp": 1791280800})
        hit = self.parse(line)
        self.assertEqual((hit.url, hit.address, hit.referrer, hit.country), ("/", "", "", ""))
        self.assertIsNone(hit.size)
        self.assertIsNone(hit.request_time)

    def test_missing_uri_or_timestamp_is_unreadable(self):
        self.assertIsNone(self.parse(cloudflare_line(ClientRequestURI=None)))
        self.assertIsNone(self.parse(cloudflare_line(EdgeStartTimestamp=None)))
        self.assertIsNone(self.parse(cloudflare_line(EdgeStartTimestamp="yesterday")))
        self.assertIsNone(self.parse("not json"))


# ---------------------------------------------------------------- cloudfront

class TestCloudFront(unittest.TestCase):

    parse = staticmethod(PARSERS["cloudfront_w3c"])

    def test_field_mapping(self):
        hit = self.parse(cloudfront_line())
        self.assertEqual(hit.when, datetime(2026, 10, 6, 23, 59, 58, tzinfo=UTC))
        self.assertEqual(hit.address, "203.0.113.30")
        # The Host header, not the distribution's cloudfront.net name.
        self.assertEqual(hit.host, "www.example.com")
        self.assertEqual(hit.url, "/pricing?plan=pro")
        self.assertEqual(hit.user_agent, CHROME)
        self.assertEqual(hit.referrer, "https://www.perplexity.ai/search?q=x")
        self.assertEqual((hit.status, hit.size, hit.request_time), ("200", 5420, 0.082))
        self.assertEqual(hit.country, "")
        self.assertEqual(hit.fmt, "cloudfront_w3c")

    def test_no_query_and_dashes_are_empty(self):
        hit = self.parse(cloudfront_line(**{"cs-uri-query": "-", "cs(Referer)": "-",
                                            "x-host-header": "-"}))
        self.assertEqual((hit.url, hit.referrer), ("/pricing", ""))
        self.assertEqual(hit.host, "d111111abcdef8.cloudfront.net")

    def test_double_encoding_is_decoded_once(self):
        hit = self.parse(cloudfront_line(**{"cs(User-Agent)": "Bot%2520One"}))
        self.assertEqual(hit.user_agent, "Bot%20One")

    def test_header_lines_and_other_formats_are_not_cloudfront(self):
        self.assertIsNone(self.parse("#Version: 1.0\n"))
        self.assertIsNone(self.parse("#Fields: date time\n"))
        for name in ("mixed_extended.log", "combined.log", "caddy.jsonl"):
            for line in (FIXTURES / name).read_text().splitlines():
                self.assertIsNone(self.parse(line), line)

    def test_a_fields_line_earlier_in_the_read_is_followed(self):
        order = ["time", "date", "c-ip", "cs-method", "cs-uri-stem", "sc-status",
                 "x-host-header"]
        text = (f"#Version: 1.0\n#Fields: {' '.join(order)}\n"
                "08:00:00\t2026-10-06\t203.0.113.5\tGET\t/a\t200\texample.com\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cf.log"
            path.write_text(text)
            stats = ReadStats()
            hits = list(read([path], "cloudfront_w3c", stats))
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0].when.hour, hits[0].url, hits[0].host),
                         (8, "/a", "example.com"))
        self.assertEqual((stats.lines, stats.unparsed), (1, 0))
        # The shared parser keeps the standard order whatever it is handed.
        self.parse(f"#Fields: {' '.join(order)}\n")
        self.assertIsNotNone(self.parse(cloudfront_line()))

    def test_a_file_synced_twice_is_counted_once(self):
        """x-edge-request-id is unique per request, so a repeat is dropped."""
        text = (FIXTURES / "cloudfront.log").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cf.log"
            path.write_text(text + text)
            stats = ReadStats()
            hits = list(read([path], "auto", stats))
        self.assertEqual(len(hits), 7)
        self.assertEqual(len(stats.removed), 7)


# -------------------------------------------------------------------- fastly

class TestFastly(unittest.TestCase):

    parse = staticmethod(PARSERS["fastly_json"])

    def test_field_mapping(self):
        hit = self.parse(fastly_line())
        # strftime's "+0200": two hours ahead of UTC.
        self.assertEqual(hit.when, datetime(2026, 10, 6, 10, tzinfo=UTC))
        self.assertEqual((hit.address, hit.host, hit.method),
                         ("198.51.100.7", "example.com", "GET"))
        self.assertEqual(hit.url, "/guides/alpha?x=1")
        self.assertEqual((hit.status, hit.size), ("200", 7340))
        self.assertEqual(hit.referrer, "https://www.google.com/")
        self.assertEqual(hit.user_agent, CHROME)
        self.assertEqual(hit.country, "DE")
        self.assertEqual(hit.request_time, 0.25)      # microseconds -> seconds
        self.assertEqual(hit.fmt, "fastly_json")

    def test_alternative_names(self):
        line = json.dumps({"timestamp": 1791280800, "client_ip": "198.51.100.8",
                           "path": "/a", "query": "b=1", "method": "HEAD",
                           "status": "301", "referer": "https://example.org/",
                           "user_agent": "curl/8", "bytes": "12",
                           "country_code": "fr", "elapsed_ms": 40})
        hit = self.parse(line)
        self.assertEqual(hit.when, datetime(2026, 10, 6, 10, tzinfo=UTC))
        self.assertEqual((hit.url, hit.method, hit.status), ("/a?b=1", "HEAD", "301"))
        self.assertEqual((hit.referrer, hit.user_agent, hit.size, hit.country),
                         ("https://example.org/", "curl/8", 12, "FR"))
        self.assertEqual(hit.request_time, 0.04)
        self.assertEqual(self.parse(fastly_line(url=None, request_url="/r")).url, "/r")
        self.assertEqual(self.parse(fastly_line(time_elapsed=None,
                                                time_elapsed_ms=5)).request_time, 0.005)

    def test_timestamps(self):
        want = datetime(2026, 10, 6, 10, tzinfo=UTC)
        for stamp in ("2026-10-06T10:00:00Z", "2026-10-06T10:00:00+00:00",
                      "2026-10-06 10:00:00", "[06/Oct/2026:10:00:00 +0000]",
                      1791280800000, "1791280800"):
            with self.subTest(stamp=stamp):
                self.assertEqual(self.parse(fastly_line(timestamp=stamp)).when, want)

    def test_a_country_name_is_not_turned_into_a_code(self):
        self.assertEqual(self.parse(fastly_line(geo_country="germany")).country, "")
        self.assertEqual(self.parse(fastly_line(geo_country="ZZ")).country, "")

    def test_needs_a_timestamp_and_a_url(self):
        self.assertIsNone(self.parse(fastly_line(timestamp=None)))
        self.assertIsNone(self.parse(fastly_line(url=None)))


# -------------------------------------------------------------------- detect

class TestDetect(unittest.TestCase):

    def test_each_cdn_format_is_detected(self):
        for name, fmt in CDN.items():
            with self.subTest(name=name):
                lines = (FIXTURES / name).read_text().splitlines(True)
                self.assertEqual(detect(lines), fmt)

    def test_the_old_formats_are_still_detected(self):
        for name, fmt in (("mixed_extended.log", "nginx_extended"),
                          ("combined.log", "nginx_combined"),
                          ("caddy.jsonl", "caddy_json")):
            with self.subTest(name=name):
                lines = (FIXTURES / name).read_text().splitlines(True)
                self.assertEqual(detect(lines), fmt)

    def test_the_json_formats_do_not_read_each_others_lines(self):
        samples = {"caddy_json": (FIXTURES / "caddy.jsonl").read_text().splitlines(),
                   "cloudflare_json": [cloudflare_line()],
                   "fastly_json": [fastly_line()]}
        for owner, lines in samples.items():
            for name in ("caddy_json", "cloudflare_json", "fastly_json"):
                if name == owner:
                    continue
                for line in lines:
                    self.assertIsNone(PARSERS[name](line), (name, owner))

    def test_every_new_format_is_registered_for_auto(self):
        for fmt in CDN.values():
            self.assertIn(fmt, PARSERS)
            self.assertIn(fmt, AUTO_ORDER)


# ---------------------------------------------------------------- the files

class TestFixtures(unittest.TestCase):

    def test_auto_reads_every_line_and_no_header_counts(self):
        for name, fmt in CDN.items():
            with self.subTest(name=name):
                totals, stats = analyse(FIXTURES / name)
                self.assertEqual(totals.parsed, 7)
                # CloudFront's four header lines are neither lines nor unparsed.
                self.assertEqual((stats.lines, stats.unparsed), (7, 0))
                hits = list(read([FIXTURES / name]))
                self.assertEqual({h.fmt for h in hits}, {fmt})

    def test_the_figures(self):
        for name in CDN:
            with self.subTest(name=name):
                totals, _ = analyse(FIXTURES / name)
                people = totals.groups[Group.PEOPLE]
                # The asset is a request, not a page; the cached /pricing is.
                self.assertEqual((people.hits, people.views, people.visits), (4, 3, 2))
                self.assertEqual(dict(people.cited_by), {"chatgpt.com": 1})
                self.assertEqual(dict(totals.groups[Group.ANSWER_ENGINE].tiers),
                                 {"training": 1})
                self.assertEqual(totals.groups[Group.SEARCH_ENGINE].hits, 1)
                self.assertEqual((totals.groups[Group.BOTS].hits,
                                  totals.groups[Group.BOTS].probes), (1, 1))
                expected = {} if name == "cloudfront.log" else {"US": 1, "GB": 1}
                self.assertEqual(dict(people.countries), expected)
                self.assertEqual(check(totals), [])

    def test_a_mixed_file_still_reads(self):
        """The day a site moves behind a CDN: nginx lines, then CloudFront
        with its headers, then Cloudflare and Fastly lines."""
        text = "".join((FIXTURES / name).read_text() for name in
                       ("mixed_extended.log", "cloudfront.log",
                        "cloudflare_logpush.jsonl", "fastly.jsonl"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text(text)
            stats = ReadStats()
            hits = list(read([path], "auto", stats))
        self.assertEqual(len(hits), 16 + 7 + 7 + 7)
        self.assertEqual((stats.lines, stats.unparsed), (37, 0))
        counts = {}
        for hit in hits:
            counts[hit.fmt] = counts.get(hit.fmt, 0) + 1
        self.assertEqual(counts, {"nginx_extended": 16, "cloudfront_w3c": 7,
                                  "cloudflare_json": 7, "fastly_json": 7})

    def test_headers_only_at_the_start_do_not_spoil_detection(self):
        """A sample that opens with many W3C headers (many small files
        concatenated) is still detected from its records."""
        records = [l for l in (FIXTURES / "cloudfront.log").read_text().splitlines(True)
                   if not l.startswith("#")]
        header = "#Version: 1.0\n#Fields: " + " ".join(CLOUDFRONT_FIELDS) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cf.log"
            path.write_text(header * 150 + "".join(records))
            stats = ReadStats()
            hits = list(read([path], "auto", stats))
        self.assertEqual(len(hits), 7)
        self.assertEqual((stats.lines, stats.unparsed), (7, 0))


class TestCommandLine(unittest.TestCase):

    def test_check_exits_zero_for_each_cdn_log(self):
        for name in CDN:
            with self.subTest(name=name):
                done = subprocess.run(
                    [sys.executable, str(ROOT / "report.py"), "--config",
                     "config.example.yml", "--log", f"tests/fixtures/{name}", "--check"],
                    cwd=ROOT, capture_output=True, text=True, env=dict(os.environ),
                    timeout=120)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("7 requests, every category reconciles", done.stdout)


if __name__ == "__main__":
    unittest.main()
