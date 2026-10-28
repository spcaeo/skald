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
    last_real(...)     2.45: a hook's newest real (not test) delivery, in words
    since_saved(...)   2.45: its real deliveries since its key was saved:
                       accepted, refused (a signature that did not match),
                       unsigned (no signature at all)

2.45: a refusal says which: `unsigned` (the tool sent no signature: its
webhook was made without a key, so no key pasted into Skald can match it;
the fix is to make the webhook again with Skald's) or `bad_signature` (it
signed with another key), each in the tool's own word for its key (KEY_WORD).

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
# What each tool calls the key it signs with (its own screens' word).
KEY_WORD = {"calendly": "signing key", "calcom": "secret", "typeform": "secret",
            "stripe": "signing secret", "hubspot": "client secret", "lead": "secret",
            "json": "secret"}
KEY_REFUSALS = ("unsigned", "bad_signature")
# A real delivery whose signature held: it proves the saved key (accepted_held: taken
# in from the hold once a saved key matched it, held.py; counted like the others).
ACCEPTED = ("recorded", "duplicate", "accepted_held", "ignored", "replay", "marked_test",
            "unmarked_test")
REFUSED = {"bad_signature": "the signature did not match",
           "unsigned": "it came with no signature",
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


def key_word(tool: str) -> str:
    return KEY_WORD.get(tool, "secret")


def refused_words(outcome: str, tool: str) -> str:
    """Why a delivery was refused, in plain words, with the tool's key word."""
    name, kw = TOOL_NAMES.get(tool, tool), key_word(tool)
    if outcome == "unsigned":
        if tool in ("lead", "json"):
            return f"it came with no signature and no key: the sender was set up without the {kw}"
        return f"{name} sent no signature: the webhook was made without a {kw}"
    if outcome == "bad_signature":
        return (f"the signature did not match: the {kw} {name} signs with is not the one "
                "saved in Skald")
    return REFUSED.get(outcome, outcome)


def _fix_for(outcome: str, tool: str, site: str, cmd: str, detail: str | None) -> str:
    name, kw = TOOL_NAMES.get(tool, tool), key_word(tool)
    again = f"Settings > Leads & tools, or `{cmd} hooks secret {site} {tool}`"
    if outcome == "unsigned":
        if tool in ("stripe", "hubspot"):
            return (f"{name} always signs, so this did not come from {name}'s own webhook. "
                    f"Check that the address is saved in {name} only.")
        if tool in ("lead", "json"):
            return (f"Sign each call with X-Skald-Signature, or send Authorization: Bearer "
                    f"<the {kw}> ({again}). The lead files do it for you.")
        return (f"Make the {name} webhook again with the {kw} Skald gives ({again}): a "
                f"webhook made without a {kw} can never be checked.")
    if outcome == "bad_signature":
        if tool in ("lead", "json"):
            return (f"The {kw} the sender signs with is not the one saved in Skald. Give it "
                    f"the {kw} again ({again}).")
        if tool in ("stripe", "hubspot"):
            return (f"The {kw} {name} signs with is not the one saved in Skald: paste the "
                    f"right one from {name}.")
        return (f"The {kw} {name} signs with is not the one saved in Skald: paste the right "
                f"one, or make the webhook again with Skald's ({again}).")
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
    attention, fix, last_at, test_at, unplaced, held}. state: needs_secret, missing
    (an environment variable named but empty), never, ready (only tests so far),
    received. `db` is conversions.sqlite opened, or None when there is none.
    `held`: how many refused deliveries wait in the hold (held.py)."""
    from . import held as held_mod
    stamp = (now or datetime.now(timezone.utc)).timestamp()
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
                        "last_at": None, "test_at": None, "unplaced": None, "held": 0})
            continue
        waiting = held_mod.count(folder, site, tool, stamp) if folder is not None else 0
        entry = {"tool": tool, "name": name, "url": url, "set": bool(value),
                 "where": where, "last_at": None, "test_at": None, "fix": None,
                 "attention": False, "unplaced": None, "held": waiting}
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
            words = f"last delivery {when} was refused: {refused_words(last['outcome'], tool)}"
            if waiting and last["outcome"] in KEY_REFUSALS:
                words += (f"; {waiting} refused deliver{'y is' if waiting == 1 else 'ies are'} "
                          f"held for 24 h: save the right {key_word(tool)} and Skald takes "
                          f"{'it' if waiting == 1 else 'them'} in")
            entry.update(state="received", attention=True, words=words,
                         fix=_fix_for(last["outcome"], tool, site, cmd, last.get("error")))
        else:
            detail = f", {last['error']}" if last.get("error") else ""
            entry.update(state="received",
                         words=f"last received {when} ({KEPT_WORDS.get(last['outcome'], last['outcome'])}{detail})",
                         unplaced=unplaced(db, site, tool, site_config))
        out.append(entry)
    return out


KEPT_WORDS = {"recorded": "kept", "duplicate": "a repeat", "ignored": "not counted",
              "replay": "a repeat", "marked_test": "leads marked test",
              "unmarked_test": "test marks taken off",
              "accepted_held": "kept, taken in from the hold once the key matched"}


def _count(row) -> int:
    """How many deliveries one row stands for: a refusal row says "<n> refused"
    (hooks._refused writes at most one a minute); every other row is one."""
    if row["outcome"] not in ("unsigned", "bad_signature", "rate_limited"):
        return 1
    head, _, rest = str(row.get("error") or "").partition(" ")
    return int(head) if head.isdigit() and rest.startswith("refused") else 1


def delivery_words(row: dict) -> str:
    """One delivery row in plain words: kept, a repeat, or why it was refused."""
    outcome = row["outcome"]
    if outcome in REFUSED:
        return "refused: " + refused_words(outcome, row.get("tool") or "")
    return KEPT_WORDS.get(outcome, outcome)


def last_real(db, site: str, tool: str) -> dict | None:
    """{at, outcome, words} of the hook's newest real (not test) delivery row,
    by the order written; None when there is none."""
    if db is None:
        return None
    marks = ",".join("?" * len(TESTS))
    got = db.execute(f"SELECT received_at, outcome, error FROM deliveries WHERE site = ? AND "
                     f"tool = ? AND outcome NOT IN ({marks}) ORDER BY id DESC LIMIT 1",
                     (site, tool, *TESTS)).fetchone()
    if got is None:
        return None
    return {"at": got[0], "outcome": got[1],
            "words": delivery_words({"outcome": got[1], "error": got[2], "tool": tool})}


def since_saved(db, site: str, tool: str, saved_at: str | None) -> dict | None:
    """{accepted, refused, unsigned}: the hook's real deliveries written after its key
    was saved at `saved_at` (None: not known, so None). "After" is by the order rows
    were written: every row past the last one received before the save, leaving out
    the rows a taken-in held delivery wrote (accepted_held, or one starting with
    held.NOTE: they carry the time it first came), so the ones that save took in
    count. A refusal row stands for its count ("<n> refused")."""
    from .held import NOTE
    if not saved_at:
        return None
    out = {"accepted": 0, "refused": 0, "unsigned": 0}
    if db is None:
        return out
    edge = db.execute("SELECT COALESCE(MAX(id), 0) FROM deliveries WHERE site = ? AND tool = ? "
                      "AND received_at < ? AND outcome <> 'accepted_held' AND "
                      "substr(COALESCE(error, ''), 1, ?) <> ?",
                      (site, tool, saved_at, len(NOTE), NOTE)).fetchone()[0]
    for row in db.execute("SELECT outcome, error FROM deliveries WHERE site = ? AND tool = ? "
                          "AND id > ?", (site, tool, edge)):
        row = {"outcome": row[0], "error": row[1]}
        if row["outcome"] in ACCEPTED:
            out["accepted"] += 1
        elif row["outcome"] == "bad_signature":
            out["refused"] += _count(row)
        elif row["outcome"] == "unsigned":
            out["unsigned"] += _count(row)
    return out


def last_test(db, site: str, tool: str) -> dict | None:
    """{received_at, outcome} of the hook's newest test of Skald's own, or None."""
    if db is None:
        return None
    got = db.execute("SELECT received_at, outcome FROM deliveries WHERE site = ? AND tool = ? "
                     "AND outcome IN ('test', 'test_failed') ORDER BY id DESC LIMIT 1",
                     (site, tool)).fetchone()
    return {"received_at": got[0], "outcome": got[1]} if got else None


def refused_last_at(db, site: str, tool: str) -> str | None:
    """When the hook last refused a delivery for its key (unsigned or bad_signature)."""
    if db is None:
        return None
    got = db.execute("SELECT received_at FROM deliveries WHERE site = ? AND tool = ? AND "
                     "outcome IN ('unsigned', 'bad_signature') ORDER BY id DESC LIMIT 1",
                     (site, tool)).fetchone()
    return got[0] if got else None


def last_refusal(db, site: str, tool: str) -> str | None:
    """The outcome of the hook's newest key refusal, or None."""
    if db is None:
        return None
    got = db.execute("SELECT outcome FROM deliveries WHERE site = ? AND tool = ? AND "
                     "outcome IN ('unsigned', 'bad_signature') ORDER BY id DESC LIMIT 1",
                     (site, tool)).fetchone()
    return got[0] if got else None


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
