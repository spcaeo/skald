"""The helper's Real time route (refresh_server.py dispatches it here).

    GET <page>/api/realtime     what Overview > Real time polls every 15 seconds

The answer has the two roads side by side, each with its own time:

  people     the live snapshot's `realtime` part (realtime.py): readers'
             visits, counted by the day's tally with the people rule, as of
             its `until` (the live run, every 2 minutes); null when today's
             snapshot is missing, withheld or has no such part
  requests   every request of the site's hosts per minute, from the newest
             log lines, as of the second it was read (realtime_tail.py)

Read-only; no address and no user agent in either. The whole site's figures,
also on a view's page (the page says so). An unknown site is 404.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

PAGE = r"^/traffic/(?P<site>[a-z0-9.-]+)/(?:(?P<view>[a-z0-9-]+)/)?"
REALTIME_PATH = re.compile(PAGE + r"api/realtime$")


def is_realtime(path: str) -> bool:
    return REALTIME_PATH.match(path.split("?", 1)[0]) is not None


def site_dir(config: dict, live_dir, site: str) -> Path | None:
    """Where a site's live snapshot is: the first site's beside the history,
    another's in sites/<slug> (multisite.state_dir), not created here."""
    from .config import site_name
    from .files import slug
    if live_dir is None:
        return None
    if site == site_name(config or {}):
        return Path(live_dir)
    return Path(live_dir) / "sites" / slug(site)


def answer(config: dict, live_dir, site: str, config_path=None, now=None) -> tuple[int, dict]:
    from . import live, realtime_tail
    from .config import site_name
    from .people.api import _site_config
    from .window import zone
    cfg = _site_config(config or {}, site, config_path)
    if site_name(cfg) != site:
        return 404, {"ok": False, "error": "no such site"}
    tz = zone(cfg)
    folder = site_dir(config, live_dir, site)
    now = now or datetime.now(timezone.utc)
    snap = live.load(live.path_for(folder, site)) if folder is not None else None
    today = now.astimezone(tz).date().isoformat()
    people, state = None, "empty"
    if snap and snap.get("day") == today:
        state = snap.get("state") or "empty"
        if state == "ok":
            people = snap.get("realtime")
            if people is None:
                state = "empty"
    got = realtime_tail.cached(site, cfg, folder, now=now)
    return 200, {"ok": True, "site": site, "now": now.astimezone(tz).isoformat(timespec="seconds"),
                 "people_state": state, "people": people,
                 "people_counted": snap.get("generated_at") if snap else None,
                 "requests": realtime_tail.as_page(got, tz)}


def handle(h, config, live_dir, config_path=None) -> None:
    m = REALTIME_PATH.match(h.path.split("?", 1)[0])
    if m is None or ".." in h.path:
        return h._json(404, {"ok": False, "error": "not found"})
    code, body = answer(config, live_dir, m.group("site"), config_path)
    return h._json(code, body)
