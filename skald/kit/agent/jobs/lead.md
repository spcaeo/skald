## Step __N__. Leads, and the booking, form or payment tools

**Check first.**

- Does the site's code tell Skald about its leads already? A call to the lead file in the form
  handler, or the WordPress plugin "Skald Leads":

      grep -rIl --exclude-dir=node_modules --exclude-dir=.git -e 'skald-lead' -e 'skald_lead' -e 'traffic-hooks/' .

- Which booking, form or payment tools does the site use? Search the code for
  `calendly.com`, `cal.com`, `stripe` (Checkout, Payment Links), `typeform.com`, HubSpot
  (`hsforms`, `hs-scripts`, `meetings.hubspot.com`), and form posts to Zapier, Make or n8n.
- What Skald had when this line was made:

__HOOK_STATES__

  A tool whose secret Skald has may already send its webhook: check in the tool (or ask the
  user) before you make anything, and never replace a working secret.

If the site makes no lead and uses none of these tools, report this job as `skipped` and go on.
Do only the parts that are missing.

### The site's own forms (the lead file)

__LEADS__

1. Find where the backend handles the form (an API route, a server action, a form handler).
2. Download the file for the backend's language from `__LEADS_URL__` and read
   `__LEADS_URL__README.md` first. The files: `skald-lead.php`, `skald-lead.cjs` (Node),
   `skald_lead.py`, `skald-leads.zip` (the WordPress plugin, no code). For example:
   `curl -fsSL -o skald-lead.php '__LEADS_URL__skald-lead.php'`. They hold no secret: they
   read `SKALD_LEAD_SECRET` from the environment (WordPress: `wp-config.php`).
3. Call it once, after the lead is saved, as the README says.
4. Put `SKALD_LEAD_SECRET` in the backend's environment (the host's secret settings), from the
   keys file, never in code and never shown. WordPress keeps it in `wp-config.php`: first check
   that git does not track that file (`git ls-files --error-unmatch wp-config.php` must say
   it does not match). If git tracks it, ask the user where the secret should go instead.
5. Send one test lead with `test: true` (the README says how). Skald lists it under Left out
   and does not count it.

### Booking, form and payment tools (webhooks)

Each tool sends a signed message to its own address in Skald when something happens (a
booking, a form, a payment). A tool needs its webhook and a secret that Skald and the tool
share. Set up each tool the site uses that is not set up yet:

- **With the tool's API, CLI or MCP server** (when you have one, or the user gives you an API
  key in a 0600 file or an environment variable, never in the chat): make the webhook
  yourself, with the address, events and secret below. Ask the user first, as for any change.
- **Else** give the user the clicks below, with the address filled in, and ask them to make
  or paste the secret in Skald themselves (__DASHBOARD__, Settings > Leads & integrations, the tool's
  box): then the secret never passes through you. Report the tool as `left`.

**A secret Skald makes** (Calendly, Cal.com, Typeform; Zapier, Make and n8n): take it with
curl into its own 0600 file, never shown, then put it into the tool from that file. Put the
tool's id in place of `<tool>` (three times):

    umask 077 && grep '^SKALD_REPORT_KEY=' __ENV_FILE__ | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /' | curl -sS -X POST -H @- -H 'Content-Type: application/json' --data '{"tool": "<tool>", "make": true}' -o __ENV_DIR__/__SITE__.<tool>.env.part -w 'HTTP %{http_code}\n' '__HOOKSECRET_URL__' && grep -q '^SKALD_HOOK_SECRET_' __ENV_DIR__/__SITE__.<tool>.env.part && mv __ENV_DIR__/__SITE__.<tool>.env.part __ENV_DIR__/__SITE__.<tool>.env

HTTP 200: the file holds one line, `SKALD_HOOK_SECRET_<TOOL>=...` (the tool's id in capitals).
Skald shows it this once. Anything else: `cat` the `.part` file (Skald's words, no secret),
then remove it.

**A secret the tool makes** (Stripe's `whsec_...`, HubSpot's client secret; Calendly, Cal.com
and Typeform may give their own too): send it to Skald straight from the command that
prints it, through a pipe, never shown. In bash or zsh, with the tool's id in place of
`<tool>`:

    <a command that prints only the secret, on one line> | sed 's/.*/{"tool": "<tool>", "secret": "&"}/' | curl -sS -X POST -H @<(grep '^SKALD_REPORT_KEY=' __ENV_FILE__ | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /') -H 'Content-Type: application/json' --data-binary @- '__HOOKSECRET_URL__'

Skald answers `{"ok": true, ...}` and never shows the secret again.

Skald answers 409 when it has a secret for that tool already. Leave it if the tool's webhook
works. To replace it, ask the user first (the old secret stops working at once), then add
`"replace": true` to the JSON.

#### Calendly (`calendly`)

Address: `__HOOKS__calendly`. Events: `invitee.created`, `invitee.canceled`,
`invitee_no_show.created`. Needs a paid Calendly plan (Standard or higher).

- API (a personal access token as `CALENDLY_TOKEN`): make the secret (`calendly`), find the
  organisation with `curl -sS https://api.calendly.com/users/me -H "Authorization: Bearer
  $CALENDLY_TOKEN"` (`current_organization`), then:

      ( set -a; . __ENV_DIR__/__SITE__.calendly.env; set +a; curl -sS -o /dev/null -w 'HTTP %{http_code}\n' -X POST https://api.calendly.com/webhook_subscriptions -H "Authorization: Bearer $CALENDLY_TOKEN" -H 'Content-Type: application/json' --data "{\"url\": \"__HOOKS__calendly\", \"events\": [\"invitee.created\", \"invitee.canceled\", \"invitee_no_show.created\"], \"organization\": \"<the organisation URI>\", \"scope\": \"organization\", \"signing_key\": \"$SKALD_HOOK_SECRET_CALENDLY\"}" )

- By hand: Calendly has no screen for webhooks. Ask the user (or their developer) to make the
  subscription as the help page says: __HELP_HOOKS__

#### Cal.com (`calcom`)

Address: `__HOOKS__calcom`. Triggers: Booking Created, Booking Cancelled, Booking Rescheduled.

- With Cal.com's API or MCP server: make that webhook, its secret from `make` above (`calcom`).
- By hand: Cal.com, Settings > Developer > Webhooks > New. Subscriber URL: the address.
  Triggers: the three above. Secret: from Skald's Cal.com box (Make secret).

#### Typeform (`typeform`)

Address: `__HOOKS__typeform`. Every response of the form is sent.

- API (a personal token as `TYPEFORM_TOKEN`, and the form's id): make the secret
  (`typeform`), then:

      ( set -a; . __ENV_DIR__/__SITE__.typeform.env; set +a; curl -sS -o /dev/null -w 'HTTP %{http_code}\n' -X PUT 'https://api.typeform.com/forms/<form id>/webhooks/skald' -H "Authorization: Bearer $TYPEFORM_TOKEN" -H 'Content-Type: application/json' --data "{\"url\": \"__HOOKS__typeform\", \"enabled\": true, \"secret\": \"$SKALD_HOOK_SECRET_TYPEFORM\"}" )

- By hand: the form in Typeform, Connect > Webhooks > Add a webhook: the address. Then Edit:
  Secret, from Skald's Typeform box (Make secret). Save, and turn the webhook on.

#### Stripe (`stripe`)

Address: `__HOOKS__stripe`. Events: `checkout.session.completed`,
`checkout.session.async_payment_succeeded`, `invoice.paid`, `invoice_payment.paid`,
`charge.refunded`. Stripe makes the secret (`whsec_...`).

- API (a secret or restricted key that may write webhook endpoints, as `STRIPE_SECRET_KEY`):
  the endpoint's answer holds its secret once, so pipe it straight into Skald:

      curl -sS https://api.stripe.com/v1/webhook_endpoints -u "$STRIPE_SECRET_KEY:" -d url='__HOOKS__stripe' -d 'enabled_events[]=checkout.session.completed' -d 'enabled_events[]=checkout.session.async_payment_succeeded' -d 'enabled_events[]=invoice.paid' -d 'enabled_events[]=invoice_payment.paid' -d 'enabled_events[]=charge.refunded' | sed -n 's/^ *"secret": *"\(whsec_[^"]*\)".*/\1/p' | sed 's/.*/{"tool": "stripe", "secret": "&"}/' | curl -sS -X POST -H @<(grep '^SKALD_REPORT_KEY=' __ENV_FILE__ | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /') -H 'Content-Type: application/json' --data-binary @- '__HOOKSECRET_URL__'

  Stripe's MCP server or CLI, when you have one, makes the same endpoint: its answer holds the
  secret; send it the same way.
- By hand: Stripe, Developers > Webhooks > Add endpoint: the address and the events above.
  Then reveal its Signing secret and paste it in Skald's Stripe box.

#### HubSpot (`hubspot`)

Address: `__HOOKS__hubspot`. HubSpot signs with the HubSpot app's client secret.

- By hand (the user, in their HubSpot app): Auth > copy the Client secret and paste it in
  Skald's HubSpot box; Webhooks > Target URL: the address; subscribe to `contact.creation`,
  `object.creation` for meetings and `deal.propertyChange` for `dealstage`.

#### Zapier, Make or n8n (`json`)

Address: `__HOOKS__json`. For a form or tool that has no hook of its own in Skald: a POST of
JSON to the address with the header `Authorization: Bearer <the secret>`.

- By hand (the user, in the tool): Webhooks by Zapier (POST, Payload Type `json`), Make's
  HTTP module or n8n's HTTP Request node, with the address and that header; the secret from
  Skald's "Zapier, Make, n8n (json)" box (Make secret), kept in the tool's own secure storage.
