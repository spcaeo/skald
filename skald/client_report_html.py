"""A client report (client_report_data.py) as mail: HTML for mail clients and
the plain-text part beside it.

The same build rules as the daily mail (mail_html.py, whose palette and
cards it reuses): tables for layout, inline styles, at most 640 pixels,
nothing fetched, no tracking. The images - the site's logo and the
agency's - travel inside the mail as CID parts (`cid:site-logo`,
`cid:agency-logo`); the preview writes them in as data: addresses. A logo
that cannot travel (SVG, a bitmap icon) gives way to the site's letter.

Branding comes from the organisation (Settings > Mail & reports > Client reports > Agency
branding): its name in the header and the From name, its colour as the top
band (text on it is white or ink, whichever reads), its logo top right.
"""
from __future__ import annotations

from datetime import date
from html import escape as esc

from .client_report_data import (LEAD_RULE, SC_NOTE, coverage_lines, leads_missing, num, pct,
                                 period_words, search_console_lines)
from .mail_html import (CARD, DARK, FONT, INK, INK2, INK3, MONO, PAGE, PEOPLE, RULE, _card,
                        _table)

SITE_CID, AGENCY_CID = "site-logo", "agency-logo"
GAP = "#c9d2db"                         # a day not in the figures: a pale stub, never zero


def luminance(color: str) -> float:
    c = color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def on(color: str) -> str:
    """White or ink, whichever has more contrast on `color`."""
    lum = luminance(color)
    white = 1.05 / (lum + 0.05)
    ink = (lum + 0.05) / (luminance(INK) + 0.05)
    return "#ffffff" if white >= ink else INK


def _p(text: str, colour: str = INK2, size: int = 13) -> str:
    return (f'<div class="s-ink2" style="font:400 {size}px/1.55 {FONT};color:{colour};'
            f'padding:0 0 4px">{esc(text)}</div>')


def _rows(rows, mono: bool = False) -> list[tuple]:
    out = []
    for r in rows or []:
        name = esc(r["name"])
        if r.get("flag"):               # a place: its flag, the full name on hover
            name = f'<span title="{esc(r.get("title") or "")}">{esc(r["flag"])} {name}</span>'
        if mono:
            name = f'<span style="font-family:{MONO};font-size:13px">{name}</span>'
        out.append((name, f"{r['n']:,}", pct(r.get("share"))))
    return out


def _kpis(data: dict) -> str:
    head, changes = data["headline"], data["changes"]
    tiles = (("visitors", "Visitors"), ("pages", "Pages read"), ("ai", "From AI"),
             ("leads", "Leads"), ("returning", "Returning"))
    cells = []
    for key, label in tiles:
        delta = changes.get(key) or ""
        cells.append(
            f'<td class="s-kpi" valign="top" width="20%" style="padding:4px 4px 10px">'
            f'<div class="s-ink3" style="font:600 11px/1.3 {FONT};color:{INK3};'
            f'text-transform:uppercase;letter-spacing:.04em">{esc(label)}</div>'
            f'<div class="s-ink" style="font:700 24px/1.2 {FONT};color:{INK};padding:4px 0 2px">'
            f'{num(head[key])}</div><div class="s-ink2" style="font:500 12px/1.3 {FONT};'
            f'color:{INK2}">{esc(delta)}</div></td>')
    note = ("Change against the period before, the same length, only when both are whole "
            "and verified." if data["compared"] else
            "No change is given: the period before is not wholly recorded.")
    body = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse"><tr>{"".join(cells)}</tr></table>'
            + "".join(_p(line) for line in coverage_lines(data)))
    return _card("Summary", body, esc(note + " Visitors are people whose browser drew the "
                                      "page; automated readers are left out. From AI: visitors who "
                                      "came from an AI assistant's answer."))


def _bars(data: dict) -> str:
    days = data["daily"]
    top = max([d["visitors"] for d in days if d["visitors"]] or [1])
    peak = max(days, key=lambda d: d["visitors"] or -1)
    width = max(2, int(100 / max(1, len(days))))
    cols = []
    for d in days:
        v = d["visitors"]
        h = max(2, round(v / top * 90)) if v else (2 if v == 0 else 6)
        colour = PEOPLE if v is not None else GAP
        label = f"{v:,}" if d is peak and v else "&nbsp;"
        day = date.fromisoformat(d["day"])
        cols.append(
            f'<td valign="bottom" align="center" width="{width}%" style="padding:0 1px">'
            f'<div class="s-ink" style="font:600 10px/1.3 {FONT};color:{INK};padding:0 0 3px;'
            f'white-space:nowrap">{label}</div><table role="presentation" width="100%" '
            f'cellpadding="0" cellspacing="0"><tr><td height="{h}" bgcolor="{colour}" '
            f'style="height:{h}px;background:{colour};border-radius:3px 3px 0 0;font-size:0;'
            f'line-height:0">&nbsp;</td></tr></table><div class="s-ink3" style="font:500 9px/1.3 '
            f'{FONT};color:{INK3};padding:4px 0 0">{day.day}</div></td>')
    note = "The tallest day is labelled. Pale stubs: days not in the figures (see the summary)."
    body = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-collapse:collapse;table-layout:fixed"><tr>{"".join(cols)}</tr></table>')
    return _card("Visitors per day", body, note)


def _missing(title: str, why: str) -> str:
    return _card(title, _p(why))


BREAKDOWN_WHY = ("Not shown: some days of the period were counted before this breakdown "
                 "was recorded, and a part of the period would not add up to its visitors.")


def sections(data: dict) -> list[str]:
    """The HTML cards, in the report's order."""
    out = []
    chosen = data["sections"]
    if "summary" in chosen:
        out += [_kpis(data), _bars(data)]
    if "sources" in chosen:
        out.append(_missing("Where visitors came from", BREAKDOWN_WHY) if data["sources"] is None
                   else _card("Where visitors came from", _table(_rows(data["sources"]),
                                                                 ("Source", "Visitors", ""))))
    if "pages" in chosen:
        out.append(_card("Top pages", _table(_rows(data["pages"], mono=True),
                                             ("Page", "Reads", ""))))
    if "places" in chosen:
        if data["countries"] is None:
            out.append(_missing("Countries and cities", BREAKDOWN_WHY))
        else:
            out.append(_card("Countries", _table(_rows(data["countries"]),
                                                 ("Country", "Visitors", ""))))
            out.append(_card("Cities", _table(_rows(data["cities"]), ("City", "Visitors", "")))
                       if data["cities"] else _missing("Cities", "Not recorded for every day "
                                                       "of the period (the city file was not "
                                                       "read on all of them)."))
    if "ai" in chosen:
        ai = data["ai"]
        lead = (f"{ai['asked']:,} fetches because someone asked an AI · {ai['training']:,} to "
                f"train or index · {ai['search']:,} by search engines · {ai['bots']:,} by "
                f"other bots.")
        rows = [(f'{esc(c["name"])}<div class="s-ink3" style="font:400 12px/1.4 {FONT};'
                 f'color:{INK3}">{esc(c["kind"])}</div>', f"{c['n']:,}", "")
                for c in ai["crawlers"]]
        body = _p(lead) + _table(rows, ("Who", "Requests", ""))
        if ai["cited_by"]:
            body += _p("AI assistants that sent visitors:", INK, 13) + \
                _table(_rows(ai["cited_by"]), ("Assistant", "Visitors", ""))
        out.append(_card("AI and bots", body, "Requests, not people: one question can fetch "
                                              "several pages."))
    if "leads" in chosen:
        leads = data["leads"]
        why = leads_missing(leads)
        out.append(_missing("Leads", why) if why else
                   _card("Leads", _p(f"{leads['total']:,} leads in the period.", INK, 14)
                         + _table(_rows(leads["rows"]), ("Kind", "Leads", "")), LEAD_RULE))
    if "search_console" in chosen:
        out.append(_search_console(data.get("search_console")))
    if "notes" in chosen and data["notes"]:
        body = "".join(_p(par, INK, 14) for par in data["notes"].split("\n") if par.strip())
        out.append(_card("Notes", body))
    return out


def _sc_rows(rows, mono: bool = False) -> list[tuple]:
    out = []
    for r in rows or []:
        name = esc(r["name"])
        if mono:
            name = f'<span style="font-family:{MONO};font-size:13px">{name}</span>'
        pos = "" if r["position"] is None else f" · position {r['position']:.1f}"
        name += (f'<div class="s-ink3" style="font:400 12px/1.4 {FONT};color:{INK3}">'
                 f'{num(r["impressions"])} impressions{pos}</div>')
        out.append((name, num(r["clicks"]), pct(r["ctr"])))
    return out


def _search_console(sc: dict | None) -> str:
    lines = search_console_lines(sc)
    if not sc or not sc.get("totals"):
        return _card("Search Console", "".join(_p(x) for x in lines))
    body = _p(lines[0], INK, 14) + "".join(_p(x) for x in lines[1:])
    body += _table(_sc_rows(sc["queries"]), ("Query", "Clicks", "CTR"))
    body += '<div style="height:12px"></div>' + _table(_sc_rows(sc["pages"], mono=True),
                                                        ("Page", "Clicks", "CTR"))
    return _card("Search Console", body, esc(SC_NOTE))


def render(data: dict, brand: dict, recipients: list[str]) -> str:
    """The whole HTML part. `brand`: agency_name, color, site_logo,
    agency_logo (bytes or None), letter, letter_color."""
    colour = brand.get("color") or INK
    ink_on = on(colour)
    agency = brand.get("agency_name") or ""
    when = period_words(data["first"], data["last"])
    zone = data["timezone"]
    site_mark = (f'<img src="cid:{SITE_CID}" width="40" height="40" alt="" style="display:block;'
                 f'width:40px;height:40px;border:0;border-radius:9px;background:#fff">'
                 if brand.get("site_logo") else
                 f'<div style="width:40px;height:40px;border-radius:9px;background:'
                 f'{brand.get("letter_color") or INK};color:#fff;font:700 20px/40px {FONT};'
                 f'text-align:center">{esc(brand.get("letter") or "?")}</div>')
    agency_mark = (f'<div style="display:inline-block;background:#ffffff;border-radius:8px;'
                   f'padding:4px 8px"><img src="cid:{AGENCY_CID}" height="32" alt="{esc(agency)}" '
                   f'style="display:block;height:32px;max-width:150px;border:0"></div>'
                   if brand.get("agency_logo") else
                   f'<div style="font:650 14px/1.3 {FONT};color:{ink_on}">{esc(agency)}</div>')
    band = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'bgcolor="{colour}" style="border-collapse:separate;background:{colour};'
            f'border-radius:12px;margin:0 0 16px"><tr><td style="padding:14px 18px" '
            f'width="48">{site_mark}</td><td style="padding:14px 0"><div style="font:700 '
            f'18px/1.25 {FONT};color:{ink_on}">{esc(data["name"])}</div><div style="font:400 '
            f'13px/1.4 {FONT};color:{ink_on};opacity:.9">{esc(data["site"])} · {esc(when)}</div>'
            f'</td><td align="right" style="padding:14px 18px">{agency_mark}</td></tr></table>')
    span = (f"{data['days']} days, midnight to midnight, {zone}. Figures from the web "
            f"server's own logs; verified days only.")
    foot = []
    if data["footer"]:
        foot.append(f'<div class="s-ink2" style="font:500 13px/1.6 {FONT};color:{INK2}">'
                    f'{esc(data["footer"])}</div>')
    made = f"Prepared by {agency} with Skald." if agency else "Made with Skald."
    foot.append(f'<div class="s-ink3" style="font:400 12px/1.6 {FONT};color:{INK3};padding-top:6px">'
                f'{esc(made)} You get this report because {esc(", ".join(recipients))} '
                f'{"is" if len(recipients) == 1 else "are"} on its list for {esc(data["site"])}. '
                f'Nothing in this mail tracks you. The PDF attached holds the same figures.</div>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f'<title>{esc(data["name"])}</title><style>{DARK}</style></head>'
        f'<body class="s-page" style="margin:0;padding:0;background:{PAGE}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'class="s-page" bgcolor="{PAGE}" style="background:{PAGE}"><tr><td align="center" '
        f'style="padding:24px 10px"><table role="presentation" width="100%" cellpadding="0" '
        f'cellspacing="0" style="max-width:640px;width:100%"><tr><td class="s-pad" '
        f'style="padding:0 6px">' + band
        + f'<div class="s-ink2" style="font:400 13px/1.5 {FONT};color:{INK2};padding:0 2px 14px">'
        f'{esc(span)}</div>' + "".join(sections(data))
        + f'<div style="text-align:center;padding:4px 12px 0;background:{PAGE}">'
        + "".join(foot) + '</div></td></tr></table></td></tr></table></body></html>')


def as_text(data: dict, brand: dict) -> str:
    """The plain-text part: the same figures, line by line."""
    head = data["headline"]
    lines = [data["name"], f"{data['site']} · {period_words(data['first'], data['last'])} "
             f"({data['timezone']})", ""]
    lines += coverage_lines(data) + [""]
    if "summary" in data["sections"]:
        for key, label in (("visitors", "Visitors"), ("pages", "Pages read"),
                           ("ai", "Visitors from AI"), ("leads", "Leads"),
                           ("returning", "Returning")):
            delta = data["changes"].get(key)
            lines.append(f"  {label:<20} {num(head[key]):>10}" + (f"  {delta}" if delta else ""))
        lines.append("")
    blocks = (("sources", "WHERE VISITORS CAME FROM"), ("pages", "TOP PAGES"),
              ("countries", "COUNTRIES"), ("cities", "CITIES"))
    for key, title in blocks:
        part = "places" if key in ("countries", "cities") else key
        if part in data["sections"] and data.get(key):
            lines.append(title)
            lines += [f"  {r['name'][:48]:<48} {r['n']:>9,}  {pct(r.get('share'))}"
                      for r in data[key]]
            lines.append("")
    if "ai" in data["sections"]:
        ai = data["ai"]
        lines += ["AI AND BOTS", f"  {ai['asked']:,} asked · {ai['training']:,} training · "
                  f"{ai['search']:,} search · {ai['bots']:,} other bots"]
        lines += [f"  {c['name']:<30} {c['n']:>9,}" for c in ai["crawlers"]] + [""]
    if "leads" in data["sections"] and data["leads"] and not leads_missing(data["leads"]):
        lines += ["LEADS"] + [f"  {r['name']:<30} {r['n']:>9,}" for r in data["leads"]["rows"]]
        lines.append("")
    if "search_console" in data["sections"]:
        sc = data.get("search_console")
        lines += ["SEARCH CONSOLE"] + [f"  {x}" for x in search_console_lines(sc)]
        for title, key in (("Query", "queries"), ("Page", "pages")):
            for r in (sc or {}).get(key) or []:
                lines.append(f"  {r['name'][:48]:<48} {num(r['clicks']):>9} clicks  "
                             f"{num(r['impressions'])} impressions")
        lines.append("")
    if "notes" in data["sections"] and data["notes"]:
        lines += ["NOTES", data["notes"], ""]
    if data["footer"]:
        lines.append(data["footer"])
    agency = brand.get("agency_name")
    lines.append(f"Prepared by {agency} with Skald." if agency else "Made with Skald.")
    return "\n".join(lines) + "\n"
