"""Log drains: Vercel and Netlify request logs posted to the ingest endpoint.

The fixtures are what the platforms post (shapes from their docs, values
made up: example.com, RFC 5737 addresses). Each holds the seven requests of
the CDN fixtures (test_cdn_formats.py) and records that are not requests:
a build log, a function's own log line, a background revalidation, a
beacon sent on by a rewrite. Vercel's also has one request logged twice
(a function that wrote two lines), which is counted once.

Vercel:  https://vercel.com/docs/drains/reference/logs
Netlify: https://docs.netlify.com/manage/monitoring/log-drains/
"""
from __future__ import annotations

import ast
import gzip
import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth_support import B  # noqa: E402
from ingest_support import TenantServer  # noqa: E402
from support import CHROME, GOOGLEBOT, GPTBOT, ASKED, Sandbox  # noqa: E402

from skald import Classifier, Group, audit, audit_drains, check, ingest  # noqa: E402
from skald import ingest_drain, summarise  # noqa: E402
from skald.accounts import site_configs  # noqa: E402
from skald.parse import AUTO_ORDER, PARSERS, ReadStats, detect, read  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
UTC = timezone.utc
SHOP, NEWS = "shop.example.com", "news.example.com"


def vercel_record(**proxy) -> dict:
    base = {"timestamp": 1791280800000, "method": "GET", "host": "example.com",
            "path": "/guides/alpha?x=1", "userAgent": [CHROME], "region": "fra1",
            "referer": "https://chatgpt.com/", "statusCode": 200,
            "clientIp": "203.0.113.10", "responseByteSize": 7340}
    base.update(proxy)
    return {"id": "1791280000000000000000000999", "deploymentId": "dpl_EXAMPLE",
            "source": "static", "host": "my-app-abc123.vercel.app",
            "timestamp": 1791280800111, "projectId": "prj_EXAMPLE", "level": "info",
            "requestId": "req-example-x",
            "proxy": {k: v for k, v in base.items() if v is not None}}


def netlify_record(**over) -> dict:
    row = {"log_type": "traffic", "timestamp": "2026-10-06T10:00:00.831Z",
           "client_ip": "203.0.113.10", "method": "GET",
           "url": "https://example.com/guides/alpha?x=1", "status_code": 200,
           "user_agent": CHROME, "referrer": "https://chatgpt.com/", "country": "de",
           "duration": 250, "response_size": 7340, "request_id": "01FDWR77JMF2DA1CHF5YA6H07C",
           "site_id": "00000000-0000-4000-8000-000000000000"}
    row.update(over)
    return {k: v for k, v in row.items() if v is not None}


def kept(name: str, fixture: str) -> list[str]:
    lines, _, _ = ingest_drain.convert((FIXTURES / fixture).read_bytes(), name)
    data, _, _ = ingest.split(lines, "auto")
    return data.decode().splitlines()


# ----------------------------------------------------------------- parsers

class Parsers(unittest.TestCase):

    def test_a_vercel_request(self):
        hit = PARSERS["vercel_json"](json.dumps(vercel_record()))
        self.assertEqual(hit.when, datetime(2026, 10, 6, 10, 0, tzinfo=UTC))
        self.assertEqual((hit.address, hit.host, hit.method, hit.url, hit.status),
                         ("203.0.113.10", "example.com", "GET", "/guides/alpha?x=1", "200"))
        self.assertEqual((hit.referrer, hit.user_agent, hit.country), (
            "https://chatgpt.com/", CHROME, ""))
        self.assertEqual((hit.size, hit.request_time, hit.rid, hit.fmt),
                         (7340, None, "req-example-x", "vercel_json"))

    def test_vercel_user_agent_as_a_string_and_status_fallbacks(self):
        row = vercel_record(userAgent=CHROME, statusCode=None)
        row["statusCode"] = 502
        hit = PARSERS["vercel_json"](json.dumps(row))
        self.assertEqual((hit.user_agent, hit.status), (CHROME, "502"))
        self.assertEqual(PARSERS["vercel_json"](json.dumps(vercel_record(userAgent=[]))
                                                ).user_agent, "")

    def test_vercel_records_that_are_not_readable_requests(self):
        cases = {"no address (IP addresses hidden)": vercel_record(clientIp=None),
                 "a background revalidation": vercel_record(statusCode=-1),
                 "no path": vercel_record(path=None)}
        build = {"id": "1", "source": "build", "timestamp": 1791280800000,
                 "message": "Build completed", "type": "stdout"}
        for label, row in list(cases.items()) + [("a build log", build)]:
            with self.subTest(label):
                self.assertIsNone(PARSERS["vercel_json"](json.dumps(row)))
                self.assertIsNone(audit.line_hit(json.dumps(row)))

    def test_a_netlify_request(self):
        hit = PARSERS["netlify_json"](json.dumps(netlify_record()))
        self.assertEqual(hit.when, datetime(2026, 10, 6, 10, 0, 0, 831000, tzinfo=UTC))
        self.assertEqual((hit.host, hit.url, hit.country, hit.status),
                         ("example.com", "/guides/alpha?x=1", "DE", "200"))
        self.assertEqual((hit.request_time, hit.size, hit.rid),
                         (0.25, 7340, "01FDWR77JMF2DA1CHF5YA6H07C"))

    def test_netlify_urls_and_countries(self):
        cases = [("/a?b=1", "", "/a?b=1"), ("https://Example.com:443/x#top", "example.com", "/x"),
                 ("https://example.com", "example.com", "/"),
                 ("https://example.com?q=1", "example.com", "/?q=1"),
                 ("http://user@example.com/p?", "example.com", "/p")]
        for url, host, path in cases:
            with self.subTest(url):
                hit = PARSERS["netlify_json"](json.dumps(netlify_record(url=url)))
                self.assertEqual((hit.host, hit.url), (host, path))
        for cc in ("XX", "ZZ", "-", "", "usa"):
            self.assertEqual(PARSERS["netlify_json"](
                json.dumps(netlify_record(country=cc))).country, "")

    def test_netlify_records_that_are_not_readable_requests(self):
        for label, row in (("PII excluded", netlify_record(client_ip=None, user_agent=None)),
                           ("a function log", netlify_record(log_type="functions")),
                           ("no status", netlify_record(status_code=None))):
            with self.subTest(label):
                self.assertIsNone(PARSERS["netlify_json"](json.dumps(row)))
                self.assertIsNone(audit.line_hit(json.dumps(row)))

    def test_registered_for_auto_and_for_sites(self):
        for fmt in ("vercel_json", "netlify_json"):
            self.assertIn(fmt, PARSERS)
            self.assertIn(fmt, AUTO_ORDER)
            self.assertIn(fmt, site_configs.FORMATS)

    def test_no_json_format_reads_another_ones_lines(self):
        samples = {
            "vercel_json": [json.dumps(vercel_record())],
            "netlify_json": [json.dumps(netlify_record()),
                             json.dumps(netlify_record(url="/relative"))],
            "caddy_json": (FIXTURES / "caddy.jsonl").read_text().splitlines(),
            "cloudflare_json": (FIXTURES / "cloudflare_logpush.jsonl").read_text().splitlines(),
            "fastly_json": (FIXTURES / "fastly.jsonl").read_text().splitlines(),
        }
        for owner, lines in samples.items():
            for name in samples:
                if name == owner:
                    continue
                for line in lines:
                    self.assertIsNone(PARSERS[name](line), (name, owner))

    def test_detected(self):
        self.assertEqual(detect(kept("vercel", "vercel_drain.json")), "vercel_json")
        self.assertEqual(detect(kept("netlify", "netlify_drain.ndjson")), "netlify_json")


# ------------------------------------------------------------ what is kept

class Convert(unittest.TestCase):

    def test_json_array_and_ndjson_give_the_same_lines(self):
        self.assertEqual(kept("vercel", "vercel_drain.json"),
                         kept("vercel", "vercel_drain.ndjson"))

    def test_counts(self):
        for name, fixture, lines, skipped in (("vercel", "vercel_drain.json", 8, 4),
                                              ("netlify", "netlify_drain.ndjson", 7, 3)):
            with self.subTest(fixture):
                body, got_skipped, bad = ingest_drain.convert(
                    (FIXTURES / fixture).read_bytes(), name)
                data, accepted, rejected = ingest.split(body, ingest_drain.PLATFORMS[name])
                self.assertEqual((accepted, rejected, got_skipped, bad),
                                 (lines, 0, skipped, 0))

    def test_only_the_fields_skald_reads_are_kept(self):
        text = "\n".join(kept("vercel", "vercel_drain.json") +
                         kept("netlify", "netlify_drain.ndjson"))
        for gone in ("deploymentId", "projectId", "ja3Digest", "message", "region",
                     "vercelCache", "scheme", "entrypoint", "account_id", "site_id",
                     "deploy_id", "content_type", "request_size", "firewall_rule"):
            self.assertNotIn(f'"{gone}"', text, gone)
        self.assertNotIn("traffic-beacon", text)

    def test_unreadable_bodies_and_records(self):
        self.assertEqual(ingest_drain.records(b"[not json"), ([], 1))
        self.assertEqual(ingest_drain.records(b'{"a":1}\nnope\n\n[1]'), ([{"a": 1}, [1]], 1))
        _, skipped, bad = ingest_drain.convert(b'[1, "x", {"source": "build"}]', "vercel")
        self.assertEqual((skipped, bad), (1, 2))

    def test_the_figures_match_the_cdn_fixtures(self):
        for name, fixture, countries in (
                ("vercel", "vercel_drain.json", {}),
                ("netlify", "netlify_drain.ndjson", {"US": 1, "GB": 1})):
            with self.subTest(fixture), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "access.log"
                path.write_text("\n".join(kept(name, fixture)) + "\n")
                stats = ReadStats()
                totals = summarise(read([path], "auto", stats), Classifier([]), 30)
                self.assertEqual(totals.parsed, 7)            # the twin is dropped by id
                self.assertEqual((stats.unparsed, len(stats.removed)),
                                 (0, 1 if name == "vercel" else 0))
                people = totals.groups[Group.PEOPLE]
                self.assertEqual((people.hits, people.views, people.visits), (4, 3, 2))
                self.assertEqual(dict(people.cited_by), {"chatgpt.com": 1})
                self.assertEqual(totals.groups[Group.SEARCH_ENGINE].hits, 1)
                self.assertEqual(dict(people.countries), countries)
                self.assertEqual(check(totals), [])


# ------------------------------------------------------------- the audit

def _same(line: str):
    hit = None
    for name in ("vercel_json", "netlify_json"):
        hit = hit or PARSERS[name](line)
    got = audit.line_hit(line)
    if hit is None or got is None:
        return hit, got
    return ((hit.when, hit.address, hit.host, hit.method, hit.url, hit.status, hit.referrer,
             hit.user_agent, hit.country, hit.rid),
            (got.when, got.address, got.host, got.method, got.url, got.status, got.referrer,
             got.agent, got.country, got.rid))


class AuditReadsThemItself(unittest.TestCase):

    def test_it_imports_nothing_from_the_package(self):
        tree = ast.parse(Path(audit_drains.__file__).read_text())
        relative = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level]
        self.assertEqual(relative, [])

    def test_both_roads_read_every_line_alike(self):
        lines = kept("vercel", "vercel_drain.json") + kept("netlify", "netlify_drain.ndjson")
        odd = [vercel_record(userAgent="curl/8.7.1", timestamp=None),
               vercel_record(timestamp=1791280800123456),          # microseconds
               netlify_record(timestamp="2026-10-06T12:00:00.123456789+02:00"),
               netlify_record(timestamp="2026-10-06 10:00:00z", url="https://[2001:db8::1]:8443/v"),
               netlify_record(country="gb", referrer="-", url="https://example.com?x=1"),
               netlify_record(timestamp="not a time"), netlify_record(status_code="20x")]
        for line in lines + [json.dumps(r) for r in odd]:
            with self.subTest(line=line[:90]):
                main, second = _same(line)
                self.assertEqual(main, second)

    def test_a_drain_day_passes_the_audit(self):
        """Collected by run-daily's road, recounted by the audit's: all match."""
        day = date(2026, 10, 5)
        noon = datetime(2026, 10, 5, 12, tzinfo=UTC)
        rows = [(noon + timedelta(minutes=i), f"203.0.113.{10 + i}",
                 "/guides/alpha" if i % 2 else "/", CHROME,
                 "https://chatgpt.com/" if i == 0 else "", 200, "example.com",
                 "GB" if i % 2 else "US") for i in range(4)]
        rows += [(noon + timedelta(hours=1), "198.51.100.40", "/guides/alpha", GPTBOT, "", 200,
                  "example.com", "US"),
                 (noon + timedelta(hours=1, minutes=1), "198.51.100.41", "/guides/beta", ASKED,
                  "", 200, "example.com", "US"),
                 (noon + timedelta(hours=1, minutes=2), "198.51.100.42", "/", GOOGLEBOT, "",
                  200, "example.com", "US"),
                 (noon + timedelta(hours=1, minutes=3), "198.51.100.52", "/.env", "curl/8.7.1",
                  "", 404, "example.com", "US"),
                 (noon + timedelta(hours=1, minutes=4), "198.51.100.54", "/v1/x", CHROME, "",
                  200, "api.example.com", "US")]
        for name in ("vercel", "netlify"):
            records = []
            for i, (when, ip, path, agent, ref, status, host, cc) in enumerate(rows):
                if name == "vercel":
                    rec = vercel_record(timestamp=int(when.timestamp() * 1000), clientIp=ip,
                                        path=path, userAgent=[agent], referer=ref or None,
                                        statusCode=status, host=host)
                    rec["requestId"] = f"req-{i}"
                else:
                    rec = netlify_record(timestamp=when.isoformat(), client_ip=ip,
                                         url=f"https://{host}{path}", user_agent=agent,
                                         referrer=ref or None, status_code=status, country=cc,
                                         request_id=f"01J{i:023d}")
                records.append(rec)
            body, _, _ = ingest_drain.convert(json.dumps(records).encode(), name)
            with self.subTest(name):
                box = Sandbox()
                try:
                    box.log([body.decode()])
                    code, _, err = box.run("--today", "2026-10-06", "collect")
                    self.assertEqual(code, 0, err)
                    code, out, err = box.run("--today", "2026-10-06", "audit")
                    self.assertEqual(code, 0, err + out)
                    self.assertIn("all match", out)
                    from skald.config import load_config
                    figures = audit.recount(load_config(box.config), day, UTC)
                    self.assertEqual(figures["quality"]["old_format"], 0)
                    self.assertEqual((figures["requests"], figures["readers"],
                                      figures["excluded"]), (8, 4, 1))
                finally:
                    box.close()


# ------------------------------------------------------------ the endpoint

class DrainEndpoint(TenantServer):

    def setUp(self):
        super().setUp()
        db = self.db()
        try:
            site_configs.create(db, self.beta["id"], SHOP, "cli", fmt="vercel_json")
            site_configs.create(db, self.beta["id"], NEWS, "cli", fmt="netlify_json")
        finally:
            db.close()

    def post(self, site, body: bytes, fmt="vercel", token=None, headers=None, gz=False):
        hdrs = {"Content-Type": "application/json"}
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        if gz:
            body = gzip.compress(body)
            hdrs["Content-Encoding"] = "gzip"
        hdrs.update(headers or {})
        return self.call("POST", f"/traffic-ingest/{site}?format={fmt}", headers=hdrs, raw=body)

    def test_a_vercel_drain_with_a_token(self):
        token = self.token(self.beta, sites=[SHOP])
        body = (FIXTURES / "vercel_drain.json").read_bytes()
        got = self.post(SHOP, body, token=token)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json, {"ok": True, "accepted": 8, "rejected": 0, "skipped": 4,
                                    "duplicate": False})
        hits = list(read([self.ingest_root / SHOP / "access.log"], "vercel_json"))
        self.assertEqual(len(hits), 7)
        again = self.post(SHOP, body, token=token)                # Vercel retried it
        self.assertTrue(again.json["duplicate"])
        self.assertEqual(self.stored(SHOP).count(b"\n"), 8)
        ndjson = self.post(SHOP, (FIXTURES / "vercel_drain.ndjson").read_bytes(), token=token,
                           gz=True)
        self.assertEqual((ndjson.status, ndjson.json["accepted"]), (200, 8))

    def test_a_netlify_drain(self):
        token = self.token(self.beta, sites=[NEWS])
        got = self.post(NEWS, (FIXTURES / "netlify_drain.ndjson").read_bytes(), "netlify",
                        token)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual((got.json["accepted"], got.json["skipped"]), (7, 3))
        self.assertNotIn(b"deploy_id", self.stored(NEWS))

    def test_who_may_not_post(self):
        body = (FIXTURES / "vercel_drain.json").read_bytes()
        self.assertEqual(self.post(SHOP, body).status, 401)
        self.assertEqual(self.post(SHOP, body, token=self.token(self.alpha)).status, 403)
        self.assertEqual(self.post(SHOP, body, token=self.token(
            self.beta, scopes=("read",))).status, 403)
        self.assertEqual(self.post(SHOP, body, "heroku", self.token(self.beta)).status, 400)
        # The site reads nginx lines: a drain is refused, not half-kept.
        self.assertEqual(self.post(B, body, token=self.token(self.beta)).status, 400)
        self.assertEqual(self.stored(SHOP) + self.stored(B), b"")

    def test_a_removed_site(self):
        token = self.token(self.beta, sites=[SHOP])
        db = self.db()
        try:
            site_configs.remove(db, self.beta["id"], SHOP, "cli")
        finally:
            db.close()
        self.assertEqual(self.post(SHOP, b"[]", token=token).status, 410)

    def test_vercels_signature(self):
        body = (FIXTURES / "vercel_drain.ndjson").read_bytes()
        secret = "drain-secret-for-tests-only"
        sign = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
        self.config["ingest"]["drains"] = {SHOP: {"vercel_secret_env": "TI_TEST_DRAIN"}}
        with mock.patch.dict(os.environ, {"TI_TEST_DRAIN": secret}):
            bad = self.post(SHOP, body, headers={"x-vercel-signature": "0" * 40})
            self.assertEqual(bad.status, 401)
            # A valid token does not excuse a wrong signature once a secret is set.
            self.assertEqual(self.post(SHOP, body, token=self.token(self.beta),
                                       headers={"x-vercel-signature": "0" * 40}).status, 401)
            good = self.post(SHOP, body, headers={"x-vercel-signature": sign})
            self.assertEqual((good.status, good.json["accepted"]), (200, 8))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TI_TEST_DRAIN", None)
            self.assertEqual(self.post(SHOP, body, headers={"x-vercel-signature": sign}
                                       ).status, 503)

    def test_vercels_ownership_check(self):
        self.config["ingest"]["drains"] = {SHOP: {"vercel_verify": "verify-value-example"}}
        probe = self.post(SHOP, b"")
        self.assertEqual(probe.status, 200)
        self.assertEqual(probe.headers.get("x-vercel-verify"), "verify-value-example")
        self.assertEqual(self.stored(SHOP), b"")
        # A post with a wrong token is still refused, and still says the value.
        bad = self.post(SHOP, b"[]", token="skald_x_y")
        self.assertEqual(bad.status, 401)
        self.assertEqual(bad.headers.get("x-vercel-verify"), "verify-value-example")



if __name__ == "__main__":
    unittest.main()
