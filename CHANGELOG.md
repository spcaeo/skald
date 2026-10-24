# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

### Website: the 11 feature pages rebuilt and graded (group E, live 2026-10-24)

- **Changed.** /features/ and its ten pages (dashboard, real time, alerts, counted twice,
  pages and sources, page groups, visitors and journeys, reports and exports, team and
  access, privacy and retention), each its own design from the code it describes and graded
  on `_src/pages/RUBRIC.md`; the features hub now names revenue on leads (2.32.0). /docs/
  links to /docs/guides/ and /llms.txt, and its FAQ names the guides first. **Why:** the
  owner's rebuild plan, approved 2026-10-24 ("finish all"). **Who:** readers of
  skaldanalytics.com. **Do:** nothing. **Checked:** the site build ends "problems: none"
  (61 pages graded); the 12 pages load at 1440 and 390 px with one h1, no sideways scroll,
  no NaN or "undefined", and no script error (the only failed request is the site's own
  `/traffic-js/skald.js`, which only the live server serves).

### Website: log and set-up pages rebuilt and graded (group D, live 2026-10-24)

- **Changed.** 20 pages, each its own design from the code it describes, graded 81 or more of
  90 on `_src/pages/RUBRIC.md`: the server log analytics hub and how it works; nginx, Apache,
  Caddy, Cloudflare, CloudFront, Fastly and Vercel; /docs/ and its set-up pages (add a site,
  one command, the script tag, Claude Code), which now start with "One line for your AI
  agent"; and /self-host/ with Docker, Coolify, Fly, Kubernetes, Railway and Render. Every
  control writes its state to the address. **Why:** the owner's rebuild plan, approved
  2026-10-24 ("finish all"). **Who:** readers of skaldanalytics.com. **Do:** nothing.
  **Checked:** the site build ends "problems: none"; each page's old links are kept; browser
  checks at 1440 and 390 px, with reduced motion and without JavaScript.

### Website: the Help guides as docs pages, and every page as Markdown for AI agents (live 2026-10-24)

- **Added.** Each guide in `docs/help/` is now a page at `/docs/<guide>/`, with a list of all
  of them at `/docs/guides/`, made by the same parser as the in-app Help, so the website, the
  app and GitHub say the same words. Every page of the site, and every guide, is also Markdown
  (`/features/` is `/features.md`, the home page `/index.md`), and `/llms.txt` lists every
  page and guide with a one-line summary; `/llms-full.txt` holds every guide in one file. Each
  page names its Markdown copy and llms.txt in a `<link rel="alternate">` and in a hidden line
  near the top, which shows on keyboard focus. The footer links "All guides" and "llms.txt".
  New: `_src/docs_guides.py`, `_src/page_markdown.py` (stdlib HTML to Markdown: menus, hidden
  parts and the closing band left out, cards kept as one line each).
  **Why:** AI assistants and coding agents read docs as Markdown; the owner approved
  publishing the guides this way and scoring them with Fern's agent-friendly docs check
  (item 3 of 2026-10-24). **Who:** readers of skaldanalytics.com and the AI tools that fetch
  it. **Do:** nothing. **Checked:** the site build ends "problems: none" (the "firewall"
  rule now lets "a firewall" and "any firewall" through: the guides mean the reader's own);
  `npx afdocs` 0.22.2 on a local copy scores 96 of 100 (the one failing check, content
  negotiation, needs the nginx change at upload); every guide fits at 390 px with no
  sideways scroll; new tests in `tests/test_site_markdown.py`.
  **Live:** uploaded 19:15 UTC with nginx serving `.md` as `text/markdown` and answering
  `Accept: text/markdown` with the page's Markdown (`Vary: Accept`). `afdocs` on the live site:
  99/100. Fern's Agent Score: 98/100, grade A (buildwithfern.com/agent-score/company/skald).

### Website: the main button is a warm orange with white text (live 2026-10-24)

- **What changed:** the main button on every page (`.btn-p`, `.sk-btn-p`) is now `#c84a16`
  with white text, `#b03f12` on hover, from two new colour tokens (`--sk-cta`,
  `--sk-cta-hover`). The owner also approved the first 28 rebuilt pages (A, B, C); from here
  pages ship on the rubric without a review page by page.
- **Why:** the owner asked for every page to be built around its CTA buttons ("very focused CRO
  and CTA buttons"); the main button now stands apart from the page's other colours.
- **Who:** website visitors. **Do:** nothing.
- **Checked:** the site build, "problems: none"; white on `#c84a16` is about 4.7 to 1 (AA);
  the colour and hover read back in a browser at 1440 and 390 wide.

### Website: the 11 AI traffic pages rebuilt and graded (live 2026-10-24)

- **What changed:** the AI crawlers, ChatGPT, Claude, Perplexity, Google AI Mode, AI referrals,
  crawl health, block AI crawlers and llms.txt pages, the AI traffic guide and What is GEO are
  rebuilt, each with its own hero and folds drawn from its own code (classify, bot_verify,
  bot_policy, robots, ai_likely, ai_read, ai_formats, llms_txt, crawl_health, crawler_cost,
  alerts). The robots.txt tester, the llms.txt file maker and the format sorter are JavaScript
  copies of the Python code, checked to give the same answers. All 11 graded on the rubric:
  77-84 before, 86-87 of 90 after.
- **Facts corrected on the way:** Google and Anthropic do publish address lists (Skald simply has
  no check for some of their names); Google-Extended is only a robots.txt line, no request
  carries it; the guide's referrer is the second quoted field, and its command counts requests,
  not visits; "about 60" or "about 40" names is now the 39 in the code. Claims the code does not
  back were removed (most AI Mode clicks lose their referrer, the big crawlers follow
  robots.txt, fakes probe /.env, a reason Gemini makes no fetches, any AI Overview click figure).
- **Why:** the owner: every page unique and deep, and no AI-sounding pages.
- **Who:** site visitors, once deployed. **Do:** nothing. First-hand details wait for the
  owner's OK (listed in RUBRIC.md).
- **Checked:** build "problems: none" with 29 pages graded; each page at 1440 and 390 px with no
  JS errors, 4xx, sideways scroll or raw placeholders; every visible control clicked and kept in
  the URL.

### Website: AI visibility and leads pages rebuilt; every page graded on a rubric (live 2026-10-24)

- **What changed:** the 5 AI visibility pages and the 12 leads and journeys pages are rebuilt
  with their own parts, each from its own code (answers/, conversions/ and its adapters,
  funnels, firsttouch, utm_hygiene, the WordPress plugin, the lead files). A rubric now grades
  every page out of 100 (`_src/pages/RUBRIC.md`: title pays its promise, sourced numbers,
  plain voice, every term explained, no fake proof, SEO basics, the answer in the first 100
  words, one first-hand detail). `_src/rubric.py` runs its machine checks in the build for
  graded pages. The first 18 pages were graded and fixed: 75-82 before, 84-86 of 90 after.
  "More on wordPress" headings now keep the name's capital. Facts corrected on the way:
  Perplexity is sent "en", not "en-GB"; leads count finished bookings and forms, not
  payments; the funnel "Contains" match is written in the funnel's link only.
- **Why:** the owner: every page unique and deep, and no AI-sounding pages.
- **Who:** site visitors, once deployed. **Do:** nothing. First-hand details wait for the
  owner's OK (listed in RUBRIC.md).
- **Checked:** build "problems: none" with 18 pages graded; site tests; each page at 1440 and
  390 px with no errors or sideways scroll.

### Website: every page its own, starting with AI traffic (live 2026-10-24)

- **What changed:** /ai-traffic-analytics/ rebuilt top to bottom: a hero that sorts sample log
  lines live, a drag-to-compare of a script tag against the log, a step-through of one ChatGPT
  question, a crawler check that stamps Verified or Spoofed, a look-back window you drag to
  see a "likely from ChatGPT" visit appear, llms.txt demand and a suggested file, crawler cost
  beside a sitemap grid, and a rule builder that writes Skald's real nginx lines. The tag line
  under the logo is plain and sharp (no italics). A page can now load its own CSS and JS
  (`css`, `js` in page.json; the build dropped them before). `_src/pages/REBUILD.md` tracks
  every page; `_src/pages/LEDGER.md` lists every signature part so none repeats.
- **Why:** the owner: 71 of 90 pages opened on the same log window, and every fold must speak
  to a problem or an outcome, be engaging, and rest on the real code.
- **Who:** site visitors, once deployed. **Do:** nothing.
- **Checked:** build "problems: none"; site tests; all 111 pages at 1440 and 390 px; every
  control on the page tried (window 20 and 8 minutes, the rule builder, the URL keeps each
  choice).

### Website: skaldanalytics.com rebuilt, one page per feature (live 2026-10-24)

- **What changed:** the marketing site has 100 new pages built from `_src/pages/` (a page.json
  and its HTML parts each): the home page, AI traffic (crawlers, live fetches, clicks, cost,
  crawl health, rules), AI visibility, leads and journeys, server log analytics, self-hosting,
  docs, features, comparisons, Google Analytics alternative, security, roles, integrations,
  insights, pricing, demo and the author page. A new dark header with a light menu panel (the
  dark-on-dark menu was hard to read), the tag line under the logo, and a new footer on every
  page, old ones too. The old pages (security, check, install, about, story, privacy, contact,
  beta, what's new, 404) keep their words.
- **Fixed on the way:** the dark button in the orange end band showed no text (owner's
  screenshot); the yearly price switch did nothing; browsers kept old CSS and JS (each link now
  carries a hash of the file); `{{TRIAL}}` and `{{DEMO}}` were left as raw text in some heroes;
  related-card titles lost their capitals ("ai traffic").
- **Why:** the owner asked for every feature to have a page that says what it is, why it
  matters and what to do next, with the same look and motion as the new home page, and each
  page built for search.
- **Who:** visitors of skaldanalytics.com, once it is deployed. **Do:** before deploying, the
  live Skald's render test for skaldanalytics.com must accept `/css/`, `/js/` and `/fonts/`
  as page assets, or real visits to the new pages may count as bots. Prices still show
  "Proposed prices, not final yet" (`PRICES_PROPOSED` in `_src/conf.py`).
- **Checked:** the build ends "problems: none" (one H1, title and description lengths, dead
  links, banned claims); the site's tests (one browser test of the check page's agency mode fails
  now and then, on the last commit too); the full test suite; every sitemap URL opened at 1440 and 390 px wide
  (no sideways scroll, no script errors, no broken assets, every switch and tab has a choice).
  Words checked against the product's own limits (`_src/pages/FEATURES.md`).

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

## 2.31.1 (2026-10-24)

### Fixed: a site's own page about WordPress counted as a probe

- **What changed:** the bare path words `wordpress` and `wp` mark a WordPress probe only at the
  start of the path (`/wordpress/`, `//wp/wp-includes/...`, as scanners send them). WordPress's own
  names (`wp-admin`, `wp-login`, `wp-content`, `wp-includes`, `wp-json`, `wp-config`, `xmlrpc`)
  still mark one anywhere. Same rule in the classifier and in Security's categories.
- **Why:** skaldanalytics.com's new page `/integrations/wordpress/` (about the WordPress plugin)
  was read as a probe: its readers' page views left the counts, and Security mailed "Possible
  exposure ... answered 200 (45,715 bytes)" for it, an hour after the page went live.
- **Who:** sites with a page whose path has a `wordpress` or `wp` segment after the first
  (`/blog/category/wordpress/`).
- **Do:** nothing. Close the alert in Security if it is still open.
- **Checked:** a new test (`tests/test_wordpress_pages.py`: 6 pages are not probes, 12 scanner
  paths still are); the full suite; a scan of every kept log on Skald's own server (68 files,
  8 sites): the fix moves exactly one request, today's read of that page, so no day needs a
  recount.

## 2.31.0 (2026-10-24)

Add a site gives one line to paste into your AI agent. The line holds a one-time code, never a
key; the agent takes the keys once, connects the site and reports back while you watch.

### Added: one line for your AI agent sets up a site

- **What changed:** Add a site's step 3 is now **Your AI agent** ("Which AI agent are you
  using?": Claude Code, Codex, Cursor, Claude.ai or ChatGPT, Another agent). Step 4 shows one
  line to paste into the agent: `set up Skald for <site> — read <your Skald>/traffic-kit/llms.txt
  and use code <code> (works once, 24 hours)`. The agent reads the site's steps, takes the
  keys once with curl into a 0600 file (a new sending token, ingest only for that site, and the
  site's lead secret, copied when it has one), connects the logs, adds the script tag and the
  lead file, asks the privacy question, and sends a short report. Step 5, **Watch it connect**,
  ticks each step and shows the report in plain words; the admin applies what fits ("Use these
  page assets"). The code is hidden until **Show code**. Under it, "Is it safe to paste this
  into a chat?" says what the code is. **Cancel this line** ends it at once, a new line cancels
  an older one whose keys were not taken yet, and step 5 says when the keys were taken. Skald keeps only the code's hash and
  the keys sealed with it. The keys answer only curl or Wget, and the agent fetches its steps
  with curl too, so a web reader or fetch tool cannot pass them into a chat. The keys file also
  holds a report key: the report needs it in the `X-Skald-Report-Key` header (403 without), so
  only the agent that took the keys can send or replace it. The sending key can only send log lines; the lead secret sends leads and reads
  back the site's lead list (reference, stage, time; no personal details). After the keys are
  taken, the steps, installer, lead files and report keep answering until the expiry (no
  secret in any). Chat-only agents get the one command instead. **No AI agent: set it up by hand**
  keeps the old steps. Connections has **Set up with your AI agent** for a site that exists.
  New routes: `/traffic-kit/llms.txt` and `/traffic-kit/<code>/steps`, `keys`, `install.sh`,
  `leads/<file>`, and `POST .../report`; dashboard calls `sites/agentlink`, `sites/agentstatus`
  and `sites/agentcancel`. The address keeps `agent=` and `link=` (a hash, never the code).
- **Why:** the owner: adding a site should be as easy as treg's onboarding, one line to paste
  into an agent. Unlike treg's long-lived token, Skald's line holds a one-time code.
- **Who:** owners and admins adding a site. Sites already sending need nothing.
- **Do:** self-hosters who run their own front nginx from DEPLOY.md's sample must take its new
  `location ^~ /traffic-kit/` block: the nested `location` for `/traffic-kit/<code>/report`
  (POST, 16 KiB), or the agent's report is refused, and `error_log stderr crit;`, or nginx's
  error log can hold the code. Then `nginx -t` and reload. Everyone else (the Docker image has
  both): nothing.
- **Checked:** the full suite, 2875 OK, with new tests (tests/test_kit_agent.py, 36;
  tests/js/agent-setup.mjs); a real curl run against the routes; the wizard walked in a sandbox,
  67 of 67 checks. A real Claude Code run on a local Docker test site passed all 7 checks, with
  the first log lines in about 2 minutes. That run found two problems, both fixed: a dry run
  with no token stopped, and the check script's probe showed as a refusal. An independent
  review found 8 problems, all fixed before release:
  - nginx's error log wrote the request line, code included;
  - anyone with the code could send or replace the report;
  - two lines made at the same moment cancelled each other;
  - step 4 restored from an address made a new line, cancelling the one already sent;
  - a repeated key fetch wiped the keys file;
  - a downgrade to an older image would hand out the agent's token as an install link;
  - a site value shaped like a placeholder broke the steps page;
  - a second report was not shown.

  Re-run after the fixes: a second real Claude Code run passed every check, with the first
  log lines in about 1 minute 19 seconds. Two lines made at once left one live, no code was in
  the container's logs, a report without its key got 403, and a second key fetch kept the keys.
  It found one more problem, fixed: Claude Code run from an allow list refuses to write a file
  with `>`, so step 8 now pipes the report key into `curl -H @-` and writes no header file.

  A second independent review of the fixes found five more, fixed before release: two
  lines made in the same instant could both stay live (each read the clock before the lock); a
  failed **Make the line** left no Try again button; step 3 could lose the keys if the agent
  skipped moving the file into place (the one fetch line now moves it only when it holds the
  keys); the check script's marker hid any refusal, not only the 401 it expects; and step 5
  kept asking when the organisation was read only (402). The reviewer's race probes now always
  end with one live line (30 runs of 8 at once). Left as known: nginx's own 403 and 413 pages on
  `/traffic-kit/` carry no `no-store` header (they hold no code); the step 8 report needs curl
  7.55 or newer (the steps say so).

## 2.30.0 (2026-10-23)

Connecting a site and its leads in one step: one command on the server (with or without Docker,
the token made for you), one file and one line for leads (or a WordPress plugin, or a plain key
for Zapier and form tools), and the whole set-up in one zip, by mail, that a person or Claude Code
can follow alone. Plus two fixes from a 24-hour review of the live server's logs.

### Added: one command connects a server's logs

- **What changed:** Send this site's visits to Skald (and Add a site) has one choice, "My own
  server (nginx or Apache)", for servers with or without Docker, and three steps instead of four.
  The Run step shows `curl -fsSL <your Skald>/traffic-kit/<code> | sudo bash`. Skald makes the
  sending token itself. The link works once, for 24 hours; Skald keeps only a hash of the code
  and the token sealed with it, so its disk never holds a usable token. A browser or a mail's
  link preview only sees the command and never uses the link up; a used link prints "This
  install link was used or has expired" and changes nothing. The new `/traffic-kit/` path is
  answered by the beacon helper (docker/nginx.conf has its route).
- **The installer** (one file, also **Download as one file**, `skald-install-<site>.sh`) uses
  Docker when the server has it, else a systemd service with Python 3.9 or newer (the shipper is
  inside the file). It finds the site's access log in nginx's or Apache's settings by itself and
  asks only when it cannot tell (`--log`, `--dry-run`, `--yes`). It leaves `skald-ship-check` and
  `skald-ship-uninstall` on the server. Running it again is safe and keeps the place in the log.
  The Test step starts by itself.
- **Why:** the owner: adding a site was "very long and confusing": four steps, a token to make by
  hand, a zip to copy, unzip and run, and a question for the log file.
- **Who:** owners and admins adding a site. Sites already sending need nothing. **Do:** nothing.
- **Checked:** tests/test_kit_server.py and tests/test_kit_link_pack.py; on a clean Ubuntu 24.04
  with systemd and nginx (two sites), the real command against a Skald built from this release:
  it picked the right site's log, installed without Docker, all lines arrived, the Test said
  Connected, a second run of the same command was refused with the message, a re-run of the
  installer kept its place, and uninstall removed everything. The Docker road checked by dry run.

### Added: send the whole set-up to someone, in one zip

- **What changed:** **Send set-up to someone** (top of a site's Set up list, and in the logs and
  leads dialogs) mails `skald-setup-<site>.zip` to up to 3 addresses through Skald's own mail, or
  downloads it. It holds START-HERE.md (every case step by step), CLAUDE.md and AGENTS.md (the
  same for an AI coding agent: "give the folder to Claude Code and say Set up Skald from
  CLAUDE.md"; keys only in environment variables, never in code or git), secrets.env, the
  installer, Cloudflare and Vercel/Netlify steps, the script tag, and the lead files. **Include
  the keys** (ticked by default) puts in the sending token and the site's lead secret (a new one
  when it has none); each pack is in the audit log, never its keys. 10 mails an hour per site.
  The Node lead file is `.cjs`, because Gmail refuses zips holding `.js` files.
- **Why:** the owner's clients use Claude Code: one zip it can follow alone.
- **Who:** owners and admins. **Do:** nothing; mailing needs mail set up (Settings > Mail).
- **Checked:** tests/test_kit_link_pack.py (contents with and without keys, the mail with its
  attachment, refused without mail, the limit); downloaded from the browser and opened.

### Added: leads in one file and one line, a WordPress plugin, and a plain key

- **What changed:** Connect your leads first says what the script tag already counts with no
  code (form sends, Calendly and Cal.com bookings, phone and email clicks). The secret is made by
  itself when the site has none (a set one is never replaced without the confirm). For the site's
  own backend: pick PHP, Node or Python, download one file (`skald-lead.php`, `skald-lead.cjs`,
  `skald_lead.py`), and call one function, e.g. `skald_lead("L-1001", "demo", $email)`; the file
  signs each lead, reads `SKALD_LEAD_SECRET` first, waits at most 3 seconds and never breaks the
  form. **WordPress forms**: a plugin (Plugins > Add New > Upload) that sends Contact Form 7,
  WPForms, Gravity Forms, Elementor Pro and Ninja Forms leads with no code. The `lead` and `json`
  hooks also take `Authorization: Bearer <secret>` when no signature is sent, so Zapier's plain
  webhook step and form plugins work without signing code; a wrong key is refused like a bad
  signature, and the header is never logged. New endpoint: `POST <page>/integrations/leadfile`.
- **Why:** the owner: connecting leads needed a developer to write signing code.
- **Who:** sites that send leads. Signed hooks work as before. **Do:** nothing.
- **Checked:** tests/test_hooks_plain_key.py, tests/test_lead_files.py (the Python helper's real
  request accepted by the receiver), tests/test_integrations_leadfile.py; `php -l`, `node --check`
  and each helper posting to a local receiver; a plain-key lead kept and a wrong key refused
  through nginx on a local build. The WordPress plugin was checked against stubbed WordPress
  hooks, not a real WordPress install.

### Changed: docs/INTEGRATIONS.md split

- Search Console, Bing and AI answers moved to docs/INTEGRATIONS-SEARCH.md (the file was over
  1000 lines). **Do:** nothing.

### Fixed: a visitor who left during the public stack check printed a traceback

- **What changed:** the beacon helper no longer prints a Python traceback when a visitor closes
  the page before its answer is sent (a broken pipe or a reset connection). Any other error still
  prints its traceback.
- **Why:** the 24-hour log review on 23 Oct found one in the live container's log at 05:04 UTC: a
  visitor left during the public stack check, which takes a few seconds. Nothing was lost; it
  only looked like a crash.
- **Who:** every install. **Do:** nothing.
- **Checked:** tests/test_beacon.py `VisitorLeft` (fails without the fix).

### Fixed: `doctor` gave a wrong fix for a site still waiting for its first log lines

- **What changed:** for a site added from the dashboard whose server has not sent a line yet,
  `doctor`'s Access log line says "none yet: the site waits for its first log lines" (OK), as
  its Daily run and Days stored lines already did. A site set up by hand with a missing log
  still needs attention.
- **Why:** on 23 Oct `doctor` said NEEDS ATTENTION for a site added the day before, with the fix
  "Set logs.base to the log's file name", which was wrong: nothing had been shipped yet.
- **Who:** installs with a newly added site. **Do:** nothing.
- **Checked:** tests/test_doctor.py `WaitingSite` (fails without the fix).

### Fixed: a test of the new installer passed only on machines without systemd

- **What changed:** the test "no Docker and no systemd says what to install" now runs the
  installer with a PATH that holds the system's own tools less `docker` and `systemctl`.
- **Why:** on 23 Oct GitHub's tests failed on every Python version: the Ubuntu test machine has
  a real `/usr/bin/systemctl`, so the installer rightly found systemd and the test's "neither"
  case never happened. The installer was right; the test was not sealed.
- **Who:** nobody using Skald; anyone running the tests on Linux. **Do:** nothing.
- **Checked:** the kit tests in a Linux container with a real `systemctl`: they fail without
  the fix and pass with it.

### Fixed: help, docs and page words still described the old zip kit

- **What changed:** the site check's reason says "so one command on that server sends its log"
  (was "the log shipper kit is the way"). The Common problems table, the refusal fixes and the
  shared link's page say `sudo skald-ship-check` and `sudo skald-ship-uninstall`, and an older
  zip kit's `check.sh` is still named. The help guides Connections and If a connection does
  not work, INGEST.md, SETTINGS.md (`sites/kit` takes `server`; `sites/link`, `sites/pack` and
  `sites/packmail` listed), HOSTING.md, INSTALL.md, ROUTES.md and ADD-A-CLIENT-SITE.md match the
  code. LEADS-REFERENCE.md said "next release" for nine things that shipped in 2.26.0; it now says
  "since 2.26.0". A broken link in DATA-CONTRACT-REALTIME.md is fixed. The public copy no longer
  carries a link to the private design folder in ROADMAP.md.
- **Why:** a check of every document after the 2.30.0 work found them still telling people to
  download a zip kit and run `sudo bash check.sh`, which the page no longer offers for a server.
- **Who:** anyone reading the help or the Connections dialogs. **Do:** nothing.
- **Checked:** the full test suite; a grep for check.sh, "install kit", "shipper kit" and "next
  release" across the docs and the page's code; every relative link in the public copy resolves.

### Fixed: a failed Test gave the old kit's advice for a set-up saved before 2.30

- **What changed:** for every server way, a Test that has not heard from the site says: run
  `sudo skald-ship-check` (or an older zip kit's `sudo bash check.sh`), then where to see what
  the shipper says.
- **Why:** a set-up saved with the old choice "docker" or "systemd" opened the new one-command
  step, but a failed Test still said "run check.sh from the kit", a file the one command does
  not leave.
- **Who:** sites whose set-up was started before 2.30. **Do:** nothing.
- **Checked:** tests/js/tag-check.mjs, for "docker", "systemd" and "server" (fails without the fix).

### Fixed: a developer's shared link for a server refused the zip kits under "Other ways"

- **What changed:** a shared set-up link for "My own server" gives the one file, and the zip
  kits with and without Docker under "Other ways".
- **Why:** the link took only the method it was made with, so those buttons answered "This link
  has no install kit."
- **Who:** developers sent a set-up link. **Do:** nothing.
- **Checked:** tests/test_share_links.py `test_a_server_link_gives_every_server_kit` (fails
  without the fix).

## 2.29.0 (2026-10-22)

Leads and the pages they read can be kept for good (Settings > Data retention > Leads), and the
pages of visitors who have not signed up yet up to 400 days; a site still waiting for its first
log lines is skipped by the live audit instead of reported as a mismatch.

### Fixed: the live audit said "does not match" for a site with no log lines yet

- **What changed:** `audit --live` says "audit skipped: live <day>: <site> has no log lines yet"
  when the live snapshot is empty and the recount finds no request either, and ends 0.
- **Why:** on 22 Oct a site added that afternoon, still waiting for its server to send logs, made
  the all-sites live audit read "THE RECOUNT DOES NOT MATCH THE SNAPSHOT"; both roads were empty.
- **Who:** installs with a newly added site. **Do:** nothing.
- **Checked:** tests/test_audit_recount.py (the test fails without the fix).

### Added: keep leads and the pages they read for good

- **What changed:** `conversions.retention_days` now takes `0` (or the word `forever`): kept for
  good. Skald's nightly prune then never deletes a lead (every stage, test rows too), the rows a
  sync removed, the pages read by a visitor ID that became a lead, the lead's name and email, or
  the hook spool's lines (the raw copy the second count recounts leads from). The delivery log
  still goes after 90 days. `journeys.vid_days` (the pages of a visitor ID with no lead yet) is
  1 to 400 days. Both are now settings per site, on a new **Leads** card under Settings > Data
  retention ("Leads and the pages they read: Kept for good / N days"; "Pages of visitors who have
  not signed up yet: N days. Once they sign up, their pages are kept with the lead"), and from the
  shell: `skald settings set <site> conversions.retention_days 0` (or `forever`),
  `skald settings set <site> journeys.vid_days 400`. Each site is pruned by its own values; a
  spool day holding lines of sites with different windows is written again with only the lines
  still kept. Going from kept for good back to days, or to fewer days, asks for the site's name
  (page) or `--yes` (shell), as every shorter window does, and the page shows what would go.
  The privacy-notice wording says how long a lead's name and email, and the pages read with a
  visitor ID, are kept: "until you ask us to delete them" when kept for good, else the days.
- **Why:** the owner's decision (22 Oct): never delete a lead's pages. Until now a lead and its
  pages went after 400 days, and the setting was only in the config file, for the whole install.
- **Who:** sites that take leads. New installs keep the same defaults (400 days for leads, 30 for
  pages before a sign-up); nothing changes until someone sets it. **Do:** to keep leads for good,
  set it per site (above) and update the site's privacy notice with the new wording. A person's
  own request to be deleted still works: `skald forget --email ...` (or `--lead`, `--vid`).
- **The audit:** the second count still agrees over old days. The hook spool is kept as long as
  the leads, site by site, so a day older than 400 recounts the same; the beacon's day counts the
  audit keeps (`conversions-audit.json`) are kept as long as the leads too (they were cut to 400
  days), so beacon leads older than the beacon spool are still checked against the count made
  while it held them.
- **Checked:** tests/test_leads_kept_for_good.py (0 keeps rows, removed rows, linked pages,
  identities and the spool; a linked page older than `vid_days` stays and an unlinked one goes;
  each site by its own days; `forget` still deletes; the settings' checks, plan cap and CLI;
  the page's save, confirm and preview; the notice wording; the audit agrees over a 639-day-old
  lead after the prune, kept for good or not, and withholds it when the store is kept without
  its spool), tests/test_privacy_notice.py and tests/js/settings-privacy.mjs (the Leads card).

## 2.28.1 (2026-10-22)

### Fixed: a hook dropped the visitor ID when visitor IDs were switched on in Settings

- **What changed:** the hook receiver now reads the site's visitor-ID switch
  (`beacon.visitor_ids`) with the site's Settings rows applied, as the beacon and the daily run
  already did.
- **Why:** on 22 Oct an end-to-end test (three pages on a site, then a sign-up on its app
  subdomain) arrived with the right visitor ID, and its first-touch time was worked out from it,
  but the row was stored without the ID, so its visits were not linked to the sign-up. The switch
  had been turned on in Settings, not in the config file, and the receiver read only the file.
- **Who:** sites that turned visitor IDs on in Settings (or with `skald settings set`) and send
  leads by hook. **Do:** nothing. Leads sent before this release keep no visitor ID; a sender can
  send a later stage again with it.
- **Checked:** tests/test_conversions_hooks.py (a settings row turns the vid on for hooks; the
  test fails without the fix), and a live end-to-end run after the deploy.

## 2.28.0 (2026-10-22)

Leads' 7, 30 and 90 days include today so far, with the exact dates from and to.

### Changed: Leads' 7, 30 and 90 days include today

- **What changed:** on Leads & sales > Leads, 7 days are now today so far and the 6 whole days
  before it (30 and 90 the same way). The heading gives the dates from and to, with weekdays:
  "Last 7 days: Fri 16 Oct to Thu 22 Oct (today, so far)", the year only when the days cross a
  year. Today's leads are in the list, newest first, each with a small green live dot. The
  "Today so far" line is now part of the period, under the count ("Today so far: 2 of these 5
  leads"), with Show today (live) still going to today alone, and says in one sentence that the
  whole days are verified and today is live, checked again once whole. The change against the
  period before is like for like: the period before's whole days, then its last day only up to
  the time it is now ("25% more than Fri 9 Oct to Thu 15 Oct 14:00 EDT (4), the 7 days before to
  this hour"), never a part-day against a whole one. With a label or a source, country, device or
  campaign filter on, no change is shown, and the line says why. The CSV is named after the
  period's days (`leads-2026-10-16-to-2026-10-22.csv`). In the Timeline, today's bar is said to be
  so far, and pressing it opens Today (it opened yesterday's day before: a custom day stops at the
  last whole day). The empty state names its dates too.
- **Why:** the owner, 2026-10-22: on #sales/leads "if you are looking at 7 days it should also
  show today ... today is 1 + last 6 = 7 days", and "show clear dates from and to so it's not
  confusing". The list opened on the last 7 whole days, so a lead that came in today was only in
  the "Today so far" line.
- **New figure:** conversions.json `today.same_time` (conversions_leads.same_time): the day that
  ends each period before (today minus 7, 30, 90), counted from midnight to the file's time of
  day, by kind. Second count: `audit_conversions_leads.check_same_time`, one SQL GROUP BY between
  its own bounds; a difference withholds `today` as before. The period's days, today's included,
  are conversions.json's `days[]`, recounted by audit_conversions.py on every build.
- **Who:** everyone who opens Leads. Summary, Sources, Calendar bookings, Funnels and Events keep
  whole days up to yesterday: their figures sit beside visitors, rates and Compare with…, which
  take whole, verified days only, so a part-day would mix in. The Leads line names their dates. Yesterday, Today,
  All time and custom periods are unchanged everywhere. The URL keeps `range=7d` etc. as before.
- **Do:** nothing.
- **Checked:** tests/test_leads_today_period.py (the period's days with today's rows, the list
  newest first, the like-for-like count against the SQL recount, a tampered figure withheld),
  tests/js/leads-period.mjs (the heading words, the dates, the "Today so far" line, the live
  mark, the change and its filters, the URL, Summary unchanged), the full suite, and the demo
  (public/docs/screenshots/leads-list.png).

## 2.27.0 (2026-10-22)

Share the visitor ID across a site's subdomains from Skald's side (a per-site setting, off by
default), so a sign-up on app.example.com links to the visits on www.example.com without touching
the site's script tag; and the developer's set-up page draws properly again.

### Fixed: the developer's set-up page drew a page-sized icon

- **What changed:** the private set-up page (Share with your developer) now loads the stylesheet
  for the copy and open icons beside an address, and says when the link ends in words
  ("29 Oct 2026, 16:17 UTC"), not as a raw time stamp.
- **Why:** on 22 Oct the owner opened a hook's set-up page and saw a huge empty box with a dark
  shape across it: the address's icons (2.21) had no styles on that page, so the icon filled it.
- **Who:** anyone opening a developer link. **Do:** nothing.
- **Checked:** a test that every stylesheet the page needs is linked and served.

### New: share the visitor ID across subdomains from Skald, with the tag unchanged

- **What changed:** a new site setting, `beacon.share_subdomains` (admin, off by default;
  Settings > Sites > Script tag, or `skald settings set <site> beacon.share_subdomains true`),
  does what `data-share-subdomains="true"` on the script tag does: `www.` and `app.` share one
  anonymous visitor ID through the first-party cookie `skald_vid`. The beacon's answer to a page
  view from the site's own Origin now carries `X-Skald-Sh: 1` or `0` (exposed by CORS). Its
  status and body are unchanged (204 counted, 202 not, no body), so nginx's count and older
  scripts are untouched; no other answer and no other Origin gets it. `skald.js`, without the
  attribute, sends its first page view of a load by `fetch` (keepalive, no credentials, the same
  text/plain body) instead of `sendBeacon`, reads the header, writes the cookie at once on `1`,
  and keeps the answer a day in `localStorage` (`skald.sh`); a fresh answer decides at start
  with no ask. On `0` after a `1` it deletes the cookie it wrote. The attribute still wins. Do
  Not Track, GPC, `data-consent="required"` and visitor IDs off behave as before: no ID, no
  cookie, no ask. Settings > Integrations says when sharing is on in Skald, and the privacy
  notice's cookie line is then plain, without "[Keep this line only if...]". `skald.js` grows
  from 6,132 to 6,628 bytes (3,250 to 3,475 gzipped); the size test's budget is now 6.5 KB.
- **Why:** a client site's web developer cannot add `data-share-subdomains="true"` to the tag,
  and we have no access to that site, so its subdomains could not share the ID.
- **Who:** sites on several subdomains that want one journey across them. **Do:** nothing,
  unless you want it: an admin switches it on per site (visitor IDs must be on). Browsers pick it
  up within a day; switching it off stops the sharing within a day too.
- **Checked:** tests/test_share_subdomains.py (the setting and the CLI; the answer on and off,
  never for a foreign Origin, other answers and nginx's count unchanged; Integrations; the
  notice), tests/js/skald-snippet.mjs (first load asks then sets the cookie on `.example.com`, a
  fresh flag skips the ask, a stale one asks again, `0` clears, the attribute wins, an older
  Skald, a refusal, DNT/GPC/consent/IDs off), `node --check`, the full suite.

## Older versions

- 2.23.0 to 2.26.0 (22 October 2026): [docs/CHANGELOG-2.23-2.26.md](docs/CHANGELOG-2.23-2.26.md).
- 2.21.0 to 2.22.3 (21 and 22 October 2026): [docs/CHANGELOG-2.21-2.22.md](docs/CHANGELOG-2.21-2.22.md).
- 2.14.0 to 2.20.1 (18 to 21 October 2026): [docs/CHANGELOG-2.14-2.20.md](docs/CHANGELOG-2.14-2.20.md).
- 2.8.0 to 2.13.0 (18 October 2026): [docs/CHANGELOG-2.8-2.13.md](docs/CHANGELOG-2.8-2.13.md).
- 2.7.1 and earlier (8 to 12 October 2026): [docs/CHANGELOG-2.0-2.7.md](docs/CHANGELOG-2.0-2.7.md).
