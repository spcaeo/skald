"""Proving a site is yours before Skald collects for it, and holding a purged
site's name.

A site made by sign-up, or from Settings > Sites while saas is on, starts
"pending": a row in `site_verify` with a random token. Until it is
verified, nothing is collected for it: the ingest endpoint (ingest.py), the
hook receiver (conversions/hooks.py) and the beacon (beacon_server.py)
refuse it. A site with no row (every config-file site, and every site made
before this check existed) counts as verified.

It is verified, by the person in Settings > Sites (the Verify button) or by
`check` here, when either is found:

  * a DNS TXT record on the host: `skald-verify=<token>`, asked over UDP of
    the system resolver (/etc/resolv.conf's first nameserver)
  * `<meta name="skald-verify" content="<token>">` on https://<host>/,
    fetched with outgoing.get: the same client as the outgoing webhooks (no
    redirect, never a private address, a size and time limit)

An install admin can mark a site verified: `skald site verify NAME`.

`site purge` (sites_cli.py) reserves the purged name for REUSE_DAYS
(`site_purged`): neither sign-up, Settings > Sites nor `site add` may make it
again before then, unless the install admin passes `--allow-reuse`.

Both tables are made with CREATE TABLE IF NOT EXISTS on first use, outside
db.py's numbered schema, like site_configs.py's.
"""
from __future__ import annotations

import hmac
import ipaddress
import os
import secrets
import socket
import sqlite3
import struct
import threading
import time
from html.parser import HTMLParser
from pathlib import Path

from .accounts import auditlog
from .accounts import db as base

TABLES = (
    "CREATE TABLE IF NOT EXISTS site_verify (name TEXT PRIMARY KEY, token TEXT NOT NULL, "
    "created_at TEXT NOT NULL, verified_at TEXT, verified_by TEXT, method TEXT)",
    "CREATE TABLE IF NOT EXISTS site_purged (name TEXT PRIMARY KEY, purged_at TEXT NOT NULL, "
    "until TEXT NOT NULL, purged_by TEXT)")
REUSE_DAYS = 30
PREFIX = "skald-verify="
META = "skald-verify"
RESOLV = "/etc/resolv.conf"
DNS_SECONDS = 3.0
PAGE_BYTES = 65536
PAGE_SECONDS = 10.0
CACHE_SECONDS = 10.0
PENDING_WORDS = ("This site is waiting for its domain to be verified (Settings > Sites); "
                 "nothing is collected for it until then.")
RESERVED_WORDS = ("{name} was deleted on this server; its name is held until {until}. An "
                  "install admin can re-use it sooner with `skald site add --allow-reuse`.")


def ensure(db) -> None:
    for sql in TABLES:
        db.execute(sql)


# ------------------------------------------------------------- the state

def start(db, name: str) -> str:
    """Make `name` pending with a new token; the token."""
    ensure(db)
    token = secrets.token_hex(16)
    db.execute("INSERT INTO site_verify (name, token, created_at) VALUES (?, ?, ?) "
               "ON CONFLICT(name) DO UPDATE SET token = excluded.token, created_at = "
               "excluded.created_at, verified_at = NULL, verified_by = NULL, method = NULL",
               (str(name), token, base.now()))
    return token


def state(db, name: str) -> dict | None:
    """The site's row ({"name", "token", "verified_at", ...}), or None (no
    check: counts as verified)."""
    ensure(db)
    return base.one(db, "SELECT * FROM site_verify WHERE name = ?", (str(name),))


def pending(db, name: str) -> bool:
    got = state(db, name)
    return got is not None and not got["verified_at"]


def shown(db, name: str) -> dict | None:
    """What Settings > Sites shows: None for a site with no check."""
    got = state(db, name)
    if got is None:
        return None
    if got["verified_at"]:
        return {"state": "verified", "verified_at": got["verified_at"], "method": got["method"]}
    return {"state": "pending", "token": got["token"], "txt": PREFIX + got["token"],
            "meta": f'<meta name="{META}" content="{got["token"]}">'}


def mark(db, name: str, actor, method: str) -> bool:
    """Mark a pending site verified. False when it was not pending."""
    ensure(db)
    with base.tx(db):
        done = db.execute("UPDATE site_verify SET verified_at = ?, verified_by = ?, "
                          "method = ? WHERE name = ? AND verified_at IS NULL",
                          (base.now(), str(actor), method, str(name))).rowcount
        if done:
            org = db.execute("SELECT org_id FROM sites WHERE name = ?", (str(name),)).fetchone()
            auditlog.record(db, org[0] if org else None, actor, "site.verify", str(name),
                            method)
    clear_cache()
    return bool(done)


def forget(db, name: str) -> None:
    ensure(db)
    db.execute("DELETE FROM site_verify WHERE name = ?", (str(name),))
    clear_cache()


# ------------------------------------------------------- held names

def reserve(db, name: str, actor, days: int = REUSE_DAYS) -> str:
    """Hold a purged name for `days`; the end, as a stamp."""
    ensure(db)
    until = base.shift(days * 86400)
    db.execute("INSERT INTO site_purged (name, purged_at, until, purged_by) VALUES (?,?,?,?) "
               "ON CONFLICT(name) DO UPDATE SET purged_at = excluded.purged_at, "
               "until = excluded.until, purged_by = excluded.purged_by",
               (str(name), base.now(), until, str(actor)))
    return until


def reserved_until(db, name: str) -> str | None:
    ensure(db)
    row = db.execute("SELECT until FROM site_purged WHERE name = ? AND until > ?",
                     (str(name), base.now())).fetchone()
    return row[0] if row else None


def refuse_reserved(db, name: str, allow_reuse: bool = False) -> None:
    """ValueError while the name is held; with allow_reuse the hold ends."""
    until = reserved_until(db, name)
    if until is None:
        return
    if allow_reuse:
        db.execute("DELETE FROM site_purged WHERE name = ?", (str(name),))
        return
    raise ValueError(RESERVED_WORDS.format(name=name, until=until[:10]))


# ------------------------------------------- collecting (hot paths)

_CACHE: dict = {}
_GUARD = threading.Lock()


def clear_cache() -> None:
    with _GUARD:
        _CACHE.clear()


def refuses(config: dict, folder, site: str) -> bool:
    """True when `site` is pending in the install's accounts file (beside
    the history in `folder`): its hooks and beacon events are refused.
    Read-only, cached CACHE_SECONDS; no accounts file means False."""
    path = base.path_for(config or {}, Path(folder) if folder is not None else None)
    if path is None:
        return False
    key = (str(path), str(site))
    now = time.monotonic()
    with _GUARD:
        got = _CACHE.get(key)
        if got is not None and now - got[0] < CACHE_SECONDS:
            return got[1]
    value = False
    if Path(path).is_file():
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            try:
                row = db.execute("SELECT verified_at FROM site_verify WHERE name = ?",
                                 (str(site),)).fetchone()
                value = row is not None and not row[0]
            finally:
                db.close()
        except sqlite3.Error:
            value = False                 # no table yet: no site is pending
    with _GUARD:
        _CACHE[key] = (now, value)
    return value


# ------------------------------------------------------------- DNS TXT

def nameservers(text: str | None = None) -> list[str]:
    """The nameserver addresses in resolv.conf (its text, or the file)."""
    if text is None:
        try:
            text = Path(RESOLV).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
    out = []
    for raw in text.splitlines():
        parts = raw.split("#", 1)[0].split()
        if len(parts) >= 2 and parts[0] == "nameserver":
            try:
                out.append(str(ipaddress.ip_address(parts[1].split("%", 1)[0])))
            except ValueError:
                continue
    return out


def _query(host: str, ident: int) -> bytes:
    labels = host.rstrip(".").encode("idna").split(b".")
    if any(not label or len(label) > 63 for label in labels):
        raise ValueError("not a host name")
    qname = b"".join(bytes([len(label)]) + label for label in labels) + b"\0"
    return struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0) + qname + struct.pack(">HH", 16, 1)


def _skip_name(data: bytes, off: int) -> int:
    while True:
        if off >= len(data):
            raise ValueError("short answer")
        size = data[off]
        if size & 0xC0 == 0xC0:
            return off + 2
        if size == 0:
            return off + 1
        off += 1 + size


def parse_txt(data: bytes, ident: int) -> list[str]:
    """The TXT records in a DNS answer (each record's strings joined)."""
    if len(data) < 12:
        raise ValueError("short answer")
    got_id, flags, qd, an = struct.unpack(">HHHH", data[:8])
    if got_id != ident or not flags & 0x8000:
        raise ValueError("not our answer")
    if flags & 0x000F not in (0, 3):           # 3: no such name, no records
        raise ValueError(f"DNS error {flags & 0x000F}")
    off = 12
    for _ in range(qd):
        off = _skip_name(data, off) + 4
    out = []
    for _ in range(an):
        off = _skip_name(data, off)
        rtype, _cls, _ttl, size = struct.unpack(">HHIH", data[off:off + 10])
        off += 10
        rdata, off = data[off:off + size], off + size
        if rtype != 16:
            continue
        parts, i = [], 0
        while i < len(rdata):
            n = rdata[i]
            parts.append(rdata[i + 1:i + 1 + n])
            i += 1 + n
        out.append(b"".join(parts).decode("utf-8", "replace"))
    return out


def dns_txt(host: str, nameserver=None, timeout: float = DNS_SECONDS) -> list[str]:
    """The TXT records of `host`, asked over UDP of `nameserver` ((address,
    port), or the system's first). [] when nothing answers."""
    if nameserver is None:
        found = nameservers()
        if not found:
            return []
        nameserver = (found[0], 53)
    address, port = nameserver
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    ident = int.from_bytes(os.urandom(2), "big")
    deadline = time.monotonic() + timeout
    with socket.socket(family, socket.SOCK_DGRAM) as sock:
        sock.sendto(_query(host, ident), (address, port))
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                return []
            sock.settimeout(left)
            try:
                data, peer = sock.recvfrom(4096)
            except OSError:
                return []
            if peer[0] != address:
                continue
            try:
                return parse_txt(data, ident)
            except (ValueError, struct.error):
                continue


# ----------------------------------------------------------- the page

class _Metas(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        got = {str(k).lower(): (v or "") for k, v in attrs}
        if got.get("name", "").strip().lower() == META:
            self.found.append(got.get("content", "").strip())

    handle_startendtag = handle_starttag


def meta_tokens(page: bytes) -> list[str]:
    parser = _Metas()
    try:
        parser.feed(page[:PAGE_BYTES].decode("utf-8", "replace"))
        parser.close()
    except Exception:                       # noqa: BLE001 - a broken page has no tag
        pass
    return parser.found


def fetch_home(host: str, config: dict) -> tuple[int, bytes, str | None]:
    """(status, body, error) of https://<host>/ by the outgoing client."""
    from .conversions import outgoing
    getter = getattr(outgoing, "get", None)
    if getter is None:
        return 0, b"", "the page check is not available on this server"
    return getter(f"https://{host}/", config, max_bytes=PAGE_BYTES, seconds=PAGE_SECONDS)


def check(db, name: str, config: dict, actor, resolver=None, fetcher=None) -> dict:
    """Look for the token by DNS, then on the home page; mark the site
    verified when found. {"verified", "method", "error"}."""
    got = state(db, name)
    if got is None or got["verified_at"]:
        return {"verified": True, "method": (got or {}).get("method"), "error": None}
    token = got["token"]
    resolver = resolver or dns_txt
    fetcher = fetcher or fetch_home
    try:
        records = resolver(name)
    except (OSError, ValueError, UnicodeError):
        records = []
    want = (PREFIX + token).encode()
    if any(hmac.compare_digest(str(r).strip().encode(), want) for r in records):
        mark(db, name, actor, "dns")
        return {"verified": True, "method": "dns", "error": None}
    status, page, error = fetcher(name, config)
    if not error and 200 <= int(status or 0) < 300 and any(
            hmac.compare_digest(t.encode(), token.encode()) for t in meta_tokens(page or b"")):
        mark(db, name, actor, "meta")
        return {"verified": True, "method": "meta", "error": None}
    why = error or (f"HTTP {status}" if status and not 200 <= status < 300 else
                    "no tag on the page")
    return {"verified": False, "method": None,
            "error": (f"Neither a TXT record {PREFIX}{token} on {name} nor the "
                      f"{META} meta tag on https://{name}/ was found ({why}).")}
