"""The public check's answer (stack_public.py): one card per thing to know, each with its proof.

Every card says what was seen ("saw": the exact header line, tag, cookie name or page
references, each with the URL it was read from and a curl command that shows the same
thing), what that means ("means": only what the facts prove), and for an advisory why it
matched ("because"). The answer also lists every request made ("fetched"), the User-Agent,
what was detected ("products", for the chips) and a one-line summary.

Cards, by group (the order shown):

  act    update   an advisory applies to a version the server showed
         login    /wp-login.php ends in WordPress's login form
  check  hidden   an advisory names PHP or Node.js here, but the version is not shown
         unknown  something could not be checked: said so, nothing claimed
  tips   tip      a server shows its exact version, XML-RPC is on, readme.html shows the
                  version, security headers are missing, the certificate ends soon
         info     a headless WordPress; a firewall in front (with what its maker says
                  about this week's flaw, when the advisory lists it)
  good   hosted   a platform runs and patches PHP or Node.js for you (Shopify, Vercel ...)
         good     the login page is hidden or blocked; every security header is there
         fixed    the version shown has the fix
         nothing  the site was read and nothing in the advisory list applies

"Update needed" only for a version actually read; never "affected" without one.

The same finding on two hosts of one site (a tip "Your server shows its exact version: nginx
1.18.0" on www. and on wp.) is one card (merge): every host listed, each one's evidence kept.
"""
from __future__ import annotations

import shlex
import ssl
from datetime import datetime, timezone

from . import advisories
from .stack_public_detect import FIREWALLS, NAMES, runtimes

GROUPS = {"update": "act", "login": "act", "hidden": "check", "unknown": "check", "tip": "tips",
          "info": "tips", "hosted": "good", "good": "good", "fixed": "good", "nothing": "good"}
ORDER = ("act", "check", "tips", "good")
KINDS = ("update", "login", "hidden", "unknown", "tip", "info", "hosted", "good", "fixed", "nothing")
COMMANDS = {"php": "php -v", "nodejs": "node -v"}
HIDE = {"nginx": "set server_tokens off; in nginx's http block, then reload nginx",
        "apache": "set ServerTokens Prod and ServerSignature Off, then reload Apache",
        "litespeed": "turn off the server signature in LiteSpeed's settings",
        "openresty": "set server_tokens off; in the http block, then reload",
        "iis": "remove the Server header with URL Rewrite or removeServerHeader",
        "caddy": "remove the Server header with header -Server"}
HEADERS = (("strict-transport-security", "Strict-Transport-Security"),
           ("content-security-policy", "Content-Security-Policy"),
           ("x-frame-options", "X-Frame-Options"),
           ("x-content-type-options", "X-Content-Type-Options"),
           ("referrer-policy", "Referrer-Policy"))
CERT_WARN_DAYS = 14


def _q(url: str) -> str:
    return shlex.quote(url)


def _see(text: str, url: str, cmd: str) -> dict:
    return {"text": text, "url": url, "command": cmd}


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _card(kind: str, title: str, saw: list, means: str, advice: str, hosts: list, **more) -> dict:
    return {"kind": kind, "group": GROUPS[kind], "title": title, "saw": saw, "means": means,
            "advice": advice, "hosts": hosts, **more}


def _mine(a: dict, ver: str | None):
    v = advisories.version(ver or "")
    if not v:
        return None
    branch = advisories.branch_of(v, a["branch"])
    return next((f for b, f in a["fixed"].items()
                 if advisories.branch_of(advisories.version(b) or (), a["branch"]) == branch), None)


def advisory_card(rt: dict, a: dict, state: str, servers: list) -> dict:
    name, ver, host = rt["name"], rt.get("version"), rt["host"]
    fixed = [str(v) for v in a["fixed"].values()]
    under = rt.get("under") or []
    because = f"{name} {ver or 'version not shown'} on {host}" + (
        f", which runs {_and(under)}" if under else "")
    facts = list(under)
    affected = ""
    if rt["product"] == "php" and any(s["product"] == "litespeed" for s in servers):
        affected = " LiteSpeed, which serves this site, is one of the ways of running PHP the advisory lists."
        facts.append("LiteSpeed")
    base = {"advisory": a["id"], "product": rt["product"], "version": ver,
            "severity": a.get("severity"), "cves": list(a.get("cves") or []), "fixed": fixed,
            "sources": [s for s in a.get("sources") or [] if str(s).startswith("https://")],
            "because": because, "facts": facts, "also_known_as": a.get("also_known_as")}
    if state == "update_needed":
        return _card("update", f"Update needed: {name} {ver} on {host}", rt["saw"],
                     f"This means {name} {ver} is older than {_mine(a, ver)}, the fixed release of "
                     f"its branch. {a.get('summary', '')}{affected}".strip(),
                     a.get("action", ""), [host], **base)
    if state == "no_fix":
        return _card("update", f"Update needed: {name} {ver} on {host} gets no official fix",
                     rt["saw"], f"This means {a.get('no_fix_words', '')} {a.get('summary', '')}"
                                f"{affected}".strip(), a.get("action", ""), [host], **base)
    if state == "check_version":
        cmd = COMMANDS.get(rt["product"], "")
        return _card("hidden", f"{name} on {host}: version not shown by the server", rt["saw"],
                     f"This means we can't tell whether the fix is in. Keeping the version hidden "
                     f"is good, but the flaw works either way. {a.get('title', '')}: fixed in "
                     f"{_and(fixed)}. {a.get('no_fix_words', '')}{affected}".strip(),
                     f"Check it on the server with {cmd}, and update if it is older.", [host],
                     command=cmd, **base)
    mine = _mine(a, ver)
    return _card("fixed", f"{name} {ver} on {host} has the fix", rt["saw"],
                 f"This means {a.get('title', '')} does not apply: "
                 + (f"fixed in {mine} on this branch." if mine and state == "fixed"
                    else f"this branch is newer than every fixed release listed ({_and(fixed)})."),
                 "Nothing to do for this advisory.", [host], **base)


def hosted_card(f: dict, runtime: str | None = None) -> dict:
    who = f["patched"]
    if f["family"] == "hosted":
        return _card("hosted", f"Hosted by {who}: they patch PHP and Node.js for you", f["saw"],
                     f"This means {who} runs the servers, and PHP or Node.js on them, and keeps them "
                     f"updated: there is nothing for you to update for these advisories.",
                     "Nothing to do on the server side. Keep your apps and accounts on it secure.",
                     [f["host"]], product=f["product"])
    name = NAMES[runtime]
    return _card("hosted", f"{name} on {f['host']} is run for you by {who}", f["saw"],
                 f"This means {who} runs {name} for this site and patches it: there is nothing for "
                 f"you to update for the {name} advisory.", "Nothing to do for this advisory.",
                 [f["host"]], product=runtime)


def firewall_card(f: dict, doc: dict, php_here: bool) -> dict:
    notes = [n for a in doc.get("advisories") or [] for n in a.get("firewall_notes") or []
             if n.get("product") == f["product"] and php_here]
    means = (f"This means a firewall and cache ({f['name']}) answers before your server. It can "
             f"block some attacks; it does not patch your server.")
    sources = []
    for n in notes:
        means += " " + n["words"]
        sources.append(n["source"])
    return _card("info", f"A firewall sits in front: {f['name']}", f["saw"], means,
                 "Patch anyway: the firewall is a second line, not the fix.", [f["host"]],
                 product=f["product"], sources=sources)


def tip_card(f: dict) -> dict:
    return _card("tip", f"Your server shows its exact version: {f['name']} {f['version']}", f["saw"],
                 f"This means anyone can read it. No advisory in our list names {f['name']}, so "
                 f"this is not a flaw found: it only tells scanners what to try.",
                 f"Hide it: {HIDE.get(f['product'], 'remove the version from the Server header')}.",
                 [f["host"]], product=f["product"])


def login_card(row: dict) -> dict:
    lg = row["login"]
    saw = []
    for hop in lg.get("chain") or []:
        words = f"{hop['url']} answered {hop['status']}" + (
            f", sending visitors to {hop['location']}" if hop.get("location") else "")
        saw.append(_see(f"We saw {words}", hop["url"], f"curl -sI {_q(hop['url'])}"))
    last = (lg.get("chain") or [{}])[-1].get("url") or lg["url"]
    if lg["state"] == "open":
        saw.append(_see(f"We saw a WordPress login form on {last}", last,
                        f"curl -sL {_q(lg['url'])} | grep -c 'id=\"loginform\"'"))
        return _card("login", "Login page open to the internet", saw,
                     "This means anyone can try passwords there, all day.",
                     "Allow only your own addresses there, or add a second factor, and use long, "
                     "unique passwords.", [row["host"]])
    if lg["state"] == "hidden":
        if not saw:
            saw.append(_see(f"We saw {lg['url']}: {lg['why']}", lg["url"], f"curl -sI {_q(lg['url'])}"))
        elif not lg["why"].startswith("it "):
            saw.append(_see(f"We saw {last} answer with {lg['why']}", last,
                            f"curl -sL {_q(lg['url'])} | grep -c -E 'loginform|name=.pwd.'"))
        return _card("good", f"Login page on {row['host']} hidden or blocked (good)", saw,
                     "This means /wp-login.php does not show a login form to strangers.",
                     "Nothing to do.", [row["host"]])
    saw.append(_see(f"We could not read {lg['url']}: {lg['why']}", lg["url"], f"curl -sIL {_q(lg['url'])}"))
    return _card("unknown", f"Login page on {row['host']}: could not check", saw,
                 "This means we say nothing about it: we could not see it.",
                 f"Open {lg['url']} yourself: a login form there is open to anyone.", [row["host"]])


def extras_cards(row: dict) -> list[dict]:
    out, ex = [], row.get("extras") or {}
    x = ex.get("xmlrpc")
    if x and x["on"]:
        out.append(_card("tip", "XML-RPC is on", [
            _see(f"We saw {x['url']} answer {x['status']}: \"XML-RPC server accepts POST requests only.\"",
                 x["url"], f"curl -s {_q(x['url'])}")],
            "This means WordPress's old remote API answers. It is often used to try many passwords "
            "in one request.", "Turn it off if nothing you use needs it (a security plugin, or "
            "deny /xmlrpc.php in the web server).", [row["host"]]))
    r = ex.get("readme")
    if r and r.get("version"):
        out.append(_card("tip", f"readme.html shows WordPress {r['version']}", [
            _see(f"We saw {r['url']} answer {r['status']}, showing Version {r['version']}", r["url"],
                 f"curl -s {_q(r['url'])} | grep -i -o 'version [0-9.]*'")],
            "This means anyone can read your WordPress version there.",
            "Delete readme.html (WordPress puts it back on updates; a rule in the web server "
            "keeps it hidden).", [row["host"]], facts=[f"WordPress {r['version']}"]))
    return out


def headers_card(row: dict) -> dict | None:
    got = row.get("headers") or {}
    url = row.get("url") or f"https://{row['host']}/"
    cmd = f"curl -sI {_q(url)} | grep -i -E '^({'|'.join(h for h, _ in HEADERS)}):'"
    have = {h: ", ".join(got.get(h) or []) for h, _ in HEADERS if got.get(h)}
    csp = have.get("content-security-policy", "")
    if "x-frame-options" not in have and "frame-ancestors" in csp.lower():
        have["x-frame-options"] = "(frame-ancestors in the Content-Security-Policy)"
    saw = [_see(f"We saw the header {pretty}: {have[h][:160]}", url, cmd)
           for h, pretty in HEADERS if h in have and not have[h].startswith("(")]
    missing = [pretty for h, pretty in HEADERS if h not in have]
    if missing:
        saw.append(_see(f"We saw no {_and(missing)} header in the home page's answer", url, cmd))
        return _card("tip", f"Security headers: {len(HEADERS) - len(missing)} of {len(HEADERS)}", saw,
                     "This means browsers get fewer instructions to block some attacks (framing, "
                     "content sniffing, mixed content). They do not fix PHP or Node.js; they are "
                     "worth adding.", f"Add {_and(missing)} in the web server or the app.", [row["host"]])
    return _card("good", "Security headers: all 5 set", saw,
                 "This means browsers get clear instructions to block framing, content sniffing "
                 "and mixed content.", "Nothing to do.", [row["host"]])


def cert_days(row: dict, now: datetime) -> int | None:
    if not row.get("not_after"):
        return None
    try:
        end = ssl.cert_time_to_seconds(row["not_after"])
    except ValueError:
        return None
    return int((end - now.timestamp()) // 86400)


def headless_card(origin: dict, site_found: list, site_host: str) -> dict:
    """A WordPress on another host of the domain that the site's page loads files from:
    "headless" when the front is a JavaScript app (Next.js ...), else plainly where it is."""
    front = [f for f in site_found if f["family"] == "js"][:1]
    saw = (front[0]["saw"][:1] if front else []) + origin["found"][0]["saw"]
    if origin.get("headless"):
        h = origin["headless"]
        saw.append(_see(f"We saw {h['url']} answer {h['status']}, sending visitors to {h['location']}",
                        h["url"], f"curl -sI {_q(h['url'])}"))
    if front:
        return _card("info", f"Headless WordPress at {origin['host']}", saw,
                     f"This means {site_host} ({front[0]['name']}) takes its content from a WordPress "
                     f"at {origin['host']}. That server runs PHP, so it needs the PHP update too.",
                     f"Check PHP on the server behind {origin['host']}.", [origin["host"], site_host])
    return _card("info", f"WordPress at {origin['host']}", saw,
                 f"This means {site_host} loads files from a WordPress at {origin['host']}. That "
                 f"server runs PHP, so it needs the PHP update too.",
                 f"Check PHP on the server behind {origin['host']}.", [origin["host"], site_host])


def merge(cards: list[dict]) -> list[dict]:
    """Cards of the same kind and title (the same finding, seen on several hosts) as one card:
    its hosts in order, every host's evidence ("saw") kept, and the hosts named in "means".
    The order of first appearance is kept, so the counts and the summary count each once."""
    out, seen = [], {}
    for c in cards:
        key = (c["kind"], c["title"])
        first = seen.get(key)
        if first is None:
            seen[key] = c
            out.append(c)
            continue
        if first is c:
            continue
        if not first.get("merged"):
            first.update(saw=list(first.get("saw") or []), hosts=list(first.get("hosts") or []),
                         merged=True, means_one=first.get("means", ""))
        for s in c.get("saw") or []:
            if not any(s.get("text") == x.get("text") and s.get("url") == x.get("url")
                       for x in first["saw"]):
                first["saw"].append(s)
        for h in c.get("hosts") or []:
            if h not in first["hosts"]:
                first["hosts"].append(h)
        for f in c.get("facts") or []:
            first.setdefault("facts", [])
            if f not in first["facts"]:
                first["facts"].append(f)
    for c in out:
        if c.pop("merged", False):
            one = c.pop("means_one")
            if len(c["hosts"]) > 1:
                c["means"] = f"{one} Seen on {len(c['hosts'])} hosts: {_and(c['hosts'])}.".strip()
    return out


def summary(site: dict, found: list, rts: list, cards: list) -> str:
    here = [f for f in found if f["host"] == site["host"]]
    app = next((f for fam in ("hosted", "cms", "js", "framework") for f in here if f["family"] == fam), None)
    words = "Your site"
    if app:
        words += f" runs {app['name']}" + (f" {app['version']}" if app.get("version") else "")
    elif any(f["family"] == "server" for f in here):
        srv = next(f for f in here if f["family"] == "server")
        words += f" is served by {srv['name']}"
    host = next((f for f in here if f["family"] == "hosting"), None)
    if not app and not any(f["family"] == "server" for f in here):
        words += f" is hosted on {host['name']}" if host else " names no platform we know"
        host = None
    mine = [r for r in rts if r["host"] == site["host"]]
    rt = next((r for r in mine if app and any(u.startswith(app["name"]) for u in r.get("under") or [])),
              mine[0] if mine else None)
    if rt and not (app and app["family"] == "hosted"):
        words += f" on {rt['name']}" + (f" {rt['version']}" if rt.get("version") else
                                        f" (run by {rt['patched']})" if rt.get("patched")
                                        else " (version hidden)")
    elif host:
        words += f", hosted on {host['name']}"
    cdn = next((f for f in here if f["product"] in FIREWALLS), None)
    if cdn:
        words += f" behind {cdn['name']}"
    n = {g: sum(1 for c in cards if c["group"] == g) for g in ORDER}
    todo = f"{n['act']} thing{'s' if n['act'] != 1 else ''} to do now" if n["act"] else "Nothing to do now"
    rest = [f"{n['check']} to check" if n["check"] else "", f"{n['tips']} tip{'s' if n['tips'] != 1 else ''}"
            if n["tips"] else ""]
    return f"{words}. {todo}" + "".join(f", {r}" for r in rest if r) + "."


def answer(host: str, blob: dict, doc: dict, now: datetime, ua: str) -> dict:
    """The JSON the page shows and the report mails."""
    rows = blob.get("hosts") or []
    site = next((r for r in rows if r["role"] == "site"), {"host": host})
    reached = bool(site.get("read"))
    found = [f for r in rows for f in r.get("found") or []]
    rts = [r for r in runtimes(found) if r["product"] in ("php", "nodejs")]
    cards = []
    by_id = {a["id"]: a for a in doc.get("advisories") or []}
    for rt in rts:
        servers = [f for f in found if f["host"] == rt["host"] and f["family"] == "server"]
        if rt.get("patched"):
            maker = next((f for f in found if f["host"] == rt["host"] and f.get("patched") == rt["patched"]
                          and f["family"] in ("hosted", "hosting")), None)
            if maker and maker["family"] == "hosting":
                cards.append(hosted_card({**maker, "saw": maker["saw"] + rt["saw"]}, rt["product"]))
            continue
        for m in advisories.match([{"product": rt["product"], "version": rt.get("version"),
                                    "host": rt["host"]}], doc):
            cards.append(advisory_card(rt, by_id[m["advisory"]], m["state"], servers))
    php_hosts = {r["host"] for r in rts if r["product"] == "php" and not r.get("patched")}
    for f in found:
        if f["family"] == "hosted":
            cards.append(hosted_card(f))
        elif f["product"] in FIREWALLS and f["host"] == site.get("host"):
            cards.append(firewall_card(f, doc, f["host"] in php_hosts))
        elif f["family"] == "server" and f.get("version"):
            cards.append(tip_card(f))
    for row in rows:
        if row.get("login"):
            cards.append(login_card(row))
        cards += extras_cards(row)
    origin = next((r for r in rows if r["role"] == "content origin"), None)
    facts = []
    if reached:
        if origin:
            cards.append(headless_card(origin, [f for f in found if f["host"] == site["host"]],
                                       site["host"]))
        card = headers_card(site)
        if card:
            cards.append(card)
        days = cert_days(site, now)
        if days is not None:
            facts.append(f"Certificate valid for {days} more day{'s' if days != 1 else ''}")
            if days < CERT_WARN_DAYS:
                url = site.get("url") or f"https://{site['host']}/"
                cards.append(_card("tip", f"Your certificate expires in {days} day{'s' if days != 1 else ''}", [
                    _see(f"We saw the certificate for {site['host']} valid until {site['not_after']}", url,
                         f"echo | openssl s_client -connect {_q(site['host'] + ':443')} -servername "
                         f"{_q(site['host'])} 2>/dev/null | openssl x509 -noout -enddate")],
                    "This means browsers will warn visitors after that date.",
                    "Renew it, or check that automatic renewal works.", [site["host"]]))
        if blob.get("moved"):
            facts.append(f"Goes to {blob['moved']}")
    if not reached:
        f = (blob.get("fetched") or [{}])[-1]
        url = f.get("url") or f"https://{host}/"
        saw = [_see(f"We could not read {url}: {site.get('error') or 'no answer'}", url, f"curl -sIL {_q(url)}")]
        if blob.get("reason") == "blocked":
            cards.append(_card("unknown", f"{host}'s firewall blocked our check", saw,
                               "This means we can't see what it shows, so we say nothing about it. "
                               "That's often good news: strangers see little too.",
                               "Check the versions on your server instead: php -v, node -v, nginx -v "
                               "(or apachectl -v).", [host],
                               commands=["php -v", "node -v", "nginx -v", "apachectl -v"]))
        else:
            cards.append(_card("unknown", f"Could not check {host}", saw,
                               "This means we say nothing about this site: we could not read it.",
                               "Check the address, or try again later.", [host]))
    elif not any(c["kind"] in ("update", "hidden", "login", "hosted") for c in cards):
        home = next((f for f in blob.get("fetched") or [] if f.get("url") == site.get("url")), {})
        named = [f["name"] for f in found if f["host"] == site["host"]]
        saw = [_see(f"We saw {site.get('url')} answer {home.get('status', 200)}"
                    + (f" ({home['bytes']:,} bytes)" if home.get("bytes") is not None else "")
                    + (f", showing {_and(named)}" if named else ", naming no server, language or framework"),
                    site.get("url"), f"curl -sI {_q(site.get('url') or '')}")]
        cards.append(_card("nothing", "Nothing we know of applies", saw,
                           f"This means none of the advisories in our list (updated "
                           f"{doc.get('updated')}) names what your site shows.",
                           "This is only what anyone can see from outside: keep the server and "
                           "everything on it updated anyway.", [site["host"]]))
    cards.sort(key=lambda c: (ORDER.index(c["group"]), KINDS.index(c["kind"])))
    cards = merge(cards)
    products = [{"product": f["product"], "name": f["name"], "version": f.get("version"),
                 "shown": f.get("version") or (f"run by {f['patched']}" if f["family"] == "runtime"
                                               and f.get("patched") else "version not shown"
                                               if f["family"] in ("runtime", "cms", "server") else ""),
                 "family": f["family"], "host": f["host"], "patched": f.get("patched")}
                for f in [*[x for x in found if x["product"] not in ("php", "nodejs")], *rts]]
    return {"host": host, "reached": reached, "error": None if reached else site.get("error"),
            "reason": None if reached else blob.get("reason") or "unreachable",
            "summary": summary(site, found, rts, cards) if reached else None,
            "counts": {g: sum(1 for c in cards if c["group"] == g) for g in ORDER},
            "checked_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "agent": ua, "fetched": blob.get("fetched") or [], "facts": facts,
            "hosts": [{"host": r["host"], "role": r["role"], "reached": bool(r.get("read") or r.get("found")),
                       "error": r.get("error")} for r in rows],
            "products": products, "cards": cards, "advisories_updated": doc.get("updated"),
            "fetches": blob.get("fetches", 0)}
