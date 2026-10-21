# Changelog: 2.8.0 to 2.13.0

The releases of 18 October 2026. Newer ones: [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.0-2.7.md](CHANGELOG-2.0-2.7.md).

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
