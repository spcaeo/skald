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
  POST sites/agentlink {site, leads: bool = true}
       -> {ok, line, llms_url, steps_url, expires_at, token_id, link_id,
          cancelled}: the
          one line for an AI agent (kit/agent.py). A new sending token ("AI
          agent set-up") and, with leads, the site's lead secret (the one it
          has, else one made now), both sealed under a one-time code for 24
          hours. Never answers the token or the secret. 409 when the log
          endpoint is off. link_id: the first 16 hex of the code's sha256.
          One live line per site: in the same lock as the new code, the site's
          older codes whose keys were not taken are cancelled and their unused
          tokens revoked (`cancelled`: how many), and expired ones whose keys
          were never taken give up their token too.
  POST sites/agentstatus {site, link_id}
       -> {ok, state: waiting | opened | keys_taken | expired | cancelled |
          unknown, opened_at, keys_at, reported_at, report, cancelled_at,
          expires_at}: that site's agent code only.
  POST sites/agentcancel {site, link_id}
       -> {ok, state: "cancelled"}: the code ends at once (its keys can no
          longer be taken; every route answers as expired); its token is
          revoked when the keys were never taken. 404 for an unknown code.

Every route writes the audit log (who, site, how many recipients, keys or
not); no token, secret, code or address is ever logged.
"""
from __future__ import annotations

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

def agent_link(c, form):
    from .accounts import site_setup
    from .integrations_api import _origin
    from .kit import agent
    from .sites_api import tag
    site = _site(c, form)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    if not ingest.enabled(c.config):
        return c.no(409, "The log endpoint is switched off on this server "
                         "(ingest.enabled in the server's config).")
    leads = form.get("leads") is not False
    got = fields(c, site)
    try:
        installer(site, got)                   # it can be built here, before a token is made
    except ValueError as why:
        return c.no(400, str(why))
    secret, kind, refusal = _lead_secret(c, site, {}, leads, "AI agent set-up")
    if refusal:
        return c.no(500, refusal)
    origin = _origin(c)
    got.update(lead_url=f"{origin}/traffic-hooks/{site}/lead", tag=tag(site, origin))
    token, tid = _new_token(c, site, "AI agent set-up")
    found = (site_setup.get(c.db, site) or {}).get("found")
    code, expires, ended = agent.make(_folder(c), site, token, tid, got, lead_secret=secret,
                                      lead_note="included" if secret else kind, leads=leads,
                                      found=found, replace=True)
    lid = agent.link_id(code)
    older = _ended(c, site, ended, "a new line replaced it")
    _audit(c, "kit.agentlink", site, f"token {tid}; link {lid}; lead secret "
                                     f"{kind if leads else 'not asked'}; keys once, for "
                                     f"{agent.link.HOURS} hours; {older} older line(s) "
                                     "cancelled")
    base = got["base"]
    llms = f"{base}{agent.link.PREFIX}llms.txt"
    return c.ok(line=f"set up Skald for {site} — read {llms} and use code {code} "
                     f"(works once, {agent.link.HOURS} hours)",
                llms_url=llms, steps_url=f"{base}{agent.link.PREFIX}{code}/steps",
                expires_at=agent.link.stamp(expires), token_id=tid, link_id=lid,
                cancelled=older)


def _ended(c, site: str, ended, why: str) -> int:
    """Revoke the tokens of ended agent codes that were never handed out, one
    audit row per cancelled code (agent.make's `ended`, agent.cancel's answer
    as (link_id, token_id, "cancelled")); how many were cancelled."""
    from .accounts import apitokens
    cancelled = 0
    for one, unused, how in ended:
        if unused:
            try:
                apitokens.revoke(c.db, c.org["id"], unused, c.uid)
            except ValueError:                 # the token is gone already
                pass
        if how != "cancelled":                 # an expired line's unused token: token.revoke
            continue
        cancelled += 1
        _audit(c, "kit.agentcancel", site, f"link {one}; {why}; " + (
            f"its unused token {unused} revoked" if unused else
            "its keys were taken, so its token stays (revoke it in Settings > Connections)"))
    return cancelled


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
        _ended(c, site, [(one, unused, "cancelled")
                         for one, unused in agent.cancel(_folder(c), site, lid)], "cancelled")
    return c.ok(state="cancelled")


def agent_status(c, form):
    from .kit import agent
    site = _site(c, form)
    if site is None:
        return c.no(404, "There is no such site in this organisation.")
    lid = text(form, "link_id", 40).strip().lower()
    if not agent.LINK_ID.match(lid):
        return c.no(400, "link_id is the 16 hex characters sites/agentlink answered.")
    return c.ok(**agent.status(_folder(c), site, lid))
