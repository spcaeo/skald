"""`hubspot`: HubSpot app webhooks and workflow "Send a webhook" actions.

Signature v3: `X-HubSpot-Signature-v3: <base64 HMAC-SHA256 of method + URI
+ raw body + timestamp>` with the app's client secret, the timestamp (Unix
milliseconds) in `X-HubSpot-Request-Timestamp`; refused more than 5
minutes off. The URI is the full public URL HubSpot called, with a few
percent-escapes decoded as HubSpot does before signing.

Bodies:
  * a list of subscription events (app webhooks): contact.creation ->
    action "contact", completed; object.creation of a meeting (objectTypeId
    0-47) -> "demo", completed; deal.propertyChange of dealstage to
    closedwon -> action "deal", won. External ref "<action>:<objectId>".
  * one object (a workflow's webhook): {"objectId": ..., "properties":
    {...}} -> action "contact" (or the property `skald_action`, such as
    "demo" for a "meeting booked" workflow), completed, ref
    "workflow:<objectId>". The visitor ID from the property `skv`; utm_*
    properties give the last touch.
"""
from __future__ import annotations

import hmac

from .. import ACTION, EVENTS, HUBSPOT_MEETING, TOLERANCE, action_name
from . import Invalid, hmac_b64, skald_vid, text, utm_touch, when

HEADER = "x-hubspot-signature-v3"
STAMP_HEADER = "x-hubspot-request-timestamp"
MAX_EVENTS = 100
# HubSpot decodes these in the URI before it signs (its v3 documentation).
DECODED = {"%3A": ":", "%2F": "/", "%3F": "?", "%40": "@", "%21": "!", "%24": "$",
           "%27": "'", "%28": "(", "%29": ")", "%2A": "*", "%2C": ",", "%3B": ";"}


def _uri(uri: str) -> str:
    for code, char in DECODED.items():
        uri = uri.replace(code, char).replace(code.lower(), char)
    return uri


def _message(method: str, uri: str, body: bytes, stamp: str) -> bytes:
    return method.upper().encode() + _uri(uri).encode() + body + stamp.encode()


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    got, stamp = headers.get(HEADER) or "", headers.get(STAMP_HEADER) or ""
    if not secret or not got or not stamp.isdigit():
        return False
    if abs(now * 1000 - int(stamp)) > TOLERANCE * 1000:
        return False
    want = hmac_b64(secret, _message(headers.get(":method", "POST"), headers.get(":uri", ""),
                                     body, stamp))
    return hmac.compare_digest(want, got.strip())


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    stamp = str(int(now * 1000))
    return {"X-HubSpot-Signature-v3": hmac_b64(secret, _message(method, uri, body, stamp)),
            "X-HubSpot-Request-Timestamp": stamp}


def _prop(props: dict, name: str):
    value = props.get(name)
    return value.get("value") if isinstance(value, dict) else value


def _event(item) -> dict | None:
    if not isinstance(item, dict):
        raise Invalid("a HubSpot event is an object")
    kind = str(item.get("subscriptionType") or "")
    if kind == "deal.propertyChange" and item.get("propertyName") == "dealstage" \
            and item.get("propertyValue") == "closedwon":
        kind += "+closedwon"
    if kind == "object.creation" and str(item.get("objectTypeId") or "") == HUBSPOT_MEETING:
        kind += "+" + HUBSPOT_MEETING
    mapped = EVENTS["hubspot"].get(kind)
    if mapped is None:
        return None
    obj = text(item.get("objectId"), 40)
    if not obj:
        raise Invalid("no objectId")
    return {"action": mapped[0], "stage": mapped[1], "external_ref": f"{mapped[0]}:{obj}",
            "at": when(item.get("occurredAt"))}


def to_records(payload, site_config: dict | None = None) -> list[dict]:
    if isinstance(payload, list):
        if len(payload) > MAX_EVENTS:
            raise Invalid(f"at most {MAX_EVENTS} events in one delivery")
        return [r for r in (_event(item) for item in payload) if r]
    if not isinstance(payload, dict):
        raise Invalid("not a HubSpot webhook body")
    props = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}
    obj = text(payload.get("objectId") or _prop(props, "hs_object_id"), 40)
    if not obj:
        raise Invalid("no objectId")
    action, stage = EVENTS["hubspot"]["workflow"]
    flat = {k: _prop(props, k) for k in props}
    named = action_name(flat.get("skald_action")) if isinstance(
        flat.get("skald_action"), str) else ""
    action = named if named and ACTION.match(named) else action
    return [{"action": action, "stage": stage, "external_ref": f"workflow:{obj}",
             "at": when(_prop(props, "createdate")) or when(payload.get("occurredAt")),
             "vid": skald_vid(flat.get("skv")), "last_touch": utm_touch(flat),
             "name": text(" ".join(str(flat.get(k) or "") for k in ("firstname", "lastname"))),
             "email": text(flat.get("email"), 320)}]


def sample(site: str, now: float) -> dict:
    return {"objectId": int(now), "properties": {
        "createdate": {"value": str(int(now * 1000))}, "skv": {"value": "skv_" + "A" * 22},
        "utm_source": {"value": "linkedin"}, "email": {"value": "test@example.com"}}}
