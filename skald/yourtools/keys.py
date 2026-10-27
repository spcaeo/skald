"""Where each tool's key lives, per site. Never in config.yml, never in the repo,
never in an answer, a log or the audit log.

A site's key for a tool is found, in this order (as a hook's secret is,
conversions/secrets_store.py, and the Search Console key, search/google.py):

  1. an environment variable the config names:
       your_tools:
         example.com/ga4: SKALD_TOOL_GA4_EXAMPLE
     (flat, readable by the small parser too) or, nested (PyYAML):
       your_tools:
         example.com:
           ga4: {key_env: SKALD_TOOL_GA4_EXAMPLE}
  2. secrets.json beside the history (0600; `hooks.secrets` moves it), key
     "tools/<site>/<tool>": what Settings > Leads & tools, the CLI or an AI
     agent's line (kit/agent_tools.py) kept;
  3. for a tool that may share a key (GA4: `shares_key = "search"`), when the
     connection's option `key` is "search": the install's Search Console key
     (search/google.find_key), the same Google robot.

A file others can read is refused (secrets_store.Exposed), never used.
"""
from __future__ import annotations

import os
from pathlib import Path

from ..conversions import secrets_store

SECTION = "your_tools"
SHARED = "search"                       # options["key"]: use the Search Console key


def secret_name(site: str, tool: str) -> str:
    return f"tools/{site}/{tool}"


def env_name(config: dict, site: str, tool: str) -> str | None:
    """The environment variable the config names for this site's tool key."""
    got = (config or {}).get(SECTION) or {}
    if not isinstance(got, dict):
        return None
    flat = got.get(f"{site}/{tool}")
    if isinstance(flat, str) and flat:
        return flat
    per_site = got.get(site)
    if isinstance(per_site, dict):
        entry = per_site.get(tool)
        if isinstance(entry, dict) and entry.get("key_env"):
            return str(entry["key_env"])
        if isinstance(entry, str) and entry:
            return entry
    return None


def path(config: dict, folder) -> Path | None:
    from ..settings_store import secrets_path
    return secrets_path(config, folder)


def find(config: dict, folder, site: str, tool: str, options: dict | None = None
         ) -> tuple[str | None, str]:
    """(the key's text, where it lives): "env NAME", "file", "search console key",
    or "" when there is none. Raises secrets_store.Exposed for a file others
    can read."""
    name = env_name(config, site, tool)
    if name:
        value = os.environ.get(name, "").strip()
        return (value or None), f"env {name}"
    where = path(config, folder)
    if where is not None:
        value = secrets_store.load(where).get(secret_name(site, tool))
        if value:
            return str(value), "file"
    from . import get
    adapter = get(tool)
    if adapter is not None and adapter.shares_key == SHARED and \
            (options or {}).get("key") == SHARED:
        from ..search import google
        text, _ = google.find_key(config, folder)
        return (text, "search console key") if text else (None, "")
    return None, ""


def state(config: dict, folder, site: str, tool: str, options: dict | None = None) -> dict:
    """What a screen may show: {"set", "where", "who", "problem"}. Never the key."""
    from . import get
    adapter = get(tool)
    try:
        text, where = find(config, folder, site, tool, options)
    except secrets_store.Exposed:
        return {"set": False, "where": "file", "who": None,
                "problem": "secrets.json can be read by others; it must be 0600."}
    if not text:
        return {"set": False, "where": where, "who": None,
                "problem": "The environment variable is empty." if where.startswith("env")
                else None}
    if adapter is None:
        return {"set": True, "where": where, "who": None, "problem": "Skald has no such tool."}
    try:
        info = adapter.check_key(text)
    except ValueError as why:
        return {"set": True, "where": where, "who": None, "problem": str(why)}
    return {"set": True, "where": where, "who": info.get("who"), "problem": None}


def put(config: dict, folder, site: str, tool: str, text: str) -> None:
    """Keep a checked key in secrets.json (0600, under its lock). OSError when
    the server has no secrets file; secrets_store.Exposed when it is not private."""
    where = path(config, folder)
    if where is None:
        raise OSError("the server has no secrets file")
    secrets_store.put(where, secret_name(site, tool), text)


def remove(config: dict, folder, site: str, tool: str) -> bool:
    """Take a site's tool key out of secrets.json. True when one was there."""
    where = path(config, folder)
    return bool(where is not None and secrets_store.delete(where, [secret_name(site, tool)]))


def in_env(config: dict, site: str, tool: str) -> bool:
    """The key is kept in the server's environment: no screen may change it."""
    return env_name(config, site, tool) is not None
