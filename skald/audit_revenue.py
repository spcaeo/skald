"""The second count of revenue on leads (2.32): conversions.json's per-day
`revenue` and its `ltv` (conversions_revenue.py), counted again two ways.

1. SQL over conversions.sqlite opened read-only: the sales by NOT EXISTS (a
   `completed` row is no sale when the same tool and ref has a `paid` one with
   a value), attribution by a correlated sub-select of the first finished
   row, renewals by EXISTS of an earlier sale of the same customer and
   currency, tags by json_each, every figure by GROUP BY. Every figure, every
   cell.
2. The hook spool (`lead`, `json` and `stripe` lines) with this module's own
   reading of value, currency, customer_ref and Stripe's amounts, its own
   first-delivery-wins on (tool, ref, stage), its own refund rule (one per
   sale, the largest total in the sale's currency; no value: the sale's value
   known then; Stripe's refund found by its payment intent or invoice) and
   its own day: per day and currency the gross, refunded and net sums and the
   counts of sales, refunds, new customers and renewals.

It shares only the name lists in conversions/__init__.py (the currencies, the
decimals, STRIPE_HUNDREDS, MAX_MINOR, CUSTOMER_REF, the labels for what was not
recorded) and the spool and test/removed readers of the audit itself
(audit_conversions.py). A day either road disagrees with is withheld, the
`ltv` block too (audit_conversions.check_file, conversions_data.withhold).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .audit_conversions import (_Bad, _instant, _lead, _lines, _zone_of,
                                test_keys)
from .audit_conversions_figures import _bounds, _open
from .conversions import (CURRENCIES, CUSTOMER_PHONE, CUSTOMER_REF, DECIMALS, FUTURE_SLACK,
                          MAX_AMOUNT_TEXT, MAX_MINOR, NO_LABEL, STRIPE_HUNDREDS, TAG_IP,
                          TAG_MAX_DIGITS, UNKNOWN)

FIN = "('completed', 'paid')"
MONEY = "value_minor IS NOT NULL AND currency IS NOT NULL"
# conversions.json's `revenue.by` names -> the column (its own list).
COLS = (("source", "source_type"), ("first_source", "first_source"), ("campaign", "campaign"),
        ("landing", "landing"), ("country", "country"), ("device", "device"),
        ("tool", "tool"), ("label", "label"))
TOTALS = ("gross_minor", "refunded_minor", "net_minor", "sales", "refunds", "new_customers",
          "renewals")

BASE = (f"m AS (SELECT * FROM conversions WHERE site = ? AND test = 0), "
        f"sale AS (SELECT c.* FROM m c WHERE c.stage IN {FIN} AND c.{MONEY} AND NOT "
        f"(c.stage = 'completed' AND EXISTS (SELECT 1 FROM m p WHERE p.tool = c.tool AND "
        f"p.external_ref = c.external_ref AND p.stage = 'paid' AND p.{MONEY}))), "
        # a refund counts only on a counted sale in its currency; each part on its day
        f"refund_row AS (SELECT r.* FROM m r WHERE r.stage = 'refunded' AND r.{MONEY} AND "
        f"EXISTS (SELECT 1 FROM sale s WHERE s.tool = r.tool AND s.external_ref = "
        f"r.external_ref AND s.currency = r.currency)), "
        f"refund AS (SELECT r.*, p.at AS part_at, p.value_minor AS part FROM refund_row r "
        f"JOIN refund_parts p ON p.conversion_id = r.id WHERE p.value_minor > 0) ")


def _attr(col: str, row: str) -> str:
    """The column of `row`'s attribution: the first finished row of its tool
    and ref (by at, stage, id), else the row's own."""
    first = (f"FROM m a WHERE a.tool = {row}.tool AND a.external_ref = {row}.external_ref "
             f"AND a.stage IN {FIN}")
    return (f"CASE WHEN EXISTS (SELECT 1 {first}) THEN (SELECT a.{col} {first} ORDER BY a.at, "
            f"a.stage, a.id LIMIT 1) ELSE {row}.{col} END")


def _renewal(s: str) -> str:
    return (f"CASE WHEN {s}.customer_ref IS NOT NULL AND EXISTS (SELECT 1 FROM sale e WHERE "
            f"e.customer_ref = {s}.customer_ref AND e.currency = {s}.currency AND (e.at < "
            f"{s}.at OR (e.at = {s}.at AND e.id < {s}.id))) THEN 1 ELSE 0 END")


def _events() -> str:
    """Each sale and refund of the bounded days, with its money and names."""
    def names(row: str) -> str:
        return ", ".join(f"{_attr(col, row) if col != 'tool' else row + '.tool'} AS {name}"
                         for name, col in COLS)
    tags_r = ("CASE WHEN EXISTS (SELECT 1 FROM sale x WHERE x.tool = r.tool AND x.external_ref "
              "= r.external_ref) THEN (SELECT x.tags FROM sale x WHERE x.tool = r.tool AND "
              "x.external_ref = r.external_ref) ELSE r.tags END")
    return (f"ev AS (SELECT b.day AS day, s.currency AS cur, s.value_minor AS gross, 0 AS back, "
            f"1 AS sales, 0 AS refunds, {_renewal('s')} AS renew, {names('s')}, s.tags AS tg "
            f"FROM sale s JOIN b ON s.at >= b.lo AND s.at < b.hi "
            f"UNION ALL SELECT b.day, r.currency, 0, r.part, 0, 1, 0, {names('r')}, "
            f"{tags_r} FROM refund r JOIN b ON r.part_at >= b.lo AND r.part_at < b.hi) ")


def recount_store(path: Path, site: str, tz, first: date, last: date) -> dict:
    """{day: {key: n}} by SQL: (cur, total), (cur, "by", name, value, "net_minor" or
    "sales"), (cur, "tag", key, value, ...)."""
    head, args = _bounds(tz, first, last)
    sql = head.rstrip() + ", " + BASE + ", " + _events()
    out: dict = {}
    db = _open(path)
    try:
        for day, cur, gross, back, sales, refunds, new, renew in db.execute(
                sql + "SELECT day, cur, SUM(gross), SUM(back), SUM(sales), SUM(refunds), "
                "SUM(CASE WHEN sales = 1 AND renew = 0 THEN 1 ELSE 0 END), SUM(renew) FROM ev "
                "GROUP BY 1, 2", [*args, site]):
            got = out.setdefault(day, {})
            for k, v in zip(TOTALS, (gross, back, gross - back, sales, refunds, new, renew)):
                got[(cur, k)] = v
        for name, _ in COLS:
            blank = NO_LABEL if name == "label" else UNKNOWN
            for day, cur, value, net, sales in db.execute(
                    sql + f"SELECT day, cur, COALESCE(NULLIF({name}, ''), ?), SUM(gross - back), "
                    f"SUM(sales) FROM ev GROUP BY 1, 2, 3", [*args, site, blank]):
                out.setdefault(day, {})[(cur, "by", name, str(value), "net_minor")] = net
                out[day][(cur, "by", name, str(value), "sales")] = sales
        for day, cur, key, value, net, sales in db.execute(
                sql + "SELECT ev.day, ev.cur, j.key, j.value, SUM(ev.gross - ev.back), "
                "SUM(ev.sales) FROM ev, json_each(CASE WHEN json_valid(ev.tg) AND "
                "json_type(ev.tg) = 'object' THEN ev.tg ELSE '{}' END) j GROUP BY 1, 2, 3, 4",
                [*args, site]):
            out.setdefault(day, {})[(cur, "tag", str(key), str(value), "net_minor")] = net
            out[day][(cur, "tag", str(key), str(value), "sales")] = sales
    finally:
        db.close()
    return out


def recount_ltv(path: Path, site: str, tz) -> dict:
    """{key: n} by SQL over every row kept: (cur, total), (cur, "first_day"),
    (cur, "by", first source, total)."""
    who = ("CASE WHEN s.customer_ref IS NOT NULL THEN 'c' || s.customer_ref ELSE '#' || "
           "s.tool || '|' || s.external_ref END")
    sql = ("WITH " + BASE + f", cust AS (SELECT s.*, {who} AS who FROM sale s), "
           # the refund rows' own totals (the main road adds up their parts)
           "per AS (SELECT c.who, c.currency AS cur, COUNT(*) AS n, SUM(c.value_minor) - "
           "COALESCE(SUM((SELECT SUM(r.value_minor) FROM refund_row r WHERE r.tool = c.tool AND "
           "r.external_ref = c.external_ref AND r.currency = c.currency)), 0) AS net, "
           "MIN(c.at) AS first_at, "
           f"(SELECT {_attr('first_source', 'x')} FROM cust x WHERE x.who = c.who AND "
           "x.currency = c.currency ORDER BY x.at, x.id LIMIT 1) AS src FROM cust c "
           "GROUP BY c.who, c.currency) ")
    out: dict = {}
    db = _open(path)
    try:
        for cur, src, people, net, renewals, repeat, first_at in db.execute(
                sql + "SELECT cur, COALESCE(NULLIF(src, ''), ?), COUNT(*), SUM(net), "
                "SUM(n - 1), SUM(n > 1), MIN(first_at) FROM per GROUP BY 1, 2",
                (site, UNKNOWN)):
            for k, v in (("customers", people), ("net_minor", net), ("renewals", renewals),
                         ("repeat_customers", repeat)):
                out[(cur, k)] = out.get((cur, k), 0) + v
                out[(cur, "by", src, k)] = v
            day = datetime.strptime(first_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc).astimezone(tz).date().isoformat()
            out[(cur, "first_day")] = min(out.get((cur, "first_day"), day), day)
    finally:
        db.close()
    return out


def recount_since(path: Path, site: str, tz) -> str | None:
    """The local day of the first counted row with a value, by SQL; None."""
    db = _open(path)
    try:
        got = db.execute(f"SELECT MIN(at) FROM conversions WHERE site = ? AND test = 0 AND "
                         f"{MONEY}", (site,)).fetchone()[0]
    finally:
        db.close()
    if not got:
        return None
    return datetime.strptime(got, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc).astimezone(tz).date().isoformat()


def recount_alone(path: Path, site: str) -> dict:
    """{"count": n, "currencies": {cur: total}} by SQL: the refunds kept with no
    counted sale of their tool and ref."""
    sql = ("WITH " + BASE + ", alone AS (SELECT r.* FROM m r WHERE r.stage = 'refunded' AND "
           "r.id NOT IN (SELECT id FROM refund_row)) ")
    db = _open(path)
    try:
        count = db.execute(sql + "SELECT COUNT(*) FROM alone", (site,)).fetchone()[0]
        cash = {cur: total for cur, total in db.execute(
            sql + f"SELECT currency, SUM(value_minor) FROM alone WHERE {MONEY} AND value_minor > 0 "
            "GROUP BY 1 ORDER BY 1", (site,))}
    finally:
        db.close()
    return {"count": count, "currencies": cash}


# ------------------------------------------------------------ the spool

_AMOUNT = re.compile(r"\A(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z")


def _minor(raw, cur: str | None) -> int | None:
    """Major units -> minor units, by text arithmetic (no Decimal)."""
    if cur is None or isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    places = DECIMALS.get(cur, 2)
    if isinstance(raw, int):
        if raw < 0:
            return None
        n = raw * 10 ** places
        return n if n <= MAX_MINOR else None
    if isinstance(raw, str) and len(raw.strip()) > MAX_AMOUNT_TEXT:
        return None
    s = raw.strip() if isinstance(raw, str) else repr(raw)
    if len(s) > MAX_AMOUNT_TEXT or not _AMOUNT.match(s):
        return None
    whole, _, frac = s.partition(".")
    frac = frac.rstrip("0")
    if len(frac) > places:
        return None
    n = int(whole or "0") * 10 ** places + int(frac.ljust(places, "0") or "0")
    return n if n <= MAX_MINOR else None


def _currency(raw) -> str | None:
    if not isinstance(raw, str):
        return None
    cur = raw.strip().upper()
    return cur if cur in CURRENCIES else None


def _customer(raw) -> str | None:
    if isinstance(raw, bool) or not isinstance(raw, (str, int)) or \
            (isinstance(raw, str) and len(raw) > 200):
        return None
    got = str(raw).strip()
    if not CUSTOMER_REF.match(got) or TAG_IP.search(got):
        return None
    digits = len([ch for ch in got if "0" <= ch <= "9"])
    return None if CUSTOMER_PHONE.match(got) and digits > TAG_MAX_DIGITS else got


def _stripe_amount(raw, cur: str | None) -> int | None:
    if cur is None or isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return None
    if cur in STRIPE_HUNDREDS:
        if raw % 100:
            return None
        raw //= 100
    return raw if raw <= MAX_MINOR else None


def _ident(value) -> str:
    if isinstance(value, dict):
        value = value.get("id")
    return str(value).strip()[:120] if isinstance(value, str) else ""


def _lead_money(item: dict) -> dict:
    sent = item.get("value") not in (None, "")
    cur = _currency(item.get("currency")) if sent else None
    value = _minor(item.get("value"), cur) if sent else None
    return {"value": value, "cur": cur if value is not None else None, "sent": sent,
            "customer": _customer(item.get("customer_ref")), "pays": (), "find": ()}


def _money_lines(tool: str, body, zone, received: datetime) -> list[tuple]:
    """[(action, stage, ref, at, money)] of one spooled body; _Bad for one the
    main road refuses (audit_conversions._lead's own checks). Stripe's
    invoice_payment.paid is ("", "link", invoice, at, {"pays": (intent,)})."""
    if tool in ("lead", "json"):
        items = [body] if tool == "lead" else (
            body.get("records") if isinstance(body, dict) and "records" in body else body)
        items = [items] if isinstance(items, dict) else items
        if not isinstance(items, list) or not 0 < len(items) <= 100:
            raise _Bad
        out = []
        for item in items:
            action, stage, ref, at = _lead(item, zone)
            out.append((action, stage, ref, at or received, _lead_money(item)))
        return out
    if tool != "stripe" or not isinstance(body, dict) or body.get("object") != "event":
        return []
    data = (body.get("data") or {}).get("object") if isinstance(body.get("data"), dict) else None
    if not isinstance(data, dict):
        return []
    kind = str(body.get("type") or "")
    at = _instant(body.get("created")) or received
    if kind == "invoice_payment.paid":
        inv = _ident(data.get("invoice"))
        pay = data.get("payment")
        pi = _ident(pay.get("payment_intent")) if isinstance(pay, dict) else ""
        return [("", "link", inv, at, {"pays": (pi,)})] if inv and pi else []
    ref = _ident(data.get("id"))
    if not ref:
        return []
    cur = _currency(data.get("currency"))
    cust = data.get("customer") if isinstance(data.get("customer"), str) else None
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        stage = "started" if kind == "checkout.session.completed" and \
            data.get("payment_status") == "unpaid" else "paid"
        value = _stripe_amount(data.get("amount_total"), cur)
        pay = _ident(data.get("payment_intent")) or _ident(data.get("invoice"))
        return [("paid", stage, ref, at, {
            "value": value, "cur": cur if value is not None else None, "sent": True,
            "customer": _customer(cust), "pays": (pay,) if pay else (), "find": ()})]
    if kind == "invoice.paid" and data.get("billing_reason") == "subscription_cycle":
        value = _stripe_amount(data.get("amount_paid"), cur)
        pay = _ident(data.get("payment_intent")) or ref       # basil: no payment intent
        return [("paid", "paid", ref, at, {
            "value": value, "cur": cur if value is not None else None, "sent": True,
            "customer": _customer(cust), "pays": (pay,), "find": ()})]
    if kind == "charge.refunded":
        value = _stripe_amount(data.get("amount_refunded"), cur)
        pay, inv = _ident(data.get("payment_intent")), _ident(data.get("invoice"))
        return [("paid", "refunded", pay or ref, at, {
            "value": value, "cur": cur if value is not None else None, "sent": True,
            "customer": None, "pays": (pay,) if pay else (),
            "find": tuple(k for k in (pay, inv) if k)})]
    return []


class _Replay:
    """The hook spool replayed in the order it came, by this module's own
    rules: first delivery wins on (tool, ref, stage); a refund is one row per
    sale, found by its payment and invoice (and what invoice_payment.paid
    joined them to), its whole sale's value when none was sent, never more
    than the sale nor in another currency, each rise a part with its own
    time; a refund that came before its sale moves onto it when it comes."""

    def __init__(self) -> None:
        self.rows: dict = {}            # (tool, ref, stage) -> row
        self.links: dict = {}           # (tool, key) -> {keys}
        self.n = 0

    def _keys(self, tool: str, keys) -> set:
        got = {k for k in keys if k}
        for k in list(got):
            got |= self.links.get((tool, k), set())
        return got

    def _sale(self, tool: str, ref: str) -> dict | None:
        return _sale(self.rows, tool, ref)

    def _seq(self) -> int:
        self.n += 1
        return self.n

    def drop(self, key: tuple) -> None:
        """A row taken away (the store's `removed`), at the time it was: what it
        changed while it was there (a refund cut or filled by it) stays."""
        self.rows.pop(key, None)

    def take(self, tool: str, action: str, stage: str, ref: str, at: datetime,
             cash: dict) -> None:
        if stage == "link":
            for a, b in ((ref, cash["pays"][0]), (cash["pays"][0], ref)):
                self.links.setdefault((tool, a), set()).add(b)
            keys = {ref, cash["pays"][0]}
            for r in sorted(self.rows.values(), key=lambda r: r["order"]):
                if r["tool"] == tool and r["stage"] in ("completed", "paid") and \
                        r["value"] is not None and (r["ref"] in keys or keys & set(r["pays"])):
                    self._claim(tool, r["ref"])
            return
        if stage == "refunded":
            ref, cash = self._refund(tool, ref, cash)
        key = (tool, ref, stage)
        if key in self.rows:
            old = self.rows[key]
            if stage == "refunded" and cash["value"] is None and cash.get("later") and \
                    old["value"] is None and not any(p[1] is None for p in old["parts"]):
                old["parts"].append([at, None, self._seq()])     # waits for the sale's value
                return
            if stage == "refunded" and cash["value"] is not None and cash["cur"] and (
                    old["value"] is None or (old["cur"] == cash["cur"]
                                             and cash["value"] > old["value"])):
                old["parts"] = [p for p in old["parts"] if p[1] is not None]
                rise = cash["value"] - (old["value"] or 0)
                if rise:
                    old["parts"].append([at, rise, self._seq()])
                old["value"], old["cur"] = cash["value"], cash["cur"]
            return
        row = {"tool": tool, "ref": ref, "stage": stage, "action": action, "at": at,
               "order": self._seq(), "value": cash["value"], "cur": cash["cur"],
               "customer": cash.get("customer"), "pays": tuple(cash.get("pays") or ()),
               "parts": []}
        if stage == "refunded":
            if cash["value"]:                   # a refund of 0 is no part
                row["parts"] = [[at, cash["value"], self._seq()]]
            elif cash.get("later"):
                row["parts"] = [[at, None, self._seq()]]
        self.rows[key] = row
        if stage in ("completed", "paid") and cash["value"] is not None:
            self._claim(tool, ref)

    def _refund(self, tool: str, ref: str, cash: dict) -> tuple[str, dict]:
        keys = self._keys(tool, cash["find"])
        if keys:
            hits = [(r["at"], r["order"], r["ref"]) for r in self.rows.values()
                    if r["tool"] == tool and r["stage"] in ("completed", "paid")
                    and (r["ref"] in keys or keys & set(r["pays"]))]
            if hits:
                ref = min(hits)[2]
        sale = self._sale(tool, ref)
        cash = dict(cash)
        if cash["value"] is None and not cash["sent"]:
            if sale is not None:
                cash["value"], cash["cur"] = sale["value"], sale["cur"]
            else:
                cash["later"] = True
        elif cash["value"] is not None and sale is not None:
            if cash["cur"] != sale["cur"]:
                cash["value"] = cash["cur"] = None
            elif cash["value"] > sale["value"]:
                cash["value"] = sale["value"]
        return ref, cash

    def _claim(self, tool: str, ref: str) -> None:
        sale = self._sale(tool, ref)
        if sale is None:
            return
        pays = [p for r in self.rows.values() if r["tool"] == tool and r["ref"] == ref
                for p in r["pays"]]
        keys = self._keys(tool, [ref, *pays])
        waiting = sorted((r for r in self.rows.values() if r["tool"] == tool
                          and r["stage"] == "refunded"
                          and (r["ref"] in keys or keys & set(r["pays"]))),
                         key=lambda r: r["order"])
        for r in waiting:
            if r["ref"] != ref:
                if (tool, ref, "refunded") in self.rows or any(
                        (tool, r["ref"], s) in self.rows for s in ("completed", "paid")):
                    continue
                del self.rows[(tool, r["ref"], "refunded")]
                r["ref"] = ref
                self.rows[(tool, ref, "refunded")] = r
            self._fit(r, sale)

    @staticmethod
    def _fit(r: dict, sale: dict) -> None:
        whole = sale["value"]
        if r["value"] is None:
            later = [p for p in r["parts"] if p[1] is None]
            if later:
                r["parts"] = [[later[0][0], whole, later[0][2]]] if whole else []
                r["value"], r["cur"] = whole, sale["cur"]
            return
        if r["cur"] != sale["cur"]:
            r["parts"], r["value"], r["cur"] = [], None, None
            return
        if r["value"] <= whole:
            return
        left, kept = whole, []
        for at, v, seq in sorted(r["parts"], key=lambda p: (p[0], p[2])):
            got = min(v or 0, left)
            left -= got
            if got:
                kept.append([at, got, seq])
        r["parts"], r["value"] = kept, whole


def replay(spool: Path, site: str, removed=None) -> dict:
    """{(tool, ref, stage): row} of the lead, json and stripe hooks' spool,
    replayed by _Replay (audit_conversions.recount takes its refunds from it).
    `removed`: [(removed at, tool, ref, stage)] (_removals), or
    audit_conversions.removed_keys' {(tool, ref, stage): last removed at}; each
    removal is replayed at its time, between the lines received before it and
    after it, on the row's ref at that time (a refund moved onto its sale is
    removed under the sale's ref, as the store has it)."""
    if isinstance(removed, dict):
        removed = [(at, *key) for key, at in removed.items()]
    gone = sorted(removed or (), key=lambda g: g[0])
    book = _Replay()
    for line in _lines(spool):
        tool = line.get("tool")
        if line.get("site") != site or tool not in ("lead", "json", "stripe"):
            continue
        received = _instant(line.get("received_at"))
        if received is None:
            continue
        while gone and gone[0][0] < received:
            book.drop(tuple(gone.pop(0)[1:]))
        try:
            found = _money_lines(tool, line.get("body"), _zone_of(line), received)
            if any(at > received + timedelta(seconds=FUTURE_SLACK) for *_, at, _ in found):
                raise _Bad
        except _Bad:
            continue
        for action, stage, ref, at, cash in found:
            book.take(tool, action, stage, ref, at, cash)
    for g in gone:
        book.drop(tuple(g[1:]))
    return book.rows


def _removals(path: Path, site: str) -> list[tuple]:
    """[(removed at, tool, ref, stage)] of the store's `removed`, oldest first."""
    if not Path(path).is_file():
        return []
    db = _open(path)
    try:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND "
                          "name = 'removed'").fetchone():
            return []
        rows = db.execute("SELECT removed_at, tool, external_ref, stage FROM removed WHERE "
                          "site = ? ORDER BY removed_at, id", (site,)).fetchall()
    finally:
        db.close()
    return [(_instant(at), tool, ref, stage) for at, tool, ref, stage in rows
            if _instant(at) is not None]


def recount_spool(spool: Path, site: str, tz, first: date, last: date,
                  skip: frozenset = frozenset(), removed=None,
                  floor: datetime | None = None) -> tuple[dict, dict, dict, str | None]:
    """({day: {(cur, total): n}}, {(cur, total): n} lifetime, {"count": n,
    "currencies": {cur: total}} of the refunds no figure counts, the local day
    of the first row with a value) from the spool's own lines. Rows before
    `floor` (the store's first row: retention) are not counted, nor rows
    marked test (`skip`) or taken away (`removed`, replayed at their time)."""
    rows = replay(spool, site, removed)
    kept = {k: r for k, r in rows.items() if k not in skip and (floor is None or r["at"] >= floor)}
    sales = []
    for (tool, ref, stage), r in kept.items():
        if stage in ("completed", "paid") and r["value"] is not None and r["cur"]:
            paid = kept.get((tool, ref, "paid"))
            if stage == "completed" and paid is not None and paid["value"] is not None \
                    and paid["cur"]:
                continue
            sales.append(r)
    sales.sort(key=lambda r: (r["at"], r["order"]))
    per_day: dict = {}
    life: dict = {}
    people: dict = {}
    seen: set = set()
    by_ref = {(r["tool"], r["ref"]): r for r in sales}
    alone = {"count": 0, "currencies": {}}

    def add(day_key: str, cur: str, name: str, n: int) -> None:
        per_day.setdefault(day_key, {})
        per_day[day_key][(cur, name)] = per_day[day_key].get((cur, name), 0) + n

    def who_of(r: dict) -> tuple:
        return ("c", r["customer"], r["cur"]) if r["customer"] else ("s", r["tool"], r["ref"],
                                                                     r["cur"])

    lo, hi = first.isoformat(), last.isoformat()
    for r in sales:
        who = who_of(r)
        again = who in seen
        seen.add(who)
        p = people.setdefault(who, [0, 0])
        p[0] += 1
        p[1] += r["value"]
        day = r["at"].astimezone(tz).date().isoformat()
        if lo <= day <= hi:
            for name, n in (("gross_minor", r["value"]), ("net_minor", r["value"]),
                            ("sales", 1), ("renewals" if again else "new_customers", 1),
                            ("refunded_minor", 0), ("refunds", 0),
                            ("new_customers" if again else "renewals", 0)):
                add(day, r["cur"], name, n)
    for (tool, ref, stage), r in kept.items():
        if stage != "refunded":
            continue
        sale = by_ref.get((tool, ref))
        if sale is None or r["value"] is None or not r["cur"] or sale["cur"] != r["cur"]:
            alone["count"] += 1             # kept, counted nowhere: listed
            if r["value"] and r["cur"]:
                alone["currencies"][r["cur"]] = alone["currencies"].get(r["cur"], 0) + r["value"]
            continue
        for at, v, _ in r["parts"]:
            if not v:
                continue
            people[who_of(sale)][1] -= v
            day = at.astimezone(tz).date().isoformat()
            if lo <= day <= hi:
                for name, n in (("refunded_minor", v), ("net_minor", -v), ("refunds", 1),
                                ("gross_minor", 0), ("sales", 0), ("new_customers", 0),
                                ("renewals", 0)):
                    add(day, r["cur"], name, n)
    for who, (n, net) in people.items():
        cur = who[-1]
        for name, v in (("customers", 1), ("net_minor", net), ("renewals", n - 1),
                        ("repeat_customers", 1 if n > 1 else 0)):
            life[(cur, name)] = life.get((cur, name), 0) + v
    valued = [r["at"] for r in kept.values() if r["value"] is not None and r["cur"]]
    since = min(valued).astimezone(tz).date().isoformat() if valued else None
    alone["currencies"] = dict(sorted(alone["currencies"].items()))
    return per_day, life, alone, since


def _sale(rows: dict, tool: str, ref: str) -> dict | None:
    for stage in ("paid", "completed"):
        got = rows.get((tool, ref, stage))
        if got is not None and got["value"] is not None and got["cur"]:
            return got
    return None


# ------------------------------------------------------------ the check

def _flat_day(revenue: dict) -> dict:
    out: dict = {}
    for cur, block in (revenue or {}).items():
        for k in TOTALS:
            out[(cur, k)] = block.get(k)
        for name, cells in (block.get("by") or {}).items():
            if name == "tag":
                for key, values in cells.items():
                    for value, cell in values.items():
                        for k in ("net_minor", "sales"):
                            out[(cur, "tag", key, value, k)] = cell.get(k)
                continue
            for value, cell in cells.items():
                for k in ("net_minor", "sales"):
                    out[(cur, "by", name, value, k)] = cell.get(k)
    return out


def _flat_ltv(block: dict) -> dict:
    out: dict = {}
    for cur, got in (block or {}).items():
        for k in ("customers", "net_minor", "renewals", "repeat_customers"):
            out[(cur, k)] = got.get(k)
        out[(cur, "first_day")] = got.get("first_day")
        for src, cell in (got.get("by_first_source") or {}).items():
            for k in ("customers", "net_minor", "renewals", "repeat_customers"):
                out[(cur, "by", src, k)] = cell.get(k)
    return out


def _diff(where: str, mine: dict, theirs: dict, road: str) -> list[str]:
    return [f"{where} revenue {' '.join(map(str, key))}: file {mine.get(key)}, {road} "
            f"{theirs.get(key)}" for key in sorted(set(mine) | set(theirs), key=str)
            if mine.get(key) != theirs.get(key)]


def _floor(path: Path, site: str) -> datetime | None:
    db = _open(path)
    try:
        got = db.execute("SELECT MIN(at) FROM conversions WHERE site = ?", (site,)).fetchone()[0]
    finally:
        db.close()
    return _instant(got) if got else None


def check(config: dict, folder: Path, site: str, tz, first: date, last: date,
          blob: dict) -> dict[str, list[str]]:
    """{"days/<day>" or "ltv": problems} for conversions.json's revenue."""
    from .conversions import spool as spool_mod
    from .conversions import store
    path = store.path_for(config, folder)
    if path is None or not Path(path).is_file():
        return {}
    shown = {d["day"]: d for d in blob.get("days") or [] if d.get("state") == "ok"}
    by_sql = recount_store(path, site, tz, first, last)
    skip = test_keys(path, site)
    by_spool, life, alone, spool_since = recount_spool(
        spool_mod.spool_dir(config, folder), site, tz, first, last, skip,
        _removals(path, site), _floor(path, site))
    out: dict[str, list[str]] = {}
    sql_since = recount_since(path, site, tz)
    said = blob.get("revenue_since")
    if said != sql_since or said != spool_since:
        out["revenue_since"] = [f"revenue recorded from: file {said}, SQL recount {sql_since}, "
                                f"spool recount {spool_since}"]
    for day, d in shown.items():
        want = sql_since is not None and day >= sql_since
        if ("revenue" in d) != want:
            out[f"days/{day}"] = [f"{day} revenue: the file {'has' if 'revenue' in d else 'has no'}"
                                  f" block, values are recorded from {sql_since}"]
            continue
        if not want:
            if by_sql.get(day) or by_spool.get(day):
                out[f"days/{day}"] = [f"{day} revenue: the file has none, the recounts find some"]
            continue
        mine = _flat_day(d.get("revenue"))
        problems = _diff(day, mine, by_sql.get(day, {}), "SQL recount")
        totals = {k: v for k, v in mine.items() if len(k) == 2}
        problems += _diff(day, totals, by_spool.get(day, {}), "spool recount")
        if problems:
            out[f"days/{day}"] = problems
    ltv = blob.get("ltv")
    if isinstance(ltv, dict) and "currencies" in ltv:
        mine = _flat_ltv(ltv["currencies"])
        problems = _diff("ltv", mine, recount_ltv(path, site, tz), "SQL recount")
        totals = {k: v for k, v in mine.items() if len(k) == 2 and k[1] != "first_day"}
        problems += _diff("ltv", totals, life, "spool recount")
        if problems:
            out["ltv"] = problems
    elif ltv is None and recount_ltv(path, site, tz):
        out["ltv"] = ["ltv: the file has none, the SQL recount finds sales"]
    shown_alone = blob.get("refunds_without_sale")
    if isinstance(shown_alone, dict) and "count" in shown_alone:
        problems = []
        for road, got in (("SQL recount", recount_alone(path, site)), ("spool recount", alone)):
            if got != {"count": shown_alone.get("count"),
                       "currencies": shown_alone.get("currencies")}:
                problems.append(f"refunds without a sale: file {shown_alone}, {road} {got}")
        if problems:
            out["refunds_without_sale"] = problems
    return out
