# AI & bots: bots.json, robots.json, crawler_cost.json, ai_activity.json

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply.

## bots.json

`days[]` and `today`: `requests` int, `probes` int (scanner probes),
`agents` `{short name: requests}` (monitors, SEO suites, unfurlers,
crawler sessions in browser clothes; null in `today`), `statuses` (bots'
status classes).

From release 2 (null on days collected before it; `today` has them too):

| field | type | meaning |
|---|---|---|
| `link_previews` | `{app: requests}` | link-preview unfurlers by app (`Slack`, `iMessage`, `WhatsApp`, `LinkedIn`, `Microsoft Teams`, `Discord`, `Telegram`, `X (Twitter)`, `Facebook`, `Skype`, `Pinterest`, `Reddit`, `Embedly`, `Iframely`, ...). A preview means someone pasted a link in a chat. Filed under bots; included in `requests` and in `agents` as `"link preview: <app>"`. |
| `verification` | `{crawler: {"group","method","verified","unverified","spoofed"}}` | every named assistant or search crawler that came, checked against its owner's published ranges or by reverse+forward DNS. `group` is `answer_engines` or `search_engines` (where it counts when not spoofed); `method` is `ranges`, `dns`, `network` (the owner's network list) or `none` (nothing published: always `unverified`). `spoofed` requests are filed under **bots** as `"claims to be <crawler>"` (and counted in `requests`); `verified + unverified` add up to the crawler's requests in its group. |
| `fake_browsers` | `{"hosting_network","fan_out","bare_mozilla": {"requests","addresses"}}` | browser-looking requests counted in **people** that carry a warning sign: from a cloud or hosting network, the same agent from 10+ addresses within 10 seconds, or the bare agent `Mozilla/5.0`. Flags only - they stay in people until a rule is proven; one request can carry several flags. |
| `not_rendered` | `{"requests","pages","readers"}` | browser-like requests moved to **bots** because their visit never rendered a page (no own script, style or `?_rsc=` payload near a page, no beacon event, not seen rendering earlier that day or reading on an earlier day; `rendering.py`, CLASSIFICATION.md rule 9). `pages` are their page views; `readers` the visits among them that read a page - the visitors this rule took out. In `requests` and in `agents` as `"browser-like, never rendered the page"`. Absent on days collected before 2026-10-11. Recounted by the audit. |
| `too_fast` | `{"requests","pages","readers"}` | browser-like requests moved to **bots** because their visit read pages faster than a person can: at least `site.too_fast_pages` (6) page views, all within `site.too_fast_seconds` (2) of the first (`too_fast.py`, CLASSIFICATION.md rule 9b). A visit that never rendered is in `not_rendered` instead. Same three figures as `not_rendered`. In `requests` and in `agents` as `"too fast to be a person"`. Absent on days collected before the rule. Recounted by the audit (`audit_too_fast.py`). |
| `blocked` | `{crawler: n}` | 403 answers to each AI crawler of the AI crawler settings' catalog (`bot_policy.CATALOG`, by the token in its user agent), whichever group it counts in: what the settings refused, plus any other 403 that crawler got. Null on days collected before 2026-10-08; `{}` when none. Recounted by the audit. |

The AI crawler settings themselves are not a data file: AI & bots > Crawler rules reads and
saves them through the refresh helper, `GET <page>/bot-policy` and
`POST <page>/bot-policy` with `{"owners": {assistant: "allow"|"block"|"block_training"},
"crawlers": {name: "allow"|"block"}}` (admins only, same-origin). Both answer
`{"ok", "policy", "modes", "assistants": [{"owner","mode","crawlers": [{"name","tier"
("training"|"index"|"asked"),"robots_only","override","effective"}]}], "blocked": [name],
"robots_suggestion": text, "applied": {"at","ok","changed","error","blocked",
"policy_updated_at","conf_sha256"} or null}`, plus `"error"` on a refused save.
bots.json says whether that route exists: top level `api` is
`{"bot_policy": "bot-policy"}` (relative to the page) when the config has
`bot_policy.enabled: true`, else null - then the page fetches nothing and
shows the settings as not set up.
`applied` is the last time root's path unit wrote the nginx map; when its
`policy_updated_at` is older than the policy's `updated_at`, the change is
still being applied (seconds).

Top level (not per day): `ranges` `{list: {"fetched": ISO or null, "networks": int, "ok": bool, "error": string or null}}` - when each published list was last fetched; `dns_cache` `{"addresses": int, "checked_at": ISO or null}`.

## robots.json

The site's own robots.txt beside what each crawler actually fetched
(`robots.py`). robots.txt is fetched by the live run at most once an hour
and kept beside the history; verdicts use Python's `urllib.robotparser`
with the crawler's own token.

| field | type |
|---|---|
| `robots` | `{"url","fetched_at" (ISO or null),"ok": bool,"error": string or null,"groups": [{"agents": [token],"allow": [path],"disallow": [path],"crawl_delay": number or null}],"sitemaps": [url]}` |
| `crawlers[]` | one per assistant, search crawler or named bot seen in the last 30 days and today: `{"name","group","token" (the token matched against robots.txt),"applies" (the robots.txt group that applies: a token or "*"),"root_allowed": bool,"days_seen": int,"requests": int,"paths": int (distinct paths),"disallowed": int (requests for paths robots.txt disallows it),"disallowed_paths": [{"path","n"}] (top 10),"today": {"requests","disallowed"} or null}` - newest activity first |
| `days[]` | `{"day","state","crawlers": {name: {"requests","disallowed"}} or null}` (30 days) |

Requests are counted per day per crawler by path (`day_extras` kind
`crawler_paths`, the top 200 paths per crawler and an `"(all others)"`
row, verified and audited); `disallowed` is judged against the robots.txt
fetched at `robots.fetched_at` - rules change, so a past day is judged by
today's rules, and the file says so.
`llms_txt.json`, a suggested /llms.txt: [DATA-CONTRACT-LLMS-TXT.md](DATA-CONTRACT-LLMS-TXT.md).
`crawl_health.json`, the day kind `crawl_health` and the `sitemaps/` lists, each crawler beside the site's sitemap: [DATA-CONTRACT-CRAWL-HEALTH.md](DATA-CONTRACT-CRAWL-HEALTH.md).

## crawler_cost.json

What each crawler, assistant and bot cost the server (`crawler_cost.py`).
Counted per day into the `day_extras` kind `crawler_cost` (kept
`report.retention_days`, like the other per-day detail), checked by verify and
recounted by the audit (`audit_crawler_cost.py`). Only the three machine groups:
`answer_engines` and `search_engines` by the name the classifier matched, `bots`
by the name `bots.json` `agents` uses (a check, a preview, a crawler session, or
the short name the user agent announces); a scanner probe with no other name is
`"(scanner probes)"`. People and our own traffic are never in it. No address.

The day kind, `{"groups": {group: {name: entry}}}`, one entry per name:

| field | type | meaning |
|---|---|---|
| `requests` | int | every request it made that day |
| `bytes` | int or null | the log's body-size field summed over the lines that have one; **null (not recorded) when none of its lines had a size** |
| `sized` | int | lines with a size. Below `requests`, `bytes` is a partial sum and the page says so |
| `ms`, `timed` | int or null, int | response times in whole milliseconds (each line's time rounded), summed, over the `timed` lines that logged one; `ms` null when `timed` is 0 |
| `p90_ms` | int or null | the day's 90th percentile, nearest rank (the smallest time at least 90% of its timed lines took no longer than); null when `timed` is 0 |
| `status` | `{"2xx","3xx","4xx","5xx": n}` | requests by status class; errors are 4xx + 5xx |
| `paths` | int | distinct paths (query string cut, first 200 characters) |
| `pages` | `{path: n}` | the 10 paths it fetched most, and `"(all others)"`: adds up to `requests` |
| `countries` | `{code: n}` | its requests by the line's country (cc= or the GeoIP file), `"Unknown"` for none; top 10 and `"(all others)"` |
| `agents` | `{user agent: n}` or null | the user-agent strings it sent, first 200 characters; top 5 and `"(all others)"`. A named crawler's own strings only: **null (not kept)** for the bots whose string may be a person's browser - `"(scanner probes)"`, link previews (iMessage sends the sender's Safari string), browser-like crawler sessions, visits that never rendered, `"browser-like agent"` and the Googlebot template. The only user-agent strings history or the live snapshot holds |
| `last` | ISO | its last request of the day, UTC |

Each group keeps its 50 busiest names; the rest are one `"(all others)"` entry
with `requests`, `bytes`, `sized`, `ms`, `timed`, `status`, `names` (how many were
folded), `last`, and `p90_ms`, `paths` null. Verify holds: each group's entries
add up to the group's requests; each entry's statuses, pages, countries and
agents add up to its requests; `bytes` is null exactly when `sized` is 0, `ms` and
`p90_ms` exactly when `timed` is 0. Body size: nginx and combined logs' `$bytes`
field (`-` is none), Vercel `responseByteSize`, Netlify `response_size`, an edge
record's `bytes`, Caddy's `size`, the CDN formats' own fields. Response time:
nginx's `$request_time`, the combined layout's number after the user agent,
Netlify's `duration`, the CDN formats' own; Vercel, Caddy and edge records give
none, so their times are not recorded.

The data file:

| field | type |
|---|---|
| `days[]` | `{"day","state","names": {group: {name: {"requests","bytes","sized","ms","timed","p90_ms","status","paths","last", "tier" (answer engines: "training" or "asked"), "names" (a fold only), and on the last 30 days only "pages","countries","agents"}}} or null}` (180 days; null: collected before this was counted) |
| `today` | the live snapshot's day the same way, lists included, or null |
| `detail_days` | 30: how many days carry the lists |

Over a range the page sums `requests`, `bytes`, `sized`, `ms`, `timed` and the
statuses; the mean time is `ms / timed` (weighted by request); the p90 is shown
for one day only (a range's p90 cannot be built from daily ones); distinct paths
are each day's count summed (a path fetched on two days counts twice), and
re-crawl is `requests / paths`, fetches per distinct path within a day.

## ai_activity.json

| field | type |
|---|---|
| `today` | null, or `{"events": [...], "total": int, "by_name": {name: {"kind","events","visitors","repeat"}}}` (`visitors`/`repeat` null without the visitor key; a view's `by_name` is null and its events are the ones on its paths) |
| `days[]` | `{"by_name": {name: {"kind","events"}}, "by_kind": {"reader"/"asked"/"training": {"visitors","repeat_visitors"}} or null}` - visitors are distinct keyed hashes that day (whole site), repeat ones were seen on an earlier day within 30 |
| `repeat_window_days` | 30 (the file says 30 even when `visitors.repeat_days` is changed) |
| `likely_ai`, `days[].ai_likely`, `today.ai_likely` | likely sent by an AI assistant, inferred (null: not recorded): [DATA-CONTRACT-AI-LIKELY.md](DATA-CONTRACT-AI-LIKELY.md) |
| `days[].ai_read`, `today.ai_read` | what an AI visit's assistant fetched before it, per assistant (null: not recorded): same file |
| `repeat_counts` | `"days"`: `times_seen_30d` counts distinct days the visitor was seen in the 30 days ending today, today included |

These addresses are written only here and in the private snapshot file
`live-<site>-ai.json` beside history (mode 0640); never in history, the
other data files, CSV exports or mail. (A site that keeps addresses keeps
its readers' visits in `conversions.sqlite`, not here.)

`events[]`, newest first, at most 200: `at` (ISO local), `name`
(`"ChatGPT-User"`, `"GPTBot"`, or the assistant a reader came from, e.g.
`"chatgpt.com"`), `kind` (`"asked"`, `"training"`, `"referred"` = a reader
who arrived from an assistant, one per page loaded), `path`, `status`,
`country` (code or `""`), `country_name`, `ip` (from today's raw log),
`repeat` (bool or null when the visitor key is not configured),
`times_seen_30d` (int or null), `first_seen` (date or null).

Repeat: the visitor is `HMAC-SHA256(SKALD_VISITOR_KEY, ip) + family`
(family = the assistant or crawler name; for readers the browser family and
system). History keeps that hash per day (`visitor_days`) for
`visitors.repeat_days` (default 30) days, then deletes it. `repeat` = the
same hash on an earlier day within that window.
