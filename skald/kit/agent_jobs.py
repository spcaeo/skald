"""The jobs one AI agent line can carry (docs/plans/2026-10-26-agent-everywhere.md),
and what agent.py hands out for them: the line's words, the keys file and the
steps.

  id       what the agent does on the site                keys it gets
  logs     connects the server's log (cases A-D)          SKALD_INGEST_TOKEN
  script   puts the script tag in the shared <head>       none
  lead     the site's own forms (the lead file), and      SKALD_LEAD_SECRET; a tool's
           the booking, form or payment tools'            secret through POST
           webhooks                                        <code>/hooksecret (agent_hooks.py)
  rsc      Next.js's log field in nginx or Apache         none
  assets   finds where the pages load their own files     none
  privacy  reads the privacy notice, recommends a keep    none
  search   Google Search Console: the robot's address,     none; a new Search Console key
           and the one click the user makes                through POST <code>/searchkey
                                                           (agent_search.py), only when
                                                           Skald has none and an install
                                                           admin made the line
  mcp      connects the user's assistant to Skald's MCP   SKALD_MCP_TOKEN (mcp scope,
                                                          this site, no addresses)

2.41: a to-do line (Overview > Insights' Fix this, kit/agent_todos.py) carries TODO_JOBS
instead: todo-lost, todo-errors, todo-markdown, todo-sitemap, todo-leave, one per kind of
to-do it holds; its keys file holds SKALD_SITE and SKALD_REPORT_KEY only, and its steps
are agent_todos.steps' (todo-head.md, keys.md, todo-rows.md, todo-where.md,
jobs/todo-<kind>.md, todo-finish.md). The two families never mix in one line.

SKALD_REPORT_KEY is in every keys file. A line with no `jobs` (Add a site, and
every caller and stored entry from before 2.39) has DEFAULT, without "lead"
when leads were not asked: its words, keys file and keys are today's.

The steps are kit/agent/head.md, keys.md (step 1), jobs/<id>.md for each job
in JOBS' order (steps 2...), and finish.md (the report, the last step), each
filled. `<!-- if a|b -->...<!-- else -->...<!-- end -->` keeps a part only
when the line has one of the jobs named (`if not a`: when it has none of them).
"""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from . import link

HERE = Path(__file__).resolve().parent / "agent"
JOBS = ("logs", "script", "lead", "rsc", "assets", "privacy", "search", "mcp")
DEFAULT = ("logs", "script", "lead")
STATES = ("done", "already", "skipped", "left")     # the report's `jobs` values
# The line's words (after "finish setting up Skald for <site>").
TITLES = {"logs": "connect the logs", "script": "add the script tag",
          "lead": "send leads and tool webhooks", "rsc": "add the Next.js log field",
          "assets": "find the page assets", "privacy": "check the privacy settings",
          "search": "connect Google Search Console", "mcp": "connect the AI assistant (MCP)"}
MOST = 20                                            # ids looked at in one request
FOUND_MOST = 120                      # a site check value's length in the steps
COND = re.compile(r"<!-- if (not )?([a-z|-]+) -->\n(.*?)(?:<!-- else -->\n(.*?))?<!-- end -->\n",
                  re.S)
# 2.41: a to-do line's jobs (agent_todos.py), one per kind of Insights' to-dos it carries.
# Never mixed with the set-up jobs above in one line.
TODO_JOBS = ("todo-lost", "todo-errors", "todo-markdown", "todo-sitemap", "todo-leave")
# What the site check's recommended method means in the steps' cases.
WAYS = {"docker": "case A, the site's own server (the one-file installer)",
        "systemd": "case A, the site's own server (the one-file installer)",
        "cloudflare": "case B, Cloudflare (the Skald Worker)",
        "vercel": "case C, Vercel (a log drain)", "netlify": "case C, Netlify (a log drain)",
        "script": "case D, the script tag only"}
LEAD_WORDS = {
    "included": "The lead secret is `SKALD_LEAD_SECRET` in the keys file (step 1).",
    "env": ("The lead secret is kept in the Skald server's environment, so it is not in the "
            "keys file. Ask the user to get it from whoever runs their Skald."),
    "none": ("Leads were not included in this line, so the keys file has no lead secret. If "
             "the site makes leads, ask the user to make a new line with leads, or to make the "
             "secret in Skald (Settings > Leads & integrations > Lead)."),
}
TOOL_LABELS = {"lead": "Your site's server (lead)", "json": "Zapier, Make, n8n (json)",
               "calendly": "Calendly", "calcom": "Cal.com", "stripe": "Stripe",
               "typeform": "Typeform", "hubspot": "HubSpot"}
HOOK_WORDS = {"set": "Skald has its secret", "env": "its secret is kept in the Skald server's "
              "environment (ask whoever runs Skald; you cannot change it)",
              "none": "no secret yet"}
KEEP_WORDS = {"full": "kept in full", "short": "kept shortened", "off": "not kept"}


def default(leads: bool = True) -> list[str]:
    return list(DEFAULT) if leads else ["logs", "script"]


def clean(raw) -> list[str]:
    """The asked jobs in JOBS' order; ValueError in plain words."""
    if not isinstance(raw, list) or not all(isinstance(one, str) for one in raw):
        raise ValueError(f"jobs is a list of job ids: {', '.join(JOBS)}.")
    if not raw:
        raise ValueError(f"Name at least one job: {', '.join(JOBS)}.")
    if len(raw) > MOST:
        raise ValueError(f"At most {MOST} job ids.")
    bad = [one for one in raw if one not in JOBS]
    if bad:
        return _unknown(bad[0])
    return [job for job in JOBS if job in raw]


def _unknown(job: str):
    shown = "".join(ch for ch in job[:40] if ch.isprintable())
    raise ValueError(f'There is no job "{shown}". The jobs are: {", ".join(JOBS)}.')


def of(entry: dict | None) -> list[str]:
    """A stored line's jobs; an entry from before 2.39 has the default."""
    got = (entry or {}).get("jobs")
    if isinstance(got, list) and got and (all(one in JOBS for one in got)
                                          or all(one in TODO_JOBS for one in got)):
        return list(got)
    return default((entry or {}).get("leads", True) is not False)


def is_default(jobs) -> bool:
    return list(jobs) in (default(True), default(False))


def line(site: str, llms: str, code: str, jobs, hours: int = link.HOURS) -> str:
    """The one line to paste: today's words for the default jobs."""
    tail = f"read {llms} and use code {code} (works once, {hours} hours)"
    if is_default(jobs):
        return f"set up Skald for {site} — {tail}"
    return (f"finish setting up Skald for {site} ({', '.join(TITLES[j] for j in jobs)}) — "
            f"{tail}")


# ---------------------------------------------------------------- keys

def keys_file(entry: dict, keys: dict) -> str:
    """The env file: only the keys the jobs need, each value shell-quoted
    (sourced with `.`); the default jobs give today's file."""
    fields = entry.get("fields") or {}
    jobs = of(entry)
    values = [("SKALD_SITE", entry["site"])]
    if "logs" in jobs:
        values += [("SKALD_INGEST_URL", fields.get("url") or ""),
                   ("SKALD_INGEST_TOKEN", keys.get("token") or "")]
    if "logs" in jobs or "lead" in jobs:
        values.append(("SKALD_LEAD_URL", fields.get("lead_url") or ""))
    if keys.get("lead"):
        values.append(("SKALD_LEAD_SECRET", keys["lead"]))
    if keys.get("mcp"):
        values += [("SKALD_MCP_URL", fields.get("mcp_url") or ""), ("SKALD_MCP_TOKEN", keys["mcp"])]
    if keys.get("report_key"):
        values.append(("SKALD_REPORT_KEY", keys["report_key"]))
    lines = [f"# Skald keys for {entry['site']}. Keep this file 0600 and out of any "
             "repository;", "# never print it or paste it in a chat."]
    return "\n".join(lines + [f"{k}={shlex.quote(str(v))}" for k, v in values]) + "\n"


def _key_names(entry: dict, jobs: list[str]) -> str:
    names = ["SKALD_SITE"]
    if "logs" in jobs:
        names += ["SKALD_INGEST_URL", "SKALD_INGEST_TOKEN"]
    if "logs" in jobs or "lead" in jobs:
        names.append("SKALD_LEAD_URL")
    if "lead" in jobs and entry.get("lead_note") == "included":
        names.append("SKALD_LEAD_SECRET")
    if "mcp" in jobs:
        names += ["SKALD_MCP_URL", "SKALD_MCP_TOKEN"]
    return ", ".join(f"`{n}`" for n in names) + " and `SKALD_REPORT_KEY` (for the report)"


# --------------------------------------------------------------- steps

def fill(text: str, values: dict) -> str:
    """The template filled; ValueError when a placeholder is left."""
    from . import LEFT, fill as put
    text = put(text, values)
    left = LEFT.findall(text)
    if left:
        raise ValueError(f"a placeholder is left: {left[0]}")
    return text


def choose(text: str, jobs) -> str:
    """Keep each `<!-- if ... -->` part that fits the line's jobs."""
    def one(m):
        named = set(m.group(2).split("|"))
        want = bool(named & set(jobs)) != bool(m.group(1))
        return m.group(3) if want else (m.group(4) or "")
    return COND.sub(one, text)


def _plain(value) -> str:
    """A site check value as the steps show it: one line, capped, and never
    a placeholder (`__` split) or the end of a code span."""
    got = " ".join(str(value).split())[:FOUND_MOST].replace("`", "'")
    while "__" in got:
        got = got.replace("__", "_ _")
    return got


# Values the site's own answers set (its Server header...): shown as code.
FROM_SITE = ("server", "server_detail", "platform", "framework")


def found_lines(found: dict | None) -> str:
    if not found:
        return "- Nothing: the check did not run. Find it out as the steps say."
    lines = []
    for label, key in (("The site answers", "reachable"), ("HTTPS", "https"),
                       ("Web server", "server"), ("Server details", "server_detail"),
                       ("Hosting", "platform"), ("Framework", "framework"),
                       ("Its addresses", "hosts"),
                       ("Its own files are served from", "asset_prefixes"),
                       ("Why that way", "reason"), ("Note", "assets_note")):
        value = found.get(key)
        if value in (None, "", [], "unknown"):
            continue
        if isinstance(value, bool):
            value = "yes" if value else "no"
        elif isinstance(value, list):
            value = ", ".join(f"`{_plain(v)}`" for v in value[:10])
        elif key in FROM_SITE:
            value = f"`{_plain(value)}`"
        else:
            value = _plain(value)
        lines.append(f"- {label}: {value}")
    return "\n".join(lines) or "- Nothing certain. Find it out as the steps say."


def _hook_states(facts: dict) -> str:
    hooks = facts.get("hooks") if isinstance(facts.get("hooks"), dict) else {}
    lines = [f"  - {label} (`{tool}`): {HOOK_WORDS.get(hooks.get(tool), 'not known')}"
             for tool, label in TOOL_LABELS.items() if tool != "lead"]
    return "\n".join(lines)


def _privacy_now(facts: dict) -> str:
    mode, days = facts.get("keep_ips"), facts.get("keep_days")
    if mode not in KEEP_WORDS:
        return "not known (ask the user to look at Settings > Privacy & retention > People)"
    words = f"IP addresses {KEEP_WORDS[mode]}"
    if mode != "off" and isinstance(days, int) and not isinstance(days, bool):
        words += f" for {days} days"
    if facts.get("keep_source") in ("default", "upgrade"):
        words += " (Skald's default: nobody chose it yet)"
    return words


def _assets_now(facts: dict) -> str:
    got = facts.get("asset_prefixes")
    if isinstance(got, list) and got:
        return ", ".join(f"`{_plain(p)}`" for p in got[:10])
    return "not known"


def _mcp_state(facts: dict) -> str:
    if facts.get("mcp_on") is False:
        return ("\nMCP is switched off on this Skald server, so the address answers \"not found\" "
                "for now. Tell the user: whoever runs their Skald turns it on (`mcp.enabled`; "
                "Docker: `SKALD_MCP=true`). You can connect it now; it answers once it is on.\n")
    return ""


def _example(jobs: list[str], site: str) -> str:
    """The report command's JSON: the fields the line's jobs fill."""
    out: dict = {"jobs": {job: "done" for job in jobs}}
    if "logs" in jobs:
        out.update(hosting="own server", server="nginx", log_path="/var/log/nginx/access.log")
    if "logs" in jobs or "assets" in jobs:
        out.update(framework="Next.js", asset_paths=["/_next/static/"])
    if "script" in jobs:
        out["script_tag"] = "app/layout.tsx"
    if "lead" in jobs:
        out["leads"] = [{"tool": "contact form", "file": "app/api/contact/route.ts"}]
        out["tools"] = [{"tool": "calendly", "hook": "set"}, {"tool": "stripe", "hook": "left"}]
    if "logs" in jobs or "privacy" in jobs:
        out["privacy"] = {"keep_ips": True, "days": 30, "notice_url": f"https://{site}/privacy"}
    if "logs" in jobs or "rsc" in jobs:
        out["nextjs_log_field"] = True
    if "search" in jobs:
        out["search"] = {"google_property": f"sc-domain:{site}", "robot_added": True}
    out["changed_files"] = ["app/layout.tsx"] if "script" in jobs else []
    out["left_for_user"] = (["Set Settings > Privacy & retention > People to 30 days"]
                            if "logs" in jobs or "privacy" in jobs else []) + \
        (["Search Console: add the robot address as a Restricted user"]
         if "search" in jobs else [])
    out["notes"] = "Anything else, in one or two plain sentences."
    return json.dumps({k: v for k, v in out.items() if v != []})


def _search_now(facts: dict) -> str:
    """What Skald had for the search job, for its Check first."""
    google = facts.get("google_key") if isinstance(facts.get("google_key"), dict) else {}
    prop, bing = facts.get("search_property"), facts.get("bing_site")
    lines = [f"- Google Search Console: connected to `{_plain(prop)}`" if prop
             else "- Google Search Console: not connected"]
    if google.get("set") and google.get("client_email"):
        lines.append("- Skald's Google key: set; its robot address is "
                     f"`{_plain(google['client_email'])}`")
    elif google.get("set"):
        lines.append("- Skald's Google key: set, but it cannot be read (ask whoever runs Skald)")
    else:
        lines.append("- Skald's Google key: none yet")
    lines.append(f"- Bing: connected to `{_plain(bing)}`" if bing else "- Bing: not connected")
    lines.append("- Skald's Bing key: " + ("set" if facts.get("bing_key") else "none yet"))
    return "\n".join(lines)


def _search_robot(facts: dict, site: str, env_dir: str, env_file: str, url: str) -> str:
    """Step 2 of the search job: the robot address Skald has, or how to make
    one (only an install admin's line may), or who to ask."""
    google = facts.get("google_key") if isinstance(facts.get("google_key"), dict) else {}
    if google.get("set") and google.get("client_email"):
        return (f"Skald's robot address is `{_plain(google['client_email'])}`. It is the same "
                "for every site of this Skald: nothing to make. Go on to 3.")
    if not facts.get("may_upload_key"):
        return ("Skald has no Search Console key yet, and only whoever runs the user's Skald may "
                "set one (it serves every site). Put this in `left_for_user`: \"Ask whoever runs "
                "Skald to upload a Google service-account key in Settings > Integrations > "
                "Search; its robot address then shows there.\" Then do 3 once it is there.")
    key = f"{env_dir}/{site}.gsc-key.json"
    return f"""Skald has no Search Console key yet. You can make one with `gcloud`, if it is installed
and signed in (`gcloud config list`). Ask the user first, and wait for a yes:

"May I make a Google Cloud service account for Skald in your project <project id>, with one
key? It can only read Search Console figures, and Skald keeps the key on its own server."

Without `gcloud`, or without a yes, put this in `left_for_user` instead: "Make a service
account and a JSON key in Google Cloud (IAM > Service accounts), turn on the Search Console
API, and upload the key in Skald, Settings > Leads & integrations > Search Console & Bing." Then go on to 3.

With a yes, put the project's id in place of `<project id>`:

    P='<project id>'
    gcloud services enable searchconsole.googleapis.com --project "$P"
    gcloud iam service-accounts create skald-search --display-name 'Skald (reads Search Console)' --project "$P"
    umask 077 && mkdir -p {env_dir} && gcloud iam service-accounts keys create {key} --iam-account "skald-search@$P.iam.gserviceaccount.com"

Never `cat` the key file. Send it to Skald from stdin (bash or zsh), then remove it:

    curl -sS -w '\\nHTTP %{{http_code}}\\n' -X POST -H @<(grep '^SKALD_REPORT_KEY=' {env_file} | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /') -H 'Content-Type: application/json' --data-binary @- '{url}' < {key}

- **HTTP 200:** Skald answers `{{"ok": true, "client_email": "..."}}`: that is the robot
  address. Remove the file: `rm -f {key}`.
- **HTTP 409:** Skald has a key already: its answer names the robot address. Remove the file,
  and, with the user's yes, the key you made (`gcloud iam service-accounts delete`).
- **Anything else:** show Skald's words (they hold no secret) and remove the file.

If Google refuses to make a key (an organisation policy such as
`iam.disableServiceAccountKeyCreation`), tell the user and put the upload in `left_for_user`."""


def _read(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def steps(entry: dict, code: str, base: str) -> str:
    """The line's steps in Markdown: addresses and words, never a key."""
    if entry.get("todos"):                           # a to-do line (2.41)
        from . import agent_todos
        return agent_todos.steps(entry, code, base)
    fields = entry.get("fields") or {}
    facts = entry.get("facts") if isinstance(entry.get("facts"), dict) else {}
    jobs = of(entry)
    site = entry["site"]
    root = (fields.get("base") or base or "").rstrip("/")
    here = f"{root}{link.PREFIX}{code}"
    found = entry.get("found") or None
    way = WAYS.get((found or {}).get("recommended_method") or "")
    note = LEAD_WORDS.get(entry.get("lead_note") or "none", LEAD_WORDS["none"])
    numbers = {job: str(n) for n, job in enumerate(jobs, 2)}
    parts = [_read("head.md"), _read("keys.md").replace("__N__", "1")]
    parts += [_read(f"jobs/{job}.md").replace("__N__", numbers[job]) for job in jobs]
    parts.append(_read("finish.md").replace("__N__", str(len(jobs) + 2)))
    text = choose("\n".join(parts), jobs)
    dashboard = fields.get("dashboard") or ""
    hooks = fields.get("hooks_url") or (fields.get("lead_url") or "").rpartition("/")[0] + "/"
    env_dir, env_file = "$HOME/.config/skald", f"$HOME/.config/skald/{site}.env"
    values = {
        "SEARCH_NOW": _search_now(facts) if "search" in jobs else "",
        "SEARCH_ROBOT": _search_robot(facts, site, env_dir, env_file, f"{here}/searchkey")
        if "search" in jobs else "",
        "SITE_DASHED": site.replace(".", "-"),
        "SITE": site, "EXPIRES": link.stamp(entry["expires_at"]).replace("T", " ")[:16],
        "JOB_LIST": ", ".join(TITLES[job] for job in jobs),
        "DASHBOARD": dashboard, "HELP": fields.get("help") or "",
        "HELP_HOOKS": f"{dashboard}#help?part=demo-bookings" if dashboard else "the Skald help",
        "INGEST_URL": fields.get("url") or "", "LEAD_URL": fields.get("lead_url") or "",
        "TAG": fields.get("tag") or "", "MCP_URL": fields.get("mcp_url") or "",
        "FOUND": found_lines(found),
        "WAY": way or "not settled by the check: find it out as the logs step says.",
        "ENV_FILE": env_file, "ENV_DIR": env_dir,
        "KEYS_URL": f"{here}/keys", "INSTALL_URL": f"{here}/install.sh",
        "LEADS_URL": f"{here}/leads/", "REPORT_URL": f"{here}/report",
        "HOOKSECRET_URL": f"{here}/hooksecret", "HOOKS": hooks, "LEADS": note,
        "KEY_NAMES": _key_names(entry, jobs), "HOOK_STATES": _hook_states(facts),
        "PRIVACY_NOW": _privacy_now(facts), "ASSETS_NOW": _assets_now(facts),
        "MCP_STATE": _mcp_state(facts), "REPORT_EXAMPLE": _example(jobs, site),
        "STEP_FINISH": str(len(jobs) + 2),
        **{f"STEP_{job.upper()}": numbers.get(job, "") for job in JOBS}}
    return fill(text, values)
