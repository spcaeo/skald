"""Writing files other processes read while they are being written.

The dashboard is served while cron rewrites it, and the live snapshot is
rewritten every two minutes while the dashboard renderer reads it. Both are
written to a temporary file beside the target and renamed over it, so a
reader sees the old file or the new one, never half of one.
"""
from __future__ import annotations

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


def write_atomic(path: Path, text: str) -> None:
    """Write to a temp file beside `path`, then rename over it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
