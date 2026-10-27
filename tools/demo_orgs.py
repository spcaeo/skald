"""Settings > Organisation > Organisations in the demo (tools/demo.py): the answers the
helper would give (orgs_api.py: GET orgs, orgs/show?org=, orgs/auditlog?org=) for three
sample organisations, written beside the page as data/demo/orgs-*.json.

  1  Example Co            internal, the demo's own site (example.com); its figures come
                           from the demo's history by the same code as the helper's
                           (org_figures.recent, checked by audit_orgs.recount)
  2  Sample Client Studio  client, two sites the demo does not hold: its figures are
                           Not recorded, never 0
  3  Old Agency            archived: its one site paused, nothing deleted

Every person is made up, at example.com, example.org or example.net; no token's value is
kept anywhere, as on a real install."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


def _shapes(now: datetime, site: str, figures: dict) -> tuple[dict, dict, dict]:
    day = lambda n: (now - timedelta(days=n)).isoformat(timespec="seconds")
    cards = [
        {"id": 1, "name": "Example Co", "slug": "example-co", "sites": [site], "members": 3, "plan": None,
         "privacy_class": "internal", "state": "active", "created_at": day(140), "archived_at": None,
         "role": "owner", "path": f"{site}/"},
        {"id": 2, "name": "Sample Client Studio", "slug": "sample-client-studio",
         "sites": ["shop.example.org", "blog.example.org"], "members": 2, "plan": None,
         "privacy_class": "client", "state": "active", "created_at": day(33), "archived_at": None,
         "role": None, "path": None},
        {"id": 3, "name": "Old Agency", "slug": "old-agency", "sites": ["old.example.net"], "members": 1,
         "plan": None, "privacy_class": "internal", "state": "archived", "created_at": day(400),
         "archived_at": day(12), "role": None, "path": None},
    ]
    member = lambda i, email, name, role, sites, seen, totp, me=False: {
        "id": i, "email": email, "name": name, "role": role, "sites": sites, "added_at": day(100),
        "last_seen": day(seen) if seen is not None else None, "totp_on": totp, "disabled_at": None,
        "has_password": True, "me": me}
    members = {
        1: [member(1, "owner@example.com", "Sam Owner", "owner", None, 0, True, True),
            member(2, "admin@example.com", "Alex Admin", "admin", None, 1, True),
            member(3, "viewer@example.com", "Vic Viewer", "viewer", [site], 6, False)],
        2: [member(4, "lead@example.org", "Lee Client", "owner", None, 2, True),
            member(5, "analyst@example.org", "Ana Lyst", "viewer", ["shop.example.org"], 9, False)],
        3: [member(6, "founder@example.net", "Fay Founder", "owner", None, 40, False)],
    }
    tokens = {1: [
        {"id": "3", "name": "Weekly sheet", "scopes": ["read"], "sites": [site], "private": False,
         "created_by": "1", "created_at": day(41), "last_used": day(1), "revoked_at": None},
        {"id": "5", "name": "Claude Desktop", "scopes": ["mcp"], "sites": [site], "private": False,
         "created_by": "1", "created_at": day(19), "last_used": day(0), "revoked_at": None},
        {"id": "7", "name": "Web server shipper", "scopes": ["ingest"], "sites": [site], "private": False,
         "created_by": "2", "created_at": day(9), "last_used": day(0), "revoked_at": None}]}
    invites = {1: [{"email": "new.hire@example.com", "role": "viewer", "invited_by": 2, "created_at": day(2),
                    "expires_at": day(-5), "sites": [site], "expired": False}],
               2: [{"email": "partner@example.org", "role": "admin", "invited_by": 4, "created_at": day(1),
                    "expires_at": day(-6), "sites": None, "expired": False}]}
    states = {1: {site: "active"}, 2: {"shop.example.org": "active", "blog.example.org": "active"},
              3: {"old.example.net": "paused"}}
    audit = {
        1: [("token.create", "1", "7", "Web server shipper", 9), ("member.sites", "1", "3", f"every site -> {site}", 6),
            ("member.role", "1", "2", "viewer -> admin", 30), ("org.create", "1", "1", "Example Co", 140)],
        2: [("invite.create", "4", "partner@example.org", "admin", 1), ("member.sites", "4", "5", "every site -> shop.example.org", 8),
            ("org.privacy", "1", "2", "internal -> client", 33), ("org.create", "1", "2", "Sample Client Studio", 33)],
        3: [("org.archive", "1", "3", "1 site paused: old.example.net", 12), ("org.create", "1", "3", "Old Agency", 400)],
    }
    emails = {str(m["id"]): m["email"] for ms in members.values() for m in ms}
    shows, logs = {}, {}
    for card in cards:
        oid, mine = card["id"], card["role"]
        admin = True                                       # the reader is an install admin
        shows[oid] = {
            "ok": True, "org": {k: v for k, v in card.items() if k != "path"}, "role": mine,
            "acts": "owner",
            "may": {"rename": admin, "privacy": True, "archive": True, "members": admin, "owners": True,
                    "sites_access": admin, "settings_totp": True, "settings_mail": admin, "keys": admin,
                    "audit": admin, "move": admin, "add_site": admin, "leave": mine is not None,
                    "transfer": mine == "owner"},
            "overview": {"sites": len(card["sites"]), "members": card["members"],
                         **(figures if oid == 1 else {"requests_7d": None, "last_day": None, "withheld": None})},
            "sites": [{"name": s, "path": f"{s}/", "state": states[oid][s]} for s in card["sites"]],
            "members": members[oid], "invites": invites.get(oid, []),
            "settings": {"require_totp": oid == 1, "session_days": None, "mail_daily": True},
            "keys": tokens.get(oid, []),
            "movable": [{"name": s, "org": c["name"], "org_id": c["id"]} for c in cards
                        if c["id"] != oid and c["state"] == "active" for s in c["sites"]],
            "install_keeps": True,
        }
        logs[oid] = {"ok": True, "entries": [
            {"id": 100 * oid + n, "at": day(ago), "org_id": oid, "actor": actor, "action": action,
             "target": target, "detail": detail, "actor_email": emails.get(actor)}
            for n, (action, actor, target, detail, ago) in enumerate(audit[oid])]}
    listing = {"ok": True, "orgs": cards, "install_admin": True, "current": 1, "can_create": True}
    return listing, shows, logs


def orgs_answers(root: Path, site_dir: Path, now: datetime, site: str) -> dict:
    """Writes the answers; returns {helper path: file} for app.json's demo.api.orgs."""
    from skald import org_figures
    figures = org_figures.recent(root / "history.sqlite", [site], now.date())
    listing, shows, logs = _shapes(now, site, figures)
    folder = site_dir / "data" / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    out = {}

    def put(key: str, name: str, body: dict) -> None:
        (folder / name).write_text(json.dumps(body, separators=(",", ":")))
        out[key] = f"data/demo/{name}"

    put("orgs", "orgs.json", listing)
    for oid, body in shows.items():
        put(f"orgs/show?org={oid}", f"orgs-show-{oid}.json", body)
        put(f"orgs/auditlog?org={oid}", f"orgs-audit-{oid}.json", logs[oid])
    return out
