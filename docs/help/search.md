# Search: queries, impressions and position from Google and Bing

Your server log cannot see a search. It never knows what someone typed, how often your page was shown, or where it ranked. Only the search engine knows. Skald syncs these figures from Google Search Console and Bing Webmaster Tools, every 6 hours, and shows them on **Traffic › Search**, beside the visits Skald counted itself. This guide covers connecting them, what the tab shows, and why Google's clicks and Skald's visits never quite match.

## Where to find it

- [Traffic › Search](#traffic/search): the figures first, then one section at a time: the trend and the tables (queries, pages, countries, devices and search appearance), **Opportunities**, **New and lost** queries, **Positions** over time, and the **Cross-check** with Skald's own visits.
- **Settings › This site › Leads & tools › Search Console & Bing**, or [Search Console & Bing](#settings/site/leads?tool=search): connect, test, sync now, and the sync's status.

Until a site is connected, the Search tab says what it needs and offers one **Connect**, which asks **Who will do it?** (Me, My developer or My AI agent). A viewer reads "Ask an admin to connect it" with a link to copy. Once it is connected, owners and admins see **Sources: Leads & tools** on the tab, which opens the group that feeds it.

## Connect Search Console

Skald reads Search Console with a **service account**: a robot Google account that can only read. You make it once for the whole Skald install.

**Once, by an install admin:**

1. In Google Cloud console, make a project (or pick one).
2. In APIs & Services › Library, find **Google Search Console API** and choose **Enable**.
3. In IAM & Admin › Service accounts, choose **Create service account**. Give it a name, such as skald-search. It needs no role.
4. Open it, then Keys › Add key › Create new key › **JSON**. A `.json` file downloads. Keep it safe: it is the robot's password.
5. In Skald, **Settings › This site › Leads & tools › Search Console & Bing › Upload service account key**, and pick the file. Skald checks it, keeps it on the server only, and from then on shows only the robot's email.

**For each site, by a site admin:**

1. **Give the robot access.** Copy the robot's email. In Search Console › Settings › Users and permissions, choose **Add user**, paste the email, set **Restricted** and choose **Add**. Restricted can only read: it cannot change anything.
2. **Find my properties.** Skald lists the Search Console properties the robot can see for this site. Pick one. Only a property that covers this site's host names is accepted.
3. **Test connection.** Skald reads the last 3 days and shows, for example, "OK: 412 rows, clicks 37". Nothing is saved yet.
4. **Connect.** Choose how much history to fetch: none, 3 months, or 16 months (all Search Console keeps). The history comes in the background, with its progress on the page.

**A client's site:** your client does step 1 in their own Search Console. **Copy text to send** gives you a short message with the steps and the robot's email, ready to paste into an email.

## Connect Bing

1. In Bing Webmaster Tools, go to Settings › API access and make an **API key**.
2. An install admin types it in **Settings › This site › Leads & tools › Search Console & Bing › Bing API key**. Skald shows only its last 4 characters after that.
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

**Bing** gives fewer figures: clicks and impressions per day, and its top queries and pages, updated weekly. Bing gives no total beside its top tables, so a Bing table is only what Bing returned. Opportunities, new and lost queries and positions over time are Search Console's only.

**Missing or partial days.** When the history does not cover the whole period, a line above the figures says so: how many of the days are there, the day the history starts, any day with no figures, and which newest days are still provisional. If Search Console is connected but has no figures yet, the tab says that too, and why (a new property, a history still syncing, a failing sync).

Every choice on the tab is in the page's address: the engine, the period, the section, each list's filter and "Show all". Copy the address to share exactly what you see.

## Opportunities

Queries where a page could win more clicks. Two simple rules, over the period you picked:

| Rule | A query is listed when | What usually helps |
|---|---|---|
| **Rarely clicked** | It was shown at least 100 times, or 5 times a day if that is more; under 1% of the people who saw it clicked; and its average position is better than 8. | It already ranks high. A clearer title and description for the page. |
| **Positions 8-20** | Its average position is from 8 to 20, and it was shown at least 30 times, or once a day if that is more. | It is at the foot of page one or the top of page two. More on the page about that query. |

Each query is linked to the **page** it showed most, by impressions. Skald keeps each query's page from this release on; for days synced before it, the page says **Not known** until the history is fetched again (Settings › This site › Leads & tools › Search Console & Bing, with 3 or 16 months). Choose **Rarely clicked** or **Positions 8-20** to see one rule; click a query for its detail.

The exact numbers are behind the **?** next to the heading.

## New and lost queries

**New**: a query in Search Console's query table in the period and on no day of the same number of days before it. **Lost**: the other way round. Pick **New** or **Lost**.

- **Whole days only.** Both stretches end at the newest **final** day, so the provisional days are left out, and every day of both must be in the history. When they are not, the section says which day it needs and where the history starts.
- **16 months** has no "before": Search Console keeps 16 months, so there is nothing to compare it with.
- Google gives each day's top queries (Skald keeps 500 a day) and leaves rare and personal queries out. A query just below that line can look new or lost when it only moved across it.

## Position tracking

The average position of each query and page over the period: one point a day for 7 and 28 days, a week for 3 months, 30 days for 16 months. Pick **Queries** or **Pages**; **Move** compares the first point with the latest (up is better). Click a row for its chart.

- **Google's position is an average.** It is the site's best place in each result shown, added up and divided by the times it was shown (weighted by impressions). It is not a rank you can check by searching: it differs by place, device and person.
- **Gaps.** A point where the query or page had no row that day is empty, never 0.
- **The newest points are provisional.** Google may still change them. In the chart they are hollow and dashed.
- The 100 queries and the 100 pages shown most in the period are tracked.

## How fresh it is

- Skald syncs **every 6 hours** by itself. **Sync now** asks for a sync at once (admins, at most once in 10 minutes).
- Google's figures arrive **2 to 3 days late**. The newest days can still change: they are marked **provisional**, and each sync fetches the last 4 days again until Google says they are final.
- Google's days are **Pacific Time**. Skald keeps them as Google gives them.
- The status line says **Last synced 13:40 · next ~19:40**, the days stored, and any error.

## When something goes wrong

If a sync fails, the Search tab and Settings › This site › Leads & tools › Search Console & Bing say why, in plain words, and what to do. The most common cause: someone removed the robot from Search Console. Add it back (step 1 above); the next sync clears the error.

The first failure sends **one mail** to the site's mail recipients. No more mails come until it works again.

## Why Google's clicks and Skald's visits differ

The **Cross-check** panel puts Search Console's clicks beside Skald's visits from Google search, by day and by landing page. They never match exactly, and Skald never forces them to:

- A click is not a visit. Two clicks by one person can be one visit. A click closed before the page drew is no visit in Skald.
- Some browsers and apps send no referrer. Skald counts those visits as Direct, not Google.
- Google's days are Pacific Time; yours may not be. One day differs more than a week.
- Search Console here is web results only. Ad clicks are in neither side.

What matters is the ratio over time. When it moves sharply, the panel says so: that is usually a tracking break, such as a page that stopped loading or a redirect that drops the referrer.

## How Skald checks these figures

These figures are Google's and Bing's, not Skald's count, so Skald cannot recount them from the log. Instead, every day it adds up every stored table again by a separate road, checks the tables against the day's total, and asks Google again for one day's total. It also works the opportunities, the new and lost queries and the positions out again by that separate road, and compares them with what the tab shows. If they disagree, the tab says so. Skald's own side of the cross-check (visits from search) is counted twice, like every Skald figure.
