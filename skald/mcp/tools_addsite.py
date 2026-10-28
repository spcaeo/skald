"""The MCP tools that add a site and watch its set-up (2.44): add_site,
site_progress, check_site and send_invites.

The owner (2026-10-27): an AI agent (Claude Code, ChatGPT, Cursor) may "Add a
site", depending on the plan. So "add shop.example.com to Skald, invite these
two people as viewers, and tell me when data arrives" works over MCP:

  add_site       site_add.add, the very code POST sites/add runs: the plan's
                 sites and members, a read-only organisation, the log endpoint,
                 the host, at most setup_people.PER_SITE people, saas's pending
                 verification. Then kit_api.make_agent_line, as setup_line makes
                 it, for the set-up jobs. Always into the token's own
                 organisation: a new organisation is made in the dashboard only.
  site_progress  setup_live.live_now, the answer of POST sites/live
  check_site     setup_live.check_now, POST sites/check's Check now; its
                 CHECK_PER_HOUR is counted per token
  send_invites   setup_live.send_now, POST sites/sendinvites: mails the people now

add_site needs a token with the add_sites scope (accounts/apitokens.py: for the
whole organisation, made by an owner or admin who sees every site, with mcp;
checked at every use). The other three take that token for any site of its
organisation, or a setup token for its one site. A read-only organisation is
refused, as the dashboard refuses every change. The token's maker is the actor.
add_site and send_invites write an audit row (mcp.add_site, mcp.send_invites:
the token's id, the site, counts), never a code, a token or an address.
"""
from __future__ import annotations

from .data import SITE, Refused
from .tools import schema, tool
from .tools_setup import JOBS_ARG, _base, _jobs

NEED = ("a token with the add_sites scope (made by an owner or admin in Settings › AI & API, "
        "with AI assistant (MCP))")
PEOPLE_ARG = {"type": "array", "maxItems": 20,
              "items": {"type": "object", "additionalProperties": False,
                        "properties": {
                            "email": {"type": "string", "maxLength": 300,
                                      "description": "Their email address."},
                            "user": {"type": "integer",
                                     "description": "Or a member's id in this organisation."},
                            "role": {"type": "string", "enum": ["viewer", "admin"],
                                     "description": "viewer (default) or admin."},
                            "sees": {"type": "string", "enum": ["site", "all"],
                                     "description": "site: this site only (default); all: "
                                                    "every site of the organisation."}}},
              "description": "Who will use the site, at most 20. Each gets an invite mail once "
                             "the first data arrives (send_invites sends them sooner). Each "
                             "new person counts against the plan's members."}
STEP_WORDS = {True: "done", False: "not yet"}
STATE_WORDS = {"done": "set up and done", "receiving": "receiving data",
               "waiting": "waiting for its first data"}


def _site_arg(given) -> str:
    if not isinstance(given, str) or not SITE.match(given):
        raise Refused(f"{given!r} is not a site name, e.g. shop.example.com.")
    return given


def _adder(ctx) -> dict:
    """The token's entry when it has the add_sites scope, else Refused."""
    if ctx.adder is None:
        raise Refused(f"Adding a site needs {NEED}, over the MCP endpoint (POST /traffic-mcp). "
                      "This connection has no token.")
    ok, why, entry = ctx.adder()
    if not ok or not entry:
        raise Refused(f"Adding a site needs {NEED}: {why or 'not allowed'}.")
    return entry


def _db(ctx):
    from ..accounts import db as base
    return base.connect(base.path_for(ctx.config, ctx.live_dir))


def _actor(entry) -> int | str:
    who = str(entry.get("created_by") or "cli")
    return int(who) if who.isdigit() else who


def _core(ctx, db, org, actor):
    from ..kit_api import _Core
    return _Core(db, ctx.config, org, actor, ctx.live_dir, ctx.config_path, ctx.allowed)


def _watched(ctx, db, site: str) -> tuple[dict, dict]:
    """(the site's organisation, the token's entry) for a token with add_sites for
    that organisation, or setup for that one site. The same words whether or
    not the site exists: nothing leaks."""
    from ..accounts.orgs import org_of_site
    from ..sites_api import read_only
    org = org_of_site(db, site)
    entry = None
    if ctx.adder is not None and org is not None:
        ok, _, got = ctx.adder()
        if ok and got and got["org_id"] == org["id"]:
            entry = got
    if entry is None and ctx.setup is not None and org is not None:
        ok, _, got = ctx.setup(site)
        if ok and got and got["org_id"] == org["id"]:
            entry = got
    if entry is None:
        raise Refused(f"Watching {site}'s set-up needs {NEED} for its organisation, or a token "
                      "with the setup scope for that one site.")
    frozen = read_only(db, ctx.config, org["id"])
    if frozen:
        raise Refused(frozen)
    return org, entry


# ------------------------------------------------------------------ add_site

@tool("add_site", "Add a site",
      "Adds a website to Skald, in this token's own organisation, exactly as the dashboard's "
      "Add a site does, within what the organisation's plan allows (its number of sites and "
      "members). Optionally names who will use it (an email, viewer or admin, this site only "
      "or every site): they get an invite mail once the first data arrives. Answers with the "
      "site's dashboard address, its state (on a hosted Skald the domain is verified first) and "
      "the one-time set-up line for an AI agent (the jobs: logs, script, lead by default), as "
      "setup_line makes it. A new organisation is never made here: that is done in the "
      "dashboard. Needs a token with the add_sites scope (made by an owner or admin). Then "
      "call site_progress to watch it and check_site when nothing comes. Written to the "
      "audit log.",
      schema({"host": {"type": "string", "maxLength": 200,
                       "description": "The site's host name, e.g. shop.example.com."},
              "timezone": {"type": "string", "maxLength": 64,
                           "description": "Its time zone, e.g. Europe/London (default: the "
                                          "server's)."},
              "people": PEOPLE_ARG,
              "jobs": {**JOBS_ARG, "description": "The set-up line's jobs (default: logs, "
                                                  "script, lead). " + JOBS_ARG["description"]}},
             required=("host",)), read_only=False)
def add_site(ctx, args):
    from .. import kit_api, site_add
    from ..accounts import auditlog, orgs, users
    from ..files import slug
    from ..kit.agent_jobs import DEFAULT
    entry = _adder(ctx)
    jobs = _jobs(args["jobs"]) if args.get("jobs") is not None else list(DEFAULT)
    actor = _actor(entry)
    db = _db(ctx)
    try:
        org = orgs.get_org(db, entry["org_id"])
        role = users.role_in(db, actor, org["id"]) if isinstance(actor, int) else "owner"
        form = {"host": args.get("host"), "timezone": args.get("timezone"),
                "people": args.get("people"), "token": False}
        try:
            got = site_add.add(db, ctx.config, org, actor, form, live_dir=ctx.live_dir,
                               config_path=ctx.config_path, allowed=ctx.allowed, out=ctx.out,
                               origin=ctx.origin or kit_api._own_origin(ctx.config, ctx.allowed),
                               role=role)
        except site_add.Refused as no:
            raise Refused(str(no)) from None
        site = got["site"]
        line, problem = {}, None
        try:
            line = kit_api.make_agent_line(db, ctx.config, org, site, jobs, actor,
                                           live_dir=ctx.live_dir, config_path=ctx.config_path,
                                           allowed=ctx.allowed, origin=ctx.origin)
        except ValueError as no:
            problem = str(no)
        verify = got.get("verify") or None
        auditlog.record(db, org["id"], actor, "mcp.add_site", site,
                        f"token {entry['id']}; {got['people']} people; jobs {','.join(jobs)}; "
                        f"link {line.get('link_id') or 'none'}; "
                        f"{'domain to verify' if verify and verify['state'] == 'pending' else 'open'}")
    finally:
        db.close()
    page = f"{_base(ctx)}/traffic/{slug(site)}/"
    pending = bool(verify) and verify.get("state") == "pending"
    data = {"site": site, "org": got["org"]["name"], "dashboard": page,
            "state": "pending" if pending else "waiting", "verify": verify,
            "people": got["people"], "jobs": list(line.get("jobs") or jobs),
            **{k: line[k] for k in ("line", "llms_url", "steps_url", "expires_at", "link_id")
               if k in line}}
    if problem:
        data["line_error"] = problem
    text = [f"Added {site} to {got['org']['name']}. Its page: {page}"]
    if pending:
        text.append(f"Nothing is collected until the domain is verified: add the DNS TXT record "
                    f"{verify['txt']} or the meta tag {verify['meta']} to the home page, then "
                    "press Verify in Settings › Sites.")
    if got["people"]:
        n = got["people"]
        text.append(f"{n} {'person gets an' if n == 1 else 'people get an'} invite mail once "
                    "the first data arrives (send_invites sends them now).")
    if problem:
        text.append(f"The set-up line could not be made: {problem} Make it in the dashboard: "
                    "Settings › To do, Finish set-up, My AI agent.")
    else:
        text += [f"The set-up line for an AI agent ({', '.join(data['jobs'])}):",
                 str(line.get("line") or ""),
                 f"It works once, until {line.get('expires_at') or 'it runs out (24 hours)'}.",
                 "If you are the AI agent working in this site's own code or server, follow the "
                 "line yourself now: fetch its llms.txt and steps with curl in a shell, as they "
                 "say. Else give it, as it is, to the agent that works on the site."]
    text.append(f"Then call site_progress for {site} to watch it; check_site says what is "
                "missing when nothing comes.")
    return "\n".join(text), data


# ------------------------------------------------------------- site_progress

LINK_ARG = {"type": "string", "maxLength": 40,
            "description": "The set-up line's link_id (add_site or setup_line gave it); left "
                           "out: the site's newest line."}


def _when(at) -> str:
    return f" ({str(at)[:16].replace('T', ' ')} UTC)" if at else ""


def live_words(live: dict) -> str:
    out = [f"{live['site']}: {STATE_WORDS.get(live['state'], live['state'])}."]
    for s in live["steps"]:
        more = ""
        if s["id"] == "data" and s["done"]:
            more = (f": {s.get('lines', 0):,} lines kept so far, {s.get('recent', 0):,} in the "
                    f"last 15 minutes")
        out.append(f"- {s['words']}{more}: {STEP_WORDS[bool(s['done'])]}{_when(s.get('at'))}.")
    if live.get("refused"):
        out.append(f"Skald refused what was sent{_when(live['refused'].get('at'))}: "
                   f"{live['refused']['words']}")
    return "\n".join(out)


@tool("site_progress", "Watch a site's set-up",
      "A site's set-up, step by step, as the dashboard's live set-up shows it: the agent opened "
      "its line, took its keys, the data road (Vercel or Netlify log drain, Cloudflare Worker, "
      "the shipper, the script tag), the first data with its counts, the domain verified, the "
      "set-up done, and the invites. State: waiting, receiving or done. Call it again to watch "
      "(every 30 seconds is plenty). Once data arrives Skald marks the set-up done and sends "
      "the invites, as it does by itself in its live run. Needs a token with the add_sites "
      "scope for the site's organisation, or the setup scope for the site.",
      schema({"site": {"type": "string", "description": "The site's name, e.g. "
                                                        "shop.example.com."},
              "link_id": LINK_ARG}, required=("site",)))
def site_progress(ctx, args):
    from .. import setup_live
    site = _site_arg(args.get("site"))
    db = _db(ctx)
    try:
        org, entry = _watched(ctx, db, site)
        live = setup_live.live_now(_core(ctx, db, org, _actor(entry)), site,
                                   str(args.get("link_id") or "").strip().lower())
    finally:
        db.close()
    return live_words(live), live


# ---------------------------------------------------------------- check_site

@tool("check_site", "Check now: what is missing",
      "The dashboard's Check now for a site: the same checks, at once, in plain words: "
      "verdict ok (receiving data), wait (nothing yet, and what to look at for the way the "
      "data comes) or bad (refused, not verified, the line expired), with what to fix. At most "
      "60 checks an hour per token. Needs a token with the add_sites scope for the site's "
      "organisation, or the setup scope for the site.",
      schema({"site": {"type": "string", "description": "The site's name, e.g. "
                                                        "shop.example.com."},
              "link_id": LINK_ARG}, required=("site",)))
def check_site(ctx, args):
    from .. import setup_live
    site = _site_arg(args.get("site"))
    db = _db(ctx)
    try:
        org, entry = _watched(ctx, db, site)
        got = setup_live.check_now(_core(ctx, db, org, _actor(entry)), site,
                                   f"setup-check:token:{entry['id']}",
                                   str(args.get("link_id") or "").strip().lower())
    finally:
        db.close()
    if got is None:
        raise Refused(f"Too many checks with this token ({setup_live.CHECK_PER_HOUR} an hour). "
                      "Try again in a few minutes.")
    c = got["check"]
    text = [f"{site}: {c['head']}", *(x for x in (c.get("says"),) if x)]
    if c.get("fix"):
        text.append(f"Fix: {c['fix']}")
    if c.get("tech"):
        text.append(c["tech"])
    return "\n".join(text), got


# -------------------------------------------------------------- send_invites

@tool("send_invites", "Send the invites now",
      "Sends the invites of the people named when the site was added now, before the first "
      "data, once: each new address gets an invite mail, a member of another organisation is "
      "added and told, and the person who made the token gets one mail. Without a call they "
      "go by themselves once the first data arrives. Needs a token with the add_sites scope "
      "for the site's organisation, or the setup scope for the site. Written to the audit log.",
      schema({"site": {"type": "string", "description": "The site's name, e.g. "
                                                        "shop.example.com."}},
             required=("site",)), read_only=False)
def send_invites(ctx, args):
    from .. import setup_live
    from ..accounts import auditlog
    site = _site_arg(args.get("site"))
    db = _db(ctx)
    try:
        org, entry = _watched(ctx, db, site)
        actor = _actor(entry)
        try:
            got = setup_live.send_now(_core(ctx, db, org, actor), site)
        except ValueError as no:
            raise Refused(str(no)) from None
        auditlog.record(db, org["id"], actor, "mcp.send_invites", site,
                        f"token {entry['id']}; " + ("already sent" if got.get("already") else
                                                    f"{got['sent']} invited, {got['added']} "
                                                    f"added, {got['skipped']} skipped, "
                                                    f"{got.get('handed', 0)} not mailed"))
    finally:
        db.close()
    words = got.get("words") or ""
    text = (f"The invites for {site} went already: {words}" if got.get("already")
            else f"Invites for {site}: {words}")
    return text, {"site": site, "invites": got}
