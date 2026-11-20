"""What the log endpoint last did for a site, for the Test button in
Settings > Data > Send logs and the set-up wizard (sites/status, connections_api.py).

One small JSON file per site in the live folder (the history's folder):

    <history folder>/ingest-status/<site>.json
    {"last_batch":   {"at", "lines", "rejected", "shipper"},
     "last_contact": "<when any batch was answered 200>",
     "today":        {"day": "YYYY-MM-DD" (UTC), "lines": N},
     "last_refusal": {"at", "code", "reason", "words"},
     "refused":      {"YYYY-MM-DDTHH:MM" (UTC, the quarter hour): {reason: count}}, every
                     refusal, the last KEEP_DAYS only (SKALD-34: Data quality's "Refused at
                     the log endpoint"; quarter hours, so a site day in a half-hour or
                     45-minute time zone gets exactly its own)
     "counting_since": "<when this file first counted refusals>" (SKALD-34; absent before),
     "first_lines":  "<when lines were first kept>" (2.43; absent before),
     "minutes":      {"YYYY-MM-DDTHH:MM": lines}, the last RECENT_MINUTES only
                     (2.43: the set-up's live "N in the last 15 min", setup_live.py)}

`note` is called by ingest._answer after every answer to /traffic-ingest/
(the shipper's batches and the platforms' drains). It keeps no address, no
user agent, no token and no line: only the time, the counts, the shipper's
own id (or the drain's name) and, for a refusal, the HTTP code with a
reason word from REASONS. The server's own refusal text is not kept either.

Cheap and never in the way: a write is a temp file and a rename, under a
per-site lock in this process, and any failure is swallowed. A refusal is
written only for a site this install knows (its ingest folder exists, or a
config names it), and at most once a second per site, so a stream of bad
posts cannot fill the disk or slow the endpoint. Every refusal is still
counted (SKALD-34): the ones in between wait in memory and are added at the
next write, or by a timer a second later (`flush`).

skald-ship-check's own probe (check.sh: a POST with no token and the header
`X-Skald-Check: 1`, which expects the 401) is not a refusal: it is not
written, so a good set-up never shows one.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .files import slug

FOLDER = "ingest-status"
REFUSAL_GAP = 1.0              # seconds between two refusals written for one site
RECENT_MINUTES = 15            # the per-minute counts kept (setup_live.py)
KEEP_DAYS = 35                 # the hours of refusal counts kept (Data quality's days)
_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()
_LAST_REFUSAL: dict[str, float] = {}
# (base, site) -> {hour: {reason: count}}: refusals counted, not written yet (SKALD-34).
_PENDING: dict[tuple[str, str], dict] = {}
_TIMERS: set[tuple[str, str]] = set()

# reason word -> the plain words the page shows (and what to do about it)
REASONS = {
    "no_token": "No token was sent.",
    "bad_token": "The token is wrong or was revoked.",
    "wrong_site": "The token is not for this site.",
    "not_sending": "The token is not a sending token (it has no ingest scope).",
    "not_verified": "The site is not verified yet, so nothing is collected for it.",
    "removed": "The site was removed.",
    "not_here": "This server does not process this site.",
    "rate_limited": "Too many batches at once. The shipper slows down and catches up.",
    "edge_limited": "Too many posts from the edge at once. Those records are lost: a Worker does not send them again.",
    "day_full": "Today's limit of log data is used up. The shipper sends the rest later.",
    "plan_limit": "Over the plan's limit.",
    "read_only": "The organisation is read-only (billing).",
    "disk": "Skald's server is short of disk space. The shipper tries again later.",
    "bad_format": "The site's log format does not match what was sent.",
    "bad_batch": "The batch was malformed.",
    "too_large": "The batch was too large.",
    "no_accounts": "Accounts are not set up on Skald's server.",
    "off": "The log endpoint is switched off on Skald's server.",
    "other": "Refused.",
}


def folder(base) -> Path:
    return Path(base) / FOLDER


def path_for(base, site: str) -> Path:
    return folder(base) / f"{slug(site)}.json"


def reason(code: int, error: str) -> str:
    """The reason word for a refusal: its HTTP code and the server's words."""
    text = str(error or "").lower()
    if code == 401:
        return "no_token" if "needed" in text else "bad_token"
    if code == 403:
        if "not for that site" in text:
            return "wrong_site"
        if "scope" in text:
            return "not_sending"
        if "verified" in text:
            return "not_verified"
        return "other"
    if code == 429:
        if "edge posts" in text:          # ingest_drain.EDGE_LIMIT_WORDS (SKALD-34)
            return "edge_limited"
        if "slow down" in text:
            return "rate_limited"
        if "plan" in text or "month" in text:
            return "plan_limit"
        return "day_full"
    if code == 400:
        return "bad_format" if "format" in text else "bad_batch"
    return {402: "read_only", 404: "not_here" if "process" in text else "off",
            410: "removed", 411: "bad_batch", 413: "too_large", 415: "bad_batch",
            503: "no_accounts", 507: "disk"}.get(code, "other")


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read(base, site: str) -> dict:
    try:
        got = json.loads(path_for(base, site).read_text())
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def _lock(key: str) -> threading.Lock:
    with _GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def _write(base, site: str, change) -> None:
    path = path_for(base, site)
    if not Path(base).is_dir():
        return                            # never makes a history folder that is gone
    with _lock(str(path)):
        path.parent.mkdir(mode=0o750, exist_ok=True)
        got = read(base, site)
        change(got)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(got, separators=(",", ":"), sort_keys=True))
        os.replace(tmp, path)


def accepted(base, site: str, lines: int, rejected: int, shipper: str,
             now: float | None = None) -> None:
    """A batch answered 200: its counts and when."""
    now = time.time() if now is None else now
    stamp, day = _stamp(now), _stamp(now)[:10]

    def change(got: dict) -> None:
        got["last_contact"] = stamp
        if lines or rejected:
            got["last_batch"] = {"at": stamp, "lines": int(lines), "rejected": int(rejected),
                                 "shipper": shipper}
        today = got.get("today") if isinstance(got.get("today"), dict) else {}
        if today.get("day") != day:
            today = {"day": day, "lines": 0}
        today["lines"] = int(today.get("lines") or 0) + int(lines)
        got["today"] = today
        got.setdefault("counting_since", stamp)
        if lines:
            got.setdefault("first_lines", stamp)
            got["minutes"] = _minutes(got.get("minutes"), now, int(lines))
    _write(base, site, change)


def _minutes(old, now: float, lines: int = 0) -> dict:
    """The per-minute counts of the last RECENT_MINUTES, with `lines` added now."""
    cut = _stamp(now - RECENT_MINUTES * 60)[:16]
    out = {k: v for k, v in (old.items() if isinstance(old, dict) else ())
           if isinstance(k, str) and k > cut and isinstance(v, int)}
    key = _stamp(now)[:16]
    out[key] = out.get(key, 0) + lines
    return out


def recent(base, site: str, now: float | None = None) -> dict:
    """{"lines": kept in the last RECENT_MINUTES, "newest_at", "first_at",
    "shipper"}: the set-up's live line (setup_live.py). Read only."""
    now = time.time() if now is None else now
    got = read(base, site)
    cut = _stamp(now - RECENT_MINUTES * 60)[:16]
    mins = got.get("minutes") if isinstance(got.get("minutes"), dict) else {}
    lines = sum(v for k, v in mins.items() if isinstance(v, int) and k > cut)
    batch = got.get("last_batch") if isinstance(got.get("last_batch"), dict) else {}
    return {"lines": lines, "newest_at": batch.get("at"), "first_at": got.get("first_lines"),
            "shipper": batch.get("shipper")}


def refused(base, site: str, code: int, error: str, now: float | None = None) -> None:
    """A refusal: counted always (by UTC hour and reason); its code and reason word
    written at most once a second per site, with the counts waiting since."""
    now = time.time() if now is None else now
    why = reason(code, error)
    key = (str(base), site)
    with _GUARD:
        hours = _PENDING.setdefault(key, {})
        hour = hours.setdefault(quarter(now), {})
        hour[why] = hour.get(why, 0) + 1
        if now - _LAST_REFUSAL.get(site, 0.0) < REFUSAL_GAP:
            _later(base, site)
            return
        if len(_LAST_REFUSAL) > 1000:
            _LAST_REFUSAL.clear()
        _LAST_REFUSAL[site] = now

    def change(got: dict) -> None:
        got["last_refusal"] = {"at": _stamp(now), "code": int(code), "reason": why,
                               "words": REASONS[why]}
        _add(got, _take(key), now)
    _write(base, site, change)


def quarter(now: float) -> str:
    """The UTC quarter hour of `now`: "YYYY-MM-DDTHH:MM", minutes 00, 15, 30 or 45."""
    stamp = _stamp(now)
    return f"{stamp[:14]}{int(stamp[14:16]) // 15 * 15:02d}"


def _take(key) -> dict:
    with _GUARD:
        return _PENDING.pop(key, {})


def _add(got: dict, hours: dict, now: float) -> None:
    """Add waiting counts to the file's, and drop hours older than KEEP_DAYS."""
    got.setdefault("counting_since", _stamp(now))
    old = got.get("refused") if isinstance(got.get("refused"), dict) else {}
    for hour, by in hours.items():
        into = old[hour] = old[hour] if isinstance(old.get(hour), dict) else {}
        for why, n in by.items():
            into[why] = int(into.get(why) or 0) + n
    cut = quarter(now - KEEP_DAYS * 86400)
    got["refused"] = {h: v for h, v in old.items() if isinstance(h, str) and h >= cut}


def flush(base, site: str, now: float | None = None) -> None:
    """Write the refusals counted since the last write (none: nothing is written)."""
    key = (str(base), site)
    with _GUARD:
        _TIMERS.discard(key)
        if not _PENDING.get(key):
            return
    now = time.time() if now is None else now
    try:
        _write(base, site, lambda got: _add(got, _take(key), now))
    except Exception:                     # noqa: BLE001 - the status never stops anything
        pass


def flush_all() -> None:
    for base, site in list(_PENDING):
        flush(base, site)


def _later(base, site: str) -> None:
    """One flush a second from now for this site (called under _GUARD)."""
    key = (str(base), site)
    if key in _TIMERS:
        return
    _TIMERS.add(key)
    timer = threading.Timer(REFUSAL_GAP, flush, args=(base, site))
    timer.daemon = True
    timer.start()


CHECK_HEADER = "X-Skald-Check"      # check.sh's tokenless probe of the send address
BATCH = re.compile(r"^(?P<shipper>[A-Za-z0-9_-]{1,64}):\d{1,18}$")


def note(h, code: int, body: dict) -> None:
    """Called by ingest._answer: keep what this answer says about its site.
    `h._skald_ingest` (set by ingest._handle once the path named a site):
    {"base", "site", "known" (a function), "shipper" (a drain's name)}."""
    ctx = getattr(h, "_skald_ingest", None)
    if not ctx:
        return
    try:
        base, site = ctx["base"], ctx["site"]
        if code == 200:
            if body.get("duplicate"):
                return
            shipper = ctx.get("shipper")
            if not shipper:
                m = BATCH.match(h.headers.get("X-Skald-Batch") or "")
                shipper = m.group("shipper") if m else "shipper"
            accepted(base, site, int(body.get("accepted") or 0),
                     int(body.get("rejected") or 0), shipper)
            return
        if code == 401 and h.headers.get(CHECK_HEADER) == "1" and not h.headers.get("Authorization"):
            return                        # skald-ship-check's probe: the 401 it expects
        known = ctx.get("known")
        if path_for(base, site).exists() or (known is not None and known()):
            refused(base, site, code, str(body.get("error") or ""))
    except Exception:                     # noqa: BLE001 - the status never stops an answer
        pass


def status(base, site: str) -> dict:
    """The file as the page reads it, with the reason words filled in."""
    got = read(base, site)
    today = got.get("today") if isinstance(got.get("today"), dict) else None
    if today and today.get("day") != _stamp(time.time())[:10]:
        today = {"day": _stamp(time.time())[:10], "lines": 0}
    last = got.get("last_refusal")
    if isinstance(last, dict) and last.get("reason") in REASONS:
        last = {**last, "words": REASONS[last["reason"]]}
    return {"last_batch": got.get("last_batch"), "last_contact": got.get("last_contact"),
            "today": today, "last_refusal": last}
