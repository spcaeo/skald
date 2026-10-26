"""POST /traffic-kit/<code>/hooksecret: a booking, form or payment tool's hook
secret, set by the AI agent of a line with the lead job (agent.py serves it;
docs/plans/2026-10-26-agent-everywhere.md).

curl or Wget only (anything else: 403, nothing made), the header
X-Skald-Report-Key (SKALD_REPORT_KEY from the keys file; missing or wrong:
403), a JSON object of at most 2 KiB with a Content-Length:

  {"tool": t, "make": true}   a tool whose secret Skald makes (conversions.TOOLS
                              but lead and integrations_api.OWN_SECRET): a new
                              secret, kept 0600 in the secrets file Settings >
                              Integrations uses (secrets_store), and answered
                              once as one env line, `SKALD_HOOK_SECRET_<TOOL>=...`
                              (text/plain), for the agent's curl -o into a 0600
                              file and then into the tool, never into the chat
  {"tool": t, "secret": s}    the signing secret the tool made (Stripe's whsec_...,
                              HubSpot's client secret; Calendly, Cal.com and
                              Typeform may give their own), read by the steps'
                              command from stdin: kept as a pasted one, never
                              sent back. {"ok": true, "tool", "replaced"}
  "replace": true             only then is a secret the site has already
                              replaced (409 without it), so a second run never
                              breaks a hook that works

Refused: no lead job on the line (403), a tool not in TOOLS (400), "lead"
(its secret is SKALD_LEAD_SECRET in the keys file: 400), a secret kept in the
server's environment (409), `make` for Stripe or HubSpot (409), a `secret` for
a tool only Skald signs for (400). An expired or cancelled code: 410. Each
kept secret writes one audit row, hook.secret, actor "ai-agent", with the
link id; no secret is ever logged or kept anywhere else. The route has its
own rate limit (agent.ROUTES).
"""
from __future__ import annotations

import hmac
import json
import shlex
import sqlite3
import sys
import time
from pathlib import Path

from . import agent, agent_jobs, link

MOST = 2048
ACTOR = "ai-agent"
ASK = 'Send one JSON object: {"tool": "<tool>", "make": true} or {"tool": "<tool>", "secret": "..."}.'


def _no(h, code: int, error: str) -> None:
    agent._json(h, code, {"ok": False, "error": error})


def _body(h) -> tuple[dict | None, tuple[int, str] | None]:
    try:
        length = int(h.headers.get("Content-Length") or -1)
    except ValueError:
        length = -1
    if length < 0:
        return None, (411, "Send the request with a Content-Length.")
    if length > MOST:
        return None, (413, "The request is at most 2 KiB.")
    try:
        form = json.loads(h.rfile.read(length).decode("utf-8") or "null")
    except (ValueError, UnicodeDecodeError, RecursionError):
        form = None
    return (form, None) if isinstance(form, dict) else (None, (400, ASK))


def answer(h, folder, code: str, config: dict | None, config_path=None,
           now: float | None = None) -> None:
    now = time.time() if now is None else now
    if not (h.headers.get("User-Agent") or "").lower().startswith(link.AGENTS):
        return _no(h, 403, "Send this with curl in a shell; never with a web reader or fetch "
                           "tool. Nothing was made.")
    form, why = _body(h)
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
    if agent.ended(entry, now):
        return _no(h, 410, "This code has expired or was cancelled.")
    if "lead" not in agent_jobs.of(entry):
        return _no(h, 403, "This line has no lead job, so it cannot set a hook's secret. Ask "
                           "the user to set it in Skald (Settings > Integrations), or for a line "
                           "with the lead job.")
    if config is None:
        return _no(h, 503, "Hook secrets cannot be set through this server. Ask the user to set "
                           "it in Skald (Settings > Integrations).")
    return _keep(h, folder, code, entry, form, config, config_path)


def _keep(h, folder, code: str, entry: dict, form: dict, config: dict, config_path) -> None:
    from ..conversions import TOOLS, secrets_store
    from ..conversions.hooks import site_configs
    from ..conversions.roads import TOOL_NAMES
    from ..integrations_api import EITHER, OWN_SECRET, PASTED
    tool = form.get("tool")
    if not isinstance(tool, str) or tool not in TOOLS:
        return _no(h, 400, f"Name one of the tools: {', '.join(t for t in TOOLS if t != 'lead')}.")
    if tool == "lead":
        return _no(h, 400, "The lead secret is SKALD_LEAD_SECRET in the keys file: use that one.")
    make, given = form.get("make") is True, form.get("secret")
    if make == (given is not None):
        return _no(h, 400, ASK)
    site, name = entry["site"], TOOL_NAMES.get(tool, tool)
    conf = site_configs(config, config_path).get(site) or config
    env = secrets_store.env_name(conf, site, tool)
    if env:
        return _no(h, 409, f"{name}'s secret is kept in the Skald server's environment ({env}), "
                           "so it cannot be set here. Ask whoever runs the user's Skald.")
    value = ""
    if make and tool in OWN_SECRET:
        return _no(h, 409, f"{name} makes its own signing secret. Send it with \"secret\" "
                           "instead, as the steps show.")
    if not make:
        if tool not in OWN_SECRET + EITHER:
            return _no(h, 400, "Skald makes this hook's secret: send \"make\": true.")
        value = given.strip() if isinstance(given, str) else ""
        if not PASTED.match(value):
            return _no(h, 400, f"The secret from {name} is one line, no spaces, 12 to 500 "
                               "characters.")
        if tool == "stripe" and not value.startswith("whsec_"):
            return _no(h, 400, "A Stripe signing secret starts with whsec_ (the webhook "
                               "endpoint's signing secret).")
    path = secrets_store.path_for(config, folder)
    try:
        had = bool(secrets_store.load(path).get(secrets_store.key(site, tool)))
    except secrets_store.Exposed:
        return _no(h, 500, "Skald's secrets file is not private on its server, so nothing was "
                           "kept. Ask whoever runs the user's Skald to fix it.")
    if had and form.get("replace") is not True:
        return _no(h, 409, f"This site has a {name} secret in Skald already. If {name}'s webhook "
                           "works, leave it. To replace it, ask the user first (the old secret "
                           "stops working at once), then send \"replace\": true.")
    value = secrets_store.make() if make else value
    secrets_store.put(path, secrets_store.key(site, tool), value)
    how = ("made" if make else "pasted") + (", replaced" if had else "")
    _audit(config, folder, site, tool, f"{how} (AI agent set-up, link {agent.link_id(code)})")
    if make:
        return agent._send(h, 200, f"SKALD_HOOK_SECRET_{tool.upper()}={shlex.quote(value)}\n")
    return agent._json(h, 200, {"ok": True, "tool": tool, "replaced": had})


def _audit(config: dict, folder, site: str, tool: str, detail: str) -> None:
    """One audit row in the accounts file (never the secret). A failure is
    one line on stderr, without a value: the secret is kept already."""
    from ..accounts import auditlog
    from ..accounts import db as base
    from ..accounts.orgs import org_of_site
    path = base.path_for(config, Path(folder))
    if path is None or not Path(path).is_file():
        return
    try:
        db = base.connect(path)
        try:
            org = org_of_site(db, site)
            auditlog.record(db, org["id"] if org else None, ACTOR, "hook.secret",
                            f"{site}/{tool}", detail)
        finally:
            db.close()
    except (sqlite3.Error, OSError) as why:
        print(f"kit hooksecret: the audit row for {site}/{tool} could not be written "
              f"({type(why).__name__})", file=sys.stderr)
