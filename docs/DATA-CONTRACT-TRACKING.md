# Data contract: tracking additions (day kinds, leads, goals)

Split out of [../DATA-CONTRACT.md](../DATA-CONTRACT.md) to keep it under 1000 lines. Rules for all of them: none of them changes the history's schema (it is at 13: 12 added
indexes, 13 one meta row for the 2.4.0 privacy default); new day figures are `day_extras` kinds (listed in `store_extras.KINDS`, computed by a module registered in
`day_more.KINDS`, checked by its `check`); every figure has a second count registered in
`audit_more.py`; only `ok` days count; a figure not recorded is `null`, never 0; no rate over
fewer than 10.

### Day kind `funnels` (funnels.json `history`)

Each saved funnel (not the defaults) is counted over the day's journeys when the day is
collected, and in the live snapshot (`funnel_days.py`). **History starts the day it is saved**
(`saved_at` in `timezone`): a day before it is not recorded, never zero. Only the visit steps
(the first, `any` or a page, and later page steps) are counted; lead and event steps keep their
own history. Kept `report.retention_days` (400), like the other detail.

Journeys carry `at`: one entry per `trail` entry, the seconds since the visit's first request,
bucketed like durations (to the second under a minute, 10 s under ten minutes, the minute under
an hour, then 10 minutes). The trail and `at` keep the first 50 entries.
The web app's `data/app.json` gives each journey's trail as `{"path","page","at"}`: the same
offset on its step (Traffic > Visitors shows "+0 s, +40 s"). A journey stored before `at` was kept
has steps with no `at`, never a guessed 0. No new personal data: an offset is a bucketed time.

`day_extras` kind `funnels`: `{key: series}`. `key` is the first 16 hex digits of the SHA-256 of
`{"source", "steps"}` as JSON with sorted keys and no spaces (`","` and `":"`), `source` the
funnel's source or null, `steps` its visit steps without labels (`{"kind":"any"}` or
`{"kind":"path","match","paths"}`). Changing a page, a match or the source starts a new series;
renaming or relabelling does not. A series:

| field | meaning |
|---|---|
| `name`, `source`, `steps` | the funnel when counted; `steps` its visit steps with labels |
| `visits` | the day's visits from the source (all visits when `source` is null) |
| `reached` | `[int]` per step: visits that reached it. A step is met by the first trail entry at or after the entry that met the step before (`any` uses none). The source is met by the visit's source type, the assistant or site that sent it (`via`), or its referring host, in any case |
| `by_source`, `by_device` | `{label: [int per step]}`; each step sums to `reached` |
| `next` | per step, `{path: n}` for the visits that got no further: the first later trail entry with another path, or `"(left the site)"`; after `any`, the landing page. For the last step, every visit that reached it. Top 10 and `"(all others)"`; sums to `reached[k] - reached[k+1]` (the last: `reached[k]`) |
| `complete` | `{bucket: n}` for the visits that reached the last step, by `at` of the last step's entry minus `at` of the first step's (0 for `any`): `under 10s`, `10-30s`, `30s-1m`, `1-3m`, `3-10m`, `10-30m`, `30m or more`; sums to the last `reached`. Null with one step |

Verify withholds the day when a sum fails, a step has more visits than the one before, or a key
does not match its steps. Second count: `audit_funnels.py` (every audit, and `audit --live`)
rebuilds each visit's trail and offsets from the raw lines, reads `funnels.json` itself, and
recounts every stored series (one no longer saved from its stored steps, once their hash is its
key) with its own step matching; any difference withholds the day.

funnels.json `history` of a saved funnel: `{"key","since" (the day it was saved, or the first
day stored under its key if earlier; null when neither),"steps": [label],"days": [...],"today"}`.
`days`: from `since` to yesterday (at most the file's 180 days), `{"day","state"}` as in Rules,
plus, on an `ok` day only, `visits`, `reached`, `by_source`, `by_device`, `next`, `complete`
(each null when that day was not recorded). `today`: `{"day", ...the same}` from a good
snapshot, or null. Any range sums from the `ok` days; a rate over fewer than 10 visits is not
given.

### Day kind `engagement` (visits.json)

Written (lane B): `engagement.py`, second count `audit_engagement.py`. Each `visits.json`
`days[]` entry (with figures) and `today` (when `ok`) gain two fields, both `null` when not
recorded:

- `engagement`: `{"by_source": {source type: Row}, "by_device": {device: Row}}`, from the
  day's people visits. `Row` = `visits` int, `views` int (pages loaded), `one_page` int
  (visits that loaded one page), `seconds` `{"<bucket seconds>": visits}` (the buckets of
  `stats.seconds`). All counts: sum any range of `ok` days, then read pages per visit
  (`views / visits`), the one-page share (`one_page / visits`) and the median length (from
  `seconds`). Each map sums to the day's visits, pages loaded and one-page visits; its rows
  equal `stats.source` / `stats.device`. A day with no people: two empty maps.
- `returning_by_source`: `{"by_source": {source type: {"readers": int, "returning": int}},
  "warming_up": bool}`. Labelled by THIS visit's source (overview's and campaigns'
  `first_touch` keep the source of the visitor's first visit in 30 days). New = `readers -
  returning`. Null without the visitor key. `warming_up`: history held hashes from fewer
  than 29 days before the day (the key is new, or the day was backfilled after its earlier
  hashes were pruned), so `returning` is a floor. Stored in the `returning` day kind as
  `by_source` and `warming_up`.

Second count: the audit labels each visit's first page with its own labels, buckets the
span of its lines with its own rule, and recounts every field of every row; it recounts
`by_source` from its own keyed hashes against the earlier days in `visitor_days` (the whole
site only). The page gives no rate over fewer than 10 visits ("too few to say"). No
address, user agent or hash is in either field.

### Day kind `utm_hygiene` (campaigns.json)

Campaign tag hygiene (`utm_hygiene.py`), per day from the day's journeys (one per visit, by
its landing page). campaigns.json `days[].utm_hygiene` and `today.utm_hygiene`: the blob, or
`null` on a day it was not counted.

| field | type |
|---|---|
| `visits` | int: the visits looked at (= the day's visits) |
| `counts` | `{"source_no_medium","unknown_medium","click_id_no_tags","internal_tags"}`: visits whose landing address had utm_source without utm_medium; a utm_medium outside `classify.UTM_MEDIUMS`; an ad click id (`classify.CLICK_ID_PARAMS`) and no utm_ tag; a utm_ tag on a link from one of the site's own hosts (EDGE-CASES E8). A visit can be in more than one |
| `paths` | `{problem: {landing path: visits}}`: the 20 largest and `"(all others)"`; each adds up to its count |
| `examples` | `{problem: [{"path","tags","click_id"}]}`: the day's first three; `tags` is only the utm_ tags (`"utm_source=x&utm_medium=y"`), `click_id` the network (`"Google Ads"`), never the id; no other query value |

Verify: `visits` equals the day's visits, each problem's `paths` add up to its count, no
count above the visits. Second count: `audit_utm.py` (registered in `audit_more.RECOUNTS`)
reads each visit's first page line again with `parse_qsl` and its own rules, and compares
`visits`, every count and every kept path. Examples are illustrations, not figures.
"Campaigns in leads but never in the log" is worked out in the app from leads.json
(`period.first_touch`/`last_touch.utm_campaign`, last 30 days) against every `ok` day's
`utm_campaign` rows, only when the lead store is set up.

### Day kinds `ai_likely` and `ai_fetches`

Likely sent by an AI assistant (inferred, never a count; `ai_likely.py`, `ai_fetches.py`,
second count `audit_ai_likely.py`): [docs/DATA-CONTRACT-AI-LIKELY.md](DATA-CONTRACT-AI-LIKELY.md).

### leads.json `attribution_rows`

Written (lane A, `leads.py`; second count `audit_leads.py`). Leads by day crossed with
their type, status and both touches, so the app sums any range of the 180 days.

| field | type |
|---|---|
| `attribution_columns` | `["day","type","status","touch","source_type","ai","campaign","utm_source","utm_medium","landing","paid","likely_ai","n"]` (`likely_ai`, an estimate, and top-level `likely_ai`: [docs/DATA-CONTRACT-AI-LIKELY.md](DATA-CONTRACT-AI-LIKELY.md)) |
| `attribution_rows` | list of rows in that order, for the 180 days ending today (local), or `{"state": "withheld", "why"}` |

- Every lead counts twice, once with `touch` `"first"` and once `"last"`. Spam and
  duplicates are included: `status` says which, and the app leaves them out of lead
  counts. So for each day and touch, `n` adds up to the day's `status` total.
- `source_type`: one of the source types, by the same rules as the logs; `"(none)"`
  when the lead has no such touch (then every label is `"(none)"` and `paid` false).
- `ai`, `campaign`, `utm_source`, `utm_medium`: lower case, at most 60 characters;
  `landing`: at most 120. `"(none)"` when the touch did not carry it.
- `paid`: true when the touch carried `gclid`, `gbraid`, `wbraid` (Google Ads clicks from
  iOS) or `msclkid`, or its `utm_medium` is a paid medium (cpc, ppc, paid, paidsearch,
  paidsocial, display, cpm and spellings). A touch without one of these fields (an old
  lead, a site that does not send it) reads it as empty.
  `fbclid` alone is not paid: Facebook adds it to every link out.
- **Statuses are as of now.** When the team changes a lead's status in the website's
  admin, past days change with it.

### leads.json time to convert

Written (lane A, `leads.py`; second count `audit_leads.py`, SQL `julianday` buckets).
`time_to_convert` is `{"state": "withheld", "why"}` or:

| field | type |
|---|---|
| `first`, `last` | the 180 days ending today |
| `buckets` | `["<1h","<1d","1-7d","8-30d","31-90d",">90d","unknown","clock_error"]` |
| `rows` | `[[day, type, bucket, n]]`: leads (spam and duplicates left out) by the elapsed time from `first_touch.at` to `created_at`. `<1d` is 1 to 24 hours; `1-7d` is 1 to 7 whole days (so up to 8 days less a moment). `unknown`: no first touch or no readable `at`; `clock_error`: `at` after the lead |
| `known` | leads over the 180 days with a known, non-negative time |
| `median_hours` | their median in hours (1 decimal), `null` under 10 known |
| `visits_buckets` | `["0","1","2","3-5","6-10","11+","unknown"]`, or `null` when the lead store has no `visits` column |
| `visits_rows` | `[[day, type, bucket, n]]`: leads by the website's `visits` value (the browser's visit count when it sent the form), or `null` with no such column. A value that is not a whole number of at least 0 is `unknown` |

For each day, `rows` and `visits_rows` each add up to the day's leads.

### events.json goals (`beacon.goals`, events by source)

`beacon.goals` (config, or Settings > Sites > Goals: `settings_store`, the site's row
wins): a list of event names that are goals; names this site does not count are ignored. events.json gains:

| field | type |
|---|---|
| `days[].by_source` | `"ok"` (the recount by event and source matched), `"withheld"` (it did not), or `null` (not recounted by source yet, or not an `ok` day) |
| `rows[]` source | `null` on a day whose `by_source` is `"withheld"`: its totals stand, its sources are not shown |
| `goals` | `null` when no goal is set, else `{"names": [event],"labels": {event: label},"min_rate": 10,"days": [...]}` |
| `goals.days[]` | one per day from `first_day` to yesterday: `{"day","state": "ok","visits": {source type: visits},"events": {goal: {source type: n}}}` or `{"day","state": "left_out","why"}` |

A goal day is `ok` only when its events are `ok`, its `by_source` is `"ok"`, and its log
day is `ok` (whole and verified) with breakdowns; `why` says which failed. `visits` are the
log's readers by source (on a view, the view's). The app sums any range and shows events per
100 visits by source, and no rate over fewer than `min_rate` visits ("too few to say").
Second count: `events.audit` recounts the spool's `s` field with its own pattern and compares
people's events by event and source; visits by source are the audited readers by source.
