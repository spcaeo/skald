"""Search Console connects by itself (2.44).

The owner (2026-10-27): he gave the agent line for Search Console to Claude
Code. The agent reported `sc-domain:example.com`, told him to add Skald's robot address, then
sent him to Settings to press Connect; at the foot of a long watch he pressed Apply, and Google
refused: the robot was on the address property `https://example.com/`, not the domain one.
The connection failed and the open page did not say so.

Now Skald asks Google which properties its robot can see (google.Client.sites, the same
listing as integrations/search/properties) and connects the one that covers the site's hosts
(props.matching: a domain property first):

  - the one reported (or pressed) when Google shows it; else another that covers the site,
    said in one line ("Your agent named sc-domain:example.com, but Skald's robot is on
    https://example.com/: Skald uses that one.");
  - none yet: "Waiting for Google: Skald's robot address is not on a example.com property
    yet." The want is kept (the search state's `auto` part) and Skald looks again by itself,
    at most once a minute, from the live run (setup_live.run), from every page that shows it
    (connect_check "search", sites/arrived) and on Check now, for KEEP_DAYS; once it appears,
    Skald connects it and starts the 16-month history. Whoever ran the line already said yes.

Who wants it: the agent's report (kit/agent.py: a line with the search job whose report names
`search.google_property`; the report's answer then carries these words, so the agent tells the
person what Skald sees), Check now on the watch and on Traffic › Search, and the Connect of
Search Console & Bing (search/api.py connect). Nothing here counts a figure.

`auto` (in <history folder>/search/<site>.json): {property (the one wanted), by, since,
last_try, state: waiting | connected | gave_up | no_key | failed, words, note, source,
connected_at}.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import http, props, state, sync

KEEP_DAYS = 7               # how long Skald keeps looking for a property it was asked for
EVERY_S = 60                # at most one look at Google a minute per site (unless pressed)
MONTHS = 16                 # the history a connect starts with
SETTING = "search.google_property"
ROOT = Path(__file__).resolve().parents[2]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def spawn(config_path, folder, site: str, args: list[str]) -> bool:
    """`skald --site SITE <args>` in the background (search/api.py spawn's twin, for callers
    without a helper request). Replaced in tests. False when it cannot start."""
    if config_path is None:
        return False
    log = state.folder(folder) / f"{site}.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as out:
            subprocess.Popen([sys.executable, str(ROOT / "bin/skald"), "--config", str(config_path),
                              "--site", site, *args], cwd=str(ROOT), stdin=subprocess.DEVNULL,
                             stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    except OSError:
        return False
    return True


def _site_config(config, config_path, site: str) -> dict:
    from ..conversions import hooks
    return hooks.site_configs(config or {}, config_path).get(site) or config or {}


def hosts_of(config, config_path, folder, db, site: str) -> list[str]:
    from .. import settings_store
    got = settings_store.explain(_site_config(config, config_path, site), site, db)
    return [str(h) for h in ((got.get("sites.hosts") or {}).get("value") or [])]


def connected(config, config_path, db, site: str) -> str | None:
    from .. import settings_store
    got = settings_store.explain(_site_config(config, config_path, site), site, db)
    return (got.get(SETTING) or {}).get("value")


def _job(config, config_path, folder, site: str) -> sync.Job:
    from .. import settings_store
    conf = settings_store.apply(_site_config(config, config_path, site), site, folder)
    db_path = Path(((config or {}).get("_resolved") or {}).get("history_db")
                   or Path(folder) / "history.sqlite")
    return sync.Job(conf, site, Path(folder), db_path, _now(), out=lambda *a: None,
                    err=lambda *a: None)


def look(job: sync.Job, hosts, wanted: str | None) -> dict:
    """Ask Google which properties the robot sees: {state: found | waiting | no_key | failed,
    source, note, words, tech}."""
    site = job.site
    try:
        client = sync.google_client(job)
    except http.Failed as why:
        return {"state": "no_key", "words": "Skald has no Google robot key yet: whoever runs "
                "Skald uploads one in Settings › Leads & tools › Search Console & Bing.",
                "tech": str(why)}
    try:
        found = client.sites()
    except http.Failed as why:
        return {"state": "failed", "words": "Skald could not ask Google just now. It tries "
                "again by itself in a minute.", "tech": str(why)}
    fit = [str(p["siteUrl"]) for p in props.matching(found, hosts)]
    if not fit:
        return {"state": "waiting", "tech": f"The robot sees {len(found)} properties, none for "
                f"{', '.join(hosts) or site}.",
                "words": f"Waiting for Google: Skald's robot address is not on a {site} property "
                         "yet. Google can take a few minutes."}
    source = wanted if wanted in fit else fit[0]
    note = (f"Your agent named {wanted}, but Skald's robot is on {source}: Skald uses that one."
            if wanted and wanted != source else None)
    return {"state": "found", "source": source, "note": note}


def connect(db, folder, config_path, site: str, source: str, actor, months: int = MONTHS,
            start=None) -> bool:
    """Save the property and start its history, as search/api.py connect does."""
    from .. import settings_store
    settings_store.put(db, f"site:{site}", SETTING, source, actor)
    state.update(folder, site, "google", source=source, error=None, error_since=None,
                 error_mailed=None, connected_at=state.now_text(),
                 backfill={"state": "queued", "months": months, "done": 0, "of": None})
    args = ["search-console", "sync", "--backfill-months", str(months)]
    return (start or spawn)(config_path, folder, site, args) if start is not False else False


def want(folder, site: str, prop: str | None, by: str) -> dict:
    """Keep looking for `prop` (or any property that covers the site) until it appears."""
    return state.update(folder, site, "auto", property=prop or None, by=str(by), since=state.now_text(),
                        last_try=None, state="waiting", words=None, note=None, source=None,
                        connected_at=None)


def run(config, config_path, folder, db, site: str, force: bool = False, start=None,
        job=None) -> dict | None:
    """One look for a wanted property; connects it once Google shows it. The `auto` part
    after the look, or None when nothing is wanted. Never raises."""
    part = state.load(folder, site).get("auto")
    if not isinstance(part, dict) or part.get("state") in (None, "connected", "gave_up"):
        return part if isinstance(part, dict) else None
    now = _now()
    have = connected(config, config_path, db, site)
    if have:
        return state.update(folder, site, "auto", state="connected", source=have,
                            words="Connected. Skald is getting Google's history.",
                            connected_at=part.get("connected_at") or state.now_text(now))
    since = _parse(part.get("since"))
    if since and now - since > timedelta(days=KEEP_DAYS):
        return state.update(folder, site, "auto", state="gave_up", words=(
            f"Skald looked for {KEEP_DAYS} days and Google never showed its robot on a {site} "
            "property. Connect it in Settings › Leads & tools › Search Console & Bing."))
    last = _parse(part.get("last_try"))
    if not force and last and (now - last).total_seconds() < EVERY_S:
        return part
    try:
        got = look(job or _job(config, config_path, folder, site),
                   hosts_of(config, config_path, folder, db, site), part.get("property"))
    except Exception as why:              # noqa: BLE001 - a look never breaks its caller
        got = {"state": "failed", "words": "Skald could not ask Google just now.",
               "tech": f"{type(why).__name__}: {why}"}
    if got["state"] != "found":
        return state.update(folder, site, "auto", last_try=state.now_text(now), state=got["state"],
                            words=got["words"], tech=got.get("tech"))
    started = connect(db, folder, config_path, site, got["source"], part.get("by") or "ai-agent",
                      start=start)
    words = "Connected. Skald is getting Google's history: the last 16 months."
    if not started:
        words = "Connected. Google's history starts with the next sync."
    return state.update(folder, site, "auto", last_try=state.now_text(now), state="connected",
                        source=got["source"], note=got.get("note"), words=words, tech=None,
                        connected_at=state.now_text(now))


def tick(config, config_path, folder, db, site: str) -> str | None:
    """The live run's step: one look while a property is wanted. Plain words when it changed."""
    before = (state.load(folder, site).get("auto") or {}).get("state")
    if before not in ("waiting", "failed", "no_key"):
        return None
    got = run(config, config_path, folder, db, site) or {}
    return f"search console: {got.get('state')}" if got.get("state") != before else None
