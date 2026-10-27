# From your tools: figures from a person's own tools

Skald counts from the server log. A person's own tools (Google Analytics 4, and later Search
Console beyond Traffic › Search, Vercel Web Analytics, Calendly, Resend) count in their own way.
The owner's decision of 2026-10-27: Skald may show those tools' numbers, read with the person's
OWN keys from the tools' free APIs, in their own area, **never mixed into the log's counts**.
No LLM call, ever. The end-user guide is [help/your-tools.md](help/your-tools.md).

## The rules

- **Apart.** Every figure from a tool is labelled with its tool ("Counted from: Google
  Analytics"), on Overview's card **From your tools**, in MCP's `your_tools` and in the API
  answers. Nothing here is added to, compared into or subtracted from a log figure.
- **Every figure reconciles, or it is withheld.** Each answer is stored exactly as it came,
  with its SHA-256. Each figure shown records where in that answer it was read (a JSON pointer,
  RFC 6901). After every sync, `recount.py` reads every figure again from the stored answer
  by its own code; a mismatch sets the tool to **Withheld** and hides its figures.
- **Unknown stays unknown.** A figure the tool did not give is NULL ("Not given"), never 0. No
  answer kept: no figure.
- **No secrets.** A key lives in the server's environment (named in the config) or in
  `secrets.json` (0600, `conversions/secrets_store.py`) as `tools/<site>/<tool>`. It is never
  shown again, logged, mailed or put in an address; the pages show only "who" (a service
  account's address, a token's last four characters).
- **No new crawling.** A suggestion (a GA4 `G-...` tag) comes only from what the site check
  already fetched (`accounts/site_setup`'s `found`).
- **Low priority.** The scheduler's `tools` job runs every 6 hours (`SKALD_TOOLS_HOURS`, `0`
  off), first at `SKALD_TOOLS_AT` (02:10), at a nice level 5 above the other jobs.

## The parts (`skald/yourtools/`)

| File | What it does |
|---|---|
| `__init__.py` | `adapters()`: every `tool_<id>.py` that exports `ADAPTER`, found by name; `get(id)`; `register`/`unregister` for tests |
| `base.py` | the adapter interface: `Adapter`, `Option`, `Answer`, `Figure`, `BadKey`, `Unreachable`, `pointer()`; `when()` (a tool's time to aware UTC) and `kept_person()` (the People rule for a name or email) |
| `names.py` | the name lists the main code and the audit share (GA4's metrics, reports, labels, flags) |
| `keys.py` | where a site's key lives: `find`, `state` (`{set, where, who, problem}`), `put`, `remove`, `in_env` |
| `conn.py` | which tools are on, per site (`<history folder>/yourtools/<site>.json`): options, who connected it, the last try and the last good answer, the error, the audit; `status()` gives the one state every screen shows |
| `store.py` | the raw answers and their figures (`<history folder>/yourtools.sqlite`, never `history.sqlite`) |
| `sync.py` | `run(job)`: ask each tool that is on, keep its answers and figures, recheck them; `connect`, `pause`; the CLI `skald tools` |
| `recount.py` | the second road: shares only `names.py` with the rest |
| `api.py` | the dashboard's routes, under `<page>/integrations/yourtools` |
| `tool_<id>.py` | one tool each: `tool_ga4.py` (Google Analytics 4), `tool_vercel.py` (Vercel Web Analytics), `tool_calendly.py` (Calendly history), `tool_resend.py` (Resend) |

`kit/agent_tools.py` is the agent's route and step text; `mcp/tools_yourtools.py` the MCP tool.

### States

| State | Pill | When |
|---|---|---|
| `off` | off | not connected, or paused (`paused_at`) |
| `no_key` | warn | on, but no key found (or the secrets file is not 0600) |
| `waiting` | info | on, never tried yet |
| `answering` | good | the last try was good and its recheck matched |
| `failing` | warn | the last try failed; the last good answer is under 26 hours old |
| `stopped` | bad | no good answer for 26 hours, or never |
| `withheld` | bad | the last recheck (`recount.py`) did not match |

A failure keeps the figures from the last good answer and mails the site's recipients once
per run of failures (`failmail`).

## The routes

Dashboard (sessions, `yourtools/api.py`; the nginx helper's `integrations/...` location covers them):

| Route | Who | What |
|---|---|---|
| `GET <page>/integrations/yourtools/figures` | any member | the tools that are on, their state and figures (no key, no "who", no error) |
| `GET <page>/integrations/yourtools` | owner, admin, install admin | every tool Skald knows: state, where its key lives and "who", options, what key it needs and which permission, suggestions |
| `POST .../yourtools/key` `{site, tool, key, options, replace}` | admins | keep a pasted key (never replaces one unless `replace: true`) and switch it on; audit `tools.key` |
| `POST .../yourtools/set` `{site, tool, options}` | admins | change its options, switch it on; audit `tools.set` |
| `POST .../yourtools/pause` | admins | stop asking; the key and figures stay; audit `tools.pause` |
| `POST .../yourtools/remove` | admins | remove its key (not one in the environment) and pause; the figures stay; audit `tools.remove` |
| `POST .../yourtools/sync` | admins | ask now, at most once in 10 minutes (429); audit `tools.sync` |

The agent's route: `POST /traffic-kit/<code>/toolkey?tool=<id>[&<option>=<value>][&replace=1][&key=search]`,
the key on stdin, only for a line with the `connect-tools` job made by an install admin (checked
again at the upload), its own rate limit, one audit row `tools.key` without the key
([INGEST.md](INGEST.md), "The agent line"). nginx: the kit's POST location takes
`(report|hooksecret|searchkey|toolkey)` (DEPLOY.md; `docker/nginx.conf` has it).

MCP: `your_tools` (read-only; any token that may read the site).

## The CLI

```
skald --site <site> tools status                 # every tool: state, options, where its key lives
skald --site <site> tools sync [<tool>]          # ask now (the scheduler's job, without --site: every site)
skald --site <site> tools audit [<tool>]         # recheck every stored figure; exit 1 on a mismatch
skald --site <site> tools connect <tool> --option name=value [--key-stdin] [--replace]
skald --site <site> tools pause <tool>
```

## A key in the server's environment

```yaml
your_tools:
  example.com/ga4: SKALD_GA4_KEY_EXAMPLE        # flat: "<site>/<tool>": the variable's name
# or, nested:
your_tools:
  example.com:
    ga4: {key_env: SKALD_GA4_KEY_EXAMPLE}
```

A key named this way wins over `secrets.json`, cannot be changed or removed from the pages or
the agent (409), and the pages say so.

## Google Analytics 4 (`tool_ga4.py`)

- **Key.** A service-account key file (JSON) by default: a JWT bearer signed by `search/rsa.py`
  through `search/google.Client` with the scope `analytics.readonly`. It may be the install's
  Search Console key (option `key=search`; nothing copied, `keys.find` reads it where Search
  Console keeps it). Or an OAuth `authorized_user` file (client_id, client_secret,
  refresh_token): Skald trades the refresh token at `oauth2.googleapis.com/token`. "Who": the
  service account's address, or "a Google sign-in (OAuth client ...)".
- **Option.** `property`: the property ID's digits (not the `G-` measurement ID).
- **Calls.** Three `POST analyticsdata.googleapis.com/v1beta/properties/<id>:runReport`, dates
  `28daysAgo` to `yesterday` (GA4's own days):

  | Report | Dimensions | Metrics | Also |
  |---|---|---|---|
  | `totals` | none | sessions, totalUsers, engagedSessions, keyEvents | the one row is the total |
  | `landing` | landingPage | sessions, keyEvents | limit 10, by sessions, `metricAggregations: TOTAL` |
  | `sources` | sessionSourceMedium | sessions, keyEvents | the same |

- **The window.** The answer names the property's time zone (`metadata.timeZone`); the 28 days
  kept are worked out in it (`zoneinfo`; without tz data, UTC, and the note says so).
- **Figures.** GA4's string values as numbers. Totals come from GA4 (the no-dimension row or
  its TOTAL), never by adding rows: users are not additive. A metric GA4 did not give, or an
  answer with no rows: NULL. Headline: sessions, users, key events.
- **Flags.** `subjectToThresholding`, `samplingMetadatas`, `dataLossFromOtherRow`, shown in
  plain words (`names.GA4_FLAGS`).
- **Recheck.** `recount._ga4` recounts every answer whole from its headers, rows and totals
  and finds a figure changed, missing or extra, besides the pointer check every tool gets.
- **Refusals.** 403: add the robot as a Viewer, or turn on the Data API; 400/404: no such
  property (use the digits); 429: quota; a token refused: the key was deleted or the refresh
  token revoked. Never a token or secret in the words.
- **Suggestions.** The site check (`site_detect.tags_of`) reads `G-` tags and Calendly links
  from the home page it already fetched (`found.tags`); the drawer shows the `G-` id.
- **The agent.** With Skald's Search Console robot: `key=search` and the one Viewer click.
  Else a key file from the project, a JSON key in `.env`, or (with `gcloud` and a yes) a new
  service account `skald-ga4` with the Data API turned on, its key sent from a 0600 file and
  removed.

## Vercel Web Analytics (`tool_vercel.py`)

Vercel's documented Web Analytics API (public since May 2026), with a Vercel access token:

- `GET https://api.vercel.com/v1/query/web-analytics/visits/count?projectId=&teamId=&since=&until=`:
  `data.visitors`, `data.pageviews` (production only).
- `GET .../visits/aggregate?by=<requestPath|referrerHostname|country>&limit=10&...`: the top 10
  rows (`data[].key`, `visitors`, `pageviews`); the rest in Vercel's own "Others" row, kept
  as Vercel gave it (flag `others`). An empty key (no referrer) is shown as `(none)`.
- The window: the last 28 whole UTC days (`since` = today - 28, `until` = yesterday, both
  inclusive); note "Vercel's own days, UTC, production only". `latest_only`.
- Options: `project` (required; env `VERCEL_PROJECT_ID`) and `team` (`team_...`; env
  `VERCEL_TEAM_ID`, `VERCEL_ORG_ID`). Key names an agent may find: `VERCEL_TOKEN`,
  `VERCEL_ACCESS_TOKEN`, `VERCEL_API_TOKEN`.
- Vercel tokens cannot be read-only: the permission asks for one scoped to the project's team,
  with an expiry. Refusals in words: 401/403 (expired or out of scope), 402 (Web Analytics not
  on the plan), 404 (no such project), 429. An answer not in the documented shape keeps the
  last figures and says so.
- The drawer's note: Skald's own count of the site comes from Vercel's log drain (the ingest
  road every Vercel site uses); this is Vercel's own count, apart. Recounted whole by
  `recount._vercel`.

## Calendly history (`tool_calendly.py`)

Calendly API v2 with a personal access token (scopes `users:read`, `scheduled_events:read`;
legacy tokens have every scope):

- `GET /users/me`, then every page of `GET /scheduled_events` (`user` or, with option
  `scope=organization`, `organization`; `min_start_time` = 90 days back, `max_start_time` =
  60 ahead, `count=100`, `sort=start_time:asc`; at most 20 pages, else `incomplete`); then
  `GET /scheduled_events/<uuid>/invitees` for past active meetings (no-shows; at most 150,
  else `no_shows_partial`) and the 10 newest bookings.
- Only whitelisted fields are kept (`EVENT_KEEP`, `INVITEE_KEEP`; a cancellation keeps only
  who and when): no answers to questions, phone numbers or reasons.
- One answer `totals`, with counted figures (names.py `CALENDLY_COUNTS`): bookings, upcoming,
  past, canceled, no_shows (NULL when not every past meeting's invitees were read),
  booked_7d and booked_prev_7d (by `created_at`, days (0, 7] and (7, 14] before UTC midnight
  of the ask), and each event type's bookings. `incomplete`: every figure NULL.
- Never a lead: the webhook adapter (`conversions/adapters/calendly.py`) stays the only road.
  `more()` says "Of these N bookings, M reached Skald by the webhook too; K did not", matched
  on the meeting's URI against the leads' `external_ref` (the invitee URI), counted twice:
  a Python prefix set here, SQL `LIKE` in `recount.webhook_match`; when they differ the
  line is withheld.

## Resend (`tool_resend.py`)

Resend's API with a full-access key (a sending-only key cannot read: refused in words);
0.6 s between calls (two a second):

- every page of `GET /contacts` (`limit=100`, `after`; at most 50 pages): contacts,
  subscribed, unsubscribed (NULL when not every page was read);
- `GET /segments` (Resend's audiences are now segments), at most 20, and each one's contacts
  (`GET /contacts?segment_id=`);
- `GET /emails?limit=100`: the newest 100 emails' `last_event` states (flag `recent_only`
  when there are more).
- Kept: ids, times, states, segment names; an address only for the 10 newest contacts and
  emails; never a name or a subject.

## Names and emails in an answer

`Adapter.scrub(answer, policy)` runs before an answer is stored. `policy` is
`sync.people_policy(job)`: `identity` (`people.policy.identity_full`, the site's
`conversions.identity`), `keep_days` (the People days) and `now`. A name or email is kept only
when `kept_person(at, policy)`: identity full and within the People days. `latest_only` tools
keep only their newest answer, so an old answer's names go at the next good sync. A tool that
stopped answering keeps its last answer, so the daily prune also sweeps the stored answers
(`yourtools/people_days.py`, from `cli_conversions.cmd_prune`): each goes through its tool's
`scrub` again with the site's People days counted back from midnight UTC. Only the names and
emails go; the figures stay, and the answer's sha256 is made again from the cut text in the
same write, so the recount still matches (no figure reads a name or an email). A site that
keeps everything (`keep_everything.Keeper`, the organisation rule deciding) loses nothing. `more(ctx)`
gives admins extra lines and the newest people (`{"lines": [...], "people": [{when, what,
state, name, email}]}`), shown in the drawer with copy icons; members never get it.
`notes` are the drawer's fixed lines about where the figures come from.

Calendly's and Resend's figures are counts of records, with no single place in the answer:
`recount.COUNTED` lists them, and their `src` may be NULL; the recount works each one out
again from the stored answer by its own reading of names.py's rules, keyed by (name, dim,
rank), so a changed, missing or extra figure withholds the tool.

## Marketing alerts and the Monday mail

`alerts_marketing.py` reads these figures for four alerts (`tool_stopped`, `leads_drop`,
`bookings_drop`, `ga4_log_gap`; docs/DATA-CONTRACT-ALERTS.md), and `mail_marketing.py` puts
each connected tool's headline figures in the optional Monday marketing mail, under
"Counted from: <tool>", after Skald's own (docs/SETTINGS.md `mail.marketing`).

## Adding a tool

One file and its tests:

1. `skald/yourtools/tool_<id>.py` with `ADAPTER = <your Adapter subclass>()`. Set `id`
   (the file's `<id>`), `name` (the label every figure carries), `key_words`, `permission`
   (read-only first), `make_key`, `env_names` (the `.env` names an agent may find), and
   `options` (`{name: Option(label, pattern, words, env=(...))}`, never a secret).
2. `check_key(text)`: read the key with `plain_key_words`, refuse a wrong shape with `BadKey`
   in plain words (never echo the key), return `{"who": <what may be shown again>}`.
3. `fetch(key, options, now, opener, sleep)`: ask the tool's free API (standard library only;
   `search/http.call` for retries), return `[Answer]`, one per question, each with the tool's
   own window (`start`, `end`, `note`) and what the tool said about its answer in `flags`.
   Raise `Unreachable(words, code)` in plain words.
4. `figures(answer)`: one `Figure` per value shown, each with `src` (where the value is), and
   `name_src`/`dim_src` when the answer names it. A value the tool did not give: `value=None`,
   `src=None`.
5. Put the names the audit needs in `names.py`, and, for a full recount, add the tool to
   `recount.RECOUNTS` with its own reading of the answer's shape (sharing only `names.py`).
6. Tests with recorded answers through `opener`, no network: the figures, NULL for a missing
   value, the audit finding a changed figure, `check_key` refusing a wrong shape.

The framework does the rest: the key's storage, the routes, the agent's steps and its route,
the set-up line ("<name> connected", optional), the drawer on Leads & tools, Overview's card and
MCP.
