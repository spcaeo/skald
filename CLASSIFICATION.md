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

All are case-insensitive. The names are the constants in `classify.py`.

### `AI_TRAINING` - matched against the user agent

Assistants fetching to train a model or build their own index. Nobody is
waiting on the response.

`GPTBot`, `ClaudeBot`, `Claude-SearchBot`, `CCBot`, `anthropic-ai`,
`OAI-SearchBot`, `PerplexityBot`, `meta-externalagent`, `FacebookBot`, `Bytespider`,
`Amazonbot`, `Applebot-Extended`, `cohere-ai`, `Diffbot`, `omgili`, `AI2Bot`,
`Timpibot`, `ImagesiftBot`, `YouBot`, `PanguBot`, `Kangaroo Bot`,
`DuckAssistBot`, `Amzn-SearchBot`, `Google-CloudVertexBot`,
`cohere-training-data-crawler`.

Added 2026-10-18 (below, "Checking the name lists"): `Amzn-SearchBot` builds
Amazon's search index for Alexa (Amazon says it does not train);
`Google-CloudVertexBot` crawls for Vertex AI agents a site owner builds;
`cohere-training-data-crawler` is Cohere's training crawler.

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
`Gemini-User`, `BingPreview`, `MistralAI-User`, `Claude-Web`, `Google-Agent`,
`GoogleAgent-Mariner`, `Google-GeminiNotebook`, `Google-NotebookLM`, `Amzn-User`.

Added 2026-10-18: `Claude-Web` is Anthropic's older agent for fetches made
from claude.ai (`Claude-User` replaced it; it is still seen, and Anthropic's
published ranges do not cover it, so it is never checked, never "spoofed").
`Google-Agent` is Google's agent that browses and acts on a user's request
(listed with Google's user-triggered fetchers; `GoogleAgent-Mariner` is the
Project Mariner form). `Google-GeminiNotebook` (formerly `Google-NotebookLM`)
reads a page a user added as a source. `Amzn-User` fetches to answer an Alexa
question. Each has an owner in `AI_FETCHER_OWNERS` (Google's are
`gemini.google.com`, Alexa is `alexa.amazon.com`) and a row in the AI crawler
controls (`bot_policy.CATALOG`). None is checked against an address list
yet: Google publishes Google-Agent's ranges in a file `bot_verify.py` does not
read, and a check against the wrong list would call the real agent a fake.

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
`Baiduspider`, `YandexBot`, `Sogou(?!MSE|MobileBrowser|Explorer)`, `Exabot`,
`Applebot(?!-Extended)`, `SeznamBot`, `Yeti(?=/)`, `coccocbot`, `Qwantbot`,
`Qwantify`, `MojeekBot`.

`Sogou` means Sogou's spiders, never its browsers: `SogouMobileBrowser` and
`SogouMSE` are people with a phone, and were filed as the search engine until
2026-10-18. Added that day: the indexing crawlers of Seznam (Czech), Naver
(`Yeti/`, Korean), Coc Coc (Vietnamese), Qwant (French) and Mojeek
(British), whose referrers `dimensions.py` already counts as search engines.
They were bots before. None of them is checked against an address list.

A name that claims one of these, or an assistant's crawler, is checked
against its owner's published address ranges or by reverse and forward DNS
(`bot_verify.py`). One proven fake is filed under bots as "claims to be
<name>"; one that cannot be checked stays, marked unverified.

### `LINK_PREVIEWS` - matched against the user agent, before search

An app fetching a page because someone pasted its link in a chat or a post:
`Slack`, `iMessage`, `WhatsApp`, `LinkedIn`, `Microsoft Teams`, `Discord`,
`Telegram`, `X (Twitter)`, `Facebook`, `Pinterest`, `Reddit`, `Embedly`,
`Iframely`, `Snapchat`, `VK`, `Bluesky`, `Mastodon`, `Google Messages`
(`GoogleMessages/`, added 2026-10-18). Filed under bots as
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
  the phone maker CUBOT is not a bot) and not ending an Android model name
  ("M bot 60 Build/", "POWER BOT Build/": phones, people), `bot/<version>` ("FooBot/2.1"), the
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
  `PTST/` or `PTST ` (WebPageTest), `GTmetrix`, `Google-PageRenderer`
- added 2026-10-18 from the check below, all filed as people before because
  they send a full browser agent with their name tacked on:
  - testers and synthetic monitors: `Google Page Speed Insights`, `DareBoost`,
    `DebugBear`, `Ghost Inspector`, `RuxitSynthetic` (Dynatrace),
    `DatadogSynthetics`, `Neustar WPM`, `YottaaMonitor`, `Siteimprove`
  - Google tools and ad checks that are not indexing: `Google Web Preview`,
    `Google Search Console`, `Google-Ads-Overview`, `Google-Ads-Conversions`,
    `Google-Adwords-DisplayAds`, `Google-HotelAdsVerifier`, `DuplexWeb-Google`,
    `GoogleImageProxy` (Gmail's image proxy), `Google Favicon`,
    `Google-SearchByImage`, `Google Keyword Suggestion`, `Google-Publisher-Plugin`
  - screenshots and image search: `mShots`, `shrinktheweb`, `Site-Shot`,
    `wkhtmlto` (wkhtmltopdf, wkhtmltoimage), `webkit2png`, `TinEye`
  - link checkers, sitemap builders, crawl frameworks, data collectors:
    `deadlinkchecker`, `BrokenLinkCheck`, `XML-Sitemaps`, `Pro-Sitemaps`,
    `Nutch`, `Spinn3r`, `HubSpot`, `Datanyze`
  - security scanners and load testers: `zgrab`, `OpenVAS`, `ProbelySPDR`,
    `Hardenize`, `Siege/`, `fasthttp`, `Zombie.js`
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

### Checking the name lists (dev time only)

`tools/check-bot-names.py` runs a corpus of real user agents through
`classify.py` and lists the crawler agents it files as people (a bot the
lists miss) and the device agents it files as anything else (a person
counted as a bot). Each agent is one request for `/` with no referrer: the
name lists alone decide. The corpus used is Crawler-Detect's test fixtures
(github.com/JayBizzle/Crawler-Detect, MIT licence), downloaded by hand into
a folder of their own - data only, nothing from that project is run:

    mkdir -p /tmp/crawler-detect && cd /tmp/crawler-detect
    curl -fsSLO https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/tests/data/user_agent/crawlers.txt
    curl -fsSLO https://raw.githubusercontent.com/JayBizzle/Crawler-Detect/master/tests/data/user_agent/devices.txt
    cd -   # back to the repo
    python3 -I tools/check-bot-names.py /tmp/crawler-detect/crawlers.txt /tmp/crawler-detect/devices.txt
    # --all also lists every crawler agent filed as a bot, with the name it matched

Skald never reads Crawler-Detect, or any other list, at runtime, and never
learns names by itself. The lists are fixed data in the code: a day
recounted later is counted by the same rules, and the audit recounts with the
very same lists. A name the check finds is added here by hand, in its group,
with a test (`tests/test_bot_names.py`), conservatively: only names that are
well known or documented by their owner, and only when none of the device
agents matches.

The run of 2026-10-18 (3,713 distinct crawler agents, 165,640 device agents):

| | before | after |
|---|---|---|
| crawler agents filed as people | 249 | 135 |
| device agents filed as not people | 2,804 | 2,792 |

The 135 left are mostly dead services (StumbleUpon, Cuil, Voila), one-person
scripts, and Microsoft Office checking a link a person clicked in a
document (`Word/`, `Excel/`, `Microsoft Outlook`), which stays people for
now. The 2,792 device agents filed as bots are by design: Internet Explorer
7 and older ("compatible; MSIE" with no engine named), UCWEB and other
feature-phone and app clients (`Dalvik/`, `CFNetwork/`) that send no browser
token, and Googlebot's phone template without the Googlebot token.

### Bing Copilot by `form=MA...`: not adopted

The Third Audience WordPress plugin files a `bing.com` referrer whose query
has `form=MA...` (e.g. `form=MA13FV`) as Copilot. Not adopted, 2026-10-18:

- the plugin gives no source for the rule, and Microsoft documents no
  meaning for Bing's `form=` codes, which mark where a Bing search was
  started, not that an assistant answered;
- Bing, like Google, normally sends other sites only its origin
  (`https://www.bing.com/`), so the query string with `form=` seldom reaches
  a server log at all;
- Copilot has its own host, `copilot.microsoft.com`, already counted, and
  Bing's chat answers keep their `/chat` path (`AI_REFERRER_PATHS`).

Counting it would relabel ordinary Bing searches as AI on an undocumented
guess. If a real log ever shows `form=MA...` referrers that can be tied to
Copilot, add it to `AI_REFERRER_PATHS`'s rule in `classify.cited_by` and to
the audit's `_cited` together, with a test on both roads.

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
- WordPress as a segment: `/wp-admin`, `/wp-login`, `/wp-content`, `/xmlrpc`; the bare words
  `wordpress` and `wp` only at the start of the path (`/wordpress/`, `//wp/...`), so a site's
  own page about WordPress (`/integrations/wordpress/`) is a page (2.31.1)
- dumps and backups shaped like files: `/backup.zip`, `/db.sql`,
  `/dump.sql.gz`, any `.sql`, `.bak`, `.sqlite`, and a bare `/backup/`
- keys and credentials shaped like files: `id_rsa`, `.pem`, `.key`,
  `/credentials.json`, `/secrets.yml`, `/service-account*.json`,
  `/docker-compose*.yml`
- an app's settings shaped like files: `/config.json`, `/settings.yml`,
  `/appsettings.json`, `/firebase*.json`, `/key.json`, `/env.js`
- infrastructure and deployment files (2.20.1): any file ending `.tf`,
  `.tfvars`, `.tfvars.json`, `.tf.json`, `.tfstate` or `.tfstate.backup`;
  `/.terraform/`, `/.kube/`, `/.circleci/`, `/.github/`, `/.gitlab-ci.yml`,
  `/.travis.yml` (dotfiles, as above); `cdk.out`, `cdk.json`,
  `cdk.context.json`; `appspec`, `buildspec`, `serverless`, `cloudbuild`,
  `bitbucket-pipelines`, `azure-pipelines`, `kustomization` and `skaffold`
  `.yml`/`.yaml`; `samconfig.toml`, `kubeconfig`, `Jenkinsfile`,
  `Dockerfile`; and **at the root only** `/template.yaml`, `/values.yaml`
  and `/Chart.yaml` (CloudFormation, Helm), names a real page could carry
  deeper in a site
- a project's package files: lock files anywhere (`composer.lock`,
  `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Gemfile.lock`,
  `Pipfile.lock`, `poetry.lock`, `Cargo.lock`); manifests **at the root
  only** (`/composer.json`, `/package.json`, `/Gemfile`, `/Pipfile`,
  `/requirements.txt`, `/go.mod`, `/Cargo.toml`, `/pyproject.toml`)
- admin panels and consoles as a segment: `/admin`, `/phpmyadmin`,
  `/cgi-bin`, `/jenkins`, `/actuator`, `/telescope`, ...
- framework debug endpoints that are remote-code-execution routes:
  `/_ignition`, `/_debugbar`, `/_profiler`, `/vendor/phpunit`, `eval-stdin`,
  `invokefunction`, `/containers/json`, `/HNAP1`, `/owa`, `/sdk`, ...

`SECRET_PROBE` is the part that marks the whole visitor (rule 6b): the
dotfile, dump and backup, key and credential, infrastructure and package
families. Scripts, WordPress, an app's settings, admin panels and debug
routes stay probes of their own request only, because real readers ask for
them too.

`/administration-guide/` is not `/admin`; `/blog/wp-alternatives` is not
WordPress; `/sitemap.xml.gz` is not a backup; `/terraform/`,
`/main-features/`, `/composer/`, `/templates/` and `/fonts/x.ttf` are not
infrastructure files (`tests/test_scanner_visitor.py`).

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
landed in bots on every site. The same agent reads the site's sitemaps for
crawl health (sitemap.py): the files on robots.txt's `Sitemap:` lines and
`/sitemap.xml`, once a day (retried at most hourly after a failure), only on
the site's own hosts, 5 s and 10 MB a file, 20 files at most;
`crawl_health.sitemap: false` turns it off
([docs/DATA-CONTRACT-CRAWL-HEALTH.md](docs/DATA-CONTRACT-CRAWL-HEALTH.md)). Those
requests are our own traffic too, under the same label.

Crawl health follows Google (`Googlebot`), Bing (`bingbot`) and every AI
crawler and AI user fetcher by the name and tier given above; a crawler
claiming one of those names from an address that is not theirs is a bot and is
not in it.

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
