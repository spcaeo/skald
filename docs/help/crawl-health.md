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
| Fetches per page | Its requests per sitemap page it fetched: how often it comes back. |
| 404 / 410, 5xx, Redirects | How many of its requests got each answer. |
| Last crawl | Its last request. |

The chart **Sitemap pages fetched per day** shows one crawler at a time: pick it beside the title. A day it made no request is 0; a day that was not recorded is a gap, never a 0.

## Orphans: sitemap pages a crawler never fetched

**Sitemap pages and when each was fetched** lists, for the crawler you pick, the sitemap pages it did not fetch in the window, with its last fetch in 30 days and how many other crawlers did fetch each. Switch to **Every sitemap page** to see all of them. A page no crawler reaches usually has few links to it from pages crawlers do read, or is blocked.

## Fetched but not in the sitemap

Pages crawlers fetched as a page (and your site served) that the sitemap does not list, with how many times, by which crawlers, on how many days, and the last time. Add the ones people should find to the sitemap; redirect, remove or keep out the rest. Markdown copies and other page-like addresses show here too.

## Problems crawlers hit

Five lists, each with the crawlers that met the problem and whether the page is in your sitemap (**Listed**: the sitemap points crawlers at a broken page):

- **Not found (404 and 410)**: pages crawlers keep asking for that are gone.
- **Server errors (5xx)**: the server failed a crawler.
- **Redirects (3xx)**: crawlers still asking for an old address. A log does not record where a redirect pointed, so a chain of redirects is counted one redirect at a time.
- **Slow for crawlers**: the server took a second or more.
- **Large answers**: bodies of 1 MB or more.

Slow and large need the response time and the body size in your log; a log without them leaves those lists empty.

## How the figures are checked

Every figure is counted twice, by two pieces of code written apart: the daily count, and an independent recount from the raw log lines and the stored sitemap list. If the two disagree, the day is withheld. Each day is judged by the sitemap kept that day; the windows here use today's list, so a page added to the sitemap counts from then on.
