# Data contract: page lifecycle, one page's story

Traffic > Pages > a page, `skald page /x`, the helper's `api/page` and the MCP `page_story` tool.
The rest of the data files: [DATA-CONTRACT.md](../DATA-CONTRACT.md).

What happened to a page since it was published.

`page_index.json` (the site's data folder): one row per page the website
lists, its sitemap dates or the logs saw.

| field | type |
|---|---|
| `meta` | `{"source": "website" or null, "generated": date or null, "lastmod": {"day","dated","missing","invalid","future"} or null}`: where publish dates come from (`/etc/skald/pages.json`, written from the website at deploy); `lastmod` the sitemap's change-date counts of the last day read (DATA-CONTRACT-CRAWL-HEALTH.md, "Change dates") |
| `pages[]` | `{"path","title" or null,"locale" or null,"published" (date or null),"date_source" ("website", "page" or "first seen": where `published` comes from),"published_at" (the page's own value or null),"published_from" ("jsonld", "meta", "time" or null),"updated" (date or null),"updated_source" ("website", "page", "sitemap" or null),"updated_at" (the page's own value when `updated_source` is "page", else null),"lastmod" (date or null),"lastmod_seen" ([[date, day first seen]]),"changes" ([{"day","at","sources"}]),"check" ({"at","outcome","status","error"} or null),"first_seen" (date: the first day any request for it was logged),"days_since_publish" (int or null),"milestones": {"googlebot","bingbot","human","from_search","from_ai","lead"} (ISO or null),"views_7d","views_30d","readers_30d"}` |

- `published`: the website's page list's date (`"website"`) when it gives
  one; else the page's own published date, when Skald read one from the page
  (`"page"`, SKALD-64: the site's setting `site.page_dates` on; `published` its
  local day, `published_at` the value as kept, `published_from` where it was
  read); else the first day the logs saw it (`"first seen"`).
- `updated` is a **change date**: the website's own (`updated_source`
  "website") when its page list gives one, else the latest modified date the
  page itself gave (`"page"`, its full value in `updated_at`), else the latest
  `<lastmod>` the sitemap gave (`"sitemap"`), else null. A lastmod is never a
  publish date.
- **The page's own dates (SKALD-64, page_dates.py).** With `site.page_dates`
  on, every live run reads a few of the site's pages (at most 6 a run and 500
  a local day, as Skald's own `site-page-dates/1` request, never counted as a
  visitor or a bot): a page never read (its published date is read once),
  one whose sitemap date changed since its last read, one whose last read
  failed (at most once a day), and every page once in 30 days. The pages are
  the day's sitemap list and the 200 pages people read most in the last 7
  days that it does not list; never an address of the not-a-page list. Each
  date is read from the page's JSON-LD (an article's, else a web page's;
  never a comment's or the organisation's), else its `article:*_time` meta
  tags (or microdata), else a `<time>` marked as the page's (itemprop or the
  hAtom classes); a bare `<time>` never counts. A value is kept as a date
  (`2024-11-05`), a UTC time (`2026-11-26T05:42:14Z`) or a time without a
  zone as written; anything else, a date before 1990 or a future one is not a
  date. The sitemap's dates are read again every 6 hours and kept with their
  time; when a site is turned on, the dates its sitemap history holds are
  copied in. Every value ever seen is kept (history tables `page_dates` and
  `page_checks`, schema 16; never pruned).
- `changes`: every modified date kept for the page, the page's own and the
  sitemap's, one entry per local day (`at` the day's latest value, `sources`
  the places it came from), oldest first; [] when the site has none. `check`:
  the last read of the page (`outcome` dated, not_given, not_html,
  redirected, failed or blocked; `status` the HTTP status; `error` plain
  words). A page Skald could not read keeps the sitemap's date.
- The second counts: `audit_page_dates.py` reads the stored rows by its own
  SQL and works `published_at`, `published_from`, `updated_at`, `changes` and
  `check` out again; `audit_lastmod.py` takes the page's own day before the
  sitemap's for `updated`.
- `lastmod`: the latest change date the sitemap gave the page (shown even
  when the website's own `updated` wins); `lastmod_seen`: each date, with the
  first local day Skald read it, oldest first, at most 20. "Changed since day
  X" is `lastmod >= X`. Both spellings of a path (with and without the
  trailing slash) are one page. A page only the sitemap lists has a row with
  `published` and `first_seen` null.

`GET <page>/api/page?path=/x` (helper; also `skald page /x`):

```json
{"ok":true,"path":"/x/","title":"...","published":"2026-10-01","updated":"2026-10-06",
 "date_source":"website","updated_source":"website","lastmod":"2026-10-06",
 "lastmod_seen":[["2026-10-06","2026-10-07"]],"first_seen":"2026-10-06","days_since_publish":7,
 "milestones":{"googlebot":{"at":"2026-10-06T19:02:11-04:00"},"bingbot":null,
   "ai_training":[{"who":"GPTBot","at":"..."}],"ai_asked":[{"who":"ChatGPT-User","at":"..."}],
   "human":{"at":"..."},"from_search":{"at":"...","who":"google.com"},
   "from_ai":[{"who":"chatgpt.com","at":"..."}],"lead_landed":{"at":"..."} ,"lead_sent":null,
   "googlebot_latest":{"at":"2026-10-11T07:40:02-04:00","status":200},"bingbot_latest":null},
 "time_on_page":{"median_s":40,"measured":12,"not_measured_last_page":9,"min_measured":5,"days":6},
 "days":[{"day":"2026-10-06","state":"partial","days_since_publish":5,"readers":3,"views":4,
   "ai_asked":0,"ai_training":2,"search":1,"sources":{},"assistants":{},"countries":{},
   "time_on_page":{"median_s":null,"measured":2,"not_measured_last_page":2}}]}
```

- Milestones are kept for good (history table `page_milestones`, schema 11)
  and each is the earliest time seen: Googlebot and Bingbot fetching the page,
  each AI crawler fetching it to train or index (`ai_training`), each
  assistant fetching it for a live question (`ai_asked`), the first person
  reading it, the first person arriving on it from a search engine
  (`from_search`, with the search site) and from each AI assistant
  (`from_ai`). Only verified crawlers count for Googlebot and Bingbot (a
  "claims to be" never does). `lead_landed` / `lead_sent`: the first lead
  whose first touch landed on the page, and the first sent from a form on it
  (CMS). The audit recounts each day's first times from the raw log.
- `googlebot_latest` / `bingbot_latest` (#44): the crawler's newest fetch of
  the page, `{"at", "status"}` (the HTTP status it got), kept for good in the
  same table (kinds `googlebot_latest` and `bingbot_latest`, the status in
  `via`; no schema change). The same rule as the first fetch: a verified
  crawler and a page view (2xx or 304, GET or HEAD, no asset, no not-a-page
  address), so a redirect or an error never counts. Filled from each day's
  `page_firsts` blob (`"googlebot_latest": [UTC time, status]`, the greatest
  pair of the day); an earlier day collected again never moves it back.
  Null: the crawler never fetched the page since the logs began. The audit
  recounts each day's latest pair from the raw log (audit_release2.FirstsRecount).
- `time_on_page` (#46, page_time.py): from your own log, per day in `days[]`
  and over the story's whole (`ok`) days at the top. For each time a visit
  was on the page (a page load, or an in-app move seen from a later
  request's referrer) that has a next one in the same visit: the seconds to
  the next, kept to the second under a minute and to 10 s under ten minutes
  (visits.seconds_bucket). `measured` is how many; `not_measured_last_page`
  the visits that ended on the page (it had no next view, so no time);
  `median_s` their median, null under `min_measured` (5) measured views. A
  day without figures has `time_on_page` null; a day stored before the times
  were kept would too. An estimate: the log sees when the next page was asked
  for, not how long someone read. The audit recounts each day's seconds per
  page and this figure from the raw log (audit_page_time.py).
- `days[]` run from the publish date (or first seen) to yesterday, at most
  400 (a page published before the logs began, as its own date often says,
  has those days as "before"; the page charts from its first counted day), each with its state; a day with no figures (`missing`, `withheld`)
  has them null, never 0. Today is not included.

## One page's Google Search figures (SKALD-64)

`GET <page>/api/page-search?path=/x&days=28` (helper; the page drawer's "Google
Search" section on Traffic > Pages). Search Console's own figures for the page,
never Skald's count: `mcp/tools_search.figures` over the stored `search_days`
rows, which `audit_search_pages.py` recounts (days, countries and, from
SKALD-64, the page's queries).

```json
{"ok":true,"connected":true,"engine":"google","path":"/x/","address":"/x/",
 "first":"2026-10-29","last":"2026-11-25","length":28,
 "days":[{"day":"2026-10-29","final":true,"clicks":0,"impressions":6,"ctr":0.0,"position":9.5}],
 "totals":{"clicks":12,"impressions":4300,"ctr":0.0028,"position":5.3},"totals_partial":false,
 "not_in_page_table":[],"missing_days":[],"provisional_days":["2026-11-24","2026-11-25"],
 "queries":[{"query":"...","clicks":9,"impressions":3100,"ctr":0.0029,"position":5.2}],
 "countries":[{"country":"usa","clicks":8,"impressions":2600,"ctr":0.0031,"position":5.0}],
 "countries_not_stored":[],"index":null,
 "before":{"first":"2026-10-01","last":"2026-10-28","totals":null,"totals_partial":false,
           "missing_days":[]}}
```

- The period is the last `days` days (7 to 93, default 28) up to the newest day
  Search Console has stored, in Google's own (Pacific Time) days: Google has
  no figures for today and is two or three days late. `before` is the same
  number of days just before, totals only.
- A day the page has no row in a complete page table is 0; in a table that
  kept only its top pages it is null (not known, a gap in the chart) and
  listed in `not_in_page_table`. `queries` are the page's 25 largest over the
  period, `countries` its 10 largest, from each day's top pairs.
- `address`: the path the figures are for. When Search Console has no row at
  all for the drawer's path, the same path with its closing "/" added or
  taken off is used when that one has rows.
- `{"ok": true, "connected": false}` when Search Console never stored a day
  for the site.
