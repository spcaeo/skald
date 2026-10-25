"""`skald try-log <file>`: the dry run of try_log.py, in words.

    skald try-log /var/log/nginx/access.log
    skald try-log export.json.gz --format cloudflare_json --site <site>
    docker exec skald skald try-log /var/lib/skald/ingest/<site>/access.log

Reads the file's first --lines lines (plain or gzip), picks the reader that
reads the most of them (or the one --format names), and prints what a daily
run would make of them. Stores nothing. Exit 0 when Skald can read the log
(with or without warnings), 1 when a daily run would withhold the day or
nothing can be read, 2 when the file cannot be opened.

Which settings judge the lines: the site --site names (its hosts, own
traffic, page assets, time zone) when it is a site of this install; a site
named by the path (`.../ingest/<site>/...`); the only site of a one-site
install; else none (no host filter, the defaults). It runs without a
config file too (cli.main: `bare`).
"""
from __future__ import annotations

import json
import re
import sys

from .try_log import FORMATS, MOST_LINES, SAMPLE_LINES, SampleError, dry_run, sample_file

INGEST_PATH = re.compile(r"/ingest/([a-z0-9.-]+)/")


def add_command(sub) -> None:
    p = sub.add_parser("try-log", help="a dry run: can Skald read this log file, and what "
                       "would it count? Stores nothing")
    p.add_argument("file", help="a log file, plain or .gz")
    p.add_argument("--format", dest="log_format", default="auto", choices=FORMATS,
                   help="the reader to use (default auto: the one that reads the most lines)")
    p.add_argument("--site", dest="host", metavar="HOST",
                   help="the site the log is for: its settings judge the lines")
    p.add_argument("--lines", type=int, default=SAMPLE_LINES,
                   help=f"how many lines to read from the top (default {SAMPLE_LINES})")
    p.add_argument("--json", action="store_true", help="the report as JSON")
    p.set_defaults(run=cmd_try_log, bare=cmd_bare)


def _site_config(configs: list[dict], host: str | None):
    """(config, name) of the site named by `host` (its name or one of its
    hosts), or (None, None)."""
    from .config import setting, site_name
    if not host:
        return None, None
    want = host.strip().lower()
    for config in configs:
        name = site_name(config).lower()
        hosts = [str(h).lower() for h in (setting(config, "site", "hosts") or [])]
        if want == name or want in hosts:
            return config, site_name(config)
    return None, None


def cmd_try_log(ctx) -> int:
    args = ctx.args
    configs = list(getattr(ctx, "all_configs", None) or [ctx.config])
    host = args.host or (ctx.site if getattr(args, "only_site", None) else None)
    if not host:
        found = INGEST_PATH.search(str(args.file).replace("\\", "/"))
        host = found.group(1) if found else None
        if host is None and len(configs) == 1:
            host = ctx.site
    config, name = _site_config(configs, host)
    return _run(args, config, host, name)


def cmd_bare(args) -> int:
    """No config file: judged with the defaults (and --site's host)."""
    return _run(args, None, args.host, None)


def _run(args, config, host, name) -> int:
    if not 1 <= args.lines <= MOST_LINES:
        print(f"--lines must be between 1 and {MOST_LINES:,}", file=sys.stderr)
        return 2
    try:
        lines = sample_file(args.file, args.lines)
        report = dry_run(lines, args.log_format, config, host, site_known=config is not None)
    except SampleError as why:
        print(str(why), file=sys.stderr)
        return 2
    report["source"] = str(args.file).rsplit("/", 1)[-1]
    report["site_name"] = name
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render(report, args.lines))
    return 1 if report.get("verdict") == "bad" else 0


# ------------------------------------------------------------------ words

def _when(iso: str) -> str:
    """2026-10-25T00:00:41.28+00:00 -> 2026-10-25 00:00:41 +0000."""
    from datetime import datetime
    return f"{datetime.fromisoformat(iso):%Y-%m-%d %H:%M:%S %z}".strip()


def _plural(n: int, one: str, many: str) -> str:
    return f"{n:,} {one if n == 1 else many}"


def _n(value) -> str:
    return f"{value:,}"


def render(report: dict, asked: int | None = None) -> str:
    """The report in plain words, one block per question."""
    out = []
    say = out.append
    top = f" (the first {_n(report['lines'])} lines)" if asked else ""
    say(f"Skald dry run: {report.get('source') or 'the sample'}{top}. Nothing is stored.")
    say("")
    fmt = report["format"]
    if fmt["asked"] == "auto":
        sure = {"sure": "sure", "likely": "likely", "unsure": "not sure",
                "none": "no reader fits"}[fmt["sure"]]
        pick = fmt["picked"] or "none"
        say(f"Format:   {pick} ({sure})")
        some = [c for c in fmt["candidates"] if c["read"]]
        none = len(fmt["candidates"]) - len(some)
        say("          lines read by each reader: " + ", ".join(
            [f"{c['format']} {_n(c['read'])}" for c in some]
            + ([f"the other {none} read none"] if some and none else [])
            + (["none reads a line"] if not some else [])))
    else:
        say(f"Format:   {fmt['asked']} (chosen with --format)")
    if fmt.get("configured") and fmt["configured"] != "auto" and report.get("site_known"):
        say(f"          this site is set to {fmt['configured']}")
    say(f"Lines:    {_n(report['lines'])}: {_n(report['read'])} read, "
        f"{_n(report['unread'])} could not be read")
    for r in report.get("reasons") or []:
        at = ", ".join(str(n) for n in r["examples"])
        say(f"          {_n(r['lines'])} {r['why']} (line {at})")
    if report["lines"] == 0:
        say("")
        say(f"Result:   {report['headline']}")
        return "\n".join(out)
    times = report.get("times")
    if times:
        say(f"Times:    {_when(times['first'])} to {_when(times['last'])}")
        say(f"          time zone in the lines: {', '.join(times['zones'])}; "
            f"the site's zone: {times['site_zone']}")
    if report.get("hosts") or report.get("no_host"):
        parts = []
        for h in report.get("hosts") or []:
            mark = "" if h["site"] is None else (" (this site)" if h["site"] else " (another host)")
            parts.append(f"{h['host']} {_n(h['lines'])}{mark}")
        if report.get("more_hosts"):
            parts.append(f"{report['more_hosts']} more")
        if report.get("no_host"):
            parts.append(f"no host field {_n(report['no_host'])}")
        say("Hosts:    " + ", ".join(parts))
    site = report.get("site_name") or report.get("site")
    if site:
        known = "its settings" if report.get("site_known") else "the default settings"
        say(f"Site:     {site}, judged with {known}")
    counted = report.get("counted")
    if counted:
        say(f"Groups:   {_n(counted['site_requests'])} requests for the site, in Skald's five groups")
        for g in report["groups"]:
            more = (f", {_plural(g['views'], 'page view', 'page views')}, "
                    f"{_plural(g['readers'], 'reader', 'readers')}"
                    if g["group"] == "people" else "")
            say(f"          {g['label']:<18} {_n(g['requests']):>7}{more}")
        sums = " + ".join(_n(g["requests"]) for g in report["groups"])
        ok = "adds up" if counted["adds_up"] else "DOES NOT ADD UP"
        say(f"          {sums} = {_n(counted['groups_sum'])}: {ok}")
        rest = [f"{_n(counted['site_requests'])} for the site"]
        if counted["other_hosts"]:
            rest.append(f"{_n(counted['other_hosts'])} for other hosts")
        rest.append(f"{_n(counted['unreadable'])} unreadable")
        if counted["duplicates"]:
            rest.append(f"{_n(counted['duplicates'])} repeated request ids")
        say(f"          {_n(counted['lines'])} lines = " + " + ".join(rest))
    if report.get("pages"):
        say("Pages:    the pages people viewed most")
        for p in report["pages"]:
            say(f"          {_n(p['views']):>5}  {p['path']}")
    elif counted:
        say("Pages:    no page view by a person in the sample")
    for title, items in (("Warnings", report.get("warnings")), ("Notes", report.get("notes"))):
        if items:
            say(f"{title}:")
            for item in items:
                say(f"  - {item}")
    say("")
    say(f"Result:   {report['headline']}")
    return "\n".join(out)
