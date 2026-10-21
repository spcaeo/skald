"""Release 2 data files (DATA-CONTRACT.md): requests, alerts, quality,
markers, leads, and later ones (events, conversions). Each module defines
`build(page) -> dict` (the body below the envelope); a page is
data_files.Page."""
from __future__ import annotations

import importlib

FILES = {"requests": "requests_feed", "alerts": "alerts", "quality": "quality",
         "markers": "markers", "leads": "leads", "cube": "cube", "robots": "robots",
         "speed": "pagespeed", "funnels": "funnels",
         "page_index": "lifecycle", "events": "events", "conversions": "conversions_data",
         "llms_txt": "llms_txt", "crawler_cost": "crawler_cost",
         "crawl_health": "crawl_health",
         "realtime": "realtime", "search": "search.data", "retention": "retention_page",
         "ai_answers": "answers.data", "security": "security_page"}


def builders() -> dict:
    out = {}
    for name, module in FILES.items():
        try:
            mod = importlib.import_module(f".{module}", __package__)
        except ModuleNotFoundError as why:
            if why.name != f"{__package__}.{module}":
                raise
            continue
        out[name] = mod.build
    return out
