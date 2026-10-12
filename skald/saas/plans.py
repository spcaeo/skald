"""The plans in the config, and each organisation's plan and status.

    saas:
      default_plan: pro
      plans:
        pro: {sites: 5, requests_month: 1000000, retention_days_max: 400,
              members: 10, price_id: price_..., trial_days: 14, label: "Pro"}

or, for the small config parser (no PyYAML), a flow list with `name`:

      plans: [{name: pro, sites: 5, requests_month: 1000000, members: 10}]

A limit left out, empty, "null" or "unlimited" is no limit. `price_id` is
the Stripe Price a customer subscribes to (none: the plan cannot be bought
from the page). `trial_days` is the trial a new sign-up gets.

An organisation's plan lives on its row in accounts.sqlite (schema 3):
plan, plan_status (trialing, active, past_due, canceled, none),
trial_ends_at, stripe_customer, stripe_subscription, created_via and
past_due_since. An organisation with no plan (the install's own, made with
`skald accounts init` or `org create`) has no limits. Every change is
audited ("billing.plan").
"""
from __future__ import annotations

from . import STATUSES, section
from ..accounts import auditlog
from ..accounts import db as base

LIMITS = ("sites", "requests_month", "retention_days_max", "members")
NO_LIMIT = ("", "null", "none", "unlimited", "~")
KEEP = object()
COLUMNS = ("id, name, slug, created_at, plan, plan_status, trial_ends_at, stripe_customer, "
           "stripe_subscription, created_via, past_due_since")


def _limit(name: str, field: str, value) -> int | None:
    if value is None or (isinstance(value, str) and value.strip().lower() in NO_LIMIT):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        got = int(str(value).strip())
        if got < 0:
            raise ValueError
    except ValueError:
        raise ValueError(f"saas.plans {name}: {field} is a whole number, or left out for no "
                         f"limit (got {str(value)[:40]!r})") from None
    return got


def plans(config) -> dict[str, dict]:
    """{name: {name, sites, requests_month, retention_days_max, members,
    price_id, trial_days, label}}, in the config's order. ValueError for a
    limit that is not a number."""
    raw = section(config).get("plans") or {}
    if isinstance(raw, dict):
        items = [(k, v) for k, v in raw.items()]
    elif isinstance(raw, list):
        items = [(m.get("name"), m) for m in raw if isinstance(m, dict)]
    else:
        items = []
    out: dict[str, dict] = {}
    for name, entry in items:
        name = str(name or "").strip()
        if not name or not isinstance(entry, dict):
            continue
        plan = {"name": name}
        for field in LIMITS:
            plan[field] = _limit(name, field, entry.get(field))
        # Log lines an organisation may ship a day (ingest.py); not in LIMITS,
        # so /me and the billing page are unchanged.
        plan["ingest_daily_mb"] = _limit(name, "ingest_daily_mb", entry.get("ingest_daily_mb"))
        price = str(entry.get("price_id") or "").strip()
        plan["price_id"] = price or None
        plan["trial_days"] = _limit(name, "trial_days", entry.get("trial_days")) or 0
        plan["label"] = str(entry.get("label") or "").strip()[:80]
        out[name] = plan
    return out


def default_plan(config) -> str | None:
    """saas.default_plan when it is a plan, else the first plan, else None."""
    table = plans(config)
    named = str(section(config).get("default_plan") or "").strip()
    if named in table:
        return named
    return next(iter(table), None)


def plan_by_price(config, price_id) -> str | None:
    for name, plan in plans(config).items():
        if price_id and plan["price_id"] == price_id:
            return name
    return None


def org_state(db, org_id) -> dict | None:
    return base.one(db, f"SELECT {COLUMNS} FROM orgs WHERE id = ?", (org_id,))


def find_org(db, *, subscription=None, customer=None) -> dict | None:
    """The organisation of a Stripe subscription, else of a Stripe customer."""
    for column, value in (("stripe_subscription", subscription), ("stripe_customer", customer)):
        if isinstance(value, str) and value:
            got = base.one(db, f"SELECT {COLUMNS} FROM orgs WHERE {column} = ? "
                               "ORDER BY id LIMIT 1", (value,))
            if got is not None:
                return got
    return None


def set_plan(db, org_id, plan, status, actor, *, trial_ends_at=KEEP, customer=KEEP,
             subscription=KEEP, via=KEEP, detail: str = "") -> dict:
    """Set the plan (None: no plan) and status; the grace period starts when
    the status first becomes past_due and ends with any other status.
    ValueError for an unknown organisation or status."""
    if status not in STATUSES:
        raise ValueError(f"A plan status is one of: {', '.join(STATUSES)}.")
    plan = str(plan).strip() if plan else None
    with base.tx(db):
        old = org_state(db, org_id)
        if old is None:
            raise ValueError("There is no such organisation.")
        since = old["past_due_since"] if old["plan_status"] == "past_due" else None
        if status == "past_due" and since is None:
            since = base.now()
        if status != "past_due":
            since = None
        sets = {"plan": plan, "plan_status": status, "past_due_since": since}
        for column, value in (("trial_ends_at", trial_ends_at), ("stripe_customer", customer),
                              ("stripe_subscription", subscription), ("created_via", via)):
            if value is not KEEP:
                sets[column] = value
        db.execute(f"UPDATE orgs SET {', '.join(f'{k} = ?' for k in sets)} WHERE id = ?",
                   (*sets.values(), org_id))
        changed = (old["plan"], old["plan_status"]) != (plan, status)
        if changed or detail:
            auditlog.record(db, org_id, actor, "billing.plan", plan or "(none)",
                            f"{old['plan'] or '(none)'}/{old['plan_status']} -> "
                            f"{plan or '(none)'}/{status}" + (f"; {detail}" if detail else ""))
        return org_state(db, org_id)


def start_trial(db, org_id, config, actor, via: str = "signup") -> dict:
    """The default plan for a new organisation: trialing for its trial_days,
    else active when it has no price (a free plan), else status none."""
    name = default_plan(config)
    plan = plans(config).get(name) if name else None
    if plan is None:
        return set_plan(db, org_id, None, "none", actor, via=via)
    if plan["trial_days"]:
        return set_plan(db, org_id, name, "trialing", actor, via=via,
                        trial_ends_at=base.shift(plan["trial_days"] * 86400))
    return set_plan(db, org_id, name, "active" if not plan["price_id"] else "none", actor,
                    via=via, trial_ends_at=None)
