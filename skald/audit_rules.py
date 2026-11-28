"""Which rules a stored day, or a live snapshot, was counted by: the audit recounts it by
the same ones (audit.recount's `cdn`, `agent_lists` and `hidden`), so a good day is never withheld
for a rule that came after it.

  cdn          SKALD-17's CDN rules, with a CDN list at hand: its quality blob holds
               "cdn_lines" as a number (a day stored before has no such key, one counted
               without a list holds null).
  agent_lists  Claude-User's own address lists (bot_verify.AGENT_LISTS, SKALD-52): its
               bots blob holds "agent_lists" (the lists at hand, maybe none). A day stored
               before has no such key.
  hidden       the Hidden referral rule (SKALD-69): its quality blob says
               "hidden_referral": true (audit_labels.hidden_counted). A day stored before
               is recounted without it: a Caddy log held Sec-Fetch-Site before Skald read it.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from .audit_labels import hidden_counted


def counted_with_cdn(quality_blob) -> bool:
    return isinstance(quality_blob, dict) and quality_blob.get("cdn_lines") is not None


def counted_with_agent_lists(bots_blob) -> bool:
    return isinstance(bots_blob, dict) and "agent_lists" in bots_blob


def rules_of(extras) -> dict:
    """recount()'s rule switches for a live snapshot, from its extras."""
    extras = extras if isinstance(extras, dict) else {}
    return {"cdn": counted_with_cdn(extras.get("quality")),
            "agent_lists": counted_with_agent_lists(extras.get("bots")),
            "hidden": hidden_counted(extras.get("quality"))}


def stored_rules(db_path, site: str, day: date) -> dict:
    """recount()'s rule switches for a stored day, from its day_extras rows. A rule whose
    row is missing (or a day not stored, or a store that cannot be read) is on: there is
    nothing old to protect."""
    got: dict = {}
    try:
        db = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
        try:
            got = dict(db.execute("SELECT kind, data FROM day_extras WHERE site = ? AND "
                                  "day = ? AND kind IN ('quality', 'bots')",
                                  (site, day.isoformat())).fetchall())
        finally:
            db.close()
    except (sqlite3.Error, OSError):
        pass
    out = {}
    for rule, kind, test in (("cdn", "quality", counted_with_cdn),
                             ("agent_lists", "bots", counted_with_agent_lists),
                             ("hidden", "quality", hidden_counted)):
        try:
            out[rule] = test(json.loads(got[kind])) if kind in got else True
        except (TypeError, ValueError):
            out[rule] = True
    return out
