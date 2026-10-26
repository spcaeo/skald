"""The one-command install and the set-up pack: Settings > Connections'
routes beside sites/kit (sites_api.py routes them, with its session, owner
or admin role, same-origin and CSRF checks):

  POST sites/kit {site, method: "server", include_token?, token?}
       -> the one-file installer, text/x-shellscript, skald-install-<site>.sh
          (connections_api.kit_zip hands it here; docker and systemd stay zips)
  POST sites/link {site}
       -> {ok, url, command, expires_at, token, token_id}: a new sending token
          ("Sending logs: <site>, <day> (one-command install)") and a one-time
          link, `curl -fsSL <url> | sudo bash`, for 24 hours (kit/link.py). The
          token is answered once, so the page can offer the file too. 409 when
          the log endpoint is off.
  POST sites/pack {site, include_secrets, token?, lead_secret?}
       -> skald-setup-<site>.zip (kit/pack.py). With include_secrets and no
          token, a new sending token is made (its id in X-Skald-Token-Id); the
          lead secret is the one given (the page just made it, checked against
          the store), else the one the site has, else one made now; none when
          it is kept in the server's environment.
  POST sites/packmail {site, to: [up to 3], include_secrets, token?, lead_secret?, note?}
       -> {ok, sent_to, token_id, lead_secret_made}: the same zip, mailed
          through the install's mail settings. 409 when mail is not set up,
          429 after PACKMAIL_PER_HOUR mails of a site in an hour. A token made
          for a mail that did not go is revoked again.
  POST sites/agentlink {site, jobs?: [id, ...], leads: bool = true}
       -> {ok, line, llms_url, steps_url, expires_at, token_id, link_id,
          cancelled, jobs, mcp_token_id?}: the one line for an AI agent
          (kit/agent.py), for the jobs asked (kit/agent_jobs.py: logs,
          script, lead, rsc, assets, privacy, mcp; without `jobs`: logs,
          script, lead, or logs, script with leads false). Only the keys the
          jobs need, sealed under a one-time code for 24 hours: a new sending
          token ("AI agent set-up") for logs, the site's lead secret (the one
          it has, else one made now) for lead, a read-only MCP token for this
          site for mcp (`mcp_token_id`). token_id: null without logs. Never
          answers a token or the secret. 400 for an unknown job or an empty
          list, 409 when the log endpoint is off and logs is asked. link_id:
          the first 16 hex of the code's sha256. Its core is
          make_agent_line(db, config, org, site, jobs, actor, ...), which the
          MCP's setup_line calls too (Refused, a ValueError, for a refusal).
          One live line per site: in the same lock as the new code, the site's
          older codes whose keys were not taken are cancelled and their unused
          tokens revoked (`cancelled`: how many), and expired ones whose keys
          were never taken give up their token too. A token is marked revoked
          only once its revoke succeeded; one that failed stays as it was, is
          listed in `not_revoked` (and the audit row), and is tried again.
  POST sites/agentstatus {site, link_id}
       -> {ok, state: waiting | opened | keys_taken | expired | cancelled |
          unknown, opened_at, keys_at, reported_at, report, cancelled_at,
          expires_at, jobs, tools, line_jobs}: that site's agent code only.
          jobs and tools: the report's ({id: done | already | skipped |
          left}, [{tool, hook: set | left}]), null before a report;
          line_jobs: the line's job ids. Once it reads expired or cancelled,
          the site's ended codes' unused tokens are revoked.
  POST sites/agentcancel {site, link_id}
       -> {ok, state: "cancelled"}: the code ends at once (its keys can no
          longer be taken; every route answers as expired); its token is
          revoked when the keys were never taken (`not_revoked` when that
          failed). 404 for an unknown code.

Every token a line made (its sending token and its MCP token) is revoked when
the line ends before its keys were taken.

The daily run (`daily`, a step of run-daily for each site) revokes the
unused tokens of the site's expired or cancelled codes still to revoke, so an
expired line's token goes within a day, before its entry is dropped.

Every route writes the audit log (who, site, how many recipients, keys or
not); no token, secret, code or address is ever logged.
"""
from __future__ import annotations

import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from . import ingest, kit
from .auth_api import text
from .files import slug

PACKMAIL_PER_HOUR = 10


def _folder(c) -> Path:
    from .conversions import hooks
    return Path(c.live_dir) if c.live_dir is not None else \
        hooks.history_folder(c.config, c.config_path)


def fields(c, site: str) -> dict:
    """The installer's values for the site: nothing secret."""
    from .connections_api import send_base
    base = send_base(c)
    page = f"{base}/traffic/{slug(site)}/"
    return {"base": base, "url": f"{base}{ingest.PREFIX}{site}", "dashboard": page,
            "help": f"{page}#help?part=troubleshooting-connections",
            "image": kit.image(c.config) or "", "ship_path": kit.ship_path(c.config)}


def installer(site: str, got: dict, token: str | None = None) -> bytes:
    return kit.one_file(site, got["url"], got["dashboard"], got["help"],
                        got["image"] or None, got["ship_path"] or None, token)


def send_bytes(h, data: bytes, kind: str, name: str, more=()) -> None:
    h.send_response(200)
    for k, v in (("Content-Type", kind), ("Content-Disposition", f'attachment; filename="{name}"'),
                 ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                 ("Content-Length", str(len(data))), *more):
        h.send_header(k, v)
    h.end_headers()
    h.wfile.write(data)


def server_file(c, site: str, token: str | None):
    """The one-file installer as a download (sites/kit, method "server")."""
    try:
        data = installer(site, fields(c, site), token)
    except ValueError as why:
        return c.no(400, str(why))
    send_bytes(c.h, data, "text/x-shellscript; charset=utf-8", f"skald-install-{site}.sh")
    return None


def _site(c, form) -> str | None:
    from .connections_api import _site as of_org
    return of_org(c, text(form, "site", 200))


def _new_token(c, site: str, why: str) -> tuple[str, str]:
    from .accounts import apitokens
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    token = apitokens.create(c.db, c.org["id"], f"Sending logs: {site}, {day} ({why})",
                             sites=[site], scopes=("ingest",), actor=c.uid)
    return token, token.split("_", 2)[1]


def _given_token(c, site: str, form) -> tuple[str | None, str | None]:
    """(a token the page gave, None) or (None, why it cannot go in)."""
    from .accounts import apitokens
    token = text(form, "token", 200).strip()
    if not token:
        return None, None
    ok, why, _ = apitokens.check(c.db, f"Bearer {token}", site, "ingest")
    return (token, None) if ok else (None, f"The token cannot go in the pack: {why}.")


def _audit(c, action: str, site: str, detail: str) -> None:
    from .accounts import auditlog
    auditlog.record(c.db, c.org["id"], c.uid, action, site, detail)


# ------------------------------------------------------------------ link

def link(c, form):
    from .kit import link as links
    site = _site(c, form)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    if not ingest.enabled(c.config):
        return c.no(409, "The log endpoint is switched off on this server "
                         "(ingest.enabled in the server's config).")
    got = fields(c, site)
    try:
        installer(site, got)                   # it can be built here, before a token is made
    except ValueError as why:
        return c.no(400, str(why))
    token, tid = _new_token(c, site, "one-command install")
    code, expires = links.make(_folder(c), site, token, tid, got)
    _audit(c, "kit.link", site, f"token {tid}; works once, for {links.HOURS} hours")
    url = f"{got['base']}{links.PREFIX}{code}"
    return c.ok(url=url, command=f"curl -fsSL {url} | sudo bash",
                expires_at=links.stamp(expires), token=token, token_id=tid)


# ------------------------------------------------------------------ pack

def _lead_secret(c, site: str, form, include: bool,
                 why: str = "set-up pack") -> tuple[str | None, str, str | None]:
    """(the lead secret for the pack, the note's kind, why not: a refusal)."""
    from .conversions import hooks, secrets_store
    if not include:
        return None, "none", None
    conf = hooks.site_configs(c.config, c.config_path).get(site) or c.config
    if secrets_store.env_name(conf, site, "lead"):
        return None, "env", None
    path = secrets_store.path_for(c.config, _folder(c))
    try:
        had = secrets_store.load(path).get(secrets_store.key(site, "lead"))
    except secrets_store.Exposed as why:
        return None, "none", f"{why}. Fix it on the server first."
    given = text(form, "lead_secret", 200).strip()
    if given:
        if not had or given != had:
            return None, "none", "That lead secret is not this site's. Make it again and retry."
        return given, "included", None
    if had:      # the owner (2026-10-23): the pack holds every key it needs, not a placeholder
        _audit(c, "hook.secret", f"{site}/lead",
               "put in a set-up pack" if why == "set-up pack" else f"copied ({why})")
        return had, "included", None
    value = secrets_store.make()
    secrets_store.put(path, secrets_store.key(site, "lead"), value)
    _audit(c, "hook.secret", f"{site}/lead", f"made ({why})")
    return value, "made", None


def _pack(c, form):
    """(site, zip bytes, made: {token_id, lead_secret_made}) or None after answering."""
    from .integrations_api import _origin
    from .kit import pack
    from .sites_api import tag
    site = _site(c, form)
    if site is None:
        c.no(404, "There is no such site in this organisation.")
        return None
    include = form.get("include_secrets") is True
    token, why = _given_token(c, site, form) if include else (None, None)
    if why:
        c.no(400, why)
        return None
    got = fields(c, site)
    try:
        installer(site, got)
    except ValueError as why_not:
        c.no(400, str(why_not))
        return None
    made = {"token_id": None, "lead_secret_made": False}
    secret, kind, refusal = _lead_secret(c, site, form, include)
    if refusal:
        c.no(400 if "not this site's" in refusal else 500, refusal)
        return None
    made["lead_secret_made"] = kind == "made"
    if include and token is None:
        token, made["token_id"] = _new_token(c, site, "set-up pack")
    origin = _origin(c)
    try:
        files = pack.files(site, ingest_url=got["url"],
                           lead_url=f"{origin}/traffic-hooks/{site}/lead",
                           dashboard=got["dashboard"], help_url=got["help"],
                           tag=tag(site, origin), installer=installer(site, got, token),
                           token=token, lead_secret=secret,
                           lead_note="included" if secret else kind)
    except ValueError as why_not:
        c.no(400, str(why_not))
        return None
    return site, pack.build(site, files), made


def pack_zip(c, form):
    got = _pack(c, form)
    if got is None:
        return None
    site, data, made = got
    keys = "yes" if form.get("include_secrets") is True else "no"
    _audit(c, "kit.pack", site, f"downloaded; keys {keys}")
    more = (("X-Skald-Token-Id", made["token_id"]),) if made["token_id"] else ()
    send_bytes(c.h, data, "application/zip", f"skald-setup-{site}.zip", more)
    return None


def pack_mail(c, form):
    import smtplib
    from . import mailer
    from .accounts import apitokens, limits
    from .conversions import secrets_store
    from .kit import pack
    site = _site(c, form)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    try:
        to = pack.clean_recipients(form.get("to"))
    except ValueError as why:
        return c.no(400, str(why))
    from .accounts.mails import configured
    if not configured(c.config):
        return c.no(409, "Mail is not set up on this server, so the pack cannot be mailed. "
                         "Download it instead, or set up mail in Settings > Mail.")
    key = f"kit-packmail:site:{site}"
    if limits.too_many(c.db, key, limit=PACKMAIL_PER_HOUR, minutes=60):
        return c.no(429, "Too many set-up mails for this site. Try again in an hour.")
    got = _pack(c, form)
    if got is None:
        return None
    site, data, made = got
    include = form.get("include_secrets") is True
    limits.note_failure(c.db, key)
    try:
        msg, cfg = pack.message(c.config, site, to, data, include, text(form, "note", 2000))
        mailer.send(msg, cfg)
    except (mailer.Refused, OSError, smtplib.SMTPException) as why:
        if made["token_id"]:                   # nothing reached anyone: take it back
            apitokens.revoke(c.db, c.org["id"], made["token_id"], c.uid)
        if made["lead_secret_made"]:
            path = secrets_store.path_for(c.config, _folder(c))
            secrets_store.delete(path, [secrets_store.key(site, "lead")])
        _audit(c, "kit.packmail", site, f"not sent ({type(why).__name__}); "
                                        f"{len(to)} recipient(s)")
        return c.no(502, "The mail server did not take the mail. Nothing was sent; try again, "
                         "or download the pack instead.")
    _audit(c, "kit.packmail", site, f"sent to {len(to)} recipient(s); keys "
                                    f"{'yes' if include else 'no'}")
    return c.ok(sent_to=to, token_id=made["token_id"],
                lead_secret_made=made["lead_secret_made"])


# ------------------------------------------------------------- AI agent

class Refused(ValueError):
    """make_agent_line's refusal: plain words, and the status the route answers."""

    def __init__(self, status: int, words: str):
        super().__init__(words)
        self.status = status


class _Core:
    """What the helpers above read from a request's context, without one."""

    def __init__(self, db, config, org, actor, live_dir, config_path, allowed):
        self.db, self.config, self.org, self.uid = db, config, org, actor
        self.live_dir, self.config_path, self.allowed = live_dir, config_path, allowed


def _own_origin(config, allowed) -> str:
    """integrations_api._origin without a request: hooks.public_url,
    access.base_url, else the address links point to."""
    from .config import setting
    for got in (setting(config, "hooks", "public_url"), setting(config, "access", "base_url")):
        if got:
            return str(got).rstrip("/")
    from .auth_api import base_url
    from .sites_api import _base
    return str(base_url(config, allowed) or _base(config, allowed)).rstrip("/")


def agent_link(c, form):
    from .integrations_api import _origin
    from .kit import agent_jobs
    site = _site(c, form)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    try:
        jobs = agent_jobs.default(form.get("leads") is not False) if form.get("jobs") is None \
            else agent_jobs.clean(form.get("jobs"))
        got = make_agent_line(c.db, c.config, c.org, site, jobs, c.uid, live_dir=c.live_dir,
                              config_path=c.config_path, allowed=c.allowed, origin=_origin(c))
    except Refused as why:
        return c.no(why.status, str(why))
    except ValueError as why:
        return c.no(400, str(why))
    return c.ok(**got)


def make_agent_line(db, config, org, site: str, jobs, actor, *, live_dir=None,
                    config_path=None, allowed=(), origin=None) -> dict:
    """The core of POST sites/agentlink, for the route and the MCP's
    setup_line: one AI agent line for `site` of `org` (a row, org["id"]) and
    the jobs asked, its tokens made as `actor` (a user id or "cli"), and the
    kit.agentlink audit row. `db`: accounts.sqlite, open (the caller closes
    it). `origin`: this install's address (the route: integrations_api._origin;
    None: the configured one). The route's answer without "ok". Refused (a
    ValueError, with .status 400 / 404 / 409 / 500) in plain words."""
    from .accounts import orgs, site_setup
    from .kit import agent, agent_jobs
    from .sites_api import tag
    c = _Core(db, config, org, actor, live_dir, config_path, allowed)
    if site not in orgs.sites_of_org(db, org["id"]):
        raise Refused(404, "There is no such site in this organisation.")
    try:
        jobs = agent_jobs.clean(list(jobs) if isinstance(jobs, (list, tuple)) else jobs)
    except ValueError as why:
        raise Refused(400, str(why)) from None
    if "logs" in jobs and not ingest.enabled(config):
        raise Refused(409, "The log endpoint is switched off on this server "
                           "(ingest.enabled in the server's config).")
    got = fields(c, site)
    if "logs" in jobs:
        try:
            installer(site, got)               # it can be built here, before a token is made
        except ValueError as why:
            raise Refused(400, str(why)) from None
    leads = "lead" in jobs
    secret, kind, refusal = _lead_secret(c, site, {}, leads, "AI agent set-up")
    if refusal:
        raise Refused(500, refusal)
    origin = str(origin).rstrip("/") if origin else _own_origin(config, allowed)
    got.update(lead_url=f"{origin}/traffic-hooks/{site}/lead", tag=tag(site, origin),
               hooks_url=f"{origin}/traffic-hooks/{site}/", mcp_url=_mcp_url(c))
    token, tid = _new_token(c, site, "AI agent set-up") if "logs" in jobs else (None, None)
    mcp, mcp_tid = _mcp_token(c, site) if "mcp" in jobs else (None, None)
    found = (site_setup.get(db, site) or {}).get("found")
    code, expires, ended = agent.make(_folder(c), site, token, tid, got, lead_secret=secret,
                                      lead_note="included" if secret else kind, leads=leads,
                                      found=found, replace=True, jobs=jobs, mcp_token=mcp,
                                      mcp_token_id=mcp_tid, facts=_facts(c, site, jobs))
    lid = agent.link_id(code)
    older, failed = _ended(c, site, ended, "a new line replaced it")
    _audit(c, "kit.agentlink", site, f"token {tid or 'none'}; link {lid}; jobs {','.join(jobs)}; "
                                     f"lead secret {kind if leads else 'not asked'}; "
                                     + (f"MCP token {mcp_tid}; " if mcp_tid else "")
                                     + f"keys once, for {agent.link.HOURS} hours; {older} older "
                                     "line(s) cancelled")
    base = got["base"]
    llms = f"{base}{agent.link.PREFIX}llms.txt"
    return dict(line=agent_jobs.line(site, llms, code, jobs), llms_url=llms,
                steps_url=f"{base}{agent.link.PREFIX}{code}/steps",
                expires_at=agent.link.stamp(expires), token_id=tid, link_id=lid,
                cancelled=older, jobs=jobs, **({"mcp_token_id": mcp_tid} if mcp_tid else {}),
                **({"not_revoked": failed} if failed else {}))


def _mcp_url(c) -> str:
    """Skald's MCP address: the dashboard's own (connections_api.extras)."""
    from .auth_api import base_url
    from .connections_api import send_base
    return f"{str(base_url(c.config, c.allowed) or send_base(c)).rstrip('/')}/traffic-mcp"


def _mcp_token(c, site: str) -> tuple[str, str]:
    """A read-only MCP token for this one site, as the MCP dialog makes it
    (scope mcp only: no visitor addresses, nothing it can change)."""
    from .accounts import apitokens
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    token = apitokens.create(c.db, c.org["id"], f"AI assistant (MCP): {site}, {day} (AI agent)",
                             sites=[site], scopes=("mcp",), actor=c.uid)
    return token, token.split("_", 2)[1]


def _facts(c, site: str, jobs) -> dict:
    """What Skald has now, for the steps' "Check first": the hook secrets
    set (lead), MCP on (mcp), the privacy and asset settings. Nothing secret;
    a fact that cannot be read is left out."""
    from . import settings_store
    from .conversions import TOOLS, hooks, secrets_store
    from .mcp.http import enabled as mcp_on
    conf = hooks.site_configs(c.config, c.config_path).get(site) or c.config
    out: dict = {}
    if "lead" in jobs:
        states = {}
        for tool in TOOLS:
            try:
                value, where = secrets_store.find(conf, _folder(c), site, tool)
            except secrets_store.Exposed:
                continue
            states[tool] = "env" if where.startswith("env") else ("set" if value else "none")
        out["hooks"] = states
    if "mcp" in jobs:
        out["mcp_on"] = mcp_on(c.config)
    if "privacy" in jobs or "assets" in jobs:
        got = settings_store.explain(conf, site, c.db)
        ips, days = got.get("privacy.keep_ips") or {}, got.get("privacy.keep_days") or {}
        out.update(keep_ips=ips.get("value"), keep_days=days.get("value"),
                   keep_source=ips.get("source"),
                   asset_prefixes=list((got.get("site.asset_prefixes") or {}).get("value") or []))
    return out


NOT_REVOKED = "Skald tries again in the daily run, or revoke it in Settings > Connections"


def revoke_unused(db, folder, org_of, actor, done) -> tuple[list, list]:
    """Revoke each (link_id, token_id) of `done`, then mark in the store only
    those whose revoke succeeded (a token already gone counts). `org_of(tid)`:
    the org to revoke it in. (revoked, [(link_id, token_id, why it failed)])."""
    from .accounts import apitokens
    from .kit import agent
    revoked, failed = [], []
    for one, tid in done:
        try:
            apitokens.revoke(db, org_of(tid), tid, actor)
        except ValueError:                     # the token is gone already: nothing to do
            pass
        except (sqlite3.Error, OSError) as why:
            failed.append((one, tid, type(why).__name__))
            continue
        revoked.append((one, tid))
    if revoked:
        agent.mark_revoked(folder, revoked)
    return revoked, failed


def _ended(c, site: str, ended, why: str) -> tuple[int, list[str]]:
    """Revoke every token of ended agent codes that was never handed out
    (agent.make's `ended`, agent.cancel's answer as (link_id, token_id,
    "cancelled"): one row per token), one audit row per cancelled code, and
    one per code with a token whose revoke failed. (how many codes were
    cancelled, the token ids not revoked)."""
    _, failed = revoke_unused(c.db, _folder(c), lambda _tid: c.org["id"], c.uid,
                              [(one, unused) for one, unused, _ in ended if unused])
    bad = {tid: err for _, tid, err in failed}
    lines: dict = {}                           # link id -> (how, its rows), in order
    for one, unused, how in ended:
        lines.setdefault(one, (how, []))[1].append(unused)
    cancelled = 0
    for one, (how, rows) in lines.items():
        words = "; ".join(_token_words(unused, bad) for unused in rows)
        if how == "cancelled":
            cancelled += 1
            _audit(c, "kit.agentcancel", site, f"link {one}; {why}; {words}")
        elif any(unused in bad for unused in rows):  # an expired line's: token.revoke when it went
            _audit(c, "kit.agenttoken", site, f"link {one}; {how}; {words}")
    return cancelled, list(bad)


def _token_words(unused, bad: dict) -> str:
    if unused in bad:
        return f"its unused token {unused} could not be revoked ({bad[unused]}); {NOT_REVOKED}"
    if unused:
        return f"its unused token {unused} revoked"
    if unused == "":
        return "it made no token"
    return "its keys were taken, so its token stays (revoke it in Settings > Connections)"


def _sweep(c, site: str) -> list[str]:
    """Revoke the unused tokens of the site's ended codes still to revoke;
    the token ids that failed."""
    from .kit import agent
    return _ended(c, site, [(one, tid, "expired") for one, tid in
                            agent.unrevoked(_folder(c), site)], "found ended")[1]


def agent_cancel(c, form):
    from .kit import agent
    site = _site(c, form)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    lid = text(form, "link_id", 40).strip().lower()
    if not agent.LINK_ID.match(lid):
        return c.no(400, "link_id is the 16 hex characters sites/agentlink answered.")
    was = agent.status(_folder(c), site, lid)["state"]
    if was == "unknown":
        return c.no(404, "There is no such line for this site (it may have run out a day ago).")
    if was != "cancelled":
        failed = _ended(c, site, [(one, unused, "cancelled") for one, unused in
                                  agent.cancel(_folder(c), site, lid)], "cancelled")[1]
    else:                                      # again: a revoke that failed is tried again
        failed = _sweep(c, site)
    return c.ok(state="cancelled", **({"not_revoked": failed} if failed else {}))


def agent_status(c, form):
    from .kit import agent
    site = _site(c, form)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    lid = text(form, "link_id", 40).strip().lower()
    if not agent.LINK_ID.match(lid):
        return c.no(400, "link_id is the 16 hex characters sites/agentlink answered.")
    got = agent.status(_folder(c), site, lid)
    if got["state"] in ("expired", "cancelled"):   # found ended: its unused token goes now
        _sweep(c, site)
    return c.ok(**got)


def daily(ctx) -> int:
    """run-daily's step for each site: revoke the unused tokens of the
    site's expired or cancelled agent codes still to revoke, and tidy the
    store (an expired code's seals wiped, old entries dropped). Never stops
    the run: a failure is one line on stderr, and the next run tries again."""
    from .accounts import db as base
    from .kit import agent
    folder = Path(ctx.db_path).parent
    try:
        todo = agent.unrevoked(folder, ctx.site)
        accounts = base.path_for(ctx.config, folder)
        if todo and accounts is not None and Path(accounts).is_file():
            db = base.connect(accounts)
            try:
                def org_of(tid):
                    row = db.execute("SELECT org_id FROM tokens WHERE id = ?", (tid,)).fetchone()
                    if row is None:
                        raise ValueError("gone")
                    return row[0]
                revoked, failed = revoke_unused(db, folder, org_of, "run-daily", todo)
            finally:
                db.close()
            if revoked:
                ctx.out(f"kit tokens: {len(revoked)} unused token(s) of ended AI agent "
                        "line(s) revoked")
            for one, tid, why in failed:
                ctx.err(f"kit tokens: link {one}: token {tid} could not be revoked "
                        f"({why}); tried again tomorrow")
        agent.mark_revoked(folder, [])         # tidy: an expired code's seals, old entries
    except Exception as why:                   # noqa: BLE001 - never stops a run
        ctx.err(f"kit tokens: {type(why).__name__}: {why}")
    return 0
