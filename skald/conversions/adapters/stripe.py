"""`stripe`: Stripe Checkout webhooks.

Signature: `Stripe-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "<t>.<raw
body>">` (several v1 may be sent while a secret is rolled), with the
endpoint's signing secret (whsec_...); refused more than 5 minutes off.

Events: checkout.session.completed -> paid (completed while its
payment_status is "unpaid", a delayed payment method), and
checkout.session.async_payment_succeeded -> paid. The external ref is the
Checkout Session id. The visitor ID: client_reference_id, or metadata.skv,
when it looks like a Skald ID. Customer details are never read.
"""
from __future__ import annotations

from .. import EVENTS
from . import Invalid, dig, sign_timed, skald_vid, text, utm_touch, verify_timed, when

HEADER = "stripe-signature"


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    return verify_timed(headers.get(HEADER, ""), body, secret, now)


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    return {"Stripe-Signature": sign_timed(body, secret, now)}


def to_records(payload, site_config: dict | None = None) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("object") != "event":
        raise Invalid("not a Stripe event")
    kind = str(payload.get("type") or "")
    obj = dig(payload, "data", "object")
    if not isinstance(obj, dict):
        raise Invalid("no data.object")
    if kind == "checkout.session.completed" and obj.get("payment_status") == "unpaid":
        kind += "+unpaid"
    mapped = EVENTS["stripe"].get(kind)
    if mapped is None:
        return []
    ref = text(obj.get("id"), 120)
    if not ref:
        raise Invalid("no session id")
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    return [{"action": mapped[0], "stage": mapped[1], "external_ref": ref,
             "at": when(payload.get("created")),
             "vid": skald_vid(obj.get("client_reference_id")) or skald_vid(meta.get("skv")),
             "last_touch": utm_touch(meta)}]


def sample(site: str, now: float) -> dict:
    return {"id": f"evt_skaldtest{int(now)}", "object": "event", "created": int(now),
            "type": "checkout.session.completed",
            "data": {"object": {"id": f"cs_test_skald{int(now)}", "object": "checkout.session",
                                "payment_status": "paid",
                                "client_reference_id": "skv_" + "A" * 22,
                                "metadata": {"utm_source": "google", "utm_medium": "cpc"}}}}
