"""Revenue on leads (2.32): conversions.json's per-day `revenue` and the file's
`ltv`, from the money the hooks keep (conversions/money.py; Stripe's
amounts). DATA-CONTRACT.md and docs/DATA-CONTRACT-CONVERSIONS.md.

A sale is a finished row (completed or paid) that carries a value and a
currency, counted once per (tool, external ref): its `paid` row when that
carries a value, else its `completed` one (store.sale_of). This is NOT
store.repeat_finishes' rule for leads: a `paid` sent after a `completed` for
the same sign-up is one lead (the completed row, the lead's first finish) but
the paid row is the one sale - the money came then. A finished row without a
value, or with a currency Skald does not know, is no sale; it stays a lead.

A refund is a `refunded` row with a value (store.record_conversion keeps one
per sale, its amount the total refunded so far, never more than the sale), and
it counts only when its sale counts, in the sale's currency. Every other
refund row kept is never subtracted and is listed in `refunds_without_sale`:
its sale is not kept (Stripe sends charge.refunded for every charge of the
account, Skald's or not), is a test or was taken away, or the refund has no
value (one that could not be read, or one sent in another currency than its
sale's, which the store keeps without its value). Each part of a refund (its
first amount, then each larger total's difference: store.refund_parts) counts
on the day it arrived, as one refund, under its sale's attribution, never on
the sale's day; a part of 0 is no refund.

Revenue is recorded from `since` (first_day): the local day of the site's
first counted row with a value. A day before it is not recorded (no
`revenue` at all, never {}: a site that sent sales without amounts before
2.32 did not sell nothing).

Attribution (source, first source, campaign, landing, country, device,
label) is the (tool, ref)'s first finished row, by `at`, then the stage's
name, then id - where the visitor came from, the lead; else the row itself.
Tags are the sale row's (a refund: its sale's, else its own). The tool is the
row's.

A customer is a customer_ref within one currency; a sale without one is its
own customer. Of a customer's sales (every row kept, any day; by `at`, then
id) the first is a new customer, every later one a renewal.

Currencies are never converted: every figure is per currency. Test rows
(test <> 0) never count; removed rows are gone from the table. Unknown is
"Unknown", a sale without a label "(no label)" (conversions.NO_LABEL).

Counted here in Python from plain SELECTs. audit_revenue.py counts every
figure again by SQL GROUP BY and the raw sums from the hook spool; a day it
disagrees with is withheld, the `ltv` block too.
"""
from __future__ import annotations

import json
from datetime import date

from .conversions import FINISHED, NO_LABEL, REFUNDED, UNKNOWN

# conversions.json's `revenue.by` names -> the conversions column.
DIMS = (("source", "source_type"), ("first_source", "first_source"),
        ("campaign", "campaign"), ("landing", "landing"), ("country", "country"),
        ("device", "device"), ("tool", "tool"), ("label", "label"))
_COLS = ("id, tool, external_ref, action, stage, at, source_type, first_source, campaign, "
         "landing, country, device, label, value_minor, currency, customer_ref, tags")


def _name(dim: str, value) -> str:
    if value is None or value == "":
        return NO_LABEL if dim == "label" else UNKNOWN
    return str(value)


def _local_day(at: str, tz) -> str:
    from .conversions.store import parse
    return parse(at).astimezone(tz).date().isoformat()


class Book:
    """Every counted money row of one site, with each sale's and refund's
    attribution, tags and customer worked out."""

    def __init__(self, db, site: str) -> None:
        rows = [dict(r) for r in db.execute(
            f"SELECT {_COLS} FROM conversions WHERE site = ? AND test = 0 ORDER BY at, id",
            (site,))]
        first: dict = {}
        priced: dict = {}
        for r in rows:
            key = (r["tool"], r["external_ref"])
            if r["stage"] in FINISHED:
                mine = (r["at"], r["stage"], r["id"])
                if key not in first or mine < first[key][0]:
                    first[key] = (mine, r)
                if r["value_minor"] is not None and r["currency"]:
                    priced.setdefault(key, {})[r["stage"]] = r
        self.sales = []
        for key, by_stage in priced.items():
            self.sales.append(by_stage.get("paid") or by_stage["completed"])
        self.sales.sort(key=lambda r: (r["at"], r["id"]))
        self.sale_at = {(r["tool"], r["external_ref"]): r for r in self.sales}
        refunded = [r for r in rows if r["stage"] == REFUNDED]
        self.refunds = [r for r in refunded if r["value_minor"] is not None and r["currency"]
                        and (self.sale_of(r) or {}).get("currency") == r["currency"]]
        counted = {r["id"] for r in self.refunds}
        self.orphans = [r for r in refunded if r["id"] not in counted]
        # Each counted refund's parts: [(at, value)], by when they arrived.
        mine = {r["id"]: r for r in self.refunds}
        self.parts = []
        for rid, at, value in db.execute(
                "SELECT p.conversion_id, p.at, p.value_minor FROM refund_parts p JOIN conversions "
                "c ON c.id = p.conversion_id WHERE c.site = ? AND c.test = 0 AND p.value_minor > 0 "
                "ORDER BY p.at, p.id", (site,)):
            if rid in mine:
                self.parts.append((mine[rid], at, int(value)))
        self.first = {k: v[1] for k, v in first.items()}
        # A customer's sales in one currency, in order: the first is new.
        self.renewal: dict = {}
        seen: set = set()
        for r in self.sales:
            who = self.customer(r)
            self.renewal[r["id"]] = who in seen
            seen.add(who)

    def customer(self, sale: dict) -> tuple:
        if sale["customer_ref"]:
            return ("customer", sale["customer_ref"], sale["currency"])
        return ("sale", sale["tool"], sale["external_ref"], sale["currency"])

    def attribution(self, row: dict) -> dict:
        return self.first.get((row["tool"], row["external_ref"])) or row

    def sale_of(self, refund: dict) -> dict | None:
        return self.sale_at.get((refund["tool"], refund["external_ref"]))

    def tags(self, row: dict) -> dict:
        if row["stage"] == REFUNDED:
            row = self.sale_of(row) or row
        try:
            got = json.loads(row["tags"]) if row["tags"] else {}
        except ValueError:
            return {}
        return got if isinstance(got, dict) else {}


def has_money(db, site: str) -> bool:
    """True when the site has any counted row with a value."""
    return db.execute("SELECT 1 FROM conversions WHERE site = ? AND test = 0 AND value_minor "
                      "IS NOT NULL AND currency IS NOT NULL LIMIT 1", (site,)).fetchone() \
        is not None


def _cur(day: dict, currency: str) -> dict:
    return day.setdefault(currency, {
        "gross_minor": 0, "refunded_minor": 0, "net_minor": 0, "sales": 0, "refunds": 0,
        "new_customers": 0, "renewals": 0,
        "by": {**{name: {} for name, _ in DIMS}, "tag": {}}})


def _put(table: dict, name: str, net: int, sales: int) -> None:
    cell = table.setdefault(name, {"net_minor": 0, "sales": 0})
    cell["net_minor"] += net
    cell["sales"] += sales


def _attribute(block: dict, book: Book, row: dict, net: int, sales: int) -> None:
    src = book.attribution(row)
    for name, col in DIMS:
        _put(block["by"][name], _name(name, row["tool"] if col == "tool" else src[col]),
             net, sales)
    for key, value in sorted(book.tags(row).items()):
        _put(block["by"]["tag"].setdefault(key, {}), str(value), net, sales)


def days(db, site: str, tz, first: date, last: date, book: Book | None = None) -> dict:
    """{local day: {currency: figures}} for first..last; a day with no sale
    and no refund is left out."""
    book = book or Book(db, site)
    lo, hi = first.isoformat(), last.isoformat()
    out: dict = {}
    for r in book.sales:
        day = _local_day(r["at"], tz)
        if not lo <= day <= hi:
            continue
        block = _cur(out.setdefault(day, {}), r["currency"])
        value = int(r["value_minor"])
        block["gross_minor"] += value
        block["net_minor"] += value
        block["sales"] += 1
        block["renewals" if book.renewal[r["id"]] else "new_customers"] += 1
        _attribute(block, book, r, value, 1)
    for r, at, value in book.parts:
        day = _local_day(at, tz)
        if not lo <= day <= hi:
            continue
        block = _cur(out.setdefault(day, {}), r["currency"])
        block["refunded_minor"] += value
        block["net_minor"] -= value
        block["refunds"] += 1
        _attribute(block, book, r, -value, 0)
    return out


def ltv(db, site: str, tz, book: Book | None = None) -> dict:
    """{currency: {customers, net_minor, renewals, repeat_customers, first_day,
    by_first_source: {name: {customers, net_minor, renewals,
    repeat_customers}}}} over every row kept. A customer's first source is that
    of their first sale's attribution; their net, their sales less the parts
    of the refunds on them (a refund with no sale counted belongs to no
    customer)."""
    book = book or Book(db, site)
    people: dict = {}
    for r in book.sales:
        who = book.customer(r)
        p = people.setdefault(who, {"currency": r["currency"], "net": 0, "sales": 0,
                                    "source": _name("first_source",
                                                    book.attribution(r)["first_source"]),
                                    "day": _local_day(r["at"], tz)})
        p["net"] += int(r["value_minor"])
        p["sales"] += 1
    for r, _, value in book.parts:
        people[book.customer(book.sale_of(r))]["net"] -= value
    out: dict = {}
    for p in people.values():
        total = out.setdefault(p["currency"], {"customers": 0, "net_minor": 0, "renewals": 0,
                                               "repeat_customers": 0, "first_day": p["day"],
                                               "by_first_source": {}})
        total["first_day"] = min(total["first_day"], p["day"])
        for cell in (total, total["by_first_source"].setdefault(p["source"], {
                "customers": 0, "net_minor": 0, "renewals": 0, "repeat_customers": 0})):
            cell["customers"] += 1
            cell["net_minor"] += p["net"]
            cell["renewals"] += p["sales"] - 1
            cell["repeat_customers"] += 1 if p["sales"] > 1 else 0
    return out


def currencies(book: Book) -> dict:
    """{currency: its decimals} for every currency the site's counted sales are in
    (a counted refund is in its sale's)."""
    from .conversions.money import decimals
    return {c: decimals(c) for c in sorted({r["currency"] for r in book.sales})}


def first_day(db, site: str, tz) -> str | None:
    """The local day of the site's first counted row with a value: revenue is
    recorded from it on. None: no value yet."""
    got = db.execute("SELECT MIN(at) FROM conversions WHERE site = ? AND test = 0 AND "
                     "value_minor IS NOT NULL AND currency IS NOT NULL", (site,)).fetchone()[0]
    return _local_day(got, tz) if got else None


def without_sale(book: Book) -> dict:
    """{"count": refund rows kept that no figure counts (no counted sale, or no
    value in the sale's currency), "currencies": {currency: their total, over
    0}} over every row kept: stored, never subtracted."""
    total: dict = {}
    for r in book.orphans:
        if r["value_minor"] is not None and r["currency"] and int(r["value_minor"]) > 0:
            total[r["currency"]] = total.get(r["currency"], 0) + int(r["value_minor"])
    return {"count": len(book.orphans), "currencies": dict(sorted(total.items()))}
