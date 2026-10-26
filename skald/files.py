"""Writing files other processes read while they are being written.

The dashboard is served while cron rewrites it, and the live snapshot is
rewritten every two minutes while the dashboard renderer reads it. Both are
written to a temporary file beside the target and renamed over it, so a
reader sees the old file or the new one, never half of one.

A file can have a gzip copy beside it, `<name>.gz`, that nginx sends instead
to a browser that accepts gzip (gzip_static, DEPLOY.md): the dashboard's data
files and the app's code. `write_atomic(..., pack=True)` writes it. The copy is
never older than its file: whenever a file that has one is written, by any
writer (a privacy redaction too), the old copy is removed before the file is
replaced and a new one is written after it, so a crash in between leaves no
copy at all (nginx then compresses the file itself), never a stale one.
"""
from __future__ import annotations

import gzip
import os
import re
import tempfile
from pathlib import Path


def slug(site: str) -> str:
    """A directory name for a site, safe on any filesystem."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", site).strip(".-") or "site"


def own_like_folder(path: Path) -> None:
    """Give a file its folder's owner and group. For the commands an admin
    runs as root (skald user, skald token): the files they write beside the
    history must stay readable by the service user the helper runs as."""
    path = Path(path)
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return
    st = path.parent.stat()
    try:
        os.chown(path, st.st_uid, st.st_gid)
    except OSError:
        pass


# A file smaller than this gets no gzip copy: the packing costs more than it saves.
GZ_MIN = 1024
# zlib's default: about a tenth of a data file's size, at about 100 MB/s on one core.
GZ_LEVEL = 6


def packed(path: Path) -> Path:
    """The gzip copy of `path`: <name>.gz beside it."""
    path = Path(path)
    return path.with_name(path.name + ".gz")


def write_atomic(path: Path, text: str, pack: bool = False) -> None:
    """Write to a temp file beside `path`, then rename over it. With `pack`, or
    when `path` already has a gzip copy, the copy is written again too."""
    write_atomic_bytes(path, text.encode("utf-8"), pack)


def write_atomic_bytes(path: Path, data: bytes, pack: bool = False) -> None:
    """write_atomic for bytes."""
    path = Path(path)
    gz = packed(path)
    had = gz.exists()
    inode = _replace(path, data)
    if had or pack:
        _pack(gz, data, path, inode)


def _replace(path: Path, data: bytes) -> int:
    """Write `data` over `path` atomically; the new file's inode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    gz = packed(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            inode = os.fstat(handle.fileno()).st_ino
        os.chmod(tmp, 0o644)
        # The old copy goes first: from here to the new copy, nginx sends the file
        # itself (compressing it), never the old copy with the new file beside it.
        try:
            gz.unlink()
        except FileNotFoundError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return inode


def _pack(gz: Path, data: bytes, path: Path, inode: int) -> None:
    """Write the gzip copy (none for a small file). mtime 0 in its header: the
    same bytes give the same copy. When another writer replaced `path` while
    this one packed, the copy may be of the older bytes: it is removed (the
    other writer writes its own)."""
    if len(data) < GZ_MIN:
        return
    fd, tmp = tempfile.mkstemp(dir=gz.parent, prefix=f".{gz.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(gzip.compress(data, compresslevel=GZ_LEVEL, mtime=0))
        os.chmod(tmp, 0o644)
        os.replace(tmp, gz)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    try:
        same = os.stat(path).st_ino == inode
    except FileNotFoundError:
        same = False
    if not same:
        try:
            gz.unlink()
        except FileNotFoundError:
            pass
