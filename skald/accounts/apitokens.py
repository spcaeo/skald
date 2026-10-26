"""API tokens per organisation: the successor of skald/tokens.py.

Same token shape, `skald_<id>_<secret>`, and the same stored SHA-256 of the
whole token, so `import_json` moves tokens.json entries in and every token
already handed out keeps working. A token reads only sites of its own
organisation (and, if it names sites, only those). Scopes:

  read           the data files over /traffic-api/
  read_private   also the files that hold addresses (tokens.PRIVATE)
  mcp            the MCP endpoint
  ingest         post log lines to /traffic-ingest/<site> (ingest.py)
  setup          (2.39.0) the MCP tool setup_line: make a set-up line for an AI
                 agent. Reads nothing by itself (not even with read: the MCP
                 endpoint needs mcp too). Only an owner or admin of the
                 organisation (or the server: "cli") may make it, only for exactly
                 one site, and only together with mcp.

`private=True` is the old flag and means `read_private`. `check` writes
`last_used` at most once a minute per token.

`created_by` is the user id of the admin who made the token in the page, or
"cli" / "tokens.json" for one made on the server. A token made by a person
works only while that person is enabled and still an owner or admin of the
token's organisation: checked at every use (`creator_ok`), so removing or
demoting an admin stops the tokens they made at once, without revoking them.
"""
from __future__ import annotations

import hmac
import json
import secrets
from pathlib import Path

from .. import tokens as old_tokens
from . import auditlog
from . import db as base

SCOPES = ("read", "read_private", "mcp", "ingest", "setup")
PRIVATE = old_tokens.PRIVATE
DENIED = "unrecognised or revoked token"


def _entry(row: dict) -> dict:
    scopes = [s for s in (row["scopes"] or "").split(",") if s]
    return {"id": row["id"], "org_id": row["org_id"], "name": row["name"],
            "sites": json.loads(row["sites"]) if row["sites"] else None,
            "private": "read_private" in scopes, "scopes": scopes,
            "created_by": row["created_by"], "created_at": row["created_at"],
            "last_used": row["last_used"], "revoked_at": row["revoked_at"]}


def _scopes(scopes, private: bool) -> list[str]:
    got = [str(s) for s in (scopes or ())]
    bad = [s for s in got if s not in SCOPES]
    if bad:
        raise ValueError(f"A scope is one of: {', '.join(SCOPES)}.")
    if private and "read_private" not in got:
        got.append("read_private")
    if not got:
        raise ValueError("Give the token at least one scope.")
    return [s for s in SCOPES if s in got]


def creator_ok(db, org_id, created_by) -> bool:
    """False when a person made the token and is now disabled, gone, or no
    longer an owner or admin of `org_id`. Server-made tokens are always fine."""
    who = str(created_by or "")
    if not who.isdigit():
        return True
    row = db.execute("SELECT u.disabled_at, m.role FROM users u LEFT JOIN members m "
                     "ON m.user_id = u.id AND m.org_id = ? WHERE u.id = ?",
                     (org_id, int(who))).fetchone()
    return row is not None and not row[0] and row[1] in ("owner", "admin")


def _setup_ok(db, org_id, sites, scopes, actor) -> None:
    """The setup scope's rules (2.39.0), or ValueError in plain words."""
    if "setup" not in scopes:
        return
    if not creator_ok(db, org_id, actor):
        raise ValueError("Only an owner or admin may make a token that makes set-up lines.")
    if not sites or len(sites) != 1:
        raise ValueError("A token that makes set-up lines is for exactly one site: choose one.")
    if "mcp" not in scopes:
        raise ValueError("A token that makes set-up lines works through the MCP server: "
                         "give it the mcp scope too.")


def create(db, org_id, name, sites=None, private=False, scopes=("read",), actor="cli") -> str:
    """The token, to show once; only its hash is kept."""
    name = " ".join(str(name or "").split())[:60]
    if not name:
        raise ValueError("Give the token a name: what uses it.")
    scopes = _scopes(scopes, private)
    sites = sorted({str(s) for s in sites}) if sites else None
    with base.tx(db):
        if not db.execute("SELECT 1 FROM orgs WHERE id = ?", (org_id,)).fetchone():
            raise ValueError("There is no such organisation.")
        _setup_ok(db, org_id, sites, scopes, actor)
        own = {r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))}
        foreign = [s for s in sites or () if s not in own]
        if foreign:
            raise ValueError(f"Not a site of this organisation: {', '.join(foreign)}.")
        tid = secrets.token_hex(4)
        while db.execute("SELECT 1 FROM tokens WHERE id = ?", (tid,)).fetchone():
            tid = secrets.token_hex(4)
        token = f"skald_{tid}_{secrets.token_urlsafe(32)}"
        db.execute("INSERT INTO tokens (id, org_id, name, sha256, sites, private, scopes, "
                   "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (tid, org_id, name, base.sha256(token), json.dumps(sites) if sites else None,
                    int("read_private" in scopes), ",".join(scopes), str(actor), base.now()))
        auditlog.record(db, org_id, actor, "token.create", tid,
                        f"{name}; {','.join(scopes)}; {', '.join(sites or ['all sites'])}")
    return token


def check(db, header: str | None, site: str, scope="read",
          name=None) -> tuple[bool, str, dict | None]:
    """(allowed, why not, the token's entry) for an Authorization header."""
    if not header or not header.startswith("Bearer "):
        return False, "a bearer token is needed", None
    token = header[7:].strip()
    parts = token.split("_", 2)
    if len(parts) != 3 or parts[0] != "skald" or len(token) > 200:
        return False, "not a token", None
    row = base.one(db, "SELECT * FROM tokens WHERE id = ?", (parts[1],))
    if row is None or not hmac.compare_digest(row["sha256"], base.sha256(token)):
        return False, DENIED, None
    if row["revoked_at"] or not creator_ok(db, row["org_id"], row["created_by"]):
        return False, DENIED, None
    entry = _entry(row)
    owner = db.execute("SELECT org_id FROM sites WHERE name = ?", (site,)).fetchone()
    if owner is None or owner[0] != entry["org_id"]:
        return False, "this token is not for that site", None
    if entry["sites"] and site not in entry["sites"]:
        return False, "this token is not for that site", None
    if scope not in entry["scopes"]:
        return False, f"this token has no {scope} scope", None
    if name in PRIVATE and "read_private" not in entry["scopes"]:
        return False, f"{name} holds addresses; this token may not read it", None
    stamp = base.now()
    if not row["last_used"] or row["last_used"] <= base.shift(-60):
        db.execute("UPDATE tokens SET last_used = ? WHERE id = ?", (stamp, row["id"]))
        entry["last_used"] = stamp
    return True, "", entry


def revoke(db, org_id, token_id, actor) -> None:
    tid = str(token_id or "").removeprefix("skald_").split("_", 1)[0]
    with base.tx(db):
        row = base.one(db, "SELECT name, revoked_at FROM tokens WHERE id = ? AND org_id = ?",
                       (tid, org_id))
        if row is None:
            raise ValueError(f"There is no token {tid} in this organisation.")
        if not row["revoked_at"]:
            db.execute("UPDATE tokens SET revoked_at = ? WHERE id = ?", (base.now(), tid))
        auditlog.record(db, org_id, actor, "token.revoke", tid, row["name"])


def listing(db, org_id) -> list[dict]:
    """The organisation's tokens, newest first, revoked ones included."""
    return [_entry(r) for r in base.rows(
        db, "SELECT * FROM tokens WHERE org_id = ? ORDER BY created_at DESC, id", (org_id,))]


def import_json(db, path: Path, org_id, actor="cli") -> int:
    """Move tokens.json entries into the organisation; how many were added.
    Their stored hashes move as they are, so the tokens keep working.
    Ids already here are skipped, so running it twice adds nothing."""
    entries = old_tokens.load(Path(path))
    added = 0
    with base.tx(db):
        if not db.execute("SELECT 1 FROM orgs WHERE id = ?", (org_id,)).fetchone():
            raise ValueError("There is no such organisation.")
        for tid, e in sorted(entries.items()):
            if not isinstance(e, dict) or not e.get("sha256"):
                continue
            if db.execute("SELECT 1 FROM tokens WHERE id = ?", (str(tid),)).fetchone():
                continue
            private = bool(e.get("private"))
            scopes = ["read", "read_private"] if private else ["read"]
            sites = e.get("sites") or None
            db.execute("INSERT INTO tokens (id, org_id, name, sha256, sites, private, scopes, "
                       "created_by, created_at, revoked_at) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (str(tid), org_id, str(e.get("name") or tid)[:60], str(e["sha256"]),
                        json.dumps(list(sites)) if sites else None, int(private),
                        ",".join(scopes), "tokens.json", e.get("created_at") or base.now(),
                        e.get("revoked_at")))
            added += 1
        if added:
            auditlog.record(db, org_id, actor, "token.import", str(path), f"{added} tokens")
    return added
