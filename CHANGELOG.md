# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

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

## Older versions

2.7.1 and earlier (8 to 12 October 2026): [docs/CHANGELOG-2.0-2.7.md](docs/CHANGELOG-2.0-2.7.md).
