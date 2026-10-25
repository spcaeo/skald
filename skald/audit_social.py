"""The second count of "Social networks" (day kind `social_networks`).

Registered in audit_more.RECOUNTS. It sees every people visit (`visit`) and
rebuilds the figure from its raw lines with its own code, written apart from
social_networks.py. It shares only the name lists in social_names.py:

  a social visit  a visit that read a page whose source (the audit's own
                  label, audit_labels.source_of) is Social media
  its referrer    the first page line's referrer, its host read here: the
                  part after "scheme://" (or the whole referrer when it has
                  no "//"), up to "/", "?" or "#", without a user part or a
                  port, lower case, a final "." and a leading "www." off
  its network     the first network, in the list's order, whose host is the
                  host or a parent of it (split on "."), whose any-TLD base
                  is a label of the host followed only by letters and dots,
                  or whose app id start begins the host
  no referrer     the first page line's URL, its query split here by hand on
                  "&" and "=" (pairs with no value left out, the first 40
                  kept, the last of a repeated name winning, names lower
                  case); utm_source's words, then utm_medium's (runs of a-z
                  and 0-9, lower case), then the social click ids, as
                  social_names.py says
  its landing     the audit's landing label (the first page's path, 70
                  characters)

Each network's pages are folded as the stored blob says (the top kept, more
visits first, then the path; the rest summed as "(all others)") and
compared page by page.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import unquote_plus, urlsplit

from .social_names import (ALL_OTHERS, APP_PREFIX, HOST_KEEP, IDS, LANDINGS_KEPT, NETWORKS,
                           OTHER, SOCIAL, SOCIAL_CLICK_IDS)


def _host(referrer: str) -> str:
    text = (referrer or "").strip()
    if not text or text == "-":
        return ""
    try:
        got = urlsplit(text if "//" in text else "//" + text).netloc
    except ValueError:
        return ""
    got = got.rpartition("@")[2]
    if got.startswith("["):
        got = got[1:].partition("]")[0]
    else:
        got = got.partition(":")[0]
    got = got.lower()
    while got.endswith("."):
        got = got[:-1]
    return got[4:] if got.startswith("www.") else got


def _any_tld(host: str, base: str) -> bool:
    labels = host.split(".")
    for i, label in enumerate(labels):
        rest = ".".join(labels[i + 1:])
        if label == base and rest and all(("a" <= c <= "z") or c == "." for c in rest):
            return True
    return False


def _of_host(host: str) -> str:
    parents = {".".join(host.split(".")[i:]) for i in range(len(host.split(".")))}
    for net, _name, hosts, bases, apps, _words, _ids in NETWORKS:
        if parents & set(hosts):
            return net
        if any(_any_tld(host, b) for b in bases):
            return net
        if any(host[: len(a)] == a for a in apps):
            return net
    return OTHER


def _pairs(url: str) -> dict:
    if "?" not in url:
        return {}
    kept = []
    for part in url.split("?", 1)[1].split("&"):
        name, eq, value = part.partition("=")
        if not eq or not value:
            continue
        kept.append((unquote_plus(name).lower(), unquote_plus(value)))
        if len(kept) == 40:
            break
    return dict(kept)


def _words(value: str) -> set[str]:
    out, word = set(), ""
    for ch in value.lower() + " ":
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            word += ch
        elif word:
            out.add(word)
            word = ""
    return out


def network_of(referrer: str, url: str) -> tuple[str, str]:
    """(network id, how) of a Social media visit's first page line."""
    host = _host(referrer)
    if host:
        how = APP_PREFIX + host if (referrer or "").strip().lower()[:len(APP_PREFIX)] \
            == APP_PREFIX else host
        return _of_host(host), how[:HOST_KEEP]
    query = _pairs(url or "")
    for key in ("utm_source", "utm_medium"):
        words = _words(query.get(key) or "")
        named = [n[0] for n in NETWORKS if any(w in words for w in n[5])]
        if len(named) == 1:
            return named[0], "(" + key + ")"
        if named:
            return OTHER, "(" + key + ")"
    for key in SOCIAL_CLICK_IDS:
        if (query.get(key) or "") != "":
            return next((n[0] for n in NETWORKS if key in n[6]), OTHER), "(" + key + ")"
    for key in ("utm_source", "utm_medium"):
        if (query.get(key) or "") != "":
            return OTHER, "(" + key + ")"
    return OTHER, "(none)"


def _fold(pages: Counter) -> dict:
    ranked = sorted(pages.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) <= LANDINGS_KEPT:
        return dict(ranked)
    out = dict(ranked[: LANDINGS_KEPT - 1])
    out[ALL_OTHERS] = sum(n for _, n in ranked[LANDINGS_KEPT - 1:])
    return out


class Recount:
    def __init__(self, config, day, tz, own) -> None:
        self.visits = 0
        self.networks: Counter = Counter()
        self.via: dict[str, Counter] = {}
        self.pages: dict[str, Counter] = {}

    def visit(self, lines, is_page, labels) -> None:
        if labels is None:
            return
        self.visits += 1
        if labels["source"] != SOCIAL:
            return
        first = next((x for x in lines if is_page(x)), None)
        if first is None:
            return
        net, how = network_of(first.referrer, first.url)
        self.networks[net] += 1
        self.via.setdefault(net, Counter())[how] += 1
        self.pages.setdefault(net, Counter())[labels["landing"]] += 1

    def compare(self, stored, same, problems) -> None:
        blob = stored.get("social_networks")
        if blob is None:
            return
        same("social_networks: visits", int(blob.get("visits", 0)), self.visits)
        same("social_networks: social visits", int(blob.get("social", 0)),
             sum(self.networks.values()))
        kept = {k: int(v) for k, v in (blob.get("networks") or {}).items()}
        for net in sorted(set(kept) | set(self.networks)):
            same(f"social_networks: {net}", kept.get(net, 0), self.networks[net])
            for part, mine in (("via", dict(self.via.get(net) or {})),
                               ("landings", _fold(self.pages.get(net) or Counter()))):
                theirs = {k: int(v) for k, v in
                          (((blob.get(part) or {}).get(net)) or {}).items()}
                for name in sorted(set(theirs) | set(mine)):
                    same(f"social_networks: {net} {part}, {name}", theirs.get(name, 0),
                         mine.get(name, 0))
        for extra in sorted(set(kept) - set(IDS)):
            problems.append(f"social_networks: a network the recount does not know: {extra}")
