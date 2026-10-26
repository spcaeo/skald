# Changelog: 2.35.0 and 2.35.1

The releases of 25 October 2026. Newer ones: [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.32-2.34.md](CHANGELOG-2.32-2.34.md).

## 2.35.1 (2026-10-25)

A fix found by the recount after the 2.35.0 deploy.

### Security: tied attack rows keep one order on both counts

- **Fixed.** Security > Attacks lists each attack try by its requests, first time, kind and
  address number. Two tries from addresses without a number, in the same second and of the same
  kind, differed only in their answer (one 3xx, one 4xx), and the stored day and the second
  count put them in opposite orders. **Effect:** the audit after the 2.35.0 recount found 4 of
  32,710 figures out of order on one site's 24 Oct and withheld that day, so its figures were
  not shown. **Now:** both counts break the tie by the last time and the answers. **Who:** any
  site with such tries; only the order of two rows changes, no figure. **Do:** nothing; the
  withheld day is counted again after the upgrade. **Checked:** `tests/test_security_tie.py`
  (fails before the fix: both orders seen, both counts, one result); the stored day read on
  the live server (rows 79 and 80: no number, traversal, 1 request, 19:37:14, 3xx and 4xx).

## 2.35.0 (2026-10-25)

Is it working, and what to fix next. Overview › Summary answers "what changed" against the
period before, with exact dates, "Include today" and the pages people landed on; Traffic › Pages
sorts by Rising and Falling and shows when each page last changed (from the sitemap). Insights
becomes a to-do list that re-checks each fix, and a page you changed shows whether the change
worked; Site › Not found lists old addresses still asked for, with the closest live page and the
server line to copy; each page gets an AI readiness block. Also a trail with Back over every
tab, a dry run for a new log source, a copy icon on every value, and counting fixes: bots that
looked like people, scanners using a crawler's name, machine addresses counted as pages, and
crawler address checks that were off in Docker.

### Upgrade: recount the stored days

- Figures from the live install below name its client sites example.com, example.org, example.net
  and site.example.
- Several counting rules changed (the Counting entries below). Stored days keep their old figures
  until they are counted again from the raw logs: after the upgrade, run
  `skald backfill --days 14 --force` for each site (`--days` up to the logs still held), then
  `skald audit`. Days whose raw log is gone keep their old figures. Crawler address checks start
  with the next daily run (it fetches the owners' lists first); a second recount after that run
  files the fakes among the past days too.

### Summary and Pages: is it working? (release 2 screens)

- **Added: the period line.** On Overview › Summary and Traffic › Pages, under the title: two
  switches, **Include today** and **Compare with the period before**, and one line with the
  exact dates. On 15 Jan, "Last 7 days" with today is 9-15 Jan against 2-8 Jan; whole days
  only, 8-14 Jan against 1-7 Jan. When the earlier period was not counted (the site was not
  measured yet) it says "before: not measured", never a 0 and never a rise. Both switches are
  in the address (`inc=1`, `cmp=prev`), so Back and Forward work. While today is included,
  Compare does not compare (today is not complete) and says why.
- **Changed: the key figures.** Summary's tiles are five now: People, From search engines,
  Returning people, Leads, Sent by AI assistants. With Compare on, each says its change, as
  "▼ 40% · before: 125", or "≈ about the same" when the gap is 3 or fewer. The whole tile opens
  its tab. The old trend lines under the tiles are gone (the chart below has them).
- **Added: "What changed: is it working?"** Sources and Landing pages, each Now, Before and
  Change, and one sentence with the biggest rise and drop. Off, it offers to switch Compare on.
- **Added: "Work on the page, or on traffic?"** Pages with many visits where most people left
  at once and no form was sent (improve the page), and pages search finds where most still
  leave at once (work on both the page and its traffic). "Left at once" means the visit loaded that one page and nothing else; the card and the help say
  so. The thresholds are in one place (`page-figs.js` `WORK`) with why each is what it is.
- **Added: "New and updated pages: are they getting found?"** The pages changed in the last
  30 days (the website's date, else the sitemap's "last changed"), their visits and search
  visits since, the first search visit, and whether Google fetched them. When most sitemap
  dates fall on one day the card says they look like build times.
- **Added: Traffic › Pages sorts and columns.** Sort chips: Most visits, Rising, Falling
  (these two need Compare and say so), Recently changed, Needs work (`psort` in the address).
  New columns: pages per visit, left at once, AI reads, changed. A "Changed in the last 30
  days" preset in the Filters panel opens Pages with `chgfrom` and the newest changes first.
- **Added: AI reads per page.** AI & bots › Assistants: per page, the assistants' live fetches
  now against the period before, by assistant, followed to AI visits and leads.
- **Demo:** the sample sitemap now has "last changed" dates, so the New and updated pages card
  has rows.
- **Why:** the owner asked for Summary and Pages to answer "is it working?": what changed
  against before, which pages need work, whether new pages get found. Before, the period's
  exact dates were not shown, today could not be added to a range, and Compare showed only on
  the chart.
- **Who:** everyone who opens Summary, Pages or Assistants. **Do:** nothing. The new cards need
  `page_trends.json` (next entry); until the first day is collected after the upgrade they say
  "not recorded yet".
- **Checked:** every figure is either one the app already showed (the range's totals, Compare's
  B totals, leads from conversions.json) or from `page_trends.json`, recounted by
  `audit_page_trends.py`. JS tests `tests/js/period.mjs` (the 15 Jan example both ways, the
  not-measured case, the address round trip and Back) and `tests/js/page-work.mjs` (tiles,
  cards, sorts, columns, copy and open icons on paths); the full suite; the demo at 1440 and
  390 wide, light and dark. Help: getting-started.md "Summary and Pages: is it working?";
  `docs/ROUTES.md` has `inc` and `psort`.

### Visits by landing page, and each page's trend by day (the figures behind the new Summary and Pages)

- **Added.** A new day figure, `landings`: per page a visit started on, the visits, those
  that loaded only that page ("left at once": one page view in the server's log), the page
  views they made, and the visits from search engines and from AI assistants (the top 200
  pages a day, the rest in one "(all others)" row). Verify holds every row and every sum to
  the day's own visits, one-page visits, page views and sources. A new data file,
  `page_trends.json`, puts each page's stored figures side by side by day: the landings, the
  assistants' live fetches (ChatGPT-User, Perplexity-User, Claude-User) by page and assistant,
  and the pages changed in the last 30 days with their visits and search visits since, the
  first search visit, and whether Googlebot fetched them since; plus a note when most sitemap
  dates fall on one day (they look like build times). Two new second counts: `audit_landings.py`
  recounts the landings from the raw lines with the audit's own labels, and
  `audit_page_trends.py` (run-daily's recounts) works every figure of the file out again with
  its own SQL. **Why:** the new Summary cards ("What changed", "Work on the page, or on
  traffic?", "New and updated pages") and the Pages sorts need per-page figures by day, which
  history did not keep. **Who:** every site; a view (page group) gets a "whole site only" note.
  **Do:** nothing; the figures start with the first day collected after the upgrade, and older
  days say "not recorded" until they are recounted. **Checked:** unit tests for both kinds and
  both audits, each catching a planted error; the full suite.

### Change dates from the sitemap's lastmod

- **Added.** The daily sitemap read now keeps each page's `<lastmod>` too: the date the site
  says the page last changed, normalised to the site's day (a date, or a date and time with a
  zone; values that are not a date, and dates in the future, are left out and counted). Each
  day's counts are in `sitemaps/days.json`, and each page's dates across days in the new
  `sitemaps/lastmod/history.json` (version 1, at most 20 dates per page). Traffic > Pages shows
  them: a **Changed** column marked "from your sitemap", a **Changed since** filter
  (`chgfrom=` in the address), and each change on the page story's timeline. `page_index.json`
  and the page story gain `updated_source`, `lastmod` and `lastmod_seen`; the website's own
  page list still wins for `updated`, and without it `published` stays the first day seen (a
  lastmod is a change date, not a publish date). A page only the sitemap lists now has a row.
  A new second count, `audit_lastmod.py` (run-daily's recounts), re-reads the stored files and
  checks every date shown. **Why:** without a page list from the website, Skald had no change
  date at all and dated pages by the first day its logs saw them, so every example.net page
  showed 21 Oct (the day Skald started), and "Pages by publish date" could not say which pages
  had changed. **Who:** every site with a sitemap; the path list Crawl health is judged by is
  built exactly as before. **Do:** nothing; dates start on the first sitemap read after the
  upgrade (the next local day). **Checked:** unit tests (sitemap index, gzip, odd and future
  dates, missing lastmod, the website's dates winning, the audit catching a nudged date and a
  rewritten file, the Pages tab); the new reading run over the eight live sites' public
  sitemaps on 2026-10-25 gave the same path lists as the server kept that day, and dated 115 of
  115 example.net pages, 69 changed since 13 Oct in the site's New York time (70 in UTC).

### AI readiness per page

- **Added: "AI readiness" in a page's story** (Traffic › Pages, select a page). Six lines, each
  **Good**, **Needs attention** or **Not known**, with one line of evidence and what to do:
  robots.txt (may each of the 9 main AI crawlers read this path: GPTBot, OAI-SearchBot,
  ChatGPT-User, ClaudeBot, Claude-User, PerplexityBot, Perplexity-User, Google-Extended,
  Applebot-Extended; the deciding rule and an `Allow:` snippet to copy), crawler errors (5xx,
  other 4xx, slow answers in the last 30 days; redirects named, not counted), in the sitemap
  (with its lastmod), the Markdown copy (did `page.md`, `page/index.md` or `page/.md` answer
  AI: "AI asked for the Markdown copy 19 times; it answered 404 each time"), AI asking for a
  404, and the last AI read with its trend (page_trends.json, not counted again). From the log
  and Skald's own copies of robots.txt and the sitemap only; no AI is asked anything.
  "Not known" when Skald has no copy of robots.txt or the sitemap, or for days before this
  release; never a guess, never a 0 it did not count. Names, status codes and robots.txt lines
  have copy; every path has copy and open. The address keeps it: `psec=ai`.
- **Added: "Pages AI can't read well"** on AI & bots › Assistants: every page where AI got an
  error, a 404 or a slow answer, asked for a Markdown copy that does not answer, or that
  robots.txt shuts them out of, worst first, with a filter (`arw`: Markdown copy, 404, Errors,
  robots.txt, Slow). A row opens the page's AI readiness. A crawler robots.txt keeps out of the
  whole site is said once, above the list. Only addresses shaped like a page count: files,
  feeds, APIs, sitemaps, image resizers and probes such as `/.env` are left out.
- **New figures:** the day kind `ai_status` (what AI got back by address and name; every answer
  but 200 and 304, every Markdown-copy request, slow answers; the rest by name only; at most
  1,000 addresses a day, the rest summed) and `ai_ready.json`
  ([docs/DATA-CONTRACT-AI-READY.md](DATA-CONTRACT-AI-READY.md)). robots.txt is read the
  RFC 9309 way (the longest rule wins, an Allow wins a tie), not Python's first-match
  robotparser.
- **Why:** the owner asked whether AI can read each page well, from the log alone. On example.net
  a WordPress plugin redirects AI assistants to each page's `.md` copy, and many of those copies
  answer 404: AI gets nothing for those pages, and no screen said so.
- **Who:** every site. **Do:** nothing. What AI got back is recorded from this release on; a
  recount or backfill of a day whose raw log is still kept fills it in. Views (page groups)
  show it for the whole site only.
- **Checked:** unit tests (`tests/test_ai_ready.py`: the day kind and its recount from the raw
  lines, a nudged figure caught, the folded tail, verify's sums, the file and its second count
  agreeing and catching changes, robots.txt not kept or a 404, no sitemap, a view, non-page
  addresses left out, a redirect alone not listed; 1,000 random robots.txt cases main against
  audit; `tests/test_ai_ready_js.py`: the lines, the block and the list drawn, and 600 random
  robots.txt cases JS against Python). Second counts: `audit_ai_status.py` (RECOUNTS, from the
  raw lines) and `audit_ai_ready.py` (DAILY: its own SQL, robots.txt reading, sitemap reading
  and page shape). A read-only run of this code on example.net's real log on the live server
  (2026-10-21 to 25, 70,938 lines): 394 to 573 addresses a day, 30 to 43 KB, none summed;
  robots.txt lets all 9 crawlers in; 115 sitemap pages; 475 pages listed, 437 of them for a
  Markdown copy that answered 404 or another error (top: `/healthcare-app-development/appointment-reminder-app-for-clinics/`,
  PerplexityBot got a 302 there 19 times and asked for its `.md` copy 19 times, which answered
  404 each time), while
  `/index.md` answered 200 to all 150 requests. The demo's robots.txt now keeps Google-Extended
  out of `/guides/`, and `/guides/webhooks.md` answers 404, so the block shows both.

### Insights: a to-do list. Not found: lost pages with the closest live page

- **Added.** Overview > Insights now starts with **To do now**: what to fix this week, worst
  leak first, above the "what changed" cards. Each to-do has its proof (a figure and its days),
  what to do, how Skald will check it, and the list behind it: **Show the list**, **Download
  CSV**, **Copy link** (the address keeps the to-do open: `todo=`), **Open in** its tab, **Mark
  done** and **Not now**. A done item is re-checked on every whole day after the mark with the
  same measure ("Fixed: 0 not-found answers since 25 Oct", or "Not yet: ..."). **Send to team**
  mails one to-do to a confirmed member of the site's team, with its rows as a CSV and the link,
  through Skald's own mail server; it shows only when there is one and a team, and the page says
  why otherwise. The kinds, each only past its threshold (one block, `todos.LIMITS`): old page
  addresses still asked for, server errors, AI asking for `.md` copies of live pages, a sitemap
  address crawlers ask for that is not there, and a page nearly every visit leaves at once with
  no form sent. New files `todos.json` and `lost_pages.json` (docs/DATA-CONTRACT-TODOS.md).
- **Added.** Site > Not found starts with **Old addresses still asked for**: the page addresses
  people, search engines and AI asked for in the last 30 whole days that now fail (scanner probes
  left out), most asked first, each with the closest live page Skald found (Same page, Same topic,
  Loose, or No good match) and the line to copy for nginx or Apache: a 301 redirect, or 410 gone.
  Tabs **Lost pages**, **AI asks for Markdown** and **After the fix** (`nfk=`; `nfsrv=apache`), a
  download of every suggested line, and **Mark fixed**, after which the address is counted on
  the days after the mark. Skald never changes the web server. Every path has copy and open, and
  every line to paste the copy icon (the owner's 2026-10-25 rule).
- **Why:** Insights said what changed but not what to do; and example.net, after moving from AI
  topics to healthcare, had 288 old addresses answering "not found" to people (257 times), search
  engines (228) and AI in four days, with nothing to show where each should go.
- **Who:** every site. Marks and Send to team need accounts (signing in); owners and admins mark
  and send, viewers see the list. Without accounts the list shows and says why nothing can be
  marked.
- **Do:** nothing. To send to-dos, set up Settings > Mail and invite the team.
- **Checked:** a second count for every figure (`audit_todos.py`, its own SQL, sharing only the
  name lists and thresholds; a to-do or list it disagrees with is withheld and named); unit tests
  for the matcher (exact, likely, guess, no match), the to-do builders and thresholds, the
  re-checks, the marks and the mail (`tests/test_todos.py`), and the page (`tests/js/todos.mjs`:
  the address keys, Copy link's tick, marks with and without accounts, Send to team, the lost
  pages' tabs and lines, the copy icons). Run read-only on the live history: example.net and
  example.com built in under a second, both counts agreeing; the matcher compared with the
  hand-made example.net redirect list.

### Did my change work? A tracker on each page. The trail and Back over every tab

- **Added: "Did my change work?"** On Traffic > Pages > a page, **+ Mark a change** records
  the day the page changed, what changed (content, title, a link to it, a redirect, other)
  and a short note. Skald then puts the same number of whole days before and after that day
  side by side, up to 28 on each side, the day itself in neither: visits that started on the
  page, leads and conversions that landed there, search engine visits, AI assistant visits,
  AI reads (live fetches) and the share who left at once, each with its change and a verdict
  (**Up**, **Down**, **No clear change** within 2 standard errors of the day-to-day swing,
  **Too few to tell**). Under 14 whole days it says **Too early to tell**, how many days it
  has and the day the verdict comes. A day not whole or not recorded is in neither side and
  says **not recorded**, never 0; when the sides then have different numbers of days the card
  says so and compares per day. When the sitemap or the website says the page changed on a
  day not yet marked, the page asks **Track that change?**. The change is a marker on every
  day chart; Overview > Insights lists every change under **Done, and did it work?**. The
  marks are rows in the to-do marks table (`todo_marks`, `page:/path/`, state `changed`, new
  `kind` and `note` columns; an older table is rebuilt in place, every row kept), read and
  written by the helper's `settings/todos`; the figures are `page_changes.json`
  (`page_changes.py`, docs/DATA-CONTRACT-PAGE-CHANGES.md). New address keys: `pchg` (one
  change open), `pcm`, `pcd`, `pck` (the dialog, its day and kind; the note never in the
  address). **Why:** the owner asked for a "did my change work?" tracker per page, from the
  mockups approved on 2026-10-25 (T8). **Who:** owners and admins mark and stop changes, with
  accounts; everyone on the site's team sees them; without accounts nothing is tracked and
  the page says why. **Do:** nothing; a change marked today shows its figures from the next
  data update.
- **Added: the trail and Back.** Over every tab, a line shows the path taken in this browser
  tab (Summary, a source, a page, a visitor): **← Back to** the step before, then each step as
  a link to its exact view (period, filters, sort, what was open), the current one with copy
  and open icons. Browser Back and Forward walk the same steps and put each page back where
  it was scrolled. A step already on the trail cuts the trail back to it; moving along a
  section's tabs does not add steps; at most 12 are kept. The trail lives in the tab's
  sessionStorage (never sent); a reload keeps it; a copied link opened fresh starts its own
  from the address (Traffic › Pages, then /pricing/). On a phone the line is Back and where
  you are. **Why:** the owner asked that a drill-down always shows the way back (T9). **Who:**
  everyone. **Do:** nothing.
- **Checked:** unit tests (`tests/test_page_changes.py`, 15: the windows, too early and
  waiting, a clear rise and a lower left-at-once share, unequal coverage and not-recorded
  days, the top-200 floor, leads from a real conversions store, the old marks table rebuilt,
  and the second count `audit_page_changes.py`, by its own SQL, catching a wrong figure, a
  wrong lead and a missing mark, the build then withholding the change); JS tests
  (`tests/js/pagechange.mjs`: the words, the dialog's address keys and request, Insights'
  list, copy and open on every path; `tests/js/crumbs.mjs`: the trail rules and a
  browser-like history with Back, Forward, a crumb, scroll put back, a reload and a fresh
  link); the demo seeds three changes (`tools/demo_changes.py`: two compared, one too early)
  and was checked in a browser, light and dark, at 1440 and 390 wide, Back and Forward
  putting the scroll back.

### A dry run for a new log source: `try-log` and Test a sample

- **Added.** `skald try-log <file>` (Docker: `docker exec skald skald try-log
  /var/lib/skald/ingest/<site>/access.log --site <site>`) reads the first 500 lines of a log
  (`--lines N`, plain or gzip, told apart by its bytes) and stores nothing. With `--format auto`
  it tries every reader and keeps the one that reads the most lines, with the count each
  reader read and how sure it is. It prints the lines read and not read, the main reasons with
  up to 3 line numbers each and the field that failed (never a raw line; IP addresses and
  emails in hosts and paths are masked), the first and last time and the time zone in the
  lines, the hosts and whether they are the site's, the five groups for the sample (they add
  up to the lines read: site requests + other hosts + unreadable + repeated request ids), the
  pages people viewed most, and warnings: an error log instead of an access log, no referrer
  (every source would be Direct), no user agent, no host name, a `www.` host missing from the
  site's hosts, a site set to another format, page assets that do not match, more than 1%
  unreadable. `--site` judges the lines with that site's settings; `--json` prints the report.
  Exit 0 readable, 1 a daily run would withhold the day, 2 the file cannot be opened. It runs
  without a config file too. Settings > Connections has **Test a sample** on the send card:
  up to 200 pasted lines (256 KB), the same report, owners and admins, 60 tests an hour
  (`POST <page>/sites/trylog`; the pasted lines are not kept and never go in the address:
  `conn=sample&step=` and `lfmt=` do). It reads with the daily run's own readers and counts
  with its own pipeline (`window.analyse_paths`) over a private temporary copy of the sample
  (`try_log.py`, `try_log_cli.py`, `webapp/js/tabs/conn-sample.js`). docs/INSTALL.md
  ("Try a log first") and the Connections help guide ("Test a sample of a log") say how.
  **Why:** someone adding a site or a new log source (a server's
  log, a CDN or host export) learned only after the next daily run, a day later, whether
  Skald could read it. **Who:** anyone adding a site or a log source; owners and admins in
  the dashboard. **Do:** nothing. **Checked:** unit tests (`tests/test_try_log.py`: each
  format's detection from its fixture, a chosen reader that does not fit, the reasons by line
  number with no address in the report, an error log, gzip by bytes, an empty file, a missing
  file, a folder, a broken gzip, a binary file, the groups adding up, a known site's settings,
  the count matching a daily run's read, the CLI with and without a config, the route and its
  refusals, the dialog drawn in node with its copy and open icons); read-only on the live
  server on 2026-10-25 with the code copied in, each site's own settings: the first 500 to
  3,000 lines of example.com, docomatic.ai and skaldanalytics.com (`nginx_extended`),
  freshlycited.com (`caddy_json`), example.net, example.org and site.example
  (`nginx_combined`): each format picked "sure", every line read, the groups added up on all
  seven, and the warnings named the real gaps (no host field on example.net and example.org,
  26 such lines on site.example); an nginx error log was named as one.

### Copy any value with one click, not only links

- **Added.** Every value someone may paste elsewhere now has the copy icon at its end, the
  same one links have (it turns into a green tick, then hides): IP addresses, user agents,
  emails, names, visitor IDs and references, search queries, referring sites, campaign and
  UTM values, crawlers and assistants, networks and hosts, reasons and error details, token
  names, robots.txt lines and the request, lead, visit and scanner drawers' facts. Tables and
  data grids add it by the column (its key, its name, or the value it drills into), bar lists
  and drawers through the same helper (`js/urlactions.js` `copyCell`, `copyIf`, `copyFact`);
  the old "Copy" text buttons beside an address (Site > Requests, the request drawer, the AI
  feed, Find a person) are replaced by it. An address, an email or a user agent copies its
  whole value, a drilled crawler its own name; a blank, "removed" or "(all others)" gets none.
  Also: the person search's request paths and a lead's page, a visit's referring page and
  last page, the site list's names and a search page's drawer title gain copy and open, and
  "none close" / "not live" in Not found's path columns is set in the text font (it is not a
  path). **Why:** the owner wanted to copy any value without selecting text (2026-10-25).
  **Who:** everyone reading the dashboard. **Do:** nothing. **Checked:** a new test
  (`tests/js/copy-values.mjs`) draws the tables, bar lists, Find a person, the lead list, the
  scanners table and a visit's facts with sample data and fails when an address, user agent,
  email, path or URL is drawn without its icons, or a raw one comes back in the code; the demo
  in a browser at 1440 and 390 wide, light and dark, on touch: no row moves on hover, a row
  click still opens its drawer, a copy shows the tick.

### Skald's crawler list as a public JSON file, /bots.json

- **Added.** https://skaldanalytics.com/bots.json lists every crawler and assistant fetcher
  Skald names: 38 AI names it matches plus Google-Extended (a robots.txt token, marked so and
  given no pattern), the search engines and their ads checks, and the SEO crawlers inside its
  bot list, 66 in all, with the assistants' referrer hosts and UTM tags. For each: the pattern
  it is matched by, the owner, the purpose (training, live fetch, search index, ads, SEO tool,
  other), the group Skald files it in, and how its claim is checked (the owner's published
  list with its address, reverse DNS, the owner's network, or not checked). A header gives the
  Skald version and the day the list last changed. The site's build writes it from
  `classify.py`, `bot_policy.CATALOG` and `bot_verify.py`, so a name added there shows up on
  the next build; the AI crawlers page links it. **Why:** the list was only readable in the code
  and on a page whose count (39) is written by hand; a file built from the code stays exact.
  **Who:** anyone comparing crawler lists or building on Skald's. **Do:** nothing. **Checked:**
  `tests/test_bots_json.py` fails while the file and the code differ, or a name has no owner;
  the site build ends "problems: none"; the full test suite passes.

### Akamai DataStream 2 logs, format `akamai_json`

- **Added.** Skald reads Akamai DataStream 2 logs (log format JSON, one object a line, Akamai's
  own field names) as a CDN log, beside Cloudflare Logpush, CloudFront and Fastly: `cliIP`,
  `reqTimeSec` (Unix seconds, a fraction, milliseconds or RFC 3339), `reqMethod`, `reqPath`
  plus `queryStr`, `statusCode`, `bytes`, `UA` and `referer` (URL-decoded once), `reqHost`
  (port dropped), `country`, `turnAroundTimeMSec` as the request time, and `reqId` to drop a
  record delivered twice. `cacheStatus` is noted, not counted. A line without `cliIP`, a
  `statusCode` of 0, a WebSocket line and a midgress line are not read and count as unreadable,
  never as traffic. `auto` detects it; the site's log format list and Settings > Add or remove
  sites offer it. **Why:** a site behind Akamai is mostly answered from Akamai's cache, which
  the origin's log never sees. **Who:** sites behind Akamai. **Do:** nothing unless you use
  Akamai; then stream DataStream 2 to S3 and read it as docs/CDN-LOGS.md says (the HTTPS
  destination cannot carry Skald's ingest token). As with the other CDN logs, the independent
  audit does not read these lines yet, so a day read only from them is withheld.
  **Checked:** `tests/test_akamai.py` and the shared CDN fixture tests (the same seven
  requests give the same figures as every other CDN format, `auto` picks it, no other reader
  takes its lines); field names against Akamai's docs on 2026-10-25; no real DataStream 2
  file yet.

### Counting: a link checker, a probe sweep and an encoded attack are bots, not people

- **Fixed.** Three tools that send a browser's name and load the page's assets were counted as
  people. Now each is bots, whole, and the five groups still add up to the log:
  - **An attack encoded twice.** The query-string attack list read `%2e%2e` but not
    `%252e%252e`; it now reads the dots and slashes of `../` and `/etc/passwd` encoded any number
    of times. The address and agent that sent one are a scanner for the day (rule 6b), its form
    posts included.
  - **A probe sweep** (new rule 6c): 5 or more different probe paths that the site answered 4xx or
    5xx (`/info.php`, `/wp-login.php`, `/admin/`, ...) make the address and agent a scanner for the
    day, "scanner (asked for many missing probe paths)". Redirects, assets and
    `site.legacy_paths` do not count.
  - **A link checker** (new rule 8b): a browser-like visit that sends `HEAD` for 2 or more different
    pages is "browser-like link checker (HEAD requests)". A browser opens pages with GET.

  **Why:** on example.net, 21 to 24 Oct, 174 of 398 people visits read one page in 3 s or less, a
  scanner and the office's own link checker were people, and 21 Oct showed 1,163 people page views
  (560 of them one "visit" of the checker). On example.org, 23 Oct had 1,934 people page views
  and 1,486 people's form posts from one encoded attack. **Not changed on purpose:** a short visit
  stays people (real people bounce), and a hosting network stays a flag (VPNs exit there); about
  half of example.net's short visits came from one, and they stay people. The live install has no
  `bots.ranges_dir`, so its hosting flags and crawler checks are off today; the new rules do not
  need them. **Who:** every site; mostly example.net, example.org, docomatic.ai and site.example.
  **Do:** recount the stored days from the logs after the upgrade (`backfill --days 14 --force`,
  per site) so past days match; nothing else. **Checked:** `tests/test_tool_visits.py` (16 tests:
  each rule, the readers it must leave alone, both roads, and a main road with either pass removed
  caught by the audit); the full suite; a local recount of every day still in the raw logs, every
  day's audit "all match" (one day, freshlycited.com 17 Oct, fails on Security's tied exposure rows
  with the unchanged code too). People readers and page views, before -> after (live figures were
  counted without crawler checks or hosting flags):

  | Site | Days | Readers | Page views | People's form posts |
  |---|---|---|---|---|
  | example.net | 21-24 Oct | 386 -> 376 | 1,601 -> 498 | 33 -> 23 |
  | example.net, 21 Oct | | 81 -> 73 | 1,163 -> 94 | 4 -> 4 |
  | example.org | 22-24 Oct | 1,120 -> 1,105 | 2,956 -> 1,575 | 1,664 -> 134 |
  | example.org, 23 Oct | | 402 -> 392 | 1,934 -> 646 | 1,486 -> 1 |
  | docomatic.ai | 11-24 Oct | 280 -> 275 | 610 -> 575 | 399 -> 391 |
  | site.example | 11-24 Oct | 437 -> 434 | 1,044 -> 1,017 | 77 -> 68 |
  | skaldanalytics.com | 12-24 Oct | 753 -> 752 | 1,198 -> 1,180 | 479 -> 479 |
  | example.com | 11-24 Oct | 142 -> 142 | 420 -> 420 | 6 -> 6 |
  | freshlycited.com | 17-24 Oct | 785 -> 785 | 1,847 -> 1,847 | 1,343 -> 1,343 |

### Counting: machine addresses are not page views

- **Changed.** A default list of machine and utility addresses is no longer counted as page
  views, on every site: Markdown copies of pages (`.md`, `.mdx`, `.markdown`), WordPress's
  REST API (`/wp-json/`, `?rest_route=`) and machine files (`xmlrpc.php`, `wp-cron.php`,
  `admin-ajax.php`), feeds (`/feed/`, `/comments/feed/`, `?feed=`), oEmbed (`/oembed/`),
  trackbacks, `?author=N` lookups and `?replytocom=` links. A request for one still counts as
  a request, in its usual group, so the five groups still add up to the log; it leaves page
  views, readers, landing pages, exits and journeys, in every group. Data quality shows each
  day's **Not counted as pages** (requests, people, by entry), and Requests marks each one
  "a machine address, not a page" with its entry (`quality.json` `not_pages`, the feed's kind
  `not_page`). **Why:** the owner asked that paths "not really traffic in any sense" stay out
  of page and people figures. It started from his question about example.net's `/sitemap/`
  visitors; a read-only survey of the eight live sites (2026-10-25) found WordPress API, feed
  and user-number probes counted as people's page views on docomatic.ai and example.org
  (a site that is no longer WordPress answers them with its home page) and Markdown copies
  fetched by an AI agent on example.net, and every group counting `.md` fetches as page views.
  example.net's `/sitemap/` is a real HTML page and stays one: its one-page visits are a question
  of who visited, not of the address. Search results, carts, sign-in pages, app dashboards
  (freshlycited.com's real users) and thank-you pages stay pages too. **Who:** every site;
  people's figures move little (trap 18's rules had already moved most of these to bots),
  AI and bot page views of `.md` copies move most. **Do:** nothing. A site that serves a real
  page at one of these addresses unticks it in Settings > Sites > Not pages
  (`site.not_pages_off`, e.g. `ti.py settings set <site> site.not_pages_off '["feeds"]'`); a
  site adds its own under **Also not pages** (`site.not_pages_extra`: `/path`, `/prefix*`,
  `?key`, up to 20). Stored days keep their figures until recounted with
  `backfill --days N --force`. **Checked:** unit tests (`tests/test_not_pages.py`: each entry
  with its matches and near misses on both roads, the made-up sitemap matching nothing, 3,000
  awkward URLs answered alike by both roads, the switch, the audit agreeing and catching a main
  road without the list or ignoring the setting); a local recount of every whole day on disk
  for the seven sites with logs (70 days, the copied raw logs, before = this release's other
  counting fixes), every audit "all match", every group's requests unchanged. People page views
  and readers, before -> after: docomatic.ai 566 -> 565 and 267 -> 266 (14 days), example.net
  498 -> 494 and 376 -> 376 (4 days), example.org 1,575 -> 1,570 and 1,105 -> 1,105 (3 days);
  skaldanalytics.com (1,152 / 741), example.com (404 / 133), site.example (1,008 / 429) and
  freshlycited.com (1,753 / 774) unchanged. Page views in all groups: skaldanalytics.com 6,426
  -> 5,551 (874 `.md` fetches, 164 of them by AI assistants), example.org 28,964 -> 26,018
  (2,875 `.md`, 1,776 by AI assistants), example.net 11,154 -> 10,808, freshlycited.com 14,111 ->
  13,904, site.example 26,912 -> 26,793, docomatic.ai 169,753 -> 169,552, example.com 16,197 ->
  16,189. aicouplestherapy.app has no log lines yet. Not yet recounted on the live server.

### Copilot, Meta AI, DeepSeek and Grok referrers; OAI-AdsBot; a crawler name no longer hides a scanner

- **Added.** People from `copilot.com`, `meta.ai`, `chat.deepseek.com`, `grok.com` and Grok
  inside X (`x.com/i/grok`; the rest of x.com stays X) count as AI assistant visits, shown as
  Copilot, Meta AI, DeepSeek and Grok. So do the Android apps of DeepSeek (`com.deepseek.chat`),
  Grok (`ai.x.grok`) and Meta AI (`com.facebook.stella`), and the tags `utm_source=deepseek`,
  `grok` and `meta.ai` (not a bare `meta`, which advertisers use for Facebook and Instagram
  ads). iPhone apps send no app id, so there is nothing to add for Copilot's iOS app.
  **Why:** these assistants were missing from `classify.py`; a visit from one was "Other
  website" or "Social media". **Who:** every site. **Do:** nothing. No site's log or stored day
  holds one of these hosts or tags yet (checked on the live server for every site), so no
  recount is needed for them. One freshlycited.com visit came from `deepseek.com` itself (not
  its chat), which stays "Other website". **Checked:** `tests/test_new_assistants.py` (both
  roads name each referrer the same; a sandbox day with `x.com/i/grok` audits clean).
- **Added.** `OAI-AdsBot`, OpenAI's check of the landing pages of ads placed on ChatGPT, is named
  with the AI crawlers (owner OpenAI, like OAI-SearchBot) and checked against OpenAI's
  published `openai.com/adsbot.json`. It is also in the AI crawler controls. **Why:** on
  example.net it asked for `.env.local` and key files. Every OAI-AdsBot line on the live server
  (example.net 39, example.org 285, site.example 251, docomatic.ai 672) came from outside
  OpenAI's list: scanners using the name. With the lists in place they are filed under bots as
  "claims to be OAI-AdsBot". **Who:** every site. **Do:** nothing.
- **Changed (counting).** A crawler name that is scanning (the request is a probe, or the same
  address and agent asked for secret files that day) is no longer believed unless the address is
  proven its owner's. It stays in bots, as a probe or a scanner (CLASSIFICATION.md, rule 2b); a
  proven fake still shows as "claims to be ...". **Why:** the name rules ran before the scanner
  rules, so on a day without fresh crawler lists a scanner writing Googlebot, bingbot,
  ChatGPT-User or OAI-AdsBot in its user agent was counted as that crawler. The live server has
  no lists (see the crawler-check entry), so past days hold these: over the logs it still keeps,
  docomatic.ai 13,860 requests (10-12 to 10-25), example.org 5,971, site.example 5,133,
  example.net 972, example.com 438 and freshlycited.com 8 that rule 2b files as bots. **Who:** every
  site: past AI crawler and search engine figures were inflated by these name-rotating
  scanners; they go down by these requests, bots go up by the same, people do not change.
  **Do:** nothing; the release recounts the stored days whose logs are still held. **Checked:** tests with lists and without, for OAI-AdsBot, Googlebot
  and an unlisted crawler; the main road and the audit agree on a sandbox day either way; the
  figures above measured read-only on the live server's logs.

### "Likely from an AI assistant" no longer credits typed-in home-page visits

- **Changed (inferred figure).** A direct visit is no longer "likely" from an assistant when chance
  explains the match: for each assistant and page of the day, the page's direct untagged visits
  times the minutes that assistant's fetches of it cover (fetch minute to 15 minutes after), over
  1440, is a quarter of a visit or more. Those fetches are then no evidence that day, for visits
  and for leads and conversions alike. The day stores the limit (`chance_limit`) and the pages it
  ruled out (`by_chance`); days counted before keep their old figure and still audit clean.
  **Why:** on example.net ChatGPT-User fetched the home page 78 times in four days (and its Markdown
  copy /index.md 76 times, which never counted for /: no normalisation joins them), its windows
  covered 12 to 29 % of each day, and 25 ordinary home-page visits were "likely ChatGPT", about
  what chance gives (19). **Who:** every site's Likely from AI assistants (AI & bots, Leads &
  sales › Sources, the visitor drawer, AI alerts that read it). Stored days, by the new rule
  (read-only from the live history, 10-18 to 10-24 where kept): example.net 27 to 1 (ChatGPT 25 to
  0, Gemini 2 to 1), skaldanalytics.com 54 to 1 (mostly /check/), freshlycited.com 50 to 0,
  example.org 56 to 13 (blog pages stay), site.example 11 to 1, docomatic.ai 5 to 1, example.com
  5 to 3. **Do:** nothing; a recount of the stored days applies it to them. **Checked:**
  `tests/test_ai_likely_chance.py` (a busy home page and a rare page on one day; both roads agree;
  a planted by-chance error is caught; a day stored before the rule audits clean; leads leave the
  same fetches out) and the existing likely tests.

### Crawler address checks on in Docker (they were off on every Docker install)

- **Fixed.** The container's generated config now sets `bots.ranges_dir` (the data folder's
  `ranges/`, made at start), unless `SKALD_VERIFY_BOTS=off`. `config.example.yml` sets it too, for
  new installs without Docker. **Why:** `docker/entrypoint.py` never wrote a `bots` section, so
  `bot_verify.from_config` gave no checker: no crawler claim was ever checked, no fake was filed
  as one, no browser was flagged as from a hosting network, and run-daily skipped verify-bots.
  The live server's generated config has no `bots` key and no lists folder. **Who:** every
  Docker install, including the live one. **Effect:** from the next daily run, run-daily runs
  verify-bots first; a fake crawler (a name from an address its owner does not publish) is filed
  under bots as "claims to be ...", and people's requests from cloud and hosting networks carry
  the hosting-network flag. Past days were counted without checks; with rule 2b (above) the
  scanners among them are already fixed by a recount, but fakes that never scanned stay counted
  as their crawler until those days are recounted with the lists in place. Recommendation:
  recount the stored days whose logs are still held, after the first daily run has fetched the
  lists (the lead decides at deploy). **Do:** nothing, or `-e SKALD_VERIFY_BOTS=off` to keep
  checks off; a mounted config needs its own `bots.ranges_dir`. The server needs outbound HTTPS
  and DNS. **Cost of a first fetch** (measured): 37 requests (15 owners' lists and 22 hosting
  networks from stat.ripe.net), about 7.8 MB downloaded, 1.3 MB kept, 37 s (Amazon's network list
  alone 2.9 MB, 14 s), then DNS look-ups capped at 30 s. Lists fetched in the last 12 hours are
  not fetched again, so the eight sites of one install share one fetch a morning instead of eight.
  A failed fetch keeps the last good copy and never stops the run. **Added:** `doctor` line
  "Crawler checks": NEEDS ATTENTION "crawler checks off" when there is no `bots.ranges_dir`, OFF
  when `SKALD_VERIFY_BOTS` is off, and whether the lists are fresh. **Checked:**
  `tests/test_crawler_checks_on.py` (the config on and off, the folder, run-daily running
  verify-bots before the audit with no network and still counting, the 12-hour reuse, doctor's
  three states); the fetch timed from a workstation.

### Security mail and to-do marks reach the team on every site, not only the first

- **Fixed.** With several sites in one install, each site's daily run opened `accounts.sqlite` in
  its own folder (`sites/<slug>/`), not the one beside the history where the team is. The open
  made a new, empty file there. **Why it mattered:** the security mail (2.21) found no team for
  any site but the first, so no one got those sites' alerts; Insights' marks (this release)
  would have been kept in two places. The live server had six such empty files (0 users each)
  beside the one real accounts file. **Now:** without `access.accounts`, every site uses the
  accounts file beside the history, as the docs always said. **Who:** installs with more than
  one site. **Effect:** from the next daily run, people who chose security alerts get them for
  every site of the organisation; open items those sites' files had already noted are seen as
  new once, so a first mail may list them. The old empty files are left in place, unused.
  **Do:** nothing. **Checked:** `tests/test_accounts_shared.py` (fails before the fix); the
  live server's files read read-only (six site files with no users, one install file with the
  team); the full suite.

### Tests

- The first publish of 2.35.0 (public pull request 68) failed on Python 3.14 only: a test's side
  remark checked that Python's own robots.txt reader takes the first rule. Python 3.14's reader
  takes the longest, as RFC 9309 says, so the remark no longer held. The remark is gone; Skald's
  own reader (`robots_match.py`) is tested the same on every version. Nothing else changed.
- The second publish stopped before pushing: the local public copy was still on the first
  publish's branch with the new export written over it, and switching back to main was refused.
  `tools/publish-update.sh` now switches with `-f` (that copy holds only generated files). The
  third publish (pull request 69) passed every check and was merged.
