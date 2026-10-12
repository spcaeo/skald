# Skald MCP server

Skald speaks the Model Context Protocol (MCP), so an AI agent - Claude Code,
Claude Desktop, ChatGPT, or any MCP client - can ask about your traffic in
plain words. "How did last week compare with the week before?" "Which pages
did ChatGPT fetch?" "Was any day withheld?"

It is **read-only**. It reads the same data files the dashboard reads
(DATA-CONTRACT.md). It never counts anything again and never invents a
figure. An agent cannot get a figure the dashboard would not show.

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
| `conversions` | site, from, to, action | every action (demo, contact, signup, paid, ...) by stage: started, completed, abandoned, the completion rate (over 10 or more starts), cancelled, no-show, won, lost; completed ones by source; withheld and not-recorded days named. From conversions.json; anonymous |

A site you may not read, a bad date or a missing file comes back as a tool
error (`isError: true`) in plain words, not as a protocol error.

**Addresses.** Two data files hold visitors' addresses: `requests` and
`ai_activity`. Only a token with the `read_private` scope reads them (today
that means `ai_activity`'s list of today's assistant events, with
addresses). Without it, no answer carries an address.

## Resources and prompt

| URI | What |
| --- | --- |
| `skald://docs/api` | docs/API.md: the data files and the read-only API |
| `skald://docs/counting` | CLASSIFICATION.md: the five groups and what the figures cannot know |
| `skald://sites/<site>/overview` | the site's latest overview.json |

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

Make a token with the `mcp` scope in Settings > API & tokens, for the sites it
should read (or on the server: `skald token create NAME --scope mcp`). Add `read_private` only
if the agent must see addresses. The token is shown once; keep it where you
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
organisation tokens, and stdio in a subprocess).
