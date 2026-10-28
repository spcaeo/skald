"""The second count of the hold (2.45): refused hook deliveries kept 24 hours
for a key to be saved (conversions/held.py), and the ones taken in later
(conversions/key_check.py, delivery outcome `accepted_held`).

Its own road, sharing only the file locations (the history folder's
`hooks-held/`, the spool, conversions.sqlite) and the outcome names with the
main code:

  * accepted_held, two ways: the delivery log's rows with that outcome (this
    road's own SQL over the file opened read-only), against the spool's lines
    marked "held" (this road's own JSON reading, and audit_conversions' own
    reading of each tool's body: a line whose body it refuses, or that holds
    no event Skald counts, the main road logs as bad_body or ignored, never
    as accepted_held). Stripe's invoice_payment.paid holds no event but links
    a payment to its invoice, which the main road keeps (accepted_held too).
    Per tool, over the last AUDIT_DAYS days by when each first came.
  * a held file (or a claim left behind) that came more than HOLD_HOURS ago:
    the purge failed (run-daily purges before this runs).
  * a held body whose hook has no refusal row (unsigned or bad_signature)
    within REFUSAL_SLACK seconds before or after it came: a body kept that
    was never refused. The receiver writes at most one refusal row a minute
    per hook (with its count), so one always falls within the minute before.

`daily` is registered in audit_more.DAILY; a finding withholds nothing of the
conversion figures (audit_conversions.py recounts those), it ends run-daily
with exit 1 so the hold is looked at.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

AUDIT_DAYS = 30
HOLD_HOURS = 24                 # the rule held.py keeps to (DATA-CONTRACT.md)
REFUSAL_SLACK = 120             # seconds
FOLDER = "hooks-held"
OUTCOME = "accepted_held"
REFUSALS = ("unsigned", "bad_signature")
LINKS_ONLY = ("stripe", "invoice_payment.paid")


def _when(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def _held(folder: Path, site: str) -> list[dict]:
    """[{tool, at, file}] for every file in the site's hold, claims too, by
    this road's own reading: the file's received_at, else its mtime."""
    base = Path(folder) / FOLDER / site
    out = []
    if not base.is_dir():
        return out
    for tool_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for path in sorted(tool_dir.iterdir()):
            if not path.is_file() or path.name.startswith(".new-"):
                continue
            at = None
            try:
                got = json.loads(path.read_text(encoding="utf-8"))
                at = _when(got.get("received_at")) if isinstance(got, dict) else None
            except (OSError, ValueError):
                pass
            if at is None:
                try:
                    at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                except OSError:
                    continue
            out.append({"tool": tool_dir.name, "at": at, "file": path.name})
    return out


def _db(path) -> sqlite3.Connection | None:
    if path is None or not Path(path).is_file():
        return None
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def _refusals(db, site: str) -> dict[str, list[datetime]]:
    out: dict[str, list[datetime]] = {}
    if db is None:
        return out
    for tool, at in db.execute("SELECT tool, received_at FROM deliveries WHERE site = ? AND "
                               "outcome IN (?, ?)", (site, *REFUSALS)):
        got = _when(at)
        if got is not None:
            out.setdefault(tool, []).append(got)
    return out


def logged(db, site: str, since: datetime) -> dict[str, int]:
    """{tool: accepted_held rows} received since `since`, from the delivery log."""
    out: dict[str, int] = {}
    if db is None:
        return out
    for tool, at in db.execute("SELECT tool, received_at FROM deliveries WHERE site = ? AND "
                               "outcome = ?", (site, OUTCOME)):
        got = _when(at)
        if got is not None and got >= since:
            out[tool] = out.get(tool, 0) + 1
    return out


def spooled(spool: Path, site: str, since: datetime) -> dict[str, int]:
    """{tool: spool lines marked held, read to something the main road keeps}."""
    from .audit_conversions import _Bad, _lines, _read, _zone_of
    from .conversions import FUTURE_SLACK
    out: dict[str, int] = {}
    if not Path(spool).is_dir():
        return out
    for line in _lines(spool):
        if line.get("held") is not True or line.get("site") != site:
            continue
        tool, body = line.get("tool"), line.get("body")
        received = _when(line.get("received_at"))
        if not isinstance(tool, str) or received is None or received < since:
            continue
        if (tool, body.get("type") if isinstance(body, dict) else None) == LINKS_ONLY:
            out[tool] = out.get(tool, 0) + 1
            continue
        try:
            found = _read(tool, body, _zone_of(line))
        except _Bad:
            continue
        if not found or any(at is not None and at > received + timedelta(seconds=FUTURE_SLACK)
                            for *_, at in found):
            continue
        out[tool] = out.get(tool, 0) + 1
    return out


def findings(config: dict, folder: Path, site: str, now: float | None = None) -> list[str]:
    """The problems found for one site (empty: the hold matches)."""
    from .conversions import spool as spool_mod
    from .conversions import store
    stamp = datetime.fromtimestamp(time.time() if now is None else now, tz=timezone.utc)
    problems = []
    db = _db(store.path_for(config, Path(folder)))
    try:
        refused = _refusals(db, site)
        for entry in _held(folder, site):
            if entry["at"] < stamp - timedelta(hours=HOLD_HOURS):
                problems.append(f"hooks held: {site}/{entry['tool']}: a held delivery from "
                                f"{entry['at']:%Y-%m-%d %H:%M} UTC is past {HOLD_HOURS} hours")
            slack = timedelta(seconds=REFUSAL_SLACK)
            if not any(entry["at"] - slack <= at <= entry["at"] + slack
                       for at in refused.get(entry["tool"], ())):
                problems.append(f"hooks held: {site}/{entry['tool']}: a held delivery from "
                                f"{entry['at']:%Y-%m-%d %H:%M} UTC has no refusal in the "
                                "delivery log")
        since = stamp - timedelta(days=AUDIT_DAYS)
        rows = logged(db, site, since)
    finally:
        if db is not None:
            db.close()
    lines = spooled(spool_mod.spool_dir(config, Path(folder)), site, since)
    for tool in sorted(set(rows) | set(lines)):
        if rows.get(tool, 0) != lines.get(tool, 0):
            problems.append(f"hooks held: {site}/{tool}: {rows.get(tool, 0)} taken in by the "
                            f"delivery log, {lines.get(tool, 0)} held lines in the spool")
    return problems


def set_up(ctx) -> bool:
    """Whether the site has a hold or a conversions file to check."""
    from .conversions import store
    folder = ctx.db_path.parent
    return (folder / FOLDER / ctx.site).is_dir() or store.path_for(ctx.config, folder).exists()


def daily(ctx, day: date) -> list[str] | None:
    """run-daily's step (audit_more.DAILY): the hold and what it let in."""
    return findings(ctx.config, ctx.db_path.parent, ctx.site)

