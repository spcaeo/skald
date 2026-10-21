# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## 2.17.0 (2026-10-21)

Add a site now looks at the site itself, so you do not have to know how it is hosted.

### Added

- **Skald checks your site.** Type an address in Add a site (or open Send this site's visits) and
  Skald looks at it from outside, like a browser: the web server (nginx, Apache, LiteSpeed, Caddy,
  IIS), a platform in front (Cloudflare's proxy, Vercel, Netlify, CloudFront, Fastly, GitHub Pages;
  or a hosted builder such as Shopify, Wix, Squarespace or Webflow), the framework (Next.js,
  WordPress, Nuxt, Gatsby, Astro), both host names, and the page assets to count people by. It
  then suggests the way in, with the reason, and marks it "Recommended for <site>" on step 3.
  Every fact is a suggestion you can change; the host names and page assets are saved with the site.
  A hosted builder gets the script tag, with the reason: Skald cannot read its server log.
- **Safe by design:** the check reaches only public addresses on ports 80 and 443 (never a private,
  loopback, link-local or cloud-metadata address, checked again on every redirect, and connected to
  the address it checked), sends no cookies, reads at most 256 KB, is for admins only and
  rate-limited, and logs only the host and the outcome.
- **The site list** (`/traffic/`) shows the same footer line as every dashboard page: "Live ·
  v2.17.0 · released ...", in the sites' time zone (UTC when they differ), with the release and
  commit in its tooltip.

### Fixed

- Add a site, step 3, showed the word "null" when the site was reachable.

## 2.16.0 (2026-10-21)

Connecting a site, step by step: from the address to "Connected", with a test at the end and
plain-words fixes when something is wrong.

### Added

- **Settings > Connections** (was API & tokens). Three tasks, each a short guided dialog:
  - **Send this site's visits to Skald**: choose how (a Linux server with Docker, the same
    without Docker, Cloudflare, Vercel or Netlify, or only the script tag), make a sending token
    for this one site, follow the steps with the address and token filled in, and **Test
    connection**: "Waiting for the first lines", "Connected: 1,240 lines received, the last at
    10:42", or "Refused at 10:41: the token is not for this site" with the fix.
  - **Read your figures (API)**: a read token, a curl command filled in, and a Test.
  - **Connect an AI assistant (MCP)**: a token, the Claude Code command and Claude Desktop
    config, and a Test that lists the tools.
  - **Your tokens**: what each one is for, its sites, and Revoke. Sending tokens can now be made
    in the dashboard, not only on the server.
- **Install kit (.zip)** for the Docker and systemd shippers: `install.sh`, `uninstall.sh` (removes
  only what it made), `check.sh` (checks Docker, nginx, the log file, the way out to Skald, the
  token file and the shipper, one line each with the fix, and ends with a report to send, with no
  token or address in it) and a README. The token is never in the zip unless you tick the box.
- **Add a site, step by step**: your site, prove it is yours, how its visits reach Skald,
  install, test and finish. Progress is kept on the server: close it and continue later; the site
  picker shows "Setup: step 3 of 5, continue", and a site with no visits for 24 hours says so.
- **Share with your developer**: a private link to one task's steps for one site, filled in, with
  the kit and the Test. It ends after 7 days (1 or 30 if you choose) or when you revoke it; the
  token or secret it needs is made when the developer presses Show, and shown once.
- **Set up this site** on Overview: each open line is one plain sentence and a Set up button that
  opens its guided dialog (logs, the script tag, the lead hook, mail, privacy). The technical
  detail is folded under "For your server admin".
- **Help:** Connections, and Troubleshooting connections (the common problems and their fixes).

### Fixed

- `skald-ship` warned that a token file at mode 640 was "readable by others", the very mode its
  message recommends. It warns now only when the file is open to everyone or writable by others.
- The install steps named `www.<site>` even for a site without www.

## 2.15.0 (2026-10-20)

Two privacy controls, from a community question: "does it also track visitors who don't accept the
cookie consent?" Yes: the log has every request. Now you can choose to keep less of it.

### Added

- **Shortened IP addresses.** Settings > Data retention > People > Keep visitors' IP addresses is
  now a choice of three: **Full address**, **Shortened (last part removed)** and **Don't keep**
  (`privacy.keep_ips: full | short | off`; `SKALD_KEEP_IPS=short` with Docker; the old true/false
  still work). Shortened keeps 203.0.113.57 as 203.0.113.0, and an IPv6 address's first 48 bits.
  Country and city are looked up from the full address first; bots, internal traffic and every total
  read the raw log as before. Switching from full to shortened shortens the visits already kept at
  the next nightly run. A person search by a full address finds its shortened visits and says one
  shortened address can be several people; the visitor drawer says the link is weaker.
- **Counted twice:** the second count of kept visits shortens with its own code and checks that no
  kept address is full and that each shortened address holds exactly the visits of the addresses
  that shorten to it.
- **Wording for your privacy notice.** A card on Settings > Data retention with a short text to paste
  into your privacy page, made from the same settings that decide what is kept (IP addresses, how
  long, leads' names and emails, the script tag, visitor IDs, Do Not Track and GPC), with a Copy
  button. What Skald cannot know is left in [square brackets]. A starting point, not legal advice.
- **FAQ:** does Skald count visitors who decline or ignore the cookie banner? (README, Help, the site).

### Fixed

- A flaky AI-answers test: it changed the first stored answer, which, with the assistants asked at
  once, was sometimes one that never named the site.

## 2.14.1 (2026-10-18)

### Fixed

- **Crawl health** fits at 1280 px: "Kind" and "Fetches per page" start hidden ("Columns" shows
  them; the address keeps the choice). Tables can mark a column hidden by default.
- **Leads won or lost later:** the rule is now written down and tested. A lead counts once, on the
  day it was completed or paid; a later won or lost is shown apart and adds or takes away nothing.
  A won or lost with no completed row is not a lead. Same on Overview, mails, client reports and
  Leads & sales.
- **Audit:** first touch says "not checkable (inputs expired)" when visitor-ID page views older
  than 30 days were pruned after the day was counted, instead of reporting a mismatch.

## 2.14.0 (2026-10-18)

What ChatGPT, Perplexity, Gemini and Claude answer when asked the questions your customers ask,
joined with what only your server log shows: what the assistant then read, and who it sent.

### Added

- **AI answers** (AI & bots › AI answers). What ChatGPT, Perplexity, Gemini and Claude answer to
  the questions your customers ask, per **tracking profile**: a place (city, region, country) and
  a language, asked daily, weekly or monthly with 1 to 5 tries a question. For each run and
  assistant: whether the answer **names** you, the **pages** of yours it cites and where the
  first one sits, and the **competitors** it names. The page shows how often each assistant
  names you run by run, every profile × assistant for one question as "x of N tries", the
  questions with a line from an answer and the full answer, and the competitors.
- **From an answer to a lead.** For one assistant and one cited page over 30 days, four counts
  side by side, each from its own road: answers that **cited** it, that assistant's fetcher
  **reading** it in your log, the visitors it **sent** there, and the **leads** whose first
  visit came from an AI answer and landed on it. Joined by page and day, never added together.
- **Tracking profiles** in Settings › AI answers: the site's questions (at most 50), brand terms
  and competitors, or a profile's own; at most 10 profiles a site; duplicate, pause, resume,
  Run now and delete. Nothing is erased: an edit is a new version that later runs ask with, and
  a deleted profile's results stay.
- **Cost estimate and daily cap.** Before anything runs, each profile shows its cost (questions
  × tries × assistants × a price an answer, by month); a run that would pass the profile's daily
  cap in US dollars stops there and goes on the next day. The prices are rough defaults, set in
  config.yml to match your contract.
- **Your own API keys.** Each assistant needs its provider's API key (OpenAI, Perplexity, Google
  Gemini, Anthropic), set write-only by an install admin in Settings › Integrations or in the
  environment (`SKALD_OPENAI_API_KEY`, `SKALD_PERPLEXITY_API_KEY`, `SKALD_GEMINI_API_KEY`,
  `SKALD_ANTHROPIC_API_KEY`). Nothing is asked, and nothing costs, until a key and a profile
  exist. Only the questions and the profile's place and language are sent; nothing about your
  visitors.
- **A sample, labelled so.** These are a sample of API answers, not what every user sees: each
  provider answers people differently by account, history, place and wording, and its API can
  differ from its app. The page says so above every figure, and every answer is kept to read.
- **Counted twice.** Every answer's reading and every run's figures are recounted from the
  stored text and links by a second, separate count (`audit_ai_answers.py`); a run where the
  two disagree is withheld, listed with no figures.
- The demo has made-up AI answers, asked through the same code with a stand-in for the
  providers.

### Fixed

- A table's column filter and Real time's map legend no longer show the word "null" where a
  button or legend line was left out.

### Upgrading

- Docker: nothing by hand. The scheduler asks the due profiles every
  `SKALD_AI_ANSWERS_MINUTES` (15; `0` stops it). Outside Docker, add
  `*/15 * * * * ... ti.py ai-answers --due` to cron, and add `ai-answers` to the helper paths
  in your nginx site (DEPLOY.md shows the line). Set up: docs/AI-ANSWERS.md.

## 2.13.0 (2026-10-18)

A new Overview for today and a new Traffic › Visitors; where a visitor first came from, and
their city; Google's and Bing's own search figures; client reports, retention and crawl health;
advanced filters and one toolkit for every table.

### Added

- **Overview, today, live.** With Today · Live on, Overview › Summary is one live page: visitors
  now and arrivals in the last 5 minutes minute by minute (one Pause), the four tiles (Visitors,
  Pages, Leads, AI) against **yesterday at this hour** with both days' running totals, the map
  with country chips, the pages being read beside the newest visits, sources and a two-page flow,
  what converted, AI & bots; each card links to its full tab. Yesterday-by-now is a new figure
  with its own second count (`audit --live` recounts both days hour by hour, leads by SQL); a
  withheld, partial or unrecorded yesterday says "not recorded", never 0.
- **Traffic › Visitors, rebuilt.** The visitor flow first; each visit with its country (flag and
  code), city, device with browser and system, source with "First came from …", new or
  returning, pages, time on site and the pages in order; a **New and returning visitors** card
  and a **How engaged visits were** card whose figures must add up to each day's visitors, or
  the card is withheld.
- **Where a returning visitor first came from (first touch).** Each visit carries its
  visitor's first visit Skald knows of, linked by the script tag's visitor ID, else the kept
  address with the same browser, else the 30-day code; none found says "first visit we know
  of", never a guess. Shown under the visit's source, in Real time's newest visits, and on
  Traffic › Sources as "Where returning visitors first came from", counted twice (a new day kind
  `first_touch`, recounted by `audit_firsttouch.py`).
- **One visitor drawer, with an animated journey.** Every visit and visitor (the visit list,
  Real time, Find a person, Leads & sales, funnels, the flow) opens the same drawer: "Visitor
  from Toronto", visits over days, first came from, the outcome, and each visit as a timeline
  with the time between pages and "12 days later" between visits; **Replay** plays them again
  at their real pace (still with reduced motion). Admins and owners, audit-logged.
- **Cities.** `logs.city_db` (Docker `SKALD_CITY_DB`) names a city file such as DB-IP's free
  "IP to City Lite"; each visit gets its city, Places & devices gets a **Cities** table, and
  the real-time map a pulsing dot per active city. People only; a city in another country than
  the line's own is not used. Counted twice (`audit_cities.py`). `tools/update-dbip-city.sh`
  fetches the monthly file.
- **Client reports.** Settings › Reports: branded reports an agency sends its clients, as a mail
  with a PDF attached, weekly on a weekday, monthly on a day or every few days, at a time in the
  site's zone; last week, last month or month to date; the sections you pick, your notes and a
  footer; the agency's name, colour and logo. Recipients confirm first. Figures are verified
  days only: a withheld or missing day is listed and never counted, and the sums are counted a
  second time before a report goes. Preview, Download PDF, Send now and a history of every send;
  a failed send is tried once more. The PDF is made without a browser. With Search Console
  connected, a Search Console section gives the period's clicks, impressions, CTR, position and
  top queries and pages, final days only; provisional days are listed, not counted.
- **Search queries, impressions and position, synced from Google and Bing.** A new Traffic ›
  Search tab: queries, pages, countries, devices and search appearance with clicks,
  impressions, CTR and position over 7 days, 28 days, 3 or 16 months, and a trend. Synced from
  the Search Console and Bing Webmaster Tools APIs every 6 hours; the newest days are marked
  provisional and fetched again until Google calls them final. Connected from the dashboard
  (Settings › Integrations › Search): upload a service-account key once, add its robot email to
  each site's Search Console (a ready text to send to a client), find the property, test,
  connect, with an optional 3 or 16 month backfill. "Sync now", the last sync and the next, and
  errors in plain words with one mail per run of failures. Also `skald search-console sync`,
  `skald bing sync`, `skald search sync`.
- **Search Console beside Skald's own visits.** A cross-check panel puts Google's clicks beside
  Skald's visits from Google search, by day and landing page, says why they differ, and flags a
  sharp change in the ratio. Never forced to match. The synced figures are checked by a second
  road (every table re-added, one day asked of Google again); Skald's own side is counted twice.
- **Retention cohorts.** Traffic › Retention: of the visitors first seen in a week (or on a day),
  how many came back in each of the 8 weeks (14 days) after, or came back and read 2 or more
  pages; split by first source type, country, device or landing page, with a curve and the
  visitors behind a cell (admins). Counted from what is kept, never past it ("not recorded"),
  and checked again by `audit_retention.py`; a cohort that does not match is withheld.
- **Crawl health.** AI & bots › Crawl health: your sitemap (read once a day) beside what Google,
  Bing and each AI crawler fetch: coverage per crawler, sitemap pages never fetched, pages
  fetched that the sitemap does not list, and 404/410, 5xx, redirect, slow and large answers,
  over 7 or 30 days and today. Counted twice (`audit_crawl_health.py`).
- **Advanced filters and saved views.** The Filters button builds rules over every field a visit
  carries (country, city, source, referring site, campaign, AI assistant, first came from,
  landing page, a page read, pages read, time on site, sent a form, device, browser, system, new
  or returning, crawler) with is, is not, contains, starts with, at least, at most; All or Any,
  and groups. A live count of matching visits, and of each rule alone. A value not recorded
  never matches by chance. Applied in full to single visits (Visitors, Funnels, Requests); other
  tabs grey a rule they cannot apply and say where it does apply. Saved views can be renamed and
  copied as a link (the reader still signs in).
- **One toolkit for every table.** Sort any column (one way, the other, the table's own order;
  not recorded always last), filter columns (contains, a range, pick values), choose columns,
  and **Export what you see** (the matching rows, in their order, with the columns shown). All
  kept in the address.
- **Search the dashboard.** The magnifier (Ctrl K, Cmd K) finds pages, countries, sources,
  referring sites, campaigns, AI assistants and crawlers seen in the period and opens each on
  its tab with its detail; tabs, settings, guides and saved views too.
- **Set up this site.** A first-run checklist on a new site's Overview for owners and admins
  (logs, page assets, countries, script tag, lead hook, mail recipient, privacy), read from the
  doctor's own checks; hidden per site.
- **Mail preview.** Settings › Mail shows the daily or weekly mail as it would be sent, never
  sending it.
- **Alert switches.** Admins switch alerts, their mail and each rule on or off per site on
  Site › Alerts; a key locked in the config stays the config's and says why.

### Changed

- **Visitors' cards follow the filters when that is honest.** With a filter on, New and
  returning visitors and How engaged visits were count only the visits the filters keep, rebuilt
  from the kept visits and only when every day's kept visits are exactly that day's own figures
  ("Filtered: N of M visits"); past the 7 kept days, or when a day does not match, they show
  every visit and say why. The engagement tables by source and device stay whole-site.
- **Every row opens its detail,** the whole row, by click, Enter or Space; the drill panel has
  **Go to** links (its visits, its flow, a page's sources and story, Visitors filtered to it).
  Closing it keeps the browser's Back for the tab you came from.
- **Insights** shows the five biggest first (by how much moved and what it is worth), one card
  per subject, one sentence, one number, one link; **Show all** lists the rest.
- **Countries are a flag and a three-letter code** everywhere ("🇨🇦 CAN"); the full name is in
  the tooltip, found by search, and kept with a Code column in the CSV.
- **Dates in one form, in the site's time zone** by default: "3 h ago (18 Oct 13:43 EDT)".
- **Counts that agree.** Places that show the same figure now say the same number and which
  count it is; a tab with its own period shows a fixed **Period** chip instead of a picker it
  ignores; a filter a tab cannot apply shows a banner; something the site never sent (an event,
  a kind of lead, a heartbeat, page speed) says **Not set up**, never 0 or 0%.
- **Too fast to be a person.** A browser-like visit with 6 or more page views all within 2
  seconds of its first now counts as a bot, whole, so the groups still add up
  (`site.too_fast_pages`, `site.too_fast_seconds`; its own audit road).
- **A visit's pages are said in full:** "3 pages (2 seen in the browser)" when the script tag
  saw steps the log did not.
- **Site › Requests** calls the script tag's posts "script tag event" and Skald's own hooks
  "Skald endpoint", never "form post".
- **Plain words and contrast:** one name per thing, headings that match the tabs, darker light
  greys, tables that scroll sideways on a phone keep their first column, tooltips stay on
  screen, each chart is one Tab stop.
- **GeoIP files are mapped read-only** instead of copied into memory, so the 120 MB city file
  is shared by every process.
- History schema 14 (search days) and conversions schema 6 (a visit's city, a page view's
  referring host), applied by the normal upgrade on first open.

### Fixed

- **Line order.** nginx writes a line when its request ends, so a slow request can sit after a
  faster, later one. Both counting roads now read a window's lines in time order (ties in file
  order); before, such a visit could get the wrong landing page or steps, and the audit withheld
  the day.
- **The audit and expired inputs.** A day audited after its 30-day visitor hashes were pruned
  says "not checkable (inputs expired)" for those figures instead of failing.
- **Today's returning visitors** showed "–": the live snapshot's figure was dropped.
- **The visitor flow** wrote the word "null" under the map.
- **"Direct or unknown"** no longer shows in grids, People, the flow map or the visit filters.
- **One "Leads" everywhere.** The daily and weekly mails and client reports counted the lead
  database (no demos) while Overview's Leads tile counts completed forms and demo bookings: the
  same week read 24 in the mail and 32 on the page. Both now count the tile's way, recounted by
  a second road before a report goes; a period before conversions were recorded is not summed.
- **Client reports and mails in the app's words:** "Direct", three-letter country codes,
  cities as "London, England, GBR", assistants by name (ChatGPT, not chatgpt.com).
- **Saving a report** says whether a confirm link went out, or that none could because no mail
  server is set up (no one's one-link-a-day is used up).
- **Visitors with filters on:** Where visits ended and Common next steps follow the filters too
  (when the kept visits give back each day's own lists); tables that cannot say so; the filter
  banner says what narrows.
- **The drill panel's visits follow the period** (they always showed the whole 7 kept days); a
  city's panel has the same Go to links as a country's.
- **Crawl health's panel counts the tab's own window** (7 or 30 days and today), as its row does.
- **The person drawer** found by email or lead named the lead as its outcome (it said "No lead
  linked" above it) and shows no empty journey, visit table or Replay.
- **Column filters match what a cell shows:** "USA" no longer finds AUS through the hidden full
  name. The Export button counts the CSV's columns; the Sources CSV writes Change as a fraction,
  like Share.
- **Layout:** phone tables no longer make the page scroll sideways; data grids show only the
  sorted column's mark (▼ biggest first); Real time has no empty gaps; Site › Health's figures
  line up; Settings › Integrations' fix line wraps and shows commands as code; the palette uses
  a code font for paths only; the Pages leaderboard dates its fold in words; Crawler rules shows
  a counted 0 as 0.
- **Events and Pipeline** say why their "started" counts differ (the script tag keeps one start
  per browser and action per 30 minutes); Funnels says when its lead steps cover other days.

### Upgrading

- Nothing by hand. The new helper routes sit under paths nginx already passes on. For cities,
  mount a city file and set `SKALD_CITY_DB` (docs/INSTALL.md); for search figures, connect
  Search Console and Bing in Settings › Integrations › Search.

## 2.12.0 (2026-10-18)

### Added

- **Visitor flow.** A flow map of how visits moved: where they came from, the pages they read in
  order, and when they left. On Traffic › Visitors, in every drill-down ("How these visitors
  moved", e.g. one country), and in Funnels ("Flow between the steps"). Hover for figures, click a
  page to open it, or switch to the table. Drawn from the same kept visits as the visit tables;
  each column adds up to the visits, and a map that does not add up is not shown.
- **Pause, edit and delete internal traffic.** Each entry in Settings › Internal traffic has an
  Active / Paused switch, Edit and Delete; also `skald ours list|pause|resume|edit|delete`.
  Nothing is erased: a pause, an edit or a delete is recorded with its time, so a past day
  recounted later gives the same figures, on both counting roads.
- **Active now pings on the live map:** two rings and a soft blink on each country with visitors
  active now (a still halo with reduced motion).

## 2.11.1 (2026-10-18)

### Fixed

- **The live check on a busy site with shipped logs.** The live run and `audit --live` read the
  log at different moments; lines shipped in between (stamped before the snapshot's end) made
  the recount differ by a request or a visitor. The live run now records how far it read each
  log file (`read_upto` in the snapshot, the requests feed and the real-time tail) and every
  live reader, the audit's own included, stops there. Older snapshots audit as before.

## 2.11.0 (2026-10-18)

Who is on the site now, on a live world map; alerts for AI citations and crawlers, also sent to
Slack or any webhook; no "unknown" anywhere.

### Added

- **Real time** (Overview › Real time, and the first block of Overview › Summary with
  Today · Live on). Visitors active now (last 5 minutes) and in the last 30 minutes, visitors on
  the site minute by minute, from the live run's count every 2 minutes with the same people rules
  as every other figure. Requests per minute, read from the end of the log every 15 seconds
  through the helper (`api/realtime`), always labelled requests, never people. The page asks for
  fresh figures every 15 seconds while it is open; Pause holds it.
- **A world map of who is on the site.** Countries shaded by visits today, a bubble for each
  country with visitors in the last 30 minutes; point at one, or Tab to it, for its figures, and
  click or Enter for its detail. A countries table beside it to search, sort and download. The
  outlines are Natural Earth's (public domain), drawn in the page: no map service is asked for
  anything. Beside it: pages being read, sources and devices now, AI assistants and crawlers now
  (in requests), and the newest visits (no address, no browser string).
- **Every Real time figure counted twice.** `audit --live` recounts the snapshot's real-time part
  and the helper's last 15-second count from the raw lines (`audit_realtime.py`). If today's
  figures disagree, Real time shows no visitor figures until they match.
- **AI alerts.** The first visit ever from an assistant's answer; a page's first visit from an AI
  answer (more than 5 in a day make one alert); visits from AI answers against the median of the
  same weekday over the 6 weeks before (at least 2 times the usual and 10 visits, or at most half
  of a usual of at least 10; fewer is "too few to judge"); an AI or search crawler that came
  often and has been silent for 7 days. Each alert states its rule and figures in plain words, in
  visits (people) or requests (crawlers), never both. Whole, checked days only: a withheld,
  partial or missing day makes it wait. The first-citation alerts start once 28 days are kept.
  Each alert's figures are recounted by the daily run (`audit_alerts.py`).
- **Alerts in Slack or any tool.** Every new alert is the outgoing webhook event `alert.opened`
  (site, alert, text, figures with their unit, time), opt-in per site on Settings › Integrations,
  signed with the webhook's own secret. A Slack incoming-webhook address (`hooks.slack.com`) gets
  Slack's own `{"text"}` shape.

### Changed

- **No "unknown" shown anywhere.** A visit with no referrer and no campaign tag reads "Direct"
  (with a note saying so), and a value the log did not have reads "Not recorded", in the
  dashboard, mails, CSV and JSON exports, MCP answers, help and docs. Only the words shown
  change: the stored names stay, so earlier days do not split, and filters and links keep
  working.
- **Grids and tables line up.** Every cell sits at the top of its row; text on the left,
  numbers and dates on the right, badges and yes/no in the middle; each header follows its column.

### Upgrading

- Docker: nothing extra. An nginx you run yourself needs `api/realtime` in the helper's
  per-site route for the 15-second request count (docs/UPGRADING.md); without it Real time
  shows requests from the 2-minute count and says so.

## 2.10.1 (2026-10-18)

### Changed

- **More bots recognised, no person lost.** Checked against Crawler-Detect's test files (3,713
  crawler and 165,640 device user agents): `Claude-Web`, Google's AI agents (`Google-Agent`,
  NotebookLM), Amazon's AI user fetcher, Seznam, Naver, Coc Coc, Qwant, Mojeek and about 45
  monitors, testers and scanners added. Sogou's phone browser and phones named "... bot" stay
  people. The check is a dev-time tool (`tools/check-bot-names.py`); nothing is synced at runtime.

- **Today is the default period.** The dashboard opens on Today, live, on every page. Old links
  that name a period keep it.

### Fixed

- **"Form sent" on every visit.** The script tag posts its events to `/traffic-beacon`; when the
  site's log kept those requests, every visit with the tag counted as having sent a form. A POST
  to Skald's own endpoints (`/traffic-beacon`, `/traffic-js/`, `/traffic-hooks/`,
  `/traffic-ingest/`) is no form post, on both counting roads.
- **Returning readers with everything cached.** A browser that already had a site's styles and
  scripts cached asked for none, so it passed the render test only if the script tag's page
  opening was kept. That page opening (`page_view`) was dropped unless beacon-only mode or
  visitor IDs were on, so a real returning reader could be missing. Now the page opening is kept,
  apart from the events (`opens-<day>.jsonl` beside the spool: path and time only, no address,
  no agent), as proof that the page was drawn. Both counting roads read it. It is not counted
  as an event and changes no event figure.

## 2.10.0 (2026-10-18)

What AI assistants and crawlers read, ask for and cost, Google's AI Mode told apart, and client
sites set up from the dashboard or the shell.

### Added

- **What each crawler costs** (day kind `crawler_cost`). Per assistant, search crawler and bot, per
  day: requests, bytes sent (the log's size field; not recorded when no line had one), mean and
  90th-percentile response time (when the log has a time), status classes and error share,
  distinct paths and re-crawls (fetches per distinct path). Tables "What each crawler costs" on
  AI & bots > Crawlers and "What each assistant costs" on Assistants; a range shows the mean, the
  p90 for one day only. Each group keeps its 50 busiest names, the rest folded into
  "(all others)". Recounted from the raw lines by its own audit (`audit_crawler_cost.py`), with its
  own size and time readers. Kept 180 days in `crawler_cost.json`, with lists for the last 30.
- **A detail view per crawler.** Open a crawler or bot for its cost, requests by day, pages, status
  mix, verified share, countries, user agents and last seen. User-agent strings are kept only for
  named crawlers, never for probes, link previews or anything that may be a person's browser.
- **What AI fetches ask for** (day kind `ai_formats`). Every AI fetch, for training or for a live
  question, filed by what its path names: Page, llms.txt, Markdown, Text, robots.txt, Sitemap,
  Other file. "What they fetch" on AI & bots > Assistants and Crawlers. Recounted by
  `audit_ai_formats.py`, which has its own path rule. A range with a day counted before 2.10.0 shows
  no table rather than a partial one.
- **What the AI read before it sent this visitor** (day kind `ai_read`). For a visit from an AI
  answer (cited, or likely), the pages that same assistant's user fetcher fetched in the minutes
  before: at most 10, nearest first. The visit drawer lists them; AI & bots > Assistants has a
  table per assistant: visits from its answers, how many it had read pages for first, and how many
  landed on one of those pages. Likely visits are kept apart. Context, never a count of people.
  Recounted by `audit_ai_likely.py`.
- **Google AI Mode.** A Google search referrer with `udm=50` (on the referrer or the landing
  address) stays a Search engine visit, with the referring site `google.com (AI Mode)`. Only when
  the parameter is there, never guessed. Both counting roads.
- **Page assets per site.** `site.asset_prefixes` and `site.require_rendering` are site settings
  (Settings > Sites > Page assets), read by both counting roads and by `doctor`. A WordPress or
  other client site can name its own asset folders, so its readers are counted as people.
- **Visitor IDs switch** in Settings > Sites > Script tag (`beacon.visitor_ids`, per site, off by
  default). Settings > Integrations shows the site's own value.
- **Settings and sites from the shell:** `skald settings list-keys`, `settings get SITE [KEY]`,
  `settings set SITE KEY VALUE` (checked and audit-logged like the page; secrets and locked keys
  refused; a shorter retention window needs `--yes`); `skald site hosts NAME HOST...` and
  `skald site remove NAME --yes`.

### Changed

- `skald site purge` also deletes the site's logo folder, and lists every folder it deleted.
- The Add-a-site panel's tag loads `/traffic-js/skald.js`, the path the tag is served from.
- `skald token --help` names the `ingest` scope.

## 2.9.0 (2026-10-18)

The script tag for every site of an install, and Google Ads clicks from iOS read as paid.

### Added

- **The script tag works for every site, not only the first.** The beacon helper sends each
  `POST /traffic-beacon` to the site its `Origin` names, into that site's own spool: the first
  site's stays `<history folder>/beacon`, another site's is `sites/<name>/beacon`, where its daily
  run already reads. A site added from the dashboard (or in a `sites:` file) accepts
  `https://<each of its hosts>` as origins, but only while the install has the script tag on
  (the first site has an origin: `beacon.origins`, `SKALD_BEACON_ORIGINS`). The first site keeps
  its own list. Sites and their settings are read again every 60 seconds.
- **Visitor IDs per site:** `beacon.visitor_ids` is a site setting (admin, off by default).
  `/traffic-js/skald.js` is served with the setting of the site whose page loads it (by
  `Referer`; the first site when there is none), with `Vary: Referer`. Turn it on only when that
  site's privacy notice says so; a consent banner should gate the tag.
- **Each site's beacons counted apart in the audit.** The helper names the site in a response
  header, `X-Skald-Site`, and nginx's beacon log writes it as a third field:
  `log_format skald_beacon '$time_iso8601 $status $upstream_http_x_skald_site';`. The event audit
  compares each site's 204s with its own spool. A line without the field (before 2.9.0) is the
  first site's. The Docker image has the new line; **an nginx you run yourself needs it**
  (docs/UPGRADING.md).
- A site can pass the tag through its own server (Caddy or nginx on the site's domain, forwarding
  `/traffic-js/` and `/traffic-beacon` to the Skald server), so the tag and the beacon stay on the
  site's own origin. The Skald server's nginx must trust that server's address for
  `X-Forwarded-For` (`set_real_ip_from`; Docker: `SKALD_TRUSTED_PROXIES`), so the rate limit and
  the own-traffic check see the visitor's address. It is never stored.

### Fixed

- **Google Ads clicks from iOS mark a lead paid.** `gbraid` and `wbraid` count like `gclid`: the
  touch is paid and reads as a Search engine visit, on both counting roads. Lead hooks and the
  lead database keep them on the touch.

## 2.8.1 (2026-10-18)

### Fixed

- **API calls are not pages:** a GET under `/api/` (a site's JSON API, called by the page's script)
  was counted as a page view, so it showed up as where visits ended and as a step between pages.
  Everything under `/api/` is now an endpoint, like the analytics beacon: evidence of a visit,
  never a page of its own. Both counting roads.
- The countries table says where countries come from: the log's own field, or the GeoIP file.

## 2.8.0 (2026-10-18)

Countries for logs that carry none, and counting fixes for Caddy logs, dashboard-made sites and
traffic sources.

### Added

- **Countries from a GeoIP file:** `logs.country_db` (Docker: `SKALD_COUNTRY_DB`) names a
  MaxMind-format `.mmdb` file; DB-IP's free country file works. A log line with no country of its
  own (Caddy JSON, a plain combined log) gets its address's country. The line's own country
  (nginx `cc=`, Cloudflare's `CF-IPCountry`) always wins. Both counting roads look it up. The same
  file serves lead hooks and the beacon (`conversions.country_db` still works). With DB-IP's file,
  "IP Geolocation by DB-IP" is shown beside the countries unless `report.country_credit` is set.

### Fixed

- **Caddy logs failed the daily run:** the audit refused Caddy JSON, so every Caddy site's run
  stopped at `audit` and its days were not stored. Caddy's `client_ip` is now taken before
  `remote_ip`, `host:port` becomes `host`, and a record with no address, URI or three-digit status
  is not counted as a request (on both roads).
- **Sites added from the dashboard inherited the first site's `site:` section** (asset prefixes,
  rendering rule, legacy paths). A static first site's asset prefixes made Next.js sites wait for
  the wrong files, so returning readers were not counted as people (30-60% too few, seen live).
- A combined log line's trailing quoted `"$host"`, and `$request_time` right after the user agent,
  are read. A quoted address list or `"-"` is not a host.
- **A 304 (cached copy shown) is a page view;** a cached landing page keeps the visit's source.
- **Sources:** AI assistants' phone-app referrers (`android-app://com.openai.chatgpt` and others)
  count as citations. Google's Android apps other than Search and Gmail are no longer "Search
  engine" (YouTube, WhatsApp, Telegram are Social media). `utm_source` decides the source type
  before `utm_medium` (`linkedin` + `cpc` is Social media). Click ids `gbraid`, `wbraid` (Google
  Ads on iOS), `ttclid` (TikTok) and `twclid` (X) are recognised.
- Skald's own robots.txt check (`site-version-check/1`) is counted as our own traffic, not a bot.
- The "no countries" message names `logs.country_db`.

## 2.7.1 (2026-10-12)

### Added

- **Links to Skald on GitHub** in every install: "★ Star Skald on GitHub", Source code, Releases and "Report a problem" on About; "★ GitHub" in the footer; "★ Skald on GitHub" in the account menu.

## 2.7.0 (2026-10-12)

A simpler dashboard: five sections with tabs instead of eighteen pages, Live and Compare as
switches on every page, and one place for each answer. No figure changed.

### Changed

- **Five sections with tabs:** Overview (Summary, Insights) · Traffic (Visitors, Sources, Pages,
  Places & devices, Time) · Leads & sales (Pipeline, Bookings, Funnels, Events, People) · AI &
  bots (Assistants, Crawlers, Crawler rules, llms.txt) · Site (Health, Requests, Not found,
  Speed, Alerts, Data quality). Settings, Help and About sit in the menu's foot. Every old
  address, bookmark and link redirects to its new tab.
- **"Today · Live" and "Compare with…" in the top bar,** on every section: Live shows today and
  refreshes; Compare puts the previous period, the same period last year or any period beside
  this one (A · B · ±). The separate Live and Compare pages are gone.
- **One place for each answer:** landing pages were listed in five places, now one; sources in
  six, now one grid; countries in two, now one. Elsewhere a short link points to it.
- **Leads & sales options:** count from the lead database (default) or the booking and payment
  tools (never added together), then source, action, stage, show left-out (spam, duplicates,
  test, cancelled, removed) and period, in one row.
- **Data Grids** (from spcaeo/ui, MIT) for long lists (sources, pages, countries, requests, not
  found, people, AI lists): search, filters, sort and page live in the address, so a view can be
  shared or bookmarked. **Folder Tabs** from the same library for tab strips. Both themed with
  Skald's colours; every colour pair checked for contrast in light and dark.
- The Overview tiles sit evenly (4 + 3); Site > Health shows the uptime outages that used to sit
  in Settings.
- Compare with… also works on Traffic > Sources, Pages and Places & devices (B and ± beside each
  row), and the lead tiles follow it (last year or any period, not only the previous one).

## 2.6.1 (2026-10-12)

### Fixed

- **The site switcher was cut off** on the right with two or more sites (the check mark and "N today" hidden at the menu's edge). Long names now end with "…". A browser check opens the switcher with two sites.

## 2.6.0 (2026-10-12)

Each site's own logo, everywhere you pick or switch a site.

### Added

- **Site logos** on the site picker, in the menu, the site switcher and the browser tab (the
  site's icon with a small Skald badge). Taken from the site itself (its app icon, then its
  favicon; only from the site's own hosts, never an outside icon service; checked weekly),
  uploaded (PNG, ICO or a safe SVG, square, 64 px or more; admins and owners), or a letter on a
  colour, which is also the fallback. Settings > Sites > Logo; `ti.py logo --check`.
- **Choose a site** after sign-in: a card per site with its logo, a Live dot and today's
  visitors, leads and demos booked.

### Fixed

- The site switcher never loaded the list of sites, so a second site never appeared in it.
- **Nothing pruned the conversions file.** Conversions past `conversions.retention_days`, journeys past `journeys.vid_days`, delivery rows past 90 days and old spool files stayed for good; `conversions prune` ran only by hand. The daily run now prunes them.

## 2.5.2 (2026-10-12)

### Fixed

- **A lead marked spam in the CMS without a new `updated_at` kept counting until the next
  daily run**, so the second count (which reads the lead database as it is now) disagreed and
  the day's lead figures were withheld. The sync every two minutes now also re-reads the leads
  created in the last 48 hours, so a status change is caught at once and the removed row is
  kept in the removed list.
- A tile's sentence ("withheld: the second count disagrees") wraps instead of being cut off.

## 2.5.1 (2026-10-12)

### Fixed

- **Lead tiles showed "-" when the count was 0.** When the lead database held only spam or
  duplicates, every day read as "not recorded". Days from the lead database's first lead on now
  count as recorded and show 0; the audit recounts that first day by its own SQL, and if it
  disagrees every day is withheld (never shown as 0).
- **Live showed the date range** with "30 days" picked. Live is always today; the range is
  hidden there and kept for the other pages.
- **The top bar overlapped** on pages with a long title at 1280-1680 px. When the bar is full,
  the group name and the Refresh label go first, then the range and filters move to a second
  row. The period highlight now sits exactly on its button. A browser check covers every page
  at five widths in both themes.
- Small: a halo behind lead counts on the Overview chart, padding under sparklines, only the
  known parts of a campaign on Live, "-" for the rate of a not-recorded row, and the doctor's
  weekly-mail line.

## 2.5.0 (2026-10-12)

Leads and demo bookings on every page where they help, each counted twice.

### Added

- **Overview:** Leads and Demos booked tiles, with the change only when both periods are whole
  and checked, and each day's leads as dots on the main chart.
- **Live:** today's leads and bookings as they arrive (time, action, stage, source, landing
  page, country), with today's totals. Test rows say "test, not counted".
- **Sources, Pages, Locations:** a Leads column and a lead rate (leads per visitor, from 10
  visitors up). Sources use the last touch; Pages the landing page recorded with the lead.
- **Insights:** lead findings, week on week and 30 days on 30, by source, page and country.
- **Compare:** leads, demos booked and all completed, in total, by source and by landing page,
  in full-width tables (A · B · ± under each group; long labels on one line).
- **MCP:** the `conversions` tool takes `by` (source, page, country) and gives lead totals.
- A new audit (`audit_conversions_leads.py`) recounts today's list and every lead finding; a
  list it disagrees with is withheld, a finding left out and named.

### Changed

- `skald doctor` names the step a daily run stopped at and why. A weekly mail held back by a
  partial day says the day itself is fine and that it clears by itself next week.

## 2.4.1 (2026-10-12)

### Fixed

- **A lead's visitor ID reached viewers.** The Leads > "Left out" list sent the lead
  database's session ID as a visitor ID to every member. Now only admins and owners get it, and
  only where the site has visitor IDs on (`beacon.visitor_ids`); a site's session column is no
  visitor otherwise.
- **The top bar overflowed below 1600 px for admins.** The person search box squeezed the
  period and the buttons. Below 1600 px it is now an icon button that opens the same search.

## 2.4.0 (2026-10-12)

Find any person by IP, email or lead and follow them across days; nothing left out is hidden;
and setup that checks itself.

### Added

- **Person search.** One box in the top bar (and Ctrl K) for an IP, an email, a lead or a
  visitor ID, for admins and owners. It opens every visit across the kept days (source,
  referrer, landing, pages in order, country, device), the last 6 hours of requests, and every
  lead and conversion, linked. A lead is tied to a visit by visitor ID, email, or a form sent
  within 2 minutes (said as not certain). API `/traffic-api/v1/<site>/people?q=` and the MCP
  tool `find_person` need the `read_private` scope. Each search is in the audit log, without
  the value.
- **Visits kept with their address.** Each reader's visit is kept with its IP and user agent
  for `privacy.keep_days` (395), counted twice: a new audit recounts each day's kept visits
  and pages per address from the log, and a day that disagrees is withheld.
- **Nothing hidden.** Leads > "Left out" lists the spam, duplicate and test leads.
  Conversions lists cancelled, removed and test rows with their journey. A lead sync that
  removes a row keeps it in a removed list (when, why, the row). `conversions mark-test SITE
  ID... [--unmark]` marks test rows: listed, never counted, by both counts.
- **`skald doctor`**: one line per part (daily run, missing days, logs, the dashboard app,
  the hook receiver, each hook's secret and last delivery, the script tag, mail, a newer
  version, disk) with the exact fix. Settings > Integrations shows the same status per road,
  with a test that says what a real delivery would keep.
- **Calendly and Cal.com event-type filter** (`hooks.calendly.event_types`,
  `hooks.calcom.event_types`, in Settings > Integrations): one account that books for several
  businesses sends only your own events to Skald's figures; others are answered and dropped.
- **Four how-to guides** in Help: pick your road, send leads from your backend in 5 minutes,
  demo bookings, Docker first install.
- **The live demo** lists the left-out leads and the cancelled, removed and test conversions too.
  The person search needs a running install, so the demo does not offer it.

### Changed

- **Keeping IPs and emails is a setting, on for new installs** (`privacy.keep_ips`,
  `conversions.identity: full`; Docker `SKALD_KEEP_IPS`, `SKALD_IDENTITY`). **An install
  upgraded from before 2.4.0 keeps nothing new until you turn it on** (Settings > Data
  retention > People). Change your privacy notice first. `forget` now takes `--ip`, `--email`,
  `--vid` and `--lead` and deletes everywhere, kept visits and removed rows included.
- A hook time without an offset is read in the site's time zone, not UTC, and the delivery
  log says so. A lead that arrives through two tools is flagged (it would count twice).
- Percent shares of fewer than 10 show counts only.
- `hooks secret` prints the real address; `hooks test` shows what a real delivery keeps.

### What to do

Upgrade as usual. To keep IPs and emails on an upgraded install, update your privacy notice,
then turn it on in Settings > Data retention > People.

## 2.3.0 (2026-10-12)

Flags beside every country, and a visit from an AI assistant is never hidden inside an earlier
visit.

### Added

- **A flag beside every country** across the dashboard: tables, chips, filters and filter
  chips, drill-downs, visits, leads, conversions, requests, live, insights, the printed report,
  and the plain page and mails. The code or name stays beside it; unrecognised codes get none.

### Changed

- **A new outside source starts a new visit.** Before, a visit was one browser with no gap
  over 30 minutes. So someone who opened the site directly, then came back from ChatGPT or
  Perplexity minutes later, was one "Direct" visit. The assistant showed under "AI assistants
  that sent visitors" but not in Traffic sources or the visit list. Now a page arriving from
  an outside source (an AI assistant, search, social, email, another site, a campaign link)
  that differs from the visit's own starts a new visit. Same-site pages, pages with no
  referrer, and the same source again continue the visit. The audit's second count follows
  the same rule by its own code. Bot and crawler visits, and the "did the page draw" check,
  are unchanged.
- Days already stored keep their counts. `backfill --force` recounts the days the logs still
  hold. A manual audit of a day stored before 2.3.0 can differ on visits where someone came
  back from outside within 30 minutes; the daily run audits only days collected by the new code.

## 2.2.3 (2026-10-12)

"Visitor IDs off" now holds on every road, and "abandoned" no longer counts a later booking
as a lost one.

### Fixed

- **A booking in a later session was counted as abandoned.** A finish matched a start only by
  visitor ID. Now the same person (the same email, when the site sends it) finishing the
  action within the window counts too.
- **Visitor IDs off did not cover every road.** A webhook's `vid`, and the lead database's
  `session_id`, were kept even with `beacon.visitor_ids` off. Now neither is kept: the hook's
  `vid` is dropped from the spool and the store, and the session column is read only with
  visitor IDs on. A site's session ID (often 30 minutes) is not a visitor, and had made a
  booking in a new session look abandoned.

### What to do

Nothing: upgrade (`docker compose pull && docker compose up -d`, or `sudo skald upgrade`). The
next daily run rewrites lead-database rows that held a session ID; outgoing webhooks are not
sent twice.

## 2.2.2 (2026-10-12)

Webhooks work on every install, and every install opens the dashboard. An upgrade does both
by itself.

### Fixed

- **Webhooks answered 502 unless the script tag was on.** The receiver for the signed tool
  hooks (Calendly, Cal.com, Stripe, Typeform, HubSpot, the generic `lead` hook) runs in the
  beacon helper, which started only with `SKALD_BEACON_ORIGINS` (Docker) or when enabled by
  hand. Now the Docker image always starts it, `install.sh` enables it, and `skald upgrade`
  switches it on when it was installed but off. Without allowed origins it takes hooks only:
  `/traffic-beacon` and `/traffic-js/skald.js` answer 404 until the site's origin is set.
- **A config without `dashboard.app` showed only the plain page.** Installs made from an
  older `config.example.yml` have no such key; it now means the web app. `app: false` keeps
  the plain page.

### What to do

- **Docker:** pull the new image and start the container again (`docker compose pull && docker
  compose up -d`). Nothing else.
- **Install script:** `sudo skald upgrade`, or let the upgrade timer do it. Nothing else.

## 2.2.1 (2026-10-12)

### Fixed

- **Docker and one-command installs showed only the plain page, not the dashboard.** The
  container's generated config and `config.example.yml` did not set `dashboard.app: true`, so
  the site's address served the no-JavaScript fallback page (no menu, tabs or drawers). Both
  now turn the web app on. Docker: pull the new image and start the container again. An
  install-script install keeps its own `config.yml`: add `app: true` under `dashboard:`.

## 2.2.0 (2026-10-12)

Alerts when AI assistants start or stop reading your pages; a suggested llms.txt; one-command,
safe upgrades and a notice when a new release is out; a live demo; faster pages. No figure changed.

### Added

- **Update notices, safe upgrades, explicit migrations, optional automatic upgrades** (issue #8).
  Once a day Skald asks GitHub for its latest release (one request, header `User-Agent:
  Skald/<version>`, nothing else; `updates.check: false` turns it off; offline it is silent). A
  newer release shows as a card in the daily and weekly mail and a line on the dashboard for
  owners and admins (dismissible per version; security releases in red); `skald updates` prints it.
  `skald upgrade [--to vX.Y.Z] [--dry-run]` installs a release on an install-script install: checks
  the tarball's SHA-256 against SHA256SUMS, refuses downgrades, major jumps without
  `--allow-major` and the daily run's window (`report.run_window`), copies and restore-tests every
  database, swaps the code (the old one stays in `/opt/skald.prev`), migrates, restarts the
  helpers, health-checks, and rolls the code and the databases back on any failure. `skald migrate
  [--check]` lists and applies each database's schema steps after a copy, recorded in
  `migrations.json`. `updates.auto: patch | minor` (default off) lets the new
  `skald-upgrade.timer` upgrade by itself and mail the result; never across a major. Docker
  images are now also tagged by major version (`:2`). Guide: docs/UPGRADING.md.
- **AI alerts: an assistant starts or stops reading a page** (issue #5). Three new alert rules,
  judged once a day on the last whole day: an assistant (by its company: GPTBot, OAI-SearchBot and
  ChatGPT-User are OpenAI) fetched a page it had not fetched in the 28 days before; an assistant
  that fetched a page in 3 of the 4 weeks before has not fetched it for 7 days; visits likely sent
  by an assistant jumped or vanished against its 28-day average ("too few to judge" below the
  thresholds, never an alert). Each alert names the assistant, the page, the days and the numbers.
  No new figure: they read figures already counted twice (each assistant's requests by page, and
  the likely-AI visits), and a withheld or missing day makes a rule wait, never fire. Shown on
  Alerts (new **AI** filter) and in **AI reading changes** on AI & crawlers; mailed like other
  alerts and listed in the weekly mail when alert mail is on; a new outgoing webhook event
  `ai.reading_changed`. Settings `alerts.ai_*` (on/off per rule and every threshold).
- **Deploy to Cloudflare button for the Skald Worker** (issue #4). `deploy/cloudflare-worker/` now
  deploys in one click: the button copies the folder into a new repository in your GitHub or
  GitLab account and deploys it to your Cloudflare account. It asks for `SKALD_INGEST_URL` and
  `SKALD_TOKEN` as secrets, with no default. The Worker is deployed with no route and no
  `workers.dev` address: add your site's route afterwards. New files: `wrangler.toml`,
  `.dev.vars.example`, `package.json`; `wrangler.toml.example` stays for a deploy by hand. In
  README, docs/HOSTING.md and docs/CDN-LOGS.md.
- **Suggested llms.txt** (issue #6). Skald suggests an `/llms.txt` (llmstxt.org format) from your
  site's real pages: those people and AI assistants read most over the last 90 recorded days,
  grouped by section, under their titles from the website's page list (or their paths). Private
  paths, paths robots.txt disallows, redirects and gone pages are left out; any day not recorded
  is named. On Settings > AI crawlers (preview, Copy, Download), `ti.py llms-txt [--site X]
  [--out FILE]`, the MCP resource `skald://sites/<site>/llms.txt` and `llms_txt.json`. No figure
  is published. Skald never writes to your website. Contract: `docs/DATA-CONTRACT-LLMS-TXT.md`.
- **A live demo on GitHub Pages** (issue #3): https://spcaeo.github.io/skald/. `tools/demo.py`
  runs 60 days of sample data for a made-up site on example.com (RFC 5737 addresses, made-up
  names; people, AI assistants and their user fetches, crawlers, bots, leads, bookings and
  payments, a saved funnel, in-page events) through Skald's own pipeline and writes the dashboard
  as static files. Seeded, so each build tells the same story. The new `pages.yml` workflow builds
  and deploys it on every push to main and again every Monday, so the demo's dates stay recent. In the demo the page needs no helper: a banner says it is
  sample data, Compare and page stories read answers worked out at build time, and refresh,
  saving and the settings pages say they need a running Skald instead of failing.

### Changed

- **Faster dashboards, page stories and live runs** (issue #2). On a history ten times the size
  of the first live install, the 2-minute live run takes 6.2 s instead of 9.4 s, the data files
  5.0 s instead of 7.7 s, and a page's story 131 ms instead of 327 ms. No figure changed: every
  data file, compare answer and page story is the same, byte for byte. New indexes through each
  database's normal upgrade (history schema 12, accounts 5, conversions 3), applied once on first
  open. A benchmark, `tools/bench.py`, and the results and reasons in docs/PERFORMANCE.md.
- The tracking additions to the data contract (day kinds, leads, goals) moved out of
  `DATA-CONTRACT.md` into `docs/DATA-CONTRACT-TRACKING.md`, linked from it.
- The README and "Why Skald" say how to say the name: "skawld", one syllable.

### Fixed

- Insights that tie now come out in the same order on every run (the title breaks the tie), so
  the list no longer reshuffles between two identical runs.
- Older code refuses to read a history file written by a newer Skald, with a message to upgrade,
  instead of reading it wrongly.

## 2.1.0 (2026-10-12)

AI clicks that lost their referrer, estimated and kept apart; Cloudflare on any plan; a guide for
sites on Vercel. Every new figure has its own second, independent count.

### Added

- **Likely sent by an AI assistant (inferred).** A visit with no referrer and no campaign tag that
  lands on a page an assistant's user fetcher (ChatGPT-User, Perplexity-User, Claude-User, ...)
  fetched in the same minute or up to 15 minutes before is shown as "likely" from that
  assistant: on Sources, AI & crawlers (with fetches followed by a visit, per assistant), Leads
  (by first and last touch), Conversions (by first touch) and a visitor's
  details. Two or more assistants count once, as "more than one". **An estimate, never a count:**
  every place says "likely", with an (i) that gives the window, and it is never added to the AI
  assistant source, to people or to any other figure. Settings `attribution.ai_likely` (on) and
  `attribution.ai_window_minutes` (15). The user fetches it rests on are kept 180 days as minute,
  assistant and page only: no address, no user agent. Counted a second time by
  `audit_ai_likely.py`, `audit_leads.py` and `audit_conversions_figures.py`; a day that differs is
  withheld. Contract: `docs/DATA-CONTRACT-AI-LIKELY.md`.
- **The Skald Worker for Cloudflare, on any plan** (`deploy/cloudflare-worker/`). It passes each
  request on unchanged and, after the response has gone out, posts one edge record to
  `/traffic-ingest/<site>?format=edge`, so pages served from Cloudflare's cache are counted. New
  log format `edge_json`; its own rate limit (`ingest.edge_per_minute`, `ingest.edge_burst`); a
  record posted twice is read once; the independent audit reads edge records too.
- **An example Netlify Edge Function** (`deploy/netlify-edge-function/`) that posts the same
  record, for a Netlify site without Log Drains.
- **`docs/VERCEL.md`:** step by step for a site on Vercel, from zero to a working dashboard, and
  what each Vercel plan lets Skald see. Linked from the README, `docs/HOSTING.md` and Help.
- **Help:** "Likely from an AI assistant" in Leads and conversions, two new questions in the FAQ
  (what "likely" means; Cloudflare's cache), and "Your site on Vercel, Netlify or behind
  Cloudflare" in Getting started.

### Changed

- **Never a request counted twice with the Worker.** With `logs.edge_only_cached` (true unless
  the site's format is `edge_json`), Skald keeps only the Worker's cache hits when it also reads
  the server's log: any other cache status may have reached the server.
- `leads.json` gains the `likely_ai` column (just before `n`); `ai_activity.json` and each
  `conversions.json` day gain `likely_ai`. Existing fields are unchanged.
- The README's feature list, the comparison and "Why we built Skald" mention the estimate, the
  log drains and the Worker.

### Fixed

- A table with one row says "1 row", not "1 rows".

## 2.0.0 (2026-10-11)

The first public release. Skald grows from a traffic report into a platform: accounts, results,
agents and integrations. **Every new part is off until an install switches it on**, so an existing
install works as before. Every new figure has its own second, independent count.

### Added

- **Accounts (sessions mode).** Sign-in with email and password, organisations, owner, admin and
  viewer roles, invites, forgotten-password links, two-step sign-in (TOTP with recovery codes),
  "Keep me signed in", Show/Hide on password fields, and an audit log with CSV export.
- **Settings in the dashboard.** Retention windows (a shorter window says first what it will
  remove), mail and SMTP, sites, internal addresses, AI crawler policy, integrations and the
  organisation's security rules. Secrets typed there are write-only and kept in a 0600 file.
- **Conversions.** Signed webhooks from Calendly, Cal.com, Stripe, Typeform, HubSpot, Zapier (and
  Make, n8n, any script) and the site's own server; the site's lead database read as conversions;
  started, completed and abandoned forms and bookings; a Conversions page. Anonymous by default.
- **Outgoing webhooks** to a CRM, Zapier, Make or Slack: signed, HTTPS only, retried, never with a
  name or email.
- **The `skald.js` script tag** (under 6 KB): page views, form steps, phone, mail and outbound
  clicks, 75% scroll, copies, 404 views, and Calendly, Cal.com and HubSpot meeting bookings.
  Respects Do Not Track and GPC; consent mode; optional anonymous visitor IDs (off by default).
- **MCP server** with 13 read-only tools for Claude, ChatGPT and other agents, over Streamable HTTP
  with a scoped token, or stdio on the server.
- **Better tracking.** Leads by first and last source over any range, crossed with the team's lead
  status; time from first visit to lead; every saved funnel counted daily by source and device;
  engagement and returning visitors by source; goals from events per 100 visits; campaign tag
  problems; exit rate per page; a Yesterday period.
- **Logs from other servers.** `skald-ship`, one standard-library file, sends new log lines over
  HTTPS with a token that can only add lines to one site. Sites can be added from the dashboard and
  must prove their domain first.
- **Scoped API tokens** (`read`, `read_private`, `mcp`, `ingest`) per organisation.
- **A failure mail.** A failed morning run sends one short mail; a withheld day sends none.
- **A new menu** grouped by what you came for: Home, Audience, Results, AI & bots, Site & server,
  with Settings in its own menu. In-app Help pages, a drill-down drawer, a command palette, and a
  phone layout with a drawer menu.
- **A hosted layer** (sign-up, plans and limits, Stripe billing). Built and tested, **off**; Skald is
  not sold as a service today.
- **Public project files:** Elastic License 2.0, security policy, contributing guide, code of
  conduct, CI, Docker image and install script.
- **Four ways to install** (Docker, Docker Compose with an HTTPS profile, `install.sh`, manual)
  and a hosting guide (`docs/HOSTING.md`): Render (with a Deploy button), Railway, Fly.io,
  Kubernetes and a VPS for Skald; nginx, Apache, Caddy, Vercel, Netlify, Cloudflare, CloudFront,
  Fastly and WordPress for your site, with what each loses without a log.
- **Vercel and Netlify log drains:** `POST /traffic-ingest/<site>?format=vercel|netlify`, with
  Vercel's signature checked; a request sent twice is stored once; the audit re-reads them.
- **Real visitor addresses behind a platform's proxy** (`SKALD_TRUSTED_PROXIES`,
  `SKALD_REAL_IP_HEADER`); nobody is trusted by default.

### Changed

- The product, command, package and paths are all named `skald` (command `skald`, package `skald`,
  `/opt/skald`, `/etc/skald`, `/var/lib/skald`).
- Python 3.11 or newer is required (tested on 3.11 to 3.14).
- A browser-looking visit that loads no page assets is counted as a bot, with its own audit road.

### Security

- Fixes from two security reviews: strict path parsing at nginx's sign-in check (an encoded `..`
  could reach another organisation's files), sign-in floods counted before the password check and
  password checks capped, the helper never trusts identity headers in sessions mode, sites prove
  their domain, and new mail recipients confirm by link.

## 1.0.0 (2026-10-08)

The first release, used privately on one production website.

### Added

- **The report from logs.** Every request in one of five groups (people, AI assistants, search
  engines, bots and scanners, your own traffic) that add up to the log exactly, or the report
  refuses to send.
- **AI split by reason:** training, answering someone live, or a person clicking a citation.
- **Daily history** in SQLite (totals and labels only), a dashboard, and daily and weekly HTML mail.
- **"Today so far"**, redrawn every 2 minutes, and a Requests feed of the last 6 hours with the rule
  that placed each request, in words.
- **An independent audit** that recounts every figure from the raw log; a day that disagrees is
  withheld.
- **Breakdowns** by country, browser, system, device, source, campaign, landing page and hour;
  anonymous visits and journeys; returning visitors by keyed hash.
- **Verified crawlers** (owner address lists and DNS), with fakes filed as "claims to be".
- **Alerts:** site down, logging stopped, 5xx, 404 surge, crawler burst, new crawler, traffic drop.
- **Data quality** panel, deploy and change markers, nightly restore-tested backups, `forget --ip`.
- **Funnels**, leads by source, drill-down, compare any two ranges, page stories, reports as HTML or
  CSV zip.
- **AI crawler settings** (allow, block, block training only) and robots.txt beside each crawler.
- **CDN logs** (Cloudflare, CloudFront, Fastly), page speed, a read-only API,
  named users and roles, several sites in one install, and the optional event beacon.
