# Changelog: 2.42.0

The release of 26 October 2026. Newer ones: [CHANGELOG.md](../CHANGELOG.md); older ones: [CHANGELOG-2.39-2.41.md](CHANGELOG-2.39-2.41.md).

## 2.42.0 (2026-10-26)

A simpler dashboard, screen by screen. Each screen shows state and one action; help and method
text sit behind a "?"; every task that has a doer asks one question first, **Who will do it? Me /
My developer / My AI agent**, then shows only that path. Settings has a menu on the left and
opens on To do. Measured at 1440 px on the sample data, before → after: AI & bots › Assistants
5,969 → 830 px; Traffic › Sources 4,653 → 896; Overview › Summary (7 days) 2,584 → 1,393;
Site › Alerts 3,536 → 856 (14 cards → 3, each with Fix); Leads & tools 3,078 → 712 (one screen);
Help 2,238 → 830; Add a site 5 steps → 2; Export 47 controls → 6. Compare is on by default.
Also: "visits active" in Real time no longer misses a visit that ended in the last seconds of the
30 minutes.

### Upgrade

- Nothing to do. Old addresses (Settings pages, `fixby=`, `#sales/revenue?by=`, Add a site's
  `step=3/4/5`, `agent=hand`, `dlg=report`) open their new place.
- Bookmarks of the crumb trail still work; the trail now shows only "← Back to …".

### A simpler dashboard, part 1: the shared pieces

- **Added.** One visual system for every screen (`css/ui.css`, `docs/UI-RULES.md`): one card
  style, five status pills (good, waiting, broken, off, info), one accent colour kept for the one
  main button of a screen, a faint tint of each area's colour behind the top bar, and fixed sizes
  for corners and text. It uses only the colours Skald already had. Why: the owner found screens
  crowded, with many buttons of the same weight and no colour for status (UX audit of 26 Oct).
  Who: everyone, as screens move to it. What to do: nothing. Checked: `tests/test_ui_system.py`
  measures every pill and the main button at 4.5:1 or more in light and dark.
- **Added.** Four shared pieces in `js/ui/`: the "?" that opens a short help with "Read the
  guide" (opens on a press, so phones work; Escape closes it), status pills, folds ("3 done"),
  and the one main button. And "Who will do it? Me / My developer / My AI agent" (`ui/who.js`):
  the first question of a fix or set-up dialog, which then shows only that path, using the agent
  line, the developer link and the steps by hand that already exist. The choice is in the address
  (`by=me|dev|agent`) and remembered per person in this browser. Checked: `tests/js/ui.mjs`.
- **Changed.** Revenue's breakdown in the address is now `rby=` (was `by=`), because `by=` is
  the new "Who will do it?" choice. Old links still open the same breakdown. What to do: nothing.
  Checked: `tests/js/revenue.mjs`, `tests/js/ui.mjs`.

### A simpler dashboard, part 2: Overview, Site › Alerts and the top bar

- **Changed.** Site › Alerts shows one card per kind of alert, the most urgent first, each with a
  pill, instead of one card per alert (the sample: 14 cards became 3; the page went from 3,536 px
  to 856 px at 1440 wide, 7,492 to 1,273 on a phone). **Fix** asks "Who will do it? Me / My
  developer / My AI agent" and shows that path only: the steps (for a possible exposure, the line
  for nginx with a copy icon; for an advisory, its item on Security › Your stack; for a path, its
  recent requests), a message for your developer with a link to the alert, or the AI agent line
  where the kit has the job (logging stopped). In the address: `alfix=<kind>&by=me`. The method
  text is behind the "?"; closed alerts and **Which alerts are on** are one line each
  (`alerts_view=switches` opens the switches). Why: the owner found 14 cards with no button on any
  (UX audit, task 1). Who: everyone with alerts. What to do: nothing.
- **Changed.** The Site badge, the bell and Site › Alerts count the same thing: the kinds that need
  you (urgent or worth a look), so 14 open alerts of 3 kinds show 3, not 14.
- **Changed.** Overview › Summary opens on the figures. The set-up checklist is one line
  ("Set-up: 1 left · Mail recipient confirmed", **Finish set-up**, **Show the list**); in Live mode
  the map, what visitors are doing now and the flow are on Real time only (the flow moved there),
  and the footnote is behind the "?". The live Summary went from 2,942 px to 1,090 px at 1440 wide
  (5,441 to 2,217 on a phone); its figures start at 232 px instead of 498.
- **Changed.** The top bar went from 17 controls to 11: 7, 30 and 90 days stay, Yesterday, All
  time and Custom are under **More** beside them; Refresh (now **Recount today now**), saved views
  and export are in the three-dot menu at every width; Help is in the menu only; one **Search or
  jump to** (Ctrl K) also finds a person for admins, so the separate Find a person box is gone.
- **Changed.** Insights' window buttons count cards, as "Show all N" does (was findings: 31 beside
  29 cards), and the note says "29 cards from 31 findings". Data quality says "Today's log lines so
  far: Good" and names the scheduled jobs that are late, failed or never ran beside it.
- **Changed.** Insights' Fix this uses the same "Who will do it?" step: Me, My developer, My AI
  agent, in that order, the last answer remembered. Its answer is `by=` (mails now link
  `&fix=1&by=agent`); older `fixby=` links still open the same answer, `someone` as My developer.
- Checked: `tests/js/si-alerts.mjs`, `tests/js/ov-setup.mjs`, `tests/js/todos.mjs`,
  `tests/test_ux_overview_alerts.py`; the full suite with and without PyYAML; before and after
  screenshots at 1440x830 and 390x844, light and dark, in `docs/plans/ux-build-shots/`.

### Settings v2: a menu on the left, To do first, one button per page

- **Changed.** Settings is a menu on the left and the page on the right, 13 pages in groups:
  **To do**, **This site** (Data, Leads & tools, Site, Privacy, Mail & reports), **AI** (AI
  assistants, AI answers), **Organisation** (Sites, People, Billing, Audit log) and **You** (Your
  account). The card page (All settings), the Set-up checklist page and Help & docs are gone:
  Help is in the sidebar's foot.
- **Added.** **Settings > To do** (`#settings/todo`, where Settings opens): one list of what
  needs you, most important first: the site's open set-up lines, a site waiting for proof or
  paused, a plan 80% used or more, invites not accepted, two-step sign-in off, tokens unused
  for 90 days. Done lines fold into **N done**. Empty: "Nothing needs you. Everything is set
  up for example.com." **Find a setting** at the top.
- **Changed.** The set-up checklist (To do and Overview) has one title, a correct count
  ("2 left, 1 optional") and one button, **Finish set-up (N left)**. It asks **Who will do it?
  Me / My developer / My AI agent** (`setup=finish&by=me|dev|agent`); each open line is one
  button that asks the same for that line (`setup=finish-<line>`). It replaces **Set up
  everything left with your AI agent**, **Send set-up to someone** and each line's own Set up.
  It is the app's one "Who will do it?" (`js/ui/who.js`, shared with every other dialog that
  asks it): **Me** lists the open lines, each opening its own steps; **My developer** is the
  set-up pack; **My AI agent** shows **What it does** (each job ticked) and the agent tiles,
  and makes the line in the same dialog. It opens on the address's choice, else the one this
  person chose last in this browser.
- **Changed.** Every page has one title with a **?** (what it is for, its guide and docs, on
  demand), one primary button beside the title (Connect a tool, Connect the log, Add a site,
  Invite someone, Connect an assistant...), and rows with a status pill (Working, Waiting, Not
  working, Off). Long lists show 5 and **Show all (N)**. No glyphs in labels: line icons.
- **Changed.** **Leads & tools** has no tabs: each connected tool is a row with its pill; the
  row opens its details in a drawer (`tool=calendly`: address, secret, test event, deliveries,
  Remove). A red line with **Fix** only when something is broken. The tools not connected are
  one quiet line. **Send each lead out** (`tool=webhooks`) and **Search Console & Bing**
  (`tool=search`) are two small rows; **Every check** opens the checks (`tool=checks`).
- **Changed.** The pages that were forms are rows now: **Site** (Names & time, the logo),
  **Internal traffic**, **Privacy**, **Mail** and **Client reports**, **AI answers** (the lists,
  the profiles, the API keys), **Data**'s cards (log file, page assets, not pages, script tag,
  goals), **Sign-in rules**, **Billing**, **Audit log**, **Your account** and **Tokens &
  links**. Each setting is a row with its value in words, where it comes from, and a pill for
  on/off or set/not set; a card nothing in which is yours to change is one **Read-only** line.
  A row opens the card's form in a drawer, with one **Save** that wakes up on a change; the
  drawer's part is in the address (`edit=people`, `edit=report-12`, `edit=profile-p1`,
  `edit=ip-<code>`: an internal address by a code, never the address), so a link or a reload
  opens it and Back closes it. The page's one button sits by its title: **Add an address**,
  **Send a test mail**, **New report**, **New profile**, **New token**, **Download CSV**,
  **Turn on two-step sign-in** (only while it is off). The Audit log's filter is in the address
  (`aact=`). Internal traffic's figures moved behind a fold under the list. Measured at 1440 px
  (lines of text / page height in px, before → after, sample data): Site 38/1358 → 16/712,
  Internal traffic 41/1092 → 7/712, Privacy 36/1334 → 21/771, Client reports 19/796 → 18/712,
  AI answers 20/1085 → 21/712, its API keys 22/712 → 9/712, Your account 38/936 → 16/712; Mail
  16/712 → 20/712 (the values now show instead of a folded form) and Audit log 29 → 36 lines
  (two lines a change instead of a table row) are a little longer, both still one screen.
- **Changed.** Settings draws with the shared pieces (`js/ui/pill.js`, `primary.js`,
  `fold.js`, `help.js`, `who.js`, `css/ui.css`); its own copies of the accent, the pills and the
  "?" are gone from `settings.css`. Pills use the five shared kinds (good, warn, bad, off, info).
- **Changed.** The set-up dialogs (logs, page assets, Next.js pages, the script tag, the lead
  hook, privacy, Search Console) and Connect an AI assistant (MCP) open on the app's one
  "Who will do it?" (`js/ui/who.js` whoStep), in place of "Your AI agent, or by hand?": **Me**
  (the dialog's own steps, from step 2), **My developer** (the set-up in one mail or one zip,
  for logs, page assets, Next.js pages, the script tag and the lead hook) and **My AI agent**
  (the agent tiles, then the line and its watch, as before), in that order, the last answer
  remembered. In the address: `by=me|dev|agent`; an older `agent=hand` link opens Me. Why: one
  question, asked the same way everywhere (the coordinator's review of Settings v2). Who:
  owners and admins setting up a site. What to do: nothing. Checked: `tests/js/agent-jobs.mjs`
  (the answers per job, My developer's pack, Next refused until chosen, by=me and agent=hand,
  Back), `tests/js/setup-checklist.mjs`, `tests/js/connections.mjs`.
- **Added.** **Settings › This site › Alerts** (`#settings/site/alerts`): which alerts are on
  for this site and whether they are mailed. One line on top says where things stand ("16 of 17
  rules are checked with every live run, and mailed…"; off: "Alerts are off, so nothing is
  checked. 16 rules will run when you turn them on", never an "on" count that is not true).
  **Turn alerts on** is the page's one button, beside the title, only while alerts are off.
  All alerts and Mail alerts are two switches; the rules are in folds by area (Site health,
  Traffic, Crawlers & AI, Security, Sales), each "N of M on", a rule one line with its
  threshold behind its "?"; "not watched" on every row is gone; the sale minimum opens in a
  panel (`edit=alertmin`). The page is 712 px tall at 1440 wide and 661 px on a phone, where
  the same switches in one list were 1,450 and 2,720. Site › Alerts' switches fold is now one
  line, **Which alerts are on: N of M**, with a link here; an older `alerts_view=switches` link
  opens this page. Why: the switches are a setting, and Site › Alerts is for the alerts
  themselves (the Overview/Alerts builder's ask; the coordinator's review of the first cut).
  Who: admins and owners. What to do: nothing. Checked: `tests/js/set-alerts.mjs` (the state
  line on and off, the one primary, the folds and pills, one line per rule, a locked rule,
  the drawer), `tests/js/si-alerts.mjs` (the line, its link, the redirect),
  `tests/js/settings-menu.mjs`; screenshots `after3-settings-site-alerts*` in
  `docs/plans/settings-v2-shots/`.
- **Fixed.** The Settings menu cut off its last row at 830 px tall once it had fifteen pages, so
  **You** showed with nothing under it. Its rows are 28 px now (were 32): every row fits with
  room for Billing's. Checked in a browser at 1440x830.
- **Fixed.** Your account's sign-ins card wrote "null" with two to five sessions (a hidden
  "Show all" that was not there).
- **Why.** The owner, 2026-10-26: "This is like card card card... There should be a left
  navigation menu, and then on the right side, the action items"; "this has too many buttons";
  "such long screens... all the information, notes, etc. should be only on demand". The UX
  audit (docs/plans/ux-audit-2026-10-26) set the rules: one primary, a plain question first,
  rows with a pill, help behind a "?".
- **Who / what to do.** Everyone who opens Settings. Nothing to do: every older address opens
  its new home with its parameters (`#settings/home`, `#settings/site/setup`,
  `#settings/site/collect`, `#settings/ai/mcp`, `#settings/org/team`,
  `#settings/site/leads?sub=search` and the rest; the table is in docs/ROUTES.md).
- **Checked.** `tests/js/settings-menu.mjs` (the menu, the frame, the one primary beside the
  title, the old addresses), `tests/js/set-leads.mjs` (rows, pills, the red line and its Fix,
  the drawer and its address), `tests/js/set-parts.mjs` and `tests/js/set-account.mjs` (the
  pages that were forms: rows, pills, one primary, each drawer and its `edit=`, a link opening
  it, a save that updates the rows, an address never in the URL), `tests/js/settings-privacy.mjs`
  and `tests/js/views-fill.mjs` (their forms, now in the drawer), `tests/js/settings-todo.mjs` (every To do source and the
  order), `tests/js/routes.mjs` and `tests/test_routes.py` (old addresses, `setup=finish`,
  `by=`, `tool=`), the checklist and agent tests, before/after screenshots at 1440 and 390 px
  in light and dark (docs/plans/settings-v2-shots/), and the full suite with and without
  PyYAML.

### A simpler dashboard, part 3: AI & bots, Traffic, Leads & sales, Security and Compare

- **Changed.** Compare is on by default (the UX audit's task 5). With 7, 30 or 90 days, Yesterday
  or a custom period, every tab that compares sets the period against the same number of days
  before it, and the bar says "vs previous period"; no click needed (it was 4: period, Compare,
  Previous period, Compare). The address leaves that default out; another choice is written
  (`cmp=year`), and **Turn compare off** writes `cmp=off`, which stays as you move. Today, All
  time and a period that includes today are never compared, as before. A tab that does not
  compare has no Compare button and no "No compare on this tab" line unless a link asked for one.
  Why: the audit found the change against the period before was the figure people looked for
  and four clicks away. Who: everyone. What to do: nothing; links that said `cmp=prev` still open
  the same view. The Overview Summary on 7 days grows (2,584 to 2,728 px at 1440) because each
  tile and "What changed" now show the change.
- **Changed.** The top bar is the mockup's seven groups: the title, the period (Today, live, as
  its first choice; 7, 30, 90 days; More), Compare, Filters, Search, Alerts and More. Today was
  its own "Today · Live" switch; the page group list moved into the Filters panel (at its top),
  and a chosen group shows as a chip under the bar. That is 10 buttons on a tab that compares
  (17 on 2.41.0, 11 after part 2), 9 where Compare does not apply; the period group alone is 5
  of them, as in the mockup. Checked: `tests/test_routes.py` (compare on by default, off kept,
  Today and back), `tests/e2e/modes.mjs`, `topbar.mjs` and `layout.mjs` updated for the new bar.
- **Changed.** AI & bots › Assistants opens on the answer (the UX audit's task 4): three figures
  with their change (Visitors sent by AI, Pages AI read for someone, AI collecting for training),
  which assistant sent people and which read for someone (five each, then **Show all (N)**), and
  one card, "7 pages AI can't read well", with the screen's one primary button, **Let AI read
  the site better**. It asks "Who will do it?": Me (the pages by what to do), My developer (a
  message and a link), or My AI agent when Insights has a to-do the agent already fixes
  (Markdown copies, server errors, lost pages; it opens that to-do's Fix this). No new agent job.
  The day chart, the tables by name, the formats, the costs, the pages fetched, AI reading
  changes and the full list are under **Open the details** (`ai_view=open`). The page went from
  5,969 px to 830 px at 1440 (12,324 to 1,365 on a phone). Crawlers folds what they fetch, the
  costs and the address check the same way (4,139 to 1,819 px). Why: the answer to "which AI
  sent people" was four screens down. Who: everyone. What to do: nothing; every figure is the
  one shown before. In the address: `fixit=airead&by=me`. Checked: `tests/js/phase-c.mjs`,
  `tests/test_ux_sections.py`, before and after shots.
- **Changed.** One place for each control, and a shorter Summary (the UX build's polish).
  **Include today** and **Compare with the period before** were switches on Summary and
  Pages as well as in the top bar; now Compare is only the top bar's menu, and Include today
  is a check item in the period's **More** menu (the button reads "More · today" while it is
  on; still `inc=1`). The period line keeps the dates; what the period means is behind its
  (i). The trail line over each screen ("← Back to … · Overview › Summary › …") is now the
  **← Back to** link alone, and nothing when you came from nowhere; Back and Forward still
  walk every step. **Overview › Summary** keeps the key figures, the chart and What changed
  (5 rows each, then Show all; "About the same" behind its (i)) open, drops the "Key
  figures, each with its change" caption (each tile says its change), and folds the rest (countries, top pages and sources, AI
  assistants, who else came, pages to work on, new pages, server requests, each day) into
  **More for this period** (`ovx_view=open`): 2,728 to 1,393 px at 1440 on the sample data.
  Who: everyone. What to do: nothing. Checked: `tests/js/crumbs.mjs`,
  `tests/test_ux_sections.py`, before and after shots.
- **Changed.** Security, one action per screen (the UX audit's task 9). **Is anything
  exposed?** shows **Fix** in its verdict line only when there is a possible exposure; it asks
  **Who will do it?** (`fixit=exposed`): Me sees the paths by kind with the nginx line to copy,
  My developer gets a message with a link back. **Block list** has **Block them**
  (`fixit=block`) with the steps for nginx, Cloudflare (Settings › Lists, as in Cloudflare's
  guide) and fail2ban; its three downloads stay plain buttons and show only when there is
  something to block. My AI agent is not offered on either: no agent job does this yet, and
  this release adds none. Each host's answers is under **Open the details** (`sxx_view=open`);
  the Block list's long warning is behind the "?", one line of it stays. Who: owners and
  admins (the Block list), everyone (Exposed). What to do: nothing. Checked:
  `tests/test_ux_sections.py`, shots of both screens and the Fix dialog.
- **Fixed (words, not counts).** Two figures that looked like a mismatch now say why they
  differ. On Leads & sales with **7 days**, Leads said 25 and Summary said 19: Leads counts the
  7 days up to today, so far, from every tool (demos booked too); Summary and Sources count
  the 7 whole days up to yesterday from the lead database (sign-ups, contact forms and early
  access, no demos booked). Both are right; neither figure changed. The line under the Leads
  count now names Summary's dates and what it counts, and a note under Summary's figures
  links back to Leads. On Traffic › Retention the period chip said "12 weeks of first visits"
  while the New visitors figure said "the 8 weeks counted": it now says "first seen in 8 of
  the 12 weeks: 4 before what is kept begins (Tue 25 Aug 2026)". Seen in the UX audit (task
  3). Who: everyone. What to do: nothing. Checked: `tests/js/leads-period.mjs`,
  `tests/js/phase-c.mjs`, `tests/test_ux_sections.py`, and the sample data's shots.
- **Changed.** Traffic, answer first (the UX audit's tasks 7 and 8). **Visitors** opens on the
  visits: a **List / Flow** switch kept in the address (`vis_view=flow`), the list's first 12
  rows then **Show all**, the two cards, and **Open the details** (`visx_view=open`) for where
  visits ended, next steps and the engagement tables (4,747 to 2,718 px at 1440). **Sources**
  opens on its grid; its five method notes are behind the "?" beside the title, and the likely
  causes of Direct, where returning visitors first came from and campaigns and referrers are
  under **Open the details** (`srcx_view=open`; 4,653 to 858 px). **Pages** opens on Landing
  pages and their leads (search a page, a row opens its story, `page=`); Pages by publish date,
  the leaderboard and Pages read by people are under **Open the details** (`pgx_view=open`;
  3,639 to 1,254 px). A page's story has one primary button, **Mark a change**; **Compare this
  page** is a plain button. Why: the visit list started under a 1,000 px flow map, and Sources
  repeated the same six sources in 11 sections. Who: everyone. What to do: nothing; every
  figure and table is still there. Checked: `tests/test_ux_sections.py`, before and after shots.
- **Changed.** Insights' **Fix this** writes `by=` in the address too (it wrote `fixby=`), so
  every "Who will do it?" step uses one key. Older links with `fixby=` still open the same answer.
  Who: anyone who copies an Insights link. What to do: nothing. Checked: `tests/js/todos.mjs`.

### A simpler dashboard, part 4: Export, Add a site, the visitor drawer, Help, sign-in and mail

- **Fixed.** "Get the daily mail" waited for good when the install has no mail server: step 3
  said "Waiting for owner@example.com to press the link in their confirm mail" with **Check
  again**, and the mail could never go. Saving the recipients also used up the day's confirm link
  for nothing. Now every step shows one card, "Skald cannot send mail yet", with what is missing in
  plain words and "Who will set it up?": **Me** (install admins: the form in Settings › Mail &
  reports) or **My developer** (a message to send, which names where the settings go and holds no
  secret). The answer is in the address (`setup=mail&step=3&by=dev`). No confirm mail is tried
  without a mail server, and your own address (the one you sign in with) is never asked to
  confirm. Why: the UX audit found the dialog stuck. Who: installs without SMTP settings. What to
  do: nothing; set the mail server when you want mail. Checked: `tests/js/mail-ready.mjs`,
  `tests/test_mail_confirm.py` (no link used up, own address confirmed), the sandbox shots.
- **Changed.** GET and POST `settings` answer `mail_server: {ready, missing}`. The helper for any
  page that shows mail settings is `js/mail-ready.js`.
- **Changed.** Export is one item under the three-dot menu (and in Search, "Export: a PDF, the
  tables as CSV, a report by mail or JSON"). It asks "What do you need?" and shows only that
  path: **A PDF of this page** (this page as on screen; **Change** opens the sections, period,
  page group and filters of the old Report builder), **The tables, as CSV** (each table on its
  own, or all in a ZIP), **A report someone gets every month** (who gets it, filled from your
  last report; how often; this page's part; **Preview**, **Start sending**; owners and admins with
  accounts) and **Everything, for my own tools** (JSON, the API, MCP). Each path has one main
  button, and Export opens on your last choice, so a PDF again is three presses. In the address:
  `dlg=export&kind=pdf|csv|monthly|tools`, `xch=1` while Change is open. Why: four export items,
  a 33-box Report builder and the client reports in Settings did the same job three ways (UX
  audit, task 6). Who: everyone who exports. What to do: nothing; old `dlg=report` links open the
  PDF path with its sections open. Checked: `tests/js/export.mjs` (every path, the address round
  trip, the old link, no mail server), `tests/test_ux_overview_alerts.py`, the sandbox shots.
- **Changed.** Add a site is two steps: **Your site** and **Connect it**. Step 1 takes the
  address, says what Skald found in one line while you type ("Runs on nginx · suggested: one
  command on the server", details folded), shows the time zone in one line with **Change**, and
  asks "Who will connect it?": **Me**, **My developer** or **My AI agent**. Step 2 shows only that
  path: for Me the found way with its one command made at once and the Test below it (**Another
  way** for the others); for My developer the private link; for My AI agent the agent choice, its
  line, and "Skald watches your agent" under the line. The proof step shows only when the server
  asks for one. The site's row says **Finish setting up** in place of "Setup: step 3 of 5,
  continue". In the address: `setup=<site>&step=1|2&by=me|dev|agent`. Why: the old wizard took
  five steps and about 11 presses for a site Skald could read itself (UX audit). Who: owners and
  admins who add sites. What to do: nothing; older links still open (`step=3`, `4` or `5` is
  Connect it, `agent=hand` is Me), and the server still saves its five-step progress. Checked:
  `tests/js/add-site.mjs` (both steps, every path, the address round trip, the old links, the
  proof step only when asked), `tests/js/connections.mjs`, `tests/js/agent-setup.mjs`,
  `tests/js/routes.mjs`, `tests/test_site_setup.py`, the sandbox shots at 1440 and 390 wide.
- **Fixed.** In the send steps, a long install command no longer widens the dialog on a phone
  (the command scrolls inside its box). Seen at 390 px wide in Add a site. Checked: the sandbox
  shot, measured with no part wider than the dialog.
- **Changed.** The visitor drawer starts with the state: one card with pills (**Here now**,
  **Returning** or **First visit**, and how the visits ended), one sentence ("4 visits over 13
  days. First came from reddit.com, 13 days ago.") and one line of facts (place, device and
  browser, first seen), each with a copy icon. How the visits are linked moved behind a **?**.
  The journey draws the newest two visits, then **Show all (N)** (`vall=1` in the address, gone
  when the drawer closes). Leads and conversions, This visit and Every visit as a table are folds.
  Why: the drawer opened on a six-box grid and every visit at once (about 1,900 px tall for a
  visitor with four visits, 295 words). Now about 960 px and 110 words before you open anything.
  Who: everyone who opens a visit or a person. What to do: nothing. Checked:
  `tests/js/visitor-short.mjs` (the state, the pills, the copy icons, Show all and its address
  round trip, the folds, a lead's fold open), `tests/js/visitor-drawer.mjs`, `tests/js/routes.mjs`,
  `tests/test_firsttouch.py`, the sandbox shots at 1440 and 390 wide.
- **Changed.** Help lists the guides in six groups (Start here, Your visitors, Leads and sales,
  AI and bots, Connect and set up, Security and privacy), one line per guide with its summary on
  hover. The search lists the guides that hold every word, each with the sections they are in;
  a section opens the guide there. The search words and the section are in the address
  (`hq=`, `hs=`). A **?** popover can name a guide's section (`guide: "id#section"`), and its
  **Read the guide** opens it there: Export and the visitor drawer do. Why: the index was a wall
  of 29 cards, about 1,450 words and 2,240 px tall, before the search. Now about 150 words and
  one screen at 1440 wide. Who: everyone who opens Help. What to do: nothing; old
  `#help?part=<guide>` links open as before. Checked: `tests/js/help-guides.mjs` (every guide in
  one group; every Help link and "?" in the app names a guide and a section that exist; the
  search and its address round trip; a section link), a browser check (typing keeps the focus;
  a link with `hs=` opens at that section; Back works), the sandbox shots.
- **Changed.** The sign-in and invite pages are shorter. Sign in has no line under its title, and
  the "Keep me signed in" note is behind a **?** beside it. The invite says "As a viewer, for
  teammate@example.com." in one line, and the password rule in one line. Both cards carry the
  dashboard's five traffic colours as a thin line on top, in light and dark. Why: the owner asked
  for less on every screen (38 words on sign in, now 15; the card 460 px tall, now 404). Who:
  everyone who signs in or accepts an invite. What to do: nothing. Checked:
  `tests/test_webapp_auth.py`, `tests/test_saas_pages.py`, `tests/test_auth_api.py`, a browser check
  (the ? opens and closes its words, the box still ticks), the sandbox shots.
- **Fixed.** Settings › Mail with no mail server. Before, saving a recipient said "A confirm
  link was mailed to ..." though no mail could go, and nothing on the page said why. Now the
  card **Skald cannot send mail yet** sits above the recipients, says what is missing and asks
  **Who will set it up?** (Me for an install admin: the Mail server (SMTP) drawer; My developer:
  a message to copy). A saved address is told it gets its link once the mail server is set.
  With a mail server the page is as before. Who: owners and admins of an install with no mail
  server. What to do: nothing. Checked: `tests/js/prefs-mail.mjs`, drawn from real helper
  answers by `tests/test_mail_confirm.py`, with and without a mail server.
- **Changed.** Merged with Settings v2 (branch `ux-int`). Add a site asks who connects it once,
  in step 1, with the shared "Who will do it?" tiles (`ui/who.js`); step 2's agent tiles no
  longer carry a second "Me" (press **Change** to go back). Export's links for your own tools
  open Settings › AI assistants (API, MCP), and the no-mail-server card's **Me** opens the Mail
  server (SMTP) drawer (`#settings/site/mail?edit=smtp`). Why: Settings v2 renamed the pages and
  moved every set-up dialog to the same question. Who: owners and admins. What to do: nothing;
  older links still open. Checked: the node tests of both branches, both full suites.

### Summary and Pages state the period once; the chart's note is behind "?"

The scope line already gave the period's dates, then the period line gave them again, and the
sentence under the figures said a third time what the changes were against. The period line now
only says what the period is compared with, and only when Compare is on; the sentence lost its
"Changes are against …". The by-day chart's two-line explanation is behind a "?" by its title.
Who: everyone. To do: nothing. Checked in the browser on the sample data at 30 days.

### Real time: a visit that ended just under 30 minutes ago counts as active

- **Fixed.** Real time's "active now" (the last 30 minutes) left out a visit whose last request
  came in the first seconds of that window, before the first clock minute the per-minute bars
  show. A live run at 12:00:40 counts from 11:30:40, but its bars start at 11:31, and a visit
  last seen at 11:30:50 was skipped with the bars, so it was missing from the active count and
  from active by country, city, source and device (it was still listed under "What visitors are
  doing now", so the list could be one longer than the count).
- **Why.** `audit --live` on the busiest shipped-log site said now and then "visits active in the
  last 30 minutes: snapshot 14, recount 15", with US 9 vs 10, one city, a source and a device one
  higher too, a different visit each run, every other figure matching (seen 2026-10-24 and after
  the 2.40.0 deploy on 2026-10-26). The recount follows the documented rule, so the snapshot was
  the one wrong. It was not the order of the shipped lines: both roads count a window in time
  order (CLASSIFICATION.md, "Line order"), and shuffled shipped batches give the same visits.
  It happens on any site whose live run does not end on a whole minute; a busy site meets it
  more often.
- **Who / what to do.** Anyone looking at Real time. Nothing to do. No stored figure changes: the
  real-time part is never stored or mailed, and the daily figures were never affected, so no
  recount is needed.
- **Added.** `audit --live --show-active` (docs/CLI.md): both roads' active visits for the
  snapshot, one line each (start, last request, country, city, device, source, pages), the ones
  on one road only marked. Labels and times only, never an address.
- **Checked.** `tests/test_realtime_edge.py`: a live run at 12:00:40 with a visit last seen at
  11:30:50 (failed before the fix: snapshot 1, recount 2, the same pattern as the live runs);
  shuffled shipped batches against the same lines in time order give the same snapshot, real
  time, recount and day; `--show-active` prints no address. The full suite, with and without
  PyYAML.

### Fixed: the phone's bottom bar showed Menu on a second row

On a phone, the bar at the bottom has six sections (Overview, Traffic, Leads, AI & bots, Security,
Site) and Menu, but it was laid out for six items, so Menu wrapped onto a second row under
Overview. It now makes one column per item. Who: everyone on a phone. To do: nothing. Checked in
the browser at 390 px, light and dark: seven items on one row.
