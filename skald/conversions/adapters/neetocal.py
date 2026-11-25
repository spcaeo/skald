"""`neetocal`: NeetoCal webhooks (SKALD-54). Every NeetoCal plan has them.

Signature: `X-Neeto-Webhook-Signature: sha256=<hex HMAC-SHA256 of the raw
body>` with the webhook's secret key (typed in, or made by NeetoCal's
"Generate secret key"); the same value comes again in
X-Neeto-Hook-Secret-Sha-256. Checked on real deliveries through a tunnel
(25 Nov 2026). NeetoCal's help also shows the body signed with HTML
characters escaped (< > & and U+2028/U+2029 as \\u003c ...), so that form is
taken too. No timestamp is signed, so a replay cannot be told by
time: the receiver keeps each accepted body's hash for 30 days and refuses a
repeat (hooks.replay_digest), as for Cal.com.

The body, as a real test booking showed it (25 Nov 2026; tests/fixtures/
neetocal/): one object `webhook` holding the booking itself and `method`:

    create   a booking made: sid, id, booked_on, status ("confirmed", or
             "awaiting_approval" when the link needs the host's approval),
             meeting {name, id, sid}, metadata.scheduling_link (the link's
             address), and the answers as details [{field_code, value, ...}]
    update   a change: the same booking, plus reschedule_details
             {time_changed, member_changed, ...} when it was moved
    cancel   a cancellation: only id, sid, canceller and cancel_reason

Mapped (EVENTS["neetocal"], by kind()): create -> demo completed (started
while it awaits approval); update with reschedule_details -> rescheduled; a
no-show outcome on an update -> no_show; an update that says cancelled or
rejected, cancel and reject -> cancelled. Any other update (notes, host,
place) is taken and ignored. The external ref is the booking's sid (its id
when there is none): every step of one booking shares it.

The visitor ID: a hidden booking question whose field code is `skv`
(skald.js puts ?skv= on NeetoCal links and embeds; NeetoCal fills the
question from the address). utm_* answers are the booking's own touch. Of
the answers only skv, utm_*, and name and email are read or kept (prepare());
a phone, a company or a note never is.
"""
from __future__ import annotations

import hmac
import re

from .. import EVENTS
from . import TOUCH_KEYS, Invalid, hmac_hex, skald_vid, text, utm_touch, when

HEADER = "x-neeto-webhook-signature"
# NeetoCal sends the same "sha256=<hex>" again in this header (seen live, 25 Nov).
ALSO = "x-neeto-hook-secret-sha-256"
SIGNED = (HEADER, ALSO)     # neither header at all: "unsigned"
VID_CODE = "skv"            # the hidden question's field code
WAITING = ("awaiting_approval", "pending", "requested")
_NO_SHOW = re.compile(r"no[\s_-]?show", re.I)
_ESCAPES = ((b"<", b"\\u003c"), (b">", b"\\u003e"), (b"&", b"\\u0026"),
            (" ".encode(), b"\\u2028"), (" ".encode(), b"\\u2029"))


def escaped(body: bytes) -> bytes:
    """The body as NeetoCal's help signs it: HTML characters escaped."""
    for raw, esc in _ESCAPES:
        body = body.replace(raw, esc)
    return body


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    got = (headers.get(HEADER) or headers.get(ALSO) or "").strip().lower()
    if got.startswith("sha256="):
        got = got[7:]
    if not (secret and got):
        return False
    return any(hmac.compare_digest(hmac_hex(secret, b), got) for b in (body, escaped(body)))


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    return {"X-Neeto-Webhook-Signature": "sha256=" + hmac_hex(secret, body)}


def booking_of(payload) -> dict:
    """The booking: the body's `webhook` object (the body itself without one)."""
    if not isinstance(payload, dict):
        return {}
    return payload["webhook"] if isinstance(payload.get("webhook"), dict) else payload


def kind(booking: dict) -> str:
    """What happened, as EVENTS["neetocal"] names it: the method, and for a
    create or an update what its fields say ("create+awaiting_approval",
    "update+rescheduled", "update+no_show", "update+cancelled"...)."""
    method = str(booking.get("method") or "").strip().lower()
    status = str(booking.get("status") or "").strip().lower()
    if method == "create":
        return "create+awaiting_approval" if status in WAITING else "create"
    if method == "update":
        moved = booking.get("reschedule_details")
        if isinstance(moved, dict) and (moved.get("time_changed") or moved.get("member_changed")):
            return "update+rescheduled"
        outcome = booking.get("meeting_outcome")
        if booking.get("no_show") is True or (isinstance(outcome, str) and _NO_SHOW.search(outcome)):
            return "update+no_show"
        if status in ("cancelled", "canceled", "rejected"):
            return "update+cancelled"
        return "update"
    return method


def answers(booking: dict) -> dict:
    """The booking's answers by field code: `details` (the webhook's list of
    {field_code, value}), else form_responses (the API's list), else
    form_responses_as_hash."""
    out: dict = {}
    for key in ("details", "form_responses"):
        listed = booking.get(key)
        if isinstance(listed, list):
            for item in listed:
                if isinstance(item, dict) and isinstance(item.get("field_code"), str):
                    out.setdefault(item["field_code"].strip().lower(), item.get("value"))
    got = booking.get("form_responses_as_hash")
    if isinstance(got, dict):
        for k, v in got.items():
            out.setdefault(str(k).strip().lower(), v)
    return {k: (v.get("value") if isinstance(v, dict) else v) for k, v in out.items()}


def _kept(code: str) -> bool:
    """skv, utm_* and click IDs; name and email too, which the spool and the
    row keep only when the site's identity is full (conversions.strip)."""
    return code in (VID_CODE, "name", "email") or code in TOUCH_KEYS


def prepare(payload):
    """The body as Skald reads and keeps it: the booking's answers only as
    form_responses_as_hash, and of them only those _kept() names. A phone, a
    company or a note never reaches the spool or a row."""
    if isinstance(payload, list):
        return [prepare(v) for v in payload]
    if not isinstance(payload, dict):
        return payload
    lists = ("details", "form_responses")
    out = {key: prepare(value) for key, value in payload.items() if key not in lists}
    if any(k in payload for k in lists + ("form_responses_as_hash",)):
        out["form_responses_as_hash"] = {k: v for k, v in answers(payload).items() if _kept(k)}
    return out


def ref_of(booking: dict) -> str | None:
    """The booking's sid, else its id: what every step of it shares."""
    return text(booking.get("sid"), 120) or text(booking.get("id"), 120)


def to_records(payload, site_config: dict | None = None) -> list[dict]:
    booking = booking_of(payload)
    if not booking or not booking.get("method"):
        raise Invalid("not a NeetoCal webhook body")
    mapped = EVENTS["neetocal"].get(kind(booking))
    if mapped is None:
        return []
    ref = ref_of(booking)
    if not ref:
        raise Invalid("no booking sid or id")
    said = answers(booking)
    # A booking made: when it was made. A change carries no time of its own:
    # Skald's receiving time is used (normalise.row).
    at = when(booking.get("booked_on")) if mapped[1] in ("completed", "started") else None
    return [{"action": mapped[0], "stage": mapped[1], "external_ref": ref, "at": at,
             "vid": skald_vid(said.get(VID_CODE)) or skald_vid(said.get("utm_content")),
             "last_touch": utm_touch({k: v for k, v in said.items() if k in TOUCH_KEYS}),
             "name": text(said.get("name")) or text(booking.get("name")),
             "email": text(said.get("email") or booking.get("email"), 320)}]


def meeting_of(booking: dict) -> dict:
    """The scheduling link the booking was made on: {"id", "sid", "slug",
    "name"}; the slug is the last part of metadata.scheduling_link."""
    got = booking.get("meeting") if isinstance(booking.get("meeting"), dict) else {}
    out = {k: got.get(k) for k in ("id", "sid", "slug", "name")}
    meta = booking.get("metadata") if isinstance(booking.get("metadata"), dict) else {}
    link = meta.get("scheduling_link")
    if not out["slug"] and isinstance(link, str) and link.strip("/"):
        out["slug"] = link.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    if not out["name"] and isinstance(booking.get("meeting_name"), str):
        out["name"] = booking["meeting_name"]
    return out


def sample(site: str, now: float) -> dict:
    return {"webhook": {"source": "neetoCal", "method": "create", "sid": f"skald-test-{int(now)}",
                        "id": f"test-{int(now)}", "status": "confirmed",
                        "booked_on": when(int(now)), "name": "Test Person",
                        "email": "test@example.com",
                        "meeting": {"name": "Demo", "id": "test-meeting", "sid": "demo123"},
                        "metadata": {"scheduling_link": "https://example.neetocal.com/demo"},
                        "details": [{"field_code": "skv", "value": "skv_" + "A" * 22},
                                    {"field_code": "utm_source", "value": "newsletter"}]}}
