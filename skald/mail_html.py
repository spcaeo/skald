"""The daily and weekly mails as branded HTML (the plain-text part is
report.as_text, unchanged).

Built for mail clients, not browsers: tables for layout, every style inline,
system fonts, at most 640 pixels wide, nothing fetched - the only image is
the Skald mark, sent inside the mail (a CID part, mailer.py), and there is no
tracking of any kind. A `color-scheme` meta and a small dark-mode style keep
it readable when a client darkens it; the cards are off-white, never pure
white, and the mark carries its own dark square.

Layout, top to bottom: the brand, the site and period; a banner when the day
is partial (no change is shown then); five headline figures, each with its
change against the same weekday a week before (daily) or the week before
(weekly) - only when both periods are whole and verified, otherwise "—";
what changed (insights); where visitors came from, top pages, countries, AI
and crawlers, site health - each a table of at most five rows; for the week,
readers per day as a row of bars; the dashboard button and why this mail
came.

Every number is read from the verified history the plain-text part reads,
so the two parts cannot disagree.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from html import escape as esc

from . import brand
from .classify import AI_ASKED, Group
from .countries import label as country_label
from .labels import shown as shown_label, shown_text
from .conversions_leads import LEAD_RULE
from .dimensions import OTHER
from .visits import assistant_label

LOGO_CID = "skald-mark"
ROWS = 5

# The dashboard's palette (webapp/app.css), light and dark.
PAGE, CARD, SUNK, INK, INK2, INK3, RULE = ("#edf0f3", "#fbfcfd", "#e4e9ee", "#17212b",
                                           "#4f5d6b", "#5a6672", "#d8dfe6")
PEOPLE, AI, SEARCH, GOOD, WARN, BAD = ("#2a78d6", "#d95926", "#199e70", "#1b7f52",
                                       "#9a6400", "#c0352f")
# Single quotes only: every style sits inside a double-quoted attribute.
FONT = "system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
DOT = {"working": GOOD, "dropped": BAD, "new": PEOPLE, "gone": INK3, "anomaly": WARN,
       "opportunity": AI}
WORD = {"working": "Up", "dropped": "Down", "new": "New", "gone": "Gone", "anomaly": "Unusual",
        "opportunity": "Idea"}

DARK = """
:root{color-scheme:light dark;supported-color-schemes:light dark}
@media (prefers-color-scheme:dark){
 .s-page{background:#0d1319!important}
 .s-card{background:#141c24!important;border-color:#26313c!important}
 .s-sunk{background:#1b252f!important}
 .s-ink{color:#e4eaf0!important}
 .s-ink2{color:#a9b5c1!important}
 .s-ink3{color:#8593a0!important}
 .s-rule{border-color:#26313c!important}
 .s-btn{background:#e4eaf0!important}
 .s-btn a{color:#0d1319!important}
 .s-bar{background:#3987e5!important}
}
@media only screen and (max-width:480px){
 .s-pad{padding-left:14px!important;padding-right:14px!important}
 .s-kpi{display:inline-block!important;width:50%!important;box-sizing:border-box}
}
"""


def _n(v) -> str:
    return "—" if v is None else f"{int(v):,}"


def _pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f}%" if whole else ""


def change(current: int | None, previous: int | None) -> str:
    """'▲ 12%', '▼ 5%', 'same', 'new', or '—' (not comparable)."""
    if current is None or previous is None:
        return "—"
    if previous == 0:
        return "same" if current == 0 else "new"
    pct = (current - previous) / previous * 100
    if round(pct) == 0:
        return "same"
    return f"{'▲' if pct > 0 else '▼'} {abs(pct):.0f}%"


# ------------------------------------------------------------ the figures

def _leads(config: dict, history, site: str, tz, first: date, last: date) -> int | None:
    """The dashboard's leads for the period (conversions_leads.period_leads, the
    Overview tile's own rule), counted again by audit_client_reports.check_leads;
    None ("—") when the site records none, the period starts before they were
    recorded, or the two counts differ."""
    from . import audit_client_reports
    from .conversions_leads import period_leads, store_of
    try:
        got = period_leads(config, history, site, tz, first, last)
        if not got or got["state"] != "ok":
            return None
        if audit_client_reports.check_leads(store_of(config, history), site, tz, first, last, got):
            return None
    except Exception:                   # noqa: BLE001 - a missing figure, not a failed mail
        return None
    return got["total"]


def _returning(history, site: str, first: date, last: date) -> int | None:
    blobs = history.extras(site, first, last, ("returning",))
    total = 0
    for i in range((last - first).days + 1):
        got = (blobs.get((first + timedelta(days=i)).isoformat()) or {}).get("returning")
        if got is None:
            return None
        total += int(got.get("returning", 0))
    return total


def figures(config, history, site, tz, period, first, last) -> dict:
    people = period.totals.groups.get(Group.PEOPLE)
    return {"visitors": people.readers if people else 0,
            "pages": people.views if people else 0,
            "ai": people.cited_visits if people else 0,
            "leads": _leads(config, history, site, tz, first, last),
            "returning": _returning(history, site, first, last)}


def whole(period) -> bool:
    return bool(period) and period.complete and not period.partial


# ------------------------------------------------------------- building

def _card(title: str, body: str, note: str = "") -> str:
    note_html = (f'<div class="s-ink3" style="font:400 12px/1.5 {FONT};color:{INK3};'
                 f'padding-top:8px">{note}</div>') if note else ""
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'class="s-card" style="border-collapse:separate;background:{CARD};border:1px solid '
            f'{RULE};border-radius:12px;margin:0 0 14px"><tr><td class="s-pad" '
            f'style="padding:16px 20px"><div class="s-ink" style="font:650 15px/1.3 {FONT};'
            f'color:{INK};padding:0 0 10px">{esc(title)}</div>{body}{note_html}</td></tr></table>')


def _table(rows: list[tuple], heads: tuple = ()) -> str:
    """Rows of (label html, figure, share) - label left, numbers right."""
    if not rows:
        return (f'<div class="s-ink3" style="font:400 13px/1.5 {FONT};color:{INK3}">'
                f'Nothing recorded.</div>')
    out = []
    if heads:
        out.append("<tr>" + "".join(
            f'<td class="s-ink3 s-rule" style="font:600 11px/1.4 {FONT};color:{INK3};'
            f'text-transform:uppercase;letter-spacing:.04em;padding:0 0 6px;border-bottom:1px '
            f'solid {RULE};text-align:{"left" if i == 0 else "right"}">{esc(h)}</td>'
            for i, h in enumerate(heads)) + "</tr>")
    for i, (name, value, share) in enumerate(rows):
        line = "" if i == len(rows) - 1 else f"border-bottom:1px solid {RULE};"
        out.append(
            f'<tr><td class="s-ink s-rule" style="font:400 14px/1.45 {FONT};color:{INK};'
            f'padding:7px 8px 7px 0;{line}word-break:break-word">{name}</td>'
            f'<td class="s-ink s-rule" align="right" style="font:600 14px/1.45 {FONT};'
            f'color:{INK};padding:7px 0 7px 8px;{line}white-space:nowrap">{esc(value)}</td>'
            f'<td class="s-ink3 s-rule" align="right" style="font:400 13px/1.45 {FONT};'
            f'color:{INK3};padding:7px 0 7px 10px;{line}white-space:nowrap;width:44px">'
            f'{esc(share)}</td></tr>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse">{"".join(out)}</table>')


# How a visitor is counted (rendering.py), said beside the figure in every mail.
VISITORS_RULE = ("counted only when the browser loaded the page's scripts and styles, so automated readers are left out")


def _kpis(now_f: dict, before: dict | None, compare_words: str) -> str:
    tiles = (("visitors", "Visitors"), ("pages", "Pages read"), ("ai", "Visitors from AI"),
             ("leads", "Leads"), ("returning", "Returning"))
    cells = []
    for key, name in tiles:
        delta = change(now_f[key], (before or {}).get(key)) if before else "—"
        cells.append(
            f'<td class="s-kpi" valign="top" width="20%" style="padding:4px 4px 10px">'
            f'<div class="s-ink3" style="font:600 11px/1.3 {FONT};color:{INK3};'
            f'text-transform:uppercase;letter-spacing:.04em">{esc(name)}</div>'
            f'<div class="s-ink" style="font:700 26px/1.2 {FONT};color:{INK};padding:4px 0 2px">'
            f'{_n(now_f[key])}</div><div class="s-ink2" style="font:500 12px/1.3 {FONT};'
            f'color:{INK2}">{esc(delta)}</div></td>')
    note = (f"Visitors are {VISITORS_RULE}. "
            f"Change against {compare_words}, only when both are whole, verified "
            f"days. Arrows give the direction, not good or bad. {LEAD_RULE}")
    body = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse"><tr>{"".join(cells)}</tr></table>')
    return _card("The headline", body, esc(note))


def _insights(found: list[dict]) -> str:
    if not found:
        return ""
    rows = []
    for i in found:
        colour = DOT.get(i.get("type"), INK3)
        rows.append(
            f'<tr><td valign="top" style="width:18px;padding:8px 0 0">'
            f'<span style="display:inline-block;width:9px;height:9px;border-radius:5px;'
            f'background:{colour};font-size:0;line-height:0">&nbsp;</span></td>'
            f'<td class="s-ink" style="font:400 14px/1.5 {FONT};color:{INK};padding:3px 0">'
            f'<span class="s-ink3" style="font:600 11px/1.5 {FONT};color:{INK3};'
            f'text-transform:uppercase;letter-spacing:.04em">'
            f'{esc(WORD.get(i.get("type"), i.get("type", "")))}</span>&nbsp; '
            f'{esc(shown_text(i.get("title", "")))}</td></tr>')
    body = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse">{"".join(rows)}</table>')
    return _card("What changed", body, "Only whole, verified days are compared.")


def _unmeasured(title: str) -> str:
    """A section whose days were collected before it was counted: said so,
    never shown as zeros."""
    from .report_breakdowns import NOT_RECORDED
    return _card(title, f'<div class="s-ink2" style="font:400 13px/1.5 {FONT};color:{INK2}">'
                        f'{esc(NOT_RECORDED)}</div>')


def _sources(people) -> str:
    by = (people.by or {}).get("source") or {} if people else {}
    total = sum(by.values())
    cited = Counter(people.cited_by) if people else Counter()
    rows = []
    for name, n in Counter(by).most_common(ROWS):
        shown = esc(shown_label(name))
        if name == "AI assistant" and cited:
            shown += (f'<div class="s-ink3" style="font:400 12px/1.4 {FONT};color:{INK3}">'
                      + esc(", ".join(f"{assistant_label(a)} {c}" for a, c in cited.most_common(4)))
                      + "</div>")
        rows.append((shown, f"{n:,}", _pct(n, total)))
    return _card("Where visitors came from", _table(rows, ("Source", "Visitors", "")),
                 "Each visitor counted once, by the first page they read." if rows else "")


def _pages(people) -> str:
    pages = Counter(people.pages) if people else Counter()
    total = people.views if people else 0
    rows = [(f'<span style="font-family:{MONO};'
             f'font-size:13px">{esc(p)}</span>', f"{n:,}", _pct(n, total))
            for p, n in pages.most_common(ROWS + 1) if p != OTHER][:ROWS]
    return _card("Top pages", _table(rows, ("Page", "Reads", "")))


def _countries(people, credit=None) -> str:
    by = (people.by or {}).get("country") or {} if people else {}
    total = sum(by.values())
    rows = [(esc(country_label(c)), f"{n:,}", _pct(n, total))
            for c, n in Counter(by).most_common(ROWS)]
    note = ""
    if credit:                          # the country database's licence asks for it here
        text, link = credit
        note = (f'<a href="{esc(link)}" style="color:{INK3}">{esc(text)}</a>' if link
                else esc(text))
    return _card("Countries", _table(rows, ("Country", "Visitors", "")), note)


def _crawlers(totals) -> str:
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    search = totals.groups.get(Group.SEARCH_ENGINE)
    asked = int(engines.tiers.get("asked", 0)) if engines else 0
    training = int(engines.tiers.get("training", 0)) if engines else 0
    indexing = search.hits if search else 0
    names = Counter()
    if engines:
        names.update(engines.engines)
    kinds = {n: ("asked" if AI_ASKED.fullmatch(n) else "training") for n in names}
    if search:
        for n, c in search.engines.items():
            names[n] += c
            kinds.setdefault(n, "search")
    words = {"asked": "someone asked it", "training": "to train or index",
             "search": "search crawler"}
    rows = [(f'{esc(n)}<div class="s-ink3" style="font:400 12px/1.4 {FONT};color:{INK3}">'
             f'{words[kinds[n]]}</div>', f"{c:,}", "")
            for n, c in names.most_common(ROWS)]
    summary = (f'<div class="s-ink2" style="font:400 13px/1.5 {FONT};color:{INK2};'
               f'padding:0 0 8px">{asked:,} fetches because someone asked an AI · '
               f'{training:,} to train or index · {indexing:,} by search engines</div>')
    return _card("AI and crawlers", summary + _table(rows, ("Who", "Requests", "")),
                 "Requests, not people: one question can fetch several pages.")


def _health(history, site: str, tz, first: date, last: date, totals, config=None) -> str:
    from .config import ours_rules, setting
    from .data_files import _heartbeat
    from .window import day_window
    label = str(setting(config or {}, "report", "heartbeat_label", "heartbeat"))
    beating = any(r["label"] == label for r in ours_rules(config or {}))
    blobs = history.extras(site, first, last, ("ours",))
    ok = expected = 0
    known = True
    for i in range((last - first).days + 1):
        d = first + timedelta(days=i)
        beat = ((blobs.get(d.isoformat()) or {}).get("ours") or {}).get("heartbeat")
        start, end = day_window(d, tz)
        got = _heartbeat(beat, start, end, tz)
        if got is None or not got["expected"]:
            known = False
            continue
        ok += got["ok"]
        expected += got["expected"]
    uptime = (f"{min(100.0, ok / expected * 100):.2f}%" if beating and known and expected
              else "—")
    people = totals.groups.get(Group.PEOPLE)
    measured = bool(totals.breakdowns)
    errors = (f"{sum(int(s.statuses.get('5xx', 0)) for s in totals.groups.values()):,}"
              if measured else "—")
    broken = Counter(people.not_found) if people and measured else Counter()
    rows = [("Uptime (our 5-minute check)", uptime, ""),
            ("Server errors (5xx), all visitors", errors, ""),
            ("Broken links people hit (404)",
             f"{sum(broken.values()):,}" if measured else "—", "")]
    rows += [(f'<span class="s-ink2" style="color:{INK2};font-family:ui-monospace,'
              f'SFMono-Regular,Menlo,Consolas,monospace;font-size:13px">&nbsp;&nbsp;'
              f'{esc(p)}</span>', f"{n:,}", "") for p, n in broken.most_common(3)
             if p != OTHER][:2]
    return _card("Site health", _table(rows[:ROWS]))


def _week_bars(history, site: str, first: date, last: date) -> str:
    days = history.daily(site, first, last)
    values = [(e["day"], (e["groups"][Group.PEOPLE]["readers"]
                          if e["state"] in ("ok", "partial") else None)) for e in days]
    top = max([v for _, v in values if v] or [1])
    cols = []
    for d, v in values:
        h = max(2, round((v or 0) / top * 90)) if v is not None else 2
        colour = PEOPLE if v is not None else RULE
        cols.append(
            f'<td valign="bottom" align="center" style="padding:0 3px;width:14%">'
            f'<div class="s-ink" style="font:600 12px/1.3 {FONT};color:{INK};padding:0 0 4px">'
            f'{_n(v)}</div><table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0"><tr><td class="s-bar" height="{h}" bgcolor="{colour}" '
            f'style="height:{h}px;background:{colour};border-radius:4px 4px 0 0;font-size:0;'
            f'line-height:0">&nbsp;</td></tr></table>'
            f'<div class="s-ink3" style="font:500 11px/1.3 {FONT};color:{INK3};padding:6px 0 0">'
            f'{d:%a}<br>{d.day}</div></td>')
    body = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse"><tr>{"".join(cols)}</tr></table>')
    return _card("Visitors per day", body)


def _button(url: str | None) -> str:
    if not url:
        return ""
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" align="center" '
            f'style="margin:6px auto 18px"><tr><td class="s-btn" bgcolor="{INK}" '
            f'style="background:{INK};border-radius:8px"><a href="{esc(url)}" '
            f'style="display:inline-block;padding:12px 22px;font:650 15px/1 {FONT};'
            f'color:{CARD};text-decoration:none;border-radius:8px">Open the dashboard</a>'
            f'</td></tr></table>')


def render(kind: str, config: dict, history, tz, site: str, first: date, last: date,
           period, before, insights: list[dict], partial: str, url: str | None,
           recipients: list[str], credit=None, logo: bool = True, extra: str = "") -> str:
    """The whole HTML part. `before` is the period compared with, or None;
    `extra` a ready card after the insights (the weekly AI reading changes)."""
    b = brand.load()
    totals = period.totals
    people = totals.groups.get(Group.PEOPLE)
    zone = getattr(tz, "key", str(tz))
    place = zone.split("/")[-1].replace("_", " ")
    if kind == "daily":
        heading = f"{site} · Daily report · {last:%a} {last.day} {last:%b %Y}"
        span = f"Midnight to midnight, {place} time ({zone})"
        compare_words = f"the same weekday a week before ({last - timedelta(days=7):%a %d %b})"
    else:
        heading = (f"{site} · Weekly report · {first:%a} {first.day} {first:%b} – "
                   f"{last:%a} {last.day} {last:%b %Y}")
        span = f"7 days, midnight to midnight, {place} time ({zone})"
        compare_words = "the 7 days before"
    now_f = figures(config, history, site, tz, period, first, last)
    before_f = None
    if before is not None and whole(period) and whole(before):
        bf, bl = before.first, before.last
        before_f = figures(config, history, site, tz, before, bf, bl)
    pre = (f"{_n(now_f['visitors'])} visitors, {_n(now_f['pages'])} pages read, "
           f"{_n(now_f['ai'])} from AI" + (f" - {partial}" if partial else ""))
    banner = ""
    if partial:
        banner = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                  f'style="border-collapse:separate;margin:0 0 14px"><tr><td '
                  f'style="background:#fdf3dc;border:1px solid #e8c77a;border-radius:10px;'
                  f'padding:12px 16px;font:500 14px/1.5 {FONT};color:#5c3d00">'
                  f'<strong>Partial day:</strong> {esc(partial.removeprefix("partial day, "))}. '
                  f'The figures are true for the hours the logs cover, and are not compared '
                  f'with any other day.</td></tr></table>')
    header = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border-collapse:collapse;margin:0 0 16px"><tr>'
        + (f'<td width="48" valign="middle" style="width:48px;padding:0 12px 0 0">'
           f'<img src="cid:{LOGO_CID}" width="40" height="40" alt="{esc(b["name"])}" '
           f'style="display:block;width:40px;height:40px;border:0;border-radius:9px"></td>'
           if logo else "") +
        f'<td valign="middle"><div class="s-ink" style="font:750 20px/1.2 {FONT};color:{INK};'
        f'letter-spacing:-.01em">{esc(b["name"])}</div>'
        f'<div class="s-ink3" style="font:400 13px/1.4 {FONT};color:{INK3}">'
        f'{esc(b["tagline"])}</div></td></tr></table>'
        f'<div class="s-ink" style="font:700 18px/1.35 {FONT};color:{INK};padding:0 0 2px">'
        f'{esc(heading).replace(".", ".&#8288;", 1) if "." in site else esc(heading)}</div><div class="s-ink2" style="font:400 13px/1.5 {FONT};'
        f'color:{INK2};padding:0 0 16px">{esc(span)}</div>')
    sections = [
        banner, _kpis(now_f, before_f, compare_words),
        _week_bars(history, site, first, last) if kind == "weekly" else "",
        _insights(insights), extra,
        _sources(people) if totals.breakdowns else _unmeasured("Where visitors came from"),
        _pages(people),
        _countries(people, credit) if totals.breakdowns else _unmeasured("Countries"),
        _crawlers(totals), _health(history, site, tz, first, last, totals, config)]
    who = ", ".join(recipients)
    footer = (
        _button(url)
        + f'<div class="s-ink3" style="font:500 12px/1.6 {FONT};color:{INK3};text-align:center">'
        f'{esc(brand.line(b))}</div>'
        f'<div class="s-ink3" style="font:400 12px/1.6 {FONT};color:{INK3};text-align:center;'
        f'padding:6px 12px 0">You get this because {esc(who)} is on the report list for '
        f'{esc(site)} (mail.to in the server\'s Skald settings): a daily report each morning '
        f'and a weekly one on Mondays. Read from the web server\'s own logs; nothing in this '
        f'mail tracks you.</div>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f'<title>{esc(heading)}</title><style>{DARK}</style></head>'
        f'<body class="s-page" style="margin:0;padding:0;background:{PAGE};'
        f'-webkit-text-size-adjust:100%">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{PAGE}">'
        f'{esc(pre)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'class="s-page" bgcolor="{PAGE}" style="background:{PAGE}"><tr><td align="center" '
        f'style="padding:24px 10px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="max-width:640px;width:100%"><tr><td class="s-pad" style="padding:0 6px">'
        + header + "".join(sections) + footer +
        '</td></tr></table></td></tr></table></body></html>')
