"""Read log-drain records: Vercel Log Drains and Netlify Log Drains (traffic).

A site on Vercel or Netlify has no access log of its own to read. Both
platforms can post their request logs to an HTTPS endpoint instead (a "log
drain"); Skald's ingest endpoint takes them (ingest_drain.py) and keeps one
JSON object a line, cut down to the fields below. These readers turn such a
line into the same Hit the server formats produce, so nothing downstream
changes. A full record, as the platform sent it, reads the same.

  vercel_json   a Vercel Log Drains record with a `proxy` object (a request
                the edge answered). Fields, checked 2026-10-11:
                https://vercel.com/docs/drains/reference/logs
  netlify_json  a Netlify Log Drains traffic record (`log_type: traffic`).
                Fields, checked 2026-10-11:
                https://docs.netlify.com/manage/monitoring/log-drains/

A record without the client's address is not read: Vercel's "IP addresses
are hidden in your Drains" and Netlify's "Exclude personally identifiable
information" leave it out, and without it every person would be one
visitor. Unknown stays unknown: such a line is unreadable, and counted so.

The independent audit reads these lines with its own code (audit_drains.py).
"""
from __future__ import annotations

import re

from .parse import Hit, _country
from .parse_cdn import _bytes, _duration, _json_object, _text, _when


def _status(value) -> str:
    """A status code as the log writes it: three digits, else ""."""
    if isinstance(value, bool) or value is None:
        return ""
    text = str(value).strip()
    return text if re.fullmatch(r"\d{3}", text) else ""


# ------------------------------------------------------------------ vercel

def _agent(value) -> str:
    """proxy.userAgent is documented as an array of strings; a plain string
    is read too. The first non-empty one is the request's user agent."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item:
                return item
        return ""
    return _text(value)


def vercel(line: str) -> Hit | None:
    """One Vercel log drain record with a `proxy` object.

    proxy.timestamp (Unix milliseconds) is when the edge took the request;
    the record's own `timestamp` is used only when it is missing.
    proxy.statusCode -1 is a revalidation Vercel ran in the background, not
    a request anyone made: not read. The status falls back to the record's
    `statusCode` (-1 there: the function crashed; no status, not read).
    The request id (requestId, else proxy.vercelId, else the entry's id)
    drops a request whose records came in twice, as read() does for nginx's
    $request_id: a function that logs three lines sends three records.
    `proxy.region` is Vercel's data centre, not the visitor's country:
    a Vercel record carries no country.
    """
    row = _json_object(line)
    if row is None:
        return None
    proxy = row.get("proxy")
    if not isinstance(proxy, dict):
        return None
    path = proxy.get("path")
    address = _text(proxy.get("clientIp")).strip()
    if not isinstance(path, str) or not path or not address:
        return None
    stamp = proxy.get("timestamp")
    if stamp is None:
        stamp = row.get("timestamp")
    try:
        when = _when(stamp)
    except (ValueError, OverflowError, OSError):
        return None
    status = proxy.get("statusCode")
    if status is None:
        status = row.get("statusCode")
    status = _status(status)
    if not status:
        return None
    rid = row.get("requestId") or proxy.get("vercelId") or row.get("id") or ""
    return Hit(
        when=when,
        address=address,
        host=_text(proxy.get("host")),
        method=_text(proxy.get("method")),
        url=path,
        status=status,
        referrer=_text(proxy.get("referer")),
        user_agent=_agent(proxy.get("userAgent")),
        country="",
        request_time=None,
        size=_bytes(proxy.get("responseByteSize")),
        fmt="vercel_json",
        rid=str(rid)[:128],
    )


# ----------------------------------------------------------------- netlify

_ABSOLUTE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://(?P<host>[^/?#]*)(?P<rest>.*)$")


def _url(raw: str) -> tuple[str, str]:
    """(host, path and query) from Netlify's `url`, "URL of the request".
    An absolute URL gives its host (without a port or user part) and the
    rest; a path is kept as it is, with no host. A fragment is dropped."""
    m = _ABSOLUTE.match(raw)
    if not m:
        return "", raw.split("#", 1)[0]
    host = m.group("host").rpartition("@")[2]
    if host.startswith("["):
        host = host[1:].split("]", 1)[0]
    else:
        host = host.split(":", 1)[0]
    path, _, query = m.group("rest").split("#", 1)[0].partition("?")
    return host.lower(), (path or "/") + (f"?{query}" if query else "")


def netlify(line: str) -> Hit | None:
    """One Netlify log drain traffic record (`log_type` "traffic").

    timestamp is RFC 3339; duration is in milliseconds; country is an ISO
    3166-1 two-letter code; request_id is Netlify's id for the request and
    drops a record that came in twice. Function, edge-function and deploy
    records have another log_type and are not read.
    """
    row = _json_object(line)
    if row is None or row.get("log_type") != "traffic":
        return None
    raw = row.get("url")
    address = _text(row.get("client_ip")).strip()
    if not isinstance(raw, str) or not raw or not address:
        return None
    try:
        when = _when(row.get("timestamp"))
    except (ValueError, OverflowError, OSError):
        return None
    status = _status(row.get("status_code"))
    if not status:
        return None
    host, url = _url(raw)
    country = _text(row.get("country")).strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        country = ""
    return Hit(
        when=when,
        address=address,
        host=host,
        method=_text(row.get("method")),
        url=url,
        status=status,
        referrer=_text(row.get("referrer")),
        user_agent=_text(row.get("user_agent")),
        country=_country(country),
        request_time=_duration(row.get("duration"), 1000),
        size=_bytes(row.get("response_size")),
        fmt="netlify_json",
        rid=_text(row.get("request_id"))[:128],
    )
