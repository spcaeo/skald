# conversions.json

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply.

Conversions (Phase 4b; `conversions_data.py`, docs/INTEGRATIONS.md): what
visitors did that counts, from `conversions.sqlite` - the hooks, the
beacon's events with visitor IDs, and the site's lead database (tool
`site`). The same file on the site's page and every view's (conversions
do not know about views). Anonymous: no name, email, address or visitor ID.
Statuses and cancellations are "as known now": a later change rewrites the
day the action was taken.

| field | type |
|---|---|
| `available` | bool; false: `reason` says why (no conversions file yet) and every block below is empty |
| `set_up` | `{"beacon","visitor_ids","leads_db","store": bool, "hooks": [tool names with a secret]}`: what is on, for the tab's empty states |
| `min_rate` | int, 10: no rate over fewer starts or browsers |
| `as_known` | the "as known" sentence the tab shows |
| `abandon_hours` | number, 24: how long a start may wait for its finish |
| `stages`, `finished` | the stages in report order; the ones that count as completed (`completed`, `paid`) |
| `dims`, `visit_buckets`, `convert_buckets` | the breakdown names and bucket names below, in order |
| `since` | local date of the first conversion kept, or null |
| `days[]` | 180 entries ending today (local), oldest first: `{"day","state"}`; `state` is `ok`, `withheld` (+ `why`) or `before` (before `since`: not recorded, never zero). When `ok`: `stages` `{action: {stage: n}}` (every row); `abandoned` `{action: n}` (starts with a visitor ID, the window closed, not finished by the same browser and action); `by` `{dim: {action: {label: n}}}` for finished rows, dims `source_type` (last touch), `first_source`, `campaign`, `landing`, `country`, `device`, `tool`, `"Unknown"` for a value not recorded; `visits_before` and `time_to_convert` `{action: {bucket: n}}` for finished rows (`unknown`, and `clock_error` when the first touch is after the conversion); `assisted` `{action: {source: n}}` (each finished conversion with a visitor ID counted once per earlier journey source that is not its last touch) or null without journeys |
| `period` | `{"first","last"}`: the last 30 days (today included) of the two blocks below |
| `pages_before` | null without journeys (visitor IDs off), `{"state": "withheld","why"}`, or `{"converting","other","pages": [[path, converting, other]]}`: browsers with a finished conversion in the period and a journey up to it, and the browsers seen in the period that did not convert; per page, how many of each saw it (the converting ones before converting). Top 50 by converting, then other, then path; exact |
| `timeline[]` | the latest 50 finished conversions of the period, one per browser (or per lead without one), newest first, withheld days left out: `{"at","action","stage","tool","source","first_source","campaign","landing","country","device","visits_before","first_touch","browser": bool,"visits": [{"day","source","paths": [up to 15]}] (last 10 days with page views up to the conversion; [] without a browser),"steps": [{"at","action","stage","tool"}] (up to 20)}`. Times are local ISO. A listing, not a figure |
| `withheld` | `{"days/<day>" or "pages_before": why}` |

A day's `by` tables each add up, per action, to its finished stages; its
`visits_before` and `time_to_convert` too. A `withheld` day shows no figures.

**Second count.** `audit_conversions.check_file` runs on every build: the
stages per day against the hook spool, the beacon spool (whole days from
the audit's own `conversions-audit.json`) and the lead database (its own
SQL), and every other figure of every day and `pages_before` against
`audit_conversions_figures.py`, which counts them again by SQL GROUP BY over
the file opened read-only. A day either road disagrees on is withheld, and
so is `pages_before`; a recount that cannot run withholds them all.

```json
{"available":true,"set_up":{"beacon":true,"visitor_ids":true,"leads_db":true,"store":true,"hooks":["calendly"]},
 "min_rate":10,"abandon_hours":24.0,"since":"2026-10-11",
 "days":[{"day":"2026-10-11","state":"ok","stages":{"demo":{"started":1,"completed":2,"won":1}},
   "abandoned":{"contact":1},"by":{"source_type":{"demo":{"Search engine":2}},"tool":{"demo":{"beacon":1,"site":1}}},
   "visits_before":{"demo":{"2":1,"unknown":1}},"time_to_convert":{"demo":{"1-7d":1,"unknown":1}},
   "assisted":{"demo":{"Search engine":1}}}],
 "period":{"first":"2026-09-14","last":"2026-10-13"},
 "pages_before":{"converting":1,"other":1,"pages":[["/",1,0],["/pricing/",1,0],["/blog/",0,1]]},
 "timeline":[{"at":"2026-10-11T12:01:00+00:00","action":"demo","stage":"completed","tool":"beacon","browser":true,
   "visits":[{"day":"2026-10-09","source":"Search engine","paths":["/"]}],
   "steps":[{"at":"2026-10-11T12:00:00+00:00","action":"demo","stage":"started","tool":"beacon"}]}],
 "withheld":{}}
```
