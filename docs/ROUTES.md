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
| `range` | state.js | the period: `today`, `yesterday`, `7d`, `30d`, `90d`, `custom` |
| `from`, `to` | state.js | a custom period's first and last day |
| `view` | state.js | the page group (a view's slug) |
| `country`, `path`, `source`, `device`, `browser`, `campaign`, `referrer` | filterpanel.js | the single filters |
| `pathmode` | filterpanel.js | `starts`: the page filter matches the start of paths |
| `rules` | rules.js | the advanced filters' rules |
| `cmp` | modes.js | Compare with: `prev`, `year`, `custom` |
| `cb`, `cnorm`, `cgran`, `cm` | mode-compare.js | Compare's custom B, per day, the chart's grain and figure |
| `tz` | tz.js | `local` or `utc` (the site's zone when absent) |
| `dd` | drill.js | the drill-down trail, `dim:value` steps joined by a bar (an address as a token) |

## A tab's own keys

Kept while the tab is open (its `keep` list in `js/tabs/s-*.js`).

| Key | Owner | Means |
| --- | --- | --- |
| `page`, `pubfrom`, `pubto` | tabs/pagestory.js, tr-pages.js | Traffic > Pages: the page's story, published from, to |
| `rg`, `rm`, `rs`, `rv` | tabs/tr-retention.js | Retention: grain, measure, split, value |
| `since` | tabs/insights.js | Insights: the window |
| `fn`, `fsrc`, `fstep`, `fmode` | tabs/funnels.js | Funnels: steps, starting source, step open, reached or left |
| `lsrc`, `lact`, `llabel`, `lstage` | tabs/s-sales.js, sa-options.js | Leads & sales: count from, kind, label, stage |
| `lnow`, `lby`, `lshow`, `lview`, `lsplit` | tabs/sa-leads.js | Leads: stage now, source, show left out, the view, the split |
| `bact`, `bshow` | tabs/sa-bookings.js | Bookings: action, what to show |
| `cw`, `chb`, `co` | tabs/crawlhealth.js | Crawl health: 7 or 30 days, crawler, only problems |
| `ap`, `aq` | tabs/ai-answers.js | AI answers: the profile and the question open |
| `ip` | tabs/si-requests.js | Requests: one address only (always a token) |
| `rq` | tabs/si-requests.js | Requests: the quick filters |
| `strat` | tabs/speed.js | Speed: desktop |
| `part` | tabs/help.js | Help: the guide or its part |
| `note` | tabs/about.js | About: the note |
| `test` | tabs/sitesadmin.js | Add or remove sites: a site's wizard at its Test (read once, then `setup`) |

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
| `setup` | tabs/setup-dialogs.js | a Set up dialog: `logs`, `assets`, `rsc`, `countries`, `script`, `lead`, `mail`, `privacy` | `setup=rsc&step=2` |
| `setup` (on `#settings/sitesadmin`) | tabs/sitesadmin.js | the Add a site wizard: `new`, or a site's name | `setup=new&step=1` |
| `conn` | tabs/connections.js | a Connections dialog: `send`, `api`, `mcp` | `conn=api&step=2` |
| `step` | tabs/conn-ui.js | the step of the dialog open, 1 first | `step=2` |
| `share` | tabs/conn-share.js | the Share with your developer form is open (the link it makes never is in the address) | `share=1` |
| `dlg` | main.js, keys.js, extras.js, report.js, filterpanel.js, tabs/person.js | an app dialog: `keys`, `new`, `views`, `report`, `filters`, `find` | `dlg=views` |

A dialog opened from a link at a later step starts at the first step whose choice is
still missing (`wizard()` runs each earlier step's `check`). Who may open each: the Set
up and Connections dialogs and the Add a site wizard are for owners and admins; Find a
person (`who`) for owners and admins; everything else for whoever may open the tab.

## Tables and sub-tabs

Each table and grid keeps its own state under its namespace, `<ns>_<suffix>`
(`js/tablestate.js`, the data grid's `url-state.js`), while the tab stays:

| Suffix | Means |
| --- | --- |
| `_q` | the search box (an address or an email typed there becomes a token) |
| `_sort` | the order, `column:asc` or `column:desc` |
| `_page`, `_size` | the page and rows per page (grids) |
| `_seg`, `_fx`, `_sel` | a grid's segment, filters and rows chosen |
| `_cf` | the column filters |
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
