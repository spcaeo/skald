"""Did the live log rotate or shrink under a count? (`audit --live`)

A live run records how far it read each plain log file (`read_upto`, by file
name) and which file that was (`read_ids`, its inode). The live
audit reads the same names as far again. If the log was rotated or truncated
in between (a shipped `access.log` moves to `access.log.1` at the first batch
of a new UTC day; logrotate does the same on a server; a crashed ingest
append is cut back), the same name now holds other bytes, and the recount
would differ from the snapshot for no fault in either count.

`moved()` says why the bytes under a name are no longer the ones counted, or
None. Three signs, each enough on its own:

- a name the run read now holds a different file (inode changed);
- a name the run read is smaller than it read (truncated, or a new file);
- a name the run read is gone, or a log the run would have read appeared.

The audit then answers "skipped: the log rotated during the check, run it
again" instead of a mismatch. It never turns a mismatch into a pass: with
the files unchanged, every figure is compared as before.
"""
from __future__ import annotations

from pathlib import Path

from .parse import log_files


def plain_files(config: dict) -> list[Path]:
    """The files a live run reads up to a size: the log and its first
    rotation (window.plain_sizes)."""
    logs = config.get("logs") or {}
    return log_files(Path(logs.get("dir") or "/var/log/nginx"),
                     logs.get("base") or "access.log", 2)


def _stats(paths) -> dict:
    out = {}
    for path in (Path(p) for p in paths):
        if path.suffix == ".gz":
            continue
        try:
            out[path.name] = path.stat()
        except OSError:
            pass
    return out


def ids(paths) -> dict[str, int]:
    """Each plain file's inode now, by file name."""
    return {name: st.st_ino for name, st in _stats(paths).items()}


def plain_state(config: dict) -> tuple[dict[str, int], dict[str, int]]:
    """({name: size}, {name: inode}) of the live run's plain files, from one
    look at each: what the run reads up to, and which file that was."""
    got = _stats(plain_files(config))
    return ({n: st.st_size for n, st in got.items()},
            {n: st.st_ino for n, st in got.items()})


def moved(upto: dict | None, seen: dict | None, paths, whole_set: bool = True,
          appeared: bool | None = None) -> str | None:
    """Why the files named in `upto` no longer hold the bytes counted, or None.

    `seen`: {name: inode} when they were read (None or missing names: not
    checked). `paths`: the files the recount reads now. `whole_set`: the
    paths are the same set the run looked at (not an operator's --log list),
    so a name gone, or (unless `appeared` is False: a reader that looked at
    fewer files) a new one appeared, is a rotation too."""
    if not upto:
        return None
    if appeared is None:
        appeared = whole_set
    now = _stats(paths)
    for name in sorted(upto):
        st = now.get(name)
        if st is None:
            if whole_set:
                return f"{name} is gone"
            continue
        if seen and name in seen and int(seen[name]) != st.st_ino:
            return f"{name} is a new file"
        if st.st_size < int(upto[name]):
            return f"{name} shrank from {int(upto[name]):,} to {st.st_size:,} bytes"
    if appeared:
        for name in sorted(set(now) - set(upto)):
            return f"{name} appeared"
    return None


def words(why: str) -> str:
    return f"the log rotated during the check ({why}); run it again"


class Still:
    """The live audit's check, before its recounts and again after them.

    Before: the files against the snapshot's record. After: against the
    snapshot again, and against each file as it was when the audit began (an
    older snapshot recorded no inodes), so a rotation while the audit itself
    reads is caught too."""

    def __init__(self, config: dict, snap: dict, log_args=None) -> None:
        self.paths = [Path(p) for p in log_args] if log_args else plain_files(config)
        self.whole_set = not log_args
        self.upto = snap.get("read_upto")
        self.seen = {**ids(self.paths), **(snap.get("read_ids") or {})}
        self.why = moved(self.upto, snap.get("read_ids"), self.paths, self.whole_set)

    def check(self) -> str | None:
        """Look again, after the recounts: why the files moved, or None."""
        self.why = moved(self.upto, self.seen, self.paths, self.whole_set)
        return self.why

    def words(self) -> str:
        return words(self.why or "")
