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
| `privacy.keep_ips` | `true` on a new install; `false` on one upgraded from before 2.4.0 | keep each visit with its address and user agent |
| `privacy.keep_days` | 395 | how long a kept visit stays (1 to 3650) |
| `conversions.identity` | `full` on a new install; `anonymous` on one upgraded from before 2.4.0 | keep a lead's name and email with its conversions |

"Upgraded" is read from the history file: history schema 13 adds no table,
but an upgrade from 12 or older writes the meta row `privacy_legacy`; a file
still at 12 or older counts the same. No history file is a new install.

## Tables (conversions.sqlite schema 4)

`visits`: one row per reader's visit (a visit that read a page, by the 2.3.0
visit rule: the same key, no gap over `report.session_gap_minutes`, no new
outside source), so a day's rows are its readers.

| column | type | meaning |
|---|---|---|
| `site`, `day`, `seq` | text, text, int | the site, the local day, the visit's place in the day (oldest first); unique together |
| `ip` | text | the address; `(removed)` for an address on the forgotten list |
| `user_agent` | text or NULL | cut to 400; NULL when removed |
| `start`, `end` | text | UTC, `YYYY-MM-DDTHH:MM:SSZ`: the visit's first and last request |
| `source`, `via`, `campaign`, `landing`, `exit`, `country`, `device`, `browser`, `os` | text or NULL | the journey's labels (NULL: not recorded) |
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

`conversions.test`: 1 for a row marked test (`skald conversions mark-test`),
which marks every row of the same tool and reference. A test row is never
counted: not in `conversions.json` (stages, breakdowns, abandoned, pages
before, timeline), not by `store.day_counts`.

Written by the daily run (whole days, `cli.collect_day`) and every live run
(today, `live.build`), only while `keep_ips` is on and the day is inside
`keep_days`. Pruned at each daily run: rows older than the site's
`keep_days`, and every row of a site that turned `keep_ips` off.
`skald forget --ip` deletes an address's rows.

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
`kept` (the three keys above and `legacy`), `visits` (rows above, newest
first), `requests` (the address's rows of the private 6-hour feed),
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
