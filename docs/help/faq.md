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

## What are the AI alerts?

Three alerts watch how AI assistants treat your site. They show on [Alerts](#health/alerts) (press **AI** to see only them) and in **AI reading changes** on [AI & crawlers](#bots):

- **AI started reading**: an assistant fetched a page yesterday that it had not fetched in the 28 days before.
- **AI stopped reading**: an assistant that fetched a page in at least 3 of the 4 weeks before has not fetched it for 7 days.
- **AI sending people**: the visits likely sent by an assistant jumped (3 times its 28-day average, and at least 10) or vanished. With fewer visits Skald says "too few to judge" and does not alert.

An assistant means its company: GPTBot, OAI-SearchBot and ChatGPT-User are all OpenAI. Each alert names the assistant, the page, the days and the numbers. They use whole days only, and only figures Skald has already counted twice. If a day in the window is withheld or missing, the alert waits; it never fires on a day it cannot trust. The server admin can change the thresholds or switch each one off (`alerts.ai_*` in the server's config). If alert mail is on, the weekly mail lists the week's changes, and an outgoing webhook can receive each one as `ai.reading_changed` ([Webhooks](webhooks.md)).

## Can Skald write an llms.txt for my site?

It suggests one; it never writes it to your website. Open [AI crawlers](#settings/crawlers) and see **Suggested llms.txt**: links to the pages people and AI assistants read most over the last 90 days, grouped by section, in the llmstxt.org format. Write the one-line summary yourself, check the links, then copy or download it and publish it at `/llms.txt`. See [Settings and retention](settings-and-retention.md).

## Why is my own visit not counted?

Your team's addresses are probably listed as internal. Visits from them go to the "Our own" group, kept apart from people, so your own testing does not inflate the figures. See [Internal traffic](internal-traffic.md) and [Internal traffic settings](#settings/internal).

## Does Skald use cookies?

Not to count visits. Skald reads the server's log, which needs nothing in the browser. The optional script tag sets no cookie by default; a cookie is used only if your site turns on anonymous visitor IDs shared across subdomains. Signing in to the dashboard uses one cookie, for your own session. See [Privacy](privacy.md).

## How fresh is today?

Today's figures are recounted about every two minutes. The foot of the page says when they were last updated and when the next update is due. If your server allows it, **Refresh** in the top bar recounts at once. Yesterday becomes a whole, checked day after the morning's run.

## Why does a whole day appear only the next morning?

The daily run checks each finished day by both counts before it is stored. Until then, today's figures are a live count, and can change.

## Where are my leads?

On [Leads](#leads), under Results: leads per day by kind, and where they first and last came from. Leads and demos booked also show beside the visitors on Overview, Live, Sources, Pages, Locations, Insights and Compare. Spam, duplicate and test leads are listed under **Left out**. Owners and admins can find one lead, with its email and the visits around it, with the search at the top, when your site keeps names and emails. See [Leads and conversions](leads-and-conversions.md).

## How do I get data out?

- **Export** in the top bar: every table on the page as CSV files in a ZIP, the page as JSON, a printable report, or the report builder for several pages at once.
- **API**: every figure as JSON, for a script. Tokens are made in **Settings > Team & access > API & tokens**. See [API](api.md).
- **MCP**: let an AI assistant read your figures. See [MCP](mcp.md).

## Who can see visitor addresses?

Only people signed in to your organisation: [Requests](#requests) (the last 6 hours), today's AI activity, and the internal-address list (admins). When your site keeps IP addresses, owners and admins also see each kept visit's address in the person search; every search goes to the audit log. Stored history never holds an address. API tokens see addresses only with the private scope. See [Privacy](privacy.md).

## How do I delete someone's data on request?

Send the address or the email address to the person who runs your Skald server. They run Skald's forget command, which deletes the visits, conversions, name and email kept for it. See [Privacy](privacy.md).

## Why are my filters greyed out?

The log keeps each breakdown on its own, so some pages cannot apply some filters, and filters cannot be crossed (for example, Canada AND Chrome). A greyed-out filter chip is one the page cannot apply. The page says which.

## Can I see times in my own time zone?

Yes. Select the round **You** button at the foot of the sidebar and choose **Time zone**: your own, the site's, or UTC. Days are still counted midnight to midnight in the site's own zone.

## How do I invite a colleague?

Admins and owners go to **Settings > Team & access > Team** and use **Invite someone**. See [Sign-in and team](sign-in-and-team.md).

## My site is behind Cloudflare: will cached pages be missed?

Only if Skald reads nothing but your server's log. A page Cloudflare serves from its cache never reaches your server, so your server's log does not see that visit. Two fixes, set up by whoever runs your Skald server: Cloudflare's own request log (Logpush), if your Cloudflare plan offers it, or the small Skald Worker on any plan. The Worker sends Skald one line per request after the page has gone out, so it never slows the page. When Skald reads both the Worker and your server's log, it takes only the cached pages from the Worker, so no visit is counted twice.

## What does "A newer Skald is available" mean?

A newer release of Skald is out than the one your server runs. Only owners and admins see this line at the top of the dashboard, and the daily and weekly mail show it too. **What's new** opens the release notes. **×** hides the line in your browser until the next release. A red line is a security release: ask whoever runs your Skald server to upgrade soon. Nothing changes until they do (or until they switch on automatic upgrades). To check, your server asks GitHub once a day which release is the latest; it sends only Skald's version, never your figures or visitors. Your server admin can turn this off (`updates.check: false`). See [Upgrading](https://github.com/spcaeo/skald/blob/main/docs/UPGRADING.md).

## How is Skald upgraded?

Whoever runs your Skald server upgrades it with one command. It checks the download, copies every database first, refuses to jump to a new major version or to run during the morning run, and puts the old version back if anything fails. Your figures and settings stay. Automatic upgrades for fixes (or fixes and features) can be switched on; they are off unless your admin turns them on. With Docker, the admin pulls the new image. See [Upgrading](https://github.com/spcaeo/skald/blob/main/docs/UPGRADING.md).
