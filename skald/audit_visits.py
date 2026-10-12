"""The audit's own recount of visits and of our own traffic by label.

Part of audit.py's second road, and written apart from visits.py on
purpose: the visits audit.recount already splits for the readers are
walked again here, in time order, to rebuild every stored visit figure -
pages loaded per visit, pages seen (in-app moves included), duration,
exit page, each step from page to page, the visits that met a 404,
sent a POST or moved in-app, and per page the visits seen on it and the
visits that ended on it (pages.json's exit rate is the one over the other). Nothing from visits.py, parse.py or
dimensions.py is called. The rules are the ones documented in visits.py
and SOP.md, read from the text and written again.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import urlsplit

OTHER = "(all others)"
_SKIP_EXT = (".css", ".js", ".mjs", ".map", ".png", ".jpg", ".jpeg", ".gif", ".svg",
             ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".txt",
             ".xml", ".json", ".webmanifest", ".xsl", ".xslt", ".rss", ".atom", ".csv",
             ".tsv", ".pdf", ".zip", ".gz", ".tgz", ".rar", ".7z", ".mp4", ".webm", ".mov",
             ".mp3", ".wav", ".ogg", ".m4a", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
             ".pptx", ".wasm")
_SKIP_DIRS = ("/_next/", "/static/", "/assets/", "/_nuxt/", "/build/")
_BEACONS = ("api/events", "api/analytics", "__analytics", "collect", "beacon", "ping")


def _is_asset_path(path: str) -> bool:
    low = path.lower()
    return low.endswith(_SKIP_EXT) or low.startswith(_SKIP_DIRS)


def _is_beacon_path(path: str) -> bool:
    low = path.lower()
    for name in _BEACONS:
        head = "/" + name
        if low.startswith(head):
            rest = low[len(head):]
            # A word boundary after the name, as the documented rule says.
            if not rest or not (rest[0].isalnum() or rest[0] == "_"):
                return True
    return False


def _bucket(seconds: int) -> int:
    """Seconds under a minute, 10 s steps under ten minutes, minutes under an
    hour, then 10-minute steps (SOP.md, "Visits")."""
    if seconds < 60:
        return seconds
    step = 10 if seconds < 600 else 60 if seconds < 3600 else 600
    return seconds // step * step


def ours_entries(raw, key: str, addresses: bool) -> list[tuple[str, str]]:
    """(value, label) from one `ours` list, plain or labelled entries; an
    unlabelled address is "Listed address N", never itself."""
    out = []
    for i, item in enumerate(raw or [], 1):
        value, label = (item.get(key) or item.get("value"), item.get("label")) \
            if isinstance(item, dict) else (item, None)
        value = str(value or "").strip()
        if not value:
            continue
        label = str(label or "").strip() or (f"Listed address {i}" if addresses else value)
        out.append((value, label))
    return out


def page_added(config: dict) -> list[tuple[str, str, object]]:
    """(ip or range, label, from when) for the addresses added on the page:
    the JSON file `ours.file` (else ours.json beside the history), read here
    on its own terms."""
    import json
    import os
    from datetime import datetime, timezone
    raw = ((config or {}).get("ours") or {}).get("file")
    if not raw:
        made = (((config or {}).get("_resolved") or {}).get("history_db")
                or ((config or {}).get("history") or {}).get("db"))
        made = os.path.expanduser(str(made)) if made else ""
        if not os.path.isabs(made):
            return []
        raw = os.path.join(os.path.dirname(made), "ours.json")
    try:
        with open(str(raw), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return []
    out = []
    for e in (data.get("entries") or []) if isinstance(data, dict) else []:
        if not isinstance(e, dict) or not e.get("ip") or not e.get("label"):
            continue
        try:
            when = datetime.fromisoformat(str(e.get("added_at") or ""))
        except ValueError:
            continue
        out.append((str(e["ip"]), " ".join(str(e["label"]).split()),
                    when if when.tzinfo else when.replace(tzinfo=timezone.utc)))
    return out


class VisitRecount:
    """Every stored visit figure, from visits handed over one at a time."""

    def __init__(self, own: set[str]) -> None:
        self.own = own
        self.visits = 0
        self.pages: Counter = Counter()
        self.trail: Counter = Counter()
        self.seconds: Counter = Counter()
        self.exits: Counter = Counter()
        self.steps: Counter = Counter()
        self.flags: Counter = Counter()
        self.page_visits: Counter = Counter()      # per page: visits seen on it
        self.journeys_pages = 0

    def _where(self, line) -> str:
        """The page on this site the request was made from, or ""."""
        if not line.referrer:
            return ""
        try:
            parts = urlsplit(line.referrer)
        except ValueError:
            return ""
        host = (parts.hostname or "").lower()
        own = self.own or ({line.host.lower()} if line.host else set())
        if not host or host not in own:
            return ""
        path = parts.path or "/"
        if _is_asset_path(path) or _is_beacon_path(path):
            return ""
        return path[:70]

    def visit(self, lines: list, is_page) -> None:
        """One visit's lines, oldest first. Ignored unless it loaded a page."""
        loaded = [l for l in lines if is_page(l)]
        if not loaded:
            return
        seen: list[str] = []
        moved = 0
        for l in lines:
            here = is_page(l)
            if seen and l.status[:1] in ("2", "3"):
                where = self._where(l)
                if where and where != seen[-1] and not (here and where == l.path[:70]):
                    seen.append(where)
                    moved += 1
            if here:
                seen.append(l.path[:70])
        self.visits += 1
        self.pages[str(len(loaded))] += 1
        self.trail[str(len(seen))] += 1
        span = int((lines[-1].when - lines[0].when).total_seconds())
        self.seconds[str(_bucket(max(0, span)))] += 1
        self.exits[seen[-1]] += 1
        self.page_visits.update(set(seen))
        for i in range(1, len(seen)):
            self.steps[f"{seen[i - 1]} → {seen[i]}"] += 1
        if any(l.status == "404" and not _is_asset_path(l.path) for l in lines):
            self.flags["not_found"] += 1
        if any(l.method == "POST" for l in lines):
            self.flags["posted"] += 1
        if moved:
            self.flags["in_app"] += 1
        self.journeys_pages += len(loaded)

    def figures(self) -> dict:
        return {"visits": self.visits, "pages": self.pages, "trail": self.trail,
                "seconds": self.seconds, "exits": self.exits, "steps": self.steps,
                "flags": self.flags, "page_visits": self.page_visits}


def _folded(name: str, stored: Counter, counted: Counter, same) -> None:
    """Each label the stored list kept, exactly, and its folded tail
    against what the recount has left over."""
    kept = [k for k in stored if k != OTHER]
    for k in sorted(kept):
        same(f"visits by {name}: {k}", stored[k], counted.get(k, 0))
    same(f"visits by {name}: {OTHER}", stored.get(OTHER, 0),
         sum(counted.values()) - sum(counted.get(k, 0) for k in kept))


def compare(stored: dict, ours: Counter | None, figures: dict, same) -> None:
    """Compare stored visit figures ({name: Counter}, as history or the
    snapshot holds them) and our own traffic by label with the recount."""
    got = figures["journeys"]
    same("visits", stored.get("visits", 0), got["visits"])
    for name in ("pages", "trail", "seconds", "flags"):
        want = Counter(stored.get(name) or {})
        for k in sorted(set(want) | set(got[name])):
            same(f"visits by {name}: {k}", want.get(k, 0), got[name].get(k, 0))
    for name in ("exits", "steps"):
        _folded(name, Counter(stored.get(name) or {}), got[name], same)
    if ours is not None:
        for k in sorted(set(ours) | set(figures["ours"])):
            same(f"our own traffic: {k}", ours.get(k, 0), figures["ours"].get(k, 0))


def compare_pages(pages: dict | None, got: dict, same) -> None:
    """The pages blob's per-page visits (in-app pages included) and exits,
    every page, against the recount's: the two halves of the exit rate."""
    pages = pages or {}
    for path in sorted(set(pages) | set(got["page_visits"]) | set(got["exits"])):
        row = pages.get(path) or {}
        same(f"page {path}: visits", int(row.get("visits", 0)), got["page_visits"].get(path, 0))
        same(f"page {path}: exits", int(row.get("exits", 0)), got["exits"].get(path, 0))


def from_counts(counts: dict[str, Counter]) -> dict:
    """History's visit figures for one day, from its counts rows."""
    kinds = {"pages": "visit_pages", "trail": "visit_trail", "seconds": "visit_seconds",
             "exits": "visit_exit", "steps": "visit_step", "flags": "visit_flag"}
    out = {name: counts.get(kind, Counter()) for name, kind in kinds.items()}
    out["visits"] = sum(out["pages"].values())
    return out
