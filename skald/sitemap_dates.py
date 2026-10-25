"""The sitemap's <lastmod> dates: when the site says each page last changed.

sitemap.py reads them in the same fetch as the path list (nothing more is
fetched) and calls `merge` once per local day, with the day's first good
fetch. A lastmod is a change date the site gives, not a publish date.

  day_of()    one <lastmod> value as a local date, or None. The W3C datetime
              forms: a date (YYYY-MM-DD, taken as it stands: it has no time),
              or a date and time with a zone (Z or +hh:mm), seconds and their
              fractions optional, turned into the site's time zone (a time
              without a zone, which the W3C form does not allow, is read as the
              site's own time). A year or a month alone is too coarse: invalid,
              as is any other text, a date that does not exist, or a year
              before 1990.
  dates()     the day's {path: date} and its counts. Each path of the day's
              list is counted once: `dated` (a valid date no later than the
              fetch's local day; two spellings of one path keep the latest),
              `missing` (no <lastmod>), `invalid` (only values that do not
              parse), `future` (only dates after the fetch's day: ignored).
              dated + missing + invalid + future = the list's paths.
  merge()     folds the day's dates into the history file, once per day.
  load()      the history file's paths, {} when none (or another version).

Storage, beside the path lists (DATA-CONTRACT-CRAWL-HEALTH.md):

  sitemaps/lastmod/history.json
      {"version": 1, "day": the last day merged, "cap": CAP,
       "paths": {path: {"now": date or null, "last": day, "seen": [[date, day], ...]}}}
      `seen`: each lastmod value the path had, with the first local day Skald
      saw it, oldest first, at most CAP (the oldest dropped). `now`: the
      value in the last day merged (null when that day's sitemap gave the
      path no valid date or no longer listed it). `last`: the last day the
      path had a valid date. A path whose `last` is KEEP_DAYS old is dropped.
  sitemaps/days.json  each day's entry gains "lastmod": {"version", "dated",
      "missing", "invalid", "future", "digest"} - the digest is the first 16
      hex characters of the SHA-256 of the day's "path<TAB>date" lines,
      sorted, joined by newlines. A day kept before this existed has none.

The folder is a subfolder so the path lists' clean-up (sitemap.keep, which
removes every sitemaps/*.json no day names) never touches it.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .files import write_atomic

VERSION = 1
CAP = 20
KEEP_DAYS = 400
FOLDER = "lastmod"
HISTORY = "history.json"
EARLIEST = 1990
_W3C = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})"
    r"(?:[Tt ](\d{2}):(\d{2})(?::(\d{2})(?:[.,]\d+)?)?\s*(Z|z|[+-]\d{2}(?::?\d{2})?)?)?")


def day_of(raw, tz) -> date | None:
    """A <lastmod> value as the site's local date; None when it is not one."""
    found = _W3C.fullmatch(str(raw or "").strip())
    if not found:
        return None
    y, mo, d, hh, mm, ss, zone = found.groups()
    try:
        day = date(int(y), int(mo), int(d))
    except ValueError:
        return None
    if day.year < EARLIEST:
        return None
    if hh is None:
        return day
    if int(hh) > 23 or int(mm) > 59 or int(ss or 0) > 59:
        return None
    if zone is None:
        return day                          # no zone: the site's own time
    if zone in ("Z", "z"):
        offset = "+00:00"
    else:
        digits = zone[1:].replace(":", "")
        if len(digits) == 2:
            digits += "00"
        if int(digits[:2]) > 23 or int(digits[2:]) > 59:
            return None
        offset = f"{zone[0]}{digits[:2]}:{digits[2:]}"
    try:
        stamp = datetime.fromisoformat(f"{day.isoformat()}T{int(hh):02d}:{int(mm):02d}:"
                                       f"{int(ss or 0):02d}{offset}")
    except ValueError:
        return None
    return stamp.astimezone(tz).date()


def dates(paths, raws: dict, tz, today: date) -> tuple[dict, dict]:
    """({path: "YYYY-MM-DD"}, {"dated","missing","invalid","future"}) for the
    day's list `paths`; `raws` is {path: [<lastmod> text, ...]} (sitemap.collect)."""
    out: dict[str, str] = {}
    counts = {"dated": 0, "missing": 0, "invalid": 0, "future": 0}
    for path in paths:
        values = raws.get(path) or []
        if not values:
            counts["missing"] += 1
            continue
        got = [day_of(v, tz) for v in values]
        good = [d for d in got if d is not None and d <= today]
        if good:
            out[path] = max(good).isoformat()
            counts["dated"] += 1
        elif any(d is not None for d in got):
            counts["future"] += 1
        else:
            counts["invalid"] += 1
    return out, counts


def digest(found: dict) -> str:
    lines = "\n".join(sorted(f"{p}\t{d}" for p, d in found.items()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()[:16]


def path_of(directory) -> Path:
    return Path(directory) / "sitemaps" / FOLDER / HISTORY


def _read(directory) -> dict | None:
    try:
        got = json.loads(path_of(directory).read_text())
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(got, dict) or got.get("version") != VERSION:
        return None
    return got if isinstance(got.get("paths"), dict) else None


def load(directory) -> dict:
    """{path: {"now", "last", "seen"}} from the history file; {} when none."""
    if directory is None:
        return {}
    got = _read(directory)
    return got["paths"] if got else {}


def last_day(directory) -> str | None:
    """The last day merged into the history file, or None."""
    got = _read(directory) if directory is not None else None
    return str(got["day"]) if got and got.get("day") else None


def merge(directory, day: date, found: dict) -> bool:
    """Fold the day's {path: date} into the history file. False (nothing
    written) when the file already holds this day or a later one."""
    old = _read(directory) or {"version": VERSION, "day": None, "cap": CAP, "paths": {}}
    wanted = day.isoformat()
    if old.get("day") and str(old["day"]) >= wanted:
        return False
    paths = old["paths"]
    for path, entry in paths.items():
        if path not in found:
            entry["now"] = None
    for path, value in found.items():
        entry = paths.setdefault(path, {"now": None, "last": None, "seen": []})
        seen = entry.get("seen") or []
        if not seen or seen[-1][0] != value:
            seen.append([value, wanted])
        entry.update(now=value, last=wanted, seen=seen[-CAP:])
    oldest = (day - timedelta(days=KEEP_DAYS)).isoformat()
    kept = {p: e for p, e in sorted(paths.items()) if (e.get("last") or "") >= oldest}
    write_atomic(path_of(directory), json.dumps(
        {"version": VERSION, "day": wanted, "cap": CAP, "paths": kept},
        sort_keys=True, separators=(",", ":")) + "\n")
    return True
