"""SKALD-34: nginx leaves a Worker's posts to Skald's own per-site edge limit.

nginx limited every post to /traffic-ingest/ to 5 a second per address (burst 20). A
Cloudflare Worker posts once per request from Cloudflare's addresses, which every
Worker-fed site shares, so a scanner burst on one site went over it: on 18 Nov 2026
nginx refused 1,157 of one site's posts, which the Worker never sends again.

Now a post with `?format=edge` is limited per sending token (the Bearer token only that
site's Worker has) at 40 a second, burst 600: above Skald's own edge limit
(ingest.edge_per_minute 1,200, burst 300), so for a Worker Skald's limit, which counts and
says what it refused (tests/test_intake_refusals.py), is the one that refuses. Keyed on
the token, not the path: anyone may post to a site's path, and a path key let a stranger
with no token use up that site's budget so the real Worker was refused uncounted (found in
review). A post with no well-formed token is not counted in that zone. A cap per address
stays (100 a second, burst 1,000) so one address cannot flood the helper. A shipper's
batches keep 5 a second per address.

The config checks run everywhere; the bursts against a real nginx run where one is
installed (in the image: `docker run --user 10001:10001 ...`, as the other nginx tests).
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_nginx_cache import free_port, nginx_usable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = {"DEPLOY.md": (ROOT / "DEPLOY.md").read_text(),
           "docker/nginx.conf": (ROOT / "docker" / "nginx.conf").read_text()}


def ingest_location(text: str) -> str:
    """The /traffic-ingest/ block, nested braces (limit_except) included."""
    start = text.index("location ^~ /traffic-ingest/ {")
    depth = 0
    for i in range(text.index("{", start), len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            return text[start:i + 1]
    raise AssertionError("the location never closes")


class TheConfig(unittest.TestCase):
    def test_edge_posts_have_their_own_keys(self):
        for name, text in CONFIGS.items():
            with self.subTest(config=name):
                # A shipper's batch by address; a Worker's post by site, and by address only as a cap.
                self.assertRegex(text, r"map \$arg_format \$skald_ingest_addr \{\s*edge\s+\"\";\s*default\s+\$binary_remote_addr;\s*\}")
                self.assertIn('map "$arg_format $http_authorization" $skald_ingest_site { '
                              '"~*^edge Bearer\\s+(?<skald_ingest_tok>skald_[A-Za-z0-9_-]{20,120})$" '
                              '$skald_ingest_tok; default ""; }', text)
                self.assertRegex(text, r"map \$arg_format \$skald_ingest_edge_addr \{\s*edge\s+\$binary_remote_addr;\s*default\s+\"\";\s*\}")
                self.assertIn("limit_req_zone $skald_ingest_addr zone=skald_ingest:10m rate=5r/s;", text)
                self.assertIn("limit_req_zone $skald_ingest_site zone=skald_ingest_site:10m rate=40r/s;", text)
                self.assertIn("limit_req_zone $skald_ingest_edge_addr zone=skald_ingest_edge:10m rate=100r/s;", text)
                self.assertNotIn("limit_req_zone $binary_remote_addr zone=skald_ingest:", text)

    def test_the_location_applies_all_three(self):
        for name, text in CONFIGS.items():
            with self.subTest(config=name):
                loc = ingest_location(text)
                self.assertIn("limit_req zone=skald_ingest burst=20 nodelay;", loc)
                self.assertIn("limit_req zone=skald_ingest_site burst=600 nodelay;", loc)
                self.assertIn("limit_req zone=skald_ingest_edge burst=1000 nodelay;", loc)
                self.assertIn("limit_req_status 429;", loc)

    def test_nginx_stays_above_skalds_own_edge_limit(self):
        from skald.ingest_drain import EDGE_BURST, EDGE_PER_MINUTE
        text = CONFIGS["docker/nginx.conf"]
        rate = int(re.search(r"zone=skald_ingest_site:10m rate=(\d+)r/s", text).group(1))
        burst = int(re.search(r"zone=skald_ingest_site burst=(\d+)", text).group(1))
        self.assertGreater(rate * 60, EDGE_PER_MINUTE)
        self.assertGreater(burst, EDGE_BURST)


SHOP = "skald_1_" + "a" * 43            # sending tokens, shaped as accounts/apitokens.py makes them
BLOG = "skald_2_" + "b" * 43


class Helper(BaseHTTPRequestHandler):
    """Every session check passes; every post is taken (200), as Skald's helper would."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@unittest.skipUnless(nginx_usable(), "no nginx with auth_request and gzip_static here")
class RealNginx(unittest.TestCase):
    def setUp(self):
        # A fresh nginx per test: the limits' memory starts empty.
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        for sub in ("body", "proxy", "fastcgi", "uwsgi", "scgi", "www"):
            (base / sub).mkdir()
        self.helper = ThreadingHTTPServer(("127.0.0.1", 0), Helper)
        threading.Thread(target=self.helper.serve_forever, daemon=True).start()
        self.port = free_port()
        text = CONFIGS["docker/nginx.conf"]
        mime = next((p for p in ("/etc/nginx/mime.types", "/opt/homebrew/etc/nginx/mime.types",
                                 "/usr/local/etc/nginx/mime.types") if Path(p).is_file()), None)
        if mime is None:
            raise unittest.SkipTest("no mime.types for nginx")
        text = (text.replace("/etc/nginx/mime.types", mime)
                .replace("/var/www/skald/", f"{base / 'www'}/")
                .replace("server 127.0.0.1:8765;", f"server 127.0.0.1:{self.helper.server_address[1]};")
                .replace("/var/log/nginx/skald-beacon.log", str(base / "beacon.log"))
                .replace("/tmp/skald-nginx", str(base)))
        (base / "listen.conf").write_text(f"listen 127.0.0.1:{self.port};\n")
        (base / "trusted.conf").write_text("")
        (base / "nginx.conf").write_text(text)
        self.nginx = subprocess.Popen(["nginx", "-p", str(base), "-c", str(base / "nginx.conf"),
                                       "-e", str(base / "error.log"), "-g", "daemon off;"],
                                      stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)

    def tearDown(self):
        self.nginx.terminate()
        self.nginx.wait(10)
        self.helper.shutdown()
        self.helper.server_close()
        self.tmp.cleanup()

    def post(self, path, token=None) -> int:
        hdrs = {"Content-Type": "application/json"}
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method="POST",
                                     data=json.dumps({"id": "x"}).encode(), headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def burst(self, paths, token=None) -> list[int]:
        """Post them all at once, from 8 connections: a Worker's burst. `paths` may hold
        (path, token) pairs; else every post carries `token`."""
        jobs = [p if isinstance(p, tuple) else (p, token) for p in paths]
        out: list[int] = [0] * len(jobs)

        def run(k):
            for i in range(k, len(jobs), 8):
                out[i] = self.post(*jobs[i])
        threads = [threading.Thread(target=run, args=(k,)) for k in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return out

    def test_a_workers_burst_for_one_site_is_let_through(self):
        # 18 Nov: a scanner sweep made one site's Worker post ~150 a second.
        got = self.burst(["/traffic-ingest/shop.example.com?format=edge"] * 150, SHOP)
        self.assertEqual(got.count(429), 0, "a burst Skald's own edge limit takes must pass nginx")

    def test_a_stranger_without_the_token_cannot_use_up_a_sites_budget(self):
        # Anyone may post to a site's path. With no token (or a made-up one) the posts
        # count against their own address only, never against the site's Worker.
        stranger = self.burst(["/traffic-ingest/shop.example.com?format=edge"] * 700)
        self.assertEqual(stranger.count(429), 0, "under the address cap")
        worker = self.burst(["/traffic-ingest/shop.example.com?format=edge"] * 150, SHOP)
        self.assertEqual(worker.count(429), 0, "the Worker's own budget is untouched")

    def test_two_sites_bursting_together_do_not_crowd_each_other_out(self):
        paths = [("/traffic-ingest/shop.example.com?format=edge", SHOP),
                 ("/traffic-ingest/blog.example.org?format=edge", BLOG)] * 120
        self.assertEqual(self.burst(paths).count(429), 0)

    def test_a_shippers_batches_are_still_limited_per_address(self):
        got = self.burst(["/traffic-ingest/shop.example.com"] * 60)
        self.assertGreater(got.count(429), 0)
        self.assertGreaterEqual(got.count(200), 20)
        # Another format (a Vercel drain) is limited as a shipper's batch too.
        again = self.burst(["/traffic-ingest/blog.example.org?format=vercel"] * 60)
        self.assertGreater(again.count(429), 0)

    def test_format_edge_is_matched_as_skald_reads_it(self):
        # nginx's map ignores case, as Skald's own reading does (ingest_drain.platform
        # lower-cases it): "Edge" is a Worker post on both sides, never one of each.
        from skald.ingest_drain import platform
        self.assertEqual(platform("/traffic-ingest/x?format=Edge"), "edge")
        got = self.burst(["/traffic-ingest/shop.example.com?format=Edge"] * 150, SHOP)
        self.assertEqual(got.count(429), 0)

    def test_one_address_still_has_a_cap_for_edge_posts(self):
        # Made-up tokens, a new one each post, so only the per-address cap can stop it.
        paths = [("/traffic-ingest/shop.example.com?format=edge", f"skald_9_{i:040d}")
                 for i in range(1500)]
        got = self.burst(paths)
        self.assertGreater(got.count(429), 0, "one address cannot flood the helper")
        self.assertGreaterEqual(got.count(200), 1000)


if __name__ == "__main__":
    unittest.main()
