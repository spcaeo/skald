"""Is the input trustworthy? The data-quality figures (quality.json).

verify.py proves the figures agree with each other; it cannot prove the log
they came from was whole. This counts what can be seen of that, per day and
for today so far:

  lines, unparsed   every line in the window and those no format read
  duplicates        lines byte-identical to an earlier one in the same second
                    (counted, never dropped: without $request_id a real repeat
                    and a doubled line look the same - COUNTING-TRAPS.md 7)
  duplicates_removed  lines that repeat an earlier line's request id (rid=):
                    the same request written twice, dropped by parse.read()
                    and counted by window.py
  old_format        lines in the old combined layout: no host, no country
  not_pages         requests of the site's hosts shaped like a page view that
                    the site's not-a-page list kept out of the page views, by
                    entry (not_pages.py): {entry: {"requests", "people"}}
  gaps              stretches of more than GAP_MINUTES with no line at all
  first/last line   when the window's own lines start and stop

and, at render time, whether each day verified and passed the independent
audit, the newest line against the server clock, the log files on disk, and
when each scheduled job last ran (runs.py).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

GAP_MINUTES = 10


def _aware(when: datetime) -> datetime:
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


class Duplicates:
    """Says whether a hit repeats, field for field, one already seen in the
    same second. Lines arrive nearly in time order, so only the last few
    seconds are remembered."""

    def __init__(self) -> None:
        self.by_second: dict[int, set] = {}
        self.newest = 0

    def seen(self, hit) -> bool:
        second = int(_aware(hit.when).timestamp())
        # The raw line's hash when read() set it; else every field we have.
        key = hit.line_id or (hit.address, hit.host, hit.method, hit.url, hit.status,
                              hit.size, hit.referrer, hit.user_agent, hit.country,
                              hit.request_time, hit.fmt)
        bucket = self.by_second.setdefault(second, set())
        if second > self.newest:
            self.newest = second
            # nginx logs a request when it ends, so lines come a little out
            # of order; ten minutes back is far more than any request takes.
            if len(self.by_second) > 1200:
                for old in [s for s in self.by_second if s < second - 600]:
                    del self.by_second[old]
        if key in bucket:
            return True
        bucket.add(key)
        return False


class Quality:
    """Fed every parsed hit in the window, whatever its host."""

    def __init__(self, tz=None) -> None:
        self.tz = tz
        self.parsed = 0
        self.duplicates = 0
        self.old_format = 0
        self.minutes: set[int] = set()
        self.first = None
        self.last = None
        self.dups = Duplicates()
        self.not_pages: dict[str, list] = {}

    def not_page(self, rule: str, people: bool) -> None:
        """A request of the site's hosts the not-a-page list took out of the
        page views (aggregate.Tally.add): by entry, and how many of them
        were people's."""
        got = self.not_pages.setdefault(rule, [0, 0])
        got[0] += 1
        got[1] += people

    def add(self, hit) -> None:
        self.parsed += 1
        when = _aware(hit.when)
        if self.dups.seen(hit):
            self.duplicates += 1
        if hit.fmt in ("nginx_combined", "apache_combined"):
            self.old_format += 1
        self.minutes.add(int(when.timestamp()) // 60)
        if self.first is None or when < self.first:
            self.first = when
        if self.last is None or when > self.last:
            self.last = when

    def _hhmm(self, when: datetime) -> str:
        return (when.astimezone(self.tz) if self.tz else when).strftime("%H:%M")

    def finish(self) -> dict:
        gaps = []
        ordered = sorted(self.minutes)
        for a, b in zip(ordered, ordered[1:]):
            if b - a - 1 > GAP_MINUTES:
                start = datetime.fromtimestamp((a + 1) * 60, timezone.utc)
                end = datetime.fromtimestamp(b * 60, timezone.utc)
                gaps.append({"from": self._hhmm(start), "to": self._hhmm(end),
                             "minutes": b - a - 1})
        return {"parsed": self.parsed, "duplicates": self.duplicates,
                "old_format": self.old_format, "gaps": gaps,
                "first_line": self._hhmm(self.first) if self.first else None,
                "last_line": self._hhmm(self.last) if self.last else None,
                "newest_line": self.last.isoformat(timespec="seconds") if self.last else None,
                "not_pages": {rule: {"requests": n, "people": p}
                              for rule, (n, p) in sorted(self.not_pages.items())}}


def check(blob: dict | None, parsed: int) -> list:
    from .verify import Problem
    if not blob:
        return []
    problems = []
    if blob.get("parsed") != parsed:
        problems.append(Problem("quality: lines parsed",
                                f"{blob.get('parsed')} against {parsed:,} in the window"))
    for k in ("duplicates", "old_format"):
        if int(blob.get(k) or 0) > parsed:
            problems.append(Problem(f"quality: {k}", "more than the lines parsed"))
    return problems


# ------------------------------------------------------------- quality.json

def log_files(config: dict) -> list[dict]:
    logs = (config or {}).get("logs") or {}
    folder = Path(str(logs.get("dir") or "/var/log/nginx"))
    base = str(logs.get("base") or "access.log")
    out = []
    try:
        found = [p for p in folder.glob(base + "*") if p.is_file()]
    except OSError:
        return out
    for path in found:
        try:
            st = path.stat()
        except OSError:
            continue
        out.append({"name": path.name, "bytes": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc)
                    .isoformat(timespec="seconds")})
    out.sort(key=lambda f: f["modified"], reverse=True)
    return out


def _audit(blob: dict | None) -> dict:
    if not blob:
        return {"state": "not run", "at": None, "compared": None, "problems": []}
    return {"state": blob.get("state", "not run"), "at": blob.get("at"),
            "compared": blob.get("compared"), "problems": list(blob.get("problems") or [])}


def _lines(p) -> dict[str, tuple]:
    """{day: (lines_read, unparsed, problems)} of the page's stored days, in one query."""
    return {d: (lines, unparsed, problems) for d, lines, unparsed, problems in p.history.db.execute(
        "SELECT day, lines_read, unparsed, problems FROM days WHERE site = ? AND day BETWEEN ? AND ?",
        (p.key, p.first.isoformat(), p.anchor.isoformat()))}


def _day(p, entry: dict, stored: dict[str, tuple]) -> dict:
    d = entry["day"].isoformat()
    row = {"day": d, "state": entry["state"]}
    if entry["state"] in ("missing", "before"):
        return row
    blobs = p.extras.get(d) or {}
    q = blobs.get("quality")
    lines = stored.get(d)
    row.update({
        "lines": lines[0] if lines else None, "unparsed": lines[1] if lines else None,
        "duplicates": q.get("duplicates") if q else None,
        "duplicates_removed": q.get("duplicates_removed") if q else None,
        "old_format": q.get("old_format") if q else None,
        # Shaped like pages, not counted as pages (not_pages.py); None: not recorded.
        "not_pages": q.get("not_pages") if q else None,
        "first_line": q.get("first_line") if q else None,
        "last_line": q.get("last_line") if q else None,
        "gaps": q.get("gaps") if q else None,
        "files": q.get("files") if q else None,
        # Browser-like requests moved to bots: their visit never rendered a page.
        "not_rendered": (blobs.get("bots") or {}).get("not_rendered"),
        "verify": entry["state"], "problems": (lines[2] if lines else "") or "",
        "audit": _audit(blobs.get("audit")),
    })
    return row


def build(p) -> dict:
    from . import runs
    stored = _lines(p)
    days = [_day(p, e, stored) for e in p.daily]
    today = None
    if p.snap is not None:
        q = ((p.snap.get("extras") or {}).get("quality")) if p.live_ok else None
        newest = (q or {}).get("newest_line")
        skew = None
        if newest and p.snap.get("generated_at"):
            skew = round((datetime.fromisoformat(p.snap["generated_at"])
                          - datetime.fromisoformat(newest)).total_seconds(), 1)
        today = {"state": p.snap.get("state"), "lines": p.snap.get("lines_read"),
                 "unparsed": p.snap.get("unparsed"),
                 **{k: (q or {}).get(k) for k in ("duplicates", "duplicates_removed",
                                                   "old_format", "not_pages", "gaps",
                                                   "first_line", "last_line", "files")},
                 "not_rendered": (((p.snap.get("extras") or {}).get("bots") or {})
                                  .get("not_rendered")) if p.live_ok else None,
                 "newest_line": newest, "clock_skew_s": skew}
    state = runs.load(p.live_dir) if p.live_dir is not None else {}
    beat = None
    if p.live_ok:
        last = ((((p.snap.get("extras") or {}).get("ours") or {}).get("heartbeat")) or {}
                ).get("last_ok_at")
        beat = last
    every = {"live": 2, "run-daily": 1440, "verify-bots": 1440, "alerts": 2,
             "backup": 1440, "pagespeed": 1440, "heartbeat": 5}
    out_runs = {}
    for name, minutes in every.items():
        got = state.get(name) or {}
        out_runs[name] = {"last_ok": got.get("last_ok"), "last_fail": got.get("last_fail"),
                          "last_exit": got.get("last_exit"), "expected_every_min": minutes}
    out_runs["heartbeat"]["last_ok"] = beat
    failures = getattr(p, "failures", None)
    return {"days": days, "today": today, "runs": out_runs,
            "rotation": {"files": log_files(p.config)},
            # Optional data files that failed to build this run (builders.py).
            "builders_failing": failures.listing() if failures is not None else []}
