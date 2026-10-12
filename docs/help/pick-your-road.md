# Pick your road

Which way your site's leads, bookings and payments should reach Skald, by the kind of site you run: what each road gives you, what it cannot see, and what to set.

## The roads

Skald always reads your web server's log: visits, pages, sources, AI assistants and bots. Conversions come in by four other roads. Pick the ones that fit your site.

| Road | What it is | Set up in |
| --- | --- | --- |
| The script tag | One line in every page's head. It reports form steps, phone and email clicks, booking widgets and button clicks | [Tracking script](tracking-script.md) |
| The lead hook | Your site's own server tells Skald "a lead was made", in a signed message | [Send leads from your backend](leads-from-your-backend.md) |
| Tool hooks | Calendly, Cal.com, Stripe, HubSpot, Typeform, Zapier or Make send their own signed messages | [Webhooks](webhooks.md) |
| The lead database | Skald reads your site's own lead store, with no change to the website | the server's config (`leads.db`) |

The lead database road reads **SQLite only**: a Payload-style `submissions` table. It cannot read MySQL, Postgres or a WordPress database. For those, use the lead hook.

## By kind of site

| Your site | Road | What you get | What you do not get | What to set |
| --- | --- | --- | --- | --- |
| WordPress or another CMS with a form plugin | Script tag, plus the `json` hook through Zapier or Make (or the plugin's own webhook, if it can sign) | Forms started and sent, phone and email clicks, each lead with its source | The lead's later status (won, lost), unless your CRM sends it | The tag on every page; `data-skald="contact"` on the contact form; a Zap or scenario that posts to the `json` hook |
| Next.js on Vercel | Script tag, plus the signed `lead` hook from an API route or server action | Every lead your server makes, with its first and last touch | The visit figures, until Vercel's logs reach Skald through a log drain | The tag; the hook secret in Vercel's environment variables; a log drain (`docs/CDN-LOGS.md`) |
| A site with a Postgres or MySQL backend | The signed `lead` hook from the backend | Every lead, on the server's word, even when a browser blocks scripts | Form steps, unless you add the script tag too | The hook secret in the backend's environment |
| A site that keeps leads in SQLite (Payload CMS) | The lead database | Every lead, its status (won, lost, spam) and its touches, with no code | Leads from other places | `leads.db` in the server's config |
| No-code site (Webflow, Squarespace, Wix) | Script tag, plus Zapier or Make to the `json` hook | Form steps and clicks from the tag; the form's leads from Zapier or Make | Anything the builder will not let you add to the page head | The tag in the site's custom code; a Zap that posts to the `json` hook |
| Calendly or Cal.com | The tool's hook, plus the embed through the script tag | Bookings, cancellations, reschedules and no-shows; opened and time chosen when embedded | Opened and time chosen when you only link to the booking page | See [Demo bookings](demo-bookings.md) |
| Stripe | The `stripe` hook | Each paid checkout, and one paid later by a slow method | Refunds, subscriptions, customer details (never read) | The endpoint's signing secret (`whsec_...`), pasted on the Integrations page; the visitor ID as the session's `client_reference_id` |
| HubSpot | The `hubspot` hook, or Zapier to the `json` hook | New contacts, booked meetings, deals won | Anything HubSpot does not send | The app's client secret, pasted on the Integrations page |
| Zapier, Make, n8n | The `json` hook | Any lead any tool knows about, up to 100 in one message | Nothing by itself: it sends what the Zap sends | **Make secret** for `json`, and the signing step in the Zap |

Never sign a hook in the browser. The secret must stay on a server. A browser can only use the script tag.

## What each road costs in privacy

- **Visitor IDs are off by default.** Then the script tag makes no ID, and a hook's `vid` is dropped before anything is kept. Journeys, abandoned forms and assisted sources need the IDs on. Your privacy notice must say so.
- **Names and emails are never kept** unless the site's identity is set to full. Then the name and the primary email only. Nothing else, ever: no phone, no address, no message.
- **Addresses and browsers.** A lead hook may send the visitor's address and browser once. Skald looks up the country and the device, then drops both.
- **The lead database** is opened read-only. Only the columns Skald needs are read.

## One lead, one road

Send each lead through one road only. Each tool keeps its own row, so the same lead sent through two (for example the lead hook and Zapier, or the lead hook and the lead database) counts twice.

**Settings > Integrations > Status** flags it: "One lead, two tools", with the leads it saw. Turn one of the two roads off for those leads.

## Check it

- On the server: `sudo skald doctor` (Docker: `docker exec skald skald doctor`). It lists every part with OK or NEEDS ATTENTION, and the fix.
- In the dashboard: **Settings > Integrations > Status** shows the same lines for the roads in, and each hook says "ready", "never received" or "last received 2 h ago".
