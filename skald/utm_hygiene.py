"""Campaign tag hygiene: the day kind `utm_hygiene` (campaigns.json).

Badly tagged links split a campaign into pieces or hide it. Per day, from
the day's journeys (one per visit, by its landing page), the visits whose
landing address shows one of these:

  source_no_medium   utm_source without utm_medium
  unknown_medium     a utm_medium outside classify.UTM_MEDIUMS (the channel
                     names analytics tools know)
  click_id_no_tags   an ad click id (gclid, fbclid, msclkid, ...) and no
                     utm_ tag: the network is known, the campaign is not
  internal_tags      a utm_ tag on a link from one of the site's own pages
                     (EDGE-CASES E8): it starts a new "source" mid-visit

A visit can show more than one. The blob:

  visits    the visits looked at (the day's journeys)
  counts    {problem: visits}, every problem always present
  paths     {problem: {landing path: visits}}, the 20 largest and
            "(all others)": each adds up to its count
  examples  {problem: [{"path", "tags", "click_id"}]}, the day's first three:
            the landing path, its utm_ tags as "utm_source=x&utm_medium=y"
            (the only query values ever kept), and the click id's network,
            never the id

Campaigns seen in leads but never in the log are read in the app, from
leads.json beside campaigns.json, when the lead store is set up.

Second count: audit_utm.py, from the raw landing line with parse_qsl and
its own rules; it shares only classify.py's name lists.
"""
from __future__ import annotations

from collections import Counter

from .classify import UTM_MEDIUMS

PROBLEMS = ("source_no_medium", "unknown_medium", "click_id_no_tags", "internal_tags")
UTM = ("source", "medium", "campaign", "term", "content")
TOP = 20
EXAMPLES = 3
OTHER = "(all others)"


def _own(host: str, own: set[str]) -> bool:
    return bool(host) and (host in own or "www." + host in own)


def problems_of(j: dict, own: set[str]) -> list[str]:
    """The hygiene problems of one journey (campaigns.fields' labels)."""
    utm = j.get("utm") or {}
    out = []
    if utm.get("source") and not utm.get("medium"):
        out.append("source_no_medium")
    if utm.get("medium") and utm["medium"] not in UTM_MEDIUMS:
        out.append("unknown_medium")
    if j.get("paid") and not utm:
        out.append("click_id_no_tags")
    # "This site" is a referrer from our own hosts; a visit an assistant's
    # utm_source marks as cited keeps its referring host instead.
    if utm and (j.get("source") == "This site" or _own(j.get("ref_host") or "", own)):
        out.append("internal_tags")
    return out


def _fold(paths: Counter) -> dict:
    ordered = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))
    out = dict(ordered[:TOP])
    rest = sum(n for _, n in ordered[TOP:])
    if rest:
        out[OTHER] = rest
    return out


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    if journeys is None:
        return None
    own = set(getattr(extras, "own_hosts", None) or ())
    counts = Counter({p: 0 for p in PROBLEMS})
    paths = {p: Counter() for p in PROBLEMS}
    examples: dict[str, list] = {p: [] for p in PROBLEMS}
    for j in journeys:
        for p in problems_of(j, own):
            counts[p] += 1
            landing = str(j.get("landing") or "")
            paths[p][landing] += 1
            if len(examples[p]) < EXAMPLES:
                utm = j.get("utm") or {}
                examples[p].append({
                    "path": landing,
                    "tags": "&".join(f"utm_{k}={utm[k]}" for k in UTM if utm.get(k)),
                    "click_id": j.get("paid") or ""})
    return {"visits": len(journeys), "counts": {p: int(counts[p]) for p in PROBLEMS},
            "paths": {p: _fold(paths[p]) for p in PROBLEMS}, "examples": examples}


def check(totals, blob, differs, problems) -> None:
    from .verify import Problem
    stats = getattr(totals, "visits", None)
    if stats is not None:
        differs("utm_hygiene: visits", int(blob.get("visits", 0)), int(stats.visits), "visits")
    counts = blob.get("counts") or {}
    for p in PROBLEMS:
        n = int(counts.get(p, 0))
        differs(f"utm_hygiene: {p} by landing page",
                sum(int(v) for v in ((blob.get("paths") or {}).get(p) or {}).values()), n,
                "visits")
        if n > int(blob.get("visits", 0)):
            problems.append(Problem(f"utm_hygiene: {p}", "more than the visits"))
