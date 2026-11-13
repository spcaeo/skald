"""When each scheduled job last succeeded or failed (quality.json `runs`).

One small JSON file beside the history, `runs.json`, rewritten atomically
by each command at its end: {name: {"last_ok", "last_fail", "last_exit"}}.
It holds times and exit codes only, and for run-daily `last_outcome`: ok,
waiting (a site made from the dashboard with no log line yet, exit 0),
withheld (stopped by design: a day that does not reconcile, or a mail refused
for its data) or failed, which the failure mail reads (failmail.py); and
`last_step` / `last_reason`: the step it stopped at and why, in one line
(null when it ran to the end), which `skald doctor` shows.

On each success it also keeps `gaps_s`: the seconds between the last few
successes (#54). A live round of many sites takes longer than the two
minutes it is planned for, so "next" and "late" use the measured gap
(`every_s`), never less than the plan.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .files import write_atomic

FILE = "runs.json"

# How often each job is meant to run, in minutes (for "late" in the panel).
EXPECTED = {"live": 2, "run-daily": 1440, "verify-bots": 1440, "alerts": 2,
            "backup": 1440, "pagespeed": 1440, "heartbeat": 5}
GAPS = 6                 # the last few gaps between successes, kept
LONGEST_GAP_S = 6 * 3600  # a longer gap is a stopped server, not a round


def path_for(directory: Path) -> Path:
    return Path(directory) / FILE


def load(directory: Path) -> dict:
    try:
        got = json.loads(path_for(directory).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def record(directory: Path | None, name: str, code: int, now: datetime | None = None,
           outcome: str | None = None, step: str | None = None,
           reason: str | None = None) -> None:
    """Note that job `name` ended with exit `code`. With an `outcome`, also
    the step it stopped at and the one-line reason (both null when given
    none). Never raises: a job's bookkeeping must not turn a success into a
    failure."""
    if directory is None:
        return
    try:
        runs = load(directory)
        at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        entry = runs.setdefault(name, {"last_ok": None, "last_fail": None, "last_exit": None})
        entry["last_exit"] = int(code)
        if code == 0:
            _note_gap(entry, at)
        entry["last_ok" if code == 0 else "last_fail"] = at
        if outcome is not None:
            entry["last_outcome"] = outcome
            entry["last_step"] = step
            entry["last_reason"] = one_line(reason)
        write_atomic(path_for(directory), json.dumps(runs, indent=1, sort_keys=True) + "\n")
    except OSError:
        pass


def _note_gap(entry: dict, at: str) -> None:
    """Keep the gap from the last success to this one, in seconds."""
    try:
        gap = (datetime.fromisoformat(at) - datetime.fromisoformat(entry["last_ok"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        return
    if 0 < gap <= LONGEST_GAP_S:
        kept = [g for g in entry.get("gaps_s") or [] if isinstance(g, (int, float))]
        entry["gaps_s"] = (kept + [round(gap)])[-GAPS:]


def measured_s(entry: dict | None) -> float | None:
    """The median gap between a job's successes, in seconds; None until
    two gaps are known."""
    gaps = sorted(g for g in (entry or {}).get("gaps_s") or [] if isinstance(g, (int, float)))
    if len(gaps) < 2:
        return None
    mid = len(gaps) // 2
    return float(gaps[mid] if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) / 2)


def every_s(state: dict | None, name: str, planned_min: float | None = None) -> float | None:
    """How often job `name` really runs, in seconds: the measured gap, never
    below the plan; the plan until it is measured (None for no plan)."""
    planned = planned_min if planned_min is not None else EXPECTED.get(name)
    got = measured_s((state or {}).get(name))
    if planned is None:
        return got
    return max(planned * 60.0, got or 0.0)


def one_line(text) -> str | None:
    """The first line of a reason, at most 300 characters; None for none."""
    if not text:
        return None
    line = str(text).strip().splitlines()[0] if str(text).strip() else ""
    return (line[:297] + "...") if len(line) > 300 else (line or None)
