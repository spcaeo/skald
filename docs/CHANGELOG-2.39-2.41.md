# Changelog: 2.39.0 to 2.41.0

The releases of 26 October 2026. Newer ones: [CHANGELOG-2.42.md](CHANGELOG-2.42.md); older ones: [CHANGELOG-2.36-2.38.md](CHANGELOG-2.36-2.38.md).

## 2.41.0 (2026-10-26)

The dashboard opens fast and stays fast as data grows: code and data are compressed, code is cached until the next release, the four big lists load only when their tab opens, and the counting runs give way to the dashboard. Measured on a 3,000-page sample over a slow line, a first load went from 8.0 s and 17.8 MB to 1.4 s and 1.4 MB, and a site switch from 7.9 s to 0.4 s. Each site gets its own AI agent line, so ten sites can be set up at once, and Search Console is an agent job. Every Insights to-do has one **Fix this** button: your AI agent gets the full list from Skald, fixes it and reports back.

### Upgrade

- **Docker:** nothing to do. The image's nginx compresses and caches by itself.
- **Self-hosted with your own front nginx built from DEPLOY.md:** copy the new cache `map` and the
  gzip lines, and widen the kit's POST location to `(report|hooksecret|searchkey)` plus the new
  `/fix` location (DEPLOY.md). Rolling back below 2.41.0 while keeping those lines: first delete
  the `*.json.gz` files beside the data files (UPGRADING.md).
- Scheduled jobs now run at a lower CPU priority (`SKALD_JOB_NICE`, default 10; `0` turns it off).

### The dashboard opens fast, and stays fast as data grows

- **Fixed.** Opening a site fetched every data file at full size, every time: on a sample of
  3000 pages, 293 files and 17.8 MB before the key figures showed, 8.0 s on a 2.5 MB/s line,
  and the same again on every reload and site switch. Now 1.4 MB and 1.4 s the first time,
  42 kB and 0.3 s on a reload, 0.4 s on a site switch. How:
  - **Compressed.** nginx gzips the app's code and data, and sends each data file's
    `.json.gz`, written beside it by every run, as it is. The helper's answers are never
    compressed (they can hold the session's CSRF token: BREACH).
  - **Kept by the browser.** The code is fetched at an address carrying its version (a hash
    of the code, on every import too) and kept a year; a new release is a new address. Data
    files are asked for again each time and answer 304 while unchanged. The page itself,
    `sites.json` and every helper route stay `no-store`. Every file still needs a session;
    the session check for the shared code is cheaper (a pass for 30 seconds after a full
    check, ended at sign-out).
  - **The big files when needed.** `not_found`, `pages`, `page_index` and `page_trends` load
    when a tab or card first needs them, never with the Overview. Those cards show their
    title and "Loading" meanwhile.
  - **Smaller copies for the app.** `data/slim/` holds `not_found`, `pages` and `page_index`
    without the parts the app never draws (each day's 404 rows, each page's day-by-day and
    breakdowns, sitemap date lists). Every row and value kept is the full file's, checked by
    the audit's own walk before the copy is written; the full files, API and MCP are
    unchanged (DATA-CONTRACT.md, "The app's slim copies").
  - **Code asked for at once** (modulepreload), and **scheduled jobs at a lower CPU
    priority** (`SKALD_JOB_NICE`, 10), so the dashboard comes first during a live run.
- **Why.** The owner, 2026-10-26: "when we open a new site, it is taking a lot of time ...
  you cannot wait five minutes for the overview to load."
- **Who / what to do.** Everyone, on the next upgrade; Docker installs: nothing. A
  self-hosted nginx made from DEPLOY.md: take the new `map $request_uri $skald_cache` and
  the `/traffic/` location's gzip and Cache-Control lines (DEPLOY.md, "Compression and
  caching"). A web server in front passes both through as they are. Rolling back below this
  release with the new nginx lines: delete the `*.json.gz` copies first.
- **Checked.** `tools/bench_load.py` (the figures above: a 3000-page sample, real nginx with
  the image's config behind HTTP/2, Chromium on a throttled line), `tests/test_nginx_cache.py`
  (the rules from DEPLOY.md, then a real nginx: gzip, HTTP/1.0 proxies, 304, Cache-Control per
  path, helper answers neither kept nor compressed), `tests/test_gzip_copies.py` (every copy is
  its file, atomic, removed when it would be stale), `tests/test_lazy_load.py` with
  `tests/js/lazy-load.mjs` (nothing big at open, each file once, every reader known),
  `tests/test_slim.py` (copies reconcile on a real run, the audit catches a changed, dropped,
  reordered or added value), `tests/test_auth_api.py` (the 30-second pass), the scheduler's
  nice, and the full suite with and without PyYAML.

### Many sites with your AI agent: one line each, two lines through MCP, and Search Console

- **Added.** Settings > Organisation > Sites > **Set up many sites with your AI agent**
  (`#settings/org/sites?lines=all`): every site with what is left on it, its own **Make its
  line**, **Make a line for each site** (one separate line per site), each site's line and watch,
  and **Add several sites** (up to 25 names, each with Add a site's checks and the plan's limit).
  Each site's **Two lines (MCP)** makes a token for that one site (`mcp` + `setup`) and shows
  line 1 for Claude Code (`claude mcp add ...`, kept to that folder) or Codex (its own
  `[mcp_servers.skald-<site>]`), and line 2, `Set up Skald for this site`. MCP `setup_line` no
  longer needs `site` with a one-site token. New `GET sites/agentleft`.
- **Added.** A `search` job: the agent finds the Search Console property and, with the user's
  yes, when Skald has no key and the line's maker is an install admin, makes a service account
  with gcloud and sends its key file to the new `POST /traffic-kit/<code>/searchkey` from the
  file (never the chat, never a log; never replaces a key). The one click (add the robot as a
  Restricted user) and Bing's key stay the user's. Checklist line 8, "Search Console connected"
  (optional), whose Set up opens This site > Leads & integrations > Search Console & Bing. The
  report's property is a recommendation with **Apply**.
- **Fixed.** The AI agent kit's rate limit counted per address only, so ten sessions on one
  laptop setting up ten sites shared 10 tries a minute and got "Too many tries". It now counts
  per address and code, with 120 a minute per address across codes.
- **Why.** The owner: "a user can be working on 10 sites ... i will give permission from 10
  sites separate". No code or token covers two sites.
- **Who / what to do.** Owners and admins. A self-hosted front nginx made from DEPLOY.md must
  widen the kit's POST location to `(report|hooksecret|searchkey)`; the Docker image's nginx has
  it. Nothing else.
- **Checked.** `tests/test_agent_many.py` (ten sites' lines used at once from one address, the
  searchkey route's refusals and its bash + curl command, the two lines' token),
  `tests/js/agent-many.mjs` (the view and its address), the checklist parity test, and the full
  suite.

### To-dos your AI agent fixes: one button, "Fix this"

- **Changed.** Each to-do on Overview > Insights has one main button, **Fix this**, in place of
  Download CSV, Copy link and Send to team. It asks **Who will do it?**: **My AI agent** (one
  line to paste into Claude Code, Codex or Cursor), **Me** (the exact nginx or Apache lines to
  paste, from every row, with the CSV as a small link) or **Someone else** (Send to team, or the
  link). **Fix all (N)** above the list asks the same for every open to-do. The link to a to-do
  is the copy icon by its title. The address keeps each choice
  (`todo=<id>&fix=1&fixby=agent|me|someone`, and `link=<id>` for the line being watched; never
  the line or its code).
- **Added.** The to-do line: `fix the Skald to-do "<title>" for <site> — read <address>/traffic-kit/llms.txt
  and use code <code> (works once, 24 hours)`. Its steps fetch every row of the to-do from Skald
  with curl into a 0600 file (new `GET /traffic-kit/<code>/todo/<id>`: paths and counts only;
  never the browser's files, which hold at most 1,000 rows), check first where the site keeps
  its redirects or rules (nginx, Apache, Next.js, vercel.json, Netlify, WordPress, Cloudflare),
  change only what is missing, ask before any server change, test with `nginx -t`, and report
  each to-do (new `POST /traffic-kit/<code>/fix`, up to 256 KiB): done, partly or left, the
  exact change, the rows left and why. The report shows in the dialog and on the to-do; "done"
  marks the to-do done, so Skald re-checks it on the days after. Marking done changes no figure
  and is undone with one click; that is the most a leaked line can do. One job per kind:
  todo-lost, todo-errors, todo-markdown, todo-sitemap, todo-leave. A new to-do line never ends a
  set-up line.
- **Added.** MCP tools `fix_todo` (every row and the steps; any token for the site) and
  `mark_todo_done` (the report and the mark; the setup scope for that one site, owner or
  admin; audit row `mcp.todo_done`). "Fix my Skald to-dos" now works with the MCP token alone.
- **Added.** New to-dos are said: "N new to-dos your AI agent can fix" above the list and in
  the summary mail (each to-do with a link that opens Fix this > My AI agent; never a code in a
  mail), and the outgoing webhook event `todo.new` (title, proof, figures, link; never a code or
  a row). `todos.json` gains `agent` and `first_seen`; every row is kept for the agents in
  `<history folder>/todo-rows/<site>.json` (0600).
- **Why.** The owner (26 Oct): give the to-do's data to the person's own AI agent so it can do
  all that is needed, with no download and no copy and paste; and one button that asks what
  you want, instead of a row of buttons. "Fix the lost pages", from opening Insights to the
  change made: before, 4 clicks (Open in Site > Not found, Download the nginx lines, back to Insights,
  Mark done) plus signing in to the server, editing nginx, `nginx -t` and a reload by hand; now
  3 clicks (Fix this, My AI agent, Copy), one paste into the agent and one "yes" to its server
  change. The mark is made by the agent's report.
- **Who / what to do.** Owners and admins make lines; anyone who may read the site sees the
  reports. A self-hosted front nginx made from DEPLOY.md needs the new
  `^/traffic-kit/<code>/fix$` location (POST, 256k); the Docker image's nginx has it. Nothing
  else.
- **Checked.** `tests/test_todo_agent.py` (the rows equal todos.py's full rows with
  `todos.json` cut to one row; the steps run as written under bash with curl, the key never on
  a command line; one line reads only its own site and to-dos; expiry and cancel answer 410;
  "done" marks and "left" does not; the MCP refusals and audit row; no code in a mail; the
  webhook body), `tests/js/todos.mjs` (the one button, Fix all, the dialog's three answers,
  the address round trip after a reload, cancel, the report on the card), the MCP and mail
  tests, and the full suite with and without PyYAML.

## 2.40.0 (2026-10-26)

Settings is rebuilt around what you came to do: a menu in five groups (This site, AI & API, Organisation, You, Help & docs), a page per task, and Help and Docs under every title; every old address still works. Each site has a menu to pause, remove, clear or delete it, with an archive written first. Hosted plans mail owners and admins at 80%, 90% and 100% of the month's requests. A site can keep everything: on internal and enterprise sites Skald deletes nothing by itself. Leads' names and emails follow the site's own People days on every other site.

### Upgrade

- **Read this before you upgrade if you set People days and want nothing cleared.** The first
  run on 2.40.0 clears the names and emails of leads older than a site's People days (the Fixed
  entry below). To keep everything, add `SKALD_KEEP_EVERYTHING=1` to the container's env file
  (or `retention.keep_everything: true` in config.yml) **before** the new container starts.
  A site with no People days set changes nothing.
- Bookmarks and links to old Settings addresses (`#settings/api`, `#settings/sitesadmin` and the
  rest) keep working: they open the new page, with their dialog.

### Settings: a menu by what you came to do, a page per task, Help and Docs on every page

- **Changed.** Settings has a menu of its own, in five groups: **This site** (Set-up checklist,
  Collect data, Site details, Leads & integrations, Internal traffic, Privacy & retention, Mail &
  reports, AI answers), **AI & API** (AI assistant (MCP), Read figures (API), Tokens & links),
  **Organisation** (Sites, Team, Users, Sign-in rules, Audit log, Billing & usage), **You** (Your
  account) and **Help & docs**. `#settings` opens **All settings**: the common tasks in plain
  words ("Connect an AI assistant", "Add, pause or delete a site", "Revoke a token") and every
  page with one line on what it is for. On a phone each page starts with a **Settings page**
  select, so the menu is one tap away. Long pages have tabs (Collect data: Send logs, Script tag
  & goals, What counts; Leads & integrations; Mail & reports; AI answers), each with its own
  address (`sub=`). The old Connections page is split by task: sending logs is under Collect
  data, MCP and the API have pages of their own, and every token and shared link is under Tokens
  & links.
- **Changed.** The MCP and API pages say how it works first, as four numbered steps, then one
  button. In the MCP dialog, by hand, one step holds it all in order: choose your assistant
  (Claude Code, Claude Desktop, ChatGPT through the API, other), make its token right there, then
  the command or config with the token already in it. The API dialog shows the curl command
  under the token it made. Each Test names the next step. The assistant chosen is in the address
  (`asst=`); the token never is.
- **Added.** Every settings page and tab has **Help** (its guide in the app) and **Docs** (the
  same guide on skaldanalytics.com/docs/, in a new tab, with the copy and open icons) under its
  title, and a **Next step** at its foot. A **Help & docs** page lists every guide, the public
  docs, the MCP and API pages, What's new and the contact page. Ctrl K (Cmd K) finds MCP, API,
  tokens, sites and Help & docs by those words.
- **Why.** The owner (26 Oct 2026): "every option in settings ... is super confusing and also
  not as per user flows ... the token was above the steps ... i could not find where the mcp
  was in ... the help and documents are not easy to access". The pages were a flat list of 15
  named by what they held, not by what people came to do.
- **Who.** Everyone who opens Settings. Nothing changes in what each setting does or who may
  change it.
- **Do.** Nothing. Every old address still works and opens the new page with its parameters:
  `#settings/api?conn=mcp` opens AI assistant (MCP) with its dialog, `#settings/sitesadmin?setup=new`
  Sites with the wizard, `#settings/account` Your account, and so on (docs/ROUTES.md lists
  them all). Links in mails sent before still land.
- **Checked.** A new node test (tests/js/settings-menu.mjs): the groups and their order, every
  page drawn with Help and Docs (copy and open icons), one title, the phone's select, Next step,
  each tab in the address, every old address opening its new home with its parameters. The
  connection, route and agent tests walk the new pages and the reordered MCP dialog (choose,
  token, command, then Test; the assistant in the address and gone on close). The help guides,
  mails, kit files and CLI words name the new pages. Screenshots before and after at 1440 and
  390 px, light and dark (docs/plans/settings-shots/), with no sideways scroll at 390 px. The
  full suite passes.

### Hosted plans: a mail at 80%, 90% and 100% of the month's requests

- **Added.** When an organisation's requests this month reach 80%, 90% and 100% of its plan's
  `requests_month`, its owners and admins get one mail each: "X of the Y requests its plan
  allows this month (Z%)", the day the count starts again, what happens past the limit (new log
  lines turned away; Skald's shipper keeps them and sends them again, a Cloudflare Worker's are
  lost) and an **Open Billing** button to Settings > Billing on that organisation's own
  dashboard. One mail per mark and month, never twice: each mark is written before the send
  (decision D93's rule), so a restart, a recount or a second run repeats nothing. A jump past
  two marks sends one mail, for the higher; a bigger plan in the month starts from its own marks
  not yet passed. From 80%, owners and admins also see a banner on every page with a link to
  `#settings/billing`; viewers see nothing. Settings > Billing shows the month's requests as a
  bar with the 80, 90 and 100 marks, and admins may now read Billing (only owners choose a plan
  or change the payment). Each alert is one `billing.usage_alert` row in the audit log, with the
  mark and the counts, never an address. `/me`'s plan usage gains `percent`, `mark` and
  `resets_on`. The check runs after every live run and run-daily, at most once per organisation
  every 5 minutes (run-daily always), never inside an ingest request. `saas.usage_alerts: false`
  switches the mails and the banner off.
- **Why.** The owner: "we also send alerts to upgrade your plan when you reach 80%, 90%, 100% so
  that your data is not lost". Past the limit the ingest answers 429, and nobody was warned
  before; a Cloudflare Worker's lines are lost then.
- **Who.** Hosted Skald (saas on) only: owners and admins of an organisation whose plan has a
  `requests_month`. Self-hosted installs (saas off) see no change, and no table is made.
- **Do.** Nothing: on by default with saas, through the install's own mail settings.
  `saas.usage_alerts: false` turns it off.
- **Checked.** New tests: each mark once, a jump past two, a new month, a bigger plan and one a
  little bigger, back to the old plan, a restart, a recount down and up, a failed send, saas
  off, the switch, no plan or no `requests_month`, unknown or withheld usage, viewers and
  unconfirmed or disabled accounts never mailed, the link on each organisation's own dashboard,
  one check per 5 minutes; over real HTTP, /me's new fields and Billing for an admin (read
  only); and the banner and bar drawn in node from those answers (tests/js/billing-usage.mjs).
  The full suite passes.

### Added: keep everything, for internal and enterprise sites

- **Added.** A site can keep everything: Skald then deletes and clears nothing by itself on it.
  It applies when the install says so (`retention.keep_everything: true`, Docker
  `SKALD_KEEP_EVERYTHING=1`), or, on a server that sells plans, when the site's organisation
  has no plan (the server's own) or its plan says `keep_everything: true` (Enterprise). Every
  automatic delete skips such a site: the history's journeys, returning-visitor codes, detail
  and AI fetches; visits with addresses and Security's scanner rows (by days, and when
  addresses are turned off or shortened); leads, removed rows, lead journeys, identities,
  deliveries, replay hashes and payment links; the hook spool; the People-days clearing of
  names and emails (the entry below); the outgoing webhooks' outbox; in-page event counts and
  the beacon spool; AI answers runs; closed alerts; the conversions file's backup copies;
  and the shipped raw logs, whose days past 14 move to the site's `archive/` folder instead of
  being deleted (about 11 MB a day for every site on our server). A person's own deletion request (`forget`, `conversions forget`), run by an admin,
  still works. Settings > Data retention and its People card say "Kept: nothing is deleted
  (internal or enterprise).", a shorter window's preview says nothing is removed, the privacy
  notice wording says "until you ask us to delete it", and `ti.py doctor` shows "Keep
  everything: on". **Why:** the owner's rule of 2026-10-26: "all our projects that we have on
  live are internal and enterprise, nothing gets deleted on that". **Who:** our server (every
  site on it, once `SKALD_KEEP_EVERYTHING=1` is in its env file) and Enterprise plans; a
  customer plan's sites and every other install are pruned as before. **Do:** on our server,
  add `SKALD_KEEP_EVERYTHING=1` to the env file at the upgrade that ships this, before the
  container starts, so the People-days sweep below never runs there; give an Enterprise plan
  `keep_everything: true`. The history's own backups (copies, not data) still rotate. **Checked:** `tests/test_keep_everything.py`: every prune of the daily
  run on a keep-everything install leaves every table row and every file byte for byte as it
  was; the same install with the rule off is pruned; hosted, a site with no plan and an
  Enterprise site are untouched while a customer plan's site is pruned; the outbox, closed
  alerts, AI answers, conversions backups and the People-days sweep each kept and, with the
  rule off, cleared; `tests/test_ingest.py`: a raw log past its 14 days lands in `archive/`,
  whole, outside run-daily's files; the notice, the env var and the plan flag.

### Fixed: leads' names and emails kept past the site's own promise

- **Fixed.** A site sets in Settings > Data retention > People how many days it keeps what
  names a person (**Visits with addresses**, `privacy.keep_days`). That number covered only the
  visits with IP addresses. A lead's name and email lived as long as the lead: 400 days, or for
  good. Now, when a site has set its People days and they are shorter than the leads, a name
  and email are kept that many days. Then they are cleared from every place Skald keeps them:
  the lead's identity, the leads a sync removed, the copy of each hook message, and the copies
  a schema upgrade keeps (`conversions/people_days.py`). The lead stays, counted, without them.
  If the same person sent a newer form, the newer lead keeps the email; the older leads lose
  it. A start and its finish within the abandonment window stay linked, so no lead ever
  becomes "abandoned". The privacy notice wording now says it: "We keep them for 180 days.
  After that we keep the form or booking without your name and email, ...". **Why:** the
  2026-10-26 security review: docomatic.ai promises 180 days, and its emails were kept for
  good. **Who:** sites that keep names and emails and set People days shorter than their
  leads. A site that never set People days keeps today's rule: the code's 395 is not a
  promise. A site that keeps everything (the entry above) is never cleared: on our server,
  where docomatic.ai promises 180 days and two more sites 365, nothing is cleared once
  `SKALD_KEEP_EVERYTHING=1` is set.
  **Do:** nothing. The first live run after the upgrade clears what is already past the
  promise, then the nightly run each day. Each site's counts go to the run's output,
  `privacy.log` and the audit log (`privacy.cleared`), never a name or an email. A site whose
  notice promises a number of days should set it under People. **Checked:**
  `tests/test_people_days.py` (old rows lose name and email, young keep them; a person with a
  new and an old lead; a start chained to its finish across the edge; removed rows, spool lines
  and upgrade copies; no change without a shorter promise; once after the upgrade; the
  command's counts never show an email). `conversions.json` for April and today, the second
  count included, and the abandoned starts are the same before and after; with the chain
  turned off the test sees a lead turn "abandoned", so the check is real.

### Pause, remove, clear or delete a site from the dashboard

- **Added.** Each site in Settings > Add or remove sites has a ⋯ menu: **Pause** and
  **Resume** (an owner or an admin), **Remove** and **Restore**, **Clear data** and **Delete
  all data** (an owner). Each opens a dialog that says what happens, what stays and how to
  undo it; the dialog is in the address (`sact=<act>.<site>`). Pause comes first and deletes
  nothing: the log endpoint answers 503 with Retry-After, so the shipper keeps its lines, and
  the daily and live runs skip the site; the site shows "Paused since". Resume says how many
  days were missed and whether the log can still fill them (a shipper kept its lines, a log
  drain did not, a local log holds days from a date). Removed sites are listed apart, with
  Restore. Clear data and Delete all data need the site's name typed and a box ticked; before
  deleting anything they write one archive of everything that goes into the install's backups
  folder, kept 30 days, and show its path. Clear data keeps the site, its settings and its
  tokens; the days before it read Not recorded and are never counted again. Delete all data
  also deletes settings, set-up links and the logo, and revokes the site's tokens; a site from
  the server's config file keeps its config entry and becomes Removed. All of this works for
  config-file sites too (the install's main site can only be paused). One audit row per
  action (the site, who, the archive's name). New commands: `ti.py site pause|resume|restore|
  clear`; `site remove` and `site purge` now work on config-file sites and `purge` on an
  active site, both still with `--yes`. **Fixed.** A purge left the site's page-group rows
  (`<site>::<view>`) in the history, its AI answers, its security items, its set-up links and
  its Search sync state; it now takes every one (`site_data.py` lists each store).
  **Why:** the owner found no way to delete a website he had added, or to clear its data.
  **Who:** owners and admins of every install. **Do:** nothing. **Checked:**
  tests/test_site_lifecycle.py (pause stops ingest and the runs, resume restarts them, remove
  and restore, purge writes the archive then empties every store, clear keeps settings and
  tokens, roles, the typed name and the tick, config-file sites, audit rows, paused and cleared
  days read Not recorded), tests/js/site-actions.mjs (the menu per role, the dialog's words,
  the address, nothing posted until the name is typed and the box ticked), and the full suite.

## 2.39.0 (2026-10-26)

Your AI agent can now do every set-up job, not only a new site's. Each Set up dialog asks **Your AI agent, or by hand?**, the set-up list offers **Set up everything left with your AI agent**, and your assistant can ask Skald over MCP what is left and make the line itself. Also: the agent's findings for Skald's own settings wait for your **Apply**; a tie in a list's "(all others)" cut no longer withholds a day; a quiet site no longer shows a false "no page assets".

### Upgrade

- Nothing to do on the Docker image. A self-hosted install with its **own front nginx that allows only GET** under `/traffic-kit/` must also allow POST to `.../hooksecret`, as it already does for `.../report` (DEPLOY.md, the regex `(report|hooksecret)`). A front nginx that only proxies needs nothing.

### Your AI agent, in every set-up job

- **Added.** The one line for an AI agent works for each set-up job of a site already in Skald:
  connect the logs, add the script tag, leads and tool webhooks, the Next.js log field, find the
  page assets, check the privacy settings, and connect the AI assistant (MCP). Every Set up
  dialog an agent can do (logs, page assets, Next.js pages, script tag, lead hook, privacy, and
  Connect an AI assistant) opens on **Your AI agent, or by hand?**; by hand is the old dialog,
  one step later. Countries and mail stay by hand. **Why:** the owner pointed out that the lead
  set-up (`?setup=lead`) walked a person through by hand while Add a site did it all through one
  line. **Who:** owners and admins. **Do:** nothing. **Checked:** `tests/js/agent-jobs.mjs` and the
  checklist and connections tests; the default Add a site line, keys and steps are byte for byte
  as before.
- **Added.** **Set up everything left with your AI agent** at the top of a site's Set up list,
  when two or more open lines are agent jobs: one line for all of them. Its address is
  `setup=all&jobs=...`. **Checked:** `agent-jobs.mjs` (jobs in order, the address round trip).
- **Changed.** A line makes only the keys its jobs need: a sending token only with logs, the lead
  secret only with leads, a read-only token for that one site only with MCP. Cancelling, expiry
  or a new line revokes every token the line made. **Checked:** endpoint tests on cancel, expiry,
  a revoke that failed once, and the daily run.
- **Changed.** The agent's steps give each job its own section, each starting with **Check
  first**: the agent leaves done work alone, changes only what is missing, and asks before any
  server or web-server change. Keys still go only into a 0600 file through curl or wget.
- **Added.** `POST /traffic-kit/<code>/hooksecret` lets the agent set a booking, form or payment
  tool's webhook secret (Calendly, Cal.com, Typeform, Stripe, HubSpot, Zapier) without the
  secret passing through the chat: Skald makes one and hands it once into a file, or takes the
  tool's own from stdin. A tool that has a secret already is left alone unless replacing is
  asked. Audited, never logged. **Checked:** tests run the steps' own commands with bash and curl.
- **Added.** The agent's report says which jobs it did ("done", "already there", "skipped",
  "left for you") and which tool hooks it set. Page assets and privacy show as recommendations
  with **Apply**, which makes the same save as the by-hand dialogs. **Why:** a leaked code must
  never change what Skald keeps; Skald changes its own settings only on your press. **Checked:**
  nothing is saved before the press; the exact save bodies after.
- **Changed.** Connect an AI assistant (MCP) has **Read the MCP guide** at the top. **Why:** the
  owner found no documentation link there.

### MCP: what is left to set up, and the line to do it

- **Added.** `setup_left`: a site's open set-up lines, each with the job an agent can do and
  its dialog's address. Worked out on the server (`setup_items.py`), held to the page's own
  checklist by a test that runs both on 22 sets of answers.
- **Added.** `setup_line`: makes the same one-time line as the dashboard's **Your AI agent**, for
  the jobs given, audited (never the code). It needs a token with the new permission
  **Set-up lines (AI agent)** (scope `setup`): only an owner or admin may make it, for exactly
  one site, together with AI assistant (MCP); it reads nothing by itself, and stops if its maker
  is demoted. **Do:** make such a token only if you want your assistant to start set-ups.
  **Checked:** `tests/test_mcp_setup.py` (every refusal, the audit row, a real line end to end).
- **Fixed.** The MCP server reads each site's own config for set-up answers, not the main
  site's.

### Fixed: a tie at the "(all others)" cut withheld a live panel

- **Fixed.** A list that ends in "(all others)" keeps the pages with the most visits. When
  several pages had the same count at the cut, it kept whichever it had counted first. The
  visits and the readers count in a different order, so the two lists could keep different
  pages, the check "visits by entries match readers by landing" failed, and the figures were
  withheld. Now, at an equal count, the first by name is kept, whatever order the lines came in
  (`dimensions.fold`; rule added to DATA-CONTRACT.md, Counters). **Why:** one site's live panel
  was withheld on 26 Oct (19 landing pages with one reader each, the cut inside them). **Who:**
  every site; a day or live panel could be withheld. **Do:** nothing: no stored day was withheld
  for this, nothing needs recounting. **Checked:** `tests/test_landing_ties.py` rebuilds the case
  (failed before, passes now); the day's real lines, read on the server without writing, verify
  clean with the new rule; the audit road does not fold and is unchanged.

### Fixed: a quiet site's "no page assets" false alarm

- **Fixed.** The doctor's Page assets line read only the log's last 512 KB. On a quiet site
  those can all be crawler lines, so it said "no request for /_next/static/" while people loaded
  the pages all day, and the set-up checklist offered a wrong to-do ("none counts as a person
  yet"). With nothing in the tail it now reads further back, the live file and its first
  rotation, 64 MB at most, and says "seen in the log (not in its last lines: a quiet spell)"
  (`doctor.py`). **Why:** docomatic.ai showed the false alarm. **Who:** quiet sites with the
  page-assets rule. **Do:** nothing. **Checked:** `tests/test_doctor.py` (an asset request before
  512 KB of other lines is found; the 64 MB cap holds).
