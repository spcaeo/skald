"""Stripe's billing events -> an organisation's plan and status.

    checkout.session.completed      plan (from its metadata), customer and
                                    subscription saved; status active
    customer.subscription.updated   status from Stripe's (below); plan from
                                    the price, when the config names it
    customer.subscription.deleted   canceled (read-only; nothing deleted)
    invoice.payment_failed          past_due (the grace period starts)

Stripe's subscription statuses: trialing and active as they are; past_due,
unpaid, incomplete and paused are past_due; canceled and
incomplete_expired are canceled.

Each event is applied once: its id goes into billing_events in the same
transaction as the change, so a retried delivery is answered "duplicate".
An event older than one already applied to the same organisation is kept
but not applied (Stripe does not promise the order). Every change is
audited with the actor "stripe". Other event types are noted and ignored.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import plans
from ..accounts import db as base

HANDLED = ("checkout.session.completed", "customer.subscription.updated",
           "customer.subscription.deleted", "invoice.payment_failed")
STATUS = {"trialing": "trialing", "active": "active", "past_due": "past_due",
          "unpaid": "past_due", "incomplete": "past_due", "paused": "past_due",
          "canceled": "canceled", "incomplete_expired": "canceled"}
ACTOR = "stripe"


class Invalid(ValueError):
    """A verified body that is not a Stripe event."""


def _text(value, limit: int = 255) -> str | None:
    return value[:limit] if isinstance(value, str) and value else None


def _dig(obj, *keys):
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list) and isinstance(key, int) and len(obj) > key:
            obj = obj[key]
        else:
            return None
    return obj


def _org_by_id(db, raw) -> dict | None:
    raw = str(raw or "").strip()
    return plans.org_state(db, int(raw)) if raw.isdigit() else None


def _org_for(db, kind: str, obj: dict) -> dict | None:
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    if kind == "checkout.session.completed":
        return _org_by_id(db, obj.get("client_reference_id")) or _org_by_id(db, meta.get("org_id"))
    if kind.startswith("customer.subscription."):
        return (_org_by_id(db, meta.get("org_id"))
                or plans.find_org(db, subscription=_text(obj.get("id")),
                                  customer=_text(obj.get("customer"))))
    subscription = (_text(obj.get("subscription"))
                    or _text(_dig(obj, "parent", "subscription_details", "subscription")))
    return plans.find_org(db, subscription=subscription, customer=_text(obj.get("customer")))


def apply(db, event, config) -> str:
    """Apply one verified event; the outcome in words ("applied ...",
    "duplicate", "ignored ..."). Invalid for a body that is not an event."""
    if not isinstance(event, dict) or event.get("object") != "event":
        raise Invalid("not a Stripe event")
    event_id, kind = _text(event.get("id")), _text(event.get("type"), 100)
    obj = _dig(event, "data", "object")
    if not event_id or not kind or not isinstance(obj, dict):
        raise Invalid("not a Stripe event")
    created = event.get("created") if isinstance(event.get("created"), int) else None
    with base.tx(db):
        if db.execute("SELECT 1 FROM billing_events WHERE event_id = ?",
                      (event_id,)).fetchone():
            return "duplicate"
        org, outcome = None, f"ignored: {kind} is not a billing event Skald uses"
        if kind in HANDLED:
            org = _org_for(db, kind, obj)
            if org is None:
                outcome = "ignored: no organisation here matches it"
            elif created is not None and _newer_applied(db, org["id"], created):
                outcome = "ignored: a newer event was applied already"
            else:
                outcome = _change(db, kind, obj, org, config, event_id)
        db.execute("INSERT INTO billing_events (event_id, type, org_id, created, received_at, "
                   "outcome) VALUES (?, ?, ?, ?, ?, ?)",
                   (event_id, kind, org["id"] if org else None, created, base.now(),
                    outcome[:200]))
    return outcome


def _newer_applied(db, org_id, created: int) -> bool:
    row = db.execute("SELECT MAX(created) FROM billing_events WHERE org_id = ? "
                     "AND outcome LIKE 'applied%'", (org_id,)).fetchone()
    return row[0] is not None and row[0] > created


def _change(db, kind: str, obj: dict, org: dict, config, event_id: str) -> str:
    detail = f"{kind} {event_id}"
    known = plans.plans(config)
    if kind == "checkout.session.completed":
        meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        plan = meta.get("plan") if meta.get("plan") in known else org["plan"]
        plans.set_plan(db, org["id"], plan, "active", ACTOR, trial_ends_at=None,
                       customer=_text(obj.get("customer")) or org["stripe_customer"],
                       subscription=_text(obj.get("subscription")) or org["stripe_subscription"],
                       detail=detail)
        return f"applied: {plan or '(no plan)'} active"
    if kind.startswith("customer.subscription."):
        status = "canceled" if kind.endswith(".deleted") else STATUS.get(
            str(obj.get("status") or ""), org["plan_status"])
        price = _dig(obj, "items", "data", 0, "price", "id")
        plan = plans.plan_by_price(config, price) or org["plan"]
        ends = obj.get("trial_end")
        trial = (datetime.fromtimestamp(ends, timezone.utc).strftime(base.STAMP)
                 if status == "trialing" and isinstance(ends, int) else None)
        plans.set_plan(db, org["id"], plan, status, ACTOR, trial_ends_at=trial,
                       customer=_text(obj.get("customer")) or org["stripe_customer"],
                       subscription=_text(obj.get("id")) or org["stripe_subscription"],
                       detail=detail)
        return f"applied: {plan or '(no plan)'} {status}"
    plans.set_plan(db, org["id"], org["plan"], "past_due", ACTOR, detail=detail)
    return f"applied: {org['plan'] or '(no plan)'} past_due"
