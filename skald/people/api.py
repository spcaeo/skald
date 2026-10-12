"""The helper's people routes (refresh_server.py dispatches them here).

    GET <page>/people?q=Q              a person (lookup.person): admins and
                                       owners only; every search is written
                                       to the audit log (never the value: its
                                       kind and a hash prefix)
    GET <page>/people/left-out         the leads and conversions the figures
                                       leave out (spam, duplicates, test)
    GET <page>/people/conversions?kind=cancelled|removed|test
                                       those conversions, with row and journey
    GET /traffic-api/v1/<site>/people?q=Q
                                       a person, for an API token with the
                                       read_private scope (tokens.PRIVATE)

The two listings are for every member who may read the site; names, emails
and visitor IDs in them only for admins and owners. In basic mode the role
comes from users.json (access.role_of), the audit line goes to privacy.log.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
PEOPLE_PATH = re.compile(PAGE + r"people(?:/(?P<act>left-out|conversions))?$")
PRIVATE_ROLES = ("owner", "admin")
KINDS = ("cancelled", "removed", "test")


def is_people(path: str) -> bool:
    return PEOPLE_PATH.match(path.split("?", 1)[0]) is not None


def _folder(config: dict, history_path) -> Path | None:
    from .policy import history_path as find
    if history_path is not None:
        return Path(history_path).parent
    got = find(config)
    return got.parent if got is not None else None


def _site_config(config: dict, site: str, config_path=None) -> dict:
    """The site's own config on a multi-site install, else the install's."""
    from ..config import site_name
    if site == site_name(config or {}):
        return config or {}
    try:
        from ..conversions.hooks import site_configs
        return site_configs(config or {}, config_path).get(site) or config or {}
    except (OSError, ValueError, SystemExit):
        return config or {}


def handle(h, config, live_dir, history_path=None, config_path=None, sessions_mode=False):
    """Answer one GET (the caller is already gated by the helper)."""
    from urllib.parse import parse_qsl
    from . import lookup
    path, _, raw = h.path.partition("?")
    m = PEOPLE_PATH.match(path)
    if m is None or ".." in path:
        return h._json(404, {"ok": False, "error": "not found"})
    q = dict(parse_qsl(raw)[:10])
    site = m.group("site")
    user, role = h._user()
    private = role in PRIVATE_ROLES
    cfg = _site_config(config, site, config_path)
    folder = _folder(cfg, history_path)
    act = m.group("act")
    if act == "left-out":
        return h._json(200, {**lookup.left_out(cfg, folder, site, private), "private": private})
    if act == "conversions":
        kind = q.get("kind") or "removed"
        if kind not in KINDS:
            return h._json(400, {"ok": False, "error": f"kind is one of {', '.join(KINDS)}"})
        return h._json(200, {**lookup.conversions_listing(cfg, folder, site, kind, private),
                             "private": private})
    if not private:
        return h._json(403, {"ok": False, "role": role,
                             "error": "Only an admin or an owner can look a person up: it "
                                      "shows addresses, emails and names."})
    try:
        got = lookup.person(cfg, folder, site, q.get("q", ""), live_dir)
    except lookup.Invalid as why:
        return h._json(400, {"ok": False, "error": str(why)})
    record(config, live_dir, site, h.who if sessions_mode else None, user, got)
    return h._json(200, got)


def token(h, m, config, live_dir, history_path=None, config_path=None) -> None:
    """/traffic-api/v1/<site>/people?q=: the token was checked (read_private)."""
    from urllib.parse import parse_qsl
    from . import lookup
    q = dict(parse_qsl(h.path.partition("?")[2])[:10])
    site = m.group("site")
    cfg = _site_config(config, site, config_path)
    try:
        got = lookup.person(cfg, _folder(cfg, history_path), site, q.get("q", ""), live_dir)
    except lookup.Invalid as why:
        return h._json(400, {"ok": False, "error": str(why)})
    record(config, live_dir, site, None, "api token", got)
    return h._json(200, got)


def words(got: dict) -> str:
    """The audit line's detail: the kind, a hash prefix and what was found."""
    kind, value = got["query"]["kind"], got["query"]["value"]
    digest = hashlib.sha256(str(value).strip().lower().encode()).hexdigest()[:12]
    return (f"{kind} sha256:{digest} visits={len(got['visits'])} leads={len(got['leads'])} "
            f"conversions={len(got['conversions'])} removed={len(got['removed'])}")


def record(config, live_dir, site: str, who: dict | None, user: str, got: dict) -> None:
    """One audit row per search (sessions: accounts.sqlite's audit log;
    basic: a line in privacy.log beside the history). Never the value."""
    detail = words(got)
    if who is not None:
        from ..auth_api import open_db
        from ..accounts import auditlog
        db = open_db(config, live_dir)
        if db is not None:
            try:
                org = who.get("org")
                auditlog.record(db, org.get("id") if isinstance(org, dict) else org,
                                who.get("user_id") or "?", "people.search", site, detail)
            finally:
                db.close()
            return
    if live_dir is None:
        return
    from ..privacy import LOG
    line = (f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} people.search "
            f"site={site} by={(user or 'unknown')[:80]} {detail}\n")
    log = Path(live_dir) / LOG
    try:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(line)
        log.chmod(0o640)
    except OSError:
        pass
