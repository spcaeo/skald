"""`stripe`: Stripe webhooks.

Signature: `Stripe-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "<t>.<raw
body>">` (several v1 may be sent while a secret is rolled), with the
endpoint's signing secret (whsec_...); refused more than 5 minutes off.

Events (subscribe the endpoint to these; conversions.EVENTS["stripe"]):

    checkout.session.completed        -> paid (started while its payment_status
                                         is "unpaid", a delayed payment method)
    checkout.session.async_payment_succeeded -> paid
    invoice.paid                      -> paid, only with billing_reason
                                         "subscription_cycle" (a renewal; the
                                         first invoice is the checkout's sale)
    charge.refunded                   -> refunded, on the sale's row
    invoice_payment.paid              -> no row: which payment intent paid
                                         which invoice (links)

A checkout's external ref is the Checkout Session id; a renewal's, the
invoice id. Since 2.32 each keeps its money: value = amount_total (a session)
or amount_paid (an invoice), in Stripe's smallest unit (conversions/money.py
stripe_minor: ISK and UGX are sent as hundredths), the currency, customer_ref =
the `customer` id (cus_...) when it is a string, and pay_ref = the payment
intent (else the invoice), so a refund finds its sale. charge.refunded carries
the total refunded so far (amount_refunded): the store keeps one refunded row
per sale and raises its amount (store.record_conversion).

Stripe's API 2025-03-31 ("basil") took `payment_intent` off the Invoice and
`invoice` off the Charge (docs.stripe.com/changelog/basil/2025-03-31/add-
support-for-multiple-partial-payments-on-invoices). Its InvoicePayment object
(`invoice`, `payment.payment_intent`; docs.stripe.com/api/invoice-payment/
object), sent as invoice_payment.paid, joins them: `links` reads it and the
store keeps it (pay_links), so a renewal's refund (a charge with only its
payment intent) still finds the invoice it paid. Older payloads carry both
fields and need no link. The visitor ID:
client_reference_id, or metadata.skv (a renewal: the subscription's
metadata.skv), when it looks like a Skald ID; a renewal without one is joined
to its first sale by customer_ref when lifetime value is counted. Customer
details (name, email, address) are never read.
"""
from __future__ import annotations

from .. import EVENTS, money
from . import Invalid, dig, sign_timed, skald_vid, text, utm_touch, verify_timed, when

HEADER = "stripe-signature"
SIGNED = (HEADER,)          # no signature header at all: "unsigned"


def verify(headers: dict, body: bytes, secret: str, now: float) -> bool:
    return verify_timed(headers.get(HEADER, ""), body, secret, now)


def sign(body: bytes, secret: str, now: float, method: str = "POST", uri: str = "") -> dict:
    return {"Stripe-Signature": sign_timed(body, secret, now)}


def _id(value) -> str | None:
    """An object's id: Stripe sends an id, or the object when expanded."""
    if isinstance(value, dict):
        value = value.get("id")
    return text(value, 120) if isinstance(value, str) else None


def _money(obj: dict, amount_key: str) -> dict:
    currency = money.currency_of(obj.get("currency"))
    value = money.stripe_minor(obj.get(amount_key), currency)
    customer = obj.get("customer")
    customer_ref, _ = money.customer_of(customer if isinstance(customer, str) else None)
    return {"value_minor": value, "currency": currency if value is not None else None,
            "customer_ref": customer_ref}


def to_records(payload, site_config: dict | None = None) -> list[dict]:
    if not isinstance(payload, dict) or payload.get("object") != "event":
        raise Invalid("not a Stripe event")
    kind = str(payload.get("type") or "")
    obj = dig(payload, "data", "object")
    if not isinstance(obj, dict):
        raise Invalid("no data.object")
    if kind == "checkout.session.completed" and obj.get("payment_status") == "unpaid":
        kind += "+unpaid"
    if kind == "invoice.paid":
        kind += "+" + str(obj.get("billing_reason") or "")
    mapped = EVENTS["stripe"].get(kind)
    if mapped is None:
        return []
    ref = text(obj.get("id"), 120)
    if not ref:
        raise Invalid("no object id")
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    out = {"action": mapped[0], "stage": mapped[1], "external_ref": ref,
           "at": when(payload.get("created")), "last_touch": utm_touch(meta)}
    if kind.startswith("invoice.paid"):
        sub = dig(obj, "subscription_details", "metadata") or \
            dig(obj, "parent", "subscription_details", "metadata")
        sub = sub if isinstance(sub, dict) else {}
        out.update(_money(obj, "amount_paid"), vid=skald_vid(sub.get("skv")),
                   last_touch=utm_touch(sub),
                   pay_ref=_id(obj.get("payment_intent")) or ref)
    elif kind == "charge.refunded":
        pay = _id(obj.get("payment_intent"))
        invoice = _id(obj.get("invoice"))
        out.update(_money(obj, "amount_refunded"), vid=None, customer_ref=None,
                   external_ref=pay or ref, pay_ref=pay,
                   refund_of=[k for k in (pay, invoice) if k])
    else:
        out.update(_money(obj, "amount_total"),
                   vid=skald_vid(obj.get("client_reference_id")) or skald_vid(meta.get("skv")),
                   pay_ref=_id(obj.get("payment_intent")) or _id(obj.get("invoice")))
    return [out]


def links(payload) -> list[tuple[str, str]]:
    """[(invoice id, payment intent id)] of an invoice_payment.paid event; []."""
    if not isinstance(payload, dict) or payload.get("type") != "invoice_payment.paid":
        return []
    obj = dig(payload, "data", "object")
    if not isinstance(obj, dict):
        return []
    invoice, pay = _id(obj.get("invoice")), _id(dig(obj, "payment", "payment_intent"))
    return [(invoice, pay)] if invoice and pay else []


def sample(site: str, now: float) -> dict:
    return {"id": f"evt_skaldtest{int(now)}", "object": "event", "created": int(now),
            "type": "checkout.session.completed",
            "data": {"object": {"id": f"cs_test_skald{int(now)}", "object": "checkout.session",
                                "payment_status": "paid", "amount_total": 4900,
                                "currency": "usd", "customer": "cus_skaldtest",
                                "payment_intent": f"pi_skaldtest{int(now)}",
                                "client_reference_id": "skv_" + "A" * 22,
                                "metadata": {"utm_source": "google", "utm_medium": "cpc"}}}}
