# AI & bots: what each crawler costs

See which AI assistants, search engines and bots fetch your site, how much work each one makes for your server, and what one of them did in detail. This guide covers the cost table, the detail view, and what each figure means.

## Where to find it

Open **AI & bots**. The table **What each crawler costs** is on two tabs:

- **Crawlers**: AI collecting pages for training or AI search, search engines, and bots and scanners.
- **Assistants**: AI assistants fetching a page because someone asked them a question. Here it is headed **What each assistant costs**.

Pick the period at the top as on any other page: today, yesterday, a number of days, or your own dates.

## What the columns mean

| Column | What it is |
|---|---|
| Name | The name the crawler gives itself. Bots without a known name go by the name in their user agent. Scanner probes are one row, **(scanner probes)**; everything else a scanner asked for that day (its home page, say, between two probes) is another, **scanner (asked for secret or config files)**. |
| Requests | Every request it made in the period. |
| Bytes sent | How much your server sent it, from the size field of each log line. |
| Mean time | How long your server took per request, on average. |
| p90 time | 9 in 10 of its requests took no longer than this. Shown for a single day only. |
| Errors | The share of its requests that got an error (4xx or 5xx). |
| Distinct paths | How many different addresses on your site it asked for. |
| Re-crawl | Requests per distinct path: 3.0× means it fetched each path three times on average. |
| Last seen | Its last request in the period. |

Select a name to open its detail.

An assistant is called by the name people know it by: **ChatGPT**, not `chatgpt.com`. A bot keeps its own name, because it is one fetcher, not the assistant. A bot that reads a page only when one user asks the assistant about it (`ChatGPT-User`, `Claude-User`, `Perplexity-User`) is marked **user fetcher**.

## When a figure says "not recorded" or "partial"

Skald only shows what your server log holds. It never fills a gap with zero.

- **Bytes: not recorded.** None of that crawler's log lines had a size. Some log formats and hosting platforms do not write one.
- **Bytes: partial.** Only some lines had a size. The figure is the sum over those lines; hover over it to see how many.
- **Mean time: -** The log does not record how long the server took. nginx does when its log format has `$request_time`. Vercel, Caddy and edge records do not.
- **p90 time** shows only when the period is a single day. A p90 over many days cannot be built from each day's p90, so for longer periods use the mean, or pick one day.

## Figures over several days

For a period of more than one day:

- Requests, bytes and errors are added up over the days.
- The mean time is weighted by request: a busy day counts more than a quiet one.
- Distinct paths are counted per day and added up. A path fetched on two days counts twice. Re-crawl is therefore requests per path within a day.
- Each day keeps its 50 busiest names per group. The rest are one row, **(all others)**.

## The detail view

Select a name in the table, or any crawler name elsewhere on AI & bots. The detail opens on the right. Under **What it costs and what it fetched** you see:

- **Requests, bytes sent, mean server time and errors** for the period.
- **From an address checked as theirs**: the share of its requests from an address that really belongs to its owner. Requests that use a crawler's name from an address that is not theirs are counted apart, as "claims to be ...".
- **Requests per day**, as a chart.
- **Pages it fetched**: the pages it asked for most.
- **Status mix**: how the server answered.
- **Countries of its requests**: from the log's country field or the GeoIP file.
- **User agents it sent**: the exact strings, the five most used each day. These are the crawler's own, never a person's. For scanner probes and the rest of a scanner's requests, link previews and browser-like bots the strings are not kept, because they may be a real person's browser.
- **Last seen**.

Pages, countries and user agents are kept for the last 30 days. For an older period the detail says how many of its days have them. No address is ever shown.

## How the figures are checked

Every figure here is counted twice, by two pieces of code written apart: the daily count, and an independent recount from the raw log lines. If the two disagree, the day is withheld until someone finds out why. A withheld day is left out of every total and named at the top of the page.
