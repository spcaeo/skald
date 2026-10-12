"""MCP resources and prompts.

Resources (read-only text):
  skald://docs/api                 docs/API.md: the read-only API and its files
  skald://docs/counting            CLASSIFICATION.md: the five groups and what
                                   the figures cannot know
  skald://sites/<site>/overview    the site's latest overview.json
  skald://sites/<site>/llms.txt    a suggested /llms.txt (llms_txt.py), from
                                   the latest llms_txt.json

Prompt: weekly_report(site) - asks the model for a short weekly report
written with the tools, under Skald's honesty rules.
"""
from __future__ import annotations

import json
from pathlib import Path

from .data import SITE, Refused

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS = {"skald://docs/api": ("docs/API.md", "Skald read-only API",
                             "The data files and how the read-only API serves them."),
        "skald://docs/counting": ("CLASSIFICATION.md", "How Skald counts",
                                  "The five groups every request falls in, and what the "
                                  "figures cannot know.")}
SITE_URI = "skald://sites/{site}/overview"
LLMS_URI = "skald://sites/{site}/llms.txt"


class Missing(Exception):
    """resources/read of a resource that does not exist (or is not yours)."""


def listing(ctx) -> list[dict]:
    out = [{"uri": uri, "name": Path(path).name, "title": title, "description": about,
            "mimeType": "text/markdown"} for uri, (path, title, about) in DOCS.items()
           if (ROOT / path).is_file()]
    for site in ctx.sites():
        out.append({"uri": SITE_URI.format(site=site), "name": f"{site} overview",
                    "title": f"{site}: overview data file",
                    "description": "The latest overview.json: headline figures per day, "
                                   "with each day's state (ok, partial, withheld, missing).",
                    "mimeType": "application/json"})
        out.append({"uri": LLMS_URI.format(site=site), "name": f"{site} llms.txt",
                    "title": f"{site}: suggested llms.txt",
                    "description": "A suggested /llms.txt: the pages people and AI assistants "
                                   "read most over the last 90 recorded days. Skald never "
                                   "publishes it.",
                    "mimeType": "text/markdown"})
    return out


def templates() -> list[dict]:
    return [{"uriTemplate": SITE_URI, "name": "site overview",
             "title": "A site's overview data file",
             "description": "overview.json of a site you may read.",
             "mimeType": "application/json"},
            {"uriTemplate": LLMS_URI, "name": "site llms.txt",
             "title": "A site's suggested llms.txt",
             "description": "A suggested /llms.txt for a site you may read.",
             "mimeType": "text/markdown"}]


def read(ctx, uri: str) -> list[dict]:
    if uri in DOCS:
        path = ROOT / DOCS[uri][0]
        if not path.is_file():
            raise Missing(uri)
        return [{"uri": uri, "mimeType": "text/markdown", "text": path.read_text()}]
    prefix, suffix = "skald://sites/", "/overview"
    if uri.startswith(prefix) and uri.endswith("/llms.txt"):
        doc = _site_doc(ctx, uri, uri[len(prefix):-len("/llms.txt")], "llms_txt")
        if not doc.get("ok") or not isinstance(doc.get("text"), str):
            raise Missing(uri)
        return [{"uri": uri, "mimeType": "text/markdown", "text": doc["text"]}]
    if uri.startswith(prefix) and uri.endswith(suffix):
        site = uri[len(prefix):-len(suffix)]
        if not SITE.match(site):
            raise Missing(uri)
        try:
            site = ctx.site(site)
            doc = ctx.load(site, None, "overview")
        except Refused:
            raise Missing(uri)          # the same answer whether it exists or is not yours
        return [{"uri": uri, "mimeType": "application/json",
                 "text": json.dumps(doc, separators=(",", ":"))}]
    raise Missing(uri)


def _site_doc(ctx, uri: str, site: str, name: str) -> dict:
    if not SITE.match(site):
        raise Missing(uri)
    try:
        doc = ctx.load(ctx.site(site), None, name)
    except Refused:
        raise Missing(uri)              # the same answer whether it exists or is not yours
    if not isinstance(doc, dict):
        raise Missing(uri)
    return doc


# ---------------------------------------------------------------- prompts

RULES = (
    "Skald's rules, which the report must keep:\n"
    "- Call visits \"visits (an upper bound on people)\". Never call them users, and never "
    "present requests as people.\n"
    "- Use only figures the tools return. Never estimate, fill in, or turn a missing or "
    "null figure into zero.\n"
    "- Name every withheld, partial or missing day by date and say its figures are left "
    "out.\n"
    "- State a change only when a tool gives one (both periods complete).\n"
    "- Visits that followed a link from an AI assistant are a floor (referrers are often "
    "stripped). Clicks from Google's AI Overviews are not measurable.\n"
    "- Plain English, short sentences, under 250 words.")

PROMPTS = {"weekly_report": {
    "name": "weekly_report", "title": "Weekly report",
    "description": "A short weekly traffic report for one site, written with Skald's tools "
                   "and its honesty rules.",
    "arguments": [{"name": "site", "description": "The site's name, as list_sites gives it.",
                   "required": False}]}}


def prompt(ctx, name: str, args: dict) -> dict:
    site = str((args or {}).get("site") or "").strip()
    target = site or "the site (call list_sites first if there is more than one)"
    text = (f"Write a short weekly traffic report for {target}, using Skald's tools.\n"
            "1. overview with no dates: the last 7 whole days.\n"
            "2. compare with no dates: those 7 days against the 7 before; use only the "
            "changes it gives.\n"
            "3. breakdown by source, and by country.\n"
            "4. top_pages, ai_activity and leads for the same days.\n"
            "5. data_quality and site_health: say plainly if anything is withheld, late or "
            "broken.\n"
            "Open with the 3 things that matter most, then the figures, then what was left "
            "out.\n\n" + RULES)
    return {"description": PROMPTS[name]["description"],
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
