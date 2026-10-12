# Skald compared

**Every visit, truly told.**

How Skald stands beside Google Analytics 4, Search Console, Bing Webmaster Tools, Plausible, Matomo, Cloudflare, GoAccess, PostHog and Known Agents, grouped by module. The story behind it is in [WHY-WE-BUILT-SKALD.md](WHY-WE-BUILT-SKALD.md); the same matrix as a page, with filters, is [comparison.html](comparison.html) (made from the 2026-10-07 version: the 2026-10-11 rows and notes are only here and in the dashboard's About page).

Every competitor fact comes from that vendor's own docs, pricing page or source code, checked on 2026-10-07. Skald's column claims only what is built and tested in its code (updated 2026-10-11); a part that is off until an install switches it on says so in its note, and anything on the roadmap says *planned*. Where a fact could not be confirmed on the vendor's own pages the cell says `?`. A `✗` means the feature is not offered, or we found no sign of it in the vendor's docs. Rows added on 2026-10-11 (accounts, conversions, webhooks, MCP, the hosted layer, engagement, campaign tag problems, exit rate) have not been checked for the other tools yet: their cells say *not checked*.

| Mark | Means |
| --- | --- |
| ✓ | Yes |
| ◐ | Partly, or only on some plans or setups (see the note) |
| ✗ | No, or not found in its own docs |
| planned | On Skald's roadmap, not built yet |
| ? | Could not be confirmed from the vendor's own pages |
| – | Does not apply (the tool does not measure site visits) |
| not checked | A row added after 2026-10-07; this tool was not checked for it yet |

## Data collection

How each tool gets its numbers, and who that leaves out.

**Method**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| How it collects | Reads the web server's access log [^1] | Google tag (JavaScript) in the page [^2] | Google's own search data; nothing on your site [^3] | Bing's own search data; nothing on your site [^4] | JavaScript snippet [^5] | JavaScript tag, or server logs through its importer [^6] | JavaScript beacon; AI Crawl Control at Cloudflare's edge [^7] | Reads the web server's access log [^8] | JavaScript SDK [^9] | Events sent from your server, CDN or WordPress [^10] |
| Nothing runs in the visitor's browser <br><sub>No script, no cookie</sub> | ✓ [^256] | ✗ | – | – | ✗ [^11] | ◐ [^12] | ◐ [^13] | ✓ | ✗ | ✓ [^14] |
| Works where you cannot read the server's log <br><sub>Hosted builders, static hosts</sub> | ◐ [^15] | ✓ | – | – | ✓ | ✓ [^16] | ◐ [^17] | ✗ | ✓ | ◐ [^18] |
| Counts pages a CDN served from its cache | ✓ [^19] | ✓ | – | – | ✓ | ✓ [^20] | ✓ | ◐ [^21] | ✓ | ✓ [^22] |
| Takes the log from another server <br><sub>A small shipper sends new lines as they are written</sub> | ✓ [^257] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |

**Who it can see**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Visitors with an ad-blocker | ✓ | ✗ [^23] | – | – | ◐ [^24] | ◐ [^25] | ✗ [^26] | ✓ | ◐ [^27] | ✓ [^28] |
| Visitors who decline cookies | ✓ [^29] | ◐ [^30] | – | – | ✓ [^31] | ◐ [^32] | ✓ [^33] | ✓ | ◐ [^34] | ? |
| AI training crawlers <br><sub>GPTBot, ClaudeBot, CCBot</sub> | ✓ | ✗ [^35] | – | – | ✗ [^36] | ◐ [^37] | ✓ [^38] | ✓ [^39] | ✗ [^40] | ✓ [^41] |
| AI assistants fetching a page to answer someone, live <br><sub>ChatGPT-User, Perplexity-User, Claude-User</sub> | ✓ [^42] | ✗ | – | – | ✗ [^43] | ◐ [^44] | ✓ [^45] | ✓ [^46] | ✗ | ✓ [^47] |
| Search engine crawlers | ✓ | ✗ [^48] | ◐ [^49] | ? | ✗ [^50] | ◐ [^51] | ◐ [^52] | ✓ [^53] | ✗ | ✓ [^54] |
| Scanners and credential probes <br><sub>Requests hunting for .env, wp-login</sub> | ✓ [^55] | ✗ | – | – | ✗ | ◐ [^56] | ◐ [^57] | ◐ [^58] | ✗ | ? |

## Machines

Whether a crawler's name can be trusted, and what you can do about it.

**Identity**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Checks a crawler is who it claims to be <br><sub>Owner's published addresses, reverse DNS</sub> | ✓ [^59] | – | – | – | – | ? | ◐ [^60] | ✗ [^61] | – | ? |
| Files fake crawlers apart <br><sub>"Claims to be GPTBot"</sub> | ✓ [^62] | – | – | – | – | ? | ? | ✗ | – | ? |
| Splits AI traffic by why it came <br><sub>Training, answering a live question, a person clicking a citation</sub> | ✓ [^63] | ✗ | – | – | ✗ | ? | ? | ✗ [^64] | ✗ | ? |

**Policy**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Blocks or charges AI crawlers | ✓ [^65] | ✗ | – | – | ✗ | ✗ | ✓ [^66] | ✗ | ✗ | ✓ [^67] |
| robots.txt rules beside what each crawler fetched | ✓ [^68] | ✗ | – | – | ✗ | ✗ | ? | ✗ | ✗ | ◐ [^69] |

## Audience

Who the people were.

**Visitors**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Visitors and visits | ✓ [^70] | ✓ | – | – | ✓ | ✓ | ✓ | ✓ | ✓ | ◐ [^71] |
| Returning visitors | ◐ [^72] | ✓ [^73] | – | – | ? | ✓ [^74] | ? | ? | ? | ? |
| Countries | ✓ [^75] | ✓ | ✓ [^76] | ? | ✓ | ✓ [^77] | ✓ [^78] | ✓ [^79] | ✓ [^80] | ? |
| Browser, system and device | ✓ [^81] | ✓ | ◐ [^82] | ? | ✓ | ✓ [^83] | ✓ [^84] | ✓ [^85] | ✓ [^86] | ? |
| Each visit's pages in order <br><sub>Journeys</sub> | ✓ [^87] | ? | – | – | ◐ [^88] | ✓ [^89] | ✗ | ✗ | ✓ [^90] | ? |
| Engagement by source and device <br><sub>Pages per visit, one-page visits, visit length</sub> | ✓ [^269] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |

## Sources

Where people came from.

**Links and campaigns**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Referring sites | ✓ | ✓ | – | – | ✓ | ✓ | ✓ [^91] | ✓ [^92] | ✓ | ? |
| UTM campaigns | ✓ [^93] | ✓ | – | – | ✓ [^94] | ✓ [^95] | ? | ? | ✓ [^96] | ? |
| Campaign tag problems <br><sub>A source with no medium, an unknown medium, an ad click with no tags</sub> | ✓ [^270] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |

**AI and search**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| People who clicked through from an AI assistant <br><sub>Its own channel, by assistant</sub> | ✓ [^97] | ✓ [^98] | – | – | ✓ [^99] | ✓ [^100] | ◐ [^101] | ✗ [^102] | ✓ [^103] | ✓ [^104] |
| AI clicks that lost their referrer, estimated <br><sub>A direct visit to a page an assistant fetched minutes before; labelled "likely"</sub> | ◐ [^272] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |
| How often an assistant cites you, clicked or not | ◐ [^105] | ✗ | ◐ [^106] | ✓ [^107] | ✗ | ✗ | ✗ | ✗ | ✗ | ? |
| Search queries, impressions, position | planned [^108] | ◐ [^109] | ✓ [^110] | ✓ [^111] | ◐ [^112] | ◐ [^113] | ✗ | ✗ | ? | ✗ |
| Google AI Overview clicks told apart | ✗ [^114] | ✗ [^115] | ◐ [^116] | – | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

## Real time

How fresh the newest number is.

**Freshness**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Newest figures | Today so far, redrawn every 2 minutes [^117] | Realtime covers the last 30 minutes; full processing 24-48 hours [^118] | 2-3 days; a preliminary 24-hour view [^119] | ? | Current visitors (last 5 minutes); refreshes every 30 seconds [^120] | Real-time visitor log; the importer can stream [^121] | ? | Every second over WebSocket [^122] | Live view; online count covers 30 seconds [^123] | "In real time" (its words) [^124] |
| Every request of the last hours, one by one <br><sub>With why it was counted where it was</sub> | ✓ [^125] | ✗ | – | – | ✗ | ◐ [^126] | ✗ | ✗ [^127] | ? | ? |

## Content and site health

What was read, and what broke.

**Pages**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Top pages | ✓ | ✓ | ◐ [^128] | ◐ [^129] | ✓ | ✓ | ✓ [^130] | ✓ [^131] | ✓ | ? |
| AI fetches per page | ✓ [^132] | ✗ | – | – | ✗ | ◐ [^133] | ✓ [^134] | ◐ [^135] | ✗ | ? |
| Exit rate per page | ✓ [^271] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |

**Health**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 404s, and who met them <br><sub>People, probes, crawlers</sub> | ✓ [^136] | ? | ◐ [^137] | ◐ [^138] | ◐ [^139] | ◐ [^140] | ✗ [^141] | ✓ [^142] | ◐ [^143] | ? |
| Server errors (5xx) by page | ✓ | ✗ | ◐ [^144] | ? | ✗ | ◐ [^145] | ✗ [^146] | ✓ [^147] | ✗ | ? |
| Page speed | ✓ [^148] | ? | ◐ [^149] | ? | ? | ? | ✓ [^150] | ◐ [^151] | ? | ? |

## Trust in the number

Whether a figure can be wrong without anyone noticing.

**Checks**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Totals must add up, or the day is withheld | ✓ [^152] | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| A second, independent recount of every figure | ✓ [^153] | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Data-quality panel <br><sub>Unreadable lines, gaps, duplicates, log age</sub> | ✓ [^154] | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

**Limits**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Unsampled and unthresholded | ✓ [^155] | ◐ [^156] | ◐ [^157] | ◐ [^158] | ? | ? | ◐ [^159] | ✓ | ? | ? |

## Alerts and operations

Being told without having to look.

**Alerts**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Email alerts | ✓ [^160] | ✓ [^161] | ✓ [^162] | ✓ [^163] | ✓ [^164] | ✓ [^165] | ? | ✗ | ✓ [^166] | ? |
| Uptime check | ◐ [^167] | ✗ | ✗ | ✗ | ✗ | ✗ | ? | ✗ | ✗ | ✗ |
| Deploy and change markers on charts | ✓ [^168] | ✓ [^169] | ✓ [^170] | ? | ✓ [^171] | ✓ [^172] | ? | ✗ | ✓ [^173] | ? |

## Leads and conversions

Whether the visits turned into business.

**Goals**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Events inside the page <br><sub>Clicks, scrolls, sign-ups</sub> | ✓ [^174] | ✓ | – | – | ✓ [^175] | ✓ [^176] | ✗ | ✗ | ✓ | ✗ |
| Funnels | ✓ [^177] | ✓ [^178] | – | – | ◐ [^179] | ◐ [^180] | ✗ | ✗ | ✓ [^181] | ✗ |
| Leads by source and AI assistant | ✓ [^182] | ◐ [^183] | – | – | ◐ [^184] | ◐ [^185] | ✗ | ✗ | ◐ [^186] | ✗ |
| Ad cost and Google Ads link | ✗ | ✓ [^187] | – | – | ✗ | ? | ✗ | ✗ | ? | ✗ |

**Conversions**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Bookings, forms and payments pushed in by the tools <br><sub>Signed webhooks: Calendly, Cal.com, Stripe, Typeform, HubSpot, Zapier</sub> | ✓ [^258] | not checked | – | – | not checked | not checked | not checked | not checked | not checked | not checked |
| Forms and bookings started but not finished | ✓ [^259] | not checked | – | – | not checked | not checked | not checked | not checked | not checked | not checked |
| The anonymous pages a browser read before it converted | ✓ [^260] | not checked | – | – | not checked | not checked | not checked | not checked | not checked | not checked |
| Time from first visit to lead | ✓ [^261] | not checked | – | – | not checked | not checked | not checked | not checked | not checked | not checked |
| Webhooks out to a CRM, Zapier or Slack | ✓ [^262] | not checked | – | – | not checked | not checked | not checked | not checked | not checked | not checked |

## Privacy and ownership

Where the data lives, and for how long.

**Ownership**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Runs on your own server | ✓ | ✗ | ✗ | ✗ | ◐ [^188] | ✓ [^189] | ✗ | ✓ [^190] | ◐ [^191] | ✗ |
| Raw requests and addresses | ✓ [^192] | ◐ [^193] | ◐ [^194] | ? | ✗ [^195] | ◐ [^196] | ◐ [^197] | ✓ [^198] | ? | ◐ [^199] |
| Deleting one visitor on request | ✓ [^200] | ? | – | – | – | ✓ [^201] | – | ✗ | ? | ? |
| Named users and roles | ✓ [^202] | ✓ [^203] | ✓ [^204] | ? | ✓ [^205] | ✓ [^206] | ? | ✗ [^207] | ? | ◐ [^208] |
| Two-step sign-in | ✓ [^263] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |
| Audit log of who changed what | ✓ [^264] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |
| Conversions with or without name and email <br><sub>The site's choice</sub> | ✓ [^265] | not checked | – | – | not checked | not checked | not checked | not checked | not checked | not checked |

**Retention**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| How long data is kept | Raw addresses 14 days in the log; hashes 30 days; totals for good [^209] | Explorations 2 or 14 months (360: up to 50) [^210] | 16 months [^211] | 16 months [^212] | 3 years (5 on Business) [^213] | Cloud: raw 24 months, reports for good; self-host: yours [^214] | 6 months [^215] | Yours (--persist, --keep-last) [^216] | 1 year free, 7 years paid; self-host: yours [^217] | ? |
| Retention windows set in the dashboard <br><sub>A shorter window says first what it will remove</sub> | ✓ [^266] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |

## Exports and reports

Getting the data out.

**Out**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| CSV or JSON export | ✓ [^218] | ✓ | ✓ [^219] | ✓ [^220] | ✓ [^221] | ✓ [^222] | ◐ [^223] | ✓ [^224] | ✓ | ◐ [^225] |
| Scheduled email reports | ✓ [^226] | ? | ✗ | ? | ✓ [^227] | ✓ [^228] | ? | ✗ | ? | ? |
| API | ✓ [^229] | ✓ [^230] | ✓ [^231] | ? | ◐ [^232] | ✓ [^233] | ✓ [^234] | ◐ [^235] | ? | ◐ [^236] |
| AI agents can query it <br><sub>An MCP server for Claude, ChatGPT and other clients</sub> | ✓ [^267] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |

## Cost and licence

What it takes to run.

**Terms**

| Feature | Skald | Google Analytics 4 | Search Console | Bing Webmaster Tools | Plausible | Matomo | Cloudflare | GoAccess | PostHog | Known Agents |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Price | Free to self-host; runs on your server (Python 3.11+, standard library) [^237] | Free; 360 price on request [^238] | No price listed [^239] | Free [^240] | From $9 a month (10k pageviews); self-host free [^241] | Cloud from EUR 29 a month; self-host free [^242] | Web Analytics free; AI Crawl Control on all plans [^243] | Free [^244] | 1M events a month free, then per event [^245] | Free to 100k events; $29 and $299 a month [^246] |
| Licence | Source-available, Elastic License 2.0: free to use and self-host; hosting it for others needs a licence [^247] | Closed, SaaS | Closed, SaaS | Closed, SaaS | AGPLv3 (Community Edition) [^248] | GPL [^249] | Closed, SaaS | MIT [^250] | MIT (self-host) [^251] | Closed, SaaS |
| Several sites in one place | ✓ [^252] | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ [^253] | ◐ [^254] | ✓ | ✓ [^255] |
| Hosted service with sign-up and billing | Built, off; not offered yet [^268] | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked | not checked |

## Where Skald leads

- **It sees the machines.** AI training crawlers and the fetches an assistant makes while answering someone are in the log; a JavaScript tag never runs for them, and GA4 and Plausible drop known bots on purpose.
- **It says why an AI came.** To train, because someone just asked, or a person who clicked a citation; three tiers that never double count. It also estimates the AI clicks whose referrer was lost, shown apart and labelled "likely".
- **It checks names.** A crawler is compared with its owner's published addresses or DNS; a fake is filed apart as "claims to be".
- **Every figure is proven.** Groups add up to the log, a second count checks every figure, and a day that fails is withheld rather than shown.
- **Live, private, unblockable.** Today so far every 2 minutes, each request of the last 6 hours with its reason, nothing needed in the visitor's browser, and it runs on your own server.
- **Conversions checked like traffic.** Bookings, forms and payments arrive signed from the site and its tools, are kept without names or addresses by default, and every conversion figure is counted a second way; a day that does not agree is withheld.

## Where others lead

- **Search itself.** Queries, impressions and ranking come only from Search Console and Bing Webmaster Tools; Bing also counts Copilot citations, and Search Console AI Overview impressions. Skald plans an import, not a replacement.
- **What happens inside the page.** Click and scroll events, funnels with in-page steps, ad spend and the Google Ads link belong to GA4, PostHog, Matomo and Plausible. Skald's optional tag now sends clicks, form steps and bookings too, but it has no ad spend or Google Ads link.
- **Reach and control.** Script-based tools work on any host and count pages a CDN serves from cache; Cloudflare and Known Agents can block or charge AI crawlers; Skald blocks them (since 2026-10-08) but does not charge.

## Who should use what

Most sites need more than one of these. Pick by the question you need answered.

- **What people searched for, and where you rank.** Search Console and Bing Webmaster Tools. Only they hold the search engine's own data.
- **Clicks, scrolls, funnels and ad spend inside the page.** Google Analytics 4 and PostHog. A script in the page sees what a server log cannot.
- **Simple, cookie-free visitor counts on any host.** Plausible. One snippet, and it works where you cannot read the server's log.
- **Charging AI crawlers.** Cloudflare (pay per crawl). Skald blocks crawlers, per assistant or only their training crawlers, but cannot charge them.
- **Every visitor, crawler and AI fetch, with checked figures, on your own server.** Skald. It sits beside the tools above, and can also count the bookings, forms and payments your tools report.
- **A self-hosted suite that does a bit of everything.** Matomo. Tag or log import, GPL, free to self-host.
- **A one-off report straight from a log file.** GoAccess. Free, MIT, nothing to set up in the page.

## Also checked

Given no column, to keep the table readable.

- **Fathom.** JavaScript snippet, SaaS. Blocks bots including AI scrapers and does not report them; an AI tab for ChatGPT, Claude, Perplexity and Gemini referrals was added on 2026-10-02; no cookies; from $15 a month. Sources: [Fathom: features](https://usefathom.com/features), [Fathom: bot detection](https://usefathom.com/docs/features/bot-detection), [Fathom: changelog](https://usefathom.com/changelog), [Fathom: pricing](https://usefathom.com/pricing).
- **Umami.** JavaScript tracker, MIT licence, self-host or cloud. Excludes bots by default; an llm channel for ChatGPT, Claude, Copilot, Gemini, Meta AI and Perplexity referrals exists in its code; cloud free to 100k events. Sources: [Umami: GitHub](https://github.com/umami-software/umami), [Umami: environment variables](https://docs.umami.is/docs/environment-variables), [Umami: channel query (llm channel)](https://github.com/umami-software/umami/blob/master/src/queries/sql/getChannelExpandedMetrics.ts), [Umami: pricing](https://umami.is/pricing).
- **AWStats.** Server logs, GPL. Its robots list includes GPTBot, ClaudeBot, ChatGPT-User and PerplexityBot; batch runs from cron, not live. Version 8.0 is its author's final major release, and the author recommends moving to Matomo. Sources: [AWStats](https://www.awstats.org/), [AWStats: robots list](https://github.com/eldy/AWStats/blob/develop/wwwroot/cgi-bin/lib/robots.pm).
- **Profound Agent Analytics.** Reads server or CDN logs (AWS, Cloudflare, GCP, Vercel) rather than a JavaScript tracker; checks crawler addresses against published ranges; reports crawlers and human visits from AI. Price not published. Sources: [Profound: Agent Analytics](https://www.tryprofound.com/features/agent-analytics), [Profound: Agent Analytics integrations](https://www.tryprofound.com/blog/agent-analytics-integrations).

## Notes

[^1]: **Skald**: [Skald SOP](../SOP.md)
[^2]: **Google Analytics 4**: [GA4: consent mode](https://support.google.com/analytics/answer/9976101)
[^3]: **Search Console**: [Search Console: Performance report](https://support.google.com/webmasters/answer/7042828)
[^4]: **Bing Webmaster Tools**: [Bing Webmaster Tools: getting started (2025)](https://blogs.bing.com/webmaster/2025/6/Start-Using-Bing-Webmaster-Tools-to-Improve-Your-Site-Visibility/)
[^5]: **Plausible**: [Plausible: proxy and ad-blockers](https://plausible.io/docs/proxy/introduction)
[^6]: **Matomo**: [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^7]: **Cloudflare**: [Cloudflare Web Analytics: about](https://developers.cloudflare.com/web-analytics/about/); [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/)
[^8]: **GoAccess**: [GoAccess: features](https://goaccess.io/features)
[^9]: **PostHog**: [PostHog: web analytics](https://posthog.com/docs/web-analytics)
[^10]: **Known Agents**: [Known Agents](https://knownagents.com/)
[^11]: **Plausible, nothing runs in the visitor's browser**: Script, no cookies. [Plausible: data policy](https://plausible.io/data-policy)
[^12]: **Matomo, nothing runs in the visitor's browser**: Log import: yes; tag: no. [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^13]: **Cloudflare, nothing runs in the visitor's browser**: Crawl Control: yes; Web Analytics beacon: no. [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/); [Cloudflare Web Analytics: about](https://developers.cloudflare.com/web-analytics/about/)
[^14]: **Known Agents, nothing runs in the visitor's browser**: Server, CDN or WordPress integrations. [Known Agents](https://knownagents.com/)
[^15]: **Skald, works where you cannot read the server's log**: Beacon-only mode: a small script posts page views and events through a same-origin path to a Skald server you run. Bots and AI assistants run no script, so it sees people only; with a log, use the log. A log on another server can be shipped to Skald instead (row below). [Skald beacon-only mode](BEACON.md#beacon-only-mode-a-site-with-no-server-log)
[^16]: **Matomo, works where you cannot read the server's log**: With the JavaScript tag.
[^17]: **Cloudflare, works where you cannot read the server's log**: Beacon: anywhere; Crawl Control: traffic must pass through Cloudflare. [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/)
[^18]: **Known Agents, works where you cannot read the server's log**: Needs a supported CDN, platform or server code. [Known Agents](https://knownagents.com/)
[^19]: **Skald, counts pages a cdn served from its cache**: Reads the CDN's own log: Cloudflare Logpush, CloudFront standard logs, Fastly JSON. Cache hits included. [Skald CDN logs](CDN-LOGS.md)
[^20]: **Matomo, counts pages a cdn served from its cache**: Tag: yes; importer also reads CloudFront logs. [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^21]: **GoAccess, counts pages a cdn served from its cache**: If you feed it the CDN's logs (S3, CloudFront). [GoAccess: features](https://goaccess.io/features)
[^22]: **Known Agents, counts pages a cdn served from its cache**: CDN connectors. [Known Agents](https://knownagents.com/)
[^23]: **Google Analytics 4, visitors with an ad-blocker**: When blocked; Google publishes no rate.
[^24]: **Plausible, visitors with an ad-blocker**: 5-25% gap without its proxy, by its own estimate. [Plausible: proxy and ad-blockers](https://plausible.io/docs/proxy/introduction)
[^25]: **Matomo, visitors with an ad-blocker**: Log import: yes; tag: can be blocked. [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^26]: **Cloudflare, visitors with an ad-blocker**: Its FAQ says the beacon is blocked by ad-blockers. [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
[^27]: **PostHog, visitors with an ad-blocker**: Advises a reverse proxy against blockers. [PostHog: web analytics FAQ](https://posthog.com/docs/web-analytics/faq)
[^28]: **Known Agents, visitors with an ad-blocker**: Server-side.
[^29]: **Skald, visitors who decline cookies**: The log needs no cookie. The optional script tag keeps an ID only when the install turns visitor IDs on, and can wait for consent. [Skald integrations, the script tag](INTEGRATIONS.md)
[^30]: **Google Analytics 4, visitors who decline cookies**: Basic consent mode: nothing; advanced: cookieless pings plus modelling. [GA4: consent mode](https://support.google.com/analytics/answer/9976101)
[^31]: **Plausible, visitors who decline cookies**: No cookies. [Plausible: data policy](https://plausible.io/data-policy)
[^32]: **Matomo, visitors who decline cookies**: Cookieless option. [Matomo: tracking without cookies](https://matomo.org/faq/general/faq_157/)
[^33]: **Cloudflare, visitors who decline cookies**: No cookies or local storage. [Cloudflare Web Analytics](https://www.cloudflare.com/web-analytics/)
[^34]: **PostHog, visitors who decline cookies**: Cookieless mode option. [PostHog: cookieless tracking](https://posthog.com/tutorials/cookieless-tracking)
[^35]: **Google Analytics 4, ai training crawlers**: Known bots are excluded on purpose. [GA4: known bot traffic exclusion](https://support.google.com/analytics/answer/9888366)
[^36]: **Plausible, ai training crawlers**: Filtered out, not reported. [Plausible: tracking AI traffic](https://plausible.io/track-ai-traffic)
[^37]: **Matomo, ai training crawlers**: AI Chatbots report needs a Cloudflare, CloudFront or WordPress integration; or log import with --enable-bots. [Matomo: AI Chatbots report](https://matomo.org/faq/reports/ai-chatbots-overview-report/); [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^38]: **Cloudflare, ai training crawlers**: AI Crawl Control, all plans, if proxied. [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/)
[^39]: **GoAccess, ai training crawlers**: Own AI-crawler category. [GoAccess: README](https://github.com/allinurl/goaccess); [GoAccess: crawler list (browsers.c)](https://github.com/allinurl/goaccess/blob/master/src/browsers.c)
[^40]: **PostHog, ai training crawlers**: Known bots blocked by default; crawlers rarely run JS. [PostHog: web analytics FAQ](https://posthog.com/docs/web-analytics/faq)
[^41]: **Known Agents, ai training crawlers**: [Known Agents](https://knownagents.com/)
[^42]: **Skald, ai assistants fetching a page to answer someone, live**: Own tier: someone just asked. [Skald CLASSIFICATION](../CLASSIFICATION.md)
[^43]: **Plausible, ai assistants fetching a page to answer someone, live**: [Plausible: tracking AI traffic](https://plausible.io/track-ai-traffic)
[^44]: **Matomo, ai assistants fetching a page to answer someone, live**: Same integrations as above. [Matomo: AI Chatbots report](https://matomo.org/faq/reports/ai-chatbots-overview-report/)
[^45]: **Cloudflare, ai assistants fetching a page to answer someone, live**: By crawler name. [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/)
[^46]: **GoAccess, ai assistants fetching a page to answer someone, live**: By name (ChatGPT-User listed). [GoAccess: crawler list (browsers.c)](https://github.com/allinurl/goaccess/blob/master/src/browsers.c)
[^47]: **Known Agents, ai assistants fetching a page to answer someone, live**: [Known Agents](https://knownagents.com/)
[^48]: **Google Analytics 4, search engine crawlers**: [GA4: known bot traffic exclusion](https://support.google.com/analytics/answer/9888366)
[^49]: **Search Console, search engine crawlers**: Googlebot only, in Crawl Stats. [Search Console: Crawl Stats report](https://support.google.com/webmasters/answer/9679690)
[^50]: **Plausible, search engine crawlers**: [Plausible: what is excluded](https://plausible.io/docs/excluding)
[^51]: **Matomo, search engine crawlers**: Log import with --enable-bots. [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^52]: **Cloudflare, search engine crawlers**: Bot Analytics, Business and Enterprise plans. [Cloudflare Bot Analytics](https://developers.cloudflare.com/bots/bot-analytics/)
[^53]: **GoAccess, search engine crawlers**: [GoAccess: manual](https://goaccess.io/man)
[^54]: **Known Agents, search engine crawlers**: "Every crawler, scraper and AI agent". [Known Agents](https://knownagents.com/)
[^55]: **Skald, scanners and credential probes**: Counted and grouped as probes. [Skald CLASSIFICATION](../CLASSIFICATION.md)
[^56]: **Matomo, scanners and credential probes**: As bot hits, via log import. [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^57]: **Cloudflare, scanners and credential probes**: Bot Analytics (Business+). [Cloudflare Bot Analytics](https://developers.cloudflare.com/bots/bot-analytics/)
[^58]: **GoAccess, scanners and credential probes**: As requests and 404s, not grouped. [GoAccess: manual](https://goaccess.io/man)
[^59]: **Skald, checks a crawler is who it claims to be**: Google, Bing, Apple, OpenAI, Perplexity, Anthropic, DuckDuckGo, Meta; DNS for others. [Skald ROADMAP](ROADMAP.md)
[^60]: **Cloudflare, checks a crawler is who it claims to be**: Below Enterprise, AI crawlers are told apart by user agent. [AI Crawl Control: get started](https://developers.cloudflare.com/ai-crawl-control/get-started/)
[^61]: **GoAccess, checks a crawler is who it claims to be**: By user agent.
[^62]: **Skald, files fake crawlers apart**: Moved to bots and labelled. [Skald README](../README.md)
[^63]: **Skald, splits ai traffic by why it came**: Three tiers that never double count. [Skald CLASSIFICATION](../CLASSIFICATION.md)
[^64]: **GoAccess, splits ai traffic by why it came**: One AI category. [GoAccess: README](https://github.com/allinurl/goaccess)
[^65]: **Skald, blocks or charges ai crawlers**: Blocks, does not charge: per assistant, allow, block, or block only its training crawlers, applied by the web server (robots.txt always reachable). [Skald DEPLOY, AI crawler settings](../DEPLOY.md)
[^66]: **Cloudflare, blocks or charges ai crawlers**: Allow and block rules; pay per crawl. [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/)
[^67]: **Known Agents, blocks or charges ai crawlers**: Auto-updating robots.txt; WordPress rule enforcement on paid plans. [Known Agents](https://knownagents.com/); [Known Agents: pricing](https://knownagents.com/pricing)
[^68]: **Skald, robots.txt rules beside what each crawler fetched**: The site's own robots.txt, fetched hourly, beside each assistant's and search crawler's fetched paths; requests for disallowed paths counted per crawler and recounted by the audit. [Skald DATA-CONTRACT, robots.json](../DATA-CONTRACT.md)
[^69]: **Known Agents, robots.txt rules beside what each crawler fetched**: Writes robots.txt for you. [Known Agents](https://knownagents.com/)
[^70]: **Skald, visitors and visits**: Readers: visits that read a page; an upper bound. [Skald README](../README.md)
[^71]: **Known Agents, visitors and visits**: Visits from AI chats. [Known Agents](https://knownagents.com/)
[^72]: **Skald, returning visitors**: By a keyed hash, within 30 days by default (1 to 90 in Settings); also by the visit's source. [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^73]: **Google Analytics 4, returning visitors**: [GA4: dimensions and metrics](https://support.google.com/analytics/answer/9143382)
[^74]: **Matomo, returning visitors**: [Matomo: features](https://matomo.org/features/)
[^75]: **Skald, countries**: Unknown kept, never guessed. [Skald SOP](../SOP.md)
[^76]: **Search Console, countries**: Of searchers. [Search Console: Performance report](https://support.google.com/webmasters/answer/7042828)
[^77]: **Matomo, countries**: [Matomo: features](https://matomo.org/features/)
[^78]: **Cloudflare, countries**: [Cloudflare Web Analytics: dimensions](https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/)
[^79]: **GoAccess, countries**: [GoAccess: manual](https://goaccess.io/man)
[^80]: **PostHog, countries**: [PostHog: web analytics](https://posthog.com/docs/web-analytics)
[^81]: **Skald, browser, system and device**: In-app browsers by app.
[^82]: **Search Console, browser, system and device**: Device only. [Search Console: Performance report](https://support.google.com/webmasters/answer/7042828)
[^83]: **Matomo, browser, system and device**: [Matomo: features](https://matomo.org/features/)
[^84]: **Cloudflare, browser, system and device**: [Cloudflare Web Analytics: dimensions](https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/)
[^85]: **GoAccess, browser, system and device**: [GoAccess: manual](https://goaccess.io/man)
[^86]: **PostHog, browser, system and device**: [PostHog: web analytics](https://posthog.com/docs/web-analytics)
[^87]: **Skald, each visit's pages in order**: Anonymous, kept 7 days; funnels over them are counted each day and kept. [Skald README](../README.md)
[^88]: **Plausible, each visit's pages in order**: Not in the free Community Edition. [Plausible: Community Edition](https://plausible.io/docs/self-hosting)
[^89]: **Matomo, each visit's pages in order**: Visits log. [Matomo: features](https://matomo.org/features/)
[^90]: **PostHog, each visit's pages in order**: User paths. [PostHog: user paths](https://posthog.com/docs/product-analytics/paths)
[^91]: **Cloudflare, referring sites**: [Cloudflare Web Analytics: dimensions](https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/)
[^92]: **GoAccess, referring sites**: [GoAccess: manual](https://goaccess.io/man)
[^93]: **Skald, utm campaigns**: Five UTM tags; ad network from the click id, never its value; tag problems flagged (no medium, unknown medium, click id without tags, tags on internal links). [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^94]: **Plausible, utm campaigns**: [Plausible: dashboard guide](https://plausible.io/docs/your-plausible-experience)
[^95]: **Matomo, utm campaigns**: [Matomo: features](https://matomo.org/features/)
[^96]: **PostHog, utm campaigns**: [PostHog: channel types](https://posthog.com/docs/data/channel-type)
[^97]: **Skald, people who clicked through from an ai assistant**: Counted once per visitor; a floor, as referrers get stripped. [Skald CLASSIFICATION](../CLASSIFICATION.md)
[^98]: **Google Analytics 4, people who clicked through from an ai assistant**: AI Assistant channel; excludes Google's AI Overviews and AI Mode. [GA4: default channel group](https://support.google.com/analytics/answer/9756891)
[^99]: **Plausible, people who clicked through from an ai assistant**: AI Assistants channel since June 2026. [Plausible: changelog](https://plausible.io/changelog); [Plausible: tracking AI traffic](https://plausible.io/track-ai-traffic)
[^100]: **Matomo, people who clicked through from an ai assistant**: AI Assistant channel. [Matomo: AI assistants channel](https://matomo.org/faq/reports/what-are-ai-assistants-in-matomo/)
[^101]: **Cloudflare, people who clicked through from an ai assistant**: AI referrers in AI Crawl Control, paid plans only. [AI Crawl Control: analyze AI traffic](https://developers.cloudflare.com/ai-crawl-control/features/analyze-ai-traffic/)
[^102]: **GoAccess, people who clicked through from an ai assistant**: Plain referrer list.
[^103]: **PostHog, people who clicked through from an ai assistant**: AI channel type. [PostHog: channel types](https://posthog.com/docs/data/channel-type)
[^104]: **Known Agents, people who clicked through from an ai assistant**: [Known Agents](https://knownagents.com/)
[^105]: **Skald, how often an assistant cites you, clicked or not**: Sees each live fetch an assistant makes, not the answer it gives.
[^106]: **Search Console, how often an assistant cites you, clicked or not**: Impressions in AI Overviews and AI Mode. [Search Console: Generative AI performance report](https://support.google.com/webmasters/answer/16984139)
[^107]: **Bing Webmaster Tools, how often an assistant cites you, clicked or not**: Citations in Copilot and Bing AI; no clicks; queries sampled. [Bing: AI Performance report (Feb 2026)](https://blogs.bing.com/webmaster/February-2026/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview); [Bing: AI visibility insights (Jun 2026)](https://blogs.bing.com/search/June-2026/New-AI-Visibility-Insights-in-Bing-Webmaster-Tools-Intents-Topics-Citation-Share-Compare)
[^108]: **Skald, search queries, impressions, position**: Search Console import, ROADMAP P1-6. [Skald ROADMAP](ROADMAP.md)
[^109]: **Google Analytics 4, search queries, impressions, position**: Through a Search Console link; thresholds apply. [GA4: data thresholds](https://support.google.com/analytics/answer/9383630)
[^110]: **Search Console, search queries, impressions, position**: [Search Console: Performance report](https://support.google.com/webmasters/answer/7042828)
[^111]: **Bing Webmaster Tools, search queries, impressions, position**: [Bing Webmaster Tools: getting started (2025)](https://blogs.bing.com/webmaster/2025/6/Start-Using-Bing-Webmaster-Tools-to-Improve-Your-Site-Visibility/)
[^112]: **Plausible, search queries, impressions, position**: Search Console integration. [Plausible: dashboard guide](https://plausible.io/docs/your-plausible-experience)
[^113]: **Matomo, search queries, impressions, position**: Paid add-on. [Matomo: features](https://matomo.org/features/)
[^114]: **Skald, google ai overview clicks told apart**: They arrive looking like ordinary Google clicks. [Skald README](../README.md)
[^115]: **Google Analytics 4, google ai overview clicks told apart**: [GA4: default channel group](https://support.google.com/analytics/answer/9756891)
[^116]: **Search Console, google ai overview clicks told apart**: Reported apart, but also merged into Web results. [Search Console: Generative AI performance report](https://support.google.com/webmasters/answer/16984139); [Google Search: AI features and your site](https://developers.google.com/search/docs/appearance/ai-features)
[^117]: **Skald**: [Skald README](../README.md)
[^118]: **Google Analytics 4**: [GA4: Realtime report](https://support.google.com/analytics/answer/9271392); [GA4: data freshness](https://support.google.com/analytics/answer/11198161)
[^119]: **Search Console**: [Search Console: data delays and limits](https://support.google.com/webmasters/answer/96568); [Search Console: 24-hour view](https://support.google.com/webmasters/answer/7576553)
[^120]: **Plausible**: [Plausible: realtime dashboard](https://plausible.io/docs/realtime-dashboard)
[^121]: **Matomo**: [Matomo: features](https://matomo.org/features/); [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^122]: **GoAccess**: [GoAccess: features](https://goaccess.io/features)
[^123]: **PostHog**: [PostHog: web analytics FAQ](https://posthog.com/docs/web-analytics/faq)
[^124]: **Known Agents**: [Known Agents](https://knownagents.com/)
[^125]: **Skald, every request of the last hours, one by one**: 6 hours, up to 5,000 rows, the rule in words. [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^126]: **Matomo, every request of the last hours, one by one**: Per visit, not per request. [Matomo: features](https://matomo.org/features/)
[^127]: **GoAccess, every request of the last hours, one by one**: Panels, not rows. [GoAccess: manual](https://goaccess.io/man)
[^128]: **Search Console, top pages**: Pages in search. [Search Console: Performance report](https://support.google.com/webmasters/answer/7042828)
[^129]: **Bing Webmaster Tools, top pages**: Pages in search. [Bing Webmaster Tools: getting started (2025)](https://blogs.bing.com/webmaster/2025/6/Start-Using-Bing-Webmaster-Tools-to-Improve-Your-Site-Visibility/)
[^130]: **Cloudflare, top pages**: [Cloudflare Web Analytics: dimensions](https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/)
[^131]: **GoAccess, top pages**: [GoAccess: manual](https://goaccess.io/man)
[^132]: **Skald, ai fetches per page**: [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^133]: **Matomo, ai fetches per page**: With the AI Chatbots integrations. [Matomo: AI Chatbots report](https://matomo.org/faq/reports/ai-chatbots-overview-report/)
[^134]: **Cloudflare, ai fetches per page**: Top paths per crawler. [AI Crawl Control: analyze AI traffic](https://developers.cloudflare.com/ai-crawl-control/features/analyze-ai-traffic/)
[^135]: **GoAccess, ai fetches per page**: With --crawlers-only. [GoAccess: manual](https://goaccess.io/man)
[^136]: **Skald, 404s, and who met them**: People apart from probes; shows if a redirect now fixes it. [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^137]: **Search Console, 404s, and who met them**: Googlebot's 404s, past month. [Search Console: Page indexing report](https://support.google.com/webmasters/answer/7440203)
[^138]: **Bing Webmaster Tools, 404s, and who met them**: Site Scan. [Bing Webmaster Tools: getting started (2025)](https://blogs.bing.com/webmaster/2025/6/Start-Using-Bing-Webmaster-Tools-to-Improve-Your-Site-Visibility/)
[^139]: **Plausible, 404s, and who met them**: Needs an event on your 404 page. [Plausible: 404 tracking](https://plausible.io/docs/error-pages-tracking-404)
[^140]: **Matomo, 404s, and who met them**: Needs setup; importer has --enable-http-errors. [Matomo: features](https://matomo.org/features/); [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^141]: **Cloudflare, 404s, and who met them**: No status-code dimension. [Cloudflare Web Analytics: dimensions](https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/)
[^142]: **GoAccess, 404s, and who met them**: Not-found panel. [GoAccess: manual](https://goaccess.io/man)
[^143]: **PostHog, 404s, and who met them**: Site health scout. [PostHog: web analytics](https://posthog.com/docs/web-analytics)
[^144]: **Search Console, server errors (5xx) by page**: As Googlebot met them. [Search Console: Crawl Stats report](https://support.google.com/webmasters/answer/9679690)
[^145]: **Matomo, server errors (5xx) by page**: Log import. [Matomo log analytics importer](https://github.com/matomo-org/matomo-log-analytics)
[^146]: **Cloudflare, server errors (5xx) by page**: [Cloudflare Web Analytics: dimensions](https://developers.cloudflare.com/web-analytics/data-metrics/dimensions/)
[^147]: **GoAccess, server errors (5xx) by page**: Status codes panel. [GoAccess: manual](https://goaccess.io/man)
[^148]: **Skald, page speed**: Google PageSpeed Insights once a day for the top 5 landing pages, phone and desktop: lab score, LCP, CLS, and real-user LCP, CLS and INP when Google has them; plus server time per hour. [Skald DATA-CONTRACT, speed.json](../DATA-CONTRACT.md)
[^149]: **Search Console, page speed**: Googlebot response time. [Search Console: Crawl Stats report](https://support.google.com/webmasters/answer/9679690)
[^150]: **Cloudflare, page speed**: Measured in the browser. [Cloudflare Web Analytics: about](https://developers.cloudflare.com/web-analytics/about/)
[^151]: **GoAccess, page speed**: Time served, if logged. [GoAccess: manual](https://goaccess.io/man)
[^152]: **Skald, totals must add up, or the day is withheld**: Never guessed, never drawn as zero. [Skald README](../README.md)
[^153]: **Skald, a second, independent recount of every figure**: Own parser, own rules, every day. [Skald README](../README.md)
[^154]: **Skald, data-quality panel**: Unreadable lines, gaps, log age and duplicates per day; a repeated request id (nginx's own) is dropped and counted as a duplicate removed, a byte-identical line without one is counted and flagged. [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^155]: **Skald, unsampled and unthresholded**: Every line is counted.
[^156]: **Google Analytics 4, unsampled and unthresholded**: Sampling over 10M events in explorations; thresholds on demographic and query data; (other) rows. [GA4: data sampling](https://support.google.com/analytics/answer/13331292); [GA4: data thresholds](https://support.google.com/analytics/answer/9383630); [GA4: the (other) row](https://support.google.com/analytics/answer/13331684)
[^157]: **Search Console, unsampled and unthresholded**: 1,000-row tables; rare queries hidden. [Search Console: data delays and limits](https://support.google.com/webmasters/answer/96568)
[^158]: **Bing Webmaster Tools, unsampled and unthresholded**: AI grounding queries are a sample. [Bing: AI Performance report (Feb 2026)](https://blogs.bing.com/webmaster/February-2026/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview)
[^159]: **Cloudflare, unsampled and unthresholded**: Adaptive sampling; full detail for 7 days. [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
[^160]: **Skald, email alerts**: Site down, logging stopped, 5xx, 404 surge, crawler burst, new crawler, traffic drop; shown on the dashboard, mailed when the install turns alert mail on. A failed daily run sends one short mail. [Skald README](../README.md)
[^161]: **Google Analytics 4, email alerts**: Custom insights. [GA4: custom insights and alerts](https://support.google.com/analytics/answer/9443595)
[^162]: **Search Console, email alerts**: Site issues. [Search Console: about](https://search.google.com/search-console/about)
[^163]: **Bing Webmaster Tools, email alerts**: Alerts and recommendations. [Bing Webmaster Tools: getting started (2025)](https://blogs.bing.com/webmaster/2025/6/Start-Using-Bing-Webmaster-Tools-to-Improve-Your-Site-Visibility/)
[^164]: **Plausible, email alerts**: Traffic spikes and drops. [Plausible: traffic spike alerts](https://plausible.io/docs/traffic-spikes)
[^165]: **Matomo, email alerts**: Custom alerts. [Matomo: features](https://matomo.org/features/)
[^166]: **PostHog, email alerts**: On insights. [PostHog: alerts](https://posthog.com/docs/alerts)
[^167]: **Skald, uptime check**: Heartbeat from the same server; an outside check is planned. [Skald ROADMAP](ROADMAP.md)
[^168]: **Skald, deploy and change markers on charts**: Written automatically by every deploy and config change. [Skald README](../README.md)
[^169]: **Google Analytics 4, deploy and change markers on charts**: Annotations. [GA4: annotations](https://support.google.com/analytics/answer/15884203)
[^170]: **Search Console, deploy and change markers on charts**: Annotations. [Search Console: annotations](https://support.google.com/webmasters/answer/16530728)
[^171]: **Plausible, deploy and change markers on charts**: Annotations since July 2026. [Plausible: changelog](https://plausible.io/changelog)
[^172]: **Matomo, deploy and change markers on charts**: Annotations. [Matomo: features](https://matomo.org/features/)
[^173]: **PostHog, deploy and change markers on charts**: [PostHog: annotations](https://posthog.com/docs/data/annotations)
[^174]: **Skald, events inside the page**: Optional first-party beacon or a one-line script tag: button clicks, form steps, demo bookings, 75% scroll, copies, phone and mail clicks, links out and 404s, posted to your own server. Chosen events are shown as goals per 100 visits by source. Checked against the log's page views and audited against nginx's own count. [Skald event beacon](BEACON.md)
[^175]: **Plausible, events inside the page**: Goals and events. [Plausible: plans and features](https://plausible.io/)
[^176]: **Matomo, events inside the page**: [Matomo: features](https://matomo.org/features/)
[^177]: **Skald, funnels**: Funnels built from page rules (equals, starts with, any locale), optionally from one source, over each visit's pages in order; saved by name; each saved funnel counted every day by source and device, with drop-off, where people went after leaving a step, and time to go through; lead steps from the site's own CMS beside them. [Skald DATA-CONTRACT, funnels.json](../DATA-CONTRACT.md)
[^178]: **Google Analytics 4, funnels**: [GA4: data retention](https://support.google.com/analytics/answer/7667196)
[^179]: **Plausible, funnels**: Business plan. [Plausible: plans and features](https://plausible.io/)
[^180]: **Matomo, funnels**: Paid add-on. [Matomo: features](https://matomo.org/features/)
[^181]: **PostHog, funnels**: [PostHog: funnels](https://posthog.com/docs/product-analytics/funnels)
[^182]: **Skald, leads by source and ai assistant**: Leads, sign-ups and demos booked by first- and last-touch source and AI assistant over any range, crossed with the status the team set (lead quality), per site, from the site's CMS read-only; recounted by SQL. [Skald DATA-CONTRACT, leads.json](../DATA-CONTRACT.md)
[^183]: **Google Analytics 4, leads by source and ai assistant**: Key events by channel.
[^184]: **Plausible, leads by source and ai assistant**: Goals by source.
[^185]: **Matomo, leads by source and ai assistant**: Goals by channel.
[^186]: **PostHog, leads by source and ai assistant**: Events by channel.
[^187]: **Google Analytics 4, ad cost and google ads link**: [GA4: connect Google Ads](https://support.google.com/analytics/answer/9379420)
[^188]: **Plausible, runs on your own server**: Community Edition, with fewer features. [Plausible: Community Edition](https://plausible.io/docs/self-hosting)
[^189]: **Matomo, runs on your own server**: [Matomo: features](https://matomo.org/features/)
[^190]: **GoAccess, runs on your own server**: [GoAccess: README](https://github.com/allinurl/goaccess)
[^191]: **PostHog, runs on your own server**: Supported only on its cloud; self-host is unsupported. [PostHog: self-host](https://posthog.com/docs/self-host)
[^192]: **Skald, raw requests and addresses**: Your own log, plus a private 6-hour feed. Since 2.4.0, if the site keeps them, each visit with its address for 395 days, and one search for a person's visits, leads and conversions (admins only, audit-logged). [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^193]: **Google Analytics 4, raw requests and addresses**: Event-level BigQuery export, no IP; 1M events a day on the free tier. [GA4: BigQuery export schema](https://support.google.com/analytics/answer/7029846); [GA4: BigQuery export limits](https://support.google.com/analytics/answer/9358801)
[^194]: **Search Console, raw requests and addresses**: Bulk export without anonymised queries. [Search Console: bulk export to BigQuery](https://support.google.com/webmasters/answer/12918484)
[^195]: **Plausible, raw requests and addresses**: Never stores IPs. [Plausible: data policy](https://plausible.io/data-policy)
[^196]: **Matomo, raw requests and addresses**: Your database when self-hosted. [Matomo: features](https://matomo.org/features/)
[^197]: **Cloudflare, raw requests and addresses**: GraphQL API, sampled, no IP. [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
[^198]: **GoAccess, raw requests and addresses**: [GoAccess: manual](https://goaccess.io/man)
[^199]: **Known Agents, raw requests and addresses**: CSV on paid plans. [Known Agents: pricing](https://knownagents.com/pricing)
[^200]: **Skald, deleting one visitor on request**: skald forget --ip for an address (its kept visits too); skald forget --email, --vid or --lead for conversions, removed rows and journeys. [Skald README](../README.md); [Skald integrations](INTEGRATIONS.md)
[^201]: **Matomo, deleting one visitor on request**: GDPR tools. [Matomo: features](https://matomo.org/features/)
[^202]: **Skald, named users and roles**: Named logins with admin and viewer roles; with accounts switched on, organisations with owner, admin and viewer, invites and password resets by mail. Only admins change settings, and every change records who made it. [Skald accounts](ACCOUNTS.md)
[^203]: **Google Analytics 4, named users and roles**: [GA4: users and roles](https://support.google.com/analytics/answer/9305788)
[^204]: **Search Console, named users and roles**: [Search Console: owners, users and permissions](https://support.google.com/webmasters/answer/7687615)
[^205]: **Plausible, named users and roles**: [Plausible: team members and roles](https://plausible.io/docs/users-roles)
[^206]: **Matomo, named users and roles**: [Matomo: managing users](https://matomo.org/faq/general/manage-users/)
[^207]: **GoAccess, named users and roles**: A static report; you add the lock.
[^208]: **Known Agents, named users and roles**: Team members on paid plans. [Known Agents: pricing](https://knownagents.com/pricing)
[^209]: **Skald**: Defaults; the windows can be changed per site in Settings. [Skald README](../README.md); [Skald settings](SETTINGS.md)
[^210]: **Google Analytics 4**: [GA4: data retention](https://support.google.com/analytics/answer/7667196)
[^211]: **Search Console**: [Search Console data in Analytics (16 months)](https://support.google.com/analytics/answer/10737381)
[^212]: **Bing Webmaster Tools**: [Bing: 16 months of search data](https://blogs.bing.com/webmaster/October-2024/Bing-Webmaster-Tools-Extends-Search-Performance-Data-to-16-Months)
[^213]: **Plausible**: [Plausible: plans and features](https://plausible.io/)
[^214]: **Matomo**: [Matomo: pricing](https://matomo.org/pricing/)
[^215]: **Cloudflare**: [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
[^216]: **GoAccess**: [GoAccess: manual](https://goaccess.io/man)
[^217]: **PostHog**: [PostHog: event retention](https://posthog.com/docs/data/events-retention)
[^218]: **Skald, csv or json export**: Any table, filtered; verified days only. [Skald README](../README.md)
[^219]: **Search Console, csv or json export**: [Search Console API: getting all your data](https://developers.google.com/webmaster-tools/v1/how-tos/all-your-data)
[^220]: **Bing Webmaster Tools, csv or json export**: [Bing Webmaster Tools: getting started (2025)](https://blogs.bing.com/webmaster/2025/6/Start-Using-Bing-Webmaster-Tools-to-Improve-Your-Site-Visibility/)
[^221]: **Plausible, csv or json export**: [Plausible: changelog](https://plausible.io/changelog)
[^222]: **Matomo, csv or json export**: [Matomo: features](https://matomo.org/features/)
[^223]: **Cloudflare, csv or json export**: GraphQL API. [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
[^224]: **GoAccess, csv or json export**: [GoAccess: features](https://goaccess.io/features)
[^225]: **Known Agents, csv or json export**: Paid plans. [Known Agents: pricing](https://knownagents.com/pricing)
[^226]: **Skald, scheduled email reports**: Daily and weekly; refused if the figures do not add up. [Skald README](../README.md)
[^227]: **Plausible, scheduled email reports**: [Plausible: plans and features](https://plausible.io/)
[^228]: **Matomo, scheduled email reports**: [Matomo: features](https://matomo.org/features/)
[^229]: **Skald, api**: A read-only JSON API over every dashboard figure, with the dashboard login or a revocable token; with accounts, tokens belong to an organisation and carry scopes. [Skald API](API.md)
[^230]: **Google Analytics 4, api**: [GA4: Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)
[^231]: **Search Console, api**: [Search Console API: getting all your data](https://developers.google.com/webmaster-tools/v1/how-tos/all-your-data)
[^232]: **Plausible, api**: Business plan. [Plausible: plans and features](https://plausible.io/)
[^233]: **Matomo, api**: [Matomo: features](https://matomo.org/features/)
[^234]: **Cloudflare, api**: GraphQL. [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
[^235]: **GoAccess, api**: JSON output. [GoAccess: manual](https://goaccess.io/man)
[^236]: **Known Agents, api**: Enterprise plan. [Known Agents: pricing](https://knownagents.com/pricing)
[^237]: **Skald**: [Skald README](../README.md)
[^238]: **Google Analytics 4**: [Google Analytics 360](https://marketingplatform.google.com/about/analytics-360/)
[^239]: **Search Console**: [Search Console: about](https://search.google.com/search-console/about)
[^240]: **Bing Webmaster Tools**: [Bing Webmaster Tools: getting started (2025)](https://blogs.bing.com/webmaster/2025/6/Start-Using-Bing-Webmaster-Tools-to-Improve-Your-Site-Visibility/)
[^241]: **Plausible**: [Plausible: plans and features](https://plausible.io/)
[^242]: **Matomo**: [Matomo: pricing](https://matomo.org/pricing/)
[^243]: **Cloudflare**: [Cloudflare Web Analytics](https://www.cloudflare.com/web-analytics/); [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/)
[^244]: **GoAccess**: [GoAccess: README](https://github.com/allinurl/goaccess)
[^245]: **PostHog**: [PostHog: pricing](https://posthog.com/product-analytics/pricing)
[^246]: **Known Agents**: [Known Agents: pricing](https://knownagents.com/pricing)
[^247]: **Skald**: [Skald licence](../LICENSE)
[^248]: **Plausible**: [Plausible: Community Edition](https://plausible.io/docs/self-hosting)
[^249]: **Matomo**: [Matomo: features](https://matomo.org/features/)
[^250]: **GoAccess**: [GoAccess: README](https://github.com/allinurl/goaccess)
[^251]: **PostHog**: [PostHog: self-host](https://posthog.com/docs/self-host)
[^252]: **Skald, several sites in one place**: Several sites in one install, each with its own settings and pages, an index and a site switcher; slices by path within each. With accounts, each site belongs to one organisation, and admins add sites from the dashboard. [Skald README](../README.md)
[^253]: **Cloudflare, several sites in one place**: Soft limit of 10 sites. [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
[^254]: **GoAccess, several sites in one place**: Virtual hosts panel. [GoAccess: manual](https://goaccess.io/man)
[^255]: **Known Agents, several sites in one place**: Projects. [Known Agents: pricing](https://knownagents.com/pricing)
[^256]: **Skald, nothing runs in the visitor's browser**: The log needs nothing in the page. The beacon and the script tag are optional, added by the site. [Skald integrations, the script tag](INTEGRATIONS.md)
[^257]: **Skald, takes the log from another server**: skald-ship, one standard-library Python file, sends new lines over HTTPS with a token that can only add lines to one site; never a line lost or counted twice. Off by default; needs accounts. [Skald log intake](INGEST.md)
[^258]: **Skald, bookings, forms and payments pushed in by the tools**: Each tool's own signature checked on the raw body; a repeat changes nothing; kept once per tool, reference and stage; every figure counted a second time from the raw copies. [Skald integrations](INTEGRATIONS.md)
[^259]: **Skald, forms and bookings started but not finished**: A start with no finish by the same browser and action within 24 hours. Needs the visitor IDs, which are off by default. [Skald integrations](INTEGRATIONS.md)
[^260]: **Skald, the anonymous pages a browser read before it converted**: A random ID per browser, never a name or an address; page views kept 30 days unless the browser converted. Off by default. Never matched by address. [Skald event beacon, visitor IDs](BEACON.md)
[^261]: **Skald, time from first visit to lead**: Buckets from first touch to the lead, from the lead database or a hook; unknown and clock errors shown apart. [Skald DATA-CONTRACT, leads.json](../DATA-CONTRACT.md)
[^262]: **Skald, webhooks out to a crm, zapier or slack**: Signed, https only, never to a private address; retried five times over about 15 hours. Never a name or an email. [Skald integrations](INTEGRATIONS.md)
[^263]: **Skald, two-step sign-in**: A code from any authenticator app, with one-time recovery codes; an owner can require it. With accounts switched on. [Skald accounts](ACCOUNTS.md)
[^264]: **Skald, audit log of who changed what**: Sign-ins, invites, roles, tokens, settings; never a password, token or address; CSV export. With accounts switched on. [Skald accounts](ACCOUNTS.md); [Skald settings](SETTINGS.md)
[^265]: **Skald, conversions with or without name and email**: Addresses, user agents, phones and form answers are taken out before anything is kept. Since 2.4.0 a site keeps the lead's name and email by default (identity full), or none (identity anonymous); an install upgraded from before 2.4.0 keeps none until it is turned on. [Skald integrations](INTEGRATIONS.md)
[^266]: **Skald, retention windows set in the dashboard**: Detail days, journeys, the returning-visitor window, events and backups. A shorter window says what it will remove, needs the site's name typed, and removes nothing before the next daily run. Totals are kept for good. With accounts switched on. [Skald settings](SETTINGS.md)
[^267]: **Skald, ai agents can query it**: Fourteen read-only tools (find_person only with the read_private scope) over the same files the dashboard reads; visits called an upper bound on people, withheld days named. A token with the mcp scope, or stdio on the server. Off by default. [Skald MCP server](MCP.md)
[^268]: **Skald, hosted service with sign-up and billing**: Sign-up with a mailed link, plans and limits, Stripe billing. Built and tested, off by default; Skald is not sold as a service today. [Skald as a service](SAAS.md)
[^269]: **Skald, engagement by source and device**: Pages per visit, the share of one-page visits and the median visit length, for people's visits by source type and by device; counted a second time by its own audit. [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^270]: **Skald, campaign tag problems**: Visits whose landing address has a utm_source with no utm_medium, a medium analytics tools do not know, an ad click ID with no tags, or tags on a link inside the site; counted a second time by its own audit. [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^271]: **Skald, exit rate per page**: The share of a page's visits that left from it, over the last 30 whole days; not shown under 10 visits. [Skald DATA-CONTRACT](../DATA-CONTRACT.md)
[^272]: **Skald, ai clicks that lost their referrer, estimated**: A visit with no referrer and no campaign tag that lands on a page an assistant's user fetcher fetched in the same minute or up to 15 minutes before is "likely" from that assistant, by assistant, landing page, lead and conversion. An estimate, shown apart and never added to the citation count; counted a second time by its own audit. [Skald CLASSIFICATION](../CLASSIFICATION.md)
