# People: visits kept with their address, and the person lookup (2.4.0)

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply. Code: `skald/people/`
(`policy.py`, `visits.py`, `lookup.py`, `api.py`), the second count
`skald/audit_people.py`.

These are not data files: nothing here is written to the dashboard folder,
and nothing here is a figure. They are tables in `conversions.sqlite` (0640,
beside the history) and helper answers behind sign-in.

## What is kept, and when

| key | default | meaning |
|---|---|---|
| `privacy.keep_ips` | `full` on a new install; `off` on one upgraded from before 2.4.0 | keep each visit with its address and user agent: `full`, `short` (the address shortened, below) or `off`. `true` reads as `full` and `false` as `off` (configs, settings rows and answers from before 2.15.0) |
| `privacy.keep_days` | 395 | how long a kept visit stays (1 to 3650) |
| `conversions.identity` | `full` on a new install; `anonymous` on one upgraded from before 2.4.0 | keep a lead's name and email with its conversions |

"Upgraded" is read from the history file: history schema 13 adds no table,
but an upgrade from 12 or older writes the meta row `privacy_legacy`; a file
still at 12 or older counts the same. No history file is a new install.

### The shortened address (2.15.0, `privacy.keep_ips: short`)

`people/policy.shorten`, with the standard library's `ipaddress`:

- IPv4: the last octet is zeroed. `203.0.113.57` is kept as `203.0.113.0`.
- IPv6: the first 48 bits are kept, the rest zeroed. `2001:db8:85a3:8d3::` is kept as
  `2001:db8:85a3::`.
- An IPv4-mapped IPv6 address (`::ffff:203.0.113.57`) is IPv4: `203.0.113.0`.
- A value that is not an IP address is kept as it is (`(removed)`).

Only what is kept about a person is shortened: the kept visits' `ip`, and the address the
first touch looks a visit up by (`firsttouch.py`). The country and the city are looked up
from the full address first. Everything that reads the raw log is unchanged: bot sorting,
internal traffic, the totals, the private 6-hour Requests feed. Conversions and leads keep no
address in Skald at all (a hook's address gives the country, then is dropped).

Switching: full to short shortens every row the site already keeps at the next daily run
(`visits.prune_kept`, `shorten_kept`); short to full keeps the old rows shortened, and only
new rows are full; off deletes them at the next daily run, as before.

## Tables (conversions.sqlite schema 6)

`visits`: one row per reader's visit (a visit that read a page, by the 2.3.0
visit rule: the same key, no gap over `report.session_gap_minutes`, no new
outside source), so a day's rows are its readers.

| column | type | meaning |
|---|---|---|
| `site`, `day`, `seq` | text, text, int | the site, the local day, the visit's place in the day (oldest first); unique together |
| `ip` | text | the address (shortened with `keep_ips: short`); `(removed)` for an address on the forgotten list (asked about the full address) |
| `user_agent` | text or NULL | cut to 400; NULL when removed |
| `start`, `end` | text | UTC, `YYYY-MM-DDTHH:MM:SSZ`: the visit's first and last request |
| `source`, `via`, `campaign`, `landing`, `exit`, `country`, `device`, `browser`, `os` | text or NULL | the journey's labels (NULL: not recorded) |
| `city` | text or NULL | schema 5 (2.12.0): `"City, Region, CC"` from the city file `logs.city_db`; NULL without the file or when it had no city. Derived from the address, so kept only where the address is |
| `referrer` | text or NULL | the first page's referrer, cut to 300; NULL when removed |
| `pages` | int | pages loaded |
| `seconds` | int or NULL | first to last request |
| `trail` | JSON | `[[path, "page" or "app", seconds since start], ...]`, at most 50 |
| `posts` | JSON | UTC times of the visit's POST requests (a form sent), at most 20 |

`visit_days`: `site`, `day`, `state` (`whole`: written by the daily run;
`today`: written by the last live run, replaced each run), `visits`, `pages`,
`written_at`. A day without a row was not kept (keep_ips off, before 2.4.0,
or past keep_days): never zero.

`removed`: a conversion row a lead-database sync took away, kept whole:
`site`, `removed_at`, `why` (in words), `conversion_id`, `tool`,
`external_ref`, `vid`, `action`, `stage`, `at`, `row` (JSON of the full row,
with the identity's email and name when it had one). Pruned with
`conversions.retention_days`.

`conversions.test`: 0 counted; 1 for a row marked test (`skald conversions
mark-test`, or the site's `POST /traffic-hooks/<site>/leads/test`), which
marks every row of the same tool and reference, and a later delivery of it;
2 (2.19) for a row whose own lead body said `test: true`, that row only. Read
it as `test <> 0`. A test row is never counted: not in `conversions.json`
(stages, breakdowns, abandoned, pages before, timeline), not by
`store.day_counts`.

`conversions.label` (schema 7, 2.18): the lead hook's optional token
(`^[a-z0-9][a-z0-9_-]{0,39}$`), NULL when none was sent or it was not one.
Each row its own: a later stage keeps the label it was sent with, never an
earlier stage's. Every conversion row in the answers below carries it, and a
removed row's `row` JSON too; the lists show it as a tag.

Written by the daily run (whole days, `cli.collect_day`) and every live run
(today, `live.build`), only while `keep_ips` is on and the day is inside
`keep_days`. Pruned at each daily run: rows older than the site's
`keep_days`, every row of a site that turned `keep_ips` off, and every full
address of a site that turned it to `short` is shortened. `skald forget --ip`
deletes an address's rows; on a site that shortens, also the rows of its
shortened form, which may hold other people's visits too.

## Helper answers (behind sign-in)

| route | who | answer |
|---|---|---|
| `GET <page>/people?q=Q` | owners and admins (403 otherwise) | the person, below |
| `GET <page>/people/left-out` | every member | `{"ok","private","leads":[...],"conversions":[...]}`: the lead database's spam, duplicate and test leads (status `test`, or a flag mentioning test), each with `why`; conversions marked test |
| `GET <page>/people/conversions?kind=cancelled\|removed\|test` | every member | `{"ok","kind","private","rows":[...]}`, each with `journey` (the visitor ID's page views) |
| `GET /traffic-api/v1/<site>/people?q=Q` | an API token with `read_private` | the person, below |

In the two lists `email`, `name` and `vid` are left out unless the caller is
an owner or admin (`private: true`) and the site keeps identities.

The person (`lookup.person`): `query` `{kind: ip|email|vid|lead, value}`,
plus `short` (the shortened form) when the site keeps addresses shortened and
the search is an address, `kept` (`keep_ips` true/false, `ip_mode`
full/short/off, `identity`, `keep_days`, `legacy`), `visits` (rows above, newest
first; with `query.short`, the rows of the shortened form: one shortened
address can be several people, and the page and MCP say so), `requests`
(the address's rows of the private 6-hour feed, by the full address),
`leads` (lead database rows: `id`, `created_at`, `type`, `status`, `page`,
`first_source`, `last_source`, `landing`, `test`, `left_out`, `vid`, and
`email` / `name` when the site keeps them), `conversions` (every row, test
and cancelled ones too), `removed`, `journeys` (the visitor IDs' page views),
`candidates` (for each lead, the kept visits that sent a POST from 2 minutes
before it to 30 seconds after: matched by time, never certain), `withheld`
(`{day: "withheld"}` for days of those visits whose figures did not
reconcile) and `keys` (the linked `ips`, `emails`, `vids`, `leads`). 400 for
a value that is none of the four kinds. Each search writes one audit row
(`people.search`; basic mode: a line in `privacy.log`) with the kind and a
SHA-256 prefix, never the value.

## Second count

`audit_people.Recount` (in `audit_more.RECOUNTS`) rides on the audit's pass
over the raw log: for each people visit by the audit's own split, it counts
readers and page views per address. For a whole day it opens
`conversions.sqlite` read-only and checks, by its own SQL: the visits kept
equal the readers, their pages equal the page views, the day's own counts
equal its rows, every address kept has exactly the recount's visits and
pages, and the `(removed)` rows equal the visits of addresses not kept by
name. A mismatch withholds the day like any audit finding. No address is
written into a problem. Today's rows (`state` `today`) are not compared.

On a site that keeps addresses shortened (`privacy.keep_ips` is the word
`short`, read from the config by the audit itself) it shortens each address
by its own code (`audit_people.short_address`: integer masks, sharing only
the rule above with `policy.shorten`) and checks: no kept address is in full;
each kept shortened address holds exactly the visits and pages of every
recount address that shortens to it (on a day with `(removed)` rows, no more
than that, the totals taking up the rest); the `(removed)` rows equal the rest.
A site back on full keeps its older days shortened: a day whose full check
fails, whose every kept address is already shortened and which passes the
shortened check passes.

## First touch (2.12.0)

Where each reader's visit's visitor first came from. Code: `skald/firsttouch.py`
(written by the daily run and every live run, right after the visits are kept), the
second count `skald/audit_firsttouch.py` (in `audit_more.RECOUNTS`).

### The links, in order

The first link that finds an earlier visit wins; none: `none` ("first visit we know of",
never a guess); no link could be tried for the visit: `off`.

| `by` | when | the visit's first touch |
|---|---|---|
| `vid` | `beacon.visitor_ids` on, and exactly one visitor ID has a page view of the visit's landing page from 2 seconds before its first request to 30 seconds after (and before the window's end), and that ID matches no other visit of the day | the ID's earliest page view more than 2 seconds before the visit (conversions.sqlite `journeys`): time, page, source type, referring host (`via`, schema 6; a row from before is `(not kept)`) |
| `address` | `privacy.keep_ips` on | the earliest kept visit (`visits`) of the same address with the same browser and system, started before this one, within `privacy.keep_days`; the day's own visits count (they are kept first). A forgotten address is kept as `(removed)`: it never links |
| `hash` | the visitor key is set | the earliest earlier day within `visitors.repeat_days` whose `visitor_days` has the visit's 30-day code as a reader (its day and source type; referrer `(not kept)`), else an earlier visit the same day with the same code (its labels) |

A site that keeps no addresses gets only `vid` and `hash`. Views get no first touch: their
visits are cut by path, so the site's kept visits would read as earlier visits of the same visit.

### On each journey (history `journeys`, the live snapshot, app.json)

`first_touch`: `{"by","day" (local),"start" (local, to the minute; null by hash),"source"
(source type),"via" (the site or assistant, or ""),"referrer" (referrer label: host,
`(none)`, `(this site)`, `(not kept)`),"campaign","landing"}`, or `{"by":"none"}` /
`{"by":"off"}`. Absent on a visit counted before 2.12.0 or when no link is on: not recorded.
`seq`: the visit's place in the day (the site's own journeys only) - the kept visit's `seq`,
which the visitor timeline asks by. Labels only: no address, no visitor ID, no hash.
Real time's `newest` rows carry both.

### Day kind `first_touch` (day_extras; app.json `days[].first_touch`, `live.figures.first_touch`)

| key | meaning |
|---|---|
| `roads` | `{"vid": bool, "address": keep_days or 0, "hash": window or 0}`; app.json: true/false |
| `until` | the window's end (UTC): no page view after it is read (not in app.json) |
| `visits` | the day's readers' visits |
| `by` | `{vid, address, hash, none, off}`: how each was linked; sums to `visits` |
| `direct` | the Direct visits: `visits`, `known` + `none` + `off` (= `visits`), `first` `{source type: n}` and `referrer` `{referrer label: n}` (each sums to `known`) |
| `returning` | every visit with an earlier one known: `visits`, `first`, `referrer` (each sums to `visits`) |
| `address_form` | `"short"` when the address link looked visits up by the shortened address (`privacy.keep_ips: short`, 2.15.0); absent when full |

No blob: no link was on (or a view), not zero. Traffic > Sources shows it as "Where
returning visitors first came from"; a day without it is left out and said.

### Second count

`audit_firsttouch.Recount` gets each people visit as the audit split it, labels it with the
audit's own labels, and links it again with its own SQL on conversions.sqlite (`journeys`,
`visits`) and history (`visitor_days`), opened read-only, and its own keyed hash. Which links
were on (`roads`) is read from the blob (a setting, not a figure); the window's end is its own.
With `address_form: "short"` it shortens each visit's address by its own code
(`audit_people.short_address`) before it looks it up.
Every count above is compared; a mismatch withholds the day.

A day audited after inputs its links could have read were pruned (an ID's page views after
`journeys.vid_days`, 30, unless the ID converted; kept visits after `privacy.keep_days`; the
30-day codes after `visitors.repeat_days`) says its first touch is "not checkable (inputs
expired)", as the visitor hashes and returning readers do: never a mismatch, never withheld.
Only its visit count, which needs no kept input, is still compared. Pruned is read from the
files: a stored day the count could have read (its blob says the link was on and it had visits)
whose page views (of IDs that never converted, before the earliest one kept), kept visits or
codes are gone. Kept visits and codes count only when the day linked a visit by them.

## The visitor timeline (2.12.0)

`GET <page>/people/visitor?day=D&seq=S` (owners and admins; 403 otherwise; 400 for a bad day
or seq; each answer writes an audit row `people.visitor` with the visit's day and seq, never
an address): `people/timeline.py`, from the kept visit `(site, D, S)`:

`{"ok","found","kept","why" (when not found: addresses not kept, not kept yet, forgotten),
"visits": [...],"leads": [...],"conversions": [...],"withheld","vid_matched","linked_by"}`.
`linked_by`: `address`, or `short_address` on a site that keeps addresses shortened: a
weaker link, which the drawer says.
`visits`, newest first: every kept visit of the same address with the same browser and
system within `keep_days` (`kind` `kept`: the visit row's labels, `trail`, `posts`, `day`,
`seq`; `linked` `this` or `address`), and, when a visitor ID matched one of them by the rule
above, the ID's page views no kept visit covers, grouped 30 minutes apart (`kind` `script`,
"seen by the script"). The oldest has `first: true`. `leads`: made from 30 seconds before to 2
minutes after a form one of the visits sent (`lead`, `visit_start`, `created_at`, `type`,
`status`, `left_out`; matched by time, never certain). `conversions`: the matched IDs'
(test rows left out). No address, no visitor ID, no email in the answer. The web app's
visitor drawer (`webapp/js/tabs/visitor.js`) draws it; the demo writes one file per visit
it can answer.

## Retention cohorts

Of the visitors first seen in a week (or on a day), how many came back in each later week
(day). `retention.py` counts them after each collect (`collect`, `backfill`, run-daily),
from what is kept; `audit_retention.py` recounts them; `retention_page.py` writes
`retention.json` and answers the cell lists. The whole site only, never a view.

### Who is the same visitor

One identity per site: the first of the first-touch links (above) that can follow a visitor
for weeks.

| identity | when | same visitor | horizon `H` |
|---|---|---|---|
| `address` | `privacy.keep_ips` on | the kept visits (`visits`, whole days only): same address, same browser and system (NULL equals only NULL) | `privacy.keep_days` (395) |
| `hash` | else, with the visitor key | the 30-day code (`visitor_days`, kind `reader`): a day and a source type only | `visitors.repeat_days` (30) |
| none | neither | nothing is counted; `retention.json` says why | - |

The beacon's visitor ID is not used: it is seen only on visits that ran the page script and
its page views are kept `journeys.vid_days` (30), so the same visitor would count as one or
two depending on the script. A forgotten address (`(removed)`) is in no cohort; its visits
are counted in `removed`.

### The rule

- **Days and weeks** are the site's local days (the kept visit's `day`); a week starts on
  Monday. Only periods that are over are cohorts.
- **New** in a period: the visitor's earliest visit in it (by `start`, then `seq`) has no
  visit of the same visitor in the `lookback` days before it.
  `lookback = max(H - 63, ceil(H / 2))`: 332 for 395 days, 15 for the 30-day code.
- **Back** at `+k`: a member with a visit in the period `k` weeks (days) later. **Deep**: one
  of those visits read 2 or more pages (not recorded on the 30-day code).
- **Reach** `H - lookback - 1` days (62 for 395, 14 for 30): a cell whose period ends later
  than that after the cohort's first day is never counted while its inputs are all kept:
  "not recorded", never 0.
- **Counted while kept**: a cohort is counted (again each run, the same answer) while the
  store holds every day it reads, from `lookback` days before its first day to yesterday.
  While nothing has been pruned yet (the store began less than `H` days ago), a cohort whose
  lookback starts before the store began is counted with `since`: "new" means first seen
  since then. Once its inputs are pruned it stays as last counted ("inputs expired").
- **Splits** by the first visit's source type, country, device and landing page (the 30-day
  code: source type only); the 8 biggest values of each, the rest `(other)`.

### Day kinds `retention_week`, `retention_day` (day_extras, on the cohort's first day)

`{"version": 1, "grain", "start", "end", "by", "horizon", "lookback", "size", "cells":
{"k": [back, deep]}, "split": {dim: {value: {"size", "cells"}}}, "removed", "deep" (2, or
null on the 30-day code), "computed" (the last day it was counted to), "since", "kept_from",
"audit": {"on", "ok", "problems"}}`. `cells` holds only the offsets counted (1 to 8 weeks,
1 to 14 days). Totals and labels only: no address, no code. Re-collecting the cohort's first
day (`backfill --force`) clears the blob; the next run counts it again where its inputs are
still kept.

### retention.json

`{"identity": {"by", "horizon", "lookback", "reach"} | null, "why", "words", "deep",
"anchor", "begun", "kept_from", "offsets": {"week": 8, "day": 14}, "grains": {"week" | "day":
{"cohorts": [...]}}}`: the latest 12 weeks and 30 days. Each cohort: the blob's fields,
`checkable` (false once its inputs are pruned), `state` (`ok`; `held`: a day of the cohort
period is not verified; `withheld`: its recount did not match; `nr`: never counted) and
`status` per offset: `ok`, `pending` (not over), `held` (a day of that period is not
verified), `nr` (later than the reach), `nr-pruned` (its inputs were pruned before it was
counted). A view's page says `"why": "view"`.

### The visitors behind a cell

`GET <page>/people/cohort?grain=week|day&start=D&k=K[&split=S&value=V][&deep=1]` (owners
and admins; 403 otherwise; 400 for a bad grain, start, offset or split; each answer writes an
audit row `people.cohort` with the cell, never an address). On the address identity only:
each member's first visit in the cell's period (`k` 0: its first visit), newest first, at
most 500, each with `day` and `seq` so the visitor drawer opens on it. `stored` is the
blob's figure, `listed` the kept visits' now; `differs` says so when an address was
forgotten since. Inputs pruned: `found: false` and why.

### Second count

`audit_retention.py` (in `audit_more.DAILY`, run-daily's recounts step once a cohort is
stored) reads every stored cohort and, where its inputs are still kept, counts it again with
its own SQL on the same rows, read-only: the period's end, Monday starts, the lookback
against the rule, the new visitors, every cell (back and deep), every split value and
`(other)` against the rest. A cohort whose inputs are pruned is "not checkable (inputs
expired)": said and counted, never a problem. The verdict is written into each checked blob;
the page withholds a cohort whose recount did not match.
