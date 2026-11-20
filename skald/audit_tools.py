"""The audit's own answer to "is this a tool in a browser's clothes?" (tool_visits.py).

Written apart from tool_visits.py, as the rest of the audit is: its own
browser test, its own visit split, its own reading of a status and of a
document. The asset and document tests are the audit's own (audit._asset and
audit's payload and beacon tests, passed in). It shares only the name lists
PROBE and OTHER_BOT from classify.py.

The rules it recounts (CLASSIFICATION.md):

  6c  an address and agent that asked the site's hosts, in the window, for
      at least 5 different paths matching PROBE that were answered 4xx or
      5xx - no asset (a folder, ending in "/", is none), nothing under
      site.legacy_paths - is a bot on every line of the window.
  8b  a browser-like visit (address and agent, no gap longer than the
      session gap, on the site's hosts) that sent HEAD for at least 2
      different documents (no asset, payload or beacon), or for images at
      least 2 times, the same picture or not (SKALD-25), is a bot: every
      line of it, from its first to its last.
"""
from __future__ import annotations

import re
from datetime import timedelta

from .classify import OTHER_BOT, PROBE

_LIKE_A_BROWSER = re.compile(r"Mozilla/|Opera/|Safari/|Chrome/|Firefox/", re.I)
MISSING_PROBES = 5
HEAD_DOCUMENTS = 2
# The audit's own image test: a picture by its extension, or Next.js's image address.
_PICTURE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico")


def _on_site(line, hosts: set) -> bool:
    return not (hosts and line.host and line.host.lower() not in hosts)


def _picture(path: str) -> bool:
    low = path.lower()
    return low.endswith(_PICTURE_EXT) or low in ("/_next/image", "/_next/image/")


def sweepers(lines: list, hosts: set, legacy: tuple, is_asset) -> set:
    """{(address, agent)} that asked for MISSING_PROBES different probe paths
    the site answered with an error."""
    asked: dict[tuple, set] = {}
    for line in lines:
        if not line.status or line.status[0] not in "45" or not _on_site(line, hosts):
            continue
        path = line.path
        # The audit's own reading: an address ending in "/" asks for a folder, never a file.
        if (is_asset(line) and path[-1:] != "/") or any(path.startswith(p) for p in legacy):
            continue
        if PROBE.search(path):
            asked.setdefault((line.address, line.agent), set()).add(path)
    return {pair for pair, paths in asked.items() if len(paths) >= MISSING_PROBES}


def link_checkers(lines: list, gap: timedelta, hosts: set, is_asset, is_payload,
                  is_beacon) -> dict:
    """{(address, agent): [(first, last)]} of the browser-like visits that
    sent HEAD for HEAD_DOCUMENTS different documents, or for images that many times."""
    by_pair: dict[tuple, list] = {}
    for line in lines:
        agent = line.agent
        if not _on_site(line, hosts) or not agent or not _LIKE_A_BROWSER.search(agent) \
                or OTHER_BOT.search(agent):
            continue
        by_pair.setdefault((line.address, agent), []).append(line)
    found: dict[tuple, list] = {}
    for pair, seen in by_pair.items():
        if not any(l.method == "HEAD" for l in seen):
            continue
        seen = sorted(seen, key=lambda l: l.when)
        cut = [0] + [k for k in range(1, len(seen)) if seen[k].when - seen[k - 1].when > gap]
        for a, b in zip(cut, cut[1:] + [len(seen)]):
            visit = seen[a:b]
            asked = [l for l in visit if l.method == "HEAD" and not is_payload(l)
                     and not is_beacon(l)]
            pages = {l.path for l in asked if not is_asset(l)}
            pictures = sum(1 for l in asked if is_asset(l) and _picture(l.path))
            if len(pages) >= HEAD_DOCUMENTS or pictures >= HEAD_DOCUMENTS:
                found.setdefault(pair, []).append((visit[0].when, visit[-1].when))
    return found
