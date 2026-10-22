# Leads from the site's server: labels, the reconcile GET and test marks

Part of [INTEGRATIONS.md](INTEGRATIONS.md) (kept apart to hold that file under 1000 lines);
the rules there apply. The end-user guide with copy-paste examples:
[help/leads-from-your-backend.md](help/leads-from-your-backend.md).

## A lead's label (2.18)

The lead body's optional `label` (INTEGRATIONS.md, "The lead body") is kept in
`conversions.label` (schema 7), spooled with the body, and shown as a small tag in the lists of
conversions (Leads & sales > Leads, Calendar bookings' Show left out lists, the person drawer).
conversions.json counts it per day (`labels`, `labels_abandoned`,
[DATA-CONTRACT-CONVERSIONS.md](DATA-CONTRACT-CONVERSIONS.md)), recounted by
`audit_conversions_figures.py`; Leads & sales > Leads, and Summary and Sources counting from the
tools, have a **Label** option (`llabel` in the address) that narrows Every action to it, and the MCP `conversions` tool takes `label`.

## Check that Skald has every lead: `GET /traffic-hooks/<site>/leads`

2.18. A site's server asks for the leads its own `lead` hook delivered, compares them with its
own and sends the missing ones again (`conversions/reconcile.py`). Read only. Signed with the
`lead` hook's secret over the method and the request target, the path and the query exactly
as sent (no `?` without a query), with the same 5-minute window and constant-time compare as
the POST:

```
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.GET /traffic-hooks/<site>/leads?<query>")>
```

| parameter | | |
| --- | --- | --- |
| `since` | | `received_at` at or after (ISO with an offset, `Z` simplest, or Unix seconds; without an offset, UTC) |
| `at_since`, `at_until` | | `at` in `[at_since, at_until)` |
| `limit` | default 200 | 1 to 500 |
| `cursor` | | the last answer's `next_cursor` |

Each at most once; another name is refused (400). `since` filters on when Skald got the lead,
not on its `at`: a backfilled lead carries an old `at`, and a reconcile asks "what arrived since
my last check". The answer:

```
{"ok": true, "site": "example.com", "since": "2026-10-19T00:00:00Z", "at_since": null,
 "at_until": null, "limit": 200,
 "rows": [{"external_ref": "L-1001", "action": "contact", "stage": "completed",
           "at": "2026-10-19T14:30:00Z", "label": "sales", "test": false,
           "received_at": "2026-10-19T14:30:02Z"}],
 "next_cursor": null}
```

Only rows of tool `lead` for that site (not `json`, a booking tool or the lead database);
never an email, a name, an address, a user agent, a visitor ID or a source. Ordered by
`received_at`, then the row's id; the cursor is that pair of the page's last row, opaque
(base64url), so a lead arriving later lands after it and paging neither skips nor repeats one.
`next_cursor` is `null` on the last page. Rows marked test are in it with `"test": true`. A row
pruned (`at` older than `conversions.retention_days`, 400) or deleted by `forget` is not.

Answers: 401 no or a wrong signature, or `t` off by more than 5 minutes (it spends the sender's
pre-auth bucket, as the POST does); 404 an unknown site or no `lead` secret, the same body; 429
past `hooks.leads_per_minute` (60, burst `hooks.leads_burst` 20) per site, a bucket apart from
the POST's, spent only by verified requests; 400 a parameter. It writes no delivery row: one
line on the helper's log, `hooks: GET leads <site> <outcome> rows=<n> params=<names>`, never a
value. Every other GET to `/traffic-hooks/` is 405, POST unchanged. nginx must let GET through
to `/traffic-hooks/` (INTEGRATIONS.md, "nginx").

A resend is safe: the hook keeps one row per site, tool, `external_ref` and stage
(`store.record_conversion`), so a lead Skald has is answered `"duplicates": 1` and changes
nothing (its label neither: the first delivery wins). Never resend a lead deleted on request:
the `lead` hook keeps no hash of bodies, so it would come back.

Tested in `tests/test_lead_label_reconcile.py` and `tests/js/pipeline-label.mjs`.

## Test leads the site marks itself (2.19)

A site's own team accounts and QA runs make real-looking leads. Two ways for the site's server
to keep them out of the figures without the server admin: the lead body's `test`, and a
signed call that marks (or unmarks) leads already sent. Both make the same mark as
`skald conversions mark-test`: the row is kept, listed (Leads & sales > Leads with Show left
out, Calendar bookings' Show left out, the person drawer, the GET above with `"test": true`), and never counted.

### `test` in the lead body

`"test": true` (a JSON boolean) keeps that delivery's row with `conversions.test` =
`store.TEST_SENT` (2). `false`, `null` or absent: a real lead, as before. Any other value
(`"true"`, `1`) is ignored: the lead is kept as a real one, the answer carries
`"notes": ["test was not true or false: ignored, kept as a real lead"]` and the delivery log
says so. The `json` hook reads it the same way (it reads the lead body); the spool keeps it.

Each delivery says it for itself: an earlier stage sent with `test: true` makes no later stage
of the same `external_ref` test, so the sender sends `test: true` on every stage of a test
lead. A resend of a ref and stage Skald has is a no-op (`"duplicates": 1`), `test` included:
a resend never flips a stored row; change it with the call below.

### `POST /traffic-hooks/<site>/leads/test`

`conversions/marks.py`, answered by `hooks.Receiver.mark`. Signed exactly like the lead POST:
the `lead` hook's secret, HMAC-SHA256 over `"<t>.<raw body>"`, the same 5-minute window and
constant-time compare.

```
POST /traffic-hooks/example.com/leads/test
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>

{"refs": ["L-1001", "L-1002"], "test": true}
```

| key | | |
| --- | --- | --- |
| `refs` | required | 1 to 100 external refs, each read as the body's `external_ref` (text, trimmed, at most 120 characters; a number is read as its text). A ref given twice counts once |
| `test` | default `true` | a JSON boolean; `false` takes the mark off |

Any other key is refused (400), so a misspelt `test` never marks by default. The call affects
only that site's rows of tool `lead`, every stage of each ref; not `json`, a booking tool or
the lead database. Marked rows are `store.TEST_MARKED` (1), as the CLI's: a later stage the
site sends for a marked ref is test too (`store.record_conversion`), whatever its own `test`
says; unmarked, the next stage counts again. A row sent as test (2) that is marked becomes 1
and counts under `already`. The answer:

```
{"ok": true, "test": true, "marked": 3, "already": 0, "not_found": ["L-1002"]}
```

`marked`: rows whose counting changed; `already`: rows that were so already; `unknown`: refs
with no `lead` row on the site (never sent, pruned or forgotten).

Answers: 400 a bad body (not JSON, not an object, no refs, over 100, an empty ref, `test` not a
boolean, another key), the answer says which; 401 a missing or wrong signature, or `t` off by
more than 5 minutes (it spends the sender's pre-auth bucket); 404 an unknown site or no `lead`
secret, the same body; 405 another method; 411/413 as the POST; 429 past
`hooks.leads_per_minute` (60, burst `hooks.leads_burst` 20) per site, a bucket of its own,
apart from the GET's and the POST's, spent only by verified calls; 500 nothing changed, ask
again.

Each answered call writes one delivery row (tool `lead`, outcome `marked_test` or
`unmarked_test`, error column `"<n> ref(s): <c> row(s) changed, <a> already, <u> unknown"`,
never a ref: `forget` could not find it there) in the same transaction as the marks, and one
audit entry: the accounts audit log (actor `hook:lead`, action `conversions.test` or
`conversions.untest`, target the site, detail the counts and `refs=<the refs>`, the sender's
own ids), or in basic mode a `privacy.log` line. The CLI's `mark-test` writes through the same
function (`marks.audit_entry`, actor `cli`).

### Counts after a mark

The store is the one place the mark lives. The GET above shows it at once. `conversions.json`
is built from the store on each run (`test = 0` in every SELECT), so marking or unmarking
moves the counted figures of past days at the next build. The second count follows by its own
SQL: `audit_conversions.test_keys` reads `(tool, ref, stage)` of every row with `test <> 0`
and leaves exactly those out of the spool recount (per stage since 2.19, since a body's
`test` marks one stage only), and the call drops the audit's cached beacon days
(`conversions-audit.json`) as the CLI does. The two roads agree after a mark and after an
unmark: tested in `tests/test_lead_test_marks.py`.
