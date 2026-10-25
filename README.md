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
    <img src="docs/screenshots/hero-light.png" alt="The Skald dashboard for example.com, Overview, Summary for the last 30 whole days, 22 Sep to 21 Oct, compared with 23 Aug to 21 Sep: five key figures with their change (people 2,409, up 20%; from search engines 885; returning people 617; leads 116; sent by AI assistants 174), the chart with the period before dashed and each day's leads as dots, and the start of What changed: is it working?" width="960">
  </picture>
</p>

---

## What's new

- **2.35.0: is it working, and what to fix next** ([changelog](CHANGELOG.md#2350-2026-10-25)).
  Summary says what changed against the period before, with exact dates; Pages sorts by Rising
  and Falling with each page's change date from the sitemap; Insights is a to-do list that
  re-checks each fix; "Did my change work?" on each page; Not found suggests the closest live page
  for old addresses; each page has an AI readiness check. Also a trail with Back over every tab, a
  dry run for a new log, a copy icon on every value, and counting fixes (recount after upgrading).
- **2.34.0: social networks** ([changelog](docs/CHANGELOG-2.32-2.34.md#2340-2026-10-24)). Traffic › Sources has a
  Social network tab (X, LinkedIn, Facebook and more, each network's addresses added up), and All
  sites shows every site's Search, Social, X, LinkedIn, AI and Direct side by side.

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
*"claims to be GPTBot"*. Every name, owner and check: [`bots.json`](https://skaldanalytics.com/bots.json).

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
from any server: **one command** (`curl … | sudo bash`, with or without Docker; it finds the log
by itself). Settings > Connections walks you through each one, with a **Test** that starts by itself; step by step for Vercel: [docs/VERCEL.md](docs/VERCEL.md). A Next.js
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
- **One summary mail a day** (01:00 in your time zone): each person gets one mail with every
  site's open security items, to-dos and set-up problems, never a mail per item.

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
- **Copy on every value, open on every URL:** point at a page or URL and two icons copy it or open
  it in a new tab; an address, user agent, email, name or server line gets the copy icon alone.
- **Is it working?** (Overview › Summary): the period's exact dates, **Include today**, five key
  figures with their change, the sources and landing pages that rose and fell, pages to work on
  (most visits leave at once, no form), and new and updated pages with whether search found them.
- **Insights as a to-do list:** each item with its proof and the full list behind it (old pages
  still asked for, server errors, Markdown copies AI asks for); mark it done, download it, send it
  to the team, and Skald re-checks it with the same measure: did it work?
- **Did my change work?** Mark the day you changed a page (content, title, a redirect): Skald sets
  the same whole days before and after side by side (visits, leads, search, AI, left at once), with
  Up, Down, No clear change or Too early to tell. A sitemap date offers to track it for you.
- **A trail with Back** over every tab: the steps you took (Summary, a source, a page), each a link
  to that exact view; browser Back and Forward walk the same steps.
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
  log did not have is **Not recorded**. Under Direct, its **likely** cause (payment return,
  in-app browser, shared link), an estimate with its own second count.
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
  are told apart by their tags and click IDs. Calls under `/api/` are never a page view, nor are machine addresses (WordPress
  REST and feed calls, oEmbed, Markdown copies; a switch per site).
- A new outside source starts a new visit: someone who opens the site directly and comes back from
  ChatGPT minutes later is two visits, the second from ChatGPT, so an AI assistant's visit is never
  hidden inside an earlier one.
- Anonymous journeys: each visit's pages in order, kept 7 days by default.
- **Traffic › Pages:** sort by Most visits, Rising, Falling, Recently changed or Needs work; pages
  per visit, left at once, AI reads, and each page's change date from your sitemap's `lastmod`.
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
- AI assistants by name and by reason (ChatGPT, Claude, Perplexity, Gemini, Copilot, Meta AI,
  DeepSeek, Grok and more), with the pages each one fetched. The whole list is public:
  [skaldanalytics.com/bots.json](https://skaldanalytics.com/bots.json), built from the code.
- **AI readiness per page:** `robots.txt` for each AI crawler, crawler errors, the sitemap and its
  `lastmod`, the Markdown copy, AI asking for a 404 and the last AI read, each good or needs
  attention with its evidence and the fix; **Pages AI can't read well**, worst first; and AI reads
  per page against the period before, followed to AI visits and leads.
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
- One section, **Leads & sales**, one question per tab: Leads, Summary, Sources, Revenue,
  Calendar bookings, Funnels, Events and Find a person.
- **Revenue (2.32):** which sources (AI assistants among them), pages and campaigns made money: net revenue, sales, refunds,
  new customers, renewals and revenue per visitor, per currency, never converted; by source, campaign, page, country or your own
  tags; lifetime value by first source. Stripe's amounts are read; Polar, Dodo, Paddle, Lemon Squeezy, Gumroad or your own server send `value` and `currency` through the lead hook, Zapier, Make or n8n. Counted twice; a day that disagrees is withheld.
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
- **Add a site** in five steps you can leave and resume. Pick your AI agent (Claude Code, Codex,
  Cursor or another) and paste one line: it holds a one-time code that gives the keys once, for
  this site only, then stops; the agent connects the logs, the script tag and the lead file, and
  Skald ticks each step as it happens. Or set it up by hand: one command on the server (or one
  file), with `skald-ship-check` to say what is wrong in plain words; a private link to share the
  steps with your developer.
- **Send set-up to someone:** one zip by mail with every way in, the keys, and a `CLAUDE.md`, so a
  client gives the folder to Claude Code and says "Set up Skald from CLAUDE.md".
- **Leads in one file:** PHP, Node or Python, one function to call; a WordPress plugin with no
  code; or a plain key for Zapier and form tools.
- **Set up this site** on Overview, and always in Settings › Connections: each open line one plain
  sentence and a Set up button.
- **Test a sample** (or `skald try-log <file>` on the server): paste a few lines of a new log and
  see which reader fits, what it could not read and why, and the five groups adding up. Nothing kept.
- **Next.js:** one field in the site's log format and every click inside the site counts as a
  page, never a prefetch.

**Site**
- Health, Alerts, Requests, Not found, Speed and Data quality, as tabs of one section.
- 404s and who met them (people, probes, crawlers), server errors by page, page speed, uptime from
  the heartbeat with every outage.
- **Lost pages:** old addresses people, search engines and AI still ask for, the closest live page
  and how close, and the nginx or Apache line (redirect, or 410 gone) to copy.
- Alerts: site down, logging stopped, 5xx burst, 404 surge, crawler burst, new crawler, traffic
  drop, each switched on or off per site, and a **sale** (or refund) once leads carry money. A failed
  morning run sends one short mail. Any alert can go to **Slack** or any tool, as `alert.opened`.
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
- CDN logs: Cloudflare Logpush, CloudFront, Fastly, Akamai DataStream 2. Cached pages count too.
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

### Is it working, and what to fix next (2.35)

<p align="center">
  <img src="docs/screenshots/summary-what-changed.png" alt="Overview, Summary, What changed: is it working? for 22 Sep to 21 Oct against 23 Aug to 21 Sep: more people than the period before, 2,409 against 2,012, the biggest rise and drop; Sources and Landing pages each with Now, Before and Change, such as Search engine 885 against 761, up 16%, and /blog/ai-crawlers-explained about the same" width="900"><br>
  <strong>What changed: is it working?</strong> Sources and landing pages, now against before.
</p>

| | |
| :---: | :---: |
| <img src="docs/screenshots/summary-work-pages.png" alt="Overview, Summary: Work on the page, or on traffic? with its two lists and what left at once means, beside New and updated pages: are they getting found?, the pages changed since 22 Sep with their sitemap date, visits, search visits, first search visit and when Google fetched them" width="440"><br>**Work on the page, or on traffic?** And are new pages found? | <img src="docs/screenshots/pages-sorts.png" alt="Traffic, Pages, Landing pages and their leads sorted by Rising with Compare on: each page's visitors now and before, the change, leads, pages per visit, left after one page, AI reads and the date it last changed" width="440"><br>**Pages: Rising, Falling, Recently changed.** And each page's change date. |
| <img src="docs/screenshots/insights-todos.png" alt="Overview, Insights, To do now: Send old pages somewhere useful, Fix the server errors and Give AI the Markdown copies it asks for, each with its proof, what to do and what Skald will re-check, and the buttons Show the list, Download CSV, Copy link, Open, Mark done and Not now; then Done, and did it work? and Pages you changed: did it work?, with each tracked change and its verdict" width="440"><br>**Insights as a to-do list.** Mark it done; Skald checks it worked. | <img src="docs/screenshots/not-found-lost.png" alt="Site, Not found, Old addresses still asked for: 2 old addresses, asked by people 40 times, search engines 15 and AI 13; each with the closest live page, how close, and the nginx line to redirect it or answer 410 gone" width="440"><br>**Lost pages.** The closest live page and the server line to copy. |
| <img src="docs/screenshots/ai-readiness.png" alt="A page's story, AI readiness for /guides/webhooks/: 3 of 6 need attention; robots.txt keeps Google-Extended out, with the line to allow it; one server error to a crawler; in the sitemap; the Markdown copy answered 404 nine times; no 404 for the page; last AI read on 21 Oct" width="440"><br>**AI readiness per page.** Six checks, each with its evidence and fix. | <img src="docs/screenshots/ai-cant-read.png" alt="AI and bots, Assistants, Pages AI can't read well: filters for Markdown copy, 404, errors, robots.txt and slow; each page, worst first, with what AI got, which crawlers, whether it is in the sitemap and what to do" width="440"><br>**Pages AI can't read well.** Worst first. |
| <img src="docs/screenshots/change-tracker.png" alt="A page's story for /pricing/, Did my change work?: Changed 22 Sep, New title, compared: the 28 whole days after against the 28 before, a chart with the change marked, and per measure the daily figure before and after, the change and what it says, such as visits that started here 12 a day before, 15 after, up 20%, Up" width="440"><br>**Did my change work?** Before and after, with a verdict. | <img src="docs/screenshots/trail-back.png" alt="The trail over Traffic, Pages: Back to Pages, then Overview › Summary, Source: Search engine, Traffic › Pages and /pricing/, each a link to that view" width="440"><br>**The trail and Back.** Every step, one click back. |
| <img src="docs/screenshots/ai-reads-trend.png" alt="AI and bots, Assistants, AI reads by page: now against before: each page's live fetches by assistants now and in the period before, the change, the fetches by assistant, and the AI visits and leads that started there" width="440"><br>**AI reads per page.** Now against before, to visits and leads. | <img src="docs/screenshots/test-sample.png" alt="Settings, Connections, Test a sample of a log, step 2: Skald can read this log, with the warnings below; nginx_combined, sure; 200 lines, 199 read and line 121 not, with why; the times and zone; no host field; the five groups, 160 + 19 + 11 + 9 + 0 = 199, adds up" width="440"><br>**Test a sample.** Can Skald read a new log? Before the next run. |

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
  <img src="docs/screenshots/leads-list.png" alt="Leads and sales, Leads, on its default of the last 7 days: the heading Last 7 days, Fri 16 Oct to Thu 22 Oct (today, so far), the count against the same days and hour of the week before, Today so far: 6 of these leads, Show today (live), and one row per lead with today's first, each marked live" width="900"><br>
  <strong>Leads.</strong> Who they are, what they did and where they came from, in one list.
</p>

<p align="center"><img src="docs/screenshots/revenue.png" alt="Leads and sales, Revenue, on the demo's sample data for the last 90 days: a Currency switch with USD chosen and EUR beside it, Breakdown and Tag options; net revenue $16,798.40 ($16,818.00 sold, $19.60 refunded), 33 sales, 1 refund, 29 new customers, 4 renewals and $3.78 revenue per visitor over 4,440 visitors of the 58 days with values; the line Also in this period, never added: €488.40 net from 8 sales; and the start of Revenue by source (last touch)" width="900"><br><strong>Revenue (2.32).</strong> Which sources made money, per currency, never converted; refunds, renewals and lifetime value.</p>

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

### Connecting a site (2.16, 2.17, 2.31)

<p align="center">
  <img src="docs/screenshots/connections.png" alt="Settings, Connections: Set up example.com, 1 of 5 left (logs arriving, visits count as people, countries shown, the script tag, the lead hook and privacy ticked; the mail recipient with a Set up button), then three tasks: send this site's visits to Skald, read your figures (API) and connect an AI assistant (MCP), and the organisation's tokens with what each is for" width="900"><br>
  <strong>Connections.</strong> The set-up list, three guided tasks with a Test at the end, and your tokens.
</p>

| | |
| :---: | :---: |
| <img src="docs/screenshots/site-check.png" alt="Add a site, step 1: example.com typed in, and What Skald found: server nginx on Ubuntu, no platform in front, built with Next.js, host names example.com and www.example.com, page assets /_next/static/, and the suggestion: a Linux server with Docker" width="440"><br>**Skald checks your site** (your own Skald). And suggests the way in. | <img src="docs/screenshots/add-site-wizard.png" alt="Add a site, step 3 of 5, Which AI agent are you using: Claude Code, Codex, Cursor, Claude.ai or ChatGPT, Another agent, and No AI agent: set it up by hand" width="440"><br>**Add a site in five steps** (2.31). Pick your AI agent, or set it up by hand. |
| <img src="docs/screenshots/add-site-agent-line.png" alt="Add a site, step 4 of 5, Send this line: set up Skald for example.org, read https://stats.example.com/traffic-kit/llms.txt and use code (hidden), works once, 24 hours; Copy, Show code, Make a new line, Cancel this line, and Is it safe to paste this into a chat?" width="440"><br>**One line for your AI agent** (2.31). A one-time code, never a key. | <img src="docs/screenshots/add-site-agent-watch.png" alt="Add a site, step 5 of 5, Watch it connect: the agent read the steps, took the keys once, sent its report, the first log lines arrived; then what the agent did: hosting, web server, access log, framework" width="440"><br>**Watch it connect** (2.31). Each step ticks; the agent's report in plain words. |
| <img src="docs/screenshots/connections-install.png" alt="Send this site's visits to Skald, step 2 of 3, Run one command: curl -fsSL https://stats.example.com/traffic-kit/ and a one-time code, piped to sudo bash, with Copy, Download as one file, Email it to your server admin and Make a new command" width="440"><br>**One command** (2.30). With or without Docker; the token is made for you. | <img src="docs/screenshots/setup-checklist.png" alt="Set up example.com: six lines ticked and one open, Mail recipient confirmed: 'Nobody gets the daily mail yet', with a Set up button" width="440"><br>**Set up this site.** Each open line has a Set up button. |
| <img src="docs/screenshots/lead-setup-file.png" alt="Connect your leads, step 3 of 4: choose PHP, Node or Python, Download skald-lead.php, then require it and call skald_lead with the lead's ID, the action and the email; the secret goes in SKALD_LEAD_SECRET" width="440"><br>**Leads in one file** (2.30). One function to call; WordPress needs no code. | <img src="docs/screenshots/setup-pack.png" alt="Send set-up to someone: up to three email addresses, a note, Include the keys ticked, Send by email and Download (.zip), and the line: give the folder to Claude Code and say Set up Skald from CLAUDE.md" width="440"><br>**Send set-up to someone** (2.30). One zip a person or Claude Code can follow. |
| <img src="docs/screenshots/links-copy-open.png" alt="Traffic, Pages: pointing at /pricing/ shows a copy button and an open-in-a-new-tab button at the end of the path" width="440"><br>**Copy and open on every URL** (2.21). Every view has its own link. | <img src="docs/screenshots/copy-values.png" alt="A scanner's detail: pointing at its user agent, Go-http-client/1.1, shows the copy button beside it" width="440"><br>**Copy any value** (2.35). Addresses, user agents, emails, names. |

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
| <img src="docs/screenshots/overview.png" alt="Overview, Summary for 90 days with the note that 62 of them are whole and verified: the period's dates, Include today and Compare switches, five key figures, a chart with each day's leads, and the countries and top pages" width="440"><br>**Overview.** The period at a glance, with its exact dates. | <img src="docs/screenshots/compare-mode.png" alt="Compare with the previous period switched on: Traffic, Sources with A, B and the change beside every source" width="440"><br>**Compare with…** Previous period, last year or any period. |
| <img src="docs/screenshots/traffic-sources-grid.png" alt="Traffic, Sources: one grid with segments for source type, referring site and campaign, with visitors, the change, a trend, leads and lead rate, then where returning visitors first came from" width="440"><br>**Sources.** One grid; search, filters and sort in the address. | <img src="docs/screenshots/visitors.png" alt="Traffic, Visitors for 7 days: the visitor flow from source through four pages, and each visit with its time, country, city, device, source, new or returning, pages and time on site" width="440"><br>**Visitors.** The flow, then each visit page by page. |
| <img src="docs/screenshots/direct-likely.png" alt="Traffic, Sources, Direct, likely (inferred), 90 days: of 1,452 Direct visits, 82 likely a shared link (Instagram 43, WhatsApp 39), 37 likely a checkout return (Stripe), 26 likely an in-app browser (Instagram app), the rest with no likely cause" width="440"><br>**Direct, likely.** What Direct probably was, as an estimate. | <img src="docs/screenshots/alerts-sale.png" alt="Site, Alerts: the Sale and Refund on a sale switches, off by default, under the other alert rules" width="440"><br>**Sale alerts.** One alert per sale, by mail or Slack. |
| <img src="docs/screenshots/social-networks.png" alt="Traffic, Sources, Social network, 90 days: LinkedIn 360, X 71, Reddit 61, Hacker News 45, Facebook 18 and Instagram 10 visitors; X open: t.co, twitter.com, the X Android app and x.com, and the pages its visitors landed on" width="440"><br>**Social networks.** One row per network, every address added up. | <img src="docs/screenshots/across-sites.png" alt="All sites, Where visitors came from, 30 days: for each site, visitors from Search, Social, X, LinkedIn, Facebook, Instagram, Reddit, YouTube, AI and Direct" width="440"><br>**All your sites.** Each source side by side. |
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
mail and outbound clicks, 75% scroll, and Calendly, Cal.com and HubSpot bookings. Under 6.5 KB of
plain JavaScript served by your own Skald and posting back to it: no third-party code, no cookie by
default, Do Not Track and Global Privacy Control respected. Visitor IDs are set per site and can be
shared across subdomains ([docs/INTEGRATIONS.md](docs/INTEGRATIONS.md#the-script-tag)).

```html
<script src="/traffic-js/skald.js" data-site="example.com" defer></script>
```

**Incoming webhooks**, each checked against its tool's own signature on the raw body (a repeat
changes nothing): Calendly and Cal.com bookings, HubSpot meetings, contacts and deals, Stripe
payments, Typeform, the signed `json` hook for Zapier, Make, n8n or any script, and the signed
`lead` hook from your own server. Settings > Integrations shows each road's state and flags a lead
that arrived by two roads. The Help guides "Pick your road" and "Send leads from your backend in 5
minutes" cover each kind of site; everything an app needs to send, check and read back its leads is
on one page: [docs/LEADS-REFERENCE.md](docs/LEADS-REFERENCE.md).

**Outgoing webhooks.** Signed, HTTPS only, never to a private address, retried five times over about
15 hours, and never with a name or an email.

**Cloudflare on any plan.** The Skald Worker counts the pages Cloudflare serves from its cache
([docs/HOSTING.md](docs/HOSTING.md#cloudflare-on-any-plan-the-skald-worker)).

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/spcaeo/skald/tree/main/deploy/cloudflare-worker)

**API and MCP.** A read-only JSON API over every dashboard figure, with revocable, scoped tokens
([docs/API.md](docs/API.md)), and an MCP server with 14 read-only tools for Claude, ChatGPT and any
MCP client that can send a header: `overview`, `breakdown`, `top_pages`, `ai_activity`, `leads`,
`funnel`, `compare`, `page_story`, `live_today`, `data_quality`, `site_health`, `conversions`,
`list_sites` and, with the `read_private` scope only, `find_person`. Answers call visits "an upper
bound on people" and name every withheld day; it cannot change anything. OAuth sign-in is not
offered yet ([docs/MCP.md](docs/MCP.md)).

```sh
claude mcp add --transport http skald https://stats.example.com/traffic-mcp \
  --header "Authorization: Bearer skald_<id>_<secret>"
```

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

**What if my site is on Vercel, Netlify or a static host?**
Vercel and Netlify can send every request to Skald with a log drain (Vercel Pro, Netlify
Enterprise); step by step for Vercel: [docs/VERCEL.md](docs/VERCEL.md). Behind Cloudflare, use
Logpush or the Skald Worker. Otherwise use a CDN's log, ship the log from another server with
`skald-ship`, or use beacon-only mode (people only). See [docs/HOSTING.md](docs/HOSTING.md).

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
