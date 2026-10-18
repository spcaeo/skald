# Privacy

What Skald keeps about the people who visit, who can see it, for how long, and how a person is removed when they ask.

## The short version

- Skald can keep each visit with its IP address, so you can look a person up and follow them across days. That is a switch, on by default for a new install.
- It can keep the name and email of each lead with its conversions. Also a switch, on by default for a new install.
- An install upgraded from before version 2.4.0 keeps neither until you turn them on.
- Only owners and admins can look a person up. Every search is written to the audit log.
- Stored history (the totals) never holds an address.
- Nothing is hidden: spam, duplicate and test leads, and cancelled, removed and test conversions, are listed, not only counted.
- One command on the server removes a person everywhere Skald keeps them.

> Your privacy notice must say what you keep before you turn these on. Some places also need the visitor's consent.

## What is kept about a visit

When **Keep visitors' IP addresses** is on (**Settings > Data retention > People**), each visit is kept with:

- its IP address and browser string
- when it started and ended
- the pages it read, in order
- where it came from: source, referring site, campaign
- its country and device

A visit here is a visit that read at least one page, the same visit Traffic > Visitors counts. Visits are kept for 395 days by default (**Visits with addresses**). Turn the switch off and no address is kept from then on. The visits already kept with an address are deleted at the next nightly run.

These visits are kept apart from the history, in the conversions file on your server. They are counted twice like everything else: each morning Skald counts every address's visits again from the raw log, by separate code. A day that does not match is withheld.

## What is kept about a lead

When **Leads' names and emails** is **full**, the name and email of each lead are kept with its conversions. With **anonymous**, neither is kept.

Skald reads your website's lead database without changing it. Leads marked spam or duplicate there, and leads marked test, are left out of every figure. They are listed in full: on [Leads & sales > Pipeline](#sales/pipeline), turn on **Show left out**.

## Looking a person up

Owners and admins see a **Find a person** box at the top of every page; on a narrower screen it is a search icon. The same search is on [Leads & sales > People](#sales/people), and **Ctrl K** (or **Cmd K**) also offers **Find a person**. Type one of these:

- an IP address
- an email
- a lead's number or reference
- a visitor ID (`skv_...`)

The person opens in a panel on the right:

- **Linked**: the IP addresses, emails, visitor IDs and leads tied to them, and what this site keeps.
- **Visits**: every visit kept with that address, with its pages in order, source, referring site, country and device. A day whose figures did not add up is marked "withheld day".
- **Requests in the last 6 hours**: the address's requests from Site > Requests.
- **Leads**: their leads, spam and test ones too.
- **Leads and the visits that sent a form at their time**: visits that sent a form from 2 minutes before a lead to 30 seconds after it. This is a match by time only. It is likely the same person, never certain: the lead database keeps no address.
- **Conversions**: every conversion, cancelled and test ones too, and the rows removed by a sync.
- **Pages seen by its visitor IDs**, when the site has visitor IDs on.

Every address, email, lead and visitor ID in the panel is a link. Select it to open that one.

Each search is written to the [audit log](#settings/audit): who searched, when, and what kind of value. Never the value itself.

Viewers cannot look a person up. An API token or an AI assistant can, only with the **Read private files** scope. See [API](api.md) and [MCP](mcp.md).

## Where addresses appear

Addresses show only behind sign-in:

- The person search, for owners and admins.
- [Site > Requests](#site/requests): the last 6 hours of the request log.
- Today's AI activity, on [AI & bots > Assistants](#ai/assistants) when the period is Today (or **Today · Live** is on): today only.
- The internal-address list in [Internal traffic](#settings/internal), so your team can manage it.

They never appear in a stored day's totals, a CSV export of history, or a mail.

## How long things are kept

| What | Kept |
| --- | --- |
| Raw access logs, with addresses | 14 days on your server |
| Each visit with its address (when kept) | 395 days, or what you set |
| Leads' names and emails (when kept) | As long as their conversions: 400 days |
| Conversions removed by a sync, whole | 400 days |
| The Requests list, with addresses | Its 6-hour window |
| Today's AI activity, with addresses | Today only |
| Returning-visitor codes | 30 days |
| Anonymous journeys | 7 days |
| Per-visit and per-page detail | 400 days |
| In-page events from the script tag | 400 days |
| Totals and labels | For good |
| Backups of the history and the conversions file (the conversions file holds the kept visits, names and emails) | 14 daily and 8 weekly copies |

Admins can change most of these. See [Settings and retention](settings-and-retention.md).

## Turning it on after an upgrade

An install that ran a version before 2.4.0 keeps working as before: no address and no email is kept. The **People** card says "kept off by the upgrade to 2.4.0". To turn them on:

1. Change your privacy notice first, so it says what Skald keeps.
2. Open **Settings > Data retention**.
3. Under **People**, tick **Keep visitors' IP addresses**, and set **Leads' names and emails** to **full**.
4. Select **Save**. It applies from the next run.

On a server without the Settings pages, the server admin sets `privacy: keep_ips: true` and `conversions: identity: full` in the config file. With Docker, `SKALD_KEEP_IPS=1` and `SKALD_IDENTITY=full`.

## The script tag

The optional `skald.js` tag counts what happens inside a page. It is served from your own site and posts to your own site. No third-party code. See [Tracking script](tracking-script.md).

- **No cookie by default.** A cookie is set only if your site turns on visitor IDs and also asks to share them across subdomains.
- **Do Not Track and Global Privacy Control are respected.** A browser that sends either is not counted at all: no ID, no storage, no event.
- **Consent first, if you need it.** The tag can wait and send nothing until your consent banner says yes. When a visitor says no, the ID and anything stored are deleted.
- **Never a field's value.** Form events say which form was used, never what was typed. A click on a phone or email link never keeps the number or the address.

Visitor IDs are off by default, and set per site. With them on, the browser keeps a random ID. Turn them on for a site only when that site's privacy notice says so, and let its consent banner gate the tag where consent is needed.

## Webhooks and conversions

When a booking, form or payment tool sends Skald a webhook, Skald keeps only the fields it needs. Everything else is dropped before anything is written.

Always dropped:

- addresses and browser strings
- phone numbers
- answers to form questions and any free text
- cancel and reschedule links

Kept: the action (for example, a demo or a sign-up), its stage, the time, the tool, the tool's own reference, and the source, campaign, landing page, country and device. The name and email too, when **Leads' names and emails** is **full**. Skald's outgoing webhooks never send a name or an email.

See [Webhooks](webhooks.md) and [Leads and conversions](leads-and-conversions.md).

## Removing a person on request

If someone asks you to delete their data, the server admin removes it. It cannot be done from the dashboard. Use the search first to see what is kept about them.

1. Ask the person for their IP address or email (or a lead's reference).
2. Send it to the person who runs your Skald server.
3. The server admin runs `skald forget`, first with `--dry-run` to see what it would remove.

`skald forget --ip` with the address:

- Deletes every visit kept with that address.
- Replaces it with "(removed)" in the Requests list and today's AI activity.
- Deletes its returning-visitor codes.
- Keeps it hidden for 15 days, longer than the raw logs last. Visits in that time are kept without the address.
- Writes a line to a private log with the counts, never the address.

`skald forget --email` (or `--lead`, `--vid`) deletes that person's conversions, the rows removed by a sync, their name and email, and the page views of their visitor IDs.

The raw access logs rotate away after 14 days. The server admin can also scrub the address from them sooner. The lead itself, in your website's own database, is yours to delete there.

> Backups made before the request still hold what was kept then: the 30-day codes, and the copies of the conversions file, with the visits kept with addresses and the names and emails. They stay on your server, readable only by Skald, and age out on their own (14 daily and 8 weekly copies).

## Related guides

- [Settings and retention](settings-and-retention.md)
- [Leads and conversions](leads-and-conversions.md)
- [Internal traffic](internal-traffic.md)
- [FAQ](faq.md)
