"""The audit's own reading of the not-a-page list (not_pages.py, trap 19).

It shares the name lists only: the entry names, their extensions, path
segments and query keys (not_pages.RULES). The matching is written here
again, without a regular expression: the path is cut into its segments and
the query into its keys, and each list is compared with them. A site's
setting (config["site"]["not_pages_off"], ["not_pages_extra"]) is read and
checked by this module's own code too.

Upper and lower case are the ASCII letters only (_low), as on the main road.
"""
from __future__ import annotations

import string

from .not_pages import DEFAULT, OWN, RULES

_UP = str.maketrans(string.ascii_uppercase, string.ascii_lowercase)
_KEY_CHARS = set(string.ascii_letters + string.digits + "_.-[]")


def _low(text: str) -> str:
    return text.translate(_UP)


def _items(raw) -> list | None:
    if raw is None or raw == "" or raw == []:
        return []
    if isinstance(raw, str):
        return raw.replace(",", " ").split()
    return list(raw) if isinstance(raw, (list, tuple)) else None


def _off(raw) -> set:
    """The entries the site counts as pages again; an unreadable value is none."""
    items = _items(raw)
    if items is None or not all(isinstance(i, str) and i.strip() in RULES for i in items):
        return set()
    return {i.strip() for i in items}


def _good(entry: str) -> bool:
    if not entry or len(entry) > 100 or ".." in entry or "#" in entry:
        return False
    if any(not (33 <= ord(c) <= 126) for c in entry):
        return False
    if entry[0] == "?":
        return 1 <= len(entry) - 1 <= 60 and all(c in _KEY_CHARS for c in entry[1:])
    if entry[0] != "/":
        return False
    body = entry[:-1] if entry[-1] == "*" else entry
    return "*" not in body and "?" not in body and body.replace("/", "") != ""


def _extra(raw) -> list:
    """The site's own entries, each once; an unreadable value (or more than
    20 entries) is none."""
    items = _items(raw)
    if items is None or not all(isinstance(i, str) and _good(i.strip()) for i in items):
        return []
    out = []
    for item in items:
        if item.strip() not in out:
            out.append(item.strip())
    return out if len(out) <= 20 else []


class Marker:
    """(path, url) -> the entry that makes it no page, or "". Callable."""

    def __init__(self, config: dict | None = None) -> None:
        site = (config or {}).get("site") or {}
        off = _off(site.get("not_pages_off"))
        self.names = [n for n in DEFAULT if n not in off]
        self.extra = _extra(site.get("not_pages_extra"))

    def __call__(self, path: str, url: str) -> str:
        low = _low(path)
        segments = [s for s in low.split("/") if s]
        bare = low.rstrip("/")
        query = url.split("?", 1)[1].split("#", 1)[0] if "?" in url else ""
        pairs = []
        for part in (query.split("&") if query else []):
            key, _, value = part.partition("=")
            pairs.append((_low(key), value, "=" in part))
        keys = {k for k, _, _ in pairs}
        for name in self.names:
            shapes = RULES[name][1]
            if any(bare.endswith(end) for end in shapes.get("ends", ())):
                return name
            for tail in shapes.get("tails", ()):
                if len(segments) >= len(tail) and tuple(segments[-len(tail):]) == tail:
                    return name
            if any(seg in segments for seg in shapes.get("segments", ())):
                return name
            if any(key in keys for key in shapes.get("keys", ())):
                return name
            for key, value, has in pairs:
                if has and key in shapes.get("numbers", ()) and value \
                        and all(c in string.digits for c in value):
                    return name
        for entry in self.extra:
            if entry[0] == "?":
                if _low(entry[1:]) in keys:
                    return f"{OWN}: {entry}"
            elif entry[-1] == "*":
                if low.startswith(_low(entry[:-1])):
                    return f"{OWN}: {entry}"
            elif bare == _low(entry).rstrip("/"):
                return f"{OWN}: {entry}"
        return ""


STANDARD = Marker()
