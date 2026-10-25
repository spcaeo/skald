# Alerts, data quality and markers: alerts.json, quality.json, markers.json

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply.

## alerts.json

What the alert check (every live run) found, open and recently closed. The
same file on every page.

| field | type | meaning |
|---|---|---|
| `enabled` | bool | `alerts.enabled`: the config's, or the site's switch on Site > Alerts |
| `mail` | bool | alerts are mailed (false: evaluated and shown only - staging, or `alerts.mail: false`) |
| `mail_on` | bool | the `alerts.mail` switch itself (config or Site > Alerts), whatever the last check did |
| `checked_at` | ISO or null | the last check |
| `rules[]` | `{"cause","on","threshold","setting"}` | every alert type, whether it is switched on, its threshold in words, and `setting`: the settings key that switches it on Site > Alerts (`alerts.<config name>`, docs/SETTINGS.md) |
| `open[]` | alert | newest first |
| `closed[]` | alert | closed in the last 30 days, newest first |
| `history` | object or null | the citation and crawler rules' last evaluation (alerts_history.py): `{"day","evaluated_at","rules": {"first_citation"/"first_cited_page"/"cited_visits"/"crawler_silent": {"on","state" ("ok"/"waiting"/"off"),"waiting_on": [day],"why" (a waiting rule's reason when it is not a day: history too young),"found": int}}}`; `cited_visits` also has `day_visits`, `median`, `weeks` (how many same weekdays were counted), `skipped` [day] and `verdict` ("rose"/"fell"/"steady"/"too few to judge") once judged. null before the first check |
| `ai` | object or null | the AI rules' last evaluation (alerts_ai.py): `{"day" (the last whole day judged),"evaluated_at","rules": {"started_reading"/"stopped_reading"/"sending_people": {"on","state" ("ok"/"waiting"/"off"),"waiting_on": [day] (withheld, partial, missing or not-recorded days the rule needs),"unjudged": [assistant] (an "(all others)" path row on a day that had to be empty),"found": int}}}`; `sending_people` also has `assistants[]`: `{"assistant","day" (likely visits),"average" (a day, the 28 days before),"verdict" ("jumped"/"vanished"/"steady"/"too few to judge")}`. null before the first check |

An alert: `id` (string), `cause` (`site_down`, `logging_stopped`,
`server_errors`, `not_found_surge`, `crawler_burst`, `new_crawler`,
`traffic_drop`, `ai_started_reading`, `ai_stopped_reading`, `ai_sending_people`,
`ai_first_citation`, `ai_first_cited_page`, `ai_cited_visits`, `crawler_silent`,
`security_exposure`, `scan_wave`, `stack_advisory`, `sale`, `sale_refunded`), `subject` (what it is about: a crawler name, a path, or
`""`), `severity` (`high`, `medium`, `low`), `title` (one plain line),
`detail` (a few lines: the figure, the threshold, what to look at), `figure`
(number or null), `threshold` (number or null), `opened_at`, `last_seen_at`,
`closed_at` (ISO or null), `mailed` (mails sent for it), `repeats` (checks
that found it again while it was open and were not mailed - they go in the
daily digest). An AI alert also has `data`: `{"kind","assistant","crawlers","day","window",
"pages" | "visits","average"}` (the webhook body, docs/INTEGRATIONS.md); its `subject` is
`"<assistant>: <path>"`, `"<assistant>: pages"` (more than `ai_max_pages` pages in one alert) or
`"<assistant>: jumped"`/`"vanished"`, and `rules[]` rows for them carry `"group": "ai"`.

The AI rules count nothing new: they read the day kinds `crawler_paths` (checked by
robots.check, recounted by audit_release2) and `ai_likely` (checked by ai_likely.check,
recounted by audit_ai_likely.py), and the `pages` kind (a page answered to an assistant), on
whole `ok` days only. A withheld, partial, missing or not-recorded day in a rule's window makes
it wait. Settings `alerts.ai_*` (config.example.yml).

The citation and crawler alerts (alerts_history.py) also carry `unit` (`"visits"` or
`"requests"`, never both) and `data` by `data.kind`:
`first_citation` `{"assistant","day","at" (UTC),"path","visits" (that day's visits from its
citations, or null: not recorded),"history_since"}` (subject: the assistant, e.g.
`"claude.ai"`); `first_cited_page` `{"day","pages": [{"path","assistant","at","visits"}],
"history_since"}` (subject: the path, or `"pages"` for more than `first_max_pages`, figure =
pages); `cited_rose`/`cited_fell` `{"day","visits","median","weeks": [{"day","visits"}],
"skipped": [day],"spike_factor","drop_percent","minimum"}` (subject `"rose"`/`"fell"`);
`silent` `{"crawler","group","day","quiet": [first, last],"window": [first, last],
"active_days","requests","last_seen"}`. They read the `page_milestones` table and the
`counts` kinds `cited_by`, `cited_page` and `reader_source` ("AI assistant"), and the
`crawler_paths` day kind; nothing new is stored but the alert state. Run-daily's recounts
(audit_alerts.py) work each kept alert's figures out again from the stored days' `page_firsts`
and `crawler_paths` blobs and the `counts` rows, with its own code.

The security alerts (alerts_security.py, 2.21) carry `unit` and, for an exposure, `data`
`{"host","path","at" (UTC),"category"}`. `security_exposure` (subject `"<host><path>"`,
figure the answer's bytes, threshold the host's fallback page size or null): a scanner probe
answered 2xx with a size unlike the host's fallback page (the day kind `security`'s exposure
rows, verdict `possible`), from the live snapshot (today) and the last whole, verified day;
on by default, so it follows `alerts.enabled` and `alerts.mail`. `scan_wave` (subject the
day, figure its probes, threshold `max(scan_wave_factor x median, scan_wave_minimum)`):
the last whole day's probes against the median of the `scan_wave_days` (14) whole, verified
days before that have the figure, at least `scan_wave_min_days` (7) of them, else it waits;
off by default (`alerts.scan_wave`). Its evaluation is kept in the alert state (`security`:
`{"wave": {"state","day","figure","median","need","days","found"},"settings"}`) and
rechecked from history by audit_security.recheck (audit_more.DAILY `security_alerts`).
`stack_advisory` (subject the item id, `data` `{"item"}`, no figure): an advisory
shipped with Skald matches the site's stack in the latest daily check (update needed, no
official fix, check your version), one per advisory, host and product; on by default. Rows of
`rules[]` for them carry `"group": "security"`. Each person's own security mail is
docs/DATA-CONTRACT-SECURITY.md, "Alerts to the people on the site".

The sale alerts (alerts_sales.py, 2.33) are events, not conditions: each is opened and
closed at once (`closed_at` = `opened_at`), so it is listed in `closed[]`, mailed once and
never reopens. Both are off by default (`alerts.sale`, `alerts.sale_refund`; the minimum
`alerts.sale_minimum`, docs/SETTINGS.md "Sale alerts"); `rules[]` rows for them carry
`"group": "revenue"`. `id` is `"<cause>-<16 hex>"` and `subject` the 16 hex: the start of
the sha256 of the stable key, the same on every run, so the webhook outbox drops a repeat
too. `severity` `low`; `figure`, `threshold` and `unit` null. `data`:

- `sale` `{"kind": "sale", "value_minor", "currency", "amount" (as the dashboard shows it,
  e.g. `"$49.99"`), "stage" (`paid`/`completed`), "renewal" (bool), "at" (the sale's UTC
  time), "source", "first_source" (shown words: "Direct", "Not recorded"), "campaign",
  "landing" (the path without its query string), "label", "tool"}` (null: not sent). The
  key: site, `sale`, tool, external ref.
- `sale_refunded` `{"kind": "refund", "value_minor" (this part), "refunded_minor" (the
  sale's refunded total after it), "sale_minor", "currency", "amount", "stage": "refunded",
  "at" (the part's UTC time), ...the same attribution}`. The key: site, `refund`, tool,
  external ref, the refunded total after the part.

What counts is the Revenue tab's rule (conversions_revenue.Book): a sale or a counted refund
part, never a test row, nothing before `revenue_since`. Nothing new is counted, so there is
no second count: the amount is the row's own.

The alert state (`alerts-state.json`) keeps them under `sales`: `{"since":
{"sale"/"sale_refunded": UTC stamp (the run that first saw the switch on; gone while it is
off)}, "done": {key hash (32 hex): [UTC stamp, "sent" | "below" (under the minimum)]},
"signature": [...] (the settings and the last ids the last look saw: unchanged, nothing is
read)}`. An alert goes only for a sale or part received (`received_at`) at or after `since`
and made (`at`) in the last 72 hours; `done` keys are dropped 72 hours + 14 days after their
stamp, when nothing that old can alert. The state is written with them before any mail or
webhook goes, so a crash while sending never sends one twice (at most once); a failed mail is
noted on the alert (`mail_error`) and not retried. At most 20 a run; the rest wait for the
next. Never from a replay (`--today`).

## quality.json

Is the input trustworthy - the data-quality panel.

| field | type |
|---|---|
| `days[]` | `{"day","state", ...}` - when the day has figures: `lines`, `unparsed`, `duplicates` (byte-identical to an earlier line in the same second; kept and counted), `duplicates_removed` (lines repeating an earlier line's request id `rid=`: the same request written twice, dropped before counting; null for days collected before the log carried `rid=`), `old_format` (lines in the combined format: no host, no country), `first_line`, `last_line` (HH:MM local), `gaps` `[{"from","to","minutes"}]` (no line at all for more than 10 minutes), `files` (log files read), `not_rendered` (bots.json's `{"requests","pages","readers"}`: browser-like requests moved to bots, null before 2026-10-11), `not_pages` (2.35: `{entry: {"requests","people"}}`, the site's requests shaped like a page view that the not-a-page list kept out of the page views, by entry name (`markdown`, `wp_rest`, `feeds`, ..., or `"own: <entry>"` for the site's own; CLASSIFICATION.md "What decides a page view"); `{}` none; null for days collected before 2.35), `verify` (`"ok"`, `"withheld"`, `"partial"`), `problems` (string), `audit` `{"state": "ok"/"mismatch"/"not run", "at": ISO or null, "compared": int or null, "problems": [string]}`. Fields null when the day was collected before release 2. |
| `today` | null, or `{"state","lines","unparsed","duplicates","duplicates_removed","old_format","gaps","first_line","last_line","newest_line" (ISO),"clock_skew_s" (server clock minus the newest line, seconds; large = logging stopped or the clock is wrong),"files","not_rendered","not_pages"}` |
| `runs` | `{name: {"last_ok": ISO or null, "last_fail": ISO or null, "last_exit": int or null, "expected_every_min": int}}` for `live`, `run-daily`, `verify-bots`, `alerts`, `backup`, `pagespeed`, and `heartbeat` (its last answered beat in the log) |
| `rotation` | `{"files": [{"name","bytes","modified"}]}` - the log files on disk now, newest first |
| `builders_failing` | `[{"file","error","since"}]`: optional data files whose builder failed on this redraw (see below); `[]` when all were built |

**A data file that failed to build.** The core files - overview, live,
visits, hourly, breakdowns, health, ours, quality - are always built or the
run stops. Any other file whose builder raises is written as the envelope
plus `{"state": "error", "error": "<short message>"}` and nothing else, and
listed in `quality.json` `builders_failing` with the time it started
failing; every other file is still written. Show such a file as "could
not be built", never as empty or zero.

## markers.json

Things we did, to draw as vertical lines on every chart.

| field | type |
|---|---|
| `markers[]` | `{"at": ISO, "kind", "label", "detail"}`, newest first, the last 180 days. `kind`: `website_release` (a release directory on the server), `skald_deploy`, `config_change` (the skald config changed), `ours_change` (an internal address added, removed, paused, resumed or edited), `backfill` (history recounted), `page_change` (a page someone marked changed, by day: `day`, no time, `at` its midnight, with `change` its id and `path`; [DATA-CONTRACT-PAGE-CHANGES.md](DATA-CONTRACT-PAGE-CHANGES.md)) |
| `website_version` | string or null: the version the live site's footer shows now, e.g. `"v1.4.0 · build 212"` |
