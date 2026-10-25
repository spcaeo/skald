# Changelog: 2.27.0 to 2.31.1

The releases of 22 to 24 October 2026. Newer ones: [CHANGELOG-2.32-2.34.md](CHANGELOG-2.32-2.34.md) and [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.23-2.26.md](CHANGELOG-2.23-2.26.md).

## 2.31.1 (2026-10-24)

### Fixed: a site's own page about WordPress counted as a probe

- **What changed:** the bare path words `wordpress` and `wp` mark a WordPress probe only at the
  start of the path (`/wordpress/`, `//wp/wp-includes/...`, as scanners send them). WordPress's own
  names (`wp-admin`, `wp-login`, `wp-content`, `wp-includes`, `wp-json`, `wp-config`, `xmlrpc`)
  still mark one anywhere. Same rule in the classifier and in Security's categories.
- **Why:** skaldanalytics.com's new page `/integrations/wordpress/` (about the WordPress plugin)
  was read as a probe: its readers' page views left the counts, and Security mailed "Possible
  exposure ... answered 200 (45,715 bytes)" for it, an hour after the page went live.
- **Who:** sites with a page whose path has a `wordpress` or `wp` segment after the first
  (`/blog/category/wordpress/`).
- **Do:** nothing. Close the alert in Security if it is still open.
- **Checked:** a new test (`tests/test_wordpress_pages.py`: 6 pages are not probes, 12 scanner
  paths still are); the full suite; a scan of every kept log on Skald's own server (68 files,
  8 sites): the fix moves exactly one request, today's read of that page, so no day needs a
  recount.

## 2.31.0 (2026-10-24)

Add a site gives one line to paste into your AI agent. The line holds a one-time code, never a
key; the agent takes the keys once, connects the site and reports back while you watch.

### Added: one line for your AI agent sets up a site

- **What changed:** Add a site's step 3 is now **Your AI agent** ("Which AI agent are you
  using?": Claude Code, Codex, Cursor, Claude.ai or ChatGPT, Another agent). Step 4 shows one
  line to paste into the agent: `set up Skald for <site> — read <your Skald>/traffic-kit/llms.txt
  and use code <code> (works once, 24 hours)`. The agent reads the site's steps, takes the
  keys once with curl into a 0600 file (a new sending token, ingest only for that site, and the
  site's lead secret, copied when it has one), connects the logs, adds the script tag and the
  lead file, asks the privacy question, and sends a short report. Step 5, **Watch it connect**,
  ticks each step and shows the report in plain words; the admin applies what fits ("Use these
  page assets"). The code is hidden until **Show code**. Under it, "Is it safe to paste this
  into a chat?" says what the code is. **Cancel this line** ends it at once, a new line cancels
  an older one whose keys were not taken yet, and step 5 says when the keys were taken. Skald keeps only the code's hash and
  the keys sealed with it. The keys answer only curl or Wget, and the agent fetches its steps
  with curl too, so a web reader or fetch tool cannot pass them into a chat. The keys file also
  holds a report key: the report needs it in the `X-Skald-Report-Key` header (403 without), so
  only the agent that took the keys can send or replace it. The sending key can only send log lines; the lead secret sends leads and reads
  back the site's lead list (reference, stage, time; no personal details). After the keys are
  taken, the steps, installer, lead files and report keep answering until the expiry (no
  secret in any). Chat-only agents get the one command instead. **No AI agent: set it up by hand**
  keeps the old steps. Connections has **Set up with your AI agent** for a site that exists.
  New routes: `/traffic-kit/llms.txt` and `/traffic-kit/<code>/steps`, `keys`, `install.sh`,
  `leads/<file>`, and `POST .../report`; dashboard calls `sites/agentlink`, `sites/agentstatus`
  and `sites/agentcancel`. The address keeps `agent=` and `link=` (a hash, never the code).
- **Why:** the owner: adding a site should be as easy as treg's onboarding, one line to paste
  into an agent. Unlike treg's long-lived token, Skald's line holds a one-time code.
- **Who:** owners and admins adding a site. Sites already sending need nothing.
- **Do:** self-hosters who run their own front nginx from DEPLOY.md's sample must take its new
  `location ^~ /traffic-kit/` block: the nested `location` for `/traffic-kit/<code>/report`
  (POST, 16 KiB), or the agent's report is refused, and `error_log stderr crit;`, or nginx's
  error log can hold the code. Then `nginx -t` and reload. Everyone else (the Docker image has
  both): nothing.
- **Checked:** the full suite, 2875 OK, with new tests (tests/test_kit_agent.py, 36;
  tests/js/agent-setup.mjs); a real curl run against the routes; the wizard walked in a sandbox,
  67 of 67 checks. A real Claude Code run on a local Docker test site passed all 7 checks, with
  the first log lines in about 2 minutes. That run found two problems, both fixed: a dry run
  with no token stopped, and the check script's probe showed as a refusal. An independent
  review found 8 problems, all fixed before release:
  - nginx's error log wrote the request line, code included;
  - anyone with the code could send or replace the report;
  - two lines made at the same moment cancelled each other;
  - step 4 restored from an address made a new line, cancelling the one already sent;
  - a repeated key fetch wiped the keys file;
  - a downgrade to an older image would hand out the agent's token as an install link;
  - a site value shaped like a placeholder broke the steps page;
  - a second report was not shown.

  Re-run after the fixes: a second real Claude Code run passed every check, with the first
  log lines in about 1 minute 19 seconds. Two lines made at once left one live, no code was in
  the container's logs, a report without its key got 403, and a second key fetch kept the keys.
  It found one more problem, fixed: Claude Code run from an allow list refuses to write a file
  with `>`, so step 8 now pipes the report key into `curl -H @-` and writes no header file.

  A second independent review of the fixes found five more, fixed before release: two
  lines made in the same instant could both stay live (each read the clock before the lock); a
  failed **Make the line** left no Try again button; step 3 could lose the keys if the agent
  skipped moving the file into place (the one fetch line now moves it only when it holds the
  keys); the check script's marker hid any refusal, not only the 401 it expects; and step 5
  kept asking when the organisation was read only (402). The reviewer's race probes now always
  end with one live line (30 runs of 8 at once). Left as known: nginx's own 403 and 413 pages on
  `/traffic-kit/` carry no `no-store` header (they hold no code); the step 8 report needs curl
  7.55 or newer (the steps say so).

## 2.30.0 (2026-10-23)

Connecting a site and its leads in one step: one command on the server (with or without Docker,
the token made for you), one file and one line for leads (or a WordPress plugin, or a plain key
for Zapier and form tools), and the whole set-up in one zip, by mail, that a person or Claude Code
can follow alone. Plus two fixes from a 24-hour review of the live server's logs.

### Added: one command connects a server's logs

- **What changed:** Send this site's visits to Skald (and Add a site) has one choice, "My own
  server (nginx or Apache)", for servers with or without Docker, and three steps instead of four.
  The Run step shows `curl -fsSL <your Skald>/traffic-kit/<code> | sudo bash`. Skald makes the
  sending token itself. The link works once, for 24 hours; Skald keeps only a hash of the code
  and the token sealed with it, so its disk never holds a usable token. A browser or a mail's
  link preview only sees the command and never uses the link up; a used link prints "This
  install link was used or has expired" and changes nothing. The new `/traffic-kit/` path is
  answered by the beacon helper (docker/nginx.conf has its route).
- **The installer** (one file, also **Download as one file**, `skald-install-<site>.sh`) uses
  Docker when the server has it, else a systemd service with Python 3.9 or newer (the shipper is
  inside the file). It finds the site's access log in nginx's or Apache's settings by itself and
  asks only when it cannot tell (`--log`, `--dry-run`, `--yes`). It leaves `skald-ship-check` and
  `skald-ship-uninstall` on the server. Running it again is safe and keeps the place in the log.
  The Test step starts by itself.
- **Why:** the owner: adding a site was "very long and confusing": four steps, a token to make by
  hand, a zip to copy, unzip and run, and a question for the log file.
- **Who:** owners and admins adding a site. Sites already sending need nothing. **Do:** nothing.
- **Checked:** tests/test_kit_server.py and tests/test_kit_link_pack.py; on a clean Ubuntu 24.04
  with systemd and nginx (two sites), the real command against a Skald built from this release:
  it picked the right site's log, installed without Docker, all lines arrived, the Test said
  Connected, a second run of the same command was refused with the message, a re-run of the
  installer kept its place, and uninstall removed everything. The Docker road checked by dry run.

### Added: send the whole set-up to someone, in one zip

- **What changed:** **Send set-up to someone** (top of a site's Set up list, and in the logs and
  leads dialogs) mails `skald-setup-<site>.zip` to up to 3 addresses through Skald's own mail, or
  downloads it. It holds START-HERE.md (every case step by step), CLAUDE.md and AGENTS.md (the
  same for an AI coding agent: "give the folder to Claude Code and say Set up Skald from
  CLAUDE.md"; keys only in environment variables, never in code or git), secrets.env, the
  installer, Cloudflare and Vercel/Netlify steps, the script tag, and the lead files. **Include
  the keys** (ticked by default) puts in the sending token and the site's lead secret (a new one
  when it has none); each pack is in the audit log, never its keys. 10 mails an hour per site.
  The Node lead file is `.cjs`, because Gmail refuses zips holding `.js` files.
- **Why:** the owner's clients use Claude Code: one zip it can follow alone.
- **Who:** owners and admins. **Do:** nothing; mailing needs mail set up (Settings > Mail).
- **Checked:** tests/test_kit_link_pack.py (contents with and without keys, the mail with its
  attachment, refused without mail, the limit); downloaded from the browser and opened.

### Added: leads in one file and one line, a WordPress plugin, and a plain key

- **What changed:** Connect your leads first says what the script tag already counts with no
  code (form sends, Calendly and Cal.com bookings, phone and email clicks). The secret is made by
  itself when the site has none (a set one is never replaced without the confirm). For the site's
  own backend: pick PHP, Node or Python, download one file (`skald-lead.php`, `skald-lead.cjs`,
  `skald_lead.py`), and call one function, e.g. `skald_lead("L-1001", "demo", $email)`; the file
  signs each lead, reads `SKALD_LEAD_SECRET` first, waits at most 3 seconds and never breaks the
  form. **WordPress forms**: a plugin (Plugins > Add New > Upload) that sends Contact Form 7,
  WPForms, Gravity Forms, Elementor Pro and Ninja Forms leads with no code. The `lead` and `json`
  hooks also take `Authorization: Bearer <secret>` when no signature is sent, so Zapier's plain
  webhook step and form plugins work without signing code; a wrong key is refused like a bad
  signature, and the header is never logged. New endpoint: `POST <page>/integrations/leadfile`.
- **Why:** the owner: connecting leads needed a developer to write signing code.
- **Who:** sites that send leads. Signed hooks work as before. **Do:** nothing.
- **Checked:** tests/test_hooks_plain_key.py, tests/test_lead_files.py (the Python helper's real
  request accepted by the receiver), tests/test_integrations_leadfile.py; `php -l`, `node --check`
  and each helper posting to a local receiver; a plain-key lead kept and a wrong key refused
  through nginx on a local build. The WordPress plugin was checked against stubbed WordPress
  hooks, not a real WordPress install.

### Changed: docs/INTEGRATIONS.md split

- Search Console, Bing and AI answers moved to docs/INTEGRATIONS-SEARCH.md (the file was over
  1000 lines). **Do:** nothing.

### Fixed: a visitor who left during the public stack check printed a traceback

- **What changed:** the beacon helper no longer prints a Python traceback when a visitor closes
  the page before its answer is sent (a broken pipe or a reset connection). Any other error still
  prints its traceback.
- **Why:** the 24-hour log review on 23 Oct found one in the live container's log at 05:04 UTC: a
  visitor left during the public stack check, which takes a few seconds. Nothing was lost; it
  only looked like a crash.
- **Who:** every install. **Do:** nothing.
- **Checked:** tests/test_beacon.py `VisitorLeft` (fails without the fix).

### Fixed: `doctor` gave a wrong fix for a site still waiting for its first log lines

- **What changed:** for a site added from the dashboard whose server has not sent a line yet,
  `doctor`'s Access log line says "none yet: the site waits for its first log lines" (OK), as
  its Daily run and Days stored lines already did. A site set up by hand with a missing log
  still needs attention.
- **Why:** on 23 Oct `doctor` said NEEDS ATTENTION for a site added the day before, with the fix
  "Set logs.base to the log's file name", which was wrong: nothing had been shipped yet.
- **Who:** installs with a newly added site. **Do:** nothing.
- **Checked:** tests/test_doctor.py `WaitingSite` (fails without the fix).

### Fixed: a test of the new installer passed only on machines without systemd

- **What changed:** the test "no Docker and no systemd says what to install" now runs the
  installer with a PATH that holds the system's own tools less `docker` and `systemctl`.
- **Why:** on 23 Oct GitHub's tests failed on every Python version: the Ubuntu test machine has
  a real `/usr/bin/systemctl`, so the installer rightly found systemd and the test's "neither"
  case never happened. The installer was right; the test was not sealed.
- **Who:** nobody using Skald; anyone running the tests on Linux. **Do:** nothing.
- **Checked:** the kit tests in a Linux container with a real `systemctl`: they fail without
  the fix and pass with it.

### Fixed: help, docs and page words still described the old zip kit

- **What changed:** the site check's reason says "so one command on that server sends its log"
  (was "the log shipper kit is the way"). The Common problems table, the refusal fixes and the
  shared link's page say `sudo skald-ship-check` and `sudo skald-ship-uninstall`, and an older
  zip kit's `check.sh` is still named. The help guides Connections and If a connection does
  not work, INGEST.md, SETTINGS.md (`sites/kit` takes `server`; `sites/link`, `sites/pack` and
  `sites/packmail` listed), HOSTING.md, INSTALL.md, ROUTES.md and ADD-A-CLIENT-SITE.md match the
  code. LEADS-REFERENCE.md said "next release" for nine things that shipped in 2.26.0; it now says
  "since 2.26.0". A broken link in DATA-CONTRACT-REALTIME.md is fixed. The public copy no longer
  carries a link to the private design folder in ROADMAP.md.
- **Why:** a check of every document after the 2.30.0 work found them still telling people to
  download a zip kit and run `sudo bash check.sh`, which the page no longer offers for a server.
- **Who:** anyone reading the help or the Connections dialogs. **Do:** nothing.
- **Checked:** the full test suite; a grep for check.sh, "install kit", "shipper kit" and "next
  release" across the docs and the page's code; every relative link in the public copy resolves.

### Fixed: a failed Test gave the old kit's advice for a set-up saved before 2.30

- **What changed:** for every server way, a Test that has not heard from the site says: run
  `sudo skald-ship-check` (or an older zip kit's `sudo bash check.sh`), then where to see what
  the shipper says.
- **Why:** a set-up saved with the old choice "docker" or "systemd" opened the new one-command
  step, but a failed Test still said "run check.sh from the kit", a file the one command does
  not leave.
- **Who:** sites whose set-up was started before 2.30. **Do:** nothing.
- **Checked:** tests/js/tag-check.mjs, for "docker", "systemd" and "server" (fails without the fix).

### Fixed: a developer's shared link for a server refused the zip kits under "Other ways"

- **What changed:** a shared set-up link for "My own server" gives the one file, and the zip
  kits with and without Docker under "Other ways".
- **Why:** the link took only the method it was made with, so those buttons answered "This link
  has no install kit."
- **Who:** developers sent a set-up link. **Do:** nothing.
- **Checked:** tests/test_share_links.py `test_a_server_link_gives_every_server_kit` (fails
  without the fix).

## 2.29.0 (2026-10-22)

Leads and the pages they read can be kept for good (Settings > Data retention > Leads), and the
pages of visitors who have not signed up yet up to 400 days; a site still waiting for its first
log lines is skipped by the live audit instead of reported as a mismatch.

### Fixed: the live audit said "does not match" for a site with no log lines yet

- **What changed:** `audit --live` says "audit skipped: live <day>: <site> has no log lines yet"
  when the live snapshot is empty and the recount finds no request either, and ends 0.
- **Why:** on 22 Oct a site added that afternoon, still waiting for its server to send logs, made
  the all-sites live audit read "THE RECOUNT DOES NOT MATCH THE SNAPSHOT"; both roads were empty.
- **Who:** installs with a newly added site. **Do:** nothing.
- **Checked:** tests/test_audit_recount.py (the test fails without the fix).

### Added: keep leads and the pages they read for good

- **What changed:** `conversions.retention_days` now takes `0` (or the word `forever`): kept for
  good. Skald's nightly prune then never deletes a lead (every stage, test rows too), the rows a
  sync removed, the pages read by a visitor ID that became a lead, the lead's name and email, or
  the hook spool's lines (the raw copy the second count recounts leads from). The delivery log
  still goes after 90 days. `journeys.vid_days` (the pages of a visitor ID with no lead yet) is
  1 to 400 days. Both are now settings per site, on a new **Leads** card under Settings > Data
  retention ("Leads and the pages they read: Kept for good / N days"; "Pages of visitors who have
  not signed up yet: N days. Once they sign up, their pages are kept with the lead"), and from the
  shell: `skald settings set <site> conversions.retention_days 0` (or `forever`),
  `skald settings set <site> journeys.vid_days 400`. Each site is pruned by its own values; a
  spool day holding lines of sites with different windows is written again with only the lines
  still kept. Going from kept for good back to days, or to fewer days, asks for the site's name
  (page) or `--yes` (shell), as every shorter window does, and the page shows what would go.
  The privacy-notice wording says how long a lead's name and email, and the pages read with a
  visitor ID, are kept: "until you ask us to delete them" when kept for good, else the days.
- **Why:** the owner's decision (22 Oct): never delete a lead's pages. Until now a lead and its
  pages went after 400 days, and the setting was only in the config file, for the whole install.
- **Who:** sites that take leads. New installs keep the same defaults (400 days for leads, 30 for
  pages before a sign-up); nothing changes until someone sets it. **Do:** to keep leads for good,
  set it per site (above) and update the site's privacy notice with the new wording. A person's
  own request to be deleted still works: `skald forget --email ...` (or `--lead`, `--vid`).
- **The audit:** the second count still agrees over old days. The hook spool is kept as long as
  the leads, site by site, so a day older than 400 recounts the same; the beacon's day counts the
  audit keeps (`conversions-audit.json`) are kept as long as the leads too (they were cut to 400
  days), so beacon leads older than the beacon spool are still checked against the count made
  while it held them.
- **Checked:** tests/test_leads_kept_for_good.py (0 keeps rows, removed rows, linked pages,
  identities and the spool; a linked page older than `vid_days` stays and an unlinked one goes;
  each site by its own days; `forget` still deletes; the settings' checks, plan cap and CLI;
  the page's save, confirm and preview; the notice wording; the audit agrees over a 639-day-old
  lead after the prune, kept for good or not, and withholds it when the store is kept without
  its spool), tests/test_privacy_notice.py and tests/js/settings-privacy.mjs (the Leads card).

## 2.28.1 (2026-10-22)

### Fixed: a hook dropped the visitor ID when visitor IDs were switched on in Settings

- **What changed:** the hook receiver now reads the site's visitor-ID switch
  (`beacon.visitor_ids`) with the site's Settings rows applied, as the beacon and the daily run
  already did.
- **Why:** on 22 Oct an end-to-end test (three pages on a site, then a sign-up on its app
  subdomain) arrived with the right visitor ID, and its first-touch time was worked out from it,
  but the row was stored without the ID, so its visits were not linked to the sign-up. The switch
  had been turned on in Settings, not in the config file, and the receiver read only the file.
- **Who:** sites that turned visitor IDs on in Settings (or with `skald settings set`) and send
  leads by hook. **Do:** nothing. Leads sent before this release keep no visitor ID; a sender can
  send a later stage again with it.
- **Checked:** tests/test_conversions_hooks.py (a settings row turns the vid on for hooks; the
  test fails without the fix), and a live end-to-end run after the deploy.

## 2.28.0 (2026-10-22)

Leads' 7, 30 and 90 days include today so far, with the exact dates from and to.

### Changed: Leads' 7, 30 and 90 days include today

- **What changed:** on Leads & sales > Leads, 7 days are now today so far and the 6 whole days
  before it (30 and 90 the same way). The heading gives the dates from and to, with weekdays:
  "Last 7 days: Fri 16 Oct to Thu 22 Oct (today, so far)", the year only when the days cross a
  year. Today's leads are in the list, newest first, each with a small green live dot. The
  "Today so far" line is now part of the period, under the count ("Today so far: 2 of these 5
  leads"), with Show today (live) still going to today alone, and says in one sentence that the
  whole days are verified and today is live, checked again once whole. The change against the
  period before is like for like: the period before's whole days, then its last day only up to
  the time it is now ("25% more than Fri 9 Oct to Thu 15 Oct 14:00 EDT (4), the 7 days before to
  this hour"), never a part-day against a whole one. With a label or a source, country, device or
  campaign filter on, no change is shown, and the line says why. The CSV is named after the
  period's days (`leads-2026-10-16-to-2026-10-22.csv`). In the Timeline, today's bar is said to be
  so far, and pressing it opens Today (it opened yesterday's day before: a custom day stops at the
  last whole day). The empty state names its dates too.
- **Why:** the owner, 2026-10-22: on #sales/leads "if you are looking at 7 days it should also
  show today ... today is 1 + last 6 = 7 days", and "show clear dates from and to so it's not
  confusing". The list opened on the last 7 whole days, so a lead that came in today was only in
  the "Today so far" line.
- **New figure:** conversions.json `today.same_time` (conversions_leads.same_time): the day that
  ends each period before (today minus 7, 30, 90), counted from midnight to the file's time of
  day, by kind. Second count: `audit_conversions_leads.check_same_time`, one SQL GROUP BY between
  its own bounds; a difference withholds `today` as before. The period's days, today's included,
  are conversions.json's `days[]`, recounted by audit_conversions.py on every build.
- **Who:** everyone who opens Leads. Summary, Sources, Calendar bookings, Funnels and Events keep
  whole days up to yesterday: their figures sit beside visitors, rates and Compare with…, which
  take whole, verified days only, so a part-day would mix in. The Leads line names their dates. Yesterday, Today,
  All time and custom periods are unchanged everywhere. The URL keeps `range=7d` etc. as before.
- **Do:** nothing.
- **Checked:** tests/test_leads_today_period.py (the period's days with today's rows, the list
  newest first, the like-for-like count against the SQL recount, a tampered figure withheld),
  tests/js/leads-period.mjs (the heading words, the dates, the "Today so far" line, the live
  mark, the change and its filters, the URL, Summary unchanged), the full suite, and the demo
  (public/docs/screenshots/leads-list.png).

## 2.27.0 (2026-10-22)

Share the visitor ID across a site's subdomains from Skald's side (a per-site setting, off by
default), so a sign-up on app.example.com links to the visits on www.example.com without touching
the site's script tag; and the developer's set-up page draws properly again.

### Fixed: the developer's set-up page drew a page-sized icon

- **What changed:** the private set-up page (Share with your developer) now loads the stylesheet
  for the copy and open icons beside an address, and says when the link ends in words
  ("29 Oct 2026, 16:17 UTC"), not as a raw time stamp.
- **Why:** on 22 Oct the owner opened a hook's set-up page and saw a huge empty box with a dark
  shape across it: the address's icons (2.21) had no styles on that page, so the icon filled it.
- **Who:** anyone opening a developer link. **Do:** nothing.
- **Checked:** a test that every stylesheet the page needs is linked and served.

### New: share the visitor ID across subdomains from Skald, with the tag unchanged

- **What changed:** a new site setting, `beacon.share_subdomains` (admin, off by default;
  Settings > Sites > Script tag, or `skald settings set <site> beacon.share_subdomains true`),
  does what `data-share-subdomains="true"` on the script tag does: `www.` and `app.` share one
  anonymous visitor ID through the first-party cookie `skald_vid`. The beacon's answer to a page
  view from the site's own Origin now carries `X-Skald-Sh: 1` or `0` (exposed by CORS). Its
  status and body are unchanged (204 counted, 202 not, no body), so nginx's count and older
  scripts are untouched; no other answer and no other Origin gets it. `skald.js`, without the
  attribute, sends its first page view of a load by `fetch` (keepalive, no credentials, the same
  text/plain body) instead of `sendBeacon`, reads the header, writes the cookie at once on `1`,
  and keeps the answer a day in `localStorage` (`skald.sh`); a fresh answer decides at start
  with no ask. On `0` after a `1` it deletes the cookie it wrote. The attribute still wins. Do
  Not Track, GPC, `data-consent="required"` and visitor IDs off behave as before: no ID, no
  cookie, no ask. Settings > Integrations says when sharing is on in Skald, and the privacy
  notice's cookie line is then plain, without "[Keep this line only if...]". `skald.js` grows
  from 6,132 to 6,628 bytes (3,250 to 3,475 gzipped); the size test's budget is now 6.5 KB.
- **Why:** a client site's web developer cannot add `data-share-subdomains="true"` to the tag,
  and we have no access to that site, so its subdomains could not share the ID.
- **Who:** sites on several subdomains that want one journey across them. **Do:** nothing,
  unless you want it: an admin switches it on per site (visitor IDs must be on). Browsers pick it
  up within a day; switching it off stops the sharing within a day too.
- **Checked:** tests/test_share_subdomains.py (the setting and the CLI; the answer on and off,
  never for a foreign Origin, other answers and nginx's count unchanged; Integrations; the
  notice), tests/js/skald-snippet.mjs (first load asks then sets the cookie on `.example.com`, a
  fresh flag skips the ask, a stale one asks again, `0` clears, the attribute wins, an older
  Skald, a refusal, DNT/GPC/consent/IDs off), `node --check`, the full suite.
