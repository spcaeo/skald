"""The second count of what AI fetches asked for (day kind `ai_formats`).

Registered in audit_more.RECOUNTS. It sees every line the audit judged
(`hit`) and counts the lines the audit put in "answer_engines", by the
audit's tier and crawler name and by its own reading of the path, written
apart from ai_formats.py (it imports nothing from the package):

  the path      the line's path, lower case, cut at "?" and "#"
  llms.txt      exactly /llms.txt or /llms-full.txt
  robots.txt    exactly /robots.txt
  Markdown      the last segment ends ".md" or ".mdx"
  Sitemap       the last segment starts "sitemap" and ends ".xml"
  Text          the last segment ends ".txt"
  Other file    a file extension below, a framework folder, an /api path or
                beacon, or a framework payload in the query string
  Page          anything else

It compares every format per tier, every kept name's formats, and the
folded "(all others)" against the names the stored day did not keep.
"""
from __future__ import annotations

import re
from collections import Counter

REST = "(all others)"
_FILES = (".css", ".js", ".mjs", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
          ".avif", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".xml", ".json", ".webmanifest",
          ".xsl", ".xslt", ".rss", ".atom", ".csv", ".tsv", ".pdf", ".zip", ".gz", ".tgz",
          ".rar", ".7z", ".mp4", ".webm", ".mov", ".mp3", ".wav", ".ogg", ".m4a", ".doc",
          ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".wasm")
_FOLDERS = ("/_next/", "/static/", "/assets/", "/_nuxt/", "/build/")
_ENDPOINT = re.compile(r"^/(?:api(?:/|$)|(?:__analytics|collect|beacon|ping)\b)")
_PAYLOAD = re.compile(r"[?&](?:_rsc|__flight__|_data)=", re.I)


def kind_of(path: str, url: str) -> str:
    p = re.split(r"[?#]", path or "", maxsplit=1)[0].lower()
    last = p[p.rfind("/") + 1:]
    if p == "/llms.txt" or p == "/llms-full.txt":
        return "llms.txt"
    if p == "/robots.txt":
        return "robots.txt"
    if last.endswith(".md") or last.endswith(".mdx"):
        return "Markdown"
    if last.startswith("sitemap") and last.endswith(".xml"):
        return "Sitemap"
    if last.endswith(".txt"):
        return "Text"
    if p.endswith(_FILES) or p.startswith(_FOLDERS) or _ENDPOINT.match(p) \
            or _PAYLOAD.search(url or ""):
        return "Other file"
    return "Page"


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.seen = {"asked": Counter(), "training": Counter()}    # (name, kind) -> n

    def hit(self, line, group, tier, name) -> None:
        if group == "answer_engines" and tier in self.seen:
            self.seen[tier][(name, kind_of(line.path, line.url))] += 1

    def visit(self, lines, is_page, labels) -> None:
        return None

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("ai_formats")
        if blob is None:
            return
        for tier, seen in self.seen.items():
            part = blob.get(tier) or {}
            mine: Counter = Counter()
            names: dict[str, Counter] = {}
            for (name, kind), n in seen.items():
                mine[kind] += n
                names.setdefault(name, Counter())[kind] += n
            kept = {k: int(v) for k, v in (part.get("formats") or {}).items()}
            for kind in sorted(set(kept) | set(mine)):
                same(f"ai_formats: {tier} {kind}", kept.get(kind, 0), mine[kind])
            stored_names = part.get("by_name") or {}
            rest: Counter = Counter()
            for name, got in names.items():
                if name not in stored_names or name == REST:
                    rest.update(got)
            for name in sorted(stored_names):
                was = {k: int(v) for k, v in (stored_names[name] or {}).items()}
                now = rest if name == REST else names.get(name, Counter())
                for kind in sorted(set(was) | set(now)):
                    same(f"ai_formats: {tier} {name} {kind}", was.get(kind, 0), now[kind])
            if REST not in stored_names:
                for kind in sorted(rest):
                    same(f"ai_formats: {tier} {REST} {kind}", 0, rest[kind])
