"""Where each hook's secret lives. Never in the config, never in the repo.

A hook's secret is found, in this order:

  1. an environment variable named in the config:
       hooks:
         example.com:
           calendly: {secret_env: SKALD_HOOK_CALENDLY}
     (nested, needs PyYAML) or, flat, readable by the small parser too:
       hooks:
         example.com/calendly: SKALD_HOOK_CALENDLY
  2. `secrets.json` beside the history (`hooks.secrets` to move it), key
     "hooks/<site>/<tool>", written by `skald hooks secret SITE TOOL`.

secrets.json must be 0600: a file others can read is refused, not used.
Named secrets_store, not secrets, so it never hides the standard library's.
"""
from __future__ import annotations

import fcntl
import json
import os
import secrets
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..files import own_like_folder

FILE = "secrets.json"


class Exposed(PermissionError):
    """secrets.json can be read by others than its owner."""


def path_for(config: dict, folder: Path) -> Path:
    raw = ((config or {}).get("hooks") or {}).get("secrets")
    return Path(str(raw)).expanduser() if raw else Path(folder) / FILE


def key(site: str, tool: str) -> str:
    return f"hooks/{site}/{tool}"


def env_name(config: dict, site: str, tool: str) -> str | None:
    """The environment variable the config names for this hook, if any."""
    hooks = (config or {}).get("hooks") or {}
    if not isinstance(hooks, dict):
        return None
    flat = hooks.get(f"{site}/{tool}")
    if isinstance(flat, str) and flat:
        return flat
    per_site = hooks.get(site)
    if isinstance(per_site, dict):
        entry = per_site.get(tool)
        if isinstance(entry, dict) and entry.get("secret_env"):
            return str(entry["secret_env"])
    return None


def load(path: Path) -> dict:
    """The secrets file, {} when there is none. Raises Exposed when its mode
    lets anyone but the owner read it."""
    path = Path(path)
    try:
        st = path.stat()
    except FileNotFoundError:
        return {}
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise Exposed(f"{path} must be 0600 (it is {oct(stat.S_IMODE(st.st_mode))})")
    try:
        got = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError:
        return {}
    return got if isinstance(got, dict) else {}


def find(config: dict, folder: Path, site: str, tool: str) -> tuple[str | None, str]:
    """(secret, where it lives). where: "env NAME", "file", or "" when none."""
    name = env_name(config, site, tool)
    if name:
        value = os.environ.get(name)
        return (value or None), f"env {name}"
    value = load(path_for(config, folder)).get(key(site, tool))
    return (str(value) if value else None), ("file" if value else "")


def lock_path(path: Path) -> Path:
    """The lock file beside secrets.json: every change holds it."""
    path = Path(path)
    return path.with_name(f".{path.name}.lock")


@contextmanager
def _locked(path: Path):
    """An exclusive flock for one read-modify-write of the secrets file, so
    two writers (the page, the CLI, a purge) never lose each other's key."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)                    # closing releases the lock


def _write(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    own_like_folder(path)


def put(path: Path, name: str, value: str) -> None:
    """Set one key in the secrets file, written 0600 and renamed into place,
    under the lock."""
    path = Path(path)
    with _locked(path):
        data = load(path)
        data[name] = value
        _write(path, data)


def delete(path: Path, names) -> int:
    """Take keys out of the secrets file, under the lock. `names` is a list
    of keys or a function that says yes to a key. How many went."""
    path = Path(path)
    if not path.exists():
        return 0
    with _locked(path):
        data = load(path)
        gone = [k for k in data if (names(k) if callable(names) else k in names)]
        if gone:
            _write(path, {k: v for k, v in data.items() if k not in gone})
    return len(gone)


def make() -> str:
    """A new secret: 32 random bytes, URL-safe text."""
    return "skh_" + secrets.token_urlsafe(32)
