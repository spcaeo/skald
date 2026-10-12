"""Where the links in account mails point: one rule for the CLI
(`skald accounts`, cli_accounts.py) and the helper (auth_api.py, team_api.py).

In order: the CLI's --base-url when given; else `access.base_url`; else
`dashboard.base_url`; else the scheme and host of `dashboard.url`; else (the
helper only) the first --origin it was started with. Each is cut to its
scheme and host, since the account pages live at the root
(/traffic-auth/...). Never the request's Host header, which the asker
controls.
"""
from __future__ import annotations

from urllib.parse import quote, urlsplit

PREFIX = "/traffic-auth/"


def _origin(raw) -> str | None:
    """https://host[:port] of an address, or None when it is not one."""
    try:
        parts = urlsplit(str(raw or "").strip())
    except ValueError:
        return None
    if parts.scheme in ("https", "http") and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    return None


def base_url(config: dict | None, override: str | None = None,
             allowed=None) -> str | None:
    """The address links start with, or None when none is set. A given
    `override` that is not an address is None, never a quiet fallback."""
    if override:
        return _origin(override)
    config = config or {}
    for raw in (((config.get("access") or {}).get("base_url")),
                ((config.get("dashboard") or {}).get("base_url")),
                ((config.get("dashboard") or {}).get("url"))):
        got = _origin(raw) if raw else None
        if got:
            return got
    for origin in sorted(allowed or ()):
        got = _origin(origin)
        if got:
            return got
    return None


def link(base: str, page: str, token: str) -> str:
    """The full link for one account page ("reset", "invite")."""
    return f"{base}{PREFIX}{page}?t={quote(token, safe='')}"
