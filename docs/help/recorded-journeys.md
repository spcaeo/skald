# Recorded journeys: what your site sends Skald

Your website can tell Skald what each consenting visitor did: the pages they read, the buttons they pressed, the form they sent, the booking they made. Skald shows these sessions in their own card, **Recorded by your site**, and never adds them to the figures it reads from your server log. This guide covers what you see, how to connect your site, and what is kept.

## What it is

Skald's figures come from your server's log: every visit, from every visitor, whether they ran a script or not. A log line says which page was asked for, but not which button was pressed or whether a booking went through.

Recorded journeys fill that gap. Your site's own server sends Skald one small event each time something happens: a session began, a page was read, a call to action was pressed, a form was sent, an account was made, a booking calendar was opened, a booking was made, a file was downloaded.

- **Only with consent.** An event is kept only when the visitor said yes to analytics. Without it, Skald refuses the event and keeps nothing.
- **Never mixed in.** These sessions have their own figures: sessions, visitors, pages read and actions. They are never added to the log's visits or visitors, and a session is not a visit.
- **Never a form's answers.** Only fixed facts come: the page, the event, a short label such as a button's words. An email may come with a form sent, a signup or a booking made, and is kept only when your site keeps leads' names and emails.
- **Counted twice.** Every figure is recounted from the stored events by a separate road. When the two counts differ, the figures are withheld and the card says so. The sessions are still listed.

## Where to find it

| What | Where |
| --- | --- |
| The sessions and their figures | [Traffic > Visitors](#traffic/visitors), the card **Recorded by your site** under the visit list |
| One session, every step | Press a session's row: its drawer opens |
| The sessions linked to a log visit | A visitor's drawer on [Traffic > Visitors](#traffic/visitors) (owners and admins) |
| Connect your site, its status, the last event received | [Leads & tools](#settings/site/leads), the row **Recorded journeys** |

The card shows once your site is connected or has sent something. The period is the one in the top bar. An open session is in the page's address (`rj=` and a code), so a link or a reload opens the same session.

## What the card shows

- **Sessions**: sessions that started in the period.
- **Visitors**: the different visitors behind them, by the ID your site keeps for each browser.
- **Pages read**: the pages read in those sessions.
- **Actions**: everything else they did: calls to action, forms, signups, bookings, downloads.

Each row is one session: when it started, how long it lasted, where it landed, how many pages, and how it ended (the best thing it did: a booking made first, then a signup, a form, a download, a booking calendar opened, a call to action). A returning visitor is marked.

The session's drawer shows every page in order with the time since the start, each action with its label, where the visitor came from (the referrer and the campaign tags), and the log visits linked to it.

Owners and admins also see the address and the email kept with a session, when your site keeps them. Other members see the same sessions without them.

## How a session is linked to a log visit

Never by guess. A recorded session is linked to a visit from your log in one of two ways, and the drawer says which:

- **By visitor ID.** The page had Skald's script tag with visitor IDs on, your site sent that ID with its events, and the ID was matched to the visit.
- **By address.** The session's address is the same as the visit's, and the session happened inside the visit's time. This needs your site to keep addresses (**Settings > This site > Privacy**).

When neither holds, the session stands alone. That is not an error.

## Connect your site

You need to be an owner or admin of the site.

1. Open [Leads & tools](#settings/site/leads) and press **Connect** on the **Recorded journeys** row.
2. Skald asks **Who will do it?**
   - **Me**: Skald makes the site's secret and shows it once. Copy it straight into your website server's settings. Then follow the steps on the screen.
   - **My developer**: Skald writes a message with the steps to send to your developer.
   - **My AI agent**: Skald gives one line for your AI coding agent. The agent gets the address and the secret from Skald, never through the chat, adds the page helper and the relay to your website's code, and asks you before each change.
3. When the first event comes, the row says when it was received.

What gets added to your website:

- **The page helper**, one line in your pages:

  ```
  <script src="https://stats.example.com/traffic-js/journeys.js" data-relay="/api/skald-journey" defer></script>
  ```

  Use your own Skald address. If your site has its own consent banner, tell the helper when the visitor says yes or no: `window.skaldJourneys.consent(true)` or `false`. To mark an action: `window.skaldJourneys.track("cta_click", {label: "Book a demo"})`.

- **The relay**, a small route on your website's own server. The page sends each event to it; it signs the event with the secret and passes it to Skald. The secret stays on your server, never in a web page. Skald has a ready example for Next.js; your developer or agent can write the same in any language.

Keep the secret in your server's settings (environment variables), never in the code or a public repository. **Connect** again makes a new secret: the old one stops working at once.

## When a visitor changes their mind

If a visitor withdraws consent, your site tells Skald (the helper's `window.skaldJourneys.withdraw()`, through the relay). Skald deletes every event of that visitor at once, and for 90 days refuses any late event from them. It keeps no copy of the visitor's ID to do so, only a code that cannot be turned back into it.

## What is kept, and for how long

- **The address**: as your site's privacy setting says: in full, shortened, or not at all.
- **The email**: only when your site keeps leads' names and emails.
- **How long**: each event for the same days as page views per visitor ID (30 by default). When your People days are shorter, the address and the email are cleared after those days and the event stays.
- **Keep everything**: on an internal or enterprise site, nothing is deleted. A visitor's own withdrawal still deletes, because it is their request.

See [Privacy](privacy.md) and [Settings and retention](settings-and-retention.md).

## When something is wrong

- **The row says nothing has come.** Check that the page helper is on your pages, that the visitor said yes to analytics, and that the relay has the address and the secret.
- **Skald answers the relay 401, "bad signature".** The relay's secret is not the current one, or its server's clock is off by more than five minutes. Make a new secret and update the relay.
- **Figures withheld.** The recount did not match. The sessions are still listed; the figures come back when the counts agree. Owners and admins see what differed.
- **An event is refused.** The answer names the field. The most common: a page address with a query string (`?`), or a label that holds an email or a phone number. Send the page's path only, and fixed words as labels.

The technical contract, every answer and its limits are in Skald's docs (`docs/JOURNEYS.md`).
