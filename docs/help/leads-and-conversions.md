# Leads and conversions

Where Skald's leads and conversions come from, what the **Leads & sales** section shows, what "abandoned" means, and how to see every lead and conversion the figures leave out. The **Leads** tab lists every lead of a period, one row each; owners and admins see each lead's name and email there, when your site keeps them.

## Leads & sales: four tabs, one period

Everything about results sits in **Leads & sales** in the menu. Each tab answers one question, written under its title, and has the same shape: one row of options, at most one row of numbers, then one main table or chart. The period is the one in the top bar, the same on every tab. A small **i** beside a title or a number says what it counts; **Learn more** opens this guide at the right part.

| Tab | The question it answers |
| --- | --- |
| [Leads](#sales/leads) | Who are my leads? One row per lead: when, who (name and email, owners and admins), what they did, its stage now, where it came from. Pick **What: Demos** for the calls booked, step by step. Owners and admins find one person with the box at the top |
| [Summary](#sales/summary) | How many leads came in, where from, and is it better than before? The figures, each kind of lead, and where they came from |
| [Revenue](#sales/revenue) | Which sources, pages and campaigns made money? Sales with a value, per currency, refunds taken off, new customers, renewals and lifetime value. See [Revenue](revenue.md) |
| [Funnels](#sales/funnels) | Any series of pages and events. See [Funnels and goals](funnels-and-goals.md) |

**Where the old tabs went.** Leads & sales had eight tabs until it was made simpler. Every old link still opens the same view:

- **Sources** is the **Where they came from** part of Summary. An old Sources link opens Summary with that part open.
- **Calendar bookings** is the Leads tab with **What: Demos** (or the booking the link named). Its steps (opened the booking, booked, cancelled, no-show, won) show above the list, and its **Show left out** lists are under Leads' **More > Show left out**.
- **Events** moved to [Traffic > Events](#traffic/events): what visitors did inside your pages is about visits, not leads.
- **Find a person** is the search box at the top right of Leads (owners and admins). It is also the first result in **Search or jump to** at the top of every page.

Older links keep working too: `#sales/pipeline`, `#leads` and `#conversions` open Summary.

### One period on every tab

Leads & sales opens on the **last 7 days** when the link names no period. Pick another in the top bar (or **All time**) and it stays while you move between the section's tabs. Every tab reads the period the same way:

- **7, 30 and 90 days include today.** 7 days are today so far and the 6 whole days before it: 7 calendar days. The heading gives the dates from and to, for example "Last 7 days: Fri 16 Oct to Thu 22 Oct (today, so far)"; the year shows only when the days cross into a new year. Today's part is marked **live**.
- **All time**, and a custom period that ends today, include today too. **Yesterday** is that whole day. **Today** is today so far.
- **Each figure is counted twice.** The 7, 30 and 90 days are counted again in one go from the stored leads, by a second road. A Leads figure that does not agree with it is withheld, with one line why, until the next count agrees. Today's part is checked again once the day is whole.
- **The change compares like for like.** Today is not over, so the period before is counted to the same hour: its whole days, then its last day up to the time it is now. For example "25% more than the 7 days before (4 leads: Fri 9 Oct to Thu 15 Oct, up to 14:00 EDT)". A part of a day is never compared with a whole one. With a **Label**, or a source, country, device or campaign filter on, no change is shown (the day cut to the hour is counted by kind of lead only), and the line says so. **Compare with…** is off by default here, because every period holds today so far.

### Leads only

A **lead** is a form sent (contact, sign-up, early access, trial) or a demo booked, once completed, from every road: the lead database, the booking tools, the page's script tag and your site's server. Every figure called Leads in this section counts exactly that, never a button click, a phone or email click, a payment or a page view. So the Leads tab's count and Summary's **Leads** tile are the same number for the same period, and Overview's **Leads** tile is the same number on the same days.

### The completion rate

A completion rate is completions out of starts. Only the page's script tag sees a start (a form field used, a booking widget opened), so a rate is shown only where the completions came from the script tag too. Where some came from a booking tool, your site's server or the lead database, the rate says **not comparable**, and its **i** says why in one line: putting 84 sign-ups from your server over 25 starts the script saw would give a rate that means nothing. Under 10 starts it says **too few to say**. This is the same on Summary's table and on Leads' booking steps.

### The Leads tab

[Leads & sales > Leads](#sales/leads) lists every lead of the period, newest first: when it came in; the name and email (owners and admins only, and only when **Leads' names and emails** is **full**, in **Settings > This site > Privacy > People**); what they did (a sign-up, a contact form, a demo booking), with its label; its stage now (completed, won, lost, cancelled, no-show); where it came from (**Lead database**, a booking tool, the page's script tag, or your site's server); the source of the visit it came in on and the first source the browser remembered; the landing page and the country. A row opens the visitor drawer with the lead's steps and pages; owners and admins also see **Their profile** there: who, everything they did and their visits, newest first (see [Finding one person](leads-and-conversions.md#finding-one-person)).

- **Reference.** Each lead carries the ID the sender gave it: your site's own account ID (`u-119797`), a booking's address at Calendly. Turn on the **Reference** column under **Columns** to see it; the search box finds a lead by it either way, and the CSV export always holds it. The copy icon beside it copies the whole ID, so you can find the lead in your own admin. The lead's drawer shows it too, with where it came from ("Reference: u-119797 (from example.com's server)") and every step of that reference, oldest first. Everyone who can see the leads sees the reference: it is your system's record number, not a name or an email. One exception: a lead the page's script tag reported has a reference made from the browser's visitor ID, so only owners and admins see that one.
- **Today so far.** A line under the count says how many of the period's leads came in today ("Today so far: 2 of these 5 leads"), with **Show today (live)** for today alone. Today's leads are in the list, newest first, each with a small green **live** dot.
- The count above the list is the **Leads** figure itself, the same as Summary's on the same period, with the change against the period before, and what is applied: "5 leads · filtered: Source = Search engine". The list never makes a count of its own. The CSV export is named after the period's days, for example `leads-2026-10-16-to-2026-10-22.csv`.
- **One filter row.** **What**, **Label**, **Stage now** and **Source** narrow the list; under **More**, **Show left out** adds the test, spam and duplicate leads, marked, never counted, and lists the tools' cancelled, removed and test conversions under the leads (see [Cancelled, removed and test](leads-and-conversions.md#cancelled-removed-and-test)). The top bar's **Filters** apply here too, for what a lead carries: its source, country, device and campaign. Every filter that is on, from either place, is one chip in the **Filtered by** line under the row; its **×** takes it off, and **Clear all** takes them all off. A top-bar filter a lead does not carry (a page read, a browser, a referring site) shows greyed, with the reason, and is not applied.
- **What: Demos** (the old Calendar bookings). Above the list, each step of the bookings in the period: **Opened the booking**, **Chose a time**, **Booked**, then **Cancelled**, **Rescheduled**, **No-show**, **Won** and **Lost**, only the steps your site has ever sent, with "booked of opened" under the completion rate rule above. A line says which tools reported them (Calendly, Cal.com, the script tag). With no booking tool connected, it says so and shows how to connect one. Summary's **Demos booked** tile links here with **Each step ›**.
- **Find a person.** Owners and admins type an IP address, an email, a lead or a visitor ID in the box at the top right and press **Find**: the person's visits, leads and conversions open in the drawer (see [Finding one person](leads-and-conversions.md#finding-one-person)). Other members and the demo see no box.
- The count follows the filters: What, Label and one of source, country, device or campaign narrow the Leads figure itself. Two of those at once (say a source and a country), a label with one of them, **Stage now** or **Show left out** cannot be counted as the figure, because the figure keeps each breakdown on its own; the line then counts the rows listed ("8 listed"), beside the period's figure, and says why.
- **A period with no lead** says where the leads are: "No new leads in the last 7 days, Fri 16 Oct to Thu 22 Oct (today, so far). 5 leads in the last 30 days, Wed 23 Sep to today.", with **Show last 30 days** and **All time**, or the leads since the first day when the last 30 days hold none. Both counts are the same Leads figure over those days. With no lead at all it says **No leads yet** and how to connect a source of leads.
- The search box, **Columns** and **Export** work as on every table. The Leads table has no **Filter** button of its own: the row above it is its filter row.
- The same leads come in four shapes, picked with the small buttons at the right of the options: **List**, **Board** (a column per stage now: new or open, won, lost, cancelled or no-show; read-only, because stages come from your tools), **Timeline** (leads per day, split by what they did or by source; press a day to list its leads) and **Map** (leads by country). The timeline and the map draw the Leads figure itself, so they always agree with the count. They count a lead when it came in, so **Stage now** and **Show left out** are greyed there; the map counts by country alone, so a source, device or campaign filter is greyed on it, and with a label on it says the map is not split by label.
- Every load that shows names and emails is written to the audit log as "lead list viewed", with the period and the number of rows, never a name or an email. Members who are not owners or admins see the same list without names and emails.

### Summary

[Leads & sales > Summary](#sales/summary) answers "How many leads came in, where from, and is it better than before?", top to bottom:

- **The figures.** **Leads** (the same number as the Leads tab, with the change against the period before) and, once the site has sent a sale with a value, **Sales**: how many sales in the period and their value, per currency, less refunds (the same figures as [Revenue](revenue.md)). **Demos booked** shows only on a site with a booking tool or a demo booking, with **Each step ›** to Leads > What: Demos; **Won** and **Lost** only on a site whose team or CRM has ever marked a lead won or lost. A line under them says how many of the leads came in today.
- **Each kind of lead.** A row per kind: **Completed** (each lead once: a sign-up that later paid is one completed sign-up), and, once the site has a sale, **Sales** and **Value** (the sales of that kind in the period and their value less refunds; a sale belongs to the lead it was paid for, so a sign-up that paid shows its sale on the Sign-ups row). **Started**, **Abandoned** and **Completion rate** show only on a site whose page script records starts; **Cancelled or no-show**, **Won** and **Lost** only on a site that has sent them.
- **Where they came from.** The five sources that sent the most leads, then one fold, **Every source, touch and time to convert**: the leads by source, first touch, campaign, landing page, country, device and the tool that reported them; first, last and assisted touch; likely from AI assistants; and the time to convert (see [Summary, part by part](leads-and-conversions.md#summary-part-by-part)). An old **Sources** link opens Summary with this part first, under the figures, its fold open.

Two options narrow what you see, and the address keeps them, so a link or a reload opens the same view:

- **What**: one kind of lead, for example Demo booking or Sign-up.
- **Label**: one label your site's server sent with its leads, for example a contact form's topic: sales, support or partnership (see [Send leads from your backend](leads-from-your-backend.md)). **Each kind of lead** then counts only the leads with that label. Where they came from, the touches, the time to convert and the sales are not split by label, so they are left out while a label is chosen. The lists of conversions show each lead's label as a small tag.

Summary has no **Count from** any more: it counts the leads one way, the same as the Leads tab, so the two never show two numbers for the same days. An old link that asked for the lead database's view opens Summary itself.

## Leads on every page

Leads and demo bookings also show where you look at your visitors, so you can see which source, page or country brings them. All of these count the same leads as Leads & sales, from every road at once.

A **lead** here is a form sent (contact, sign-up, early access, trial) or a demo booked, once completed. **Demos booked** are counted on their own as well. Payments, deals and clicks are not leads. A conversion marked test is never counted.

| Tab | What you see |
| --- | --- |
| [Overview > Summary](#overview/summary) | The **Leads** tile for the period, with the change against the period before. It says which count it is ("Leads only", or "From the lead database" on a site with no tools file) and links to Leads & sales > Summary, which counts the same leads. Overview's 7, 30 and 90 days are whole days up to yesterday unless **Include today** is on, so on the same days the figures agree. Pink dots on the main chart: each day's leads. |
| Overview > Summary, with **Today** (live) picked | The **Leads** tile for today so far, against yesterday up to the same time of day ([vs yesterday at this hour](real-time.md#vs-yesterday-at-this-hour)), and **What converted today**: each completed form and demo booking with its time, what it was, the page, the country with its flag, and where it came from (and where the visitor first came from, when that differs). A link opens all of today's on Leads. |
| [Traffic > Sources](#traffic/sources) | **Leads** and **Lead rate** beside each source's visitors. |
| [Traffic > Pages](#traffic/pages) | **Landing pages, with leads**: visitors who started on each page, its leads and lead rate. |
| [Traffic > Places & devices](#traffic/places) | **Leads** and **Lead rate** beside each country. |
| [Overview > Insights](#overview/insights) | Findings about leads, for example "Leads from AI assistant up 60% week on week" or "/pricing/ is the page that started the most leads". |

With **Compare with…** on, the Traffic grids add the other period's visitors and the change; their lead columns stay the period in the top bar's.

Which touch each column uses:

- **Sources**: the last touch, the source of the visit the lead was sent from.
- **Pages**: the landing page recorded with the lead (its first visit's, when known).
- **Places & devices**: the lead's country, from the tool or the visitor's address.

The honesty rules are the same as everywhere:

- Only days with **checked** conversions count. A day the second count disagreed on is withheld. A day before conversions were recorded is "not recorded", never zero.
- The **lead rate** is leads per visitor over the same days only: days whole in the visitor figures *and* checked in conversions. It is given over at least 10 visitors. Below that you see the count alone, with "too few to say".
- A **change** (Overview, Compare with…) is shown only when both periods are whole and every day of both has checked conversions.
- **Insights** about leads follow the same rules as the others: two whole periods, at least 5 leads, a change of at least 20%. A finding the second count does not confirm is left out, and the tab says so.
- Leads are counted for the whole site. On a page group (for example one language), the lead columns are not shown.

> A lead reported by two roads (for example the script tag and the lead database, for the same form) counts on each, as on Summary. A lead that arrived from two tools with the same reference (for example the lead hook and Zapier, or a hook and the lead database) is flagged as "One lead, two tools" under **Settings > This site > Leads & tools > Incoming hooks > Status** and by the server's doctor command. The script tag's own rows are not part of that check.

## When a page says "not connected yet"

A page that is empty because its source is not connected says so, and shows how to connect it, instead of an empty table. This is the same card on every page: Leads (and Leads with **What: Demos**, for the booking tools), Revenue, Traffic > Events, Funnels (a step that needs the script tag or a lead source), Traffic > Search, Overview's **From your tools** and Traffic > Visitors' **Recorded by your site**.

The card says:

- **What the page needs**, in one line. For example: "Leads need a source: your forms, your booking tool or your site's server telling Skald about each one."
- **Skald found on example.com**: what Skald saw when the site was added (the site check in [Add a site, step by step](connections.md#skald-checks-your-site)): how the site is built and where it runs, how many forms the home page has, and the tools it names, such as a Calendly link, the Google Analytics tag, Stripe or HubSpot. Nothing new is fetched from your site for this.
- **Recommended**: the one way that fits your site. A Next.js site on Vercel reads "Your site is Next.js on Vercel: send leads from your form's server action with the signed lead hook." A WordPress site gets the plugin; a site on Wix, Squarespace, Webflow or Shopify gets Zapier or Make, no code.
- **Connect**: opens that set-up dialog, which asks **Who will do it?** (Me, My developer, My AI agent) first. **Other ways** lists the rest, and **Every source** opens Settings > This site > Leads & tools.

A page that gets some of its data but not all says what is still missing, for example "Leads arrive from Calendly; your forms are not connected.", with its own **Connect**.

Only owners and admins can connect a source. Anyone else reads **Ask an admin to connect it**, with the link to the set-up dialog and its copy and open icons: send it to an admin, and it opens the same dialog for them.

AI answers are different: they stay off until someone adds a provider key, because each question costs money. Their page shows that they are off and the four steps, not a Connect button.

Each Leads & sales tab, Search and Overview's **From your tools** also has a small **Sources: Leads & tools** link in its head (owners and admins). It opens Leads & tools at the group that feeds the page. Site > Alerts says when an alert that is switched on can never open because its source is not connected (a sale alert with no payment source, for example).

## Leads & tools: what to connect next

[Settings > This site > Leads & tools](#settings/site/leads) (owners and admins) starts with **Next step for example.com**: what Skald found on the site, and the single most useful thing to connect, with one **Connect** button. A source that stopped working comes first ("Stripe is not working ... Fix it"). Then the Leads source, a booking tool when your site links one, Stripe when your site uses it, Search Console, Google Analytics when its tag is on your site, and the script tag. **Connect everything left with your AI agent** gives your agent one line for every tool left. When everything that fits your site is connected, the card says **All connected**, unless a check below needs a fix (say, leads that came without the visitor's address): then it says **1 to fix** and the red **Needs a fix** line under it says what and has **Fix**.

Below it, every source is in a group by what it is for, each with one line on why:

| Group | Sources |
| --- | --- |
| Leads from your forms | your site's server (the lead hook), Zapier, Make or n8n, Typeform, HubSpot, the script tag |
| Bookings | Calendly, Cal.com |
| Payments | Stripe |
| Search | Search Console & Bing |
| Your own tools | Google Analytics and the others |
| Recorded journeys | your site's own sessions, after consent |
| Send each lead out | webhooks to your CRM, Zapier or Slack |

Each row has a pill: **Connected**, **Waiting** (set up, nothing real arrived yet), **Failing** or **Not connected**, when it last sent something, and one button: a connected row opens its details, one not connected has **Connect**. A connected row also links to the page with its data: **See leads**, **See bookings**, **See revenue**, **See searches**, **See on Overview**, **See journeys**.

Sources that do not fit your site (Stripe when the site check saw no Stripe, Cal.com when it saw a Calendly link) fold under **More you can connect**. They still work the same when you need them.

The address keeps where you are: `#settings/site/leads?lt=bookings` opens the page at Bookings, `tool=calendly` opens Calendly's details (`&how=paste` with its question answered), and Connect adds the dialog's own key, such as `setup=lead&way=calendly` (the lead hook's dialog with Calendly picked).

## Where leads and conversions come from

There are four sources. You can use one or all of them.

| Source | What it gives | Shown on |
| --- | --- | --- |
| Your website's lead database | every lead, its kind, its status, first and last touch | Leads; Summary |
| Your site's lead push (the `lead` hook) | a lead your own server reports the moment it is made | Leads; Summary |
| Webhooks from your tools | bookings, cancellations, no-shows, form answers, payments, CRM deals | Leads (What: Demos for the bookings); Summary; Revenue |
| The `skald.js` script tag | forms started and sent, booking widgets opened and booked, phone and email clicks | Leads; Summary; Traffic > Events |

### The lead database

If your website keeps its leads in its own database, the person who runs your Skald server can point Skald at it. Skald opens it read-only and never changes it. Every few minutes it reads the leads that changed.

- Leads marked `spam` or `duplicate` are left out of every count, and counted apart. They are listed in full on Leads, under **More > Show left out**.
- A lead's status (new, contacted, qualified, won, lost) is read as it is now. When your team changes a status, past days change with it.
- Names and emails are read and kept only when **Leads' names and emails** is **full** (Settings > This site > Privacy > People). Owners and admins then see them on Leads, in the person search and in the left-out lists. See [Privacy](privacy.md).

### Your site's lead push

Your site's own server can tell Skald "a lead was made" with a signed message. See [Webhooks](webhooks.md), section "Your own site's lead push".

### Webhooks from your tools

Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier and Make can send Skald a signed message for each booking, form or payment. This is how Skald learns about cancellations, no-shows and payments, which the page itself never sees. See [Webhooks](webhooks.md).

A tool's row says **Connected** only once a real delivery from it was taken in since its key was saved. A passed **Test Skald's address** is not enough: Skald signs that sample with the key it holds, so it proves only Skald's address. While every real delivery since the key was saved was refused (its signature did not match, or it had none), the row says **Failing**, and the tool's details say why in plain words, with the fix. Each tool's key has the tool's own name (Calendly's **signing key**, Stripe's **signing secret**, HubSpot's **client secret**), and the details say when it was saved and by whom. See [Webhooks, The key](webhooks.md#the-key).

### The script tag

One line on every page lets Skald see what happens inside the page: a form started, a form sent, a booking widget opened and booked. Only the script tag can see a *start*, so only it makes "abandoned" possible. See [The tracking script](tracking-script.md).

## One name per action

Whatever reports it, an action gets one name, so the same thing is never counted under two names.

| Action on the page | Means | Reported by |
| --- | --- | --- |
| Demos | a demo or meeting booked | Calendly, Cal.com, HubSpot meetings, the script tag, the lead database |
| Contact forms | a form sent | the script tag, Typeform, HubSpot contacts, the lead database |
| Sign-ups | a sign-up form sent | the script tag, the lead database |
| Early access | an early-access or waitlist form sent | the script tag, the lead database |
| Payments | a Stripe Checkout paid | Stripe |
| Deals | a HubSpot deal moved to won | HubSpot |
| Phone clicks, Email clicks, Button clicks | a `tel:` link, a `mailto:` link or a marked button clicked | the script tag |

Each action has a *stage*: started, completed, paid, cancelled, rescheduled, no-show, won or lost.

### A lead counts once, even when it is won or lost later

A lead is counted once, on the day it was completed: a form sent, a demo booked (or a payment made). When your team later marks it **won** or **lost**, in your lead database or through your tools, it is still that one lead, on that same day:

- the outcome never adds a second lead and never takes the first one away;
- the day the outcome arrives counts no lead for it;
- won and lost are shown apart, as outcomes: **Won** and **Lost** on Summary, **Stage now** on Leads, and the **Won** step of Leads > What: Demos;
- a "won" or "lost" for something that was never completed is not a lead.

This is the same on Overview's **Leads** tile, the daily and weekly mails, client reports and Leads & sales. Only spam and duplicates are taken out of the leads.

## Summary, part by part

[Leads & sales > Summary](#sales/summary) counts the leads from every road at once. If nothing is set up yet, the tab says what to connect, with **Connect**.

### Each kind of lead

One row per kind of lead, with these columns:

- **Started**: starts seen by the script tag. "not seen" means no start was reported, for example a kind only a tool reports.
- **Completed**: completed and paid together. A lead that sent both counts once.
- **Abandoned**: see below.
- **Completion rate**: completed out of started, only where the script tag saw both, and over at least 10 starts. Otherwise **not comparable** or **too few to say** (see [The completion rate](leads-and-conversions.md#the-completion-rate)).
- **Cancelled or no-show**, **Won**, **Lost**.

### Leads > What: Demos, each step

[Leads & sales > Leads](#sales/leads?lact=demo) with **What: Demos** shows the calls booked through Calendly and Cal.com, with the script tag and the lead database: **Opened the booking**, **Chose a time**, **Booked**, then **Cancelled**, **Rescheduled**, **No-show**, **Won** and **Lost**. "Chose a time" is a count of page events from a Calendly embed, not of browsers. Cancelled, rescheduled and no-show need the booking tool's webhook. Pick another booking kind in **What** for its own steps.

### Where they came from

The five sources that sent the most leads in the period, by last touch. The fold **Every source, touch and time to convert** holds the rest.

Completed leads by Source (last touch), First touch, Campaign, Landing page, Country, Device and **Reported by** (which source told Skald). A value Skald was not told is shown as "Not recorded", never guessed. A breakdown no lead of the period carries is named in one line instead of a card that only says "Not recorded".

### First, last and assisted touch

- **First touch**: where the browser, or the lead, first came from.
- **Last touch**: the visit it converted in.
- **Assisted**: a source seen earlier in a converting browser's journey that was not its last touch. Each lead counts once per source.

Assisted needs anonymous visitor IDs (below).

**Filled by Skald.** When a lead arrives with a visitor ID but without its touches (your server or tool did not say where the visitor came from), Skald fills them from that browser's own page views: the first touch is its first visit, the last touch the visit it converted in, with that visit's campaign. Script-tag conversions get their first touch and campaign the same way, and their source too: the source of the visit the lead was sent from (where that visit came from, by its first page), not "Not recorded". Only when the browser's page views prove no visit (none reached Skald before the lead) does a script-tag lead keep the source its own event carried; one sent back from a payment page then says "Not recorded", because no earlier visit is proven.

**Payment pages are never a lead's source.** A lead or sale made after the buyer came back from Stripe Checkout or PayPal keeps the source of the visit before it, from the same browser, never "Returned from payment" or "stripe.com". When your server or tool sends the touches, a last touch from a payment page gives way to the first touch (see [Returned from payment](where-visitors-come-from.md#returned-from-payment)). Only by the visitor ID, never by IP address, and only from pages read before the lead. Anything the sender gave always wins. The lead's row and drawer mark these values **filled by Skald**. Page views that reach Skald after the lead still fill it at the next run, and the second count checks every filled value against the page views: a day where they disagree is withheld.

### Likely from an AI assistant

Many people who click a link in a ChatGPT, Perplexity, Claude, Copilot or Gemini answer arrive with no referrer. Their touch then says "Direct" (no referrer and no campaign tag). The section **Likely from AI assistants (inferred)** gives Skald's best guess for those leads, by the assistant that likely sent them. The first touch is the lead's or the tool's first touch; for the script tag, the browser's first visit. It is an estimate, never a count.

How Skald guesses:

1. The touch came with no referrer and no campaign tag.
2. When someone asks an assistant, the assistant fetches the page from your server at that moment. Skald keeps those fetches: which assistant, which page, which minute.
3. If an assistant fetched the touch's landing page in the same minute or up to 15 minutes before, the touch is **likely** from that assistant. Your server's admin can change the window (`attribution.ai_window_minutes`).
4. Unless chance explains it: when an assistant fetched a page so often that day that the page's ordinary direct visits would land after its fetches anyway (your home page, typically), its fetches of that page that day are left out.

What it shows:

- **ChatGPT** (or another assistant): one assistant fetched the page in the window.
- **More than one**: two or more did. The lead counts once.
- A touch that was not direct, or whose page no assistant fetched in the window, is not in the table.
- **Not recorded**, under the table: Skald did not keep the fetches for that time. For example, the touch is from before this feature, more than 180 days ago, or today (today's fetches are kept the next morning).

> Why only "likely"? A fetch can be for someone who read the answer and never clicked. A direct visit a minute later can be someone else. Skald never adds these to the AI assistant source or to any count. The (i) beside the title says the same.

### Time to convert

**From first touch to converting** and **Visits before converting**, for completed leads. A lead whose first touch is dated after it is counted as a clock error and left out.

### The latest leads, on Leads

[Leads & sales > Leads](#sales/leads) lists every lead of the period, newest first (see [The Leads tab](leads-and-conversions.md#the-leads-tab)). A row opens its steps and the pages its browser read, for example "Demo started, then completed". Owners and admins find one person, with every visit and lead, with the **Find a person** box at the top of Leads.

### Cancelled, removed and test

Nothing is hidden. On Leads, **More > Show left out** lists the test, spam and duplicate leads beside the counted ones, and, under the leads, the conversions the figures do not show as completed, of the kind chosen in **What**:

- **Cancelled or no-show**: bookings the booking tool reported as cancelled, or as a no-show.
- **Removed**: rows a lead-database sync took away. For example, the lead was deleted, or marked spam. Each row is kept whole, with when and why.
- **Test**: conversions marked as a test (see below). They are kept and listed, and never counted.

Each one shows its row and, when it had a visitor ID, the pages it read.

## Marking a conversion as a test

A test booking or form should not count. There are three ways to mark a test lead. All three make the same mark, on every stage of the same booking or lead (the same reference from the same tool):

1. **In the dashboard (owners and admins).** Open the lead: a row on Leads, a conversion in a visitor's drawer, in **Find a person** or in the **Show left out** lists. Under its reference, press **Mark as test**. Skald asks first: "Mark u-119797 as test? It stays listed under Show left out and leaves every count." Press **Mark as test** again to do it, or **Cancel**. A short message says how many steps were left out, and the list and the counts update. On a test lead the same button says **Not a test**: it counts the lead again. Viewers do not see the button.
2. **From your site's server.** Send your team's own accounts with `"test": true`, or mark leads you already sent with the signed `leads/test` call. See [Leads from your server](leads-from-your-backend.md#10-mark-leads-as-test).
3. **On the server.** The server admin runs `skald conversions list example.com` to see the latest conversions with their numbers, then `skald conversions mark-test example.com 6 7` to mark conversions 6 and 7 as test, or `skald conversions mark-test example.com --ref u-1001` to mark every step of the lead with that reference. To count one again: `skald conversions mark-test example.com 6 --unmark`.

A lead sent with the wrong step or action can be taken out of the counts without deleting it: the server admin runs `skald conversions remove example.com --ref u-1001 --why "sent twice" --dry-run` to see what would go, then the same without `--dry-run`. Each removed step is kept, with when and why, under **Show left out** on Leads (listed as Removed). Your site can then send the lead again, correct.

One lead counts once: if your site sends both a **completed** and a **paid** step for the same reference and kind of lead (a sign-up that later paid), it is one lead, on the day of the first one. The second step shows in the lead's drawer.

A test conversion is left out of every figure, and of the second count too. It stays listed, marked test, under **Show left out** on Leads. Each change is written to the audit log with who made it, never the reference or a name. A later step of a marked lead (won, lost) is test too.

For a lead in your website's lead database, mark it spam there, or give it the status `test`.

## What "abandoned" means

A conversion is **abandoned** when all of this is true:

1. The script tag saw it start (a form field used, a booking widget opened).
2. The start carried an anonymous visitor ID.
3. Neither the same browser nor the same person (the same email, when your site sends it) completed or paid for the same action within the abandon window. The window is 24 hours unless your server sets another. So a demo opened today and booked tomorrow from another device is a booking, not an abandoned demo.

So:

- A start still inside the window is not counted as abandoned yet.
- A start without a visitor ID cannot be judged, and is never counted as abandoned.
- Abandoned is worked out each time the tab is drawn. It is not stored.

## How a conversion is tied to a visit

Skald ties a conversion to a journey only through an **anonymous visitor ID**: a random ID the browser makes, such as `skv_` followed by 22 letters and digits. It holds no name, email or fingerprint.

- The script tag makes the ID and sends it with each event.
- It adds the ID to Calendly links and embeds as `utm_content`, and Calendly sends it back in its webhook.
- For other tools, the ID is passed in a hidden field or a metadata value. [Webhooks](webhooks.md) says how for each tool.
- Your site's lead push and lead database can carry the same ID.

The figures never match by IP address, and never link a new ID to an old one. A visitor ID is a *browser*, not a person: one person on a phone and a laptop is two browsers. The person search can show, apart from the figures, the visits that sent a form at a lead's time: a match by time, never certain. See [Privacy](privacy.md).

> Visitor IDs are off by default. An owner or admin turns them on per site in [Settings > This site > Data > Script tag & goals](#settings/site/data?sub=script). That tab says, under the tag, whether they are on. Your privacy notice must say so, and some places need consent first. See [Privacy](privacy.md).

Without visitor IDs, conversions are still counted, but there are no journeys, no abandoned counts, no assisted sources and no pages seen before converting. With them off, Skald keeps no visitor ID from any road: not from the script tag, not from a webhook's `vid`, and not from your lead database's session column.

## Goals

Skald's goals are not set on Leads & sales' figures. A goal is a page event, such as "demo booked" or "sign-up sent", shown per 100 visits by source on [Traffic > Events](#traffic/events). Admins choose them in **Settings > This site > Data > Script tag & goals**. See [Funnels and goals](funnels-and-goals.md).

## When a figure is missing

- **Withheld**: every figure is counted twice, by two separate roads. When they disagree on a day, that day is withheld and left out of every sum. The tab says which days and why.
- **Not recorded**: days before a source was set up are not recorded, never zero.
- **Too few to say**: no rate is given over fewer than 10.

## Finding one person

Owners and admins can type an IP address, an email, a lead's number or a visitor ID in the **Find a person** box at the top of [Leads & sales > Leads](#sales/leads), or in the search box at the top of every page (or **Ctrl K**). It shows that person's visits, leads and conversions, spam, test, cancelled and removed ones too, linked together. Each search is written to the audit log. See [Privacy](privacy.md).

**Their visits, newest first** (2.46.5). For a lead your site's server sent, Find a person walks back to the visits in your server log that are that person's, newest on top: where they first came from on their earliest visit (a search engine, an AI assistant, a referring site, a campaign, or no source it can name), the page they landed on, every page they read, and what each visit sent. Each visit is marked:

- **Proven**: the only visit that sent a form within 10 seconds of the lead. Your server reports a lead the moment its form is sent, so that visit is the lead's.
- **Likely**: another visit from the same address and the same browser, from a day before the first proven visit to a day after the lead. Likely the same person, never certain: an office or a phone network can share an address.

A step no visit is proven for (a payment page, a tool's own webhook, a form sent from another network) is listed as not matched. None of this is counted in any figure.

**Their profile, in the lead's drawer.** Owners and admins see the same in the drawer of a lead on [Leads & sales > Leads](#sales/leads), under **Their profile**, without searching: **Who** (the name and email, only when the site keeps them), **Everything they did** (every step linked to them, newest first, with its time, its value and its reference) and **Their visits, newest first** as above. Skald looks the lead up by its reference, as Find a person does, and writes it to the audit log. The link to the drawer holds only the lead's row number, never its reference, name or email. Other members see the drawer as before.

**A Lead or Customer pill on the visit.** On [Traffic > Visitors](#traffic/visitors) and in the visitor drawer, a visit proven to have sent a lead shows a small **Lead** pill, or **Customer** when that person has paid (a paid step on the same reference). Proven only: a likely visit never gets a pill. A pill is a label, never counted, and the daily second count checks every pill by its own road.

## Ad click IDs (off unless you turn them on)

An ad's link carries a click ID that the ad network adds: `gclid` (Google Ads), `msclkid` (Microsoft Ads), `fbclid` (Meta), `li_fat_id` (LinkedIn), `ttclid` (TikTok), `twclid` (X), and `gbraid` or `wbraid` (Google on iPhones). Skald always reads it to name the source and the campaign. With **Keep ad click IDs on leads** on ([Settings > This site > Privacy](#settings/site/privacy), card **Leads**; owners and admins), Skald also keeps the ID itself with the lead, so a lead can be tied to the exact ad click. It comes from the touch your server or tool sent, or, for a lead filled by Skald and for the script tag's own conversions, from the page view the visit started on.

Only owners and admins see it, in the lead's drawer (**Ad click**, with a copy button) and in Find a person; it is never in the figures, the data files or the webhooks Skald sends. It is deleted with the lead, with a person's deletion request, after the People days when you set those shorter than the leads, and all of this site's click IDs at the next run when you turn the setting off. Your privacy notice must say you keep them: the wording Settings offers adds the line when the setting is on.

## Removing a person's data

To delete one person's data (for a privacy request), ask the person who runs your Skald server. They run `skald forget` with the email, IP address, visitor ID or lead reference. It deletes their conversions (with any ad click ID kept on them), the removed rows, their name and email, and the visits kept with their address.
