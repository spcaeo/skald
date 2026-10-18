"""Which Search Console property or Bing site belongs to which Skald site.

Search Console has two kinds of property: a Domain property
("sc-domain:example.com", every host and scheme under the domain) and a
URL-prefix property ("https://www.example.com/", that scheme and host and
the paths under it). Bing names a site by its address ("https://example.com/").

A property may be connected to a site only when it covers one of the site's
host names (`site.hosts`): one service account and one Bing key serve every
site of an install, so this is what stops one organisation's admin from
connecting another's property. A site with no host names set cannot be
checked; the CLI allows it (config.yml is the server owner's), the page does not.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

HOST = re.compile(r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?"
                  r"(?:\.[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?)+$")


class Invalid(ValueError):
    pass


def _url(value: str, what: str) -> str:
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not HOST.match(host) or parts.query \
            or parts.fragment or parts.username or parts.password:
        raise Invalid(f"{what} is an address like https://www.example.com/.")
    path = parts.path or "/"
    if not path.endswith("/"):
        path += "/"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{host}{port}{path}"


def google_property(value) -> str:
    """A property as Search Console names it, checked."""
    value = str(value or "").strip()
    if len(value) > 300 or any(ord(c) <= 0x20 for c in value):
        raise Invalid("A Search Console property is sc-domain:example.com or "
                      "https://www.example.com/.")
    if value.lower().startswith("sc-domain:"):
        domain = value.split(":", 1)[1].strip().lower().rstrip(".")
        if not HOST.match(domain):
            raise Invalid("A Domain property is sc-domain: and a domain, like sc-domain:example.com.")
        return f"sc-domain:{domain}"
    return _url(value, "A URL-prefix property")


def bing_site(value) -> str:
    value = str(value or "").strip()
    if len(value) > 300:
        raise Invalid("A Bing site is an address like https://www.example.com/.")
    return _url(value, "A Bing site")


def host_of(prop: str) -> tuple[str, bool]:
    """(host or domain, True for a Domain property)."""
    if prop.startswith("sc-domain:"):
        return prop.split(":", 1)[1], True
    return (urlsplit(prop).hostname or "").lower(), False


def covers(prop: str, hosts) -> bool:
    """Does the property (or Bing site) cover one of the site's hosts?"""
    host, domain = host_of(prop)
    for h in hosts or ():
        h = str(h).lower().split(":", 1)[0]
        if h == host or (domain and h.endswith("." + host)):
            return True
    return False


def matching(found: list[dict], hosts) -> list[dict]:
    """The properties from a sites listing that cover the site's hosts,
    Domain properties first."""
    out = [p for p in found if covers(str(p.get("siteUrl") or ""), hosts)]
    return sorted(out, key=lambda p: (not str(p["siteUrl"]).startswith("sc-domain:"),
                                      str(p["siteUrl"])))


def path_of(page: str) -> str:
    """A Search Console page (a full address) as the path Skald's landing
    pages use: no scheme, host, query or fragment."""
    parts = urlsplit(page)
    return parts.path or "/"
