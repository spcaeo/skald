"""The audit's own check of the app's slim copies (slim.py).

Written apart from slim.py: it shares no code with it. A slim copy may leave
parts out, never change, add or reorder anything. So, walking the copy beside
the full file:

  * every key in the copy is in the full file, with the same value (a number
    is the same number, a string the same string);
  * every list in the copy has as many items as the full file's, in the same
    order (every row kept: no total can differ);
  * the copy's own `slim` note is the only key the full file lacks;
  * the totals the app shows are the same, counted again from the rows:
    not_found's days' totals, pages' views, readers, entries and exits over
    every page, page_index's pages.

Any problem: the copy is not written and the app reads the full file.
"""
from __future__ import annotations

NOTE = "slim"


def _walk(full, part, where: str, out: list[str]) -> None:
    if isinstance(part, dict):
        if not isinstance(full, dict):
            out.append(f"{where}: an object where the file has {type(full).__name__}")
            return
        for k, v in part.items():
            if where == "" and k == NOTE:
                continue
            if k not in full:
                out.append(f"{where}.{k}: not in the file")
                continue
            _walk(full[k], v, f"{where}.{k}", out)
    elif isinstance(part, list):
        if not isinstance(full, list) or len(full) != len(part):
            out.append(f"{where}: {len(part)} items, the file has "
                       f"{len(full) if isinstance(full, list) else type(full).__name__}")
            return
        for i, (a, b) in enumerate(zip(full, part)):
            _walk(a, b, f"{where}[{i}]", out)
    elif type(part) is not type(full) or part != full:
        out.append(f"{where}: {part!r}, the file has {full!r}")


def _sum(rows, key):
    """The rows' figure added up; text where a number should be counts as a problem."""
    total = 0
    for r in rows or []:
        v = r.get(key) if isinstance(r, dict) else None
        if isinstance(v, bool) or (v is not None and not isinstance(v, (int, float))):
            return f"not a number: {v!r}"
        total += v or 0
    return total


def _totals(body: dict) -> dict:
    """What the app shows from each file, counted from its rows."""
    out = {}
    for d in body.get("days") or []:
        if isinstance(d, dict) and isinstance(d.get("totals"), dict):
            out[f"day {d.get('day')}"] = d["totals"]
    for k in ("views", "readers", "entries", "exits", "ai_asked"):
        out[f"pages {k}"] = _sum(body.get("pages"), k)
    out["rows"] = len(body.get("pages") or []) + len(body.get("paths") or []) + len(body.get("days") or [])
    return out


def problems(full: dict, slim: dict) -> list[str]:
    """Why the slim copy is not the full file's (empty: it is)."""
    out: list[str] = []
    if not isinstance(slim.get(NOTE), dict):
        out.append("no slim note")
    _walk(full, slim, "", out)
    if _totals(full) != _totals(slim):
        out.append("the totals differ")
    return out[:20]
