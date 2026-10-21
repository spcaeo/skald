"""The hook receiver: POST /traffic-hooks/<site>/<tool>, public, behind nginx.

Each request, in this order, before anything is kept:

  1. the site must be one this install reports on, the tool one of
     conversions.TOOLS with a secret set for that site, and not waiting for
     its domain to be verified (site_verify.py): 404 otherwise
  2. a body of at most 64 KiB: 411 without a length, 413 over it
  3. the tool's signature over the raw bytes, checked BEFORE the body is
     parsed and before any per-hook bucket is spent: 401. A failure spends
     the sender's small pre-auth bucket (`hooks.preauth_per_minute`, burst
     `hooks.preauth_burst`): 429 once it is empty
  4. at most `hooks.per_minute` verified deliveries a minute per site and
     tool (burst `hooks.burst`): 429. An unsigned flood cannot spend it.
  5. the body must be JSON: 400
  5a. Calendly and Cal.com, when the site names its event types
     (hooks.<tool>.event_types, event_types.py): another type is answered
     200 and logged "ignored", with nothing spooled or kept
  6. Cal.com and Typeform sign no timestamp: a body whose hash was accepted
     in the last 30 days is a replay (200, "replay"), never spooled or kept
     again. The hash (table hook_replays) outlives `forget`, so a replay
     cannot bring back a forgotten conversion.
  7. the verified body is appended to the day's spool (spool.py) with only
     the keys its adapter and the audit read (conversions.SPOOL_KEYS); name
     and primary email only when the site's identity is full
  8. the adapter maps it to records, normalise.py makes them rows, the
     store keeps them once per (site, tool, external ref, stage): 200. A
     `lead` or `json` time without an offset is read in the site's time zone;
     the spool line carries that zone and the delivery log says so

Every outcome for a known site and tool is a row in `deliveries` (what
happened, never the body); refusals for the rate limit and failed
signatures are written at most once a minute per hook, as a count. A
request with `X-Skald-Test: 1` (still signed) is checked and mapped, logged
as "test", and neither spooled nor kept; its answer shows what a real one
would keep (no visitor ID when the site's are off, nothing for another event
type).

The sender's address is read only for the pre-auth bucket, kept in memory:
X-Real-IP on the proxy's connection (loopback, or `hooks.trusted_proxies`),
else the connection's own address.

One GET (2.18): /traffic-hooks/<site>/leads, the leads the site's `lead`
hook delivered, read only, signed with that hook's secret over the method
and the request target (reconcile.py). Every other GET is 405 as before.
It writes no delivery row: one line on the helper's log with the site, the
outcome, the row count and the parameter names, never their values.

One more POST (2.19): /traffic-hooks/<site>/leads/test (marks.py), the site
marking its own leads as test or not, signed like the lead POST; one
delivery row (the counts, never a ref) and one audit entry per call.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..beacon import visitor_ids
from ..config import setting, site_name
from . import LEAD_SHAPED, MAX_BODY, TOOLS, event_types, geo, marks, reconcile, spool, store
from .adapters import Invalid, adapter
from .adapters.lead import LABEL_NOTE, TEST_NOTE, verify_get
from .normalise import row as make_row
from .secrets_store import Exposed, find

PREFIX = "/traffic-hooks/"
_PATH = re.compile(r"^/traffic-hooks/([A-Za-z0-9][A-Za-z0-9._-]{0,99})/([a-z]{2,20})/?$")
REFUSED_EVERY = 60
SITES_EVERY = 30          # seconds: a hook for an unknown site re-reads the sites
REPLAY_TOOLS = ("calcom", "typeform")     # no signed timestamp: refused by hash
PROXIES = ("127.0.0.1", "::1")


def without_vid(value):
    """The body with every `vid` key removed, at any depth."""
    if isinstance(value, dict):
        return {k: without_vid(v) for k, v in value.items() if k != "vid"}
    if isinstance(value, list):
        return [without_vid(v) for v in value]
    return value


def replay_digest(tool: str, payload, body: bytes) -> str | None:
    """sha256 of the tool, the event's id and the raw body, for the tools
    that sign no timestamp; None for the others."""
    if tool not in REPLAY_TOOLS or not isinstance(payload, dict):
        return None
    inner = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    event = payload.get("event_id") if tool == "typeform" else \
        f"{payload.get('triggerEvent')}:{inner.get('uid')}"
    return hashlib.sha256(f"{tool}\0{event}\0".encode() + body).hexdigest()


def history_folder(config: dict, config_path=None) -> Path:
    db = Path(str(setting(config, "history", "db", "history.sqlite"))).expanduser()
    if not db.is_absolute() and config_path is not None:
        db = Path(config_path).resolve().parent / db
    return db.parent


def site_configs(config: dict, config_path=None) -> dict[str, dict]:
    """{site name: its (merged) config} for every site of the install: the
    config files' and the dashboard's (accounts.sqlite), loaded as run-daily
    loads them (multisite.site_configs), with or without a `sites:` list."""
    out = {site_name(config): config}
    if config_path is None:
        return out
    from ..multisite import site_configs as others
    moved = ((config or {}).get("hooks") or {}).get("secrets")
    try:
        for got in others(config, Path(config_path)):
            if got.get("_dashboard_site") and moved:
                # A dashboard site inherits no `hooks:`, but its secret is
                # kept in the install's secrets file (Settings > Integrations).
                got = {**got, "hooks": {"secrets": moved}}
            out[site_name(got)] = got
    except SystemExit:
        pass
    return out


def identity_full(site_config: dict, folder=None) -> bool:
    """`conversions.identity` (people/policy.py: full unless the site says
    anonymous, or the install was upgraded to 2.4.0 and nobody turned it on)."""
    from ..people.policy import identity_full as full
    return full(site_config, folder)


class Receiver:
    def __init__(self, config: dict, folder=None, config_path=None, clock=time.time) -> None:
        from ..beacon_server import Limiter
        from ..window import zone
        self.config, self.clock = config, clock
        self.config_path = config_path
        self.folder = Path(folder) if folder is not None else history_folder(config, config_path)
        self.sites, self.hosts, self.sites_at, self.zones = {}, {}, None, {}
        self._load_sites()
        self.tz = zone(config)
        self.db_path = store.path_for(config, self.folder)
        self.spool = spool.spool_dir(config, self.folder)
        self.country_db = geo.database(config)
        self.limiter = Limiter(float(setting(config, "hooks", "per_minute", 60)),
                               float(setting(config, "hooks", "burst", 30)),
                               float(setting(config, "hooks", "all_per_second", 20)),
                               clock=time.monotonic)
        # Unsigned or badly signed attempts, per sender address (never kept).
        self.preauth = Limiter(float(setting(config, "hooks", "preauth_per_minute", 30)),
                               float(setting(config, "hooks", "preauth_burst", 10)),
                               float(setting(config, "hooks", "preauth_all_per_second", 20)),
                               clock=time.monotonic)
        # GET .../leads (reconcile.py), per site, verified requests only.
        self.reads = Limiter(float(setting(config, "hooks", "leads_per_minute", 60)),
                             float(setting(config, "hooks", "leads_burst", 20)),
                             float(setting(config, "hooks", "all_per_second", 20)),
                             clock=time.monotonic)
        self.lock = threading.Lock()
        self.refused: dict[tuple[str, str, str], list] = {}

    # -------------------------------------------------------------- pieces

    def _load_sites(self) -> None:
        from ..beacon import own_hosts
        sites = site_configs(self.config, self.config_path)
        self.sites, self.hosts = sites, {name: own_hosts(c) for name, c in sites.items()}
        self.sites_at = time.monotonic()

    def secret(self, site: str, tool: str) -> str | None:
        """The hook's secret; None when the site or tool is not set up.
        Raises Exposed for a secrets file others can read. A site added
        from the dashboard after the helper started is found by reading
        the sites again, at most once every SITES_EVERY seconds."""
        if tool not in TOOLS:
            return None
        if site not in self.sites and time.monotonic() - self.sites_at >= SITES_EVERY:
            self._load_sites()
        if site not in self.sites:
            return None
        from ..site_verify import refuses           # a site waiting for verification
        if refuses(self.config, self.folder, site):
            return None
        return find(self.sites[site], self.folder, site, tool)[0]

    def _log(self, site: str, tool: str, outcome: str, status: int, error=None,
             ref=None, at=None) -> None:
        db = store.connect(self.db_path)
        try:
            store.log_delivery(db, site, tool, outcome, status, error, ref, at)
        finally:
            db.close()

    def _refused(self, site: str, tool: str, outcome: str = "rate_limited",
                 status: int = 429) -> None:
        """Count a refusal; write one row a minute per hook and outcome,
        with the count, so a flood is never a flood of rows."""
        now = self.clock()
        with self.lock:
            entry = self.refused.setdefault((site, tool, outcome), [0, 0.0])
            entry[0] += 1
            if now - entry[1] < REFUSED_EVERY:
                return
            count, entry[0], entry[1] = entry[0], 0, now
        self._log(site, tool, outcome, status, f"{count} refused")

    def _limited(self, site: str, tool: str) -> None:
        self._refused(site, tool, "rate_limited", 429)

    def client(self, handler) -> str:
        """The sender's address for the pre-auth bucket: X-Real-IP on the
        proxy's own connection, else the connection's address."""
        peer = str((getattr(handler, "client_address", None) or ("",))[0] or "")
        extra = setting(self.config, "hooks", "trusted_proxies") or ()
        extra = [extra] if isinstance(extra, str) else list(extra)
        if peer in PROXIES or peer in [str(p) for p in extra]:
            got = (handler.headers.get("X-Real-IP") or "").strip()
            if got and len(got) <= 64:
                return got
        return peer

    def _replayed(self, site: str, digest: str, now: float) -> bool:
        if not self.db_path.exists():
            return False
        since = store.stamp(datetime.fromtimestamp(now, tz=timezone.utc)
                            - timedelta(days=store.REPLAY_DAYS))
        db = store.connect(self.db_path)
        try:
            return store.replayed(db, site, digest, since)
        finally:
            db.close()

    def uri(self, handler) -> str:
        base = setting(self.config, "hooks", "public_url")
        if base:
            return str(base).rstrip("/") + handler.path
        proto = handler.headers.get("X-Forwarded-Proto") or "https"
        return f"{proto}://{handler.headers.get('Host') or ''}{handler.path}"

    # --------------------------------------------------------------- HTTP

    def http(self, handler) -> tuple[int, dict]:
        """(status, answer) for one request on the handler; reads its body."""
        if handler.command == "GET" and reconcile.site_of(handler.path):
            return self.leads(handler)
        if marks.site_of(handler.path):
            if handler.command != "POST":
                return 405, {"error": "POST only"}
            return self.mark(handler)
        found = _PATH.match(handler.path.split("?", 1)[0])
        if not found:
            return 404, {"error": "not found"}
        site, tool = found.groups()
        if handler.command != "POST":
            return 405, {"error": "POST only"}
        secret = self._secret_or_answer(site, tool)
        if isinstance(secret, tuple):
            return secret
        body = self._body(handler, site, tool)
        if isinstance(body, tuple):
            return body
        headers = {k.lower(): v for k, v in handler.headers.items()}
        headers[":method"], headers[":uri"] = "POST", self.uri(handler)
        # The signature first (cheap): only a verified delivery spends the
        # hook's bucket, so an unsigned flood cannot starve the real tool.
        if not adapter(tool).verify(headers, body, secret, self.clock()):
            self._refused(site, tool, "bad_signature", 401)
            if not self.preauth.allow(self.client(handler)):
                return 429, {"error": "too many"}
            return 401, {"error": "bad signature"}
        if not self.limiter.allow(f"{site}/{tool}"):
            self._limited(site, tool)
            return 429, {"error": "too many"}
        return self.process(site, tool, headers, body, secret, verified=True)

    def _secret_or_answer(self, site: str, tool: str):
        """The hook's secret, or the (status, answer) refusing the request:
        404 not set up, 500 a secrets file others can read."""
        try:
            secret = self.secret(site, tool)
        except Exposed:
            self._log(site, tool, "error", 500, "the secrets file is not 0600")
            return 500, {"error": "not set up"}
        return secret or (404, {"error": "not found"})

    def _body(self, handler, site: str, tool: str):
        """The raw body, or the (status, answer): 411 without a length, 413
        over MAX_BODY."""
        try:
            length = int(handler.headers.get("Content-Length") or -1)
        except ValueError:
            length = -1
        if length < 0:
            self._log(site, tool, "no_length", 411)
            return 411, {"error": "length required"}
        if length > MAX_BODY:
            self._log(site, tool, "too_large", 413, f"{length} bytes")
            return 413, {"error": "body over 64 KiB"}
        return handler.rfile.read(length)

    def mark(self, handler) -> tuple[int, dict]:
        """POST /traffic-hooks/<site>/leads/test (marks.py): the lead hook's
        secret and signature over the raw body, then the site's bucket, then
        the body. One delivery row and one audit entry per answered call."""
        site, tool = marks.site_of(handler.path), marks.TOOL
        secret = self._secret_or_answer(site, tool)
        if isinstance(secret, tuple):
            return secret
        body = self._body(handler, site, tool)
        if isinstance(body, tuple):
            return body
        headers = {k.lower(): v for k, v in handler.headers.items()}
        if not adapter(tool).verify(headers, body, secret, self.clock()):
            self._refused(site, tool, "bad_signature", 401)
            if not self.preauth.allow(self.client(handler)):
                return 429, {"error": "too many"}
            return 401, {"error": "bad signature"}
        if not self.reads.allow(f"{site}/test"):
            self._limited(site, tool)
            return 429, {"error": "too many"}
        try:
            refs, on = marks.read_body(body)
        except marks.BadBody as why:
            self._log(site, tool, "bad_body", 400, f"leads/test: {why}")
            return 400, {"error": str(why)}
        try:
            got = marks.apply(self.db_path, site, refs, on)
        except Exception as why:            # noqa: BLE001 - the sender will ask again
            self._log(site, tool, "error", 500, f"leads/test: {type(why).__name__}")
            return 500, {"error": "nothing changed, send again"}
        marks.recount(self.folder)
        try:
            marks.audit(self.config, self.folder, site, refs, got)
        except Exception as why:            # noqa: BLE001 - the marks stand; say so
            sys.stderr.write(f"hooks: leads/test {site}: the audit entry failed: "
                             f"{type(why).__name__}\n")
        return 200, got

    def leads(self, handler) -> tuple[int, dict]:
        """GET /traffic-hooks/<site>/leads (reconcile.py): 404 not set up,
        401 a missing or wrong signature, 429 too many, 400 a bad query."""
        site = reconcile.site_of(handler.path)
        try:
            secret = self.secret(site, reconcile.TOOL)
        except Exposed:
            self._said(site, "error")
            return 500, {"error": "not set up"}
        if not secret:
            return 404, {"error": "not found"}
        headers = {k.lower(): v for k, v in handler.headers.items()}
        if not verify_get(headers, handler.path, secret, self.clock()):
            self._said(site, "bad_signature")
            if not self.preauth.allow(self.client(handler)):
                return 429, {"error": "too many"}
            return 401, {"error": "bad signature"}
        if not self.reads.allow(site):
            self._said(site, "rate_limited")
            return 429, {"error": "too many"}
        try:
            query = reconcile.read_query(handler.path)
        except reconcile.BadQuery as why:
            self._said(site, "bad_query")
            return 400, {"error": str(why)}
        try:
            got = reconcile.answer(self.db_path, site, query)
        except Exception as why:            # noqa: BLE001 - never a traceback to a caller
            self._said(site, f"error {type(why).__name__}")
            return 500, {"error": "failed, ask again"}
        self._said(site, "ok", len(got["rows"]), query["params"])
        return 200, got

    def _said(self, site: str, outcome: str, rows: int | None = None, params=()) -> None:
        """The helper's log line for a GET .../leads: the site, the outcome, the
        row count and the parameter names. A refusal at most once a minute
        per site and outcome, with its count."""
        count = 1
        if rows is None:
            now = self.clock()
            with self.lock:
                entry = self.refused.setdefault((site, "leads", outcome), [0, 0.0])
                entry[0] += 1
                if now - entry[1] < REFUSED_EVERY:
                    return
                count, entry[0], entry[1] = entry[0], 0, now
        words = f"rows={rows}" if rows is not None else f"count={count}"
        sys.stderr.write(f"hooks: GET leads {site} {outcome} {words}"
                         + (f" params={','.join(params)}" if params else "") + "\n")

    def process(self, site: str, tool: str, headers: dict, body: bytes,
                secret: str, verified: bool = False) -> tuple[int, dict]:
        """Verify (unless `http` just did), spool, map and keep one
        delivery. (status, answer)."""
        mod = adapter(tool)
        now = self.clock()
        received = store.stamp(datetime.fromtimestamp(now, tz=timezone.utc))
        if not verified and not mod.verify(headers, body, secret, now):
            self._refused(site, tool, "bad_signature", 401)
            return 401, {"error": "bad signature"}
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._log(site, tool, "bad_body", 400, "not JSON", at=received)
            return 400, {"error": "not JSON"}
        full = identity_full(self.sites[site], self.folder)
        # Calendly or Cal.com with the site's event types named: another type is
        # answered 200, logged, and nothing else - no spool line, no row.
        keep, skipped = event_types.decide(
            tool, payload, event_types.wanted(self.sites[site], site, tool, self.folder),
            lambda ref: self._booked(site, tool, ref))
        # Visitor IDs off for the site (beacon.visitor_ids): a hook's `vid` is not
        # kept either, in the spool or the store, whatever the sender put in it.
        keep_vid = visitor_ids(self.sites[site])
        tz = self.site_zone(site) if tool in LEAD_SHAPED else None
        if headers.get("x-skald-test") == "1":
            return self._test(site, tool, mod, payload, received, full, keep_vid, skipped, tz)
        if not keep:
            self._log(site, tool, "ignored", 200, skipped, at=received)
            return 200, {"ok": True, "recorded": 0, "duplicates": 0,
                         "outcome": event_types.IGNORED}
        digest = replay_digest(tool, payload, body)
        if digest and self._replayed(site, digest, now):
            self._log(site, tool, "replay", 200, "the same body was taken before",
                      at=received)
            return 200, {"ok": True, "recorded": 0, "duplicates": 1}
        if not keep_vid:
            payload = without_vid(payload)
        records, bad = [], None
        try:
            records = mod.to_records(payload, self.sites[site], **({"tz": tz} if tz else {}))
        except Invalid as why:
            bad = why                       # refused below, after the spool line
        naive = any(r.get("naive_at") for r in records)
        try:
            day = datetime.fromtimestamp(now, tz=timezone.utc).astimezone(self.tz).date()
            spool.append(self.spool, day, spool.line_for(
                received, site, tool, payload, full, str(tz) if naive else None))
        except OSError as why:
            self._log(site, tool, "error", 500, f"spool: {type(why).__name__}", at=received)
            return 500, {"error": "not kept, send again"}
        try:
            if bad is not None:
                raise bad
            rows = [make_row(r, site, tool, received, self.hosts[site], full, self.country_db)
                    for r in records]
            if not keep_vid:
                for r in rows:
                    r["vid"] = None
        except Invalid as why:
            self._log(site, tool, "bad_body", 400, str(why), at=received)
            return 400, {"error": str(why)}
        if not rows:
            self._log(site, tool, "ignored", 200, at=received)
            return 200, {"ok": True, "recorded": 0, "duplicates": 0}
        try:
            db = store.connect(self.db_path)
            try:
                kept = [store.record_conversion(db, r) for r in rows]
                new = sum(kept)
                if digest:
                    store.keep_replay(db, site, digest, received)
                notes = soft_notes(records, tz)
                store.log_delivery(db, site, tool, "recorded" if new else "duplicate", 200,
                                   "; ".join(notes) or None, rows[0]["external_ref"], received)
            finally:
                db.close()
        except Exception as why:            # noqa: BLE001 - the tool will send again
            self._log(site, tool, "error", 500, f"store: {type(why).__name__}", at=received)
            return 500, {"error": "not kept, send again"}
        out = {"ok": True, "recorded": new, "duplicates": len(kept) - new}
        notes = [n for n in soft_notes(records, tz) if n in (LABEL_NOTE, TEST_NOTE)]
        if notes:
            out["notes"] = notes
        return 200, out

    def _test(self, site, tool, mod, payload, received, full, keep_vid=True,
              skipped=None, tz=None) -> tuple[int, dict]:
        """Read a test as the real path would, and say what it would keep:
        no visitor ID when the site's are off, nothing for another event type."""
        if not keep_vid:
            payload = without_vid(payload)
        try:
            records = mod.to_records(payload, self.sites[site], **({"tz": tz} if tz else {}))
            rows = [make_row(r, site, tool, received, self.hosts[site], full, self.country_db)
                    for r in records]
        except Invalid as why:
            self._log(site, tool, "test_failed", 400, str(why), at=received)
            return 400, {"error": str(why), "test": True}
        notes = []
        if not keep_vid:
            notes.append("visitor IDs are off for this site: the visitor ID is dropped")
            for r in rows:
                r["vid"] = None
        notes += soft_notes(records, tz)
        if skipped:
            notes.append(f"{skipped}: a real one would be answered 200 and not kept")
        self._log(site, tool, "test", 200, f"{len(rows)} record(s) read, none kept"
                  + (f"; {skipped}" if skipped else ""), at=received)
        kept = [] if skipped else rows
        return 200, {"ok": True, "test": True, "records": len(rows),
                     "would_keep": len(kept), "notes": notes,
                     "read": [{k: r.get(k) for k in ("action", "stage", "at", "vid",
                                                     "source_type", "campaign", "country",
                                                     "device", "label", "test")}
                              for r in kept[:5]]}

    def _booked(self, site: str, tool: str, ref: str) -> bool:
        """Is the booking `ref` (an external ref) of this tool kept already?"""
        if not self.db_path.exists():
            return False
        db = store.connect(self.db_path)
        try:
            return db.execute("SELECT 1 FROM conversions WHERE site = ? AND tool = ? AND "
                              "external_ref = ? LIMIT 1", (site, tool, ref)).fetchone() \
                is not None
        finally:
            db.close()

    def site_zone(self, site: str):
        """The site's time zone, with its Settings row (as run-daily reads it),
        read again at most every SITES_EVERY seconds."""
        got = self.zones.get(site)
        if got is not None and time.monotonic() - got[1] < SITES_EVERY:
            return got[0]
        from ..settings_store import apply
        from ..window import zone
        try:
            tz = zone(apply(self.sites[site], site, self.folder))
        except Exception:                  # noqa: BLE001 - the config's own zone
            tz = zone(self.sites[site])
        self.zones[site] = (tz, time.monotonic())
        return tz


def naive_note(tz) -> str:
    return f"a time without an offset was read in the site's zone, {tz}"


def soft_notes(records: list[dict], tz) -> list[str]:
    """What was kept, but not as sent: the delivery log's and a test's notes."""
    out = []
    if any(r.get("naive_at") for r in records):
        out.append(naive_note(tz))
    if any(r.get("label_dropped") for r in records):
        out.append(LABEL_NOTE)
    if any(r.get("test_dropped") for r in records):
        out.append(TEST_NOTE)
    return out


_RECEIVERS: dict = {}
_GUARD = threading.Lock()


def receiver(config: dict, folder=None, config_path=None) -> Receiver:
    """One Receiver per config for the life of the process (its rate limits
    live in memory)."""
    path = config_path or (config.get("_resolved") or {}).get("config_path")
    key = (id(config), str(folder), str(path))
    with _GUARD:
        got = _RECEIVERS.get(key)
        if got is None:
            got = _RECEIVERS[key] = Receiver(config, folder, path)
        return got


def handle(handler, config: dict, live_dir=None, config_path=None) -> None:
    """Answer one request to /traffic-hooks/ on a BaseHTTPRequestHandler.
    `live_dir` is the history's folder (None: worked out from the config)."""
    try:
        status, answer = receiver(config, live_dir, config_path).http(handler)
    except Exception:                      # noqa: BLE001 - never a traceback to a caller
        status, answer = 500, {"error": "failed"}
    raw = json.dumps(answer, separators=(",", ":")).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    if status in (411, 413):
        handler.send_header("Connection", "close")
        handler.close_connection = True
    handler.end_headers()
    handler.wfile.write(raw)
