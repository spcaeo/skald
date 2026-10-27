"""The recorded-journeys receiver, on the beacon helper (beacon_server.py), behind nginx:

    POST /traffic-hooks/<site>/journey            one event (contract.py), JSON
    POST /traffic-hooks/<site>/journey/withdraw   {"schema_version": 1, "visitor_id",
                                                   "occurred_at", "consent": {"analytics":
                                                   "withdrawn"}}: delete the visitor's events

Both signed by the website's own server with the site's journey secret (secrets.json
"hooks/<site>/journey", or the environment variable the config names for it):

    X-Skald-Timestamp: <unix seconds>
    X-Skald-Signature: hex(HMAC-SHA256(secret, timestamp + "." + body))

The browser never holds the secret: the page posts to the site's own relay (the
Next.js example, kit/journeys/), which signs and forwards. Each request, in order:

  1. the site is one this install reports on, with a journey secret, and not waiting
     for its domain to be verified: else 404 (500 when secrets.json is not 0600)
  2. a Content-Length (411) of at most MAX_BODY bytes (413)
  3. the signature, inside SIGN_WINDOW seconds, checked before the body is read as
     JSON: 401, and a failure spends the sender's small pre-auth bucket (429)
  4. at most `journeys.per_minute` signed events a minute per site (600, burst 200)
     and `journeys.visitor_per_minute` per visitor (120): 429 with Retry-After
  5. the body (contract.py): 400 in plain words; no analytics consent: 400, counted
  6. the site's privacy settings, applied before anything is kept: the address kept
     in full, shortened or dropped (privacy.keep_ips), the email only when the site
     keeps identity (conversions.identity: full)
  7. kept once by its event ID: 201 new, 200 the same body again, 409 the same ID
     with another body, 202 its visitor withdrew (nothing kept)

A withdrawal is answered 200 with how many events went. Nothing in a request is ever
logged; refusals are counted (one deliveries row a minute per kind, as the hooks do).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import time
from datetime import datetime, timezone

from ..config import setting
from . import EMAIL_EVENTS, MAX_BODY, SIGN_WINDOW, TOOL
from . import store
from .contract import Invalid, NoConsent, loads, validate, validate_withdraw

ROUTE = re.compile(r"^/traffic-hooks/(?P<site>[A-Za-z0-9][A-Za-z0-9._-]{0,99})/journey"
                   r"(?P<withdraw>/withdraw)?/?$")
STAMP = re.compile(r"\d{9,11}")
SIGNATURE = re.compile(r"[0-9a-f]{64}")


def is_route(path: str) -> bool:
    return ROUTE.match(path.split("?", 1)[0]) is not None


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body,
                    hashlib.sha256).hexdigest()


def signed(secret: str, headers: dict, body: bytes, now: float) -> bool:
    stamp = str(headers.get("x-skald-timestamp") or "")
    got = str(headers.get("x-skald-signature") or "").lower()
    if not STAMP.fullmatch(stamp) or not SIGNATURE.fullmatch(got):
        return False
    if abs(now - int(stamp)) > SIGN_WINDOW:
        return False
    return hmac.compare_digest(sign(secret, stamp, body), got)


class Limits:
    """The site's and each visitor's buckets, for the life of the process."""

    def __init__(self, config: dict) -> None:
        from ..beacon_server import Limiter
        per = float(setting(config, "journeys", "per_minute", 600))
        self.site = Limiter(per, float(setting(config, "journeys", "burst", 200)),
                            max(per / 60.0 * 5, 50.0), clock=time.monotonic)
        self.visitor = Limiter(float(setting(config, "journeys", "visitor_per_minute", 120)), 60,
                               10_000, clock=time.monotonic)


_LIMITS: dict = {}


def limits(config: dict) -> Limits:
    got = _LIMITS.get(id(config))
    if got is None:
        got = _LIMITS[id(config)] = Limits(config)
    return got


def secret_of(rec, site: str):
    """(the site's journey secret, None) or (None, (status, answer))."""
    from ..conversions.hooks import SITES_EVERY
    from ..conversions.secrets_store import Exposed, find
    from ..site_verify import refuses
    if site not in rec.sites and time.monotonic() - rec.sites_at >= SITES_EVERY:
        rec._load_sites()
    if site not in rec.sites or refuses(rec.config, rec.folder, site):
        return None, (404, {"error": "not found"})
    try:
        value = find(rec.sites[site], rec.folder, site, TOOL)[0]
    except Exposed:
        return None, (500, {"error": "not set up"})
    return (value, None) if value else (None, (404, {"error": "not found"}))


def private(rec, site: str, event: dict) -> list[str]:
    """Apply the site's privacy settings to the event in place; the notes."""
    from ..people import policy
    conf = rec.settled(site)
    notes = []
    if "ip" in event:
        mode = policy.ip_mode(conf, rec.folder)
        if mode == policy.SHORT:
            event["ip"] = policy.shorten(event["ip"])
            notes.append("the address was kept shortened (the site's setting)")
        elif mode != policy.FULL:
            event.pop("ip")
            notes.append("the address was not kept (the site keeps none)")
    if "email" in event and not policy.identity_full(conf, rec.folder):
        event.pop("email")
        notes.append("the email was not kept (the site keeps no identity)")
    return notes


def answer(handler, config: dict, config_path=None, clock=time.time) -> tuple[int, dict, dict]:
    """(status, body, extra headers) for one request on a BaseHTTPRequestHandler."""
    from ..conversions.hooks import receiver
    found = ROUTE.match(handler.path.split("?", 1)[0])
    if not found:
        return 404, {"error": "not found"}, {}
    if handler.command != "POST":
        return 405, {"error": "POST only"}, {}
    rec = receiver(config, None, config_path)
    site = found["site"]
    secret, refused = secret_of(rec, site)
    if refused:
        return (*refused, {})
    try:
        length = int(handler.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return 411, {"error": "length required"}, {}
    if length > MAX_BODY:
        return 413, {"error": f"at most {MAX_BODY} bytes"}, {}
    body = handler.rfile.read(length)
    headers = {k.lower(): v for k, v in handler.headers.items()}
    now = clock()
    if not signed(secret, headers, body, now):
        rec._refused(site, TOOL, "bad_signature", 401)
        if not rec.preauth.allow(rec.client(handler)):
            return 429, {"error": "too many"}, {"Retry-After": "60"}
        return 401, {"error": "bad signature"}, {}
    gate = limits(config)
    if not gate.site.allow(site):
        rec._refused(site, TOOL, "rate_limited", 429)
        return 429, {"error": "too many"}, {"Retry-After": "60"}
    when = datetime.fromtimestamp(now, tz=timezone.utc)
    try:
        payload = loads(body)
        if found["withdraw"]:
            asked = validate_withdraw(payload, when)
        else:
            event = validate(payload, when)
    except NoConsent as why:
        _counted(rec, site, when, "refused_consent")
        return 400, {"error": str(why), "field": "consent"}, {}
    except Invalid as why:
        return 400, {"error": str(why), "field": why.field}, {}
    if found["withdraw"]:
        return _withdraw(rec, site, asked["visitor_id"], when)
    if not gate.visitor.allow(f"{site}/{event['visitor_id']}"):
        return 429, {"error": "too many for one visitor"}, {"Retry-After": "60"}
    notes = private(rec, site, event)
    try:
        db = store.connect(rec.db_path)
        try:
            got = store.record(db, site, event, when)
        finally:
            db.close()
    except store.Conflict as why:
        return 409, {"error": str(why)}, {}
    except (OSError, sqlite3.Error):
        return 503, {"error": "storage unavailable"}, {"Retry-After": "30"}
    if got == "withdrawn":
        return 202, {"ok": True, "ignored": "this visitor withdrew their consent"}, {}
    out = {"ok": True, "event_id": event["event_id"], "duplicate": got == "duplicate"}
    if notes:
        out["notes"] = notes
    return (201 if got == "created" else 200), out, {}


def _withdraw(rec, site: str, visitor_id: str, when: datetime):
    try:
        db = store.connect(rec.db_path)
        try:
            gone = store.withdraw(db, site, visitor_id, when)
        finally:
            db.close()
    except (OSError, sqlite3.Error):
        return 503, {"error": "storage unavailable"}, {"Retry-After": "30"}
    return 200, {"ok": True, "removed": gone}, {}


def _counted(rec, site: str, when: datetime, what: str) -> None:
    try:
        db = store.connect(rec.db_path)
        try:
            with store.cstore.tx(db):
                store.log(db, site, when, what)
        finally:
            db.close()
    except (OSError, sqlite3.Error):
        pass


def handle(handler, config: dict, config_path=None) -> None:
    """Answer one request to the journey routes (beacon_server.py dispatches here)."""
    try:
        status, body, more = answer(handler, config, config_path)
    except Exception:                      # noqa: BLE001 - never a traceback to a caller
        status, body, more = 500, {"error": "failed"}, {}
    raw = json.dumps(body, separators=(",", ":")).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    for name, value in more.items():
        handler.send_header(name, value)
    if status in (411, 413):
        handler.send_header("Connection", "close")
        handler.close_connection = True
    handler.end_headers()
    handler.wfile.write(raw)


# The emails an event may carry (for the docs' table): contract.EMAIL_EVENTS.
__all__ = ["answer", "handle", "is_route", "sign", "signed", "EMAIL_EVENTS"]
