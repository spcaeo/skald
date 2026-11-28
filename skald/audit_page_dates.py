"""The second count of each page's own dates (page_dates.py, SKALD-64): the
`published_at`, `published_from`, `updated_at`, `changes` and `check` that
lifecycle.py shows (page_index.json, the page story, page_trends.json).

Registered in audit_more.DAILY. run-daily's recounts step reads the
`page_dates` and `page_checks` rows of the site by its own SQL and works every
page's figures out again by the documented rule (DATA-CONTRACT.md, "Page
lifecycle"). It shares only the name lists (page_dates.KINDS, SOURCES,
OUTCOMES) with the code it checks; it asks lifecycle.page_dates only for the
figures it shows, to compare them.

  the rows     a kind and a source of the lists; a value that is a date
               (YYYY-MM-DD), a UTC time (YYYY-MM-DDTHH:MM:SSZ) or a time
               without a zone (YYYY-MM-DDTHH:MM:SS), from 1990 on and not after
               the time it was first seen (with 14 hours for a zone-less one);
               first_seen_at a UTC time no later than now; a page's own value
               (not the sitemap's) has a page_checks row for its path; a check
               has an outcome of the list, an error unless it read the page
               (dated, not_given), and a status 200 when it read it
  a page       its path cut at "?", a "/" added unless it ends with one (or is
               "/"): every spelling together
  published    of its own published rows (any source but the sitemap), the one
               first seen last (then the latest value): its value and source
  updated_at   the same for its own modified rows, shown when the page's
               updated date comes from the page ("page")
  changes      every modified row, the page's and the sitemap's, by local day
               (a UTC time moved to the site's zone, any other value its own
               first ten characters): the day, the latest value that day (a
               date counts as its midnight), the sources sorted
  check        of its page_checks rows, the latest checked_at
  title        (SKALD-70) a title row is one line with spaces folded, 1 to
               TITLE_CHARS characters, read from html, meta or jsonld; the
               page's title is the one first seen last (then the text); the
               website's page list's title wins ("website")
  shown dates  the website's page list (report.pages_meta, read here) wins: its
               `published` makes date_source "website"; else a page with its own
               published value shows that value's local day, "page". Its
               `updated` wins too; else a page with its own modified value shows
               that value's local day as `updated`, "page"

A problem is a figure shown that the rows do not give. Nothing is changed.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .page_dates import KINDS, OUTCOMES, SOURCES

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_NAIVE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
READ = ("dated", "not_given")
TITLE_FROM = ("html", "meta", "jsonld")       # SKALD-70: where a title is read
DATE_FROM = ("jsonld", "meta", "time", "sitemap")
TITLE_CHARS = 300


def _rows(db, site: str):
    try:
        dates = list(db.execute(
            "SELECT path, kind, value, source, first_seen_at FROM page_dates WHERE site = ? "
            "ORDER BY path, kind, value, source", (site,)))
        checks = list(db.execute(
            "SELECT path, checked_at, outcome, status, error FROM page_checks WHERE site = ? "
            "ORDER BY path", (site,)))
    except Exception:                    # noqa: BLE001 - no tables: nothing kept
        return [], []
    return dates, checks


def _page(path: str) -> str:
    p = str(path).split("?")[0]
    return p if p == "/" or p[-1:] == "/" else p + "/"


def _moment(value: str):
    """(kind of value, datetime): "date", "utc" or "naive"; None when it is neither."""
    v = str(value)
    try:
        if _UTC.fullmatch(v):
            return "utc", datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if _NAIVE.fullmatch(v):
            return "naive", datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")
        if _DATE.fullmatch(v):
            return "date", datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        return None
    return None


def _sortable(value: str) -> str:
    got = _moment(value)
    return got[1].strftime("%Y-%m-%dT%H:%M:%S") if got else ""


def _day(value: str, tz) -> str | None:
    got = _moment(value)
    if got is None:
        return None
    if got[0] == "utc":
        return got[1].astimezone(tz).strftime("%Y-%m-%d")
    return got[1].strftime("%Y-%m-%d")


def check_rows(dates: list, checks: list, now: datetime) -> list[str]:
    problems = []
    checked = {p for p, *_ in checks}
    for path, kind, value, source, seen in dates:
        where = f"page dates {path} {kind} {value!r} ({source})"
        if kind not in KINDS or source not in SOURCES:
            problems.append(f"{where}: not a kind and source of the lists")
            continue
        got = _moment(value)
        seen_at = _moment(seen)
        if seen_at is None or seen_at[0] != "utc" or seen_at[1] > now:
            problems.append(f"{where}: first seen {seen!r} is not a UTC time before now")
            continue
        if kind != "title" and source in TITLE_FROM and source not in DATE_FROM:
            problems.append(f"{where}: a date is read from jsonld, meta, time or the sitemap")
        if kind == "title":
            if source not in TITLE_FROM:
                problems.append(f"{where}: a title is read from html, meta or jsonld only")
            elif not isinstance(value, str) or value != " ".join(value.split()) or not value \
                    or len(value) > TITLE_CHARS:
                problems.append(f"{where}: not a title as Skald keeps one (one line, folded "
                                f"spaces, 1 to {TITLE_CHARS} characters)")
        elif got is None or got[1].year < 1990:
            problems.append(f"{where}: not a date or time Skald keeps")
        elif got[0] == "utc" and got[1] > seen_at[1] + timedelta(minutes=5):
            problems.append(f"{where}: after the time it was first seen")
        elif got[0] != "utc" and got[1] > seen_at[1].replace(tzinfo=None) + timedelta(hours=14):
            problems.append(f"{where}: after the day it was first seen")
        if source != "sitemap" and path not in checked:
            problems.append(f"{where}: the page's own value, but no read of the page is kept")
    for path, at, outcome, status, error in checks:
        where = f"page dates {path}: last read"
        if outcome not in OUTCOMES:
            problems.append(f"{where} has the outcome {outcome!r}")
        elif outcome in READ and status != 200:
            problems.append(f"{where} read the page, with status {status!r}")
        elif outcome not in READ and outcome != "not_html" and not error:
            problems.append(f"{where} failed ({outcome}) without saying why")
        at_ = _moment(at)
        if at_ is None or at_[0] != "utc" or at_[1] > now:
            problems.append(f"{where} at {at!r} is not a UTC time before now")
    return problems


def expected(dates: list, checks: list, tz) -> dict:
    """{page: {"published_at", "published_from", "modified_at", "modified_day",
    "changes", "check"}} by the rule (module doc)."""
    out: dict[str, dict] = {}

    def entry(path):
        return out.setdefault(_page(path), {"published": None, "modified": None,
                                            "title": None, "days": {}, "check": None})

    for path, kind, value, source, seen in dates:
        e = entry(path)
        if kind == "title" and source in TITLE_FROM:
            best = e["title"]
            if best is None or (seen, value) > (best[2], best[0]):
                e["title"] = (value, source, seen)
        elif source != "sitemap" and kind in KINDS:
            best = e[kind]
            if best is None or (seen, _sortable(value)) > (best[2], _sortable(best[0])):
                e[kind] = (value, source, seen)
        if kind == "modified":
            day = _day(value, tz)
            if day is not None:
                cell = e["days"].setdefault(day, [value, set()])
                cell[1].add(source)
                if _sortable(value) > _sortable(cell[0]):
                    cell[0] = value
    for path, at, outcome, status, error in checks:
        e = entry(path)
        if e["check"] is None or at > e["check"]["at"]:
            e["check"] = {"at": at, "outcome": outcome, "status": status, "error": error}
    final = {}
    for page, e in out.items():
        pub, mod, title = e["published"], e["modified"], e["title"]
        final[page] = {
            "title": title[0] if title else None, "title_from": title[1] if title else None,
            "published_at": pub[0] if pub else None, "published_from": pub[1] if pub else None,
            "modified_at": mod[0] if mod else None,
            "modified_day": _day(mod[0], tz) if mod else None,
            "changes": [{"day": d, "at": v[0], "sources": sorted(v[1])}
                        for d, v in sorted(e["days"].items())],
            "check": e["check"]}
    return final


def own_modified(db, site: str, tz) -> dict:
    """{page: the local day of its own latest modified date} (audit_lastmod's
    `updated` rule takes it before the sitemap's)."""
    dates, checks = _rows(db, site)
    return {p: e["modified_day"] for p, e in expected(dates, checks, tz).items()
            if e["modified_day"]}


def _site_list(meta_file) -> dict:
    """{page: entry} of the website's own page list (report.pages_meta), {} without."""
    import json
    if not meta_file:
        return {}
    try:
        with open(str(meta_file), encoding="utf-8") as handle:
            got = json.load(handle)
    except (OSError, ValueError):
        return {}
    out = {}
    for entry in (got.get("pages") or []) if isinstance(got, dict) else []:
        if isinstance(entry, dict) and str(entry.get("path", "")).startswith("/"):
            out[_page(entry["path"])] = entry
    return out


def recheck(db, site: str, tz, shown: dict, now: datetime | None = None,
            meta_file=None) -> list[str]:
    """Every check; `shown` is lifecycle.page_dates' answer (with history) for the
    site, `meta_file` the website's page list (report.pages_meta) or None."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    dates, checks = _rows(db, site)
    problems = check_rows(dates, checks, now)
    want = expected(dates, checks, tz)
    listed = _site_list(meta_file)
    for page, b in want.items():
        a, entry = shown.get(page) or {}, listed.get(page) or {}
        title = (entry["title"], "website") if entry.get("title") else (b["title"], b["title_from"])
        if title[0] and (a.get("title"), a.get("title_from")) != title:
            problems.append(f"page dates {page}: title shown "
                            f"{(a.get('title'), a.get('title_from'))!r}, the rows give {title!r}")
        if b["published_at"] or b["modified_at"]:
            if entry.get("published"):
                pub = (entry["published"], "website")
            elif b["published_at"]:
                pub = (_day(b["published_at"], tz), "page")
            else:
                pub = (None, None)
            if (a.get("published"), a.get("date_source")) != pub:
                problems.append(f"page dates {page}: published shown "
                                f"{(a.get('published'), a.get('date_source'))!r}, the rows give "
                                f"{pub!r}")
        if b["modified_day"] and not entry.get("updated") and \
                (a.get("updated"), a.get("updated_source")) != (b["modified_day"], "page"):
            problems.append(f"page dates {page}: updated shown "
                            f"{(a.get('updated'), a.get('updated_source'))!r}, the rows give "
                            f"{(b['modified_day'], 'page')!r}")
    for page in sorted(set(want) | {p for p, v in shown.items()
                                    if v.get("changes") or v.get("check")
                                    or v.get("published_at")}):
        a, b = shown.get(page) or {}, want.get(page) or {}
        pairs = [("published_at", b.get("published_at")),
                 ("published_from", b.get("published_from")),
                 ("changes", b.get("changes") or []), ("check", b.get("check"))]
        if a.get("updated_source") == "page":
            pairs.append(("updated_at", b.get("modified_at")))
            pairs.append(("updated", b.get("modified_day")))
        for field, value in pairs:
            if (a.get(field) or None) != (value or None):
                problems.append(f"page dates {page}: {field} shown {a.get(field)!r}, the rows "
                                f"give {value!r}")
    return problems


def set_up(ctx) -> bool:
    """True once the site has a page date or a read kept."""
    try:
        with ctx.history() as history:
            dates, checks = _rows(history.db, ctx.site)
    except Exception:                    # noqa: BLE001
        return False
    return bool(dates or checks)


def daily(ctx, day) -> list[str] | None:
    """run-daily: the problems found (empty: they match); None when nothing is kept."""
    if not set_up(ctx):
        return None
    from pathlib import Path
    from . import lifecycle
    from .window import zone
    tz = zone(ctx.config)
    folder = Path(ctx.live_dir) if getattr(ctx, "live_dir", None) else None
    with ctx.history() as history:
        shown = lifecycle.page_dates(ctx.config, folder, history, ctx.site)
        problems = recheck(history.db, ctx.site, tz, shown, meta_file=(
            (ctx.config or {}).get("report") or {}).get("pages_meta"))
        n = len(_rows(history.db, ctx.site)[0])
    ctx.out(f"page dates: {n} dates of {sum(1 for v in shown.values() if v.get('check'))} "
            "pages read rechecked from the stored rows")
    return problems
