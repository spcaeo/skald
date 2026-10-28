"""How each road into Skald is doing, in plain words: for `skald doctor`
(doctor.py) and Settings > Leads & tools (integrations_api.py), one reading.

    hook_states(...)   each tool's incoming hook: needs a secret, never
                       received, ready (a test passed), or last received N ago;
                       with what to do when something is wrong
    duplicates(...)    external refs that arrived from two tools: each tool
                       keeps its own row, so the same lead counts twice
    helper(...)        is the beacon helper (the hook receiver, and the
                       script tag's server) answering on its port?
    unplaced(...)      the `lead` and `json` hooks' last PLACE_LOOK real
                       leads, when every one was kept without a country
                       (hook_states' "unplaced"; the doctor and the set-up
                       checklist say it, with the fix)

Reads only. No figure here is a count shown as a result: the states are
facts about the delivery log, the secrets and the helper.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from datetime import datetime, timezone

from . import TOOLS, geo, secrets_store, store

TOOL_NAMES = {"lead": "Your site's server (lead)", "json": "Zapier, Make, n8n (json)",
              "calendly": "Calendly", "calcom": "Cal.com", "stripe": "Stripe",
              "typeform": "Typeform", "hubspot": "HubSpot"}
TESTS = ("test", "test_failed")
REFUSED = {"bad_signature": "the signature did not match",
           "bad_body": "the body could not be read",
           "too_large": "the body was over 64 KiB",
           "no_length": "it had no length",
           "rate_limited": "too many at once",
           "error": "Skald could not keep it"}
HELPER_URL = "http://127.0.0.1:8766"
NOT_HOOKS = ("beacon",)          # the script tag's rows: its refs are made by Skald


def ago(then, now: datetime | None = None) -> str:
    """"5 min ago", "3 h ago", "2 days ago" for an ISO time; "" when unknown."""
    try:
        at = datetime.fromisoformat(str(then).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    seconds = max(0, int(((now or datetime.now(timezone.utc)) - at).total_seconds()))
    if seconds < 90:
        return "just now"
    if seconds < 5400:
        return f"{round(seconds / 60)} min ago"
    if seconds < 48 * 3600:
        return f"{round(seconds / 3600)} h ago"
    return f"{round(seconds / 86400)} days ago"


def _fix_for(outcome: str, tool: str, site: str, cmd: str, detail: str | None) -> str:
    name = TOOL_NAMES.get(tool, tool)
    if outcome == "bad_signature":
        return (f"The secret {name} signs with is not the one Skald has. Give {name} the "
                f"secret again (Settings > Leads & tools, or `{cmd} hooks secret {site} {tool}`)"
                + (", or paste the signing secret it shows" if tool != "lead" else "") + ".")
    if outcome == "bad_body":
        return (f"Skald could not read what {name} sent" + (f": {detail}" if detail else "")
                + ". docs/INTEGRATIONS.md lists the fields.")
    if outcome == "error":
        return "Skald could not write it (disk or database). Check the disk and the helper's log."
    if outcome == "rate_limited":
        return "More than hooks.per_minute arrived at once; raise it if this is normal traffic."
    return "See the delivery log on Settings > Leads & tools."


PLACE_LOOK = 3                   # the last leads read for "unplaced"
PLACE_TOOLS = ("lead", "json")   # the hooks that can send the visitor's address (ip)


def unplaced(db, site: str, tool: str, site_config: dict | None = None) -> dict | None:
    """{"leads", "no_vid", "says", "fix"} when each of the tool's last
    PLACE_LOOK real leads (by when Skald got them; test rows apart) was kept
    without a country, else None. A state read from at most PLACE_LOOK
    stored rows, not a figure: "leads" is how many were read. Leads already
    kept stay as they are: no country is guessed after the fact."""
    if db is None or tool not in PLACE_TOOLS:
        return None
    got = db.execute("SELECT external_ref, MAX(received_at) AS got, MAX(country IS NOT NULL), "
                     "MAX(vid IS NOT NULL) FROM conversions WHERE site = ? AND tool = ? AND "
                     "test = 0 GROUP BY external_ref ORDER BY got DESC, external_ref LIMIT ?",
                     (site, tool, PLACE_LOOK)).fetchall()
    if not got or any(r[2] for r in got):
        return None
    n, no_vid = len(got), all(not r[3] for r in got)
    last = "Your last lead" if n == 1 else f"Your last {n} leads"
    if not geo.database(site_config or {}):
        return {"leads": n, "no_vid": no_vid,
                "says": f"{last} came without a country: Skald's server has no country file to "
                        "look the visitor's address up in",
                "fix": "Set the country file on Skald's server (logs.country_db, or "
                       "SKALD_COUNTRY_DB in Docker), then have the lead call pass the "
                       "visitor's address as `ip`. Leads already kept stay without a country."}
    what = "a visitor ID or the visitor's address" if no_vid else "the visitor's address"
    lost = "their country and the pages they read are" if no_vid else "their country is"
    return {"leads": n, "no_vid": no_vid,
            "says": f"{last} came without {what}, so {lost} not recorded",
            "fix": "Pass the visitor's address as `ip` in the lead call, from the header your "
                   "host sets (the lead files' README, \"The visitor's address\"), or run the "
                   "AI agent's lead job again. Leads already kept stay without a country."}


def hook_states(site_config: dict, folder, site: str, db, now: datetime | None = None,
                cmd: str = "skald", base: str = "") -> list[dict]:
    """One entry per tool: {tool, name, url, set, where, state, words,
    attention, fix, last_at, test_at, unplaced}. state: needs_secret, missing (an
    environment variable named but empty), never, ready (only tests so far),
    received. `db` is conversions.sqlite opened, or None when there is none."""
    out = []
    for tool in TOOLS:
        name = TOOL_NAMES.get(tool, tool)
        url = f"{base}/traffic-hooks/{site}/{tool}"
        try:
            value, where = secrets_store.find(site_config, folder, site, tool)
        except secrets_store.Exposed as why:
            out.append({"tool": tool, "name": name, "url": url, "set": False, "where": "file",
                        "state": "exposed", "words": f"cannot be used: {why}",
                        "attention": True, "fix": "chmod 600 the secrets file on the server.",
                        "last_at": None, "test_at": None, "unplaced": None})
            continue
        entry = {"tool": tool, "name": name, "url": url, "set": bool(value),
                 "where": where, "last_at": None, "test_at": None, "fix": None,
                 "attention": False, "unplaced": None}
        if not value:
            if where.startswith("env "):
                entry.update(state="missing", attention=True,
                             words=f"its secret comes from {where[4:]}, which is empty",
                             fix=f"Set the environment variable {where[4:]} on the server.")
            else:
                entry.update(state="needs_secret", words="needs a secret")
            out.append(entry)
            continue
        rows = store.deliveries(db, site, tool, 50) if db is not None else []
        real = [r for r in rows if r["outcome"] not in TESTS]
        tests = [r for r in rows if r["outcome"] in TESTS]
        if tests:
            entry["test_at"] = tests[0]["received_at"]
        if not real:
            if tests and tests[0]["outcome"] == "test":
                entry.update(state="ready", words=f"ready: a test passed "
                             f"{ago(tests[0]['received_at'], now)}; nothing real yet")
            else:
                entry.update(state="never", attention=True,
                             words="secret set, but nothing has arrived, not even a test",
                             fix=f"Send a test (`{cmd} hooks test {site} {tool}`, or Send a "
                                 f"test on Settings > Leads & tools). Then check that {name} "
                                 f"posts to {url}.")
            out.append(entry)
            continue
        last = real[0]
        entry["last_at"] = last["received_at"]
        when = ago(last["received_at"], now)
        if last["outcome"] in REFUSED:
            entry.update(state="received", attention=True,
                         words=f"last delivery {when} was refused: {REFUSED[last['outcome']]}",
                         fix=_fix_for(last["outcome"], tool, site, cmd, last.get("error")))
        else:
            what = {"recorded": "kept", "duplicate": "a repeat",
                    "ignored": "not counted", "replay": "a repeat",
                    "marked_test": "leads marked test",
                    "unmarked_test": "test marks taken off"}.get(last["outcome"],
                                                                  last["outcome"])
            detail = f", {last['error']}" if last.get("error") else ""
            entry.update(state="received", words=f"last received {when} ({what}{detail})",
                         unplaced=unplaced(db, site, tool, site_config))
        out.append(entry)
    return out


def duplicates(db, site: str, limit: int = 20) -> list[dict]:
    """[{ref, tools}] for each external ref that came from more than one tool
    (the script tag's own rows apart), newest first. Each tool keeps its own
    row, so such a lead counts once per tool."""
    if db is None:
        return []
    marks = ",".join("?" * len(NOT_HOOKS))
    rows = db.execute(
        "SELECT external_ref, GROUP_CONCAT(DISTINCT tool), MAX(at) FROM conversions "
        f"WHERE site = ? AND tool NOT IN ({marks}) GROUP BY external_ref "
        "HAVING COUNT(DISTINCT tool) > 1 ORDER BY MAX(at) DESC LIMIT ?",
        (site, *NOT_HOOKS, int(limit))).fetchall()
    return [{"ref": r[0], "tools": sorted(str(r[1]).split(",")), "last_at": r[2]}
            for r in rows]


def helper(url: str = HELPER_URL, timeout: float = 2.0) -> dict:
    """{"up": bool, "script": bool | None, "error": str | None}: the beacon
    helper answers (any HTTP answer is up), and whether it serves the script
    tag's file (it does only with beacon.origins)."""
    base = url.rstrip("/")
    try:
        with urllib.request.urlopen(urllib.request.Request(
                base + "/traffic-js/skald.js", method="HEAD"), timeout=timeout) as got:
            return {"up": True, "script": got.status == 200, "error": None}
    except urllib.error.HTTPError as why:
        return {"up": True, "script": False if why.code == 404 else None, "error": None}
    except (urllib.error.URLError, OSError, ValueError) as why:
        reason = getattr(why, "reason", why)
        return {"up": False, "script": None, "error": f"{type(reason).__name__}: {reason}"[:200]}
