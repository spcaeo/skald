"""The hook spool: every verified hook body, one JSON line each, written
before anything else is done with it. One file per local day:
<history folder>/hooks/<YYYY-MM-DD>.jsonl (`hooks.spool` to move it), 0640.

    {"received_at": "2026-10-11T14:00:00Z", "site": "example.com",
     "tool": "calendly", "body": {...}}

plus "zone": "<site's time zone>" on a `lead` or `json` line whose body has a
time without an offset (read in that zone, since 2.4.0), and "held": true on
a refused delivery taken in after a key was saved (2.45, held.py).

The body is the tool's JSON with only the keys its adapter and the audit
read (conversions.SPOOL_KEYS, an allow-list per tool), plus the name and the
primary email when the site's identity is full (conversions.strip). The spool is what the second count
(audit_conversions.py) reads; `forget` scrubs it with the store, and
people_days.py drops a line's name and email once older than the site's
People days (when set and shorter), leaving the rest of the line.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, timedelta
from pathlib import Path

from ..config import setting
from . import strip

KEEP_DAYS = 400          # conversions.retention_days: the same days (0: for good)


def spool_dir(config: dict, folder: Path) -> Path:
    raw = setting(config or {}, "hooks", "spool")
    return Path(str(raw)).expanduser() if raw else Path(folder) / "hooks"


def day_file(spool: Path, day: date) -> Path:
    return Path(spool) / f"{day.isoformat()}.jsonl"


def line_for(received_at: str, site: str, tool: str, body, identity_full: bool,
             zone: str | None = None, held: bool = False) -> str:
    """One line. `zone`: the time zone the receiver read the body's times
    without an offset in (the site's; 2.4.0). A line without it read them as
    UTC, so the second count reads each line the way it was kept. `held`
    (2.45): a refused delivery taken in later, once a saved key matched it
    (held.py, key_check.py); its received_at is when it first came, and the
    line sits in the file of the day it was taken in."""
    line = {"received_at": received_at, "site": site, "tool": tool,
            "body": strip(body, identity_full, tool)}
    if zone:
        line["zone"] = zone
    if held:
        line["held"] = True
    return json.dumps(line, separators=(",", ":"), sort_keys=True)


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


def prune(spool: Path, today: date, keep_days: int = KEEP_DAYS,
          own: dict | None = None, spare=None) -> int:
    """Remove the lines older than their site's keeping days: `keep_days`,
    a site in `own` by its own; 0 keeps them for good (the raw evidence the
    second count reads, kept as long as the conversions it recounts). A day
    file with every line past its time is deleted; one with some lines kept
    is written again without the others. Files deleted. A site `spare`
    names (keep_everything) keeps every line; with every site spared (the
    install keeps everything) nothing is read or written."""
    if spare is not None and getattr(spare, "all", False):
        return 0
    own = {s: int(n) for s, n in (own or {}).items()}
    if spare is not None:
        found = {row["site"] for day in days(spool) for row in read(spool, day)
                 if isinstance(row.get("site"), str)}
        own.update({s: 0 for s in found if spare(s)})

    def gone_by(days: int, day: date) -> bool:
        return days != 0 and day < today - timedelta(days=days)

    gone = 0
    for day in days(spool):
        if not gone_by(keep_days, day) and not any(gone_by(n, day) for n in own.values()):
            continue
        path = day_file(spool, day)
        if not own:
            path.unlink(missing_ok=True)
            gone += 1
            continue
        keep, dropped = [], 0
        with open(path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                try:
                    site = json.loads(raw).get("site")
                except (ValueError, AttributeError):
                    site = None
                if gone_by(own.get(site, keep_days) if isinstance(site, str) else keep_days,
                           day):
                    dropped += 1
                else:
                    keep.append(raw)
        if not keep:
            path.unlink(missing_ok=True)
            gone += 1
        elif dropped:
            _rewrite(path, "".join(keep))
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
