"""A dry run for a log source: can Skald read it, and what would it count?

Someone adding a site, or a new log source (a server's nginx or Apache log,
Caddy's JSON, a CDN or host export: Cloudflare, CloudFront, Fastly, Akamai,
Vercel, Netlify), used to learn only after the next daily run whether Skald
could read it. This reads a sample and says so at once. Nothing is stored:
no history, no state, no spool. `skald try-log` (try_log_cli.py) and
Settings > Collect data > Send logs' "Test a sample" (connections_api.try_sample) both
call dry_run() on the sample's lines.

It reads with the real readers (parse.PARSERS, in parse.AUTO_ORDER) and
counts with the real pipeline (window.analyse_paths: the same two passes,
the same Classifier, the same host filter as a daily run), over a private
temporary copy of the sample that is removed before dry_run returns. The
only code of its own is the diagnosis of a line no reader takes
(`why_unread`): which layout it looks like and which field failed. It never
returns a raw line: lines are named by number, an IP address in a host or a
path is masked.

The arithmetic is the usual rule (CLASSIFICATION.md): the five groups add
up to the site's requests, and the site's requests, the other hosts' and
the unreadable lines add up to the lines read.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classify import BROWSER, COMPATIBLE, OTHER_BOT, Group
from .parse import ASSET, AUTO_ORDER, PARSERS, W3C_HEADER, CloudFront

SAMPLE_LINES = 500          # the CLI's default sample
MOST_LINES = 100_000        # the CLI's ceiling
WEB_LINES = 200             # the dashboard's pasted sample
WEB_BYTES = 256 * 1024
EXAMPLES = 3                # line numbers shown per reason
FORMATS = ("auto", *sorted(PARSERS))

GROUP_LABELS = {Group.PEOPLE: "Real people", Group.ANSWER_ENGINE: "Answer engines",
                Group.SEARCH_ENGINE: "Search engines", Group.BOTS: "Bots and scanners",
                Group.OURS: "Our own traffic"}


class SampleError(ValueError):
    """The file cannot be read at all: the words say why."""


# ------------------------------------------------------------ the sample

def sample_file(path, lines: int = SAMPLE_LINES) -> list[str]:
    """The first `lines` lines of a plain or gzip file (told apart by its
    first bytes, not its name), W3C header lines kept on top. Raises
    SampleError with plain words when the file cannot be read."""
    p = Path(path)
    if not p.exists():
        raise SampleError(f"There is no file at {path}.")
    if p.is_dir():
        raise SampleError(f"{path} is a folder. Name the log file in it, e.g. {p / 'access.log'}.")
    try:
        with open(p, "rb") as handle:
            magic = handle.read(2)
        opener = gzip.open if magic == b"\x1f\x8b" else open
        out: list[str] = []
        content = 0
        with opener(p, "rt", errors="replace") as handle:
            for line in handle:
                if "\x00" in line:
                    raise SampleError(f"{p.name} is not a text file (it holds binary bytes).")
                out.append(line)
                if line.strip() and not W3C_HEADER.match(line):
                    content += 1
                    if content >= lines:
                        break
        return out
    except PermissionError:
        raise SampleError(f"Skald may not read {path}: permission denied. Run it as a user "
                          "who can read the log (on Docker the container's own user).") from None
    except (EOFError, gzip.BadGzipFile, OSError) as why:
        if isinstance(why, SampleError):
            raise
        raise SampleError(f"{p.name} looks like a gzip file but cannot be unpacked "
                          f"(cut short or damaged: {type(why).__name__}).") from None


def sample_text(text: str, lines: int = WEB_LINES) -> list[str]:
    """A pasted sample's first `lines` content lines."""
    out, content = [], 0
    for line in str(text or "").splitlines():
        out.append(line + "\n")
        if line.strip() and not W3C_HEADER.match(line):
            content += 1
            if content >= lines:
                break
    return out


# ------------------------------------------------------ why a line fails

ERROR_LOG = re.compile(r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[(?:debug|info|notice|warn|error"
                       r"|crit|alert|emerg)\]")
APACHE_ERROR = re.compile(r"^\[[A-Z][a-z]{2} [A-Z][a-z]{2} [ \d]\d [\d:.]+ \d{4}\] \[(?:[a-z_]+:)?"
                          r"(?:debug|info|notice|warn|error|crit|alert|emerg|trace\d)\]")
ISO_START = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
CLF_START = re.compile(r"^\S+ \S+ \S+ \[")
# The fields of the two plain layouts, in order: the first that does not
# match is the field that failed.
_Q = r'"(?:[^"\\]|\\.)*"'
COMBINED_STEPS = (("address", r"\S+ "), ("identity", r"\S+ "), ("user", r"\S+ "),
                  ("time", r"\[\d{2}/[A-Z][a-z]{2}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4}\] "),
                  ("request", _Q + " "), ("status", r"\d{3} "), ("bytes", r"\S+"),
                  ("referrer", " " + _Q), ("user agent", " " + _Q))
EXTENDED_STEPS = (("time", r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})? "),
                  ("address", r"\S+ "), ("host", r"\S+ "), ("request", _Q + " "),
                  ("status", r"\d{3} "), ("bytes", r"\S+ "), ("referrer", _Q + " "),
                  ("user agent", _Q))


def _failed_field(line: str, steps) -> str | None:
    at = 0
    for name, pattern in steps:
        m = re.compile(pattern).match(line, at)
        if not m:
            return name
        at = m.end()
    return None


def why_unread(line: str) -> tuple[str, str]:
    """(a short key, plain words) for a line no reader takes. Never the
    line itself: only the layout it looks like and the field that failed."""
    text = line.rstrip("\r\n")
    if ERROR_LOG.match(text) or APACHE_ERROR.match(text):
        return "error_log", "an error-log line, not an access-log line"
    if len(text.strip()) < 16:
        return "short", "too short to be a request (a line cut off?)"
    if text.lstrip().startswith("{"):
        try:
            row = json.loads(text)
        except ValueError:
            return "json_broken", "JSON, but cut short or broken"
        if not isinstance(row, dict):
            return "json_unknown", "JSON, but not an object"
        keys = ", ".join(sorted(str(k) for k in row)[:8])
        return "json_unknown", f"JSON with fields no reader knows ({keys})"
    if "\t" in text and text.count("\t") >= 5:
        return "tabs", (f"tab-separated with {text.count(chr(9)) + 1} fields (a CloudFront "
                        "line?), but not in CloudFront's order and no #Fields line fits")
    if ISO_START.match(text):
        field = _failed_field(text, EXTENDED_STEPS)
        return f"extended:{field}", (f"starts with an ISO time like Skald's extended layout, "
                                     f"but the {field} field is not as expected")
    if CLF_START.match(text):
        field = _failed_field(text, COMBINED_STEPS)
        if field == "referrer" and re.match(r'^\S+ \S+ \S+ \[[^\]]+\] ' + _Q + r' \d{3} \S+\s*$', text):
            return "common", ("the common log format: no referrer and no user agent "
                              "(Skald needs the combined format)")
        if field is None:
            return "combined", "shaped like the combined format, but a field holds an odd value"
        return f"combined:{field}", (f"shaped like the combined format, but the {field} field "
                                     "is not as expected")
    return "other", "a layout no reader knows"


# ---------------------------------------------------------------- reading

def _reader(name: str):
    """A reader of its own (CloudFront follows #Fields: lines)."""
    return CloudFront() if name == "cloudfront_w3c" else PARSERS[name]


def candidates(lines: list[str]) -> list[dict]:
    """[{format, read}] for every reader, most lines first, ties in
    AUTO_ORDER (richest first), as parse.detect settles them."""
    got = []
    for name in AUTO_ORDER:
        read_one, n = _reader(name), 0
        for line in lines:
            if W3C_HEADER.match(line):
                if name == "cloudfront_w3c":
                    read_one.header(line)
                continue
            if line.strip() and read_one(line) is not None:
                n += 1
        got.append({"format": name, "read": n})
    return sorted(got, key=lambda c: -c["read"])


def _sure(best: int, second: int, total: int) -> str:
    if best == 0:
        return "none"
    if best >= 0.95 * total and second <= 0.1 * best:
        return "sure"
    if second >= 0.5 * best:
        return "unsure"
    return "likely"


def _line_pass(lines: list[str], fmt: str, picked: str | None):
    """Each content line read as parse.read reads it (with "auto", the
    picked reader first, then every other): (hits, unread [(n, key, words)],
    {other format: lines})."""
    first = _reader(fmt if fmt != "auto" else (picked or AUTO_ORDER[0]))
    others = [] if fmt != "auto" else [_reader(n) for n in AUTO_ORDER
                                       if n != (picked or AUTO_ORDER[0])]
    hits, unread, layouts = [], [], Counter()
    for number, line in enumerate(lines, 1):
        if W3C_HEADER.match(line):
            for one in [first, *others]:
                if isinstance(one, CloudFront):
                    one.header(line)
            continue
        if not line.strip():
            continue
        hit = first(line)
        if hit is None:
            for other in others:
                hit = other(line)
                if hit is not None:
                    layouts[hit.fmt or "another layout"] += 1
                    break
        if hit is None:
            key, words = why_unread(line)
            if fmt != "auto":
                for name in AUTO_ORDER:
                    if name != fmt and _reader(name)(line) is not None:
                        key, words = f"layout:{name}", f"in the {name} layout, not {fmt}"
                        break
            unread.append((number, key, words))
        else:
            hits.append(hit)
    return hits, unread, dict(layouts)


def _count(lines: list[str], fmt: str, config: dict):
    """The real pipeline over a private temporary copy of the sample."""
    from .window import analyse_paths
    with tempfile.TemporaryDirectory(prefix="skald-try-") as folder:
        path = Path(folder) / "sample.log"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as handle:
            handle.writelines(line if line.endswith("\n") else line + "\n" for line in lines)
        return analyse_paths(config, [path], top=25, fmt=fmt)


# ---------------------------------------------------------------- masking

_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6 = re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])")
_EMAIL = re.compile(r"[^\s/?&=@]+@[^\s/?&=@]+")


def mask(text: str) -> str:
    """An IP address or an email in a host or a path, masked."""
    text = _EMAIL.sub("(an email)", str(text))
    text = _IPV4.sub("(an IP address)", text)
    return _IPV6.sub(lambda m: "(an IP address)" if m.group(0).count(":") >= 2 and
                     re.search(r"[0-9A-Fa-f]", m.group(0)) else m.group(0), text)


# ---------------------------------------------------------------- the run

def _zone_of(when: datetime) -> str:
    if when.tzinfo is None:
        return "none written (read as UTC)"
    off = when.utcoffset() or timedelta(0)
    if not off:
        return "UTC"
    minutes = int(off.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"UTC{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def dry_run(lines: list[str], fmt: str = "auto", config: dict | None = None,
            site: str | None = None, site_known: bool = False,
            now: datetime | None = None) -> dict:
    """The report, as data (try_log_cli.render words it; the dashboard draws
    it). `config` is the site's config when known (its hosts, own traffic,
    page assets, time zone); `site` a host name to judge the lines against."""
    from .config import setting
    from .verify import check
    from .window import zone
    if fmt not in FORMATS:
        raise SampleError(f"{fmt} is not a format Skald reads. Choose one of: {', '.join(FORMATS)}.")
    config = json.loads(json.dumps(config or {}, default=str))
    site = (site or "").strip().lower() or None
    hosts = [str(h).lower() for h in (setting(config, "site", "hosts") or [])]
    if site and not site_known:
        config.setdefault("site", {})["hosts"] = hosts = [site]
    now = now or datetime.now(timezone.utc)
    content = [line for line in lines if line.strip() and not W3C_HEADER.match(line)]
    report: dict = {"lines": len(content), "headers": sum(1 for x in lines if W3C_HEADER.match(x)),
                    "site": site, "site_known": site_known, "hosts_wanted": hosts,
                    "warnings": [], "notes": []}
    tried = candidates(lines)
    best = tried[0]["read"] if tried else 0
    second = tried[1]["read"] if len(tried) > 1 else 0
    picked = tried[0]["format"] if best else None
    configured = str(setting(config, "logs", "format", "auto") or "auto")
    report["format"] = {"asked": fmt, "picked": picked if fmt == "auto" else fmt,
                        "sure": _sure(best, second, len(content)) if fmt == "auto" else "chosen",
                        "configured": configured, "candidates": tried}
    if not content:
        report.update(read=0, unread=0, reasons=[], verdict="bad",
                      headline="The sample is empty: there are no lines to read.")
        return report
    hits, unread, layouts = _line_pass(lines, fmt, picked)
    report["read"], report["unread"] = len(hits), len(unread)
    reasons: dict[str, dict] = {}
    for number, key, words in unread:
        r = reasons.setdefault(key, {"why": words, "lines": 0, "examples": []})
        r["lines"] += 1
        if len(r["examples"]) < EXAMPLES:
            r["examples"].append(number)
    report["reasons"] = sorted(reasons.values(), key=lambda r: -r["lines"])[:5]
    report["other_layouts"] = layouts
    _facts(report, hits, config, now, zone(config))
    if hits:
        _groups(report, _count(lines, fmt, config), check)
    _warn(report, hits, unread, config, configured, layouts)
    return report


def _facts(report: dict, hits, config: dict, now: datetime, tz) -> None:
    """Times, zones and hosts as the lines hold them."""
    if not hits:
        report.update(times=None, hosts=[], no_host=0)
        return
    whens = sorted(_aware(h.when) for h in hits)
    zones = Counter(_zone_of(h.when) for h in hits)
    report["times"] = {"first": whens[0].isoformat(), "last": whens[-1].isoformat(),
                       "zones": [z for z, _ in zones.most_common()], "site_zone": str(tz),
                       "future": whens[-1] > now + timedelta(hours=1)}
    wanted = set(report["hosts_wanted"])
    names = Counter(h.host.lower() for h in hits if h.host)
    report["no_host"] = sum(1 for h in hits if not h.host)
    report["hosts"] = [{"host": mask(name), "lines": n, "site": (name in wanted) if wanted else None}
                       for name, n in names.most_common(8)]
    report["more_hosts"] = max(0, len(names) - 8)


def _groups(report: dict, totals, check) -> None:
    """The five groups, the site's top pages, and whether it adds up."""
    groups = []
    for which in Group:
        stats = totals.groups.get(which)
        groups.append({"group": which.value, "label": GROUP_LABELS[which],
                       "requests": stats.hits if stats else 0,
                       "views": stats.views if stats else 0,
                       "readers": (stats.readers or 0) if stats else 0})
    summed = sum(g["requests"] for g in groups)
    unparsed = totals.unparsed
    duplicates = max(0, totals.lines_read - unparsed - totals.parsed)
    report["groups"] = groups
    report["counted"] = {
        "site_requests": totals.hits, "other_hosts": totals.other_hosts,
        "unreadable": unparsed, "duplicates": duplicates, "lines": totals.lines_read,
        "groups_sum": summed, "unfiltered": totals.unfiltered,
        "adds_up": (summed == totals.hits and
                    totals.hits + totals.other_hosts + unparsed + duplicates == totals.lines_read),
        "problems": [f"{p.what}: {p.detail}" for p in check(totals)]}
    people = totals.groups.get(Group.PEOPLE)
    report["pages"] = [{"path": mask(path), "views": n}
                       for path, n in (people.pages.most_common(5) if people else [])]


# Files a crawler asks for that are no page's asset, though ASSET matches them.
NOT_ASSET = re.compile(r"(?:^/robots\.txt|^/ads\.txt|^/llms(?:-full)?\.txt|\.xml(?:\.gz)?)$", re.I)


def _browser(agent: str) -> bool:
    """A browser's user agent, not a crawler's that starts with Mozilla/."""
    return bool(BROWSER.search(agent)) and not OTHER_BOT.search(agent) \
        and not COMPATIBLE.search(agent)


def _warn(report: dict, hits, unread, config: dict, configured: str, layouts: dict) -> None:
    from .config import setting
    from .rendering import asset_prefixes, required
    warn, note = report["warnings"].append, report["notes"].append
    lines, read = report["lines"], report["read"]
    errors = sum(1 for _, key, _ in unread if key == "error_log")
    if errors and errors >= max(1, len(unread) // 2):
        warn("This looks like an error log, not an access log. Point Skald at the access log "
             "(often access.log in the same folder).")
    if not read:
        report["verdict"] = "bad"
        asked = report["format"]["asked"]
        report["headline"] = ("Skald cannot read this log: no reader takes its lines."
                              if asked == "auto" else f"The {asked} reader cannot read these "
                              "lines. Try Detect it (auto).")
        return
    limit = float(setting(config, "report", "max_unparsed_percent", 1))
    share = 100 * len(unread) / lines
    if share > limit:
        warn(f"{share:.1f}% of the lines cannot be read. A daily run withholds a day above "
             f"{limit:g}% (report.max_unparsed_percent).")
    if not any(h.referrer for h in hits):
        warn("No line has a referrer, so every visit's source will be Direct. If people come "
             "from search or links, the log is not recording the Referer header.")
    if not any(h.user_agent for h in hits):
        warn("No line has a user agent, so Skald cannot tell people from bots. Add the "
             "User-Agent header to the log format.")
    if report["no_host"]:
        part = ("No line carries a host name" if report["no_host"] == read
                else f"{report['no_host']} lines carry no host name")
        warn(f"{part}, so Skald cannot tell this site's requests from "
             "another site's on the same server. Fine when the server serves one site; "
             "otherwise add $host to the log format.")
    wanted = report["hosts_wanted"]
    if wanted and report["hosts"] and not any(h["site"] for h in report["hosts"]):
        warn(f"No line is for {', '.join(wanted)}. The hosts in the sample are "
             f"{', '.join(h['host'] for h in report['hosts'][:4])}. Check the site name or the log.")
    for h in report["hosts"]:
        if h["site"] is False and any(h["host"] in (f"www.{w}", w.removeprefix("www.")) for w in wanted):
            warn(f"{h['lines']} lines are for {h['host']}, which is not one of the site's host "
                 "names: add it to the site's hosts (Settings > Site details), or they are counted apart.")
    times = report.get("times") or {}
    if times.get("future"):
        warn("Some times are in the future: the server's clock or the time zone in the log is wrong.")
    if times.get("zones") == ["UTC"]:
        zone_name = times.get("site_zone")
        note("Times are UTC. That is fine: Skald shows them in the site's time zone"
             + ("." if zone_name in ("UTC", "Etc/UTC") else f" ({zone_name})."))
    if layouts:
        names = ", ".join(f"{n} ({k})" for k, n in layouts.items())
        note(f"Some lines are in another layout: {names}. The log format changed part-way, "
             "or two sources share the file. Skald reads both.")
    picked = report["format"]["picked"]
    if configured not in ("auto", picked) and report["format"]["asked"] == "auto":
        warn(f"This site is set to read {configured}, but the sample is {picked}. Set the "
             "site's log format to Detect it (auto) or to this one.")
    # Only what a browser fetched and was served counts here: a scanner's 404 for
    # /.docker/config.json is not a page asset. A sample with few browser page views
    # (a quiet hour, bots only) says nothing about the assets.
    mine = [h for h in hits if (not wanted or h.host.lower() in wanted or not h.host)
            and _browser(h.user_agent) and (h.ok or h.status == "304")]
    assets = [h.path for h in mine if ASSET.search(h.path) and not NOT_ASSET.search(h.path)]
    browsed = sum(1 for h in mine if h.is_page)
    prefixes = asset_prefixes(config)
    if browsed < 20 or not required(config):
        pass
    elif not assets:
        warn("No request for CSS, JavaScript or images in the sample. Skald counts a person only "
             "when the browser also fetched the page's assets. If they come from another host "
             "(a CDN), set the site's page assets, or people will show as bots.")
    elif not any(p.startswith(prefixes) for p in assets):
        folders = Counter("/" + p.lstrip("/").split("/", 1)[0] + "/" for p in assets if p.count("/") > 1)
        hint = f" (here most are under {folders.most_common(1)[0][0]})" if folders else ""
        warn(f"No asset request is under the site's page assets ({', '.join(prefixes)}){hint}. "
             "Skald counts a person only when the browser fetched one of them: set the site's "
             "page assets (Settings > Collect data > What counts), or people will show as bots.")
    if lines < 50:
        note(f"Only {lines} lines: a bigger sample gives a surer answer.")
    counted = report.get("counted") or {}
    if counted.get("duplicates"):
        note(f"{counted['duplicates']} lines repeat a request id already read; a daily run "
             "drops them too.")
    if counted and not counted.get("adds_up"):
        warn("The groups do not add up to the lines read. Please report this: "
             + "; ".join(counted.get("problems") or []))
    bad = report["warnings"] and (share > limit or not counted.get("adds_up", True))
    report["verdict"] = "bad" if bad else ("warn" if report["warnings"] else "ok")
    report["headline"] = {
        "ok": "Skald can read this log.",
        "warn": "Skald can read this log, with the warnings below.",
        "bad": "Skald can read part of this log; a daily run would withhold the day.",
    }[report["verdict"]]
