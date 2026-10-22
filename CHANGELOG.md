# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

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
  check showed spaceo.ai's "Your server shows its exact version: nginx 1.18.0" twice (once for
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

## 2.20.1 (2026-10-21)

Three fixes the owner reported from the live site on 2026-10-21: a vulnerability scanner shown
as a live person, a tall empty box in the visitor drawer, and a 404 for a site whose setup is not
finished.

### Fixed

- **A vulnerability scanner was counted, and shown live, as a person.**
  - **What was seen:** on one site, Overview's "What visitors are doing now" listed a visitor
    from Hong Kong, "from" the site's own `wp.` subdomain, "now on /". In about two seconds that address, sending the user
    agent "Chrome" and a forged referrer of the site's own `wp.` subdomain, asked for
    `/.env.production.local`, `/.env.development`, `/.env.dev`, `/.env.bak`,
    `/.env.development.local` (404) and `/.env.prod.bak`, `/cdk.out`, `/outputs.tf`,
    `/variables.tf`, `/terraform.tfvars.json`, `/appspec.yml`, `/main.tf` (499).
  - **Why:** two faults. (1) The scanner-path list (`PROBE`, `classify.py`) caught
    the `.env` files, so those rows were "bot: scanner probe", but knew no cloud or Terraform
    file, so those rows were "people: client error". (2) A probe only ever moved itself: the
    requests around it, from the same address and agent in the same second, stayed people. With
    its `/` they made a visit: a reader, a page view, a landing, a source, a city dot and a live
    visitor.
  - **Fix (a), the list:** `PROBE` now knows infrastructure and deployment files no site serves
    on purpose, by file shape (an extension or name at the end of a path segment, never a bare
    word): Terraform (any file ending `.tf`, `.tfvars`, `.tfvars.json`, `.tf.json`, `.tfstate`,
    `.tfstate.backup`; `/.terraform/`), AWS CDK (`cdk.out`, `cdk.json`, `cdk.context.json`),
    CodeDeploy and CodeBuild (`appspec`/`buildspec` `.yml`/`.yaml`), Serverless
    (`serverless.yml/yaml`), SAM (`samconfig.toml`), Kubernetes (`kubeconfig`, `/.kube/`,
    `kustomization.yaml`, `skaffold.yaml`), CI (`/.gitlab-ci.yml`, `/.travis.yml`,
    `/.circleci/`, `/.github/`, `Jenkinsfile`, `bitbucket-pipelines.yml`,
    `azure-pipelines.yml`, `cloudbuild.yaml`), `Dockerfile`, and package files.
  - **Decisions made (say if you want them otherwise):**
    - `/template.yaml` (CloudFormation), `/values.yaml` and `/Chart.yaml` (Helm) are probes
      **only at the root**; a deeper path with those names could be a real page or file.
    - Lock files (`composer.lock`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`,
      `Gemfile.lock`, `Pipfile.lock`, `poetry.lock`, `Cargo.lock`) are probes **anywhere**;
      manifests (`composer.json`, `package.json`, `Gemfile`, `Pipfile`, `requirements.txt`,
      `go.mod`, `Cargo.toml`, `pyproject.toml`) **only at the root**.
    - Added beyond the list asked for: `cdk.json`, `.tf.json`, `.tfstate.backup`, `/.github/`,
      `Dockerfile`, `cloudbuild`, `bitbucket-pipelines`, `azure-pipelines`, `kustomization`,
      `skaffold`, and the other ecosystems' lock and manifest files.
    - Left out: `.yml`/`.yaml`/`.toml`/`.json` in general, `/terraform/` or `/kubernetes/` as
      words, and any manifest below the root. Real pages such as `/terraform/`,
      `/main-features/`, `/composer/`, `/templates/` and `/fonts/x.ttf` do not match, and the
      made-up sitemap (`tests/fixtures/site_paths.txt`, 475 pages) still matches nothing.
  - **Fix (b), one probe marks the whole visitor** (CLASSIFICATION.md rule 6b, COUNTING-TRAPS.md
    trap 17): an address and user agent that asked the site's hosts for a secret or config file
    on a day (new name list `SECRET_PROBE`: the dotfile, dump and backup, key and credential,
    infrastructure and package families of `PROBE`), or sent an attack in a URL
    (`PROBE_QUERY`), is a scanner for that whole day on that site. Every other request it made, before the
    probe or after it, is filed under bots as **"bot: scanner (asked for secret or config
    files)"**; the probes themselves stay "bot: scanner probe" and are still the `probes`
    count. None of its requests can be people, page views, a visit, a landing, a source, a live
    visitor, a city dot or a journey. The same address with another browser stays a person.
    Our own traffic, named crawlers and link previews come first, as before.
    - **Decision: not every probe marks the visitor.** WordPress paths (`/wp-content/`,
      `/wp-json/`, ...), server-side scripts (`.php`, ...), admin panels and debug routes, and an
      app's settings files (`/config.json`, `/appsettings.json`, `/env.js`, `/firebase*.json`)
      still make their own request a probe, but mark no one. Real readers ask for them too:
      every reader of a WordPress site loads `/wp-content/`, the owner opens their own `/admin`,
      an app loads its settings as it starts. The first version ("any probe") turned every
      reader of a WordPress client site into a scanner; the suite caught it
      (`test_client_site_settings.AssetRowsCount`). The live scanner is still caught: its `.env`
      and Terraform files are secret or config files.
    - **How:** the same two-pass mechanism the rendering rule uses. The first pass over the
      window (`window._classifier`, the new `classify.Scanners`) keeps every address and agent
      that sent a probe; the classifier then files all their requests. So a probe at 23:50
      moves a page read at 10:00, and the groups still add up to the log. The daily run's
      window is the day; the live run reads the day so far, so a visitor shown at one live run
      is gone at the next run after its probe.
    - **The audit** finds the same pairs with its own code (`audit.Judge._scanners`, sharing
      only the `SECRET_PROBE` and `PROBE_QUERY` lists), which every recount that uses the judge
      (daily, live, real time, crawler cost) follows.
    - **Where it shows:** a new row in bots' agents and in AI & bots > Crawler cost,
      "scanner (asked for secret or config files)", whose user-agent strings are not kept (as
      for scanner probes: they may be a person's browser).
  - **Fix (c), live:** "What visitors are doing now" never lists a visitor whose requests include
    a probe; it follows from (b).
  - **Who it affects:** every site. People, page views, readers and the breakdowns drop by the
    scanners that were counted; bots rise by the same number of requests.
  - **What to do:** stored days keep the old figures until recounted. Run `backfill --force`
    for the days you want corrected (owner: you said you will run it). Today's live figures
    correct themselves at the next live run.
  - **How it was checked:** `tests/test_scanner_visitor.py` (15 tests): the live scanner's twelve
    paths and 29 more are probes that mark the visitor, ten paths real readers ask for
    (WordPress, `/admin/`, `/config.json`, `/env.js`, ...) are probes that mark no one and a
    WordPress reader and an app's reader stay people, 25 real-looking pages are not probes, the
    sitemap fixture matches none; on one fixture (the live scanner with its page before and after its probes, a probe
    first, a probe last, and an honest visitor on the scanner's address with another browser)
    only the honest visitor is people and the groups add up; the audit says "all match"; a
    mutation that marks a scanner only after its probe (as a one-pass reader would) keeps the
    pre-probe pages as people and the audit catches it ("people: visits: history has 3, the
    recount finds 1"); and the live run lists only the honest visitor in "doing", with
    `audit --live` ok.
- **The visitor drawer drew a page seen in the browser as a tall empty box.**
  - **What was seen:** on one site, a visitor's drawer ("2 pages (1 seen in
    the browser)") showed `/insights/` as a normal chip, then `/telemedicine-app-development/`
    as a dashed green box hundreds of pixels tall, with the path at its bottom.
  - **Why:** that step carried the CSS class `app`, which is also the dashboard shell's class
    (`app.css`: a grid with `min-height: 100vh`), so the chip became a grid as tall as the
    window.
  - **Fix:** the step's class is now `jm-app` (`js/journeymap.js`, `css/visitor.css`); it is the
    same small chip as every other page, and only its dashed border marks it.
  - **Who it affects:** every journey with a step seen in the browser, on every site; the drawer
    only. No figure changed. Nothing to do beyond upgrading.
  - **How it was checked:** a render test (`tests/js/journey-steps.mjs`, run by
    `test_firsttouch.DrawerOutcome`) asserts the step has the chip classes, no shell class and
    no inline style or height, and that the CSS gives it only `border-style: dashed`; screenshots
    of the drawer at 1440 wide before and after.
- **A site whose setup is not finished answered 404.**
  - **What was seen:** `https://app.skaldanalytics.com/traffic/foxcue.com/` gave nginx's bare
    404. The site was added in the dashboard, its wizard stopped at step 3 of 5, and the site
    picker still showed its card with "Setup: step 3 of 5, continue".
  - **Why:** nginx serves `/traffic/<site>/` as a static file from the dashboard folder, and
    the runs draw a page only for an active site with data. A site with no log line yet, or one
    that was removed, has no folder; the container also rebuilds the dashboard folder from
    nothing when it is made again. (Checked read-only on the server: foxcue.com was added at
    13:49 UTC, reached step 3, and was **removed** at 14:24 UTC; its setup row stayed, so the
    picker still offered "continue".)
  - **Fix:** every dashboard write (`ti.py dashboard`, every live run) now writes a small page
    (`setup_page.py`) into the folder of each known site that has no page:
    - **Waiting site:** "<site> is waiting for its first log lines", the wizard step it
      reached, a **Continue setup** button opening the Add a site wizard at that step (the same
      link as the picker's badge, `#settings/sitesadmin?setup=<site>`, on a site of the same
      organisation that has a dashboard), or **Test the connection** when the setup is
      finished, a link to the troubleshooting guide (`#help?part=troubleshooting-connections`),
      and "All sites". It reloads itself every minute; the site's first run draws its real
      dashboard over it.
    - **Removed site:** "<site> was removed", the day, that nothing is collected, and that its
      data stays until an install admin purges it. No setup button.
    - It is written only where there is no page or where the page is this one, so a real
      dashboard or the "Getting ready" page is never replaced. It holds no figure, address or
      token. Sign-in is unchanged: it is a file in the dashboard folder, behind the same auth.
    - The picker no longer offers "Setup: step N of 5, continue" for a removed site.
  - **Decisions made (say if you want them otherwise):** a removed site gets an honest
    "was removed" page, not "waiting" (continuing its wizard would collect nothing, and there
    is no restore); so foxcue.com will say "was removed" after this ships, and measuring it
    again means purging and adding it again. The page is static, so it cannot tell admins from
    other members: everyone sees the button, and the page says setup is for owners and admins.
  - **Who it affects:** installs with sites made from the dashboard. Nothing to do beyond
    upgrading.
  - **How it was checked:** `tests/test_setup_page.py` (11 tests): a waiting site, a finished
    setup and a removed site; the link equals the picker's badge; a real dashboard and the
    "Getting ready" page are never replaced; the page follows step changes and gives way to the
    real dashboard; no host; nothing written for sites with data; a failure never breaks the
    dashboard; and a live run end to end after the folder is lost. Docs: `docs/SETTINGS.md`
    and the "Continue later" part of `docs/help/connections.md`.

## 2.20.0 (2026-10-21)

Leads & sales, redone: one question per tab, every lead in one list (with names and emails for
owners and admins), and the same tidy toolbars, gaps and empty states on every page.

### Added

- **Leads & sales > Leads: who are my leads?** One row per lead of the period, newest first:
  when, name and email, what they did (with its label), its stage now (completed, won, lost,
  cancelled, no-show), where it came from (the lead database, a booking tool, the page's script tag
  or the site's server), the source and the first touch, the landing page and the country. A row
  opens the visitor drawer with the lead's steps and pages. Until now no page listed leads with
  their names: only Find a person showed one at a time (the owner asked where they were).
  - **Who sees names and emails:** owners and admins only, and only on a site that keeps them
    (`conversions.identity: full`, Settings > Data retention > People). Everyone else gets the
    same list without those columns, and one line saying why. The names come from a new helper
    call, `GET <page>/people/leads?first=&last=[&names=1]`: `names=1` needs an owner or admin
    and the session's CSRF value (basic mode: a same-origin request), and each answer with names
    writes one audit row, `people.leads`, "lead list viewed" with the period and the row count,
    never a name or an email. Names never go into a data file a viewer could fetch; the public
    demo shows the list as a viewer sees it.
  - **No new figure:** the count above the list is the Leads figure itself (the same sum as
    Overview's Leads tile), with the change against the period before. The list's counted rows are
    the very rows that figure counts; `tests/test_people_leadlist.py` checks they are equal.
  - **One options row:** What, Label, Stage now, Source; under **More**, **Show left out** (test,
    spam and duplicate leads, marked, never counted).
  - **Four views of the same leads**, picked with small icon buttons at the right of the row and
    kept in the address (`lview`): **List**; **Board** (a column per stage now; read-only, stages
    come from the site's tools); **Timeline** (leads per day, split by what they did or by source;
    a day's bar opens the list on that day); **Map** (leads by country). The timeline and the map
    draw the Leads figure's own days and breakdowns, so no view can disagree with the count. The
    switcher (`js/viewswitch.js`) is built for other sections to use later.
- **Help in context, on Leads & sales first:** an (i) beside a tab's title, its options row and
  each number opens a short popover with **Learn more** into the right part of the guide; the long
  paragraphs that sat in the page moved into the (i) beside their heading. Summary's numbers say
  what they count, the days they cover and how they compare with the period before. The (i) is the
  shared one (`tiles.js info`), so any page can add a Learn more link.
- **Overview, Today · Live: "What visitors are doing now".** The map now runs across the page,
  and under it one block shows, on the left, the five visitors with the newest activity (active in
  the last 30 minutes): flag and city, device, where they came from, and their pages in order,
  `/ → /pricing → /book-a-demo`, the page they are on now marked ("now on /pricing · 20 s ago");
  a long path is cut in the middle, whole in its tooltip. It follows the live answer every 15
  seconds: a new visitor slides in at the top, one who moved gets the new page appended, one who
  went quiet fades out (no motion with reduced motion). On the right, **Pages read in the last 30
  minutes**, the same figure and audit as before: a page narrows the list to the visitors who read
  it, a second press opens its detail. A row under the pointer pulses its city on the map, and a
  city marks its rows; a row opens the visitor drawer. With a drill-down (`dd=country:CA`, a city,
  a source, a referring site or assistant, a device, a landing page or a page read), the map shows
  that place and the list only its visitors, with "N shown"; a kind the live rows do not carry (a
  campaign, an hour) says "Live list shows every visitor: this filter can't apply to it". It
  replaces the Newest visits panel and the pages list under the map, so a visit is shown once.
  The rows come from Real time's answer, which now carries `doing` (the active visits, newest
  activity first, at most 50, each with its pages in order: labels and paths only, as the newest
  visits and the journeys); `ti.py audit --live` recounts each row's start, country, pages and
  newest request, and that every active visit is listed.
- **Filters you set show as chips above every table and grid** ("Stage: completed ×"); the ×
  takes one off, **Clear all** takes them all off.

### Changed

- **Leads & sales has seven tabs, each answering one question in plain words under its title:**
  Leads, Summary ("How many leads came in, and is it better than before?": Leads, Demos booked, Won
  and Lost against the period before, every action side by side, the best sources), Sources ("Where
  did the leads come from?": where the completed ones came from, first, last and assisted touch,
  likely from AI, the time to convert, the pages seen before), Calendar bookings, Funnels, Events
  and Find a person. **Pipeline** is now Summary and Sources: every figure is the same, counted by
  the same code; nothing is counted anew. **Count from** (lead database or tools, never added) is a
  quiet option at the right of Summary's and Sources' row. Old links keep working:
  `#sales/pipeline` opens Summary with its options, `#leads` and `#conversions` open Summary from
  the lead database or the tools. The keyboard's `g e` opens Leads.
- **Bookings is now Calendar bookings,** and says plainly what it holds: calls booked through
  Calendly and Cal.com, and payments Stripe reports where a site sends them. The route stays
  `#sales/bookings`.
- **People is now Find a person.** Its "Recent people" list is gone: the Leads list replaces it,
  one row per lead, with names for owners and admins.
- **The period is chosen in one place, the top bar.** The Period select is gone from Leads &
  sales' options rows.
- **One toolbar row on every table and grid.** Search and filters on the left; Filter, Columns
  and Export on the right, on the same row (it wraps when narrow); the row count and the pager sit
  under the table. On grids the tools used to sit on a row of their own above the search, so the
  toolbar was split over two rows with a gap (the owner's screenshot of Bookings); a small card's
  table now puts its tools, as icons, on the card's title line, and a section's table on the
  section's heading line, instead of a row of their own. The export button says **Export** on
  every table; what it writes ("CSV, 37 rows, 8 columns") is on hover and read to a screen
  reader. **Columns** shows "6 of 8" only when some are hidden. Grids: no "0 of 0" and no page-size
  choice under an empty or short list; the request log's export moved onto its grid's row.
- **One spacing scale and one control height.** Sections, cards and options rows use the same
  gaps (8, 12, 16, 24 px), buttons, search boxes and selects are one height (32 px), and notes and
  help lines never run wider than about 90 characters.
- **Empty states are one line and one button** ("This site has no lead database connected. Its
  leads come from its tools" with **Show leads from the tools**), and an empty grid is one compact
  line instead of a big box.

### Fixed

- **Summary from the lead database on a site that has none** (`#sales/summary?lsrc=db`, the old
  Pipeline's "Count from: Lead database") showed an empty, silent page. It now says "This site has
  no lead database connected. Its leads come from its tools (the lead hook, the script tag, booking
  tools)", with **Show leads from the tools** and a link to the help on connecting one.
- **A grid printed the word "null" under its rows for a moment while they loaded** (its pager
  appended an empty page count). Vendored data grid, Skald patch 9.

### Who it affects, and what to do

Everyone who opens Leads & sales: nothing to set up. Owners and admins of a site that keeps names
and emails see them on Leads; to stop keeping them, set **Leads' names and emails** to anonymous in
Settings > Data retention > People. Links and bookmarks to the old tabs keep working.

### How it was checked

`python3 -m unittest discover tests` ends OK. New: `tests/js/live-doing.mjs` (the paths, folded; the live diff; a page narrowing the list; `dd=country:CA` showing only Canadian rows and an unsupported filter its line) and `test_realtime` (`doing` lists every active visit, newest activity first, and the audit fails on a tampered row); `tests/test_people_leadlist.py` (the list's
counted rows equal the Leads figure; names only for owners and admins, only with the CSRF value or
same-origin, never on an anonymous site; one audit row with no value in it; a bad period refused;
test rows listed, not counted) and `tests/js/sales-leads.mjs` (the tab names; Name and Email columns
only in an answer that holds them, a viewer never asks for them; Show left out; the board; a row
opens the drawer; the view switcher). Changed: `tests/js/tables.mjs` (one toolbar row, the count
under the table, the chips), `tests/js/pipeline-label.mjs` (Summary's Label option; the
no-lead-database message and its button), `tests/test_routes.py` (the old addresses). Every tab and
Settings page, the visitor drawer and the setup dialogs were screenshotted before and after at
1440 and 1280 px wide, and the main pages at 390.

### Changed

- **Onboarding: the Next.js log line is a requirement, with why it is safe, and a new site is
  checked end to end.** The owner's own phone visit to one of the sites showed only its first page: on
  a Next.js site, pages opened by a click inside it need ` rsc_prefetch=$http_next_router_prefetch`
  at the end of the server's nginx `log_format` (Apache: ` rsc_prefetch=%{Next-Router-Prefetch}i`).
  The client runbook (`deployments/skaldanalytics.com/ADD-A-CLIENT-SITE.md`), Help > Connections
  and the install kit's READMEs now say it is required for every Next.js site and why it is safe
  (it adds one header's value to the server's own log; no port, route or access changes; nginx
  escapes odd values; the log already travels over HTTPS with the site's token). A new section,
  "Check a new site end to end", lists the proof a site is live: a desktop and a phone visit with
  clicks inside the site, the doctor, the live audit, a test lead and the setup checklist.
  Who: anyone adding a site. What to do: nothing for existing sites, except one site's admin
  adding the line. Checked: the docs build (tools/build-about.py) and the suite.

## 2.19.0 (2026-10-21)

A site's server can keep its own team's leads out of the figures, without asking Skald's admin.
Also: the changelog's 1.0.0 to 2.7.1 entries moved to docs/CHANGELOG-2.0-2.7.md (the file had
passed 1,000 lines); nothing was removed.

### Added

- **A site can mark its own test leads.** Leads a site's own team makes (team accounts, QA
  runs) were counted as real unless the server admin marked them with `conversions
  mark-test`. Now the site's server does it itself, two ways, both the same mark as the CLI's:
  kept, listed under Left out and in the lead check, never counted.
  - `"test": true` in the lead body (a JSON boolean) keeps that delivery's row as test.
    `false` or absent: a real lead, as before. Any other value is ignored with a note in the
    answer and the delivery log, and the lead counts. Each delivery says it for itself, so send
    it on every stage; a resend that differs only in `test` changes nothing.
  - `POST /traffic-hooks/<site>/leads/test`, body `{"refs": [...], "test": true}` (1 to 100
    refs; `false` unmarks), signed exactly like the lead POST with the same secret. It marks
    every stage of each ref that came through the site's `lead` hook, and a later stage sent
    for a marked ref is marked too. Answer `{"ok", "test", "marked", "already", "not_found"}`;
    400, 401, 404, 429 as the other lead calls. Each call writes one delivery-log row (counts
    only) and one audit-log entry (actor `hook:lead`, the counts and the refs).

  Who: sites that send leads from their own server (the `lead` hook). What to do: send your
  team's own accounts with `test: true`; to fix leads already sent, call `leads/test`
  (docs/help/leads-from-your-backend.md, section 10, has curl, Node, Python and PHP). Nothing
  changes for a site that does neither. Marking or unmarking moves the counted figures of past
  days at the next dashboard build; the lead check (`GET .../leads`) shows it at once. The
  second count now leaves test rows out per stage, not per lead, so a stage sent as test and
  a later real stage are both counted right. Checked by `tests/test_lead_test_marks.py`
  (26 tests: the body field, inheritance, signature, clock window, 404, bad bodies, over 100
  refs, refs not found, only `lead` rows, mark and unmark, rate limit, delivery and audit log,
  the lead check, and conversions.json and the second count agreeing after a mark and after
  an unmark) and the full suite.

## 2.18.1 (2026-10-21)

### Fixed

- **Leads did not show for sites added in the dashboard.** Their leads were stored and counted,
  and the lead check returned them, but Leads & sales and the Overview Leads tile looked for them
  in the site's own state folder instead of the install's, found none, and said "no conversions
  yet". Only the first site of an install showed its leads. Every site now reads the one store the
  lead hook, the script tag and the booking tools write to. Seen on three sites of one install;
  nothing was lost.

## 2.18.0 (2026-10-21)

Next.js pages counted, lead labels, and a way for a site's server to check every lead reached Skald.

### Added

- **Pages opened inside a Next.js site count.** A click inside a Next.js site loads no page from
  the server, only a `?_rsc=` request, and Next.js sends the same request to prefetch links, so a
  plain log cannot tell them apart and Skald counted neither: every page after the first was
  missed. When the site's log records Next.js's prefetch header, Skald counts each real click as a
  page view of its path, never a prefetch, and an HTML page and a click of the same path within 2
  seconds once. The line to add: nginx ` rsc_prefetch=$http_next_router_prefetch` at the end of the
  `log_format`; Apache ` rsc_prefetch=%{Next-Router-Prefetch}i`; Caddy logs headers already. Without
  it, nothing changes. Counted twice, by the audit's own reader. The doctor, Set up this site (with
  a dialog, the lines to copy, Share with your developer and a Test), the install kit's `check.sh`
  and the site check tell a Next.js site, and no other.
- **A label on a lead:** `label` in the lead body, such as `sales` or `support`
  (`^[a-z0-9][a-z0-9_-]{0,39}$`). Kept with each stage, shown as a tag in Pipeline, People and the
  person drawer, and a Label filter in Pipeline's Tools view; the per-label counts are recounted by
  the conversions audit. The MCP `conversions` tool takes `label`. Conversions schema 7.
- **Check that Skald has every lead:** `GET /traffic-hooks/<site>/leads?since=<time>`, signed
  with the lead hook's secret over `"<t>.GET <path>?<query>"`, read-only: `external_ref`, `action`,
  `stage`, `at`, `label`, `test` and `received_at` only, never a name, email or address, in pages
  of up to 500. Resending a lead Skald has is a no-op, so a daily reconcile can resend every ref
  missing from the answer. The image's nginx now passes GET on `/traffic-hooks/`.
- **The script tag** counts a page restored from the browser's back-forward cache.

### Fixed

- **Leads & sales > Pipeline was empty for a site with no lead database.** It counts from the
  lead database by default, so a site whose leads come only from its server's lead hook, the script
  tag or a booking tool showed nothing until you chose "Count from: Tools". With no lead database
  and no choice made, it now opens the tools' view. (Reported for freshlycited.com.)
- **The word "null" in setup dialogs** (Get the daily mail, Add a site step 3): a step's left-out
  part was printed. The shared dialog now drops empty parts, and the tests fail if any page ever
  draws null or undefined.

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

## Older versions

- 2.8.0 to 2.13.0 (18 October 2026): [docs/CHANGELOG-2.8-2.13.md](docs/CHANGELOG-2.8-2.13.md).
- 2.7.1 and earlier (8 to 12 October 2026): [docs/CHANGELOG-2.0-2.7.md](docs/CHANGELOG-2.0-2.7.md).
