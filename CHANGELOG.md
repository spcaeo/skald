# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

Nothing yet.

## 2.44.1 (2026-10-28)

A webhook whose key does not match no longer loses its events, and the key's screen says the
truth. A refused delivery now says why: the tool sent no signature (its webhook was made
without a key) or signed with another key. Refused deliveries are held (24 hours on a client
site; until taken in on a site that keeps everything), and saving the right key takes them in
with their own times. Each tool uses its own word for its key (Calendly "signing key"), asks
first how its webhook was made, keeps the saved state on screen ("Signing key saved … by …"),
and **Test Skald's address** says it checks Skald's side only, beside the last real delivery.
A tool shows Connected only after a real delivery was accepted since the key was saved.

### Upgrade

- Nothing is required: no schema change, no new nginx line. Refused deliveries start being held
  from the upgrade on; ones refused before it cannot be taken in.
- A webhook made without a signing key (Calendly with a personal access token and no
  `signing_key`) must be made again with Skald's key: the tool's details give the requests.

### A webhook key that does not match no longer loses the events: refused deliveries are held

- **Keep everything:** on a site that keeps everything (internal and enterprise) the held
  deliveries are never deleted by age or count; they wait for the right key or a person's
  deletion request. Past 2,000 a hook no more are held. Client sites hold them 24 hours.
- **What:** a hook delivery refused for its key now says which way it failed: `unsigned` (the
  tool sent no signature at all: its webhook was made without a key) or `bad_signature` (it
  signed with another key), in the tool's own word for its key (Calendly "signing key", Stripe
  "signing secret", HubSpot "client secret", the others "secret"), with the fix for each. Either
  is held for 24 hours (raw, 0600, at most 200 a hook; never a test of Skald's own). When someone
  then pastes, makes or rotates the hook's key in Settings › Leads & tools, Skald checks every
  held delivery with it and takes in the ones that match, with the time each first came (logged
  `accepted_held`, counted like any accepted delivery); the answer says how many were held,
  matched and taken. Each tool now says when its key was saved, by whom and how, the last real
  delivery, and what arrived since. **Test Skald's address** says it proves the address only, and the
  set-up check turns good only after a real event was accepted since the key was saved.
- **Why:** a site's Calendly sent eight real bookings that Skald refused (the pasted key was not
  the one Calendly signed with), while all five of Skald's own tests passed: a test is signed with
  the key Skald has and posted to itself, so it can only prove the address. Calendly does not
  send a refused booking again, so no booking was kept. Calendly's signing key is optional with a
  personal access token and never shown again; a subscription made without one can only be made
  again with Skald's key, and Skald now says so.
- **Who:** every site with an incoming hook (Calendly, Cal.com, Stripe, Typeform, HubSpot, a lead
  or json sender). **What to do:** nothing. A hook whose deliveries were refused before the
  upgrade stays refused until its key is fixed; only refusals from the upgrade on are held.
- **Privacy:** held bodies are never logged, backed up or shown; `ti.py forget --email/--vid/--lead`
  deletes the ones holding that value, and clearing a site's data deletes its folder. Documented in
  docs/DATA-CONTRACT-CONVERSIONS.md ("Refused deliveries held").
- **Checked:** new tests (tests/test_hooks_held.py): unsigned and bad signature for every tool;
  hold, cap and the 24-hour purge; the right key takes the held deliveries in with their times and
  only once, a wrong key leaves them held, a test is never held; the deletion request; the tools
  list fields; the set-up check good only after a real accepted delivery; the audit's own road
  (audit_hooks_held.py: accepted_held in the delivery log against the spool's held lines, a held
  file past 24 hours, a held body with no refusal row). Full suite, also with PyYAML hidden.

### A tool's key in the tool's own word, kept on screen, and a Test that says what it proves

- **What:** a tool's details on Settings › Leads & tools and the Connect your leads dialog now call
  the key by the tool's own name (Calendly's **signing key**, Stripe's **signing secret**,
  HubSpot's **client secret**, **secret** for the others) and say once which way it goes ("Skald
  gives Calendly a signing key; Calendly signs each booking with it"). Calendly, Cal.com and
  Typeform ask one question first ("How was your Calendly webhook made?": not made yet, made
  with a `signing_key`, made without one or not sure), kept in the address as `how=`; a Calendly
  webhook made without a signing key gets the two requests that delete it and make it again with
  Skald's key, and **Let your AI agent do it**. After Save or Make the details stay open on
  "Signing key saved 28 Oct 10:16 by Ann (pasted)", with **Replace**, and the paste's answer in
  plain words: it matches (and how many held bookings were taken in), it is not the key the tool
  signs with, the tool sends no signature, or saved and waiting for the next one. **Send a test
  event** is now **Test Skald's address** and says it proves the address only, beside the last
  real delivery. A live line on top of the details says whether real deliveries work, with the
  next step under it. A row says Connected only after a real delivery was taken in since its key
  was saved, never on a passed test alone (a passed test alone now reads Waiting, not Ready).
  The help guides (Webhooks, Leads and conversions, If a connection does not work, Connections,
  Demo bookings) and the agent's lead job say the same, and no longer claim Calendly has no screen
  for webhooks.
- **Why:** on a site's Calendly the page said "secret" where Calendly says "signing key"; once
  saved, nothing on screen said a key was saved; Skald's own test passed (it signs its own sample
  with the key it holds) while every real booking was refused, so the hook looked fine and failed
  at once.
- **Who:** owners and admins connecting Calendly, Cal.com, Typeform, Stripe, HubSpot, their site's
  server, Zapier, Make or n8n. **What to do:** nothing. A Calendly webhook made without a signing
  key must be made again; its details say so.
- **Checked:** `tests/js/hook-key.mjs` (each state with stubbed helper answers: not made yet, saved
  and no match, matches and taken in, unsigned, an older server's answer; the set-up dialog's
  steps), `tests/js/setup-checklist.mjs`, `tests/js/set-leads.mjs`; both test suites (with and
  without PyYAML); the public sweep; screenshots of the Calendly details in each state
  (`docs/plans/hook-key-shots/`, sample data only). Needs the server side (`key_word`, `saved_at`,
  `since_saved`, `last_real`, `check`) for the times and answers; an older server shows none of
  them.

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

## Older versions

- 2.43.0 (27 October 2026): [docs/CHANGELOG-2.43.md](docs/CHANGELOG-2.43.md).
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
