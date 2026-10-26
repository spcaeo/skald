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

Every address of the code carries the app's version, a hash of its files
(`?v=<hash>`): the shell's links and every import inside the modules, so a
browser may keep the code for a year (DEPLOY.md, Cache-Control) and a new
release is a new address. A file whose bytes did not change is not written
again (the live run installs the app every two minutes), and each has a gzip
copy beside it for nginx (gzip_static).
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from ..files import GZ_MIN, packed, slug, write_atomic

HERE = Path(__file__).resolve().parent
SHARED = "_app"
# vendor/: third-party code, copied as shipped (vendor/spcaeo-ui/VERSION.md says what and why).
ASSETS = ("app.css", "features.css", "compare.css", "screens.css", "nav.css", "drawer.css", "css", "js", "vendor")
CLASSIC = "classic.html"


def _assets() -> list[Path]:
    found = []
    for name in ASSETS:
        path = HERE / name
        found += sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    return [p for p in found if p.suffix in (".css", ".js")]


@lru_cache(maxsize=1)
def _version() -> str:
    """The app's version: a hash of its files (and the shell). Any change to the
    code is a new version, in a checkout as in a release, so a browser that kept
    the code never pairs a new page with an old stylesheet or script."""
    digest = hashlib.sha256()
    for path in [*_assets(), HERE / "index.html"]:
        digest.update(str(path.relative_to(HERE)).encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()[:12]


# A module's relative imports, as the app writes them: a static import or export
# (the statement's line starts with import, export or the "}" of a long list) and
# import("..."). Only "./" and "../" addresses of .js files.
_IMPORTS = (
    re.compile(r"""^(\s*(?:import|export|\})[^\n;]*?\bfrom\s*["'])(\.{1,2}/[^"'?]+\.js)(["'])""", re.M),
    re.compile(r"""^(\s*import\s*["'])(\.{1,2}/[^"'?]+\.js)(["'])""", re.M),
    re.compile(r"""(\bimport\(\s*["'])(\.{1,2}/[^"'?]+\.js)(["']\s*\))"""),
)


def versioned(code: str, v: str) -> str:
    """A module with `?v=<v>` on every relative import, so the whole module graph
    is fetched at this version's addresses (one copy of each module per page)."""
    for rx in _IMPORTS:
        code = rx.sub(lambda m: f"{m.group(1)}{m.group(2)}?v={v}{m.group(3)}", code)
    return code


@lru_cache(maxsize=1)
def static_graph(entry: str = "js/main.js") -> tuple[str, ...]:
    """Every module main.js loads before it runs (its static imports, and theirs),
    nearest first, as paths under the app ("js/ui.js"). The shell asks for all of
    them at once (modulepreload), rather than one level of imports at a time: seven
    levels deep, each a round trip on a slow line. import("...") is left out: those
    load when their screen opens."""
    seen, queue = [entry], [entry]
    while queue:
        rel = queue.pop(0)
        code = (HERE / rel).read_text(encoding="utf-8")
        for rx in _IMPORTS[:2]:
            for m in rx.finditer(code):
                dep = (HERE / rel).parent.joinpath(m.group(2)).resolve().relative_to(HERE.resolve()).as_posix()
                if dep not in seen and (HERE / dep).is_file():
                    seen.append(dep)
                    queue.append(dep)
    return tuple(seen[1:])


def _preloads(shell: str, v: str) -> str:
    """The shell with a modulepreload line for each module of main.js's graph."""
    tag = '<script type="module" src="../_app/js/main.js'
    links = "".join(f'<link rel="modulepreload" href="../_app/{rel}?v={v}">\n' for rel in static_graph())
    return shell.replace(tag, links + tag, 1) if tag in shell else shell


def _write(dest: Path, text: str) -> None:
    """Write the file and its gzip copy, unless it already holds these bytes."""
    try:
        same = dest.read_bytes() == text.encode("utf-8")
    except OSError:
        same = False
    if same and (packed(dest).exists() or len(text.encode("utf-8")) < GZ_MIN):
        return
    write_atomic(dest, text, pack=True)


def _in_flight(path: Path) -> bool:
    """A temp file write_atomic is writing (.<name>.<random>.tmp)."""
    return path.name.startswith(".") and path.name.endswith(".tmp")


def _stale(path: Path, minutes: int = 60) -> bool:
    import time
    try:
        return time.time() - path.stat().st_mtime > minutes * 60
    except FileNotFoundError:
        return False


def install(out: Path, sites: list[str]) -> list[Path]:
    """Copy the app into `out` and write each site's shell. Paths written."""
    out = Path(out)
    written = []
    shared = out / SHARED
    keep = set()
    v = _version()
    for src in _assets():
        rel = src.relative_to(HERE)
        dest = shared / rel
        text = src.read_text(encoding="utf-8")
        _write(dest, versioned(text, v) if src.suffix == ".js" else text)
        keep.update((dest, packed(dest)))
        written.append(dest)
    if shared.is_dir():
        for old in shared.rglob("*"):
            # Another run may be writing beside us (the live run every 2 minutes, a
            # site's daily run): its temp file is not ours to delete until it is
            # stale (2026-10-22: a deleted temp file failed one site's morning run).
            if not old.is_file() or old in keep or (_in_flight(old) and not _stale(old)):
                continue
            try:
                old.unlink()
            except FileNotFoundError:
                pass
    shell = (HERE / "index.html").read_text(encoding="utf-8")
    shell = re.sub(r'((?:href|src)="\.\./_app/[^"?]+\.(?:css|js))"', rf'\1?v={v}"', shell)
    shell = _preloads(shell, v)
    for site in sites:
        page = out / slug(site) / "index.html"
        _write(page, shell)
        written.append(page)
    return written
