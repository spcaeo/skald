# Data contract: to-dos and lost pages (2.35)

Overview > Insights' to-do list and Site > Not found's lost pages. The rest of the data
files: [DATA-CONTRACT.md](../DATA-CONTRACT.md).

## todos.json

Overview > Insights' to-do list (`todos.py`), worst leak first. Built only from
what history already holds; nothing new is read from the log. The window: the
last 30 days with figures (verified, whole or partial) ending yesterday.

| field | type |
|---|---|
| `window` | `{"first","last","days","of": 30}` |
| `limits` | the thresholds (`todos.LIMITS`): `lost_min_asks` 10, `markdown_min_asks` 5, `sitemap_min_asks` 3, `errors_min` 5, `leave_min_visits` 20, `leave_share` 0.8, `leave_pages` 3 |
| `marks` | bool: the marks could be read (accounts); false without accounts |
| `todos[]` | see below; only those over their threshold, or marked done or not now |
| `withheld` | `[{"id","title","why"}]`: to-dos the second count disagreed with, left out |

Each to-do: `id` (`lost-pages`, `server-errors`, `ai-markdown`, `sitemap`, or
`leave-` and 8 hex, a hash of the site and the page), `kind` (`lost`, `errors`,
`markdown`, `sitemap`, `leave`), `subject` (the page, for `leave`; else null),
`tag`, `tone`, `title`, `proof` (words with the figure and the days), `todo`,
`check`, `figures` (the numbers in the proof), `qualifies`, `columns`
(`[{"key","label","path"?: true,"num"?: true}]`), `rows` (at most 1,000),
`rows_total`, `file` (the CSV's name), `open` (`{"tab", ...the filter, "name"}`),
`window`, `state` (`open`, `done`, `notnow`), `marked` (the mark, or null) and
`recheck` (for `done`: `{"marked_day","days","first","last","figures","verdict":
"waiting"/"fixed"/"not_yet","words"}`, the same measure over the whole days after
the day it was marked).

Where each comes from: `lost` and `markdown` and `sitemap` from the day kind
`not_found` (as lost_pages.json below); `errors` from the counts
`server_error_page` (path, with its `(all others)` fold) and `status_<group>`
`5xx`; `leave` from the stored journeys (landing, pages, posted), over the
days of the window they are kept for.

## lost_pages.json

Site > Not found's lost pages (`lost_pages.py`), over the same 30-day window.
From the day kind `not_found` (404 and 410 by path, status, who asked, probe)
and the day kind `pages` (pages served). Who asked: `people`, `search`
(search engines), `ai` (`ai_asked` and `ai_training`); bots, probes and our own
traffic are left out. Live pages: the sitemap's paths for the last whole day,
and every path served as a page in the window (an address served on or after
the last day it failed counts as live).

| field | type |
|---|---|
| `window` | `{"first","last","days","of","not_recorded"}` |
| `live` | `{"sitemap": int or null,"sitemap_day","served","pages"}` |
| `marks` | bool, as above |
| `totals` | `{"paths","people","search","ai","md_paths","md_live","md_asks","md_live_asks"}`, or null when withheld |
| `lost` | `[{"path","people","search","ai","bots","n","first_day","last_day","statuses","sources","target","match": "exact"/"likely"/"guess"/null,"why","nginx","apache","gone": {"nginx","apache"} or null,"marked": day or null}]`, most asked first; null when withheld. `nginx`/`apache` are the lines for the suggestion (301 to `target`, or 410 without one), null when the address has characters a server line cannot take as they are |
| `markdown` | `{"live": [...], "other": [...]}`: `.md`/`.mdx` addresses AI asked for, `{"path","ai","ai_asked","ai_training","people","search","page","nginx","apache","first_day","last_day"}`; `page` is the live page it copies (null in `other`) |
| `fixed` | `[{"path","marked_day","days","people","search","ai","bots","served","verdict": "waiting"/"not_yet"/"fixed","today": {"people","search","ai","served"} or null}]`: addresses marked fixed, counted on the whole days after the mark |
| `withheld` | `[why]`: the second count disagreed; `totals`, `lost` and `markdown` are then null |

The closest live page (`closest_page.py`): `exact` the same address written
another way (case, slash, `index.html`, a malformed tail, a copy suffix, a
moved slug of 3 or more words); `likely` a page sharing most of its words
(Dice 0.62 or more); `guess` its nearest live parent section (never `/`).

Second count for both files: `audit_todos.py`, by its own SQL over history and
its own path rules, sharing only the name lists (`MACHINE`, `PAGE_ENDINGS`,
`MARKDOWN_ENDINGS`, `WHO`) and `LIMITS`.

The marks (`todo_marks.py`): table `todo_marks` in accounts.sqlite,
append-only, `(site, item, state, day, at, by_user, kind, note)`; `item` is a to-do's id,
`path:/old/`, or `page:/path/` for a tracked page change; `state` `done`, `notnow`,
`fixed`, `changed` (a page change, with its `kind` and `note`) or `open` (undo). The newest
row is the mark (for a page change: the newest per page and day). Page changes:
[DATA-CONTRACT-PAGE-CHANGES.md](DATA-CONTRACT-PAGE-CHANGES.md). Read and written by the helper's `settings/todos`
(`todo_api.py`); every change and every mail sent is an audit-log row
(`todo.marked`, `todo.sent`).
