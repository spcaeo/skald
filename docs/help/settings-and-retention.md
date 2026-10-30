# Settings and retention

What each settings page does, who may change it, and how long Skald keeps each kind of detail.

## Opening Settings

Select the gear at the foot of the sidebar, or press `g` then `,` (comma). On a phone, open **Menu** first: the gear is at its foot. Settings opens on **To do** ([To do](#settings/todo)): what needs you now, most important first. At its top, **Find a setting** finds any setting by its name (the same finder as **Ctrl K**).

Settings pages come with accounts. On a server with one shared login, most of these values are set in the server's config file by whoever runs it, and the pages say so.

A page you may not change is shown read-only, with the reason beside each field. Pages your role cannot use are left out of the menu.

### Rows, and the panel that changes them

Each page shows what is set, not a form. A card lists its settings as rows: the name, the value in words, and where it comes from (this site, the organisation, the whole install, the config file or the default). Something that is on or off, or set or not, has a coloured label: **On**, **Off**, **Set**, **Not set**. A card where nothing is yours to change is one line, **Read-only**, with the reason.

To change a setting, select its row. The card's settings open in a panel on the right, with one **Save** at its foot. **Save** wakes up once you change something. After a save the panel says so, and the rows behind it show the new values. The panel's address names the card (`edit=people`, for example), so a link or a reload opens it again, and **Back** closes it.

The same goes for lists: an internal address, a client report, an AI answers profile and a token each have a row with a status label, and their actions (pause, edit, send, delete) are in the row's panel. The page's one main button sits beside its title: **Add an address**, **New report**, **New profile**, **New token**, **Send a test mail**, **Download CSV**.

### How the pages are laid out

- **The menu.** On a computer, the settings menu takes the sidebar's place while a settings page is open. On a phone, the menu sits at the top of every settings page as a select, **Settings page**, grouped the same way, so you never need the drawer.
- **Tabs inside a page.** Some pages have tabs, such as **Data**, **Site** and **Mail & reports**. Each tab has its own address (`sub=`), so a link opens that tab.
- **What it is for.** Each page shows its state and its action only. The **?** beside the title says what the page is for in a sentence or two, with a link to its guide inside Skald and to the same guide on the public site, skaldanalytics.com/docs/<guide>/.
- **Old addresses.** A link to an old settings page still works. It opens the page the setting is on now.

The palette (**Ctrl K**, **Cmd K** on a Mac) finds every settings page by its name, such as "AI assistants".

## The settings menu

**To do** is at the top, above the groups.

| Group | Pages |
| --- | --- |
| This site | Data, Leads & tools, Site, Privacy, Mail & reports, Alerts |
| AI | AI assistants, AI answers |
| Organisation | Sites, People, Billing (hosted plans only), Audit log, Organisations (accounts only) |
| You | Your account |

**This site** is about the site you have open; its name is beside the group. **Organisation** is about every site and person of your organisation. **Help**, at the foot of the sidebar, opens every guide.

**Back to the dashboard**, at the top of the settings menu, returns to the page you came from.

The tabs inside a page:

| Page | Tabs |
| --- | --- |
| Data | Send logs, Script tag & goals, What counts, Test a sample |
| Site | Names & time, Internal traffic |
| Mail & reports | Mail, Client reports |
| AI assistants | MCP, API, Tokens & links |
| AI answers | Questions & profiles, API keys |
| People | Team (Users, on a server with one shared login), Sign-in rules |

These pages have guides of their own:

- To do: [Getting started](getting-started.md), "Set up your site".
- Data › Send logs and Test a sample, and Organisation › Sites: [Connections](connections.md).
- Data › Script tag & goals: [Tracking script](tracking-script.md) and [Funnels and goals](funnels-and-goals.md).
- Leads & tools: [Leads and conversions](leads-and-conversions.md), [Webhooks](webhooks.md), [Search](search.md), [Your own tools](your-tools.md) and [Recorded journeys](recorded-journeys.md).
- Alerts: which alerts are on and whether they are mailed; the alerts themselves are on Site › Alerts ([Security](security.md) for the security ones, [Your own tools](your-tools.md#alerts-and-the-monday-mail) for the marketing ones).
- Site › Internal traffic: [Internal traffic](internal-traffic.md).
- Privacy: [Privacy](privacy.md), and this guide below.
- Mail & reports › Client reports: [Client reports](client-reports.md).
- AI answers, and its API keys: [AI answers](ai-answers.md).
- AI assistants › MCP: [MCP](mcp.md). API and Tokens & links: [API](api.md).
- People and Your account: [Sign-in and team](sign-in-and-team.md).
- Organisations: [Organisations](organisations.md).

## Who may change what

"Admin" means an owner or admin of the site's organisation. "Install admin" is a flag the server admin gives to a person, for settings that apply to every site on the server.

| Page | Part | Who may change it |
| --- | --- | --- |
| Privacy | Detail kept for this site | Admin |
| Privacy | People (IP addresses, names and emails) | Admin |
| Privacy | Leads (how long leads and their pages are kept) | Admin |
| Privacy | Backups | Install admin |
| Mail & reports › Mail | Reports (the daily and weekly mail) | Admin |
| Mail & reports › Mail | Mail server (SMTP), Google PageSpeed | Install admin |
| Mail & reports › Client reports | Client reports, agency branding | Admin |
| Site › Names & time | Host names, Views, Time zone, Logo | Admin |
| Site › Internal traffic | Your own addresses | Admin |
| Data › Send logs | Log file | Install admin |
| Data › Script tag & goals | Visitor IDs, Goals | Admin |
| Data › What counts | Page assets, Not forms, Not pages | Admin |
| Leads & tools | Hooks, event types, outgoing webhooks, your own tools, recorded journeys | Admin |
| Alerts | Which alerts are on, and the mail | Admin |
| AI answers › Questions & profiles | The site's lists, tracking profiles | Admin |
| AI answers › API keys | The assistants' API keys | Install admin |
| AI assistants | Tokens, MCP and API set-up, shared links | Admin |
| People › Sign-in rules | Require two-step sign-in, session length | Owner |
| Audit log | (read only) | Admins may read it |
| AI & bots › Crawler rules | Every crawler | Install admin |
| Organisation › Sites | Add a site | Admin |
| Organisation › Sites | Pause or resume a site | Admin |
| Organisation › Sites | Remove, restore, clear data, delete all data | Owner |
| Billing | Plan and payment | Owner (admins can read it) |
| Organisations | Members, site access, invites, keys, settings | Owner or admin of that organisation |
| Organisations | Archive or restore; the sign-in rule | Owner |
| Organisations | Make an organisation; its privacy class | Install admin |

Viewers see the pages read-only.

## Privacy

[Privacy](#settings/site/privacy) (**Settings › This site › Privacy**) sets how long the detail is kept. Totals, page milestones and every stored day's figures are kept forever. They are not a setting.

| Setting | What it keeps | Range | Default |
| --- | --- | --- | --- |
| Detail days | Each visit by its labels, and each page's daily figures (used by Compare with… and the page story) | 30 to 3650 days | 400 |
| Journeys | Anonymous visits: start time, country, device, source, pages in order | 1 to 90 days | 7 |
| Returning-visitor matching | How long a visitor can be recognised as returning | 1 to 90 days | 30 |
| In-page events | Events from the script tag | 30 to 3650 days | 400 |
| Visits with addresses | Each visit with its IP address and browser (card **People**). When you set it shorter than the leads, also the most a lead's name and email are kept | 1 to 3650 days | 395 |
| Leads and the pages they read | Each lead, its name and email, and the pages its visitor ID read (card **Leads**) | Kept for good, or 1 to 3650 days | 400 days |
| Pages of visitors who have not signed up yet | The pages read with a visitor ID that has no lead yet (card **Leads**) | 1 to 400 days | 30 |
| Keep ad click IDs on leads | The ad click ID (gclid, msclkid, fbclid...) kept with each lead, for owners and admins only (card **Leads**). Turned off, the ones kept are deleted at the next run. See [Ad click IDs](leads-and-conversions.md#ad-click-ids-off-unless-you-turn-them-on) | On or off | Off |
| Daily backup copies | Copies of the history on the server, for every site | 1 to 60 | 14 |
| Weekly backup copies | Weekly copies of the history | 0 to 52 | 8 |

Each field says where its value comes from: this site, the organisation, the whole server, the config file, or the default.

On an internal or enterprise site the page says **Kept: nothing is deleted (internal or enterprise).** at the top and on the **People** card. The windows are then not applied: Skald deletes and clears nothing by itself on that site, and a shorter window removes nothing. A person's own request to be deleted, run by an admin, still removes what is kept about them. See [Privacy](privacy.md#sites-that-keep-everything).

Which rule decides is the organisation's **privacy class** ([Organisations](organisations.md#privacy-class)). **Internal** (the default) keeps everything on a server that keeps everything. **Client** makes the site follow the windows above even then. The page says which one applies, for example "Example Co is a client organisation: this site follows its own retention settings, even though the install keeps everything." Only an install admin changes the class.

### People

The **People** card says what Skald keeps about the people who visit:

- **Keep visitors' IP addresses**: each visit is kept with its IP address, browser, times, pages in order, source, referrer, campaign, country and device. Admins can then look a person up with the search at the top. Three choices:
  - **Full address**: the whole address.
  - **Shortened (last part removed)**: `203.0.113.57` is kept as `203.0.113.0`. Switching from full shortens the addresses already kept at the next nightly run. Switching back to full keeps only new visits in full.
  - **Don't keep**: no address is kept, and the visits already kept with one are deleted at the next nightly run.
- **Visits with addresses**: how many days those visits are kept. The default is 395. When you set it, and it is fewer days than the leads are kept, it is also the most a lead's name and email are kept: after that the lead stays, counted, without them. See [Privacy](privacy.md), "How long a name and email are kept".
- **Leads' names and emails**: **full** keeps a lead's name and email with its conversions; **anonymous** keeps neither.

A new install keeps both. An install that was upgraded from a version before 2.4.0 keeps neither until you turn them on. The field then says "kept off by the upgrade to 2.4.0". Your privacy notice must say what you keep before you turn them on. See [Privacy](privacy.md).

Below the card, **Wording for your privacy notice** gives a short text made from these settings, with a **Copy** button. Fill in the parts in [square brackets]. It is a starting point, not legal advice.

### Leads

The **Leads** card says how long Skald keeps your leads. A lead is a form sent or a call booked.

- **Leads and the pages they read**: each lead, with its name and email (when **Leads' names and emails** is full), where it came from, the pages its visitor ID read, and the leads a sync removed. Two choices:
  - **Kept for good**: Skald never deletes them. Nothing is removed at any nightly run, however old.
  - **N days**: each lead is deleted N days after it came, with its pages. The default is 400 days.
- **Pages of visitors who have not signed up yet**: the pages read with a visitor ID that has no lead, kept for this many days (1 to 400, default 30). Once that visitor sends a form or books a call, all their pages are kept with the lead, for as long as the lead is kept.

What is kept for good:

- the leads, every stage of each (sent, booked, paid, won, lost), and the ones marked test;
- the leads a sync removed (under **Show left out › Removed**);
- the pages read by a visitor ID that became a lead;
- the name and email of each lead (when you keep them), unless you set **Visits with addresses** to fewer days: then they are cleared after those days;
- the raw copy of each hook message, which the second count recounts leads from. So old days still add up.

What still goes: the log of hook deliveries after 90 days, and the pages of visitors who never became a lead, after the days you set.

"Kept for good" means Skald never deletes them by itself. A person's own request to be deleted still works: your server admin runs `skald forget --email ...` (or `--lead`, `--vid`), and everything about that person goes. See [Privacy](privacy.md). Your privacy notice must say how long you keep leads: the **Wording for your privacy notice** card says "until you ask us to delete them" when they are kept for good.

The server admin can set the same from the shell, for one site:

```
skald settings set example.com conversions.retention_days forever
skald settings set example.com journeys.vid_days 400
```

`0` means the same as `forever`.

### Keeping less

Making a window shorter removes stored data, so Skald asks first.

1. Type the new, smaller number (or pick days instead of **Kept for good**) and select **Save**.
2. The page shows what will go: how many rows and days.
3. Type the site's name to confirm, then select **Yes, keep less**. Or select **Keep it as it is**.

Nothing is removed at once. Removal happens at the next daily run. On a site that keeps everything, the page says so instead and nothing is removed.

A change to **Returning-visitor matching** also changes who counts as a returning visitor from then on.

> If your server sells plans, your plan may cap the detail you can keep. The page then says "Capped by your plan".

## Mail & reports

[Mail & reports](#settings/site/mail) (**Settings › This site › Mail & reports**) has two tabs. **Mail**, below, sets the mails Skald sends. **Client reports** ([Client reports](#settings/site/mail?sub=reports)) sends a client their own report: see [Client reports](client-reports.md).

The **Mail** tab has these cards.

### Reports

- **Daily mail**: sent after each morning's run.
- **Weekly mail**: sent on Mondays.
- **Monday marketing mail** (off until you turn it on): last week's visitors, pages read, leads and where visitors came from, then each of your connected tools' own figures, each under its tool's name and never added to Skald's. See [Your own tools](your-tools.md#alerts-and-the-monday-mail).
- **Recipients**: up to 20 email addresses.
- **From name**: the name the mail comes from.

Each new recipient first gets one mail with a confirm link. They get nothing else until they open the link and select the button on that page. The link works once, for 7 days. Until at least one address is confirmed, the reports are held back, not failed. Your own address (the one you sign in with) needs no link. With no mail server set (below), no confirm mail is tried: the Mail page shows **Skald cannot send mail yet** above the recipients, says what is missing and asks **Who will set it up?**, and a saved address is told it gets its link once the mail server is set.

The mails carry figures only, never an address and never a journey. A mail that would include a withheld or partial day is held back.

### Mail server (SMTP)

For install admins. The sender address, server, port, security, user and password apply to every site on the server. The password is write-only: the page only says whether it is set.

### Google PageSpeed

A free API key raises Google's daily limit for the tests on [Site › Speed](#site/speed). It is write-only too.

### Preview the mail

Owners, admins and install admins can see the daily or the weekly mail exactly as this site would send it now: select **Preview the daily mail** or **Preview the weekly mail**. The mail is built from the same checked days, by the same code, and shown on the page with its subject. Nothing is sent, and no mail server is needed. When the mail would not go now (a day held back, a week not whole), the preview says why.

### Send a test mail

Owners, admins and install admins can send a short test mail through the settings above.

1. Type the address in **Send to**. It must be your own address or a confirmed recipient.
2. Select **Send test mail**.

At most 3 test mails in 10 minutes.

### Alerts and failure mail

Alerts always show on [Site › Alerts](#site/alerts) and on the bell in the top bar. They go to confirmed recipients only.

Site › Alerts shows one card per kind of alert, the most urgent first, each with a pill (**Urgent**, **Worth a look**, **For information**). The page, the Site tab's badge and the bell all count the same thing: the kinds that need you (urgent or worth a look), not the number of rows. Fourteen open alerts of three kinds show as **3**.

- **Fix** opens one question, **Who will do it? Me / My developer / My AI agent**. **Me** shows the steps (for a possible exposure, the line for your web server, with a copy icon; for an advisory, the item on Security › Your stack; for a path, its recent requests). **My developer** gives a message to send and a link to this alert. **My AI agent** shows only where the agent kit has the job (logging stopped). Your answer is kept in the address (`alfix=<kind>&by=me`) and remembered for the next time.
- **I have done it** closes the dialog. Skald checks again with every live run, and the alert closes by itself once the problem is gone.
- A kind with nothing to fix (an AI assistant stopped reading pages) has **See the N pages** instead.
- The **?** beside the title says what is watched and how. Alerts closed in the last 30 days are one line that opens to their table.

Admins and owners switch alerts on or off for this site on **Settings › This site › Alerts** ([Alerts](#settings/site/alerts)). The last line on [Site › Alerts](#site/alerts), **Which alerts are on: N of M**, links there, and an older link with `alerts_view=switches` opens it too:

- **The line at the top** says where things stand. On: "16 of 17 rules are checked with every live run, and mailed to the site's confirmed recipients" (or "shown on Site › Alerts, not mailed"). Off: "Alerts are off, so nothing is checked. 16 rules will run when you turn them on."
- **Turn alerts on**, beside the title, only while alerts are off and you may switch them. There is no other button on the page.
- **All alerts**: the switch for every rule. While it is off, nothing is checked.
- **Mail alerts**: off, alerts are only shown on Site › Alerts, never mailed.
- **The rules**, in folds by area: **Site health** (site down, logging stopped, server errors, broken links), **Traffic** (traffic drop, visits from AI answers, first citations), **Crawlers & AI** (crawl bursts, new or silent crawlers, AI reading pages), **Security** (exposures, scan waves, advisories), **Sales** and **Marketing**. Each fold says how many of its rules are on ("3 of 4 on"; while alerts are off, "3 of 4 will run"). A rule is one line: its name, a **?** with what makes it alert, and its switch.
- **Sale** and **Refund on a sale** (off until you turn them on): one alert for each sale or refund the Revenue tab counts, with an optional **Sale alert minimum** per currency (its row opens a panel). See [Revenue](revenue.md#sale-alerts).
- **Marketing**: **A tool stopped answering** (one of your own tools gave no good answer for 26 hours), **Leads dropped** (the last 7 whole days' leads under half of the 7 days before, when those were 5 or more), **Bookings dropped** (the same rule on Calendly's own bookings, when Calendly is connected) and **Google Analytics and the log far apart** (off until you turn it on: Google Analytics' sessions and the log's visits over the same 28 days are 2 to 1 or more apart). The last one never says either count is wrong: they count in different ways, and a large gap usually means a missing tag, a consent banner or a host the log does not see. See [Your own tools](your-tools.md#alerts-and-the-monday-mail).

A change applies from the next live run, within 2 minutes. How much makes an alert (the thresholds) is set in the server's config. A switch the server's config locks says "Locked in the server's config file" and cannot be changed here. Viewers see the switches but cannot change them.

If the morning run fails, the server can send one short failure mail. It goes to the same people as the daily mail: the confirmed recipients on this page, or the server's own list when none is set here or none has confirmed yet. It uses the mail server set on this page or on the server. A day held back because it did not add up is not a failure, so it sends no failure mail.

## Site: names and time

[Site](#settings/site/details) (**Settings › This site › Site**, tab **Names & time**) says what counts as this site. Its other tab, **Internal traffic**, is in [Internal traffic](internal-traffic.md).

- **Host names**: the names this site answers to, such as `www.example.com` and `example.com`. 1 to 50.
- **Views**: page groups, one per line: a name, the path it starts with, and any paths to leave out. Up to 20. They show in the **Page group** list at the top of the **Filters** panel, which reads **All pages** until you pick one. See "Views (page groups)" below.
- **Time zone**: the site's own zone. Days are counted midnight to midnight in it.
- **Logo**: see "Logo" below.

Changes apply from the next run. Days already stored are not counted again, except a new page group's (below).

### Views (page groups)

A page group is a part of your site you want to see on its own, such as the blog or the Canada pages. Each one gets its own pages, with the same figures as the whole site, counted the same way. Pick it in the **Page group** list in the top bar (it reads **All pages** until you do).

Write one group per line: its name, the path it starts with, and any paths to leave out, separated by `|`. Several paths to leave out are separated by spaces.

For example:

- `Blog | /blog/`: every page under /blog/, and /blog itself.
- `Canada | /ca/ | /ca/fr/`: the Canada pages, but not the French ones under /ca/fr/.
- `Security pages | /security/`: every page under /security/.
- `Rest of the site | | /blog/ /ca/`: every page except the blog and the Canada pages.

Paths start with `/` and match the start of the address's path, capital letters counted, never the part after `?`. Up to 20 groups.

**What fills automatically.** A new group counts from the next run. Its past days are filled from the server's raw log: under the Views box, **Fill past days for the new groups** is ticked. Press **Save** and Skald counts the new or changed groups again for every whole day the raw log still holds, in the background. The box below shows how far it is: "Filling 9 days… 4 of 9", then "Done: 9 days filled, all audited". Each day is checked by a second, separate count, as every stored day is; a day where the two disagree is held back and not shown. Untick the box and Skald offers the same with a **Fill past days for the new groups** button instead. One fill runs at a time on a server; owners and admins can start one.

**What cannot be filled.** The raw log keeps only the last days, 14 on most servers. The box says so: "Days before 13 Oct can't be filled: the raw log is kept 14 days." In the group's pages those earlier days show as **not recorded for this group**, never as 0.

A renamed group counts as a new one. A removed group leaves the **Page group** list; nothing needs counting again.

### Logo

Each site shows its own logo: on the page where you choose a site, in the menu's site button, in the site switcher and on the browser tab. The card shows it at those three sizes, and what Skald found on the site.

Choose where it comes from:

- **From the site (automatic)**: Skald asks your site itself for its app icon, then its favicon. It never asks an outside icon service. It asks again once a week. **Check the site again now** asks at once.
- **Upload my own**: a PNG, SVG or ICO file, square, at least 64 x 64 pixels, at most 256 KB. An SVG that could run a script or load something from elsewhere is refused; save it again as a plain drawing, or upload a PNG.
- **A letter on a colour**: the site's first letter on one of four colours. Skald also shows this while there is no logo.

Press **Save**. Owners and admins can change the logo; everyone else sees it.

## Data

[Data](#settings/site/data) (**Settings › This site › Data**) is how this site's visits reach Skald, and what counts. It has four tabs:

- **Send logs**: sending this site's visits to Skald from another server or platform, with your AI agent or by hand. See [Connections](connections.md). It also has the **Log file**: the log folder and file name, for install admins.
- **Script tag & goals** ([Script tag & goals](#settings/site/data?sub=script)): the tag to copy into every page, its visitor IDs (and sharing them across subdomains), and the **Goals**: the page events that count as this site's goals, such as Sign-up sent or Demo booked. Tick up to 10. The events your site has already counted are listed first; the others are under **Not counted yet**. See [Tracking script](tracking-script.md) and [Funnels and goals](funnels-and-goals.md).
- **What counts** ([What counts](#settings/site/data?sub=counting)): the **Page assets**, the folders your pages load their own files from (without them nobody counts as a person); **Not forms**, the addresses your pages post to by themselves, which are not a form someone sent (see "Not forms" below); and the **Not pages**: machine addresses that are never a person reading a page, such as feeds and WordPress's API. See "Not pages" below.
- **Test a sample** ([Test a sample](#settings/site/data?sub=sample)): paste a few lines of a log and Skald says what it would count. See [Connections](connections.md#test-a-sample-of-a-log).

Changes apply from the next run. Days already stored are not counted again.

### Not pages

Some addresses answer like a page but nobody reads them: a feed for feed readers, WordPress's API, a Markdown copy of a page that an AI agent fetches. Skald does not count a request for one as a page view, on every site. The request still counts as a request, in its usual group (people, bots and the rest), so the groups still add up to the log. It is left out of page views, visitors who read a page, landing pages, exits and journeys.

The list, each one ticked by default:

- **markdown**: a Markdown copy of a page (`/docs/index.md`, `.mdx`, `.markdown`). People read the page itself; tools and AI agents fetch the copy. AI fetches of it still show under **What they fetch** on AI & bots, as Markdown. If you publish `.md` copies for AI on purpose and want them in the pages' AI columns, untick it.
- **wp_rest**: WordPress's API, `/wp-json/` and `?rest_route=`.
- **wp_files**: WordPress's machine files, `xmlrpc.php`, `wp-cron.php` and `admin-ajax.php`.
- **feeds**: feeds, `/feed/`, `/comments/feed/`, `/feed/atom/` and `?feed=`.
- **oembed**: `/oembed/`, what another site asks for to embed a link.
- **trackback**: `/trackback/` and `wp-trackback.php`, notices one blog sends another.
- **author_number**: `?author=2`, a lookup that lists a WordPress site's user names.
- **reply_to_comment**: `?replytocom=`, WordPress's reply link for browsers without scripts.
- **sitemap_page**: an HTML sitemap page, `/sitemap/`, `/site-map/`, `/html-sitemap/` and `/sitemap.html`. Crawlers, link checkers and test browsers walk it; people find pages through the menu and search. Its visits show in Site health › Data quality, not in the pages.

**Count one as pages again.** If your site serves a real page at one of these, for example a page called `/feed/`, untick it and press **Save**.

**Add your own.** Under **Also not pages**, one per line, up to 20:

- `/status`: that path, with or without a slash at the end.
- `/preview/*`: every path that starts with `/preview/`.
- `?preview`: every address with `preview` in its query, such as `/?preview=1`.

Capital letters do not matter. `/` alone is refused: it would take every page out.

**What stays a page.** Pages a person opens are never on the list: search results, a cart or checkout, a sign-in page, an app's dashboard, a thank-you page. If one of them is filled by a bot, that is a question of who visited, which Skald answers by itself; add it under **Also not pages** only if you never want it counted.

**Where you see it.** [Site health › Data quality](#site/quality) shows each day's **Not counted as pages**: the requests, how many were people's, and which entry (hover the number). In [Requests](#site/requests) such a request says "a machine address, not a page" and names the entry.

A change counts from the next run. Days already stored keep their figures until the server recounts them (`backfill --days N --force`).

### Not forms

A visit **sent a form** when it sent something to your server (a POST): a contact form, a sign-up, a search box that posts. But many pages also post by themselves, a few seconds after they open, with nobody doing anything: an analytics or event script, an error report. Counted as forms, nearly every visit "sent a form". On one site, each page sent `POST /api/events` four seconds after it opened, and 29 of 34 visits on one day read "sent a form".

So these are **not** forms, on every site:

- **Skald's own endpoints**: the script tag's events (`/traffic-beacon`), hooks and log upload.
- **A POST answered 204 with no body.** A real form gets a page or a redirect back; an empty 204 is a beacon.
- **Well-known beacons**: `/api/events`, `/api/event`, `/api/analytics`, `/api/collect`, `/api/track`, `/api/sentry…`, `/monitoring`, `/_vercel/insights/…`, `/_vercel/speed-insights/…`, `/cdn-cgi/rum` and `/ingest/…`. The card lists them under **Never forms on any site**.
- **Your own list**, under **Sent by the site's own pages, not forms**.

Everything else stays a form, for example `/contact` or `/api/contact`. WordPress's `admin-ajax.php` stays a form too, unless it was answered 204: its heartbeat cannot be told from a real form in the log.

**Suggested from your log.** Skald suggests a path when most page views send it: on 3 of the last 14 days, at least half of the visits that sent a POST sent it, and so did at least a fifth of all visits, and it was answered without an error. Each suggestion says its figures. Press **Add** next to it, then **Save**. Skald never adds one by itself: if a suggested path is a real form (a site whose only POST is its contact form, say), leave it. The doctor names a suggested path once too. To add one by hand, type `/path` (that path, with or without a slash at the end) or `/prefix*` (every path that starts with it) and press **Add**. **Remove** takes one off. Capital letters do not matter. Up to 20.

**Where you see it.** In a visit, **sent a form** now means a real form. In [Requests](#site/requests) a skipped POST says "sent by the page's own script (not a form)". The request still counts as a request, in its group, and in Site health's server requests; only **Form posts** and **sent a form** leave it out.

**Days stored before.** A day counted before this rule may still count a page script's POST as a form. The server recounts each day its raw log still holds (`backfill --days N --force`). A day older than the log keeps its old count, and the page says so: **Form posts** says how many days of the range were counted before, and such a visit says it "sent a POST, counted before the page's own script was told from a form".

## Sites

[Sites](#settings/org/sites) (**Settings › Organisation › Sites**) lists your organisation's sites. If your server offers it, an admin adds a site here with **Add a site**, in two steps. **Your site**: the address, which organisation it goes in, who will use it (they are invited once the first data arrives) and who will connect it (me, my developer or my AI agent). **Connect it**: that path only, with **Live progress**, which ticks itself as each part works, and **Check now**. Skald finds the rest, and asks for proof that the domain is yours only when the server needs it. You can stop at any step and continue later. Each site's row says **Waiting for data** or **Receiving data**. A site not finished shows **Finish setting up**; a finished one that has received nothing for a day shows **No visits yet: test the connection**. See [Connections](connections.md), "Add a site, step by step".

A new site gets a page at once, with a short "Getting ready" note until its first figures arrive.

### Pause, remove or delete a site

Each site has a **⋯** menu at the end of its row. Every choice opens a short dialog that says what happens, what stays and how to undo it. The address names the open dialog, so you can send someone the link.

| Choice | Who | What happens | What stays | How to undo |
| --- | --- | --- | --- | --- |
| **Pause** (start here) | Owner or admin | Skald stops collecting and counting the site. Its log endpoint asks the shipper to wait, so the shipper keeps its lines. The daily and live runs skip the site. The site shows **Paused since** the day you paused it. | Everything: history, settings, tokens, set-up, dashboard. | **Resume**, in the same menu. |
| **Remove** | Owner, typing the site's name | Skald stops processing the site and hides it from the dashboard and the site switcher. Its log endpoint refuses new lines. | All of its data. | **Restore**, under **Removed sites** on the same page. |
| **Clear data** | Owner, typing the name and ticking a box | Skald deletes the site's collected data: its day history, the log lines it holds for it, its leads, sales and conversions, its AI answer runs and today's live figures. | The site, its settings, page groups, funnels, webhooks, tokens and set-up. Collecting goes on. | No undo button: see "The archive" below. |
| **Delete all data** | Owner, typing the name and ticking a box | Skald deletes everything it keeps for the site: day history, the log lines it holds, leads, sales and conversions, AI answers, settings, tokens (they stop working at once), its dashboard folder, its logo and its set-up links. | A site made here is gone; its name can be added again after 30 days. A site from the server's config file keeps its entry there and becomes **Removed**, with no data. | No undo button: see "The archive" below. |

**Pause first.** If you only want a break, or want to test something, pause the site. Nothing is deleted.

**The days in between.** Days while a site was paused or removed, and the days before you cleared its data, read **Not recorded**, never 0. When you resume, Skald says in plain words whether those days can still be filled:

- a site that sends its log with the shipper: the shipper kept its lines and sends them now; an install admin can then count those days with `skald --site <site> backfill --days <n>`;
- a site that sends its log by a log drain (Vercel, Netlify): the drain does not keep lines it could not send, so those days stay Not recorded;
- a site whose log is on the Skald server itself: Skald says which of those days the log still holds.

After **Clear data**, the days before the clear are never counted again, even when the web server's own log still holds them.

**The archive.** Before **Clear data** or **Delete all data** deletes anything, Skald writes one archive of everything it is about to delete into the install's backups folder (where `skald backup` writes), and shows you its path. The archive is kept 30 days. Skald has no one-step restore from it: within those 30 days an install admin can copy data back from it by hand. Secrets such as hook signing keys are deleted and never put in the archive.

**The install's main site** (the one the server's config file is for) can only be paused here. Removing it or deleting its data is done on the server.

Every choice writes one line in the [Audit log](#settings/org/audit): the site, who did it and, for a clear or a delete, the archive's file name.

The same choices exist for an install admin at the server: `skald site pause|resume|remove|restore|clear|purge <site>`; `remove`, `clear` and `purge` need `--yes`.

## Crawler rules

The rules for AI crawlers are not in Settings any more. They are on [AI & bots › Crawler rules](#ai/rules), next to the crawlers they apply to. Old links to Settings › AI crawlers open that tab.

Crawler rules lets each AI company's crawlers in, or keeps them out. If your server offers it, each company has three choices:

- **Allow**: every crawler of that company may read the site.
- **Block training only**: crawlers that collect for training are kept out. AI search and answers to people's questions still reach the site.
- **Block**: every crawler of that company is kept out.

Each crawler can also be set on its own: **As** the company, **Always allow** or **Always block**. Beside each one is how often it was refused in the last 30 days.

Select **Save**. The tab says "Saved. Being applied to the site..." and then "Live on the site" within a few seconds. **Undo changes** puts back what was saved before.

A blocked crawler gets a refusal before the page is served. Some crawlers cannot be told apart by the server: they are marked "robots.txt only", and only a line in your robots.txt can ask them to stay away. The tab suggests the lines to use, with a **Copy** button. Under the rules, your site's robots.txt is shown beside each crawler. Skald never writes your robots.txt.

These rules apply to every site on the server, so only an install admin may change them.

### Suggested llms.txt

[AI & bots › llms.txt](#ai/llms) shows **Suggested llms.txt**: a file you can publish at `/llms.txt` on your site. It follows the format at llmstxt.org: your site's name, a one-line summary, then links to your pages, grouped by section, so an AI assistant knows which pages matter.

Skald picks the pages people and AI assistants read most over the last 90 days. Only recorded days count; any day left out is named. It leaves out private pages (sign-in, account, cart, search, admin), pages your robots.txt keeps crawlers from, redirects, and pages that are gone. With your website's page list, each link has the page's title; without it, the link is named by its path.

Write the summary line yourself and check the links. Then select **Copy** or **Download** and publish it on your site. Skald never writes it to your website. Your server admin can also print it with `skald llms-txt`.

## Sign-in rules

[Sign-in rules](#settings/org/people?sub=security) (**Settings › Organisation › People › Sign-in rules**) sets the sign-in rules for everyone in the organisation. Only an owner may change them.

- **Require two-step sign-in**: members without it set it up the next time they sign in. Turn it on for your own account first.
- **Session length**: how long a sign-in lasts at most, 1 to 90 days. The default is 14.

## Audit log

[Audit log](#settings/org/audit) (**Settings › Organisation › Audit log**) shows who changed what, and when, newest first: settings, the team, tokens, sign-ins and failed sign-ins. Admins may read it. Viewers cannot.

- Pick one kind of change in **Action**, or keep **Every action**.
- Select **Download CSV** to keep a copy.

No password, token, link or address is ever written to the log. Each person search is written too (`people.search`): what kind of value was searched and a one-way code of it, never the value. So is each conversion marked test or not (`conversions.test`, `conversions.untest`). Install admins see every organisation's rows.

## Billing

[Billing](#settings/org/billing) (**Settings › Organisation › Billing**) shows only on servers that sell plans, to owners and admins. Admins can read it; only owners can choose a plan or change the payment. Other servers say "This server does not sell plans."

- **Your plan**: its name, status and trial days left.
- **Requests this month** as a bar, with marks at 80%, 90% and 100% of what the plan allows, and the day the count starts again.
- A table of use against the plan's limits: sites, requests this month, members and days of detail kept.
- **Plans**: select **Choose** and a plan's name to buy it.
- **Manage billing**: card, invoices and cancelling, on the payment provider's own page.

"Requests this month" counts every request the server logged for your sites, people and machines alike.

### Usage alerts

So that no data is lost, Skald warns before your requests run out. When this month's requests reach **80%**, **90%** and **100%** of your plan, every owner and admin gets one mail. It says how many requests are used, of how many, and the day the count starts again, with a button to Billing. From 80%, owners and admins also see a line at the top of every page, with a link to Billing. Viewers get neither.

You get each mail once a month. If the count jumps past two marks at once, you get one mail, for the higher one. After you choose a bigger plan, the mails start again from the new plan's marks.

Past 100%, Skald turns new log lines away until the month turns or you choose a bigger plan. Skald's shipper keeps them and sends them again later. Lines sent by a Cloudflare Worker are lost. The count includes the days stored so far; today is added after it ends.

Whoever runs the Skald server can switch these alerts off (`saas.usage_alerts: false`).

If your organisation goes over a limit, every page shows a banner. Nothing is deleted. If a payment is overdue, the organisation becomes read-only: you can still read every page, change your own account and pay, but not change settings or the team.

## Related guides

- [Getting started](getting-started.md)
- [Privacy](privacy.md)
- [FAQ](faq.md)
