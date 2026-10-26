# Command reference

Every command and every argument of `skald` (`skald` in the Docker image), written from
the parser itself by `tools/cli-reference.py`: do not edit by hand.
In Docker, put `docker exec skald` in front: `docker exec skald skald doctor`. What each part
does and when to run it: [README.md](../README.md) ("System"), [DEPLOY.md](../DEPLOY.md),
[INSTALL.md](INSTALL.md) and each part's own guide. Exit codes, unless a command says
otherwise: 0 done, 1 refused or failed, 2 a usage mistake.

## Global options

They go before the command: `skald --config /etc/skald/config.yml --site example.com live`.

| Argument | What it does |
| --- | --- |
| `--config` | the config file (default `config.yml`) |
| `--today` YYYY-MM-DD | pretend the local date is this (replays and tests) |
| `--site` NAME | with several sites (config `sites:`), work on this one only |

## Commands

`check` · `collect` · `backfill` · `dashboard` · `mail` · `export` · `audit` · `live` · `run-daily` · `compare` · `page` · `version` · `user` · `token` · `report` · `verify-bots` · `backup` · `forget` · `mark-deploy` · `markers` · `leads` · `alerts` · `favicons` · `pagespeed` · `events` · `notify-failure` · `accounts` · `org` · `member` · `account` · `site` · `mcp` · `hooks` · `conversions` · `plan` · `usage` · `billing` · `llms-txt` · `updates` · `migrate` · `upgrade` · `doctor` · `logo` · `settings` · `ours` · `search-console` · `bing` · `search` · `reports` · `ai-answers` · `stack` · `views` · `try-log` · `summary-mail`

### skald check

Verify one day's figures; store nothing.

| Argument | What it does |
| --- | --- |
| `--day` | the local day: YYYY-MM-DD, yesterday or today (default `yesterday`) |
| `--log` | read this file, repeatable |

### skald collect

Analyse one day and store it.

| Argument | What it does |
| --- | --- |
| `--day` | the local day: YYYY-MM-DD, yesterday or today (default `yesterday`) |
| `--log` | read this file, repeatable |

### skald backfill

Store each of the last N days.

| Argument | What it does |
| --- | --- |
| `--days` | how many local days, ending yesterday (required) |
| `--force` | re-collect days already stored and verified |

### skald dashboard

Render the static dashboard.

| Argument | What it does |
| --- | --- |
| `--out` | output directory (default dashboard.out) |

### skald mail

Send the daily or weekly mail.

| Argument | What it does |
| --- | --- |
| `--daily` | yesterday's mail (the default) |
| `--weekly` | the last 7 complete days against the 7 before |
| `--dry-run` | print, do not send |
| `--save-html` PATH | also write the HTML part |

### skald export

History or today so far as CSV or JSON; verified days only unless asked.

| Argument | What it does |
| --- | --- |
| `--from` DATE | first day (default: 30 days before --to) |
| `--to` DATE | last day, inclusive (default: yesterday) |
| `--table` | what to export (one of `daily`, `pages`, `ai_pages`, `engines`, `citations`, `countries`, `readers`, `statuses`, `not_found`, `server_errors`, `posts`, `speed`, `slow_pages`, `visits`, `visit_paths`, `journeys`, `campaigns`; default `daily`) |
| `--group` | people, answer_engines, search_engines, bots, ours |
| `--tier` | training, asked or cited |
| `--engine` | an assistant or crawler by name, e.g. GPTBot |
| `--source` | a citing site, e.g. perplexity.ai; on journeys also a referring host or utm_source |
| `--path-prefix` PREFIX | only paths that start with this |
| `--country` CC | only this country (two letters) |
| `--dimension` | readers table: country, browser, os, device, source, referrer, campaign, landing or hour |
| `--browser` | readers table: a browser family, e.g. Chrome |
| `--os` | readers table: an operating system, e.g. iOS |
| `--device` | readers table: Desktop, Mobile or Tablet |
| `--source-type` | readers table: a traffic source, e.g. 'Search engine' |
| `--status` | statuses table: 2xx, 3xx, 404, 4xx, 5xx, other |
| `--view` | a dashboard.views name: export that view |
| `--total` | sum over the range instead of one row per day |
| `--include-withheld` | also export days whose figures did not reconcile, marked state=withheld |
| `--live` | today so far instead |
| `--format` | csv or json (one of `csv`, `json`; default `csv`) |
| `--out` FILE | write here instead of stdout |

### skald audit

Recount a stored day from the raw log by a separate road and compare with history.

| Argument | What it does |
| --- | --- |
| `--day` | the local day: YYYY-MM-DD, yesterday or today (default `yesterday`) |
| `--log` | read this file, repeatable |
| `--withhold` | mark the day withheld if anything does not match |
| `--live` | recount today so far and compare with the live snapshot |

### skald live

Snapshot today so far and redraw the dashboard; never stored as a day, never mailed.

| Argument | What it does |
| --- | --- |
| `--out` | dashboard directory (default dashboard.out) |

### skald run-daily

Check, collect, dashboard, mail.

| Argument | What it does |
| --- | --- |
| `--dry-run` | print the mail instead of sending it |

### skald compare

Compare two date ranges (whole verified days).

| Argument | What it does |
| --- | --- |
| `--a` | YYYY-MM-DD..YYYY-MM-DD: the range looked at (required) |
| `--b` | YYYY-MM-DD..YYYY-MM-DD: what it is compared with (required) |
| `--view` | a view's slug |
| `--filter` | name=value, e.g. country=CA (repeatable) |
| `--json` | print the answer as JSON |

### skald page

One page's story since it was published.

| Argument | What it does |
| --- | --- |
| `path` | the page's path, e.g. /pricing/ |
| `--json` | print the answer as JSON |

### skald version

The name, version and release deployed.

| Argument | What it does |
| --- | --- |
| `--json` | print it as JSON |

### skald user

Named dashboard users and their roles (run as root).

| Argument | What it does |
| --- | --- |
| `action` | list, add, remove or role (one of `list`, `add`, `remove`, `role`) |
| `name` | the dashboard user's name (basic mode's password file) |
| `--role` | the user's role (one of `admin`, `viewer`; default `viewer`) |
| `--password-stdin` | read the new user's password from stdin |

### skald token

API tokens: read the data, the MCP endpoint, or ship a site's log (docs/API.md, docs/INGEST.md).

| Argument | What it does |
| --- | --- |
| `action` | create, list or revoke (one of `create`, `list`, `revoke`) |
| `name` | create: what uses it; revoke: its id |
| `--site` | only this site (repeatable) |
| `--private` | may also read requests.json and ai_activity.json (addresses) |
| `--org` SLUG | sessions mode: the organisation (needed when there are several) |
| `--scope` SCOPE | read (default), read_private (addresses too), mcp (the MCP endpoint) or ingest (post log lines for the --site it names: skald-ship, log drains); repeatable. mcp and ingest need sessions mode |

### skald report

A report to keep or send: one self-contained HTML page (print it for a PDF) or a ZIP of CSV tables.

| Argument | What it does |
| --- | --- |
| `--from` DATE | default: 7 days before --to |
| `--to` DATE | default: yesterday |
| `--view` | a dashboard.views name |
| `--format` | an HTML file, or a zip of CSV files (one of `html`, `csv-zip`; default `html`) |
| `--out` PATH | where to write it (required) |

### skald verify-bots

Fetch the crawler owners' address lists and look up reverse DNS of claimed crawlers (run-daily runs it first).

| Argument | What it does |
| --- | --- |
| `--dns-only` | only look up addresses not seen yet; do not fetch the lists |

### skald backup

Copy history (daily, plus a weekly gzip) and test the copy by restoring it.

| Argument | What it does |
| --- | --- |
| `--dir` | backup directory (default backup.dir, else backups/ beside the history) |
| `--keep` | daily copies kept (default backup.daily, else 14) |
| `--weekly-keep` | weekly gzip copies kept (default backup.weekly, else 8) |
| `--verify` | only restore-test the newest copy |
| `--pull` | print the scp command that fetches the newest copy |

### skald forget

Delete a person (deletion requests): an IP address everywhere it is kept, and an email, visitor ID or lead's conversions.

| Argument | What it does |
| --- | --- |
| `--ip` | the address to forget |
| `--email` | a lead's email: its conversions and identity |
| `--vid` | a visitor ID (skv_...) |
| `--lead` | a lead's id or a tool's reference (external_ref) |
| `--dry-run` | count what would change; change nothing |

### skald mark-deploy

Add a skald deploy marker to the charts (run from the deploy procedure).

| Argument | What it does |
| --- | --- |
| `--label` | what was deployed, e.g. 'release 2: requests feed' |
| `--detail` | one more line, e.g. the commit |

### skald markers

List the chart markers of the last 180 days.

| Argument | What it does |
| --- | --- |
| `--json` | print them as JSON |

### skald leads

Leads from the website's CMS, aggregates only (read-only); --audit recounts them by SQL.

| Argument | What it does |
| --- | --- |
| `--json` | print leads.json's body |
| `--audit` | recount every figure by SQL GROUP BY and compare |

### skald alerts

Evaluate the alert rules now and print them (never mails; the live run mails).

| Argument | What it does |
| --- | --- |
| `--json` | print them as JSON |

### skald favicons

Fetch the icons of referring sites into the dashboard's data/favicons/ (never from a third-party service).

| Argument | What it does |
| --- | --- |
| `--limit` | most hosts fetched (default 10) (default `10`) |

### skald pagespeed

Google PageSpeed Insights for the day's top landing pages, phone and desktop (run-daily runs it last).

| Argument | What it does |
| --- | --- |
| `--day` | the day whose landing pages to test (default yesterday) |
| `--force` | test again pages already tested |

### skald events

In-page events from the beacon: show a day's spool, or --collect / --audit it into history.

| Argument | What it does |
| --- | --- |
| `--day` | the local day: YYYY-MM-DD, yesterday or today (default `today`) |
| `--collect` | count the day's spool into history, verify and audit it |
| `--audit` | recount a stored day from the spool and nginx's beacon log |

### skald notify-failure

One short mail when a scheduled run failed (cron, after run-daily); never for a withheld day.

| Argument | What it does |
| --- | --- |
| `--job` | the job that failed (default `run-daily`) |
| `--exit` CODE | its exit status (cron passes $?) |
| `--log` | its log; the last lines go in the mail |
| `--dry-run` | print the mail, send nothing |
| `--force` | mail even if one went for this job within the cooldown |

### skald accounts

Accounts mode: set up (init) and status.

| Command | Argument | What it does |
| --- | --- | --- |
| `accounts init` | | Make the accounts file from users.json and tokens.json. |
| | `--org` | the organisation's name (required) |
| | `--owner-email` | the owner (an install admin) (required) |
| | `--owner-name` | the owner's name (default: from the email) |
| | `--map` NAME=EMAIL | the email of a users.json name (repeatable); others are asked |
| | `--base-url` | https://host of the dashboard, for the links (default access.base_url, then dashboard.base_url, then dashboard.url) |
| | `--force` | already set up: add only what is missing, never remove |
| `accounts status` | | Mode, organisations, people, invites, tokens. |

### skald org

Organisations (accounts mode).

| Command | Argument | What it does |
| --- | --- | --- |
| `org list` | | Every organisation. |
| `org create` | | Make an organisation. |
| | `name` | its name |
| `org rename` | | Rename an organisation. |
| | `slug` | the organisation's slug (`skald org list`) |
| | `name` | its new name |

### skald member

Members and invites of an organisation (accounts mode).

| Command | Argument | What it does |
| --- | --- | --- |
| `member list` | | The members of one organisation. |
| | `--org` SLUG | needed when there are several |
| `member invite` | | Invite someone by email; prints the invite link. |
| | `email` | their email |
| | `--role` | owner, admin or viewer (required) |
| | `--base-url` | https://host of the dashboard, for the link |
| | `--org` SLUG | needed when there are several |
| `member role` | | Change a member's role. |
| | `email` | the member's email |
| | `role` | the new role |
| | `--org` SLUG | needed when there are several |
| `member remove` | | Take someone out of the organisation. |
| | `email` | the member's email |
| | `--org` SLUG | needed when there are several |

### skald account

One person's sign-in (accounts mode); `skald user` is the basic-mode password file.

| Command | Argument | What it does |
| --- | --- | --- |
| `account reset-link` | | Print a link to set a new password. |
| | `email` | the account's email |
| | `--base-url` | https://host of the dashboard, for the link |
| `account disable` | | Stop an account signing in. |
| | `email` | the account's email |
| `account enable` | | Let a disabled account sign in again. |
| | `email` | the account's email |
| `account totp-off` | | Turn off an account's two-step sign-in. |
| | `email` | the account's email |
| `account install-admin` | | Make an account an install admin, or stop it being one. |
| | `email` | the account's email |
| | `flag` | on or off (one of `on`, `off`) |

### skald site

The install's sites (accounts mode): assign, list, add, hosts, remove, purge, verify.

| Command | Argument | What it does |
| --- | --- | --- |
| `site assign` | | Give a site to an organisation; its settings, set-up progress and the tokens for that site alone move with it. |
| | `site` | the site's name |
| | `--org` SLUG | the organisation's slug (required) |
| `site list` | | Every site, where it is defined, and its organisation. |
| `site add` | | Add a dashboard site to an organisation. |
| | `host` | the site's host name, e.g. example.com |
| | `--org` SLUG | the organisation's slug (required) |
| | `--format` | the log format (auto: told from the lines) (default `auto`) |
| | `--timezone` | the site's IANA time zone, e.g. America/New_York |
| | `--allow-reuse` | re-use a name purged in the last 30 days |
| `site hosts` | | Replace a dashboard site's host names. |
| | `name` | the site's name |
| | `hosts` | every host name it answers to |
| `site remove` | | Stop processing a dashboard site; its data stays until purge. |
| | `name` | the site's name |
| | `--yes` | really remove it |
| `site purge` | | Delete a removed dashboard site and all its data, its logo folder too. |
| | `name` | the site's name |
| | `--yes` | really delete; nothing is undone |
| `site verify` | | Mark a site's domain as verified. |
| | `name` | the site's name |

### skald mcp

MCP server on stdin/stdout for a local agent (docs/MCP.md); read-only.

| Argument | What it does |
| --- | --- |
| `--site` NAME | answer for this site only |
| `--private` | also read the files that hold visitors' addresses (requests, ai_activity) |

### skald hooks

Incoming hooks from the site and its tools (Calendly, Stripe, ...): secrets, list, test.

| Command | Argument | What it does |
| --- | --- | --- |
| `hooks secret` | | Make a hook's secret (printed once, kept 0600). |
| | `site` | the site's name |
| | `tool` | the hook (one of `lead`, `json`, `calendly`, `calcom`, `stripe`, `typeform`, `hubspot`) |
| | `--value` | keep this secret (one the tool made, such as Stripe's whsec_...) instead of a new one; '-' reads it from standard input |
| `hooks list` | | The hooks set up, where their secrets live, their last deliveries. |
| `hooks test` | | Post a signed sample to the local receiver (marked as a test: read, never kept). |
| | `site` | the site's name |
| | `tool` | the hook (one of `lead`, `json`, `calendly`, `calcom`, `stripe`, `typeform`, `hubspot`) |
| | `--url` | the receiver (default hooks.test_url or http://127.0.0.1:8766) |

### skald conversions

The conversions file: list, mark test, remove, forget a person, prune.

| Command | Argument | What it does |
| --- | --- | --- |
| `conversions forget` | | Delete everything for an email, visitor ID or lead. |
| | `--email` | everything kept for this email |
| | `--vid` | a visitor ID (skv_...) |
| | `--lead` | a lead's external reference |
| | `--dry-run` | count what would go; change nothing |
| `conversions prune` | | Delete journeys, conversions, deliveries and spool files past their keeping time. |
| `conversions mark-test` | | Mark conversions as test: kept and listed (Left out), never counted; every stage of the same booking or lead too. |
| | `site` | the site's name |
| | `ids` | conversion ids (conversions list) |
| | `--ref` REF | a lead's external_ref: every stage of it (repeat for more) |
| | `--tool` | the tool the refs came through (default lead) (one of `lead`, `json`, `calendly`, `calcom`, `stripe`, `typeform`, `hubspot`; default `lead`) |
| | `--unmark` | count them again |
| `conversions remove` | | Soft-remove a lead's rows: each kept whole under Show left out > Removed with when and why, out of every count. |
| | `site` | the site's name |
| | `--ref` | the lead's external_ref (required) |
| | `--tool` | the tool it came through (default lead) (one of `lead`, `json`, `calendly`, `calcom`, `stripe`, `typeform`, `hubspot`; default `lead`) |
| | `--stage` | only this stage (default every stage) (one of `started`, `completed`, `cancelled`, `rescheduled`, `no_show`, `paid`, `won`, `lost`, `refunded`) |
| | `--action` | only this action |
| | `--why` | why it goes (kept with each row) (required) |
| | `--dry-run` | list what would go; change nothing |
| `conversions list` | | The latest conversions of a site, with their ids. |
| | `site` | the site's name |
| | `--test` | only the ones marked test |
| | `--limit` | how many (default `50`) |

### skald plan

Saas plans: list them, or set an organisation's.

| Command | Argument | What it does |
| --- | --- | --- |
| `plan list` | | The plans in the config, then each organisation's plan and status. |
| `plan set` | | Give an organisation a plan (none takes it away). |
| | `org` | the organisation's slug or name |
| | `plan` | a plan in saas.plans, or none |
| | `--status` | the billing status (one of `trialing`, `active`, `past_due`, `canceled`, `none`) |
| | `--trial-days` | start a trial of N days from now |

### skald usage

Saas: this month's requests per organisation.

| Argument | What it does |
| --- | --- |
| `--org` SLUG | one organisation (its slug) |
| `--month` YYYY-MM | another month |

### skald billing

Saas: the Stripe secrets (read from stdin).

| Command | Argument | What it does |
| --- | --- | --- |
| `billing secret` | | The Stripe secret key or the webhook's signing secret, read from stdin into secrets.json (0600); never printed. |
| | `which` | which secret (one of `key`, `webhook`) |

### skald llms-txt

Suggest an /llms.txt from the pages read most (prints it; never writes to the website).

| Argument | What it does |
| --- | --- |
| `--site` NAME | with several sites, this one |
| `--out` FILE | write it to FILE instead of printing it |

### skald updates

Is a newer release out? (asks GitHub at most once a day; updates.check).

| Argument | What it does |
| --- | --- |
| `--check-now` | ask GitHub now, whatever the time of the last answer |
| `--json` | print the answer as JSON |

### skald migrate

Upgrade the databases to this code's schema, after a restore-tested copy (--check: list only).

| Argument | What it does |
| --- | --- |
| `--check` | list each database, its schema, the code's, and the steps pending |
| `--json` | --check as JSON, with the record |
| `--no-backup` | skip the copy (`upgrade` has just taken one) |

### skald upgrade

Install a newer release (install.sh layout): check, back up, swap, migrate, health-check, roll back on failure.

| Argument | What it does |
| --- | --- |
| `--to` vX.Y.Z | this release instead of the latest |
| `--dry-run` | download and check it, say what would happen, change nothing |
| `--yes` | do not ask before upgrading |
| `--allow-major` | allow a new major version (read its notes first) |
| `--auto` | the daily timer: only what updates.auto allows; mails the result |
| `--source-url` URL | a folder holding skald-X.Y.Z.tar.gz and SHA256SUMS (default: the GitHub release) |

### skald doctor

Is this install working? one line per part, with the fix (reads only; --send-test sends one mail).

| Argument | What it does |
| --- | --- |
| `--json` | the same list as JSON, one object per site |
| `--send-test` | also send one test mail to the recipients |

### skald logo

The site's logo: where it comes from, and --check to ask the site for it now (never an outside icon service).

| Argument | What it does |
| --- | --- |
| `--check` | ask the site for its icon now |

### skald settings

The dashboard's settings from the shell (accounts mode): list-keys, get SITE [KEY], set SITE KEY VALUE.

| Command | Argument | What it does |
| --- | --- | --- |
| `settings list-keys` | | Every key: kind, scope, who, default. |
| `settings get` | | A site's values and where each comes from. |
| | `site` | the site's name |
| | `key` | the setting's key (`settings list-keys`) |
| `settings set` | | Save one value (JSON; null clears the row), audited as cli. |
| | `site` | the site's name |
| | `key` | the setting's key (`settings list-keys`) |
| | `value` | JSON: true, 180, '["/wp-content/"]', null; or a word |
| | `--yes` | a smaller retention window: really remove the older data |

### skald ours

Internal traffic: list, pause, resume, edit, delete the addresses added on the page.

| Command | Argument | What it does |
| --- | --- | --- |
| `ours list` | | Every entry by label, Active or Paused. |
| `ours pause` | | Stop it applying from now on. |
| | `entry` | the entry's label or address |
| `ours resume` | | Apply it again from now on. |
| | `entry` | the entry's label or address |
| `ours edit` | | Change the label and/or the address from now on. |
| | `entry` | the entry's label or address |
| | `--label` | its new label |
| | `--address` | its new address |
| `ours delete` | | Stop it applying from now on (needs --yes). |
| | `entry` | the entry's label or address |
| | `--yes` | really delete it |

### skald search-console

Sync Google Search Console figures into history (the scheduler runs `search sync` every 6 hours).

| Argument | What it does |
| --- | --- |
| `action` | sync (import is the same): fetch the newest days and the last days again; status: what is connected and how the last sync went (one of `sync`, `import`, `status`) |
| `--days` | fetch this many recent days again (default 4; Bing: keep only the last N days it returns) |
| `--backfill-months` | fetch this much history first (Search Console keeps 16 months) (one of `3`, `16`) |

### skald bing

Sync Bing Webmaster Tools figures into history (the scheduler runs `search sync` every 6 hours).

| Argument | What it does |
| --- | --- |
| `action` | sync (import is the same): fetch the newest days and the last days again; status: what is connected and how the last sync went (one of `sync`, `import`, `status`) |
| `--days` | fetch this many recent days again (default 4; Bing: keep only the last N days it returns) |

### skald search

Sync Search Console and Bing figures into history (the scheduler runs `search sync` every 6 hours).

| Argument | What it does |
| --- | --- |
| `action` | sync (import is the same): fetch the newest days and the last days again; status: what is connected and how the last sync went (one of `sync`, `import`, `status`) |
| `--days` | fetch this many recent days again (default 4; Bing: keep only the last N days it returns) |
| `--backfill-months` | fetch this much history first (Search Console keeps 16 months) (one of `3`, `16`) |

### skald reports

Client reports: send the due ones, list, send or write one (Settings > Reports).

| Argument | What it does |
| --- | --- |
| `--due` | send every report that is due |
| `--list` | each report and its sends |
| `--send` ID | send this report now |
| `--pdf` ID | write its PDF, send nothing |
| `--out` FILE | with --pdf: where to write it |

### skald ai-answers

Ask the AI assistants the tracking profiles' questions (AI answers); --due asks only what is due.

| Argument | What it does |
| --- | --- |
| `--due` | only profiles whose time has come (default) |
| `--now` | with --profile: run it now, due or not |
| `--profile` | one profile's id |
| `--show` | print one stored answer in full, by its id |

### skald stack

Check now what serves the site and which advisories apply.

No arguments.

### skald views

Page groups: list them, or fill their past days from the raw log (refresh).

| Command | Argument | What it does |
| --- | --- | --- |
| `views list` | | Each view, its rule and its first stored day. |
| `views refresh` | | Recount the views' past days from the raw log, audited (default: every whole day the log holds). |
| | `--days` | the last N days instead |
| | `--view` SLUG | only this view (its folder name), repeatable; default every view |
| | `--by` | who asked (the page passes the admin's email) |

### skald try-log

A dry run: can Skald read this log file, and what would it count? Stores nothing.

| Argument | What it does |
| --- | --- |
| `file` | a log file, plain or .gz |
| `--format` | the reader to use (default auto: the one that reads the most lines) (one of `auto`, `akamai_json`, `apache_combined`, `caddy_json`, `cloudflare_json`, `cloudfront_w3c`, `edge_json`, `fastly_json`, `netlify_json`, `nginx_combined`, `nginx_extended`, `vercel_json`; default `auto`) |
| `--site` HOST | the site the log is for: its settings judge the lines |
| `--lines` | how many lines to read from the top (default 500) (default `500`) |
| `--json` | the report as JSON |

### skald summary-mail

The daily summary: one mail per person with what to look at on every site (security, to-dos, set-up).

| Argument | What it does |
| --- | --- |
| `--dry-run` | print the mails instead of sending them |
| `--after` HH:MM | do nothing before this time of day (the site's zone): for an hourly cron line |
