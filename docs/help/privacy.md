# Privacy

What Skald keeps, what it never stores, and how an address is removed when someone asks.

## The short version

- Stored history holds totals and labels only. Never a visitor's address or browser details.
- Visitor addresses appear only on the private dashboard, for a short time.
- Raw logs stay on your server for 14 days, then rotate away.
- The script tag sets no cookie by default and respects Do Not Track.
- One command on the server removes an address on request.

## What is never stored in history

Skald works out each visit from the server's access log. The address is used to sort each request into a group and to group a visit. Then it is dropped.

- **No address and no browser string** of a visitor goes into the stored history. History holds totals and labels: a country, a device, a source, a page.
- **Visits are grouped in memory.** The key that groups one visit's requests is made with a random value for that run alone. It is never stored.
- **Returning visitors use a one-way code**, not the address. The code is made from the address with a secret kept on the server, and cannot be turned back into the address. Codes are deleted after 30 days (the **Returning-visitor matching** window in **Settings > This site > Data retention**).
- **Journeys are anonymous**: start time, country, device, source and pages in order. No address, no browser string, no code. They are deleted after 7 days by default.
- **Leads are counts only.** Skald reads the website's own lead database without changing it, and never shows a name, an email, a phone number or a message. Each lead's details stay in your website's own admin.

## Where addresses do appear

Addresses show in three places, all behind sign-in:

- [Requests](#requests): the last 6 hours of the request log.
- Today's AI activity, on [Live](#live): today only.
- The internal-address list in [Internal traffic](#settings/internal), so your team can manage it. Admins may read it.

They never appear in a stored day, a CSV export of history, or a mail. An API token sees them only if it was made with the private scope. See [API](api.md).

## How long things are kept

| What | Kept |
| --- | --- |
| Raw access logs, with addresses | 14 days on your server |
| The Requests list, with addresses | Its 6-hour window |
| Today's AI activity, with addresses | Today only |
| Returning-visitor codes | 30 days |
| Anonymous journeys | 7 days |
| Per-visit and per-page detail | 400 days |
| In-page events from the script tag | 400 days |
| Totals and labels | For good |
| Backups of the history | 14 daily and 8 weekly copies |

Admins can change most of these. See [Settings and retention](settings-and-retention.md).

## The script tag

The optional `skald.js` tag counts what happens inside a page. It is served from your own site and posts to your own site. No third-party code. See [Tracking script](tracking-script.md).

- **No cookie by default.** A cookie is set only if your site turns on anonymous visitor IDs and also asks to share them across subdomains.
- **Do Not Track and Global Privacy Control are respected.** A browser that sends either is not counted at all: no ID, no storage, no event.
- **Consent first, if you need it.** The tag can wait and send nothing until your consent banner says yes. When a visitor says no, the ID and anything stored are deleted.
- **Never a field's value.** Form events say which form was used, never what was typed. A click on a phone or email link never keeps the number or the address.
- **No address is stored with an event.** Each event keeps the page, the event's name, the source of the visit and the time.

Anonymous visitor IDs are off by default. With them on, the browser keeps a random ID that holds no name, email or fingerprint. Turn them on only when your privacy notice says so.

## Webhooks and conversions

When a booking, form or payment tool sends Skald a webhook, Skald keeps only the fields it needs to count the conversion. Everything else is dropped before anything is written.

Always dropped:

- addresses and browser strings
- names, emails and phone numbers
- answers to form questions and any free text
- cancel and reschedule links

What is kept: the action (for example, a demo or a sign-up), its stage, the time, the tool, the tool's own reference, and the source, campaign, landing page, country and device.

A site can choose to keep the name and email of a conversion, but only if it says so in its privacy notice. Even then, Skald's outgoing webhooks never send a name or an email. Skald never matches a visitor by address.

See [Webhooks](webhooks.md) and [Leads and conversions](leads-and-conversions.md).

## Removing an address on request

If someone asks you to delete their data, the server admin removes it. It cannot be done from the dashboard.

1. Ask the person for the address (and, for conversions, the email address or reference) they want removed.
2. Send it to the person who runs your Skald server.
3. The server admin runs Skald's forget command. They try it first in a mode that only shows what it would remove.

What the forget command does:

- Replaces that address with "(removed)" in the Requests list and today's AI activity.
- Deletes that address's returning-visitor codes.
- Keeps the address hidden for 15 days, longer than the raw logs last, so it does not come back.
- Writes a line to a private log with the counts, never the address.

Totals and journeys hold no address, so they do not change.

The raw access logs rotate away after 14 days. The server admin can also scrub the address from them sooner.

For conversions, a separate forget command removes them by email address, visitor ID or lead reference: the conversions, their journeys, any name and email kept, and the delivery records. The lead itself, in your website's own database, is yours to delete there.

> Backups made before the request still hold the 30-day codes. They hold no address, the codes cannot be read without the server's secret, and the backups age out on their own.

## Related guides

- [Settings and retention](settings-and-retention.md)
- [Internal traffic](internal-traffic.md)
- [FAQ](faq.md)
