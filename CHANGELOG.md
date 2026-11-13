# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

## 2.49.1 (2026-11-13)

One odd referrer from a scanner can no longer stop a site's count.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting. A site whose live count or daily run stopped on
  such a line counts again at the next round; nothing was lost, the log still holds every line.

### Fixes

- **A referrer no URL parser can read no longer stops a count (#61).** Seen on Skald's own
  site at 00:20 UTC on 13 Nov: a router-attack scanner sent 5 requests with the referrer
  `{[RootURL]}/admin/more.html`. Python's `urlsplit` takes the `[` and `]` for a broken IPv6
  address and raises an error; four places that read referrers did not catch it, so the
  site's live count crashed on every round (Right now stood still at 00:20 for that site
  while the others went on), and the next daily run would have stopped on the same line.
  Now such a referrer has no host and no path: no source, no citation, no own-site file.
  The second counts read it the same way on their own road (one audit place caught it
  too). Affects any site whose log holds such a line; nothing to do. Checked: a new test
  runs the real line and three more like it through the day's count, its audit, the live
  count and the live audit; a guard fails if any referrer is split without catching the
  error; full suite OK; the live count of that site checked after the upgrade.

## 2.49.0 (2026-11-13)

Leads & sales in four simple tabs with one period rule; your AI assistant can ask how people reach your pages and on which page they booked; newest first everywhere; and a warning when Search Console stops syncing.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- `conversions.sqlite` moves to schema 11 on first open (a new `visits.posts_from` column, #57); a copy of the old file is kept beside it (`conversions.sqlite.v10.bak`). 2.48 and older refuse a schema 11 file, so roll back from the backup.
- Past days stay as they were counted. Leads sent by the script tag and leads Skald fills from page views get their sources again at the next daily run (#34).
- Leads & sales has four tabs; every old link still opens the same view (#33).

### Added

- **A Search Console or Bing sync that stopped now says so (#40).** Found on 12 Nov: one
  site's Search Console sync had failed on every try for 12 days, because Google said the
  Cloud project behind Skald's robot key had been deleted, and nobody knew. The only sign was
  a small red line on Settings. Now a sync that worked before and then failed on every try
  for a whole day (24 hours), or 4 tries in a row (one day of the 6-hourly syncs), counts as
  stopped. Not connected is never stopped. Then: a to-do on Overview › Insights (which
  engine, since when, Google's or Bing's own reason in one line, what to do, and one button
  to the settings), the same state on Settings › Leads & tools › Search Console & Bing and on
  Traffic › Search, `your_tools` over MCP says "stopped answering" with the reason, and one
  mail to the site's mail recipients when it stops and one when it works again, never one
  per try. A single failed try no longer mails; a sync that never worked still mails once
  at its first failure. A second count (`audit_search_sync.py`, in the daily audits) works
  "stopped" out again from the kept tries and withholds a to-do it does not bear out. Who it
  affects: every site with Search Console or Bing connected. What to do: nothing. Checked:
  `tests/test_search_health.py` (never worked, under a day, a day, 4 tries, back again, one
  mail each way, Bing the same, the audit agreeing and catching a planted change, old state
  files) and `tests/js/todos.mjs`, with example data and fake engines only.

- **MCP: `page_journeys`, how people reach a set of pages and where they go next (#51).**
  Asked by a developer working with an AI assistant: "for a given set of URLs, user
  profiles, journeys, how people come on that page". For 1 to 20 pages over whole days (at
  most 93), the new read-only tool answers the visits that read each page; how they arrived
  (landed on it, by source and referring site, or the page read just before); the page read
  next, or left the site; who they were (new or returning, lead or customer when the visit is
  proven to have sent a form, countries, devices); and the newest 20 visits, newest first,
  each with its pages in order. From Skald's stored visits, which carry no address. Days
  before the oldest kept visit are named in `not_kept`, never counted as 0. Who it affects:
  anyone using Skald's MCP; 31 tools now. What to do: nothing. Checked:
  `tests/test_mcp_journeys.py`, a second count by its own road
  (`audit_page_journeys.py`, SQL over the stored trails, run in the daily audit), and a
  read-only trial on three live sites' real visits: 75 figures each, 0 differences.

- **MCP `conversions`: by the page it happened on, and the pages read before it (#52).**
  Asked by a developer: "How did demos get booked from what page." The tool could group
  completed actions by source, first touch, landing page, country, campaign, device or
  tool, but not say on which page a demo was booked or a form sent, nor what the person
  read first. Now `by: "page"` gives the page last seen at or before the action in its
  visit, and `by: "path"` that visit's pages up to it (the 20 most common paths, each its
  last 10 pages). A conversion is tied to its visit by a proven link only, never a likely
  one: its visitor ID's page views, or the only server-log visit that sent a form within
  10 seconds of it; the answer says how many came each way. One with no such link counts
  as "page not known" ("page not known (visit not kept)" when that day's server-log
  visits are not kept), never dropped. Counted each run into `conversions.json`
  (`pages_at`, `paths_to`, `page_link`) and recounted by a new second count,
  `audit_conversions_page.py`, by its own SQL; a day the two disagree on is withheld.
  Affects anyone asking Skald through MCP; nothing to do. Checked by unit tests with
  example data (both links, the form's own second, a page in the form's own step, two
  visits sending a form at once, a day with no kept visits, a long path cut to 10) and a
  planted wrong page that withholds its day.

### Changed

- **Leads & sales has four tabs, not eight: Leads, Summary, Revenue and Funnels (#33).** The
  owner asked for it "simple and easy": eight tabs, three of them about the same leads, made
  people hunt for a figure. Where each old tab went: **Sources** is Summary's "Where they came
  from" (the five best sources, then one fold with every breakdown, the touches, likely from
  AI and the time to convert); **Calendar bookings** is Leads with **What: Demos**, its steps
  (opened, chose a time, booked, cancelled, rescheduled, no-show, won, lost) above the list,
  and its cancelled, removed and test lists under Leads' **More > Show left out**; **Events**
  moved to Traffic, since it counts what visitors did, not leads; **Find a person** is a
  search box at the top of Leads, for owners and admins (still the first result of Search or
  jump to). Summary no longer has "Count from" or Status, and no longer shows the lead
  database's own view (Lead quality by source, Funnel by source, Per day by kind), the demo
  funnel (now on Leads with What: Demos) or "Pages seen before converting", which counted
  every kind of conversion, not only leads. Who it affects: everyone who opens Leads & sales.
  What to do: nothing. Every old link opens the same view in its new place, and the new
  address replaces the old one, so Back never loops: `#sales/sources` opens Summary with the
  fold open, `#sales/bookings?bact=…` opens Leads with that kind, `#sales/events` and
  `#events` open Traffic › Events, `#sales/people` opens Leads with the box focused, and
  `#leads`, `#conversions` and links with `lsrc` or `lstage` open Summary. An old Sources
  link shows "Where they came from" first, under the figures, so it is on screen without
  scrolling. The keyboard
  shortcuts and the set-up cards' links land there too. Checked:
  `tests/js/sales-routes.mjs` (every old address, Back and Forward, the address keys),
  `tests/test_routes.py`, the e2e route table, and a click-through of the demo in light and
  dark, at desktop and phone width.

### Fixed

- **Opening a visitor could show another visit when the day's visit numbers moved (#56).**
  Found 12 Nov while checking the drill-downs: the page opens a visitor by its place in the
  day's list (day 2026-11-12, number 14). A late log line or a shipped batch can shift those
  places between two counts, so the page and the server could mean different visits, and an
  owner or admin could see another address's visits in the drawer. Now the page also sends
  the visit's start (site time, to the minute): the server opens the visit only when it
  started then, else the one visit of that day that did, and with none it says the place
  changed and to reload, never another visit. The same check on a visit's recorded sessions
  and on Right now's newest visits. Who it affects: owners and admins on sites that keep
  addresses. What to do: nothing. Checked: `tests/test_firsttouch.py` (a moved place, a start
  no visit has, a bad start refused), `tests/js/visitor-short.mjs` (the page sends it).
- **A booking's page came out "page not known" when the visit's page times rounded
  together (#57).** Seen in a read-only trial of the MCP `conversions` tool by page (#52)
  on 12 Nov: on one site, 3 of 3 bookings tied to their visit through the server log came
  out "page not known". A visit's page times are kept rounded (to 10 seconds after the
  first minute, then to the minute), so a page in the form's own step could be before or
  after the form, and Skald rightly refused to guess. Now each form a visit sends keeps the
  page it was sent from (its referrer on the site) beside its time, in a new column
  `visits.posts_from`; that page is the one the booking happened on, and the path runs to
  it. A form with no referrer from the site keeps the old rule. The answer says how many
  came this way (`page_form` in conversions.json, `page_from_form` in the tool). Who it
  affects: sites that keep visits with addresses and get forms through the server log.
  What to do: back up before the upgrade (`docker exec skald skald backup`);
  `conversions.sqlite` moves to schema 11 on first open, a copy of the old file kept
  beside it (`conversions.sqlite.v10.bak`). Days kept before stay as they were: their
  forms have no recorded page, so they keep the old answer, never a guess. Checked: unit
  tests with example data (a page in the form's own step, a page not in the trail, a page
  read twice, an old row with no page, a list out of step with the forms, the upgrade from
  schema 10 with its copy, an older Skald refusing schema 11), a second count by its own
  SQL (`audit_conversions_page.py`, json_each over the forms and their pages) that agrees
  and withholds a day with a planted wrong page, and the whole suite.

- **Paid customers showed as coming from stripe.com, and script-tag leads as "Not
  recorded" (#34).** Seen on the Leads & sales and Sources tabs: a buyer who paid on
  Stripe Checkout or PayPal came back with the payment page as referrer, so the visit after
  the payment was a new visit from "Other website: checkout.stripe.com", and the lead or sale
  made in it took that as its source; and a lead sent by the page's script tag did not take
  the source of the visit it was sent from (only the source its own event carried), so some
  read Unknown (shown Not recorded) or Direct. The owner's decisions of 11 Nov: (6) a referrer that is a payment page
  (`checkout.stripe.com`, `paypal.com`, `www.paypal.com`, `checkout.paypal.com`, one list in
  `payment_names.py`, plus a site's own `site.checkout_hosts`) is the new source
  type **Returned from payment**. Back within the 30-minute visit gap it continues the open
  visit, which keeps its source (splitting it would add a reader who is not there and hand
  the lead to the payment page); later it is a visit of its own under that label, never a
  referral, with the referrer row `(payment page)`. A lead or sale after it keeps the source
  of the visit before it (the same browser's page views, or the sender's first touch), and
  it is never a lead's source, first touch or assisting source. (7) A script-tag lead's
  source is now the source of the visit it was sent from, by its visitor ID's page views
  (filled by Skald); only with no page view to prove a visit does its event's own source
  stay, and a payment page's is then Not recorded. Who it affects: every site whose buyers
  pay on Stripe Checkout or PayPal, and every site with the script tag's visitor IDs on. What
  to do: nothing. Traffic days already stored keep their figures unless someone counts them
  again (`backfill --force`, then `audit --day ... --withhold`); script-tag leads and leads
  Skald filled from page views are filled again at the next daily run, so their sources on
  past days change then; the lead database's figures are worked out afresh on every build.
  Checked: `tests/test_payment_and_beacon_sources.py` (a Stripe return inside the gap keeps
  the search source; after the gap it is Returned from payment and adds no referral; PayPal
  the same; a script-tag lead takes its visit's source; one with no proven visit keeps its
  own, and from a payment page stays Not recorded), both rules recounted by their own second
  roads (`audit.py` with `audit_labels.py` for visits, `audit_filled.py` and
  `audit_leads.py` for leads, `audit_conversions_figures.py` for assisted sources), which
  agree and catch a planted change; the whole suite.
- **The same click showed different counts on Leads & sales (#32).** The owner saw it: "the
  same click showed different counts". Leads counted 7 days up to today from every tool,
  while Summary and Sources counted 7 whole days up to yesterday, from the lead database by
  default, and some tables counted button clicks or a site's own actions as if they were
  leads. Now every tab reads one period, from one function: 7, 30 and 90 days, All time and
  a custom period that ends today include today so far, marked live; Yesterday is that whole
  day. Every Leads figure counts leads only: forms sent and demos booked, completed, never a
  click, a payment or an app's own action. So Summary's Leads tile and the Leads tab show the
  same number for the same period. A completion rate is shown only where the page's script
  saw both the starts and the completions; anywhere else it says "not comparable", with one
  line why, on Summary's table and on Leads' booking steps alike. Compare is off by default
  on Leads & sales, because each period holds today so far. Revenue per visitor, for a period
  that ends today, is taken over its whole days (today's visitors are not whole until the day
  is), and says so, instead of going blank. Who it affects: everyone who reads
  Leads & sales; a figure on Summary can move up (today's leads are now in it) or down (a
  non-lead action is no longer in it). What to do: nothing. Checked: a second count for the
  new figure, `conversions.json`'s `today.periods` (the 7, 30 and 90 days that end today),
  recounted in one SQL window per period by `audit_conversions_leads.check_periods`, so a sum
  that does not agree is withheld (`tests/test_leads_today_period.py`); the page compares its
  own figure with that block and withholds it, with why, when they differ
  (`tests/js/sales-period.mjs`); the rate rule in `tests/js/sales-rate.mjs`; the same count on
  Leads, Summary and Revenue for 7 and 30 days; and a source check that no Leads & sales tab
  builds a period of its own.

- **A drill-down on today lagged Right now and did not say how old it was (#53).** Seen on
  a client's site on 12 Nov: Right now showed the owner's visit from a city, and the city's
  panel did not. The panel read the page's data file, which the page re-reads every two
  minutes, and its request and period parts were kept from the first time the tab opened
  them. Now a panel opened on Today reads the newest count at once, says "as of 17:24"
  beside its visits, reads its request and period parts fresh every time, and lists the
  latest visits newest first (visits that started in the same minute: the later one on
  top). Who it affects: every site. What to do: nothing. Checked: `tests/js/live-newer.mjs`
  (newest first with the tie-break; the as-of words only on Today), the whole suite.
- **Newest first everywhere: lists that showed or kept the oldest rows (#55).** The owner's
  rule (12 Nov): every list ordered by time shows the newest on top. Some did not, and a
  few that were cut to a limit kept the oldest rows and dropped the newest. Now newest
  first, and a cut list keeps the newest: a lead profile's "Everything they did" and its
  visits; Find a person's pages seen by its visitor IDs (500), its conversions (500), its
  visits (one list, not grouped by address) and the visits at a lead's time; the journeys
  on the Conversions lists (the newest 200 pages kept, read in time order as a path); the page-script visits in the visitor drawer (500); a
  lead's own visits (200); open security items on the page and in the summary and
  right-away mails; a visit's recorded sessions and a session's log visits; pending
  invites. Closed alerts are now listed by when they closed, with a Closed column, on
  Site › Alerts and Health › Alerts. Left in time order on purpose, because each is a
  path: the pages inside one visit, the steps of one lead or conversion, and a page
  story's firsts. "First came from" still names the earliest visit. Who it affects: owners
  and admins who look people up, everyone who reads alerts or security items. What to do:
  nothing. Checked: `tests/test_newest_first.py` (newest on top, and with more rows than
  the limit the newest kept; each fails on the old code), new tests in
  `test_accounts_invites.py` and `test_recorded_journeys.py`, `tests/js/closed-alerts.mjs`,
  `tests/js/lead-profile.mjs`, and the whole suite.
- **"Next update" and "late" now follow how often the live count really runs (#54).** On a
  server with many sites, one live round of them all takes 5-6 minutes, so the scheduler's
  2-minute turns in between are skipped. The footer counted down two minutes and then said
  "next any moment" for most of every round, and Data quality showed amber "late" badges on
  the live count and the alert check for part of every round. Now each job keeps the gaps
  between its last few successful runs (`runs.json` `gaps_s`; a gap over 6 hours, a stopped
  server, is left out), and uses their median, never less than the plan. The footer says
  "next in about N min" to that time, and "any moment" only once it has passed. Data
  quality says how often a job really runs ("every 6 minutes (measured)",
  `measured_every_min` in `quality.json`) and calls it late only after twice that; the MCP's
  `site_health` uses the same figure. About 100 places that said the live count runs every
  2 minutes (dashboard, help, docs, website) now say every few minutes, and that Refresh now
  counts the site at once. Who it affects: every install; most visible with many sites. What
  to do: nothing; a server measures its round after its first three live runs. Checked:
  `tests/test_live_round.py` (gaps kept, median, a long gap left out, an old `runs.json`
  loads, late after twice the measured gap, the MCP), `tests/js/live-round.mjs` (the
  footer), the whole suite. Also: an upgrade by `upgrade.py` (servers set up with install.sh) waits up to 10 minutes for a running live round, not 2, and Site › Alerts says the check runs every few minutes.

## 2.48.2 (2026-11-12)

Right now never steps back: an older count no longer replaces a newer one, so a visitor you just saw does not vanish again.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting.

### Fixes

- **Right now: an older count no longer replaces a newer one (#50).** Seen on a client's
  site on 12 Nov: the owner opened a page, pressed Refresh now and saw their visit; two
  minutes later it was gone again. Live counts overlap (the server's round of every site
  takes minutes, Refresh now counts one site at once), and a round that had started
  earlier finished later and saved its older count over the newer one. The same could
  happen in four more places, found by a review of the whole app. Now:
  - a count is saved under a lock, and only when it reaches further than the one already
    saved; an older one is dropped with "a newer count is already saved; kept it";
  - today's kept visits (the person search) are replaced only by a run that read further
    (a "kept up to" marker beside the count);
  - one page redraw per site at a time, each drawing the newest saved count, so a redraw
    that started on an older count never finishes last;
  - one alerts check per site at a time, so two overlapping counts cannot mail one alert
    twice;
  - an open dashboard takes a refreshed count only when it is later than the one shown.

  Who it affects: every site, mostly busy servers with many sites. What to do: nothing.
  Checked: `tests/test_live_newest.py` and `tests/js/live-newer.mjs` (an earlier count
  finishing later leaves the saved count, request list and kept visits untouched; a
  later count and a new day still write; draws wait their turn; the first test fails on
  the old code), the whole suite.

## 2.48.1 (2026-11-12)

Each page's index status comes in about four times faster, and a check stopped part-way keeps what came in.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting.

### Fixes

- **The index status check was slow and kept nothing until it ended (#49).** Seen on
  a client's site right after 2.48.0 went live: the URL Inspection step after a Search
  Console sync asked Google one page at a time (about 6.5 s each, 22 minutes for 200
  pages) and kept every answer in memory until the end, so a job stopped part-way (an
  upgrade, a restart) lost every answer while Google still counted them against the
  day's quota. Now four pages are asked at once and the answers are kept 20 at a time:
  200 pages take about 5 minutes, and a stop keeps what came in. A refusal still stops
  further asking. Who it affects: every site with Search Console connected. What to do:
  nothing. Checked: `tests/test_search_inspect.py` (several pages in flight at once; a
  refusal part-way keeps the batch before it and the day's count), the whole suite.
- **Docs: Restricted access is enough for index status.** Google answered a client site's
  Restricted robot for all 200 pages on 12 Nov; the help and `INTEGRATIONS-SEARCH.md`
  say so.
- **No client named in a test note.** `tests/test_crawler_browsers.py` named a client's site in its
  opening note; it now says "a client site". Nothing to do.

## 2.48.0 (2026-11-12)

Search Console for AI agents: the MCP's new search_performance gives Google's own clicks, impressions, CTR and position per page and day, with the page's queries and countries and whether Google has it indexed. A page's story shows Googlebot's and Bingbot's latest fetch and its time on page, counted from the log.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- **History schema 15** (a new table, `search_inspect`): the first start copies the history file to `history.sqlite.schema-v14.bak`, then adds the table. Check there is room for one more copy.
- New setting `search_console.inspect_per_day` (200; 0 turns URL Inspection off).
- A page's latest crawl fills from the next collect on; `backfill --force` fills the stored days. Countries per page start with the next Search Console sync; a 16-month backfill fetches them for the past.

### New

- **Search Console for AI agents, and each page's index status (#41, #45).** A client's
  page tracker reads Skald through the MCP and needed Search Console's figures per page to
  see whether 45 rebuilt pages were found: none of the 29 tools gave clicks, impressions,
  position or whether a page is indexed. Now:
  - **`search_performance`**, a new read-only MCP tool (30 tools now): Search Console's (or
    Bing's) own clicks, impressions, CTR and position per day, for the whole site or one
    page (every address of the path added), with the page's top 10 queries and countries
    (Skald now keeps each page with its country, `page_country`, counted by page and re-added
    by the audit like every stored table; days fetched before are named, never 0); without a page,
    the site's days, top pages, top queries and countries. A day not stored is named; a page
    with no row is 0 only on a day whose page table is complete, else "not known" (null),
    never 0. Labelled as the engine's own figures, never added to Skald's visits.
  - **Index status per page.** After each good Search Console sync Skald asks Google's URL
    Inspection about up to 200 pages a day (`search_console.inspect_per_day`, 0 turns it
    off): the pages Google showed in the last 28 days, then pages people read that Googlebot
    fetched, never-asked first. Google's answer is kept as given, one row per page and day
    for 16 months (history schema 15, table `search_inspect`): indexed, crawled or
    discovered but not indexed, not seen by Google yet, or excluded with Google's reason, its last
    crawl, and the canonical Google chose against the page's own. A refusal (permission,
    quota) is kept in the sync state and never fails the sync.
  - **`your_tools`** also names Search Console's and Bing's state (answering, last try
    failed, stopped answering) and when it last answered.

  Who: anyone using the MCP with Search Console connected. To do: nothing; the upgrade to
  schema 15 copies the history file aside once (DEPLOY.md). Checked: tests against the fake
  Search Console (the answers kept as given, the daily budget, a refusal, never-asked
  first, nothing asked twice in 20 hours), the tool's figures on a fixture (two addresses of
  one path, a complete and an incomplete page table, a missing day), and the second count
  `audit_search_pages.py`, run by the daily audit, which recounts the tool's per-page days
  and the index counts by its own SQL and catches a wrong figure.

- **A page's latest Googlebot and Bingbot fetch, beside the first (#44).** A client's page
  tracker rebuilt more than 45 pages from 10 Nov and could not tell whether Google had fetched
  the new versions: the page story (MCP `page_story` and Traffic > Pages > a page) gave only each
  crawler's first fetch, weeks old. Now it also gives each one's latest fetch and the status it
  got (`milestones.googlebot_latest` / `bingbot_latest`, `{"at", "status"}`; null when the
  crawler never fetched the page since the logs began), and the page story shows it as
  **Latest crawl** under the firsts. Same rule as the first fetch: verified Googlebot or Bingbot,
  and a page view (200-299 or 304), never a redirect or an error. Kept for good in the page
  milestones table (no schema change, no setting), so it survives log rotation; a day collected
  again never moves it back. Pages gain it from the next collect on (a `backfill --force` fills
  it for the stored days). Who: anyone reading a page's story; nothing to do. Checked: tests for
  the first and latest, a 304, a 404 and a 301 left out, a re-collected earlier day, pruned
  stored days, the command line and the MCP text; the audit recounts each day's latest fetch from
  the raw log (`audit_release2.FirstsRecount`) and a changed status in history fails it.
  A day kept before 2.48 has no latest fetch: the audit leaves it out for that day (not
  recorded) rather than calling it a mismatch, found by auditing 11 Nov on a copy of the live
  data before release.

- **Time on page from Skald's own log, per page per day (#46).** A client's page tracker read
  time on page only from Google Analytics, which stopped answering from 1 to 12 Nov. Skald
  already kept, per page per day, the seconds from each view to the visit's next view; the page
  story now shows it: `time_on_page` `{"median_s", "measured", "not_measured_last_page"}` per day
  in `days[]`, and over the whole, checked days at the top (with `min_measured` and `days`). A
  view that was the visit's last page has no next view, so it is not measured and is counted
  apart; under 5 measured views the median is withheld (null), never 0. Shown in the MCP
  `page_story` text and under the page story's daily chart. An estimate: the log sees when the
  next page was asked for, not how long someone read. Who: anyone who wants time on page without
  Google Analytics; nothing to do (the stored days already have it). Checked: tests for the
  median, the minimum, the last page and the whole days; a new second count
  (`audit_page_time.py`) recounts each day's seconds per page from the raw log and the shown
  figure by its own median, and fails on a changed day; until now those stored seconds were not
  recounted at all.

## 2.47.0 (2026-11-12)

Overview is one page with Right now on top: who is on the site now, the page each person is on, New, Returning, Lead or Customer, and Refresh now that counts this site at once. A lead's drawer shows their profile, and a visit that sent a lead carries a Lead or Customer pill.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting. `#overview/realtime` links still work (they open Overview for today).

### New

- **Overview is one page, with Right now on top (#43).** The owner could not see who was on the
  site at that moment: the visitor figures were 4 to 7 minutes old with no way to count again,
  Summary and Real time showed the same thing twice, and "What converted today" and "Where
  today's visitors came from" were confusing on the main page. Now:
  - **Right now**, on top of Overview in every period: people on the site now, the last 30
    minutes minute by minute, and the people here now, one row each: where they are and their
    device, the page they are on now (copy and open), time on the site, pages, where they came
    from, and a pill: **New** or **Returning** (with how many of the last 30 days and where they
    first came from), **Lead** or **Customer** when the visit carries #31's proven mark. No pill
    when Skald cannot tell (never shown as New). A row opens the visitor drawer; the first six
    are listed, the rest in a fold kept in the address.
  - **Updated 40 s ago** says how old the count is, and **Refresh now** counts this site at once:
    `POST <page>/refresh` now runs `live` for that site only (`--site`), not every site (which
    took about 4 minutes on an install with 14 sites, longer than the run's 90-second limit), answers JSON when
    the page asks for it, keeps one run at a time and a 15-second gap per site; a site the
    install does not have is refused and nothing runs. Saving internal addresses, funnels or a
    test mark also recounts only that page's site now.
  - Real time is no longer a tab: its requests chart, map, pages being read, newest visits,
    sources, devices and machines now sit under today's tiles, then the flow. `#overview/realtime`
    opens Overview for today. "What converted today" and "Where today's visitors came from" left
    the page (they stay on Leads & sales and Traffic › Sources).
  - The live run's `doing` rows carry `returning` and `days_seen` (visitors.py's labels, the
    ones the visit list shows). No figure is counted anew: every number is Real time's, which
    `audit --live` recounts.

  Who: everyone who opens Overview. To do: nothing. Checked: tests (`tests/js/right-now.mjs`,
  the refresh helper's per-site run and JSON answer, routes, the realtime `doing` labels), the
  full suite, and the demo build in a browser (Today and 7 days, a row opening its journey,
  `#overview/realtime` landing on Overview, Refresh now in the demo).

- **A lead's profile in its drawer, and a Lead or Customer pill on visits (#31).** The owner
  asked, about a new customer, to see "everything about him in his profile", and a pill on a
  visitor who is a customer. Before, a lead's drawer on Leads & sales > Leads showed its steps
  and facts but not the visits that sent it: you had to search its reference in Find a person.
  Now owners and admins see **Their profile** in the lead's drawer: who (name and email, only
  where the site keeps them), everything they did with its time and value, where they first came
  from and every visit in order with its pages, each marked proven or likely. It is asked by the
  lead's reference, like Find a person, and written to the audit log; the link keeps only the
  lead's row number. On Traffic > Visitors and in the visitor drawer, a visit proven to have sent
  a lead (the only visit that sent a form at the lead's time) shows a small **Lead** pill, or
  **Customer** when that person has paid; a likely visit never gets one. The pill is a label,
  never counted; the daily second count (audit_lead_visits) now finds every pill again by its
  own road. Who: owners and admins for the profile; every member sees the pills. Nothing to do.
  Checked: Python tests on a sandbox shaped on a real lead (proven, likely, two visits at one
  second, a test row, a lead that has not paid, app.json carrying the pill on that visit only,
  the audit catching a wrong pill), and tests/js/lead-profile.mjs (the profile for an owner,
  none for a viewer, no reference or email in the link, the pills on the list and the drawer).
  Speed: the pills cost the live run one read-only look at the conversions store per site (the
  last days' finished conversions and the visits that sent a form around them).

## 2.46.6 (2026-11-12)

Right after an upgrade every dashboard page shows the new version at once; and a small Find a person fix.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting.

### Fixes

- **Fix: right after an upgrade, a dashboard could show the old screens (#38).** Checking 2.46.5
  live on 12 Nov, Find a person did not show its new part though the server sent it. The live run
  replaces the shared code first and rewrites each site's page only at that site's turn, so for up
  to 2 minutes a page still named the old version and a browser ran its kept copy of the old code
  until a reload. Now a new version rewrites every site's page in the same step (`_app/VERSION`
  says which version the pages name). Who: anyone opening a dashboard just after an upgrade;
  nothing to do. Checked: a test installs a new version for one site and finds another site's page
  naming it (it failed before the fix), and a static page left as it was.

- **Find a person: no stray full stop under "First came from" (#30).** On the live check the
  full stop after the landing page's copy and open icons wrapped onto a line of its own. Removed.
  Who: owners and admins; nothing to do. Checked: tests/js/person-path.mjs and on the live page.

- Housekeeping: the 2.45.3 entry named the customer whose request led to the fix; it now says
  "a customer". Client sites are not named in public text. Nothing to do. Checked: the full test
  suite.

## 2.46.5 (2026-11-11)

Find a person shows a lead's own visits, in order: where they first came from, every page, and whether each visit is proven or likely theirs.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting.

### Changes

- **A lead's own visits, in order (#30).** Find a person showed a server-sent lead's steps but
  not how the person got there: on freshlycited.com, lead 1179's journey had to be rebuilt by hand
  from the server log. Find a person now lists that person's visits, oldest first,
  with where they first came from, every page and what each visit sent. A visit is "proven" when
  it is the only one that sent a form within 10 seconds of the lead, "likely" when it has the same
  address and browser within a day; a step no visit is proven for is listed as not matched. Owners
  and admins only; never counted in a figure. Who: every site that keeps addresses with its visits;
  nothing to do. Checked: lead-visit tests (proven, likely, another browser not linked, two
  visits at one second prove nothing) and tests/js/person-path.mjs. Second count:
  `audit_lead_visits.py`, run every day by run-daily, finds each conversion's proven visit again
  by its own road and checks every likely visit against the rule; a mismatch ends the run with
  exit 1 (no figure is withheld: these links are never counted).

- **Website: the 2.46.4 "What's new" entry closed properly.** On skaldanalytics.com/whats-new/
  the 2.46.4 entry was missing its closing tags, so the 2.46.3 entry sat inside it. A release
  helper mistake, fixed the same evening. Who: website readers; nothing to do. Checked: every
  list and box on the page opens and closes in order (an HTML tag check), site build problems none.

## 2.46.4 (2026-11-11)

Funnels count the leads your site sends, the default funnel fits a site without a pricing page, and three small Leads & sales fixes.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting.

### Fixes

- **Funnels count the leads your site sends (#25).** On a site without a lead database (its leads
  come from its own server or a tool, through the hooks), every lead step of a funnel read
  "not recorded": freshlycited.com's default funnel never showed its sign-ups. A lead step now adds
  up the leads the site sent on the funnel's visit days, from the day counts Leads & sales already
  shows (each checked by its second count; a day that failed is left out), each lead once. With a
  starting source it shows "-" (a lead's first touch is not the visit's source). A lead step may
  also name any action the site has sent (Add a step › "A lead, sent by your site"). Sites with
  a lead database are unchanged. Who: every site on the hooks; nothing to do. Checked:
  tests/js/funnel-leads.mjs (counts, a withheld day, the page), funnel tests.
- **The default funnel has no Pricing step (#25, #27).** "Landing to lead" required a pricing page
  in order, so on a site without one (freshlycited.com) every step after the first read 0. It is now
  landed, a sign-up or contact page, then the lead steps; its lead steps no longer say
  "(lead database)". A saved funnel can still have a pricing step. The default keeps no daily
  history, so none is lost. Nothing to do. Checked: funnel tests.
- **Calendar bookings no longer shows another action's sale (#27).** Since 2.46.3, freshlycited.com's
  Calendar bookings › Every stage showed a "Sign-ups" row with its $25.00 sale while "Demos" was
  chosen: the page narrowed every figure to the booking except the new sales by action. It now
  narrows those too, and on a range with no booking it says "No booking in this range" (it said
  "No conversion", on a day with five other conversions). Affects every site with sales; nothing to
  do. Checked: tests/js/summary-sales.mjs, and on the live page before the fix.
- **A form page called /sign-up or /register counts (#27).** Funnels' "Sign-up, contact or
  early-access page" step and Leads › Funnel's "Opened a form" matched `signup` but not `sign-up`:
  freshlycited.com's form page (16 visits on 4–11 Nov) was never counted. The list gains
  `sign-up` and `register`; the second count (audit_leads) takes the same list, so both move
  together. Counting change: sites with such pages show more "Opened a form" visits from the next
  build (every build recounts every day); nothing to do. Checked: a new leads test.
- **A visitor's "Leads and conversions (n)" counts each lead once (#27).** One lead with a sign-up
  and a payment on its reference read "(3)": the heading added the steps and the reference. It now
  counts what the part lists. Checked: tests/js/visitor-drawer.mjs.

## 2.46.3 (2026-11-11)

Leads & sales › Summary shows a payment: a Sales figure and each action's sales and value, and no completion rate clamped to 100%.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting. conversions.json's `revenue.by` gains `action` on the first build.

### Fixes

- **Leads & sales › Summary shows a payment (#26).** On freshlycited.com today a sign-up paid $25.00, yet Summary showed only "Leads 1" and "Won 0": no sale anywhere. Summary now has a **Sales** figure (sales and their value per currency, the Revenue tab's figures) and the table, renamed **What people did**, has **Sales** and **Value** per action; a sale belongs to the lead it was paid for (revenue's new `by.action`, the lead's own action, counted again by `audit_revenue`). Columns and tiles of stages a site has never sent in the file's days (Started, Abandoned, rate, Cancelled or no-show, Won, Lost, Demos booked) are left off (freshlycited.com keeps Won, Lost and Started: it sent them in October; it loses Cancelled and Demos booked), and **Count from** is gone on a site with no lead database. Who: every site with sales; nothing to do. The completion rate is no longer clamped to 100%: an action whose completions came partly from your server or a tool (no start to match them) says "not comparable"; freshlycited's 30-day sign-ups read 100% from 25 starts and 84 completions. Checked: a column-by-column check of every Leads & sales tab on freshlycited.com against the live store (the rest is #27), `tests/js/summary-sales.mjs` (freshlycited's day), revenue tests with a second count, the full suite.
- **Two tests no longer fail on a busy machine (#29).** Publishing 2.46.3 failed twice while the
  Mac ran other projects: the live speed check timed itself by the wall clock (15.6 s against
  15 s; about 3.4 s when quiet), and a test server's temp folder was removed while a handler
  thread still wrote into it. The speed check now counts CPU time; the folder clean-up ignores a
  late write. Affects nobody using Skald; nothing to do. Checked: both files' tests pass.

## 2.46.2 (2026-11-11)

A fix for 2.46.0: an opened failed fix says plainly what is still wrong, and addresses only bots ask for no longer fail a lost-pages fix.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting.

### Fixes

- **Insights: an opened failed fix says plainly what is still wrong (#23).** On one site, an
  opened failed "Old pages still answer Page not found" card was confusing: the AI assistant's "Done" note and a week-old check ("4 fixed, 46 not yet ... none answered
  404") read as good news above a Failed card, there were six actions, and the list mixed 2
  real pages with 4 addresses only bots probe (`/wp-/`, `/_astro/`, `/*/`,
  `apple-app-site-association`), which the assistant had left as not found on purpose. Now an
  opened failed fix shows "Still not found since your fix on <day>", each real address with
  **Send it to** (its closest live page), the bot-only addresses folded into one line ("stay
  not found; that is right for them", Show lists them, `tdbots=`), and three actions: Check
  again, Undo and History. The assistant's note and older checks sit behind **History**
  (`tdhist=`); a check just made shows its answer at once. Who it affects: anyone opening a
  failed fix. What to do: nothing. Checked: the Insights JS tests, the full test suite, the
  page in a browser (desktop and phone) with one site's real to-do list.
- **Counting change: addresses only bots ask for never fail a lost-pages fix (#23, owner's
  choice).** A still-failing old address that no person asked for since the fix, and that has
  no live page like it (`closest_page`), is named in the re-check's new `bots_only` list and no
  longer keeps the fix Failed; one with a live page to send it to, or that a person asked for,
  still does. The second count (`audit_todos.bots_only_of`) recounts the list by its own SQL and
  its own reading of the live pages, sharing only the closest-page rule, and withholds a to-do it
  disagrees with. Who it affects: sites with a lost-pages fix marked done. What to do: nothing.
  Checked: new tests (bots only passes; a page to send it to, or a person, keeps it failing; a
  nudged list or status is caught), and a read-only dry run on the live server: every site's
  to-do list built with the new code, nothing withheld (one site's fix still Failed with 4 bot
  addresses set apart, another's with 1).
- **Test fix: the "fill past days" page test waited a fixed 30 ms (2026-11-11).** On a busy
  machine the first progress read landed later, so the test sometimes saw "starting" instead of
  "4 of 9" and failed the full run (seen once in the 2.46.2 release run; 2 of 5 reruns). It now
  waits until the progress shows, up to 2 s. Who it affects: developers only. What to do:
  nothing. Checked: 30 runs in a row, 10 of them with the machine under load.

## 2.46.1 (2026-11-10)

A fix for 2.46.0: each Insights card shows only its three lines until it is opened.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting.

### Fixes

- **Fix: an Insights card shows only its three lines until it is opened (#21).** On the live
  2.46.0, a "Fixes that failed" card showed the AI assistant's done note (a paragraph and its
  files) and the last Check again result ("Checking 50 of 386 addresses ...") under its three
  lines, before Fix this and Open. The approved design keeps every card to what is wrong, why
  and what to do; the sample data the design was checked on had no such note, so it did not
  show there. Now the note and the check's answer sit behind Open, and a link to a check's
  answer opens its card. Who it affects: anyone whose to-dos were fixed by an AI assistant or
  checked again. What to do: nothing. Checked: the Insights JS tests (the card's face has no
  note or answer; Open and a check link show them), the full test suite, the page in a browser.

## 2.46.0 (2026-11-10)

Insights shows only what needs fixing, in plain words, and a fix the log still finds failing
says Failed. Crawlers that read pages in a real browser are counted as crawlers, not people.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- No schema change. Two new settings, both on by default: `site.cloud_fast_pages` (20) and
  `site.cloud_fast_seconds` (10); `cloud_fast_pages: 0` turns rule 9c off.
- People figures can drop a little where crawlers read the site in a real browser. Days
  already stored keep their figures unless recounted (`skald backfill --days 14 --force`).

### Changes

- **Overview > Insights shows only what needs fixing (#5, #6).** Insights was hard to read:
  long cards with proof sentences, five buttons each, a "Done, and did it work?" list, and the "What changed" cards below, with figures that did not match each other
  (59 visits on one card, 62 on another, for the same page). Now the tab shows only open
  problems: **To do this week** and **Fixes that failed**, one card each, in three plain lines
  (what is wrong, why it matters, Do: what to do) with no counts, percentages or dates, a pill
  (Needs fixing, Failed), **Fix this** and **Open**. Every open leaving page shares one card
  ("3 pages lose their readers", `todo=leave`). One small link, "N fixes being checked"
  (`show=checking`), lists the fixes still being checked, the ones that worked and the page
  changes marked on Traffic > Pages; with nothing open the page says "Nothing to fix right
  now." Open shows the list behind a card (a failed fix: the addresses still failing since the
  mark), its tab, and the smaller actions (Check again, Mark done, Not now, Undo). The cards'
  words are written in one place (`js/tabs/todo-words.js`), from each to-do's own fields; no
  site is typed in. What rose or fell stays on Overview > Summary. Who it affects: everyone
  who opens Insights. What to do: nothing. Checked: the JS tests of the cards, Open, the
  marks, Check again and Fix this (todos.mjs, todo-check.mjs), the full test suite, and the
  page in a browser against the approved mock-up (light and 390 px).
- **Fix: a fix that the log still shows failing says Failed (#5).** When Check again found
  every address fixed, the to-do showed "Fixed", even when visitors and crawlers kept getting
  "not found" on the days after (on one site, Check again passed on 2 Nov, then
  `/news_sitemap.xml` answered 404 twice a day). Now the daily re-check of the log decides:
  todos.json gives each to-do a `status` (open, checking, failed, passed, notnow) and, on a
  re-check, `still` (the addresses still failing, most first) and `still_total`; the card says
  "1 of 3 sitemaps is still missing". The second count (audit_todos.py) recounts the
  addresses and the status by its own road and withholds a to-do it disagrees with. Who it
  affects: any site with a to-do marked fixed by Check again. What to do: nothing. Checked: new
  tests (a passing live check with a failing log shows failed; waiting is checking; the audit
  agrees, and catches a nudged status, address figure or count), the to-do tests, the full
  test suite.
- **Fix: Skald's own addresses are no longer "lost pages" (#16).** Skald's beacon
  (`/traffic-beacon/`) answers 404 to anything but its own posts, so crawlers that found it in
  a page were counted as asking for an old page: on one site, lost pages said 409 addresses and
  592 asks, 152 of them the beacon's, and the lost-pages re-check counted 82 "not found"
  answers since the fix, 74 of them the beacon's. Now `/traffic-beacon`, `/traffic-js/`,
  `/traffic-hooks/` and `/traffic-ingest/` (any case, with or without a trailing slash) are
  never a lost page, a Markdown or sitemap ask, or an address a re-check counts, on both roads
  (lost_pages.py and its second count). Look-alikes such as `/traffic-beaconx/` stay pages.
  Who it affects: every site with the beacon or the page script on. What to do: nothing; the
  next data update counts without them. Checked: new tests (both roads leave them out and
  keep the look-alikes, the audit agrees and names a beacon row slipped back in, the re-check
  never counts them), the to-do tests, the full test suite.

- **Counting change: crawlers in a real browser are no longer counted as people.** One site's
  31 Oct showed about 400 scroll events in two hours, counted as people's. OpenAI's crawler
  rendered pages in a real Mac Chrome: its page loads named the crawler and were counted right,
  but its page script's events did not, so they counted as people's. Checking a week of every
  site's logs also found headless browsers on Amazon and Google Cloud reading exactly 20 pages
  in a minute or two, counted as people on most sites. Two new rules, both
  counted on both roads: (1) a normal browser name from an address on a crawler's own published
  list (Google's common crawlers, Bing, Apple, OpenAI's GPTBot, OAI-SearchBot and OAI-AdsBot,
  PerplexityBot, DuckDuckBot) is that crawler, verified, not a person; lists a person can be
  behind (ChatGPT-User, Perplexity-User, Google's user fetchers) are left out (CLASSIFICATION.md
  rule 5b). (2) A browser from a hosting or cloud network that reads 20 pages or more at 10
  seconds a page or faster in one visit is "too fast to be a person" (rule 9c; settings
  `site.cloud_fast_pages`, `site.cloud_fast_seconds`, 0 pages turns it off). Before, a cloud
  address was only a flag, because people on a VPN come from there too; a VPN reader that fast
  is now counted as a bot, the price of the rule. Who it affects: sites with the crawler lists
  on (`bots.ranges_dir`, on by default in Docker); people figures can drop a little where such
  crawlers read the site. What to do: nothing; days already stored keep their figures unless
  recounted (`skald backfill --days 14 --force`). In-page events arriving one at a time follow
  rule 1, not rule 2 (it needs the whole visit), and 31 Oct's events stay as they are, with this
  note. Checked: new tests (both rules, the edges that stay people, the audit agreeing and
  catching a nudged figure), the full test suite, and a dry count of a week of every site's live
  logs, old rules against new, read only.
- **Fix: a weekly mail that cannot go out no longer stops the Monday run.** On Mondays the
  weekly mail is refused when its week is not complete (a site that started mid-week, or a day
  in it held back). That refusal stopped the whole morning run, skipped everything after it,
  and sent "[Skald] Daily run failed" (seen on two Mondays for one site). Now it skips that
  one mail with a line in the run log ("weekly mail skipped: ...; the run goes on"); the run
  goes on and ends ok. A mail that fails to send (the mail server) still fails the run as
  before. Who it affects: every install with the weekly mail on. What to do: nothing; the
  weekly mail comes back by itself on the first Monday after a whole week. Checked: the tests
  of a part week (the run ends ok, no failure mail), the full test suite.
- **Fix: two equal rows in the security list no longer hold back a day.** Security's "possible
  exposure" rows were ordered by time (to the second), host and path. When two addresses asked
  for the same path in the same second, the main count and its second count (the audit) could
  list them in opposite orders; the audit compares the list row by row, found two rows that
  differ and withheld the whole day (one site's 4 Nov: "history has 110, the recount finds 63"
  and the other way round). Both now settle a tie the same way: the answer, its size, the
  category, then the address number. Who it affects: any site, on a day two such rows tie. What
  to do: nothing; a day withheld for this can be counted again while its log is kept (`skald
  backfill`). Days already stored are not re-judged. Checked: new test (two tied rows, seen in
  either order, come out in one order on both roads), the security tests, the full test suite,
  and the live recount of the day that showed it.
- **Fix (website tests): the /check/ agency-mode browser test no longer fails one run in two.**
  The test clicked "Download one PDF" and then waited a fixed 3 seconds before looking for the
  "done" message. It runs in headless Chrome with virtual time (a test clock that only stops
  while a network request is open). The PDF step reads the logo with a FileReader, which does
  not stop that clock, so virtual time jumped ahead while the read finished. The done message
  came anywhere from a quarter of a second to more than 10 seconds of virtual time after the
  click, so the fixed wait often ended too early (`out["done"]` false, empty error). The
  test now waits for the real result: it asks the test server for a short answer again and
  again (each request holds the clock) until the done message or an error shows, for up to
  about 15 seconds. The page itself was right and is unchanged; the checks are unchanged. Who
  it affects: developers running the site tests. What to do: nothing. Checked: the failure
  reproduced 4 times in 8 runs and was traced to the FileReader; after the fix the test passed
  20 runs in a row, and all 51 site tests and the main suite passed.

## 2.45.7 (2026-11-09)

In-page events are kept even on a day whose log figures are held back, and an older day's events
can be checked.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting. A day's events withheld because the audit found no
  beacons in nginx's log can be collected again while that log is kept:
  `skald events --day <day> --collect`.

### Fixes

- **Fix: in-page events are stored even on a day whose log figures are held back.** When a
  day's log figures did not reconcile (so the day was withheld), the morning run stopped there
  and skipped every later step, the in-page events (scrolls, form starts, clicks from the
  script tag) among them. One site's events for a whole day were never stored. The steps that
  do not rest on the day's log figures (events, favicons, logo, updates, stack, kit tokens,
  page speed) now still run after a stop; the mails and the dashboard still wait, as before.
  Who it affects: sites with the script tag on. What to do: nothing. Checked: new test (a stop
  at the audit still runs events, not the mails), the full test suite.
- **Fix: the events audit can check an older day.** It read only the newest three files of
  nginx's beacon log, so a day collected or recounted later (here five days on) found none of
  its beacons and was withheld. It now reads every rotation there is, counting only the day's
  window. Who it affects: anyone recounting events for an older day. What to do: nothing; a day
  withheld for this can be collected again (`skald events --day <day> --collect`) while its
  beacon log is kept. Checked: new test (a day whose lines are in `skald-beacon.log.5.gz`
  audits ok), the full test suite, and the live recount of the day that showed it.

## 2.45.6 (2026-11-09)

An upgrade no longer leaves a dashboard on "404 Not Found" for minutes (Docker).

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no setting. This first start writes the dashboards anew on
  the volume, so a site not yet written says "This dashboard is being prepared" for a few
  minutes; from the next upgrade on the pages stay. If you run nginx yourself, take the new
  `@skald_not_written` lines from DEPLOY.md.

### Fix

- **Fix: no more 404 on a dashboard right after an upgrade (Docker).** Each site's dashboard
  pages were kept inside the container, not on the data volume, so every upgrade (`docker rm`,
  `docker run`) dropped them, and each site answered nginx's "404 Not Found" until the first
  live run wrote its pages again, one site after another (about ten minutes for thirteen
  sites). Seen on the live install after 2.45.5. Now the image links `/var/www/skald` to
  `/var/lib/skald/www` on the volume, so an upgrade keeps serving the last pages until they
  are rewritten. And a site's page that is not written yet (a new site, a fresh install, the
  first start after this upgrade) says "This dashboard is being prepared" (HTTP 503 with
  `Retry-After`, reloads by itself) instead of a 404; any other missing file is still a 404.
  Who it affects: Docker installs (an install without Docker kept its pages on disk already;
  it gets the "being prepared" page for a new site). What to do: nothing. The first start on
  this version still writes the pages anew; from the next upgrade on they stay. Checked: new
  tests (the image's link and the folder made at start; a real nginx answers 503 for a site
  not written yet and 404 for a missing data file), the full test suite, and on the live install.

## 2.45.5 (2026-11-09)

A fix for 2.45.4: a day where your own server got a server error adds up again.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no nginx line, no setting. A day withheld on 2.45.4 for this
  reason can be recounted while its log is kept (`skald backfill`).

### Fix

- **Fix: 2.45.4 could withhold a day when your own server got a server error.** 2.45.4 left
  your own requests out of the server errors by address, but the check that every figure adds
  up still compared that list with the 5xx of every group, ours included. A day where your own
  server or monitor got a 5xx no longer added up and was withheld (not shown, not mailed). It
  showed on the public demo's build right after 2.45.4. Now each day stored also keeps how many
  of your own 5xx were left out (counts kind `server_error_ours`), and the check is: by address
  = every 5xx minus those. Days stored before 2.45.4 kept yours in the list and left none out,
  so they, and any span that mixes old and new days (a month's mail, an export, a client
  report), still add up. The second count (`audit.py`) checks the new number against its own
  recount. Who it affects: installs on 2.45.4 whose own requests got a 5xx. What to do: nothing;
  a day withheld for this on 2.45.4 can be recounted while its log is kept (`skald backfill`).
  Checked: new tests (a day with your own 502 passes the check; a span of an old-style day and a
  new day adds up), the full test suite, the demo build.

## 2.45.4 (2026-11-09)

Server errors your own server makes no longer count against your site, and the to-dos people
met come first on Insights.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no nginx line, no setting. Add your own server's address or
  your monitor's user agent to your own list (Settings › Data › What counts › Ours) so its
  requests are known as yours.

### Changes

- **Your own traffic is no longer counted as a site's server errors.** A site's deploy smoke
  test, sent from its own server, made 137 of one site's 168 server errors (5xx) in ten days,
  and the "Fix the server errors" to-do counted them. Requests Skald classifies as yours (the
  addresses and user agents on your own list) are now left out of the server errors by
  address (`server_error_page`), so out of the to-do, its re-check and Site > Health's list,
  the same way they are never counted as traffic. The day's total "5xx to anyone" is
  unchanged. The second count (`audit.py`) follows the same rule. Stored days are not
  rewritten: on the live install only two older days had any (1 and 7), and their raw logs
  have rotated away. Who it affects: everyone whose own tools hit their site. What to do: add
  your server's address or your monitor's user agent to your own list. Checked: new tests
  (an own 502 is counted under ours, not by address), the full test suite.
- **To-dos people met come first.** Insights' "To do now" was ordered by the kind of
  problem, so server errors that only bots met were placed above a page where 95% of visits
  left. Now what people met (lost pages people asked for, server errors people got, a page
  people leave) comes first, then what only machines met. A server-errors to-do no person met
  says **Bots only** (amber), not **Broken** (red). What to do: nothing. Checked: new tests
  of the order and the label.

## 2.45.3 (2026-11-06)

A booking from Calendly or Cal.com that carries only the visitor ID now shows the pages its
visitor read before booking.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no nginx line, no setting.

### A visitor ID in `utm_content` is no campaign tag

- **What:** a Calendly or Cal.com booking that carries only the visitor ID now gets its source,
  first source and landing page from that visitor's pages (marked filled by Skald), and its lead
  drawer shows each page in order, ending in "Booked a demo". A real `utm_content` (a campaign's
  own) is kept as before.
- **Why:** the script tag puts the visitor ID in `utm_content` of Calendly embeds and links, and
  Skald read it as the booking's own campaign tag. The booking was stored as "Direct or unknown"
  and never filled from its journey. Found while building the booking journey a customer asked for.
- **Who:** sites with visitor IDs on and a Calendly or Cal.com webhook. No site has visitor IDs
  on yet, so no stored booking is affected.
- **What to do:** nothing. To see a booking's pages, turn on visitor IDs (Settings › This site ›
  Data › Script tag & goals; the privacy notice must say so). Bookings made before that have no
  journey.
- **Checked:** new adapter and fill tests (the second count agrees), the full test suite, and a
  local run with signed Calendly bookings: with only the ID, the drawer shows each page then
  "Booked a demo"; without an ID, "None linked"; with the booking's own UTM tags, those are kept.

### Housekeeping

- A few code comments that name old commits were updated after the project's private history
  was rewritten (new commit IDs). No change in behaviour; nothing to do. Checked: the full test
  suite.
- A test of the log installer (`tests/test_kit_server.py`) built its sealed tool folder with
  `exists()`, which says no for a broken link, so a machine with a broken link in both `/bin` and
  `/usr/bin` (GitHub's Ubuntu runner, `grub-ntldr-img`) failed the test before it began. It now
  checks the link itself. Test only; nothing to do. Checked: the full test suite.

## 2.45.2 (2026-10-31)

The morning run no longer reports "failed" for two checks that were wrong, not the figures.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- Nothing else: no schema change, no nginx line. The next Search Console sync marks the last
  days provisional again by itself.

### Held webhook deliveries on a keep-everything site no longer fail the morning run

- **What:** the second count of held webhook deliveries (`audit_hooks_held.py`) now follows the
  keep-everything rule, as the hold itself does: on such a site nothing is deleted by age, so a
  held delivery older than 24 hours is no finding; more than 2,000 held for one hook is.
- **Why:** on 31 Oct the morning run failed and mailed "Daily run failed": one site's 22
  held Calendly deliveries (28 to 29 Oct, signed with an old key) were kept, as the rule says,
  and the check expected them gone after 24 hours.
- **Who:** sites that keep everything and have held deliveries.
- **What to do:** nothing.
- **Checked:** a test holds deliveries on a keep-everything site two days, finds them kept and
  the check quiet, the 2,000 cap reported, and the 24-hour finding back with the rule off.

### A Search Console day is final only once it is 3 days old

- **What:** a day counts as final (Google will not change it) only before Google's first
  incomplete date and at least 3 days old. Younger days are provisional and fetched again.
- **Why:** on 31 Oct Google named no incomplete date, so 30 Oct was stored as final; the
  morning check asked Google for 30 Oct's final figures, got 0 / 0, and failed the run
  (docomatic.ai 1 click, 48 impressions; another site 97 clicks). Google's final figures come 2
  to 3 days after a day ends. The stored figures were Google's own; only the label was early.
- **Who:** every site with Search Console.
- **What to do:** nothing; the next sync relabels the last days.
- **Checked:** sync tests, among them the 31 Oct case (no incomplete date: yesterday and the
  day before stay provisional).

## 2.45.1 (2026-10-31)

A POST your site refused no longer counts as "sent a form", and an audit of a day whose log is
gone no longer hides that day.

### Upgrade

- **Back up first** (`docker exec skald skald backup`).
- **Recount the past days** again, as for 2.45.0: `docker exec skald skald backfill --days 14
  --force` (more where the raw log is kept longer). A day not recounted says it was counted the
  old way, as before.
- Nothing else: no new nginx line, no schema change.

### "Sent a form" leaves out POSTs the site refused

- **What:** a POST answered 301, 307, 308, 404, 405, 410, 444 or 501 (nothing at that address
  took it) no longer marks a visit "sent a form", and is left out of Form posts and a page's
  "posts from". A form that was taken (2xx, 302, 303), failed on the server (5xx) or was turned
  back with a reason (400, 403, 422, 429) still counts. Site › Requests names such a request
  "a POST the site refused (not a form)" (new kind `refused_post`). Days counted with the 2.45.0
  rule say they were counted the old way until recounted.
- **Why:** after 2.45.0's recount, docomatic.ai's 24 Oct still had 18 of 34 visits "sent a
  form". Read from the raw log, every one was a scanner posting to `/`, `/api`, `/app`,
  `/graphql`, `/v1/graphql` or `/xmlrpc.php` and getting 301, 404, 405 or 444 back. Not one of
  that day's browser POSTs was answered 2xx.
- **Who:** every site; most of all sites that scanners probe.
- **What to do:** the recount above.
- **Checked:** tests on both roads (each refused answer, each answer that still counts, a
  scanner's visit, the Requests kind; collect and audit agree on a day with a refused POST);
  the 24 Oct raw log grouped per visitor by path and answer, by Skald's own parser.

### An audit of a day with no log lines leaves the day alone

- **What:** `audit --day D` on a day whose raw log lines are gone (rotated away) now says "no
  log lines in this day's window; nothing to compare" and exits 2. Before, it compared history
  with a recount of nothing, reported a mismatch and, with `--withhold`, withheld the day.
- **Why:** 2.45.0's recount audited 13 and 14 Oct with `--withhold` on three sites whose raw
  lines for those days had rotated away, so six good days were withheld. They were put
  back the same hour from the backup taken before the upgrade (state and audit note as they
  were), written in the deploy history.
- **Who:** anyone running day audits over old days. The daily run audits yesterday, whose log is
  there, and was never affected.
- **What to do:** nothing.
- **Checked:** a test collects a day, audits it against an empty log with `--withhold`, and
  finds the day still verified with no problems.

## 2.45.0 (2026-10-30)

"Sent a form" means a form again, and a lead's visits fill in from its visitor ID. **Not
forms:** a POST a page's own script sends by itself (an event beacon such as `/api/events`, or
any POST answered 204 with nothing in it) no longer marks a visit "sent a form"; a site's own
list of such paths is in Settings › Data › What counts › Not forms, with suggestions from the
log; past days are recounted from the raw logs where they are kept. **Leads:** a lead sent with
a visitor ID and no touches gets its first and last touch from that browser's page views, marked
"filled by Skald", with a second count of its own; **ad click IDs** can be kept on leads (off by
default). **Compare:** Skald next to Hyros on the website and in the comparison.

### Upgrade

- **Back up first** (`docker exec skald skald backup`, and a copy of `conversions.sqlite`): the
  leads file moves to schema 10 on the first start (columns added, no row changed). 2.44.1
  refuses a schema-10 file, so going back means restoring that copy.
- **Recount the past days** so "sent a form" follows the new rule: `docker exec skald skald
  backfill --days 14 --force` (more days where the raw log is kept longer), then the audits
  (`docs/plans/not-forms-recount.md`). A day whose raw log is gone keeps its old count and says so.
- Nothing else: no new nginx line. Click IDs stay off until turned on.

### A lead's first and last visit filled from its visitor ID; ad click IDs kept when you turn them on

- **What:** a lead sent with a visitor ID but no touches read "Unknown" everywhere, though Skald
  keeps that browser's page views. Now its first touch (the earliest page view at or before the
  lead: source, landing page, time) and last touch (the last visit's first page view: source,
  campaign) are filled from those page views, by visitor ID only (never an address), never from a
  page view after the lead, and never over a value the sender gave. Filled values say "filled by
  Skald" in the lead list and drawer. Script-tag leads get their landing visit's source, campaign
  and first touch time (the tag now sends `utm_medium` and `utm_campaign` with page views).
  **Ad click IDs**, a new setting, off by default (Settings › Data retention › Leads): with it on, a
  lead keeps its ad click ID (gclid, gbraid, wbraid, msclkid, fbclid, li_fat_id, ttclid, twclid),
  shown only to people allowed to see names, never in data files, MCP figures or webhooks; deleted
  with the lead, cleared with names and emails, and cleared at the next run when turned off.
- **Why:** buyers comparing Skald with ad attribution tools (Hyros) ask for touches on every lead
  and for click IDs; the gap report is `docs/marketing/GAP-HYROS-2026-10-30.md`.
- **Who:** every site that sends leads with a visitor ID. **What to do:** nothing; the first daily
  run fills older leads and recounts past days. Turn on click IDs only if you need them.
- **Checked:** `tests/test_conversions_fill.py` (43 tests: the fill rules, a second count in
  `audit_filled.py` that works the touches out on its own and withholds a day it disagrees with,
  the click ID setting), `tests/js/skald-snippet.mjs`, both full suites.

### Skald compared with Hyros

- **What:** a new website page, /compare/hyros/ (twelve questions side by side, each Hyros answer
  linked to its own page, read 30 Oct 2026; where each is the better choice; using both), the
  compare hub now lists 15 tools, and `docs/COMPARISON.md` has Hyros under "Also checked" with four
  attribution rows. Doc fixes found on the way (BEACON.md's one cookie, prices public since 26 Oct).
- **Why:** buyers weighing lead attribution ask about Hyros. **Who:** website readers.
  **What to do:** nothing. **Checked:** the site build ("problems: none"), all 13 Hyros links answer.

### README: the 2.45 gallery, Not forms and "filled by Skald"

- **What:** two new README images, `not-forms.png` (Settings › Data › What counts › Not forms,
  one suggested path with Add and one saved path with Remove) and `lead-filled.png` (a lead's
  drawer whose first and last touch say "filled by Skald"), in a 2.45 gallery block; one line
  each in docs/FEATURES.md.
- **Why:** the GitHub page shows every new feature before the version is tagged.
- **Who:** readers of the public README. **What to do:** nothing.
- **Checked:** taken from the current build's demo (`tools/demo.py --now 2026-10-22T19:07:00Z`),
  light, 1440 wide at scale 2, cropped to the drawer; the helper's answers stubbed with sample
  data only (example.com, made-up people at example.org); the README tests and the public
  export check pass.

### A page's own script is no longer "sent a form"

- **What:** a POST no longer marks a visit "sent a form" when the page's own script sent it by
  itself: a POST answered 204 with no body (a beacon by definition: a real form gets a page or
  a redirect back), a path on a shared list of well-known beacons (`/api/events`, `/api/event`,
  `/api/analytics`, `/api/collect`, `/api/track`, `/api/sentry*`, `/monitoring`,
  `/_vercel/insights/*`, `/_vercel/speed-insights/*`, `/cdn-cgi/rum`, `/ingest/*`), or a path
  on the site's own new list, **Settings › Data › What counts › Not forms**. That card suggests
  a path when most page views send it (half the visits that sent a POST and a fifth of all
  visits, on 3 of the last 14 days, answered without an error), each with **Add**; it never
  adds one by itself. The doctor names a suggested path once. Site › Requests names a skipped
  one "sent by the page's own script (not a form)". The same rule applies to Site health's
  Form posts, the pages' posts, the POST times kept with a visit (lead matching by time), the
  visit list's "form sent" badge and filter, and Insights. `/contact`, `/api/contact` and
  WordPress's `admin-ajax.php` (unless answered 204) stay forms.
- **Why:** on docomatic.ai most visits read "sent a form" (29 of 34 on 24 Oct, 18 of 28 on
  27 Oct). Each page view sends `POST /api/events` to the site's own server four seconds
  after it opens, answered 204 with no body; the visitor did nothing.
- **Who:** every site; docomatic.ai most. Real form posts are counted as before.
- **What to do:** nothing. Past days are recounted from the raw log (`backfill --days 14
  --force`, docs/plans/not-forms-recount.md). A day older than the log (14 days) keeps its old
  count and says so: Site health › Form posts says how many days of the range were counted
  before, an older visit that posted says "counted before the page's own script was told from
  a form", and the doctor names the stored days still counted the old way.
- **Checked:** tests for `/api/events` 204 after a page (not a form), a real form POST (200
  and 303) still a form, the list, the 204 rule, the site's own list, the suggestion rule,
  the independent audit agreeing (it matches the lists by its own code), and the recount
  rebuilding the stored figures; the full suite, also without PyYAML.

## 2.44.1 (2026-10-28)

A webhook whose key does not match no longer loses its events, and the key's screen says the
truth. A refused delivery now says why: the tool sent no signature (its webhook was made
without a key) or signed with another key. Refused deliveries are held (24 hours on a client
site; until taken in on a site that keeps everything), and saving the right key takes them in
with their own times. Each tool uses its own word for its key (Calendly "signing key"), asks
first how its webhook was made, keeps the saved state on screen ("Signing key saved … by …"),
and **Test Skald's address** says it checks Skald's side only, beside the last real delivery.
A tool shows Connected only after a real delivery was accepted since the key was saved.

### Upgrade

- Nothing is required: no schema change, no new nginx line. Refused deliveries start being held
  from the upgrade on; ones refused before it cannot be taken in.
- A webhook made without a signing key (Calendly with a personal access token and no
  `signing_key`) must be made again with Skald's key: the tool's details give the requests.

### A webhook key that does not match no longer loses the events: refused deliveries are held

- **Keep everything:** on a site that keeps everything (internal and enterprise) the held
  deliveries are never deleted by age or count; they wait for the right key or a person's
  deletion request. Past 2,000 a hook no more are held. Client sites hold them 24 hours.
- **What:** a hook delivery refused for its key now says which way it failed: `unsigned` (the
  tool sent no signature at all: its webhook was made without a key) or `bad_signature` (it
  signed with another key), in the tool's own word for its key (Calendly "signing key", Stripe
  "signing secret", HubSpot "client secret", the others "secret"), with the fix for each. Either
  is held for 24 hours (raw, 0600, at most 200 a hook; never a test of Skald's own). When someone
  then pastes, makes or rotates the hook's key in Settings › Leads & tools, Skald checks every
  held delivery with it and takes in the ones that match, with the time each first came (logged
  `accepted_held`, counted like any accepted delivery); the answer says how many were held,
  matched and taken. Each tool now says when its key was saved, by whom and how, the last real
  delivery, and what arrived since. **Test Skald's address** says it proves the address only, and the
  set-up check turns good only after a real event was accepted since the key was saved.
- **Why:** a site's Calendly sent eight real bookings that Skald refused (the pasted key was not
  the one Calendly signed with), while all five of Skald's own tests passed: a test is signed with
  the key Skald has and posted to itself, so it can only prove the address. Calendly does not
  send a refused booking again, so no booking was kept. Calendly's signing key is optional with a
  personal access token and never shown again; a subscription made without one can only be made
  again with Skald's key, and Skald now says so.
- **Who:** every site with an incoming hook (Calendly, Cal.com, Stripe, Typeform, HubSpot, a lead
  or json sender). **What to do:** nothing. A hook whose deliveries were refused before the
  upgrade stays refused until its key is fixed; only refusals from the upgrade on are held.
- **Privacy:** held bodies are never logged, backed up or shown; `ti.py forget --email/--vid/--lead`
  deletes the ones holding that value, and clearing a site's data deletes its folder. Documented in
  docs/DATA-CONTRACT-CONVERSIONS.md ("Refused deliveries held").
- **Checked:** new tests (tests/test_hooks_held.py): unsigned and bad signature for every tool;
  hold, cap and the 24-hour purge; the right key takes the held deliveries in with their times and
  only once, a wrong key leaves them held, a test is never held; the deletion request; the tools
  list fields; the set-up check good only after a real accepted delivery; the audit's own road
  (audit_hooks_held.py: accepted_held in the delivery log against the spool's held lines, a held
  file past 24 hours, a held body with no refusal row). Full suite, also with PyYAML hidden.

### A tool's key in the tool's own word, kept on screen, and a Test that says what it proves

- **What:** a tool's details on Settings › Leads & tools and the Connect your leads dialog now call
  the key by the tool's own name (Calendly's **signing key**, Stripe's **signing secret**,
  HubSpot's **client secret**, **secret** for the others) and say once which way it goes ("Skald
  gives Calendly a signing key; Calendly signs each booking with it"). Calendly, Cal.com and
  Typeform ask one question first ("How was your Calendly webhook made?": not made yet, made
  with a `signing_key`, made without one or not sure), kept in the address as `how=`; a Calendly
  webhook made without a signing key gets the two requests that delete it and make it again with
  Skald's key, and **Let your AI agent do it**. After Save or Make the details stay open on
  "Signing key saved 28 Oct 10:16 by Ann (pasted)", with **Replace**, and the paste's answer in
  plain words: it matches (and how many held bookings were taken in), it is not the key the tool
  signs with, the tool sends no signature, or saved and waiting for the next one. **Send a test
  event** is now **Test Skald's address** and says it proves the address only, beside the last
  real delivery. A live line on top of the details says whether real deliveries work, with the
  next step under it. A row says Connected only after a real delivery was taken in since its key
  was saved, never on a passed test alone (a passed test alone now reads Waiting, not Ready).
  The help guides (Webhooks, Leads and conversions, If a connection does not work, Connections,
  Demo bookings) and the agent's lead job say the same, and no longer claim Calendly has no screen
  for webhooks.
- **Why:** on a site's Calendly the page said "secret" where Calendly says "signing key"; once
  saved, nothing on screen said a key was saved; Skald's own test passed (it signs its own sample
  with the key it holds) while every real booking was refused, so the hook looked fine and failed
  at once.
- **Who:** owners and admins connecting Calendly, Cal.com, Typeform, Stripe, HubSpot, their site's
  server, Zapier, Make or n8n. **What to do:** nothing. A Calendly webhook made without a signing
  key must be made again; its details say so.
- **Checked:** `tests/js/hook-key.mjs` (each state with stubbed helper answers: not made yet, saved
  and no match, matches and taken in, unsigned, an older server's answer; the set-up dialog's
  steps), `tests/js/setup-checklist.mjs`, `tests/js/set-leads.mjs`; both test suites (with and
  without PyYAML); the public sweep; screenshots of the Calendly details in each state
  (`docs/plans/hook-key-shots/`, sample data only). Needs the server side (`key_word`, `saved_at`,
  `since_saved`, `last_real`, `check`) for the times and answers; an older server shows none of
  them.

## 2.44.0 (2026-10-28)

Set-ups that say by themselves whether they worked, and leads with their country. **Live status:**
every connect journey (an agent line, an install command, a hook address, a share page, Search
Console) checks itself while it is open, has a **Test** beside it, and says in plain words when
something failed; Your tools no longer says "Connected" before a tool has answered. **Search
Console connects by itself** once Google shows Skald's robot, on whichever property (Domain or
URL-prefix) the robot can see, and Traffic › Search fills in as Google's history arrives, with no
reload. **Shorter set-up steps:** one status line, the next thing to do under it, the details and
the safety list folded. **Lead countries:** Skald's lead files (PHP, Node, Python, WordPress 1.1.0)
send the visitor's address, Skald looks up the country and drops the address; a warning shows when
the last three leads came without one. **MCP:** a new "Add sites (AI agent)" token lets an agent
add a site, follow it and send the invites, within the plan's site and member limits. **Welcome:**
a new person's first sign-in says whose sites they see and where to start. Docs, help and
screenshots are brought up to date, and Leads & tools no longer says "All connected" over a red line.

### Upgrade

- Nothing is required: no schema change, no new nginx line, no new setting.
- **Lead countries:** if your site sends leads with one of Skald's lead files, download it again
  (Settings › Leads & tools) or add the visitor's address as `ip` to your own call; leads sent
  without it keep "Country not recorded". The WordPress plugin is 1.1.0.
- Search Console: a site whose robot was added but never connected connects by itself within a
  minute of the upgrade (Skald checks every minute for 7 days after a set-up).

### Check again's "In the log since" time follows the check, not the wall clock

- **What:** the log line under a Check again result writes the mark's time alone when it is on
  the check's own day, and "27 Oct 14:10" when it is on another day. It compared with the
  server's wall clock instead of the check's time, so near midnight the day could be wrong.
- **Why:** found by the 2.44 public test run, which crossed midnight UTC and failed one test.
- **Who:** anyone using Check again near midnight. **What to do:** nothing.
- **Checked:** `tests/test_todo_check.py`, also run with the clock set two days later.

### Leads & tools no longer says "All connected" over a red line

- **What:** when every tool that fits is connected but a check needs a fix (for example the
  lead-country warning), the Next step card now says **1 to fix** and "everything that fits is
  connected, but one thing needs a fix: see below", not a green **All connected**. The red line's
  word is **Needs a fix** (was **Broken**), and its name reads "Lead countries: Your site's server"
  (was "Lead countries (Your site's server (lead))").
- **Why:** found while checking the 2.44 screenshots: the page said all was well and broken at once.
- **Who:** owners and admins on Settings › Leads & tools. **What to do:** nothing.
- **Checked:** `tests/js/set-leads.mjs` (all connected with nothing to fix stays green; with one
  red line it says 1 to fix), the doctor and lead-country tests, a fresh screenshot.

### Screenshots of the signed-in screens retaken, and the 2.44 gallery

- **What:** the README and website screenshots the static demo cannot draw, because they need a
  signed-in Skald, are retaken from the current build: Leads & tools (and its status crop), Data,
  People, Add a site's two steps, the set-up dialogs (Who will do it?, Finish set-up's line, the
  one command), Privacy's address choice and notice wording, the logo, and the three person
  searches; on the website, the client report preview (`reports-preview*.webp`, on about 163
  pages) and the tracking profiles (`ai-answers-profiles*.webp`, now 1200 × 327). Same names,
  sizes and crops where the screen allows; alt texts carry the new figures. The README gets a
  2.44 gallery (set-up lines with their Test, the short Watch it work, Search Console syncing by
  itself, the Add sites token, the lead-country warning, the welcome line), a 2.44 line in
  What's new, and FEATURES.md the 2.44 lines. Site rebuilt.
- **Why:** the 2.43 sweep left them showing screens from before 2.43 (Leads & tools before its
  rebuild, the old Reports page, profile cards with five buttons each).
- **Who:** readers of the GitHub page and the website. **What to do:** nothing.
- **How it was made and checked:** the demo build (`tools/demo.py --now 2026-10-22T19:07:00Z
  --keep`) served to a browser with the real helper behind it, in sessions mode, on the kept
  install: made-up people at example.com, .org and .net, sample data only, every site fetch
  answered locally, one-time codes replaced by a sample before each picture. Both test suites OK
  (with and without PyYAML); public sweep 0 hits; every image the README and the website name
  exists.

### The "Is it safe to paste this into a chat?" list starts folded

- **What:** under every line for an AI agent, the seven-point safety list now starts folded, its
  title in view; one press opens it. It used to be open on a wide screen, pushing Next below the fold.
- **Why:** the owner (27 Oct) on the set-up dialogs: "so long, so much info"; help belongs behind a press.
- **Who:** everyone who opens a set-up line. **What to do:** nothing.
- **Checked:** `tests/js/agent-setup.mjs` (folded, the same seven points), both suites.

### Every connect journey says by itself whether it worked, with a Test beside it

- **What:** wherever Skald gives someone something to do (a line for an AI agent, the install
  command, the set-up pack, the script tag, a "Share with your developer" page, a webhook
  address, a tool key, recorded journeys, a new API or MCP token), a pill and one plain sentence
  now say whether it arrived yet ("Waiting for your agent: it has not opened the line yet.",
  "Connected. The last delivery from Calendly came at 10:44"), and update by themselves: every
  5 seconds for 3 minutes, then every 30 seconds, never while the tab is hidden. A **Test**
  button beside it checks at once and says the next thing to do; the technical words are behind
  Details. Traffic › Search and the connect cards follow the live state and read their data
  again by themselves when it changes: no reload. People who only view re-read the page's file
  once a minute while a history is still syncing. New route POST `sites/arrived`
  (docs/DATA-CONTRACT-CONNECT.md).
- **Why:** the owner (27 Oct), on docomatic.ai's Traffic › Search: it kept saying "Search
  Console is not connected yet" while it was connected and its history was syncing, because the
  page decided from its file read once. "Status does not get updated, and it's very confusing
  ... wherever you have a command, 'copy this and give it to Claude Code', there should be a
  test button." The full list of journeys and what each one does now:
  docs/plans/connect-journeys-audit.md.
- **Who:** owners and admins setting anything up; viewers of Traffic › Search while it syncs.
- **What to do:** nothing.
- **Checked:** `tests/test_connect_check.py` (every kind of `what`, the words, a viewer
  refused, an unknown kind, the limit per hour), `tests/js/live.mjs` (the poller, the redraw, the
  Test button, Traffic › Search turning connected and syncing without a reload),
  `tests/js/setup-checklist.mjs`, both suites (with and without PyYAML).

### Search Console connects by itself, and the agent's watch fits on one screen

- **What:** when an AI agent reports a Search Console property, or someone presses Connect or
  Check now, Skald asks Google which properties its robot can see and connects the one that
  covers the site. If the robot is on another property than the one named, Skald uses it and
  says so in one line. If Google shows none yet, the page says "Waiting for Google: Skald's
  robot address is not on a <site> property yet. Google can take a few minutes. Last checked
  17:56." with Check now, and Skald keeps checking by itself (at most once a minute, for 7 days),
  then connects and starts the 16-month history. The agent's report gets the same answer, so
  the agent tells the person what Skald sees; the agent's steps no longer send anyone to
  Settings to press Connect. Step 3 of every agent line ("Watch it work") now has one status
  line on top, the next action right under it (Apply, Check now), the ticks folded once done,
  and the keys, Cancel and the agent's full report behind Details. A failed connect shows on the
  open page in plain words, not only by mail.
- **Why:** the owner (27 Oct), on one of his sites: the agent reported the domain property and
  sent him to Settings to connect; at the foot of a long step 3 he pressed Apply, Google refused
  because the robot was on the site's URL-prefix property instead, the connection went
  failed and the open page did not say so.
- **Who:** anyone connecting Search Console, by hand or with an AI agent.
- **What to do:** nothing. A site waiting for Google connects by itself once the robot address
  is on its property.
- **Checked:** `tests/test_search_auto.py` (the property the robot sees is used and said, none
  visible waits then connects by itself, Check now, gives up after a week, the agent's report
  answer), `tests/js/agent-jobs.mjs`, `tests/js/agent-setup.mjs`, `tests/js/live.mjs` (the
  watch's top line, Traffic › Search waiting for Google), both suites.

### Docs, screenshots and website brought up to 2.43

- **What:** the marketing site's dashboard screenshots (`/img/*.webp`, same names and sizes)
  and 45 README screenshots, the README hero (light and dark) and the GitHub social card are
  retaken from the 2.43 demo (sample data for example.com only). The Security story page's
  numbered hotspots moved to match. The help guides and technical docs, the website's feature,
  docs, compare and pricing pages, and the alt texts now describe the 2.42 screens and the 2.43
  features (your tools, organisations, Add a site's questions and live progress, connect cards,
  Check again, Search Console reports, recorded journeys, AI reads). Detailed GitHub release
  notes for v2.43.0 and corrected links for v2.38.0 to v2.42.0 are written in
  `docs/plans/release-notes/`, to publish by hand.
- **Why:** the owner asked for every document, release note and screenshot to match the live
  2.43.0 (27 Oct). The website still showed the 2.13 screens; the README showed the top bar
  from before its seven controls; the GitHub release notes' "Full release notes" links pointed
  at sections that moved into `docs/`.
- **Who:** readers of skaldanalytics.com, the GitHub page and the in-app Help. Nobody running
  Skald.
- **What to do:** nothing.
- **Checked:** both test suites (with and without PyYAML), `tools/build-about.py --check`,
  `tools/cli-reference.py --check`, the site build ("problems: none"), every sitemap page
  answering 200 from a local server, image pages seen at 1440 and 390 px, the public export
  check.

### Leads from your own server get their country: the lead files send the visitor's address

- **What:** the lead files (`skald-lead.php`, `skald-lead.cjs`, `skald_lead.py` and the
  WordPress plugin, now 1.1.0) send the visitor's address as `ip`. Skald looks the country up
  and drops the address at once, as it already did for an `ip` it was sent. PHP and WordPress
  read it by themselves (`REMOTE_ADDR`; behind a proxy on the same server, `X-Real-IP` or the
  first `X-Forwarded-For` entry; behind a CDN, the header named in `SKALD_LEAD_IP_HEADER`).
  Node and Python take `ip` from the caller; their README shows the line for Next.js on Vercel,
  Express, Flask, Django and FastAPI, and which header to trust on which host. Every file sends
  `ip` only when it is an IPv4 or IPv6 address; Skald reads a header's list as its first
  address. `vid` and `ip` work together: `vid` joins the lead to the pages read, `ip` gives the
  country, and a lead's country never comes from its visitor ID. When each of a site's last 3
  leads from its server came without a country, Skald says so with the fix: Settings › Leads &
  tools › Status ("Lead countries", also in `doctor`) and the set-up checklist's lead line,
  whose Set up gives the AI agent's `lead` job. The agent's job now passes the address and
  checks its test lead: the signed `GET .../leads` says `country_recorded` (true or false, never
  the country). A lead whose `ip` gave no country (a proxy's private address) says why in the
  answer and the delivery log.
- **Why:** on a site on Vercel with no script tag, Overview › Summary's "What converted today"
  showed "Country not recorded" for every lead, while its visits all had countries. Its leads
  came from its own server with neither a visitor ID nor the visitor's address, and none of the
  files Skald gives sites sent the address. The owner (27 Oct): "it should never happen".
- **Who:** every site that sends leads from its own server (the lead files, the WordPress
  plugin, or its own code on the `lead` or `json` hook). Sites whose leads come from the script
  tag's forms already had a country.
- **What to do:** sites that send leads from their own server download the lead file again
  (Settings › Leads & tools) or re-run the AI agent's `lead` job; Node and Python callers add
  `ip` as the README says. Leads already kept stay as they are: Skald never guesses their
  country afterwards (no matching by time to the log).
- **Checked:** `tests/test_lead_country.py` (the hook with `ip`, a list, a port, with and
  without `vid`, visitor IDs off, a private address, no country file, the address never on disk;
  the warning's states; the doctor's and the checklist's lines; the read-back; the Node file
  in node and the PHP file and WordPress plugin in php, posting to a stand-in Skald), the
  checklist's page-and-server parity case, both suites.

### An AI agent can add a site over MCP, within the plan

- **What:** four MCP tools and one token scope. `add_site` adds a site to the token's own
  organisation, with the people who will use it, and answers its page and the one-time set-up
  line for an AI agent; `site_progress` shows the live set-up step by step; `check_site` is
  Check now; `send_invites` mails the people before the first data. The scope **Add sites (AI
  agent)** (`add_sites`) is for the whole organisation, only with AI assistant (MCP), made by an
  owner or admin who sees every site, in Settings › AI & API › New token. The MCP server now has
  29 tools. The dashboard's Add a site and Who will use it now also check the plan's members for
  the new people they name (open invites included).
- **Why:** the owner (27 Oct): "yes, and depending on plan etc they are". Saying to Claude "add
  shop.example.com to Skald, invite these two people as viewers, and tell me when data arrives"
  needed the dashboard before.
- **Who:** owners and admins who connect an AI agent. Plans hold over MCP as in the dashboard: the
  plan's sites and members refuse in one sentence with what to do, a read-only organisation adds
  nothing, an organisation with no plan has no limit, a hosted site waits for its domain to be
  verified. A new organisation is never made over MCP. Each site added and each invite sent is in
  the audit log (`mcp.add_site`, `mcp.send_invites`), never a code, token or address.
- **What to do:** nothing. To use it, make a token with Add sites (AI agent) and connect your
  agent with it.
- **Checked:** `tests/test_mcp_add_site.py` (the scope's rules, the shared code path, the plan's
  sites and members with the dashboard's own words, read-only, no plan no limit, wrong scope,
  revoked and demoted makers, another organisation's site, the same answers as sites/live and
  sites/check, Check now per token, the audit rows), `tests/js/set-account.mjs` (the token
  maker), both suites.

### A short welcome on a new person's first load

- **What:** the first time a new person opens the dashboard, one line over the page says
  "Welcome to Skald, <first name>. You see <organisation>'s sites. Start with Overview." with
  links to Overview and Help, and a × to close it. It stays across reloads in that tab until
  closed, and never comes back.
- **Why:** the owner asked for a short welcome on first sign-in (27 Oct), for people invited to
  a new organisation of its own.
- **Who:** only accounts made from this release on. Everyone who has an account already never
  sees it.
- **What to do:** nothing.
- **Checked:** `tests/test_welcome.py` (once, then never; a second sign-in; an account from
  before; each person their own; the words), both suites; seen in the demo at 1440 px.

## Older versions

- 2.43.0 (27 October 2026): [docs/CHANGELOG-2.43.md](docs/CHANGELOG-2.43.md).
- 2.42.0 (26 October 2026): [docs/CHANGELOG-2.42.md](docs/CHANGELOG-2.42.md).
- Website changes, 24 to 27 October 2026: [docs/CHANGELOG-website-2026-10.md](docs/CHANGELOG-website-2026-10.md).
- 2.39.0 to 2.41.0 (26 October 2026): [docs/CHANGELOG-2.39-2.41.md](docs/CHANGELOG-2.39-2.41.md).
- 2.36.0 to 2.38.0 (25 and 26 October 2026): [docs/CHANGELOG-2.36-2.38.md](docs/CHANGELOG-2.36-2.38.md).
- 2.35.0 and 2.35.1 (25 October 2026): [docs/CHANGELOG-2.35.md](docs/CHANGELOG-2.35.md).
- 2.32.0 to 2.34.1 (24 and 25 October 2026): [docs/CHANGELOG-2.32-2.34.md](docs/CHANGELOG-2.32-2.34.md).
- 2.27.0 to 2.31.1 (22 to 24 October 2026): [docs/CHANGELOG-2.27-2.31.md](docs/CHANGELOG-2.27-2.31.md).
- 2.23.0 to 2.26.0 (22 October 2026): [docs/CHANGELOG-2.23-2.26.md](docs/CHANGELOG-2.23-2.26.md).
- 2.21.0 to 2.22.3 (21 and 22 October 2026): [docs/CHANGELOG-2.21-2.22.md](docs/CHANGELOG-2.21-2.22.md).
- 2.14.0 to 2.20.1 (18 to 21 October 2026): [docs/CHANGELOG-2.14-2.20.md](docs/CHANGELOG-2.14-2.20.md).
- 2.8.0 to 2.13.0 (18 October 2026): [docs/CHANGELOG-2.8-2.13.md](docs/CHANGELOG-2.8-2.13.md).
- 2.7.1 and earlier (8 to 12 October 2026): [docs/CHANGELOG-2.0-2.7.md](docs/CHANGELOG-2.0-2.7.md).
