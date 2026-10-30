"""One module per tool. Each offers:

    verify(headers, body, secret, now) -> bool
        `headers` is a dict with lower-case names, plus ":method" and
        ":uri" (the public URL the tool called); `body` the raw bytes;
        `now` Unix seconds. Checked BEFORE the body is parsed.
    to_records(payload, site_config) -> list[dict]
        the parsed body as records: action, stage, external_ref, and what is
        known of at, vid, first_touch, last_touch, landing, campaign,
        source_type, country or ip, device or user_agent, name, email,
        visits_before, first_touch_at. Raises Invalid for a body that is
        not what the tool sends; [] for an event Skald does not count.
    sign(body, secret, now, method, uri) -> dict
        the headers the tool would send: for tests and `skald hooks test`.
    sample(site, now) -> dict
        a body like the tool's, for `skald hooks test`.
    HEADER, SIGNED
        the signature's header, and every header that carries a signature
        (lead and json: also Authorization). A delivery with none of SIGNED
        is "unsigned" (2.44.1, signed()): the tool was set up without a key,
        so no key pasted into Skald can ever match it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone

from .. import SKALD_VID, TOLERANCE


class Invalid(ValueError):
    """A verified body that cannot be read as this tool's event."""


STAMP = "%Y-%m-%dT%H:%M:%SZ"
TOUCH_KEYS = ("referrer", "landing", "utm_source", "utm_medium", "utm_campaign",
              "utm_content", "utm_term", "gclid", "gbraid", "wbraid", "msclkid", "fbclid",
              "li_fat_id", "ttclid", "twclid")


def hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def hmac_b64(secret: str, message: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).decode()


def pairs(header: str) -> dict[str, list[str]]:
    """"t=1,v1=ab,v1=cd" -> {"t": ["1"], "v1": ["ab", "cd"]}."""
    out: dict[str, list[str]] = {}
    for part in (header or "").split(","):
        k, sep, v = part.strip().partition("=")
        if sep:
            out.setdefault(k.strip(), []).append(v.strip())
    return out


def verify_timed(header: str, body: bytes, secret: str, now: float,
                 tolerance: int = TOLERANCE) -> bool:
    """The "t=<unix>,v1=<hex HMAC-SHA256 of '<t>.<body>'>" scheme (Skald's
    own, Stripe's and Calendly's): within `tolerance` seconds of now."""
    if not secret or not header:
        return False
    got = pairs(header)
    try:
        t = int(got.get("t", [""])[0])
    except ValueError:
        return False
    if abs(now - t) > tolerance:
        return False
    want = hmac_hex(secret, f"{t}.".encode() + body)
    return any(hmac.compare_digest(want, v.lower()) for v in got.get("v1", []))


def sign_timed(body: bytes, secret: str, now: float) -> str:
    t = int(now)
    return f"t={t},v1={hmac_hex(secret, f'{t}.'.encode() + body)}"


def when(value, tz=None) -> str | None:
    """A time as UTC "YYYY-MM-DDTHH:MM:SSZ": ISO text (any offset, any
    fraction) or Unix seconds or milliseconds. None when missing or not a time.
    ISO text without an offset ("2026-09-25", "2026-09-25T08:00:00") is read
    in `tz`, the site's time zone, when given; else as UTC (naive() tells)."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = value / 1000 if value > 10_000_000_000 else value
            got = datetime.fromtimestamp(seconds, tz=timezone.utc)
        else:
            text = str(value).strip()
            if text.isdigit():
                return when(int(text))
            got = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
            if got.tzinfo is None:
                got = got.replace(tzinfo=tz or timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return got.astimezone(timezone.utc).strftime(STAMP)


def naive(value) -> bool:
    """True for ISO text that is a time but names no offset ("2026-09-25",
    "2026-09-25T08:00:00"): its zone is a guess, the site's."""
    if not isinstance(value, str) or value.strip().isdigit():
        return False
    try:
        got = datetime.fromisoformat(value.strip().replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        return False
    return got.tzinfo is None


def dig(value, *path):
    """value[path[0]][path[1]]..., None when any step is missing."""
    for key in path:
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and isinstance(key, int) and -len(value) <= key < len(value):
            value = value[key]
        else:
            return None
    return value


def text(value, limit: int = 200) -> str | None:
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    out = str(value).strip()[:limit]
    return out or None


def skald_vid(value) -> str | None:
    value = text(value, 64)
    return value if value and SKALD_VID.match(value) else None


def touch(raw, tz=None) -> dict | None:
    """A touch (where a visit came from) with only the known keys, or None.
    Its `at` without an offset is read in `tz` (when())."""
    if not isinstance(raw, dict):
        return None
    out = {k: text(raw.get(k), 300) for k in TOUCH_KEYS if text(raw.get(k), 300)}
    at = when(raw.get("at"), tz)
    if at:
        out["at"] = at
    return out or None


def utm_touch(source: dict | None) -> dict | None:
    """A touch from a tool's own UTM fields (Calendly's `tracking`, metadata)."""
    if not isinstance(source, dict):
        return None
    return touch({k: source.get(k) for k in TOUCH_KEYS})


def signed(tool: str, headers: dict) -> bool:
    """Did the delivery carry any of the tool's signature headers (SIGNED),
    with a value? False: "unsigned", told apart from a signature that did
    not match ("bad_signature")."""
    mod = adapter(tool)
    names = getattr(mod, "SIGNED", None) or (getattr(mod, "HEADER", ""),)
    return any(str(headers.get(name) or "").strip() for name in names if name)


def _load():
    from . import calcom, calendly, generic, hubspot, lead, stripe, typeform
    return {"lead": lead, "json": generic, "calendly": calendly, "calcom": calcom,
            "stripe": stripe, "typeform": typeform, "hubspot": hubspot}


_ADAPTERS: dict | None = None


def adapter(tool: str):
    """The module for a tool name, or None."""
    global _ADAPTERS
    if _ADAPTERS is None:
        _ADAPTERS = _load()
    return _ADAPTERS.get(tool)
