"""The names of "Hidden referral" (SKALD-69, GitHub #118).

A page view that arrives with no referrer, no campaign tag and no ad click id
was "Direct or unknown": a typed address, a bookmark, a link opened from an
app, and also a click on another website that hid its address
(rel="noreferrer", a no-referrer policy, some Google AI Mode clicks). The
browser's Sec-Fetch-Site request header tells the last apart: a click from
another site sends "cross-site"; a typed address, a bookmark or a link an app
opened sends "none". So a page view with no referrer and no tag whose
Sec-Fetch-Site is "cross-site" is a "Hidden referral". Every other one stays
"Direct or unknown", shown as "Direct": "none", any other value, and a line
that does not record the header (an older browser, most bots, a day before
the log carried it, a log source with no request headers).

It says only that the visitor clicked a link somewhere that hid itself. It
never says where, and never "AI Mode".

Like Direct (owner's decision, 27 Nov 2026), a Hidden referral never opens a
new visit inside the visit gap, so visit counts do not change; only the first
page's source does. "Likely sent by an AI assistant" looks at both Direct and
Hidden referral visits (a hidden click from an answer is what it looks for);
"Direct, likely <reason>" explains the Direct row only.

Names only: the main road (parse.py, parse_drains.py, ingest_drain.py,
dimensions.py, ai_likely.py, conversions_data.py) and the second counts
(audit_labels.py, audit.py, audit_ai_likely.py, audit_conversions_figures.py)
each apply them with their own code, so this is all they share. The audit's
line readers (audit_lines.py, audit_drains.py) import nothing and write the
field names again.

A stored day records that it was counted with this rule ("hidden_referral" in
its quality blob); the audit recounts a day stored before without it, as it
was counted (audit_rules, via audit_labels.hidden_counted): a Caddy log held the header before.

  HIDDEN       the source's stored and shown name
  CROSS_SITE   the Sec-Fetch-Site value that makes one
  FIELD        the log line's field that records the header (nginx
               ` sec_fetch_site=$http_sec_fetch_site`, docs/INGEST.md); an
               edge record's key is EDGE_KEY, Caddy logs the header itself
"""
from __future__ import annotations

HIDDEN = "Hidden referral"
CROSS_SITE = "cross-site"
FIELD = "sec_fetch_site="
EDGE_KEY = "fetch_site"
HEADER = "sec-fetch-site"
