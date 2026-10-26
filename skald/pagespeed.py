"""Real page speed: Google PageSpeed Insights for the pages people land on.

The log knows how long the server took to answer ($request_time, kept in
ours.json); it cannot know how long the page took to appear in a browser.
Once a day, after run-daily, this asks Google's PageSpeed Insights API (v5)
about the day before's top PAGES landing pages, on a phone and on a
desktop:

  lab     a Lighthouse run Google does on the spot: the performance score
          (0-100), largest contentful paint, layout shift, blocking time,
          first contentful paint and speed index
  field   what real Chrome users saw over the last 28 days (the Chrome UX
          Report): LCP, CLS and INP at the 75th percentile and Google's
          verdict - only when Google has enough of those users; for the page,
          and for the whole site (origin)

Results go in history's `page_speed` table (schema 10), one row per day,
page and strategy, and into speed.json. These numbers come from Google, not
from the log, so the audit cannot recount them; what is checked instead is
that what is stored is exactly what was read from Google's answer
(`check`, run on every row written).

Never in the way: one call per page and strategy (at most 10 a day; a day
already tested is skipped unless --force), 30 seconds each and one retry,
every failure stored as a failed row with its reason, and the run always
exits 0. A run where Google refused every test is recorded as FAILED all the
same (runs.json), and speed.json's `status` says so in plain words: from
launch to 2026-10-11 every test got HTTP 429 and the run said "ok". PSI_API_KEY in the environment, when set, raises Google's quota;
it is never printed or stored.
"""
from __future__ import annotations

import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from .config import setting

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
STRATEGIES = ("mobile", "desktop")
PAGES = 5
TIMEOUT = 30
ENV_KEY = "PSI_API_KEY"
DAYS = 30
OTHER = "(all others)"

LAB = (("lcp_ms", "largest-contentful-paint"), ("cls", "cumulative-layout-shift"),
       ("tbt_ms", "total-blocking-time"), ("fcp_ms", "first-contentful-paint"),
       ("si_ms", "speed-index"))


# ---------------------------------------------------------------- settings

def enabled(config: dict) -> bool:
    raw = ((config or {}).get("pagespeed") or {}).get("enabled")
    if raw is None or raw == "":
        return bool(setting(config, "site", "hosts"))
    return raw is True or str(raw).strip().lower() in ("1", "true", "yes", "on")


def base_url(config: dict) -> str | None:
    """https://<host> the pages are tested on: pagespeed.base_url, else the
    site's www host, else its first host."""
    given = setting(config, "pagespeed", "base_url")
    if given:
        return str(given).rstrip("/")
    hosts = [str(h) for h in (setting(config, "site", "hosts") or [])]
    if not hosts:
        return None
    host = next((h for h in hosts if h.startswith("www.")), hosts[0])
    return f"https://{host}"


def top_landings(history, site: str, day: date, n: int = PAGES) -> list[str]:
    """The day's top landing pages (readers' first page), else its most read
    pages; never the folded "(all others)" row."""
    for kind in ("reader_landing", "people_page"):
        rows = history.db.execute(
            "SELECT name, n FROM counts WHERE site = ? AND day = ? AND kind = ? "
            "ORDER BY n DESC, name", (site, day.isoformat(), kind)).fetchall()
        paths = [name for name, _ in rows if name != OTHER and name.startswith("/")]
        if paths:
            return paths[:n]
    return []


# -------------------------------------------------------------- the call

def _scrub(text: str, key: str | None) -> str:
    return text.replace(key, "***") if key else text


def fetch(url: str, strategy: str, key: str | None, timeout: float = TIMEOUT,
          opener=None, retries: int = 1, pause: float = 2.0) -> dict:
    """Google's answer as JSON. Raises RuntimeError with a reason that never
    holds the key."""
    query = {"url": url, "strategy": strategy, "category": "performance"}
    if key:
        query["key"] = key
    request = urllib.request.Request(f"{API}?{urllib.parse.urlencode(query)}",
                                     headers={"User-Agent": "skald-pagespeed/1"})
    opener = opener or urllib.request.urlopen
    last = "no answer"
    for attempt in range(retries + 1):
        try:
            with opener(request, timeout=timeout) as answer:
                return json.loads(answer.read(20_000_000).decode("utf-8", "replace"))
        except urllib.error.HTTPError as why:
            last = f"HTTP {why.code}"
            if why.code in (400, 403, 404):
                break                       # a wrong URL or key: retrying will not help
        except (urllib.error.URLError, OSError, ValueError) as why:
            last = f"{type(why).__name__}: {why}"
        if attempt < retries:
            time.sleep(pause)
    raise RuntimeError(_scrub(last, key)[:300])


def _num(value):
    return round(float(value), 4) if isinstance(value, (int, float)) else None


def _experience(block) -> dict | None:
    """LCP, CLS and INP at the 75th percentile, and Google's overall verdict."""
    metrics = (block or {}).get("metrics") or {}
    if not metrics:
        return None

    def p75(name):
        got = (metrics.get(name) or {}).get("percentile")
        return got if isinstance(got, (int, float)) else None

    cls = p75("CUMULATIVE_LAYOUT_SHIFT_SCORE")
    return {"lcp_ms": p75("LARGEST_CONTENTFUL_PAINT_MS"),
            "cls": round(cls / 100, 4) if cls is not None else None,
            "inp_ms": p75("INTERACTION_TO_NEXT_PAINT"),
            "category": (block or {}).get("overall_category")}


def parse(raw: dict) -> dict:
    """{"score", "lab", "field", "origin"} from a v5 answer. Raises ValueError
    when it holds no Lighthouse result."""
    lighthouse = (raw or {}).get("lighthouseResult")
    if not isinstance(lighthouse, dict):
        error = ((raw or {}).get("error") or {}).get("message")
        raise ValueError(f"no Lighthouse result{': ' + error if error else ''}")
    score = ((lighthouse.get("categories") or {}).get("performance") or {}).get("score")
    audits = lighthouse.get("audits") or {}
    lab = {name: _num((audits.get(audit) or {}).get("numericValue")) for name, audit in LAB}
    if lab["cls"] is None and lab["lcp_ms"] is None and score is None:
        raise ValueError("the Lighthouse result holds no performance figures")
    return {"score": round(score * 100, 1) if isinstance(score, (int, float)) else None,
            "lab": lab,
            "field": _experience(raw.get("loadingExperience")),
            "origin": _experience(raw.get("originLoadingExperience"))}


# ----------------------------------------------------------------- store

def store(db, site: str, day: date, path: str, strategy: str, parsed: dict | None,
          error: str | None, now: datetime) -> None:
    with db:
        db.execute(
            "INSERT OR REPLACE INTO page_speed (site, day, path, strategy, ok, error, score, "
            "lab_json, field_json, origin_json, tested_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (site, day.isoformat(), path, strategy, 1 if parsed else 0, error,
             parsed["score"] if parsed else None,
             json.dumps(parsed["lab"], sort_keys=True) if parsed else None,
             json.dumps(parsed["field"], sort_keys=True) if parsed and parsed["field"] else None,
             json.dumps(parsed["origin"], sort_keys=True) if parsed and parsed["origin"] else None,
             now.astimezone(timezone.utc).isoformat(timespec="seconds")))


def _row(r) -> dict:
    site, day, path, strategy, ok, error, score, lab, field, origin, tested = r
    return {"site": site, "day": day, "path": path, "strategy": strategy, "ok": bool(ok),
            "error": error, "score": score, "lab": json.loads(lab) if lab else None,
            "field": json.loads(field) if field else None,
            "origin_field": json.loads(origin) if origin else None, "tested_at": tested}


COLUMNS = ("site, day, path, strategy, ok, error, score, lab_json, field_json, origin_json, "
           "tested_at")


def rows(db, site: str, first: date, last: date) -> list[dict]:
    return [_row(r) for r in db.execute(
        f"SELECT {COLUMNS} FROM page_speed WHERE site = ? AND day BETWEEN ? AND ? "
        "ORDER BY day, path, strategy", (site, first.isoformat(), last.isoformat()))]


def check(db, site: str, day: date, path: str, strategy: str, parsed: dict) -> list[str]:
    """What was stored is exactly what was read from Google's answer."""
    got = [r for r in rows(db, site, day, day) if r["path"] == path and r["strategy"] == strategy]
    if not got:
        return [f"{path} {strategy}: not stored"]
    r = got[0]
    problems = []
    for name, stored, read in (("score", r["score"], parsed["score"]), ("lab", r["lab"], parsed["lab"]),
                               ("field", r["field"], parsed["field"]),
                               ("origin", r["origin_field"], parsed["origin"])):
        if stored != read:
            problems.append(f"{path} {strategy}: {name} stored {stored!r}, read {read!r}")
    return problems


# ------------------------------------------------------------------- run

def test_day(history, site: str, config: dict, day: date, now: datetime, force: bool = False,
             opener=None, out=print, err=print) -> dict:
    """Test the day's top landing pages. {"tested","failed","skipped"}."""
    base = base_url(config)
    paths = top_landings(history, site, day)
    # Only answered tests count as done: one Google refused (quota, a 429) is
    # tried again on the next run.
    done = {(r["path"], r["strategy"]) for r in rows(history.db, site, day, day) if r["ok"]}
    tally = {"tested": 0, "failed": 0, "skipped": 0}
    if base is None or not paths:
        err(f"pagespeed {day}: " + ("no site host to test" if base is None
                                    else "no landing pages recorded for the day"))
        return tally
    key = _key(config)
    for path in paths:
        for strategy in STRATEGIES:
            if (path, strategy) in done and not force:
                tally["skipped"] += 1
                continue
            url = base + path
            try:
                parsed, error = parse(fetch(url, strategy, key, opener=opener)), None
            except (RuntimeError, ValueError) as why:
                parsed, error = None, _scrub(str(why), key)[:300]
            store(history.db, site, day, path, strategy, parsed, error, now)
            if parsed is not None:
                problems = check(history.db, site, day, path, strategy, parsed)
                if problems:
                    err("pagespeed: STORED DIFFERS FROM GOOGLE'S ANSWER: " + "; ".join(problems))
                tally["tested"] += 1
                out(f"pagespeed {day} {strategy:<7} {path}: score {parsed['score']}")
            else:
                tally["failed"] += 1
                err(f"pagespeed {day} {strategy:<7} {path}: failed ({error})")
    return tally


def _key(config: dict) -> str | None:
    """PSI_API_KEY from the environment, else from secrets.json (typed in
    Settings > Mail & reports by an install admin). Never printed."""
    from .settings_store import secret_value
    try:
        return (secret_value(config, "pagespeed.api_key") or "").strip() or None
    except PermissionError:
        return os.environ.get(ENV_KEY, "").strip() or None


def run(ctx, day: date | None = None, force: bool = False, opener=None) -> int:
    """The run-daily step: yesterday's top landing pages. Always exits 0."""
    from . import runs
    from .window import yesterday
    if not enabled(ctx.config):
        return 0
    day = day or yesterday(ctx.tz, ctx.now)
    try:
        with ctx.history() as history:
            tally = test_day(history, ctx.site, ctx.config, day, ctx.now, force, opener,
                             ctx.out, ctx.err)
        ctx.out("pagespeed: " + ", ".join(f"{k} {v}" for k, v in tally.items()))
        if tally["failed"] and not tally["tested"]:
            # Nothing measured is a failure, whatever the exit code says.
            ctx.err("pagespeed: FAILED - Google refused every test")
            runs.record(ctx.live_dir, "pagespeed", 1)
        else:
            runs.record(ctx.live_dir, "pagespeed", 0)
    except Exception as why:            # noqa: BLE001 - never stops the day
        ctx.err(f"pagespeed: {type(why).__name__}: {_scrub(str(why), _key(ctx.config))}")
        runs.record(ctx.live_dir, "pagespeed", 1)
    return 0


def cmd_pagespeed(ctx) -> int:
    from .window import parse_day
    day = parse_day(ctx.args.day, ctx.tz, ctx.now) if ctx.args.day else None
    return run(ctx, day, ctx.args.force)


def add_command(sub) -> None:
    p = sub.add_parser("pagespeed", help="Google PageSpeed Insights for the day's top landing "
                       "pages, phone and desktop (run-daily runs it last)")
    p.add_argument("--day", help="the day whose landing pages to test (default yesterday)")
    p.add_argument("--force", action="store_true", help="test again pages already tested")
    p.set_defaults(run=cmd_pagespeed)


# ------------------------------------------------------------ speed.json

NO_KEY = ("Not working: Google refused every test. A free PageSpeed API key is needed "
          f"({ENV_KEY} in /etc/skald/env).")


def status(tests: list[dict]) -> dict:
    """The newest tested day: "ok" when any test was answered, "failing" when
    Google answered none, "not tested" when there is no test at all."""
    days = sorted({t["day"] for t in tests})
    if not days:
        return {"state": "not tested", "day": None, "message": None}
    newest = [t for t in tests if t["day"] == days[-1]]
    if any(t["ok"] for t in newest):
        return {"state": "ok", "day": days[-1], "message": None}
    errors = sorted({str(t["error"] or "no reason given") for t in newest})
    refused = any("429" in e or "quota" in e.lower() for e in errors)
    message = NO_KEY if refused else ("Not working: every test failed (" + "; ".join(errors)[:200]
                                      + ").")
    return {"state": "failing", "day": days[-1], "message": message, "errors": errors}


def _median(values):
    got = [v for v in values if isinstance(v, (int, float))]
    return round(statistics.median(got), 4) if got else None


def build(p) -> dict:
    site = p.key.split("::", 1)[0]
    last = p.today
    first = last - timedelta(days=DAYS - 1)
    base = base_url(p.config) or ""
    try:
        found = rows(p.history.db, site, first, last)
    except Exception:                   # noqa: BLE001 - an older history: no table yet
        found = []
    tests = [{"url": base + r["path"], "path": r["path"], "strategy": r["strategy"],
              "ok": r["ok"], "error": r["error"], "score": r["score"], "lab": r["lab"],
              "field": r["field"], "origin_field": r["origin_field"], "day": r["day"]}
             for r in found]
    days = []
    for i in range(DAYS):
        d = (first + timedelta(days=i)).isoformat()
        days.append({"day": d, "tests": [{k: v for k, v in t.items() if k != "day"}
                                          for t in tests if t["day"] == d]})
    latest: dict[tuple, dict] = {}
    for t in tests:                     # oldest first, so the newest wins
        latest[(t["path"], t["strategy"])] = t
    trend = {}
    for strategy in STRATEGIES:
        series = []
        for d in days:
            ok = [t for t in d["tests"] if t["strategy"] == strategy and t["ok"]]
            if not ok:
                continue
            series.append({"day": d["day"],
                           "score": _median(t["score"] for t in ok),
                           "lcp_ms": _median((t["lab"] or {}).get("lcp_ms") for t in ok),
                           "cls": _median((t["lab"] or {}).get("cls") for t in ok),
                           "inp_ms": _median((t["field"] or {}).get("inp_ms") for t in ok)})
        trend[strategy] = series
    return {"source": "Google PageSpeed Insights v5", "days": days, "status": status(tests),
            "latest": sorted(latest.values(), key=lambda t: (t["path"], t["strategy"])),
            "trend": trend}
