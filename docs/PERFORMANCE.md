# Performance

How fast Skald is, how to measure it, and what was changed to make it faster
(issue #2). No figure changed: every data file, compare answer and page story
came out the same before and after (see "Proof that no figure changed").

## How to run the benchmark

```sh
python3 tools/bench.py                       # 1x and 10x, about 5 minutes on a laptop
python3 tools/bench.py --scale 1x            # one size
python3 tools/bench.py --scale 100x          # the large size: slow to build, many GB
python3 tools/bench.py --json after.json --against before.json   # before | after table
python3 tools/bench.py --keep /tmp/bench     # keep the built installs to look at
```

It needs nothing but Python. It builds each size in a temporary folder and deletes it
afterwards (unless `--keep`). Addresses are documentation addresses (RFC 5737), hosts are
example.com, and the visitor key is a dummy.

## What is measured

The bench builds a synthetic install per size with the real pipeline: the last 7 days of each
site are synthetic logs collected by `skald collect` (people who render pages, scrapers that
do not, AI crawlers and assistants, search crawlers, monitors, scanner probes, our own
heartbeat, a sibling host). Older days are copies of those rows on earlier dates
(`tools/bench_data.py`), so a long history costs a copy, not a parse. Today has a log up to
noon. The install runs in sessions mode with an accounts file, and has a conversions file
with 90 days of conversions and browser journeys.

| size | requests/day per site | days | sites | pages | history file |
|------|----------------------|------|-------|-------|--------------|
| 1x   | 10,000 | 60  | 1 (+3 views) | 60  | 46 MB |
| 10x  | 10,000 | 300 | 2 | 200 | 421 MB |
| 100x | 20,000 | 400 | 8 | 600 | not run here |

1x has the request count and the days of the first live install, but its history is larger
than the live 5 MB file: the synthetic crawlers spread over more pages each day. So the times
err on the slow side.

Each operation is timed by wall clock; the median of its repeats:

- `live`: `skald live` (today's snapshot and the dashboard redraw, every site)
- `dashboard`: `skald dashboard` (every data file and CSV, every site and view)
- `audit --live`: the second count of today so far
- `backup`: `skald backup` (history, accounts and conversions, each restore-tested)
- `api ...`: real HTTP requests to the refresh helper, signed in with a session cookie:
  a data file, compare over 90 and 400 days (cold: the helper's parsed-blob cache emptied;
  warm: asked again), a page's story, the sites list, and nginx's auth check
- `session check`: `access.session_caller` alone (what every gated request pays)
- `mcp ...`: MCP tools through the protocol handler
- `conversions.json body`: `conversions_data.blob`, with its second count

## Results

Apple M3 Max, Python 3.11, SQLite 3.42. Before: the code before this change (2.1.0). After: with it.

| operation                | 1x before | 1x after | 10x before | 10x after |
|--------------------------|-----------|----------|------------|-----------|
| live                     | 2.62 s    | 2.13 s   | 9.35 s     | 6.20 s    |
| dashboard                | 1.90 s    | 1.45 s   | 7.68 s     | 4.95 s    |
| audit --live             | 571 ms    | 580 ms   | 1.23 s     | 1.20 s    |
| backup                   | 1.64 s    | 1.53 s   | 15.50 s    | 14.22 s   |
| api overview (data file) | 1.3 ms    | 1.0 ms   | 1.4 ms     | 1.2 ms    |
| api compare 90 d, cold   | 15 ms     | 13 ms    | 84 ms      | 79 ms     |
| api compare 90 d, warm   | 10 ms     | 7.9 ms   | 41 ms      | 32 ms     |
| api compare 400 d, cold  | 17 ms     | 14 ms    | 138 ms     | 126 ms    |
| api compare 400 d, warm  | 16 ms     | 9.5 ms   | 62 ms      | 46 ms     |
| api page story           | 20 ms     | 11 ms    | 327 ms     | 131 ms    |
| api sites list           | 1.1 ms    | 1.0 ms   | 1.1 ms     | 1.4 ms    |
| api auth check (nginx)   | 0.8 ms    | 0.8 ms   | 0.8 ms     | 0.9 ms    |
| session check (no HTTP)  | 0.7 ms    | 1.4 ms   | 0.6 ms     | 1.0 ms    |
| mcp list_sites           | 0.5 ms    | 0.9 ms   | 2.1 ms     | 2.6 ms    |
| mcp overview             | 0.7 ms    | 0.9 ms   | 1.3 ms     | 1.5 ms    |
| mcp breakdown            | 2.1 ms    | 2.8 ms   | 5.5 ms     | 6.1 ms    |
| mcp top_pages            | 1.7 ms    | 1.9 ms   | 4.6 ms     | 4.5 ms    |
| mcp ai_activity          | 2.2 ms    | 2.5 ms   | 5.2 ms     | 5.5 ms    |
| mcp compare              | 11 ms     | 10 ms    | 16 ms      | 15 ms     |
| mcp page_story           | 18 ms     | 12 ms    | 338 ms     | 133 ms    |
| mcp site_health          | 2.1 ms    | 2.3 ms   | 5.8 ms     | 6.2 ms    |
| mcp data_quality         | 0.8 ms    | 0.7 ms   | 1.5 ms     | 1.6 ms    |
| mcp conversions          | 0.6 ms    | 0.7 ms   | 1.4 ms     | 1.2 ms    |
| conversions.json body    | 90 ms     | 69 ms    | 303 ms     | 294 ms    |

How to read it:

- The big wins are the 2-minute `live` run (-34% at 10x) and the data files (-36%), and
  the page story (-60%).
- Rows under about 2 ms move by noise from run to run (single calls on a busy laptop). The
  session check, measured A/B in one process (min of 5 x 200 calls), went from 0.55 ms to
  0.47 ms; it was never a bottleneck.
- `backup` is disk and gzip; it scales with the file and was not a target.
- At 1x everything a person waits for answers in well under 50 ms.

## What was slow, and what changed

Found by profiling `live` and `dashboard` at 10x, and by tracing every SQL statement the
paths above run, with `EXPLAIN QUERY PLAN` and a timing for each. SQL was rarely the cost:
almost every read keys on `(site, day, ...)`, which the primary keys already serve. Python
was the cost. Each fix keeps the output byte for byte.

| where | what it did | now |
|-------|-------------|-----|
| `export_visits._day_stats` | `out.setdefault(d, VisitStats())` built a new VisitStats (a dozen Counters) for every row, not every day: 370,000 at 10x | one per day |
| `data_files._visit_stats` | asked history for the measured days once per day (an N+1) | once |
| `data_files.Page` | parsed every day kind for 180 days on every page, including the six largest that no builder reads from the Page (`ai_fetches`, `page_firsts`, `crawler_paths`, `cube`, `visit_cube`, `page_counts`) | those six are left out; asking a Page for one raises, so it can never read as "not recorded" |
| `dashboard_webapp.build` | `history.period(key, d, d)` per day: 5 queries x 180 days per page | `History.periods`: 4 queries for all the days, each day summed by the same code as `period` |
| `data_reports._visitor_days` | for each visitor and day, re-parsed every earlier day's date (quadratic) | the previous day alone decides it (the days are in order) |
| `lifecycle.story` | parsed every day's page blob twice (first seen, then the series) | once, keeping only the page asked for |
| `lifecycle.build` (page_index.json) | worked out the same site's index again for each view | once per site per run |
| `ai_likely.fetch_index` | `strptime` on every stored fetch minute | read by position (strptime for anything unusual) |
| `compare._metrics` | `kind = A OR (kind = B AND name = C)` made SQLite read every count of every day | `kind IN (A, B) AND ...`: a seek in the key (14.6 ms to 1.6 ms at 10x) |
| `quality` | one query per day for its lines | one query |
| `accounts.connect`, `conversions.connect` | ran the whole SCHEMA script (25 statements) on every connection, i.e. every signed-in request | skipped when the file is stamped with this SCHEMA and version (`schema_stamp` in `meta`); any change to SCHEMA changes the stamp, so the script runs again once |

## Indexes

Each through its database's normal upgrade path: a version bump, statements that are
idempotent (`CREATE INDEX IF NOT EXISTS`), applied in one transaction when missing. On the
live 5 MB history the upgrade takes milliseconds (0.8 s on the 421 MB 10x file). An index
changes no row, so no backup copy is made for one (the history upgrade still copies the file
aside when it adds a column or a table). Older code refuses a newer file, as before.

| database | version | index | why |
|----------|---------|-------|-----|
| history | 11 to 12 | `day_extras_day (day, kind)` | the daily prune (`DELETE ... WHERE day < ? AND kind IN (...)`) read the whole table: 500 ms cold at 10x, now under 1 ms |
| history | 11 to 12 | `visitor_days_day (day)`, `journeys_day (day)` | the same prune for the 30-day hashes and the 7-day journeys |
| accounts | 4 to 5 | `sites_org (org_id, name)` | an organisation's sites: read on every signed-in request (the member and admin site lists) |
| accounts | 4 to 5 | `settings_key (key, scope)` | a setting by key over its scopes (settings applied at every run) |
| accounts | 4 to 5 | `tokens_org (org_id)`, `invites_org (org_id, email)` | an organisation's tokens and invites (Settings, plan limits) |
| conversions | 2 to 3 | `journeys_site_at (site, at)` | a site's browser journeys in a time range (pages before converting, the audit's recount); before, every journey of the site was read |

Not added: an index for `page_milestones ORDER BY at` (a few thousand rows, the sort is
cheap), and secondary indexes on `counts` (every hot query seeks `(site, day, kind)`).
The cost: about 5% on the 1x history file, 2% at 10x.

## PRAGMA settings

- **History stays in rollback-journal mode.** WAL would let the helper read during the daily
  collect, but a read-only connection (`History.reader`, the helper's user) to a WAL file
  needs write access to the `-shm` file or the folder. Not worth that risk.
- **busy_timeout**: the history uses Python's default 5 s; accounts and conversions set
  10 s and run in WAL (unchanged).
- **synchronous** left at the default (FULL). NORMAL is only safe in WAL, and accounts
  (sessions, the audit log) and conversions are written rarely.
- **mmap_size and cache_size** were tried on the history (256 MB and 64 MB): `dashboard` at
  10x moved within noise (7.4-7.6 s against 7.4-8.7 s). The OS page cache already holds the
  file. Not added.

## Proof that no figure changed

- `tests/test_performance.py` builds one install (six collected days of synthetic traffic,
  three views, returning visitors, today's snapshot), then draws every data file twice: with
  the code as it is, and with the replaced code put back (kept in the test as references).
  Every file must be equal (the build time set aside). The same for every page's story, the
  compare metrics query, `History.periods` against `period` day by day (down to the order of
  every top list), and the three upgrades. A deliberate one-day change to the repeat-visitor
  window makes it fail.
- On the 1x and 10x installs, every data file, every CSV and HTML page, compare over five
  ranges, three views and five filters, and the story of every page were written before and
  after the change and compared: identical. One difference showed up at 10x and is not from
  this change: `insights.json` orders tied insights by Python's string hashing, which changes
  per process (`insights.py`, the set in its ranking). With `PYTHONHASHSEED` fixed, the old
  and new code give identical files.
- The full test suite passes.

## Left for later

- `insights.json` order of ties depends on the process (above). A stable sort key would fix
  it; it is a change of output, so not done here.
- `live` at 10x is still 6 s for two sites; most of it is now reading today's log
  (`window.analyse_window_views`) and the CSV exports (`dashboard.write_exports`, 30-day
  tables recomputed every 2 minutes). Caching the CSVs between live runs is the next step.
- `backup` writes the weekly gzip at the default level; a lower level would be faster.
- The 100x size was not run for this report.
