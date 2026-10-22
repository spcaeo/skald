# Skald for a site on Vercel

A step-by-step setup for a site hosted on Vercel, about 15 minutes. Skald itself cannot run on
Vercel (it needs an always-on process and a disk for its history), so it runs on a small
service beside it, and Vercel sends it the site's traffic.

Which Vercel plan you are on decides how much Skald sees (Vercel dashboard > **Settings >
Billing**):

| Your plan | How traffic reaches Skald | What you see |
| --- | --- | --- |
| **Pro or Enterprise** | a Log Drain: Vercel posts every request to Skald | everything: people, AI assistants (ChatGPT, Claude, Perplexity), crawlers, bots, leads and their sources |
| **Hobby** | the `skald.js` tag only (Log Drains need Pro) | people, sources, forms, bookings and conversions; **not** AI assistants or crawlers (they never run scripts). A Pro trial lets you see everything. |

Vercel's middleware runs before the response exists, so it cannot report a page's status or
cache result; that is why Skald uses the Log Drain on Vercel, not middleware.

## 1. Run Skald on Render (or Railway)

Use the **Deploy to Render** button on Skald's GitHub page, or Render > **New > Blueprint** with a fork
of the repository. It makes one web service from the Skald image with a disk (a disk needs a
paid Render instance; without one the history is lost at every restart). Fill in:

| Setting | Value |
| --- | --- |
| `SKALD_SITE` | your site, e.g. `example.com` |
| `SKALD_HOSTS` | every host name it answers on, e.g. `example.com www.example.com` |
| `SKALD_BASE_URL` | Skald's own address, e.g. `https://stats.example.com` |
| `SKALD_TIMEZONE` | where your day starts, e.g. `America/New_York` |
| `SKALD_INGEST` | `true` (already set by the Blueprint) |
| `SKALD_LOG_DIR` | `/var/lib/skald/ingest/example.com` (your `SKALD_SITE`) |

A new install keeps each visit's IP address for 395 days, and leads' names and emails, so a
person can be looked up. If your privacy notice does not allow that, also set
`SKALD_KEEP_IPS=0` and `SKALD_IDENTITY=anonymous` (or change it later in Settings > Data
retention > People).

Then give it a domain: Render > **Settings > Custom Domains**, add `stats.example.com`, and add
the `CNAME` record Render shows at your DNS provider (in Vercel's DNS if Vercel holds your
domain). Render issues the certificate. Sign-in needs HTTPS, so wait for it.

Render does not publish its proxies' addresses. After the first deploy, set
`SKALD_TRUSTED_PROXIES` as [HOSTING.md](HOSTING.md), "Render", says; until then the sign-in
limits see Render's proxy, not each visitor.

Railway works the same way: [HOSTING.md](HOSTING.md), "Railway".

## 2. Make yourself the owner

Render > your service > **Shell**, then:

```sh
skald accounts init --org "Example Co" --owner-email you@example.com
```

It prints a link: open it, choose your password, and sign in at
`https://stats.example.com/traffic/`.

## 3. Make an ingest token

In Skald: **Settings > Add or remove sites > New token** (scope: ingest), or in the Shell:

```sh
skald token create vercel-drain --scope ingest --site example.com
```

Copy the token; it is shown once.

## 4. Connect Vercel (Pro or Enterprise)

Vercel > **Team Settings > Drains > Add Drain > Logs**:

1. **Projects:** your site's project. **Sources:** `static`, `edge`, `lambda` (add `external` and
   `redirect` if you use rewrites to other domains). **Environments:** `production`.
2. **Sampling:** 100%. A sample would undercount every figure.
3. **Destination:** Custom endpoint,
   `https://stats.example.com/traffic-ingest/example.com?format=vercel`
4. **Format:** JSON or NDJSON.
5. **Custom headers:** `Authorization: Bearer <your ingest token>`.
6. **Create.** Vercel tests the address; Skald answers 200.

Also keep **Team Settings > Security & Privacy > IP Address Visibility** on: without the
visitor's address Skald cannot tell people apart, and refuses those requests.

To also require Vercel's signature on every delivery, see [HOSTING.md](HOSTING.md), "The
signature (optional)".

## 5. Add the tag (any plan; the only source on Hobby)

The tag adds what a log cannot see: forms, clicks, scroll depth and booking embeds such as
Calendly. Since 2.24.0 the plain tag needs nothing on Vercel: add
`<script src="https://stats.example.com/traffic-js/skald.js" data-site="example.com" defer></script>`
to every page and it posts to Skald directly. To serve it from your own domain instead (fewer
ad blockers stop it), in your project's `vercel.json`:

```json
{
  "rewrites": [
    { "source": "/traffic-beacon", "destination": "https://stats.example.com/traffic-beacon" },
    { "source": "/traffic-js/:path*", "destination": "https://stats.example.com/traffic-js/:path*" }
  ]
}
```

On Render, set `SKALD_BEACON_ORIGINS` to your site's address, e.g. `https://www.example.com`.
Then, with the rewrites, add to every page (in Next.js, the root layout):

```html
<script src="/traffic-js/skald.js" data-site="example.com" defer></script>
```

What it sends and what it never sends: [BEACON.md](BEACON.md) and the in-app guide
**Help > The tracking script**.

## 6. Check it works

- Open your site in a private window, then Skald's **Live** page: your visit appears within a
  few minutes.
- Skald > **Settings > Add or remove sites** shows, for the site, the lines kept, the lines
  refused and the time of the last delivery.
- The daily figures fill in after the next daily run; the next morning you have your first
  whole day.

## Leads and bookings

- Form tools and Calendly, Cal.com, HubSpot, Typeform or Stripe can post their events to Skald:
  **Settings > Integrations** and the in-app guide **Help > Webhooks**.
- Each lead is traced to what brought it: ChatGPT, Perplexity, Google or a campaign.

## If something is off

| You see | Why, and what to do |
| --- | --- |
| Vercel says the drain test failed | Skald's address is not reachable over HTTPS yet, or the path or site name in the URL is wrong. Open the URL in a browser: a 403 or 405 answer (it takes POST only) means it is reachable; a timeout or certificate error means it is not. |
| No traffic in Live after 10 minutes | Check the drain's Sources and Environments, and that `SKALD_HOSTS` lists the host names your site answers on. |
| "Rejected: no visitor address" | Turn IP Address Visibility on in Vercel. |
| The country cards are empty | Vercel's drain records carry no country, so Skald cannot show one. Not an error. |
| The tag sends nothing | `SKALD_BEACON_ORIGINS` (or the site's host names) does not match your site's address, or, with the first-party tag, the rewrites are missing. The browser's network tab shows the `traffic-beacon` answers; the set-up dialog's Test also looks at your page and says what is wrong. |

More: [HOSTING.md](HOSTING.md) (every platform), [INGEST.md](INGEST.md) (log intake),
[INSTALL.md](INSTALL.md) (all install ways).
