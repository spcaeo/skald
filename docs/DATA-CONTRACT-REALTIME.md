# Real time: realtime.json and its helper route

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply.

## realtime.json

Overview › Real time (`realtime.py`): who is on the site now. Built by the live
run (every 2 minutes) inside its own tally, so the people rule is the main road's
to the letter, and kept in the live snapshot as `realtime` (never in history,
never mailed). Recounted from the raw lines by `skald audit --live`
(`audit_realtime.py`, registered in `audit_more.RECOUNTS`). No address and no
user agent anywhere in it. Written for the site's own data folder only: a page
group's copy says `"state": "site"` (the figures are the whole site's).

| field | type | meaning |
|---|---|---|
| `state` | `ok`, `stale`, `empty`, `withheld`, `site` | `stale`: the part is more than 10 minutes old; `withheld`: today's snapshot did not reconcile, so no figure is given; `empty`: no snapshot or no part yet |
| `realtime` | object or null | the snapshot's part, below; null unless `ok` or `stale` |

The snapshot's `realtime` part (times in the site's zone):

| field | type | meaning |
|---|---|---|
| `version`, `minutes`, `short` | int | 1; the window, 30; the short window, 5 |
| `until` | ISO | the end of the window (the snapshot's own `until`, not included) |
| `visits_today` | int | readers' visits today so far (= the journeys, = the readers) |
| `active` | `{"5": n, "30": n}` | readers' visits with any request (assets included) in the last 5 / 30 minutes before `until` |
| `per_minute[]` | `{"at", "under_way", "started", "requests": {group: n}}` | the last 30 clock minutes, oldest first, the last one running to `until`. `under_way`: visits whose first request was before the minute ended and whose last was in it or after; `started`: visits whose first request was in it; `requests`: every request of the site's hosts in it by group (another host's lines are not in it) |
| `countries` | `{code: {"visits", "active"}}` | every country with a visit today (the visit's first page's country, `"Unknown"` for none), and of those the visits active in the last 30 minutes |
| `cities` | `{"City, Region, CC": {"visits", "active", "lat", "lon"}}` | only with a city file (`logs.city_db`): every city with a visit today, every active one kept, then the most visits up to 60, the rest one `"(all others)"` row (no point); `lat`/`lon` the city's own point from the file (3 decimals), absent when the file has none. A visit whose city is not recorded is in no row |
| `sources`, `devices` | `{label: n}` | visits active in the last 30 minutes, by the labels of their first page |
| `pages` | `{path: n}` | people's page views in the last 30 minutes, top 25 and `"(all others)"`: adds up to `page_views` |
| `page_views` | int | people's page views in the last 30 minutes |
| `machines` | `{"answer_engines": {name: n}, "search_engines": {name: n}, "bots": n}` | requests in the last 30 minutes; the two named lists top 15 and `"(all others)"` |
| `newest[]` | `{"start", "country", "city", "device", "browser", "source", "via", "landing", "pages", "in_app", "active", "first_touch", "seq"}` (`in_app` the steps seen only in the browser, shown beside `pages`; `city` `""` when not recorded; `first_touch` the visitor's first known visit or null, `seq` the visit's place in the day, see DATA-CONTRACT-PEOPLE.md) | the 10 newest visits by first request; `start` to the minute; `active` `"5"`, `"30"` or `""` |
| `doing[]` (2.20) | `{"start", "last", "country", "city", "device", "source", "via", "landing", "pages", "trail", "seq", "first_touch", "active"}` (`last` the visit's newest request, local, to the second; `trail` its pages in order as the day's journeys hold them, a page loaded twice in a row once, at most 20: the first two and the newest) | the active visits (last 30 minutes), newest activity first, at most 50: Overview's "What visitors are doing now". Labels and paths only, as `newest` and the journeys. The audit recounts each row's start, country, pages and newest request, and that it lists every active visit up to 50 |

### Real time's helper route: GET `<page>/api/realtime`

What the page polls every 15 seconds (`realtime_api.py`, read-only, same
sign-in as the page; nginx routes it with `api/compare` and `api/page`). An
unknown site is 404.

| field | type | meaning |
|---|---|---|
| `ok`, `site`, `now` | | |
| `people_state` | `ok`, `withheld`, `empty` | today's snapshot's state |
| `people` | object or null | the snapshot's `realtime` part (above), as of its `until` |
| `people_counted` | ISO or null | when the snapshot was written |
| `requests` | `{"from", "until", "per_minute": [{"at", "requests"}], "total", "newest", "partial"}` | every request of the site's hosts per clock minute over the 30 minutes before `until` (the second it was read), unsorted (`realtime_tail.py`): read from the end of the plain log files only; `partial` true when the end was too large to read whole (64 MB), so the count is a floor |

The helper keeps an answer 10 seconds (many open pages cost one read) and writes
the last one beside the snapshot, `live-<site>-tail.json` (counts only:
`from`, `until` UTC, `per_minute` keyed by epoch minute, `total`, `newest`,
`partial`, `read_upto`: each plain file's size when the count began, read no
further), which `audit --live` counts again from the same bytes of the raw lines.

### Yesterday at this hour: the snapshot's `by_now` (2.13)

What Overview › Summary in Live mode compares today with (`by_now.py`): yesterday
from local midnight to the same local time of day as the snapshot's `until`,
counted by the live run with the same tally and verify as today, and carried in
app.json as `live.by_now` (the site's page only; a page group's has none). Never
stored, never mailed. Recounted from the raw lines by `skald audit --live`
(`audit_by_now.py`: the figures, and both days hour by hour).

| field | type | meaning |
|---|---|---|
| `day`, `from`, `until` | date, ISO, ISO | yesterday; its midnight; the cut (yesterday at today's time of day), not included |
| `state` | `ok`, `withheld`, `partial`, `empty` | `withheld`/`partial`: yesterday is stored so in history (or the recount did not verify: `problems`); `empty`: no line in the window. Only `ok` carries figures |
| `history` | state or null | yesterday's state in history; null when it is not collected yet (the daily run collects it in the morning) |
| `visitors`, `pages`, `ai_visitors` | int or null | readers, people's page views, and visits sent by an AI assistant's answer (cited, per address and user agent and gap) to the cut |
| `hours` | `{"visitors", "pages", "ai_visitors"}` of 24 ints, or null | yesterday by local hour to the cut: readers by the hour of their first page, page views and AI-sent visits by the hour of the request that counted them; null when one does not add up to its figure |
| `today_hours` | the same, or null | today so far, by the same rules (adds up to the snapshot's `people.readers`, `people.views`, `people.cited_visits`) |

conversions.json `today.by_now` holds the leads ([DATA-CONTRACT-CONVERSIONS.md](docs/DATA-CONTRACT-CONVERSIONS.md)).

### Real time's helper route: GET `<page>/api/realtime`

What the page polls every 15 seconds (`realtime_api.py`, read-only, same
sign-in as the page; nginx routes it with `api/compare` and `api/page`). An
unknown site is 404.

| field | type | meaning |
|---|---|---|
| `ok`, `site`, `now` | | |
| `people_state` | `ok`, `withheld`, `empty` | today's snapshot's state |
| `people` | object or null | the snapshot's `realtime` part (above), as of its `until` |
| `people_counted` | ISO or null | when the snapshot was written |
| `requests` | `{"from", "until", "per_minute": [{"at", "requests"}], "total", "newest", "partial"}` | every request of the site's hosts per clock minute over the 30 minutes before `until` (the second it was read), unsorted (`realtime_tail.py`): read from the end of the plain log files only; `partial` true when the end was too large to read whole (64 MB), so the count is a floor |

The helper keeps an answer 10 seconds (many open pages cost one read) and writes
the last one beside the snapshot, `live-<site>-tail.json` (counts only:
`from`, `until` UTC, `per_minute` keyed by epoch minute, `total`, `newest`,
`partial`, `read_upto`: each plain file's size when the count began, read no
further), which `audit --live` counts again from the same bytes of the raw lines.
