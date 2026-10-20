"""The MCP tool that looks a person up (2.4.0): find_person.

Only for a caller with the read_private scope (ctx.private): it answers
with addresses, emails and names. It calls the same lookup the page's
search calls (people/lookup.person), on the files opened read-only, and
writes the same audit line (people/api.record): never the value searched,
only its kind and a hash prefix. A listing, not a figure.
"""
from __future__ import annotations

from .data import Refused
from .tools import SITE_ARG, schema, tool


@tool("find_person", "Find a person: visits, leads and conversions",
      "Everything Skald keeps about one person, linked: every visit kept with the address "
      "(time, source, referrer, landing page, pages in order, country, device), the last 6 "
      "hours of requests, the leads in the site's lead database (spam, duplicates and test "
      "too) and every conversion (test, cancelled and removed ones too). Give one IP "
      "address, email, visitor ID (skv_...) or lead id. On a site that keeps addresses "
      "shortened (the last part removed), a full address finds the visits of its "
      "shortened form, which can be several people. Needs the read_private scope; "
      "each search is written to the audit log.",
      schema({"site": SITE_ARG,
              "q": {"type": "string", "minLength": 1, "maxLength": 320,
                    "description": "An IP address, an email, a visitor ID or a lead's id "
                                   "or reference."}}, required=("q",)))
def find_person(ctx, args):
    from ..people import api, lookup
    site = ctx.site(args.get("site"))
    if not ctx.private(site):
        raise Refused("Looking a person up needs a token with the read_private scope: the "
                      "answer holds addresses, emails and names.")
    config = ctx.config_for(site)
    folder = ctx.history_path.parent if ctx.history_path is not None else None
    try:
        got = lookup.person(config, folder, site, args.get("q", ""), ctx.live_dir)
    except lookup.Invalid as why:
        raise Refused(str(why)) from None
    api.record(ctx.config, ctx.live_dir, site, None, "mcp", got)
    q = got["query"]
    kept = got["kept"]
    lines = [f"{site}: {q['kind']} {q['value']}.",
             f"Visits kept with the address: {len(got['visits'])}"
             + ("" if kept["keep_ips"] else " (this site keeps no addresses: only the last "
                                              "6 hours of requests show them)") + ".",
             *([f"This site keeps addresses shortened (the last part removed): "
                f"{q['value']} is kept as {q['short']}, and a shortened address can be "
                f"several people. Visits linked by it are a weaker link."]
               if q.get("short") else []),
             f"Requests in the last 6 hours: {len(got['requests'])}.",
             f"Leads: {len(got['leads'])}; conversions: {len(got['conversions'])}; "
             f"removed conversions: {len(got['removed'])}.",
             f"Visits that sent a form within 2 minutes of a lead (matched by time, not "
             f"certain): {len(got['candidates'])}."]
    if got["withheld"]:
        lines.append("Days withheld (their figures did not reconcile): "
                     + ", ".join(sorted(got["withheld"])) + ".")
    keys = got["keys"]
    lines.append("Linked: " + "; ".join(f"{k} {', '.join(v[:10])}" for k, v in keys.items()
                                        if v) + ".")
    return "\n".join(lines), got
