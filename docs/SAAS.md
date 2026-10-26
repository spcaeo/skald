# Skald as a service: sign-up, plans, billing

People sign up on
their own, get an organisation on a trial, and pay through Stripe. Plans set limits on sites,
requests a month, members and how long detail is kept.

**All of it is off by default** (`saas.enabled: false`, or no `saas:` section). Then every new
route answers 404, no limit applies, and nothing in `accounts.sqlite` changes: a self-hosted
install works exactly as before. It also needs accounts (`access.mode: sessions`,
[ACCOUNTS.md](ACCOUNTS.md)); in basic mode `saas` is ignored.

Code: `skald/saas/` (`signups.py`, `signup_api.py`, `plans.py`, `limits.py`,
`usage_alerts.py`, `stripe_client.py`, `stripe_events.py`, `billing_api.py`, `cli.py`), `skald/audit_usage.py`
(the second count of usage), `skald/webapp/auth/signup.html`, `signup-finish.html` and
`skald/webapp/js/tabs/billing.js`.

## Turning it on

1. Accounts first: `access.mode: sessions` and the nginx part of [DEPLOY.md](../DEPLOY.md)
   "Sessions mode", with `access.base_url` set (every link in a mail, and Stripe's way back,
   starts with it) and mail set up (Settings > Mail, or `mail:` in `config.yml`). Without mail,
   no sign-up link can be sent.
2. Add the `saas:` section to `config.yml` (the commented block in `config.example.yml`):

   ```yaml
   saas:
     enabled: true
     signup: true                     # /traffic-auth/signup
     allowed_domains: [example.com]   # optional: only these addresses (and subdomains) may sign up
     billing: stripe                  # Settings > Billing and the webhook; leave out for no payment
     grace_days: 7                    # past due this long: read-only
     usage_alerts: true               # the 80/90/100 % mails and banner (the default)
     default_plan: starter            # what a sign-up gets
     plans: [{name: starter, sites: 1, requests_month: 300000, retention_days_max: 90, members: 3, trial_days: 14, price_id: price_123, label: Starter}, {name: team, sites: 10, requests_month: 3000000, retention_days_max: 400, members: 20, price_id: price_456, label: Team}]
   ```
3. The nginx locations in DEPLOY.md's sessions-mode block: `/traffic-auth/signup` and
   `signup-finish` (limited like sign-in), `billing` in the helper's route list, and
   `location = /traffic-hooks/_billing/stripe`. `nginx -t` before the reload.
4. Restart the helper: `systemctl restart skald-refresh`.

To switch it off, set `enabled: false` and restart. Plans, statuses and Stripe ids stay in the
accounts file, unused, until it is on again.

## Plans

| Field | Meaning |
| --- | --- |
| `name` | The plan's name (shown to customers). |
| `sites` | Sites the organisation may have. |
| `requests_month` | Requests a calendar month, every site of the organisation together. |
| `retention_days_max` | The most days a retention setting may hold (detail days, journeys, returning-visitor matching, in-page events; never below a key's own floor). |
| `members` | Members, open invites included. |
| `price_id` | The Stripe Price a customer subscribes to. Without one the plan cannot be bought from the page (a free plan, or one you set by hand). |
| `trial_days` | The trial a new sign-up gets when this is the default plan. |
| `label` | A short line under the name on the Billing page, such as the price. |
| `ingest_daily_mb` | Log lines the organisation's sites may ship a UTC day, together (docs/INGEST.md); left out, the install's `ingest.org_daily_mb` (200). Not shown on the Billing page. |

A limit left out (or `unlimited`) is no limit. With PyYAML installed, `plans` may also be a
mapping (`plans: {starter: {sites: 1, ...}}`). An organisation with **no plan** has no limits:
the install's own organisations (`skald accounts init`, `org create`) start that way. A plan
name the config no longer lists takes the default plan's limits.

`skald plan list` shows the plans and every organisation's plan and status; `skald plan set ORG
PLAN [--status S] [--trial-days N]` changes one (`none` takes the plan away). `skald usage
[--org SLUG] [--month YYYY-MM]` shows the requests against the limit.

## Sign-up

1. `/traffic-auth/signup`: the person types an email address. The page always says "check your
   mail", whether or not the address has an account. A new address gets a link
   (`/traffic-auth/signup-finish?t=...`) that works once, for 24 hours. An address that has an
   account gets "you already have an account" with the sign-in and forgot-password links
   instead. Only the mailbox learns which.
2. The link's page asks for a name, a password (the usual policy: 12 characters, not the email,
   not a common one), the organisation's name and the first site's host name.
3. Skald makes the user (never an install admin), the organisation (`created_via: signup`) with
   them as its owner, the site, and the default plan: `trialing` for its `trial_days`, `active`
   for a plan with no price, else `none`. When the plan caps retention, the organisation's
   retention settings start at the cap. Then it signs the person in.

Limits: at most 3 links an hour per address (more are silently not sent), at most 10 sign-up
forms an hour per client address (429), and nginx's `limit_req` in front. Only the SHA-256 of a
link is stored, and the client address only as a keyed hash.

**There is no captcha** (Skald uses the standard library only, and a captcha would mean a
third party's script on the page). The mailed link is the check that a real mailbox is behind
the sign-up, and the limits keep a script slow. If bots become a problem, set
`allowed_domains`, tighten the nginx limit, or turn `signup` off and invite people by hand.

A site already on the install cannot be claimed again: the page says to ask its owner for an
invite. Nor can a site from the server's config files, or a name purged in the last 30 days
(`skald site purge` holds it; an install admin re-uses it with `skald site add --allow-reuse`).
Getting the new site's data in (log shipping, the beacon) is a separate step.

**Domain verification.** The new site (and, with saas on, every site added in Settings > Sites)
starts *waiting for verification*: nothing is collected for it. The ingest endpoint answers 403,
the hook receiver 404, the beacon 403. Settings > Sites shows a token; the person adds either a
DNS TXT record `skald-verify=<token>` on the host, or `<meta name="skald-verify"
content="<token>">` on `https://<host>/`, and presses Verify (at most 10 checks an hour per
site). The TXT record is asked of the system resolver (`/etc/resolv.conf`) over UDP; the page is
fetched with the outgoing-webhook client (public addresses only, no redirect, 64 KiB, 10 s).
An install admin can mark a site verified: `skald site verify <host>`. Config-file sites and
sites made before this check count as verified (`skald/site_verify.py`).

## Billing with Stripe

**Set-up in Stripe** (use test mode first: test keys start `sk_test_`, and nothing is charged):

1. Products: one product per plan, each with a recurring Price. Put each Price id
   (`price_...`) in the plan's `price_id`.
2. Customer portal: Settings > Billing > Customer portal in Stripe. Turn on what customers may
   do (update the card, see invoices, cancel, switch plans among your prices).
3. Webhook endpoint: `https://<your server>/traffic-hooks/_billing/stripe`, with these events:
   `checkout.session.completed`, `customer.subscription.updated`,
   `customer.subscription.deleted`, `invoice.payment_failed`.
4. The keys, on the server, as the skald user (each read from stdin, never printed):

   ```sh
   ./bin/skald --config /etc/skald/config.yml billing secret key       # sk_test_... / sk_live_...
   ./bin/skald --config /etc/skald/config.yml billing secret webhook   # whsec_...
   ```

   They go into `secrets.json` beside the history (0600; keys `billing/stripe_key` and
   `billing/stripe_webhook`). The environment variables `SKALD_STRIPE_KEY` and
   `SKALD_STRIPE_WEBHOOK_SECRET` win when set (`/etc/skald/env`). A restricted key
   with write access to Checkout Sessions and Customer portal is enough.

**How it works.** The owner opens Settings > Billing and chooses a plan. The helper asks
Stripe for a Checkout Session (subscription mode, the plan's price, the organisation's id as
`client_reference_id` and in the metadata, the owner's email, success and cancel addresses on
`access.base_url`) and sends the browser there. Stripe sends events to the webhook:

| Event | Effect |
| --- | --- |
| `checkout.session.completed` | the plan from its metadata, `active`; the Stripe customer and subscription are kept |
| `customer.subscription.updated` | the status (trialing, active; past_due, unpaid, incomplete, paused are `past_due`; canceled, incomplete_expired are `canceled`) and the plan from the price |
| `customer.subscription.deleted` | `canceled` |
| `invoice.payment_failed` | `past_due` (the grace period starts) |

Each event's `Stripe-Signature` is checked over the raw body before it is read (the same
verifier as the conversion hooks, 5 minutes' tolerance). Each event id is applied once (a retry
answers `duplicate`), an event older than one already applied to the organisation is not
applied, and every change is in the audit log with the actor `stripe`. "Manage billing" opens
Stripe's customer portal for the organisation's customer.

## What customers see

- **Settings > Billing** (only when saas is on; owners, and admins to read it): the plan and
  its status, trial days left, this month's requests as a bar with the 80, 90 and 100 % marks,
  sites and members against the limits, the plans to choose from, and "Manage billing". Only
  owners see the Choose and Manage buttons; the routes refuse an admin's POST (403).
- **A banner** on every page for every member when the organisation is over a limit, or
  read-only; and, for owners and admins only, when this month's requests reach 80 % of the
  plan (below).
- `/me` has `saas: true` and `plan: {name, status, usage, limits, used, over, read_only,
  read_only_why, trial_days_left, trial_ends_at}` (`plan` is null for an organisation with no
  plan). `usage` adds `percent` (of `requests_month`, rounded down), `resets_on` (the first
  of next month) and `mark` (80, 90 or 100, the highest reached; null below 80 or with
  `usage_alerts: false`).

## Usage alerts (80, 90 and 100 %)

The owner's words (2026-10-26): "we also send alerts to upgrade your plan when you reach 80%,
90%, 100% so that your data is not lost". Past `requests_month` the ingest turns new batches
away (429): Skald's shipper keeps the lines and sends them again, a Cloudflare Worker's are
lost. So the owners and admins hear before that happens (`skald/saas/usage_alerts.py`).

- **The figure** is the one `over_limit` reads: the organisation's requests this calendar month
  from the stored days, counted twice. Unknown or withheld: no alert. Today's requests join
  after the day is stored, as they do for the limit itself.
- **The marks**: 80, 90 and 100 % of the plan's `requests_month`. One mail per mark, per
  organisation, per month. A jump past several marks sends one mail, for the highest; the ones
  below are kept as skipped. A new month starts again.
- **Never twice.** Each mark is written to `usage_alerts` in accounts.sqlite before anything is
  sent (the sale alerts' rule, decision D93): a restart, a recount (the figure going down and up
  again) or a second run never repeats one. A failed send is noted, not retried.
- **A plan change** in the month: a bigger limit starts from its own marks that the usage had
  not passed yet; the ones it had passed are kept as skipped. A smaller limit is new: its
  highest passed mark mails. Going back to a limit used before this month repeats nothing.
- **Who**: the organisation's owners and admins with a confirmed, working account, one mail
  each. Viewers never.
- **The mail** (the account mails' look): "<org> has used X of the Y requests its <plan> plan
  allows this month (Z%). The count starts again on <1st of next month>." Then what happens
  past the limit (new lines turned away until the month turns or the plan is bigger; Skald's
  shipper keeps them, a Cloudflare Worker's are lost) and one button, **Open Billing**, to
  `#settings/billing` on the organisation's own dashboard: its first site's `dashboard.url`
  (each site its own, the 2.36.1 rule), else `access.base_url` + `/traffic/<site>/`.
- **When**: after every live run and run-daily, once for the whole install
  (`summary_mail.after_run`). At most one check per organisation every 5 minutes (live runs
  every 2); run-daily always checks, since it stores the day the figure is made of. Nothing
  runs inside an ingest request.
- **The audit log**: one `billing.usage_alert` row per alert, actor `skald`, with the mark and
  the counts ("850 of 1,000 requests in 2026-10 (85%), small plan; mailed 2 of 2 owners and
  admins"). Never an address.
- **The switch**: `saas.usage_alerts: false` stops the mails and the banner; the Billing bar
  stays. On by default with saas. With saas off nothing runs and no table is made.

## Over a limit, and read-only

**Nothing is ever deleted because of going over a limit or being read-only.** The one thing a
plan cuts is retention (below).

- Members: an invite past the limit is refused (402); open invites count.
- Retention: a value above `retention_days_max` is refused when saved (400). A value saved
  before, or under a bigger plan, is read as the cap ("capped by your plan"), and the daily
  run prunes by the cap (docs/SETTINGS.md, "A plan's retention cap").
- Sites: `saas.limits.can_add_site(db, org_id, config)` says whether one more fits; the code
  that adds sites calls it.
- Requests a month: going over shows the banner. Whether new data is refused is the ingest's
  choice: `saas.limits.over_limit(db, org_id, config, history_path)` lists what is over.
- Read-only: the log ingest refuses every batch with 402 (the shipper keeps the lines).
- Usage is the sum of the history's daily request totals (`days.hits`) for the organisation's
  sites in the calendar month, counted a second way from the day's groups
  (`audit_usage.py`). When the two disagree the usage is withheld, never guessed; a month with
  no recorded day is "not known", not 0. Requests are every logged request, people and
  machines alike.

**Read-only** (the dashboard stays readable; team, tokens and settings changes answer 402;
each person's own account and Settings > Billing still work, so it can be paid):

- the last payment failed more than `grace_days` (default 7) ago and is still unpaid;
- the subscription was cancelled;
- with billing on, the trial ended more than `grace_days` ago and no plan was bought.

Paying (or `skald plan set ORG PLAN --status active`) ends it at once.

## Routes

| Route | Who |
| --- | --- |
| `GET /traffic-auth/signup`, `signup-finish` | anyone (pages) |
| `GET /traffic-auth/signup-info?t=` | anyone with a link |
| `POST /traffic-auth/signup`, `signup-finish` | anyone, same-origin |
| `GET <page>/billing` | owners, and admins to read (`can_change: false`) |
| `POST <page>/billing/checkout`, `billing/portal` | owners, same-origin, CSRF |
| `POST /traffic-hooks/_billing/stripe` | Stripe (signed) |

All answer 404 while saas (or, for the sign-up pages, `saas.signup`) is off.
