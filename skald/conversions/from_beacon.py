"""Beacon events made into journeys and conversions (Phase 4b, build step 2).

Only when `beacon.visitor_ids` is true and the event carries a visitor ID
(`v`, made by skald.js or the site's own code) and came from people (not
our own addresses, not bots). The beacon helper calls `record` right after
it spools the event, under the same lock, so the store sees the events in
the spool's order:

  page_view             one row in `journeys` (path, the visit's source and
                        referring host; since 2.45 its campaign, from the
                        tag's utm_ tags and the ad click's kind, and, while
                        the site keeps click IDs, the ad click itself)
  BEACON_ACTIONS        one conversion (tool "beacon"), at most one per
                        (visitor ID, action, stage) within
                        BEACON_REPEAT_SECONDS of the last one kept
  anything else         nothing

Country comes from the request's address (geo.py, `conversions.country_db`)
and device from its user agent, through normalise.row like a hook's
record; both are then dropped, never stored. Landing is the first page of
the visit as the journeys know it (page views no more than 30 minutes
apart); without journeys it is NULL. Its first source, campaign, first
touch time and ad click come from the same journeys (fill.py, 2.45).

The second count (audit_conversions.recount_beacon) reads the spool by its
own road and shares only conversions/__init__.py's name lists.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from urllib.parse import urlencode

from ..config import setting
from ..dimensions import campaign
from . import BEACON_ACTIONS, BEACON_REPEAT_SECONDS, BEACON_TOOL, VISIT_GAP, fill, store
from .normalise import row as make_row

PAGE_VIEW = "page_view"


def abandon_hours(config: dict) -> float:
    """`conversions.abandon_hours` (default 24)."""
    return float(setting(config or {}, "conversions", "abandon_hours", store.ABANDON_HOURS))


def vid_days(config: dict) -> int:
    """`journeys.vid_days` (default 30): how long an ID's page views are kept
    when it never converted (store.vid_days)."""
    return store.vid_days(config)


def abandoned(db, config: dict, site: str, since: str, until: str,
              now: str | None = None) -> list[dict]:
    """Starts in [since, until) not finished within `conversions.abandon_hours`,
    worked out now (store.abandoned), never stored."""
    return store.abandoned(db, site, since, until, abandon_hours(config), now)


def _landing(db, site: str, vid: str, at: str) -> str | None:
    """The first page of the visit that holds `at`, from the journeys."""
    pages = db.execute("SELECT at, path FROM journeys WHERE site = ? AND vid = ? AND at <= ? "
                       "ORDER BY at DESC LIMIT 200", (site, vid, at)).fetchall()
    if not pages:
        return None
    landing, before = None, store.parse(at)
    for when, path in pages:
        moment = store.parse(when)
        if (before - moment).total_seconds() > VISIT_GAP:
            break
        landing, before = path, moment
    return landing


def visit_campaign(event: dict, click: str = "") -> str:
    """A page view's campaign label (dimensions.campaign, as the log names a
    reader's): the tag's utm_source (`u`), utm_medium (`m`) and utm_campaign
    (`c`), else its ad click's kind (`k`)."""
    tags = [(k, event[f]) for k, f in (("utm_source", "u"), ("utm_medium", "m"),
                                       ("utm_campaign", "c")) if event.get(f)]
    kind = str(click or "").partition(":")[0]
    if kind:
        tags.append((kind, "1"))
    return campaign("/?" + urlencode(tags) if tags else "/")


def record(db, site: str, event: dict, when: datetime, source: str | None,
           own_hosts: set[str], country_db=None, address: str = "",
           agent: str = "", click: str = "", clicks: bool = False) -> str | None:
    """Keep what one accepted beacon event means for journeys and
    conversions. Returns "journey", "conversion", "repeat" or None. `click`:
    the tag's `k` (never in the spool); its ID is kept only with `clicks`
    (the site's `conversions.click_ids`)."""
    vid = event.get("v")
    if not vid:
        return None
    at = store.stamp(when)
    if event.get("e") == PAGE_VIEW:
        store.record_page_view(db, site, vid, at, event["p"], source,
                               str(event.get("r") or "")[:60], visit_campaign(event, click),
                               fill.click_text(click) if clicks else None)
        return "journey"
    pair = BEACON_ACTIONS.get(event.get("e"))
    if pair is None:
        return None
    action, stage = pair
    with store.tx(db):
        edge = store.stamp(store.parse(at) - timedelta(seconds=BEACON_REPEAT_SECONDS))
        if db.execute("SELECT 1 FROM conversions WHERE site = ? AND tool = ? AND vid = ? AND "
                      "action = ? AND stage = ? AND at > ?",
                      (site, BEACON_TOOL, vid, action, stage, edge)).fetchone():
            return "repeat"
        rec = {"action": action, "stage": stage, "at": at, "vid": vid,
               "external_ref": f"{vid}:{action}:{stage}:{at}", "source_type": source,
               "landing": _landing(db, site, vid, at), "ip": address, "user_agent": agent}
        row = make_row(rec, site, BEACON_TOOL, at, own_hosts, False, country_db)
        store.record_conversion(db, fill.apply(db, row, clicks))
    return "conversion"


# ------------------------------------------------------------------ forget

def scrub_spool(spool: Path, vids: set[str], dry_run: bool = False) -> int:
    """Take the visitor ID out of every beacon spool line that carries one
    of `vids` (lower case). The line itself stays: the event audit counts it
    against nginx's beacon log. Lines changed. A file is rewritten only when
    it holds one of the IDs."""
    changed = 0
    if not vids or not Path(spool).is_dir():
        return 0
    for path in sorted(Path(spool).glob("*.jsonl")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not any(v in text.lower() for v in vids):
            continue
        out, hits = [], 0
        for raw in text.splitlines(keepends=True):
            try:
                row = json.loads(raw)
            except ValueError:
                out.append(raw)
                continue
            if isinstance(row, dict) and str(row.get("v", "")).lower() in vids:
                row.pop("v")
                hits += 1
                out.append(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
            else:
                out.append(raw)
        if hits and not dry_run:
            _rewrite(path, "".join(out))
        changed += hits
    return changed


def _rewrite(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
