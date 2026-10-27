"""The script tag's page check, for the set-up Test (POST <page>/sites/tagcheck,
connections_api.py): when nothing from the tag has reached Skald, look at the
site's home page from outside and say what is wrong, in plain words.

  1. GET https://<site>/ (redirects followed), by site_fetch's safe rules.
  2. Find the tag: a <script src=".../skald.js"> or ".../traffic-js/...", else
     that address inside a loader (Next.js's script list, a tag manager's
     inline code). Its src and its data-endpoint.
  3. Where it posts, as skald.js decides: data-endpoint; else beside its src
     (.../traffic-js/skald.js gives .../traffic-beacon); else the page's own
     /traffic-beacon (a copy served from another folder, as before 2.24.0).
  4. Checks, the first that fails is the answer:
       * the page's origin is one the beacon helper takes (`origins`): else 403;
       * a first-party src loads (GET, 200); Skald's own must be its path;
       * a post address that is not Skald's own reaches Skald: POST with
         `X-Skald-Probe: 1` and no body; the helper answers 200 with
         X-Skald-Beacon (beacon_server.py), so a 308, 404 or 405 is the
         site's own server answering, and nothing is counted anywhere;
       * the page's Content-Security-Policy (header or <meta>) lets it
         connect there (connect-src, else default-src).

The answer: {state, words, fix, facts}. state "ok" (every check passed),
"problem" (one failed: words say which, fix what to do), "unknown" (the page
could not be read, or the tag is not in its HTML, which a tag manager can
hide). facts: the page, the tag's src, where it posts, what that answered.
Nothing from the page beyond those addresses; nothing kept.
"""
from __future__ import annotations

import html as htmllib
import re
import time
from urllib.parse import urljoin, urlsplit

from . import site_fetch

DEADLINE = 15.0                    # seconds for the whole check
SCRIPT = re.compile(r"<script\b([^>]*)>", re.I)
ATTR = re.compile(r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?""")
LOADER = re.compile(r"""["'](?P<u>(?:https?:)?//[^"'\s<>]+?/traffic-js/[^"'\s<>]*|"""
                    r"""/[^"'\s<>]*?traffic-js/[^"'\s<>]*)["']""")
LOADER_ENDPOINT = re.compile(r"""["']?data-endpoint["']?\s*[:=,]\s*["']([^"'<>\s]+)["']""")
TAG_MANAGER = re.compile(r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]{4,}")
META_CSP = re.compile(r"""<meta\b[^>]*http-equiv\s*=\s*["']?content-security-policy["']?[^>]*>""", re.I)
FOLDER = re.compile(r"^(?P<dir>.*)/traffic-js/[^/]*$")


def _attrs(text: str) -> dict:
    out = {}
    for m in ATTR.finditer(text):
        value = m.group(2) if m.group(2) is not None else m.group(3) if m.group(3) is not None \
            else m.group(4) or ""
        out.setdefault(m.group(1).lower(), htmllib.unescape(value))
    return out


def _ours(src: str) -> bool:
    path = urlsplit(src).path.lower()
    return "/traffic-js/" in path or path.endswith("/skald.js") or path.endswith("/skald.min.js")


def find_tag(page: str, page_url: str) -> dict | None:
    """{src, endpoint, how}: the tag in the page's HTML ("tag"), or its address
    in a loader's code ("loader"); None when neither is there."""
    for m in SCRIPT.finditer(page):
        a = _attrs(m.group(1))
        src = a.get("src") or ""
        if src and _ours(src):
            return {"src": urljoin(page_url, src), "endpoint": a.get("data-endpoint") or "",
                    "how": "tag"}
    flat = page.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
    got = LOADER.search(flat)
    if got:
        near = LOADER_ENDPOINT.search(flat, max(0, got.start() - 400), got.end() + 400)
        return {"src": urljoin(page_url, htmllib.unescape(got.group("u"))),
                "endpoint": near.group(1) if near else "", "how": "loader"}
    return None


def endpoint_for(src: str, endpoint: str, page_url: str) -> str:
    """Where skald.js posts (absolute), by its own rule (skald.js `ep`)."""
    if endpoint:
        return urljoin(page_url, endpoint)
    parts = urlsplit(src or "")
    m = FOLDER.match(parts.path or "")
    if parts.scheme in ("http", "https") and m:
        return f"{parts.scheme}://{parts.netloc}{m.group('dir')}/traffic-beacon"
    return urljoin(page_url, "/traffic-beacon")


def origin_of(url: str) -> str:
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    port = f":{p.port}" if p.port and p.port != {"http": 80, "https": 443}.get(p.scheme) else ""
    return f"{p.scheme}://{host}{port}"


def shown(url: str) -> str:
    """An address as people say it: no https://, no trailing slash on a bare host."""
    p = urlsplit(url)
    return f"{p.netloc}{p.path if p.path not in ('', '/') else ''}"


# ---------------------------------------------------------------- CSP

def _source_allows(source: str, target: str, page_origin: str) -> bool:
    s = source.strip().lower()
    t = urlsplit(target)
    if s == "*":
        return t.scheme in ("http", "https")
    if s == "'self'":
        return origin_of(target) == page_origin
    if re.fullmatch(r"[a-z][a-z0-9+.-]*:", s):
        return t.scheme == s[:-1] or (s == "http:" and t.scheme == "https")
    if s.startswith("'"):
        return False                    # 'none', nonces, hashes: no address
    scheme, _, rest = s.rpartition("://")
    if scheme and scheme != t.scheme and not (scheme == "http" and t.scheme == "https"):
        return False
    host = rest.split("/", 1)[0].split(":", 1)[0]
    name = (t.hostname or "").lower()
    if host.startswith("*."):
        return name.endswith(host[1:])
    return name == host


def csp_allows(policies: list[str], target: str, page_origin: str) -> bool:
    """Every policy lets the page connect to `target` (connect-src, else
    default-src; a policy with neither allows it)."""
    for policy in policies:
        found = {}
        for part in policy.split(";"):
            words = part.split()
            if words:
                found.setdefault(words[0].lower(), words[1:])
        sources = found.get("connect-src", found.get("default-src"))
        if sources is None:
            continue
        if not any(_source_allows(s, target, page_origin) for s in sources):
            return False
    return True


def policies_of(answer, page: str) -> list[str]:
    out = [p.strip() for v in answer.headers.get("content-security-policy", [])
           for p in v.split(",") if p.strip()]
    for m in META_CSP.finditer(page):
        content = _attrs(m.group(0)[5:]).get("content")
        if content:
            out.append(content)
    return out


# -------------------------------------------------------------- the check

def _answer(state: str, words: str, fix: str = "", **facts) -> dict:
    return {"state": state, "words": words, "fix": fix, "facts": facts}


def check(site: str, origins: set[str], skald: str) -> dict:
    """The page check for `site` (its name, the address fetched). `origins`:
    the Origins the beacon helper takes for it; `skald`: this Skald's own
    address (its base URL), where the plain tag loads from."""
    deadline = time.monotonic() + DEADLINE
    skald = origin_of(skald) if skald else ""
    home = f"https://{site}/"
    try:
        got, _ = site_fetch.follow(home, "GET", deadline)
    except (site_fetch.Refused, site_fetch.Unreachable) as why:
        return _answer("unknown", f"Skald could not open {shown(home)}: {why}",
                       "Check that the address opens in a browser.", page=home)
    page_url = got.url or home
    if got.status != 200:
        return _answer("unknown", f"Your home page, {shown(page_url)}, answered {got.status}, "
                       "so Skald could not look for the tag.", page=page_url)
    page = got.body.decode("utf-8", "replace")
    tag = find_tag(page, page_url)
    facts = {"page": page_url}
    if tag is None:
        if TAG_MANAGER.search(page):
            return _answer("unknown", f"The tag is not in the HTML of {shown(page_url)}. "
                           "The page loads Google Tag Manager, which may add it.",
                           "If the tag is in Tag Manager: publish the container, and make it "
                           "fire on All Pages.", **facts)
        return _answer("problem", f"The tag is not on your home page ({shown(page_url)}).",
                       "Add the line from step 2 to the <head> of every page, then publish "
                       "the site.", **facts)
    target = endpoint_for(tag["src"], tag["endpoint"], page_url)
    facts.update(src=tag["src"], posts_to=target, how=tag["how"])
    here = origin_of(page_url)
    if here not in origins:
        return _answer("problem", f"Your page is at {shown(here)}, which is not one of "
                       f"{site}'s host names, so Skald refuses its events (403).",
                       f"Add {urlsplit(here).hostname} to the site's host names in "
                       "Settings > Site.", **facts)
    src_origin = origin_of(tag["src"])
    if skald and src_origin == skald:
        if urlsplit(tag["src"]).path != "/traffic-js/skald.js":
            return _answer("problem", f"The tag is on your page, but its address, "
                           f"{shown(tag['src'])}, is not Skald's script.",
                           "Copy the line from step 2 again.", **facts)
    elif src_origin == here:
        try:
            loads = site_fetch.fetch(tag["src"], "GET", deadline, max_bytes=1024)
        except (site_fetch.Refused, site_fetch.Unreachable) as why:
            loads = None
            facts["script"] = str(why)
        if loads is not None and loads.status != 200:
            facts["script"] = loads.status
            return _answer("problem", f"The tag is on your page, but its script, "
                           f"{shown(tag['src'])}, answers {loads.status}.",
                           _proxy_fix(skald, "/traffic-js/"), **facts)
    if not (skald and origin_of(target) == skald):
        try:
            probe = site_fetch.fetch(target, "POST", deadline, max_bytes=0,
                                     headers={"X-Skald-Probe": "1"})
        except (site_fetch.Refused, site_fetch.Unreachable) as why:
            facts["answered"] = str(why)
            return _answer("problem", f"The tag is on your page but posts to {shown(target)}, "
                           f"which does not answer ({why}).", _proxy_fix(skald), **facts)
        facts["answered"] = probe.status
        if probe.header("x-skald-beacon") != "1":
            return _answer("problem", f"The tag is on your page but posts to {shown(target)}, "
                           f"which answers {probe.status}.", _proxy_fix(skald), **facts)
    if not csp_allows(policies_of(got, page), target, here):
        return _answer("problem", "The tag is on your page, but the page's "
                       f"Content-Security-Policy does not let it send to {shown(origin_of(target))}, "
                       "so the browser blocks every event.",
                       f"Add {origin_of(target)} to connect-src in that policy.", **facts)
    return _answer("ok", f"The tag is on your page, and its events go to {shown(target)}, "
                   "which reaches Skald.",
                   "So the page is right. Open it in a normal browser window, without an ad "
                   "blocker, with Do Not Track and Global Privacy Control off. A browser that "
                   "opened the site in the last day may still run the older script: empty its "
                   "cache or use a private window.", **facts)


def _proxy_fix(skald: str, path: str = "/traffic-beacon") -> str:
    where = f" (it loads from {shown(skald)} and posts there)" if skald else ""
    return (f"Update to the latest tag in step 2{where}. Or, to keep serving it from your own "
            f"domain, pass {path} on to Skald from your server: see "
            "\"Advanced: serve it from your own domain\" in step 2.")
