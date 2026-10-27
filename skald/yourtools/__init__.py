"""From your tools: figures from a person's OWN marketing tools (Google Analytics 4,
and later Search Console's figures through the same Google connection, Vercel Web
Analytics, Calendly, Resend), each connected per site with the person's own key to
the tool's free API (the owner's decision, 2026-10-27; docs/TOOLS.md).

They are never Skald's count and never mixed into the log's figures: they sit in
their own "From your tools" area, every figure labelled with the tool's name.
Unknown stays unknown: a figure a tool did not give is NULL, never 0. No LLM is
ever called; only the tools' own APIs, with the person's own keys.

  base.py         the adapter interface: Adapter, Answer, Figure, Option, BadKey
  names.py        the name lists (tool ids, GA4's metric and dimension names): the
                  one thing recount.py shares with the code it checks
  keys.py         where each key lives: an environment variable the config names,
                  else secrets.json beside the history (0600), as the hooks' and the
                  Search Console key's
  conn.py         each site's connections and freshness, `yourtools/<site>.json`:
                  which tools are on, their options, when each last answered, and
                  the states answering / failing / stopped answering
  store.py        the raw-answer store, `yourtools.sqlite` beside the history: each
                  tool's answer exactly as it came, and the figures read from it,
                  each with the place in the answer it was read from
  sync.py         the sync (`skald tools sync`, the scheduler's low-priority job)
  recount.py      the second road: every figure shown, read again from the stored
                  answer by its own code
  api.py          the dashboard's routes (Settings > Leads & tools, Overview's card)
  tool_<id>.py    one adapter each (tool_ga4.py). A new tool is one such file and
                  its tests: `adapters()` finds it by its name.

The kit's route for an AI agent's key is kit/agent_tools.py (POST <code>/toolkey).
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

PREFIX = "tool_"
_FOUND: dict | None = None


def adapters() -> dict:
    """{tool id: its Adapter}, every tool_<id>.py in this package, in id order."""
    global _FOUND
    if _FOUND is None:
        found = {}
        for info in pkgutil.iter_modules([str(Path(__file__).resolve().parent)]):
            if not info.name.startswith(PREFIX):
                continue
            module = importlib.import_module(f"{__name__}.{info.name}")
            got = getattr(module, "ADAPTER", None)
            if got is not None and got.id == info.name[len(PREFIX):]:
                found[got.id] = got
        _FOUND = dict(sorted(found.items()))
    return _FOUND


def get(tool) -> object | None:
    """The adapter of a tool id, or None."""
    return adapters().get(str(tool or ""))


def register(adapter) -> None:
    """Add an adapter by hand (tests: a fake tool)."""
    adapters()[adapter.id] = adapter


def unregister(tool: str) -> None:
    adapters().pop(tool, None)
