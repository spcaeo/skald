"""Render the cards, as plain text and as HTML for email.

Both renderers read the same Totals, so they cannot disagree about a number -
there is no second place where a figure is formatted. That is not a style
preference: the report this replaces had its text and HTML parts built
separately for a while, and they drifted.

Three rules about the HTML, all of them about other people's mail clients
rather than taste:

  1. Every colour and size is an inline attribute. Gmail discards most of a
     <style> block, so a stylesheet renders as an unstyled wall of text. The
     one <style> block carries only the dark-mode query, which has nowhere to
     be inlined to, and is an improvement rather than a requirement.
  2. Layout is nested tables with explicit widths. Flex, grid and float each
     have a client that ignores them, and the failure is a collapsed column.
  3. Nothing is fetched from outside the mail: no font, image, stylesheet or
     CDN. Images are blocked by default and arrive as holes, and a mail that
     reaches for a remote file is shaped exactly like one with a tracking
     pixel in it.

Every caveat sits next to the number it qualifies, never in a footnote. A
reader who sees "people" has to be told in the same breath that a user agent
is self-reported, or the number is a small lie.
"""
from __future__ import annotations

import textwrap
from html import escape as esc

from .aggregate import GroupStats, Totals
from .classify import Group, ads_checks
from .countries import label as country_label

WIDTH = 72

TITLES = {
    Group.PEOPLE: "Real people",
    Group.ANSWER_ENGINE: "Answer engines",
    Group.SEARCH_ENGINE: "Search engines",
    Group.BOTS: "Bots and scanners",
    Group.OURS: "Our own traffic",
}

BLURBS = {
    Group.PEOPLE: "A browser that is not any of the categories below, counted only "
                  "when it loaded the page's scripts and styles, so automated readers "
                  "are left out. A user agent is self-reported, so this is still an "
                  "upper bound on humans, not a count of them.",
    Group.ANSWER_ENGINE: "Assistants. Split by why they came, because the three "
                         "reasons mean completely different things.",
    Group.SEARCH_ENGINE: "Classic indexing. Wanted traffic, which is why it is "
                         "not filed under bots.",
    Group.BOTS: "Everything else automated: monitors, SEO suites, link "
                "unfurlers, and scanners probing for credentials.",
    Group.OURS: "Our own crawler and tests. Not traffic; shown so the "
                "categories add up to the log.",
}

# label, what it means, why it matters. The label is written out rather than
# derived from the sentence: deriving it produced rows headed "To" and
# "Because".
TIER_WORDS = {
    "training": ("To train or index", "fetched to train or index",
                 "nobody is waiting on these"),
    "asked": ("Someone just asked", "fetched while answering a live question",
              "a reader is waiting on each one"),
    "cited": ("Followed a citation", "followed a citation to us",
              "the tier that becomes customers"),
}


# ------------------------------------------------------------------ plain text

def _wrap(text: str, indent: str = "    ") -> list[str]:
    return textwrap.wrap(text, WIDTH, initial_indent=indent,
                         subsequent_indent=indent, break_long_words=False,
                         break_on_hyphens=False) or [indent.rstrip()]


def _count(n: int | None) -> str:
    """A figure, or "not recorded" for history from before it was counted."""
    return "not recorded" if n is None else f"{n:,}"


def _share(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f}%" if whole else "0%"


def _top(counter, limit: int = 5, sep: str = ", ") -> str:
    return sep.join(f"{name} {n:,}" for name, n in list(counter.items())[:limit])


def _assistants(counter) -> dict:
    """Assistants by the name a reader knows ('ChatGPT', not chatgpt.com), same order."""
    from .visits import assistant_label
    out: dict = {}
    for name, n in counter.items():
        out[assistant_label(name)] = out.get(assistant_label(name), 0) + n
    return out


def _flagged(counter) -> dict:
    """Country codes as their flag and alpha-3 code ('🇨🇦 CAN'), same order."""
    return {country_label(code): n for code, n in counter.items()}


def unreadable_words(totals: Totals) -> str:
    """The unreadable-line count, said the same way everywhere."""
    if not totals.lines_read:
        return ""
    share = totals.unparsed / totals.lines_read
    head = (f"Unreadable lines: {totals.unparsed:,} of {totals.lines_read:,} "
            f"{totals.lines_scope} ({share:.1%})")
    if totals.max_unparsed_share is None:
        return head + "; each day was checked against the limit when collected."
    return head + f"; above {totals.max_unparsed_share:.0%} the report is withheld."


def _partial_words(totals: Totals) -> str:
    bits = []
    if totals.partial_from:
        bits.append(f"from {totals.partial_from:%d %b %H:%M %Z}".strip())
    if totals.partial_until:
        bits.append(f"until {totals.partial_until:%d %b %H:%M %Z}".strip())
    return ("PARTIAL: the logs cover this window only " + " and ".join(bits)
            + ". These are true figures for that time, not for the whole window.")


def _unfiltered_words(totals: Totals) -> str:
    return (f"{totals.unfiltered:,} of these had no host in the log line (an "
            f"older log format), so the site's host list could not be applied "
            f"to them; they are included above.")


def as_text(totals: Totals, cards: list[Group],
            credit: tuple[str, str | None] | None = None,
            tz_name: str | None = None) -> str:
    """The report as text. This is the copy worth keeping in an archive.

    `credit` is (text, url) for the country data's source, shown wherever
    countries are - a GeoIP database's licence usually requires it.
    `tz_name` names the zone the busiest hours are in (report.timezone).
    """
    from . import report_breakdowns
    out: list[str] = []
    breakdowns_shown = False
    total = totals.hits

    out.append("TRAFFIC")
    out.append(f"  {total:>9,}  requests reached the server")
    for which in cards:
        stats = totals.groups.get(which)
        if not stats or not stats.hits:
            continue
        out.append(f"  {stats.hits:>9,}  {TITLES[which].lower()}"
                   f"  ({_share(stats.hits, total)})")
    out.append(f"  {'':>9}  these add to the line above exactly; if they ever")
    out.append(f"  {'':>9}  do not, the report refuses to send")
    if totals.unfiltered:
        out.extend(_wrap(_unfiltered_words(totals), f"  {'':>9}  "))
    if totals.lines_read:
        out.extend(_wrap(unreadable_words(totals), f"  {'':>9}  "))
    if totals.partial:
        out.extend(_wrap(_partial_words(totals), f"  {'':>9}  "))
    out.append("")

    for which in cards:
        stats = totals.groups.get(which)
        if not stats or not stats.hits:
            continue
        out.append(TITLES[which].upper())
        out.extend(_wrap(BLURBS[which], "  "))
        out.append("")
        out.extend(_card_text(which, stats, total, credit))
        out.append("")
        if which is Group.PEOPLE:
            out.extend(report_breakdowns.as_text(totals, credit, tz_name))
            breakdowns_shown = True
    if not breakdowns_shown:
        out.extend(report_breakdowns.as_text(totals, credit, tz_name))
    return "\n".join(out).rstrip() + "\n"


def _card_text(which: Group, stats: GroupStats, total: int,
               credit: tuple[str, str | None] | None = None) -> list[str]:
    rows: list[str] = []

    def row(label: str, value: str) -> None:
        rows.append(f"    {label:<14} {value}")

    if which is Group.PEOPLE:
        row("Readers", f"{_count(stats.readers)} visits that read at least one page "
                       f"(counted only when the browser loaded the page's scripts and "
                       f"styles, so automated readers are left out)")
        row("Visits", f"{stats.visits:,} browser sessions in all"
                      + (f", {stats.visits - stats.readers:,} without a page view"
                         if stats.readers is not None else ""))
        row("Pages read", f"{stats.views:,} page views "
                          f"(payload fetches and assets excluded)")
        if stats.cited_visits:
            row("From an AI", f"{stats.cited_visits:,} arrived by following a "
                              f"citation ({_top(_assistants(stats.cited_by), 3)})")
        else:
            row("From an AI", "none arrived by following a citation")
        # With the breakdowns, countries of readers are in their own card.
        if stats.countries and not stats.by.get("country"):
            row("Countries", _top(_flagged(stats.countries)) + " (visits)")
            if credit:
                row("", credit[0] + (f" ({credit[1]})" if credit[1] else ""))
        if stats.pages:
            row("Top pages", "")
            for page, n in list(stats.pages.items())[:5]:
                rows.append(f"      {n:>6,}  {page}")
        rows.extend(_wrap("A citation is counted once per visitor, not once per "
                          "request. Referrers are often stripped, so it "
                          "undercounts. Google AI Overview clicks cannot be "
                          "told apart from ordinary Google clicks and are not "
                          "in this number."))

    elif which is Group.ANSWER_ENGINE:
        for tier in ("training", "asked"):
            # Citations are not here: they are a property of the person who
            # followed one, and live on the people card. Counting them in both
            # places is what made the old tiers over-sum.
            n = stats.tiers.get(tier, 0)
            label, words, why = TIER_WORDS[tier]
            row(label, f"{n:,} {words}")
            rows.extend(_wrap(why, "                   "))
        if stats.engines:
            row("By name", "")
            for name, n in list(stats.engines.items())[:8]:
                rows.append(f"      {n:>6,}  {name}")
        if stats.pages:
            row("Fetched", _top(stats.pages, 4, "; "))
        rows.extend(_wrap("Names are self-reported and sometimes forged. "
                          "'Fetched' is not 'read': an image or an API path can "
                          "top that list with nobody having opened a page."))

    elif which is Group.SEARCH_ENGINE:
        ads = ads_checks(stats.engines)
        row("Requests", f"{stats.hits:,}")
        row("Indexing", f"{stats.hits - ads:,} fetches by search crawlers")
        if ads:
            row("Ads checks", f"{ads:,} ads quality checks (AdsBot-Google); "
                              f"not indexing")
        row("Pages", f"{stats.views:,} indexable page fetches")
        if stats.engines:
            row("By name", _top(stats.engines, 6))
        if stats.pages:
            row("Top pages", _top(stats.pages, 3, "; "))

    elif which is Group.BOTS:
        row("Requests", f"{stats.hits:,}")
        row("Scanners", f"{stats.probes:,} probing for paths we do not serve "
                        f"({_share(stats.probes, stats.hits)} of these)")
        if stats.agents:
            row("Others", _top(stats.agents, 6))
        rows.extend(_wrap("Scanner probes are counted here whatever user agent "
                          "they send, including a browser's."))

    else:
        row("Requests", f"{stats.hits:,} from our own crawler and tests")

    return rows


# ------------------------------------------------------------------------ HTML

FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,"
        "sans-serif")
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
INK, MUTE, FAINT = "#15181c", "#5c6672", "#7d8794"
RULE, CARD, PAGE, QUIET = "#e6e9ed", "#ffffff", "#eef0f3", "#f7f8fa"
HUMAN, MACHINE, WANTED, NOISE = "#157f45", "#6b7a8d", "#1a4fc4", "#8a7320"

ACCENT = {
    Group.PEOPLE: HUMAN,
    Group.ANSWER_ENGINE: WANTED,
    Group.SEARCH_ENGINE: MACHINE,
    Group.BOTS: NOISE,
    Group.OURS: FAINT,
}

DARK = """
@media (prefers-color-scheme: dark) {
  .page { background:#111418 !important; }
  .card { background:#1a1e24 !important; }
  .ink  { color:#e8ecf1 !important; }
  .mute { color:#9aa5b1 !important; }
  .hr   { border-color:#2b313a !important; }
  .quiet{ background:#20252c !important; }
}
"""


def _bar(part: int, whole: int, colour: str) -> str:
    """A proportion drawn with two table cells. No image, no SVG.

    It carries nothing on its own: every row states its count and share in
    words beside it, so a client that drops backgrounds loses decoration only.
    """
    pct = max(1, round(part / whole * 100)) if whole else 0
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin-top:5px"><tr>'
        f'<td width="{pct}%" style="height:5px;background:{colour};'
        f'border-radius:3px 0 0 3px;font-size:0;line-height:0">&nbsp;</td>'
        f'<td style="height:5px;background:#e4e8ec;border-radius:0 3px 3px 0;'
        f'font-size:0;line-height:0" class="quiet">&nbsp;</td>'
        f'</tr></table>'
    )


def _row(label: str, value: str, note: str = "") -> str:
    tail = (f'<div class="mute" style="font:400 12px/1.5 {FONT};color:{FAINT};'
            f'padding-top:2px">{esc(note)}</div>' if note else "")
    return (
        f'<tr><td style="padding:7px 0;border-bottom:1px solid {RULE}" class="hr">'
        f'<div class="mute" style="font:400 11px/1.4 {FONT};color:{FAINT};'
        f'text-transform:uppercase;letter-spacing:.04em">{esc(label)}</div>'
        f'<div class="ink" style="font:500 14px/1.5 {FONT};color:{INK};'
        f'padding-top:2px">{value}</div>{tail}</td></tr>'
    )


def _listing(counter, limit: int = 6) -> str:
    if not counter:
        return ""
    items = "".join(
        f'<tr><td style="font:500 13px/1.7 {MONO};color:{INK};padding-right:10px" '
        f'class="ink" align="right">{n:,}</td>'
        f'<td style="font:400 13px/1.7 {MONO};color:{MUTE}" class="mute">'
        f'{esc(str(name))}</td></tr>'
        for name, n in list(counter.items())[:limit]
    )
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;margin-top:3px">{items}</table>')


def credit_html(credit: tuple[str, str | None], colour: str = MUTE) -> str:
    """The country source's attribution: a text link, nothing fetched."""
    text, url = credit
    if not url:
        return esc(text)
    return (f'<a href="{esc(url)}" style="color:{colour};text-decoration:underline">'
            f'{esc(text)}</a>')


def _card(which: Group, stats: GroupStats, total: int,
          credit: tuple[str, str | None] | None = None) -> str:
    colour = ACCENT[which]
    rows: list[str] = []

    if which is Group.PEOPLE:
        rows.append(_row("Readers", _count(stats.readers),
                         "visits that read at least one page - the headline; counted "
                         "only when the browser loaded the page's scripts and styles, so "
                         "automated readers are left out"))
        rows.append(_row("Visits", f"{stats.visits:,}",
                         "distinct sessions, not requests"))
        rows.append(_row("Pages read", f"{stats.views:,}",
                         "payload fetches, assets and beacons excluded"))
        if stats.cited_visits:
            rows.append(_row(
                "Followed a citation",
                f'<span style="color:{HUMAN};font-weight:600">'
                f'{stats.cited_visits:,}</span>',
                f"from {_top(_assistants(stats.cited_by), 3)} - counted once per visitor"))
        else:
            rows.append(_row("Followed a citation", "none yet",
                             "the number that becomes customers"))
        if stats.countries and not stats.by.get("country"):
            value = _top(_flagged(stats.countries), 5) + " (visits, not requests)"
            if credit:
                value += (f'<div class="mute" style="font:400 11px/1.5 {FONT};'
                          f'color:{FAINT};padding-top:2px">{credit_html(credit)}</div>')
            rows.append(_row("Countries", value))
        if stats.pages:
            rows.append(_row("Most read", _listing(stats.pages, 5)))

    elif which is Group.ANSWER_ENGINE:
        for tier in ("training", "asked"):
            n = stats.tiers.get(tier, 0)
            label, _words, why = TIER_WORDS[tier]
            rows.append(_row(label, f"{n:,}", why))
        if stats.engines:
            rows.append(_row("Which assistants", _listing(stats.engines, 8),
                             "self-reported, sometimes forged"))
        if stats.pages:
            rows.append(_row("What they fetched", _listing(stats.pages, 5),
                             "fetched, not read"))
        rows.append(_row("Google AI Overviews", "not measurable",
                         "an AI Overview click arrives with a bare google.com "
                         "referrer, identical to an ordinary search click"))

    elif which is Group.SEARCH_ENGINE:
        ads = ads_checks(stats.engines)
        rows.append(_row("Requests", f"{stats.hits:,}"))
        rows.append(_row("Indexing", f"{stats.hits - ads:,}",
                         "fetches by search crawlers"))
        if ads:
            rows.append(_row("Ads quality checks", f"{ads:,}",
                             "AdsBot-Google checking ad landing pages; not indexing"))
        rows.append(_row("Page fetches", f"{stats.views:,}"))
        if stats.engines:
            rows.append(_row("By name", _listing(stats.engines, 6)))

    elif which is Group.BOTS:
        rows.append(_row("Requests", f"{stats.hits:,}"))
        rows.append(_row("Credential scanners", f"{stats.probes:,}",
                         f"{_share(stats.probes, stats.hits)} of this card - "
                         "counted here whatever agent they send"))
        if stats.agents:
            rows.append(_row("The rest", _listing(stats.agents, 6)))

    else:
        rows.append(_row("Requests", f"{stats.hits:,}",
                         "our own crawler and tests; not traffic"))

    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'class="card" style="border-collapse:collapse;background:{CARD};'
        f'border:1px solid {RULE};border-radius:10px;margin-bottom:14px">'
        f'<tr><td style="padding:16px 18px 6px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse"><tr>'
        f'<td><div class="ink" style="font:600 15px/1.3 {FONT};color:{INK}">'
        f'{esc(TITLES[which])}</div></td>'
        f'<td align="right"><div class="ink" style="font:700 19px/1.2 {FONT};'
        f'color:{colour}">{stats.hits:,}</div>'
        f'<div class="mute" style="font:400 11px/1.3 {FONT};color:{FAINT}">'
        f'{_share(stats.hits, total)} of all requests</div></td>'
        f'</tr></table>'
        f'{_bar(stats.hits, total, colour)}'
        f'<div class="mute" style="font:400 12px/1.55 {FONT};color:{MUTE};'
        f'padding-top:8px">{esc(BLURBS[which])}</div>'
        f'</td></tr>'
        f'<tr><td style="padding:0 18px 12px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse">{"".join(rows)}</table>'
        f'</td></tr></table>'
    )


def as_html(totals: Totals, cards: list[Group], title: str,
            subtitle: str = "", preface: str = "", postscript: str = "",
            credit: tuple[str, str | None] | None = None,
            tz_name: str | None = None) -> str:
    """The same numbers, as a mail body. Text stays the real report.

    `preface` and `postscript` are HTML placed above the cards and below the
    footnote - the weekly comparison and a dashboard link. They are the
    caller's own markup and are not escaped.
    """
    total = totals.hits
    window = ""
    if totals.first and totals.last:
        window = (f"{totals.first:%d %b %H:%M} to {totals.last:%d %b %H:%M} UTC")

    from . import report_breakdowns
    extra = report_breakdowns.as_html(totals, credit, tz_name)
    parts = []
    for which in cards:
        if totals.groups.get(which) and totals.groups[which].hits:
            parts.append(_card(which, totals.groups[which], total, credit))
            if which is Group.PEOPLE:
                parts.append(extra)
                extra = ""
    body = "".join(parts) + extra

    return (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<style>{DARK}</style></head>"
        f'<body class="page" style="margin:0;padding:0;background:{PAGE}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;background:{PAGE}"><tr>'
        f'<td align="center" style="padding:20px 16px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;max-width:600px">'
        f'<tr><td style="padding-bottom:4px">'
        f'<div class="ink" style="font:600 18px/1.3 {FONT};color:{INK}">'
        f'{esc(title)}</div>'
        f'<div class="mute" style="font:400 12px/1.6 {FONT};color:{FAINT};'
        f'padding-top:3px">{esc(subtitle or window)}</div></td></tr>'
        f'<tr><td style="padding:14px 0 4px">'
        f'<div class="ink" style="font:700 26px/1.1 {FONT};color:{INK}">'
        f'{total:,}</div>'
        f'<div class="mute" style="font:400 12px/1.6 {FONT};color:{MUTE}">'
        f'requests reached the server. Every card below is a slice of this '
        f'number, and they add to it exactly.'
        + (f' {esc(_unfiltered_words(totals))}' if totals.unfiltered else '')
        + (f' {esc(unreadable_words(totals))}' if totals.lines_read else '')
        + f'</div></td></tr>'
        f'<tr><td style="padding-top:14px">{preface}{body}</td></tr>'
        f'<tr><td style="padding-top:2px">'
        f'<div class="mute" style="font:400 11px/1.6 {FONT};color:{FAINT}">'
        f'From server access logs, so bots are visible - a JavaScript tracker '
        f'cannot see them. A user agent is self-reported and forgeable.'
        f'</div>{postscript}</td></tr>'
        f'</table></td></tr></table></body></html>\n'
    )
