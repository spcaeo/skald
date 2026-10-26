# Skald MCP server

Skald speaks the Model Context Protocol (MCP), so an AI agent - Claude Code,
Claude Desktop, ChatGPT, or any MCP client - can ask about your traffic in
plain words. "How did last week compare with the week before?" "Which pages
did ChatGPT fetch?" "Was any day withheld?"

It is **read-only**, with one exception (2.39.0): `setup_line` makes a set-up
line for an AI agent, and only with a token that has the `setup` scope (below,
"Setting a site up"). It reads the same data files the dashboard reads
(DATA-CONTRACT.md). It never counts anything again and never invents a
figure. An agent cannot get a figure the dashboard would not show.
What it can and cannot do with leads (no tool writes one):
[LEADS-REFERENCE.md](LEADS-REFERENCE.md).

Code: `skald/mcp/`. Protocol version `2025-06-18` (clients asking for
`2025-03-26` or `2024-11-05` are answered with `2025-06-18`).

## Honesty in every answer

- Each tool answers with a short plain-English text and the numbers as
  structured data.
- Visits are called "visits (an upper bound on people)". A browser's name can
  be faked, so a visit count is at most the number of people, never a count
  of them. Requests are never presented as people.
- Ranges are summed from whole, verified days only. Withheld, partial and
  missing days are named by date and left out, never counted as zero. A
  figure that was not recorded is null, never 0.
- A change against an earlier period is stated only when both periods are
  whole.

## Tools

Dates are `YYYY-MM-DD` in the site's own time zone. With no dates, a tool
uses the last 7 whole days (yesterday and the 6 days before it). `site` may
be left out when the token reads only one site. `view` is a part of a site
(a slug such as `us-english`).

| Tool | Arguments | What it answers |
| --- | --- | --- |
| `list_sites` | | the sites you may read, their views and the days held |
| `overview` | site, from, to, view | visits, pages read, AI fetches, search fetches, 404s, server errors, the change against the period before |
| `breakdown` | site, dimension, from, to, view, limit | visits by `country`, `source`, `campaign`, `landing`, `device`, `browser`, `hour`, `os` or `referrer`; the rows add up to the visits |
| `top_pages` | site, from, to, view, limit | the pages people read most, with AI fetches of each |
| `ai_activity` | site, from, to, view | assistants and crawlers by name, the pages they fetched, visits that followed an assistant's link |
| `leads` | site, from, to | leads from the website's database by type, and by first-touch source (aggregates only) |
| `funnel` | site, name or steps, source, view | a saved funnel, or your own path steps, over the journeys of the last 7 days and today |
| `compare` | site, a_from, a_to, b_from, b_to, filters, view | two ranges side by side (up to 400 days), the same answer as the dashboard's compare |
| `page_story` | site, path | one page since it was published: first Googlebot, AI crawler, person, lead, and its days |
| `live_today` | site, view | today so far from the 2-minute snapshot (partial; never compared) |
| `data_quality` | site, from, to | per day: verify, audit, log gaps, unreadable lines; files that failed to build |
| `site_health` | site | open alerts, heartbeat uptime, errors today, late scheduled runs, page-speed status |
| `conversions` | site, from, to, action, by | every action (demo, contact, signup, paid, ...) by stage: started, completed, abandoned, the completion rate (over 10 or more starts), cancelled, no-show, won, lost; completed ones by source (last touch), or `by` first_source, landing, country, campaign, device or tool; the leads (forms sent and demos booked) and demos booked, and the leads by the same breakdown (2.5.0); withheld and not-recorded days named. From conversions.json; no name or email; rows marked test are never counted |
| `what_changed` | site, from, to, view, limit | Overview > Summary's "What changed: is it working?": visits by source and by landing page, now against the same number of days just before, each Now, Before and the change (a gap of 3 or fewer is "about the same"), with the biggest rise and drop. Stated only when every day of both periods is whole and verified; otherwise the days are named and nothing is compared. From overview.json and breakdowns.json, the sums the `breakdown` tool makes |
| `todos` | site, id, limit | Overview > Insights' to-do list (todos.json): each to-do's title, proof, what to do, how Skald checks it, its tab, and its state: to do, marked done (with the re-check on the whole days after the mark, fixed or not yet) or not now; `id` gives one to-do's rows. To-dos the second count disagreed with are named as withheld. Marking stays on the dashboard |
| `lost_pages` | site, part, server, limit | Site > Not found (lost_pages.json): `part` `lost` (default) the old page addresses still asked for, by people, search engines and AI, with the closest live page (the same page, the same topic, a loose match, no good match) and the nginx or Apache line (`server`) to copy; `markdown` the Markdown copies AI asked for; `fixed` the addresses marked fixed and what came since. Withheld: null, never 0 |
| `page_changes` | site, path, id | the page changes marked on Traffic > Pages (page_changes.json): day, kind, note, status (waiting, too early, ready, and the day the verdict comes), and per measure (visits, leads, search, AI visits, AI reads, left at once) the before and after sides with the change and the verdict (up, down, no clear change, too few, not enough days, not recorded). `path` matches with or without the closing `/` |
| `ai_readiness` | site, path, need, limit | without `path`: AI & bots > Assistants' "Pages AI can't read well" (ai_ready.json `attention`), worst first, `need` `copy`, `404`, `errors`, `robots` or `slow`, and the crawlers robots.txt keeps out of the whole site; with `path`: that page's AI readiness: robots.txt for each of the 9 main AI crawlers with the deciding rule (`robots_match.decide`), what AI got back in the last 30 days (`ai_ready.needs`), the Markdown copy, the sitemap entry and lastmod, and the last AI read from page_trends.json. Not known stays not known |
| `changed_pages` | site, limit | Summary's "New and updated pages: are they getting found?" (page_trends.json `changed`): the pages changed in the last 30 days, the visits and search visits since, the first search visit, whether Google's verified crawler fetched them, and the note when sitemap dates look like build times |
| `setup_left` | site | (2.39.0) the site's set-up checklist lines that are not done, the same lines as Settings › Connections' "Set up <site>" (worked out by `setup_items.py`, held to `js/setup-items.js` by a test): each with its state (`todo`, `wait`, `unknown`), its plain sentence, `job` when an AI agent can do it (`logs`, `script`, `lead`, `rsc`, `assets`, `privacy`; `countries` and `mail` are a person's) and `dialog`, the address of its Set up dialog (`.../traffic/<site>/#settings/api?setup=<act>`). Also `done`, `needed_left` of `needed`, and `jobs`: the open jobs, ready for `setup_line`. Any token that may read the site. A site just added (no dashboard folder yet) is answered too |
| `setup_line` | site, jobs | (2.39.0) **setup scope only; the one tool that writes.** Makes the line for an AI agent for the given jobs exactly as POST `sites/agentlink` does (`kit_api.make_agent_line`): works once, for 24 hours, and ends the site's older lines whose keys were not taken. Answers `line`, `llms_url`, `steps_url`, `expires_at`, `link_id`, `cancelled`, `jobs`. Jobs are `setup_left`'s six, at least one, given in any order (answered in the table's order, each once); `countries`, `mail` or an unknown id is refused. The sending token it makes is made as the setup token's maker. One audit row `mcp.setup_line` (the token's id, the jobs, the line's id), never the code. Over stdio (no token) it is refused |
| `find_person` | site, q | **read_private only.** One IP address, email, visitor ID or lead id: every visit kept with the address, the last 6 hours of requests, the leads (spam, duplicates and test too), every conversion (test, cancelled and removed too), linked. The same lookup as the page's search (`people/lookup.py`); each call is written to the audit log by its kind and a hash, never the value. A listing, not a figure |

A site you may not read, a bad date or a missing file comes back as a tool
error (`isError: true`) in plain words, not as a protocol error.

**Addresses.** Two data files hold visitors' addresses: `requests` and
`ai_activity`. Only a token with the `read_private` scope reads them (today
that means `ai_activity`'s list of today's assistant events, with
addresses), and only such a token may call `find_person` (addresses, emails
and names). Without it, no answer carries an address.

## Setting a site up (2.39.0)

`setup_left` and `setup_line` let an agent finish a site's set-up the way the
dashboard's checklist does. The token for it has two scopes: `mcp` (to reach
the endpoint, and read the site for `setup_left`) and `setup` (to make a line).

- **The `setup` scope** (accounts/apitokens.py, docs/ACCOUNTS.md): only an owner or
  admin of the organisation may make it (or the server, `skald token create
  NAME --scope mcp --scope setup --site <site>`), only for exactly one site,
  and only together with `mcp`. A viewer, a second site or no `mcp` is
  refused. It reads nothing by itself (it is not `read`). In the page:
  Settings › Connections, **Make a token by hand**, tick the one site,
  **AI assistant (MCP)** and **Set-up lines (AI agent)** ("can make set-up
  lines for an AI agent"). Like every token made in the page, it stops at
  once when its maker is disabled, removed or no longer an owner or admin.
- **The line** is the same line the dashboard's "Your AI agent" choice
  makes, with the same safety: the agent fetches its keys once with curl or
  Wget into a file (never in a chat, a commit or a log), checks first and
  changes only what is missing, and asks the user before any server or
  web-server change. Skald's own settings change only by the user's Apply.

**Example: "finish setting up kiwi.example".** The agent calls:

1. `setup_left {"site": "kiwi.example"}` on a site just added: "kiwi.example: 5 of 5
   needed set-up lines left, and 2 optional." Logs arriving (to do, job `logs`),
   Visits count as people and Countries shown (waiting for the first visitor),
   Script tag events and Lead hook tested (optional, jobs `script` and `lead`),
   Mail recipient confirmed (to do, a person's: its dialog's address), Privacy
   settings chosen (to do, job `privacy`); `jobs: ["logs", "script", "lead",
   "privacy"]`.
2. `setup_line {"site": "kiwi.example", "jobs": ["logs", "script", "lead",
   "privacy"]}`: answers the line, `finish setting up Skald for kiwi.example
   (...) — read https://stats.example.com/traffic-kit/llms.txt and use code
   <code> (works once, 24 hours)`.
3. It follows the line: reads llms.txt and the steps, takes the keys with curl
   into a file, connects the log, puts the tag in the shared `<head>`, wires the
   form backend, reads the privacy notice, and reports back. The privacy
   recommendation waits for the owner's Apply.
4. `setup_left` again: the lines Skald sees working have ticked themselves.
   The mail line stays for the owner (the dialog's address is in the answer).

## Resources and prompt

| URI | What |
| --- | --- |
| `skald://docs/api` | docs/API.md: the data files and the read-only API |
| `skald://docs/counting` | CLASSIFICATION.md: the five groups and what the figures cannot know |
| `skald://sites/<site>/overview` | the site's latest overview.json |
| `skald://sites/<site>/llms.txt` | a suggested `/llms.txt` for the site, from its latest llms_txt.json (`skald llms-txt`) |

Prompt `weekly_report(site)`: asks the model for a short weekly report
written with the tools, under the rules above.

## Switching it on (server)

It is off until the config says so, and it needs accounts:

```yaml
access:
  mode: sessions        # organisation tokens in accounts.sqlite
mcp:
  enabled: true
```

**Docker** (a config made from the `SKALD_*` environment): add `SKALD_MCP=true` to the
container's environment (`-e`, `--env-file` or Compose) and start the container again
(2.26). The image's nginx already passes `/traffic-mcp` to the helper; before 2.26 a
Docker install without its own mounted config had no way to say `mcp.enabled`, so the
path answered 404 `{"error": "MCP is not switched on here"}`. A mounted config
(`/etc/skald/config.yml`) keeps using its own `mcp:` key. A front proxy in front
of the container must pass `POST /traffic-mcp` too (DEPLOY.md has the nginx location).
Check from the server: `curl -s -X POST http://127.0.0.1:8080/traffic-mcp -d '{}'` answers
401 (on, no token) instead of 404 (off).

Make a token with the `mcp` scope in Settings > Connections (called API & tokens before):
the card "Connect an AI assistant (MCP)" makes one for the current site, shows the Claude Code
and Claude Desktop set-up, and tests it with `initialize` and `tools/list`; "Make a token by
hand" takes several sites (or on the server: `skald token create NAME --scope mcp`). Add `read_private` only
if the agent must see addresses, and `setup` only for an agent that should make set-up lines
(one site, above). The token is shown once; keep it where you
keep other secrets, never in a repository.

The endpoint is `POST https://<your host>/traffic-mcp` on the refresh helper,
behind nginx:

- `Authorization: Bearer skald_<id>_<secret>` on every request (401 with
  `WWW-Authenticate: Bearer` without a valid token that has the `mcp` scope);
  each tool call checks the token again for the site it reads.
- JSON-RPC in the body (at most 64 KiB), one JSON answer back
  (`Content-Type: application/json`); no event stream, so `GET` is 405.
- A browser's `Origin` header must be the dashboard's own origin (the helper's
  `--origin`), else 403. Agents send none.
- `MCP-Protocol-Version` is accepted for the three versions above.

OAuth is not offered yet: clients connect with the bearer token.

## Connecting

Replace `stats.example.com` with your dashboard's host and the token with
your own.

**Claude Code**

```sh
claude mcp add --transport http skald https://stats.example.com/traffic-mcp \
  --header "Authorization: Bearer skald_<id>_<secret>"
```

**Claude Desktop** - either through a remote connector to the same URL with
the token, or locally over stdio by running the command on the server
through SSH, in `claude_desktop_config.json`:

```json
{"mcpServers": {"skald": {
  "command": "ssh",
  "args": ["stats.example.com", "python3", "/opt/skald/bin/skald",
           "--config", "/etc/skald/config.yml", "mcp", "--site", "example.com"]}}}
```

**ChatGPT / OpenAI** - add a remote MCP server (a connector, or the Responses
API's `mcp` tool) with the server URL `https://stats.example.com/traffic-mcp`
and the header `Authorization: Bearer skald_<id>_<secret>`. OAuth sign-in is
not offered yet, so use a client that lets you set the header.

**Any MCP client** - Streamable HTTP at the URL above with the bearer
header, or stdio with the command below.

## Local use (stdio)

```sh
skald --config /etc/skald/config.yml mcp [--site example.com] [--private]
```

Newline-delimited JSON-RPC on stdin and stdout; logs on stderr only. No token:
whoever can run this on the server can already read the data files. `--site`
limits it to one site. Addresses are read only with `--private`.

## Checked by

`tests/test_mcp_protocol.py` (JSON-RPC, lifecycle, errors, batches),
`tests/test_mcp_tools.py` (every tool against a dashboard folder made by the
real commands, the withheld day named, honesty words, site isolation,
addresses), `tests/test_mcp_transport.py` (the HTTP endpoint with real
organisation tokens, and stdio in a subprocess), `tests/test_mcp_conversions.py`,
`tests/test_mcp_withheld.py`, `tests/test_mcp_support.py` and `tests/test_mcp_insights.py`
(the six 2.35 tools: compared only over whole periods, withheld and not-recorded figures
named and null, a path with or without its slash, robots.txt not known without a copy, and
every one refusing a site the caller may not read), `tests/test_setup_items.py` (the
server's checklist lines against `js/setup-items.js` in node, on the same answers) and
`tests/test_mcp_setup.py` (`setup_left` on a real helper equals the page's own lines, a
finished site has none left; `setup_line`'s scope, site and job refusals, its audit row,
and who may make a `setup` token).
