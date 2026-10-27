"""The site check of the "Add a site" wizard: how is this site hosted?

The owner types an address; Skald looks at the site from outside, the way a
browser would, and suggests how its visits should reach Skald. Every answer
is a suggestion the owner can change: the check never decides alone.

`detect(address)` fetches https://<host>/ and https://www.<host>/ (or the
bare host when the address starts with www.), through site_fetch.py: HEAD
first, following at most 3 redirects by hand, then a GET of the first
256 KB when the headers alone do not say enough. It returns plain facts:

  reachable      an HTTP answer came back from either name
  final_url      where the address ends after its redirects
  https          that answer came over https
  hosts          the names that answer the same site (both, when one
                 redirects to the other, or both answer alike), and
  redirects      [{from, to}]: which name sends people to which
  server         nginx, apache, litespeed, caddy, iis or unknown (the
                 Server header), with server_detail and os when it says
  platform       a host in front of or instead of a server: cloudflare
                 (proxied), vercel, netlify, cloudfront, fastly,
                 github_pages, or a hosted builder (shopify, wix,
                 squarespace, webflow), or None
  framework      nextjs, nuxt, wordpress, gatsby, astro, plain, or None
  asset_prefixes what Settings > Data > What counts would take (checked by
                 settings_store's own rule), or None
  recommended_method  one of the wizard's ways (accounts/site_setup.py
                 METHODS), or None, with `reason` in one plain line
  log_note       LOG_NOTE for a Next.js site whose own nginx, Apache or
                 LiteSpeed log the shipper will read: the one field its
                 log_format needs so pages opened inside the site count
                 (parse.Hit.soft_navigation); "" otherwise. Caddy logs the
                 request headers already; a drain or a Worker carries none.
  checked        per name: reachable, status, final_url, error (words)
  tags           what the page already fetched names of the site's own tools
                 (From your tools, docs/TOOLS.md): {"ga4": ["G-..."], "calendly":
                 ["calendly.com/<name>/<event>"]}, at most 3 each; {} when no page
                 was read. Read from the same GET, never a fetch of its own.
                 2.43: also "calcom" (cal.com/<name>), "stripe" (its script or a buy
                 link's host) and "hubspot" (its tracking or forms script)
  forms          how many <form> tags that page has (at most FORMS_MOST), or None

The recommendation table is `recommend`. Nothing here names a site.
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit

from . import site_fetch

DEADLINE = 25.0                    # seconds for one whole check, both names
SERVERS = {"nginx": "nginx", "apache": "Apache", "litespeed": "LiteSpeed", "caddy": "Caddy",
           "iis": "Microsoft IIS", "unknown": "unknown"}
OWN_SERVERS = ("nginx", "apache", "litespeed", "caddy")
PLATFORMS = {"shopify": "Shopify", "wix": "Wix", "squarespace": "Squarespace",
             "webflow": "Webflow", "cloudflare": "Cloudflare (proxied)", "vercel": "Vercel",
             "netlify": "Netlify", "github_pages": "GitHub Pages", "cloudfront": "CloudFront",
             "fastly": "Fastly"}
BUILDERS = ("shopify", "wix", "squarespace", "webflow")
FRAMEWORKS = {"nextjs": "Next.js", "nuxt": "Nuxt", "wordpress": "WordPress",
              "gatsby": "Gatsby", "astro": "Astro", "plain": "plain HTML (no framework seen)"}
ASSETS = {"nextjs": ["/_next/static/"], "nuxt": ["/_nuxt/"],
          "wordpress": ["/wp-content/", "/wp-includes/"], "astro": ["/_astro/"],
          "gatsby": ["/webpack-runtime-", "/page-data/"]}
METHODS = ("docker", "systemd", "cloudflare", "vercel", "netlify", "script")
# Servers whose log_format needs the field that records Next.js's prefetch header.
LOG_FORMAT_SERVERS = ("nginx", "apache", "litespeed")
LOG_NOTE = ("Next.js: add rsc_prefetch=$http_next_router_prefetch at the end of the site's "
            "nginx log_format (Apache: rsc_prefetch=%{Next-Router-Prefetch}i), then reload "
            "nginx, so pages opened by a click inside the site count.")
PRINTABLE = re.compile(r"[^\x20-\x7e]")
# The site's own tools named in its page (docs/TOOLS.md): suggestions, nothing more.
TAGS = {"ga4": re.compile(r"(?:googletagmanager\.com/gtag/js\?id=|gtag\(\s*['\"]config['\"]\s*,"
                          r"\s*['\"])(G-[A-Z0-9]{4,15})\b"),
        "calendly": re.compile(r"\b(calendly\.com/[A-Za-z0-9_-]{1,60}(?:/[A-Za-z0-9_-]{1,60})?)"),
        # 2.43: Cal.com links, Stripe's and HubSpot's scripts, so Leads & tools and the "not
        # connected yet" card can say what the site already uses (js/connect-plan.js).
        "calcom": re.compile(r"(?<![\w.-])((?:app\.)?cal\.com/(?!embed\b)[A-Za-z0-9_-]{1,60}"
                             r"(?:/[A-Za-z0-9_-]{1,60})?)"),
        "stripe": re.compile(r"\b((?:js|buy|checkout)\.stripe\.com)\b"),
        "hubspot": re.compile(r"\b(js\.(?:hs-scripts\.com|hsforms\.net|hs-analytics\.net)"
                              r"|[a-z0-9-]{1,30}\.hsforms\.com)\b")}
TAG_SHAPES = {"ga4": re.compile(r"G-[A-Z0-9]{4,15}"),
              "calendly": re.compile(r"calendly\.com/[A-Za-z0-9_-]{1,60}(?:/[A-Za-z0-9_-]{1,60})?"),
              "calcom": re.compile(r"(?:app\.)?cal\.com/[A-Za-z0-9_-]{1,60}(?:/[A-Za-z0-9_-]{1,60})?"),
              "stripe": re.compile(r"(?:js|buy|checkout)\.stripe\.com"),
              "hubspot": re.compile(r"js\.(?:hs-scripts\.com|hsforms\.net|hs-analytics\.net)"
                                    r"|[a-z0-9-]{1,30}\.hsforms\.com")}
FORMS_MOST = 20                    # <form> tags counted on the home page, at most


def _short(value, most: int) -> str:
    return PRINTABLE.sub("", str(value or "")).strip()[:most]


def clean_address(raw) -> str:
    """The host the owner typed (a whole link works), as the site's name is
    made (accounts/site_configs.clean_name); ValueError in plain words.
    An address that is an IP is refused: a site is a name."""
    from .accounts.site_configs import clean_name
    got = str(raw or "").strip().lower()
    if "://" in got:
        got = got.split("://", 1)[1]
    got = got.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "@" in got or ":" in got:
        raise ValueError("Type the site's address alone: its name, with no port or user name.")
    name = clean_name(got)
    if re.fullmatch(r"[\d.]+", name):
        raise ValueError("Type the site's name, not an IP address.")
    return name


def pair(host: str) -> tuple[str, str]:
    """The typed name and its other form: www. added, or taken off."""
    return host, (host[4:] if host.startswith("www.") else f"www.{host}")


# --------------------------------------------------------------- the page

class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.generator = ""
        self.title = ""
        self.ids: set[str] = set()
        self.attrs: set[str] = set()
        self.assets: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        got = {str(k).lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if got.get("id"):
            self.ids.add(got["id"])
        self.attrs.update(k for k in got if k.startswith("data-wf-"))
        if tag == "meta" and got.get("name", "").lower() == "generator":
            self.generator = self.generator or _short(got.get("content"), 80)
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and got.get("src"):
            self.assets.append(got["src"])
        elif tag == "link" and got.get("href") and set(got.get("rel", "").lower().split()) \
                & {"stylesheet", "preload", "modulepreload"}:
            self.assets.append(got["href"])

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and len(self.title) < 200:
            self.title += data


def forms_of(html: str) -> int:
    """How many <form> tags the page has, at most FORMS_MOST (Leads & tools says so)."""
    return min(FORMS_MOST, len(re.findall(r"<form\b", html or "", re.I)))


def tags_of(html: str) -> dict:
    """{"ga4": [...], "calendly": [...], "calcom", "stripe", "hubspot"} named in the page's
    text, each at most 3."""
    out = {}
    for kind, rx in TAGS.items():
        seen = []
        for got in rx.findall(html or ""):
            if got not in seen:
                seen.append(got)
        if seen:
            out[kind] = seen[:3]
    return out


def read_page(body: bytes) -> tuple[str, _Page]:
    text = (body or b"")[:site_fetch.MAX_BYTES].decode("utf-8", "replace")
    page = _Page()
    try:
        page.feed(text)
        page.close()
    except Exception:                       # noqa: BLE001 - a broken page says less
        pass
    page.title = " ".join(page.title.split())[:120]
    return text, page


# ------------------------------------------------------------ the reading

def server_of(headers: dict) -> tuple[str, str, str]:
    """(server id, the Server header as shown, the OS it names or "")."""
    raw = _short(", ".join(headers.get("server", [])), 80)
    low = raw.lower()
    kind = ("nginx" if low.startswith(("nginx", "openresty")) else
            "apache" if low.startswith("apache") else
            "litespeed" if low.startswith("litespeed") else
            "caddy" if low.startswith("caddy") else
            "iis" if low.startswith("microsoft-iis") else "unknown")
    found = re.search(r"\(([A-Za-z][A-Za-z0-9 ._-]{0,30})\)", raw) if kind != "unknown" else None
    return kind, raw, (found.group(1) if found else "")


def _has(headers: dict, *names) -> bool:
    return any(n in headers for n in names)


def _value(headers: dict, name: str) -> str:
    return ", ".join(headers.get(name, [])).lower()


def platform_of(headers: dict, html: str = "", page: _Page | None = None) -> str | None:
    """The host in front of (or instead of) a server, first match wins: the
    hosted builders (they bring their own CDN), then Cloudflare's proxy,
    Vercel, Netlify, GitHub Pages, CloudFront, Fastly."""
    page = page or _Page()
    server = _value(headers, "server")
    gen = page.generator.lower()
    powered = _value(headers, "powered-by") + " " + _value(headers, "x-powered-by")
    if _has(headers, "x-shopid", "x-shopify-stage") or "shopify" in powered \
            or "cdn.shopify.com" in html or "Shopify.theme" in html:
        return "shopify"
    if _has(headers, "x-wix-request-id") or server.startswith("pepyaka") \
            or gen.startswith("wix.com") or "static.wixstatic.com" in html:
        return "wix"
    if server.startswith("squarespace") or "static1.squarespace.com" in html \
            or gen.startswith("squarespace"):
        return "squarespace"
    if "data-wf-site" in page.attrs or "data-wf-page" in page.attrs or gen.startswith("webflow"):
        return "webflow"
    if _has(headers, "cf-ray") or server == "cloudflare":
        return "cloudflare"
    if _has(headers, "x-vercel-id", "x-vercel-cache") or server == "vercel":
        return "vercel"
    if _has(headers, "x-nf-request-id") or server == "netlify":
        return "netlify"
    if _has(headers, "x-github-request-id") or server == "github.com":
        return "github_pages"
    if _has(headers, "x-amz-cf-id", "x-amz-cf-pop") or "cloudfront" in _value(headers, "via") \
            or "cloudfront" in _value(headers, "x-cache") or server == "cloudfront":
        return "cloudfront"
    if any(n.startswith(("x-fastly", "fastly-")) for n in headers) \
            or re.search(r"\bcache-[a-z0-9-]+", _value(headers, "x-served-by")):
        return "fastly"
    return None


def framework_of(headers: dict, html: str = "", page: _Page | None = None) -> str | None:
    """What the pages are built with: the generator tag decides first, then
    X-Powered-By, then the page's own markers. "plain" when a page was read
    and nothing was seen; None when no page was read and no header says."""
    page = page or _Page()
    gen = page.generator.lower()
    for word, kind in (("wordpress", "wordpress"), ("gatsby", "gatsby"), ("astro", "astro"),
                       ("nuxt", "nuxt"), ("next.js", "nextjs")):
        if gen.startswith(word):
            return kind
    powered = _value(headers, "x-powered-by")
    if "next.js" in powered or any(n.startswith("x-nextjs-") for n in headers):
        return "nextjs"
    if "nuxt" in powered:
        return "nuxt"
    if "/_next/static/" in html or "__NEXT_DATA__" in html or "__next" in page.ids:
        return "nextjs"
    if "/_nuxt/" in html or "__nuxt" in page.ids or "window.__NUXT__" in html:
        return "nuxt"
    if "___gatsby" in page.ids or "/page-data/" in html:
        return "gatsby"
    if "/_astro/" in html:
        return "astro"
    if "/wp-content/" in html or "/wp-includes/" in html \
            or "api.w.org" in _value(headers, "link"):
        return "wordpress"
    if html.strip():
        return "plain"
    return None


def _valid_prefixes(items) -> list[str] | None:
    from .settings_store import Invalid, validate
    try:
        return validate("site.asset_prefixes", list(items)) if items else None
    except Invalid:
        return None


def assets_of(framework: str | None, page: _Page | None, hosts) -> tuple[list | None, str]:
    """(asset_prefixes for Settings > Data > What counts, or None; and a
    note). A framework's own folders first; else the folders this page
    loads its scripts and styles from, on its own names; else None."""
    if framework in ASSETS:
        return _valid_prefixes(ASSETS[framework]), f"{FRAMEWORKS[framework]} pages load their files from there."
    if page is None or not page.assets:
        return None, ""
    counts: dict[str, int] = {}
    elsewhere = 0
    for src in page.assets[:200]:
        try:
            parts = urlsplit(src)
        except ValueError:
            continue
        if parts.netloc and (parts.hostname or "") not in hosts:
            elsewhere += 1
            continue
        path = parts.path if src.startswith(("/", "http:", "https:")) or parts.netloc else ""
        if not path.startswith("/") or path == "/":
            continue
        first = path.split("/")[1]
        prefix = f"/{first}/" if path.count("/") > 1 else path
        counts[prefix] = counts.get(prefix, 0) + 1
    if not counts:
        if elsewhere:
            return None, ("Its scripts and styles come from another address, so this "
                          "server's log never sees them.")
        return None, ""
    top = sorted(counts, key=lambda p: (-counts[p], p))[:3]
    return _valid_prefixes(top), "The page loads its scripts and styles from there."


# ------------------------------------------------------- the recommendation

def recommend(site: str, facts: dict) -> tuple[str | None, str]:
    """(one of METHODS or None, one plain line why). The table:

      not reachable                 None    choose by hand
      Shopify, Wix, Squarespace,
      Webflow (hosted builders)     script  their server log cannot be read
      Cloudflare (proxied)          cloudflare  the Worker sees every request
      Vercel                        vercel  its log drain
      Netlify                       vercel  ("Vercel or Netlify": its log drain)
      GitHub Pages                  script  no log to read
      CloudFront or Fastly in front
        of nginx/Apache/LiteSpeed/Caddy  docker  the origin's log (cached pages missed)
        of an unseen server         None    choose by hand
      nginx, Apache, LiteSpeed,
      Caddy                         docker  the one-command install on that server
      Microsoft IIS                 script  the one-command install is for Linux servers
      anything else                 None    choose by hand

    "docker" is the id this has always returned for a site's own server; the
    page shows it as the one server way, "My own server" (conn-words.js
    OLD_WAYS), and log_note keys on it.
    """
    if not facts.get("reachable"):
        why = facts.get("error") or "no answer"
        return None, f"Skald could not reach {site} from here ({why}). Choose the way by hand."
    platform, server = facts.get("platform"), facts.get("server") or "unknown"
    label = PLATFORMS.get(platform or "", "")
    if platform in BUILDERS:
        return "script", (f"{site} is built on {label}, a hosted builder: Skald cannot read its "
                          f"server log, so the script tag is the way.")
    if platform == "cloudflare":
        return "cloudflare", (f"{site} goes through Cloudflare's proxy, so the Skald Worker sees "
                              f"every request, cached pages too.")
    if platform in ("vercel", "netlify"):
        return "vercel", f"{site} runs on {label}, so its log drain sends each request to Skald."
    if platform == "github_pages":
        return "script", (f"{site} is served by GitHub Pages, which keeps no log you can read, "
                          f"so the script tag is the way.")
    if platform in ("cloudfront", "fastly"):
        if server in OWN_SERVERS:
            return "docker", (f"{site} is served through {label} from its own "
                              f"{SERVERS[server]} server, so one command on that server sends "
                              f"its log (pages {label} answers from its cache are not in it).")
        return None, (f"{site} is served through {label}, and the server behind it could not be "
                      f"seen. Choose by hand: the one command on that server if it is yours, else "
                      f"the script tag.")
    if server in OWN_SERVERS:
        on = f" ({facts['os']})" if facts.get("os") else ""
        return "docker", (f"{site} runs on its own {SERVERS[server]} server{on}, so one "
                          f"command on that server sends its log.")
    if server == "iis":
        return "script", (f"{site} runs on Microsoft IIS (Windows). The one-command install is for "
                          f"Linux servers, so the script tag is the way.")
    return None, f"Skald could not tell how {site} is hosted. Choose the way by hand."


# ---------------------------------------------------------------- one name

def _look(host: str, deadline: float) -> dict:
    """One name: HEAD over https (http when https cannot connect), redirects
    followed by hand, then GET when the headers alone do not say enough."""
    out = {"host": host, "reachable": False, "status": None, "final_url": None,
           "error": None, "answer": None, "html": "", "page": None, "addresses": set()}
    answer = None
    for scheme in ("https", "http"):
        try:
            answer, chain = site_fetch.follow(f"{scheme}://{host}/", "HEAD", deadline)
            break
        except site_fetch.Refused as why:
            out["error"] = str(why)
            return out
        except site_fetch.Unreachable as why:
            out["error"] = str(why)
    if answer is None:
        return out
    out["addresses"].add(answer.peer)
    headers = answer.headers
    needs_page = answer.status in (400, 403, 405, 406, 501) or (
        200 <= answer.status < 300 and framework_of(headers) is None
        and "html" in (_value(headers, "content-type") or "text/html"))
    if needs_page:
        try:
            got, _ = site_fetch.follow(answer.url if 200 <= answer.status < 300
                                       else chain[0], "GET", deadline)
            answer = got
            out["addresses"].add(got.peer)
            out["html"], out["page"] = read_page(got.body)
        except (site_fetch.Refused, site_fetch.Unreachable):
            pass                            # the HEAD answer stands
    out.update(reachable=True, status=answer.status, final_url=answer.url, answer=answer,
               error=None)
    return out


def _final_host(look: dict) -> str | None:
    try:
        return (urlsplit(look["final_url"]).hostname or "").lower() or None
    except (ValueError, TypeError):
        return None


def _alike(a: dict, b: dict) -> bool:
    """Two names answer the same site: both 2xx, the same server, platform
    and framework, and a shared address or the same page title."""
    if not (a["reachable"] and b["reachable"]):
        return False
    if not (200 <= (a["status"] or 0) < 300 and 200 <= (b["status"] or 0) < 300):
        return False
    sig = [(server_of(x["answer"].headers)[1], platform_of(x["answer"].headers, x["html"],
                                                           x["page"]),
            framework_of(x["answer"].headers, x["html"], x["page"])) for x in (a, b)]
    if sig[0] != sig[1]:
        return False
    titles = [x["page"].title if x["page"] else "" for x in (a, b)]
    return bool(a["addresses"] & b["addresses"]) or (titles[0] and titles[0] == titles[1])


def _note(host: str, outcome: str) -> None:
    sys.stderr.write(f"site check: {host}: {outcome}\n")       # the host and outcome only


def detect(address: str) -> dict:
    """The facts and the suggestion for `address` (see the module's words)."""
    site = clean_address(address)
    deadline = time.monotonic() + DEADLINE
    first, other = (_look(h, deadline) for h in pair(site))
    main = first if first["reachable"] else other
    f_end = _final_host(first) if first["reachable"] else None
    o_end = _final_host(other) if other["reachable"] else None
    redirects = [{"from": x["host"], "to": end} for x, end in ((first, f_end), (other, o_end))
                 if end and end != x["host"]]
    hosts = [site] + ([f_end] if f_end else [])
    if other["reachable"] and (not first["reachable"] or o_end in (site, f_end)
                               or f_end == other["host"] or _alike(first, other)):
        hosts += [other["host"], o_end]
    from .settings_store import Invalid, validate
    try:
        hosts = validate("sites.hosts", [h for h in hosts if h][:4])
    except Invalid:
        hosts = [site]
    facts: dict = {"site": site, "reachable": bool(main["reachable"]),
                   "final_url": main["final_url"], "https": False, "hosts": hosts,
                   "redirects": redirects, "server": "unknown", "server_detail": "", "os": "",
                   "platform": None, "framework": None, "asset_prefixes": None,
                   "assets_note": "", "error": main["error"]}
    if main["reachable"]:
        headers = main["answer"].headers
        kind, raw, os_name = server_of(headers)
        facts.update(https=str(main["final_url"] or "").startswith("https://"), server=kind,
                     server_detail=raw, os=os_name,
                     platform=platform_of(headers, main["html"], main["page"]),
                     framework=framework_of(headers, main["html"], main["page"]), error=None)
    facts["recommended_method"], facts["reason"] = recommend(site, facts)
    facts["log_note"] = log_note(facts)
    if facts["reachable"] and facts["recommended_method"] not in ("script",) \
            and facts["platform"] not in BUILDERS:
        facts["asset_prefixes"], facts["assets_note"] = assets_of(
            facts["framework"], main["page"], set(hosts))
    facts["tags"] = tags_of(main["html"]) if main["reachable"] else {}
    facts["forms"] = forms_of(main["html"]) if main["reachable"] else None
    facts["checked"] = [{"host": x["host"], "reachable": x["reachable"], "status": x["status"],
                         "final_url": x["final_url"], "error": x["error"]}
                        for x in (first, other)]
    facts["checked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    facts.update(labels(facts))
    _note(site, (f"{facts['server']}, {facts['platform'] or 'no platform'}, "
                 f"{facts['framework'] or 'framework unknown'} -> "
                 f"{facts['recommended_method'] or 'by hand'}") if facts["reachable"]
          else "not reachable")
    return facts


def log_note(facts: dict) -> str:
    """LOG_NOTE for a Next.js site whose own server's log the shipper reads, else ""."""
    if (facts.get("framework") == "nextjs" and facts.get("server") in LOG_FORMAT_SERVERS
            and facts.get("recommended_method") == "docker"):
        return LOG_NOTE
    return ""


def labels(facts: dict) -> dict:
    """The words for the ids, so the page shows what the server means."""
    return {"server_label": SERVERS.get(facts.get("server") or "unknown", "unknown"),
            "platform_label": PLATFORMS.get(facts.get("platform") or "") or None,
            "framework_label": FRAMEWORKS.get(facts.get("framework") or "") or None,
            "hosted_builder": facts.get("platform") in BUILDERS}


# ----------------------------------------------- kept in the wizard's progress

def clean_found(raw) -> dict | None:
    """What the wizard keeps of a check (accounts/site_setup.py `found`):
    only these keys, each checked, so the page cannot store anything else."""
    if not isinstance(raw, dict):
        return None
    from .settings_store import Invalid, validate

    def hosts_of(items):
        try:
            return validate("sites.hosts", [str(x) for x in items][:4]) if items else []
        except Invalid:
            return []
    out = {"reachable": raw.get("reachable") is True, "https": raw.get("https") is True,
           "use": raw.get("use") is not False,
           "site": _short(raw.get("site"), 100),
           "final_url": _short(raw.get("final_url"), 300)
           if str(raw.get("final_url") or "").startswith(("https://", "http://")) else None,
           "hosts": hosts_of(raw.get("hosts") if isinstance(raw.get("hosts"), list) else []),
           "redirects": [], "server": raw.get("server") if raw.get("server") in SERVERS
           else "unknown", "server_detail": _short(raw.get("server_detail"), 80),
           "os": _short(raw.get("os"), 30),
           "platform": raw.get("platform") if raw.get("platform") in PLATFORMS else None,
           "framework": raw.get("framework") if raw.get("framework") in FRAMEWORKS else None,
           "asset_prefixes": _valid_prefixes(raw.get("asset_prefixes"))
           if isinstance(raw.get("asset_prefixes"), list) else None,
           "assets_note": _short(raw.get("assets_note"), 200),
           "recommended_method": raw.get("recommended_method")
           if raw.get("recommended_method") in METHODS else None,
           "reason": _short(raw.get("reason"), 300), "error": _short(raw.get("error"), 200),
           "log_note": LOG_NOTE if raw.get("log_note") == LOG_NOTE else "",
           "tags": {k: [str(v) for v in raw["tags"][k] if TAG_SHAPES[k].fullmatch(str(v))][:3]
                    for k in TAG_SHAPES if isinstance(raw.get("tags"), dict)
                    and isinstance(raw["tags"].get(k), list)},
           "forms": raw["forms"] if isinstance(raw.get("forms"), int) and not isinstance(
               raw.get("forms"), bool) and 0 <= raw["forms"] <= FORMS_MOST else None,
           "checked_at": _short(raw.get("checked_at"), 25)}
    for r in (raw.get("redirects") or [])[:4] if isinstance(raw.get("redirects"), list) else []:
        if isinstance(r, dict):
            pair_ = hosts_of([r.get("from"), r.get("to")])
            if len(pair_) == 2:
                out["redirects"].append({"from": pair_[0], "to": pair_[1]})
    out.update(labels(out))
    return out
