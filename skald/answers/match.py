"""What one answer says about the site: the main road (the second is
audit_ai_answers.py, which shares only the name lists).

  mentioned     a brand term appears in the text as a whole word or phrase,
                any case ("Contoso" in "Contoso's plan", not in "Contosoville")
  mention_rank  1 + the number of competitors whose first mention comes
                before the brand's first mention; None when not mentioned
  own_pages     the paths of the cited URLs on the site's own hosts (a host
                or a subdomain of one, "www." ignored), query and fragment
                cut, "/" for none; a citation known only by its domain
                (Gemini's unresolved redirect) counts as the site cited with
                its page unknown: "(page not known)"
  cite_rank     the position, from 1, of the first own citation among the
                answer's cited URLs; None when none is the site's
  competitors   the competitors the answer names: a name as a whole word in
                the text, or, for a competitor written as a domain
                (example.org), that domain in the text or a cited URL on it
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

UNKNOWN_PAGE = "(page not known)"
DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")


def _pattern(term: str):
    return re.compile(r"(?<!\w)" + re.escape(term.strip()) + r"(?!\w)", re.IGNORECASE)


def first_at(text: str, term: str) -> int | None:
    """Where `term` first appears as a whole word or phrase, or None."""
    if not term or not term.strip():
        return None
    m = _pattern(term).search(text or "")
    return m.start() if m else None


def bare_host(host: str) -> str:
    host = (host or "").strip().lower().rstrip(".")
    host = host.split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def is_domain(name: str) -> bool:
    return bool(DOMAIN.match((name or "").strip().lower()))


def on_host(host: str, hosts) -> bool:
    host = bare_host(host)
    return bool(host) and any(host == h or host.endswith("." + h)
                              for h in (bare_host(x) for x in hosts) if h)


def citation_host(c: dict) -> tuple[str, bool]:
    """(host, page known) of a citation."""
    if c.get("domain"):
        return bare_host(c["domain"]), False
    return bare_host(urlsplit(c.get("url") or "").hostname or ""), True


def page_of(url: str) -> str:
    path = urlsplit(url).path or "/"
    return path[:300]


def analyse(text: str, citations: list[dict], brands, competitors, own_hosts) -> dict:
    text = text or ""
    brand_at = [p for p in (first_at(text, b) for b in brands) if p is not None]
    first_brand = min(brand_at) if brand_at else None
    named, comp_first = [], {}
    for name in competitors:
        at = first_at(text, name)
        if at is None and is_domain(name):
            at = next((10 ** 9 for c in citations if on_host(citation_host(c)[0], [name])), None)
        if at is not None and name not in comp_first:
            comp_first[name] = at
            named.append(name)
    rank = None
    if first_brand is not None:
        rank = 1 + sum(1 for at in comp_first.values() if at < first_brand)
    own, cite_rank = [], None
    for i, c in enumerate(citations, 1):
        host, known = citation_host(c)
        if not on_host(host, own_hosts):
            continue
        cite_rank = cite_rank or i
        page = page_of(c["url"]) if known else UNKNOWN_PAGE
        if page not in own:
            own.append(page)
    return {"mentioned": first_brand is not None, "mention_rank": rank, "own_pages": own,
            "cite_rank": cite_rank, "competitors": named}


def own_hosts(config: dict, brands) -> list[str]:
    """The site's hosts (site.hosts) and the brand terms written as domains."""
    from ..config import setting
    hosts = [str(h) for h in (setting(config or {}, "site", "hosts") or [])]
    hosts += [b for b in brands if is_domain(b)]
    out = []
    for h in hosts:
        h = bare_host(h)
        if h and h not in out:
            out.append(h)
    return out
