# Recorded journeys (2.43)

A website may send Skald what its own visitors did, one event at a time: a session began,
a page was read, a button was pressed, a form was sent, a booking was made. Skald keeps these
events apart from the log, labels them **Recorded by your site**, and never adds them to the
log's counts.

Code: `skald/recorded/` (`contract.py`, `receive.py`, `store.py`, `queries.py`), the
dashboard routes `skald/journeys_api.py`, the second count
`skald/audit_journeys.py`. Tests: `tests/test_recorded_journeys.py`. End-user guide:
[docs/help/recorded-journeys.md](help/recorded-journeys.md).

## What it is, and what it is not

The owner's decision (2026-10-27): data a site sends about itself may feed Skald, as long as

- it is labelled by where it came from ("Recorded by your site"),
- it is never mixed into the log's figures (visits, visitors, pages, sources),
- it is stored raw, with an independent recount that shares only name lists with the main code,
- unknown stays unknown: a figure not recorded is never shown as 0,
- every set-up step can be done by the one-time agent line,
- the site's privacy settings apply as they do for leads.

It is:

- consented sessions only: an event without analytics consent is refused, never kept;
- fixed facts: identifiers, paths, event names, a short label, the first touch;
- sent by the website's own server, signed with the site's own secret.

It is not:

- a replacement for the log or the script tag. Visits, visitors and pages still come from the log;
- a form recorder. A form's answers never come here. Only an email may come, on three events,
  and only when the site keeps identity;
- a guess. A recorded session is linked to a log visit only by a shared visitor ID or by the
  same kept address inside the visit's time (see "Linking to the log's visits").

## The contract (version 1)

One event is one JSON object. Every field is checked. An unknown field, a repeated key, a
path with a query string, or a text that looks like an email, a phone number, an IP address or
a long token is refused as a whole (400). Skald never cleans a bad event: the site's code is
wrong and should know.

```json
{
  "schema_version": 1,
  "event_id": "0f8b5a52-3c1e-4c4e-9b7d-2a6f0e1c9d01",
  "event_name": "session_started",
  "occurred_at": "2026-10-27T12:00:00Z",
  "visitor_id": "6c1d2e3f-4a5b-4c6d-8e7f-90a1b2c3d4e5",
  "session_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "path": "/pricing",
  "consent": {"analytics": "granted", "notice_version": "2026-10"},
  "touch": {"landing_path": "/pricing", "referrer": {"host": "search.example.com", "path": "/"},
            "utm_source": "newsletter", "utm_medium": "email"},
  "skald_vid": "skv_Q2xhc3NpY0V4YW1wbGVJRA",
  "ip": "203.0.113.7"
}
```

| Field | | Rule |
| --- | --- | --- |
| `schema_version` | required | the number `1` (not `"1"`) |
| `event_id` | required | a lowercase UUID, new for each event. A retry sends the same ID |
| `event_name` | required | one of the names below |
| `occurred_at` | required | UTC, `YYYY-MM-DDTHH:MM:SSZ`, up to 6 decimals; kept to the whole second. At most 7 days old, at most 5 minutes ahead |
| `visitor_id` | required | a lowercase UUID the site keeps for the browser (not Skald's ID) |
| `session_id` | required | a lowercase UUID for the session. One session holds one visitor |
| `path` | required | the page's path only: starts with `/`, at most 500 characters, no `?`, `#`, `\`, `..` or control character. A trailing `/` is dropped (`/pricing/` is kept as `/pricing`) |
| `consent` | required | `{"analytics": "granted"}`, with an optional `notice_version` (at most 80 characters). Anything else: refused |
| `label` | optional | a short line of text, at most 80 characters, such as the button's words |
| `touch` | optional, `session_started` only | `landing_path` (required in it), `referrer` (`host`, and `path`, default `/`), `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term` (each at most 160). The host is kept lowercase; a bare IP host is refused |
| `skald_vid` | optional | the script tag's visitor ID (`skv_` and 22 characters), when the page has it. It is what links a session to a log visit by visitor ID |
| `ip` | optional | the visitor's address as the website's server saw it; kept by the site's setting (below) |
| `email` | optional, `form_sent`, `signup`, `booking_made` only | at most 254 characters, kept lowercase; kept only when the site keeps identity |

The text fields (`label`, `notice_version`, the `utm_` fields) and every path are refused when
they hold an `@`, seven digits in a row, a phone-like run of ten digits, a run of 40 letters and
digits, or an IP address.

Event names:

| Name | Means | Counted as |
| --- | --- | --- |
| `session_started` | a session began; carries `touch` | the session's start |
| `page_view` | a page was read | a page read |
| `cta_click` | a call to action was pressed | an action |
| `form_sent` | a form was sent | an action |
| `signup` | an account was made | an action |
| `booking_opened` | a booking calendar was opened | an action |
| `booking_made` | a booking was made | an action |
| `download` | a file was downloaded | an action |

A session's ending, shown in the list, is its best action in this order: `booking_made`,
`signup`, `form_sent`, `download`, `booking_opened`, `cta_click`.

A withdrawal is its own body, posted to `.../journey/withdraw`:

```json
{"schema_version": 1, "visitor_id": "6c1d2e3f-4a5b-4c6d-8e7f-90a1b2c3d4e5",
 "occurred_at": "2026-10-27T12:05:00Z", "consent": {"analytics": "withdrawn"}}
```

## Signing

The browser never holds the secret. The page posts to the site's own relay (its own server),
which signs and forwards. Two headers:

```
X-Skald-Timestamp: <unix seconds>
X-Skald-Signature: hex(HMAC-SHA256(secret, timestamp + "." + body))
```

The body is signed exactly as sent. The timestamp must be within 300 seconds of Skald's clock,
either way. The signature is checked before the body is read as JSON.

The secret is the site's own: `secrets.json` key `hooks/<site>/journey` (0600, beside the
history), made in Settings › Leads & tools › Recorded journeys, by the agent job, or on the
server with `skald hooks secret <site> journey` (printed once with the address; a new one
replaces the old at once). A config may name an environment variable for it instead, as for
any hook (`hooks: {"example.com/journey": SKALD_JOURNEY_SECRET_EXAMPLE}`); then neither the
dashboard nor the command makes it. Journey is not a conversion tool: `hooks list` and
`hooks test` do not show it.

## The routes

Both on the beacon helper (`beacon_server.py`), behind nginx:

- `POST /traffic-hooks/<site>/journey`: one event.
- `POST /traffic-hooks/<site>/journey/withdraw`: delete the visitor's events.

Each request, in order:

| Answer | When | Retry? |
| --- | --- | --- |
| 404 | the site is not one this install reports on, has no journey secret, or waits for its domain to be verified | no |
| 405 | not a POST | no |
| 500 | `secrets.json` is not 0600, or an unexpected failure | fix the server first |
| 411 | no Content-Length | no |
| 413 | the body is over 16 KiB | no |
| 401 | the signature is wrong or outside the 300 s window | no; check the secret and the server's clock |
| 429 | too many bad signatures from one sender, the site over `journeys.per_minute` (600 a minute, burst 200), or one visitor over `journeys.visitor_per_minute` (120); `Retry-After: 60` | yes, after Retry-After |
| 400 | the body breaks the contract: `{"error", "field"}`, in plain words. No consent: field `consent` (counted) | no; fix the code |
| 201 | kept, new: `{"ok", "event_id", "duplicate": false}` | done |
| 200 | the same event again: `"duplicate": true` | done |
| 409 | the same `event_id` came before with another body | no; a new event needs a new ID |
| 202 | the visitor withdrew; nothing kept: `{"ok", "ignored"}` | done |
| 503 | storage unavailable; `Retry-After: 30` | yes, after Retry-After |

A withdrawal answers `200 {"ok": true, "removed": <n>}`, or 400, 401, 404, 429 or 503 as above.

When the site's privacy settings dropped or shortened something, a 201 or 200 carries
`"notes"` saying so, in words. A retry is safe: send the same body with the same `event_id`.

Nothing in a request is ever written to a log. Bad signatures and rate refusals are counted in
the `deliveries` table as the other hooks are (one row a minute per kind, tool `journey`).
Consent refusals, withdrawals and ignored retries are counted per day in `recorded_log`.

## Consent

Every event says `consent.analytics: "granted"`. Anything else (`denied`, `pending`, missing)
is refused with 400 before any other field is read, and counted. Skald keeps nothing about it.

A withdrawal (`consent.analytics: "withdrawn"`) deletes every event of that visitor ID on that
site, then writes a tombstone: a keyed digest of the visitor ID (HMAC-SHA256 with a key kept
in `conversions.sqlite`'s `meta`, never the ID itself). For 90 days, a late retry from that
visitor is answered 202 and not kept.

## Privacy at the door

Applied before anything is kept, from the site's own settings, as for leads:

| Setting | `ip` | `email` |
| --- | --- | --- |
| `privacy.keep_ips: full` | kept | |
| `privacy.keep_ips: short` | shortened (IPv4 last octet zeroed, IPv6 first 48 bits kept) | |
| `privacy.keep_ips: off` | dropped | |
| `conversions.identity: full` | | kept |
| `conversions.identity: anonymous` | | dropped |

Only owners and admins see a kept address or email on the dashboard. Other members see the
same sessions without them.

## Retention

The daily run's `conversions prune` step (`store.run_prune`), each site by its own settings:

- an event goes once it is older than `journeys.vid_days` (30, the same days as page views per
  visitor ID);
- its address and email are cleared (the column and the raw JSON) once older than
  `privacy.keep_days`, when that is shorter than `journeys.vid_days`;
- a site that keeps everything (`keep_everything.py`, docs/SETTINGS.md "Keep everything")
  loses nothing and has nothing cleared;
- a withdrawal still deletes, on any site: it is the person's own request. Its tombstone holds
  no data about anyone and is removed when its 90 days end.

## Storage

Three tables in `conversions.sqlite`, beside the leads (docs/DATA-CONTRACT-PEOPLE.md):

| Table | Holds |
| --- | --- |
| `recorded_events` | one row per kept event: `raw` (the event as kept, JSON with sorted keys) and its projected columns `event_id`, `event_name`, `occurred_at`, `visitor_id`, `session_id`, `path`, `skald_vid`, `ip`, `email`; also `site`, `received_at`, and `ref`, the session's opaque id (`s` and the first 12 hex of SHA-256 of the site and the session ID). Unique by site and event ID |
| `recorded_tombstones` | `site`, `digest`, `expires_at`: a withdrawn visitor's keyed digest |
| `recorded_log` | `site`, `day`, `what`, `n`: per day, events `withdrawn`, `refused_consent` and `ignored_withdrawn`. Counts only |

Nothing else in Skald reads these tables.

## The second count

`audit_journeys.py` reads each event's raw JSON with its own code and checks:

- every projected column equals its raw value, and `ref` is its own hash of the session ID;
- every kept event says analytics `granted`, a known event name and schema version 1;
- one visitor per session ID;
- no event is kept for a visitor whose tombstone still stands;
- the period's figures (sessions that started in it, their visitors, pages read, actions, each
  event's count) equal the main code's (`queries.figures`).

It runs on every dashboard listing and once a day in run-daily (`audit_more.DAILY`
`recorded_journeys`). When anything differs, the period's figures are withheld: the dashboard
still lists the sessions, says the figures did not match their recount, and shows owners and
admins the first problems.

## Sessions and figures

A session is what the site sent under one session ID, from its first event to its last. It
belongs to the day (in the site's time zone) of its first event.

| Figure | Counts |
| --- | --- |
| sessions | sessions that started in the period |
| visitors | their distinct visitor IDs |
| pages read | their `page_view` events |
| actions | their events other than `session_started` and `page_view` |

These are the site's own figures. They are never added to the log's visits or visitors, and a
session is not a visit.

Each session shows: when, how long, its landing page, pages read, its trail of pages (at most
100), its actions with their labels (at most 50), its ending, whether the visitor had an earlier
session, the first touch (referrer host, `utm_source`, `utm_medium`, `utm_campaign`), and
whether it carried the script tag's visitor ID.

## Linking to the log's visits

Never by guess. A recorded session and a kept log visit (`visits`, kept only with
`privacy.keep_ips` on) are linked in two ways, and the dashboard says which:

- **visitor ID**: the session carries `skald_vid`, that ID was matched to the visit by the
  first-touch rule (`firsttouch.match_vids`, from the beacon's page views with visitor IDs on),
  and the session's events fall inside the visit's time, a minute either side;
- **address**: the session's kept address equals the visit's kept address, and the session
  falls inside the visit's time, a minute either side. Both sides are kept by the same
  `privacy.keep_ips` setting, so a shortened address matches a shortened one. An address
  removed with `skald forget` never links.

The visitor drawer uses both. The session drawer lists the visits linked by address.

## The page helper

The beacon helper serves it at `/traffic-js/journeys.js` (`skald/webapp/snippet/journeys.js`):

```html
<script src="https://stats.example.com/traffic-js/journeys.js"
        data-relay="/api/skald-journey" data-notice="v1" defer></script>
```

| Attribute | |
| --- | --- |
| `data-relay` | the site's own relay that signs and forwards (default `/api/skald-journey`) |
| `data-withdraw` | the relay's withdraw address (default: the relay plus `/withdraw`) |
| `data-notice` | the privacy notice's version, sent as `consent.notice_version`. A new version needs a new yes |
| `data-consent="granted"` | start at once: the site's own banner already said yes |

```js
window.skaldJourneys.consent(true);       // or false: stop, and forget the IDs in this browser
window.skaldJourneys.track("cta_click", {label: "Book a demo"});
window.skaldJourneys.track("form_sent", {label: "Contact", email: "person@example.com"});
window.skaldJourneys.withdraw();          // posts {visitor_id} to data-withdraw, then forgets
window.skaldJourneys.state();             // {consent, visitor_id, session_id, notice}
```

What it does:

- before consent it stores nothing and sends nothing; with Do Not Track or Global Privacy
  Control on it never records;
- after consent it keeps the visitor ID and the session in `localStorage`, sends
  `session_started` (with the first touch) and a `page_view` for each page, links inside a
  single-page app included;
- a session ends after 30 minutes without an event;
- it sends the script tag's visitor ID as `skald_vid` when the page has one;
- `track` takes the six action names only; a label or a path part that may name a person is
  left out (a path part becomes `-`), an email only on `form_sent`, `signup`, `booking_made`;
- on 429, a 5xx or a network failure it tries once more after 3 seconds, with the same body.

## The Next.js relay

`skald/kit/journeys/` holds an example for the Next.js App Router (its README says where
each file goes): `route.ts` (`app/api/skald-journey/route.ts`, one event),
`withdraw/route.ts` (`app/api/skald-journey/withdraw/route.ts`), `sign.ts` (shared signing) and
`SkaldJourneys.tsx` (a React component around the helper: `setJourneyConsent`,
`trackJourney`, `WithdrawJourneysLink`).

The event route drops any `ip` the browser sent, adds the visitor's address as its own server
saw it (the first `x-forwarded-for` hop, else `x-real-ip`), signs the body and forwards it. The
withdraw route takes `{visitor_id}` and builds the signed withdrawal itself. Both answer 403 to a
post from another origin, 413 over 16 KiB, 503 when their settings are missing, and otherwise
pass Skald's answer on. They wait at most 5 seconds and never log a body. Environment:

| Variable | |
| --- | --- |
| `SKALD_JOURNEY_URL` | the receiver, `https://<skald>/traffic-hooks/<site>/journey` |
| `SKALD_JOURNEY_SECRET` | the site's journey secret (server only, never in the page) |
| `SKALD_SITE_ORIGIN` | optional: the site's own origin, when a proxy makes the request's own URL another one. Only pages from it may post |
| `SKALD_JOURNEY_SEND_IP` | optional: `0` sends no visitor address at all |

## The agent job

The one-time agent line (Settings › Leads & tools › Recorded journeys › Connect › My AI agent)
carries the job `connect-journeys` (`kit/agent_jobs.py`). Its steps add the page helper and the
relay to the website's code, asking the person before each change.

The agent gets the secret from Skald, never from the chat: it posts
`{"tool": "journey", "make": true}` to the line's `<code>/hooksecret` (`kit/agent_hooks.py`),
and Skald answers two env lines once, `SKALD_JOURNEY_SECRET=...` and `SKALD_JOURNEY_URL=...`,
for the site's server settings. A line without the job is refused (403). When the site has a
secret already, Skald keeps it and answers 409; `"replace": true`, after the person agreed,
makes a new one (the old one stops working at once). A secret kept in the server's environment
answers 409. Each secret made is audited (never its value).

## Dashboard routes

Served by the refresh helper with `access.mode: sessions` (404 otherwise), for every site page
`/traffic/<site>/[<view>/]recorded...`:

| Route | Who | Answers |
| --- | --- | --- |
| `GET recorded?first=D&last=D` | every member who reads the site | the period's sessions (newest first, at most 500) and their figures, recounted; at most 400 days. Address and email for owners and admins only |
| `GET recorded/session?ref=R` | every member | one session, every event (`R`: `s` and 12 hex); owners and admins also get the log visits linked by address, and the view is audited (`recorded.session`) |
| `GET recorded/visit?day=D&seq=S` | owners and admins | the sessions linked to one kept log visit; audited (`recorded.visit`, a count, never a value) |
| `GET recorded/status` | owners and admins | connected or not (and where the secret lives), the receiver's, the withdraw and the helper's addresses, the last event received, the last 30 days' counts |
| `POST recorded/connect` | owners and admins, same origin, CSRF | make or rotate the secret, shown once; audited (`hook.secret`). 409 when the config reads it from the environment |

The address keys of the drawers and the dialog are in docs/ROUTES.md (`rj`, `rjc`).

## nginx

DEPLOY.md's sessions-mode blocks (and `docker/nginx.conf`, built from them):

- inside `location ^~ /traffic-hooks/`, a nested location for
  `^/traffic-hooks/<site>/journey(/withdraw)?/?$`: POST only, at most 16 KiB, its own
  `limit_req` zone `skald_journeys` (20 a second per address, burst 100), no access log;
- `/traffic-js/journeys.js` under `location ^~ /traffic-js/`;
- `recorded` and `recorded/*` in the per-site route location.

## Limits

| | |
| --- | --- |
| one event | 16 KiB |
| signature window | 300 s either way |
| an event's age | at most 7 days old, at most 5 minutes ahead |
| per site | `journeys.per_minute` 600 a minute, burst `journeys.burst` 200 |
| per visitor | `journeys.visitor_per_minute` 120 a minute |
| nginx, per sending address | 20 a second, burst 100 |
| a tombstone | 90 days |
| the dashboard's list | 500 sessions, a period of at most 400 days |
