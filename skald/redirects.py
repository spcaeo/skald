"""The site's own old-URL map, read so a 404 that is now handled says so.

`report.redirect_map` names a copy of the website's legacy-urls.ts (on the
server /etc/skald/legacy-urls.ts). It is read as data, never run:
the quoted paths inside LEGACY_REDIRECTS ("old": "new"), LEGACY_GONE and
LEGACY_GONE_PREFIXES. No file, or no such names: every 404 is "open".
"""
from __future__ import annotations

import re
from pathlib import Path

_BLOCK = re.compile(r"export const (LEGACY_[A-Z_]+)[^=]*=\s*([\[{])(.*?)[\]}];", re.S)
_PAIR = re.compile(r'"([^"]+)"\s*:\s*"([^"]+)"')
_ITEM = re.compile(r'"([^"]+)"')
_COMMENT = re.compile(r"//[^\n]*")


class RedirectMap:
    def __init__(self, redirects=None, gone=(), prefixes=()) -> None:
        self.redirects = dict(redirects or {})
        self.gone = set(gone)
        self.prefixes = tuple(prefixes)

    @classmethod
    def load(cls, path) -> "RedirectMap":
        if not path:
            return cls()
        try:
            text = Path(str(path)).read_text()
        except OSError:
            return cls()
        redirects, gone, prefixes = {}, [], []
        for name, _, body in _BLOCK.findall(text):
            body = _COMMENT.sub("", body)
            if name == "LEGACY_REDIRECTS":
                redirects.update(_PAIR.findall(body))
            elif name == "LEGACY_GONE":
                gone += _ITEM.findall(body)
            elif name == "LEGACY_GONE_PREFIXES":
                prefixes += _ITEM.findall(body)
        return cls(redirects, gone, prefixes)

    def state(self, path: str) -> tuple[str, str]:
        """("redirected", to) / ("gone", "") / ("", "") for a path, with or
        without its trailing slash."""
        for candidate in (path, path if path.endswith("/") else path + "/"):
            if candidate in self.redirects:
                return "redirected", self.redirects[candidate]
            if candidate in self.gone:
                return "gone", ""
        if any(path.startswith(p) for p in self.prefixes):
            return "gone", ""
        return "", ""
