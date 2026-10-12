"""The dashboard web app: copied beside the static pages on every run.

The app is static files - one HTML shell, a stylesheet and ES modules - that
read the JSON the data layer writes beside each page. Nothing is built and
nothing is fetched from outside: the files in this folder are the app.

Layout in dashboard.out, when `dashboard.app` is on:

    _app/app.css, _app/js/...      shared by every site (no site is named _app)
    <site>/index.html              the app's shell
    <site>/classic.html            the static page, for a browser without script;
                                   the shell sends such a browser there itself

Every file is written atomically, and a file left in _app/ by an older
version is removed, so a reader never gets a mix of two versions' modules.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..files import slug, write_atomic

HERE = Path(__file__).resolve().parent
SHARED = "_app"
ASSETS = ("app.css", "features.css", "compare.css", "screens.css", "nav.css", "drawer.css", "js")
CLASSIC = "classic.html"


def _assets() -> list[Path]:
    found = []
    for name in ASSETS:
        path = HERE / name
        found += sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    return [p for p in found if p.suffix in (".css", ".js")]


def _version() -> str:
    """The deployed commit, from build.json beside the code (tools/build-info.sh);
    "dev" in a checkout without one. The shell asks for its assets with it,
    so a browser never pairs a new page with an old stylesheet or script."""
    try:
        return re.sub(r"[^0-9A-Za-z._-]", "", str(json.loads((HERE.parents[1] / "build.json").read_text())["commit"])) or "dev"
    except (OSError, ValueError, KeyError, TypeError):
        return "dev"


def install(out: Path, sites: list[str]) -> list[Path]:
    """Copy the app into `out` and write each site's shell. Paths written."""
    out = Path(out)
    written = []
    shared = out / SHARED
    keep = set()
    for src in _assets():
        rel = src.relative_to(HERE)
        dest = shared / rel
        write_atomic(dest, src.read_text(encoding="utf-8"))
        keep.add(dest)
        written.append(dest)
    if shared.is_dir():
        for old in shared.rglob("*"):
            if old.is_file() and old not in keep:
                old.unlink()
    shell = (HERE / "index.html").read_text(encoding="utf-8")
    v = _version()
    shell = re.sub(r'((?:href|src)="\.\./_app/[^"?]+\.(?:css|js))"', rf'\1?v={v}"', shell)
    for site in sites:
        page = out / slug(site) / "index.html"
        write_atomic(page, shell)
        written.append(page)
    return written
