"""The name lists: the one thing recount.py shares with the code it checks.

Nothing here counts, reads or parses. A list is a name a tool uses in its own
answers (GA4's metric and dimension names) or a word every screen shows.
"""
from __future__ import annotations

# The label every figure from a tool carries: "Counted from: Google Analytics".
COUNTED_FROM = "Counted from"
LOG_SOURCE = "your server log"

# Google Analytics 4 (tool_ga4.py): the reports Skald asks for, each one runReport
# with these dimensions and metrics, in this order (docs/TOOLS.md).
GA4_METRICS = ("sessions", "totalUsers", "engagedSessions", "keyEvents")
GA4_ROW_METRICS = ("sessions", "keyEvents")
GA4_REPORTS = {
    "totals": ((), GA4_METRICS),
    "landing": (("landingPage",), GA4_ROW_METRICS),
    "sources": (("sessionSourceMedium",), GA4_ROW_METRICS),
}
GA4_TOP = 10                       # rows asked for in landing and sources
GA4_DAYS = 28                      # the window: the last 28 whole days, GA4's own days
GA4_LABELS = {"sessions": "Sessions", "totalUsers": "Users",
              "engagedSessions": "Engaged sessions", "keyEvents": "Key events"}
# What GA4 says about its own answer (runReport's metadata), shown beside its figures.
GA4_FLAGS = {"subjectToThresholding": "Thresholded: Google hid some small numbers",
             "samplingMetadatas": "Sampled: Google counted part of the data",
             "dataLossFromOtherRow": "Some rows were folded into (other)"}

# A row the tool named with nothing (Vercel's direct visits have no referrer).
NONE_DIM = "(none)"

# Vercel Web Analytics (tool_vercel.py): the documented Web Analytics API. "totals" is
# visits/count (Vercel's own distinct visitors over the window); each other report is
# visits/aggregate by one dimension, the top VERCEL_TOP, the rest in Vercel's "Others".
VERCEL_METRICS = ("visitors", "pageviews")
VERCEL_REPORTS = {"totals": None, "pages": "requestPath", "referrers": "referrerHostname",
                  "countries": "country"}
VERCEL_TOP = 10
VERCEL_DAYS = 28
VERCEL_LABELS = {"visitors": "Visitors", "pageviews": "Page views"}

# Calendly (tool_calendly.py): one report, "totals", over meetings that start from
# CALENDLY_PAST days ago to CALENDLY_AHEAD days ahead (UTC). Each figure is a count of
# the answer's meetings (events) or invitees, by these rules, read by the audit too:
#   bookings        every meeting in the window, any status
#   upcoming        status "active", start_time at or after `asked_at`
#   past            status "active", start_time before `asked_at` (held, or a no-show)
#   canceled        status "canceled"
#   no_shows        invitees of past active meetings with a no_show; NULL unless every
#                   past active meeting's invitees were read
#   booked_7d       meetings made (created_at) in the 7 whole UTC days before asked_at's
#   booked_prev_7d  the 7 days before those
#   bookings / dim  each event type's name (the meeting's "name"): its meetings
# NULL for every count when the answer is not complete (more pages than Skald reads).
CALENDLY_PAST = 90
CALENDLY_AHEAD = 60
CALENDLY_COUNTS = ("bookings", "upcoming", "past", "canceled", "no_shows", "booked_7d",
                   "booked_prev_7d")
CALENDLY_LABELS = {"bookings": "Bookings", "upcoming": "Upcoming", "past": "Past",
                   "canceled": "Canceled", "no_shows": "No-shows",
                   "booked_7d": "Booked, last 7 days", "booked_prev_7d": "Booked, 7 days before"}
CALENDLY_ACTIVE, CALENDLY_CANCELED = "active", "canceled"

# Resend (tool_resend.py): three reports.
#   totals    contacts: every contact; subscribed (unsubscribed is false); unsubscribed
#             (true). NULL when not every page was read
#   segments  contacts / dim: each segment's name, its contacts (NULL: not every page read)
#   emails    emails: the recent emails read (Resend's newest RESEND_EMAILS);
#             emails / dim: each `last_event` (delivered, bounced...), its emails
RESEND_TOTALS = ("contacts", "subscribed", "unsubscribed")
RESEND_EMAILS = 100
RESEND_LABELS = {"contacts": "Contacts", "subscribed": "Subscribed",
                 "unsubscribed": "Unsubscribed", "emails": "Recent emails"}

# What a tool said about its own answer, in plain words (every tool's flags).
TOOL_FLAGS = {**GA4_FLAGS,
              "incomplete": "Not every page was read: Skald shows no count rather than a "
                            "short one",
              "no_shows_partial": "No-shows are not counted: too many past meetings to read",
              "others": "The rest are folded into Others, as the tool does",
              "recent_only": "Only the most recent emails: Resend lists them newest first"}
