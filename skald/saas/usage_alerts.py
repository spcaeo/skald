"""Usage alerts (owner, 2026-10-26): "we also send alerts to upgrade your plan when you
reach 80%, 90%, 100% so that your data is not lost".

Past its plan's `requests_month`, an organisation's new log batches are turned away
(ingest.quota, 429): Skald's shipper keeps the lines and sends them again, a Cloudflare
Worker's are lost. These mails warn its owners and admins before that happens.

  figure     limits.usage, the one `over_limit` reads: the organisation's sites' requests
             in this calendar month (limits.month_now) from the history's stored days,
             checked twice (audit_usage.py). Unknown or withheld: no alert
  marks      80, 90 and 100 % of the plan's requests_month (used * 100 >= mark * limit).
             No plan, no requests_month, or saas off: nothing
  once       usage_alerts (org, month, limit, mark) in accounts.sqlite: a mark is decided
             once a month per limit, and the row is written BEFORE anything is sent
             (decision D93's rule), so a restart, a recount (usage going down, then up
             again) or a second run never repeats one; a crash while sending loses that
             one mail instead. A failed send is noted on the row and in the audit log,
             not retried
  jump       straight past several marks: one mail, for the highest; the ones below are
             kept as "skipped"
  new limit  a bigger limit in the month starts again from the new limit's marks that the
             usage had not passed at the last check (those it had are kept as "skipped",
             unmailed). A smaller limit is treated as new: its highest passed mark mails
  who        the organisation's owners and admins (confirmed, not disabled), one mail each;
             viewers never. The audit log gets one `billing.usage_alert` row per alert:
             the mark and the counts, never an address
  when       after every live run and run-daily (summary_mail.after_run): at most one check
             per organisation per CHECK_MINUTES, run-daily always (it stores the day the
             figure is made of). Never inside an ingest request
  switch     `saas.usage_alerts: false` stops the mails and the dashboard's banner; on by
             default when saas is on. A self-hosted install (saas off) sees no change

The mail (saas/mails.usage_mail) has one button to Settings > Billing & usage on the
organisation's own dashboard: its first site's `dashboard.url` (multisite.own_url, the
2.36.1 rule), else access.base_url + /traffic/<site>/.
"""
from __future__ import annotations

from datetime import date

from . import enabled, section
from ..accounts import auditlog
from ..accounts import db as base

MARKS = (80, 90, 100)
CHECK_MINUTES = 5          # at most one check per organisation this often (live runs: 2 min)
KEEP_MONTHS = 13           # decided rows older than this are dropped
OFF = ("false", "off", "no", "0")
ROLES = ("owner", "admin")

TABLES = (
    "CREATE TABLE IF NOT EXISTS usage_alerts (org_id INTEGER NOT NULL, month TEXT NOT NULL, "
    "requests_limit INTEGER NOT NULL, mark INTEGER NOT NULL, state TEXT NOT NULL, "
    "used INTEGER, decided_at TEXT NOT NULL, "
    "PRIMARY KEY (org_id, month, requests_limit, mark))",
    "CREATE TABLE IF NOT EXISTS usage_checks (org_id INTEGER PRIMARY KEY, "
    "checked_at TEXT NOT NULL, month TEXT NOT NULL, requests_limit INTEGER, used INTEGER)",
)


def on(config) -> bool:
    """saas is on and `saas.usage_alerts` is not switched off (on by default)."""
    if not enabled(config):
        return False
    got = section(config).get("usage_alerts")
    return not (got is False or (isinstance(got, str) and got.strip().lower() in OFF))


def percent(used, limit) -> int | None:
    """Whole per cent used, rounded down (79.99 % is 79), or None when not known."""
    if used is None or not limit:
        return None
    return int(used) * 100 // int(limit)


def passed(used, limit) -> list[int]:
    """The marks `used` has reached against `limit`, lowest first."""
    if used is None or not limit:
        return []
    return [m for m in MARKS if int(used) * 100 >= m * int(limit)]


def mark(used, limit) -> int | None:
    """The highest mark reached, or None."""
    got = passed(used, limit)
    return got[-1] if got else None


def resets_on(month: str) -> str:
    """The day the count starts again: "1 November 2026" for "2026-10"."""
    year, mon = int(month[:4]), int(month[5:7])
    first = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    return f"1 {first:%B %Y}"


def _ready(db) -> None:
    for sql in TABLES:
        db.execute(sql)


# ------------------------------------------------------------------ the check

def check(db, org_id, config, history_path, *, force=False, link=None, send=None) -> dict | None:
    """Check one organisation; mail its owners and admins when it reached a new mark.
    Returns {"mark", "used", "limit", "month", "sent", "failed", "people"} for an alert
    decided now, else None. `link` is the Billing address for its mails (None: no button);
    `send(msg, config, to)` replaces accounts.mails.deliver in tests."""
    from . import limits
    if not on(config):
        return None
    _ready(db)
    prev = base.one(db, "SELECT checked_at, month, requests_limit, used FROM usage_checks "
                        "WHERE org_id = ?", (org_id,))
    if not force and prev and prev["checked_at"] > base.shift(-CHECK_MINUTES * 60):
        return None
    got = limits.limits_for(db, org_id, config)
    limit = got["requests_month"] if got else None
    month = limits.month_now()
    used = None
    if limit:
        sites = [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))]
        used = limits.usage(history_path, sites, month)["requests"]
    with base.tx(db):
        db.execute("INSERT OR REPLACE INTO usage_checks (org_id, checked_at, month, "
                   "requests_limit, used) VALUES (?, ?, ?, ?, ?)",
                   (org_id, base.now(), month, limit, used))
        if not limit or used is None:
            return None
        decided = {r[0] for r in db.execute(
            "SELECT mark FROM usage_alerts WHERE org_id = ? AND month = ? AND requests_limit = ?",
            (org_id, month, limit))}
        if (not decided and prev and prev["month"] == month and prev["requests_limit"]
                and limit > prev["requests_limit"]):
            # A bigger plan this month: the marks the usage had already passed under the
            # new limit at the last check are not news; only the ones still ahead mail.
            for m in passed(prev["used"], limit):
                _decide(db, org_id, month, limit, m, "skipped", prev["used"])
                decided.add(m)
        now_marks = passed(used, limit)
        if not now_marks or any(m >= now_marks[-1] for m in decided):
            return None
        top = now_marks[-1]
        for m in now_marks:
            if m not in decided:
                _decide(db, org_id, month, limit, m, "sending" if m == top else "skipped", used)
        db.execute("DELETE FROM usage_alerts WHERE month < ?", (_months_ago(month, KEEP_MONTHS),))
    return _send(db, org_id, config, got["plan"], month, limit, used, top, link, send)


def _decide(db, org_id, month, limit, m, state, used) -> None:
    db.execute("INSERT OR IGNORE INTO usage_alerts (org_id, month, requests_limit, mark, state, "
               "used, decided_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
               (org_id, month, limit, m, state, used, base.now()))


def _months_ago(month: str, n: int) -> str:
    year, mon = int(month[:4]), int(month[5:7]) - n
    while mon < 1:
        year, mon = year - 1, mon + 12
    return f"{year:04d}-{mon:02d}"


def recipients(db, org_id) -> list[dict]:
    """The organisation's owners and admins with a confirmed, working account."""
    return base.rows(db, "SELECT u.id AS user_id, u.email, m.role FROM members m JOIN users u "
                         "ON u.id = m.user_id WHERE m.org_id = ? AND m.role IN ('owner', 'admin') "
                         "AND u.pw_hash IS NOT NULL AND u.disabled_at IS NULL ORDER BY u.id",
                     (org_id,))


def _send(db, org_id, config, plan, month, limit, used, top, link, send) -> dict:
    from ..accounts import mails as account_mails
    from .mails import usage_mail
    org = base.one(db, "SELECT name FROM orgs WHERE id = ?", (org_id,)) or {"name": ""}
    people = recipients(db, org_id)
    sent, failed = 0, []
    for p in people:
        try:
            msg = usage_mail(config, p["email"], org["name"], plan, used, limit, month, top, link)
            (send or account_mails.deliver)(msg, config, p["email"])
            sent += 1
        except Exception as why:           # noqa: BLE001 - noted, never stops the run
            failed.append(type(why).__name__)
    state = "sent" if sent else ("no one" if not people else "failed")
    pct = percent(used, limit)
    detail = (f"{used:,} of {limit:,} requests in {month} ({pct}%), {plan} plan; mailed "
              f"{sent} of {len(people)} owners and admins")
    if failed:
        detail += f"; not sent: {', '.join(sorted(set(failed)))}"
    with base.tx(db):
        db.execute("UPDATE usage_alerts SET state = ? WHERE org_id = ? AND month = ? AND "
                   "requests_limit = ? AND mark = ?", (state, org_id, month, limit, top))
        auditlog.record(db, org_id, "skald", "billing.usage_alert", f"{top}%", detail)
    return {"mark": top, "used": used, "limit": limit, "month": month, "sent": sent,
            "failed": len(failed), "people": len(people)}


# ------------------------------------------------------------------- the runs

def billing_link(org_sites: list[str], urls: dict, config) -> str | None:
    """Settings > Billing & usage on the organisation's own dashboard: its first site (by name)
    with a dashboard.url, else the install's base address + /traffic/<site>/."""
    from ..accounts import links
    for site in sorted(org_sites):
        url = str(urls.get(site) or "").split("#", 1)[0]
        if url:
            return url + ("" if url.endswith("/") else "/") + "#settings/billing"
    root = links.base_url(config)
    if root and org_sites:
        return f"{root}/traffic/{sorted(org_sites)[0]}/#settings/billing"
    return None


def run(db, config, history_path, urls: dict | None = None, *, force=False,
        send=None) -> list[dict]:
    """check() every organisation with a plan; the alerts decided now."""
    if not on(config):
        return []
    out = []
    for (org_id,) in db.execute("SELECT id FROM orgs WHERE plan IS NOT NULL AND plan != '' "
                                "ORDER BY id").fetchall():
        sites = [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))]
        got = check(db, org_id, config, history_path, force=force, send=send,
                    link=billing_link(sites, urls or {}, config))
        if got:
            out.append(got)
    return out


def after_run(contexts: list, command: str = "live", send=None) -> list[dict]:
    """After every site of a live run or run-daily (summary_mail.after_run). Never raises."""
    if not contexts:
        return []
    first = contexts[0]
    try:
        if not on(first.config):
            return []
        from ..auth_api import open_db
        from .limits import history_path
        db = open_db(first.config, first.live_dir)
        if db is None:
            return []
        try:
            urls = {c.site: ((c.config or {}).get("dashboard") or {}).get("url")
                    for c in contexts}
            got = run(db, first.config, history_path(first.config, first.live_dir), urls,
                      force=command == "run-daily", send=send)
        finally:
            db.close()
        for a in got:
            first.out(f"usage alert: an organisation reached {a['mark']}% of its requests "
                      f"this month; mailed {a['sent']} of {a['people']} owners and admins")
        return got
    except Exception as why:                # noqa: BLE001 - never stops the run
        first.err(f"usage alerts: {type(why).__name__}: {why}")
        return []
