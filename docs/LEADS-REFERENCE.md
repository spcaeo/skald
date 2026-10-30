# Leads in Skald: the reference for an app that sends them

Everything an app (or an AI session working on it) needs to send leads to Skald, check them,
correct them and read them back. Checked against the code of version 2.24.0, and the changes
added in 2.26.0 (marked "since 2.26.0"): lookup by any reference, one lead per ref, `conversions remove` and
`mark-test --ref`, `SKALD_MCP`. Where something does not exist, this page says **not available**. The details behind each part:
[INTEGRATIONS.md](INTEGRATIONS.md) (hooks), [INTEGRATIONS-LEADS.md](INTEGRATIONS-LEADS.md)
(the reconcile GET and test marks), [API.md](API.md), [MCP.md](MCP.md),
[DATA-CONTRACT-CONVERSIONS.md](DATA-CONTRACT-CONVERSIONS.md).

In the examples, `stats.example.com` is the Skald install's host, `example.com` the site, and
`u-1001` a lead's own id. Skald's hosted install is `app.skaldanalytics.com` (dashboard at
`/traffic/`, hooks at `/traffic-hooks/`).

## Quick start for an app sending leads

1. **Get the hook's secret.** A Skald admin makes it once: **Settings › This site ›
   Integrations › Your site's server (lead) › Make secret**, or on the server
   `docker exec skald skald hooks secret example.com lead`. It is shown once. Keep it in the
   app server's environment or secret store (for example `SKALD_HOOK_SECRET`). Never in code,
   a repo, a chat or the browser.
2. **Post each lead from the server**, signed:
   `POST https://stats.example.com/traffic-hooks/example.com/lead` with
   `X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>`.
3. **Body:** `{"external_ref": "u-1001", "action": "signup", "at": "2026-10-22T14:30:00Z"}`.
   Add `"ip"` (the visitor's address, read in the request that made the lead: it gives the
   lead its country, and is dropped at once), `"stage"` (default `completed`), `"vid"` (the
   page's visitor ID), `"last_touch"` and `"first_touch"` (UTMs, referrer, landing),
   `"label"`, and `"test": true` for test accounts.
4. **Read the answer.** `200 {"ok":true,"recorded":1,"duplicates":0}` is kept;
   `"duplicates":1` means Skald had it already (safe). Retry on 429 and 5xx, never on 400/401.
5. **Check daily** with the signed `GET /traffic-hooks/example.com/leads?since=<last check>`
   and resend any `external_ref` missing from it.
6. **Mark test leads** you missed with the signed `POST /traffic-hooks/example.com/leads/test`.

Rules that bite: one row per site, tool, `external_ref` and stage (the first delivery wins);
`at` always with an offset; one road per lead; `test: true` on every stage of a test lead.
Section 6 lists them all.

## 1. MCP

**Yes, Skald has an MCP server** (`skald/mcp/`, [MCP.md](MCP.md)). It is **read-only**:
every tool is marked `readOnlyHint`, and no MCP tool sends, marks, corrects or deletes a lead.

| | |
| --- | --- |
| URL | `POST https://<skald-host>/traffic-mcp` (one address for every site; the token decides which sites) |
| Transport | Streamable HTTP, one JSON answer per POST, no event stream (`GET` is 405), body at most 64 KiB. Protocol `2025-06-18` (`2025-03-26` and `2024-11-05` accepted). Or stdio on the server: `skald mcp [--site S] [--private]` |
| Switched on | Only when the install's config has `mcp: {enabled: true}` and accounts (`access.mode: sessions`). On Docker: `SKALD_MCP=true` in the container's environment (since 2.26.0; before it, a Docker install made its config from the environment and had no way to switch MCP on). Off: 404 `{"error": "MCP is not switched on here"}`. Ask the Skald admin |
| Auth | `Authorization: Bearer skald_<id>_<secret>`, an organisation API token with the `mcp` scope. 401 without it |
| Where to make it | **Settings › Team & access › Connections › Connect an AI assistant (MCP) › Set up** (a token for the current site), or **Make a token by hand** (several sites, any scopes). Owners and admins only. On the server: `skald token create NAME --scope mcp --site example.com`. Shown once |
| Scopes | `mcp` (use the endpoint), plus `read_private` only if the agent must see addresses, emails and names (`find_person`). `read` and `ingest` are not used by MCP |

Connect Claude Code (token in an environment variable, never in a repo):

```sh
claude mcp add --transport http skald https://stats.example.com/traffic-mcp \
  --header "Authorization: Bearer $SKALD_MCP_TOKEN"
```

Then `/mcp` in Claude Code shows `skald` connected. The JSON form, for a project's
`.mcp.json` (Claude Code expands `${VAR}`):

```json
{"mcpServers": {"skald": {"type": "http", "url": "https://stats.example.com/traffic-mcp",
  "headers": {"Authorization": "Bearer ${SKALD_MCP_TOKEN}"}}}}
```

The 29 tools (all **READ** but `setup_line`, `mark_todo_done`, `add_site` and `send_invites`). Dates are `YYYY-MM-DD` in the site's zone; no dates means the last
7 whole days.

| Tool | | What it answers |
| --- | --- | --- |
| `list_sites` | READ | the sites the token reads, their views, the days held |
| `overview` | READ | visits, pages read, AI and search fetches, 404s, errors, the change against the period before |
| `breakdown` | READ | visits by country, source, campaign, landing, device, browser, hour, os or referrer |
| `top_pages` | READ | the most-read pages, with AI fetches of each |
| `ai_activity` | READ | assistants and crawlers, the pages they fetched, visits that followed an assistant's link |
| `leads` | READ | leads from the **website's own lead database** only (leads.json), by type and first-touch source. Not the hook's leads |
| `funnel` | READ | a saved funnel, or your own steps, over the last 7 days and today |
| `compare` | READ | two date ranges side by side |
| `page_story` | READ | one page since it was published |
| `live_today` | READ | today so far (partial) |
| `data_quality` | READ | per day: verified, audited, withheld, log gaps |
| `site_health` | READ | open alerts, uptime, errors today, late runs |
| `conversions` | READ | **the hook's leads live here**: every action by stage (started, completed, abandoned, cancelled, no-show, won, lost), leads and demos booked, by source or by `first_source`, `landing`, `country`, `campaign`, `device`, `tool`; filters `action` and `label`. Anonymous; test rows never counted |
| `what_changed` | READ | sources and landing pages against the period before (both periods whole) |
| `todos` | READ | Insights' to-do list with each to-do's state and re-check; `id` for its rows |
| `lost_pages` | READ | Not found's old addresses, the closest live page, the nginx or Apache line |
| `page_changes` | READ | the page changes marked, and the before/after verdict of each measure (leads among them) |
| `ai_readiness` | READ | pages AI can't read well, or one page's AI readiness |
| `changed_pages` | READ | pages changed in the last 30 days and whether they get found |
| `setup_left` | READ | (2.39.0) the site's open set-up lines, each with the job an AI agent can do and its dialog's address |
| `setup_line` | MAKES A LINE | (2.39.0) **`setup` scope only.** The one-time line for an AI agent for the jobs given, as the dashboard's **Your AI agent** makes it |
| `fix_todo` | READ | (2.41) one to-do with every row behind it and the steps to fix it |
| `mark_todo_done` | MARKS DONE | (2.41) **`setup` scope only.** Keeps the agent's report on a to-do and marks it done |
| `your_tools` | READ | the figures from the site's own tools (Google Analytics...), labelled with the tool, never added to Skald's |
| `add_site` | ADDS A SITE | (Unreleased) **`add_sites` scope only.** Adds a site to the token's organisation within the plan, as **Add a site** does, and makes its set-up line. No lead is written |
| `site_progress` | READ | (Unreleased) a set-up's live steps, as Add a site's live progress shows them |
| `check_site` | READ | (Unreleased) Check now: what is missing, in plain words |
| `send_invites` | MAILS | (Unreleased) sends a new site's invites now |
| `find_person` | READ | **`read_private` only.** One IP, email, visitor ID or lead ref: visits, leads, every conversion (test, cancelled, removed too). Each call is audit-logged. Any ref is found by its `external_ref` since 2.26.0 (section 7) |

Also two resources (`skald://docs/api`, `skald://docs/counting`), two per site
(`skald://sites/<site>/overview`, `skald://sites/<site>/llms.txt`) and one prompt,
`weekly_report(site)`.

## 2. HTTP API

Three different credentials. Do not mix them up:

| Credential | Looks like | Used for | Made where | Lives where |
| --- | --- | --- | --- | --- |
| Hook secret | random text | signing `/traffic-hooks/<site>/lead`, its GET `leads` and POST `leads/test` | Settings › This site › Integrations (Make or Rotate secret), or `skald hooks secret <site> lead` | on Skald: `secrets.json` beside the history (0600, key `hooks/<site>/lead`), or an environment variable named in the config; on the sender: its environment or secret store |
| API token | `skald_<id>_<secret>` | `GET /traffic-api/v1/...` (scope `read`, `read_private` for `people`) | Settings › Team & access › Connections (Read your figures, or Make a token by hand), or `skald token create` | on Skald only a SHA-256 of it (`accounts.sqlite`); on the reader: its secret store |
| MCP token | `skald_<id>_<secret>` | `/traffic-mcp` (scope `mcp`) | as the API token | as the API token |

### 2.1 Hook endpoints (signed with the hook secret)

Base: `https://<skald-host>/traffic-hooks/<site>/`. The clock skew allowed is **300 seconds**
(5 minutes) either way, for POST and GET.

**Signing a POST:**
`X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>`. Sign the
exact bytes you send.

**Signing a GET:**
`X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.GET <target>")>`, where
`<target>` is the path and query exactly as sent, for example
`/traffic-hooks/example.com/leads?since=1792454400&limit=200` (no `?` when there is no query).
Sign the encoded query, character for character.

| Endpoint | Exists | What |
| --- | --- | --- |
| `POST /traffic-hooks/<site>/lead` | yes | send one lead (section 3) |
| `POST /traffic-hooks/<site>/json` | yes | the same body, or a list, or `{"records": [...]}`, at most 100; its own secret |
| `GET /traffic-hooks/<site>/leads` | yes (2.18) | list the leads Skald holds **from the `lead` tool** (not `json`, not other tools) |
| `POST /traffic-hooks/<site>/leads/test` | yes (2.19) | mark or unmark refs as test (`lead` tool only) |
| get one lead with its steps | **not available** on the hooks. With an API token that has `read_private`: `GET /traffic-api/v1/<site>/people?q=<ref>` (section 2.2) |
| delete, correct or soft-remove a lead, a stage, its `at`, action or label | **not available** over HTTP or MCP. Only the admin CLI: `conversions remove` (soft, since 2.26.0) or `conversions forget` (hard), section 4 |
| the delivery log | **not available** over HTTP or MCP. Settings › This site › Integrations (last 50 per hook) and `skald hooks list` (last 5) |
| view the hook secret | **not available** anywhere: it is shown once, when made |
| rotate the hook secret | Settings › This site › Integrations › Rotate secret, or `skald hooks secret <site> lead`. The old one stops at once |

**List the leads** (`conversions/reconcile.py`). Parameters, each at most once, any other
name refused (400):

| Parameter | |
| --- | --- |
| `since` | received at or after (ISO with an offset, or Unix seconds; no offset is read as UTC). When Skald got it, not its `at` |
| `at_since`, `at_until` | `at` in `[at_since, at_until)` |
| `limit` | 1 to 500, default 200 |
| `cursor` | the previous answer's `next_cursor` (`null` on the last page) |

```sh
TARGET="/traffic-hooks/example.com/leads?since=1792454400&limit=200"
T=$(date +%s)
SIG=$(printf '%s.GET %s' "$T" "$TARGET" | openssl dgst -sha256 -hmac "$SKALD_HOOK_SECRET" -hex | sed 's/^.* //')
curl -sS "https://stats.example.com$TARGET" -H "X-Skald-Signature: t=$T,v1=$SIG"
```

```json
{"ok": true, "site": "example.com", "since": "2026-10-20T00:00:00Z", "at_since": null,
 "at_until": null, "limit": 200,
 "rows": [{"external_ref": "u-1001", "action": "signup", "stage": "completed",
           "at": "2026-10-19T14:30:00Z", "label": null, "test": false,
           "received_at": "2026-10-19T14:30:02Z", "value": "49.99", "value_minor": 4999,
           "currency": "USD", "customer_ref": "cust_1001", "tags": {"plan": "pro"},
           "country_recorded": true}],
 "next_cursor": null}
```

Rows never carry an email, name, address, country, user agent, visitor ID or source. Since the
release after 2.43.0 each row says `country_recorded` (true or false): whether Skald kept a
country for it, so your server can check that its lead call passes the visitor's address
(`ip`), never the country itself. Test rows are in
it with `"test": true`. Since 2.32 each row carries the money kept: `value` (exact text in the
currency's units), `value_minor` (whole minor units), `currency`, `customer_ref`, `tags`; each
`null` when none was kept. A `refunded` row's value is the total refunded so far, never more than
its sale. Rows pruned (older than 400 days) or forgotten are not.

**Mark test** (`conversions/marks.py`), signed like a POST. Body takes only `refs` (1 to 100)
and `test` (a JSON boolean, default `true`; `false` unmarks):

```sh
BODY='{"refs":["u-1001","u-1002"],"test":true}'
T=$(date +%s)
SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "$SKALD_HOOK_SECRET" -hex | sed 's/^.* //')
curl -sS -X POST 'https://stats.example.com/traffic-hooks/example.com/leads/test' \
  -H 'Content-Type: application/json' -H "X-Skald-Signature: t=$T,v1=$SIG" --data-raw "$BODY"
```

Answer: `{"ok": true, "test": true, "marked": 3, "already": 0, "not_found": ["u-1002"]}`.
Every stage of each ref is marked, and a later stage sent for a marked ref is test too. The
rows stay and are listed, never counted. One delivery row and one audit-log entry per call.

### 2.2 Read API (API token)

`GET https://<skald-host>/traffic-api/v1/<site>/[<view>/]<name>` with
`Authorization: Bearer skald_<id>_<secret>` ([API.md](API.md)). Read-only.

| Name | Scope | What, for leads |
| --- | --- | --- |
| `conversions` | `read` | conversions.json: per local day, every action by stage, abandoned, labels, breakdowns. The Leads figure is the finished rows of lead actions (section 3.4) |
| `leads` | `read` | leads.json: the website's lead database only |
| `people?q=<value>` | `read_private` | one IP, email, visitor ID or lead ref: every conversion of it (each stage, test, cancelled, removed, with its `filled` mark and, since 2.45, its ad click `click_kind` and `click_id` when the site keeps them), the leads, visits and journeys, linked. Audit-logged. The "steps" of one lead. A visitor ID is only the `skv_` + 22 characters shape; any other ref (`u-1234567`, `u-1001`) is looked up as the lead's `external_ref` on that site (and as a site's own visitor ID) |

```sh
curl -sS -H "Authorization: Bearer $SKALD_API_TOKEN" \
  'https://stats.example.com/traffic-api/v1/example.com/people?q=u-1001'
```

Answers: 200 the file; 400 a `q` that is none of the four kinds; 401 no or a wrong token, a
token for another site, or a missing scope; 404 no such file.

## 3. Hooks

### 3.1 The tools (`conversions.TOOLS`)

URL: `POST https://<skald-host>/traffic-hooks/<site>/<tool>`. A hook exists only once it has a
secret; without one it answers 404.

| Tool | For | Signature header and scheme |
| --- | --- | --- |
| `lead` | the site's own server | `X-Skald-Signature: t=..,v1=<hex HMAC-SHA256("<t>.<body>")>`, 300 s |
| `json` | Zapier, Make, n8n, scripts | the same as `lead`; body one lead, a list, or `{"records": [...]}` (at most 100) |
| `calendly` | Calendly webhook subscriptions | `Calendly-Webhook-Signature: t=..,v1=..` (the same scheme), 300 s; secret = the subscription's `signing_key` |
| `calcom` | Cal.com webhooks | `X-Cal-Signature-256: <hex HMAC-SHA256(body)>` (an optional `sha256=` prefix); no timestamp, so a body seen in the last 30 days is a replay |
| `stripe` | Stripe Checkout, subscriptions and refunds | `Stripe-Signature: t=..,v1=..`, 300 s; secret = the endpoint's `whsec_...`, pasted in |
| `typeform` | Typeform webhooks | `Typeform-Signature: sha256=<base64 HMAC-SHA256(body)>`; no timestamp, replay check as Cal.com |
| `hubspot` | HubSpot app and workflow webhooks | `X-HubSpot-Signature-v3` (base64 HMAC-SHA256 of method + URI + body + timestamp) with `X-HubSpot-Request-Timestamp` in ms, 300 s; secret = the app's client secret, pasted in |

What each provider event becomes (`conversions.EVENTS`): Calendly `invitee.created` demo
completed, `invitee.canceled` cancelled (or rescheduled), `invitee_no_show.created` no_show;
Cal.com `BOOKING_CREATED` / `CANCELLED` / `RESCHEDULED`; Stripe `checkout.session.completed`
paid (started while unpaid), `async_payment_succeeded` paid, (2.32) `invoice.paid` with
`billing_reason` `subscription_cycle` paid (a renewal), `charge.refunded` refunded,
`invoice_payment.paid` no row (it joins a payment to its invoice); Typeform `form_response` contact
completed; HubSpot `contact.creation` contact, a meeting (`0-47`) demo, a deal moved to
`closedwon` deal won, a workflow contact (or its `skald_action`). Other events are taken and
ignored.

**Stripe: the events to subscribe the endpoint to** (Developers › Webhooks › the endpoint ›
Events): `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
`invoice.paid`, `charge.refunded` and `invoice_payment.paid`. Since 2.32 each keeps its money: a checkout's
`amount_total` (its ref the Checkout Session id), a renewal's `amount_paid` (its ref the
invoice id; the first invoice of a subscription is the checkout's sale, not a renewal), in
Stripe's smallest unit (ISK and UGX are sent in hundredths and divided by 100), the
`currency`, `customer_ref` = the `customer` id (`cus_...`) and the payment intent, so a refund
finds its sale. `charge.refunded` carries the total refunded so far (`amount_refunded`): one
`refunded` row per sale, raised by a later, larger total, never a second row; each rise counts
on the day it arrived. Stripe sends `charge.refunded` for every charge of the account: a refund
whose sale never reached Skald is kept, never subtracted, and counted in conversions.json's
`refunds_without_sale`. A refund that arrives before its sale is moved onto it when the sale
comes. Since Stripe's API version 2025-03-31 ("basil") an Invoice has no `payment_intent` and a
Charge no `invoice`, so a renewal's refund names only its payment intent. Stripe's
`invoice_payment.paid` (an InvoicePayment: `invoice` and `payment.payment_intent`) joins the
two: subscribe to it, or a basil renewal's refund stays without its sale. Older API versions
send both fields and need no link. A renewal's
visitor ID is the subscription's `metadata.skv` when set; without it the renewal is joined to
its first sale by the customer id when lifetime value is counted. Customer details (name,
email, address) are never read.

### 3.2 The lead body (`lead` and `json`, `adapters/lead.py`)

| Field | | Rules |
| --- | --- | --- |
| `external_ref` | required | the lead's own id, text, trimmed, at most 120 characters |
| `action` | required | a lowercase token `^[a-z0-9][a-z0-9_.:-]{0,39}$`. Aliases: `booking`, `meeting`, `demo_booked`, `call_booked` read as `demo`; `checkout`, `payment` as `paid`; `form`, `contact_form` as `contact`; `sign_up` as `signup` |
| `stage` | default `completed` | one of `started`, `completed`, `cancelled`, `rescheduled`, `no_show`, `paid`, `won`, `lost`, `refunded` (2.32: money given back on the sale with the same `external_ref`; it counts only once that sale is kept, in the sale's currency) |
| `at` | default: when it arrived | ISO 8601 with an offset (`...Z`, `...-04:00`) or Unix seconds (milliseconds accepted). Without an offset it is read in the site's time zone, and the delivery log says so. More than a day in the future: 400 |
| `vid` | | the visitor ID the page had (`skald('id')` in the browser gives the `skv_...` one), or the site's own ID: `^[A-Za-z0-9_.:-]{8,80}$`, else dropped. Dropped too when the site has visitor IDs off (`beacon.visitor_ids`) |
| `first_touch`, `last_touch` | | objects with `referrer`, `landing`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `gclid`, `gbraid`, `wbraid`, `msclkid`, `fbclid`, `li_fat_id`, `ttclid`, `twclid` (the last two since 2.45), `at`. The source comes from `last_touch` (else `first_touch`). Send neither and a `vid`: Skald fills both from that browser's page views (2.45, "Touches filled" in 3.4) |
| `landing`, `campaign`, `source` | | when the app worked them out (`source` only if it is one of Skald's source types) |
| `country` or `ip` | | two letters, or the visitor's address: Skald looks up the country (in `logs.country_db`) and drops the address; it is never kept, spooled or logged. **Send `ip` on every lead from your server**: without it (or `country`) the lead has no country ("Country not recorded"), whether or not it has a `vid`. `ip` is an IPv4 or IPv6 address, or an `X-Forwarded-For` list whose first entry is read (`"192.0.2.10, 198.51.100.1"`), a port after it taken off. An address that gives no country (a private one such as a proxy's, or not an address) is kept without one, with a note. `country` wins over `ip`. A visitor ID never gives a lead its country: `vid` joins the pages read, `ip` gives the country; send both. Which header holds the address on which host: the lead files' README ("The visitor's address") |
| `device` or `user_agent` | | `Desktop`, `Mobile` or `Tablet`, or the agent: Skald works out the device and drops the agent |
| `visits_before` | | a whole number 0 to 100000 |
| `first_touch_at` | | a time, as `at` |
| `name`, `email` | | kept only when the site's `conversions.identity` is `full`; else dropped before anything is written |
| `label` | | a short token `^[a-z0-9][a-z0-9_-]{0,39}$`, trimmed and lower-cased. Anything else: kept without a label, with a note |
| `test` | | a JSON boolean. `true`: this row is kept and listed, never counted. Anything else but `false`/`null`: ignored, with a note |
| `value` | (2.32) | the money, in the currency's major units: a JSON number (`49.99`) or a numeric string (`"49.99"`), at least 0, with no more decimals than the currency has (JPY 0, USD 2, KWD 3). Kept as whole minor units (`4999`), at most 10^12; text longer than 30 characters is never read. On a `refunded` row: the total refunded so far, in the sale's currency; left out, the whole sale. More than the sale: kept as the sale's value, with a note; in another currency than the sale's: kept without a value, with a note. Not one (`"49.999"` in USD, `-1`, `"1e3"`, `"1,000"`, `true`): kept without a value, with a note |
| `currency` | with `value` | ISO 4217, three letters, upper-cased first (`usd` is `USD`). Missing or not an ISO code: the value and the currency are dropped, with a note. Skald never converts currencies |
| `customer_ref` | (2.32) | the customer's own opaque id in your app, `^[A-Za-z0-9_.:-]{1,128}$` (a number is read as text). Never an email, a phone number or an address: one with `@`, one shaped like an IPv4 address (`198.51.100.7`), one of only digits and `+ ( ) . -` with 7 or more digits (`15551234567`, `555.123.4567`), or anything else, is dropped with a note, in the store and the spool. Ids such as `cus_9`, `c_10293847` or a UUID are kept. Joins a renewal to the first sale |
| `tags` | (2.32) | an object of at most 5 `{key: value}`: key `^[a-z0-9_]{1,24}$`, value a token `^[a-z0-9_.-]{1,40}$`, both lower-cased. Never a phone number, an address or a personal key: a value with 7 or more digits in all (`555-123-4567`, `555.123.4567`), a value shaped like an IPv4 address (`192.0.2.10`) and a key such as `phone`, `email` or `ip` are not tags, in the store or the spool. A bad tag (or a sixth, by key order) is dropped with a note, the others kept. Stored sorted, as canonical JSON |

Any other key is dropped before the body is spooled.

### 3.3 Answers

| Status | Body | When |
| --- | --- | --- |
| 200 | `{"ok":true,"recorded":1,"duplicates":0}` | kept (or a `refunded` row's total raised). `"notes":[...]` is added when a `label`, `test`, `value`/`currency`, `customer_ref` or tag was ignored, a refund was cut to its sale's value or kept without a value (another currency than the sale's), or an `ip` gave no country (a private address, or no country file on Skald's server) |
| 200 | `{"ok":true,"recorded":0,"duplicates":1}` | Skald has that ref and stage already (or a Cal.com/Typeform replay); nothing changed |
| 200 | `{"ok":true,"recorded":0,"duplicates":0,"outcome":"ignored: other event type"}` | Calendly/Cal.com with the site's event types named, another type |
| 200 | `{"ok":true,"test":true,"records":1,"would_keep":1,"notes":[...],"read":[{action, stage, at, vid, source_type, campaign, country, device, label, test, value_minor, currency, customer_ref, tags}]}` | the request had `X-Skald-Test: 1` (still signed): checked and read, never kept or counted |
| 400 | `{"error":"..."}` (and `"test":true` for a test) | not JSON, or the body breaks a rule (no `external_ref`, a bad `action` or `stage`, `at` not a time or a day ahead, over 100 records) |
| 401 | `{"error":"bad signature"}` | wrong or missing signature, or `t` more than 300 s off |
| 404 | `{"error":"not found"}` | unknown site or tool, no secret, or a site waiting for domain verification |
| 405 | `{"error":"POST only"}` | another method (the one GET is `.../leads`) |
| 411 / 413 | `{"error":"length required"}` / `{"error":"body over 64 KiB"}` | no `Content-Length` / over 64 KiB |
| 429 | `{"error":"too many"}` | over a rate limit (3.6) |
| 500 | `{"error":"not kept, send again"}` | disk or database; retry |

`X-Skald-Test: 1` works on every tool's POST. Send it to check a new integration end to end
without leaving a row.

### 3.4 The rules

- **Duplicates.** One row per (site, tool, `external_ref`, stage): `UNIQUE` in the store. The
  first delivery wins. A resend of a kept ref and stage changes nothing, not its `at`,
  `action`, `label`, `test` or touches. The action is **not** part of the key: a `trial`
  `started` for a ref that already has a `signup` `started` is answered
  `{"ok":true,"recorded":0,"duplicates":1}` and dropped (checked on the live install).
- **Stages.** `conversions.STAGES` as above. `FINISHED` = `completed`, `paid`. `OUTCOMES` =
  `won`, `lost`: a later outcome of a finished lead, a row of its own on its own `at`, never a
  lead itself. A `won` or `lost` for a ref that never finished is not a lead.
- **Lead actions** (`LEAD_ACTIONS`): `contact`, `signup`, `waitlist`, `trial`, `demo`
  (`DEMO_ACTIONS` = `demo`, also counted as demos booked).
- **What counts as a lead.** One (site, tool, `external_ref`, action) of a lead action is one
  lead, on the local day of its first finished row (`completed` or `paid`; the earliest `at`,
  then the stage's name), test rows left out. A ref sent as both `completed` and `paid` under
  a lead action is one lead (since 2.26.0; before, two): the later row is a step of it, listed
  in its drawer, left out of Leads, Every action and the breakdowns. Another action (`paid`,
  `deal`, `lead`, `purchase`...) is a conversion, never a lead, and counts every row.
- **Money (2.32).** A sale is a finished row (`completed` or `paid`) with a `value`, counted
  once per (tool, `external_ref`): the `paid` row when it carries a value, else the
  `completed` one. So a sign-up sent `completed` and then `paid` with the amount is one lead
  and one sale. A refund is `stage: "refunded"` on the sale's `external_ref`, with `value`
  the total refunded so far (send 10, then 25 for a second partial refund of 15; a smaller
  or repeated total changes nothing; no `value`: the whole sale). Each part counts on the day
  it arrived (the 10 on its day, the 15 on the later one), against the sale's source, campaign
  and the rest. A refund counts only once its sale is kept, in the sale's currency, and never
  more than the sale; a refund of 0 is no refund. One sent before its sale waits for it
  (conversions.json's `refunds_without_sale` until then) and is then moved onto it; if the
  sale then cuts it to its value, or empties it for another currency, no note is sent (the
  refund's answer went out before the sale was known). A refund kept without a value (not
  readable, or another currency than its sale) stays in `refunds_without_sale`. **Renewals:** send each renewal as a new
  `paid` row with its own `external_ref` (the invoice's id) and the same `customer_ref`; the
  first sale of a `customer_ref` in a currency is a new customer, every later one a renewal.
  Money is summed per currency, never converted. Test rows and removed rows are never money.
  Example:

  ```json
  {"external_ref": "inv_2026_10", "action": "signup", "stage": "paid", "value": "49.00",
   "currency": "USD", "customer_ref": "cust_1001", "tags": {"plan": "pro"}}
  ```
- **Abandoned.** A `started` row with a visitor ID and no `completed` or `paid` of the same
  action, by the same visitor ID or identity, within 24 hours (`conversions.abandon_hours`).
  Counted only once the window has closed; never without a visitor ID; worked out at each
  build, not stored.
- **Labels.** As in the body table. Each row keeps its own label: a later stage has the label
  it sends, else none.
- **Test.** Per row: `test: true` marks only that delivery's row (stage). Send it on every
  stage of a test lead. A ref marked through `leads/test` or `mark-test` passes the mark on to
  its later stages.
- **Identity.** Names and the primary email are kept only when the site's
  `conversions.identity` is `full` (the default on a new install; `anonymous` on one upgraded
  from before 2.4.0). Phones, other emails, addresses and user agents are never kept.
- **Visitor ID linking.** A `vid` ties the lead to the browser's journey (pages before, first
  and assisted touch, abandoned). Only when the site has `beacon.visitor_ids` on; with it off,
  no visitor ID is kept from any road. Matching is never by IP address, and a lead's country
  never comes from its visitor ID's visits: only from `country` or `ip`. For `www.` and `app.`
  to share one ID, the tag takes `data-share-subdomains="true"`, or an admin can switch sharing
  on in Skald instead of the tag (`beacon.share_subdomains`, Settings > Sites > Script tag;
  docs/BEACON.md).
- **Touches filled from the visitor ID (2.45).** A lead with a `vid` and no `first_touch`, no
  `last_touch` and no `source` gets them from that browser's page views (the script tag's,
  `journeys`): the first touch is its earliest page view (first source, first touch time,
  landing page), the last touch the latest visit up to the lead's `at` (its source and
  campaign). Only by the visitor ID, never by IP address; only page views at or before `at`.
  What the sender gave always wins: a lead with any touch or `source` is not filled, and a
  `landing`, `campaign` or `first_touch_at` sent alone stays. The lists, the drawer and the
  person lookup say "filled by Skald" (`filled`: the columns). It is done when the lead
  arrives and again on each run, so page views that arrive after the lead still fill it.
  Script-tag conversions get their first source, campaign and first touch time the same way.
  The second count (`audit_filled.py`) checks every filled value against the page views; a
  day it disagrees with is withheld (`docs/DATA-CONTRACT-CONVERSIONS.md`).
- **Ad click IDs (2.45, opt-in).** With `conversions.click_ids` on (Settings › Data retention
  › Leads, "Keep ad click IDs on leads"; off by default) a lead keeps the ad click ID its
  touch carried: the last touch's (else the first's) `gclid`, `gbraid`, `wbraid`, `msclkid`,
  `fbclid`, `li_fat_id`, `ttclid` or `twclid`, as a key of the touch or in its `landing`
  address's query, as `click_kind` and `click_id` (an ID of 1 to 250 characters of
  `A-Z a-z 0-9 . _ ~ + / = -`, else none). A filled lead takes its page views' click (the
  script tag sends it only while this is on); a script-tag conversion too. Shown only to
  owners and admins (the lead drawer, with the names' gate) and to a `read_private` token
  (`people?q=`); never in conversions.json, the MCP figures or outgoing webhooks. Deleted
  with the lead (`forget --email/--vid/--lead`; a conversion keeps no IP address, so
  `forget --ip` finds none), after the People days when those are shorter than the lead's
  (as a name and an email are, `conversions/people_days.py`), and all of the site's at the
  next run when the setting is turned off. Before 2.45 click IDs were read only to name the
  source and campaign, never kept on a conversion. The hook spool keeps the body's touches
  as sent, click IDs included, as it did before.
- **Leads without a country.** When each of the `lead` (or `json`) hook's last 3 real leads was
  kept without a country, Skald says so, with the fix: Settings › Leads & tools › Status
  ("Lead countries", the doctor's `place:<tool>` line, also in `skald doctor`) and the set-up
  checklist's lead line, whose Set up is the AI agent's `lead` job. Leads kept already stay as
  they are: Skald never guesses a country afterwards (never by matching times to the log).
- **One road per lead.** Each tool keeps its own row, so the same ref through `lead` and
  `json` (or a hook and the lead database) counts once per tool. Settings › Integrations ›
  Status flags it as "One lead, two tools".
- **Keeping.** Rows older than 400 days (`conversions.retention_days`) are pruned; with 0
  (`forever`, Settings › Data retention › Leads) they are kept for good, with the pages
  their visitor IDs read and the hook spool. Delivery rows go after 90 days either way.

### 3.5 Limits

| What | Limit (config key, default) |
| --- | --- |
| Verified POSTs per site and tool | `hooks.per_minute` 60 a minute, burst `hooks.burst` 30 |
| Install-wide, per bucket | `hooks.all_per_second` 20 a second |
| Failed signatures per sender address | `hooks.preauth_per_minute` 30, burst `hooks.preauth_burst` 10 |
| GET `leads`, per site | `hooks.leads_per_minute` 60, burst `hooks.leads_burst` 20 |
| POST `leads/test`, per site | the same numbers, a bucket of its own |
| Body | 64 KiB; `json` at most 100 records; `leads/test` at most 100 refs; GET at most 500 rows a page |

A bucket holds the burst and refills at the per-minute rate: for a hook, 30 at once, then 1 a
second. A failed signature never spends the hook's own bucket. On 429, back off and retry.

## 4. Admin CLI on the server

On Docker: `docker exec skald skald <command>` (the image's `skald` runs
`skald --config <config> <command>`). The global `--site NAME` goes **before** the command.
These are for the Skald admin, not for an app.

| Command | Flags (from the argparse code) | Does |
| --- | --- | --- |
| `conversions list SITE` | `--test` (only rows marked test), `--limit N` (default 50) | the latest rows, newest first: id, at, tool, action, stage, ref, label, TEST |
| `conversions mark-test SITE [ID ...]` | `--ref REF` (repeat for more; since 2.26.0), `--tool T` (default `lead`), `--unmark` | mark rows by **id**, or every stage of each **ref** (the same function as `POST .../leads/test`), as test, and later stages of it too; prints the rows changed, already so and refs not found; audit-logged |
| `conversions remove SITE` | `--ref REF` (required), `--tool T` (default `lead`), `--stage S`, `--action A`, `--why "text"` (required), `--dry-run` | since 2.26.0: **soft remove** of that ref's rows (or one stage or action of it): each row copied whole into `removed` with when and why, out of every count, listed under Calendar bookings › More › Show left out › Removed and in Find a person. Refused without `--why`; `--dry-run` lists what would go. Audit-logged. A resend of the same ref and stage afterwards is kept as a new row |
| `conversions forget` | one of `--email`, `--vid`, `--lead REF`; `--dry-run` | **hard delete**: the conversions (every tool), and through their visitor IDs and email the other conversions and page views of the same person, the identity, removed rows, delivery rows and spool lines. Add the global `--site` to keep it to one site; try `--dry-run` first |
| `forget` | `--ip`, `--email`, `--vid`, `--lead`; `--dry-run` | a deletion request: also the visits kept with an address |
| `conversions prune` | | delete what is past its keeping time (the daily run does it) |
| `hooks secret SITE TOOL` | `--value V` (a tool's own secret; `-` reads stdin) | make or replace the secret, printed once with the hook's address; the old one stops at once |
| `hooks list` | | each hook, where its secret lives (never the value), its last 5 deliveries |
| `hooks test SITE TOOL` | `--url` (default `http://127.0.0.1:8766`) | post a signed sample with `X-Skald-Test: 1`: read, never kept; prints what a real one would keep |
| `settings get SITE [KEY]` | | the value and where it comes from |
| `settings set SITE KEY VALUE` | `--yes` (for a smaller retention) | save it, audited. `conversions.identity` takes `full` or `anonymous`; `beacon.visitor_ids` `true` or `false` |
| `doctor` | | per hook: needs a secret, never received, ready, or last received N ago |

Examples:

```sh
docker exec skald skald conversions list example.com --limit 20
docker exec skald skald conversions mark-test example.com 6 7
docker exec skald skald conversions mark-test example.com --ref u-1001 --ref u-1002
docker exec skald skald conversions remove example.com --ref u-1001 --stage paid \
  --why "paid sent under the signup action" --dry-run
docker exec skald skald --site example.com conversions forget --lead u-1001 --dry-run
docker exec skald skald settings get example.com conversions.identity
docker exec skald skald settings set example.com beacon.visitor_ids true
```

`backfill` and `audit` are about **log days**, not leads: `backfill --days N [--force]` stores
past days from the access log; `audit --day D [--withhold] [--live]` recounts a log day by a
second road. Leads need neither: conversions.json is rebuilt from the store on every run, and
its own second count (`audit_conversions*.py`) recounts the hook spool; a day the two disagree
on is withheld. To backfill old leads, post them with their real `at` (section 6).

## 5. The screens

| Where | What |
| --- | --- |
| **Leads & sales › Leads** | one row per lead (the first finished row of each ref and lead action, section 3.4): when, name and email (owners and admins, identity `full` only), action, label, stage now (the latest won, lost, cancelled, no-show or rescheduled of the same lead), where it came from, source, landing, country. A row opens its steps and pages. List, Board, Timeline, Map. Names viewed are audit-logged |
| **Leads & sales › Summary** | Count from **Tools** (the hooks) or **Lead database**, never added: Leads, Demos booked, Won, Lost against the period before; Every action (started, completed, abandoned, rate over 10 starts, cancelled, won, lost) |
| **Leads & sales › Sources** | where finished leads came from: last, first and assisted touch, time to convert |
| **Leads & sales › Funnels** | pages and events over visits (the script tag), not the hook |
| **Leads › More › Show left out** | test, spam and duplicate leads, marked, never counted |
| **Calendar bookings › More › Show left out** | Cancelled or no-show, **Removed** (rows a lead-database sync or `conversions remove` took away, kept whole with when and why), Test |
| **Find a person** | one IP, email, visitor ID or ref, linked (owners and admins) |
| **Overview › Summary** | the Leads and Demos booked tiles, today live |
| **Settings › This site › Integrations** | each hook's state, Make/Rotate secret, Send a test event, the last 50 deliveries, Status |

Leads & sales opens on the **last 7 whole days** (up to yesterday) when the link names no
period; today's new leads show as a line with **Show today (live)**. Only days whose
conversions passed the second count are summed; a withheld day is named, a day before a source
existed is "not recorded", never zero.

## 6. Never do

- **Re-send with a different `at` for the same ref and stage.** It is a duplicate: answered
  `"duplicates":1`, nothing changes, the old `at` stays.
- **Send a bare date or a time without an offset** (`2026-10-22`, `2026-10-22T09:00:00`). It is
  read in the site's zone at that clock time, which is rarely the real moment. Send UTC with
  `Z`, an offset, or Unix seconds.
- **Send the same lead through two tools** (`lead` and `json`, or a hook and the lead database).
  It counts once per tool. Backfill through the same tool you use live.
- **Send test or staff leads without `test: true`**, on every stage. Missed ones: mark them
  with `leads/test`.
- **Change the action mid-life.** Keep one `action` per ref. A later stage under another action
  is a row of that other action (its outcome and abandoned are matched per action), and a
  resend of a kept stage keeps the first action.
- **Send two actions with the same stage for one ref** (`signup` `started`, then `trial`
  `started`). The second is a duplicate and is dropped. Use one action per ref.
- **Send `completed` and `paid` for the same ref under a lead action** to count a payment
  without a `value`. It is one lead (since 2.26.0; before, two), and the `paid` is only a step
  of it, in no lead count. Since 2.32 send the amount on the `paid` row (`value`, `currency`):
  it is then the sale, in Revenue, while the lead stays one.
- **Send a refund as a negative value, or each partial refund on its own.** Send `refunded`
  with the running total (10, then 25), never -10, and never a second ref for it.
- **Put an email, a phone number or a name in `customer_ref` or `tags`.** They are dropped, but
  they should not leave the app at all. Use your own opaque customer id.
- **Add up two currencies.** Skald never converts: send each sale in the currency it was paid
  in, and read Revenue per currency.
- **Send names or emails where the site's identity is not `full`.** They are dropped, but they
  should not leave the app at all.
- **Exceed the rate limits.** Each hook is a token bucket: 30 at once (`hooks.burst`), then
  refilled at 1 a second (`hooks.per_minute` 60), then 429. Pace senders at about 1 a second,
  never burst more than 30, and on 429 back off and retry. The GET and `leads/test` have 60 a
  minute, burst 20, each. Failed signatures spend a per-sender bucket (30 a minute, burst 10),
  so fix a bad secret before retrying. A backfill goes at that pace through the tool used live
  (see "two tools").
- **Send from the browser with the secret.** The secret signs on the server only. The browser
  may only read `skald('id')` and pass it to the server.
- **Resend a lead deleted on request.** The `lead` hook keeps no hash of bodies, so it would
  come back.

**Correcting a mistake.** There is no edit, and no remove over HTTP or MCP, for a hook's lead:

- a lead that should not count: mark it test (`POST .../leads/test`, the app can do it), or an
  admin runs `conversions mark-test SITE --ref <ref>` (or by row id). Kept and listed, never
  counted; reversible.
- a wrong `at`, action, label, source or stage: **ask the Skald admin.** Since 2.26.0:
  `skald conversions remove <site> --ref <ref> [--stage S] --why "..." --dry-run`, then without
  `--dry-run` (each row kept whole under Calendar bookings › More › Show left out › Removed,
  with when and why, out of every count), and then the app sends the lead again, correct: a
  resend after a remove is kept as a new row. Before it, or to erase a person on request:
  `skald --site <site> conversions forget --lead <ref> --dry-run`, then without `--dry-run` (a
  hard delete of every stage of that ref from every tool, its identity, delivery rows and spool
  lines, and also every other conversion and page view of the visitor IDs it carries). Not
  available over HTTP or MCP.
- re-sending a different stage never replaces a row: it adds a row of that stage, and the
  wrong one stays.
- a removed ref is no longer in the GET `leads` list, so an app that resends every ref missing
  from that list sends it back. If the app reconciles that way and the lead must stay out, mark
  it test instead of removing it.

## 7. Known limits

- Fixed in 2.26.0: up to 2.25, a lead ref of 8 to 80 characters made only of
  letters, digits, `_ . : -` (for example `u-1234567`) was read as a **visitor ID** by the
  person lookup (Find a person, `people?q=`, MCP `find_person`), so it was never found by its
  ref. Now only the `skv_` shape is a visitor ID; every other ref is found by `external_ref`.
- The GET `leads` list and `leads/test` cover the `lead` tool only, not `json`.
- The delivery log and secret rotation are dashboard or CLI only.
- A hook's row cannot be edited by any command or call. A correction is a soft remove by the
  admin (`conversions remove`, since 2.26.0) or a `forget` (hard delete), and a resend.
