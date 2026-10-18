"""How a stored label is shown to a person.

History keeps the names it was written with: the source "Direct or unknown"
and "Unknown" (a country, device or touch the log or the tool did not record)
are in the store's rows, the journeys, the conversions' source_type and the
beacon spool, and the audit compares them. Renaming them would split old days
from new ones, so the stored names never change; what a person reads does:

    shown("Direct or unknown")  -> "Direct"
    shown("Unknown")            -> "Not recorded"

Every place that shows or exports a stored label to a person (the mails, the
CSV files, the MCP answers) passes it through shown(). The web app has the
same table in webapp/js/labels.js. Filters and drills keep the stored value;
stored() turns the shown words back into it.
"""

from __future__ import annotations

import re

SHOWN = {
    "Direct or unknown": "Direct",
    "direct or unknown": "direct",
    "Unknown": "Not recorded",
    "unknown": "not recorded",
    "(unknown)": "(not recorded)",
}
STORED = {v: k for k, v in SHOWN.items()}
_DIRECT = re.compile(r"\b([Dd])irect or unknown\b")


def shown(value):
    """A stored label in the words a person reads; anything else as it is."""
    return SHOWN.get(value, value) if isinstance(value, str) else value


def shown_text(text):
    """shown(), and a sentence that names the direct source inside it."""
    if not isinstance(text, str):
        return text
    if text in SHOWN:
        return SHOWN[text]
    return _DIRECT.sub(r"\1irect", text) if "irect or unknown" in text else text


def stored(value):
    """The stored name for shown words ("Direct" -> "Direct or unknown")."""
    return STORED.get(value, value) if isinstance(value, str) else value


def shown_keys(obj):
    """A dict's keys (nested too) and string values as shown, for JSON a person reads."""
    if isinstance(obj, dict):
        return {shown(k): shown_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shown_keys(v) for v in obj]
    return shown(obj)
