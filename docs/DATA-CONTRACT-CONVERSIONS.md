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

**One lead counts once (2.26).** Of the finished rows (`completed`, `paid`)
of a lead action under one site, tool, `external_ref` and action, only the
first (earliest `at`, then the stage's name) is counted; another (a `paid`
sent after the `completed`) is left out of every block below, as a test row
is, and stays listed among the lead's steps (`store.repeat_finishes`).
Before 2.26 such a ref was two leads. A day stored before 2.26 changes when
it is next built (conversions.json is rebuilt from the store on every run);
the daily history's stored figures (mails, client reports already sent) do
not. Other actions (`paid`, `deal`...) count every row, as before.

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
| `days[]` | 180 entries ending today (local), oldest first: `{"day","state"}`; `state` is `ok`, `withheld` (+ `why`) or `before` (before `since`: not recorded, never zero). When `ok`: `stages` `{action: {stage: n}}` (every row); `abandoned` `{action: n}` (starts with a visitor ID, the window closed, not finished by the same browser and action); `by` `{dim: {action: {label: n}}}` for finished rows, dims `source_type` (last touch), `first_source`, `campaign`, `landing`, `country`, `device`, `tool`, `"Unknown"` for a value not recorded; `visits_before` and `time_to_convert` `{action: {bucket: n}}` for finished rows (`unknown`, and `clock_error` when the first touch is after the conversion); `assisted` `{action: {source: n}}` (each finished conversion with a visitor ID counted once per earlier journey source that is not its last touch) or null without journeys; `likely_ai` `{action: {label: n}}` for finished rows: the first touch likely sent by an AI assistant, an estimate ([DATA-CONTRACT-AI-LIKELY.md](DATA-CONTRACT-AI-LIKELY.md)); (2.18) `labels` `{action: {lead label: {stage: n}}}`, the rows that carry a lead's label (the lead hook's optional `label`, `conversions.label`), every stage, and `labels_abandoned` `{action: {lead label: n}}`, the abandoned starts among them. A row without a label is in neither, so a label's counts are a part of `stages` and `abandoned`, never the whole; `{}` when no row has one |
| `period` | `{"first","last"}`: the last 30 days (today included) of the two blocks below |
| `pages_before` | null without journeys (visitor IDs off), `{"state": "withheld","why"}`, or `{"converting","other","pages": [[path, converting, other]]}`: browsers with a finished conversion in the period and a journey up to it, and the browsers seen in the period that did not convert; per page, how many of each saw it (the converting ones before converting). Top 50 by converting, then other, then path; exact |
| `timeline[]` | the latest 50 finished conversions of the period, one per browser (or per lead without one), newest first, withheld days left out: `{"at","action","stage","tool","source","first_source","campaign","landing","country","device","visits_before","first_touch","browser": bool,"visits": [{"day","source","paths": [up to 15]}] (last 10 days with page views up to the conversion; [] without a browser),"steps": [{"at","action","stage","tool","label"}] (up to 20),"label"}`; `label` (2.18) is the row's lead label or null. Times are local ISO. A listing, not a figure |
| `lead_actions`, `demo_actions` | (2.5.0) the actions that are a lead once finished (`contact`, `signup`, `waitlist`, `trial`, `demo`: a form sent or a demo booked) and the ones also shown as demos booked (`demo`); name lists from `conversions/__init__.py`, never figures |
| `today` | (2.5.0) null without a conversions file, `{"day","state": "withheld","why"}`, or `{"day","state": "ok","total","tests","rows"}`: today's (local) rows of the lead actions, every stage, newest first, at most 100: `{"id" (the row, 2.25),"ref" (its `external_ref`, the sender's own ID, 2.25; null for the page script's, which holds the visitor ID),"at" (local ISO),"action","stage","tool","source","first_source","campaign","landing","country","device","test": bool,"repeat": bool (2.26: the lead finished again, a `paid` after its `completed`: listed, not a lead)}`. `total` counts all of today's such rows, `tests` the ones marked test (listed, marked, never counted: today's `days[]` entry leaves them out). A listing for the Live tab, not a figure; withheld when today's day is withheld or the second count disagrees |
| `currencies` | (2.32) `{currency: decimals}` for every currency the site's counted sales are in (ISO 4217; minor units = value × 10^decimals; `{}` when the only money is refunds without a sale), or null when the site has no counted value at all: then no day carries `revenue` |
| `ltv` | (2.32) null (no money), `{"state": "withheld","why"}`, or `{"window": "every row kept","currencies": {currency: {"customers","net_minor","renewals","repeat_customers","first_day","by_first_source": {source: {"customers","net_minor","renewals","repeat_customers"}}}}}`: see "Revenue" below |
| `refunds_without_sale` | (2.32) null (no money), `{"state": "withheld","why"}`, or `{"count": n, "currencies": {currency: total minor units}}`: every refund row kept (every row kept, test rows left out) that no figure counts: its sale is not counted (Stripe sends `charge.refunded` for every charge of the account; the sale may never have reached Skald, been a test or been taken away), its value could not be read, or it was sent in another currency than its sale (kept without a value). `currencies` sums those kept with a value over 0. Stored and shown here, never subtracted from any figure; a refund that waits for its sale leaves this count when the sale comes |
| `revenue_since` | (2.32) null (no value kept), `{"state": "withheld","why"}`, or the local day (`YYYY-MM-DD`) of the site's first counted row (not test) with a value and a currency: a sale or a refund. Days before it carry no `revenue` (not recorded, never zero) |
| `withheld` | `{"days/<day>", "pages_before", "ltv", "refunds_without_sale", "revenue_since" or "today": why}` |

A day's `by` tables each add up, per action, to its finished stages; its
`visits_before` and `time_to_convert` too. A `withheld` day shows no figures.

**Revenue (2.32, `conversions_revenue.py`).** When `currencies` is not null,
every `ok` day from `revenue_since` on carries `revenue`: `{}` (no sale and no
refund that day: a known none), else per currency, never converted and never
summed across. An `ok` day before `revenue_since` has no `revenue` at all: a
site that sent sales without amounts before then did not sell nothing.

    "revenue": {"USD": {"gross_minor": 6999, "refunded_minor": 999, "net_minor": 6000,
                        "sales": 2, "refunds": 1, "new_customers": 1, "renewals": 1,
                        "by": {"source": {name: {"net_minor", "sales"}}, "first_source": {...},
                               "campaign": {...}, "landing": {...}, "country": {...},
                               "device": {...}, "tool": {...}, "label": {...},
                               "tag": {key: {value: {"net_minor", "sales"}}}}}}

- Amounts are whole minor units of the currency (`currencies` gives the
  decimals). A value is what the sender gave (`value`, `currency` on the
  `lead` and `json` hooks; Stripe's `amount_total`, `amount_paid`,
  `amount_refunded`); a row without one is no money, never 0.
- **A sale** is a finished row (`completed` or `paid`) with a value, counted
  once per (tool, `external_ref`): its `paid` row when that carries a value,
  else its `completed` one. This is not the leads' rule (2.26): a `paid` after
  a `completed` for the same ref is one lead (the completed row) and one sale
  (the paid row).
- **A refund** is a `refunded` row with a value, one per sale, its amount the
  total refunded so far (a later, larger total raises it; Stripe's
  `amount_refunded` is cumulative; a refund sent without a value is the whole
  sale's value). It counts only when its sale counts, in the sale's currency;
  every other refund row (no counted sale, a value that could not be read,
  or another currency than the sale's) is in `refunds_without_sale`, never
  subtracted. A refund of 0, or a part of 0, is no refund. When the sale is
  known a refund is never more than it (cut to the sale's value) nor in
  another currency (kept without a value), each with a note to the sender. A
  refund that came before its sale (a refund sent first, or Stripe's events
  out of order) is moved onto the sale when the sale comes, and a whole one
  takes the sale's value then; a whole one sent after an unreadable one waits
  for the sale's value too. A refund cut or emptied when its sale comes later
  gets no note: its answer went out before the sale was known. **Each part counts on the day it arrived**:
  the first amount on its day, each larger total's difference on its own day
  (`refund_parts`, with each part's time), one refund each, under the sale's
  attribution (`net_minor` can be negative there, with `sales` 0), never on
  the sale's day. So `refunds` counts refunds that arrived, and a raise 40
  days later shows in that later day. `net_minor` = gross − refunded.
- **Attribution** (`source` = last touch, `first_source`, `campaign`,
  `landing`, `country`, `device`, `label`) is the (tool, ref)'s first finished
  row: where the visitor came from. `tool` is the row's. "Unknown" for a value
  not recorded; a sale without a label is "(no label)". `tag` holds the
  sale's tags (a refund: its sale's), only the tags sent.
- **Customers.** A customer is a `customer_ref` within one currency; a sale
  without one is its own customer. Of a customer's sales (every row kept, any
  day, by `at`, then id) the first is a new customer, every later one a
  renewal: `new_customers` + `renewals` = `sales`. A renewal whose first sale
  is past `conversions.retention_days` counts as new.
- **`ltv`** is over every row kept (`conversions.retention_days`; 400 days by
  default, or for good), not a period: per currency, the customers, their
  net (their sales less the refunds on those sales; a refund whose sale is not
  counted belongs to no customer), the renewals (sales after a customer's
  first), the repeat customers (more than one sale) and the first day of a
  sale; and the same by the first source of each customer's first sale (a
  renewal sent without a visitor ID is joined to it by `customer_ref`). An
  average or a repeat rate is the page's own division of two of these.
- Test rows and removed rows are never money.
- `value` text longer than 30 characters (`MAX_AMOUNT_TEXT`) is never parsed:
  the row is kept without a value, with a note. `customer_ref` is dropped with
  a note when it is shaped like an IP address or is a phone number (only
  digits and `+ ( ) . -`, with more than 6 digits).

Second count: `audit_revenue.py`, on every build (from
`audit_conversions.check_file`). (1) SQL over the file opened read-only:
the sales by NOT EXISTS, attribution by a correlated sub-select, renewals by
EXISTS of an earlier sale, tags by `json_each`, every figure and every cell
by GROUP BY over each refund part, `ltv` the same but from the refund rows'
own totals (the main count adds up their parts, so a part changed by hand
withholds `ltv` too), `refunds_without_sale` as the refund rows not counted,
and `revenue_since` by MIN over the rows with a value (each `ok` day must
carry `revenue` exactly from that day on). (2) The hook
spool replayed in the order it came: its own reading of `value`, `currency`,
`customer_ref` and Stripe's amounts (text arithmetic, no Decimal), its own
first-delivery-wins, refund rule (one per sale, the sale's currency, never
more than the sale, each rise a part with its time, an early refund moved
onto its sale), Stripe refund matching (including `invoice_payment.paid`
links) and each removal (the `removed` table) replayed at the time it
happened, between the lines received before and after it, on the row's ref
at that time: per day and currency the gross, refunded and net sums and the
counts of sales, refunds, new customers and renewals, `ltv`'s totals,
`refunds_without_sale` and the first day with a value. A day either
disagrees on is withheld (as every conversion figure), and `ltv`,
`refunds_without_sale` and `revenue_since` too. A sale written
into the table by hand, not through a hook, is in no spool: its day is
withheld.

**Second count.** `audit_conversions.check_file` runs on every build: the
stages per day against the hook spool, the beacon spool (whole days from
the audit's own `conversions-audit.json`) and the lead database (its own
SQL), and every other figure of every day and `pages_before` against
`audit_conversions_figures.py`, which counts them again by SQL GROUP BY over
the file opened read-only. Both roads leave test rows out by their own code:
the spool, beacon and lead recounts skip the (tool, reference) pairs marked
test (`audit_conversions.test_keys`), the SQL recount reads `c.test = 0`.
A lead's repeat finish (2.26) is left out by each road's own rule: the spool
recount keeps the first finished stage per tool, ref and action from its own
reading of the lines, the SQL recounts by NOT EXISTS of an earlier finished,
unmarked row (`audit_conversions_figures.once`). A row soft-removed
(`skald conversions remove`, kept in `removed`) leaves the spool recount too:
its lines received before it went are skipped (`audit_conversions.removed_keys`).
A lead's label (2.18) is recounted there by its own GROUP BY over the column
(`labels` by day, action, label and stage; `labels_abandoned` by the same
NOT EXISTS as `abandoned`, grouped by label too).
A day either road disagrees on is withheld, and
so is `pages_before`; a recount that cannot run withholds them all.

**Leads everywhere (2.5.0).** Overview (the Leads and Demos booked tiles, a
day's leads as marks on the main chart; since 2.7.0 Overview > Summary,
with today's on Today, live), Sources, Pages (landing pages), Locations
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

`today.same_time` (2.27, `conversions_leads.same_time`): Leads & sales > Leads counts 7, 30
and 90 days as today so far and the whole days before it, and compares them like for like
with the period before: its whole days (from `days[]`), then its last day to the same time of
day. `{"time": "HH:MM:SS" (the file's own local time), "days": [{"back": 7 | 30 | 90, "day":
today minus back, "until": that day at "time" (local ISO), "state": "ok" | "withheld" |
"not_recorded", "leads": n or null, "actions": {action: n} or null}]}`: finished rows
(completed, paid) of the lead actions, `test = 0`, a lead's repeat finish left out (2.26),
from the day's midnight to `until`. A day withheld or before `since` carries no figure, and
the page shows no change. `check_same_time` counts the same again by one SQL GROUP BY action
between its own UTC bounds (the day's local midnight, and that day at `time`), with the repeat
finish left out by its own NOT EXISTS (`audit_conversions_figures.once`); a difference
withholds the listing as above. The period's own days, today's included, are `days[]`,
recounted by `audit_conversions.py` on every build like every day.

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

**Refused deliveries held (2.45).** What: a hook delivery refused for its key,
`unsigned` (none of the tool's signature headers came) or `bad_signature` (one came
and did not match), is kept as it came: the raw body, only the headers that verify
it (the tool's signature headers, HubSpot's timestamp, the content type, the method
and the public address the tool called; never `Authorization`), when it came and
why it was refused. One file each, `hooks-held/<site>/<tool>/<ms>-<random>.json`
beside the history, 0600 in 0700 folders (`conversions/held.py`). Never a test of
Skald's own (`X-Skald-Test: 1`), never a `lead` or `json` sent with the plain key.
Why: so a key saved later still takes in the real events the tool sent meanwhile; the
tools do not send a refused event again (a site's Calendly lost eight bookings this
way while Skald's own Test passed). How long: 24 hours from when it came, at most 200
a hook (the oldest go first), each at most the receiver's 64 KiB; purged on every
write, on every key save and by run-daily (`conversions/jobs.py`). A site that keeps everything (internal and enterprise sites: `keep_everything.py`) has none purged by age or count: they wait until a saved key takes them in or a person's deletion request removes them; past 2,000 a hook no more are held, and no old one is deleted to make room (`held.keeps`, `KEEP_ALL_CAP`). It is held, not
counted: nothing here is a figure until a key verifies it. Never logged, never in
`skald backup` (which copies the databases only) or a site's archive, never shown:
pages say only how many wait. `skald forget --email/--vid/--lead` deletes the held
bodies holding that value; clearing or deleting a site's data deletes its folder.

When a key is saved (Settings > Leads & tools: paste, make, rotate),
`conversions/key_check.py` verifies each held delivery with it by the tool's own
adapter, its time window moved from "now" to when the delivery came (a signed time
within 5 minutes of it; the delivery within the last 24 hours). One that matches is
taken in by the receiver's normal road (spool, event-type filter, de-duplication by
external ref and stage, a lead's own `test`, the store) with that time as its
`received_at`; its spool line carries `"held": true`, its delivery row outcome
`accepted_held` (counted like `recorded` and `duplicate` wherever accepted deliveries
are), and it leaves the hold. Delivery outcomes 2.45 adds: `unsigned`, `accepted_held`;
older `bad_signature` rows read as before. Second count: `audit_hooks_held.py`
(INTEGRATIONS.md, "The second count").

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
