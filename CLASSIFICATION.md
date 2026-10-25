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
6b. this address and agent asked the site's hosts for a secret or config
      file (SECRET_PROBE) or sent an attack in a URL (PROBE_QUERY) in the
      window (the day), before this request or after it
                                               -> BOTS ("scanner (asked for
                                                   secret or config files)")
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
9b. BROWSER matches, and this visit read site.too_fast_pages (6) page
      views or more, all within site.too_fast_seconds (2) of its first
                                               -> BOTS ("too fast to be a
                                                   person")
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

Rule 6b (2.20.1, COUNTING-TRAPS.md trap 17) is the same two-pass idea for
scanners: **one probe marks the whole visitor.** A scanner that sends a
browser's name asks for a page or two between its probes, and before the
rule those pages were people: a visit, a landing, a source, a live visitor,
a city dot. So the first pass (`classify.Scanners`) keeps every address and
user agent that asked the site's hosts for a secret or config file in the
window (`SECRET_PROBE` on the path: the dotfile, dump and backup, key and
credential, infrastructure and package families of `PROBE`) or sent an
attack in a URL (`PROBE_QUERY`), not under `site.legacy_paths`, and the
classifier files every other request of that pair, before the probe or
after it, under bots as `"scanner (asked for secret or config files)"`. The
probes themselves stay rule 6 (`probe`, counted in `probes`).

The other `PROBE` families - WordPress paths, server-side scripts, admin
panels and consoles, an app's settings file (`/config.json`,
`/appsettings.json`, `/env.js`) - still make their own request a probe, but
mark no one: a real reader asks for them too (every reader of a WordPress
site loads `/wp-content/` and `/wp-json/`; the owner opens their own
`/admin`; an app loads its settings as it starts). Marking on them would
have filed every reader of a WordPress site as a scanner.

It is per address **and** agent: someone else behind
the same address, with another browser, stays a person. It is per window:
the daily run's window is the site's day, so a probe at 23:50 moves a page
read at 10:00; the live run reads the day so far, so a visitor shown at one
run disappears at the next run after its probe. The rules above it come
first, as for rule 6: our own traffic, a named crawler and a link preview
keep their group whatever path they asked for. The audit finds the same
pairs with its own code (`audit.Judge._scanners`), sharing only the name
lists `SECRET_PROBE` and `PROBE_QUERY`.

Rule 9 is the same two-pass idea made general (`rendering.py`, added
2026-10-11 - COUNTING-TRAPS.md trap 13). A browser that opens a page goes
on to fetch the page's own scripts and styles; a scraper sending a browser's
name takes the HTML and leaves. So a browser-like visit (address and agent,
no gap over 30 minutes, on the site's hosts) is people only with evidence
that a browser drew the page, any one of:

- **assets**: it fetched something under `site.asset_prefixes` (default
  `/_next/static/`; per site also in Settings > Sites > Page assets,
  docs/SETTINGS.md) or a `?_rsc=` payload (a prefetch or a navigation),
  from 5 seconds before to
  `site.render_seconds` (30) after one of its page requests. Before, too,
  because a streamed page is logged when it ends, after its styles were
  asked for. Images, `/og/` cards and favicons do not count: link
  unfurlers fetch those.
  A Next.js navigation (above) is a page request and a payload at once, so
  a visit whose only pages are navigations (a tab left open, a page restored
  from the cache) drew: the page's running script asked for it.
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

Rule 9b (`too_fast.py`, added 2026-10-18) catches the scraper that passes
rule 9. On 14 Oct a visit counted as a person read 17 pages, every one at
second 0 of the visit: it drives a real browser, or fetched one asset, so it
"rendered". Nobody reads that fast. A click is a choice - find the link, move
the hand, wait for the page - and even a hurried reader clicking through a
menu spends about a second per page: a fast clicker reads 3 pages in 2
seconds, and stays a person (tests/test_too_fast.py). So a browser-like visit (the same visit as rule 9) with
at least `site.too_fast_pages` (6) page views, all of them within
`site.too_fast_seconds` (2) of its first, is a bot. The log stamps whole
seconds, so that is 6 pages in under 3 real seconds - two a second, with
nothing slower anywhere in the visit. "All of the visit's pages", not "any 6
in a row", on purpose: a person who restores six tabs and then reads on is
left alone. A page view is a 2xx or 304 document (rule "What decides a page
view"), so redirects never make a reader look faster. Like rule 9 it is
whole-visit, every request of the visit moves to bots, and the groups still
partition the log; bots.json's `too_fast` says how many (`requests`,
`pages`, `readers`). A visit that never rendered is rule 9's first.
`site.too_fast_pages: 0` turns it off. The audit recounts it on its own road
(`audit_too_fast.py`). Prefetch and prerender (Chrome speculation rules
fetch whole pages a person never opens) would look the same; they send
`Sec-Purpose: prefetch`, which the log format does not carry yet
(docs/EDGE-CASES.md B2), so a site that prerenders many pages at once should
raise `site.too_fast_pages`.

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

**What the AI read before it sent the visitor** (`ai_read.py`, kind
`ai_read`). The same fetches, read the other way. For each AI visit, cited
(rule 10, from an assistant that has a user fetcher in `AI_FETCHER_OWNERS`)
or likely (above), the visit keeps the paths that same assistant's user
fetcher fetched in the same window before its first request: at most 10,
nearest first, labelled "fetched by <assistant> in the N minutes before".
Only `AI_ASKED` fetchers; never a training crawler. Context, never a count
of people. The day figure is, per assistant, the cited visits, of which it
fetched pages first, of which the landing page was one of them ("fetch ->
visit to the same page"); likely visits are kept apart, since by their rule
they always land on a fetched page. A citation from an assistant with no
known user fetcher (You.com, Phind, Poe) is not recorded, never 0.
Recounted in `audit_ai_likely.py`, with its own reading of the citation.

## Inferred, not classified: Direct, likely a checkout return, an in-app browser or a shared link

Not a rule either. It moves no request and no visit: the Direct row keeps
every visit below. It is an estimate laid under that row, shown as
"Direct, likely <reason>" with an (i), and never as fact.

Many Direct visits ("Direct or unknown": no referrer, no `utm_source` or
`utm_medium`, no ad click id) say a little more in their own request or in
the log just before them. Each Direct visit gets **at most one** reason,
tested in this order; the first that matches wins, and anything else stays
plain Direct. The name lists are in `skald/direct_names.py`.

```
1. checkout   "Direct, likely checkout or payment return"
   the first page's address carries a payment provider's return parameter,
     its value starting with the provider's prefix:
       Stripe        session_id=cs_...  payment_intent=pi_...  setup_intent=seti_...
       PayPal        PayerID=<any>      ba_token=BA-...
       Razorpay      razorpay_payment_id=pay_...
       Checkout.com  cko-session-id=sid_...
       Adyen         redirectResult=<any>
   or its path is a checkout's end:
       a segment such as order-received, order-confirmation, payment-success,
       checkout-complete (CHECKOUT_PAGES), or
       a done word (success, thank-you, thanks, complete, confirmation,
       return, done, receipt) after a checkout section earlier in the path
       (checkout, order, payment, purchase, billing, pay, cart, subscribe)
   detail: the provider, or "(return page)" for a path

2. in_app     "Direct, likely in-app browser"
   the visit's browser label is an app's own browser: Facebook app,
   Instagram app, LinkedIn app, Gmail app, Google app, X (Twitter) app,
   TikTok app, Snapchat app, Pinterest app, WeChat, Line app, or an
   unnamed web view, "In-app browser (iOS)" / "(Android)"
   detail: the browser label

3. shared     "Direct, likely shared link"
   the first page's address carries a share marker:
       igshid= or igsh= (Instagram), mibextid= (Facebook), or
       a ref=, source=, src=, via=, from= or share= value naming a share
       or a messaging app (ref=whatsapp, source=share, via=copy-link,
       from=sms; SHARE_WORDS)
   or an app fetched a link preview (LINK_PREVIEWS: WhatsApp, Slack,
   iMessage, Telegram, Discord, Teams, ...) of the page the visit landed
   on, in the same minute as the visit's first request or up to
   attribution.share_window_minutes (default 30) minutes before
   detail: the app, "(share tag)" for a marker that names none, or
   "(more than one)" when two or more apps previewed the page
```

- **What is left out on purpose.** A bare `/success` or `/thank-you` (a
  form's thank-you page looks the same as a shop's); PayPal's bare
  `token=` (many sites use one); `si=` (YouTube and Spotify put it on their
  own links, never on a link to another site); `ref=` values that name a
  site, such as `ref=producthunt` (a source, not a share); `fbclid`, `gclid`
  and the other click ids (they are not Direct at all: rule "The source
  type of a visit"). A visit with any referrer or a `utm_source` is not
  Direct and is never split.
- **Why this order.** A provider's return parameter is the narrowest sign,
  so it goes first: a PayPal return opened in Instagram's browser is a
  checkout return. The browser label is read from the visit's own request,
  so it comes before the shared link, which is read from the link or from
  the log around it: a `ref=whatsapp` link opened in Facebook's browser is
  an in-app visit. Inside shared, a marker on the link comes before a
  preview.
- **The preview is matched by page and time, not by visitor.** It comes
  from the app's servers (Slack, Discord, Telegram) or from the sender's
  phone (WhatsApp, iMessage), never from the person who clicks. The pages
  are compared as the likely-AI figure compares them (no query, 70
  characters, a trailing `/` ignored), to the minute in UTC. A page that
  is previewed often (the home page on a busy site) makes more of its
  Direct visits "likely shared": that is why it is only likely.
- **The two estimates are apart.** A visit can be "likely from an AI
  assistant" and "Direct, likely in-app browser" at once; neither is added
  to the other, nor to any count.
- **Settings.** `attribution.direct_likely` (default true) turns it on or
  off; `attribution.share_window_minutes` sets the preview window. Each day
  keeps the window it was counted with. Off: the figure is "not recorded",
  never 0.
- **Nothing personal is kept.** Only the reason, the detail (a provider,
  a browser label or an app) and counts. A landing address's query values
  (a Stripe session, a PayPal payer) are read in memory and never stored.

It is counted twice like every figure: `direct_likely.py` in the tally
pass, and `audit_direct_likely.py` from the raw lines with its own code
(its own query split, its own path reading, the audit's own browser and
source labels), sharing only `direct_names.py`. A day the two disagree on
is withheld (DATA-CONTRACT.md: the day kind `direct_likely`, campaigns.json
`direct_likely`, visits.json `likely_direct`).

## The patterns

The patterns each rule matches against (the name lists in `classify.py`) are in
[CLASSIFICATION-PATTERNS.md](CLASSIFICATION-PATTERNS.md), split out on 2026-10-24 to keep
this file under the 1000-line limit. Its sections:

- [`AI_TRAINING` - matched against the user agent](CLASSIFICATION-PATTERNS.md#ai_training---matched-against-the-user-agent)
- [`AI_ASKED` - matched against the user agent](CLASSIFICATION-PATTERNS.md#ai_asked---matched-against-the-user-agent)
- [`AI_REFERRER_HOSTS` - matched against the referrer's host](CLASSIFICATION-PATTERNS.md#ai_referrer_hosts---matched-against-the-referrers-host)
- [`AI_UTM` - matched against the URL](CLASSIFICATION-PATTERNS.md#ai_utm---matched-against-the-url)
- [`SEARCH_ENGINE` - matched against the user agent](CLASSIFICATION-PATTERNS.md#search_engine---matched-against-the-user-agent)
- [`LINK_PREVIEWS` - matched against the user agent, before search](CLASSIFICATION-PATTERNS.md#link_previews---matched-against-the-user-agent-before-search)
- [`OTHER_BOT` - matched against the user agent](CLASSIFICATION-PATTERNS.md#other_bot---matched-against-the-user-agent)
- [Checking the name lists (dev time only)](CLASSIFICATION-PATTERNS.md#checking-the-name-lists-dev-time-only)
- [Bing Copilot by `form=MA...`: not adopted](CLASSIFICATION-PATTERNS.md#bing-copilot-by-formma-not-adopted)
- [`PROBE` - matched against the path; `PROBE_QUERY` - against the URL](CLASSIFICATION-PATTERNS.md#probe---matched-against-the-path-probe_query---against-the-url)
- [`BROWSER` - matched against the user agent](CLASSIFICATION-PATTERNS.md#browser---matched-against-the-user-agent)
- [`ours` - from your config](CLASSIFICATION-PATTERNS.md#ours---from-your-config)

## What decides a page view

`parse.Hit.is_page` answers "could a person have read this", and it is separate
from who asked. It is true only for a 2xx or 304 response to a GET or HEAD
that is none of:

- **`RSC_PAYLOAD`** - `?_rsc=`, `?__flight__=`, `?_data=`. A React or Next
  client fetching the page you just clicked, or prefetching a link in view.
  Counting them *instead* of pages is what produced "56 people". One
  exception, only when the line can tell a click from a prefetch: a Next.js
  navigation (`Hit.soft_navigation`) - a GET for `?_rsc=` or `&_rsc=` on a
  line that carries the trailing ` rsc_prefetch=` field (nginx
  `$http_next_router_prefetch`, Apache `%{Next-Router-Prefetch}i`; Caddy's
  logged headers) with `-` or nothing, for no asset or beacon path - is a
  page view of its path. Any other value (`1`; `2` to `4` in newer Next.js)
  is a prefetch, never a page view. Without the field no payload is one
  (COUNTING-TRAPS.md trap 10). One click is one page view: an HTML page and
  a navigation of the same path in the same visit (address, agent, host),
  2 seconds or less apart, count once, the earlier (`parse.one_click`, run on
  every window read in time order; the audit's `audit.same_click`). A POST
  (a Next.js server action) or HEAD never is.
- **`ASSET`** - by extension (`css`, `js`, `mjs`, `map`, images, fonts, `txt`,
  `xml`, `json`, `webmanifest`, `xsl`, feeds, `pdf` and office documents,
  archives, audio and video, `wasm`) or by prefix (`/_next/`, `/static/`,
  `/assets/`, `/_nuxt/`, `/build/`). Note that `robots.txt` and `sitemap.xml`
  are assets by this rule, which is right: nobody reads them.
- **`BEACON`** - everything under `/api/` (since 2.8.1), `/__analytics`,
  `/collect`, `/beacon`, `/ping`. A page calls these while you read it. They are
  evidence of a visit, never a visit of their own. Before 2.8.1 only
  `/api/events` and `/api/analytics` were; a site's JSON API (`/api/v1/...`)
  then showed up as pages where visits ended and as steps between pages.

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

## What an AI fetch asked for

Every answer-engine request (both tiers, `asked` and `training`) is also
filed by what its path names (day kind `ai_formats`, since 2.10.0;
`ai_formats.format_of`, and on the audit's road `audit_ai_formats.kind_of`,
written apart). The path alone decides, lower case, without the query
string; the status does not, so a 404 for `/llms.txt` is a fetch of
llms.txt. In this order:

| format | path |
|---|---|
| llms.txt | exactly `/llms.txt` or `/llms-full.txt` (at the root; `/docs/llms.txt` is Text) |
| robots.txt | exactly `/robots.txt` |
| Markdown | the last segment ends `.md` or `.mdx` |
| Sitemap | the last segment is `sitemap*.xml` (`sitemap.xml`, `sitemap_index.xml`, `sitemap-1.xml`) |
| Text | any other `.txt` |
| Other file | an asset, feed, document, archive or media file (the extensions of "What decides a page view"), a framework folder (`/_next/`, `/static/`, ...), an `/api` or beacon path, or a framework payload (`?_rsc=`) |
| Page | everything else |

## The source type of a visit

`dimensions.source_type` (and, on the audit's own road,
`audit_labels.source_of`) gives each visit one of: AI assistant, Search
engine, Social media, Email, Other website, This site, Tagged link, Direct
or unknown (the stored name; shown to a person as Direct, see
`skald/labels.py`). A referrer decides first. With none, the tags do:

- **Search engines** are named by their real domains (`google.com`,
  `google.de`, `google.co.uk`, `google.com.au`, `bing.com`, ...), never by
  the word "google". An Android app's referrer is
  `android-app://<package id>/`: only Google's search app
  (`com.google.android.googlequicksearchbox`) is a search engine, and Gmail
  (`com.google.android.gm`) is email. Since 2.8.0 Google's other apps are not
  "Search engine": YouTube, WhatsApp and Telegram apps are Social media, the
  rest Other website. An assistant's app is the assistant (above).
- **Google AI Mode** (since 2.10.0). A Google search referrer (`google.com`,
  `google.de`, ..., not Gmail) with `udm=50` in its own query string or in the
  landing URL's is Google's AI Mode: the source type stays "Search engine",
  and the referrer label becomes `google.com (AI Mode)` (`google.de (AI
  Mode)`, ...), so it can be seen apart. Only when the parameter is there,
  never inferred: a bare `google.com` referrer stays `google.com`.
  `dimensions.referrer_label` and, on the audit's road,
  `audit_labels.referrer_of`; a visit's first page carries the label, and a
  later page from the other label is a new outside source, on both roads.
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
- **Social networks** (day kind `social_networks`). A breakdown of Social
  media, never a new type: each Social media visit gets exactly one network
  (`skald/social_names.py` lists them), by its first page's referrer
  host or app (X: `t.co`, `x.com`, `twitter.com` and under them,
  `com.twitter*`; LinkedIn: `linkedin.com`, `lnkd.in`, `com.linkedin*`;
  Facebook: `facebook.com`, `fb.com`; Threads, before Instagram, owns the
  app `com.instagram.barcelona`; Pinterest any `pinterest.<tld>`; ...),
  else by the words of `utm_source`, then of `utm_medium` (`x`/`twitter`,
  `linkedin`, `facebook`, `instagram`, `reddit`, `youtube`, `tiktok`), else
  by a social click id. A tag naming two networks, or none
  (`utm_source=social`), is "Social, network not named". The networks add up
  to the Social media visits. Only hosts already Social media are listed:
  `producthunt.com`, `threads.com`, `fb.me` and Mastodon servers other than
  `mastodon.social` stay Other website. Second count: `audit_social.py`.

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
  nginx's GeoIP module reads, not a guess. With neither, it is stored as
  Unknown and shown as Not recorded.
- **City** (2.12.0, people only). With a city file `logs.city_db` (a
  MaxMind-format `.mmdb`, DB-IP's free "IP to City Lite"), a reader's visit
  gets the city of its first page's address: `"City, Region, CC"` (the
  region left out when missing or the same as the city; commas in a name are
  spaces). A record without a city name gives none, and so does a city whose
  country is not the line's own country (`cc=`, or the country file's): a
  visit is never placed in a city of another country. No file, or no city:
  stored as Unknown, shown as Not recorded, never guessed. Bots, crawlers and
  our own traffic are never looked up.

## Line order

A visit is built from its lines in time order, so which page came first
decides its landing page, its steps (a → b), its exit, its trail and flow,
the funnels it meets, its first touch, what the AI read before it, and
whether a page from a new source starts a new visit. A log is not always in
time order: nginx writes a line when the request ends (a slow request lands
after faster ones that started later), some formats stamp a line with the
request's start, and shipped logs (skald-ship, ingest) and rotations can
interleave.

**The rule (both roads):** a window's lines are counted in timestamp order;
lines with the same timestamp keep the order they were read in (files oldest
first, each top to bottom). Which line of a repeated request id is kept is
decided before that, in file order, as it always was.

- **Main road** (`parse.in_time_order`, used by `window.ordered_classifier`
  and both passes of a window): it streams, holding each line back until a
  line at least 60 seconds newer (`parse.HOLD`) has been read, so memory is
  a minute of lines, never the day. The first pass (the classifier's) also
  measures how far behind any line was. When a line was further behind than
  the hold, that pass is read again holding back that far, and the count's
  pass uses the same hold: the order is exact whatever the lateness, and a
  log hours out of order costs a second read and that many hours of lines in
  memory, only on such a day.
- **Audit** (`audit.in_time_order`): sorts its whole window by (timestamp,
  place read), its own code.

Requests, page views and statuses never depend on order (every line is
still counted once); visits and the figures above can, and a day written in
order is counted exactly as before.

## What this cannot know

State these next to the numbers, not in a footnote.

**A user agent is self-reported and forgeable.** Every string the classifier
reads is a claim by the client. `people` is therefore an upper bound on humans,
never a count of them. A scraper that sends a plausible Chrome string and only
requests pages is caught by rule 9; one that drives a real browser and loads
the assets as well (a headless browser not saying so) is indistinguishable
from a reader.

**A person whose browser fetches six pages at once is not counted.** Rule 9b
cannot tell a visit that only restored six or more tabs of the site (or that
prerendered them) and loaded nothing after from a scraper. Reading on after
the burst keeps them a person.

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
purpose. Google's AI Mode is the one exception, and only when the click
carries `udm=50` (on the referrer or the landing URL): it is then labelled
`google.com (AI Mode)` ("The source type of a visit"). Most AI Mode clicks
arrive with the bare origin and stay plain `google.com`, so it is a floor.

**Referrers are frequently stripped**, by privacy settings, by
`Referrer-Policy`, by apps that open links in their own webview, and by HTTPS
to HTTP transitions. Every citation count is therefore a floor, not a figure.
`AI_UTM` recovers some of it and not all.
Skald estimates part of the rest, labelled as an estimate: a direct visit
to a page an assistant's user fetcher had just fetched is "likely" from
that assistant ("Inferred, not classified" above). It is never added to
the citation count. The rest of Direct is split the same way, as an
estimate under the Direct row: likely a checkout return, an in-app browser
or a shared link ("Direct, likely ..." above).

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
