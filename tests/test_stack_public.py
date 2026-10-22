"""The public "Is my site exposed?" check (stack_public.py, stack_public_api.py, 2.22).

It fetches addresses strangers type, so most of this file is refusals: every way to point it
inside a network (literal addresses in every form, names that resolve inside, a name that
changes its answer between the check and the connection, a redirect inside, odd ports),
then its limits (time, size, requests), the rate limits and the cache, the HTTP side on
the beacon helper, and a happy path against a fake server on this machine.

No network: names resolve through a stub. RFC 5737 / RFC 3849 documentation addresses
stand for public ones here (a wrapper lets them through; every other rule is the real one).
"""
from __future__ import annotations

import http.client
import http.server
import json
import shlex
import socket
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import advisories, site_fetch, stack_public as sp  # noqa: E402
from skald import stack_public_api as api  # noqa: E402
from skald.beacon_server import Limiter, Sink, make_handler  # noqa: E402

NOW = datetime(2026, 10, 21, 18, tzinfo=timezone.utc)
PUBLIC, PUBLIC2, PUBLIC6 = "192.0.2.10", "198.51.100.20", "2001:db8::10"
TESTNET = {PUBLIC, PUBLIC2, PUBLIC6}
ORIGIN = "https://www.example.com"
CONFIG = {"security": {"public_check": True, "public_check_origins": [ORIGIN],
                       "public_check_info_url": "https://www.example.com/check/"}}
WP_HOME = (b'<html><head><meta name="generator" content="WordPress 6.4.2"></head>'
           b'<body><img src="https://wp.example.com/wp-content/uploads/a.png">'
           b'<img src="https://cdn.example.net/wp-content/uploads/b.png"></body></html>')
real_refused = site_fetch.address_refused


def doc_refused(text):
    """Documentation addresses stand for public ones; every other address, the real rule."""
    return None if str(text) in TESTNET else real_refused(text)


class Net:
    """lookup and open_pinned stand-ins. names: host -> [addresses] (or a list of such lists,
    one per lookup); pages: (method, url) or url -> (status, headers, body)."""

    def __init__(self, names=None, pages=None):
        self.names, self.pages = names or {}, pages or {}
        self.looked: list[str] = []
        self.opened: list[dict] = []

    def lookup(self, host, port):
        self.looked.append(host)
        got = self.names.get(host)
        if got is None:
            raise socket.gaierror("no such name")
        if got and isinstance(got[0], list):
            return list(got.pop(0) if len(got) > 1 else got[0])
        return list(got)

    def open(self, scheme, host, address, port, method, target, timeout, max_bytes, agent=None):
        url = f"{scheme}://{host}{target}"
        self.opened.append({"url": url, "address": address, "method": method, "agent": agent,
                            "timeout": timeout, "max_bytes": max_bytes})
        status, headers, body = self.pages.get((method, url)) or self.pages.get(url) \
            or (404, {}, b"")
        return site_fetch.Answer(status, {k.lower(): [v] for k, v in headers.items()},
                                 body if method == "GET" else b"", url, address)

    def __enter__(self):
        self._p = [mock.patch.object(site_fetch, "lookup", self.lookup),
                   mock.patch.object(site_fetch, "open_pinned", self.open),
                   mock.patch.object(site_fetch, "address_refused", doc_refused)]
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._p:
            p.stop()


def run(raw, net):
    with net:
        return sp.check(raw, CONFIG, advisories.load(), NOW)


class Addresses(unittest.TestCase):
    def test_typed_addresses_that_are_refused_before_any_lookup(self):
        cases = [
            "", "   ", "a b.com", "x" * 600 + ".com",
            "http://127.0.0.1/", "127.0.0.1", "http://[::1]/", "http://[::ffff:127.0.0.1]/",
            "http://[::ffff:a00:1]/", "http://[fd00:ec2::254]/", "http://169.254.169.254/",
            "http://2130706433/", "http://017700000001/", "http://0x7f000001/", "http://0x7f.1/",
            "http://127.1/", "http://10.1/", "203.0.113.9",
            "localhost", "http://localhost:8080/", "http://foo.localhost/", "printer.local",
            "db.internal", "nas.home.arpa", "router.lan", "site.test", "x.invalid", "corp",
            "ftp://example.com/", "file:///etc/passwd", "javascript:alert(1)", "gopher://example.com/",
            "https://user:pw@example.com/", "https://example.com@10.0.0.1/",
            "https://example.com:8443/", "http://example.com:22/", "http://example.com:0/",
        ]
        net = Net()
        for raw in cases:
            with self.subTest(raw), net:
                with self.assertRaises(sp.Refused):
                    sp.check(raw, CONFIG, advisories.load(), NOW)
        self.assertEqual(net.looked, [], "nothing typed above is even looked up")
        self.assertEqual(net.opened, [])

    def test_the_typed_forms_that_are_accepted(self):
        for raw, want in (("example.com", ("https", "example.com")),
                          ("https://www.example.com/some/page?q=1", ("https", "www.example.com")),
                          ("http://example.com", ("http", "example.com")),
                          ("Example.COM.", ("https", "example.com")),
                          ("example.com:443", ("https", "example.com"))):
            with self.subTest(raw):
                self.assertEqual(sp.target(raw), want)

    def test_names_that_resolve_inside_are_refused_whole(self):
        inside = {"a.example.com": ["10.0.0.5"], "b.example.com": ["127.0.0.1"],
                  "c.example.com": ["169.254.169.254"], "d.example.com": ["fd00:ec2::254"],
                  "e.example.com": ["::ffff:127.0.0.1"], "f.example.com": ["::ffff:10.0.0.1"],
                  "g.example.com": ["100.64.1.1"], "h.example.com": ["fe80::1"],
                  "i.example.com": ["224.0.0.1"], "j.example.com": ["0.0.0.0"],
                  "k.example.com": ["::1"], "l.example.com": ["240.0.0.1"],
                  "m.example.com": ["2002:7f00:1::"], "n.example.com": ["64:ff9b::a00:1"],
                  "o.example.com": [PUBLIC, "192.168.1.1"]}       # one inside is enough
        for host in inside:
            net = Net(names=dict(inside))
            with self.subTest(host):
                with self.assertRaises(sp.Refused):
                    run(host, net)
                self.assertEqual(net.opened, [], "never connected")

    def test_a_name_that_changes_its_answer_cannot_rebind(self):
        """The name is resolved once per request, and the connection goes to the address
        that passed: a second answer (inside) is never asked for or used."""
        net = Net(names={"www.example.com": [[PUBLIC], ["127.0.0.1"]]},
                  pages={"https://www.example.com/": (200, {"Server": "nginx"}, b"<html></html>")})
        got = run("www.example.com", net)
        self.assertTrue(got["reached"])
        self.assertEqual(net.looked, ["www.example.com"])
        self.assertEqual([o["address"] for o in net.opened], [PUBLIC])
        # The other way round: inside at the check, public afterwards: refused, never opened.
        net = Net(names={"www.example.com": [["10.0.0.1"], [PUBLIC]]})
        with self.assertRaises(sp.Refused):
            run("www.example.com", net)
        self.assertEqual(net.opened, [])

    def test_a_rebinding_redirect_is_checked_again(self):
        """Each hop is a new lookup and a new check: the same name answering inside on its
        second lookup is refused at that hop."""
        net = Net(names={"www.example.com": [[PUBLIC], ["127.0.0.1"]]},
                  pages={"https://www.example.com/": (302, {"Location": "/home"}, b"")})
        with self.assertRaises(sp.Refused):
            run("www.example.com", net)
        self.assertEqual([o["address"] for o in net.opened], [PUBLIC])

    def test_redirects_inside_or_to_odd_places_are_refused(self):
        for location in ("http://127.0.0.1/", "http://[::ffff:127.0.0.1]/", "http://2130706433/",
                         "http://0x7f.1/", "http://inside.example.com/", "https://www.example.com:8443/",
                         "http://localhost/", "file:///etc/passwd", "http://user:pw@www.example.com/",
                         "http://169.254.169.254/latest/meta-data/"):
            net = Net(names={"www.example.com": [PUBLIC], "inside.example.com": ["10.0.0.9"]},
                      pages={"https://www.example.com/": (301, {"Location": location}, b"")})
            with self.subTest(location):
                with self.assertRaises(sp.Refused):
                    run("www.example.com", net)
                self.assertEqual([o["address"] for o in net.opened], [PUBLIC])

    def test_at_most_three_redirects(self):
        pages = {f"https://www.example.com/{i}": (302, {"Location": f"/{i + 1}"}, b"") for i in range(9)}
        pages["https://www.example.com/"] = (302, {"Location": "/0"}, b"")
        net = Net(names={"www.example.com": [PUBLIC]}, pages=pages)
        with self.assertRaises(sp.Refused) as got:
            run("www.example.com", net)
        self.assertIn("more than 3", str(got.exception))
        self.assertEqual(len(net.opened), 4)


class Limits(unittest.TestCase):
    def test_at_most_max_fetches_requests_get_and_head_only_with_the_agent(self):
        hops = {f"https://www.example.com/h{i}": (302, {"Location": f"/h{i + 1}"}, b"") for i in range(9)}
        net = Net(names={"www.example.com": [PUBLIC], "example.com": [PUBLIC],
                         "wp.example.com": [PUBLIC2], "cdn.example.net": [PUBLIC2]},
                  pages={"https://example.com/": (301, {"Location": "https://www.example.com/"}, b""),
                         "https://www.example.com/": (200, {"X-Powered-By": "PHP/8.3.10"}, WP_HOME),
                         "https://www.example.com/wp-login.php": (302, {"Location": "/h0"}, b""),
                         **hops})
        got = run("example.com", net)
        self.assertEqual(len(net.opened), sp.MAX_FETCHES)
        self.assertEqual(got["fetches"], sp.MAX_FETCHES)
        self.assertEqual({o["method"] for o in net.opened}, {"GET"})
        self.assertEqual({o["agent"] for o in net.opened}, {sp.agent(CONFIG)})
        self.assertTrue(sp.agent(CONFIG).endswith("StackCheck/1.0 (+https://www.example.com/check/)"))
        self.assertTrue(all(o["max_bytes"] == sp.MAX_BYTES and o["timeout"] <= sp.TIMEOUT
                            for o in net.opened))
        self.assertNotIn("cdn.example.net", net.looked, "another domain's server is never asked")
        origin = [h for h in got["hosts"] if h["role"] == "content origin"]
        self.assertEqual(origin[0]["host"], "wp.example.com")
        skipped = [f for f in got["fetched"] if (f["error"] or "").startswith("not fetched")]
        self.assertEqual([f["url"] for f in skipped][:2], ["https://www.example.com/xmlrpc.php",
                                                            "https://www.example.com/readme.html"])
        self.assertIn("https://wp.example.com/wp-login.php", [f["url"] for f in skipped])
        login = next(c for c in got["cards"] if "Login page" in c["title"])
        self.assertEqual(login["kind"], "unknown", "a chain past the hop limit is not a finding")
        self.assertEqual([f["status"] for f in got["fetched"][:3]], [301, 200, 302])
        evidenced(self, got)

    def test_the_whole_check_has_a_deadline(self):
        clock = [0.0]
        budget = sp.Budget(clock=lambda: clock[0])
        budget.take()
        clock[0] = sp.DEADLINE
        with self.assertRaises(sp.Unreachable):
            budget.take()


def evidenced(case, got):
    """Every card carries proof: lines of what was seen, each with its URL and a command."""
    for card in got["cards"]:
        case.assertTrue(card["saw"], card["title"])
        for seen in card["saw"]:
            case.assertTrue(seen["text"].startswith(("We saw", "We could not")), seen["text"])
            case.assertTrue(seen["url"] and seen["command"].startswith("curl "), seen)
        case.assertTrue(card["means"].startswith("This means"), card["means"])


LOGIN_FORM = (b'<form name="loginform" id="loginform" action="/wp-login.php" method="post">'
              b'<input name="log"><input name="pwd" type="password"></form>')
HEADLESS = ("<html><head><script src=\"/_next/static/chunks/main.js\"></script></head><body>"
            + "".join(f'<img src="https://wp.example.com/wp-content/uploads/2026/{i % 12 + 1:02d}/p{i}.webp">'
                      for i in range(289))
            + '<script id="__NEXT_DATA__" type="application/json">{}</script></body></html>').encode()
WP_JSON = {"Server": "nginx", "Link": '<https://wp.example.com/wp-json/>; rel="https://api.w.org/"'}


class Answers(unittest.TestCase):
    def headless(self, **pages):
        base = {"https://www.example.com/": (200, {"Server": "nginx/1.18.0 (Ubuntu)",
                                                   "X-Powered-By": "Next.js"}, HEADLESS),
                "https://wp.example.com/wp-login.php": (302, {"Location": "https://wp.example.com/not_found"}, b""),
                "https://wp.example.com/not_found": (404, {}, b"<html>Not found</html>"),
                ("HEAD", "https://wp.example.com/wp-json/"): (200, WP_JSON, b"")}
        names = {"www.example.com": [PUBLIC], "wp.example.com": [PUBLIC2]}
        return run("www.example.com", Net(names=names, pages={**base, **pages}))

    def test_a_headless_wordpress_behind_a_next_site(self):
        """As a real headless site answered on 2026-10-21 (example.com names here)."""
        got = self.headless()
        evidenced(self, got)
        kinds = [c["kind"] for c in got["cards"]]
        self.assertEqual(kinds, ["hidden", "hidden", "tip", "tip", "info", "good"])
        php = next(c for c in got["cards"] if c.get("product") == "php")
        self.assertEqual(php["title"], "PHP on wp.example.com: version not shown by the server")
        self.assertEqual(php["because"], "PHP version not shown on wp.example.com, which runs WordPress")
        self.assertEqual(php["saw"][0]["text"], "We saw wp.example.com runs WordPress (its files), "
                                                "and WordPress runs on PHP")
        self.assertEqual(php["command"], "php -v")
        saw = " | ".join(s["text"] for s in php["saw"])
        self.assertIn("load 289 different files under /wp-content/ or /wp-includes/ from "
                      "wp.example.com", saw)
        self.assertIn("https://wp.example.com/wp-content/uploads/2026/01/p0.webp", saw)
        self.assertIn('Link: <https://wp.example.com/wp-json/>; rel="https://api.w.org/"', saw)
        self.assertTrue(php["sources"][0].startswith("https://www.php.net/"))
        node = next(c for c in got["cards"] if c.get("product") == "nodejs")
        self.assertEqual(node["title"], "Node.js on www.example.com: version not shown by the server")
        self.assertIn("We saw the header X-Powered-By: Next.js", [s["text"] for s in node["saw"]])
        self.assertIn("26.12.1", node["means"])
        tip = next(c for c in got["cards"] if c["kind"] == "tip")
        self.assertEqual(tip["title"], "Your server shows its exact version: nginx 1.18.0")
        self.assertIn("server_tokens off;", tip["advice"])
        self.assertNotIn("advisory", tip)
        login = got["cards"][-1]
        self.assertEqual(login["title"], "Login page on wp.example.com hidden or blocked (good)")
        self.assertIn("https://wp.example.com/wp-login.php answered 302, sending visitors to "
                      "https://wp.example.com/not_found", login["saw"][0]["text"])
        self.assertEqual([(f["method"], f["url"], f["status"]) for f in got["fetched"]],
                         [("GET", "https://www.example.com/", 200),
                          ("GET", "https://wp.example.com/wp-login.php", 302),
                          ("GET", "https://wp.example.com/not_found", 404),
                          ("HEAD", "https://wp.example.com/wp-json/", 200),
                          ("HEAD", "https://wp.example.com/", 404)])
        self.assertEqual(got["fetched"][0]["bytes"], len(HEADLESS))
        self.assertEqual(got["agent"], sp.agent(CONFIG))

    def test_a_plain_wordpress_names_php_not_wordpress_as_hidden(self):
        home = (b'<html><head><meta name="generator" content="WordPress 7.1.3"></head><body>'
                + b"".join(b'<img src="/wp-content/uploads/a%d.png">' % i for i in range(3))
                + b'<img src="/wp-content/uploads/a0.png"><img src="https://www.example.com/wp-content/uploads/a0.png">'
                + b"</body></html>")
        got = run("www.example.com", Net(names={"www.example.com": [PUBLIC]}, pages={
            "https://www.example.com/": (200, {"Server": "Apache"}, home),
            "https://www.example.com/wp-login.php": (200, {}, LOGIN_FORM)}))
        evidenced(self, got)
        php = next(c for c in got["cards"] if c.get("product") == "php")
        self.assertEqual(php["title"], "PHP on www.example.com: version not shown by the server")
        self.assertEqual(php["saw"][0]["text"], "We saw www.example.com runs WordPress 7.1.3 (generator "
                                                "tag), and WordPress runs on PHP")
        self.assertEqual(php["facts"], ["WordPress 7.1.3"])
        files = next(s for s in php["saw"] if "different file" in s["text"])
        self.assertIn("We saw links to 4 different files under /wp-content/ or /wp-includes/ on "
                      "www.example.com", files["text"])
        self.assertIn("| sort -u | wc -l", files["command"], "the command counts what the text says")
        self.assertIn(("WordPress", "7.1.3"), {(p["name"], p["shown"]) for p in got["products"]})
        self.assertIn("login", [c["kind"] for c in got["cards"]])

    def test_a_login_chain_of_three_redirects_ends_hidden(self):
        got = self.headless(**{
            "https://wp.example.com/wp-login.php": (302, {"Location": "https://wp.example.com/not_found"}, b""),
            "https://wp.example.com/not_found": (302, {"Location": "https://www.example.com/not_found"}, b""),
            "https://www.example.com/not_found": (308, {"Location": "/not_found/"}, b""),
            "https://www.example.com/not_found/": (404, {}, b"<html>404</html>")})
        evidenced(self, got)
        login = next(c for c in got["cards"] if c["kind"] == "good")
        self.assertEqual(len(login["saw"]), 4, "the whole chain is the proof")
        self.assertIn("https://www.example.com/not_found/ answered 404", login["saw"][-1]["text"])

    def test_the_login_page_open_only_with_a_form(self):
        got = self.headless(**{"https://wp.example.com/wp-login.php": (200, {}, LOGIN_FORM)})
        evidenced(self, got)
        login = next(c for c in got["cards"] if c["kind"] == "login")
        self.assertEqual(login["title"], "Login page open to the internet")
        self.assertIn("We saw a WordPress login form on https://wp.example.com/wp-login.php",
                      [s["text"] for s in login["saw"]])
        for page, kind in (((200, {}, b"<html><div id='__next'></div></html>"), "good"),  # an SPA shell
                           ((403, {}, b"no"), "good"),
                           ((503, {"cf-mitigated": "challenge"}, b"Just a moment..."), "unknown"),
                           ((500, {}, b"oops"), "unknown")):
            with self.subTest(page[0]):
                got = self.headless(**{"https://wp.example.com/wp-login.php": page})
                evidenced(self, got)
                kinds = [c["kind"] for c in got["cards"]]
                self.assertIn(kind, kinds)
                self.assertNotIn("login", kinds)

    def test_a_challenge_or_a_blocked_home_page_is_could_not_check(self):
        challenge = (b"<html><title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/h/b'>"
                     b"</script></html>")
        for page in ((403, {"Server": "cloudflare", "cf-mitigated": "challenge"}, challenge),
                     (503, {"Server": "cloudflare"}, challenge),
                     (403, {"Server": "nginx/1.18.0", "X-Powered-By": "PHP/7.4.3"}, WP_HOME)):
            with self.subTest(page[0]):
                got = run("www.example.com", Net(names={"www.example.com": [PUBLIC]},
                                                 pages={"https://www.example.com/": page}))
                evidenced(self, got)
                self.assertFalse(got["reached"])
                self.assertEqual(got["reason"], "blocked")
                self.assertEqual([c["kind"] for c in got["cards"]], ["unknown"])
                self.assertEqual(got["cards"][0]["title"], "www.example.com's firewall blocked our check")
                self.assertIn("php -v", got["cards"][0]["commands"])
                self.assertEqual(got["products"], [], "nothing read from a page we could not check")
        got = run("www.example.com", Net(names={"www.example.com": [PUBLIC]},
                                         pages={"https://www.example.com/": (500, {}, b"oops")}))
        self.assertEqual((got["reason"], got["error"]), ("error", "the home page answered 500"))

    def test_an_old_php_shown_and_a_fixed_one(self):
        net = Net(names={"www.example.com": [PUBLIC]},
                  pages={"https://www.example.com/": (200, {"X-Powered-By": "PHP/8.3.10"}, b"<p>hi</p>")})
        got = run("www.example.com", net)
        evidenced(self, got)
        php = got["cards"][0]
        self.assertEqual((php["kind"], php["title"]), ("update", "Update needed: PHP 8.3.10 on www.example.com"))
        self.assertIn("older than 8.3.36", php["means"])
        self.assertEqual(php["fixed"], ["8.5.12", "8.4.27", "8.3.36", "8.2.35"])
        self.assertIn("We saw the header X-Powered-By: PHP/8.3.10", php["saw"][0]["text"])
        old = run("www.example.com", Net(names={"www.example.com": [PUBLIC]}, pages={
            "https://www.example.com/": (200, {"X-Powered-By": "PHP/8.1.2"}, b"<p>hi</p>")}))
        self.assertEqual(old["cards"][0]["title"],
                         "Update needed: PHP 8.1.2 on www.example.com gets no official fix")
        net = Net(names={"www.example.com": [PUBLIC]},
                  pages={"https://www.example.com/": (200, {"X-Powered-By": "PHP/8.4.27"}, b"<p>hi</p>")})
        got = run("www.example.com", net)
        evidenced(self, got)
        self.assertEqual([c["kind"] for c in got["cards"]], ["tip", "fixed", "nothing"])
        self.assertEqual(got["cards"][-1]["title"], "Nothing we know of applies")

    def test_hidden_php_on_a_wordpress_site_and_an_unreachable_one(self):
        net = Net(names={"www.example.com": [PUBLIC]},
                  pages={"https://www.example.com/": (200, {"Server": "Apache"}, WP_HOME.replace(
                      b"https://wp.example.com/wp-content", b"/wp-content"))})
        got = run("www.example.com", net)
        evidenced(self, got)
        self.assertEqual(got["cards"][0]["kind"], "hidden")
        self.assertEqual(got["cards"][0]["command"], "php -v")
        self.assertIn("8.1 and older", got["cards"][0]["means"])
        net = Net(names={})                                       # no such name
        got = run("gone.example.com", net)
        evidenced(self, got)
        self.assertFalse(got["reached"])
        self.assertEqual((got["error"], got["reason"]), ("the name doesn't exist", "unreachable"))
        self.assertEqual([c["kind"] for c in got["cards"]], ["unknown"])

    def test_commands_quote_what_a_server_sent(self):
        odd = "https://www.example.com/a;echo$(id)'x"
        net = Net(names={"www.example.com": [PUBLIC]},
                  pages={"https://www.example.com/": (302, {"Location": "/a;echo$(id)'x"}, b""),
                         odd: (200, {"X-Powered-By": "PHP/8.3.10"}, b"x")})
        got = run("www.example.com", net)
        php = got["cards"][0]
        self.assertEqual(php["saw"][0]["url"], odd)
        self.assertIn(shlex.quote(odd), php["saw"][0]["command"], "the URL is one quoted word")


class FakeSite:
    """A web server on this machine standing for a public site: the stub sends every
    connection to it (the rules themselves see only documentation addresses)."""

    def __init__(self, headers=None, body=b"", sleep=0.0, login=200, login_body=b""):
        seen = self.seen = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def _answer(self, with_body):
                seen.append((self.command, self.path, {k.lower(): v for k, v in self.headers.items()}))
                if sleep:
                    time.sleep(sleep)
                status = login if self.path == "/wp-login.php" else 200
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.send_header("Set-Cookie", "session=abc")
                raw = login_body if self.path == "/wp-login.php" else body
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                if with_body:
                    try:
                        self.wfile.write(raw)
                    except OSError:
                        pass

            def do_GET(self):
                self._answer(True)

            def do_HEAD(self):
                self._answer(False)

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.port = self.server.server_address[1]
        self.real = site_fetch.open_pinned

    def open(self, scheme, host, address, port, method, target, timeout, max_bytes, agent=None):
        assert address in TESTNET, address
        return self.real("http", host, "127.0.0.1", self.port, method, target, timeout, max_bytes,
                         agent=agent)

    def __enter__(self):
        self._p = [mock.patch.object(site_fetch, "lookup", lambda h, p: [PUBLIC]),
                   mock.patch.object(site_fetch, "open_pinned", self.open),
                   mock.patch.object(site_fetch, "address_refused", doc_refused)]
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._p:
            p.stop()
        self.server.shutdown()
        self.server.server_close()


class OverTheWire(unittest.TestCase):
    def test_happy_path_against_a_local_server(self):
        body = WP_HOME.replace(b"wp.example.com", b"www.example.com")
        with FakeSite({"Server": "nginx/1.24.0", "X-Powered-By": "PHP/8.4.10"}, body,
                      login_body=LOGIN_FORM) as site:
            got = sp.check("https://www.example.com/", CONFIG, advisories.load(), NOW)
        self.assertTrue(got["reached"])
        evidenced(self, got)
        self.assertEqual(got["cards"][0]["title"], "Update needed: PHP 8.4.10 on www.example.com")
        self.assertIn("login", [c["kind"] for c in got["cards"]])
        self.assertEqual([(m, p) for m, p, _ in site.seen], [("GET", "/"), ("GET", "/wp-login.php"),
                                                             ("GET", "/xmlrpc.php"), ("GET", "/readme.html")])
        for _m, _p, headers in site.seen:
            self.assertEqual(headers["user-agent"], sp.agent(CONFIG))
            self.assertNotIn("cookie", headers)
            self.assertNotIn("authorization", headers)
            self.assertTrue(headers["host"].startswith("www.example.com"))

    def test_the_size_cap(self):
        big = b"<html>" + b"x" * (2 * sp.MAX_BYTES)
        with FakeSite({}, big):
            got = sp.get("https://www.example.com/", "GET", sp.Budget(), "t")
        self.assertEqual(len(got.body), sp.MAX_BYTES)

    def test_the_time_cap(self):
        with FakeSite({}, b"<html></html>", sleep=2.0), mock.patch.object(sp, "TIMEOUT", 0.4):
            started = time.monotonic()
            got = sp.check("www.example.com", CONFIG, advisories.load(), NOW)
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertFalse(got["reached"])
        self.assertEqual((got["error"], got["reason"]), ("no answer in 5 seconds", "unreachable"))


class Service(unittest.TestCase):
    def setUp(self):
        self.clock = [1000.0]
        self.asked = []

        def checker(raw):
            self.asked.append(raw)
            return {"host": raw, "reached": "down" not in raw, "cards": []}
        self.svc = api.Service(CONFIG, clock=lambda: self.clock[0], checker=checker)

    def test_ten_an_hour_per_sender_then_429(self):
        for i in range(10):
            self.assertEqual(self.svc.run("203.0.113.5", f"s{i}.example.com")[0], 200)
        status, body, extra = self.svc.run("203.0.113.5", "s99.example.com")
        self.assertEqual(status, 429)
        self.assertIn("Retry-After", extra)
        self.assertEqual(self.svc.run("203.0.113.6", "s0.example.com")[0], 200, "another sender")
        self.clock[0] += 3601
        self.assertEqual(self.svc.run("203.0.113.5", "s99.example.com")[0], 200, "the hour slid")

    def test_each_answer_says_its_kind(self):
        self.assertEqual(self.svc.run("203.0.113.5", "not a site")[1]["kind"], "address")
        self.assertEqual(self.svc.run("203.0.113.5", "ftp://example.com/")[1]["kind"], "address")
        status, body, _ = self.svc.run("203.0.113.5", "http://127.0.0.1/")
        self.assertEqual((status, body["kind"]), (400, "refused"))
        self.assertIn("not an IP address", body["error"])
        self.assertEqual(self.svc.run("203.0.113.5", "https://example.com:8443/")[1]["kind"], "refused")

    def test_the_rate_limit_says_when(self):
        svc = api.Service(CONFIG, clock=lambda: self.clock[0], checker=lambda raw: {"reached": True},
                          now=lambda: NOW)
        for i in range(10):
            svc.run("203.0.113.5", f"s{i}.example.com")
        self.clock[0] += 600                         # ten minutes after the first
        status, body, extra = svc.run("203.0.113.5", "s10.example.com")
        self.assertEqual((status, body["kind"], body["limit"]), (429, "rate", 10))
        self.assertEqual(body["retry_in"], 3001)
        self.assertEqual(body["retry_at"], "2026-10-21T18:50:01+00:00")
        self.assertEqual(extra["Retry-After"], "3000")

    def test_refusals_count_against_the_sender_too(self):
        for _ in range(10):
            self.assertEqual(self.svc.run("203.0.113.5", "http://127.0.0.1/")[0], 400)
        self.assertEqual(self.svc.run("203.0.113.5", "example.com")[0], 429)
        self.assertEqual(self.asked, [])

    def test_the_cache_an_hour_and_five_minutes_for_a_site_down(self):
        self.assertFalse(self.svc.run("203.0.113.5", "www.example.com")[1]["cached"])
        self.assertTrue(self.svc.run("203.0.113.6", "https://www.example.com/x")[1]["cached"])
        self.assertEqual(len(self.asked), 1)
        self.clock[0] += 3599
        self.assertTrue(self.svc.run("203.0.113.7", "www.example.com")[1]["cached"])
        self.clock[0] += 2
        self.assertFalse(self.svc.run("203.0.113.8", "www.example.com")[1]["cached"])
        self.svc.run("203.0.113.9", "down.example.com")
        self.clock[0] += 301
        self.assertFalse(self.svc.run("203.0.113.10", "down.example.com")[1]["cached"])
        self.assertEqual(len(self.asked), 4)

    def test_cached_only_never_fetches(self):
        status, body, _ = self.svc.run("203.0.113.5", "www.example.com", cached_only=True)
        self.assertEqual((status, self.asked), (404, []))
        self.svc.run("203.0.113.5", "www.example.com")
        status, body, _ = self.svc.run("203.0.113.5", "https://www.example.com/", cached_only=True)
        self.assertEqual((status, body["cached"], len(self.asked)), (200, True, 1))

    def test_the_global_cap_counts_checks_not_cache_hits(self):
        svc = api.Service({"security": {"public_check": True, "public_check_global_per_hour": 3}},
                          clock=lambda: self.clock[0], checker=lambda raw: {"reached": True})
        for i in range(3):
            self.assertEqual(svc.run(f"203.0.113.{i}", f"s{i}.example.com")[0], 200)
        self.assertEqual(svc.run("203.0.113.50", "s0.example.com")[0], 200, "from the cache")
        self.assertEqual(svc.run("203.0.113.51", "s9.example.com")[0], 429)

    def test_a_failure_is_plain_words(self):
        svc = api.Service(CONFIG, checker=lambda raw: 1 / 0)
        status, body, _ = svc.run("203.0.113.5", "www.example.com")
        self.assertEqual((status, body["kind"]), (500, "failed"))
        self.assertIn("on our side, not your site", body["error"])

    def test_too_many_at_once(self):
        gate = threading.Event()
        svc = api.Service(CONFIG, checker=lambda raw: gate.wait(5) and {"reached": True})
        threads = [threading.Thread(target=svc.run, args=(f"203.0.113.{i}", f"p{i}.example.com"))
                   for i in range(api.PARALLEL)]
        for t in threads:
            t.start()
        time.sleep(0.2)
        self.assertEqual(svc.run("203.0.113.99", "q.example.com")[0], 503)
        gate.set()
        for t in threads:
            t.join()


class Http(unittest.TestCase):
    """On the beacon helper, as nginx reaches it."""

    def start(self, config):
        self.tmp = tempfile.TemporaryDirectory()
        config = {"site": {"name": "example.com", "hosts": ["www.example.com"]},
                  "report": {"timezone": "UTC"}, **config}
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            Sink(config, Path(self.tmp.name) / "beacon"), Limiter(), set()))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def ask(self, method="POST", body=None, origin=ORIGIN, ip="203.0.113.7", path=api.PATH):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        headers = {"Content-Type": "application/json", "X-Real-IP": ip}
        if origin:
            headers["Origin"] = origin
        raw = body if isinstance(body, bytes) else json.dumps(body or {"url": "http://127.0.0.1/"}).encode()
        conn.request(method, path, body=raw if method == "POST" else None, headers=headers)
        res = conn.getresponse()
        got = (res.status, dict(res.getheaders()), res.read())
        conn.close()
        return got

    def test_off_by_default(self):
        self.start({})
        status, headers, _ = self.ask()
        self.assertNotEqual(status, 400)
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_origin_cors_preflight_body_and_senders(self):
        self.start(CONFIG)
        status, headers, raw = self.ask()
        self.assertEqual(status, 400)
        self.assertEqual(headers["Access-Control-Allow-Origin"], ORIGIN)
        self.assertNotIn("Set-Cookie", headers)
        self.assertIn("IP address", json.loads(raw)["error"])
        self.assertEqual(self.ask(origin="https://evil.example.net")[0], 403)
        self.assertEqual(self.ask(origin=None)[0], 400, "no Origin: not a browser on another page")
        status, headers, _ = self.ask("OPTIONS")
        self.assertEqual((status, headers["Access-Control-Allow-Origin"]), (204, ORIGIN))
        self.assertEqual(self.ask("OPTIONS", origin="https://evil.example.net")[0], 403)
        self.assertEqual(self.ask(body=b"x" * (api.MAX_BODY + 1))[0], 413)
        self.assertEqual(self.ask(body=b"not json")[0], 400)
        for _ in range(8):                      # 10 checks in all from this sender, with the two above
            self.ask()
        self.assertEqual(self.ask()[0], 429)
        self.assertEqual(self.ask(ip="203.0.113.8")[0], 400, "X-Real-IP from the proxy is the sender")


class Docker(unittest.TestCase):
    def test_the_environment_switches_it_on(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "docker"))
        import entrypoint
        env = {"SKALD_SITE": "example.com"}
        self.assertNotIn("security", entrypoint.render_config(env))
        cfg = entrypoint.render_config({**env, "SKALD_PUBLIC_CHECK": "true",
                                        "SKALD_PUBLIC_CHECK_ORIGINS": ORIGIN,
                                        "SKALD_PUBLIC_CHECK_INFO_URL": "https://www.example.com/check/"})
        self.assertTrue(api.on(cfg))
        self.assertEqual(cfg["security"]["public_check_origins"], [ORIGIN])
        self.assertIn("(+https://www.example.com/check/)", sp.agent(cfg))


if __name__ == "__main__":
    unittest.main()
