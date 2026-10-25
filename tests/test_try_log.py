"""The dry run of a log source (try_log.py, try_log_cli.py, POST sites/trylog):
each format is detected from its own fixture, unreadable files and lines say
why without printing a line, gzip and empty files, the five groups add up to
the lines read, the warnings, the CLI with and without a config, and the
dashboard route. RFC 5737 addresses and example.com only.
"""
from __future__ import annotations

import contextlib
import gzip
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import cli, parse, try_log  # noqa: E402
from skald.try_log import SampleError, dry_run, sample_file, sample_text  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"


def extended(n: int, host: str = "example.com", path: str = "/", ref: str = "https://www.example.org/",
             agent: str = UA, minute: int = 0) -> str:
    return (f'2026-10-06T10:{minute:02d}:{n % 60:02d}+00:00 192.0.2.{n % 250 + 1} {host} "GET {path} HTTP/2.0" '
            f'200 512 "{ref}" "{agent}" 0.004 cc=US\n')


def combined(n: int, ref: str = "-", agent: str = UA, tail: str = "") -> str:
    return (f'198.51.100.{n % 250 + 1} - - [06/Oct/2026:10:00:{n % 60:02d} +0000] "GET /p{n} HTTP/1.1" '
            f'200 512 "{ref}" "{agent}"{tail}\n')


def visit(n: int, host: str = "example.com") -> list[str]:
    """One person's page and its assets, so the page counts as rendered."""
    return [extended(n, host, "/pricing/", minute=n % 50),
            extended(n, host, "/_next/static/app.css", minute=n % 50),
            extended(n, host, "/_next/static/app.js", minute=n % 50)]


class Detection(unittest.TestCase):
    CASES = {"akamai_datastream2.jsonl": "akamai_json", "caddy.jsonl": "caddy_json",
             "cloudflare_logpush.jsonl": "cloudflare_json", "cloudfront.log": "cloudfront_w3c",
             "combined.log": "nginx_combined", "edge_worker.ndjson": "edge_json",
             "fastly.jsonl": "fastly_json", "one_session.log": "nginx_extended",
             "netlify_drain.ndjson": "netlify_json", "vercel_drain.ndjson": "vercel_json"}

    def test_each_format_is_picked_from_its_own_sample(self):
        for name, want in self.CASES.items():
            with self.subTest(name):
                r = dry_run(sample_file(FIXTURES / name))
                self.assertEqual(r["format"]["picked"], want)
                self.assertIn(r["format"]["sure"], ("sure", "likely"))
                self.assertGreater(r["read"], 0)
                by = {c["format"]: c["read"] for c in r["format"]["candidates"]}
                self.assertEqual(by[want], max(by.values()))
                self.assertEqual(set(by), set(parse.AUTO_ORDER))

    def test_every_reader_is_offered(self):
        self.assertEqual(set(try_log.FORMATS), {"auto", *parse.PARSERS})

    def test_a_chosen_reader_that_does_not_fit_says_which_does(self):
        r = dry_run(sample_file(FIXTURES / "one_session.log"), "nginx_combined")
        self.assertEqual(r["read"], 0)
        self.assertEqual(r["verdict"], "bad")
        self.assertIn("in the nginx_extended layout", r["reasons"][0]["why"])
        self.assertIn("nginx_combined reader cannot read", r["headline"])

    def test_the_count_matches_a_daily_runs_read(self):
        lines = sample_file(FIXTURES / "edge_worker.ndjson")
        r = dry_run(lines)
        stats = parse.ReadStats()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.log"
            path.write_text("".join(lines))
            got = list(parse.read([path], "auto", stats))
        # A line repeating a request id is read, then dropped by the count as a daily run does.
        dropped = len(stats.removed)
        self.assertEqual(dropped, 1)
        self.assertEqual((r["read"], r["unread"]), (len(got) + dropped, stats.unparsed))
        self.assertEqual(r["counted"]["unreadable"], stats.unparsed)
        self.assertEqual(r["counted"]["duplicates"], dropped)
        self.assertTrue(any("repeat a request id" in x for x in r["notes"]))

    def test_assets_outside_the_sites_page_assets(self):
        lines = [x for n in range(20) for x in (extended(n, path="/"), extended(n, path="/assets/a.css"),
                                                extended(n, path="/assets/b.js"))]
        r = dry_run(lines)
        self.assertTrue(any("not under the site's page assets" in w or
                            "No asset request is under the site's page assets (/_next/static/) "
                            "(here most are under /assets/)" in w for w in r["warnings"]), r["warnings"])
        r = dry_run(lines, config={"site": {"asset_prefixes": ["/assets/"]}})
        self.assertFalse(any("page assets" in w for w in r["warnings"]), r["warnings"])
        self.assertGreater(r["groups"][0]["readers"], 0)


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_gzip_is_read_by_its_bytes_not_its_name(self):
        body = "".join(extended(n) for n in range(30))
        for name in ("access.log.2.gz", "access.log.2"):
            with self.subTest(name):
                (self.tmp / name).write_bytes(gzip.compress(body.encode()))
                r = dry_run(sample_file(self.tmp / name))
                self.assertEqual((r["format"]["picked"], r["read"]), ("nginx_extended", 30))

    def test_lines_limit_counts_content_lines_only(self):
        (self.tmp / "cf.log").write_text("#Version: 1.0\n" + (FIXTURES / "cloudfront.log").read_text())
        got = sample_file(self.tmp / "cf.log", 2)
        self.assertEqual(sum(1 for x in got if x.strip() and not x.startswith("#")), 2)
        self.assertEqual(len(sample_file(FIXTURES / "one_session.log", 10)), 10)

    def test_an_empty_file(self):
        (self.tmp / "empty.log").write_text("")
        r = dry_run(sample_file(self.tmp / "empty.log"))
        self.assertEqual((r["lines"], r["verdict"]), (0, "bad"))
        self.assertIn("empty", r["headline"])

    def test_files_that_cannot_be_read(self):
        (self.tmp / "bad.gz").write_bytes(b"\x1f\x8b" + b"not really gzip")
        (self.tmp / "bin.log").write_bytes(b"\x00\x01\x02binary\n")
        for path, words in ((self.tmp / "missing.log", "no file"), (self.tmp, "folder"),
                            (self.tmp / "bad.gz", "cannot be unpacked"),
                            (self.tmp / "bin.log", "not a text file")):
            with self.subTest(path.name):
                with self.assertRaises(SampleError) as got:
                    sample_file(path)
                self.assertIn(words, str(got.exception))

    def test_an_unknown_format_name(self):
        with self.assertRaises(SampleError):
            dry_run(["x\n"], "nginx_fancy")


class Unreadable(unittest.TestCase):
    def test_reasons_name_lines_and_fields_never_the_line(self):
        lines = [extended(n) for n in range(20)]
        lines[3] = '203.0.113.9 - - [06/Oct/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 512\n'   # common
        lines[5] = '{"ts": 1, "who": "203.0.113.9"}\n'
        lines[7] = '{"ts": 1, "who": \n'
        lines[9] = '2026-10-06T10:00:00+00:00 203.0.113.9 example.com GET / 200\n'
        r = dry_run(lines)
        self.assertEqual((r["read"], r["unread"]), (16, 4))
        words = {x["why"]: x["examples"] for x in r["reasons"]}
        self.assertEqual(words["the common log format: no referrer and no user agent "
                              "(Skald needs the combined format)"], [4])
        self.assertEqual(words["JSON with fields no reader knows (ts, who)"], [6])
        self.assertEqual(words["JSON, but cut short or broken"], [8])
        self.assertIn(10, words["starts with an ISO time like Skald's extended layout, but the "
                                "request field is not as expected"])
        self.assertNotIn("203.0.113.9", json.dumps(r))
        self.assertEqual(r["verdict"], "bad")        # 20% unreadable: a day would be withheld
        self.assertTrue(any("cannot be read" in w for w in r["warnings"]))

    def test_at_most_three_examples_and_five_reasons(self):
        r = dry_run([f"junk line number {n} that is long enough\n" for n in range(10)])
        self.assertEqual(r["reasons"][0]["examples"], [1, 2, 3])
        self.assertEqual(r["reasons"][0]["lines"], 10)

    def test_an_error_log(self):
        lines = ["2026/10/24 05:11:48 [error] 123#123: *5 open() failed, client: 192.0.2.7, "
                 "server: example.com\n"] * 5
        r = dry_run(lines)
        self.assertEqual(r["read"], 0)
        self.assertTrue(any("error log, not an access log" in w for w in r["warnings"]))
        self.assertNotIn("192.0.2.7", json.dumps(r))


class Groups(unittest.TestCase):
    def lines(self):
        out = []
        for n in range(12):
            out += visit(n)
        out += [extended(n, agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
                for n in range(20, 26)]
        out += [extended(n, agent="Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
                         "GPTBot/1.1; +https://openai.com/gptbot)") for n in range(30, 34)]
        out += [extended(n, path="/.env") for n in range(40, 43)]
        out += [extended(n, host="api.example.com") for n in range(50, 55)]
        out += ["not a log line, but long enough to read\n"]
        return out

    def test_the_five_groups_add_up_to_the_lines_read(self):
        r = dry_run(self.lines(), site="example.com")
        c = r["counted"]
        self.assertTrue(c["adds_up"])
        self.assertEqual(c["groups_sum"], sum(g["requests"] for g in r["groups"]))
        self.assertEqual(c["groups_sum"], c["site_requests"])
        self.assertEqual(c["site_requests"] + c["other_hosts"] + c["unreadable"] + c["duplicates"],
                         c["lines"])
        self.assertEqual(c["lines"], r["lines"])
        self.assertEqual((c["other_hosts"], c["unreadable"]), (5, 1))
        self.assertEqual([g["group"] for g in r["groups"]],
                         ["people", "answer_engines", "search_engines", "bots", "ours"])
        by = {g["group"]: g for g in r["groups"]}
        self.assertEqual(by["search_engines"]["requests"], 6)
        self.assertEqual(by["answer_engines"]["requests"], 4)
        self.assertGreaterEqual(by["bots"]["requests"], 3)
        self.assertEqual(r["pages"][0]["path"], "/pricing/")
        # The one unreadable line is 1.8%, above the 1% a daily run allows: said, not hidden.
        self.assertEqual(len(c["problems"]), 1)
        self.assertTrue(c["problems"][0].startswith("too many unreadable lines"))

    def test_hosts_and_the_site(self):
        r = dry_run(self.lines(), site="example.com")
        hosts = {h["host"]: h for h in r["hosts"]}
        self.assertTrue(hosts["example.com"]["site"])
        self.assertFalse(hosts["api.example.com"]["site"])
        r = dry_run([extended(n, host="www.example.com") for n in range(10)], site="example.com")
        self.assertTrue(any("www.example.com, which is not one of the site's host" in w
                            for w in r["warnings"]))
        self.assertTrue(any("No line is for example.com" in w for w in r["warnings"]))

    def test_a_known_sites_settings_judge_the_lines(self):
        config = {"site": {"name": "example.com", "hosts": ["example.com", "www.example.com"]},
                  "logs": {"format": "nginx_combined"}}
        r = dry_run([extended(n, host="www.example.com") for n in range(10)], config=config,
                    site="example.com", site_known=True)
        self.assertEqual(r["counted"]["other_hosts"], 0)
        self.assertTrue(any("set to read nginx_combined" in w for w in r["warnings"]))


class Warnings(unittest.TestCase):
    def test_no_referrer_no_agent_no_host(self):
        r = dry_run([combined(n, agent="-") for n in range(60)])
        said = " ".join(r["warnings"])
        self.assertIn("No line has a referrer", said)
        self.assertIn("No line has a user agent", said)
        self.assertIn("No line carries a host name", said)
        self.assertNotIn("No request for CSS", said)      # no browser: nothing to say on assets
        self.assertEqual(r["verdict"], "warn")

    def test_browsers_with_no_assets(self):
        r = dry_run([combined(n) for n in range(60)])
        self.assertTrue(any("No request for CSS" in w for w in r["warnings"]))
        r = dry_run([combined(n) for n in range(10)])      # a quiet sample: no word on assets
        self.assertFalse(any("CSS" in w for w in r["warnings"]))
        probes = [extended(n, path="/.docker/config.json").replace(" 200 ", " 404 ") for n in range(30)]
        r = dry_run([extended(n) for n in range(30)] + probes)
        self.assertFalse(any("(here most are under /.docker/)" in w for w in r["warnings"]))

    def test_a_host_at_the_end_of_combined_and_utc(self):
        r = dry_run([combined(n, ref="https://www.example.org/", tail=' "example.com"')
                     for n in range(10)])
        self.assertEqual(r["no_host"], 0)
        self.assertEqual(r["times"]["zones"], ["UTC"])
        self.assertTrue(any("Times are UTC" in x for x in r["notes"]))
        self.assertTrue(any("Only 10 lines" in x for x in r["notes"]))

    def test_another_zone_and_the_future(self):
        line = (f'203.0.113.4 - - [06/Oct/2099:10:00:00 -0400] "GET / HTTP/1.1" 200 5 "-" "{UA}"\n')
        r = dry_run([line])
        self.assertEqual(r["times"]["zones"], ["UTC-04:00"])
        self.assertTrue(any("in the future" in w for w in r["warnings"]))

    def test_mixed_layouts(self):
        r = dry_run([extended(n) for n in range(5)] + [combined(n) for n in range(5)])
        self.assertEqual(r["read"], 10)
        self.assertEqual(r["other_layouts"], {"nginx_combined": 5})

    def test_ip_addresses_and_emails_in_paths_and_hosts_are_masked(self):
        lines = []
        for n in range(3):
            lines += [extended(n, "192.0.2.80", "/u/a@example.com/198.51.100.3"),
                      extended(n, "192.0.2.80", "/assets/x.css")]
        r = dry_run(lines)
        text = json.dumps(r)
        for secret in ("192.0.2.80", "a@example.com", "198.51.100.3"):
            self.assertNotIn(secret, text)
        self.assertEqual(try_log.mask("/x/2001:db8::1/y"), "/x/(an IP address)/y")
        self.assertEqual(try_log.mask("/a:b/c"), "/a:b/c")

    def test_a_pasted_sample(self):
        text = "".join(extended(n) for n in range(300)).replace("\n", "\r\n")
        got = sample_text(text)
        self.assertEqual(len(got), try_log.WEB_LINES)
        self.assertEqual(dry_run(got)["read"], try_log.WEB_LINES)


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.log = self.tmp / "access.log"
        self.log.write_text("".join(sum((visit(n) for n in range(20)), [])))

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_without_a_config(self):
        code, out, _ = self.run_cli("--config", str(self.tmp / "none.yml"), "try-log", str(self.log),
                                    "--site", "example.com")
        self.assertEqual(code, 0)
        for words in ("Format:   nginx_extended (sure)", "Lines:    60: 60 read, 0 could not be read",
                      "adds up", "60 lines = 60 for the site + 0 unreadable", "/pricing/",
                      "Result:   Skald can read this log.", "Nothing is stored"):
            self.assertIn(words, out)
        self.assertNotIn("192.0.2.", out)

    def test_with_a_config_its_site_judges(self):
        config = self.tmp / "config.yml"
        config.write_text(json.dumps({"site": {"name": "example.com", "hosts": ["example.com"]},
                                      "history": {"db": str(self.tmp / "h.sqlite")},
                                      "report": {"timezone": "America/New_York"}}))
        code, out, _ = self.run_cli("--config", str(config), "try-log", str(self.log))
        self.assertEqual(code, 0)
        self.assertIn("Site:     example.com, judged with its settings", out)
        self.assertIn("the site's zone: America/New_York", out)
        self.assertFalse((self.tmp / "h.sqlite").exists())        # nothing is stored
        code, out, _ = self.run_cli("--config", str(config), "try-log", str(self.log), "--json")
        self.assertEqual(json.loads(out)["counted"]["adds_up"], True)

    def test_exit_codes(self):
        bad = self.tmp / "error.log"
        bad.write_text("2026/10/24 05:11:48 [error] 1#1: *5 open() failed\n" * 3)
        none = str(self.tmp / "none.yml")
        self.assertEqual(self.run_cli("--config", none, "try-log", str(bad))[0], 1)
        code, _, err = self.run_cli("--config", none, "try-log", str(self.tmp / "gone.log"))
        self.assertEqual(code, 2)
        self.assertIn("There is no file", err)
        self.assertEqual(self.run_cli("--config", none, "try-log", str(self.log), "--lines", "0")[0], 2)


try:
    from ingest_support import TenantServer
except ImportError:          # pragma: no cover
    TenantServer = None

if TenantServer is not None:
    from auth_support import A, B

    class Route(TenantServer):
        def test_an_admin_tests_a_pasted_sample(self):
            cookie, csrf = self.session("admin@example.com")
            text = "".join(extended(n, host=A) for n in range(250))
            got = self.post(f"/traffic/{A}/sites/trylog", {"site": A, "text": text}, cookie, csrf)
            self.assertEqual(got.status, 200, got.json)
            r = got.json["report"]
            self.assertEqual((r["lines"], r["read"], r["site_known"]), (200, 200, True))
            self.assertTrue(r["counted"]["adds_up"])
            self.assertTrue(any("set to read nginx_combined" in w for w in r["warnings"]))
            self.assertNotIn("192.0.2.", json.dumps(got.json))

        def test_refusals(self):
            cookie, csrf = self.session("admin@example.com")
            path = f"/traffic/{A}/sites/trylog"
            self.assertEqual(self.post(path, {"site": A, "text": " "}, cookie, csrf).status, 400)
            self.assertEqual(self.post(path, {"site": B, "text": "x"}, cookie, csrf).status, 404)
            self.assertEqual(self.post(path, {"site": A, "text": "x" * 20, "format": "nope"},
                                       cookie, csrf).status, 400)
            big = "x" * (try_log.WEB_BYTES + 100)        # read, then refused in words
            self.assertEqual(self.post(path, {"site": A, "text": big}, cookie, csrf).status, 413)
            viewer, vcsrf = self.session("viewer@example.com")
            self.assertEqual(self.post(path, {"site": A, "text": "x"}, viewer, vcsrf).status, 403)


class Page(unittest.TestCase):
    def test_the_dialog_in_node(self):
        if not shutil.which("node"):
            self.skipTest("node not installed")
        report = dry_run([line for n in range(8) for line in visit(n)] + ["junk that is long enough\n"],
                         site="example.com")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text(json.dumps({"report": report, "formats": list(try_log.FORMATS),
                                        "web_lines": try_log.WEB_LINES,
                                        "web_bytes": try_log.WEB_BYTES}))
            js = Path(__file__).resolve().parent / "js" / "conn-sample.mjs"
            done = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=60,
                                  env={**os.environ, "SAMPLE_JSON": str(path)})
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        self.assertIn("conn-sample: all passed", done.stdout)


if __name__ == "__main__":
    unittest.main()
