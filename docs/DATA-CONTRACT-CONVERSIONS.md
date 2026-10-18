# conversions.json

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply.

Conversions (Phase 4b; `conversions_data.py`, docs/INTEGRATIONS.md): what
visitors did that counts, from `conversions.sqlite` - the hooks, the
beacon's events with visitor IDs, and the site's lead database (tool
`site`). The same file on the site's page and every view's (conversions
do not know about views). No name, email, address or visitor ID: those are
for the person lookup ([DATA-CONTRACT-PEOPLE.md](DATA-CONTRACT-PEOPLE.md)).
A row marked test (`conversions.test`, `skald conversions mark-test`) is left
out of every block below: stages, abandoned, breakdowns, pages before and
the timeline. Cancelled, removed and test rows are listed by the helper
(`<page>/people/conversions?kind=`), not here.
Statuses and cancellations are "as known now": a later change rewrites the
day the action was taken.

| field | type |
|---|---|
| `available` | bool; false: `reason` says why (no conversions file yet) and every block below is empty (`reason` is null when true) |
| `set_up` | `{"beacon","visitor_ids","leads_db","store": bool, "hooks": [tool names with a secret]}`: what is on, for the tab's empty states |
| `min_rate` | int, 10: no rate over fewer starts or browsers |
| `as_known` | the "as known" sentence the tab shows |
| `abandon_hours` | number, 24: how long a start may wait for its finish |
| `repeat_minutes` | int, 30: the script tag's started (and other) rows keep one per browser, action and stage in this many minutes (conversions.BEACON_REPEAT_SECONDS), so they can be fewer than Events' count of the same event |
| `stages`, `finished` | the stages in report order; the ones that count as completed (`completed`, `paid`) |
| `dims`, `visit_buckets`, `convert_buckets` | the breakdown names and bucket names below, in order |
| `since` | the first local date conversions are recorded for, or null: the earliest of the first conversion kept, the first row taken away (`removed`), and, once the lead DB has been read into the store, the lead DB's first lead of any status (spam and duplicates make no row, yet their day was read: a day from `since` on with no lead counted is 0). audit_conversions_figures.check_since finds the same day by its own SQL; when it disagrees every day is withheld |
| `likely_ai` | `{"on","window_minutes","method"}`, the note for the per-day `likely_ai` below ([DATA-CONTRACT-AI-LIKELY.md](DATA-CONTRACT-AI-LIKELY.md)); absent when `available` is false |
| `days[]` | 180 entries ending today (local), oldest first: `{"day","state"}`; `state` is `ok`, `withheld` (+ `why`) or `before` (before `since`: not recorded, never zero). When `ok`: `stages` `{action: {stage: n}}` (every row); `abandoned` `{action: n}` (starts with a visitor ID, the window closed, not finished by the same browser and action); `by` `{dim: {action: {label: n}}}` for finished rows, dims `source_type` (last touch), `first_source`, `campaign`, `landing`, `country`, `device`, `tool`, `"Unknown"` for a value not recorded; `visits_before` and `time_to_convert` `{action: {bucket: n}}` for finished rows (`unknown`, and `clock_error` when the first touch is after the conversion); `assisted` `{action: {source: n}}` (each finished conversion with a visitor ID counted once per earlier journey source that is not its last touch) or null without journeys; `likely_ai` `{action: {label: n}}` for finished rows: the first touch likely sent by an AI assistant, an estimate ([DATA-CONTRACT-AI-LIKELY.md](DATA-CONTRACT-AI-LIKELY.md)) |
| `period` | `{"first","last"}`: the last 30 days (today included) of the two blocks below |
| `pages_before` | null without journeys (visitor IDs off), `{"state": "withheld","why"}`, or `{"converting","other","pages": [[path, converting, other]]}`: browsers with a finished conversion in the period and a journey up to it, and the browsers seen in the period that did not convert; per page, how many of each saw it (the converting ones before converting). Top 50 by converting, then other, then path; exact |
| `timeline[]` | the latest 50 finished conversions of the period, one per browser (or per lead without one), newest first, withheld days left out: `{"at","action","stage","tool","source","first_source","campaign","landing","country","device","visits_before","first_touch","browser": bool,"visits": [{"day","source","paths": [up to 15]}] (last 10 days with page views up to the conversion; [] without a browser),"steps": [{"at","action","stage","tool"}] (up to 20)}`. Times are local ISO. A listing, not a figure |
| `lead_actions`, `demo_actions` | (2.5.0) the actions that are a lead once finished (`contact`, `signup`, `waitlist`, `trial`, `demo`: a form sent or a demo booked) and the ones also shown as demos booked (`demo`); name lists from `conversions/__init__.py`, never figures |
| `today` | (2.5.0) null without a conversions file, `{"day","state": "withheld","why"}`, or `{"day","state": "ok","total","tests","rows"}`: today's (local) rows of the lead actions, every stage, newest first, at most 100: `{"at" (local ISO),"action","stage","tool","source","first_source","campaign","landing","country","device","test": bool}`. `total` counts all of today's such rows, `tests` the ones marked test (listed, marked, never counted: today's `days[]` entry leaves them out). A listing for the Live tab, not a figure; withheld when today's day is withheld or the second count disagrees |
| `withheld` | `{"days/<day>", "pages_before" or "today": why}` |

A day's `by` tables each add up, per action, to its finished stages; its
`visits_before` and `time_to_convert` too. A `withheld` day shows no figures.

**Second count.** `audit_conversions.check_file` runs on every build: the
stages per day against the hook spool, the beacon spool (whole days from
the audit's own `conversions-audit.json`) and the lead database (its own
SQL), and every other figure of every day and `pages_before` against
`audit_conversions_figures.py`, which counts them again by SQL GROUP BY over
the file opened read-only. Both roads leave test rows out by their own code:
the spool, beacon and lead recounts skip the (tool, reference) pairs marked
test (`audit_conversions.test_keys`), the SQL recount reads `c.test = 0`.
A day either road disagrees on is withheld, and
so is `pages_before`; a recount that cannot run withholds them all.

**Leads everywhere (2.5.0).** Overview (the Leads and Demos booked tiles, a
day's leads as marks on the main chart; since 2.7.0 Overview > Summary,
with today's in Today · Live), Sources, Pages (landing pages), Locations
(Places & devices since 2.7.0) and Compare (the Compare with… mode since
2.7.0) sum these `days` in the browser: the `ok` days
only, a lead being a finished row of `lead_actions` (`by.source_type`, last
touch, for sources; `by.landing`; `by.country`). A rate (leads per visitor)
puts them over the visitors of the same days only (days whole in the log
and `ok` here), and only over at least `min_rate` (10) visitors. A change
against another period needs both periods whole in the log and every day of
both `ok` here. On a page group (a view) no lead figure is shown: conversions
do not know about views. These sums are of figures the second count already
matched day by day; nothing new is stored for them.

`today` has its own second count: `audit_conversions_leads.check_today`
counts today's rows of the lead actions by SQL GROUP BY (action, stage,
test) over the file opened read-only, and compares the total, the test
count and (when every row is listed) the rows by action, stage and test
mark. A difference withholds the listing (`withheld["today"]`).

`today.by_now` (2.13, `conversions_leads.by_now`): the Leads tile's "vs
yesterday at this hour" in Live mode. `{"day": yesterday, "until": yesterday at
the file's own time of day (local ISO), "state": "ok" | "withheld" |
"not_recorded", "leads": n or null, "hours": [24] or null, "today_hours": [24] or
null}`: finished rows (completed, paid) of the lead actions, `test = 0`, from
yesterday's midnight to `until`, by local hour; `today_hours` today's the same way
(they add up to today's `days[]` leads). Yesterday withheld or before `since`
carries no figure. `check_by_now` counts the same again with one SQL COUNT per
local hour between its UTC bounds; a difference withholds the listing as above.

**Lead findings in insights.json (2.5.0).** `conversions_leads.insights` adds
findings with `metric` `"leads"`, by insights.py's rules (whole periods only,
`min_after` 5, `min_change` 20%, the same confidence): all leads (`subject`
`{"kind": "site", "name": "leads"}`), and per source (last touch), landing
page and country, week on week and 30 days on 30, `working`, `dropped` and,
for a source, `gone`; and the source and the landing page that sent the most
leads in the last 30 whole days (`"top": true`, `"of"`: all the leads of
those days), when one leads alone with at least `min_after`. A period counts
only when every day of it is `ok` in conversions.json. Only the whole site's
page carries them. Second count: `audit_conversions_leads.check_insights`
recounts each finding's `after` and `before` (and, for a top finding, the
leader, its count and `of`) by its own SQL over the file; a finding it
disagrees with is left out and named in insights.json's `leads_withheld`.

**Times without an offset (2.4.0).** A `lead` or `json` hook's `at` (and
`first_touch_at`, a touch's `at`) given without an offset is read in the
site's time zone, not UTC; the delivery log says so. The spool line then
carries `"zone"`, and the second count reads that line's times in it (a line
without `zone` was kept as UTC, and is read so). An event a Calendly or
Cal.com event-type filter leaves out is never spooled or stored, so neither
road counts it.

**Shares at low volume.** The web app shows a share (`time_to_convert`,
`visits_before`, and every other share of a small base) only over at least
`min_rate` (10); below it, the counts alone.

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
