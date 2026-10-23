"""The site check (skald/site_detect.py) and its endpoint, POST
<page>/sites/detect (connections_api.py): reading each platform and framework
from canned answers, the recommendation table, both names and their
redirects, what is kept in the wizard's progress, and the endpoint's rules
(admins only, CSRF, rate limits). No network: site_fetch's lookup and
open_pinned are stubbed."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_support import A, SAME  # noqa: E402
from ingest_support import TenantServer  # noqa: E402

from skald import connections_api, settings_store, site_detect as d, site_fetch  # noqa: E402
from skald.accounts import site_configs, site_setup  # noqa: E402

PUBLIC = "8.8.8.8"
T = f"/traffic/{A}/"
NEXT_PAGE = (b'<!doctype html><html><head><title>Fox</title>'
             b'<script src="/_next/static/chunks/main.js"></script></head>'
             b'<body><div id="__next"></div></body></html>')
# What the brief saw on an own server: nginx on Ubuntu, Next.js, both names
# answering, no redirect, no Cloudflare proxy.
OWN_NGINX = {"server": "nginx/1.28.3 (Ubuntu)", "x-powered-by": "Next.js",
             "content-type": "text/html; charset=utf-8"}


def h(**headers) -> dict:
    return {k.replace("_", "-").lower(): [v] for k, v in headers.items()}


def page(html: str):
    return d.read_page(html.encode())


class Net:
    """site_fetch's lookup and open_pinned, from canned answers by URL:
    {url: (status, headers, body)}; any other URL of a known name answers 404."""

    def __init__(self, answers, names=None, down=()):
        self.answers = answers
        self.names = names
        self.down = set(down)
        self.calls: list[tuple[str, str]] = []

    def lookup(self, host, port):
        names = self.names or {}
        return names.get(host, [PUBLIC])

    def open(self, scheme, host, address, port, method, target, timeout, max_bytes):
        url = f"{scheme}://{host}{target}"
        self.calls.append((method, url))
        if host in self.down or url in self.down:
            raise ConnectionRefusedError("refused")
        status, headers, body = self.answers.get(url, (404, {}, b""))
        return site_fetch.Answer(status, {k.lower(): [v] for k, v in headers.items()},
                                 body if method == "GET" else b"", url, address)

    def __enter__(self):
        self._p = [mock.patch.object(site_fetch, "lookup", self.lookup),
                   mock.patch.object(site_fetch, "open_pinned", self.open)]
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._p:
            p.stop()


def run(address, answers, **kw):
    err = io.StringIO()
    with Net(answers, **kw) as net, contextlib.redirect_stderr(err):
        got = d.detect(address)
    return got, net, err.getvalue()


class Reading(unittest.TestCase):
    def test_platforms_from_headers_and_pages(self):
        cases = [
            ("cloudflare", h(cf_ray="8a1b2c3d4e5f-LHR", server="cloudflare"), ""),
            ("cloudflare", h(server="cloudflare"), ""),
            ("vercel", h(x_vercel_id="lhr1::abc", server="Vercel"), ""),
            ("vercel", h(server="Vercel"), ""),
            ("netlify", h(x_nf_request_id="01ABC"), ""),
            ("netlify", h(server="Netlify"), ""),
            ("cloudfront", h(via="1.1 abc.cloudfront.net (CloudFront)"), ""),
            ("cloudfront", h(x_amz_cf_id="abc=="), ""),
            ("fastly", h(x_served_by="cache-lhr7342-LHR"), ""),
            ("fastly", h(x_fastly_request_id="abc"), ""),
            ("github_pages", h(server="GitHub.com", x_github_request_id="AB:CD"), ""),
            ("shopify", h(server="cloudflare", cf_ray="1", x_shopid="123"), ""),
            ("shopify", h(server="cloudflare", cf_ray="1"),
             '<link rel="stylesheet" href="//cdn.shopify.com/s/files/x.css">'),
            ("wix", h(x_wix_request_id="1", server="Pepyaka"), ""),
            ("wix", h(), '<meta name="generator" content="Wix.com Website Builder">'),
            ("squarespace", h(server="Squarespace"), ""),
            ("webflow", h(server="cloudflare", cf_ray="1"),
             '<html data-wf-site="abc" data-wf-page="def"><head></head></html>'),
            (None, h(server="nginx/1.28.3 (Ubuntu)", x_powered_by="Next.js"), ""),
            (None, h(server="Apache"), "<html><title>x</title></html>"),
        ]
        for want, headers, html in cases:
            with self.subTest(want=want, headers=headers):
                text, p = page(html)
                self.assertEqual(d.platform_of(headers, text, p), want)

    def test_servers(self):
        for raw, kind, os_name in (("nginx/1.28.3 (Ubuntu)", "nginx", "Ubuntu"),
                                   ("openresty", "nginx", ""),
                                   ("Apache/2.4.58 (Debian)", "apache", "Debian"),
                                   ("LiteSpeed", "litespeed", ""), ("Caddy", "caddy", ""),
                                   ("Microsoft-IIS/10.0", "iis", ""),
                                   ("cloudflare", "unknown", ""), ("", "unknown", "")):
            with self.subTest(raw):
                got = d.server_of(h(server=raw) if raw else {})
                self.assertEqual((got[0], got[2]), (kind, os_name))

    def test_frameworks(self):
        cases = [
            ("nextjs", h(x_powered_by="Next.js"), ""),
            ("nextjs", h(x_nextjs_cache="HIT"), ""),
            ("nextjs", h(), NEXT_PAGE.decode()),
            ("nuxt", h(), '<script src="/_nuxt/entry.js"></script>'),
            ("nuxt", h(x_powered_by="Nuxt"), ""),
            ("wordpress", h(), '<link rel="stylesheet" href="/wp-content/themes/a/style.css">'),
            ("wordpress", h(), '<meta name="generator" content="WordPress 6.6">'),
            ("wordpress", h(link='<https://www.example.com/wp-json/>; rel="https://api.w.org/"'), ""),
            ("gatsby", h(), '<meta name="generator" content="Gatsby 5.13.0"><div id="___gatsby">'),
            ("astro", h(), '<script type="module" src="/_astro/page.js"></script>'),
            ("astro", h(), '<meta name="generator" content="Astro v4.0.0">'),
            ("plain", h(), "<html><head><title>Hello</title></head></html>"),
            (None, h(server="nginx"), ""),
        ]
        for want, headers, html in cases:
            with self.subTest(want=want, html=html[:40]):
                text, p = page(html)
                self.assertEqual(d.framework_of(headers, text, p), want)

    def test_page_asset_suggestions_pass_the_settings_rule(self):
        for kind in d.ASSETS:
            with self.subTest(kind):
                got, _ = d.assets_of(kind, None, {"www.example.com"})
                self.assertEqual(settings_store.validate("site.asset_prefixes", got), got)
        _, p = page('<script src="/assets/app.js"></script><link rel="stylesheet" '
                    'href="/assets/site.css"><link rel="stylesheet" href="/css/x.css">'
                    '<script src="https://www.example.com/static/b.js"></script>'
                    '<script src="https://cdn.example.net/lib.js"></script>'
                    '<link rel="icon" href="/favicon.ico">')
        got, _ = d.assets_of("plain", p, {"www.example.com"})
        self.assertEqual(got, ["/assets/", "/css/", "/static/"])
        _, p = page('<script src="https://cdn.example.net/lib.js"></script>')
        got, note = d.assets_of("plain", p, {"www.example.com"})
        self.assertIsNone(got)
        self.assertIn("another address", note)


class Recommending(unittest.TestCase):
    def facts(self, **kw):
        return {"reachable": True, "server": "unknown", "platform": None, "os": "", **kw}

    def test_the_table(self):
        site = "www.example.com"
        cases = [
            ({"reachable": False, "error": "it did not answer in time"}, None, "could not reach"),
            ({"platform": "shopify"}, "script", "hosted builder"),
            ({"platform": "wix"}, "script", "cannot read its server log"),
            ({"platform": "squarespace"}, "script", "script tag"),
            ({"platform": "webflow"}, "script", "script tag"),
            ({"platform": "cloudflare", "server": "nginx"}, "cloudflare", "Worker"),
            ({"platform": "vercel"}, "vercel", "log drain"),
            ({"platform": "netlify"}, "vercel", "Netlify"),
            ({"platform": "github_pages"}, "script", "no log"),
            ({"platform": "cloudfront", "server": "apache"}, "docker", "cache"),
            ({"platform": "fastly"}, None, "by hand"),
            ({"server": "nginx", "os": "Ubuntu"}, "docker",
             "runs on its own nginx server (Ubuntu), so one command on that server sends its log."),
            ({"server": "apache"}, "docker", "own Apache server"),
            ({"server": "litespeed"}, "docker", "LiteSpeed"),
            ({"server": "caddy"}, "docker", "Caddy"),
            ({"server": "iis"}, "script", "Linux"),
            ({}, None, "could not tell"),
        ]
        for extra, method, words in cases:
            with self.subTest(extra):
                got, why = d.recommend(site, self.facts(**extra))
                self.assertEqual(got, method)
                self.assertIn(words, why)
                self.assertTrue(why.startswith(("www.example.com", "Skald could")), why)
                if got:
                    self.assertIn(got, site_setup.METHODS)


class Detecting(unittest.TestCase):
    def test_an_own_nginx_server_with_next_js_on_both_names(self):
        """The brief's case: the same nginx answers both names, no redirect,
        no proxy in front: the one-command install, both names, /_next/static/."""
        answers = {u: (200, OWN_NGINX, NEXT_PAGE) for u in
                   ("https://example.com/", "https://www.example.com/")}
        got, net, said = run("https://Example.com/pricing", answers)
        self.assertTrue(got["reachable"])
        self.assertEqual(got["site"], "example.com")
        self.assertEqual(got["final_url"], "https://example.com/")
        self.assertTrue(got["https"])
        self.assertEqual(got["hosts"], ["example.com", "www.example.com"])
        self.assertEqual(got["redirects"], [])
        self.assertEqual((got["server"], got["server_detail"], got["os"]),
                         ("nginx", "nginx/1.28.3 (Ubuntu)", "Ubuntu"))
        self.assertIsNone(got["platform"])
        self.assertEqual(got["framework"], "nextjs")
        self.assertEqual(got["asset_prefixes"], ["/_next/static/"])
        self.assertEqual(got["recommended_method"], "docker")
        self.assertEqual(got["reason"], "example.com runs on its own nginx server (Ubuntu), "
                                        "so one command on that server sends its log.")
        # Next.js on its own nginx: the one log_format field for pages opened inside the site.
        self.assertEqual(got["log_note"], d.LOG_NOTE)
        self.assertIn("rsc_prefetch=$http_next_router_prefetch", got["log_note"])
        self.assertIn("rsc_prefetch=%{Next-Router-Prefetch}i", got["log_note"])
        # HEAD said enough (X-Powered-By): no GET was needed.
        self.assertEqual({m for m, _ in net.calls}, {"HEAD"})
        # The log line: the host and the outcome, never an address.
        self.assertEqual(said.strip(), "site check: example.com: nginx, no platform, nextjs -> docker")
        self.assertNotIn(PUBLIC, said)
        self.assertNotIn(PUBLIC, json.dumps(got))

    def test_a_redirect_from_the_bare_name_to_www(self):
        answers = {"https://example.com/": (301, {"Location": "https://www.example.com/"}, b""),
                   "https://www.example.com/": (200, {"Server": "Apache",
                                                      "Content-Type": "text/html"},
                                                b'<link rel="stylesheet" href="/wp-content/a.css">')}
        got, net, _ = run("example.com", answers)
        self.assertEqual(got["final_url"], "https://www.example.com/")
        self.assertEqual(got["hosts"], ["example.com", "www.example.com"])
        self.assertEqual(got["redirects"], [{"from": "example.com", "to": "www.example.com"}])
        self.assertEqual(got["framework"], "wordpress")
        self.assertEqual(got["asset_prefixes"], ["/wp-content/", "/wp-includes/"])
        self.assertIn(("GET", "https://www.example.com/"), net.calls)   # the page was needed
        self.assertEqual(got["recommended_method"], "docker")
        self.assertEqual(got["log_note"], "")        # WordPress: nothing to add

    def test_two_different_sites_are_not_merged(self):
        answers = {"https://example.com/": (200, {"Server": "nginx"}, b"<title>One</title>"),
                   "https://www.example.com/": (200, {"Server": "Caddy"}, b"<title>Two</title>")}
        got, _, _ = run("example.com", answers,
                        names={"example.com": [PUBLIC], "www.example.com": ["2001:4860::1"]})
        self.assertEqual(got["hosts"], ["example.com"])

    def test_a_hosted_builder_gets_the_script_tag_and_no_page_assets(self):
        answers = {"https://www.example.com/": (200, {"Server": "cloudflare", "CF-Ray": "1",
                                                      "X-ShopId": "42"}, b"<title>Shop</title>")}
        got, _, _ = run("www.example.com", answers)
        self.assertEqual((got["platform"], got["recommended_method"]), ("shopify", "script"))
        self.assertTrue(got["hosted_builder"])
        self.assertIsNone(got["asset_prefixes"])
        self.assertIn("cannot read its server log", got["reason"])

    def test_cloudflare_proxied(self):
        answers = {"https://www.example.com/": (200, {"Server": "cloudflare", "CF-Ray": "1",
                                                      "X-Powered-By": "Next.js"}, b"")}
        got, _, _ = run("www.example.com", answers)
        self.assertEqual((got["platform"], got["recommended_method"]), ("cloudflare", "cloudflare"))
        self.assertEqual(got["platform_label"], "Cloudflare (proxied)")
        # Next.js behind the Worker: no nginx log is read, so no log_format line.
        self.assertEqual(got["log_note"], "")

    def test_log_note_only_for_next_js_on_an_own_log_format_server(self):
        base = {"framework": "nextjs", "server": "nginx", "recommended_method": "docker"}
        self.assertEqual(d.log_note(base), d.LOG_NOTE)
        self.assertEqual(d.log_note({**base, "server": "apache"}), d.LOG_NOTE)
        for other in ({"framework": "wordpress"}, {"server": "caddy"},
                      {"recommended_method": "vercel"}, {"framework": None}):
            self.assertEqual(d.log_note({**base, **other}), "", other)

    def test_http_when_https_cannot_connect(self):
        answers = {"http://www.example.com/": (200, {"Server": "nginx"}, b"<title>x</title>")}
        got, _, _ = run("www.example.com", answers,
                        down={"https://www.example.com/", "https://example.com/"})
        self.assertTrue(got["reachable"])
        self.assertFalse(got["https"])
        self.assertEqual(got["final_url"], "http://www.example.com/")

    def test_unreachable_says_so_and_suggests_nothing(self):
        got, _, said = run("www.example.com", {}, down={"www.example.com", "example.com"})
        self.assertFalse(got["reachable"])
        self.assertIsNone(got["recommended_method"])
        self.assertIn("could not reach www.example.com", got["reason"])
        self.assertIn("refused the connection", got["reason"])
        self.assertEqual(said.strip(), "site check: www.example.com: not reachable")

    def test_a_name_inside_the_network_is_never_fetched(self):
        got, net, _ = run("www.example.com", {}, names={"www.example.com": ["10.0.0.8"],
                                                        "example.com": ["127.0.0.1"]})
        self.assertFalse(got["reachable"])
        self.assertEqual(net.calls, [])
        self.assertIn("private address", got["checked"][0]["error"])

    def test_addresses_the_owner_may_type(self):
        self.assertEqual(d.clean_address("HTTPS://www.Example.com/a?b"), "www.example.com")
        for bad in ("", "203.0.113.5", "http://user@www.example.com/", "www.example.com:8080",
                    "localhost", "a b.example.com"):
            with self.subTest(bad), self.assertRaises(ValueError):
                d.clean_address(bad)


class Kept(unittest.TestCase):
    def test_only_known_keys_and_checked_values_are_kept(self):
        got = d.clean_found({"reachable": True, "server": "nginx", "platform": "evil",
                             "framework": "nextjs", "hosts": ["example.com", "bad host"],
                             "asset_prefixes": ["/"], "recommended_method": "rm -rf",
                             "reason": "x" * 999, "extra": "<script>", "use": False,
                             "redirects": [{"from": "example.com", "to": "www.example.com"},
                                           {"from": "x", "to": "?"}],
                             "final_url": "javascript:alert(1)"})
        self.assertNotIn("extra", got)
        self.assertIsNone(got["platform"])
        self.assertEqual(got["hosts"], [])
        self.assertIsNone(got["asset_prefixes"])
        self.assertIsNone(got["recommended_method"])
        self.assertIsNone(got["final_url"])
        self.assertEqual(len(got["reason"]), 300)
        self.assertFalse(got["use"])
        self.assertEqual(got["redirects"], [{"from": "example.com", "to": "www.example.com"}])
        self.assertEqual(got["framework_label"], "Next.js")
        self.assertEqual(got["log_note"], "")
        self.assertEqual(d.clean_found({"log_note": d.LOG_NOTE})["log_note"], d.LOG_NOTE)
        self.assertEqual(d.clean_found({"log_note": "<b>x</b>"})["log_note"], "")


class Api(TenantServer):
    def answers(self):
        return {u: (200, OWN_NGINX, NEXT_PAGE) for u in
                ("https://shop.example.org/", "https://www.shop.example.org/")}

    def test_an_admin_gets_the_facts(self):
        cookie, csrf = self.session("admin@example.com")
        with Net(self.answers()), contextlib.redirect_stderr(io.StringIO()):
            got = self.post(T + "sites/detect", {"address": "shop.example.org"}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        found = got.json["found"]
        self.assertEqual((found["recommended_method"], found["hosts"]),
                         ("docker", ["shop.example.org", "www.shop.example.org"]))
        self.assertEqual(self.post(T + "sites/detect", {"address": "203.0.113.9"}, cookie,
                                   csrf).status, 400)

    def test_admins_only_with_csrf_and_same_origin(self):
        cookie, csrf = self.session("viewer@example.com")
        self.assertEqual(self.post(T + "sites/detect", {"address": "shop.example.org"}, cookie,
                                   csrf).status, 403)
        cookie, csrf = self.session("admin@example.com")
        with Net(self.answers()) as net:
            self.assertEqual(self.call("POST", T + "sites/detect", {"address": "x.example.org"},
                                       SAME, cookie=cookie).status, 403)              # no CSRF
            self.assertEqual(self.call("POST", T + "sites/detect", {"address": "x.example.org"},
                                       cookie=cookie, csrf=csrf).status, 403)     # cross-site
            self.assertEqual(self.call("GET", T + "sites/detect", cookie=cookie).status, 405)
            self.assertEqual(self.call("POST", T + "sites/detect", {"address": "x.example.org"},
                                       SAME).status, 401)                    # not signed in
        self.assertEqual(net.calls, [])

    def test_rate_limits_per_admin_and_per_address(self):
        cookie, csrf = self.session("admin@example.com")
        with Net(self.answers()), contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.object(connections_api, "DETECT_PER_TARGET", 2):
            codes = [self.post(T + "sites/detect", {"address": "shop.example.org"}, cookie,
                               csrf).status for _ in range(3)]
            self.assertEqual(codes, [200, 200, 429])
            owner, owner_csrf = self.session("owner@example.com")     # anyone: per address
            got = self.post(T + "sites/detect", {"address": "shop.example.org"}, owner,
                            owner_csrf)
            self.assertEqual(got.status, 429)
            self.assertIn("checked many times", got.json["error"])
        with Net(self.answers()), contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.object(connections_api, "DETECT_PER_ADMIN", 2):
            got = self.post(T + "sites/detect", {"address": "other.example.org"}, cookie, csrf)
            self.assertEqual(got.status, 429)      # 2 checks this hour; the refused one not counted
            self.assertIn("Too many site checks", got.json["error"])

    def test_the_facts_are_kept_only_in_existing_progress(self):
        cookie, csrf = self.session("admin@example.com")
        with Net(self.answers()), contextlib.redirect_stderr(io.StringIO()):
            self.post(T + "sites/detect", {"address": "shop.example.org", "name": A}, cookie, csrf)
        db = self.accounts_db()
        try:
            self.assertIsNone(site_setup.get(db, A))           # no progress row was made
        finally:
            db.close()
        self.assertEqual(self.post(T + "sites/setup", {"name": A, "step": 3}, cookie,
                                   csrf).status, 200)
        with Net(self.answers()), contextlib.redirect_stderr(io.StringIO()):
            self.post(T + "sites/detect", {"address": "shop.example.org", "name": A}, cookie, csrf)
        listed = self.call("GET", T + "sites", cookie=cookie).json
        kept = next(s for s in listed["sites"] if s["name"] == A)["setup"]["found"]
        self.assertEqual((kept["recommended_method"], kept["use"]), ("docker", True))
        got = self.post(T + "sites/setup", {"name": A, "found": {**kept, "use": False,
                                                                 "platform": "nope"}},
                        cookie, csrf)
        self.assertEqual(got.status, 200)
        self.assertEqual((got.json["setup"]["found"]["use"], got.json["setup"]["found"]["platform"]),
                         (False, None))
        self.assertEqual(got.json["setup"]["step"], 3)

    def test_add_takes_the_found_hosts_and_page_assets(self):
        cookie, csrf = self.session("admin@example.com")
        got = self.post(T + "sites/add", {"host": "shop.example.org", "token": False,
                                          "hosts": ["shop.example.org", "www.shop.example.org"],
                                          "asset_prefixes": ["/_next/static/"]}, cookie, csrf)
        self.assertEqual(got.status, 200, got.json)
        db = self.accounts_db()
        try:
            self.assertEqual(site_configs.get(db, "shop.example.org")["hosts"],
                             ["shop.example.org", "www.shop.example.org"])
            self.assertEqual(settings_store.get(db, "site:shop.example.org",
                                                "site.asset_prefixes"), ["/_next/static/"])
        finally:
            db.close()
        bad = self.post(T + "sites/add", {"host": "two.example.org", "asset_prefixes": ["/"]},
                        cookie, csrf)
        self.assertEqual(bad.status, 400)
        db = self.accounts_db()
        try:
            self.assertIsNone(site_configs.get(db, "two.example.org"))      # nothing was made
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
