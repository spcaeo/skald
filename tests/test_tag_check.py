"""The script tag's page check (skald/tag_check.py) and its endpoint,
POST <page>/sites/tagcheck (connections_api.py): finding the tag, where it
posts (the same rule as skald.js), and the plain words for each way it fails.
No network: site_fetch's lookup and open_pinned are stubbed. Hosts are
example.com / example.net; addresses public stand-ins or RFC 1918 for refusals."""
from __future__ import annotations

import contextlib
import io
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A  # noqa: E402
from ingest_support import TenantServer  # noqa: E402

from skald import connections_api, site_fetch, tag_check as tc  # noqa: E402

SKALD = "https://skald.example.net"
SITE = "example.com"
ORIGINS = {"https://example.com", "https://www.example.com"}
HTML = "text/html; charset=utf-8"


def page(head: str = "", body: str = "") -> bytes:
    return f"<!doctype html><html><head><title>Hi</title>{head}</head><body>{body}</body></html>".encode()


PLAIN = f'<script src="{SKALD}/traffic-js/skald.js" data-site="example.com" defer></script>'
FIRST_PARTY = '<script src="/traffic-js/skald.js" data-site="example.com" defer></script>'


class Net:
    """{url: (status, headers, body)}; any other URL answers 404. Records each
    call with the headers sent."""

    def __init__(self, answers, names=None):
        self.answers, self.names = answers, names or {}
        self.calls: list[tuple[str, str, dict]] = []

    def lookup(self, host, port):
        return self.names.get(host, ["8.8.8.8"])

    def open(self, scheme, host, address, port, method, target, timeout, max_bytes,
             headers=None):
        url = f"{scheme}://{host}{target}"
        self.calls.append((method, url, dict(headers or {})))
        got = self.answers.get((method, url)) or self.answers.get(url) or (404, {}, b"")
        if isinstance(got, Exception):
            raise got
        status, h, body = got
        return site_fetch.Answer(status, {k.lower(): [v] for k, v in h.items()},
                                 body if method == "GET" else b"", url, address)

    def __enter__(self):
        self._p = mock.patch.multiple(site_fetch, lookup=self.lookup, open_pinned=self.open)
        self._p.start()
        return self

    def __exit__(self, *exc):
        self._p.stop()


def run(answers, origins=ORIGINS, **kw):
    with Net(answers, **kw) as net:
        return tc.check(SITE, origins, SKALD), net


def home(head="", headers=None, at="https://www.example.com/"):
    return {"https://example.com/": (301, {"Location": at}, b""),
            at: (200, {"Content-Type": HTML, **(headers or {})}, page(head))}


class Finding(unittest.TestCase):
    def test_the_tag_and_where_it_posts(self):
        url = "https://www.example.com/pricing/"
        cases = [
            (PLAIN, f"{SKALD}/traffic-js/skald.js", f"{SKALD}/traffic-beacon"),
            (FIRST_PARTY, "https://www.example.com/traffic-js/skald.js",
             "https://www.example.com/traffic-beacon"),
            ('<script defer src="/stats/traffic-js/skald.js"></script>',
             "https://www.example.com/stats/traffic-js/skald.js",
             "https://www.example.com/stats/traffic-beacon"),
            (f"<script src='{SKALD}/traffic-js/skald.js' data-endpoint='/traffic-beacon'></script>",
             f"{SKALD}/traffic-js/skald.js", "https://www.example.com/traffic-beacon"),
            ('<script src="/js/skald.js"></script>', "https://www.example.com/js/skald.js",
             "https://www.example.com/traffic-beacon"),
        ]
        for html, src, posts in cases:
            got = tc.find_tag(page(html).decode(), url)
            self.assertEqual((got["src"], got["how"]), (src, "tag"), html)
            self.assertEqual(tc.endpoint_for(got["src"], got["endpoint"], url), posts, html)

    def test_inside_a_loader(self):
        # Next.js's <Script> list: the address in an inline push, slashes escaped
        html = ('<script>(self.__next_s=self.__next_s||[]).push(["https:\\/\\/skald.example.net'
                '\\/traffic-js\\/skald.js",{"data-site":"example.com","defer":true}])</script>')
        got = tc.find_tag(html, "https://www.example.com/")
        self.assertEqual((got["src"], got["endpoint"], got["how"]),
                         (f"{SKALD}/traffic-js/skald.js", "", "loader"))
        self.assertIsNone(tc.find_tag(page('<script src="/_next/app.js"></script>').decode(),
                                      "https://www.example.com/"))

    def test_csp(self):
        page_origin = "https://www.example.com"
        target = f"{SKALD}/traffic-beacon"
        for policy, ok in (("default-src 'self'", False), ("connect-src 'self' https://skald.example.net", True),
                           ("connect-src *.example.net", True), ("connect-src https:", True),
                           ("default-src 'none'; script-src 'self'", False),
                           ("script-src 'self'", True), ("connect-src 'self'; default-src *", False),
                           ("connect-src https://evil.example.org", False)):
            self.assertEqual(tc.csp_allows([policy], target, page_origin), ok, policy)
        self.assertTrue(tc.csp_allows(["default-src 'self'"], "https://www.example.com/traffic-beacon",
                                      page_origin))


class Checking(unittest.TestCase):
    def test_the_plain_tag_is_right_and_nothing_is_posted(self):
        got, net = run(home(PLAIN))
        self.assertEqual(got["state"], "ok", got)
        self.assertIn("skald.example.net/traffic-beacon", got["words"])
        self.assertEqual(got["facts"]["posts_to"], f"{SKALD}/traffic-beacon")
        self.assertEqual([c[0] for c in net.calls], ["GET", "GET"])    # the redirect, the page

    def test_posting_to_the_site_s_own_address_that_redirects(self):
        """The two live cases: the page posts to its own /traffic-beacon and
        the site's server (Next.js) answers 308 or 405."""
        tag = f'<script src="{SKALD}/traffic-js/skald.js" data-endpoint="/traffic-beacon"></script>'
        for status in (308, 405, 404):
            answers = {**home(tag), ("POST", "https://www.example.com/traffic-beacon"):
                       (status, {"Location": "/traffic-beacon/"} if status == 308 else {}, b"")}
            got, net = run(answers)
            self.assertEqual(got["state"], "problem")
            self.assertEqual(got["words"], "The tag is on your page but posts to "
                             f"www.example.com/traffic-beacon, which answers {status}.")
            self.assertIn("Update to the latest tag in step 2 (it loads from skald.example.net",
                          got["fix"])
            probe = [c for c in net.calls if c[0] == "POST"]
            self.assertEqual(len(probe), 1)
            self.assertEqual(probe[0][2], {"X-Skald-Probe": "1"})

    def test_a_first_party_proxy_that_works(self):
        answers = {**home(FIRST_PARTY),
                   "https://www.example.com/traffic-js/skald.js": (200, {}, b"/* skald */"),
                   ("POST", "https://www.example.com/traffic-beacon"):
                       (200, {"X-Skald-Beacon": "1"}, b"")}
        got, _ = run(answers)
        self.assertEqual(got["state"], "ok", got)

    def test_a_first_party_tag_whose_script_is_not_passed_on(self):
        got, _ = run(home(FIRST_PARTY))
        self.assertEqual(got["state"], "problem")
        self.assertIn("its script, www.example.com/traffic-js/skald.js, answers 404", got["words"])
        self.assertIn("/traffic-js/", got["fix"])

    def test_no_tag_and_a_tag_manager(self):
        got, _ = run(home(""))
        self.assertEqual((got["state"], got["words"]),
                         ("problem", "The tag is not on your home page (www.example.com)."))
        got, _ = run(home('<script async src="https://www.googletagmanager.com/gtm.js?id=GTM-ABC123"></script>'))
        self.assertEqual(got["state"], "unknown")
        self.assertIn("Google Tag Manager", got["words"])

    def test_a_page_host_the_site_does_not_have(self):
        got, _ = run(home(PLAIN), origins={"https://example.com"})
        self.assertEqual(got["state"], "problem")
        self.assertIn("www.example.com, which is not one of example.com's host names", got["words"])
        self.assertIn("Add www.example.com to the site's host names", got["fix"])

    def test_a_content_security_policy_that_blocks_it(self):
        got, _ = run(home(PLAIN, {"Content-Security-Policy": "default-src 'self'; script-src 'self' https://skald.example.net"}))
        self.assertEqual(got["state"], "problem")
        self.assertIn("Content-Security-Policy", got["words"])
        self.assertIn("Add https://skald.example.net to connect-src", got["fix"])
        meta = '<meta http-equiv="Content-Security-Policy" content="connect-src \'self\'">'
        got, _ = run(home(meta + PLAIN))
        self.assertEqual(got["state"], "problem")

    def test_pages_skald_cannot_read(self):
        got, _ = run({"https://example.com/": ConnectionRefusedError("no")})
        self.assertEqual(got["state"], "unknown")
        self.assertIn("could not open example.com", got["words"])
        got, net = run(home(PLAIN), names={"example.com": ["10.0.0.8"]})
        self.assertEqual(got["state"], "unknown")
        self.assertIn("private address", got["words"])
        self.assertEqual(net.calls, [], "nothing fetched from a private address")
        got, _ = run({"https://example.com/": (503, {}, b"")})
        self.assertEqual((got["state"], got["words"]),
                         ("unknown", "Your home page, example.com, answered 503, so Skald could "
                                     "not look for the tag."))

    def test_a_probe_never_carries_a_cookie(self):
        with Net({}) as net:
            site_fetch.fetch("https://www.example.com/traffic-beacon", "POST",
                             headers={"X-Skald-Probe": "1"})
        self.assertEqual(net.calls[0][2], {"X-Skald-Probe": "1"})
        got = {}

        class Conn:
            def __init__(self, *a, **k):
                pass

            def request(self, method, target, headers):
                got.update(headers)
                raise OSError("stop here")

            def close(self):
                pass

        with mock.patch.object(site_fetch, "_PinnedHTTPS", Conn), \
                self.assertRaises(OSError):
            site_fetch.open_pinned("https", "www.example.com", "8.8.8.8", 443, "POST",
                                   "/traffic-beacon", 1, 0,
                                   headers={"X-Skald-Probe": "1", "Cookie": "a=b",
                                            "Authorization": "Bearer x"})
        self.assertEqual(got.get("X-Skald-Probe"), "1")
        self.assertNotIn("Cookie", got)
        self.assertNotIn("Authorization", got)


class Dialog(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_dialog_pieces_in_a_fake_dom(self):
        js = Path(__file__).resolve().parent / "js" / "tag-check.mjs"
        got = subprocess.run(["node", str(js)], capture_output=True, text=True, timeout=120)
        self.assertEqual(got.returncode, 0, got.stdout + got.stderr)
        self.assertIn("tag-check: all passed", got.stdout)


class Api(TenantServer):
    T = f"/traffic/{A}/"

    def test_an_admin_gets_the_check(self):
        self.config["beacon"] = {"origins": [f"https://{A}"]}
        self.config.setdefault("access", {})["base_url"] = SKALD
        answers = {f"https://{A}/": (200, {"Content-Type": HTML}, page(PLAIN))}
        cookie, csrf = self.session("admin@example.com")
        with Net(answers), contextlib.redirect_stderr(io.StringIO()):
            got = self.post(self.T + "sites/tagcheck", {"site": A}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        self.assertEqual(got.json["check"]["state"], "ok")
        self.assertEqual(got.json["check"]["facts"]["posts_to"], f"{SKALD}/traffic-beacon")
        self.assertEqual(connections_api.beacon_origins(self.config, self.config_path, A),
                         {f"https://{A}"})

    def test_rules(self):
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(self.T + "sites/tagcheck", {"site": A}, cookie, csrf).status, 403)
        cookie, csrf = self.session("admin@example.com")
        with Net({}) as net:
            got = self.post(self.T + "sites/tagcheck", {"site": A}, cookie, csrf)
            self.assertEqual(got.status, 409, "the tag is off on this server")
            self.assertEqual(self.post(self.T + "sites/tagcheck", {"site": "nope.example"},
                                       cookie, csrf).status, 404)
        self.assertEqual(net.calls, [])


if __name__ == "__main__":
    unittest.main()
