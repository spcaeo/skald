"""Recorded journeys (2.43): consented browser sessions a website sends Skald itself.

The owner's decision (2026-10-27): data a site sends about its own visitors may feed
Skald, labelled by where it came from ("Recorded by your site") and never mixed into
the log's counts. Kept raw, recounted by an independent second road
(audit_journeys.py), unknown stays unknown. docs/JOURNEYS.md says it for people.

    contract.py   what one event may hold (version 1): fixed facts, never form data
    receive.py    POST /traffic-hooks/<site>/journey and .../journey/withdraw, signed
                  with the site's own secret (secrets.json "hooks/<site>/journey")
    store.py      the tables in conversions.sqlite: each event raw, its columns,
                  withdrawals (a keyed digest, never the ID), retention
    queries.py    the sessions and their figures, for the dashboard (journeys_api.py)

This file holds the name lists the main code and the second count share. Nothing
else is shared between the two roads.
"""
from __future__ import annotations

VERSION = 1
# The secret's name: secrets.json "hooks/<site>/journey" (secrets_store.key), made in
# Settings › Leads & tools › Recorded journeys or by the agent line's connect-journeys job.
TOOL = "journey"
LABEL = "Recorded by your site"

# What a page may say happened. Fixed facts only: a form's answers never come here.
EVENTS = ("session_started", "page_view", "cta_click", "form_sent", "signup",
          "booking_opened", "booking_made", "download")
# Events whose page the person gave an email on (kept only when the site keeps identity).
EMAIL_EVENTS = ("form_sent", "signup", "booking_made")
# How a session ended, best first: the drawer's and the list's words come from this order.
ENDINGS = ("booking_made", "signup", "form_sent", "download", "booking_opened", "cta_click")

FIELDS = ("schema_version", "event_id", "event_name", "occurred_at", "visitor_id",
          "session_id", "path", "consent", "label", "touch", "skald_vid", "ip", "email")
WITHDRAW_FIELDS = ("schema_version", "visitor_id", "occurred_at", "consent")
CONSENT_FIELDS = ("analytics", "notice_version")
GRANTED = "granted"
WITHDRAWN = "withdrawn"
TOUCH_FIELDS = ("landing_path", "referrer", "utm_source", "utm_medium", "utm_campaign",
                "utm_content", "utm_term")
REFERRER_FIELDS = ("host", "path")
# The columns each stored event's raw JSON is projected to (store.py), in order.
COLUMNS = ("event_id", "event_name", "occurred_at", "visitor_id", "session_id", "path",
           "skald_vid", "ip", "email")

MAX_BODY = 16 * 1024          # one event, bytes
SIGN_WINDOW = 300             # seconds either side of now for X-Skald-Timestamp
MAX_AGE_DAYS = 7              # an event may arrive this late (a retry queue), never later
FUTURE_SECONDS = 300          # nor more than five minutes ahead
TOMBSTONE_DAYS = 90           # a withdrawn visitor's later retries are refused this long
