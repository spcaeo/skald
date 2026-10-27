"""A client report (client_report_data.py) as a PDF: A4, vector text, tables
and bars, drawn with pdf_writer.py - the same figures, in the same order,
as the mail it is attached to (client_report_html.py).

The chart is one series (visitors per day), so it has no legend: its title
names it. Columns at most 16 pt wide with a 2 pt gap, rounded at the top,
square at the baseline; only the tallest day is labelled; a day not in the
figures is a pale stub, never a zero. Text is ink on the page's paper; the
agency's colour is only the top band, with white or ink text on it.
"""
from __future__ import annotations

from datetime import date

from . import pdf_writer as pw
from .client_report_data import (LEAD_RULE, SC_NOTE, asked_words, coverage_lines, leads_missing,
                                 num, pct, period_words, search_console_lines)
from .client_report_html import BREAKDOWN_WHY, GAP, on
from .mail_html import INK, INK2, INK3, PEOPLE, RULE

M = 42                                  # page margin
W, H = pw.A4
CW = W - 2 * M                          # content width
FOOT = 46                               # room kept for the footer
TRACK = "#e4e9ee"


class Layout:
    def __init__(self, doc: pw.Document, data: dict):
        self.doc, self.data = doc, data
        self.page = None
        self.y = 0.0
        self.new_page(first=True)

    def new_page(self, first: bool = False) -> None:
        self.page = self.doc.add_page()
        self.y = M
        if not first:
            self.page.text(M, self.y + 8, pw.fit(f"{self.data['name']} · {self.data['site']}",
                                                 8, CW), 8, color=INK3)
            self.y += 22

    def need(self, h: float) -> None:
        if self.y + h > H - M - FOOT:
            self.new_page()

    def heading(self, title: str, room: float = 60) -> None:
        self.need(room + 26)
        self.y += 10
        self.page.text(M, self.y + 11, title, 12, bold=True, color=INK)
        self.y += 18
        self.page.line(M, self.y, M + CW, self.y, RULE, 0.6)
        self.y += 8

    def para(self, text: str, size: float = 9, color: str = INK2, bold: bool = False) -> None:
        for line in pw.wrap(text, size, CW, bold):
            self.need(size * 1.5)
            self.page.text(M, self.y + size, line, size, bold, color)
            self.y += size * 1.5


def _header(lay: Layout, brand: dict, logos: dict) -> None:
    p, data = lay.page, lay.data
    colour = brand.get("color") or INK
    ink_on = on(colour)
    p.rect(M, lay.y, CW, 66, fill=colour, radius=8)
    if logos.get("site"):
        p.rect(M + 12, lay.y + 13, 40, 40, fill="#ffffff", radius=6)
        p.image(logos["site"], M + 14, lay.y + 15, 36, 36)
    else:
        p.rect(M + 12, lay.y + 13, 40, 40, fill=brand.get("letter_color") or INK, radius=6)
        p.text(M + 32, lay.y + 40, brand.get("letter") or "?", 20, True, "#ffffff", "center")
    right = M + CW - 14
    agency = brand.get("agency_name") or ""
    room = CW - 64 - 12
    if logos.get("agency"):
        img = logos["agency"]
        w = min(120, img.width * 32 / img.height) + 12
        p.rect(right - w, lay.y + 15, w, 36, fill="#ffffff", radius=6)
        p.image(img, right - w + 6, lay.y + 17, w - 12, 32)
        room -= 132
    elif agency:
        words = pw.fit(agency, 10, 150, True)
        p.text(right, lay.y + 37, words, 10, True, ink_on, "right")
        room -= pw.text_width(words, 10, True) + 14
    p.text(M + 64, lay.y + 30, pw.fit(data["name"], 15, room, True), 15, True, ink_on)
    p.text(M + 64, lay.y + 47, pw.fit(f"{data['site']} · "
                                      f"{period_words(data['first'], data['last'])}", 9.5, room),
           9.5, color=ink_on)
    lay.y += 78
    lay.para(f"{data['days']} days, midnight to midnight, {data['timezone']}. Figures from the "
             f"web server's own logs; verified days only.", 9, INK2)


def _kpis(lay: Layout) -> None:
    data = lay.data
    lay.heading("Summary", 140)
    tiles = (("visitors", "VISITORS"), ("pages", "PAGES READ"), ("ai", "FROM AI"),
             ("leads", "LEADS"), ("returning", "RETURNING"))
    col = CW / len(tiles)
    for i, (key, label) in enumerate(tiles):
        x = M + i * col
        lay.page.text(x, lay.y + 8, label, 7, True, INK3)
        lay.page.text(x, lay.y + 29, num(data["headline"][key]), 18, True, INK)
        delta = data["changes"].get(key)
        if delta:
            lay.page.text(x, lay.y + 42, delta, 8.5, False, INK2)
    lay.y += 52
    for line in coverage_lines(data):
        lay.para(line, 9, INK2)
    lay.para(("Change against the period before, the same length, only when both are whole and "
              "verified." if data["compared"] else "No change is given: the period before is "
              "not wholly recorded.") + " Visitors are people whose browser drew the page; "
             "automated readers are left out. From AI: visitors who came from an AI assistant's "
             "answer.", 8, INK3)


def _bars(lay: Layout) -> None:
    days = lay.data["daily"]
    lay.heading("Visitors per day", 150)
    top = max([d["visitors"] for d in days if d["visitors"]] or [1])
    plot_h, base = 100, lay.y + 116
    slot = CW / max(1, len(days))
    bar = min(16, slot - 2)
    p = lay.page
    p.line(M, base - plot_h, M + CW, base - plot_h, TRACK, 0.5)
    peak = max(days, key=lambda d: d["visitors"] or -1)
    every = 1 if slot >= 14 else 2 if slot >= 8 else 7
    for i, d in enumerate(days):
        x = M + i * slot + (slot - bar) / 2
        v = d["visitors"]
        if v is None:
            p.rect(x, base - 4, bar, 4, fill=GAP)
        elif v:
            h = max(1.5, v / top * plot_h)
            p.rect(x, base - h, bar, h, fill=PEOPLE, radius=min(3, bar / 2), top_only=True)
            if d is peak:
                p.text(x + bar / 2, base - h - 4, f"{v:,}", 7.5, True, INK, "center")
        if i % every == 0:
            p.text(x + bar / 2, base + 10, str(date.fromisoformat(d["day"]).day), 7, False,
                   INK3, "center")
    p.line(M, base, M + CW, base, RULE, 0.6)
    lay.y = base + 18
    lay.para("Pale stubs: days not in the figures (see the summary). The tallest day is "
             "labelled.", 8, INK3)


def _table(lay: Layout, heads: tuple, rows: list[dict], share: bool = True,
           note: str = "") -> None:
    """Name, figure and (optionally) its share with a small bar."""
    if not rows:
        lay.para("Nothing recorded.", 9, INK3)
        return
    name_w = CW - 70 - (100 if share else 0)

    def head():
        lay.page.text(M, lay.y + 8, heads[0].upper(), 7, True, INK3)
        lay.page.text(M + name_w + 70, lay.y + 8, heads[1].upper(), 7, True, INK3, "right")
        lay.y += 13
    lay.need(30)
    head()
    for r in rows:
        before = lay.page
        lay.need(17)
        if lay.page is not before:      # a table carried over: its heads again
            head()
        p = lay.page
        p.text(M, lay.y + 11, pw.fit(r["name"], 9.5, name_w - 8), 9.5, False, INK)
        p.text(M + name_w + 70, lay.y + 11, f"{r['n']:,}", 9.5, True, INK, "right")
        if share and r.get("share") is not None:
            p.rect(M + name_w + 82, lay.y + 5, 60, 6, fill=TRACK, radius=2)
            p.rect(M + name_w + 82, lay.y + 5, max(1.5, 60 * r["share"]), 6, fill=PEOPLE,
                   radius=2)
            p.text(M + CW, lay.y + 11, pct(r["share"]), 8.5, False, INK2, "right")
        lay.y += 16
        p.line(M, lay.y, M + CW, lay.y, TRACK, 0.4)
    lay.y += 4
    if note:
        lay.para(note, 8, INK3)


def _sections(lay: Layout) -> None:
    data = lay.data
    chosen = data["sections"]
    if "summary" in chosen:
        _kpis(lay)
        _bars(lay)
    if "sources" in chosen:
        lay.heading("Where visitors came from")
        if data["sources"] is None:
            lay.para(BREAKDOWN_WHY)
        else:
            _table(lay, ("Source", "Visitors"), data["sources"],
                   note="Each visitor counted once, by the first page they read.")
    if "pages" in chosen:
        lay.heading("Top pages")
        _table(lay, ("Page", "Reads"), data["pages"])
    if "places" in chosen:
        lay.heading("Countries")
        if data["countries"] is None:
            lay.para(BREAKDOWN_WHY)
        else:
            _table(lay, ("Country", "Visitors"), data["countries"])
            lay.heading("Cities")
            if data["cities"]:
                _table(lay, ("City", "Visitors"), data["cities"])
            else:
                lay.para("Not recorded for every day of the period (the city file was not "
                         "read on all of them).")
    if "ai" in chosen:
        ai = data["ai"]
        lay.heading("AI and bots")
        lay.para(f"{asked_words(ai)} · {ai['training']:,} requests "
                 f"to train or index · {ai['search']:,} by search engines · {ai['bots']:,} by "
                 f"other bots.", 9, INK2)
        lay.y += 4
        _table(lay, ("Who", "Requests"), [{"name": f"{c['name']} ({c['kind']})", "n": c["n"]}
                                          for c in ai["crawlers"]], share=False,
               note="Requests, not people. A page read is one page an AI fetched for someone's "
                    "question; asking for it again within seconds, or for its files, is no new "
                    "read.")
        if ai["cited_by"]:
            lay.need(40)
            lay.y += 8
            lay.para("AI assistants that sent visitors", 9.5, INK, True)
            _table(lay, ("Assistant", "Visitors"), ai["cited_by"])
    if "leads" in chosen:
        lay.heading("Leads")
        why = leads_missing(data["leads"])
        if why:
            lay.para(why)
        else:
            lay.para(f"{data['leads']['total']:,} leads in the period.", 10, INK, True)
            _table(lay, ("Kind", "Leads"), data["leads"]["rows"], note=LEAD_RULE)
    if "search_console" in chosen:
        sc = data.get("search_console")
        lay.heading("Search Console")
        lines = search_console_lines(sc)
        lay.para(lines[0], 10 if sc and sc.get("totals") else 9,
                 INK if sc and sc.get("totals") else INK2, bool(sc and sc.get("totals")))
        for x in lines[1:]:
            lay.para(x, 8.5, INK2)
        if sc and sc.get("totals"):
            lay.y += 4
            for heads, key in ((("Query", "Clicks"), "queries"), (("Page", "Clicks"), "pages")):
                _table(lay, heads, [{"name": f"{r['name']} ({num(r['impressions'])} impressions"
                                             + ("" if r["position"] is None
                                                else f", position {r['position']:.1f}") + ")",
                                     "n": r["clicks"], "share": r["ctr"]}
                                    for r in sc[key]])
            lay.para(SC_NOTE, 8, INK3)
    if "notes" in chosen and data["notes"]:
        lay.heading("Notes", 30)
        lay.para(data["notes"], 10, INK)


def render(data: dict, brand: dict, now=None) -> bytes:
    """The PDF's bytes. `brand` as client_report_html.render takes it."""
    agency = brand.get("agency_name") or ""
    doc = pw.Document(title=f"{data['name']} - {data['site']}", author=agency or "Skald")
    logos = {}
    if brand.get("site_logo"):
        logos["site"] = doc.image(brand["site_logo"])
    if brand.get("agency_logo"):
        logos["agency"] = doc.image(brand["agency_logo"])
    lay = Layout(doc, data)
    _header(lay, brand, logos)
    _sections(lay)
    made = f"Prepared by {agency} with Skald" if agency else "Made with Skald"
    total = len(doc.pages)
    for n, page in enumerate(doc.pages, start=1):
        page.line(M, H - M - 18, M + CW, H - M - 18, RULE, 0.5)
        left = data["footer"] or made
        page.text(M, H - M - 6, pw.fit(left, 8, CW - 90), 8, False, INK2)
        page.text(M + CW, H - M - 6, f"Page {n} of {total}", 8, False, INK3, "right")
        if data["footer"]:
            page.text(M, H - M + 6, made, 7, False, INK3)
    return doc.to_bytes(now)
