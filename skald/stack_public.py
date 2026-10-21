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
    "Just a moment..."), is "could not check": nothing is read from it;
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
    seconds for a whole check, MAX_REDIRECTS redirects, each hop checked again;
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
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from . import advisories, site_detect, site_fetch

TIMEOUT = 5.0              # seconds for one request
DEADLINE = 9.0             # seconds for a whole check (the proxy in front waits 10)
MAX_BYTES = 512 * 1024     # of one body
MAX_FETCHES = 4            # requests in one check, redirects included
MAX_REDIRECTS = 3
MAX_URL = 500
EXAMPLES = 2               # examples shown of each kind of evidence
# Last labels that only work inside a network, or are reserved (RFC 2606, 6761, 6762, 8375).
INSIDE = {"localhost", "local", "internal", "intranet", "lan", "home", "corp", "private",
          "localdomain", "test", "invalid", "example", "arpa", "onion", "alt"}
HEADERS = ("server", "x-powered-by", "link")
NAMES = {"server": "Server", "x-powered-by": "X-Powered-By", "link": "Link"}
WP_REF = re.compile(r"(?:(?:https?:)?//([a-z0-9][a-z0-9.-]*[a-z0-9])(?::\d+)?)?"
                    r"(/wp-(?:content|includes)/[^\"'\s<>()\\]*)", re.I)
NEXT_REF = re.compile(r"(?:https?://[a-z0-9.-]+)?/_next/[^\"'\s<>()\\]*", re.I)
GENERATOR = re.compile(r"<meta\b[^>]*\bname\s*=\s*[\"']?generator[\"']?[^>]*>", re.I)
LOGIN_FORM = re.compile(r"id\s*=\s*[\"']loginform[\"']", re.I)
LOG, PWD = (re.compile(rf"name\s*=\s*[\"']{n}[\"']", re.I) for n in ("log", "pwd"))
CHALLENGE = (b"challenge-platform", b"just a moment...", b"attention required!",
             b"cf-browser-verification", b"captcha")
HIDDEN = (401, 403, 404, 410)
Refused = site_fetch.Refused
Unreachable = site_fetch.Unreachable


class Spent(Exception):
    """The check's requests are used up: what is left is not read."""


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
        return "That name works only inside a network, or is kept for tests, so it is not checked."
    return None


def target(raw) -> tuple[str, str]:
    """(scheme, host) of what someone typed (a host name, or a whole link), or Refused."""
    text = str(raw or "").strip()
    if not text or len(text) > MAX_URL or any(c.isspace() or ord(c) < 32 for c in text):
        raise Refused("Type your site's address, as you would in a browser.")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", text, re.I):
        if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", text, re.I):     # javascript:, file:, ...
            raise Refused("Only http and https addresses are checked.")
        text = "https://" + text
    scheme, host, _port, _path = site_fetch.check_url(text)
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


def challenged(got) -> bool:
    """A bot challenge (Cloudflare's and the like) answered instead of the page."""
    if (got.headers.get("cf-mitigated") or [""])[0].strip().lower() == "challenge":
        return True
    return got.status in (403, 429, 503) and any(m in got.body[:30000].lower() for m in CHALLENGE)


# ------------------------------------------------------------------ reading

def proof(got, html: str = "", page=None) -> dict:
    """What one answer says, exactly as received: header lines, the generator tag, the
    WordPress and Next.js references in the page (counts and the first examples)."""
    own = host_of(got.url)
    headers = []
    for name in HEADERS:
        for value in got.headers.get(name) or []:
            if name == "link" and "api.w.org" not in value.lower():
                continue
            headers.append(f"{NAMES[name]}: {value.strip()[:300]}")
    wp: dict[str, dict] = {}
    for m in WP_REF.finditer(html or ""):
        where = (m.group(1) or own).lower()
        found = wp.setdefault(where, {"count": 0, "examples": []})
        found["count"] += 1
        if len(found["examples"]) < EXAMPLES:
            full = m.group(0) if m.group(1) else f"https://{own}{m.group(2)}"
            full = "https:" + full if full.startswith("//") else full
            if full[:300] not in found["examples"]:
                found["examples"].append(full[:300])
    nxt = NEXT_REF.findall(html or "")
    tag = GENERATOR.search(html or "")
    return {"url": got.url, "status": got.status, "headers": headers,
            "generator": (page.generator if page is not None else "")[:80],
            "generator_tag": tag.group(0)[:200] if tag else None, "wp": wp,
            "next": {"count": len(nxt), "examples": list(dict.fromkeys(nxt))[:EXAMPLES],
                     "data": "__NEXT_DATA__" in (html or "")}}


def evidence(pr: dict, host: str, loaded: bool = False) -> dict:
    """stack.products' evidence from a proof. WordPress paths count for a host only when the
    files are its own (or `loaded`: the site's page loads them from it)."""
    line = {n: ", ".join(h.split(": ", 1)[1] for h in pr["headers"] if h.lower().startswith(n + ":"))
            for n in ("server", "x-powered-by")}
    markers = []
    if loaded or host in pr["wp"]:
        markers.append("wp-content")
    if pr["next"]["count"]:
        markers.append("_next")
    if pr["next"]["data"]:
        markers.append("__NEXT_DATA__")
    if any(h.lower().startswith("link:") for h in pr["headers"]):
        markers.append("wp-json link")
    return {"status": pr["status"], "server": line["server"], "powered_by": line["x-powered-by"],
            "generator": pr["generator"], "markers": markers}


def is_wordpress(ev: dict) -> bool:
    return bool(re.match(r"^\s*WordPress", ev.get("generator") or "", re.I)
                or {"wp-content", "wp-json link"} & set(ev.get("markers") or []))


def login(scheme: str, host: str, budget: Budget, ua: str) -> dict:
    """/wp-login.php followed to its final page within the domain, its body read."""
    url = f"{scheme}://{host}/wp-login.php"
    chain, current = [], url
    for _hop in range(MAX_REDIRECTS + 1):
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


def origin(host: str, site_pr: dict, budget: Budget, ua: str) -> dict:
    """A WordPress host the site's page loads files from: its login page, /wp-json/, home."""
    row = {"host": host, "role": "content origin", "error": None, "proof": None,
           "loaded": {**site_pr["wp"][host], "page": site_pr["url"]}}
    row["login"] = login("https", host, budget, ua)
    pr = None
    try:
        got = get(f"https://{host}/wp-json/", "HEAD", budget, ua)
        if not challenged(got):
            pr = proof(got)
    except (Spent, Refused, Unreachable):
        pass
    row["proof"] = pr or {"url": f"https://{host}/", "status": None, "headers": [], "generator": "",
                          "generator_tag": None, "wp": {}, "next": {"count": 0, "examples": [],
                                                                    "data": False}}
    row["evidence"] = evidence(row["proof"], host, loaded=True)
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

    def unread(words):
        return {"hosts": [{"host": host, "role": "site", "error": words, "proof": None,
                           "evidence": None}], "fetched": budget.log, "fetches": budget.used}
    try:
        home = follow(f"{scheme}://{host}/", budget, ua)
    except Unreachable as why:
        return unread(str(why))
    except Spent:
        return unread("it redirected too often")
    if challenged(home):
        return unread("a bot challenge (for example Cloudflare's \"Just a moment\") answered "
                      "instead of the page")
    if not 200 <= home.status < 300:
        return unread(f"the home page answered {home.status}")
    final = host_of(home.url) or host
    html, page = site_detect.read_page(home.body)
    pr = proof(home, html, page)
    row = {"host": final, "role": "site", "error": None, "proof": pr,
           "evidence": evidence(pr, final)}
    if is_wordpress(row["evidence"]):
        row["login"] = login(urlsplit(home.url).scheme or scheme, final, budget, ua)
    hosts = [row]
    wanted = sorted((h for h in pr["wp"] if h not in (host, final) and family(h) == family(host)
                     and not host_refused(h)), key=lambda h: -pr["wp"][h]["count"])
    if wanted:
        hosts.append(origin(wanted[0], pr, budget, ua))
    return {"hosts": hosts, "fetched": budget.log, "fetches": budget.used}


def check(raw, config: dict | None = None, doc: dict | None = None,
          now: datetime | None = None) -> dict:
    """The whole check for what someone typed. Refused (in plain words) when the address
    is not checked; a site that cannot be read is an answer with `reached` false."""
    from .stack_public_cards import answer
    scheme, host = target(raw)
    ua = agent(config)
    blob = read(scheme, host, ua)
    return answer(host, blob, doc or advisories.load(), now or datetime.now(timezone.utc), ua)
