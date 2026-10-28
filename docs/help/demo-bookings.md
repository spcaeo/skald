# Demo bookings

How booked calls from Calendly and Cal.com reach Skald, what each way can see, and how to keep only your own event types when one account books for several businesses.

## Three ways Calendly reaches Skald

| | Embedded on your page | A link to calendly.com | The Calendly webhook |
| --- | --- | --- | --- |
| Needs | The script tag | The script tag | A paid Calendly plan (Standard or higher) and the `calendly` hook |
| Opened the booking | Yes (`calendly_open`) | No: only a click out to calendly.com | No |
| Chose a time | Yes (`calendly_time_selected`) | No | No |
| Booked | Yes (`calendly_booked`) | No | Yes |
| Cancelled, rescheduled, no-show | No | No | Yes |
| Booked off your site (a link in an email) | No | No | Yes |
| Joined to the visitor's journey | Yes, with visitor IDs on | With visitor IDs on, through `utm_content` | Yes, through `utm_content`, with visitor IDs on |

- **Embedded** means Calendly's inline widget or popup on your own page. The script tag listens to Calendly's own messages in the page.
- **A link** sends the visitor away to calendly.com. The page sees only the click out. The script tag adds the visitor ID to the link as `utm_content`, so the webhook can join the booking to the journey.
- **The webhook** is Calendly telling Skald about each booking. It sees every booking, wherever it was made.

The best of both: embed the booking on your page, and turn on the webhook. Then you see opened, time chosen, booked, and what happened after.

## Set up the Calendly webhook

1. In Skald: **Settings > This site > Leads & tools > Calendly** (in **Bookings**) **> Make secret**. Copy the secret and the address.
2. In Calendly: make a personal access token (on Calendly's integrations page, under API and webhooks).
3. Find your organisation's URI:

```
curl -s https://api.calendly.com/users/me -H "Authorization: Bearer $CALENDLY_TOKEN"
```

4. Make the subscription. The `signing_key` is Skald's secret:

```
curl -sS -X POST https://api.calendly.com/webhook_subscriptions \
  -H "Authorization: Bearer $CALENDLY_TOKEN" -H 'Content-Type: application/json' \
  -d '{"url": "https://stats.example.com/traffic-hooks/example.com/calendly",
       "events": ["invitee.created", "invitee.canceled", "invitee_no_show.created"],
       "organization": "https://api.calendly.com/organizations/<ORG>",
       "scope": "organization", "signing_key": "<the hook secret>"}'
```

5. Press **Send a test event** in Calendly's details on Leads & tools. Then book a test call.

A booking counts as a demo completed; a cancellation as cancelled (or rescheduled, when Calendly says so); a no-show as no-show.

## Keep only your own event types

One Calendly account often books for several businesses. A Calendly webhook cannot be limited to some event types: it sends every booking of the account. So Skald filters them.

In **Settings > This site > Leads & tools > Calendly**, fill **Only these Calendly event types**, one per line. Any of these works:

- The event type's URI: `https://api.calendly.com/event_types/AAAA1111`. This always matches.
- Its id alone: `AAAA1111`.
- The booking page's slug: `product-demo`, or the page's address `https://calendly.com/example/product-demo`.

Calendly does not send the booking page's slug. So Skald compares a slug with the event type's **name** written as a slug: "Product demo" becomes `product-demo`. If you rename the event type, a slug stops matching. The URI never does.

To find the URI:

```
curl -s "https://api.calendly.com/event_types?user=<your user URI>" -H "Authorization: Bearer $CALENDLY_TOKEN"
```

Or wait for a booking of another type: the delivery log names each event type it left out, so you can copy the URI from there.

What happens then:

- A booking of a listed type is kept, as before.
- A booking of another type is answered 200, so Calendly does not send it again. It shows as "not a conversion" in Last deliveries, with the detail "other event type" and the type it named. Nothing else is kept: no conversion, no copy of the message.
- A no-show names only the person, not the event type. It is kept when its booking was kept.
- An empty list keeps every booking.

On a server without accounts, set it in the config:

```
hooks:
  calendly_event_types: [https://api.calendly.com/event_types/AAAA1111]
```

With PyYAML installed, the nested form works too: `hooks: {calendly: {event_types: [...]}}`.

## Cal.com

- **The webhook:** Settings > Developer > Webhooks > New. Subscriber URL: the `calcom` hook's address. Triggers: Booking Created, Booking Cancelled, Booking Rescheduled. Secret: the hook's secret.
- **The embed:** with the script tag on the page, Skald sees the booking open (`cal_open`) and booked (`cal_booked`).
- **The visitor ID:** pass it in the embed as `metadata[skv]=skv_...`, or as a hidden booking question named `skv`.
- **Event types:** **Only these Cal.com event types** in Cal.com's details on Leads & tools takes event type ids (`1234`) or slugs (`30min`, or the page's address `https://cal.com/example/30min`). Config: `hooks: {calcom_event_types: [...]}`.

## A relay of your own

Some sites want their own filtering, or to add something before Skald sees it. Then the site receives the tool's webhook itself:

1. Check the tool's signature with the tool's key.
2. Keep what you want. Drop the rest, and store nothing of it.
3. Sign the kept body again with Skald's `calendly` hook secret, in Calendly's scheme: `Calendly-Webhook-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">`.
4. Post it to `/traffic-hooks/example.com/calendly`.

For the common case, keeping some event types, the filter above does this for you. You do not need a relay.

See also [Webhooks](webhooks.md) for every tool, and [Leads and conversions](leads-and-conversions.md) for what started, completed and abandoned mean.
