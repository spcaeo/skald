"""What an organisation's plan allows, what it uses, and what happens over it.

    limits_for(db, org_id, config)          the plan's limits and state, or None
    can_add_member(db, org_id, config)      (ok, why): team_api's invite
    can_add_site(db, org_id, config)        (ok, why): for whoever adds a site
    retention_cap(db, org_id, config)       the most days a retention setting may hold
    usage(history_path, sites, month)       the month's requests, from the history
    over_limit(db, org_id, config, ...)     which limits are passed (for ingest)
    read_only(db, org_id, config)           why changes are refused, or None
    summary(db, org_id, config, ...)        the `plan` block of /me

Every one gives "no limit" when saas is off (saas.enabled) or the
organisation has no plan. Being over a limit never loses data: /me says so
and the page shows a banner; refusing new data is the ingest's choice
(`over_limit`). An organisation whose payment failed more than
saas.grace_days ago (or whose trial ended that long ago, with billing on,
or whose subscription was cancelled) is read-only: the dashboard is still
readable, settings and the team cannot be changed. Nothing is deleted.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from . import billing_on, enabled, grace_days
from . import plans as plan_table
from ..accounts import db as base

READ_ONLY_PAST_DUE = ("The last payment failed more than {days} days ago, so this "
                      "organisation is read-only until it is paid. Nothing is deleted. "
                      "The owner can fix it in Settings > Billing.")
READ_ONLY_TRIAL = ("The trial ended more than {days} days ago, so this organisation is "
                   "read-only until a plan is chosen. Nothing is deleted. The owner can "
                   "choose one in Settings > Billing.")
READ_ONLY_CANCELED = ("The subscription was cancelled, so this organisation is read-only. "
                      "Nothing is deleted. The owner can choose a plan in Settings > Billing.")


def limits_for(db, org_id, config) -> dict | None:
    """{plan, known, status, sites, requests_month, retention_days_max,
    members, trial_ends_at, trial_days_left} (a limit None: no limit), or
    None when saas is off or the organisation has no plan. A plan name the
    config no longer lists takes the default plan's limits (known: False)."""
    if not enabled(config):
        return None
    state = plan_table.org_state(db, org_id)
    if state is None or not state["plan"]:
        return None
    table = plan_table.plans(config)
    plan = table.get(state["plan"]) or table.get(plan_table.default_plan(config) or "") or {}
    got = {"plan": state["plan"], "known": state["plan"] in table,
           "status": state["plan_status"], "trial_ends_at": state["trial_ends_at"],
           "trial_days_left": _days_left(state)}
    for field in plan_table.LIMITS:
        got[field] = plan.get(field)
    return got


def _days_left(state: dict) -> int | None:
    if state["plan_status"] != "trialing" or not state["trial_ends_at"]:
        return None
    seconds = (base.parse(state["trial_ends_at"]) - base.parse(base.now())).total_seconds()
    return max(0, math.ceil(seconds / 86400))


# ---------------------------------------------------------------- members, sites

def members_used(db, org_id, email: str | None = None) -> int:
    """Members plus open invites (not used, not expired), less `email`'s invite."""
    members = db.execute("SELECT COUNT(*) FROM members WHERE org_id = ?",
                         (org_id,)).fetchone()[0]
    invites = db.execute("SELECT COUNT(*) FROM invites WHERE org_id = ? AND used_at IS NULL "
                         "AND expires_at > ? AND email != ?",
                         (org_id, base.now(), str(email or "").strip().lower())).fetchone()[0]
    return members + invites


def sites_used(db, org_id) -> int:
    return db.execute("SELECT COUNT(*) FROM sites WHERE org_id = ?", (org_id,)).fetchone()[0]


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def can_add_member(db, org_id, config, email: str | None = None) -> tuple[bool, str]:
    """(True, "") or (False, why). Open invites count; resending `email`'s does not."""
    got = limits_for(db, org_id, config)
    if got is None or got["members"] is None:
        return True, ""
    if members_used(db, org_id, email) < got["members"]:
        return True, ""
    return False, (f"The {got['plan']} plan allows {_plural(got['members'], 'member')}, "
                   "open invites included. Cancel an invite, remove a member, or choose a "
                   "bigger plan in Settings > Billing.")


def can_add_site(db, org_id, config) -> tuple[bool, str]:
    """(True, "") or (False, why): for the code that adds a site to an organisation."""
    got = limits_for(db, org_id, config)
    if got is None or got["sites"] is None:
        return True, ""
    if sites_used(db, org_id) < got["sites"]:
        return True, ""
    return False, (f"The {got['plan']} plan allows {_plural(got['sites'], 'site')}. Choose a "
                   "bigger plan in Settings > Billing to add another.")


def retention_cap(db, org_id, config) -> int | None:
    """The most days a retention setting may be set to, or None (no cap)."""
    got = limits_for(db, org_id, config)
    return None if got is None else got["retention_days_max"]


# ------------------------------------------------------------------- usage

def month_now() -> str:
    """This month, "YYYY-MM", by the accounts clock (UTC)."""
    return base.now()[:7]


def history_path(config, live_dir=None) -> Path | None:
    """The history file the helper reads: the one Context or the helper
    resolved, else history.sqlite in `live_dir`."""
    made = ((config or {}).get("_resolved") or {}).get("history_db")
    if made:
        return Path(str(made))
    return Path(live_dir) / "history.sqlite" if live_dir is not None else None


def usage(history_path, sites, month: str) -> dict:
    """{"month", "requests", "days", "withheld"}: the requests of `sites` in
    `month` ("YYYY-MM", the sites' own calendar days), from the history's
    daily totals, read-only. requests is None when no day of the month is
    recorded, and withheld (with the reason) when the second count
    (audit_usage.py) does not agree."""
    from .. import audit_usage
    out = {"month": month, "requests": None, "days": 0, "withheld": None}
    names = [str(s) for s in sites or ()]
    if not names or history_path is None or not Path(history_path).is_file():
        return out
    marks = ",".join("?" * len(names))
    try:
        conn = sqlite3.connect(f"file:{Path(history_path).resolve()}?mode=ro", uri=True)
        try:
            days, total = conn.execute(
                f"SELECT COUNT(DISTINCT day), SUM(hits) FROM days WHERE site IN ({marks}) "
                "AND day >= ? AND day < ?", (*names, f"{month}-01", f"{month}-32")).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as why:
        out["withheld"] = f"the history could not be read ({type(why).__name__})"
        return out
    out["days"] = int(days or 0)
    if not days:
        return out
    again, _ = audit_usage.recount(history_path, names, month)
    if again != int(total or 0):
        out["withheld"] = (f"the daily totals and their groups do not add up for {month} "
                           f"({int(total or 0):,} against {again if again is not None else '?'}"
                           "); run skald audit")
        return out
    out["requests"] = int(total or 0)
    return out


# ----------------------------------------------------------- over, read-only

def over_limit(db, org_id, config, history_path=None, month: str | None = None) -> list[str]:
    """The limits the organisation is past, from: "sites", "members",
    "requests_month" (this month's usage, when it is known). [] when saas is
    off, there is no plan, or nothing is over. For the ingest: refusing new
    data over "requests_month" is its choice; nothing here deletes any."""
    got = limits_for(db, org_id, config)
    if got is None:
        return []
    over = []
    if got["sites"] is not None and sites_used(db, org_id) > got["sites"]:
        over.append("sites")
    if got["members"] is not None and members_used(db, org_id) > got["members"]:
        over.append("members")
    if got["requests_month"] is not None:
        sites = [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))]
        used = usage(history_path, sites, month or month_now())["requests"]
        if used is not None and used > got["requests_month"]:
            over.append("requests_month")
    return over


def read_only(db, org_id, config) -> str | None:
    """Why this organisation cannot change settings or its team now, or None."""
    if not enabled(config) or org_id is None:
        return None
    state = plan_table.org_state(db, org_id)
    if state is None or not state["plan"]:
        return None
    days = grace_days(config)
    limit = base.shift(-days * 86400)
    status = state["plan_status"]
    if status == "canceled":
        return READ_ONLY_CANCELED
    if status == "past_due" and state["past_due_since"] and state["past_due_since"] < limit:
        return READ_ONLY_PAST_DUE.format(days=days)
    if (status == "trialing" and billing_on(config) and state["trial_ends_at"]
            and state["trial_ends_at"] < limit):
        return READ_ONLY_TRIAL.format(days=days)
    return None


def summary(db, org_id, config, history_path=None) -> dict | None:
    """The `plan` block of /me: {name, status, usage, limits, used, over,
    read_only, read_only_why, trial_days_left, trial_ends_at}; None when saas
    is off or the organisation has no plan. usage adds `percent` (of
    requests_month, rounded down), `resets_on` and `mark` (80, 90, 100: the
    usage alerts' highest mark reached; None when they are switched off)."""
    got = limits_for(db, org_id, config)
    if got is None:
        return None
    from . import usage_alerts
    sites = [r[0] for r in db.execute("SELECT name FROM sites WHERE org_id = ?", (org_id,))]
    why = read_only(db, org_id, config)
    month = month_now()
    used = usage(history_path, sites, month)
    share = usage_alerts.percent(used["requests"], got["requests_month"])
    return {"name": got["plan"], "known": got["known"], "status": got["status"],
            "usage": {**used, "percent": share, "resets_on": usage_alerts.resets_on(month),
                      "mark": usage_alerts.mark(used["requests"], got["requests_month"])
                      if usage_alerts.on(config) else None},
            "limits": {f: got[f] for f in plan_table.LIMITS},
            "used": {"sites": len(sites), "members": members_used(db, org_id)},
            "over": over_limit(db, org_id, config, history_path),
            "read_only": why is not None, "read_only_why": why,
            "trial_days_left": got["trial_days_left"], "trial_ends_at": got["trial_ends_at"]}
