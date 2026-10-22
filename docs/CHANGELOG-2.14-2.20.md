# Changelog: 2.14.0 to 2.20.1

The releases of 18 to 21 October 2026. Newer ones: [CHANGELOG-2.21-2.22.md](CHANGELOG-2.21-2.22.md) and [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.8-2.13.md](CHANGELOG-2.8-2.13.md).

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
