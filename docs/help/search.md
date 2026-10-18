# Search: queries, impressions and position from Google and Bing

Your server log cannot see a search. It never knows what someone typed, how often your page was shown, or where it ranked. Only the search engine knows. Skald syncs these figures from Google Search Console and Bing Webmaster Tools, every 6 hours, and shows them on **Traffic › Search**, beside the visits Skald counted itself. This guide covers connecting them, what the tab shows, and why Google's clicks and Skald's visits never quite match.

## Where to find it

- [Traffic › Search](#traffic/search): the queries, pages, countries, devices and search appearance, a trend chart, and the cross-check with Skald's own visits.
- **Settings › This site › Integrations › Search**, or [Integrations](#settings/integrations): connect, test, sync now, and the sync's status.

Until a site is connected, the Search tab shows the steps to connect it.

## Connect Search Console

Skald reads Search Console with a **service account**: a robot Google account that can only read. You make it once for the whole Skald install.

**Once, by an install admin:**

1. In Google Cloud console, make a project (or pick one).
2. In APIs & Services › Library, find **Google Search Console API** and choose **Enable**.
3. In IAM & Admin › Service accounts, choose **Create service account**. Give it a name, such as skald-search. It needs no role.
4. Open it, then Keys › Add key › Create new key › **JSON**. A `.json` file downloads. Keep it safe: it is the robot's password.
5. In Skald, **Settings › Integrations › Search › Upload service account key**, and pick the file. Skald checks it, keeps it on the server only, and from then on shows only the robot's email.

**For each site, by a site admin:**

1. **Give the robot access.** Copy the robot's email. In Search Console › Settings › Users and permissions, choose **Add user**, paste the email, set **Restricted** and choose **Add**. Restricted can only read: it cannot change anything.
2. **Find my properties.** Skald lists the Search Console properties the robot can see for this site. Pick one. Only a property that covers this site's host names is accepted.
3. **Test connection.** Skald reads the last 3 days and shows, for example, "OK: 412 rows, clicks 37". Nothing is saved yet.
4. **Connect.** Choose how much history to fetch: none, 3 months, or 16 months (all Search Console keeps). The history comes in the background, with its progress on the page.

**A client's site:** your client does step 1 in their own Search Console. **Copy text to send** gives you a short message with the steps and the robot's email, ready to paste into an email.

## Connect Bing

1. In Bing Webmaster Tools, go to Settings › API access and make an **API key**.
2. An install admin types it in **Settings › Integrations › Search › Bing API key**. Skald shows only its last 4 characters after that.
3. For each site: **Find my sites**, pick the site, **Test connection**, **Connect**.

## What the tab shows

| Figure | What it is |
|---|---|
| Clicks | Clicks on your site in the search results. |
| Impressions | How often a page of yours was shown in the results. |
| CTR | Clicks divided by impressions. |
| Position | Your average place in the results, weighted by impressions. 1 is the top. |

Pick **7 days**, **28 days**, **3 months** or **16 months**. Sort any table by a column; click a row for its detail.

- **Queries**: what people searched for. Google leaves out rare queries to protect searchers, so the queries add up to less than the total. The table shows that gap as **Not given by Google**, never hidden.
- **Pages**: your pages in the results. Google counts these per page, so this table has its own total.
- **Countries**, **Devices**, **Search appearance**: how and where you were shown, under Google's own names.
- **(all others)**: the rows past the top of each day's table, added together, so every table still adds up to its total.

**AI Overviews and AI Mode:** Google's API does not give them apart yet. If Google adds them, they appear under **Search appearance** with Google's own name. Skald never guesses them.

**Bing** gives fewer figures: clicks and impressions per day, and its top queries and pages, updated weekly. Bing gives no total beside its top tables, so a Bing table is only what Bing returned.

## How fresh it is

- Skald syncs **every 6 hours** by itself. **Sync now** asks for a sync at once (admins, at most once in 10 minutes).
- Google's figures arrive **2 to 3 days late**. The newest days can still change: they are marked **provisional**, and each sync fetches the last 4 days again until Google says they are final.
- Google's days are **Pacific Time**. Skald keeps them as Google gives them.
- The status line says **Last synced 13:40 · next ~19:40**, the days stored, and any error.

## When something goes wrong

If a sync fails, the Search tab and Integrations say why, in plain words, and what to do. The most common cause: someone removed the robot from Search Console. Add it back (step 1 above); the next sync clears the error.

The first failure sends **one mail** to the site's mail recipients. No more mails come until it works again.

## Why Google's clicks and Skald's visits differ

The **Cross-check** panel puts Search Console's clicks beside Skald's visits from Google search, by day and by landing page. They never match exactly, and Skald never forces them to:

- A click is not a visit. Two clicks by one person can be one visit. A click closed before the page drew is no visit in Skald.
- Some browsers and apps send no referrer. Skald counts those visits as Direct, not Google.
- Google's days are Pacific Time; yours may not be. One day differs more than a week.
- Search Console here is web results only. Ad clicks are in neither side.

What matters is the ratio over time. When it moves sharply, the panel says so: that is usually a tracking break, such as a page that stopped loading or a redirect that drops the referrer.

## How Skald checks these figures

These figures are Google's and Bing's, not Skald's count, so Skald cannot recount them from the log. Instead, every day it adds up every stored table again by a separate road, checks the tables against the day's total, and asks Google again for one day's total. If they disagree, the tab says so. Skald's own side of the cross-check (visits from search) is counted twice, like every Skald figure.
