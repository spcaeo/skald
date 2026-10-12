"""What a visit's first page says about where it came from, and campaigns.

From the landing URL and its referrer, and nothing else:

  utm          the five utm_ tags (source, medium, campaign, term, content)
  paid         the ad network a click id names - never the id itself
  ref_param    a ref=, source= or via= query value
  ref_host     the referring host (no "www.")
  ref_page     host + path, for other websites only: which article linked us.
               Search engines, assistants and social sites give the host only
  search_terms q= or query= in the referrer, when a search engine sent one

Every other query parameter is dropped here, before anything is stored: a
query string can carry an email address or a token.

`aggregate(journeys)` turns a day's journeys into campaigns.json rows: per
dimension, visits, pages loaded, 404s met and form posts (conversions).
Every dimension adds up to the visits, "(none)" included.
"""
from __future__ import annotations

from collections import Counter
from urllib.parse import parse_qsl, urlsplit

from . import dimensions as dim

UTM = ("source", "medium", "campaign", "term", "content")
CLICK_IDS = {"gclid": "Google Ads", "gbraid": "Google Ads", "wbraid": "Google Ads",
             "msclkid": "Microsoft Ads", "fbclid": "Meta", "li_fat_id": "LinkedIn",
             "ttclid": "TikTok", "twclid": "X"}
NONE = "(none)"
DIMENSIONS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
              "ref_host", "ref_page", "paid", "ref_param", "ai")
HOST_ONLY = ("AI assistant", "Search engine", "Social media", "Email")


def _query(url: str) -> dict[str, str]:
    if "?" not in url:
        return {}
    try:
        return {k.lower(): v for k, v in parse_qsl(url.split("?", 1)[1])[:60]}
    except ValueError:
        return {}


def _clean(value: str, limit: int = 60) -> str:
    return " ".join(str(value).split()).strip().lower()[:limit]


def fields(url: str, referrer: str, source: str) -> dict:
    """The campaign fields of a first page; empty strings when absent."""
    tags = _query(url)
    utm = {k: _clean(tags[f"utm_{k}"]) for k in UTM if tags.get(f"utm_{k}", "").strip()}
    paid = next((net for key, net in CLICK_IDS.items() if tags.get(key)), "")
    ref_param = next((_clean(tags[k]) for k in ("ref", "source", "via")
                      if tags.get(k, "").strip()), "")
    host = dim.referrer_host(referrer)[:60]
    page = terms = ""
    if host and source == "Other website":
        try:
            path = urlsplit(referrer).path or "/"
        except ValueError:
            path = "/"
        page = (host + path)[:120]
    if host and source == "Search engine":
        said = _query(referrer)
        terms = _clean(said.get("q") or said.get("query") or "", 100)
    if source == "This site":
        host = ""
    return {"utm": utm, "paid": paid, "ref_param": ref_param, "ref_host": host,
            "ref_page": page, "search_terms": terms}


def tagged(j: dict) -> bool:
    """A visit carrying a UTM tag, a click id or an AI source."""
    return bool(j.get("utm") or j.get("paid") or j.get("source") == "AI assistant")


def _names(j: dict) -> dict[str, str]:
    utm = j.get("utm") or {}
    out = {f"utm_{k}": utm.get(k) or NONE for k in UTM}
    out.update({
        "ref_host": j.get("ref_host") or NONE,
        "ref_page": j.get("ref_page") or NONE,
        "paid": j.get("paid") or NONE,
        "ref_param": j.get("ref_param") or NONE,
        "ai": j.get("via") if j.get("source") == "AI assistant" and j.get("via") else NONE,
    })
    return out


def aggregate(journeys: list[dict], top: int = 50) -> dict:
    """{"rows": {dimension: [row]}, "tagged": int, "visits": int}."""
    per: dict[str, dict[str, Counter]] = {d: {} for d in DIMENSIONS}
    tagged_n = 0
    for j in journeys:
        tagged_n += tagged(j)
        for d, name in _names(j).items():
            row = per[d].setdefault(name, Counter())
            row["visits"] += 1
            row["pages"] += int(j.get("pages", 0))
            row["not_found"] += 1 if j.get("not_found") else 0
            row["posts"] += 1 if j.get("posted") else 0
    rows = {}
    for d, names in per.items():
        ordered = sorted(names.items(), key=lambda kv: (kv[0] == NONE, -kv[1]["visits"], kv[0]))
        kept, rest = ordered[:top], ordered[top:]
        out = [{"name": n, **{k: int(c[k]) for k in ("visits", "pages", "not_found", "posts")}}
               for n, c in kept]
        if rest:
            tail = Counter()
            for _, c in rest:
                tail.update(c)
            out.append({"name": dim.OTHER, **{k: int(tail[k]) for k in
                                              ("visits", "pages", "not_found", "posts")}})
        rows[d] = out
    return {"rows": rows, "tagged": tagged_n, "visits": len(journeys)}


def merge(parts: list[dict]) -> dict:
    """Sum several days' campaigns blobs into one (same shape)."""
    per: dict[str, dict[str, Counter]] = {d: {} for d in DIMENSIONS}
    tagged_n = visits = 0
    for p in parts:
        tagged_n += int(p.get("tagged", 0))
        visits += int(p.get("visits", 0))
        for d, rows in (p.get("rows") or {}).items():
            for r in rows:
                per.setdefault(d, {}).setdefault(r["name"], Counter()).update(
                    {k: int(r.get(k, 0)) for k in ("visits", "pages", "not_found", "posts")})
    rows = {d: [{"name": n, **{k: int(c[k]) for k in ("visits", "pages", "not_found", "posts")}}
                for n, c in sorted(names.items(), key=lambda kv: (kv[0] == NONE,
                                                                  -kv[1]["visits"], kv[0]))]
            for d, names in per.items()}
    return {"rows": rows, "tagged": tagged_n, "visits": visits}
