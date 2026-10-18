#!/usr/bin/env python3
"""Build the dashboard's "About Skald" and Help content from the docs.

    tools/build-about.py        # writes js/about-data.js, js/help-data.js and js/help-index.js

The docs stay the single source: docs/WHY-WE-BUILT-SKALD.md, docs/WHY-SKALD.md
(the story, up to and including the icon; not the rename checklist) and
docs/COMPARISON.md (the matrix, its notes and sources, where Skald leads, where others
do, and who should use what). They are turned into plain data - blocks of text, links and tables - that
the page draws with its own components, so nothing is fetched and no HTML from
the docs is ever injected. Run it whenever those docs change, and commit the
result; tests/test_about.py fails when the built file is stale.

The Help pages come the same way from docs/help/*.md, one guide each, in the
order of HELP_ORDER: help-data.js holds every guide (loaded when Help opens),
help-index.js only their names (for the command palette and the shortcuts
list). Guides may also use code blocks and simple tables; tests/test_help.py
fails when either file is stale.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = ROOT / "skald" / "webapp" / "js" / "about-data.js"
HELP = DOCS / "help"
HELP_OUT = ROOT / "skald" / "webapp" / "js" / "help-data.js"
HELP_INDEX = ROOT / "skald" / "webapp" / "js" / "help-index.js"
# The guides in the order the Help page lists them; a new guide not named here comes last.
HELP_ORDER = ("getting-started", "docker-first-install", "pick-your-road", "sign-in-and-team", "real-time", "internal-traffic",
              "leads-and-conversions", "tracking-script", "webhooks", "leads-from-your-backend", "demo-bookings",
              "funnels-and-goals", "ai-and-bots", "api", "mcp", "settings-and-retention", "privacy", "faq")
GUIDES = sorted((p.stem for p in HELP.glob("*.md") if p.stem.lower() != "readme"),
                key=lambda k: (HELP_ORDER.index(k) if k in HELP_ORDER else len(HELP_ORDER), k)) if HELP.is_dir() else []

# Links between the docs become links inside the page; other repo files are plain text.
LOCAL = {"COMPARISON.md": ("#about?part=compare", "the comparison below"), "comparison.html": ("#about?part=compare", "the table below"),
         "WHY-WE-BUILT-SKALD.md": ("#about?part=why", "Why we built Skald"), "WHY-SKALD.md": ("#about?part=name", "Why the name")}
TAGLINE = "**Every visit, truly told.**"

# A matrix cell shows at most six words; the full text opens in its note. Every
# longer cell needs a short form here, or the build stops and says which.
SHORT_WORDS = 6
SHORT = {
    "Google's own search data; nothing on your site": "Google's own search data",
    "Bing's own search data; nothing on your site": "Bing's own search data",
    "JavaScript tag, or server logs through its importer": "JavaScript tag, or log import",
    "JavaScript beacon; AI Crawl Control at Cloudflare's edge": "JavaScript beacon; edge for crawlers",
    "Events sent from your server, CDN or WordPress": "Events from your server or CDN",
    "Visitors now and today so far every 2 minutes; requests every 15 seconds": "Visitors 2 min, requests 15 s",
    "Realtime covers the last 30 minutes; full processing 24-48 hours": "Last 30 minutes; full in 24-48h",
    "Current visitors (last 5 minutes); refreshes every 30 seconds": "Last 5 minutes, every 30 seconds",
    "Real-time visitor log; the importer can stream": "Real-time visitor log",
    "Live view; online count covers 30 seconds": "Live view; last 30 seconds",
    "Raw addresses 14 days in the log; hashes 30 days; totals for good": "Addresses 14 days; totals for good",
    "Explorations 2 or 14 months (360: up to 50)": "Explorations 2 or 14 months",
    "Cloud: raw 24 months, reports for good; self-host: yours": "Cloud: raw data 24 months",
    "1 year free, 7 years paid; self-host: yours": "1 year free, 7 paid",
    "Free to self-host; runs on your server (Python 3.11+, standard library)": "Free, on your own server",
    "From $9 a month (10k pageviews); self-host free": "From $9 a month",
    "Cloud from EUR 29 a month; self-host free": "From EUR 29 a month",
    "Web Analytics free; AI Crawl Control on all plans": "Free; Crawl Control on all plans",
    "1M events a month free, then per event": "1M events a month free",
    "Free to 100k events; $29 and $299 a month": "Free to 100k events, then $29",
    "Source-available, Elastic License 2.0: free to use and self-host; hosting it for others needs a licence": "Source-available (Elastic License 2.0)",
}
# Repository files a note cites: named on the page, not linked (they are not served).
REPO_FILE = "in Skald's code"
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

INLINE = re.compile(r"\[\[(\d+)\]\]\(([^)]+)\)|\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`|\[\^(\d+)\]")


def link(label: str, href: str) -> dict:
    href = href.strip()
    if href.startswith(("http://", "https://")):
        return {"a": label, "href": href}
    # A page of the app (#settings/integrations) stays a link inside it.
    if re.match(r"^#[a-z][a-z/-]*(\?[a-z]+=[a-z0-9-]+)?$", href):
        return {"a": label, "href": href}
    name = href.split("/")[-1].split("#")[0]
    # A Help guide (webhooks.md) opens in Help.
    if name.endswith(".md") and name[:-3] in GUIDES:
        return {"a": label, "href": f"#help?part={name[:-3]}"}
    if name in LOCAL:
        href, words = LOCAL[name]
        # A file name reads oddly on a page: say what it is instead.
        return {"a": words if label.endswith((".md", ".html")) else label, "href": href}
    return {"s": label}


def inline(text: str) -> list:
    """Markdown inline to segments: {s}, {b}, {i}, {code}, {a, href}, {ref: n} (a footnote)."""
    text = re.sub(r"<br\s*/?>", " ", text)
    out, pos = [], 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            out.append({"s": text[pos:m.start()]})
        if m.group(1):
            out.append({**link(f"[{m.group(1)}]", m.group(2)), "cite": True})
        elif m.group(3):
            out.append(link(m.group(3), m.group(4)))
        elif m.group(5):
            out.append({"b": m.group(5)})
        elif m.group(6):
            out.append({"i": m.group(6)})
        elif m.group(7):
            out.append({"code": m.group(7)})
        else:
            out.append({"ref": int(m.group(8))})
        pos = m.end()
    if pos < len(text):
        out.append({"s": text[pos:]})
    return [x for x in out if x.get("s", "x") != ""]


def cells(row: str) -> list:
    return [inline(c.strip()) for c in row.strip().strip("|").split("|")]


def blocks(md: str, rich: bool = False) -> list:
    """Headings, paragraphs, lists and quotes; tables are left to the matrix.
    rich (the Help guides): code blocks ({t: pre}) and simple tables ({t: table}) too."""
    out, para, code, table = [], [], None, []

    def flush():
        if para:
            quote = para[0] == "\x00quote"
            text = " ".join(para[1:] if quote else para)
            # The tagline already heads the page; a doc's own copy of it is left out.
            if text.strip() != TAGLINE:
                out.append({"t": "quote" if quote else "p", "in": inline(text)})
            para.clear()

    def flush_table():
        if table:
            body = [r for r in table[1:] if not set(r.replace("|", "").strip()) <= set(":- ")]
            out.append({"t": "table", "head": cells(table[0]), "rows": [cells(r) for r in body]})
            table.clear()

    for line in md.splitlines():
        s = line.rstrip()
        if rich and code is not None:
            if s.strip().startswith("```"):
                out.append({"t": "pre", "text": "\n".join(code)})
                code = None
            else:
                code.append(line.rstrip())
            continue
        if rich and s.strip().startswith("```"):
            flush()
            flush_table()
            code = []
            continue
        if rich and s.startswith("|"):
            flush()
            table.append(s)
            continue
        flush_table()
        if not s.strip():
            flush()
            continue
        if para and para[0] == "\x00quote" and not s.startswith(">"):
            flush()
        if s.startswith("#"):
            flush()
            level = len(s) - len(s.lstrip("#"))
            out.append({"t": f"h{min(level, 4)}", "text": s.lstrip("#").strip()})
        elif re.match(r"^\s*(-|\d+\.)\s", s):
            flush()
            item = re.sub(r"^\s*(-|\d+\.)\s+", "", s)
            ordered = bool(re.match(r"^\s*\d+\.", s))
            if out and out[-1]["t"] == ("ol" if ordered else "ul"):
                out[-1]["items"].append(inline(item))
            else:
                out.append({"t": "ol" if ordered else "ul", "items": [inline(item)]})
                start = int(re.match(r"^\s*(\d+)", s).group(1)) if ordered else 1
                if start != 1:
                    out[-1]["start"] = start
        elif s.startswith(">"):
            # A quote may run over several lines: they are one quote.
            if para and para[0] == "\x00quote":
                para.append(s.lstrip("> ").strip())
            else:
                flush()
                para.extend(["\x00quote", s.lstrip("> ").strip()])
        elif s.startswith("|"):
            flush()
        else:
            para.append(s.strip())
    flush()
    flush_table()
    if code is not None:
        out.append({"t": "pre", "text": "\n".join(code)})
    return out


def section(md: str, start: str | None, stop: str | None) -> str:
    """The text from heading `start` (or the top) up to heading `stop` (excluded)."""
    lines = md.splitlines()
    i = 0 if start is None else next(k for k, l in enumerate(lines) if l.strip() == start)
    j = len(lines) if stop is None else next((k for k, l in enumerate(lines) if l.strip() == stop), len(lines))
    return "\n".join(lines[i:j])


LISTS = ("Where Skald leads", "Where others lead", "Who should use what", "Also checked")


def matrix(md: str) -> dict:
    """COMPARISON.md: the legend, the modules with their groups of rows, the notes."""
    tools, modules, raw = [], [], {}
    module = group = None
    lines = md.splitlines()
    for k, line in enumerate(lines):
        s = line.strip()
        m = re.match(r"^\[\^(\d+)\]:\s*(.*)$", s)
        if m:
            raw[int(m.group(1))] = m.group(2)
            continue
        if s.startswith("## "):
            name = s[3:].strip()
            if name in LISTS or name == "Notes":
                module = None
                continue
            desc = next((l.strip() for l in lines[k + 1:k + 4] if l.strip() and not l.startswith(("|", "**", "#"))), "")
            module = {"name": name, "desc": desc, "groups": []}
            modules.append(module)
            group = None
        elif module is not None and re.match(r"^\*\*[^*]+\*\*$", s):
            group = {"name": s.strip("*"), "rows": []}
            module["groups"].append(group)
        elif module is not None and s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells[0] == "Feature":
                tools = cells[1:]
                continue
            if set(cells[0]) <= set(":- "):
                continue
            if group is None:
                group = {"name": "", "rows": []}
                module["groups"].append(group)
            feat = cells[0]
            sub = ""
            sm = re.search(r"<br>\s*<sub>(.*?)</sub>", feat)
            if sm:
                sub = sm.group(1)
                feat = feat[:sm.start()].strip()
            row = {"feature": feat, "sub": sub, "cells": []}
            for c in cells[1:]:
                refs = [int(x) for x in re.findall(r"\[\^(\d+)\]", c)]
                body = re.sub(r"\s*\[\^\d+\]", "", c).strip()
                mark = body if body in ("✓", "◐", "✗", "?", "–", "planned") else "text"
                cell = {"mark": mark, "text": "" if mark != "text" else body, "refs": refs}
                if mark == "text" and len(body.split()) > SHORT_WORDS:
                    if body not in SHORT:
                        sys.exit(f"build-about: no short form (six words at most) for the cell {body!r}: add it to SHORT")
                    cell["short"] = SHORT[body]
                row["cells"].append(cell)
            group["rows"].append(row)
    sources, seen = [], {}

    def cite(label: str, href: str) -> int:
        """The number of a source in the list at the bottom, added on first sight."""
        href = href.strip()
        web = href.startswith(("http://", "https://"))
        key = href if web else href.split("/")[-1]
        if key not in seen:
            sources.append({"label": label, "href": href} if web else {"label": label, "file": key})
            seen[key] = len(sources)
        return seen[key]

    def cited(text: str) -> tuple[list, list]:
        """A note's words without its links, and the numbers of the sources it links to."""
        src = [cite(a, b) for a, b in LINK.findall(text)]
        # What is left after the links: "Sources:" and the commas and semicolons between them.
        words = re.sub(r"\s*Sources?:[\s,.;]*$", "", LINK.sub("", text).strip())
        words = re.sub(r"[\s;,]+$", "", words)
        return (inline(words) if words.strip(" .") else []), list(dict.fromkeys(src))

    notes = {}
    for n in sorted(raw):
        m = re.match(r"^\*\*([^*]+)\*\*:?\s*(.*)$", raw[n])
        who, rest = (m.group(1), m.group(2)) if m else ("", raw[n])
        tool, _, about = who.partition(", ")
        text, src = cited(rest)
        notes[str(n)] = {"tool": tool, "about": about, "text": text, "src": src}

    def items(title: str) -> list:
        """A list section's items as (bold lead, the rest) pairs."""
        part = section(md, f"## {title}", next((l.strip() for l in md[md.find(f"## {title}") + 3:].splitlines() if l.startswith("## ")), None))
        out = []
        for line in part.splitlines():
            m = re.match(r"^- \*\*(.+?)\*\*\s*(.*)$", line.strip())
            if m:
                out.append((m.group(1).rstrip("."), m.group(2)))
        return out

    def lede(title: str) -> str:
        part = section(md, f"## {title}", None).splitlines()[1:]
        return next((l.strip() for l in part if l.strip() and not l.startswith(("-", "#"))), "")

    leads = [{"title": t, "text": inline(x)} for t, x in items("Where Skald leads")]
    others = [{"title": t, "text": inline(x)} for t, x in items("Where others lead")]
    who = []
    for need, rest in items("Who should use what"):
        use, _, why = rest.partition(". ")
        who.append({"need": need, "use": [t for t in tools if t in use], "text": use.rstrip("."), "why": why})
    also = []
    for name, rest in items("Also checked"):
        text, src = cited(rest)
        also.append({"name": name, "text": text, "src": src})
    legend = []
    for line in section(md, None, "## Data collection").splitlines():
        m = re.match(r"^\|\s*(✓|◐|✗|planned|\?|–)\s*\|\s*(.+?)\s*\|$", line.strip())
        if m:
            legend.append({"mark": m.group(1), "means": m.group(2)})
    intro = blocks("\n".join(l for l in section(md, None, "## Data collection").splitlines()[1:] if not l.startswith("|")))
    checked = re.search(r"checked on (\d{4}-\d{2}-\d{2})", md)
    return {"tools": tools, "legend": legend, "intro": intro, "modules": modules, "notes": notes, "sources": sources,
            "checked": checked.group(1) if checked else "", "where_skald_leads": leads, "where_others_lead": others,
            "who": who, "who_lede": lede("Who should use what"), "also_checked": also, "also_lede": lede("Also checked")}


def build() -> str:
    why = (DOCS / "WHY-WE-BUILT-SKALD.md").read_text(encoding="utf-8")
    name = (DOCS / "WHY-SKALD.md").read_text(encoding="utf-8")
    comp = (DOCS / "COMPARISON.md").read_text(encoding="utf-8")
    after_icon = next((h for h in re.findall(r"^## .+$", name, re.M) if name.index(h) > name.index("## The icon")), None)
    data = {
        "why": blocks("\n".join(why.splitlines()[1:])),
        "name": blocks("\n".join(section(name, None, after_icon).splitlines()[1:])),
        "compare": matrix(comp),
    }
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return ("// Built by tools/build-about.py from docs/WHY-WE-BUILT-SKALD.md, docs/WHY-SKALD.md and\n"
            "// docs/COMPARISON.md. Do not edit: change the docs and run the script again.\n"
            f"export default {body};\n")


def guide(key: str) -> dict:
    """One Help guide: its title (the # line), its summary (the first paragraph), the rest as blocks."""
    md = (HELP / f"{key}.md").read_text(encoding="utf-8")
    lines = md.splitlines()
    top = next((k for k, l in enumerate(lines) if l.startswith("# ")), None)
    if top is None:
        sys.exit(f"build-about: docs/help/{key}.md has no '# Title' line")
    body = blocks("\n".join(lines[top + 1:]), rich=True)
    summary = body.pop(0)["in"] if body and body[0]["t"] == "p" else []
    return {"id": key, "title": lines[top][2:].strip(), "summary": summary, "blocks": body}


def plain(segs: list) -> str:
    return "".join(x.get("s") or x.get("b") or x.get("i") or x.get("code") or x.get("a") or "" for x in segs)


def build_help() -> tuple[str, str]:
    guides = [guide(k) for k in GUIDES]
    body = json.dumps({"guides": guides}, ensure_ascii=False, separators=(",", ":"))
    index = json.dumps([{"id": g["id"], "title": g["title"], "summary": plain(g["summary"])} for g in guides], ensure_ascii=False, separators=(",", ":"))
    head = "// Built by tools/build-about.py from docs/help/*.md. Do not edit: change the guides and run the script again.\n"
    return f"{head}export default {body};\n", f"{head}// The guides' names only, for the command palette and the shortcuts list.\nexport default {index};\n"


if __name__ == "__main__":
    outs = [(OUT, build()), *zip((HELP_OUT, HELP_INDEX), build_help())]
    if "--check" in sys.argv:
        sys.exit(0 if all(p.exists() and p.read_text(encoding="utf-8") == t for p, t in outs) else 1)
    for path, text in outs:
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(text) // 1024} KB)")
