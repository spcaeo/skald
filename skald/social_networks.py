"""Social networks: the day kind `social_networks`, the Social media visits
by network (X, LinkedIn, Facebook, ...), each with the hosts, apps and tags
it rolled up and the pages its visitors landed on.

A count, not an estimate: every visit whose source type is Social media
(dimensions.source_type, unchanged) is given exactly one network by the
rules in social_names.py - its first page's referrer host or app first, else
the utm_ tag that made it Social media, else its social ad click id - and a
visit no list names is "other" (Social, network not named). So the networks
add up to the Social media visits, which are the Sources tab's Social media
row (visits equal readers, visits.check).

The blob (kind `social_networks`; None when the visits were not counted -
"not recorded", never 0):

  visits     the day's visits (journeys)
  social     of which Social media: equals the visits whose source is Social media
  networks   {id: visits}: only networks with a visit; adds up to social
  via        {id: {how: visits}}: how each network's visits were matched -
             a host ("t.co", "l.facebook.com"), an app
             ("android-app://com.linkedin.android") or a tag ("(utm_source)",
             "(utm_medium)", "(fbclid)"); each adds up to its network
  landings   {id: {path: visits}}: the pages they landed on, the top
             social_names.LANDINGS_KEPT and "(all others)"; each adds up to
             its network

Only hosts, app ids, tag names, paths and counts are kept: never a query
value, an address or a whole referrer.

Second count: audit_social.py, from the raw lines with its own code; it
shares only social_names.py's lists.
"""
from __future__ import annotations

import re
from collections import Counter

from . import dimensions as dim
from .social_names import (ALL_OTHERS, APP_PREFIX, HOST_KEEP, IDS, LANDINGS_KEPT, NETWORKS,
                           OTHER, SOCIAL, SOCIAL_CLICK_IDS)

_WORD = re.compile(r"[^a-z0-9]+")
_TLD = {n[0]: [re.compile(rf"(?:^|\.){re.escape(b)}\.[a-z.]+$") for b in n[3]] for n in NETWORKS}
_CLICK_NET = {key: n[0] for n in NETWORKS for key in n[6]}


def _by_host(host: str) -> str:
    """The first network whose host, any-TLD base or app id names `host`
    (an android-app:// referrer's host is the app's id)."""
    for net, _name, hosts, _bases, apps, _words, _ids in NETWORKS:
        if any(host == h or host.endswith("." + h) for h in hosts):
            return net
        if any(p.search(host) for p in _TLD[net]):
            return net
        if any(host.startswith(a) for a in apps):
            return net
    return OTHER


def _named(value: str) -> list[str]:
    """The networks the words of a tag's value name (UTM_WORDS)."""
    words = {w for w in _WORD.split(value.lower()) if w}
    return [n[0] for n in NETWORKS if words & set(n[5])]


def network(source: str, referrer: str, url: str) -> tuple[str, str] | None:
    """(network id, how it was matched) of a visit's first page, or None
    when its source type is not Social media."""
    if source != SOCIAL:
        return None
    host = dim.referrer_host(referrer or "")
    if host:
        app = (referrer or "").lower().startswith(APP_PREFIX)
        return _by_host(host), ((APP_PREFIX if app else "") + host)[:HOST_KEEP]
    tags = dim.query(url or "")
    # utm_source's words, then utm_medium's, then a social click id: the
    # first that names a network decides; one naming two is "other".
    for key in ("utm_source", "utm_medium"):
        named = _named(tags.get(key, ""))
        if named:
            return (named[0] if len(named) == 1 else OTHER), f"({key})"
    for key in SOCIAL_CLICK_IDS:
        if tags.get(key):
            return _CLICK_NET.get(key, OTHER), f"({key})"
    said = next((k for k in ("utm_source", "utm_medium") if tags.get(k)), "")
    return OTHER, f"({said})" if said else "(none)"


METHOD = ("Counted, not inferred: each visit whose source type is Social media gets one "
          "network, by its first page's referring host or app (t.co, x.com and twitter.com "
          "are X; linkedin.com and lnkd.in are LinkedIn; ...), else by the words of its "
          "utm_source, then its utm_medium (utm_source=twitter is X), else by a social ad "
          "click id (fbclid is Facebook). A tag naming two networks, or none "
          "(utm_source=social), is Social, network not named. The networks add up to the "
          "Social media row.")


def note() -> dict:
    """What a page says beside the figure: the networks' names in the
    list's order, and the method."""
    from .social_names import NAMES
    return {"names": dict(NAMES), "order": list(IDS), "method": METHOD}


def fold(pages: Counter) -> dict:
    """The top LANDINGS_KEPT pages (more visits first, then the path) and
    the rest as "(all others)", so the pages still add up."""
    ranked = sorted(pages.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) <= LANDINGS_KEPT:
        return dict(ranked)
    kept = ranked[: LANDINGS_KEPT - 1]
    out = dict(kept)
    out[ALL_OTHERS] = int(sum(n for _, n in ranked[LANDINGS_KEPT - 1:]))
    return out


def finish(extras, totals, journeys, page_visits, readers_by_hour) -> dict | None:
    landings = getattr(extras, "visit_landings", None)
    people = getattr(totals, "people", None)
    if journeys is None or landings is None or people is None \
            or not len(landings) == len(people) == len(journeys):
        return None
    networks: Counter = Counter()
    via: dict[str, Counter] = {}
    pages: dict[str, Counter] = {}
    social = 0
    for j, url, who in zip(journeys, landings, people):
        got = network(j.get("source", ""), (who or {}).get("referrer", ""), url or "")
        if got is None:
            continue
        social += 1
        net, how = got
        networks[net] += 1
        via.setdefault(net, Counter())[how] += 1
        pages.setdefault(net, Counter())[j.get("landing") or "/"] += 1
    order = sorted(networks, key=lambda k: (-networks[k], k))
    return {"visits": len(journeys), "social": social,
            "networks": {k: int(networks[k]) for k in order},
            "via": {k: dict(sorted(via[k].items(), key=lambda kv: (-kv[1], kv[0]))) for k in order},
            "landings": {k: fold(pages[k]) for k in order}}


def check(totals, blob, differs, problems) -> None:
    from .verify import Problem
    nets = {k: int(v) for k, v in (blob.get("networks") or {}).items()}
    social = int(blob.get("social", 0))
    differs("social_networks: visits by network", sum(nets.values()), social, "social visits")
    for part in ("via", "landings"):
        got = blob.get(part) or {}
        if set(got) != set(nets):
            problems.append(Problem("social_networks", f"the {part} name other networks than "
                                                       "the visits"))
        for net, n in nets.items():
            differs(f"social_networks: {net} by {part}",
                    sum(int(v) for v in (got.get(net) or {}).values()), n, f"{net} visits")
    unknown = sorted(set(nets) - set(IDS))
    if unknown:
        problems.append(Problem("social_networks", f"a network not in the list: {unknown[0]}"))
    if any(v <= 0 for v in nets.values()):
        problems.append(Problem("social_networks", "a network is kept with no visit"))
    if not 0 <= social <= int(blob.get("visits", 0)):
        problems.append(Problem("social_networks", "social visits are not within the visits"))
    stats = getattr(totals, "visits", None)
    if stats is not None:
        differs("social_networks: visits", int(blob.get("visits", 0)), int(stats.visits), "visits")
        # On a tally that labelled the visits by source (visits.check holds
        # them equal to the readers': the Sources tab's Social media row).
        if sum(stats.source.values()) == stats.visits:
            differs("social_networks: social visits", social, int(stats.source.get(SOCIAL, 0)),
                    "visits whose source is Social media")
