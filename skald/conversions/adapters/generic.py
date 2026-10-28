"""`json`: any tool that can send signed JSON (Zapier, Make, n8n, a script).

Same signature and fields as `lead` (adapters/lead.py). The body is one
lead object, a list of them, or {"records": [...]} (at most 100).
"""
from __future__ import annotations

from . import Invalid, lead

MAX_RECORDS = 100

HEADER = lead.HEADER
SIGNED = lead.SIGNED
verify = lead.verify
sign = lead.sign


def to_records(payload, site_config: dict | None = None, tz=None) -> list[dict]:
    items = payload.get("records") if isinstance(payload, dict) and "records" in payload \
        else payload
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list) or not items:
        raise Invalid("a lead object, a list of them, or {\"records\": [...]}")
    if len(items) > MAX_RECORDS:
        raise Invalid(f"at most {MAX_RECORDS} records in one delivery")
    return [lead.record(item, tz) for item in items]


def sample(site: str, now: float) -> dict:
    one = lead.sample(site, now)
    one["action"] = "trial"
    return {"records": [one]}
