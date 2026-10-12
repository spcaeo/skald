#!/usr/bin/env python3
"""skald command line.

    ./report.py                      text cards, using ./config.yml
    ./report.py --html out.html      also write the mail body
    ./report.py --days 7             override the window
    ./report.py --check              only verify the arithmetic; exit 1 if wrong
    ./report.py --log path/to/access.log   one file, ignoring config
    ./report.py --day 2026-10-05     exactly one local day (report.timezone)
    ./report.py --from 2026-09-28 --to 2026-10-04   a run of local days

No network, no database, no writes anywhere but a path you name. The system
commands - history, dashboard, mail - are in skald.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skald import Group, as_html, as_text, check, log_files  # noqa: E402
from skald.config import country_credit, load_config, tiny_yaml  # noqa: E402
from skald.window import (analyse_paths, analyse_window, parse_day,  # noqa: E402
                                 range_window, zone)

# Kept under its old name: tests and callers import it from here.
_tiny_yaml = tiny_yaml


def as_json(totals) -> dict:
    """The card data, in a shape another program can render.

    Stable contract: every group carries the same keys, and `groups` sums to
    `total`. A consumer that trusts that does not need to re-derive anything,
    which is the point - the old report re-derived its own subtotals from a
    different source and they disagreed with each other.
    """
    out = {
        "total": totals.hits,
        "parsed": totals.parsed,
        "unfiltered": totals.unfiltered,
        "linesRead": totals.lines_read,
        "unparsed": totals.unparsed,
        "from": totals.first.isoformat() if totals.first else None,
        "to": totals.last.isoformat() if totals.last else None,
        "groups": {},
    }
    for which, stats in totals.groups.items():
        out["groups"][which.value] = {
            "hits": stats.hits,
            "views": stats.views,
            "visits": stats.visits,
            "readers": stats.readers,
            "probes": stats.probes,
            "countries": dict(stats.countries),
            "pages": dict(stats.pages),
            "agents": dict(stats.agents),
            "tiers": dict(stats.tiers),
            "engines": dict(stats.engines),
            "citedVisits": stats.cited_visits,
            "citedBy": dict(stats.cited_by),
            "citedPages": dict(stats.cited_pages),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.yml")
    ap.add_argument("--log", action="append", help="a log file, repeatable")
    ap.add_argument("--days", type=int)
    ap.add_argument("--day", metavar="DATE",
                    help="exactly one local day: yesterday, today or YYYY-MM-DD")
    ap.add_argument("--from", dest="first", metavar="DATE",
                    help="first local day of a range (with --to)")
    ap.add_argument("--to", dest="last", metavar="DATE",
                    help="last local day of a range, inclusive")
    ap.add_argument("--format", default=None)
    ap.add_argument("--html", metavar="PATH", nargs="?", const="-")
    ap.add_argument("--title", default="Traffic report")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true",
                    help="emit the card data for another program to render")
    args = ap.parse_args()

    config = load_config(Path(args.config))
    logs = config.get("logs", {})
    days = args.days or int(logs.get("days", 2) or 2)

    if args.log:
        paths = [Path(p) for p in args.log]
    else:
        paths = log_files(Path(logs.get("dir", "/var/log/nginx")),
                          logs.get("base", "access.log"), days)
    if not paths:
        print("no log files found; set logs.dir and logs.base, or pass --log",
              file=sys.stderr)
        return 2

    if args.format:
        config.setdefault("logs", {})["format"] = args.format
    if args.day or args.first or args.last:
        # An exact window, cut in report.timezone. --days is ignored: which
        # rotations to read is worked out from the window.
        tz = zone(config)
        first = parse_day(args.day or args.first or args.last, tz)
        last = parse_day(args.day or args.last or args.first, tz)
        if last < first:
            print("--to is before --from", file=sys.stderr)
            return 2
        start, end = range_window(first, last, tz)
        totals = analyse_window(config, start, end,
                                paths=paths if args.log else None, top=8)
    else:
        totals = analyse_paths(config, paths, top=8, fmt=args.format)

    problems = check(totals)
    if problems:
        print("FIGURES DO NOT RECONCILE:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if args.check:
            return 1
        print("  (report withheld; fix the above)", file=sys.stderr)
        return 1
    if args.check:
        print(f"ok: {totals.hits:,} requests, every category reconciles")
        return 0

    if args.json:
        import json as _json
        print(_json.dumps(as_json(totals), indent=1))
        return 0

    names = config.get("report", {}).get("cards")
    order = [Group.PEOPLE, Group.ANSWER_ENGINE, Group.SEARCH_ENGINE,
             Group.BOTS, Group.OURS]
    cards = [g for g in order if not names or g.value in names]

    credit = country_credit(config)
    print(as_text(totals, cards, credit))
    if args.html:
        page = as_html(totals, cards, args.title, credit=credit)
        if args.html == "-":
            print(page)
        else:
            Path(args.html).write_text(page)
            print(f"[html written to {args.html}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
