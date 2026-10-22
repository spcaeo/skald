"""What a site keeps about people, and the rule for an install that is upgraded.

The owner's decision (2026-10-12): Skald keeps each visit's address with its
user agent, times, pages, source and the rest, and a lead's email and name,
so a person can be followed across days. That is the default - but only for
a new install. An install whose history predates 2.4.0 keeps today's
behaviour (no address, no email kept) until someone turns it on, because
its site's privacy notice may still promise otherwise:

    privacy.keep_ips      full / short / off (2.15.0; true reads as full,
                          false as off). Unset: full on a new install, off
                          on one upgraded to 2.4.0 (store.ADDED_META,
                          history meta `privacy_legacy`)
    privacy.keep_days     how long a kept visit stays (default 395 days)
    conversions.identity  full / anonymous. Unset: full on a new install,
                          anonymous on one upgraded to 2.4.0

Each is a setting (Settings > This site > Privacy, settings_store.SCHEMA)
that config.yml or a settings row may set per site, per organisation or for
the install; the Docker image takes SKALD_KEEP_IPS (1, 0 or short) and
SKALD_IDENTITY.

The shortened address (`privacy.keep_ips: short`, `shorten`). The rule:

    IPv4   the last octet is zeroed: 203.0.113.57 -> 203.0.113.0
    IPv6   the first 48 bits are kept, the rest zeroed:
           2001:db8:85a3:8d3:: -> 2001:db8:85a3::
    IPv4-mapped IPv6 (::ffff:203.0.113.57) is IPv4: 203.0.113.0
    a value that is not an IP address is kept as it is ("(removed)")

Only what is KEPT about a person is shortened: the kept visits
(people/visits.py) and the address their first touch is looked up by
(firsttouch.py). The country and the city are looked up from the full
address before it is shortened, and everything that reads the raw log (bot
sorting, our own traffic, the totals) reads the full address. Switching full
to short shortens the rows already kept at the next nightly run
(visits.prune_kept); short to full keeps the old rows short, and only new
rows are full. The second count (audit_people.py) shortens by its own code.

"Upgraded" is read from the history file: the meta row, or a file still at
a schema before 13 (the upgrade has not run yet). No history file at all is
a new install.
"""
from __future__ import annotations

import ipaddress
import sqlite3
from pathlib import Path

from ..config import setting

KEEP_DAYS = 395
LEGACY_SCHEMA = 13               # store.SCHEMA_VERSION that added the meta row
LEGACY_KEY = "privacy_legacy"
TRUE = ("1", "true", "on", "yes")
FALSE = ("0", "false", "off", "no")
FULL, SHORT, OFF = "full", "short", "off"
MODES = (FULL, SHORT, OFF)


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


def mode_of(raw) -> str | None:
    """A `privacy.keep_ips` value as full, short or off; None when unset or
    not one of its words. true and the on words are full, false and the
    off words are off."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return FULL if raw else OFF
    word = str(raw).strip().lower()
    if word in (FULL, SHORT):
        return word
    got = _flag(word)
    return None if got is None else FULL if got else OFF


def ip_mode(config: dict, folder=None) -> str:
    """"full", "short" or "off": how this site keeps each visit's address."""
    got = mode_of(setting(config or {}, "privacy", "keep_ips"))
    if got is not None:
        return got
    return OFF if legacy(config, folder) else FULL


def keep_ips(config: dict, folder=None) -> bool:
    """Whether this site keeps each visit's address, in full or shortened
    (people/visits.py). `ip_mode` says which."""
    return ip_mode(config, folder) != OFF


def shorten(value) -> str:
    """The address as a site with `privacy.keep_ips: short` keeps it (the
    rule in the module): the last IPv4 octet zeroed, an IPv6 address cut to
    its first 48 bits. A value that is not an address comes back as it is."""
    text = "" if value is None else str(value)
    try:
        addr = ipaddress.ip_address(text.strip())
    except ValueError:
        return text
    if addr.version == 6 and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    raw = addr.packed
    if addr.version == 4:
        return str(ipaddress.IPv4Address(raw[:3] + b"\0"))
    return str(ipaddress.IPv6Address(raw[:6] + bytes(10)))


def kept_ip(config: dict, folder=None):
    """The function that turns a visit's address into what is kept: the
    address itself (full), `shorten` (short), or None (off)."""
    mode = ip_mode(config, folder)
    return None if mode == OFF else shorten if mode == SHORT else str


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
    """{"keep_ips", "ip_mode", "identity", "keep_days", "legacy"} for the
    page and doctor. keep_ips: an address is kept (full or short)."""
    mode = ip_mode(config, folder)
    return {"keep_ips": mode != OFF, "ip_mode": mode,
            "identity": "full" if identity_full(config, folder) else "anonymous",
            "keep_days": keep_days(config), "legacy": legacy(config, folder)}


# A conversion's reference (`external_ref`, 2.25): the sender's own record ID (an account
# ID, a booking's address), not a name or an email, so shown to every member who sees the
# lead. One exception: the page's script tag makes its reference from the visitor ID
# (conversions/from_beacon.py, "<vid>:<action>:<stage>:<at>"), so that one is shown only
# where a visitor ID may be: to owners and admins, never in a file every member reads.
VID_REFS = ("beacon",)


def shown_ref(tool, ref, private: bool):
    """The reference as this reader may see it: itself, or None."""
    return ref if private or tool not in VID_REFS else None
