# Search: Search Console and Bing figures, and the cross-check (P1-6)

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply. Code: `skald/search/`
(`days.py` the table, `sync.py` the sync, `data.py` the file, `reports.py` the
opportunities, new and lost queries and positions),
`skald/search_landing.py` (Skald's own side). Second roads:
`skald/audit_search.py` (the synced figures, and through
`skald/audit_search_reports.py` the reports) and
`skald/audit_search_landing.py` (`search_landing`). Setup:
[INTEGRATIONS.md](INTEGRATIONS-SEARCH.md#search-console-and-bing).

The engines' figures are theirs, never Skald's: nothing here is ever added
to a Skald figure, and a search figure is never drawn as people.

## The history table `search_days` (history schema 14)

One row per site, engine, day and kind. A table, not a column: older days
simply have no rows. The upgrade to 14 copies the file aside first, then
adds the table (DEPLOY.md section 7).

| column | meaning |
|---|---|
| `site` | the site (never a view: search figures are for the whole site) |
| `engine` | `google` (Search Console) or `bing` (Bing Webmaster Tools) |
| `day` | the engine's own day, `YYYY-MM-DD`. Search Console's days are Pacific Time (America/Los_Angeles), as Google gives them; Bing's are the dates Bing gives. Never re-cut into the site's time zone. |
| `kind` | `total`, `query`, `page`, `country`, `device`, `appearance`, `query_page` (Bing: `total`, `query`, `page`) |
| `data` | the blob below, JSON |
| `final` | 1 when the engine says the day will not change (Search Console: before the answer's `first_incomplete_date`; Bing: 10 days old or more); 0 provisional, fetched again by the next sync |
| `source` | the property or site address it was read from |
| `fetched_at` | UTC, ISO 8601 |

The blob (`days.fold`):

| field | meaning |
|---|---|
| `total` | `{"clicks", "impressions", "position"}`: the engine's own total for the day in this kind's terms. Search Console counts the page table by page and the others by property, so `page` has its own total. Bing's `query` and `page` have no total from Bing: theirs is the sum of the rows. |
| `rows` | `[[key, clicks, impressions, position], ...]`: the top rows by clicks, then impressions, then key. Top: query 500, page 300, country 250, device 10, appearance 100, query_page 500; `total` holds one row `"(all)"` |
| `others` | `{"rows", "clicks", "impressions", "position"}`: every row past the top, summed ("(all others)"); position their impression-weighted mean |
| `unattributed` | `{"clicks", "impressions"}`: the total minus every row the engine returned. Positive: counted, but not given by this dimension (Search Console leaves anonymised queries out of the query table). Negative: rows overlap (one result can count under more than one search appearance). Shown, never forced to 0. |
| `complete` | true when there are no others and nothing unattributed |

**The sum rule**, for clicks and for impressions: `sum(rows) + others +
unattributed = total`. The sync refuses a blob that breaks it, writes a
day's kinds in one transaction, reads them back, and keeps nothing when what
is stored differs from what the engine gave.

Counts are whole numbers when whole (Google sends doubles). Position is
rounded to 2 places; null when the engine gives none (Bing writes -1 for
none; Skald keeps null).

`query_page` (Search Console only): each query with the page it showed,
keyed `"<query>\t<page address>"` (a tab between them). Google counts a
table with the page by page, so its `total` is the page blob's total (the
second road checks it); anonymised queries are in `unattributed`. Days
synced before this kind was kept have no `query_page` row: the reports say
the page is not known for them.

A day inside a Search Console range that Google leaves out had no
impressions (Google omits empty days): it is stored with zeros. A day after
the newest day Google has is never stored.

## The day kind `search_landing`

Skald's own side of the cross-check: people's visits from search engines,
per day, from the day's journeys (`search_landing.py`; in `day_extras`).

| field | meaning |
|---|---|
| `visits` | every people visit whose source is "Search engine" |
| `engines` | `{"Google", "Bing", "Other", "Paid"}`: by the referring host (a google.<tld> search domain or Google's Android search app; bing.com). `Paid` when the landing address carries an ad click id (the engines count unpaid results only); `Other` every other engine and a tagged link with no referrer |
| `pages` | `{"Google": {landing path: visits}, "Bing": {...}}`: the top 200 and `"(all others)"` |

Sums: `engines` adds up to `visits`, and to the day's visits by source
"Search engine"; each engine's `pages` add up to its visits. Second count:
`audit_search_landing.py`, from the raw lines with its own host and
click-id rules (it shares only classify.py's click-id names). A day that
disagrees is withheld, like any day kind.

## search.json

The Search tab (Traffic › Search). Written for the site and every view; a
view's file says `view_note` (search figures are for the whole site).

| field | type |
|---|---|
| `engines` | `{"google": part, "bing": part}` (below) |
| `keys` | `{"google": bool, "bing": bool}`: is a usable key set on the install. Never the key, never the robot's email. |
| `view_note` | `"Search figures are for the whole site."` on a view, else null |
| `crosscheck` | below |

Each engine's `part`:

| field | type |
|---|---|
| `name` | `"Search Console"` or `"Bing Webmaster Tools"` |
| `connected` | the property or site address, or null when not connected |
| `status` | the sync state (`search/state.py`): `last_sync`, `last_ok`, `ok`, `error` (plain words, null after a good sync), `error_since`, `error_mailed`, `next_sync` (about when the scheduler syncs next), `rows`, `note`, `days`, `first`, `last`, `provisional`, `backfill` `{"state": "queued"/"running"/"done"/"failed", "months", "done", "of", "started_at", "finished_at", "error"}`, `audit` `{"at", "ok", "problems"}` (the second road's last result) |
| `summary` | `{"days", "first", "last", "provisional", "fetched_at"}` of what history holds |
| `days[]` | every stored day of the last 480 up to the newest, oldest first: `{"day", "clicks", "impressions", "ctr", "position", "final"}`. `ctr` is clicks / impressions (null when 0 impressions). |
| `periods` | `{"7", "28", "90", "480"}`: the last N days up to the newest stored day, each `{"first", "last", "days", "provisional_days": [day], "totals": {"clicks", "impressions", "ctr", "position"}, "query", "page", "country", "device", "appearance", "coverage"}`, and for Search Console also `"changes"`, `"positions"`, `"opportunities"` (below) |

Each table in a period: `{"rows": [[key, clicks, impressions, ctr,
position]], "others": {"rows", "clicks", "impressions", "position"},
"unattributed": {"clicks", "impressions"}, "total": {"clicks",
"impressions", "ctr", "position"}, "folded_days"}`. Rows are each day's top
rows summed, then the top (query 300, page 200, country 100, device 10,
appearance 50); the rest go to `others`. `folded_days` counts the days on
which some rows were already in "(all others)": a row's sum may then be
short, and the tab says so. Position is impression-weighted. The sum rule
holds for every table.

### A period's reports (`search/reports.py`)

Worked out from the stored days only; nothing is asked of Google. Second
road: `audit_search_reports.py`, by SQL over the stored JSON, run by
`audit_search.py` every day; a difference ends run-daily "withheld".

`coverage` (both engines): `{"days", "stored", "before_history" (days before
the first stored day), "missing": [day] (inside the history, no figures),
"provisional": [day], "history_first", "empty"}` (`empty`: every stored day
has 0 impressions).

`changes`, new and lost queries, on whole days only:

| field | type |
|---|---|
| `state` | `"ok"`; `"too_long"` (16 months: the period and the one before are longer than Search Console keeps); `"no_final"`; `"short"` (a day of the two is not stored or not final; with `need_from`, `history_first`, `not_whole`) |
| `now`, `before` | `{"first", "last"}`: the last N final days (ending at the newest final day) and the N days before |
| `new`, `lost` | `{"count", "clicks", "impressions", "rows": [[query, clicks, impressions, ctr, position]]}`: queries in the query rows of one stretch and on no day of the other; `lost` has the figures of `before`. The first 300 rows, by impressions, clicks, query |
| `queries_now`, `queries_before` | distinct queries in each |
| `folded_days` | days of the two with queries below the day's top 500 |

`positions`: `{"size": days per bucket (7 and 28 days: 1; 3 months: 7; 16 months: 30),
"buckets": [{"first", "last", "days", "provisional"}] (oldest first; the oldest may be
short), "query" and "page": {"keys": distinct keys, "rows": the 100 most shown, each
{"key", "clicks", "impressions", "position", "points": [position or null per bucket],
"shown": [impressions or null], "first", "last", "change": first - last (positive: up),
null with fewer than two points}}}`. Positions are Google's, weighted by impressions; a
bucket where the key had no row is null, never 0.

`opportunities`: `{"days", "count", "by_rule": {"low_ctr", "near"}, "rules": {"many",
"some", "low_ctr", "high", "near"}, "pages_from", "pages_days", "rows"}`. Rules:
`low_ctr` when shown at least `many` times (the larger of 100 and 5 per stored day), a
click rate under 1% and an average position better than 8; `near` when the average
position is 8 to 20 and it was shown at least `some` times (the larger of 30 and 1 per
day). Each row `{"query", "rule", "clicks", "impressions", "ctr", "position", "page",
"pages", "page_share"}`: `page` is the page it showed most by impressions in
`query_page` (null when not known), `pages` how many pages, `page_share` that page's share
of its impressions. The first 300, by impressions, clicks, query.

`crosscheck` (Search Console only):

| field | type |
|---|---|
| `engine` | `"google"` |
| `days[]` | `{"day", "search_console_clicks", "skald_visits", "difference", "ratio"}` over the last 28 days that are final in Search Console and whole and verified in Skald. `skald_visits` is `search_landing` `engines.Google`; `difference` is visits minus clicks; `ratio` visits / clicks (null for 0 clicks) |
| `pages[]` | the 30 largest landing paths: `{"path", "search_console_clicks", "skald_visits", "difference"}`. Search Console's page addresses are cut to their path; two addresses of one path are added together |
| `totals` | the same four fields over the days |
| `left_out[]` | `{"day", "why"}`: days left out (withheld, not counted by Skald, partial, missing) |
| `notes[]` | why the two differ, in plain words (Pacific days, a click is not a visit, lost referrers, web results only, paths) |
| `flag` | a sentence when the last 7 days' ratio moved by more than half against the 21 before (both with at least 20 clicks): usually a tracking break; else null |
| `state` | `"no final Search Console days yet"` when there is nothing to compare |

The cross-check is a comparison, never a check: the two count different
things and are never expected to match.
