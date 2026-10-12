"""When each scheduled job last succeeded or failed (quality.json `runs`).

One small JSON file beside the history, `runs.json`, rewritten atomically
by each command at its end: {name: {"last_ok", "last_fail", "last_exit"}}.
It holds times and exit codes only, and for run-daily `last_outcome`: ok,
waiting (a site made from the dashboard with no log line yet, exit 0),
withheld (stopped by design: a day that does not reconcile) or failed, which
the failure mail reads (failmail.py).
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
           outcome: str | None = None) -> None:
    """Note that job `name` ended with exit `code`. Never raises: a job's
    bookkeeping must not turn a success into a failure."""
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
        write_atomic(path_for(directory), json.dumps(runs, indent=1, sort_keys=True) + "\n")
    except OSError:
        pass
