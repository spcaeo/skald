# Data contract: Security

Scanners, what the server answered them, attack attempts and fake browsers
(`skald/security.py`, its name lists and thresholds
`skald/security_names.py`; the second count is
`skald/audit_security.py`). The section is Security in the menu (route
`#threats/...`); the guide is [help/security.md](help/security.md). Part of
[DATA-CONTRACT.md](../DATA-CONTRACT.md); its rules apply.

Security is a view across the five groups, never a group: every request stays
where classify.py put it, and the groups still add up to the site's requests.
Nothing in history or in `security.json` holds an address or a user agent.

## Who is what

| term | rule |
|---|---|
| scanner probe | a request in the bots group whose path matches `classify.PROBE` or whose URL matches `classify.PROBE_QUERY`, not under `site.legacy_paths`; and a line of a host the site does not list whose Host is an IP literal and whose path or URL matches them (`probes_other`) |
| scanner | an (address, user agent) pair with at least one probe that day; every request of the pair is on its row |
| category | the first of `security_names.CATEGORIES` that matches (injection reads the URL, the rest the lower-cased path), else `other`: `injection`, `secrets`, `cloud`, `wordpress`, `dumps`, `admin`, `php`, `other`. The categories add up to the probes |
| injection kind | the first of `security_names.INJECTION` that matches the URL: `traversal`, `log4shell`, `xss`, `sql`, `php`, else `other` |
| bare IP | a request whose Host is an IP literal (`203.0.113.5`, `[2001:db8::1]`, with or without a port) |
| forged referrer | a suspect pair that sent a referrer whose host is a site host, or a subdomain of one with `www.` taken off (no hosts listed: the line's own host), and never loaded an asset or framework payload with such a referrer |
| login hammering | at least `login_posts` (20) POSTs to a path `security_names.LOGIN_PATH` matches, from one address, within `login_seconds` (300); people and bots only |
| burst | at least `burst_requests` (300) requests from one address within `burst_seconds` (60); people and bots only (search engines, AI crawlers and our own traffic are left out) |
| episode | every request that lies in some window of the threshold's length holding at least the threshold's count; such requests stay in one episode while the gap between two of them is within the window |
| fake browser | a bots request classify.py filed as `browser-like, never rendered the page` (`not_rendered`), `too fast to be a person` (`too_fast`), `browser-like crawler` (`crawler_session`), or a crawler's name it could not prove (`claims:<name>`) |
| suspect | a pair with a probe, a fake-browser request, or a request in a login or burst episode |

Thresholds: the config's `security:` section (`shell_paths`, `tolerance`,
`login_posts`, `login_seconds`, `burst_requests`, `burst_seconds`,
`large_post_bytes`), each kept within `security_names.LIMITS`.

"Worth a look" (Attack attempts, computed by the page from the stored `signs`, js/sec-data.js
`signsOf`): a day whose gateway errors or .php requests are at least 3 times the median of the
14 days before it that have the figure (at least 7 of them) and at least 20.

## Is anything exposed? (the verdict of a 2xx probe)

| verdict | rule |
|---|---|
| `shell` | at least `shell_paths` (3) distinct probe paths of that host were answered 2xx that day with a size within `tolerance` (16) bytes of this one: a fallback size. A host may have several (2.21.1): the same page sent compressed and not (404 and 626 bytes on a real server) |
| `empty` | a body of 0 bytes |
| `possible` | any other size: a possible exposure |
| `unknown` | the line has no size: cannot tell, never counted as safe |

Only a probe whose **path** is a probe is judged (2.21.1): a probe that is an ordinary page
with an attack in its query string (`/?id=1 union select`) asked for no file, and its answer is
that page; it is counted in `query_only` and listed under Attack attempts with what was
answered. Each host has its own fallback sizes, and an IP literal is a host of its own: the log's
size is the size sent after compression, so the same page can be 392 bytes
through the host name (a CDN's compression) and 404 bytes through the bare IP
(the server's). The log never records the content (nor, in Skald's formats,
the content type), so a `possible` answer is a reason to look and a `shell`
answer no proof of safety.

## The day kind `security`

Whole site only (a view has none). Counted in the tally pass, every daily run
and every live run (the snapshot's `extras.security`). Kept like the other
detail kinds (`report.retention_days`, 400). Not counted for a day collected
before 2.21: the figure is then null ("not recorded", never 0); `backfill`
counts it for a day whose raw lines are still on the server.

| field | type | meaning |
|---|---|---|
| `rules` | object | the thresholds the day was counted with, and `exposure_rule` (2 since 2.21.1; absent: a day counted by 2.21.0, which no alert and no mail reads until it is recounted) |
| `probes` | int | scanner probes, the bare-IP lines of other hosts included |
| `probes_other` | int | of which lines of a host the site does not list (bare IP only), counted in no group |
| `scanners` | int | pairs with a probe |
| `addresses` | int | distinct addresses among them |
| `requests` | int | every request of those pairs |
| `categories` | `{category: n}` | probes by what they looked for; adds up to `probes` |
| `status` | `{"2xx": n, ...}` | probes by status class; adds up to `probes` |
| `countries` | `{cc: n}` | probes by the pair's first line's country (`Unknown` none), top 10 and `(all others)`; adds up to `probes` |
| `hosting` | int or null | probes from a hosting or cloud network (the hosting list `bots.ranges_dir` keeps); null when there is none |
| `forged` | int | suspects with a forged referrer |
| `bare_ip` | int | probes sent to a bare IP |
| `paths` | `{path: n}` | probes by path (no query string, 200 characters), top 20 and `(all others)`; adds up to `probes` |
| `exposure` | object | `answered` (probes whose path is a probe, answered 2xx), `query_only` (query-only probes answered 2xx, never judged; `answered + query_only = status["2xx"]`), `shell`, `empty`, `possible`, `unknown` (add up to `answered`), `hosts` (`{host: {"bare_ip","shell_size" (the fallback size most paths share; null: none found),"shell_paths","shell_sizes" (every fallback size, once per tolerance),"answered","shell","empty","possible","unknown"}}`), `rows` (every `possible` and `unknown` answer, possible first, then by time, at most 200: `{"host","path","at" (UTC),"status","size" (null: not recorded),"verdict","category","shell_size","who"}`), `folded` (answers beyond the 200) |
| `attacks.injection` | object | `requests` (= `categories.injection`), `kinds` (`{kind: n}`, adds up to `requests`), `rows` (per pair and kind: `{"who","kind","requests","first","last","status"}`, most first, at most 100) |
| `attacks.login` | object | `posts` (every POST in an episode), `episodes`, `rows` (`{"start","end","posts","status","path" (the most posted),"paths","who": [seq]}`, most first, at most 100) |
| `attacks.bursts` | object | the same with `requests` |
| `fake` | object | `requests`, `pairs`, `kinds` (`{kind: n}`, adds up to `requests`), `pages` (their page views by path, top 10 and `(all others)`) |
| `signs` | object | log signs (2.21): `gateway` and `php`: `{"requests","hours": {"YYYY-MM-DDTHH" (UTC): n}}` (502/503/504 answers; paths matching `\.php\d?(/|$)`; every group, the site's hosts only; hours add up to `requests`); `posts`: `{"recorded" (POSTs whose line has request_length=),"large" (of `large_post_bytes` or more),"max","paths" (large ones by path, top 5 and `(all others)`)}`, or null when no line of the day recorded the field |
| `who` | list | the suspects, worst first (probes, then login and burst requests, then requests, then the first time), at most 300: `{"seq","kinds" (scanner/attack/fake),"first","last","requests","probes","categories","status" (all its requests),"probe_status","forged","bare_ip" (its requests to a bare IP),"country","hosting","fake" (its most frequent kind),"fake_requests","injection","login","burst","paths" (its top 5 probe paths),"pages" (its top 5 fake page views)}` |
| `who_folded` | int | suspects beyond the 300 |

`who` (and an episode's `who`) is the row's sequence number: never an address.
verify (`security.check`) holds every sum above; a day whose sums fail is withheld.

## The addresses behind the rows (conversions.sqlite, schema 8)

Only while the site keeps addresses (`privacy.keep_ips` full or short), for the
days inside `privacy.keep_days`, written by the daily run (state `whole`) and
every live run (today, state `today`); pruned with the kept visits; deleted by
`skald forget --ip`. Module `skald/security_kept.py`.

| table | columns |
|---|---|
| `security_rows` | `site`, `day`, `seq` (the `who` row), `ip` (in full; shortened with `keep_ips: short`; `(removed)` for a forgotten address), `user_agent` (null when removed) |
| `security_days` | `site`, `day`, `state` (`whole`/`today`), `rows`, `written_at` |

`GET <page>/people/security?first=D&last=D` (people/api.py): owners and admins
only, with the page's CSRF value (basic mode: a same-origin request), at most
400 days; one audit row "security addresses viewed" (the period and the row
count, never an address). Answer: `{"ok","mode" (full/short/off),"keep_days",
"kept_from","days": [{"day","state"}],"rows": [{"day","seq","ip","user_agent"}]}`.

## security.json

Beside each page; a view's says `{"whole_site_only": true}`.

| field | meaning |
|---|---|
| `rules` | the thresholds now |
| `categories`, `injection` | the words for each key |
| `privacy` | `{"ip_mode","keep_days"}` |
| `requests_hours` | how many hours the request log (Site › Requests) keeps |
| `who_days` | 31: the days whose `who` rows the file carries |
| `alerts` | the two security alert rules: `{"cause","on","threshold","unit","group": "security"}` |
| `days[]` | each stored day of the page's 180: `day`, `state`, and `security`: the day kind (with `who_kept`: false and no `who` beyond `who_days`), or null (not recorded) |
| `today` | today so far from the live snapshot, the same shape, or null |

## Your stack (stack.py) and advisories (advisories.py)

Read from outside once a day by run-daily's `stack` step (never stops the run): each of
`site.hosts` once (`www.x` left out when `x` is listed), at most 3, through the safe fetcher
(site_fetch.py); each host the pages load WordPress files from (at most 3) once too; and
`/wp-login.php` on every WordPress host (HEAD, no credentials, no redirect followed).
`security.stack_check: false` turns it off. Kept per day in `stack-<site>.json` beside the
live files, the last 90 days (not in `day_extras`: collecting a day again rewrites its extras,
and this is a fetch, not a count): `{"days": {day: check}}`, a check being

| field | meaning |
|---|---|
| `checked_at` | UTC |
| `hosts[]` | `{"host","role" (site / content origin),"error" (why it was not read, or null),"evidence": {"status","server","powered_by","generator","markers": [..]} or null,"login" (the status of /wp-login.php, on WordPress hosts),"login_error"}` |
| `advisories` | the `updated` date of the list used |
| `read.products[]` | `{"product" (php, nodejs, nginx, apache, litespeed, wordpress, nextjs),"version" (null: not shown by the server),"host","how"}` |
| `read.logins[]` | `{"host","status","open"}`: open when 2xx |
| `read.matches[]` | `{"advisory","product","host","version","state"}`, state `update_needed`, `no_fix`, `check_version`, `fixed`, `not_listed` |

`security.json`'s `stack` is the latest check: `day`, `checked_at`, `hosts` (no evidence),
`products`, `logins`, `matches`, `advisories` (the full entries matched), `list_updated`,
`commands` (the command that shows each product's version), `names`; null before the first.

**Advisories** (`skald/data/advisories.json`, schema 1, shipped with each release): `{"schema": 1,
"updated", "advisories": [...]}`, each `{"id","product","cves","title","severity","score",
"published","branch" ("minor": 8.4, "major": 22),"fixed": {branch: first fixed version},
"no_fix_below" (a branch below which there is no fix),"no_fix_words","affected","summary",
"action","mitigations": [..],"mitigations_note","sources": [https URL]}`, and optionally
`"also_known_as"` (the name the flaw is known by, or null) and `"firewall_notes": [{"product",
"words","source" (https URL)}]` (what a firewall vendor said it deployed, in its own words with
its date; quoted, never a claim that the site is covered). To add one, add an
entry from the vendor's own advisory and bump `updated`. With `security.advisories_fetch: true`
(off by default) the daily run fetches the public repo's copy of the file and keeps a valid,
newer one beside the live files (`advisories.json`).

States: a version below its branch's fixed one is `update_needed`, at or above `fixed`; a
branch below `no_fix_below`, or not listed and older than the newest listed, `no_fix`; a newer
unlisted branch `not_listed`; a version not shown `check_version`.

Second count: `audit_stack.py` (audit_more.DAILY `stack`) reads the kept evidence again with
its own parsing and compares versions with its own code, against the list the check names.

## Alerts to the people on the site (security_notify.py, 2.21)

Kept in accounts.sqlite, tables made on first use:

| table | columns |
|---|---|
| `security_prefs` | `user_id`, `site`, `alerts` (1/0), `mode` (`now` / `daily`), `updated_at`. No row: owners and admins on, `daily` (the daily summary, since 2.36); viewers off |
| `security_items` | `site`, `item`, `kind` (`exposure` / `advisory`), `title`, `todo`, `first_at`, `last_seen_at`, `closed_at` (null while open) |
| `security_sends` | `site`, `item`, `user_id`, `how` (`first`, `reminder`, `daily` (before 2.36), `summary`, `test`), `sent_at` |
| `summary_sends` | `user_id`, `day` (the schedule zone's date), `sent_at`, `items`, `sites`; one row per person and day (summary_mail.py, 2.36) |
| `summary_items` | `user_id`, `day`, `site`, `part` (`security`, `todos`, `setup`), `item`: what each summary carried |

An item's id is `x` (an exposure) or `a` (an advisory match) and the first 12 hex characters
of the SHA-256 of its kind, site and parts (host and path; advisory, host and product): the
same every run, never an address. `security.json` carries it on each exposure row and stack
match (`item`), and the page opens `#threats/exposed?item=<id>` or `#threats/stack?item=<id>`
with that item first. Items come from the live snapshot (today), the last whole, verified day
and the latest stack check; one no longer found is closed. Since 2.36 the live run and
run-daily's `security mail` step only keep `security_items` up to date. The people who chose
`daily` (the default) get the items in the daily summary (summary_mail.py, `skald summary-mail`,
01:00 in the schedule's zone: one mail per person and day for all their sites, with the open
to-dos and set-up problems; a `summary` row per item carried). The people who chose `now` get,
after every site of a live run or run-daily, ONE mail with every item due on all the sites they
chose it for (never one per item); each person gets each item once, then a reminder every
`security.remind_days` (3) days while it is open (a summary that carried it counts). Recipients: members of the site's organisation with a password set (the
invite used) and not disabled; an exposure is not mailed again to an address the site's alert
mail already reaches (alerts on, mail on, `security_exposure` on). Each send is an audit row
`security.alert.sent` (actor `skald`, target the address, detail `<item> <kind> <how>`); each
summary one `summary.sent` per organisation it covered (detail `<day> <n> items on <k> sites`).

Routes (security_api.py, sessions mode; 404 in basic mode), under `settings/` which nginx
already passes: `GET settings/security-prefs` (`{alerts, mode, default, role, email, summary_at, open}`),
`POST settings/security-prefs` (`{alerts, mode}`, the caller's own choice, any member), `POST
settings/security-test` (owners and admins; 3 in 10 minutes; the CSRF value and same-origin).

## The second count

`audit_security.py` (audit_more.RECOUNTS `security`) rebuilds the whole blob
from the raw lines by its own code: its own pairing, category, referrer,
asset, shell (bisect over sorted sizes), episode (two pointers and a
difference array) and ranking; the hosting list read by the audit's own
crawler checks. Every leaf of the stored blob is compared. On a whole day kept
with addresses, every kept row's address and agent must be the recount's own
ranking's (shortened by the documented rule on a site that shortens; a site
back to full may hold a shortened older day), or `(removed)` without an agent.
`audit_more.DAILY` `security_alerts` rechecks the scan-wave alert's figure and
median from history.
