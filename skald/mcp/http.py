"""MCP over HTTP: POST /traffic-mcp on the refresh helper (Streamable HTTP,
one JSON answer per POST, no event stream, no session id).

    handle_http(handler, config, live_dir, out_dir, token_checker=None,
                history_path=None, allowed_origins=(), config_path=None,
                setup_checker=None)

`handler` is the helper's BaseHTTPRequestHandler. The rules, in order:

  * off unless `mcp: {enabled: true}` in the config: 404
  * POST only: anything else is 405 (Allow: POST) - no event stream is offered
  * an Origin header, when a browser sends one, must be one of
    `allowed_origins` (the helper's --origin list): 403 otherwise. Agents
    send none. (DNS rebinding: MCP spec, Transports, Security Warning.)
  * MCP-Protocol-Version, when sent, is one we know: 400 otherwise
  * Authorization: Bearer <token>, a token with the "mcp" scope: 401 with
    WWW-Authenticate: Bearer otherwise
  * a body of at most 64 KiB (413), JSON (400 with a -32700 error)
  * a body with only notifications or responses: 202, no body; else 200
    with Content-Type: application/json

The token is then checked again for each site a tool reads:
`token_checker(authorization, site) -> (allowed, why, may_read_addresses)`;
`site` None asks only "is this a valid token with the mcp scope". The
default checker reads the organisation tokens in accounts.sqlite
(accounts/apitokens.py), so it needs `access: {mode: sessions}`.

`setup_checker(authorization, site) -> (allowed, why, token entry)` (2.39.0):
the same token with the setup scope for that site, for the setup_line tool.
The default reads accounts.sqlite too; with a `token_checker` given and no
`setup_checker`, no call may make a set-up line.
"""
from __future__ import annotations

import hmac
import json
from pathlib import Path

from . import protocol
from .data import Context

MAX_BODY = 64 * 1024
PATH = "/traffic-mcp"
NO_ACCOUNTS = "MCP needs accounts (access.mode: sessions) and a token with the mcp scope"


def enabled(config: dict | None) -> bool:
    return bool(((config or {}).get("mcp") or {}).get("enabled"))


def is_mcp(path: str) -> bool:
    return path.split("?", 1)[0].rstrip("/") == PATH


def accounts_checker(config: dict | None, live_dir):
    """The default token check: organisation tokens in accounts.sqlite."""
    from ..accounts import apitokens
    from ..accounts import db as base
    path = base.path_for(config or {}, live_dir)
    mode = ((config or {}).get("access") or {}).get("mode")

    def check(header, site):
        if mode != "sessions" or path is None or not Path(path).is_file():
            return False, NO_ACCOUNTS, False
        db = base.connect(path)
        try:
            if site is None:
                return _valid(db, header)
            ok, why, entry = apitokens.check(db, header, site, scope="mcp")
            return ok, why, bool(ok and entry and "read_private" in entry["scopes"])
        finally:
            db.close()
    return check


def accounts_setup(config: dict | None, live_dir):
    """The setup scope's check (2.39.0): organisation tokens in accounts.sqlite."""
    from ..accounts import apitokens
    from ..accounts import db as base
    path = base.path_for(config or {}, live_dir)
    mode = ((config or {}).get("access") or {}).get("mode")

    def check(header, site):
        if mode != "sessions" or path is None or not Path(path).is_file():
            return False, NO_ACCOUNTS, None
        db = base.connect(path)
        try:
            ok, why, entry = apitokens.check(db, header, site, scope="setup")
            return ok, why, entry if ok else None
        finally:
            db.close()
    return check


def origin_of(handler, config: dict | None) -> str:
    """This install's address as integrations_api._origin says it:
    hooks.public_url, access.base_url, else the request's own host."""
    from ..config import setting
    for got in (setting(config or {}, "hooks", "public_url"),
                setting(config or {}, "access", "base_url")):
        if got:
            return str(got).rstrip("/")
    proto = handler.headers.get("X-Forwarded-Proto") or "https"
    return f"{proto}://{handler.headers.get('Host') or 'localhost'}"


def _valid(db, header) -> tuple[bool, str, bool]:
    """A real, unrevoked token with the mcp scope, whatever site it reads."""
    from ..accounts import apitokens
    from ..accounts import db as base
    if not header or not header.startswith("Bearer "):
        return False, "a bearer token is needed", False
    token = header[7:].strip()
    parts = token.split("_", 2)
    if len(parts) != 3 or parts[0] != "skald" or len(token) > 200:
        return False, "not a token", False
    row = base.one(db, "SELECT org_id, sha256, scopes, created_by, revoked_at FROM tokens "
                       "WHERE id = ?", (parts[1],))
    if row is None or not hmac.compare_digest(row["sha256"], base.sha256(token)) or \
            row["revoked_at"] or not apitokens.creator_ok(db, row["org_id"], row["created_by"]):
        return False, apitokens.DENIED, False
    if "mcp" not in (row["scopes"] or "").split(","):
        return False, "this token has no mcp scope", False
    return True, "", False


def _send(handler, code: int, body=None, headers: dict | None = None) -> None:
    data = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
    handler.send_response(code)
    if body is not None:
        handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    for k, v in (headers or {}).items():
        handler.send_header(k, v)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    if data:
        handler.wfile.write(data)


def _refuse(handler, code: int, why: str, headers: dict | None = None) -> None:
    _send(handler, code, protocol.error(None, protocol.INVALID_REQUEST, why), headers)


def handle_http(handler, config, live_dir, out_dir, token_checker=None, history_path=None,
                allowed_origins=(), config_path=None, setup_checker=None) -> None:
    """Answer one request to /traffic-mcp, whatever its method."""
    if not enabled(config):
        return _send(handler, 404, {"ok": False, "error": "MCP is not switched on here"})
    if handler.command != "POST":
        return _send(handler, 405, {"ok": False, "error": "POST only: this server sends "
                                    "plain JSON answers, no event stream"}, {"Allow": "POST"})
    origin = handler.headers.get("Origin")
    allowed = {str(o).rstrip("/") for o in allowed_origins or ()}
    if origin is not None and origin.rstrip("/") not in allowed:
        return _refuse(handler, 403, "Forbidden: this Origin may not call the MCP server")
    asked = handler.headers.get("MCP-Protocol-Version")
    if asked is not None and asked.strip() not in protocol.SUPPORTED:
        return _refuse(handler, 400, f"Bad Request: unsupported MCP-Protocol-Version "
                                     f"{asked!r}; supported: {', '.join(protocol.SUPPORTED)}")
    checker = token_checker or accounts_checker(config, live_dir)
    auth = handler.headers.get("Authorization")
    ok, why, _ = checker(auth, None)
    if not ok:
        return _send(handler, 401, protocol.error(None, protocol.INVALID_REQUEST,
                                                  f"Unauthorized: {why}"),
                     {"WWW-Authenticate": 'Bearer realm="skald", error="invalid_token"'})
    try:
        length = int(handler.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return _refuse(handler, 411, "Length Required: send Content-Length")
    if length > MAX_BODY:
        return _refuse(handler, 413, f"Payload Too Large: at most {MAX_BODY} bytes")
    kind = handler.headers.get("Content-Type") or "application/json"
    if "json" not in kind:
        return _refuse(handler, 415, "Unsupported Media Type: send application/json")
    raw = handler.rfile.read(length) if length else b""
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _send(handler, 400, protocol.error(None, protocol.PARSE_ERROR, "Parse error"))
    if setup_checker is None and token_checker is None:
        setup_checker = accounts_setup(config, live_dir)
    ctx = Context(out_dir, config=config, live_dir=live_dir, history_path=history_path,
                  checker=lambda site: checker(auth, site), config_path=config_path,
                  setup=(lambda site: setup_checker(auth, site)) if setup_checker else None,
                  allowed=allowed_origins, origin=origin_of(handler, config))
    answer = protocol.handle(message, ctx)
    if answer is None:
        return _send(handler, 202)
    return _send(handler, 200, answer)
