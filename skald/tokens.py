"""Read-only API tokens: `skald token create|list|revoke`.

A token reads the data files over `/traffic-api/v1/<site>/[<view>/]<name>`
(docs/API.md) with `Authorization: Bearer <token>`, without the dashboard
password - for a script or another tool. It can never change anything.

Only a hash is kept (`access.tokens`, default tokens.json beside the
history, 0640): {"tokens": {id: {"name", "sha256", "created_at", "sites"
(null = all), "private" (may read requests.json and ai_activity.json, which
hold addresses), "revoked_at"}}}. The token itself is printed once, at
create, and is `skald_<id>_<secret>`.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from .files import own_like_folder, write_atomic

# Need the private flag (read_private): they hold addresses. "people" is the
# person lookup (people/api.py, 2.4.0), not a file.
PRIVATE = ("requests", "ai_activity", "people")


def path_for(config: dict, live_dir) -> Path | None:
    raw = ((config or {}).get("access") or {}).get("tokens")
    if raw:
        return Path(str(raw))
    return Path(live_dir) / "tokens.json" if live_dir is not None else None


def load(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        got = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    tokens = got.get("tokens") if isinstance(got, dict) else None
    return tokens if isinstance(tokens, dict) else {}


def _save(path: Path, tokens: dict) -> None:
    write_atomic(Path(path), json.dumps({"tokens": tokens}, indent=1, sort_keys=True) + "\n")
    os.chmod(path, 0o640)
    own_like_folder(path)


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create(path: Path, name: str, sites=None, private: bool = False) -> str:
    tokens = load(path)
    tid = secrets.token_hex(4)
    while tid in tokens:
        tid = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    token = f"skald_{tid}_{secret}"
    tokens[tid] = {"name": name[:60], "sha256": _digest(token),
                   "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "sites": list(sites) if sites else None, "private": bool(private),
                   "revoked_at": None}
    _save(path, tokens)
    return token


def check(path: Path | None, header: str | None, site: str, name: str) -> tuple[bool, str]:
    """(allowed, why) for an Authorization header reading `name` of `site`."""
    if not header or not header.startswith("Bearer "):
        return False, "a bearer token is needed"
    token = header[7:].strip()
    parts = token.split("_", 2)
    if len(parts) != 3 or parts[0] != "skald":
        return False, "not a token"
    entry = load(path).get(parts[1])
    if not entry or entry.get("revoked_at"):
        return False, "unrecognised or revoked token"
    if not hmac.compare_digest(entry.get("sha256", ""), _digest(token)):
        return False, "unrecognised or revoked token"
    if entry.get("sites") and site not in entry["sites"]:
        return False, "this token is not for that site"
    if name in PRIVATE and not entry.get("private"):
        return False, f"{name} holds addresses; this token may not read it"
    return True, ""


def cmd_token(ctx) -> int:
    if ((ctx.config or {}).get("access") or {}).get("mode") == "sessions":
        from .cli_accounts import cmd_token_sessions      # tokens live in the accounts file
        return cmd_token_sessions(ctx)
    a = ctx.args
    path = path_for(ctx.config, ctx.live_dir)
    if a.action == "create":
        scopes = set(getattr(a, "scope", None) or ())
        if scopes - {"read", "read_private"}:
            ctx.err("--scope mcp, ingest, setup and add_sites need accounts (access.mode: sessions); "
                    "in basic mode a token reads, and --private (or --scope read_private) "
                    "adds addresses")
            return 2
        a.private = a.private or "read_private" in scopes
        if not a.name:
            ctx.err("give the token a name: what uses it")
            return 2
        token = create(path, a.name, a.site or None, a.private)
        ctx.out(f"{token}\n(shown once; only its hash is kept. Use it as "
                f"'Authorization: Bearer <token>'.)")
        return 0
    tokens = load(path)
    if a.action == "list":
        for tid, e in sorted(tokens.items(), key=lambda kv: kv[1].get("created_at", "")):
            state = f"revoked {e['revoked_at']}" if e.get("revoked_at") else "active"
            ctx.out(f"{tid}  {e.get('name', ''):<24} {', '.join(e.get('sites') or ['all sites'])}"
                    f"{'  +addresses' if e.get('private') else ''}  {state}")
        if not tokens:
            ctx.out("no tokens")
        return 0
    tid = (a.name or "").removeprefix("skald_").split("_", 1)[0]
    if tid not in tokens:
        ctx.err(f"no token {tid}")
        return 1
    tokens[tid]["revoked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _save(path, tokens)
    ctx.out(f"revoked {tid} ({tokens[tid].get('name')})")
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("token", help="API tokens: read the data, the MCP endpoint, or ship "
                       "a site's log (docs/API.md, docs/INGEST.md)")
    p.add_argument("action", choices=("create", "list", "revoke"))
    p.add_argument("name", nargs="?", help="create: what uses it; revoke: its id")
    p.add_argument("--site", action="append", help="only this site (repeatable)")
    p.add_argument("--private", action="store_true",
                   help="may also read requests.json and ai_activity.json (addresses)")
    p.add_argument("--org", metavar="SLUG",
                   help="sessions mode: the organisation (needed when there are several)")
    p.add_argument("--scope", action="append", metavar="SCOPE",
                   help="read (default), read_private (addresses too), mcp (the MCP "
                        "endpoint), ingest (post log lines for the --site it names: "
                        "skald-ship, log drains), setup (the MCP tool setup_line: "
                        "set-up lines for an AI agent; one --site, with mcp) or add_sites "
                        "(the MCP tool add_site: add sites to the organisation within its "
                        "plan; no --site, with mcp); repeatable. mcp, ingest, setup and "
                        "add_sites need sessions mode")
    p.set_defaults(run=cmd_token)
