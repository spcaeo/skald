# Retention: who came back

**Traffic › Retention** answers one question: of the visitors first seen in a week, how many came back in each week after? Or by day: of those first seen on a day, how many came back each day after. Like the retention reports in Google Analytics 4 or PostHog, with Skald's rules: every figure is counted twice, and what Skald cannot know is said, never shown as 0.

## Who is the same visitor

Skald has no cookie. It knows a visitor again in one of two ways, and the page says which one your site uses, at the top of the tab:

- **Kept visits**, when the site keeps IP addresses (Settings › This site › Privacy & retention › People). The same IP address with the same browser and system is the same visitor. Kept 395 days unless you changed it.
- **The 30-day code**, when the site keeps no addresses but the visitor key is set. An address and browser family, hashed with a secret. It keeps a day and a source type only, so there is no split by country, device or landing page, and no "read 2 or more pages".

With neither, the tab says so and counts nothing. The page script's visitor ID is not used here: it is kept 30 days and only for visits that ran the script, so it would make the same visitor count once or twice depending on the script.

One address can be several people (an office), and one person on two devices is two visitors.

## New, and how far back

A visitor is **new** in a week when its first visit there has no visit of the same visitor in the days before it: 332 days with kept visits (395 days kept), 15 days with the 30-day code. The rest of the days are needed to follow the cohort afterwards: Skald counts a cell only while every day it reads is still kept.

So each identity can follow a visitor so far after the first visit: **62 days** with kept visits (all 8 weeks), **14 days** with the 30-day code (the next week, not the one after). A later cell says **not recorded**, never 0.

While your history is young, "new" means first seen since Skald started keeping visits; the tab gives that day.

## Reading the triangle

- Each **row** is a cohort: the visitors first seen that week (Monday to Sunday, in the site's time zone) or that day, and how many.
- Each **column** is a later week (+1, +2 ...) or day. A cell shows the share that came back and how many. Darker is more, scaled to the highest share on the screen.
- A **blank** cell: that week is not over yet.
- A **hatched** cell: not recorded (later than the identity can follow, or its days were removed before it was counted), or held back (a day in it is not verified).
- A cohort with fewer than 10 new visitors shows counts only: a share of a tiny group misleads.

Hover or focus a cell for its figures. Click it to list the visitors behind it, each opening in the visitor drawer with every visit (admins and owners, on kept visits only; each list is written to the audit log, never the address).

The **retention curve** under it is the share back at each step, over every cohort counted there: the visitors back, summed, over the new visitors in those cohorts. On a phone the triangle and the curve become two tables.

## Options

- **Weeks or Days**: weekly cohorts over the last 12 weeks (8 weeks after each), or daily cohorts over the last 30 days (14 days after each).
- **Came back** or **Read 2+ pages**: any visit, or a visit that read 2 or more pages.
- **Split by** the first visit's source type, country, device or landing page, then pick a value. The 8 biggest values of each split are kept, the rest are "Other".

The date range at the top does not apply: the tab has its own period.

## Checked twice

The daily run counts the cohorts after it collects the day, and keeps them. The audit then counts each one again from the same kept rows with its own code. A cohort whose two counts disagree is withheld. A cohort counted on the last run says "not checked yet" until the next daily run.

Kept visits and codes are removed after their keeping time. A cohort whose days are gone stays as last counted and checked, marked **inputs expired**: it can no longer be checked again. A visitor you forget (`skald forget --ip`) leaves every cohort still counted at the next run.
