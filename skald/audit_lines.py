"""The audit's own reader of log lines (audit.py): its own patterns for the
nginx extended and combined layouts (Apache's too), and the drain and Caddy
records through audit_drains.py. Moved out of audit.py whole, to keep that
file under the size limit; audit.py imports every name back, so
audit.line_hit, audit.Line and the rest are where they were.

Nothing here calls the package's parser (parse.py). The trailing
rsc_prefetch= field (Next.js's prefetch header, docs/INGEST.md) is read by
its own code (_prefetch), sharing only the documented token.
"""
from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import audit_drains

_EXTENDED = re.compile(
    r'^(\S+) (\S+) (\S+) "([^"]*)" (\d{3}) (\S+) "([^"]*)" "([^"]*)"'
    r'(?:\s+(\S+))?(?:\s+cc=(\S+))?')
_COMBINED = re.compile(
    r'^(\S+) \S+ \S+ \[([^\]]+)\] "([^"]*)" (\d{3}) (\S+) "([^"]*)" "([^"]*)"(.*)$')
# A combined line's last field, when it is quoted and a host name (a name with
# a letter and a dot; a port dropped). An address list or "-" is not one.
_LAST_QUOTED = re.compile(r'"([^"]*)"\s*$')
_REQUEST = re.compile(r"^([A-Z]+) (\S*)")
# Skald's own endpoints (script-tag events, its file, hooks, shipped logs): a
# POST to one is no form post.
_OWN = re.compile(r"/traffic-(?:beacon(?:$|[/?])|js/|hooks/|ingest/)")
# nginx's $request_id, the last field of the extended layout since it was
# added; older lines have none.
_RID = re.compile(r"\srid=([0-9A-Za-z-]{8,64})\s*$")
# The field a line ends with to record Next.js's Next-Router-Prefetch header
# (docs/INGEST.md): the documented token, written here again, not imported.
_PREFETCH_KEY = "rsc_prefetch="


@dataclass
class Line:
    when: datetime
    address: str
    host: str
    method: str
    url: str
    status: str
    referrer: str
    agent: str
    country: str
    rid: str = ""
    # Body bytes sent and the response time in seconds, when the line has
    # them (None: not logged). What each crawler costs (audit_crawler_cost).
    size: int | None = None
    seconds: float | None = None
    # The rsc_prefetch= field's value ("-": the header was not sent), or
    # None when the line has no such field (a Caddy line: its headers).
    prefetch: str | None = None
    # A page view of one click already counted (audit.same_click): not a page view.
    repeat: bool = False

    @property
    def path(self) -> str:
        return self.url.partition("?")[0]


def line_hit(raw: str) -> Line | None:
    """One log line, or None if no layout reads it: nginx's extended or
    combined (Apache's too), a Caddy JSON line, or a Vercel / Netlify drain
    record kept by the ingest endpoint (audit_drains, its own reader)."""
    if raw.lstrip().startswith("{"):
        got = audit_drains.fields(raw)
        return Line(**got) if got else None
    m = _EXTENDED.match(raw)
    if m:
        try:
            when = datetime.fromisoformat(m.group(1))
        except ValueError:
            when = None
        if when is not None:
            got = _line(when, m.group(2), m.group(3), m.group(4), m.group(5),
                        m.group(7), m.group(8), m.group(10))
            got.prefetch, rest = _prefetch(raw[m.end(8) + 1:].rstrip("\n"))
            rid = _RID.search(rest)
            got.rid = rid.group(1) if rid else ""
            got.size, got.seconds = _byte_count(m.group(6)), _secs(m.group(9))
            return got
    m = _COMBINED.match(raw)
    if m:
        try:
            when = datetime.strptime(m.group(2), "%d/%b/%Y:%H:%M:%S %z")
        except ValueError:
            return None
        prefetch, tail = _prefetch(m.group(8))
        got = _line(when, m.group(1), _named_host(tail), m.group(3), m.group(4),
                    m.group(6), m.group(7), None)
        got.size, got.seconds = _byte_count(m.group(5)), _tail_seconds(tail)
        got.prefetch = prefetch
        return got
    return None


def _prefetch(rest: str) -> tuple[str | None, str]:
    """(the value of the rsc_prefetch= field, the line's trailing part
    without it). The field is a word of its own (a space or the start
    before it) anywhere after the user agent; the first one is read. None
    when there is none: the line cannot tell a click from a prefetch."""
    start = 0
    while True:
        at = rest.find(_PREFETCH_KEY, start)
        if at < 0:
            return None, rest
        if at == 0 or rest[at - 1].isspace():
            break
        start = at + 1
    end = at + len(_PREFETCH_KEY)
    while end < len(rest) and not rest[end].isspace():
        end += 1
    return rest[at + len(_PREFETCH_KEY):end], rest[:at] + rest[end:]


def _byte_count(raw: str | None) -> int | None:
    """The size field: a whole number of bytes, or None ("-", absent)."""
    if not raw or not raw.isdigit():
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _secs(raw: str | None) -> float | None:
    """A response time in seconds: a number from 0 up to a day, else None."""
    try:
        value = float(raw) if raw else None
    except ValueError:
        return None
    return value if value is not None and 0 <= value < 86400 else None


def _tail_seconds(tail: str) -> float | None:
    """The combined layout's optional response time: the first field after
    the user agent, when it is digits with at most one decimal point and
    a space or the end after it."""
    if not tail[:1].isspace():
        return None
    first = tail.split(None, 1)[0] if tail.strip() else ""
    whole, dot, frac = first.partition(".")
    if not whole.isdecimal() or (dot and not frac.isdecimal()):
        return None
    return _secs(first)


def _named_host(tail: str) -> str:
    found = _LAST_QUOTED.search(tail or "")
    if not found or found.start() == 0 or not tail[found.start() - 1].isspace():
        return ""
    name = found.group(1).rsplit(":", 1)[0] if found.group(1).count(":") == 1 \
        else found.group(1)
    labels = name.split(".")
    if len(labels) < 2 or not any(c.isalpha() for c in name):
        return ""
    if not all(lab and all(c.isalnum() or c == "-" for c in lab) for lab in labels):
        return ""
    return name.lower()


def _line(when, address, host, request, status, referrer, agent, cc) -> Line:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    req = _REQUEST.match(request)
    cc = (cc or "").strip()
    return Line(when, address, host or "", req.group(1) if req else "",
                req.group(2) if req else "", status,
                "" if referrer == "-" else referrer, "" if agent == "-" else agent,
                "" if cc in ("", "-", "XX", "ZZ") else cc.upper())


def log_files(config: dict) -> list[Path]:
    """Every rotation of the log, oldest first: base.N.gz ... base.1, base."""
    logs = config.get("logs") or {}
    folder = Path(logs.get("dir") or "/var/log/nginx")
    base = str(logs.get("base") or "access.log")
    found = []
    for path in folder.glob(base + "*"):
        rest = path.name[len(base):]
        m = re.fullmatch(r"(?:\.(\d+))?(?:\.gz)?", rest)
        if m:
            found.append((-(int(m.group(1)) if m.group(1) else 0), path))
    return [p for _, p in sorted(found)]


def raw_lines(path: Path, upto: dict | None = None):
    """A file's text lines. `upto` ({file name: bytes}) is how far the live
    run read each plain file (the snapshot's `read_upto`): only the lines
    wholly inside that many bytes, so lines appended since are not counted.
    No limit (a day's audit, an older snapshot): the whole file."""
    limit = None if path.suffix == ".gz" else (upto or {}).get(path.name)
    if limit is None:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", errors="replace") as handle:
            yield from handle
        return
    left = int(limit)
    with open(path, "rb") as handle:
        while left > 0:
            raw = handle.readline(left)
            left -= len(raw)
            if not raw.endswith(b"\n"):
                return              # a line cut at the limit (or still being written)
            text = raw[:-1].decode("utf-8", "replace")
            yield (text[:-1] if text.endswith("\r") else text) + "\n"


def _read(paths, upto: dict | None = None):
    """Every readable line, without a second copy of any request id: a line
    repeating an earlier rid= is the same request written twice. `upto`:
    raw_lines."""
    rids = set()
    for path in paths:
        for raw in raw_lines(path, upto):
            got = line_hit(raw)
            if got is None:
                continue
            if got.rid:
                if got.rid in rids:
                    continue
                rids.add(got.rid)
            yield got
