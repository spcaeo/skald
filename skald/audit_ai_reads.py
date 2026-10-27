"""The second count of an assistant's reads (day kind `ai_reads`, and the
reads column of the day kind `ai_fetches`).

Registered in audit_more.RECOUNTS. It keeps every line the audit put in
"answer_engines" with tier "asked" (`hit`), in time order, and at the end
gives each one a role with its own code, written apart from ai_reads.py.
It shares only the names and the window of ai_read_names.py and the owner
list classify.AI_FETCHER_OWNERS:

  the page      the line's path cut at "?" and "#", 70 characters; compared
                with every trailing "/" taken off ("/" stays "/")
  a file        the path's last segment ends in a FILE_EXTENSIONS name, the
                path starts with a FILE_FOLDERS folder or one of the site's
                asset prefixes (the config's site.asset_prefixes, else
                DEFAULT_PREFIXES), or a FILE_QUERY name is a key of its query
                string; or its referrer's host (without "www." and the port)
                is the line's own host (or the line has none) and the
                referrer's page is another page this assistant (the audit's
                crawler name) began reading at most the window before
  a repeat      the same assistant, the same page, at most the window after
                its read began
  a read        any other line: a read begins

The window is the stored day's `window_seconds` (else WINDOW_SECONDS), so a
day keeps the window it was counted with. Compared: the five totals, each
kept name's (and the folded "(all others)"), each kept name's pages (and
its folded tail), and each ai_fetches row's reads by minute (UTC),
assistant (its owner) and path.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit

from .ai_read_names import (DEFAULT_PREFIXES, FILE_EXTENSIONS, FILE_FOLDERS, FILE_QUERY,
                            WINDOW_SECONDS)
from .classify import AI_FETCHER_OWNERS

REST = "(all others)"
NAMES = ("requests", "reads", "repeats", "files", "files_with_page")


def _cut(path: str) -> str:
    return (path or "").split("#")[0].split("?")[0]


def _shown(path: str) -> str:
    return _cut(path)[:70]


def _same(path: str) -> str:
    got = _shown(path)
    while len(got) > 1 and got.endswith("/"):
        got = got[:-1]
    return got or "/"


def _site(host: str) -> str:
    got = (host or "").lower().partition(":")[0].rstrip(".")
    return got[len("www."):] if got.startswith("www.") else got


def prefixes_of(config) -> tuple:
    raw = ((config or {}).get("site") or {}).get("asset_prefixes")
    if raw is None:
        return DEFAULT_PREFIXES
    items = raw.split() if isinstance(raw, str) else list(raw)
    return tuple(str(x) for x in items if str(x).startswith("/"))


def _seconds(when: datetime) -> float:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.timestamp()


def _file(line, prefixes) -> bool:
    path = _cut(line.path)
    low = path.lower()
    last = low.split("/")[-1]
    if any(last.endswith(ext) for ext in FILE_EXTENSIONS):
        return True
    if any(low.startswith(f) for f in FILE_FOLDERS):
        return True
    if any(path.startswith(p) for p in prefixes):
        return True
    url = line.url or ""
    if "?" in url:
        try:
            keys = [k.lower() for k, _ in parse_qsl(url.split("?", 1)[1], keep_blank_values=True)]
        except ValueError:
            keys = []
        if any(k in FILE_QUERY for k in keys):
            return True
    return False


def roles(pairs, window: int, prefixes) -> list:
    """[(line, name, role, page of the read or "")] for the (line, name)
    pairs, in their (time) order. audit_ai_likely reads them too."""
    began: dict = {}                          # (name, page) -> (seconds, shown path)
    out = []
    for line, name in pairs:
        now = _seconds(line.when)
        page = _same(line.path)
        of = ""
        ref = (line.referrer or "").strip()
        if ref and ref != "-":
            try:
                split = urlsplit(ref if "//" in ref else "//" + ref)
                host, rpath = _site(split.hostname or ""), split.path or "/"
            except ValueError:
                host, rpath = "", ""
            mine = _site(line.host)
            if host and (mine == "" or host == mine) and _same(rpath) != page:
                got = began.get((name, _same(rpath)))
                if got is not None and now - got[0] <= window:
                    of = got[1]
        if of or _file(line, prefixes):
            out.append((line, name, "file", of))
            continue
        got = began.get((name, page))
        if got is not None and now - got[0] <= window:
            out.append((line, name, "repeat", got[1]))
            continue
        began[(name, page)] = (now, _shown(line.path))
        out.append((line, name, "read", _shown(line.path)))
    return out


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.prefixes = prefixes_of(config)
        self.lines: list = []                     # (line, name)

    def hit(self, line, group, tier, name) -> None:
        if group == "answer_engines" and tier == "asked":
            self.lines.append((line, name))

    def visit(self, lines, is_page, labels) -> None:
        return None

    def roles(self, window: int) -> list:
        return roles(self.lines, window, self.prefixes)

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("ai_reads")
        rows = (stored.get("ai_fetches") or {}).get("rows")
        whole = rows is not None and all(len(r) >= 5 for r in rows)
        if blob is None and not whole:
            return
        window = int((blob or {}).get("window_seconds", WINDOW_SECONDS))
        roles = self.roles(window)
        if whole:
            kept = Counter()
            for r in rows:
                kept[(str(r[0]), str(r[1]), str(r[2]))] += int(r[4])
            counted = Counter()
            for line, name, role, _ in roles:
                if role != "read":
                    continue
                stamp = datetime.fromtimestamp(int(_seconds(line.when)) // 60 * 60, timezone.utc)
                who = AI_FETCHER_OWNERS.get(name.lower(), name.lower())
                counted[(stamp.strftime("%Y-%m-%dT%H:%M"), who, line.path[:70])] += 1
            for key in sorted(set(kept) | set(counted)):
                if kept[key] or counted[key]:
                    same(f"ai_fetches: reads by {key[1]} of {key[2]} at {key[0]}",
                         kept[key], counted[key])
        if blob is not None:
            self._compare_blob(blob, roles, same)

    def _compare_blob(self, blob, roles, same) -> None:
        names: dict = {}
        pages: dict = {}
        field = {"read": "reads", "repeat": "repeats", "file": "files"}
        for _, name, role, of in roles:
            c = names.setdefault(name, Counter())
            c["requests"] += 1
            c[field[role]] += 1
            if role == "read":
                pages.setdefault(name, {}).setdefault(of, Counter())["reads"] += 1
            elif role == "file" and of:
                c["files_with_page"] += 1
                pages.setdefault(name, {}).setdefault(of, Counter())["files"] += 1
        for key in NAMES:
            same(f"ai_reads: {key}", int(blob.get(key, 0)),
                 sum(c[key] for c in names.values()))
        stored = blob.get("by_name") or {}
        rest = Counter()
        for name, c in names.items():
            if name not in stored or name == REST:
                rest.update(c)
        for name in sorted(stored):
            now = rest if name == REST else names.get(name, Counter())
            for key in NAMES:
                same(f"ai_reads: {name} {key}", int((stored[name] or {}).get(key, 0)), now[key])
        if REST not in stored:
            for key in NAMES:
                if rest[key]:
                    same(f"ai_reads: {REST} {key}", 0, rest[key])
        kept_pages = blob.get("pages") or {}
        for name in sorted(n for n in stored if n != REST):
            was = kept_pages.get(name) or {}
            mine = pages.get(name) or {}
            listed = Counter()
            for path in sorted(p for p in was if p != REST):
                for key in ("reads", "files"):
                    got = (mine.get(path) or Counter())[key]
                    listed[key] += got
                    same(f"ai_reads: {name} {key} of {path}", int(was[path].get(key, 0)), got)
            for key in ("reads", "files"):
                total = sum(c[key] for c in mine.values())
                same(f"ai_reads: {name} {key} of {REST}",
                     int((was.get(REST) or {}).get(key, 0)), total - listed[key])
