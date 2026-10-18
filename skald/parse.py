"""Read access-log lines into a common record, whatever format they are in.

Nothing downstream knows which web server produced a line. Everything works on
the Hit below, so adding a format means adding a pattern here and nothing else.

Two fields decide almost every later question, so they are worth naming:

  referrer    where the visitor came from. This is the ONLY way to tell that a
              person arrived from an answer engine, because such a visitor runs
              an ordinary browser and nothing in their user agent says
              "ChatGPT sent me". It is frequently stripped, so it undercounts.

  user_agent  what the client claims to be. Self-reported and forgeable, which
              is why classify.py never treats it as proof of a human.

A country comes from the line when the server logged one (nginx's cc= from
a GeoIP module, Cloudflare's CF-IPCountry). A line without one is looked up
in the GeoIP database `logs.country_db` names (read(geo=...)), the same
DB-IP file such a module reads - a lookup, not a guess. With neither, the
country is "Unknown".
"""
from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


@dataclass(slots=True)
class Hit:
    """One request. The unit every later count is built from."""

    when: datetime
    address: str
    host: str
    method: str
    url: str
    status: str
    referrer: str
    user_agent: str
    country: str = ""
    # Seconds the server took to answer ($request_time), when the log has it.
    request_time: float | None = None
    # Body bytes sent, when the log has them ("-" or absent: None).
    size: int | None = None
    # The layout this line was read in (a PARSERS name). The old combined
    # format carries no host and no country; quality.json counts its lines.
    fmt: str = ""
    # A hash of the raw line (read() sets it): two lines with the same one
    # are byte-identical. Only compared within one run.
    line_id: int = 0
    # nginx's $request_id (the trailing rid= field), unique per request.
    # Empty for lines written before the log carried it.
    rid: str = ""

    @property
    def path(self) -> str:
        """The URL without its query string."""
        return self.url.split("?", 1)[0]

    @property
    def ok(self) -> bool:
        """Answered without an error: served, or pointed somewhere else."""
        return self.status[:1] in ("2", "3")

    @property
    def is_form_post(self) -> bool:
        """A POST the site's own pages sent (a form, an API call), not one to
        Skald's own endpoints: the script tag posts its events to
        /traffic-beacon from every page, which made every visit "form sent"."""
        return self.method == "POST" and not OWN_ENDPOINT.match(self.path)

    @property
    def is_page(self) -> bool:
        """A document a person could actually look at.

        This is the distinction that broke the citation count in the system this
        package was extracted from: a single visitor clicking through a
        React/Next site produces one HTML request and then dozens of payload
        and asset requests, every one of them carrying the same referrer.
        Counting requests instead of pages turned one visitor into "56 people".

        So: no framework payloads, no assets, no analytics beacons. Scanner
        probes are not filtered here - they are a question about who, not
        about what, and classify.py answers it by putting them in the bots
        group whatever user agent they send.

        A redirect is not a page either, and this is worth stating because it
        is the same mistake in a quieter form. A 301 sends the browser
        somewhere else; the page it lands on is logged separately as its own
        200. Counting the 3xx as well counts that read twice. On the reference
        log it was 3,993 of 15,727 claimed views - 25% - almost all of them
        301 and 308 trailing-slash redirects.

        A 304 is not a redirect: it tells the browser its cached copy is
        current, and the browser shows that copy. It is a page view, of a
        returning reader, and the first page of a visit carries the visit's
        source. Counted as anything else, a reader coming back from a search
        to a page they had cached lost their source to the next page they
        opened ("This site"), or was no reader at all.
        """
        if (self.status[:1] != "2" and self.status != "304") or \
                self.method not in ("GET", "HEAD"):
            return False
        if RSC_PAYLOAD.search(self.url):
            return False
        if ASSET.search(self.path) or BEACON.search(self.path):
            return False
        return True


# Skald's own endpoints on the site's server: the script tag's events and its
# file, signed hooks, shipped logs. A POST to one is no form being sent.
OWN_ENDPOINT = re.compile(r"^/traffic-(?:beacon(?:$|[/?])|js/|hooks/|ingest/)")


# Next.js/React Server Components fetch a payload for the page you clicked.
# Other frameworks have their own: add them here rather than in the classifier.
RSC_PAYLOAD = re.compile(r"[?&](_rsc|__flight__|_data)=", re.I)

# Files, not pages. Release 2 added the ones the real log showed being
# counted as page views (/sitemap.xsl, 4 people "pages" in a day) and their
# kin: stylesheets for feeds, feeds, documents, archives and media. A PDF is
# a download, not a page read.
ASSET = re.compile(
    r"\.(css|js|mjs|map|png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|eot|txt|xml|json|webmanifest"
    r"|xsl|xslt|rss|atom|csv|tsv|pdf|zip|gz|tgz|rar|7z|mp4|webm|mov|mp3|wav|ogg|m4a"
    r"|docx?|xlsx?|pptx?|wasm)$"
    r"|^/_next/|^/static/|^/assets/|^/_nuxt/|^/build/",
    re.I,
)

# Endpoints a page calls while you read it. They are evidence of a visit, never
# a visit of their own. Everything under /api/ is one: a site's JSON API
# (/api/v1/jobs/..., /api/search) answers a page's script, and counted as a
# page it showed up as where visits ended and as steps between pages.
BEACON = re.compile(r"^/(?:api(?:/|$)|(?:__analytics|collect|beacon|ping)\b)", re.I)


# $time_iso8601 $remote_addr $host "$request" $status $bytes "$ref" "$ua" $rt cc=XX ray=... rid=...
NGINX_EXTENDED = re.compile(
    r'^(?P<when>\S+) (?P<address>\S+) (?P<host>\S+) '
    r'"(?P<request>[^"]*)" '
    r'(?P<status>\d{3}) (?P<size>\S+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
    r'(?:\s+(?P<request_time>\S+))?(?:\s+cc=(?P<country>\S+))?'
)

# The request id nginx gives every request ($request_id, 32 hex characters),
# logged last as rid=. Read on its own so a line with an empty or odd field
# before it still yields it. Lines from before it was added have none.
RID = re.compile(r"\srid=([0-9A-Za-z-]{8,64})\s*$")

# The stock combined format, used by nginx and Apache alike. Many servers add
# fields after it; two are read when present: a response time right after the
# user agent ($request_time), and a quoted host name as the very last field
# ("$host"), e.g.  ... "Mozilla/5.0 ..." 0.010 0.010 "<the host name>".
COMBINED = re.compile(
    r'^(?P<address>\S+) \S+ \S+ \[(?P<when>[^\]]+)\] '
    r'"(?P<request>[^"]*)" '
    r'(?P<status>\d{3}) (?P<size>\S+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
    r'(?:\s+(?P<request_time>\d+(?:\.\d+)?)(?=\s|$))?(?P<tail>.*)'
)
# The last quoted field, when it is a host name: letters in it, dots between
# labels, an optional :port. A quoted address list ("$http_x_forwarded_for"
# in many layouts) or "-" is not one, and leaves the host empty, as before.
TAIL_HOST = re.compile(r'\s"(?P<host>(?=[^"]*[A-Za-z])[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)'
                       r'(?::\d+)?"\s*$')


def _when_iso(raw: str) -> datetime:
    return datetime.fromisoformat(raw)


def _when_clf(raw: str) -> datetime:
    # 06/Oct/2026:23:15:19 +0000
    return datetime.strptime(raw, "%d/%b/%Y:%H:%M:%S %z")


# "GET /path HTTP/1.1". Anything else in the request field - empty, when a
# client connects and sends nothing; bytes, when TLS is spoken to port 80 -
# is still a request the server answered (with a 400), so it is kept, with
# no method and no path. It used to fail the whole line, and those requests
# vanished from the count.
REQUEST = re.compile(r"^(?P<method>[A-Z]+) (?P<url>\S*)")


def _seconds(raw: str | None) -> float | None:
    """$request_time, or None when the field is absent or is not a number -
    the one field before cc= is free-form in other layouts."""
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if 0 <= value < 86400 else None


def _size(raw: str | None) -> int | None:
    return int(raw) if raw and raw.isdigit() else None


def _country(raw: str) -> str:
    """XX is Cloudflare's "unknown", ZZ that of DB-IP and other GeoIP
    databases. Either way: no country, never a guessed one. Every format
    goes through this, the CDN ones too."""
    country = (raw or "").strip()
    return "" if country in ("", "-", "XX", "ZZ") else country


def _from_match(m: re.Match, when: datetime, fmt: str = "") -> Hit:
    got = m.groupdict()
    rid = RID.search(m.string) if fmt == "nginx_extended" else None
    request = REQUEST.match(got["request"])
    host = got.get("host", "") or ""
    if not host and got.get("tail"):
        found = TAIL_HOST.search(got["tail"])
        host = found.group("host").lower() if found else ""
    return Hit(
        when=when,
        address=got["address"],
        host=host,
        method=request.group("method") if request else "",
        url=request.group("url") if request else "",
        status=got["status"],
        referrer="" if got["referrer"] in ("-", "") else got["referrer"],
        user_agent="" if got["user_agent"] == "-" else got["user_agent"],
        country=_country(got.get("country") or ""),
        request_time=_seconds(got.get("request_time")),
        size=_size(got.get("size")),
        fmt=fmt,
        rid=rid.group(1) if rid else "",
    )


def _caddy(line: str) -> Hit | None:
    """Caddy's JSON access log. `client_ip` is the client once Caddy has
    trusted proxies (remote_ip is then the proxy); older Caddy logs only
    remote_ip. A record with no address, no URI or no three-digit status is
    not a request this counts (the nginx patterns cannot match one either)."""
    try:
        row = json.loads(line)
        req = row["request"]
        headers = {k.lower(): v for k, v in (req.get("headers") or {}).items()}

        def header(name: str) -> str:
            got = headers.get(name)
            return ((got[0] if got else "") if isinstance(got, list) else got) or ""

        address = str(req.get("client_ip") or req.get("remote_ip") or "").strip()
        status = row.get("status")
        if (not address or not req.get("uri") or isinstance(status, bool)
                or not re.fullmatch(r"\d{3}", str(status).strip())):
            return None
        return Hit(
            when=datetime.fromtimestamp(row["ts"], tz=timezone.utc),
            address=address,
            host=re.sub(r":\d+$", "", str(req.get("host") or "")) if "]" not in str(
                req.get("host") or "") else str(req.get("host")),
            method=req.get("method", ""),
            url=req.get("uri", ""),
            status=str(status).strip(),
            referrer=header("referer"),
            user_agent=header("user-agent"),
            country=_country(header("cf-ipcountry")),
            size=row.get("size") if isinstance(row.get("size"), int) else None,
            fmt="caddy_json",
        )
    except (ValueError, KeyError, TypeError):
        return None


def _line_parser(pattern: re.Pattern, when, fmt: str):
    """A line parser that returns None, never raises, for a line it cannot
    read - including one shaped right whose timestamp is not a timestamp."""
    def parse(line: str) -> Hit | None:
        m = pattern.match(line)
        if not m:
            return None
        try:
            return _from_match(m, when(m.group("when")), fmt)
        except (ValueError, OverflowError):
            return None
    return parse


# The CDN formats live in their own module; it imports Hit and the helpers
# above, which is why this import sits here and not at the top.
from .parse_cdn import W3C_HEADER, CloudFront, cloudflare, fastly  # noqa: E402
from .parse_drains import edge, netlify, vercel  # noqa: E402

PARSERS = {
    "nginx_extended": _line_parser(NGINX_EXTENDED, _when_iso, "nginx_extended"),
    "nginx_combined": _line_parser(COMBINED, _when_clf, "nginx_combined"),
    "caddy_json": _caddy,
    "cloudflare_json": cloudflare,
    "cloudfront_w3c": CloudFront(follow=False),
    "fastly_json": fastly,
    "vercel_json": vercel,
    "netlify_json": netlify,
    "edge_json": edge,
}
PARSERS["apache_combined"] = PARSERS["nginx_combined"]

# Richest first: the extended format carries a country, so prefer it when both
# would match. No two of these read the same line - the JSON ones are told
# apart by their key names, CloudFront by its tabs - so the order only
# settles a sample none of them reads.
AUTO_ORDER = ["nginx_extended", "nginx_combined", "caddy_json",
              "cloudflare_json", "fastly_json", "cloudfront_w3c",
              "vercel_json", "netlify_json", "edge_json"]


def detect(sample: list[str]) -> str:
    """Pick the format that parses the most of these lines, richest first.
    W3C header lines ("#Fields: ...") are not lines of any format."""
    sample = [line for line in sample if not W3C_HEADER.match(line)]
    best, best_score = "nginx_extended", -1
    for name in AUTO_ORDER:
        parse_one = PARSERS[name]
        score = sum(1 for line in sample if parse_one(line))
        if score > best_score:
            best, best_score = name, score
    return best


def log_files(directory: Path, base: str, days: int) -> list[Path]:
    """The access log plus as many rotations as `days` covers.

    Rotations are <base>.1 uncompressed and <base>.N.gz beyond that. Only two
    being uncompressed is why this is easy to mistake for two days of history;
    on a Debian/Ubuntu default there are fourteen.
    """
    found = [directory / base]
    if days >= 2:
        found.append(directory / f"{base}.1")
    for n in range(2, max(days, 2)):
        found.append(directory / f"{base}.{n}.gz")
    return [p for p in found if p.exists()]


_ROTATION = re.compile(r"\.(\d+)(\.gz)?$")


def oldest_first(paths: list[str] | list[Path]) -> list[Path]:
    """Rotations in the order their lines were written: <base>.N.gz ... .1,
    then <base>.

    Sessions are counted as hits arrive, so reading the newest file first
    split every visit that ran across a rotation in two: a reader at 06:20
    and 06:40 either side of a 06:25 rotation was seen at 06:40, then 06:20
    an hour of later lines afterwards, and counted twice. Files that are not
    numbered rotations keep their modification-time order.
    """
    def key(path: Path):
        m = _ROTATION.search(path.name)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0
        return (-(int(m.group(1)) if m else 0), mtime)
    return sorted((Path(p) for p in paths), key=key)


class ReadStats:
    """What read() saw: every non-blank line, and those no format parsed.

    An unreadable line has no timestamp, so `placed` records where each one
    sits in time: the timestamp of the readable line just before it in the
    same file, or - at the start of a file - just after it. None for a file
    with no readable line at all. That is what lets a window count only the
    unreadable lines among its own.
    """

    def __init__(self) -> None:
        self.lines = 0
        self.unparsed = 0
        self.placed: list = []
        # When each line dropped as a repeat of an earlier request id was
        # written (read() never yields those).
        self.removed: list = []

    def in_window(self, start, end) -> int:
        """Unreadable lines placed in [start, end); unplaceable ones count."""
        n = 0
        for when in self.placed:
            if when is None:
                n += 1
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if start <= when < end:
                n += 1
        return n

    def removed_in(self, start, end) -> int:
        """Lines dropped as repeated request ids, written in [start, end)."""
        return sum(1 for when in self.removed
                   if start <= (when if when.tzinfo else when.replace(tzinfo=timezone.utc)) < end)


def geo_database(config: dict) -> str | None:
    """The GeoIP file a site's lines are looked up in, or None."""
    from .conversions.geo import database
    return database(config)


def _country_filler(path: str | None):
    """address -> country code or "", cached; None without a file."""
    if not path:
        return None
    from .conversions.geo import country
    seen: dict[str, str] = {}

    def fill(address: str) -> str:
        got = seen.get(address)
        if got is None:
            got = seen[address] = _country(country(path, address) or "")
        return got
    return fill


def sizes(paths) -> dict[str, int]:
    """Each plain (uncompressed) file's size in bytes now, by file name.

    A live run takes them at its start and reads each file only that far
    (read's `upto`), and records them, so the live audit reads the very same
    bytes however many lines the shipper appends meanwhile. A compressed
    rotation is not written to any more and is always read whole."""
    out = {}
    for path in (Path(p) for p in paths):
        if path.suffix == ".gz":
            continue
        try:
            out[path.name] = path.stat().st_size
        except OSError:
            pass
    return out


def lines_of(path: Path, upto: dict | None = None) -> Iterator[str]:
    """A log file's lines. With a byte limit for it in `upto` (sizes()),
    only the whole lines in its first that many bytes: a line still being
    written at the limit is not read."""
    limit = (upto or {}).get(path.name) if path.suffix != ".gz" else None
    if limit is None:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", errors="replace") as handle:
            yield from handle
        return
    left = int(limit)
    with open(path, "rb") as handle:
        for raw in handle:
            left -= len(raw)
            if left < 0 or not raw.endswith(b"\n"):
                return
            text = raw.decode("utf-8", "replace")
            yield text[:-2] + "\n" if text.endswith("\r\n") else text


def read(paths: list[str] | list[Path], fmt: str = "auto",
         stats: ReadStats | None = None, geo: str | None = None,
         upto: dict | None = None) -> Iterator[Hit]:
    """Every parsable hit in these files. Unparsable lines are skipped.

    A line that will not parse is not an error worth stopping for - logs
    contain truncated writes and the occasional binary probe - but a format
    that parses nothing at all is, and the caller can see that from the count.

    With "auto", a line the detected format rejects is tried against the
    others before it is dropped. One file often holds two formats: the day
    the log_format changed, the lines before the reload are in the old one.
    Detection samples the start of the file, so without the fallback every
    line after the change was silently discarded - on a real changeover,
    exactly the lines in the new, richer format.

    Pass `stats` to learn how many lines were dropped. They used to vanish
    without a count; now every report states it and verify fails above a
    threshold, because a format that quietly stops matching looks exactly
    like a quiet day.

    A line whose request id (rid=) was already read in this call is the same
    request written twice: it is dropped, never yielded, and `stats.removed`
    records it. A request id is unique per request, so this never drops a
    real repeat. Lines without one (the log before it was added) are all
    yielded, as before; quality.Duplicates still flags their exact repeats.

    W3C header lines (#Version:, #Fields:, #Software:, #Date:, #Remark:)
    are skipped and counted nowhere: not lines, not unparsed. CloudFront
    starts every file with two, and a day built from many small files would
    otherwise be withheld for them. A #Fields: line sets the field order the
    CloudFront reader uses for the lines after it, in this read only.

    `geo` is a GeoIP .mmdb file (geo_database(config)): a hit whose line
    carries no country gets the one its address is in there. The line's own
    country always wins. Each address is looked up once per read.

    `upto` ({file name: bytes}, sizes()) reads each plain file named in it
    only up to that many bytes (lines_of): the live run's same bytes.
    """
    paths = [Path(p) for p in paths]
    fill = _country_filler(geo)
    auto = fmt == "auto"
    # A CloudFront reader of this read's own, so it can follow #Fields: lines.
    parsers = dict(PARSERS)
    cloudfront = parsers["cloudfront_w3c"] = CloudFront()
    if auto:
        sample: list[str] = []
        for path in paths:
            lines = lines_of(path, upto)
            for line in lines:
                if W3C_HEADER.match(line):
                    continue
                sample.append(line)
                if len(sample) >= 200:
                    break
            lines.close()
            if sample:
                break
        fmt = detect(sample) if sample else "nginx_extended"

    parse_one = parsers[fmt]
    if auto:
        first = parse_one
        others = [parsers[name] for name in AUTO_ORDER if parsers[name] is not first]

        def parse_one(line: str) -> Hit | None:
            hit = first(line)
            if hit is None:
                for other in others:
                    hit = other(line)
                    if hit is not None:
                        break
            return hit

    rids: set[str] = set()
    for path in paths:
        last = None          # timestamp of the last readable line in this file
        waiting = 0          # unreadable lines before the first readable one
        for line in lines_of(path, upto):
            if W3C_HEADER.match(line):
                cloudfront.header(line)
                continue
            hit = parse_one(line)
            if stats is not None and line.strip():
                stats.lines += 1
                if hit is None:
                    stats.unparsed += 1
                    if last is None:
                        waiting += 1
                    else:
                        stats.placed.append(last)
            if hit is not None and hit.rid:
                if hit.rid in rids:
                    if stats is not None:
                        stats.removed.append(hit.when)
                    continue
                rids.add(hit.rid)
            if hit is not None:
                if fill is not None and not hit.country:
                    hit.country = fill(hit.address)
                hit.line_id = hash(line.rstrip("\n"))
                if waiting:
                    stats.placed.extend([hit.when] * waiting)
                    waiting = 0
                last = hit.when
                yield hit
        if stats is not None and waiting:
            stats.placed.extend([None] * waiting)
