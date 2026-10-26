# Where visitors come from, and their journeys

Most visits say **Direct**: the browser sent no referrer. Many of them are people coming back, who first found you through a search, an AI assistant or a post days before. Others came back from a payment page, opened your link inside an app, or followed a shared link. This guide covers visitors by social network (X, LinkedIn, ...) on each site and across all your sites, how Skald finds a visitor's first visit, what a Direct visit likely was, where you see both, and the visitor drawer with every visit of one visitor.

## Social networks: X, LinkedIn and the rest

A visit from X can arrive as `t.co`, `x.com`, `twitter.com` or the X app; one from LinkedIn as `linkedin.com`, `lnkd.in` or the LinkedIn app. **Traffic › Sources › Social network** puts each network in one row, so you see at once how many visitors X sent:

- **X**: t.co, x.com, twitter.com (and mobile.twitter.com), the X app. **LinkedIn**: linkedin.com, lnkd.in, the LinkedIn app. **Facebook**: facebook.com (and l., m., lm.facebook.com), fb.com, the Facebook app. **Instagram**, **Threads**, **Reddit**, **YouTube** (youtube.com, youtu.be, its app), **TikTok**, **Pinterest** (any country domain), **Bluesky**, **Mastodon** (mastodon.social only), **Hacker News**, **Quora**, **Telegram**, **WhatsApp**, **Slack** and **Discord**.
- A tagged link with no referrer counts for the network its `utm_source` names (`utm_source=twitter` or `x` is X), else its `utm_medium`, else its ad click id (`fbclid` is Facebook, `li_fat_id` LinkedIn, `ttclid` TikTok, `twclid` X). A tag that names two networks, or only "social", counts as **Social, network not named**.
- Every visit counts once, in one network, and the networks add up to the **Social media** row of Source type. Nothing is reclassified: a site Skald does not call social (Product Hunt, threads.com, fb.me, a Mastodon server other than mastodon.social) stays under Other website.

Click a network to open it under the grid: **how they were matched** (each host, app or tag, with its visitors) and **where they landed**. The address keeps it, for example `#traffic/sources?src_seg=social&net=x`, so you can copy the link, and Back closes it. Before, Change, the trend and Compare mode work as for source types, when every day of both periods recorded the networks. Each day is counted twice, by two separate roads; a day where they disagree is withheld. A day counted before this release (2.34.0) says "Not recorded", never zero.

### Fill in the days before 2.34.0

The person who runs your Skald server can count those days again from the raw log, for the days the log still holds: 14 by default (the web server's log rotation, and the folder that keeps shipped logs). Older days stay "Not recorded". After the upgrade, away from the daily run (07:15 in the site's time zone):

```
docker exec skald skald backfill --days 14 --force
docker exec skald skald audit --day 2026-10-20 --withhold
```

- `backfill --force` counts each of the last 14 days again with the current version, for every site (`--site example.com` before `backfill` picks one). It fills in the networks, and any other figure those days did not record yet, such as Direct, likely.
- Then run `audit --day ... --withhold` for each of those days, one date at a time. The audit counts the networks a second time from the raw log, and must end with "all match". With `--withhold`, as in the daily run, a day that does not match is withheld and not shown; find why before you go on.
- The recount also counts the rest of those days again with the current rules, so a figure of those days can change a little if a rule changed since they were stored. The chart marks the recount.

## All your sites side by side

On the site picker (**All sites**, `/traffic/`), **Where visitors came from, all your sites** has one row per site you may open: visitors from **Search**, **Social** and its top networks (**X**, **LinkedIn**, **Facebook**, **Instagram**, **Reddit**, **YouTube**), **AI** and **Direct**, for **Today**, **7 days**, **30 days** or **90 days**. The period is in the address (`#sources-30d`), and Back and Forward move between periods. Each figure opens that site's Sources with the network open.

It shows no new figure: each cell is the site's own verified figure, the same its Sources tab shows. A site's row says how many days of the period are verified; a withheld day is left out and named. A cell no verified day recorded says **Not recorded**, never zero. A site you may not open is not listed at all. One person who visited two sites counts on both.

## First touch: the first visit we know of

For every visit, Skald looks for the same visitor's first visit it knows of. It tries three links, in this order, and the first one that finds an earlier visit wins:

1. **The visitor ID**, when the script tag has visitor IDs on (Settings › This site › Collect data › Script tag & goals). The visit is the ID's when the ID's page view of the landing page arrived within seconds of the visit, and no other ID did. Its first touch is the ID's earliest page view.
2. **The address and browser**, when the site keeps addresses (Settings › This site › Privacy & retention › People). The earliest kept visit from the same address with the same browser and system, even earlier the same day.
3. **The 30-day code**, when the visitor key is set. It gives the day and the source type of the first visit within 30 days, not the site that sent it.

When none finds an earlier visit, the visit says **first visit we know of**. Skald never guesses. A site that keeps no addresses uses only the visitor ID and the 30-day code, and says which one linked each visit.

One address can be several people (an office), and one person on two devices is two visitors. A visitor ID is one browser.

## Where you see it

- **Traffic › Visitors**, in **Each visit**: under a visit's source, a line such as "First came from google.com, 3 days ago". It shows only when the first visit came from somewhere else.
- **Overview › Real time**, in **Newest visits**: the same line, and each visit opens the visitor drawer.
- **Traffic › Sources**, in **Where returning visitors first came from**: for the period, how many Direct visits came before, by where they first came from and by the site that sent them; and every returning visit by where it first came from. Each day's figures are counted twice, by two separate roads; a day where the two disagree is withheld. A day counted before this existed is left out and said.

## Direct, likely: what a Direct visit probably was

Some Direct visits say more in their own request, or in the log just before them. Skald shows those as **likely** a cause, never as fact. Each Direct visit gets one reason at most, checked in this order:

1. **Direct, likely checkout or payment return.** The visit landed on a page with a payment provider's return code in its address (Stripe, PayPal, Razorpay, Checkout.com, Adyen), or on a checkout's end page, such as `/checkout/order-received/` or `/order/thank-you`. A bare `/thank-you` is not enough: a form's thank-you page looks the same.
2. **Direct, likely in-app browser.** The visit was opened inside an app's own browser: Instagram, Facebook, LinkedIn, TikTok, Snapchat, Pinterest, X, Gmail, the Google app, WeChat, Line, or an app that did not say its name. Those apps often send no referrer.
3. **Direct, likely shared link.** The link carried a share marker (such as `igshid=` from Instagram or `ref=whatsapp`), or an app such as WhatsApp, Slack, iMessage or Discord fetched a preview of the same page up to 30 minutes before. The preview comes from the app or the sender's phone, not from the person who clicked, so it is matched by page and time only.

Anything else stays plain Direct.

Where you see it:

- **Traffic › Sources**, in **Direct, likely (inferred)** under the sources grid: each reason, its visits, its share of Direct and what it showed (for example "Stripe 3" or "WhatsApp 2"), and how many stayed plain Direct. The Direct row above keeps every one of these visits: nothing is moved out of it. The (i) says how it is worked out. In Compare mode it is not shown.
- **The visitor drawer**, under **This visit**: a line such as "Direct, likely in-app browser (Instagram app)".

Each day is counted twice, by two separate roads; a day where the two disagree is withheld, and a range that does not add up shows "Withheld". A day counted before this release says "Not recorded", never zero. Only the reason, the app or provider and counts are kept: never the codes in the address. An admin can turn it off, or change the 30-minute preview window, with `attribution.direct_likely` and `attribution.share_window_minutes` in the config file.

This is a different estimate from **Likely from AI assistants** (AI & bots › Assistants). A visit can be in both.

## The visitor drawer

Every visit and every visitor opens in the same drawer: a row of the visit list, a newest visit in Real time, a funnel's journey, a visit picked out of the visitor flow, a person found with **Find a person**, and a converted person or conversion under Leads & sales.

- **The title** names the visitor by city ("Visitor from Toronto"), else by country, and the line under it says how many visits over how many days, and any booked demo or lead.
- **At the top**: first seen, how many visits over how many days, where the visitor first came from (and how long ago; the link that tied the visits is on hover), the city (or the country) with its flag and three-letter code, the device with its browser and system, and the outcome: a booked demo, a lead, a form sent, or none linked.
- **Journey, newest visit first**: each visit as a card, its steps down a line. Where it came from, each page in order with the time between pages on the line, and how it ended: left, sent a form, a lead, or a booked demo. Between visits it says how long after ("12 days later"). The steps appear one by one when the drawer opens; **Replay**, beside the close button, plays the visits again, oldest first, at their real pace (one second per minute, at most four seconds a visit). With reduced motion on, it stays still. Hover or focus a page for its time; click it to open the page.
- **Every visit as a table**: open it for the same visits as rows, the first visit highlighted.
- **Leads and conversions** linked to the visits. A lead is matched to a visit by the time a form was sent: likely, never certain.
- **This visit**: the visit's own labels and campaign tags.

A visit alone is anonymous. Every visit of the visitor shows only to admins and owners, and only where the site keeps addresses. Each time it is opened, the audit log records it (never the address). Pages seen only by the script tag, with no visit in the server log, are marked "seen by the script".
