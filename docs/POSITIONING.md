# Skald: positioning

**Every visit, truly told.**

Skald is self-hosted web analytics that reads the web server's own access log. It counts the
people, the AI assistants, the search engines and the bots that visit a site, files each request in
exactly one group, and checks every figure a second way before it shows it.

This page is for anyone deciding whether Skald fits: who it is for, what jobs it does, why it
matters now, and how it sits beside the tools you already use. The full feature matrix, with a
source for every competitor fact, is in [COMPARISON.md](COMPARISON.md). The story is in
[WHY-WE-BUILT-SKALD.md](WHY-WE-BUILT-SKALD.md).

## One line

> Skald shows you the visitors your analytics cannot see (AI assistants, crawlers and bots) beside
> the people, from a record you own, with every number checked twice.

## Why now

The way people find a business is changing. More and more of them ask ChatGPT, Claude, Perplexity
or Copilot first. Behind that question, three kinds of AI traffic reach your site:

1. **Training crawlers** collect pages to train models. Nobody is waiting on them.
2. **Live fetches.** An assistant fetches your page *while* answering someone. A real person is
   waiting on the answer.
3. **Click-throughs.** A person clicks the link the assistant cited and arrives on your page.

Script-based analytics see only the third, and only when the referrer survives. The first two run no
JavaScript, so tools built on a tag never count them, and Google Analytics drops known bots on
purpose. The usual tools have added an "AI" channel for click-throughs. None of them sees the
assistant reading your page to answer someone.

The server log sees all three. A tag-based tool sees none of the first two. And for the third,
when the referrer is stripped, Skald goes one step further: an assistant fetches the page while
answering, so a direct visit landing on that page minutes later is shown as *likely* from that
assistant. Labelled as an estimate, kept apart from the counts. How large that share is
differs from site to site; Skald's first run measures it from the site's own log.

## Who it is for

| Who | What they need | What Skald gives them |
| --- | --- | --- |
| **Founders and marketing leads** of B2B and service businesses | "Is AI reading us, and does it send us leads?" | AI assistants by name and reason, citations clicked, and leads and bookings by first source, AI included. |
| **SEO and content teams, agencies** | AI visibility they can report to a client without hand-waving | Pages each assistant fetched, crawler names verified, robots.txt beside what each crawler did, figures that reconcile. |
| **Engineers and site owners** | Analytics with no third-party script, nothing to block, data on their own server | Standard-library Python, SQLite, no build step, no outside requests, Docker or a plain server. |
| **Privacy-minded organisations** | Counting without cookies or consent prompts for counting, and deletion on request | No script needed, no addresses in history, short windows for raw data, one command to forget an address. |
| **Site owners and their admins** | "Is anyone probing our server, and did it hand them anything?" | Security from the same log: scanners and what they asked for, any probe answered with a real file, attack attempts, fake browsers, a block list to review, and the site's stack against known advisories. |
| **Teams using AI agents** | Ask about traffic in plain words inside Claude or ChatGPT | An MCP server with 14 read-only tools that name withheld days and never call visits "people". |

## Jobs to be done

- **"Tell me if AI is reading us."** Which assistants came, which pages they fetched, for training
  or to answer someone live, and whether the crawler is who it says it is.
- **"Tell me if AI sends us business."** People who clicked through from an assistant, the leads,
  demos and payments that followed, by first and last source.
- **"Tell me the true number of people."** An honest upper bound, with bots, scanners and our own
  team taken out, and ad-blocked visitors put back in.
- **"Tell me when something breaks."** Site down, logging stopped, 5xx bursts, 404 surges, crawler
  bursts and traffic drops, live, with a deploy marker on the chart.
- **"Tell me who is probing us."** Scanners and what they looked for (`.env`, `wp-login.php`,
  Terraform files), whether the server ever answered one with a real file, login hammering and
  bursts, and which known advisories apply to the site's server, PHP, WordPress or Node.js.
- **"Let me decide which crawlers may come."** Allow, block, or block only training, per assistant,
  applied by the web server.
- **"Let me prove the numbers."** Every figure counted twice, a day that disagrees withheld, a
  data-quality panel, and an export of everything.

## How it sits beside other tools

Skald is not a replacement for everything. It is the one tool that answers *who actually visited*
from the record that saw every visit. Most sites will keep one or two others beside it.

**Google Analytics 4.** The default for in-page behaviour and ad spend, with a Google Ads link.
It counts only browsers that run its tag and accept it, drops known bots on purpose, and its full
processing can take 24 to 48 hours. Keep GA4 for ads and deep in-page analysis. Use Skald for AI,
bots, ad-blocked visitors and live figures. The gap between the two counts is itself a finding: it
shows how much the tag misses.

**Search Console and Bing Webmaster Tools.** The only source of search queries, impressions and
ranking, and of the search engine's own AI citation data. Keep them. Skald syncs their figures
every 6 hours and shows them beside its own visits from search, but the figures stay the engines'.

**Plausible, Umami, Fathom.** Simple, privacy-friendly, cookie-free tag analytics that work on any
host. They filter bots out, so they do not report AI crawlers or live AI fetches; each has added an AI
referral channel for click-throughs. Choose them when you cannot read a server log. Choose Skald
when you can, and want the machines too.

**Matomo.** A broad self-hosted suite, GPL, with a tag or a log importer. It can report AI chatbots
through specific integrations or log import with bots enabled. Skald goes deeper on one thing:
every request classified, crawler names verified, AI split by reason, and every figure recounted.

**PostHog.** Product analytics with a JavaScript SDK: in-page events, funnels and user paths.
Different job. Skald's tag sends clicks, form steps and bookings, but Skald is not a product-analytics suite.

**Cloudflare.** Web Analytics is a free beacon (blocked by ad-blockers, by Cloudflare's own FAQ).
AI Crawl Control sees and controls AI crawlers, including charging per crawl, when your traffic
passes through Cloudflare. Skald works on any server whose log you can read, keeps the data on that
server, and blocks crawlers but does not charge them.

**GoAccess and AWStats.** Log analysers. GoAccess is free (MIT), updates every second and has an
AI-crawler category. By its own docs it tells crawlers apart by user agent only, has one AI
category, and has no totals check or named users. AWStats runs in batches from cron, and its author
recommends moving to Matomo. Skald is built for teams that need verified names, AI split by reason,
checked figures, conversions and accounts.

## Advantages, in one list

- **Sees the machines.** AI training crawlers and live AI fetches, by name, with pages.
- **Says why AI came.** Training, answering someone, or a person clicking a citation; never double
  counted.
- **Finds hidden AI referrals.** Direct visits and leads that an assistant very likely sent, from its
  fetch minutes before; labelled "likely", never mixed into the counts.
- **Checks names.** Crawlers verified against owners' published addresses or DNS; fakes filed apart.
- **Security from the same log.** Who probes the server, whether any probe got a real file, attack
  attempts, a block list, and the site's stack against known advisories. It blocks nothing itself:
  use it beside your firewall.
- **Proves its numbers.** Groups add up to the log; a second count checks every figure; a day that
  fails is withheld.
- **Unblockable and cookie-free.** Nothing runs in the visitor's browser to count a visit.
- **Live.** Today so far every 2 minutes, requests every 15 seconds on Real time, what the newest
  visitors are doing now; each request of the last 6 hours, with its reason.
- **Results.** Every lead in one list, funnels and conversions from the tools you already use;
  names and emails only where the site keeps them, and only for owners and admins.
- **Yours.** Runs on your server, standard library only, SQLite files you can copy, no outside
  requests.
- **Agent-ready.** MCP and a read-only API.
- **Works where your site lives.** Vercel and Netlify log drains, a Cloudflare Worker for cached
  pages on any plan, CloudFront and Fastly logs, or your own server's log; Settings › Connections
  checks the site, suggests the way in and ends with a connection test.

## Honest limits

- You need a server whose log you can read (or a CDN log, a shipped log, or beacon-only mode for
  people only).
- A page a CDN serves from its cache never reaches the origin's log; feed Skald the CDN's log, or
  the Skald Cloudflare Worker (any plan).
- "People" is an upper bound, because a browser's name is self-reported.
- AI click-throughs are a floor, because referrers are often stripped. Skald estimates the hidden
  part ("likely from" an assistant, from its fetch minutes before), but an estimate is not a count,
  and an assistant that answers from its memory, without fetching, leaves no trace. Google AI Overview
  clicks look like ordinary Google clicks.
- Search queries only as Search Console and Bing report them; no ad spend, no session replay.
- Security reads only what the access log records: it cannot see request bodies or file contents,
  and it does not block anything.

## Pricing and licence intent

- **Self-hosting is free**, under the [Elastic License 2.0](../LICENSE): use it, change it, run it
  for your own sites or your clients' sites.
- **Offering Skald to others as a hosted or managed service needs a commercial licence** from
  Space-O Technologies. This keeps the project sustainable and protects the hosted version.
- **Hosted Skald is in beta** at [skaldanalytics.com/beta](https://skaldanalytics.com/beta/): 30
  days free, no card, the account set up by us. In the product, sign-up, plans, limits and Stripe
  billing are built and switched off. Prices are not set yet. To licence Skald for your own
  service: [contact us](https://skaldanalytics.com/contact/).

## Messaging guide

- **Tagline:** Every visit, truly told.
- **Headline:** Your analytics cannot see the new visitors.
- **Proof points to use:** every figure counted twice; 14 read-only MCP tools; 2,600+ tests;
  standard library only. Never quote one site's AI share as typical: say the reader's own log will
  show theirs.
- **Words to keep apart:** requests, people, machines. Never call requests or AI fetches "visitors".
- **Words to avoid:** "100% accurate", "replaces Google Analytics", "open source" (say
  "source-available"), "real-time" without saying how fresh (visitors every 2 minutes, requests
  every 15 seconds), "blocks attacks" or "WAF" (Skald reports; it does not block).

## About the author

Skald was built by **Rakesh Patel**, CEO of Space-O Technologies and CEO of
[LabsMedia](https://www.labsmedia.com), to answer one question on his own company's website: is AI
reading us, and does it send anyone?
