# The event beacon: what happens inside a page

The access log sees every request, and nothing a reader does once the page
has loaded. A click on "Book a demo", a form started and not sent, a reader
who reached the bottom: none of them is a request. The beacon counts them,
on your own Skald server, without cookies and without any third-party code.

It is optional. A site that does not send beacons loses nothing; the log's
figures never depend on it.

## How it works

```
page  --navigator.sendBeacon('<Skald>/traffic-beacon', {...})-->  nginx  -->  beacon helper (127.0.0.1:8766)
                                                                    |               |
                                     the beacon log: time, status, site      the site's spool: one line per event
                                                                                    |
                                                         run-daily: collect -> verify -> audit -> history (400 days)
```

1. The page posts one small JSON body per event to `/traffic-beacon` beside
   the address it loaded `skald.js` from (below, "Where the tag posts"): with
   the plain tag, straight to the Skald server; with the first-party set-up,
   to the site's own server, which passes it on.
2. nginx rate-limits it, caps the body at 1 KB, writes one line to its own
   beacon log (time, status and the site's name; no address) and forwards it
   to the helper (`skald/beacon_server.py`).
3. The helper finds the site by the Origin (below, "Several sites"), checks
   the body and its own per-address limit,
   drops Do Not Track and Global Privacy Control, drops anything the
   classifier does not file under people (bots do not click), and appends
   the event to that site's spool for the day. The address is used in
   memory only.
4. run-daily counts yesterday's spool into history, checks it against the
   log's page views, and audits it by a second road (below).

## Several sites (2.9.0)

One install can count several sites: the first site (`config.yml`) and the
sites added from the dashboard or listed in a `sites:` file. Since 2.9.0 one
beacon helper takes events for all of them. Before, only the first site could
use the script tag.

- **The site is the Origin.** Each `POST /traffic-beacon` goes to the site
  its `Origin` header names. The first site takes the origins it is given
  (`beacon.origins`, Docker `SKALD_BEACON_ORIGINS`, `--origin`), and only
  those. Every other site takes `https://<each of its hosts>` (`site.hosts`,
  Settings > Sites), but only while the install has the script tag on, that
  is while the first site has an origin. An origin no site claims is refused
  (`403`). When two sites name the same origin, the first site wins.
- **Each site has its own spool.** The first site's is
  `<history folder>/beacon`; another site's is
  `<history folder>/sites/<name>/beacon`, where its daily run already
  reads. Each site's events are collected, verified and audited on their own.
- **Each site's 204s are counted apart.** The helper names the site in a
  response header, `X-Skald-Site`, and nginx writes it as the beacon log's
  third field (`$upstream_http_x_skald_site`, below). The audit compares
  each site's 204s with that site's spool. A line without the field
  (written before 2.9.0) is the first site's, the only one then. With the
  old two-field `log_format`, every line reads as the first site's, so
  another site's audit finds no 204s and withholds its days.
- **Visitor IDs per site.** `beacon.visitor_ids` is a site setting (below).
  `/traffic-js/skald.js` is served with the setting of the site whose page
  loads it, found by the `Referer` (scheme and host only). With no
  `Referer`, or one that is not a site's, it is served with the first site's
  setting. The answer carries `Vary: Referer`, so a cache keeps one copy per
  page. Whatever the file did, the helper keeps `v` only for a site that has
  visitor IDs on.
- **Read again every minute.** The list of sites, their hosts and their
  settings (visitor IDs, goals) are read again every 60 seconds. A site
  added from the dashboard takes events within a minute; no restart.

### Where the tag posts (2.24.0)

The plain tag needs **no change on the site's server**:

```html
<script src="https://skald.example.com/traffic-js/skald.js" data-site="example.net" defer></script>
```

`skald.js` posts beside the address it was loaded from: `.../traffic-js/skald.js`
gives `.../traffic-beacon` on the same origin, under the same folder. Loaded
from `https://skald.example.com/traffic-js/skald.js`, it posts to
`https://skald.example.com/traffic-beacon`; loaded from the page's own
`/traffic-js/skald.js` (the first-party set-up, below), it posts to the page's
own `/traffic-beacon`, as every version did. `data-endpoint` still wins. A copy
served from another folder (not `.../traffic-js/`) posts to the page's own
`/traffic-beacon`, as before. Before 2.24.0 the tag always posted to the page's
own origin, so the plain tag only worked when the site's server passed the path
on; without that, a Next.js site answered 308 or 405 and nothing arrived.

A direct post is cross-site, and the helper takes it safely:

- **The Origin is the proof.** It is taken only when its `Origin` is one of the
  site's (the map above: `https://<each host>`, or the first site's
  `beacon.origins`), and goes to that site's spool. Any other Origin, `null`, or
  none at all: `403`, as before.
- **Sec-Fetch-Site**, when the browser sends it, may be `same-origin`,
  `same-site` (www. posting to app. of the same domain) or `cross-site`, and
  only for an Origin in the map. `none` (not a page's post) is refused.
- **CORS for that one Origin.** The answer carries
  `Access-Control-Allow-Origin: <the page's origin>` and `Vary: Origin`, never
  `*` and never `Access-Control-Allow-Credentials`. The request is CORS-simple
  (`sendBeacon` with a `text/plain` Blob, or `fetch` with `keepalive` and a
  string body, no custom header), so the browser sends **no preflight**:
  `OPTIONS` stays `405`, and nginx needs no change. `fetch` sends no cookie to
  another origin by default, and Skald's own session cookie is
  `SameSite=Lax`, so a cross-site post never carries it.
- **Rate limits, the 1 KB body, validation, Do Not Track and the bot rule are
  the same** for both roads.
- **Counted once.** Each event is one request, by one road: the tag picks one
  address. A page with the tag twice (a first-party copy and Skald's, or one in
  Tag Manager and one in the HTML) runs only the first; the second copy stops
  at once (`skald.on`), so a page view is never sent twice. nginx logs each
  answer once, so the audit's two roads are unchanged.
- **The visitor's address.** A direct post comes from the visitor's own
  browser, so Skald's nginx sees the visitor's address (`X-Real-IP`): no trust
  setting is needed.
- **The ID stays first-party.** The visitor ID lives in the page's own
  `localStorage` (and, with `data-share-subdomains` or `beacon.share_subdomains`,
  a cookie on the page's own domain), exactly as before. Nothing is stored on Skald's domain.
- **The set-up Test checks the page.** While nothing has arrived, Settings'
  "Add the script tag" Test asks `POST <page>/sites/tagcheck`
  (`skald/tag_check.py`): Skald fetches the site's home page by the site
  check's safe rules (`site_fetch.py`), finds the tag, works out where it posts
  by the same rule, and says what is wrong: no tag, a host the site does not
  have, a script that does not load, a post address that answers 308, 404 or
  405 (probed with `POST` and `X-Skald-Probe: 1`, which the helper answers
  `200` with `X-Skald-Beacon` and counts nowhere, so nginx's 204 count is
  untouched), or a Content-Security-Policy whose `connect-src` leaves Skald out.

Ad blockers block third-party analytics addresses more often than a site's
own. Where that matters, use the first-party set-up below; it stays supported.

### First-party: pass the tag through the site's server

To keep the script and its events on the site's own domain, the page's server
forwards two paths to the Skald server: `/traffic-js/` and `/traffic-beacon`.
The browser then sees one origin, and the `Origin` the helper reads is the
site's own. With Caddy on the site's server (`www.example.net`; Skald at
`skald.example.com`):

```caddy
www.example.net {
  @skald path /traffic-beacon /traffic-js/*
  handle @skald {
    reverse_proxy https://skald.example.com {
      header_up Host {upstream_hostport}
    }
  }
  # ... the site itself
}
```

and in the page's `<head>`:

```html
<script src="/traffic-js/skald.js" data-site="example.net" defer></script>
```

Netlify, Vercel and Cloudflare do the same with a rewrite (docs/HOSTING.md).

The Skald server then sees the site's server, not the visitor. Its nginx must
take the visitor's address from that server's `X-Forwarded-For`, and only
from that server:

```nginx
set_real_ip_from 203.0.113.10;     # the site's server
real_ip_header X-Forwarded-For;
real_ip_recursive on;
```

In Docker: `SKALD_TRUSTED_PROXIES=203.0.113.10` (docs/HOSTING.md). Without
it, every visitor has the site server's address: one rate limit for all of
them, and our own traffic is not told apart. The address is used for those
two things only, in memory, and never stored.

## What a beacon may say

One JSON object, at most 1 KB, with only these fields:

| field | what | rule |
|---|---|---|
| `e` | the event | one of the list below, else refused |
| `p` | the page's path, `location.pathname` | starts with `/`, no query, no fragment, else refused |
| `id` | which button or form: `signup_hero`, `demo_header`; the destination host for `outbound_click` | lowercase token, 60 characters; anything else dropped |
| `r` | the visit's referring host | a host name; anything else dropped |
| `u` | the visit's `utm_source` | lowercase token; anything else dropped |
| `vw` | viewport width bucket | `xs` <480, `sm` <768, `md` <1024, `lg` <1440, `xl` |
| `t` | seconds from opening the page to the event | 0 to 86400; an offset, never a clock time |
| `v` | the anonymous visitor ID (below) | `skv_` and 22 base64url characters; anything else dropped. Kept only with `beacon.visitor_ids: true` |

Any other field - an address, a user id, an email, free text - and the beacon is
refused. The helper answers `204` when it counted the event, `202` when it
took it and kept nothing (Do Not Track, GPC, a bot, a `page_view` when
neither beacon-only mode nor visitor IDs are on), `400` for a bad body,
`403` for a foreign or missing Origin (or a site made by sign-up whose domain
is not verified yet), `411` with no length, `413` over 1 KB
and `429` over the limit. Until `beacon.origins` names an origin, the beacon
answers `404`. Each answer to a post carries `X-Skald-Site: <site>` when the
helper knew the site (2.9.0), and, for an Origin in the map,
`Access-Control-Allow-Origin: <that origin>` with `Vary: Origin` (2.24.0). A
post with `X-Skald-Probe: 1` (the set-up Test's page check) answers `200` with
`X-Skald-Beacon: 1` before any rule, reads no body and counts nothing.

### Events

| event | when the page sends it | `id` |
|---|---|---|
| `cta_click` | a call-to-action button or link is clicked | which one, `<target>_<place>` |
| `book_demo_open` | the demo booking opens | the button's place |
| `demo_booked` | the booking tool confirms a time | the button's place |
| `signup_start` | the first field of the sign-up form is used | `signup` |
| `signup_submit` | the sign-up form is sent successfully | `signup` |
| `contact_submit` | the contact form is sent successfully | `contact` |
| `waitlist_submit` | the early-access form is sent successfully | `early_access` |
| `outbound_click` | a link to another site is clicked | the destination host |
| `scroll_75` | the reader reaches 75% of the page, once per page | - |
| `copy_text` | text is copied, once per page (never the text) | - |
| `404_view` | the not-found page is shown | - |
| `page_view` | a page loads, a client-side navigation (`pushState`, `replaceState`, back and forward), or a page restored from the back-forward cache (`pageshow` with `persisted`); counted in beacon-only mode or with visitor IDs on. Otherwise (since 2.10.1) kept only as proof the page was drawn: path and time in `opens-<day>.jsonl`, read by the render test, never counted as an event | - |
| `form_start` | a field of a form is first used, once per form per page | the form's `id` or `name` |
| `form_submit` | a form is submitted | the form's `id` or `name` |
| `calendly_open` | a Calendly embed shows its page | - |
| `calendly_time_selected` | a time is chosen in a Calendly embed | - |
| `calendly_booked` | a Calendly embed confirms a booking | - |
| `cal_open`, `cal_booked` | a Cal.com embed is ready / confirms a booking | - |
| `hubspot_meeting_booked` | a HubSpot meetings embed confirms a booking | - |
| `tel_click`, `mailto_click` | a `tel:` / `mailto:` link is clicked (never the number or address) | - |

`skald.js` (docs/INTEGRATIONS.md, "The script tag") sends every event above by
itself except `book_demo_open` and `demo_booked` (`beacon.CODE_ONLY`): only the
site's own code sends those (`skald('track', 'demo_booked')` or its own
beacon), and the Events tab (Leads & sales > Events) says so. The tag's own rules: `cta_click` for
`data-skald-cta="<name>"`; `signup_*` for a form with `data-skald="signup"`;
`contact_submit` / `waitlist_submit` when a form with `data-skald="contact"` /
`"waitlist"` is submitted (its start is `form_start`); `scroll_75` and
`copy_text` once per page view; `404_view` once per page view when the page
holds an element with `data-skald="404"`. tests/test_snippet.py fails when an
event is neither sent by the tag nor in `CODE_ONLY`. A site with its own
code can send any of them too.

Each event is stored with the visit's source type, worked out on the server
from `r` and `u` by the same rules as a reader's source in the log
(`dimensions.source_type`): AI assistant, Search engine, Social media,
Email, Other website, This site, Tagged link, Direct or unknown. Events from
an AI citation also keep the assistant's name.

## Visitor IDs (off by default)

`beacon.visitor_ids` is set per site (since 2.9.0: a site setting, admin,
default off; docs/SETTINGS.md). With `beacon.visitor_ids: true` the beacon
also keeps `v`, a random ID the
browser made (`skv_` and 16 random bytes in base64url; no name, email or
fingerprint). It lets Skald follow one browser's anonymous journey to a
conversion. Off, the
helper drops `v` before anything is written, `page_view` is not kept
(unless beacon-only mode is on), and `/traffic-js/skald.js` is served so
that the browser makes no ID at all: today's behaviour, unchanged.

On, for people's events that carry an ID (never our own, never bots), the
helper also writes to `conversions.sqlite`, right after the spool line:

| event | goes to |
|---|---|
| `page_view` | `journeys`: ID, time, path, the visit's source type and referring host (`via`, since conversions schema 6) |
| `form_start` / `form_submit`, `contact_submit` | conversion `contact`, started / completed |
| `signup_start` / `signup_submit` | `signup`, started / completed |
| `waitlist_submit` | `waitlist`, completed |
| `calendly_open`, `calendly_time_selected`, `cal_open`, `book_demo_open` | `demo`, started |
| `calendly_booked`, `cal_booked`, `hubspot_meeting_booked`, `demo_booked` | `demo`, completed |
| `tel_click` / `mailto_click` / `cta_click` | `call` / `email` / `cta`, completed (the page sees nothing after a click) |
| anything else | nothing |

- One conversion per (ID, action, stage) within 30 minutes of the last one
  kept: a second focus or a reload is not a second start. The spool still
  has every event.
- Country from the request's address (the DB-IP file, `conversions.country_db`)
  and device from its user agent, as for a hook; then both are dropped.
  Landing is the first page of the visit as the journeys know it, else NULL.
- **Abandoned** is worked out when a report asks, never stored: a start with
  no completed (or paid) for the same ID and action within
  `conversions.abandon_hours` (default 24).
- Journeys are deleted after `journeys.vid_days` (default 30) unless the ID
  converted (then kept as long as the conversion); `skald conversions prune`.
- `skald conversions forget --vid skv_...` deletes the ID's journeys and
  conversions and takes `v` out of its beacon spool lines (the lines stay:
  the event audit counts them against nginx's log).
- The second count (`audit_conversions.py`) reads the beacon spool by its
  own road and recounts these conversions per day; a day that disagrees is
  withheld (docs/INTEGRATIONS.md, "The second count").
- A failed write to `conversions.sqlite` is counted (`conversion_errors` in
  the day's counters); the spool line stands, so the second count withholds
  that day rather than show a short figure.

A visitor ID is a browser, not a person: one person on two devices is two
IDs, and clearing storage makes a new one. Skald never links a new ID to an
old one, and no figure matches by address. (The 2.4.0 person search, apart
from the figures, shows the visits kept with an address and the visits that
sent a form at a lead's time, said as not certain: DATA-CONTRACT-PEOPLE.md.)

### Sharing the ID across subdomains, switched on in Skald (2.27)

`data-share-subdomains="true"` on the tag keeps the ID in a first-party cookie
`skald_vid` on the registrable domain too, so `www.` and `app.` share it
(docs/INTEGRATIONS.md, "Subdomains"). Where the site's developer cannot change
the tag, an admin switches the same thing on in Skald instead:
`beacon.share_subdomains` (a site setting, admin, default off; Settings > Sites >
Script tag, or `skald settings set example.com beacon.share_subdomains true`).
The tag stays `<script src=".../traffic-js/skald.js" data-site="example.com" defer>`.

- **The beacon's answer says it.** The helper's answer to a `page_view` from
  the site's own Origin carries `X-Skald-Sh: 1` (on) or `X-Skald-Sh: 0` (off),
  with `Access-Control-Expose-Headers: X-Skald-Sh` beside the CORS header it
  already sends, so the page can read it. Nothing else changes: the status is
  the one it always was (204 counted, 202 not), the body stays empty (a 204
  has none, and 204 is what nginx's beacon log counts), and no other answer
  carries it: another event, a refusal, the probe, another Origin.
- **skald.js asks once a day.** Without the attribute and without a fresh
  answer, the first `page_view` of a page load goes by `fetch` (keepalive,
  `credentials: "omit"`, the same text/plain body, so still no preflight)
  instead of `sendBeacon`, and the tag reads the header. It keeps the answer in
  `localStorage` as `skald.sh` = `1|<epoch ms>` or `0|<epoch ms>`; for 24 hours
  that flag decides at start, with no ask. Older, it asks again. On `1` it
  writes the cookie at once; while it does not know yet, it takes a shared ID
  a sibling subdomain already set. On `0` after a `1`, it clears the cookie
  (`max-age=0`), so switching the setting off stops the sharing within a day.
  No answer header (an older Skald) counts as `0`; a refusal (429, 403) or a
  blocked post keeps nothing and asks again on the next load.
- **The attribute still wins**, with no ask. Do Not Track, Global Privacy
  Control, `data-consent="required"` before consent, and visitor IDs off all
  behave as before: no ID, no cookie, no ask, no flag.
- Settings > Integrations says, under the tag, when sharing is on in Skald, and
  the privacy notice's cookie line is then plain, without "[Keep this line only
  if...]" (people/notice.py).

## What is kept

- The spool, `<history folder>/beacon/<YYYY-MM-DD>.jsonl` for the first
  site and `<history folder>/sites/<name>/beacon/<YYYY-MM-DD>.jsonl` for
  each other site: one line per counted event - time, the fields above, people or ours, the source type,
  and `v` only with visitor IDs on. No address, no user agent. Kept 400
  days, like the counts.
- With visitor IDs on: journeys and conversions in `conversions.sqlite`
  (above; docs/INTEGRATIONS.md "What is kept").
- `stats-<day>.json` beside it: the helper's counters (counted, refused by
  reason, declined, not people).
- In history: `event_counts` (day, event, label, path, source, n) for
  people, and `event_days` (state, our own events, events by assistant,
  anomalies, the audit). 400 days (`beacon.keep_days`).

Our own addresses' events are kept apart as "ours", exactly as our own
requests are kept apart in the log, and never added to people.

## Verify and audit

**Verify** (at collect). An event comes from a page someone read, so:

- per path, events (all but `404_view`) may not exceed 10 x that page's
  people views or visits in the log + 20. Past it, the path is recorded as an
  anomaly and shown.
- `404_view` per path may not exceed 3 x the people 404s of that path + 10.
- the day's events may not exceed 10 x the people page views + 50. Past it,
  something other than readers is posting: the day's events are withheld.

**Audit** (after collect, by a separate road). The spool is recounted from
its raw text with a pattern, not the JSON reader collect used, and compared
with history per event; and the site's 204s in nginx's beacon log are
counted for the same local day and compared with the spool's lines. Only events within
2 seconds of midnight may differ (two clocks, one each side). A mismatch
withholds the day's events.
The same recount reads each line's source (`s`) with its own pattern and
compares people's events by event and source. A mismatch there withholds
only the by-source figures: the day keeps its totals, its rows lose their
source, and goals leave the day out.

`skald events` shows today's spool; `skald events --day D --collect` counts
and audits a day again; `--audit` audits only.

## Setting it up

### config.yml

```yaml
beacon:
  enabled: true                 # run-daily collects and audits, events.json is filled
  origins:
    - https://www.your-site.org # the first site's page origins; other sites use their hosts
  log: /var/log/nginx/skald-beacon.log   # nginx's beacon log, for the audit
  # per_minute: 60              # per address; burst: 20
  # site_per_second: 20         # everyone together
  # keep_days: 400
  # spool: /var/lib/skald/beacon
  # page_views: false           # beacon-only mode
  # visitor_ids: false          # keep the anonymous visitor ID (journeys, conversions);
  #                             # with accounts, set per site (docs/SETTINGS.md)
  # goals: [demo_booked, signup_submit]   # events per 100 visits by source (Leads & sales > Events);
  #                             # with accounts, Settings > Sites > Goals sets it per site
```

### The helper

`install.sh` (and, since 2.2.2, `skald upgrade`) already runs it, because it also
receives the signed tool hooks. Until `beacon.origins` names the site's own address it
takes hooks only, and the beacon answers 404. By hand:

```sh
cp systemd/skald-beacon.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now skald-beacon
```

### nginx

At the `http` level (a `conf.d` file, or the top of the site's file):

```nginx
# Skald event beacon: 60 a minute per address, bursts of 30; a log with no address in it.
limit_req_zone $binary_remote_addr zone=skald_beacon:1m rate=60r/m;
log_format skald_beacon '$time_iso8601 $status $upstream_http_x_skald_site';
```

In the site's HTTPS `server { }`:

```nginx
location = /traffic-beacon {
  limit_except POST { deny all; }
  limit_req zone=skald_beacon burst=30 nodelay;
  limit_req_status 429;
  client_max_body_size 1k;
  access_log /var/log/nginx/skald-beacon.log skald_beacon;
  add_header Cache-Control "no-store" always;
  add_header X-Robots-Tag "noindex" always;
  proxy_pass http://127.0.0.1:8766;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
}
```

The plain tag posts here from the site's pages directly (cross-site): this
location needs nothing more for it. The helper answers the CORS headers itself,
and the request is CORS-simple, so there is no `OPTIONS` preflight to allow.

The location's own `access_log` keeps the beacon posts out of the main
access log, so they are never counted as requests or as a visit's form
posts. Its third field, `$upstream_http_x_skald_site`, is the site the helper
named (`-` when it named none); the audit counts each site's 204s by it. The beacon log rotates with the other nginx logs; the audit reads
the current file and the two before it.

### The website

Send from the page, only on the live hosts, never when the browser says Do
Not Track or GPC:

```js
function skald(e, id) {
  if (navigator.doNotTrack === "1" || navigator.globalPrivacyControl) return;
  const b = { e, p: location.pathname, t: Math.round(performance.now() / 1000) };
  if (id) b.id = id;
  navigator.sendBeacon("/traffic-beacon", new Blob([JSON.stringify(b)], { type: "text/plain" }));
}
```

`text/plain` keeps the request simple: no preflight, and the helper reads
the body as JSON whatever the type says.

## Beacon-only mode: a site with no server log

Some sites cannot give Skald a log: a static host, a platform that keeps
its logs to itself. For them, `beacon/skald.js` (under 1 KB) posts a
`page_view` on load, on every client-side navigation (`pushState`,
`replaceState`, back and forward) and when a page is restored from the
back-forward cache, with the same fields and the same rules: no cookie, no storage, nothing when Do Not Track
or GPC is on. The full snippet, `/traffic-js/skald.js` (docs/INTEGRATIONS.md,
"The script tag"), sends page views the same way and tracks forms, links
and booking embeds too; with visitor IDs off it stores nothing either.

These page openings are the script's own events, a separate road: they are
never added to the people or page views counted from a server log (a Next.js
navigation counts there only from the log line itself, CLASSIFICATION.md,
"What decides a page view"). Without a log, in beacon-only mode, they are the
only page views there are.

```html
<script src="/skald.js" defer></script>
<!-- or post somewhere else on the same origin: data-endpoint="/stats/beacon" -->
```

It also exposes `window.skald(event, id)` for the events above.

What it needs:

- `beacon.page_views: true`, or `page_view` is refused.
- The beacon must reach the helper from the site's own origin: a rewrite on
  the host (`/traffic-beacon` proxied to the Skald server; Netlify, Vercel
  and Cloudflare all can) or a path on a server you run. A cross-site post
  is refused by design.
- Behind such a proxy the address nginx sees is the proxy's. Tell nginx
  the real one (`set_real_ip_from <proxy ranges>; real_ip_header
  X-Forwarded-For;`), or the per-address limit becomes one limit for
  everyone.

What it is not: a log. Bots and AI assistants do not run scripts, so in
beacon-only mode Skald sees people's page views and events and nothing else,
and the five groups, the audit against the log and the bounds against page
views do not apply. The page views appear under Events, not in the log's
figures. With a log, use the log; skald.js is not needed and is not loaded.

## Privacy

What leaves the browser is listed above and nothing else. What is kept has
no address, no user agent and no text a person typed, and no identifier
unless the site has `beacon.visitor_ids` on (then a random per-browser ID,
above; that site's privacy notice must say so, and in some places it needs
consent first: `data-consent="required"`, with the consent banner calling
`skald('consent', true)`). The
address is used for the rate limit and to recognise our own traffic, in the
helper's memory only, and is not in the beacon log. A suggested sentence for
a privacy page: "We count anonymous button clicks and form steps on our own
server, without cookies."

The beacon is apart from what the log keeps. Since 2.4.0 a site may keep each
reader's visit with its address and user agent (`privacy.keep_ips`: on for a
new install, off for one upgraded from before 2.4.0; SETTINGS.md). The beacon
spool never holds an address, whatever that setting says.
