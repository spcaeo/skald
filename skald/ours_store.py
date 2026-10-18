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
older day gives the same answer it gave before. That holds for every change
(2026-10-18), because nothing is ever taken out of the file:

- Pause / resume. The pauses stay on the entry:

    "paused": [["2026-10-18T17:23:36+00:00", "2026-10-18T19:00:00+00:00"],
               ["2026-10-19T09:00:00+00:00", null]]

  Each pair is [from, to]; `to` null means still paused.
- Delete. The entry gets `removed_at` and leaves the list, the limit and
  the duplicate check, but stays in the file, so the days before it still
  recount the same.
- Edit (label or address). The old entry ends (`removed_at` = now,
  `replaced_by` the new address) and a new entry starts now with the new
  values (an open pause carries over, starting now). A day before the edit
  recounts under the old label and address; a day after under the new.

So an entry applies to a request at time t when added_at <= t, t is before
`removed_at` (when set), and t is in no pause (from <= t < to; from <= t
when `to` is null). A time that does not read as ISO is ignored, by this
road and by the audit's own (audit_visits.page_added). Entries from
config.yml always apply and cannot be paused, edited or deleted here.

Every change is appended to the change log (`ours.change_log`, on the server
/var/log/skald/ours-changes.log) with time, action, label and
address. Addresses appear here, in the log and in the page's management
list; never in the data files, CSV exports or mail.
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
    """The file's entries, deleted and replaced ones included (the counting
    needs them for the days before); [] when there is no file or it cannot
    be read. `live()` keeps the ones still listed."""
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
            for key, size in (("site", 253), ("added_by", LABEL_MAX),
                              ("replaced_by", 64), ("removed_by", LABEL_MAX)):
                if isinstance(e.get(key), str) and e[key]:
                    entry[key] = e[key][:size]
            if _when(e.get("removed_at")) is not None:
                entry["removed_at"] = e["removed_at"]
            pairs = _pause_pairs(e.get("paused"))
            if pairs:
                entry["paused"] = pairs
            out.append(entry)
        except (Invalid, KeyError, TypeError):
            continue
    return out


def live(entries: list[dict]) -> list[dict]:
    """The entries still listed: not deleted, not replaced by an edit."""
    return [e for e in entries if not e.get("removed_at")]


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


def _when(text) -> datetime | None:
    """An ISO time, made aware (UTC when it names no zone); None otherwise."""
    if not isinstance(text, str):
        return None
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def since(entry: dict) -> datetime | None:
    return _when(entry.get("added_at") or "")


def until(entry: dict) -> datetime | None:
    """When a deleted or edited entry stopped applying; None while listed."""
    return _when(entry.get("removed_at"))


def _pause_pairs(raw) -> list[list]:
    """The readable [from, to-or-None] pairs of `paused`, as text."""
    out = []
    for pair in raw if isinstance(raw, list) else []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        start, end = pair
        if _when(start) is None or (end is not None and _when(end) is None):
            continue
        out.append([start, end])
    return out


def pauses(entry: dict) -> list[tuple[datetime, datetime | None]]:
    """The entry's pauses as (from, to or None) times."""
    return [(_when(a), _when(b) if b is not None else None)
            for a, b in _pause_pairs(entry.get("paused"))]


def paused_at(spans, when: datetime) -> bool:
    """Whether `when` falls in one of the pauses: from <= when < to."""
    return any(start <= when and (end is None or when < end) for start, end in spans)


def paused_since(entry: dict) -> str | None:
    """When the open pause began, or None when the entry applies now."""
    pairs = _pause_pairs(entry.get("paused"))
    return pairs[-1][0] if pairs and pairs[-1][1] is None else None


def config_entries(config: dict) -> list[dict]:
    """config.yml's addresses, read-only, in the same shape."""
    from .config import ours_entries
    raw = ((config or {}).get("ours") or {}).get("addresses")
    return [{"ip": ip, "label": label, "added_at": None, "added_from": None,
             "source": "config", "editable": False}
            for ip, label in ours_entries(raw, "addresses")]


def listing(config: dict) -> list[dict]:
    """Config entries then the listed file entries, as the management list
    shows them. Each says whether it applies now (`active`) and, when
    paused, since when."""
    return ([{**e, "active": True, "paused_since": None, "pausable": False}
             for e in config_entries(config)]
            + [{**e, "source": "file", "editable": True, "pausable": True,
                "active": paused_since(e) is None, "paused_since": paused_since(e)}
               for e in live(load(path_of(config)))])


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


def _stamp(now: datetime | None) -> tuple[datetime, str]:
    when = now or datetime.now(timezone.utc)
    return when, when.isoformat(timespec="seconds")


def _room(config: dict, listed: list[dict], ip: str, but: dict | None = None) -> None:
    """Refuse an address already listed (other than `but`), or a full list."""
    if any(e["ip"] == ip and e is not but for e in config_entries(config) + listed):
        raise Invalid(f"{ip} is already listed")
    if but is None and len(config_entries(config)) + len(listed) >= LIMIT:
        raise Full(f"the list holds at most {LIMIT} addresses; remove one first")


def add(config: dict, ip, label, added_from: str = "page",
        now: datetime | None = None, by: str = "", site: str = "") -> dict:
    path = path_of(config)
    if path is None:
        raise Invalid("this server does not know where to keep the list; "
                      "whoever runs it sets ours.file in config.yml")
    when, stamp = _stamp(now)
    entry = {"ip": normal(ip), "label": clean_label(label), "added_at": stamp,
             "added_from": clean_label(added_from)}
    if by:
        entry["added_by"] = clean_label(by)
    if site:
        entry["site"] = str(site)[:253]
    entries = load(path)
    _room(config, live(entries), entry["ip"])
    entries.append(entry)
    _save(path, entries)
    _log(config, "add", entry, when, by)
    return entry


def _find(config: dict, entries: list[dict], key) -> dict:
    """The listed page-added entry named by its address or label (any case)."""
    text = " ".join(str(key or "").split())
    if not text:
        raise Invalid("name the entry by its address or its label")
    try:
        target = normal(text)
    except Invalid:
        target = None
    listed = live(entries)
    found = [e for e in listed if e["ip"] == target] if target else []
    if not found:
        found = [e for e in listed if e["label"].casefold() == text.casefold()]
    if len(found) > 1:
        raise Invalid(f"{len(found)} entries are labelled {text!r}; name it by its address")
    if found:
        return found[0]
    if any(e["ip"] == target or e["label"].casefold() == text.casefold()
           for e in config_entries(config)):
        raise Invalid("that entry is in config.yml: it always applies and cannot be "
                      "changed here; change it on the server")
    raise Invalid(f"{text!r} is not in the list")


def remove(config: dict, ip, now: datetime | None = None, by: str = "") -> dict:
    """Delete an entry from the list: it stops applying now. It stays in the
    file with `removed_at`, so the days before still recount the same."""
    path = path_of(config)
    entries = load(path)
    gone = _find(config, entries, ip)
    when, stamp = _stamp(now)
    gone["removed_at"] = stamp
    if by:
        gone["removed_by"] = clean_label(by)
    _save(path, entries)
    _log(config, "remove", gone, when, by)
    return gone


def edit(config: dict, key, label=None, ip=None, now: datetime | None = None,
         by: str = "") -> dict:
    """Change an entry's label and/or address from now on: the old entry
    ends now and a new one starts now (an open pause carries over), so the
    days before recount under the old label and address."""
    path = path_of(config)
    entries = load(path)
    old = _find(config, entries, key)
    new_ip = normal(ip) if ip not in (None, "") else old["ip"]
    new_label = clean_label(label) if label not in (None, "") else old["label"]
    if (new_ip, new_label) == (old["ip"], old["label"]):
        raise Invalid("nothing to change: give a new label or a new address")
    _room(config, live(entries), new_ip, but=old)
    when, stamp = _stamp(now)
    new = {"ip": new_ip, "label": new_label, "added_at": stamp,
           "added_from": old.get("added_from") or "page"}
    for k in ("added_by", "site"):
        if old.get(k):
            new[k] = old[k]
    if paused_since(old) is not None:
        new["paused"] = [[stamp, None]]
    old["removed_at"] = stamp
    old["replaced_by"] = new_ip
    if by:
        old["removed_by"] = clean_label(by)
    entries.append(new)
    _save(path, entries)
    _log(config, "edit", {**new, "label": f"{old['label']} -> {new_label}"
                          if new_label != old["label"] else new_label,
                          "ip": f"{old['ip']} -> {new_ip}" if new_ip != old["ip"] else new_ip},
         when, by)
    return new


def _switch(config: dict, key, pause_it: bool, now: datetime | None, by: str) -> dict:
    path = path_of(config)
    entries = load(path)
    entry = _find(config, entries, key)
    when, stamp = _stamp(now)
    pairs = entry.get("paused") or []
    open_pause = bool(pairs) and pairs[-1][1] is None
    if pause_it:
        if open_pause:
            raise Invalid(f"{entry['label']} is already paused")
        pairs = pairs + [[stamp, None]]
    else:
        if not open_pause:
            raise Invalid(f"{entry['label']} is not paused")
        start = pairs[-1][0]
        end = stamp if when >= _when(start) else start
        pairs = pairs[:-1] + [[start, end]]
    entry["paused"] = pairs
    _save(path, entries)
    _log(config, "pause" if pause_it else "resume", entry, when, by)
    return entry


def pause(config: dict, key, now: datetime | None = None, by: str = "") -> dict:
    """Stop an entry applying from `now` on (its visits count as visitors)
    until it is resumed. Earlier pauses are kept, so recounts agree."""
    return _switch(config, key, True, now, by)


def resume(config: dict, key, now: datetime | None = None, by: str = "") -> dict:
    """Close the open pause at `now`: the entry applies again from then on."""
    return _switch(config, key, False, now, by)
