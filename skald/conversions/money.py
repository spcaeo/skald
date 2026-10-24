"""Money on a lead (2.32): the lead hook's `value`, `currency`, `customer_ref`
and `tags` read into what the store keeps, and Stripe's amounts.

    value         the amount in the currency's major units: a JSON number or a
                  numeric string ("49.99"), >= 0, with at most the currency's
                  decimals (conversions.DECIMALS). Kept as whole minor units,
                  `value_minor` (4999), at most conversions.MAX_MINOR
    currency      ISO 4217, three letters (upper-cased first); required with
                  value
    customer_ref  the customer's own opaque id in the site, 1-128 of
                  A-Z a-z 0-9 _ . : - (never an email, a phone number - digits
                  only, 7 or more - or an IPv4 address: conversions.customer)
    tags          {key: value}, at most MAX_TAGS, both short lowercase tokens,
                  never 7 digits in all, an IPv4 address or a personal key
                  (conversions.tag: no phone numbers, addresses or emails)

A field that is not one is dropped and the delivery log says so: a lead is
never refused for it (like a bad `label`). A value without a currency, or a
currency Skald does not know, drops both. Currencies are never converted:
every sum is per currency. Shares nothing with the second count but the name
lists in conversions/__init__.py.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from . import (CURRENCIES, DECIMALS, MAX_AMOUNT_TEXT, MAX_MINOR, MAX_TAGS, STRIPE_HUNDREDS,
               customer, tag)

VALUE_NOTE = ("value or currency was not an amount Skald can keep (a number >= 0 with at "
              "most the currency's decimals, and an ISO 4217 currency): kept without a value")
CUSTOMER_NOTE = ("customer_ref was not an opaque id (1-128 letters, digits, _ . : -, never an "
                 "email, a phone number or an address): kept without it")
TAGS_NOTE = ("a tag was not kept (at most 5, keys and values short lowercase tokens, no "
             "phone numbers, addresses or personal keys)")
# A refund checked against its sale (store.record_conversion).
REFUND_OVER_NOTE = ("the refund was more than its sale: kept as the sale's whole value")
REFUND_CURRENCY_NOTE = ("the refund's currency is not its sale's: kept without a value")
NOTES = (VALUE_NOTE, CUSTOMER_NOTE, TAGS_NOTE, REFUND_OVER_NOTE, REFUND_CURRENCY_NOTE)


def decimals(currency: str) -> int:
    return DECIMALS.get(currency, 2)


def currency_of(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    got = raw.strip().upper()
    return got if got in CURRENCIES else None


def minor(raw, currency: str | None) -> int | None:
    """The amount `raw` (major units) in whole minor units of `currency`;
    None when it is not one."""
    if currency is None or isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    if isinstance(raw, int) and raw.bit_length() > 128:
        return None                                 # far past MAX_MINOR; repr would fail
    text = raw.strip() if isinstance(raw, str) else repr(raw)
    if len(text) > MAX_AMOUNT_TEXT:
        return None                                 # before parsing: "1" * 4400
    if isinstance(raw, str) and not (text.isascii() and text.replace(".", "", 1).isdigit()):
        return None                                 # "1e3", "-1", " ", "1,000"
    try:
        got = Decimal(text)                         # exact: no context rounding here
    except InvalidOperation:
        return None
    if not got.is_finite() or got.is_signed():
        return None                                 # NaN, Infinity, -0.0
    # Exact integer arithmetic from the digits: Decimal's scaleb would round to
    # 28 digits ("49.99000...001" kept as 4999).
    _, digits, exp = got.as_tuple()
    n = int("".join(map(str, digits)))
    while exp < 0 and n % 10 == 0:
        n, exp = n // 10, exp + 1                   # 49.990 is 49.99
    places = decimals(currency)
    if -exp > places:
        return None                                 # more decimals than the currency has
    if exp + places > 13:
        return None                                 # far past MAX_MINOR
    out = n * 10 ** (exp + places)
    return out if out <= MAX_MINOR else None


def shown(value_minor, currency) -> str | None:
    """Minor units as the major-unit amount, exact: 4999 USD -> "49.99"."""
    if value_minor is None or not currency:
        return None
    places = decimals(currency)
    got = Decimal(int(value_minor)).scaleb(-places)
    return f"{got:.{places}f}"


def stripe_minor(amount, currency: str | None) -> int | None:
    """A Stripe amount (its smallest unit) in Skald's minor units."""
    if currency is None or isinstance(amount, bool) or not isinstance(amount, int) \
            or amount < 0:
        return None
    if currency in STRIPE_HUNDREDS:
        if amount % 100:
            return None
        amount //= 100
    return amount if amount <= MAX_MINOR else None


def customer_of(raw) -> tuple[str | None, bool]:
    """(the customer_ref or None, True when one was sent but is not one)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None, False
    got = customer(raw)
    return (got, False) if got is not None else (None, True)


def tags_of(raw) -> tuple[str | None, bool]:
    """(the tags as canonical JSON, sorted keys, or None when none; True when
    any tag sent was dropped). Keys and values are lower-cased; past MAX_TAGS
    good ones (in key order) the rest are dropped."""
    if raw is None or raw == [] or raw == {}:
        return None, False
    if not isinstance(raw, dict):
        return None, True
    kept: dict = {}
    dropped = False
    for key in sorted(raw, key=str):
        got = tag(key, raw[key])
        if got is None or got[0] in kept or len(kept) >= MAX_TAGS:
            dropped = True
            continue
        kept[got[0]] = got[1]
    return (json.dumps(kept, sort_keys=True, separators=(",", ":")) if kept else None), dropped


def read(item: dict) -> dict:
    """The money fields of one lead object: value_minor, currency,
    customer_ref, tags (canonical JSON), the *_dropped flags for the notes,
    and value_sent (False: no value at all, which on a `refunded` row means
    the whole sale)."""
    raw_value, raw_currency = item.get("value"), item.get("currency")
    sent = raw_value not in (None, "")
    currency = currency_of(raw_currency) if sent else None
    value = minor(raw_value, currency) if sent else None
    customer, customer_dropped = customer_of(item.get("customer_ref"))
    tags, tags_dropped = tags_of(item.get("tags"))
    return {"value_minor": value, "currency": currency if value is not None else None,
            "value_sent": sent, "value_dropped": sent and value is None,
            "customer_ref": customer, "customer_dropped": customer_dropped,
            "tags": tags, "tags_dropped": tags_dropped}
