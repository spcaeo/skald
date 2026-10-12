# Leads and conversions

Where Skald's leads and conversions come from, what the Leads and Conversions pages show, and what "abandoned" means. Every figure here is a count: no names, emails or messages.

## Two pages, two jobs

Skald has two pages for results. Both are under **Results** in the menu.

- [Leads](#leads) counts the leads in your website's own lead database: sign-ups, contact forms, early-access requests and demo bookings.
- [Conversions](#conversions) counts every action that matters, from every source at once: the lead database, your booking, form and payment tools, and the script tag on your pages.

The Leads page reads only the lead database. A booking that reaches Skald from Calendly, or a form from Typeform, shows on the Conversions page, not on the Leads page.

## Where leads and conversions come from

There are four sources. You can use one or all of them.

| Source | What it gives | Shown on |
| --- | --- | --- |
| Your website's lead database | every lead, its kind, its status, first and last touch | Leads and Conversions |
| Your site's lead push (the `lead` hook) | a lead your own server reports the moment it is made | Conversions |
| Webhooks from your tools | bookings, cancellations, no-shows, form answers, payments, CRM deals | Conversions |
| The `skald.js` script tag | forms started and sent, booking widgets opened and booked, phone and email clicks | Conversions and Events |

### The lead database

If your website keeps its leads in its own database, the person who runs your Skald server can point Skald at it. Skald opens it read-only and never changes it. Every two minutes it reads the leads that changed.

- Leads marked `spam` or `duplicate` are left out of every count, and counted apart.
- A lead's status (new, contacted, qualified, won, lost) is read as it is now. When your team changes a status, past days change with it.
- Names and emails stay in your website's admin. Skald does not show them.

### Your site's lead push

Your site's own server can tell Skald "a lead was made" with a signed message. See [Webhooks](webhooks.md), section "Your own site's lead push".

### Webhooks from your tools

Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier and Make can send Skald a signed message for each booking, form or payment. This is how Skald learns about cancellations, no-shows and payments, which the page itself never sees. See [Webhooks](webhooks.md).

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

## The Leads page

Open [Leads](#leads). The date range at the top governs most of the page.

### The figures at the top

- **Leads**: sign-ups, contact forms and early access, with spam and duplicates removed.
- One figure per kind: Sign-ups, Contact forms, Early access, Demo opened, Demos booked.
- **Leads per 100 visitors**: leads against the visitors of the same verified days. It is given only over at least 10 visitors.

Under them, a line says how many spam and duplicate leads were left out.

### Per day, by kind

A chart of each kind of lead per day. A hatched stub is a day with no lead counts. That day is *not recorded*, never zero.

### Where they came from

Each lead is shown twice, by its **First touch** and by its **Last touch**:

- **First touch** is the source the lead's own browser remembered from its very first visit.
- **Last touch** is the visit the form was sent from.

There are four tables: by Source, by AI assistant, by Campaign and by Landing page. A lead without a value is said under the table, not shown as a row.

### Likely from an AI assistant

Many people who click a link in a ChatGPT, Perplexity, Claude, Copilot or Gemini answer arrive with no referrer. Their touch then says "Direct or unknown". The **Likely AI (inferred)** table, beside the four above, gives Skald's best guess for those touches, by first touch and by last touch. It is an estimate, never a count.

How Skald guesses:

1. The touch came with no referrer and no campaign tag.
2. When someone asks an assistant, the assistant fetches the page from your server at that moment. Skald keeps those fetches: which assistant, which page, which minute.
3. If an assistant fetched the touch's landing page in the same minute or up to 15 minutes before, the touch is **likely** from that assistant. Your server's admin can change the window (`attribution.ai_window_minutes`).

What it shows:

- **ChatGPT** (or another assistant): one assistant fetched the page in the window.
- **More than one**: two or more did. The lead counts once.
- A touch that was not direct, or whose page no assistant fetched in the window, is not in the table.
- **Not recorded**, under the table: Skald did not keep the fetches for that time. For example, the touch is from before this feature, more than 180 days ago, or today (today's fetches are kept the next morning).

> Why only "likely"? A fetch can be for someone who read the answer and never clicked. A direct visit a minute later can be someone else. Skald never adds these to the AI assistant source or to any count. The (i) beside the title says the same.

### Lead quality by source

Statuses by first-touch source: New, Contacted, Qualified, Won, Lost, Spam, Duplicates. The column **Qualified or won, of reviewed** is the share of leads that are no longer new and were marked qualified or won. It is given over at least 10 reviewed leads. If every lead is still "new", the page says so and shows no zeros.

### Time to convert

- **From first touch to lead**: how long after the first visit the lead came, in buckets from "Under an hour" to "Over 90 days".
- **Visits up to the lead**: the browser's own count of its visits when it sent the form.

### Funnel, by source

From visitors to demos booked, per source: **Visitors**, **Saw pricing**, **Opened a form**, **Opened the demo**, **Became a lead**, **Booked a demo**. Each step is shown as a share of that source's visitors, over at least 10 visitors.

> The first three steps are visits from your server log. The last three come from the lead database, by the lead's first-touch source. Skald puts them side by side for the same days. It never joins one lead to one visit.

## The Conversions page

Open [Conversions](#conversions). If nothing is set up yet, the page lists each source as **On** or **Off** and says what to turn on.

### Every action

One row per action, with these columns:

- **Started**: starts seen by the script tag. "not seen" means no start was reported, for example an action only a tool reports.
- **Completed**: completed and paid together.
- **Abandoned**: see below.
- **Completion rate**: completed out of started, given over at least 10 starts.
- **Cancelled or no-show**, **Won**, **Lost**.

### Demo funnel

For demos only: **Opened the booking**, **Chose a time**, **Booked**, then **Cancelled**, **Rescheduled**, **No-show** and **Won**. "Chose a time" is a count of page events from a Calendly embed, not of browsers. Cancelled, rescheduled and no-show need the booking tool's webhook.

### Where the completed ones came from

Completed conversions by Source (last touch), First touch, Campaign, Landing page, Country, Device and **Reported by** (which source told Skald). A value Skald was not told is shown as "Unknown", never guessed.

### First, last and assisted touch

- **First touch**: where the browser, or the lead, first came from.
- **Last touch**: the visit it converted in.
- **Assisted**: a source seen earlier in a converting browser's journey that was not its last touch. Each conversion counts once per source.

Assisted needs anonymous visitor IDs (below).

### Likely from an AI assistant (conversions)

The section **Likely from AI assistants (inferred)**: completed conversions whose first touch was direct, by the assistant that likely sent them, the same guess as on the Leads page. The first touch is the lead's or the tool's first touch; for the script tag, the browser's first visit. "Not recorded", under the table, means the first touch, or the fetches around it, were not kept. Likely, never certain, and not part of the sources above.

### Time to convert

**From first touch to converting** and **Visits before converting**, for completed conversions. A conversion whose first touch is dated after it is counted as a clock error and left out.

### Pages seen before converting

For the last 30 days: the share of converting browsers that saw each page before converting, beside the share of browsers that did not convert. Use it to ask "does the pricing page help?". It needs visitor IDs.

### Latest conversions

The latest 50 completed conversions, one per browser (or per lead without one). Each shows its visits by day, the pages it read and its steps, for example "Demo started, then completed". No name, email or visitor ID is shown.

## What "abandoned" means

A conversion is **abandoned** when all of this is true:

1. The script tag saw it start (a form field used, a booking widget opened).
2. The start carried an anonymous visitor ID.
3. The same browser did not complete (or pay for) the same action within the abandon window. The window is 24 hours unless your server sets another.

So:

- A start still inside the window is not counted as abandoned yet.
- A start without a visitor ID cannot be judged, and is never counted as abandoned.
- Abandoned is worked out each time the page is drawn. It is not stored.

## How a conversion is tied to a visit

Skald ties a conversion to a journey only through an **anonymous visitor ID**: a random ID the browser makes, such as `skv_` followed by 22 letters and digits. It holds no name, email or fingerprint.

- The script tag makes the ID and sends it with each event.
- It adds the ID to Calendly links and embeds as `utm_content`, and Calendly sends it back in its webhook.
- For other tools, the ID is passed in a hidden field or a metadata value. [Webhooks](webhooks.md) says how for each tool.
- Your site's lead push and lead database can carry the same ID.

Skald never matches by IP address, and never links a new ID to an old one. A visitor ID is a *browser*, not a person: one person on a phone and a laptop is two browsers.

> Visitor IDs are off by default. The person who runs your Skald server turns them on per site. [Integrations](#settings/integrations) says whether they are on. Your privacy notice must say so, and some places need consent first. See [Privacy](privacy.md).

Without visitor IDs, conversions are still counted, but there are no journeys, no abandoned counts, no assisted sources and no pages seen before converting.

## Goals

Skald's goals are not set on the Conversions page. A goal is a page event, such as "demo booked" or "sign-up sent", shown per 100 visits by source on the [Events](#events) page. Admins choose them in **Settings > Sites > Goals**. See [Funnels and goals](funnels-and-goals.md).

## When a figure is missing

- **Withheld**: every figure is counted twice, by two separate roads. When they disagree on a day, that day is withheld and left out of every sum. The page says which days and why.
- **Not recorded**: days before a source was set up are not recorded, never zero.
- **Too few to say**: no rate is given over fewer than 10.

## Removing a person's data

To delete one person's conversions (for a privacy request), ask the person who runs your Skald server. They can delete by email, visitor ID or lead reference.
