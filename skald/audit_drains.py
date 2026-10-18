"""The audit's own reader for log-drain lines (Vercel, Netlify, edge records).

audit.py recounts a day from the raw lines by a road of its own. A site on
Vercel or Netlify has no nginx log: its lines are the drain records the
ingest endpoint kept (ingest_drain.py), one JSON object a line. This reads
them again without the package's parser (parse_drains.py, parse_cdn.py):
its own JSON checks, its own timestamp reading, its own URL split. Only the
documented field names are shared, because they are the platforms' data.

  Vercel:  https://vercel.com/docs/drains/reference/logs
  Netlify: https://docs.netlify.com/manage/monitoring/log-drains/

fields() gives the keyword arguments of audit.Line, or None for a line it
does not read. The rules match the main road's on purpose (written apart):
a record needs the client's address, a three-digit status and a URL;
Vercel's revalidations (status -1) and records without a `proxy` are not
requests; Netlify's records other than `log_type: traffic` are not either.

Edge records (Skald's own format, posted by a CDN Worker; ingest_drain.py)
are read here too: `ts` is RFC 3339 or a JSON number of Unix milliseconds,
`path` starts with "/", `id` is the request's id. No country.

Caddy's JSON access log too (https://caddyserver.com/docs/caddyfile/directives/log):
`ts` is Unix seconds, the request is under `request` (`client_ip` when
Caddy has trusted proxies, else `remote_ip`; `host`, `method`, `uri`, and
`headers` as lists of values, any letter case), `status` is a number.
Country only from a logged CF-IPCountry header.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

_UTC = timezone.utc
_EPOCH = datetime(1970, 1, 1, tzinfo=_UTC)


def _string(value) -> str:
    if value is None or value == "-":
        return ""
    return value if isinstance(value, str) else str(value)


def _three_digits(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    text = str(value).strip()
    return text if len(text) == 3 and text.isdigit() else ""


def _from_number(value) -> datetime | None:
    """Unix time, the unit told by its size (Vercel writes milliseconds)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    scale = 1
    for limit, per in ((1e17, 10**9), (1e14, 10**6), (1e11, 10**3)):
        if value >= limit:
            scale = per
            break
    if isinstance(value, int):
        return _EPOCH + timedelta(microseconds=value * 10**6 // scale)
    return _EPOCH + timedelta(microseconds=round(value * 10**6 / scale))


def _from_text(value: str) -> datetime | None:
    """RFC 3339: 2021-08-24T18:54:34.831Z, any number of fractional digits,
    Z or an offset. A string of digits is Unix time."""
    text = value.strip()
    if text.isdigit():
        return _from_number(int(text))
    if len(text) < 19 or text[4] != "-" or text[10] not in "Tt ":
        return None
    head, rest = text[:19], text[19:]
    micro = 0
    if rest[:1] in (".", ","):
        digits = ""
        for ch in rest[1:]:
            if not ch.isdigit():
                break
            digits += ch
        if not digits:
            return None
        micro = int((digits + "000000")[:6])
        rest = rest[1 + len(digits):]
    zone = rest.strip()
    if zone in ("", "Z", "z"):
        tz = _UTC
    else:
        sign = zone[:1]
        bare = zone[1:].replace(":", "")
        if sign not in "+-" or len(bare) != 4 or not bare.isdigit():
            return None
        delta = timedelta(hours=int(bare[:2]), minutes=int(bare[2:]))
        tz = timezone(delta if sign == "+" else -delta)
    try:
        base = datetime.strptime(head.replace("t", "T").replace(" ", "T"),
                                 "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return base.replace(microsecond=micro, tzinfo=tz)


def _time(value) -> datetime | None:
    try:
        if isinstance(value, str):
            return _from_text(value)
        return _from_number(value)
    except (OverflowError, ValueError):
        return None


def _vercel(row: dict) -> dict | None:
    proxy = row["proxy"]
    path = proxy.get("path")
    address = _string(proxy.get("clientIp")).strip()
    if not isinstance(path, str) or path == "" or address == "":
        return None
    when = _time(proxy["timestamp"] if proxy.get("timestamp") is not None
                 else row.get("timestamp"))
    code = proxy.get("statusCode")
    status = _three_digits(code if code is not None else row.get("statusCode"))
    if when is None or status == "":
        return None
    agents = proxy.get("userAgent")
    if isinstance(agents, list):
        agent = next((a for a in agents if isinstance(a, str) and a), "")
    else:
        agent = _string(agents)
    rid = row.get("requestId") or proxy.get("vercelId") or row.get("id") or ""
    return {"when": when, "address": address, "host": _string(proxy.get("host")),
            "method": _string(proxy.get("method")), "url": path, "status": status,
            "referrer": _string(proxy.get("referer")), "agent": agent, "country": "",
            "rid": str(rid)[:128]}


def _netlify(row: dict) -> dict | None:
    raw = row.get("url")
    address = _string(row.get("client_ip")).strip()
    if not isinstance(raw, str) or raw == "" or address == "":
        return None
    when = _time(row.get("timestamp"))
    status = _three_digits(row.get("status_code"))
    if when is None or status == "":
        return None
    host, url = "", raw.partition("#")[0]
    scheme, sep, _ = raw.partition("://")
    if sep and scheme[:1].isalpha() and all(c.isalnum() or c in "+.-" for c in scheme):
        parts = urlsplit(raw)
        host = (parts.hostname or "").lower()
        url = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    cc = _string(row.get("country")).strip().upper()
    if len(cc) != 2 or not cc.isalpha() or cc in ("XX", "ZZ"):
        cc = ""
    return {"when": when, "address": address, "host": host,
            "method": _string(row.get("method")), "url": url, "status": status,
            "referrer": _string(row.get("referrer")), "agent": _string(row.get("user_agent")),
            "country": cc, "rid": _string(row.get("request_id"))[:128]}


def _edge_when(value) -> datetime | None:
    """RFC 3339, or a JSON number of Unix milliseconds; nothing else."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if not value >= 0:                      # negative, or NaN
            return None
        try:
            if isinstance(value, int):
                return _EPOCH + timedelta(microseconds=value * 1000)
            return _EPOCH + timedelta(microseconds=round(value * 1000))
        except (OverflowError, ValueError):
            return None
    if not isinstance(value, str) or value.strip().isdigit():
        return None
    return _time(value)


def _edge(row: dict) -> dict | None:
    path = row.get("path")
    address = _string(row.get("ip")).strip()
    if not isinstance(path, str) or path[:1] != "/" or address == "":
        return None
    when = _edge_when(row.get("ts"))
    status = _three_digits(row.get("status"))
    if when is None or status == "":
        return None
    return {"when": when, "address": address, "host": _string(row.get("host")),
            "method": _string(row.get("method")), "url": path, "status": status,
            "referrer": _string(row.get("referer")), "agent": _string(row.get("ua")),
            "country": "", "rid": _string(row.get("id"))[:128]}


def _header(headers, name: str) -> str:
    if not isinstance(headers, dict):
        return ""
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == name:
            if isinstance(value, list):
                value = value[0] if value else ""
            return _string(value)
    return ""


def _caddy(row: dict) -> dict | None:
    req = row["request"]
    address = _string(req.get("client_ip") or req.get("remote_ip")).strip()
    uri = req.get("uri")
    if not isinstance(uri, str) or uri == "" or address == "":
        return None
    seconds = row.get("ts")
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
        return None
    try:
        when = _EPOCH + timedelta(microseconds=round(seconds * 10**6))
    except (OverflowError, ValueError):
        return None
    status = _three_digits(row.get("status"))
    if status == "":
        return None
    headers = req.get("headers")
    cc = _header(headers, "cf-ipcountry").strip().upper()
    if len(cc) != 2 or not cc.isalpha() or cc in ("XX", "ZZ"):
        cc = ""
    host = _string(req.get("host"))
    name, colon, port = host.rpartition(":")
    if colon and port.isdigit() and "]" not in host and name:
        host = name                                    # a host with :443 on it
    return {"when": when, "address": address, "host": host,
            "method": _string(req.get("method")), "url": uri, "status": status,
            "referrer": _header(headers, "referer"), "agent": _header(headers, "user-agent"),
            "country": cc, "rid": ""}


def fields(raw: str) -> dict | None:
    """audit.Line's fields from one drain line, or None."""
    text = raw.strip()
    if not text.startswith("{"):
        return None
    try:
        row = json.loads(text)
    except ValueError:
        return None
    if not isinstance(row, dict):
        return None
    if isinstance(row.get("proxy"), dict):
        return _vercel(row)
    if row.get("log_type") == "traffic":
        return _netlify(row)
    if isinstance(row.get("request"), dict) and "ts" in row:
        return _caddy(row)
    if "ts" in row and "log_type" not in row:
        return _edge(row)
    return None
