"""Outgoing webhooks: Skald tells the owner's CRM, Zapier or Slack what
happened (Settings > Leads & integrations > Outgoing webhooks, docs/INTEGRATIONS.md).

Each site may have webhooks (table `webhooks`): a URL and the events it
wants (EVENTS). The live and daily runs call `run(..., deliver=False)` per
site (steps 1 and 2), then jobs.deliver calls `deliver_pass` once for every
site (step 3): DEADLINE seconds of wall clock a delivery, RUN_BUDGET for
the pass, the rest left for the next run. None of it ever raises:

  1. new conversions since the site's cursor (meta "outbox_cursor:<site>",
     by conversions.id) become outbox rows, one per webhook that wants the
     event; the first run, or a webhook added when the site had none, starts
     the cursor at the current last id, so old rows are never flooded out
  2. starts that are now abandoned (store.abandoned, conversions.abandon_hours)
     become "conversion.abandoned" rows, once each (the outbox's unique key)
  3. due rows are POSTed, at most `limit` a run: signed like Skald's own
     hooks, `X-Skald-Signature: t=<unix>,v1=<hex HMAC-SHA256 of
     "<t>.<body>">`, with the webhook's own secret (secrets.json, key
     "outgoing/<site>/<id>"); a 2xx is "sent", anything else is tried again
     after 1 minute, 5 minutes, 30 minutes, 2 hours and 12 hours, then
     "failed". Rows older than 90 days are deleted.

Events that are not conversions come through `notify`: the alert check
queues "ai.reading_changed" once per new AI alert (alerts_ai.py; its body is
the assistant, pages, days and numbers - nothing about a person), and
"alert.opened" once per new alert of any kind (alerts.hook_body: {site,
alert, text, figures, at}), and "todo.new" once per to-do new on Overview >
Insights (todo_rows.hook_body: {site, todo, figures, rows_total, link,
first_seen, text}; never a row and never an agent's code).

Slack: an address on hooks.slack.com (a Slack incoming webhook) takes only
{"text": ...}, so it gets the body's `text` (or one line made from a
conversion's fields) in that shape (`wire`); still signed, which Slack
ignores. Every other address gets the body as queued.

The body is a summary, never a name or an email: the action, stage, source,
campaign, landing page, country, device, visits before, time to convert and
the anonymous journey's paths (at most 50 page views). Its `id` is the
same on every retry, so the receiver can drop a repeat.

Only https, never redirected, and never to a private, loopback, link-local
or reserved address, nor an IPv6 address carrying an IPv4 one (HIDDEN_V4);
every address the name resolves to is checked and the connection made to
one that was checked. `get` reads a page with the same guards. `integrations.allow_private_urls: true` lifts
that, for tests and closed networks only.
"""
from __future__ import annotations

import http.client
import ipaddress
import json
import re
import secrets
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from ..config import setting
from . import secrets_store, store
from .adapters import sign_timed

EVENTS = ("conversion.started", "conversion.completed", "conversion.cancelled",
          "conversion.rescheduled", "conversion.no_show", "conversion.abandoned", "lead.won",
          "lead.lost", "ai.reading_changed", "alert.opened", "todo.new")
STAGE_EVENT = {"started": "conversion.started", "completed": "conversion.completed",
               "paid": "conversion.completed", "cancelled": "conversion.cancelled",
               "rescheduled": "conversion.rescheduled", "no_show": "conversion.no_show",
               "won": "lead.won", "lost": "lead.lost"}
BACKOFF = (60, 300, 1800, 7200, 43200)   # seconds before attempt 2, 3, ... 6
MAX_ATTEMPTS = len(BACKOFF) + 1
KEEP_DAYS = 90
DEADLINE = 10             # seconds of wall clock for one delivery, lookup to last byte
RUN_BUDGET = 30           # seconds one run spends on deliveries, every site together
HEAD_MAX = 16384          # bytes of an answer's status line and headers
LEASE = 300               # seconds a row is held by the run sending it
JOURNEY_MAX = 50
MAX_URL = 500
MAX_HOOKS = 10            # webhooks per site
LOG_ROWS = 50
HEADER = "X-Skald-Signature"
AGENT = "Skald-Webhooks/1"


class Refused(ValueError):
    """A URL or a list of events Skald will not send to."""


def secret_key(site: str, wid: int) -> str:
    return f"outgoing/{site}/{wid}"


def private_ok(config: dict) -> bool:
    return setting(config or {}, "integrations", "allow_private_urls", False) in (True, "true")


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(microsecond=0)


# ----------------------------------------------------------- the address

def check_url(url, config: dict) -> str:
    """The URL as kept, or Refused: https (http only with
    allow_private_urls), a host, no user name or password in it."""
    url = str(url or "").strip()
    if not url or len(url) > MAX_URL or any(c.isspace() for c in url):
        raise Refused("Give the full address, https://...")
    parts = urlsplit(url)
    allowed = ("https", "http") if private_ok(config) else ("https",)
    if parts.scheme not in allowed:
        raise Refused("The address must start with https://.")
    if not parts.hostname or parts.username or parts.password:
        raise Refused("The address needs a host name, and no user name or password in it.")
    try:
        parts.port
    except ValueError:
        raise Refused("The address has a port that is not a number.") from None
    return url


def check_events(events) -> list[str]:
    if isinstance(events, str):
        events = [e for e in events.replace(",", " ").split() if e]
    got = [str(e) for e in (events or [])]
    if not got or any(e not in EVENTS for e in got):
        raise Refused(f"Choose events from: {', '.join(EVENTS)}.")
    return [e for e in EVENTS if e in got]


# IPv6 ranges that carry an IPv4 address, refused whatever that address is:
# IPv4-compatible (::a.b.c.d), IPv4-mapped, 6to4, NAT64 (both) and Teredo.
HIDDEN_V4 = tuple(ipaddress.ip_network(n) for n in (
    "::/96", "::ffff:0:0/96", "2002::/16", "64:ff9b::/96", "64:ff9b:1::/48", "2001::/32"))


def bad_address(raw: str) -> bool:
    """True for an address Skald never connects to: not global, multicast,
    or an IPv6 address with an IPv4 address inside it."""
    try:
        ip = ipaddress.ip_address(str(raw).split("%", 1)[0])
    except ValueError:
        return True
    if ip.version == 6 and (ip.ipv4_mapped is not None or ip.sixtofour is not None
                            or ip.teredo is not None or any(ip in n for n in HIDDEN_V4)):
        return True
    return not ip.is_global or ip.is_multicast


def _resolve(host: str, port: int, seconds: float) -> list:
    """getaddrinfo, given at most `seconds` (it cannot be interrupted, so it
    runs in a thread that is left behind when it is late)."""
    box: dict = {}

    def look():
        try:
            box["got"] = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (OSError, UnicodeError) as why:
            box["why"] = why
    worker = threading.Thread(target=look, daemon=True)
    worker.start()
    worker.join(max(0.0, seconds))
    if worker.is_alive():
        raise Refused("The host name took too long to resolve.")
    if "why" in box:
        raise Refused(f"The host name does not resolve ({type(box['why']).__name__}).")
    return box["got"]


def public_address(host: str, port: int, config: dict, seconds: float | None = None) -> str:
    """The address to connect to for `host`: the first it resolves to, when
    every address it resolves to is public. Refused otherwise."""
    found = _resolve(host, port, DEADLINE if seconds is None else seconds)
    addresses = [info[4][0] for info in found]
    if not addresses:
        raise Refused("The host name does not resolve.")
    if not private_ok(config) and any(bad_address(a) for a in addresses):
        raise Refused("The address is on a private or reserved network.")
    return addresses[0]


class _Late(Exception):
    """The request's deadline passed."""


def _left(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise _Late()
    return left


def _recv(sock, deadline: float) -> bytes:
    sock.settimeout(_left(deadline))     # each read gets only what is left
    try:
        return sock.recv(65536)
    except (socket.timeout, TimeoutError):
        raise _Late() from None


def _unchunk(raw: bytes) -> bytes:
    out, at = bytearray(), 0
    while True:
        end = raw.find(b"\r\n", at)
        if end < 0:
            break
        try:
            size = int(raw[at:end].split(b";", 1)[0].strip() or b"0", 16)
        except ValueError:
            break
        if size <= 0:
            break
        out += raw[end + 2:end + 2 + size]
        at = end + 2 + size + 2
    return bytes(out)


def _answer(sock, deadline: float, max_bytes: int | None) -> tuple[int, bytes]:
    """(status, body) read under the deadline; the body only when max_bytes
    is set, at most that many bytes."""
    buf = bytearray()
    while b"\r\n\r\n" not in buf:
        if len(buf) > HEAD_MAX:
            raise http.client.HTTPException("headers too long")
        got = _recv(sock, deadline)
        if not got:
            break
        buf += got
    head, sep, rest = bytes(buf).partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    found = re.match(r"HTTP/1\.[01] (\d{3})\b", lines[0]) if sep else None
    if not found:
        raise http.client.BadStatusLine(lines[0][:40])
    status = int(found.group(1))
    if not max_bytes:
        return status, b""
    fields = {k.strip().lower(): v.strip() for k, _, v in (ln.partition(":") for ln in lines[1:])}
    chunked = "chunked" in fields.get("transfer-encoding", "").lower()
    length = fields.get("content-length", "")
    length = int(length) if length.isdigit() and not chunked else None
    body, cap = bytearray(rest), max_bytes + (max_bytes // 8 + 64 if chunked else 0)
    while len(body) < cap:
        if length is not None and len(body) >= length:
            break
        if chunked and (body.startswith(b"0\r\n") or b"\r\n0\r\n" in body):
            break
        got = _recv(sock, deadline)
        if not got:
            break
        body += got
    return status, (_unchunk(bytes(body)) if chunked else bytes(body))[:max_bytes]


def _request(method: str, url: str, body: bytes | None, headers: dict, config: dict,
             seconds: float, max_bytes: int | None) -> tuple[int, bytes]:
    """One request, all of it - name lookup, connect, TLS, send, answer -
    inside `seconds` of wall clock. Raises Refused, _Late or OSError."""
    deadline = time.monotonic() + max(0.05, float(seconds))
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    address = public_address(parts.hostname, port, config, _left(deadline))
    sock = socket.create_connection((address, port), timeout=_left(deadline))
    try:
        if parts.scheme == "https":
            # The handshake treats the timeout as one deadline for all of it.
            sock.settimeout(_left(deadline))
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parts.hostname)
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        lines = [f"{method} {path} HTTP/1.1", f"Host: {parts.netloc.rsplit('@', 1)[-1]}",
                 *(f"{k}: {v}" for k, v in headers.items()), "Connection: close"]
        if body is not None:
            lines.append(f"Content-Length: {len(body)}")
        data = memoryview(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + (body or b""))
        while data:
            sock.settimeout(_left(deadline))
            try:
                data = data[sock.send(data):]
            except (socket.timeout, TimeoutError):
                raise _Late() from None
        return _answer(sock, deadline, max_bytes)
    finally:
        sock.close()


def _why(why: BaseException, seconds: float) -> str:
    if isinstance(why, (_Late, socket.timeout, TimeoutError)):
        return f"timed out after {seconds:g} s"
    return str(why) if isinstance(why, Refused) else type(why).__name__


SLACK_HOST = "hooks.slack.com"


def is_slack(url: str) -> bool:
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".") == SLACK_HOST
    except ValueError:
        return False


def text_of(body: dict) -> str:
    """One plain line for a body without `text` (a conversion)."""
    if body.get("text"):
        return str(body["text"])
    words = [f"[{body.get('site') or '?'}] {body.get('event') or 'event'}"]
    if body.get("action"):
        words.append(f"{body['action']} ({body.get('stage') or '?'})")
    if body.get("source_type"):
        words.append(f"from {body['source_type']}")
    if body.get("landing"):
        words.append(f"landed on {body['landing']}")
    return " ".join(words) + (" (test)" if body.get("test") else "")


def wire(url: str, body: str) -> bytes:
    """The bytes sent to `url`: Slack's {"text"} shape for a Slack incoming
    webhook, the queued body for everything else."""
    if not is_slack(url):
        return body.encode()
    try:
        got = json.loads(body)
    except ValueError:
        got = {}
    return json.dumps({"text": text_of(got if isinstance(got, dict) else {})[:3000]},
                      separators=(",", ":")).encode()


def post(url: str, body: bytes, secret: str, config: dict, now: float,
         seconds: float | None = None) -> tuple[int, str | None]:
    """(HTTP status or 0, error words or None). Never follows a redirect.
    The whole delivery has DEADLINE seconds of wall clock (less when the
    run's budget has less left)."""
    seconds = DEADLINE if seconds is None else min(DEADLINE, seconds)
    headers = {"Content-Type": "application/json", "User-Agent": AGENT,
               HEADER: sign_timed(body, secret, now)}
    try:
        status, _ = _request("POST", url, body, headers, config, seconds, None)
    except (Refused, _Late, OSError, ValueError, http.client.HTTPException) as why:
        return 0, _why(why, seconds)
    if 200 <= status < 300:
        return status, None
    return status, ("a redirect, not followed" if 300 <= status < 400 else f"HTTP {status}")


def get(url: str, config: dict, max_bytes: int = 65536,
        seconds: float = 10.0) -> tuple[int, bytes, str | None]:
    """(HTTP status or 0, at most max_bytes of the body, error words or
    None): a GET with the same guards as a delivery - https only (unless
    allow_private_urls), public addresses only, no redirect followed, one
    wall-clock deadline. Used to read a site's page (site verification)."""
    try:
        url = check_url(url, config)
        status, body = _request("GET", url, None, {"User-Agent": AGENT, "Accept": "text/html"},
                                config, seconds, max(1, int(max_bytes)))
    except (Refused, _Late, OSError, ValueError, http.client.HTTPException) as why:
        return 0, b"", _why(why, seconds)
    if 200 <= status < 300:
        return status, body, None
    return status, b"", ("a redirect, not followed" if 300 <= status < 400 else f"HTTP {status}")


# ------------------------------------------------------------- webhooks

def _cursor_key(site: str) -> str:
    return f"outbox_cursor:{site}"


def _last_id(db, site: str) -> int:
    return int(db.execute("SELECT COALESCE(MAX(id), 0) FROM conversions WHERE site = ?",
                          (site,)).fetchone()[0])


def _set_cursor(db, site: str, value: int) -> None:
    db.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE "
               "SET value = excluded.value", (_cursor_key(site), str(value)))


def active(db, site: str) -> list[dict]:
    return [dict(r) for r in db.execute("SELECT * FROM webhooks WHERE site = ? AND active = 1 "
                                        "ORDER BY id", (site,))]


def add(db, config: dict, folder: Path, site: str, url, events, by: str = "",
        now: datetime | None = None) -> tuple[dict, str]:
    """A new webhook and its secret (shown once). Refused for a bad URL,
    events, or too many webhooks."""
    url = check_url(url, config)
    events = check_events(events)
    with store.tx(db):
        if len(active(db, site)) >= MAX_HOOKS:
            raise Refused(f"At most {MAX_HOOKS} outgoing webhooks for a site.")
        if not active(db, site):          # nothing was being sent: start from now
            _set_cursor(db, site, _last_id(db, site))
        wid = db.execute("INSERT INTO webhooks (site, url, events, created_at, created_by) "
                         "VALUES (?, ?, ?, ?, ?)", (site, url, ",".join(events),
                                                    store.stamp(_now(now)), by or None)
                         ).lastrowid
    secret = rotate(config, folder, site, wid)
    return webhook(db, site, wid), secret


def webhook(db, site: str, wid) -> dict | None:
    row = db.execute("SELECT * FROM webhooks WHERE site = ? AND id = ? AND active = 1",
                     (site, wid)).fetchone()
    if row is None:
        return None
    out = dict(row)
    out["events"] = [e for e in out["events"].split(",") if e]
    return out


def rotate(config: dict, folder: Path, site: str, wid: int) -> str:
    """A new secret for the webhook, kept 0600; the old one stops at once."""
    value = secrets_store.make().replace("skh_", "skw_", 1)
    secrets_store.put(secrets_store.path_for(config, folder), secret_key(site, wid), value)
    return value


def remove(db, config: dict, folder: Path, site: str, wid) -> bool:
    """Stop a webhook: its pending rows and its secret go; its log stays
    until the rows are 90 days old."""
    with store.tx(db):
        gone = db.execute("UPDATE webhooks SET active = 0 WHERE site = ? AND id = ? AND "
                          "active = 1", (site, wid)).rowcount
        if gone:                        # only this site's own webhook, never another's rows
            db.execute("UPDATE outbox SET state = 'failed', error = 'webhook removed' "
                       "WHERE webhook_id = ? AND site = ? AND state = 'pending'", (wid, site))
    if gone:
        try:
            secrets_store.delete(secrets_store.path_for(config, folder), [secret_key(site, wid)])
        except secrets_store.Exposed:
            pass
    return bool(gone)


def log(db, wid: int, limit: int = LOG_ROWS) -> list[dict]:
    """The webhook's last deliveries, newest first, without their bodies."""
    return [dict(r) for r in db.execute(
        "SELECT id, event, ref, state, attempts, http_status, error, created_at, sent_at, "
        "next_at FROM outbox WHERE webhook_id = ? ORDER BY id DESC LIMIT ?", (wid, limit))]


def listing(db, site: str) -> list[dict]:
    return [{**webhook(db, site, w["id"]), "deliveries": log(db, w["id"])}
            for w in active(db, site)]


# --------------------------------------------------------------- enqueue

def _journey(db, site: str, vid: str | None, at: str) -> list[dict]:
    if not vid:
        return []
    rows = db.execute("SELECT at, path, source_type FROM journeys WHERE site = ? AND vid = ? "
                      "AND at <= ? ORDER BY at DESC LIMIT ?", (site, vid, at, JOURNEY_MAX))
    return [dict(r) for r in reversed(rows.fetchall())]


def _seconds(first: str | None, at: str | None) -> int | None:
    try:
        got = int((store.parse(at) - store.parse(first)).total_seconds())
    except (TypeError, ValueError):
        return None
    return got if got >= 0 else None


def body_for(db, row: dict, event: str) -> dict:
    """The summary sent for one conversion row: never a name or an email."""
    return {"event": event, "id": secrets.token_hex(12), "site": row["site"],
            "action": row["action"], "stage": row["stage"], "at": row["at"],
            "tool": row["tool"], "external_ref": row["external_ref"], "vid": row["vid"],
            "source_type": row["source_type"], "first_source": row["first_source"],
            "campaign": row["campaign"], "landing": row["landing"], "country": row["country"],
            "device": row["device"], "visits_before": row["visits_before"],
            "seconds_to_convert": _seconds(row["first_touch_at"], row["at"]),
            "journey": _journey(db, row["site"], row["vid"], row["at"])}


def _queue(db, hook: dict, event: str, ref: str, body: dict, now: datetime) -> int:
    if event not in hook["events"]:
        return 0
    stamp = store.stamp(now)
    return db.execute("INSERT OR IGNORE INTO outbox (webhook_id, site, event, ref, body, "
                      "created_at, next_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (hook["id"], hook["site"], event, ref,
                       json.dumps({**body, "id": secrets.token_hex(12)},
                                  separators=(",", ":")), stamp, stamp)).rowcount


def enqueue(db, config: dict, site: str, now: datetime | None = None) -> int:
    """New conversions and newly abandoned starts as outbox rows. Count."""
    from .from_beacon import abandon_hours
    now = _now(now)
    hooks = [webhook(db, site, w["id"]) for w in active(db, site)]
    if not hooks:
        return 0
    added = 0
    with store.tx(db):
        row = db.execute("SELECT value FROM meta WHERE key = ?", (_cursor_key(site),)).fetchone()
        if row is None:
            _set_cursor(db, site, _last_id(db, site))
            cursor = _last_id(db, site)
        else:
            cursor = int(row[0])
        rows = [dict(r) for r in db.execute("SELECT * FROM conversions WHERE site = ? AND "
                                            "id > ? ORDER BY id LIMIT 1000", (site, cursor))]
        for r in rows:
            event = STAGE_EVENT.get(r["stage"])
            if event:
                body = body_for(db, r, event)
                added += sum(_queue(db, h, event, f"c{r['id']}", body, now) for h in hooks)
            cursor = r["id"]
        _set_cursor(db, site, cursor)
        hours = abandon_hours(config)
        for h in hooks:
            if "conversion.abandoned" not in h["events"]:
                continue
            since = max(h["created_at"], store.stamp(now - timedelta(hours=hours, days=2)))
            for r in store.abandoned(db, site, since, store.stamp(now), hours,
                                     store.stamp(now)):
                r.pop("email", None)
                added += _queue(db, h, "conversion.abandoned", f"c{r['id']}",
                                body_for(db, r, "conversion.abandoned"), now)
    return added


def notify(config: dict, folder: Path, site: str, event: str, ref: str, body: dict,
           now: datetime | None = None) -> int:
    """Queue one event that is not a conversion (alerts_ai: ai.reading_changed)
    for every webhook of the site that wants it, once per `ref`. Rows queued;
    0 without a conversions file or a webhook. Delivered by the next pass."""
    if event not in EVENTS:
        raise Refused(f"Unknown event: {event}")
    path = store.path_for(config, folder)
    if path is None or not Path(path).exists():
        return 0
    db = store.connect(path)
    try:
        hooks = [webhook(db, site, w["id"]) for w in active(db, site)]
        if not hooks:
            return 0
        now = _now(now)
        with store.tx(db):
            return sum(_queue(db, h, event, str(ref)[:100], {**body, "event": event, "site": site},
                              now) for h in hooks)
    finally:
        db.close()


# ---------------------------------------------------------------- deliver

def _secret(config: dict, folder: Path, site: str, wid: int) -> str | None:
    try:
        return secrets_store.load(secrets_store.path_for(config, folder)).get(
            secret_key(site, wid)) or None
    except secrets_store.Exposed:
        return None


def deliver(db, config: dict, folder: Path, row: dict, url: str, now: datetime,
            seconds: float | None = None) -> dict:
    """Send one outbox row now (at most `seconds`, DEADLINE when None) and
    keep its outcome. The row's new state."""
    secret = _secret(config, folder, row["site"], row["webhook_id"])
    if secret is None:
        status, error = 0, "no secret for this webhook (secrets.json)"
    else:
        status, error = post(url, wire(url, row["body"]), secret, config, now.timestamp(),
                             seconds=seconds)
    attempts = row["attempts"] + 1
    if error is None:
        state, next_at, sent = "sent", store.stamp(now), store.stamp(now)
    elif attempts >= MAX_ATTEMPTS:
        state, next_at, sent = "failed", store.stamp(now), None
    else:
        state, sent = "pending", None
        next_at = store.stamp(now + timedelta(seconds=BACKOFF[attempts - 1]))
    db.execute("UPDATE outbox SET attempts = ?, state = ?, next_at = ?, http_status = ?, "
               "error = ?, sent_at = ? WHERE id = ?",
               (attempts, state, next_at, status or None, error and str(error)[:200], sent,
                row["id"]))
    return {"id": row["id"], "state": state, "http_status": status or None, "error": error,
            "attempts": attempts}


def _claim(db, row: dict, now: datetime) -> bool:
    """Hold a due row for this run, so a second run does not send it too."""
    return db.execute("UPDATE outbox SET next_at = ? WHERE id = ? AND state = 'pending' AND "
                      "next_at = ?", (store.stamp(now + timedelta(seconds=LEASE)), row["id"],
                                      row["next_at"])).rowcount == 1


def _deliver_rows(db, configs: dict, folder: Path, now: datetime, limit: int,
                  budget: float | None) -> dict:
    """Due rows of the sites in `configs` ({site: its config}), oldest
    first, until `limit` rows or `budget` seconds (RUN_BUDGET when None) are
    spent. A row not reached is not held: the next run sends it."""
    end = time.monotonic() + (RUN_BUDGET if budget is None else budget)
    got = {"sent": 0, "retry": 0, "failed": 0, "waiting": 0}
    sites = sorted(configs)
    if not sites:
        return got
    due = [dict(r) for r in db.execute(
        "SELECT o.*, w.url AS url FROM outbox o JOIN webhooks w ON w.id = o.webhook_id "
        f"WHERE o.site IN ({','.join('?' * len(sites))}) AND o.state = 'pending' AND "
        "w.active = 1 AND w.site = o.site AND o.next_at <= ? ORDER BY o.next_at, o.id LIMIT ?",
        (*sites, store.stamp(now), limit))]
    for n, row in enumerate(due):
        left = end - time.monotonic()
        if left < 0.05:                 # the run's time is spent: the rest wait
            got["waiting"] = len(due) - n
            break
        if not _claim(db, row, now):
            continue
        done = deliver(db, configs[row["site"]], folder, row, row["url"], now,
                       seconds=min(DEADLINE, left))
        got[{"sent": "sent", "pending": "retry", "failed": "failed"}[done["state"]]] += 1
    return got


def deliver_due(db, config: dict, folder: Path, site: str, now: datetime | None = None,
                limit: int = 20, budget: float | None = None) -> dict:
    return _deliver_rows(db, {site: config}, folder, _now(now), limit, budget)


def deliver_pass(configs: dict, folder: Path, now: datetime | None = None,
                 budget: float | None = None, limit: int = 50) -> dict:
    """The one delivery pass after every site's live or daily step
    (jobs.deliver): {site: its config} sharing one conversions file, at
    most `budget` seconds for all of them. Counts; {"error": ...} instead
    of raising."""
    out = {"sent": 0, "retry": 0, "failed": 0, "waiting": 0}
    try:
        if not configs:
            return out
        path = store.path_for(next(iter(configs.values())), folder)
        if path is None or not Path(path).exists():
            return out
        db = store.connect(path)
        try:
            out.update(_deliver_rows(db, configs, folder, _now(now), limit, budget))
        finally:
            db.close()
    except Exception as why:            # noqa: BLE001 - a job beside the run, never its end
        out["error"] = f"{type(why).__name__}: {str(why)[:200]}"
    return out


def test(db, config: dict, folder: Path, site: str, wid, now: datetime | None = None) -> dict:
    """Queue a signed sample (marked "test": true) for one webhook and try
    it now. Its outcome, or None when there is no such webhook."""
    now = _now(now)
    hook = webhook(db, site, wid)
    if hook is None:
        return None
    sample = {"event": "conversion.completed", "id": secrets.token_hex(12), "test": True,
              "site": site, "action": "demo", "stage": "completed", "at": store.stamp(now),
              "tool": "site", "external_ref": "skald-test", "vid": None, "source_type": "Search",
              "first_source": "Search", "campaign": None, "landing": "/", "country": None,
              "device": "Desktop", "visits_before": 1, "seconds_to_convert": 3600,
              "journey": [{"at": store.stamp(now - timedelta(hours=1)), "path": "/",
                           "source_type": "Search"}]}
    with store.tx(db):
        oid = db.execute("INSERT INTO outbox (webhook_id, site, event, ref, body, created_at, "
                         "next_at, attempts) VALUES (?, ?, 'conversion.completed', ?, ?, ?, ?, "
                         "?)", (hook["id"], site, f"test:{sample['id']}",
                                json.dumps(sample, separators=(",", ":")), store.stamp(now),
                                store.stamp(now), MAX_ATTEMPTS - 1)).lastrowid
    row = dict(db.execute("SELECT * FROM outbox WHERE id = ?", (oid,)).fetchone())
    return deliver(db, config, folder, row, hook["url"], now)


# -------------------------------------------------------------------- run

def prune(db, now: datetime | None = None, keep_days: int = KEEP_DAYS, spare=None) -> int:
    """Outbox rows older than keep_days, but none of a site `spare` names
    (keep_everything)."""
    edge = store.stamp(_now(now) - timedelta(days=keep_days))
    kept = [s for (s,) in db.execute("SELECT DISTINCT site FROM outbox").fetchall()
            if spare is not None and spare(s)]
    marks = f" AND site NOT IN ({','.join('?' * len(kept))})" if kept else ""
    return db.execute("DELETE FROM outbox WHERE created_at < ?" + marks,
                      (edge, *kept)).rowcount


def run(config: dict, folder: Path, site: str, now: datetime | None = None,
        limit: int = 20, deliver: bool = True) -> dict:
    """Enqueue, deliver what is due (within RUN_BUDGET), prune. The live and
    daily runs pass deliver=False: they queue per site, and jobs.deliver
    sends once after every site. Counts; {"error": ...} instead of raising."""
    out = {"queued": 0, "sent": 0, "retry": 0, "failed": 0, "pruned": 0}
    try:
        path = store.path_for(config, folder)
        if path is None or not Path(path).exists():
            return out
        db = store.connect(path)
        try:
            if not active(db, site):
                return out
            now = _now(now)
            out["queued"] = enqueue(db, config, site, now)
            if deliver:
                out.update(deliver_due(db, config, folder, site, now, limit))
            from ..keep_everything import Keeper
            out["pruned"] = prune(db, now, spare=Keeper(config))
        finally:
            db.close()
    except Exception as why:            # noqa: BLE001 - a job beside the run, never its end
        out["error"] = f"{type(why).__name__}: {str(why)[:200]}"
    return out
