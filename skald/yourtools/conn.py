"""Each site's tool connections and their freshness.

`<history folder>/yourtools/<site>.json`, written atomically under its own
lock, one part per tool:

  on             the tool is connected and synced (False: paused; its key, its
                 answers and its figures stay)
  options        what the connection needs beside the key (GA4: property)
  connected_at, connected_by   when and by whom ("ai-agent", "cli", a user id)
  paused_at      when it was switched off
  last_try       when the last sync of the tool ended (UTC, ISO 8601)
  last_ok        when one last ended well: the tool's freshness
  ok             how the last one ended
  error          the last failure in plain words (None after a good one)
  error_since    when the current run of failures began
  error_mailed   when the one mail about it went
  answers        answers kept by the last good sync
  asked_at       the last "Sync now" (its rate limit)
  audit          {ok, at, problems, checked}: the last recheck (recount.py)

`status(part, key_set, now)` turns a part into the one state every screen
shows, with its pill (docs/UI-RULES.md rule 13):

  off       not connected, or paused                         off   "Not connected" / "Paused"
  no_key    on, but no key is found                          warn  "Needs its key"
  waiting   on, a key, no sync has ended yet                 info  "Waiting for its first answer"
  answering the last answer is fresh (within STALE_HOURS)    good  "Answering"
  failing   the last try failed, the last answer still fresh warn  "Last try failed"
  stopped   no good answer for STALE_HOURS, or none ever and  bad   "Stopped answering"
            the tries fail                                         / "Not answering"
  withheld  the audit's recheck did not match                bad   "Withheld"
"""
from __future__ import annotations

import fcntl
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..files import write_atomic

FOLDER = "yourtools"
SITE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,252}$")
EVERY_HOURS = 6                         # the scheduler's sync (docker/scheduler.py)
STALE_HOURS = 26                        # no good answer for this long: stopped answering
PILLS = {"off": "off", "no_key": "warn", "waiting": "info", "answering": "good",
         "failing": "warn", "stopped": "bad", "withheld": "bad"}


class Busy(RuntimeError):
    """Another sync of the site holds the lock."""


def folder(history_folder) -> Path:
    return Path(history_folder) / FOLDER


def _file(history_folder, site: str, suffix: str) -> Path:
    if not SITE.match(site or ""):
        raise ValueError("not a site name")
    return folder(history_folder) / f"{site}{suffix}"


def load(history_folder, site: str) -> dict:
    """{tool: part} for a site; {} when nothing was ever connected."""
    try:
        got = json.loads(_file(history_folder, site, ".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def now_text(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc) \
        .isoformat(timespec="seconds")


def parse(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


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


def update(history_folder, site: str, tool: str, **fields) -> dict:
    """Merge fields into one tool's part (a None value is kept as None);
    the part after the change."""
    with _guard(history_folder, site):
        got = load(history_folder, site)
        part = dict(got.get(tool) or {})
        part.update(fields)
        got[tool] = part
        write_atomic(_file(history_folder, site, ".json"),
                     json.dumps(got, indent=1, sort_keys=True) + "\n")
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
            raise Busy("a sync of this site's tools is already running") from None
        yield
    finally:
        os.close(fd)


def on_tools(history_folder, site: str) -> list[str]:
    """The tools switched on for a site."""
    return sorted(t for t, p in load(history_folder, site).items()
                  if isinstance(p, dict) and p.get("on"))


def _ago(then: datetime | None, now: datetime) -> str:
    if then is None:
        return "never"
    s = max(0, int((now - then).total_seconds()))
    if s < 90:
        return "just now"
    if s < 5400:
        return f"{s // 60} min ago"
    if s < 172800:
        return f"{s // 3600} h ago"
    return f"{s // 86400} days ago"


def status(part: dict | None, key_set: bool, now: datetime | None = None) -> dict:
    """{state, pill, words, last_ok, ago, error}: the one state every screen shows."""
    part = part or {}
    now = now or datetime.now(timezone.utc)
    last_ok = parse(part.get("last_ok"))
    out = {"last_ok": part.get("last_ok"), "ago": _ago(last_ok, now),
           "last_try": part.get("last_try"), "error": part.get("error")}
    audit = part.get("audit") if isinstance(part.get("audit"), dict) else {}
    if not part.get("on"):
        state = "off"
        words = "Paused" if part.get("paused_at") or part.get("connected_at") else "Not connected"
    elif not key_set:
        state, words = "no_key", "Needs its key"
    elif not part.get("last_try"):
        state, words = "waiting", "Waiting for its first answer"
    elif audit and audit.get("ok") is False:
        state, words = "withheld", "Withheld"
    elif last_ok is not None and now - last_ok <= timedelta(hours=STALE_HOURS):
        state = "answering" if part.get("ok") else "failing"
        words = "Answering" if part.get("ok") else "Last try failed"
    else:
        state = "stopped"
        words = "Stopped answering" if last_ok is not None else "Not answering"
    out.update(state=state, pill=PILLS[state], words=words)
    return out
