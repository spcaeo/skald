"""Read CDN logs: Cloudflare Logpush, CloudFront standard logs, Fastly JSON.

A site behind a CDN is mostly answered by the CDN. A page served from the
CDN's cache never reaches the origin, so the origin's access log never sees
it. The CDN's own log sees every request. These parsers turn its lines into
the same Hit the server formats produce, so nothing downstream changes.

How to ship each CDN's logs to the box Skald runs on is in docs/CDN-LOGS.md.

  cloudflare_json  Logpush, dataset http_requests, one JSON object a line.
  cloudfront_w3c   CloudFront standard (legacy) logs: W3C, tab-separated.
  fastly_json      a JSON log format written in Fastly's VCL. Fastly has no
                   fixed format, so the common field names are all accepted.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from .parse import Hit, _country, _when_clf

UTC = timezone.utc


# ------------------------------------------------------------------ values

def _number(value) -> float | None:
    """A number from JSON: int, float or a numeric string. None otherwise."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _duration(value, per_second: float) -> float | None:
    """A duration in some unit, as seconds. The same bound as $request_time:
    a negative or a day-long value is not a request time."""
    got = _number(value)
    if got is None:
        return None
    seconds = got / per_second
    return seconds if 0 <= seconds < 86400 else None


def _bytes(value) -> int | None:
    got = _number(value)
    return int(got) if got is not None and got >= 0 else None


def _epoch(value: int | float) -> datetime:
    """Unix time in seconds, milliseconds, microseconds or nanoseconds.

    The unit is read from the size. Seconds stay below 1e11 until the year
    5138, so nothing real is mistaken. Integers are split exactly: a float
    holds a nanosecond timestamp only to about a quarter of a microsecond.
    """
    if value < 0:
        raise ValueError("negative timestamp")
    if value >= 1e17:
        per = 10**9
    elif value >= 1e14:
        per = 10**6
    elif value >= 1e11:
        per = 10**3
    else:
        per = 1
    if isinstance(value, int):
        whole, part = divmod(value, per)
        micro = part * 10**6 // per
    else:
        seconds = value / per
        whole = int(seconds)
        micro = round((seconds - whole) * 10**6)
    return datetime.fromtimestamp(whole, tz=UTC) + timedelta(microseconds=micro)


_ISO = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:[.,](\d+))?"
    r"\s*(Z|z|[+-]\d{2}:?\d{2})?"
)


def _when(value) -> datetime:
    """A timestamp in any of the forms a CDN log writes.

    RFC 3339 / ISO 8601 with "Z", "+00:00" or "+0000" (what strftime's %z
    writes, which Python 3.10's fromisoformat refuses), any number of
    fractional digits; Unix time as a number or a string of digits; and the
    bracketed common log time ("%t" in a Fastly format). No zone: UTC, as
    every CDN logs in UTC. Raises ValueError for anything else.
    """
    if isinstance(value, bool) or value is None:
        raise ValueError("no timestamp")
    if isinstance(value, (int, float)):
        return _epoch(value)
    text = str(value).strip()
    if re.fullmatch(r"\d+", text):
        return _epoch(int(text))
    if re.fullmatch(r"\d+\.\d+", text):
        return _epoch(float(text))
    if text.startswith("[") and text.endswith("]"):
        return _when_clf(text[1:-1])
    m = _ISO.fullmatch(text)
    if not m:
        raise ValueError(f"not a timestamp: {text[:40]}")
    year, month, day, hour, minute, second, frac, zone = m.groups()
    micro = int((frac or "0")[:6].ljust(6, "0"))
    if zone in (None, "Z", "z"):
        tz = UTC
    else:
        digits = zone[1:].replace(":", "")
        offset = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        tz = timezone(-offset if zone[0] == "-" else offset)
    return datetime(int(year), int(month), int(day), int(hour), int(minute),
                    int(second), micro, tzinfo=tz)


def _text(value) -> str:
    """A string field; a JSON null, a number or "-" read as what they say."""
    if value is None:
        return ""
    text = str(value)
    return "" if text == "-" else text


def _json_object(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        row = json.loads(line)
    except ValueError:
        return None
    return row if isinstance(row, dict) else None


# -------------------------------------------------------------- cloudflare

def cloudflare(line: str) -> Hit | None:
    """One Logpush http_requests record (Cloudflare's own field names).

    ClientCountry comes lower-case ("us") and is upper-cased. The request
    time is the edge's time to first byte when the job logs it, else the
    origin's response time; both are in milliseconds. A record without
    ClientRequestURI or EdgeStartTimestamp is not one Skald can count.
    """
    row = _json_object(line)
    if row is None or "ClientRequestURI" not in row or "EdgeStartTimestamp" not in row:
        return None
    try:
        when = _when(row["EdgeStartTimestamp"])
    except (ValueError, OverflowError, OSError):
        return None
    took = None
    for key in ("EdgeTimeToFirstByteMs", "OriginResponseDurationMs"):
        took = _duration(row.get(key), 1000)
        if took is not None:
            break
    status = row.get("EdgeResponseStatus")
    return Hit(
        when=when,
        address=_text(row.get("ClientIP")),
        host=_text(row.get("ClientRequestHost")),
        method=_text(row.get("ClientRequestMethod")),
        url=_text(row["ClientRequestURI"]),
        status="" if status is None else str(status),
        referrer=_text(row.get("ClientRequestReferer")),
        user_agent=_text(row.get("ClientRequestUserAgent")),
        country=_country(_text(row.get("ClientCountry")).upper()),
        request_time=took,
        size=_bytes(row.get("EdgeResponseBytes")),
        fmt="cloudflare_json",
    )


# -------------------------------------------------------------- cloudfront

# The legacy standard log's 33 fields, in order, as its "#Fields:" line names
# them. Older files stop earlier; only the ones read below have to be there.
CLOUDFRONT_FIELDS = (
    "date time x-edge-location sc-bytes c-ip cs-method cs(Host) cs-uri-stem "
    "sc-status cs(Referer) cs(User-Agent) cs-uri-query cs(Cookie) "
    "x-edge-result-type x-edge-request-id x-host-header cs-protocol cs-bytes "
    "time-taken x-forwarded-for ssl-protocol ssl-cipher "
    "x-edge-response-result-type cs-protocol-version fle-status "
    "fle-encrypted-fields c-port time-to-first-byte x-edge-detailed-result-type "
    "sc-content-type sc-content-len sc-range-start sc-range-end"
).split()

_REQUIRED = ("date", "time", "c-ip", "cs-method", "cs-uri-stem", "sc-status")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_TIME = re.compile(r"\d{2}:\d{2}:\d{2}")

# The header lines of a W3C extended log. read() skips them: they are not
# traffic, and counting them as unreadable would withhold a day built from
# many small CloudFront files.
W3C_HEADER = re.compile(r"#(Version|Fields|Software|Date|Remark):")


class CloudFront:
    """A CloudFront standard log reader: a callable, line -> Hit | None.

    It starts with the standard field order. Given a "#Fields:" line - by
    read(), which sees the file's headers, or by calling it with one - it
    reads the lines after it in that order instead, and returns None for the
    header itself. read() makes a fresh one for each read, so one file's
    header never leaks into another read. The shared one in PARSERS is made
    with follow=False: it always reads the standard order, whatever lines
    detect() or a caller hands it.
    """

    fmt = "cloudfront_w3c"

    def __init__(self, fields: list[str] | tuple[str, ...] = CLOUDFRONT_FIELDS,
                 follow: bool = True) -> None:
        self.follow = follow
        self.index: dict[str, int] = {}
        self._use(fields)

    def _use(self, fields) -> None:
        index = {name: i for i, name in enumerate(fields)}
        if all(name in index for name in _REQUIRED):
            self.index = index

    def header(self, line: str) -> None:
        """Take the field order from a "#Fields:" line; other headers are
        ignored. A "#Fields:" line without the fields Skald needs is ignored
        too, and the order before it stays."""
        text = line.strip()
        if self.follow and text.startswith("#Fields:"):
            self._use(text[len("#Fields:"):].split())

    def __call__(self, line: str) -> Hit | None:
        if line.startswith("#"):
            self.header(line)
            return None
        cols = line.rstrip("\r\n").split("\t")
        index = self.index

        def get(name: str) -> str:
            i = index.get(name)
            if i is None or i >= len(cols):
                return ""
            value = cols[i]
            return "" if value == "-" else value

        if any(index[name] >= len(cols) for name in _REQUIRED):
            return None
        day, clock, status = get("date"), get("time"), get("sc-status")
        if not (_DATE.fullmatch(day) and _TIME.fullmatch(clock)
                and re.fullmatch(r"\d{3}", status)):
            return None
        try:
            when = datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        query = get("cs-uri-query")
        url = get("cs-uri-stem") + (f"?{query}" if query else "")
        return Hit(
            when=when.replace(tzinfo=UTC),
            address=get("c-ip"),
            # cs(Host) is the distribution's dxxxx.cloudfront.net name; the
            # name the visitor asked for is the Host header.
            host=get("x-host-header") or get("cs(Host)"),
            method=get("cs-method"),
            url=url,
            status=status,
            # URL-encoded in the log, some characters twice: decode once.
            referrer=unquote(get("cs(Referer)")),
            user_agent=unquote(get("cs(User-Agent)")),
            country="",
            request_time=_duration(get("time-taken") or None, 1),
            size=_bytes(get("sc-bytes") or None),
            fmt=self.fmt,
            # Unique per request, so read() drops a line it has seen already:
            # the same log file synced or concatenated twice.
            rid=get("x-edge-request-id"),
        )


# ------------------------------------------------------------------ fastly

def _first(row: dict, *keys: str):
    for key in keys:
        value = row.get(key)
        if value not in (None, "", "-"):
            return value
    return None


def fastly(line: str) -> Hit | None:
    """One line of a JSON log format written in Fastly's VCL.

    The field names are Fastly's own recommended ones (docs/CDN-LOGS.md has
    the exact format) with the usual alternatives. time_elapsed is in
    microseconds, as Fastly's %D and time.elapsed.usec are; elapsed_ms and
    time_elapsed_ms are milliseconds. The country is kept only as a
    two-letter code: Fastly's own example logs client.geo.country_name, a
    full name, and a name is not turned into a code by guessing.

    A Caddy line (a "request" object), a Cloudflare one (ClientRequestURI),
    a Vercel drain record (a "proxy" object) or a Netlify one (log_type) is
    not read as Fastly's, so auto-detection tells them apart.
    """
    row = _json_object(line)
    if row is None or "ClientRequestURI" in row or "log_type" in row or \
            isinstance(row.get("request"), dict) or isinstance(row.get("proxy"), dict):
        return None
    stamp = _first(row, "timestamp", "time")
    url = _first(row, "url", "request_url")
    if url is None:
        path = _first(row, "path")
        if path is not None:
            query = str(_first(row, "query", "query_string") or "").lstrip("?")
            url = f"{path}?{query}" if query else str(path)
    if stamp is None or url is None:
        return None
    try:
        when = _when(stamp)
    except (ValueError, OverflowError, OSError):
        return None
    took = _duration(row.get("time_elapsed"), 10**6)
    if took is None:
        took = _duration(_first(row, "elapsed_ms", "time_elapsed_ms"), 1000)
    country = _text(_first(row, "geo_country", "country_code")).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2}", country):
        country = ""
    status = _first(row, "response_status", "status", "resp_status")
    return Hit(
        when=when,
        address=_text(_first(row, "client_ip")),
        host=_text(_first(row, "host")),
        method=_text(_first(row, "request_method", "method")),
        url=str(url),
        status="" if status is None else str(status),
        referrer=_text(_first(row, "request_referer", "referer")),
        user_agent=_text(_first(row, "request_user_agent", "user_agent")),
        country=_country(country),
        request_time=took,
        size=_bytes(_first(row, "response_body_size", "response_bytes", "bytes")),
        fmt="fastly_json",
    )
