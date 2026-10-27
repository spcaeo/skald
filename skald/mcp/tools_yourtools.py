"""The MCP tool for the figures from the user's own tools: your_tools.

It reads what the dashboard's "From your tools" card reads (yourtools/api.view,
for members: no key, no robot address, no error text), for any token that may
read the site. Every figure is labelled with the tool it came from: these are
the tool's own counts, never Skald's, and never added to Skald's figures. A
figure the tool did not give is null, never 0; a tool whose recheck failed
(yourtools/recount.py) shows none.
"""
from __future__ import annotations

from .tools import SITE_ARG, schema, tool


def _number(v) -> str:
    if v is None:
        return "not given"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


@tool("your_tools", "Figures from the user's own tools (Google Analytics...)",
      "The figures Skald keeps from the site's own marketing tools, connected with the "
      "user's own keys (Google Analytics 4: sessions, users, engaged sessions, key events, "
      "top landing pages and sources, over the tool's own last 28 days; Vercel Web Analytics: "
      "visitors, page views, top pages, referrers, countries; Calendly: bookings, upcoming, "
      "canceled, no-shows; Resend: contacts, segments, email delivery states). Each tool with its "
      "state (answering, last try failed, stopped answering), when it last answered, and what "
      "the tool said about its own answer (sampled, thresholded). These are the tool's counts, "
      "never Skald's: never add them to Skald's figures or present them as Skald's.",
      schema({"site": SITE_ARG}))
def your_tools(ctx, args):
    from ..yourtools.api import view
    site = ctx.site(args.get("site"))
    folder = ctx.history_path.parent if ctx.history_path is not None else ctx.live_dir
    got = view(ctx.config_for(site), folder, site, admin=False)
    if not got["tools"]:
        return (f"{site}: no tool of the user's own is connected (Settings > Leads & tools > "
                "Connect a tool)."), got
    out = [f"{site}: figures from the user's own tools. They are each tool's own counts, "
           "not Skald's (Skald's own: Counted from: your server log); never add them to "
           "Skald's figures."]
    for t in got["tools"]:
        line = f"- {t['name']}: {t['words']}, last answer {t['ago']}. {t['counted_from']}."
        if t.get("withheld"):
            out.append(line + " " + t["withheld"])
            continue
        period = t.get("period") or {}
        if period.get("start"):
            line += f" Its period: {period['start']} to {period['end']}"
            line += f" ({period['note']})." if period.get("note") else "."
        out.append(line)
        for name, rep in t["reports"].items():
            figs = rep["figures"]
            totals = [f for f in figs if f["dim"] is None]
            rows = [f for f in figs if f["dim"] is not None]
            if totals:
                out.append(f"  {name}: " + ", ".join(f"{f['label']} {_number(f['value'])}"
                                                     for f in totals))
            seen: dict = {}
            for f in rows:
                seen.setdefault(f["dim"], []).append(f"{f['label']} {_number(f['value'])}")
            for dim, vals in list(seen.items())[:10]:
                out.append(f"    {dim}: {', '.join(vals)}")
            if rep.get("flags"):
                out.append(f"  {name}, as the tool said: {'; '.join(rep['flags'])}.")
    return "\n".join(out), got
