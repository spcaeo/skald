"""Recorded journeys' doctor line (doctor.integration_checks: Settings › Leads & tools'
checks, and the set-up checklist's optional "Recorded journeys" line, setup_items.py).

    journeys   none when the site has no journey secret (it is optional and off);
               OK when an event came in the last FRESH_DAYS days; OFF while the site
               waits for its first event; NEEDS ATTENTION when events stopped
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import TOOL

FRESH_DAYS = 7
PART = "Recorded journeys"


def doctor_line(site_config: dict, folder, site: str, now: datetime | None = None):
    from ..conversions.secrets_store import find
    from ..conversions.store import parse, path_for
    from ..doctor import ATTENTION, OFF, OK, _ago, item
    now = now or datetime.now(timezone.utc)
    if not find(site_config, Path(folder), site, TOOL)[0]:
        return None
    last = None
    path = path_for(site_config, Path(folder))
    if path is not None and Path(path).is_file():
        db = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        try:
            have = db.execute("SELECT 1 FROM sqlite_master WHERE name = 'recorded_events'").fetchone()
            if have:
                last = db.execute("SELECT MAX(received_at) FROM recorded_events WHERE site = ?",
                                  (site,)).fetchone()[0]
        finally:
            db.close()
    if not last:
        return item("journeys", PART, OFF, "connected; waiting for the first event from the site",
                    "Put the page helper and the relay on the site (Settings > Leads & tools > "
                    "Recorded journeys), then accept analytics in a browser.")
    when = parse(last)
    if now - when <= timedelta(days=FRESH_DAYS):
        return item("journeys", PART, OK, f"the last event came {_ago(when.isoformat(), now)}")
    return item("journeys", PART, ATTENTION, f"no event since {_ago(when.isoformat(), now)}",
                "Check that the site's relay still sends (its SKALD_JOURNEY_URL and "
                "SKALD_JOURNEY_SECRET) and that its consent banner still calls the helper.")
