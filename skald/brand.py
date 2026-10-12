"""The tool's name, version and tagline, from one place.

The package, its paths, cron entries and services keep the name
skald; what a reader sees - the mail's sender name, subject prefix
and footer, the report header - says the brand. It is read from:

  build.json   written at deploy beside the code (tools/build-info.sh): name,
               version, tagline, release (commit count), commit, deployed_at
  NAME, VERSION, TAGLINE
               the repository's own files, when there is no build.json (a
               checkout, the tests); release and commit are then unknown

so renaming the tool is a change to NAME and nothing else.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FALLBACK = {"name": "skald", "version": "", "tagline": ""}


def _text(path: Path) -> str:
    try:
        return " ".join(path.read_text(encoding="utf-8").split())
    except OSError:
        return ""


@lru_cache(maxsize=4)
def load(root: Path = ROOT) -> dict:
    """{"name","version","tagline","release","commit","deployed_at"}."""
    out = {**FALLBACK, "release": None, "commit": None, "deployed_at": None}
    for key, file in (("name", "NAME"), ("version", "VERSION"), ("tagline", "TAGLINE")):
        got = _text(Path(root) / file)
        if got:
            out[key] = got
    try:
        built = json.loads((Path(root) / "build.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        built = None
    if isinstance(built, dict):
        for key in out:
            if built.get(key) not in (None, ""):
                out[key] = built[key]
    return out


def line(b: dict | None = None) -> str:
    """"Skald v1.0.0 · release 57 · Every visit, truly told." (parts missing
    are left out)."""
    b = b or load()
    parts = [b["name"] + (f" v{b['version']}" if b["version"] else "")]
    if b.get("release") is not None:
        parts.append(f"release {b['release']}")
    if b["tagline"]:
        parts.append(b["tagline"])
    return " · ".join(parts)


def prefix(b: dict | None = None) -> str:
    """The subject prefix when the config sets none: "[Skald]"."""
    return f"[{(b or load())['name']}]"


def cmd_version(ctx) -> int:
    b = load()
    if getattr(ctx.args, "json", False):
        ctx.out(json.dumps(b))
    else:
        ctx.out(line(b) + (f"  (commit {b['commit']}, deployed {b['deployed_at']})"
                           if b.get("commit") else ""))
    return 0


def add_command(sub) -> None:
    p = sub.add_parser("version", help="the name, version and release deployed")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_version)
