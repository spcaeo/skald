# Integrations: incoming hooks

Skald counts conversions (a booking, a form, a trial, a payment) that the
site's own server and the tools it uses push to it. Each push is a signed
`POST` to the site's own address. Skald checks the signature, keeps a raw
copy in its spool, and records the conversion once. It also reads the
site's own lead database, when it has one (below, "Leads from the lead
database"), and the page's script tag. It also syncs search figures from
Google Search Console and Bing Webmaster Tools ([INTEGRATIONS-SEARCH.md](INTEGRATIONS-SEARCH.md)).

**One name per action**, whatever reports it:

| Action | From |
| --- | --- |
| `demo` | Calendly, Cal.com, HubSpot meetings, the page's booking events (`calendly_*`, `cal_*`, `book_demo_open`, `demo_booked`), the lead DB's `demo_opened` / `demo_booked` |
| `paid` | Stripe (a checkout paid; one paid later by a delayed method is `started` first) |
| `contact` | forms: the page's `form_*` / `contact_submit`, Typeform, HubSpot contacts and workflows, the lead DB's `contact` |
| `signup`, `waitlist` | the page's sign-up and early-access events, the lead DB |
| `deal` | HubSpot deals (`won` when one moves to closedwon) |
| `call`, `email`, `cta` | the page's `tel_click`, `mailto_click` and `cta_click` (visitor IDs on) |

A `lead` or `json` hook may name any short action; the older names
`booking`, `meeting`, `demo_booked`, `call_booked` are read as `demo`,
`checkout` and `payment` as `paid`, `form` and `contact_form` as `contact`,
`sign_up` as `signup` (`conversions.ALIASES`). The conversions file (schema 2)
renamed its existing rows the same way when it was upgraded, keeping a copy
of the old file beside it (`conversions.sqlite.v1.bak`).

Code: `skald/conversions/` (receiver `hooks.py`, one adapter per tool in
`adapters/`), second count `skald/audit_conversions.py`.

## The script tag

One line in every page's `<head>` gives Skald page views, form steps,
`tel:`/`mailto:`/outbound clicks and Calendly, Cal.com and HubSpot meeting
embeds, each with an anonymous visitor ID when the install keeps them:

```html
<script src="https://skald.example.com/traffic-js/skald.js" data-site="example.com" defer></script>
```

(`skald.example.com` is your Skald's address; Settings > Integrations and the
set-up dialog give the exact line.) It needs **no change on the site's server**
(2.24.0): the page loads the file from Skald and posts its events to
`/traffic-beacon` beside it, on Skald. The file is under 6.5 KB (the test's
budget; 6 KB until it asked Skald about shared subdomains, 5 KB before),
plain JavaScript, served by the beacon helper (`GET /traffic-js/skald.js`, an
ETag and a day's cache). No `eval`, never a field's value; the visitor ID stays
in the page's own storage. How a cross-site post is taken (the Origin map,
CORS for that Origin, no preflight): docs/BEACON.md, "Where the tag posts".

**First-party, from the site's own domain (optional).** Where ad blockers
matter, the site's server can pass `/traffic-js/` and `/traffic-beacon` on to
Skald and the page loads the tag from itself:

```html
<script src="/traffic-js/skald.js" data-site="example.com" defer></script>
```

It then posts to the site's own `/traffic-beacon`, exactly as before 2.24.0.
The set-up dialog's "Advanced: serve it from your own domain" has the nginx,
Apache and Caddy lines; Skald's nginx must then trust that server for
`X-Forwarded-For` (docs/BEACON.md).

On Skald's own server, nginx, in its HTTPS `server { }` beside `/traffic-beacon`:

```nginx
location = /traffic-js/skald.js {
  limit_except GET { deny all; }
  proxy_pass http://127.0.0.1:8766;
  proxy_set_header Host $host;
}
```

**Every site of the install (2.9.0).** The tag works for each site Skald counts,
not only the first. A post goes to the site its `Origin` names, into that
site's own spool. The first site takes its listed origins (`beacon.origins`,
`SKALD_BEACON_ORIGINS`); a site added from the dashboard or a `sites:` file
takes `https://<each of its hosts>`, while the install has the tag on (the
first site has an origin). The file is served with the visitor-ID setting of
the site whose page loads it (by `Referer`). A site on another server uses
the plain tag (it posts to Skald directly, from the visitor's own address), or
passes `/traffic-js/` and `/traffic-beacon` through its own server so the tag
and the beacon stay on its own origin; Skald's nginx must then trust that
server for `X-Forwarded-For`. Details: docs/BEACON.md, "Several sites".

### Options (attributes on the tag)

| attribute | default | what |
| --- | --- | --- |
| `data-site` | - | the site's own domain, `example.com`; also the shared cookie's domain (below) |
| `data-endpoint` | `/traffic-beacon` beside the script | where to post. Without it the tag posts beside the address it was loaded from: `https://skald.example.com/traffic-js/skald.js` posts to `https://skald.example.com/traffic-beacon`, `/traffic-js/skald.js` to the page's own `/traffic-beacon` |
| `data-consent="required"` | not required | send nothing and store nothing until the page calls `skald('consent', true)` |
| `data-share-subdomains="true"` | off | keep the ID in a first-party cookie too, so `www.` and `app.` share it |
| `data-link-domains` | - | comma list of other domains you own (`app.example.net, shop.example.org`): links to them get `?skv=<id>` when clicked, and an `skv` arriving from them is adopted (below) |
| `data-accept-id="true"` | off | adopt a valid `?skv=<id>` whatever the referrer (below) |

### What it does by itself

- `page_view` on load, on each client-side navigation (`history.pushState`, `replaceState`, back and
  forward; once per path) and on a page restored from the back-forward cache: the tag's own events, never added to the log's counts.
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
- **Visitor IDs are off by default** (`beacon.visitor_ids: false`), and set
  per site (since 2.9.0: a site setting for admins, docs/SETTINGS.md): the
  helper then serves the file so that it makes no ID, and drops any `v`
  it is sent. Turn them on for a site only when its privacy notice says so,
  and let its consent banner gate the tag (`data-consent="required"`).
- With IDs on or off, the visit's source (the referring host without
  `www.`, a space, and the `utm_source` value) is kept in `sessionStorage`
  (`skald.src`): written when a page has another site's referrer or a
  `utm_source`, read by the visit's later pages. It ends with the tab.
- With IDs on, the ID (`skv_` + 16 random bytes) is kept in `localStorage`
  (`skald.vid`), and with `data-share-subdomains="true"` in a cookie
  `skald_vid` (400 days, `SameSite=Lax; Secure`).
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

example.com's website posts a signed `lead` hook for each lead and a signed
`calendly` hook for each booking. A site whose lead database sits on Skald's
own server needs no lead hook: Skald reads the leads from that database (next
section), which it already reads for Leads & sales > Summary and Sources (Count from:
Lead database).

## Recorded journeys (2.43)

A site's own pages can also send Skald each consenting visitor's session: pages read, calls to
action, forms sent, signups and bookings. A page helper (`/traffic-js/journeys.js`) posts each
event to a relay on the site's own server, which signs it with the site's journey secret and
forwards it to `POST /traffic-hooks/<site>/journey`. The sessions show as **Recorded by your
site**, with their own figures, never added to the log's. Everything else, the contract, the
answers, consent, privacy and retention, is in [JOURNEYS.md](JOURNEYS.md).

## Leads from the lead database

When `leads.db` names the website's lead database (the default road of Leads & sales > Summary), every
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
| `session_id` | the visitor ID, when it has the shape of one (8 to 80 letters, digits, `_.:-`) and the site has visitor IDs on (`beacon.visitor_ids`); off, it is left out |

The file is opened read-only and only those columns are read; names and
emails only when the site's `conversions.identity` is `full` (the default
since 2.4.0, except on an install upgraded from before it: see Privacy,
below). Every live run (2 minutes) reads the leads changed since the last
one (by `updated_at`); run-daily reads them all and removes the rows of
leads deleted from the CMS. A row a sync takes away (the lead deleted,
marked spam or duplicate, or changed) is first copied whole into the
`removed` table, with when and why (`store.remove`): Leads & sales > Sources
(Count from: Tools, "Cancelled, removed and test") lists it under "Removed". Nothing disappears unseen; only `forget` deletes.
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
| `lead` | the site's own server or CMS: "a lead was made" | `X-Skald-Signature` (Skald's scheme, below), or the plain key `Authorization: Bearer <secret>` (2.30) |
| `json` | Zapier, Make, n8n, any script | `X-Skald-Signature` (Skald's scheme), or the plain key (2.30) |
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
| 401 | the signature (or, `lead` and `json`, the plain key) does not match, or its time is more than 5 minutes off. Failed attempts are written once a minute per hook, as a count |
| 404 | unknown site or tool, no secret set, or (saas) a site still waiting for its domain to be verified |
| 405 | not a POST; the one GET taken is `/traffic-hooks/<site>/leads` (2.18, INTEGRATIONS-LEADS.md) |
| 411 / 413 | no length / a body over 64 KiB |
| 429 | over `hooks.per_minute` (default 60) verified deliveries per site and tool, burst `hooks.burst` (30); or a sender address with too many failed signatures (`hooks.preauth_per_minute`, default 30, burst `hooks.preauth_burst`, 10) |
| 500 | not kept (disk or database); the tool should send again. Also when `secrets.json` can be read by others (it must be 0600) |

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
200 (`"duplicates":1`), logged as `replay`, neither spooled nor kept. `forget` leaves these
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

### The plain key (2.30)

A sender that cannot sign (Zapier's Webhooks step, a form plugin's custom
headers) may send the hook's secret itself, on `lead` and `json` only:

```
Authorization: Bearer <the hook's secret>
```

It is read only when the request has no `X-Skald-Signature` (a signature,
right or wrong, is always checked as one). The key is compared in constant
time (`adapters/lead.verify_key`, `hooks.accepted`); a wrong or empty one is
refused exactly like a bad signature: 401, a `bad_signature` delivery row
written at most once a minute as a count, and the sender's pre-auth bucket
spent. The header is never logged, spooled or kept. Calendly, Cal.com,
Stripe, Typeform and HubSpot never take it, nor does the signed
`leads/test` call or the signed GET of `leads`. It has no time: a captured
request could be sent again, which keeps nothing new (a lead is kept once per
site, tool, ref and stage), but a leaked key works until it is rotated. So
signing stays the default; the key is for `https://` senders that cannot sign.

### One-file helpers (2.30)

`skald/kit/leadfiles.py` fills the templates in `skald/kit/leads/`
for a site: `skald-lead.php` (`skald_lead($ref, $action, $email, $name, $extra)`),
`skald-lead.cjs` (Node 18+, `skaldLead(ref, action, {email, name, ...})`; `.cjs`
because Gmail refuses a zip holding `.js` or `.mjs`), `skald_lead.py`
(`skald_lead(ref, action, email, name, **extra)`, urllib only),
`wordpress/skald-leads/skald-leads.php` (a plugin: the after-submit actions of
Contact Form 7, WPForms, Gravity Forms, Elementor Pro and Ninja Forms, action
`contact`, ref `<plugin>-<entry id or a random id>`, the visitor ID from a
`skald_vid` field it adds to forms or the `skald_vid` cookie, posted with
`blocking => false`) and a `README.md`. Each signs with `X-Skald-Signature`, so
works on every Skald version, waits at most 3 seconds and never throws into
the caller. The secret: the environment variable `SKALD_LEAD_SECRET` first
(WordPress: the constant in `wp-config.php` first); with no secret given the
file holds none and says so; with one, the file holds it as the fallback and
says to move it. The README never holds it.

`leadfiles.files(site, url, secret)` gives `{path under leads/: bytes}` (the
set-up pack); `leadfiles.one(lang, site, url, secret)` gives
`(file name, bytes, media type)` for `php`, `node`, `python` or `wordpress`
(the plugin as `skald-leads.zip`, one folder, for Plugins > Add New > Upload).
The dashboard serves them at `POST <page>/integrations/leadfile` (below).

### The lead body

| field | | |
| --- | --- | --- |
| `external_ref` | required | the lead's own id in the site |
| `action` | required | what was done, a lowercase token: `demo`, `trial`, `contact` |
| `stage` | default `completed` | `started`, `completed`, `cancelled`, `rescheduled`, `no_show`, `paid`, `won`, `lost` (a `won` or `lost` row stands on its own and counts on its own `at`), `refunded` (2.32.0: a refund on the sale's `external_ref`, never a lead or a finish) |
| `at` | default: when it arrived | ISO time with its offset (`2026-09-25T14:30:00-04:00`, `...Z`) or Unix seconds. A time without an offset (`2026-09-25`, `2026-09-25T08:00:00`) is read in the site's time zone (2.4.0; before, as UTC, which put a bare date on the day before for a site west of UTC); the delivery log says so, and so does the hook test. The same for `first_touch_at` and a touch's `at` |
| `vid` | | the visitor ID the page had (`skv_...`, or the site's own ID). Kept only when the site has visitor IDs on (`beacon.visitor_ids`); off, it is dropped from the spool and the store (2.2.3), and so is a Skald ID in any other field: a tool's own (Typeform `hidden.skv`, Cal.com `metadata`, Calendly `tracking.utm_content`, Stripe `client_reference_id`, HubSpot's `skv`) or inside a text such as a landing address's `?skv=` (2.38.0; before, those were kept in the spool for its 400 days) |
| `first_touch`, `last_touch` | | `{referrer, landing, utm_source, utm_medium, utm_campaign, utm_content, utm_term, gclid, gbraid, wbraid, msclkid, fbclid, li_fat_id, at}`, each optional. `gbraid` and `wbraid` are Google Ads clicks from iOS: like `gclid`, they make the touch a paid Search engine visit |
| `landing`, `campaign`, `source` | | when the site worked them out itself (`source` one of Skald's source types) |
| `country` or `ip` | | two letters, or the visitor's address: Skald looks up the country (`conversions.country_db`, the DB-IP `.mmdb` file the web server uses) and drops the address |
| `device` or `user_agent` | | `Desktop`/`Mobile`/`Tablet`, or the agent: Skald works out the device and drops the agent |
| `visits_before`, `first_touch_at` | | when the site knows them |
| `name`, `email` | | kept only when the site's identity is `full` (Privacy, below) |
| `label` | | 2.18: a short lowercase token that sorts the leads of one action, e.g. a contact form's topic (`sales`, `support`, `partnership`): `^[a-z0-9][a-z0-9_-]{0,39}$` (`conversions.LABEL`), trimmed and lower-cased first. Anything else (a longer one, a space, a number, an object) is no label: the lead is kept without one, never refused for it; the answer carries `"notes"` and the delivery log's error column says so (never the value sent). Each row keeps its own: a later stage of the same `external_ref` has the label it sends, else none. A resend of a kept ref and stage changes nothing, its label neither |
| `test` | | 2.19: a JSON boolean. `true` keeps this delivery's row marked test (kept and listed, never counted); `false` or absent, a real lead. That row only: a later stage of the ref is test only if it says so too, or if the ref was marked (`leads/test`, `mark-test`). Not a boolean: ignored with a note, like `label`. A resend differing only in `test` changes nothing |

| `value`, `currency` | | 2.32.0: a sale's amount, in the currency's normal units (`49.00`), at most its decimals, kept as integer minor units; ISO 4217 code, upper-cased, needed with `value`. A bad one is dropped with a note, never refused |
| `customer_ref` | | 2.32.0: the customer's own ID, 1 to 128 of `[A-Za-z0-9_.:-]`, never an `@`. A `paid` whose customer paid before is a renewal |
| `tags` | | 2.32.0: at most 5 `{key: value}` pairs, key `[a-z0-9_]{1,24}`, value `[a-z0-9_.-]{1,40}` lower-cased, never 7 or more digits in all (`-` and `.` not counted) nor an IP address's shape, and no key naming a person's detail (`email`, `phone`, a name); a bad pair is dropped with a note |

The revenue fields, the rules and recipes for Polar, Dodo Payments, Paddle, Lemon Squeezy and Gumroad: [INTEGRATIONS-REVENUE.md](INTEGRATIONS-REVENUE.md).

`json` takes the same object, a list of them, or `{"records": [...]}` (at most 100).

Where the label is kept and shown, the signed `GET /traffic-hooks/<site>/leads` a site's server uses to check that Skald has every lead it sent (2.18), and `POST /traffic-hooks/<site>/leads/test`, the site marking its own leads as test (2.19): [INTEGRATIONS-LEADS.md](INTEGRATIONS-LEADS.md).

### Lead stages: a lead counts once, won and lost are outcomes

A lead is a finished row (`completed` or `paid`, `conversions.FINISHED`) of a lead action
(`contact`, `signup`, `waitlist`, `trial`, `demo`: `conversions.LEAD_ACTIONS`), test rows
left out. It counts once, on the day of that row's `at`. A lead the team later marks won or
lost keeps that row: a hook posts the same `external_ref` with stage `won` or `lost` (a row of
its own, at its own `at`, since a conversion is kept once per site, tool, ref and stage), and
the lead database adds a `won` or `lost` row beside the completed one (at `created_at`). So:

- a lead later won, or later lost, is still one lead, on its completed day; the outcome
  neither adds a lead nor takes one away, and the day the outcome arrives counts none;
- `won` and `lost` are outcomes, shown apart: as stages on Leads & sales > Leads (Stage now) and
  Summary (Tools), Calendar bookings ("Won"), the outgoing `lead.won` / `lead.lost` events; never in a Leads figure;
- a `won` or `lost` for a ref that never completed is an outcome with no lead: not counted;
- a lead marked `spam` or `duplicate` in the lead database stops being a lead (its rows are
  taken away and kept in `removed`), and every past day changes with it.

The same rule everywhere a Leads figure is shown: Overview's Leads tile (conversions.json days,
`js/tabs/leadfigs.js`), the daily and weekly mails and client reports
(`conversions_leads.period_leads`), and Leads & sales > Summary counting from the tools. Counting
from the lead database (leads.json), a lead is a submission that is not spam or a duplicate, on
its `created_at` day, whatever its status; won and lost are its status, counted apart. Each is
recounted on its own road: `audit_conversions_leads.py` and `audit_client_reports.recount_leads`
(SQL over the finished stages), `audit_leads.py` (the lead database). Tested in
`tests/test_leads_outcomes.py`.

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
Events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, and for
revenue (2.32.0) `invoice.paid` (a renewal: `billing_reason` `subscription_cycle`, its invoice
id as the ref), `invoice_payment.paid` (Stripe's API 2025-03-31 and later: it ties a renewal's
payment intent to its invoice) and `charge.refunded` (stage `refunded` on the sale its
`payment_intent` paid, the cumulative `amount_refunded` kept as the latest total; a larger
total counts the difference on its own day, never past the sale's value).
Then give Skald the endpoint's signing secret (`whsec_...`): paste it on the
Integrations page, or `hooks secret example.com stripe --value -`. Set the visitor ID as the
Checkout Session's `client_reference_id` (or `metadata.skv`). Action `paid`:
a session paid by a delayed method counts as started first, then paid.
2.32.0: the amount (`amount_total`, an invoice's `amount_paid`), the currency and the Stripe
customer (`customer`, `cus_...`, as `customer_ref`) are kept, with the payment intent to match
refunds. Customer details (name, email, address) are never read.

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

A sale adds `value`, `currency` and `customer_ref` (above; recipes per payment tool in
[INTEGRATIONS-REVENUE.md](INTEGRATIONS-REVENUE.md)). Post the lead body (above) to `/traffic-hooks/example.com/json` with Skald's
signature, or with the plain key (2.30, above): Zapier's "Webhooks by Zapier"
POST, payload type json, header `Authorization: Bearer <secret>`. Zapier can
also sign in a "Code by Zapier" (Python) step running the Python example
above. Make: the HTTP module, with the header value
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
  (`doctor.integration_checks`): the access log and its page assets (2.13;
  Overview's first-run checklist reads them too), the hook receiver answering, the script tag
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
- **The one-file lead helper** (2.30, `POST integrations/leadfile`
  `{site, lang: php|node|python|wordpress, secret?}`, admins): the file of
  `kit/leadfiles.py` as a download (`Content-Disposition: attachment`;
  `wordpress` is `skald-leads.zip`). The secret goes in the file only when the
  request carries it, the page having just made it (shown once), and only
  when it is the lead hook's own (else 400; 409 with no lead secret yet);
  without it the file reads `SKALD_LEAD_SECRET` on the site's server. Audit
  log: `hook.leadfile` with the language and whether the secret is in the
  file, never the secret.
- **Outgoing webhooks** (below): add, test, rotate the secret, remove, and
  each one's last 50 deliveries.
- **What the site check found** (2.43): the GET answer carries `found`, the
  set-up's own check of the site (`accounts/site_setup` `found`, cleaned by
  `site_detect.clean_found`; `integrations_api.FOUND_KEYS`: server, platform,
  framework and their labels, `hosted_builder`, `tags` (ga4, calendly, calcom,
  stripe, hubspot) and `forms`, the home page's form count), or null when the
  site was never reached; and each tool's `last_at` and `test_at`. Settings >
  This site > Leads & tools (its Next step and groups) and the "not connected
  yet" card on each data page (`webapp/js/connect-plan.js`, `js/ui/connect.js`)
  read them to recommend one way. Nothing is fetched from the site for it.

Every change is in the audit log (Settings > Audit log), never a secret.
With saas on, an organisation whose plan is locked (payment overdue) can read
the page but not change it.
nginx sends `<page>/integrations` and `integrations/*` to the helper
(DEPLOY.md, the helper routes; `integrations/hooks/paste`, `/remove`,
`/types` and `integrations/leadfile` fit the existing `integrations(?:/[a-z]+(?:/[a-z]+)?)?`).

## Outgoing webhooks

Skald can tell your CRM, Zapier, Make or Slack what happened. Add an
`https://` address and the events it wants on the Integrations page (at
most 10 webhooks a site):

| event | when |
| --- | --- |
| `conversion.started` | an action started: a form or a booking opened |
| `conversion.completed` | an action completed: a form sent, a demo booked, a payment (stage `completed` or `paid`) |
| `conversion.cancelled`, `conversion.rescheduled`, `conversion.no_show` | a booking changed |
| `conversion.abandoned` | started and not completed by the same visitor ID within `conversions.abandon_hours`; sent once |
| `lead.won`, `lead.lost` | the team marked the lead (the lead database, a CRM) |
| `ai.reading_changed` | a new AI alert (alerts_ai.py, alerts on): an assistant started or stopped reading a page, or its likely visits jumped or vanished; once per alert, never from a replay |
| `alert.opened` | any new alert (alerts.py, alerts on), of every cause; once per alert, never from a replay |
| `todo.new` | a to-do that newly qualified on Overview > Insights (todo_rows.py, at the data update); once per to-do and first day; 2.41 |

`alert.opened` is `{"event","id","site","alert": {"id","cause","subject","severity","title"},
"text" ("[<site>] <title>\n<detail>"),"figures": {"figure","threshold","unit" ("visits",
"requests" or null),"data" (the alert's data, or null)},"at" (opened, UTC ISO)}`. A webhook
whose address is on `hooks.slack.com` (a Slack incoming webhook) is sent `{"text": ...}`
instead, for every event: the body's `text`, or one line made from a conversion's event,
action, stage, source and landing page (outgoing.wire). It is still signed; Slack ignores
the header.

`todo.new` is `{"event","id","site","todo": {"id","kind","subject","title","proof","todo",
"check"},"figures","rows_total","link" (the dashboard address that opens Fix this > My AI
agent: `...#overview/insights?todo=<id>&fix=1&fixby=agent`),"first_seen" (the day),"text"}`.
It never carries a code, a line or a row: the person makes the line by pressing.

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
127.0.0.1:8766). nginx forwards one path to it: public, POST and GET, small
bodies, rate-limited, not logged (the delivery log is Skald's own). GET only for the signed
`GET /traffic-hooks/<site>/leads` (2.18; any other GET is 405): a block from before 2.18 with
`limit_except POST { deny all; }` answers it 403 until it reads `limit_except GET POST`.

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
    limit_except GET POST { deny all; }
    client_max_body_size 64k;
    limit_req zone=skald_hooks burst=30 nodelay;
    limit_req_status 429;
    access_log off;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 10s;
    proxy_pass http://127.0.0.1:8766;
}
```

`X-Real-IP` matters: without it every failed signature counts against one
sender, nginx's own address. DEPLOY.md and `docker/nginx.conf` have the full
blocks. Run `nginx -t` before every reload.

## What is kept, and privacy

| what | where | kept |
| --- | --- | --- |
| conversions: action, stage, time, visitor ID, external ref, tool, source, campaign, landing, country, device | `conversions.sqlite` beside the history (`conversions.db`), 0640 | `conversions.retention_days` (400; 0: for good) |
| page views per visitor ID (beacon `page_view` with visitor IDs on) | same file, `journeys` | `journeys.vid_days` (30, 1 to 400); for an ID that converted, as long as its conversions |
| conversions from the beacon (tool `beacon`, docs/BEACON.md "Visitor IDs") | same file, `conversions` | as conversions |
| name and email | same file, `identities` | only when `conversions.identity: full`; else never written |
| rows a lead sync took away, whole, with when and why | same file, `removed` | as conversions |
| each visit with its IP address and user agent (2.4.0, `privacy.keep_ips`) | same file, `visits`, `visit_days` | `privacy.keep_days` (395) |
| delivery log: time, outcome, HTTP status, error, external ref; never a body | same file, `deliveries` | 90 days |
| hashes of Cal.com and Typeform bodies (replays) | same file, `hook_replays` | 30 days |
| the verified bodies (and, on a `lead` or `json` line with a time without an offset, the zone it was read in) | `hooks/<day>.jsonl` beside the history (`hooks.spool`), 0640 | `conversions.retention_days` (400; 0: for good), each site's lines by its own |
| recorded journeys (2.43): each consented event raw, with its address and email by the site's settings | same file, `recorded_events` (docs/JOURNEYS.md) | `journeys.vid_days` (30); address and email `privacy.keep_days` when shorter |
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
  (the script tag's `data-consent="required"`, above).
- **Addresses.** The receiver reads the caller's address only to limit
  failed signatures, in memory; it is never written. A site's own `lead`
  may pass the visitor's address once, for the country; it is dropped at
  once. A conversion holds no address: a person's visits are linked to a
  lead by the person search (people/lookup.py), through a visitor ID, an
  email, or the visits that sent a form within 2 minutes of the lead
  (matched by time, said as not certain).
- **Test marks.** `./bin/skald conversions list SITE [--test]` shows the latest
  rows with their ids; `./bin/skald conversions mark-test SITE ID... | --ref REF [--unmark]`
  marks them test (every row of the same tool and reference, so a booking's
  later stages too); a site's server marks its own `lead` refs with `POST
  .../leads/test` (INTEGRATIONS-LEADS.md). A test row is kept and listed, never counted: not in
  `conversions.json`, not abandoned; the second count leaves it out by its own SQL. Each
  change is an audit-log row (`conversions.test`/`untest`; actor `cli` or `hook:lead`).
- **Delete on request:** `./bin/skald conversions forget --email ADDRESS`,
  `--vid skv_...` or `--lead REF` (or `./bin/skald forget` with the same flags;
  try `--dry-run` first) deletes the conversions, the removed rows, the
  journeys of every visitor ID involved, the identity, the delivery rows and
  the hook spool lines, and takes the visitor ID out of the beacon spool's
  lines. `./bin/skald forget --ip` deletes the visits kept with an address.
  `privacy.log` gets a line with a hash prefix, never the value.
- **Pruning:** `skald conversions prune` applies the "kept" column
  above (conversions, removed rows, journeys, identities, deliveries, replay
  hashes, spool files). Nothing runs it by itself: not run-daily, not
  install.sh's cron, not the Docker scheduler. Add a daily line for it to
  `/etc/cron.d/skald` (Docker: the host's cron, `docker exec skald
  skald conversions prune`). The kept visits with addresses
  are pruned by run-daily on their own (`privacy.keep_days`).

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
reads their tool, reference and stage from `conversions.sqlite` by its own SQL
(`audit_conversions.test_keys`) and skips them in the spool, the beacon and
the lead recounts. run-daily compares the last 30 days
(`conversions.audit_days`) with `conversions.sqlite`; a day that disagrees
is withheld and run-daily ends "withheld". The beacon's counts of whole
days are kept in the audit's own file (`conversions-audit.json` beside the
history) so each redraw reads only the newest spool files; `conversions
forget` deletes it. Every figure of `conversions.json` is counted a second
time by SQL (`audit_conversions_figures.py`); see DATA-CONTRACT.md.

## Search Console, Bing and AI answers

These are in [INTEGRATIONS-SEARCH.md](INTEGRATIONS-SEARCH.md).
