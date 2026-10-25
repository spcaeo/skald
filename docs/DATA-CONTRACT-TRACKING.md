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

### Day kind `direct_likely` (campaigns.json)

Direct, likely a checkout return, an in-app browser or a shared link (inferred, never a count;
`direct_likely.py`, name lists `direct_names.py`, second count `audit_direct_likely.py`; the
rules are in [CLASSIFICATION.md](../CLASSIFICATION.md), "Inferred, not classified: Direct,
likely ..."). Per day from the day's journeys. campaigns.json `days[].direct_likely` and
`today.direct_likely`: the blob, or `null` on a day it was not recorded (before this release,
or `attribution.direct_likely: false`), never zeros.

| field | type |
|---|---|
| `share_window_minutes` | int: the link-preview window the day was counted with |
| `visits` | int: the visits looked at (= the day's visits) |
| `direct` | int: of which Direct (source `Direct or unknown`) = the Sources tab's Direct row |
| `likely` | int: of which given a likely reason |
| `plain` | int: of which not (`direct - likely`) |
| `reasons` | `{"checkout","in_app","shared": visits}`: always all three; adds up to `likely` |
| `details` | `{reason: {detail: visits}}`: `checkout` by provider (`Stripe`, `PayPal`, `Razorpay`, `Checkout.com`, `Adyen`) or `"(return page)"`; `in_app` by browser label (`Instagram app`, `Facebook app`, ..., `In-app browser (iOS)`); `shared` by app (`WhatsApp`, `Slack`, `Instagram`, ...), `"(share tag)"` or `"(more than one)"`. Each adds up to its reason |

```json
{"share_window_minutes": 30, "visits": 18, "direct": 15, "likely": 10, "plain": 5,
 "reasons": {"checkout": 4, "in_app": 2, "shared": 4},
 "details": {"checkout": {"(return page)": 2, "PayPal": 1, "Stripe": 1},
             "in_app": {"Facebook app": 1, "Instagram app": 1},
             "shared": {"(more than one)": 1, "(share tag)": 1, "Instagram": 1, "WhatsApp": 1}}}
```

The top-level `direct_likely` of campaigns.json: `{"on", "share_window_minutes", "method",
"reasons"}` (the setting, the window now, the method in one sentence, each reason's words).
Each likely visit's journey (visits.json, the live snapshot, app.json) carries
`likely_direct` `{"reason", "detail"}`, and `"minutes"` (from the nearest preview) for a link
preview. No query value of a landing address is ever kept: only the reason, the detail and
counts.

Verify withholds the day when `reasons` does not add up to `likely`, `likely + plain` is not
`direct`, a reason's `details` do not add up to it, `visits` is not the day's visits, `direct`
is not the visits whose source is Direct, or the journeys marked with each reason are not its
count. Second count: `audit_direct_likely.py` (registered in `audit_more.RECOUNTS`, so the
daily audit and `audit --live` both compare it) reads each Direct visit's first page line
again, splits its query by hand, reads the path and the audit's own browser label with its
own code, rebuilds the link previews from the audit judge's own verdicts, and compares
`visits`, `direct`, `likely`, `plain`, every reason and every detail, with the window the
stored day says it used. It shares only `direct_names.py`'s lists.

### Day kind `social_networks` (campaigns.json)

The Social media visits by network: X, LinkedIn, Facebook, ... (a count, not an estimate;
`social_networks.py`, name lists `social_names.py`, second count `audit_social.py`; the rules
are in [CLASSIFICATION.md](../CLASSIFICATION.md), "The source type of a visit", Social
networks). Per day from the day's journeys, each visit's first page's referrer and landing
address. campaigns.json `days[].social_networks` and `today.social_networks`: the blob, or
`null` on a day it was not recorded (before this release), never zeros.

| field | type |
|---|---|
| `visits` | int: the visits looked at (= the day's visits) |
| `social` | int: of which Social media = the Sources tab's Social media row |
| `networks` | `{id: visits}`, most first: only networks with a visit; adds up to `social`. Ids: `x`, `linkedin`, `facebook`, `threads`, `instagram`, `reddit`, `youtube`, `tiktok`, `pinterest`, `bluesky`, `mastodon`, `hackernews`, `quora`, `telegram`, `whatsapp`, `slack`, `discord`, and `other` (Social, network not named) |
| `via` | `{id: {how: visits}}`: a referring host (`t.co`, `l.facebook.com`, no `www.`), an app (`android-app://com.linkedin.android`), or a tag (`(utm_source)`, `(utm_medium)`, `(fbclid)`, `(li_fat_id)`, `(ttclid)`, `(twclid)`); each adds up to its network |
| `landings` | `{id: {path: visits}}`: the landing pages, the top 20 (most first, then the path) and `"(all others)"`; each adds up to its network |

```json
{"visits": 12, "social": 6,
 "networks": {"x": 3, "linkedin": 2, "other": 1},
 "via": {"x": {"t.co": 1, "android-app://com.twitter.android": 1, "(utm_source)": 1},
         "linkedin": {"lnkd.in": 2}, "other": {"(utm_source)": 1}},
 "landings": {"x": {"/": 2, "/blog/a": 1}, "linkedin": {"/pricing": 2}, "other": {"/": 1}}}
```

The top-level `social_networks` of campaigns.json: `{"names": {id: name}, "order": [ids],
"method"}` (each network's name as shown, the list's order, the method in one sentence). Only
hosts, app ids, tag names, paths and counts are kept: never a query value, an address or a
whole referrer.

Verify withholds the day when `networks` does not add up to `social`, a network's `via` or
`landings` do not add up to it or name other networks, a network is not in the list or kept
with no visit, `visits` is not the day's visits, or `social` is not the visits whose source is
Social media. Second count: `audit_social.py` (registered in `audit_more.RECOUNTS`, so the daily
audit and `audit --live` both compare it) reads each Social media visit's first page line
again (the audit's own source label), reads its referrer's host and splits its query by hand,
with its own code, and compares `visits`, `social`, every network, every `via` entry and every
folded landing page. It shares only `social_names.py`'s lists.

**Across sites** (the site picker, `across_sites.py`): no new figure. It reads each site's
`data/app.json` (`days[].state`, `days[].by.source`, `live`) and `data/campaigns.json`
(`days[].social_networks`, `today`) and sums verified days only, as the page does; a figure no
verified day recorded is "Not recorded", a network figure whose day does not add up to its
Social media readers is "Withheld". Only the sites the viewer's organisations hold are read.

### Day kind `ai_formats` (app.json)

Since 2.10.0: every answer-engine request by what its path names (`ai_formats.py`; second count
`audit_ai_formats.py`, from the raw lines with its own path rule). The formats, in order:
`Page`, `llms.txt` (`/llms.txt`, `/llms-full.txt`), `Markdown` (`.md`, `.mdx`), `Text` (other
`.txt`), `robots.txt`, `Sitemap` (`sitemap*.xml`), `Other file`; the rules are in
[CLASSIFICATION.md](../CLASSIFICATION.md) ("What an AI fetch asked for").

```json
{"asked":    {"formats": {"Page": 12, "Markdown": 3},
              "by_name": {"ChatGPT-User": {"Page": 10, "Markdown": 3}, "(all others)": {"Page": 2}}},
 "training": {"formats": {}, "by_name": {}}}
```

- Both tiers are always there. `formats` adds up to the tier's requests (`engine_tier`);
  `by_name` keeps the 20 names with the most fetches that day (the classifier's token, as
  `engines` names them) and folds the rest into `"(all others)"`, so each format over the names
  adds up to `formats`. Only formats seen are keys. Verify withholds the day when a sum fails;
  the audit compares every format, every kept name and the folded rest.
- The web app's `data/app.json` gives the blob as `days[].ai_formats` on a day with figures and
  `live.figures.ai_formats` today; a day collected before 2.10.0 has no `ai_formats` (not
  recorded, never 0), and AI & bots > Assistants and Crawlers ("What they fetch") then show no
  table for a range that holds one. Kept for good, like the other small day kinds.

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

### Day kind `landings` (visits by the page they started on)

`landings.py`, from the day's journeys (and the live snapshot's, for today). Each people
visit is counted once, on its first page, as the readers' landing breakdown counts it:

    {"fields": ["visits", "one_page", "views", "search", "ai"], "top": 200,
     "folded": 0, "pages": {"/pricing/": [12, 9, 17, 4, 1], ...}}

| field | meaning |
|---|---|
| `visits` | visits that started on the page |
| `one_page` | of them, visits that loaded that one page and no other: one page view in the log. This is **"left at once"** on Summary and Pages. A step a single-page app shows without asking the server is not in the log, so on such a site it is an upper bound |
| `views` | the page views those visits made, on every page |
| `search` | of the visits, those whose source is `Search engine` |
| `ai` | of the visits, those whose source is `AI assistant` (a referrer or a tag; "likely" AI visits are never here) |

The 200 pages with most visits (ties by path) are kept; the rest are summed into one
`(all others)` row and `folded` says how many paths it holds. `check` (verify) holds every
row to one_page <= visits <= views and search + ai <= visits, and the sums to the day's
visits, one-page visits, people's page views and visits by source. A day collected before
this kind existed has no blob: **not recorded** (null), until the day is recounted.
Second count: `audit_landings.py` (audit_more.RECOUNTS), from the raw lines with the
audit's own landing label, page rule and source labels: every kept row field by field, the
`(all others)` row against every page it does not keep, and `folded`.

### page_trends.json (each page by day, pages changed lately)

`page_trends.py` (data_more.FILES). Nothing new is counted: stored, audited day figures
put side by side per page, for Overview > Summary, Traffic > Pages and AI & bots >
Assistants. A view (page group) gets `{"whole_site_only": true}`: crawl health and the
change dates are the whole site's.

| field | meaning |
|---|---|
| `fields` | the landings row fields, as above |
| `first_day` | the first day with a `landings` blob, or null |
| `days[]` | one per day of the window: `{"day","state"}`, and on an `ok` or `partial` day `landings` (the stored blob or null: not recorded) and `fetches` |
| `days[].fetches` | the assistants' user fetches (day kind `ai_fetches`: ChatGPT-User, Perplexity-User, Claude-User and the other user fetchers) as `{"paths": {path: {assistant: n}}, "folded": n}`; the 200 paths with most fetches kept (ties by path), the rest summed per assistant into `(all others)`; null when not recorded |
| `today` | the snapshot's `{"state","from","until"}` with the same `landings` and `fetches`, or null |
| `changed` | `{"days": 30, "since", "until", "rules", "pages": [...], "counts"}`: the pages whose change date (`updated`: the website's own date, else the sitemap's `<lastmod>`) falls in the last 30 days to the last whole day |
| `changed.pages[]` | `path`, `changed`, `source` (`website`/`sitemap`), `visits` and `search` (visits that started on the page from the change date on, over whole verified days; null when no such day has a blob), `first_search` (the first of those days with a search visit), `counted_from`, `unmeasured` (days from the change date that were not whole, verified and recorded), `at_least` (a day folded the page into `(all others)`: the figures are a floor), `google` (the verified Google crawler fetched the page on such a day, by crawl health; null when no such day has crawl health), `google_last` |
| `changed.counts` | `pages`, `measured`, `visited`, `searched`, `none` (measured with no visit), `google` |
| `same_day` | the sitemap's dates look like build times: more than half of at least 10 dated pages carry one date: `{"day","pages","of"}`, else null |

Paths are compared with `?` and `#` cut and a trailing `/` added. Second count:
`audit_page_trends.py` (audit_more.DAILY): its own SQL for the day states and the blobs,
its own fold of the fetches, the change dates by `audit_lastmod.expected`, and every
field of `days[]`, `changed` and `same_day` worked out again.
