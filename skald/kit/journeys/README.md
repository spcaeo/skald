# Skald recorded journeys: Next.js example

Your site sends Skald the visits of people who said yes to analytics. The page never
holds the secret: it posts each event to a small route on your own server, which adds
the visitor's address, signs the event and forwards it to Skald.

## Where each file goes

| File here | In your Next.js (App Router) site |
| --- | --- |
| `route.ts` | `app/api/skald-journey/route.ts` |
| `withdraw/route.ts` | `app/api/skald-journey/withdraw/route.ts` |
| `sign.ts` | `app/api/skald-journey/sign.ts` |
| `SkaldJourneys.tsx` | `components/SkaldJourneys.tsx` (anywhere you like) |

The routes import `./sign.ts` with its extension, so the same files run in plain
Node. TypeScript needs one line in `tsconfig.json` for that:
`"allowImportingTsExtensions": true` (Next.js already sets `"noEmit": true`).
If you would rather not, change the two imports to `./sign` and `../sign`.

## Settings (environment variables on your server)

| Name | What |
| --- | --- |
| `SKALD_JOURNEY_URL` | Skald's address for this site: `https://<your Skald>/traffic-hooks/<site>/journey` |
| `SKALD_JOURNEY_SECRET` | The site's journey secret, made in Skald (Settings › Leads & tools › Recorded journeys). Keep it in your host's secret settings, never in the code. |
| `SKALD_SITE_ORIGIN` | Optional. Your site's own origin, e.g. `https://www.example.com`. Set it when your server sits behind a proxy and sees another address. Only pages from this origin may post. |
| `SKALD_JOURNEY_SEND_IP` | Optional. `0` sends no visitor address at all. |

Without the URL or the secret the routes answer 503 and send nothing.

## The page

In `app/layout.tsx`:

```tsx
import SkaldJourneys from "@/components/SkaldJourneys";

<SkaldJourneys skald="https://skald.example.com" notice="v1" />
```

In your consent banner:

```tsx
import { setJourneyConsent, trackJourney } from "@/components/SkaldJourneys";

onAccept={() => setJourneyConsent(true)}
onDecline={() => setJourneyConsent(false)}
```

Nothing is stored in the browser and nothing is sent before `setJourneyConsent(true)`.
Then the helper sends `session_started` and a `page_view` for each page, links inside
the page included. A browser with Do Not Track or Global Privacy Control sends nothing.
When your notice's version changes (`notice="v2"`), the old yes no longer counts: ask again.

Other events, after the visitor did them (a label is a short name, never a person's
details; an email goes only with `form_sent`, `signup` and `booking_made`):

```tsx
trackJourney("cta_click", { label: "Pricing hero" });
trackJourney("form_sent", { label: "Contact", email });
```

On your privacy page, `<WithdrawJourneysLink />` deletes everything Skald kept about
this visitor and stops recording.

Without React, the script tag alone does the same:

```html
<script src="https://skald.example.com/traffic-js/journeys.js" data-relay="/api/skald-journey" data-notice="v1" defer></script>
<script>
  // from the banner
  window.skaldJourneys.consent(true);
</script>
```

`data-withdraw` changes the withdraw route (default: the relay plus `/withdraw`).
`data-consent="granted"` starts recording at once, for a banner that already said yes.
`window.skaldJourneys.state()` tells whether it records and under which IDs.

## Check it

1. Deploy, open your site, accept analytics and open two pages.
2. In the browser's network panel, `/api/skald-journey` answers 201 (200 for the same
   event again).
3. In Skald, Settings › Leads & tools › Recorded journeys shows the events, and the
   session appears under "Recorded by your site".

Answers you may see: 400 the event broke a rule (the answer names the field), 401 the
secret or the server's clock is wrong, 403 the page is not on `SKALD_SITE_ORIGIN`,
404 the site has no journey secret in Skald, 429 too many (the helper tries once more),
503 the settings are missing here.
