# FAQ

Short answers to the questions people ask most about Skald's figures, privacy and data.

## Why do my numbers differ from Google Analytics?

They count different things, in different ways.

- Google Analytics counts only browsers that run its script and accept it. Ad blockers, privacy browsers and refused consent banners hide many visits from it. Skald reads the server's own log, so it sees those visits.
- Google Analytics cannot see AI assistants, search engines or bots. Skald counts them, but in their own groups, never as people.
- Skald is careful about who is a person: when in doubt, a request is not a person. Its people figure is an upper bound.
- On sites that change pages without loading a new one, the log sees fewer page views than a script does. Skald says so where it matters.
- Days may be cut at different times if the two tools use different time zones.

## Why does a day say withheld?

Every figure is counted twice, by two separate roads. If the two counts do not agree, the day is withheld rather than shown wrong. It is never shown as zero. The server admin can see why on [Data quality](#health/quality).

## Why is a figure blank and not zero?

Blank means not known. Zero means Skald counted and found nothing. A figure that was not recorded, for example a breakdown from before Skald began collecting it, stays blank. Unknown stays unknown.

## Is AI traffic counted as people?

No. AI crawlers and fetches are machines, and show on [AI & crawlers](#bots) in their own units. A person who clicks a link in an AI answer is a person, and the AI assistant is shown as their source on [Sources](#sources).

## What does "likely from ChatGPT" mean?

It is an estimate, not a count. A person who clicks a link in an AI answer often arrives with no referrer, so the visit shows as Direct. But when they asked, the assistant fetched your page from your server. When a direct visit with no campaign tag lands on a page an assistant fetched in the same minute or up to 15 minutes before, Skald says the visit was *likely* sent by that assistant. It shows these on [Sources](#sources), [AI & crawlers](#bots), [Leads](#leads), [Conversions](#conversions) and in a visitor's details, always marked "likely" with an (i) that says how. They are never added to the AI assistant source or to any other figure. See [Leads and conversions](leads-and-conversions.md).

## Why is my own visit not counted?

Your team's addresses are probably listed as internal. Visits from them go to the "Our own" group, kept apart from people, so your own testing does not inflate the figures. See [Internal traffic](internal-traffic.md) and [Internal traffic settings](#settings/internal).

## Does Skald use cookies?

Not to count visits. Skald reads the server's log, which needs nothing in the browser. The optional script tag sets no cookie by default; a cookie is used only if your site turns on anonymous visitor IDs shared across subdomains. Signing in to the dashboard uses one cookie, for your own session. See [Privacy](privacy.md).

## How fresh is today?

Today's figures are recounted about every two minutes. The foot of the page says when they were last updated and when the next update is due. If your server allows it, **Refresh** in the top bar recounts at once. Yesterday becomes a whole, checked day after the morning's run.

## Why does a whole day appear only the next morning?

The daily run checks each finished day by both counts before it is stored. Until then, today's figures are a live count, and can change.

## Where are my leads?

On [Leads](#leads), under Results. Skald shows counts only: leads per day by kind, and where they first and last came from. It never shows names or emails. Each lead's details stay in your website's own admin. See [Leads and conversions](leads-and-conversions.md).

## How do I get data out?

- **Export** in the top bar: every table on the page as CSV files in a ZIP, the page as JSON, a printable report, or the report builder for several pages at once.
- **API**: every figure as JSON, for a script. Tokens are made in **Settings > Team & access > API & tokens**. See [API](api.md).
- **MCP**: let an AI assistant read your figures. See [MCP](mcp.md).

## Who can see visitor addresses?

Only people signed in to your organisation, and only in three places: [Requests](#requests) (the last 6 hours), today's AI activity, and the internal-address list (admins). Stored history never holds an address. API tokens see addresses only with the private scope. See [Privacy](privacy.md).

## How do I delete someone's data on request?

Send the address (or, for conversions, the email address) to the person who runs your Skald server. They run Skald's forget command. See [Privacy](privacy.md).

## Why are my filters greyed out?

The log keeps each breakdown on its own, so some pages cannot apply some filters, and filters cannot be crossed (for example, Canada AND Chrome). A greyed-out filter chip is one the page cannot apply. The page says which.

## Can I see times in my own time zone?

Yes. Select the round **You** button at the foot of the sidebar and choose **Time zone**: your own, the site's, or UTC. Days are still counted midnight to midnight in the site's own zone.

## How do I invite a colleague?

Admins and owners go to **Settings > Team & access > Team** and use **Invite someone**. See [Sign-in and team](sign-in-and-team.md).

## My site is behind Cloudflare: will cached pages be missed?

Only if Skald reads nothing but your server's log. A page Cloudflare serves from its cache never reaches your server, so your server's log does not see that visit. Two fixes, set up by whoever runs your Skald server: Cloudflare's own request log (Logpush), if your Cloudflare plan offers it, or the small Skald Worker on any plan. The Worker sends Skald one line per request after the page has gone out, so it never slows the page. When Skald reads both the Worker and your server's log, it takes only the cached pages from the Worker, so no visit is counted twice.
