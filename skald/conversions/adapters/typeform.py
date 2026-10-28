"""`typeform`: Typeform webhooks.

Signature: `Typeform-Signature: sha256=<base64 HMAC-SHA256 of the raw
body>`, with the secret set on the webhook. No timestamp: the receiver
keeps each accepted body's hash for 30 days and refuses a repeat, even
after `forget` (hooks.replay_digest).

Event: form_response -> completed. The external ref is
form_response.token. The visitor ID comes from the hidden field `skv`
(add it to the form, and to the embed's hidden fields); utm_* hidden fields
give the last touch. Answers are never read.
"""
from __future__ import annotations

import hmac

from .. import EVENTS
from . import Invalid, hmac_b64, skald_vid, text, utm_touch, when

HEADER = "typeform-signature"
SIGNED = (HEADER,)          # no signature header at all: "unsigned"


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    got = (headers.get(HEADER) or "").strip()
    if not secret or not got.startswith("sha256="):
        return False
    return hmac.compare_digest(hmac_b64(secret, body), got[7:])


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    return {"Typeform-Signature": "sha256=" + hmac_b64(secret, body)}


def to_records(payload, site_config: dict | None = None) -> list[dict]:
    if not isinstance(payload, dict):
        raise Invalid("not a Typeform webhook body")
    mapped = EVENTS["typeform"].get(str(payload.get("event_type") or ""))
    if mapped is None:
        return []
    response = payload.get("form_response")
    if not isinstance(response, dict):
        raise Invalid("no form_response")
    ref = text(response.get("token"), 120)
    if not ref:
        raise Invalid("no response token")
    hidden = response.get("hidden") if isinstance(response.get("hidden"), dict) else {}
    return [{"action": mapped[0], "stage": mapped[1], "external_ref": ref,
             "at": when(response.get("submitted_at")), "vid": skald_vid(hidden.get("skv")),
             "last_touch": utm_touch(hidden)}]


def sample(site: str, now: float) -> dict:
    return {"event_id": f"skaldtest{int(now)}", "event_type": "form_response",
            "form_response": {"form_id": "TEST", "token": f"skald-test-{int(now)}",
                              "submitted_at": when(int(now)),
                              "hidden": {"skv": "skv_" + "A" * 22, "utm_source": "newsletter"},
                              "answers": [{"type": "email", "email": "test@example.com"}]}}
