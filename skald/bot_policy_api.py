"""The AI crawler settings on the refresh helper (refresh_server.py).

  GET  <page>/bot-policy   every assistant and crawler with its mode, what is
                           blocked, the robots.txt suggestion, and the outcome
                           of the last apply to nginx
  POST <page>/bot-policy   {"owners": {assistant: mode}, "crawlers": {name: mode}}
                           as JSON: replaces the policy. Admins only (when the
                           helper knows roles; in sessions mode an install
                           admin), same-origin only, at most one save per
                           POLICY_GAP seconds.

The helper only writes the policy file (bot_policy.save). Root's systemd
path unit sees the change and runs bot_policy.py apply, which writes the
nginx map, tests it and reloads; the page reads the outcome from "applied".
"""
from __future__ import annotations

import json
import re
import threading
import time

from . import bot_policy

PATH = re.compile(r"^/traffic/[a-z0-9.-]+/(?:[a-z0-9-]+/)?bot-policy$")
MAX_BODY = 4096
POLICY_GAP = 2          # seconds between two saves

_lock = threading.Lock()
_last = {"at": None}


def is_policy(path: str) -> bool:
    path = path.split("?", 1)[0]
    return bool(PATH.match(path)) and ".." not in path


def answer(config: dict | None, policy: dict, **extra) -> dict:
    _, state = bot_policy.paths(config)
    return {"ok": "error" not in extra, **extra, "policy": policy, **bot_policy.view(policy),
            "applied": bot_policy.status(state)}


def handle(h, write: bool, config: dict | None, allowed: set[str], same_origin,
           clock=time.monotonic) -> None:
    """Answer one request on handler `h` (its _json writes the reply)."""
    if not same_origin(h.headers, allowed):
        return h._json(403, {"ok": False, "error": "same-origin requests only"})
    file, _ = bot_policy.paths(config)
    try:
        current = bot_policy.load(file)
        warning = None
    except (bot_policy.Invalid, OSError) as why:
        current, warning = bot_policy.empty(), f"stored policy unreadable: {why}"
    if not write:
        extra = {"warning": warning} if warning else {}
        return h._json(200, answer(config, current, **extra))
    # Admins only once the helper knows roles (refresh_server's _admin
    # answers 403 itself and returns None for anyone else). The policy is for
    # the whole server, so in sessions mode it takes an install admin.
    admin = getattr(h, "_admin", None)
    who = admin(install=True) if admin is not None else "page"
    if who is None:
        return None
    try:
        length = int(h.headers.get("Content-Length") or 0)
    except ValueError:
        length = -1
    if length <= 0 or length > MAX_BODY:
        return h._json(400, {"ok": False, "error": "send the policy as JSON, at most 4 KB"})
    try:
        data = json.loads(h.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return h._json(400, {"ok": False, "error": "the body is not JSON"})
    with _lock:
        now = clock()
        if _last["at"] is not None and now - _last["at"] < POLICY_GAP:
            return h._json(429, {"ok": False, "error": "saved a moment ago; try again"})
        try:
            policy = bot_policy.save(file, data, by=who)
        except bot_policy.Invalid as why:
            return h._json(400, answer(config, current, error=str(why)))
        except OSError:
            return h._json(500, answer(config, current, error="could not store the policy"))
        _last["at"] = now
    return h._json(200, answer(config, policy))
