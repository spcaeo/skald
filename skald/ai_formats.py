"""What AI fetches asked for: the day kind `ai_formats`.

Every answer-engine request (both tiers: `asked`, an assistant fetching for
someone's question, classify.AI_ASKED; `training`, a crawler collecting,
classify.AI_TRAINING) by the kind of thing its path names. Only the path
decides (lower case, query string left out); the status does not, so a 404
for /llms.txt is still a fetch of llms.txt:

  llms.txt     /llms.txt or /llms-full.txt (at the site's root)
  robots.txt   /robots.txt
  Markdown     a path ending .md or .mdx
  Sitemap      a file named sitemap*.xml (sitemap.xml, sitemap_index.xml, ...)
  Text         any other path ending .txt
  Other file   an asset, feed, document, archive or media file (parse.ASSET),
               an API or beacon path (parse.BEACON) or a framework payload
               (parse.RSC_PAYLOAD)
  Page         everything else: a document

    {"asked":    {"formats": {"Page": 12, "Markdown": 3},
                  "by_name": {"ChatGPT-User": {"Page": 10, "Markdown": 3},
                              "(all others)": {"Page": 2}}},
     "training": {"formats": {...}, "by_name": {...}}}

Both tiers are always present. `by_name` keeps the TOP names with the most
fetches (the classifier's token, as `engines` names them) and folds the
rest into "(all others)", so every sum holds: per tier, `formats` adds up to
the tier's requests (engine_tier), each name's formats to its fetches, and
each format over the names to `formats`. Second count: audit_ai_formats.py,
from the raw lines with its own path rule.
"""
from __future__ import annotations

from collections import Counter

from .classify import Group
from .parse import ASSET, BEACON, RSC_PAYLOAD

TOP = 20
OTHER = "(all others)"
TIERS = ("asked", "training")
FORMATS = ("Page", "llms.txt", "Markdown", "Text", "robots.txt", "Sitemap", "Other file")


def format_of(path: str, url: str = "") -> str:
    """One of FORMATS for a request's path (and its URL, for a payload)."""
    low = (path or "").split("?", 1)[0].split("#", 1)[0].lower()
    name = low.rsplit("/", 1)[-1]
    if low in ("/llms.txt", "/llms-full.txt"):
        return "llms.txt"
    if low == "/robots.txt":
        return "robots.txt"
    if name.endswith((".md", ".mdx")):
        return "Markdown"
    if name.startswith("sitemap") and name.endswith(".xml"):
        return "Sitemap"
    if name.endswith(".txt"):
        return "Text"
    if ASSET.search(low) or BEACON.search(low) or RSC_PAYLOAD.search(url or ""):
        return "Other file"
    return "Page"


class Formats:
    """The tally pass's answer-engine requests (extras.Extras offers it every hit)."""

    def __init__(self) -> None:
        self.seen: dict[str, Counter] = {t: Counter() for t in TIERS}   # (name, format)

    def add(self, hit, verdict) -> None:
        if verdict.group is not Group.ANSWER_ENGINE or not verdict.tier:
            return
        tier = verdict.tier.value
        if tier in self.seen:
            self.seen[tier][(verdict.engine or "", format_of(hit.path, hit.url))] += 1


def _tier(seen: Counter) -> dict:
    formats: Counter = Counter()
    names: dict[str, Counter] = {}
    for (name, kind), n in seen.items():
        formats[kind] += n
        names.setdefault(name, Counter())[kind] += n
    order = sorted(names, key=lambda k: (-sum(names[k].values()), k))
    by_name = {k: dict(sorted(names[k].items())) for k in order[:TOP]}
    rest: Counter = Counter()
    for k in order[TOP:]:
        rest.update(names[k])
    if rest:
        by_name[OTHER] = dict(sorted(rest.items()))
    return {"formats": dict(sorted(formats.items())), "by_name": by_name}


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    got = getattr(extras, "ai_formats", None)
    if got is None:
        return None
    return {tier: _tier(got.seen[tier]) for tier in TIERS}


def check(totals, blob, differs, problems) -> None:
    engines = totals.groups.get(Group.ANSWER_ENGINE)
    for tier in TIERS:
        part = blob.get(tier) or {}
        formats = part.get("formats") or {}
        by_name = part.get("by_name") or {}
        differs(f"ai_formats: {tier} fetches by format", sum(int(v) for v in formats.values()),
                int(engines.tiers.get(tier, 0)) if engines else 0, f"{tier} fetches")
        for kind in sorted(set(formats) | {k for v in by_name.values() for k in v}):
            differs(f"ai_formats: {tier} {kind} by name",
                    sum(int(v.get(kind, 0)) for v in by_name.values()), int(formats.get(kind, 0)),
                    f"{tier} {kind} fetches")
