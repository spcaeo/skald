"""The daily summary mail's HTML part (summary_mail.py, #68).

Built from the same digest as the plain-text part (summary_mail.digest), so the two
cannot disagree, in the branded layout of the daily and weekly mails (mail_html.py: its
palette, cards, dark mode and mark; tables, inline styles, at most 640 pixels, nothing
fetched, no tracking, no hidden text).

Short on purpose (a long mail is clipped by Gmail and looks like bulk mail to filters):
the brand; the day and the last whole day the figures count; four counts; Act now, one
line per item (a name, "New" or "Still open", one link: no descriptions, no addresses);
an overview, one row per site, every figure a link to its list; why this mail came.
"""
from __future__ import annotations

from html import escape as esc

from . import brand
from .mail_html import (BAD, CARD, DARK, FONT, INK, INK2, INK3, LOGO_CID, PAGE, PEOPLE,
                        RULE, SUNK, WARN, _card)

MARK = {"New": (BAD, "#fdecea"), "Still open": (WARN, "#fdf3dc")}


def _badge(mark: str) -> str:
    if not mark:
        return ""
    ink, bg = MARK.get(mark, (INK2, SUNK))
    return (f'<span style="display:inline-block;font:700 11px/1 {FONT};color:{ink};'
            f'background:{bg};border-radius:4px;padding:3px 6px;margin:0 6px 0 0;'
            f'text-transform:uppercase;letter-spacing:.03em;vertical-align:1px">'
            f'{esc(mark)}</span>')


def _link(url: str | None, words: str) -> str:
    if not url:
        return ""
    return (f'<a href="{esc(url)}" style="font:600 13px/1.4 {FONT};color:{PEOPLE};'
            f'text-decoration:none">{esc(words)}&nbsp;&rsaquo;</a>')


def _row(e: dict, last: bool) -> str:
    line = "" if last else f"border-bottom:1px solid {RULE};"
    many = (f' <span class="s-ink3" style="color:{INK3}">({e["folded"]:,})</span>'
            if e["folded"] else "")
    end = _link(e.get("link"), "Open")
    if not end and e.get("where"):
        end = (f'<span class="s-ink3" style="font:400 12px/1.4 {FONT};color:{INK3}">'
               f'{esc(e["where"])}</span>')
    return (f'<tr><td class="s-ink s-rule" style="font:500 14px/1.45 {FONT};color:{INK};'
            f'padding:8px 8px 8px 0;{line}word-break:break-word">{_badge(e["mark"])}'
            f'<span class="s-ink3" style="color:{INK3}">{esc(e["site"])} &middot;</span> '
            f'{esc(e["head"])}{many}</td>'
            f'<td class="s-rule" align="right" style="padding:8px 0;{line}white-space:nowrap">'
            f'{end}</td></tr>')


def _rows(entries: list[dict]) -> str:
    rows = [_row(e, i == len(entries) - 1) for i, e in enumerate(entries)]
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse">{"".join(rows)}</table>')


def _overview(d: dict) -> str:
    head = "".join(
        f'<td class="s-ink3 s-rule" style="font:600 11px/1.4 {FONT};color:{INK3};'
        f'text-transform:uppercase;letter-spacing:.04em;padding:0 0 6px;border-bottom:1px '
        f'solid {RULE};text-align:{"left" if i == 0 else "right"}">{esc(h)}</td>'
        for i, h in enumerate(("Site", "Act now", "To-dos", "Notes")))
    rows = []
    for i, r in enumerate(d["sites"]):
        line = "" if i == len(d["sites"]) - 1 else f"border-bottom:1px solid {RULE};"
        name = (f'<a class="s-ink" href="{esc(r["url"])}" style="color:{INK};'
                f'text-decoration:none">{esc(r["site"])}</a>' if r["url"] else esc(r["site"]))
        cells = [(r["n_act"], r["links"]["act"]), (r["n_todos"], r["links"]["todos"]),
                 (r["n_notes"], r["links"]["notes"])]
        tds = ""
        for j, (c, url) in enumerate(cells):
            red = bool(c) and j == 0
            ink, cls = (BAD, "") if red else ((INK, "s-ink") if c else (INK3, "s-ink3"))
            figure = f"{c:,}" if c else "&ndash;"
            if c and url:
                figure = (f'<a class="{cls}" href="{esc(url)}" style="color:{ink};'
                          f'text-decoration:underline">{figure}</a>')
            tds += (f'<td class="{cls} s-rule" align="right" style="font:{"700" if red else "500"} '
                    f'14px/1.45 {FONT};color:{ink};padding:7px 0 7px 10px;{line}'
                    f'white-space:nowrap">{figure}</td>')
        rows.append(f'<tr><td class="s-ink s-rule" style="font:500 14px/1.45 {FONT};'
                    f'color:{INK};padding:7px 8px 7px 0;{line}word-break:break-word">{name}</td>'
                    f'{tds}</tr>')
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse"><tr>{head}</tr>{"".join(rows)}</table>')


def _counts(d: dict) -> str:
    # (figure, words, colour, dark-mode class): red stays red in both modes.
    tiles = [(d["act"], "to act on now", BAD if d["act"] else INK3, "" if d["act"] else "s-ink3"),
             (d["todos"], "to-dos", INK if d["todos"] else INK3, "s-ink" if d["todos"] else "s-ink3"),
             (d["notes"], "notes", INK2 if d["notes"] else INK3, "s-ink2" if d["notes"] else "s-ink3"),
             (len(d["sites"]), "sites", INK2, "s-ink2")]
    cells = "".join(
        f'<td class="s-kpi" width="25%" style="padding:0 4px 8px 0;vertical-align:top">'
        f'<div class="s-card" style="background:{CARD};border:1px solid {RULE};border-radius:10px;'
        f'padding:10px 12px"><div class="{k}" style="font:750 22px/1.1 {FONT};color:{c}">'
        f'{n:,}</div><div class="s-ink3" style="font:500 12px/1.4 {FONT};color:{INK3};'
        f'padding-top:2px">{esc(w)}</div></div></td>' for n, w, c, k in tiles)
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;margin:0 0 10px"><tr>{cells}</tr></table>')


def render(d: dict, day: str, logo: bool = True) -> str:
    """The whole HTML part for one person's digest."""
    from .summary_mail import _day, act_now, footer_words
    b = brand.load()
    heading = f"Daily summary · {_day(day)}"
    span = (f"Figures up to {_day(d['upto'])}, the last whole day counted."
            if d["upto"] else "")
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
        f'{esc(heading)}</div><div class="s-ink2" style="font:400 13px/1.5 {FONT};'
        f'color:{INK2};padding:0 0 14px">{esc(span)}</div>')
    sections = [_counts(d)]
    act = act_now(d)
    if act:
        body = _rows(act)
        for r in d["sites"]:
            if r["act_more"]:
                n, url = r["act_more"]
                body += (f'<div style="padding:8px 0 0">'
                         f'{_link(url, f"{n:,} more on " + r["site"])}</div>')
        sections.append(_card(f"Act now ({d['act']:,})", body))
    sections.append(_card("Overview", _overview(d)))
    footer = (f'<div class="s-ink3" style="font:500 12px/1.6 {FONT};color:{INK3};'
              f'text-align:center">{esc(brand.line(b))}</div>'
              f'<div class="s-ink3" style="font:400 12px/1.6 {FONT};color:{INK3};'
              f'text-align:center;padding:6px 12px 0">{esc(footer_words())}</div>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        '<meta name="supported-color-schemes" content="light dark">'
        f'<title>{esc(heading)}</title><style>{DARK}</style></head>'
        f'<body class="s-page" style="margin:0;padding:0;background:{PAGE};'
        f'-webkit-text-size-adjust:100%">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'class="s-page" bgcolor="{PAGE}" style="background:{PAGE}"><tr><td align="center" '
        f'style="padding:24px 10px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="max-width:640px;width:100%"><tr><td class="s-pad" style="padding:0 6px">'
        + header + "".join(sections) + footer +
        '</td></tr></table></td></tr></table></body></html>')
