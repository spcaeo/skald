"""The one line for an AI agent: "set up Skald for <site> — read
<base>/traffic-kit/llms.txt and use code <code> (works once, 24 hours)".

A line carries one or more jobs (agent_jobs.py: logs, script, lead, rsc,
assets, privacy, mcp; Add a site's default is logs, script, lead).
`POST <page>/sites/agentlink` (kit_api.py) makes only the keys its jobs need
(a sending token for "logs", the site's lead secret for "lead", a read-only
MCP token for "mcp"), then an **agent code**: an entry in link.py's store
(kit-links.json, 0600, under its lock) with `kind: "agent"`:

    {"kind": "agent", "site", "made_at", "expires_at", "jobs",
     "token_id", "mcp_token_id" the tokens it made (null when its jobs need none)
     "made_by"                  who made the line (a user id, "cli"): the search key
                                route checks they are still an install admin
     "sealed", "sealed_lead",   the sending token, the lead secret, the report key and
     "sealed_report",           the MCP token, each sealed with its own keystream
     "sealed_mcp"               label (link.seal; never the install link's, so no other
                                code can hand them out); null when not made, once the
                                keys are taken, the code expired or was cancelled
     "report_key"               the report key's sha256: POST .../report needs the key
     "fields"                   link.FIELDS plus lead_url, tag, mcp_url, hooks_url:
                                nothing secret
     "leads", "lead_note"       leads asked for; "included", "env" or "none"
     "found"                    the site check's facts (site_setup `found`)
     "facts"                    what Skald had when the line was made, for the steps'
                                "Check first" (hook secrets set, MCP on, privacy and
                                asset settings): nothing secret
     "opened_at", "keys_at", "reported_at", "report", "cancelled_at",
     "token_revoked", "revoked_ids"}

The code itself is never kept or logged; the dashboard knows the entry by
its link_id, the first 16 hex of the code's sha256 (`sites/agentstatus`).
`cancel` ends a code at once (`sites/agentcancel`), and `make` with
`replace` ends the site's older live codes whose keys were not taken, inside
the same lock (`sites/agentlink`: one live line per site): seals wiped, every
route then answers as for an expired code. Both hand back the ids of every
token the code made that was never given out (the sending token and the MCP
token), for kit_api.py to revoke; `unrevoked` lists them for the ended codes
still to revoke (an expired code's, or one whose revoke failed), for
sites/agentstatus and the daily run. `mark_revoked` notes each token once its
revoke has succeeded (`revoked_ids`), and the entry `token_revoked` once all
of them are.

A request that changes nothing (a refused report, a second read of the
steps) never rewrites kit-links.json.

On the beacon helper (beacon_server.py), `serve` answers:

  GET  /traffic-kit/llms.txt          the public guide for an agent: no code, no secret
  GET  /traffic-kit/<code>            an agent code: to curl or Wget a script that says
                                      "read .../steps" and exits 1 (`| sudo bash` never
                                      runs Markdown); those words to anything else. Never
                                      burns. An install link's code: link.answer_code.
  GET  /traffic-kit/<code>/steps      the site's steps in Markdown, no secret; the first
                                      GET sets opened_at. Valid until expiry or a cancel.
  GET  /traffic-kit/<code>/keys       curl or Wget only: the keys once, as an env file
                                      (values shell-quoted; only the keys the jobs need,
                                      and SKALD_REPORT_KEY always),
                                      then the seals are wiped (keys_at). Again: 410.
                                      Another user agent (a web reader, which may pass the
                                      page through a model): 403 and nothing burned. HEAD:
                                      the status only.
  GET  /traffic-kit/<code>/install.sh the one-file installer without a token (it reads
                                      SKALD_SHIP_TOKEN). Valid until expiry or a cancel.
  GET  /traffic-kit/<code>/leads/<f>  the lead files without a secret (kit/leadfiles.py)
  POST /traffic-kit/<code>/report     JSON, at most 16 KiB, with the header
                                      X-Skald-Report-Key (from the keys file; missing or
                                      wrong: 403, nothing kept): only REPORT's keys are
                                      kept, each cleaned and capped. {"ok": true}
  POST /traffic-kit/<code>/hooksecret a booking, form or payment tool's hook secret, for
                                      a line with the lead job (agent_hooks.py)
  POST /traffic-kit/<code>/searchkey  a Search Console service-account key file, read
                                      from stdin, for a line with the search job
                                      (agent_search.py)
  GET  /traffic-kit/<code>/todo/<id>  a to-do line's to-do with every row, as JSON, with
                                      the report key header (agent_todos.py, 2.41)
  POST /traffic-kit/<code>/fix        a to-do line's report for one to-do, at most 256 KiB
                                      (agent_todos.py): "done" marks it done in Skald

A to-do line (Overview > Insights' Fix this, 2.41) is an agent code whose entry has
`todos` ([{id, kind, title}]) and `fixes` ({id: {state, at}}); its jobs are todo-<kind>.
It makes no token. A new to-do line ends only the site's older to-do lines; a set-up line
only older set-up lines. `latest` reads one family at a time.

Cache-Control no-store and X-Robots-Tag noindex on every answer (link._answer),
a limit per caller address and code on every route but llms.txt, each route
(ROUTES) with its own, so steps read many times never use up the keys' tries,
and one more per address across every code ("any"), so ten sessions on one
machine can each set up their own site at the same time; no code, token or
secret is ever logged.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from pathlib import Path

from . import agent_jobs, link
from .agent_jobs import FOUND_MOST, LEAD_WORDS, WAYS, keys_file, steps  # noqa: F401

KIND = "agent"
HERE = Path(__file__).resolve().parent / "agent"
TOKEN_LABEL = b"skald-kit-agent"     # never the install link's label (link.seal's default)
LEAD_LABEL = b"skald-kit-lead"
REPORT_LABEL = b"skald-kit-report"
MCP_LABEL = b"skald-kit-mcp"
REPORT_HEADER = "X-Skald-Report-Key"
WIPED = dict.fromkeys(link.SEALS)     # every seal of a code, wiped together
LINK_ID = re.compile(r"^[0-9a-f]{16}$")
HOST = re.compile(r"^[A-Za-z0-9.-]{1,253}(?::[0-9]{1,5})?$")
REPORT_MOST = 16 * 1024
NOTES_MOST = 1000
STATES = ("waiting", "opened", "keys_taken", "expired", "cancelled", "unknown")
# The routes, each with its own limit (beacon_server.py); "code" is the bare code.
ROUTES = ("code", "steps", "keys", "install.sh", "leads", "report", "hooksecret", "searchkey",
          "todo", "fix", "other")
WEB_READER = ("Fetch this with curl in a shell into a file; never with a web reader, which "
              "would put the keys in a chat. Nothing was used up: the keys are still there.\n")
# A value an agent might paste by mistake: a sending token or a lead secret.
SECRETISH = re.compile(r"skald_[0-9a-f]{4,16}_[A-Za-z0-9_-]{8,}|skh_[A-Za-z0-9_-]{8,}"
                       r"|whsec_[A-Za-z0-9_-]{8,}")


def link_id(code: str) -> str:
    return link.digest(code)[:16]


# --------------------------------------------------------------- store

def _key_hash(key: str) -> str:
    return hashlib.sha256(("skald-report-key:" + key).encode()).hexdigest()


def make(folder, site: str, token: str | None, token_id: str | None, fields: dict,
         lead_secret: str | None = None, lead_note: str = "none", leads: bool = True,
         found: dict | None = None, now: float | None = None, hours: int = link.HOURS,
         replace: bool = False, jobs=None, mcp_token: str | None = None,
         mcp_token_id: str | None = None, facts: dict | None = None,
         made_by: str | None = None,
         todos=None) -> tuple[str, int, list[tuple[str, str | None, str]]]:
    """(the code, when it expires, ended). Only the code's hash and the sealed
    keys are kept. `jobs`: agent_jobs.JOBS ids (None: the default, without
    "lead" when not `leads`). With `replace`, under the same lock: the site's
    older live codes whose keys were not taken are cancelled, and ended ones
    whose keys were never taken give up their tokens (until mark_revoked).
    `ended`: [(link_id, a token_id to revoke, or None when its keys were
    taken, or "" when it made no token, "cancelled" or "expired")], one row
    for each token to revoke. `todos` (2.41): [{id, kind, title}] makes a to-do line
    (agent_todos.py): its jobs are the to-dos' kinds, and `replace` ends only the
    site's older to-do lines (a set-up line only older set-up lines)."""
    from . import agent_todos
    now = time.time() if now is None else now
    if todos:
        todos = agent_todos.clean(list(todos))
        jobs = agent_todos.jobs_of(todos)
    else:
        jobs = agent_jobs.default(leads) if jobs is None else agent_jobs.clean(list(jobs))
    code = secrets.token_urlsafe(32)
    report_key = secrets.token_urlsafe(24)
    path = link.path_for(folder)
    keep = {k: str(fields.get(k) or "") for k in (*link.FIELDS, "lead_url", "tag", "mcp_url",
                                                  "hooks_url")}
    ended_now = []
    with link._locked(path):
        links = link._load(path)
        if replace:
            ended_now = _replace(links, site, now, bool(todos))
        links[link.digest(code)] = {
            "kind": KIND, "site": site, "made_at": int(now),
            "expires_at": int(now + hours * 3600), "jobs": jobs,
            "token_id": token_id or None, "mcp_token_id": mcp_token_id or None,
            "sealed": link.seal(token, code, TOKEN_LABEL) if token else None,
            "sealed_lead": link.seal(lead_secret, code, LEAD_LABEL) if lead_secret else None,
            "sealed_report": link.seal(report_key, code, REPORT_LABEL),
            "sealed_mcp": link.seal(mcp_token, code, MCP_LABEL) if mcp_token else None,
            "report_key": _key_hash(report_key),
            "fields": keep, "leads": "lead" in jobs,
            "lead_note": lead_note if lead_note in LEAD_WORDS else "none",
            "found": found if isinstance(found, dict) else None,
            "facts": facts if isinstance(facts, dict) else None,
            "made_by": str(made_by) if made_by is not None else None,
            "opened_at": None, "keys_at": None, "reported_at": None, "report": None,
            **({"todos": todos, "fixes": {}} if todos else {})}
        link._save(path, links, now)
    return code, int(now + hours * 3600), ended_now


def _replace(links: dict, site: str, now: float,
             todo: bool = False) -> list[tuple[str, str | None, str]]:
    """make's sweep, inside its lock: every code already in the store is older
    than the new one, whatever its made_at says (two calls may read the clock
    in one order and take the lock in the other). An older ended code whose
    tokens are still to revoke (expired, or a revoke failed) is "expired".
    Only codes of the same family: a to-do line (`todo`) or a set-up line."""
    out = []
    for key, entry in links.items():
        if entry.get("kind") != KIND or entry.get("site") != site \
                or bool(entry.get("todos")) != todo:
            continue
        was = state(entry, now)
        if was in ("waiting", "opened"):
            entry.update(cancelled_at=int(now), **WIPED)
            out += [(key[:16], tid, "cancelled") for tid in _ended_rows(entry)]
        else:
            out += [(key[:16], tid, "expired") for tid in _pending(entry)]
    return out


def _tokens(entry: dict) -> list[str]:
    """Every token the code made: the sending token, the MCP token."""
    return [tid for tid in (entry.get("token_id"), entry.get("mcp_token_id")) if tid]


def _pending(entry: dict) -> list[str]:
    """The token ids of a code whose keys were never taken that are not
    revoked yet."""
    if entry.get("keys_at") or entry.get("token_revoked"):
        return []
    done = set(entry.get("revoked_ids") or ())
    return [tid for tid in _tokens(entry) if tid not in done]


def _ended_rows(entry: dict) -> list[str | None]:
    """An ended code's rows for the caller: each token to revoke; else one
    row, None (its keys were taken, so its tokens stay) or "" (no token)."""
    return _pending(entry) or [None if _tokens(entry) else ""]


def _unused(entry: dict) -> str | None:
    """The first token id still to revoke, else None."""
    got = _pending(entry)
    return got[0] if got else None


def unrevoked(folder, site: str, now: float | None = None) -> list[tuple[str, str]]:
    """[(link_id, token_id)]: each token of the site's ended codes (expired
    or cancelled) whose keys were never taken and that is not revoked yet.
    Read only: the caller revokes, then mark_revoked."""
    now = time.time() if now is None else now
    return [(key[:16], tid) for key, entry in link._load(link.path_for(folder)).items()
            if entry.get("kind") == KIND and entry.get("site") == site and ended(entry, now)
            for tid in _pending(entry)]


def mark_revoked(folder, done, now: float | None = None) -> int:
    """Note each token in `done` [(link_id, token_id)] revoked, once its
    revoke has succeeded (`revoked_ids`; `token_revoked` once every token of
    the code is); how many. Saved only when one changed or the store holds an
    expired code's seals or an entry past its keeping (the daily run calls it
    with nothing, to tidy)."""
    now = time.time() if now is None else now
    path = link.path_for(folder)
    if not path.exists():
        return 0
    marked = 0
    with link._locked(path):
        links = link._load(path)
        for key, entry in links.items():
            if entry.get("kind") != KIND or entry.get("token_revoked"):
                continue
            had = set(entry.get("revoked_ids") or ())
            hit = [tid for tid in _tokens(entry) if tid not in had and any(
                key.startswith(lid) and tid == one for lid, one in done)]
            if not hit:
                continue
            marked += len(hit)
            gone = [tid for tid in _tokens(entry) if tid in had or tid in hit]
            if len(gone) == len(_tokens(entry)):
                entry["token_revoked"] = True
                entry.pop("revoked_ids", None)
            else:
                entry["revoked_ids"] = gone
        if marked or link.stale(links, now):
            link._save(path, links, now)
    return marked


def find(folder, code: str) -> dict | None:
    """The agent code's entry, or None (unknown, or an install link's code)."""
    if not link.CODE.match(code or ""):
        return None
    entry = link._load(link.path_for(folder)).get(link.digest(code))
    return entry if entry is not None and entry.get("kind") == KIND else None


def state(entry: dict | None, now: float | None = None) -> str:
    """One of STATES. Keys taken stays keys_taken after the expiry: the
    outcome is settled then. A cancelled code is "cancelled" always."""
    now = time.time() if now is None else now
    if entry is None:
        return "unknown"
    if entry.get("cancelled_at"):
        return "cancelled"
    if entry.get("keys_at"):
        return "keys_taken"
    if float(entry.get("expires_at") or 0) <= now:
        return "expired"
    return "opened" if entry.get("opened_at") else "waiting"


def ended(entry: dict, now: float | None = None) -> bool:
    """Expired or cancelled: every route then answers 410."""
    now = time.time() if now is None else now
    return bool(entry.get("cancelled_at")) or float(entry.get("expires_at") or 0) <= now


def _change(folder, code: str, change, now: float):
    """Run `change(entry)` on the code's entry under the store's lock: it
    answers (its answer, whether it changed the entry), and the store is saved
    only then. (its answer, the entry) or (None, None) when the code is unknown."""
    if not link.CODE.match(code or ""):
        return None, None
    path = link.path_for(folder)
    if not path.exists():
        return None, None
    with link._locked(path):
        links = link._load(path)
        entry = links.get(link.digest(code))
        if entry is None or entry.get("kind") != KIND:
            return None, None
        got, changed = change(entry)
        if changed:
            link._save(path, links, now)
    return got, entry


def opened(folder, code: str, now: float | None = None) -> dict | None:
    """The entry, with opened_at set the first time (until expiry)."""
    now = time.time() if now is None else now

    def change(entry):
        if not entry.get("opened_at") and not ended(entry, now):
            entry["opened_at"] = int(now)
            return None, True
        return None, False
    return _change(folder, code, change, now)[1]


def take(folder, code: str, now: float | None = None):
    """(state, entry, {"token", "lead", "report_key"} or None): the keys once;
    the seals are wiped."""
    now = time.time() if now is None else now

    def change(entry):
        was = state(entry, now)
        if was in ("keys_taken", "expired", "cancelled") or not (
                entry.get("sealed") or entry.get("sealed_report")):
            return ("keys_taken" if was == "keys_taken" else "expired", None), False

        def opened_seal(name, label):
            return link.unseal(entry[name], code, label) if entry.get(name) else None
        keys = {"token": opened_seal("sealed", TOKEN_LABEL),
                "lead": opened_seal("sealed_lead", LEAD_LABEL),
                "report_key": opened_seal("sealed_report", REPORT_LABEL)}
        if entry.get("sealed_mcp"):
            keys["mcp"] = opened_seal("sealed_mcp", MCP_LABEL)
        entry.update(keys_at=int(now), **WIPED)
        return ("ok", keys), True
    got, entry = _change(folder, code, change, now)
    if got is None:
        return "unknown", None, None
    return got[0], entry, got[1]


def keep_report(folder, code: str, report: dict, key: str | None,
                now: float | None = None) -> str:
    """"ok", "refused" (no report key, or the wrong one), "expired" (or
    cancelled) or "unknown"; the latest report replaces an earlier one. Only
    "ok" writes the store."""
    now = time.time() if now is None else now

    def change(entry):
        want = entry.get("report_key") or ""
        if not key or not want or not hmac.compare_digest(_key_hash(key), want):
            return "refused", False
        if ended(entry, now):
            return "expired", False
        entry.update(report=_for_line(report, agent_jobs.of(entry)), reported_at=int(now))
        return "ok", True
    got, _ = _change(folder, code, change, now)
    return got or "unknown"


def cancel(folder, site: str, lid: str,
           now: float | None = None) -> list[tuple[str, str | None]]:
    """End the agent code of `site` whose link_id is `lid` at once, whatever
    its state. [(link_id, a token_id never handed out and not yet revoked,
    for the caller to revoke and then mark_revoked)], one row for each such
    token; else one row with None (its keys were taken) or "" (it made no
    token)."""
    now = time.time() if now is None else now
    path = link.path_for(folder)
    if not LINK_ID.match(lid or "") or not path.exists():
        return []
    done = []
    with link._locked(path):
        links = link._load(path)
        for key, entry in links.items():
            if entry.get("kind") != KIND or entry.get("site") != site \
                    or entry.get("cancelled_at") or not key.startswith(lid):
                continue
            entry.update(cancelled_at=int(now), **WIPED)
            done += [(key[:16], tid) for tid in _ended_rows(entry)]
        if done:
            link._save(path, links, now)
    return done


def status(folder, site: str, lid: str, now: float | None = None) -> dict:
    """The wizard's view of one agent code of `site`, found by its link_id."""
    now = time.time() if now is None else now
    entry = None
    if LINK_ID.match(lid or ""):
        for key, got in link._load(link.path_for(folder)).items():
            if key.startswith(lid) and got.get("kind") == KIND and got.get("site") == site:
                entry = got
                break

    def when(key):
        return link.stamp(entry[key]) if entry and entry.get(key) else None
    report = (entry or {}).get("report")
    return {"state": state(entry, now), "opened_at": when("opened_at"),
            "keys_at": when("keys_at"), "reported_at": when("reported_at"),
            "cancelled_at": when("cancelled_at"),
            "report": report, "expires_at": when("expires_at"),
            "jobs": (report or {}).get("jobs"), "tools": (report or {}).get("tools"),
            "line_jobs": agent_jobs.of(entry) if entry else None,
            **({"todos": entry["todos"], "fixes": entry.get("fixes") or {}}
               if entry and entry.get("todos") else {})}


def latest(folder, sites, now: float | None = None, todo: bool = False) -> dict:
    """{site: its newest agent line's status (as `status`, plus link_id)},
    for the sites given that have one: the "Lines for your sites" view
    (kit_left.py) watches each site's own line after a reload. Read only.
    `todo`: the newest to-do line instead (Insights' Fix this)."""
    now = time.time() if now is None else now
    want, best = set(sites), {}
    for key, entry in link._load(link.path_for(folder)).items():
        site = entry.get("site")
        if entry.get("kind") != KIND or site not in want or bool(entry.get("todos")) != todo:
            continue
        if site not in best or float(entry.get("made_at") or 0) > best[site][1]:
            best[site] = (key[:16], float(entry.get("made_at") or 0))
    return {site: {"link_id": lid, **status(folder, site, lid, now)}
            for site, (lid, _) in best.items()}


# -------------------------------------------------------------- report

def _text(value, most: int) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    got = "".join(ch for ch in " ".join(str(value).split()) if ch.isprintable())
    got = SECRETISH.sub("[removed]", got)[:most].strip()
    return got or None


def _texts(value, many: int, most: int, test=None) -> list[str] | None:
    """At most `many` good values, from the first 5 x `many` given."""
    if not isinstance(value, list):
        return None
    out = []
    for one in value[:many * 5]:
        got = _text(one, most)
        if got and (test is None or test(got)) and got not in out:
            out.append(got)
            if len(out) == many:
                break
    return out


def _privacy(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    out = {}
    if isinstance(value.get("keep_ips"), bool):
        out["keep_ips"] = value["keep_ips"]
    days = value.get("days")
    if isinstance(days, int) and not isinstance(days, bool) and 0 <= days <= 3650:
        out["days"] = days
    url = _text(value.get("notice_url"), 300)
    if url and url.startswith(("https://", "http://")) and " " not in url:
        out["notice_url"] = url
    return out


PROPERTY = re.compile(r"^(?:sc-domain:[a-z0-9.-]{1,253}|https?://[^\s]{1,250}/)$")


def _search(value) -> dict | None:
    """{google_property, robot_added, bing_site}: a Search Console property
    (sc-domain:<host> or an address ending in /), whether the user said they
    added Skald's robot, the site's address in Bing. A recommendation only:
    the user connects it in Skald."""
    if not isinstance(value, dict):
        return None
    out = {}
    prop = _text(value.get("google_property"), 260)
    if prop and PROPERTY.match(prop):
        out["google_property"] = prop
    if isinstance(value.get("robot_added"), bool):
        out["robot_added"] = value["robot_added"]
    bing = _text(value.get("bing_site"), 260)
    if bing and bing.startswith(("https://", "http://")) and " " not in bing:
        out["bing_site"] = bing
    return out


def _leads(value) -> list[dict] | None:
    if not isinstance(value, list):
        return None
    out = []
    for one in value[:10]:
        if not isinstance(one, dict):
            continue
        got = {k: v for k, v in (("tool", _text(one.get("tool"), 60)),
                                 ("file", _text(one.get("file"), 300))) if v}
        if got:
            out.append(got)
    return out


def _job_states(value) -> dict | None:
    """{job id: done | already | skipped | left}, known ids only."""
    if not isinstance(value, dict):
        return None
    return {job: value[job] for job in agent_jobs.JOBS
            if isinstance(value.get(job), str) and value[job] in agent_jobs.STATES}


def _tools(value) -> list[dict] | None:
    """[{tool, hook: set | left}]: the hook tools only, each once."""
    from ..conversions import TOOLS
    if not isinstance(value, list):
        return None
    out = []
    for one in value[:len(TOOLS) * 5]:
        if not isinstance(one, dict):
            continue
        tool, hook = one.get("tool"), one.get("hook")
        if isinstance(tool, str) and tool in TOOLS and hook in ("set", "left") \
                and tool not in [got["tool"] for got in out]:
            out.append({"tool": tool, "hook": hook})
    return out


def _for_line(report: dict, jobs: list[str]) -> dict:
    """Only the line's own jobs in `jobs`, and `tools` only with the lead job."""
    out = dict(report)
    if isinstance(out.get("jobs"), dict):
        out["jobs"] = {job: how for job, how in out["jobs"].items() if job in jobs}
        if not out["jobs"]:
            del out["jobs"]
    if "lead" not in jobs:
        out.pop("tools", None)
    if "search" not in jobs:
        out.pop("search", None)
    return out


REPORT = {
    "jobs": _job_states, "tools": _tools,
    "hosting": lambda v: _text(v, 100), "server": lambda v: _text(v, 100),
    "log_path": lambda v: _text(v, 300), "framework": lambda v: _text(v, 60),
    "asset_paths": lambda v: _texts(v, 10, 200,
                                    lambda p: p.startswith("/") and " " not in p),
    "script_tag": lambda v: _text(v, 300),
    "leads": _leads, "privacy": _privacy, "search": _search,
    "nextjs_log_field": lambda v: v if isinstance(v, bool) else None,
    "changed_files": lambda v: _texts(v, 50, 300),
    "left_for_user": lambda v: _texts(v, 20, 300),
    "notes": lambda v: _text(v, NOTES_MOST),
}


def clean_report(raw) -> dict:
    """Only REPORT's keys, each cleaned and capped; an unknown key, a wrong
    kind or anything shaped like a token or lead secret is dropped.
    ValueError when it is not a JSON object."""
    if not isinstance(raw, dict):
        raise ValueError("The report is one JSON object.")
    out = {}
    for key, clean in REPORT.items():
        if key in raw:
            got = clean(raw[key])
            if got is not None and got != {} and got != []:
                out[key] = got
    return out


# --------------------------------------------------------------- pages

def _base(entry: dict | None, base: str) -> str:
    return ((entry or {}).get("fields", {}).get("base") or base or "").rstrip("/")


def guide(base: str) -> str:
    """llms.txt, filled: no code, no secret."""
    text = (HERE / "llms.txt").read_text(encoding="utf-8")
    return agent_jobs.fill(text, {"BASE": base.rstrip("/") or
                                  "the address you read this file from"})


def _lead_file(entry: dict, name: str) -> tuple[bytes, str] | None:
    from .leadfiles import PLUGIN, files, plugin_zip
    try:
        got = files(entry["site"], (entry.get("fields") or {}).get("lead_url") or "", None)
    except ValueError:
        return None
    if name == "skald-leads.zip":
        return plugin_zip(got[PLUGIN]), "application/zip"
    return (got[name], "text/plain; charset=utf-8") if name in got else None


def _send(h, code: int, body, kind: str = "text/plain; charset=utf-8") -> None:
    if isinstance(body, bytes):
        h.send_response(code)
        for k, v in (("Content-Type", kind), ("Cache-Control", "no-store"),
                     ("X-Robots-Tag", "noindex, nofollow"), ("X-Content-Type-Options", "nosniff"),
                     ("Content-Length", str(len(body)))):
            h.send_header(k, v)
        h.end_headers()
        if h.command != "HEAD":
            h.wfile.write(body)
        return None
    return link._answer(h, code, body, kind)


def _script(words: str) -> str:
    return "#!/bin/sh\necho '" + words.replace("'", "") + "' >&2\nexit 1\n"


def _expired(entry: dict, base: str) -> str:
    page = (entry.get("fields") or {}).get("dashboard") or f"{_base(entry, base)}/traffic/"
    what = "was cancelled" if entry.get("cancelled_at") else "has expired"
    if entry.get("todos"):
        return (f"This code {what}. Ask the user to press Fix this again in Skald: "
                f"{page} (Overview > Insights).\n")
    return (f"This code {what}. Ask the user to make a new line in Skald: "
            f"{page} (Settings > Sites).\n")


UNKNOWN = ("This code is not known. Ask the user to make a new line in Skald "
           "(Settings > Sites).\n")


def _own_base(h) -> str:
    """This request's own address, when the install names none (llms.txt only)."""
    host = h.headers.get("Host") or ""
    proto = h.headers.get("X-Forwarded-Proto") or "https"
    if not HOST.match(host) or proto not in ("https", "http"):
        return ""
    return f"{proto}://{host}"


def route(path: str) -> str:
    """Which of ROUTES a path after /traffic-kit/ is (llms.txt excepted)."""
    sub = path.partition("/")[2]
    if not sub:
        return "code"
    if sub.startswith("leads/"):
        return "leads"
    if sub.startswith("todo/"):
        return "todo"
    return sub if sub in ROUTES else "other"


def serve(h, folder, base: str, limits, address: str, config: dict | None = None,
          config_path=None) -> None:
    """Every /traffic-kit/ request on the beacon helper (GET, HEAD, POST).
    `limits`: {route: a Limiter} (one per ROUTES), or one Limiter for all.
    `config`, `config_path`: the install's, for POST .../hooksecret."""
    path = h.path.split("?", 1)[0][len(link.PREFIX):]
    if path == "llms.txt":
        if h.command == "POST":
            return _send(h, 405, "Read this with GET.\n")
        return _send(h, 200, guide((base or "").rstrip("/") or _own_base(h)))
    limiter = limits[route(path)] if isinstance(limits, dict) else limits
    anyone = limits.get("any") if isinstance(limits, dict) else None
    code, _, sub = path.partition("/")
    # Per address AND code: ten sessions on one machine (one address) each set up their
    # own site at once; "any" still caps one address across every code.
    if (anyone is not None and not anyone.allow(address)) or \
            not limiter.allow(f"{address} {code[:16]}"):
        return _send(h, 429, "Too many tries. Wait a minute and try again.\n")
    if h.command == "POST":
        if sub == "report":
            return _report(h, folder, code)
        if sub == "hooksecret":
            from . import agent_hooks
            return agent_hooks.answer(h, folder, code, config, config_path)
        if sub == "searchkey":
            from . import agent_search
            return agent_search.answer(h, folder, code, config)
        if sub == "fix":
            from . import agent_todos
            return agent_todos.fix(h, folder, code, config, config_path)
        return _send(h, 405, "Only the report, a hook secret, a search key and a to-do's fix "
                             "are sent with POST.\n")
    entry = find(folder, code)
    if not sub:
        if entry is None:                          # an install link, or unknown: as before
            return link.answer_code(h, folder, base, code)
        return _bare(h, entry, code, base)
    if entry is None:
        return _send(h, 404, UNKNOWN)
    now = time.time()
    if sub == "keys":
        return _keys(h, folder, entry, code, base, now)
    if ended(entry, now):
        return _send(h, 410, _expired(entry, base))
    if sub == "steps":
        if h.command == "GET" and not entry.get("opened_at"):
            entry = opened(folder, code, now) or entry
        try:
            text = steps(entry, code, base)
        except ValueError:
            return _send(h, 500, "The steps could not be made. Ask the user to make a new line "
                                 "in Skald, and to tell whoever runs their Skald.\n")
        return _send(h, 200, text, "text/markdown; charset=utf-8")
    if sub == "install.sh":
        from . import one_file
        fields = entry.get("fields") or {}
        try:
            data = one_file(entry["site"], fields["url"], fields["dashboard"], fields["help"],
                            fields.get("image") or None, fields.get("ship_path") or None, None)
        except (ValueError, KeyError, OSError):
            return _send(h, 500, _script("The installer could not be made. Ask the user to "
                                         "make a new line in Skald."))
        return _send(h, 200, data)
    if sub.startswith("todo/"):
        from . import agent_todos
        return agent_todos.rows(h, folder, code, sub[len("todo/"):], now)
    if sub.startswith("leads/"):
        got = _lead_file(entry, sub[len("leads/"):])
        if got is None:
            return _send(h, 404, "No such lead file. See leads/README.md.\n")
        return _send(h, 200, got[0], got[1])
    return _send(h, 404, "No such page for this code. Read its steps: "
                         f"{_base(entry, base)}{link.PREFIX}{code}/steps\n")


def _bare(h, entry: dict, code: str, base: str) -> None:
    """The bare code of an agent: never an installer, never Markdown to curl."""
    tool = (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS)
    if ended(entry):
        words = _expired(entry, base).strip()
        return _send(h, 200, _script(words)) if tool else _send(h, 410, words + "\n")
    words = f"This code is for an AI agent: read {_base(entry, base)}{link.PREFIX}{code}/steps"
    return _send(h, 200, _script(words) if tool else words + "\n")


def _keys(h, folder, entry: dict, code: str, base: str, now: float) -> None:
    tool = (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS)
    was = state(entry, now)
    if was == "keys_taken":
        return _send(h, 410, "The keys were taken already: they work once. Ask the user to make "
                             "a new line in Skald (Settings > Sites).\n")
    if was in ("expired", "cancelled"):
        return _send(h, 410, _expired(entry, base))
    if not tool:
        return _send(h, 403, WEB_READER)
    if h.command != "GET":                          # HEAD: the status only, never burned
        return _send(h, 200, "")
    got, entry, keys = take(folder, code, now)
    if got != "ok":
        return _send(h, 410, "The keys were taken already: they work once.\n")
    return _send(h, 200, keys_file(entry, keys))


def _json(h, code: int, body: dict) -> None:
    link._answer(h, code, json.dumps(body) + "\n", "application/json; charset=utf-8")


def _report(h, folder, code: str) -> None:
    try:
        length = int(h.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return _json(h, 411, {"ok": False, "error": "Send the report with a Content-Length."})
    if length > REPORT_MOST:
        return _json(h, 413, {"ok": False, "error": "The report is at most 16 KiB."})
    try:
        report = clean_report(json.loads(h.rfile.read(length).decode("utf-8") or "null"))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return _json(h, 400, {"ok": False, "error": "The report is one JSON object."})
    got = keep_report(folder, code, report, (h.headers.get(REPORT_HEADER) or "").strip())
    if got == "refused":
        return _json(h, 403, {"ok": False, "error": f"Send the {REPORT_HEADER} header with "
                                                    "SKALD_REPORT_KEY from the keys file."})
    if got == "unknown":
        return _json(h, 404, {"ok": False, "error": UNKNOWN.strip()})
    if got == "expired":
        return _json(h, 410, {"ok": False, "error": "This code has expired or was cancelled."})
    return _json(h, 200, {"ok": True})
