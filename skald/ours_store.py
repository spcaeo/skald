"""Internal addresses the owner adds from the dashboard, kept beside config.

config.yml's `ours.addresses` stay read-only. `ours.file` (on the server
/var/lib/skald/ours.json, owned by skald; when it is not set,
ours.json beside the history, like the other state files) holds the entries
added on the page:

    {"entries": [{"ip": "203.0.113.7", "label": "Home laptop",
                  "added_at": "2026-10-07T13:05:00+00:00", "added_from": "page",
                  "site": "<site name>"}]}

`site` is the page it was added on (since accounts): in sessions mode only an
install admin changes the list (it applies to every site), and an org admin
who is not one sees only the entries added on their own sites' pages
(`for_sites`), never the config file's.

An entry applies from its `added_at` on - to the live view and to days not
yet collected - so a stored day is never rewritten, and re-collecting an
older day gives the same answer it gave before. Removing an entry stops it
applying. Every change is appended to the change log (`ours.change_log`,
on the server /var/log/skald/ours-changes.log) with time, action,
label and address. Addresses appear here, in the log and in the page's
management list; never in the data files, CSV exports or mail.
"""
from __future__ import annotations

import ipaddress
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .files import write_atomic

LIMIT = 50
LABEL_MAX = 60


class Invalid(ValueError):
    """Input the list will not take."""


class Full(ValueError):
    """The list is at LIMIT."""


def path_of(config: dict) -> Path | None:
    """`ours.file`, else ours.json beside the history; None when neither is
    known (no history folder resolved): then nothing can be added."""
    raw = ((config or {}).get("ours") or {}).get("file")
    if raw:
        return Path(str(raw))
    from .settings_store import history_folder
    folder = history_folder(config)
    return folder / "ours.json" if folder is not None else None


def log_of(config: dict) -> Path | None:
    raw = ((config or {}).get("ours") or {}).get("change_log")
    return Path(str(raw)) if raw else None


def load(path: Path | None) -> list[dict]:
    """The file's entries; [] when there is no file or it cannot be read."""
    if path is None:
        return []
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return []
    out = []
    for e in (data.get("entries") if isinstance(data, dict) else None) or []:
        try:
            entry = {"ip": normal(e["ip"]), "label": clean_label(e.get("label")),
                     "added_at": str(e.get("added_at") or ""),
                     "added_from": str(e.get("added_from") or "")}
            if isinstance(e.get("site"), str) and e["site"]:
                entry["site"] = e["site"][:253]
            out.append(entry)
        except (Invalid, KeyError, TypeError):
            continue
    return out


def normal(value) -> str:
    """An address or CIDR range, canonical; Invalid otherwise."""
    text = str(value or "").strip()
    if not text or len(text) > 64:
        raise Invalid("enter an IPv4 or IPv6 address, or a range like 203.0.113.0/24")
    try:
        if "/" in text:
            net = ipaddress.ip_network(text, strict=False)
            if net.prefixlen == net.max_prefixlen:
                return str(net.network_address)
            if (net.version == 4 and net.prefixlen < 16) or (net.version == 6 and net.prefixlen < 32):
                raise Invalid("that range is too wide (at most /16 for IPv4, /32 for IPv6)")
            return str(net)
        return str(ipaddress.ip_address(text))
    except ValueError as why:
        if isinstance(why, Invalid):
            raise
        raise Invalid(f"{text!r} is not an IP address or range") from None


def clean_label(value) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise Invalid("give it a label, e.g. Office Mac")
    if len(text) > LABEL_MAX:
        raise Invalid(f"labels are at most {LABEL_MAX} characters")
    if any(ord(c) < 32 for c in text):
        raise Invalid("the label has control characters")
    return text


def since(entry: dict) -> datetime | None:
    try:
        when = datetime.fromisoformat(entry.get("added_at") or "")
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def config_entries(config: dict) -> list[dict]:
    """config.yml's addresses, read-only, in the same shape."""
    from .config import ours_entries
    raw = ((config or {}).get("ours") or {}).get("addresses")
    return [{"ip": ip, "label": label, "added_at": None, "added_from": None,
             "source": "config", "editable": False}
            for ip, label in ours_entries(raw, "addresses")]


def listing(config: dict) -> list[dict]:
    """Config entries then file entries, as the management list shows them."""
    return config_entries(config) + [{**e, "source": "file", "editable": True}
                                     for e in load(path_of(config))]


def for_sites(config: dict, sites) -> list[dict]:
    """Only the page-added entries made on one of `sites`' pages."""
    keep = set(sites or ())
    return [e for e in listing(config) if e["source"] == "file" and e.get("site") in keep]


def _save(path: Path, entries: list[dict]) -> None:
    write_atomic(path, json.dumps({"entries": entries}, indent=1) + "\n")
    os.chmod(path, 0o640)


def _log(config: dict, action: str, entry: dict, now: datetime, by: str = "") -> None:
    """One line per change: time, action, label, address, from where, and -
    since named users (access.py) - who."""
    path = log_of(config)
    if path is None:
        return
    line = (f"{now.isoformat(timespec='seconds')}\t{action}\t{entry['label']}\t"
            f"{entry['ip']}\t{entry.get('added_from') or ''}\t{by}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)


def add(config: dict, ip, label, added_from: str = "page",
        now: datetime | None = None, by: str = "", site: str = "") -> dict:
    path = path_of(config)
    if path is None:
        raise Invalid("this server does not know where to keep the list; "
                      "whoever runs it sets ours.file in config.yml")
    entry = {"ip": normal(ip), "label": clean_label(label),
             "added_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
             "added_from": clean_label(added_from)}
    if by:
        entry["added_by"] = clean_label(by)
    if site:
        entry["site"] = str(site)[:253]
    entries = load(path)
    if any(e["ip"] == entry["ip"] for e in config_entries(config) + entries):
        raise Invalid(f"{entry['ip']} is already listed")
    if len(config_entries(config)) + len(entries) >= LIMIT:
        raise Full(f"the list holds at most {LIMIT} addresses; remove one first")
    entries.append(entry)
    _save(path, entries)
    _log(config, "add", entry, now or datetime.now(timezone.utc), by)
    return entry


def remove(config: dict, ip, now: datetime | None = None, by: str = "") -> dict:
    path = path_of(config)
    target = normal(ip)
    entries = load(path)
    gone = next((e for e in entries if e["ip"] == target), None)
    if gone is None:
        if any(e["ip"] == target for e in config_entries(config)):
            raise Invalid("that address is in config.yml; change it on the server")
        raise Invalid(f"{target} is not in the list")
    _save(path, [e for e in entries if e["ip"] != target])
    _log(config, "remove", gone, now or datetime.now(timezone.utc), by)
    return gone
