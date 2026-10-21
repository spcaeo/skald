"""Security advisories set against a site's stack (Security > Your stack, 2.21).

The list is `skald/data/advisories.json`, shipped with each release. Nothing is
fetched unless `security.advisories_fetch` is on (off by default): then the daily run may
fetch the public repo's copy of the same file (ADVISORIES_URL) through the safe fetcher,
and a copy that is valid and newer than the shipped one is kept beside the history
(`advisories.json`) and used instead.

An advisory (docs/DATA-CONTRACT-SECURITY.md, "Advisories"):

  id, product ("php", "nodejs", ...), cves, title, severity, score, published,
  branch       "minor" (8.4) or "major" (22): how a version names its branch
  fixed        {branch: the first fixed version}
  no_fix_below a branch below which there is no official fix
  no_fix_words, affected, summary, action, mitigations [..], mitigations_note, sources [url]

`match(products)` sets each detected product (stack.py) against every advisory for it:

  update needed     a version below its branch's fixed one
  fixed             at or above it (kept, never shown as a warning)
  no official fix   a branch below `no_fix_below`, or one the advisory does not list
                    that is older than the newest it does
  check your version the product is there but its server does not show the version
  not listed        a branch newer than every listed one

The second count is audit_stack.py: it reads the same file and compares versions by its
own code.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SHIPPED = Path(__file__).resolve().parent / "data" / "advisories.json"
ADVISORIES_URL = ("https://raw.githubusercontent.com/spcaeo/skald/main/"
                  "skald/data/advisories.json")
LOCAL = "advisories.json"
STATES = ("update_needed", "no_fix", "check_version", "fixed", "not_listed")
WORDS = {"update_needed": "Update needed", "no_fix": "No official fix: upgrade the branch",
         "check_version": "Check your version", "fixed": "Fixed", "not_listed": "Not listed"}
FIELDS = ("id", "product", "title", "severity", "published", "branch", "fixed", "sources")


def valid(doc) -> bool:
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        return False
    items = doc.get("advisories")
    if not isinstance(items, list):
        return False
    for a in items:
        if not isinstance(a, dict) or any(k not in a for k in FIELDS):
            return False
        if a["branch"] not in ("major", "minor") or not isinstance(a["fixed"], dict):
            return False
        if not all(str(u).startswith("https://") for u in a["sources"]):
            return False
    return True


def load(folder=None) -> dict:
    """The list in use: the shipped one, or a valid newer copy kept beside the history."""
    doc = json.loads(SHIPPED.read_text())
    if folder is not None:
        try:
            other = json.loads((Path(folder) / LOCAL).read_text())
        except (OSError, ValueError):
            other = None
        if valid(other) and str(other.get("updated", "")) > str(doc.get("updated", "")):
            return other
    return doc


def version(text: str) -> tuple[int, ...] | None:
    got = re.match(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(text or ""))
    return tuple(int(x) for x in got.groups() if x is not None) if got else None


def branch_of(ver: tuple, how: str) -> tuple:
    return ver[:2] if how == "minor" else ver[:1]


def judge(advisory: dict, ver_text: str | None) -> str:
    """One product's state against one advisory."""
    if not ver_text:
        return "check_version"
    ver = version(ver_text)
    if ver is None:
        return "check_version"
    how = advisory["branch"]
    need = len(branch_of((0, 0), how))
    if len(ver) < need:
        return "check_version"
    mine = branch_of(ver, how)
    fixed = {branch_of(version(b) or (), how): version(v) for b, v in advisory["fixed"].items()}
    if mine in fixed:
        got = fixed[mine]
        return "fixed" if ver + (0,) * (3 - len(ver)) >= got + (0,) * (3 - len(got)) \
            else "update_needed"
    below = version(advisory.get("no_fix_below") or "")
    if below is not None and mine < branch_of(below, how):
        return "no_fix"
    if fixed and mine < max(fixed):
        return "no_fix"
    return "not_listed"


def match(products: list, doc: dict) -> list:
    """[{advisory id, product, host, version, state}] for every product an advisory names."""
    out = []
    for p in products:
        for a in doc.get("advisories") or []:
            if a["product"] != p.get("product"):
                continue
            out.append({"advisory": a["id"], "product": p["product"], "host": p.get("host"),
                        "version": p.get("version"), "state": judge(a, p.get("version"))})
    out.sort(key=lambda m: (STATES.index(m["state"]), m["advisory"], m["host"] or ""))
    return out


def refresh(config: dict, folder, fetch=None) -> str:
    """security.advisories_fetch: fetch the public list, keep a valid newer copy. Words."""
    on = ((config or {}).get("security") or {}).get("advisories_fetch")
    if not (on is True or str(on).strip().lower() in ("1", "true", "yes", "on")):
        return "off"
    if fetch is None:
        from . import site_fetch
        fetch = lambda url: site_fetch.follow(url, "GET")[0]  # noqa: E731
    try:
        got = fetch(ADVISORIES_URL)
        doc = json.loads(got.body.decode("utf-8"))
    except Exception as why:            # noqa: BLE001 - the shipped list stays
        return f"not fetched ({type(why).__name__})"
    if not valid(doc):
        return "not valid; the shipped list stays"
    if str(doc.get("updated", "")) <= str(load().get("updated", "")):
        return "no newer list"
    from .files import write_atomic
    write_atomic(Path(folder) / LOCAL, json.dumps(doc, indent=1) + "\n")
    return f"kept the list of {doc.get('updated')}"
