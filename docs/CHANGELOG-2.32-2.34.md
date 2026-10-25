# Changelog: 2.32.0 to 2.34.1

The releases of 24 and 25 October 2026. Newer ones: [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.27-2.31.md](CHANGELOG-2.27-2.31.md).

## 2.34.1 (2026-10-25)

Fixes, no new figure. The help and the privacy notice Skald writes now say what the
script tag keeps in the browser and where it loads from; four known issues in "one line for
your AI agent" are fixed; the recount that fills Social networks for earlier days is written
down and tested; CLASSIFICATION.md and this changelog are split before they cross 1000 lines.

### Docs: the changelog's 2.27.0 to 2.31.1 moved to docs/CHANGELOG-2.27-2.31.md

- **Changed (docs only).** CHANGELOG.md was at 960 lines with this release's entries, near the
  1000-line limit. Its sections 2.27.0 to 2.31.1 are now `docs/CHANGELOG-2.27-2.31.md`, word
  for word; CHANGELOG.md keeps Unreleased and 2.32.0 on, and its "Older versions" list and the
  2.23-2.26 file's header link to the new file. The website's What's new page linked its
  "Full notes" for 2.27.0 to 2.31.0 to anchors that moved now, and for 2.23.0 to 2.26.0 to
  anchors that had moved already in an earlier split (those links opened the changelog's top);
  all nine now point to the right file on GitHub. **Why:** the file would have crossed the
  limit with the next release. **Who:** readers of the changelog and the website's What's new.
  **Do:** nothing; the website's links go live with its next upload. **Checked:** the moved
  sections equal the old lines exactly (diff); the README's changelog links name only 2.33.0
  and 2.34.0, which stay; the in-app What's new (`keys.js`) links none; full suite OK.

### SECURITY.md: the supported version no longer goes stale

- **Fixed (docs only).** The public SECURITY.md said "2.5.x (the newest)" is supported and
  "2.0 to 2.4" is not, while the newest release is 2.34. It now says the newest 2.x minor
  release (the top version in CHANGELOG.md) gets security fixes and older 2.x minors should
  upgrade, with no number to change on each release. **Why:** a reader on 2.34 could think
  their version unsupported, or 2.5 still supported (public repo, SECURITY.md). **Who:**
  anyone reading the security policy on GitHub. **Do:** nothing; it goes out with the next
  `tools/publish-update.sh`. **Checked:** read through; `tools/make-public.py` copies
  `public/` over the root as it is, so the CHANGELOG.md link resolves in the public repo;
  full suite OK.

### One line for your AI agent: four known issues fixed

- **Fixed.** Four items HANDOVER/00 listed as known in 2.31.0's one line for an AI agent
  (`/traffic-kit/`). (1) A refused report (no `X-Skald-Report-Key`, or a wrong one) still
  rewrote `kit-links.json`; now a request that changes nothing (a refused or late report, a
  second read of the steps, a second try for the keys) leaves the file as it is. (2) A line was
  marked `token_revoked` in the store before the revoke call, so a revoke that failed was never
  tried again and the token stayed live; now it is marked only once the revoke succeeded, a
  failure leaves the line as it was, `sites/agentcancel` and `sites/agentlink` answer
  `not_revoked: [token ids]`, the audit row says "could not be revoked", and the next cancel,
  line, status or daily run tries again. (3) An expired line's unused token was revoked only
  when the site's next line was made, and never if that came more than a day later (the entry
  is dropped a day after its expiry); now `sites/agentstatus` revokes it when it finds the line
  ended, and run-daily has a new step, `kit tokens`, for each site (also one still waiting for
  its first lines), that revokes every ended line's unused token and tidies the file. (4) All
  kit routes shared one rate limit per address, so an agent that read its steps a few times
  could be refused its keys; each route (the bare code, `steps`, `keys`, `install.sh`,
  `leads/`, `report`, anything else) now has its own limit, the same 10 a minute with a burst
  of 5. **Why:** the open item on the one line for an AI agent (HANDOVER/00). **Who:** admins
  who connect a site with an AI agent; server admins (a new run-daily step). **Do:** nothing.
  The nginx 403/413 pages without `no-store` stay open (server config). **Checked:** new
  `tests/test_kit_agent_tokens.py` (the file's bytes, mtime and inode unchanged after refused
  and late reports; a revoke made to fail with a locked database or a disk error keeps the
  token live and unmarked and is done on the next try; agentstatus and the daily run revoke an
  expired line's unused token and keep a taken line's; steps read past their limit leave the
  keys and installer answering 200); each new test fails on the code before the fix; full
  suite OK.

### Social networks for the days before 2.34.0: the recount that fills them, written down

- **Docs and a test; no code change.** Days stored before 2.34.0 say "Not recorded" in Social
  networks (Sources tab and All sites). Skald already has the road that fills them:
  `backfill --days N --force` counts stored days again from the raw log with the running
  version, which stores every day kind (`social_networks`, and 2.33.0's `direct_likely`, among
  them), and `audit --day D` runs every registered second count, `audit_social` included, on
  each recounted day. The help (Where visitors come from, "Fill in the days before 2.34.0") and
  `deployments/skaldanalytics.com/README.md` ("fill in Social networks") now give the steps,
  how far back the logs reach (14 days, and only from a site's first shipped line), and what
  else the recount changes. **Why:** the 2.34.0 open item "no backfill yet" (HANDOVER/00).
  **Who:** server admins; on skald-vps, the deployer after the 2.34.0 upgrade. **Do:** after
  upgrading, `backfill --days 14 --force`, then `audit --day D --withhold` for each of those
  days; each must say "all match". **Checked:** a new test in `tests/test_social_networks.py`
  stores a day, removes its `social_networks` (a day from before 2.34.0), shows that a plain
  backfill skips it, that `--force` stores the networks exactly as a fresh day has them, that
  the audit matches, and that a planted wrong network count fails that day's audit; full
  suite OK; help rebuilt.

### Docs: CLASSIFICATION.md split in two, rules and patterns

- **Changed (docs only).** CLASSIFICATION.md was at 989 lines, under the 1000-line limit by
  11. Its "The patterns" section (`AI_TRAINING` to `ours`, with "Checking the name lists" and
  the Bing Copilot note) is now CLASSIFICATION-PATTERNS.md (356 lines); CLASSIFICATION.md keeps
  the five groups, the order of the rules, the inferred rows, page views, source types, log
  lines, line order and what the log cannot know (658 lines), and its "The patterns" heading
  now lists the moved sections with links to them. No rule's wording or number changed. Links
  to a moved section (COUNTING-TRAPS.md "PROBE", `tools/check-bot-names.py`,
  DATA-CONTRACT-CRAWL-HEALTH.md, HANDOVER 00 and 03, README) now point to the new file.
  **Why:** the next rule would have pushed the file over the limit (HANDOVER/00 open item).
  **Who:** people who read the counting rules. **Do:** nothing; the MCP resource
  `skald://docs/counting` still serves CLASSIFICATION.md, with the groups and what the figures
  cannot know. **Checked:** the two files joined again, less the new pointer and header, equal
  the old file line for line; full suite OK.

### Help and privacy notice: what the script tag keeps in the browser, and where it loads from

- **Fixed (docs and wording only; the tag is unchanged).** The Tracking script guide and the
  privacy notice Skald writes said that with visitor IDs off the tag "stores nothing in your
  browser". `skald.js` keeps the visit's source (the referring site, without `www.`, and the
  `utm_source` value) in the tab's session storage as `skald.src`, with IDs on or off, so a
  visit's later pages carry the same source; the browser deletes it when the tab closes. The
  guide now has "What the tag keeps in the browser" (`skald.src`; with IDs on also `skald.vid`,
  `skald.sh` and the `skald_vid` cookie; nothing under Do Not Track, GPC or before consent), and
  the notice has a line for the source with IDs on or off. The Privacy guide, the notice and the
  Integrations page said the tag loads "from your own site": as Skald gives it, it loads from the
  Skald server and posts there, and from your own site only when your server passes it on; they
  now say so, as does the Tracking script guide's "never to a third party" line. BEACON.md and
  INTEGRATIONS.md said the same about storage and now match the code. The Security guide's
  Cloudflare path for lists (Manage account › Configurations › Lists) is now Cloudflare's
  current one, Settings › Lists. **Why:** found while grading the website (entry below): the
  guides and the notice must say what the code does. **Who:** sites that use the script tag and
  paste Skald's privacy wording; admins who upload the block list to Cloudflare. **Do:** copy
  the privacy wording again from Settings › Data retention and replace the old lines.
  **Checked:** read against the tag's own code (`webapp/snippet/skald.js`) (`src()`, `id()`, `drop()`,
  the `skald.sh` ask); Cloudflare's "Create a list in the dashboard" page read on 24 October
  2026 (last updated 16 April 2026); `tests/test_privacy_notice.py` now checks the source line
  in every combination and that "from our own site" is gone; full suite OK; help rebuilt.

## 2.34.0 (2026-10-24)

Traffic from each social network, on one row and across all your sites. Traffic › Sources
has a Social network tab (X, LinkedIn, Facebook and more, every address of a network added
up), and All sites has one table with every site's Search, Social, X, LinkedIn, Facebook,
Instagram, Reddit, YouTube, AI and Direct.

### Added: social networks, per site and across sites

- **What changed.** Traffic › Sources has a new segment, **Social network**: one row per
  network (X, LinkedIn, Facebook, Instagram, Threads, Reddit, YouTube, TikTok, Pinterest,
  Bluesky, Mastodon, Hacker News, Quora, Telegram, WhatsApp, Slack, Discord, and "Social,
  network not named"), each adding up its hosts, apps and tags: X is `t.co`, `x.com`,
  `twitter.com` and the X app; LinkedIn is `linkedin.com`, `lnkd.in` and its app. A row opens
  how its visitors were matched and the pages they landed on, in the address
  (`#traffic/sources?src_seg=social&net=x`). The site picker (All sites) has a new table,
  **Where visitors came from, all your sites**, for today, 7, 30 or 90 days
  (`#sources-30d`), each figure linking to that site's Sources with the network open; it
  shows only the sites the viewer may open.
- **The rule.** A visit counts once, in one network: by its referrer host or app; with no
  referrer, by the words of `utm_source`, then `utm_medium`, then a social ad click id
  (`fbclid` Facebook, `li_fat_id` LinkedIn, `ttclid` TikTok, `twclid` X). A tag naming two
  networks or none counts as "Social, network not named". The networks add up to the
  Social media row. No source is reclassified: `producthunt.com`, `threads.com`, `fb.me` and
  Mastodon servers other than mastodon.social stay Other website.
- **Why:** the owner wanted traffic from X, LinkedIn and the other common networks without
  drilling down, and across all sites. X arrived as separate `t.co`, `x.com` and
  `twitter.com` rows, and nothing grouped them.
- **Who:** everyone with a dashboard. **Do:** nothing. Figures start from the first day
  collected with this release; earlier days say "Not recorded". The X and LinkedIn apps
  often send no referrer: those visits stay in Direct, where Direct, likely (2.33.0) can
  show them as an in-app browser.
- **Checked:** stored as the day kind `social_networks`, counted a second time by
  `audit_social.py` from the raw lines, sharing only `social_names.py`; a day that disagrees
  is withheld. The across-sites table adds no figure: it reads each site's stored, verified
  days. Unit tests for every network's hosts, app referrers, hosts that are not social, the
  tag rule, the audit agreeing and failing (also live), the address keys and the
  across-sites rights rule (one organisation never sees another's row); a node test of the
  page logic; the rebuilt demo viewed at desktop and phone width (the across-sites Social
  and X figures match the site's own Sources tab).
- **Demo.** Some X, LinkedIn and Reddit visits now arrive by `x.com`, `twitter.com`,
  `lnkd.in`, the X and LinkedIn apps, `l.facebook.com` and `l.instagram.com`, chosen by the
  visit's second, never by a random draw, so no other demo figure moves.

### Tests

- `test_accounts_hardening.ScryptSlots` (at most two password checks at once) failed once
  on the 2.33.0 records commit under a machine load of about 25 and passed on the rerun and
  5 of 5 times alone: a timing test, not a code change. Noted as an open item.
- **A wrong tag, removed.** The first publish of 2.34.0 failed on a timing test
  (`test_live`, "live took 18.0s", limit 15 s) and merged nothing, but `v2.34.0` was tagged
  on the public repo anyway, on the 2.33.0 commit (23:38 UTC). It was deleted about a minute
  later; its Docker image and release runs were cancelled during their tests, so no image or
  release was made. The timing test fails on the 2.33.0 code too on a machine with a load of
  90 or more; 2.34.0 was published again once the load dropped.
- The second publish stopped on the public copy's privacy sweep: a test referrer with a user
  part before the host looked like an email address. It is now `https://u:@x.com:443/a`, which
  checks the same thing (a user part before the host is ignored); the social tests pass.

## 2.33.0 (2026-10-24)

Direct traffic gets a likely cause, and sales can alert you. Sources shows which Direct
visits were likely a payment return, an in-app browser or a shared link, always as an
estimate and counted twice. A new sale alert (off until you turn it on) tells you about each
counted sale, and optionally each refund, by mail, Slack or webhook.

### Added: Direct, likely

- **What changed.** Each Direct visit (no referrer, no campaign tag) gets at most one likely
  reason, first match wins: a **checkout or payment return** (a Stripe, PayPal, Razorpay,
  Checkout.com or Adyen return parameter with its own prefix, or a checkout's end page such
  as `order-received`; a bare `/success` or `/thank-you` is left out, as a form's thank-you
  page looks the same), else an **in-app browser** (Facebook, Instagram, LinkedIn, Gmail,
  Google app, X, TikTok, Snapchat, Pinterest, WeChat, Line, or an unnamed web view), else a
  **shared link** (a share marker such as `igshid=` or `ref=whatsapp`, or an app's link
  preview of the same page up to 30 minutes before). The rest stays plain Direct. Shown under
  the Sources grid as "Direct, likely (inferred)" and in the visitor drawer; nothing is moved
  out of the Direct row. New day kind `direct_likely` in `campaigns.json`, `likely_direct` on
  journeys. Only the reason, the app or provider and counts are kept, never a query value.
  A known weakness, written in the docs: a link preview is matched by page and time only, so
  a page previewed often (the home page) marks more of its Direct visits as likely shared.
- **Why:** most visits are Direct, and owners could not tell what they were; the request
  line and the log often say more.
- **Who:** every site, from the first day collected after the upgrade; earlier days say
  "Not recorded". **Do:** nothing. `attribution.direct_likely: false` turns it off;
  `attribution.share_window_minutes` changes the preview window.
- **Checked:** a second count, `audit_direct_likely.py`, from the raw lines with its own
  code, sharing only the name lists (`direct_names.py`), in the daily and live audits (a
  day that disagrees is withheld); unit tests for each reason, the order, the non-matches,
  the switch and window, and the audit agreeing and failing; a node test of the page's
  reading; the panel drawn on a demo build.

### Added: sale alerts

- **What changed.** When a lead gains a sale value that Leads & sales > Revenue counts,
  Skald opens one alert, sent the way every alert is: the site's alert mail, the
  `alert.opened` webhook (Slack included) and Site > Alerts. A second switch alerts on each
  counted refund part. Both are per site and off by default, with an optional minimum per
  currency (`alerts.sale_minimum`, for example `USD 100, EUR 90.50`; a currency not listed
  alerts at any amount). One alert per sale, ever: a hashed key is saved before anything is
  sent, so a restart, recount, rebuilt file or replayed delivery never repeats one (a crash
  at that moment loses that one alert rather than sending it twice). Only sales received
  after the switch was turned on and made in the last 72 hours alert; test leads and days
  before `revenue_since` never do; at most 20 a run, the rest on the next. The message has
  the site, the amount as the dashboard shows it, the stage, the tool, the lead's source,
  first touch, campaign, landing page and label, new customer or renewal, and the time;
  never a name, email, address or customer reference. The sale alert also needs "All
  alerts" on; when that switch comes back on, sales of the last 72 hours received while it
  was off alert then.
- **Why:** the owner wanted to hear about sales as they happen, without watching the
  Revenue tab.
- **Who:** sites that send sale values (2.32); nothing changes until an admin turns it on.
  **Do:** nothing; to use it, turn on All alerts and Sale on Site > Alerts.
- **Checked:** `tests/test_alerts_sales.py` (18 tests: sent once, not resent after restart,
  replay or rebuilt file, minimum, off by default, test lead skipped, `revenue_since`,
  refunds, the per-run limit, currency formatting checked against the browser's formatter
  for all 170 currencies, a failed mail, a crash while sending, Slack retry).

### Release checks

- Each feature was built on its own copy of 2.32.0 and passed the full suite there (2,970
  tests each); merged, with the generated help files rebuilt from the merged guides, the
  full suite and the JavaScript tests pass.
- **Fixed before release.** The merged suite found one error: `data_reports.campaigns` now
  reads the page's config for the Direct, likely note, and an older test's stand-in page had
  none. The stand-in now has one (a real page always does). **Who:** no one; caught before
  release. **Checked:** that test and the Direct, likely tests.
- **Demo.** The sample site now has Direct visits with a likely cause (a few share markers,
  a Stripe return, and about one iPhone visitor in eight browsing inside the Instagram app),
  chosen by time and address, never by a random draw, so every other demo figure stays as it
  was. Screenshots: `direct-likely.png` and `alerts-sale.png`, from the rebuilt demo.

## 2.32.0 (2026-10-24)

Leads carry money. Send a value and a currency with a sale, from Stripe, any payment tool
through Zapier, Make or n8n, or your own server, and Leads & sales > Revenue shows which
sources, pages, campaigns and AI assistants made money, with refunds, renewals and lifetime
value. Each currency stays its own; nothing is converted. Every figure is counted twice.
**Stripe users:** add `invoice.paid`, `invoice_payment.paid` and `charge.refunded` to the
Skald endpoint's events for renewals and refunds.

### Added: revenue on leads

- **Server: money on every lead, counted and recounted.** The `lead` and `json` hooks, the
  lead files (PHP, Node, Python) and the WordPress plugin's `skald_leads_lead` filter take optional `value` and `currency`
  (ISO 4217, kept as whole minor units), `customer_ref` and `tags`, and a new stage `refunded`.
  A bad one is dropped with a note in the answer and the delivery log, never refused. Stripe
  now keeps the amount, currency, customer and payment intent of each checkout, and reads
  `invoice.paid` renewals and `charge.refunded` (one refund row per sale, raised to Stripe's
  running total). conversions.json gains per-day `revenue` per currency (gross, refunded, net;
  sales, refunds, new customers, renewals; by source, first source, campaign, landing, country,
  device, tool, label, tag), `currencies` and `ltv` (lifetime value by first source).
  Currencies are never converted. GET `/traffic-hooks/<site>/leads`, `skald conversions list`
  and the lead drawer return the value, currency, customer ref and tags. conversions.sqlite
  goes to schema 9: the table is rebuilt for the new stage, every row kept with its id, test
  mark, label and identity, a copy of the old file kept first (`conversions.sqlite.v8.bak`);
  `store.py`'s tables moved to `conversions/schema.py`.
  **Why:** the owner wants Skald to say which source, page, campaign and AI assistant made
  money, without an adapter per payment tool. **Who:** sites that send a value, and Stripe
  users. **Do:** nothing to keep working. For revenue, send `value` and `currency` with paid
  leads, and subscribe the Stripe endpoint to `invoice.paid`, `charge.refunded` and
  `invoice_payment.paid` too.
  **Checked:** `audit_revenue.py` recounts every figure by its own SQL and re-sums the money
  from the hook spool with its own reader; a day either disagrees with is withheld, `ltv` too.
  New tests (tests/test_revenue.py, tests/test_lead_files.py) cover the field rules and notes,
  the schema 9 rebuild of a schema 8 file built in the test, Stripe renewals, partial and
  out-of-order refunds and ISK, two currencies and JPY, test and removed rows, the audit
  agreeing on good data and withholding a changed sale or refund, the reconcile GET, the CLI
  list, the lead drawer, and the Python helper passing the new arguments.
- **Server: fixes from an independent review, before release.** The review found eight
  defects in the money. (1) Stripe sends `charge.refunded` for every charge of the account; a
  refund with no sale kept was subtracted under "Unknown". A refund now counts only on its
  counted sale, in its currency; any other is kept, never subtracted, and shown in the new
  conversions.json `refunds_without_sale` (`{count, currencies}`: every refund row no figure
  counts, also one kept without a value; see the second review below). (2) A refund that came
  before its sale was counted twice once raised (1000, the checkout, then 3000 gave 4000), and
  a whole refund sent first stayed without a value: the sale now takes over every refund that
  waited for it, and fills in a whole one's value. (3) Stripe's API 2025-03-31 ("basil") took
  `payment_intent` off the Invoice and `invoice` off the Charge, so a renewal's refund could not
  find its sale: Skald now reads `invoice_payment.paid` (Stripe's InvoicePayment, its `invoice`
  and `payment.payment_intent`) and keeps the link (`pay_links`); older payloads still work.
  (4) A refund was not checked against its sale (500 on a 49.99 sale gave net -400.02; a EUR
  refund on a USD sale opened a EUR block): it is now cut to the sale's value, or kept without
  a value in another currency, each with a note to the sender. (5) Tags kept `555-123-4567`,
  `555.123.4567` and `192.0.2.10`: a tag value with 7 or more digits in all or shaped like an
  IPv4 address, and a personal key (`phone`, `email`, `ip`...), is now dropped, in the store and
  the spool alike (`conversions.tag`). (6) Decimal's 28-digit precision rounded
  `49.990000000000000000000000000000000001` to 49.99 while the second count refused it, and the
  day was withheld: amounts are now read with exact integer arithmetic. (7) The WordPress plugin
  took `skald_value`, `skald_currency` and `skald_customer_ref` from the visitor's own form
  post, so anyone could post any amount: removed; money comes only from the server-side
  `skald_leads_lead` filter, and `$_POST` is read through `wp_unslash`. (8) A raised refund
  was counted on the first refund's day, so a raise more than 30 days later showed in no
  period: each part of a refund is now kept with its own time (`refund_parts`) and counts on
  the day it arrived; `refunds` counts the refunds that arrived. **Who:** sites that send
  refunds or use Stripe, and WordPress sites. **Do:** subscribe the Stripe endpoint to
  `invoice_payment.paid`; a WordPress site that put money in hidden form fields moves it to the
  `skald_leads_lead` filter. **Checked:** tests/test_revenue_review.py, a test per defect
  through both counting roads (it failed before each fix: 22 of its tests), a table of 34
  hostile amounts read alike by both readers, the reviewer's own probe scripts rerun, and the
  full suite.
- **Server and dashboard: fixes from a second independent review, before release.** (1) Every
  `ok` day before a site's first value carried `revenue: {}`, a "known none" for days when
  amounts were simply not sent, and revenue per visitor counted those days' visitors: revenue
  is now recorded from the local day of the first row with a value, given as conversions.json's
  new `revenue_since`; a day before it has no `revenue` at all. The second count finds that day
  with its own reader and checks it, and that each day carries a block exactly from then. The
  Revenue tab says "Values are recorded from <day>", and leaves out any day before it. (2) An
  amount of more than 4,300 digits raised an error and lost the delivery (a json batch lost
  every record): amount text over 30 characters is now never parsed, in both readers, and the
  lead is kept without a value, with a note; a huge JSON number is read as text. (3, 4) The
  spool recount applied a removal to the whole spool, before or after it happened, and missed
  a refund that had moved onto its sale: each removal is now replayed at the time it happened,
  on the row's ref at that time, so removing a sale, a sale removed and sent again, and a moved
  refund removed all agree with the store instead of withholding the day. (5) A refund kept
  without a value (another currency than its sale, or unreadable) was counted nowhere: it is
  now listed in `refunds_without_sale` on both roads, and the tab's line says which refunds it
  holds. (a) A refund with an unreadable value, then a whole refund, then the sale: the whole
  refund was answered as a duplicate; it now waits for the sale's value and counts. (b) A
  refund of 0 counted as one refund in the Refunds tile: a refund or a part of 0 is no refund.
  (c) `customer_ref` kept `198.51.100.7` and `15551234567`: a reference shaped like an IP
  address, or of only digits and `+ ( ) . -` with 7 or more digits, is now dropped with a note,
  in the store and the spool (ids such as `cus_9`, `c_10293847` and UUIDs are kept). The docs
  now also say that a refund that came before its sale and is cut or emptied when the sale
  arrives gets no note. **Who:** sites that send money. **Do:** nothing. **Checked:**
  tests/test_revenue_rereview.py, a test per finding through both roads (16 of its first 17 tests
  failed or errored before the fixes, the 18th before its own), tests/js/revenue.mjs for the
  tab, the reviewer's probe scripts and the schema 8 upgrade probe rerun, and the full suite.
- **Dashboard: Leads & sales > Revenue.** A new tab after Sources answers "which sources, pages
  and campaigns made money?": net revenue (sold less refunded), sales, refunds, new customers,
  renewals and revenue per visitor (net revenue over the visitors of the same checked days,
  given over at least 10 visitors), then net revenue and sales by source, first touch,
  campaign, landing page, country, device, tool, label or tag, and a folded lifetime value by
  first source. Each currency is its own set of figures, picked with a Currency switch; the
  others are listed under the numbers as "Also in this period, never added". A withheld day is
  left out and said in the conversions' own words; a site that never sent a value gets the
  how-to. The currency, the breakdown and the tag are in the address (`cur`, `by`, `tag`), and
  each landing page has its copy and open icons; `tag=plan` alone lists every value of that tag.
  The Refunds tile says each refund counts on the day it arrives and a later, larger total
  counts the difference on its own day, and a line under the table counts the refunds kept
  without a counted sale (`refunds_without_sale`), never taken off. Money uses the file's own
  decimals (`currencies`). **Why:** the server side above gives the
  figures; this is where people read them. **Who:** every site; it says "No revenue yet" until
  a value arrives. **Do:** nothing. **Checked:** tests/js/revenue.mjs (money per currency in
  minor units, JPY and KWD decimals, withheld and not-recorded days, never adding USD and EUR,
  the address, copy and open, the empty state, refunds without a sale, `tag=plan`), run from tests/test_navigate_js.py; walked in
  a browser on the demo at 1440 and 390 px, light and dark.
- **Dashboard: a lead's drawer shows its sale.** Value (with its currency), what was refunded
  on it, the customer reference with a copy icon, and its tags, only when the lead carries
  them. **Why:** to see one sale's money beside its journey. **Who:** sites that send a value.
  **Do:** nothing. **Checked:** tests/js/revenue.mjs; the demo's trials paid for annual plans.
- **Docs and help.** A new help guide, Revenue (`docs/help/revenue.md`, in the app's Help and
  at /docs/revenue/ on the website), and `docs/INTEGRATIONS-REVENUE.md`: the fields, renewals,
  refunds as the total refunded so far (a later, larger total counts the difference on its own day), the tag rules, amounts in cents divided by 100, and recipes for
  Zapier, Make and n8n, with the field names of Polar, Dodo Payments, Paddle, Lemon Squeezy and
  Gumroad cited from each one's own webhook documentation (and "check your tool's payload"
  where a tool's refund carries only its own amount). Webhooks, Send leads from your backend,
  Leads & sales, `docs/INTEGRATIONS.md`, `docs/ROUTES.md`, the README's feature list and
  `docs/COMPARISON.md` (a revenue row, checked 2026-10-24 for GA4 and Plausible only) say the
  same. **Why:** the brief asked for every document in the same release. **Who:** anyone
  setting revenue up. **Do:** nothing. **Checked:** tests/test_help.py, tests/test_about.py,
  `tools/build-about.py` run; each tool's field names read from its docs on 2026-10-24.
- **Demo: sample sales.** `tools/demo.py` gives its Stripe checkouts amounts in USD and EUR,
  Stripe customers, monthly `invoice.paid` renewals for one in three and a part refund; and the
  site's server sends trials through the lead hook that are paid 14 days later for an annual
  plan, with a customer reference and the tags `plan` and `billing`. Each sale carries its
  visit's touch, so revenue splits by source. Picked by the sale's number, never from the seeded
  draws, so the rest of the demo is as it was. **Why:** the live demo and the README screenshot
  show the Revenue tab with real figures from the real pipeline. **Who:** the demo only. **Do:**
  nothing. **Checked:** the demo built, its second counts agreeing (no day withheld).
- **Website.** Stripe payment attribution: a new fold follows one sample customer through a
  paid Checkout, a renewal, a part refund and the refund raised to the whole sale; the hero
  now shows the amount, currency, customer ID and payment intent as read, and the set-up, the
  limits and the FAQ name the five events (with `invoice_payment.paid`). Zapier, Make, n8n: a fold maps Polar, Dodo, Paddle, Lemon Squeezy
  and Gumroad sales (amount in cents, divided by 100). Backend lead file: a fold shows which
  money fields Skald keeps or drops and the answer's own note. Lead attribution: revenue by
  source, per currency. The features page names revenue. **Why:** the pages said Skald never
  reads amounts, which is no longer true. **Who:** website readers. **Do:** nothing. **Checked:**
  the site's build ends "problems: none" with every rubric check passing on these pages.

### Tests: the set-up checklist test no longer depends on the machine it runs on

- **Fixed.** `tests/test_setup_checklist.py` asked the real port 127.0.0.1:8766 whether a
  beacon helper was running, so it failed whenever anything listened there (on 2026-10-24 a
  preview web server did, and the suite failed on unchanged code too). It now points the
  check at a port that refuses, the "no helper" state it was written for. **Who:** people
  running the tests. **Do:** nothing. **Checked:** the test passes with a server on 8766.
- **Fixed.** The first publish of 2.32.0 stopped before anything went out: the public copy
  ran a test of the website's Markdown pages without the website builder it tests (that
  builder is not public), and the release check flagged the older changelog split out to
  `docs/CHANGELOG-2.23-2.26.md` because it names the company, as the main changelog may.
  That test now stays in the private repo, and split-out changelogs follow the main
  changelog's rule. **Who:** no one outside; nothing was published. **Do:** nothing.
  **Checked:** the publish-tool tests, then the publish's own sweep and full test run.
