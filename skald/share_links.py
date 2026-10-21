"""Private links that hand one set-up task to a web developer, no sign-in
needed: "Share with your developer" in Settings > Connections, Add a site and
the Set up dialogs. The page they open is share_api.py's.

A link is `<base>/traffic-auth/setup/<id>`, the id 22 random URL-safe
characters (128 bits). Only its SHA-256 is kept, in accounts.sqlite
(`share_links`, CREATE TABLE IF NOT EXISTS on first use), with:

    ref         8 hex characters naming the link in lists and the audit log
    org_id, site, task ("send", "script" or "hook"), method (send: docker,
                systemd, cloudflare or vercel; hook: the tool, e.g. lead)
    created_by, created_at, expires_at (1, 7 or 30 days), revoked_at, revoked_by
    viewed_at (first), views, revealed_at, secret_ref (the token id or hook)

The secret: nothing secret is stored for a link. Its token (send) or hook
secret (hook) is made only when the developer presses "Show the secret", at
most once per link: a new sending token for that one site, made in the name
of the admin who made the link (so it stops if that admin is removed), or a
new hook secret for that tool (an older one for it stops working then). A
script-tag link has no secret. After the reveal the page says it was shown
and asks for a new link.

Every create, view, reveal and revoke is an audit row. No address, user agent
or secret is written anywhere.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from .accounts import auditlog
from .accounts import db as base

TABLE = ("CREATE TABLE IF NOT EXISTS share_links (id_hash TEXT PRIMARY KEY, ref TEXT NOT NULL "
         "UNIQUE, org_id INTEGER NOT NULL, site TEXT NOT NULL, task TEXT NOT NULL, method TEXT, "
         "created_by TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, "
         "revoked_at TEXT, revoked_by TEXT, viewed_at TEXT, views INTEGER NOT NULL DEFAULT 0, "
         "revealed_at TEXT, secret_ref TEXT)")
TASKS = ("send", "script", "hook")
SEND_METHODS = ("docker", "systemd", "cloudflare", "vercel")
DAYS = (1, 7, 30)
ID_CHARS = 22
GONE = "This link has expired or was revoked. Ask for a new one."


def ensure(db) -> None:
    db.execute(TABLE)


def digest(link_id: str) -> str:
    return hashlib.sha256(str(link_id).encode()).hexdigest()


def _stamp(dt: datetime) -> str:
    return dt.strftime(base.STAMP)


def _entry(row) -> dict:
    d = dict(row)
    d.pop("id_hash", None)
    now = base.now()
    d["state"] = "revoked" if d["revoked_at"] else "expired" if d["expires_at"] <= now \
        else "shown" if d["revealed_at"] else "open"
    return d


def create(db, org_id, site: str, task: str, actor, method: str | None = None,
           days: int = 7) -> tuple[str, dict]:
    """(the link's id, to show once, its entry); ValueError in plain words."""
    from .conversions import TOOLS
    if task not in TASKS:
        raise ValueError(f"A task is one of: {', '.join(TASKS)}.")
    if task == "send" and method not in SEND_METHODS:
        raise ValueError(f"A way to send is one of: {', '.join(SEND_METHODS)}.")
    if task == "hook" and method not in TOOLS:
        raise ValueError("Choose the tool the leads come from.")
    if task == "script":
        method = None
    try:
        days = int(days)
    except (TypeError, ValueError):
        days = 0
    if days not in DAYS:
        raise ValueError("A link lasts 1, 7 or 30 days.")
    ensure(db)
    link_id = secrets.token_urlsafe(16)[:ID_CHARS]
    ref = secrets.token_hex(4)
    now = datetime.strptime(base.now(), base.STAMP).replace(tzinfo=timezone.utc)
    with base.tx(db):
        while db.execute("SELECT 1 FROM share_links WHERE ref = ?", (ref,)).fetchone():
            ref = secrets.token_hex(4)
        db.execute("INSERT INTO share_links (id_hash, ref, org_id, site, task, method, created_by, "
                   "created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (digest(link_id), ref, org_id, site, task, method, str(actor), _stamp(now),
                    _stamp(now + timedelta(days=days))))
        auditlog.record(db, org_id, actor, "share.create", f"{site}/{task}",
                        f"{ref}; {method or '-'}; {days} days")
    return link_id, get_ref(db, ref)


def get_ref(db, ref: str) -> dict | None:
    ensure(db)
    row = db.execute("SELECT * FROM share_links WHERE ref = ?", (str(ref),)).fetchone()
    return _entry(row) if row is not None else None


def find(db, link_id: str) -> dict | None:
    """The link's entry when it is usable (not expired, not revoked), else None."""
    if not isinstance(link_id, str) or len(link_id) != ID_CHARS:
        return None
    ensure(db)
    row = db.execute("SELECT * FROM share_links WHERE id_hash = ?", (digest(link_id),)).fetchone()
    if row is None:
        return None
    got = _entry(row)
    return got if got["state"] in ("open", "shown") else None


def viewed(db, entry: dict) -> None:
    with base.tx(db):
        db.execute("UPDATE share_links SET views = views + 1, viewed_at = COALESCE(viewed_at, ?) "
                   "WHERE ref = ?", (base.now(), entry["ref"]))
        auditlog.record(db, entry["org_id"], f"link:{entry['ref']}", "share.view",
                        f"{entry['site']}/{entry['task']}", entry["ref"])


def claim_reveal(db, entry: dict) -> bool:
    """Mark the secret shown; False when it was shown before (or never may be)."""
    if entry["task"] == "script":
        return False
    with base.tx(db):
        done = db.execute("UPDATE share_links SET revealed_at = ? WHERE ref = ? AND "
                          "revealed_at IS NULL AND revoked_at IS NULL AND expires_at > ?",
                          (base.now(), entry["ref"], base.now())).rowcount
        if done:
            auditlog.record(db, entry["org_id"], f"link:{entry['ref']}", "share.reveal",
                            f"{entry['site']}/{entry['task']}", entry["ref"])
    return bool(done)


def note_secret(db, ref: str, secret_ref: str) -> None:
    db.execute("UPDATE share_links SET secret_ref = ? WHERE ref = ?", (secret_ref, ref))


def revoke(db, org_id, ref: str, actor) -> dict:
    ensure(db)
    with base.tx(db):
        got = get_ref(db, ref)
        if got is None or got["org_id"] != org_id:
            raise ValueError("There is no such link in this organisation.")
        if not got["revoked_at"]:
            db.execute("UPDATE share_links SET revoked_at = ?, revoked_by = ? WHERE ref = ?",
                       (base.now(), str(actor), got["ref"]))
        auditlog.record(db, org_id, actor, "share.revoke", f"{got['site']}/{got['task']}",
                        got["ref"])
    return get_ref(db, ref)


def listing(db, org_id) -> list[dict]:
    """The organisation's links, newest first, ended ones included."""
    ensure(db)
    return [_entry(r) for r in db.execute(
        "SELECT * FROM share_links WHERE org_id = ? ORDER BY created_at DESC, ref", (org_id,))]
