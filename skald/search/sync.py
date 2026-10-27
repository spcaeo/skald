"""The sync: Search Console and Bing figures into history, by themselves.

Once a site is connected (Settings > Leads & tools > Search Console & Bing), the container's
scheduler runs `skald search sync` every EVERY_HOURS hours (docker/scheduler.py,
SKALD_SEARCH_HOURS), one site after another under each site's lock. A sync:

Search Console (per site property, `search_console.property`):
  1. asks for the last NEWEST_WINDOW days with dataState "all" to find the
     newest day Google has, and where its data stops being final (the
     answer's metadata.first_incomplete_date);
  2. fetches from the earliest of: the day after the newest stored day, the
     REFETCH_DAYS days before the newest day, and any stored day still
     provisional - to the newest day; replacing what was stored;
  3. per CHUNK_DAYS days: the day totals (by property and by page), then
     query, page, country, device and search appearance, each grouped by date
     (search appearance alone per day if Google refuses it with the date);
  4. folds each day and kind (days.fold: top rows, "(all others)" and what
     Google does not attribute) and writes it, read back and checked.
  A day after the newest Google has is never stored; a day inside the range
  that Google leaves out had no impressions (Google omits empty days) and is
  stored as 0. Google keeps 16 months: nothing older is asked for.

Bing (per site, `bing.site_url`): one call each for the daily traffic and
the top queries and pages; every day Bing returns is replaced. Days older
than days.BING_FINAL_DAYS are final.

The first connection's history (3 or 16 months) is a backfill: the same
fetch, chunk by chunk, with its progress in the state file
(`--backfill-months`), started in the background by the connect wizard.

A failure is kept in the state file in plain words; the first failure of a
run of failures sends one mail to the site's mail recipients (never one per
run); a good sync clears it. A sync never touches the log's figures.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import setting
from . import bing, days, google, http, props, state

PACIFIC = ZoneInfo("America/Los_Angeles")
NEWEST_WINDOW = 10
REFETCH_DAYS = 4
FIRST_DAYS = 28
CHUNK_DAYS = 7
KEEP_DAYS = 486                         # Search Console keeps 16 months
EVERY_HOURS = 6
DIMENSIONS = {"query": "query", "page": "page", "country": "country", "device": "device",
              "appearance": "searchAppearance"}
ENGINE_NAMES = {"google": "Search Console", "bing": "Bing Webmaster Tools"}


@dataclass
class Job:
    """One site's sync. `opener`, `sleep`, `api` and `token_url` are for tests."""
    config: dict
    site: str
    folder: Path                        # the history's folder
    db_path: Path
    now: datetime
    out: object = print
    err: object = print
    opener: object = None
    sleep: object = time.sleep
    send: object = None                 # mail sender (failmail.send); tests hand one in
    api: dict = field(default_factory=dict)

    def history(self):
        from ..store import History
        return History(self.db_path)


def google_property(config: dict) -> str | None:
    got = setting(config or {}, "search_console", "property")
    return str(got).strip() if got else None


def bing_site(config: dict) -> str | None:
    got = setting(config or {}, "bing", "site_url")
    return str(got).strip() if got else None


def connected(config: dict) -> dict:
    return {"google": google_property(config), "bing": bing_site(config)}


def pacific_today(now: datetime) -> date:
    return now.astimezone(PACIFIC).date()


def _days(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def google_client(job: Job) -> google.Client:
    text, where = google.find_key(job.config, job.folder)
    if not text:
        raise http.Failed(0, "No service-account key: an install admin uploads one in "
                             "Settings > Leads & tools > Search Console & Bing.")
    extra = {}
    if job.api.get("google_api"):
        extra["api"] = job.api["google_api"]
    if job.api.get("google_token_url"):
        extra["token_url"] = job.api["google_token_url"]
    try:
        return google.Client(text, opener=job.opener, sleep=job.sleep, **extra)
    except google.BadKey as why:
        raise http.Failed(0, f"The service-account key cannot be used: {why}") from None


def bing_client(job: Job) -> bing.Client:
    key, _ = bing.find_key(job.config, job.folder)
    if not key:
        raise http.Failed(0, "No Bing API key: an install admin types one in "
                             "Settings > Leads & tools > Search Console & Bing.")
    try:
        return bing.Client(key, opener=job.opener, sleep=job.sleep,
                           **({"api": job.api["bing_api"]} if job.api.get("bing_api") else {}))
    except bing.BadKey as why:
        raise http.Failed(0, str(why)) from None


# ------------------------------------------------------------ Search Console

def _row(r: dict, at: int = 1) -> list:
    keys = r.get("keys") or []
    return [str(keys[at]) if len(keys) > at else "", r.get("clicks"), r.get("impressions"),
            r.get("position")]


def newest(client, prop: str, today: date) -> tuple[date | None, date | None]:
    """(the newest day Google has, its first incomplete day or None)."""
    rows, meta = client.query(prop, {
        "startDate": (today - timedelta(days=NEWEST_WINDOW)).isoformat(),
        "endDate": today.isoformat(), "dimensions": ["date"], "type": "web",
        "dataState": "all", "aggregationType": "byProperty"})
    have = sorted(date.fromisoformat(r["keys"][0]) for r in rows if r.get("keys"))
    incomplete = meta.get("first_incomplete_date")
    return (have[-1] if have else None,
            date.fromisoformat(incomplete) if incomplete else None)


def earliest(client, prop: str, first: date, last: date) -> date | None:
    """The first day in [first, last] Search Console has any figure for."""
    rows, _ = client.query(prop, {"startDate": first.isoformat(), "endDate": last.isoformat(),
                                  "dimensions": ["date"], "type": "web", "dataState": "all",
                                  "aggregationType": "byProperty"})
    have = [r["keys"][0] for r in rows if r.get("keys")]
    return date.fromisoformat(min(have)) if have else None


def fetch_google(client, prop: str, first: date, last: date,
                 floor: date | None = None) -> tuple[dict, dict, int]:
    """({day: {kind: blob}}, {day: final}, rows read) for [first, last].
    A day with no row is stored as 0 only from `floor` (the property's first
    day with data) on; before it, Google has nothing, which is not a zero."""
    base = {"startDate": first.isoformat(), "endDate": last.isoformat(), "type": "web",
            "dataState": "all"}
    totals, meta = client.query(prop, {**base, "dimensions": ["date"],
                                       "aggregationType": "byProperty"})
    by_page, _ = client.query(prop, {**base, "dimensions": ["date"],
                                     "aggregationType": "byPage"})
    incomplete = meta.get("first_incomplete_date")
    read = len(totals) + len(by_page)

    def per_day(rows):
        return {r["keys"][0]: {"clicks": r.get("clicks"), "impressions": r.get("impressions"),
                               "position": r.get("position")} for r in rows if r.get("keys")}

    total, page_total = per_day(totals), per_day(by_page)
    zero = {"clicks": 0, "impressions": 0, "position": None}
    grouped: dict[str, dict[str, list]] = {}
    for kind, dimension in DIMENSIONS.items():
        try:
            rows, _ = client.query(prop, {**base, "dimensions": ["date", dimension]})
        except http.Failed as why:
            if kind != "appearance" or why.code != 400:
                raise
            rows = []                   # search appearance alone, one day at a time
            for d in _days(first, last):
                got, _ = client.query(prop, {**base, "startDate": d.isoformat(),
                                             "endDate": d.isoformat(),
                                             "dimensions": ["searchAppearance"]})
                rows += [{**r, "keys": [d.isoformat(), *(r.get("keys") or [])]} for r in got]
        read += len(rows)
        for r in rows:
            if r.get("keys"):
                grouped.setdefault(kind, {}).setdefault(r["keys"][0], []).append(_row(r))
    out, finals = {}, {}
    if floor is None:
        floor = min((date.fromisoformat(k) for k in total), default=last + timedelta(days=1))
    for d in _days(max(first, floor), last):
        k = d.isoformat()
        t = total.get(k, zero)
        blobs = {"total": days.fold([["(all)", t["clicks"], t["impressions"], t["position"]]],
                                    t, 1)}
        for kind in DIMENSIONS:
            blobs[kind] = days.fold((grouped.get(kind) or {}).get(k, []),
                                    page_total.get(k, zero) if kind == "page" else t,
                                    days.TOP[kind])
        out[d] = blobs
        finals[d] = incomplete is None or k < incomplete
    return out, finals, read


def plan_google(db, site: str, newest_day: date, today: date, backfill_days: int | None,
                refetch: int) -> tuple[date, date]:
    have = days.summary(db, site, "google")
    oldest = today - timedelta(days=KEEP_DAYS)
    if backfill_days:
        first = newest_day - timedelta(days=backfill_days - 1)
    elif not have["last"]:
        first = newest_day - timedelta(days=FIRST_DAYS - 1)
    else:
        first = min(date.fromisoformat(have["last"]) + timedelta(days=1),
                    newest_day - timedelta(days=refetch))
        waiting = days.provisional(db, site, "google")
        if waiting:
            first = min(first, date.fromisoformat(waiting[0]))
    return max(first, oldest), newest_day


def sync_google(job: Job, refetch: int = REFETCH_DAYS, backfill_months: int | None = None,
                client=None) -> dict:
    prop = google_property(job.config)
    client = client or google_client(job)
    today = pacific_today(job.now)
    newest_day, _ = newest(client, prop, today)
    if newest_day is None:
        return {"days": 0, "rows": 0, "first": None, "last": None,
                "note": "Search Console has no data for this property in the last "
                        f"{NEWEST_WINDOW} days."}
    backfill_days = min(KEEP_DAYS, backfill_months * 30 + 6) if backfill_months else None
    with job.history() as history:
        first, last = plan_google(history.db, job.site, newest_day, today, backfill_days, refetch)
        have = days.summary(history.db, job.site, "google")["first"]
    floor = earliest(client, prop, first, last)
    if have:
        floor = min(floor, date.fromisoformat(have)) if floor else date.fromisoformat(have)
    floor = floor or last + timedelta(days=1)
    chunks = []
    at = first
    while at <= last:
        chunks.append((at, min(last, at + timedelta(days=CHUNK_DAYS - 1))))
        at += timedelta(days=CHUNK_DAYS)
    began = state.now_text()
    if backfill_months:
        state.update(job.folder, job.site, "google", backfill={
            "state": "running", "months": backfill_months, "done": 0, "of": len(chunks),
            "started_at": began, "finished_at": None, "error": None})
    stored = rows = 0
    for n, (a, b) in enumerate(reversed(chunks), 1):    # newest first: useful soonest
        got, finals, read = fetch_google(client, prop, a, b, floor)
        with job.history() as history:
            stored += days.write(history.db, job.site, "google", got, finals, prop, job.now)
        rows += read
        job.out(f"search-console {job.site} {a}..{b}: {read} rows")
        if backfill_months:
            state.update(job.folder, job.site, "google", backfill={
                "state": "running" if n < len(chunks) else "done", "months": backfill_months,
                "done": n, "of": len(chunks), "started_at": began, "error": None,
                "finished_at": state.now_text() if n == len(chunks) else None})
    return {"days": (last - first).days + 1, "rows": rows, "first": first.isoformat(),
            "last": last.isoformat(), "calls": getattr(client, "calls", None)}


# --------------------------------------------------------------------- Bing

def fetch_bing(client, site_url: str, today: date, keep_days: int | None = None):
    traffic = client.traffic(site_url)
    tables = {kind: client.stats(site_url, kind) for kind in ("query", "page")}
    floor = today - timedelta(days=keep_days) if keep_days else None
    out: dict = {}
    for r in traffic:
        if floor is None or r["day"] >= floor:
            t = {"clicks": r["clicks"], "impressions": r["impressions"], "position": None}
            out.setdefault(r["day"], {})["total"] = days.fold(
                [["(all)", r["clicks"], r["impressions"], None]], t, 1)
    for kind, rows in tables.items():
        by_day: dict = {}
        for r in rows:
            if floor is None or r["day"] >= floor:
                by_day.setdefault(r["day"], []).append(
                    [r["key"], r["clicks"], r["impressions"], r["position"]])
        for d, got in by_day.items():
            out.setdefault(d, {})[kind] = days.fold(got, None, days.TOP[kind])
    finals = {d: (today - d).days >= days.BING_FINAL_DAYS for d in out}
    read = len(traffic) + sum(len(v) for v in tables.values())
    return out, finals, read


def sync_bing(job: Job, keep_days: int | None = None, client=None) -> dict:
    site_url = bing_site(job.config)
    client = client or bing_client(job)
    got, finals, read = fetch_bing(client, site_url, job.now.date(), keep_days)
    with job.history() as history:
        days.write(history.db, job.site, "bing", got, finals, site_url, job.now)
    span = sorted(got)
    job.out(f"bing {job.site}: {len(span)} days, {read} rows")
    return {"days": len(span), "rows": read, "first": span[0].isoformat() if span else None,
            "last": span[-1].isoformat() if span else None}


# ------------------------------------------------------------- one engine

def test(job: Job, engine: str, source: str, client=None) -> dict:
    """The connect wizard's "Test connection": the last 3 days, read and
    folded but never stored. {"ok", "rows", "clicks", "impressions", "days"}."""
    if engine == "google":
        client = client or google_client(job)
        today = pacific_today(job.now)
        newest_day, _ = newest(client, source, today)
        if newest_day is None:
            return {"ok": True, "rows": 0, "clicks": 0, "impressions": 0, "days": [],
                    "note": "Connected, but Search Console has no data for the last "
                            f"{NEWEST_WINDOW} days."}
        got, _, read = fetch_google(client, source, newest_day - timedelta(days=2), newest_day)
    else:
        client = client or bing_client(job)
        got, _, read = fetch_bing(client, source, job.now.date(), 14)
    totals = [b["total"]["total"] for b in got.values() if "total" in b]
    return {"ok": True, "rows": read, "days": sorted(d.isoformat() for d in got),
            "clicks": days._clean(sum(t["clicks"] for t in totals)),
            "impressions": days._clean(sum(t["impressions"] for t in totals))}


def run(job: Job, engine: str, **options) -> int:
    """Sync one engine for the job's site, under its lock, recording the
    outcome. 0: synced or not connected; 1: failed; 3: another sync holds
    the lock."""
    source = connected(job.config)[engine]
    if not source:
        return 0
    try:
        with state.lock(job.folder, job.site):
            started = state.now_text(job.now)
            hosts = setting(job.config, "site", "hosts") or []
            if hosts and not props.covers(source, hosts):
                return _failed(job, engine, source, f"{source} does not cover this site's host "
                               f"names ({', '.join(map(str, hosts))}); connect a property "
                               "of this site in Settings > Leads & tools > Search Console & Bing.", started)
            try:
                if engine == "google":
                    got = sync_google(job, **options)
                else:
                    got = sync_bing(job, **options)
            except (http.Failed, ValueError, OSError) as why:
                return _failed(job, engine, source, str(why), started,
                               backfill="backfill_months" in options
                               and options["backfill_months"])
            _ok(job, engine, source, got, started)
            return 0
    except state.Busy as why:
        job.err(f"{engine} {job.site}: {why}")
        return 3


def _summary(job: Job, engine: str) -> dict:
    try:
        with job.history() as history:
            return days.summary(history.db, job.site, engine)
    except Exception:                   # noqa: BLE001 - a status, never a stop
        return {}


def _next(now: datetime | None = None) -> str:
    """About when the scheduler syncs next: EVERY_HOURS after `now` (the sync's end,
    the moment last_sync records), as state.py says."""
    return state.now_text((now or datetime.now(timezone.utc)) + timedelta(hours=EVERY_HOURS))


def _ok(job: Job, engine: str, source: str, got: dict, started: str) -> None:
    ended = datetime.now(timezone.utc)
    state.update(job.folder, job.site, engine, ok=True, source=source, last_sync=state.now_text(ended),
                 last_ok=state.now_text(ended), started_at=started, error=None, error_since=None,
                 error_mailed=None, rows=got.get("rows"), note=got.get("note"),
                 next_sync=_next(ended), **_summary(job, engine))


def _failed(job: Job, engine: str, source: str, why: str, started: str, backfill=None) -> int:
    job.err(f"{engine} {job.site}: FAILED: {why}")
    before = state.load(job.folder, job.site).get(engine) or {}
    ended = datetime.now(timezone.utc)
    fields = dict(ok=False, source=source, last_sync=state.now_text(ended), started_at=started,
                  error=why[:600], error_since=before.get("error_since") or state.now_text(ended),
                  next_sync=_next(ended), **_summary(job, engine))
    if backfill:
        fields["backfill"] = {**(before.get("backfill") or {}), "state": "failed",
                              "error": why[:300], "finished_at": state.now_text()}
    part = state.update(job.folder, job.site, engine, **fields)
    if not part.get("error_mailed"):
        if _mail(job, engine, why):
            state.update(job.folder, job.site, engine, error_mailed=state.now_text())
    return 1


def _mail(job: Job, engine: str, why: str) -> bool:
    """One plain mail about a sync that started failing. True when sent."""
    from .. import failmail
    try:
        cfg = failmail.mail_settings(job.config)
    except Exception as refused:        # noqa: BLE001 - no mail set up: the page shows it
        job.err(f"{engine} {job.site}: no failure mail ({refused})")
        return False
    name = ENGINE_NAMES[engine]
    msg = EmailMessage()
    msg["Subject"] = f"{cfg['prefix']} {name} sync failing for {job.site}".strip()
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(cfg["to"])
    msg["Date"] = format_datetime(job.now)
    msg["Message-ID"] = make_msgid(domain=cfg["from"].rsplit("@", 1)[-1].strip("> ") or None)
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content("\n".join([
        f"Skald could not sync {name} for {job.site} ({job.now:%Y-%m-%d %H:%M} UTC).",
        "", f"Why: {why}", "",
        "Search figures already synced stay on the Search tab. Skald keeps trying every "
        f"{EVERY_HOURS} hours; the first good sync clears this.",
        "Status and the fix: Settings > Leads & tools > Search Console & Bing.", "",
        "One mail per run of failures: no more mails until it works again and then fails.",
    ]) + "\n")
    try:
        (job.send or failmail.send)(msg, cfg)
    except Exception as failed:         # noqa: BLE001
        job.err(f"{engine} {job.site}: the failure mail could not be sent "
                f"({type(failed).__name__})")
        return False
    return True


# ------------------------------------------------------------------- the CLI

def job_of(ctx) -> Job:
    return Job(ctx.config, ctx.site, Path(ctx.db_path).parent, Path(ctx.db_path),
               ctx.now.astimezone(timezone.utc), ctx.out, ctx.err)


def _status(ctx, engines) -> int:
    got = state.load(Path(ctx.db_path).parent, ctx.site)
    for engine in engines:
        source = connected(ctx.config)[engine]
        part = got.get(engine) or {}
        ctx.out(f"{ENGINE_NAMES[engine]} {ctx.site}: "
                + (f"connected to {source}" if source else "not connected")
                + (f"; last sync {part.get('last_sync')} "
                   f"({'ok' if part.get('ok') else 'FAILED: ' + str(part.get('error'))})"
                   if part.get("last_sync") else "")
                + (f"; {part.get('days')} days, newest {part.get('last')}, "
                   f"{part.get('provisional')} provisional" if part.get("days") else ""))
    return 0


def cmd(ctx, engines) -> int:
    a = ctx.args
    if a.action == "status":
        return _status(ctx, engines)
    job = job_of(ctx)
    codes = []
    for engine in engines:
        if not connected(ctx.config)[engine]:
            continue
        options = {}
        if engine == "google":
            options["refetch"] = max(1, a.days or REFETCH_DAYS)
            if getattr(a, "backfill_months", None):
                options = {"backfill_months": a.backfill_months}
        elif a.days:
            options["keep_days"] = a.days
        codes.append(run(job, engine, **options))
    return max(codes) if codes else 0


def add_command(sub) -> None:
    for name, engines, words in (
            ("search-console", ("google",), "Google Search Console"),
            ("bing", ("bing",), "Bing Webmaster Tools"),
            ("search", ("google", "bing"), "Search Console and Bing")):
        p = sub.add_parser(name, help=f"sync {words} figures into history (the scheduler runs "
                                      f"`search sync` every {EVERY_HOURS} hours)")
        p.add_argument("action", choices=("sync", "import", "status"),
                       help="sync (import is the same): fetch the newest days and the last "
                            "days again; status: what is connected and how the last sync went")
        p.add_argument("--days", type=int, help="fetch this many recent days again "
                       f"(default {REFETCH_DAYS}; Bing: keep only the last N days it returns)")
        if "google" in engines:
            p.add_argument("--backfill-months", type=int, choices=(3, 16),
                           help="fetch this much history first (Search Console keeps 16 months)")
        p.set_defaults(run=lambda ctx, e=engines: cmd(ctx, e))
