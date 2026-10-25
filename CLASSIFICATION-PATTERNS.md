# Classification: the patterns

The second part of [CLASSIFICATION.md](CLASSIFICATION.md): the patterns its rules match
against. Rule numbers (rule 6b, rule 9, ...) are the ones in CLASSIFICATION.md, "The
order of the rules"; "above" and "below" mean in this file.

## The patterns

All are case-insensitive. The names are the constants in `classify.py`.

**The list as a file.** Every crawler and assistant fetcher these patterns name (with the
search engines, the SEO crawlers inside `OTHER_BOT` and the assistants' referrers) is
published as JSON at <https://skaldanalytics.com/bots.json>: for each name its pattern as
written here, its owner, its purpose (training, live fetch, search index, ads, SEO tool,
other), the group Skald files it in, and how its claim is checked (the owner's published
list with its address, reverse DNS, the owner's network, or not checked). It is built from
these constants, `bot_policy.CATALOG` and `bot_verify.py` by the website's build, carries
the Skald version, and a test fails while the file and the code differ. `Google-Extended`
is in it with no pattern, marked as a robots.txt token. (Not the dashboard's `bots.json`
data file, [docs/DATA-CONTRACT-BOTS.md](docs/DATA-CONTRACT-BOTS.md).)

### `AI_TRAINING` - matched against the user agent

Assistants fetching to train a model or build their own index. Nobody is
waiting on the response.

`GPTBot`, `ClaudeBot`, `Claude-SearchBot`, `CCBot`, `anthropic-ai`,
`OAI-SearchBot`, `PerplexityBot`, `meta-externalagent`, `FacebookBot`, `Bytespider`,
`Amazonbot`, `Applebot-Extended`, `cohere-ai`, `Diffbot`, `omgili`, `AI2Bot`,
`Timpibot`, `ImagesiftBot`, `YouBot`, `PanguBot`, `Kangaroo Bot`,
`DuckAssistBot`, `Amzn-SearchBot`, `Google-CloudVertexBot`,
`cohere-training-data-crawler`, `OAI-AdsBot`.

Added 2026-10-18 (below, "Checking the name lists"): `Amzn-SearchBot` builds
Amazon's search index for Alexa (Amazon says it does not train);
`Google-CloudVertexBot` crawls for Vertex AI agents a site owner builds;
`cohere-training-data-crawler` is Cohere's training crawler.

Added 2026-10-25: `OAI-AdsBot` is OpenAI's check of the landing pages of ads
submitted on ChatGPT (OpenAI's crawler page, developers.openai.com/api/docs/bots:
it visits only pages submitted as ads, and what it collects is not used for
training). Nobody waits on it, so it sits here like `OAI-SearchBot`, and it is
checked the same way, against `openai.com/adsbot.json` (`bot_verify.LISTS`
`openai-adsbot`, vendor `openai`). On the live sites every request carrying
the name, up to that day, came from outside OpenAI's list and asked for
`.env` files and keys: a scanner wearing the name. Rule 2b keeps those in bots
even on a day with no fresh lists.

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
`poe.com`, `mistral.ai`, `copilot.com`, `meta.ai`, `chat.deepseek.com`, `grok.com` -
or a host that an assistant shares, by its path (`AI_REFERRER_PATHS`): `bing.com`
under `/chat` (Copilot in Bing) and `x.com` under `/i/grok` (Grok inside X; any
other x.com address is X, the social network). A substring
match counted `thank-you.com` as `you.com`; `notperplexity.ai` and a
`?ref=chatgpt.com` query are not citations either.

An assistant's Android app sends `android-app://<package id>/`, so its package
id is the host. These count as the assistant: `com.openai.chatgpt`
(ChatGPT), `ai.perplexity.app.android` (Perplexity), `com.anthropic.claude`
(Claude), `com.google.android.apps.bard` (Gemini), `com.microsoft.copilot`
(Copilot), and since 2026-10-25 `com.deepseek.chat` (DeepSeek), `ai.x.grok`
(Grok) and `com.facebook.stella` (Meta AI), each checked on its Google Play
page. Without them an app citation was "Other website" (or, for Gemini,
"Search engine"). iPhone apps send no app id: an iOS app opens a link in Safari
or its own web view, which sends either no referrer (Direct) or the
assistant's web address, which the hosts above already count. So Copilot's
iOS app has no id to add; no `ios-app://` referrer appears in any site's log.

Every signal for one assistant gives it one name - its main domain:
`chat.openai.com`, `openai.com` and `utm_source=chatgpt` are all
`chatgpt.com`; `bing.com/chat` and `utm_source=copilot` are
`copilot.microsoft.com`, and so is `copilot.com` (Copilot's newer host: the
name stays the one history already holds); `chat.deepseek.com` and
`utm_source=deepseek` are `deepseek.com`; `x.com/i/grok` and `utm_source=grok`
are `grok.com`; each app's package id is its assistant's domain
(`classify.assistant_name`). History written with an
older name of an assistant is read back under the canonical one.

### `AI_UTM` - matched against the URL

Some assistants tag the outbound link instead of sending a referrer:
`utm_source=` followed by `chatgpt`, `openai`, `perplexity`, `claude`,
`gemini`, `copilot`, `mistral`, `deepseek`, `grok` or `meta.ai`. Meta AI only
as `meta.ai`: a bare `utm_source=meta` is how advertisers commonly tag their
Facebook and Instagram ads, and counting it would turn paid social into AI. Checked as a fallback for the same question,
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
`../`, `/etc/passwd`, `${jndi:`, `UNION SELECT`, `XDEBUG_SESSION`. Since
2026-10-25 the dots and slashes of `../` and `/etc/passwd` count encoded
once or many times over: `%2e%2e%2f`, `.%2e/`, `%2e.%5c`, `%252e%252e%252f`,
`%252fetc%252fpasswd` (`%(?:25)*2e` is `%2e`, `%252e`, `%25252e`, ...). A
live attack sent `pagename=templates%252f%252e%252e%252f...` and the single
`%2e%2e` did not see it. `?page=2`, `?q=v1..v2` and `?v=1.5.0` are not
attacks, and no page of the made-up sitemap matches (`tests/test_tool_visits.py`).

Rule 6c counts `PROBE` paths too: 5 or more different ones that the site
answered 4xx or 5xx (no asset, nothing under `site.legacy_paths`) make the
address and agent a scanner for the window, **scanner (asked for many
missing probe paths)**. Redirects and served probes never count.

That last family is the one worth remembering: it exists because somebody read
a real log and found those requests sitting in the "people" column.

### `BROWSER` - matched against the user agent

`Mozilla/`, `Opera/`, `Safari/`, `Chrome/`, `Firefox/`. The weakest signal in
the file, checked last. A browser-like visit that sends `HEAD` for 2 or more
different documents is a link checker (rule 8b): a browser opens pages with
GET.

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

