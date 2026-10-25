# Data contract: the JSON files beside the dashboard

The static dashboard (`dashboard.py`, no script) and the web app
(`skald/webapp/`) read the same figures. Every render (`skald
dashboard`, `skald live` every 2 minutes, `run-daily`) writes them:

```
<dashboard.out>/<site>/data/<name>.json            the whole site
<dashboard.out>/<site>/<view-slug>/data/<name>.json each dashboard.views entry
```

All files are written atomically (temp file + rename), mode 0644, behind the
same password as the page. **Schema version 1.** A field may be added without
a version change; a field is never renamed or removed without one.

## Rules every file follows

- **Envelope.** Every file is an object with:

  | field | type | meaning |
  |---|---|---|
  | `schema_version` | int | 1 |
  | `generated_at` | string, ISO 8601 with offset | when this file was written |
  | `site` | string | `site.name`, e.g. `"example.com"` |
  | `view` | `null` or `{"slug": str, "name": str, "rule": str}` | null for the whole site |
  | `timezone` | string | IANA name days and hours are cut in, e.g. `"America/New_York"` |

- **Days.** Most files carry `days`: one entry per local day for the 180
  days ending yesterday (`anchor`), oldest first, so the app can sum any
  range and the previous range of the same length. Each entry has `day`
  (`"YYYY-MM-DD"`) and `state`:

  | state | figures present | meaning |
  |---|---|---|
  | `ok` | yes | verified, whole day |
  | `partial` | yes, plus `partial_from` / `partial_until` (ISO or null) | verified, the logs did not cover the whole day: never compare or sum it with whole days |
  | `withheld` | no (`problems`: string) | failed verify or the audit: never show figures |
  | `missing` | no | not collected |
  | `before` | no | before history starts |

  An entry whose figures were not counted on that day (collected by an
  older version) has the field set to `null`, never `0`.
- **Today.** Files with a `today` block take it from the live snapshot:
  `today` is `null` when there is none for today; otherwise it has `state`
  (`ok`, `withheld`, `empty`), `from`, `until` (ISO) and, when `ok`, the
  same figures as a day entry. `live.json` also keeps `events`: the 20
  latest AI fetches and citation clicks, without addresses (`at`, `kind`,
  `who`, `path`).
- **Counters** are objects `{label: int}`. A key `"(all others)"` is the
  folded tail of a longer list; it is a real count and keeps the sums.
- **Hours** are `"00"` to `"23"` in `timezone`.
- **Countries** are two-letter ISO codes. A request's country is the log
  line's own (nginx `cc=`, Cloudflare's `CF-IPCountry`, a CDN log's country
  field). A line with none (Caddy JSON, a plain combined log) gets its
  address's country from the GeoIP file `logs.country_db` (a MaxMind-format
  `.mmdb`, e.g. DB-IP's free country file), when one is set (since 2.8.0).
  The line's own country always wins. Both counting roads (main and audit)
  look it up the same way. With no country and no file, the country is
  `""` / `Unknown` (shown as Not recorded), never guessed.
- **Cities** (2.12.0) are `"City, Region, CC"` (`"Toronto, Ontario, CA"`; the
  region left out when missing or the same as the city), from the city file
  `logs.city_db` (DB-IP's free "IP to City Lite" `.mmdb`), people only, at
  each visit's first page; never a city in another country than the line's
  (CLASSIFICATION.md). Only where the file is set: then history keeps
  `people_city_visits` per day (readers by city, top 50 and `"(all others)"`,
  `"Unknown"` for none, adding up to the readers; one `"Unknown": 0` row on a
  day without a reader), a day's `by.city` in `app.json` and the live
  snapshot's `breakdowns.by.city`; a journey gets `city` only when known;
  `realtime.cities` ([docs/DATA-CONTRACT-REALTIME.md](docs/DATA-CONTRACT-REALTIME.md)). A period sums cities only when each of its days
  has them. The audit recounts them by its own road (`audit_cities.py`: its
  own label from the same file's raw record). A day stored without cities is
  skipped by the audit (collected before the file was set). `app.json`'s
  `cities` (bool) says whether a city file is set.
- **Groups**: `people`, `answer_engines`, `search_engines`, `bots`, `ours`.
- **Privacy.** No data file carries an IP address, a user agent or a visitor
  key, except `ai_activity.json`'s `today.events[].ip` and `requests.json`'s
  `rows[].ip` (the owner's decisions, 2026-10-07: shown on the private page
  only, read from the raw log; `requests.json` holds only its window). The
  history (`history.sqlite`) never holds an address. Since 2.4.0 a site may
  keep each reader's visit with its address and user agent, and a lead's name
  and email, in `conversions.sqlite`: settings `privacy.keep_ips` (full,
  short or off since 2.15.0: short keeps each address shortened),
  `privacy.keep_days` (395) and `conversions.identity`, on for a new install,
  off for one upgraded from before 2.4.0 (`people/policy.py`). Those are not
  data files: [docs/DATA-CONTRACT-PEOPLE.md](docs/DATA-CONTRACT-PEOPLE.md).
  An address removed with `skald forget --ip` is shown as `"(removed)"` from
  then on. Journeys are anonymous and kept `journey_days` days; their `first_touch` and `seq` (2.12.0) are in DATA-CONTRACT-PEOPLE.md.
- **Release 3 files** (2026-10-08): `robots.json`, `speed.json`,
  `funnels.json`, `sites.json`, `page_index.json` - and the API, users and
  roles, compare and page lifecycle below.
- **Release 2 files** (2026-10-07): `requests.json`, `alerts.json`,
  `quality.json`, `markers.json`, `leads.json`, `cube.json`, and new fields
  in `bots.json`; `favicons.json` in the site's folder only. They are listed in `overview.json`'s `files` like the others.
  `alerts.json`, `markers.json` and `leads.json` are the same for the site
  and every view (`view` in the envelope says which page wrote it).

---

## overview.json

Meta for the app, and one row of headline figures per day.

| field | type | meaning |
|---|---|---|
| `anchor` | date | yesterday, the last day `days` covers |
| `today` | date string | the local date now (for the live block, see live.json) |
| `first_day` | date or null | first day history holds for this key |
| `views` | `[{"slug","name","rule"}]` | all configured views (same list on every page) |
| `refresh_button` | bool | the Refresh now endpoint exists |
| `credit` | `{"text","url"}` or null | country data attribution, show beside countries: `report.country_credit`, else DB-IP's credit when `logs.country_db` is a DB-IP file |
| `journey_days` | int | how long journeys are kept |
| `files` | `[string]` | the data files written beside this one |
| `days[]` | | see below |

`days[]` entry (when `ok`/`partial`):

| field | type |
|---|---|
| `groups` | `{group: {"hits","views","visits","readers","probes"}}` (`readers` may be null) |
| `cited_visits` | int: readers who followed an AI citation |
| `ai_tiers` | `{"training": int, "asked": int}` |
| `search_indexing` | int: search-engine fetches minus ads quality checks |
| `ads_checks` | int |
| `not_found_people` | int or null: 404s served to people |
| `server_errors` | int or null: 5xx to anyone |
| `visits` | `{"visits","views","one_page","median_seconds","in_app","not_found","posted"}` or null |
| `returning` | `{"readers": int, "returning": int}` or null: readers seen on an earlier day within 30 days (keyed hash, see ai_activity.json) |

```json
{"schema_version":1,"generated_at":"2026-10-08T07:16:02-04:00","site":"example.com","view":null,
 "timezone":"America/New_York","anchor":"2026-10-07","today":"2026-10-08","first_day":"2026-10-06",
 "views":[{"slug":"us-english","name":"US English","rule":"all paths except under /ca/"}],
 "refresh_button":true,"credit":{"text":"IP geolocation by DB-IP","url":"https://db-ip.com"},
 "journey_days":7,"files":["overview.json","live.json"],
 "days":[{"day":"2026-10-07","state":"ok",
   "groups":{"people":{"hits":3120,"views":190,"visits":410,"readers":140,"probes":0}},
   "cited_visits":2,"ai_tiers":{"training":5100,"asked":12},"search_indexing":600,"ads_checks":40,
   "not_found_people":9,"server_errors":0,
   "visits":{"visits":140,"views":190,"one_page":118,"median_seconds":3,"in_app":6,"not_found":2,"posted":1},
   "returning":{"readers":140,"returning":11}}]}
```

## live.json

Today so far: the live snapshot (`live.py`) as written every 2 minutes,
without the journeys (in `visits.json`) and without the AI events (in
`ai_activity.json`). Fields: `state` (`ok` / `withheld` / `empty`), `day`,
`from`, `until`, `generated_at` (of the snapshot), `problems`, `requests`,
`groups`, `people` (`visits`, `readers`, `views`, `cited_visits`, `cited_by`,
`pages`, `countries`), `ai` (`training`/`asked` by name), `ai_tiers`,
`ai_pages`, `search`, `bots` (`requests`, `probes`), `ours`, `ours_labels`,
`other_hosts`, `unfiltered`, `breakdowns` (same shape as a breakdowns.json
day), `visits` (same shape as a visits.json `stats`), `journeys_total`.
`live.stale` is true when the snapshot is not for today.

The snapshot file itself (`live-<site>.json` beside history) and the requests
feed (`live-<site>-requests.json`) also carry `read_upto`: `{file name: bytes}`,
each plain (uncompressed) log file's size when the live run began. The run
reads each file only that far (a line cut at the limit is not read), and
`audit --live` reads only as far, so lines appended meanwhile change neither
side. A file without `read_upto` (an older one) is recounted whole.

```json
{"schema_version":1,"generated_at":"...","site":"example.com","view":null,"timezone":"America/New_York",
 "stale":false,"state":"ok","day":"2026-10-08","from":"2026-10-08T00:00:00-04:00",
 "until":"2026-10-08T13:00:16-04:00","requests":14884,"groups":{"people":3100}}
```

## visits.json

One journey per visit. A visit is one address and user agent with no gap over
`report.session_gap_minutes`, and a page view arriving from a new outside
source (an assistant, another website, a search engine, social, email, a
tagged link) starts a new one (SOP.md, "What a visit is"; days collected from
2026-10-12 on).

| field | type |
|---|---|
| `journey_days` | int |
| `days[]` | `{"day","state","stats"}` - `stats` is null when not counted |
| `journeys` | stored journeys, newest first (only the last `journey_days` days) |
| `today` | `{"state","stats","journeys","journeys_total"}` (journeys newest first, at most 1000) |

`stats`: `visits` int; `pages` `{"<n pages loaded>": visits}`; `trail`
`{"<n pages seen>": visits}`; `seconds` `{"<bucket seconds>": visits}`;
`exits` `{path: visits}`; `steps` `{"/a → /b": times}`; `flags`
`{"not_found"|"posted"|"in_app": visits}`; `entries`, `source`, `country`,
`device` `{label: visits}`; plus computed `views`, `per_visit` (float or
null), `one_page`, `median_seconds` (int or null).

A journey: `day`, `start` (`"YYYY-MM-DDTHH:MM"`, local), `country` (ISO code
or `"Unknown"`), `device`, `browser`, `os`, `source` (one of the source types
below), `via` (assistant name like `"ChatGPT"`, a referrer host, or `""`),
`campaign` (`"source / medium / campaign"` or `""`), `landing`, `exit`,
`pages` (loaded), `seen` (incl. in-app), `in_app`, `trail`
(`[[path, "page"|"app"]]`, at most 50), `seconds`, `not_found`, `posted`,
`summary` (one readable line), `at` (seconds into the visit of each `trail`
entry, bucketed: [docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md)), and from schema 9: `utm`
(`{"source","medium","campaign","term","content"}`, only those present),
`paid` (network name or `""`), `ref_param` (`ref`/`source`/`via` query value
or `""`), `ref_host`, `ref_page` (host + path, other websites only),
`search_terms` (or `""`), `returning` (bool or null), `days_seen_30d` (int or
null), `likely_ai` (only on a visit likely sent by an AI assistant, an estimate),
`likely_direct` (only on a Direct visit with a likely cause, an estimate: `{"reason"`:
`"checkout"|"in_app"|"shared"`, `"detail"`, and `"minutes"` for a link preview`}`:
[docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md#day-kind-direct_likely-campaignsjson)),
`ai_read` (only on an AI visit whose assistant fetched pages just before it, at most 10:
[docs/DATA-CONTRACT-AI-LIKELY.md](docs/DATA-CONTRACT-AI-LIKELY.md)). Source types: `AI assistant`, `Search engine`, `Social media`,
`Email`, `Other website`, `This site`, `Tagged link`, `Direct or unknown` (stored names; people read **Direct** and, for `Unknown`, **Not recorded**: `labels.py`).

`pages` stays the page views (what both roads add up); `seen` = `pages` + `in_app`.
Every view of a visit states both: "3 pages (2 seen in the browser)" is `seen` with
`in_app` named (`visits.pages_words`, `webapp/js/visitpages.js`); the `summary` line
says it the same way. app.json's journeys carry `seen` and `in_app` too, and real
time's newest visits carry `in_app`.

```json
{"journey_days":7,"days":[{"day":"2026-10-07","state":"ok","stats":{"visits":140,"pages":{"1":118,"2":15}}}],
 "journeys":[{"day":"2026-10-07","start":"2026-10-07T12:41","country":"CA","device":"Mobile",
   "browser":"Safari","os":"iOS","source":"AI assistant","via":"ChatGPT","campaign":"",
   "landing":"/compare/x/","exit":"/pricing/","pages":2,"seen":3,"in_app":1,
   "trail":[["/compare/x/","page"],["/features/","app"],["/pricing/","page"]],"seconds":100,
   "not_found":0,"posted":0,"utm":{"source":"chatgpt.com"},"paid":"","ref_param":"",
   "ref_host":"chatgpt.com","ref_page":"","search_terms":"","returning":false,"days_seen_30d":1,
   "summary":"12:41 · 🇨🇦 Canada · Mobile, Safari on iOS · from ChatGPT → /compare/x/ → /features/ (in-app) → /pricing/ · 3 pages (1 seen in the browser) · 1m 40s"}],
 "today":{"state":"ok","stats":{"visits":12},"journeys":[],"journeys_total":12}}
```

## hourly.json

| field | type |
|---|---|
| `days[]` | `{"day","state","hours"}`; `hours` null when not counted |
| `today` | `{"state","until","hours"}` (hours up to now) |
| `averages` | `{"7d": {...}, "30d": {...}}`: per hour, the mean over the whole `ok` days in the last 7 / 30 days, each `{"days": int, "hours": {hour: {metric: float}}}` |
| `busiest` | `{"7d": [{"hour","readers"}], "30d": [...], "today": [...]}`: top 3 hours by readers |

`hours`: `{hour: {"people","answer_engines","search_engines","bots","ours"
(requests), "readers" (by first page), "ai_asked","ai_training"
(requests), "server_errors"}}`. Every group's 24 hours add up to its day
total (verified and audited).

`hours_utc` (days[] and today, from 2026-10-07; null before): the same
figures keyed by the UTC hour they fall in, `"YYYY-MM-DDTHH"` (UTC), only
hours with something in them. Re-bucket these to show any time zone
exactly: the day the clocks go back has two local `"01"` hours, merged in
`hours`, apart here; the day they go forward has no local `"02"`. Each
metric's UTC hours add up to its local hours (verified) and the audit
recounts every UTC hour. Days are still cut midnight to midnight in
`timezone`, so a UTC hour at a day's edge belongs to the day it was
counted in. For readers by hour in another zone use `hours_utc` -
`breakdowns.json`'s `readers_by.hour` stays in site time.

```json
{"days":[{"day":"2026-10-07","state":"ok","hours":{"09":{"people":210,"answer_engines":400,
  "search_engines":30,"bots":90,"ours":12,"readers":14,"ai_asked":1,"ai_training":399,"server_errors":0}}}],
 "averages":{"7d":{"days":1,"hours":{"09":{"readers":14.0}}}},"busiest":{"7d":[{"hour":"09","readers":14.0}]}}
```

## breakdowns.json

`days[]` and `today`, each (figures null when not counted):

| field | type |
|---|---|
| `readers_by` | `{"country","browser","os","device","source","referrer","campaign","landing","hour": {label: readers}}` - each adds up to the day's readers |
| `pages` | `{path: page views by people}` |
| `ai_pages` | `{path: answer-engine fetches}` |
| `cited_by` | `{assistant: readers}` |
| `engines` | `{"training": {name: n}, "asked": {name: n}}` |
| `search` | `{crawler: n}` |

## health.json

`days[]` and `today`: `statuses` `{group: {"2xx","3xx","404","4xx","5xx","other"}}`,
`not_found` `{path: 404s to people}`, `server_errors` `{path: n}`, `speeds`
`{bucket: page views}`, `slow_pages` `{path: n}`, `posts` `{group: {"total": n,
"pages": {path: n}}}`. Speed buckets: `under 0.2 s`, `0.2 to 0.5 s`,
`0.5 to 1 s`, `1 to 3 s`, `3 s or more`, `not logged`.

## bots.json

Moved to [docs/DATA-CONTRACT-BOTS.md](docs/DATA-CONTRACT-BOTS.md#botsjson).

## requests.json

Every request of the last `window_hours` hours, newest first - Site >
Requests. Written by every live run (2 minutes). **Private**: it holds
raw addresses; nothing of it is stored in history, and the file holds only
its window.

| field | type | meaning |
|---|---|---|
| `state` | `"ok"` / `"empty"` / `"stale"` | `stale`: the last live run is older than 10 minutes, rows as they were then |
| `window_hours` | int | 6 by default (`requests.window_hours`) |
| `cap` | int | most rows kept (`requests.cap`, default 5000) |
| `from`, `until` | ISO | the window read |
| `total` | int | requests in the window on this page (a view: its paths only) |
| `shown` | int | rows in the file (newest `cap`) |
| `truncated` | bool | `total > shown` |
| `by_group` | `{group: int}` | over the whole window, not just the rows shown; groups plus `"excluded"` (another host on the same server). Adds up to `total`. |
| `rows[]` | | below |

A row:

| field | type | meaning |
|---|---|---|
| `at` | ISO local, seconds | when the server logged it |
| `ip` | string | the address, or `"(removed)"` after `skald forget` |
| `country`, `country_name` | string | ISO code (the line's own, else `logs.country_db`'s) or `""` |
| `host` | string | the host asked for |
| `method` | string | `GET`, `POST`, `HEAD`, ... or `""` (an empty or garbled request line) |
| `path` | string | without the query, at most 300 characters |
| `query` | string | the query string with every value that could be personal replaced by `…` (attribution tags, `_rsc` and short plain values are kept; click ids show as `(id)`); `""` when none |
| `status` | int | |
| `bytes` | int or null | body bytes sent |
| `ms` | int or null | server time in milliseconds |
| `ref_host`, `ref_path` | string | the referrer's host and path (never its query), `""` when none |
| `agent` | string | the browser family (`Chrome`, `Safari`, `LinkedIn app`, ...) for a browser, else the crawler or tool name (`GPTBot`, `curl`, `(no user agent)`) |
| `os`, `device` | string | from the user agent (`macOS`, `iOS`, ... / `Desktop`, `Mobile`, `Tablet`); bots usually `Other` / `Desktop` |
| `group` | string | `people`, `answer_engines`, `search_engines`, `bots`, `ours`, or `excluded` |
| `rule` | string | why it is in that group, in words: `"people: reader"`, `"people: asset"`, `"people: Next.js payload (_rsc)"` (a prefetch, or a line without the `rsc_prefetch=` field; a Next.js navigation on a line with it is `kind` `"page"`, `page_view` true), `"people: reader from chatgpt.com"`, `"ours: Office Mac (Morgan)"`, `"AI asked: ChatGPT-User"`, `"AI training: GPTBot"`, `"search: Googlebot"`, `"bot: meta-webindexer"`, `"bot: scanner probe"`, `"bot: scanner (asked for secret or config files)"` (any other request of an address and agent that asked for a secret or config file that day, CLASSIFICATION.md rule 6b), `"bot: link preview: Slack"`, `"bot: claims to be Googlebot"`, `"bot: browser-like crawler (robots.txt or sitemap, no rendering)"`, `"bot: browser-like, never rendered the page"`, `"excluded: other host"` |
| `kind` | string | what was asked for: `page`, `rsc`, `asset`, `beacon`, `crawler_file`, `redirect`, `not_modified`, `not_found`, `client_error`, `server_error`, `post` (a form or API call the site's own pages sent), `script_event` (the script tag's events posted to Skald's own `/traffic-beacon` or `/traffic-js/`: never a form post), `skald_endpoint` (a call to `/traffic-hooks/` or `/traffic-ingest/`), `other` |
| `page_view` | bool | counted as a page view in its group |
| `assistant` | string | the AI assistant: the crawler's name, or the assistant a reader came from; `""` |
| `source` | string | people rows: the source type of the visit the request belongs to (same words as journeys: `AI assistant`, `Search engine`, `Social media`, `Email`, `Other website`, `This site`, `Tagged link`, `Direct or unknown`) - the source of the visit's first page view, or of its first request until a page is read; a page from a new outside source starts a new visit (SOP.md, "What a visit is"), as in the journeys; `""` for every other group |
| `utm` | object | `{"source","medium","campaign","term","content"}`, only those present |
| `verified` | string or null | `verified`, `unverified`, `spoofed` for a named assistant or search crawler; null for everyone else |
| `flags` | `[string]` | any of `hosting_network`, `fan_out`, `bare_mozilla` (fake-browser signs), `probe`, `legacy_path` (an old-site URL kept out of the probes), `old_format` (a line in the old log format, no host or country), `duplicate` (byte-identical to an earlier line in the same second) |

```json
{"state":"ok","window_hours":6,"cap":5000,"from":"2026-10-08T07:00:00-04:00","until":"2026-10-08T13:00:16-04:00",
 "total":2412,"shown":2412,"truncated":false,
 "by_group":{"people":700,"answer_engines":1200,"search_engines":300,"bots":180,"ours":30,"excluded":2},
 "rows":[{"at":"2026-10-08T12:59:57-04:00","ip":"192.0.2.7","country":"CA","country_name":"Canada","host":"www.example.com",
   "method":"GET","path":"/pricing/","query":"_rsc=1x2y","status":200,"bytes":10812,"ms":7,
   "ref_host":"www.example.com","ref_path":"/case-studies/","agent":"Chrome","os":"macOS","device":"Desktop",
   "group":"people","rule":"people: Next.js payload (_rsc)","kind":"rsc","page_view":false,"assistant":"",
   "utm":{},"verified":null,"flags":[]}]}
```

## cube.json

The drill-down cube: readers' visits per day by country, landing page,
source, assistant and device, for the last 90 days and today (`cube.py`).

| field | type |
|---|---|
| `dims` | `["country","landing","source","assistant","device","visits"]` - the order of each row |
| `cap` | int (300): most combinations kept per day |
| `days_kept` | 90 |
| `days[]` | `{"day","state", "rows": [[country, landing, source, assistant, device, visits]] or null, "folded": bool or null}` |
| `today` | the snapshot's, same fields, or null |

`assistant` is the assistant's name (`"ChatGPT"`, `"Perplexity"`, as in
journeys' `via`) when `source` is `"AI assistant"`, else `""`. Every day's
rows add up to its visits (= readers). A day with more than `cap`
combinations keeps the largest and folds the rest into one row whose five
labels are `"(all others)"` (`folded: true`): its visits count in every
total but cannot be sliced. While a day is not folded, each field's totals
equal that day's readers breakdowns exactly (verify and the audit hold it).

## Which drill-downs are exact

| Slice | Over | Exact? |
|---|---|---|
| Any combination of a visit's labels, pages in order, length, flags, UTMs | today, and the last `journey_days` (7) days | exact: `visits.json` journeys, one per visit |
| Any combination of request fields (group, rule, path, status, agent, country, source, flags) | the last 6 hours | exact up to `cap` rows; `by_group` and `total` are always whole (`requests.json`) |
| Country x landing page x source x assistant x device (visits) | 90 days | exact while a day is not `folded` (cube.json) |
| One dimension at a time: readers by country, browser, OS, device, source, referrer, campaign, landing page, hour | 180 days | exact; lists longer than 50 end in an `"(all others)"` row that keeps the sum |
| Pages, AI pages, engines, bots, 404 paths | 180 days | top-N per day (50 or the stated limit); sums over days miss a page that never made a day's list |
| Pages x anything else (country, source) | 30 days | `pages.json` per page: sources, assistants and countries of its readers, top lists |
| Browser or OS crossed with anything | beyond 7 days | not stored; journeys only |

## favicons.json

Small icons of referring sites, fetched by skald itself from each
site (never a third-party favicon service). Written in the **site's** data
folder only: a view page reads `../data/favicons.json`, and its paths are
relative to that folder.

```json
{"schema_version":1,"generated_at":"2026-10-07T20:10:00+00:00",
 "hosts":{"linkedin.com":"favicons/linkedin.com.ico","www.linkedin.com":"favicons/linkedin.com.ico"}}
```

`hosts` lists only hosts that have a file, under both the bare and `www.`
form, keyed like `ref_host`. Files are raster images of at most 50 KB, as
fetched (`.ico`, `.png`, `.gif`, `.jpg`, `.webp`) - 32x32 PNG when the
server has Pillow (it does not today). Fetched for new hosts on each live
run (10 at most) and in run-daily, again after 30 days; switched on by
`dashboard.favicons: true`.

## robots.json

Moved to [docs/DATA-CONTRACT-BOTS.md](docs/DATA-CONTRACT-BOTS.md#robotsjson).

## crawler_cost.json

Moved to [docs/DATA-CONTRACT-BOTS.md](docs/DATA-CONTRACT-BOTS.md#crawler_costjson).

## realtime.json

Moved to [docs/DATA-CONTRACT-REALTIME.md](docs/DATA-CONTRACT-REALTIME.md#realtimejson).

Yesterday at this hour (`by_now`, 2.13): [docs/DATA-CONTRACT-REALTIME.md](docs/DATA-CONTRACT-REALTIME.md#yesterday-at-this-hour-the-snapshots-by_now-213).

## speed.json

Real page speed from Google PageSpeed Insights (`pagespeed.py`), once a day
after run-daily, for the top 5 landing pages of the day before, phone and
desktop. Server time (`ours.json`) is unchanged.

| field | type |
|---|---|
| `source` | `"Google PageSpeed Insights v5"` |
| `days[]` | `{"day","tests": [{"url","path","strategy" ("mobile"/"desktop"),"ok": bool,"error": string or null,"score": 0-100 or null (lab performance),"lab": {"lcp_ms","cls","tbt_ms","fcp_ms","si_ms"},"field": {"lcp_ms","cls","inp_ms","category"} or null (real Chrome users, when Google has enough of them),"origin_field": same or null}]}` for the last 30 days, oldest first |
| `latest` | the newest test per (path, strategy) |
| `trend` | `{"mobile": [{"day","score","lcp_ms","cls","inp_ms"}], "desktop": [...]}`: the site's median over the day's tested pages |
| `status` | `{"state","day","message","errors"?}` for the newest tested day: `"ok"` (Google answered at least one test), `"failing"` (it answered none; `message` says so in plain words - HTTP 429 or a quota error: "Not working: Google refused every test. A free PageSpeed API key is needed (PSI_API_KEY in /etc/skald/env)."; `errors` the distinct reasons), or `"not tested"`. A run with no test answered is also recorded as failed in runs.json. |

## funnels.json

Funnels over visits (`funnels.py`), the defaults and the ones saved on the
page. Steps are visits that reached each step in order, from the
anonymous journeys of the last `journey_days` (7) days and today; the
lead steps come from the CMS (aggregates, by first-touch source) and are
never divided per visit.

| field | type |
|---|---|
| `funnels[]` | `{"name","saved_by" (user or "default"),"saved_at","source" (a source type or assistant, or null = all),"steps": [step],"result": {"first","last","visits","steps": [{"label","kind","n","of_previous_pct","of_first_pct","drop"}]},"long": {"days": 90, "first_step": int} or null,"history": {...} or null (a default funnel)}` - `history` below |
| `api` | `{"list": "funnels", "save": "funnels/save", "delete": "funnels/delete"}` relative to the page |

A step: `{"label","kind": "path" | "lead" | "any","match": "equals" | "starts_with" | "segment" | "contains" (path steps),"paths": [path] (any of them),"types": ["signup",...] (lead steps)}`. A first step of kind `any` is the visit's start: every visit reaches it and it uses no page. An event step `{"label","kind":"event","events":["cta_click",...]}` counts people's in-page events of those kinds (events.json, whole days and today) over the same days, by the event's source type when the funnel has a source; like a lead step it has no percentages and is never divided per visit (`n` null when the beacon is off).
A visit reaches a path step when one of its pages (loaded or in-app) matches,
after it reached the step before. `long.first_step` is the first step's
visits over 90 days from cube.json, when the first step is a landing-page
rule. Saving and deleting are for admins only (see Users and roles).

## sites.json

The sites this install reports on, for the site switcher; written at the
dashboard's root (`<dashboard.out>/sites.json`) and in each site's data
folder.

```json
{"schema_version":1,"generated_at":"...","sites":[{"name":"example.com","slug":"example.com",
 "path":"example.com/","views":[{"slug":"us-english","name":"US English"}],
 "first_day":"2026-10-06","last_day":"2026-10-07","waiting":false,"live":true,
 "logo":{"url":"example.com/logo?v=3f2a9c1b07de","letter":"W","color":"#0f766e","source":"auto","kind":"png"},
 "today":{"day":"2026-10-08","visitors":12,"leads":2,"demos":1,"live":true,"timezone":"America/New_York"}}],
 "current":"example.com"}
```

From 2.6.0 each site also has (`site_picker.py`, `site_logos.py`; the helper fills both in
as they are at that moment when it answers, in sessions mode):

- `logo`: `url` is the logo's address relative to the dashboard's root, carrying a hash of
  the file so a new logo is a new address (served by the helper, `<site>/logo`), or null
  while the site shows its letter; `letter` and `color` (one of four) are that fallback;
  `source` is `site.logo.source` (`auto`, `upload`, `letter`); `kind` the stored type.
- `today`: today so far, for the site picker and the switcher. Read, never counted here:
  `visitors` is live.json's `people.readers` (the Overview's Visitors for Today) when the
  live count is for today and `ok`; `leads` and `demos` are today's `days[]` entry of
  conversions.json summed like the dashboard (finished stages of `lead_actions`, of
  `demo_actions`), only when that day is `ok` (matched by the second count). Anything not
  known is null, shown as "-", never 0. `live` is true while the live count is under 15
  minutes old; `day` and `timezone` are the live count's.

## Compare: any two date ranges (helper API)

`GET <page>/api/compare?a=YYYY-MM-DD..YYYY-MM-DD&b=YYYY-MM-DD..YYYY-MM-DD`
(same password; also `skald compare --a .. --b ..`). Optional filters, each
`name=value`: `page` (a path), or any of `country`, `continent`, `source`,
`assistant`, `device`, `browser`, `os`, `campaign`, `landing`. Ranges may be up
to 400 days long and go back as far as history keeps (`report.retention_days`,
400). Answer in well under a second at 365 days.

```json
{"ok":true,"site":"example.com","view":null,
 "a":{"from":"2026-10-01","to":"2026-10-31","days":31,"used":29,
      "excluded":[{"day":"2026-10-06","state":"partial"},{"day":"2026-10-12","state":"missing"}],
      "unmeasured":[]},
 "b":{"from":"2026-09-01","to":"2026-09-30","days":30,"used":30,"excluded":[],"unmeasured":[]},
 "presets":{"previous":{"from":"2026-08-31","to":"2026-09-30"},"last_year":{"from":"2025-10-01","to":"2025-10-31"}},
 "filters":{"country":"CA"},"filtered":true,
 "metrics":[{"key":"visitors","label":"Visitors","a":412,"b":300,"delta":112,"delta_pct":37.3}],
 "series":{"a":[{"day":"2026-10-01","state":"ok","visitors":14,"pages_read":20,"visitors_from_ai":0,
   "ai_asked":2,"ai_training":180,"search":160,"leads":0}],"b":[]},
 "dimensions":{"pages":[{"name":"/pricing/","a":40,"b":25,"delta":15,"delta_pct":60.0,"new":false,"gone":false}],
               "sources":[],"assistants":[],"countries":[],"continents":[],"devices":[],
               "browsers":[],"os":[],"campaigns":[]},
 "dimension_counts":{"pages":"page views","sources":"visitors"},
 "reconciled":true,"problems":[]}
```

- Only whole, verified days (`ok`) count; every other day in a range is in
  `excluded` with its state (`partial`, `withheld`, `missing`, `before`).
  `used` is the number of days counted. `unmeasured`: used days collected
  before the drill-down data existed (their dimension rows are missing; the
  metrics still count).
- `metrics[].key`: `visitors` (readers), `pages_read`, `visitors_from_ai`
  (readers who came from an assistant), `ai_asked`, `ai_training` (assistant
  fetches), `search` (search-engine fetches), `leads` (sign-up, contact,
  early access, demo booked; from the CMS), `returning`, `pages_per_visitor`
  (float), `not_found_people` (404s people met). A metric the filters cannot
  apply to is `null` on both sides (the CMS and crawler figures are not
  filtered by country, say), never a whole-site number under a filter.
- `delta = a - b` and `delta_pct = (a - b) / b * 100` (null when b is 0):
  **A is the range being looked at, B what it is compared with.** `new`: in A, not in B; `gone`: in B, not in A.
- Dimensions count visitors (readers, once each, by the first page they
  read), except `pages`, which counts page views. Rows are every value seen,
  biggest first (no top-N cut; at most 1,000 rows, then `"(all others)"`).
  `continents` are derived from the country (Africa, Antarctica, Asia,
  Europe, North America, Oceania, South America, Unknown). There are no
  sub-national regions: the address database is country-level.
- With `page=/path`: visitors = readers of that page, pages_read = its views,
  ai_asked / ai_training / search = fetches of that page; `sources`,
  `assistants`, `countries` and `continents` are that page's readers'; the
  other dimensions and metrics are null.
- `series.a` / `series.b`: one entry per calendar day of each range, with its
  state and the figures `visitors`, `pages_read`, `visitors_from_ai`,
  `ai_asked`, `ai_training`, `search`, `leads` - null on a day not counted,
  and null for a figure the filters cannot split. The days add up to the
  metrics (checked: `reconciled`).
- `reconciled`: the dimension rows add up to the visitors metric over the
  measured days (and the page rows to the page views); `problems` says
  where not.

The data under it, both kept `report.retention_days` (400) days:
`day_extras` kind `visit_cube` (every reader's visit as
[country, landing, source, assistant, device, browser, os, campaign] → n, all
pages, no cap; verified against the readers breakdowns and recounted by the
audit), kind `pages` (every page: views, readers, AI and search fetches,
sources, assistants, countries; read for a `page=` filter) and kind
`page_counts` (the same pages, compact: `{path: [views, readers, ai_asked,
ai_training, search]}`; read for the page views of an unfiltered compare).

## Connections status (helper API)

`GET <page>/sites/status?site=<name>` (owner or admin; `skald/connections_api.py`):
what has reached Skald for one site, for the Test in Settings > Connections and in Add a
site. Not a data file and not a figure: counts of lines received, never visits.

```json
{"ok": true, "site": "example.com", "ingest_enabled": true,
 "send_url": "https://stats.example.com/traffic-ingest/example.com", "folder": true,
 "received": {"batches": 42, "accepted": 51200, "rejected": 3, "last_at": "...", "shippers": 1},
 "last_batch": {"at": "2026-10-21T10:42:05Z", "lines": 120, "rejected": 0, "shipper": "a1b2c3"},
 "last_contact": "2026-10-21T10:42:05Z",
 "today": {"day": "2026-10-21", "lines": 1240},
 "last_refusal": {"at": "2026-10-21T10:41:00Z", "code": 403, "reason": "wrong_site",
                  "words": "The token is not for this site."},
 "verify": {"state": "verified", "verified_at": "...", "method": "dns"},
 "beacon": {"day": "2026-10-21", "updated_at": "...", "events": 15, "last_open_at": "..."},
 "setup": {"name": "example.com", "org_id": 1, "step": 5, "method": "docker", "verified": true,
           "token_id": "ab12cd34", "started_at": "...", "updated_at": "...", "updated_by": "...",
           "done_at": "...", "done": true},
 "now": "2026-10-21T10:44:00Z"}
```

- `received`: the ingest folder's totals (`ingest_log.summary`), null with no folder.
- `last_batch`, `last_contact`, `today`, `last_refusal`: the site's
  `<history folder>/ingest-status/<site>.json` (`ingest_status.py`; docs/INGEST.md, "What
  the endpoint notes for the Test"), each null until it happened. `today.day` is the UTC
  day; a file from an earlier day reads `lines: 0`. `reason` is one of `ingest_status.REASONS`,
  `words` its plain sentence. No address, user agent, token or log line, ever.
- `verify`: null for a site with no check; pending: `{"state":"pending","token","txt","meta"}`.
- `beacon`: null when the script tag is off on the install; else the newest day's events
  kept and when its counters and the last page open were written.
- `setup`: the Add a site row (`accounts/site_setup.py`), or null. `token_id` is the
  sending token's id, never the token.
- 403 for a viewer, 404 for a site of another organisation.

## Page lifecycle

What happened to a page since it was published.

`page_index.json` (the site's data folder): one row per page the website
lists or the logs saw.

| field | type |
|---|---|
| `meta` | `{"source": "website" or null, "generated": date or null}`: where publish dates come from (`/etc/skald/pages.json`, written from the website at deploy) |
| `pages[]` | `{"path","title" or null,"locale" or null,"published" (date or null),"updated","date_source" ("website" or "first seen"),"first_seen" (date: the first day any request for it was logged),"days_since_publish" (int or null),"milestones": {"googlebot","bingbot","human","from_search","from_ai","lead"} (ISO or null),"views_7d","views_30d","readers_30d"}` |

`GET <page>/api/page?path=/x` (helper; also `skald page /x`):

```json
{"ok":true,"path":"/x/","title":"...","published":"2026-10-01","updated":"2026-10-06",
 "date_source":"website","first_seen":"2026-10-06","days_since_publish":7,
 "milestones":{"googlebot":{"at":"2026-10-06T19:02:11-04:00"},"bingbot":null,
   "ai_training":[{"who":"GPTBot","at":"..."}],"ai_asked":[{"who":"ChatGPT-User","at":"..."}],
   "human":{"at":"..."},"from_search":{"at":"...","who":"google.com"},
   "from_ai":[{"who":"chatgpt.com","at":"..."}],"lead_landed":{"at":"..."} ,"lead_sent":null},
 "days":[{"day":"2026-10-06","state":"partial","days_since_publish":5,"readers":3,"views":4,
   "ai_asked":0,"ai_training":2,"search":1,"sources":{},"assistants":{},"countries":{}}]}
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
- `days[]` run from the publish date (or first seen) to yesterday, at most
  400, each with its state; a day with no figures (`missing`, `withheld`)
  has them null, never 0. Today is not included.

## The read-only API

Every data file is also served as `GET /traffic/<site>/[<view>/]api/v1/<name>`
(behind the dashboard password) and as `GET /traffic-api/v1/<site>/[<view>/]<name>`
with `Authorization: Bearer <token>` (tokens from `skald token create`).
`GET .../api/v1/` lists the files. Answers are the files exactly as above;
docs/API.md has the details.

## Users and roles

Basic mode (the default): nginx checks the password; the helper reads who
it was (`X-Skald-User`, believed from 127.0.0.1 only). `admin` may change
internal addresses and funnels; `viewer` reads only.
`GET <page>/me` -> `{"ok":true,"user":"morgan","role":"admin"}`, plus
`update` (a newer release) for an owner or admin.
With accounts (`access: {mode: sessions}`, docs/ACCOUNTS.md) the roles are
`owner`, `admin` and `viewer`, read from the session, never from a header;
an owner counts as an admin, and `/me` adds `name`, `org`, `csrf`, `mode`,
`install_admin` and `totp_on`.

## alerts.json

Moved to [docs/DATA-CONTRACT-ALERTS.md](docs/DATA-CONTRACT-ALERTS.md#alertsjson).

## quality.json

Moved to [docs/DATA-CONTRACT-ALERTS.md](docs/DATA-CONTRACT-ALERTS.md#qualityjson).

## markers.json

Moved to [docs/DATA-CONTRACT-ALERTS.md](docs/DATA-CONTRACT-ALERTS.md#markersjson).

## leads.json

Leads from the website's CMS, as **aggregates only** - no name, email,
phone, company, session or address. Details: `/admin` on the website,
through the SSH tunnel (`admin_note`). A lead is never joined to a visit:
"first touch" is what the lead's own browser remembered, which is not the
source of any one visit in the logs.

| field | type |
|---|---|
| `available` | bool: the CMS database could be read (false: `error` says why, everything else empty) |
| `error` | string or null |
| `since` | date or null: the local day of the first lead in the database |
| `admin_note` | string |
| `types` | `["signup","contact","waitlist","demo_opened","demo_booked"]` |
| `days[]` | `{"day","leads": {type: n},"status": {status: n},"spam": n,"duplicates": n}` - `leads` excludes spam and duplicates, for the 180 days ending today (local) |
| `by_source_type` | from release 2b: `{"first_touch": {source type: {type: n}}, "last_touch": {...}, "ai_first": {assistant: {type: n}}, "ai_last": {assistant: {type: n}}}` over `period`'s days - leads (spam and duplicates excluded) by source and by AI assistant, split by lead type, so demos booked can be read by the source and assistant that brought them |
| `period` | the last 30 days and today: `{"first","last","leads": {type: n},"status": {...},"first_touch": {"source": {..},"ai": {..},"utm_campaign": {..},"landing": {..}},"last_touch": {same},"page": {path sent from: n},"locale": {..}}` - each breakdown counts leads (spam and duplicates excluded) and adds up to the leads; `"(none)"` holds those without it |
| `funnel` | `{"first","last","days","note","steps": ["readers","pricing","form_page","demo_opened","leads","demo_booked"],"by_source": [{"source","readers","pricing","form_page","demo_opened","leads","demo_booked"}],"total": {...}}` - `readers`, `pricing` (a visit that reached a pricing page), `form_page` (a visit that opened a sign-up, contact or early-access page) come from the logs' journeys (visits, by the visit's source; the last `journey_days` days); `demo_opened`, `leads` (sign-up, contact, early access) and `demo_booked` come from the CMS, by the lead's first-touch source type, over the same days. Two systems side by side, never divided per visit. |
| `attribution_columns`, `attribution_rows` | phase 4: [docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md#leadsjson-attribution_rows) |
| `time_to_convert` | phase 4: [docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md#leadsjson-time-to-convert) |
| `likely_ai` | `{"on","window_minutes","method"}`: [docs/DATA-CONTRACT-AI-LIKELY.md](docs/DATA-CONTRACT-AI-LIKELY.md) |
| `withheld` | `{block: why}`: the blocks the second count disagreed with (empty when all agree). A block is `period`, `by_source_type`, `funnel`, `attribution_rows`, `time_to_convert`, or `days/<day>` |

**Second count and withheld blocks (phase 4).** Each time leads.json is built,
`audit_leads.py` recounts every figure above by its own road: SQL GROUP BY over
`json_extract` per local day (UTC bounds), source types by the audit's own rules
(`audit_labels.source_of`), time buckets by SQL `julianday`, the funnel's log steps
from the same journeys with its own page matching. A block that disagrees is
replaced by `{"state": "withheld", "why": "..."}`; a day in `days` that disagrees
becomes `{"day", "state": "withheld", "why"}` with no figures (read it as not
recorded, never zero). A recount that cannot run withholds every block. run-daily
runs the same comparison (step "leads audit"); a mismatch ends the run "withheld".

## ours.json

Our own traffic, and the server's health as our own heartbeat sees it.

| field | type |
|---|---|
| `rules` | `[{"label","kind" ("user agent"/"referrer"/"address"),"source" ("config"/"file"),"paused" (file entries only: bool, paused now)}]` - labels only, never an address (the address list is the management API below); deleted and replaced entries are not listed |
| `heartbeat_label` | string, the label whose requests are the 5-minute heartbeat (default `"heartbeat"`) |
| `days[]` / `today` | `labels` `{label: requests}`; `heartbeat` (below); `hours` `{hour: {"requests","p50_ms","p95_ms","server_errors","heartbeat_ok","heartbeat_failed"}}` (`p50_ms`/`p95_ms`: all site requests' server time, null when not logged) |
| `api` | `{"list": "ours", "add": "ours/add", "remove": "ours/remove", "add_mine": "ours/add-mine", "pause": "ours/pause", "resume": "ours/resume", "edit": "ours/edit"}` relative to the page (an older file without the last three: the page uses these defaults) |

`heartbeat`: `{"expected": int (one per 5 min in the window), "seen": int,
"ok": int (status 2xx/3xx), "failed": int, "uptime_pct": float or null
(ok / expected * 100), "gaps": [{"from","to","minutes"}] (no heartbeat for
more than 10 minutes)}`.

### Internal addresses API (refresh helper, same password, same-origin only)

- `GET <page>/ours` -> `{"ok":true,"limit":50,"entries":[{"ip":"203.0.113.7","label":"Office","source":"config","editable":false,"pausable":false,"active":true,"paused_since":null,"added_at":null,"added_from":null}]}`.
  A page-added entry has `"source":"file"`, `"editable":true`, `"pausable":true`, `active`
  (false while paused), `paused_since` (ISO, when the open pause began, else null) and `paused`
  (below). Deleted and replaced entries are not listed.
  Internal addresses are shown here (private page) and never in the JSON
  files, CSV exports or emails. (Visitors' addresses, when a site keeps
  them, are shown only by the person lookup:
  [docs/DATA-CONTRACT-PEOPLE.md](docs/DATA-CONTRACT-PEOPLE.md).)
- `POST <page>/ours/add` (form or JSON `ip`, `label`), `POST <page>/ours/remove`
  (`ip`), `POST <page>/ours/add-mine` (`label`; the caller's address from
  nginx's `X-Real-IP`). Answer: `{"ok":bool,"error":string?,"entries":[...]}`;
  400 on invalid input, 403 when not same-origin, 409 at the limit.
  `POST <page>/ours/pause` and `POST <page>/ours/resume` (`ip`): 400 when it is
  already paused / not paused, or a config entry. `POST <page>/ours/edit` (`ip`,
  and `label` and/or `new_ip`). Same permission as add.
  An address added applies from `added_at` on (live and future days); stored
  days are never rewritten. Each change is logged to
  `/var/log/skald/ours-changes.log` (actions `add`, `remove`, `pause`,
  `resume`, `edit`).

  The server's own file (`ours.file`, else `ours.json` beside the history; not
  a data file) keeps, per entry: `ip`, `label`, `added_at`, `added_from`,
  `added_by`, `site`, and since 2026-10-18 `paused`: `[[from, to-or-null], ...]`
  (ISO with offset; null: still paused), `removed_at` (deleted, or replaced by an
  edit), `replaced_by`, `removed_by`. An entry counts a request at time t when
  `added_at <= t`, t is before `removed_at`, and t is in no pause (`from <= t < to`).
  Entries are never taken out of the file, so a stored day re-collected later,
  and the audit's own recount, give the same figures. A file without these
  fields reads as before (active, never removed).

### Outside uptime check (`outside`: null until set up; written by the outside check, not by Skald)

`ours.json` has a top-level `outside`. Today it is `null`: no outside check
is set up yet - show "not set up on this server
yet" beside the heartbeat. Once one runs, it becomes this block:

```json
"outside": {"enabled": true, "source": "remote", "checked_every_min": 1,
  "last": {"at": "2026-10-08T12:19:00Z", "ok": true, "ms": 180, "status": 200},
  "days": [{"day": "2026-10-08", "checks": 1440, "ok": 1439, "failed": 1,
            "uptime_pct": 99.93, "p50_ms": 175}],
  "outages": [{"from": "2026-10-08T03:12:00Z", "to": "2026-10-08T03:14:00Z", "minutes": 2}]}
```

`outside` null or `enabled` false: not set up. `last` null: no check yet.

## not_found.json

Every 404 and 410, by path.

| field | type |
|---|---|
| `days[]` / `today` | `rows`: `[{"path","status" (404/410),"group" ("people"/"ai_asked"/"ai_training"/"search_engines"/"bots"/"ours"),"probe": bool,"source" (referrer label: assistant or search engine name, a host, or "(none)"),"source_kind" (a source type),"utm_source","n","first","last" (HH:MM local)}]`; `totals` `{"all","people","probes"}` |
| `paths` | over the last 30 days plus today, one row per path: `{"path","n","people","probe": bool,"statuses":{...},"groups":{...},"sources":{...},"first_day","last_day","trend": {day: n},"fix"}` |

`fix`: `"redirected"` (the site's old-URL map sends it elsewhere, `fix_to`
has where), `"gone"` (map answers 410), `"fixed"` (the path now answers
2xx/3xx in the log, `fix_status`), or `"open"`. Probe rows (scanners: `.env`,
`wp-login`, `.php` ...) keep `probe: true` so the app can group them apart.
The people rows' `n` with status 404 add up to `health.json`'s 404s seen by
people (`statuses.people.404`).

## ai_activity.json

Moved to [docs/DATA-CONTRACT-BOTS.md](docs/DATA-CONTRACT-BOTS.md#ai_activityjson).

## campaigns.json

`days[]` and `today`: `rows` `{dimension: [{"name","visits","pages","not_found","posts"}]}`
with dimensions `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`,
`utm_content`, `ref_host` (referring host), `ref_page` (other websites: host
+ path), `paid` (ad network from a click id: `Google Ads`, `Microsoft Ads`,
`Meta`, `LinkedIn`, `TikTok`, `X`), `ref_param`, `ai` (assistant). `"(none)"`
is the visits without it, so each dimension adds up to the day's visits.
`tagged` int: visits with a UTM tag, a click id or an AI source.
`last_30_days`: the same `rows`/`tagged`/`visits` summed over the whole
days of the last 30.
`first_touch` `{source type: returning visitors}` - the source of each
returning visitor's first visit within 30 days. `posts` are form POSTs
(conversions). Only these query parameters are ever kept; every other one
is dropped before anything is stored.
`days[].utm_hygiene` and `today.utm_hygiene`: campaign tag problems;
`days[].direct_likely` and `today.direct_likely`: Direct, likely a checkout
return, an in-app browser or a shared link (an estimate), `null` on a day it
was not recorded; the top-level `direct_likely` `{"on","share_window_minutes",
"method","reasons"}` says how it is made. Both:
[docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md).
`days[].social_networks` and `today.social_networks`: the Social media visits by
network (X, LinkedIn, ...), `null` on a day it was not recorded; the top-level
`social_networks` `{"names","order","method"}`:
[docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md#day-kind-social_networks-campaignsjson).

## pages.json

| field | type |
|---|---|
| `pages` | `[{"path","views","readers","visits","entries","exits","after_pages" (mean pages after landing, float or null),"time_on_page_s" (median estimate, null when unknown),"time_estimate": true,"exit_rate" (exits / visits, 0 to 1, null under 10 visits),"not_found_from","posts_from","ai_asked","ai_training","search","sources": {type: visits},"assistants": {name: visits},"countries": {code: readers},"prev": {same figures for the previous 30 days} or null,"change_pct": float or null,"daily": {day: views}}]` over the last 30 whole days, by views |
| `period` | `{"first","last","days": int,"complete": bool}` and `prev_period` |
| `today` | `{"pages": [{"path","views","readers","entries","ai_asked","ai_training","search"}]}` |

`time_on_page_s` is the median time from a page view to the visitor's next
request, so a visitor's last page has none: an estimate, labelled as such.
`daily` covers 90 days. `change_pct` only when both periods are complete.
`exit_rate` is the share of the page's visits (in-app pages included) that
ended on it, from the period's summed `exits` and `visits`; `null` under 10
visits (no rate over fewer than 10). The audit recounts each day's `visits` and
`exits` of every page from the raw lines (`audit_visits.compare_pages`).

## insights.json

`insights[]`, most important first, and `today[]` (the same rules over
today so far against the same weekday's baseline, `confidence` lower):

| field | type |
|---|---|
| `type` | `working`, `dropped`, `new`, `gone`, `anomaly`, `opportunity` |
| `title` | plain English, e.g. "/pricing/ readers up 80% week on week" |
| `metric` | e.g. `"readers"`, `"visits"`, `"ai_asked"`, `"not_found"` |
| `subject` | `{"kind": "page"/"source"/"country"/"assistant"/"campaign"/"referrer"/"crawler"/"path"/"site", "name": str}` |
| `before`, `after` | number or null |
| `change_pct` | float or null |
| `confidence` | `"high"`, `"medium"`, `"low"` |
| `filter` | `{field: value}` the app can apply, e.g. `{"path": "/pricing/"}` |
| `since` | date: start of the "after" period |
| `period` | `{"after": [first, last], "before": [first, last]}` |

Comparisons only between complete periods (no withheld, missing or partial
days). Thresholds (`insights:` in the config, defaults: at least 5 events
after, and 20% change) keep tiny numbers out.

Since 2.5.0 the whole site's file also holds lead findings (`metric`
`"leads"`, subject kinds `site`, `source`, `page`, `country`; a "sends the
most leads" finding has `"top": true` and `"of"`, all the leads of its 30
days), from conversions.json's checked days, and `leads_withheld`: `[why]`,
the lead findings the second count (`audit_conversions_leads.py`) disagreed
with, left out. Rules and second count:
[docs/DATA-CONTRACT-CONVERSIONS.md](docs/DATA-CONTRACT-CONVERSIONS.md).

## events.json

In-page events from the beacon (`events.py`, docs/BEACON.md): what readers
did inside pages, counted on the site's own server. People only; our own
addresses' events are kept apart in `ours`. Everything is an aggregate:
there is no visit or visitor key, so an event step in a funnel is shown
beside the visit steps (like the lead steps), never divided per visit.

| field | type |
|---|---|
| `events` | `[{"name","label"}]`: the event names this site counts, in report order (`cta_click`, `book_demo_open`, `demo_booked`, `signup_start`, `signup_submit`, `contact_submit`, `waitlist_submit`, `outbound_click`, `scroll_75`, `copy_text`, `404_view`; skald.js's own `form_start`, `form_submit`, `calendly_open`, `calendly_time_selected`, `calendly_booked`, `cal_open`, `cal_booked`, `hubspot_meeting_booked`, `tel_click`, `mailto_click`; and `page_view` when `beacon.page_views` or `beacon.visitor_ids` is on) |
| `keep_days` | int: how many days history keeps (`beacon.keep_days`, default 400) |
| `first_day` | date or null: the first day with events |
| `limits` | `{"factor","slack","day_factor","day_slack"}`: verify's bounds (events per page view) |
| `days[]` | `keep_days` entries ending yesterday, oldest first: `{"day","state"}`; `state` is `ok`, `withheld` (+ `problems`), `missing` or `before`. When `ok`: `events` `{event: n}`, `ours` `{event: n}` and `ai` `{assistant: {event: n}}` (both null on a view), `anomalies` `[{"kind": "path"/"404"/"unchecked"/"spool", "path","events","views","limit"} or {"kind","note"}]`, `audit` `"ok"`/`"mismatch"`/null, `by_source` (see "events.json goals" below) |
| `row_fields` | `["day","event","label","path","source","n"]` |
| `sent` | `{event: day}`: every event name the beacon ever recorded for the site (any kept day, withheld days included, and today's spool), with the last day it did. Names only, no count. An event in `events` but not here was never sent: the page says "not set up", never 0 |
| `rows_from` | date: the first day `rows` cover |
| `rows` | `[[day, event, label, path, source, n]]` for `ok` days from `rows_from` (180 days); `label` is which button or form (`"signup_hero"`, `"demo_header"`; the destination host for `outbound_click`; `""` when none); `source` is one of the source types (Visits) of the visit the event came from |
| `today` | `{"state": "ok"/"empty"/"withheld","from","until" (local ISO, first and last event),"events": {event: n},"ours","ai","rows": [[event, label, path, source, n]]}` from today's spool; not yet verified or audited |
| `helper` | `{"today","yesterday"}`: the helper's counters, `{"day","accepted","accepted_ours","declined" (Do Not Track / GPC),"not_people","refused_origin","refused_body","refused_event","refused_path","refused_field","refused_rate","updated_at"}` (keys absent when zero) or null |

On a view, `rows`, `days[].events` and `today` keep only the view's paths.
A day's `events` sum the day's `rows`. A `withheld` day shows no figures.

```json
{"events":[{"name":"cta_click","label":"Button clicks"}],"keep_days":400,"first_day":"2026-10-08",
 "days":[{"day":"2026-10-08","state":"ok","events":{"cta_click":12,"scroll_75":30},"ours":{"cta_click":2},
   "ai":{"chatgpt.com":{"cta_click":1}},"anomalies":[],"audit":"ok"}],
 "rows":[["2026-10-08","cta_click","signup_hero","/","Search engine",4]],
 "today":{"state":"ok","from":"2026-10-09T00:12:03-04:00","until":"2026-10-09T09:40:11-04:00",
   "events":{"book_demo_open":1},"ours":{},"ai":{},"rows":[["book_demo_open","header","/pricing/","Direct or unknown",1]]},
 "helper":{"today":{"accepted":1,"declined":1},"yesterday":null}}
```

---

## conversions.json

Conversions (Phase 4b; `conversions_data.py`): per local day for 180 days
ending today, every action's rows by stage, abandoned starts, and for
finished ones the breakdowns (source, first source, campaign, landing,
country, device, tool), visits before, time to convert and assisted
sources; over the last 30 days the pages seen before converting and the
latest conversions as timelines without name, email or visitor ID. The same
file on every view. A row marked test is never counted in it.
Every figure is counted twice (`audit_conversions.py`,
`audit_conversions_figures.py`); a day or block that disagrees is withheld.
Every field: [docs/DATA-CONTRACT-CONVERSIONS.md](docs/DATA-CONTRACT-CONVERSIONS.md); the
per-day `likely_ai` (an estimate): [docs/DATA-CONTRACT-AI-LIKELY.md](docs/DATA-CONTRACT-AI-LIKELY.md).
Since 2.18 a lead may carry a `label` (the lead hook's optional token): each day's `labels`
and `labels_abandoned` count the labelled rows, recounted by the same SQL audit; the
timeline's rows and steps name it. `conversions.sqlite` is schema 7 (`conversions.label`).
Since 2.27 `today.same_time` holds the last day of the period before Leads' 7, 30 and 90
days, counted to the file's time of day, so Leads compares today so far and the whole days
before it like for like; recounted by `audit_conversions_leads.check_same_time`.

Since 2.32 (revenue on leads) a day carries `revenue` per currency (gross, refunded and net
minor units; sales, refunds, new customers, renewals; by source, first source, campaign, landing,
country, device, tool, label and tag) and the file `currencies`, `ltv` (lifetime value by
first source over every row kept), `refunds_without_sale` (refunds kept that no figure counts:
stored, never subtracted) and `revenue_since` (the first local day with a value: a day before it
has no `revenue`, never zero); never converted between currencies, absent when the site has
no value at all. A refund counts only on its counted sale, in its currency, never more than it;
each part of a refund counts on the day it arrived. `conversions.sqlite` is schema 9: the stage
`refunded` (the table rebuilt, every row kept), `value_minor`, `currency`, `customer_ref`, `tags`,
`pay_ref`, and the tables `refund_parts` (each rise of a refund with its time) and `pay_links`
(Stripe's `invoice_payment.paid`: which payment paid which invoice). Recounted by
`audit_revenue.py` (SQL and the hook spool); a day it disagrees with is withheld, `ltv`,
`refunds_without_sale` and `revenue_since` too.
Every field: [docs/DATA-CONTRACT-CONVERSIONS.md](docs/DATA-CONTRACT-CONVERSIONS.md), "Revenue".

A lead sent with the plain key (2.30, `Authorization: Bearer`, INTEGRATIONS.md) is the same
row as a signed one: it changes how a sender proves itself, never a figure.

The site's server reads back what its `lead` hook delivered with the signed
`GET /traffic-hooks/<site>/leads` (2.18; `conversions/reconcile.py`, INTEGRATIONS.md): rows
`{external_ref, action, stage, at, label, test, received_at}` ordered by `received_at`, then id,
paged by an opaque `next_cursor`; never a name, email, address, user agent, visitor ID or source.
Since 2.32 each row also has `value` (exact text, major units), `value_minor`, `currency`,
`customer_ref` and `tags`.
A listing for reconciling, not a figure.

## People (2.4.0)

Each visit kept with its address (`visits`, `visit_days` in
`conversions.sqlite`), rows a sync removed (`removed`), the `test` mark, and
the helper's person lookup and left-out lists: not data files, not figures.
Every field: [docs/DATA-CONTRACT-PEOPLE.md](docs/DATA-CONTRACT-PEOPLE.md).

`retention.json` (Traffic › Retention) and the day kinds `retention_week` and
`retention_day`: cohorts of new visitors and who came back, counted from the kept
visits or the 30-day code, recounted by `audit_retention.py`. Every field:
[docs/DATA-CONTRACT-PEOPLE.md](docs/DATA-CONTRACT-PEOPLE.md), "Retention cohorts".

## Client reports (2.13)

Moved to [docs/DATA-CONTRACT-REPORTS.md](docs/DATA-CONTRACT-REPORTS.md#client-reports-213).

---

## Tracking additions

The day kinds `funnels`, `engagement`, `utm_hygiene`, `ai_likely`, `ai_fetches`, `ai_read`,
`direct_likely`, `social_networks` and `ai_formats` (also app.json `days[].ai_formats`), leads.json
`attribution_rows` and time to convert, and events.json goals: [docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md).

## search.json (P1-6)

Search Console and Bing Webmaster Tools figures synced into history (table
`search_days`, history schema 14), the day kind `search_landing` (people from
search engines by engine and landing page) and the cross-check between them.
Every field: [docs/DATA-CONTRACT-SEARCH.md](docs/DATA-CONTRACT-SEARCH.md).

## security.json and the day kind `security` (2.21)

Scanners, what the server answered them ("Is anything exposed?"), attack
attempts and fake browsers: a view across the groups, never a group. The day
kind `security` (no address, no user agent), the addresses behind its rows in
conversions.sqlite (schema 8, `security_rows` and `security_days`, only while
the site keeps addresses), the helper's `people/security` (owners and admins)
and `security.json`. Every field: [docs/DATA-CONTRACT-SECURITY.md](docs/DATA-CONTRACT-SECURITY.md).

## ai_answers.json (AI answers)

What AI assistants say about the site, asked through their APIs per tracking
profile (`ai_answers.sqlite` beside the history), only figures the second count
(`audit_ai_answers.py`) verified, and the cited → read → sent → converted chain.
Every field: [docs/DATA-CONTRACT-AI-ANSWERS.md](docs/DATA-CONTRACT-AI-ANSWERS.md).
