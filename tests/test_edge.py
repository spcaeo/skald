"""Edge records: one JSON object per request, posted by a CDN Worker.

Cloudflare's own request log (Logpush, HTTP requests) is not on every plan,
so there a page Cloudflare serves from its cache never reaches any log Skald
reads. The Skald Worker (deploy/cloudflare-worker/skald-edge.js) posts one
"edge record" per request to POST /traffic-ingest/<site>?format=edge.

The fixture holds the seven requests of the CDN and drain fixtures, with
cf-cache-status values, plus: one request posted twice (same id, counted
once), a beacon (Skald's own path, skipped) and a record without the
visitor's address (rejected). Values are made up: example.com, RFC 5737.

The double-count rule: a request the CDN passed on (MISS, BYPASS, DYNAMIC,
...) is in the origin's log too. When the site reads both, Skald keeps
only the edge records with cache HIT (`logs.edge_only_cached`, true unless
the site's format is `edge_json`, the edge alone).
"""
from __future__ import annotations

import ast
import gzip
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest_support import TenantServer  # noqa: E402
from support import ASKED, CHROME, GOOGLEBOT, GPTBOT, Sandbox  # noqa: E402

from skald import Classifier, Group, audit, audit_drains, check, ingest  # noqa: E402
from skald import ingest_drain, summarise  # noqa: E402
from skald.accounts import site_configs  # noqa: E402
from skald.parse import AUTO_ORDER, PARSERS, ReadStats, detect, read  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURES / "edge_worker.ndjson"
UTC = timezone.utc
EDGE_ONLY, BOTH = "edge.example.com", "both.example.com"

# What the origin's own log has: the three requests the CDN passed on.
ORIGIN = [
    '203.0.113.10 - - [06/Oct/2026:10:00:20 +0000] "GET /pricing?plan=pro HTTP/1.1" 200 4096 '
    f'"https://example.com/" "{CHROME}"',
    '198.51.100.40 - - [06/Oct/2026:10:10:00 +0000] "GET /guides/alpha HTTP/1.1" 200 7340 '
    f'"-" "{GPTBOT}"',
    '198.51.100.52 - - [06/Oct/2026:10:12:00 +0000] "GET /.env HTTP/1.1" 404 66 "-" '
    '"curl/8.7.1"',
]


def record(**over) -> dict:
    row = {"ts": "2026-10-06T10:00:00.000Z", "ip": "203.0.113.10", "method": "GET",
           "host": "example.com", "path": "/guides/alpha?x=1", "status": 200, "bytes": 7340,
           "referer": "https://chatgpt.com/", "ua": CHROME, "cache": "HIT",
           "id": "8c0000000000abcd-AMS"}
    row.update(over)
    return {k: v for k, v in row.items() if v is not None}


def kept(only_hits: bool, body: bytes | None = None) -> tuple[list[str], int, int, int]:
    """(kept lines, accepted, rejected, skipped) for the fixture."""
    lines, skipped, bad = ingest_drain.convert(
        FIXTURE.read_bytes() if body is None else body, "edge", only_hits=only_hits)
    data, accepted, rejected = ingest.split(lines, "auto")
    return data.decode().splitlines(), accepted, rejected + bad, skipped


# ----------------------------------------------------------------- parser

class Parser(unittest.TestCase):

    def test_an_edge_record(self):
        hit = PARSERS["edge_json"](json.dumps(record()))
        self.assertEqual(hit.when, datetime(2026, 10, 6, 10, 0, tzinfo=UTC))
        self.assertEqual((hit.address, hit.host, hit.method, hit.url, hit.status),
                         ("203.0.113.10", "example.com", "GET", "/guides/alpha?x=1", "200"))
        self.assertEqual((hit.referrer, hit.user_agent, hit.country, hit.request_time),
                         ("https://chatgpt.com/", CHROME, "", None))
        self.assertEqual((hit.size, hit.rid, hit.fmt), (7340, "8c0000000000abcd-AMS",
                                                        "edge_json"))

    def test_times(self):
        cases = {1791280800000: datetime(2026, 10, 6, 10, 0, tzinfo=UTC),
                 1791280800123.5: datetime(2026, 10, 6, 10, 0, 0, 123500, tzinfo=UTC),
                 "2026-10-06T12:00:00.5+02:00": datetime(2026, 10, 6, 10, 0, 0, 500000,
                                                         tzinfo=UTC),
                 "2026-10-06t10:00:00z": datetime(2026, 10, 6, 10, 0, tzinfo=UTC)}
        for ts, want in cases.items():
            with self.subTest(ts):
                self.assertEqual(PARSERS["edge_json"](json.dumps(record(ts=ts))).when, want)
        for ts in ("1791280800000", "yesterday", True, -5, None):
            with self.subTest(ts):
                self.assertIsNone(PARSERS["edge_json"](json.dumps(record(ts=ts))))

    def test_records_that_are_not_readable(self):
        for label, row in (("no address", record(ip="")), ("no path", record(path=None)),
                           ("not a path", record(path="https://example.com/x")),
                           ("no status", record(status=None)), ("odd status", record(status=-1)),
                           ("no time", record(ts=None))):
            with self.subTest(label):
                self.assertIsNone(PARSERS["edge_json"](json.dumps(row)))
                self.assertIsNone(audit.line_hit(json.dumps(row)))

    def test_registered_for_auto_and_for_sites(self):
        self.assertIn("edge_json", AUTO_ORDER)
        self.assertIn("edge_json", site_configs.FORMATS)
        self.assertIn('edge_json: "', (ROOT / "skald" / "webapp" / "js" / "tabs" /
                                       "sitesadmin.js").read_text())
        self.assertEqual(detect(kept(False)[0]), "edge_json")

    def test_no_other_format_reads_an_edge_record_and_back(self):
        others = [n for n in AUTO_ORDER if n != "edge_json"]
        lines = kept(False)[0]
        for name in others:
            for line in lines:
                self.assertIsNone(PARSERS[name](line), name)
        for fixture in ("caddy.jsonl", "cloudflare_logpush.jsonl", "fastly.jsonl",
                        "vercel_drain.ndjson", "netlify_drain.ndjson", "combined.log"):
            for line in (FIXTURES / fixture).read_text().splitlines():
                self.assertIsNone(PARSERS["edge_json"](line), fixture)


# ------------------------------------------------------------ what is kept

class Convert(unittest.TestCase):

    def test_edge_alone_keeps_every_request(self):
        lines, accepted, rejected, skipped = kept(False)
        # 7 requests and one posted twice; the beacon skipped; no address rejected.
        self.assertEqual((accepted, rejected, skipped), (8, 1, 1))
        self.assertEqual(len(lines), 8)

    def test_with_the_origin_only_cache_hits_are_kept(self):
        lines, accepted, rejected, skipped = kept(True)
        # HIT: /, the css, /guides/alpha, Googlebot's / ("hit" too), and the twin.
        self.assertEqual((accepted, rejected, skipped), (5, 1, 4))
        self.assertTrue(all('"cache":"HIT"' in x or '"cache":"hit"' in x for x in lines))

    def test_a_record_without_a_cache_status_is_not_a_hit(self):
        body = json.dumps([record(cache=None), record(cache="STALE", id="b-1")]).encode()
        self.assertEqual(kept(True, body)[1:], (0, 0, 2))
        self.assertEqual(kept(False, body)[1:], (2, 0, 0))

    def test_only_the_fields_of_an_edge_record_are_kept(self):
        text = "\n".join(kept(False)[0])
        for gone in ("colo", "country"):
            self.assertNotIn(f'"{gone}"', text)
        self.assertNotIn("traffic-beacon", text)
        keys = set()
        for line in text.splitlines():
            keys |= set(json.loads(line))
        self.assertEqual(keys, {"ts", "ip", "method", "host", "path", "status", "bytes",
                                "referer", "ua", "cache", "id"})

    def test_array_ndjson_and_one_object(self):
        rows = [json.loads(x) for x in FIXTURE.read_text().splitlines()]
        self.assertEqual(kept(False, json.dumps(rows).encode())[0], kept(False)[0])
        one = kept(False, json.dumps(record()).encode())
        self.assertEqual(one[1:], (1, 0, 0))

    def test_the_figures_match_the_cdn_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("\n".join(kept(False)[0]) + "\n")
            self._seven(path, removed=1)

    def test_origin_and_edge_together_count_each_request_once(self):
        """The double-count rule: the origin's lines plus the edge's hits."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "access.log"
            path.write_text("\n".join(kept(True)[0] + ORIGIN) + "\n")
            self._seven(path, removed=1)
            # Without the rule the three misses are there twice.
            path.write_text("\n".join(kept(False)[0] + ORIGIN) + "\n")
            stats = ReadStats()
            self.assertEqual(summarise(read([path], "auto", stats), Classifier([]), 30).parsed,
                             10)

    def _seven(self, path: Path, removed: int):
        stats = ReadStats()
        totals = summarise(read([path], "auto", stats), Classifier([]), 30)
        self.assertEqual(totals.parsed, 7)
        self.assertEqual((stats.unparsed, len(stats.removed)), (0, removed))
        people = totals.groups[Group.PEOPLE]
        self.assertEqual((people.hits, people.views, people.visits), (4, 3, 2))
        self.assertEqual(dict(people.cited_by), {"chatgpt.com": 1})
        self.assertEqual(totals.groups[Group.SEARCH_ENGINE].hits, 1)
        self.assertEqual(check(totals), [])


class Setting(unittest.TestCase):

    def test_edge_only_cached(self):
        rule = ingest_drain.edge_only_cached
        self.assertTrue(rule({"logs": {"format": "auto"}}))
        self.assertTrue(rule({}))
        self.assertTrue(rule({"logs": {"format": "nginx_extended"}}))
        self.assertFalse(rule({"logs": {"format": "edge_json"}}))
        self.assertFalse(rule({"logs": {"format": "auto", "edge_only_cached": False}}))
        self.assertFalse(rule({"logs": {"edge_only_cached": "false"}}))
        self.assertTrue(rule({"logs": {"format": "edge_json", "edge_only_cached": True}}))


# ------------------------------------------------------------- the audit

class AuditReadsThemItself(unittest.TestCase):

    def test_it_imports_nothing_from_the_package(self):
        tree = ast.parse(Path(audit_drains.__file__).read_text())
        relative = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.level]
        self.assertEqual(relative, [])

    def test_both_roads_read_every_line_alike(self):
        odd = [record(ts=1791280800123), record(ts=1791280800123.5),
               record(ts="2026-10-06T12:00:00.123456789+02:00"),
               record(ts="2026-10-06 10:00:00z"), record(ts="2026-10-06t10:00:00Z"),
               record(ts="1791280800000"), record(ts="nope"), record(status="20x"),
               record(status="404"), record(referer="-", ua=None, host=None, method=None),
               record(path="/a b?c=d"), record(path="x"), record(ip=" "), record(id=None),
               record(bytes="12"), {"ts": 1, "path": "/"}, ["not", "a", "record"]]
        for line in kept(False)[0] + [json.dumps(r) for r in odd]:
            with self.subTest(line=line[:90]):
                hit = PARSERS["edge_json"](line)
                got = audit.line_hit(line)
                if hit is None or got is None:
                    self.assertEqual((hit, got), (None, None))
                    continue
                self.assertEqual(
                    (hit.when, hit.address, hit.host, hit.method, hit.url, hit.status,
                     hit.referrer, hit.user_agent, hit.country, hit.rid),
                    (got.when, got.address, got.host, got.method, got.url, got.status,
                     got.referrer, got.agent, got.country, got.rid))

    def test_an_edge_day_passes_the_audit(self):
        """Collected by run-daily's road, recounted by the audit's: all match."""
        day = date(2026, 10, 5)
        noon = datetime(2026, 10, 5, 12, tzinfo=UTC)
        rows = [(noon + timedelta(minutes=i), f"203.0.113.{10 + i}",
                 "/guides/alpha" if i % 2 else "/", CHROME,
                 "https://chatgpt.com/" if i == 0 else "", 200) for i in range(4)]
        rows += [(noon + timedelta(hours=1), "198.51.100.40", "/guides/alpha", GPTBOT, "", 200),
                 (noon + timedelta(hours=1, minutes=1), "198.51.100.41", "/guides/beta", ASKED,
                  "", 200),
                 (noon + timedelta(hours=1, minutes=2), "198.51.100.42", "/", GOOGLEBOT, "",
                  200),
                 (noon + timedelta(hours=1, minutes=3), "198.51.100.52", "/.env", "curl/8.7.1",
                  "", 404)]
        rows = [r + ("example.com",) for r in rows]
        rows.append((noon + timedelta(hours=1, minutes=4), "198.51.100.54", "/v1/x", CHROME, "",
                     200, "api.example.com"))
        records = [record(ts=int(w.timestamp() * 1000) if i % 2 else
                          w.isoformat().replace("+00:00", "Z"),
                          ip=ip, path=path, ua=agent, referer=ref, status=status, host=host,
                          id=f"8c{i:014d}-AMS", cache="MISS")
                   for i, (w, ip, path, agent, ref, status, host) in enumerate(rows)]
        records.append(dict(records[0]))                          # posted twice
        body, _, _ = ingest_drain.convert(json.dumps(records).encode(), "edge",
                                          only_hits=False)
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
            self.assertEqual((figures["requests"], figures["readers"], figures["excluded"]),
                             (8, 4, 1))
        finally:
            box.close()


# ------------------------------------------------------------ the endpoint

class EdgeEndpoint(TenantServer):

    def setUp(self):
        super().setUp()
        db = self.db()
        try:
            site_configs.create(db, self.beta["id"], EDGE_ONLY, "cli", fmt="edge_json")
            site_configs.create(db, self.beta["id"], BOTH, "cli", fmt="auto")
        finally:
            db.close()

    def post(self, site, body: bytes, token=None, gz=False):
        hdrs = {"Content-Type": "application/json"}
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        if gz:
            body = gzip.compress(body)
            hdrs["Content-Encoding"] = "gzip"
        return self.call("POST", f"/traffic-ingest/{site}?format=edge", headers=hdrs, raw=body)

    def test_one_record_a_post_as_the_worker_sends(self):
        token = self.token(self.beta, sites=[EDGE_ONLY])
        for line in FIXTURE.read_text().splitlines():
            got = self.post(EDGE_ONLY, line.encode(), token)
            self.assertEqual(got.status, 200, got.json)
            self.assertFalse(got.json["duplicate"])
        stored = self.stored(EDGE_ONLY)
        self.assertEqual(stored.count(b"\n"), 8)                  # the twin is kept ...
        hits = list(read([self.ingest_root / EDGE_ONLY / "access.log"], "edge_json"))
        self.assertEqual(len(hits), 7)                            # ... and read once
        self.assertNotIn(b"colo", stored)
        # One state entry for all of them, not one per post.
        state = json.loads((self.ingest_root / EDGE_ONLY / ".ingest-state.json").read_text())
        self.assertEqual(list(state["shippers"]), ["edge"])
        self.assertEqual(state["totals"]["accepted"], 8)

    def test_a_batch_gzip(self):
        token = self.token(self.beta, sites=[EDGE_ONLY])
        got = self.post(EDGE_ONLY, FIXTURE.read_bytes(), token, gz=True)
        self.assertEqual(got.json, {"ok": True, "accepted": 8, "rejected": 1, "skipped": 1,
                                    "duplicate": False})

    def test_with_the_origin_only_hits_are_kept(self):
        token = self.token(self.beta, sites=[BOTH])
        got = self.post(BOTH, FIXTURE.read_bytes(), token)
        self.assertEqual((got.json["accepted"], got.json["skipped"]), (5, 4))
        shipped = self.ship(BOTH, token, ("\n".join(ORIGIN) + "\n").encode())
        self.assertEqual(shipped.json["accepted"], 3)
        hits = list(read([self.ingest_root / BOTH / "access.log"], "auto"))
        self.assertEqual(len(hits), 7)
        self.assertEqual(sorted(h.url for h in hits),
                         sorted(["/", "/assets/app.css", "/pricing?plan=pro", "/guides/alpha",
                                 "/guides/alpha", "/", "/.env"]))

    def test_who_may_not_post(self):
        body = json.dumps(record()).encode()
        self.assertEqual(self.post(EDGE_ONLY, body).status, 401)
        self.assertEqual(self.post(EDGE_ONLY, body, self.token(self.alpha)).status, 403)
        # A Vercel drain's signature is no way in for an edge record.
        got = self.call("POST", f"/traffic-ingest/{EDGE_ONLY}?format=edge",
                        headers={"x-vercel-signature": "0" * 40}, raw=body)
        self.assertEqual(got.status, 401)
        # A site that reads nginx lines refuses edge records whole.
        from auth_support import B
        self.assertEqual(self.post(B, body, self.token(self.beta)).status, 400)
        self.assertEqual(self.stored(EDGE_ONLY) + self.stored(B), b"")

    def test_its_own_rate_limit(self):
        self.config["ingest"].update({"edge_per_minute": 60, "edge_burst": 2})
        ingest._BUCKETS.clear()
        token = self.token(self.beta, sites=[EDGE_ONLY])
        codes = [self.post(EDGE_ONLY, json.dumps(record(id=f"r-{i}")).encode(), token).status
                 for i in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        # The shipper's own limit is untouched by the edge's.
        self.assertEqual(self.ship(EDGE_ONLY, token, b"", batch="s1:1").status, 200)


# ------------------------------------------------------------ the Worker

WORKER = ROOT / "deploy" / "cloudflare-worker" / "skald-edge.js"
NETLIFY = ROOT / "deploy" / "netlify-edge-function" / "skald-edge.js"
BEHAVIOUR = ROOT / "tests" / "js" / "skald-edge-worker.mjs"


class Worker(unittest.TestCase):

    def test_the_files_are_there(self):
        for path in (WORKER, NETLIFY, WORKER.parent / "wrangler.toml.example",
                     WORKER.parent / "README.md", BEHAVIOUR):
            self.assertTrue(path.is_file(), path)
        text = WORKER.read_text()
        self.assertIn("ctx.waitUntil(", text)
        self.assertNotIn("await send", text)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_behaviour(self):
        got = subprocess.run(["node", str(BEHAVIOUR)], capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_node_check(self):
        for path in (WORKER, NETLIFY):
            got = subprocess.run(["node", "--input-type=module", "--check"],
                                 input=path.read_text(), capture_output=True, text=True,
                                 timeout=60)
            self.assertEqual(got.returncode, 0, got.stderr)


if __name__ == "__main__":
    unittest.main()
