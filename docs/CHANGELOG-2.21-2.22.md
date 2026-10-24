# Changelog: 2.21.0 to 2.22.3

The releases of 21 and 22 October 2026. Newer ones: [CHANGELOG-2.23-2.26.md](CHANGELOG-2.23-2.26.md) and [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.14-2.20.md](CHANGELOG-2.14-2.20.md).

## 2.22.3 (2026-10-22)

### Fixed

- **`audit --live` no longer fails on an old Real time request count.** The helper saves its
  last 15-second count (`live-<site>-tail.json`) only while someone has Real time open, and
  the live audit recounted that window from the raw log whenever it ran. Lines whose time was
  inside the old window but that reached the log later (a log shipper's lag) made the recount
  larger: on docomatic.ai on 2026-10-22 a count from 20:52 UTC read "the helper counted 14,
  the recount finds 18" four hours later, and `audit --live` failed for that site on every run
  since. The count is now compared only when its end is at most 5 minutes
  (`audit_realtime.FRESH_MINUTES`) before the live snapshot's own end; an older one is printed
  as "real time requests (15-second count): skipped (snapshot from HH:MM UTC, older than 5
  minutes)", never as a mismatch and never silently. A fresh one is still compared exactly:
  the log records when a request was made, not when its line arrived, so late lines cannot be
  told apart and freshness is the rule (module docstring, `docs/DATA-CONTRACT-REALTIME.md`,
  help "Real time"). Who it affects: every install running `audit --live`, most on sites
  whose logs are shipped. What to do: nothing. Checked: `tests/test_realtime.py` (a stale tail
  missing a late line is skipped with its time and exits 0; a fresh one is still compared and
  a fresh mismatch still fails; the rule at its edges, a day old and newer than the snapshot).
- **The live run is about twice as fast, with every figure unchanged.** `test_live.TestLiveCost`
  ("a busy log is read quickly") reached its 15 s limit on GitHub CI on 2026-10-21 (15.1 and
  15.2 s), and the server's live run took 56 s for six sites. Measured on that test's busy log
  before changing anything: 6.5 s here, 0.9 s at 2.12.0 and 6.2 s at 2.13.0, so the jump came
  with 2.13's "yesterday at this hour" (it tallies yesterday up to the same time on every live
  run), not with 2.21's Security: switching Security's collector off saved about 0.2 s. The
  profile showed the cost in a few per-request repeats, now each worked out once:
  `classify.FanOut` ran two case-insensitive alternations per request on the user agent
  (about a quarter of the run), now once per agent; the link-preview list (18 patterns) joins
  the classifier's per-agent cache; `Hit.is_page` keeps its answer apart from `repeat`; the
  parser skips the `rsc_prefetch=`, `request_length=` and `rid=` searches on lines without
  them; a tally no longer builds a fresh `GroupStats` (a dozen Counters) on every request to
  find an existing one. Security's episodes (`security.Runs`) keep per request only what an
  episode reads (time, status class, path, pair), sort each address once by plain tuple order,
  skip addresses under the threshold, and are worked out once instead of twice. The audit's
  road is untouched. Result: 6.5 s to 3.4 s for the test's live run here. Who it affects:
  every install's live run. What to do: nothing. Checked: the full suite; every stored figure,
  both audits' outputs and the live snapshot equal before and after on Security's day, the
  order test's day (sorted and shuffled), an ordinary day and the busy log (both roads); a new
  test compares `Runs` with the rule read plainly on shuffled synthetic days
  (`tests/test_security_order.py`).

## 2.22.2 (2026-10-22)

### Fixed

- **A firewall that stops the public check is "could not check", with what to run instead.**
  On 2026-10-22 someone told us the check "is not giving correct result": the most-checked site
  that day was stopped by its firewall every time, and the answer read like a failure. Three
  sites answered our server with a Cloudflare-style challenge and one with 403 (a visitor
  elsewhere got a 301). The check still never changes its User-Agent or works around a
  challenge. Instead `stack_public_blocked.py` reads the answer: a challenge
  (`cf-mitigated: challenge`, AWS WAF's `x-amzn-waf-action`, "Just a moment..." and the like),
  401 (a password, said so), 403, 429, or a 503 that is a firewall's own denial page (a 503
  alone, and Sucuri's "unable to connect to the backend", stay "the home page answered 503").
  The answer's summary says "Your site's firewall stopped our check, so we can't see what it
  shows. That's often good news: it blocks automated scanners too."; a new `block` field gives
  the kind, the status, the firewalls its own headers or page name (Cloudflare, Sucuri, Akamai,
  AWS WAF, CloudFront, Imperva, Fastly, Wordfence) and the commands to run by hand
  (`curl -sI https://<host>/ | grep -iE "server|x-powered-by"`, `php -v`); the card shows the
  proof (the status, the challenge's header or page title, the firewall's header) and the counts
  stay at 0, so it is never counted as a problem with the site. Who it affects: sites that
  switched the public check on. What to do: nothing. Checked: `tests/test_stack_public_blocked.py`
  (a Cloudflare challenge, a plain 403, Sucuri's 503, AWS WAF, Akamai, Wordfence, Imperva, a
  password, two 503s that are not blocks, one request and no other agent) and three new corpus
  cases in `tests/fixtures/stack_public/`.
- **The summary reads in the order people say it.** A site served by nginx, with PHP proven
  but its version hidden, behind CloudFront read "Your site is served by nginx on PHP (version
  hidden) behind CloudFront". `stack_public_cards.stack_words` now names the platform or the
  language first, then the web server, the host and the CDN: "Your site runs PHP (version
  hidden) on nginx, behind CloudFront." The web server is now named after a platform too
  ("Your site runs Drupal 10 on PHP (version hidden), served by Apache."), and a language not
  under the platform is no longer put under it. Who it affects: anyone reading a public check.
  What to do: nothing. Checked: every summary of the 25-case corpus in a table
  (`tests/test_stack_public_blocked.py`, with checks on the order of the parts), and 15
  combinations of platform, language, server, host and CDN.

### skaldanalytics.com (the marketing site, not the Skald image)

- **/check/: a blocked check shows what to run from your own computer.** Under the summary, a
  box: "To see the details, run the same check from your own computer:" with the command-line
  check's one-liner, the site's name filled in and a copy button
  (`curl -sSL https://raw.githubusercontent.com/spcaeo/php2shell-check/main/php2shell_check.py |
  python3 - <host>`, from the form's `data-cli`, built from `check-news.json`'s `cli_repo`), then
  the commands by hand. The PDF report is offered for a blocked check too and carries the same
  words and commands (the one-liner broken after its pipe so it still runs when copied); the
  agency table says "could not check" with the same summary. Checked: `_src/test_check_ui.py`
  (headless Chrome, drawing Skald's own answer for the Cloudflare case), `_src/test_check_pdf.mjs`,
  `_src/test_check_messages.mjs`.
- **A slim GitHub bar at the bottom of /check/, /security/ and /security/php2shell/** (owner,
  2026-10-22): "Free & open source: run this check from your terminal or CI" (on phones
  "Open-source CLI") and "Star on GitHub" to github.com/spcaeo/php2shell-check (MIT; Skald itself
  stays "source-available"). Its × hides it, remembered in this browser's localStorage (inside
  try/catch: without storage it shows again); while shown the page gets bottom padding of its own
  height, so it never covers the form, the PDF button or the footer; hidden when printing and
  never in the PDF (which is drawn from the answer, not the page). Nothing is tracked. Checked:
  `_src/test_check_spread.py` (on the three pages only, its link, label and close button, no
  network call in its script), `_src/test_check_ui.py` (closes, stays closed, padding back to 0),
  by eye at 1440 and 390 px, light and dark.

## 2.22.1 (2026-10-22)

### Fixed

- **The same finding on two hosts is one card now, listing both.** On 2026-10-21 the public
  check showed one site's "Your server shows its exact version: nginx 1.18.0" twice (once for
  www., once for the headless WordPress at wp., the same title), and counted it as 2 tips.
  `stack_public_cards.merge` joins cards of the same kind and title: the card lists every host,
  keeps each host's evidence (each line still says which URL it was read from), ends "Seen on 2
  hosts: www... and wp...", and the counts and the summary count it once. Who it affects:
  anyone using the public check (`security.public_check`), on sites with a content origin.
  What to do: nothing. Checked: `tests/test_stack_public.py` (a headless site whose two hosts
  send the same `Server` header, and a single card kept as it was); the 22-site corpus in
  `tests/test_stack_public_cases.py` is unchanged.

### Added

- **The public check says how many checks are left, and when one more is allowed.** Every 200
  answer from `POST /traffic-hooks/_public/stack-check` now carries `limit`, `left` (after this
  check) and `next_at` (UTC, when the oldest counted check stops counting); `{"quota": true}`
  answers just those and counts nothing. Why: the marketing site's new agency mode checks up to
  10 sites one after another under the same 10-an-hour limit and must tell people how many they
  can still run, and when. Who it affects: sites that switched the public check on. What to
  do: nothing. Checked: `tests/test_stack_public.py` (left after fresh and cached checks, per
  sender, the quota call never counted, over HTTP through the beacon helper).

### skaldanalytics.com (the marketing site, not the Skald image)

- **/check/: the PDF report up front.** In the first 5 hours after launch 21 browsers opened
  /check/, 13 people ran a check and none downloaded the PDF, whose form sat at the bottom of a
  long result. A "Download PDF report" button now sits right under the summary, with "Share with
  your developer", and opens the email form in place (`#get-pdf` in the address, so a reload
  opens it again); the bottom card stays. Nothing new is tracked in the browser: the lead is
  still kept server-side only, when the form is sent. Checked in headless Chrome
  (`_src/test_check_ui.py`).
- **/check/: "Check another site"** at the top of every result, without leaving the page.
- **/check/?urls=: an agency mode.** Up to 10 sites, checked one at a time on the same endpoint
  and limit (10 an hour from one address: every site counts, a site checked in the last hour
  too). The page says how many checks are left and when (from the endpoint's own `left` and
  `next_at`; only the rule itself when an older Skald does not say), stops at the limit with
  the time one more is allowed and a "Check the rest" button, waits and retries when nginx's
  short burst limit answers, and shows a table: site (with its full result's address to copy or
  open), worst status, summary. One PDF for every site checked (`SkaldCheckPdf.buildMany`: the
  table first, then each site's findings) for one email; the lead is labelled
  `exposure-report-agency` (`-alerts` when ticked) and `report.py` keeps every site and their
  number (`site_count`, a column added to an existing table on start). The hint says the list is
  in the page's address and so in our server log (14 days). Checked: `_src/test_check_multi.mjs`
  (the list, the limit message, the worst status), `_src/test_check_pdf.mjs` (the combined PDF
  holds every site and finding), `_src/test_check_ui.py` (the limit message, the table and one
  report with every site, in headless Chrome), `signup/test_report.py` (label, sites, count,
  limits, an old table).
- **Share without exposing anyone.** LinkedIn, X, WhatsApp and copy-link buttons on the hero,
  the result, the bottom of /check/ and the php2shell article: plain links, no third-party
  script; the address shared is always `https://skaldanalytics.com/check/`, never a result's
  `?url=`, with "php2shell: I just checked my site. Check yours in 10 seconds." The result's own
  link is now labelled "it names the site, so keep it to your team". Checked:
  `_src/test_check_spread.py` reads every share link on every page.
- **A badge for READMEs and footers:** `https://skaldanalytics.com/check/badge.svg` ("php2shell ·
  checked with Skald"), static and the same for everyone (no site, no status), with Markdown and
  HTML to copy in a "Spread the word" fold on /check/. Checked: valid SVG, generic text.
- **/security/ and /security/php2shell/ are built and linked:** "Security" in the menu, a
  Security column in the footer (Security, Free site check, php2shell guide), the home band
  "New: is your site exposed to php2shell?", the sitemap with lastmod, share cards
  (`share-php2shell.png`, `share-security.png`, problem-first) and the 2.21 screenshots as WebP.
  The article (about 900 words) lists only what php.net, Cloudflare and nodejs.org confirm, each
  linked, with our audited scanner figures and the `awk` one-liner to check your own log.
  Checked: `_src/test_check_spread.py` (title, description, canonical, Open Graph, Twitter,
  JSON-LD `Article`/`CollectionPage` with `BreadcrumbList`, one h1, sitemap, links in).
- **"Run it from your terminal or CI"** on /check/ (the hero and under a result) and in the
  article: the `curl ... | python3 - example.com` line and a 6-line GitHub Action job
  (`spcaeo/php2shell-check@v1`), each with a copy button, and a link to
  github.com/spcaeo/php2shell-check (MIT). Behind `show_cli` in `_src/check-news.json`, on now
  that the repo is public.
- **The page no longer says a checked site is not logged.** The guide's "Nothing kept" line and
  the FAQ "Do you keep the address I type?" said the address was not logged; a result page's
  address (`/check/?url=...`) is in our web server's log for 14 days, read by Skald. Both now
  say so, as the hint and the privacy note already did (owner's choice, 2026-10-21).
- Copy buttons keep a snippet's leading spaces (a YAML job pasted under `jobs:`) and add a
  newline only after a terminal command.

Deploy: the site folder; `signup/report.py` to `/opt/skald-signup/` and a restart (the agency
label and `site_count`); the merged cards and `left`/`next_at` come with the next Skald image.

## 2.22.0 (2026-10-21)

### Added

- **A public "Is my site exposed?" check, off by default** (`security.public_check: true`, or
  `SKALD_PUBLIC_CHECK=true` with `SKALD_PUBLIC_CHECK_ORIGINS` and `SKALD_PUBLIC_CHECK_INFO_URL`
  in Docker and docker-compose.yml). `POST /traffic-hooks/_public/stack-check` with
  `{"url": ...}` on the beacon helper (`stack_public.py`, `stack_public_cards.py`,
  `stack_public_api.py`) reads a site's home page from outside, as Security > Your stack does,
  then one WordPress host of the site's own domain that the page loads `/wp-content/` files
  from (a headless WordPress), and `/wp-login.php` on each WordPress host. It matches the
  shipped advisories (PHP CVE-2026-109618 and CVE-2026-109619; Node.js October 2026) and
  answers JSON cards: update needed, check your version, login page open, could not check,
  your server shows its exact version (a tip, never a flaw), headless WordPress, login page
  hidden (good), has the fix, nothing known applies. Why: a free page anyone can use the week
  PHP fixed two critical flaws. Who it affects: no one until an admin switches it on. What to
  do: nothing, or the settings guide's "Public check" to offer it. With `"cached_only": true`
  it answers only a check made in the last hour, never fetching: a page's "send this report"
  reads its findings back this way, so a report carries only what the check found.
- **Every finding shows its proof** (owner: "everything has to be true and authenticated").
  Each card says what was seen, exactly as received (`Server: nginx/1.18.0 (Ubuntu)`,
  `X-Powered-By: Next.js`, the generator tag, the `api.w.org` Link header, "289 files loaded
  from https://wp.<site>/wp-content/..." with the first examples), the URL it was read from,
  what it means ("This means..." only for what the facts prove), why an advisory matched
  (product, version or "version not shown", host), and `curl` commands to check it yourself,
  with every URL shell-quoted. The answer lists every request (method, URL, status, size,
  redirect, error, or "not fetched: the limit of 8 requests"), its time and the User-Agent.
  "Update needed" only for a version the server showed; "could not check" for a home page that
  is not a 2xx or is a bot challenge (Cloudflare's "Just a moment"), with nothing read from it.
  The login page is followed to its final page and its body read: "open" only for WordPress's
  login form; a redirect to a page without it (a security plugin's `/not_found`), 401, 403,
  404 or 410 is "hidden (good)"; anything else "could not check". Checked against responses
  recorded from a real headless site on 2026-10-21 (renamed to example.com in the tests): it
  gives WordPress (PHP) and Next.js (Node.js) "check your version" with their advisories, the
  nginx version tip, the headless set-up and the login page hidden.
- **Its safety rules, because it fetches addresses strangers type.** Only http and https,
  ports 80 and 443, no `user:password@`; never an IP address in any form (literal,
  `[::ffff:127.0.0.1]`, `2130706433`, `017700000001`, `0x7f.1`, `127.1`), never a name that
  only works inside a network (`localhost`, `*.local`, `*.internal`, `*.lan`, `*.home.arpa`,
  `*.test`...); the name is resolved once and refused whole when any address is loopback,
  private, link-local, CGNAT, multicast, reserved or a cloud metadata address (IPv4 and IPv6,
  mapped and embedded IPv4 too); the connection goes to the address checked, with the name as
  Host and TLS name, so DNS rebinding has nothing to switch; at most 3 redirects, each checked
  again; login redirects followed only within the site's domain; 5 seconds and 512 KB per
  request, 8 requests and 9 seconds per check (5 redirects from a login page); GET and HEAD only, no cookie or credentials.
  Limits in memory: 10 checks an hour per address (X-Real-IP only on the proxy's loopback
  connection), 300 fetching checks an hour in all, 4 at once; each answer cached an hour (a
  site that did not answer, 5 minutes). CORS only for the configured origin; a page of another
  origin gets 403. Nothing is written or logged but one hourly line of counts. Checked by
  `tests/test_stack_public.py`: every refusal above, rebinding in both directions and
  between redirect hops, redirects inside and to odd ports, the caps against a local server,
  the rate limits, the cache, the HTTP side, the challenge, blocked and redirect-to-not-found
  cases, and that every card carries non-empty evidence.
- **It reads many platforms, each with its evidence** (`stack_public_detect.py`): WordPress
  (generator, its own files, the wp-json Link, core files' `?ver=`, multisite), WooCommerce,
  Drupal, Joomla, Magento, Laravel (XSRF-TOKEN plus `<app>_session`), Statamic, Symfony,
  CodeIgniter, PrestaShop, OpenCart, Craft, TYPO3 and plain PHP; Shopify, Wix, Squarespace,
  Webflow, HubSpot, WordPress.com and WordPress VIP, which patch for you; Next.js, Nuxt, Gatsby,
  Remix, SvelteKit, Astro, Hugo, Angular Universal, Express and Ghost; Vercel and Netlify, which
  run Node.js for you; nginx, Apache, LiteSpeed, OpenResty, IIS, Caddy; Cloudflare, Fastly,
  Akamai, CloudFront, Sucuri (with Cloudflare's own php2shell note, from `advisories.json`).
  Extras: security headers, the certificate's end (from the handshake already made), XML-RPC on,
  readme.html's version. A one-line summary and cards by group (act, check, tips, good). A
  product that only runs on PHP or Node.js is named by itself ("PHP on <host>: version not
  shown"), with what runs on it as the evidence. Checked by a corpus of 22 recorded sites
  (`tests/fixtures/stack_public/`, example.com names, exact cards), and by
  `tools/verify-public-check.py` on 29 real sites whose stack is public (`tools/public-check-truth.json`,
  each with how its truth was verified; ours included): both kept out of the public export.
- **skaldanalytics.com: the page `/check/`** ("php2shell: is your site exposed?"), in the
  marketing site's own source (not in this repository's public copy). The week's story at the
  top from `_src/check-news.json`, every item linked to its source (php.net, Cloudflare's blog,
  nodejs.org), and the build stops on an item without one; the form; while it runs, a scan
  frame that shows no step that did not happen; the result: a summary line with counts, cards
  with their proof, brand logos (Simple Icons, CC0, with an ownership line), "check it yourself"
  folds with copy buttons, "What we saw" chips and a "What we fetched" table; a shareable
  `/check/?url=...` that runs the check again and is never indexed; about 1,000 words of
  indexable guidance and a 7-question FAQ (with "What is php2shell?" and "Does Cloudflare
  protect me?") with `FAQPage`, `WebApplication` and `BreadcrumbList` JSON-LD; a problem-first
  1200x630 share card (`img/share-check.png`, made by `tools/make-share-cards.py` from the same
  story) with full Open Graph and X tags; links from the home page, What's new and the privacy
  page. Every failure is said plainly (below). Checked by the build ("problems: none"), tests
  that parse the page's JSON-LD and every page's share tags and image sizes, node tests of the
  messages and of the PDF, Lighthouse on mobile, and screenshots at 1440 and 390 px. The
  `/security/` hub and the php2shell article are written but not built: the next release.
- **skaldanalytics.com: "Get this as a PDF report"** (the sign-up helper's `report.py`,
  `POST /api/report`). The result stays free on the page; the PDF needs the person's email
  (name and company optional, an unticked "email me when a new advisory matches my site"). The
  helper records who downloads it and sends them to Skald as a `contact` lead (label
  `exposure-report`, or `exposure-report-alerts` when ticked; `test` for our own and test
  domains); it sends no mail and asks for nobody else's address (owner: no emails to admins).
  Limits: 3 an hour per address, a honeypot, a minimum fill time. The browser then builds the
  branded PDF from the result on the page (`check-pdf.js` with jsPDF 2.5.2, MIT, vendored, loaded
  only then): a cover with the host, time, summary and counts; the week's story with its
  sources; each finding with its badge, quoted evidence, meaning, fix and commands; what was
  fetched; what the check can and can't see; a last page on reading your server log; page
  numbers and clickable links; `skald-security-check-<host>-<date>.pdf`. Checked by tests of the
  lead body, the limits, the honeypot, consent only when ticked, no SMTP anywhere in the path,
  and a node test that the PDF holds the host, the summary and every finding's title.
- **Every failure of the check says what happened and what to do** (owner: "Sorry, the check did
  not go through" was a bad error). The endpoint's errors carry a `kind` (`address`, `refused`,
  `rate` with `retry_at` and `retry_in`, `busy`, `failed`), and a site it could not read carries
  a `reason` (`unreachable`, `blocked`, `error`) with plain words ("no answer in 5 seconds", "the
  name doesn't exist", "its certificate is invalid"). The `/check/` page turns each into one
  sentence: not a website address (try www.example.com); we couldn't reach the site, and why,
  with the requests tried; the site's firewall blocked our check (often good news; check the
  version on your server, with the commands); you've run 10 checks, check again at a given time;
  lots of people are checking; our checker isn't answering (on our side, not your site); and, on
  a local preview, the check service isn't running there. Checked by a node test of each case on
  mocked answers and by the endpoint's own tests.

### Changed

- **The site check refuses a host that ends in numbers** (`127.1`, `0x7f.1`): an address in
  disguise that a resolver may read as one. Before, such a name was looked up and the address
  it gave was then refused, so nothing was reachable; now it is refused before any lookup, for
  the Add a site check too. Who it affects: no real site (no name ends in a number). Checked by
  the existing site check tests and the new ones.
- **`site_fetch.open_pinned` takes the User-Agent** (`agent`), so the public check names itself
  `SkaldStackCheck/1.0`; the Add a site check is unchanged.

## 2.21.1 (2026-10-21)

Bursts and login hammering now counted the same way by both roads, two false "possible exposure"
rules fixed, and no alert from a day counted by 2.21.0. Stored days need a recount.

### Fixed

- **Security's bursts and login hammering failed the audit on real logs** (live, 2026-10-21:
  "bursts.episodes" 2 against 198 on one site, an episode's end a second or more apart on
  others; every other figure matched). Two order bugs, one in each count. The main count read
  each address's requests as they arrived and assumed time order, which a real log does not
  keep (nginx writes a line when the answer ends; shipped files are merged), so a late line
  broke its 60-second or 5-minute window and an episode ended at the last line read. The second
  count listed an address's requests agent by agent, so an address that rotates user agents
  (most scrapers) was read out of time order. Both now work the episodes out on each
  address's requests sorted by time (then status, path and agent), whatever order they were
  read in; an episode ends at its latest time; the list of episodes has a full tie-break; a
  scanner's country is its earliest line's.
- **False "possible exposure" alarms, found in real data** (2.21.0 counted both as
  possible exposures, which a site's people would have been mailed about):
  - **One page, two sizes on one host.** On 17 Oct a server's bare IP answered 134 probe paths
    with its default page at 404 bytes (compressed), and 18 WordPress probes from one scanner
    that did not ask for compression with the same 626-byte page uncompressed. Only the most
    common size counted as harmless, so the 18 became "possible". Now every size at least 3
    probe paths of the host share is a fallback size (`shell_sizes`); a lone path with its own
    size stays possible.
  - **An injection in the query of an ordinary page.** On 20 Oct `/` with an injection in its
    query string was answered 200 with the home page (101,804 bytes, its usual size); the host
    had no fallback page, so it was "possible". "Is anything exposed?" is about files served
    for probe paths: a probe whose path is an ordinary page is no candidate now
    (`query_only`); Attack attempts lists it with what was answered.
  - **No alert or mail from a day counted before this:** each day records its exposure rule
    (`rules.exposure_rule`: 2). The site's alert and each person's security mail read only days
    counted with it, so a day stored by 2.21.0 never alerts until it is recounted; today's
    figures are counted again at the next live run. Items no longer found close at the next run.
- **Who it affects:** every site with a burst or a login-hammering episode, and every site with
  a possible exposure in 2.21.0's figures. **What to do:**
  recount the stored days with `backfill --force` for the days the raw log still holds (the
  owner's release does it); days collected by 2.21.0 keep their old episode figures until then.
- **How it was checked:** `tests/test_security_order.py` (the same figures from both counts on
  a day read in order and shuffled twice; an address rotating three agents in a burst and
  coming back slowly all morning; two bursts 62 seconds apart; 19 POSTs never an episode; the
  latest time as the end; the collector alone forwards and backwards; a burst across midnight
  in the site's time zone). The 2.21.0 code reproduces the live mismatch on these.
  `tests/test_security_fallbacks.py` (the 404/626 shape with 134 and 18 paths, both harmless,
  and a lone 1,873-byte file still possible; the home page answered to a query injection is no
  candidate and is listed under Attack attempts; both counts agree and the audit catches a
  dropped fallback size; a day without the rule stamp opens no alert and sends no mail).

## 2.21.0 (2026-10-21)

Two parts: **Security**, a new section built from the server's own log (exposure check, scanners,
attack attempts, fake browsers, a block list, your stack and its advisories, alerts to the people
on each site); and **every view has its own link**, with copy and open-in-a-new-tab on every URL
and three fixes to the set-up list. Also: the Node.js advisory card's score line no longer
repeats its severity ("High · High"), and the scanner detail has its own key (`scan=`) and opens
its request list through a token, never the address in the link.

### Part 1: Security

- **`skald stack` checks the stack now** (the same public reads as the daily run), so a new install or a new advisory list shows on Security > Your stack without waiting for the morning run; `dashboard` then draws it.

Security: a new section that shows who probes the server, whether it ever handed one of them
a real file, what else was tried, and which addresses to block, all from the server's own log
and every figure counted twice. For owners and admins of any site Skald reads.

### Added

- **Security, a section of its own** (in the menu after AI & bots; route `#threats/...`,
  `g` then `y`). Why a section and not a tab of AI & bots: it is about the server and what was
  tried against it, on every host the log names (the server's bare IP too), where AI & bots is
  about who reads the site; and its six questions would crowd that strip. The menu has room for
  a sixth row; the phone's bottom bar keeps five sections and Menu, so Security opens from Menu
  there. `#security` still opens Settings > Security, as it always did. Why now: the owner asked
  to "see all similar logs and double confirm" after a hand check of the sites' logs found
  thousands of scanner probes on one site in a day (`/phpinfo.php`, `/.env`,
  `/storage/logs/laravel.log`, `/serverless.yml`, `/owa/...`), some of them answered 200, and
  wanted it as a selling point (the figures are now Skald's own, counted twice). Six tabs, each answering one question:
  - **Is anything exposed?** The headline, first: one line, "Nothing exposed in this period",
    "N possible exposures: check these now" or "Can't tell for N answers". Every scanner probe
    the server answered 2xx is set against its host's own fallback page (what a single-page app
    or a default server page sends for any path it does not have): the size (within 16 bytes)
    that the most distinct probe paths of that host got that day, when at least 3 paths share
    it. Harmless if it matches, a possible exposure if not, "can't tell" (never "safe") when the
    log has no size. Each host has its own, and the bare IP is a host of its own: the log's size
    is the size sent after compression, so the same 626-byte page was 392 bytes through the CDN
    and 404 bytes straight to the IP on a real site, both harmless. Each possible exposure lists
    host, path, time, status, size, why it was flagged and one line of advice (for example
    `location ~ /\. { deny all; }`, then rotate the secrets). The (i) says plainly what the log
    cannot prove: it records the size, never the content.
  - **Who is scanning us?** One row per scanner (address and user agent): first and last seen,
    requests, probes, country, hosting network (where Skald keeps that list; no guess when it
    does not), what it looked for (secret files, cloud and deploy configs, admin panels,
    WordPress, PHP, dumps and backups, path tricks and injection), what the server answered, and
    two signs: a **forged referrer** (it claimed one of the site's pages or subdomains, such as
    a `wp.` subdomain, and never loaded the site's files) and **sent to the bare IP**. Probes per
    day as a small chart. A row opens its detail and **Open its requests** (Site > Requests
    filtered to the address), which says that older raw lines have expired from the request list.
  - **Attack attempts:** path traversal and injection by kind (traversal, Log4Shell, script, SQL,
    PHP settings); login and form hammering (20 POSTs to a login or form path from one address
    within 5 minutes); bursts (300 requests from one address within 60 seconds, people and bots
    only). Each: address, when, how many, what was answered. Thresholds in the config's
    `security:` section (docs/SETTINGS.md).
  - **Fake browsers and scrapers:** the requests Skald already files as bots (never rendered the
    page, too fast for a person, a browser-like crawler, "claims to be Googlebot"), by address
    and network, with the pages they took; named crawlers stay on AI & bots.
  - **Block list:** the worst addresses and networks (probes, then attack attempts), exported as
    nginx `deny` lines, a Cloudflare IP list CSV or a plain list (fail2ban, ipset). An (i) and a
    note say to review first: a shared address or a CDN can carry real visitors.
  - **Alerts:** the two new rules and the security alerts of the last 30 days.
- **Your stack** (Security's second tab): once a day the morning run reads each site from
  outside, like a visitor (the 2.17 safe fetcher: no cookie, no password, public addresses
  only): the web server and its version, PHP and its version, WordPress, Next.js (and so
  Node.js), and any host the pages load WordPress files from (a headless WordPress at `wp.`
  of the site, as on a real site checked today), with `/wp-login.php` asked once on every
  WordPress host: "Login page open to the internet" when it answers. A version the server
  hides reads "not shown by the server", never guessed, with the command to see it folded
  under "For your server admin". Kept per day (`stack-<site>.json`), shown "as of" its time.
  Why: the owner asked what runs each site and whether today's PHP and Node.js advisories
  apply. Off with `security.stack_check: false`.
- **Advisories** shipped with Skald (`data/advisories.json` in the package): PHP's
  CVE-2026-109618 and CVE-2026-109619 (critical, unauthenticated remote code execution; fixed
  in 8.5.12, 8.4.27, 8.3.36, 8.2.35; none for 8.1 and older) and Node.js's October 2026
  security releases (fixed in 22.23.4, 24.22.1, 26.12.1), from php.net and nodejs.org. Each is
  matched against the stack: **Update needed**, **No official fix: upgrade the branch**, or
  **Check your version** (hidden), as a card with what to do, the advisory's mitigations
  (folded, said to reduce the exposure, not to make a site safe) and the source links. Skald
  tells you what applies and how to fix it; it does not detect or block an exploit. Nothing is
  fetched unless `security.advisories_fetch: true` (off by default) lets the morning run take
  the newest list from the public repository. Second count: `audit_stack.py` reads the kept
  evidence again with its own parsing and version comparison (run-daily's recounts).
- **Log signs worth a look** (top of Attack attempts), never "attack detected": a day whose
  gateway errors (502, 503, 504: crashing PHP workers or an upstream) or requests for `.php`
  paths reach 3 times the median of the 14 days before it (7 recorded at least) and 20, with
  its busiest hour; and, where the log records each request's size, POST bodies of 1,000,000
  bytes or more (`security.large_post_bytes`). The size is a new optional log field,
  `request_length=$request_length`, read like `rsc_prefetch=` by both roads and documented in
  docs/INGEST.md; without it the tab says "not recorded" and gives the line. Why: the PHP
  advisory's flaw crashes workers and takes large multipart bodies. The counts are part of the
  day kind `security` (`signs`), recounted by audit_security.py by its own reading.
- **Security alerts to the people on the site.** Each team member chooses their own, per
  site, under Security > Alerts, "Your security alerts": on or off, right away or in the daily
  mail. Defaults: owners and admins on, right away; viewers off until they opt in. What: a
  possible exposure, and an advisory that matches the stack. Each mail names the site, what was
  found, what to do in one line, and a link straight to it (`#threats/exposed?item=<id>`, an
  opaque hash, never an address), which opens the tab with that item first. Each item once; a
  reminder only while it stays open, every `security.remind_days` (3) days. Only confirmed,
  enabled accounts get one; an exposure the site's alert mail already sends to that address is
  not doubled. Every send is an audit-log row (to whom, which item, how; never the content).
  "Send a test security alert" for owners and admins (3 in 10 minutes). Routes under
  `settings/` (no nginx change). Why: the owner asked for "a way to alert the people you added
  to receive those messages". Also a third site alert, **Advisory matches your stack**, on with
  the site's alerts, so the site's mail and Slack hear about it too.
- **Two alerts**, through the existing alert machinery (dashboard, mail, webhooks and Slack's
  `alert.opened`): **Possible exposure** opens at once from the live count and from the last
  whole day, one per host and path; it is on by default, so it follows the site's alerts
  (`alerts.enabled`, `alerts.mail`). **New scan wave**: the last whole day's probes at least 3
  times the median of the 14 whole days before (at least 7 counted) and at least 200; off by
  default (`alerts.scan_wave`). Both on Site > Alerts.

### Who sees what

- **Addresses:** owners and admins only, through a new helper call `GET <page>/people/security
  ?first=&last=` (CSRF or same-origin, one audit row "security addresses viewed", never an
  address), and only what the site keeps (`privacy.keep_ips`): full addresses and their
  networks; with `short`, networks only (/24, /48) and the page says so; with `off`, none, and
  each day's rows stand alone. Viewers see every figure and row without the address. The public
  demo shows its made-up documentation addresses as an owner sees them.
- **Nothing in history holds an address or a user agent:** the day kind `security` carries a
  row number; the address behind it is kept in `conversions.sqlite` (schema 8, tables
  `security_rows` and `security_days`) beside the kept visits, under the same rules: only while
  the site keeps addresses, for `privacy.keep_days`, pruned nightly, deleted by `forget --ip`.

### How it is counted

- **A view, never a group:** every request stays where classify.py put it; the five groups add up
  exactly as before. A probe is a bots request whose path or query a scanner pattern matches
  (classify.PROBE / PROBE_QUERY), plus probe-shaped lines sent to the server's bare IP, which
  count in no group (another host's) and only here.
- **New day kind `security`** (docs/DATA-CONTRACT-SECURITY.md), counted in the tally pass every
  daily and live run, whole site only; `security.json` for the page (the last 31 days' rows, every
  day's totals). Days collected before this release read **Not recorded**, never 0; `backfill`
  counts them for days whose raw lines are still on the server.
- **Second count:** `audit_security.py` rebuilds the whole day from the raw lines by its own code
  (its own pairing, categories, referrer and asset tests, shell rule, episode rule and ranking)
  and compares every figure, and on a whole day kept with addresses, every kept address against
  its own ranking. The scan-wave alert's figure and median are rechecked from history by
  run-daily. A mismatch withholds the day, as always.

### What to do

- Nothing to set up: Security fills from the next run. Owners and admins see the addresses on
  sites that keep them. To count the days before the upgrade, run `backfill` for the days the raw
  log still holds. Switch **New scan wave** on in Site > Alerts if you want it.
- On a site whose log has no body size (`$body_bytes_sent`), "Is anything exposed?" can only say
  "can't tell": add it to the log format.

### Checked

- `tests/test_security.py` (categories, bare IP, own referrers, login paths; the exposure rule:
  a 392-byte app shell and a 404-byte IP default page harmless each on its own host, a 1,873-byte
  leak possible, the tolerance, too few paths, one file asked five times, no size and empty; the
  login threshold at 19, 20 and spread out; a burst with Googlebot left out; the whole day stored,
  verified and audited; no address in history; the groups unchanged; a view has none; the live
  run and `audit --live`; old paths; a log without bytes; the audit catching a moved exposure, a
  moved category and a dropped row).
- `tests/test_security_more.py` (addresses kept in full, shortened and not at all; the audit
  catching a swapped address; `forget --ip`; `people/security` refused to viewers and cross-site,
  audit-logged without an address; security.json with a not-recorded day and no address; both
  alerts, their settings, their webhook body, the wave's median and its recheck catching a change).
- `tests/test_security_notify.py` (who gets them: owners and admins by default, a viewer who
  opts in, never an unconfirmed or disabled account; the item ids and link format; once per item
  then a reminder after 3 days, a closed item never; no double mail for the site's alert
  recipients; the daily-mail digest in one mail; the test send and its audit row; the routes by
  role and the test limit) and the advisory site alert in `tests/test_security_stack.py`.
- `tests/test_security_signs.py` (request_length= read by both roads wherever it sits, "-" and
  absent as not recorded; gateway errors, .php requests and large POSTs counted and audited;
  the audit catching a moved hour) and the worth-a-look rule in `tests/js/security.mjs` (a
  flagged day against its usual, too few days flags nothing, the not-recorded line).
- `tests/test_security_stack.py` (products and hidden versions, the content origin, www. read
  once, every advisory state, the shipped list valid, a check kept with its matches and
  audited, the audit catching a changed state, a failed fetch never stopping the run, the
  switch, no fetch unless asked and an invalid list refused, the data file's cards).
- `tests/js/security.mjs` (the period's sums, the verdict, rows joined to addresses, the block
  list and its three exports in full, short and off modes, every tab drawn for a viewer and an
  admin with nothing null appended). The demo (`tools/demo_security.py`) adds scanners, one fake
  leak, login hammering, a burst and a browser-like crawler on example.com, with RFC 5737
  addresses only.

### Part 2: every view has its own link

Every state in the address, copy and open-in-a-new-tab on every URL, and three fixes to the
set-up list (the owner's rules of 2026-10-21: "a proper URL router ... so any state is reachable
and copy-pasteable"; "if there is a URL on a mouse over, show two small icons ... copy ... open in
a new tab").

### Added

- **Every view has its own link.** *Seen:* opening a visitor, a lead, a request, a Set up or a
  Connections dialog left the address as it was, so it could not be shared, and Back left the page.
  *Change:* one key registry (`js/routekeys.js`, `docs/ROUTES.md`) and one router for what is open
  over a tab (`js/overlays.js`). New keys: `vis` (visit day and number, `vis=2026-10-20.14`), `who`
  (person search), `lead`, `conv`, `req` (a code of the log line), `cohort`, `sq`, `list`, `ans`,
  `setup` + `step` (Set up dialogs; Add a site on Add or remove sites), `conn`, `share`, `dlg` (keys,
  What's new, saved views, report builder, Filters, Find a person); sub-tabs as `<ns>_view` (Alerts,
  UTM tag, Search's engine/period/measure, the flow, Live's sources order). Opening pushes a history
  entry so **Back closes it**; a step replaces it; closing removes the key. A link to what the reader
  may not see opens the page with one plain line ("That visitor is no longer kept (journeys are kept
  7 days).", "Not available to your role."). *Privacy:* no address ever holds an IP address, an email
  or a person search: they become a token (`~` + 10 characters, `js/routemask.js`) only the browser
  that made it reads back. This fixes Requests' `ip=` filter and a drill-down by address, which put
  the IP in links; old links are rewritten on load. *Who:* everyone; old links keep working. *Do:*
  nothing. *Checked:* `tests/js/routes.mjs` (each opener writes its key, a link reopens it, Back
  closes it, missing ids and roles get the line, every key state.js reads is registered, and no value
  in 40+ written addresses is an IP or holds "@"); `tests/test_routes.py`; and in Chrome on the demo
  (the visitor drawer reopens on reload and Back closes it).
- **Copy and open in a new tab on every URL and page path** (`js/urlactions.js`,
  `css/urlactions.css`). On hover or keyboard focus two icons appear at the cell's edge without moving
  anything: **Copy** writes the full URL (a path joined with `https://` + the site's name), shows a
  green tick for 1.5 s, then hides; **Open** opens it (`noopener noreferrer`). A refused copy says
  "Copy failed: select and copy". Always shown on touch screens; the row's own click still works.
  Where: every table and grid column of pages (Pages, Landing pages, Search, AI and crawler pages,
  Not found, Health, Speed, Events), referring sites, Requests' request and referrer, the visitor
  drawer's journey and visits, leads' and bookings' landing page, Live's lists, the drill-down title,
  the page story, the set-up and connection dialogs' URLs, webhook URLs, the API file list, AI
  answers' citations and the site switcher. *Who:* everyone. *Do:* nothing. *Checked:*
  `tests/js/urlactions.mjs` (labels, full URL copied, tick and its end on fake timers, failure, href
  and rel, the row never clicked, every path/url column draws them, no page column lacks the flag).

### Fixed

- **"Lead hook tested" was ticked while its sentence said the last delivery was refused** (Overview's
  set-up list). *Why:* `setup-items.js` counted every hook in state "received" as done, but
  `conversions/roads.py` keeps "received" with `attention` after a refusal. *Fix:* a hook that needs
  attention is never done: the line is to do ("leads are not arriving"), with the cause and fix under
  "For your server admin". A signed test Skald itself sends (`X-Skald-Test: 1`) whose signature fails
  is now logged `test_failed`, not `bad_signature` (`conversions/hooks.py`), so it never reads as real
  leads refused. *Who:* sites with a lead hook. *Do:* if the line turns to do, give the tool the
  secret again. *Checked:* `tests/js/setup.mjs`, `tests/test_conversions_hooks.py`.
- **The set-up list did not name its site:** it is now "Set up example.com".
- **Once hidden, the set-up list was reachable only through Ctrl/Cmd+K.** It is now always at the top
  of **Settings › Connections** for owners and admins (all ticks and "All set" once done); Overview's
  "Hide this list" became "Hide on Overview" with the note "Always in Settings › Connections". Both
  checked in `tests/js/setup-checklist.mjs`; help: Getting started and Connections.
