## Step __N__. Connect recorded journeys

Recorded journeys are the sessions a visitor agreed to, sent by the site itself (pages read,
clicks, forms, bookings). Skald shows them beside the visits it reads from the log, labelled
"Recorded by your site", and never adds them to the log's counts. Nothing is sent before the
visitor accepts analytics in the site's consent banner.

Two parts go into the site's code:

- **The page helper**, one script tag: `__JOURNEY_JS__`. It keeps nothing and sends nothing
  until the banner calls `window.skaldJourneys.consent(true)`.
- **The relay**, two small server routes on the site's own address. The page posts each event
  to the relay; the relay signs it with the journey secret and sends it to Skald
  (`__JOURNEY_URL__`). The secret stays on the site's server, never in the browser.

**Ask the user before each change** in this job: show the file and what you add, and wait for a
yes. Change nothing else.

**Check first.** Search the site's code:

    grep -rIl --exclude-dir=node_modules --exclude-dir=.git -e 'traffic-js/journeys.js' -e 'SKALD_JOURNEY_SECRET' .

If the helper is in the shared layout, both relay routes are there, the host has
`SKALD_JOURNEY_URL` and `SKALD_JOURNEY_SECRET`, and the consent banner calls
`skaldJourneys.consent`, this job is done already: report it as `already`.

Find the consent banner first. If the site has none (no cookie or analytics notice the visitor
answers), stop this job: tell the user that recorded journeys need one, and report it as
`left`, with "add a consent banner" in `left_for_user`. Never call `consent(true)` without the
visitor's own choice.

### 1. The journey secret

Skald makes it once and gives it, with the address, as two env lines into a 0600 file, never
shown:

    umask 077 && grep '^SKALD_REPORT_KEY=' __ENV_FILE__ | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /' | curl -sS -X POST -H @- -H 'Content-Type: application/json' --data '{"tool": "journey", "make": true}' -o __ENV_DIR__/__SITE__.journey.env.part -w 'HTTP %{http_code}\n' '__HOOKSECRET_URL__' && grep -q '^SKALD_JOURNEY_SECRET=' __ENV_DIR__/__SITE__.journey.env.part && mv __ENV_DIR__/__SITE__.journey.env.part __ENV_DIR__/__SITE__.journey.env

- **HTTP 200:** `__ENV_DIR__/__SITE__.journey.env` holds `SKALD_JOURNEY_SECRET` and
  `SKALD_JOURNEY_URL`. Never `cat` it.
- **HTTP 409:** Skald has a journey secret already. If the site's host has
  `SKALD_JOURNEY_SECRET`, keep it. Otherwise ask the user: "Skald has a journey secret for
  __SITE__ already. May I make a new one? The old one stops working at once." With a yes, send
  the same command with `"replace": true` added to the JSON.
- **Anything else:** `cat` the `.part` file (Skald's words, no secret), tell the user, remove it.

Put both values in the host's secret settings (Vercel, Netlify, the server's env file...) the
way rule 2 says, without showing them. For a local `.env.local` that git ignores:

    grep -E '^SKALD_JOURNEY_(SECRET|URL)=' __ENV_DIR__/__SITE__.journey.env >> .env.local

Check `git check-ignore .env.local` prints the name first.

### 2. The page helper

Put the tag once in the shared layout (Next.js App Router: `app/layout.tsx`; Pages Router:
`pages/_document.tsx`; WordPress: `header.php`; else the shared `<head>`):

    <script src="__JOURNEY_JS__" data-relay="/api/skald-journey" defer></script>

`data-relay` is the relay's path on the site (step 3). Optional: `data-notice="v1"` names the
privacy notice's version, sent with each event; `data-consent="granted"` only when the banner
has already decided before the page loads and the tag is added only after a yes.

### 3. The relay

Next.js (App Router): three files. Skald's own example, unchanged except for the paths. The
two routes import `sign.ts` with a `.ts` ending; if the build refuses it, set
`"allowImportingTsExtensions": true` in `tsconfig.json` (Next.js does not emit), or drop the
ending in both imports.

`app/api/skald-journey/sign.ts`:

__JOURNEY_SIGN__

`app/api/skald-journey/route.ts`:

__JOURNEY_ROUTE__

`app/api/skald-journey/withdraw/route.ts`:

__JOURNEY_WITHDRAW__

Another stack: write the same two routes in the site's own language. Each takes the page's
JSON (at most 16 KiB, the site's own origin only), adds the visitor's address as `ip` (the
first `X-Forwarded-For` hop), and posts the exact body to `SKALD_JOURNEY_URL` (the withdrawal
to `SKALD_JOURNEY_URL/withdraw`) with two headers: `X-Skald-Timestamp` (unix seconds) and
`X-Skald-Signature` (hex HMAC-SHA256 of `<timestamp>.<body>` with `SKALD_JOURNEY_SECRET`).

### 4. The consent banner

Where the banner records the visitor's answer, add (a yes, then a no):

    window.skaldJourneys?.consent(true)
    window.skaldJourneys?.consent(false)

Where the site lets a person take back their consent (the privacy page, "Cookie settings"), add
`window.skaldJourneys?.withdraw()`: Skald deletes what it holds for that browser.

Optional, at the moments that matter (no email or phone in a label):

    window.skaldJourneys?.track("cta_click", { label: "Book a demo" })
    window.skaldJourneys?.track("form_sent", { label: "Contact" })

The names Skald takes: `cta_click`, `form_sent`, `signup`, `booking_opened`, `booking_made`,
`download`.

### 5. Test

Commit with the user's yes and let it deploy. Then, in a browser, open the site, accept
analytics in the banner, and open two pages. Within a minute Skald shows the session in Traffic
› Visitors under "Recorded by your site", and Settings › Leads & tools › Recorded journeys says
when the last event came (__DASHBOARD__). A relay answer of 401 means the secret or the clock
is wrong; 400 names the field Skald refused.

For the report: `jobs` `"connect-journeys"`, and each file you changed in `changed_files`.
