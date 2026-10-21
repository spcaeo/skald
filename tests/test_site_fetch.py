"""The site check's fetching (skald/site_fetch.py): each refusal that
keeps it from reaching what sits behind Skald's server (SSRF), the pinned
connection, and what it sends. No request leaves this machine: name lookup
and the network are stubbed, and the one real connection is to a server on
this machine, called below the checks."""
from __future__ import annotations

import http.server
import socket
import ssl
import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skald import site_fetch as f  # noqa: E402

PUBLIC = "8.8.8.8"                      # a public address; nothing is sent to it here
PUBLIC6 = "2001:4860:4860::8888"


class Stub:
    """lookup and open_pinned stand-ins: names -> addresses, URLs -> answers."""

    def __init__(self, names=None, answers=None):
        self.names = names or {}
        self.answers = answers or {}
        self.opened: list[tuple] = []
        self.looked: list[str] = []

    def lookup(self, host, port):
        self.looked.append(host)
        if host not in self.names:
            raise socket.gaierror("no such name")
        return list(self.names[host])

    def open(self, scheme, host, address, port, method, target, timeout, max_bytes):
        self.opened.append((scheme, host, address, port, method, target))
        status, headers = self.answers.get(f"{scheme}://{host}{target}", (200, {}))
        return f.Answer(status, {k.lower(): [v] for k, v in headers.items()}, b"",
                        f"{scheme}://{host}{target}", address)

    def __enter__(self):
        self._p = [mock.patch.object(f, "lookup", self.lookup),
                   mock.patch.object(f, "open_pinned", self.open)]
        for p in self._p:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._p:
            p.stop()


class Addresses(unittest.TestCase):
    def test_every_kind_of_inside_address_is_refused(self):
        cases = {
            "127.0.0.1": "loopback", "127.8.9.10": "loopback", "::1": "loopback",
            "10.1.2.3": "private", "172.16.5.4": "private", "192.168.1.1": "private",
            "fc00::1": "private", "fd12:3456::1": "private",
            "169.254.10.20": "link-local", "fe80::1": "link-local",
            "100.64.0.1": "CGNAT", "100.127.255.254": "CGNAT",
            "224.0.0.1": "multicast", "ff02::1": "multicast",
            "0.0.0.0": "unspecified", "::": "unspecified",
            "240.0.0.1": "address", "255.255.255.255": "address",
            "169.254.169.254": "metadata", "169.254.170.2": "metadata",
            "100.100.100.200": "metadata", "fd00:ec2::254": "metadata",
            "::ffff:127.0.0.1": "loopback", "::ffff:10.0.0.1": "private",
            "::ffff:169.254.169.254": "metadata",
            "2002:7f00:1::": "loopback", "2002:a00:1::": "private",     # 6to4
            "64:ff9b::a00:1": "private", "64:ff9b::7f00:1": "loopback",  # NAT64
            "2001:db8::1": "address", "192.0.2.10": "address",          # documentation
            "198.51.100.7": "address", "203.0.113.9": "address",
            "not an address": "cannot be read",
        }
        for address, words in cases.items():
            with self.subTest(address):
                why = f.address_refused(address)
                self.assertIsNotNone(why, address)
                self.assertIn(words, why)
                self.assertNotIn(address, why)          # the words never carry the address

    def test_public_addresses_pass(self):
        for address in (PUBLIC, PUBLIC6, "64:ff9b::808:808", f"{PUBLIC6}%eth0"):
            with self.subTest(address):
                self.assertIsNone(f.address_refused(address))

    def test_a_name_with_one_inside_address_is_refused_whole(self):
        with Stub({"mixed.example.com": [PUBLIC, "10.0.0.5"],
                   "meta.example.com": ["169.254.169.254"],
                   "six.example.com": ["::1"], "ok.example.com": [PUBLIC, PUBLIC6]}):
            for host in ("mixed.example.com", "meta.example.com", "six.example.com"):
                with self.subTest(host), self.assertRaises(f.Refused) as got:
                    f.resolve(host, 443)
                self.assertIn(host, str(got.exception))
                self.assertNotIn("10.0.0.5", str(got.exception))
            self.assertEqual(f.resolve("ok.example.com", 443), [PUBLIC, PUBLIC6])
            with self.assertRaises(f.Unreachable):
                f.resolve("nothing.example.com", 443)

    def test_an_address_typed_as_the_host_is_checked_too(self):
        for literal in ("127.0.0.1", "[::1]", "169.254.169.254", "10.0.0.1"):
            with self.subTest(literal), self.assertRaises(f.Refused):
                f.resolve(literal, 80)


class Urls(unittest.TestCase):
    def test_only_http_and_https_on_80_and_443(self):
        for url, words in (("ftp://www.example.com/", "http and https"),
                           ("file:///etc/passwd", "http and https"),
                           ("gopher://www.example.com/", "http and https"),
                           ("https://www.example.com:8443/", "ports 80 and 443"),
                           ("http://www.example.com:22/", "ports 80 and 443"),
                           ("https://www.example.com:99999/", "not an address"),
                           ("https://user:secret@www.example.com/", "user name or password"),
                           ("https://user@www.example.com/", "user name or password"),
                           ("https://localhost/", "host name"),
                           ("https://app.localhost/", "host name"),
                           ("https://intranet/", "host name"),
                           ("https:///nothing", "host name")):
            with self.subTest(url), self.assertRaises(f.Refused) as got:
                f.check_url(url)
            self.assertIn(words, str(got.exception))

    def test_a_good_url(self):
        self.assertEqual(f.check_url("https://WWW.Example.com/a?b=1#c"),
                         ("https", "www.example.com", 443, "/a?b=1"))
        self.assertEqual(f.check_url("http://www.example.com:80"),
                         ("http", "www.example.com", 80, "/"))


class Redirects(unittest.TestCase):
    def test_each_redirect_is_checked_again(self):
        start = "https://www.example.com/"
        for target, refused in (("http://127.0.0.1/", "loopback"),
                                ("http://169.254.169.254/latest/meta-data/", "metadata"),
                                ("https://inside.example.com/", "private"),
                                ("https://[::1]/", "loopback"),
                                ("ftp://www.example.com/", "http and https"),
                                ("https://www.example.com:8080/", "ports 80 and 443"),
                                ("https://u:p@www.example.com/", "user name")):
            with self.subTest(target), Stub({"www.example.com": [PUBLIC],
                                             "inside.example.com": ["10.9.8.7"]},
                                            {start: (302, {"Location": target})}) as net:
                with self.assertRaises(f.Refused) as got:
                    f.follow(start, "HEAD")
                self.assertIn(refused, str(got.exception))
                self.assertEqual(len(net.opened), 1)        # nothing was asked of the target

    def test_at_most_three_redirects(self):
        answers = {f"https://www.example.com/{i}": (301, {"Location": f"/{i + 1}"})
                   for i in range(5)}
        with Stub({"www.example.com": [PUBLIC]}, answers) as net:
            with self.assertRaises(f.Refused) as got:
                f.follow("https://www.example.com/0", "HEAD")
            self.assertIn("More than 3 redirects", str(got.exception))
            self.assertEqual(len(net.opened), 4)
        answers["https://www.example.com/3"] = (200, {})
        with Stub({"www.example.com": [PUBLIC]}, answers):
            got, chain = f.follow("https://www.example.com/0", "HEAD")
        self.assertEqual((got.status, len(chain)), (200, 4))

    def test_the_connection_goes_to_the_checked_address(self):
        """No second lookup between the check and the connection: the
        address the check passed is the one connected to, by name."""
        answers = {"https://example.com/": (301, {"Location": "https://www.example.com/"})}
        with Stub({"example.com": [PUBLIC], "www.example.com": [PUBLIC6]}, answers) as net:
            got, _ = f.follow("https://example.com/", "HEAD")
        self.assertEqual(got.status, 200)
        self.assertEqual([(o[1], o[2]) for o in net.opened],
                         [("example.com", PUBLIC), ("www.example.com", PUBLIC6)])
        self.assertEqual(net.looked, ["example.com", "www.example.com"])


class Pinned(unittest.TestCase):
    def test_tls_names_the_site_while_connecting_to_the_address(self):
        seen = {}

        def connect(addr, timeout):
            seen["addr"] = addr
            return mock.Mock()

        conn = f._PinnedHTTPS("www.example.com", PUBLIC, 443, 5)
        with mock.patch.object(socket, "create_connection", connect), \
                mock.patch.object(conn._ctx, "wrap_socket",
                                  lambda raw, server_hostname: seen.update(sni=server_hostname)):
            conn.connect()
        self.assertEqual(seen, {"addr": (PUBLIC, 443), "sni": "www.example.com"})
        self.assertEqual(conn._ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(conn._ctx.check_hostname)

    def test_errors_are_words_without_addresses(self):
        def refuse(*a, **k):
            raise ConnectionRefusedError("[Errno 61] refused by 10.0.0.1")
        with mock.patch.object(f, "lookup", lambda h, p: [PUBLIC]), \
                mock.patch.object(f, "open_pinned", refuse):
            with self.assertRaises(f.Unreachable) as got:
                f.fetch("https://www.example.com/", "HEAD")
        self.assertEqual(str(got.exception), "it refused the connection")

    def test_what_is_sent_and_the_size_cap(self):
        """Called below the checks, against a server on this machine: the
        Host is the site's name, no cookie or authorization goes, and no more
        than MAX_BYTES of the body is read."""
        got = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                got.update({k.lower(): v for k, v in self.headers.items()})
                body = b"x" * (f.MAX_BYTES * 2)
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Set-Cookie", "a=b")
                self.end_headers()
                try:
                    self.wfile.write(body)
                except OSError:
                    pass

            def log_message(self, *a):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            port = server.server_address[1]
            answer = f.open_pinned("http", "www.example.com", "127.0.0.1", port, "GET", "/",
                                   5, f.MAX_BYTES)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(answer.status, 200)
        self.assertEqual(len(answer.body), f.MAX_BYTES)
        self.assertEqual(got["host"], f"www.example.com:{port}")
        self.assertNotIn("cookie", got)
        self.assertNotIn("authorization", got)
        self.assertEqual(got["accept-encoding"], "identity")
        from skald.brand import load
        self.assertIn(f"{load()['name']}-site-check", got["user-agent"])
        self.assertNotIn("example", got["user-agent"])         # no host in the agent


if __name__ == "__main__":
    unittest.main()
