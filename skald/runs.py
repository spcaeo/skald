"""When each scheduled job last succeeded or failed (quality.json `runs`).

One small JSON file beside the history, `runs.json`, rewritten atomically
by each command at its end: {name: {"last_ok", "last_fail", "last_exit"}}.
It holds times and exit codes only, and for run-daily `last_outcome`: ok,
waiting (a site made from the dashboard with no log line yet, exit 0),
withheld (stopped by design: a day that does not reconcile, or a mail refused
for its data) or failed, which the failure mail reads (failmail.py); and
`last_step` / `last_reason`: the step it stopped at and why, in one line
(null when it ran to the end), which `skald doctor` shows.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .files import write_atomic

FILE = "runs.json"

# How often each job is meant to run, in minutes (for "late" in the panel).
EXPECTED = {"live": 2, "run-daily": 1440, "verify-bots": 1440, "alerts": 2,
            "backup": 1440, "heartbeat": 5}


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
        entry["last_ok" if code == 0 else "last_fail"] = at
        if outcome is not None:
            entry["last_outcome"] = outcome
            entry["last_step"] = step
            entry["last_reason"] = one_line(reason)
        write_atomic(path_for(directory), json.dumps(runs, indent=1, sort_keys=True) + "\n")
    except OSError:
        pass


def one_line(text) -> str | None:
    """The first line of a reason, at most 300 characters; None for none."""
    if not text:
        return None
    line = str(text).strip().splitlines()[0] if str(text).strip() else ""
    return (line[:297] + "...") if len(line) > 300 else (line or None)
