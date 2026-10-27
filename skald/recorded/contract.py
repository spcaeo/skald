"""What one recorded event may hold, version 1 (docs/JOURNEYS.md, "The contract").

Identifiers and fixed facts, never a form's answers. Every field is checked; an
unknown field, a repeated key, a page with a query string, a text that looks like an
email, a phone number, an address or a long token is refused as a whole (400), never
cleaned: the site's code is wrong and should know.

    validate(payload, now)          -> the event as it is kept (a new dict)
    validate_withdraw(payload, now) -> {"visitor_id", "occurred_at"}

Consent: `consent.analytics` must be "granted" on every event; anything else is
refused (NoConsent). A withdrawal says "withdrawn".

The address (`ip`) and the email are the visitor's as the website's own server saw
them; whether Skald keeps them is the site's privacy setting, applied by receive.py.
"""
from __future__ import annotations

import ipaddress
import json
import re
from datetime import datetime, timedelta
from urllib.parse import unquote

from . import (CONSENT_FIELDS, EMAIL_EVENTS, EVENTS, FIELDS, FUTURE_SECONDS, GRANTED,
               MAX_AGE_DAYS, REFERRER_FIELDS, TOUCH_FIELDS, VERSION, WITHDRAW_FIELDS,
               WITHDRAWN)

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
INSTANT = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z")
SKALD_VID = re.compile(r"skv_[A-Za-z0-9_-]{22}")
EMAIL = re.compile(r"[A-Za-z0-9._%+'-]{1,64}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
HOST = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,198}[a-z0-9])?")
# A text that may name a person: an @, seven digits in a row, a phone-like run, a long token.
PERSONAL = re.compile(r"@|\d{7,}|(?:\d[\s()+.-]*){10,}|[A-Za-z0-9_]{40,}")
IP_TOKEN = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])|[0-9A-Fa-f]{0,4}:[0-9A-Fa-f:]{2,}")


class Invalid(ValueError):
    """The event is refused; `field` names what was wrong (never its value)."""

    def __init__(self, field: str, words: str = "") -> None:
        super().__init__(words or f"invalid {field}")
        self.field = field


class NoConsent(Invalid):
    def __init__(self) -> None:
        super().__init__("consent", "no analytics consent: nothing is kept")


def loads(body: bytes):
    """The JSON body; a repeated key is refused (it could change a signed meaning)."""
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise Invalid("body", "a key is repeated")
            out[key] = value
        return out
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=pairs)
    except Invalid:
        raise
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise Invalid("body", "the body is not one JSON object") from None


def uuid(value, field: str) -> str:
    if not isinstance(value, str) or not UUID.fullmatch(value):
        raise Invalid(field, f"{field} is not a lowercase UUID")
    return value


def instant(value, field: str, now: datetime) -> str:
    if not isinstance(value, str) or not INSTANT.fullmatch(value):
        raise Invalid(field, f"{field} is not a UTC time like 2026-10-27T12:00:00Z")
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Invalid(field) from None
    if at > now + timedelta(seconds=FUTURE_SECONDS):
        raise Invalid(field, f"{field} is in the future")
    if at < now - timedelta(days=MAX_AGE_DAYS):
        raise Invalid(field, f"{field} is more than {MAX_AGE_DAYS} days old")
    # Whole seconds, as every other time Skald keeps (conversions.store.STAMP).
    return at.strftime("%Y-%m-%dT%H:%M:%SZ")


def personal(value: str) -> bool:
    text = unquote(value)
    if PERSONAL.search(text):
        return True
    for token in IP_TOKEN.finditer(text):
        try:
            ipaddress.ip_address(token.group())
            return True
        except ValueError:
            continue
    return False


def text(value, field: str, most: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > most \
            or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise Invalid(field, f"{field} is not a short line of text")
    if personal(value):
        raise Invalid(field, f"{field} looks like it holds an email, a phone number, an "
                             "address or a token")
    return value.strip()


def path(value, field: str = "path") -> str:
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//") \
            or len(value) > 500:
        raise Invalid(field, f"{field} is not a page's path")
    plain = unquote(value)
    if any(c in plain for c in "?#\\") or ".." in plain.split("/") \
            or any(ord(c) < 32 for c in plain) or personal(value):
        raise Invalid(field, f"{field} must be the page's path only, with no query string")
    return value.rstrip("/") or "/"


def _consent(value, want: str) -> dict:
    if not isinstance(value, dict) or set(value) - set(CONSENT_FIELDS):
        raise NoConsent() if want == GRANTED else Invalid("consent")
    if value.get("analytics") != want:
        raise NoConsent() if want == GRANTED else Invalid("consent", 'consent.analytics must '
                                                                      'be "withdrawn"')
    out = {"analytics": want}
    if value.get("notice_version") is not None:
        out["notice_version"] = text(value["notice_version"], "consent.notice_version", 80)
    return out


def _touch(value) -> dict:
    if not isinstance(value, dict) or set(value) - set(TOUCH_FIELDS):
        raise Invalid("touch", "touch holds landing_path, referrer and the utm_ fields only")
    out = {"landing_path": path(value.get("landing_path"), "touch.landing_path")}
    ref = value.get("referrer")
    if ref is not None:
        if not isinstance(ref, dict) or set(ref) - set(REFERRER_FIELDS):
            raise Invalid("touch.referrer", "touch.referrer holds host and path only")
        host = ref.get("host")
        if not isinstance(host, str) or not HOST.fullmatch(host.lower()) or ".." in host \
                or re.fullmatch(r"[\d.]+", host):
            raise Invalid("touch.referrer.host", "touch.referrer.host is not a host name")
        out["referrer"] = {"host": host.lower(),
                           "path": path(ref.get("path", "/"), "touch.referrer.path")}
    for key in TOUCH_FIELDS[2:]:
        if value.get(key) is not None:
            out[key] = text(value[key], f"touch.{key}", 160)
    return out


def validate(payload, now: datetime) -> dict:
    """The event as kept, or Invalid / NoConsent."""
    if not isinstance(payload, dict):
        raise Invalid("body", "the body is not one JSON object")
    extra = sorted(set(payload) - set(FIELDS))
    if extra:
        raise Invalid("fields", f"unknown field {extra[0][:40]!r}")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != VERSION:
        raise Invalid("schema_version", f"schema_version must be {VERSION}")
    # Consent first: an event without it is refused before anything else is read.
    consent = _consent(payload.get("consent"), GRANTED)
    name = payload.get("event_name")
    if name not in EVENTS:
        raise Invalid("event_name", "event_name is not one Skald knows: " + ", ".join(EVENTS))
    out = {"schema_version": VERSION, "event_id": uuid(payload.get("event_id"), "event_id"),
           "event_name": name, "occurred_at": instant(payload.get("occurred_at"), "occurred_at", now),
           "visitor_id": uuid(payload.get("visitor_id"), "visitor_id"),
           "session_id": uuid(payload.get("session_id"), "session_id"),
           "path": path(payload.get("path")), "consent": consent}
    if payload.get("label") is not None:
        out["label"] = text(payload["label"], "label", 80)
    if payload.get("touch") is not None:
        if name != "session_started":
            raise Invalid("touch", "touch is sent with session_started only")
        out["touch"] = _touch(payload["touch"])
    if payload.get("skald_vid") is not None:
        if not isinstance(payload["skald_vid"], str) or not SKALD_VID.fullmatch(payload["skald_vid"]):
            raise Invalid("skald_vid", "skald_vid is not the script tag's visitor ID")
        out["skald_vid"] = payload["skald_vid"]
    if payload.get("ip") is not None:
        try:
            out["ip"] = str(ipaddress.ip_address(str(payload["ip"]).strip()))
        except ValueError:
            raise Invalid("ip", "ip is not an IP address") from None
    if payload.get("email") is not None:
        if name not in EMAIL_EVENTS:
            raise Invalid("email", "email is sent only with " + ", ".join(EMAIL_EVENTS))
        email = payload["email"]
        if not isinstance(email, str) or len(email) > 254 or not EMAIL.fullmatch(email.strip()):
            raise Invalid("email", "email is not an email address")
        out["email"] = email.strip().lower()
    return out


def validate_withdraw(payload, now: datetime) -> dict:
    if not isinstance(payload, dict):
        raise Invalid("body", "the body is not one JSON object")
    extra = sorted(set(payload) - set(WITHDRAW_FIELDS))
    if extra:
        raise Invalid("fields", f"unknown field {extra[0][:40]!r}")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != VERSION:
        raise Invalid("schema_version", f"schema_version must be {VERSION}")
    _consent(payload.get("consent"), WITHDRAWN)
    return {"visitor_id": uuid(payload.get("visitor_id"), "visitor_id"),
            "occurred_at": instant(payload.get("occurred_at"), "occurred_at", now)}
