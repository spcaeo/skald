"""Stripe by plain HTTPS (urllib): a Checkout Session and a customer portal
session. Form-encoded POSTs to https://api.stripe.com with the secret key
as a Bearer token. The key is never logged and never in an error.

The opener is injectable (`opener=`, or the module's OPENER for the
helper): the tests never touch the network.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import urlencode

API = "https://api.stripe.com"
TIMEOUT = 20
OPENER = None              # None: urllib.request.urlopen


class StripeError(RuntimeError):
    """Stripe refused, or could not be reached; the words are safe to show."""


def flatten(fields, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: {"a": {"b": 1}, "l": [{"x": 2}]} ->
    [("a[b]", "1"), ("l[0][x]", "2")]. None is left out."""
    out: list[tuple[str, str]] = []
    items = fields.items() if isinstance(fields, dict) else enumerate(fields)
    for key, value in items:
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            out.extend(flatten(value, name))
        elif isinstance(value, bool):
            out.append((name, "true" if value else "false"))
        else:
            out.append((name, str(value)))
    return out


def call(secret_key: str, path: str, fields: dict, opener=None) -> dict:
    """POST `fields` to API + `path`; the parsed answer, or StripeError."""
    if not secret_key:
        raise StripeError("The Stripe secret key is not set.")
    req = urllib.request.Request(
        API + path, data=urlencode(flatten(fields)).encode(), method="POST",
        headers={"Authorization": f"Bearer {secret_key}",
                 "Content-Type": "application/x-www-form-urlencoded"})
    opener = opener or OPENER or urllib.request.urlopen
    try:
        with opener(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as err:
        try:
            said = json.loads(err.read() or b"{}").get("error", {}).get("message")
        except (ValueError, AttributeError, OSError):
            said = None
        raise StripeError(f"Stripe refused it ({err.code})" +
                          (f": {str(said)[:200]}" if said else ".")) from None
    except (urllib.error.URLError, OSError, ValueError):
        raise StripeError("Stripe could not be reached. Try again in a minute.") from None
    try:
        got = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise StripeError("Stripe's answer could not be read.") from None
    if not isinstance(got, dict):
        raise StripeError("Stripe's answer could not be read.")
    return got


def checkout_session(secret_key: str, *, org_id: int, plan: str, price_id: str,
                     email: str | None, customer: str | None, success_url: str,
                     cancel_url: str, opener=None) -> dict:
    """A subscription Checkout Session for one organisation. The org id rides
    as client_reference_id and in the metadata of the session and of the
    subscription, so every later event finds the organisation."""
    fields = {"mode": "subscription",
              "line_items": [{"price": price_id, "quantity": 1}],
              "client_reference_id": str(org_id),
              "success_url": success_url, "cancel_url": cancel_url,
              "metadata": {"org_id": str(org_id), "plan": plan},
              "subscription_data": {"metadata": {"org_id": str(org_id), "plan": plan}}}
    if customer:
        fields["customer"] = customer
    elif email:
        fields["customer_email"] = email
    return call(secret_key, "/v1/checkout/sessions", fields, opener)


def portal_session(secret_key: str, *, customer: str, return_url: str, opener=None) -> dict:
    return call(secret_key, "/v1/billing_portal/sessions",
                {"customer": customer, "return_url": return_url}, opener)
