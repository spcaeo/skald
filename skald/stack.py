"""What serves each site, read from outside once a day (Security > Your stack, 2.21).

The daily run fetches the site's home page through the safe fetcher (site_fetch.py: public
addresses only, no cookie, no credentials, a size and time limit) and reads what the server
says about itself, and what the page says about what built it:

  Server        nginx/1.24.0, Apache/2.4.58 (Ubuntu), LiteSpeed: the server and its version
  X-Powered-By  PHP/8.1.2, Next.js, Express: PHP and its version, a framework
  the page      the generator tag (WordPress 6.4.2), /wp-content/ or /wp-includes/ paths
                (WordPress), /_next/ (Next.js, and so Node.js)
  origins       another host the page loads WordPress files from (a headless WordPress at
                wp.<site>): its root is fetched once too
  login page    on every WordPress host, /wp-login.php once (HEAD, no credentials, no
                redirect followed): a 2xx answer is "login page open to the internet"

Hosts read: each of `site.hosts` once (www.x left out when x is listed), at most 3, and at
most 3 origins.

A version the server does not show is None ("not shown by the server"): never guessed.
Nothing here counts the log. The check is kept per day in `stack-<site>.json` beside the
history (STORE: the last KEEP days), not in day_extras: collecting a day again rewrites its
extras, and this is a fetch, not a count. Each check keeps its evidence (the header values
and markers it read), so audit_stack.py can read them again with its own code.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import advisories

KEEP = 90
MAX_ORIGINS = 3
MAX_SITE_HOSTS = 3
STORE = "stack-{site}.json"
COMMANDS = {"php": "php -v", "nodejs": "node -v", "nginx": "nginx -v",
            "apache": "apachectl -v", "litespeed": "/usr/local/lsws/bin/lshttpd -v",
            "wordpress": "wp core version", "nextjs": "npm ls next"}
NAMES = {"php": "PHP", "nodejs": "Node.js", "nginx": "nginx", "apache": "Apache",
         "litespeed": "LiteSpeed", "wordpress": "WordPress", "nextjs": "Next.js"}
WP_PATH = re.compile(r"https?://([a-z0-9][a-z0-9.-]*[a-z0-9])(?::\d+)?/wp-(?:content|includes)/",
                     re.I)


def _one(headers: dict, name: str) -> str:
    return ", ".join(headers.get(name.lower(), []) or [])[:200]


def evidence(answer, html: str, page) -> dict:
    """What one answer says, kept as read (the audit reads it again)."""
    headers = answer.headers if answer is not None else {}
    markers = []
    for word, mark in (("/wp-content/", "wp-content"), ("/wp-includes/", "wp-includes"),
                       ("/_next/", "_next"), ("__NEXT_DATA__", "__NEXT_DATA__")):
        if word in html:
            markers.append(mark)
    if "api.w.org" in _one(headers, "link").lower():
        markers.append("wp-json link")
    return {"status": getattr(answer, "status", None), "server": _one(headers, "server"),
            "powered_by": _one(headers, "x-powered-by"),
            "generator": (page.generator if page is not None else "")[:80],
            "markers": markers}


def products(host: str, ev: dict) -> list[dict]:
    """[{product, version (None: not shown), host, how}] from one host's evidence."""
    out = []
    server = ev.get("server") or ""
    got = re.match(r"^\s*(nginx|openresty|apache|litespeed)(?:/(\d+(?:\.\d+){0,2}))?", server, re.I)
    if got:
        kind = got.group(1).lower()
        kind = "nginx" if kind == "openresty" else kind
        out.append({"product": kind, "version": got.group(2), "host": host, "how": "Server header"})
    powered = ev.get("powered_by") or ""
    php = re.search(r"\bPHP/(\d+(?:\.\d+){0,2})", powered, re.I)
    if php or re.search(r"\bPHP\b", powered, re.I):
        out.append({"product": "php", "version": php.group(1) if php else None, "host": host,
                    "how": "X-Powered-By header"})
    gen = ev.get("generator") or ""
    wp = re.match(r"^\s*WordPress(?:\s+(\d+(?:\.\d+){0,2}))?", gen, re.I)
    markers = set(ev.get("markers") or [])
    if wp or markers & {"wp-content", "wp-includes", "wp-json link"}:
        out.append({"product": "wordpress", "version": wp.group(1) if wp else None, "host": host,
                    "how": "generator tag" if wp else "the page's WordPress paths"})
        if not php:
            out.append({"product": "php", "version": None, "host": host,
                        "how": "WordPress runs on PHP"})
    nx_head = re.search(r"Next\.js(?:\s+(\d+(?:\.\d+){0,2}))?", powered, re.I)
    nx_gen = re.match(r"^\s*Next\.js(?:\s+(\d+(?:\.\d+){0,2}))?", gen, re.I)
    if nx_head or nx_gen or markers & {"_next", "__NEXT_DATA__"}:
        got = nx_head or nx_gen
        out.append({"product": "nextjs", "version": got.group(1) if got else None, "host": host,
                    "how": "X-Powered-By header" if nx_head else "generator tag" if nx_gen
                    else "the page's Next.js paths"})
        out.append({"product": "nodejs", "version": None, "host": host,
                    "how": "Next.js runs on Node.js"})
    seen, unique = set(), []
    for p in out:
        key = (p["product"], p["host"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def origins(html: str, own: str) -> list[str]:
    """Other hosts the page loads WordPress files from (a headless WordPress)."""
    found = []
    for host in WP_PATH.findall(html or ""):
        host = host.lower()
        if host != own and host not in found:
            found.append(host)
    return found[:MAX_ORIGINS]


def _get(fetch, url: str, method: str = "GET"):
    from . import site_fetch
    try:
        return fetch(url, method), None
    except (site_fetch.Refused, site_fetch.Unreachable) as why:
        return None, str(why)


def reserved(host: str) -> bool:
    """A name reserved for documentation and tests (RFC 2606, RFC 6761): never fetched."""
    labels = host.lower().rstrip(".").split(".")
    if labels[-1] in ("test", "invalid", "localhost", "example", "local"):
        return True
    return len(labels) >= 2 and labels[-2] == "example" and labels[-1] in ("com", "net", "org")


def site_hosts(hosts) -> list[str]:
    """The site's hosts worth reading: each name once (www.x left out when x is listed
    too), at most MAX_SITE_HOSTS."""
    names = [str(h).lower() for h in hosts or [] if str(h).strip()]
    out = []
    for h in names:
        if h.startswith("www.") and h[4:] in names:
            continue
        if h not in out:
            out.append(h)
    return out[:MAX_SITE_HOSTS]


def check(hosts, fetch=None, now: datetime | None = None) -> dict:
    """The site's stack: each of its hosts' home page, then each WordPress origin a page
    loads from (and that origin's /wp-login.php)."""
    from . import site_detect, site_fetch
    # The login page is asked once, its redirect never followed: a redirect is not "open".
    fetch = fetch or (lambda url, method: site_fetch.fetch(url, method) if method == "HEAD"
                      else site_fetch.follow(url, method)[0])
    now = now or datetime.now(timezone.utc)
    found, html_all, names = [], [], site_hosts([hosts] if isinstance(hosts, str) else hosts)
    for host in names:
        answer, error = _get(fetch, f"https://{host}/")
        html, page = site_detect.read_page(answer.body) if answer is not None else ("", None)
        html_all.append(html)
        ev = evidence(answer, html, page) if answer is not None else None
        row = {"host": host, "role": "site", "error": error, "evidence": ev}
        if ev and any(p["product"] == "wordpress" for p in products(host, ev)):
            login, l_why = _get(fetch, f"https://{host}/wp-login.php", "HEAD")
            row.update(login=None if login is None else login.status, login_error=l_why)
        found.append(row)
    hosts = found
    seen = set(names)
    wanted = []
    for html in html_all:
        for origin in origins(html, ""):
            if origin not in seen:
                seen.add(origin)
                wanted.append(origin)
    for origin in wanted[:MAX_ORIGINS]:
        got, why = _get(fetch, f"https://{origin}/")
        o_html, o_page = site_detect.read_page(got.body) if got is not None else ("", None)
        o_ev = evidence(got, o_html, o_page) if got is not None else None
        login, l_why = _get(fetch, f"https://{origin}/wp-login.php", "HEAD")
        hosts.append({"host": origin, "role": "content origin", "error": why, "evidence": o_ev,
                      "login": None if login is None else login.status, "login_error": l_why})
    return {"checked_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "hosts": hosts}


def read(blob: dict, doc: dict | None = None) -> dict:
    """The check's products, login lines and advisory matches (derived, never stored alone)."""
    found = []
    for h in blob.get("hosts") or []:
        if h.get("evidence"):
            found += products(h["host"], h["evidence"])
    logins = [{"host": h["host"], "status": h.get("login"),
               "open": h.get("login") is not None and 200 <= int(h["login"]) < 300}
              for h in blob.get("hosts") or [] if "login" in h]
    doc = doc or advisories.load()
    return {"products": found, "logins": logins, "matches": advisories.match(found, doc)}


def path_for(config: dict, folder, site: str) -> Path:
    return Path(folder) / STORE.format(site=re.sub(r"[^a-z0-9.-]", "_", site.lower()))


def stored(folder, site: str) -> dict:
    try:
        got = json.loads(path_for({}, folder, site).read_text())
    except (OSError, ValueError):
        return {"days": {}}
    return got if isinstance(got, dict) and isinstance(got.get("days"), dict) else {"days": {}}


def daily(ctx, fetch=None) -> int:
    """run-daily's step: check, keep, never stop the run (always 0)."""
    from .files import write_atomic
    sec = (ctx.config or {}).get("security") or {}
    if sec.get("stack_check") is False or str(sec.get("stack_check")).lower() == "false":
        return 0
    hosts = ((ctx.config or {}).get("site") or {}).get("hosts") or []
    if not hosts:
        return 0
    folder = Path(ctx.live_dir)
    try:
        ctx.out(f"advisories: {advisories.refresh(ctx.config, folder)}")
        if fetch is None and all(reserved(str(h)) for h in hosts):
            return 0                    # a test or sample install: nothing to read
        blob = check(hosts, fetch, ctx.now)
        doc = advisories.load(folder)
        blob["advisories"] = doc.get("updated")
        blob["read"] = read(blob, doc)
        kept = stored(folder, ctx.site)
        day = ctx.now.astimezone(ctx.tz).date().isoformat()
        kept["days"][day] = blob
        kept["days"] = dict(sorted(kept["days"].items())[-KEEP:])
        write_atomic(path_for(ctx.config, folder, ctx.site), json.dumps(kept, indent=1) + "\n")
        found = blob["read"]["matches"]
        ctx.out(f"stack: {len(blob['read']['products'])} products, "
                f"{sum(1 for m in found if m['state'] in ('update_needed', 'no_fix'))} advisories to act on")
    except Exception as why:            # noqa: BLE001 - a fetch never stops the run
        ctx.err(f"stack: {type(why).__name__}: {why}")
    return 0


def latest(folder, site: str) -> tuple[str, dict] | None:
    days = stored(folder, site)["days"]
    if not days:
        return None
    day = max(days)
    return day, days[day]


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def add_command(sub) -> None:
    """`stack`: run the daily stack check now (after an install, or a new advisory list),
    then `dashboard` shows it. Same reads as the daily run: the site's public pages only."""
    p = sub.add_parser("stack", help="check now what serves the site and which advisories apply")
    p.set_defaults(run=daily)
