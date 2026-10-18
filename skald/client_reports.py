"""Client reports (Settings > Reports): branded reports a site's admins
schedule for their clients, sent as an HTML mail with a PDF attached.

A report is one row per site in accounts.sqlite (`client_reports`, made
here on first use, like mail_confirms), owned by the site's organisation:
every read and write names the organisation and the site, so one
organisation never sees, previews or sends another's report.

    name        what the client sees on top ("Monthly traffic report")
    recipients  addresses; each one typed on the page must confirm first
                (mail_confirm.py, the rule every Skald mail follows)
    schedule    weekly on a weekday, monthly on day N (a shorter month: its
                last day), or every N days from a start date; at HH:MM in
                the site's time zone
    period      last_week (Monday to Sunday), last_month, month_to_date
                (on the 1st: the whole month before)
    sections    which parts the report shows (SECTIONS)
    notes       the agency's own words, shown as they are typed
    footer      one line at the foot of every page

Each send - scheduled or "Send now" - is a row in `client_report_sends`:
who started it (the schedule or a person), when, the period, the addresses
it went to, ok or the error. A scheduled send that fails is tried once more,
RETRY_AFTER later; then it waits for the next occurrence. Figures are only
ever read from verified history (client_report_data.py).
"""
from __future__ import annotations

import calendar
import json
import re
import sqlite3
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .accounts import db as base

SECTIONS = ("summary", "sources", "pages", "places", "ai", "leads", "search_console", "notes")
SECTION_WORDS = {"summary": "Summary", "sources": "Where visitors came from",
                 "pages": "Top pages", "places": "Countries and cities",
                 "ai": "AI and bots", "leads": "Leads", "search_console": "Search Console",
                 "notes": "Notes"}
PERIODS = ("last_week", "last_month", "month_to_date")
PERIOD_WORDS = {"last_week": "Last week", "last_month": "Last month",
                "month_to_date": "Month to date"}
KINDS = ("weekly", "monthly", "custom")
MAX_REPORTS = 20                  # per site
MAX_RECIPIENTS = 20
MAX_NOTES = 2000
MAX_FOOTER = 160
MAX_NAME = 80
ATTEMPTS = 2                      # a scheduled send: the first try and one retry
RETRY_AFTER = timedelta(minutes=30)
CATCH_UP = timedelta(days=2)      # an occurrence older than this is not sent late
WAIT_FOR_DAY_UNTIL = time(18, 0)  # the period's last day not stored yet: wait until then
HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
EMAIL = re.compile(r"^[^@\s<>,;\"]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,63}$")
TABLES = (
    "CREATE TABLE IF NOT EXISTS client_reports (id INTEGER PRIMARY KEY, "
    "org_id INTEGER NOT NULL, site TEXT NOT NULL, spec TEXT NOT NULL, "
    "created_by TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
    "CREATE INDEX IF NOT EXISTS client_reports_site ON client_reports (org_id, site)",
    "CREATE TABLE IF NOT EXISTS client_report_sends (id INTEGER PRIMARY KEY, "
    "report_id INTEGER NOT NULL, org_id INTEGER NOT NULL, site TEXT NOT NULL, "
    "at TEXT NOT NULL, occurrence TEXT, first TEXT, last TEXT, by TEXT NOT NULL, "
    "recipients TEXT NOT NULL DEFAULT '[]', ok INTEGER NOT NULL, detail TEXT NOT NULL "
    "DEFAULT '')",
    "CREATE INDEX IF NOT EXISTS client_report_sends_report ON client_report_sends "
    "(report_id, id)",
)


class Invalid(ValueError):
    """A report setting that cannot be used, in plain words."""


# ------------------------------------------------------------ the checks

def _clean_email(raw) -> str:
    email = str(raw or "").strip()
    if not EMAIL.match(email) or len(email) > 254:
        raise Invalid(f"{email or 'An empty address'} is not an email address.")
    return email


def validate(raw) -> dict:
    """A report's settings, checked and in their stored shape."""
    if not isinstance(raw, dict):
        raise Invalid("Send the report's settings.")
    name = " ".join(str(raw.get("name") or "").split())
    if not name or len(name) > MAX_NAME:
        raise Invalid(f"Give the report a name of at most {MAX_NAME} characters.")
    people = raw.get("recipients") or []
    if isinstance(people, str):
        people = re.split(r"[\s,;]+", people)
    if not isinstance(people, list):
        raise Invalid("Recipients are a list of addresses.")
    seen, recipients = set(), []
    for p in people:
        if not str(p or "").strip():
            continue
        email = _clean_email(p)
        if email.lower() not in seen:
            seen.add(email.lower())
            recipients.append(email)
    if not recipients:
        raise Invalid("Add at least one recipient.")
    if len(recipients) > MAX_RECIPIENTS:
        raise Invalid(f"At most {MAX_RECIPIENTS} recipients.")
    sched = raw.get("schedule") or {}
    if not isinstance(sched, dict) or sched.get("kind") not in KINDS:
        raise Invalid("Choose when it goes: weekly, monthly or every few days.")
    at = str(sched.get("at") or "08:00")
    if not HHMM.match(at):
        raise Invalid("The time is HH:MM, 24-hour (08:00).")
    schedule = {"kind": sched["kind"], "at": at}
    try:
        if sched["kind"] == "weekly":
            schedule["weekday"] = int(sched.get("weekday", 0))
            if not 0 <= schedule["weekday"] <= 6:
                raise ValueError
        elif sched["kind"] == "monthly":
            schedule["day"] = int(sched.get("day", 1))
            if not 1 <= schedule["day"] <= 31:
                raise ValueError
        else:
            schedule["every"] = int(sched.get("every", 14))
            schedule["start"] = date.fromisoformat(str(sched.get("start"))).isoformat()
            if not 1 <= schedule["every"] <= 92:
                raise ValueError
    except (TypeError, ValueError):
        raise Invalid("Pick a weekday, a day of the month (1 to 31), or every 1 to 92 days "
                      "from a start date.") from None
    period = raw.get("period") or "last_week"
    if period not in PERIODS:
        raise Invalid("The period is last week, last month or month to date.")
    sections = [s for s in SECTIONS if s in (raw.get("sections") or [])]
    if not sections:
        raise Invalid("Choose at least one section.")
    notes = str(raw.get("notes") or "").replace("\r\n", "\n").strip()
    footer = " ".join(str(raw.get("footer") or "").split())
    if len(notes) > MAX_NOTES or len(footer) > MAX_FOOTER:
        raise Invalid(f"Notes are at most {MAX_NOTES} characters, the footer {MAX_FOOTER}.")
    return {"name": name, "recipients": recipients, "schedule": schedule, "period": period,
            "sections": sections, "notes": notes, "footer": footer,
            "agency_logo": raw.get("agency_logo", True) is not False,
            "paused": raw.get("paused") is True}


# ----------------------------------------------------- the schedule's math

def _month_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def scheduled_days(spec: dict, first: date, last: date) -> list[date]:
    """Every local day in [first, last] the report goes on."""
    s = spec["schedule"]
    out = []
    d = first
    while d <= last:
        if s["kind"] == "weekly" and d.weekday() == s["weekday"]:
            out.append(d)
        elif s["kind"] == "monthly" and d == _month_day(d.year, d.month, s["day"]):
            out.append(d)
        elif s["kind"] == "custom":
            start = date.fromisoformat(s["start"])
            if d >= start and (d - start).days % s["every"] == 0:
                out.append(d)
        d += timedelta(days=1)
    return out


def at_local(spec: dict, day: date, tz: ZoneInfo) -> datetime:
    """The moment (UTC) the report goes on `day`, HH:MM in the site's zone. A
    time the clocks skip that day is the same instant zoneinfo gives (an hour on)."""
    h, m = (int(x) for x in spec["schedule"]["at"].split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=tz).astimezone(timezone.utc)


def latest(spec: dict, now: datetime, tz: ZoneInfo) -> date | None:
    """The last scheduled local day whose time has come by `now`, within
    CATCH_UP; None when there is none."""
    today = now.astimezone(tz).date()
    for d in reversed(scheduled_days(spec, today - timedelta(days=3), today)):
        when = at_local(spec, d, tz)
        if when <= now and now - when <= CATCH_UP:
            return d
    return None


def next_send(spec: dict, now: datetime, tz: ZoneInfo) -> datetime | None:
    """The next moment (UTC) after `now` the report goes."""
    today = now.astimezone(tz).date()
    for d in scheduled_days(spec, today, today + timedelta(days=400)):
        when = at_local(spec, d, tz)
        if when > now:
            return when
    return None


def period_for(kind: str, send_day: date) -> tuple[date, date]:
    """(first, last) local days the report sent on `send_day` covers."""
    if kind == "last_week":
        monday = send_day - timedelta(days=send_day.weekday())
        return monday - timedelta(days=7), monday - timedelta(days=1)
    first_of = send_day.replace(day=1)
    if kind == "month_to_date" and send_day.day > 1:
        return first_of, send_day - timedelta(days=1)
    last = first_of - timedelta(days=1)
    return last.replace(day=1), last


def due(spec: dict, sends: list[dict], now: datetime, tz: ZoneInfo,
        created_at: str | None = None) -> date | None:
    """The occurrence (its local day) to send now, or None. Not before the
    report was made, not again after one went, at most ATTEMPTS tries, the
    second RETRY_AFTER after the first."""
    if spec.get("paused"):
        return None
    day = latest(spec, now, tz)
    if day is None:
        return None
    if created_at and at_local(spec, day, tz) < base.parse(created_at):
        return None
    tries = [s for s in sends if s.get("occurrence") == day.isoformat()
             and s.get("by") == "schedule"]
    if any(s["ok"] for s in tries) or len(tries) >= ATTEMPTS:
        return None
    if tries and now - base.parse(max(s["at"] for s in tries)) < RETRY_AFTER:
        return None
    return day


def should_wait(missing_last: bool, now: datetime, tz: ZoneInfo) -> bool:
    """True while the period's last day is not stored yet and it is still
    before WAIT_FOR_DAY_UNTIL locally: the morning run may still bring it."""
    return missing_last and now.astimezone(tz).time() < WAIT_FOR_DAY_UNTIL


# ------------------------------------------------------------- the store

def _ready(db) -> None:
    for sql in TABLES:
        db.execute(sql)


def _row(r) -> dict:
    out = dict(r)
    out["spec"] = json.loads(out["spec"])
    return out


def listing(db, org_id: int, site: str) -> list[dict]:
    _ready(db)
    return [_row(r) for r in db.execute(
        "SELECT * FROM client_reports WHERE org_id = ? AND site = ? ORDER BY id",
        (int(org_id), site))]


def get(db, org_id: int, site: str, report_id) -> dict | None:
    _ready(db)
    try:
        rid = int(report_id)
    except (TypeError, ValueError):
        return None
    row = db.execute("SELECT * FROM client_reports WHERE id = ? AND org_id = ? AND site = ?",
                     (rid, int(org_id), site)).fetchone()
    return _row(row) if row else None


def save(db, org_id: int, site: str, spec: dict, actor, report_id=None) -> dict:
    """Make or change a report (`spec` from validate)."""
    _ready(db)
    body = json.dumps(spec, sort_keys=True)
    with base.tx(db):
        if report_id is None:
            n = db.execute("SELECT COUNT(*) FROM client_reports WHERE org_id = ? AND site = ?",
                           (int(org_id), site)).fetchone()[0]
            if n >= MAX_REPORTS:
                raise Invalid(f"At most {MAX_REPORTS} reports per site.")
            cur = db.execute("INSERT INTO client_reports (org_id, site, spec, created_by, "
                             "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                             (int(org_id), site, body, str(actor), base.now(), base.now()))
            report_id = cur.lastrowid
        elif not db.execute("UPDATE client_reports SET spec = ?, updated_at = ? WHERE id = ? "
                            "AND org_id = ? AND site = ?", (body, base.now(), int(report_id),
                                                            int(org_id), site)).rowcount:
            raise Invalid("There is no such report.")
    return get(db, org_id, site, report_id)


def delete(db, org_id: int, site: str, report_id) -> bool:
    _ready(db)
    with base.tx(db):
        gone = db.execute("DELETE FROM client_reports WHERE id = ? AND org_id = ? AND site = ?",
                          (int(report_id), int(org_id), site)).rowcount
        if gone:
            db.execute("DELETE FROM client_report_sends WHERE report_id = ? AND org_id = ?",
                       (int(report_id), int(org_id)))
    return bool(gone)


def record(db, report: dict, by: str, ok: bool, detail: str, first: date | None = None,
           last: date | None = None, recipients=(), occurrence: date | None = None,
           at: datetime | None = None) -> None:
    _ready(db)
    stamp = at.astimezone(timezone.utc).strftime(base.STAMP) if at else base.now()
    db.execute("INSERT INTO client_report_sends (report_id, org_id, site, at, occurrence, "
               "first, last, by, recipients, ok, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, "
               "?, ?)", (report["id"], report["org_id"], report["site"], stamp,
                         occurrence.isoformat() if occurrence else None,
                         first.isoformat() if first else None,
                         last.isoformat() if last else None, str(by)[:200],
                         json.dumps(list(recipients)), 1 if ok else 0, str(detail)[:500]))


def sends(db, org_id: int, report_id, limit: int = 50) -> list[dict]:
    _ready(db)
    out = []
    for r in db.execute("SELECT * FROM client_report_sends WHERE report_id = ? AND org_id = ? "
                        "ORDER BY id DESC LIMIT ?", (int(report_id), int(org_id), int(limit))):
        row = dict(r)
        row["recipients"] = json.loads(row["recipients"] or "[]")
        row["ok"] = bool(row["ok"])
        out.append(row)
    return out


def org_reports(db, site: str) -> list[dict]:
    """Every report of `site` under the organisation that owns it now; a
    report left from an organisation the site moved away from is not sent."""
    from .accounts.orgs import org_of_site
    try:
        org = org_of_site(db, site)
    except sqlite3.OperationalError:
        return []
    return listing(db, org["id"], site) if org else []


def recipients_state(db, org_id: int, emails, trusted=()) -> tuple[list, list]:
    """(confirmed, waiting) by mail_confirm's rule."""
    from .mail_confirm import keep_confirmed
    return keep_confirmed(db, org_id, emails, trusted)
