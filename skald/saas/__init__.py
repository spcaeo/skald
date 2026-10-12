"""Skald as a service: sign-up, plans and limits, Stripe billing (docs/SAAS.md).

Off by default. With `saas.enabled` false (or missing), or without
`access.mode: sessions`, every route here answers 404, no limit applies and
nothing in the accounts file changes: a self-hosted install is as before.

    saas:
      enabled: true
      signup: true                 # /traffic-auth/signup
      allowed_domains: [example.com]
      billing: stripe              # Settings > Billing and the Stripe webhook
      grace_days: 7
      default_plan: pro
      plans: [{name: pro, sites: 5, requests_month: 1000000, ...}]

    signups.py      sign-up links (24 h, used once, rate-limited)
    signup_api.py   /traffic-auth/signup, signup-finish (the helper)
    plans.py        the plans in the config; an organisation's plan and status
    limits.py       limits_for, can_add_site/member, retention_cap, usage, over_limit
    stripe_client.py, stripe_events.py, billing_api.py   Stripe, by plain HTTPS
    cli.py          bin/skald plan, usage, billing
"""
from __future__ import annotations

STATUSES = ("trialing", "active", "past_due", "canceled", "none")
GRACE_DAYS = 7


def section(config) -> dict:
    got = (config or {}).get("saas")
    return got if isinstance(got, dict) else {}


def flag(value) -> bool:
    """True for YAML's true and the small parser's "true"; nothing else."""
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def enabled(config) -> bool:
    """saas.enabled, and the install runs with accounts (access.mode: sessions)."""
    from .. import access
    return flag(section(config).get("enabled")) and access.mode(config) == "sessions"


def signup_on(config) -> bool:
    return enabled(config) and flag(section(config).get("signup"))


def billing_on(config) -> bool:
    return enabled(config) and str(section(config).get("billing") or "").lower() == "stripe"


def grace_days(config) -> int:
    try:
        return max(0, int(str(section(config).get("grace_days", GRACE_DAYS)).strip()))
    except ValueError:
        return GRACE_DAYS


def allowed_domains(config) -> list[str]:
    raw = section(config).get("allowed_domains") or []
    if isinstance(raw, str):
        raw = raw.replace(",", " ").split()
    return [str(d).strip().lower().lstrip("@") for d in raw if str(d).strip()]
