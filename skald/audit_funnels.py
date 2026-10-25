"""The audit's own recount of funnel history (day_extras kind `funnels`).

Part of audit.py's second road (registered in audit_more.py), written apart
from funnels.py, funnel_days.py and visits.py on purpose. Nothing from them
is called. From each people visit's raw lines, in time order, it rebuilds
the visit's trail - the pages loaded and the in-app moves seen from a
same-site referrer, each with the seconds since the visit's first request,
bucketed as durations are - and matches the funnel steps with its own code,
from the rules in DATA-CONTRACT.md ("funnels.json"):

  equals       the path, with or without its trailing slash
  starts_with  the path starts with it
  segment      the path's last part, any case ("pricing" meets /ca/pricing/)
  contains     the path holds it anywhere
  any          (first step only) the visit's start; it uses no trail entry

A step is met by the first trail entry at or after the one that met the
step before. A funnel's source is met by the visit's source type, the
assistant or site that sent it, or its referring host, in any case.

It reads funnels.json itself for the funnels saved on or before the day,
and recounts every series the day holds: from its listed definition, or -
for a series no longer listed (deleted or changed since) - from the
definition stored beside it, once its own hash of that definition is the
series' key. A series the day does not hold was not counted that day: not
recorded, nothing to compare.

What it shares with the package is only classify.py's name lists, the
audit's own labels (audit_labels.py) and its asset and duration rules
(audit_visits.py).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .audit_labels import _bare, _host_of, _tags
from .audit_visits import _bucket, _is_asset_path, _is_beacon_path
from .classify import AI_REFERRER_HOSTS, AI_REFERRER_PATHS, AI_UTM, ASSISTANT_ALIASES

KEEP = 50                      # trail entries a journey keeps (visits.TRAIL_KEEP)
LEFT = "(left the site)"
OTHER = "(all others)"
TOP = 10
# Time to complete, from DATA-CONTRACT.md: [from, to) seconds.
TIME_LABELS = ((0, 10, "under 10s"), (10, 30, "10-30s"), (30, 60, "30s-1m"),
               (60, 180, "1-3m"), (180, 600, "3-10m"), (600, 1800, "10-30m"))
# The names a reader knows each assistant by (the journeys' `via`).
SHOWN = {"chatgpt.com": "ChatGPT", "perplexity.ai": "Perplexity", "claude.ai": "Claude",
         "gemini.google.com": "Gemini", "copilot.microsoft.com": "Copilot",
         "you.com": "You.com", "phind.com": "Phind", "poe.com": "Poe",
         "mistral.ai": "Mistral", "meta.ai": "Meta AI", "deepseek.com": "DeepSeek",
         "grok.com": "Grok"}
# The utm_source tags an assistant puts on its links: the shared name list.
_TAGGED = AI_UTM


def _time_label(seconds: int) -> str:
    for low, high, label in TIME_LABELS:
        if low <= seconds < high:
            return label
    return "30m or more"


def _visit_steps(steps) -> list[dict]:
    """The steps counted per visit: "any" and page steps, without labels."""
    out = []
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        kind = s.get("kind", "path")
        if kind == "any":
            out.append({"kind": "any"})
        elif kind == "path":
            out.append({"kind": "path", "match": s.get("match") or "equals",
                        "paths": list(s.get("paths") or [])})
    return out


def series_key(source, steps) -> str:
    """The series' key, from the contract's words: the SHA-256 of
    {"source", "steps" (visit steps, no labels)} as compact JSON with
    sorted keys; its first 16 hex digits."""
    text = json.dumps({"source": source or None, "steps": _visit_steps(steps)},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _hit(step: dict, path: str) -> bool:
    path = path.partition("?")[0]
    for want in step.get("paths") or []:
        how = step.get("match")
        if how == "equals":
            if (path.rstrip("/") or "/") == (want.rstrip("/") or "/"):
                return True
        elif how == "starts_with":
            if path.startswith(want):
                return True
        elif how == "contains":
            if want in path:
                return True
        else:
            parts = [p for p in path.split("/") if p]
            last = parts[-1] if parts else ""
            if last.lower() == want.strip("/").lower():
                return True
    return False


def _assistant(line) -> str:
    """The assistant that sent a cited visit, by the name a reader knows."""
    name = ""
    host = _host_of(line.referrer).rstrip(".") if line.referrer else ""
    if host:
        for domain in AI_REFERRER_HOSTS:
            if host == domain or host.endswith("." + domain):
                name = ASSISTANT_ALIASES.get(domain, domain)
                break
        else:
            for domain, prefix in AI_REFERRER_PATHS.items():
                if (host == domain or host.endswith("." + domain)) and \
                        urlsplit(line.referrer).path.startswith(prefix):
                    name = ASSISTANT_ALIASES.get(domain + prefix, domain + prefix)
    if not name:
        tagged = _TAGGED.search(line.url)
        if tagged:
            raw = tagged.group(1).lower()
            name = ASSISTANT_ALIASES.get(raw, raw)
    return SHOWN.get(name, name)


def _names(line, source: str) -> set[str]:
    """What a funnel's source may name for this visit, lower case."""
    host = _bare(line.referrer) if line.referrer else ""
    if source == "AI assistant":
        via = _assistant(line)
    elif source in ("Direct or unknown", "This site"):
        via = ""
    elif host:
        via = host[:60]
    else:
        via = (_tags(line.url).get("utm_source") or "").strip().lower()[:30]
    ref = "" if source == "This site" else host[:60]
    return {x.lower() for x in (source, via, ref) if x}


def _saved(config: dict, day, tz) -> dict:
    """{key: {"source", "steps"}} from funnels.json, saved on or before day."""
    folder = ((config or {}).get("_resolved") or {}).get("live_dir")
    if not folder:
        return {}
    try:
        with open(Path(folder) / "funnels.json", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    items = data.get("funnels") if isinstance(data, dict) else None
    out = {}
    for f in (items or {}).values() if isinstance(items, dict) else []:
        if not isinstance(f, dict) or not _visit_steps(f.get("steps")):
            continue
        try:
            when = datetime.fromisoformat(str(f.get("saved_at") or ""))
        except ValueError:
            continue
        when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
        if when.astimezone(tz).date() <= day:
            out[series_key(f.get("source"), f.get("steps"))] = {
                "source": f.get("source"), "steps": f.get("steps")}
    return out


def _int(v) -> int:
    return v if isinstance(v, int) else 0


def _nth(values, i: int) -> int:
    return _int(values[i]) if isinstance(values, list) and i < len(values) else 0


class Recount:
    """Every stored funnel series of one day, counted again."""

    def __init__(self, config: dict, day, tz, own: set) -> None:
        self.own = own
        self.listed = _saved(config, day, tz)
        self.visits: list[tuple] = []          # (paths, at, source, device, names)

    def _where(self, line) -> str:
        if not line.referrer:
            return ""
        try:
            parts = urlsplit(line.referrer)
            host = (parts.hostname or "").lower()
        except ValueError:
            return ""
        own = self.own or ({line.host.lower()} if line.host else set())
        if not host or host not in own:
            return ""
        path = parts.path or "/"
        if _is_asset_path(path) or _is_beacon_path(path):
            return ""
        return path[:70]

    def visit(self, lines: list, is_page, labels: dict | None) -> None:
        if labels is None:
            return
        paths, times = [], []
        for line in lines:
            here = is_page(line)
            if paths and line.status[:1] in ("2", "3"):
                where = self._where(line)
                if where and where != paths[-1] and not (here and where == line.path[:70]):
                    paths.append(where)
                    times.append(line.when)
            if here:
                paths.append(line.path[:70])
                times.append(line.when)
        start = lines[0].when
        at = [_bucket(max(0, int((t - start).total_seconds()))) for t in times[:KEEP]]
        first = next(line for line in lines if is_page(line))
        self.visits.append((paths[:KEEP], at, labels["source"], labels["device"],
                            _names(first, labels["source"])))

    def count(self, source, steps) -> dict:
        steps = _visit_steps(steps)
        want = (source or "").strip().lower()
        k = len(steps)
        got = {"visits": 0, "reached": [0] * k, "by_source": {}, "by_device": {},
               "next": [Counter() for _ in range(k)], "complete": Counter()}
        for paths, at, src, device, names in self.visits:
            if want and want not in names:
                continue
            got["visits"] += 1
            met, i = [], 0
            for step in steps:
                if step["kind"] == "any":
                    met.append(None)
                    continue
                j = i
                while j < len(paths) and not _hit(step, paths[j]):
                    j += 1
                if j >= len(paths):
                    break
                met.append(j)
                i = j
            if not met:
                continue
            for split, label in (("by_source", src), ("by_device", device)):
                row = got[split].setdefault(label, [0] * k)
                for x in range(len(met)):
                    row[x] += 1
            for x in range(len(met)):
                got["reached"][x] += 1
            last = met[-1]
            if last is None:
                after = paths[0] if paths else LEFT
            else:
                after = next((p for p in paths[last + 1:] if p != paths[last]), LEFT)
            got["next"][len(met) - 1][after] += 1
            if len(met) == k and k > 1:
                begin = 0 if met[0] is None else at[met[0]]
                got["complete"][_time_label(max(0, at[last] - begin))] += 1
        return got

    def compare(self, stored: dict, same, problems: list) -> None:
        blob = stored.get("funnels")
        if not isinstance(blob, dict):
            return
        for key, have in sorted(blob.items()):
            have = have if isinstance(have, dict) else {}
            name = f"funnel {have.get('name') or key}"
            if series_key(have.get("source"), have.get("steps")) != key:
                problems.append(f"{name}: its stored steps do not match its key {key}")
                continue
            plan = self.listed.get(key) or have
            mine = self.count(plan.get("source"), plan.get("steps"))
            self._same(name, have, mine, same)

    def _same(self, name: str, have: dict, mine: dict, same) -> None:
        k = len(mine["reached"])
        same(f"{name}: visits", _int(have.get("visits")), mine["visits"])
        for i in range(k):
            same(f"{name}: step {i + 1} reached", _nth(have.get("reached"), i),
                 mine["reached"][i])
        for split, words in (("by_source", "by source"), ("by_device", "by device")):
            theirs = have.get(split) if isinstance(have.get(split), dict) else {}
            for label in sorted(set(theirs) | set(mine[split])):
                for i in range(k):
                    same(f"{name}: {words} {label}, step {i + 1}", _nth(theirs.get(label), i),
                         _nth(mine[split].get(label), i))
        nexts = have.get("next") if isinstance(have.get("next"), list) else []
        for i in range(k):
            theirs = nexts[i] if i < len(nexts) and isinstance(nexts[i], dict) else {}
            counted = mine["next"][i]
            kept = [p for p in theirs if p != OTHER]
            for p in sorted(kept):
                same(f"{name}: next pages after step {i + 1}: {p}", _int(theirs[p]),
                     counted.get(p, 0))
            same(f"{name}: next pages after step {i + 1}: {OTHER}", _int(theirs.get(OTHER)),
                 sum(counted.values()) - sum(counted.get(p, 0) for p in kept))
        if k > 1:
            theirs = have.get("complete") if isinstance(have.get("complete"), dict) else {}
            for label in sorted(set(theirs) | set(mine["complete"])):
                same(f"{name}: time to complete {label}", _int(theirs.get(label)),
                     mine["complete"].get(label, 0))
