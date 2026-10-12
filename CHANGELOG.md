# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

Nothing yet.

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
