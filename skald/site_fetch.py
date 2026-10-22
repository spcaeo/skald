"""Fetching a site's home page for the site check (site_detect.py), safely.

The site check is asked for by an admin with an address they typed, so this
client must never become a way to reach what sits behind Skald's server
(server-side request forgery). Every request, and every redirect it gets:

  * is http or https only, on port 80 or 443, with no user:password@ part,
    and never a host that ends in numbers (127.1, 0x7f.1: an address in disguise);
  * has its name resolved here (`resolve`), and is refused when ANY address
    the name gives is loopback, private, link-local, shared (CGNAT, 100.64/10),
    multicast, reserved, unspecified, a cloud metadata address, or anything
    else that is not a public address, for IPv4 and IPv6 (IPv4 inside IPv6
    too: ::ffff:, 6to4, Teredo, NAT64);
  * connects to the address it checked, with the site's name as Host and as
    the TLS name (SNI and the certificate check), so the name cannot be
    pointed elsewhere between the check and the connection;
  * sends no cookie and no Authorization header, only an honest User-Agent
    that names the site check (from brand.py), Accept and
    Accept-Encoding: identity;
  * reads at most MAX_BYTES of the body, waits at most TIMEOUT seconds;
  * follows at most MAX_REDIRECTS redirects, each checked again as above.

Errors come back as `Refused` (a rule said no) or `Unreachable` (the network
said no), each with plain words made here: never an exception's own text, and
never an address. Nothing is logged here; the caller logs the host and the
outcome only.

The network itself is `open_pinned`, and name lookup `lookup`: tests replace
them (no network in tests).
"""
from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

TIMEOUT = 6.0
MAX_BYTES = 262144
MAX_REDIRECTS = 3
PORTS = {"http": 80, "https": 443}
REDIRECTS = (301, 302, 303, 307, 308)
MAX_ADDRESSES = 2                  # addresses tried per name, in the resolver's order
NAME = re.compile(r"^(?=.{3,253}$)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
                  r"(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$")
# Cloud metadata services (AWS, GCP, Azure, ECS, Alibaba, Oracle, AWS IPv6).
# Each is also caught by the general rules; named so the refusal says so.
METADATA = {ipaddress.ip_address(a) for a in (
    "169.254.169.254", "169.254.170.2", "169.254.169.253", "100.100.100.200",
    "fd00:ec2::254")}
# A last label of digits or hex (0x7f) is an address in an odd form that a resolver may
# read as one (127.1, 2130706433.0); no real name ends in one.
NUMERIC_LABEL = re.compile(r"^(?:\d+|0x[0-9a-f]*)$", re.I)
CGNAT = ipaddress.ip_network("100.64.0.0/10")
NAT64 = ipaddress.ip_network("64:ff9b::/96")
NAT64_LOCAL = ipaddress.ip_network("64:ff9b:1::/48")


class Refused(ValueError):
    """A request a rule refuses, in plain words."""


class Unreachable(OSError):
    """No answer: the words say why (timed out, refused, the certificate)."""


@dataclass
class Answer:
    status: int
    headers: dict = field(default_factory=dict)       # lower-case name -> [values]
    body: bytes = b""
    url: str = ""
    peer: str = ""                                    # the address used; never shown
    not_after: str | None = None                      # the TLS certificate's end (https)

    def header(self, name: str) -> str:
        return ", ".join(self.headers.get(name.lower(), []))


def user_agent() -> str:
    from .brand import load
    b = load()
    version = f"/{b['version']}" if b.get("version") else ""
    return (f"Mozilla/5.0 (compatible; {b['name']}-site-check{version}; a one-time look at "
            f"the home page, asked for by the site's admin)")


# ------------------------------------------------------------ addresses

def _embedded(ip: ipaddress.IPv6Address) -> list:
    """The IPv4 addresses an IPv6 address carries (mapped, 6to4, Teredo, NAT64)."""
    out = []
    if ip.ipv4_mapped:
        out.append(ip.ipv4_mapped)
    if ip.sixtofour:
        out.append(ip.sixtofour)
    if ip.teredo:
        out.extend(ip.teredo)
    if ip in NAT64 or ip in NAT64_LOCAL:
        out.append(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return out


def address_refused(text: str) -> str | None:
    """Why Skald does not fetch from this address (plain words, without the
    address), or None for a public one."""
    try:
        ip = ipaddress.ip_address(str(text).split("%", 1)[0])
    except ValueError:
        return "an address that cannot be read"
    if ip in METADATA:
        return "a cloud metadata address"
    if ip.version == 6:
        for inner in _embedded(ip):
            why = address_refused(str(inner))
            if why:
                return why
        if ip in NAT64 or ip in NAT64_LOCAL:
            return None if ip in NAT64 else "a private address"
    if ip.is_loopback:
        return "a loopback address (this server itself)"
    if ip.is_unspecified:
        return "an unspecified address"
    if ip.is_link_local:
        return "a link-local address"
    if ip.version == 4 and ip in CGNAT:
        return "a shared (CGNAT) address"
    if ip.is_multicast:
        return "a multicast address"
    if ip.is_private:
        return "a private address"
    if ip.is_reserved:
        return "a reserved address"
    if not ip.is_global:
        return "an address that is not public"
    return None


def lookup(host: str, port: int) -> list[str]:
    """The addresses of `host` (the system resolver), in its order."""
    got = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    out = []
    for *_, sockaddr in got:
        if sockaddr[0] not in out:
            out.append(sockaddr[0])
    return out


def resolve(host: str, port: int) -> list[str]:
    """The addresses to connect to; Refused when any address of the name is
    not public (a name that gives one private address is refused whole)."""
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        why = address_refused(str(literal))
        if why:
            raise Refused(f"The address is {why}, which Skald does not fetch.")
        return [str(literal)]
    try:
        found = lookup(host, port)
    except (OSError, UnicodeError):
        raise Unreachable(f"{host} has no address in DNS.") from None
    if not found:
        raise Unreachable(f"{host} has no address in DNS.")
    for address in found:
        why = address_refused(address)
        if why:
            raise Refused(f"{host} points to {why}, which Skald does not fetch.")
    return found


# ----------------------------------------------------------------- URLs

def check_url(url: str) -> tuple[str, str, int, str]:
    """(scheme, host, port, path and query) of a URL Skald may fetch, or Refused."""
    try:
        parts = urlsplit(str(url).strip())
        port = parts.port
    except ValueError:
        raise Refused("That is not an address Skald can fetch.") from None
    scheme = (parts.scheme or "").lower()
    if scheme not in PORTS:
        raise Refused("Only http and https addresses are fetched.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise Refused("An address with a user name or password is not fetched.")
    if port is not None and port not in PORTS.values():
        raise Refused("Only ports 80 and 443 are fetched.")
    host = (parts.hostname or "").rstrip(".")
    is_ip = True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        is_ip = False
    if not is_ip:
        try:
            host = host.encode("idna").decode("ascii").lower() if host else ""
        except UnicodeError:
            raise Refused("That is not a host name Skald can fetch.") from None
    if not host or (not is_ip and (not NAME.match(host) or host.endswith(".localhost"))):
        raise Refused("That is not a host name Skald can fetch.")
    if not is_ip and NUMERIC_LABEL.match(host.rsplit(".", 1)[-1]):
        # 127.1, 0x7f.1, 017700000001.0: an address in an odd form, never a name.
        raise Refused("An address written as numbers is not fetched.")
    target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    return scheme, host, port or PORTS[scheme], target


# -------------------------------------------------------------- network

class _PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, address, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._address = address

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, port, timeout):
        self._ctx = ssl.create_default_context()
        super().__init__(host, port, timeout=timeout, context=self._ctx)
        self._address = address

    def connect(self):
        raw = socket.create_connection((self._address, self.port), self.timeout)
        try:
            self.sock = self._ctx.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def open_pinned(scheme: str, host: str, address: str, port: int, method: str, target: str,
                timeout: float, max_bytes: int, agent: str | None = None,
                headers: dict | None = None) -> Answer:
    """One request to `address`, named `host` (Host header and TLS name). `agent` is the
    User-Agent (default: the site check's own, user_agent()); `headers`, a few more
    (tag_check.py's X-Skald-Probe), never a cookie or Authorization. A POST has no body."""
    cls = _PinnedHTTPS if scheme == "https" else _PinnedHTTP
    conn = cls(host, address, port, timeout)
    shown = host if port == PORTS[scheme] else f"{host}:{port}"
    extra = {k: v for k, v in (headers or {}).items()
             if k.lower() not in ("cookie", "authorization", "host")}
    try:
        conn.request(method, target, headers={
            "Host": shown, "User-Agent": agent or user_agent(), "Accept-Encoding": "identity",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5", "Connection": "close",
            **extra})
        res = conn.getresponse()
        headers: dict[str, list[str]] = {}
        for name, value in res.getheaders():
            headers.setdefault(name.lower(), []).append(value)
        body = res.read(max_bytes) if method == "GET" else b""
        not_after = None
        if scheme == "https":
            try:
                not_after = (conn.sock.getpeercert() or {}).get("notAfter")
            except (AttributeError, ValueError, OSError):
                pass
        return Answer(res.status, headers, body, f"{scheme}://{shown}{target}", address, not_after)
    finally:
        conn.close()


def _words(why: BaseException) -> str:
    if isinstance(why, (socket.timeout, TimeoutError)):
        return "it did not answer in time"
    if isinstance(why, ssl.SSLCertVerificationError):
        return "its HTTPS certificate is not valid for this name"
    if isinstance(why, ssl.SSLError):
        return "its HTTPS connection failed"
    if isinstance(why, ConnectionRefusedError):
        return "it refused the connection"
    if isinstance(why, http.client.HTTPException):
        return "its answer could not be read"
    return "the connection failed"


def fetch(url: str, method: str = "GET", deadline: float | None = None,
          max_bytes: int = MAX_BYTES, headers: dict | None = None) -> Answer:
    """One request, checked as the module says; no redirect is followed."""
    more = {"headers": headers} if headers else {}
    scheme, host, port, target = check_url(url)
    addresses = resolve(host, port)
    last = None
    for address in addresses[:MAX_ADDRESSES]:
        left = TIMEOUT if deadline is None else min(TIMEOUT, deadline - time.monotonic())
        if left <= 0.2:
            raise Unreachable("it did not answer in time")
        try:
            return open_pinned(scheme, host, address, port, method, target, left, max_bytes,
                               **more)
        except ssl.SSLCertVerificationError as why:
            raise Unreachable(_words(why)) from None        # another address won't fix it
        except (OSError, http.client.HTTPException) as why:
            last = why
    raise Unreachable(_words(last) if last else "the connection failed")


def follow(url: str, method: str = "GET", deadline: float | None = None,
           max_redirects: int = MAX_REDIRECTS) -> tuple[Answer, list[str]]:
    """The answer at the end of at most `max_redirects` redirects, and the
    addresses passed through (the first included). Each hop is checked."""
    chain = [url]
    for hop in range(max_redirects + 1):
        got = fetch(url, method, deadline)
        location = (got.headers.get("location") or [""])[0].strip() \
            if got.status in REDIRECTS else ""
        if not location:
            return got, chain
        if hop == max_redirects:
            raise Refused(f"More than {max_redirects} redirects.")
        url = urljoin(got.url or url, location)
        check_url(url)
        chain.append(url)
    raise Refused(f"More than {max_redirects} redirects.")       # not reached
