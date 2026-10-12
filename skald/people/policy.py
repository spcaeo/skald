"""What a site keeps about people, and the rule for an install that is upgraded.

The owner's decision (2026-10-12): Skald keeps each visit's address with its
user agent, times, pages, source and the rest, and a lead's email and name,
so a person can be followed across days. That is the default - but only for
a new install. An install whose history predates 2.4.0 keeps today's
behaviour (no address, no email kept) until someone turns it on, because
its site's privacy notice may still promise otherwise:

    privacy.keep_ips      true / false. Unset: true on a new install, false
                          on one upgraded to 2.4.0 (store.ADDED_META,
                          history meta `privacy_legacy`)
    privacy.keep_days     how long a kept visit stays (default 395 days)
    conversions.identity  full / anonymous. Unset: full on a new install,
                          anonymous on one upgraded to 2.4.0

Each is a setting (Settings > This site > Privacy, settings_store.SCHEMA)
that config.yml or a settings row may set per site, per organisation or for
the install; the Docker image takes SKALD_KEEP_IPS and SKALD_IDENTITY.

"Upgraded" is read from the history file: the meta row, or a file still at
a schema before 13 (the upgrade has not run yet). No history file at all is
a new install.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import setting

KEEP_DAYS = 395
LEGACY_SCHEMA = 13               # store.SCHEMA_VERSION that added the meta row
LEGACY_KEY = "privacy_legacy"
TRUE = ("1", "true", "on", "yes")
FALSE = ("0", "false", "off", "no")


def history_path(config: dict, folder=None) -> Path | None:
    """The history file: the one the CLI resolved, else an absolute
    `history.db`, else history.sqlite in `folder`."""
    raw = ((config or {}).get("_resolved") or {}).get("history_db") or \
        setting(config or {}, "history", "db")
    if raw and Path(str(raw)).expanduser().is_absolute():
        return Path(str(raw)).expanduser()
    return Path(folder) / "history.sqlite" if folder is not None else None


def legacy(config: dict, folder=None) -> bool:
    """True when this install's history predates 2.4.0 (see the module)."""
    path = history_path(config, folder)
    if path is None or not path.is_file():
        return False
    try:
        db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    except sqlite3.Error:
        return True
    try:
        rows = dict(db.execute("SELECT key, value FROM meta WHERE key IN "
                               "('schema_version', ?)", (LEGACY_KEY,)).fetchall())
    except sqlite3.Error:
        return False                      # an empty file: nothing written yet
    finally:
        db.close()
    if LEGACY_KEY in rows:
        return True
    try:
        return int(rows.get("schema_version") or LEGACY_SCHEMA) < LEGACY_SCHEMA
    except ValueError:
        return True


def _flag(raw) -> bool | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    word = str(raw).strip().lower()
    return True if word in TRUE else False if word in FALSE else None


def keep_ips(config: dict, folder=None) -> bool:
    """Whether this site keeps each visit's address (people/visits.py)."""
    got = _flag(setting(config or {}, "privacy", "keep_ips"))
    return got if got is not None else not legacy(config, folder)


def identity_full(config: dict, folder=None) -> bool:
    """Whether this site keeps a lead's name and email with its conversions."""
    raw = str(setting(config or {}, "conversions", "identity", "") or "").strip().lower()
    if raw in ("full", "anonymous"):
        return raw == "full"
    return not legacy(config, folder)


def keep_days(config: dict) -> int:
    try:
        return max(1, int(setting(config or {}, "privacy", "keep_days", KEEP_DAYS)))
    except (TypeError, ValueError):
        return KEEP_DAYS


def describe(config: dict, folder=None) -> dict:
    """{"keep_ips", "identity", "keep_days", "legacy"} for the page and doctor."""
    return {"keep_ips": keep_ips(config, folder),
            "identity": "full" if identity_full(config, folder) else "anonymous",
            "keep_days": keep_days(config), "legacy": legacy(config, folder)}
