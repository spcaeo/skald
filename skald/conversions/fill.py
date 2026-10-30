"""A lead's touches filled from its visitor ID's page views (2.45).

A lead sent with a visitor ID (`vid`) and no touches (no first_touch, no
last_touch, no source) read "Unknown" everywhere, though Skald keeps that
browser's page views (`journeys`, from the script tag). Now they fill it:

    first touch   the ID's earliest page view at or before the conversion's
                  `at`: first_source (its source type), first_touch_at (its
                  time) and landing (its page)
    last touch    the latest visit at or before `at` (page views no more than
                  VISIT_GAP apart are one visit), by its first page view:
                  source_type (its source type) and campaign (its campaign
                  label; NULL on a page view from a tag older than 2.45)
    click         the last touch's ad click (click_kind, click_id), else the
                  first touch's: only while the site keeps click IDs
                  (`conversions.click_ids`)

Only by the visitor ID: never by an address, a hash or a time match. Only
page views at or before `at`: a later one never changes a lead. A value the
sender gave is never changed: a lead whose sender gave a touch (or a source)
is not filled at all, and a column the sender gave on its own (landing,
campaign, first_touch_at, the click) stays. A script-tag conversion (tool
"beacon") keeps its own event's source and landing: only FILLED_BEACON
(first_source, campaign, first_touch_at, click) are filled.

`filled` names the columns Skald filled (FILLABLE's order, comma-joined), so
the lists and the drawer say "filled by Skald"; NULL when none. A column is
the sender's when it holds a value and `filled` does not name it.

When:
    at intake   hooks.py, from_beacon.py and from_leads.py fill a new row
                before it is stored (`apply`)
    each run    `refresh` (conversions/jobs.py: `skald live` the last two
                days' rows, run-daily every row) fills again every row that
                may be filled, from the page views kept now: a page view that
                arrived after the lead (a slow beacon) fills it, one taken
                away (retention) unfills it. It runs before the second count:
                audit_filled.py works the same columns out by its own road,
                and a day it disagrees with is withheld.

With click IDs off, `refresh` also clears every click ID the site kept (its
conversions, page views and removed rows): turning the setting off deletes
them at the next run.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from ..config import setting
from . import BEACON_TOOL, CLICK_ID, CLICK_KINDS, FILLABLE, FILLED_BEACON, VISIT_GAP, store

LIVE_DAYS = 2           # `skald live` refreshes the rows of the last two days


def keep_clicks(config: dict | None) -> bool:
    """`conversions.click_ids` (default off): keep the ad click ID on a
    conversion, and on the page views it is filled from."""
    return setting(config or {}, "conversions", "click_ids", False) in (True, "true")


def click_text(text) -> tuple[str, str] | None:
    """The script tag's `k` ("gclid:<id>") as (kind, id); None for a kind
    alone (sent while the site keeps none) or anything else."""
    kind, _, value = str(text or "").partition(":")
    return (kind, value) if kind in CLICK_KINDS and CLICK_ID.match(value) else None


def _named(filled) -> set[str]:
    return set(str(filled).split(",")) if filled else set()


def touches(db, site: str, vid: str, at: str) -> dict | None:
    """Every FILLABLE column from the ID's page views at or before `at`
    (None where they hold none); None when it has no page view."""
    first = db.execute("SELECT at, path, source_type, click_kind, click_id FROM journeys "
                       "WHERE site = ? AND vid = ? AND at <= ? ORDER BY at, rowid LIMIT 1",
                       (site, vid, at)).fetchone()
    if first is None:
        return None
    last, before = None, None
    for row in db.execute("SELECT at, source_type, campaign, click_kind, click_id FROM "
                          "journeys WHERE site = ? AND vid = ? AND at <= ? "
                          "ORDER BY at DESC, rowid DESC", (site, vid, at)):
        moment = store.parse(row[0])
        if before is not None and (before - moment).total_seconds() > VISIT_GAP:
            break
        last, before = row, moment
    click = next(((k, v) for k, v in ((last[3], last[4]), (first[3], first[4])) if k and v),
                 None)
    return {"source_type": last[1], "first_source": first[2], "campaign": last[2],
            "landing": first[1], "first_touch_at": first[0], "click": click}


def fillable(row, clicks: bool | None) -> tuple[str, ...]:
    """The columns Skald may fill on `row` (a conversion, dict or Row): see
    the module. () for a row without a visitor ID or with the sender's touches.
    `clicks` None: the click is left as it is (neither filled nor cleared)."""
    if not row["vid"]:
        return ()
    named = _named(row["filled"] if "filled" in row.keys() else None)
    if row["tool"] == BEACON_TOOL:
        base = FILLED_BEACON
    elif all(row[c] is None or c in named for c in ("source_type", "first_source")):
        base = FILLABLE
    else:
        return ()
    return tuple(c for c in base if (clicks or c != "click") and (
        c in named or (row["click_id"] if c == "click" else row[c]) is None))


def _values(db, row, clicks: bool | None) -> dict | None:
    """{column: value} for the columns `row` may have filled, and "filled";
    None when none may be."""
    cols = fillable(row, clicks)
    if not cols:
        return None
    got = touches(db, row["site"], row["vid"], row["at"]) or {}
    out = {}
    done = ["click"] if clicks is None and "click" in _named(row["filled"]) else []
    for col in cols:
        value = got.get(col)
        if col == "click":
            out["click_kind"], out["click_id"] = value or (None, None)
        else:
            out[col] = value
        if value is not None:
            done.append(col)
    out["filled"] = ",".join(c for c in FILLABLE if c in done) or None
    return out


def apply(db, rec: dict, clicks: bool | None) -> dict:
    """A new row (normalise.row's shape) with its touches filled, before
    store.record_conversion keeps it."""
    row = {"filled": None, "click_id": None, **rec}
    got = _values(db, row, clicks)
    if got:
        rec.update(got)
    return rec


def refresh(db, site: str, clicks: bool | None, since: str | None = None) -> int:
    """Fill again every row of `site` that may be filled (at or after `since`)
    from the page views kept now; with click IDs off (False), first clear them
    all (clear_clicks); None leaves every click as it is (the prune, which does
    not know each site's setting). Rows changed."""
    changed = clear_clicks(db, site) if clicks is False else 0
    sql = ("SELECT id, site, tool, vid, at, source_type, first_source, campaign, landing, "
           "first_touch_at, click_kind, click_id, filled FROM conversions WHERE site = ? AND "
           "vid IS NOT NULL")
    args: list = [site]
    if since:
        sql += " AND at >= ?"
        args.append(since)
    with store.tx(db):
        for row in db.execute(sql, args).fetchall():
            got = _values(db, row, clicks)
            if got is None or all(row[k] == v for k, v in got.items()):
                continue
            db.execute(f"UPDATE conversions SET {', '.join(f'{k} = ?' for k in got)} "
                       f"WHERE id = ?", (*got.values(), row["id"]))
            changed += 1
    return changed


def clear_clicks(db, site: str, before: str | None = None) -> int:
    """Every click ID of `site` (on rows with `at` before `before`, when
    given) taken away: its conversions, page views and removed rows, and
    "click" from `filled`. Conversion rows changed."""
    when, args = (" AND at < ?", [before]) if before else ("", [])
    with store.tx(db):
        n = 0
        for rid, filled in db.execute(
                f"SELECT id, filled FROM conversions WHERE site = ? AND (click_id IS NOT NULL "
                f"OR click_kind IS NOT NULL){when}", [site, *args]).fetchall():
            left = ",".join(c for c in FILLABLE if c in _named(filled) and c != "click")
            db.execute("UPDATE conversions SET click_kind = NULL, click_id = NULL, filled = ? "
                       "WHERE id = ?", (left or None, rid))
            n += 1
        db.execute(f"UPDATE journeys SET click_kind = NULL, click_id = NULL WHERE site = ? "
                   f"AND click_id IS NOT NULL{when}", [site, *args])
        for rid, text in db.execute(
                f"SELECT id, row FROM removed WHERE site = ? AND row LIKE '%click_id%'"
                f"{when}", [site, *args]).fetchall():
            try:
                kept = json.loads(text)
            except (TypeError, ValueError):
                continue
            if isinstance(kept, dict) and (kept.get("click_id") or kept.get("click_kind")):
                kept["click_kind"] = kept["click_id"] = None
                db.execute("UPDATE removed SET row = ? WHERE id = ?",
                           (json.dumps(kept, sort_keys=True), rid))
    return n


def live_since(now: datetime) -> str:
    """The first moment `skald live` refreshes (LIVE_DAYS before `now`)."""
    return (now.astimezone(timezone.utc) - timedelta(days=LIVE_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
