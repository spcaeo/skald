"""The second count of what each crawler costs (day kind `crawler_cost`).

Registered in audit_more.RECOUNTS. It sees every line the audit judged,
with what the judge found (`judged`: audit.Judge.info), and rebuilds each
name's figures with its own code, written apart from crawler_cost.py:

  the name      answer engines and search crawlers: the name the judge
                matched in classify.py's lists. Bots: "claims to be <name>"
                for a spoof, the link-preview prefix and app for a preview,
                classify's names for a visit that never rendered and for a
                browser-like crawler session, "(scanner probes)" for a probe,
                else the short name read from the user agent here (below)
  bytes         the sum of audit.Line.size over the lines that have one, and
                how many do; None when none does
  times         audit.Line.seconds in whole milliseconds (rounded), their
                sum and count, and the 90th percentile by counting up the
                sorted times until nine tenths of them are covered
  status        the first digit of the status and "xx"
  paths         the URL cut at "?", first 200 characters: how many distinct,
                and per path how many
  countries     the line's country (cc= or the GeoIP file), "Unknown" for none
  agents        the user-agent string, first 200 characters; for a probe,
                a preview, a crawler session, a never-rendered visit or a
                browser-like short name none may be kept (it may be a person's)
  last          the latest line's time, UTC, to the second

Every name the stored day kept is compared figure by figure; its folded
"(all others)" rows (per group, and inside each list) against what the
recount has beyond the names and labels kept. Only classify.py's name
strings are shared.
"""
from __future__ import annotations

from collections import Counter
from datetime import timezone

from .classify import CRAWLER_SESSION, LINK_PREVIEW, NOT_RENDERED

GROUPS = ("answer_engines", "search_engines", "bots")
OTHER = "(all others)"
PROBES = "(scanner probes)"
NO_AGENT = "(no user agent)"
# Bots whose strings may be a person's browser: their agents are not kept.
UNKEPT = {PROBES, NOT_RENDERED, CRAWLER_SESSION, "browser-like agent",
          "Googlebot template, no Googlebot"}


def short_name(agent: str) -> str:
    """A bot's short name from its user agent: the word after "compatible;"
    up to "/", ";" or ")"; else the agent's first word before "/" or a
    space ("browser-like agent" for Mozilla); at most 28 characters."""
    if not agent:
        return NO_AGENT
    if "Nexus 5X Build/MMB29P" in agent:
        return "Googlebot template, no Googlebot"
    mark = "compatible;"
    start = 0
    while True:
        at = agent.find(mark, start)
        if at < 0:
            break
        rest = agent[at + len(mark):]
        stops = [i for i in (rest.find("/"), rest.find(";"), rest.find(")")) if i >= 0]
        if not stops:
            break
        word = rest[:min(stops)]
        if word:
            return (word.strip() or word[-1])[:28]
        start = at + 1
    first = agent.partition("/")[0].partition(" ")[0]
    if first == "Mozilla":
        return "browser-like agent"
    return (first or agent)[:28]


def _name(line, group: str, info: dict) -> str:
    if group != "bots":
        return info.get("name") or "(unnamed)"
    if info.get("spoofed"):
        return f"claims to be {info['spoofed']}"
    if info.get("preview"):
        return LINK_PREVIEW + info["preview"]
    if info.get("not_rendered"):
        return NOT_RENDERED
    if info.get("crawler"):
        return CRAWLER_SESSION
    if info.get("probe"):
        return PROBES
    return short_name(line.agent)


def _ninetieth(times: list[int]) -> int | None:
    if not times:
        return None
    ordered = sorted(times)
    covered = 0
    for value in ordered:
        covered += 1
        if covered * 10 >= len(ordered) * 9:
            return value
    return ordered[-1]


class _Seen:
    def __init__(self) -> None:
        self.requests = 0
        self.bytes = 0
        self.sized = 0
        self.times: list[int] = []
        self.status = Counter()
        self.paths = Counter()
        self.countries = Counter()
        self.agents = Counter()
        self.last = None


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.seen: dict[str, dict[str, _Seen]] = {g: {} for g in GROUPS}

    def judged(self, line, group, info) -> None:
        if group not in self.seen:
            return
        name = _name(line, group, info or {})
        got = self.seen[group].setdefault(name, _Seen())
        got.requests += 1
        if line.size is not None:
            got.sized += 1
            got.bytes += int(line.size)
        if line.seconds is not None:
            got.times.append(int(round(line.seconds * 1000)))
        got.status[line.status[:1] + "xx"] += 1
        got.paths[line.url.partition("?")[0][:200]] += 1
        got.countries[line.country.upper() if line.country else "Unknown"] += 1
        got.agents[(line.agent or NO_AGENT)[:200]] += 1
        stamp = line.when.astimezone(timezone.utc)
        if got.last is None or stamp > got.last:
            got.last = stamp

    def visit(self, lines, is_page, labels) -> None:
        return

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("crawler_cost")
        if blob is None:
            return
        kept_groups = blob.get("groups") or {}
        for group in GROUPS:
            kept = kept_groups.get(group) or {}
            mine = self.seen[group]
            for name in sorted(n for n in kept if n != OTHER):
                _one(f"crawler_cost: {group} {name}", kept[name], mine.get(name) or _Seen(),
                     same, problems, group != "bots" or not (
                         name in UNKEPT or name.startswith(LINK_PREVIEW)))
            rest = [s for n, s in mine.items() if n not in kept or n == OTHER]
            fold = kept.get(OTHER) or {}
            what = f"crawler_cost: {group} {OTHER}"
            same(f"{what}: requests", int(fold.get("requests") or 0),
                 sum(s.requests for s in rest))
            same(f"{what}: lines with a size", int(fold.get("sized") or 0),
                 sum(s.sized for s in rest))
            same(f"{what}: bytes", int(fold.get("bytes") or 0), sum(s.bytes for s in rest))
            same(f"{what}: timed lines", int(fold.get("timed") or 0),
                 sum(len(s.times) for s in rest))
            same(f"{what}: milliseconds", int(fold.get("ms") or 0),
                 sum(sum(s.times) for s in rest))
            status = Counter()
            for s in rest:
                status.update(s.status)
            got = {k: int(v) for k, v in (fold.get("status") or {}).items()}
            for k in sorted(set(got) | set(status)):
                same(f"{what}: {k} responses", got.get(k, 0), status[k])


def _one(what: str, kept: dict, mine: _Seen, same, problems: list,
         agents: bool = True) -> None:
    same(f"{what}: requests", int(kept.get("requests") or 0), mine.requests)
    same(f"{what}: lines with a size", int(kept.get("sized") or 0), mine.sized)
    same(f"{what}: bytes", int(kept.get("bytes") or 0), mine.bytes)
    if (kept.get("bytes") is None) != (mine.sized == 0):
        problems.append(f"{what}: bytes are {'not ' if kept.get('bytes') is None else ''}"
                        f"recorded, the recount finds {mine.sized:,} lines with a size")
    same(f"{what}: timed lines", int(kept.get("timed") or 0), len(mine.times))
    same(f"{what}: milliseconds", int(kept.get("ms") or 0), sum(mine.times))
    p90 = _ninetieth(mine.times)
    same(f"{what}: p90 milliseconds", int(kept.get("p90_ms") or 0), p90 or 0)
    if (kept.get("p90_ms") is None) != (p90 is None):
        problems.append(f"{what}: p90 is {kept.get('p90_ms')}, the recount finds {p90}")
    got = {k: int(v) for k, v in (kept.get("status") or {}).items()}
    for k in sorted(set(got) | set(mine.status)):
        same(f"{what}: {k} responses", got.get(k, 0), mine.status[k])
    same(f"{what}: distinct paths", int(kept.get("paths") or 0), len(mine.paths))
    if (kept.get("agents") is not None) != agents:
        problems.append(f"{what}: user agents are {'' if kept.get('agents') is not None else 'not '}"
                        f"kept, and must {'' if agents else 'not '}be")
    for key, counted in (("pages", mine.paths), ("countries", mine.countries),
                         ("agents", mine.agents)):
        if key == "agents" and kept.get("agents") is None:
            continue
        listed = {k: int(v) for k, v in (kept.get(key) or {}).items()}
        for label in sorted(k for k in listed if k != OTHER):
            same(f"{what}: {key} {label}", listed[label], counted.get(label, 0))
        rest = sum(counted.values()) - sum(counted.get(k, 0) for k in listed if k != OTHER)
        same(f"{what}: {key} {OTHER}", listed.get(OTHER, 0), rest)
    last = mine.last.isoformat(timespec="seconds") if mine.last else None
    if kept.get("last") != last:
        problems.append(f"{what}: last seen {kept.get('last')}, the recount finds {last}")
