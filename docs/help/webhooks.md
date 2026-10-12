# Webhooks

How to connect Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier, Make and your own site to Skald, so bookings, forms and payments show on the Conversions page. Also how Skald can send conversions out to your CRM.

## How it works

Each tool gets its own address in Skald and its own secret. When something happens (a booking, a payment, a form), the tool sends a signed message to that address. Skald checks the signature, records the conversion once, and shows it on [Conversions](#conversions).

All of this is set up on one page: **Settings > This site > Integrations**, or [Integrations](#settings/integrations).

- You need to be an admin or owner of the site's organisation. Viewers do not see this page.
- The page needs a server with accounts. Without it, the page says so, and the person who runs your Skald server sets up hooks on the server instead.
- If you manage more than one site, choose the site at the top first.

## The Integrations page

Under **Incoming hooks**, each tool has a box with:

- Its **address**, with a copy button. It looks like `https://analytics.example.com/traffic-hooks/example.com/calendly`. Always copy yours from the page.
- A badge: **no secret**, **secret set**, or **set (environment ...)** when the secret is kept on the server.
- **Make secret** (or **Rotate secret** once there is one), for the tools that take a secret Skald makes.
- **Paste the signing secret from ...**, for the tools that make their own secret (Stripe, HubSpot). Calendly, Cal.com and Typeform have both: use either one.
- **Send a test event**.
- **Remove**, once the hook has a secret.
- **Last deliveries**: the last 50 messages, with when, the answer, the outcome and any detail.

A hook does nothing until it has a secret. Without one, its address answers "not found".

### The secret

Who makes the secret depends on the tool:

| Tool | The secret |
| --- | --- |
| Your site's server (lead), Zapier, Make, n8n (json) | Skald makes it: **Make secret** |
| Calendly, Cal.com, Typeform | Either one: **Make secret** and give it to the tool, or paste the tool's own |
| Stripe, HubSpot | The tool makes it: **Paste the signing secret from ...** |

To make a secret in Skald:

1. Press **Make secret**.
2. The secret is shown once, with the address. Copy both.
3. Paste the secret into the other tool (each section below says where).
4. Press **I have copied it**. The secret is not shown again.

To paste a tool's own secret:

1. Copy the signing secret in the other tool (each section below says where).
2. In that tool's box in Skald, paste it into **Paste the signing secret from ...**.
3. Press **Save secret**. The box says **secret set**. Skald never shows the secret again, not even to you.

To replace a pasted secret, paste the new one and save again.

> Treat a secret like a password. Never put it in an email, a chat, a ticket or a shared document. Anyone with it can send fake conversions. If one leaks, press **Rotate secret** (or make a new secret in the tool and paste it): the old one stops working at once, and you give the new one to the tool.

If the box says **set (environment ...)**, the secret is kept on the server. It cannot be made, pasted or removed on this page: ask the person who runs your Skald server.

### The test button

**Send a test event** sends a signed sample to Skald's own receiver for that tool. It checks the signature and reads the sample, then keeps nothing and counts nothing. The page says "the test was signed, received and read". The test shows as "test, read and not kept" in Last deliveries.

The test checks Skald's side only. To check the other tool, use its own "send test" button, if it has one, and look at Last deliveries.

## Calendly

Calendly sends webhooks on its paid plans (Standard or higher). It has no screen for them: they are made through Calendly's API, usually by a developer.

1. In Skald, open the **Calendly** box, press **Make secret**, and copy the address and the secret.
2. Make a webhook subscription in Calendly with that address. Use the secret as the subscription's **signing key**.
3. Choose these events: `invitee.created`, `invitee.canceled`, `invitee_no_show.created`.

If your subscription already has a signing key from Calendly, paste that key into **Paste the signing secret from Calendly** instead of making one.

A developer can make the subscription with one request:

```
curl -X POST https://api.calendly.com/webhook_subscriptions \
  -H "Authorization: Bearer <your-calendly-token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://analytics.example.com/traffic-hooks/example.com/calendly",
       "events": ["invitee.created", "invitee.canceled", "invitee_no_show.created"],
       "organization": "https://api.calendly.com/organizations/<your-organization-id>",
       "scope": "organization", "signing_key": "<your-secret>"}'
```

What Skald records: a booking (Demos, completed), a cancellation (cancelled, or rescheduled when Calendly says so) and a no-show. To join a booking to the visitor's journey, the tracking script adds the visitor ID to Calendly links as `utm_content`. See [The tracking script](tracking-script.md).

## Cal.com

1. In Skald, open the **Cal.com** box, press **Make secret**, and copy the address and the secret.
2. In Cal.com, go to **Settings > Developer > Webhooks > New**.
3. **Subscriber URL**: paste the address.
4. **Event triggers**: Booking Created, Booking Cancelled, Booking Rescheduled.
5. **Secret**: paste the secret. Save.

If the Cal.com webhook already has a secret of its own, paste it into **Paste the signing secret from Cal.com** in Skald instead.

To join a booking to the journey, pass the visitor ID in the embed as `metadata[skv]`, or add a hidden booking question named `skv`.

## HubSpot

HubSpot signs its messages with your HubSpot app's **client secret**. Skald cannot make one for it.

1. In your HubSpot app, open **Auth** and copy the **Client secret**.
2. In Skald's **HubSpot** box, paste it into **Paste the signing secret from HubSpot** and press **Save secret**.
3. In your HubSpot app, open **Webhooks** and set the **Target URL** to the address from the **HubSpot** box.
4. Subscribe to `contact.creation` (counted as a Contact form), to `object.creation` for meetings (counted as a Demo), and to `deal.propertyChange` for `dealstage` (a deal moved to closed won counts as a won Deal).

You can also use a HubSpot workflow's **Send a webhook** action, signed by the same app. Skald counts it as a Contact form. To count it as something else, add a property `skald_action`, for example `demo` in a "meeting booked" workflow. Skald reads the properties `skv` (the visitor ID) and `utm_*`.

> If your HubSpot account cannot sign a workflow webhook, send it through Zapier or Make instead (below).

## Typeform

1. In Skald, open the **Typeform** box, press **Make secret**, and copy the address and the secret.
2. In Typeform, open your form, then **Connect > Webhooks > Add a webhook**. Paste the address.
3. Open the webhook's settings (**Edit**) and paste the secret into **Secret**. Save, and turn the webhook on.

If the Typeform webhook already has a secret of its own, paste it into **Paste the signing secret from Typeform** in Skald instead.

Typeform sends every response. Skald counts each as a Contact form, completed. To join it to the journey, add a hidden field `skv` to the form and fill it in the embed. Hidden `utm_*` fields give the last touch. Skald never reads the answers.

## Stripe

Stripe makes its own signing secret, which starts with `whsec_`.

1. In Stripe, go to **Developers > Webhooks > Add endpoint**.
2. **Endpoint URL**: paste the address from the **Stripe** box.
3. Events: `checkout.session.completed` and `checkout.session.async_payment_succeeded`.
4. Save, then reveal the endpoint's **Signing secret**.
5. In Skald's **Stripe** box, paste it into **Paste the signing secret from Stripe** and press **Save secret**. Skald cannot make a secret for Stripe.

Skald counts a paid Checkout as a Payment. A Checkout paid by a delayed method counts as started first, then paid. To join it to the journey, set the visitor ID as the Checkout Session's `client_reference_id`, or as `metadata.skv`. Skald never reads customer details.

## Zapier and Make

Use the **Zapier, Make, n8n (json)** box. This hook takes the same fields as your own site's lead push (next section), signed the same way.

1. Press **Make secret** in that box, and copy the address and the secret.
2. Keep the secret in the tool's own secure storage, not in a plain text step.
3. In **Zapier**, add a "Code by Zapier" step that signs the body and posts it (the example in the next section works).
4. In **Make**, use the HTTP module. Set the header `X-Skald-Signature` to `t={{timestamp}},v1={{sha256(timestamp + "." + body; "hex"; secret)}}`.

One message can carry one record, a list of them, or `{"records": [...]}`, up to 100.

## Your own site's lead push

If your website's database is not read by Skald directly, your site's server can tell Skald each time a lead is made. Use the **Your site's server (lead)** box.

1. Press **Make secret**, and copy the address and the secret.
2. Give both to your developer. They keep the secret in the server's settings, never in the code.
3. Your server sends a `POST` with a JSON body and this header:

```
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">
```

The key is the secret. Skald refuses a time more than 5 minutes off its own clock.

| Field | Needed | What |
| --- | --- | --- |
| `external_ref` | yes | the lead's own ID in your site |
| `action` | yes | a short word: `demo`, `signup`, `contact`, `trial` |
| `stage` | no | `started`, `completed` (the default), `cancelled`, `rescheduled`, `no_show`, `paid` |
| `at` | no | when, as an ISO time; default: when it arrived |
| `vid` | no | the visitor ID the page had |
| `first_touch`, `last_touch` | no | referrer, landing page, `utm_*` tags, ad click ids, time |
| `country` or `ip` | no | two letters, or the visitor's address: Skald finds the country and drops the address |
| `device` or `user_agent` | no | Desktop, Mobile or Tablet, or the browser string: Skald works out the device and drops it |
| `name`, `email` | no | kept only if your server is set to keep them; otherwise dropped |

A short test from a terminal:

```
BODY='{"external_ref":"L-1001","action":"demo"}'
T=$(date +%s)
SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "<your-secret>" -hex | sed 's/^.* //')
curl -X POST 'https://analytics.example.com/traffic-hooks/example.com/lead' \
  -H 'Content-Type: application/json' -H "X-Skald-Signature: t=$T,v1=$SIG" --data-raw "$BODY"
```

> If Skald already reads your website's lead database, you do not need the lead push. See [Leads and conversions](leads-and-conversions.md).

## What Skald stores, and what it drops

- **Kept**: the action, its stage, the time, the tool, the tool's own reference, the visitor ID, and the source, campaign, landing page, country and device when known.
- **Kept for checking**: a copy of each verified message, cut down to the fields Skald reads. It is kept 400 days, so every figure can be counted a second time.
- **Always dropped**: IP addresses, browser strings, phone numbers, extra email addresses, form answers, customer details, and Calendly's cancel and reschedule links.
- **Names and emails**: dropped, unless the person who runs your server has turned on keeping them for your site. Your privacy notice must then say so.
- **The delivery log**: when, the outcome and the answer, never the message itself. Kept 90 days.

## Duplicates and retries

- A tool sends again when it does not get an "OK" answer. This is harmless.
- Skald keeps each conversion once per tool, reference and stage. A repeat is answered "OK" and shows as "already had it" in Last deliveries. Nothing is counted twice.
- Cal.com and Typeform sign no time, so Skald also remembers each message for 30 days and ignores an exact repeat.
- If Skald cannot save a message, it answers with an error, and the tool sends it again later.

## Remove an integration

1. Delete the webhook in the other tool (Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier or Make).
2. In Skald, press **Remove** in that tool's box, then **Yes, remove**.

Skald deletes the hook's secret. Its address then refuses every message, as if it had never been set up. **Last deliveries** stays, and the removal is in the audit log. To use the tool again, make or paste a secret.

If the secret is kept on the server (**set (environment ...)**), there is no Remove button: ask the person who runs your Skald server.

Conversions already recorded stay. To delete one person's data, see [Leads and conversions](leads-and-conversions.md).

## Sending conversions out (outgoing webhooks)

Skald can tell your CRM, Zapier, Make or Slack each time something happens. This is under **Outgoing webhooks** on the same page.

1. Under **Add an outgoing webhook**, paste the **Address**. It must start with `https://`.
2. Tick the **Events** you want: `conversion.started`, `conversion.completed`, `conversion.cancelled`, `conversion.rescheduled`, `conversion.no_show`, `conversion.abandoned`, `lead.won`, `lead.lost`, and `ai.reading_changed` (an AI assistant started or stopped reading a page, or visits likely sent by AI answers jumped or vanished: see the FAQ).
3. Press **Add webhook**. Copy the secret shown once, and give it to the receiving tool so it can check each message.
4. Press **Send a test** to check that the address answers.

An `ai.reading_changed` message names the assistant, the pages, the days and the numbers, and is sent once per alert, only while alerts are on. Each conversion message names the action, its source, campaign, landing page, country, device, visits and time before converting, and the anonymous journey. It never holds a name or an email. A failed delivery is tried again for about 15 hours. Only conversions recorded after you add the webhook are sent. **Remove** stops it at once.

## Troubleshooting

Open the tool's box and look at **Last deliveries**. The **Outcome** column says what happened:

| Outcome | What it means | What to do |
| --- | --- | --- |
| kept | recorded | nothing |
| already had it | a repeat of a message already kept | nothing |
| not a conversion | an event Skald does not count | choose the events listed above |
| test, read and not kept | a test | nothing |
| bad signature | the secret does not match, or the time is more than 5 minutes off | paste the secret again, or rotate it and give the new one; check the sender's clock |
| not readable | the message is not what this tool sends | check you used the address for the right tool |
| too large | the message is over 64 KB | send fewer records at once |
| too many | over 60 messages a minute | the tool will retry; send in smaller batches |
| error | Skald could not save it | the tool will retry; tell the person who runs your server if it repeats |

- **No deliveries at all**: the tool is not sending. Check the address is pasted exactly, and that the webhook is turned on in the tool.
- **The box says "no secret"**: the address answers "not found" until a secret is set. A removed hook says this too.
- **"A Stripe signing secret starts with whsec_"**: you copied something else, such as an API key. Copy the endpoint's **Signing secret** in Stripe.
- **A red note says the site's hooks are not answered**: this server does not report on that site yet.
- **Bookings show but have no journey**: the visitor ID did not reach the tool. Check visitor IDs are on, and the hidden field or `utm_content` above.
- **HubSpot "bad signature" behind a proxy**: the person who runs your server may need to set Skald's public address.
