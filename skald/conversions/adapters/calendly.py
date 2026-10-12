"""`calendly`: Calendly webhook subscriptions (a paid Calendly plan).

Signature: `Calendly-Webhook-Signature: t=<unix>,v1=<hex HMAC-SHA256 of
"<t>.<raw body>">`, with the signing key given when the subscription was
made; refused more than 5 minutes off.

Events: invitee.created -> completed; invitee.canceled -> cancelled, or
rescheduled when payload.rescheduled is true; invitee_no_show.created ->
no_show. The external ref is the invitee's URI, so every stage of one
booking shares it. The visitor ID comes back in payload.tracking.utm_content
(the snippet puts it there) when it looks like a Skald ID.
"""
from __future__ import annotations

from .. import EVENTS
from . import Invalid, sign_timed, skald_vid, text, utm_touch, verify_timed, when

HEADER = "calendly-webhook-signature"


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    return verify_timed(headers.get(HEADER, ""), body, secret, now)


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    return {"Calendly-Webhook-Signature": sign_timed(body, secret, now)}


def to_records(payload, site_config: dict | None = None) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("payload"), dict):
        raise Invalid("not a Calendly webhook body")
    event = str(payload.get("event") or "")
    inner = payload["payload"]
    key = event
    if event == "invitee.canceled" and inner.get("rescheduled") is True:
        key = "invitee.canceled+rescheduled"
    mapped = EVENTS["calendly"].get(key)
    if mapped is None:
        return []
    # A no-show names its invitee by URL; the invitee's own events by `uri`.
    invitee = inner.get("invitee") if isinstance(inner.get("invitee"), str) else None
    ref = text(invitee or inner.get("uri"), 300)
    if not ref:
        raise Invalid("no invitee URI")
    tracking = inner.get("tracking") if isinstance(inner.get("tracking"), dict) else {}
    return [{"action": mapped[0], "stage": mapped[1], "external_ref": ref,
             "at": when(payload.get("created_at")) or when(inner.get("created_at")),
             "vid": skald_vid(tracking.get("utm_content")),
             "last_touch": utm_touch(tracking),
             "name": text(inner.get("name")), "email": text(inner.get("email"), 320)}]


def sample(site: str, now: float) -> dict:
    stamp = when(int(now))
    uri = f"https://api.calendly.com/scheduled_events/TEST/invitees/T{int(now)}"
    return {"event": "invitee.created", "created_at": stamp,
            "created_by": "https://api.calendly.com/users/TEST",
            "payload": {"uri": uri,
                        "status": "active", "rescheduled": False, "created_at": stamp,
                        "name": "Test Person", "email": "test@example.com",
                        "tracking": {"utm_source": "newsletter", "utm_medium": "email",
                                     "utm_campaign": "october",
                                     "utm_content": "skv_" + "A" * 22}}}

