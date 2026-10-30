"""What Settings > Leads & tools says about each hook's key (2.44.1): when it was
saved, by whom and how, and what has arrived since, so the screen can tell
"the address works" (a test of Skald's own) from "the key works" (a real
delivery the saved key verified).

    saved(accounts_db, site, tool) -> {saved_at, saved_by, saved_how}
        from the newest `hook.secret` audit row that saved a key for the hook
        ("made", "rotated", "pasted", "pasted, replaced", "made from a shared
        link", an AI agent's "made"/"pasted"; a pack that only copied the key
        saved nothing). saved_by is a display name, never an email: the
        member's name (none set: null), "an AI agent", "your developer (a
        shared link)", "the command line". saved_how: "made by Skald" or
        "pasted". All null when no row says (a key set from the command line
        or the environment, or before the audit log).
    facts(accounts_db, conversions_db, folder, site, tool, now) -> the tools
        list's fields: key_word, saved_at, saved_by, saved_how, last_real,
        since_saved, held (roads.last_real, roads.since_saved, held.count)

Reads only. No figure here is a result: the counts are facts about the
delivery log, which the audit recounts (audit_hooks_held.py).
"""
from __future__ import annotations

import time

from .conversions import held, roads

MADE = ("made", "rotated")
PASTED = ("pasted",)


def _how(detail: str) -> str | None:
    detail = str(detail or "").strip().lower()
    if detail.startswith(PASTED):
        return "pasted"
    if detail.startswith(MADE):
        return "made by Skald"
    return None                          # copied into a pack, a link: nothing saved


def _who(actor: str, name) -> str | None:
    actor = str(actor or "")
    if actor.isdigit():
        return (str(name).strip() or None) if name else None
    if actor == "ai-agent":
        return "an AI agent"
    if actor.startswith("link:"):
        return "your developer (a shared link)"
    if actor == "cli":
        return "the command line"
    return None


NONE = {"saved_at": None, "saved_by": None, "saved_how": None}


def saved(db, site: str, tool: str) -> dict:
    """{saved_at, saved_by, saved_how} of the hook's key, null when unknown."""
    if db is None:
        return dict(NONE)
    try:
        rows = db.execute(
            "SELECT a.at, a.actor, a.detail, u.name FROM audit a LEFT JOIN users u ON "
            "a.actor GLOB '[0-9]*' AND u.id = CAST(a.actor AS INTEGER) WHERE a.action = "
            "'hook.secret' AND a.target = ? ORDER BY a.id DESC LIMIT 50",
            (f"{site}/{tool}",)).fetchall()
    except Exception:                    # noqa: BLE001 - no accounts tables: not known
        return dict(NONE)
    for at, actor, detail, name in rows:
        how = _how(detail)
        if how:
            return {"saved_at": at, "saved_by": _who(actor, name), "saved_how": how}
    return dict(NONE)


def facts(accounts_db, conv_db, folder, site: str, tool: str,
          now: float | None = None, keeps: bool = False) -> dict:
    """The tools list's key fields for one hook (the module's docstring)."""
    got = saved(accounts_db, site, tool)
    return {"key_word": roads.key_word(tool), **got,
            "last_real": roads.last_real(conv_db, site, tool),
            "since_saved": roads.since_saved(conv_db, site, tool, got["saved_at"]),
            "held": held.count(folder, site, tool, time.time() if now is None else now, keeps)
            if folder is not None else 0}
