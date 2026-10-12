"""A new site's page, there the moment the site is made.

A site added in Settings > Sites, or by sign-up, has no page until a run
draws one, so its address answered nginx's 404 for a few minutes. Right
after the site is made, `start`:

  1. writes a small "Getting ready" index.html in its folder of the
     dashboard's output, only when no page is there yet. It says what is
     happening and reloads itself every RELOAD seconds; it holds no figure.
  2. draws the real page on a thread: `skald --config <file> --site <site>
     dashboard --out <out>`, the same build the runs make, one at a time,
     at most TIMEOUT seconds. The next live run draws it anyway if this
     fails; a failure is noted, never raised.

Nothing here fails the request that made the site.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from html import escape
from pathlib import Path

from .files import slug, write_atomic

RELOAD = 15
TIMEOUT = 300
ROOT = Path(__file__).resolve().parent.parent
RUN = subprocess.run              # tests replace it
_ONE_AT_A_TIME = threading.Lock()

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="{reload}">
<meta name="robots" content="noindex">
<title>{site}: getting ready</title>
<style>
:root{{color-scheme:light dark;--bg:#f7f7f5;--ink:#1d1d1b;--mute:#5f5f5a;--rule:#deded8}}
@media (prefers-color-scheme:dark){{
:root{{--bg:#151514;--ink:#ecece8;--mute:#a3a39c;--rule:#33332f}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}
main{{max-width:34rem;margin:12vh auto;padding:0 16px}}
h1{{font-size:1.3rem;margin:0 0 .6rem}}
p{{margin:.5rem 0;color:var(--mute)}}
.box{{border:1px solid var(--rule);border-radius:10px;padding:18px 20px}}
a{{color:inherit}}
</style></head>
<body><main><div class="box" role="status">
<h1>Getting ready: {site}</h1>
<p>Skald is drawing this site's first page. This page reloads itself; the dashboard
appears here within minutes.</p>
<p>Figures come once the site's log lines arrive (and, where it is asked for, once
the domain is verified in Settings &gt; Sites).</p>
<p><a href="/traffic/">All sites</a></p>
</div></main></body></html>
"""


def placeholder(out, site: str) -> Path | None:
    """Write the "Getting ready" page for `site` when it has no page yet.
    The path written, or None (no output folder, a page already there, or
    the folder cannot be written)."""
    if out is None or not site:
        return None
    page = Path(out) / slug(site) / "index.html"
    if page.exists():
        return None
    try:
        write_atomic(page, PAGE.format(site=escape(site), reload=RELOAD))
    except OSError:
        return None
    return page


def command(config_path, site: str, out) -> list[str]:
    cmd = [sys.executable, str(ROOT / "bin/skald"), "--config", str(config_path), "--site", site,
           "dashboard"]
    return cmd + (["--out", str(out)] if out is not None else [])


def build(config_path, site: str, out) -> bool:
    """Draw `site`'s pages now (blocking). True when the build worked."""
    with _ONE_AT_A_TIME:
        try:
            done = RUN(command(config_path, site, out), cwd=str(ROOT), timeout=TIMEOUT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except (OSError, subprocess.SubprocessError):
            return False
    return getattr(done, "returncode", 1) == 0


def start(out, site: str, config_path=None) -> threading.Thread | None:
    """The placeholder now, then the real build on a thread (when the
    config file is known). The thread, or None when no build was started."""
    placeholder(out, site)
    if config_path is None or out is None:
        return None
    from .auth_api import note, spawn

    def work():
        try:
            if not build(config_path, site, out):
                note("a new site's first page: the build did not finish; the next run draws it")
        except Exception as why:      # noqa: BLE001 - a thread must never take the helper down
            note(f"a new site's first page: {type(why).__name__}")
    return spawn(work)
