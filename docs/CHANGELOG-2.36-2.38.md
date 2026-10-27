# Changelog: 2.36.0 to 2.38.0

The releases of 25 and 26 October 2026. Newer ones: [CHANGELOG-2.39-2.41.md](CHANGELOG-2.39-2.41.md) and [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.35.md](CHANGELOG-2.35.md).

## 2.38.0 (2026-10-26)

In two organisations? The site switcher, All sites and the Team page now say which organisation each site and each team belongs to. Also: a 410 gone counts as handled and a redirect anywhere as fixed; the Setup button on All sites is bright and continues at the step you reached; moving a site to another organisation takes its settings, set-up progress and own tokens along; and visitor IDs off now keeps no ID from a booking, form or payment tool's webhook either.

### Upgrade

- Nothing to do.

### Sites and teams grouped by organisation

- **Added.** For a person in two or more organisations, the sidebar's site switcher lists the
  sites under each organisation's name, and **All sites** groups its cards the same way, each
  heading with its number of sites. A person in one organisation sees the plain list as before.
  `sites.json` from the helper names each site's `org` only then (`helper_sessions.org_names`;
  `access.session_caller` gives the caller's organisations). **Why:** the owner gave a business
  partner one site in its own organisation and, being in both, could not tell from the dashboard
  which team was which. **Who:** anyone in more than one organisation. **Do:** nothing.
  **Checked:** `tests/test_org_grouping.py` (one organisation: no names, no headings; two: each
  site named, two headed groups in order, and the other organisation's own owner sees nothing of
  the first; "Other sites" last); a sandbox with two organisations in a browser, desktop and
  390 px wide (no sideways scroll).
- **Changed.** **Settings > Team** is titled with the organisation ("Team of Kiwi"), says which
  sites the team sees ("These people see kiwi.example only.") and links to your other
  organisations' teams. The team answer adds `sites` and `others` (`team_api.py`). **Checked:**
  `tests/test_team_api.py` (the sites, and the other team seen from both sides).
- **Docs.** The help's Sign-in and team guide has "Several organisations" and "Give someone one
  site only"; docs/ACCOUNTS.md and docs/CLI.md say what `site assign` does with tokens.

### A 410 gone counts as handled; a redirect anywhere counts as fixed

- **Changed.** Site > Not found and the to-dos counted a 410 as "not found", like a 404, so an
  address answered "410 gone" on purpose (the to-do's own advice) kept coming back as lost
  traffic. Now only a 404 is an ask: a 410 is counted in the address's answers only, and an
  address that answered 410 on or after the last day it answered 404 is handled and leaves the
  lost pages and the sitemap addresses. The re-check of a done to-do and **After the fix** count
  404s only, so a redirect, to the site or to another one, counts as fixed. Both roads changed
  apart (`lost_pages.py`, `audit_todos.py`). **Why:** one site sent 64 old pages to another
  site, 8 to its own pages and answered 410 for 80 on 26 Oct; the 410s would have stayed "lost".
  **Who:** every site with Site > Not found. **Do:** nothing; an address you redirected stays on
  Lost pages until its last 404 is older than the 30-day window, while its re-check already says
  fixed. **Checked:** `tests/test_todos.py` (a 404 then a 410: handled; a 410 then a 404: lost,
  with the 404s only; 410 only: never listed; a sitemap address answering 410: no to-do; the
  re-check after the mark counts only the address still answering 404; a redirected address
  marked fixed says fixed; the second count agrees); the tests fail on the old code.

### Fixed: moving a site took its log shipper's access away

- **Fixed.** A token reads only its own organisation's sites, so `skald site assign` to another
  organisation cut off the tokens made for that site alone, such as its log shipper. They now
  move with the site, each with a `token.move` audit row; a token for several sites, or for all
  of the old organisation's, stays (`accounts/orgs.py`). **Why:** on skaldanalytics.com,
  kiwiform.com was moved to its own organisation on 26 Oct and its log token stopped working
  until it was moved by hand. **Who:** anyone moving a site between organisations. **Do:**
  nothing. **Checked:** `tests/test_accounts_orgs.py` (the site's own token works after the move,
  a two-site token and an all-sites token do not read the moved site, the same organisation
  again moves nothing); the test fails on the old code.
- **Fixed.** The move also left the site's settings and its set-up progress in the old
  organisation. The old organisation's Settings > Add or remove sites still listed the site, and
  its wizard said "Your progress was not saved: There is no such site in this organisation". Both
  now move with the site, each with a `site.move` audit row. They move even when the site is
  already in that organisation, so running `skald site assign` again mends a site moved before
  2.38.0 (`accounts/orgs.py`). **Who:** anyone who moved a site made from the dashboard. **Do:**
  for a site moved before 2.38.0, run `skald site assign SITE --org SLUG` once more. **Checked:**
  `tests/test_accounts_orgs.py` (settings and progress listed and saved in the new organisation,
  refused in the old one; a move made the old way mended by assigning again).

### Fixed: the site picker's Setup button started over at step 1

- **Fixed.** **Setup: step 4 of 5, continue** under a site's card on All sites opened the wizard
  at step 1, not the step reached. It also opened the wizard inside the first site you administer,
  so a site of another organisation could not save its progress. Now the button opens the wizard
  at the saved step, inside the site's own dashboard or another dashboard of its organisation. With
  no dashboard of that organisation drawn yet, there is no button; the card leads to the site's
  waiting page (`helper_sessions.py`, `setup_page.app_for`, `js/tabs/sitesadmin.js`
  `openSiteKey`). **Why:** the owner pressed it for kiwiform.com on 26 Oct and was sent to step 1
  with "Your progress was not saved". **Who:** owners and admins with a set-up left half way.
  **Do:** nothing. **Checked:** `tests/test_site_setup.py` (the link names the site's own
  dashboard, never another organisation's, and the wizard saves there); `tests/js/connections.mjs`
  (a link with no step opens the saved step 3).
- **Changed.** The button is now bright blue with an arrow, so it reads as the next thing to do,
  not as a grey note under the card. **Checked:** a sample page in a browser, light and dark.

### Privacy: visitor IDs off now means no ID in a tool's webhook either

- **Fixed.** With a site's visitor IDs off, the hook receiver dropped the `vid` key, but a tool's
  own field for the ID was still written to the hook spool, which is kept 400 days: Typeform's
  `hidden.skv`, Cal.com's `metadata.skv` or `utm_content`, Calendly's `tracking.utm_content`,
  Stripe's `client_reference_id` and HubSpot's `skv` property. The store row was right (no ID);
  the spool line was not. Now every value that is a Skald ID goes, at any depth, and so does a
  Skald ID inside a longer text, such as a landing address's `?skv=`
  (`conversions/hooks.py`, `without_vid`). **Why:** found in the security review of
  26 Oct 2026; visitor IDs off is a promise that no ID is kept. **Who:** a self-hosted install
  with visitor IDs off that takes Typeform, Cal.com, Calendly, Stripe or HubSpot webhooks.
  **Do:** nothing after upgrading; spool lines written before it keep what they had until the
  spool drops them. **Checked:** `tests/test_conversions_hooks.py` posts each tool's sample with
  IDs off (no `skv_` in the spool, no ID in the store) and a lead whose landing address carries
  one; the new tests fail on the old code. With IDs on, Stripe's reference still reaches the
  store. Live (skaldanalytics.com, 26 Oct, counts only): the spool has lines from `lead` hooks
  only; the sites with IDs off have 0 lines holding an ID, so nothing kept there needs
  cleaning.

## 2.37.0 (2026-10-25)

Ask your AI assistant what to fix: six read-only MCP tools for the to-dos, lost pages, page changes, AI readiness and what changed. Also: the live visitor count readable again, a command reference, docs that match 2.36, and release notes on every GitHub release.

### Upgrade

- Nothing to do. The MCP server lists the new tools by itself; an assistant connected before sees them after it reconnects.

### MCP: six read-only tools for what to fix and whether it worked

- **Added.** The MCP server answers what 2.35's screens show: `what_changed` (Summary's "What
  changed: is it working?": sources and landing pages against the period before, only when both
  periods are whole), `todos` (Insights' to-do list with each to-do's state: to do, marked done
  with its re-check, or not now; `id` gives one to-do's rows), `lost_pages` (Site › Not found:
  old addresses, the closest live page, the nginx or Apache line; the Markdown copies AI asked
  for; the addresses marked fixed), `page_changes` (each marked change and the before/after
  verdict of every measure), `ai_readiness` (Pages AI can't read well, or one page's robots.txt
  per AI crawler, what AI got back, the Markdown copy, the sitemap and the last AI read) and
  `changed_pages` (New and updated pages: are they getting found?). They read todos.json,
  lost_pages.json, page_changes.json, ai_ready.json, page_trends.json, overview.json and
  breakdowns.json as the page does and count nothing again; a figure withheld or not recorded is
  named and null, never 0. The same token rules as every tool: the `mcp` scope, the sites the
  token may read, no address. **Why:** the read-only API already served these files, but an AI
  assistant asked "what should we fix?" or "did my change work?" had no tool for them. **Who:**
  anyone with an MCP token. **Do:** nothing; an assistant sees the new tools on its next
  `tools/list`. **Checked:** `tests/test_mcp_insights.py` (each tool on hand-made files in the
  builders' shapes: compared only over whole periods, the not-measured period, lists that do not
  add up withheld, withheld to-dos and lost pages named, a path with or without its slash,
  robots.txt not known without a copy, a site the caller may not read refused by every new tool);
  the protocol and transport tests list 20 tools; every tool run over a freshly built demo.
- **Docs.** docs/MCP.md, the MCP and API help guides, docs/API.md (every data file the API
  serves, among them todos, lost_pages, page_changes, ai_ready and page_trends, and the Real
  time route), LEADS-REFERENCE.md and the README name the 20 tools.

### GitHub page: 2.36 in the README, 39 screenshots retaken and 2 new; the live visitor count shows full size again

- **Changed.** The public README names 2.36 (one summary mail a day, the HTML sitemap page not a
  page) in What's new and the feature list, and the gallery gains two images: Site › Data quality
  with "Not counted as pages" (`data-quality.png`) and the daily summary mail (`summary-mail.png`,
  the real `summary-mail --dry-run` text of the sample install). 39 older images, most from the
  2.22 demo, were retaken from the current build: Security › Alerts now shows "In the daily
  summary" or "Right away"; Traffic › Sources shows the Social network tab and Direct, likely.
  **Why:** the images showed version 2.22 and screens that have changed since.
- **Changed.** The demo's sample traffic has an HTML sitemap page (`/sitemap/`), walked by
  Googlebot, bingbot, a weekly SEO site audit and now and then a test browser, from a generator of
  its own, so every other figure stays the same and Data quality has something to show.
- **Fixed.** Overview, today: the number of visitors on the site now showed as a small grey dot
  since 2.35.0, because the to-do number's style (`.td-n` in `todos.css`) also matched the live
  count. It is now kept to the to-do cards. **Who:** everyone looking at today's Overview.
  **Do:** nothing.
- **Checked.** `tests/test_demo.py` (the sitemap page is walked and shows in Data quality, never in
  Pages; the rest of the traffic unchanged); the full test suite passes; every new image looked at
  against the README's text, sample data only (RFC 5737 addresses, example.com).

### Docs: a command reference, and every Docker setting

- **Added.** docs/CLI.md lists every command and every argument, written from the command
  parser itself, so it cannot fall behind: a test fails when a command or a flag is added
  without it. The README's command list gained the commands it left out (`summary-mail`,
  `settings`, `ours`, `search`, `reports`, `ai-answers`, `stack`, `views`). docs/INSTALL.md now
  names every environment setting the Docker image reads, among them `SKALD_SCHEDULE_TZ`,
  `SKALD_MAIL_FROM` and `SKALD_CONFIG`, and lists the scheduler's jobs with their times
  (the daily summary at `SKALD_SUMMARY_AT` among them). **Why:** about twenty commands and flags,
  and several Docker settings, were written down nowhere but the code. **Who:** anyone who runs
  Skald. **Do:** nothing. **Checked:** `tests/test_cli_reference.py` (every command and argument
  of the parser is in its section; the file is what the tool writes); each setting checked
  against the entrypoint and the scheduler.

### Docs: the data contracts match 2.36

- **Fixed.** The not-a-page entry `sitemap_page` (2.36) was missing from the Requests feed's
  `not_page` values and from the `site.not_pages_off` setting's list, and the counting-traps
  page still said an HTML sitemap page stays a page. The set-up routes table gained
  `sites/detect`, `sites/tagcheck` and `sites/trylog` (Test a sample: what it takes, what its
  report holds, its limits). The to-do contract gained the helper's `settings/todos` and
  `settings/todo-send` routes. The advisories list's `also_known_as` and `firewall_notes`
  fields are described. The `arw` address key named a "redirects" filter the page does not
  have; it is "slow". The Not found help called the download button "Download the lines"; the
  page says "Download the nginx lines" (or Apache). The comparison's notes on 404s, email alerts
  and chart markers now name Lost pages, the security and sale alerts with the daily summary,
  and marked page changes. **Why:** these docs had fallen behind 2.35 and 2.36. **Who:** anyone who
  reads the files or calls the routes. **Do:** nothing. **Checked:** every field of a freshly
  built demo's data files looked up in its contract; every setting key in the settings
  reference; each route against its code.

### GitHub releases carry their notes

- **Changed.** Every GitHub release page said only "See CHANGELOG.md for what changed." The
  release workflow now writes the version's own changelog section into its release, with a link
  to the full notes; the 58 existing releases (2.0.0 to 2.36.1) were filled the same way, once,
  by hand. **Why:** the owner asked for the release notes on GitHub. **Do:** nothing.
  **Checked:** the workflow's step run on the changelog gives 2.36.1's section; each release
  page read back after the edit.

## 2.36.1 (2026-10-25)

A fix found by the dry run of the first summary mail on the live server.

### Mail links open the site they are about

- **Fixed.** In an install with several sites, a site that sets no `dashboard.url` of its own
  took the first site's, so every link in its mails (the security alerts, the daily summary,
  the daily and weekly reports, alert mails, a to-do sent to a teammate) opened the first
  site's dashboard. Each site now gets the first site's address with its own name in place of
  the first site's last segment (`.../traffic/example.com/` becomes `.../traffic/example.org/`).
  A site with its own `dashboard.url` keeps it; an address that does not end with the first
  site's name is left as it is.
- **Why.** The dry run of the 2.36.0 summary showed every site's links opening the first site.
  The 2.35.0 security mails had the same wrong links.
- **Who.** Installs with more than one site. **Do:** nothing.
- **Checked.** New tests (inherited, own, other shapes, the first site unchanged); the full
  test suite passes; `summary-mail --dry-run` on the live server after the upgrade.

## 2.36.0 (2026-10-25)

One summary mail a day instead of a mail per security item, and the HTML sitemap page out of the page views.

### Upgrade

- Docker: nothing; the scheduler sends the summary at 01:00 (`SKALD_SUMMARY_AT`). Without Docker: add the hourly `summary-mail --after 01:00` cron line (DEPLOY.md section 5).
- Recount the stored days so the sitemap page leaves them: `backfill --days 14 --force`, then `audit --day D --withhold` for each day.

### Counting: an HTML sitemap page is not a page any more

- **Changed.** `/sitemap/`, `/site-map/`, `/html-sitemap/` and `/sitemap.html` joined the
  not-a-page list as `sitemap_page`, ticked by default on every site. Its visits stay in the
  log's requests, in the same group, and show in Site health > Data quality under "Not
  counted as pages"; they leave the page views, readers, landings, exits and journeys.
- **Why.** The owner saw `/sitemap/` among one client site's people's pages: "a user never
  looks at" it. That day's log had 45 requests for it: Googlebot, PetalBot, Amazonbot, an SEO
  site audit, a "research-check" tool and four browser signatures with no referrer. The last
  four were counted as people. 2.35.0 had kept the HTML sitemap page as a page on purpose; this
  reverses that call.
- **Who it affects.** Every site with an HTML sitemap page. A site that wants it counted again
  unticks `sitemap_page` in Settings > Sites > Not pages.
- **What to do.** Nothing. Stored days keep their figures until recounted
  (`backfill --days N --force`); the live server is recounted at deploy.
- **Checked.** Tests on both counting roads (the audit matches the same list by its own code):
  matches, near misses (`/sitemaps-guide/`, `/sitemap/page-2/`, `/my-sitemap/`) and the
  made-up sitemap of 400+ paths, which still matches nothing.

### One summary mail a day per person, at 01:00, instead of one security mail per item

- **Changed.** Each person's security mail now comes by default in a daily summary: one mail
  per person a day at 01:00 in the schedule's time zone, covering every site they get security
  alerts for, with a section per site (only sites with something open): the open security
  items (marked New the first time, then "still open"), the open to-dos from Overview ›
  Insights (less the ones marked done or "not now"), and the set-up problems the doctor finds
  from local files (the daily run, days stored, the access log, the script tag, hooks, crawler
  checks, the disk). At most 10 lines per part and site, then a link to the rest; each line says
  what it is, what to do and links straight to it. No mail when nothing is open; never two the
  same day (each send is recorded, a failed one is retried by the next run). At 01:00 the to-dos
  are the ones the last daily run found; the security items are current from the live runs.
  A new command `summary-mail` (`--dry-run` prints the mails; `--after HH:MM` for an hourly
  cron line); Docker runs it at `SKALD_SUMMARY_AT` (default `01:00`, `off` stops it).
- **Changed.** "Right away" stays as a person's own choice, but one run now sends ONE mail per
  person with every item due on all their sites, never one mail per item. The morning run's
  separate security mail step no longer mails anyone; it only keeps the open items up to date.
  Security › Alerts, "Your security alerts", now offers "In the daily summary" (first, the
  default) or "Right away", and says what each sends.
- **Why:** on 2026-10-25 one person got 44 security mails in a minute: the first run after a
  fix sent every open item, one mail per item and per site, across 6 sites.
- **Who:** everyone on a site's team with security alerts on (owners and admins by default).
  Someone who had saved "Right away" keeps it, now batched.
- **Do:** nothing on Docker (the scheduler runs it). Without Docker, add the hourly
  `summary-mail --after 01:00` cron line (DEPLOY.md section 5; `install.sh` now writes it).
  To keep a mail per run, choose "Right away" on Security › Alerts.
- **Checked:** new tests for one mail per person across several sites and organisations,
  nothing sent when nothing is open, not sent twice the same day, a failed send retried, the
  10-line limit, the doctor lines read without any network call, right away batched into one
  mail, the old daily step mailing nobody, and the scheduler's job time and `off`; the
  existing security alert tests updated; the full test suite passes.
