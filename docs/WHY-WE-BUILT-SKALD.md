# Why we built Skald

**Every visit, truly told.**

Skald reads your web server's own access log, so it sees what a JavaScript tracker cannot. This is why it exists. The full feature-by-feature comparison with nine other tools is in [COMPARISON.md](COMPARISON.md), and as a page in [comparison.html](comparison.html). Competitor facts were checked on their own sites on 2026-10-07.

## The question nobody could answer

We run a small business website. More and more of the people who find a business now ask an AI assistant first. So we wanted to know three plain things. Is ChatGPT, Claude or Perplexity reading our pages? When someone asks it a question, does it come and fetch us to answer? And do the people it cites actually click through?

Google Analytics could not tell us. Not because it was set up badly, but because of how it works.

## What the usual tools miss

**They only count what runs their script.** Google Analytics 4, Plausible, PostHog and Cloudflare Web Analytics count a visit when a piece of JavaScript runs in a browser. AI crawlers and the fetchers an assistant sends while answering do not run that script. GA4 also drops known bots on purpose: "Traffic from known bots and spiders is automatically excluded" [[1]](https://support.google.com/analytics/answer/9888366). Plausible filters AI crawlers out too [[2]](https://plausible.io/track-ai-traffic). How large a share AI assistants make differs from site to site. Only the server's log can count it, and a script-based tool shows none of it [[3]](../README.md).

**Some people are missing as well.** Cloudflare says plainly that its own analytics beacon is blocked by ad-blockers [[4]](https://developers.cloudflare.com/web-analytics/faq/). Plausible estimates a 5 to 25% gap without its proxy [[5]](https://plausible.io/docs/proxy/introduction). With GA4's basic consent mode, nothing is sent until a visitor agrees. Advanced mode sends cookieless pings and fills the gap with modelling [[6]](https://support.google.com/analytics/answer/9976101). A modelled visitor is an estimate, not a count.

**The numbers are not live where it matters.** GA4's Realtime report covers only the last 30 minutes [[7]](https://support.google.com/analytics/answer/9271392), and its full processing can take 24 to 48 hours [[8]](https://support.google.com/analytics/answer/11198161). Search Console data arrives after 2 to 3 days, with a preliminary 24-hour view [[9]](https://support.google.com/webmasters/answer/96568) [[10]](https://support.google.com/webmasters/answer/7576553). It covers only Google, caps tables at 1,000 rows and hides rare queries [[9]](https://support.google.com/webmasters/answer/96568).

**AI is half covered.** To be fair, the tools are catching up. GA4 now has an "AI Assistant" channel, though it leaves out Google's own AI Overviews and AI Mode [[11]](https://support.google.com/analytics/answer/9756891). Plausible [[12]](https://plausible.io/changelog), Matomo [[13]](https://matomo.org/faq/reports/what-are-ai-assistants-in-matomo/) and PostHog [[14]](https://posthog.com/docs/data/channel-type) have one too. But a channel only sees the person who clicks a link. It never sees the assistant reading your page to answer, or a crawler reading it to train. Bing shows citations in Copilot, but no clicks [[15]](https://blogs.bing.com/webmaster/February-2026/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview). Search Console reports AI Overview impressions [[16]](https://support.google.com/webmasters/answer/16984139). Tools that do see AI crawlers, like Cloudflare AI Crawl Control [[17]](https://developers.cloudflare.com/ai-crawl-control/) or Known Agents [[18]](https://knownagents.com/), need your traffic to pass through their network or a connector.

Nobody answered the whole question in one place, from data we own.

## What Skald does differently

Skald reads the one record that sees every visit: the web server's own access log.

- **Every request, sorted into five groups** that add up to the log exactly: people, AI assistants, search engines, bots and scanners, and our own traffic.
- **AI split by why it came:** to train, because someone just asked a question, or a person who clicked a citation.
- **Crawlers checked, not trusted.** A crawler's name is compared with its owner's published addresses or DNS. A fake is filed as "claims to be GPTBot".
- **Counted twice.** Every figure is recounted by a separate audit. A day that does not add up is withheld, never guessed.
- **Live.** "Today so far" is redrawn every 2 minutes, the last 6 hours can be read request by request, and alerts show on the dashboard (and by email, if you want them).
- **Private and yours.** The log needs no script and no cookie in anyone's browser. It runs on your own server. Raw addresses stay in the log for 14 days, history keeps totals, and one command deletes an address on request.

## What it does now

Since 2026-10-11 Skald does more than count visits. Each part below is built and tested. Most are off until an install switches them on. On the first live install, accounts, settings, MCP and conversions from the lead database are on; the hosted layer is off.

- **Leads that tell you something.** Leads by first and last source over any range, crossed with the status your team set, and the time from first visit to lead.
- **Better tracking.** How engaged each source's and device's visits are, returning visitors by source, goals from the tag's events per 100 visits, campaign tags that are missing or wrong, the exit rate of each page, and Yesterday as a period.
- **Funnels with a history.** Each saved funnel is counted every day, by source and device, with where people dropped off and how long they took.
- **Conversions from your tools.** Calendly, Cal.com, Stripe, Typeform, HubSpot and Zapier can send signed webhooks: a booking, a form, a payment. A Conversions tab shows what started, what finished and what was left half done. It is anonymous by default: no name, no email, no address. Skald never matches people by their address.
- **A script tag, if you want one.** One line in the page sends page views, form steps and bookings to your own server. An anonymous visitor ID, off by default, joins a browser's visits to its conversion.
- **Accounts.** Each person signs in with their own email and password (Show to check it, Keep me signed in on a trusted computer), with invites, roles, two-step sign-in, API tokens and an audit log.
- **Settings in the dashboard.** How long detail is kept, mail and SMTP, sites, internal addresses, integrations and security, without editing a file on the server. A failed morning run sends one short mail.
- **A menu by what you came for, and help in plain words.** Home, Audience, Results, AI & bots, and Site & server; Settings has its own menu. The Help pages explain each part step by step: [getting started](help/getting-started.md), [webhooks](help/webhooks.md), [the API](help/api.md) and [MCP](help/mcp.md) among them.
- **Ask it in plain words.** An MCP server lets Claude, ChatGPT and other AI agents read the same checked figures. It cannot change anything.
- **Logs from other servers, and a hosted layer.** A small shipper sends another server's log to Skald. Sign-up, plans and Stripe billing are built for a hosted Skald, and switched off.

Every new figure is counted twice, like the old ones. A day the two counts do not agree on is withheld.

## What it cannot do

Keep Search Console for search queries, impressions and ranking. Keep GA4 or PostHog for deep in-page analysis and for ad spend; Skald's optional tag sends clicks, form steps and bookings, but no more. Skald also has its own limits. A page a CDN serves from its cache never reaches the log. "People" is an upper bound, because a browser's name is self-reported. AI citations are a floor, because referrers are often stripped. Skald now estimates the hidden part: a direct visit to a page an assistant fetched minutes before is shown as "likely" from that assistant. It is labelled as an estimate and never added to the count, so the citations stay a floor. And you need a server whose log you can read.

So Skald does not replace those tools. It sits beside them. Even the gap between Skald's count and GA4's is useful: it shows how much the script misses.

## Sources

Checked 2026-10-07. Numbers match the comparison page.

1. [GA4: known bot traffic exclusion](https://support.google.com/analytics/answer/9888366)
2. [Plausible: tracking AI traffic](https://plausible.io/track-ai-traffic)
3. [Skald README](../README.md)
4. [Cloudflare Web Analytics: FAQ](https://developers.cloudflare.com/web-analytics/faq/)
5. [Plausible: proxy and ad-blockers](https://plausible.io/docs/proxy/introduction)
6. [GA4: consent mode](https://support.google.com/analytics/answer/9976101)
7. [GA4: Realtime report](https://support.google.com/analytics/answer/9271392)
8. [GA4: data freshness](https://support.google.com/analytics/answer/11198161)
9. [Search Console: data delays and limits](https://support.google.com/webmasters/answer/96568)
10. [Search Console: 24-hour view](https://support.google.com/webmasters/answer/7576553)
11. [GA4: default channel group](https://support.google.com/analytics/answer/9756891)
12. [Plausible: changelog](https://plausible.io/changelog)
13. [Matomo: AI assistants channel](https://matomo.org/faq/reports/what-are-ai-assistants-in-matomo/)
14. [PostHog: channel types](https://posthog.com/docs/data/channel-type)
15. [Bing: AI Performance report (Feb 2026)](https://blogs.bing.com/webmaster/February-2026/Introducing-AI-Performance-in-Bing-Webmaster-Tools-Public-Preview)
16. [Search Console: Generative AI performance report](https://support.google.com/webmasters/answer/16984139)
17. [Cloudflare AI Crawl Control](https://developers.cloudflare.com/ai-crawl-control/)
18. [Known Agents](https://knownagents.com/)
