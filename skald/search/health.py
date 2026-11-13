"""Has a site's search sync stopped? (#40)

A Search Console or Bing sync that worked and then failed try after try used to
say so only on Settings, in small type: one site's sync failed for twelve days
and nobody knew. This module holds the one rule every screen and mail uses.

A sync counts as STOPPED when:
  - it is connected (not connected is never stopped), and
  - it worked at least once before (`last_ok` is set), and
  - every try since its last good sync failed, and either
      STOPPED_TRIES tries in a row failed, or
      the newest failed try ended STOPPED_HOURS (24) or more after the last good sync.

The tries are the sync's own runs (search/sync.py: the scheduler every EVERY_HOURS
hours, a "Sync now", a history backfill). A sync that could not start because another
held the lock is not a try. With the scheduler's 6 hours, STOPPED_TRIES tries are one
day of them; a person pressing "Sync now" can make them come sooner.

The state file (search/state.py) keeps, per engine, `fails` (failed tries in a row,
0 after a good one) and `tries` (the newest KEEP_TRIES tries, oldest first, each
{"at", "ok", "error"}; when the last good try would fall off, it is kept in front).
`status` reads `last_ok`, `last_sync`, `ok` and `fails`; the second count
(audit_search_sync.py) works the same answer out again from `tries` alone.

`status` gives the plain words every screen shows: Overview > Insights' to-do,
Settings > Leads & tools > Search Console & Bing, the Search tab, the MCP's your_tools,
and the one mail when a sync stops and the one when it comes back (sync.py).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

STOPPED_HOURS = 24
STOPPED_TRIES = 4           # one day of the scheduler's tries: 24 h / sync.EVERY_HOURS (6)
KEEP_TRIES = 60             # about 15 days of tries
ENGINE_NAMES = {"google": "Search Console", "bing": "Bing Webmaster Tools"}
OWNER = {"google": "Google", "bing": "Bing"}
WHERE = "Settings › Leads & tools › Search Console & Bing"

# The engine's own words (google.words_for / bing.words_for put them in brackets).
_SAID = re.compile(r"\((Google|Bing) said: (.+)\)\s*$", re.S)


def parse(text) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


def note_try(tries, at: str, ok: bool, error: str | None = None,
             last_ok: str | None = None) -> list[dict]:
    """The tries after one more: the newest KEEP_TRIES, with the newest good try kept in
    front when it would fall off (so "worked before" and since when stay known). A state
    file from before the tries were kept starts with its `last_ok` as a good try."""
    got = [t for t in (tries or []) if isinstance(t, dict)]
    if not got and last_ok:
        got.append({"at": last_ok, "ok": True, "error": None, "seeded": True})
    got.append({"at": at, "ok": bool(ok), "error": None if ok else (error or "")[:300]})
    if len(got) <= KEEP_TRIES:
        return got
    kept = got[-KEEP_TRIES:]
    if not any(t.get("ok") for t in kept):
        good = [t for t in got[:-KEEP_TRIES] if t.get("ok")]
        if good:
            kept = [good[-1]] + got[-(KEEP_TRIES - 1):]
    return kept


def reason(error: str | None, engine: str) -> str:
    """The engine's reason in one line: its own words when it gave them, else ours."""
    text = " ".join(str(error or "").split())
    said = _SAID.search(text)
    if said:
        return f"{said.group(1)} said: {said.group(2).strip()}"[:240].rstrip(". ")
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return (first or f"{OWNER[engine]} gave no reason")[:240].rstrip(". ")


def advice(error: str | None, engine: str) -> str:
    """What to do about it, from the reason."""
    text = str(error or "").lower()
    if engine == "google":
        if "service account's key" in text or "service-account key" in text or "invalid_grant" in text:
            return f"Upload a new service-account key in {WHERE}."
        if re.search(r"deleted|disabled|suspended|has not been used|service_disabled|"
                     r"accessnotconfigured|api .*not .*enabled", text):
            return ("Check the Google Cloud project behind Skald's robot key: restore it if it was "
                    "deleted, and turn the Search Console API back on. Or upload a new key in "
                    f"{WHERE}.")
        if "has no access" in text:
            return ("In Search Console › Settings › Users and permissions, add the robot's email back "
                    f"with Restricted access, or reconnect in {WHERE}.")
    elif "api key" in text:
        return f"Check the Bing API key in {WHERE}."
    if "does not cover" in text:
        return f"Connect a property of this site in {WHERE}."
    if "quota" in text or "could not reach" in text:
        return f"Usually it passes by itself. If not, press Sync now in {WHERE}."
    return f"Open {WHERE}, press Sync now, and reconnect if it still fails."


def status(part: dict | None, source) -> dict:
    """{state, stopped, since, fails, hours, reason, advice, words, pill} for one engine.

    state: off (not connected), waiting (not synced yet), answering, not_answering (never
    worked and failing: the connection itself, no warning), failing (it worked; failing for
    less than the rule) or stopped. `since` is the last good sync; `hours` the hours from it to
    the newest failed try."""
    part = part or {}
    out = {"state": "off", "stopped": False, "since": part.get("last_ok"),
           "fails": int(part.get("fails") or 0), "hours": None, "reason": None,
           "advice": None, "words": "Not connected.", "pill": "off",
           "rule": {"tries": STOPPED_TRIES, "hours": STOPPED_HOURS}}
    if not source:
        return out
    if not part.get("last_sync"):
        return {**out, "state": "waiting", "pill": "info", "words": "Connected, not synced yet."}
    if part.get("ok"):
        return {**out, "state": "answering", "pill": "good", "words": "Syncing."}
    last_ok, last_try = parse(part.get("last_ok")), parse(part.get("last_sync"))
    engine = part.get("engine") or "google"
    out.update(reason=reason(part.get("error"), engine), advice=advice(part.get("error"), engine))
    if last_ok is None:
        return {**out, "state": "not_answering", "pill": "warn",
                "words": "It has never synced: the connection itself fails."}
    hours = (last_try - last_ok).total_seconds() / 3600 if last_try else None
    out["hours"] = round(hours, 1) if hours is not None else None
    stopped = out["fails"] >= STOPPED_TRIES or (hours is not None and hours >= STOPPED_HOURS)
    if not stopped:
        return {**out, "state": "failing", "pill": "warn",
                "words": "The last try failed. Skald tries again; the figures already synced stay."}
    return {**out, "state": "stopped", "stopped": True, "pill": "bad",
            "words": f"Stopped: no good sync since {_when(last_ok)}, "
                     f"{out['fails'] or 'every'} tr{'y' if out['fails'] == 1 else 'ies'} failed."}


def of(state: dict, engine: str, source) -> dict:
    """status() of one engine's part of a site's state file."""
    return status({**((state or {}).get(engine) or {}), "engine": engine}, source)


def _when(at: datetime) -> str:
    at = at.astimezone(timezone.utc)
    return f"{at.day} {at:%b %Y %H:%M} UTC"


# ------------------------------------------------------------ the to-do

def todo(engine: str, st: dict) -> dict:
    """Overview > Insights' to-do for a stopped sync (todos.py adds it)."""
    name = ENGINE_NAMES[engine]
    since = parse(st.get("since"))
    when = _when(since) if since else "its last good sync"
    return {"id": f"search-sync-{engine}", "kind": "search", "subject": engine, "tag": "Search",
            "tone": "bad",
            "title": f"{name} stopped syncing",
            "proof": f"No good {name} sync since {when}: {st['fails'] or 'every'} "
                     f"tr{'y' if st['fails'] == 1 else 'ies'} in a row failed. {st['reason']}.",
            "todo": st["advice"],
            "check": "the next sync: this goes away by itself after a good one",
            "figures": {"engine": engine, "since": st.get("since"), "fails": st["fails"],
                        "hours": st["hours"], "reason": st["reason"]},
            "qualifies": True, "columns": [], "rows": [], "file": None,
            "open": {"tab": "settings/site/leads", "tool": "search"}}


def todos(config: dict, folder, site: str) -> list[dict]:
    """The to-dos of every connected engine whose sync stopped."""
    from . import state
    from .sync import connected
    if folder is None:
        return []
    got = state.load(folder, site)
    out = []
    for engine, source in connected(config or {}).items():
        st = of(got, engine, source)
        if st["stopped"]:
            out.append(todo(engine, st))
    return out


# ------------------------------------------------------------ the mails

def subject(engine: str, site: str, back: bool) -> str:
    name = ENGINE_NAMES[engine]
    return f"{name} sync back for {site}" if back else f"{name} sync stopped for {site}"


def mail_text(engine: str, site: str, st: dict, back: bool, now: datetime) -> str:
    """The one mail when a sync stops (back False) or comes back (back True). `st` is
    status() as the sync stood when it stopped."""
    name = ENGINE_NAMES[engine]
    since = parse(st.get("since"))
    if back:
        gap = f"no good sync from {_when(since)} until now" if since else "it had stopped"
        return "\n".join([
            f"{name} syncs again for {site} ({now:%Y-%m-%d %H:%M} UTC).", "",
            f"It had stopped: {gap}. This and the next syncs fetch the days it missed.", "",
            "Nothing to do. This is the one mail about it coming back."]) + "\n"
    return "\n".join([
        f"{name} stopped syncing for {site}.", "",
        f"No good sync since {_when(since) if since else 'it last worked'}; "
        f"{st['fails'] or 'every'} tr{'y' if st['fails'] == 1 else 'ies'} in a row failed.",
        f"Why: {st['reason']}", "",
        f"What to do: {st['advice']}", "",
        "Search figures already synced stay on the Search tab. Skald keeps trying every few "
        "hours; Overview › Insights and Settings show it until a sync works.",
        "One mail when it stops and one when it comes back: no mail on every try."]) + "\n"
