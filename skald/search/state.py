"""Each site's sync state, and the lock that keeps two syncs of a site apart.

`<history folder>/search/<site>.json`, written atomically, one part per
engine:

  last_sync      when the last sync of this engine ended (UTC, ISO 8601)
  last_ok        when one last ended well
  ok             how the last one ended
  error          the last failure in plain words (None after a good sync)
  error_since    when the current run of failures began
  error_mailed   when the one mail about it went (None: not mailed yet)
  days, first, last, provisional   what history holds (days.summary)
  rows           rows read by the last sync
  next_sync      about when the scheduler syncs next (last_sync + EVERY hours)
  backfill       {"state": running|done|failed, "months", "done", "of",
                  "started_at", "finished_at", "error"}
  asked_at       the last "Sync now" from the page (its rate limit)

The lock is `<site>.lock` beside it, an exclusive flock taken without
waiting: the scheduler's run, a "Sync now" and a backfill of the same site
never overlap; the second one says "already syncing" and stops.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ..files import write_atomic

FOLDER = "search"
SITE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,252}$")


class Busy(RuntimeError):
    """Another sync of the site holds the lock."""


def folder(history_folder) -> Path:
    return Path(history_folder) / FOLDER


def _file(history_folder, site: str, suffix: str) -> Path:
    if not SITE.match(site or ""):
        raise ValueError("not a site name")
    return folder(history_folder) / f"{site}{suffix}"


def load(history_folder, site: str) -> dict:
    try:
        got = json.loads(_file(history_folder, site, ".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def now_text(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc) \
        .isoformat(timespec="seconds")


@contextmanager
def _guard(history_folder, site: str):
    path = _file(history_folder, site, ".state-lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def update(history_folder, site: str, engine: str, **fields) -> dict:
    """Merge fields into one engine's part; a None value is kept as None.
    Returns the engine's part after the change."""
    with _guard(history_folder, site):
        state = load(history_folder, site)
        part = dict(state.get(engine) or {})
        part.update(fields)
        state[engine] = part
        write_atomic(_file(history_folder, site, ".json"),
                     json.dumps(state, indent=1, sort_keys=True) + "\n")
    return part


@contextmanager
def lock(history_folder, site: str):
    """The site's sync lock, or Busy at once."""
    path = _file(history_folder, site, ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy("a sync of this site is already running") from None
        yield
    finally:
        os.close(fd)


def is_busy(history_folder, site: str) -> bool:
    try:
        with lock(history_folder, site):
            return False
    except Busy:
        return True
    except OSError:
        return False
