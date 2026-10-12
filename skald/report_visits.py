"""The visits card for the report and the mail: metrics only.

How many visits, pages per visit, the median visit length, the share that
loaded one page, and the top entry pages, exit pages and steps. Never the
journeys themselves: those stay on the private dashboard and are deleted
after report.journey_days days.

Built from Totals.visits, so it is the same in text and HTML, and absent -
with one line saying why - when a period holds a day collected before
visits were counted.
"""
from __future__ import annotations

import textwrap
from html import escape as esc

from .dimensions import OTHER
from .visits import duration_words

NOT_RECORDED = ("Visit figures not recorded for (some of) these days: they were "
                "collected before visits were counted.")
BLURB = ("A visit is one visitor, no gap over 30 minutes, that loaded at least "
         "one page - the same count as the readers. A page arriving from a new "
         "outside source (an assistant, a search engine, another site, a tagged "
         "link) starts a new visit. Length runs from the first "
         "request to the last, so time spent reading one page is not in it.")


def rows(totals) -> list[tuple[str, str]] | None:
    """(label, value) rows, or None when there is nothing to show."""
    stats = totals.visits
    if stats is None or not stats.visits:
        return None
    one = stats.one_page()
    out = [
        ("Visits", f"{stats.visits:,}"),
        ("Pages per visit", f"{stats.per_visit():.1f} ({stats.views():,} pages loaded)"),
        ("Median length", duration_words(stats.median_seconds())),
        ("One-page visits", f"{one:,} ({one / stats.visits:.0%})"),
    ]
    ret = getattr(totals, "returning", None)
    if ret and ret.get("readers"):
        out.append(("Returning", f"{ret['returning']:,} of {ret['readers']:,} visits "
                    f"({ret['returning'] / ret['readers']:.0%}) by a visitor seen on an "
                    f"earlier day in the last 30"))
    moved = stats.flags.get("in_app", 0)
    if moved:
        out.append(("Moved in-app", f"{moved:,} visits went on to pages the app showed "
                    f"without loading them"))

    def top(counter, limit=3) -> str:
        named = [(k, n) for k, n in counter.most_common(limit + 1) if k != OTHER]
        return ", ".join(f"{k} {n:,}" for k, n in named[:limit])

    for label, counter in (("Top entry pages", stats.entries),
                           ("Top exit pages", stats.exits),
                           ("Top steps", stats.steps)):
        shown = top(counter)
        if shown:
            out.append((label, shown))
    return out


def as_text(totals) -> list[str]:
    if totals.visits is None:
        return ["VISITS", *textwrap.wrap(NOT_RECORDED, 72, initial_indent="  ",
                                         subsequent_indent="  "), ""] if totals.hits else []
    got = rows(totals)
    if not got:
        return []
    out = ["VISITS", *textwrap.wrap(BLURB, 72, initial_indent="  ",
                                    subsequent_indent="  "), ""]
    for label, value in got:
        out += textwrap.wrap(value, 72, initial_indent=f"    {label:<16} ",
                             subsequent_indent=" " * 21, break_long_words=False,
                             break_on_hyphens=False)
    return out + [""]


def as_html(totals) -> str:
    from .report import FAINT, FONT, HUMAN, _row
    from .report_breakdowns import _html_card
    if totals.visits is None:
        return (f'<div class="mute" style="font:400 12px/1.6 {FONT};color:{FAINT};'
                f'padding:0 0 14px">{esc(NOT_RECORDED)}</div>') if totals.hits else ""
    got = rows(totals)
    if not got:
        return ""
    return _html_card("Visits", BLURB, [_row(label, esc(value)) for label, value in got],
                      HUMAN)
