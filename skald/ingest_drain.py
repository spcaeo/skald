"""Log drains and edge records: POST /traffic-ingest/<site>?format=vercel|netlify|edge.

A site on Vercel or Netlify has no access log Skald can read, and no server
to run the shipper on. Both platforms post their request logs to an HTTPS
address instead, a "log drain". This takes those posts on the same endpoint
as the shipper (ingest.py) and keeps each request as one line of the site's
log, which the daily run and the audit read like any other.

  Vercel   Team Settings > Drains > Add Drain > Logs > Custom endpoint,
           JSON or NDJSON. Fields: https://vercel.com/docs/drains/reference/logs
           Setup: https://vercel.com/docs/drains/using-drains
           Signature: https://vercel.com/docs/drains/security
  Netlify  a log drain to a General HTTP endpoint, traffic logs, JSON or
           NDJSON, the token in its Authorization header (no signature).
           https://docs.netlify.com/manage/monitoring/log-drains/

  edge     an edge record, Skald's own format: one request as a CDN Worker
           saw it (deploy/cloudflare-worker/skald-edge.js). Cloudflare's own
           request log (Logpush) is not on every plan; the Worker is.
           docs/CDN-LOGS.md, "Cloudflare on any plan".

The body is a JSON array of records or one record a line (NDJSON); either
is read for each format. For each record:

- a request is kept, cut down to the fields Skald reads (parse_drains.py):
  time, address, host, method, URL, status, referrer, user agent, country,
  duration, size and the request id. Everything else (deployment and
  project ids, JA3/JA4 fingerprints, messages, firewall details) is dropped
  before anything is written;
- anything that is not a request is skipped and counted: a Vercel record
  without a `proxy` object (build output, a function's own log lines), a
  Vercel revalidation (proxy.statusCode -1), a Netlify record whose
  log_type is not "traffic" (functions, edge functions, deploys); so are
  requests to Skald's own paths (/traffic-beacon, /traffic-js/,
  /traffic-hooks/) that a rewrite sends on, as nginx keeps them out of the
  main access log;
- an edge record the origin's log also has is skipped and counted, so no
  request is counted twice. With `logs.edge_only_cached` (true unless the
  site's format is `edge_json`, the edge alone) only records with cache
  "HIT" are kept: every other cf-cache-status (MISS, EXPIRED, BYPASS,
  DYNAMIC, REVALIDATED, UPDATING, STALE, none) may have reached the origin;
- a request Skald cannot read (no address, no status) is rejected and
  counted, never kept.

Who may post, in this order:

1. Vercel, with a drain secret set for the site (`ingest.drains.<site>.
   vercel_secret_env` or `vercel_secret_file`): the x-vercel-signature
   header must be the HMAC-SHA1 of the raw body with that secret (hex), or
   401. A secret set but unreadable is 503: never an open door.
2. An `Authorization: Bearer <token>` header (both platforms add one as a
   custom header): an ingest token for this site, as for the shipper.
3. Vercel, signed and without a token: accepted for the site's own
   organisation.
4. Otherwise 401. With `ingest.drains.<site>.vercel_verify` set, every
   answer to a Vercel post carries `x-vercel-verify: <that value>`, and an
   unsigned post without a token is answered 200 with nothing kept, so
   Vercel's ownership check passes (it sends no signature).

Then the shipper's checks, unchanged: removed site 410, paused site 503 (a
drain does not keep what it could not send, so those lines are lost), site waiting for
verification 403, rate limit 429, read-only organisation 402, disk 507,
plan quota and the organisation's bytes a day 429. A drain sends no batch
number: the batch id is the platform plus a hash of the body, so a delivery
Vercel or Netlify retries is kept once. Requests that overlap across
batches are dropped when read, by their request id.

An edge post is one request, so it has its own rate limit
(`ingest.edge_per_minute`, 1200; `ingest.edge_burst`, 300), apart from the
shipper's, and is appended as the next batch of one "edge" sender: no
per-post state. A record posted twice is dropped when read, by its id.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs

from . import ingest, ingest_log
from .keep_everything import Keeper
from .config import setting
from .parse_drains import _url

PLATFORMS = {"vercel": "vercel_json", "netlify": "netlify_json", "edge": "edge_json"}

# Only these fields are kept (the platforms' own names, so the kept line
# is a Vercel or Netlify record still, minus what Skald never reads).
VERCEL_TOP = ("id", "requestId", "source", "timestamp", "statusCode")
VERCEL_PROXY = ("timestamp", "method", "host", "path", "userAgent", "referer",
                "statusCode", "clientIp", "responseByteSize", "vercelId")
NETLIFY = ("log_type", "timestamp", "client_ip", "method", "url", "status_code",
           "user_agent", "referrer", "country", "duration", "response_size", "request_id")
# An edge record's fields: what an nginx line keeps, plus the cache status and
# the request id. Anything else a sender adds is dropped.
EDGE = ("ts", "ip", "method", "host", "path", "status", "bytes", "referer", "ua",
        "cache", "id")
EDGE_PER_MINUTE, EDGE_BURST = 1200, 300

# Skald's own endpoints, reached through a rewrite on the host. nginx logs
# them apart from the site's traffic (docs/BEACON.md); so does this.
OWN_PATHS = re.compile(r"^/(?:traffic-beacon(?:$|[/?])|traffic-js/|traffic-hooks/)")


def platform(path: str) -> str | None:
    """The `format` query value, lower-cased; None when there is none."""
    query = path.split("?", 1)[1] if "?" in path else ""
    got = parse_qs(query).get("format")
    return got[0].strip().lower() if got else None


# ---------------------------------------------------------------- records

def records(body: bytes) -> tuple[list, int]:
    """(the records, how many could not be read). A JSON array, or NDJSON."""
    text = body.decode("utf-8", "replace").strip()
    if not text:
        return [], 0
    if text.startswith("["):
        try:
            got = json.loads(text)
        except ValueError:
            return [], 1
        return (got, 0) if isinstance(got, list) else ([], 1)
    out, bad = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            bad += 1
    return out, bad


def keep(record, name: str, only_hits: bool = False) -> tuple[str, str | None]:
    """("line", the line to keep) | ("skip", None) | ("bad", None).
    `only_hits`: an edge record whose cache status is not HIT is skipped."""
    if not isinstance(record, dict):
        return "bad", None
    if name == "edge":
        row = {k: record[k] for k in EDGE if k in record}
        path = record.get("path")
        if only_hits and str(record.get("cache") or "").strip().upper() != "HIT":
            return "skip", None                 # the origin's log has it
    elif name == "vercel":
        proxy = record.get("proxy")
        if not isinstance(proxy, dict):
            return "skip", None                 # build output, a function's own log
        if proxy.get("statusCode") == -1:
            return "skip", None                 # a background revalidation
        row = {k: record[k] for k in VERCEL_TOP if k in record}
        row["proxy"] = {k: proxy[k] for k in VERCEL_PROXY if k in proxy}
        path = proxy.get("path")
    else:
        if record.get("log_type") != "traffic":
            return "skip", None                 # functions, edge functions, deploys
        row = {k: record[k] for k in NETLIFY if k in record}
        path = _url(record["url"])[1] if isinstance(record.get("url"), str) else None
    if isinstance(path, str) and OWN_PATHS.match(path):
        return "skip", None
    return "line", json.dumps(row, separators=(",", ":"))


def convert(body: bytes, name: str, only_hits: bool = False) -> tuple[bytes, int, int]:
    """(lines to check and keep, records skipped, records unreadable)."""
    got, bad = records(body)
    lines, skipped = [], 0
    for record in got:
        kind, line = keep(record, name, only_hits)
        if kind == "line":
            lines.append(line)
        elif kind == "skip":
            skipped += 1
        else:
            bad += 1
    return ("\n".join(lines) + "\n").encode() if lines else b"", skipped, bad


# --------------------------------------------------------------- settings

def edge_only_cached(site_config) -> bool:
    """`logs.edge_only_cached`: keep only the edge's cache hits, because the
    origin's log has the rest. Unset, true unless the site's format is
    `edge_json` (the edge records are its only log)."""
    logs = (site_config or {}).get("logs") or {}
    got = logs.get("edge_only_cached")
    if got is None:
        return str(logs.get("format") or "auto") != "edge_json"
    return got is True or str(got).strip().lower() in ("true", "yes", "1", "on")


def edge_bucket(config) -> ingest.Bucket:
    """The edge's own rate limit: a Worker posts once a request."""
    per = float(setting(config or {}, "ingest", "edge_per_minute", EDGE_PER_MINUTE))
    burst = float(setting(config or {}, "ingest", "edge_burst", EDGE_BURST))
    with ingest._BUCKETS_GUARD:
        got = ingest._BUCKETS.get(("edge", per, burst))
        if got is None:
            got = ingest._BUCKETS[("edge", per, burst)] = ingest.Bucket(per, burst)
        return got


def drain_setting(config, site: str, key: str):
    drains = ((config or {}).get("ingest") or {}).get("drains") or {}
    own = drains.get(site) if isinstance(drains, dict) else None
    return own.get(key) if isinstance(own, dict) else None


def vercel_secret(config, site: str) -> bytes | None:
    """The drain's signature secret: None when none is set; b"" when one is
    set but cannot be read (the endpoint then refuses everything)."""
    env = drain_setting(config, site, "vercel_secret_env")
    path = drain_setting(config, site, "vercel_secret_file")
    if not env and not path:
        return None
    value = os.environ.get(str(env), "") if env else ""
    if not value and path:
        try:
            value = Path(str(path)).expanduser().read_text().strip()
        except OSError:
            value = ""
    return value.encode()


# ------------------------------------------------------------------- HTTP

def _read_raw(h) -> bytes | None:
    raw_len = h.headers.get("Content-Length")
    if raw_len is None:
        ingest.no(h, 411, "Content-Length is needed")
        return None
    try:
        length = int(raw_len)
    except ValueError:
        length = -1
    if length < 0:
        ingest.no(h, 400, "bad Content-Length")
        return None
    if length > ingest.MAX_BODY:
        ingest.no(h, 413, f"a batch is at most {ingest.MAX_BODY // (1024 * 1024)} MiB")
        return None
    return h.rfile.read(length) if length else b""


def _who(db, h, site: str, name: str, raw: bytes, config) -> tuple:
    """(organisation id, 0, "") or (None, status, why)."""
    from .accounts import apitokens
    signed = False
    if name == "vercel":
        secret = vercel_secret(config, site)
        if secret == b"":
            return None, 503, "the drain's secret is set in the config but could not be read"
        if secret is not None:
            want = hmac.new(secret, raw, hashlib.sha1).hexdigest()
            sent = (h.headers.get("x-vercel-signature") or "").strip().lower()
            if not sent or not hmac.compare_digest(want, sent):
                return None, 401, "the x-vercel-signature does not match the drain's secret"
            signed = True
    header = h.headers.get("Authorization")
    if header:
        ok, why, entry = apitokens.check(db, header, site, "ingest")
        if not ok:
            return None, (403 if ("not for that site" in why or "scope" in why) else 401), why
        return entry["org_id"], 0, ""
    if signed:
        owner = db.execute("SELECT org_id FROM sites WHERE name = ?", (site,)).fetchone()
        if owner is None:
            return None, 403, "this token is not for that site"
        return owner[0], 0, ""
    return None, 401, "a bearer token is needed"


def handle(h, config, live_dir, config_path, site: str, name: str) -> None:
    """Answer one drain post (ingest._handle has checked on, POST, path)."""
    if name not in PLATFORMS:
        return ingest.no(h, 400, "format is vercel, netlify or edge (or none, for the shipper)")
    from .accounts import db as base
    verify = drain_setting(config, site, "vercel_verify") if name == "vercel" else None
    extra = {"x-vercel-verify": str(verify)} if verify else {}
    acc = base.path_for(config, ingest.history_folder(config, live_dir))
    if acc is None or not Path(acc).is_file():
        return ingest.no(h, 503, "accounts are not set up here", extra)
    raw = _read_raw(h)
    if raw is None:
        return None
    db = base.connect(acc)
    try:
        org, code, why = _who(db, h, site, name, raw, config)
        if org is None:
            if verify and code == 401 and not h.headers.get("Authorization") \
                    and not h.headers.get("x-vercel-signature"):
                return ingest._answer(h, 200, {"ok": True, "accepted": 0, "rejected": 0,
                                               "skipped": 0, "duplicate": False}, extra)
            hdrs = dict(extra, **({"WWW-Authenticate": "Bearer"} if code == 401 else {}))
            return ingest.no(h, code, why, hdrs)
        stop = ingest.held(db, site)          # removed 410, paused 503
        if stop:
            return ingest.no(h, stop[0], stop[1], dict(extra, **(stop[2] or {})))
        from .site_verify import PENDING_WORDS, pending
        if pending(db, site):
            return ingest.no(h, 403, PENDING_WORDS, extra)
        own = ingest.site_configs(config, config_path).get(site)
        if own is None:
            return ingest.no(h, 404, "this install does not process that site", extra)
        fmt = str(((own.get("logs") or {}).get("format")) or "auto")
        if fmt not in ("auto", PLATFORMS[name]):
            return ingest.no(h, 400, f"this site's log format is {fmt}; set it to "
                             f"{PLATFORMS[name]} or auto to take a {name} drain", extra)
        wait = (edge_bucket(config) if name == "edge" else ingest.bucket(config)).take(site)
        if wait:
            return ingest.no(h, 429, "too many batches for this site; slow down",
                             dict(extra, **{"Retry-After": str(max(1, int(wait + 0.999)))}))
        ingest_root = ingest_log.root(config, ingest.history_folder(config, live_dir))
        stop = ingest.guard(db, config, org, ingest_root)
        if stop:
            status, words, hdrs = stop
            return ingest.no(h, status, words, dict(extra, **(hdrs or {})))
        try:
            body = ingest.unpack(raw, h.headers.get("Content-Encoding") or "")
        except LookupError:
            return ingest.no(h, 415, "send the body plain or with Content-Encoding: gzip", extra)
        except OverflowError:
            return ingest.no(h, 413, "a batch is at most 5 MiB unpacked", extra)
        except ValueError as bad:
            return ingest.no(h, 400, str(bad), extra)
        return _keep(h, db, config, live_dir, site, name, org, fmt, raw, body,
                     ingest_root, extra, name == "edge" and edge_only_cached(own))
    finally:
        db.close()


def _keep(h, db, config, live_dir, site, name, org, fmt, raw, body, ingest_root, extra,
          only_hits=False):
    lines, skipped, bad = convert(body, name, only_hits)
    data, accepted, rejected = ingest.split(lines, fmt)
    rejected += bad
    shipper, seq = f"{name}-{hashlib.sha256(raw).hexdigest()[:40]}", 1
    if name == "edge":                  # one sender, the next batch: no state a post
        shipper, seq = "edge", None
    folder = ingest_log.site_folder(ingest_root, site)
    writer = ingest_log.Writer(
        folder, keep=int(setting(config, "ingest", "keep", ingest_log.KEEP)),
        max_mb=float(setting(config, "ingest", "max_mb", ingest_log.MAX_MB)),
        archive=Keeper(config, live_dir)(site))
    dup = {"ok": True, "accepted": 0, "rejected": 0, "skipped": 0, "duplicate": True}
    if seq is not None and writer.seen(shipper, seq):
        return ingest._answer(h, 200, dup, extra)
    refusal = ingest.quota(db, config, site, org, accepted, len(data),
                           ingest.history_folder(config, live_dir) / "history.sqlite") \
        if accepted else None
    if refusal:
        return ingest.no(h, 429, refusal, dict(extra, **{"Retry-After": "3600"}))
    cap = ingest.daily_cap(db, config, org)
    if not ingest_log.reserve(ingest_root, org, len(data), cap):
        return ingest.no(h, 429, ingest.DAY_WORDS.format(mb=ingest._mb(cap)),
                         dict(extra, **{"Retry-After": str(ingest_log.to_midnight())}))
    try:
        outcome = writer.append(shipper, seq, data, accepted, rejected)
    except BaseException as why:
        ingest_log.release(ingest_root, org, len(data))
        if isinstance(why, ingest_log.Full):
            return ingest.no(h, 429, str(why),
                             dict(extra, **{"Retry-After": str(why.retry_after)}))
        raise
    if outcome == "duplicate":
        ingest_log.release(ingest_root, org, len(data))
        return ingest._answer(h, 200, dup, extra)
    return ingest._answer(h, 200, {"ok": True, "accepted": accepted, "rejected": rejected,
                                   "skipped": skipped, "duplicate": False}, extra)
