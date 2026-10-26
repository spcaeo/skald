"""Compression and caching of the dashboard's files (DEPLOY.md, sessions mode).

  * the app's code and the data files go gzipped (a data file's .json.gz is
    sent as written, gzip_static), also to a proxy that asks in HTTP/1.0 (the
    host's nginx in front of the Docker image);
  * the helper's answers are never compressed: they can hold the session's
    CSRF token beside what the request asked for (BREACH);
  * Cache-Control per path ($skald_cache): the code at a versioned address
    for a year (immutable), the data files revalidated every time (no-cache,
    with ETag: a 304 while unchanged), everything else no-store.

The rules are read from DEPLOY.md, then run in a real nginx (when one with
auth_request and gzip_static is installed) in front of a stub helper.
"""
from __future__ import annotations

import gzip
import json
import re
import shutil
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
import test_nginx_routes as nr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = nr.from_deploy()
DASH = [loc for loc in CONFIG.locations if loc.arg == "/traffic/"][0]
IMMUTABLE, REVALIDATE, NEVER = ("private, max-age=31536000, immutable", "private, no-cache",
                                "private, no-store")


def cache_map() -> list[tuple[str, str]]:
    """The $skald_cache map, in order: [(regex or "default", value)]."""
    for name, args, body in nr.parse(CONFIG.http_text):
        if name == "map" and args == ["$request_uri", "$skald_cache"]:
            return [(n, a[0]) for n, a, _ in body]
    raise AssertionError("DEPLOY.md: no map $request_uri $skald_cache")


def cache_for(uri: str) -> str:
    """nginx's map: the first regex that matches, in order, else the default."""
    rules = cache_map()
    for key, value in rules:
        if key.startswith("~") and re.search(key[1:], uri):
            return value
    return dict(rules)["default"]


class Rules(unittest.TestCase):
    def test_cache_control_per_path(self):
        cases = {
            "/traffic/_app/js/main.js?v=0a1b2c3d4e5f": IMMUTABLE,
            "/traffic/_app/app.css?v=0a1b2c3d4e5f": IMMUTABLE,
            "/traffic/_app/js/main.js": REVALIDATE,           # no version: never kept unasked
            "/traffic/_app/js/main.js?v=1&x=2": REVALIDATE,
            "/traffic/shop.example.com/data/overview.json": REVALIDATE,
            "/traffic/shop.example.com/blog/data/pages.json": REVALIDATE,
            "/traffic/shop.example.com/data/slim/not_found.json": REVALIDATE,
            "/traffic/shop.example.com/data/sites.json": NEVER,   # the helper's, per person
            "/traffic/sites.json": NEVER,
            "/traffic/": NEVER,
            "/traffic/shop.example.com/": NEVER,                  # the shell: always this release's
            "/traffic/shop.example.com/index.html": NEVER,
            "/traffic/shop.example.com/classic.html": NEVER,
            "/traffic/build.json": NEVER,
            "/traffic/shop.example.com/me": NEVER,
            "/traffic/shop.example.com/settings/mail": NEVER,
            "/traffic/shop.example.com/api/v1/overview": NEVER,
            "/traffic/shop.example.com/tokens": NEVER,
            "/traffic/shop.example.com/data/../../other/data/x.json": NEVER,
        }
        for uri, want in cases.items():
            with self.subTest(uri=uri):
                self.assertEqual(cache_for(uri), want)

    def test_the_dashboard_sends_the_map(self):
        heads = {a[0]: a[1] for a in DASH.directives("add_header")}
        self.assertEqual(heads["Cache-Control"], "$skald_cache")
        self.assertEqual(DASH.directives("auth_request"), [["/traffic-auth/check"]])

    def test_compression_of_the_dashboard_files(self):
        one = {n: a for n, a, _ in DASH.body}
        for name, want in (("gzip", ["on"]), ("gzip_static", ["on"]), ("gzip_vary", ["on"]),
                           ("gzip_proxied", ["any"]), ("gzip_http_version", ["1.0"])):
            self.assertEqual(one.get(name), want, name)
        level = int(one["gzip_comp_level"][0])
        self.assertTrue(1 <= level <= 6, level)
        for kind in ("application/json", "text/css", "application/javascript", "text/javascript",
                     "image/svg+xml"):
            self.assertIn(kind, one["gzip_types"])

    def test_no_helper_answer_is_compressed(self):
        helpers = [loc for loc in CONFIG.all_locations(DASH.children) if CONFIG.target(loc)]
        self.assertGreaterEqual(len(helpers), 3)
        for loc in helpers:
            with self.subTest(loc=repr(loc)):
                self.assertEqual(loc.directives("gzip"), [["off"]])
                self.assertFalse(loc.directives("add_header"),
                                 "an add_header here drops the dashboard's headers")


# ------------------------------------------------------------- a real nginx

def nginx_usable() -> bool:
    if not shutil.which("nginx"):
        return False
    got = subprocess.run(["nginx", "-V"], capture_output=True, text=True, timeout=10)
    text = got.stdout + got.stderr
    return "http_auth_request_module" in text and "http_gzip_static_module" in text


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class StubHelper(BaseHTTPRequestHandler):
    """Lets every session check through; answers a helper route with a body that
    holds a CSRF token, as /me does."""

    def do_GET(self):
        if self.path.startswith("/traffic-auth/check"):
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = json.dumps({"csrf": "x" * 43, "pad": "y" * 4000}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@unittest.skipUnless(nginx_usable(), "no nginx with auth_request and gzip_static here")
class RealNginx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from skald.files import write_atomic
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        www = base / "www"
        for sub in ("body", "proxy", "fastcgi", "uwsgi", "scgi"):
            (base / sub).mkdir()
        cls.data = json.dumps({"rows": [{"path": f"/p{i}/", "n": i} for i in range(500)]})
        write_atomic(www / "shop.example.com" / "data" / "pages.json", cls.data, pack=True)
        write_atomic(www / "shop.example.com" / "data" / "slim" / "pages.json", cls.data, pack=True)
        write_atomic(www / "_app" / "js" / "main.js", "export const x = 1;\n" * 200, pack=True)
        (www / "shop.example.com" / "index.html").write_text("<!doctype html>" + "<p>x</p>" * 300)
        cls.helper = ThreadingHTTPServer(("127.0.0.1", 0), StubHelper)
        threading.Thread(target=cls.helper.serve_forever, daemon=True).start()
        cls.port = free_port()
        text = (ROOT / "docker" / "nginx.conf").read_text()
        mime = next((p for p in ("/etc/nginx/mime.types", "/opt/homebrew/etc/nginx/mime.types",
                                 "/usr/local/etc/nginx/mime.types") if Path(p).is_file()), None)
        if mime is None:
            raise unittest.SkipTest("no mime.types for nginx")
        text = (text.replace("/etc/nginx/mime.types", mime)
                .replace("/var/www/skald/", f"{www}/")
                .replace("server 127.0.0.1:8765;", f"server 127.0.0.1:{cls.helper.server_address[1]};")
                .replace("/var/log/nginx/skald-beacon.log", str(base / "beacon.log"))
                .replace("/tmp/skald-nginx", str(base)))
        (base / "listen.conf").write_text(f"listen 127.0.0.1:{cls.port};\n")
        (base / "trusted.conf").write_text("")
        (base / "nginx.conf").write_text(text)
        cls.nginx = subprocess.Popen(["nginx", "-p", str(base), "-c", str(base / "nginx.conf"),
                                      "-e", str(base / "error.log"), "-g", "daemon off;"],
                                     stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.nginx.terminate()
        cls.nginx.wait(10)
        cls.helper.shutdown()
        cls.helper.server_close()
        cls.tmp.cleanup()

    def get(self, path, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", headers={
            "Cookie": "skald_session=stub", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_a_data_file_goes_gzipped_and_revalidates(self):
        code, head, body = self.get("/traffic/shop.example.com/data/pages.json",
                                    {"Accept-Encoding": "gzip"})
        self.assertEqual(code, 200)
        self.assertEqual(head["Content-Encoding"], "gzip")
        self.assertEqual(gzip.decompress(body).decode(), self.data)
        self.assertEqual(head["Cache-Control"], REVALIDATE)
        self.assertIn("Accept-Encoding", head["Vary"])
        self.assertTrue(head["ETag"])
        self.assertEqual(head["X-Robots-Tag"], "noindex, nofollow, noarchive")
        again, _, rest = self.get("/traffic/shop.example.com/data/pages.json",
                                  {"Accept-Encoding": "gzip", "If-None-Match": head["ETag"]})
        self.assertEqual((again, rest), (304, b""))

    def test_the_slim_copy_is_served_as_a_data_file(self):
        code, head, body = self.get("/traffic/shop.example.com/data/slim/pages.json",
                                    {"Accept-Encoding": "gzip"})
        self.assertEqual(code, 200)
        self.assertEqual(head["Content-Encoding"], "gzip")
        self.assertEqual(head["Cache-Control"], REVALIDATE)
        self.assertEqual(gzip.decompress(body).decode(), self.data)

    def test_a_browser_without_gzip_gets_the_file(self):
        code, head, body = self.get("/traffic/shop.example.com/data/pages.json")
        self.assertEqual(code, 200)
        self.assertIsNone(head["Content-Encoding"])
        self.assertEqual(body.decode(), self.data)

    def test_a_proxy_asking_in_http_1_0_still_gets_gzip(self):
        with socket.create_connection(("127.0.0.1", self.port), timeout=10) as s:
            s.sendall(b"GET /traffic/shop.example.com/data/pages.json HTTP/1.0\r\nHost: x\r\n"
                      b"Cookie: skald_session=stub\r\nAccept-Encoding: gzip\r\n\r\n")
            raw = b""
            while chunk := s.recv(65536):
                raw += chunk
        head = raw.split(b"\r\n\r\n", 1)[0].decode().lower()
        self.assertIn("content-encoding: gzip", head)

    def test_the_code_is_kept_at_its_versioned_address(self):
        code, head, body = self.get("/traffic/_app/js/main.js?v=0a1b2c3d4e5f",
                                    {"Accept-Encoding": "gzip"})
        self.assertEqual(code, 200)
        self.assertEqual(head["Cache-Control"], IMMUTABLE)
        self.assertEqual(head["Content-Encoding"], "gzip")
        _, plain, _ = self.get("/traffic/_app/js/main.js")
        self.assertEqual(plain["Cache-Control"], REVALIDATE)

    def test_the_shell_is_never_kept(self):
        code, head, _ = self.get("/traffic/shop.example.com/", {"Accept-Encoding": "gzip"})
        self.assertEqual(code, 200)
        self.assertEqual(head["Cache-Control"], NEVER)

    def test_a_helper_answer_is_neither_kept_nor_compressed(self):
        code, head, body = self.get("/traffic/shop.example.com/me", {"Accept-Encoding": "gzip"})
        self.assertEqual(code, 200)
        self.assertEqual(head["Cache-Control"], NEVER)
        self.assertIsNone(head["Content-Encoding"])
        self.assertIn(b'"csrf"', body)


if __name__ == "__main__":
    unittest.main()
