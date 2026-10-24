"""Sale alerts (2.33): a lead gained a counted sale value, or a counted refund
took money back from one. Through the same machinery as every other alert
(alerts.py): the alert state, the site's alert mail, the outgoing webhook
event `alert.opened` (Slack's shape for a hooks.slack.com address),
alerts.json and Site > Alerts.

  sale           a lead gained a counted sale value: conversions_revenue.Book's
                 sale of a (tool, external ref), its `paid` row with a value,
                 else its `completed` one. One alert per (tool, ref), ever: a
                 `paid` row that follows an alerted `completed` one is the same
                 sale. Off by default (`alerts.sale`)
  sale_refunded  a counted refund part (Book's refunds: only against a counted
                 sale, in its currency, never past its value): one alert per
                 part, keyed by the sale and the refunded total after it. Off
                 by default (`alerts.sale_refund`)

What counts is the revenue figures' own rule (conversions_revenue.Book): a
test-marked row never counts, so it never alerts, and nothing before the
site's `revenue_since` (its first counted value) alerts. An alert goes only
for a sale or part Skald received after the rule was seen on (`since`, per
cause) and made in the last MAX_AGE_HOURS, so switching it on, a backfill or
a recount never mails old sales.

`alerts.sale_minimum` ("USD 100, EUR 90.50"): a sale below its currency's
minimum does not alert (a currency not listed alerts at any amount); a
refund alerts when its sale's value reaches the minimum.

Never twice: every sale and part decided (sent, or below the minimum) is kept
by a hash of its stable key in the alert state (`sales.done`), and the state
is written before anything is sent, so a restart, a recount, a replayed
spool or a second run never repeats one; the alert's id is made from the same
hash, so the webhook outbox (unique per webhook, event and ref) drops a
repeat too. A failed mail is noted on the alert, as for every alert, and not
retried. At most PER_RUN alerts a run; the rest wait for the next run.

The message holds the site, the amount (as the dashboard formats it), the
stage, the tool, the lead's attribution (source, first touch, campaign,
landing page without its query string, label), new customer or renewal, and
the time. Never an email, a name, an address, a visitor ID, the customer_ref
or the tool's own ref: like every alert body, nothing about a person.

Alerts are not figures: nothing is counted here that the dashboard shows,
so there is no second count (the amounts are the rows' own, the sums stay
conversions_revenue.py's and audit_revenue.py's).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

CAUSES = ("sale", "sale_refunded")
SEVERITY = {"sale": "low", "sale_refunded": "low"}
UNIT = {"sale": None, "sale_refunded": None}
# Each cause's switch: settings_store key alerts.<rule>, config.yml alerts.<rule>.
RULE = {"sale": "sale", "sale_refunded": "sale_refund"}
MINIMUM = "sale_minimum"
MAX_AGE_HOURS = 72          # a sale or part made longer ago never alerts
PER_RUN = 20                # alerts a run; the rest wait for the next
KEEP_DAYS = 14              # a decided key is kept this long past MAX_AGE_HOURS
MAX_MINIMUMS = 10
_ITEM = re.compile(r"^(?:([A-Za-z]{3})\s*([0-9][0-9.]*)|([0-9][0-9.]*)\s*([A-Za-z]{3}))$")


# ------------------------------------------------------------- settings

def clean_minimum(value) -> str | None:
    """The minimum as stored: "EUR 90.50, USD 100.00" (by currency, each with
    its decimals), None for none. ValueError in plain words otherwise.
    Takes "USD 100, EUR 90.5", "100 USD" or {"USD": 100}."""
    from .conversions.money import currency_of, minor, shown
    if value is None or (isinstance(value, str) and not value.strip()) or value == {}:
        return None
    if isinstance(value, dict):
        items = [(str(k), v) for k, v in value.items()]
    elif isinstance(value, str):
        items = []
        for part in re.split(r"[,;\n]+", value):
            part = part.strip()
            if not part:
                continue
            got = _ITEM.match(part)
            if not got:
                raise ValueError(f"Not an amount with its currency: {part[:30]!r}. "
                                 "Write it like USD 100, EUR 90.50.")
            items.append((got[1] or got[4], got[2] or got[3]))
    else:
        raise ValueError("The minimum is a list like USD 100, EUR 90.50.")
    out: dict = {}
    for cur_raw, amount in items:
        cur = currency_of(cur_raw)
        if cur is None:
            raise ValueError(f"Not a currency Skald knows: {cur_raw[:10]!r}.")
        if cur in out:
            raise ValueError(f"{cur} is given twice.")
        got = minor(amount if isinstance(amount, (int, str)) else str(amount), cur)
        if got is None:
            raise ValueError(f"Not an amount in {cur}: {str(amount)[:20]!r} (a number, at most "
                             f"its currency's decimals).")
        out[cur] = got
    if len(out) > MAX_MINIMUMS:
        raise ValueError(f"At most {MAX_MINIMUMS} currencies.")
    return ", ".join(f"{c} {shown(out[c], c)}" for c in sorted(out)) or None


def minimums(value) -> dict:
    """{currency: minor units} from a stored or config minimum; a part that is
    not one is left out (so it alerts at any amount, never less often)."""
    from .conversions.money import currency_of, minor
    out: dict = {}
    if isinstance(value, dict):
        items = [(str(k), str(v)) for k, v in value.items()]
    elif isinstance(value, str):
        items = []
        for part in re.split(r"[,;\n]+", value):
            got = _ITEM.match(part.strip())
            if got:
                items.append((got[1] or got[4], got[2] or got[3]))
    else:
        return {}
    for cur_raw, amount in items:
        cur = currency_of(cur_raw)
        got = minor(amount, cur) if cur else None
        if got is not None and cur not in out:
            out[cur] = got
    return out


def _flag(value, default: bool) -> bool:
    if value in (None, "", []):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def settings(config: dict | None) -> dict:
    section = (config or {}).get("alerts") or {}
    return {"sale": _flag(section.get("sale"), False),
            "sale_refund": _flag(section.get("sale_refund"), False),
            "minimum": minimums(section.get(MINIMUM))}


def minimum_words(cfg: dict) -> str:
    from .conversions.money import display
    got = cfg.get("minimum") or {}
    if not got:
        return "any amount"
    return "at least " + ", ".join(display(got[c], c) for c in sorted(got)) \
        + " (other currencies: any amount)"


def rules(cfg: dict) -> list[dict]:
    words = {
        "sale": f"a lead gains a counted sale value (paid, or completed with an amount; never a "
                f"test), {minimum_words(cfg)}; one alert per sale",
        "sale_refunded": "a counted refund takes money back from a sale (its sale "
                         f"{minimum_words(cfg)}); one alert per refund",
    }
    return [{"cause": c, "on": cfg[RULE[c]], "threshold": words[c], "unit": UNIT[c],
             "group": "revenue"} for c in CAUSES]


# ---------------------------------------------------------------- finding

def key(*parts) -> str:
    """The stable key of a sale or a refund part, hashed: no ref is kept."""
    return hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).hexdigest()[:32]


def _iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).isoformat(timespec="seconds")


def _when(at: str, tz) -> str:
    from .conversions.store import parse
    t = parse(at)
    local = t.astimezone(tz)
    zone = getattr(tz, "key", None) or str(tz)
    return f"{local:%Y-%m-%d %H:%M} {zone} ({t:%H:%M} UTC)"


def _attribution(book, row: dict) -> dict:
    """What the alert says about where the lead came from: never a person."""
    from .labels import shown
    src = book.attribution(row)
    landing = src.get("landing")
    if landing:
        landing = str(landing).split("?", 1)[0].split("#", 1)[0][:200] or "/"
    def name(v):
        return shown(v) if v not in (None, "") else shown("Unknown")
    return {"source": name(src.get("source_type")), "first_source": name(src.get("first_source")),
            "campaign": src.get("campaign") or None, "landing": landing or None,
            "label": row.get("label") or None, "tool": row["tool"]}


def _lines(a: dict) -> str:
    out = [f"Source (last touch): {a['source']}. First touch: {a['first_source']}."]
    more = [f"Campaign: {a['campaign']}." if a["campaign"] else "",
            f"Landing page: {a['landing']}." if a["landing"] else "",
            f"Label: {a['label']}." if a["label"] else ""]
    if any(more):
        out.append(" ".join(m for m in more if m))
    return "\n".join(out)


def _alert(cause: str, k: str, title: str, detail: str, data: dict, now: datetime) -> dict:
    at = _iso(now)
    return {"id": f"{cause}-{k[:16]}", "cause": cause, "subject": k[:16],
            "severity": SEVERITY[cause], "title": title, "detail": detail, "figure": None,
            "threshold": None, "unit": UNIT[cause], "data": data, "opened_at": at,
            "last_seen_at": at, "closed_at": at, "mailed": 0, "repeats": 0,
            "since_digest": 0, "last_mailed_at": None}


def _sale(book, r: dict, site: str, tz, k: str, now: datetime) -> dict:
    from .conversions.money import display
    amount = display(r["value_minor"], r["currency"])
    who = "a renewal (a later sale of the same customer)" if book.renewal.get(r["id"]) \
        else "a new customer"
    a = _attribution(book, r)
    detail = (f"A lead on {site} gained a counted sale value: {amount} ({r['currency']}), "
              f"stage {r['stage']}, reported by {r['tool']}; {who}.\n{_lines(a)}\n"
              f"Sale time: {_when(r['at'], tz)}.")
    return _alert("sale", k, f"Sale: {amount}, {r['stage']}", detail,
                  {"kind": "sale", "value_minor": int(r["value_minor"]),
                   "currency": r["currency"], "amount": amount, "stage": r["stage"],
                   "renewal": bool(book.renewal.get(r["id"])), "at": r["at"], **a}, now)


def _refund(book, refund: dict, sale: dict, part: int, total: int, at: str, site: str, tz,
            k: str, now: datetime) -> dict:
    from .conversions.money import display
    cur = sale["currency"]
    amount, sold, so_far = (display(part, cur), display(sale["value_minor"], cur),
                            display(total, cur))
    a = _attribution(book, refund)
    detail = (f"A refund on {site}: {amount} ({cur}) back from a {sold} sale, reported by "
              f"{refund['tool']}. Refunded so far on that sale: {so_far} of {sold}.\n"
              f"{_lines(a)}\nRefund time: {_when(at, tz)}.")
    return _alert("sale_refunded", k, f"Refund: {amount} of a {sold} sale", detail,
                  {"kind": "refund", "value_minor": part, "refunded_minor": total,
                   "sale_minor": int(sale["value_minor"]), "currency": cur, "amount": amount,
                   "stage": "refunded", "at": at, **a}, now)


def _signature(db, site: str, cfg: dict) -> list:
    """What changes when a new sale or part may be there: the rule's settings,
    the counted rows and the last ids. Equal to the last run's: nothing to do."""
    got = db.execute("SELECT COUNT(*), MAX(id) FROM conversions WHERE site = ? AND test = 0",
                     (site,)).fetchone()
    part = db.execute("SELECT MAX(p.id) FROM refund_parts p JOIN conversions c ON c.id = "
                      "p.conversion_id WHERE c.site = ?", (site,)).fetchone()
    return [cfg["sale"], cfg["sale_refund"], sorted(cfg["minimum"].items()), got[0], got[1],
            part[0]]


def track(state: dict, cfg: dict, now: datetime) -> tuple[dict, dict, dict]:
    """state["sales"]: `since` per cause (when the rule was first seen on; a
    rule seen off loses it, so switching it on again starts from then) and
    `done` {key hash: [UTC stamp, "sent" or "below"]}, old keys dropped."""
    from .conversions.store import stamp
    mine = state.setdefault("sales", {})
    since = mine.setdefault("since", {})
    done = mine.setdefault("done", {})
    for cause in CAUSES:
        if cfg[RULE[cause]]:
            since.setdefault(cause, stamp(now))
        else:
            since.pop(cause, None)
    cutoff = stamp(now - timedelta(hours=MAX_AGE_HOURS + KEEP_DAYS * 24))
    for k in [k for k, v in done.items() if v[0] < cutoff]:
        del done[k]
    return mine, since, done


def due(state: dict, config: dict, db, site: str, tz, now: datetime) -> list[dict]:
    """The sale alerts to open now; `state["sales"]` records every one decided."""
    from .conversions_revenue import Book, first_day
    from .conversions.store import parse, stamp
    cfg = settings(config)
    now = now.astimezone(timezone.utc)
    mine, since, done = track(state, cfg, now)
    if not since:
        mine.pop("signature", None)
        return []
    sign = _signature(db, site, cfg)
    if mine.get("signature") == sign:
        return []
    oldest = now - timedelta(hours=MAX_AGE_HOURS)
    first = first_day(db, site, tz)
    book = Book(db, site)
    least = cfg["minimum"]

    def fresh(at: str, received: str, cause: str) -> bool:
        if cause not in since or received < since[cause]:
            return False
        t = parse(at)
        return t >= oldest and first is not None and t.astimezone(tz).date().isoformat() >= first

    out: list[dict] = []
    full = False

    def decide(k: str, at: str, alert) -> None:
        nonlocal full
        if alert is not None and len(out) >= PER_RUN:
            full = True
            return
        done[k] = [max(stamp(now), at), "sent" if alert is not None else "below"]
        if alert is not None:
            out.append(alert)

    rows = {r["id"]: r for r in db.execute(
        "SELECT id, received_at FROM conversions WHERE site = ? AND test = 0", (site,))}
    for r in book.sales:
        k = key(site, "sale", r["tool"], r["external_ref"])
        if k in done or not fresh(r["at"], rows[r["id"]]["received_at"], "sale"):
            continue
        ok = int(r["value_minor"]) >= least.get(r["currency"], 0)
        decide(k, r["at"], _sale(book, r, site, tz, k, now) if ok else None)
    if "sale_refunded" in since:
        counted = {r["id"]: r for r in book.refunds}
        totals: dict = {}
        for rid, at, value, received in db.execute(
                "SELECT p.conversion_id, p.at, p.value_minor, p.received_at FROM refund_parts p "
                "JOIN conversions c ON c.id = p.conversion_id WHERE c.site = ? AND c.test = 0 "
                "AND p.value_minor > 0 ORDER BY p.at, p.id", (site,)):
            if rid not in counted:
                continue
            refund = counted[rid]
            totals[rid] = totals.get(rid, 0) + int(value)
            sale = book.sale_of(refund)
            k = key(site, "refund", refund["tool"], refund["external_ref"], totals[rid])
            if sale is None or k in done or not fresh(at, received, "sale_refunded"):
                continue
            ok = int(sale["value_minor"]) >= least.get(sale["currency"], 0)
            decide(k, at, _refund(book, refund, sale, int(value), totals[rid], at, site, tz,
                                  k, now) if ok else None)
    if full:
        mine.pop("signature", None)     # more wait: look again on the next run
    else:
        mine["signature"] = sign
    return out


def run(state: dict, config: dict, path, site: str, tz, now: datetime) -> list[dict]:
    """due() over the site's conversions file; [] without one (never made here)."""
    if path is None or not Path(path).is_file():
        track(state, settings(config), now.astimezone(timezone.utc))
        return []
    from .conversions import store
    db = store.connect(path)
    try:
        return due(state, config, db, site, tz, now)
    finally:
        db.close()


# ------------------------------------------------------------------ mail

def mail(alert: dict, site: str, url: str | None) -> tuple[str, str]:
    """(subject, text) of a sale alert's mail."""
    d = alert.get("data") or {}
    what = "Refund" if alert["cause"] == "sale_refunded" else "Sale"
    subject = f"{what} on {site}: {d.get('amount') or alert['title']}"
    text = (f"{alert['title']}\n\n{alert['detail']}\n"
            + (f"\nDashboard: {url}\n" if url else "")
            + "\nLeads & sales > Revenue has the day's totals once they are checked twice. "
              "One mail per sale or refund; switch these off on Site > Alerts.\n")
    return subject, text
