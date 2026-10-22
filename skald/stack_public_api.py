"""POST /traffic-hooks/_public/stack-check: the public "Is my site exposed?" check over HTTP
(stack_public.py), on the beacon helper, behind `security.public_check: true` (off by
default: off, the path is an unknown hook and answers as one).

    POST {"url": "https://<a site>/"}   ->  200 the answer (stack_public.answer)
                                              400 {"error": words}  the address is not checked
                                              403 another site's page asked (Origin)
                                              429 a limit, with Retry-After
                                              503 too many checks at once
    POST {"url": ..., "cached_only": true}  ->  the answer of a check made in the last hour,
                                              else 404; never a fetch (a page's "send this
                                              report" reads the findings back from here)
    POST {"quota": true}                ->  200 {"limit", "left", "next_at"}: how many checks
                                              this sender may still run this hour, and when
                                              one more frees up (null when none is used);
                                              not counted (the page's multi-site mode asks
                                              before it starts)

Every 200 answer to a check carries the same three fields, after that check is counted.

Every request, in this order:

  * Origin: when the browser sends one it must be in `security.public_check_origins`
    (403 otherwise); only that origin is answered with CORS headers. OPTIONS (a preflight)
    is answered for it alone.
  * a body of at most MAX_BODY bytes (411 without a length, 413 over it), JSON with "url".
  * per sender, at most `public_check_per_hour` (10) requests an hour, counted whether
    they are answered from the cache or not. The sender is X-Real-IP on the proxy's own
    loopback connection, else the connection's address, as the signed hooks read it.
  * the address's own rules (stack_public.target): 400 in plain words.
  * the cache: each scheme and host's answer is kept CACHE_SECONDS (an hour; a site that
    did not answer, UNREACHED_SECONDS), in memory, at most CACHE_SIZE of them.
  * for a check that fetches, at most `public_check_global_per_hour` (300) an hour in all,
    and at most PARALLEL at once.

Nothing is written: no cookie is set or read, no address or URL is logged or kept. The
counters below are in memory; once an hour one line on stderr gives them as numbers.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import advisories, stack_public

PATH = "/traffic-hooks/_public/stack-check"
MAX_BODY = 2048
PER_HOUR = 10
GLOBAL_PER_HOUR = 300
HOUR = 3600.0
CACHE_SECONDS = 3600.0
UNREACHED_SECONDS = 300.0
CACHE_SIZE = 2000
PARALLEL = 4
PROXIES = ("127.0.0.1", "::1")
COUNTERS = ("checks", "cached", "refused", "limited", "busy", "failed")


def on(config: dict | None) -> bool:
    got = ((config or {}).get("security") or {}).get("public_check")
    return got is True or str(got).strip().lower() in ("1", "true", "yes", "on")


def _int(value, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


class Window:
    """At most `limit` events per key in the last HOUR seconds (sliding), in memory."""

    def __init__(self, limit: int, clock) -> None:
        self.limit, self.clock = limit, clock
        self.seen: dict[str, deque] = {}
        self.swept = clock()

    def allow(self, key: str) -> float:
        """0 when allowed (and counted), else the seconds until one more is."""
        now = self.clock()
        if now - self.swept > 600:
            self.seen = {k: q for k, q in self.seen.items() if q and now - q[-1] < HOUR}
            self.swept = now
        q = self.seen.setdefault(key, deque())
        while q and now - q[0] >= HOUR:
            q.popleft()
        if len(q) >= self.limit:
            return max(1.0, HOUR - (now - q[0]))
        q.append(now)
        return 0.0

    def state(self, key: str) -> tuple[int, float | None]:
        """(how many are still allowed now, seconds until the oldest counted one expires, or
        None when none is counted); counts nothing."""
        now = self.clock()
        q = [t for t in self.seen.get(key, ()) if now - t < HOUR]
        return max(0, self.limit - len(q)), (max(1.0, HOUR - (now - q[0])) if q else None)


class Service:
    """The check's state: its limits, its cache and its counters, for one helper."""

    def __init__(self, config: dict | None = None, clock=time.monotonic, checker=None,
                 now=None) -> None:
        sec = (config or {}).get("security") or {}
        origins = sec.get("public_check_origins") or []
        origins = [origins] if isinstance(origins, str) else origins
        self.origins = {str(o).strip().rstrip("/") for o in origins if str(o).strip()}
        self.config, self.clock = config or {}, clock
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.checker = checker or self._check
        self.lock = threading.Lock()
        self.senders = Window(_int(sec.get("public_check_per_hour"), PER_HOUR, 1, 1000), clock)
        self.everyone = Window(_int(sec.get("public_check_global_per_hour"), GLOBAL_PER_HOUR,
                                    1, 100000), clock)
        self.slots = threading.BoundedSemaphore(PARALLEL)
        self.cache: OrderedDict = OrderedDict()
        self.counts = dict.fromkeys(COUNTERS, 0)
        self.since = clock()

    @classmethod
    def from_config(cls, config: dict | None):
        return cls(config) if on(config) else None

    def _check(self, raw) -> dict:
        folder = None
        db = ((self.config.get("_resolved") or {}).get("history_db"))
        if db:
            folder = Path(db).parent
        return stack_public.check(raw, self.config, advisories.load(folder), self.now())

    def count(self, what: str) -> None:
        with self.lock:
            self.counts[what] += 1
            if self.clock() - self.since >= HOUR:
                sys.stderr.write("public stack check, last hour: " + ", ".join(
                    f"{k} {v}" for k, v in self.counts.items()) + "\n")
                self.counts = dict.fromkeys(COUNTERS, 0)
                self.since = self.clock()

    def _cached(self, key: str):
        with self.lock:
            got = self.cache.get(key)
            if got is None:
                return None
            if got[0] <= self.clock():
                del self.cache[key]
                return None
            return got[1]

    def _keep(self, key: str, answer: dict) -> None:
        keep = CACHE_SECONDS if answer.get("reached") else UNREACHED_SECONDS
        with self.lock:
            self.cache[key] = (self.clock() + keep, answer)
            self.cache.move_to_end(key)
            while len(self.cache) > CACHE_SIZE:
                self.cache.popitem(last=False)

    def _retry(self, wait: float) -> dict:
        """When one more is allowed: seconds, and the wall-clock time (UTC, ISO)."""
        at = self.now() + timedelta(seconds=int(wait) + 1)
        return {"retry_in": int(wait) + 1,
                "retry_at": at.astimezone(timezone.utc).isoformat(timespec="seconds")}

    def quota(self, sender: str) -> dict:
        """This sender's checks left this hour, and when one more frees up: never counted."""
        with self.lock:
            left, wait = self.senders.state(sender or "?")
        at = None
        if wait is not None:
            when = self.now() + timedelta(seconds=int(wait) + 1)
            at = when.astimezone(timezone.utc).isoformat(timespec="seconds")
        return {"limit": self.senders.limit, "left": left, "next_at": at}

    @staticmethod
    def _kind(why) -> str:
        """`address`: not a website address at all; `refused`: one the check does not read
        (an IP, an inside name, a name that points inside), its words say which."""
        return "address" if isinstance(why, stack_public.BadAddress) else "refused"

    def run(self, sender: str, raw, cached_only: bool = False) -> tuple[int, dict, dict]:
        """(status, body, extra headers) for one request's "url". `cached_only`: the answer
        of a check made in the last hour, or 404; never a new fetch (a report of findings
        this helper made, never findings someone sends)."""
        with self.lock:
            wait = self.senders.allow(sender or "?")
        if wait:
            self.count("limited")
            return 429, {"kind": "rate", "limit": self.senders.limit, **self._retry(wait),
                         "error": f"You've run {self.senders.limit} checks in the last hour."}, \
                {"Retry-After": str(int(wait))}
        try:
            scheme, host = stack_public.target(raw)
        except stack_public.Refused as why:
            self.count("refused")
            return 400, {"error": str(why), "kind": self._kind(why)}, {}
        key = f"{scheme}://{host}"
        got = self._cached(key)
        if got is not None:
            self.count("cached")
            return 200, {**got, "cached": True, **self.quota(sender)}, {}
        if cached_only:
            return 404, {"error": "Check the site first, then send the report.",
                         "kind": "not_checked"}, {}
        with self.lock:
            wait = self.everyone.allow("all")
        if wait:
            self.count("limited")
            return 429, {"kind": "busy", **self._retry(min(wait, 600)),
                         "error": "Lots of people are checking right now. "
                                  "Please try again in a few minutes."}, \
                {"Retry-After": str(int(min(wait, 600)))}
        if not self.slots.acquire(blocking=False):
            self.count("busy")
            return 503, {"kind": "busy", **self._retry(30),
                         "error": "Lots of people are checking right now. "
                                  "Please try again in a few minutes."}, {"Retry-After": "30"}
        try:
            answer = self.checker(key + "/")
        except stack_public.Refused as why:
            self.count("refused")
            return 400, {"error": str(why), "kind": self._kind(why)}, {}
        except Exception:                       # noqa: BLE001 - never a traceback to a stranger
            self.count("failed")
            return 500, {"kind": "failed", "error": "Our checker failed on this site. That's on "
                                                    "our side, not your site. Try again later."}, {}
        finally:
            self.slots.release()
        self.count("checks")
        self._keep(key, answer)
        return 200, {**answer, "cached": False, **self.quota(sender)}, {}


def sender(handler) -> str:
    """X-Real-IP on the proxy's own loopback connection, else the connection's address."""
    peer = str((getattr(handler, "client_address", None) or ("",))[0] or "")
    if peer in PROXIES:
        got = (handler.headers.get("X-Real-IP") or "").strip()
        if got and len(got) <= 64:
            return got
    return peer


def _send(handler, status: int, body: dict | None, cors: str | None, extra=None) -> None:
    raw = b"" if body is None else json.dumps(body, separators=(",", ":")).encode()
    handler.send_response(status)
    if body is not None:
        handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Robots-Tag", "noindex")
    handler.send_header("Vary", "Origin")
    if cors:
        handler.send_header("Access-Control-Allow-Origin", cors)
    for name, value in (extra or {}).items():
        handler.send_header(name, value)
    handler.send_header("Content-Length", str(len(raw)))
    if status in (411, 413):
        handler.send_header("Connection", "close")
        handler.close_connection = True
    handler.end_headers()
    if raw:
        handler.wfile.write(raw)


def _origin(handler, service: Service) -> tuple[bool, str | None]:
    """(allowed, the origin to answer CORS for)."""
    origin = (handler.headers.get("Origin") or "").strip().rstrip("/")
    if not origin:
        return True, None                       # not a browser on another page
    if origin in service.origins:
        return True, origin
    return False, None


def handle(handler, service: Service) -> None:
    """Answer one POST or OPTIONS to PATH on a BaseHTTPRequestHandler."""
    allowed, cors = _origin(handler, service)
    if not allowed:
        return _send(handler, 403, {"error": "This check answers its own site's page only."}, None)
    if handler.command == "OPTIONS":
        return _send(handler, 204, None, cors, {
            "Access-Control-Allow-Methods": "POST", "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "600"} if cors else None)
    try:
        length = int(handler.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return _send(handler, 411, {"error": "A body is needed."}, cors)
    if length > MAX_BODY:
        return _send(handler, 413, {"error": "That is too long."}, cors)
    try:
        body = json.loads(handler.rfile.read(length).decode("utf-8"))
        raw = body.get("url") if isinstance(body, dict) else None
    except (ValueError, UnicodeDecodeError):
        body, raw = None, None
    if isinstance(body, dict) and body.get("quota") is True and raw is None:
        return _send(handler, 200, service.quota(sender(handler)), cors)
    if not isinstance(raw, str):
        return _send(handler, 400, {"error": stack_public.NOT_AN_ADDRESS, "kind": "address"}, cors)
    status, answer, extra = service.run(sender(handler), raw, body.get("cached_only") is True)
    _send(handler, status, answer, cors, extra)
