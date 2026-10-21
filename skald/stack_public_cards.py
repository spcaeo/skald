"""The public check's answer (stack_public.py): one card per thing to know, each with its proof.

Every card says what was seen ("saw": the exact header line, tag or page references, with the
URL each was read from), what that means ("means": only what the facts prove), why an
advisory matched ("because": the product, its version or "version not shown", the host), and
how to check it yourself ("commands": curl lines anyone can run). The answer also lists every
request made ("fetched") and the User-Agent used, so the result can be verified without
trusting us.

Kinds, in the order shown:

  update   an advisory applies to a version the server showed: update needed
  hidden   an advisory names the product, but its version is not shown: check your version
  login    /wp-login.php ends in WordPress's login form: open to the internet
  unknown  something could not be checked (the site, a login page): said so, nothing claimed
  tip      a web server shows its exact version and no advisory names it: hide it
  info     a headless WordPress: the site loads its files from another host of its domain
  good     the login page is hidden or blocked
  fixed    the version shown has the fix
  nothing  the site was read and nothing in the advisory list applies

"Update needed" only for a version actually read; never "affected" without one.
"""
from __future__ import annotations

import shlex
from datetime import timezone

from . import advisories, stack

ORDER = ("update", "hidden", "login", "unknown", "tip", "info", "good", "fixed", "nothing")
WEB = ("nginx", "apache", "litespeed")
HIDE = {"nginx": "set server_tokens off; in nginx's http block, then reload nginx",
        "apache": "set ServerTokens Prod and ServerSignature Off, then reload Apache",
        "litespeed": "turn off the server signature in LiteSpeed's settings"}


def _q(url: str) -> str:
    return shlex.quote(url)


def header_cmd(url: str) -> str:
    return f"curl -sI {_q(url)} | grep -i -E '^(server|x-powered-by|link):'"


def _n(count: int, word: str) -> str:
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def _see(text: str, url: str, cmd: str) -> dict:
    return {"text": text, "url": url, "command": cmd}


def proofs(product: str, row: dict, inferred: bool = False) -> list[dict]:
    """What a product on this host was read from, exactly as received."""
    pr = row.get("proof") or {}
    url = pr.get("url") or f"https://{row['host']}/"
    out = []

    def headers(name, word=None):
        for line in pr.get("headers") or []:
            low = line.lower()
            if low.startswith(name + ":") and (word is None or word in low):
                out.append(_see(f"We saw the header {line}", url, header_cmd(url)))

    if product in WEB:
        headers("server")
    elif product == "php":
        headers("x-powered-by", "php")
        if not out:
            out += proofs("wordpress", row)
    elif product == "wordpress":
        if pr.get("generator_tag"):
            out.append(_see(f"We saw the tag {pr['generator_tag']}", url,
                            f"curl -s {_q(url)} | grep -i -o '<meta[^>]*generator[^>]*>'"))
        headers("link", "api.w.org")
        own = (pr.get("wp") or {}).get(row["host"])
        if own:
            out.append(_see(f"We saw {_n(own['count'], 'reference')} to {row['host']}'s own WordPress "
                            f"files (/wp-content/, /wp-includes/), for example {own['examples'][0]}",
                            url, f"curl -s {_q(url)} | grep -o -E '/wp-(content|includes)/' | wc -l"))
        loaded = row.get("loaded")
        if loaded:
            out.append(_see(f"We saw the page {loaded['page']} load {_n(loaded['count'], 'file')} from "
                            f"https://{row['host']}/wp-content/ or /wp-includes/, for example "
                            f"{loaded['examples'][0]}", loaded["page"],
                            f"curl -s {_q(loaded['page'])} | grep -o -E "
                            f"'https://{row['host']}/wp-(content|includes)/' | sort | uniq -c"))
    elif product in ("nextjs", "nodejs"):
        headers("x-powered-by", "next.js")
        nxt = pr.get("next") or {}
        if nxt.get("count"):
            out.append(_see(f"We saw {_n(nxt['count'], 'reference')} to Next.js files (/_next/), for "
                            f"example {nxt['examples'][0]}", url,
                            f"curl -s {_q(url)} | grep -o '/_next/' | wc -l"))
        if nxt.get("data"):
            out.append(_see("We saw Next.js's __NEXT_DATA__ script in the page", url,
                            f"curl -s {_q(url)} | grep -c __NEXT_DATA__"))
    return out


def _label(p: dict) -> str:
    name = stack.NAMES.get(p["product"], p["product"])
    if p["product"] == "php" and p.get("how") == "WordPress runs on PHP":
        return "WordPress (PHP)"
    if p["product"] == "nodejs" and p.get("how") == "Next.js runs on Node.js":
        return "Next.js (Node.js)"
    return name


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _mine(a: dict, ver: str | None):
    v = advisories.version(ver or "")
    if not v:
        return None
    branch = advisories.branch_of(v, a["branch"])
    return next((f for b, f in a["fixed"].items()
                 if advisories.branch_of(advisories.version(b) or (), a["branch"]) == branch), None)


def advisory_card(p: dict, a: dict, state: str, row: dict) -> dict:
    name, label, ver, host = (stack.NAMES.get(p["product"], p["product"]), _label(p),
                              p.get("version"), p["host"])
    fixed = [str(v) for v in a["fixed"].values()]
    saw = proofs(p["product"], row)
    base = {"advisory": a["id"], "product": p["product"], "version": ver, "hosts": [host],
            "severity": a.get("severity"), "cves": list(a.get("cves") or []), "fixed": fixed,
            "sources": [s for s in a.get("sources") or [] if str(s).startswith("https://")],
            "because": f"{label} {ver or 'version not shown'} on {host}", "saw": saw}
    if state == "update_needed":
        return {**base, "kind": "update", "title": f"Update needed: {label} {ver} on {host}",
                "means": f"This means {name} {ver} is older than {_mine(a, ver)}, the fixed "
                         f"release of its branch. {a.get('summary', '')}".strip(),
                "advice": a.get("action", "")}
    if state == "no_fix":
        return {**base, "kind": "update",
                "title": f"Update needed: {label} {ver} on {host} gets no official fix",
                "means": f"This means {a.get('no_fix_words', '')} {a.get('summary', '')}".strip(),
                "advice": a.get("action", "")}
    if state == "check_version":
        cmd = stack.COMMANDS.get(p["product"], "")
        return {**base, "kind": "hidden",
                "title": f"{label} on {host}: version not shown by the server",
                "means": f"This means we can't tell whether the fix is in. Keeping the version "
                         f"hidden is good, but the flaw works either way. {a.get('title', '')}: "
                         f"fixed in {_and(fixed)}. {a.get('no_fix_words', '')}".strip(),
                "advice": f"Check it on the server with {cmd}, and update if it is older."
                if cmd else "Check the version on the server, and update if it is older.",
                "command": cmd}
    mine = _mine(a, ver)
    return {**base, "kind": "fixed", "title": f"{label} {ver} on {host} has the fix",
            "means": f"This means {a.get('title', '')} does not apply: "
                     + (f"fixed in {mine} on this branch." if mine and state == "fixed"
                        else f"this branch is newer than every fixed release listed ({_and(fixed)})."),
            "advice": "Nothing to do for this advisory."}


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
        return {"kind": "login", "title": "Login page open to the internet", "hosts": [row["host"]],
                "saw": saw, "means": "This means anyone can try passwords there, all day.",
                "advice": "Allow only your own addresses there, or add a second factor, "
                          "and use long, unique passwords."}
    if lg["state"] == "hidden":
        if not saw:
            saw.append(_see(f"We saw {lg['url']}: {lg['why']}", lg["url"], f"curl -sI {_q(lg['url'])}"))
        elif not lg["why"].startswith("it "):
            saw.append(_see(f"We saw {last} answer with {lg['why']}", last,
                            f"curl -sL {_q(lg['url'])} | grep -c -E 'loginform|name=.pwd.'"))
        return {"kind": "good", "title": f"Login page on {row['host']} hidden or blocked (good)",
                "hosts": [row["host"]], "saw": saw,
                "means": "This means /wp-login.php does not show a login form to strangers.",
                "advice": "Nothing to do."}
    saw.append(_see(f"We could not read {lg['url']}: {lg['why']}", lg["url"], f"curl -sIL {_q(lg['url'])}"))
    return {"kind": "unknown", "title": f"Login page on {row['host']}: could not check",
            "hosts": [row["host"]], "saw": saw,
            "means": "This means we say nothing about it: we could not see it.",
            "advice": f"Open {lg['url']} yourself: a login form there is open to anyone."}


def tip_card(p: dict, row: dict) -> dict:
    name = stack.NAMES.get(p["product"], p["product"])
    return {"kind": "tip", "title": f"Your server shows its exact version: {name} {p['version']}",
            "hosts": [p["host"]], "saw": proofs(p["product"], row),
            "means": f"This means anyone can read it. No advisory in our list names {name}, so this "
                     f"is not a flaw found: it only tells scanners what to try.",
            "advice": f"Hide it: {HIDE[p['product']]}."}


def headless_card(origin: dict, site: dict) -> dict:
    saw = proofs("nextjs", site)[:1] + proofs("wordpress", origin)
    if origin.get("headless"):
        h = origin["headless"]
        saw.append(_see(f"We saw {h['url']} answer {h['status']}, sending visitors to {h['location']}",
                        h["url"], f"curl -sI {_q(h['url'])}"))
    return {"kind": "info", "title": f"Headless WordPress at {origin['host']}",
            "hosts": [origin["host"], site["host"]], "saw": saw,
            "means": f"This means {site['host']} takes its content from a WordPress at "
                     f"{origin['host']}. That server runs PHP, so it needs the PHP update too.",
            "advice": f"Check PHP on the server behind {origin['host']}."}


def answer(host: str, blob: dict, doc: dict, now, ua: str) -> dict:
    """The JSON the page shows and the report mails."""
    rows = blob.get("hosts") or []
    site = next((r for r in rows if r["role"] == "site"), {"host": host})
    reached = bool(site.get("evidence"))
    cards, products = [], []
    by_id = {a["id"]: a for a in doc.get("advisories") or []}
    for row in rows:
        if not row.get("evidence"):
            continue
        for p in stack.products(row["host"], row["evidence"]):
            products.append({**p, "name": stack.NAMES.get(p["product"], p["product"]),
                             "label": _label(p), "shown": p["version"] or "not shown by the server",
                             "saw": proofs(p["product"], row)})
            matched = advisories.match([p], doc)
            for m in matched:
                cards.append(advisory_card(p, by_id[m["advisory"]], m["state"], row))
            if not matched and p["product"] in WEB and p.get("version"):
                cards.append(tip_card(p, row))
        if row.get("login"):
            cards.append(login_card(row))
    origin = next((r for r in rows if r["role"] == "content origin"), None)
    if origin and site.get("evidence"):
        cards.append(headless_card(origin, site))
    if not reached:
        f = (blob.get("fetched") or [{}])[-1]
        url = f.get("url") or f"https://{host}/"
        cards.append({"kind": "unknown", "title": f"Could not check {host}", "hosts": [host],
                      "saw": [_see(f"We could not read {url}: {site.get('error') or 'no answer'}",
                                   url, f"curl -sIL {_q(url)}")],
                      "means": "This means we say nothing about this site: we could not read it.",
                      "advice": "Check the address, or try again later."})
    elif not any(c["kind"] in ("update", "hidden", "login") for c in cards):
        pr = site.get("proof") or {}
        saw = [_see(f"We saw the header {h}", pr.get("url"), header_cmd(pr.get("url")))
               for h in pr.get("headers") or []]
        saw = saw or [_see(f"We saw {pr.get('url')} answer {pr.get('status')}, naming no server, "
                           f"language or framework", pr.get("url"), header_cmd(pr.get("url")))]
        cards.append({"kind": "nothing", "title": "Nothing we know of applies", "hosts": [site["host"]],
                      "saw": saw,
                      "means": f"This means none of the advisories in our list (updated "
                               f"{doc.get('updated')}) names what your home page shows.",
                      "advice": "This is only what anyone can see from outside: keep the server "
                                "and everything on it updated anyway."})
    cards.sort(key=lambda c: ORDER.index(c["kind"]))
    return {"host": host, "reached": reached, "error": None if reached else site.get("error"),
            "checked_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "agent": ua, "fetched": blob.get("fetched") or [],
            "hosts": [{"host": r["host"], "role": r["role"], "reached": bool(r.get("evidence")),
                       "error": r.get("error")} for r in rows],
            "products": products, "cards": cards, "advisories_updated": doc.get("updated"),
            "fetches": blob.get("fetches", 0)}
