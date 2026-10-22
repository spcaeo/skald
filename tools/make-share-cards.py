#!/usr/bin/env python3
"""Make the skaldanalytics.com share cards (1200 x 630 PNG, the Open Graph and X images).

    python3 tools/make-share-cards.py          # all four, from _src/check-news.json
    python3 tools/make-share-cards.py check    # one

Each card is an HTML template in deployments/skaldanalytics.com/site/_src/share/, filled
from check-news.json (the story's name, badge, one line, fixed versions, timeline,
sources), so the next advisory makes new cards by changing that file only. Rendered by
headless Chrome's own command line (no Python package needed): Chrome from $CHROME, else
the usual places. A card over MAX_BYTES is reduced to a 256-colour palette when Pillow is
installed (optional), else the script says so.

Writes site/img/share-check.png, share-php2shell.png, share-security.png and
share-ai-key-thief.png (the story: the hero's last frame, drawn from the log). Run it, look at
them, commit them. Not part of the tests; tests check the tags and the images' sizes.
"""
from __future__ import annotations

import html
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "deployments" / "skaldanalytics.com" / "site"
SRC = SITE / "_src"
MAX_BYTES = 300 * 1024
CHROMES = [os.environ.get("CHROME") or "",
           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
           "/Applications/Chromium.app/Contents/MacOS/Chromium",
           shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chromium-browser") or ""]
MARK = ('<svg viewBox="0 0 64 64" width="40" height="40" aria-hidden="true"><rect width="64" height="64" rx="15" '
        'fill="#f3f6f9"/><path d="M20 14.5 27 11v41l-7 3.5z" fill="#0b1016"/><g fill="#0b1016" stroke="#f3f6f9" '
        'stroke-width="3" stroke-linejoin="round" paint-order="stroke"><path d="M25 41C28 29 38 17 51 10c-2 9-6 '
        '16-11 21l-3.5-.5 1.5 3c-3 3.5-7 7-10.5 9.5z"/><path d="M24.6 39.2l3.6 3.2L11.5 56.5z"/></g><path '
        'd="M27.5 41.2 48.5 13.5" stroke="#f3f6f9" stroke-width="1.6" stroke-linecap="round" fill="none"/></svg>')


def chrome() -> str:
    for path in CHROMES:
        if path and Path(path).exists():
            return path
    sys.exit("No Chrome found: set CHROME to its path.")


def fill(template: str, news: dict) -> str:
    e = html.escape
    share = news["share"]
    out = template.replace("{{MARK}}", MARK).replace("{{NAME}}", e(news["name"]))
    out = out.replace("{{BADGE}}", e(share["badge"])).replace("{{LINE}}", e(share["line"]))
    out = out.replace("{{FIXED_CHIPS}}", "".join(f'<span class="chip">{e(v)}</span>' for v in share["fixed"]))
    out = out.replace("{{STEPS}}", "".join(f'<div class="step"><b>{e(d)}</b><span>{e(w)}</span></div>'
                                           for d, w in share["timeline"]))
    out = out.replace("{{SOURCES}}", e(share["sources"])).replace("{{SHOT}}", "security-exposed-light.webp")
    if "{{THIEF_ART}}" in out:
        out = out.replace("{{THIEF_ART}}", thief_art())
    return out


def thief_art() -> str:
    """The story card's picture: the hero's last frame, drawn by the site's own thief_hero.py from
    the scanner's log (so the keys and their stamps are the log's)."""
    sys.path.insert(0, str(SRC))
    import thief_hero
    import thief_log
    reqs = thief_log.parse()
    return thief_hero.card_art(thief_log.facts(reqs), reqs)


def png_size(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()[:24]
    return struct.unpack(">II", raw[16:24])


def shrink(path: Path) -> None:
    if path.stat().st_size <= MAX_BYTES:
        return
    try:
        from PIL import Image
    except ImportError:
        print(f"  {path.name} is {path.stat().st_size // 1024} KB (over {MAX_BYTES // 1024}); install Pillow to shrink it")
        return
    Image.open(path).convert("RGB").quantize(colors=256, dither=Image.Dither.FLOYDSTEINBERG).save(path, optimize=True)


def main() -> int:
    news = json.loads((SRC / "check-news.json").read_text(encoding="utf-8"))
    browser = chrome()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copy(SRC / "share" / "card.css", work / "card.css")
        shot = SITE / "img" / "security-exposed-light.webp"         # the security card only
        if shot.exists():
            shutil.copy(shot, work / shot.name)
        for name in [a for a in sys.argv[1:] if not a.startswith("-")] or ["check", "php2shell", "security", "ai-key-thief"]:
            page = work / f"{name}.html"
            page.write_text(fill((SRC / "share" / f"{name}.html").read_text(encoding="utf-8"), news), encoding="utf-8")
            out = SITE / "img" / f"share-{name}.png"
            subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=1", "--window-size=1200,630",
                            f"--screenshot={out}", page.as_uri()], check=True, capture_output=True, timeout=60)
            shrink(out)
            print(f"{out.relative_to(ROOT)}: {png_size(out)}, {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
