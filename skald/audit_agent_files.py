"""The second count of files made for machines (day kind `agent_files`).

Registered in audit_more.RECOUNTS. Written apart from agent_files.py: it
shares only the name lists there (KINDS, WHO, the Markdown endings, the
llms.txt names, the OKF segment, the /.well-known/ names) and classify.py's
names through the audit's judge. Its own reading of a line:

  the path     the URL cut at the first "?", its first 200 characters as
               written, and " (<kind>)" after a path that was longer; the kind is read from it cut at "#" too, with its
               letters A-Z made small and every closing "/" taken off
  the kind     llms.txt names (last segment) first, then exactly
               /robots.txt, then sitemap*.xml(.gz), then /.well-known/<name>,
               then a Markdown ending: "okf" when a folder on the way is
               named okf, "markdown" otherwise
  who          the audit's group; an answer engine by the name the judge
               gave it, "ai_asked" when classify.AI_ASKED matches the name
  the name     audit_crawler_cost's name for the machine groups, "People"

Compared: every kind's requests, status classes and who; each who's kept
names kind by kind, the rest against its fold; every kept file's kind,
statuses, who, names (its kept ones, the rest against its fold) and last
request; and per kind, the files beyond the kept ones and their requests.
"""
from __future__ import annotations

from collections import Counter
from datetime import timezone

from .agent_files import (KINDS, LLMS_NAMES, MARKDOWN_ENDS, OKF_SEGMENT, PEOPLE, WELL_KNOWN,
                          WHO)
from .audit_crawler_cost import _name
from .classify import AI_ASKED

REST = "(all others)"
CHARS = 200


def _small(text: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def kind_of(url: str) -> str | None:
    path = url.partition("?")[0].partition("#")[0]
    bare = _small(path)
    while bare.endswith("/"):
        bare = bare[:-1]
    folders = bare.split("/")
    name = folders.pop() if folders else ""
    if name == LLMS_NAMES[0] or name == LLMS_NAMES[1]:
        return "llms_txt"
    if bare == "/robots.txt":
        return "robots_txt"
    if name[:7] == "sitemap" and (name[-4:] == ".xml" or name[-7:] == ".xml.gz"):
        return "sitemap"
    if len(folders) >= 2 and folders[1] == ".well-known":
        nxt = folders[2] if len(folders) > 2 else name
        if nxt in WELL_KNOWN:
            return "agent_card"
    for end in MARKDOWN_ENDS:
        if bare[-len(end):] == end:
            return "okf" if OKF_SEGMENT in folders else "markdown"
    return None


def _who(group: str, info: dict, line) -> str | None:
    if group == "answer_engines":
        name = info.get("name") or ""
        if not name:
            found = AI_ASKED.search(line.agent or "")
            name = found.group(0) if found else ""
        return "ai_asked" if name and AI_ASKED.search(name) else "ai_training"
    return {"search_engines": "search_engines", "bots": "bots", "people": "people"}.get(group)


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.kinds: dict[str, dict[str, Counter]] = {}
        self.names: dict[str, dict[str, Counter]] = {}
        self.files: dict[str, dict] = {}

    def judged(self, line, group, info) -> None:
        kind = kind_of(line.url)
        if kind is None:
            return
        who = _who(group, info or {}, line)
        if who is None:
            return
        name = PEOPLE if who == "people" else _name(line, group, info or {})
        code = str(line.status)
        k = self.kinds.setdefault(kind, {"status": Counter(), "who": Counter()})
        k["status"][code[:1] + "xx"] += 1
        k["who"][who] += 1
        self.names.setdefault(who, {}).setdefault(name, Counter())[kind] += 1
        whole = line.url.partition("?")[0]
        path = whole if len(whole) <= CHARS else f"{whole[:CHARS]} ({kind})"
        f = self.files.setdefault(path, {"kind": kind, "status": Counter(), "who": Counter(),
                                         "names": Counter(), "last": ""})
        f["status"][code] += 1
        f["who"][who] += 1
        f["names"][name] += 1
        t = line.when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if t > f["last"]:
            f["last"] = t

    def visit(self, lines, is_page, labels) -> None:
        return

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("agent_files")
        if blob is None:
            return
        kept = blob.get("kinds") or {}
        for kind in KINDS:
            was, mine = kept.get(kind) or {}, self.kinds.get(kind) or {}
            n = sum((mine.get("who") or Counter()).values())
            same(f"agent_files {kind}: requests", int(was.get("requests") or 0), n)
            for part in ("status", "who"):
                got = {k: int(v) for k, v in (was.get(part) or {}).items()}
                now = mine.get(part) or Counter()
                for key in sorted(set(got) | set(now)):
                    same(f"agent_files {kind} {part}: {key}", got.get(key, 0), now[key])
        names = blob.get("names") or {}
        for who in WHO:
            kept_names = names.get(who) or {}
            mine_by: dict[str, Counter] = {}
            for name, c in (self.names.get(who) or {}).items():
                key = name if name in kept_names and name != REST else REST
                mine_by.setdefault(key, Counter()).update(c)
            for name in sorted(set(kept_names) | set(mine_by)):
                got = {k: int(v) for k, v in (kept_names.get(name) or {}).items()}
                now = mine_by.get(name) or Counter()
                for kind in sorted(set(got) | set(now)):
                    same(f"agent_files {who} {name}: {kind}", got.get(kind, 0), now[kind])
        files = blob.get("files") or {}
        rest: dict[str, Counter] = {}
        for path, f in self.files.items():
            if path in files:
                continue
            r = rest.setdefault(f["kind"], Counter())
            r["files"] += 1
            r["requests"] += sum(f["status"].values())
        for path in sorted(files):
            was, mine = files[path], self.files.get(path)
            if mine is None:
                problems.append(f"agent_files: {path} kept, but the recount finds no request for it")
                continue
            if was.get("kind") != mine["kind"]:
                problems.append(f"agent_files: {path} kept as {was.get('kind')}, the recount reads {mine['kind']}")
            same(f"agent_files {path}: requests", int(was.get("requests") or 0), sum(mine["status"].values()))
            for part in ("status", "who"):
                got = {k: int(v) for k, v in (was.get(part) or {}).items()}
                for key in sorted(set(got) | set(mine[part])):
                    same(f"agent_files {path} {part}: {key}", got.get(key, 0), mine[part][key])
            got = {k: int(v) for k, v in (was.get("names") or {}).items()}
            now: Counter = Counter()
            for name, v in mine["names"].items():
                now[name if name in got and name != REST else REST] += v
            for key in sorted(set(got) | set(now)):
                same(f"agent_files {path} name: {key}", got.get(key, 0), now[key])
            if was.get("last") != mine["last"]:
                problems.append(f"agent_files: {path} last fetched {was.get('last')}, "
                                f"the recount finds {mine['last']}")
        kept_rest = blob.get("rest") or {}
        for kind in sorted(set(kept_rest) | set(rest)):
            got, now = kept_rest.get(kind) or {}, rest.get(kind) or Counter()
            for part in ("files", "requests"):
                same(f"agent_files {kind} beyond the kept files: {part}", int(got.get(part) or 0), now[part])
