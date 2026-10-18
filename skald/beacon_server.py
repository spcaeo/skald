"""The in-page event beacon: a tiny public helper behind nginx.

The website's pages post one small JSON body per event to their own server,
`POST /traffic-beacon` (navigator.sendBeacon; no cookie, no third party).
nginx forwards that one path here, to 127.0.0.1 only, with the caller's
address in X-Real-IP. beacon.py says what a body may contain; this file
decides whether to take it:

  * POST /traffic-beacon only; anything else 404 / 405
  * Origin must be one of the site's own (--origin / beacon.origins), and
    Sec-Fetch-Site, when the browser sends it, "same-origin": 403 otherwise,
    including no Origin at all
  * a body of at most 1 KB (413), that beacon.validate accepts (400)
  * at most `beacon.per_minute` events per address per minute (burst of
    `beacon.burst`), and `beacon.site_per_second` for everyone together: 429
  * Do Not Track or Global Privacy Control: 202, nothing kept
  * a user agent the classifier does not file under people: 202, nothing
    kept (bots do not click). Our own addresses' events are kept marked
    "ours", like our own requests in the log, and never added to people
  * page_view when neither beacon-only mode nor visitor IDs are on: 202,
    nothing kept (skald.js always sends it)
  * the visitor ID `v` is kept only with `beacon.visitor_ids: true`; then
    people's events with one also go to conversions.sqlite (journeys and
    conversions, conversions/from_beacon.py), with the country from the
    address and the device from the user agent, both then dropped

With no allowed origin (no --origin, no beacon.origins) the helper runs for the
signed tool hooks only: /traffic-beacon and /traffic-js/skald.js answer 404, so
a site cannot send events until its own origin is named. The Docker image always
starts it this way or with origins, so incoming hooks never depend on the beacon.

GET /traffic-js/skald.js serves the snippet (webapp/snippet/skald.js) with
an ETag and a day's cache; with visitor IDs off it is served with IDS=0, so
browsers make no ID at all.

204 means "counted" and nothing else does, so nginx's own record of the
answers (the beacon log) is an independent count of what the spool holds;
the audit compares the two.

The address is used for the rate limit, in memory, and to tell our own
traffic apart; it is never written. Counters of what was refused are kept
per day beside the spool (stats-<day>.json) and shown on the dashboard.

Run:  python3 -m skald.beacon_server --config /etc/skald/config.yml
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import beacon
from .config import load_config, setting
from .files import write_atomic

PATH = "/traffic-beacon"
SNIPPET_PATH = "/traffic-js/skald.js"
SNIPPET_FILE = Path(__file__).resolve().parent / "webapp" / "snippet" / "skald.js"
SNIPPET_CACHE = "public, max-age=86400, stale-while-revalidate=604800"
RELOAD_SECONDS = 60       # the classifier re-reads our own addresses this often
FLUSH_SECONDS = 5         # counters are written at most this often


class Bucket:
    """A token bucket: `rate` tokens a second, at most `burst` saved up."""

    __slots__ = ("tokens", "at")

    def __init__(self, burst: float, now: float) -> None:
        self.tokens, self.at = burst, now

    def take(self, rate: float, burst: float, now: float) -> bool:
        self.tokens = min(burst, self.tokens + (now - self.at) * rate)
        self.at = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class Limiter:
    """Per-address and site-wide limits, in memory only."""

    def __init__(self, per_minute: float = 60, burst: float = 20,
                 site_per_second: float = 20, clock=time.monotonic) -> None:
        self.rate, self.burst = per_minute / 60.0, burst
        self.site_rate, self.site_burst = site_per_second, site_per_second * 5
        self.clock = clock
        self.lock = threading.Lock()
        self.buckets: dict[str, Bucket] = {}
        self.site = Bucket(self.site_burst, clock())
        self.swept = clock()

    def allow(self, address: str) -> bool:
        now = self.clock()
        with self.lock:
            if now - self.swept > 300:
                # A full bucket is the same as no bucket: forget it.
                self.buckets = {a: b for a, b in self.buckets.items()
                                if b.tokens + (now - b.at) * self.rate < self.burst}
                self.swept = now
            bucket = self.buckets.get(address)
            if bucket is None:
                bucket = self.buckets[address] = Bucket(self.burst, now)
            if not bucket.take(self.rate, self.burst, now):
                return False
            return self.site.take(self.site_rate, self.site_burst, now)


class Sink:
    """Writes accepted events to the day's spool and keeps the counters."""

    def __init__(self, config: dict, spool: Path, clock=time.time) -> None:
        self.spool, self.clock = Path(spool), clock
        self.lock = threading.Lock()
        self.day = None
        self.stats: dict = {}
        self.flushed = 0.0
        self.accepts = beacon.EVENTS + (beacon.PAGE_VIEW,)
        self.config_path = None           # set by main (hooks and conversions.sqlite)
        self.reconfigure(config)

    def reconfigure(self, config: dict) -> None:
        """Take a site's (new) settings: visitor IDs, events, hosts, zone."""
        from .config import site_name
        from .window import zone
        self.config = config
        self.name = site_name(config)
        self.tz = zone(config)
        self.events = beacon.allowed_events(config)
        self.visitor_ids = beacon.visitor_ids(config)
        self.hosts = beacon.own_hosts(config)
        self._snippet = None
        self._classifier = None
        self._built = 0.0

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), tz=timezone.utc).astimezone(self.tz)

    def classifier(self):
        from .classify import Classifier
        if self._classifier is None or self.clock() - self._built > RELOAD_SECONDS:
            self._classifier = Classifier.from_config(self.config)
            self._built = self.clock()
        return self._classifier

    def group(self, address: str, agent: str, path: str, when: datetime) -> str:
        """"people", "ours" or "bot", by the same rules as the log's lines."""
        from .classify import Group
        from .parse import Hit
        host = next(iter(sorted(self.hosts)), "")
        hit = Hit(when=when, address=address, host=host, method="GET", url=path,
                  status="200", referrer="", user_agent=agent)
        verdict = self.classifier()(hit)
        if verdict.group is Group.PEOPLE:
            return "people"
        if verdict.group is Group.OURS:
            return "ours"
        return "bot"

    def count(self, what: str) -> None:
        with self.lock:
            self._roll(self.now())
            self.stats[what] = self.stats.get(what, 0) + 1
            self._flush(False)

    def keep(self, event: dict, group: str, address: str = "", agent: str = "") -> None:
        when = self.now()
        if not self.visitor_ids:
            event.pop("v", None)
        source, ai = beacon.source_of(event["r"], event["u"], self.hosts)
        line = beacon.line_for(event, when, group, source, ai)
        with self.lock:
            self._roll(when)
            self.spool.mkdir(parents=True, exist_ok=True)
            with open(beacon.day_file(self.spool, when.date()), "a", encoding="utf-8") as out:
                out.write(line + "\n")
            key = "accepted_ours" if group == "ours" else "accepted"
            self.stats[key] = self.stats.get(key, 0) + 1
            if event.get("v") and group == "people":
                self._conversion(event, when, source, address, agent)
            self._flush(False)

    def _conversion(self, event: dict, when: datetime, source: str, address: str,
                    agent: str) -> None:
        """Journeys and conversions for an event with a visitor ID. Inside
        the lock: the store sees events in the spool's order. A failure is
        counted, never raised: the spool line stands, and the second count
        then withholds the day."""
        from .config import site_name
        from .conversions import from_beacon, geo, store
        from .conversions.hooks import history_folder
        try:
            db = store.connect(store.path_for(
                self.config, history_folder(self.config, self.config_path)))
            try:
                from_beacon.record(db, site_name(self.config), event, when, source, self.hosts,
                                   geo.database(self.config),
                                   address, agent)
            finally:
                db.close()
        except Exception as why:          # noqa: BLE001 - a beacon never fails on this
            self.stats["conversion_errors"] = self.stats.get("conversion_errors", 0) + 1
            sys.stderr.write(f"beacon: conversion not kept: {type(why).__name__}\n")

    def unverified(self) -> bool:
        """The site waits for its domain to be verified (site_verify.py)."""
        from .config import site_name
        from .conversions.hooks import history_folder
        from .site_verify import refuses
        return refuses(self.config, history_folder(self.config, self.config_path),
                       site_name(self.config))

    def snippet(self) -> tuple[bytes, str]:
        """(skald.js as served, its ETag). IDS=0 when visitor IDs are off."""
        if self._snippet is None:
            import hashlib
            raw = SNIPPET_FILE.read_bytes()
            if not self.visitor_ids:
                raw = raw.replace(b"IDS=1", b"IDS=0")
            self._snippet = (raw, '"' + hashlib.sha256(raw).hexdigest()[:20] + '"')
        return self._snippet

    def _roll(self, when: datetime) -> None:
        if self.day != when.date():
            if self.day is not None:
                self._flush(True)
            self.day = when.date()
            self.stats = beacon.read_stats(self.spool, self.day) or {}

    def _flush(self, force: bool) -> None:
        if self.day is None or (not force and self.clock() - self.flushed < FLUSH_SECONDS):
            return
        self.flushed = self.clock()
        body = {"day": self.day.isoformat(), **self.stats,
                "updated_at": self.now().isoformat(timespec="seconds")}
        try:
            write_atomic(beacon.stats_file(self.spool, self.day),
                         json.dumps(body, sort_keys=True) + "\n")
        except OSError as why:
            sys.stderr.write(f"beacon: counters not written: {why}\n")

    def close(self) -> None:
        with self.lock:
            self._flush(True)


class Sites:
    """Every site this helper takes events for: one Sink each, found by the
    event's Origin, and for skald.js by the page that loads it (Referer).

    The first site takes the origins it is given (--origin, beacon.origins).
    A site added from the dashboard takes https://<each of its hosts>, but
    only while the install has the script tag on (the first site has an
    origin): its pages post to its own spool, sites/<name>/beacon, where its
    daily run reads them. Its settings rows (visitor IDs, goals) are read
    again every RELOAD_SECONDS, and so is the list of sites."""

    def __init__(self, main: Sink, origins, config: dict | None = None,
                 config_path=None, clock=time.time) -> None:
        self.main, self.origins = main, {o for o in (origins or []) if o}
        self.config, self.config_path, self.clock = config, config_path, clock
        self.lock = threading.Lock()
        self.others: dict[str, Sink] = {}
        self.by_origin: dict[str, Sink] = {o: main for o in self.origins}
        self.built = None

    def __bool__(self) -> bool:
        return bool(self.origins)

    def all(self) -> list[Sink]:
        return [self.main, *self.others.values()]

    def refresh(self) -> None:
        if self.config is None or not self.origins:
            return
        if self.built is not None and self.clock() - self.built < RELOAD_SECONDS:
            return
        with self.lock:
            if self.built is not None and self.clock() - self.built < RELOAD_SECONDS:
                return
            self.built = self.clock()
            try:
                self._load()
            except Exception as why:      # noqa: BLE001 - keep serving the sites known
                sys.stderr.write(f"beacon: sites not reloaded: {type(why).__name__}: {why}\n")

    def _load(self) -> None:
        from . import settings_store
        from .config import site_name
        from .multisite import history_folder, site_configs, state_dir
        folder = history_folder(self.config, Path(self.config_path))
        main = settings_store.apply(self.config, self.main.name)
        if main is not self.config:
            self.main.reconfigure({**main, "_resolved": self.config.get("_resolved", {})})
        others, by_origin = {}, {o: self.main for o in self.origins}
        for c in site_configs(self.config, Path(self.config_path)):
            name = site_name(c)
            c = settings_store.apply(c, name)
            sink = self.others.get(name)
            if sink is None:
                sink = Sink(c, beacon.spool_dir(c, None, state_dir(folder, name)), self.clock)
                sink.config_path = self.config_path
            else:
                sink.reconfigure(c)
            others[name] = sink
            for host in sorted(sink.hosts):
                by_origin.setdefault(f"https://{host}", sink)
        self.others, self.by_origin = others, by_origin

    def for_origin(self, origin: str | None) -> Sink | None:
        self.refresh()
        return self.by_origin.get(origin or "")

    def for_page(self, referrer: str | None) -> Sink:
        """The site whose page loads skald.js, by its Referer; the first site
        when it is not one of ours (or none was sent)."""
        from urllib.parse import urlsplit
        self.refresh()
        try:
            parts = urlsplit(referrer or "")
        except ValueError:
            return self.main
        got = self.by_origin.get(f"{parts.scheme}://{(parts.hostname or '').lower()}")
        return got or self.main

    def close(self) -> None:
        for sink in self.all():
            sink.close()


def same_site(headers, allowed: set[str]) -> bool:
    origin = headers.get("Origin")
    if not origin or origin not in allowed:
        return False
    site = headers.get("Sec-Fetch-Site")
    return site is None or site == "same-origin"


def declined(headers) -> bool:
    """Do Not Track or Global Privacy Control: keep nothing."""
    return headers.get("DNT") == "1" or headers.get("Sec-GPC") == "1"


def make_handler(sink, limiter: Limiter, allowed: set[str] | None = None):
    """`sink` is a Sites, or one Sink with its `allowed` origins."""
    sites = sink if isinstance(sink, Sites) else Sites(sink, allowed)
    main = sites.main

    class Handler(BaseHTTPRequestHandler):
        server_version = "skald-beacon"
        timeout = 5

        site = None             # the Sink this request is for (beacon posts)

        def _send(self, code: int) -> None:
            self.send_response(code)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            if self.site is not None:
                # nginx logs it beside the status: each site's 204s, counted
                # apart from its spool (events.audit).
                self.send_header("X-Skald-Site", self.site.name)
            self.end_headers()

        def _refuse(self, code: int, reason: str) -> None:
            (self.site or main).count("refused_" + reason)
            self._send(code)

        def do_POST(self):
            self.site = None
            if self.path.startswith("/traffic-hooks/"):    # signed tool hooks
                from .conversions.hooks import handle
                return handle(self, main.config, None, getattr(main, "config_path", None))
            if self.path.split("?", 1)[0] != PATH or not sites:   # no origin: hooks only
                return self._send(404)
            sink = sites.for_origin(self.headers.get("Origin"))
            if sink is None:
                return self._refuse(403, "origin")
            self.site = sink
            if sink.unverified():                      # site_verify.py: collects nothing yet
                return self._refuse(403, "unverified")
            if not same_site(self.headers, {self.headers.get("Origin")}):
                return self._refuse(403, "origin")
            try:
                length = int(self.headers.get("Content-Length") or -1)
            except ValueError:
                length = -1
            if length < 0:
                return self._refuse(411, "body")
            if length > beacon.MAX_BODY:
                return self._refuse(413, "body")
            raw = self.rfile.read(length)
            peer = self.client_address[0]
            address = (self.headers.get("X-Real-IP") or "").strip() \
                if peer == "127.0.0.1" else ""
            address = address or peer
            if not limiter.allow(address):
                return self._refuse(429, "rate")
            if declined(self.headers):
                sink.count("declined")
                return self._send(202)
            try:
                event = beacon.validate(raw, sink.accepts)
            except beacon.Refused as why:
                return self._refuse(400, why.reason)
            if event["e"] not in sink.events:     # page_view, not counted here
                sink.count("page_view_off")
                return self._send(202)
            agent = self.headers.get("User-Agent") or ""
            group = sink.group(address, agent, event["p"], sink.now())
            if group == "bot":
                sink.count("not_people")
                return self._send(202)
            sink.keep(event, group, address, agent)
            return self._send(204)

        def do_GET(self):
            self.site = None
            if self.path.split("?", 1)[0] == SNIPPET_PATH and sites:
                return self._snippet(self.command == "GET")
            if self.path.startswith("/traffic-js/"):
                return self._send(404)
            self._send(405)

        def do_HEAD(self):
            self.do_GET()

        def _snippet(self, with_body: bool) -> None:
            sink = sites.for_page(self.headers.get("Referer"))
            try:
                raw, tag = sink.snippet()
            except OSError:
                return self._send(404)
            fresh = tag in [t.strip() for t in
                            (self.headers.get("If-None-Match") or "").split(",")]
            self.send_response(304 if fresh else 200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Cache-Control", SNIPPET_CACHE)
            self.send_header("ETag", tag)
            self.send_header("Vary", "Referer")       # visitor IDs on or off, per site
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", "0" if fresh else str(len(raw)))
            self.end_headers()
            if with_body and not fresh:
                self.wfile.write(raw)

        def _not_allowed(self):
            self._send(405)

        do_PUT = do_DELETE = do_PATCH = _not_allowed

        def log_message(self, fmt, *args):  # no visitor details in the journal
            pass

    return Handler



class BeaconServer(ThreadingHTTPServer):
    """A page sends several events at once and hooks arrive in bursts: a
    listen queue of 128, not Python's default 5, so none is dropped."""
    daemon_threads = True
    request_queue_size = 128

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--config", required=True)
    p.add_argument("--port", type=int, default=8766)
    p.add_argument("--origin", action="append", default=[],
                   help="allowed Origin, e.g. https://www.<your site> (repeatable); "
                        "default beacon.origins")
    a = p.parse_args(argv)
    config_path = Path(a.config)
    config = load_config(config_path)
    # The history's file, so state kept beside it (ours.json) is found as the runs find it.
    db = Path(str(setting(config, "history", "db", "history.sqlite"))).expanduser()
    config.setdefault("_resolved", {"history_db": str(
        db if db.is_absolute() else config_path.resolve().parent / db)})
    origins = a.origin or setting(config, "beacon", "origins") or []
    if isinstance(origins, str):
        origins = [origins]
    if not origins:
        print("beacon helper: no allowed origin (--origin / beacon.origins), so signed hooks "
              "only; /traffic-beacon and /traffic-js/skald.js answer 404", file=sys.stderr)
    sink = Sink(config, beacon.spool_dir(config, config_path))
    sink.config_path = config_path        # for /traffic-hooks/ (conversions/hooks.py)
    sites = Sites(sink, origins, config, config_path)
    sites.refresh()
    limiter = Limiter(float(setting(config, "beacon", "per_minute", 60)),
                      float(setting(config, "beacon", "burst", 20)),
                      float(setting(config, "beacon", "site_per_second", 20)))
    server = BeaconServer(("127.0.0.1", a.port), make_handler(sites, limiter))
    # systemd stops with SIGTERM: leave through the finally, counters written.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        server.serve_forever()
    finally:
        sites.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
