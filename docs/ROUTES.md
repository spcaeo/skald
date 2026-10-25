# The dashboard's addresses

Every state of the dashboard is in its address, so any view can be copied, shared,
bookmarked and reloaded (owner's rule, 2026-10-21: "a proper URL router ... so any
state is reachable and copy-pasteable"). This page lists every key the address can
hold. The same list is in code, `skald/webapp/js/routekeys.js`, and
`tests/js/routes.mjs` fails when state.js reads a key that list does not name.

```
https://app.skaldanalytics.com/traffic/<site>/#<section>/<tab>?<key>=<value>&...
https://app.skaldanalytics.com/traffic/example.com/#traffic/visitors?range=7d&vis=2026-10-20.14
```

The route (`#traffic/visitors`) names the section and the tab; older routes redirect
(`js/routes.js`, for example `#sources` and `#live`). The keys after `?` are of four
kinds.

## Rules

- **Opening adds a history entry.** A drawer or a dialog that opens writes its key with
  `history.pushState`, so **Back** closes it before it leaves the page. A change inside
  it (a step of a dialog, a sub-tab, a table's sort) replaces the entry instead.
- **Closing removes the key.** The reader's close takes the key out of the address
  (and steps Back over the entry the opening made, unless a link in the drawer has
  already moved the page on).
- **Going to another tab** drops the drill-down and every drawer and dialog key, unless
  the move carries them.
- **A link to something the reader may not see** opens the page with one plain line at
  the top, never an error and never "unknown": "That visitor is no longer kept (journeys
  are kept 7 days).", "That lead is not in the period on screen. ...", "Not available to
  your role.", "That request is no longer in the recent log (it keeps the last 6 hours)."
- **Opaque ids only.** A record is named by an id that says nothing about a person: a
  visit's day and number, a lead's row id, a code of a log line (`codeOf`, FNV-1a in
  base 36), a cohort's first day.
- **No address, email or person search in the address.** Such a value becomes a token,
  `~` and 10 letters or digits, that only the browser that made it reads back
  (`js/routemask.js`: kept in that browser's storage, at most 200 for 30 days, never
  sent). `ip` and `who` are always tokens; any other value has its IPv4 and IPv6
  addresses and anything holding an `@` replaced (`routekeys.js` `personalParts`). An
  older link that carries an address is rewritten with the token on load. A token from
  another browser opens the page with: "That link was made in another browser: ...".
  `tests/js/routes.mjs` checks every address the tests write: no value is an address or
  holds an `@`.
- **Copy link** on a saved view and the address bar carry the whole state. A link never
  bypasses sign-in: whoever opens it signs in first and sees only what their role may.

## Global keys (every tab)

| Key | Owner | Means |
| --- | --- | --- |
| `range` | state.js | the period: `today`, `yesterday`, `7d`, `30d`, `90d`, `all` (all time, from the first day the site has data), `custom`. Absent: the section's own default, `7d` on Leads & sales and `today` everywhere else (2.23). A period the address does not name is not carried into another section; one the reader picked is written and stays |
| `from`, `to` | state.js | a custom period's first and last day |
| `view` | state.js | the page group (a view's slug) |
| `country`, `path`, `source`, `device`, `browser`, `campaign`, `referrer` | filterpanel.js | the single filters |
| `pathmode` | filterpanel.js | `starts`: the page filter matches the start of paths |
| `rules` | rules.js | the advanced filters' rules |
| `cmp` | modes.js | Compare with: `prev`, `year`, `custom` |
| `inc` | period-line.js | `1`: Include today. On Overview > Summary and Traffic > Pages with `7d`, `30d` or `90d` only: the last N days end today (part of today, counted so far) instead of yesterday. Elsewhere it is kept but does nothing. While it is on, Compare does not compare (today is not complete), and says so: `#overview/summary?range=7d&inc=1` |
| `cb`, `cnorm`, `cgran`, `cm` | mode-compare.js | Compare's custom B, per day, the chart's grain and figure |
| `tz` | tz.js | `local` or `utc` (the site's zone when absent) |
| `dd` | drill.js | the drill-down trail, `dim:value` steps joined by a bar (an address as a token) |

## A tab's own keys

Kept while the tab is open (its `keep` list in `js/tabs/s-*.js`).

| Key | Owner | Means |
| --- | --- | --- |
| `page`, `pubfrom`, `pubto`, `chgfrom` | tabs/pagestory.js, tr-pages.js | Traffic > Pages: the page's story, published from, to, changed since (the website's or the sitemap's change date) |
| `psort` | tabs/tr-pages.js | Traffic > Pages: the sort chips, `visits` (absent), `rising`, `falling`, `changed` (newest change date first), `work` (needs work: many visits, most left at once, no forms). `rising` and `falling` need Compare (`cmp`); without it they say so and sort by visits. While a column header's own sort (`lp_sort`) is set, no chip is lit; a chip clears it: `#traffic/pages?range=30d&cmp=prev&psort=rising`. The filter panel's preset writes `chgfrom=<30 days ago>&psort=changed` |
| `net` | tabs/tr-social.js | Traffic > Sources: the social network open under the grid, by its id (`x`, `linkedin`, `facebook`, ...); with `src_seg=social`, the Social network segment: `#traffic/sources?src_seg=social&net=x` |
| `rg`, `rm`, `rs`, `rv` | tabs/tr-retention.js | Retention: grain, measure, split, value |
| `since` | tabs/insights.js | Insights: the window |
| `todo` | tabs/todos.js | Insights: the to-do whose list is open, by its id (`lost-pages`, `server-errors`, `ai-markdown`, `sitemap`, or `leave-` and 8 hex, a hash of the page): `#overview/insights?todo=lost-pages` (2.35). A to-do not on the list now opens the page with one plain line |
| `pchg` | tabs/pagechange.js | Traffic > Pages (with `page`) and Insights: one tracked change open, by its id (`c` and 8 hex, a hash of the site, the page and the day): `#traffic/pages?page=%2Fpricing%2F&pchg=c22e50cf9` (2.35). A change no longer tracked opens the page with one plain line |
| `nfk`, `nfsrv` | tabs/nf-lost.js | Not found's lost pages: the tab (`md` AI asks for Markdown, `fixed` After the fix; Lost pages when absent) and the server lines (`apache`; nginx when absent) (2.35) |
| `fn`, `fsrc`, `fstep`, `fmode` | tabs/funnels.js | Funnels: steps, starting source, step open, reached or left |
| `lsrc`, `lact`, `llabel`, `lstage` | tabs/s-sales.js, sa-options.js | Leads & sales: count from, kind, label, stage |
| `lnow`, `lby`, `lshow`, `lview`, `lsplit` | tabs/sa-leads.js | Leads: stage now, source, show left out, the view, the split |
| `cur`, `by`, `tag` | tabs/sa-revenue.js | Revenue: the currency (never converted), the breakdown, one tag `key:value` |
| `bact`, `bshow` | tabs/sa-bookings.js | Calendar bookings: action, what to show |
| `psec` | tabs/pagestory.js, aiready.js | Traffic > Pages: the part of a page's story to open at; `ai` scrolls to its AI readiness (a row of "Pages AI can't read well" writes it): `#traffic/pages?page=/guides/webhooks/&psec=ai`. Back from the story clears it |
| `arw` | tabs/aiready.js | AI & bots > Assistants: the filter of "Pages AI can't read well", `copy` (a Markdown copy that does not answer), `404`, `errors` (5xx and other 4xx), `robots` (robots.txt shuts a crawler out), `slow`; all when absent: `#ai/assistants?arw=copy` |
| `cw`, `chb`, `co` | tabs/crawlhealth.js | Crawl health: 7 or 30 days, crawler, only problems |
| `ap`, `aq` | tabs/ai-answers.js | AI answers: the profile and the question open |
| `ip` | tabs/si-requests.js | Requests: one address only (always a token) |
| `rq` | tabs/si-requests.js | Requests: the quick filters |
| `strat` | tabs/speed.js | Speed: desktop |
| `part` | tabs/help.js | Help: the guide or its part |
| `note` | tabs/about.js | About: the note |
| `test` | tabs/sitesadmin.js | Add or remove sites: a site's wizard at its Test (read once, then `setup`) |
| `ca`, `cdim` | routes.js | the old Compare page's period A and table: read once and rewritten into the period and `cmp` (`cb` for a custom B) |

## Drawers and dialogs (overlay keys)

| Key | Owner | Means | Example |
| --- | --- | --- | --- |
| `vis` | tabs/visitor.js | the visitor drawer, by its visit: day and number that day | `vis=2026-10-20.14` |
| `who` | tabs/visitor.js | Find a person's answer: the search as a token | `who=~k2f9a0x7qm` |
| `lead` | tabs/sa-leads.js | a lead's drawer, by its row id | `lead=1287` |
| `conv` | tabs/sa-lists.js | a cancelled, removed or test conversion: its list and a code | `conv=test.r1x2y3z` |
| `req` | tabs/si-requests.js | one request's detail, by a code of its log line | `req=r8k2m1x` |
| `cohort` | tabs/tr-retention.js | Retention: a cell's visitors, the cohort's first day and the step | `cohort=2026-10-05.2` |
| `sq` | tabs/tr-search.js | Search: a query's or a page's drawer | `sq=query.google:skald analytics` |
| `list` | tabs/person.js | a list drawer: `leftout`, `conv-cancelled`, `conv-removed`, `conv-test` | `list=leftout` |
| `scan` | tabs/sec-scanners.js | Security, Who is scanning us?: one scanner's detail, by its first row (never its address) | `scan=2026-10-20.3` |
| `ans` | tabs/ai-answers.js | AI answers: one stored answer in full | `ans=412` |
| `setup` | tabs/setup-dialogs.js | a Set up dialog: `logs`, `assets`, `rsc`, `countries`, `script`, `lead`, `mail`, `privacy`, `pack` (send set-up to someone, 2.30) | `setup=rsc&step=2` |
| `pack` | tabs/setup-pack.js | `1` while the set-up pack box is open inside the logs or leads dialog (2.30); the addresses and keys never go in the address | `pack=1` |
| `setup` (on `#settings/sitesadmin`) | tabs/sitesadmin.js | the Add a site wizard: `new`, then the site's name once step 1 made it (replaced in place, so a reload finds the site); a site's name (it has a dot) opens its wizard on any tab, as Connections' Set up with your AI agent does (2.31) | `setup=new&step=1`, `setup=example.com&step=3` |
| `agent` | tabs/site-wizard.js | Add a site, step 3: the AI agent chosen (`claude-code`, `codex`, `cursor`, `chat`, `other`), or `hand` for set it up by hand (2.31) | `agent=claude-code` |
| `link` | tabs/agent-setup.js | Add a site, steps 4 and 5: the agent's line being watched, by its link id (the first 16 hex of the code's SHA-256). The line and its code never go in the address (2.31) | `link=0f3a9c2e7b1d4a58` |
| `conn` | tabs/connections.js | a Connections dialog: `send`, `api`, `mcp`, `sample` (Test a sample of a log, 2.35) | `conn=api&step=2` |
| `lfmt` | tabs/conn-sample.js | Test a sample: the reader chosen (a format name; absent: Detect it). The pasted lines never go in the address, so a link or a reload opens step 1 to paste again | `conn=sample&step=1&lfmt=caddy_json` |
| `step` | tabs/conn-ui.js | the step of the dialog open, 1 first | `step=2` |
| `share` | tabs/conn-share.js | the Share with your developer form is open (the link it makes never is in the address) | `share=1` |
| `token` | tabs/conn-install.js | a by-hand zip kit's "Include the access token in the zip" unticked, under "Other ways" in the send dialog or Add a site (absent: ticked, the default); never the token itself | `token=0` |
| `tdsend` | tabs/todo-send.js | Insights: Send to team, for a to-do, by its id (2.35). Who it goes to never goes in the address; without a mail server or a team the page says why instead | `tdsend=lost-pages` |
| `pcm`, `pcd`, `pck` | tabs/pagechange.js | Traffic > Pages > a page: the Mark a change dialog (`new`), its day (`YYYY-MM-DD`, today or before) and what changed (`content`, `title`, `backlink`, `redirect`, `other`); a pick replaces the entry. The note never goes in the address. Owners and admins only; elsewhere the page says why (2.35) | `pcm=new&pcd=2026-10-21&pck=title` |
| `dlg` | main.js, keys.js, extras.js, report.js, filterpanel.js, tabs/person.js | an app dialog: `keys`, `new`, `views`, `report`, `filters`, `find` | `dlg=views` |

A dialog opened from a link at a later step starts at the first step whose choice is
still missing (`wizard()` runs each earlier step's `check`). Who may open each: the Set
up and Connections dialogs and the Add a site wizard are for owners and admins; Find a
person (`who`) for owners and admins; everything else for whoever may open the tab.

## The breadcrumb line and Back (2.35)

Over every tab, a line shows the path taken in this browser tab: `← Back to <the step
before>`, then each step, the current one last with copy and open icons for this exact
view (`js/crumbs.js`, `css/crumbs.css`). The address stays the source of truth: a step is
the address it had (period, filters, sort, what was open), and a crumb goes to that address
as a new history entry.

- **A step** is a place: the tab and what is open in it (`page`, `todo`, Help's `part`, the
  drill-down's `dd` steps, a record drawer: `vis`, `lead`, `conv`, `req`, `cohort`, `sq`,
  `list`, `scan`, `ans`, `who`). A change in place (a period, a filter, a sort) keeps the
  step and takes its new address. A place already on the trail (Back, a crumb, a link to
  it) cuts the trail back to it. A move along one section's tabs with nothing open replaces
  the last step. At most 12 steps; past 5 the middle folds into `…`.
- **The trail** lives in the tab's `sessionStorage` (`ti-crumbs`), never sent and gone with
  the tab. A reload, or Back into the page, keeps it; a copied address opened in a new tab
  starts its own from the address alone: section › tab, then the item (`Traffic › Pages`,
  then `/pricing/`).
- **Scrolling.** Each step keeps where the page was scrolled, and the last 40 addresses
  too (`ti-crumbs-y`). Back, Forward, a crumb or a reload put it back once the tab is drawn
  (`history.scrollRestoration` is `manual`); a scroll made while it is being put back is
  not saved, and once the reader scrolls it is left alone.
- On a phone the line is `← Back to` and where you are; the steps between are Back's.

## Tables and sub-tabs

Each table and grid keeps its own state under its namespace, `<ns>_<suffix>`
(`js/tablestate.js`, the data grid's `url-state.js`), while the tab stays:

| Suffix | Means |
| --- | --- |
| `_q` | the search box (an address or an email typed there becomes a token) |
| `_sort` | the order, `column:asc` or `column:desc` |
| `_page`, `_size` | the page and rows per page (grids) |
| `_seg`, `_fx`, `_sel` | a grid's segment, filters and rows chosen |
| `_cf` | the column filters (not on Leads since 2.23: its options row is its filter row, so an older `ld_cf` is not applied) |
| `_hide` | the columns taken away |
| `_view` | a sub-tab or a switch inside a tab (`subView(ns)`) |

The sub-tabs kept this way: `alerts_view` (Site > Alerts: all or AI), `utm_view`
(Sources: the UTM tag), `seeng_view`, `seper_view`, `semet_view` (Traffic > Search: the
engine, the period, the measure), `flow_view` (the visitor flow: start and pages),
`tsrc_view` (Overview in Live mode: the sources' order).

## Copy and open on every URL

Every site path and URL the dashboard draws has two icons at its end on hover or
keyboard focus (always on a touch screen): copy the full URL (a path joined with
`https://<site>`) and open it in a new tab (`js/urlactions.js`, `css/urlactions.css`).
A table or grid column gets them with `path: true` or `url: true` (or a drill by page
or landing page), `href(row)` when the cell's value is not the URL;
`tests/js/urlactions.mjs` fails on a page column in the code without the flag.

## Security (2.21)

| key | tab | means |
|---|---|---|
| `sxv` | Is anything exposed? | `possible`, `nosize` (can't tell: no size in the log), or both when absent |
| `item` | Is anything exposed?, Your stack | the item a security alert names, opened first: an opaque id, `x` or `a` and 12 hex characters (security_notify.py) |
| `sxc` | Who is scanning us? | what they looked for (a category) |
| `sxk` | Who is scanning us? | `all`: every suspect, not only scanners |
| `sxa` | Attack attempts | `injection`, `login` or `burst` |

Tables: `sx`, `sxh`, `sxs`, `sxi`, `sxl`, `sxb`, `sxf`, `sxn`, `sxd`, `sxr`, `sxo` (their sort, filters and columns, as every table's).
