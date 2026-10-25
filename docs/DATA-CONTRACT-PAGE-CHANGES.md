# Data contract: tracked page changes, "Did my change work?" (2.35)

Traffic > Pages > a page, and Overview > Insights' list under "Done, and did it work?".
The rest of the data files: [DATA-CONTRACT.md](../DATA-CONTRACT.md).

## The marks

Someone marks "I changed this page on <day>" with what changed and a short note. The mark is
a row in the same append-only table as the to-do marks (`todo_marks.py`, table `todo_marks`
in accounts.sqlite; [DATA-CONTRACT-TODOS.md](DATA-CONTRACT-TODOS.md)):

| column | value |
|---|---|
| `item` | `page:` and the site path, e.g. `page:/pricing/` |
| `state` | `changed`; `open` stops tracking it (nothing is deleted) |
| `day` | the day it changed, the site's own date: today or before, at most 365 days back |
| `kind` | `content`, `title`, `backlink`, `redirect` or `other` |
| `note` | up to 200 characters, or null |

For each page and day, the newest row decides. A change's id is opaque: `c` and 8 hex of a
hash of the site, the path and the day. The helper's `settings/todos` reads them (`changes`
in its answer) and writes them (`{"item": "page:/x/", "state": "changed", "day", "kind",
"note"}`, or `"state": "open"` with the day); an owner or admin only. The audit log keeps
`todo.marked` without the note. A table from 2.35's first builds (no `changed`, no `kind`,
no `note`) is rebuilt in place on first use, every row kept.

Without accounts there are no marks: `marks` is false and nothing is tracked.

## page_changes.json

Built by `page_changes.py` on every run. Nothing new is counted: each day's figure is a
stored, audited day figure set side by side for the page, in every spelling (with or without
the trailing slash or a query; `page_trends.key`).

| field | type |
|---|---|
| `min_days` | 14: whole days after the change before a verdict |
| `max_days` | 28: at most this many whole days on each side |
| `rules` | `{"days","too_early","clear","few"}`: the rules in words |
| `measures` | `[{"key","label","better": "up"/"down"}]` |
| `marks` | bool: the marks could be read (accounts) |
| `changes[]` | below, newest day first |
| `withheld` | `[{"id","path","day","why": [problem]}]`: changes the second count disagreed with, left out |

A page group (view) gets `{"whole_site_only": true}` only: the marks are the whole site's.

Each change: `id`, `path`, `day`, `kind`, `note`, `at` (the newest mark), `first_at`,
`days_after`, `status`, `verdict_on`, `complete`, `before`, `after`, `days`, `figures`,
`leads_why`.

- **The windows.** N = the whole days from the day after the change to yesterday, at most
  28. The after side is those N days; the before side is the N days just before the change.
  The day of the change is in neither side (it changed during that day). `before` and
  `after`: `{"first","last","days": N,"whole": the days that are whole and verified}`.
  `complete`: N is 28.
- **status.** `waiting` (the change is today or yesterday: no whole day after it yet),
  `too_early` (fewer than 14 whole days after it), `ready`. `verdict_on`: the day the
  verdict comes (the change's day plus 15).
- **days[]** (for the chart): one row a day over both sides: `day`, `state` (`ok`,
  `partial`, `withheld`, `missing`, `before`), `side` (`before`/`after`), and `visits`,
  `one_page`, `search`, `ai`, `reads`, `leads`, each a number or null. Only a whole,
  verified day (`ok`) has figures; any other day is not recorded (null, never 0).
  `at_least`: the day's landings keep their top 200 pages only and this page is not among
  them, so its visits are a floor. `leads_state`: `ok`, `off` (no conversions file),
  `not_kept` (outside the 180 days conversions.json covers), or that day's conversions
  state (`before`, `withheld`).
- **figures[]**: one per measure, `{"key","better","before","after","unequal","change",
  "verdict"}`.

| key | what | from |
|---|---|---|
| `visits` | visits that started on the page | day kind `landings`, `visits` |
| `leads` | finished leads and conversions whose landing page is the page | conversions.json's audited days, `by.landing`, every action |
| `search` | of the visits, from a search engine | `landings`, `search` |
| `ai` | of the visits, from an AI assistant (a proven citation) | `landings`, `ai` |
| `reads` | AI reads: live fetches by assistants answering a user | day kind `ai_fetches`, every row of the page |
| `left` | left at once: one page view, then gone; lower is better | `landings`, `one_page` over `visits` |

  A side: `{"days": the days with the figure, "total", "per_day", "at_least"}`; for `left`,
  `{"days","visits","one_page","share","at_least"}`. A side with no day is null throughout.
  `unequal`: the two sides have the figure on a different number of days; they are then
  compared per day, and the page says so. `change`: `{"per_day","pct"}` (pct null when the
  before side is 0), or `{"points"}` for `left`; null when a side is not recorded.
- **verdict**: `too_early` (and `waiting`), then `not_recorded` (a side has no day with the
  figure), `not_enough_days` (a side has it on fewer than 7 days), `too_few` (the two sides
  count fewer than 10 together; `left`: a side with fewer than 10 visits),
  `no_clear_change` (the difference per day is within 2 standard errors of the two sides'
  daily figures: the normal day-to-day swing), else `up` or `down`. The difference is taken
  from the unrounded totals.

## The second count

`audit_page_changes.py`, on every build, shares only the name lists and the thresholds with
`page_changes.py`. It reads the marks from accounts.sqlite by its own SQL (the newest row per
page and day), the day kinds from history.sqlite by its own SQL, and the leads from
conversions.sqlite by its own SQL (finished rows, the site's local day, `landing` a site
path), with the day states from `audit_page_trends.states`. It recomputes every day's figures,
the windows, each side and each verdict. A lead figure must equal its SQL count; a null lead
must have its reason (a withheld or not-yet-recorded day, outside the 180 days, or no
conversions file). A change whose mark, figures, sides or verdict it does not find the same is
left out of `changes` and named in `withheld` with its problems; a mark missing from the file
is flagged too.

## markers.json

Each tracked change is also a marker of the kind `page_change` on its day (no time; `at` is
its midnight), drawn on every day chart: `{"at","day","kind": "page_change","label":
"/path/: new title, <note>","detail": "","change": id,"path"}`
([DATA-CONTRACT-ALERTS.md](DATA-CONTRACT-ALERTS.md#markersjson)).

## The address

`pchg=<id>` opens one change on Traffic > Pages (with `page=`) and on Overview > Insights.
The Mark a change dialog is `pcm=new`, its day `pcd=YYYY-MM-DD` and what changed `pck=<kind>`;
the note never goes in the address ([ROUTES.md](ROUTES.md)).
