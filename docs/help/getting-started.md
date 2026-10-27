# Getting started

What Skald counts, how the sections and tabs are laid out, and how to choose a period, filter, drill down, compare and export.

To look around first, open the [live demo](https://spcaeo.github.io/skald/): the whole dashboard with two months of sample data for a made-up site. No sign-up. Saving and the settings pages need a running Skald, so in the demo they say so.

## New here?

Four short guides take you from nothing to a working install:

- [Docker: first install in 10 minutes](docker-first-install.md): run it, sign in, fill the history, check it with the doctor.
- [Pick your road](pick-your-road.md): which way your leads and bookings should reach Skald, for your kind of site.
- [Send leads from your backend in 5 minutes](leads-from-your-backend.md): the signed lead hook, with copy-paste examples.
- [Demo bookings](demo-bookings.md): Calendly and Cal.com, embedded, linked or by webhook, and keeping only your own event types.

### Set up your site

For owners and admins, a new site's Overview > Summary starts with a **Set up** list named for the site, for example **Set up example.com**. Each line says in one plain sentence what works or what is left. A line that is left has a **Set up** button: it opens a short dialog that walks you through the fix, step by step. Each line ticks itself once the server's own checks see it working.

| Line | Done when | What Set up does |
| --- | --- | --- |
| Logs arriving | The server's access log is read | Opens **Send this site's visits to Skald**, as in Settings > This site > Data > Send logs: choose how, a sending token, install, test |
| Visits count as people | Browsers load the pages' own scripts and styles | Asks what the site is built with (Next.js, WordPress, something else, or files from a CDN) and saves it |
| Countries shown | Visits carry a country | Says what a country file adds, and writes the mail for whoever runs your Skald server |
| Script tag events (optional) | The script tag's events arrive | What the tag adds; the exact tag for this site with Copy, and where it goes (site builder or plain HTML, WordPress, Next.js); **Send these steps to your developer** or **Share with your developer**; a Test that waits for the first event |
| Lead hook tested (optional) | A hook passed a test or received a lead, and no hook's last real lead was refused | Where your leads come from (your own form or backend, Zapier or Make, Calendly, Cal.com, Typeform, Stripe, HubSpot); makes the secret; the steps with the address and secret filled in; **Send a test lead**, then waits for a real one |
| Mail recipient confirmed | The daily or weekly mail is on, with a recipient who opened the confirm link | Turns the mail on, takes the addresses, shows who still has to confirm, and sends a test mail. With no mail server, every step says so and asks who will set it up (you, as an install admin, or your developer) |
| Privacy settings chosen | Someone chose whether IP addresses are kept | The three IP choices (full, shortened, none), leads' names and emails, then the wording for your privacy notice with Copy |

The dialogs for logs, page assets, Next.js pages, the script tag, the lead hook and privacy start with **Who will do it?**: your AI agent gets one line and does the job, your developer gets the set-up in one mail or zip, or you follow the steps yourself. See [Your AI agent, in every set-up dialog](connections.md#your-ai-agent-in-every-set-up-dialog).

The server's own technical words (config keys, commands) are not on the line. When a line needs them, choose **My developer** in **Who will do it?** (below) and send it to your server admin.

The mail to your developer opens in your own mail program. For the script tag it holds the whole tag: the tag needs no secret. For a lead hook it holds the address and the steps but never the secret: give the secret separately, never by mail or chat.

A hook whose last real lead was refused (for example, its signature did not match) is never ticked: the line says leads are not arriving, and its dialog says the cause and the fix. A test that Skald itself sends (Send a test, or `skald hooks test`) and that fails is a failed test, never a refused lead.

On Overview the list is folded under one line, for example **Set-up: 2 left · Send your logs**, with **Finish set-up** and **Show the list**, so the figures come first. It goes away once every line that is not optional is done. **Hide on Overview** hides it there, for this site, in this browser. The same lines are always on **Settings > To do** ([To do](#settings/todo)), with the done ones folded. To show it on Overview again, search for `setup` and choose **Setup checklist**.

### To do: what needs you now

**Settings > To do** ([To do](#settings/todo)) is where Settings opens. It lists what needs you now, one sentence and one button per row: the site's open set-up lines, a site waiting for proof or paused, a plan over 80% used, an invite not accepted, a mail recipient who has not confirmed, two-step sign-in off, a token unused for 90 days, and Search Console not connected. Done lines fold into **N done**. When nothing is left it says "Nothing needs you. Everything is set up for example.com." At the top, **Find a setting** finds any setting by its name (as **Ctrl K** does).

**Finish set-up (N left)** opens one dialog that asks **Who will do it?**:

- **Me**: the open lines, numbered. Press one to open its own dialog.
- **My developer**: send it to a teammate or your server admin, as a mail or the set-up pack. See [Send set-up to someone](connections.md#send-set-up-to-someone-the-set-up-pack).
- **My AI agent**: what it does (every job it can do, ticked), then pick your agent: one line for it, made in the same dialog. See [Your AI agent, in every set-up dialog](connections.md#your-ai-agent-in-every-set-up-dialog).

The answers are always in this order, and Skald opens on the one you chose last. A choice shows only when it fits: **My AI agent** when a line is a job your agent can do, **My developer** when a line needs work on a server or on the site. Each open line is a button as a whole: it opens the same dialog for that line only. The dialog is in the address (`setup=finish`, or `setup=finish-script` for one line), and so is the choice: `by=me`, `by=dev` or `by=agent`.

Each Set up dialog has its own link, with its step: for example `#overview/summary?setup=rsc&step=2`. Send it to a colleague who is an owner or admin, and it opens the same dialog at that step (or at the first step that still needs a choice).

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

A browser that reads too fast is not a person either. A visit that loads 6 pages or more, all inside 2 seconds, is counted under bots as "too fast to be a person". A quick reader clicking 3 pages in 2 seconds is still a person. A site can change both numbers (`site.too_fast_pages`, `site.too_fast_seconds`).

Two kinds of tool also send a browser's name, and both are bots:

- **A scanner trying many paths.** A visitor that asks for 5 or more different scanner paths your site does not have (`/info.php`, `/wp-login.php`, `/admin/` and the like, each answered "not found") is a scanner for that whole day, with every page it read between them. One or two missing paths are not enough: a person can mistype.
- **A link checker.** A browser opens a page with an ordinary request. A visit that asks for two or more pages with `HEAD` (a request for the headers only) is a tool checking links, and every request of that visit is a bot.

What Skald does not do: call a visit a bot because it was short. Real people open one page and leave. A visit from a hosting or cloud network is flagged, not moved, because people on a VPN come from there too.

**A visit's pages.** A visit shows the pages it loaded from your server and the steps seen in the browser, both: "3 pages (2 seen in the browser)". A step seen in the browser is a page shown from the browser's cache, or a click your site handled without loading a page. Skald sees it from the next request's referrer. It is drawn dashed in the journey, and it is never counted as a page view.

On **Site › Requests**, the script tag's own events to Skald (`/traffic-beacon`) say **script tag event**, and calls to Skald's hooks or log upload say **Skald endpoint**. Only a POST your own pages sent is a **form post**.

### The optional script tag

If your site adds the `skald.js` script tag, Skald also counts what happens inside a page: button clicks, form steps, demo bookings, links out, and visitors who reach three quarters of a page. These show on [Leads & sales > Events](#sales/events). The log's figures never depend on the tag. See [Tracking script](tracking-script.md).

## The menu

The sidebar has six sections. Each section has tabs along its top.

| Section | Tabs |
| --- | --- |
| Overview | Summary, Real time, Insights |
| Traffic | Visitors, Sources, Pages, Places & devices, Search, Retention, Time |
| Leads & sales | Leads, Summary, Sources, Calendar bookings, Funnels, Events, Find a person |
| AI & bots | Assistants, Crawlers, Crawl health, AI answers, Crawler rules, llms.txt |
| Security | Is anything exposed?, Your stack, Who is scanning us?, Attack attempts, Fake browsers, Block list, Alerts |
| Site | Health, Alerts, Requests, Not found, Speed, Data quality |

- **Overview > Summary** is where every visit starts: the period's five key figures (leads among them) with their change, what changed, and whether to work on a page or on its traffic. See [Summary and Pages: is it working?](getting-started.md#summary-and-pages-is-it-working).
- **Overview > Real time** is who is on the site now, on a live world map. See [Real time](real-time.md).
- **Overview > Insights** lists what is working, what dropped, and what is new or gone, leads too. See [Insights](getting-started.md#insights).
- **Traffic** is who came, from where, to which pages, on what, and when; **Search** adds Google's and Bing's own queries ([Search](search.md)) and **Retention** how many came back ([Retention](retention.md)). A source of **Direct** means no referrer and no campaign tag. A country, device or touch the log did not carry says **Not recorded**.
- **Leads & sales** is what the visits brought: leads by stage, demo bookings, funnels, events, and one person's story.
- **AI & bots** is AI assistants (the pages they fetch to answer a question, and the visitors they send), crawlers, how crawlers find your pages ([Crawl health](crawl-health.md)), what the assistants answer about you ([AI answers](ai-answers.md)), which crawlers may come in, and your llms.txt.
- **Security** is who probes your server and what they tried, from the same log: whether any probe got a real file, scanners, attack attempts, fake browsers, a block list to review, your site's stack against known advisories, and security alerts. See [Security](security.md).
- **Site** is the server: what it answered, open alerts, the request log line by line, pages not found, page speed and the data's own checks.

The address names the section and the tab, for example `#traffic/sources`. Older links, such as `#sources` or `#live`, still open the right tab.

### Every view has its own link

Everything you open is in the address, so you can copy it from the address bar and send it, bookmark it, or reload the page and come back to the same place:

- the section and tab, the period, page group, filters and drill-down
- each table's sort, column filters, columns, search and page, and a tab's own switches (for example the open switches on Site > Alerts, or the engine and period on Traffic > Search)
- the drawer or dialog that is open, with what it shows: a visitor, a lead, a request, a cohort, a search row, a Set up dialog or a settings dialog (send logs, API, MCP) and its step, a settings page's tab, the saved views, Export and what you chose in it, the shortcuts

Opening a drawer or a dialog adds one step to the browser's history, so **Back** closes it before it leaves the page. Closing it takes it out of the address.

A link opens what it names only for someone allowed to see it. When it names something you may not see, or something no longer kept, the page opens with one plain line instead, for example "That visitor is no longer kept (journeys are kept 7 days)" or "Not available to your role."

No address ever holds a visitor's IP address, an email or a person search. Where one would be (an address filter on Site > Requests, a drill-down by address, a person search), the link holds a short code instead that only your own browser can read back. Opened in another browser, it says so in one line. Every key the address can hold is listed in [docs/ROUTES.md](https://github.com/spcaeo/skald/blob/main/docs/ROUTES.md).

### The trail and Back

When you go deeper (Summary, then a source, then a page, then a visitor), one link over the tab takes you back: **← Back to** the step before, to that exact view, with its period, filters, sort and what was open. When you did not come from anywhere, there is no line at all. Skald still remembers every step you took in this tab.

- The browser's **Back** and **Forward** go through the same steps, and put the page back where you had scrolled it.
- Going back to a step on the trail (with Back or a link) cuts the trail back to it. Moving along a section's tabs does not add steps.
- The trail belongs to this browser tab. A reload keeps it; closing the tab forgets it. Nothing is sent anywhere.
- A link someone sent you starts its own short trail from the link: the section and tab, then what it opens (for example **Traffic › Pages**, then **/pricing/**).
- On a phone the line shows **← Back to** and where you are.

### Copy a page's link, or open it; copy any value

Wherever a page of your site or a web address is shown (the Pages and Landing pages tables, referring sites, requests, Search pages, AI and crawler pages, pages not found, a visitor's journey, a lead's landing page, the Live lists, the set-up dialogs and the site switcher), pointing at it or moving to it with Tab shows two small icons at its end:

- **Copy** copies the full address, with your site's own address in front of a path (`/pricing/` becomes `https://example.com/pricing/`). The icon turns into a green tick for a moment. If your browser does not allow copying, it says **Copy failed: select and copy**.
- **Open in a new tab** opens the full address in a new tab.

Any other value you may want to paste somewhere else shows the **Copy** icon alone, the same way: an IP address, a user agent, an email, a name, a visitor ID or a lead's reference, a search query, a referring site, a campaign or UTM tag, a crawler or an AI assistant, a network, a host, a reason or an error, a token's name, a robots.txt line or a suggested server line. It copies the whole value, even where the cell shows a shortened one (a long user agent). Labels, headings, numbers and percentages have none.

On a phone or a tablet the icons are always shown. They never open the row's own detail: the row still does that when you select it elsewhere.

Two choices sit in the top bar on every page with figures:

- **Today**, the first choice of the period, sets every tab to today so far, redrawn every 2 minutes, with a live dot. On Overview > Summary it shows today live: visitors on the site now, today's figures against yesterday at the same time of day, where visitors came from and what converted, each linking to its full tab; the map, the visitors now and the flow are on Real time ([Today, live](real-time.md#today-live)). Turn it off to go back to the period you had.
- **Compare with…** puts another period beside this one. It is on by default: a period of whole days is set against the one before it. See Compare, below. It shows only on a tab that compares.

When your site reports leads (a form, a booking), they show beside the visitors on Overview > Summary, Traffic > Sources, Traffic > Pages, Traffic > Places & devices and Overview > Insights, not only under Leads & sales. See [Leads on every page](leads-and-conversions.md#leads-on-every-page).

**Settings**, **Help** and **About** sit at the foot of the sidebar; on a phone, they are in **Menu**. **Help** lists the guides in six groups (Start here, Your visitors, Leads and sales, AI and bots, Connect and set up, Security and privacy), one line each; hover a guide for what it covers. Type in its search box and it lists the guides that hold every word, each with the sections they are in: a section's name opens the guide there. The search and the section are in the address (`#help?hq=calendly`, `#help?part=webhooks&hs=calendly`), so a copied link opens the same. A **?** beside a figure or a heading explains it in a few words; its **Read the guide** opens the guide at the part that covers it. Settings (the gear) opens on **To do**: what needs you now. Its own menu groups the pages: **This site**, **AI**, **Organisation** and **You**. Each page shows its state and its action; the **?** beside its title says what it is for, with links to its guide here and on the public site. See [Settings and retention](settings-and-retention.md).

The round **You** button beside the gear holds your own choices:

- **Theme**: System, Light or Dark.
- **Time zone**: show times in the site's zone (the default), your own zone, or UTC. A time reads the same way everywhere: how long ago, then the moment, such as "3 h ago (18 Oct 13:43 EDT)".
- **Your account**, **Settings**, **Help**, **Keyboard shortcuts**, **What's new**, **About Skald** and **Plain page** (every figure, without scripts).
- **Sign out**.

On a phone, five sections sit in the bottom bar, and a section's tabs scroll sideways. **Menu** in the bottom bar opens Security, Settings, Help, About and your own choices.

## Cities

Where is that visitor coming from? Countries come from your log, or from a country file. Cities need a **city file**: DB-IP's free "IP to City Lite" (a new one each month, free under CC BY 4.0, about 120 MB). Point Skald at it with `logs.city_db` in the config, or `SKALD_CITY_DB` in Docker (for example `/geoip/dbip-city-lite.mmdb` with `-v /usr/share/GeoIP:/geoip:ro`). `tools/update-dbip-city.sh` downloads it once a month.

With the file set:

- **Traffic > Places & devices** has a **Cities** table under the countries: visitors by city, each with its country's flag. Search it, sort it, download it, or select a city for its detail (its trend and the visits behind it). Choosing a country in Filters keeps only that country's cities.
- **Each visit** (the visit list, a visit's panel, a person's visits and Real time's newest visits) says where it came from: "Toronto, Ontario, Canada".
- **Real time**'s map puts a dot on each city with visitors now. See [Real time](real-time.md#cities-on-the-map).

A city is counted for visitors only, never for bots, at the first page of the visit. It is the city's own point, not the visitor's street, and it is a lookup, not a guess: when the file has no city for an address, or names a city in another country than the visit's, the city says **Not recorded**. Cities start on the day the file is set; a period that reaches back before it says how many of its days have them. "IP Geolocation by DB-IP" is shown under the countries and cities, as DB-IP's licence asks.

## Choosing a period

The date range sits in the top bar, beside the page's name, as one group: **Today** (live), **7 days**, **30 days**, **90 days** and **More**, which holds **Yesterday**, **All time** and **Custom** (the one you pick shows in the group while it is the period). With the keyboard the group is one stop: Tab reaches the chosen period, the arrow keys move along it, Enter picks. Every figure on the page follows the period. Each section opens on its own default when the link names no period: **Leads & sales** on the last 7 days (a lead is rarer than a visit, so today is often empty), every other section on Today. A period you pick is kept in the address and stays as you move between tabs and sections; the default of one section is never carried into another, so moving from Overview's Today to Leads & sales opens on 7 days.

**All time** runs from the first day this site has data (its first recorded day, or its first lead when that is earlier) to the last whole day, and the period line says the day it starts: "All time: since Fri 21 Aug 2026, 62 days". The dashboard holds the last 180 days; when your site's data begins before that, the line says so ("All time held here: the last 180 days ... this site's data begins ..."), and no total counts days it does not have.

A few tabs keep a period of their own, so the date range is not shown there. A fixed **Period** chip takes its place and says the tab's own period: **Now** on Real time, each insight's own two periods on Insights, now and the last 30 days on Alerts, the last few hours on Requests, the rules as they are now on Crawler rules. Settings pages have no period at all. A part of a tab with a shorter period of its own says so beside its heading, for example **Each visit** on Traffic > Visitors (visits are kept 7 days).

To choose your own dates:

1. Select **More**, the last choice of the period in the top bar, then **Custom**.
2. Pick the first day in **From** and the last day in **To**.

Days are counted midnight to midnight in the site's own time zone, whatever time zone you choose for display. The site's zone is set in **Settings > This site > Site > Names & time**.

> A brand-new site has no whole day yet, so it opens on Today.

## Whole days and withheld days

Every figure is counted twice, by two separate roads. A day is shown only when both counts agree.

| A day that is | Means |
| --- | --- |
| Whole | Both counts agree. It is in every total |
| Partial | The log covers only part of the day. It is left out of totals |
| Withheld | The two counts did not add up. Nothing is shown for it |
| Not collected | Skald was not reading the log that day |

A withheld day is never shown as zero. A figure that was not recorded is left blank, not zero. It is never guessed. When a period holds such days, the page says how many and which.

Something your site has never sent shows **Not set up**, with one line on how to set it up, never 0 or 0%: an event the tracking tag never sent (Leads & sales > Events), a kind of lead the lead store never recorded (Summary, Funnels), a heartbeat that never ran (Site > Health), or page speed never tested (Site > Speed).

On [Site > Data quality](#site/quality), the reasons a day is **Worth a look** or **Not trusted** are listed above the days, each with how many days it covers. A stretch with no log line counts only when it is long for your site: an hour at least, and longer on a quiet site, where a night's lull is normal.

Today's live figures can be withheld too, if they do not add up. They come back at the next recount.

## Filters

Select the filter icon (**Filters**) at the right of the top bar, beside the search (or search for `filters`). A small number on it says how many filters are on. The panel builds rules:

1. Pick what to filter by: country, city, source type, referring site, campaign or UTM tag, AI assistant, where the visitor first came from, landing page, a page read, pages read, time on site, sent a form (lead), device, browser, operating system, new or returning, or crawler.
2. Pick how: **is**, **is not**, **contains**, **starts with**, **at least** or **at most**. A rule can hold several values: "Country is USA, CAN" keeps either.
3. Choose **All rules** (AND) or **Any rule** (OR). **Add group** puts a few rules in brackets with their own All or Any, for example "Device is Mobile AND (Source is ChatGPT OR Source is Perplexity)".
4. The count at the top says how many visits match as you edit, and each rule says how many it keeps alone. Select **Show N visits** to apply.

Time on site takes words: `90 s`, `1 min`, `2:30`. A value the log did not record never matches a rule by chance: "Country is not USA" leaves out visits whose country is not recorded, because they could have been in the USA. To find those, pick **Not recorded** as a value. Where having no value is an answer (no campaign, no AI assistant), **None** is a value too.

Active filters show as chips under the top bar. Select the cross on a chip to remove that rule, **Edit filters** to change them, or **Clear all** in the panel.

**Where rules apply.** Rules apply in full to the lists of single visits: Traffic > Visitors (the visit list and the visitor flow), Leads & sales > Funnels, and, for what a request carries (crawler, page, country, device), Site > Requests. The counted tabs keep each breakdown on its own, so they apply one value per breakdown and cannot cross them (for example, Canada AND Chrome). A rule a tab cannot apply is greyed out, and a line at the top of the tab says which, with a link to where it does apply, such as **CAN's own view** (the drill-down for that value) or **each visit, on Traffic > Visitors**. The count covers the visits kept for the period: single visits are kept 7 days, and the panel says which days it counts.

A country is shown as its flag and three-letter code, such as 🇺🇸 USA or 🇨🇦 CAN. Point at it to see the full name. A table's search finds a country by its code or its full name, and a CSV file has both: the full name and a **Code** column. A country the log did not record says "Not recorded".

If your site has several page groups (for example, the blog apart from the product pages), pick one under **Filters** in the top bar: **Page group** is at the top of the panel. While one is chosen, a **Page group** chip shows under the bar; its × goes back to all pages.

### Saved views

Save the tab, period, page group, rules and each table's sort, filters and columns under a name, and come back to them later. In the Filters panel, type a name under **Save as a view** and select **Save view**; the saved views are listed beside the rules, each with **Copy link**, **Rename** and **Delete**. They are also in the **More** menu (the three dots at the top right). Saved views are kept in this browser.

**Copy link** copies an address that holds everything the view shows. Whoever opens it signs in first and sees it only if their account may open this site: there is no public share link. The address bar keeps every choice too, so any page can be shared the same way.

### Tables

Every table works the same way:

- **Sort**: select a column's header. The first click sorts it (words A to Z, numbers and dates biggest or newest first), the second the other way, the third back to the table's own order. A value that was not recorded is always last.
- **Filter columns** opens a row of filters under the headers: words **contain**, numbers have a lowest and a highest (`1 min` works for a time), and a column with a few values lets you pick some. The button shows how many are on.
- **Columns** chooses which columns show. The first column, the row's name, always stays.
- **Export what you see** downloads a CSV of the rows that match, in their order, with the columns shown: every matching row, not only the ones on screen.
- Select a row to open its detail, as before, whatever the order or filters.

The sort, column filters, columns and search stay in the address, so a reload, a link or a saved view brings the same table back. Moving to another tab starts its tables fresh.

## Search

**Search or jump to** in the top bar (or **Ctrl K**, **Cmd K** on a Mac; a magnifier on a narrow screen) searches the figures and the dashboard at once. Type a few letters:

- **Pages, countries, sources, referring sites, campaigns, AI assistants and crawlers** seen in the period on screen. Type `pricing` to find /pricing/, `canada` or `CA` for Canada, `claude` for ClaudeBot and claude.ai. Each result says what it is and the period it was seen in. Choose one to open the tab that lists it with its detail panel open.
- **Tabs, Settings pages, Help guides, periods, saved views and actions**, such as `mail` for Settings > This site > Mail & reports. Every settings page is there by its name, such as **AI assistants**, and so is every guide.
- When nothing in the period matches, the days kept before it are searched, and the result says so.

Use the arrow keys and Enter, or click. The search only lists names; the figures are on the tab it opens.

### Find a person

Owners and admins can also find one person. Type an IP address, an email or a lead number in the search: **Find a person** is the first result. You see that person's visits, leads and conversions. Each search is written to the audit log. See [Privacy](privacy.md).

## Drill-down

Select any country, city, page, source, AI assistant, campaign, referring site, device, browser, hour, address or bot. A panel opens with its trend, the visits and the requests behind it.

- In every table and list, the **whole row** opens its value, not only its name. A small arrow after the name shows it. On the keyboard, Tab to a row and press Enter or Space.
- A row about one visit opens that visit instead.
- Keep selecting inside the panel to narrow further.
- At the top of the panel, **Go to** links jump to its visits and how they moved, a page's sources and its story, the Visitors tab filtered to it, and the tab that lists it.
- In the latest visits, each page of a visit opens that page's panel.
- Step back with the panel's **Back** button, the trail at the top, or the browser's Back button. Closing the panel (Esc or the cross) leaves the tab as it was, so the browser's Back button then goes to the tab and filters you came from.

When the panel has visits behind it, **How these visitors moved** draws them as a flow map. See [Visitor flow](getting-started.md#visitor-flow).

[Traffic > Pages](#traffic/pages) opens on **Landing pages and their leads**: search it for a page, sort it with the chips (Most visits, Rising, Falling, Recently changed, Needs work), and select a page to see its story: when it was published, its first crawl, its first AI fetch, its first person and its first lead, and each time it changed according to your sitemap (`page=` in the address). The story's one main button is **Mark a change**. What the columns count is behind the "?" beside the title. **Pages by publish date**, the **Page leaderboard** and **Pages read by people** are under **Open the details** (`pgx_view=open`). **Pages by publish date** has a **Changed** column and a **Changed since** filter from the same dates. See [Change dates from your sitemap](crawl-health.md#change-dates-from-your-sitemap).

## Traffic > Visitors

[Traffic > Visitors](#traffic/visitors) opens on the visits themselves. A **List / Flow** switch sits above them; the choice is kept in the address (`vis_view=flow`; the list when it is absent).

- **Each visit** (List): one row per visit, newest first, the first 12, then **Show all**. When, the country (flag and three-letter code, the name on hover), the city when your server has a city file, the device with its browser and system, the source (with "First came from …" when the visitor first came from somewhere else), **New** or **Returning**, the pages ("3 (2 in the browser)": steps seen only in the browser are said), the time on site and the pages in order. Select a row to open the visitor drawer. See [The visitor drawer](where-visitors-come-from.md#the-visitor-drawer).
- **Visitor flow** (Flow): where visits came from, the pages they read in order, and when they left. See [Visitor flow](getting-started.md#visitor-flow) below.
- **New and returning visitors**: the visits by new and by returning visitors, their shares, and each day as a column. Returning means the same visitor was seen on an earlier day in the 30 before (a keyed hash of the address and browser, kept 30 days). It is counted per visit, so two visits on a visitor's first day are both new. Each day's new and returning visits must add up to that day's visits, or the card is withheld. A day counted before returning visitors were is left out and named, never shown as zero. On Today it counts today so far.
- **How engaged visits were**: visits by pages per visit and by time on site, each adding up to the visits, with the typical (median) visit and the share that read one page and left. A log sees what was loaded, not how long someone read, so a long read of one page shows as a short visit.
- Under **Open the details** (kept open in the address, `visx_view=open`): **Where visits ended**, **Common next steps**, and the engagement tables by source and device. A rate over fewer than 10 visits is left blank, and a note under the table says how many rows that is.

With a filter on, the two cards (and the line under the tab's title) count only the visits the filters keep, when that can be done honestly: they are rebuilt from the kept visits, and only when each day's kept visits are exactly that day's own figures (its visits, returning visits, pages per visit and time on site). The card then says **Filtered: N of M visits**, counted from each visit kept and checked against the days' own figures. When the period reaches past the kept visits (they are kept 7 days) or a day's kept visits do not match its figures, the cards show every visit and say **For all visits: the filters above do not narrow this card**, with why. **Where visits ended** and **Common next steps** follow the filters the same way, when each day's kept visits give back that day's own lists. The engagement tables by source and device, and New and returning by source, are always for all visits, and say so. The flow and the visit list follow every filter.

## Visitor flow

[Traffic > Visitors](#traffic/visitors) has a **Visitor flow** map: pick **Flow** above the visit list. It shows how visits moved: where they came from, the pages they read in order, and when they left.

- Each column is one step: the source, then page 1, page 2 and so on. A bar's height is its visits. A band's width is the visits that moved from one bar to the next.
- A visit that ends flows to **Left after 1 page**, **Left after 2 pages** and so on. A visit with more pages than the map shows flows to **Went on to more pages**.
- Each column keeps its 7 biggest pages and folds the rest into **Other pages**, so every column still adds up to the visits.
- A page loaded twice in a row (a reload) counts once. Moves inside the site count, as in **Common next steps**.
- **Start from** picks the first column: the source type, or who sent them (the AI assistant or site). **Pages** picks how many page columns to draw.
- Point at or tab to a bar to see its visits, its share and where its visits went next. Click it, or press Enter, to open it.
- **Table** shows the same figures as rows, with a CSV. On a phone the table shows first.

The map uses the visits whose journeys are kept: today and the last 7 days. For a longer period it says which days it covers. Every filter applies. The same visits reconcile with **Where visits started**, **Common next steps** and **Where visits ended** for those days. A map that does not add up is withheld, not drawn.

The drill-down panel draws the same map for its visits (**How these visitors moved**), so a country, a source or a page has one too. [Funnels](funnels-and-goals.md#flow-between-the-steps) draws one between its steps.

## Insights

[Overview > Insights](#overview/insights) says what changed, in plain words: what is working, what dropped, what is new or gone, what looks unusual and what is worth fixing.

Above the cards, **To do now** lists what to fix this week, worst leak first, each with its proof, its list, a CSV and a link; mark one done and Skald re-checks it. See [What to fix](what-to-fix.md).

- **The five biggest come first.** Size is how much moved and what it is worth: a lead counts more than a visit, an AI fetch or a crawl less, and a finding on small numbers less. **Show all** lists the rest.
- **One card per subject.** A site that is both a referring site and an AI assistant, or a source's visitors and its leads, is one card; the other findings about it are under **more about this**.
- **One sentence, one number, one link** on each card. The link opens the tab that shows it, filtered to it.
- **Pick what to compare:** **Yesterday** (against the 14 days before), **7 days** or **30 days** (against the same number of days before). **Today so far** lists only what is seen for the first time today, such as a new page or country; rises and drops need whole days, so they are under the others. A window with nothing in it says so.

Insights compare whole, checked days only, so the period in the top bar does not apply here.

## Compare

Compare is on by default: with 7, 30 or 90 days, Yesterday or a custom period, every tab that compares sets the period against the same number of days just before it, and the top bar says **vs previous period**. The address does not say it (`cmp=` is written only for another choice, or `cmp=off`). Select **Compare with…** in the top bar to choose what to put beside the period:

- **Previous period**: the same number of days just before.
- **Same period last year**: 52 weeks earlier, so the weekdays match.
- **Custom period**: any whole days you pick, up to 12 months.

Tables then show A (the period in the top bar), B (the one you chose) and the change. Charts show B as a dashed line. A tab that does not compare has no **Compare with…** button, and says so in one line only when a link asked for a compare. Previous period and last year compare only when both periods are whole and checked; a custom period counts whole days and names any it left out. **Turn compare off** in the same menu; it stays off as you move between tabs and periods (`cmp=off`).

These tabs compare: Overview > Summary, Traffic > Sources, Pages and Places & devices, Leads & sales > Summary, AI & bots > Assistants and Crawlers, and Site > Health. Leads, demos booked and every completed action are compared too, when every day of both periods has checked conversions.

Today, All time and a period that includes today are never compared: picking **Today** turns Compare off, and picking 7 days again brings it back.

## Summary and Pages: is it working?

Overview > Summary and Traffic > Pages answer one question: did what you changed work?

### The period line

Under the title of [Overview > Summary](#overview/summary) and [Traffic > Pages](#traffic/pages) one line gives the exact dates; its **(i)** says what the period means and since when the site is measured. The two options for the period have one place each:

- **Include today**: the switch at the start of the line under the title, one press. With 7, 30 or 90 days, the period ends today and counts today so far, and the title's line says so ("Last 7 days including today ..."). Off, it ends yesterday and counts whole days only. It shows only where it changes the figures: Summary and Pages at 7, 30 or 90 days. It is kept in the address (`inc=1`) and stays on as you move between Summary and Pages.
- **Compare**: the top bar's Compare menu (**vs previous period** when on). It puts the same number of days just before beside the period.

The line says the dates in words. On 15 Jan:

| Period | Dates | The period before |
|---|---|---|
| 7 days, including today | 9–15 Jan | 2–8 Jan |
| 7 days, whole days | 8–14 Jan | 1–7 Jan |
| Today (live) | today until now | yesterday until the same time |

A period that includes today is **never compared**. Today is not over, so its figures would always look lower than a whole day's, and Skald keeps no earlier day cut at the same hour (only yesterday, for Today, live). Turn **Include today** off to compare whole days.

When the period before was not measured (it is before Skald started on your site), the line says **before: not measured** and the first day a full comparison comes, for example "The first full 7 days against the 7 before is on 5 Nov (29 Oct–4 Nov against 22–28 Oct)". Until then, use Yesterday or Today. It never shows 0 for the earlier period and never a rise against nothing.

### Key figures and their change

Summary shows five figures: **People**, **From search engines**, **Returning people**, **Leads** and **Sent by AI assistants**. Select one to open the tab it comes from. With Compare on, each says its change:

- **▼ 40% · before: 125**: down 40% from 125.
- **≈ about the same · before: 12**: the gap is 3 or fewer. At the small numbers most sites have, that is normal day-to-day swing.
- **before: not measured**: the earlier period was not counted. **before: not recorded**: the figure was not kept for those days (for leads, not every day's conversions are checked).

### What changed: is it working?

With Compare on and both periods whole and checked, this card lists **Sources** and **Landing pages**, each with **Now**, **Before** and **Change**, and one sentence on the biggest rise and drop. Each list shows its first 5 rows, then **Show all**. Select a row for its detail.

Below this card, the rest of Summary is one fold, **More for this period**: countries, top pages and sources, AI assistants, who else came, the two cards below, server requests and each day's figures. It stays open while the address holds `ovx_view=open`. Each part also has its own tab.

### Work on the page, or on traffic?

**Left at once** means: the visit loaded that one page and no other (one page view in the server's log). A step a single-page app shows without asking the server is not in the log, so on such a site the share is an upper bound.

- **Improve the page**: at least 10 visits started on the page, 9 in 10 of them left at once, and no lead began there. The page, not the traffic, is the problem.
- **Both**: search found the page at least 3 times and 8 in 10 of its visits left at once. Work on the page and on how it is found.

Each list shows at most 5 pages. Leads come from the conversions data; when they are not recorded for those days, a page says **forms: not recorded**. Every page, in the same order, is on Traffic > Pages with the **Needs work** sort.

### New and updated pages: are they getting found?

The pages whose change date is in the last 30 days: the website's own date when it sends a page list, else the sitemap's "last changed" (`<lastmod>`). Each shows the change date, the visits and search visits since, the first day with a search visit, and whether Google fetched it since. Its period is always the last 30 days to yesterday, whatever the top bar says.

When more than half of the sitemap's dates fall on one day, the card says **Dates look like build times**: some sites stamp every page each time they are built, so every page looks changed.

### Traffic > Pages: sort and filter

The landing pages grid adds **Pages per visit**, **Left after one page**, **AI reads** (live fetches by ChatGPT-User, Perplexity-User, Claude-User and other assistants answering someone) and **Changed**. The sort chips: **Most visits** (the default), **Rising** and **Falling** (the biggest gain or drop against the period before; they need Compare, and without it the grid stays on Most visits and says so), **Recently changed**, and **Needs work** (pages with 10 visits or more, the most left at once first). The chip is kept in the address (`psort`); a column header click sorts by that column instead.

**Changed in the last 30 days** (above the grids, and in **Filters** as a preset) keeps only the pages changed since then. It is the **Changed since** date in the address (`chgfrom`).

### Did my change work?

Changed a page? Open it on [Traffic > Pages](#traffic/pages) and select **+ Mark a change**: pick the day it changed, what changed (content, title, a link to it, a redirect, other) and add a short note if you like. When your sitemap or your website says the page changed on a day you have not marked, the page asks **Track that change?**.

Skald then compares the same number of whole days before and after that day, up to 28 on each side. The day of the change is in neither side. For each of these it shows the figure a day before, after, the change and what it says:

- visits that started on the page
- leads and conversions that landed there
- visits from search engines
- visits from AI assistants
- AI reads (assistants fetching the page live for someone)
- the share who left at once (lower is better)

Until 14 whole days have passed it says **Too early to tell**, how many days it has and the day the verdict comes. After that each figure says **Up**, **Down** or **No clear change** (the difference is within the normal day-to-day swing). **Too few to tell** means fewer than 10 on both sides together. A day that is not whole or not recorded is in neither side; when the two sides then have different numbers of days, they are compared per day and the page says so. A figure not recorded says **not recorded**, never 0.

The change shows as a marker on every day chart. **Copy link** copies the address of this change; **Stop tracking** removes it from the list (the mark stays in the history). Every change marked on the site is listed on [Overview > Insights](#overview/insights), under **Done, and did it work?**. Every figure is counted twice, the second time straight from the stored days; a change the two counts disagree on is left out and named.

Only owners and admins can mark a change, and only with accounts (signing in). A change marked today shows its figures from the next data update.

### AI reads by page

On [AI & bots > Assistants](#ai/assistants), **AI reads by page** lists each page's live fetches by assistants answering someone, now and in the period before (Compare's B when Compare is on), by assistant, then the visits that followed an AI answer's link to the page and the leads that began there. A fetch is not a reader. No AI model is asked anything.

These figures come from one day figure, **visits by landing page**, kept from the first day collected after the upgrade. Older days say **not recorded**, never zero. Each has a second count from the raw log. A page group shows these cards for the whole site only.

## Export

Select **More** (the three dots at the top right), then **Export**. It asks **What do you need?** and shows only that path, with one main button:

- **A PDF of this page**: this page as on screen, with every table row. **Print or save as PDF** opens the print dialog: choose Save as PDF there. **Change** adds other sections, or picks another period, page group or the filters. **Preview** shows the report first.
- **The tables, as CSV**: each table on the page with its own download icon, or **Download all (ZIP)**. They follow the period and filters on screen.
- **A report someone gets every month**: who gets it (your last report's address is filled in), how often (every month on the 1st, or every Monday) and what is in it (this page's part; **Change** adds others). **Start sending** saves it as a client report: see [Client reports](client-reports.md). Owners and admins, with accounts. With no mail server yet, it says so and offers **Download the PDF now**.
- **Everything, for my own tools**: this page as JSON (the tables and the period's totals), and the way to the [API](api.md) and [MCP](mcp.md).

Export opens on your last choice. A link keeps the choice: `dlg=export&kind=csv`. Links to the old Report builder open the PDF with its sections open.

## Keyboard shortcuts

Shortcuts do nothing while you type in a field.

| Keys | What it does |
| --- | --- |
| ? | Show the list of shortcuts |
| Ctrl K (Cmd K on a Mac) | Search: pages, sources, countries and more, or go anywhere and run anything |
| / | Search the list on this tab |
| [ | Shrink the sidebar to icons, or open it again |
| Esc | Close a panel or a menu |
| g then a letter | Go to a tab |

Letters to use after `g`:

| Letter | Tab |
| --- | --- |
| o, i | Overview > Summary, Insights |
| l | Overview > Summary on Today (live) |
| c | Overview > Summary compared with the previous period |
| v, s, p, d, t | Traffic > Visitors, Sources, Pages, Places & devices, Time |
| e, x, f, n | Leads & sales > Leads, Calendar bookings, Funnels, Events |
| b | AI & bots > Assistants |
| h, a, r, k, w, q | Site > Health, Alerts, Requests, Not found, Speed, Data quality |
| u | Settings > This site > Site > Internal traffic |
| , (comma) | Settings: To do |

## Your site on Vercel, Netlify or behind Cloudflare

Skald needs a record of every request. A site on your own server has one: its access log. Other hosts keep that log to themselves, so it has to be sent to Skald. Whoever runs your Skald server sets this up once:

- **Vercel:** a Log Drain sends every request to Skald (Vercel Pro or Enterprise). On the Hobby plan, only the `skald.js` tag works, so Skald sees people but not AI assistants or crawlers. Step by step: [Skald for a site on Vercel](https://github.com/spcaeo/skald/blob/main/docs/VERCEL.md).
- **Netlify:** a Log Drain (Netlify Enterprise), set up the same way.
- **Cloudflare in front of your site:** pages Cloudflare serves from its cache never reach your server. Cloudflare's own request log (Logpush) or the small Skald Worker, on any plan, sends them to Skald. No visit is counted twice. See the [FAQ](faq.md).

The full list of hosts, with what each one lets Skald see: [Hosting](https://github.com/spcaeo/skald/blob/main/docs/HOSTING.md).

## How fresh the figures are

The foot of every page says when the data was last updated, and when the next update is due. Today's figures are recounted about every two minutes. Yesterday becomes a whole day after the morning's daily run.

If your server allows it, **More** > **Recount today now** recounts today at once.

## Next steps

- [Sign-in and team](sign-in-and-team.md)
- [Internal traffic](internal-traffic.md): keep your own visits out of the figures.
- [Leads and conversions](leads-and-conversions.md)
- [FAQ](faq.md)
