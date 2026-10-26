"""The app's copies of the biggest data files (2.41): data/slim/<name>.json.

The web app opened a site by fetching every data file, and three of them grew
with the site: not_found.json (each day's every lost address), pages.json
(each page's count for every day, and its sources, countries and assistants)
and page_index.json (each page's every sitemap date). None of those parts is
drawn by the app. The slim copy is the same file without them:

  not_found   each day's `rows` (its totals stay; `paths`, the 30 days' list
              with trends, and today's rows stay whole)
  pages       each page's breakdowns: `daily`, `sources`, `countries`,
              `assistants` (also under `prev`); every count stays
  page_index  each page's `lastmod_seen`, and its milestones other than the
              first Google crawl and the first visitor

Every row is kept, in the same order, and every value kept is the full
file's: a projection, never a recount. Before a copy is written the audit
(audit_slim.py, its own walk) checks just that; a copy that does not match is
not written, and the app reads the full file instead. The full files are not
changed: the API, MCP and anyone reading data/<name>.json get all of it.
DATA-CONTRACT.md, "The app's slim copies".
"""
from __future__ import annotations

import json
from pathlib import Path

from .files import packed, write_atomic

FOLDER = "slim"
NAMES = ("not_found", "pages", "page_index")
PAGE_PARTS = ("daily", "sources", "countries", "assistants")
MILESTONES = ("googlebot", "human")


def _no_parts(row: dict) -> dict:
    out = {k: v for k, v in row.items() if k not in PAGE_PARTS}
    if isinstance(row.get("prev"), dict):
        out["prev"] = {k: v for k, v in row["prev"].items() if k not in PAGE_PARTS}
    return out


def not_found(body: dict) -> tuple[dict, list[str]]:
    days = [{k: v for k, v in d.items() if k != "rows"} if isinstance(d, dict) else d
            for d in body.get("days") or []]
    return {**body, "days": days}, ["days[].rows"]


def pages(body: dict) -> tuple[dict, list[str]]:
    out = {**body, "pages": [_no_parts(r) if isinstance(r, dict) else r
                             for r in body.get("pages") or []]}
    if isinstance(body.get("today"), dict) and isinstance(body["today"].get("pages"), list):
        out["today"] = {**body["today"], "pages": [_no_parts(r) if isinstance(r, dict) else r
                                                   for r in body["today"]["pages"]]}
    return out, [f"pages[].{p}" for p in PAGE_PARTS] + [f"pages[].prev.{p}" for p in PAGE_PARTS]


def page_index(body: dict) -> tuple[dict, list[str]]:
    def row(r):
        if not isinstance(r, dict):
            return r
        out = {k: v for k, v in r.items() if k != "lastmod_seen"}
        if isinstance(r.get("milestones"), dict):
            out["milestones"] = {k: v for k, v in r["milestones"].items() if k in MILESTONES}
        return out
    return ({**body, "pages": [row(r) for r in body.get("pages") or []]},
            ["pages[].lastmod_seen", "pages[].milestones (all but googlebot, human)"])


PROJECT = {"not_found": not_found, "pages": pages, "page_index": page_index}


def path_of(folder: Path, name: str) -> Path:
    return Path(folder) / "data" / FOLDER / f"{name}.json"


def remove(path: Path) -> None:
    for p in (path, packed(path)):
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def write(folder: Path, name: str, body: dict) -> Path | None:
    """The slim copy of one data file, checked against it; None (and no copy
    left behind) when the file failed or the copy does not match."""
    from . import audit_slim
    path = path_of(folder, name)
    if name not in PROJECT or body.get("state") == "error":
        remove(path)
        return None
    slim, left = PROJECT[name](body)
    slim = {**slim, "slim": {"of": f"{name}.json", "left_out": left}}
    if audit_slim.problems(body, slim):
        remove(path)
        return None
    write_atomic(path, json.dumps(slim, ensure_ascii=False, separators=(",", ":")) + "\n", pack=True)
    return path


def listed(data_folder: Path) -> list[str]:
    """The slim copies beside a page's data (app.json `slim`)."""
    return sorted(p.stem for p in (Path(data_folder) / FOLDER).glob("*.json") if p.stem in NAMES)
