# AI & bots: crawl health

See which of your pages Google, Bing and each AI crawler actually fetch, which they never reach, which pages they fetch that your sitemap does not list, and the pages that answer crawlers with an error, a redirect, slowly or with a large body. All of it comes from your server log, set beside your own sitemap.

## Where to find it

Open **AI & bots**, then **Crawl health**. Pick **Last 7 days and today** or **Last 30 days and today** at the top of the tab. The date range in the top bar does not apply here.

## The crawlers it follows

- **Google** (Googlebot) and **Bing** (bingbot), the two search crawlers that matter most for most sites.
- **Every AI crawler** by its own name: GPTBot, ClaudeBot, PerplexityBot, meta-externalagent, CCBot and the rest. These collect pages for training or AI search; nobody is waiting on them.
- **Every AI user fetcher** by its own name: ChatGPT-User, Claude-User, Perplexity-User and the rest. These fetch a page because one person asked an assistant about it just then. They are marked **user fetcher**.

Other search crawlers (Applebot, DuckDuckBot, Yandex), bots, people and your own traffic are not part of crawl health.

## Your sitemap

Skald reads your sitemap once a day, as its own check (user agent `site-version-check`, the same one that reads robots.txt, counted as your own traffic). It tries the files named on the `Sitemap:` lines of your robots.txt and `/sitemap.xml` on your site's own host. A sitemap index is followed to its sitemaps; gzip files and plain text lists are read too. Only addresses on your own site's hosts are fetched or kept. If a try fails, the list kept last is used, and the tab says so.

The line at the top says how many pages the sitemap lists, which files they came from and when it was read.

### Change dates from your sitemap

The same daily read keeps each page's `<lastmod>`: the date your sitemap says the page last changed. Nothing more is fetched, and it does not change which pages crawl health counts. Skald keeps every date a page had, with the day it first read it, so you can see which pages changed since a given day.

- Where it shows: [Traffic > Pages](#traffic/pages), in **Pages by publish date** (the **Changed** column, marked "from your sitemap", and the **Changed since** filter, kept in the page's address), and in each page's story (Traffic > Pages, select a page), where each change is a step on the timeline.
- A lastmod is a change date, not a publish date. When your website gives Skald its own page list with publish and updated dates, its updated date wins; without that list, the publish date stays the first day Skald saw the page in your logs.
- Dates are read as your sitemap writes them: a date (2026-10-24), or a date and time with a time zone (2026-10-24T09:30:00+00:00), turned into your site's time zone. A value that is not a date (a year alone, text, a day that does not exist) and a date in the future are left out and counted; the note under the table says how many.
- A page your sitemap lists that nobody has asked for yet has a row too, "not seen yet".
- Some site builders stamp every page with the build time. Then every page looks changed on each build; that is what the sitemap says, and Skald shows it as it is.
- Change dates start on the first sitemap read after the upgrade (the next local day). Days before that have none.

### No sitemap yet

The tab says so and shows how to add one. Coverage and orphans need a sitemap; the problem lists below still work without one.

1. Make a sitemap. Most site builders and CMSs write one (WordPress, Shopify, Webflow, Squarespace); most frameworks have a plugin.
2. Publish it on your site's own host, for example `https://www.example.com/sitemap.xml`.
3. Name it in robots.txt with a line like `Sitemap: https://www.example.com/sitemap.xml`. You can also name it under `crawl_health.sitemaps` in the config.

The next live run reads it; coverage counts from the next collected day. To stop Skald reading the sitemap at all, set `crawl_health.sitemap: false`.

## Coverage by crawler

One card per crawler: the share of your sitemap's pages it fetched at least once in the window, with how many of them it never fetched. The small line under it is each recorded day's share. The table **Each crawler** has every crawler with:

| Column | What it is |
|---|---|
| Requests | Every request it made in the window. |
| Coverage | Sitemap pages it fetched at least once, out of all of them. |
| Never fetched | Sitemap pages it did not fetch once in the window: orphans, as far as that crawler knows. |
| Not in sitemap | Pages it fetched (and your site served) that the sitemap does not list. |
| 404 / 410, 5xx, Redirects | How many of its requests got each answer. |
| Last crawl | Its last request. |
| Kind, Fetches per page | Hidden at first, so the table fits the screen: turn them on under **Columns**. Kind is search, AI crawler or AI user fetcher; fetches per page is its requests per sitemap page it fetched, how often it comes back. Your choice stays in the page's address. |

The chart **Sitemap pages fetched per day** shows one crawler at a time: pick it beside the title. A day it made no request is 0; a day that was not recorded is a gap, never a 0.

## Orphans: sitemap pages a crawler never fetched

**Sitemap pages and when each was fetched** lists, for the crawler you pick, the sitemap pages it did not fetch in the window, with its last fetch in 30 days and how many other crawlers did fetch each. Switch to **Every sitemap page** to see all of them. A page no crawler reaches usually has few links to it from pages crawlers do read, or is blocked.

## Fetched but not in the sitemap

Pages crawlers fetched as a page (and your site served) that the sitemap does not list, with how many times, by which crawlers, on how many days, and the last time. Add the ones people should find to the sitemap; redirect, remove or keep out the rest. Markdown copies and other page-like addresses show here too.

## Problems crawlers hit

Five lists, each with the crawlers that met the problem and whether the page is in your sitemap (**Listed**: the sitemap points crawlers at a broken page):

- **Not found (404 and 410)**: pages crawlers keep asking for that are gone. [Site > Not found](what-to-fix.md#lost-pages) suggests the closest live page for each and the redirect line to copy.
- **Server errors (5xx)**: the server failed a crawler.
- **Redirects (3xx)**: crawlers still asking for an old address. A log does not record where a redirect pointed, so a chain of redirects is counted one redirect at a time.
- **Slow for crawlers**: the server took a second or more.
- **Large answers**: bodies of 1 MB or more.

Slow and large need the response time and the body size in your log; a log without them leaves those lists empty.

## How the figures are checked

Every figure is counted twice, by two pieces of code written apart: the daily count, and an independent recount from the raw log lines and the stored sitemap list. If the two disagree, the day is withheld. The change dates are checked the same way: each morning a separate check reads the stored sitemap files again and works out every page's change dates on its own; if they differ from what the pages show, the morning run says so. Each day is judged by the sitemap kept that day; the windows here use today's list, so a page added to the sitemap counts from then on.
