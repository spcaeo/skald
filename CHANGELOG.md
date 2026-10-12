# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

## 2.2.3 (2026-10-12)

"Visitor IDs off" now holds on every road, and "abandoned" no longer counts a later booking
as a lost one.

### Fixed

- **A booking in a later session was counted as abandoned.** A finish matched a start only by
  visitor ID. Now the same person (the same email, when the site sends it) finishing the
  action within the window counts too.
- **Visitor IDs off did not cover every road.** A webhook's `vid`, and the lead database's
  `session_id`, were kept even with `beacon.visitor_ids` off. Now neither is kept: the hook's
  `vid` is dropped from the spool and the store, and the session column is read only with
  visitor IDs on. A site's session ID (often 30 minutes) is not a visitor, and had made a
  booking in a new session look abandoned.

### What to do

Nothing: upgrade (`docker compose pull && docker compose up -d`, or `sudo skald upgrade`). The
next daily run rewrites lead-database rows that held a session ID; outgoing webhooks are not
sent twice.

## 2.2.2 (2026-10-12)

Webhooks work on every install, and every install opens the dashboard. An upgrade does both
by itself.

### Fixed

- **Webhooks answered 502 unless the script tag was on.** The receiver for the signed tool
  hooks (Calendly, Cal.com, Stripe, Typeform, HubSpot, the generic `lead` hook) runs in the
  beacon helper, which started only with `SKALD_BEACON_ORIGINS` (Docker) or when enabled by
  hand. Now the Docker image always starts it, `install.sh` enables it, and `skald upgrade`
  switches it on when it was installed but off. Without allowed origins it takes hooks only:
  `/traffic-beacon` and `/traffic-js/skald.js` answer 404 until the site's origin is set.
- **A config without `dashboard.app` showed only the plain page.** Installs made from an
  older `config.example.yml` have no such key; it now means the web app. `app: false` keeps
  the plain page.

### What to do

- **Docker:** pull the new image and start the container again (`docker compose pull && docker
  compose up -d`). Nothing else.
- **Install script:** `sudo skald upgrade`, or let the upgrade timer do it. Nothing else.

## 2.2.1 (2026-10-12)

### Fixed

- **Docker and one-command installs showed only the plain page, not the dashboard.** The
  container's generated config and `config.example.yml` did not set `dashboard.app: true`, so
  the site's address served the no-JavaScript fallback page (no menu, tabs or drawers). Both
  now turn the web app on. Docker: pull the new image and start the container again. An
  install-script install keeps its own `config.yml`: add `app: true` under `dashboard:`.

## 2.2.0 (2026-10-12)

Alerts when AI assistants start or stop reading your pages; a suggested llms.txt; one-command,
safe upgrades and a notice when a new release is out; a live demo; faster pages. No figure changed.

### Added

- **Update notices, safe upgrades, explicit migrations, optional automatic upgrades** (issue #8).
  Once a day Skald asks GitHub for its latest release (one request, header `User-Agent:
  Skald/<version>`, nothing else; `updates.check: false` turns it off; offline it is silent). A
  newer release shows as a card in the daily and weekly mail and a line on the dashboard for
  owners and admins (dismissible per version; security releases in red); `skald updates` prints it.
  `skald upgrade [--to vX.Y.Z] [--dry-run]` installs a release on an install-script install: checks
  the tarball's SHA-256 against SHA256SUMS, refuses downgrades, major jumps without
  `--allow-major` and the daily run's window (`report.run_window`), copies and restore-tests every
  database, swaps the code (the old one stays in `/opt/skald.prev`), migrates, restarts the
  helpers, health-checks, and rolls the code and the databases back on any failure. `skald migrate
  [--check]` lists and applies each database's schema steps after a copy, recorded in
  `migrations.json`. `updates.auto: patch | minor` (default off) lets the new
  `skald-upgrade.timer` upgrade by itself and mail the result; never across a major. Docker
  images are now also tagged by major version (`:2`). Guide: docs/UPGRADING.md.
- **AI alerts: an assistant starts or stops reading a page** (issue #5). Three new alert rules,
  judged once a day on the last whole day: an assistant (by its company: GPTBot, OAI-SearchBot and
  ChatGPT-User are OpenAI) fetched a page it had not fetched in the 28 days before; an assistant
  that fetched a page in 3 of the 4 weeks before has not fetched it for 7 days; visits likely sent
  by an assistant jumped or vanished against its 28-day average ("too few to judge" below the
  thresholds, never an alert). Each alert names the assistant, the page, the days and the numbers.
  No new figure: they read figures already counted twice (each assistant's requests by page, and
  the likely-AI visits), and a withheld or missing day makes a rule wait, never fire. Shown on
  Alerts (new **AI** filter) and in **AI reading changes** on AI & crawlers; mailed like other
  alerts and listed in the weekly mail when alert mail is on; a new outgoing webhook event
  `ai.reading_changed`. Settings `alerts.ai_*` (on/off per rule and every threshold).
- **Deploy to Cloudflare button for the Skald Worker** (issue #4). `deploy/cloudflare-worker/` now
  deploys in one click: the button copies the folder into a new repository in your GitHub or
  GitLab account and deploys it to your Cloudflare account. It asks for `SKALD_INGEST_URL` and
  `SKALD_TOKEN` as secrets, with no default. The Worker is deployed with no route and no
  `workers.dev` address: add your site's route afterwards. New files: `wrangler.toml`,
  `.dev.vars.example`, `package.json`; `wrangler.toml.example` stays for a deploy by hand. In
  README, docs/HOSTING.md and docs/CDN-LOGS.md.
- **Suggested llms.txt** (issue #6). Skald suggests an `/llms.txt` (llmstxt.org format) from your
  site's real pages: those people and AI assistants read most over the last 90 recorded days,
  grouped by section, under their titles from the website's page list (or their paths). Private
  paths, paths robots.txt disallows, redirects and gone pages are left out; any day not recorded
  is named. On Settings > AI crawlers (preview, Copy, Download), `ti.py llms-txt [--site X]
  [--out FILE]`, the MCP resource `skald://sites/<site>/llms.txt` and `llms_txt.json`. No figure
  is published. Skald never writes to your website. Contract: `docs/DATA-CONTRACT-LLMS-TXT.md`.
- **A live demo on GitHub Pages** (issue #3): https://spcaeo.github.io/skald/. `tools/demo.py`
  runs 60 days of sample data for a made-up site on example.com (RFC 5737 addresses, made-up
  names; people, AI assistants and their user fetches, crawlers, bots, leads, bookings and
  payments, a saved funnel, in-page events) through Skald's own pipeline and writes the dashboard
  as static files. Seeded, so each build tells the same story. The new `pages.yml` workflow builds
  and deploys it on every push to main and again every Monday, so the demo's dates stay recent. In the demo the page needs no helper: a banner says it is
  sample data, Compare and page stories read answers worked out at build time, and refresh,
  saving and the settings pages say they need a running Skald instead of failing.

### Changed

- **Faster dashboards, page stories and live runs** (issue #2). On a history ten times the size
  of the first live install, the 2-minute live run takes 6.2 s instead of 9.4 s, the data files
  5.0 s instead of 7.7 s, and a page's story 131 ms instead of 327 ms. No figure changed: every
  data file, compare answer and page story is the same, byte for byte. New indexes through each
  database's normal upgrade (history schema 12, accounts 5, conversions 3), applied once on first
  open. A benchmark, `tools/bench.py`, and the results and reasons in docs/PERFORMANCE.md.
- The tracking additions to the data contract (day kinds, leads, goals) moved out of
  `DATA-CONTRACT.md` into `docs/DATA-CONTRACT-TRACKING.md`, linked from it.
- The README and "Why Skald" say how to say the name: "skawld", one syllable.

### Fixed

- Insights that tie now come out in the same order on every run (the title breaks the tie), so
  the list no longer reshuffles between two identical runs.
- Older code refuses to read a history file written by a newer Skald, with a message to upgrade,
  instead of reading it wrongly.

## 2.1.0 (2026-10-12)

AI clicks that lost their referrer, estimated and kept apart; Cloudflare on any plan; a guide for
sites on Vercel. Every new figure has its own second, independent count.

### Added

- **Likely sent by an AI assistant (inferred).** A visit with no referrer and no campaign tag that
  lands on a page an assistant's user fetcher (ChatGPT-User, Perplexity-User, Claude-User, ...)
  fetched in the same minute or up to 15 minutes before is shown as "likely" from that
  assistant: on Sources, AI & crawlers (with fetches followed by a visit, per assistant), Leads
  (by first and last touch), Conversions (by first touch) and a visitor's
  details. Two or more assistants count once, as "more than one". **An estimate, never a count:**
  every place says "likely", with an (i) that gives the window, and it is never added to the AI
  assistant source, to people or to any other figure. Settings `attribution.ai_likely` (on) and
  `attribution.ai_window_minutes` (15). The user fetches it rests on are kept 180 days as minute,
  assistant and page only: no address, no user agent. Counted a second time by
  `audit_ai_likely.py`, `audit_leads.py` and `audit_conversions_figures.py`; a day that differs is
  withheld. Contract: `docs/DATA-CONTRACT-AI-LIKELY.md`.
- **The Skald Worker for Cloudflare, on any plan** (`deploy/cloudflare-worker/`). It passes each
  request on unchanged and, after the response has gone out, posts one edge record to
  `/traffic-ingest/<site>?format=edge`, so pages served from Cloudflare's cache are counted. New
  log format `edge_json`; its own rate limit (`ingest.edge_per_minute`, `ingest.edge_burst`); a
  record posted twice is read once; the independent audit reads edge records too.
- **An example Netlify Edge Function** (`deploy/netlify-edge-function/`) that posts the same
  record, for a Netlify site without Log Drains.
- **`docs/VERCEL.md`:** step by step for a site on Vercel, from zero to a working dashboard, and
  what each Vercel plan lets Skald see. Linked from the README, `docs/HOSTING.md` and Help.
- **Help:** "Likely from an AI assistant" in Leads and conversions, two new questions in the FAQ
  (what "likely" means; Cloudflare's cache), and "Your site on Vercel, Netlify or behind
  Cloudflare" in Getting started.

### Changed

- **Never a request counted twice with the Worker.** With `logs.edge_only_cached` (true unless
  the site's format is `edge_json`), Skald keeps only the Worker's cache hits when it also reads
  the server's log: any other cache status may have reached the server.
- `leads.json` gains the `likely_ai` column (just before `n`); `ai_activity.json` and each
  `conversions.json` day gain `likely_ai`. Existing fields are unchanged.
- The README's feature list, the comparison and "Why we built Skald" mention the estimate, the
  log drains and the Worker.

### Fixed

- A table with one row says "1 row", not "1 rows".

## 2.0.0 (2026-10-11)

The first public release. Skald grows from a traffic report into a platform: accounts, results,
agents and integrations. **Every new part is off until an install switches it on**, so an existing
install works as before. Every new figure has its own second, independent count.

### Added

- **Accounts (sessions mode).** Sign-in with email and password, organisations, owner, admin and
  viewer roles, invites, forgotten-password links, two-step sign-in (TOTP with recovery codes),
  "Keep me signed in", Show/Hide on password fields, and an audit log with CSV export.
- **Settings in the dashboard.** Retention windows (a shorter window says first what it will
  remove), mail and SMTP, sites, internal addresses, AI crawler policy, integrations and the
  organisation's security rules. Secrets typed there are write-only and kept in a 0600 file.
- **Conversions.** Signed webhooks from Calendly, Cal.com, Stripe, Typeform, HubSpot, Zapier (and
  Make, n8n, any script) and the site's own server; the site's lead database read as conversions;
  started, completed and abandoned forms and bookings; a Conversions page. Anonymous by default.
- **Outgoing webhooks** to a CRM, Zapier, Make or Slack: signed, HTTPS only, retried, never with a
  name or email.
- **The `skald.js` script tag** (under 6 KB): page views, form steps, phone, mail and outbound
  clicks, 75% scroll, copies, 404 views, and Calendly, Cal.com and HubSpot meeting bookings.
  Respects Do Not Track and GPC; consent mode; optional anonymous visitor IDs (off by default).
- **MCP server** with 13 read-only tools for Claude, ChatGPT and other agents, over Streamable HTTP
  with a scoped token, or stdio on the server.
- **Better tracking.** Leads by first and last source over any range, crossed with the team's lead
  status; time from first visit to lead; every saved funnel counted daily by source and device;
  engagement and returning visitors by source; goals from events per 100 visits; campaign tag
  problems; exit rate per page; a Yesterday period.
- **Logs from other servers.** `skald-ship`, one standard-library file, sends new log lines over
  HTTPS with a token that can only add lines to one site. Sites can be added from the dashboard and
  must prove their domain first.
- **Scoped API tokens** (`read`, `read_private`, `mcp`, `ingest`) per organisation.
- **A failure mail.** A failed morning run sends one short mail; a withheld day sends none.
- **A new menu** grouped by what you came for: Home, Audience, Results, AI & bots, Site & server,
  with Settings in its own menu. In-app Help pages, a drill-down drawer, a command palette, and a
  phone layout with a drawer menu.
- **A hosted layer** (sign-up, plans and limits, Stripe billing). Built and tested, **off**; Skald is
  not sold as a service today.
- **Public project files:** Elastic License 2.0, security policy, contributing guide, code of
  conduct, CI, Docker image and install script.
- **Four ways to install** (Docker, Docker Compose with an HTTPS profile, `install.sh`, manual)
  and a hosting guide (`docs/HOSTING.md`): Render (with a Deploy button), Railway, Fly.io,
  Kubernetes and a VPS for Skald; nginx, Apache, Caddy, Vercel, Netlify, Cloudflare, CloudFront,
  Fastly and WordPress for your site, with what each loses without a log.
- **Vercel and Netlify log drains:** `POST /traffic-ingest/<site>?format=vercel|netlify`, with
  Vercel's signature checked; a request sent twice is stored once; the audit re-reads them.
- **Real visitor addresses behind a platform's proxy** (`SKALD_TRUSTED_PROXIES`,
  `SKALD_REAL_IP_HEADER`); nobody is trusted by default.

### Changed

- The product, command, package and paths are all named `skald` (command `skald`, package `skald`,
  `/opt/skald`, `/etc/skald`, `/var/lib/skald`).
- Python 3.11 or newer is required (tested on 3.11 to 3.14).
- A browser-looking visit that loads no page assets is counted as a bot, with its own audit road.

### Security

- Fixes from two security reviews: strict path parsing at nginx's sign-in check (an encoded `..`
  could reach another organisation's files), sign-in floods counted before the password check and
  password checks capped, the helper never trusts identity headers in sessions mode, sites prove
  their domain, and new mail recipients confirm by link.

## 1.0.0 (2026-10-08)

The first release, used privately on one production website.

### Added

- **The report from logs.** Every request in one of five groups (people, AI assistants, search
  engines, bots and scanners, your own traffic) that add up to the log exactly, or the report
  refuses to send.
- **AI split by reason:** training, answering someone live, or a person clicking a citation.
- **Daily history** in SQLite (totals and labels only), a dashboard, and daily and weekly HTML mail.
- **"Today so far"**, redrawn every 2 minutes, and a Requests feed of the last 6 hours with the rule
  that placed each request, in words.
- **An independent audit** that recounts every figure from the raw log; a day that disagrees is
  withheld.
- **Breakdowns** by country, browser, system, device, source, campaign, landing page and hour;
  anonymous visits and journeys; returning visitors by keyed hash.
- **Verified crawlers** (owner address lists and DNS), with fakes filed as "claims to be".
- **Alerts:** site down, logging stopped, 5xx, 404 surge, crawler burst, new crawler, traffic drop.
- **Data quality** panel, deploy and change markers, nightly restore-tested backups, `forget --ip`.
- **Funnels**, leads by source, drill-down, compare any two ranges, page stories, reports as HTML or
  CSV zip.
- **AI crawler settings** (allow, block, block training only) and robots.txt beside each crawler.
- **CDN logs** (Cloudflare, CloudFront, Fastly), page speed, a read-only API,
  named users and roles, several sites in one install, and the optional event beacon.
