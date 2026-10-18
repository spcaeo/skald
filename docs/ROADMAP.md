# Roadmap

What turns skald from an honest daily report into an analytics
tool a business can run on. Everything here was **beyond the release of
2026-10-07**; the tables "Release 2", "2.0.0" and "2.1.0 to 2.5.0" below say what
has been built since. EDGE-CASES.md has the
evidence (entry ids like A5 or H12 point there).

Written 2026-10-07. State brought up to 2.5.0 on 2026-10-12. The P0, P1 and P2
sections further down are the plan as written then; the tables say what of it is done.

## Where it stands

| Shipped by 2026-10-07 | Shipped next, in 1.0.0 (2026-10-08) |
| --- | --- |
| Five groups that add up to the log, or nothing is sent | Per-visit journeys (7 days) |
| Readers headline; answer-engine tiers; citations per visit | Hourly charts, day x hour heatmap |
| Daily history, dashboard, daily and weekly mail | Interactive filters (country, path, source, device, browser, view, UTM) |
| Today so far (2 minutes), Refresh now | Multi-tab app with animations |
| Views by path (one per country or language) | Internal tab: office addresses by label, uptime from heartbeat, response times |
| Breakdowns: country, browser, OS, device, source, referrer, campaign, landing page, hour | Editable internal list, "add my address" |
| Site health: status per group, 404s, 5xx, speed, posts | Broken links report: fixed badges, probe grouping |
| CSV/JSON export with filters | Latest AI activity: address, flag, repeats, times seen in 30 days |
| Independent audit recount every day | Returning visitors (keyed 30-day hash) |
| | Insights tab: Working, Dropped, New, Gone, Anomalies, Opportunities (median + MAD baselines, minimum volumes) |
| | Per-page drill-down |
| Partial days, unreadable-line gate, schema upgrades with backup | Full UTM, click-id and referrer capture |

## How to read the table entries

- **Effort:** S = up to a day, M = 2 to 5 days, L = 1 to 3 weeks (one developer, tests included).
- **Risk:** what could go wrong building or running it.
- **Depends on:** what must exist first.

Every item keeps the standing rules: figures reconcile or are withheld;
requests are never reported as people; no address or agent of a person is
stored beyond what the item states; standard library on the server.

---

## Release 2 (2026-10-07): what of this list is done

| Item | State |
| --- | --- |
| P0-1 Clean the people number | Partly: .xsl/.pdf/media not pages, Lighthouse/PTST/GTmetrix bots, legacy paths not probes, link previews to bots. Still open: HEAD as page view, `/pricing` = `/pricing/` in lists, `%xx` decoding, short-link path exclusion, command-injection query shapes, joined referrers, "likely internal" suggestions. |
| P0-2 Verified bots | Done (owner lists for Google, Bing, Apple, OpenAI, Perplexity, Anthropic, DuckDuckGo; Meta by network; DNS for Yandex and as fallback). Baidu not yet. |
| P0-3 Alerts | Done from the live run (site down by heartbeat, logging stopped, 5xx, 404 surge, crawler burst, new crawler, traffic drop). Still open: an outside uptime check, "day withheld / report not sent" to a second address. |
| P0-4 Backups | Nightly + weekly, restore-tested on each run. Off-server destination: owner's decision. |
| P0-5 Data quality | Panel done (`quality.json`). `$request_id` in the log since 2026-10-08 (repeats dropped, `duplicates_removed`); prefetch headers not added. |
| P0-6 Goals from leads | Done as `leads.json` (CMS read-only, aggregates). |
| P0-7 Privacy | Retention table and `skald forget`. Key rotation not done. |
| P1-1 Funnel | Done inside `leads.json` (log steps beside CMS steps). |
| P1-3 Markers | Done (`markers.json`). Owner notes not yet. |
| P1-7 Network and burst signals | Flags done (hosting networks, fan-out, bare Mozilla); nothing is moved. |
| P2-9 "Shared in chat" | Done as link previews by app in `bots.json`. |

## 2.0.0 (2026-10-11): what more of this list is built

Built on 2026-10-11 and released as 2.0.0 (live on example.com since release 165;
HANDOVER/00-START-HERE.md says what runs now). Each new part is off until an install
switches it on. Designs: [plans/](plans/).

| Item | State |
| --- | --- |
| P0-3 Alerts | A failed morning run sends one short mail (`skald notify-failure`); a withheld day sends none. Still open: an outside uptime check. |
| P0-6 Goals and conversions | Built well past the plan: leads by first and last touch over any range, crossed with statuses (lead quality), time to convert; goals from beacon events (`beacon.goals`); conversions from signed webhooks (Calendly, Cal.com, Stripe, Typeform, HubSpot, Zapier, the site's own server) and from the lead database; abandoned forms and bookings; the Conversions tab; outgoing webhooks (docs/INTEGRATIONS.md). Each with its own second count. |
| P0-7 Privacy | Retention windows per site in Settings; `skald forget` (--ip, --email, --vid, --lead); since 2.4.0 visits kept with their address and leads' emails (a switch, off on upgraded installs), the person search for admins, audit-logged. Key rotation still not done. |
| P1-1 Funnel | Funnel history: each saved funnel counted every day by source and device, with drop-off, the pages after leaving a step and time to go through. |
| P1-4 Access control and audit log | Accounts (sessions mode): organisations, roles, invites, resets, two-step sign-in, an audit log with CSV export (docs/ACCOUNTS.md). |
| P1-8 Counting refinements | Exit rate per page; campaign tag problems flagged. The four listed refinements are still open. |
| P1-10 API hardening | Organisation tokens with scopes (`read`, `read_private`, `mcp`, `ingest`). |
| P2-4 Multiple sites | Sites added from the dashboard, owned by an organisation; logs shipped from another server (docs/INGEST.md). |
| P2-6 Lead journey | Built the privacy way: an anonymous visitor ID per browser (off by default) joins page views to a conversion; never a name unless the site turns identity on, never matched by address. |
| P1-9 Tests and CI | Done: GitHub Actions on every push (Python 3.11 to 3.14, the JS checks); 1,826 tests at 2.5.0. |
| Not on this list | An MCP server for AI agents (docs/MCP.md); settings in the dashboard (docs/SETTINGS.md); a hosted layer with sign-up, plans and Stripe billing, off (docs/SAAS.md). |

## 2.1.0 to 2.5.0 (2026-10-12): what more is built

All released and live on example.com (public/CHANGELOG.md has each version).

| Item | State |
| --- | --- |
| P0-3 Alerts | AI alerts (2.2.0): an assistant starts or stops reading a page, likely-AI visits jump or vanish; the failure mail, too. Still open: an outside uptime check. |
| P0-6 Goals and conversions | Leads and demos booked on Overview, Live, Sources, Pages, Locations, Insights and Compare, each counted twice (2.5.0). |
| P0-7 Privacy | Keeping IPs and lead emails is a setting (2.4.0): `privacy.keep_ips`, `privacy.keep_days` (395), `conversions.identity`; on for new installs, off for upgraded ones until turned on (docs/SETTINGS.md). Key rotation still not done. |
| P1-2 Free period comparison | Done since 1.0.0 (compare any two ranges); 2.5.0 adds leads and demos to it. |
| P1-5 Scheduled reports | Partly: a printable report of any tab (print or save as PDF), a CSV zip, `skald report`. No scheduled monthly mail. |
| P1-11 Saved views | Done (saved filter sets, in the command palette). |
| P2-1 Performance | Partly (2.2.0): new indexes, live run and data files about a third faster; `tools/bench.py`, docs/PERFORMANCE.md. Incremental reading not built. |
| P2-6 Lead journey | Built (2.4.0): with `privacy.keep_ips` on, each visit is kept with its address, and the person search (admins, audit-logged) links visits, leads and conversions. |
| P2-10 AI crawler policy view | Done (allow, block, block training only, with robots.txt beside each crawler); plus a suggested llms.txt (2.2.0). |
| Not on this list | Likely sent by an AI assistant, an estimate kept apart (2.1.0); the Cloudflare Worker and Vercel/Netlify drains; safe upgrades and update notices (2.2.0, docs/UPGRADING.md); flags beside countries and a new visit per outside source (2.3.0); `skald doctor` (2.4.0). |

## After 2.13 (2026-10-18): what more is built

On a branch, not yet released.

| Item | State |
| --- | --- |
| P1-6 Search Console and GA4 cross-checks | Search Console part done (2026-10-18), with Bing Webmaster Tools too. Synced by their APIs every 6 hours, not imported once: clicks, impressions, CTR and position per day by query, page, country, device and search appearance (Bing: per day, and its top queries and pages), stored in history (`search_days`, schema 14). The last 4 days are fetched again on each sync; provisional days are shown as such; a 3- or 16-month backfill on connect. Connected from the dashboard (Settings > Integrations > Search: upload the service-account key, add the robot in Search Console, find the property, test, connect). Traffic > Search shows the tables, the trend and the cross-check: Search Console clicks beside Skald's people from Google search, by day and landing page, never forced to match, flagged when the ratio moves sharply. Second roads: `audit_search.py`, `audit_search_landing.py`. docs/INTEGRATIONS.md, "Search Console and Bing". **GA4 users and sessions: still open.** |
| AI answers (new) | Done (2026-10-18). What ChatGPT, Perplexity, Gemini and Claude say for the questions buyers ask, asked through their APIs with the install's own keys (Settings > Integrations), per tracking profile (place, language, questions, brand terms, competitors, assistants, daily/weekly/monthly, 1-5 tries, a daily cap; Settings > AI answers; nothing erased). Per run and assistant: named, own pages cited, competitors, citation rank; recounted by `audit_ai_answers.py`, a run that does not match withheld. AI & bots > AI answers: the cited -> read -> sent -> converted chain, share of voice per run, the profile x assistant matrix in "x of N tries", questions, competitors, the cost estimate. docs/AI-ANSWERS.md. **Open:** a Google Business Profile link per profile (`gbp_location_id` is kept, unused); the leads step is per page, not yet per assistant. |

## Recommended next (top 10)

In order, as written on 2026-10-07. The first five make the numbers we already show
trustworthy; the next five make them useful for growth. The state at 2.5.0 is in brackets.

1. **P0-1 Clean the people number** - the site's own team and AI agents, plus a dozen one-line fixes found in a real log. (Partly; the open fixes are listed under Release 2.)
2. **P0-2 Verified bots** - reverse DNS and published IP ranges, so "GPTBot" means GPTBot. (Done; Baidu not verified yet.)
3. **P0-3 Alerts by email** - site down (checked from outside), errors, broken-link surge, logging stopped, crawl burst, new AI assistant. (Done, except the outside check.)
4. **P0-5 Data-quality monitor and log format** - request id, prefetch and fetch headers; duplicates, gaps, skew. (Done; prefetch headers not added.)
5. **P0-4 Off-server backups and a tested restore.** (Restore-tested backups done, on the same server; off-server is the owner's decision.)
6. **P0-6 Goals and conversions from leads** - leads by first-touch source and AI assistant beside readers by source. (Done.)
7. **P0-7 Privacy rules for what this release stores** - key rotation, retention, deletion requests. (Done, except key rotation.)
8. **P1-3 Annotations and deploy markers** - every deploy and rule change on every chart. (Done.)
9. **P1-7 Network and burst signals** - data-centre browsers and many-address crawlers. (Flags done; nothing is moved.)
10. **P1-1 Funnel** - landing to pricing to form to lead. (Done.)

---

## P0 - do next

### P0-1. Clean the people number
- **Why:** one unlisted address (very likely the site's own team, working from another country) made 17% of all requests and is counted as people; the team's own Claude Code fetches are counted as "someone asked an AI" (EDGE A5, A6). Plus fixes from reading the real log: bare `Mozilla/5.0` as bots (A11); Lighthouse, PageSpeed, WebPageTest, GTmetrix tokens (A9); HEAD never a reader's page view (B4); `.xsl` as an asset and PDFs as downloads (B8); `/pricing` = `/pricing/` in lists (C2); decode `%xx` before probe matching (C3); a `legacy_paths` setting so the old site's `/wp-content/uploads/` is not a probe (C7); exclude another service's short links on the same host (C9); the site's own address as referrer is "this site" (C10); command-injection shapes in `PROBE_QUERY` (C12); first URL of a joined referrer (E5).
- **Also:** "likely internal" suggestions on the Internal tab: addresses with 5+ browser identities and a large share of a day, or that also send the team's own tools' agents. An admin accepts or dismisses; nothing is listed automatically.
- **Effort:** M (each fix is S, with a test each). **Risk:** a rule that is too broad hides a real reader; every rule needs a "stays people" test next to its "becomes bots" test. **Depends on:** the editable internal list (this release).

### P0-2. Verified bots
- **Why:** every engine name today is a claim. meta-externalagent made 31% of today's requests with no reverse DNS; ChatGPT-User came from addresses that cannot be checked by DNS (A2, A3).
- **What:** reverse-then-forward DNS for Google, Bing, Apple, Yandex, Baidu; published range files for Google, Bing, OpenAI (GPTBot, SearchBot, ChatGPT-User), Perplexity, Apple; network (ASN) for Meta. Each fetch is labelled verified / failed / not verifiable. A failed claim moves to bots as "claims to be X". Range files fetched once a day by a separate step, kept with their date; DNS results cached per address per day; parsing never waits on the network.
- **Effort:** M. **Risk:** vendor lists change format or go missing - keep the last good copy, and an unreachable list must never move a fetch to bots. **Depends on:** nothing; P1-7 reuses the ASN database.

### P0-3. Alerts by email
- **Why:** today the only alert is a failed cron run. Nobody noticed a 34-minute crawl burst; nobody would notice the site being down at night (EDGE A8, F1, F2, H3, H9, I7).
- **Insights:** the anomalies Insights finds (this release) are candidates for alerts, but only after they meet the fatigue rules in EDGE K5.
- **Alerts:**
  - Site down: an outside check (a free uptime service or a cron on another server) hitting `/` every minute; down after 2 failures.
  - Logging stopped: newest log line older than 15 minutes on a live run (the heartbeat guarantees one every 5).
  - 5xx surge: more than N 5xx in 10 minutes.
  - 404 surge: people's 404s per hour above 3x the 14-day median, with the top paths; extra line if a deploy happened in the last hour.
  - Traffic drop: readers by noon below half the same weekday's median (only once 4 complete weeks exist).
  - Crawl burst: one agent over 1,000 requests in 10 minutes, or one address over 500.
  - New AI assistant: an agent never seen before that looks like an assistant (A4).
  - Report not sent / day withheld: to a second address, not the inbox that failed.
- **Rules:** one mail per alert per hour at most; a "resolved" mail; every alert names the figure, the threshold and a link.
- **Effort:** M. **Risk:** alert fatigue - start with down, logging stopped and withheld only; add the rest after two quiet weeks. **Depends on:** mail (exists), P1-3 for the deploy line.

### P0-4. Backups and restore
- **Why:** the history is the only state that cannot be rebuilt (logs keep 14 days). Today its backups sit on the same disk.
- **What:** nightly `sqlite3 .backup` copied off the server (another server, or object storage), 30 daily + 12 monthly copies; a monthly restore test into a scratch directory that runs `skald` against it and compares totals; the site's own database the same way if nothing else backs it up.
- **Effort:** S. **Risk:** backups that hold the 30-day returning hashes are personal data - encrypt them, and keep the hash key out of the backup (P0-7). **Depends on:** a destination and its credentials (owner decision).

### P0-5. Data-quality monitor and a richer log format
- **Why:** `verify` proves sums, not inputs. Real faults found: a format switch, 58 identical lines, no way to tell a prefetch from a visit (H2, H4, B2, H12).
- **What:** add to the nginx format `$request_id`, `$msec`, `$http_sec_purpose`, `$http_purpose`, `$http_sec_fetch_mode`, `$http_sec_fetch_dest`, `$http_next_router_prefetch` (parser and its layout test changed in the same commit). A "Data quality" panel per day: lines, unreadable share, duplicates, heartbeat count (expected 288), coverage start and end, clock skew (newest line vs server time), distinct addresses per 1,000 requests (catches a proxy put in front, D6), format(s) seen, rules version. Discard a live snapshot that has fewer lines than the previous one for the same day (H8).
- **Effort:** M. **Risk:** a log format change is a production nginx change - test with `nginx -t`, deploy at a quiet hour, and expect one day with two formats (handled). **Depends on:** nothing.

### P0-6. Goals and conversions from leads
- **Why:** the question that matters is "which sources bring leads", and the answer is split across two systems: readers in the logs, leads in the CMS with first touch, last touch and AI assistant.
- **What:** the website writes a daily **aggregate** file (no names, no emails, no session ids): leads per day by type (sign-up, contact, early access, demo opened, demo booked), status (excluding spam and duplicates), first-touch source type, AI assistant, landing path, locale. skald reads it and shows a Goals tab: leads beside readers by source and landing page, conversion rate where both are whole days, demo bookings by AI assistant.
- **Rules:** never join a lead to a visit; label "first touch (lead's browser)" separately from "source of the visit" (E7); a day without the leads file shows "not recorded", never zero; spam and duplicates excluded the same way as the leads export.
- **Effort:** M (S on the website: an export mode; M here). **Risk:** small numbers - one or two leads a week make rates meaningless; show counts first, rates only past a minimum. **Depends on:** the website's leads export (exists, `leads:export`), a shared directory both can read.

### P0-7. Privacy rules for what this release stores
- **Why:** this release adds a returning-visitor hash kept 30 days and machine addresses on the AI tab. The first is pseudonymous personal data under GDPR and PIPEDA (EDGE J1-J5).
- **What:** HMAC key in its own file (0600), outside history and outside backups, rotated every 30 days; hashes deleted after 30 days on each collect; addresses shown only for machine groups, never for people or citation clicks; query values dropped except attribution keys, and any path with `@` stored as a placeholder; a written retention table (raw logs 14 days, journeys 7, hashes 30, aggregates kept) and a deletion-request procedure in the SOP; the website privacy page names server-log analytics.
- **Effort:** S to M. **Risk:** getting this wrong is a legal problem, not a bug. **Depends on:** the returning-visitor work in this release.

---

## P1 - next quarter

### P1-1. Funnel
- **Why:** where do readers drop off between landing and a lead.
- **What:** fixed steps per day: landed -> read a second page -> saw pricing -> opened a form page (`/signup`, `/contact`, Book a demo) -> sent a form (POST from that visit) -> lead (from P0-6, aggregate). Built from journeys for the log steps (each visit is one row), so steps are visits, not requests; the last step comes from the leads file and is shown as a separate bar, not divided per visit.
- **Effort:** M. **Risk:** client-side navigation hides steps (B3) - every step is a floor and must say so. **Depends on:** journeys (this release), P0-6.

### P1-2. Free period comparison
- **Why:** Insights (this release) compares against a rolling baseline; the owner will also want "this week vs the week of the launch post" and other chosen ranges.
- **What:** compare any two ranges of equal length (this week vs last, vs same week last month), weekday-aligned; arrows only when both are whole and the change clears the same noise rules Insights uses (EDGE K1, K2), so the two never disagree about whether something moved.
- **Effort:** S. **Risk:** low. **Depends on:** history (exists).

### P1-3. Annotations and deploy markers
- **Why:** tie changes in the numbers to what we did (I1, I2, H10, H11).
- **What:** the site's deploy script appends `time, version, build` to a markers file; skald adds its own markers for rule changes ("rules v12: verified bots") and for any `backfill --force` (old and new totals kept). Shown as vertical lines on every chart; owner can add a text note ("LinkedIn post", "launch announcement"). A "stale build file" 404 group that resets at each deploy.
- **Effort:** S. **Risk:** low. **Depends on:** a one-line change in the website deploy script.

### P1-4. Access control and audit log
- **Why:** one shared basic-auth password; once marketing or an agency looks, we need named users, and the AI tab shows addresses.
- **What:** named users in the htpasswd file at minimum; roles (owner: everything incl. Internal and addresses; viewer: no addresses, no Internal tab, no settings); an access log of who opened which tab and who changed the internal list. Simplest path: nginx `auth_request` to a tiny local helper (like the refresh helper) that maps the user to a role and writes the audit line.
- **Effort:** M. **Risk:** a homemade auth bug exposes the dashboard - keep nginx basic auth as the outer lock, roles only inside it. **Depends on:** the editable internal list (this release).

### P1-5. Scheduled reports
- **Why:** someone outside the dashboard (a partner, an investor, the team) wants a monthly page.
- **What:** monthly mail and a PDF built from the same figures (one renderer, so they cannot drift); several recipients per report with their own role (no addresses for viewers).
- **Effort:** M (PDF without new server packages is the hard part: render HTML and print from a desktop browser, or accept one dependency). **Risk:** a PDF that disagrees with the dashboard - build both from one stored period. **Depends on:** P1-4 roles.

### P1-6. Search Console and GA4 cross-checks
- **Why:** logs cannot see impressions or queries; GA cannot see bots. Each checks the other.
- **What:** daily import of Search Console clicks and impressions by page and query, and GA4 users and sessions by day, through their APIs with a service account. A "cross-check" row: readers vs GA4 users (expect GA lower: blockers, consent) and search-referred readers vs Search Console clicks. Flag when the ratio moves sharply - that is usually a tracking break.
- **Effort:** M. **Risk:** API credentials on the server; quota; GA4 sampling. **Depends on:** a Google service account (owner).
- **State (2026-10-18):** the Search Console part is done, with Bing too (table above, "After 2.13"). GA4 is still open.

### P1-7. Network and burst signals
- **Why:** browser-shaped crawlers from data centres and fan-out crawlers pass as readers (A1, A15, A16).
- **What:** DB-IP Lite ASN database next to the country one; "data-centre browser" label; a fan-out flag (many addresses, one agent, seconds apart, one page each, no assets). Shown first as flags with counts; moved to bots only after a fixture of a real shared-link burst proves the rule leaves it alone.
- **Effort:** M. **Risk:** VPN users exit from data centres - the render test keeps them people. **Depends on:** P0-2 (shares the network lookup).

### P1-8. Counting refinements
- GoogleOther and Google-InspectionTool on their own lines, out of the indexing figure (A10).
- A 304 for an HTML page from a rendering browser counts as a page view (B5) - decide, document, test.
- IPv6 visitors keyed by /64 (D3), before the site gets an AAAA record.
- UTM and referrer aliasing beyond assistants: `linkedin`/`linkedin.com`/`li`, case (E6).
- **Effort:** S each. **Risk:** each changes a stored figure - pair with a P1-3 rule marker. **Depends on:** P1-3.

### P1-9. Tests and CI
- **Why:** 314 tests run only when someone remembers; two agents are changing the code at once.
- **What:** GitHub Actions on push: Python tests on 3.10 and 3.12, the JS app's tests, the audit against the fixtures, a check that no domain or address appears in `skald/`. A redacted real-day fixture (addresses replaced by stable fakes) as a regression test, refreshed monthly.
- **Effort:** S. **Risk:** a real-log fixture leaking data - fake every address and drop query values before it is committed. **Depends on:** nothing.

### P1-10. API and export hardening
- **What:** read-only JSON endpoints behind the same auth (the export tables plus `/live`); streamed CSV with a row cap and a "truncated at N" line; formula-looking cells escaped (I3).
- **Effort:** S to M. **Risk:** an endpoint that bypasses roles - same role check as P1-4. **Depends on:** P1-4.

### P1-11. Saved views
- **What:** a filter set saved by name ("Canada French, LinkedIn, mobile"), shareable as a link (state in the URL, no server storage needed), listed in the app.
- **Effort:** S. **Depends on:** interactive filters (this release).

---

## P2 - later

### P2-1. Performance at 10x and 100x
- Today: about 22,000 lines a day; the live run re-reads today every 2 minutes in about a second.
- **10x (220k lines a day):** fine as is. Live run a few seconds; wrap it in `flock`.
- **100x (2.2M lines, ~600 MB a day):** re-reading today every 2 minutes stops working. Needed: incremental reading (remember file inode and byte offset, read only new lines), per-minute pre-aggregates for today, SQLite in WAL mode, an index on the returning-hash table (~1M rows over 30 days), dashboard data split per tab and paginated. Raw parse stays standard-library Python; consider DuckDB only if the project drops the standard-library rule.
- **Effort:** L. **Risk:** incremental reading across rotation (renamed file, same inode) is the classic bug - test rotation mid-read. **Depends on:** P1-9.

### P2-2. Raw log archive for re-counts
- Keep compressed raw logs off the server for 90 days (addresses replaced by the rotating HMAC, agents kept) so new rules can be applied further back than 14 days. **Effort:** S. **Risk:** personal data; covered by P0-7's retention table. **Depends on:** P0-4, P0-7.

### P2-3. Relay, VPN and Tor labels
- Apple Private Relay egress ranges, Tor exit list, VPN via ASN; country shown as "via relay" where known (D2). **Effort:** S. **Depends on:** P1-7.

### P2-4. Multiple sites in one app
- A site switcher and a combined "all sites" overview; a short-link domain and an app domain as their own sites with their own rules. **Effort:** M. **Depends on:** this release's app.

### P2-5. Cohorts and retention
- Readers grouped by first-seen week, returning in later weeks; limited to 30 days by the hash lifetime, so weekly cohorts over four weeks at most. **Effort:** M. **Risk:** small numbers. **Depends on:** returning hash (this release), P0-7.

### P2-6. Lead journey (person level)
- Showing a named lead the pages their visit read. Technically possible with a shared HMAC between the website and the logs; a privacy decision first (consent wording, retention). The CMS already keeps pages viewed per session, which may be enough. **Effort:** M. **Risk:** high (personal data). **Depends on:** owner decision, P0-7.

### P2-7. Block-list suggestions
- Addresses and networks that only probe, offered as a fail2ban/nginx deny list for the owner to apply. Never applied automatically. **Effort:** S. **Depends on:** P1-7.

### P2-8. Redirects report
- Which redirects fire most (apex, trailing slash, legacy URLs), redirect chains, redirects to 404s. **Effort:** S.

### P2-9. "Shared in chat" line
- Link previews by app (Slack, Teams, iMessage, WhatsApp, LinkedIn, X) as a signal that someone shared a page, separate from crawlers (A7). **Effort:** S.

### P2-10. AI crawler policy view
- robots.txt rules per AI agent beside what each agent actually fetched; flags agents that fetch disallowed paths. Helps decide what to allow for training vs answering. **Effort:** S. **Depends on:** P0-2.
