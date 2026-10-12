"""The hook spool: every verified hook body, one JSON line each, written
before anything else is done with it. One file per local day:
<history folder>/hooks/<YYYY-MM-DD>.jsonl (`hooks.spool` to move it), 0640.

    {"received_at": "2026-10-11T14:00:00Z", "site": "example.com",
     "tool": "calendly", "body": {...}}

The body is the tool's JSON with only the keys its adapter and the audit
read (conversions.SPOOL_KEYS, an allow-list per tool), plus the name and the
primary email when the site's identity is full (conversions.strip). The spool is what the second count
(audit_conversions.py) reads; `forget` scrubs it with the store.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from ..config import setting
from . import strip

KEEP_DAYS = 400


def spool_dir(config: dict, folder: Path) -> Path:
    raw = setting(config or {}, "hooks", "spool")
    return Path(str(raw)).expanduser() if raw else Path(folder) / "hooks"


def day_file(spool: Path, day: date) -> Path:
    return Path(spool) / f"{day.isoformat()}.jsonl"


def line_for(received_at: str, site: str, tool: str, body, identity_full: bool) -> str:
    return json.dumps({"received_at": received_at, "site": site, "tool": tool,
                       "body": strip(body, identity_full, tool)},
                      separators=(",", ":"), sort_keys=True)


def append(spool: Path, day: date, line: str) -> None:
    """Append one line, the file made 0640 when it is new."""
    spool = Path(spool)
    spool.mkdir(parents=True, exist_ok=True)
    path = day_file(spool, day)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o640)
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def read(spool: Path, day: date) -> list[dict]:
    path = day_file(spool, day)
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def days(spool: Path) -> list[date]:
    found = []
    for path in Path(spool).glob("*.jsonl"):
        try:
            found.append(date.fromisoformat(path.name[:10]))
        except ValueError:
            continue
    return sorted(found)


def prune(spool: Path, today: date, keep_days: int = KEEP_DAYS) -> int:
    cutoff = today - timedelta(days=keep_days)
    gone = 0
    for day in days(spool):
        if day < cutoff:
            day_file(spool, day).unlink(missing_ok=True)
            gone += 1
    return gone


def _texts(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)
    elif isinstance(value, (str, int)) and not isinstance(value, bool):
        yield str(value)


def scrub(spool: Path, match, dry_run: bool = False) -> int:
    """Remove every line `match(row, texts)` says belongs to a forgotten
    person; `texts` is the set of the body's values as text. Lines removed."""
    gone = 0
    for day in days(spool):
        path = day_file(spool, day)
        keep, dropped = [], 0
        with open(path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                try:
                    row = json.loads(raw)
                except ValueError:
                    keep.append(raw)
                    continue
                texts = {t.strip().lower() for t in _texts(row.get("body"))}
                if isinstance(row, dict) and match(row, texts):
                    dropped += 1
                else:
                    keep.append(raw)
        if dropped and not dry_run:
            _rewrite(path, "".join(keep))
        gone += dropped
    return gone


def _rewrite(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o640)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
