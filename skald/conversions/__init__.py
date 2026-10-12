"""Conversions: what visitors did that counts (a booking, a form, a payment),
pushed to Skald by the site's own server and by the tools it uses.

    hooks.py        the public receiver, POST /traffic-hooks/<site>/<tool>
    adapters/       one module per tool: its signature check and its mapping
    store.py        conversions.sqlite: conversions, journeys, identities, deliveries
    spool.py        the append-only record of every verified hook body
    normalise.py    a tool's record made into a stored row (country, device, source)
    geo.py          country from an address, read from the install's DB-IP file
    secrets_store.py  where each hook's secret lives

Anonymous by default: no name, email, address or user agent is stored, unless
a site turns on `conversions.identity: full` (then name and email only).

This file holds the name lists the main code and the second count
(audit_conversions.py) share. Nothing else is shared between the two.
"""
from __future__ import annotations

import re

# What happened to an action, in the order a report lists them. "won" and
# "lost" are a lead's outcome, set later by the team (the lead DB, a CRM).
STAGES = ("started", "completed", "cancelled", "rescheduled", "no_show", "paid", "won",
          "lost")
# A started action counts as finished (not abandoned) by one of these.
FINISHED = ("completed", "paid")
# Stages that are a later outcome of a finished action, never a finish themselves.
OUTCOMES = ("won", "lost")

# The tools a hook may name: /traffic-hooks/<site>/<tool>.
TOOLS = ("lead", "json", "calendly", "calcom", "stripe", "typeform", "hubspot")
# Tools whose body is Skald's own lead shape (adapters/lead.py).
LEAD_SHAPED = ("lead", "json")
# The site's own lead database (conversions/from_leads.py): not a hook.
LEADS_TOOL = "site"
# A lead's type -> (action, stage). A type not listed is its own action
# (aliased, when it is a token), completed.
LEAD_TYPES = {"demo_booked": ("demo", "completed"), "demo_opened": ("demo", "started"),
              "contact": ("contact", "completed"), "signup": ("signup", "completed"),
              "waitlist": ("waitlist", "completed")}
# A lead status that adds a row of that stage to a completed lead (same at).
LEAD_OUTCOMES = ("won", "lost")
# Statuses that are not leads: no row at all.
LEAD_EXCLUDED = ("spam", "duplicate")

# conversions.json's labels for what a row did not record, and its buckets.
UNKNOWN = "Unknown"
VISIT_BUCKETS = ("0", "1", "2", "3-5", "6-10", "11+", "unknown")
CONVERT_BUCKETS = ("<1h", "<1d", "1-7d", "8-30d", "31-90d", ">90d", "unknown", "clock_error")
# A rate is shown only over at least this many starts (or browsers).
MIN_RATE = 10

# One name per action, whatever tool reports it: a booked call is "demo"
# (Calendly, Cal.com, HubSpot meetings, the page's booking events), a
# payment "paid" (Stripe), a form "contact" or "signup". A name a site's
# own server or an older version used is read as the one here.
ALIASES = {"booking": "demo", "meeting": "demo", "demo_booked": "demo", "call_booked": "demo",
           "checkout": "paid", "payment": "paid", "form": "contact", "contact_form": "contact",
           "sign_up": "signup"}

# (tool, event) -> (action, stage). An event not listed is taken (the tool
# sent it, it was verified) and ignored.
EVENTS = {
    "calendly": {"invitee.created": ("demo", "completed"),
                 "invitee.canceled": ("demo", "cancelled"),
                 "invitee.canceled+rescheduled": ("demo", "rescheduled"),
                 "invitee_no_show.created": ("demo", "no_show")},
    "calcom": {"BOOKING_CREATED": ("demo", "completed"),
               "BOOKING_CANCELLED": ("demo", "cancelled"),
               "BOOKING_RESCHEDULED": ("demo", "rescheduled")},
    # A checkout finished but not yet paid (a bank debit) is a payment started.
    "stripe": {"checkout.session.completed": ("paid", "paid"),
               "checkout.session.completed+unpaid": ("paid", "started"),
               "checkout.session.async_payment_succeeded": ("paid", "paid")},
    "typeform": {"form_response": ("contact", "completed")},
    # "object.creation+0-47": a meeting booked (HubSpot's object type 0-47).
    # A workflow's webhook is "contact" unless its property skald_action
    # names another action.
    "hubspot": {"contact.creation": ("contact", "completed"),
                "object.creation+0-47": ("demo", "completed"),
                "deal.propertyChange+closedwon": ("deal", "won"),
                "workflow": ("contact", "completed")},
}
HUBSPOT_MEETING = "0-47"

# Beacon events (beacon.py) that are conversions, when visitor IDs are on:
# event -> (action, stage). Opening or starting is "started", sending or
# booking "completed". A tel:, mailto: or button click is the whole action
# as far as the page can see, so it is "completed" (never abandoned).
# page_view goes to journeys, not here. Kept only with a visitor ID.
BEACON_TOOL = "beacon"
BEACON_ACTIONS = {
    "form_start": ("contact", "started"), "form_submit": ("contact", "completed"),
    "contact_submit": ("contact", "completed"),
    "signup_start": ("signup", "started"), "signup_submit": ("signup", "completed"),
    "waitlist_submit": ("waitlist", "completed"),
    "calendly_open": ("demo", "started"), "calendly_time_selected": ("demo", "started"),
    "calendly_booked": ("demo", "completed"), "cal_open": ("demo", "started"),
    "cal_booked": ("demo", "completed"), "hubspot_meeting_booked": ("demo", "completed"),
    "book_demo_open": ("demo", "started"), "demo_booked": ("demo", "completed"),
    "tel_click": ("call", "completed"), "mailto_click": ("email", "completed"),
    "cta_click": ("cta", "completed"),
}
# One beacon conversion per (visitor ID, action, stage) within this many
# seconds of the last one kept: a second form focus or a reload is not a
# second start.
BEACON_REPEAT_SECONDS = 30 * 60

# A lead's action: a short lowercase token ("demo", "trial", "contact").
ACTION = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,39}$")


def action_name(raw) -> str:
    """A sender's action as Skald names it: lower case, ALIASES applied.
    Not checked against ACTION: the caller does that."""
    got = str(raw or "").strip().lower()
    return ALIASES.get(got, got)

# A Skald visitor ID: "skv_" and 16 random bytes in base64url (22 characters).
SKALD_VID = re.compile(r"^skv_[A-Za-z0-9_-]{16,43}$")
# What a site's own server may send as its visitor ID (example.com has its own).
SITE_VID = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")

# What a body may keep when it is spooled: per tool, the keys (at any depth)
# its adapter and the second count (audit_conversions.py) read. Everything
# else is dropped. Name and email are kept only when the site's identity is
# full, and then only the keys IDENTITY names (the primary email, never a
# second one). PERSONAL_* always go, whatever a list says.
_TOUCH = frozenset({"referrer", "landing", "utm_source", "utm_medium", "utm_campaign",
                    "utm_content", "utm_term", "gclid", "msclkid", "fbclid", "li_fat_id",
                    "at", "skv"})
_LEAD = frozenset({"external_ref", "action", "stage", "at", "vid", "first_touch",
                   "last_touch", "landing", "campaign", "source", "country", "device",
                   "visits_before", "first_touch_at"}) | _TOUCH
SPOOL_KEYS = {
    "lead": _LEAD,
    "json": _LEAD | {"records"},
    "calendly": frozenset({"event", "created_at", "payload", "rescheduled", "invitee", "uri",
                           "tracking"}) | _TOUCH,
    "calcom": frozenset({"triggerevent", "createdat", "payload", "uid", "metadata",
                         "responses", "value"}) | _TOUCH,
    "stripe": frozenset({"id", "object", "created", "type", "data", "payment_status",
                         "client_reference_id", "metadata"}) | _TOUCH,
    "typeform": frozenset({"event_id", "event_type", "form_response", "token",
                           "submitted_at", "hidden"}) | _TOUCH,
    "hubspot": frozenset({"objectid", "properties", "hs_object_id", "createdate",
                          "occurredat", "skald_action", "subscriptiontype", "propertyname",
                          "propertyvalue", "objecttypeid", "value"}) | _TOUCH,
}
SPOOL_KEYS_ANY = frozenset().union(*SPOOL_KEYS.values())
# Kept only as text: Calendly's no-show names its invitee by URL; the
# invitee's own events carry an object of personal data under this name.
TEXT_ONLY = frozenset({"invitee"})
# Identity full: the name and the primary email (HubSpot sends the name in two).
IDENTITY = frozenset({"name", "email", "firstname", "lastname"})
PERSONAL_EXACT = frozenset({"cancel_url", "reschedule_url"})
PERSONAL_PARTS = ("email", "phone")
PERSONAL_NAME_ENDS = ("_name", "fullname", "firstname", "lastname", "username")
_AGENT = re.compile(r"user.?agent")

MAX_BODY = 64 * 1024
TOLERANCE = 300            # seconds a signed timestamp may be off
FUTURE_SLACK = 86400       # an event more than a day after it arrived is refused


def _personal(low: str) -> bool:
    return (low in PERSONAL_EXACT or any(p in low for p in PERSONAL_PARTS)
            or low.startswith("ip") or bool(_AGENT.search(low)) or low == "name"
            or low.endswith(PERSONAL_NAME_ENDS))


def strip(value, identity_full: bool, tool: str | None = None):
    """A copy of a decoded JSON body with only the keys the tool's adapter
    and the audit read (SPOOL_KEYS; every tool's when `tool` is None), plus
    name and primary email when identity is full. Never an address, a user
    agent, a phone, another email or a cancel/reschedule link."""
    allowed = SPOOL_KEYS.get(tool, SPOOL_KEYS_ANY) if tool else SPOOL_KEYS_ANY
    return _strip(value, identity_full, allowed)


def _strip(value, identity_full: bool, allowed: frozenset):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            key_text = str(key)
            low = key_text.lower()
            if key_text in IDENTITY:          # exact: "Email" is not the primary email
                if identity_full and not isinstance(item, (dict, list)):
                    out[key] = item
                elif identity_full and isinstance(item, dict) and set(item) == {"value"}:
                    out[key] = {"value": item["value"]}     # HubSpot, Cal.com: {"value": ...}
                continue
            if _personal(low) or low not in allowed:
                continue
            if low in TEXT_ONLY and not isinstance(item, str):
                continue
            out[key] = _strip(item, identity_full, allowed)
        return out
    if isinstance(value, list):
        return [_strip(item, identity_full, allowed) for item in value]
    return value
