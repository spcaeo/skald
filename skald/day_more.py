"""The registry of later collect-time day figures (phase 4): one module per
`day_extras` kind, like data_more.py is for data files.

`KINDS` maps a kind (also listed in store_extras.KINDS, so history keeps it)
to its module in this package. A module not written yet is skipped, so each
lane adds only its own file. A registered module offers:

    finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None
        The kind's blob for the day (or a view's day, or today so far), from
        the same inputs extras.Extras.finish has; `extras` is that Extras
        (tz, own_hosts). None: not counted - nothing is stored, and the
        figure reads "not recorded", never 0.

    check(totals, blob, differs, problems) -> None
        Every sum DATA-CONTRACT.md promises for the blob. `differs(what,
        got, want, of)` adds a verify.Problem when got != want; a module may
        also append a verify.Problem to `problems` itself. Called only when
        finish returned a blob. Any problem withholds the day.

Each figure also needs its second count in audit_more.py.
"""
from __future__ import annotations

import importlib

KINDS = {"funnels": "funnel_days", "engagement": "engagement",
         "utm_hygiene": "utm_hygiene"}


def modules() -> dict:
    """{kind: module} for the kinds whose module exists."""
    out = {}
    for kind, name in KINDS.items():
        try:
            out[kind] = importlib.import_module(f".{name}", __package__)
        except ModuleNotFoundError as why:
            if why.name != f"{__package__}.{name}":
                raise
    return out


def finish(extras, totals, journeys, page_visits, readers_by_hour, out: dict) -> None:
    """Add each registered kind's blob to `out` (extras.Extras.finish's)."""
    for kind, mod in modules().items():
        blob = mod.finish(extras, totals, journeys, page_visits, readers_by_hour)
        if blob is not None:
            out[kind] = blob


def check(totals, ex: dict, differs, problems: list) -> None:
    """Each registered kind's own sums (extras.check)."""
    for kind, mod in modules().items():
        if ex.get(kind) is not None:
            mod.check(totals, ex[kind], differs, problems)
