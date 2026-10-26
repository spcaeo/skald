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
the day it was marked). 2.41 adds `agent` (bool: an AI agent can fix this kind, `todos.AGENT_KINDS`:
all five) and `first_seen` (the first day this to-do was on the list, open; null for one
withheld or not open; a to-do that left the list and came back is new again).

**The agents' rows file (2.41, `todo_rows.py`).** `todos.json` holds at most 1,000 rows a
to-do. The same build writes every row (at most 20,000) beside the history, never in the
dashboard folder: `<history folder>/todo-rows/<site>.json`, mode 0600,
`{"site","generated_at","window","todos": [{id, kind, subject, tag, title, proof, todo,
check, figures, window, columns, rows, rows_total, file, open, first_seen}], "seen": {id: day}}`.
Only the to-dos the second count agreed with. It is read by the kit's
`GET /traffic-kit/<code>/todo/<id>`, by `settings/todo-rows` and by the MCP's `fix_todo`;
each scrubs an email or IPv4 address found inside a value to `[removed]` before handing
it out. A to-do new to `seen` queues the outgoing webhook `todo.new` (no code, no row).

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
the last day it failed counts as live). Since 2.38.0 only a 404 is an ask: a
410 is the site's own answer, so it is counted in `statuses` only, and an
address that answered 410 on or after the last day it answered 404 is handled
and not listed (lost pages and sitemap addresses alike). `first_day` and
`last_day` are the 404s'. A redirect, to the site or another one, leaves no
404, so the re-checks and `fixed` count it as fixed.

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

The AI agents' reports (2.41): table `todo_fixes` in accounts.sqlite, append-only,
`(site, item, at, state, change, files, left_rows, notes, link_id, by_who)`; `state`
`done`, `partly` or `left`; `change` the exact change as text (at most 200,000
characters, anything shaped like a token removed); `files` and `left_rows` JSON
(`[path]`, `[{"row","why"}]`); `link_id` the to-do line's id (null from the MCP);
`by_who` `ai-agent` or `mcp:<token id>`. The newest row per to-do is shown. A `done`
report also writes a `done` mark (`by_user` null) unless the to-do is done already, so
the re-check runs as for a person's mark. Audit rows: `kit.todoline` (a line made: its id
and to-dos, never the code), `todo.fixed` (a kit report: the to-do, the state, the link
id), `mcp.todo_done` (an MCP report); never the change itself.

The helper's routes (sessions mode; 404 in basic mode), under `settings/`, which nginx already
passes:

| Method, path | Body -> answer |
| --- | --- |
| GET `settings/todos` | -> `{ok, marks: {item: {state, day, at, first_day}}, changes, role, can_mark, mail: {ready, why}, team: [{id, email, role}], fixes: {item: the newest report}, server: {server, platform, framework}, line}`; `team` (who a to-do can be sent to) and `line` (the site's newest to-do line's status, never its code) only for owners and admins |
| POST `settings/todos` | `{item, state}`: `done`, `notnow` or `open` for a to-do; `fixed` or `open` for `path:/old/`; `{item: "page:/x/", state: "changed", day, kind, note}` marks a page change, `{item, state: "open", day}` stops tracking it -> `{ok, ...the mark, marks}` (a page change: `changes` instead). Owners and admins; the CSRF value |
| POST `settings/todo-agent` | `{act: "make", items: [id, ...] or "all"}` -> `{ok, line, llms_url, steps_url, expires_at, link_id, cancelled, todos}`: one to-do line (kit/agent_todos.py), works once, 24 hours, ends the site's older to-do lines whose keys were not taken (never a set-up line); `"all"`: every open to-do an agent can fix. `{act: "status", link_id}` -> the line's state, `opened_at`, `keys_at`, `todos`, `fixes` and `reports` (its to-dos' kept reports). `{act: "cancel", link_id}` -> `{ok, state: "cancelled"}`. Owners and admins; read-only plans cannot make one (402) |
| GET `settings/todo-rows?item=<id>` | -> `{ok, todo}`: the to-do with every row from the rows file (Fix this > Me's lines and CSV). Anyone who may read the site |
| POST `settings/todo-send` | `{item, to}` (`to`: a confirmed member's account id) -> `{ok, sent_to, file}`: mails one to-do with its rows as a CSV file and the link to it, through the install's mail server; owners and admins; 10 an hour (429). Without a mail server the answer says why |
