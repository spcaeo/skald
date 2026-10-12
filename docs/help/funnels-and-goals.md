# Funnels and goals

How to build a funnel of pages and events, save it and read its history, how goals work on the Events tab, and how to find badly tagged campaign links.

## Funnels

A funnel answers "how many visits went through these pages, in this order, and where did the rest leave?". Open [Leads & sales > Funnels](#sales/funnels).

### How steps are counted

- A visit reaches a step when it reads a page that matches it, after the step before.
- The page that met one step may also meet the next. So "Any page" then "/pricing/" counts a visit that landed straight on pricing.
- The page steps are built from each visit's pages in order. These are kept for a few days (7 by default), so a new funnel shows only those days. Save it to count it every day (see "Funnel history").

### Build a funnel

Each page step has a choice of how it matches pages:

| Choice | Matches | Example |
| --- | --- | --- |
| Any page | every page; as a first step, the visit's start | - |
| Page is | that exact page, with or without the last slash | `/pricing/` |
| Starts with | every page whose address begins this way | `/blog/` |
| Page named | a page whose last part is this word, in any language folder | `pricing` matches `/pricing/` and `/fr/pricing/` |

1. Open [Leads & sales > Funnels](#sales/funnels).
2. In **Starting from**, choose where the visits came from: **Any source**, a kind of source (such as Search engine or AI assistant), or one assistant under **One assistant**.
3. For each step, choose how it matches pages (above), then type the page.
4. To let a step match several pages, type them separated by a vertical bar, such as `/pricing/ | /plans/`.
5. Press **Add a step** for the next one. A funnel has up to 8 steps.
6. To remove a step, press the **×** beside it.

The tab suggests pages your visitors read as you type.

### Event steps

A step can also be an event from the [tracking script](tracking-script.md), such as a button click or a demo booked.

1. Press **Add a step**.
2. In the step's list, look under **An event, from the beacon** and choose the event.

> Event steps are counted as events on the same days, beside the visits. They are never joined to a visit, so they are not a share of the step before. When **Starting from** is a single assistant or site, an event step shows "not split by this source".

### Lead steps

A funnel can also end with steps from your website's lead database: Opened Book a demo, Sign-up, Contact form, Early access, Demo booked. They are counted by the lead's first-touch source, beside the visits, never joined to them. They are counted once the funnel is saved.

Lead steps cannot be added from the step list. The built-in funnel **Landing to lead** has them: landed, pricing, a sign-up or contact page, then demo opened, lead and demo booked.

### Read the result

- The heading says how many visits went through every page step, out of how many started.
- Each step shows its visits and its share of the start.
- Between steps, a line says how many left before this step. A drop of half or more is marked.

### Open a step's visits

1. Click a page step's bar.
2. The visits that reached it are listed below, each with its pages in order. Press **Show 20 more** for more.
3. Press **Left after it** to see the visits that stopped at this step instead. Press **Reached it** to go back.
4. Click the bar again to close the list.

### Save a funnel

1. Type a name in **Name this funnel**. If you leave it empty, the steps become the name.
2. Press **Save funnel**.

Saved funnels show as buttons above the builder. Click one to open it. Press **×** beside one to delete it. **Landing to lead** is built in and cannot be deleted.

- **Saved for everyone**: your server keeps saved funnels for the whole team.
- **Saved on this browser**: your server does not keep them, so they live only in this browser (up to 20).

> With accounts, saved funnels are shared by every site of the install, so only an install admin can save or delete them. Viewers can open them but not change them.

A funnel also lives in the page's address. Copy the link to share a funnel you have not saved.

### Funnel history

A saved funnel is counted every day from the day it is saved, so it covers any date range, not only the days visits are kept. Its first day shows after the next daily run.

The **History** section shows:

- The visits at each step over the date range, and what share of the step before went on.
- **Visits at each step, per day**: one line per step. The gap between two lines is the visits lost between them.
- **By source type** and **By device**: each step per source or device, and **Went through** (the last step as a share of the first).
- **Where they went next**: for each step, the next page of the visits that went no further, or "Left the site".
- **Time to go through**: from the first step to the last, from under 10 seconds to 30 minutes or more.

History counts page steps only. Days before the funnel was saved are "not recorded", never zero. A day that did not pass Skald's checks is withheld and left out. No share is given over fewer than 10 visits.

## Goals

A goal is an event from the tracking script that counts as success for you, such as "Demo booked" or "Sign-up sent". Skald shows each goal per 100 visits, by source.

### Where goals are set

You need to be an admin of the site.

1. Open [Leads & sales > Events](#sales/events) and select **Edit goals** beside the Goals heading. Or open **Settings > This site > Sites** ([Sites](#settings/sites)).
2. In the **Goals** box, tick the events that count as success, such as **Sign-up sent** or **Demo booked**. Up to 10.
3. Select **Save**.

The events your site has already counted come first. Events not counted yet are under **Not counted yet**, so you can set a goal before the event starts.

Goals show from the next run, for every day already counted. To have no goal, untick them all and save.

> On a server without accounts, there is no Settings page for goals. The person who runs your Skald server names them in the server's settings (`beacon.goals`). A goal saved in the app replaces that list for your site.

### Where goals show

Open [Leads & sales > Events](#sales/events) and choose a date range. The **Goals** section has one table per goal:

- **Source**, **Visits** from that source, the goal's events, and **Per 100 visits**.
- The heading gives the whole site's rate.

How to read it:

- Visits come from your server log; events come from the tracking script. Two counts side by side, never joined per visit.
- A day counts only when both passed their checks. Today's goals appear after midnight.
- No rate is given over fewer than 10 visits.
- Goals are for the whole site. The page filter does not apply to them.

If no goal is set, the section says so, with a link to set one.

For conversions from all sources (bookings, payments, CRM deals), with completion rates and sources, use [Leads & sales > Pipeline](#sales/pipeline) with **Count from: Tools**. See [Leads and conversions](leads-and-conversions.md).

## The Events tab

[Leads & sales > Events](#sales/events) shows what people did inside your pages, as totals. Nothing here is tied to a visit or a person. Bots are left out.

- **The figures at the top**: each kind of event, with its rate per 100 visitors.
- **Through the forms**: Sign-up started to Sign-up sent, and Demo booking opened to Demo booked, with the share that went on (from five starts).
- **Per day**: a line per main event. A hatched stub is a day not counted.
- **Goals**: see above.
- **Which button or form**: each event by its name and page, such as a Button click named `pricing_top` on `/pricing/`.
- **By page** and **By source**: one column per kind of event.

Today's events are shown as "not yet checked". Events are checked each night against your server log. A day that does not match is left out, and the tab says why. A page marked **flagged** had more events than its page views allow on some day.

## Campaign tag problems

Badly tagged links split one campaign into several, or hide where visitors came from. Skald finds four kinds of problem.

Open [Traffic > Sources](#traffic/sources) and scroll to **Campaigns and referrers**, then **Tag problems**.

| Problem | What it means | How to fix it |
| --- | --- | --- |
| Source tag without a medium | the link has `utm_source` but no `utm_medium`, so tools cannot tell the channel | add `utm_medium`, such as `email` or `cpc` |
| Medium no tool knows | `utm_medium` is not a usual channel name, so it lands in "other" | use a usual name: `cpc`, `email`, `social`, `referral` |
| Ad click id without tags | an ad click id (such as `gclid` or `fbclid`) and no `utm_` tag: the network is known, the campaign is not | turn on auto-tagging, or add `utm_campaign` in the ad |
| Tags on links between our own pages | a `utm_` tag on a link from one of your own pages starts a new source mid-visit | never tag links between your own pages |

Each problem shows how many visits had it, up to three example landing addresses with their tags, and the pages they landed on. A visit can have more than one problem.

The same section may also list campaigns that appear in your leads but were never seen in your server log. This often means a redirect dropped the tags.

Above it, **UTM tags** lists visits by Source, Medium, Campaign, Term and Content, each with pages per visit, broken links met and form sends.
