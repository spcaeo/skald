"""`calcom`: Cal.com webhooks.

Signature: `X-Cal-Signature-256: <hex HMAC-SHA256 of the raw body>`, with
the webhook's secret. Cal.com sends no timestamp, so a replay cannot be
told by time: the receiver keeps each accepted body's hash for 30 days and
refuses a repeat, even after `forget` (hooks.replay_digest).

Events: BOOKING_CREATED -> completed, BOOKING_CANCELLED -> cancelled,
BOOKING_RESCHEDULED -> rescheduled. The external ref is the booking's uid.
The visitor ID: payload.metadata.skv or .utm_content, or a booking question
named "skv" (payload.responses.skv), when it looks like a Skald ID.
"""
from __future__ import annotations

import hmac

from .. import EVENTS
from . import Invalid, dig, hmac_hex, skald_vid, text, utm_touch, when

HEADER = "x-cal-signature-256"


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    got = (headers.get(HEADER) or "").strip().lower()
    if got.startswith("sha256="):
        got = got[7:]
    return bool(secret and got) and hmac.compare_digest(hmac_hex(secret, body), got)


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    return {"X-Cal-Signature-256": hmac_hex(secret, body)}


def _answer(value):
    return value.get("value") if isinstance(value, dict) else value


def to_records(payload, site_config: dict | None = None) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("payload"), dict):
        raise Invalid("not a Cal.com webhook body")
    mapped = EVENTS["calcom"].get(str(payload.get("triggerEvent") or ""))
    if mapped is None:
        return []
    inner = payload["payload"]
    ref = text(inner.get("uid"), 120)
    if not ref:
        raise Invalid("no booking uid")
    meta = inner.get("metadata") if isinstance(inner.get("metadata"), dict) else {}
    vid = (skald_vid(meta.get("skv")) or skald_vid(meta.get("utm_content"))
           or skald_vid(_answer(dig(inner, "responses", "skv"))))
    return [{"action": mapped[0], "stage": mapped[1], "external_ref": ref,
             "at": when(payload.get("createdAt")), "vid": vid, "last_touch": utm_touch(meta),
             "name": text(_answer(dig(inner, "responses", "name"))),
             "email": text(_answer(dig(inner, "responses", "email")), 320)}]


def sample(site: str, now: float) -> dict:
    return {"triggerEvent": "BOOKING_CREATED", "createdAt": when(int(now)),
            "payload": {"uid": f"skald-test-{int(now)}", "startTime": when(int(now) + 86400),
                        "metadata": {"skv": "skv_" + "A" * 22, "utm_source": "linkedin"},
                        "responses": {"name": {"value": "Test Person"},
                                      "email": {"value": "test@example.com"}}}}
