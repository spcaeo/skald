"""A URL's host as urllib reads it, never raising: log lines are not trusted.

urlsplit raises ValueError on a host part holding "[" or "]" that is not an
IPv6 address. A scanner's referrer "{[RootURL]}/admin/more.html" stopped a
site's live count on every round (#61). Such a URL has no host here. The
audits read hosts on their own road (audit_labels._host_of), same rule.
"""
from __future__ import annotations

from urllib.parse import SplitResult, urlsplit

NOTHING = SplitResult("", "", "", "", "")


def host_of(url: str) -> str:
    """The host, lower case, or "" when there is none or urllib cannot split it."""
    try:
        return (urlsplit(url).hostname or "").lower() if url else ""
    except ValueError:
        return ""


def split(url: str) -> SplitResult:
    """urlsplit, or every part empty when urllib cannot split the URL."""
    try:
        return urlsplit(url)
    except ValueError:
        return NOTHING
