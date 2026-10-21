# Leads from the site's server: labels and the reconcile GET

Part of [INTEGRATIONS.md](INTEGRATIONS.md) (kept apart to hold that file under 1000 lines);
the rules there apply. The end-user guide with copy-paste examples:
[help/leads-from-your-backend.md](help/leads-from-your-backend.md).

## A lead's label (2.18)

The lead body's optional `label` (INTEGRATIONS.md, "The lead body") is kept in
`conversions.label` (schema 7), spooled with the body, and shown as a small tag in the lists of
conversions (Pipeline's Show lists, People's recent conversions, the person drawer).
conversions.json counts it per day (`labels`, `labels_abandoned`,
[DATA-CONTRACT-CONVERSIONS.md](DATA-CONTRACT-CONVERSIONS.md)), recounted by
`audit_conversions_figures.py`; Pipeline (Count from: Tools) has a **Label** option (`llabel` in
the address) that narrows Every action to it, and the MCP `conversions` tool takes `label`.

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
