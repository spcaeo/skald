# Changelog: 2.23.0 to 2.26.0

The releases of 22 October 2026. Newer ones: [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.21-2.22.md](CHANGELOG-2.21-2.22.md).

## 2.26.0 (2026-10-22)

Page groups fill their past days from the screen; a lead is found by its own reference; marking
test and soft-removing by reference from the command line; one lead per reference and action
(no double count when a sign-up also sends paid); MCP can be switched on in Docker with
`SKALD_MCP=true`; the complete leads reference (docs/LEADS-REFERENCE.md).

### Fixed: what a lead's drawer says when it has no visit

- **What changed:** a conversion opened on its own (Leads, Conversions) with no visit linked
  now reads "Conversion", "Visits: None linked" (with why: no visitor ID sent, or no page view kept
  for it) and the outcome is the stage it reached ("Completed", "Paid"). The reference section is
  titled "Reference and steps".
- **Why:** the 2.25 drawer said "Visitor", "0 visits on one day" and "Outcome: No lead linked" for a
  lead sent by the site's server, and "Reference" twice. All of that was wrong.
- **Who:** anyone opening a lead from a site's server. **Do:** nothing.
- **Checked:** tests/js/visitor-drawer.mjs, and a fresh screenshot.

### Fixed: a lead that paid later said "Stage now: Completed"

Leads' Stage now (the column and the drawer) now follows a later `paid` as it already followed
won, lost and the booking stages; the lead is still counted once, on its completed day. Checked
with tests/test_lead_mark_drawer.py.

### Fixed: the Sites card said "It applies from the next run" while it was filling

When a save starts the past-days fill, the line now says the new groups' past days are filled in
the box below, and the box's own line clears when the fill is done. Checked with tests/js/views-fill.mjs and a screenshot.

- **Find a person finds a lead by any reference.** *Seen:* 2026-10-22, while writing
  LEADS-REFERENCE.md: Find a person, the API's `people?q=` and MCP `find_person` read any 8 to
  80 letters, digits and `_ . : -` as a visitor ID, so an app's account ID such as `u-1234567`
  was never found by its reference (`u-1001`, shorter, was). *Changed:* only the real visitor-ID
  shape (`skv_` and 22 characters, as the page script makes it) is a visitor ID; any other
  reference is looked up as the lead's `external_ref` on that site, and also as a site's own
  visitor ID (a site that sends its own session IDs still finds them), listed as a visitor ID
  only when one matched (`people/lookup.py`). *Who:* owners and admins, and agents with
  `read_private`. *Do:* nothing. *Checked:* `tests/test_people_lookup_refs.py` (`u-1234567`,
  `u-1001`, a real `skv_` ID, a site's own ID, an email), the existing lookup tests.
- **One lead counts once.** *Seen:* 2026-10-22, LEADS-REFERENCE.md: a reference sent under a
  lead action (contact, signup, waitlist, trial, demo) as both `completed` and `paid` counted as
  two leads, in the Leads figure, the Leads list, Every action and the breakdowns. *Changed:*
  one site, tool, `external_ref` and action is one lead, on the day of its first finished row
  (earliest `at`, then the stage's name). The other finished row stays: listed among the
  lead's steps, marked `repeat` in conversions.json's `today.rows` (Overview's What converted
  today skips it), left out of every figure as a test row is (`store.repeat_finishes`). Other
  actions (`paid`, `deal`...) count every row as before. Both counting roads changed and agree:
  the main road (conversions_data, the Leads list, today's listing and by-hour) and the second
  counts (the spool recount groups its own lines; audit_conversions_figures,
  audit_conversions_leads and audit_client_reports use their own SQL NOT EXISTS).
  *Who:* any site whose server sent both stages for one ref under a lead action. *Do:* nothing
  to run: conversions.json is rebuilt from the store on every run, so such a site's past days
  show one lead per ref at its next build (within 2 minutes of the upgrade), and the second
  count agrees. That is the recount of the stored days; mails and client reports already sent
  keep the old number. *Checked:* `tests/test_conversions_one_lead.py` (same day, next day, paid
  first, a test first stage, a non-lead action; both roads agree; a main road that counts the
  repeat is caught and withheld; the Leads list; today's flags and hours), the full suite.
- **The admin works by reference: `conversions mark-test --ref` and a new `conversions
  remove`.** *Seen:* LEADS-REFERENCE.md: the CLI marked test only by row id, and the soft remove
  existed in the code (`store.remove`, used by the lead-database sync) but no command reached it;
  a wrong stage could only be fixed by `forget`, a hard delete of the whole person. *Changed:*
  `ti.py conversions mark-test SITE --ref REF [--ref REF...] [--tool T] [--unmark]` beside the
  row ids: every stage of each ref, with `store.mark_refs`, the function `POST .../leads/test`
  calls; it prints rows changed, already so and refs not found, and writes one audit row with
  the refs. New `ti.py conversions remove SITE --ref REF [--tool T] [--stage S] [--action A]
  --why "text" [--dry-run]`: each row copied whole into `removed` with when and why (Show left
  out > Removed, Find a person), out of every count; refused without `--why`; `--dry-run` lists
  what would go; one audit row `conversions.remove` with the ids, ref and why. The spool
  recount skips a removed row's lines received before the remove (`removed_keys`), so the
  second count still agrees, and a corrected resend afterwards is a new row counted on both
  roads. *Who:* server admins. *Do:* nothing. *Checked:* `tests/test_conversions_one_lead.py`
  (mark and unmark by ref, not found, no ids and no ref refused, remove refused without why,
  dry run, remove one stage and every stage, the removed listing, the audit lines, a resend
  after a remove; the second count after each).
- **MCP can be switched on in Docker: `SKALD_MCP=true`.** *Seen:* 2026-10-22, on Skald's own
  server `POST /traffic-mcp` answered 404 from outside and from 127.0.0.1:8080 inside. *Cause:*
  the helper answers 404 ("MCP is not switched on here") unless the config says
  `mcp: {enabled: true}`; a Docker install that makes its config from the `SKALD_*`
  environment had no variable for it (the image's nginx always passed the path on). *Changed:*
  `SKALD_MCP=true` sets `mcp.enabled` (`docker/entrypoint.py`), passed by docker-compose.yml,
  listed in INSTALL.md, MCP.md and DEPLOY.md. The steps for Skald's own server (the env line,
  the host nginx location, the probes, a token with the `mcp` scope) are in
  `deployments/skaldanalytics.com/README.md`, not applied yet. *Who:* Docker installs that want
  MCP. *Do:* add `SKALD_MCP=true` and start the container again; a front proxy must pass
  `/traffic-mcp`. *Checked:* `tests/test_install_files.py` (off by default, on for true/1/yes,
  sessions mode, the image's nginx location), `tests/test_hosting_container.py` (Compose and
  INSTALL.md list it).
- **The dashboard's MCP messages name `SKALD_MCP`.** Settings › Connections' "MCP is not
  switched on here" box, the test's 404 line and the help's troubleshooting table now say
  "mcp.enabled; on Docker, SKALD_MCP=true". *Who:* owners and admins setting up an assistant.
  *Do:* nothing. *Checked:* the help rebuilt (`tools/build-about.py`), the suite.
- **The demo builds again.** *Seen:* 2026-10-22, `tools/demo.py` stopped with `KeyError:
  'start'` in Retention's answers: the 2.25 loop that hides a script-tag reference reused the
  cohort's variable name `c`. *Changed:* its own name (`conv`). *Who:* whoever builds the demo
  or screenshots. *Do:* nothing. *Checked:* a full demo build with `--keep`.
- **Screenshots for the reference features** (sample data only, 1440 light, from the demo's
  kept install with one made-up sign-up `u-1048576` sent through the real lead hook as
  completed and then paid): `public/docs/screenshots/person-by-reference.png` (Find a person by
  a lead's reference), `leads-reference.png` (Leads with the Reference column: the sign-up is
  one row), `lead-drawer-reference.png` (its drawer: the reference, both steps, Mark as test).
  The README gallery is not changed here.
- **LEADS-REFERENCE.md brought up to these changes**, and linked from the public README's
  Integrations. It and INTEGRATIONS-LEADS.md now also say the duplicate key leaves out the
  action: a `trial` `started` for a ref that has a `signup` `started` is dropped as a duplicate
  (one action per ref). *Who:* apps sending leads. *Do:* keep one action per ref. *Checked:*
  each changed line against the code above (`store.record_conversion`); the duplicate rule
  also on the live install.

- **Settings > Sites > Views: a new page group's past days are filled from the screen.**
  *Seen:* 2026-10-22, on skaldanalytics.com the owner saved two page groups ("Security pages",
  "Free check"); each showed in the page-group menu but its past days were empty until
  `backfill --days 9 --force` was run on the server by hand. *Changed:* a save of Views now
  answers which groups it added or changed (a renamed group is a new one) and which it removed.
  Under the Views box, **Fill past days for the new groups** is ticked by default: the page then
  starts the fill at once (unticked, it offers a button). The fill runs on the server in the
  background (`ti.py --site S views refresh`, new, also for the shell) for every whole day the
  raw log still holds: each day counted once with the site's rules, each new group's day
  checked, then recounted by a new, separate audit road for page groups (`audit_views.py`:
  requests, requests by group, people's visits and readers, responses by status); a day that
  does not match is withheld, never shown. The site's own days are not touched. The box shows
  "Filling 9 days… 4 of 9", then "Done: 9 days filled, all audited", and says plainly "Days
  before 13 Oct can't be filled: the raw log is kept 14 days". On a group's own pages those
  earlier days read "not recorded for this group", never 0. One fill at a time per install;
  owners and admins only (or an install admin); same-origin and CSRF; audit log `views.fill`,
  and a `backfill` marker when it ends. A removed group leaves the menu with nothing to
  recount. *Who:* anyone adding page groups. *Do:* nothing on Docker; on a systemd install the
  refresh helper's user must be able to write the history and read the logs, as the daily run
  does (DEPLOY.md); no nginx change. `backfill --force` still works as before. *Checked:*
  `tests/test_views_fill.py` (the save answer, only the days the log holds, progress states, one
  at a time, roles and CSRF, the audit agreeing and withholding a day that does not),
  `tests/js/views-fill.mjs` (the offer, the default start, progress and done, with mocked
  answers), the full suite, and a sandbox install with the real helper and job (screenshots
  `views-fill*.png`).

- **docs/LEADS-REFERENCE.md: one page for an app that sends leads.** *Why:* a site's own
  developers (and their AI sessions) asked for one place to send, check, mark and read back
  leads; the facts were spread over five docs. *What:* the lead hook and every other tool, the
  body and its rules, the answers and limits, the reconcile GET and test marks, the read API
  and MCP (and what neither can do), the admin commands with their exact flags, the screens,
  and the mistakes to avoid. Linked from INTEGRATIONS-LEADS.md, API.md and MCP.md.
  INTEGRATIONS-LEADS.md also said the `leads/test` answer's key was `unknown`; it is
  `not_found`, as the code always sent. *Who:* anyone sending leads. *Do:* nothing. *Checked:*
  every statement against the 2.24.0 code; the curl signing recipes against Skald's own verify
  functions; the test suite.

## 2.25.0 (2026-10-22)

A lead's own reference in Leads and every drawer, Mark as test from the screen, a new site's logo
at once, and a privacy fix: a script-tag lead's reference (built from its visitor ID) is shown only
to owners and admins.

- **Leads: the lead's own reference.** *Seen:* 2026-10-22, the owner on a client site's
  Leads & sales > Leads (today) could not see the client's own account IDs (`u-119797`...), so
  could not find a lead in the client's admin. *Changed:* a **Reference** column (the sender's
  `external_ref`), hidden until **Columns** shows it (kept in the address, `ld_hide`), with a copy
  icon; the search box finds a lead by it either way, and the CSV export always holds it. The
  lead's drawer says "Reference: u-119797 (from example.com's server)" (or the tool's name) with
  the copy icon, and lists every step of that reference, oldest first, with its stage and time
  (a test lead's steps too, which before showed none). *Who sees it:* everyone who can see the
  leads: it is the sender's record number, not a name or an email, and the Conversions lists
  have always shown it to every member. Except the page script's own reference, which is made
  from the visitor ID (`<vid>:<action>:<stage>:<at>`): owners and admins only, like a visitor ID.
  *Also fixed:* the Conversions lists (cancelled, test) sent that script-tag reference, and so
  the visitor ID, to every member; now only to owners and admins (`people/policy.shown_ref`).
  `people/leads` rows gain `ref`, steps gain `test`.
  *Who must act:* nobody. *Checked:* `tests/test_lead_mark_drawer.py`, `tests/js/sales-leads.mjs`,
  `tests/js/leadref.mjs`, the demo at 1440 px.
- **Mark as test / Not a test in every lead's drawer** (owners and admins). *Seen:* marking a
  team account's lead needed the server's command line or the site's signed call. *Changed:*
  every drawer that shows a lead or a conversion (Leads' lead drawer, the visitor drawer's
  "Leads and conversions", Find a person, the Conversions lists, Calendar bookings' rows, which
  now open a drawer) shows the reference, its steps and **Mark as test** (on a test lead, **Not
  a test**), from one shared part (`js/tabs/leadref.js`). A confirm step first ("Mark u-119797 as
  test? It stays listed under Show left out and leaves every count."), then a toast; the page
  reads its files again, so the row moves to or from Show left out and the counts follow. It
  calls the new `POST <page>/people/mark-test` (`people/marktest.py`): the same mark as `ti.py
  conversions mark-test` (`store.mark_test`, every stage of that tool and reference, a later
  stage follows), same-origin and with the session's CSRF value like every admin write, 403 for
  a viewer or an editor, one audit row with the user, the tool and the row ids (never the
  reference or a name), the audit's cache dropped and the live build run. `conversions.json`'s
  `today.rows` and the visitor timeline's conversions gain `id` and the reference. *Who must
  act:* nobody. *Checked:* `tests/test_lead_mark_drawer.py` (the endpoint by role, CSRF and
  same-origin, every stage marked and unmarked, the audit row, the Leads figure and the second
  count after a mark and an unmark), `tests/js/leadref.mjs` (the button by role in each drawer,
  the confirm, the POST, the toast), the demo at 1440 px.
- **A new site's logo is fetched when the site is added.** *Seen:* 2026-10-22, a site added in
  the dashboard showed its letter "T" until its logo was fetched by hand; before, only the
  morning run asked. *Changed:* adding a site (Settings > Sites, the Add a site wizard, sign-up,
  `ti.py site add`) asks the site for its logo at once, on the new site's first-page thread
  (never holding up the add; a failure is noted in the journal without an address), then
  rewrites `sites.json` so the switcher shows it. The site picker asks again, on a thread and at
  most once a day, for a site still showing its letter. *Who must act:* nobody. *Checked:*
  `tests/test_site_logo_on_add.py` (a local test site; the add in Settings and on the CLI; the
  picker's once-a-day rule).

## 2.24.0 (2026-10-22)

The script tag works with no change on the site's server: it posts its events to where it was
loaded from, and Skald accepts them from the site's own hosts only. The setup Test checks the page
and says what's wrong.

### The plain script tag works with no change on the site's server

- **The script tag posts to Skald itself.** *Seen:* twice on 2026-10-22 on the live install,
  two client sites put the documented tag
  (`<script src="https://<your Skald>/traffic-js/skald.js" data-site="..." defer>`) on their
  pages; `skald.js` then posted every event to `/traffic-beacon` on the **page's own** address,
  which only works when the site's server passes that path on to Skald. Without it the site
  (Next.js) answered 308 or 405, nothing arrived, and the set-up dialog's Test waited forever.
  *Changed:* with no `data-endpoint`, `skald.js` now posts beside the address it was loaded from
  (`.../traffic-js/skald.js` gives `.../traffic-beacon`, same origin, same folder). Loaded from
  Skald, it posts to Skald; loaded from the page's own `/traffic-js/skald.js` (the first-party
  set-up), it posts to the page's own `/traffic-beacon` exactly as before. `data-endpoint` still
  wins; a copy served from another folder posts to the page's own address, as before. The
  visitor ID stays in the page's own storage (and the page's own cookie with
  `data-share-subdomains`), unchanged. The tag on a page twice (a first-party copy and Skald's,
  or Tag Manager plus the HTML) now runs once, so a page view is never sent twice. 6,132 bytes,
  under the 6 KB budget.
- **The beacon helper takes cross-site posts, safely.** A post is taken only when its `Origin` is
  `https://<one of that site's hosts>` (the per-site map that already chose each site's spool;
  the first site's `beacon.origins`); `Sec-Fetch-Site` may be `same-origin`, `same-site` or
  `cross-site` only for such an Origin, never `none`. Any other Origin, `null` or none: 403 as
  before. Answers to a known Origin carry `Access-Control-Allow-Origin: <that origin>` and
  `Vary: Origin`, never `*` or credentials. The request stays CORS-simple (`sendBeacon` with a
  `text/plain` Blob, or `fetch` with `keepalive`), so there is no preflight and `OPTIONS` stays
  405. Rate limits, the 1 KB body, validation, Do Not Track and the bot rule are unchanged. A
  direct post comes from the visitor's own address, so no proxy trust is needed for it. A post
  with `X-Skald-Probe: 1` answers 200 with `X-Skald-Beacon: 1`, reads no body and counts
  nothing (for the page check below).
- **Add the script tag: the simple tag first, the first-party way folded.** Step 2 gives the
  plain tag and says nothing changes on the web server; "Advanced: serve it from your own domain"
  holds the nginx, Apache and Caddy lines and the first-party tag (fewer ad blockers stop it),
  and that Skald must then trust that server for `X-Forwarded-For`. The same in Settings >
  Connections' "Only the script tag", the developer's mail and the Add a site answer. Tag Manager
  is listed under "Where it goes".
- **The Test looks at the page.** While nothing from the tag has arrived, Test connection also
  asks Skald to fetch the site's home page (`POST <page>/sites/tagcheck`, new
  `tag_check.py`, by the site check's safe-fetch rules: public addresses only, at
  most 3 redirects, 256 KB, no cookie) and says what is wrong in plain words: the tag missing (or
  maybe inside Tag Manager), a page host that is not one of the site's host names (403), a
  first-party script that does not load, a post address that answers 308, 404 or 405 ("The tag is
  on your page but posts to www.example.com/traffic-beacon, which answers 308. Update to the
  latest tag..."), or a Content-Security-Policy whose `connect-src` leaves Skald out. Admins only;
  30 checks an hour per admin and 6 per site in 10 minutes. The shared developer page does not
  run it (it needs a session).
- *Who:* every site that uses the script tag. *What to do:* nothing for sites on the plain tag:
  they start sending once this version is deployed (a browser that loaded the old `skald.js`
  keeps it up to a day). First-party set-ups keep working unchanged. A site with a
  Content-Security-Policy adds the Skald address to `connect-src`. Skald's own nginx needs no
  change: the existing `location = /traffic-beacon` proxies the POST and passes the helper's
  CORS headers through. *Counting:* unchanged: each event is still one request by one road, nginx
  still logs each answer once with the site's name, and the audit's two counts match whichever
  way a post came (tested). *Checked:* new tests: `skald.js` in a fake DOM (cross-origin,
  same-origin, a folder, a copy elsewhere, `data-endpoint` overriding, `fetch` without
  credentials, the tag twice), the helper (a cross-site post into that site's spool with CORS
  headers; another Origin, `null`, no Origin and `Sec-Fetch-Site: none` refused; refusals keep
  their rules; no preflight; the probe counts nothing; the audit's nginx and spool counts equal
  for direct and proxied posts), the page check (each answer, the private-address refusal, the
  probe carries no cookie) and its endpoint (admins only, 409 with the tag off), and the dialog
  pieces in a fake DOM. Full suite OK.
- *Docs:* `docs/BEACON.md` ("Where the tag posts"), `docs/INTEGRATIONS.md`, `docs/HOSTING.md`
  (and its public copy), `docs/VERCEL.md`, the help guides (the tracking script, connections,
  troubleshooting connections), and the client-site runbook.

## 2.23.0 (2026-10-22)

Leads & sales opens on 7 days with All time and "Today so far"; one filter row with five filter
fixes; Add a site can build the kit zip without the token; the morning run no longer skips sites
after one fails; the README's "One log, two answers" and docs and screenshots brought up to date.

### Docs and screenshots brought up to 2.22

- **Docs and screenshots brought up to 2.22.** *Seen:* the owner, 2026-10-22: "the screenshots
  and demo on git are old ... all documentation needs to be updated too". The GitHub page still
  showed the 2.13 Pipeline, five menu sections, "Search Console import is on the roadmap" (synced
  since 2.13) and 1,800 tests; the demo's Search tab said "Connect Search Console", Connections said
  it needed a running Skald, the live "doing" rows showed one page each, Security on Today had no
  attempts beyond one injection and "Large POST bodies: not recorded", and Site > Health had no
  heartbeat. *Changed:*
  - **README (GitHub page):** "What's new" cut to the last releases with a link to the changelog;
    the feature list now has six sections, every view's link and copy/open, Leads & sales' seven
    tabs and the Leads list, leads you can check (label, test marks, the signed lead check),
    Security, Connecting a site and Next.js; the comparison gains two rows (scanners and attacks
    from the log, advisories matched to your stack: Skald ✓, GA4 and Plausible ✗, the rest not
    checked) and "Blocking attacks" under where others lead; the roadmap loses the done Search
    Console import; the gallery is grouped by section. "One log, two answers" unchanged.
  - **Docs:** `docs/ROADMAP.md` (a 2.15 to 2.22 table; 2.13/2.14 no longer "on a branch"),
    `docs/USE-CASES.md` (Leads & sales' new tabs, Search synced, Security answers the ops rows),
    `docs/WHY-SKALD.md` and `docs/WHY-WE-BUILT-SKALD.md` (what 2.16 to 2.22 added; six sections),
    `docs/COMPARISON.md` (Skald's column as of 2.22.3; Security under where Skald leads),
    `docs/INTEGRATIONS.md` and `docs/INTEGRATIONS-LEADS.md` (Pipeline, People and Bookings by
    their 2.20 names), `docs/HOSTING.md` and its public copy (Connections, the site check and the
    install kit), `docs/INSTALL.md` (`SKALD_KEEP_IPS=short`), `docs/ROUTES.md` (`ca`, `cdim`;
    Calendar bookings), `DEPLOY.md` (the optional `rsc_prefetch=` and `request_length=` fields),
    `public/docs/POSITIONING.md` (14 MCP tools, 2,600+ tests, Security, hosted beta, Search
    synced), help `getting-started.md` (six sections, the Security and AI answers tabs) and
    `real-time.md` (Overview shows what visitors are doing, not the newest visits), the
    marketing site's features page (six sections, links and copy/open, the Leads list, labels and
    test marks, "What visitors are doing now", Next.js, a Security and a Setting up block),
    `docs/marketing/launch-posts.md` and `security-posts-2026-10.md` (current version, Security
    wording rules, /check/ live), `HANDOVER/00` and `03`, `public/PUBLISH-CHECKLIST.md`. This
    changelog had passed 1,000 lines: 2.14.0 to 2.20.1 moved, whole, to
    `docs/CHANGELOG-2.14-2.20.md`, and the links to them follow.
  - **Screenshots retaken** (`public/docs/screenshots/`, from the demo built from the public export,
    1440 wide, light, the hero also dark; 256-colour PNG: 46 images in 3.5 MB, the folder was 17.8
    MB): hero-light, hero-dark, social-preview, overview, overview-today, overview-live, live-mode,
    realtime, compare-mode, traffic-sources-grid, visitors, visitors-drawer, filters,
    places-cities, search, retention, leads-list (the 7-day default), sales-bookings,
    conversions, conversions-removed, leads-left-out, live-leads, funnels, ai-assistants, ai-read,
    ai-assistant-cost, ai-fetch-formats, crawler-cost, crawler-detail, crawl-health, ai-answers,
    the seven security-* images, connections, setup-checklist, links-copy-open, help, mobile.
    **Added:** sales-summary (replaces sales-pipeline), public-check (the /check/ page drawing
    Skald's own answer for a recorded corpus case). **Removed:** sales-pipeline.png,
    security-exposed-light.png (nothing referenced them). **Kept as they were** (the static demo
    cannot draw them; HANDOVER/00 lists them): person-search, person-lead, privacy-ip-choice,
    privacy-notice, settings-team, logo-settings, integrations, integrations-status,
    reports-preview, ai-answers-profiles, add-site-wizard, connections-install, site-check,
    site-picker, site-switcher, mcp-claude, skald-doctor.
  - **The live demo shows sample data where it said "not recorded" or "needs a running Skald":**
    Traffic > Search (made-up Search Console and Bing answers read by the real sync,
    `tools/demo_search.py`, the clicks drawn from the demo's own Google visits so the cross-check
    is close, never equal); Settings > Connections with the set-up list and three made-up tokens
    (the list's two answers worked out by the same code from the demo's install, no folder of the
    build machine named; `demo.js` `api.setup`, `checklist.js`, `connections.js`, `main.js`; its
    buttons say why they do nothing); "What visitors are doing now" (the visitors of the last half
    hour read several pages); Security on Today (login hammering today), yesterday's possible
    exposure and its alert, a refused 2.6 MB upload, and `request_length=` on every demo line so
    large POST bodies are recorded; Site > Health (a 5-minute heartbeat with one 15-minute outage);
    alerts switched on (shown, never mailed). *Who:* readers of the GitHub page and the demo.
    *To do:* nothing until the next release publishes it. *Checked:* `tests/test_demo.py` (two new
    tests: Connections' answers from files with no build path; both engines synced, the newest day
    provisional), the full suite, `audit` on a kept demo day ("all match"), every section and tab
    of the demo walked in headless Chrome, `tools/build-about.py`, the site build ("problems:
    none"), `tools/make-public.py` ("sweep CLEAN"; two code comments that named client sites were
    reworded for it).

### Fixed

- **One site's failure no longer stops the morning run for the others.** *Seen:* on
  2026-10-22 the 07:15 run failed on one site and never ran the two sites after it, so their
  day was not collected until it was done by hand. *Why:* with several sites, a crash in one
  site's run was raised straight out of the loop over sites. *Fix:* each site runs on its own;
  a crash is recorded for that site (as before, in its runs.json and the failure mail) and the
  next site still runs; the run's exit code is still the worst one. *Who:* installs with
  several sites. *To do:* nothing. *Checked:* a test with four sites where the second crashes.
- **A redraw no longer deletes another run's half-written file.** *Seen:* the same failure:
  "No such file or directory: .../_app/js/.table.js.<random>.tmp". *Why:* each redraw copies the
  shared app files and then removed every file it had not just written, including the temp
  file of a redraw running at the same moment (the 2-minute live run). *Fix:* temp files are
  left alone unless they are over an hour old (left by a crash). *Checked:* a test with a fresh
  temp file (kept), an old one (removed) and a file the app no longer ships (removed).

### Changed

- **The install kit: "Include the access token in the zip", ticked by default.** *What:* in
  Add a site, step 4 (Install), and in Connections > Send this site's visits to Skald, the box
  above "Download the install kit (.zip)" is now ticked by default, with one plain line under
  it. Ticked: "The kit is ready to run. Treat the zip like a password: send it only to the
  site's admin." Unticked: the zip holds no token in any file, the token shows under the box
  with a Copy button to send separately, and `install.sh` takes it from a `ship-token` file the
  admin makes, else the new environment variable `SKALD_SHIP_TOKEN`, else asks for it (not
  echoed); a run with none stops and says the three ways. The kit's README.txt has a new part,
  "If the token is not in this kit". The choice is in the page's address while unticked
  (`token=0`, never the token) and leaves with the dialog. The box is drawn again when a token
  is made on the same step (before, in the wizard, the box never appeared there, because the
  token is made on the step the box is on). *Why:* the owner asked for a zip with and without
  the token, with the token in by default. *Who:* owners and admins adding a site or sending a
  site's visits; site admins running the kit. *To do:* nothing; a kit downloaded before keeps
  working. *Checked:* tests for the zip with the token (in `ship-token` only) and without it
  (every file scanned, no part of the token), the installers in dry runs reading
  `SKALD_SHIP_TOKEN`, stdin and an admin-made `ship-token`, and stopping with none; the page
  test (ticked by default, `token=0` written and read back after Back and Next, the zip asked
  for with and without the token, the key gone on close, the wizard's box after Make a token).
  The kit download is not written to the audit log, before or now.
- **README: "One log, two answers".** The GitHub page now says plainly that the same access log
  answers who visits and who probes, with a real scanner from our own site (150 requests in 14
  seconds for AI provider credentials, `.env` and Terraform files, all answered 404, redirect or
  dropped), the Security reports, and what Skald is not (no blocking, not a WAF).
- **Story page `/security/ai-key-thief/`: the hero is about the thief, and every figure explains
  itself.** *Seen:* the owner's review on 2026-10-22. The hero art (two birds) did not say "AI-key
  thief"; the chart and the log had no annotations; nothing on the page moved or invited a tap.
  *What:* a new hero story (about 8 s, then held, with Replay): the live visitor card from Sheung
  Wan glitches, its mask slips, and a hooded thief reaches for a ring of keys (Bedrock, OpenAI,
  Anthropic, LiteLLM, .env, Terraform, each with its mark) while a counter runs through the log
  second by second to 150 requests in 14 s; Skald's spotlight catches him, each key is stamped
  with the answer it got most (404) and "Nothing leaked" drops in. A slow living sky behind the
  hero. "AI-key thief" and "AI keys" are marked in the headline and the lead. The two-birds scene
  moves to its own section, redrawn (a cleaner developer; two different attackers, a disguised
  "Fake visitor" and a red "Scanner" with a crowbar), replaying every 12 s while in view. New:
  a key card per family (mark, count, a real example path, its answers, "404 · nothing leaked"),
  a stacked bar of the answers, the chart with axis labels, four callouts found in the log, a
  playhead and each second's requests on tap, the log with column notes, coloured paths,
  answer pills, three side notes and a magnifier in plain words, numbered hotspots and a zoomable
  lightbox on the Security screenshots, a story progress bar, a "Is your site leaking AI keys?"
  check card and a second share row. The story video is the new 50 s cut (`video.mp4`,
  `cover.webp`). The share card is redrawn from the hero's last frame. *Who:* readers of the
  page. *To do:* nothing. *Checked:* every figure, callout, key, stamp and per-second list
  recounted from the log by the page's tests (a second road), both stories in headless Chrome
  (reduced motion shows each last frame; the birds wait until in view), the full suite, and
  screenshots at 390 and 1440 px in light and dark.

### Added

- **A story page on skaldanalytics.com: "We built Skald to count visitors. It caught an AI-key
  thief."** (`/security/ai-key-thief/`). What: the owner's first-person story, as agreed
  and checked fact by fact, beat by beat: the live view showed a "visitor" from
  Sheung Wan, Hong Kong; the server log showed 150 requests in 14 seconds hunting AI keys
  (Bedrock 27 paths, LiteLLM 7, OpenAI proxies 5, Anthropic and Claude 3), `.env` files (17),
  Terraform (9) and AWS deployment files, all answered 404 (96), 308 (26) or dropped (19), the
  only 9 answers being the public home page and its 8 scripts. The page has a hero animation
  ("two birds, one stone": inline SVG and a small script, no library; plays once in about 6 s,
  pauses off-screen, Replay; with reduced motion, or without JavaScript, it shows its last
  frame), the live-view row recreated and labelled as such (a marked slot for the owner's
  screenshot), 12 real log lines, a requests-a-second chart coloured by what was hunted, the
  families and the answers, Skald's Security section as seven tabs with their screenshots
  (sample data) and live-demo links, "Built for this week's threats" (php2shell and the
  Node.js October releases, with sources), last week's 50 s story video behind a "Watch" fold,
  share links, copy and open on every URL shown, and a share card
  (`img/share-ai-key-thief.png`, `tools/make-share-cards.py ai-key-thief`). Why: the owner's
  story of the scanner seen on spaceo.ai on 21 Oct 2026, told with only verified facts. Every
  figure about the scanner is counted from the real log (the scanner's address replaced with
  203.0.113.7) on each build (`_src/thief_log.py`), never typed in. Linked from `/security/`
  (a card at the top), the php2shell guide, `/check/` and the home page's security band; in the
  sitemap; `Article` and `BreadcrumbList` JSON-LD. The story video (82 s, 9 MB, served from the site
  itself, `preload="none"`, its cover as poster) sits under the hero, behind `thief.HAS_VIDEO`. One difference from the agreed story, written on
  the page as the log has it: not every request names wp.spaceo.ai as referrer; 124 do, and the 26
  that followed a redirect name www.spaceo.ai. Who it affects: readers of skaldanalytics.com.
  What to do: nothing until the site is deployed (owner's go). Checked:
  `_src/test_thief_page.py` (the tags and JSON-LD; the chart, families, answers and prose
  recounted from the log by a second road; the quoted lines and the share card's lines found in
  the log; no address but 203.0.113.7; reduced motion shows the last frame and the animation
  starts from the first, in headless Chrome; one report tab at a time), the site's other tests,
  the full suite, and screenshots at 1440 and 390 px, light and dark.

### Changed

- **Leads & sales opens on the last 7 days.** The owner, live on 2026-10-22: freshlycited.com's
  `#sales/leads` said "0 leads · No lead in this period" while the site had 5 sign-ups on 20 and
  21 Oct. The page had opened on Today, the dashboard's default, carried over from Overview, and
  today had no sign-up. Now each section has its own default when the address names no period
  (`state.js` `SECTION_RANGE`): 7 days on every Leads & sales tab, Today elsewhere. An explicit
  `range=` always wins; a period picked is written to the address and stays from tab to tab
  and section to section; a default is never carried into another section (Overview's Today,
  or Live turned on there, opens Leads & sales on 7 days). Who: everyone. To do: nothing; a
  bookmark of `#sales/...` without `range=` now opens on 7 days. Checked: `tests/js/leads-period.mjs`
  (every sales tab, an explicit range, the move from Overview, a named period carried through),
  `tests/test_routes.py`, the demo in a browser.

### Added

- **All time, a period everywhere** (`range=all`, the top bar's period control, the report
  builder, the palette). From the first day the site has data (history's first day, or the
  leads' first day, `conversions.json` `since`, when earlier) to the last whole day, like every
  other preset; the period line says "All time: since Fri 21 Aug 2026, 62 days". Summed from
  the same day files as every other range, so no new figure and no new audit. The dashboard
  holds 180 days: when a site's data begins earlier, the line says "All time held here: the
  last 180 days ... this site's data begins ...", never a total that claims days it lacks.
  Checked: `tests/js/leads-period.mjs` (first day, the earlier leads' day, the cut), the demo.
- **Leads: a period with no lead says where the leads are.** "No new leads in the last 7 days.
  5 leads in the last 30 days." with **Show last 30 days** and **All time**, or "N leads since
  <first day>" when the last 30 days hold none; "No leads yet" and the setup hint when there
  is none at all. Both counts are the Leads figure (`leadfigs.js` `leadsOn`) over those days,
  narrowed by the same filters. Checked: `tests/js/leads-period.mjs` counts the same days on
  its own and compares.
- **Leads: one filter row.** The options row is the filter row; the table's own **Filter**
  button is gone from Leads (`grid.js` `columnFilters: false`; an old `ld_cf` is not applied);
  the top bar's Filters a lead carries (source, country, device, campaign) now narrow the list
  and the figure; every filter on, from either place, is one removable chip in a **Filtered
  by** line with **Clear all**, and a top-bar filter a lead does not carry is a greyed chip with
  the reason (the top bar's own chip row and banner stand aside on Leads: tab option
  `chips: "tab"`). The count line says what is applied: "5 leads · filtered: Source = Search
  engine". Who: everyone on Leads. To do: nothing. Checked: `tests/js/leads-period.mjs`, the demo.

- **Leads & sales: "Today so far" beside a period of whole days.** 7 days and All time count
  whole days only, so a lead that came in today was not in the default view (the owner,
  2026-10-22: "I thought there was data there"). Every Leads & sales tab with a period that ends
  before today (Leads, Summary, Sources, Calendar bookings, Funnels, Events) now shows one line
  when today has leads: "Today so far: 3 new leads → Show today (live)"; the button sets
  `range=today`. N is the live Leads figure, the same as Overview's Leads tile today
  (`leadsOn` over today, every lead before the page's filters); it is never added to the
  period's own figure. No line when today has none. All time stays whole days (to the last
  whole day): adding today's live part to it would mix verified days with a live count in one
  figure, and Summary, Sources and the other sections' All time would then disagree with
  Leads; the line covers today instead. Checked: `tests/js/leads-period.mjs` (N = 0 gives no
  line, N equals the live Leads figure, the period's figure unchanged, the button, every tab,
  none on Find a person or Security), the demo.

### Fixed

- **Leads: the count ignored the Source filter.** With **Source** chosen, the list narrowed but
  "N leads" stayed the whole period's figure. It is now the figure of that source
  (`conversions.json` `by.source_type`, already recounted by the second count). Two breakdowns at
  once, a label with a breakdown, **Stage now** or **Show left out** cannot be the figure (the
  figure keeps each breakdown on its own); the line then says "8 listed", beside the period's
  figure, and why.
- **Leads: a link with `lnow=out` alone listed nothing.** Stage now: Left out needed Show left
  out as well; it now lists the left-out rows by itself.
- **Leads: the timeline by source and the map came out empty with a Label on**, as if there
  were no lead (labels are counted by stage only, never by source or country). They now say they
  are not split by label. The timeline by source with a country, device or campaign filter says
  the same instead of an empty chart.
- **Leads: the top bar's country, source, device and campaign filters were not applied** (the
  tab took none and said "This tab shows all visitors"). They now narrow the leads.
- **Top bar: a filter chip was greyed "not on this tab" on tabs that apply it** (Traffic >
  Places & devices with a country, Sources with a source, ...), and the banner said the filter
  did not apply. The check compared a re-tidied copy of the rule by identity, so it never
  matched (`filterpanel.js` `applies`, `rulesBanner`). The figures were filtered; only the chip
  and the banner were wrong. Checked: `tests/js/leads-period.mjs` fails without the fix.
