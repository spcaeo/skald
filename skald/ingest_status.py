"""What the log endpoint last did for a site, for the Test button in
Settings > Data > Send logs and the set-up wizard (sites/status, connections_api.py).

One small JSON file per site in the live folder (the history's folder):

    <history folder>/ingest-status/<site>.json
    {"last_batch":   {"at", "lines", "rejected", "shipper"},
     "last_contact": "<when any batch was answered 200>",
     "today":        {"day": "YYYY-MM-DD" (UTC), "lines": N},
     "last_refusal": {"at", "code", "reason", "words"}}

`note` is called by ingest._answer after every answer to /traffic-ingest/
(the shipper's batches and the platforms' drains). It keeps no address, no
user agent, no token and no line: only the time, the counts, the shipper's
own id (or the drain's name) and, for a refusal, the HTTP code with a
reason word from REASONS. The server's own refusal text is not kept either.

Cheap and never in the way: a write is a temp file and a rename, under a
per-site lock in this process, and any failure is swallowed. A refusal is
written only for a site this install knows (its ingest folder exists, or a
config names it), and at most once a second per site, so a stream of bad
posts cannot fill the disk or slow the endpoint.

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
_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()
_LAST_REFUSAL: dict[str, float] = {}

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
    with _lock(str(path)):
        got = read(base, site)
        change(got)
        path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
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
    _write(base, site, change)


def refused(base, site: str, code: int, error: str, now: float | None = None) -> None:
    """A refusal: its code and reason word, at most once a second per site."""
    now = time.time() if now is None else now
    with _GUARD:
        if now - _LAST_REFUSAL.get(site, 0.0) < REFUSAL_GAP:
            return
        if len(_LAST_REFUSAL) > 1000:
            _LAST_REFUSAL.clear()
        _LAST_REFUSAL[site] = now
    why = reason(code, error)

    def change(got: dict) -> None:
        got["last_refusal"] = {"at": _stamp(now), "code": int(code), "reason": why,
                               "words": REASONS[why]}
    _write(base, site, change)


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
