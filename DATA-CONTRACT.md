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
- **Groups**: `people`, `answer_engines`, `search_engines`, `bots`, `ours`.
- **Privacy.** No file carries an IP address, a user agent or a visitor key,
  except `ai_activity.json`'s `today.events[].ip` and `requests.json`'s
  `rows[].ip` (the owner's decisions, 2026-10-07: shown on the private page
  only, read from the raw log, never stored in history; `requests.json` holds
  only its window). An address removed with `skald forget --ip` is shown as
  `"(removed)"` from then on. Journeys are anonymous and kept
  `journey_days` days.
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
| `credit` | `{"text","url"}` or null | country data attribution, show beside countries |
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
`summary` (one readable line), and from schema 9: `utm`
(`{"source","medium","campaign","term","content"}`, only those present),
`paid` (network name or `""`), `ref_param` (`ref`/`source`/`via` query value
or `""`), `ref_host`, `ref_page` (host + path, other websites only),
`search_terms` (or `""`), `returning` (bool or null), `days_seen_30d` (int or
null), `likely_ai` (only on a visit likely sent by an AI assistant, an estimate:
[docs/DATA-CONTRACT-AI-LIKELY.md](docs/DATA-CONTRACT-AI-LIKELY.md)). Source types: `AI assistant`, `Search engine`, `Social media`,
`Email`, `Other website`, `This site`, `Tagged link`, `Direct or unknown`.

```json
{"journey_days":7,"days":[{"day":"2026-10-07","state":"ok","stats":{"visits":140,"pages":{"1":118,"2":15}}}],
 "journeys":[{"day":"2026-10-07","start":"2026-10-07T12:41","country":"CA","device":"Mobile",
   "browser":"Safari","os":"iOS","source":"AI assistant","via":"ChatGPT","campaign":"",
   "landing":"/compare/x/","exit":"/pricing/","pages":2,"seen":3,"in_app":1,
   "trail":[["/compare/x/","page"],["/features/","app"],["/pricing/","page"]],"seconds":100,
   "not_found":0,"posted":0,"utm":{"source":"chatgpt.com"},"paid":"","ref_param":"",
   "ref_host":"chatgpt.com","ref_page":"","search_terms":"","returning":false,"days_seen_30d":1,
   "summary":"12:41 · 🇨🇦 Canada · Mobile, Safari on iOS · from ChatGPT → /compare/x/ → /features/ (in-app) → /pricing/ · 2 pages · 1m 40s"}],
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

`days[]` and `today`: `requests` int, `probes` int (scanner probes),
`agents` `{short name: requests}` (monitors, SEO suites, unfurlers,
crawler sessions in browser clothes), `statuses` (bots' status classes).

From release 2 (null on days collected before it; `today` has them too):

| field | type | meaning |
|---|---|---|
| `link_previews` | `{app: requests}` | link-preview unfurlers by app (`Slack`, `iMessage`, `WhatsApp`, `LinkedIn`, `Microsoft Teams`, `Discord`, `Telegram`, `X (Twitter)`, `Facebook`, `Skype`, `Pinterest`, `Reddit`, `Embedly`, `Iframely`, ...). A preview means someone pasted a link in a chat. Filed under bots; included in `requests` and in `agents` as `"link preview: <app>"`. |
| `verification` | `{crawler: {"group","method","verified","unverified","spoofed"}}` | every named assistant or search crawler that came, checked against its owner's published ranges or by reverse+forward DNS. `group` is `answer_engines` or `search_engines` (where it counts when not spoofed); `method` is `ranges`, `dns`, `network` (the owner's network list) or `none` (nothing published: always `unverified`). `spoofed` requests are filed under **bots** as `"claims to be <crawler>"` (and counted in `requests`); `verified + unverified` add up to the crawler's requests in its group. |
| `fake_browsers` | `{"hosting_network","fan_out","bare_mozilla": {"requests","addresses"}}` | browser-looking requests counted in **people** that carry a warning sign: from a cloud or hosting network, the same agent from 10+ addresses within 10 seconds, or the bare agent `Mozilla/5.0`. Flags only - they stay in people until a rule is proven; one request can carry several flags. |
| `not_rendered` | `{"requests","pages","readers"}` | browser-like requests moved to **bots** because their visit never rendered a page (no own script, style or `?_rsc=` payload near a page, no beacon event, not seen rendering earlier that day or reading on an earlier day; `rendering.py`, CLASSIFICATION.md rule 9). `pages` are their page views; `readers` the visits among them that read a page - the visitors this rule took out. In `requests` and in `agents` as `"browser-like, never rendered the page"`. Absent on days collected before 2026-10-11. Recounted by the audit. |
| `blocked` | `{crawler: n}` | 403 answers to each AI crawler of the AI crawler settings' catalog (`bot_policy.CATALOG`, by the token in its user agent), whichever group it counts in: what the settings refused, plus any other 403 that crawler got. Null on days collected before 2026-10-08; `{}` when none. Recounted by the audit. |

The AI crawler settings themselves are not a data file: the page reads and
saves them through the refresh helper, `GET <page>/bot-policy` and
`POST <page>/bot-policy` with `{"owners": {assistant: "allow"|"block"|"block_training"},
"crawlers": {name: "allow"|"block"}}` (admins only, same-origin). Both answer
`{"ok", "policy", "modes", "assistants": [{"owner","mode","crawlers": [{"name","tier"
("training"|"index"|"asked"),"robots_only","override","effective"}]}], "blocked": [name],
"robots_suggestion": text, "applied": {"at","ok","changed","error","blocked",
"policy_updated_at","conf_sha256"} or null}`, plus `"error"` on a refused save.
bots.json says whether that route exists: top level `api` is
`{"bot_policy": "bot-policy"}` (relative to the page) when the config has
`bot_policy.enabled: true`, else null - then the page fetches nothing and
shows the settings as not set up.
`applied` is the last time root's path unit wrote the nginx map; when its
`policy_updated_at` is older than the policy's `updated_at`, the change is
still being applied (seconds).

Top level (not per day): `ranges` `{list: {"fetched": ISO or null, "networks": int, "ok": bool, "error": string or null}}` - when each published list was last fetched; `dns_cache` `{"addresses": int, "checked_at": ISO or null}`.

## requests.json

Every request of the last `window_hours` hours, newest first - the "Recent
requests" tab. Written by every live run (2 minutes). **Private**: it holds
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
| `country`, `country_name` | string | ISO code or `""` |
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
| `rule` | string | why it is in that group, in words: `"people: reader"`, `"people: asset"`, `"people: Next.js payload (_rsc)"`, `"people: reader from chatgpt.com"`, `"ours: Office Mac (Morgan)"`, `"AI asked: ChatGPT-User"`, `"AI training: GPTBot"`, `"search: Googlebot"`, `"bot: meta-webindexer"`, `"bot: scanner probe"`, `"bot: link preview: Slack"`, `"bot: claims to be Googlebot"`, `"bot: browser-like crawler"`, `"bot: browser-like, never rendered the page"`, `"excluded: other host"` |
| `kind` | string | what was asked for: `page`, `rsc`, `asset`, `beacon`, `crawler_file`, `redirect`, `not_modified`, `not_found`, `client_error`, `server_error`, `post`, `other` |
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

The site's own robots.txt beside what each crawler actually fetched
(`robots.py`). robots.txt is fetched by the live run at most once an hour
and kept beside the history; verdicts use Python's `urllib.robotparser`
with the crawler's own token.

| field | type |
|---|---|
| `robots` | `{"url","fetched_at" (ISO or null),"ok": bool,"error": string or null,"groups": [{"agents": [token],"allow": [path],"disallow": [path],"crawl_delay": number or null}],"sitemaps": [url]}` |
| `crawlers[]` | one per assistant, search crawler or named bot seen in the last 30 days and today: `{"name","group","token" (the token matched against robots.txt),"applies" (the robots.txt group that applies: a token or "*"),"root_allowed": bool,"days_seen": int,"requests": int,"paths": int (distinct paths),"disallowed": int (requests for paths robots.txt disallows it),"disallowed_paths": [{"path","n"}] (top 10),"today": {"requests","disallowed"} or null}` - newest activity first |
| `days[]` | `{"day","state","crawlers": {name: {"requests","disallowed"}} or null}` (30 days) |

Requests are counted per day per crawler by path (`day_extras` kind
`crawler_paths`, the top 200 paths per crawler and an `"(all others)"`
row, verified and audited); `disallowed` is judged against the robots.txt
fetched at `robots.fetched_at` - rules change, so a past day is judged by
today's rules, and the file says so.
`llms_txt.json`, a suggested /llms.txt: [docs/DATA-CONTRACT-LLMS-TXT.md](docs/DATA-CONTRACT-LLMS-TXT.md).

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
 "first_day":"2026-10-06","last_day":"2026-10-07","live":true}],"current":"example.com"}
```

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
audit) and kind `pages` (every page: views, readers, AI and search fetches,
sources, assistants, countries).

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

nginx checks the password; the helper reads who it was (`X-Skald-User`).
`admin` may change internal addresses and funnels; `viewer` reads only.
`GET <page>/me` -> `{"ok":true,"user":"morgan","role":"admin"}`.

## alerts.json

What the alert check (every live run) found, open and recently closed. The
same file on every page.

| field | type | meaning |
|---|---|---|
| `enabled` | bool | `alerts.enabled` in the config |
| `mail` | bool | alerts are mailed (false: evaluated and shown only - staging, or `alerts.mail: false`) |
| `checked_at` | ISO or null | the last check |
| `rules[]` | `{"cause","on","threshold"}` | every alert type, whether it is switched on, and its threshold in words |
| `open[]` | alert | newest first |
| `closed[]` | alert | closed in the last 30 days, newest first |
| `ai` | object or null | the AI rules' last evaluation (alerts_ai.py): `{"day" (the last whole day judged),"evaluated_at","rules": {"started_reading"/"stopped_reading"/"sending_people": {"on","state" ("ok"/"waiting"/"off"),"waiting_on": [day] (withheld, partial, missing or not-recorded days the rule needs),"unjudged": [assistant] (an "(all others)" path row on a day that had to be empty),"found": int}}}`; `sending_people` also has `assistants[]`: `{"assistant","day" (likely visits),"average" (a day, the 28 days before),"verdict" ("jumped"/"vanished"/"steady"/"too few to judge")}`. null before the first check |

An alert: `id` (string), `cause` (`site_down`, `logging_stopped`,
`server_errors`, `not_found_surge`, `crawler_burst`, `new_crawler`,
`traffic_drop`, `ai_started_reading`, `ai_stopped_reading`, `ai_sending_people`), `subject` (what it is about: a crawler name, a path, or
`""`), `severity` (`high`, `medium`, `low`), `title` (one plain line),
`detail` (a few lines: the figure, the threshold, what to look at), `figure`
(number or null), `threshold` (number or null), `opened_at`, `last_seen_at`,
`closed_at` (ISO or null), `mailed` (mails sent for it), `repeats` (checks
that found it again while it was open and were not mailed - they go in the
daily digest). An AI alert also has `data`: `{"kind","assistant","crawlers","day","window",
"pages" | "visits","average"}` (the webhook body, docs/INTEGRATIONS.md); its `subject` is
`"<assistant>: <path>"`, `"<assistant>: pages"` (more than `ai_max_pages` pages in one alert) or
`"<assistant>: jumped"`/`"vanished"`, and `rules[]` rows for them carry `"group": "ai"`.

The AI rules count nothing new: they read the day kinds `crawler_paths` (checked by
robots.check, recounted by audit_release2) and `ai_likely` (checked by ai_likely.check,
recounted by audit_ai_likely.py), and the `pages` kind (a page answered to an assistant), on
whole `ok` days only. A withheld, partial, missing or not-recorded day in a rule's window makes
it wait. Settings `alerts.ai_*` (config.example.yml).

## quality.json

Is the input trustworthy - the data-quality panel.

| field | type |
|---|---|
| `days[]` | `{"day","state", ...}` - when the day has figures: `lines`, `unparsed`, `duplicates` (byte-identical to an earlier line in the same second; kept and counted), `duplicates_removed` (lines repeating an earlier line's request id `rid=`: the same request written twice, dropped before counting; null for days collected before the log carried `rid=`), `old_format` (lines in the combined format: no host, no country), `first_line`, `last_line` (HH:MM local), `gaps` `[{"from","to","minutes"}]` (no line at all for more than 10 minutes), `files` (log files read), `not_rendered` (bots.json's `{"requests","pages","readers"}`: browser-like requests moved to bots, null before 2026-10-11), `verify` (`"ok"`, `"withheld"`, `"partial"`), `problems` (string), `audit` `{"state": "ok"/"mismatch"/"not run", "at": ISO or null, "compared": int or null, "problems": [string]}`. Fields null when the day was collected before release 2. |
| `today` | null, or `{"state","lines","unparsed","duplicates","duplicates_removed","old_format","gaps","first_line","last_line","newest_line" (ISO),"clock_skew_s" (server clock minus the newest line, seconds; large = logging stopped or the clock is wrong),"files","not_rendered"}` |
| `runs` | `{name: {"last_ok": ISO or null, "last_fail": ISO or null, "last_exit": int or null, "expected_every_min": int}}` for `live`, `run-daily`, `verify-bots`, `alerts`, `backup`, and `heartbeat` (its last answered beat in the log) |
| `rotation` | `{"files": [{"name","bytes","modified"}]}` - the log files on disk now, newest first |
| `builders_failing` | `[{"file","error","since"}]`: optional data files whose builder failed on this redraw (see below); `[]` when all were built |

**A data file that failed to build.** The core files - overview, live,
visits, hourly, breakdowns, health, ours, quality - are always built or the
run stops. Any other file whose builder raises is written as the envelope
plus `{"state": "error", "error": "<short message>"}` and nothing else, and
listed in `quality.json` `builders_failing` with the time it started
failing; every other file is still written. Show such a file as "could
not be built", never as empty or zero.

## markers.json

Things we did, to draw as vertical lines on every chart.

| field | type |
|---|---|
| `markers[]` | `{"at": ISO, "kind", "label", "detail"}`, newest first, the last 180 days. `kind`: `website_release` (a release directory on the server), `skald_deploy`, `config_change` (the skald config changed), `ours_change` (an internal address added or removed), `backfill` (history recounted) |
| `website_version` | string or null: the version the live site's footer shows now, e.g. `"v1.4.0 · build 212"` |

## leads.json

Leads from the website's CMS, as **aggregates only** - no name, email,
phone, company, session or address. Details: `/admin` on the website,
through the SSH tunnel (`admin_note`). A lead is never joined to a visit:
"first touch" is what the lead's own browser remembered, which is not the
source of any one visit in the logs.

| field | type |
|---|---|
| `available` | bool: the CMS database could be read (false: `error` says why, everything else empty) |
| `admin_note` | string |
| `types` | `["signup","contact","waitlist","demo_opened","demo_booked"]` |
| `days[]` | `{"day","leads": {type: n},"status": {status: n},"spam": n,"duplicates": n}` - `leads` excludes spam and duplicates, for the 180 days ending today (local) |
| `by_source_type` | from release 2b: `{"first_touch": {source type: {type: n}}, "last_touch": {...}, "ai_first": {assistant: {type: n}}, "ai_last": {assistant: {type: n}}}` over `period`'s days - leads (spam and duplicates excluded) by source and by AI assistant, split by lead type, so demos booked can be read by the source and assistant that brought them |
| `period` | the last 30 days and today: `{"first","last","leads": {type: n},"status": {...},"first_touch": {"source": {..},"ai": {..},"utm_campaign": {..},"landing": {..}},"last_touch": {same},"page": {path sent from: n},"locale": {..}}` - each breakdown counts leads (spam and duplicates excluded) and adds up to the leads; `"(none)"` holds those without it |
| `funnel` | `{"first","last","days","note","steps": ["readers","pricing","form_page","demo_opened","leads","demo_booked"],"by_source": [{"source","readers","pricing","form_page","demo_opened","leads","demo_booked"}],"total": {...}}` - `readers`, `pricing` (a visit that reached a pricing page), `form_page` (a visit that opened a sign-up, contact or early-access page) come from the logs' journeys (visits, by the visit's source; the last `journey_days` days); `demo_opened`, `leads` (sign-up, contact, early access) and `demo_booked` come from the CMS, by the lead's first-touch source type, over the same days. Two systems side by side, never divided per visit. |
| `attribution_columns`, `attribution_rows` | phase 4, see [below](#leadsjson-attribution_rows) |
| `time_to_convert` | phase 4, see [below](#leadsjson-time-to-convert) |
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
| `rules` | `[{"label","kind" ("user agent"/"referrer"/"address"),"source" ("config"/"file")}]` - labels only, never an address (the address list is the management API below) |
| `heartbeat_label` | string, the label whose requests are the 5-minute heartbeat (default `"heartbeat"`) |
| `days[]` / `today` | `labels` `{label: requests}`; `heartbeat` (below); `hours` `{hour: {"requests","p50_ms","p95_ms","server_errors","heartbeat_ok","heartbeat_failed"}}` (`p50_ms`/`p95_ms`: all site requests' server time, null when not logged) |
| `api` | `{"list": "ours", "add": "ours/add", "remove": "ours/remove", "add_mine": "ours/add-mine"}` relative to the page |

`heartbeat`: `{"expected": int (one per 5 min in the window), "seen": int,
"ok": int (status 2xx/3xx), "failed": int, "uptime_pct": float or null
(ok / expected * 100), "gaps": [{"from","to","minutes"}] (no heartbeat for
more than 10 minutes)}`.

### Internal addresses API (refresh helper, same password, same-origin only)

- `GET <page>/ours` -> `{"ok":true,"limit":50,"entries":[{"ip":"203.0.113.7","label":"Office","source":"config","editable":false,"added_at":null,"added_from":null}]}`.
  IPs are shown here (private page) and nowhere else: never in the JSON files,
  CSV exports or emails.
- `POST <page>/ours/add` (form or JSON `ip`, `label`), `POST <page>/ours/remove`
  (`ip`), `POST <page>/ours/add-mine` (`label`; the caller's address from
  nginx's `X-Real-IP`). Answer: `{"ok":bool,"error":string?,"entries":[...]}`;
  400 on invalid input, 403 when not same-origin, 409 at the limit.
  An address added applies from `added_at` on (live and future days); stored
  days are never rewritten. Each change is logged to
  `/var/log/skald/ours-changes.log`.

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

| field | type |
|---|---|
| `today` | null, or `{"events": [...], "total": int, "by_name": {name: {"kind","events","visitors","repeat"}}}` (`visitors`/`repeat` null without the visitor key; a view's `by_name` is null and its events are the ones on its paths) |
| `days[]` | `{"by_name": {name: {"kind","events"}}, "by_kind": {"reader"/"asked"/"training": {"visitors","repeat_visitors"}} or null}` - visitors are distinct keyed hashes that day (whole site), repeat ones were seen on an earlier day within 30 |
| `repeat_window_days` | 30 |
| `likely_ai`, `days[].ai_likely`, `today.ai_likely` | likely sent by an AI assistant, inferred (null: not recorded): [docs/DATA-CONTRACT-AI-LIKELY.md](docs/DATA-CONTRACT-AI-LIKELY.md) |
| `repeat_counts` | `"days"`: `times_seen_30d` counts distinct days the visitor was seen in the 30 days ending today, today included |

The addresses are written only here and in the private snapshot file
`live-<site>-ai.json` beside history (mode 0640); never in history, the
other data files, CSV exports or mail.

`events[]`, newest first, at most 200: `at` (ISO local), `name`
(`"ChatGPT-User"`, `"GPTBot"`, or the assistant a reader came from, e.g.
`"chatgpt.com"`), `kind` (`"asked"`, `"training"`, `"referred"` = a reader
who arrived from an assistant, one per page loaded), `path`, `status`,
`country` (code or `""`), `country_name`, `ip` (from today's raw log),
`repeat` (bool or null when the visitor key is not configured),
`times_seen_30d` (int or null), `first_seen` (date or null).

Repeat: the visitor is `HMAC-SHA256(SKALD_VISITOR_KEY, ip) + family`
(family = the assistant or crawler name; for readers the browser family and
system). History keeps that hash per day (`visitor_days`), 30 days, then
deletes it. `repeat` = the same hash on an earlier day within 30 days.

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
| `events` | `[{"name","label"}]`: the event names this site counts, in report order (`cta_click`, `book_demo_open`, `demo_booked`, `signup_start`, `signup_submit`, `contact_submit`, `waitlist_submit`, `outbound_click`, `scroll_75`, `copy_text`, `404_view`, and `page_view` in beacon-only mode) |
| `keep_days` | int, 400: how many days history keeps |
| `first_day` | date or null: the first day with events |
| `limits` | `{"factor","slack","day_factor","day_slack"}`: verify's bounds (events per page view) |
| `days[]` | `keep_days` entries ending yesterday, oldest first: `{"day","state"}`; `state` is `ok`, `withheld` (+ `problems`), `missing` or `before`. When `ok`: `events` `{event: n}`, `ours` `{event: n}` and `ai` `{assistant: {event: n}}` (both null on a view), `anomalies` `[{"kind": "path"/"404"/"unchecked"/"spool", "path","events","views","limit"} or {"kind","note"}]`, `audit` `"ok"`/`"mismatch"`/null, `by_source` (see "events.json goals" below) |
| `row_fields` | `["day","event","label","path","source","n"]` |
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

## People (2.4.0)

Each visit kept with its address (`visits`, `visit_days` in
`conversions.sqlite`), rows a sync removed (`removed`), the `test` mark, and
the helper's person lookup and left-out lists: not data files, not figures.
Every field: [docs/DATA-CONTRACT-PEOPLE.md](docs/DATA-CONTRACT-PEOPLE.md).

---

## Tracking additions

The day kinds `funnels`, `engagement`, `utm_hygiene`, `ai_likely` and `ai_fetches`, leads.json
`attribution_rows` and time to convert, and events.json goals: [docs/DATA-CONTRACT-TRACKING.md](docs/DATA-CONTRACT-TRACKING.md).
