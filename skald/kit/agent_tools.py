"""POST /traffic-kit/<code>/toolkey?tool=<id>[&<option>=<value>][&replace=1]: a key
to one of the person's own tools (Google Analytics...; yourtools/), handed to
Skald by the AI agent of a line with the connect-tools job (agent.py serves it;
docs/TOOLS.md, "Connecting through your AI agent").

The agent finds what it can in the site's project (the names only, never the
values), lists it, and asks the user before it sends each key (connect-tools.md).
Then it sends the key file or token as the request body from stdin (`curl
--data-binary @- < file`, or a token piped from the user's environment): never
on a command line, never in a chat.

curl or Wget only (anything else: 403, nothing kept), the header
X-Skald-Report-Key (SKALD_REPORT_KEY from the keys file; missing or wrong: 403),
the key as the body (at most the tool's own limit, never more than MOST bytes,
with a Content-Length). The query names the tool and its options (GA4:
`property=123456789`), never a secret. `key=search` with an empty body: the tool
uses the install's Search Console key (GA4's `shares_key`), nothing sent.

Kept exactly as Settings > Leads & tools keeps a pasted one (yourtools/sync.connect:
the adapter's check_key, then keys.put into the secrets file, 0600), and the
tool is switched on. Answers {"ok": true, "tool", "who", "replaced"}: "who" is
the key's robot address or account name, never the key.

Refused: no connect-tools job on the line (403); the line's maker is no longer
an install admin (403, the owner's rule: only whoever runs Skald hands it keys
from a line); a tool Skald does not know or a bad option (400); a key the tool
does not take (400, in plain words, never echoing it); a key Skald has already
(409, unless `replace=1`: Skald never replaces a working key by itself); a key
kept in the server's environment (409); an expired or cancelled code (410). Each
kept key writes one audit row, tools.key, actor "ai-agent", with the tool, the
robot's address and the link id; the key is never logged or kept anywhere else.
The route has its own rate limit (agent.ROUTES).
"""
from __future__ import annotations

import hmac
import sqlite3
import sys
from pathlib import Path
from urllib.parse import parse_qs

from . import agent, agent_jobs, link
from .agent_search import install_admin

MOST = 8192                    # the largest key any tool takes (a Google key file: ~2.4 KB)
ACTOR = "ai-agent"
JOB = "connect-tools"


def _no(h, code: int, error: str, **more) -> None:
    agent._json(h, code, {"ok": False, "error": error, **more})


def _query(h) -> dict:
    raw = h.path.partition("?")[2]
    return {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items() if v}


def _body(h, most: int) -> tuple[str | None, tuple[int, str] | None]:
    try:
        length = int(h.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return None, (411, "Send the key with a Content-Length (curl --data-binary @-).")
    if length > most:
        return None, (413, "The request is too long for this tool's key: send only the key.")
    try:
        return (h.rfile.read(length).decode("utf-8") if length else ""), None
    except UnicodeDecodeError:
        return None, (400, "The key is not text. Send the key file or token as it is.")


def answer(h, folder, code: str, config: dict | None, config_path=None) -> None:
    from ..yourtools import adapters, get
    if not (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS):
        return _no(h, 403, "Send this with curl in a shell, the key from stdin; never with a "
                           "web reader or fetch tool. Nothing was kept.")
    asked = _query(h)
    adapter = get(asked.get("tool"))
    if adapter is None:
        return _no(h, 400, f"Name the tool with ?tool=: {', '.join(adapters()) or 'none yet'}.")
    raw, why = _body(h, min(MOST, adapter.key_most))
    if why:
        return _no(h, *why)
    entry = agent.find(folder, code)
    if entry is None:
        return _no(h, 404, agent.UNKNOWN.strip())
    key = (h.headers.get(agent.REPORT_HEADER) or "").strip()
    want = entry.get("report_key") or ""
    if not key or not want or not hmac.compare_digest(agent._key_hash(key), want):
        return _no(h, 403, f"Send the {agent.REPORT_HEADER} header with SKALD_REPORT_KEY from "
                           "the keys file.")
    if agent.ended(entry):
        return _no(h, 410, "This code has expired or was cancelled.")
    if JOB not in agent_jobs.of(entry):
        return _no(h, 403, "This line has no connect-tools job, so it cannot hand Skald a key.")
    if config is None:
        return _no(h, 503, "A key cannot be set through this server. Ask the user to paste it "
                           "in Skald (Settings > Leads & tools > Connect a tool).")
    return _keep(h, folder, code, entry, adapter, asked, raw, config, config_path)


def _keep(h, folder, code: str, entry: dict, adapter, asked: dict, raw: str, config: dict,
          config_path) -> None:
    from ..conversions import secrets_store
    from ..conversions.hooks import site_configs
    from ..yourtools import keys
    from ..yourtools.base import BadKey
    from ..yourtools.sync import connect
    site = entry["site"]
    if not install_admin(config, folder, entry.get("made_by")):
        return _no(h, 403, "Only whoever runs this Skald may hand it keys from a line, and this "
                           "line was not made by them. Tell the user: paste the key in Skald, "
                           "Settings > Leads & tools > Connect a tool.")
    conf = site_configs(config, config_path).get(site) or config
    options = {k: v for k, v in asked.items() if k in adapter.options}
    shared = asked.get("key") == keys.SHARED and adapter.shares_key == keys.SHARED
    if shared:
        options["key"] = keys.SHARED
    elif not (raw or "").strip():
        return _no(h, 400, "Send the key as the body, from stdin.")
    try:
        got = connect(conf, folder, site, adapter.id, options, ACTOR,
                      key=None if shared else raw, replace=asked.get("replace") == "1")
    except BadKey as no:
        return _no(h, 400, str(no))
    except ValueError as no:
        have = keys.state(conf, folder, site, adapter.id)
        status = 409 if have.get("set") and not shared else 400
        return _no(h, status, str(no), **({"who": have.get("who")} if status == 409 else {}))
    except secrets_store.Exposed:
        return _no(h, 500, "Skald's secrets file is not private on its server, so nothing was "
                           "kept. Ask whoever runs the user's Skald to fix it.")
    except OSError:
        return _no(h, 503, "Skald's server has no secrets file. Ask whoever runs it.")
    how = "the Search Console key" if shared else (
        f"key {'replaced' if got['replaced'] else 'kept'}" + (f" ({got['who']})" if got["who"]
                                                             else ""))
    _audit(config, folder, site, f"{adapter.name}: {how} (AI agent set-up, link "
                                 f"{agent.link_id(code)}, for {site})")
    return agent._json(h, 200, {"ok": True, **got})


def _audit(config: dict, folder, site: str, detail: str) -> None:
    """One audit row (never the key). A failure is one line on stderr."""
    from ..accounts import auditlog
    from ..accounts import db as base
    from ..accounts.orgs import org_of_site
    try:
        path = base.path_for(config, Path(folder))
        if path is None or not Path(path).is_file():
            return
        db = base.connect(path)
        try:
            org = org_of_site(db, site)
            auditlog.record(db, org["id"] if org else None, ACTOR, "tools.key", site, detail)
        finally:
            db.close()
    except (sqlite3.Error, OSError) as why:
        print(f"kit toolkey: the audit row for {site} could not be written "
              f"({type(why).__name__})", file=sys.stderr)


# ------------------------------------------------------------ the job's steps

def _plain(value) -> str:
    from .agent_jobs import _plain as plain
    return plain(value)


def facts(config: dict, folder, site: str, may_upload: bool) -> dict:
    """What Skald has for the site's tools now, for the steps' "Check first":
    each tool's state, where its key lives and its robot's address (never the
    key), and the Search Console robot a Google tool may share. Nothing secret."""
    from ..search import google
    from ..yourtools import adapters, conn, keys
    parts = conn.load(folder, site)
    tools = {}
    for tool in adapters():
        part = parts.get(tool) or {}
        key = keys.state(config, folder, site, tool, part.get("options"))
        st = conn.status(part, bool(key.get("set")))
        tools[tool] = {"state": st["state"], "words": st["words"],
                       "key": "env" if keys.in_env(config, site, tool)
                       else ("set" if key.get("set") else "none"),
                       "who": key.get("who"), "options": part.get("options") or {}}
    robot = google.key_state(config, folder)
    return {"your_tools": tools, "may_set_tool_keys": bool(may_upload),
            "search_robot": robot.get("client_email") if robot.get("set") else None}


KEY_WORDS = {"set": "Skald has its key", "none": "no key yet",
             "env": "its key is kept in the Skald server's environment (only whoever runs "
                    "Skald changes it)"}


def now_lines(facts: dict) -> str:
    from ..yourtools import adapters
    have = facts.get("your_tools") if isinstance(facts.get("your_tools"), dict) else {}
    lines = []
    for tool, adapter in adapters().items():
        got = have.get(tool) or {}
        line = (f"- {adapter.name} (`{tool}`): {_plain(got.get('words') or 'not connected')}; "
                f"{KEY_WORDS.get(got.get('key'), 'not known')}")
        if got.get("who"):
            line += f", robot `{_plain(got['who'])}`"
        opts = ", ".join(f"{k} `{_plain(v)}`"
                         for k, v in sorted((got.get("options") or {}).items()))
        lines.append(line + (f"; {opts}" if opts else ""))
    if facts.get("search_robot"):
        lines.append(f"- Skald's Search Console robot: `{_plain(facts['search_robot'])}` (a "
                     "Google tool can use the same robot: nothing to make)")
    if not facts.get("may_set_tool_keys"):
        lines.append("- This line may not hand Skald keys: it was not made by whoever runs "
                     "Skald. Find and list what the project has, then put each tool in "
                     "`left_for_user` (paste the key in Skald, Settings > Leads & tools).")
    return "\n".join(lines) or "- Skald knows no tool yet."


def find_lines() -> str:
    from ..yourtools import adapters
    out = []
    for tool, adapter in adapters().items():
        names = ", ".join(f"`{n}`" for n in adapter.env_names) or "none known"
        opts = "; ".join(f"{o.label}: {', '.join(f'`{n}`' for n in o.env) or 'ask the user'}"
                         for o in adapter.options.values())
        out.append(f"- **{adapter.name}** (`{tool}`): the key is {adapter.key_words}; "
                   f"look for {names}. {('Its ' + opts + '. ') if opts else ''}"
                   f"Permission: {adapter.permission}. {adapter.find_more}".rstrip())
    return "\n".join(out) or "- Skald knows no tool yet: report this job as `skipped`."


def send_lines(facts: dict, site: str, env_dir: str, env_file: str, url: str) -> str:
    from ..yourtools import adapters
    header = (f"-H @<(grep '^SKALD_REPORT_KEY=' {env_file} | sed "
              "'s/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /')")
    curl = f"curl -sS -w '\\nHTTP %{{http_code}}\\n' -X POST {header} --data-binary @-"
    out = []
    for tool, adapter in adapters().items():
        query = f"tool={tool}" + "".join(f"&{k}=<{o.label.lower().replace(' ', '-')}>"
                                         for k, o in adapter.options.items() if o.required)
        out.append(f"**{adapter.name}**\n")
        out.append(adapter.send_steps(curl=curl, url=f"{url}?{query}", site=site,
                                      env_dir=env_dir, robot=facts.get("search_robot")))
        out.append("")
    return "\n".join(out).strip() or "Nothing to send: Skald knows no tool yet."
