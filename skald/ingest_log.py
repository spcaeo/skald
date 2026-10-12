"""Where shipped log lines are kept: one access log per site, rotated daily.

    <ingest root>/<site>/access.log      today's lines (UTC day of the last write)
                         access.log.1    the day before, plain
                         access.log.2.gz ... access.log.<keep>.gz

That is the layout run-daily already reads (parse.log_files: `<base>`,
`<base>.1`, `<base>.N.gz`), so a site's `logs.dir` points at its folder and
nothing else changes. The root is `ingest.root`, default `<history
folder>/ingest`.

**Rotation is by day, with a size ceiling.** run-daily looks back as many
rotations as days (window.window_paths: days + 3), so a file must not be
rotated more than once a day or older lines fall out of its reach. The
first write of a new UTC day rotates; within a day, a batch that would take
the file past `ingest.max_mb` (default 1024) is refused (`Full`, the
endpoint answers 429 with the seconds to midnight UTC) and the shipper keeps
the lines until then. Rotated files keep their modification times, which
window.files_for uses to choose the files a day needs.

**Each batch once.** A batch carries `<shipper id>:<seq>`; the last seq per
shipper is kept in `.ingest-state.json` beside the log. A seq at or below
it is acknowledged and not written again. The append is journaled: the
state names the batch, where it starts and how long it is BEFORE the bytes
are written, and records the seq after they are on disk. A crash in between
is repaired on the next write: a complete append is kept and its seq
recorded, a partial one is cut off, so a re-sent batch is neither lost nor
doubled.

One writer at a time per site: a thread lock and an flock on `.ingest.lock`.
"""
from __future__ import annotations

import fcntl
import gzip
import json
import os
import re
import shutil
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .files import slug

BASE = "access.log"
STATE = ".ingest-state.json"
LOCK = ".ingest.lock"
ORG_USAGE = ".org-bytes.json"     # in the ingest root: {"day", "orgs": {org id: bytes}}
ORG_LOCK = ".org-bytes.lock"
KEEP = 14
MAX_MB = 1024
MAX_SHIPPERS = 200
SHIPPER = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()


class Full(Exception):
    """Today's file is at its ceiling; `retry_after` seconds to the next day."""

    def __init__(self, retry_after: int):
        super().__init__("today's log for this site is full")
        self.retry_after = retry_after


def root(config: dict, history_folder) -> Path:
    """`ingest.root`, else <history folder>/ingest."""
    raw = ((config or {}).get("ingest") or {}).get("root")
    if raw:
        return Path(str(raw)).expanduser()
    return Path(history_folder) / "ingest"


def site_folder(base: Path, site: str) -> Path:
    return Path(base) / slug(site)


def _day(stamp: float) -> str:
    return datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%d")


def _to_midnight(now: float) -> int:
    left = 86400 - int(now) % 86400
    return max(60, min(left, 3600))


@contextmanager
def _locked(folder: Path, name: str = LOCK):
    key = str(Path(folder) / name)
    with _GUARD:
        lock = _LOCKS.setdefault(key, threading.Lock())
    with lock:
        folder.mkdir(parents=True, exist_ok=True)
        fd = os.open(folder / name, os.O_CREAT | os.O_RDWR, 0o640)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def _write_json(path: Path, body: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(body, handle, separators=(",", ":"))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def read_state(folder: Path) -> dict:
    try:
        got = json.loads((Path(folder) / STATE).read_text())
    except (OSError, ValueError):
        got = {}
    if not isinstance(got, dict):
        got = {}
    got.setdefault("shippers", {})
    got.setdefault("pending", None)
    got.setdefault("totals", {"batches": 0, "accepted": 0, "rejected": 0, "duplicates": 0,
                              "last_at": None})
    return got


class Writer:
    """Appends one site's batches. `clock` is Unix seconds (tests move it)."""

    def __init__(self, folder: Path, keep: int = KEEP, max_mb: float = MAX_MB,
                 clock=time.time, base: str = BASE):
        self.folder, self.base = Path(folder), base
        self.keep = max(1, int(keep))
        self.max_bytes = int(float(max_mb) * 1024 * 1024)
        self.clock = clock

    @property
    def log(self) -> Path:
        return self.folder / self.base

    def seen(self, shipper: str, seq: int) -> bool:
        got = read_state(self.folder)["shippers"].get(shipper)
        return bool(got) and int(got.get("seq", 0)) >= seq

    def append(self, shipper: str, seq: int, data: bytes, accepted: int = 0,
               rejected: int = 0) -> str:
        """"stored" or "duplicate". Raises Full, ValueError (a bad shipper id)."""
        if not SHIPPER.match(shipper or "") or seq < 0:
            raise ValueError("bad batch id")
        if data and not data.endswith(b"\n"):
            data += b"\n"
        with _locked(self.folder):
            state = read_state(self.folder)
            self._recover(state)
            now = self.clock()
            last = state["shippers"].get(shipper)
            if last and int(last.get("seq", 0)) >= seq:
                state["totals"]["duplicates"] = state["totals"].get("duplicates", 0) + 1
                _write_json(self.folder / STATE, state)
                return "duplicate"
            self._rotate_if_new_day(now)
            size = self.log.stat().st_size if self.log.exists() else 0
            if data and size + len(data) > self.max_bytes:
                raise Full(_to_midnight(now))
            stamp = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if data:
                state["pending"] = {"shipper": shipper, "seq": seq, "start": size,
                                    "length": len(data), "accepted": accepted,
                                    "rejected": rejected, "at": stamp}
                _write_json(self.folder / STATE, state)
                with open(self.log, "ab") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(self.log, 0o640)
            self._done(state, shipper, seq, accepted, rejected, stamp)
            _write_json(self.folder / STATE, state)
            return "stored"

    def _done(self, state, shipper, seq, accepted, rejected, stamp) -> None:
        state["pending"] = None
        state["shippers"][shipper] = {"seq": seq, "at": stamp}
        if len(state["shippers"]) > MAX_SHIPPERS:
            oldest = sorted(state["shippers"].items(), key=lambda kv: kv[1].get("at") or "")
            for name, _ in oldest[:len(state["shippers"]) - MAX_SHIPPERS]:
                state["shippers"].pop(name, None)
        t = state["totals"]
        t["batches"] = t.get("batches", 0) + 1
        t["accepted"] = t.get("accepted", 0) + int(accepted)
        t["rejected"] = t.get("rejected", 0) + int(rejected)
        t["last_at"] = stamp

    def _recover(self, state: dict) -> None:
        """Finish or undo an append a crash interrupted."""
        p = state.get("pending")
        if not p:
            return
        size = self.log.stat().st_size if self.log.exists() else 0
        end = int(p["start"]) + int(p["length"])
        if size >= end:
            self._done(state, p["shipper"], int(p["seq"]), p.get("accepted", 0),
                       p.get("rejected", 0), p.get("at"))
        else:
            if size > int(p["start"]):
                with open(self.log, "r+b") as handle:
                    handle.truncate(int(p["start"]))
                    handle.flush()
                    os.fsync(handle.fileno())
            state["pending"] = None
        _write_json(self.folder / STATE, state)

    def _rotate_if_new_day(self, now: float) -> None:
        if not self.log.exists():
            return
        st = self.log.stat()
        if st.st_size == 0 or _day(st.st_mtime) >= _day(now):
            return
        self.rotate()

    def rotate(self) -> None:
        """access.log -> .1 -> .2.gz ... -> .<keep>.gz, oldest dropped,
        every file keeping its modification time."""
        b = self.folder / self.base
        last = self.folder / f"{self.base}.{self.keep}.gz"
        if self.keep >= 2 and last.exists():
            last.unlink()
        for n in range(self.keep - 1, 1, -1):
            src = self.folder / f"{self.base}.{n}.gz"
            if src.exists():
                os.replace(src, self.folder / f"{self.base}.{n + 1}.gz")
        one = self.folder / f"{self.base}.1"
        if one.exists():
            if self.keep >= 2:
                _gzip(one, self.folder / f"{self.base}.2.gz")
            one.unlink()
        if b.exists():
            os.replace(b, one)


def _gzip(src: Path, dest: Path) -> None:
    st = src.stat()
    tmp = dest.with_name(dest.name + ".tmp")
    with open(src, "rb") as raw, gzip.open(tmp, "wb") as out:
        shutil.copyfileobj(raw, out, 1024 * 1024)
    os.chmod(tmp, 0o640)
    os.utime(tmp, (st.st_atime, st.st_mtime))
    os.replace(tmp, dest)


# ------------------------------------------------- an organisation's day

def _org_usage(base: Path, day: str) -> dict:
    try:
        got = json.loads((Path(base) / ORG_USAGE).read_text())
    except (OSError, ValueError):
        got = {}
    if not isinstance(got, dict) or got.get("day") != day or \
            not isinstance(got.get("orgs"), dict):
        got = {"day": day, "orgs": {}}
    return got


def org_bytes(base: Path, org_id, now: float | None = None) -> int:
    """Bytes the organisation's sites had accepted today (UTC)."""
    day = _day(time.time() if now is None else now)
    return int(_org_usage(base, day)["orgs"].get(str(org_id), 0))


def reserve(base: Path, org_id, nbytes: int, cap: int, now: float | None = None) -> bool:
    """Count `nbytes` against the organisation's day, when that keeps it at
    or under `cap`: True. False (nothing counted) when it would pass it."""
    now = time.time() if now is None else now
    with _locked(Path(base), ORG_LOCK):
        usage = _org_usage(base, _day(now))
        used = int(usage["orgs"].get(str(org_id), 0))
        if nbytes and used + nbytes > cap:
            return False
        usage["orgs"][str(org_id)] = used + int(nbytes)
        _write_json(Path(base) / ORG_USAGE, usage)
        return True


def release(base: Path, org_id, nbytes: int, now: float | None = None) -> None:
    """Give back bytes reserved for a batch that was not written after all."""
    now = time.time() if now is None else now
    with _locked(Path(base), ORG_LOCK):
        usage = _org_usage(base, _day(now))
        used = int(usage["orgs"].get(str(org_id), 0))
        usage["orgs"][str(org_id)] = max(0, used - int(nbytes))
        _write_json(Path(base) / ORG_USAGE, usage)


def to_midnight(now: float | None = None) -> int:
    return _to_midnight(time.time() if now is None else now)


def summary(folder: Path) -> dict:
    """What the Sites page shows: batches, lines kept and refused, last batch."""
    t = read_state(folder)["totals"]
    return {"batches": t.get("batches", 0), "accepted": t.get("accepted", 0),
            "rejected": t.get("rejected", 0), "last_at": t.get("last_at"),
            "shippers": len(read_state(folder)["shippers"])}
