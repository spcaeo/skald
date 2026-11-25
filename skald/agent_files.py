"""Files made for machines, and who fetched them: the day kind `agent_files`
and agent_files.json (Traffic > Agent files, SKALD-56).

A site may publish files written for AI agents and tools rather than for
people: a Markdown copy of each page (linked from the page's head as
<link rel="alternate" type="text/markdown">), an OKF bundle (Open Knowledge
Format: a folder of Markdown files, /okf/index.md), /llms.txt, agent cards
under /.well-known/. This counts every request for one, from every group but
our own (ai_formats.py counts only the answer engines' fetches, as one number
per tier). Only the path decides (query string left out, letters A-Z made
small, trailing "/" taken off); the status does not, so a 404 for /llms.txt
is still a request for llms.txt, and the asking is the point:

  okf          a Markdown file (MARKDOWN_ENDS) with a path segment "okf"
  markdown     any other path whose last segment ends with MARKDOWN_ENDS
  llms_txt     a last segment named llms.txt or llms-full.txt (LLMS_NAMES),
               at the root or below it
  agent_card   /.well-known/<name> or /.well-known/<name>/..., name in
               WELL_KNOWN: A2A agent cards, MCP server cards, ai-plugin.json,
               ai-catalog.json
  robots_txt   /robots.txt
  sitemap      a last segment sitemap*.xml or sitemap*.xml.gz

Who, by the verdict (WHO): "ai_asked" and "ai_training" (an answer engine by
its tier), "search_engines", "bots", "people"; our own requests are never
counted. Each request is filed under a name: crawler_cost.name_of for the
machine groups (the classifier's name, the bots list's short name, scanner
probes), PEOPLE for people.

The blob, for a day (or today so far), whole site only:

  kinds   {kind: {"requests", "status": {"2xx".."5xx": n}, "who": {who: n}}}
          for the kinds with a request
  names   {who: {name: {kind: n}}}: each who's TOP names by requests (ties
          by name), the rest folded into one OTHER entry; `folded` says how
          many names each fold holds
  files   {path: {"kind", "requests", "status": {code: n} (as the log writes
          it), "who": {who: n}, "names": {name: n} (its NAMES busiest names
          and OTHER), "last": its latest request, UTC, "YYYY-MM-DDTHH:MM:SSZ"}}
          for the KEEP paths with most requests (ties by path); a path is
          the request's path cut to 200 characters, its case kept, and a
          cut one ends with " (<kind>)" (file_key)
  rest    {kind: {"files", "requests"}}: the paths beyond KEEP, by kind
  folded  {"names": {who: n}, "files": n}

Every sum holds (check): per kind, `who` and `status` add up to requests;
the kind's files plus its rest are its requests; per who, its names over
the kinds are what the kinds give that who; per file, status, who and names
add up to its requests; and no group has more agent-file requests than
requests. The second count is audit_agent_files.py, from the raw lines with
its own path rule (it shares only the name lists below).
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta, timezone

from .classify import Group
from .not_pages import RULES

# ---------------------------------------------------- the name lists
# (shared with audit_agent_files.py; nothing else is)

KINDS = ("markdown", "okf", "llms_txt", "agent_card", "robots_txt", "sitemap")
WHO = ("ai_asked", "ai_training", "search_engines", "bots", "people")
MARKDOWN_ENDS = tuple(RULES["markdown"][1]["ends"])          # .md, .mdx, .markdown
LLMS_NAMES = ("llms.txt", "llms-full.txt")
OKF_SEGMENT = "okf"
# /.well-known/ names agents read: A2A agent cards (new and old names), MCP
# server cards (both proposed places), the old plugin manifest, AI catalogs.
WELL_KNOWN = ("agent-card.json", "agent.json", "agents.json", "mcp", "mcp.json",
              "ai-plugin.json", "ai-catalog.json")
PEOPLE = "People"

KEEP = 50
TOP = 20
NAMES = 5
OTHER = "(all others)"
PATH_CHARS = 200
DETAIL_DAYS = 30


_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def kind_of(path: str) -> str | None:
    """One of KINDS for a request's path, or None: not a file for machines."""
    low = (path or "").split("?", 1)[0].split("#", 1)[0].translate(_ASCII_LOWER)
    bare = low.rstrip("/")
    parts = bare.split("/")
    last = parts[-1] if parts else ""
    if last in LLMS_NAMES:
        return "llms_txt"
    if bare == "/robots.txt":
        return "robots_txt"
    if last.startswith("sitemap") and (last.endswith(".xml") or last.endswith(".xml.gz")):
        return "sitemap"
    if len(parts) > 2 and parts[1] == ".well-known" and parts[2] in WELL_KNOWN:
        return "agent_card"
    if bare.endswith(MARKDOWN_ENDS):
        return "okf" if OKF_SEGMENT in parts[:-1] else "markdown"
    return None


def who_of(verdict) -> str | None:
    """One of WHO for a verdict, or None (our own requests)."""
    g = verdict.group
    if g is Group.ANSWER_ENGINE:
        return "ai_asked" if verdict.tier is not None and verdict.tier.value == "asked" else "ai_training"
    if g is Group.SEARCH_ENGINE:
        return "search_engines"
    if g is Group.BOTS:
        return "bots"
    if g is Group.PEOPLE:
        return "people"
    return None


def file_key(path: str, kind: str) -> str:
    """A file's key in `files`: the path, its first PATH_CHARS characters; a path cut there
    ends with " (<kind>)", so two long paths that start alike but are of another kind
    (/<200 x a>/llms.txt and /<200 x a>/x.md) stay two files, and every kind's files still
    add up to its requests: one visitor could otherwise withhold the day (review of SKALD-56)."""
    return path if len(path) <= PATH_CHARS else f"{path[:PATH_CHARS]} ({kind})"


def stamp(when) -> str:
    """A time as the blob keeps it: UTC, to the second, with Z."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _File:
    __slots__ = ("kind", "status", "who", "names", "last")

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.status: Counter = Counter()
        self.who: Counter = Counter()
        self.names: Counter = Counter()
        self.last: str | None = None


class Collector:
    """Fed every counted hit by extras.Extras (the whole site's tally only)."""

    def __init__(self) -> None:
        self.kinds: dict[str, dict] = {}
        self.names: dict[str, dict[str, Counter]] = {}
        self.files: dict[str, _File] = {}

    def add(self, hit, verdict) -> None:
        kind = kind_of(hit.path)
        if kind is None:
            return
        who = who_of(verdict)
        if who is None:
            return
        from .crawler_cost import name_of
        name = PEOPLE if who == "people" else name_of(hit, verdict)
        k = self.kinds.setdefault(kind, {"requests": 0, "status": Counter(), "who": Counter()})
        k["requests"] += 1
        k["status"][f"{str(hit.status)[:1]}xx"] += 1
        k["who"][who] += 1
        self.names.setdefault(who, {}).setdefault(name, Counter())[kind] += 1
        path = file_key(hit.path, kind)
        f = self.files.get(path)
        if f is None:
            f = self.files[path] = _File(kind)
        f.status[str(hit.status)] += 1
        f.who[who] += 1
        f.names[name] += 1
        t = stamp(hit.when)
        if f.last is None or t > f.last:
            f.last = t

    def finish(self) -> dict:
        kinds = {k: {"requests": v["requests"], "status": dict(sorted(v["status"].items())),
                     "who": dict(sorted(v["who"].items()))}
                 for k, v in sorted(self.kinds.items(), key=lambda kv: KINDS.index(kv[0]))}
        names, folded_names = {}, {}
        for who in WHO:
            per = self.names.get(who)
            if not per:
                continue
            ranked = sorted(per, key=lambda n: (-sum(per[n].values()), n))
            out = {n: dict(sorted(per[n].items())) for n in ranked[:TOP]}
            rest = ranked[TOP:]
            if rest:
                fold: Counter = Counter()
                for n in rest:
                    fold.update(per[n])
                out[OTHER] = dict(sorted(fold.items()))
            names[who] = out
            folded_names[who] = len(rest)
        ranked = sorted(self.files, key=lambda p: (-sum(self.files[p].status.values()), p))
        files = {}
        for p in sorted(ranked[:KEEP]):
            f = self.files[p]
            files[p] = {"kind": f.kind, "requests": sum(f.status.values()),
                        "status": dict(sorted(f.status.items())), "who": dict(sorted(f.who.items())),
                        "names": _top(f.names, NAMES), "last": f.last}
        rest: dict[str, dict] = {}
        for p in ranked[KEEP:]:
            f = self.files[p]
            r = rest.setdefault(f.kind, {"files": 0, "requests": 0})
            r["files"] += 1
            r["requests"] += sum(f.status.values())
        return {"keep": KEEP, "top": TOP, "kinds": kinds, "names": names, "files": files,
                "rest": rest, "folded": {"names": folded_names, "files": len(ranked[KEEP:])}}


def _top(counter: Counter, keep: int) -> dict:
    ranked = sorted(counter, key=lambda n: (-counter[n], n))
    out = {n: counter[n] for n in ranked[:keep]}
    rest = sum(counter[n] for n in ranked[keep:])
    if rest:
        out[OTHER] = rest
    return out


# ---------------------------------------------------- day_more registry

def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    got = getattr(extras, "agent_files", None)
    return None if got is None else got.finish()


def check(totals, blob, differs, problems) -> None:
    """Every sum the module docstring promises."""
    from .verify import Problem
    kinds = blob.get("kinds") or {}
    by_who: dict[str, Counter] = {}
    for kind, k in kinds.items():
        n = int(k.get("requests") or 0)
        differs(f"agent_files: {kind} by who", sum(int(v) for v in (k.get("who") or {}).values()),
                n, f"{kind} requests")
        differs(f"agent_files: {kind} by status", sum(int(v) for v in (k.get("status") or {}).values()),
                n, f"{kind} requests")
        for who, v in (k.get("who") or {}).items():
            by_who.setdefault(who, Counter())[kind] += int(v)
    files_by_kind: Counter = Counter()
    for path, f in (blob.get("files") or {}).items():
        n = int(f.get("requests") or 0)
        files_by_kind[f.get("kind")] += n
        for part in ("status", "who", "names"):
            differs(f"agent_files: {path} by {part}",
                    sum(int(v) for v in (f.get(part) or {}).values()), n, f"{path}'s requests")
    for kind, r in (blob.get("rest") or {}).items():
        files_by_kind[kind] += int(r.get("requests") or 0)
    for kind in sorted(set(kinds) | set(files_by_kind)):
        differs(f"agent_files: {kind} by file", files_by_kind[kind],
                int((kinds.get(kind) or {}).get("requests") or 0), f"{kind} requests")
    names = blob.get("names") or {}
    for who in sorted(set(names) | set(by_who)):
        mine: Counter = Counter()
        for per in (names.get(who) or {}).values():
            mine.update({k: int(v) for k, v in per.items()})
        want = by_who.get(who, Counter())
        for kind in sorted(set(mine) | set(want)):
            differs(f"agent_files: {who}'s names, {kind}", mine[kind], want[kind],
                    f"{who}'s {kind} requests")
    group_of = {"ai_asked": Group.ANSWER_ENGINE, "ai_training": Group.ANSWER_ENGINE,
                "search_engines": Group.SEARCH_ENGINE, "bots": Group.BOTS, "people": Group.PEOPLE}
    per_group: Counter = Counter()
    for who, c in by_who.items():
        per_group[group_of.get(who)] += sum(c.values())
    for g, n in per_group.items():
        stats = totals.groups.get(g) if g is not None else None
        if g is None or n > (stats.hits if stats else 0):
            problems.append(Problem("agent_files", f"{getattr(g, 'value', g)}: {n:,} agent-file "
                                    "requests, more than the group's requests"))
    folded = blob.get("folded") or {}
    for who, per in names.items():
        if (OTHER in per) != (int((folded.get("names") or {}).get(who) or 0) > 0):
            problems.append(Problem("agent_files", f"{who}: a fold without folded names, or the reverse"))
    if bool(blob.get("rest")) != (int(folded.get("files") or 0) > 0):
        problems.append(Problem("agent_files", "files: a rest without folded paths, or the reverse"))


# ---------------------------------------------------- agent_files.json

def _compact(blob: dict | None, detail: bool) -> dict | None:
    if blob is None:
        return None
    out = {"kinds": blob.get("kinds") or {}, "names": blob.get("names") or {}}
    if detail:
        out["files"] = blob.get("files") or {}
        out["rest"] = blob.get("rest") or {}
    return out


def build(p) -> dict:
    """agent_files.json: per day (180 days) each kind's figures and who
    fetched them, with the files for the last DETAIL_DAYS days and today."""
    if p.view is not None:
        return {"whole_site_only": True}
    blobs = p.history.extras(p.key, p.first, p.anchor, ("agent_files",))
    since = (p.anchor - timedelta(days=DETAIL_DAYS - 1)).isoformat()
    days = []
    for e in p.daily:
        row = p.day_entry(e)
        if p.has_figures(e):
            d = e["day"].isoformat()
            row["files"] = _compact((blobs.get(d) or {}).get("agent_files"), d >= since)
        days.append(row)
    today = p.today_block()
    if today is not None and p.live_ok:
        today["day"] = p.today.isoformat()
        today["files"] = _compact((p.snap.get("extras") or {}).get("agent_files"), True)
    return {"days": days, "today": today, "detail_days": DETAIL_DAYS, "keep": KEEP, "top": TOP,
            "kinds": list(KINDS), "who": list(WHO)}
