"""Getting a customer's server log in: POST /traffic-ingest/<site>.

The shipper (tools/skald-ship.py) tails the access log on the customer's
server and posts batches of lines here; the refresh helper answers. Off
unless `ingest: {enabled: true}` and accounts are set up (the token lives in
accounts.sqlite). docs/INGEST.md is the reader's guide.

Each request, in this order, before anything is kept:

  1. `ingest.enabled`, else 404; POST only, else 405
  2. Authorization: Bearer <token>, an organisation token with the "ingest"
     scope (accounts/apitokens.py) for this very site: 401 for no or a bad
     token, 403 for a token of another organisation or site, or without the
     scope. An unknown site gets the same 403, so a token cannot probe
     which sites exist.
  3. a site removed in Settings > Sites: 410; a site waiting for its domain
     to be verified (site_verify.py): 403
  4. at most `ingest.per_minute` batches a minute per site (burst
     `ingest.burst`): 429 with Retry-After; then (`guard`) a read-only
     organisation (saas.limits.read_only): 402, and less than
     `ingest.min_free_gb` (5) free on the ingest root's disk: 507
  5. Content-Length needed (411); a body of at most 5 MiB (413), gzip
     (Content-Encoding: gzip) or plain (415 for anything else); unpacked, at
     most 5 MiB too (413); a broken gzip stream is 400
  6. X-Skald-Batch: <shipper id>:<seq>, else 400
  7. every line must parse in the site's `logs.format` (parse.PARSERS;
     "auto" takes any format Skald reads). Lines that do not are counted as
     rejected and dropped: their content is never stored, logged or echoed
  8. the plan's quota, when skald.saas.limits exists and has
     `over_limit` (see `quota`): 429 with the reason; then the
     organisation's bytes for the UTC day (`daily_cap`: the plan's
     `ingest_daily_mb`, else `ingest.org_daily_mb`, 200), counted as they
     are accepted (ingest_log.reserve; given back when nothing is written):
     429 with the seconds to midnight UTC
  9. the accepted lines are appended to <ingest root>/<site>/access.log
     (ingest_log.py: daily rotation, each batch once): 200
     {"ok", "accepted", "rejected", "duplicate"}. A batch seen before is
     acknowledged with "duplicate": true and nothing written. A full day
     is 429 with the seconds to midnight UTC.

Nothing about the sender is kept: no address, no user agent.

With `?format=vercel` or `?format=netlify` the post is a platform's log
drain instead of a shipper's batch: ingest_drain.py answers it (its own
auth step, Vercel's signature; then the same checks as above).
"""
from __future__ import annotations

import inspect
import json
import re
import shutil
import threading
import time
import zlib
from pathlib import Path

from . import ingest_log
from .config import setting, site_name
from .parse import AUTO_ORDER, PARSERS
from .parse_cdn import W3C_HEADER

PREFIX = "/traffic-ingest/"
PATH = re.compile(r"^/traffic-ingest/(?P<site>[a-z0-9.-]{1,100})/?$")
BATCH = re.compile(r"^(?P<shipper>[A-Za-z0-9_-]{1,64}):(?P<seq>\d{1,18})$")
MAX_BODY = 5 * 1024 * 1024
MAX_LINE = 64 * 1024
PER_MINUTE, BURST = 120, 30


def is_ingest(path: str) -> bool:
    return path.split("?", 1)[0].startswith(PREFIX.rstrip("/"))


def enabled(config) -> bool:
    got = ((config or {}).get("ingest") or {}).get("enabled")
    return got is True or str(got).lower() == "true"


# ------------------------------------------------------------- rate limit

class Bucket:
    """A token bucket per key: `per_minute` refill, `burst` capacity."""

    def __init__(self, per_minute: float, burst: float, clock=time.monotonic):
        self.rate, self.cap, self.clock = per_minute / 60.0, max(1.0, burst), clock
        self.state: dict[str, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def take(self, key: str) -> float:
        """0 when allowed, else the seconds to wait."""
        with self.lock:
            now = self.clock()
            tokens, at = self.state.get(key, (self.cap, now))
            tokens = min(self.cap, tokens + (now - at) * self.rate)
            if tokens >= 1:
                self.state[key] = (tokens - 1, now)
                return 0.0
            self.state[key] = (tokens, now)
            return (1 - tokens) / self.rate if self.rate > 0 else 60.0


_BUCKETS: dict[tuple, Bucket] = {}
_BUCKETS_GUARD = threading.Lock()


def bucket(config) -> Bucket:
    per = float(setting(config or {}, "ingest", "per_minute", PER_MINUTE))
    burst = float(setting(config or {}, "ingest", "burst", BURST))
    with _BUCKETS_GUARD:
        got = _BUCKETS.get((per, burst))
        if got is None:
            got = _BUCKETS[(per, burst)] = Bucket(per, burst)
        return got


# ------------------------------------------------------------------ lines

def line_checker(fmt: str):
    """A function line -> True when Skald can read it in `fmt`."""
    fmt = fmt if fmt in PARSERS or fmt == "auto" else "auto"
    w3c_ok = fmt in ("auto", "cloudfront_w3c")
    parsers = [PARSERS[n] for n in AUTO_ORDER] if fmt == "auto" else [PARSERS[fmt]]

    def ok(line: str) -> bool:
        if W3C_HEADER.match(line):
            return w3c_ok
        return any(p(line) is not None for p in parsers)
    return ok


def split(body: bytes, fmt: str) -> tuple[bytes, int, int]:
    """(the accepted lines, how many, how many rejected). Blank lines are
    neither. A rejected line is counted and dropped, never kept."""
    ok = line_checker(fmt)
    kept, accepted, rejected = [], 0, 0
    for raw in body.split(b"\n"):
        raw = raw.rstrip(b"\r")
        if not raw.strip():
            continue
        if len(raw) > MAX_LINE or b"\x00" in raw:
            rejected += 1
            continue
        if ok(raw.decode("utf-8", "replace")):
            kept.append(raw)
            accepted += 1
        else:
            rejected += 1
    return (b"\n".join(kept) + b"\n") if kept else b"", accepted, rejected


def unpack(raw: bytes, encoding: str) -> bytes:
    """The body unpacked; ValueError (400) or OverflowError (413)."""
    encoding = (encoding or "identity").strip().lower()
    if encoding in ("", "identity"):
        return raw
    if encoding != "gzip":
        raise LookupError(encoding)
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = d.decompress(raw, MAX_BODY + 1)
    except zlib.error:
        raise ValueError("the gzip body could not be read") from None
    if len(out) > MAX_BODY or d.unconsumed_tail:
        raise OverflowError
    if not d.eof:
        raise ValueError("the gzip body is cut short")
    return out


# ------------------------------------------------------------------ quota

QUOTA_WORDS = ("This month's requests are over the plan's limit. Nothing is lost: the "
               "shipper keeps the lines and tries again. Choose a bigger plan in "
               "Settings > Billing.")


def quota(db, config, site: str, org_id, lines: int, nbytes: int,
          history_path=None) -> str | None:
    """The plan's refusal, or None. Asks skald.saas.limits.over_limit
    when that module exists (absent: no limit). It is called with the
    keyword arguments it names among db, config, site, org_id, lines,
    nbytes and history_path. Its answer: the list of limits the organisation
    is past (saas/limits.py; any limit stops new lines), or
    None/False, True, a reason, (over, reason) or {"over", "reason"}."""
    try:
        from .saas import limits as plan
    except ImportError:
        return None
    fn = getattr(plan, "over_limit", None)
    if fn is None:
        return None
    given = {"db": db, "config": config, "site": site, "org_id": org_id, "lines": lines,
             "nbytes": nbytes, "history_path": history_path}
    try:
        names = inspect.signature(fn).parameters
        takes_all = any(p.kind is p.VAR_KEYWORD for p in names.values())
        got = fn(**(given if takes_all else {k: v for k, v in given.items() if k in names}))
    except Exception as why:              # noqa: BLE001 - a broken plan check refuses
        return f"the plan's limits could not be checked ({type(why).__name__})"
    if isinstance(got, (list, tuple, set)) and all(isinstance(x, str) for x in got):
        if not got:
            return None
        if list(got) == ["requests_month"]:
            return QUOTA_WORDS
        return (f"Over the plan's limit ({', '.join(sorted(got))}). Nothing is lost: the "
                "shipper keeps the lines and tries again. Change the plan in "
                "Settings > Billing.")
    if isinstance(got, dict):
        return (got.get("reason") or "over the plan's limit") if got.get("over") else None
    if isinstance(got, (tuple, list)) and got:
        return (str(got[1]) if len(got) > 1 and got[1] else "over the plan's limit") \
            if got[0] else None
    if got is True:
        return "over the plan's limit"
    return str(got) if isinstance(got, str) and got else None


# ------------------------------------------------- disk and the org's day

ORG_DAILY_MB, MIN_FREE_GB = 200, 5
disk_usage = shutil.disk_usage            # tests put a smaller disk here
DAY_WORDS = ("This organisation's {mb} MB a day of log lines is used up. Nothing is lost: "
             "the shipper keeps the lines and tries again after midnight UTC.")
DISK_WORDS = ("The server is short of disk space, so no lines are taken now. Nothing is "
              "lost: the shipper keeps the lines and tries again.")


def _mb(nbytes: int) -> str:
    return f"{nbytes / (1024 * 1024):g}"


def daily_cap(db, config, org_id) -> int:
    """Bytes an organisation may ship a day: its plan's `ingest_daily_mb`
    (saas), else `ingest.org_daily_mb` (200)."""
    mb = setting(config or {}, "ingest", "org_daily_mb", ORG_DAILY_MB)
    try:
        from .saas import limits as plan, plans as table
        got = plan.limits_for(db, org_id, config)
        if got:
            own = (table.plans(config).get(got["plan"]) or {}).get("ingest_daily_mb")
            if own is not None:
                mb = own
    except Exception:                     # noqa: BLE001 - no saas: the install's size
        pass
    return int(float(mb) * 1024 * 1024)


def free_bytes(path) -> int:
    """Free space on the filesystem `path` is (or will be) on."""
    path = Path(path)
    while not path.exists() and path.parent != path:
        path = path.parent
    return int(disk_usage(path).free)


def guard(db, config, org_id, ingest_root) -> tuple | None:
    """(status, words, headers) that stops a batch before it is read, or
    None: 402 for a read-only organisation (saas), 507 when the ingest
    root's filesystem has less than `ingest.min_free_gb` (5) free."""
    try:
        from .saas import limits as plan
        locked = getattr(plan, "read_only", None)
        why = locked(db, org_id, config) if locked else None
    except ImportError:
        why = None
    if why:
        return 402, why, None
    need = float(setting(config or {}, "ingest", "min_free_gb", MIN_FREE_GB)) * 1024 ** 3
    if free_bytes(ingest_root) < need:
        return 507, DISK_WORDS, {"Retry-After": "600"}
    return None


# ------------------------------------------------------------------- HTTP

def _answer(h, code: int, body: dict, headers: dict | None = None) -> None:
    data = json.dumps(body, separators=(",", ":")).encode()
    h.send_response(code)
    h.send_header("Content-Type", "application/json; charset=utf-8")
    h.send_header("Cache-Control", "no-store")
    h.send_header("X-Content-Type-Options", "nosniff")
    for k, v in (headers or {}).items():
        h.send_header(k, v)
    h.send_header("Content-Length", str(len(data)))
    if code in (411, 413):
        h.send_header("Connection", "close")
        h.close_connection = True
    h.end_headers()
    h.wfile.write(data)


def no(h, code: int, error: str, headers: dict | None = None) -> None:
    _answer(h, code, {"ok": False, "error": error}, headers)


def site_configs(config, config_path) -> dict[str, dict]:
    """{name: merged config} for every site the install processes."""
    out = {site_name(config or {}): config or {}}
    if config_path is not None:
        from . import multisite
        try:
            for got in multisite.site_configs(config or {}, Path(config_path)):
                out.setdefault(site_name(got), got)
        except SystemExit:
            pass
    return out


def history_folder(config, live_dir) -> Path:
    if live_dir is not None:
        return Path(live_dir)
    from .settings_store import history_folder as hf
    return hf(config) or Path(".")


def handle(h, config, live_dir, config_path=None) -> None:
    """Answer one request to /traffic-ingest/ on the helper's handler."""
    try:
        return _handle(h, config or {}, live_dir, config_path)
    except Exception as why:               # noqa: BLE001 - never a traceback to a caller
        import sys
        sys.stderr.write(f"ingest: failed ({type(why).__name__})\n")
        return no(h, 500, "failed")


def _handle(h, config, live_dir, config_path) -> None:
    if not enabled(config):
        return no(h, 404, "not found")
    if h.command != "POST":
        return no(h, 405, "POST only", {"Allow": "POST"})
    path = h.path.split("?", 1)[0]
    m = PATH.match(path)
    if m is None or ".." in path:
        return no(h, 404, "not found")
    site = m.group("site")
    from . import ingest_drain                # ?format=vercel|netlify: a log drain
    drain = ingest_drain.platform(h.path)
    if drain is not None:
        return ingest_drain.handle(h, config, live_dir, config_path, site, drain)
    from .accounts import apitokens, db as base, site_configs as dsites
    acc = base.path_for(config, history_folder(config, live_dir))
    if acc is None or not Path(acc).is_file():
        return no(h, 503, "accounts are not set up here")
    db = base.connect(acc)
    try:
        ok, why, entry = apitokens.check(db, h.headers.get("Authorization"), site, "ingest")
        if not ok:
            code = 403 if ("not for that site" in why or "scope" in why) else 401
            return no(h, code, why, {"WWW-Authenticate": "Bearer"} if code == 401 else None)
        row = dsites.get(db, site)
        if row is not None and not row["active"]:
            return no(h, 410, "this site was removed; nothing is kept for it")
        from .site_verify import PENDING_WORDS, pending
        if pending(db, site):
            return no(h, 403, PENDING_WORDS)
        configs = site_configs(config, config_path)
        own = configs.get(site)
        if own is None:
            return no(h, 404, "this install does not process that site")
        wait = bucket(config).take(site)
        if wait:
            return no(h, 429, "too many batches for this site; slow down",
                      {"Retry-After": str(max(1, int(wait + 0.999)))})
        ingest_root = ingest_log.root(config, history_folder(config, live_dir))
        stop = guard(db, config, entry["org_id"], ingest_root)
        if stop:
            return no(h, *stop)
        body = _read_body(h)
        if body is None:
            return None
        got = BATCH.match(h.headers.get("X-Skald-Batch") or "")
        if got is None:
            return no(h, 400, "X-Skald-Batch: <shipper id>:<seq> is needed")
        shipper, seq = got.group("shipper"), int(got.group("seq"))
        folder = ingest_log.site_folder(
            ingest_log.root(config, history_folder(config, live_dir)), site)
        writer = ingest_log.Writer(
            folder, keep=int(setting(config, "ingest", "keep", ingest_log.KEEP)),
            max_mb=float(setting(config, "ingest", "max_mb", ingest_log.MAX_MB)))
        if writer.seen(shipper, seq):
            writer.append(shipper, seq, b"")          # counted as a duplicate
            return _answer(h, 200, {"ok": True, "accepted": 0, "rejected": 0,
                                    "duplicate": True})
        fmt = str(((own.get("logs") or {}).get("format")) or "auto")
        data, accepted, rejected = split(body, fmt)
        refusal = quota(db, config, site, entry["org_id"], accepted, len(data),
                        history_folder(config, live_dir) / "history.sqlite") \
            if accepted else None
        if refusal:
            return no(h, 429, refusal, {"Retry-After": "3600"})
        cap = daily_cap(db, config, entry["org_id"])
        if not ingest_log.reserve(ingest_root, entry["org_id"], len(data), cap):
            return no(h, 429, DAY_WORDS.format(mb=_mb(cap)),
                      {"Retry-After": str(ingest_log.to_midnight())})
        try:
            outcome = writer.append(shipper, seq, data, accepted, rejected)
        except BaseException as why:
            ingest_log.release(ingest_root, entry["org_id"], len(data))
            if isinstance(why, ingest_log.Full):
                return no(h, 429, str(why), {"Retry-After": str(why.retry_after)})
            raise
        if outcome == "duplicate":
            ingest_log.release(ingest_root, entry["org_id"], len(data))
            return _answer(h, 200, {"ok": True, "accepted": 0, "rejected": 0,
                                    "duplicate": True})
        return _answer(h, 200, {"ok": True, "accepted": accepted, "rejected": rejected,
                                "duplicate": False})
    finally:
        db.close()


def _read_body(h) -> bytes | None:
    raw_len = h.headers.get("Content-Length")
    if raw_len is None:
        no(h, 411, "Content-Length is needed")
        return None
    try:
        length = int(raw_len)
    except ValueError:
        length = -1
    if length < 0:
        no(h, 400, "bad Content-Length")
        return None
    if length > MAX_BODY:
        no(h, 413, f"a batch is at most {MAX_BODY // (1024 * 1024)} MiB")
        return None
    raw = h.rfile.read(length) if length else b""
    try:
        return unpack(raw, h.headers.get("Content-Encoding") or "")
    except LookupError:
        no(h, 415, "send the body plain or with Content-Encoding: gzip")
    except OverflowError:
        no(h, 413, f"a batch is at most {MAX_BODY // (1024 * 1024)} MiB unpacked")
    except ValueError as why:
        no(h, 400, str(why))
    return None
