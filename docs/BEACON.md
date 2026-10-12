# The event beacon: what happens inside a page

The access log sees every request, and nothing a reader does once the page
has loaded. A click on "Book a demo", a form started and not sent, a reader
who reached the bottom: none of them is a request. The beacon counts them,
on the site's own server, without cookies and without any third-party code.

It is optional. A site that does not send beacons loses nothing; the log's
figures never depend on it.

## How it works

```
page  --navigator.sendBeacon('/traffic-beacon', {...})-->  nginx  -->  beacon helper (127.0.0.1:8766)
                                                             |               |
                                     the beacon log: time, status      the day's spool: one line per event
                                                                             |
                                                  run-daily: collect -> verify -> audit -> history (400 days)
```

1. The page posts one small JSON body per event to its own origin.
2. nginx rate-limits it, caps the body at 1 KB, writes one line to its own
   beacon log (time and status only, no address) and forwards it to the
   helper (`skald/beacon_server.py`).
3. The helper checks the Origin, the body and its own per-address limit,
   drops Do Not Track and Global Privacy Control, drops anything the
   classifier does not file under people (bots do not click), and appends
   the event to the day's spool. The address is used in memory only.
4. run-daily counts yesterday's spool into history, checks it against the
   log's page views, and audits it by a second road (below).

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
`403` for a foreign or missing Origin, `413` over 1 KB and `429` over the
limit.

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
| `page_view` | a page loads, or a client-side navigation; counted in beacon-only mode or with visitor IDs on | - |
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
beacon), and the Events page says so. The tag's own rules: `cta_click` for
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

With `beacon.visitor_ids: true` the beacon also keeps `v`, a random ID the
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
| `page_view` | `journeys`: ID, time, path, the visit's source type |
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
old one, and never matches by address.

## What is kept

- The spool, `<history folder>/beacon/<YYYY-MM-DD>.jsonl`: one line per
  counted event - time, the fields above, people or ours, the source type,
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
with history per event; and the 204s in nginx's beacon log are counted for
the same local day and compared with the spool's lines. Only events within
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
    - https://www.your-site.org # the page origins allowed to post
  log: /var/log/nginx/skald-beacon.log   # nginx's beacon log, for the audit
  # per_minute: 60              # per address; burst: 20
  # site_per_second: 20         # everyone together
  # keep_days: 400
  # spool: /var/lib/skald/beacon
  # page_views: false           # beacon-only mode
  # visitor_ids: false          # keep the anonymous visitor ID (journeys, conversions)
  # goals: [demo_booked, signup_submit]   # events per 100 visits by source (Events tab);
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
log_format skald_beacon '$time_iso8601 $status';
```

In the site's HTTPS `server { }`:

```nginx
location = /traffic-beacon {
  limit_except POST { deny all; }
  limit_req zone=skald_beacon burst=30 nodelay;
  client_max_body_size 1k;
  access_log /var/log/nginx/skald-beacon.log skald_beacon;
  add_header Cache-Control "no-store" always;
  add_header X-Robots-Tag "noindex" always;
  proxy_pass http://127.0.0.1:8766;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
}
```

The location's own `access_log` keeps the beacon posts out of the main
access log, so they are never counted as requests or as a visit's form
posts. The beacon log rotates with the other nginx logs; the audit reads
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
`page_view` on load and on every client-side navigation, with the same
fields and the same rules: no cookie, no storage, nothing when Do Not Track
or GPC is on. The full snippet, `/traffic-js/skald.js` (docs/INTEGRATIONS.md,
"The script tag"), sends page views the same way and tracks forms, links
and booking embeds too; with visitor IDs off it stores nothing either.

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
unless `beacon.visitor_ids` is on (then a random per-browser ID, above;
the site's privacy notice must say so, and in some places it needs consent
first: `data-consent="required"`). The
address is used for the rate limit and to recognise our own traffic, in the
helper's memory only, and is not in the beacon log. A suggested sentence for
a privacy page: "We count anonymous button clicks and form steps on our own
server, without cookies."
