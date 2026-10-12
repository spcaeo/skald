# Counting traps

Five ways a traffic report says something false while every line of its
plumbing works. Four of them shipped. They are written out because the code
that prevents them looks arbitrary until you know what it is for.

The report these came from was a daily email with one reader. It was wrong for
days. Nobody noticed, because nothing checked.

---

## 1. Citations counted per request instead of per visitor

**What was reported.** "56 people followed a citation to us."

**What was true.** One person. A single address, one browser, a fifty-second
window: 21 `?_rsc=` React payload fetches, 34 analytics and asset requests, and
**zero HTML page views**. Against the same log, this package reports **1**.

**Why the code did it.** Every sub-request of one browsing session carries the
same `Referer`. The old code counted log lines whose referrer matched an answer
engine, so one person clicking through a Next.js site - where each navigation
fetches an `?_rsc=` payload, and the page then fires beacons and pulls fonts
and images - became as many "people" as their browser made requests. Nothing in
the logic was broken. It was answering a different question from the one in the
sentence it printed.

**How this package prevents it.**

- `Hit.is_page` (`parse.py`) exists so a report can count things a person could
  actually read: a 2xx GET or HEAD that is not a framework payload, an asset or
  a beacon.
- `aggregate.py` keeps three quantities apart and names them so a renderer
  cannot print one while meaning another: `hits` (requests), `views` (readable
  pages), `visits` (distinct sessions, one address and one user agent inside a
  30-minute gap).
- Citations are counted in **visits**, not hits: `GroupStats.cited_visits`,
  incremented once per session key in `summarise`.
- The text and HTML cards both say "counted once per visitor" next to the
  number.

**The check that catches it.** `verify.check` rule 4: `cited_visits` may not
exceed the `people` group's `visits`. Per-request counting breaks that
immediately, because a session is many requests and only one visit.

**The test.** `TestOneSessionTrap`, against `tests/fixtures/one_session.log` -
the same 55-request session, hand-built. One test asserts `cited_visits == 1`;
another computes the old per-request number from the same file and asserts it
is 55, so the gap stays visible in the suite rather than only in this document.

---

## 2. Categories that did not sum

**What was reported.** Visitor categories of 51,763 under a stated total of
55,539.

**What was true.** A gap of 3,776 requests - 7% of the traffic - unaccounted
for.

**Why the code did it.** The classifier had six buckets and the email showed
three. The remaining three were not labelled "other", not shown, and not
subtracted from anything. The total came from one query and the categories from
another, and nothing ever compared them. A reader who adds up three numbers and
gets a different total than the one printed above them stops trusting the
report - correctly, because a gap means something is being counted twice or not
at all, and they cannot tell which.

**How this package prevents it.** The five groups in `classify.Group` are a
partition by construction: `Classifier.__call__` returns exactly one group for
every hit, and its last line is an unconditional fallback so nothing can fall
through unclassified. `OURS` exists as a visible group for this reason - your
own crawler is not traffic, but hiding it would leave a gap, so it gets a card
that says "not traffic; shown so the categories add up to the log".

**The check that catches it.** `verify.check` rule 1: the sum of every group's
hits must equal `totals.parsed`, and the message names both sides so you can
see which one moved. The command line prints `FIGURES DO NOT RECONCILE` and
exits 1; `report_or_die` raises.

**The test.** `TestVerify.test_categories_that_do_not_sum_are_caught` moves the
total by exactly 3,776 and asserts one problem. A companion test deletes a
whole group, which is the same failure from the other direction.

---

## 3. Tiers that over-summed

**What was reported.** Answer-engine tiers adding to 34,495 under a group total
of 34,357 - 138 too many.

**What was true.** Two unrelated category errors that happened to land in the
same row of the same email:

- **82** scanner probes were counted in the tiers but excluded from the group
  total. A probe path was being filed under scanners for the group figure and
  still counted by the per-tier counters.
- **56** citation clicks - which are *people* - were added into the *crawler*
  group. The same 56 from trap 1, now double counted across two groups.

**Why the code did it.** Two different pieces of code decided what belonged in
the group and what belonged in a tier, and they disagreed about two edge cases.
Neither disagreement was visible in the output; both numbers looked plausible.

**How this package prevents it.**

- A probe is **flagged, not moved**. `Classifier.__call__` computes `probing`
  from the URL first and attaches it to whatever verdict it returns, so an
  engine asking for a silly path is still that engine (`group=ANSWER_ENGINE`,
  `probe=True`) and stays in both the group total and its tier. `probe` is
  therefore deliberately ordered *below* the named engines and *above*
  `people`; `CLASSIFICATION.md` has the full order.
- A citation click is a **person**. `Classifier` returns `Group.PEOPLE` with
  `Tier.CITED`, and `aggregate.summarise` only writes to `stats.tiers` for the
  `ANSWER_ENGINE` group. There is no code path that can put a citation in the
  crawler tiers.
- `report.py` renders only `training` and `asked` on the answer-engine card,
  with a comment saying why `cited` is not there.

**The check that catches it.** `verify.check` rule 2: the answer-engine tier
counters must sum to that group's hits, reported as a signed delta (`off by
+138`). Rule 3 backs it up: no child figure - views, visits, probes - may
exceed its parent's hits.

**The test.** `TestVerify.test_tiers_that_over_sum_are_caught` adds a `cited`
tier of 138 and asserts the problem and the delta.
`TestMixedLog.test_a_probing_engine_is_counted_in_both_its_group_and_the_probes`
and `TestClassifier.test_an_engine_asking_for_a_probe_path_stays_an_engine`
pin the ordering that caused the 82.

---

## 4. A scanner counted as a reader

Found while reading the real log this package was developed against, not in
production output - which is the only reason it is not a fourth wrong number in
somebody's inbox.

**What was reported.** `/_ignition/execute-solution` appearing in the "people"
column, 28 of them as page views.

**What was true.** `/_ignition/execute-solution` is a Laravel Ignition debug
route and a remote-code-execution exploit. It is somebody trying to run code on
your server.

**Why the code did it.** The probe list covered WordPress, `.env`, `.git`, admin
paths and credential files. It did not cover framework debug endpoints. The
requests sent an ordinary Chrome user agent, so with no path pattern matching,
the fallback rule - "looks like a browser, nothing else matched, call it a
person" - claimed them.

**How this package prevents it.** The framework debug family is in
`classify.PROBE`: `/_ignition`, `/_debugbar`, `/_profiler`,
`telescope/requests`, `/laravel`, `/vendor/phpunit`, `/eval-stdin`,
`/invokefunction`, `/containers/json`, `/druid/index`, `/geoserver`, `/HNAP1`,
`/owa/auth`, `/autodiscover` and `/.well-known/ALFA`. Adding them moved **93
requests** out of "people" on the reference log - 84 of them `/_ignition`
alone, 56 POSTs and 28 GETs, the 28 having been counted as page views as well.

**The check that catches it.** None, and this is the honest part: no arithmetic
invariant can tell you that a path you have never heard of is an exploit. The
sums were correct all along. `PROBE` is a list of things somebody recognised,
and **it is only ever as good as the last log somebody actually read.** The
comment above that family in `classify.py` says so, and that sentence is the
point of this entry.

What to do about it: read the raw log occasionally, grouped by path, and look
for what is sitting in the wrong column. There is one such case live in the
reference log today - a bare `/env` (no extension), 13 requests, truncated
Chrome user agents and curl mixed together, mostly 404s, currently counted as
people. It is not in `PROBE` because `/env` is also a plausible name for a real
page, and guessing in the regex is how you lose a real one.

**The test.** `TestClassifier.test_a_scanner_sending_a_browser_user_agent_is_a_bot`
and `test_more_scanner_paths_that_send_browser_user_agents`.

---

## 5. Redirects counted as pages read

Found while writing these tests. It had not shipped in a sentence anyone read,
and it was a quarter of the figure.

**What was reported.** `Hit.is_page` returned true for any 2xx **or 3xx**
response, so 15,727 "page views" on the reference log.

**What was true.** 11,734. The other 3,993 - 25% - were redirects: 3,409 `301`,
547 `308` and 37 `304`. A 301 is not a page. The browser is told to go
somewhere else, asks for that page, and *that* request is logged as its own
200. Counting the redirect counts one read twice, and trailing-slash
canonicalisation means a site can generate thousands of them.

**Why the code did it.** `is_page` reused a property called `ok`, whose own
docstring said "a 404 or a 301 is not something anyone read" while its body
tested `status[:1] in ("2", "3")`. The intent was written down correctly and
the code did the opposite. It is the same shape as trap 1 - a number answering
a slightly different question from the sentence printed above it - just
quieter.

**How this package prevents it.** `is_page` now tests for a 2xx directly, with
the reasoning and the numbers in its docstring. `ok` keeps its broader meaning
("answered without an error") and no longer claims otherwise; nothing else uses
it.

**The check that catches it.** No invariant catches this either - the figures
reconciled perfectly before and after, because views have always been checked
only against their own group's hits. It took reading a status-code histogram.
The lesson is the same as trap 4: `verify.py` can prove a report is consistent;
it cannot prove it is true. That still needs somebody to look at the log.

**The test.** `TestPageViews.test_only_a_two_hundred_is_a_page`, which walks
`301`, `302`, `304`, `308`, `404`, `410` and `500`, and
`TestMixedLog.test_views_exclude_payloads_assets_and_redirects`.

---

## 6 to 12. What the real log showed (release 2, 2026-10-07)

Found by reading a production site's log line by line (docs/EDGE-CASES.md has the
numbers). Each is fixed **from 2026-10-07 on**: history is never rewritten.
Days whose raw logs still exist can be recounted with
`skald backfill --days 14 --force` - that run is recorded as a marker
(markers.json), so a chart shows where the rules changed.

**6. Files counted as pages.** `/sitemap.xsl` was 4 "people page views" in a
day: the asset list did not know `.xsl`. Now feed stylesheets, feeds,
documents (`.pdf` is a download, not a read), archives and media are not
pages (`parse.ASSET`; the audit's own list in `audit.py` and
`audit_visits.py`). Test: `test_release2.TestCountingFixes`.

**7. Duplicate log lines.** 58 byte-identical lines in a day, mostly our own
curl tests. Without `$request_id` in the log a doubled line and a real
repeat in the same second cannot be told apart, so they are **counted, not
dropped**, and measured: `quality.json` shows the duplicates per day (a raw
line identical to an earlier one in the same second), and the Recent
requests feed flags each one `duplicate`. The audit counts them again by
comparing raw text. A share that jumps means the log is being written
twice. The real fix is `$request_id` in the nginx format (ROADMAP P0-5).
Done 2026-10-08: the log now ends with `rid=$request_id`. A line repeating
an earlier line's request id is the same request written twice and is
**dropped** (`parse.read`, and the audit's own reader), counted per day as
`duplicates_removed` in `quality.json`; `lines` still includes it. Lines
without a request id (before the change) are kept and flagged as above.

**8. The old site's images were "scanner probes".** `/wp-content/` is a
WordPress probe pattern, so a person following a link to the old site's
`/wp-content/uploads/...png` was filed as a scanner. `site.legacy_paths`
lists the old site's real prefixes; a path under one is never a probe (it is
whoever asked for it, people or bots, and the feed flags it `legacy_path`).
`wp-admin`, `wp-login`, plugins and the rest stay probes.

**9. Launch-day lines in the old format.** 1,513 lines before the log format
changed have no host and no country. They were counted and reported as
"could not be filtered"; now each day's `quality.json` says how many
(`old_format`) and the feed flags each such row. They age out with the logs.

**10. Next.js payloads are never page views - verified.** `?_rsc=` (and
`&_rsc=`) is a payload whether it is a prefetch or a navigation: never a
page view, in the package and in the audit. Tests pin it for paths in every
locale.

**11. Link previews filed as search engines.** facebookexternalhit,
Twitterbot and LinkedInBot sat in the search group; Slack, Teams, WhatsApp,
Discord and Telegram were anonymous bots. A preview is an app fetching a
page because someone pasted its link - neither indexing nor reading. They
are now **bots, by app** (`link preview: Slack`, ..., `iMessage` for the
Safari agent carrying both Facebook's and Twitter's tokens), and
`bots.json` lists them so marketing can see a link being shared. This
moves those requests out of the search figure from 2026-10-07.

**12. Crawler names were claims.** Anyone can send "Googlebot". Each named
assistant or search crawler is now checked against its owner's published
address list or by reverse-then-forward DNS (`bot_verify.py`); one proven
false moves to bots as "claims to be X". Lists are fetched once a day and
an unreachable or stale list never moves anything: the claim is kept as
"unverified". Claude Code's fetches (`claude-code/` in the agent) run on
the asker's own machine and are always "unverified". On the first real run
every Googlebot, GoogleOther, YandexBot, Applebot, ChatGPT-User,
OAI-SearchBot and meta-externalagent request verified. Page-speed testers
(Lighthouse, WebPageTest, GTmetrix) render fully and were people; they are
bots now.

Fake browsers - a browser agent from a cloud or hosting network, the same
agent from 10 or more addresses within 10 seconds, or the bare agent
`Mozilla/5.0` - are **flagged, not moved** (bots.json `fake_browsers`, the
feed's `flags`): VPN users exit from data centres and a link shared in a
busy chat fans out too. On the first real day 354 people requests (141
addresses) came from hosting networks - a number to watch, not to subtract.

## 13. Bots posing as browsers counted as readers (2026-10-11)

**What was reported.** 532 visitors on 2026-10-10 (one production site), and 25, 183,
65 and 338 on the four days before.

**What was true.** 10 that day, and 4, 26, 9 and 13. The owner asked "are
we getting honest visitors?", and the raw log said no: 717 browser-like
visitors (address and user agent, our own and named bots left out) fetched
a page, and 13 of them loaded a single script or stylesheet. The other 704
took the HTML and left. Their shape gave them away too: 99% desktop, 77%
macOS, 95% one page, median visit 0 seconds, 97% "direct". Top agents: Mac
Chrome, a Mac Firefox version (rv:151) that no person runs, Windows Chrome.
"Visitors" was about forty times too high, and so was everything built on
it: sources, countries, landing pages, journeys, first-visitor milestones.

**Why the code did it.** "Looks like a browser and nothing else matched" was
the whole test for a person (CLASSIFICATION.md rule 9, before this). A user
agent is a claim, and every scraper copies a browser's. The fake-browser
flags (trap 12) only flagged; the robots.txt rule (rule 8) only caught
crawlers that asked for robots.txt.

**How this package prevents it.** A browser-like visit counts as people only
with evidence that a browser drew the page (`rendering.py`): it fetched one
of the page's own scripts or styles (`site.asset_prefixes`, default
`/_next/static/`) or a `?_rsc=` payload from 5 seconds before to 30 seconds
after one of its pages; or the beacon (the page's own script) sent an event
from one of its pages; or the same address and agent rendered earlier that
day, or its 30-day keyed hash was a reader on an earlier day - a browser
with the assets in its cache asks for none. Images, `/og/` cards and
favicons do not count: link unfurlers fetch those. Every request of a visit
that never rendered moves to bots as "browser-like, never rendered the
page", so the groups still add up. `bots.json` counts them (`not_rendered`:
requests, page views, and the visits that would have been visitors), the
Data quality tab shows "browser-like requests moved to bots" per day, and
every place that says "Visitors" says how they are counted. History was
recounted from Oct 6 (`backfill --force`), and the page milestones were
rebuilt from the recounted days, so a scraper's "first human visitor" is
gone rather than kept as the earliest.

**What it cannot know.** A person whose browser blocks scripts and styles,
or a text-only browser, is left out with the scrapers. The beacon cannot see
them either, since it is a script. What it can show: on Oct 10 every one of
the 4 page openings it reported came from a visit the asset test had
already counted, so cached browsers are not being lost. A scraper that
fetches the assets as well (a headless browser) passes this test; that is
what the fake-browser flags and the robots.txt rule are still for.

**The check that catches it.** The independent audit recounts the rule by a
road of its own (`audit_rendered.py`: its own visit split, asset and page
tests, raw beacon spool and stored-reader query) and compares readers,
every reader breakdown and `not_rendered` with history.

**The test.** `tests/test_rendering.py`: a real browser visit, a page-only
scraper, a cached browser seen earlier that day and a reader from an
earlier day, a beacon-only visit (one opening vouches for one visit), and a
page whose stylesheet is logged the next second or a second before it.

## The pattern in all five

Every one of these was a number that answered a slightly different question
from the sentence printed above it. None needed a clever test. Four needed one
subtraction, done once, by something willing to refuse to send - which is
`verify.py`. The fifth and the scanner needed a person to read the log.

So: wire `--check` into the send path, and read the raw log sometimes.
