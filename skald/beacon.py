"""In-page events: what a beacon may say, and where accepted ones are kept.

A server log sees every request but nothing that happens inside a page: a
click on "Book a demo", a form started, the reader reaching the bottom. The
website posts those to its own server (`POST /traffic-beacon`, the helper in
beacon_server.py), and this module decides what is accepted.

Only these fields, nothing else:

  e   the event, one of EVENTS
  p   the page's path ("/pricing/"), no query string, no fragment
  id  which button or form (a short lowercase token: "signup_hero",
      "demo_header"); for outbound_click the host the link goes to
  r   the referring host of the visit ("google.com"), "" when none
  u   the visit's utm_source, a short lowercase token
  vw  the viewport width bucket, one of VIEWPORTS
  t   seconds between opening the page and the event (an offset, never a
      clock time)
  v   the anonymous visitor ID the page made ("skv_" + 22 base64url
      characters, docs/BEACON.md); anything else is dropped. Kept in the
      spool only when `beacon.visitor_ids` is true (default false)

Never an address, a user id, a cookie or free text (`v` is a random ID the
browser made, not a person's): a value that is not one
of these shapes is refused (e, p, vw, t, unknown keys) or dropped (id, r,
u), and the helper never writes the sender's address anywhere.

Accepted events are appended to a spool, one JSON line each, one file per
local day: <spool>/<YYYY-MM-DD>.jsonl. The spool is to events what the access
log is to requests - the raw record that collect counts and the audit
recounts - and holds no address either. It is kept `keep_days` days.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .classify import AI_UTM, assistant_name, cited_by
from .config import setting
from .dimensions import source_type

# The events a page may send, in the order reports list them. skald.js sends
# all of them by itself except CODE_ONLY (tests/test_snippet.py checks it).
EVENTS = ("cta_click", "book_demo_open", "demo_booked", "signup_start", "signup_submit",
          "contact_submit", "waitlist_submit", "outbound_click", "scroll_75", "copy_text",
          "404_view",
          # Phase 4b: skald.js's own events (conversions.BEACON_ACTIONS maps
          # the conversions among them).
          "form_start", "form_submit", "calendly_open", "calendly_time_selected",
          "calendly_booked", "cal_open", "cal_booked", "hubspot_meeting_booked",
          "tel_click", "mailto_click")
# The events skald.js never sends by itself: only the site's own code does
# (skald('track', ...) or its own beacon). The Events page and the guide say so.
CODE_ONLY = ("book_demo_open", "demo_booked")
# Beacon-only mode (skald.js): a page view, for a site whose server log
# cannot be read, and a visitor's journey. Accepted only when
# `beacon.page_views` or `beacon.visitor_ids` is true.
PAGE_VIEW = "page_view"

LABELS = {"cta_click": "Button clicks", "book_demo_open": "Demo booking opened",
          "demo_booked": "Demo booked", "signup_start": "Sign-up started",
          "signup_submit": "Sign-up sent", "contact_submit": "Contact form sent",
          "waitlist_submit": "Early access sent", "outbound_click": "Links to other sites",
          "scroll_75": "Read three quarters", "copy_text": "Copied text",
          "404_view": "Saw the not-found page", PAGE_VIEW: "Page views (beacon)",
          "form_start": "Form started", "form_submit": "Form sent",
          "calendly_open": "Calendly opened", "calendly_time_selected": "Calendly time chosen",
          "calendly_booked": "Calendly booked", "cal_open": "Cal.com opened",
          "cal_booked": "Cal.com booked", "hubspot_meeting_booked": "HubSpot meeting booked",
          "tel_click": "Phone link clicks", "mailto_click": "Email link clicks"}

VIEWPORTS = ("xs", "sm", "md", "lg", "xl")
FIELDS = {"e", "p", "id", "r", "u", "vw", "t", "v"}
MAX_BODY = 1024
KEEP_DAYS = 400

_PATH = re.compile(r"^/[A-Za-z0-9\-._~!$&'()*+,;=:@%/]{0,299}$")
_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,59}$")
_HOST = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
                   r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$")
_UTM = re.compile(r"^[a-z0-9][a-z0-9_.+-]{0,59}$")
_VID = re.compile(r"^skv_[A-Za-z0-9_-]{22}$")


class Refused(ValueError):
    """A body that is not a beacon. `reason` is one word, for the counters."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


def visitor_ids(config: dict | None) -> bool:
    """`beacon.visitor_ids`: keep the page's anonymous visitor ID (default no)."""
    return setting(config or {}, "beacon", "visitor_ids", False) in (True, "true")


def allowed_events(config: dict | None) -> tuple[str, ...]:
    """page_view counts in beacon-only mode and for visitor journeys."""
    if setting(config or {}, "beacon", "page_views", False) in (True, "true") or \
            visitor_ids(config):
        return EVENTS + (PAGE_VIEW,)
    return EVENTS


def validate(raw: bytes, events: tuple[str, ...] = EVENTS) -> dict:
    """The beacon in `raw`, cleaned, or Refused. Never raises anything else."""
    if len(raw) > MAX_BODY:
        raise Refused("body", "more than 1 KB")
    try:
        got = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Refused("body", "not JSON") from None
    if not isinstance(got, dict):
        raise Refused("body", "not a JSON object")
    extra = set(got) - FIELDS
    if extra:
        raise Refused("field", "unknown field " + sorted(extra)[0][:20])
    event = got.get("e")
    if not isinstance(event, str) or event not in events:
        raise Refused("event", "not an event this site counts")
    path = got.get("p")
    if not isinstance(path, str) or not _PATH.match(path) or ".." in path:
        raise Refused("path", "not a path")
    view = got.get("vw", "")
    if view not in ("",) + VIEWPORTS:
        raise Refused("field", "viewport is not a bucket")
    offset = got.get("t", 0)
    if isinstance(offset, bool) or not isinstance(offset, (int, float)) or \
            not 0 <= offset <= 86400:
        raise Refused("field", "t is not 0 to 86400 seconds")
    out = {"e": event, "p": path, "vw": view, "t": int(offset)}
    for key, shape in (("id", _TOKEN), ("r", _HOST), ("u", _UTM)):
        value = got.get(key)
        value = value.strip().lower() if isinstance(value, str) else ""
        out[key] = value if value and shape.match(value) else ""
    if out["r"].startswith("www."):
        out["r"] = out["r"][4:]
    vid = got.get("v")
    if isinstance(vid, str) and _VID.fullmatch(vid):
        out["v"] = vid
    return out


def source_of(ref_host: str, utm_source: str, own_hosts: set[str]) -> tuple[str, str]:
    """(source type, assistant) of the visit an event came from, by the same
    rules as a reader's source in the log (dimensions.source_type)."""
    referrer = f"https://{ref_host}/" if ref_host else ""
    url = f"/?utm_source={utm_source}" if utm_source else "/"
    ai = cited_by(referrer)
    if not ai and utm_source:
        tagged = AI_UTM.search(url)
        ai = assistant_name(tagged.group(1)) if tagged else ""
    return source_type(referrer, url, bool(ai), own_hosts), ai


def own_hosts(config: dict) -> set[str]:
    hosts = setting(config, "site", "hosts") or []
    if isinstance(hosts, str):
        hosts = [hosts]
    return {str(h).lower() for h in hosts}


# ------------------------------------------------------------------ spool

def spool_dir(config: dict, config_path: Path | None = None,
              live_dir: Path | None = None) -> Path:
    """`beacon.spool`, else <the history file's folder>/beacon."""
    raw = setting(config, "beacon", "spool")
    if raw:
        p = Path(str(raw)).expanduser()
        if p.is_absolute() or config_path is None:
            return p
        return Path(config_path).resolve().parent / p
    if live_dir is not None:
        return Path(live_dir) / "beacon"
    db = Path(str(setting(config, "history", "db", "history.sqlite"))).expanduser()
    if not db.is_absolute() and config_path is not None:
        db = Path(config_path).resolve().parent / db
    return db.parent / "beacon"


def day_file(spool: Path, day: date) -> Path:
    return Path(spool) / f"{day.isoformat()}.jsonl"


def line_for(event: dict, at: datetime, group: str, source: str, ai: str) -> str:
    """The spool line for one accepted event. No address, no user agent."""
    row = {"at": at.isoformat(timespec="seconds"), "g": group, "s": source, **event}
    if ai:
        row["ai"] = ai
    return json.dumps(row, separators=(",", ":"), sort_keys=True)


def read_day(spool: Path, day: date) -> list[dict]:
    """Every event line of a day's spool. A torn or foreign line is skipped
    and counted in the returned list's `bad` attribute."""
    out = _Rows()
    path = day_file(spool, day)
    if not path.exists():
        return out
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                out.bad += 1
                continue
            if isinstance(row, dict) and isinstance(row.get("e"), str) and \
                    isinstance(row.get("p"), str):
                out.append(row)
            else:
                out.bad += 1
    return out


class _Rows(list):
    bad = 0


def prune(spool: Path, today: date, keep_days: int = KEEP_DAYS) -> int:
    """Delete spool and counter files older than keep_days. Files removed."""
    cutoff = today - timedelta(days=keep_days)
    gone = 0
    for path in Path(spool).glob("*.json*"):
        stem = path.name.split(".", 1)[0].replace("stats-", "")
        try:
            day = date.fromisoformat(stem)
        except ValueError:
            continue
        if day < cutoff:
            path.unlink(missing_ok=True)
            gone += 1
    return gone


def stats_file(spool: Path, day: date) -> Path:
    return Path(spool) / f"stats-{day.isoformat()}.json"


def read_stats(spool: Path, day: date) -> dict | None:
    try:
        got = json.loads(stats_file(spool, day).read_text())
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) else None
