# Edge cases

Every way a request, a log file or a clock can make a traffic number wrong,
and what the tool does about it. Each entry says:

- **Wrong:** what goes wrong if nothing handles it
- **Detect:** how the tool can tell it is happening
- **Count:** how it should be counted (which group, page view or not, visit or not)
- **Test:** the test that pins it
- **Status:** Handled / This release / Gap (with the ROADMAP.md item)

"**Seen**" means it is in the live log of a production site. The figures come from a
read-only scan on 2026-10-07 of `access.log.1` and `access.log`
(2026-10-06 22:08 UTC to 2026-10-07 16:50 UTC, 17,065 lines) and from the
deployed `report.py` run on today's file (15,827 requests). No address is
copied here: an address is described by its network ("a data-centre
address in Germany"), never written.

The general rule behind every entry: **when in doubt, a request is not a
person.** "Readers" must stay an upper bound that drifts down as we learn,
never up.

---

## The five most dangerous, from the real log

| # | Case | Why it is dangerous | Entry |
| --- | --- | --- | --- |
| 1 | One unlisted address in another country made 2,962 requests (17% of the two days; 19% of today) with 7 different browser identities, 2,131 of them in one hour, and is counted as **real people**. The same address sent "Claude-User (claude-code/...)" requests, counted as **"someone just asked an AI"**. | Almost certainly the site's own team, working from another country, and its own AI coding agents. It inflates readers, that country's share and the AI "asked" tier at the same time, and nothing flags it. | A5, A6 |
| 2 | `meta-externalagent`: 4,897 requests from 70 addresses in 34 minutes (peak 395 a minute), 31% of today's requests. No reverse DNS. | The name is self-reported and cannot be checked by DNS. A spoofer using this name is counted as an AI crawler. A burst this size would also trip any naive "traffic surge" alert as if people had come. | A3, F2 |
| 3 | Browser-shaped crawlers: the same Chrome identity from 49 addresses within 10 seconds; one data-centre address in Germany with 306 requests and not a single page-navigation payload; a bare `Mozilla/5.0` from Singapore. | Anything that sends a browser string and skips robots.txt lands in **people**. Only the robots/sitemap rule and the readers headline hold them back today. | A1, A15, A16, A11 |
| 4 | Old-site URLs: `/wp-content/uploads/2025/...` (the old WordPress site's own images) and old `/blog/...` posts. 321 distinct 404 paths; the top one is an old blog post with 22 hits. | `/wp-content` is a scanner pattern, so a real person following an old image link is counted as a **scanner**. Old blog 404s mixed with probe 404s hide the links worth redirecting. | C7, C8 |
| 5 | Launch-day format switch: 1,513 lines (277 of them today) in the old combined format with no host and no country; plus 58 byte-identical duplicate lines and no request id to tell a retry from a real repeat. `/sitemap.xsl` is counted as 4 **people page views**. | Data-quality faults that reconcile perfectly. `verify` proves the sums; it cannot prove the inputs. | H2, H4, B8 |

---

## A. Who made the request

### A1. Bots posing as browsers
- **Seen:** 345 requests filed as "browser-like crawler" today (46 browser-identity sessions fetched robots.txt or a sitemap); 236 bare `Mozilla/5.0`; HubSpot's crawler uses a Chrome string with "HubSpot Crawler" in it.
- **Wrong:** every scraper copies a Chrome string; with no other signal it is a person.
- **Detect:** robots/sitemap/ads.txt/security.txt fetch without rendering (exists, rule 8); no assets loaded per page read; no `_rsc` navigation; data-centre network (A15); many addresses one identity (A16); stale browser versions as a weak signal only; `Sec-Fetch-*` headers absent (needs log format, H12).
- **Count:** bots. Never move a visit out of bots on a single weak signal; combine.
- **Test:** fixture sessions for each signal alone (stays people) and combined (bots); the existing `test_a_scanner_sending_a_browser_user_agent_is_a_bot`.
- **Status:** partly Handled (rule 8, readers headline). Network and fan-out signals: Gap, ROADMAP P1-7.

### A2. Verified search crawlers (reverse DNS)
- **Seen:** Googlebot 605 requests from 28 addresses, GoogleOther 3,224, Google-InspectionTool 118, YandexBot 968 from 376 addresses. The top addresses reverse-resolve to `googlebot.com` and `yandex.com`, so these are genuine. No bingbot yet.
- **Wrong:** anyone can send "Googlebot". A spoofer is filed as a wanted search engine and its probes are excused.
- **Detect:** reverse DNS of the address must end in the vendor's domain (`googlebot.com`, `google.com`, `googleusercontent.com` for some Google fetchers, `search.msn.com`, `applebot.apple.com`, `yandex.ru/.com/.net`, `baidu.com/.jp`, `duckduckgo` uses a published list), then forward DNS of that name must return the same address. Google and Bing also publish JSON IP ranges; prefer those (no DNS at parse time).
- **Count:** verified -> search engine. Claimed but failed -> bots, labelled "claims to be Googlebot". Unknown (lookup failed) -> keep the claim, mark "not verified".
- **Test:** a spoofed Googlebot line from a non-Google address lands in bots; a lookup timeout does not change the group; cache hit test.
- **Status:** Gap, ROADMAP P0-2. Cache results per address per day; never block parsing on DNS.

### A3. Verified AI crawlers (published IP ranges)
- **Seen:** meta-externalagent 4,897 (no reverse DNS), ChatGPT-User 4 from addresses in Spain and the US (no reverse DNS), OAI-SearchBot 2, Claude-User 6 (ours, A6), Bytespider 62.
- **Wrong:** AI vendors mostly do not use reverse DNS. Without a range check the AI tab is a list of claims.
- **Detect:** OpenAI publishes `gptbot.json`, `searchbot.json`, `chatgpt-user.json`; Perplexity publishes `perplexitybot.json` and `perplexity-user.json`; Meta's crawlers come from its own network (AS32934); Apple publishes Applebot ranges; Anthropic and others: name only. Fetch the lists daily, keep the last good copy, store the list's date with each day.
- **Count:** in range -> answer engine, "verified". Out of range -> bots, "claims to be X". No published list -> answer engine, "not verifiable", shown as such.
- **Test:** fixture with one in-range and one out-of-range GPTBot; list fetch failure keeps yesterday's list and says so.
- **Status:** Gap, ROADMAP P0-2.

### A4. New and renamed AI agents
- **Seen:** `meta-webindexer` (53) and `NooksWebsiteResearchBot` (27) are filed under bots today; Meta's indexer may belong with the assistants. "Claude-User" now also carries the Claude Code product name.
- **Wrong:** an assistant launched last month is in nobody's list, so it falls into bots (if it says "bot") or people.
- **Detect:** a weekly "new names" list: user agents seen this week that were never seen before, with request counts; any agent containing `ai`, `gpt`, `llm`, `agent`, `assistant`, `-User`, `fetcher` that is not in a list.
- **Count:** until classified, bots. Once added, `backfill --force` recounts what the logs still hold.
- **Test:** an unknown "FooAI-User/1.0" lands in bots and appears in the "new names" list.
- **Status:** Gap, ROADMAP P0-3 (new-assistant alert). Keep the name lists in one data file with a date and a source link per entry, so updating it is a one-line change.

### A5. Our own team, unlisted
- **Seen:** one address in another country: 2,962 requests, 7 browser identities (Windows, Linux and Mac Chrome, Safari), 86% navigation payloads, 2,131 requests between 10:00 and 11:00 UTC, plus Claude Code fetches. Counted as people; that country is 19 of 143 readers today.
- **Wrong:** internal browsing looks exactly like a reader. Only one person's address was listed.
- **Detect:** an address with many identities and a large share of the day; office hours of a known team; an address that also sends our own tools' agents (Claude Code, Playwright, curl).
- **Count:** our own traffic, by label ("Remote office"), once listed. Never auto-listed: the tool suggests, a person confirms.
- **Test:** an address listed with a CIDR range moves all its identities to ours; a suggestion is shown but changes nothing until accepted.
- **Status:** This release (editable list, "add my address"). The "suggest likely internal addresses" step is a Gap, ROADMAP P0-1.

### A6. Our own AI coding agents
- **Seen:** `Claude-User (claude-code/2.1.292; +https://support.anthropic.com/)`, 6 requests from the address in A5, counted as "Someone just asked". Also `curl/8.7.1` (190) and `HeadlessChrome` (101) from the site owner's own computer - correctly ours, by address.
- **Wrong:** when the team asks an AI agent to look at the site, the AI tab reports a buyer asking an assistant about Acme.
- **Detect:** `claude-code/` in the agent; requests from a listed internal address; agent names of tools we run (Playwright, LibreCrawl, Lighthouse).
- **Count:** ours, label "AI coding agent". Claude-User without `claude-code` stays "asked".
- **Test:** the exact string above lands in ours; plain `Claude-User/1.0` stays answer engine, asked.
- **Status:** Gap, ROADMAP P0-1 (one-line pattern plus test).

### A7. Link-preview unfurlers
- **Seen:** facebookexternalhit 15, SkypeUriPreview 3.
- **Wrong:** pasting a link in Slack, Teams, iMessage, WhatsApp, LinkedIn, X or Discord fetches the page once per chat, sometimes once per recipient. iMessage sends a plain Safari-like agent with `facebookexternalhit` and Twitterbot tokens added; Teams uses `SkypeUriPreview`; some unfurlers send no distinctive token at all.
- **Detect:** known tokens (Slackbot-LinkExpanding, Slack-ImgProxy, TelegramBot, WhatsApp, Discordbot, LinkedInBot, Twitterbot, SkypeUriPreview, Iframely, Embedly, redditbot, Pinterestbot, Snap URL Preview); a single fetch of the page plus its `og:image` with no assets; from the unfurler's network.
- **Count:** bots ("link previews"), shown as their own line: a preview means a person shared the link, which marketing wants to know.
- **Test:** each token above lands in bots under "link previews"; an iMessage preview string is not a reader.
- **Status:** partly Handled (most tokens are in the bot list; facebookexternalhit, Twitterbot and LinkedInBot sit in search engines). A separate "shared in chat" line is a Gap, ROADMAP P2-9.

### A8. Uptime monitors and our heartbeat
- **Seen:** `skald-heartbeat` 176 lines (every 5 minutes), ours.
- **Wrong:** a monitor every minute is 1,440 "visits" a day. Our heartbeat runs on the server itself, so when the server is down the heartbeat is down too and reports nothing.
- **Detect:** monitor tokens (UptimeRobot, Pingdom, StatusCake, Better Uptime, Site24x7, Checkly, Datadog Synthetics); a fixed interval from one address.
- **Count:** ours (our monitor) or bots (anyone else's).
- **Test:** existing; plus "a gap in heartbeat lines longer than 15 minutes is reported as downtime or lost logging, not as a quiet period".
- **Status:** Handled for counting. Outside uptime check: Gap, ROADMAP P0-3.

### A9. Headless browsers, Lighthouse, PageSpeed, screenshot services
- **Wrong:** PageSpeed Insights, Lighthouse, Search Console's live test and screenshot services render the page fully (assets and payloads), so the render rule calls them people.
- **Detect:** `HeadlessChrome`, `Chrome-Lighthouse`, `Google-PageRenderer`, `Google-InspectionTool`, `PTST` (WebPageTest), `GTmetrix`.
- **Count:** bots, or ours when we started them (from a listed address).
- **Test:** `Chrome-Lighthouse` with full asset loads is not a reader.
- **Status:** HeadlessChrome Handled; Lighthouse/PTST/GTmetrix tokens Gap (one-line, ROADMAP P0-1).

### A10. Google-InspectionTool and GoogleOther
- **Seen:** InspectionTool 118 today (Search Console URL inspection, Rich Results Test - started by us); GoogleOther 3,224 (Google's general-purpose crawler, used for research and product work, possibly AI).
- **Wrong:** both are counted as search "indexing". InspectionTool is our own action; GoogleOther is not search indexing.
- **Count:** keep both in search engines (they are Google's and wanted), but show them on their own lines like the ads checks, and leave them out of the indexing figure.
- **Test:** indexing figure excludes both; group total unchanged.
- **Status:** Gap, ROADMAP P1-8.

### A11. Bare or truncated agents
- **Seen:** `Mozilla/5.0` alone, 236 requests from 2 addresses (mostly Singapore): `.env` probes, 112 404s, 116 redirects.
- **Wrong:** "Mozilla/" matches the browser pattern, so the requests not on a probe path are people.
- **Detect:** an agent with no platform and no engine (`Mozilla/5.0` with nothing after it, or shorter than ~30 characters).
- **Count:** bots.
- **Test:** `Mozilla/5.0` asking for `/` is bots; a full Safari string is not.
- **Status:** Gap, ROADMAP P0-1.

### A12. Empty agent, garbage agent
- **Seen:** 6 empty agents.
- **Count:** bots (Handled).

### A13. SEO suites, marketplaces, sales tools
- **Seen:** HubSpot Crawler 242, SemrushBot 9, G2MarketplaceBot 2 (HEAD), NooksWebsiteResearchBot 27 (a sales-prospecting tool: somebody is researching Acme).
- **Count:** bots, by name. A sales-research bot is a weak buying signal worth a line in the bots tab.
- **Status:** Handled.

### A14. Search-engine ads checks
- **Seen:** AdsBot 54 (18 of them 304s), Google-Adwords-Instant.
- **Status:** Handled (own line, out of indexing).

### A15. Data-centre addresses posing as browsers
- **Seen:** one Hetzner address in Germany, 306 requests, one Chrome identity, zero navigation payloads.
- **Wrong:** a real person rarely browses from a hosting provider; a scraper almost always does.
- **Detect:** the address's network (ASN) is a hosting provider (Hetzner, OVH, DigitalOcean, AWS, GCP, Azure, Linode, Contabo, Hostinger...). DB-IP Lite has a free ASN database next to the country one.
- **Count:** bots, unless the visit renders (loads assets per page) - VPN users exit from data centres too. Show "data-centre browser" as its own line.
- **Test:** hosting-network visit with no assets -> bots; hosting-network visit that renders -> people, flagged.
- **Status:** Gap, ROADMAP P1-7.

### A16. Distributed crawlers
- **Seen:** the same Chrome identity from 49 addresses within 10 seconds (also 46, 43, 42 for other identities).
- **Wrong:** each address is its own short visit, often with one page read, so they pass as readers.
- **Detect:** N addresses, one identical agent, within S seconds, each with one page and no assets. Deliberately not built yet (CLASSIFICATION.md "burst rule") because a link shared in a busy chat looks similar.
- **Count:** flag first ("possible crawler burst"), show the count; only reclassify once a real fixture shows the rule never catches a shared link.
- **Test:** fixture of a real burst and of a real chat share; the rule must separate them.
- **Status:** Gap, ROADMAP P1-7.

---

## B. Requests that are not a page read

### B1. Next.js navigation payloads (`?_rsc=`)
- **Seen:** 10,386 of 17,065 requests (61%).
- **Count:** never a page view; evidence of a visit, and of an in-site move for journeys.
- **Status:** Handled (`RSC_PAYLOAD`).

### B2. Prefetch and prerender
- **Seen:** Chrome Privacy Preserving Prefetch Proxy asked for `/.well-known/traffic-advice` 3 times (404).
- **Wrong:** Next.js `<Link>` prefetches pages in view (as `_rsc` payloads); Chrome speculation rules can prerender whole HTML pages the person never opens; the Chrome prefetch proxy fetches from Google's network. A prerendered HTML document is logged as a 200 GET for a page.
- **Detect:** the `Sec-Purpose: prefetch` / `Purpose: prefetch` and `Next-Router-Prefetch` request headers. They are not in the log format today (H12).
- **Count:** not a page view; the visit only counts if a real navigation follows.
- **Test:** a line with `purpose=prefetch` is not a page view; the prefetch proxy agent is a bot.
- **Status:** Gap, ROADMAP P0-5 (log format) then a one-line rule. Also serve `/.well-known/traffic-advice` (or a 404 is fine; it just means no proxy prefetch).

### B3. Client-side navigation is invisible
- **Wrong:** after the first page, moving inside a Next.js site may fetch nothing (cached payload). Page views undercount; journeys miss steps.
- **Count:** "in-app" steps from the same-site referrer, never as page views (visits.py does this).
- **Status:** This release. A floor, and the dashboard must say so.

### B4. HEAD
- **Seen:** 39, mostly HubSpot (24), Semrush, curl, G2.
- **Count:** a HEAD can be a page view by the current rule. A person's browser never sends HEAD for a page. HEAD should never be a reader's page view.
- **Test:** HEAD from a browser agent is not a page view.
- **Status:** Gap, ROADMAP P0-1 (one-line change to `is_page`; CLASSIFICATION.md needs the same edit).

### B5. 304 Not Modified
- **Seen:** 64 (40 from the site owner's own computer, 18 AdsBot).
- **Count:** a 304 on an HTML page is a real re-read from cache. Today it is not a page view (2xx only). Decide: count a 304 for an HTML page from a browser that renders as a page view; never for assets.
- **Status:** Gap (decision), ROADMAP P1-8.

### B6. 206 Partial Content
- **Seen:** none (no video or PDF yet).
- **Count:** one download, however many ranges. Count the first range of a file only.
- **Status:** Gap, matters once PDFs or video are hosted.

### B7. 499 client closed, 429 rate limited, 400 bad request
- **Seen:** 499 7, 429 4 (our own rate-limit test), 400 13.
- **Count:** not page views; 499s on pages are a speed signal; 429s should show in Health.
- **Status:** Handled as non-pages; 429 in Health is This release (status per group).

### B8. Files that are not pages but are not in the asset list
- **Seen:** `/sitemap.xsl` counted as 4 people page views today.
- **Wrong:** `.xsl`, `.pdf`, `.csv`, `.rss`, `.atom`, `.zip`, `.mp4` and others are not in `ASSET`, so a 200 for them is a "page".
- **Count:** `.xsl` is an asset. PDFs are documents: count them separately as "downloads", not pages.
- **Test:** `/sitemap.xsl` 200 is not a page view; `/guide.pdf` is a download.
- **Status:** Gap, ROADMAP P0-1.

### B9. Next.js image optimiser
- **Seen:** `/_next/image?url=...&amp;w=...` (HTML-escaped), 7 of them answered 400 on the apex host.
- **Count:** asset (Handled by the `/_next/` prefix).

### B10. Form posts and server actions
- **Seen:** POST to `/` 2 (Next.js server actions post to the page path), `/rate-limit-test/` (ours), `/xmlrpc.php` (probe).
- **Count:** a POST is never a page view; a POST to a page path from a reader is the "form sent" step of a funnel. The log cannot say which form or whether it succeeded - the CMS can.
- **Status:** counted (Handled). Funnel use: ROADMAP P1-1.

### B11. Tag manager and analytics side requests
- **Seen:** `gtm_latency` query 3.
- **Count:** beacon/asset, never a page.

---

## C. URLs

### C1. Apex -> www redirect (double counting)
- **Seen:** `example.com` 799 requests: 744 redirects (301), 35 404s, 11 400s, 2 200s.
- **Wrong:** a visitor who types `example.com` makes two requests on two hosts. If both are counted as pages, one read is two.
- **Count:** the redirect is not a page (2xx rule, Handled). The visit key is address + agent, not host, so both requests are one visit (Handled).
- **Test:** existing redirect tests; plus "apex 301 then www 200 = 1 visit, 1 page view".

### C2. Trailing slash
- **Seen:** 433 trailing-slash redirects (301/308).
- **Count:** `/pricing` and `/pricing/` are one page. Normalise paths for top-page lists (strip the trailing slash except on `/`).
- **Status:** redirects Handled; path normalisation for lists: Gap, ROADMAP P0-1.

### C3. Upper case and encoding
- **Seen:** no upper-case page paths; upper-case only in certificate challenges and old WordPress uploads.
- **Count:** keep case (Next.js paths are case-sensitive; `/Pricing` is a 404), but decode `%2F`-style escapes before matching probes.
- **Test:** `/%2e%65nv` is a probe.
- **Status:** Gap (decoding), ROADMAP P0-1.

### C4. Locale paths
- **Seen:** `/ca/` 5,626 requests, `/ca/fr/` 2,584.
- **Count:** by view (Handled: US English, Canada English, Canada French). A visitor reading in two views is a visit in each; requests add up across views, visits do not (documented).
- **Wrong to watch for:** `/ca` without the slash; a future `/fr/` or `/es/`; language switch mid-visit.

### C5. Query-string noise
- **Seen:** `_rsc`, `amp;w`/`amp;q` (escaped `&`), `gtm_latency`, `ref=producthunt` 7, `ref=peerpush` 2, `step=` 30 (a WordPress installer probe), `utm_source=chatgpt.com` 2.
- **Wrong:** top-page lists split one page into many by query; personal data can arrive in a query (an email in `?email=`).
- **Count:** page identity is the path only. Keep only a known list of attribution keys (utm_*, gclid, msclkid, fbclid, li_fat_id, ttclid, ref, via, source) as campaign labels; drop every other value; treat `amp;` keys as their unescaped name.
- **Test:** `/pricing?x=1` and `/pricing` are one page; `ref=producthunt` becomes a campaign label; `?email=a@b.c` is never stored.
- **Status:** path-only Handled; `ref=` capture and `amp;` handling are This release (full UTM capture) - confirm `ref`.

### C6. Very long or odd URLs
- **Count:** cap stored paths (e.g. 200 characters); fold anything past the top list into "(all others)" (Handled).

### C7. Old WordPress URLs vs scanners
- **Seen:** `/wp-content/uploads/2025/09/cropped-Welc...` and `/wp-content/uploads/2025/11/Banner-image...` (the old site's own images, still linked from somewhere) next to `/wp-admin/install.php?step=...` (30, a real probe).
- **Wrong:** `/wp-content` is a probe pattern, so a person following an old image link is filed as a scanner.
- **Detect:** a per-site "legacy paths" list (this site was WordPress until 2026-10-06) that wins over the probe rule for `/wp-content/uploads/` only; `wp-admin`, `wp-login`, `xmlrpc` stay probes.
- **Count:** legacy 404 (people or bots by the usual rules), shown in Broken links as "old site URL".
- **Test:** `/wp-content/uploads/2025/09/x.png` with a browser agent and a Google Images referrer is not a probe when the site lists `/wp-content/uploads/` as legacy.
- **Status:** Gap, ROADMAP P0-1 (config key), ties in with the website's legacy-URL redirects work.

### C8. Old blog and feature URLs (404)
- **Seen:** 426 404s, 321 distinct paths; top `/blog/best-virtual-receptionist-for-law-firms/` 22, many `/blog/...`, `/features/...`, `/industries/...` of the old site.
- **Count:** in Broken links, grouped: old-site URL / probe / typo / stale build file (I2). A path that starts returning 200 or 301 gets the "fixed" badge.
- **Status:** This release (Broken links, fixed badges, probe grouping).

### C9. Another service's short links on the same host
- **Seen:** `/v/...` 8 requests (passed on to a short-link service on the same host).
- **Wrong:** short links you send out are another service's traffic. As that service grows they could outnumber website readers.
- **Count:** excluded like another host: a `site.exclude_prefix` (or a view) for `/v/`, reported as "excluded", never silently dropped.
- **Test:** `/v/abc` on the site lands in excluded, and the sums still hold.
- **Status:** Gap, ROADMAP P0-1.

### C10. The server's own address as the host or referrer
- **Seen:** 7 requests with the bare address as Host; 4 with it as referrer; 2 readers today list it as their referring site.
- **Count:** a request to an address is never a person (excluded host, Handled). A reader whose referrer is our own address is a scanner or our own test: source "this site", never "other website".
- **Status:** host Handled; referrer label Gap, ROADMAP P0-1.

### C11. The dashboard's own URLs
- **Seen:** `/traffic` 301 and a 404 in the main log.
- **Count:** ours. The dashboard location logs to its own file (Handled); add `/traffic` without the slash.

### C12. Garbage request lines
- **Seen:** a TLS handshake sent to the plain-HTTP port; 4 empty request lines; `/shell?cd+/tmp;rm+-rf+*;wget...` (a command-injection probe on the apex, answered 400).
- **Count:** a request (Handled), bots. Add `;rm`, `wget+http`, `cd+/tmp` shapes to `PROBE_QUERY`.
- **Status:** request counting Handled; the new probe shapes Gap, ROADMAP P0-1.

---

## D. Addresses

### D1. Shared addresses (offices, carrier NAT, universities)
- **Seen:** 73 addresses with 5 or more agents; one with 11 (Google's).
- **Wrong:** many people behind one address with one common agent become one visit; one person with two browsers becomes two.
- **Count:** accept: visits are approximate (documented). Never use the address alone as a person.
- **Test:** existing session tests.

### D2. iCloud Private Relay, VPNs, Tor
- **Wrong:** the address changes per site or per connection and the country is the exit's. Private Relay keeps the region roughly right; VPNs often do not; Tor exits are shared by thousands.
- **Detect:** Apple publishes Private Relay egress ranges; Tor publishes exit lists; VPNs show as data-centre networks (A15).
- **Count:** people if they render; label the country as "via relay/VPN" where known.
- **Status:** Gap, ROADMAP P2-3.

### D3. IPv6 privacy addresses
- **Seen:** no IPv6 at all (the site is not reached over IPv6 today).
- **Wrong:** if IPv6 is enabled, a phone's temporary address changes every few hours, splitting one person into several visits and breaking the 30-day returning hash.
- **Count:** key IPv6 visitors by their /64 network, not the full address.
- **Test:** two addresses in one /64 with one agent within 30 minutes are one visit.
- **Status:** Gap, ROADMAP P1-8. Check before adding an AAAA record.

### D4. Mobile network switching
- **Wrong:** wifi to mobile data mid-visit is two visits.
- **Count:** accept and document.

### D5. Country accuracy
- **Seen:** no `XX` countries in the new format; the 1,513 old-format lines have none.
- **Wrong:** DB-IP Lite is country-level and sometimes wrong; the database refreshes monthly, so one address can change country mid-period.
- **Count:** country of the visit at its first page (Handled). "Unknown" stays a row.

### D6. A CDN or proxy put in front later
- **Wrong:** behind Cloudflare or a load balancer, every `$remote_addr` becomes the proxy's: one "visitor", one country, and every address rule breaks silently.
- **Detect:** a sudden collapse in distinct addresses; most traffic from one network.
- **Count:** configure nginx `real_ip` from the trusted proxy only; the data-quality check alerts when distinct addresses per 1,000 requests falls below a floor.
- **Status:** Gap, ROADMAP P0-5.

---

## E. Referrers and attribution

### E1. Referrer stripped by apps and email
- **Seen:** no email-client or `android-app://` referrers yet; 84% of today's readers are "direct or unknown".
- **Wrong:** in-app browsers (LinkedIn, Facebook, Instagram, Gmail), desktop and mobile mail clients, Slack and Teams desktop, and the ChatGPT and Claude desktop/mobile apps often send no referrer. These people land in "direct".
- **Detect:** the in-app browser marker in the agent (Handled for the major apps); `utm_*` on links we control.
- **Count:** source = the in-app browser's app when known ("LinkedIn app"), else direct. "Direct" must be labelled "direct or unknown" (Handled).
- **Status:** Handled where possible; tagging all our own outbound links is a marketing practice, not code.

### E2. `utm_source=chatgpt.com` with or without a referrer
- **Seen:** 2, both with a referrer.
- **Count:** citation, once per visit, whichever signal found it (Handled; one name per assistant).
- **Test:** existing.

### E3. Referrer reduced to the origin
- **Wrong:** browsers send only `https://chatgpt.com/` (no path) across sites by default. The citing conversation is never known.
- **Count:** host only (Handled). Never promise "which answer cited us".

### E4. Google AI Overviews and AI Mode
- **Wrong:** clicks arrive as `google.com`, identical to search clicks.
- **Count:** search. Show "not measurable" (Handled).

### E5. Two referrers in one header
- **Seen:** `https://google.com, https://example.com/features/...` (2).
- **Count:** take the first URL before the comma.
- **Test:** that string's host is `google.com`.
- **Status:** Gap, ROADMAP P0-1.

### E6. UTM spelling variants
- **Wrong:** `ChatGPT.com`, `chatgpt`, `chat.openai.com`; `LinkedIn`, `linkedin.com`, `li`; `cpc` vs `CPC` split into different rows.
- **Count:** lower-case and alias to one name (Handled for assistants; Gap for others, ROADMAP P1-8).

### E7. First touch in the CMS vs first page in the logs
- **Wrong:** the CMS keeps the first visit ever on that browser (localStorage, no expiry); the logs label a reader at the first page of that day's visit. They will disagree for returning visitors, cleared storage, private windows, a second device.
- **Count:** show both, named differently: "first touch (lead's browser)" vs "source of the visit". Never sum them.
- **Status:** design rule for ROADMAP P0-6.

### E8. Our own UTM tags on internal links
- **Wrong:** a `utm_` tag on a link from one page of the site to another starts a new source mid-visit (the CMS starts a new session on any sourced arrival).
- **Count:** never tag internal links; the Broken links/health tab can list internal links carrying `utm_`.

### E9. Click ids and personal data
- **Wrong:** `gclid`, `fbclid` are long, unique per click, and with a timestamp can be tied back to an ad account; a query can carry an email.
- **Count:** store "has gclid" (Google Ads) and the campaign tags, never the id value (This release: confirm the ids are labels, not values).

---

## F. Volume anomalies

### F1. Spikes and attacks
- **Seen:** busiest minute 532 requests (10:54 UTC), mostly the Meta crawl.
- **Wrong:** a spike looks like success on a chart; a share-of-traffic figure for people collapses.
- **Detect:** requests per minute per group against the trailing 14-day median for that hour; split by group so a crawler spike is not a people spike.
- **Count:** as classified; annotate the spike.
- **Status:** Gap, ROADMAP P0-3.

### F2. Crawl bursts
- **Seen:** meta-externalagent 4,897 in 34 minutes, 70 addresses, 125 404s and 499 redirects among them.
- **Count:** answer engine, training (once verified, A3). Alert when one agent exceeds N requests in 10 minutes; show its 404s (a crawler hitting dead links is an SEO problem).
- **Status:** Gap, ROADMAP P0-3.

### F3. 404 scanners
- **Seen:** `.env` family from a bare agent, `/wp-admin/install.php` 30, `/xmlrpc.php`, `/admin`, `/api/users`.
- **Count:** bots, probe=True (Handled). Group them in Broken links so they do not drown real broken links (This release).

### F4. Rate limiting
- **Seen:** 429 x4 from our own test.
- **Count:** in Health by path; a 429 to a real reader is a bug to report.

### F5. One visitor, thousands of requests
- **Seen:** the address in A5 (2,962).
- **Count:** visits are by address + agent + gap, so it is a handful of visits. Requests share charts must not be read as people.

### F6. Low numbers
- **Wrong:** at 100-150 readers a day, a 30% change is noise; one person can be a "country".
- **Count:** show change arrows only when both periods are complete and the change is beyond a simple noise band; hide percentages under ~20 in the base.
- **Status:** This release for Insights (see K1); free period comparison ROADMAP P1-2.

---

## G. Time

### G1. Daylight-saving changes
- **When:** 2026-11-01 (New York day is 25 hours), 2027-03-14 (23 hours).
- **Wrong:** a 25-hour day looks 4% busier; the 01:00 hour happens twice; an hourly chart with 24 slots drops or merges an hour; day x hour heatmap misaligns.
- **Count:** days are local midnight to midnight (Handled). Hour labels: 01:00 appears twice on 1 Nov - label the second "01:00 (EST)"; 02:00 is missing on 14 Mar - show an empty slot, not zero.
- **Test:** fixture spanning each change: day length, hour slots, comparison with the week before flagged "25-hour day".
- **Status:** day windows Handled; hourly/heatmap labels Gap, check in this release.

### G2. New York days vs UTC rotation
- **Wrong:** logrotate runs at 00:00 UTC (20:00 or 19:00 New York), so every New York day spans two files.
- **Count:** by timestamp, not by file (Handled).

### G3. Clock skew
- **Seen:** the server clock is synchronised (NTP active); no timestamp went backwards in today's file.
- **Wrong:** a stopped NTP drifts minutes per week; journeys order wrongly; heartbeat gaps appear.
- **Detect:** compare the newest log line with the server clock on each live run; alert if more than 2 minutes apart.
- **Status:** Gap, ROADMAP P0-5.

### G4. Out-of-order lines
- **Wrong:** nginx writes a line when a request ends; a 10-second request is logged after faster later ones.
- **Count:** sessions sort by time (the audit does; confirm the main path tolerates it).
- **Test:** a shuffled-by-seconds fixture gives the same visits.

### G5. Partial days
- **Seen:** launch day (2026-10-06) is partial.
- **Count:** stored as partial, faded, never compared (Handled).

### G6. Late lines
- **Wrong:** the daily run at 07:15 New York collects a day that ended at midnight; any request still running at midnight is logged after it. Negligible here.
- **Status:** Handled (coverage rule).

---

## H. The data pipeline

### H1. Log rotation gaps
- **Wrong:** a failed rotation, a missing `.gz`, a corrupt gzip tail, or `copytruncate` (lines lost between copy and truncate) make a day short without failing.
- **Detect:** coverage check (Handled); gzip read errors must count as unreadable lines, not stop silently; heartbeat lines per day should be 288 - fewer means lost logging.
- **Test:** truncated gzip fixture; a day with 250 heartbeats is flagged.
- **Status:** coverage Handled; heartbeat-count check Gap, ROADMAP P0-5.

### H2. Format switch mid-file
- **Seen:** 1,513 combined-format lines (no host, no country) then the extended format from 00:52 UTC; 277 of today's lines could not be host-filtered.
- **Count:** parsed by the fallback, counted, and reported as "could not be filtered" (Handled).
- **Status:** Handled. Keep the notice; it will vanish once those lines age out.

### H3. Server down vs quiet
- **Wrong:** no lines because nobody came and no lines because nginx or the box was down look the same.
- **Detect:** heartbeat gaps (same box: cannot see itself down) plus an outside check.
- **Status:** Gap, ROADMAP P0-3.

### H4. Duplicate lines
- **Seen:** 58 byte-identical lines (mostly our own curl tests, a few `GET /` and `robots.txt` in the same second).
- **Wrong:** a real repeat in the same second and a duplicated log line cannot be told apart. Reading a file twice (e.g. two rotations of the same data, or a config with two `access_log` directives) doubles everything.
- **Detect:** add `$request_id` (and `$msec`) to the log format; then an identical request id is a duplicate. Today: alert if more than ~1% of lines are byte-identical.
- **Status:** Gap, ROADMAP P0-5.

### H5. Unreadable lines
- **Count:** counted, shown, withheld above 1% (Handled).

### H6. Top lists and crossed breakdowns over periods
- **Wrong:** a month's top pages are sums of daily top 50s (the tail undercounts); breakdowns are stored one at a time, so "Canada x mobile x LinkedIn" over 30 days is not in history. Interactive filters can only cross what was stored.
- **Count:** label summed tails; for filters across dimensions, read the 7-day journeys (each has all labels) and say "last 7 days only".
- **Status:** documented; the filter limits must be stated in the app (This release).

### H7. Schema upgrades
- **Count:** in place, with a backup copy first (Handled). A new column is NULL for old days, never zero (Handled).

### H8. Live run during rotation
- **Wrong:** a live run at 00:00 UTC can read `access.log` just as it is renamed and see a nearly empty today.
- **Count:** the snapshot verifies (Handled); a snapshot with fewer lines than the last one for the same day should be discarded, not shown.
- **Status:** Gap, small, ROADMAP P0-5.

### H9. Disk full / logging stops
- **Detect:** newest log line older than 15 minutes on a live run -> "logging stopped" (the heartbeat guarantees a line every 5 minutes).
- **Status:** Gap, ROADMAP P0-3.

### H10. Only 14 days of raw logs
- **Wrong:** any new rule (verified bots, a new AI name) can only be applied back 14 days; older days keep old numbers.
- **Count:** each day records which rules it was counted with (`days.scope` exists for views); add a "rules version" so a chart can mark the change.
- **Status:** Gap, ROADMAP P1-3 (annotations) and P2-2 (archive compressed raw logs off-server for longer re-counts, with privacy limits).

### H11. Backfill rewrites history
- **Wrong:** `backfill --force` changes past figures; a number someone already quoted silently changes.
- **Count:** keep the previous figures of a re-collected day (or at least log old and new totals) and annotate the chart.
- **Status:** Gap, ROADMAP P1-3.

### H12. What the log format does not carry
- Missing today and needed: `$request_id` (duplicates), `$http_sec_purpose` / `$http_purpose` and `$http_next_router_prefetch` (prefetch), `$http_sec_fetch_mode` and `$http_sec_fetch_dest` (navigation vs fetch; browsers send them, most scrapers do not), `$ssl_protocol` (old TLS = old client), `$upstream_cache_status` if caching is added.
- **Status:** Gap, ROADMAP P0-5. Adding fields must keep the parser's layout rule (one field between agent and `cc=`) or update the parser and its test in the same change.

---

## I. Product and operations

### I1. Deploy markers
- **Wrong:** a jump in 404s or a drop in readers after a deploy cannot be tied to it.
- **Detect:** the site's deploy script appends one line (time, version, build) to a file skald reads.
- **Status:** Gap, ROADMAP P1-3.

### I2. Stale build files after a deploy
- **Seen:** all 35 apex 404s and several www 404s are `/_next/static/chunks/...` and font files of a previous build.
- **Wrong:** pages already open in a browser ask for the old build's files; they 404, and the page may break for that visitor.
- **Count:** Broken links group "stale build file"; never mixed with real broken links. A surge right after a deploy is expected; one that lasts more than an hour is a bug (keep the previous build's static files for a day).
- **Status:** Gap, ROADMAP P1-3.

### I3. Large CSV exports
- **Wrong:** a 30-day journeys export at 10x traffic is hundreds of MB; spreadsheets break at 1,048,576 rows; a formula-looking cell (`=`, `+`, `-`, `@`) runs in Excel.
- **Count:** stream exports; cap rows with a clear "truncated at N" line; escape formula-looking cells (the leads export already does).
- **Test:** a cell starting with `=` is exported quoted with a leading `'`.
- **Status:** escaping: check; size cap: Gap, ROADMAP P1-10.

### I4. Multiple sites
- **Wrong:** one server, several sites (website, a short-link service, an app): host lists overlap, `/v/` belongs to another product, one history for all.
- **Count:** one config per site sharing a history (Handled by design); an "excluded" line per site.
- **Status:** Handled; site switcher in the app: This release or ROADMAP P2-4.

### I5. Dashboard data size
- **Wrong:** at 10x traffic the live JSON with 1,000 journeys and 30 days of breakdowns grows to megabytes, refreshed every 2 minutes.
- **Status:** ROADMAP P2-1.

### I6. Refresh now
- **Count:** one run per 15 seconds, same origin (Handled).

### I7. Report mail delivery
- **Wrong:** the mail goes from and to the same Gmail account; if it lands in spam or Gmail throttles, nobody knows the report failed.
- **Status:** Gap, ROADMAP P0-3 (alert on send failure goes to a second address).

---

## J. Privacy

### J1. Showing addresses
- **Rule:** addresses may be shown for machines (AI crawlers, search engines, scanners, our own labelled traffic) on password-protected pages. Never for people, including people who followed a citation (the "cited" tier is people).
- **Test:** the AI activity feed carries an address only for answer-engine rows, never for cited rows; an export of readers carries none.
- **Status:** This release (latest AI activity with address) - must implement this rule.
- **Changed (2.4.0, owner 2026-10-12):** a site that keeps IP addresses (`privacy.keep_ips`) keeps each person's visit with its address for `privacy.keep_days` (395), shown to owners and admins in the person search only, every search audit-logged. Off, the rule above stands. An install upgraded from before 2.4.0 starts with it off.

### J2. Journeys can identify
- **Wrong:** a journey with a rare country, device and landing page at 03:12 can point to one person.
- **Count:** journeys keep times to the minute, no address, no agent, 7 days (This release). Do not export journeys with country for countries with fewer than 5 readers in the period. Since 2.4.0 the visits kept with their address (`visits` in conversions.sqlite) identify by design; they are never exported, only shown in the person search.

### J3. The keyed 30-day returning-visitor hash
- **Wrong:** a hash of address + agent kept 30 days is pseudonymous personal data (GDPR, PIPEDA). If the key leaks, addresses can be recovered by brute force (the IPv4 space is small).
- **Count:** HMAC with a secret key outside the history file; rotate the key every 30 days (old hashes become useless by design); delete hashes after 30 days; never export them.
- **Test:** a stored hash cannot be reproduced without the key file; hashes older than 30 days are gone after collect.
- **Status:** This release (hash) + ROADMAP P0-7 (rotation, deletion, policy text).

### J4. Deletion and access requests
- **Wrong:** someone asks "delete what you have on me". Logs hold their address for 14 days; the 30-day hash may hold a pseudonym; the CMS holds the lead.
- **Count:** documented procedure: delete from the CMS; logs age out in 14 days (or are edited); returning hashes age out in 30 days; aggregates hold nothing personal.
- **Status:** Built. `skald forget --ip` removes the address from the private files, its hashes and its kept visits; `--email`, `--vid` and `--lead` remove the conversions, removed rows, name and email. The person search answers an access request (what is kept about this address or email).

### J5. Personal data in URLs
- **Count:** paths only, query values dropped except attribution keys (C5). A path containing an `@` is stored as "(path with personal data)".
- **Test:** `/unsubscribe/jane@example.com` never reaches history.
- **Status:** Gap, ROADMAP P0-7.

---

## K. Insights (Working, Dropped, New, Gone, Anomalies, Opportunities) and the per-page drill-down

Insights compares a recent window with a baseline: the median of past
days, with the median absolute deviation (MAD) as the spread, and a
minimum volume before anything is reported. Each entry below is a way
that can report something false. Acceptance rule for the release: **every
finding states its numbers (now, baseline, days in the baseline) so a
reader can judge it, and no finding is shown that the rules below would
suppress.**

### K1. Small numbers
- **Wrong:** at example.com's volume most pages get 0 to 3 readers a day. Three failure modes:
  - **MAD of zero.** A page that usually has 0 readers has median 0 and MAD 0; one reader is an infinitely large deviation and tops Anomalies.
  - **Many comparisons.** About 475 pages x sources x countries is thousands of series; by chance alone some "drop" or "work" every day.
  - **One visitor is the whole change.** One reader opening a page five times, or our own team testing a page, is "Working".
- **Detect:** count readers (visits), never views or requests; require at least N distinct readers in the recent window *and* in the baseline (start with 10 for "Working"/"Dropped", 5 for "New"); floor the spread: `spread = max(1.4826 x MAD, sqrt(median), 1)`; require both a relative change (e.g. 50%) and an absolute one (e.g. 5 readers); cap each list (top 10 by absolute change).
- **Count:** below the minimum, the item is listed as "too few readers to tell", never as a finding.
- **Test:** a page going from median 0 to 1 reader produces no anomaly; 200 random Poisson series with no real change produce at most a couple of findings; a change from 2 to 4 readers is not "Working" (100% but below the absolute minimum).
- **Status:** This release (thresholds exist per the brief); the MAD floor and the list cap must be checked.

### K2. Weekdays, seasons and the time of day
- **Wrong:** a B2B site is quiet at weekends; comparing a Saturday with a median of weekdays reports "Dropped" every weekend and "Working" every Monday. Holidays do the same: Canadian Thanksgiving 2026-10-12, US Thanksgiving 2026-11-26, the Christmas weeks. DST days are 23 or 25 hours (G1). Crawlers run on their own weekly schedules, so bot and AI series are seasonal too.
- **Today-so-far trap:** comparing today until 10:00 with whole past days reports everything as "Dropped" each morning.
- **Detect:** baseline by same weekday once 4 whole weeks exist (before that, whole-week totals only, never single days); compare today-so-far with the same hours of past days; mark known holidays (a small list per country in the views: US, Canada) and leave them out of baselines; normalise 23/25-hour days by hours for daily rates.
- **Count:** findings on a holiday or DST day are labelled as such and not alerted.
- **Test:** a synthetic month with a weekday/weekend cycle and no trend produces no Working/Dropped findings; today at 10:00 with a normal morning is not "Dropped".
- **Status:** This release must handle the today-so-far and weekday cases; holiday list is small and can follow.

### K3. Partial, withheld and unmeasured days
- **Wrong:** a partial day (launch day 2026-10-06, logging gaps) looks like a crash; a withheld day read as zero looks like a crash; days collected before a schema version have no breakdowns or journeys (NULL), and treating NULL as 0 makes every page "New" on the day measurement started.
- **Detect:** baseline uses whole, verified days only; NULL means "not recorded" and is skipped, never 0; the number of baseline days is shown; below a minimum (e.g. 7 whole days) the section says "not enough history yet".
- **Count:** a window containing a withheld or partial day is compared only over its whole days, and says so.
- **Test:** a baseline with one withheld day gives the same result as one without that day; a page first measured on schema-8 day D is not "New" on D.
- **Status:** This release must handle (the history already marks partial, withheld and pre-schema days).

### K4. Launch-day and rule-change effects
- **Wrong:** the site went live 2026-10-06. For the first weeks:
  - every page, source and assistant is "New" because there is no history;
  - search crawlers index heavily after launch and then settle, so "Dropped" for Googlebot or GoogleOther is expected, not bad news;
  - the launch-week audience (the team itself, launch-announcement sites, people you invited) inflates the baseline, so ordinary later weeks look like drops;
  - old-site URLs 404 heavily and then fade as redirects ship, so they show as "Gone" (that is the good kind).
  The same happens after any **rule change**: marking the team's address as ours (ROADMAP P0-1) will make readers, that country and several pages "Drop" by double digits overnight; verified bots (P0-2) will make some answer-engine names "Gone".
- **Detect:** a launch annotation and rule-change markers (ROADMAP P1-3); no "New" or "Gone" until 14 whole days of history; baselines never span a rule change without saying so, or are recounted with the new rules where the logs allow (`backfill --force`, 14 days).
- **Count:** findings whose baseline includes the launch week, or crosses a rule-change marker, carry that note.
- **Test:** a series with a launch spike then a flat level produces no "Dropped" after the spike leaves the baseline; a rule change on day D suppresses (or annotates) Dropped findings that start on D.
- **Status:** This release: minimum history for New/Gone. Markers: ROADMAP P1-3.

### K5. Alert and finding fatigue
- **Wrong:** if Insights lists 30 things every day, nobody reads it; if it emails them, the owner filters the mail and misses the one that mattered. Typical noise sources: the same finding repeated daily; one cause producing many findings (the Meta crawl burst raises answer-engine requests, 404s, redirects and the busiest hour at once); findings that flip ("Working" Monday, "Dropped" Tuesday).
- **Detect:** one finding per cause: group findings that share the same hour, agent or path; a finding must persist (2 whole days, or a whole week for slow series) before it is "Working" or "Dropped"; a repeated finding is shown once with "since D"; a short list ranked by readers affected; dismiss and snooze per finding (stored per site, not per browser).
- **Count:** only Anomalies of the alert types in ROADMAP P0-3 are ever emailed, at most once per finding per day, with a "resolved" message.
- **Test:** a 3-day synthetic incident yields one finding with "since D", not three; a flip-flopping series yields none.
- **Status:** This release for grouping, persistence and list length; email side with ROADMAP P0-3.

### K6. Composition: the number moved, but not for the reason it seems
- **Wrong:** readers "Working" because a crawler slipped into people (A1, A16); a source's share up only because the total fell; a page "Working" because one company or our own team read it repeatedly.
- **Detect:** for any Working/Dropped finding, show how concentrated the change is: share coming from one country, one hour, one browser identity, one referrer. More than ~60% from one of those is shown as "concentrated: check", not as a win.
- **Test:** a gain made entirely by one browser identity in one hour is flagged concentrated.
- **Status:** This release should at least show the concentration figure.

### K7. Gone versus not measured
- **Wrong:** a source is "Gone" because a browser or app started stripping referrers; a page is "Gone" and another "New" because it was renamed or redirected; an AI agent is "Gone" because it changed its name (A4).
- **Detect:** pair a Gone page with a New one when the old path now redirects (301/308) to the new; pair a Gone agent with a New one sharing a vendor; for sources, check whether "direct or unknown" rose by the same amount.
- **Count:** paired items are shown as "moved", not as one loss and one win.
- **Test:** `/old` returning 301 to `/new` on day D gives one "moved" item.

### K8. Opportunities
- **Wrong:** opportunities are suggestions inferred from correlations (a page that AI crawlers fetch often but nobody clicks through to; a landing page where most readers leave after one page; a 404 with real referrers). With few readers they are mostly noise, and the log never shows the cause.
- **Count:** each opportunity states its evidence and counts ("GPTBot fetched 40 times in 30 days, 0 citation clicks"), uses the same minimums as K1, and is worded as a question to check, not a conclusion.
- **Test:** an opportunity is never produced from fewer than the minimum readers or fetches.

### K9. The per-page drill-down
- **Wrong:**
  - History keeps each day's **top 50** pages by name; the rest are not stored by name (breakdowns fold them into "(all others)"). A page outside a day's top 50 has no row for that day; drawing that as 0 makes its trend wrong, and a page slipping out of the top 50 looks "Dropped".
  - `/pricing` and `/pricing/`, a page and its old WordPress URL, and its `/ca/` and `/ca/fr/` copies are different paths.
  - Readers of a page over a period are a sum of daily readers; one person on two days counts twice.
  - AI fetches of a page count requests; citations count visits; they are not comparable.
- **Detect:** the drill-down marks days where the page was "not in the stored top list" differently from a true 0, and says how many; journeys (7 days) give exact figures for the last week; paths normalised as in C2; a "same page in other views" link.
- **Count:** trend lines draw only days with a stored value; gaps are gaps.
- **Test:** a page ranked 60th on day D shows "not stored" for D, not 0; Insights never reports a page as Dropped because it left the top list.
- **Status:** This release must handle; raising the stored list size for pages (cheap at this volume) is a reasonable fix.

---

## Seen in the live log: quick reference

All from 2026-10-06 22:08 UTC to 2026-10-07 16:50 UTC (17,065 lines) unless "today".

| Fact | Number |
| --- | --- |
| Next.js navigation payloads (`_rsc`) | 10,386 (61%) |
| Old combined-format lines (no host, no country) | 1,513 |
| meta-externalagent, in 34 minutes | 4,897 from 70 addresses |
| GoogleOther / Googlebot / InspectionTool (today) | 3,224 / 546 / 118 |
| YandexBot | 968 from 376 addresses (verified by reverse DNS) |
| Unlisted address in another country (likely the site's own team) | 2,962 requests, 7 agents |
| Same agent from many addresses within 10 s | up to 49 addresses |
| Bare `Mozilla/5.0` | 236 |
| 404s / distinct 404 paths | 426 / 321 |
| Apex redirects / trailing-slash redirects | 744 / 433 |
| Byte-identical duplicate lines | 58 |
| HEAD / 304 / 206 / 499 / 429 / 400 / 5xx | 39 / 64 / 0 / 7 / 4 / 13 / 0 |
| IPv6 requests | 0 |
| Readers today, desktop share | 143, 99% desktop |
