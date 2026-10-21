"""The "Share with your developer" links (share_links.py): the admin's routes
and the page the link opens, with no sign-in.

Admin routes (sites_api.py routes them: session, owner or admin, CSRF):

  POST sites/share     {site, task: send|script|hook, method?, days: 1|7|30}
                       -> {link, ref, expires_at}; the link is shown once
  GET  sites/shares    -> {shares: [{ref, site, task, method, created_at,
                       expires_at, state, views, viewed_at, revealed_at}]}
  POST sites/unshare   {ref}: revoke

The link's page, under /traffic-auth/ (which every install's nginx already
passes on without a session, unlogged and noindex):

  GET  /traffic-auth/setup/<id>            the page (one task, one site)
  GET  /traffic-auth/setup/<id>/info       what the page draws
  POST /traffic-auth/setup/<id>/reveal     the secret, made now, once
  GET  /traffic-auth/setup/<id>/status     the Test: what reached Skald
  POST /traffic-auth/setup/<id>/kit        the install kit (send: docker, systemd)
  POST /traffic-auth/setup/<id>/test       a signed test lead (hook), never kept
  GET  /traffic-auth/app/<file>.js|.css    the app's own code the page runs
                                           (webapp/js, webapp/css, webapp/vendor:
                                           the published code, no data)

An unknown, expired or revoked link is 404 or 410 with the same words. Every
public request is rate-limited per caller address, in memory only; no address,
token or secret is written to any log. POSTs need the same-origin check.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import auth_api, ingest, share_links
from .auth_api import answer, read_json, text

PUBLIC = re.compile(r"^/traffic-auth/setup/(?P<id>[A-Za-z0-9_-]{22})(?:/(?P<act>info|reveal|status|kit|test))?$")
APP = re.compile(r"^/traffic-auth/app/(?P<file>(?:js|css|vendor)/[a-z0-9/_.-]+\.(?:js|css)|[a-z0-9_-]+\.css)$")
WEBAPP = Path(__file__).resolve().parent / "webapp"
PER_MINUTE, BURST = 120, 60          # per caller address, in memory: the page loads ~30 files
GETS = {None, "info", "status"}


def is_public(path: str) -> bool:
    path = path.split("?", 1)[0]
    return ".." not in path and (PUBLIC.match(path) is not None or APP.match(path) is not None)


def _base(config, allowed) -> str:
    return str(auth_api.base_url(config, allowed) or "").rstrip("/")


def _hook_base(config, allowed) -> str:
    raw = ((config or {}).get("hooks") or {}).get("public_url")
    return str(raw or _base(config, allowed)).rstrip("/")


# ------------------------------------------------------------ admin routes

def share(c, form):
    from .connections_api import _site
    site = _site(c, text(form, "site", 200))
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    try:
        link_id, entry = share_links.create(c.db, c.org["id"], site, text(form, "task", 20), c.uid,
                                            text(form, "method", 20) or None, form.get("days", 7))
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(link=f"{_base(c.config, c.allowed)}/traffic-auth/setup/{link_id}", **entry)


def shares(c, form):
    if c.role not in ("owner", "admin"):
        return c.no(403, "Only an admin can do this.", role=c.role)
    return c.ok(shares=share_links.listing(c.db, c.org["id"]))


def unshare(c, form):
    try:
        got = share_links.revoke(c.db, c.org["id"], text(form, "ref", 20), c.uid)
    except ValueError as why:
        return c.no(404, str(why))
    return c.ok(**got)


# --------------------------------------------------------------- the page

_BUCKET = None


def _limited(h) -> bool:
    """True after answering 429. The caller's address is used here, in memory."""
    global _BUCKET
    if _BUCKET is None:
        _BUCKET = ingest.Bucket(PER_MINUTE, BURST)
    who = h.headers.get("X-Real-IP") or (h.client_address[0] if h.client_address else "-")
    wait = _BUCKET.take(f"share:{who}")
    if wait:
        answer(h, 429, {"ok": False, "error": "Too many requests. Wait a minute."},
               {"Retry-After": str(max(1, int(wait + 0.999)))})
        return True
    return False


def _send(h, code: int, data: bytes, ctype: str, extra: dict | None = None) -> None:
    h.send_response(code)
    for k, v in {"Content-Type": ctype, "Cache-Control": "no-store", "X-Content-Type-Options":
                 "nosniff", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex, nofollow",
                 **(extra or {}), "Content-Length": str(len(data))}.items():
        h.send_header(k, v)
    h.end_headers()
    h.wfile.write(data)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive"><meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light dark"><title>Set-up steps · Skald</title>
<link rel="stylesheet" href="/traffic-auth/app/app.css"><link rel="stylesheet" href="/traffic-auth/app/screens.css">
<link rel="stylesheet" href="/traffic-auth/app/features.css"><link rel="stylesheet" href="/traffic-auth/app/css/connections.css">
<style>body{background:var(--page);color:var(--ink);margin:0}main{max-width:860px;margin:0 auto;padding:32px 20px 60px;display:grid;gap:18px}
main h1{margin:0;font-size:26px}</style></head>
<body><main id="share" data-id="__ID__"><p>Loading the steps...</p></main><div id="toast" class="toast"></div>
<script type="module" src="/traffic-auth/app/js/tabs/share-page.js"></script></body></html>
"""
GONE_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Link ended · Skald</title></head><body style="font:16px/1.5 system-ui,sans-serif;max-width:560px;margin:60px auto;padding:0 20px">
<h1>This link does not work any more</h1><p>__WORDS__</p></body></html>
"""


def handle(h, write: bool, config, live_dir, allowed, same_origin, config_path=None) -> None:
    path = h.path.split("?", 1)[0]
    if not auth_api.sessions_mode(config):
        return answer(h, 404, {"ok": False, "error": "not found"})
    if _limited(h):
        return None
    app = APP.match(path)
    if app:
        if write:
            return answer(h, 405, {"ok": False, "error": "wrong method"})
        return _asset(h, app.group("file"))
    m = PUBLIC.match(path)
    act = m.group("act")
    if write == (act in GETS):
        return answer(h, 405, {"ok": False, "error": "wrong method"})
    if write and not same_origin(h.headers, allowed):
        return answer(h, 403, {"ok": False, "error": "same-origin requests only"})
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return answer(h, 503, {"ok": False, "error": "accounts are not set up here"})
    try:
        entry = share_links.find(db, m.group("id"))
        if entry is None:
            if act is None:
                return _send(h, 410, GONE_PAGE.replace("__WORDS__", share_links.GONE).encode(),
                             "text/html; charset=utf-8")
            return answer(h, 410, {"ok": False, "error": share_links.GONE})
        form = read_json(h) if write else {}
        if form is None:
            return None
        from . import share_page
        ctx = share_page.Ctx(h, db, entry, config, live_dir, allowed, config_path)
        if act is None:
            share_links.viewed(db, entry)
            page = PAGE.replace("__ID__", m.group("id"))
            return _send(h, 200, page.encode(), "text/html; charset=utf-8",
                         {"Content-Security-Policy": "default-src 'self'; style-src 'self' "
                          "'unsafe-inline'; img-src 'self' data:; object-src 'none'; "
                          "base-uri 'none'; frame-ancestors 'none'"})
        acts = {"info": share_page.info, "reveal": share_page.reveal, "status": share_page.status,
                "kit": share_page.kit_zip, "test": share_page.test}
        return acts[act](ctx, form)
    finally:
        db.close()


def _asset(h, name: str):
    path = (WEBAPP / name).resolve()
    if WEBAPP not in path.parents or not path.is_file():
        return answer(h, 404, {"ok": False, "error": "not found"})
    ctype = "text/javascript; charset=utf-8" if name.endswith(".js") else "text/css; charset=utf-8"
    data = path.read_bytes()
    h.send_response(200)
    for k, v in (("Content-Type", ctype), ("Cache-Control", "public, max-age=300"),
                 ("X-Content-Type-Options", "nosniff"), ("Content-Length", str(len(data)))):
        h.send_header(k, v)
    h.end_headers()
    h.wfile.write(data)
    return None

