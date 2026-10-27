"""An assistant's reads, not its requests: the day kind `ai_reads`.

An AI user fetcher (classify.AI_ASKED: ChatGPT-User, Claude-User,
Perplexity-User, Google-NotebookLM, ...) can ask for one page several times
and then for the page's own files. Google NotebookLM, when someone adds a
page as a source, asks for the page twice within about 3 seconds (a fetch
and a render), then its stylesheet and scripts with the page as referrer:
one read, four requests. Counting requests made one read look like four,
and showed a stylesheet as something "AI asked" for (COUNTING-TRAPS.md,
trap 21). The names and the window are in ai_read_names.py; each request
gets one role:

  file    a file the page loaded (ai_read_names: by extension, under a
          framework folder or the site's asset prefixes, a framework payload,
          or a same-site referrer naming a page the same assistant read in
          the last WINDOW_SECONDS); never "AI asked"
  read    an assistant's first request for a page (the page: no query, 70
          characters, a trailing "/" ignored), or its first after
          WINDOW_SECONDS since that read began
  repeat  the same assistant asking for the same page inside that window

A file "with its page" is one whose referrer names a page the same assistant
read in the window: it is folded under that read ("with 2 files"). Other
files (a favicon asked for alone) are still files, never reads.

The assistant is the fetcher's name (verdict.engine, as `engines` names it).
Lines are taken in time order (CLASSIFICATION.md, "Line order"). A read that
starts before midnight and repeats after it is a read on both days.

The blob (kind `ai_reads`; counted every day, whatever the settings):

  window_seconds   the window the day was counted with
  requests         every user-fetch request: the answer-engine group's
                   "asked" requests
  reads, repeats, files    the three roles; they add up to requests
  files_with_page  of the files, those folded under a read
  by_name          {name: the five figures}; the TOP names by requests, the
                   rest summed as "(all others)"; each figure adds up
  pages            {name: {path: {"reads", "files"}}} for each kept name: its
                   PAGES pages with most reads, the rest as "(all others)";
                   reads add up to the name's reads, files to its
                   files_with_page

The day kind `ai_fetches` carries each minute row's reads as its fifth
column (ai_fetches.py), so pages can be read per day. Second count:
audit_ai_reads.py, from the raw lines with its own code.
"""
from __future__ import annotations

from collections import Counter
from datetime import timezone
from urllib.parse import parse_qsl, urlsplit

from .ai_read_names import (DEFAULT_PREFIXES, FILE_EXTENSIONS, FILE_FOLDERS, FILE_QUERY,
                            WINDOW_SECONDS)
from .classify import Group, Tier

TOP = 20
PAGES = 10
OTHER = "(all others)"
FIELDS = ("requests", "reads", "repeats", "files", "files_with_page")
ROLE_FIELD = {"read": "reads", "repeat": "repeats", "file": "files"}
PRUNE_AT = 4096


def bare(path: str) -> str:
    """A path as it is shown: no query, no fragment, 70 characters."""
    return str(path or "").split("?", 1)[0].split("#", 1)[0][:70]


def page_of(path: str) -> str:
    """A page as reads compare it: bare(), a trailing "/" ignored."""
    return bare(path).rstrip("/") or "/"


def _host(host: str) -> str:
    low = str(host or "").lower().split(":", 1)[0].rstrip(".")
    return low[4:] if low.startswith("www.") else low


def is_file(path: str, url: str = "", prefixes=DEFAULT_PREFIXES) -> bool:
    """A file a page loads, by its own address (not by its referrer)."""
    raw = str(path or "").split("?", 1)[0].split("#", 1)[0]
    low = raw.lower()
    if low.rsplit("/", 1)[-1].endswith(FILE_EXTENSIONS) or low.startswith(FILE_FOLDERS):
        return True
    if any(raw.startswith(p) for p in prefixes):
        return True
    query = str(url or "").split("?", 1)[1] if "?" in str(url or "") else ""
    if query:
        try:
            keys = {k.lower() for k, _ in parse_qsl(query, keep_blank_values=True)}
        except ValueError:
            keys = set()
        if keys & set(FILE_QUERY):
            return True
    return False


def _seconds(when) -> float:
    return (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).timestamp()


class Roles:
    """Each user-fetch request's role, fed in time order."""

    def __init__(self, prefixes=DEFAULT_PREFIXES) -> None:
        self.prefixes = tuple(prefixes)
        self.open: dict[tuple[str, str], tuple[float, str]] = {}   # (name, page) -> (start, path)

    def _prune(self, now: float) -> None:
        if len(self.open) > PRUNE_AT:
            self.open = {k: v for k, v in self.open.items() if now - v[0] <= WINDOW_SECONDS}

    def _read_of(self, name: str, page: str, now: float) -> str | None:
        got = self.open.get((name, page))
        return got[1] if got is not None and now - got[0] <= WINDOW_SECONDS else None

    def __call__(self, name: str, path: str, url: str, referrer: str, host: str,
                 when) -> tuple[str, str]:
        """(role, page): "read", "repeat" or "file", and the path of the read
        it belongs to ("" for a file whose page is not known)."""
        now = _seconds(when)
        self._prune(now)
        page = page_of(path)
        of = ""
        ref = str(referrer or "").strip()
        if ref and ref != "-":
            try:
                parts = urlsplit(ref if "//" in ref else "//" + ref)
                ref_host, ref_path = _host(parts.hostname or ""), parts.path or "/"
            except ValueError:
                ref_host, ref_path = "", ""
            own = _host(host)
            if ref_host and (not own or ref_host == own) and page_of(ref_path) != page:
                of = self._read_of(name, page_of(ref_path), now) or ""
        if of or is_file(path, url, self.prefixes):
            return "file", of
        if self._read_of(name, page, now) is not None:
            return "repeat", self.open[(name, page)][1]
        self.open[(name, page)] = (now, bare(path))
        return "read", bare(path)


class Reads:
    """The tally pass's user fetches by role (extras.Extras offers it every hit)."""

    def __init__(self, prefixes=DEFAULT_PREFIXES) -> None:
        self.roles = Roles(prefixes)
        self.names: dict[str, Counter] = {}
        self.pages: dict[str, dict[str, Counter]] = {}

    def set_prefixes(self, prefixes) -> None:
        self.roles.prefixes = tuple(prefixes)

    def add(self, hit, verdict) -> str | None:
        """The request's role, or None when it is no user fetch."""
        if verdict.group is not Group.ANSWER_ENGINE or verdict.tier is not Tier.ASKED:
            return None
        name = verdict.engine or ""
        role, of = self.roles(name, hit.path, hit.url, hit.referrer, hit.host, hit.when)
        got = self.names.setdefault(name, Counter())
        got["requests"] += 1
        got[ROLE_FIELD[role]] += 1
        if role == "read":
            self.pages.setdefault(name, {}).setdefault(of, Counter())["reads"] += 1
        elif role == "file" and of:
            got["files_with_page"] += 1
            self.pages.setdefault(name, {}).setdefault(of, Counter())["files"] += 1
        return role

    def blob(self) -> dict:
        order = sorted(self.names, key=lambda k: (-self.names[k]["requests"], k))
        by_name = {k: {f: int(self.names[k][f]) for f in FIELDS} for k in order[:TOP]}
        rest: Counter = Counter()
        for k in order[TOP:]:
            rest.update(self.names[k])
        if rest:
            by_name[OTHER] = {f: int(rest[f]) for f in FIELDS}
        pages = {}
        for k in order[:TOP]:
            got = self.pages.get(k) or {}
            ranked = sorted(got, key=lambda p: (-got[p]["reads"], -got[p]["files"], p))
            out = {p: {"reads": int(got[p]["reads"]), "files": int(got[p]["files"])}
                   for p in ranked[:PAGES]}
            tail: Counter = Counter()
            for p in ranked[PAGES:]:
                tail.update(got[p])
            if tail:
                out[OTHER] = {"reads": int(tail["reads"]), "files": int(tail["files"])}
            if out:
                pages[k] = out
        total = {f: int(sum(c[f] for c in self.names.values())) for f in FIELDS}
        return {"window_seconds": WINDOW_SECONDS, **total, "by_name": by_name, "pages": pages}


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    got = getattr(extras, "ai_reads", None)
    return got.blob() if got is not None else None


def check(totals, blob, differs, problems) -> None:
    from .verify import Problem
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    requests = int(blob.get("requests", 0))
    differs("ai_reads: user-fetch requests", requests,
            int(engines.tiers.get("asked", 0)) if engines else 0, "asked fetches")
    differs("ai_reads: reads, repeats and files",
            sum(int(blob.get(k, 0)) for k in ("reads", "repeats", "files")), requests, "requests")
    if int(blob.get("files_with_page", 0)) > int(blob.get("files", 0)):
        problems.append(Problem("ai_reads", "more files with their page than files"))
    by_name = blob.get("by_name") or {}
    for field in FIELDS:
        differs(f"ai_reads: {field} by name", sum(int(v.get(field, 0)) for v in by_name.values()),
                int(blob.get(field, 0)), field)
    for name, pages in (blob.get("pages") or {}).items():
        kept = by_name.get(name)
        if kept is None or name == OTHER:
            problems.append(Problem(f"ai_reads: {name}", "pages for a name that is not kept"))
            continue
        differs(f"ai_reads: {name} reads by page",
                sum(int(v.get("reads", 0)) for v in pages.values()), int(kept["reads"]), "reads")
        differs(f"ai_reads: {name} files by page",
                sum(int(v.get("files", 0)) for v in pages.values()),
                int(kept["files_with_page"]), "files with their page")
    fetches = (getattr(totals, "extras", None) or {}).get("ai_fetches")
    rows = (fetches or {}).get("rows")
    if rows is not None and all(len(r) > 4 for r in rows):
        differs("ai_reads: reads by minute (ai_fetches)", sum(int(r[4]) for r in rows),
                int(blob.get("reads", 0)), "reads")
