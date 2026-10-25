"""The second count of what AI got back, by address (day kind `ai_status`).

Registered in audit_more.RECOUNTS. Written apart from ai_status.py: it
shares only the name lists (the not-a-page list's Markdown endings,
not_pages.RULES, and classify.py's names through the audit's judge) and the
documented threshold:

  a request     a line the audit put in "answer_engines" with a tier and a
                crawler name
  the path      the URL cut at the first "?", first 200 characters
  a copy        the path, with every trailing "/" taken off and its letters
                A-Z made small, ends with one of the Markdown endings
  listed        a copy, or any status but 200 and 304 (as the line writes it)
  slow          the line's seconds, in whole milliseconds (rounded), 1,000
                or more; timed: the line has seconds at all

Every path the stored day kept is compared status by status and name by
name; its folded "(all others)" against what the recount has beyond the kept
paths; then each name's unlisted requests and timed lines.
"""
from __future__ import annotations

from collections import Counter

from .not_pages import RULES

SLOW = 1000
REST = "(all others)"
_ENDS = tuple(RULES["markdown"][1]["ends"])


def _small(text: str) -> str:
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)


def copy_path(path: str) -> bool:
    bare = path
    while bare.endswith("/"):
        bare = bare[:-1]
    return any(_small(bare).endswith(e) for e in _ENDS)


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.listed: dict[tuple, Counter] = {}     # (path, name) -> {status: n}
        self.slow: Counter = Counter()             # (path, name) -> n
        self.plain: Counter = Counter()            # name -> n
        self.timed: Counter = Counter()            # name -> n

    def hit(self, line, group, tier, name) -> None:
        if group != "answer_engines" or not tier or not name:
            return
        path = line.url.partition("?")[0][:200]
        code = str(line.status)
        if copy_path(path) or code not in ("200", "304"):
            self.listed.setdefault((path, name), Counter())[code] += 1
        else:
            self.plain[name] += 1
        if line.seconds is not None:
            self.timed[name] += 1
            if int(round(line.seconds * 1000)) >= SLOW:
                self.slow[(path, name)] += 1

    def visit(self, lines, is_page, labels) -> None:
        return

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("ai_status")
        if blob is None:
            return
        if int(blob.get("slow_ms") or 0) != SLOW:
            problems.append("ai_status: stored with another slow threshold")
        kept = blob.get("answers") or {}
        mine_by: dict[str, dict[str, Counter]] = {}
        for (path, name), codes in self.listed.items():
            key = path if path in kept and path != REST else REST
            mine_by.setdefault(key, {}).setdefault(name, Counter()).update(codes)
        for path in sorted(set(kept) | set(mine_by)):
            names, mine = kept.get(path) or {}, mine_by.get(path) or {}
            for name in sorted(set(names) | set(mine)):
                was = {k: int(v) for k, v in (names.get(name) or {}).items()}
                now = mine.get(name, Counter())
                for code in sorted(set(was) | set(now)):
                    same(f"ai_status {path}: {name} {code}", was.get(code, 0), now[code])
        slow_kept = blob.get("slow") or {}
        slow_by: dict[str, Counter] = {}
        for (path, name), n in self.slow.items():
            key = path if path in slow_kept and path != REST else REST
            slow_by.setdefault(key, Counter())[name] += n
        for path in sorted(set(slow_kept) | set(slow_by)):
            got = {k: int(v) for k, v in (slow_kept.get(path) or {}).items()}
            mine = slow_by.get(path) or Counter()
            for name in sorted(set(got) | set(mine)):
                same(f"ai_status slow {path}: {name}", got.get(name, 0), mine[name])
        for part, mine in (("plain", self.plain), ("timed", self.timed)):
            got = {k: int(v) for k, v in (blob.get(part) or {}).items()}
            for name in sorted(set(got) | set(mine)):
                same(f"ai_status {part}: {name}", got.get(name, 0), mine[name])
