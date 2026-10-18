"""Two more cards for the report and the mail: who the readers were, and
how the site answered.

Kept apart from report.py so neither file grows past what one person can
read, but built the same way: one function per card for text and one for
HTML, both from the same Totals, so the two parts of a mail cannot differ.

"Who the readers were" breaks the readers down - visits that read a page,
each counted once at the first page they read - by country, browser,
system, device, source, referrer, campaign, landing page and hour. Every
list adds up to the readers (verify checks it), so a share is a share of
them. "Site health" covers every group: 404s people were served, server
errors, slow page views and form posts.

When a period includes a day collected before the breakdowns existed, the
cards are replaced by one line saying so: a breakdown of some of the days
beside readers for all of them would not add up.
"""
from __future__ import annotations

import textwrap
from html import escape as esc

from .aggregate import Totals
from .classify import Group
from .countries import label as country_label
from .labels import shown as shown_label
from .dimensions import DEVICES, NO_CAMPAIGN, SLOW

NOT_RECORDED = ("Breakdowns not recorded for (some of) these days: they were "
                "collected before countries, browsers, sources and site health "
                "were counted.")

CAVEAT = ("Browser, system and device come from the user agent, which is "
          "self-reported: Brave counts as Chrome, and an iPad asking for the "
          "desktop site counts as a Mac. Referrers are often stripped, so "
          "Direct includes every visitor whose referrer was withheld.")

READERS_BLURB = ("Readers, each counted once, at the first page they read. "
                 "Every list adds up to the readers.")
HEALTH_BLURB = "How the site answered: errors, slow pages and form posts."

# Folded tails and placeholders that are not a site anyone came from.
_NOT_A_SITE = ("(none)", "(this site)")


def zone_words(tz_name: str | None) -> str:
    """'New York time' for America/New_York; 'local time' when unknown."""
    if not tz_name:
        return "local time"
    if tz_name.upper() in ("UTC", "ETC/UTC", "GMT"):
        return "UTC"
    return tz_name.rsplit("/", 1)[-1].replace("_", " ") + " time"


def _pct(n: int, whole: int) -> str:
    return f"{n / whole * 100:.0f}%" if whole else "0%"


def _shares(counter, whole: int, limit: int | None = 5, name=shown_label) -> list[str]:
    items = counter.most_common(limit) if limit else counter.most_common()
    return [f"{name(k)} {n:,} ({_pct(n, whole)})" for k, n in items if n]


def _hours(counter, tz_name: str | None, limit: int = 3) -> str:
    busiest = [(h, n) for h, n in counter.most_common(limit) if n]
    spans = ", ".join(f"{h}:00-{(int(h) + 1) % 24:02d}:00 {n:,}" for h, n in busiest)
    return f"{spans} ({zone_words(tz_name)})" if spans else ""


def reader_rows(totals: Totals, credit=None, tz_name: str | None = None
                ) -> list[tuple[str, list[str] | str, str]] | None:
    """(label, value, note) rows for the readers card, or None when there is
    nothing to show. A list value is a ranked listing, a string is one line."""
    people = totals.groups.get(Group.PEOPLE)
    if not totals.breakdowns or not people or not people.readers:
        return None
    whole = people.readers
    by = people.by
    rows: list[tuple] = []

    def get(name):
        from collections import Counter
        return by.get(name) or Counter()

    credit_note = ""
    if credit:
        credit_note = credit[0] + (f" ({credit[1]})" if credit[1] else "")
    countries = get("country")
    shown = _shares(countries, whole, 5, country_label)
    unknown = countries.get("Unknown", 0)
    if unknown and "Unknown" not in [k for k, _ in countries.most_common(5)]:
        shown.append(f"{country_label('Unknown')} {unknown:,} ({_pct(unknown, whole)})")
    rows.append(("Countries", ", ".join(shown), credit_note))
    rows.append(("Browsers", ", ".join(_shares(get("browser"), whole)), ""))
    rows.append(("Systems", ", ".join(_shares(get("os"), whole)), ""))
    devices = get("device")
    rows.append(("Devices", ", ".join(
        f"{d} {devices.get(d, 0):,} ({_pct(devices.get(d, 0), whole)})"
        for d in DEVICES), ""))
    rows.append(("Sources", ", ".join(_shares(get("source"), whole, None)), ""))
    sites = get("referrer").copy()
    for gone in _NOT_A_SITE:
        sites.pop(gone, None)
    if sites:
        rows.append(("Referrers", ", ".join(f"{k} {n:,}" for k, n in sites.most_common(5)), ""))
    campaigns = get("campaign").copy()
    campaigns.pop(NO_CAMPAIGN, None)
    if campaigns:
        rows.append(("Campaigns", ", ".join(f"{k} {n:,}" for k, n in campaigns.most_common(5)),
                     "from utm_ tags or an ad click id on the landing URL"))
    landing = get("landing")
    if landing:
        rows.append(("Landing pages", [(k, n) for k, n in landing.most_common(5)], ""))
    hours = _hours(get("hour"), tz_name)
    if hours:
        rows.append(("Busiest hours", hours, "readers by the hour of their first page"))
    return rows


def health_rows(totals: Totals) -> list[tuple[str, str, str]] | None:
    """(label, value, note) rows for the site health card, or None."""
    if not totals.breakdowns or not totals.groups:
        return None
    people = totals.groups.get(Group.PEOPLE)
    rows = []

    def top(counter, limit=3) -> str:
        return ", ".join(f"{k} {n:,}" for k, n in counter.most_common(limit) if n)

    missing = people.statuses.get("404", 0) if people else 0
    rows.append(("Not found", f"{missing:,} page-not-found (404) responses to people"
                 + (f": {top(people.not_found)}" if missing else ""), ""))

    errors = {g: s.statuses.get("5xx", 0) for g, s in totals.groups.items()}
    total_errors = sum(errors.values())
    if total_errors:
        split = ", ".join(f"{g.value} {n:,}" for g, n in errors.items() if n)
        rows.append(("Server errors", f"{total_errors:,} 5xx responses ({split}): "
                     f"{top(totals.server_errors)}", "should be zero"))
    else:
        rows.append(("Server errors", "0 5xx responses", "to anyone"))

    if people and people.views:
        speeds = people.speeds
        if speeds and speeds.get("not logged", 0) == sum(speeds.values()):
            rows.append(("Slow pages", "response time is not in the log", ""))
        else:
            slow = sum(speeds.get(s, 0) for s in SLOW)
            rows.append(("Slow pages", f"{slow:,} of {people.views:,} people's page "
                         f"views took 1 s or more"
                         + (f": {top(people.slow_pages)}" if slow else ""),
                         "server time to answer, not time to load in the browser"))

    posts_people = people.posts if people else 0
    posts_all = sum(s.posts for s in totals.groups.values())
    rows.append(("Form posts", f"{posts_people:,} POST requests by people"
                 + (f" ({top(people.post_pages)})" if posts_people else "")
                 + f"; {posts_all:,} by everyone", "counted only; no content is read"))
    return rows


# ------------------------------------------------------------------ text

def _text_row(label: str, value: str) -> list[str]:
    return textwrap.wrap(value, 72, initial_indent=f"    {label:<14} ",
                         subsequent_indent=" " * 19, break_long_words=False,
                         break_on_hyphens=False) or [f"    {label}"]


def _text_rows(rows) -> list[str]:
    out = []
    for label, value, note in rows:
        if isinstance(value, list):
            out.append(f"    {label}")
            out.extend(f"      {n:>6,}  {k}" for k, n in value)
        else:
            out.extend(_text_row(label, value))
        if note:
            out.extend(_text_row("", note))
    return out


def _blurb(text: str) -> list[str]:
    return textwrap.wrap(text, 72, initial_indent="  ", subsequent_indent="  ")


def as_text(totals: Totals, credit=None, tz_name: str | None = None) -> list[str]:
    """The two cards as text lines, or the one not-recorded line."""
    if not totals.hits:
        return []
    if not totals.breakdowns:
        return ["BREAKDOWNS", *_blurb(NOT_RECORDED), ""]
    from . import report_visits
    out: list[str] = report_visits.as_text(totals)
    readers = reader_rows(totals, credit, tz_name)
    if readers:
        out += ["WHO THE READERS WERE", *_blurb(READERS_BLURB), ""]
        out += _text_rows(readers)
        out += [*textwrap.wrap(CAVEAT, 72, initial_indent="    ",
                               subsequent_indent="    ", break_on_hyphens=False), ""]
    health = health_rows(totals)
    if health:
        out += ["SITE HEALTH", *_blurb(HEALTH_BLURB), ""]
        out += _text_rows(health)
        out.append("")
    return out


# ------------------------------------------------------------------ HTML

def _html_card(title: str, blurb: str, rows: list[str], colour: str) -> str:
    from .report import CARD, FONT, MUTE, RULE, INK
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'class="card" style="border-collapse:collapse;background:{CARD};'
        f'border:1px solid {RULE};border-radius:10px;margin-bottom:14px">'
        f'<tr><td style="padding:16px 18px 6px;border-top:3px solid {colour}">'
        f'<div class="ink" style="font:600 15px/1.3 {FONT};color:{INK}">{esc(title)}</div>'
        f'<div class="mute" style="font:400 12px/1.55 {FONT};color:{MUTE};'
        f'padding-top:6px">{esc(blurb)}</div></td></tr>'
        f'<tr><td style="padding:0 18px 12px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse">{"".join(rows)}</table>'
        f'</td></tr></table>'
    )


def _html_rows(rows, credit=None) -> list[str]:
    from collections import Counter
    from .report import FAINT, FONT, _listing, _row, credit_html
    out = []
    for label, value, note in rows:
        if isinstance(value, list):
            shown = _listing(Counter(dict(value)), len(value))
        else:
            shown = esc(value)
        if label == "Countries" and credit:
            shown += (f'<div class="mute" style="font:400 11px/1.5 {FONT};'
                      f'color:{FAINT};padding-top:2px">{credit_html(credit)}</div>')
            note = ""
        out.append(_row(label, shown, note))
    return out


def as_html(totals: Totals, credit=None, tz_name: str | None = None) -> str:
    """The two cards as mail-safe HTML, or the one not-recorded line."""
    from .report import FAINT, FONT, HUMAN, NOISE
    if not totals.hits:
        return ""
    if not totals.breakdowns:
        return (f'<div class="mute" style="font:400 12px/1.6 {FONT};color:{FAINT};'
                f'padding:0 0 14px">{esc(NOT_RECORDED)}</div>')
    from . import report_visits
    html = report_visits.as_html(totals)
    readers = reader_rows(totals, credit, tz_name)
    if readers:
        rows = _html_rows(readers, credit)
        rows.append(f'<tr><td style="padding:8px 0 0;font:400 11px/1.5 {FONT};'
                    f'color:{FAINT}" class="mute">{esc(CAVEAT)}</td></tr>')
        html += _html_card("Who the readers were", READERS_BLURB, rows, HUMAN)
    health = health_rows(totals)
    if health:
        html += _html_card("Site health", HEALTH_BLURB, _html_rows(health), NOISE)
    return html
