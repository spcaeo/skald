# Privacy

What Skald keeps about the people who visit, who can see it, for how long, and how a person is removed when they ask.

## The short version

- Skald can keep each visit with its IP address, so you can look a person up and follow them across days. You choose: the full address, a shortened one with its last part removed, or none. A new install keeps the full address.
- It can keep the name and email of each lead with its conversions. Also a switch, on by default for a new install.
- An install upgraded from before version 2.4.0 keeps neither until you turn them on.
- Only owners and admins can look a person up. Every search is written to the audit log.
- Only owners and admins see the leads' names and emails on [Leads & sales > Leads](#sales/leads). Each time the list shows them, the audit log gets one line, "lead list viewed", with the period and the number of rows: never a name or an email. Other members see the same list without them.
- Stored history (the totals) never holds an address.
- Nothing is hidden: spam, duplicate and test leads, and cancelled, removed and test conversions, are listed, not only counted.
- One command on the server removes a person everywhere Skald keeps them.
- **Settings > Data retention** gives you wording for your privacy notice, made from what this site keeps.

> Your privacy notice must say what you keep before you turn these on. Some places also need the visitor's consent.

## What is kept about a visit

**Keep visitors' IP addresses** (**Settings > Data retention > People**) has three choices. Only owners and admins can change it.

- **Full address**: each visit is kept with its whole IP address.
- **Shortened (last part removed)**: each visit is kept with a shortened address. It no longer points to one device, but visits can still be followed, more loosely.
- **Don't keep**: no address is kept with the visits.

With the full or the shortened address, each visit is kept with:

- its IP address (full or shortened) and browser string
- when it started and ended
- the pages it read, in order
- where it came from: source, referring site, campaign
- its country and device

A visit here is a visit that read at least one page, the same visit Traffic > Visitors counts. Visits are kept for 395 days by default (**Visits with addresses**).

### How an address is shortened

- An IPv4 address loses its last part: `203.0.113.57` is kept as `203.0.113.0`.
- An IPv6 address keeps its first 48 bits, and the rest is zeroed: `2001:db8:85a3:8d3::` is kept as `2001:db8:85a3::`.
- An IPv4 address written the IPv6 way (`::ffff:203.0.113.57`) is treated as IPv4.

The country and city are looked up from the full address before it is shortened. Everything else Skald works out from the raw log is the same in every choice: which visits are bots, which are your own team's, and every total.

A shortened address can be several people: everyone on the same network, or neighbours at the same internet provider. So with shortened addresses, visits linked "by address" are a weaker link, and the person panel says so.

### Changing the choice

- **Full to shortened**: the addresses already kept are shortened at the next nightly run.
- **Shortened to full**: only new visits are kept in full. The visits kept before stay shortened.
- **To Don't keep**: no address is kept from then on. The visits already kept with an address are deleted at the next nightly run.

These visits are kept apart from the history, in the conversions file on your server. They are counted twice like everything else: each morning Skald counts every address's visits again from the raw log, by separate code. A day that does not match is withheld.

## What is kept about a lead

When **Leads' names and emails** is **full**, the name and email of each lead are kept with its conversions. With **anonymous**, neither is kept.

Skald reads your website's lead database without changing it. Leads marked spam or duplicate there, and leads marked test, are left out of every figure. They are listed in full: on [Leads & sales > Leads](#sales/leads), open **More** and turn on **Show left out**.

## Looking a person up

Owners and admins see a **Find a person** box at the top of every page; on a narrower screen it is a search icon. The same search is on [Leads & sales > Find a person](#sales/people), and **Ctrl K** (or **Cmd K**) also offers **Find a person**. Type one of these:

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

When the site keeps shortened addresses, type the full address: it finds the visits kept under its shortened form. The panel says the address is shortened, and that those visits may be several people's.

Each search is written to the [audit log](#settings/audit): who searched, when, and what kind of value. Never the value itself.

Viewers cannot look a person up. An API token or an AI assistant can, only with the **Reading visitor addresses** scope (read_private). See [Connections](connections.md), [API](api.md) and [MCP](mcp.md).

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
| Leads, with their names and emails (when kept) | 400 days, or for good: Settings › Data retention › Leads |
| Conversions removed by a sync, whole | As long as the leads |
| Pages read with a visitor ID that became a lead | As long as the lead |
| Pages read with a visitor ID that has no lead | 30 days, or what you set (1 to 400) |
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
3. Under **People**, choose **Full address** or **Shortened (last part removed)** for **Keep visitors' IP addresses**, and set **Leads' names and emails** to **full**.
4. Select **Save**. It applies from the next run.

On a server without the Settings pages, the server admin sets `privacy: keep_ips: full` (or `short`) and `conversions: identity: full` in the config file. With Docker, `SKALD_KEEP_IPS=1` (or `short`) and `SKALD_IDENTITY=full`. The older `true` and `false` still work, as full and off.

## Wording for your privacy notice

**Settings > Data retention** has a card, **Wording for your privacy notice**. It is a short text you can paste into your privacy page, with a **Copy** button. It is made from this site's own settings, so it says exactly what is kept:

- that Skald reads your server's log to count visits, and that this sets no cookie and stores nothing on the visitor's device;
- that the raw log, the 6-hour Requests list and today's AI activity hold full addresses for that short time, in every choice;
- whether IP addresses are kept in full, shortened or not at all, and for how long;
- whether leads' names and emails are kept;
- if the site uses the script tag: whether it keeps a visitor ID and where, that Do Not Track and Global Privacy Control are respected, and that it can wait for consent;
- how a person can ask for their data to be deleted.

Skald does not know some things, so they are left in [square brackets] for you to fill in or delete: your contact for deletion requests, how long your web server keeps its logs, and the script tag lines that depend on how you added the tag. Save a change on the page and the wording is made again.

> A starting point, not legal advice. Your notice must match your own situation.

## The script tag

The optional `skald.js` tag counts what happens inside a page. It is served from your own site and posts to your own site. No third-party code. See [Tracking script](tracking-script.md).

- **No cookie by default.** A cookie is set only if your site turns on visitor IDs and also asks to share them across subdomains (on the tag, or an admin switches it on in Skald: Settings > Sites > Script tag). When it is switched on in Skald, the privacy notice wording says so plainly.
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

- Deletes every visit kept with that address. On a site that keeps shortened addresses, it also deletes the visits kept under the shortened form, since they cannot be told apart. Those may include other people's visits.
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
