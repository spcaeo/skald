<p align="center">
  <img src="assets/brand/skald-512.png" alt="Skald logo: a quill crossing a carved stave" width="88" height="88">
</p>

<h1 align="center">Skald</h1>

<p align="center"><sub>Say it “skawld” (/skɔːld/), one syllable, rhymes with “called”: an old Norse poet who told what happened.</sub></p>

<p align="center">
  <strong>Every visit, truly told.</strong><br>
  Web analytics from your server's own access log: the people, the AI assistants and the crawlers<br>
  that a JavaScript tracker never sees. Every figure is counted twice, by an independent audit.<br>
  No cookies, nothing needed in the visitor's browser. Self-host it free, or try hosted Skald in beta.
</p>

<p align="center">
  <a href="LICENSE"><img alt="Licence: Elastic License 2.0" src="https://img.shields.io/badge/licence-ELv2-0b7285"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-3776ab">
  <img alt="Zero dependencies" src="https://img.shields.io/badge/dependencies-zero-2b8a3e">
  <a href="https://github.com/spcaeo/skald/actions/workflows/ci.yml"><img alt="Tests" src="https://github.com/spcaeo/skald/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/spcaeo/skald/pkgs/container/skald"><img alt="Docker image" src="https://img.shields.io/badge/docker-ghcr.io%2Fspcaeo%2Fskald-2496ed"></a>
  <a href="https://github.com/spcaeo/skald/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/spcaeo/skald?sort=semver&label=release&color=555"></a>
</p>

<p align="center">
  <a href="https://spcaeo.github.io/skald/"><img alt="Try the live demo: sample data, no sign-up" src="https://img.shields.io/badge/try_the_live_demo-sample_data,_no_sign--up-2a78d6?style=for-the-badge"></a>
  <a href="https://skaldanalytics.com/beta/"><img alt="Hosted Skald beta: 30 days free, no card" src="https://img.shields.io/badge/hosted_beta-30_days_free,_no_card-2b8a3e?style=for-the-badge"></a>
</p>

<p align="center">
  <a href="https://spcaeo.github.io/skald/"><strong>Live demo</strong></a> ·
  <a href="#quick-start-in-60-seconds"><strong>Quick start</strong></a> ·
  <a href="#whats-new">What's new</a> ·
  <a href="#see-it">Screenshots</a> ·
  <a href="#how-skald-compares">Comparison</a> ·
  <a href="docs/INSTALL.md">Install guide</a> ·
  <a href="SECURITY.md">Security</a> ·
  <a href="#faq">FAQ</a> ·
  <a href="#hosted-skald-and-commercial-licences">Hosted beta / commercial</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/hero-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/screenshots/hero-light.png">
    <img src="docs/screenshots/hero-light.png" alt="The Skald dashboard for example.com, with the site's logo on the menu's site button: visitors, AI assistants, leads and demos booked over the last 30 days, with each day's leads as dots on the chart" width="960">
  </picture>
</p>

---

## What's new

- **2.27.0: share the visitor ID across subdomains from Skald** ([changelog](CHANGELOG.md#2270-2026-10-22)).
  One setting per site links a sign-up on app.example.com to the visits before it, with the script tag unchanged.
- **2.26.0: page groups fill their past days, and leads found by their reference** ([changelog](CHANGELOG.md#2260-2026-10-22)).
  Save a page group and its past days are counted from the raw log, audited; a lead is found by
  the sender's own ID; one sign-up is one lead even when it also sends paid; MCP switch for Docker.
- **2.25.0: a lead's reference, and Mark as test on screen** ([changelog](CHANGELOG.md#2250-2026-10-22)).
  The sender's own ID in Leads and every drawer; owners and admins mark test leads in one click.
- **2.24.0: the script tag just works** ([changelog](CHANGELOG.md#2240-2026-10-22)). No change on
  your web server; the setup Test now says what's wrong when nothing arrives.
- **2.23.0: Leads & sales opens on 7 days, and a sturdier morning run** ([changelog](CHANGELOG.md#2230-2026-10-22)).
  All time, "Today so far", one filter row with five fixes; the kit zip with or without its token.
- **2.22.3: a faster live run** ([changelog](docs/CHANGELOG-2.21-2.22.md#2223-2026-10-22)). About twice as fast,
  every figure unchanged; the live audit skips a stale Real time snapshot instead of failing.

Earlier releases: [CHANGELOG.md](CHANGELOG.md).

## Your analytics cannot see the new visitors

More and more people ask ChatGPT, Claude or Perplexity before they visit a website. When they do,
the assistant fetches your pages to write its answer. AI companies also crawl your site to train
their models. **None of that runs JavaScript, so Google Analytics, Plausible and other script-based
tools never count it.** Google Analytics also drops known bots on purpose.

Skald reads the one record that sees every visit: **your web server's access log.** Every request
lands in exactly one of five groups, and the five add up to the log exactly.

| Group | What is in it |
| --- | --- |
| **People** | A browser that is none of the groups below. Self-reported, so an upper bound. |
| **AI assistants** | Split by why they came: to train, because someone just asked a question, or a person who clicked a link in an AI answer. |
| **Search engines** | Google, Bing and other classic indexing. |
| **Bots and scanners** | Monitors, SEO tools, chat link previews, and probes hunting for `.env` or `wp-login`. |
| **Your own traffic** | Your team, your crawler, your tests. Kept apart, never counted as people. |

How much of your traffic is AI assistants reading your pages? Only your server's log can say, and
Skald's first run answers it for your own site, from the log you already have.

## Why Skald

<table>
<tr>
<td width="50%" valign="top">

### See AI assistants and crawlers
GPTBot, ClaudeBot, PerplexityBot, ChatGPT-User and the rest, by name, with the pages they fetched.
Each AI request is filed by **why it came**: training, answering someone live, or a person clicking
a citation. The three never double count. See what each one asks for (`llms.txt`, Markdown, pages),
what it costs your server, and what an assistant read just before it sent you a visitor.

</td>
<td width="50%" valign="top">

### Trust the names
A crawler's claim is checked against its owner's published addresses or DNS (Google, Bing, Apple,
OpenAI, Perplexity, Anthropic, DuckDuckGo, Meta; DNS for others). A fake is filed apart as
*"claims to be GPTBot"*.

</td>
</tr>
<tr>
<td valign="top">

### Every figure counted twice
A separate audit recounts every figure from the raw log with its own parser and rules. If the two
counts disagree, **the day is withheld, never guessed**. A missing day is never drawn as zero, and
a figure that was not recorded stays blank.

</td>
<td valign="top">

### Private by design, yours to set
No script and no cookie are needed in the visitor's browser, and everything stays on your server.
History keeps totals and labels. Whether each visit keeps its IP address and each lead its email is
a setting: on for a new install, off on an upgraded one until you turn it on. One command deletes a
person everywhere.

</td>
</tr>
<tr>
<td valign="top">

### Live, not 48 hours late
**Real time** shows who is on the site now, on a world map, with the pages being read and the AI
and crawlers fetching right now. **Today · Live**, in the top bar of every tab, shows today so far,
redrawn every 2 minutes, with what the newest visitors are doing now: their pages in order and the
page they are on. The last 6 hours can be read request by request, each with the rule that put it
in its group, in words. Alerts show on the dashboard, by email, or in Slack.

</td>
<td valign="top">

### Results, not just visits
Every lead in one list (who, what they did, its stage now, where it came from), as a list, board,
timeline or map, then funnels and conversions. Leads and demos booked also sit beside the traffic: Overview, Sources, Pages, Places & devices and
Insights, with a lead rate per source, page and country. Calendly, Cal.com, Stripe, Typeform,
HubSpot and Zapier push signed webhooks; the optional `skald.js` tag adds clicks, form steps and
bookings, on every site of the install. Checked twice like everything else.

</td>
</tr>
<tr>
<td valign="top">

### Find the AI traffic hiding in "Direct"
A click from a ChatGPT or Perplexity answer often arrives with no referrer, so other tools file it
under "Direct". When someone asks an assistant, it fetches your page first, and Skald sees that
fetch. A direct visit landing on that same page minutes later is shown as **likely from that
assistant**: for visits, leads and conversions. Always labelled "likely", never mixed into the real
counts, and counted twice.

</td>
<td valign="top">

### Works where your site lives
Your own server's log, or the host's: **Vercel and Netlify log drains**, a **Cloudflare Worker**
that reports pages served from cache on any plan, CloudFront and Fastly logs, or a small shipper
from any server. Settings > Connections walks you through each one, with an install kit and a
**Test connection** button; step by step for Vercel: [docs/VERCEL.md](docs/VERCEL.md). A Next.js
site adds one line to its log format so clicks inside the site count as pages.

</td>
</tr>
<tr>
<td valign="top">

### Follow one person across days
Search an IP address, an email or a lead and see that person's visits on every day kept (source,
landing page, pages in order, country, device), and their leads and conversions, linked by visitor
ID and email. An address is tied to a lead by the form it sent at the lead's time: likely, never
certain. For admins and owners; every search is in the audit log.

</td>
<td valign="top">

### Nothing hidden, and setup that checks itself
Spam, duplicate and test leads, and cancelled, removed and test conversions, are listed in full,
never just dropped. Add a site looks at the site first and suggests the way in; each connection ends
with a **Test**. `skald doctor` checks every part of the install, one line each, with the exact
fix; Settings > Integrations shows the same for each hook and the script tag.

</td>
</tr>
</table>

## One log, two answers

Skald was built to answer one question: who really visits your site. The same access log also
records everyone probing it, so Skald answers a second one: who is trying to break in.

A real example from our own site (21 Oct 2026): a "visitor" with a Chrome user agent and a
referrer from our own WordPress host loaded the home page and its scripts, then made 150 requests
in 14 seconds for AI provider credentials (Amazon Bedrock, LiteLLM, OpenAI, Anthropic configs),
`.env` files and Terraform state. Every one was answered 404, a redirect or a dropped connection.
Skald now files such a client as a scanner for the whole day instead of a visitor. Read the full
story: https://skaldanalytics.com/security/ai-key-thief/

The Security section shows, from the log alone:

- **Is anything exposed?** Every probe answered with content, set against the host's own fallback
  page, with the evidence.
- **Who is scanning:** each scanner, what it looked for, what your server answered.
- **Attack attempts:** login hammering, request bursts, injection in URLs.
- **Fake browsers:** clients that claim to be a browser but behave like a bot.
- **Your stack and advisories:** what serves each site, matched against advisories shipped with each
  release (currently php2shell and the Node.js October 2026 releases).
- **A block list** (nginx, Cloudflare, fail2ban) and **alerts** by email or Slack.

What it is not: Skald does not block traffic, is not a WAF or intrusion prevention system, and
cannot see request bodies or file contents, only what the access log records. Use it alongside
your firewall, not instead of it.

## Features

**The dashboard**
- Six sections, with tabs inside: Overview, Traffic, Leads & sales, AI & bots, Security and Site.
  Each answer has one place.
- **Every view has its own link:** the tab, the period, the filters, and the visitor, lead,
  request or dialog that is open. Back closes what you opened. No link ever holds an IP address or
  an email (they become a code only your browser reads back).
- **Copy and open on every URL:** point at a page or address anywhere and two icons copy the full
  URL or open it in a new tab.
- **Today · Live**, **All time** and **Compare with…** in the top bar, on every tab. Leads & sales
  opens on the last 7 days, the other sections on today.
- **Real time** (Overview › Real time): visitors active now and in the last 30 minutes, visitors
  minute by minute, requests per minute every 15 seconds (labelled requests, never people), pages
  being read, sources, devices, AI assistants and crawlers now, and the newest visits; both
  recounted by the audit.
- **What visitors are doing now** (Overview, today): the newest visitors with their city, source
  and pages in order, `/ → /pricing → /book-a-demo`, the page they are on now marked, following
  the live answer every 15 seconds; point at a row and its city pulses on the map.
- A **world map** of where visitors are: countries shaded by visits today, a bubble or a city dot
  where visitors are active now, a countries table beside it. Natural Earth's public-domain
  outlines drawn in the page; no map service is asked for anything.
- Nothing reads "unknown": a visit with no referrer and no campaign tag is **Direct**, a value the
  log did not have is **Not recorded**.
- **Overview, today, live:** visitors now and the four tiles against **yesterday at this hour** (a
  figure with its own second count), the map, sources, what converted and AI & bots.
- **Every table works the same way:** sort any column, filter columns, choose columns, and export
  just the rows and columns you see; all of it in the address. Every row opens its detail.
- **Advanced filters:** rules on any field a visit carries (country, city, source, campaign, AI
  assistant, first came from, pages, time on site, lead, device, browser, new or returning) with
  All or Any and groups, a live count of matching visits, saved as views. A value not recorded
  never matches by chance.
- **Search the dashboard** (Ctrl K); countries as a flag and a three-letter code; dates in the
  site's time zone; a set-up list for a new site; a preview of the daily mail.

**Traffic and audience**
- Five groups that add up to the log, every day, every site.
- Visitors, visits, pages read, countries (with a flag beside each, everywhere), browsers, systems,
  devices, sources, referring sites, UTM campaigns and ad networks (from the click ID, never its value).
- AI assistants' phone apps count as citations; paid social, iOS Google Ads, TikTok and X clicks
  are told apart by their tags and click IDs. Calls under `/api/` are never a page view.
- A new outside source starts a new visit: someone who opens the site directly and comes back from
  ChatGPT minutes later is two visits, the second from ChatGPT, so an AI assistant's visit is never
  hidden inside an earlier one.
- Anonymous journeys: each visit's pages in order, kept 7 days by default.
- **Traffic › Visitors:** the visitor flow, each visit with its city and source, real new and
  returning figures and how engaged visits were (narrowed by the filters when every kept visit
  checks out), each card withheld unless it adds up.
- **Where a returning visitor first came from** (first touch): under a Direct visit, "First came
  from google.com, 3 days ago", linked by the visitor ID, the kept address or the 30-day code,
  never guessed; on Sources, every returning visit by where it first came from, counted twice.
- **One visitor drawer:** every visit of a visitor as a timeline, the time between pages, "12 days
  later" between visits, and a Replay of the journey. Admins and owners, audit-logged.
- **Cities** from a GeoIP city file you give it (`SKALD_CITY_DB`; DB-IP's free city file works):
  a Cities table, the city on each visit, and a dot per active city on the live map. People only.
- **Retention cohorts** (Traffic › Retention): of the visitors first seen in a week, how many came
  back in each week after, split by first source, country, device or landing page.
- **Search Console and Bing** (Traffic › Search): queries, pages, countries, devices, clicks,
  impressions, CTR and position, synced every 6 hours, connected from Settings without a shell, and
  set beside Skald's own visits from search, never forced to match.
- A visit that opens 6 or more pages within 2 seconds is too fast to be a person and counts as a bot.
- People: each visit kept with its IP address and browser (395 days by default), and one search for
  an IP, an email, a lead or a visitor ID that shows that person's visits, leads and conversions
  across days, linked. Admins and owners only, every search in the audit log. Keeping IPs and emails
  is a setting: on for a new install, off on an install upgraded from before 2.4.0.
- Engagement by source and device, returning visitors by source, exit rate per page, and campaign
  tag problems flagged (no medium, an unknown medium, an ad click with no tags, internal tags).
- **Compare with…** the previous period, the same period last year, or any range up to 12 months,
  leads included. Insights (working, dropped, new, gone), and a page's story: its first Googlebot,
  first AI crawler, first person and first lead.

**AI and machines**
- AI assistants by name and by reason, with the pages each one fetched.
- What the AI read before it sent a visitor: the pages that assistant fetched in the minutes
  before the click, in the visit itself and per assistant (how many of its visits landed on a page
  it had just read). Context, never a count of people.
- What AI fetches ask for: pages, `llms.txt`, Markdown, plain text, `robots.txt`, sitemaps or other
  files, for training and for live answers apart.
- What each crawler costs your server: requests, data sent, mean and 90th-percentile response time,
  error share, distinct paths and re-crawls, per assistant, search crawler and bot. Open one for
  its detail: requests by day, pages, statuses, the share from its owner's checked addresses,
  countries, user agents and when it was last seen.
- Google's AI Mode told apart: a click from Google that carries AI Mode's `udm=50` reads
  "google.com (AI Mode)", still under Search engine. Only when Google says so, never guessed.
- AI clicks that lost their referrer, estimated: a direct visit to a page an assistant fetched
  minutes before is shown as "likely" from that assistant, on AI & bots and on Leads & sales.
  Kept apart, never added to any count.
- Block AI crawlers per assistant, or only their training crawlers (AI & bots > Crawler rules),
  applied by the web server (`robots.txt` stays reachable). Skald blocks; it does not charge.
- Your `robots.txt` rules shown beside what each crawler actually fetched.
- **Crawl health:** your sitemap beside what Google, Bing and each AI crawler fetch: coverage,
  sitemap pages never fetched, pages fetched that the sitemap does not list, errors, redirects,
  slow and large answers.
- AI alerts: an assistant starts or stops reading a page; the first visit ever from an
  assistant's answer, a page's first; visits from AI answers against the same weekday's median
  over 6 weeks; a crawler gone silent for 7 days. Whole, checked days only, each recounted.
- A suggested `llms.txt` from the pages people and assistants read most, to copy and publish.
- **AI answers:** what ChatGPT, Perplexity, Gemini and Claude answer to the questions your
  customers ask, asked through their APIs with your own keys, per **tracking profile** (a place
  and a language; daily, weekly or monthly; 1 to 5 tries a question). Whether each answer names
  you, which of your pages it cites, which competitors it names, run by run and as "x of N
  tries"; then **cited → read → sent → leads** for one page, from your own log and lead tools.
  A cost estimate before anything runs and a daily cap; every figure recounted, a run that
  disagrees withheld. A sample of API answers, labelled so, not what every user sees.

**Results**
- One section, **Leads & sales**, one question per tab: Leads, Summary, Sources, Calendar
  bookings, Funnels, Events and Find a person.
- **Leads:** every lead of the period, newest first: when, name and email (owners and admins
  only, where the site keeps them), what they did and its label, its stage now, where it came
  from, the source, first touch, landing page and country; as a list, a board, a timeline or a
  map. One filter row; the count above it is the Leads figure itself. A period with no lead says
  where the leads are, and "Today so far" names today's.
- Summary and Sources count from your lead database or from your tools, never both in one figure.
- Leads and demos booked on the Overview (two tiles, and each day's leads as dots on the main
  chart), and today's as they arrive with Today · Live.
- A Leads column and a lead rate (leads per visitor, from 10 visitors up) on Sources, Pages and
  Places & devices; lead findings in Insights; leads against another period (Compare with…).
- Leads by first and last source, crossed with the status your team set, and time from first
  visit to lead. Saved funnels counted every day by source and device.
- Conversions from signed webhooks; forms and bookings started but not finished. One Calendly or
  Cal.com account that books for several businesses: keep only your own event types.
- **Leads you can check:** a label on each lead (sales, support); the site's own server marks its
  team's test leads (`"test": true`, or a signed call for leads already sent); a signed, read-only
  call lists what Skald has, so the site can resend any lead it missed.
- Spam, duplicate and test leads, and cancelled, removed and test conversions, each listed in full.
- Outgoing signed webhooks to your CRM, Zapier or Slack, never with a name or email.

**Security** (from the same access log)
- **Is anything exposed?** Every scanner probe your server answered with content, set against the
  host's own fallback page by size, with the evidence; "can't tell" when the log has no size.
- **Who is scanning us?** Each scanner by address and user agent: what it looked for (secret
  files, cloud and deploy configs, admin panels, WordPress, PHP), what the server answered, a
  forged referrer or the bare IP, probes per day.
- **Attack attempts:** path traversal and injection, login hammering, bursts, and log signs worth
  a look (gateway errors, `.php` requests, large POST bodies).
- **Fake browsers and scrapers**, by address and network, with the pages they took.
- **Your stack:** the web server, PHP, WordPress and Next.js read from outside once a day, matched
  against the advisories shipped with each release: update needed, or check your version.
- A **block list** to review (nginx `deny` lines, a Cloudflare IP list, a plain list), and
  **alerts** to the people on each site, right away or in the daily mail.
- Optional: a public **"Is my site exposed?"** check your install can answer for any site, with
  the proof for each finding and strict limits on what it fetches.
- Addresses for owners and admins only, where the site keeps them. Skald blocks nothing itself.

**Connecting a site**
- **Settings › Connections:** send a site's visits, read your figures (API) or connect an AI
  assistant (MCP), each a short dialog with your address and token filled in and a **Test** at
  the end ("Connected: 1,240 lines received, the last at 10:42", or what is wrong and the fix).
- **Skald checks your site** from outside: the web server, any platform in front, the framework,
  the host names and page assets, and suggests the way in. You confirm or change it.
- **Add a site** in five steps you can leave and resume; an install kit whose `check.sh` says what
  is wrong in plain words; a private link to share the steps with your developer.
- **Set up this site** on Overview, and always in Settings › Connections: each open line one plain
  sentence and a Set up button.
- **Next.js:** one field in the site's log format and every click inside the site counts as a
  page, never a prefetch.

**Site**
- Health, Alerts, Requests, Not found, Speed and Data quality, as tabs of one section.
- 404s and who met them (people, probes, crawlers), server errors by page, page speed, uptime from
  the heartbeat with every outage.
- Alerts: site down, logging stopped, 5xx burst, 404 surge, crawler burst, new crawler, traffic
  drop, each switched on or off per site. A failed morning run sends one short mail. Any alert can
  go to **Slack** or any tool, as the signed webhook event `alert.opened`.
- A data-quality panel: unreadable lines, gaps, duplicates, log age.
- Deploy and change markers on every chart.

**Team, data and agents**
- Accounts: organisations, owner/admin/viewer roles, invites, two-step sign-in, scoped API tokens
  and an audit log. Or a single nginx password, if that is all you need.
- Settings in the dashboard: retention windows, what is kept about people, mail, sites, internal
  addresses, integrations (with each road's status), security.
- `skald doctor`: one line per part of the install (daily run, missing days, logs, the hooks, the
  script tag, mail, a newer version, disk), each with its fix.
- Several sites in one install, each with its own settings, page assets and logo (from the site
  itself, an upload, or a letter on a colour; never an outside icon service). After sign-in, a card
  per site with a Live dot and today's visitors, leads and demos booked ("-" when not known yet,
  never 0). Settings and sites can be changed from the shell too (`skald settings`, `skald site`).
- Export any table as CSV or JSON, print to PDF, a report builder, and daily and weekly email
  reports (refused if the figures do not add up).
- **Client reports:** branded reports for an agency's clients, a mail with a PDF attached, weekly,
  monthly or every few days, with your name, colour and logo; verified days only, the sums counted
  twice before a report goes.
- A read-only JSON API and an **MCP server with 14 read-only tools** for Claude, ChatGPT and other
  AI agents (the person search only with a token that may read private data).
- In-app Help in plain words with how-to guides, keyboard shortcuts, a command palette, light and
  dark themes, and a phone layout.
- A notice when a new release is out, and one-command upgrades with a backup and a rollback.

**Inputs**
- nginx and Apache logs (combined or extended), Caddy JSON.
- Countries from the log (Cloudflare's country, or nginx's `cc=`), else from a GeoIP file you give
  it (`SKALD_COUNTRY_DB`; DB-IP's free file works); a city file (`SKALD_CITY_DB`) adds cities. Without
  one, Not recorded, never guessed.
- CDN logs: Cloudflare Logpush, CloudFront, Fastly. Pages served from the CDN cache are counted too.
- Vercel and Netlify log drains, and the Skald Worker for Cloudflare on any plan (it posts each
  request after the page has gone out; with your server's log, only cache hits are kept).
- `skald-ship`: one standard-library Python file that sends another server's log to Skald.
- Beacon-only mode for a site with no readable log (people only, since bots run no script).

## See it

<p align="center">
  <a href="https://spcaeo.github.io/skald/"><strong>Try the live demo: sample data, no sign-up.</strong></a>
</p>

The whole dashboard with 60 days of sample data for a made-up site, in your browser: today's Overview
with what visitors are doing now, Real time on a world map, the visitor drawer, cities, Search
Console and Bing figures (made up), retention and crawl health, AI answers (made-up answers), AI &
bots, every Security tab, every lead in one list, bookings, the left-out leads and the removed
conversions, and Settings › Connections with its set-up list. Nothing to install. Saving, the
person search and the other Settings pages need your own Skald. Every image below is the demo.

### Security, from the same log (2.21)

<p align="center">
  <img src="docs/screenshots/security-exposed.png" alt="Security, Is anything exposed? for the last 7 days: a red verdict '1 possible exposure: check it now'; 608 scanner probes, 270 answered with a page, 269 the host's harmless page, 1 possible exposure; the row for /.env.production on example.com answered 200 with 1,873 bytes and what to do; each host's fallback page, the bare IP 192.0.2.10 included" width="900"><br>
  <strong>Is anything exposed?</strong> Every probe that got a page, set against the host's own harmless page.
</p>

| | |
| :---: | :---: |
| <img src="docs/screenshots/security-stack.png" alt="Security, Your stack: an 'Update needed' card for PHP's remote code execution flaw naming PHP 8.3.10 on media.example.com and PHP 8.1.2 on example.com, a 'Check your version' card for the Node.js October 2026 releases, and what serves each host, with an open WordPress login page" width="440"><br>**Your stack.** What serves each host, and which advisories apply. | <img src="docs/screenshots/security-scanners.png" alt="Security, Who is scanning us?: probes per day, what scanners looked for, and one row per scanner with requests, probes, what the server answered and signs such as a forged referrer or the bare IP" width="440"><br>**Who is scanning us?** Each scanner, what it looked for, what it got. |
| <img src="docs/screenshots/security-attacks.png" alt="Security, Attack attempts over 30 days: injection attempts, login and form posts and burst requests; log signs worth a look (PHP requests and gateway errors above their usual, one POST of 2.6 MB); path traversal, Log4Shell and SQL injection by kind with each address" width="440"><br>**Attack attempts.** Injection, login hammering, bursts and log signs. | <img src="docs/screenshots/security-fake.png" alt="Security, Fake browsers and scrapers: requests from clients that claim to be a browser or a known crawler, what gave them away, the pages they took, and each address with its network" width="440"><br>**Fake browsers.** What gave them away, and what they took. |
| <img src="docs/screenshots/security-block-list.png" alt="Security, Block list: a note to review before blocking, exports as nginx deny lines, a Cloudflare IP list or a plain list, the networks with two or more scanners, and each address with its probes and attack attempts" width="440"><br>**Block list.** nginx, Cloudflare or a plain list, to review first. | <img src="docs/screenshots/security-alerts.png" alt="Security, Alerts: the rules (possible exposure, new scan wave, advisory matches your stack) and the security alerts of the last 30 days, among them a possible exposure of /.env.production and three advisories" width="440"><br>**Security alerts.** To the people on each site. |
| <img src="docs/screenshots/security-scanner-detail.png" alt="One scanner's detail: its address, user agent, country, hosting network, days seen, requests and probes, what the server answered, what it looked for, its signs (a forged referrer, the bare IP) and the paths it asked for" width="440"><br>**One scanner.** Its paths, its answers, its signs. | <img src="docs/screenshots/public-check.png" alt="The public check at skaldanalytics.com/check/ for www.example.com: 'Your site runs WordPress 7.1.3 on PHP (version hidden), behind Cloudflare. 1 thing to do now, 1 to check, 3 tips', a Download PDF report button, and the first card, Login page open to the internet, with what was seen and where it was read from" width="440"><br>**The public check (2.22, optional).** Any site, read from outside, with the proof. |

### Leads & sales (2.20)

<p align="center">
  <img src="docs/screenshots/leads-list.png" alt="Leads and sales, Leads, on its default of the last 7 days: 'Today so far: 4 new leads, Show today (live)', the options row (what, stage now, source), 31 leads, 15% more than the 7 days before, and one row per lead with when, name, email (made-up example.com names), what they did, stage now, where it came from, source, first touch and landing page; view buttons for list, board, timeline and map" width="900"><br>
  <strong>Leads.</strong> Who they are, what they did and where they came from, in one list.
</p>

| | |
| :---: | :---: |
| <img src="docs/screenshots/sales-summary.png" alt="Leads and sales, Summary for the last 7 days: leads, sign-ups and contact forms against the period before, demos booked not set up in the lead database, leads per 100 visitors, and leads per day by kind" width="440"><br>**Summary.** How many, and better than before? | <img src="docs/screenshots/conversions.png" alt="Leads and sales, Sources counted from the tools: where the completed ones came from by last touch, first touch, campaign and landing page, each split by action" width="440"><br>**Sources.** Where the leads came from, first and last touch. |
| <img src="docs/screenshots/sales-bookings.png" alt="Leads and sales, Calendar bookings: every stage of the demos booked through Calendly, the demo funnel from opened to booked, cancelled, rescheduled and no-show, and where the booked ones came from" width="440"><br>**Calendar bookings.** Every stage, cancelled and no-show too. | <img src="docs/screenshots/funnels.png" alt="Funnels: a saved funnel from landing to lead, its steps, how many visits went through each and the drop between steps" width="440"><br>**Funnels.** Saved once, counted every day. |
| <img src="docs/screenshots/leads-left-out.png" alt="Leads, Stage now: Left out: 10 spam, duplicate and test leads of the last 30 days, each marked in red, listed beside the counted leads, never counted" width="440"><br>**Left out, still listed.** Spam, duplicates and test, never just dropped. | <img src="docs/screenshots/conversions-removed.png" alt="Conversions removed by a lead-database sync, each with when, why (marked duplicate or spam in the lead database) and what it was, and the journeys before them" width="440"><br>**Removed, with when and why.** |
| <img src="docs/screenshots/person-search.png" alt="Person search for the IP address 203.0.113.109: seven visits over 33 days, where it first came from (ChatGPT), its city and device, and every visit as a line of pages, newest first" width="440"><br>**Person search** (your own Skald). Every visit kept, across days. | <img src="docs/screenshots/person-lead.png" alt="Person search for lead14@example.com: the lead, the linked IP address, visitor ID and lead row, the visit that sent its form, its conversions and the pages its visitor ID saw" width="440"><br>**One lead, linked.** Its email, address, visitor ID and form visit. |
| <img src="docs/screenshots/leads-reference.png" alt="Leads with the Reference column switched on: each lead shows the sending app's own ID (made-up u-1048576) with a copy button" width="440"><br>**The lead's own reference** (2.25). The sender's ID, searchable, with a copy button. | <img src="docs/screenshots/lead-drawer-reference.png" alt="A lead's drawer: Reference u-1048576 from the site's server, both of its steps (completed, then paid), and the Mark as test button" width="440"><br>**Every step, and Mark as test** (2.25). One click moves a test lead out of every count. |
| <img src="docs/screenshots/person-by-reference.png" alt="Find a person: searching u-1048576 finds Lead: u-1048576 with its visits" width="440"><br>**Find a lead by its reference** (2.26). The ID from your own app finds the person. | <img src="docs/screenshots/views-fill.png" alt="Settings, Sites, Views: a new page group saved, and Filling 10 days, 4 of 10, from the raw log" width="440"><br>**Page groups fill their past** (2.26). Save a group; past days are counted from the raw log, audited. |

### Live (2.11, 2.13, 2.20)

<p align="center">
  <img src="docs/screenshots/overview-live.png" alt="Overview, today: the live world map with a pulsing dot on each city with someone on the site, and under it What visitors are doing now: five visitors with their city, device, source and pages in order, such as / → /pricing/ → /features/ → /customers/, 'now on /customers/ · 5 min ago', beside Pages read in the last 30 minutes" width="900"><br>
  <strong>What visitors are doing now.</strong> The newest visitors and the pages they read, live.
</p>

| | |
| :---: | :---: |
| <img src="docs/screenshots/overview-today.png" alt="Overview, today in Live mode: visitors on the site now with visitors a minute, then Visitors, Pages read, Leads and Visitors from AI, each against yesterday at this hour with both days' running lines, and the map of today's visits" width="440"><br>**Overview, today.** Every figure against yesterday at this hour. | <img src="docs/screenshots/realtime.png" alt="Overview, Real time: visitors active now and in the last 30 minutes, visitors minute by minute, requests per minute labelled as requests, a world map with each active city, and tables by country and by city" width="440"><br>**Real time.** Visitors and requests apart, both counted twice. |
| <img src="docs/screenshots/live-mode.png" alt="Today · Live switched on: visitors on the site now, and today's visitors, pages read, leads and visitors from AI, each against yesterday at this hour" width="440"><br>**Today · Live.** One switch, on every section. | <img src="docs/screenshots/live-leads.png" alt="What converted today: today's demos booked, sign-up and contact form, each with its time, page, country and where it came from" width="440"><br>**Live leads.** Each lead and booking as it lands. |

### Connecting a site (2.16, 2.17)

<p align="center">
  <img src="docs/screenshots/connections.png" alt="Settings, Connections: Set up example.com, 1 of 5 left (logs arriving, visits count as people, countries shown, the script tag, the lead hook and privacy ticked; the mail recipient with a Set up button), then three tasks: send this site's visits to Skald, read your figures (API) and connect an AI assistant (MCP), and the organisation's tokens with what each is for" width="900"><br>
  <strong>Connections.</strong> The set-up list, three guided tasks with a Test at the end, and your tokens.
</p>

| | |
| :---: | :---: |
| <img src="docs/screenshots/site-check.png" alt="Add a site, step 1: example.com typed in, and What Skald found: server nginx on Ubuntu, no platform in front, built with Next.js, host names example.com and www.example.com, page assets /_next/static/, and the suggestion: a Linux server with Docker" width="440"><br>**Skald checks your site** (your own Skald). And suggests the way in. | <img src="docs/screenshots/add-site-wizard.png" alt="Add a site, step 3 of 5, how visits reach Skald: a Linux server with Docker (recommended), the same without Docker, Cloudflare, Vercel or Netlify, or only the script tag" width="440"><br>**Add a site in five steps.** Close it any time; it continues. |
| <img src="docs/screenshots/connections-install.png" alt="Send this site's visits to Skald, step 3 of 4, Install: download the install kit (.zip), the commands to unpack it and run sudo bash install.sh, and Share with your developer" width="440"><br>**Install, filled in.** The kit, the commands, a link for your developer. | <img src="docs/screenshots/setup-checklist.png" alt="Set up example.com: six lines ticked and one open, Mail recipient confirmed: 'Nobody gets the daily mail yet', with a Set up button" width="440"><br>**Set up this site.** Each open line has a Set up button. |

<p align="center">
  <img src="docs/screenshots/links-copy-open.png" alt="Traffic, Pages: pointing at /pricing/ shows a copy button and an open-in-a-new-tab button at the end of the path" width="900"><br>
  <strong>Copy and open on every URL</strong> (2.21). And every open view has its own link.
</p>

### AI & bots

<p align="center">
  <img src="docs/screenshots/ai-answers.png" alt="AI and bots, AI answers for example.com, made-up answers: the note that these are a sample of API answers, the tracking profiles, from an answer to a lead for one assistant and page (answers that cited it, its fetcher reading it, visitors and leads), how often each assistant named the site per run, and every profile by every assistant as x of N tries" width="920"><br>
  <strong>AI answers</strong> (2.14). What the assistants say, and what they then read and sent.
</p>

| | |
| :---: | :---: |
| <img src="docs/screenshots/ai-assistants.png" alt="AI and bots, Assistants: pages fetched to answer a question per day, assistants by name with their address check and robots.txt rule, and what they fetch" width="440"><br>**Assistants.** Who read your pages to answer someone. | <img src="docs/screenshots/ai-answers-profiles.png" alt="Settings, AI answers, tracking profiles: New York, London and Montréal, each with how often, tries, questions, the daily cap and the estimated cost a month" width="440"><br>**Tracking profiles** (your own Skald). A place and a language each. |
| <img src="docs/screenshots/ai-read.png" alt="What the AI read before it sent a visitor: per assistant (ChatGPT, Perplexity, Claude, Gemini, Copilot), visits from its answers, how many it fetched pages for first, how many landed on a page it fetched, and likely visits kept apart" width="440"><br>**What the AI read before it sent a visitor.** | <img src="docs/screenshots/ai-fetch-formats.png" alt="What they fetch: every AI crawler fetch by what its address names (pages, Markdown, llms.txt, sitemaps, robots.txt), in total and per crawler" width="440"><br>**What AI fetches ask for.** Pages, `llms.txt`, Markdown, sitemaps. |
| <img src="docs/screenshots/crawler-cost.png" alt="What each crawler costs: scanner probes, Googlebot, Scrapy, GPTBot, ClaudeBot, bingbot and others with requests, bytes sent, mean time, errors, distinct paths, re-crawl and last seen" width="440"><br>**What each crawler costs.** Requests, bytes, time, errors, re-crawls. | <img src="docs/screenshots/crawler-detail.png" alt="GPTBot's detail: requests per day, what it costs, the share from its own checked addresses, the pages it fetched, its status mix and countries" width="440"><br>**One crawler in detail.** Impostors filed apart. |
| <img src="docs/screenshots/crawl-health.png" alt="AI and bots, Crawl health: the share of the sitemap each crawler fetched, then each crawler with its pages never fetched, pages not in the sitemap and errors" width="440"><br>**Crawl health.** Which sitemap pages each crawler reaches. | <img src="docs/screenshots/ai-assistant-cost.png" alt="What each assistant costs: requests, bytes sent, mean time, errors, distinct paths, re-crawl and last seen for ChatGPT-User, Perplexity-User and Claude-User" width="440"><br>**What each assistant costs.** Fetching live for a user. |

### Traffic and the rest of the dashboard

| | |
| :---: | :---: |
| <img src="docs/screenshots/overview.png" alt="Overview, Summary for 90 days: visitors, pages read, leads, visitors from AI, demos booked and returning visitors in tiles, a chart with each day's leads, and the countries and top pages" width="440"><br>**Overview.** The period at a glance. | <img src="docs/screenshots/compare-mode.png" alt="Compare with the previous period switched on: Traffic, Sources with A, B and the change beside every source" width="440"><br>**Compare with…** Previous period, last year or any period. |
| <img src="docs/screenshots/traffic-sources-grid.png" alt="Traffic, Sources: one grid with segments for source type, referring site and campaign, with visitors, the change, a trend, leads and lead rate, then where returning visitors first came from" width="440"><br>**Sources.** One grid; search, filters and sort in the address. | <img src="docs/screenshots/visitors.png" alt="Traffic, Visitors for 7 days: the visitor flow from source through four pages, and each visit with its time, country, city, device, source, new or returning, pages and time on site" width="440"><br>**Visitors.** The flow, then each visit page by page. |
| <img src="docs/screenshots/visitors-drawer.png" alt="The visitor drawer: a visitor from Austin with several visits over 17 days, where they first came from (google.com, search engine), and each visit as a line of pages with the time between them, newest first, with Replay" width="440"><br>**One visitor, every visit.** Where they first came from, replayable. | <img src="docs/screenshots/filters.png" alt="The filter builder over Traffic, Visitors: country is USA or GBR, pages read at least 2 and source type is not direct, joined by All rules, 193 of 578 visits match, each rule's own count, and a name to save it as a view" width="440"><br>**Advanced filters.** AND, OR and groups; saved as views. |
| <img src="docs/screenshots/places-cities.png" alt="Places and devices, Cities: visitors by city, each with its country's flag and three-letter code (New York, USA; San Francisco, USA; London, England, GBR), searchable and exported as shown" width="440"><br>**Cities.** Each visit's city, from a free city file. | <img src="docs/screenshots/search.png" alt="Traffic, Search with made-up Search Console figures: clicks, impressions, CTR and average position for 28 days, clicks per day with the provisional day dashed, top queries, pages, countries and devices, and Search Console clicks beside Skald's people from Google" width="440"><br>**Search.** Google's and Bing's figures beside Skald's own. |
| <img src="docs/screenshots/retention.png" alt="Traffic, Retention: weekly cohorts of new visitors, the share of each who came back in each week after, and a retention curve" width="440"><br>**Retention.** Who came back, week by week. | <img src="docs/screenshots/reports-preview.png" alt="Settings, Reports: a monthly report for a client of example.com with its schedule, period, sections and recipients, and the preview of its mail" width="440"><br>**Client reports** (your own Skald). Branded, with a PDF. |
| <img src="docs/screenshots/privacy-ip-choice.png" alt="Settings, Data retention, People: keep visitors' IP addresses as Full address, Shortened (203.0.113.57 kept as 203.0.113.0) or Don't keep" width="440"><br>**Shortened addresses.** Full, shortened or none. | <img src="docs/screenshots/privacy-notice.png" alt="Settings, Data retention: the wording for your privacy notice, made from this site's settings, with a Copy button" width="440"><br>**Privacy-notice wording.** Made from what the site keeps. |
| <img src="docs/screenshots/integrations-status.png" alt="Settings, Integrations: a status line for the hook receiver, the script tag, each hook and the lead database, all OK" width="440"><br>**Integrations status.** Each road: working, or what to fix. | <img src="docs/screenshots/integrations.png" alt="Settings: signed Calendly and Stripe hooks with their deliveries, Calendly kept to one event type, and an outgoing webhook to a CRM" width="440"><br>**Integrations.** Signed webhooks from the tools you use. |
| <img src="docs/screenshots/site-picker.png" alt="Choose a site, after sign-in: a card for each site with its logo, a green Live dot and today's visitors, leads and demos booked, and an Add a site card" width="440"><br>**Choose a site.** Each site's logo and today so far. | <img src="docs/screenshots/site-switcher.png" alt="The site switcher open from the menu's site button: each site with its logo and today's visitors, then All sites" width="440"><br>**Site switcher.** Every site, one click away. |
| <img src="docs/screenshots/settings-team.png" alt="Settings: team, roles and invites" width="440"><br>**Team & access.** Roles, invites, two-step sign-in. | <img src="docs/screenshots/logo-settings.png" alt="Settings, Sites, Logo: the logo at three sizes, found on the site, and the choices: from the site, upload my own, or a letter on a colour" width="440"><br>**Site logo.** From the site, an upload, or a letter. |
| <img src="docs/screenshots/mcp-claude.png" alt="Example: adding Skald's MCP server with one command, and the answer of its ai_activity tool" width="440"><br>**MCP in Claude.** Ask about your traffic in plain words. | <img src="docs/screenshots/skald-doctor.png" alt="Terminal output of skald doctor: one line per part of the install, OK or OFF, with its fix" width="440"><br>**`skald doctor`.** Every part checked. |
| <img src="docs/screenshots/help.png" alt="In-app help: a guide for each topic in plain words, with where to click and what Skald keeps" width="440"><br>**Help.** Every page explained, in plain words. | <img src="docs/screenshots/mobile.png" alt="Skald on a phone: Overview today, live, with the visitors on the site now and today's figures" width="220"><br>**On a phone.** The same figures, a drawer menu and a bottom bar. |

## Quick start in 60 seconds

You need a server whose access log Skald can read. Full guide, all options and troubleshooting:
**[docs/INSTALL.md](docs/INSTALL.md)**. Hosting choices (Railway, Render, Fly.io, a VPS) and how to
measure sites on Vercel, Netlify or Cloudflare: **[docs/HOSTING.md](docs/HOSTING.md)**. Site on Vercel? Follow **[docs/VERCEL.md](docs/VERCEL.md)**.

**Hosting:** [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/spcaeo/skald)
(a paid instance with a disk; `render.yaml` sets it up). Railway, Fly.io and Kubernetes:
step by step in [docs/HOSTING.md](docs/HOSTING.md).

### Option 1: Docker (fastest)

**1. Start it** with your web server's log mounted read-only:

```sh
docker run -d --name skald -p 127.0.0.1:8080:8080 \
  -v /var/log/nginx:/logs:ro \
  -v skald-data:/var/lib/skald \
  ghcr.io/spcaeo/skald:latest
```

**2. Open** `http://localhost:8080`. The port is published on this machine only. To reach it from
elsewhere, put HTTPS in front: your web server proxying to `127.0.0.1:8080`, or the bundled Caddy
(Option 2). [docs/INSTALL.md](docs/INSTALL.md) has both recipes.

**3. Make the first owner.** This prints a link to set your password:

```sh
docker exec -it skald skald accounts init --org "Example Co" --owner-email owner@example.com
```

**4. Open the link, set a password, sign in.** Your history lives in the `skald-data` volume.

**5. Fill the history and check it.** `docker exec skald skald backfill --days 14` adds the days your
logs still hold; `docker exec skald skald doctor` then says, one line per part, what works and
what to fix. The full walk-through is the Help guide "Docker: first install in 10 minutes".

Settings come from environment variables (`SKALD_SITE`, `SKALD_HOSTS`, `SKALD_TIMEZONE`,
`SKALD_BASE_URL`, `SKALD_EMAIL`, `SKALD_SMTP_*`, `SMTP_USER`, `SMTP_PASSWORD`, `SKALD_KEEP_IPS`,
`SKALD_IDENTITY`) or a config file mounted at `/etc/skald/config.yml`. The
log must be readable by group `adm` (gid 4), as it is on stock Debian and Ubuntu.

> **Sign-in needs HTTPS.** The session cookie is `Secure`, so plain `http://` works only at
> `localhost`. On a remote server, put HTTPS in front (below).

### Option 2: Docker Compose

```sh
git clone https://github.com/spcaeo/skald && cd skald
docker compose up -d
docker compose exec skald skald accounts init --org "Example Co" --owner-email owner@example.com
```

`docker-compose.yml` is at the root of the repository. Edit its log path first if your logs are
not in `/var/log/nginx`.

#### On a server with your own domain

Either let your host's nginx or Caddy proxy `/traffic*` to `127.0.0.1:8080` over HTTPS, or start the
bundled Caddy, which gets a certificate for you:

```sh
SKALD_DOMAIN=stats.example.com docker compose --profile https up -d
```

### Option 3: Install script (Debian, Ubuntu and similar)

The quick way, pinned to a release:

```sh
curl -fsSL https://raw.githubusercontent.com/spcaeo/skald/v2.7.0/install.sh | sudo bash -s -- --ref v2.7.0
```

This runs a script from the internet as root. To check it first, download the release and its
checksums, verify, then run it:

```sh
curl -fsSLO https://github.com/spcaeo/skald/releases/download/v2.7.0/skald-2.7.0.tar.gz
curl -fsSLO https://github.com/spcaeo/skald/releases/download/v2.7.0/SHA256SUMS
sha256sum --ignore-missing -c SHA256SUMS      # must print: skald-2.7.0.tar.gz: OK
tar -xzf skald-2.7.0.tar.gz && cd skald-2.7.0 && less install.sh && sudo ./install.sh
```

It installs into `/opt/skald`, with config in `/etc/skald` and data in `/var/lib/skald`, and puts
the `skald` command in `/usr/local/bin`.

Upgrading later: `sudo skald upgrade` (a backup, migrations, a health check, a rollback), update notices
and optional automatic upgrades, and the `:2` Docker tag: [docs/UPGRADING.md](docs/UPGRADING.md).

### Option 4: From source

```sh
git clone https://github.com/spcaeo/skald && cd skald && sudo ./install.sh
```

Then the daily run and the live panel come from one command (it runs as the `skald` user, with
`/etc/skald/config.yml`, so use `sudo`):

```sh
sudo skald check            # verify yesterday's figures; store nothing
sudo skald run-daily        # check, collect, audit, dashboard, mail (the cron entry)
sudo skald live             # "Today so far"; safe every 2 minutes
sudo skald version          # brand, version and release
```

**Needs:** Python 3.11 or newer (tested on 3.11 to 3.14; `install.sh` installs 3.11 on Ubuntu
22.04, which ships 3.10). Nothing else: the standard library is enough. PyYAML is used only if it
is already installed, and Pillow, if installed, turns fetched site icons into small PNGs. The account that runs Skald must be able
to read the log (on Debian and Ubuntu, the `adm` group).

## Integrations

**The script tag (optional).** One line in your page's `<head>` adds page views, form steps, phone,
mail and outbound clicks, 75% scroll, and Calendly, Cal.com and HubSpot meeting bookings. It is under
6.5 KB of plain JavaScript, served by your own Skald and posting back to it (accepted only from
your site's own addresses). No third-party code, no cookie by default, and Do Not Track and Global
Privacy Control are respected. Every site on one Skald can use it: each site's events go to that
site, and visitor IDs are set per site. To link a sign-up on app.example.com to the visits on
www.example.com, share the visitor ID across subdomains: in the tag, or with one setting in Skald.

```html
<script src="/traffic-js/skald.js" data-site="example.com" defer></script>
```

```js
skald('track', 'cta_click', {id: 'pricing_top'});   // your own events
skald('consent', true);                             // with data-consent="required"
```

**Incoming webhooks.** Each tool's own signature is checked on the raw body; a repeat changes nothing.
The receiver runs on every install, Docker or install script, with or without the script tag.

| Tool | What Skald records |
| --- | --- |
| Calendly, Cal.com | `demo`: booked, cancelled, rescheduled (Calendly also no-show); keep only your own event types when one account books for several businesses |
| HubSpot | meetings as `demo`, contacts and workflows as `contact`, deals as `deal` (`won` at closed-won) |
| Stripe | `paid` (a checkout paid) |
| Typeform | `contact` |
| Zapier, Make, n8n, any script | the signed `json` hook, any short action name |
| Your own server | the signed `lead` hook (sign-ups, contacts, trials) |

**Which road fits your site** (a form plugin, Next.js on Vercel, a Postgres backend, no code,
Calendly, Stripe, HubSpot) is in the Help guide "Pick your road"; "Send leads from your backend in
5 minutes" has signed examples in curl, Node, Python and PHP. Settings > Integrations shows each
road's state (ready, never received, last received 2 h ago) and flags a lead that arrived by two
roads, which would count twice. `skald doctor` on the server says the same, with the fix.
Everything an app needs to send, check, correct and read back its leads is on one page: [docs/LEADS-REFERENCE.md](docs/LEADS-REFERENCE.md).

**Outgoing webhooks.** Signed, HTTPS only, never to a private address, retried five times over about
15 hours. They never carry a name or an email.

**Cloudflare on any plan.** The Skald Worker counts the pages Cloudflare serves from its cache. It
asks for your Skald's ingest address and the site's token, then needs your site's route; see
[docs/HOSTING.md](docs/HOSTING.md#cloudflare-on-any-plan-the-skald-worker).

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/spcaeo/skald/tree/main/deploy/cloudflare-worker)

**API.** A read-only JSON API over every dashboard figure, with revocable, scoped tokens
(`skald_<id>_<secret>`). See [docs/API.md](docs/API.md).

**MCP for AI agents.** 14 read-only tools: `overview`, `breakdown`, `top_pages`, `ai_activity`,
`leads`, `funnel`, `compare`, `page_story`, `live_today`, `data_quality`, `site_health`,
`conversions` (its `by` breaks completed actions and leads down by source, first touch, landing
page, country, campaign, device or tool), `list_sites` and, with the `read_private` scope only,
`find_person`. Answers call visits "an upper bound on people" and name every
withheld day. It cannot change anything.

```sh
claude mcp add --transport http skald https://stats.example.com/traffic-mcp \
  --header "Authorization: Bearer skald_<id>_<secret>"
```

Claude Desktop, ChatGPT (through the API) and any MCP client that can send a header work too. OAuth
sign-in is not offered yet. See [docs/MCP.md](docs/MCP.md).

## How Skald compares

Facts about other tools come from each vendor's own docs, pricing pages or source code, checked on
2026-10-07. Rows added after that date were checked for few or no other tools; the rest say nc. The full matrix,
with a source for every cell, is in **[docs/COMPARISON.md](docs/COMPARISON.md)**.

✓ yes · ◐ partly, or on some plans or setups · ✗ no, or not found in its docs · ? not confirmed on
the vendor's pages · – does not apply · nc = not checked

| | **Skald** | GA4 | Plausible | Umami ¹ | Matomo | PostHog | Cloudflare ² | GoAccess |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| How it collects | Server access log | JS tag | JS snippet | JS tracker | JS tag, or log import | JS SDK | JS beacon; AI Crawl Control at the edge | Server access log |
| Nothing runs in the visitor's browser | ✓ | ✗ | ✗ | ✗ | ◐ | ✗ | ◐ | ✓ |
| Counts visitors with an ad-blocker | ✓ | ✗ | ◐ | nc | ◐ | ◐ | ✗ | ✓ |
| AI training crawlers (GPTBot, ClaudeBot) | ✓ | ✗ | ✗ | ✗ ³ | ◐ | ✗ | ✓ | ✓ |
| AI assistants fetching a page to answer someone | ✓ | ✗ | ✗ | ✗ ³ | ◐ | ✗ | ✓ | ✓ |
| People who clicked through from an AI answer | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ◐ | ✗ |
| Splits AI traffic by why it came | ✓ | ✗ | ✗ | nc | ? | ✗ | ? | ✗ |
| Checks a crawler is who it claims to be | ✓ | – | – | nc | ? | – | ◐ | ✗ |
| Totals must add up, or the day is withheld | ✓ | ✗ | ✗ | nc | ✗ | ✗ | ✗ | ✗ |
| A second, independent recount of every figure | ✓ | ✗ | ✗ | nc | ✗ | ✗ | ✗ | ✗ |
| Events inside the page | ✓ ⁴ | ✓ | ✓ | nc | ✓ | ✓ | ✗ | ✗ |
| Funnels | ✓ | ✓ | ◐ | nc | ◐ | ✓ | ✗ | ✗ |
| Search queries, impressions, position | ✓ | ◐ | ◐ | nc | ◐ | ? | ✗ | ✗ |
| What AI assistants answer about you, per place and language | ✓ | nc | nc | nc | nc | nc | nc | nc |
| Scanners, probes and attack attempts from the server log | ✓ | ✗ | ✗ | nc | nc | nc | nc | nc |
| Known advisories matched to your site's stack | ✓ | ✗ | ✗ | nc | nc | nc | nc | nc |
| Ad cost and Google Ads link | ✗ | ✓ | ✗ | nc | ? | ? | ✗ | ✗ |
| Runs on your own server | ✓ | ✗ | ◐ | ✓ | ✓ | ◐ | ✗ | ✓ |
| Deleting one visitor on request | ✓ | ? | – | nc | ✓ | ? | – | ✗ |
| AI agents can query it (MCP) | ✓ | nc | nc | nc | nc | nc | nc | nc |
| Licence | ELv2 (source-available) | Closed, SaaS | AGPLv3 (Community Edition) | MIT | GPL | MIT (self-host) | Closed, SaaS | MIT |
| Price | Free to self-host | Free; 360 on request | From $9/month; self-host free | Cloud free to 100k events | Cloud from EUR 29/month; self-host free | 1M events/month free | Web Analytics free | Free |

<sub>¹ Umami is in the "Also checked" list of [docs/COMPARISON.md](docs/COMPARISON.md), not in its
full matrix; only its collection method, bot handling, AI referral channel, licence and price were
checked. ² Cloudflare Web Analytics (the beacon) together with AI Crawl Control, which needs your
traffic to pass through Cloudflare. ³ Umami excludes bots by default. ⁴ With the optional `skald.js`
tag or beacon.</sub>

### Where others lead (honestly)

- **Search itself.** Queries, impressions and ranking come only from Search Console and Bing
  Webmaster Tools. Keep them: Skald syncs their figures and shows them beside its own, but the
  figures stay the engines'.
- **Blocking attacks.** Skald shows who probes your server and what they tried; it blocks nothing.
  Keep your firewall or WAF.
- **Deep in-page analysis and ad spend.** GA4 and PostHog see far more inside the page, and GA4
  links to Google Ads. Skald's tag sends clicks, form steps and bookings, but no more.
- **Any host, any cache.** Script tools work anywhere. Skald needs a log: a page a CDN serves from
  its cache never reaches your server's log unless you feed Skald the CDN's own log.
- **Charging AI crawlers.** Cloudflare can charge per crawl. Skald can block, not charge.

### Who should use what

- **What people searched for, and where you rank:** Search Console and Bing Webmaster Tools.
- **Clicks, scrolls, funnels and ad spend inside the page:** GA4 or PostHog.
- **Simple cookie-free counts on any host:** Plausible.
- **Every visitor, crawler and AI fetch, with checked figures, on your own server:** Skald. It sits
  beside the tools above. Even the gap between Skald's count and GA4's is useful: it shows how much
  the script misses.

## Who it is for

- **Founders and marketers** who need to know whether ChatGPT, Claude and Perplexity read their
  site, and whether those answers send people and leads.
- **Agencies and SEO teams** who report AI visibility to clients and need figures that hold up.
- **Engineers and site owners** who want analytics with no third-party script, no cookie banner for
  counting, and data that stays on their own server.
- **Privacy-minded organisations** that must answer a deletion request with one command.

More in [docs/POSITIONING.md](docs/POSITIONING.md) and the story in
[docs/WHY-WE-BUILT-SKALD.md](docs/WHY-WE-BUILT-SKALD.md).

## Tech stack

| Layer | What it uses |
| --- | --- |
| Language | **Python 3.11+**, standard library only. No `pip install`. PyYAML and Pillow optional. |
| Storage | **SQLite**: `history.sqlite` (daily totals), `accounts.sqlite`, `conversions.sqlite`. One file each, easy to back up. |
| Dashboard | **Vanilla ES modules** and plain CSS. **No build step**, no framework, no third-party JavaScript, no web fonts, no request to anywhere else. A strict Content-Security-Policy. |
| Mail | Branded HTML reports with inline styles, plain-text alternative, nothing fetched from outside the mail. |
| Web server | **nginx** or **Caddy** in front for HTTPS (the Docker `https` profile adds Caddy with automatic certificates). The reference nginx setup adds a sign-in check with `auth_request` and rate limits. Reads nginx, Apache and Caddy logs. |
| Running | cron and systemd on a plain Linux server, or the **Docker** image. Two small local helpers on `127.0.0.1` (or a Unix socket). |
| Security | scrypt password hashes, HMAC-SHA256 for visitor keys and webhook checks, TOTP (RFC 6238) two-step sign-in. |
| Tests | 2,600+ tests, standard library `unittest`, exact numbers against hand-built logs. |

## Architecture

```mermaid
flowchart LR
  subgraph Visitors
    P[People]
    A[AI assistants and crawlers]
    B[Search engines and bots]
  end
  P & A & B --> W[Your web server<br/>nginx, Apache or Caddy]
  CDN[CDN logs<br/>Cloudflare, CloudFront, Fastly] --> L
  SHIP[skald-ship on another server] -->|HTTPS, ingest token| H
  W --> L[(Access log)]
  L --> C[skald collect and live<br/>classify, verify crawlers]
  C --> AU[Independent audit<br/>second count]
  AU -->|agrees| HI[(history.sqlite<br/>totals and labels only)]
  AU -->|disagrees| WH[Day withheld]
  HI --> D[Data files JSON]
  D --> UI[Dashboard<br/>ES modules, no build]
  D --> M[Daily and weekly mail]
  D --> API[Read-only API]
  D --> MCP[MCP server<br/>Claude, ChatGPT]
  TAG[skald.js tag and webhooks<br/>Calendly, Stripe, HubSpot...] --> BH[Beacon helper]
  BH --> CV[(conversions.sqlite<br/>conversions, people's visits)]
  CV --> D
  H[Refresh helper<br/>sessions, settings, tokens] --- UI
  H --> ACC[(accounts.sqlite)]
```

## Security and privacy

- **No addresses in history.** Stored history holds totals and labels only. Returning visitors use
  a keyed one-way hash, deleted after 30 days.
- **People, as a switch.** A new install keeps each visit with its IP address and browser
  (`privacy.keep_ips`, 395 days by default) and leads' names and emails (`conversions.identity:
  full`), apart from history and behind sign-in, so admins can follow a person across days. An
  install upgraded from before 2.4.0 keeps neither until you turn them on (Settings > Data
  retention > People, or `SKALD_KEEP_IPS=1` / `SKALD_IDENTITY=full`). Your privacy notice must say
  so first.
- **Shortened addresses** (2.15). Keep each visit's IP with its last part removed (203.0.113.57 is
  kept as 203.0.113.0; IPv6 keeps its first 48 bits): country, city and counts still work, and no
  exact address is kept (`privacy.keep_ips: short`, `SKALD_KEEP_IPS=short`). Counted twice too.
- **Wording for your privacy notice** (2.15). Settings > Data retention writes a short text for your
  privacy page from what the site really keeps, ready to copy. A starting point, not legal advice. Off, raw addresses stay only in your own log (14 days), the 6-hour request log (Site > Requests) and
  today's AI activity.
- **One true delete.** `skald forget` removes a person's address, visits, conversions, name and
  email everywhere Skald keeps them. Every person search is written to the audit log.
- **Webhooks keep only what counts.** Phone numbers, form answers, addresses and browser strings
  are dropped before anything is written; a name and email only when the site keeps them.
- **Signed everything.** Webhooks are checked against each tool's signature; outgoing hooks are
  signed and HTTPS only.
- **Hardened sign-in.** scrypt hashes, HttpOnly + Secure session cookie (only its SHA-256 stored),
  CSRF tokens, slow-down after failed sign-ins (no lock-out), optional TOTP, scoped tokens shown
  once, an audit log that never stores a password, token or address.
- **Two security reviews** were done on the 2.0 platform code (sign-in and sessions, sites, mail,
  webhooks) before this release, and their fixes are in it. For example, a site added in the
  dashboard must prove its domain before Skald collects for it.
- **Secrets stay out of the repo.** Secrets typed in the dashboard are write-only and kept in a
  `0600` file; SMTP logins come from an env file the config names.

Read **[SECURITY.md](SECURITY.md)** for what Skald stores, the hardening checklist and how to report a
vulnerability privately.

## FAQ

**Is Skald open source?**
Skald is **source-available** under the [Elastic License 2.0](LICENSE). You can read, use, change
and self-host it for free, for your own sites or your clients' sites, including at work. The one
thing you may not do without a commercial licence is offer Skald to others as a hosted or managed
service. Because of that limit, ELv2 is not an OSI-approved open-source licence, and we do not call it
one. Questions: [contact us](https://skaldanalytics.com/contact/?topic=licence).

**Can I use it for my agency's clients?**
Yes, if you run it for them. Selling access to a hosted Skald that others sign up for is the case that
needs a licence. If you are unsure, ask.

**Why do my numbers differ from Google Analytics?**
They count different things. GA4 counts browsers that run its script and accept it; ad-blockers and
refused consent hide many visits from it. Skald reads the log, so it sees those, plus AI and bots in
their own groups. Skald's "people" is an upper bound, because a browser's name is self-reported.

**Does it replace Google Analytics or Search Console?**
No. Keep Search Console for queries and ranking, and GA4 or PostHog for deep in-page analysis and ad
spend. Skald sits beside them.

**Can it tell me how often ChatGPT cites me?**
Partly. Skald sees each live fetch an assistant makes for a user's question, and each person who
clicks through, but not the answer the assistant gives. Clicks are a floor, because referrers are
often stripped. Clicks from Google AI Overviews look like ordinary Google clicks and cannot be told
apart.

**Does it count visitors who decline or ignore the cookie banner?**
Yes. Skald counts from your web server's own access log, and the server writes a line for every
request, whatever the visitor chose on the banner. Skald sets no cookie and stores nothing on the
visitor's device to count them. The optional script tag is the one part that follows the banner: it
can wait for consent (`data-consent="required"`), does nothing when Do Not Track or Global Privacy
Control is on, and keeps no visitor ID unless you turn IDs on. The log holds IP addresses, which are
personal data in places like the EU: you choose whether Skald keeps them in full, shortened (the last
part removed) or not at all, and for how long, and Settings > Data retention writes the wording for
your privacy notice.

**Does Skald keep IP addresses or emails?**
On a new install, yes: each visit with its IP address and browser (395 days by default), and a
lead's name and email, so an admin can follow one person across days. Both are settings (Settings >
Data retention > People). An install upgraded from before 2.4.0 keeps neither until you turn it
on; update your privacy notice first. Stored history never holds an address, and `forget` deletes a
person everywhere.

**Does it need cookies or a consent banner?**
Counting from the log needs no cookie and nothing in the browser. The optional tag sets no cookie by
default and can wait for consent. Signing in to the dashboard uses one session cookie for you. Your
own legal duties depend on your country and setup.

**What if my site is on Vercel, Netlify or a static host?**
Vercel and Netlify can send every request to Skald with a log drain (Vercel Pro, Netlify
Enterprise); step by step for Vercel: [docs/VERCEL.md](docs/VERCEL.md). Behind Cloudflare, use
Logpush or the Skald Worker. Otherwise use a CDN's log, ship the log from another server with
`skald-ship`, or use beacon-only mode (people only). See [docs/HOSTING.md](docs/HOSTING.md).

**What happens when the figures do not add up?**
The day is withheld: the dashboard says so, the mail for it is refused, and nothing is shown as zero.

**How heavy is it?**
A busy day's log takes about a second for the live view, and only today's files are opened. No
database server, no queue, no build step.

**Is there a hosted version?**
Yes, in beta. [Join the beta or start a 30-day free trial](https://skaldanalytics.com/beta/): we set
the account up for you within one working day, and no card is needed. Or run Skald on your own
server, free, with the quick start above.

## Roadmap

- An outside uptime check, beside today's same-server heartbeat.
- OAuth sign-in for MCP clients, so connector screens can add Skald without a header.
- Rotation of the returning-visitor key.
- More crawler owners verified (Baidu next).
- More advisories in Security's shipped list as they are published.
- Counting refinements listed in [docs/ROADMAP.md](docs/ROADMAP.md): HEAD requests, `/pricing` equal to `/pricing/`,
  `%xx` decoding.
- Hosted Skald out of beta.

Have a need that is not here? [Open a feature request](https://github.com/spcaeo/skald/issues/new/choose).

## Contributing

Bug reports, fixes and docs are welcome. Two house rules matter most: **every new figure gets a
second, independent count**, and **no file grows past 1,000 lines**. Setup takes a minute because
there is nothing to install:

```sh
git clone https://github.com/spcaeo/skald && cd skald
python3 -m unittest discover tests
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) (including the short contributor licence agreement) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Hosted Skald and commercial licences

**Rather not run a server?** Hosted Skald is in beta at
**[skaldanalytics.com](https://skaldanalytics.com/beta/)**: 30 days free, no card, your account
ready within one working day. Or join the beta list and we will contact you.

**Want to offer Skald to your own customers as a service?** That needs a commercial licence from
Space-O Technologies. **[Talk to us](https://skaldanalytics.com/contact/?topic=licence)**.

## Licence

[Elastic License 2.0](LICENSE). Copyright 2026 Space-O Technologies. "Skald" and the Skald logo are
trademarks of Space-O Technologies; see [NOTICE](NOTICE).

## Author

<table>
<tr>
<td valign="top">

**Rakesh Patel** built Skald.

- CEO, Space-O Technologies: software development and AI engineering.
- CEO, [LabsMedia](https://www.labsmedia.com).

Skald began as a tool for one question on our own website: is AI reading us, and does it send
anyone? No tool could answer it from data we owned, so we built one.

</td>
</tr>
</table>

---

<p align="center">
  <strong>If Skald shows you something your analytics could not, give it a ⭐ star</strong> so others
  find it, and <strong>Watch → Releases</strong> to hear about new versions.<br>
  <a href="https://github.com/spcaeo/skald/stargazers">Star Skald on GitHub</a> ·
  <a href="https://github.com/spcaeo/skald/issues">Report an issue</a> ·
  <a href="https://github.com/spcaeo/skald/discussions">Ask a question</a>
</p>
