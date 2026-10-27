# The read-only API

Every figure Skald shows is also a JSON file that a script, a spreadsheet or another tool can read with a token. This guide covers tokens, scopes, the addresses to call, and what the answers look like.

## What the API is

The API gives you the same data files the dashboard itself reads. Nothing is counted again, and nothing can be changed through it. It is read-only.

The files are rewritten every 2 minutes. Each file says when it was written, in its `generated_at` field.

There are two ways in:

| Way in | Who it is for | How it proves who you are |
| --- | --- | --- |
| While signed in | You, in your own browser, for a quick look | Your dashboard sign-in |
| With a token | A script, a spreadsheet, another tool | A token in the `Authorization` header |

Both ways show exactly the same files.

## Where to find it

Open **Settings > AI > AI assistants > API**, or go straight to [API](#settings/ai/assistants?sub=api). Settings opens from the gear at the foot of the sidebar. Old links to Connections or API & tokens still work: they open the page the setting is on now.

The page has:

- how it works, first: the base address and the files this site serves;
- **Set up the API**: a dialog in three steps, **How it works** (the base address, the files), **Token** (with the curl command right under it) and **Test** (admins only);
- **Quick look while you are signed in**: the address of the overview file in this browser, and every file name you can put in place of `overview`.

Your tokens are on their own page, **Settings > AI > AI assistants > Tokens & links** ([Tokens & links](#settings/ai/assistants?sub=tokens)): every token of your organisation, **New token**, and the shared links (admins only).

## Tokens

A token is a long secret that lets a script read your figures without a password. It looks like this:

```
skald_<id>_<secret>
```

Treat it like a password. Keep it in a password manager or your tool's secret store. Never put it in a shared document, a chat, or a code repository.

### Who can make tokens

Only an owner or an admin of the organisation can make, see or revoke tokens. A viewer sees a note that tokens are for admins. See [Sign-in and team](sign-in-and-team.md) for roles.

### Make a token

1. Open [API](#settings/ai/assistants?sub=api) and press **Set up the API**.
2. **How it works** shows the base address and the files. Press **Next**.
3. **Token.** Keep the **Name** it suggests, or type one that says what it is for, for example "Weekly sheet". Leave **Can also read visitor addresses** off unless the script really needs them.
4. Press **Make the token**.
5. Copy the token from the green box. It is shown only this once. The curl command right under it has the token in it.
6. Press **Next** to **Test** it. The test names the next step.

The token made there reads the site you are on. For a token that reads several sites, or does several things, press **New token** in [Tokens & links](#settings/ai/assistants?sub=tokens): tick the **Sites** and what it may do, then press **Make token**.

> Skald keeps only a fingerprint of the token, never the token itself. If you lose it, nobody can show it to you again. Revoke it and make a new one.

### The token list

**Your tokens**, in **Settings > AI > AI assistants > Tokens & links**, shows each token's **Name**, **What it is for** (in words, such as "Reading figures"), **Sites**, when it was **Made** and by whom, and when it was **Last used**. The token itself is never shown again.

### How long a token lasts

A token has no expiry date. It works until one of these happens:

- an admin revokes it;
- the person who made it is removed, disabled, or is no longer an owner or admin.

The second rule means a token stops at once when its maker leaves the team. Make tokens for long-running jobs with that in mind.

### Revoke a token

1. Open [Tokens & links](#settings/ai/assistants?sub=tokens).
2. Find the token under **Your tokens** and press **Revoke**.
3. Press **Yes, revoke**.

Every script using it stops at once. Revoking cannot be undone.

## Scopes

A scope is what a token may do. A token can have more than one.

| Scope | Label in the app | What it allows |
| --- | --- | --- |
| `read` | Reading figures | Read every figure these pages show, as JSON, through the API |
| `read_private` | Reading visitor addresses | Also read the two files that hold visitor addresses, `requests` and `ai_activity`, and look a person up |
| `mcp` | AI assistant (MCP) | Let an AI assistant ask about your traffic through the MCP server |
| `ingest` | Sending logs | Send a site's log lines into Skald. It reads nothing |

The box **Can also read visitor addresses** in the API dialog adds **Reading visitor addresses**. A sending token is made in **Send this site's visits to Skald**, in **Settings > This site > Data > Send logs** (see [Connections](connections.md)).

> A token with only **AI assistant (MCP)** cannot read the API, and a token with only **Reading figures** cannot be used by an AI assistant. Press **New token** and tick both if one token must do both.

## The addresses to call

Every address starts with your dashboard's own address. In the examples below it is `https://analytics.example.com`, and the site is `example.com`.

With a token:

```
https://analytics.example.com/traffic-api/v1/<site>/<file>
https://analytics.example.com/traffic-api/v1/<site>/<view>/<file>
```

While signed in, in your browser:

```
https://analytics.example.com/traffic/<site>/api/v1/<file>
https://analytics.example.com/traffic/<site>/<view>/api/v1/<file>
```

- `<site>` is the site's name, for example `example.com`.
- `<view>` is a part of the site, such as `us-english`. Leave it out for the whole site.
- `<file>` is a file name without `.json`, for example `overview`.

The signed-in address also lists the files a page has: end it at `api/v1/`. The token address has no list; use the list in the API dialog's **Use it** step, or under **Quick look while you are signed in**, instead.

## The main files

| File | What it holds |
| --- | --- |
| `overview` | Headline figures per day: visits, pages read, AI and search fetches, 404s, errors |
| `live` | Today so far, from the 2-minute snapshot |
| `visits` | Visits per day, and today's anonymous journeys |
| `hourly` | Figures per hour |
| `breakdowns` | Countries, sources, devices, browsers and more |
| `pages` | Each page: readers, entries, exits, AI and search fetches |
| `campaigns` | Tagged links and campaigns |
| `bots` | Crawlers and bots |
| `leads` | Leads from the website's forms |
| `conversions` | Demos, forms, sign-ups and payments by stage |
| `funnels` | Saved funnels and their results |
| `quality` | Whether each day was read whole and passed its checks |
| `health` | Server health |
| `alerts` | Open alerts |
| `ours` | Your own traffic and the heartbeat |
| `todos` | Overview > Insights' to-do list: each to-do's proof, what to do, and whether it is to do, marked done (with its re-check) or not now |
| `lost_pages` | Site > Not found: old addresses still asked for, the closest live page, and the nginx and Apache lines |
| `page_changes` | The changes marked on a page, and whether each worked (the days before against the days after) |
| `ai_ready` | AI readiness: robots.txt for each main AI crawler, what AI got back by page, the sitemap |
| `page_trends` | Each page's visits and AI reads by day, and the pages changed in the last 30 days |
| `ai_activity` | What AI assistants did (holds addresses: needs **Reading visitor addresses**) |
| `requests` | The recent request log (holds addresses: needs **Reading visitor addresses**) |
| `people?q=...` | One person by IP address, email, visitor ID or lead: their visits, leads and conversions, linked. Needs **Reading visitor addresses**; each search goes to the audit log |

The **Read figures (API)** page lists every file your site really has.

## Examples with curl

Read the overview of the whole site:

```
curl -H "Authorization: Bearer skald_<id>_<secret>" \
  https://analytics.example.com/traffic-api/v1/example.com/overview
```

Read the pages of one view:

```
curl -H "Authorization: Bearer skald_<id>_<secret>" \
  https://analytics.example.com/traffic-api/v1/example.com/us-english/pages
```

The header must be exactly `Authorization: Bearer ` followed by the token.

## What an answer looks like

Every file starts with the same few fields, then its own figures. Most files hold one entry per day for the last 180 days, oldest first. A short piece of `overview`:

```json
{"schema_version": 1, "generated_at": "2026-10-08T07:16:02-04:00",
 "site": "example.com", "view": null, "timezone": "America/New_York",
 "anchor": "2026-10-07", "first_day": "2026-09-01",
 "days": [
  {"day": "2026-10-05", "state": "withheld", "problems": "the audit did not agree"},
  {"day": "2026-10-06", "state": "ok", "not_found_people": null, "server_errors": 0,
   "visits": {"visits": 120, "views": 170, "one_page": 98, "median_seconds": 4}},
  {"day": "2026-10-07", "state": "ok", "not_found_people": 9, "server_errors": 0,
   "visits": {"visits": 140, "views": 190, "one_page": 118, "median_seconds": 3}}
 ]}
```

### Read the day's state first

Each day has a `state`. Check it before you use any figure.

| State | Figures? | What it means |
| --- | --- | --- |
| `ok` | Yes | A whole day that passed every check |
| `partial` | Yes | Checked, but the logs did not cover the whole day. Do not add it to whole days or compare it with them |
| `withheld` | No | It failed a check, so Skald shows no figures for it. `problems` says why |
| `missing` | No | Not collected |
| `before` | No | Before your history starts |

### Not recorded is null, never 0

- A figure that was not recorded is `null`. It never becomes `0`.
- `0` means Skald counted and found none.
- A withheld or missing day has no figures at all. Leave it out of totals and say so; never count it as zero.
- Visits are an upper bound on people, not a count of people. Requests are never people.

> In a spreadsheet, keep `null` as an empty cell. If you turn it into 0, your totals and averages will be wrong.

## Errors

| Status | Body | When |
| --- | --- | --- |
| 200 | The file | All went well |
| 401 | `{"ok": false, "error": "..."}` | No token, a wrong or revoked token, a token for another site, a token without **Reading figures**, or a private file without **Reading visitor addresses** |
| 404 | `{"ok": false, "error": "no such file"}` | The site, view or file does not exist |

The `error` text says which problem it was, for example "unrecognised or revoked token" or "this token is not for that site". The **Test** step of the API dialog says each answer in words; see [If a connection does not work](troubleshooting-connections.md).

Answers are never cached. Ask again for fresh figures; they change every 2 minutes.

## Rate limits

Skald sets no request limit of its own on the API today, so you will not see a 429 answer from Skald. Whoever runs your server may add one. The files only change every 2 minutes, so asking more often than that gains nothing. Once every few minutes is plenty for a live screen; once a day is enough for a report.

## Servers that use one shared login

Some Skald servers have no team accounts. Everyone signs in with one shared name and password set on the server. On those servers:

- the **Read figures (API)** page says its set-up dialog needs team accounts. Under **Read the figures with the dashboard login, or a token made on the server** it shows the address and curl command with your login, and with a token;
- tokens are not made on the page. Whoever runs the server makes them with a command, and the page shows that command;
- the signed-in address also works from curl with `curl -u <your name>`, using the dashboard password;
- the MCP server is not available. See [MCP](mcp.md).

Everything else in this guide is the same.

## Related guides

- [Connections](connections.md): sending logs, the set-up dialogs, Tokens & links, and adding a site.
- [MCP](mcp.md): let an AI assistant read your figures.
- [Sign-in and team](sign-in-and-team.md): roles, and who may make tokens.
- [Privacy](privacy.md): which files hold addresses.
