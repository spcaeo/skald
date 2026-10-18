# Likely sent by an AI assistant (inferred)

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply. The method is
[CLASSIFICATION.md](../CLASSIFICATION.md), "Inferred, not classified".

**An estimate, never a count.** A visit is "likely referred by" an assistant
when its source is "Direct or unknown", its landing address has no utm_ tag
and no ad click id, and that assistant's user fetcher fetched the page it
landed on in the same minute as the visit's first request or up to the
window before it (`attribution.ai_window_minutes`, default 15). Minutes in
UTC; paths without the query, 70 characters, trailing `/` ignored. Two or
more assistants: once, under `"(more than one)"`. It is never added to the
"AI assistant" source, to people or to any other figure. Every place that
shows it says "likely" and gives the window.

Assistants are named as their citations are (`classify.AI_FETCHER_OWNERS`):
`chatgpt.com`, `perplexity.ai`, `claude.ai`, `gemini.google.com`,
`copilot.microsoft.com` (BingPreview), `mistral.ai`, `meta.ai`.

Config: `attribution.ai_likely` (default true; false: nothing below is
recorded, and the figures read "not recorded", never 0) and
`attribution.ai_window_minutes`.

## Day kind `ai_likely`

`ai_likely.py`, in the tally pass, for a collected day and today's live
snapshot. `null` when off or when the visits were not counted.

| field | type |
|---|---|
| `window_minutes` | int: the window this day was counted with |
| `visits` | int: the day's visits (journeys) |
| `direct` | int: of which direct and untagged - what the estimate can explain |
| `likely` | int: of which likely referred by an assistant |
| `by_assistant` | `{assistant or "(more than one)": visits}`, adds up to `likely` |
| `pages` | `{landing page: likely visits}`: the 20 largest and `"(all others)"`, adds up to `likely` |
| `fetches` | `{assistant: user-fetch requests that day}`, adds up to the answer-engine group's `asked` requests |
| `followed` | `{assistant: fetches followed, within the window, by a direct untagged visit landing on the same page}`. A fetch-side figure: a visit two assistants fetched for follows a fetch of each. Never above `fetches` |

The share of direct visits it explains is `likely / direct` (no rate over
fewer than 10). Answers turned into clicks, per assistant, is `followed /
fetches`.

Verify withholds the day when `by_assistant` or `pages` do not add up to
`likely`, `likely` is above `direct` or `direct` above `visits`, `visits`
is not the day's visits, `fetches` do not add up to the `asked` requests,
a `followed` is above its `fetches`, or the journeys marked `likely_ai`
are not `likely`.

## Day kind `ai_fetches`

`ai_fetches.py`. The day's user fetches, so leads and conversions can look
back from a touch: `{"rows": [[minute, assistant, path, n]]}`, `minute` UTC
`"YYYY-MM-DDTHH:MM"`, `path` without the query (70 characters), `n` the
fetches that minute. Only user fetchers (`AI_ASKED`): no training crawler,
no person, no address, no user agent. The rows add up to the day's `asked`
requests. Kept **180 days** (`ai_likely.FETCH_DAYS`, the leads' window),
then deleted (`cli.prune_kept`). Not in any data file.

## Day kind `ai_read`: what the AI read before it sent the visitor

`ai_read.py`, after `ai_likely` in the tally pass. Context, never a count
of people. An AI visit is **cited** (source "AI assistant", by referrer or
utm tag, from an assistant with a user fetcher: a value of
`classify.AI_FETCHER_OWNERS`) or **likely** (it carries `likely_ai`). Its
assistants (the cited one, or every assistant that made it likely) may have
fetched pages, by their user fetchers only (`AI_ASKED`, never a training
crawler), in the visit's first minute or up to the window before it, the
same window and minute rule as above. A citation from an assistant with no
known user fetcher (You.com, Phind, Poe) is left out: not recorded, never 0.
`null` when `attribution.ai_likely` is false or the visits were not
counted; days before this kind have none (not recorded).

| field | type |
|---|---|
| `window_minutes` | int: the window this day was counted with |
| `cited` | int: cited visits from an assistant with a user fetcher |
| `likely` | int: likely visits; equals `ai_likely.likely` |
| `marked` | int: visits that carry `ai_read` (at least one page fetched before) |
| `listed` | int: paths listed over those visits, at most 10 a visit |
| `beyond` | int: paths left out by the cap of 10 |
| `by_assistant` | `{assistant or "(more than one)": {"cited", "fetched", "same_page", "likely"}}`: cited visits from it; of which it fetched a page in the window before; of which the landing page was one of those pages ("fetch -> visit to the same page", paths compared as above); likely visits under its name (they land on a fetched page by their rule, so they are kept apart) |

Verify withholds the day when `by_assistant` does not add up to `cited` or
`likely`, `fetched` plus `likely` is not `marked`, a `same_page` is above
its `fetched` or a `fetched` above its `cited`, `likely` is not
`ai_likely.likely`, the journeys carrying `ai_read` are not `marked`, their
paths are not `listed`, a visit lists more than 10, or the cited journeys
are not `cited`.

```json
{"window_minutes":15,"cited":3,"likely":1,"marked":4,"listed":16,"beyond":2,
 "by_assistant":{"chatgpt.com":{"cited":1,"fetched":1,"same_page":1,"likely":1},
   "claude.ai":{"cited":1,"fetched":1,"same_page":1,"likely":0},
   "perplexity.ai":{"cited":1,"fetched":1,"same_page":0,"likely":0}}}
```

## Journeys (visits.json)

A likely visit's journey carries `likely_ai`: `{"name": assistant or
"(more than one)", "names": [every assistant in the window], "minutes":
int}` (from the nearest fetch to the visit's first request). Other journeys
have no `likely_ai`. Kept like the journeys: 7 days.

An AI visit (cited or likely, above) whose assistant fetched at least one
page in the window carries `ai_read`: `{"how": "cited" | "likely", "name":
assistant or "(more than one)", "names": [assistants looked at],
"window_minutes": int, "paths": [[path, assistant, minutes before]],
"more": int}`. `paths` holds each (path, assistant) once, at its nearest
fetch, nearest first (then path, then assistant), at most 10; `more` counts
the ones left out. Paths as the fetch records keep them (no query, 70
characters). Shown in the visit's drawer as "Fetched by <assistant> in the N
minutes before". Kept like the journeys: 7 days.

## ai_activity.json

| field | type |
|---|---|
| `likely_ai` | `{"on": bool, "window_minutes": int, "method": the sentence the page shows}` |
| `days[].ai_likely` | the day's blob above, or `null` (not recorded) |
| `today.ai_likely` | today's so far from the live snapshot, or `null` |
| `days[].ai_read`, `today.ai_read` | the `ai_read` blob above, or `null` (not recorded) |

## leads.json

`attribution_columns` gains `"likely_ai"`, just before `"n"`. Per row:

- the assistant (`"chatgpt.com"`, ...) or `"(more than one)"`: the touch's
  source is "Direct or unknown" with no utm campaign, and the assistant
  fetched its `landingPath` in the window before its `at`;
- `"(none)"`: the touch is not direct, or no fetch matched;
- `"(not recorded)"`: a direct touch whose window reaches a day without
  stored fetches (before the feature, past the 180 days, a day not whole
  and verified, or today until it is collected), or a touch with no
  landing page or time.

Top-level `likely_ai`: `{"on", "window_minutes", "method"}`. A lead is still
never joined to a visit: the match is between the lead's own touch and the
stored fetch rows, never a person. Second count: `audit_leads.py` reads the
stored fetch rows by its own SQL (`json_each` over `day_extras`, whole and
verified days only) and matches each touch with its own code; a difference
withholds `attribution_rows`.

## conversions.json

Each `ok` day gains `likely_ai`: `{action: {label: n}}` over finished rows,
labels as for leads but `"Unknown"` for not recorded. The touch is the
first touch: for a row with a `first_source` (the lead database, a hook),
it must be "Direct or unknown", the page is `landing` and the time
`first_touch_at`; else, for a row with a visitor ID (the beacon), the
browser's earliest journey row (its source type, path and time). A row
keeps no first-touch campaign, so "untagged" here means only what the
source says: no referrer, no utm_source or utm_medium, no ad click id. A
first touch not known, or with no page or time, is "Unknown". Adds up,
per action, to the day's finished rows. Second count:
`audit_conversions_figures.py`, by its own SQL over the file and the
history opened read-only; a difference withholds the day.

## Second count of the day kinds

`audit_ai_likely.py`, registered in `audit_more.RECOUNTS`: every audit and
`audit --live`. It sees every line the audit judged and every people
visit, and rebuilds the fetch rows, the direct untagged visits (its own
`parse_qsl` reading of the landing address, its own path rule) and every
field of `ai_likely` with the stored day's window. It also rebuilds every
field of `ai_read`: the cited visits with its own reading of the first
page's referrer host and utm tag, the likely ones from its own likely
rule, and each visit's distinct (path, assistant) pairs from its own fetch
rows. It shares only `classify.py`'s name lists. Any difference withholds
the day.

```json
{"window_minutes":15,"visits":4,"direct":3,"likely":2,
 "by_assistant":{"(more than one)":1,"chatgpt.com":1},"pages":{"/docs":1,"/pricing/":1},
 "fetches":{"chatgpt.com":1,"claude.ai":1,"perplexity.ai":1},
 "followed":{"chatgpt.com":1,"claude.ai":1,"perplexity.ai":1}}
```
