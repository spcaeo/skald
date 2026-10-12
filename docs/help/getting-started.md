# Getting started

What Skald counts, how the pages are laid out, and how to choose a period, filter, drill down, compare and export.

To look around first, open the [live demo](https://spcaeo.github.io/skald/): the whole dashboard with 60 days of sample data for a made-up site. No sign-up. Saving and the settings pages need a running Skald, so in the demo they say so.

## New here?

Four short guides take you from nothing to a working install:

- [Docker: first install in 10 minutes](docker-first-install.md): run it, sign in, fill the history, check it with `skald doctor`.
- [Pick your road](pick-your-road.md): which way your leads and bookings should reach Skald, for your kind of site.
- [Send leads from your backend in 5 minutes](leads-from-your-backend.md): the signed lead hook, with copy-paste examples.
- [Demo bookings](demo-bookings.md): Calendly and Cal.com, embedded, linked or by webhook, and keeping only your own event types.

## What Skald counts

Skald reads your web server's own access log. Every request the server answers is one line in that log, so Skald sees every visit, including the ones a browser script never sees: AI assistants, search engines and bots.

Each request lands in exactly one group, and the groups add up to the log exactly:

| Group | What is in it |
| --- | --- |
| People | A browser that is none of the groups below |
| AI assistants | AI crawlers that collect for training, crawlers that index for AI search, fetches made because someone asked a question, and people who followed a link from an AI answer |
| Search engines | Classic indexing, such as Google and Bing |
| Bots and scanners | Monitors, SEO tools, link previews from chats, and probes |
| Our own | Your team, your own crawler and your tests. Kept apart, never counted as people |

Keep three words apart:

- **Requests** are lines in the log. One page can make many requests.
- **People** are browsers that look like real readers. This is an upper bound: when in doubt, a request is not counted as a person.
- **Machines** are everything else: AI crawlers, search engines and bots. They are shown in their own units, never added to people.

AI traffic is not people. A person who clicks a link inside an AI answer is counted as a person, with the AI assistant as their source.

### The optional script tag

If your site adds the `skald.js` script tag, Skald also counts what happens inside a page: button clicks, form steps, demo bookings, links out, and readers who reach three quarters of a page. These show on [Events](#events). The log's figures never depend on the tag. See [Tracking script](tracking-script.md).

## The menu

The sidebar groups the pages by what you came to find out.

| Group | Pages |
| --- | --- |
| Home | Overview, Live, Insights, Compare |
| Audience | Visitors, Sources, Pages, Locations & devices, Time of day |
| Results | Leads, Conversions, Funnels, Events |
| AI & bots | AI & crawlers |
| Site & server | Site health (with Alerts, Data quality, Page speed and Broken links), Requests |

- **Overview** is where every visit starts: the period's headline figures, leads and demos booked among them.
- **Live** shows today: people first, then machines, the latest visits, and today's leads and bookings as they arrive.
- **Insights** lists what is working, what dropped, and what is new or gone, leads too.
- **Compare** puts any two periods side by side, with their leads.

When your site reports leads (a form, a booking), they show beside the visitors on Overview, Live, Sources, Pages, Locations, Insights and Compare, not only on Leads and Conversions. See [Leads on every page](leads-and-conversions.md#leads-on-every-page).
- **Site health** shows open alerts, the data's own checks, page speed and broken links.
- **Requests** lists the last few hours of the request log, line by line.

**Settings** opens from the gear at the foot of the sidebar. It has its own menu. See [Settings and retention](settings-and-retention.md).

The round **You** button beside the gear holds your own choices:

- **Theme**: System, Light or Dark.
- **Time zone**: show times in your own zone, the site's zone, or UTC.
- **Your account**, **All settings**, **Keyboard shortcuts**, **What's new**, **About Skald** and **Plain page** (every figure, without scripts).
- **Sign out**.

On a phone, the menu opens from the menu button and the bottom bar.

## Choosing a period

The date range sits in the top bar: **Today**, **Yesterday**, **7 days**, **30 days**, **90 days** or **Custom**. The default is 30 days. Every figure on the page follows the period.

To choose your own dates:

1. Select **Custom** in the top bar.
2. Pick the first day in **From** and the last day in **To**.

Days are counted midnight to midnight in the site's own time zone, whatever time zone you choose for display. The site's zone is set in **Settings > This site > Sites**.

> A brand-new site has no whole day yet, so it opens on Today.

## Whole days and withheld days

Every figure is counted twice, by two separate roads. A day is shown only when both counts agree.

| A day that is | Means |
| --- | --- |
| Whole | Both counts agree. It is in every total |
| Partial | The log covers only part of the day. It is left out of totals |
| Withheld | The two counts did not add up. Nothing is shown for it |
| Not collected | Skald was not reading the log that day |

A withheld day is never shown as zero. A figure that was not recorded is left blank, not zero. Unknown stays unknown. When a period holds such days, the page says how many and which.

Today's live figures can be withheld too, if they do not add up. They come back at the next recount.

## Filters

1. Select **Filters** in the top bar.
2. Choose a Country, Page path (contains or starts with), Source, Campaign, Referring site, Device or Browser.
3. Select **Apply filters**.

Active filters show as chips under the top bar. Select the cross on a chip to remove that filter, or **Clear all** in the Filters panel.

The log keeps each breakdown on its own, so filters cannot be crossed (for example, Canada AND Chrome). A filter that a page cannot apply is greyed out, and the page says so.

If your site has several page groups (for example, the blog apart from the product pages), a **Page group** list sits beside the period.

### Saved views

Save the period, page group and filters on screen under a name, and come back to them later. Saved views are in the top bar, and in the **More** menu on a narrow screen. The address bar also keeps every choice, so you can share a link.

## Drill-down

Select any country, page, source, AI assistant, campaign, referring site, device, browser, hour, address or bot. A panel opens with its trend, the visits and the requests behind it.

- Keep selecting inside the panel to narrow further.
- Step back with the browser's Back button, or with the trail at the top of the page.
- On the keyboard, press Enter on a value, a bar or an hour.

On [Pages](#pages), select a page to see its story: when it was published, its first crawl, its first AI fetch, its first person and its first lead.

## Compare

There are two ways to compare.

- **Compare to the previous period**: the button in the top bar. It shows the period before beside each headline figure, and as a dashed line on the charts. It shows only when both periods are whole.
- **Compare** page ([Compare](#compare)): any two periods, A against B, up to 12 months. It shows figures with their change and tables of what is new or gone. Leads, demos booked and every completed action are compared too, in total, by source and by landing page, when both periods are whole and every day has checked conversions.

## Export

Select **Export** in the top bar:

- **Tables on this tab (ZIP)**: every table, with the current filters, as CSV files.
- **This tab as JSON**: the tables and the period's totals.
- **Print this tab**: a clean report. Choose Save as PDF in the print dialog to keep a PDF.
- **Report builder**: choose several pages, the period, page group and filters, then print or download them together.

To read figures from a script or an AI tool, see [API](api.md) and [MCP](mcp.md).

## Keyboard shortcuts

Shortcuts do nothing while you type in a field.

| Keys | What it does |
| --- | --- |
| ? | Show the list of shortcuts |
| Ctrl K (Cmd K on a Mac) | Command palette: go anywhere, run anything |
| / | Search the list on this page |
| [ | Shrink the sidebar to icons, or open it again |
| Esc | Close a panel or a menu |
| g then a letter | Go to a page |

Letters to use after `g`:

| Letter | Page |
| --- | --- |
| o, l, i, c | Overview, Live, Insights, Compare |
| v, s, p, d, t | Visitors, Sources, Pages, Locations & devices, Time of day |
| e, x, f, n | Leads, Conversions, Funnels, Events |
| b | AI & crawlers |
| h, a, q, w, k, r | Site health, Alerts, Data quality, Page speed, Broken links, Requests |
| u | Internal traffic |
| , (comma) | Settings |

## Your site on Vercel, Netlify or behind Cloudflare

Skald needs a record of every request. A site on your own server has one: its access log. Other hosts keep that log to themselves, so it has to be sent to Skald. Whoever runs your Skald server sets this up once:

- **Vercel:** a Log Drain sends every request to Skald (Vercel Pro or Enterprise). On the Hobby plan, only the `skald.js` tag works, so Skald sees people but not AI assistants or crawlers. Step by step: [Skald for a site on Vercel](https://github.com/spcaeo/skald/blob/main/docs/VERCEL.md).
- **Netlify:** a Log Drain (Netlify Enterprise), set up the same way.
- **Cloudflare in front of your site:** pages Cloudflare serves from its cache never reach your server. Cloudflare's own request log (Logpush) or the small Skald Worker, on any plan, sends them to Skald. No visit is counted twice. See the [FAQ](faq.md).

The full list of hosts, with what each one lets Skald see: [Hosting](https://github.com/spcaeo/skald/blob/main/docs/HOSTING.md).

## How fresh the figures are

The foot of every page says when the data was last updated, and when the next update is due. Today's figures are recounted about every two minutes. Yesterday becomes a whole day after the morning's daily run.

If your server allows it, **Refresh** in the top bar recounts today at once.

## Next steps

- [Sign-in and team](sign-in-and-team.md)
- [Internal traffic](internal-traffic.md): keep your own visits out of the figures.
- [Leads and conversions](leads-and-conversions.md)
- [FAQ](faq.md)
