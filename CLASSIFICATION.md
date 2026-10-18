# Classification

Every request lands in exactly one of five groups. This document is the
reference for which, in what order the decision is made, and why that order.

Two separate questions are being answered, and keeping them apart is the point:

- **Who made the request?** The classifier decides, from the user agent, the
  referrer and the URL. That is this document.
- **What did they ask for?** `parse.Hit.is_page` decides whether the thing
  fetched was something a person could read. That is independent of who asked,
  and it is covered at the end.

## The five groups

| Group | `Group` value | Means |
| --- | --- | --- |
| Real people | `people` | A browser that rendered the page, and nothing above it matched. |
| Answer engines | `answer_engines` | An AI assistant's crawler or fetcher. |
| Search engines | `search_engines` | Classic indexing, and Google's ads quality checks. |
| Bots and scanners | `bots` | Everything else automated, including credential probes. |
| Our own traffic | `ours` | Your crawler, your tests. Not traffic at all. |

They partition the log: `sum(group.hits) == parsed`, checked by
`verify.check` before anything is reported.

### The three answer-engine tiers

`answer_engines` is split by *why* the engine came, because the three reasons
are not comparable quantities.

| Tier | Identified by | Means |
| --- | --- | --- |
| `training` | user agent | A crawl. Nobody is waiting on it. |
| `asked` | user agent | Someone put a question to an assistant seconds ago and it came to fetch you. A reader exists, right now. |
| `cited` | **referrer**, not user agent | A person saw you in an answer and clicked through. |

`cited` is the tier that becomes customers, and the only one not read from a
user agent. It is also **not counted in the `answer_engines` group**: a person
who followed a citation is a person, so they are counted in `people`, and the
citation is recorded as a property of that visit (`cited_visits`,
`cited_by`, `cited_pages`). Counting them in both places is double counting,
and it is how the old report's tiers over-summed by 56. See
`COUNTING-TRAPS.md`.

## The order of the rules

From `Classifier.__call__`, in exactly the order it runs. `probing` is computed
once from the URL before any of it and attached to every verdict, so a probe is
*flagged* wherever it lands without being *moved* there.

```
0.  probing = PROBE.search(path) or PROBE_QUERY.search(url)   # recorded, not yet decisive
      (not for a path under site.legacy_paths: the site's old URLs)

1.  ours.user_agents  matches the agent      -> OURS
2.  ours.referrers    matches the referrer,
      or ours.addresses holds the address    -> OURS
3.  AI_ASKED          matches the agent      -> ANSWER_ENGINE, tier asked
4.  AI_TRAINING       matches the agent      -> ANSWER_ENGINE, tier training
      (3 and 4: proven fake by bot_verify    -> BOTS, "claims to be <name>")
5.  LINK_PREVIEWS     matches the agent      -> BOTS, "link preview: <app>"
    SEARCH_ENGINE     matches the agent      -> SEARCH_ENGINE
      (proven fake                           -> BOTS, "claims to be <name>")
6.  probing                                  -> BOTS, probe=True
7.  OTHER_BOT matches, "(compatible; ...)"
      naming no browser engine, no agent at
      all, or an /.well-known/acme-challenge/
      path                                   -> BOTS
8.  BROWSER matches, and this visit (address + agent, no gap over 30
      minutes, on the site's hosts) fetched robots.txt, a sitemap, ads.txt
      or security.txt without rendering its pages        -> BOTS
9.  BROWSER matches, and this visit never rendered a page: no own script,
      style or ?_rsc= payload near one of its pages, no beacon event, and
      this address and agent did not render earlier that day or read on an
      earlier day                              -> BOTS ("browser-like, never
                                                   rendered the page")
10. BROWSER           matches the agent      -> PEOPLE
      and the referrer's host is an assistant's,
      or AI_UTM matches the URL              -> PEOPLE, tier cited
11. anything left                            -> BOTS
```

Rule 8 needs to know the whole visit before it files any of its hits, so
every analysis reads its window twice: once to find the crawler visits
(`classify.crawler_visits`), once to classify. A browser never asks for
those files by itself. On the audited day, 7 sessions with Chrome user
agents did, and made 111 of the 182 "people" page views.

It is kept narrow, because a wrong call turns a person's reading into bots:
it holds for that one visit only (a reader who opens /robots.txt by hand
hours later is a new visit), on the site's own hosts only (robots.txt on the
API host says nothing), and never for a visit that loaded the site's own
scripts, styles or payloads - referred by the site's own pages - at least
once per page it read. A browser renders; a crawler does not. That covers an
SEO extension fetching robots.txt and an office sharing one address and
browser. "At least once per page", not "at all": the audited day's largest
crawler session read 99 pages and loaded 2 assets.

Rule 9 is the same two-pass idea made general (`rendering.py`, added
2026-10-11 - COUNTING-TRAPS.md trap 13). A browser that opens a page goes
on to fetch the page's own scripts and styles; a scraper sending a browser's
name takes the HTML and leaves. So a browser-like visit (address and agent,
no gap over 30 minutes, on the site's hosts) is people only with evidence
that a browser drew the page, any one of:

- **assets**: it fetched something under `site.asset_prefixes` (default
  `/_next/static/`) or a `?_rsc=` payload, from 5 seconds before to
  `site.render_seconds` (30) after one of its page requests. Before, too,
  because a streamed page is logged when it ends, after its styles were
  asked for. Images, `/og/` cards and favicons do not count: link
  unfurlers fetch those.
- **beacon**: an event from the page's own script (the beacon spool) was
  sent from one of its pages, opened within the same window. The spool
  holds no address, so the match is by path and time: one page opening
  vouches for one visit at most, the nearest in time, and for none when a
  visit that rendered already explains it.
- **earlier**: the same address and agent rendered earlier the same day. A
  returning browser has the assets cached and asks for none.
- **returning**: its 30-day keyed hash (visitors.py) was a counted reader
  on an earlier day, for the same reason.

A visit counts whole or not at all, and every request of one that never
rendered is filed under bots, so the groups still partition the log. On the
audited day (2026-10-10) this moved 704 of 717 browser-like page visitors
to bots, and readers went from 532 to 10. `site.require_rendering: false`
turns it off, for a site whose assets come from a host this log never sees.

**Not done: a burst rule.** The same day had one page load spread over 51
addresses in 6 seconds - a distributed crawler with one user agent. A rule
for it ("N addresses, one agent, one path, within S seconds") would also
catch a link shared in a busy chat, and there is no fixture of real traffic
that tells the two apart, so it is not built. Most of that burst read no
page, so the readers headline (below) already leaves it out.

### Why this order

**`ours` is first** because your own crawler and your own end-to-end tests
would otherwise be read as a bot, or - worse - as a person who followed a
citation, if your tooling browses with a referrer you set. That would inflate
the single number you most want to be true.

**The named engines come before everything except `ours`** because a specific,
self-declared identity is the strongest signal in a log line. `GPTBot` is
`GPTBot`.

**`asked` is tested before `training`** because some agents match both lists.
When a request could be either, "a person is waiting on this" is the fact worth
reporting.

**`probe` sits above `people`.** A scanner that sends a Chrome user agent is
not a reader. This is not hypothetical: `/_ignition/execute-solution`, a
Laravel remote-code-execution probe, was being counted as a *person* because it
sends a Chrome user agent and no pattern matched the path. Adding the framework
debug routes to `PROBE` moved 93 requests out of "people" on the reference log,
84 of them `/_ignition` alone - and 56 of those were POSTs, so they were never
page views, only phantom visitors.

**`probe` sits below the named engines**, and this matters just as much. An
engine that happens to request a silly path is still that engine. File it under
scanners instead and it leaves the `answer_engines` group total while the tier
counters still see it - which is precisely how the old report's answer-engine
tiers ended up 82 higher than the group they were supposed to divide. The
verdict keeps both facts: group `ANSWER_ENGINE`, `probe=True`.

**`BROWSER` is last, and only as a fallback.** "Looks like a browser" is the
weakest claim in the file, because every scanner in the world copies a Chrome
string. Reaching rules 8 to 10 means nothing more specific matched.

**Rule 11 sends the unknown to bots, not to people.** An agent that is not empty,
not a known bot and not browser-shaped is a library or a script. Defaulting the
unknown into "people" is how a number drifts upward with nobody noticing.

## Inferred, not classified: likely sent by an AI assistant

This is not a twelfth rule. It moves no request and no visit. Every visit
keeps its group and its source. It is an estimate laid beside the counts,
and every place that shows it says "likely" and how it was made.

Rule 10 finds a person who followed an assistant's link only by the
referrer or an AI `utm_source` tag. Both are often lost: the app strips the
referrer, or the link carries no tag. That person lands in "Direct or
unknown". But when the person asked, the assistant's user fetcher
(`AI_ASKED`) fetched the page from the server at that moment. So:

```
A visit is "likely referred by" an assistant when
  its source is "Direct or unknown",
  its landing address has no utm_ tag and no ad click id (CLICK_ID_PARAMS),
  and that assistant's user fetcher fetched the page it landed on
  in the same minute as the visit's first request,
  or up to attribution.ai_window_minutes (default 15) minutes before.
```

- **Whose fetcher.** `AI_FETCHER_OWNERS` in `classify.py` names the
  assistant behind each user fetcher: `ChatGPT-User` is ChatGPT
  (`chatgpt.com`), `Perplexity-User` Perplexity, `Claude-User` Claude,
  `Gemini-User` Gemini, `MistralAI-User` Mistral, `BingPreview` Copilot
  (as `AI_ASKED` files it), `meta-externalfetcher` Meta AI. Training and
  index crawlers (`AI_TRAINING`) never count: nobody is waiting on them.
  A fetcher proven fake (spoofed) is a bot, so it does not count either.
- **The same page.** Both paths without the query string, cut to 70
  characters, with a trailing `/` ignored (`/pricing/` is `/pricing`).
- **The time.** Compared to the minute, in UTC.
- **Two or more assistants** fetched the page in the window: the visit
  counts once, under "(more than one)". Never once per assistant.
- **Settings.** `attribution.ai_likely` (default true) turns it on or off;
  `attribution.ai_window_minutes` sets the window. Each day keeps the
  window it was counted with. Off: the figure is "not recorded", never 0.

Why it is only "likely". A fetch can be for a person who read the answer
and never clicked. A direct visit to the same page a minute later can be
someone else. A visit in the first minutes of a day cannot see the
fetches of the day before. And an assistant that answers from its own
index fetches nothing. So the figure is an estimate, a floor in the same
way citations are, and it is never added to the "AI assistant" source,
to people, or to any other real count.

It is counted twice like every figure: `ai_likely.py` in the tally pass,
and `audit_ai_likely.py` from the raw lines with its own code, sharing
only the name lists here. A day the two disagree on is withheld. The same
rule, at the same minute precision, marks leads and conversions whose
touch was direct (DATA-CONTRACT.md: `ai_likely`, `ai_fetches`,
leads.json `likely_ai`, conversions.json `likely_ai`).

## The patterns

All are case-insensitive. The names are the constants in `classify.py`.

### `AI_TRAINING` - matched against the user agent

Assistants fetching to train a model or build their own index. Nobody is
waiting on the response.

`GPTBot`, `ClaudeBot`, `Claude-SearchBot`, `CCBot`, `anthropic-ai`,
`OAI-SearchBot`, `PerplexityBot`, `meta-externalagent`, `FacebookBot`, `Bytespider`,
`Amazonbot`, `Applebot-Extended`, `cohere-ai`, `Diffbot`, `omgili`, `AI2Bot`,
`Timpibot`, `ImagesiftBot`, `YouBot`, `PanguBot`, `Kangaroo Bot`,
`DuckAssistBot`.

`OAI-SearchBot` and `PerplexityBot` build the assistants' own search indexes
ahead of any question, exactly as `Googlebot` does, so nobody is waiting on
them: they are here, not under "asked". `Google-Extended` is not in any list:
it is a robots.txt token that controls whether Google may train on what
Googlebot fetched, and no request ever carries it as a user agent.

One deliberate split lives here. `Applebot-Extended` trains; plain `Applebot` indexes, and `SEARCH_ENGINE` uses
a negative lookahead (`Applebot(?!-Extended)`) so the two cannot collide.

### `AI_ASKED` - matched against the user agent

Fetching *now*, because a person asked the assistant something.

`ChatGPT-User`, `Claude-User`, `Perplexity-User`, `meta-externalfetcher`,
`Gemini-User`, `BingPreview`, `MistralAI-User`.

### `AI_REFERRER_HOSTS` - matched against the referrer's host

A person who followed a citation. Identified by where they came *from*, because
their user agent is an ordinary browser's and says nothing.

The referrer's **host** must be one of these or a subdomain of one -
`chatgpt.com`, `chat.openai.com`, `openai.com`, `perplexity.ai`, `claude.ai`,
`gemini.google.com`, `copilot.microsoft.com`, `you.com`, `phind.com`,
`poe.com`, `mistral.ai` - or `bing.com` with a path under `/chat`. A substring
match counted `thank-you.com` as `you.com`; `notperplexity.ai` and a
`?ref=chatgpt.com` query are not citations either.

An assistant's Android app sends `android-app://<package id>/`, so its package
id is the host. These count as the assistant: `com.openai.chatgpt`
(ChatGPT), `ai.perplexity.app.android` (Perplexity), `com.anthropic.claude`
(Claude), `com.google.android.apps.bard` (Gemini), `com.microsoft.copilot`
(Copilot). Without them an app citation was "Other website" (or, for Gemini,
"Search engine").

Every signal for one assistant gives it one name - its main domain:
`chat.openai.com`, `openai.com` and `utm_source=chatgpt` are all
`chatgpt.com`; `bing.com/chat` and `utm_source=copilot` are
`copilot.microsoft.com`; each app's package id is its assistant's domain
(`classify.assistant_name`). History written with an
older name of an assistant is read back under the canonical one.

### `AI_UTM` - matched against the URL

Some assistants tag the outbound link instead of sending a referrer:
`utm_source=` followed by `chatgpt`, `openai`, `perplexity`, `claude`,
`gemini`, `copilot` or `mistral`. Checked as a fallback for the same question,
so a tagged link still counts when the referrer was stripped. It applies
whatever the referrer: a tagged link that arrives with a search engine's or
this site's referrer is a citation too, in the count and in the audit.

### `SEARCH_ENGINE` - matched against the user agent

Classic indexing. Wanted traffic, which is why it is never filed under "bots".

`Googlebot`, `Google-InspectionTool`, `GoogleOther`, `APIs-Google`,
`AdsBot-Google`, `Google-Adwords-Instant`, `bingbot`, `Slurp`, `DuckDuckBot`,
`Baiduspider`, `YandexBot`, `Sogou`, `Exabot`, `Applebot(?!-Extended)`.

A name that claims one of these, or an assistant's crawler, is checked
against its owner's published address ranges or by reverse and forward DNS
(`bot_verify.py`). One proven fake is filed under bots as "claims to be
<name>"; one that cannot be checked stays, marked unverified.

### `LINK_PREVIEWS` - matched against the user agent, before search

An app fetching a page because someone pasted its link in a chat or a post:
`Slack`, `iMessage`, `WhatsApp`, `LinkedIn`, `Microsoft Teams`, `Discord`,
`Telegram`, `X (Twitter)`, `Facebook`, `Pinterest`, `Reddit`, `Embedly`,
`Iframely`, `Snapchat`, `VK`, `Bluesky`, `Mastodon`. Filed under bots as
"link preview: <app>", on their own line, because a preview means a person
shared the link. `facebookexternalhit`, `Twitterbot` and `LinkedInBot` sat
in the search group until 2026-10-07: they do not index.

`AdsBot-Google` (and its mobile form) and `Google-Adwords-Instant` are Google's
ad systems checking the landing pages of ads. They stay in this group -
Google's, and wanted - but every report shows them on their own line, "ads
quality checks", and the search-engine fetches figure leaves them out: they
are not indexing. On the audited day they were 54 of 142 search requests.

### `OTHER_BOT` - matched against the user agent

Automated, but not an engine. These families:

- generic self-declarations: `bot` as a word with no letter before it (so
  the phone maker CUBOT is not a bot), `bot/<version>` ("FooBot/2.1"), the
  `+https://` info link crawlers put in their agent and browsers never do,
  `(compatible; ...)` with no browser engine named anywhere in the agent
  (Internet Explorer also says "compatible;" but names Trident),
  `crawler`, `spider`, `scraper`
- HTTP libraries and clients: `curl`, `wget`, `python-requests`, `httpx`,
  `aiohttp`, `Go-http`, `java/`, `okhttp`, `axios`, `node-fetch`, `libwww`,
  `Scrapy`, `HeadlessChrome`, `PhantomJS`
- SEO and analytics suites: `AhrefsBot`, `SemrushBot`, `MJ12bot`, `DotBot`,
  `BLEXBot`, `DataForSeoBot`, `PetalBot`
- monitors and link unfurlers: `UptimeRobot`, `Pingdom`, `StatusCake`,
  `NewRelic`, `Site24x7`, `monitoring`, `Nagios`, `WhatsApp`, `TelegramBot`,
  `Discordbot`, `Slackbot`, `vkShare`, `Embedly`, `SkypeUriPreview` (most
  unfurlers are caught as link previews first), and the Let's Encrypt
  validator
- page-speed testers, which render pages fully: `Chrome-Lighthouse`,
  `PTST/`, `GTmetrix`, `Google-PageRenderer`
- found in a real log filed as people: `ctwatch`, `jSystem3-metadata-indexer`,
  and Googlebot's smartphone template with "Googlebot" taken out
  (`Nexus 5X Build/MMB29P` - Android 6 with this year's Chrome is a tool or a
  spoof, never a phone; the real crawler keeps the Googlebot token and is
  search)

`bot\b` is broad on purpose, and it is only reached after every named engine
and search crawler has had its turn - otherwise `Googlebot` would land here.
`HeadlessChrome` is in this list because a headless browser is automation, even
though it is a browser.

An empty user agent is treated the same way. Browsers always send one; a
request with none is a script or a scanner.

### `PROBE` - matched against the path; `PROBE_QUERY` - against the URL

Paths no real site serves. A request for one is somebody trying credentials,
whatever its user agent claims, so it is counted as a probe wherever it lands
and never believed about anything else.

Every pattern is anchored to the **shape** of what is being hunted - a file
name, an extension, a whole path segment - never a bare word. The first
version matched `backup` anywhere, and a real site's page with `backup` in its
name (think `/guides/backup-and-restore-your-schedules/`, and its `/ca/` copy)
was filed as a scanner along with every person who read it.
`tests/fixtures/site_paths.txt` is a made-up sitemap of the same shape (475
pages, many named with the words scanners hunt for), and a test fails if any
of them matches. Roughly:

- dotfiles and version control as a segment: `/.env`, `/.git`, `/.svn`,
  `/.hg`, `/.aws`, `/.ssh`, `/.vscode`, `/.idea`, `/.npmrc`, `/.htpasswd`,
  `/.DS_Store`, ...
- server-side scripts by extension: `.php`, `.asp(x)`, `.jsp`, `.cgi`, ...
- WordPress as a segment: `/wp-admin`, `/wp-login`, `/wp-content`, `/xmlrpc`
- dumps and backups shaped like files: `/backup.zip`, `/db.sql`,
  `/dump.sql.gz`, any `.sql`, `.bak`, `.sqlite`, and a bare `/backup/`
- keys and credentials shaped like files: `id_rsa`, `.pem`, `.key`,
  `.tfstate`, `/credentials.json`, `/secrets.yml`, `/config.json`,
  `/service-account*.json`, `/docker-compose*.yml`, `/env.js`
- admin panels and consoles as a segment: `/admin`, `/phpmyadmin`,
  `/cgi-bin`, `/jenkins`, `/actuator`, `/telescope`, ...
- framework debug endpoints that are remote-code-execution routes:
  `/_ignition`, `/_debugbar`, `/_profiler`, `/vendor/phpunit`, `eval-stdin`,
  `invokefunction`, `/containers/json`, `/HNAP1`, `/owa`, `/sdk`, ...

`/administration-guide/` is not `/admin`; `/blog/wp-alternatives` is not
WordPress; `/sitemap.xml.gz` is not a backup.

`PROBE_QUERY` catches the few attacks that live in the query string instead:
`../`, `/etc/passwd`, `${jndi:`, `UNION SELECT`, `XDEBUG_SESSION`.

That last family is the one worth remembering: it exists because somebody read
a real log and found those requests sitting in the "people" column.

### `BROWSER` - matched against the user agent

`Mozilla/`, `Opera/`, `Safari/`, `Chrome/`, `Firefox/`. The weakest signal in
the file, checked last.

### `ours` - from your config

Matched on user agent, on referrer, or on the visitor address (`ours.addresses`, single addresses or CIDR ranges) — your own browsing looks exactly like a reader and is not traffic.

Any entry may carry a label - `{ip: 192.0.2.10, label: "Office Mac"}`,
`{agent: skald-heartbeat, label: heartbeat}` - and a plain string still works.
The verdict carries the label of the first rule that matched, in the order
above, and the dashboard lists our own traffic by label. Addresses added on
the dashboard (`ours.file`) are merged in and apply only from the moment
they were added: a stored day is never re-judged. Privacy: raw addresses
stay in the server log and on the private page; keyed hashes 30 days;
totals for good (README). Since 2.4.0 a site may also keep each reader's
visit with its address (`privacy.keep_ips`, docs/DATA-CONTRACT-PEOPLE.md).
An unlabelled
address is "Listed address N": an address is never used as a label.

Certificate validation (`/.well-known/acme-challenge/…`, `MACHINE_PATH`) is filed under bots whatever the agent: the validators send a Mozilla user agent and were being counted as people.

Skald's own fetchers are always our own traffic, whatever the lists say
(`classify.OWN_AGENTS`): the hourly robots.txt check, user agent
`site-version-check/1`, is "Skald (robots.txt check)". Before 2.8.0 it
landed in bots on every site.

`ours.user_agents` is matched against the user agent; `ours.referrers` against
the referrer. Both are **literal substrings**, not regular expressions: the
entries are passed through `re.escape`, so `MyCompany-e2e` matches and
`MyCompany.*` matches nothing. Matching is case-insensitive. An empty list
matches nothing, rather than everything.

## What decides a page view

`parse.Hit.is_page` answers "could a person have read this", and it is separate
from who asked. It is true only for a 2xx or 304 response to a GET or HEAD
that is none of:

- **`RSC_PAYLOAD`** - `?_rsc=`, `?__flight__=`, `?_data=`. A React or Next
  client fetching the page you just clicked. One navigation produces one of
  these, so counting them doubles every click; counting them *instead* of pages
  is what produced "56 people".
- **`ASSET`** - by extension (`css`, `js`, `mjs`, `map`, images, fonts, `txt`,
  `xml`, `json`, `webmanifest`, `xsl`, feeds, `pdf` and office documents,
  archives, audio and video, `wasm`) or by prefix (`/_next/`, `/static/`,
  `/assets/`, `/_nuxt/`, `/build/`). Note that `robots.txt` and `sitemap.xml`
  are assets by this rule, which is right: nobody reads them.
- **`BEACON`** - `/api/events`, `/api/analytics`, `/__analytics`, `/collect`,
  `/beacon`, `/ping`. A page calls these while you read it. They are evidence
  of a visit, never a visit of their own.

Redirects are excluded by the 2xx rule. A 301 is not a page: the browser lands
somewhere else and that page is logged separately as its own 200, so counting
the redirect counts one read twice. On the reference log this was 3,993 of
15,727 claimed views - 25% of them - almost all trailing-slash 301s and 308s.

A 304 is not a redirect (since 2.8.0). It tells the browser its cached copy
is current, and the browser shows that copy: a returning reader read the
page. So it is a page view, and the first page of a visit carries the
visit's source. Before, a reader who came back from a search to a page they
had cached lost that source to their next page ("This site"), or was no
reader at all.

Probe paths are *not* excluded here. A scanner asking for `/.env` and getting a
200 counts as a page view inside the `bots` card, which is where the scanner
already is. If that bothers you, the honest fix is to stop serving a 200.

## The source type of a visit

`dimensions.source_type` (and, on the audit's own road,
`audit_labels.source_of`) gives each visit one of: AI assistant, Search
engine, Social media, Email, Other website, This site, Tagged link, Direct
or unknown. A referrer decides first. With none, the tags do:

- **Search engines** are named by their real domains (`google.com`,
  `google.de`, `google.co.uk`, `google.com.au`, `bing.com`, ...), never by
  the word "google". An Android app's referrer is
  `android-app://<package id>/`: only Google's search app
  (`com.google.android.googlequicksearchbox`) is a search engine, and Gmail
  (`com.google.android.gm`) is email. Since 2.8.0 Google's other apps are not
  "Search engine": YouTube, WhatsApp and Telegram apps are Social media, the
  rest Other website. An assistant's app is the assistant (above).
- **utm_ tags.** `utm_source` decides first, `utm_medium` only when the
  source names no type: the source names the place, the medium only says
  how. `utm_source=linkedin&utm_medium=cpc` is Social media, not Search
  engine (before 2.8.0 both words were pooled and search won). Tags that
  name no type are a Tagged link.
- **Ad click ids** with no utm_ tag: `gclid`, `gbraid`, `wbraid` (Google
  Ads, the last two from iOS) and `msclkid` are Search engine; `fbclid`,
  `li_fat_id`, `ttclid` (TikTok) and `twclid` (X) are Social media. The
  campaign is the network's name, never the id's value
  (`google / cpc / (gbraid)`).

## Reading a log line

`parse.py` reads each line into the fields the rules above use. Three
details decide what a line gives:

- **Combined logs.** Many servers add fields after the stock combined
  format. Two are read when present: a response time right after the user
  agent (`$request_time`), and a quoted host name as the very last field
  (`"$host"`). The host is taken only when it looks like one: letters in it,
  dots between labels, an optional `:port` (dropped). A quoted address list
  (`"$http_x_forwarded_for"`) or `"-"` is not a host, and the host stays
  empty, as before.
- **Caddy JSON.** The address is `client_ip` (the client once Caddy trusts
  its proxies; `remote_ip` is then the proxy), else `remote_ip` for older
  logs. `host:port` becomes `host`. A record with no address, no URI or no
  three-digit status is not a request and is not counted; both roads (main
  and audit) skip it the same way.
- **Country.** The line's own (`cc=`, Cloudflare's `CF-IPCountry`) always
  wins. A line with none gets its address's country from the GeoIP file
  `logs.country_db`, when one is set: a lookup in the same DB-IP file
  nginx's GeoIP module reads, not a guess. With neither, it is Unknown.

## What this cannot know

State these next to the numbers, not in a footnote.

**A user agent is self-reported and forgeable.** Every string the classifier
reads is a claim by the client. `people` is therefore an upper bound on humans,
never a count of them. A scraper that sends a plausible Chrome string and only
requests pages is caught by rule 9; one that drives a real browser and loads
the assets as well (a headless browser not saying so) is indistinguishable
from a reader.

**A person who blocks scripts and styles is not counted.** Rule 9 cannot tell
them from a scraper, and the beacon cannot see them either. On 2026-10-10
every page opening the beacon reported (4) came from a visit the asset test
had already counted.

**Google AI Overview clicks are not measurable.** A person who clicks a link
inside an AI Overview arrives with a bare `google.com` referrer - byte for byte
the same as an ordinary search result click. There is no parameter, no header
and no marker. The crawl side is not separable either: Google trains on what
Googlebot fetches, and `Google-Extended` is a robots.txt switch, not a user
agent. So a report must not claim any number for Overview clicks, nor for
"Google's AI crawl". The HTML card says "not measurable" in that row on
purpose.

**Referrers are frequently stripped**, by privacy settings, by
`Referrer-Policy`, by apps that open links in their own webview, and by HTTPS
to HTTP transitions. Every citation count is therefore a floor, not a figure.
`AI_UTM` recovers some of it and not all.
Skald estimates part of the rest, labelled as an estimate: a direct visit
to a page an assistant's user fetcher had just fetched is "likely" from
that assistant ("Inferred, not classified" above). It is never added to
the citation count.

**Sessions are approximate.** A visit is one address plus one user agent inside
a 30-minute gap; for people, a page view arriving from a new outside source (an
assistant, another website, a search engine, social, email, a tagged link)
that differs from the visit's first page's source, referrer and campaign starts
a new visit (SOP.md, "What a visit is"). A same-site or no-referrer page never
does. A household or an office behind one address is one visit; one
person moving from wifi to mobile data is two.

**New engines appear constantly.** An assistant that launched last month is in
nobody's pattern list, so it falls to `bots` (if its agent says `bot`) or to
`people`. When a report shows an unfamiliar name high in the bots list, that is
the signal to add it here.

**The probe list is only as good as the last log somebody read.** Nothing in
this package discovers a new scanner family on its own. Read the raw log
occasionally, sorted by path, and look for what is sitting in the wrong column.
