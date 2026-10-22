"""The public "Is my site exposed?" check: what anyone can see of a site from outside, set
against the shipped advisories (security.public_check, off by default; 2.22).

Someone types an address; this reads the site's home page (after its redirects) the way
stack.py's daily check does (the Server, X-Powered-By and Link headers, the generator tag,
WordPress and Next.js paths), then one content origin the page loads WordPress files from
(a headless WordPress) and /wp-login.php on each WordPress host. stack_public_cards.py turns
what was read into cards, each with its evidence; stack_public_api.py serves it over HTTP
with its limits and its cache.

Everything said must be true and shown (owner, 2026-10-21): every finding carries the exact
lines it was read from and the URL, and what could not be read is "could not check", never
a guess. So:

  * a home page that is not a 2xx after its redirects, or a bot challenge (Cloudflare's
    "Just a moment..."), is "could not check": nothing is read from it. When a firewall
    stopped us (a challenge, 401, 403, 429, or a firewall's own 503 denial page),
    stack_public_blocked.py says what proves it and how to see the site from a network the
    firewall lets through; the check never changes who it says it is to get past one;
  * /wp-login.php is followed to its final page (redirects within the site's own domain) and
    its body read: "open" only for a page with WordPress's login form (`id="loginform"`, or
    `name="log"` and `name="pwd"`); a redirect elsewhere, a page without the form, 401, 403,
    404 or 410 is "hidden"; anything else (an error, a challenge, the request limit) is
    "could not check";
  * a WordPress origin is proven by the site's own page loading its /wp-content/ files; its
    /wp-json/ (HEAD) adds its headers (the `api.w.org` Link), and its home page (no redirect
    followed) shows a headless set-up that sends visitors to the site.

Every request is logged in the answer ("What we fetched": method, URL, status, size,
redirect, error), with the User-Agent used.

The address comes from a stranger, so every request and every redirect is held to
site_fetch.py's rules (http and https only, ports 80 and 443, no user:password@, the name
resolved here and refused whole when any of its addresses is not public, cloud metadata
addresses included, the connection made to the very address checked, with the name as the
Host and the TLS name), and to stricter ones of its own:

  * a name, never an IP address in any form (a literal, [::ffff:127.0.0.1], 2130706433,
    0x7f.1, 127.1);
  * never a name that only works inside a network (localhost, *.local, *.internal, *.lan,
    *.home.arpa ...) or one reserved for tests (*.test, *.invalid, *.example);
  * TIMEOUT seconds and MAX_BYTES for each request, MAX_FETCHES requests and DEADLINE
    seconds for a whole check, MAX_REDIRECTS redirects (LOGIN_HOPS from the login page),
    each hop checked again;
  * GET and HEAD only, no cookie, no credentials, the User-Agent `agent(config)`;
  * a content origin, and every login redirect followed, only within the site's own domain
    (wp.<site> for <site>), so a page cannot send the check to someone else.

The requests go, in this order, while the limit allows: the home page and its redirects;
the site's own login page when the site is WordPress; the content origin's login page and
its redirects; its /wp-json/; its home page. What the limit leaves out is listed as not
fetched. Nothing is logged or kept here.
"""
from __future__ import annotations

import http.client
import ipaddress
import re
import ssl
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from . import advisories, site_detect, site_fetch
from .stack_public_blocked import CHALLENGE, blocker, challenged  # noqa: F401 (CHALLENGE: tests)
from .stack_public_detect import PATH_CHARS, WP_ANY, Page, detect, files

TIMEOUT = 5.0              # seconds for one request
DEADLINE = 9.0             # seconds for a whole check (the proxy in front waits 10)
MAX_BYTES = 512 * 1024     # of one body
MAX_FETCHES = 8            # requests in one check, redirects included
LOGIN_HOPS = 5             # redirects followed from /wp-login.php to its final page
MAX_REDIRECTS = 3
MAX_URL = 500
# Last labels that only work inside a network, or are reserved (RFC 2606, 6761, 6762, 8375).
INSIDE = {"localhost", "local", "internal", "intranet", "lan", "home", "corp", "private",
          "localdomain", "test", "invalid", "example", "arpa", "onion", "alt"}
LOGIN_FORM = re.compile(r"id\s*=\s*[\"']loginform[\"']", re.I)
LOG, PWD = (re.compile(rf"name\s*=\s*[\"']{n}[\"']", re.I) for n in ("log", "pwd"))
HIDDEN = (401, 403, 404, 410)
Refused = site_fetch.Refused
Unreachable = site_fetch.Unreachable


class Spent(Exception):
    """The check's requests are used up: what is left is not read."""


class BadAddress(Refused):
    """What was typed is not a website address at all (the page says how to type one)."""


NOT_AN_ADDRESS = "That doesn't look like a website address."
# Why a site could not be read, in words for the person who typed it (site_fetch's own
# words on the left).
PLAIN = (("did not answer in time", "no answer in 5 seconds"),
         ("no address in dns", "the name doesn't exist"),
         ("certificate is not valid", "its certificate is invalid"),
         ("https connection failed", "its secure connection failed"),
         ("refused the connection", "it refused the connection"),
         ("could not be read", "its answer could not be read"))


def plain(words: str) -> str:
    low = (words or "").lower()
    return next((said for seen, said in PLAIN if seen in low), words or "it did not answer")


def agent(config: dict | None) -> str:
    """The User-Agent: the product's name (brand.py) and the page that explains the check
    (security.public_check_info_url), never the person's address."""
    from .brand import load
    name = re.sub(r"[^A-Za-z0-9]", "", str(load().get("name") or "")) or "Site"
    info = str(((config or {}).get("security") or {}).get("public_check_info_url") or "").strip()
    ok = info.startswith("https://") and len(info) < 200 and not re.search(r"[\s()]", info)
    return f"{name}StackCheck/1.0" + (f" (+{info})" if ok else "")


def host_refused(host: str) -> str | None:
    """Why this name is not checked (plain words), or None."""
    host = host.lower().strip("[]").rstrip(".")
    try:
        ipaddress.ip_address(host)
        return "Type your site's name, not an IP address."
    except ValueError:
        pass
    labels = host.split(".")
    if site_fetch.NUMERIC_LABEL.match(labels[-1]):
        return "Type your site's name, not an IP address."
    if labels[-1] in INSIDE:
        return "That name works only inside a network, so we can't check it. Type the address people use on the internet."
    return None


def target(raw) -> tuple[str, str]:
    """(scheme, host) of what someone typed (a host name, or a whole link), or Refused."""
    text = str(raw or "").strip()
    if not text or len(text) > MAX_URL or any(c.isspace() or ord(c) < 32 for c in text):
        raise BadAddress(NOT_AN_ADDRESS)
    if not re.match(r"^[a-z][a-z0-9+.-]*://", text, re.I):
        if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", text, re.I):     # javascript:, file:, ...
            raise BadAddress(NOT_AN_ADDRESS)
        text = "https://" + text
    try:
        scheme, host, _port, _path = site_fetch.check_url(text)
    except Refused as why:
        if "port" in str(why).lower() or "password" in str(why).lower():
            raise                               # its own words say what to change
        raise BadAddress(NOT_AN_ADDRESS) from None
    why = host_refused(host)
    if why:
        raise Refused(why)
    return scheme, host


def family(host: str) -> str:
    """The domain a name belongs to: <site> for wp.<site>; three labels under a short two-letter one (co.uk)."""
    labels = host.lower().split(".")
    n = 3 if len(labels) >= 3 and len(labels[-1]) == 2 and len(labels[-2]) <= 3 else 2
    return ".".join(labels[-n:])


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


# ------------------------------------------------------------------ fetching

class Budget:
    """MAX_FETCHES requests and DEADLINE seconds for one check, and the log of each."""

    def __init__(self, fetches: int = MAX_FETCHES, seconds: float = DEADLINE,
                 clock=time.monotonic) -> None:
        self.fetches, self.used, self.clock = fetches, 0, clock
        self.end = clock() + seconds
        self.log: list[dict] = []

    def left(self) -> int:
        return self.fetches - self.used

    def seconds(self) -> float:
        left = min(TIMEOUT, self.end - self.clock())
        if left <= 0.2:
            raise Unreachable("it did not answer in time")
        return left

    def take(self) -> None:
        if self.used >= self.fetches:
            raise Spent()
        self.seconds()
        self.used += 1

    def note(self, method: str, url: str, got=None, error: str | None = None) -> None:
        row = {"method": method, "url": url[:300], "status": None, "bytes": None,
               "location": None, "error": error}
        if got is not None:
            row["status"] = got.status
            if method == "GET":
                row["bytes"] = len(got.body)
            else:
                length = (got.headers.get("content-length") or [""])[0]
                row["bytes"] = int(length) if length.isdigit() else None
            location = (got.headers.get("location") or [""])[0].strip()
            row["location"] = location[:300] or None
        self.log.append(row)


def get(url: str, method: str, budget: Budget, ua: str) -> site_fetch.Answer:
    """One request, no redirect followed: every rule checked, the name resolved once and the
    connection made to the address that passed (no second lookup to rebind). Logged."""
    try:
        scheme, host, port, path = site_fetch.check_url(url)
        why = host_refused(host)
        if why:
            raise Refused(why)
        addresses = site_fetch.resolve(host, port)
    except (Refused, Unreachable) as why:
        budget.note(method, url, error=str(why))
        raise
    try:
        budget.take()
    except Spent:
        budget.note(method, url, error=f"not fetched: the limit of {budget.fetches} requests")
        raise
    except Unreachable as why:
        budget.note(method, url, error=str(why))
        raise
    last = None
    for address in addresses[:site_fetch.MAX_ADDRESSES]:
        try:
            got = site_fetch.open_pinned(scheme, host, address, port, method, path,
                                         budget.seconds(), MAX_BYTES, agent=ua)
            budget.note(method, url, got)
            return got
        except ssl.SSLCertVerificationError as err:
            budget.note(method, url, error=site_fetch._words(err))
            raise Unreachable(site_fetch._words(err)) from None
        except (OSError, http.client.HTTPException) as err:
            last = err
    words = site_fetch._words(last) if last else "the connection failed"
    budget.note(method, url, error=words)
    raise Unreachable(words)


def location(got, base: str) -> str | None:
    if got.status not in site_fetch.REDIRECTS:
        return None
    loc = (got.headers.get("location") or [""])[0].strip()
    return urljoin(got.url or base, loc) if loc else None


def follow(url: str, budget: Budget, ua: str) -> site_fetch.Answer:
    """A GET at the end of at most MAX_REDIRECTS redirects, each hop checked as `get`."""
    for hop in range(MAX_REDIRECTS + 1):
        got = get(url, "GET", budget, ua)
        nxt = location(got, url)
        if not nxt:
            return got
        if hop == MAX_REDIRECTS:
            break
        url = nxt
    raise Refused(f"It redirected more than {MAX_REDIRECTS} times.")


# ------------------------------------------------------------------ reading

SECURITY_HEADERS = ("strict-transport-security", "content-security-policy", "x-frame-options",
                    "x-content-type-options", "referrer-policy")


def page_of(got, html: str | None = None) -> Page:
    if html is None:
        html = site_detect.read_page(got.body)[0] if got.body else ""
    return Page(url=got.url, host=host_of(got.url), status=got.status,
                headers=got.headers, html=html)


def origins_of(pg: Page, typed: str) -> list[str]:
    """Other hosts of the site's own domain its page loads WordPress files from, most first."""
    counts: Counter = Counter()
    for m in re.finditer(WP_ANY, pg.html, re.I):
        host = host_of("https:" + m.group(1) if m.group(1) and m.group(1).startswith("//")
                       else m.group(1) or "")
        if host and host not in (pg.host, typed) and family(host) == family(typed) \
                and not host_refused(host):
            counts[host] += 1
    return [h for h, _n in counts.most_common()]


def login(scheme: str, host: str, budget: Budget, ua: str) -> dict:
    """/wp-login.php followed to its final page within the domain, its body read."""
    url = f"{scheme}://{host}/wp-login.php"
    chain, current = [], url
    for _hop in range(LOGIN_HOPS + 1):
        try:
            got = get(current, "GET", budget, ua)
        except Spent:
            return {"state": "unknown", "url": url, "chain": chain,
                    "why": f"not fetched: the limit of {budget.fetches} requests"}
        except (Refused, Unreachable) as why:
            return {"state": "unknown", "url": url, "chain": chain, "why": str(why)}
        nxt = location(got, current)
        chain.append({"url": current, "status": got.status, "location": nxt})
        if nxt:
            if family(host_of(nxt)) != family(host):
                return {"state": "hidden", "url": url, "chain": chain,
                        "why": "it sends visitors to another domain"}
            current = nxt
            continue
        if challenged(got):
            return {"state": "unknown", "url": url, "chain": chain,
                    "why": "a bot challenge answered instead of the page"}
        body = got.body.decode("utf-8", "replace")
        if 200 <= got.status < 300:
            form = bool(LOGIN_FORM.search(body) or (LOG.search(body) and PWD.search(body)))
            return {"state": "open" if form else "hidden", "url": url, "chain": chain,
                    "why": "a WordPress login form" if form else "a page with no login form"}
        if got.status in HIDDEN:
            return {"state": "hidden", "url": url, "chain": chain, "why": f"it answers {got.status}"}
        return {"state": "unknown", "url": url, "chain": chain, "why": f"it answers {got.status}"}
    return {"state": "unknown", "url": url, "chain": chain, "why": "too many redirects"}


def once(url: str, budget: Budget, ua: str):
    """One GET, no redirect followed; None when it was not fetched or did not answer."""
    try:
        return get(url, "GET", budget, ua)
    except (Spent, Refused, Unreachable):
        return None


def wordpress_extras(scheme: str, host: str, budget: Budget, ua: str) -> dict:
    """xmlrpc.php (is XML-RPC on?) and readme.html (does it show a version?): one GET each."""
    out = {}
    got = once(f"{scheme}://{host}/xmlrpc.php", budget, ua)
    if got is not None:
        on = got.status == 405 and b"accepts post requests only" in got.body.lower()
        out["xmlrpc"] = {"url": got.url, "status": got.status, "on": on}
    got = once(f"{scheme}://{host}/readme.html", budget, ua)
    if got is not None:
        ver = re.search(rb"<br\s*/?>\s*Version\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", got.body, re.I)
        out["readme"] = {"url": got.url, "status": got.status,
                         "version": ver.group(1).decode() if ver and got.status == 200 else None}
    return out


def origin(host: str, site: Page, budget: Budget, ua: str) -> dict:
    """A WordPress host of the site's domain its page loads files from: proven by those files;
    then its login page, /wp-json/ (HEAD: its headers) and its home page (HEAD: headless?)."""
    n, _first, loaded = files(site, WP_ANY, f"file{{s}} under /wp-content/ or /wp-includes/ from {host}",
                              keep=f"^(https?:)?//{re.escape(host)}/")
    for line in loaded:
        line["text"] = line["text"].replace("We saw links to", f"We saw the page {site.url} load", 1)
    found = [{"product": "wordpress", "name": "WordPress", "version": None, "family": "cms",
              "runtime": "php", "patched": None, "saw": loaded, "host": host}]
    row = {"host": host, "role": "content origin", "found": found, "error": None}
    row["login"] = login("https", host, budget, ua)
    got = None
    try:
        got = get(f"https://{host}/wp-json/", "HEAD", budget, ua)
    except (Spent, Refused, Unreachable):
        pass
    if got is not None and not challenged(got):
        for f in detect(page_of(got, "")):
            if f["product"] == "wordpress":
                found[0]["saw"] += f["saw"]
            elif f["family"] in ("server", "cdn", "runtime"):
                found.append({**f, "host": host})
    try:
        got = get(f"https://{host}/", "HEAD", budget, ua)
        nxt = location(got, f"https://{host}/")
        if nxt and host_of(nxt) != host:
            row["headless"] = {"url": f"https://{host}/", "status": got.status, "location": nxt[:300]}
    except (Spent, Refused, Unreachable):
        pass
    return row


def read(scheme: str, host: str, ua: str, budget: Budget | None = None) -> dict:
    """The check itself: {hosts: [...], fetched: [...]}. Refused propagates (the address or
    a redirect of the home page is not checked); a site that cannot be read is an answer."""
    budget = budget or Budget()

    def unread(words, reason):
        return {"hosts": [{"host": host, "role": "site", "error": words, "found": [],
                           "read": False}], "fetched": budget.log, "fetches": budget.used,
                "reason": reason}
    try:
        home = follow(f"{scheme}://{host}/", budget, ua)
    except Unreachable as why:
        return unread(plain(str(why)), "unreachable")
    except Spent:
        return unread("it redirected too often", "error")
    block = blocker(home, host_of(home.url) or host)
    if block:
        out = unread({"challenge": "a bot challenge answered instead of the page",
                      "password": f"the home page answered {home.status} (it asks for a password)",
                      "denied": f"the home page answered {home.status}"}[block["kind"]], "blocked")
        out["block"] = block
        return out
    if not 200 <= home.status < 300:
        return unread(f"the home page answered {home.status}", "error")
    pg = page_of(home)
    found = detect(pg)
    row = {"host": pg.host, "role": "site", "error": None, "read": True, "found": found,
           "url": home.url, "not_after": home.not_after,
           "headers": {h: home.headers.get(h) for h in SECURITY_HEADERS if home.headers.get(h)}}
    wp = next((f for f in found if f["product"] == "wordpress" and not f.get("patched")), None)
    if wp:
        site_scheme = urlsplit(home.url).scheme or scheme
        row["login"] = login(site_scheme, pg.host, budget, ua)
        row["extras"] = wordpress_extras(site_scheme, pg.host, budget, ua)
    hosts = [row]
    wanted = origins_of(pg, host)
    if wanted:
        hosts.append(origin(wanted[0], pg, budget, ua))
    return {"hosts": hosts, "fetched": budget.log, "fetches": budget.used,
            "moved": home.url if home.url.rstrip("/") != f"{scheme}://{host}" else None}


def check(raw, config: dict | None = None, doc: dict | None = None,
          now: datetime | None = None) -> dict:
    """The whole check for what someone typed. Refused (in plain words) when the address
    is not checked; a site that cannot be read is an answer with `reached` false."""
    from .stack_public_cards import answer
    scheme, host = target(raw)
    ua = agent(config)
    blob = read(scheme, host, ua)
    return answer(host, blob, doc or advisories.load(), now or datetime.now(timezone.utc), ua)
