# Integrations: incoming hooks

Skald counts conversions (a booking, a form, a trial, a payment) that the
site's own server and the tools it uses push to it. Each push is a signed
`POST` to the site's own address. Skald checks the signature, keeps a raw
copy in its spool, and records the conversion once. It also reads the
site's own lead database, when it has one (below, "Leads from the lead
database"), and the page's script tag.

**One name per action**, whatever reports it:

| Action | From |
| --- | --- |
| `demo` | Calendly, Cal.com, HubSpot meetings, the page's booking events (`calendly_*`, `cal_*`, `book_demo_open`, `demo_booked`), the lead DB's `demo_opened` / `demo_booked` |
| `paid` | Stripe (a checkout paid; one paid later by a delayed method is `started` first) |
| `contact` | forms: the page's `form_*` / `contact_submit`, Typeform, HubSpot contacts and workflows, the lead DB's `contact` |
| `signup`, `waitlist` | the page's sign-up and early-access events, the lead DB |
| `deal` | HubSpot deals (`won` when one moves to closedwon) |

A `lead` or `json` hook may name any short action; the older names
`booking`, `meeting`, `demo_booked` are read as `demo`, `checkout` and
`payment` as `paid`, `form` as `contact`. The conversions file (schema 2)
renamed its existing rows the same way when it was upgraded, keeping a copy
of the old file beside it (`conversions.sqlite.v1.bak`).

Code: `skald/conversions/` (receiver `hooks.py`, one adapter per tool in
`adapters/`), second count `skald/audit_conversions.py`.

## The script tag

One line in every page's `<head>` gives Skald page views, form steps,
`tel:`/`mailto:`/outbound clicks and Calendly, Cal.com and HubSpot meeting
embeds, each with an anonymous visitor ID when the install keeps them:

```html
<script src="/traffic-js/skald.js" data-site="example.com" defer></script>
```

The file is under 6 KB (the test's budget; 5 KB until it sent every event
and adopted IDs from other domains), plain JavaScript, served by the beacon helper
(`GET /traffic-js/skald.js`, an ETag and a day's cache) from the site's own
origin, and posts to the site's own `/traffic-beacon` (docs/BEACON.md). No
third-party code, no `eval`, never a field's value.

nginx, in the site's HTTPS `server { }` beside `/traffic-beacon`:

```nginx
location = /traffic-js/skald.js {
  limit_except GET { deny all; }
  proxy_pass http://127.0.0.1:8766;
  proxy_set_header Host $host;
}
```

### Options (attributes on the tag)

| attribute | default | what |
| --- | --- | --- |
| `data-site` | - | the site's own domain, `example.com`; also the shared cookie's domain (below) |
| `data-endpoint` | `/traffic-beacon` | where to post, on the same origin |
| `data-consent="required"` | not required | send nothing and store nothing until the page calls `skald('consent', true)` |
| `data-share-subdomains="true"` | off | keep the ID in a first-party cookie too, so `www.` and `app.` share it |
| `data-link-domains` | - | comma list of other domains you own (`app.example.net, shop.example.org`): links to them get `?skv=<id>` when clicked, and an `skv` arriving from them is adopted (below) |
| `data-accept-id="true"` | off | adopt a valid `?skv=<id>` whatever the referrer (below) |

### What it does by itself

- `page_view` on load and on each client-side navigation (`history.pushState`,
  `replaceState`, back and forward), once per path.
- `form_start` the first time a field of a form gets focus (once per form per
  page) and `form_submit` on submit, with the form's `id` or `name` only.
  `data-skald="signup"` on a form sends `signup_start` / `signup_submit`
  instead; `data-skald="contact"` / `"waitlist"` send `contact_submit` /
  `waitlist_submit` on submit (`form_start` on start); `data-skald="off"`
  and `role="search"` forms are left alone. A
  form whose own code refuses the submit still sends `form_submit`; send it
  yourself (`skald('track', 'form_submit', {id: 'contact'})`) after success
  if that matters.
- `tel_click`, `mailto_click` (never the number or address), `outbound_click`
  with the destination host, `cta_click` for any element (or its parent) with
  `data-skald-cta="<name>"`.
- `scroll_75` once per page view when the window's bottom reaches 75% of the
  document's height; `copy_text` once per page view on a copy (never the
  text); `404_view` once per page view when an element with
  `data-skald="404"` is on the page (checked 50 ms after each page view and
  after DOM changes, so a single-page app's not-found route counts too).
- Never by itself: `book_demo_open`, `demo_booked` (`beacon.CODE_ONLY`); send
  them from the site's code.
- Calendly embeds: `calendly_open`, `calendly_time_selected`, `calendly_booked`
  from Calendly's window messages, only from `https://calendly.com`. Cal.com:
  `cal_open` (`linkReady`) and `cal_booked` (`bookingSuccessful`), only from
  `https://app.cal.com`. HubSpot meetings: `hubspot_meeting_booked`, only
  from `https://meetings.hubspot.com` (and its regional `meetings-<x>` hosts).
- The visitor ID goes to Calendly as `utm_content=<id>` on Calendly iframes,
  inline widgets (`data-url`) and links, unless the URL already has a
  `utm_content`; Calendly returns it in its webhook, so the booking joins the
  journey. Other domains get `skv=<id>` (`data-link-domains`).

### The ID across your own domains (`skv`)

Links to a domain in `data-link-domains` get `?skv=<id>` when clicked. The
tag on the other domain adopts it when the page's address has `skv` matching
`skv_` + 22 base64url characters and either the tag has
`data-accept-id="true"` or the referrer's host is (under) one of its own
`data-link-domains`. Adopting means: `skv` is taken out of the address at
once with `history.replaceState` (no page view for it; the path, other
parameters and the fragment stay), and the ID becomes the visitor's ID,
winning over one this browser already had there (and over the shared
cookie), stored as usual. With `data-consent="required"` it is held in
memory and stored only on `skald('consent', true)`; `skald('consent',
false)` forgets it. With visitor IDs off the address is still cleaned and
nothing is kept. Any other `skv` (no listed referrer, no opt-in, not an ID)
is ignored and left in the address. Do Not Track or GPC: the tag does
nothing, so `skv` stays.

### The API

```js
skald('track', 'cta_click', {id: 'pricing_top'});  // any event docs/BEACON.md lists
skald('consent', true);                            // or false: stop, forget the ID here
skald('id');                                       // the visitor ID, or null
```

To call it before the file has loaded, put this before the tag:

```html
<script>window.skald=window.skald||function(){(skald.q=skald.q||[]).push(arguments)}</script>
```

### Privacy and consent

- **Do Not Track or Global Privacy Control:** nothing at all. No ID, no
  storage, no beacon.
- **Visitor IDs are off by default** (`beacon.visitor_ids: false`): the
  helper then serves the file so that it makes no ID, and drops any `v`
  it is sent. Turn them on only when the site's privacy notice says so.
- With IDs on, the ID (`skv_` + 16 random bytes) is kept in `localStorage`
  (`skald.vid`), the visit's source in `sessionStorage` (`skald.src`), and
  with `data-share-subdomains="true"` in a cookie `skald_vid` (400 days,
  `SameSite=Lax; Secure`).
- Where consent is needed first (the EU, Quebec's Law 25, often the rest of
  Canada), use `data-consent="required"` and call `skald('consent', true)`
  from your consent banner on every page once the visitor agrees.
  `skald('consent', false)` deletes the ID, the cookie and the stored source.

### Subdomains: the cookie's domain, and its limit

With `data-share-subdomains="true"` the cookie is set on the registrable
domain. When the page's host is `data-site` or under it, that is
`data-site`. Otherwise the snippet guesses: the last two labels
(`www.example.com` -> `example.com`), or three when the last two look like
a two-part country suffix (`co.uk`, `com.au`, `org.nz`: `co`, `com`, `net`,
`org`, `gov`, `ac` or `edu`, then two letters). It does not carry the public
suffix list, so it guesses wrong for other suffixes (`example.pvt.k12.ma.us`)
and for shared hosting (`yoursite.vercel.app` gives `vercel.app`, which
browsers refuse). Set `data-site` to your own domain and the guess is not
used. A refused cookie only means the subdomains do not share the ID; the
`localStorage` copy still works.

### A site with its own code

A site that already sends beacons from its own code (docs/BEACON.md, "The
website") does not need the snippet:

1. Make one ID per browser, in the same shape, and keep it:

   ```js
   function skaldId() {
     let id = localStorage.getItem("skald.vid");
     if (!/^skv_[A-Za-z0-9_-]{22}$/.test(id || "")) {
       const b = crypto.getRandomValues(new Uint8Array(16));
       id = "skv_" + btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
       localStorage.setItem("skald.vid", id);
     }
     return id;
   }
   ```

   Only when Do Not Track and GPC are off, and after consent where needed.
   A 30-minute session ID is not a visitor ID: it would split one browser's
   journey into many, so make this one apart from it.
2. Send it as `v` with the events you already send (`book_demo_open`,
   `demo_booked`, `contact_submit`, ...) and add `page_view` on each page.
3. Add `utm_content=<id>` to the Calendly embed URL when your UTM fields do
   not already fill `utm_content`.
4. Pass the same ID as `vid` in the signed `lead` hook (below) when a lead is
   made, so the server's record joins the browser's journey.

Leads need no hook when Skald reads them from the website's own lead
database (next section), which it already reads for the Leads tab.

## Leads from the lead database

When `leads.db` names the website's lead database (the Leads tab's), every
lead there also becomes a conversion, with no change to the website
(`conversions/from_leads.py`; off with `conversions.from_leads: false`):

| Lead | Conversion |
| --- | --- |
| `id` | `external_ref`; tool `site` |
| `type` | `demo_booked` -> `demo` completed, `demo_opened` -> `demo` started, `contact`, `signup`, `waitlist` -> completed; another type is its own action |
| `status` | `new`, `contacted`, `qualified`: completed only; `won` / `lost`: a second row with that stage; `spam`, `duplicate`: no row at all |
| `created_at` | `at` (every row of the lead) |
| `first_touch`, `last_touch` | source (last touch), first source, campaign, landing page, the first touch's time |
| `visits` | visits before, when present |
| `ip_country` | country, only when it holds two letters |
| `session_id` | the visitor ID, when it has the shape of one (8 to 80 letters, digits, `_.:-`) |

The file is opened read-only and only those columns are read; names and
emails only when the site's `conversions.identity` is `full` (the default
since 2.4.0, except on an install upgraded from before it: see Privacy,
below). Every live run (2 minutes) reads the leads changed since the last
one (by `updated_at`); run-daily reads them all and removes the rows of
leads deleted from the CMS. A row a sync takes away (the lead deleted,
marked spam or duplicate, or changed) is first copied whole into the
`removed` table, with when and why (`store.remove`): the Conversions page
lists it under "Removed". Nothing disappears unseen; only `forget` deletes.
A status the team changes later changes the lead's day ("as known").
The second count reads the same database by its own SQL
(`audit_conversions.recount_leads`). Device is never known here (NULL).

## The address

```
POST https://www.example.com/traffic-hooks/<site>/<tool>
```

- `<site>` is the site's name in Skald's config (`site.name`, e.g. `example.com`).
- `<tool>` is one of:

| tool | for | signature header |
| --- | --- | --- |
| `lead` | the site's own server or CMS: "a lead was made" | `X-Skald-Signature` (Skald's scheme, below) |
| `json` | Zapier, Make, n8n, any script | `X-Skald-Signature` (Skald's scheme) |
| `calendly` | Calendly webhook subscriptions | `Calendly-Webhook-Signature` |
| `calcom` | Cal.com webhooks | `X-Cal-Signature-256` |
| `stripe` | Stripe Checkout | `Stripe-Signature` |
| `typeform` | Typeform webhooks | `Typeform-Signature` |
| `hubspot` | HubSpot app webhooks and workflow webhooks | `X-HubSpot-Signature-v3` |

A hook only exists once it has a secret. Without one the address answers 404.

## Set up a hook

Nothing to switch on first: the receiver runs on every install (2.2.2; see
[nginx](#nginx) below). The commands below are `sudo skald ...` on a
server set up with install.sh, and `docker exec skald skald ...` on
Docker.

1. Make its secret on the server (it is printed once, and kept 0600 in
   `secrets.json` beside the history), or on the Integrations page (below).
   It prints the hook's address too, from `hooks.public_url` or
   `access.base_url` (Docker: `SKALD_BASE_URL`):

   ```sh
   sudo skald hooks secret example.com calendly
   ```

   When the tool makes the secret itself (Stripe's `whsec_...`), give it to
   Skald from standard input, so it never lands in the shell history:

   ```sh
   sudo skald hooks secret example.com stripe --value -
   ```

   Or keep the secret in an environment variable and name it in the config
   (nested form needs PyYAML; the flat form works with the small parser):

   ```yaml
   hooks:
     example.com/calendly: SKALD_HOOK_CALENDLY        # flat
     # example.com:
     #   calendly: {secret_env: SKALD_HOOK_CALENDLY}  # nested
   ```

2. Give the address and the secret to the tool (each tool's steps below).
3. Send a test: `skald hooks test example.com calendly` posts a signed
   sample to the local receiver. A test is checked and read, logged as
   `test`, and never kept or counted. It prints what a real delivery would
   keep: the action, stage, time, source, country and device, the visitor ID
   or "none" (dropped when the site's visitor IDs are off, as the real path
   drops it), a time without an offset read in the site's zone, and
   "ignored: other event type" when the site keeps other Calendly or Cal.com
   event types only (below).
4. `skald hooks list` shows each hook, where its secret lives (never the
   secret) and its last deliveries. `skald doctor` says, per hook:
   needs a secret, never received, ready (a test passed), or last received
   N ago, and what to fix when the last delivery was refused.

### From the same server (a CDN in front)

When the site's own backend runs on the same server as Skald and the site
sits behind Cloudflare or another proxy, post to Skald's local address, not
the public one: Cloudflare can refuse a server posting to its own public
address (403, error 1010, a bot check). Docker: the port you published,
`http://127.0.0.1:8080/traffic-hooks/<site>/<tool>`. A server set up with
install.sh: the beacon helper itself, `http://127.0.0.1:8766/traffic-hooks/<site>/<tool>`.
The signature is the same. Or allow the path `/traffic-hooks/` in the CDN's
bot rules. The how-to: docs/help/leads-from-your-backend.md.

## What the receiver answers

| status | when |
| --- | --- |
| 200 | taken: `{"ok":true,"recorded":1,"duplicates":0}`; a repeat of the same event is a duplicate and changes nothing; an event Skald does not count is taken and ignored |
| 400 | the body is not JSON, or not the tool's event (`lead`: a missing `external_ref` or `action`, an unknown `stage`, a time that is not a time, an event more than a day ahead) |
| 401 | the signature does not match, or its time is more than 5 minutes off. Failed attempts are written once a minute per hook, as a count |
| 404 | unknown site or tool, or no secret set |
| 411 / 413 | no length / a body over 64 KiB |
| 429 | over `hooks.per_minute` (default 60) verified deliveries per site and tool, burst `hooks.burst` (30); or a sender address with too many failed signatures (`hooks.preauth_per_minute`, default 30, burst `hooks.preauth_burst`, 10) |
| 500 | not kept (disk or database); the tool should send again |

Every answer for a known hook is a row in the delivery log (what happened,
never the body). The signature is checked on the raw bytes before the body
is parsed and before the hook's rate-limit bucket is spent: only a verified
delivery counts against `hooks.per_minute`, so an unsigned flood cannot
starve the real tool. Failed signatures spend a small bucket per sender
address instead (X-Real-IP on the proxy's connection: loopback or
`hooks.trusted_proxies`; else the connection's address; kept in memory
only). Tools retry on anything but 2xx; a retry is harmless, because a
conversion is kept once per (site, tool, external ref, stage).

Cal.com and Typeform sign no timestamp, so a captured body could be sent
again later. Skald keeps a SHA-256 of each accepted body and its event id
(table `hook_replays`, 30 days, never the body) and answers a repeat with
200 and outcome `replay`, neither spooled nor kept. `forget` leaves these
hashes, so a replay cannot bring back a forgotten conversion.

## Skald's signature (`lead` and `json`)

```
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">
```

The key is the hook's secret. Skald refuses a `t` more than 5 minutes from
its own clock. Sign the exact bytes you send.

Python, standard library only:

```python
import hashlib, hmac, json, os, time, urllib.request

secret = os.environ["SKALD_HOOK_SECRET"]            # never in the code
body = json.dumps({
    "external_ref": "L-1001", "action": "demo", "stage": "completed",
    "vid": "skv_Q2xhc3NpY0V4YW1wbGVJRA",
    "first_touch": {"referrer": "https://www.google.com/", "landing": "/", "at": "2026-10-08T09:12:00Z"},
    "last_touch": {"landing": "/pricing/", "utm_source": "newsletter", "utm_medium": "email"},
    "ip": "192.0.2.10",                              # Skald looks up the country, drops this
    "user_agent": "Mozilla/5.0 ...",                 # Skald works out the device, drops this
}).encode()
t = str(int(time.time()))
sig = hmac.new(secret.encode(), t.encode() + b"." + body, hashlib.sha256).hexdigest()
request = urllib.request.Request(
    "https://www.example.com/traffic-hooks/example.com/lead", data=body, method="POST",
    headers={"Content-Type": "application/json", "X-Skald-Signature": f"t={t},v1={sig}"})
print(urllib.request.urlopen(request, timeout=10).read())
```

curl:

```sh
BODY='{"external_ref":"L-1001","action":"demo"}'
T=$(date +%s)
SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "$SKALD_HOOK_SECRET" -hex | sed 's/^.* //')
curl -sS -X POST 'https://www.example.com/traffic-hooks/example.com/lead' \
  -H 'Content-Type: application/json' -H "X-Skald-Signature: t=$T,v1=$SIG" --data-raw "$BODY"
```

### The lead body

| field | | |
| --- | --- | --- |
| `external_ref` | required | the lead's own id in the site |
| `action` | required | what was done, a lowercase token: `demo`, `trial`, `contact` |
| `stage` | default `completed` | `started`, `completed`, `cancelled`, `rescheduled`, `no_show`, `paid`, `won`, `lost` (a `won` or `lost` row stands on its own and counts on its own `at`) |
| `at` | default: when it arrived | ISO time with its offset (`2026-09-25T14:30:00-04:00`, `...Z`) or Unix seconds. A time without an offset (`2026-09-25`, `2026-09-25T08:00:00`) is read in the site's time zone (2.4.0; before, as UTC, which put a bare date on the day before for a site west of UTC); the delivery log says so, and so does the hook test. The same for `first_touch_at` and a touch's `at` |
| `vid` | | the visitor ID the page had (`skv_...`, or the site's own ID). Kept only when the site has visitor IDs on (`beacon.visitor_ids`); off, it is dropped from the spool and the store (2.2.3) |
| `first_touch`, `last_touch` | | `{referrer, landing, utm_source, utm_medium, utm_campaign, utm_content, utm_term, gclid, msclkid, fbclid, li_fat_id, at}` |
| `landing`, `campaign`, `source` | | when the site worked them out itself (`source` one of Skald's source types) |
| `country` or `ip` | | two letters, or the visitor's address: Skald looks up the country (`conversions.country_db`, the DB-IP `.mmdb` file the web server uses) and drops the address |
| `device` or `user_agent` | | `Desktop`/`Mobile`/`Tablet`, or the agent: Skald works out the device and drops the agent |
| `visits_before`, `first_touch_at` | | when the site knows them |
| `name`, `email` | | kept only when the site's identity is `full` (Privacy, below) |

`json` takes the same object, a list of them, or `{"records": [...]}` (at most 100).

## Each tool

### Calendly (paid plan: Standard or higher)

Calendly makes webhook subscriptions through its API only. Use the secret
from `skald hooks secret example.com calendly` as the `signing_key`:

```sh
curl -sS -X POST https://api.calendly.com/webhook_subscriptions \
  -H "Authorization: Bearer $CALENDLY_TOKEN" -H 'Content-Type: application/json' \
  -d '{"url": "https://www.example.com/traffic-hooks/example.com/calendly",
       "events": ["invitee.created", "invitee.canceled", "invitee_no_show.created"],
       "organization": "https://api.calendly.com/organizations/<ORG>",
       "scope": "organization", "signing_key": "<the hook secret>"}'
```

A signing key Calendly made for an existing subscription can be pasted on
the Integrations page instead.
Events: `invitee.created` -> completed, `invitee.canceled` -> cancelled
(rescheduled when Calendly says so), `invitee_no_show.created` -> no_show.

**Only some event types (2.4.0).** One Calendly account often books for
several businesses, and a Calendly subscription cannot be limited to some
event types. Name the site's own in Settings > Integrations > Calendly
("Only these Calendly event types"), a settings row for the site
(`hooks.calendly.event_types`), or in the config:

```yaml
hooks:
  calendly_event_types: [https://api.calendly.com/event_types/AAAA1111, product-demo]
  # calendly: {event_types: [...]}      # the nested form, with PyYAML
```

Each item is an event type's URI (`GET https://api.calendly.com/event_types`
lists them), its uuid, or the booking page's slug (or the page's address,
`https://calendly.com/<you>/<slug>`). Calendly's webhook names the event type
by its URI and its name, never the page's slug, so a slug is compared with
the name written as a slug ("Product demo" -> `product-demo`): a renamed
event type no longer matches its old slug, its URI always does. When the
list is set, an event of another type is answered 200, logged as `ignored`
with "other event type (<its URI>)" so it can be copied into the list, and
nothing else: no spool line, no row. A no-show names only its invitee: it is
kept when that booking is kept. An empty list keeps every event, as before.
Code: `conversions/event_types.py`, applied before the spool.
Pass the visitor ID in the embed as `utm_content` (Calendly returns the UTM
fields in the webhook): `https://calendly.com/<you>/<event>?utm_content=skv_...`.

### Cal.com

Settings > Developer > Webhooks > New. Subscriber URL: the hook address.
Event triggers: Booking Created, Booking Cancelled, Booking Rescheduled.
Secret: the hook secret. Pass the visitor ID in the embed as
`metadata[skv]=skv_...` (or a hidden booking question named `skv`).
Only some event types: `hooks.calcom.event_types` (Settings > Integrations >
Cal.com, or `hooks: {calcom_event_types: [...]}`), each an event type's id
(`1234`) or slug (`30min`, or the page's address); Cal.com sends both. The
rest works as for Calendly above.

### Stripe

Dashboard > Developers > Webhooks > Add endpoint. URL: the hook address.
Events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`.
Then give Skald the endpoint's signing secret (`whsec_...`): paste it on the
Integrations page, or `hooks secret example.com stripe --value -`. Set the visitor ID as the
Checkout Session's `client_reference_id` (or `metadata.skv`). Action `paid`:
a session paid by a delayed method counts as started first, then paid.
Customer details are never read.

### Typeform

Your form > Connect > Webhooks > Add a webhook (the hook address), then
Edit > Secret (the hook secret). Add a hidden field `skv` to the form and
pass it in the embed (`data-tf-hidden="skv=skv_..."`); hidden `utm_*`
fields give the last touch. Answers are never read.

### HubSpot

App webhooks: in your HubSpot app, Webhooks > Target URL (the hook
address); subscribe to `contact.creation` (action `contact`), to
`object.creation` for meetings (object type `0-47`, action `demo`) and to
`deal.propertyChange` for `dealstage`. A deal moving to `closedwon` is
`deal`, stage `won`. Give Skald the
app's client secret: paste it on the Integrations page, or
`hooks secret example.com hubspot --value -`.
Workflows: the "Send a webhook" action, with the request signed by the same
app; Skald reads `objectId` and the properties `skv` and `utm_*`, and counts
it as `contact` unless a property `skald_action` names another action (set
it to `demo` in a "meeting booked" workflow). If your
account cannot sign a workflow webhook with signature v3, send it through
Zapier or Make to the `json` hook instead.

Behind a proxy, Skald rebuilds the URL HubSpot signed from `Host` and
`X-Forwarded-Proto`; set `hooks.public_url: https://www.example.com` if they
differ from the address HubSpot calls.

### Zapier, Make, n8n (`json`)

Post the lead body (above) to `/traffic-hooks/example.com/json` with Skald's
signature. Zapier: a "Code by Zapier" (Python) step can run the Python
example above. Make: the HTTP module, with the header value
`t={{timestamp}},v1={{sha256(timestamp + "." + body; "hex"; secret)}}`.

## The Integrations page

With accounts (`access.mode: sessions`), **Settings > Integrations** does
in the browser what `skald hooks` does on the server. It is for admins and
owners of the site's organisation; an install admin may pick any site of
the install. Code: `skald/integrations_api.py`, page
`webapp/js/tabs/integrations.js`.

- **The script tag** to copy, with its options as tick boxes (wait for
  consent, share across subdomains, other domains you own, accept the ID
  from your other domains). It says whether
  anonymous visitor IDs are on for the site (`beacon.visitor_ids`).
- **Status** (2.4.0), on top: the doctor's lines for the roads in
  (`doctor.integration_checks`): the hook receiver answering, the script tag
  (its origins and its last event), each hook set up, one lead from two
  tools, the lead database; each OK, NEEDS ATTENTION with the fix, or OFF.
  The GET answer carries them as `status`, and `duplicates`: each external
  ref that arrived from two tools (the script tag's own rows apart). Each tool
  keeps its own row, so such a lead counts once per tool: send each lead
  through one road.
- **Incoming hooks**: for each tool its address, its state in words (needs a
  secret, never received, ready, last received N ago, or the last delivery
  refused and why: `conversions/roads.py`), whether its secret is set
  (and whether it comes from the server's environment), **Make secret** or
  **Rotate secret** (shown once, kept 0600 in `secrets.json`; a rotated
  secret replaces the old one at once), **Send a test event** (a signed
  sample posted to the receiver inside the helper: checked, read, logged as
  `test`, never kept or counted; the message says what a real one would
  keep), and the last 50 deliveries with their outcome. Calendly and Cal.com
  also have **Only these event types** (`POST integrations/hooks/types`
  `{site, tool, types}`; `[]` keeps every event; admins; audit log
  `setting.change`). A secret held in an environment variable is changed there, not
  on the page (make, paste and remove answer 409).
- **Paste the signing secret from <tool>** (`POST integrations/hooks/paste`
  `{site, tool, secret}`): for tools that sign with a secret they make.
  Stripe and HubSpot have only this (`integrations/secret` answers 409 for
  them); Calendly, Cal.com and Typeform have both; `lead` and `json` (Skald's
  own signature) only Make secret. The field is write-only: one line, no
  spaces, 12-500 characters (Stripe's must start `whsec_`), kept 0600 in
  `secrets.json`, never in an answer or the audit log (`hook.secret`,
  "pasted").
- **Remove** (`POST integrations/hooks/remove` `{site, tool}`, admin, with a
  confirm): deletes the hook's secret, so the receiver answers 404 to further
  deliveries, as for a hook never set up. The `deliveries` rows, the spool
  and the conversions stay. Audit log: `hook.remove`. There is no CLI
  command for it: on a server without accounts, delete the key
  `hooks/<site>/<tool>` from `secrets.json` (it must stay 0600).
- **Outgoing webhooks** (below): add, test, rotate the secret, remove, and
  each one's last 50 deliveries.

Every change is in the audit log (Settings > Audit log), never a secret.
nginx sends `<page>/integrations` and `integrations/*` to the helper
(DEPLOY.md, the helper routes; `integrations/hooks/paste` and
`integrations/hooks/remove` fit the existing `integrations(?:/[a-z]+(?:/[a-z]+)?)?`).

## Outgoing webhooks

Skald can tell your CRM, Zapier, Make or Slack what happened. Add an
`https://` address and the events it wants on the Integrations page:

| event | when |
| --- | --- |
| `conversion.started` | an action started: a form or a booking opened |
| `conversion.completed` | an action completed: a form sent, a demo booked, a payment (stage `completed` or `paid`) |
| `conversion.cancelled`, `conversion.rescheduled`, `conversion.no_show` | a booking changed |
| `conversion.abandoned` | started and not completed by the same visitor ID within `conversions.abandon_hours`; sent once |
| `lead.won`, `lead.lost` | the team marked the lead (the lead database, a CRM) |
| `ai.reading_changed` | a new AI alert (alerts_ai.py, alerts on): an assistant started or stopped reading a page, or its likely visits jumped or vanished; once per alert, never from a replay |

`ai.reading_changed` carries no conversion fields: `{"event","id","site","alert_id","cause"
("ai_started_reading"/"ai_stopped_reading"/"ai_sending_people"),"kind" ("started"/"stopped"/
"sending_jumped"/"sending_vanished"),"assistant" (its owner, e.g. "OpenAI", or a likely-AI
assistant name),"crawlers","day","window" [first, last],"pages" [{"path","n"} or
{"path","weeks","n"}],"visits","average","title","detail","figure","threshold","opened_at"}`.

Each is a `POST` with a JSON body, signed like Skald's own hooks:

```
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">
```

with the webhook's own secret (`skw_...`, shown once when it is made or
rotated). Check it as in "Skald's signature" above, and refuse a `t` more
than 5 minutes off. The body:

```json
{"event": "conversion.completed", "id": "9f2c...", "site": "example.com",
 "action": "demo", "stage": "completed", "at": "2026-10-11T14:00:00Z",
 "tool": "calendly", "external_ref": "...", "vid": "skv_...",
 "source_type": "Search", "first_source": "Search", "campaign": "october",
 "landing": "/pricing/", "country": "CA", "device": "Desktop",
 "visits_before": 2, "seconds_to_convert": 259200,
 "journey": [{"at": "2026-10-08T09:00:00Z", "path": "/", "source_type": "Search"}]}
```

- `id` is the same on every retry of one delivery: drop a repeat by it. A
  test from the page carries `"test": true`.
- Never a name or an email, even with `identity: full`. `journey` is the
  visitor ID's page views up to the conversion (at most 50; empty without
  an ID). A figure not known is `null`.
- Queued by the live run (every 2 minutes) and run-daily for each site,
  then sent in ONE pass after every site, so a slow receiver never holds up
  another site's run. Each delivery has 10 seconds of wall clock in all
  (name lookup, connect, TLS, send and answer; a receiver that trickles
  bytes is cut off), and the whole pass at most 30 seconds and 50 rows;
  what is left waits for the next run. A 2xx answer is delivered. Anything
  else, a time-out or a redirect (never followed) is tried again after
  1 minute, 5 minutes, 30 minutes, 2 hours and 12 hours, then marked
  failed. The log keeps 90 days.
- The page's test sends at once, with the same 10-second limit, at most 3
  in 10 minutes per user (then 429).
- Removing a webhook stops only that site's own webhook and its pending
  rows. The audit log keeps the webhook's host, never its path or query.
- Only conversions recorded after the webhook was added are sent; nothing
  older is replayed.
- Only `https`, and never to an address on a private, loopback, link-local
  or reserved network (the name is resolved, every address it gives is
  checked, and the connection goes to an address that was checked). IPv6
  addresses that carry an IPv4 address are refused whatever it is:
  IPv4-mapped, IPv4-compatible (`::a.b.c.d`), 6to4 `2002::/16`, NAT64
  `64:ff9b::/96` and `64:ff9b:1::/48`, Teredo `2001::/32`. `secrets.json`
  is changed under a file lock. `integrations.allow_private_urls:
  true` lifts that, for a closed network or a test only.
- Code: `skald/conversions/outgoing.py`; tables `webhooks` and
  `outbox` in `conversions.sqlite`; secrets in `secrets.json` under
  `outgoing/<site>/<id>`.

## nginx

The receiver runs inside the beacon helper (`skald/beacon_server.py`,
127.0.0.1:8766). nginx forwards one path to it: public, POST only, small
bodies, rate-limited, not logged (the delivery log is Skald's own).

Since 2.2.2 that helper runs on every install, whether or not the script tag is
on: the Docker image always starts it, `install.sh` enables it, and `skald upgrade`
switches it on if it was installed but off. Without `beacon.origins` (Docker:
`SKALD_BEACON_ORIGINS`) it takes hooks only, and `/traffic-beacon` and
`/traffic-js/skald.js` answer 404. Before 2.2.2 a hook answered 502 until the
script tag was switched on.

```nginx
# http {} context, once
limit_req_zone $binary_remote_addr zone=skald_hooks:1m rate=60r/m;

# the site's server {} block
location ^~ /traffic-hooks/ {
    limit_except POST { deny all; }
    client_max_body_size 64k;
    limit_req zone=skald_hooks burst=30 nodelay;
    limit_req_status 429;
    access_log off;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 10s;
    proxy_pass http://127.0.0.1:8766;
}
```

Run `nginx -t` before every reload.

## What is kept, and privacy

| what | where | kept |
| --- | --- | --- |
| conversions: action, stage, time, visitor ID, external ref, tool, source, campaign, landing, country, device | `conversions.sqlite` beside the history (`conversions.db`), 0640 | `conversions.retention_days` (400) |
| page views per visitor ID (beacon `page_view` with visitor IDs on) | same file, `journeys` | `journeys.vid_days` (30), longer only for IDs that converted |
| conversions from the beacon (tool `beacon`, docs/BEACON.md "Visitor IDs") | same file, `conversions` | as conversions |
| name and email | same file, `identities` | only when `conversions.identity: full`; else never written |
| rows a lead sync took away, whole, with when and why | same file, `removed` | as conversions |
| each visit with its IP address and user agent (2.4.0, `privacy.keep_ips`) | same file, `visits`, `visit_days` | `privacy.keep_days` (395) |
| delivery log: time, outcome, HTTP status, error, external ref; never a body | same file, `deliveries` | 90 days |
| the verified bodies (and, on a `lead` or `json` line with a time without an offset, the zone it was read in) | `hooks/<day>.jsonl` beside the history (`hooks.spool`), 0640 | 400 days |
| hook secrets | `secrets.json` beside the history (`hooks.secrets`), 0600, or env variables | until replaced |

- **Only what counts.** Before a body is spooled, Skald keeps only the
  keys that tool's adapter and the second count read (an allow-list per tool,
  `conversions.SPOOL_KEYS`); everything else goes. Addresses, user agents,
  phones, extra emails and Calendly's cancel and reschedule links always go.
  With `conversions.identity: full` the name and the primary `email` are
  kept, nothing more; with `anonymous`, neither.
- **Identity: full by default (2.4.0).** Unset, a new install reads `full`.
  An install whose history predates 2.4.0 reads `anonymous` until someone
  sets it (Settings > Data retention > People, `config.yml`, or Docker
  `SKALD_IDENTITY=full`): its privacy notice may still promise otherwise
  (`people/policy.py`). Change the notice first; some places need consent
  (`beacon.consent: required`).
- **Addresses.** The receiver reads the caller's address only to limit
  failed signatures, in memory; it is never written. A site's own `lead`
  may pass the visitor's address once, for the country; it is dropped at
  once. A conversion holds no address: a person's visits are linked to a
  lead by the person search (people/lookup.py), through a visitor ID, an
  email, or the visits that sent a form within 2 minutes of the lead
  (matched by time, said as not certain).
- **Test marks.** `./bin/skald conversions list SITE [--test]` shows the latest
  rows with their ids; `./bin/skald conversions mark-test SITE ID... [--unmark]`
  marks them test (every row of the same tool and reference, so a booking's
  later stages too). A test row is kept and listed (Leads > Left out,
  Conversions > Marked test), never counted: not in `conversions.json`, not
  abandoned, and the second count leaves it out by its own SQL. Each change
  is a row in the accounts audit log (`conversions.test`, `conversions.untest`).
- **Delete on request:** `./bin/skald conversions forget --email ADDRESS`,
  `--vid skv_...` or `--lead REF` (or `./bin/skald forget` with the same flags;
  try `--dry-run` first) deletes the conversions, the removed rows, the
  journeys of every visitor ID involved, the identity, the delivery rows and
  the spool lines. `./bin/skald forget --ip` deletes the visits kept with an
  address. `privacy.log` gets a line with a hash
  prefix, never the value.
- **Pruning:** `skald conversions prune` (add it to the daily cron).

## The second count

`audit_conversions.py` reads the spool on its own, maps each tool's events
with its own code, removes repeats the same way, and counts conversions per
day by action and stage. A time without an offset is read in the zone the
spool line names (`zone`, written by the receiver since 2.4.0), else as UTC,
the way that line was kept. An event the event-type filter left out was never
spooled, so neither road counts it. It reads the beacon spool too (people's events with
a visitor ID, one per ID, action and stage within 30 minutes), with its own
parsing, for the conversions the beacon made, and the lead database by its
own SQL (above). Rows marked test are left out of every road: the audit
reads their tool and reference from `conversions.sqlite` by its own SQL
(`audit_conversions.test_keys`) and skips them in the spool, the beacon and
the lead recounts. run-daily compares the last 30 days
(`conversions.audit_days`) with `conversions.sqlite`; a day that disagrees
is withheld and run-daily ends "withheld". The beacon's counts of whole
days are kept in the audit's own file (`conversions-audit.json` beside the
history) so each redraw reads only the newest spool files; `conversions
forget` deletes it. Every figure of `conversions.json` is counted a second
time by SQL (`audit_conversions_figures.py`); see DATA-CONTRACT.md.
