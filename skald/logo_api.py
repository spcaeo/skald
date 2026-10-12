"""The site's logo, from the refresh helper (2.6.0; site_logos.py).

  GET  <page>/logo           the logo as an image: its stored type as the
                             Content-Type, nosniff, a CSP of its own that runs
                             nothing (sandbox), never HTML; 404 while the site
                             shows its letter. Any member of the site.
                             ?src=fetched|upload: that stored file (Settings'
                             preview of each choice)
  GET  <page>/logo/state     what Settings > Sites > Logo shows (accounts)
  POST <page>/logo/upload    {"data": base64, "name"}: PNG, ICO or a safe SVG,
                             at most 256 KB; sets site.logo.source to upload.
                             Owners and admins, with the CSRF value (accounts)
  POST <page>/logo/check     ask the site for its icon now; at most once a
                             minute per site; owners and admins (accounts)

<page> is /traffic/<site>/[<view>/]. refresh_server.py calls `handle` after
helper_sessions.gate, so in sessions mode `who` is the session's caller
and a member of the site; in basic mode nginx's password guards the image
and the rest answers 404, as the settings routes do. An upload and a check
each write an audit row; the source change is the setting's own audit row
(settings_store.put).
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from pathlib import Path

from . import auth_api, helper_sessions, logo_image, site_logos
from . import settings_store as store

PATH = re.compile(r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
                  r"logo(?:/(?P<act>state|upload|check))?$")
POSTS = ("upload", "check")
MAX_UPLOAD_BODY = 400_000              # 256 KB as base64, with room for the JSON
IMAGE_CSP = "default-src 'none'; style-src 'unsafe-inline'; sandbox"


def match(path: str):
    path = path.split("?", 1)[0]
    if ".." in path:
        return None
    return PATH.match(path)


def is_logo(path: str) -> bool:
    return match(path) is not None


def _query(path: str) -> dict:
    from urllib.parse import parse_qsl
    return dict(parse_qsl(path.split("?", 1)[1])[:5]) if "?" in path else {}


def _config(config, config_path, site: str, live_dir=None) -> dict:
    """The site's config with its settings rows laid over it (its host names
    as Settings > Sites has them)."""
    from .settings_api import site_config
    got = site_config(config, config_path, site)
    try:
        return store.apply(got, site, live_dir)
    except Exception:                   # noqa: BLE001 - no accounts file: the config alone
        return got


def send_image(h, path: Path, kind: str) -> None:
    data = path.read_bytes()
    h.send_response(200)
    h.send_header("Content-Type", logo_image.CTYPES[kind])
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Content-Security-Policy", IMAGE_CSP)
    h.send_header("Cross-Origin-Resource-Policy", "same-origin")
    h.send_header("Content-Disposition", f'inline; filename="logo.{kind}"')
    # The address carries the file's hash (?v=), so a new logo is a new address.
    h.send_header("Cache-Control", "private, max-age=86400")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)


def handle(h, write: bool, config, live_dir, allowed, same_origin, config_path,
           who: dict | None) -> None:
    m = match(h.path)
    site, act = m.group("site"), m.group("act")
    if write != (act in POSTS):
        return h._json(405, {"ok": False, "error": "wrong method"})
    cfg = _config(config, config_path, site, live_dir)
    if act is None:
        which = _query(h.path).get("src")         # Settings' preview: one stored file
        got = site_logos.stored(live_dir, site, which) if which else \
            site_logos.chosen(cfg, site, live_dir)
        if got is None:
            return h._json(404, {"ok": False, "error": "no logo: the site shows its letter"})
        return send_image(h, got[0], got[1]["kind"])
    if not auth_api.sessions_mode(config) or who is None:
        return h._json(404, {"ok": False, "error": "not found"})
    if act == "state":
        may, why = store.may_edit("site.logo.source", who["role"], who["install_admin"], config)
        return h._json(200, {"ok": True, "site": site, "editable": may, "reason": why,
                             **site_logos.status(cfg, site, live_dir)})
    if not same_origin(h.headers, allowed):
        return h._json(403, {"ok": False, "error": "same-origin requests only"})
    if not helper_sessions.need(h, who, install=False):
        return None
    if "site.logo.source" in store.locked(config):
        return h._json(403, {"ok": False, "error": store.LOCK_WORDS})
    if act == "check":
        return _check(h, cfg, site, live_dir, config, who)
    return _upload(h, cfg, site, live_dir, config, who)


def _audit(config, live_dir, site: str, actor: str, action: str, detail: str,
           source: str | None = None) -> None:
    """The audit row, and (upload) the source set to upload, in accounts.sqlite."""
    from .accounts import auditlog
    from .accounts import db as base
    db = auth_api.open_db(config, live_dir)
    if db is None:
        return
    try:
        if source is not None:
            store.put(db, f"site:{site}", "site.logo.source", source, actor)
        with base.tx(db):
            auditlog.record(db, store._org_of(db, site), actor, action, site, detail)
    finally:
        db.close()


def _check(h, cfg, site, live_dir, config, who) -> None:
    wait = site_logos.checked_recently(live_dir, site)
    if wait:
        return h._json(429, {"ok": False, "error": f"The site was asked a moment ago. "
                                                    f"Try again in {wait} seconds."})
    got = site_logos.check(cfg, site, live_dir)
    found = (got.get("fetched") or {}).get("url") if got.get("ok") else None
    _audit(config, live_dir, site, who["email"], "logo.check",
           f"found {found}" if found else f"none: {got.get('error')}")
    return h._json(200, {"ok": True, **site_logos.status(cfg, site, live_dir)})


def _body(h) -> dict | None:
    try:
        length = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length < 0 or length > MAX_UPLOAD_BODY:
        h._json(413, {"ok": False, "error": "The file is over 256 KB."})
        return None
    raw = h.rfile.read(length) if length else b""
    try:
        got = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, ValueError):
        got = None
    if not isinstance(got, dict):
        h._json(400, {"ok": False, "error": "a JSON object, please"})
        return None
    return got


def _upload(h, cfg, site, live_dir, config, who) -> None:
    form = _body(h)
    if form is None:
        return None
    try:
        body = base64.b64decode(str(form.get("data") or ""), validate=True)
    except (binascii.Error, ValueError):
        return h._json(400, {"ok": False, "error": "The file did not arrive whole; "
                                                   "choose it again."})
    try:
        kept = site_logos.store_upload(live_dir, site, body, who["email"])
    except logo_image.Refused as why:
        return h._json(400, {"ok": False, "error": str(why)})
    size = "x".join(str(n) for n in kept["size"]) if kept.get("size") else "scalable"
    _audit(config, live_dir, site, who["email"], "logo.upload",
           f"{kept['kind']} {size}, {kept['bytes']} bytes, sha256 {kept['sha']}",
           source="upload")
    return h._json(200, {"ok": True, **site_logos.status(cfg, site, live_dir)})
