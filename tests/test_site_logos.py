"""Site logos (2.6.0): site_logos.py, logo_image.py, logo_api.py, site_picker.py.

  * what a logo's bytes are: PNG and ICO kept, a risky SVG refused, sizes
  * asking the site: a fake server on 127.0.0.1, the icon its page names,
    the size cap, a redirect to another host refused, the Content-Type
    checked, a private address refused unless the test allows it
  * the routes over real HTTP (sessions mode): the image with its own CSP,
    upload and "check now" for owners and admins only, with CSRF, audited
  * the picker's data: today's visitors, leads and demos booked read from
    live.json and conversions.json, "-" (null) when not known

Addresses are 127.0.0.1 (the test server) and example names; no secret.
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import tempfile
import threading
import unittest
import zlib
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, B, Server  # noqa: E402

from skald import logo_image, site_logos, site_picker, settings_store  # noqa: E402
from skald.accounts import auditlog  # noqa: E402

T = f"/traffic/{A}/"


def png(w: int, h: int) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    rows = b"".join(b"\x00" + b"\x10\x20\x30" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def ico(size: int) -> bytes:
    inner = png(size, size)
    entry = struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(inner), 22)
    return b"\x00\x00\x01\x00\x01\x00" + entry + inner


SAFE_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            b'<defs><linearGradient id="g"><stop offset="0" stop-color="#0f766e"/></linearGradient>'
            b'</defs><rect width="24" height="24" rx="5" fill="url(#g)"/>'
            b'<path d="M3 6l4.5 12L12 8" stroke="#fff"/></svg>')
RISKY = {
    "script": b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"><script>alert(1)</script></svg>',
    "onload": b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9" onload="alert(1)"/>',
    "foreignObject": (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"><foreignObject>'
                      b'<p xmlns="http://www.w3.org/1999/xhtml">x</p></foreignObject></svg>'),
    "external image": (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/'
                       b'xlink" viewBox="0 0 9 9"><image xlink:href="https://evil.example/x.png"/></svg>'),
    "external use": (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">'
                     b'<use href="https://evil.example/s.svg#a"/></svg>'),
    "css import": (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"><style>'
                   b'@import url(https://evil.example/a.css);</style></svg>'),
    "url fill": (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">'
                 b'<rect fill="url(https://evil.example/p#a)"/></svg>'),
    "javascript link": (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">'
                        b'<a href="javascript:alert(1)"><rect/></a></svg>'),
    "entity": (b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaa">]>'
               b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9">&a;</svg>'),
    "stylesheet pi": (b'<?xml version="1.0"?><?xml-stylesheet href="https://evil.example/a.css"?>'
                      b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"/>'),
    "animation": (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 9"><a><set '
                  b'attributeName="href" to="javascript:alert(1)"/></a></svg>'),
    "html script": (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:h="http://www.w3.org/1999/xhtml" '
                    b'viewBox="0 0 9 9"><h:script>alert(1)</h:script></svg>'),
}


# ------------------------------------------------------------ the bytes

class Images(unittest.TestCase):
    def test_types_by_their_first_bytes_and_sizes(self):
        self.assertEqual(logo_image.check(png(180, 180)), ("png", (180, 180)))
        self.assertEqual(logo_image.check(ico(48)), ("ico", (48, 48)))
        self.assertEqual(logo_image.check(b"GIF89a" + struct.pack("<HH", 32, 32) + b"\0" * 8)[0],
                         "gif")
        with self.assertRaises(logo_image.Refused):
            logo_image.check(b"<html><body>not an icon</body></html>")

    def test_an_upload_is_png_ico_or_safe_svg_square_and_big_enough(self):
        self.assertEqual(logo_image.check_upload(png(128, 128), 256 * 1024)[0], "png")
        self.assertEqual(logo_image.check_upload(ico(64), 256 * 1024)[0], "ico")
        self.assertEqual(logo_image.check_upload(SAFE_SVG, 256 * 1024)[0], "svg")
        for body, words in ((png(32, 32), "at least 64"), (png(200, 100), "square"),
                            (b"GIF89a" + struct.pack("<HH", 99, 99) + b"\0" * 8, "type"),
                            (png(300, 300) + b"\0" * 300_000, "over 256 KB"), (b"", "empty")):
            with self.assertRaises(logo_image.Refused) as got:
                logo_image.check_upload(body, 256 * 1024)
            self.assertIn(words, str(got.exception))

    def test_every_risky_svg_is_refused(self):
        for name, body in RISKY.items():
            with self.subTest(name), self.assertRaises(logo_image.Refused):
                logo_image.check_svg(body)
        logo_image.check_svg(SAFE_SVG)        # a drawing passes


# ------------------------------------------------------------ the site

class FakeSite(BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):
        got = self.routes.get(self.path)
        if got is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        status, headers, body = got
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v.replace("PORT", str(self.server.server_address[1])))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class Fetching(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        FakeSite.routes = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSite)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def route(self, path, body, ctype="image/png", status=200, **headers):
        FakeSite.routes[path] = (status, {"Content-Type": ctype, **headers}, body)

    def fetcher(self, **kw):
        return site_logos.Fetcher(["127.0.0.1"], scheme="http", port=self.port,
                                  allow_private=kw.pop("allow_private", True), **kw)

    def home(self, links):
        self.route("/", f"<html><head>{links}</head><body><link rel=icon href=/late.png>"
                   "</body></html>".encode(), "text/html; charset=utf-8")

    def test_the_icon_the_home_page_names_comes_first(self):
        self.home('<link rel="icon" href="/fav.png" sizes="32x32">'
                  '<link rel="apple-touch-icon" href="/touch.png" sizes="180x180">')
        self.route("/touch.png", png(180, 180))
        self.route("/fav.png", png(32, 32))
        got = site_logos.find(self.fetcher(), "127.0.0.1")
        self.assertEqual((got["kind"], got["size"]), ("png", (180, 180)))
        self.assertTrue(got["url"].endswith("/touch.png"))

    def test_then_apple_touch_icon_then_favicon(self):
        self.route("/favicon.ico", ico(32), "image/x-icon")
        got = site_logos.find(self.fetcher(), "127.0.0.1")       # no home page at all
        self.assertTrue(got["url"].endswith("/favicon.ico"))
        self.route("/apple-touch-icon.png", png(180, 180))
        self.assertTrue(site_logos.find(self.fetcher(), "127.0.0.1")["url"]
                        .endswith("/apple-touch-icon.png"))

    def test_an_image_over_the_cap_is_refused(self):
        self.home('<link rel="apple-touch-icon" href="/big.png">')
        self.route("/big.png", png(180, 180) + b"\0" * (site_logos.MAX_IMAGE + 10))
        self.route("/favicon.ico", ico(32), "image/x-icon")
        got = site_logos.find(self.fetcher(), "127.0.0.1")
        self.assertTrue(got["url"].endswith("/favicon.ico"))
        FakeSite.routes.pop("/favicon.ico")
        with self.assertRaises(site_logos.FetchError):
            site_logos.find(self.fetcher(), "127.0.0.1")

    def test_a_redirect_to_another_host_is_refused(self):
        self.route("/favicon.ico", b"", status=302, Location="http://localhost:PORT/x.ico")
        FakeSite.routes["/x.ico"] = (200, {"Content-Type": "image/x-icon"}, ico(32))
        with self.assertRaises(site_logos.FetchError) as got:
            self.fetcher().get(f"http://127.0.0.1:{self.port}/favicon.ico", 1000)
        self.assertIn("not one of the site's hosts", str(got.exception))
        # the same host is fine
        self.route("/favicon.ico", b"", status=301, Location="/x.ico")
        self.assertEqual(self.fetcher().get(f"http://127.0.0.1:{self.port}/favicon.ico",
                                            100_000)[0], 200)

    def test_redirects_are_limited(self):
        for i in range(6):
            self.route(f"/r{i}", b"", status=302, Location=f"/r{i + 1}")
        with self.assertRaises(site_logos.FetchError) as got:
            self.fetcher().get(f"http://127.0.0.1:{self.port}/r0", 1000)
        self.assertIn("redirects", str(got.exception))

    def test_the_content_type_must_say_image(self):
        self.route("/favicon.ico", ico(32), "text/html")
        with self.assertRaises(site_logos.FetchError) as got:
            site_logos.find(self.fetcher(), "127.0.0.1")
        self.assertIn("not an image", str(got.exception))
        self.route("/favicon.ico", b"<html>hello</html>", "image/x-icon")   # type lies
        with self.assertRaises(site_logos.FetchError):
            site_logos.find(self.fetcher(), "127.0.0.1")

    def test_a_private_address_is_never_asked(self):
        self.route("/favicon.ico", ico(32), "image/x-icon")
        with self.assertRaises(site_logos.FetchError) as got:
            self.fetcher(allow_private=False).get(f"http://127.0.0.1:{self.port}/favicon.ico", 999)
        self.assertIn("private address", str(got.exception))

    def test_check_keeps_the_file_and_the_state(self):
        self.route("/apple-touch-icon.png", png(180, 180))
        now = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
        state = site_logos.check({}, "shop.example.net", self.base, now, self.fetcher())
        self.assertTrue(state["ok"])
        config = {"site": {"name": "shop.example.net"}}
        got = site_logos.entry(config, "shop.example.net", self.base)
        self.assertEqual((got["kind"], got["letter"], got["source"]), ("png", "S", "auto"))
        self.assertTrue(got["url"].startswith("shop.example.net/logo?v="))
        self.assertFalse(site_logos.due(state, now + timedelta(days=6)))
        self.assertTrue(site_logos.due(state, now + timedelta(days=7)))
        self.assertEqual(site_logos.checked_recently(self.base, "shop.example.net",
                                                     now + timedelta(seconds=20)), 40)
        # the letter when chosen, and when nothing was found
        letter = {"site": {"name": "shop.example.net", "logo_source": "letter"}}
        self.assertIsNone(site_logos.entry(letter, "shop.example.net", self.base)["url"])
        FakeSite.routes.clear()
        failed = site_logos.check({}, "shop.example.net", self.base, now, self.fetcher())
        self.assertFalse(failed["ok"])
        self.assertTrue(site_logos.due(failed, now + timedelta(days=1)))

    def test_only_the_sites_own_public_host_names_are_asked(self):
        config = {"site": {"hosts": ["www.shop.org", "192.0.2.7", "shop.org:8443", "x.example.com",
                                     "intranet.local"]}}
        self.assertEqual(site_logos.hosts_of(config, "shop.org"), ["shop.org", "www.shop.org"])
        self.assertEqual(site_logos.hosts_of({}, "example.com"), [])


# ------------------------------------------------------- the routes, HTTP

class Routes(Server):
    def test_no_logo_is_404_and_needs_a_session(self):
        self.assertEqual(self.call("GET", T + "logo").status, 401)
        cookie = self.login().cookie
        self.assertEqual(self.call("GET", T + "logo", cookie=cookie).status, 404)
        bob = self.login("bob@example.com").cookie
        self.assertEqual(self.call("GET", T + "logo", cookie=bob).status, 403)

    def test_an_owner_uploads_and_the_image_is_served_safely(self):
        cookie, csrf = self.session()
        body = {"data": base64.b64encode(SAFE_SVG).decode(), "name": "logo.svg"}
        self.assertEqual(self.post(T + "logo/upload", body, cookie, None).status, 403)  # no CSRF
        got = self.post(T + "logo/upload", body, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["source"], "upload")
        img = self.call("GET", "/traffic/" + got.json["logo"]["url"], cookie=cookie)
        self.assertEqual(img.status, 200)
        self.assertEqual(img.header("Content-Type"), "image/svg+xml")
        self.assertEqual(img.header("X-Content-Type-Options"), "nosniff")
        self.assertIn("sandbox", img.header("Content-Security-Policy"))
        self.assertIn("default-src 'none'", img.header("Content-Security-Policy"))
        self.assertEqual(img.raw, SAFE_SVG)
        db = self.db()
        try:
            actions = [r["action"] for r in auditlog.recent(db, self.alpha["id"])]
        finally:
            db.close()
        self.assertIn("logo.upload", actions)
        self.assertIn("setting.change", actions)

    def test_risky_or_wrong_files_are_refused(self):
        cookie, csrf = self.session()
        for body in (RISKY["script"], RISKY["onload"], png(16, 16), b"plain text"):
            got = self.post(T + "logo/upload", {"data": base64.b64encode(body).decode()},
                            cookie, csrf)
            self.assertEqual(got.status, 400, got.json)
        got = self.post(T + "logo/upload", {"data": "not base64!"}, cookie, csrf)
        self.assertEqual(got.status, 400)

    def test_a_viewer_reads_but_cannot_change(self):
        cookie, csrf = self.session("viewer@example.com")
        state = self.call("GET", T + "logo/state", cookie=cookie)
        self.assertEqual(state.status, 200)
        self.assertFalse(state.json["editable"])
        body = {"data": base64.b64encode(png(64, 64)).decode()}
        self.assertEqual(self.post(T + "logo/upload", body, cookie, csrf).status, 403)
        self.assertEqual(self.post(T + "logo/check", {}, cookie, csrf).status, 403)

    def test_check_now_is_limited_to_once_a_minute(self):
        cookie, csrf = self.session("admin@example.com")
        first = self.post(T + "logo/check", {}, cookie, csrf)        # alpha.example: no host
        self.assertEqual(first.status, 200, first.json)
        self.assertIsNone(first.json["found"])
        self.assertIn("no host name", first.json["error"])
        self.assertEqual(self.post(T + "logo/check", {}, cookie, csrf).status, 429)
        self.assertEqual(self.call("GET", T + "logo/check", cookie=cookie).status, 405)

    def test_the_settings_keys(self):
        self.assertEqual(settings_store.validate("site.logo.source", "letter"), "letter")
        self.assertEqual(settings_store.validate("site.logo.color", "#0f766e"), "#0f766e")
        for key, bad in (("site.logo.source", "gravatar"), ("site.logo.color", "#ff0000")):
            with self.assertRaises(settings_store.Invalid):
                settings_store.validate(key, bad)


# ------------------------------------------------------------- the picker

def live_json(day="2026-10-12", readers=12, state="ok", made="2026-10-12T13:58:00+00:00"):
    return {"schema_version": 1, "state": state, "day": day, "stale": False,
            "timezone": "America/New_York", "generated_at": made, "people": {"readers": readers}}


def conversions_json(day="2026-10-12", state="ok"):
    entry = {"day": day, "state": state}
    if state == "ok":
        entry["stages"] = {"contact": {"started": 3, "completed": 1}, "demo": {"completed": 1},
                           "cta": {"completed": 5}, "signup": {"completed": 1, "cancelled": 2}}
    return {"schema_version": 1, "available": True, "finished": ["completed", "paid"],
            "lead_actions": ["contact", "signup", "waitlist", "trial", "demo"],
            "demo_actions": ["demo"], "days": [entry]}


class Picker(Server):
    NOW = datetime(2026, 10, 12, 14, 0, tzinfo=timezone.utc)

    def write(self, site, **files):
        for name, body in files.items():
            (self.out / site / "data" / f"{name}.json").write_text(json.dumps(body))

    def test_today_is_read_never_counted_and_dash_when_unknown(self):
        self.write(A, live=live_json(), conversions=conversions_json())
        got = site_picker.today(self.out, A, self.NOW)
        self.assertEqual((got["visitors"], got["leads"], got["demos"], got["live"]),
                         (12, 3, 1, True))
        self.write(A, conversions=conversions_json(state="withheld"))
        self.assertEqual(site_picker.today(self.out, A, self.NOW)["leads"], None)
        self.write(A, live=live_json(day="2026-10-11"))             # yesterday's count
        got = site_picker.today(self.out, A, self.NOW)
        self.assertEqual((got["visitors"], got["leads"], got["live"]), (None, None, False))
        self.assertEqual(site_picker.today(self.out, B, self.NOW)["visitors"], None)
        later = site_picker.today(self.out, A, self.NOW + timedelta(minutes=30))
        self.assertFalse(later["live"])

    def test_the_page_shows_logo_figures_and_dashes(self):
        sites = [{"name": A, "path": f"{A}/", "views": [{"slug": "blog", "name": "Blog"}],
                  "logo": {"url": f"{A}/logo?v=abc", "letter": "A", "color": "#0f766e"},
                  "today": {"visitors": 12, "leads": 1, "demos": 0, "live": True,
                            "timezone": "America/New_York"}},
                 {"name": B, "path": f"{B}/", "logo": {"url": None, "letter": "B",
                                                       "color": "#9a6400"}, "today": {}}]
        page = site_picker.render(sites, self.NOW, "owner@example.com", f"{A}/#settings/sitesadmin")
        self.assertIn(f'src="{A}/logo?v=abc"', page)
        self.assertIn("New York time", page)
        self.assertIn(">12</dd>", page)
        self.assertIn("<dt>lead</dt><dd>1</dd>", page)
        self.assertIn("not recorded for today yet", page)
        self.assertIn("Add a site", page)
        self.assertIn("1 view", page)
        self.assertNotIn("<script", page)

    def test_the_helper_answers_with_logo_and_today_for_the_callers_sites_only(self):
        listed = [{"name": s, "slug": s, "path": f"{s}/", "views": []} for s in (A, B)]
        for where, current in ((self.out / "sites.json", None),
                               (self.out / A / "data" / "sites.json", A)):
            where.write_text(json.dumps({"schema_version": 1, "sites": listed, "current": current}))
        self.write(A, live=live_json(day=datetime.now(timezone.utc).astimezone().date()
                                     .isoformat()))
        cookie = self.login().cookie
        got = self.call("GET", T + "data/sites.json", cookie=cookie)
        self.assertEqual([s["name"] for s in got.json["sites"]], [A])
        site = got.json["sites"][0]
        self.assertEqual(site["logo"]["letter"], "A")
        self.assertIsNone(site["logo"]["url"])
        self.assertIn("visitors", site["today"])
        page = self.call("GET", "/traffic/", cookie=cookie).raw.decode()
        self.assertIn("Choose a site", page)
        self.assertIn(A, page)
        self.assertNotIn(B, page)
        self.assertIn("owner@example.com", page)


if __name__ == "__main__":
    unittest.main()
