"""robots.txt as a crawler reads it today (RFC 9309): may this crawler fetch this path?

robots.py keeps the site's robots.txt. This decides, for one crawler's token
and one path, the way RFC 9309 says and Google, OpenAI and Anthropic document
it - not Python's urllib.robotparser, which takes the first rule that
matches, so "Disallow: /" above "Allow: /blog/" would shut /blog/ out where
the crawlers let it in:

  groups      the lines are split at CR, LF or CR LF; a "#" starts a comment;
              a line is "name: value" (the name in any case). One or more
              User-agent lines open a group; its Allow and Disallow lines
              follow, and a User-agent line after one of them opens the next
              group. An Allow or Disallow with no value closes the User-agent
              lines but is no rule (an empty Disallow allows everything).
              Lines before the first User-agent and other names (Sitemap,
              Crawl-delay, ...) belong to no group
  the group   every group whose User-agent line names the token (any case;
              the part before a "/" and spaces), their rules together; when
              none does, every "*" group's; when there is none of those
              either, no rule: the crawler may fetch everything
  a rule      matches when the path starts with its pattern; "*" in a
              pattern stands for any characters, a "$" at its end for the end
              of the path
  the winner  the matching rule with the longest pattern; between an Allow
              and a Disallow of the same length, the Allow. No rule matches:
              allowed

Paths and patterns are compared after the same clean-up (RFC 9309 2.2.2):
a %xx that encodes a letter, digit or one of - . _ ~ is written out; any
other %xx gets capital hex digits; a character outside printable ASCII is
written as the %xx of its UTF-8 bytes.

webapp/js/robots-match.js is the same rule for the page's own use (any page
the reader opens); tests/test_ai_ready_js.py holds both to the same answers.
The independent reading is audit_ai_ready.py's, with regular expressions.
"""
from __future__ import annotations

UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
HEX = frozenset("0123456789abcdefABCDEF")


def clean(text: str) -> str:
    """The comparison form of a path or a pattern (module doc)."""
    out, i, s = [], 0, text or ""
    while i < len(s):
        c = s[i]
        two = s[i + 1:i + 3]
        if c == "%" and len(two) == 2 and two[0] in HEX and two[1] in HEX:
            ch = chr(int(two, 16))
            out.append(ch if ch in UNRESERVED else "%" + two.upper())
            i += 3
            continue
        if " " < c <= "~":
            out.append(c)
        else:
            # a lone surrogate (an undecodable byte) as U+FFFD, as a browser writes it
            ch = "\ufffd" if "\ud800" <= c <= "\udfff" else c
            out.extend(f"%{b:02X}" for b in ch.encode("utf-8"))
        i += 1
    return "".join(out)


def groups(text: str) -> list[dict]:
    """[{"agents": [value, ...], "rules": [[kind, pattern], ...]}] in the
    file's order (module doc)."""
    out, current, ruled = [], None, True
    lines = (text or "").lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        name, colon, value = line.partition(":")
        if not colon:
            continue
        name, value = name.strip().lower(), value.strip()
        if name == "user-agent":
            if ruled:
                current = {"agents": [], "rules": []}
                out.append(current)
                ruled = False
            current["agents"].append(value)
        elif name in ("allow", "disallow") and current is not None:
            ruled = True
            if value:
                current["rules"].append([name, value])
    return out


def _token(agent: str) -> str:
    return (agent or "").split("/", 1)[0].strip().lower()


def rules_for(groups: list[dict], token: str) -> dict:
    """{"agents": the User-agent values whose groups apply ([] none: no rule),
    "rules": [[kind, pattern], ...]} for a crawler's token, from groups();
    kind is "allow" or "disallow", in the file's order (the order decides
    nothing: the longest pattern does)."""
    want = (token or "").strip().lower()
    mine = [g for g in groups if any(_token(a) == want for a in g.get("agents") or [])]
    if not mine:
        mine = [g for g in groups if any(_token(a) == "*" for a in g.get("agents") or [])]
    agents, rules = [], []
    for g in mine:
        for a in g.get("agents") or []:
            if _token(a) in (want, "*") and a.strip() not in agents:
                agents.append(a.strip())
        rules += [list(r) for r in g.get("rules") or []]
    return {"agents": agents, "rules": rules}


def matches(pattern: str, path: str) -> bool:
    """Does a pattern match the path (both in their clean() form)?"""
    end = pattern.endswith("$")
    if end:
        pattern = pattern[:-1]
    parts = pattern.split("*")
    if not path.startswith(parts[0]):
        return False
    at = len(parts[0])
    if len(parts) == 1:
        return at == len(path) if end else True
    for part in parts[1:-1]:
        found = path.find(part, at)
        if found < 0:
            return False
        at = found + len(part)
    last = parts[-1]
    if end:
        return len(path) - len(last) >= at and path.endswith(last)
    return path.find(last, at) >= 0


def decide(rules: list, path: str) -> tuple[bool, list | None]:
    """(allowed, the rule that decided it or None) for one path."""
    target = clean(path or "/")
    best, size = None, -1
    for kind, pattern in rules:
        p = clean(pattern)
        if not p or not matches(p, target):
            continue
        if len(p) > size or (len(p) == size and kind == "allow" and best[0] == "disallow"):
            best, size = [kind, pattern], len(p)
    return (best is None or best[0] == "allow"), best
