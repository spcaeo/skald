"""One-time install links: `curl -fsSL <base>/traffic-kit/<code> | sudo bash`.

`POST <page>/sites/link` (kit_api.py) makes a sending token for the site and a
random code (32 bytes, URL-safe), and keeps here, in kit-links.json beside the
history (0600, written under a lock, expired entries dropped on each write):

    {"links": {sha256(code): {"site", "made_at", "expires_at" (Unix seconds),
               "token_id", "sealed", "used_at", "fields"}}}

`sealed` is the token XORed with a keystream made from the code
(HMAC-SHA256(code, counter)); the code itself is never kept, so the disk never
holds a usable token. `fields` are the installer's other values (send address,
dashboard, help, image, shipper path): nothing secret.

`GET /traffic-kit/<code>` reaches the beacon helper (beacon_server.py, `serve`):

  * curl or Wget, the code valid: 200, the one-file installer with the token
    inside, and the code is burned (used_at set, `sealed` wiped)
  * curl or Wget, the code used, expired or unknown: 200, a tiny shell script
    that says so and exits 1 (a 410 would make `curl -f` print only its own
    error, so `| sudo bash` would never show the words)
  * anything else (a mail's link preview, a browser): the words "Run this on
    your server: ..." while the code is valid, else 410 in words; never burned
  * HEAD: the status only, never burned

Cache-Control no-store and X-Robots-Tag noindex on every answer, a limit per
caller address (in memory), and the code and the token are never logged.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..files import own_like_folder

FILE = "kit-links.json"
PREFIX = "/traffic-kit/"
HOURS = 24
CODE = re.compile(r"^[A-Za-z0-9_-]{43}$")
FIELDS = ("url", "dashboard", "help", "image", "ship_path", "base")
AGENTS = ("curl/", "wget/")


def path_for(folder) -> Path:
    return Path(folder) / FILE


def stamp(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------- sealing

def _stream(code: str, size: int) -> bytes:
    out, n = b"", 0
    while len(out) < size:
        out += hmac.new(code.encode(), b"skald-kit-link" + n.to_bytes(4, "big"),
                        hashlib.sha256).digest()
        n += 1
    return out[:size]


def seal(token: str, code: str) -> str:
    raw = token.encode()
    return base64.b64encode(bytes(a ^ b for a, b in zip(raw, _stream(code, len(raw))))).decode()


def unseal(sealed: str, code: str) -> str:
    raw = base64.b64decode(sealed)
    return bytes(a ^ b for a, b in zip(raw, _stream(code, len(raw)))).decode("utf-8", "replace")


def digest(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


# --------------------------------------------------------------- store

@contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path.with_name(f".{path.name}.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _load(path: Path) -> dict:
    try:
        got = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return {}
    links = got.get("links") if isinstance(got, dict) else None
    return links if isinstance(links, dict) else {}


def _save(path: Path, links: dict, now: float) -> None:
    """Written 0600 and renamed into place; expired entries dropped."""
    links = {k: v for k, v in links.items() if float(v.get("expires_at") or 0) > now}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"links": links}, indent=1, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    own_like_folder(path)


def make(folder, site: str, token: str, token_id: str, fields: dict,
         now: float | None = None, hours: int = HOURS) -> tuple[str, float]:
    """(the code, when it expires). Only the code's hash and the sealed token are kept."""
    now = time.time() if now is None else now
    code = secrets.token_urlsafe(32)
    path = path_for(folder)
    with _locked(path):
        links = _load(path)
        links[digest(code)] = {
            "site": site, "made_at": int(now), "expires_at": int(now + hours * 3600),
            "token_id": token_id, "sealed": seal(token, code), "used_at": None,
            "fields": {k: str(fields.get(k) or "") for k in FIELDS}}
        _save(path, links, now)
    return code, int(now + hours * 3600)


def look(folder, code: str, now: float | None = None) -> tuple[str, dict | None]:
    """("ok" | "gone" | "unknown", the entry): nothing is changed."""
    now = time.time() if now is None else now
    if not CODE.match(code or ""):
        return "unknown", None
    entry = _load(path_for(folder)).get(digest(code))
    if entry is None:
        return "unknown", None
    if entry.get("used_at") or not entry.get("sealed") or float(entry["expires_at"]) <= now:
        return "gone", entry
    return "ok", entry


def take(folder, code: str, now: float | None = None) -> tuple[str, dict | None, str | None]:
    """(state, entry, token): the token once, then the code is burned."""
    now = time.time() if now is None else now
    if not CODE.match(code or ""):
        return "unknown", None, None
    path = path_for(folder)
    if not path.exists():
        return "unknown", None, None
    with _locked(path):
        links = _load(path)
        key = digest(code)
        entry = links.get(key)
        if entry is None:
            return "unknown", None, None
        if entry.get("used_at") or not entry.get("sealed") or float(entry["expires_at"]) <= now:
            return "gone", entry, None
        token = unseal(entry["sealed"], code)
        entry.update(used_at=int(now), sealed=None)
        _save(path, links, now)
    return "ok", entry, token


# ---------------------------------------------------------------- serve

def gone_words(dashboard: str) -> str:
    where = f": {dashboard}" if dashboard else " (Settings > Connections)"
    return f"This install link was used or has expired. Make a new one in Skald{where}"


def _answer(h, code: int, body: str, kind: str = "text/plain; charset=utf-8") -> None:
    data = body.encode("utf-8")
    h.send_response(code)
    for k, v in (("Content-Type", kind), ("Cache-Control", "no-store"),
                 ("X-Robots-Tag", "noindex, nofollow"), ("X-Content-Type-Options", "nosniff"),
                 ("Content-Length", str(len(data)))):
        h.send_header(k, v)
    h.end_headers()
    if h.command != "HEAD":
        h.wfile.write(data)


def serve(h, folder, base: str, limiter, address: str) -> None:
    """Answer GET or HEAD /traffic-kit/<code> on the beacon helper's handler.
    `base`: the install's address, for the words when the link is unknown."""
    from . import one_file
    if not limiter.allow(address):
        return _answer(h, 429, "Too many tries. Wait a minute and try again.\n")
    code = h.path.split("?", 1)[0][len(PREFIX):]
    tool = (h.headers.get("User-Agent") or "").lower().startswith(AGENTS)
    burn = tool and h.command == "GET"
    if burn:
        state, entry, token = take(folder, code)
    else:
        (state, entry), token = look(folder, code), None
    fields = (entry or {}).get("fields") or {}
    dashboard = fields.get("dashboard") or (f"{base.rstrip('/')}/traffic/" if base else "")
    if state != "ok":
        words = gone_words(dashboard)
        if tool:
            return _answer(h, 200, f"#!/bin/sh\necho \"{words}\" >&2\nexit 1\n")
        return _answer(h, 410, words + "\n")
    if not burn:
        link = f"{(fields.get('base') or base or '').rstrip('/')}{PREFIX}{code}"
        return _answer(h, 200, f"Run this on your server:\n\n  curl -fsSL {link} | sudo bash\n\n"
                               "The link works once, for 24 hours.\n")
    try:
        data = one_file(entry["site"], fields["url"], fields["dashboard"], fields["help"],
                        fields.get("image") or None, fields.get("ship_path") or None, token)
    except (ValueError, KeyError, OSError):
        return _answer(h, 500, "#!/bin/sh\necho \"The installer could not be made. Make a new "
                               "link in Skald.\" >&2\nexit 1\n")
    return _answer(h, 200, data.decode("utf-8"))
