# SOP: measuring who visits a website

Written for someone picking this up cold, in another repository, with a server
and a question. It is the method, not the code; `CLASSIFICATION.md` covers the
buckets and `COUNTING-TRAPS.md` covers the ways this goes wrong.

## 1. Two data sources, two different questions

There are only two places the truth lives, and they do not overlap.

**Server access logs** - every request that reached the web server, with the
URL, the status, the referrer and the user agent. They answer:

- how much traffic there was, and from where
- which bots, crawlers and AI assistants came, how often, and for what
- which pages were read, and which were only fetched
- which countries, if the server was told to log them
- how many of those requests were scanners hunting for credentials

**The application database** - your own tables. It answers:

- signups, leads, trials, orders, revenue
- which account did what, and when
- conversion from a visit to a customer

Logs cannot tell you about a conversion: nothing in a log line knows a form was
submitted by a person who later paid you. The database cannot tell you about
bots: a crawler never creates a row. A report that claims both from one source
is guessing at half of it. The traffic figures come from logs only, and say
so. Leads and conversions come from the site's own database (read-only) and
signed webhooks (docs/INTEGRATIONS.md), and are counted on their own.

## 2. Why server-side, and not a JavaScript tracker

**Bots do not run JavaScript.** That is the entire reason this approach exists.

Google Analytics, Plausible, Fathom and every other client-side tracker work by
running a script in a browser. GPTBot, ClaudeBot, Googlebot, a credential
scanner and a monitoring probe all fetch the HTML and never execute the script,
so none of them appear in any of those tools. On the reference log, 91% of all
requests came from something that was not a person - and a JavaScript tracker
would have reported none of it.

The trade is real and worth stating: a tracker can see client-side navigation,
scroll depth and events; logs cannot. Use both. Just never ask the tracker
about bots, and never ask the logs about conversions.

## 3. The log format you need

The reference deployment is nginx behind Cloudflare, with three things appended
to the stock format: the referrer, the user agent and the Cloudflare country
header.

```nginx
log_format intel '$time_iso8601 $remote_addr $host "$request" '
                 '$status $body_bytes_sent "$http_referer" '
                 '"$http_user_agent" $request_time '
                 'cc=$http_cf_ipcountry ray=$http_cf_ray';

access_log /var/log/nginx/access.log intel;
```

The reference server also ends each line with ` rid=$request_id`, so a line
nginx wrote twice can be dropped rather than only counted (DEPLOY.md,
"Request id in the log"). Lines with and without it parse.

Three fields earn their place:

- **`$http_referer`** is the only way to know a person arrived from an answer
  engine. Someone who clicks a citation in ChatGPT is running an ordinary
  browser; nothing in their user agent says where they came from. Take the
  referrer out of the log and the number that matters most - people who found
  you through an AI - becomes unmeasurable, not merely approximate.
- **`$http_user_agent`** is how every crawler identifies itself. It is
  self-reported and forgeable, which is why `people` is an upper bound and
  never a count of humans.
- **`cc=$http_cf_ipcountry`** is the country, as Cloudflare resolved it. With
  no such header the country is **Unknown, not guessed**, unless
  `logs.country_db` names a GeoIP country file (`.mmdb`, DB-IP's free file
  works): then a line with no country of its own gets its address's country
  from that file. That is a lookup in the same file nginx's module would read,
  not an inference. A country the line carries always wins. `XX` means
  Cloudflare could not tell and is treated as no country.

  Without Cloudflare, nginx can look the country up itself from a local
  database with the GeoIP2 module, and log `cc=$geoip2_country` in the same
  place. The free databases (DB-IP Lite, CC BY 4.0) require attribution
  wherever their data is shown: set `report.country_credit` and
  `report.country_credit_url`, and every place countries appear - dashboard,
  mail, report - carries it as a plain text link. When `logs.country_db` is
  one of DB-IP's files, its credit is shown without either setting. `-`, an empty value and
  `ZZ` all mean no country. Anything after the country (`ray=-` as a literal
  dash, say) is ignored.

Two details that will cost you an afternoon if you skip them:

- The parser allows exactly one field between the user agent and `cc=`. That is
  `$request_time` above. If your format has nothing there, put a literal
  placeholder in - otherwise the line still parses and the country is silently
  empty. There is a test pinning this behaviour.
- `site.hosts` in `config.yml` is the list of hostnames the report is **about**,
  and you almost certainly need to set it. One server usually answers for
  several: a marketing site, an API, a customer app, and its own bare IP
  address. On the reference server, leaving them pooled meant 4,265 API calls
  and 3,003 app requests were counted as website visitors, plus 2,695 requests
  straight to the IP — and a request to an IP address is never a person,
  because nobody types one.

  Requests for any other host are counted in `Totals.other_hosts` and reported
  as excluded, never silently dropped, so the subtraction stays visible.
  `verify` checks it. Leave the list empty to count everything, which is right
  for a server with one site on it.

  This needs the host in the log line, so it works with `nginx_extended` and
  `caddy_json` but not the combined format, which does not carry one. Lines
  with no host are counted - there is no honest way to drop them - and the
  report, mail and dashboard each say how many could not be filtered.

Other formats work: `nginx_combined` and `apache_combined` for the stock
combined format, `caddy_json` for Caddy's JSON lines. Both lose the country,
and the combined format loses the host as well. `format: auto` samples the
first 200 lines and picks the richest format that parses them, then tries the
other formats on any line that one rejects. That matters on the day you change
`log_format`: the file starts in the old format and ends in the new, and
without the fallback every new-format line was silently dropped.

A site behind a CDN needs the CDN's log, not the origin's: pages served from
the CDN's cache never reach the origin. `cloudflare_json` (Logpush),
`cloudfront_w3c` (CloudFront standard logs) and `fastly_json` read them, and
`auto` picks each. How to ship each log to the server, and which fields to
turn on, is in [docs/CDN-LOGS.md](docs/CDN-LOGS.md).

## 4. Retention: you have more history than you think

Debian and Ubuntu ship logrotate with `rotate 14` and `daily` for nginx, and
`delaycompress`, so the directory looks like this:

```
access.log          today
access.log.1        yesterday, still plain text
access.log.2.gz     the day before
...
access.log.14.gz    two weeks ago
```

Only two of those are uncompressed. That is why people glance at the directory,
see two readable files and conclude they have two days of history. They have
fourteen. `parse.log_files` builds the list for you - `<base>`, `<base>.1`, then
`<base>.N.gz` - and `parse.read` opens the gzipped ones transparently. Set
`logs.days: 14` and the cost is parse time, not data.

Check your own retention before promising anyone a trend:

```sh
cat /etc/logrotate.d/nginx
ls -l /var/log/nginx/
```

If the server rotates hourly, or ships logs away and truncates, `days` means
something different and you need to read the config rather than assume.

## 5. Four quantities, never to be confused

This is the part that goes wrong in public.

| | What it counts | What it is for |
| --- | --- | --- |
| **hits** | every request | how much work the server did |
| **views** | requests for something a person could read | how many pages were read |
| **visits** | distinct sessions: one address and one user agent, within a 30-minute gap; for people, a page from a new outside source starts a new one (below) | how many browsers came |
| **readers** | visits with at least one page view | the closest honest answer to "how many people read us" - the headline |

A worked example, from the log this package was extracted from. One person, one
address, one browser, fifty seconds:

- **55 hits** - 21 `?_rsc=` React payload fetches, 26 assets, 8 analytics
  beacons
- **0 views** - not one HTML page among them
- **1 visit** - one person

Every one of those 55 requests carried the same `chatgpt.com` referrer. The old
report counted requests and announced "56 people followed a citation to us".
The fixture `tests/fixtures/one_session.log` is that session, and the test
asserts both numbers side by side so the gap stays visible.

Rules that follow from it:

- Never report a count of requests as a count of people. If a number is going
  to be read as "people", it has to be built from visits.
- A page view is a 2xx response to a GET or HEAD that is not a framework
  payload, an asset or a beacon. A 301 is not a page view: the page the browser
  lands on is logged separately as its own 200, so counting the redirect counts
  that read twice.
- `readers` is the headline, not `visits`. On the audited day 91 of 119
  visits read no page at all: assets, payloads and redirects, mostly from
  crawlers dressed as browsers. Both are shown; only one is people reading.
- A visit that asks for robots.txt, a sitemap, ads.txt or security.txt on the
  site's hosts, and does not render its pages (load the site's own scripts
  and styles for each), is a crawler, and every request in that visit is
  filed under bots - a browser never asks for those by itself.
- `readers` is still an upper bound. A household behind one address is one
  reader; a scraper sending a Chrome user agent that only requests real pages
  is indistinguishable from one.

## 6. Running it on a schedule

```sh
cd /opt/skald
./report.py --check                 # exit 0 means the figures reconcile
./report.py --days 7 --html /tmp/traffic.html
```

Put `--check` in front of the send, and make the send conditional on it:

```cron
# 07:15 daily: verify, then mail. No report goes out if the figures do not add up.
15 7 * * * cd /opt/skald && ./report.py --check >/dev/null \
  && ./report.py --days 7 --html /tmp/traffic.html >/tmp/traffic.txt \
  && /usr/local/bin/send-report /tmp/traffic.html
```

`report.py` withholds the report and exits 1 by itself when the checks fail, so
the gate is belt and braces rather than the only defence. From library code the
equivalent is `report_or_die(totals)`, which raises.

What the checks enforce is in `verify.py`: the five groups must sum to the
parsed total, the answer-engine tiers must sum to their group, no child figure
may exceed its parent, citations may not exceed visits, a parse that
yielded nothing is a failure rather than a calm screen of zeroes, and lines
no format could read may not exceed `report.max_unparsed_percent` (default
1%) of the window's lines. An unreadable line has no timestamp, so it is
placed by the readable line just before it in its file - a quiet day's junk
is not diluted by a busy neighbour sharing the file. That count is shown in every report,
mail and dashboard whatever it is. A wrong log
format produces exactly that calm screen, which is why it is checked.

Three operational notes:

- The reader needs the log directory. `adm` group membership is enough on
  Debian and Ubuntu; running the job as root works but is not required.
- `report.py` makes no network request and writes nowhere except a path you
  name on the command line. It is safe to run from cron on a production box.
- Parsing is single-pass and streaming, but it is still Python over every line.
  14 days of a busy log is minutes, not seconds. Run it off-peak.

## 7. Running it as a system

Section 6 sends a glance at the last N log files. For a history, a dashboard
and a weekly comparison, use `skald`. One cron line does all of it:

```cron
# /etc/cron.d/skald
# Check yesterday, store it, redraw the dashboard, mail it (and the weekly on
# Mondays). A failed run sends one short mail (notify-failure); a withheld day does not.
MAILTO=ops@example.com
15 11 * * * skald . /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml run-daily >>/var/log/skald/run.log 2>&1 || /opt/skald/bin/skald --config /etc/skald/config.yml notify-failure --job run-daily --exit $? --log /var/log/skald/run.log >>/var/log/skald/run.log 2>&1
```

A file in `/etc/cron.d/` names the user after the five time fields
(`skald` above). In a personal crontab (`crontab -e`), leave the user
out.

Cron runs on the server's clock; "yesterday" is worked out in
`report.timezone`. Pick a time at least an hour after midnight in that zone -
11:15 on a UTC server is early morning in New York. It does not need to wait
for logrotate: the day is chosen by timestamp, not by file. DEPLOY.md has
the full server setup.

First time on a server, fill the history from what rotation still holds:

```sh
./bin/skald backfill --days 14
./bin/skald dashboard
./bin/skald mail --weekly --dry-run       # read it before anyone else does
```

**The steps, and what stops them.** `run-daily` runs check, collect,
dashboard, daily mail, and on Mondays weekly mail, and stops at the first one
that fails:

| Step | Refuses when |
| --- | --- |
| check | yesterday's window has no lines, or any verify invariant fails |
| collect | (same figures as check; stored only if they passed) |
| dashboard | the output directory cannot be written |
| daily mail | yesterday is not stored, is withheld, or no longer reconciles when read back; a named SMTP variable is unset |
| weekly mail | any of the last 7 days is missing or withheld |

A weekly mail compares with the week before only if that week is complete;
otherwise it says "not comparable" rather than inventing a fall.

**Files.**

| What | Config key | Contents |
| --- | --- | --- |
| history | `history.db` | SQLite, one row per site per local day |
| dashboard | `dashboard.out` | `index.html` listing sites, `<site>/index.html` each (the web app; `classic.html` is the plain page), with its data files beside it |
| SMTP login | `mail.user_env`, `mail.password_env` | the NAMES of environment variables; the values live in an env file |

**What is stored, and what is not.** Per site per day: requests per group;
people visits, page views and citation visitors (and which assistant they
came from); top 50 pages people read, and countries; answer-engine requests
per tier and per name, and the top 50 pages they fetched; search engines by
name; bots split into scanner probes and the rest by short name; our own
traffic; requests for excluded hosts; whether the day verified. Never: an IP
address, a user agent of a person, a referrer URL. (Later schemas add the
anonymous journeys, kept 7 days, and keyed visitor hashes, kept 30; see
below.) The history file can be shared with anyone who may see the
dashboard. Since 2.4.0 a site can also keep each visit with its address,
and leads' names and emails, in `conversions.sqlite`, apart from the history
(`privacy.keep_ips`, `conversions.identity`; the README's "What is kept"). The file carries a schema
version, and newer code upgrades an older file in place on open, keeping a
copy of it first; nothing is dropped.

**Partial days.** A day is whole only if its own log lines run from within
`report.coverage_gap_minutes` (default 60) of its local midnight to within
that of the next, and the day is over. A log that starts exactly at midnight
is whole. Anything else - launch day, a new server, logging that stopped, a
hole of several days, the oldest day retention still holds, `collect --day
today` - is stored as a **partial day** with the time its data starts or
stops. It is drawn faded and labelled on the dashboard, exported with
`state=partial`, left out of every KPI and comparison, refused by the weekly
mail, and its own daily mail says "partial day, data from HH:MM" in the
subject. backfill collects a partial day again. A site that is genuinely
silent for more than an hour around midnight should raise the gap.

**Two honest limits of summing days.** A visit that crosses midnight counts
once on each day, so weekly visits are a sum of daily visits. Top lists over
7 or 30 days are sums of each day's top 50, so a page that never made a day's
top 50 is missing from the month: the long tail undercounts, the head does
not. The dashboard says both.

**Views by path.** `dashboard.views` is a list of
`{name, path_prefix, exclude_prefix}`. A view counts the requests whose path
starts with `path_prefix` (empty: every path) and with none of the
`exclude_prefix` prefixes (several, separated by spaces). A prefix ending in
`/` also matches the path without the slash, so `/ca/` includes `/ca`.

Each view is the full set of figures - five groups, visits, citations,
pages, engines - over the matching lines only, built in the same pass as the
site, stored under its own key, and verified on its own. Two things follow:

- views that split the paths between them (as the example config's three
  do) add up to the site's requests exactly; that is tested.
- a person who reads pages in two views is a visit in each, so visits do
  not add up across views. Requests do.

A view with no matching lines on a day the site had lines is a true zero,
not a failed parse. Views are computed at collect time: change a view, then
`backfill --days 14 --force` to recompute the days the logs still hold.
Older days keep the figures they were computed with; each history row
records the rule it used (`days.scope`).

**Breakdowns (schema 7).** Each reader - a visit that read a page - is
labelled once, at their first page view, by country, browser, operating
system, device, traffic source, referring site, campaign, landing page and
hour, so every one of those lists adds up to the readers. Every group's
requests are split by status class; people's 404s, page speeds and slow
pages, the 5xx and the POST requests are kept by path. Lists longer than
history keeps are folded into an "(all others)" row, never cut, so the sums
still hold. `verify` checks each sum; a day where one fails is withheld.
A period containing a day collected before schema 7 shows no breakdowns
(and says how many days lack them) rather than a sum of some of its days.

**The independent recount.** `skald audit --day D` reads the day's raw
lines again with its own patterns, groups each address and agent's requests
into visits by sorting them, labels each reader's first page, and compares
every group total, status, post count, reader and breakdown label with
what history holds. It is a second implementation: its own parser,
classification order, crawler-visit rule, page rule and labels; it shares
only the name lists (assistants, search crawlers, bots, scanner paths).
`--live` compares today so far with the live snapshot. Anything shaped
like an address is masked in its output. run-daily runs it after collect with
`--withhold`: a mismatch marks the day withheld, and the dashboard and mail
steps do not run. Read its output before overriding it.

What the logs cannot give, and is therefore not shown: a breakdown crossed
with another (each is stored on its own), and anything a browser does after
the page arrives (scrolls, clicks, time on page; the optional beacon,
docs/BEACON.md, counts some of these). New against returning visitors came
later, from keyed hashes (schema 9, below).

**What a visit is.** One address and user agent, no gap over
`report.session_gap_minutes` - and, for people, no page view arriving from a
new outside source. Inside an open visit, a page (a document, not an asset or
a payload) whose source is outside the site - an AI assistant citation,
another website, a search engine, social, email, a tagged link (utm or click
id) - and whose source, referrer and campaign differ from the visit's first
page's starts a new visit. A page from the site itself, or with no referrer
and no tag, continues the visit; so does the same outside source again. This
is Google Analytics' session rule. Why: a reader who opened the site directly
and came back from perplexity.ai two minutes later was one "Direct" visit, so
the citation count said perplexity 1 while sources and visits said 0
(docomatic.ai, 2026-10-12). The split lives in `aggregate._Sessions`,
`visits.Journeys` and the requests feed (`dimensions.new_source`), and again,
written apart, in `audit.py` (`_elsewhere`). Crawler, bot and rendering
judgements (`rendering.py`, `classify.crawler_visits`, `bot_counts.py`) still
split on the gap alone: whether a browser drew is about the browser, and a
returning reader's assets are cached. It applies to days collected from the
release that brought it (2026-10-12) on; a stored day changes only with
`backfill --force`, and an audit of a day collected before it can differ
where a reader came back from outside inside the gap.

**Visits (schema 8).** A visit is the readers' own session (above) - so
visits equal readers, and verify withholds a day where they do not, or where the visits'
pages do not add up to the pages read. The key is hashed in memory with a
salt made for the run and never written. Each visit becomes an anonymous
journey (start time to the minute in `report.timezone`, country, device,
browser, system, source and campaign of the first page, the pages in order,
count, length from first request to last, exit page, 404 and POST flags),
kept `report.journey_days` days (default 7) in the `journeys` table and then
deleted by collect. Figures kept for good, in `counts`: visits by pages
loaded, by pages seen, by length (to the second under a minute, coarser
after), exit pages, steps from page to page, flags. Entry pages, sources,
countries and devices of visits are the readers breakdowns. A same-site
referrer naming a page the visit was not last seen on is an "in-app" move -
shown, never counted as a page view; a cancelled request (499) is not
evidence. What logs cannot give: time spent reading (a one-page visit is
seconds long), and an in-app move that loaded nothing. `skald audit`
recounts every visit figure and our own traffic by label
(`skald/audit_visits.py`, its own code).

**Schema 9: extras, returning visitors, insights.** `day_extras` keeps one
JSON blob per day per kind (hourly, ours, not_found, pages, campaigns,
returning) and `visitor_days` keeps 30 days of keyed hashes. With
SKALD_VISITOR_KEY set (in /etc/skald/env; `report.env_file`
points there for the refresh helper), a reader whose hash appeared on an
earlier day within 30 days is returning; AI fetchers and readers from an
assistant get repeat flags the same way. Without the key nothing is hashed
and every such field is null. Raw addresses: in the web server's log, on
the private page (today's AI events, the internal-address list), in the
6-hour Recent requests feed (release 2), and, since 2.4.0, with each kept
visit in `conversions.sqlite` while `privacy.keep_ips` is on (395 days by
default). Hashes: 30 days. Journeys: 7 days. Totals: for good.

**Export.** `skald export --from D --to D --table T [filters] --format
csv|json` reads the history, verified days only by default. Every row is
per day unless `--total`; the JSON carries which days were recorded,
withheld and missing, so a gap is visible in the file itself. The dashboard
writes the same tables beside each page under `exports/` on every render, and
`today.csv` only while there is a reconciled snapshot for today. They sit
behind the same sign-in as the pages.

**Today so far.** A second cron line keeps a live panel at the top of the
dashboard:

```cron
*/2 * * * * skald . /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml live >>/var/log/skald/live.log 2>&1
```

It reads today from local midnight to now, verifies it like any day, writes
`live-<site>.json` beside the history file and redraws the dashboard. Three
rules keep it from contaminating anything:

- it never writes the history. A day is stored once, after it ends, by
  collect. A partial day stored as a day would look like a quiet day.
- it is never mailed and never compared. The mail and every change arrow
  read history only; the panel says "live and partial" in words.
- figures that do not reconcile are withheld, as for a whole day. A snapshot
  from yesterday is shown as stale, never as today.

The panel lists the latest 20 assistant fetches and citation clicks: time,
the assistant's name as matched (or the citing site), and the path. No
address and no user agent is written for anyone. The web app fetches the
snapshot again every two minutes; the plain page (`classic.html`) reloads
itself with `<meta http-equiv="refresh">` and runs no script.

Cost: only the files that can hold today are opened (by modification time),
yesterday's lines in them are parsed but not classified, and classification
is cached per user agent - a busy day takes about a second. Run every two
minutes, that is negligible.

**Privacy of the dashboard itself.** It makes no request to anywhere but its
own server (a strict Content-Security-Policy holds it to that), and carries
`noindex, nofollow, noarchive` and `no-referrer`. Still serve it behind
basic auth or sessions mode, with an `X-Robots-Tag` header (DEPLOY.md): the
page lists your top pages and traffic, which is nobody else's business.

## 7a. Release 2: checking claims, watching the input, raising the alarm

**Crawler claims.** A user agent is a claim. `skald verify-bots` fetches, once
a day, every crawler owner's published address list (Google's four,
Bing, Apple, OpenAI's three, Perplexity's two, Anthropic, DuckDuckGo, and
Meta's announced prefixes from RIPEstat) and the hosting networks (the big
clouds and hosters by AS number) into `bots.ranges_dir`, and looks up
reverse-then-forward DNS for crawler addresses no list covers (Yandex has
no list; Google, Bing and Apple fall back to it). run-daily runs it before
anything is counted, so collect and the audit after it read the same
answers; the live run never touches the network. A claim proven false goes
to bots as "claims to be X"; a missing, failed or week-old list keeps the
claim as "unverified" - never moves it. Claude Code fetches pages from the
asker's own machine, so `claude-code/` agents are always "unverified".

**Fake browsers** are flagged, never moved: a browser agent from a hosting
network, the same agent from 10+ addresses inside 10 seconds, the bare
`Mozilla/5.0`. VPN users exit from data centres and a shared link fans out,
so a flag is a reason to look, not a verdict (EDGE A1, A15, A16).

**Recent requests.** The live run keeps the last 6 hours of requests with
the verdict the tally used for each - group, rule in words, kind, page view
- so "why is this a person?" has an answer per line. It holds raw addresses
(the owner's decision) and therefore only its window, in a private file.

**Data quality.** `verify` proves sums, not inputs. `quality.json` shows
per day what the input looked like: unreadable lines, duplicates (counted,
never dropped - a doubled line and a real repeat look the same without
`$request_id`; with `rid=` in the log, a repeated id is dropped and counted
as removed), old-format lines, gaps over 10 minutes, the audit's
verdict; for today, how old the newest line is; and when each job last
ran. Read it before trusting a strange day.

**Alerts.** Checked every 2 minutes from figures the live run already has.
Fatigue rules matter more than thresholds: one mail per alert, a daily
digest for repeats, a resolved line for outages, a cooldown before the same
cause mails again, and nothing from a replay, another host, or a snapshot
that did not reconcile. The heartbeat runs on the same box, so "site down"
means the web server stopped answering; a whole-box outage stops the
alerts too - an outside monitor is a separate choice (ROADMAP P0-3).

**Markers.** Every deploy (`skald mark-deploy`), config change, internal
address change, `backfill --force` and website release is a marker, drawn
on every chart, so a step in a line can be tied to something we did.

**Leads.** The CMS is read read-only (`mode=ro`), aggregates only, and never
joined to a visit: a lead's first touch is what its own browser
remembered, which is not the source of any one visit in the log (EDGE E7).
The funnel shows the logs' steps and the CMS's steps side by side. Since
2.4.0 the person search may list the visits that sent a form near a lead's
time: a listing, matched by time and said to be uncertain, never a figure.

**Backups and deletion requests.** `skald backup` nightly (14 daily, 8
weekly, each restore-tested; the accounts and conversions files too);
`skald forget --ip X` (or `--email`, `--vid`, `--lead`) for a deletion
request. The retention table is in the README.

## 8. Before you trust a number you are about to send

- Did `--check` pass?
- Does the figure you are about to call "people" come from visits, not hits?
- Are the group totals in the text the same ones in the HTML? They are built
  from one `Totals`, so they cannot drift - but if you add a renderer, that
  stops being true.
- Does `quality.json` show the day's audit as ok, with no gaps you cannot
  explain and duplicates near their usual share?
- Has anyone read the raw log this week? The Recent requests tab is the
  quickest way: filter to people and look for what does not belong. Every scanner family in
  `classify.PROBE` is there because somebody read a log and found it being
  counted as a person. The list is only as good as the last log somebody
  actually read.
