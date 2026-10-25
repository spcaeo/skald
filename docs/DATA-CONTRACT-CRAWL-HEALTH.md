# Data contract: crawl health

What each crawler fetched beside the site's own sitemap, and the problems
crawlers hit (`skald/sitemap.py`, `skald/crawl_health.py`;
the second count is `skald/audit_crawl_health.py`). The tab is
AI & bots › Crawl health; the guide is [help/crawl-health.md](help/crawl-health.md).
Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md).

## The sitemap list (beside the history)

The live run reads the site's sitemaps after robots.txt (`sitemap.refresh`),
as Skald's own fetcher `site-version-check/1` (always our own traffic,
CLASSIFICATION-PATTERNS.md, `ours`): the `Sitemap:` lines of the robots.txt robots.py keeps,
`https://<host>/sitemap.xml` (the `www.` host when listed, else the first of
`site.hosts`) and any URL in `crawl_health.sitemaps`. A sitemap index is
followed to its sitemaps; gzip and plain-text sitemaps are read. Only URLs
on `site.hosts` are fetched (a redirect off them is refused) or kept; the
others are counted as `skipped`. Limits: 20 files, 10 MB each (unzipped),
100,000 paths, 5 s per file; a file with a DOCTYPE or ENTITY is refused.
Once the local day has a list, it is not fetched again that day; a failed
try is repeated at most once an hour. `crawl_health.sitemap: false` turns
the fetch off (nothing is fetched, no list is used).

| file | what |
|---|---|
| `sitemaps/days.json` | `{day: {"list", "paths", "fetched_at", "sources": [url], "skipped", "truncated", "lastmod"}}`: one entry per local day a fetch worked, written once and never rewritten; kept 400 days. `lastmod` (below) is missing on a day kept before change dates were read |
| `sitemaps/<list>.json` | `{"paths": [path]}` sorted; `<list>` is the first 16 hex characters of the SHA-256 of the paths joined by newlines. A list is stored once however many days name it, and removed when no day does |
| `sitemaps/lastmod/history.json` | each path's change dates across days, version 1 (below) |
| `sitemap-state.json` | the last try: `tried_at`, `ok`, `error`, `fetched_at`, `urls`, `paths`, `lastmod`, `skipped`, `truncated`, `file_errors` |

A path is the URL's path (no query string, no fragment, first 200
characters), compared with a log line's path as it stands. A day is judged by
the list kept that day, else the latest kept before it (`sitemap.for_day`).

## Change dates (`<lastmod>`)

The same fetch reads each `<url>`'s `<lastmod>` (`sitemap_dates.py`); nothing
more is fetched, and the path list (what crawl health is judged by) is built
exactly as before, from every `<loc>`. A sitemap index's own `<lastmod>` (when
a child file changed) is no page's and is not read; a plain-text sitemap has
none. A lastmod is when the site says a page last changed, **not a publish
date**.

- **Accepted:** the W3C datetime forms with a day: `YYYY-MM-DD` (taken as it
  stands), or with a time and a zone (`Z` or `±hh:mm`, seconds and fractions
  optional), turned into the site's time zone (`report.timezone`). A time with
  no zone (not W3C) is read as the site's own time. A year or a month alone,
  any other text, a date that does not exist and a year before 1990 are
  **invalid**; a date after the fetch's local day is **future**. Both are
  left out and counted.
- **Per day:** each path of the day's list counts once, in `days.json`'s
  `lastmod`: `{"version": 1, "dated", "missing", "invalid", "future",
  "digest"}`, dated + missing + invalid + future = `paths`. Two URLs with one
  path keep the latest valid date. `digest`: the first 16 hex characters of
  the SHA-256 of the day's sorted `path<TAB>date` lines joined by newlines.
- **Across days**, `sitemaps/lastmod/history.json` (version 1), merged once
  per local day with the day's first good fetch:

```json
{"version": 1, "day": "2026-10-25", "cap": 20,
 "paths": {"/pricing/": {"now": "2026-10-24", "last": "2026-10-25",
                         "seen": [["2026-10-02", "2026-10-21"], ["2026-10-24", "2026-10-25"]]}}}
```

  `seen`: each lastmod the path had, with the first local day Skald saw it,
  oldest first, at most `cap` (the oldest dropped). `now`: the date the last
  day merged gave (null when it gave none or no longer listed the path).
  `last`: the last day the path had a date; a path whose `last` is 400 days
  old is dropped. The file lives in a subfolder, so the lists' clean-up never
  removes it. A file of another version is not read (no dates shown).
- **Shown:** `page_index.json` and the page story (DATA-CONTRACT.md, "Page
  lifecycle"): `lastmod`, `lastmod_seen`, and `updated` with `updated_source`
  "sitemap" when the website's own list gives no updated date.
  `crawl_health.json`'s `sitemap.lastmod` is the day's counts.

The second count is `audit_lastmod.py` (run-daily's recounts, `audit_more.DAILY`
`sitemap_lastmod`). It re-reads the history file, `days.json`, the day's list
and the website's page list with its own code: real dates, none after the day
it was seen, the days rising, at most `cap`; `now` the last date seen and on
the file's day; the day's `dated` equal to the paths with a `now`, the counts
adding up to the list, the digest matching, every dated path in the day's
list, every day named kept in `days.json`. Then it works out each page's
`lastmod`, `lastmod_seen`, `updated` and `updated_source` again by the rule
(the path cut at `?`, a `/` added unless it ends with one; every spelling's
pairs sorted by day then date, a date kept once, the last `cap`; the latest
date; the website's `updated` first) and compares them with what the page
shows. A mismatch ends the run "withheld".

## The day kind `crawl_health`

Counted in the tally pass for the whole site only (a view has none), kept
like the other per-day detail (`report.retention_days`), checked by verify
and recounted by the audit. The crawlers: Google (`Googlebot`) and Bing
(`bingbot`) among the search crawlers, kind `"search"`; every AI crawler
and AI user fetcher by the name classify.py gives, kind `"ai_training"` or
`"ai_asked"`. Other search crawlers, bots, people and our own traffic are
not in it. No address and no user agent.

```json
{"sitemap": {"day": "2026-10-04", "list": "4f0c…", "paths": 16} | null,
 "slow_ms": 1000, "large_bytes": 1000000, "keep": 500, "fields": [...],
 "crawlers": {"Google": {"kind": "search", "requests": 7, "pages": 3, ...,
                         "listed": 2, "unlisted": 1, "unlisted_requests": 1,
                         "folded": 0, "paths": {"/pricing/": [...]}}}}
```

Per crawler, per path, a list in the order of `fields`:

| field | meaning |
|---|---|
| `requests` | its requests for the path |
| `pages` | of them, page views (a 2xx or 304 page, CLASSIFICATION.md "What decides a page view") |
| `listed` | 1 when the path is in the day's sitemap list, else 0 |
| `redirects` | answered 3xx, 304 not included |
| `not_found` | answered 404 or 410 |
| `server_errors` | answered 5xx |
| `slow` | took `slow_ms` (1,000 ms) or more (each line's time rounded to a millisecond) |
| `large` | a body of `large_bytes` (1,000,000) or more |
| `timed`, `ms` | lines with a response time, and those times summed (ms) |
| `sized`, `bytes` | lines with a body size, and those sizes summed |
| `max_bytes` | the largest body, null when no line had a size |
| `last` | its last request for the path, UTC ISO 8601 |

Every listed path is kept; of the others the 500 most requested (ties by
path), the rest summed into one `"(all others)"` entry (`folded`: how many
paths). Each crawler's totals are the sums of its paths' `requests`,
`pages`, `redirects`, `not_found`, `server_errors`, `slow`, `large`,
`timed`, `ms`, `sized`, `bytes`. Then, over every path, folded ones too:
`listed` distinct sitemap paths fetched, `unlisted` distinct paths fetched
as a page that the list does not hold, `unlisted_requests` their page views.
**With no sitemap list for the day, `sitemap`, `listed`, `unlisted` and
`unlisted_requests` are null (not recorded), never 0.**

Verify holds: the AI crawlers' requests add up to the AI group's; Google and
Bing's are within the search crawlers'; each total is its paths' sum; as many
paths are marked listed as `listed` says, none folded; parts never exceed
requests; `max_bytes` is null exactly when no line had a size.

The audit (`audit_crawl_health.py`) counts every crawler and path again from
the raw lines with its own code, reads the list the day names from
`sitemaps/<list>.json` with its own code (its name must be its hash, and
`days.json` must name it for the day it was kept, no later than the day),
compares every kept path field by field, the fold against the rest, and
`listed`, `unlisted` and `unlisted_requests` over every path. A day stored
without a sitemap while a list was kept before it is a mismatch.

## crawl_health.json

Beside each page (a view's says `{"whole_site_only": true}`):

| field | what |
|---|---|
| `sitemap` | `{"enabled", "url", "sources", "tried_at", "ok", "error", "fetched_at", "day", "paths", "skipped", "truncated", "lastmod"}`: the list kept for today (or the latest before); `paths` null when none; `lastmod` that day's change-date counts, null when not recorded |
| `slow_ms`, `large_bytes` | the thresholds |
| `windows` | `{"7": w, "30": w}`: the last 7 or 30 recorded days ending yesterday, and today so far when the live snapshot is ok |
| `pages` | `{"total", "rows": [{"path", "crawls": {crawler: [fetches in 7 days, fetches in 30 days, last ISO]}}]}`: every page of today's list (the 3,000 least fetched), null with no list |
| `days[]` | 30 days: `{"day", "state", "crawlers": {name: {"kind", "requests", "listed", "sitemap", "unlisted", "not_found", "server_errors", "redirects", "slow", "large"}} or null}` - the stored day's figures |
| `today` | the snapshot's state, `from`, `until`, and the same `crawlers` |

A window `w`: `days` (recorded days in it); `crawlers[]` `{"name", "kind",
"requests", "days", "folded", "last", "paths", "listed", "coverage",
"orphans", "unlisted", "per_page", "not_found", "server_errors", "redirects",
"slow", "large"}` - judged by **today's** list: `listed` the list's paths it
fetched, `coverage` = listed / list size (4 decimals), `orphans` the list's
paths it never fetched, `unlisted` paths it fetched as a page that today's
list lacks, `per_page` its requests per listed path fetched; these are null
with no list, and "at least" when `folded` (a folded path is not seen);
`unlisted` `{"total", "rows": [{"path", "pages", "requests", "by": {crawler:
page views}, "days", "last"}]}` (top 300); `problems` `{kind: {"total",
"rows": [{"path", "n", "requests", "by", "last", "listed", "mean_ms"
(slow), "max_bytes", "mean_bytes" (large)}]}}` for `not_found`,
`server_errors`, `redirects`, `slow` and `large` (top 100 each). Every figure
is a sum or a count of stored, audited day figures.
