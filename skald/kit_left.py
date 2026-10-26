"""Lines for your sites (2.40, docs/plans/2026-10-26-agent-everywhere.md,
"Many sites, one line each"): what is left to set up on every site of the
organisation, for the dashboard's view that makes one separate line per site
(js/tabs/agent-many.js). sites_api.py routes it with its session, owner or
admin role checks:

  GET sites/agentleft
       -> {ok, sites: [{site, status, pending, done, jobs, left, line}],
          mcp: {url, on}}
          site     a site of the organisation, removed ones left out
          status   active or paused
          pending  its domain still waits to be verified (saas): nothing is
                   collected until it is, so its line can wait
          done     every needed checklist line is done
          jobs     the open lines an AI agent can do, as job ids in the
                   contract's order (setup_items.JOBS): what its line carries
          left     each open line {id, title, state, says, optional, job}
          line     the site's newest AI agent line (kit/agent.py latest):
                   {link_id, state, opened_at, keys_at, reported_at, jobs,
                   line_jobs, ...}, or null: the view watches it after a reload
                   (the line itself, with its code, is never answered again)
          mcp      Skald's MCP address and whether it is on, for the "two
                   lines" (an MCP token with the mcp and setup scopes, made by
                   tokens/create)

Each site's line is its own code (POST sites/agentlink, one per site): lines
for different sites never end each other, so ten sessions can set up ten
sites at once; one live line per site stays the rule. The lines are worked
out exactly as the MCP's setup_left does (setup_items.answers and items):
nothing is counted here. A site whose lines cannot be read says "unknown" on
those lines, never done.
"""
from __future__ import annotations

import json


def _app(c, site: str) -> dict | None:
    from .refresh_server import data_file
    path = data_file(getattr(c, "out", None), site, None, "app")
    if path is None:
        return None
    try:
        got = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and got.get("state") != "error" else None


def _left(c, site: str, origin: str) -> dict:
    from . import setup_items
    got = setup_items.answers(c.config, site, c.live_dir, c.config_path, base=origin,
                              accounts_db=c.db)
    lines = setup_items.items(_app(c, site), **got)
    left = [{"id": i["id"], "title": i["title"], "state": i["state"], "says": i["says"],
             "optional": bool(i.get("optional")), "job": setup_items.job_of(i)}
            for i in lines if i["state"] != "done"]
    jobs = [j for j in setup_items.JOBS if any(x["job"] == j for x in left)]
    return {"done": setup_items.done(lines), "jobs": jobs, "left": left}


def agent_left(c, form):
    from . import site_verify
    from .accounts import orgs, site_configs, site_state
    from .integrations_api import _origin
    from .kit import agent
    from .kit_api import _folder, _mcp_url
    from .mcp.http import enabled as mcp_on
    if c.role not in ("owner", "admin"):
        return c.no(403, "Only an admin can set up sites.", role=c.role)
    names = sorted(orgs.sites_of_org(c.db, c.org["id"]))
    rows = {r["name"]: r for r in site_configs.listing(c.db, c.org["id"])}
    states = site_state.every(c.db)
    origin = _origin(c)
    keep = []
    for name in names:
        row, st = rows.get(name), states.get(name) or {}
        if (row["removed_at"] if row else None) or st.get("removed_at"):
            continue
        keep.append((name, "paused" if st.get("paused_at") else "active"))
    lines = agent.latest(_folder(c), [name for name, _ in keep])
    out = []
    for name, status in keep:
        shown = site_verify.shown(c.db, name) or {}
        out.append({"site": name, "status": status, "pending": shown.get("state") == "pending",
                    **_left(c, name, origin), "line": lines.get(name)})
    return c.ok(sites=out, mcp={"url": _mcp_url(c), "on": bool(mcp_on(c.config))})
