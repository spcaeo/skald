"""What one fetched page says about what runs a site (the public check, stack_public.py).

`detect(page)` reads the page's headers, its cookie NAMES (never their values) and its HTML,
and returns what it can prove, each with its evidence, as received:

  product   a key (wordpress, drupal, shopify, nextjs, nginx, cloudflare, ...)
  name      how people write it (WordPress, Next.js)
  version   only what the server sent (a header, the generator tag, WordPress's own core
            files' ?ver=); never guessed from a theme, a year or a file name
  family    cms, framework, hosted, js, hosting, server, cdn
  runtime   "php" or "nodejs" when the product runs on it on this host, else None
  patched   the hosting company that runs and patches that runtime for you, else None
  saw       [{text, url, command}]: "We saw ..." lines, each with a curl command that shows
            the same thing, counting the same way

`runtimes(found)` adds PHP and Node.js themselves: their own header version when the server
shows one, else "version not shown" with the product that runs on them as the evidence.

Every pattern here looks only at what an ordinary visit returns. Nothing is fetched here.
"""
from __future__ import annotations

import re
import shlex
from collections import Counter
from dataclasses import dataclass, field

# A path's characters, the same in Python and in the grep -E of the commands below.
PATH_CHARS = "[-A-Za-z0-9._~%/+,;=:@&?#!$*]*"
NAMES = {
    "wordpress": "WordPress", "woocommerce": "WooCommerce", "drupal": "Drupal", "joomla": "Joomla",
    "magento": "Magento", "laravel": "Laravel", "symfony": "Symfony", "codeigniter": "CodeIgniter",
    "prestashop": "PrestaShop", "opencart": "OpenCart", "craft": "Craft CMS", "typo3": "TYPO3",
    "statamic": "Statamic", "hugo": "Hugo",
    "php": "PHP", "nodejs": "Node.js", "shopify": "Shopify", "wix": "Wix", "squarespace": "Squarespace",
    "webflow": "Webflow", "hubspot": "HubSpot CMS", "ghost": "Ghost", "wordpresscom": "WordPress.com",
    "wpvip": "WordPress VIP",
    "nextjs": "Next.js", "nuxt": "Nuxt", "gatsby": "Gatsby", "remix": "Remix", "sveltekit": "SvelteKit",
    "astro": "Astro", "angular": "Angular Universal", "express": "Express", "vercel": "Vercel",
    "netlify": "Netlify", "nginx": "nginx", "apache": "Apache", "litespeed": "LiteSpeed",
    "openresty": "OpenResty", "iis": "Microsoft IIS", "caddy": "Caddy", "cloudflare": "Cloudflare",
    "fastly": "Fastly", "akamai": "Akamai", "cloudfront": "CloudFront", "sucuri": "Sucuri"}
PHP_APPS = ("wordpress", "drupal", "joomla", "magento", "laravel", "symfony", "codeigniter",
            "prestashop", "opencart", "craft", "typo3", "woocommerce", "statamic")
NODE_APPS = ("nextjs", "nuxt", "remix", "sveltekit", "angular", "express", "ghost")
HOSTED = ("shopify", "wix", "squarespace", "webflow", "hubspot", "wordpresscom", "wpvip")
FIREWALLS = ("cloudflare", "sucuri", "akamai", "fastly", "cloudfront")
VER = r"(\d+(?:\.\d+){0,2})"
# A WordPress file on any host; `keep` then picks one host's (a page's own, or an origin's).
WP_ANY = f"((https?:)?//[a-z0-9.-]+)?/wp-(content|includes)/{PATH_CHARS}"


@dataclass
class Page:
    url: str
    host: str
    status: int
    headers: dict = field(default_factory=dict)       # lower-case name -> [values]
    html: str = ""

    def header(self, name: str) -> str:
        return ", ".join(self.headers.get(name.lower()) or [])

    def cookies(self) -> list[str]:
        """The cookie names the answer set (never their values)."""
        out = []
        for line in self.headers.get("set-cookie") or []:
            name = line.split("=", 1)[0].strip()
            if name and name not in out:
                out.append(name)
        return out


def _q(text: str) -> str:
    return shlex.quote(text)


def see_header(pg: Page, name: str, contains: str | None = None) -> list[dict]:
    """The header line as received (the first value that contains `contains`)."""
    pretty = "-".join(w.capitalize() for w in name.split("-")).replace("Powered-By", "Powered-By")
    pretty = {"x-powered-by": "X-Powered-By", "x-nf-request-id": "X-Nf-Request-Id"}.get(name, pretty)
    for value in pg.headers.get(name) or []:
        if contains is None or contains.lower() in value.lower():
            return [{"text": f"We saw the header {pretty}: {value.strip()[:200]}", "url": pg.url,
                     "command": f"curl -sI {_q(pg.url)} | grep -i '^{name}:'"}]
    return []


def see_cookie(pg: Page, name: str) -> list[dict]:
    return [{"text": f"We saw the site set a cookie named {name} (its value is not shown)",
             "url": pg.url, "command": f"curl -sI {_q(pg.url)} | grep -i -o '^set-cookie: {name}='"}]


def see_generator(pg: Page, word: str) -> list[dict]:
    """The generator tag that names `word` (a page can carry several: a plugin's too)."""
    for tag in re.findall(r"<meta\b[^>]*\bname\s*=\s*[\"']?generator[\"']?[^>]*>", pg.html, re.I):
        if word.lower() in tag.lower():
            return [{"text": f"We saw the tag {tag[:200]}", "url": pg.url,
                     "command": f"curl -s {_q(pg.url)} | grep -i -o '<meta[^>]*generator[^>]*>'"}]
    return []


def generator(pg: Page) -> str:
    tags = re.findall(r"<meta\b[^>]*\bname\s*=\s*[\"']?generator[\"']?[^>]*>", pg.html, re.I)
    out = []
    for tag in tags:
        got = re.search(r"\bcontent\s*=\s*[\"']([^\"']*)", tag, re.I)
        if got:
            out.append(got.group(1))
    return " | ".join(out)[:200]


def files(pg: Page, pattern: str, what: str, keep: str | None = None
          ) -> tuple[int, str | None, list[dict]]:
    """(how many different matches, the first, its evidence) of an ERE that grep and Python
    both read the same way (no \\s, no \\d: [0-9], literal dots escaped). `keep`, a second
    ERE, keeps only the matches it starts (a host's own files), in both."""
    found = [m.group(0) for m in re.finditer(pattern, pg.html, re.I)]
    if keep:
        found = [m for m in found if re.match(keep, m, re.I)]
    found = list(dict.fromkeys(m.lower() for m in found))
    if not found:
        return 0, None, []
    n = len(found)
    text = (f"We saw links to {n:,} different {what.format(s='' if n == 1 else 's')}, for example "
            f"{found[0][:160]}")
    then = f" | grep -i -E {_q(keep)}" if keep else ""
    return n, found[0], [{"text": text, "url": pg.url,
                          "command": f"curl -s {_q(pg.url)} | grep -o -i -E {_q(pattern)}{then} "
                                     f"| tr 'A-Z' 'a-z' | sort -u | wc -l"}]


def contains(pg: Page, needle: str, words: str) -> list[dict]:
    if needle.lower() not in pg.html.lower():
        return []
    return [{"text": f"We saw {words} in the page", "url": pg.url,
             "command": f"curl -s {_q(pg.url)} | grep -c -i {_q(needle)}"}]


def _add(out: list, product: str, family: str, saw: list, version=None, runtime=None,
         patched=None) -> None:
    if not saw:
        return
    for f in out:
        if f["product"] == product:
            f["saw"] += [s for s in saw if s not in f["saw"]]
            f["version"] = f["version"] or version
            return
    out.append({"product": product, "name": NAMES[product], "version": version, "family": family,
                "runtime": runtime, "patched": patched, "saw": saw})


# ------------------------------------------------------------------ the families

def _wordpress(pg: Page, out: list) -> None:
    gen = generator(pg)
    host = re.escape(pg.host)
    saw, version = [], None
    got = re.search(r"WordPress\s+" + VER, gen, re.I)
    if re.search(r"\bWordPress\b", gen, re.I) and not re.search(r"WordPress\.com", gen, re.I):
        saw += see_generator(pg, "WordPress")
        version = got.group(1) if got else None
    saw += see_header(pg, "link", "api.w.org")
    n, _first, more = files(pg, WP_ANY, f"file{{s}} under /wp-content/ or /wp-includes/ on {pg.host}",
                            keep=f"^((https?:)?//{host})?/")
    saw += more
    if not version:
        # WordPress's own core files carry its version as ?ver= (never a plugin's or a theme's).
        vers = Counter(re.findall(r"/wp-includes/(?:js|css)/[-A-Za-z0-9._/]*\?ver=([0-9]+\.[0-9]+(?:\.[0-9]+)?)\b",
                                  pg.html, re.I))
        if vers:
            version, count = vers.most_common(1)[0]
            saw.append({"text": f"We saw WordPress's own core files carry ?ver={version} "
                                f"({count} of them)", "url": pg.url,
                        "command": f"curl -s {_q(pg.url)} | grep -o -E '/wp-includes/(js|css)/"
                                   f"[-A-Za-z0-9._/]*[?]ver=[0-9.]*' | sort | uniq -c"})
    _add(out, "wordpress", "cms", saw, version, "php")
    wp = next((f for f in out if f["product"] == "wordpress"), None)
    if wp:
        n, _first, multi = files(pg, f"/wp-content/uploads/sites/[0-9]+/{PATH_CHARS}",
                                 "file{s} under /wp-content/uploads/sites/ (a multisite's)")
        if n:
            wp["multisite"] = True
            _add(out, "wordpress", "cms", multi)
        got = re.search(r"WooCommerce\s+" + VER, generator(pg), re.I)
        _add(out, "woocommerce", "cms", see_generator(pg, "WooCommerce")
             + files(pg, f"/wp-content/plugins/woocommerce/{PATH_CHARS}", "WooCommerce file{s}")[2],
             got.group(1) if got else None, "php")


def _php_apps(pg: Page, out: list) -> None:
    gen = generator(pg)
    cookies = pg.cookies()
    # Drupal
    saw = see_generator(pg, "Drupal") if re.search(r"\bDrupal\b", gen, re.I) else []
    saw += see_header(pg, "x-generator", "drupal") + see_header(pg, "x-drupal-cache")
    saw += see_header(pg, "x-drupal-dynamic-cache")
    saw += files(pg, f"/sites/default/files/{PATH_CHARS}", "file{s} under /sites/default/files/")[2]
    got = re.search(r"Drupal\s+" + VER, gen + " " + pg.header("x-generator"), re.I)
    _add(out, "drupal", "cms", saw, got.group(1) if got else None, "php")
    # Joomla
    saw = see_generator(pg, "Joomla") if re.search(r"\bJoomla\b", gen, re.I) else []
    saw += files(pg, f"/media/(jui|system)/{PATH_CHARS}", "file{s} under Joomla's /media/jui/ or /media/system/")[2] \
        if saw else []
    saw += contains(pg, "/administrator/", "a link to /administrator/") if saw else []
    _add(out, "joomla", "cms", saw, None, "php")
    # Magento / Adobe Commerce
    saw = [h for name in ("x-magento-cache-debug", "x-magento-tags", "x-magento-vary")
           for h in see_header(pg, name)]
    saw += contains(pg, "Mage.Cookies", "Magento's Mage.Cookies script")
    saw += files(pg, f"/static/version[0-9]+/{PATH_CHARS}", "file{s} under Magento's /static/version.../")[2]
    _add(out, "magento", "cms", saw, None, "php")
    # PHP frameworks and shops, by their own cookies
    session = [c for c in cookies if c.lower().endswith("_session")]
    if "XSRF-TOKEN" in cookies and session:
        # Laravel's own pair: XSRF-TOKEN and <app name>_session (laravel_session by default).
        _add(out, "laravel", "framework", see_cookie(pg, "XSRF-TOKEN") + see_cookie(pg, session[0]),
             None, "php")
    _add(out, "statamic", "cms", see_header(pg, "x-powered-by", "statamic"), None, "php")
    for product, cookie in (("laravel", "laravel_session"), ("symfony", "sf_redirect"),
                            ("codeigniter", "ci_session"), ("craft", "CraftSessionId"),
                            ("opencart", "OCSESSID")):
        hit = [c for c in cookies if c.lower() == cookie.lower()]
        family = "cms" if product in ("craft", "opencart") else "framework"
        _add(out, product, family, see_cookie(pg, hit[0]) if hit else [], None, "php")
    if any(c.lower().startswith("prestashop-") for c in cookies) or re.search(r"\bPrestaShop\b", gen, re.I):
        saw = see_generator(pg, "PrestaShop") if re.search(r"\bPrestaShop\b", gen, re.I) else []
        saw += [s for c in cookies if c.lower().startswith("prestashop-") for s in see_cookie(pg, c)][:1]
        _add(out, "prestashop", "cms", saw, None, "php")
    _add(out, "craft", "cms", see_header(pg, "x-powered-by", "craft cms"), None, "php")
    saw = see_generator(pg, "TYPO3") if re.search(r"\bTYPO3\b", gen, re.I) else []
    saw += files(pg, f"/typo3(conf|temp)/{PATH_CHARS}", "file{s} under /typo3conf/ or /typo3temp/")[2]
    got = re.search(r"TYPO3\s+CMS\s*" + VER + "?", gen, re.I)
    _add(out, "typo3", "cms", saw, None, "php")
    if any(f["product"] == "opencart" for f in out):
        _add(out, "opencart", "cms", files(pg, f"/catalog/view/theme/{PATH_CHARS}", "OpenCart theme file{s}")[2])


def _hosted(pg: Page, out: list) -> None:
    gen = generator(pg)
    saw = see_header(pg, "x-shopid") + see_header(pg, "x-shopify-stage") + \
        see_header(pg, "powered-by", "shopify")
    saw += [s for c in pg.cookies() if c.lower().startswith("_shopify_") for s in see_cookie(pg, c)][:1] \
        if saw else []
    saw += files(pg, f"//cdn\\.shopify\\.com/{PATH_CHARS}", "file{s} on cdn.shopify.com")[2] if saw else []
    _add(out, "shopify", "hosted", saw, patched="Shopify")
    saw = see_header(pg, "x-wix-request-id") + see_header(pg, "server", "pepyaka")
    saw += files(pg, f"//static\\.wixstatic\\.com/{PATH_CHARS}", "file{s} on static.wixstatic.com")[2] if saw else []
    _add(out, "wix", "hosted", saw, patched="Wix")
    saw = see_header(pg, "server", "squarespace")
    saw += files(pg, f"//static1\\.squarespace\\.com/{PATH_CHARS}", "file{s} on static1.squarespace.com")[2] if saw else []
    _add(out, "squarespace", "hosted", saw, patched="Squarespace")
    saw = contains(pg, "data-wf-site", "Webflow's data-wf-site attribute") if "data-wf-site" in pg.html else []
    saw += files(pg, f"//[a-z0-9.-]*website-files\\.com/{PATH_CHARS}", "file{s} on Webflow's website-files.com")[2] \
        if saw else []
    _add(out, "webflow", "hosted", saw, patched="Webflow")
    saw = see_header(pg, "x-hs-hub-id") + see_header(pg, "x-powered-by", "hubspot")
    _add(out, "hubspot", "hosted", saw, patched="HubSpot")
    saw = see_header(pg, "x-hacker") + see_header(pg, "host-header", "wordpress.com")
    saw += see_generator(pg, "WordPress.com") if re.search(r"WordPress\.com", gen, re.I) else []
    vip = see_header(pg, "x-powered-by", "wordpress vip")
    _add(out, "wpvip", "hosted", vip, patched="WordPress VIP")
    if not vip:
        _add(out, "wordpresscom", "hosted", saw, patched="WordPress.com")
    if re.search(r"\bGhost\b", gen, re.I):
        got = re.search(r"Ghost\s+" + VER, gen, re.I)
        pro = see_header(pg, "x-ghost-cache-status")
        _add(out, "ghost", "cms", see_generator(pg, "Ghost") + pro, got.group(1) if got else None, "nodejs")


def _js(pg: Page, out: list) -> None:
    gen = generator(pg)
    saw = see_header(pg, "x-powered-by", "next.js")
    saw += files(pg, f"(https?://[a-z0-9.-]+)?/_next/{PATH_CHARS}", "Next.js file{s} (/_next/)")[2]
    saw += contains(pg, "__NEXT_DATA__", "Next.js's __NEXT_DATA__ script")
    _add(out, "nextjs", "js", saw, None, "nodejs")
    saw = see_header(pg, "x-powered-by", "nuxt")
    saw += files(pg, f"(https?://[a-z0-9.-]+)?/_nuxt/{PATH_CHARS}", "Nuxt file{s} (/_nuxt/)")[2]
    saw += contains(pg, "__NUXT__", "Nuxt's __NUXT__ data")
    _add(out, "nuxt", "js", saw, None, "nodejs")
    got = re.search(r"Gatsby\s+" + VER, gen, re.I)
    saw = (see_generator(pg, "Gatsby") if got else []) + contains(pg, "___gatsby", "Gatsby's ___gatsby root")
    _add(out, "gatsby", "js", saw, got.group(1) if got else None)
    _add(out, "remix", "js", contains(pg, "__remixContext", "Remix's __remixContext script"), None, "nodejs")
    _add(out, "sveltekit", "js", files(pg, f"/_app/immutable/{PATH_CHARS}", "SvelteKit file{s} (/_app/immutable/)")[2],
         None, "nodejs")
    got = re.search(r"Hugo\s+" + VER, gen, re.I)
    _add(out, "hugo", "js", see_generator(pg, "Hugo") if got else [], got.group(1) if got else None)
    got = re.search(r"Astro\s+v?" + VER, gen, re.I)
    saw = (see_generator(pg, "Astro") if got else []) + files(pg, f"/_astro/{PATH_CHARS}", "Astro file{s} (/_astro/)")[2]
    _add(out, "astro", "js", saw, got.group(1) if got else None)
    if "ng-server-context" in pg.html:
        _add(out, "angular", "js", contains(pg, "ng-server-context", "Angular's ng-server-context "
                                            "(rendered on a server)"), None, "nodejs")
    _add(out, "express", "js", see_header(pg, "x-powered-by", "express"), None, "nodejs")


def _hosting(pg: Page, out: list) -> None:
    _add(out, "vercel", "hosting", see_header(pg, "x-vercel-id") + see_header(pg, "server", "vercel"),
         patched="Vercel")
    _add(out, "netlify", "hosting", see_header(pg, "x-nf-request-id") + see_header(pg, "server", "netlify"),
         patched="Netlify")


def _servers(pg: Page, out: list) -> None:
    server = pg.header("server")
    for product, word in (("nginx", "nginx"), ("apache", "apache"), ("litespeed", "litespeed"),
                          ("openresty", "openresty"), ("iis", "microsoft-iis"), ("caddy", "caddy")):
        got = re.match(r"^\s*" + re.escape(word) + r"(?:/" + VER + ")?", server, re.I)
        if got:
            _add(out, product, "server", see_header(pg, "server", word), got.group(1))
    if pg.headers.get("x-litespeed-cache"):
        _add(out, "litespeed", "server", see_header(pg, "x-litespeed-cache"))
    _add(out, "cloudflare", "cdn", see_header(pg, "server", "cloudflare") + see_header(pg, "cf-ray"))
    _add(out, "fastly", "cdn", see_header(pg, "x-fastly-request-id") + see_header(pg, "x-served-by", "cache-"))
    _add(out, "akamai", "cdn", see_header(pg, "server", "akamaighost") + see_header(pg, "akamai-grn"))
    _add(out, "cloudfront", "cdn", see_header(pg, "x-amz-cf-id") + see_header(pg, "via", "cloudfront"))
    _add(out, "sucuri", "cdn", see_header(pg, "x-sucuri-id") + see_header(pg, "server", "sucuri"))


def _plain_php(pg: Page, out: list) -> None:
    saw = see_header(pg, "x-powered-by", "php/")
    got = re.search(r"\bPHP/" + VER, pg.header("x-powered-by"), re.I)
    session = [c for c in pg.cookies() if c.upper() == "PHPSESSID"]
    saw += see_cookie(pg, session[0]) if session else []
    if saw:
        _add(out, "php", "runtime", saw, got.group(1) if got else None, "php")


def detect(pg: Page) -> list[dict]:
    """Everything this page proves, each with its evidence (see the module's docstring)."""
    out: list[dict] = []
    for family in (_hosted, _wordpress, _php_apps, _js, _hosting, _servers, _plain_php):
        family(pg, out)
    host = next((f["patched"] for f in out if f["product"] in ("wordpresscom", "wpvip")), None)
    if host:                                     # WordPress hosted by WordPress.com or VIP
        for f in out:
            if f["product"] in ("wordpress", "woocommerce"):
                f["patched"] = host
    for f in out:
        f["host"] = pg.host
    return out


def how_of(saw: list[dict]) -> str:
    """How a product was read, in a few words, from its first evidence line."""
    text = saw[0]["text"] if saw else ""
    if text.startswith("We saw the tag"):
        return "generator tag"
    got = re.match(r"We saw the header ([A-Za-z-]+):", text)
    if got:
        return f"{got.group(1)} header"
    if text.startswith("We saw the site set a cookie"):
        return "its cookie"
    if "load" in text or text.startswith("We saw links to"):
        return "its files"
    return "its page"


def runtimes(found: list[dict]) -> list[dict]:
    """PHP and Node.js on each host: the server's own version when it shows one, else "version
    not shown", with what runs on them as the evidence; and who patches them when a hosted
    platform or a host like Vercel runs them."""
    out = [f for f in found if f["product"] not in ("php", "nodejs")]
    hosts = list(dict.fromkeys(f["host"] for f in found))
    for host in hosts:
        here = [f for f in found if f["host"] == host]
        patched = next((f["patched"] for f in here if f["family"] in ("hosted", "hosting") and f["patched"]),
                       None)
        for runtime in ("php", "nodejs"):
            own = next((f for f in here if f["product"] == runtime), None)
            apps = [f for f in here if f.get("runtime") == runtime and f["product"] != runtime]
            if not own and not apps:
                continue
            # A hosted platform (Shopify, Wix ...) runs PHP or Node.js for you; Vercel and
            # Netlify run Node.js, not PHP.
            who = patched if (patched and (runtime == "nodejs" or patched not in ("Vercel", "Netlify"))) \
                else next((a["patched"] for a in apps if a.get("patched")), None)
            saw = list(own["saw"]) if own else []
            if not (own and own.get("version")):
                app = apps[0] if apps else None
                if app:
                    ver = f" {app['version']}" if app.get("version") else ""
                    saw.insert(0, {"text": f"We saw {host} runs {app['name']}{ver} ({how_of(app['saw'])}), "
                                           f"and {app['name']} runs on {NAMES[runtime]}",
                                   "url": app["saw"][0]["url"],
                                   "command": app["saw"][0]["command"]})
                    saw += [s for s in app["saw"] if s not in saw]
            out.append({"product": runtime, "name": NAMES[runtime], "family": "runtime",
                        "version": own.get("version") if own else None, "runtime": runtime,
                        "patched": who, "host": host, "saw": saw,
                        "under": [a["name"] + (f" {a['version']}" if a.get("version") else "")
                                  for a in apps]})
    return out
