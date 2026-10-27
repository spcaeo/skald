"""The MCP tools for setting a site up (2.39.0): setup_left and setup_line.

setup_left reads: the "Set up <site>" checklist's lines that are not done,
worked out by setup_items.py from the same answers the page reads (the
doctor's lines, each hook's state, the settings), each with the AI agent's
job when an agent can do it and the address of its Set up dialog. Any token
that may read the site may call it.

setup_line is the one MCP tool that makes something: a set-up line for an AI
agent, made exactly as POST sites/agentlink makes it
(kit_api.make_agent_line). It needs a token with the `setup` scope for that
one site (accounts/apitokens.py: made by an owner or admin, exactly one
site, with mcp). The setup scope reads nothing; `read` is not needed. Each
line made writes an audit row (mcp.setup_line: the token's id, the jobs, the
line's id), never the code.
"""
from __future__ import annotations

from .data import SITE, Refused
from .tools import SITE_ARG, schema, tool

JOBS_ARG = {"type": "array", "minItems": 1, "maxItems": 8,
            "items": {"type": "string", "enum": ["logs", "script", "lead", "rsc", "assets",
                                                 "privacy", "search", "connect-tools"]},
            "description": "The jobs the line carries, as setup_left names them: logs, script, "
                           "lead, rsc, assets, privacy, search, connect-tools (the user's own "
                           "tools, such as Google Analytics). At least one."}
STATE_WORDS = {"todo": "to do", "wait": "waiting", "unknown": "not checked"}


def _known(ctx, site: str) -> bool:
    """A site of this install: its dashboard folder, or its config (a site
    just added from the dashboard has no folder before its first run)."""
    if ctx.out is not None and (ctx.out / site / "data").is_dir():
        return True
    from ..conversions import hooks
    return site in hooks.site_configs(ctx.config, ctx.config_path)


def _site(ctx, given) -> str:
    if given in (None, ""):
        return ctx.site(None)
    if not isinstance(given, str) or not SITE.match(given):
        raise Refused(f"{given!r} is not a site name; list_sites gives the names.")
    ok, why, _ = ctx.check(given)
    if not ok:
        raise Refused(f"You may not read {given}: {why or 'not allowed'}.")
    if not _known(ctx, given):
        raise Refused(f"There is no site {given} here; list_sites gives the names.")
    return given


def _base(ctx) -> str:
    """The dashboard's address for links (never the request's Host header)."""
    from ..auth_api import base_url
    return str(base_url(ctx.config, ctx.allowed) or "").rstrip("/")


def checklist(base: str, site: str) -> str:
    """Settings › To do: the site's open set-up lines."""
    from ..files import slug
    return f"{base}/traffic/{slug(site)}/#settings/todo"


def dialog(base: str, site: str, act: str) -> str:
    """The address of a Set up dialog: To do with setup=<act>."""
    return f"{checklist(base, site)}?setup={act}"


# ---------------------------------------------------------------- setup_left

@tool("setup_left", "What is left to set up",
      "The site's set-up lines that are not done (the same lines as Settings › "
      "To do): logs arriving, visits counted as people, Next.js "
      "pages, countries, the script tag, a lead hook, a mail recipient, the privacy choice, "
      "Search Console, and each of the user's own tools (Google Analytics...). "
      "Each open line has its state, one plain sentence, the address of its Set up dialog, "
      "and `job` when an AI agent can do it (logs, script, lead, rsc, assets, privacy, "
      "search, connect-tools; countries and mail are done by a person). Pass the jobs to setup_line to get "
      "one line an AI agent follows. When the user says \"Set up Skald for this site\", "
      "start here.",
      schema({"site": SITE_ARG}))
def setup_left(ctx, args):
    from .. import setup_items
    site = _site(ctx, args.get("site"))
    app = None
    if ctx.out is not None and (ctx.out / site / "data").is_dir():
        app = ctx.load(site, None, "app", required=False)
    got = setup_items.answers(ctx.config, site, ctx.live_dir, ctx.config_path,
                              base=ctx.origin or "")
    lines = setup_items.items(app, **got)
    base = _base(ctx)
    left = []
    for i in lines:
        if i["state"] == "done":
            continue
        left.append({"id": i["id"], "title": i["title"], "state": i["state"],
                     "optional": bool(i.get("optional")), "says": i["says"],
                     "job": setup_items.job_of(i),
                     "dialog": dialog(base, site, i["act"]) if i.get("act") else None})
    must = [i for i in lines if not i.get("optional")]
    todo = [i for i in must if i["state"] != "done"]
    jobs = [j for j in setup_items.JOBS if any(x["job"] == j for x in left)]
    data = {"site": site, "done": setup_items.done(lines), "left": left,
            "needed_left": len(todo), "needed": len(must), "jobs": jobs,
            "checklist": checklist(base, site)}
    if not left:
        return f"{site}: every set-up line is done. Nothing is left.", data
    out = [f"{site}: {len(todo)} of {len(must)} needed set-up lines left"
           + (f", and {len(left) - len(todo)} optional" if len(left) > len(todo) else "") + "."]
    for i in left:
        who = f" AI agent job: {i['job']}." if i["job"] else (
            " A person does this one." if i["dialog"] else "")
        out.append(f"- {i['title']}{' (optional)' if i['optional'] else ''}: "
                   f"{STATE_WORDS.get(i['state'], i['state'])}. {i['says']}{who}"
                   + (f" Dialog: {i['dialog']}" if i["dialog"] else ""))
    if jobs:
        out.append(f"One line for an AI agent can do: {', '.join(jobs)} (setup_line, with a "
                   "token that has the setup scope).")
    return "\n".join(out), data


# ---------------------------------------------------------------- setup_line

def _jobs(given) -> list[str]:
    from ..setup_items import JOBS
    if not isinstance(given, list) or not given:
        raise Refused("jobs is a list of at least one job: " + ", ".join(JOBS) + ".")
    bad = [j for j in given if not isinstance(j, str) or j not in JOBS]
    if bad:
        raise Refused(f"Not a job an AI agent can do: {', '.join(map(str, bad))}. "
                      f"A job is one of: {', '.join(JOBS)}.")
    return [j for j in JOBS if j in given]             # the table's order, each once


def _maker():
    from .. import kit_api
    return getattr(kit_api, "make_agent_line", None)


@tool("setup_line", "Make a set-up line for an AI agent",
      "Makes the one line an AI agent follows to set up the given jobs on the site "
      "(\"finish setting up Skald for <site> (...) - read <llms.txt> and use code <code>\"), "
      "exactly as the dashboard's \"Your AI agent\" choice makes it: works once, for 24 hours, "
      "and ends the site's older lines whose keys were not taken (never another site's). "
      "Needs a token with the setup scope for this one site (made by an owner or admin); "
      "without `site`, the one site the token is for. If you work in the site's own code or "
      "server, follow the line yourself at once. The agent fetches its keys "
      "with curl or Wget into a file, never in a chat; it checks first and changes only what "
      "is missing, and asks before any server change. Written to the audit log.",
      schema({"site": {**SITE_ARG, "description": "The site's name, e.g. example.com: the one "
                                                  "site the setup token is for (left out: "
                                                  "that site)."},
              "jobs": JOBS_ARG}, required=("jobs",)), read_only=False)
def setup_line(ctx, args):
    site = args.get("site")
    if site in (None, "") and ctx.setup is not None:
        site = ctx.site(None)                        # the one site this token reads
    if not isinstance(site, str) or not SITE.match(site):
        raise Refused(f"{site!r} is not a site name; list_sites gives the names.")
    jobs = _jobs(args.get("jobs"))
    if ctx.setup is None:
        raise Refused("Making a set-up line needs a token with the setup scope, over the "
                      "MCP endpoint (POST /traffic-mcp). This connection has no token.")
    ok, why, entry = ctx.setup(site)
    if not ok or not entry:
        raise Refused(f"Making a set-up line for {site} needs a token with the setup scope "
                      f"for that site: {why or 'not allowed'}.")
    if entry.get("sites") != [site]:
        raise Refused("A token that makes set-up lines is for exactly one site.")
    maker = _maker()
    if maker is None:
        raise Refused("This Skald cannot make a set-up line over MCP yet. Make it on the "
                      "dashboard: Settings › To do, Finish set-up, My AI agent.")
    from ..accounts import auditlog
    from ..accounts import db as base
    from ..accounts.orgs import org_of_site
    from ..sites_api import read_only
    db = base.connect(base.path_for(ctx.config, ctx.live_dir))
    try:
        org = org_of_site(db, site)
        if org is None or org["id"] != entry["org_id"]:
            raise Refused(f"{site} is not a site of this token's organisation.")
        frozen = read_only(db, ctx.config, org["id"])
        if frozen:
            raise Refused(frozen)
        actor = entry.get("created_by") or "mcp"
        try:
            got = maker(db, ctx.config, org, site, jobs, actor, live_dir=ctx.live_dir,
                        config_path=ctx.config_path, allowed=ctx.allowed, origin=ctx.origin)
        except ValueError as no:
            raise Refused(str(no)) from None
        auditlog.record(db, org["id"], actor, "mcp.setup_line", site,
                        f"token {entry['id']}; jobs {','.join(jobs)}; "
                        f"link {got.get('link_id') or '?'}")
    finally:
        db.close()
    keep = ("line", "llms_url", "steps_url", "expires_at", "link_id", "cancelled",
            "not_revoked")
    data = {"site": site, "jobs": list(got.get("jobs") or jobs),
            **{k: got[k] for k in keep if k in got}}
    older = got.get("cancelled") or 0
    text = [f"A set-up line for {site} ({', '.join(data['jobs'])}):",
            str(got.get("line") or ""),
            f"It works once, until {got.get('expires_at') or 'it runs out (24 hours)'}."
            + (f" It ended {older} older line{'s' if older != 1 else ''} whose keys were not "
               "taken." if older else ""),
            "If you are the AI agent working in this site's own code or server, follow the "
            "line yourself now: fetch its llms.txt and steps with curl in a shell, as they say. "
            "Else give it, as it is, to the agent that works on the site.",
            "The agent reads the steps, checks first and changes only what is missing, asks "
            "before any server change, and takes its keys with curl or Wget into a file, never "
            "into a chat. Call setup_left afterwards: a line ticks itself once Skald sees it "
            "working."]
    if got.get("not_revoked"):
        text.append("An older line's token could not be revoked; Skald tries again in the "
                    "daily run, or revoke it in Settings › AI assistants › Tokens & links.")
    return "\n".join(text), data
