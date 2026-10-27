"""Real time's fast road: the newest log lines, counted every 15 seconds.

The people figures of Real time come from the live run (realtime.py, every
2 minutes): only the whole day's tally can apply the people rule. What can
be fresher is the plain count of requests: this module reads the end of
the access log - never the whole day - and counts every request of the
site's hosts per clock minute over the last MINUTES minutes, up to the
start of the current second. Nothing is classified here, so the page calls
them requests, every kind (pages, files, bots and people alike), and never
draws them beside the people figures as if they were people.

  requests_now(config, now)   {"from", "until", "per_minute": {epoch minute: n},
                               "total", "newest", "partial"}

How the end of a file is read: blocks of BLOCK bytes from the end, back
until a line older than the window (or the file's start, or MAX_BYTES; then
"partial" is true and the count is a floor). Only the plain files the window
can need are read (window.files_for; rotations already compressed are older
than any window of minutes). A request id seen twice is one request, as in
parse.read.

The helper (realtime_api.py) keeps an answer for CACHE_SECONDS, so many
open pages cost one read, and writes the last one beside the live snapshot
(`live-<site>-tail.json`, counts only) so `skald audit --live` can count the
same window again from the raw lines (audit_realtime.recount_tail).
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .files import write_atomic

VERSION = 1
MINUTES = 30
BLOCK = 256 * 1024
MAX_BYTES = 64 * 1024 * 1024
CACHE_SECONDS = 10


def tail_path(live_dir: Path, site: str) -> Path:
    from .live import path_for
    snap = Path(path_for(live_dir, site))
    return snap.with_name(snap.stem + "-tail.json")


def _parser(config: dict, sample: list[str]):
    """line -> Hit | None, the way parse.read picks and falls back."""
    from .parse import AUTO_ORDER, PARSERS, detect
    fmt = (config.get("logs") or {}).get("format") or "auto"
    if fmt != "auto":
        return PARSERS.get(fmt) or PARSERS["nginx_extended"]
    first = PARSERS[detect(sample[:200])] if sample else PARSERS["nginx_extended"]
    others = [PARSERS[name] for name in AUTO_ORDER if PARSERS[name] is not first]

    def parse_one(line: str):
        hit = first(line)
        if hit is None:
            for other in others:
                hit = other(line)
                if hit is not None:
                    break
        return hit
    return parse_one


def _any_time(line: str):
    from .parse import AUTO_ORDER, PARSERS
    for name in AUTO_ORDER:
        hit = PARSERS[name](line)
        if hit is not None:
            w = hit.when
            return w if w.tzinfo else w.replace(tzinfo=timezone.utc)
    return None


def tail_lines(path: Path, start: datetime,
               limit: int | None = None) -> tuple[list[str], bool]:
    """The lines at the end of `path` that can be at or after `start`, and
    whether MAX_BYTES stopped the read short of them. With `limit`, the end
    is that byte (the file's size when the count began, parse.sizes) and a
    line cut there is not read: the audit counts the same bytes."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = pos = handle.tell() if limit is None else min(limit, handle.tell())
            chunks: list[bytes] = []
            limited = limit is not None
            while pos > 0:
                if size - pos >= MAX_BYTES:
                    return _split(chunks, pos > 0, limited), True
                step = min(BLOCK, pos)
                pos -= step
                handle.seek(pos)
                chunks.insert(0, handle.read(step))
                if pos == 0:
                    break
                # The first whole line of what is read so far: older than the window?
                head = b"".join(chunks[:2])
                cut = head.find(b"\n")
                if cut < 0:
                    continue
                nxt = head.find(b"\n", cut + 1)
                line = head[cut + 1:nxt if nxt > 0 else None].decode("utf-8", "replace")
                when = _any_time(line)
                if when is not None and when < start:
                    break
            return _split(chunks, pos > 0, limited), False
    except OSError:
        return [], False


def _split(chunks: list[bytes], cut_first: bool, cut_last: bool = False) -> list[str]:
    data = b"".join(chunks)
    if cut_last:                    # a line cut at the size limit is not read
        data = data[:data.rfind(b"\n") + 1]
    lines = data.decode("utf-8", "replace").splitlines()
    return lines[1:] if cut_first and lines else lines


def requests_now(config: dict, now: datetime, minutes: int = MINUTES) -> dict:
    """Every request of the site's hosts in the last `minutes` clock minutes,
    up to the start of the current second, per minute."""
    from .config import setting
    from .window import window_paths
    now = now.astimezone(timezone.utc)
    until = now.replace(microsecond=0)
    first = (int(until.timestamp()) - 1) // 60 - minutes + 1
    start = datetime.fromtimestamp(first * 60, timezone.utc)
    paths = [p for p in window_paths(config, start, until, now) if p.suffix != ".gz"]
    # Each file's size now: read that far, and recorded, so the audit counts
    # the same bytes and not the lines written since (parse.sizes).
    from .parse import sizes
    from .log_moved import ids
    seen = ids(paths)          # which file each was: the audit skips a rotated one
    upto = sizes(paths)
    wanted = {str(h).lower() for h in (setting(config, "site", "hosts") or [])}
    per_minute: Counter = Counter()
    newest, partial, rids = None, False, set()
    for path in paths:
        lines, short = tail_lines(path, start, upto.get(path.name, 0))
        partial = partial or short
        parse_one = _parser(config, lines[-200:])
        for line in lines:
            hit = parse_one(line)
            if hit is None:
                continue
            if hit.rid:
                if hit.rid in rids:
                    continue
                rids.add(hit.rid)
            when = hit.when if hit.when.tzinfo else hit.when.replace(tzinfo=timezone.utc)
            if not start <= when < until:
                continue
            if wanted and hit.host and hit.host.lower() not in wanted:
                continue
            per_minute[int(when.timestamp()) // 60] += 1
            if newest is None or when > newest:
                newest = when
    return {"version": VERSION, "minutes": minutes,
            "from": start.isoformat(timespec="seconds"),
            "until": until.isoformat(timespec="seconds"),
            "per_minute": {str(m): int(per_minute.get(m, 0)) for m in range(first, first + minutes)},
            "total": sum(per_minute.values()),
            "newest": newest.isoformat(timespec="seconds") if newest else None,
            "partial": partial, "read_upto": upto, "read_ids": seen}


# ------------------------------------------------------------- the helper's cache

_CACHE: dict[str, tuple[float, dict]] = {}
_LOCK = threading.Lock()


def cached(site: str, config: dict, live_dir: Path | None, clock=time.monotonic,
           now=None) -> dict:
    """requests_now for a site, at most once per CACHE_SECONDS; each new
    answer is also written to the tail file for the audit."""
    with _LOCK:
        got = _CACHE.get(site)
        if got is not None and clock() - got[0] < CACHE_SECONDS:
            return got[1]
        answer = requests_now(config, now or datetime.now(timezone.utc))
        _CACHE[site] = (clock(), answer)
    if live_dir is not None:
        try:
            write_atomic(tail_path(live_dir, site), json.dumps(answer, separators=(",", ":")) + "\n")
        except OSError:
            pass            # the audit then has nothing new to count; the page is not affected
    return answer


def load(path: Path) -> dict | None:
    try:
        got = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and got.get("version") == VERSION else None


def as_page(answer: dict, tz) -> dict:
    """The answer as the page reads it: minutes as local times, oldest first."""
    rows = []
    for key, value in sorted(answer.get("per_minute", {}).items(), key=lambda kv: int(kv[0])):
        at = datetime.fromtimestamp(int(key) * 60, timezone.utc).astimezone(tz)
        rows.append({"at": at.isoformat(timespec="minutes"), "requests": int(value)})
    def local(v):
        return datetime.fromisoformat(v).astimezone(tz).isoformat(timespec="seconds") if v else None
    return {"from": local(answer.get("from")), "until": local(answer.get("until")),
            "per_minute": rows, "total": answer.get("total", 0),
            "newest": local(answer.get("newest")), "partial": bool(answer.get("partial"))}


def window_of(answer: dict) -> tuple[datetime, datetime]:
    return (datetime.fromisoformat(answer["from"]), datetime.fromisoformat(answer["until"]))

