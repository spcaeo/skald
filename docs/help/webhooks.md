# Webhooks

How to connect Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier, Make and your own site to Skald, so bookings, forms and payments show under Leads & sales. Also how Skald can send conversions out to your CRM.

## How it works

Each tool gets its own address in Skald and its own secret. When something happens (a booking, a payment, a form), the tool sends a signed message to that address. Skald checks the signature, records the conversion once, and lists it on [Leads & sales > Leads](#sales/leads), counts it on [Summary](#sales/summary) (with **Count from: Tools**) and, for a booking or a payment, on [Calendar bookings](#sales/bookings).

All of this is set up on one page: **Settings > This site > Leads & tools**, or [Leads & tools](#settings/site/leads). It starts with **Next step for example.com**: what Skald found on your site and the single most useful thing to connect, with one **Connect** (see [Leads & tools: what to connect next](leads-and-conversions.md#leads-tools-what-to-connect-next)). Then every source is in a group by what it is for (Leads from your forms, Bookings, Payments, Search, Your own tools, Recorded journeys, Send each lead out). Each row has its state (**Connected**, **Waiting**, **Failing**, **Not connected**), when it last sent, and one action: **Connect**, or its details. Press a row for its details: whether it works now, its key in the tool's own word (when it was saved and by whom), its address, Test Skald's address, the last deliveries, and Remove. A connected row also links to its data (**See leads**, **See bookings**). A red line with **Fix** shows only when something is broken. Sources that do not fit your site are folded under **More you can connect**. **Every check**, at the foot, lists each road into Skald with the server's own words. Each tool's details have their own link: `#settings/site/leads?tool=calendly`.

- You need to be an admin or owner of the site's organisation. Viewers do not see this page.
- The page needs a server with accounts. Without it, the page says so, and the person who runs your Skald server sets up hooks on the server instead.
- If you manage more than one site, choose the site at the top first.

Or let your AI agent do it: on **Settings > To do** (or the site's **Set up** list on Overview), press the **Lead hook tested** line, then pick **My AI agent**. It gets one line, looks for your form handler and the booking, form or payment tools in the code, adds what is missing, and reports which hooks it set and which it left for you. Secrets go straight from Skald into the tool or your server's settings, never into the chat. See [Your AI agent, in every set-up dialog](connections.md#your-ai-agent-in-every-set-up-dialog).

## A tool's details, and every check

**Every check** (`tool=checks`) lists each road into Skald for this site, with **OK**, **Needs attention** (and what to do) or **Off**: the hook receiver, the script tag, each hook that is set up, one lead sent by two tools, and the lead database. The server's doctor command (`skald doctor`; Docker: `docker exec skald skald doctor`) shows the same lines, and checks the rest of the install too.

Each tool's details (its row on Leads & tools), top to bottom:

- **The live line**: a pill (**Working**, **Waiting**, **Needs a fix**) and one sentence that update by themselves, with the next thing to do under it and **Check for a real one**. It says **Working** only once a real delivery was taken in since the key was saved.
- **Which way the key goes**, in one line, in the tool's own word. For example: "Skald gives Calendly a signing key; Calendly signs each booking with it."
- **What is saved**: "Signing key saved 28 Oct 10:16 by Ann (pasted)" or "(made by Skald)", with **Replace**. It stays after you save or make one, and after you close and open the details again.
- **One question first**, for the tools that take either key (Calendly, Cal.com, Typeform): see [The key](webhooks.md#the-key) below. Your answer is in the page's link (`&how=`), so a link opens on it.
- **The address**, with copy and open buttons. It looks like `https://analytics.example.com/traffic-hooks/example.com/calendly`. Always copy yours from the page.
- **Test Skald's address**, and the last real delivery beside it.
- **Details**, folded: the state in words, the last 50 deliveries (when, the answer, the outcome and any detail) and **Remove**.

A hook does nothing until it has a key. Without one, its address answers "not found".

### The key

Each tool calls its key by its own name, and Skald uses the same word:

| Tool | Its word | Who makes it |
| --- | --- | --- |
| Your site's server (lead), Zapier, Make, n8n (json) | secret | Skald: **Make the secret** |
| Calendly | signing key | Skald, or you chose one in the request that made the webhook |
| Cal.com, Typeform | secret | Skald, or the one the webhook already has |
| Stripe | signing secret | Stripe: paste it |
| HubSpot | client secret | your HubSpot app: paste it |

For Calendly, Cal.com and Typeform the details ask one question first, and show only that way:

- Calendly: **How was your Calendly webhook made?** **Not made yet** (Skald makes the signing key; the steps and the one API request have it filled in), **Made with an API request that had a signing_key** (paste that value), or **Made without a signing key, or not sure** (make the webhook again; see [Calendly](webhooks.md#calendly)).
- Cal.com and Typeform: **Has Cal.com given you a secret?** **No** (Skald makes it) or **Yes** (paste it).

A key Skald makes is shown once, with a copy button: "Shown once: copy it now". Give it to the tool (each section below says where), then press **I have copied it**. What is saved stays on the page; the key itself is never shown again. A pasted key is never shown either, not even to you.

After you save or make a key, Skald checks it against the tool's last refused deliveries and says what it found:

| The page says | What it means | What to do |
| --- | --- | --- |
| It matches Calendly's booking from 10:13. 8 bookings taken in. | The key is right. The bookings refused before are counted now. | Nothing. |
| This is not the key Calendly signs with: Calendly's delivery at 11:37 still does not match. | The value you pasted is not the one the tool signs with. | Copy the right one (the line says where), not your token or the webhook address, and paste again. |
| Calendly sends no signature: the webhook was made without a signing key. | The tool's deliveries carry no signature at all, so no key can match. | Make the webhook again with Skald's key (the page shows how). |
| Saved. Skald checks it against Calendly's next booking. | No refused delivery to check it against yet. | Book a test call, or wait for the next real one. |

> Treat a key like a password. Never put it in an email, a chat, a ticket or a shared document. Anyone with it can send fake conversions. If one leaks, make a new one (or a new one in the tool, and paste it): the old one stops working at once, and you give the new one to the tool.

If the details say the key is kept in the server's environment, it cannot be made, pasted or removed on this page: ask the person who runs your Skald server.

### Test Skald's address

**Test Skald's address** sends a signed sample to Skald's own receiver for that tool, signed with the key Skald holds. It checks the signature and reads the sample, then keeps nothing and counts nothing. So it proves that Skald's address answers, and nothing about the other tool: the page says "Skald's address answers. This does not check Calendly's signing key: only a real booking does." Beside it is the last real delivery: "Last real booking: refused at 11:37, the signing key does not match", "accepted at 10:13" or "none yet". The test shows as "test, read and not kept" in the deliveries.

The server has the same test: `skald hooks test example.com lead`.

Only a real delivery from the tool shows that the tool and Skald share the same key: book a test call, send a test form or payment, or use the tool's own "send test" button, then look at the live line.

## Calendly

Calendly sends webhooks on its paid plans (Standard or higher). Calendly webhooks are made with Calendly's API, usually by a developer, with a personal access token. The request that makes the webhook can carry a `signing_key`: a value you choose. Calendly signs each booking with it and never shows it again. A webhook made without one sends no signature, and no key can be added to it later. (A Calendly OAuth app has one signing key per app, in Calendly's developer portal.)

In Skald, open the **Calendly** details and answer **How was your Calendly webhook made?**

**Not made yet.** Skald makes the signing key and shows it once. The details then show the one request, with the address and the key filled in:

```
curl -X POST https://api.calendly.com/webhook_subscriptions \
  -H "Authorization: Bearer <your-calendly-token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://analytics.example.com/traffic-hooks/example.com/calendly",
       "events": ["invitee.created", "invitee.canceled", "invitee_no_show.created"],
       "organization": "<your-organization-uri>",
       "scope": "organization", "signing_key": "<the signing key>"}'
```

Your organisation's URI is `current_organization` in the answer to `curl -sS https://api.calendly.com/users/me -H "Authorization: Bearer <your-calendly-token>"`.

**Made with an API request that had a signing_key.** Paste that value (the `signing_key` of the request, not your Calendly token and not the webhook address) and press **Save signing key**. Skald says at once whether it matches the bookings Calendly sent.

**Made without a signing key, or not sure.** Make the webhook again: Skald makes a new signing key, then the details give two requests, each with a copy button. The first lists your webhooks (the old one has `"callback_url"` set to Skald's address) and deletes it by its `uri`. The second makes it again with Skald's key. **Let your AI agent do it** gives the same job to your AI agent, which runs both with your Calendly token and never shows the key.

What Skald records: a booking (Demos, completed), a cancellation (cancelled, or rescheduled when Calendly says so) and a no-show. To join a booking to the visitor's journey, the tracking script adds the visitor ID to Calendly links as `utm_content`. See [The tracking script](tracking-script.md).

### Only some event types

One Calendly account often books for several businesses, and a Calendly webhook cannot be limited to some event types. So tell Skald which are this site's:

1. In the **Calendly** box, find **Only these Calendly event types**.
2. Enter one per line: the event type's address from Calendly's API (`https://api.calendly.com/event_types/...`), or the booking page's name at the end of its link (`product-demo` in `https://calendly.com/you/product-demo`).
3. Press **Save event types**.

Any other event type is answered "OK" and left out: nothing is kept, and Last deliveries shows "not a conversion" with the event type it named, so you can copy it. A no-show is kept when its booking was kept. Leave the box empty to keep every event. Calendly does not send the booking page's name, so Skald compares it with the event type's name ("Product demo" is `product-demo`). If you rename the event type, use its address instead. See [Demo bookings](demo-bookings.md).

## Cal.com

1. In Skald, open the **Cal.com** details. To **Has Cal.com given you a secret?** answer **No**: Skald makes it. Copy the address and the secret.
2. In Cal.com, go to **Settings > Developer > Webhooks > New**.
3. **Subscriber URL**: paste the address.
4. **Event triggers**: Booking Created, Booking Cancelled, Booking Rescheduled.
5. **Secret**: paste the secret. Save.

If the Cal.com webhook already has a secret of its own, answer **Yes** and paste it into **Paste the secret from Cal.com** instead.

To join a booking to the journey, pass the visitor ID in the embed as `metadata[skv]`, or add a hidden booking question named `skv`.

To keep only some event types, enter their ids (`1234`) or names (`30min`) in **Only these Cal.com event types**, as for Calendly above.

## HubSpot

HubSpot signs its messages with your HubSpot app's **client secret**. Skald cannot make one for it.

1. In your HubSpot app, open **Auth** and copy the **Client secret**.
2. In Skald's **HubSpot** details, paste it into **Paste the client secret from HubSpot** and press **Save client secret**.
3. In your HubSpot app, open **Webhooks** and set the **Target URL** to the address from the **HubSpot** box.
4. Subscribe to `contact.creation` (counted as a Contact form), to `object.creation` for meetings (counted as a Demo), and to `deal.propertyChange` for `dealstage` (a deal moved to closed won counts as a won Deal).

You can also use a HubSpot workflow's **Send a webhook** action, signed by the same app. Skald counts it as a Contact form. To count it as something else, add a property `skald_action`, for example `demo` in a "meeting booked" workflow. Skald reads the properties `skv` (the visitor ID) and `utm_*`.

> If your HubSpot account cannot sign a workflow webhook, send it through Zapier or Make instead (below).

## Typeform

1. In Skald, open the **Typeform** details. To **Has Typeform given you a secret?** answer **No**: Skald makes it. Copy the address and the secret.
2. In Typeform, open your form, then **Connect > Webhooks > Add a webhook**. Paste the address.
3. Open the webhook's settings (**Edit**) and paste the secret into **Secret**. Save, and turn the webhook on.

If the Typeform webhook already has a secret of its own, answer **Yes** and paste it into **Paste the secret from Typeform** instead.

Typeform sends every response. Skald counts each as a Contact form, completed. To join it to the journey, add a hidden field `skv` to the form and fill it in the embed. Hidden `utm_*` fields give the last touch. Skald never reads the answers.

## Stripe

Stripe makes its own signing secret, which starts with `whsec_`.

1. In Stripe, go to **Developers > Webhooks > Add endpoint**.
2. **Endpoint URL**: paste the address from the **Stripe** box.
3. Events: `checkout.session.completed` and `checkout.session.async_payment_succeeded`; for revenue (2.32.0) also `invoice.paid` (a subscription's renewals), `invoice_payment.paid` (ties a renewal's payment to its invoice on Stripe's API 2025-03-31 and later, so its refund is found) and `charge.refunded` (refunds).
4. Save, then reveal the endpoint's **Signing secret**.
5. In Skald's **Stripe** details, paste it into **Paste the signing secret from Stripe** and press **Save signing secret**. Skald cannot make one for Stripe.

Skald counts a paid Checkout as a Payment. A Checkout paid by a delayed method counts as started first, then paid. To join it to the journey, set the visitor ID as the Checkout Session's `client_reference_id`, or as `metadata.skv`. Skald keeps each payment's amount and currency, and the Stripe customer ID (`cus_...`) so a renewal joins its first sale; a refund takes its amount off on the day it arrives, and a later, larger total takes the difference off on its own day. All of it shows on [Leads & sales > Revenue](#sales/revenue) ([Revenue](revenue.md)). Skald never reads the customer's name, email or address.

## Zapier and Make

Use the **Zapier, Make, n8n (json)** box. This hook takes the same fields as your own site's lead push (next section).

1. Press **Make the secret** in its details, and copy the address and the secret.
2. Keep the secret in the tool's own secure storage, not in a plain text step.
3. Send the secret as a plain key, with no code: a POST to the address with these headers and a JSON body.

```
POST https://analytics.example.com/traffic-hooks/example.com/json
Authorization: Bearer <your-secret>
Content-Type: application/json

{"external_ref": "form-123", "action": "contact", "email": "person@example.com", "name": "A Person"}
```

A sale carries its value too: `{"external_ref": "inv_1042", "action": "paid", "stage": "paid", "value": 49.00, "currency": "USD", "customer_ref": "cus_1001"}`. Polar, Dodo Payments, Paddle, Lemon Squeezy and Gumroad reach Skald this way: [Revenue](revenue.md) lists what to map for each.

- In **Zapier**: add **Webhooks by Zapier**, event **POST**. URL: the address. Payload Type: `json`. Data: `external_ref` (map the entry's id), `action` (such as `contact`), and `email`, `name` if you like. Headers: `Authorization` with the value `Bearer <your-secret>`.
- In **Make** or **n8n**: the HTTP module or node, method POST, body type JSON, the same header.
- **Form plugins** that post a webhook with your own headers (WordPress form add-ons, Webflow, Tally and others) work the same way. For a WordPress site, the Skald Leads plugin needs no set-up at all: see [Send leads from your backend](leads-from-your-backend.md).

The plain key works on this hook and on **Your site's server (lead)** only, and only when the message has no `X-Skald-Signature`. A wrong key is refused like a bad signature. Use the address exactly as shown, starting with `https://`: the key travels with each message. A tool that can sign may sign instead (next section); in Make, set the header `X-Skald-Signature` to `t={{timestamp}},v1={{sha256(timestamp + "." + body; "hex"; secret)}}`.

One message can carry one record, a list of them, or `{"records": [...]}`, up to 100.

## Your own site's lead push

If your website's database is not read by Skald directly, your site's server can tell Skald each time a lead is made. Use the **Your site's server (lead)** box.

The quickest way: download the one file for your site's language from that box (PHP, Node, Python, or a WordPress plugin that needs no code) and call one function when a form is saved. See [Send leads from your backend](leads-from-your-backend.md). To write it yourself:

1. Press **Make the secret**, and copy the address and the secret.
2. Give both to your developer. They keep the secret in the server's settings, never in the code.
3. Your server sends a `POST` with a JSON body and this header:

```
X-Skald-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">
```

The key is the secret. Skald refuses a time more than 5 minutes off its own clock. A sender that cannot sign can send `Authorization: Bearer <your-secret>` instead (see Zapier and Make, above).

| Field | Needed | What |
| --- | --- | --- |
| `external_ref` | yes | the lead's own ID in your site |
| `action` | yes | a short word: `demo`, `signup`, `contact`, `trial` |
| `stage` | no | `started`, `completed` (the default), `cancelled`, `rescheduled`, `no_show`, `paid` |
| `at` | no | when, as an ISO time with its offset, such as `2026-09-25T14:30:00-04:00`; default: when it arrived. A time without an offset is read in the site's time zone, and Last deliveries says so |
| `vid` | no | the visitor ID the page had |
| `first_touch`, `last_touch` | no | referrer, landing page, `utm_*` tags, ad click ids, time |
| `country` or `ip` | no | two letters, or the visitor's address: Skald finds the country and drops the address |
| `device` or `user_agent` | no | Desktop, Mobile or Tablet, or the browser string: Skald works out the device and drops it |
| `name`, `email` | no | kept only when the site's **Leads' names and emails** is **full**; otherwise dropped |

A short test from a terminal:

```
BODY='{"external_ref":"L-1001","action":"demo"}'
T=$(date +%s)
SIG=$(printf '%s.%s' "$T" "$BODY" | openssl dgst -sha256 -hmac "<your-secret>" -hex | sed 's/^.* //')
curl -X POST 'https://analytics.example.com/traffic-hooks/example.com/lead' \
  -H 'Content-Type: application/json' -H "X-Skald-Signature: t=$T,v1=$SIG" --data-raw "$BODY"
```

> If Skald already reads your website's lead database, you do not need the lead push. See [Leads and conversions](leads-and-conversions.md).

The full how-to, with examples in curl, Node, Python and PHP, retries and backfilling: [Send leads from your backend in 5 minutes](leads-from-your-backend.md). If your server and Skald share a machine behind Cloudflare, post to Skald's local address: the guide says how.

## What Skald stores, and what it drops

- **Kept**: the action, its stage, the time, the tool, the tool's own reference, the visitor ID (only when the site has visitor IDs on), and the source, campaign, landing page, country and device when known.
- **Kept for checking**: a copy of each verified message, cut down to the fields Skald reads. It is kept as long as the leads (400 days, or for good: **Settings > This site > Privacy > Leads**), so every figure can be counted a second time.
- **Always dropped**: IP addresses, browser strings, phone numbers, extra email addresses, form answers, customer details, and Calendly's cancel and reschedule links.
- **Names and emails**: kept only when **Leads' names and emails** is **full** (**Settings > This site > Privacy > People**). That is the default for a new install. An install upgraded from before 2.4.0 drops them until an admin turns it on. Your privacy notice must say so. See [Privacy](privacy.md).
- **The delivery log**: when, the outcome and the answer, never the message itself. Kept 90 days.

## Duplicates and retries

- A tool sends again when it does not get an "OK" answer. This is harmless.
- Skald keeps each conversion once per tool, reference and stage. A repeat is answered "OK" and shows as "already had it" in Last deliveries. Nothing is counted twice.
- Cal.com and Typeform sign no time, so Skald also remembers each message for 30 days and ignores an exact repeat.
- **One lead, one road.** Each tool keeps its own record, so the same lead sent through two tools (your lead push and Zapier, or the lead push and the lead database) counts twice. The **Status** list names any lead that arrived from two tools: send each lead one way only.
- If Skald cannot save a message, it answers with an error, and the tool sends it again later.

## Remove an integration

1. Delete the webhook in the other tool (Calendly, Cal.com, HubSpot, Typeform, Stripe, Zapier or Make).
2. In Skald, press **Remove** in that tool's box, then **Yes, remove**.

Skald deletes the hook's secret. Its address then refuses every message, as if it had never been set up. **Last deliveries** stays, and the removal is in the audit log. To use the tool again, make or paste a secret.

If the secret is kept on the server (**set (environment ...)**), there is no Remove button: ask the person who runs your Skald server.

Conversions already recorded stay. To delete one person's data, see [Leads and conversions](leads-and-conversions.md).

## Sending conversions out (outgoing webhooks)

Skald can tell your CRM, Zapier, Make or Slack each time something happens. This is **Send each lead out** on the same page ([Send each lead out](#settings/site/leads?tool=webhooks)).

1. Under **Add an outgoing webhook**, paste the **Address**. It must start with `https://`.
2. Tick the **Events** you want: `conversion.started`, `conversion.completed`, `conversion.cancelled`, `conversion.rescheduled`, `conversion.no_show`, `conversion.abandoned`, `lead.won`, `lead.lost`, `ai.reading_changed` (an AI assistant started or stopped reading a page, or visits likely sent by AI answers jumped or vanished: see the FAQ), `alert.opened` (any alert, when it opens), and `todo.new` (a new to-do on Overview > Insights: its title, proof, figures and the link that opens **Fix this**; never a code and never its rows. See [What to fix](what-to-fix.md)).
3. Press **Add webhook**. Copy the secret shown once, and give it to the receiving tool so it can check each message.
4. Press **Send a test** to check that the address answers.

An `ai.reading_changed` message names the assistant, the pages, the days and the numbers, and is sent once per alert, only while alerts are on. An `alert.opened` message is sent once for each new alert of any kind (site down, a first AI citation, a crawler gone silent, a sale or a refund when those alerts are on, ...): the site, the alert, its text, its figures with their unit (visits or requests) and the time. A sale alert's figures also carry the amount, its currency and where the lead came from, never a name, an email or the customer reference. Each conversion message names the action, its source, campaign, landing page, country, device, visits and time before converting, and the anonymous journey. It never holds a name or an email. A failed delivery is tried again for about 15 hours. Only conversions recorded after you add the webhook are sent. **Remove** stops it at once.

### Alerts in Slack

Slack's incoming webhooks take only a short text. Skald knows a Slack address and sends the alert's text in Slack's own shape.

1. In Slack, add an **Incoming Webhook** to the channel and copy its address. It starts with `https://hooks.slack.com/`.
2. In Skald, under **Add an outgoing webhook**, paste it, tick `alert.opened`, and press **Add webhook**. Slack does not check the secret, so you can ignore it.
3. Press **Send a test**. A line appears in the channel.

Each new alert then posts one message: the site, the title and the detail with its numbers. Any other address gets the full message, signed.

Sending is opt-in: nothing leaves Skald until an admin adds a webhook. Each delivery has 10 seconds. A failed one is tried again after 1 minute, 5 minutes, 30 minutes, 2 hours and 12 hours, then given up.

## Troubleshooting

Open the tool's box and look at **Last deliveries**. The **Outcome** column says what happened:

| Outcome | What it means | What to do |
| --- | --- | --- |
| kept | recorded | nothing |
| already had it | a repeat of a message already kept | nothing |
| not a conversion | an event Skald does not count, or (with a detail "other event type") a Calendly or Cal.com event type this site does not keep | choose the events listed above; or add the event type to the list |
| test, read and not kept | a test | nothing |
| bad signature | the secret (or the `Bearer` key) does not match, or the time is more than 5 minutes off | paste the secret again, or rotate it and give the new one; check the sender's clock |
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
