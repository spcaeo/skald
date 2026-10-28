"""GET /traffic-hooks/<site>/leads: the leads Skald holds from the site's own
`lead` hook, for the site's server to check that every lead it sent arrived
and to send the missing ones again (the hook keeps one row per (external
ref, stage): a resend of a lead already kept changes nothing).

Read only. Signed with the `lead` hook's own secret over the method and the
request target, the path and the query exactly as sent (no "?" without a
query), so no parameter can be changed on the way:

    X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.GET <target>")>

the same 5-minute window and constant-time compare as the POST
(adapters/lead.py verify_get). hooks.Receiver.leads answers it: 404 for a
site that is not set up or has no lead secret (the same answer), 401 for a
missing or wrong signature, 429 past `hooks.leads_per_minute` (60) a minute
per site, 400 for a parameter this module refuses.

Parameters (each at most once; any other name is refused):

    since      received at or after this time (ISO with an offset, or Unix
               seconds; without an offset, UTC): when Skald got the lead,
               not its `at`, so a lead sent late about an old day is found
    at_since, at_until   `at` in [at_since, at_until)
    cursor     the answer's next_cursor: the next page
    limit      1-500 rows a page, 200 when left out

Answer: {"ok", "site", "since", "at_since", "at_until", "limit", "rows",
"next_cursor"}, rows {external_ref, action, stage, at, label, test,
received_at, value, value_minor, currency, customer_ref, tags,
country_recorded} ordered by received_at, then the row's id. Since 2.32:
`value` is the amount kept in the currency's major units as exact text
("49.99"), `value_minor` the same in whole minor units, `tags` an object;
each null when none was kept (a `refunded` row's value is the total refunded
so far). After 2.43.0: `country_recorded`, true when Skald kept a country for
the row (the lead's `country`, or one looked up from its `ip`), so a site
can check that its lead call passes the visitor's address; never the country
itself. Rows marked test are in it (test: true). Never an email, a name, an
address, a country, a user agent, a visitor ID or a source. The cursor is the last row's (received_at, id),
opaque: a new lead arrives after it, so paging never skips or repeats one.
"""
from __future__ import annotations

import base64
import json
import re
from urllib.parse import parse_qsl

from . import money, store
from .adapters import when

PATH = re.compile(r"^/traffic-hooks/([A-Za-z0-9][A-Za-z0-9._-]{0,99})/leads$")
TOOL = "lead"
LIMIT, MAX_LIMIT = 200, 500
PARAMS = ("since", "at_since", "at_until", "cursor", "limit")
STORED_KEYS = ("external_ref", "action", "stage", "at", "label", "test", "received_at")
# 2.32: the money kept (`value` is value_minor as exact major-unit text).
ROW_KEYS = STORED_KEYS + ("value", "value_minor", "currency", "customer_ref", "tags",
                          "country_recorded")
_STAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


class BadQuery(ValueError):
    """A parameter the endpoint refuses (400)."""


def site_of(path: str) -> str | None:
    found = PATH.match(path.split("?", 1)[0])
    return found.group(1) if found else None


def cursor_for(received_at: str, row_id: int) -> str:
    raw = f"{received_at}|{int(row_id)}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def read_cursor(text: str) -> tuple[str, int]:
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode()
        at, _, row_id = raw.partition("|")
        if not _STAMP.match(at) or not row_id.isdigit():
            raise ValueError
        return at, int(row_id)
    except (ValueError, UnicodeDecodeError):
        raise BadQuery("cursor is not one this endpoint gave") from None


def read_query(target: str) -> dict:
    """The request target's parameters, checked. Raises BadQuery."""
    query = target.split("?", 1)[1] if "?" in target else ""
    got: dict = {}
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=bool(query))
    except ValueError:
        raise BadQuery("the query cannot be read") from None
    for name, value in pairs:
        if name not in PARAMS:
            raise BadQuery(f"unknown parameter {name[:40]!r}; known: {', '.join(PARAMS)}")
        if name in got:
            raise BadQuery(f"{name} is given twice")
        got[name] = value
    out = {"since": None, "at_since": None, "at_until": None, "after": None, "limit": LIMIT}
    for name in ("since", "at_since", "at_until"):
        if got.get(name):
            out[name] = when(got[name])
            if out[name] is None:
                raise BadQuery(f"{name} is not a time (ISO 8601 or Unix seconds)")
    if got.get("cursor"):
        out["after"] = read_cursor(got["cursor"])
    if "limit" in got:
        text = got["limit"].strip()
        if not text.isdigit() or not 1 <= int(text) <= MAX_LIMIT:
            raise BadQuery(f"limit is a whole number from 1 to {MAX_LIMIT}")
        out["limit"] = int(text)
    out["params"] = sorted(got)
    return out


def answer(db_path, site: str, query: dict) -> dict:
    """The page of rows for one checked query."""
    rows: list[dict] = []
    if db_path is not None and db_path.exists():
        db = store.connect(db_path)
        try:
            rows = store.hook_rows(db, site, TOOL, query["since"], query["after"],
                                   query["at_since"], query["at_until"], query["limit"] + 1)
        finally:
            db.close()
    more = len(rows) > query["limit"]
    rows = rows[:query["limit"]]
    last = rows[-1] if rows else None
    return {"ok": True, "site": site, "since": query["since"], "at_since": query["at_since"],
            "at_until": query["at_until"], "limit": query["limit"],
            "rows": [_row(r) for r in rows],
            "next_cursor": cursor_for(last["received_at"], last["id"]) if more else None}


def _row(r: dict) -> dict:
    return {**{k: r[k] for k in STORED_KEYS}, "test": bool(r["test"]),
            "value": money.shown(r["value_minor"], r["currency"]),
            "value_minor": r["value_minor"], "currency": r["currency"],
            "customer_ref": r["customer_ref"], "tags": json.loads(r["tags"]) if r["tags"] else None,
            "country_recorded": r["country"] is not None}
