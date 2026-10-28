# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

Nothing yet.

## 2.44.0 (2026-10-28)

Set-ups that say by themselves whether they worked, and leads with their country. **Live status:**
every connect journey (an agent line, an install command, a hook address, a share page, Search
Console) checks itself while it is open, has a **Test** beside it, and says in plain words when
something failed; Your tools no longer says "Connected" before a tool has answered. **Search
Console connects by itself** once Google shows Skald's robot, on whichever property (Domain or
URL-prefix) the robot can see, and Traffic › Search fills in as Google's history arrives, with no
reload. **Shorter set-up steps:** one status line, the next thing to do under it, the details and
the safety list folded. **Lead countries:** Skald's lead files (PHP, Node, Python, WordPress 1.1.0)
send the visitor's address, Skald looks up the country and drops the address; a warning shows when
the last three leads came without one. **MCP:** a new "Add sites (AI agent)" token lets an agent
add a site, follow it and send the invites, within the plan's site and member limits. **Welcome:**
a new person's first sign-in says whose sites they see and where to start. Docs, help and
screenshots are brought up to date, and Leads & tools no longer says "All connected" over a red line.

### Upgrade

- Nothing is required: no schema change, no new nginx line, no new setting.
- **Lead countries:** if your site sends leads with one of Skald's lead files, download it again
  (Settings › Leads & tools) or add the visitor's address as `ip` to your own call; leads sent
  without it keep "Country not recorded". The WordPress plugin is 1.1.0.
- Search Console: a site whose robot was added but never connected connects by itself within a
  minute of the upgrade (Skald checks every minute for 7 days after a set-up).

### Check again's "In the log since" time follows the check, not the wall clock

- **What:** the log line under a Check again result writes the mark's time alone when it is on
  the check's own day, and "27 Oct 14:10" when it is on another day. It compared with the
  server's wall clock instead of the check's time, so near midnight the day could be wrong.
- **Why:** found by the 2.44 public test run, which crossed midnight UTC and failed one test.
- **Who:** anyone using Check again near midnight. **What to do:** nothing.
- **Checked:** `tests/test_todo_check.py`, also run with the clock set two days later.

### Leads & tools no longer says "All connected" over a red line

- **What:** when every tool that fits is connected but a check needs a fix (for example the
  lead-country warning), the Next step card now says **1 to fix** and "everything that fits is
  connected, but one thing needs a fix: see below", not a green **All connected**. The red line's
  word is **Needs a fix** (was **Broken**), and its name reads "Lead countries: Your site's server"
  (was "Lead countries (Your site's server (lead))").
- **Why:** found while checking the 2.44 screenshots: the page said all was well and broken at once.
- **Who:** owners and admins on Settings › Leads & tools. **What to do:** nothing.
- **Checked:** `tests/js/set-leads.mjs` (all connected with nothing to fix stays green; with one
  red line it says 1 to fix), the doctor and lead-country tests, a fresh screenshot.

### Screenshots of the signed-in screens retaken, and the 2.44 gallery

- **What:** the README and website screenshots the static demo cannot draw, because they need a
  signed-in Skald, are retaken from the current build: Leads & tools (and its status crop), Data,
  People, Add a site's two steps, the set-up dialogs (Who will do it?, Finish set-up's line, the
  one command), Privacy's address choice and notice wording, the logo, and the three person
  searches; on the website, the client report preview (`reports-preview*.webp`, on about 163
  pages) and the tracking profiles (`ai-answers-profiles*.webp`, now 1200 × 327). Same names,
  sizes and crops where the screen allows; alt texts carry the new figures. The README gets a
  2.44 gallery (set-up lines with their Test, the short Watch it work, Search Console syncing by
  itself, the Add sites token, the lead-country warning, the welcome line), a 2.44 line in
  What's new, and FEATURES.md the 2.44 lines. Site rebuilt.
- **Why:** the 2.43 sweep left them showing screens from before 2.43 (Leads & tools before its
  rebuild, the old Reports page, profile cards with five buttons each).
- **Who:** readers of the GitHub page and the website. **What to do:** nothing.
- **How it was made and checked:** the demo build (`tools/demo.py --now 2026-10-22T19:07:00Z
  --keep`) served to a browser with the real helper behind it, in sessions mode, on the kept
  install: made-up people at example.com, .org and .net, sample data only, every site fetch
  answered locally, one-time codes replaced by a sample before each picture. Both test suites OK
  (with and without PyYAML); public sweep 0 hits; every image the README and the website name
  exists.

### The "Is it safe to paste this into a chat?" list starts folded

- **What:** under every line for an AI agent, the seven-point safety list now starts folded, its
  title in view; one press opens it. It used to be open on a wide screen, pushing Next below the fold.
- **Why:** the owner (27 Oct) on the set-up dialogs: "so long, so much info"; help belongs behind a press.
- **Who:** everyone who opens a set-up line. **What to do:** nothing.
- **Checked:** `tests/js/agent-setup.mjs` (folded, the same seven points), both suites.

### Every connect journey says by itself whether it worked, with a Test beside it

- **What:** wherever Skald gives someone something to do (a line for an AI agent, the install
  command, the set-up pack, the script tag, a "Share with your developer" page, a webhook
  address, a tool key, recorded journeys, a new API or MCP token), a pill and one plain sentence
  now say whether it arrived yet ("Waiting for your agent: it has not opened the line yet.",
  "Connected. The last delivery from Calendly came at 10:44"), and update by themselves: every
  5 seconds for 3 minutes, then every 30 seconds, never while the tab is hidden. A **Test**
  button beside it checks at once and says the next thing to do; the technical words are behind
  Details. Traffic › Search and the connect cards follow the live state and read their data
  again by themselves when it changes: no reload. People who only view re-read the page's file
  once a minute while a history is still syncing. New route POST `sites/arrived`
  (docs/DATA-CONTRACT-CONNECT.md).
- **Why:** the owner (27 Oct), on docomatic.ai's Traffic › Search: it kept saying "Search
  Console is not connected yet" while it was connected and its history was syncing, because the
  page decided from its file read once. "Status does not get updated, and it's very confusing
  ... wherever you have a command, 'copy this and give it to Claude Code', there should be a
  test button." The full list of journeys and what each one does now:
  docs/plans/connect-journeys-audit.md.
- **Who:** owners and admins setting anything up; viewers of Traffic › Search while it syncs.
- **What to do:** nothing.
- **Checked:** `tests/test_connect_check.py` (every kind of `what`, the words, a viewer
  refused, an unknown kind, the limit per hour), `tests/js/live.mjs` (the poller, the redraw, the
  Test button, Traffic › Search turning connected and syncing without a reload),
  `tests/js/setup-checklist.mjs`, both suites (with and without PyYAML).

### Search Console connects by itself, and the agent's watch fits on one screen

- **What:** when an AI agent reports a Search Console property, or someone presses Connect or
  Check now, Skald asks Google which properties its robot can see and connects the one that
  covers the site. If the robot is on another property than the one named, Skald uses it and
  says so in one line. If Google shows none yet, the page says "Waiting for Google: Skald's
  robot address is not on a <site> property yet. Google can take a few minutes. Last checked
  17:56." with Check now, and Skald keeps checking by itself (at most once a minute, for 7 days),
  then connects and starts the 16-month history. The agent's report gets the same answer, so
  the agent tells the person what Skald sees; the agent's steps no longer send anyone to
  Settings to press Connect. Step 3 of every agent line ("Watch it work") now has one status
  line on top, the next action right under it (Apply, Check now), the ticks folded once done,
  and the keys, Cancel and the agent's full report behind Details. A failed connect shows on the
  open page in plain words, not only by mail.
- **Why:** the owner (27 Oct), on one of his sites: the agent reported the domain property and
  sent him to Settings to connect; at the foot of a long step 3 he pressed Apply, Google refused
  because the robot was on the site's URL-prefix property instead, the connection went
  failed and the open page did not say so.
- **Who:** anyone connecting Search Console, by hand or with an AI agent.
- **What to do:** nothing. A site waiting for Google connects by itself once the robot address
  is on its property.
- **Checked:** `tests/test_search_auto.py` (the property the robot sees is used and said, none
  visible waits then connects by itself, Check now, gives up after a week, the agent's report
  answer), `tests/js/agent-jobs.mjs`, `tests/js/agent-setup.mjs`, `tests/js/live.mjs` (the
  watch's top line, Traffic › Search waiting for Google), both suites.

### Docs, screenshots and website brought up to 2.43

- **What:** the marketing site's dashboard screenshots (`/img/*.webp`, same names and sizes)
  and 45 README screenshots, the README hero (light and dark) and the GitHub social card are
  retaken from the 2.43 demo (sample data for example.com only). The Security story page's
  numbered hotspots moved to match. The help guides and technical docs, the website's feature,
  docs, compare and pricing pages, and the alt texts now describe the 2.42 screens and the 2.43
  features (your tools, organisations, Add a site's questions and live progress, connect cards,
  Check again, Search Console reports, recorded journeys, AI reads). Detailed GitHub release
  notes for v2.43.0 and corrected links for v2.38.0 to v2.42.0 are written in
  `docs/plans/release-notes/`, to publish by hand.
- **Why:** the owner asked for every document, release note and screenshot to match the live
  2.43.0 (27 Oct). The website still showed the 2.13 screens; the README showed the top bar
  from before its seven controls; the GitHub release notes' "Full release notes" links pointed
  at sections that moved into `docs/`.
- **Who:** readers of skaldanalytics.com, the GitHub page and the in-app Help. Nobody running
  Skald.
- **What to do:** nothing.
- **Checked:** both test suites (with and without PyYAML), `tools/build-about.py --check`,
  `tools/cli-reference.py --check`, the site build ("problems: none"), every sitemap page
  answering 200 from a local server, image pages seen at 1440 and 390 px, the public export
  check.

### Leads from your own server get their country: the lead files send the visitor's address

- **What:** the lead files (`skald-lead.php`, `skald-lead.cjs`, `skald_lead.py` and the
  WordPress plugin, now 1.1.0) send the visitor's address as `ip`. Skald looks the country up
  and drops the address at once, as it already did for an `ip` it was sent. PHP and WordPress
  read it by themselves (`REMOTE_ADDR`; behind a proxy on the same server, `X-Real-IP` or the
  first `X-Forwarded-For` entry; behind a CDN, the header named in `SKALD_LEAD_IP_HEADER`).
  Node and Python take `ip` from the caller; their README shows the line for Next.js on Vercel,
  Express, Flask, Django and FastAPI, and which header to trust on which host. Every file sends
  `ip` only when it is an IPv4 or IPv6 address; Skald reads a header's list as its first
  address. `vid` and `ip` work together: `vid` joins the lead to the pages read, `ip` gives the
  country, and a lead's country never comes from its visitor ID. When each of a site's last 3
  leads from its server came without a country, Skald says so with the fix: Settings › Leads &
  tools › Status ("Lead countries", also in `doctor`) and the set-up checklist's lead line,
  whose Set up gives the AI agent's `lead` job. The agent's job now passes the address and
  checks its test lead: the signed `GET .../leads` says `country_recorded` (true or false, never
  the country). A lead whose `ip` gave no country (a proxy's private address) says why in the
  answer and the delivery log.
- **Why:** on a site on Vercel with no script tag, Overview › Summary's "What converted today"
  showed "Country not recorded" for every lead, while its visits all had countries. Its leads
  came from its own server with neither a visitor ID nor the visitor's address, and none of the
  files Skald gives sites sent the address. The owner (27 Oct): "it should never happen".
- **Who:** every site that sends leads from its own server (the lead files, the WordPress
  plugin, or its own code on the `lead` or `json` hook). Sites whose leads come from the script
  tag's forms already had a country.
- **What to do:** sites that send leads from their own server download the lead file again
  (Settings › Leads & tools) or re-run the AI agent's `lead` job; Node and Python callers add
  `ip` as the README says. Leads already kept stay as they are: Skald never guesses their
  country afterwards (no matching by time to the log).
- **Checked:** `tests/test_lead_country.py` (the hook with `ip`, a list, a port, with and
  without `vid`, visitor IDs off, a private address, no country file, the address never on disk;
  the warning's states; the doctor's and the checklist's lines; the read-back; the Node file
  in node and the PHP file and WordPress plugin in php, posting to a stand-in Skald), the
  checklist's page-and-server parity case, both suites.

### An AI agent can add a site over MCP, within the plan

- **What:** four MCP tools and one token scope. `add_site` adds a site to the token's own
  organisation, with the people who will use it, and answers its page and the one-time set-up
  line for an AI agent; `site_progress` shows the live set-up step by step; `check_site` is
  Check now; `send_invites` mails the people before the first data. The scope **Add sites (AI
  agent)** (`add_sites`) is for the whole organisation, only with AI assistant (MCP), made by an
  owner or admin who sees every site, in Settings › AI & API › New token. The MCP server now has
  29 tools. The dashboard's Add a site and Who will use it now also check the plan's members for
  the new people they name (open invites included).
- **Why:** the owner (27 Oct): "yes, and depending on plan etc they are". Saying to Claude "add
  shop.example.com to Skald, invite these two people as viewers, and tell me when data arrives"
  needed the dashboard before.
- **Who:** owners and admins who connect an AI agent. Plans hold over MCP as in the dashboard: the
  plan's sites and members refuse in one sentence with what to do, a read-only organisation adds
  nothing, an organisation with no plan has no limit, a hosted site waits for its domain to be
  verified. A new organisation is never made over MCP. Each site added and each invite sent is in
  the audit log (`mcp.add_site`, `mcp.send_invites`), never a code, token or address.
- **What to do:** nothing. To use it, make a token with Add sites (AI agent) and connect your
  agent with it.
- **Checked:** `tests/test_mcp_add_site.py` (the scope's rules, the shared code path, the plan's
  sites and members with the dashboard's own words, read-only, no plan no limit, wrong scope,
  revoked and demoted makers, another organisation's site, the same answers as sites/live and
  sites/check, Check now per token, the audit rows), `tests/js/set-account.mjs` (the token
  maker), both suites.

### A short welcome on a new person's first load

- **What:** the first time a new person opens the dashboard, one line over the page says
  "Welcome to Skald, <first name>. You see <organisation>'s sites. Start with Overview." with
  links to Overview and Help, and a × to close it. It stays across reloads in that tab until
  closed, and never comes back.
- **Why:** the owner asked for a short welcome on first sign-in (27 Oct), for people invited to
  a new organisation of its own.
- **Who:** only accounts made from this release on. Everyone who has an account already never
  sees it.
- **What to do:** nothing.
- **Checked:** `tests/test_welcome.py` (once, then never; a second sign-in; an account from
  before; each person their own; the words), both suites; seen in the demo at 1440 px.

## 2.43.0 (2026-10-27)

Your own marketing tools beside the log, organisations you manage in the dashboard, and set-ups
that show live whether they worked. **From your tools:** Google Analytics 4, Vercel Web Analytics,
Calendly history and Resend, each read with your own key, shown apart and labelled "Counted from:
<tool>", never added to the log's counts, and recounted from the stored answer; marketing alerts
and an optional Monday mail. **Recorded journeys:** a site can send the sessions its visitors
agreed to, signed, shown beside the log's own visits. **Organisations:** Settings › Organisation ›
Organisations lists every organisation with its sites, members and privacy class (internal keeps
everything; a client's sites follow their own retention); a member can be limited to some sites.
**Add a site** asks the organisation and the people up front, shows live progress with one Check
now, and mails the invites once the first data arrives. **Connect the dots:** every page that is
empty because a source is missing says what it needs, what Skald found and offers Connect; Leads
& tools is rebuilt around a next step. **Insights:** Check again re-runs a to-do's own check after
a fix. **Search Console:** opportunities, new and lost queries, positions over time. **AI:** an
assistant's live fetches are counted as reads, not requests (a page's CSS and JS were shown as
"AI asked"). The top bar has the mockup's seven controls and Include today is one press again.

### Upgrade

- **Back up first** (`docker exec skald skald backup`, and a copy of `accounts.sqlite`): the
  accounts file moves to schema 6 on the first start (organisation privacy class and archive,
  site access per member). 2.42 refuses a schema-6 file, so going back means restoring that copy.
- **Your own front nginx** (not the image's, which is updated): take DEPLOY.md's lines again. The
  kit location widens to `(report|hooksecret|searchkey|toolkey)`, recorded journeys add
  `/traffic-hooks/<site>/journey` (and `/withdraw`) and `/traffic-js/journeys.js`, and the per-site
  helper routes add `recorded` and `orgs`.
- Nothing changes for a live site's data: every organisation starts internal (keep everything),
  your tools, recorded journeys, marketing alerts and the Monday mail are off until connected or
  switched on. Days stored before 2.43.0 have no AI reads: they say "reads counted from <date>".


### Check again: re-run a to-do's own check the moment you have fixed it

- **New.** Every to-do on Overview › Insights has **Check again** (on its card, and in Fix
  this under Me). The owner, live on a site's `#overview/insights` on 27 Oct: "I have made
  fixes; there is no way to re-run the check." Until now a to-do was only re-checked on the
  whole days after it was marked done.
- **How each kind is checked.** Old addresses, Markdown copies, sitemap addresses and server
  errors: Skald asks each address now and says what it answers ("Fixed: all 12 addresses now
  answer 301 to a live page", or "3 of 12 addresses still answer 404" with those rows and what
  each answers). A page people leave (from visits) is never asked: the page says it is judged
  on whole days of visits after the mark. Each check also reads the newest log lines since the
  mark ("none of these addresses answered 404 since 14:10"); the live answer decides.
- **Fixed.** A check that finds every address fixed marks the to-do Fixed (Skald's mark, with
  the time and who pressed it); it moves to "Done, and did it work?". A later check that finds
  it broken again puts back the mark it had before.
- **Check all again** above the list checks every to-do Skald can ask, one after the other,
  with its progress in place. When a person's AI agent (or MCP assistant) reports a to-do done,
  the same check runs at once and its answer shows beside the report.
- **Polite to the site.** At most 50 addresses a check ("Check the next 50"), one at a time,
  a short wait between them, 5 s each and 20 s in all; HEAD requests (GET for server errors, or
  when HEAD is refused), no body read, no cookie; a redirect followed at most twice and never to
  another host; Skald's own user agent `site-todo-check/1`, counted as Skald's own traffic, so a
  check's 404 never becomes a lost page. The fetch is the site check's own: public addresses
  only. 30 checks an hour a site, one start a minute a to-do.
- **Who.** Owners and admins press it (CSRF checked); a viewer sees the answers. Each check is
  an audit-log row `todo.checked` (the verdict and counts, never an address). The open answer
  is in the address (`tdchk=<id>`).
- **Second count.** A separate count re-derives every Fixed mark from the answers Skald kept;
  one it does not bear out shows as done, not fixed, with why.
- **Who it affects:** owners and admins of every site. **What to do:** nothing. No nginx change
  (the route is under `settings/`, already passed).
- **Checked:** Python tests per kind with fake fetches, no network (fixed, partly, not fixed,
  another host, a timeout, the time budget, capped pages, a stale page, the limits, log only,
  the log line, the second count, the route's roles and CSRF, the check after an agent's
  report); node tests for the buttons, the answer in place, the address, Check all again and
  the demo's sample answer; the full suite with and without PyYAML; screenshots from the demo.

### Small fixes before 2.43.0: NotebookLM as a user fetcher, reads in AI answers and client reports, fresh screenshots, the mail footer

- **Fixed.** Google-NotebookLM, BingPreview, Amzn-User and the other user fetchers whose
  names do not end in "-User" had no "user fetcher" tag in lists and drill-downs, and
  NotebookLM's address check said "not verifiable". The page decided by the name's ending;
  it now uses the server's own list of user fetchers (the one that files a fetch under its
  assistant), held to it by a test. NotebookLM's address is now checked against Google's
  published user-triggered fetcher ranges (and reverse DNS), which Skald already downloads.
  The public crawler list (bots.json) says so. **Who:** every site NotebookLM or Alexa
  visits. **Do:** nothing. **Checked:** `tests/test_fetcher_names.py` (the page's list is
  the server's, every user-fetcher name is in it, the tag names the assistant for
  Google-NotebookLM and none for GPTBot, a NotebookLM address inside Google's list is
  verified and one outside is not).
- **Fixed.** AI answers' "From an answer to a lead" and the client reports' AI and bots
  line still counted an assistant's requests, so a page asked for twice, or its CSS and
  scripts, counted as several reads. Both now count reads (the same reads as AI & bots ›
  Assistants) and show the requests second: "3 page reads because someone asked an AI (4
  requests)"; the chain's Read step says "2 reads" with "3 requests" under it. A day
  stored before reads were counted leaves the reads not recorded (the report says "reads
  not recorded on every day", the chain "reads counted from <day>"), never 0. **Who:**
  sites with AI answers set up, and agencies sending client reports with the AI section.
  **Do:** nothing. **Checked:** the report's second count now sums the stored reads again
  by its own SQL and refuses a report whose reads differ or exceed the requests; a new
  second count for the chain sums the reads and requests again from the stored minute
  rows by SQLite's JSON functions and withholds both on any difference; tests for a
  repeat inside the window (3 reads, 4 requests), an old day (unknown, never 0), a
  tampered figure, and the Read step's words.
- **Docs.** The plan screenshots were older than the screens: Settings › Organisations
  (all, after the plan label left Skald installs), the Google Analytics drawer (after its
  one main button, Sync now, with Pause in a quieter row) and Add a site's two questions
  (after the "Sees: this site only / every site" line). Retaken from the demo build,
  sample data only, at 1440 and 390, light and dark. **Who:** readers of the plans.
  **Do:** nothing. **Checked:** each picture looked at; no page error while taking them.
- **Fixed.** The daily and weekly mails' footer said "a@example.com, b@example.com is on
  the report list" when the list had several addresses. It now says "are" for more than
  one and "is" for one. **Who:** every install that mails more than one address. **Do:**
  nothing. **Checked:** `tests/test_mail_html.py` (one address, then two, in the daily
  and the weekly mail).

### AI reads, not requests: an assistant's page files are no longer "AI asked"

- **Fixed and recounted.** An AI assistant's user fetcher counted every request as a page
  someone asked about. Seen live on 27 Oct on a site's AI & bots › Assistants: the
  Google-NotebookLM drawer listed `304 GET /css/global-custom.css · AI asked`, and the day's
  24 NotebookLM requests (14 page requests, 7 style sheets, 3 scripts) were 7 reads: it asks
  for a page twice within about 3 seconds, then loads the page's CSS and JS with the page as
  referrer. Each user fetch now gets one role (new day kind `ai_reads`): a **read** (one
  assistant, one page, once in 30 seconds), a **repeat**, or a **file the page loaded**
  (same-site referrer naming a page it just read, a file extension, `/_next/` or `/_nuxt/`,
  the site's asset prefixes, a Next.js data query). "Pages AI read for someone", "Which
  assistant read for someone", the assistants table (new **Reads** column; **Fetches** is now
  **Requests**), the per-day chart, Overview's AI card and tiles, "AI reads by page"
  (now Reads, then Requests), Traffic › Pages' **AI reads**, "Reads followed by a visit" and
  the daily mail now count reads and show requests as the second, smaller number. A file is
  shown as "AI page file", folded under its page's row ("asked 2 times, with 2 files its page
  loaded") in the drawer's recent requests and the AI feed, never "AI asked". A user
  fetcher's drawer has **What it read** (reads, requests, files; its pages "with N files"),
  and **?** says what that assistant is ("Google NotebookLM fetches a page when someone adds
  it as a source to a notebook, or refreshes one") and what a read means. The crawler
  drawer's path list is now **Paths it requested**. Request figures (status, bytes, cost,
  the tier totals) still count every request. `ai_fetches` rows gain a fifth item, the reads
  that minute; `ai_likely` gains `reads` and `reads_followed`; requests.json rows gain
  `ai_role` and `ai_of`; ai_activity.json asked events gain `role` and `of`.
  **Who:** every site an AI user fetcher visits; NotebookLM and any fetcher that renders
  pages most. **Do:** nothing. Days collected before this release have no reads: the
  dashboard says "Reads counted from <first day>" and keeps requests there, never 0 and
  never a guess; `backfill --force` recounts older days whose logs are still kept, if wanted. **Checked:** new
  second count `audit_ai_reads.py` (its own path and referrer reading, sharing only the
  lists and window in `ai_read_names.py`), which also checks the `reads` column of
  `ai_fetches`; `tests/test_ai_reads.py` (2 page GETs + CSS + JS = 1 read, 4 requests, 2
  files; two reads 2 minutes apart = 2; another page inside the window = 2; tampered blob
  and column fail the audit; requests.json never says "AI asked" for a file) and
  `tests/js/ai-reads.mjs`; the demo now has a NotebookLM-like reader, and its days audit
  clean. The 30-second window comes from the owner's sample (5 seconds from first request
  to last file) and the window browsers' own assets are judged in; it was not re-checked on
  the live server's log in this change (no server access), so the first live audit after
  the release is the real-data check.

### Connect the dots: every empty page shows how to connect its source, and a new Leads & tools

- **New.** A page that is empty because its source is not connected now says what it needs,
  what Skald already found on the site and the one way that fits it, with one **Connect**
  (the existing set-up dialog, which asks Who will do it? first) and **Other ways**. Why: the
  owner opened Leads & sales > Leads on a Next.js site set up by an AI agent and saw "No leads
  yet", and Settings > Leads & tools was a long list of rows with no first step. Pages: Leads,
  Calendar bookings, Revenue, Events, Funnels (a step that needs the script tag or a lead
  source), Traffic > Search, Overview's From your tools, Traffic > Visitors' Recorded by your
  site (admins), and Site > Alerts (an alert switched on whose source is not connected). A page
  fed by some sources says what is still missing ("Leads arrive from Calendly; your forms are
  not connected."). Viewers read "Ask an admin to connect it" with the dialog's link and its
  copy and open icons. AI answers stay off without keys: their page shows the plain state and
  the four steps, no Connect. Each Leads & sales tab, Search and Overview's From your tools
  have a **Sources: Leads & tools** link (admins) to the group that feeds them.
- **Changed.** Settings > This site > Leads & tools: **Next step for <site>** on top (what
  Skald found, the single most useful thing to connect as the page's one primary, a failing
  source first, and **Connect everything left with your AI agent**), then one card per goal
  (Leads from your forms, Bookings, Payments, Search, Your own tools, Recorded journeys, Send
  each lead out), each row with its pill (Connected, Waiting, Failing, Not connected), when it
  last sent and one action; a connected row links to its data (See leads, See bookings...).
  Sources that do not fit the site fold under **More you can connect**. The drawers and every
  old link (`tool=`, `setup=`, `by=`) are unchanged. New address keys: `lt=<group>` (Leads &
  tools at a group) and `way=<tool>` (the lead hook's dialog with that tool picked).
- **Changed.** The site check (Add a site, step 1) also notes, from the same home page it
  already reads, a Cal.com link, Stripe, HubSpot and how many forms the page has; GET
  integrations gives admins that check (`found`) and each hook's `last_at`. Nothing new is
  fetched from the site.
- **Who:** owners and admins of every site; viewers see the ask-an-admin card. **Do:**
  nothing; a site added before this release has no Cal.com, Stripe, HubSpot or forms facts
  until its check runs again (the recommendation then falls back to the plain way).
  **Checked:** `tests/js/connect.mjs` (each page's missing-source card, Connect's address,
  the viewer's wording and link, AI answers' plain state, partly connected, alerts),
  `tests/js/set-leads.mjs` (groups, pills, Next step, See links, More, `lt=`, drawers),
  `tests/test_site_detect.py` (the new tools and forms, their shapes),
  `tests/test_integrations_api.py` (`found` for admins only, `last_at`), both full suites,
  and screenshots at 1440 and 390 px, light and dark, in `docs/plans/dots-shots/`.

### The top bar as the mockup, Include today in one press, a shorter README

- **Changed.** The top bar is the approved mockup's seven: the page's name, the period, Compare,
  then on the right the filter, the search, the alerts and More. The period's **More** (Yesterday,
  All time, Custom) is now the last choice inside the period group instead of a button beside it,
  and the group is one keyboard stop (the arrow keys move along it). **Filters** is an icon on the
  right, before the search, with its count of active filters; the period now starts right after
  the page's name instead of the bar's middle. The bar had 10 buttons, each a keyboard stop; it
  now has 6 stops (7 on a phone, with the site button). Nothing moved out: every period, the
  Compare menu, the filters panel, `dlg=filters`, `range=`, `from=`, `to=` and `inc=` work as
  before. **Why:** the audit counted 7 controls in the approved mockup and the bar still had 10.
  **Who:** everyone. **Do:** nothing. **Checked:** `tests/e2e/topbar.mjs` on the demo (all pages,
  1280 to 1680 px and 390 px, light and dark; at most six stops, More inside the group, the filter
  on the right), `test_ux_overview_alerts`, before and after shots in `docs/plans/topbar-shots/`.
- **Changed.** **Include today** is one press again: a switch at the start of the line under the
  title on Overview › Summary and Traffic › Pages, shown only at 7, 30 or 90 days (where it changes
  the figures). Since 2.42 it took two presses (the period's More, then the item). It left the
  More menu, so it still has one place, and the period is still said once: the switch changes the
  title line's words ("Last 7 days including today ...") and gives no dates of its own. The
  address key is unchanged (`inc=1`), so old links work. **Why:** the owner noticed it took two
  clicks where it used to take one. **Who:** everyone using Summary or Pages. **Do:** nothing.
  **Checked:** `tests/js/period.mjs` (one press sets `inc=1`, a second clears it; no switch on
  other tabs, other periods or Today), `test_ux_sections`, a click on the demo at 1440 and 390 px.
- **Changed.** The public README was 1,058 lines, over the 1,000-line rule. The full feature list
  (270 lines) moved to its own page, `docs/FEATURES.md`; the README keeps the hero, What's new,
  Why Skald, a short Features section (one line per area, linking to the full page) and the whole
  screenshot gallery. It is now 810 lines, with the same 63 images. **Why:** files stay under
  1,000 lines. **Who:** readers of the GitHub page. **Do:** nothing. **Checked:** every image and
  link path in both files resolves, `tools/make-public.py --worktree` builds the public copy with
  the sweep clean and its verify OK.

### Five small fixes: the live audit during a log rotation, and four tidy-ups

- **Fixed.** `skald --site X audit --live` reported a mismatch when the log was rotated or cut
  back between the live run and the recount (seen live on a site whose logs are shipped: the
  shipped `access.log` moves to `access.log.1` at the first batch of a new UTC day). The same
  file name then held other bytes, so the recount differed from the snapshot through no fault
  in either count. The live snapshot (and the Real time helper's tail file) now record which
  file each name was (`read_ids`, beside `read_upto`); the audit looks before and after its
  recounts, and if a name now holds another file, is smaller than was read, is gone, or a new
  log appeared, it answers `audit skipped: ... the log rotated during the check (...); run it
  again` and exits 0. With the files unchanged every figure is compared as before, so a real
  mismatch still fails. **Who:** anyone who runs `audit --live`, most of all on shipped logs.
  **Do:** nothing; the next live run records the new field. **Checked:**
  `tests/test_live_rotation.py` (a rotation after the live run, one during the audit's own
  recount, a new file larger than the old, a truncation in place, an older snapshot without
  the field, the helper's tail read before a rotation, appended lines still audited, and a real
  mismatch still reported; also that without the check the same rotation was a false mismatch).
- **Changed.** Your tools' second check is now `yourtools/recount.py` (was
  `yourtools/audit_tools.py`, the same file name as the older `audit_tools.py` (the tool visits audit),
  the tool-visits recount, which was confusing). Code (the Vercel, Calendly and Resend
  adapters and the marketing alerts too), tests, docs/TOOLS.md and Help › Your own tools say
  the new name; the command stays `ti.py tools audit`. **Who:** builders only. **Do:** a new
  tool adds its recount to `recount.RECOUNTS`. **Checked:** `tests/test_yourtools.py` and
  `test_yourtools_{ga4,vercel,calendly,resend}.py` (the check still shares only `names.py`),
  the help files rebuilt.
- **Fixed.** Settings › Organisation › Organisations: a card said "Plan: Internal" beside a
  Client privacy pill, which read as a contradiction (the plan word fell back to "Internal"
  when an organisation had no plan). The plan now shows only on a hosted Skald that sells
  plans, as its name or "none"; elsewhere the card and the drawer's Overview show no plan, and
  the privacy pill is the one place that says Internal or Client. Help › Organisations says
  the same. **Who:** install admins and owners on servers with accounts. **Do:** nothing.
  **Checked:** `tests/js/orgs.mjs` (the card line hosted and not, no "Plan" on a card or in
  the drawer where nothing is sold, the Client card says Client only); screenshot
  `docs/plans/orgs-shots/orgs-1440-light.png` retaken from the demo.
- **Changed.** Settings › This site › Leads & tools › a tool's drawer (Google Analytics, and
  every tool, since they share it): Save, Replace the key, Sync now and Pause were equal
  buttons. Now one is the primary (docs/UI-RULES.md rule 1): the key once one is pasted, else
  Save when an option changed (and Save is active only then, rule 12), else Keep the key on a
  tool with no key yet, else Sync now. Pause and Remove the key sit in a quieter row of their
  own under it, with the line that says what each keeps. **Who:** admins who connect a tool.
  **Do:** nothing. **Checked:** `tests/js/your-tools.mjs` (one primary in every state: nothing
  changed, an option changed and changed back, a key pasted, no key yet, a key in the
  server's environment, Calendly's drawer; Pause and Remove only in the quiet row); screenshot
  `docs/plans/tools2-shots/ga4-drawer-1440-light.png` retaken.
- **Added.** The public demo shows recorded journeys: five sample sessions from three made-up
  visitors (example.com pages, example.org and example.net referrers, consent given on every
  event, no address or email sent), signed and posted to the real journey receiver and kept
  by the real store (`tools/demo_recorded.py`). Traffic › Visitors shows the Recorded by your
  site card and each session's drawer (`rj=`), read from the helper's own answers written
  beside the page for today, yesterday, 7, 30 and 90 days and all time (each recounted from
  the raw events; a period that did not match would stop the build). Before, the demo hid
  both. **Who:** anyone trying the demo. **Do:** nothing. **Checked:** `tests/test_demo.py`
  (the answers, their figures, no email or address, consent on every stored event, and the
  page's file map), `tests/js/recorded-ui.mjs` (the card and a drawer from the demo's files,
  no card for a period without one, Connect still says why not); a full demo build.

### Your tools: names and emails past the People days go, even from a tool that stopped

- **Fixed.** Names and emails in your tools' stored answers (Calendly invitees, Resend
  contacts and recipients) are now removed once they pass the site's People days, also when
  the tool stopped answering. **Why:** they were cut only when an answer came, so a tool that
  stopped kept its last answer's names past the promise (found while building the tools).
  **Who:** sites with Calendly or Resend connected. **Do:** nothing. The daily prune now runs
  `yourtools/people_days.py`: each stored answer goes through its tool's own cut again with
  the site's People days; the figures stay, and the answer's fingerprint is made again so the
  second road still matches. It asks the Keeper first, like every other deletion path: an
  internal or keep-everything site keeps everything, a client organisation's site follows its
  own settings (keep_everything.py's list, docs/SETTINGS.md, and the static check that every
  path asks the Keeper). Counts only go to the output, privacy.log and the audit log.
- **Fixed.** The Monday marketing mail's last line says "are on the report list" when it
  goes to more than one address.
- **Checked.** `tests/test_yourtools_people_days.py` (old names cut, young ones kept, a tool
  that stopped swept, every figure unchanged, the recount matching after a cut and still
  finding a change made any other way, nothing within the days), the keep-everything and
  organisation-rule pieces (kept on an internal install, cut for a client and with the rule
  off), the mail test; both full suites.

### Add a site: live progress, Check now, and the organisation and people chosen up front

- **Added.** Add a site's **Connect it** shows **Live progress**, which ticks itself with a time
  on each line: the agent opened the line, keys made and taken, the data road set up (for
  example a Vercel log drain), the first data received (lines in the last 15 minutes and the
  newest time), the domain verified, the set-up done. It asks every 5 s, every 30 s after 2
  minutes, and not while the tab is hidden (`POST sites/live`). **Check now** (`POST
  sites/check`, 60 an hour) says in plain words what is missing, the technical part behind a
  fold. **Why:** the owner added a site, gave the agent line to its developer, the agent did
  everything, and his open wizard still said only "Finish later". **Who:** owners and admins
  adding a site. **Do:** nothing.
- **Changed.** **Live progress** is the step's one source of truth, on every path (Me, My
  developer, My AI agent): it replaces the old "Skald waits for the first visits" block and its
  **Test connection**, so the screen never says "Receiving data" and "Nothing has reached Skald
  yet" at once, and has one check button, **Check now**. What the old block had is kept inside
  it: the plain reason Skald refused what was sent (shown without a press), the shipper's
  `sudo skald-ship-check` for your own server and the home page's tag check in Check now's
  answer. The first data saves the set-up done, as the old test did. **Why:** the coordinator
  saw both on one screen in the receiving screenshot. **Checked:** `tests/js/setup-live.mjs`
  (each path, the old words never shown once data shows, the refusal), `agent-setup.mjs`,
  `connections.mjs`.
- **Changed.** Fitted onto Settings › Organisations (merged in): the people Add a site invites
  get its site access. A one-line **Sees: this site only / every site** under **Who will use
  it**; this site only by default in an existing organisation, every site in a new one, an
  owner always every site. That organisation page's **Add a site** (`setup=new&org=<id>`) opens
  on **Another of mine** with that organisation chosen (or **This organisation**), and `org=`
  leaves the address when the dialog closes. Members here limited to some sites are marked:
  they do not see the new site by themselves. The organisation's data rule is now the
  organisation page's privacy class (accounts schema 6); the wizard's own small table for it is
  gone, no schema change of its own. **Who:** anyone adding a site with people to invite.
  **Do:** nothing. **Checked:** `tests/test_setup_live.py` (the pending invites carry this site
  or none; a new organisation sees every site), `tests/js/setup-live.mjs` (the `org=` opener,
  the Sees line, the address cleared on close), `agent-many.mjs`.
- **Added.** The done state: a green **Receiving data**, **Open the dashboard** (the one
  primary button), **Invite the people who will use it**, and the dialog's last button says
  **Close**, never "Finish later". A link to a done set-up opens on it. Settings › Sites and
  Overview's "Set up <site>" show the same state as a label (Waiting for data, Receiving data).
- **Added.** Step 1 asks two questions first: **Organisation** (this one, another of yours, or
  a new one with its name and "Internal, keep everything" or "A client: their own privacy
  settings apply") and **Who will use it** (members ticked, new emails with viewer or admin,
  owner too for a new organisation, or No one else). A new organisation is made with the site,
  its maker its owner; the choice of client or internal is kept (`orgs.set_privacy_class`,
  audit `org.privacy`). The address keeps `org=same|<id>|new` and `ppl=<user ids>`, never an
  email or a name. "Set up many sites" asks the same, the same for all by default.
- **Added.** The people chosen are invited by Skald itself once the set-up is done and the
  first data has arrived ("<site> is live, 1,283 requests so far"), and the maker gets one mail
  ("<site> is live. Invites sent to 1 person."). After 24 hours without data, one mail to the
  maker says what is missing; **Send the invites now** (`POST sites/sendinvites`) sends them
  anyway. The agent's last words say who will be invited; `llms.txt` tells it never to invite
  anyone itself. Audit rows `setup.invites` and `setup.late`. Set-ups from before this release
  get no mail.
- **Checked:** `tests/test_setup_live.py` (status route, Check now, the two questions and
  their refusals, invites only after data and only once, the late mail, no mail for an old
  set-up, the kit's last words) and `tests/js/setup-live.mjs` (polling and stopping when
  hidden or closed, the done state, never "Finish later" when done, the address holding ids
  only). No nginx change: the new routes are `sites/<word>`, already passed.

### Settings › Organisations: every organisation, its members' sites, its privacy class

- **Added.** Settings › Organisation › Organisations (accounts only): each organisation as a
  card (its sites, members, plan, privacy class, state, the day it was made), with search and
  order. An install admin sees every one and makes new ones (name, privacy class, first owner,
  sites to move in); anyone else sees their own. A card opens its drawer: Overview (requests of
  the last 7 days and the last day with data, shown only when two separate counts agree, else
  Not recorded), Sites (open each, move a site here, Add a site), Members (roles, invite,
  remove, transfer ownership, leave; an organisation always keeps one owner), Pending invites,
  Settings (name, privacy class, two-step sign-in required, daily mail by default), Keys (revoke)
  and Audit. Every state is in the address (`org=<id>&otab=<tab>`, `orgs_q`, `orgs_sort`), by
  id only. Each Settings › Organisation page says which organisation it is, with Switch, for a
  person in two or more. **Why:** organisations could only be managed from the shell, one
  command at a time. **Who:** owners, admins and install admins on servers with accounts.
  **Do:** nothing.
- **Added.** Site access per member: an admin or a viewer sees every site of the organisation
  (as before, the default) or only the sites chosen for them, on the dashboard and its switcher,
  any address typed by hand, the API and MCP tokens they make, and the mails. An invite can
  carry it. Owners always see every site. **Why:** a partner or client could only be limited to
  one site by putting it in an organisation of its own. **Who:** organisations with members who
  should see only some sites. **Do:** nothing until you choose sites for someone.
- **Added.** Archive and Restore an organisation, each asking first: Archive pauses its sites
  and deletes nothing; Restore starts again only the sites it paused. **Why:** the owner's rule,
  pause, never delete. **Do:** nothing.
- **Added.** A privacy class per organisation, set by an install admin: Internal (the default:
  on an install that keeps everything, nothing is deleted) or Client (its sites follow their
  own retention settings even then; a hosted plan that keeps everything still keeps them). Every
  automatic deletion path asks it; the Privacy page and `doctor` say which rule applies.
  **Why:** a client's data should follow the client's own windows on an internal install.
  **Who:** install admins. **Do:** nothing: every organisation starts Internal, so no live
  site changes.
- **Added.** Commands: `org show`, `org archive`, `org restore`, `org privacy`, `org transfer`
  and `member sites`.
- **Changed.** The accounts file moves to schema 6 by itself at the next start: three columns on
  organisations (privacy class, archived when and by whom) and the sites list on members and
  invites. Nothing else changes. A Skald before this release refuses a schema-6 file, so going
  back needs the backup taken before the upgrade (`skald backup`, as every upgrade does).
- **Checked.** Python tests for every new route, each role, the last-owner rule, archive and
  restore, site access (also that a URL cannot dodge it), the privacy class on every deletion
  path, the commands and the figures' second count; Node tests for the page, the drawer and the
  address; both full suites, with and without PyYAML; screenshots in light and dark at laptop and
  phone width from the demo's sample organisations.

### Traffic › Search: opportunities, new and lost queries, positions over time

- **Added.** Traffic › Search (Google) shows its figures first, then one section at a time:
  Trend and tables, **Opportunities**, **New and lost**, **Positions**, **Cross-check**.
  Opportunities lists queries a page could win more clicks from, by two plain rules (shown a
  lot but clicked by under 1% while above position 8; or at positions 8-20), each linked to
  the page it showed most. New and lost compares the period with the same number of days
  before, on whole days only (ending at the newest final day). Positions tracks the 100 most
  shown queries and pages, one point a day, week or 30 days, with a chart in each row's
  drawer. The thresholds and caveats are behind each "?". **Why:** Search Console's figures
  were only tables; the owner asked for the reports a teammate's fork had, built from the
  data Skald already syncs. **Who:** every site with Search Console connected. **Do:**
  nothing; to see each opportunity's page for days synced before this release, fetch the
  history again (Settings › Leads & tools › Search Console & Bing, 3 or 16 months).
- **Added.** The sync also keeps each query with its page (`query_page`, one more Search
  Console request per 7 days fetched, counted by page like the page table). **Why:** a query
  cannot be linked to its page without it. Older days have none: the page says "Not known".
- **Changed.** A plain line above the figures says when the period is not whole: days before
  the history starts, days with no figures, the provisional days, or no impressions at all.
  Connected with no figures says why (a new property, a history still syncing, a failing
  sync). The Cross-check moved from the foot of the page to its own section.
- **Changed.** Every choice is in the address: `sesec_view` (section), `seopr_view` (rule),
  `senl_view` (new or lost), `sepk_view` (queries or pages), `seall_view` (Show all).
- **Audit.** `audit_search_reports.py` works every new figure out again by SQL over the
  stored rows (it shares only the rules' numbers with `search/reports.py`) and runs inside
  the daily search audit; `audit_search.py` also checks that `query_page` carries the page
  table's total. A difference ends run-daily "withheld", like the other search checks.
- **Checked.** `tests/test_search_reports.py` (recorded fake Search Console rows through the
  real sync, no network: the rules at their edges, whole days, gaps never 0, buckets, the
  recount matching and catching three planted errors) and `tests/js/search-reports.mjs`
  (the words, the address keys, Show all kept, copy and open icons). Both full suites pass,
  with and without PyYAML. Screenshots on the demo at 1440 and 390, light and dark:
  `docs/plans/search-shots/`.

### From your tools: Vercel, Calendly history and Resend; marketing alerts and mail

- **Added.** Vercel Web Analytics (`yourtools/tool_vercel.py`): Vercel's own visitors and
  page views over the last 28 whole UTC days, and its top 10 pages, referrers and countries,
  from Vercel's documented Web Analytics API (`/v1/query/web-analytics/visits/count` and
  `/visits/aggregate`, production only). Options: the project id, and the team id when the
  project is a team's. Rows past the top 10 stay in Vercel's own "Others" row; an empty
  referrer shows as "(none)". The drawer says Skald's own count of the same site comes from
  Vercel's log drain and this is Vercel's own count, shown apart. Vercel tokens cannot be
  read-only: the steps ask for one scoped to the project's team, with an expiry.
- **Added.** Calendly history (`yourtools/tool_calendly.py`): bookings 90 days back to 60
  ahead, upcoming, past, canceled, no-shows, booked in the last 7 days and the 7 before, and
  each event type's, read with a personal access token (Calendly API v2; the read scopes
  `users:read` and `scheduled_events:read`; option: the token's own bookings or the
  organisation's). It never makes, changes or duplicates a lead: the webhook adapter stays
  the only road for leads. The drawer says how many bookings the webhook also has and how
  many it does not, matched on the meeting's address and counted twice (withheld when the
  two counts differ). Not every page read: every count "Not given".
- **Added.** Resend (`yourtools/tool_resend.py`): contacts, subscribed and unsubscribed, each
  segment's contacts (Resend's audiences are now segments), and the delivery states of the
  newest 100 emails. Resend's keys are full access or sending only, and a sending-only key
  cannot read: the steps say so, and such a key is refused in plain words.
- **Added.** Names and emails a tool's answer holds (Calendly invitees, Resend contacts and
  recipients) follow the site's People settings, as leads do: none kept when the site keeps
  no identity, none past the People days, cut before the answer is stored; only the 10
  newest are kept at all, and only fields Skald reads (no answers to booking questions, no
  phone numbers, no subjects). Admins see them in the tool's drawer, each with a copy icon;
  members never.
- **Added.** Framework: a tool's drawer shows its own notes and lines Skald worked out;
  `latest_only` keeps only a tool's newest answer; the recount checks counted figures
  (Calendly, Resend) whole, keyed by figure, row and rank.
- **Added.** Marketing alerts (`alerts_marketing.py`, Settings › This site › Alerts ›
  Marketing): **A tool stopped answering** (no good answer for 26 hours), **Leads dropped**
  (the dashboard's leads over the last 7 whole days under 50% of the 7 before, when those
  were 5 or more), **Bookings dropped** (the same on Calendly's own figures), and **Google
  Analytics and the log far apart** (off by default: GA4's sessions against the log's visits
  over GA4's own 28 days, 2 to 1 or more either way, worded as different counting, never
  "wrong"). Each has its switch and is mailed like every alert, once while it stays open.
  Thresholds in config.yml (docs/SETTINGS.md). No new figure is counted: each rule reads a
  figure already counted twice, and stays silent when that figure is missing or withheld.
- **Added.** The Monday marketing mail (`mail_marketing.py`; Settings › This site › Mail &
  reports › **Monday marketing mail**, off by default): last week's visitors, pages read and
  leads from the log, each against the week before, and where visitors came from (the weekly
  mail's own figures), then one card per connected tool with its headline figures under
  "Counted from: <tool>", its own period and freshness ("Not given" for a figure the tool
  did not give; a withheld tool says so and shows nothing). Same recipients and mail server
  as the weekly mail; refused by design, like it, when the week is not whole.
- **Why:** the owner asked for the tools the marketing branch named, built on the checked
  framework, with alerts on the figures marketing watches. **Who:** owners and admins
  connect a tool or switch an alert; anyone on the site sees a tool's figures. **Do:**
  nothing; a tool shows only once connected, and the new alerts run only while alerts are on.
- **Checked.** Recorded-shape answers through fake openers, no network (`tests/fixtures/
  yourtools/vercel.json`, `calendly.json`, `resend.json`): each call GET only and its
  parameters, pagination, NULL for not given, each refusal's words with no key in them, the
  People rules (identity off, past the People days), the webhook match against a real leads
  file left unchanged, the recount matching and finding planted errors (a changed count, an
  extra row, a changed answer); each alert at and past its threshold, silent without its
  figure, once a day, mailed once; the Monday mail from a real history (the weekly mail's
  figures, each tool apart, Not given, withheld, a week not whole refused); node tests of the
  drawer and the alert areas. No real Vercel, Calendly or Resend account was called.

### From your tools: figures from your own tools, apart from Skald's

- **Added.** A framework for showing figures from a person's own tools, read with their own
  keys from the tools' free APIs, in their own area and never added to the log's counts
  (the `yourtools` package, docs/TOOLS.md, Help › Your own tools). Each tool is one file
  (`tool_<id>.py`). Each answer is kept exactly as it came (`yourtools.sqlite`, with its
  SHA-256), each figure with the place in the answer it was read from; after every sync a
  second, separate check (`yourtools/recount.py`, `ti.py tools audit`) reads every figure
  again and withholds the tool's figures on a mismatch. A figure the tool did not give is
  "Not given", never 0. Each tool has one state everywhere: Not connected, Paused, Needs its
  key, Waiting for its first answer, Answering, Last try failed (the last good figures stay;
  one mail per run of failures), Stopped answering (no good answer for 26 hours), Withheld.
- **Added.** Settings › This site › Leads & tools: each tool you connected is a row with its
  pill and its last answer; its drawer (`tool=your-<id>`) shows where its key is kept and
  whose it is (never the key), its options, Replace the key, Sync now (once in 10 minutes),
  Pause and Remove the key. **Connect a tool** now asks Who will do it? for the lead hook and
  your own tools (`setup=finish-tools`): Me pastes the key (`setup=tool-<id>`), My developer
  gets a message that says which key to make and where to paste it (never a key by mail), My
  AI agent gets the line. Settings › To do has one optional line per tool, so Finish set-up
  and Set up everything left include them.
- **Added.** Overview: a small card **From your tools** after What changed, one line per tool
  with its key figures, each labelled "Counted from: <tool>", the tool's own period, what the
  tool said about its answer (sampled, thresholded) and its freshness. None connected: one
  folded line.
- **Added.** The agent's job `connect-tools` (kit steps and llms.txt): the agent finds keys by
  their names only (`.env` names, key files), lists them, asks before sending each one, says
  the permission each needs (read-only first), and sends it on stdin to the new route
  `POST /traffic-kit/<code>/toolkey?tool=<id>`. The route takes a key only from a line an
  install admin made (checked again at the upload), never replaces a key unless asked
  (`replace=1`), has its own rate limit, and writes one audit row `tools.key` without the key.
  MCP: a read-only tool `your_tools`; `setup_line` takes the job `connect-tools`.
- **Added.** The CLI `ti.py tools status|sync|audit|connect|pause`, and the container's
  scheduler job `tools` every 6 hours (`SKALD_TOOLS_HOURS`, `0` off; first at
  `SKALD_TOOLS_AT`, 02:10), at a lower priority (nice +5) than every other job.
- **Added.** Google Analytics 4, the first tool (`yourtools/tool_ga4.py`): sessions, users,
  engaged sessions and key events over the property's own last 28 days (in its own time
  zone), and its top 10 landing pages and sources, read with the Google Analytics Data API.
  Users are GA4's own total, never added up. Thresholding, sampling and rows folded into
  "(other)" are shown as Google said them. The key: a service-account key file by default;
  or Skald's Search Console key (nothing new to make, one Viewer click in GA4); or an OAuth
  "authorized_user" file with a refresh token. A figure GA4 did not give is "Not given". Every
  answer is recounted whole by the second road. The site check now notes the GA4 `G-` tag and
  Calendly links it sees on the home page it already fetches (no new fetch), and Connect a
  tool shows the `G-` id. The set-up list gains one optional line, "Google Analytics connected". Overview's card says "Counted from: your server log" for Skald's
  figures and "Counted from: Google Analytics" for GA4's.
- **Why:** the owner's decision of 2026-10-27: Skald may show numbers from a person's own
  Google Analytics, Search Console, Vercel Web Analytics, Calendly and Resend, kept apart and
  checked like every other figure. **Who:** owners and admins connect a tool; anyone on the
  site sees its figures. **Do:** nothing to keep things as they are. A self-hosted front
  nginx made from DEPLOY.md's sample must widen the kit's POST location to
  `(report|hooksecret|searchkey|toolkey)` for the agent to hand Skald a tool's key
  (`docker/nginx.conf` has it); pasting a key in the page needs no change. **Checked:** unit
  tests with a fake tool (keys, states, store, sync, a failure, the recheck finding a changed
  figure, a changed answer and a 0 for nothing; the CLI; the scheduler's job), the route's
  tests (user agent, report key, job, install admin, 409 and replace, no key in any log or
  answer, its own limit), the dashboard routes by role, node tests of the page parts, the
  nginx test; GA4 with recorded-shape answers through a fake opener (the token's scope, the
  three request bodies, the window in the property's time zone, NULL for nothing, a changed
  figure and a missing row found by the recount, each refusal's words, the refresh-token
  road, the Search Console key); the full suite with and without PyYAML. No real Google
  property was called. Screenshots: docs/plans/tools-shots/.

### Recorded journeys: a site can send the sessions its visitors agreed to

- **Added.** An optional, signed receiver, `POST /traffic-hooks/<site>/journey` and
  `.../journey/withdraw`, for the sessions a website sends itself after the visitor accepts
  analytics: pages read, clicks, forms, sign-ups, bookings, downloads (docs/JOURNEYS.md). The
  page helper `/traffic-js/journeys.js` sends nothing and stores nothing before
  `skaldJourneys.consent(true)`; it posts to the site's own relay, which adds the visitor's
  address, signs with a per-site secret (HMAC-SHA256, 5-minute window) and passes it on, so
  the secret never reaches a browser. A Next.js relay is in the kit (`kit/journeys/`). Each
  event is checked against a fixed contract (version 1, UUIDs, no query strings, no email or
  phone in a label) and refused without consent; at most 16 KiB, with per-site and
  per-visitor rate limits. Privacy applies at the door, as for leads: the address kept in
  full, shortened or not at all (`privacy.keep_ips`), the email only with identity full.
  Retention follows the site: events go after `journeys.vid_days`, the address and email
  after `privacy.keep_days` when shorter, and nothing goes under keep-everything. A
  withdrawal always deletes the visitor's events and refuses late retries for 90 days (a
  keyed digest, never the ID). `ti.py forget` takes a person's recorded sessions too (by
  address, email or script tag visitor ID).
- **Added.** "Recorded by your site", labelled and never added to the log's counts: a card on
  Traffic › Visitors (its own sessions, visitors, pages read and actions, and the sessions,
  each opening a drawer, `rj=<ref>`); in the visitor drawer, for owners and admins, the
  sessions linked to that log visit and how (the script tag's visitor ID, or the same kept
  address inside the visit's time; never a guess); in the session drawer, the log's own
  visit. Settings › Leads & tools has one row, Recorded journeys (status pill, last event),
  and Connect asks Who will do it? (`rjc=connect`, `by=`): Me (make the secret, shown once),
  My developer (a message without the secret), My AI agent (the new agent job
  `connect-journeys`, which adds the helper and the relay to the site's code, asking before
  each change, and takes the secret once through `<code>/hooksecret`). The set-up checklist
  shows an optional Recorded journeys line once a site is connected; `doctor` has a line.
- **Added.** A second count, `audit_journeys.py` (run daily as `recorded_journeys`): from
  each event's raw JSON, with its own code, it checks the stored columns, consent, one
  visitor per session, no event kept for a withdrawn visitor, and recounts the period's
  figures. A period that does not match shows no figure ("Figures withheld").
- **Why:** the owner's decision of 2026-10-27: data a site sends may feed Skald, labelled by
  where it came from, stored raw with an independent recheck, and every set-up possible
  through the one-time agent line. **Who:** sites that choose to send it; nothing changes
  for a site that does not. **Do:** nothing until you want it; then Settings › Leads & tools
  › Recorded journeys › Connect. A server that runs nginx in front of Skald adds the journey
  location from DEPLOY.md (docker/nginx.conf has it). **Checked:** tests for the receiver,
  consent, privacy modes, withdrawal, retention with keep-everything, forget, the queries and
  the second count (tests/test_recorded_journeys.py); the agent job and its secret
  (tests/test_kit_agent_jobs.py); the page helper and the relay in node, their bodies checked
  by the Python contract and their signatures by the receiver's own check
  (tests/js/journeys-snippet.mjs, journeys-relay.mjs); the UI in node
  (tests/js/recorded-ui.mjs); both full suites, with and without PyYAML; screenshots with
  sample data in docs/plans/journeys-shots/.

## Older versions

- 2.42.0 (26 October 2026): [docs/CHANGELOG-2.42.md](docs/CHANGELOG-2.42.md).
- Website changes, 24 to 27 October 2026: [docs/CHANGELOG-website-2026-10.md](docs/CHANGELOG-website-2026-10.md).
- 2.39.0 to 2.41.0 (26 October 2026): [docs/CHANGELOG-2.39-2.41.md](docs/CHANGELOG-2.39-2.41.md).
- 2.36.0 to 2.38.0 (25 and 26 October 2026): [docs/CHANGELOG-2.36-2.38.md](docs/CHANGELOG-2.36-2.38.md).
- 2.35.0 and 2.35.1 (25 October 2026): [docs/CHANGELOG-2.35.md](docs/CHANGELOG-2.35.md).
- 2.32.0 to 2.34.1 (24 and 25 October 2026): [docs/CHANGELOG-2.32-2.34.md](docs/CHANGELOG-2.32-2.34.md).
- 2.27.0 to 2.31.1 (22 to 24 October 2026): [docs/CHANGELOG-2.27-2.31.md](docs/CHANGELOG-2.27-2.31.md).
- 2.23.0 to 2.26.0 (22 October 2026): [docs/CHANGELOG-2.23-2.26.md](docs/CHANGELOG-2.23-2.26.md).
- 2.21.0 to 2.22.3 (21 and 22 October 2026): [docs/CHANGELOG-2.21-2.22.md](docs/CHANGELOG-2.21-2.22.md).
- 2.14.0 to 2.20.1 (18 to 21 October 2026): [docs/CHANGELOG-2.14-2.20.md](docs/CHANGELOG-2.14-2.20.md).
- 2.8.0 to 2.13.0 (18 October 2026): [docs/CHANGELOG-2.8-2.13.md](docs/CHANGELOG-2.8-2.13.md).
- 2.7.1 and earlier (8 to 12 October 2026): [docs/CHANGELOG-2.0-2.7.md](docs/CHANGELOG-2.0-2.7.md).
