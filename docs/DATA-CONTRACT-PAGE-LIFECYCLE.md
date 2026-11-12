# Data contract: page lifecycle, one page's story

Traffic > Pages > a page, `skald page /x`, the helper's `api/page` and the MCP `page_story` tool.
The rest of the data files: [DATA-CONTRACT.md](../DATA-CONTRACT.md).

What happened to a page since it was published.

`page_index.json` (the site's data folder): one row per page the website
lists, its sitemap dates or the logs saw.

| field | type |
|---|---|
| `meta` | `{"source": "website" or null, "generated": date or null, "lastmod": {"day","dated","missing","invalid","future"} or null}`: where publish dates come from (`/etc/skald/pages.json`, written from the website at deploy); `lastmod` the sitemap's change-date counts of the last day read (DATA-CONTRACT-CRAWL-HEALTH.md, "Change dates") |
| `pages[]` | `{"path","title" or null,"locale" or null,"published" (date or null),"date_source" ("website" or "first seen": where `published` comes from),"updated" (date or null),"updated_source" ("website", "sitemap" or null),"lastmod" (date or null),"lastmod_seen" ([[date, day first seen]]),"first_seen" (date: the first day any request for it was logged),"days_since_publish" (int or null),"milestones": {"googlebot","bingbot","human","from_search","from_ai","lead"} (ISO or null),"views_7d","views_30d","readers_30d"}` |

- `updated` is a **change date**: the website's own (`updated_source`
  "website") when its page list gives one, else the latest `<lastmod>` the
  sitemap gave (`"sitemap"`), else null. A lastmod is never a publish date:
  without the website's list, `published` stays the first day seen.
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
  400, each with its state; a day with no figures (`missing`, `withheld`)
  has them null, never 0. Today is not included.
