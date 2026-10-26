"""The refresh helper in `access.mode: sessions`: who may ask what.

refresh_server.py calls `gate` before every /traffic/ route it serves
itself (refresh, ours, me, funnels, the dashboard API, bot-policy, the
sites list). The person asking is read from the session cookie
(access.session_caller), never from X-Skald-User or X-Skald-Role, so a
local process that can reach the helper's port cannot pose as anyone:

  no valid session                              401
  /traffic/<site>/... and not a member of the
  site's organisation                           403
  otherwise                                     the caller, for the route

The /traffic-auth/ pages, the token routes (/traffic-api/) and
/traffic-mcp are not gated here: they have their own checks.

Changes that apply to the whole install - the AI crawler policy, the
funnels file, the internal-address list - need an install admin
(`need`, install=True). The address list itself is read by owners and
admins of the site's organisation, and an admin who is not an install admin
sees only the entries added on their own sites' pages.

The sites list (/traffic/sites.json, /traffic/<site>/data/sites.json) and
the site picker (/traffic/, /traffic/index.html; site_picker.py) are answered
here, filtered to the caller's organisations, so one organisation never sees
another's site names; each site comes with its logo and today so far as they
are at that moment. nginx proxies those paths to the helper in sessions
mode (DEPLOY.md).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from . import access, auth_api
from .files import slug

SITE_OF_PATH = re.compile(r"^/traffic/(?P<site>[a-z0-9.-]+)/")
SITES_JSON = re.compile(r"^/traffic/(?:(?P<site>[a-z0-9.-]+)/data/)?sites\.json$")
ROOT_INDEX = ("/traffic/", "/traffic/index.html")
NOT_SITES = ("sites.json", "index.html")
INSTALL_WORDS = ("Only an install admin can change this: it applies to every site of "
                 "the install.")


def site_of(path: str) -> str | None:
    """The site a /traffic/<site>/... route is for, or None (no site)."""
    m = SITE_OF_PATH.match(path.split("?", 1)[0])
    if m is None or m.group("site") in NOT_SITES:
        return None
    return m.group("site")


def gate(h, config, live_dir) -> dict | None:
    """The caller (access.session_caller) for this request, or None after
    answering 401 (no session) or 403 (not a member of the site's org)."""
    path = h.path.split("?", 1)[0]
    if ".." in path:
        h._json(404, {"ok": False, "error": "not found"})
        return None
    site = site_of(path)
    who = access.session_caller(config, live_dir, h.headers, site)
    if who is None:
        h._json(401, {"ok": False, "error": "Sign in first."})
        return None
    if site is not None and who["role"] is None:
        h._json(403, {"ok": False, "error": "You are not a member here."})
        return None
    return who


def need(h, who: dict, install: bool) -> bool:
    """An admin of the site's org (or, `install`, an install admin) with the
    session's CSRF value; False after answering 403."""
    if install and not who["install_admin"]:
        h._json(403, {"ok": False, "error": INSTALL_WORDS, "role": who["role"]})
        return False
    if not install and who["role"] not in ("owner", "admin"):
        h._json(403, {"ok": False, "error": "admins only", "role": who["role"]})
        return False
    if not auth_api.csrf_ok(who, h.headers):
        h._json(403, {"ok": False, "error": "The page is out of date. Reload it and try again."})
        return False
    return True


def ours_listing(config, who: dict) -> list[dict]:
    """The internal addresses this caller may see."""
    from . import ours_store
    if who["install_admin"]:
        return ours_store.listing(config)
    return ours_store.for_sites(config, who["admin_sites"])


# -------------------------------------------------------- the sites list

def _send(h, code: int, data: bytes, ctype: str) -> None:
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    h.send_header("Content-Length", str(len(data)))
    h.end_headers()
    h.wfile.write(data)


def is_listing(path: str) -> bool:
    path = path.split("?", 1)[0]
    return path in ROOT_INDEX or SITES_JSON.match(path) is not None


def listing(h, out: Path | None, who: dict, config=None, live_dir=None,
            config_path=None) -> None:
    """sites.json or the site picker, with only the caller's sites, each with
    its logo and today so far as they are now (site_picker.py)."""
    from . import site_picker
    path = h.path.split("?", 1)[0]
    mine = set(who["member_sites"])
    if path in ROOT_INDEX:
        known = {s.get("name"): s for s in _listed(out)}
        sites = [known.get(n) or {"name": n, "slug": slug(n), "path": f"{slug(n)}/"}
                 for n in _order(out, mine)]
        sites = site_picker.enrich(sites, out, config, live_dir, config_path)
        admin = [n for n in _order(out, set(who.get("admin_sites") or []))]
        wizard = f"{slug(admin[0])}/#settings/sitesadmin" if admin else None
        add = f"{wizard}?setup=new" if admin else None
        # A set-up left half way, or a site that heard nothing for a day: a link
        # that reopens the wizard (connections_api.badges; admins only), in a
        # dashboard of the site's own organisation (setup_page.app_for); none
        # drawn yet: no link, and its card leads to its waiting page.
        from . import connections_api, setup_page
        try:
            marks = connections_api.badges(config, live_dir, config_path, admin)
            known = setup_page.states(config, config_path) if marks and out else {}
        except Exception:                 # noqa: BLE001 - the picker never fails for a badge
            marks, known = {}, {}
        order = [s["name"] for s in sites]
        for s in sites:
            got = marks.get(s.get("name"))
            home = got and setup_page.app_for(s["name"], known, order, Path(out))
            if home:
                s["badge"] = {"words": got[0], "href": f"{slug(home)}/#settings/sitesadmin"
                                                       f"?{got[1]}={quote(s['name'])}"}
        # Where visitors came from on each of the caller's sites (across_sites.py):
        # only the sites listed here, so another organisation's never shows.
        from .across_sites import section
        page = site_picker.render(sites, datetime.now(timezone.utc), who.get("email"), add,
                                  across=section(out, sites), orgs=org_names(who))
        return _send(h, 200, page.encode("utf-8"), "text/html; charset=utf-8")
    current = SITES_JSON.match(path).group("site")
    file = (Path(out) / "sites.json" if current is None
            else Path(out) / slug(current) / "data" / "sites.json") if out else None
    try:
        body = json.loads(file.read_text()) if file is not None else None
    except (OSError, ValueError):
        body = None
    if not isinstance(body, dict):
        return h._json(404, {"ok": False, "error": "no such file"})
    body["sites"] = site_picker.enrich(
        [s for s in body.get("sites") or [] if isinstance(s, dict) and s.get("name") in mine],
        out, config, live_dir, config_path)
    orgs = org_names(who)
    for s in body["sites"] if orgs else ():
        s["org"] = orgs.get(s.get("name"))
    data = (json.dumps(body, separators=(",", ":")) + "\n").encode()
    return _send(h, 200, data, "application/json; charset=utf-8")


def org_names(who: dict) -> dict[str, str]:
    """{site: its organisation's name} for a caller in two or more
    organisations with sites (2.38.0: the switcher and the picker group by
    it), else {}: one organisation needs no heading."""
    orgs = [o for o in who.get("orgs") or [] if o.get("sites")]
    if len(orgs) < 2:
        return {}
    return {s: o["name"] for o in orgs for s in o["sites"]}


def _listed(out: Path | None) -> list[dict]:
    """The install's sites.json entries (every site), or []."""
    try:
        got = json.loads((Path(out) / "sites.json").read_text()).get("sites") or []
    except (OSError, ValueError, TypeError, AttributeError):
        return []
    return [s for s in got if isinstance(s, dict) and s.get("name")]


def _order(out: Path | None, mine: set[str]) -> list[str]:
    """The caller's sites in the order of the install's sites.json."""
    listed = [s["name"] for s in _listed(out) if s["name"] in mine]
    return listed + sorted(mine - set(listed))
