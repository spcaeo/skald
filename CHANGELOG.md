# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

### Website: live up to 2.37; What's new has 2.37

- **Live.** Every Website section below went up to skaldanalytics.com on 26 Oct 2026 at 00:28
  UTC, with 2.37.0 live on the server. **Added.** /whats-new/ has a 2.37 entry (six MCP
  tools, the live count readable, docs that match); the upload had shown 2.36.1 as the newest.
  Who it affects: readers of skaldanalytics.com. What to do: nothing. **Checked:** all 151
  sitemap pages answer 200, the build says "problems: none", no console errors on the home,
  what-changed and MCP pages.

### Public notes: a measured site no longer named in the 2.23.0 notes

- **Fixed.** The 2.23.0 notes (docs/CHANGELOG-2.23-2.26.md and the v2.23.0 GitHub release)
  named one of the sites we measure three times. They now say "one site we measure". Why: the
  public export check let the name through in changelogs, where the company behind it may be
  credited; it now flags that site's address in every file, changelogs included. Who it
  affects: nobody running Skald. What to do: nothing. Checked: the export's own tests, and a
  search of the public repo for the address finds nothing.

### Website: a GitHub button with the star count on every page; MCP pages say 20 tools; CDN days said to be withheld

- **Added.** The header on every page has a GitHub button: the GitHub mark, "GitHub" and the
  repo's star count ("★ 21"), linking github.com/spcaeo/skald; the mobile menu has "Source on
  GitHub" with the count, and the footer says "Free to self-host. Source-available under the
  Elastic License 2.0" beside the same button. The count is read when the site is built
  (`_src/github.py`, GitHub's API, kept in `_src/github.json`); offline the last kept count is
  used, and no visitor's browser calls GitHub. The home page, /self-host/ and /install/ say
  "free to self-host, source on GitHub" next to their main buttons. **Why:** the owner asked that
  the site show clearly that the source is on GitHub; it never says "open source" (a search of
  every page finds the words only for the MIT php2shell-check tool and the line saying ELv2 is
  not open source). **Who:** readers of skaldanalytics.com. **Do:** nothing. **Checked:** the
  header fits on one row at every width from 320 to 1440 px on five pages (the word "GitHub"
  drops below 1280 px, Live demo below 1220, the menu folds below 1100, the tagline and "Menu"
  word below 480, the count below 380); the site has one dark look, the same in light and dark
  mode.
- **Changed.** /integrations/mcp/, /integrations/, /features/, /for/ and /for/developers/ say the
  MCP server has 20 read-only tools, and the MCP page lists the six new ones (what_changed, todos,
  lost_pages, page_changes, ai_readiness, changed_pages) from their own descriptions in the MCP
  server's code. The six are not in 2.36.1, so upload these pages with the release that ships
  them. **Checked:** the MCP server's tool list has 20 tools, each marked read-only.
- **Fixed.** /beta/, the home page, /install/ and What's new now say that a day read only from a
  CDN log export (Cloudflare Logpush, CloudFront, Fastly, Akamai) is withheld, because the second
  count does not read those formats yet (docs/CDN-LOGS.md); the Skald Worker's days are counted
  twice. /check/ and /security/php2shell/: four of Node.js's ten fixes are rated High, not one;
  PHP's source backports for 7.4 to 8.1 sit beside the distributions' own; every source link
  carries its date; CVSS, WAF and PHP-FPM are explained. /privacy/: the script's events are kept
  400 days (the default, `beacon.KEEP_DAYS`; this site sets no other), now in the text and on
  the timeline. The Vercel plan claim links Vercel's drains page. Lines with no source were cut
  or reworded on the home, demo, pricing, story, contact, 404 and three insights pages; the demo
  says Montréal's AI answers run monthly in French, as `tools/demo_answers.py` has it.
  **Why:** an independent grader scored the 18 pages of groups J1, J2 and K: 17 at 83 to 88,
  /check/ at 80, below the bar of 81, on the Node.js line. **Who:** readers of
  skaldanalytics.com. **Do:** nothing. **Checked:** nodejs.org, php.net, Vercel's drains page and
  the OSI licence list read on 25 Oct 2026; the site build ends "problems: none"; the site
  tests pass.

### Website: the committed site is what the build writes; every link and asset checked

- **Changed.** The build's own output is now committed in full: the 30 guide pages under
  `/docs/`, the Markdown copy of every page (281 `.md` files), `/llms.txt` and
  `/llms-full.txt`. Before, only the HTML pages were in git, so every build left about 280
  untracked files, a clean export of a commit held no Markdown copies, and the uploads relied
  on a build run in the export. A guide's sitemap date is its last commit's day, or today while
  the guide has uncommitted changes, so building, committing and building again gives the same
  date (before, `/docs/security/` moved from 24 to 25 Oct after the 2.36.0 commit).
  **Added:** `_src/linkcheck.py`, run by the build: every `href`, `src`, `srcset`, CSS `url()`,
  Markdown link and written-out `https://skaldanalytics.com/...` address in every file the build
  wrote must land on a file the site has, and a `#fragment` on an id of that page; and the build
  names any page or Markdown file no page writes any more. **Why:** the owner's task list
  (reproducible build, every internal link checked). **Who:** whoever builds and uploads the
  site. **Do:** nothing; `git status` after a build of a committed tree shows nothing.
  **Checked:** the build twice: the second run changed none of the 737 files; "problems: none";
  `tests/test_site_linkcheck.py` (each kind of break named, escaped code and JSON-LD ids left
  alone, the built site clean); a planted stale page was named.

### Website: What's new shows 2.35.1, 2.36.0 and 2.36.1; the security pages say "seen", not "caught"

- **Added.** /whats-new/ has entries for 2.35.1 (Security's attack rows in one order), 2.36.0
  (one summary mail a day; the HTML sitemap page is not a page) and 2.36.1 (each site's mail
  links open that site), newest first; the hero's book spines show them. **Changed.** The
  security hub, the AI-key thief story and the What's new line that names it no longer say
  Skald "caught" a thief: "It saw an AI-key thief at work", the badge "Attackers seen", and
  "Skald shows what was tried and what your server answered. It cannot tell that an attack
  succeeded, and it blocks nothing itself." The hub says seven questions, one per tab (it said
  six), and dates the php2shell card 21 Oct 2026 instead of "This week"; source links carry
  their read date. The MCP guide (`docs/help/mcp.md`, so /docs/mcp/ and the in-app Help) says
  the OpenAI API takes the token in the MCP tool's `authorization` field, quoting OpenAI's
  connectors guide, not an `Authorization: Bearer` header. **Why:** the second, independent
  grade of 2026-10-25 (`_src/pages/FIXES-2026-10-25.md`, items 7 and the MCP item); these fixes
  were half done on two parked branches and are now applied. **Who:** readers of
  skaldanalytics.com. **Do:** nothing. **Checked:** the site build, "problems: none"; the
  story's page test now holds the new wording; `tools/build-about.py` run.
- **Changed.** The announcement bar on every page said "It caught an AI-key thief"; it now
  says "It saw an AI-key thief at work". The security hub's Alerts line says alerts come in one
  summary mail a day at 01:00 or right away (2.36.0), not "at once or in the daily mail". The
  site's SoftwareApplication data lists four 2.35/2.36 features: AI readiness per page, What
  to fix, Did my change work, the daily summary mail. **Checked:** the site build and site
  tests; the full test suite.

### Website: feature, log, set-up, self-host and security pages say what 2.35 and 2.36 do

- **Changed.** /features/ and its pages: the daily summary mail at 01:00 and "right away" as
  one mail per run (alerts, reports), sale alerts (off by default), Summary's five tiles and the
  period line, To do now, lost pages, the trail and copy icons (dashboard), Social and Direct,
  the Pages sorts and Changed column, AI readiness and "Did my change work?" (pages and
  sources), the new second counts and not-a-page addresses (counted twice; "2,900+ tests", it
  said 2,500+), whole-site-only figures (page groups), marking and sending to-dos (team).
  /server-log-analytics/ and its pages: Akamai DataStream 2, Test a sample (`try-log`), counting
  rules 2b, 6c and 8b. /self-host/ and Docker, Fly: crawler checks on by default in Docker
  (`SKALD_VERIFY_BOTS=off`), the 01:00 summary. /docs/ and add-a-site: no more "New in 2.31";
  Test a sample. /security/scanners/ and /security/stack-advisories/: the summary mail, attacks
  encoded twice, and "How Skald saw an AI-key thief at work" (it said "caught"). /check/ and
  the php2shell article: "this week" is now "17 to 20 October 2026" (the dates of those
  figures in `docs/marketing/security-posts-2026-10.md`). Guides: `docker-first-install.md`
  has the doctor's Crawler checks row; `security.md` says an attack encoded twice is read too.
  **Why:** these pages still described 2.34. **Who:** readers of skaldanalytics.com and the
  in-app Help. **Do:** nothing. **Checked:** every line against the code it names; the site
  build, "problems: none"; the full test suite.

### Website: AI traffic, AI visibility, leads, GA alternative and comparison pages up to 2.36.1

- **Changed.** The AI crawler pages count 40 AI names (39 before) with OAI-AdsBot, OpenAI's
  fourth address list (`adsbot.json`) and its row in the crawler rules; a crawler name asking
  for a probe path (`/admin/`, `/.git/config`, `/wp-login.php`) with an old address list is
  filed under bots (rule 2b). /ai-traffic-analytics/ai-referrals/ lists Copilot, Meta AI,
  DeepSeek and Grok and their apps and tags. Every page that explains "likely from an AI" says
  a match chance explains does not count. /ai-traffic-analytics/google-ai-mode/ showed
  Googlebot under Bots; it is under Search engines. Crawl health and llms.txt: `.md` copies are
  not page views, and the AI readiness checks and the sitemap's lastmod are named.
  /compare/known-agents/ says 40 for Skald (nothing quoted about the other product changed).
  /google-analytics-alternative/ adds Akamai and sales value by source. The leads hub and its
  pages add sale alerts, Leads' 7, 30 and 90 days including today, leads kept for good, Direct
  leads with their likely reason, removing a lead by its reference, and the owner-approved week
  from freshlycited.com (19 to 25 Oct 2026, test events excluded: 203 lead events from its own
  backend, 87 tied to the visit that brought them, 4 from an AI assistant, 10 sign-ups won).
  **Why:** these pages described 2.34; the owner asked that the lead work of this week shows,
  and allowed naming freshlycited.com with its aggregate figures (2026-10-25). **Who:**
  readers of skaldanalytics.com. **Do:** nothing. **Checked:** counts from `classify.py` and
  the built `/bots.json`; the site build, "problems: none"; site and repo tests.

### Website: ten new pages for 2.35 and 2.36, from the questions a site owner asks

- **New.** Five feature pages and five notes, each with its own hero and interactive parts
  built from the code they describe, around one theme: from reacting to a bad week to a short
  routine the server log answers. /features/what-changed/ (is it working: now against before,
  Include today, the change rule, work on the page or on traffic, new pages getting found);
  /features/did-my-change-work/ (mark a change, the same whole days before and after, a
  verdict per figure); /features/seo-to-do-list/ (the to-do list, its thresholds and the daily
  re-check); /features/404-redirects/ (old addresses still asked for, the closest live page and
  the 301 or 410 line to paste); /ai-traffic-analytics/ai-readiness/ (the six readiness lines
  and the pages AI cannot read well). Notes: /insights/reactive-to-proactive-analytics/ (the
  12 questions and where Skald answers each), /insights/alert-fatigue/ (from 44 security mails
  in a minute to one summary a day), /insights/bots-that-look-human/ (link checkers, probe
  sweeps and encoded attacks, and the "likely from an AI assistant" chance rule),
  /insights/markdown-copies-for-ai/ (what a .md request gets back),
  /insights/which-visits-became-customers/ (one real week of leads on freshlycited.com: none of
  the 10 won sign-ups carried the visitor ID, so their visits could not be shown; the fix is to
  send `vid` with the sign-up and its later stages). The /insights/ hub's
  opening line and its "is the data real" answer now fit the new notes.
  **Why:** 2.35.0 to 2.36.1 shipped these features with no page on the website. **Who:**
  readers of skaldanalytics.com. **Do:** nothing. Real figures: skaldanalytics.com's own, as
  published in the 2.35.0 to 2.36.1 notes above (linked to the public changelog), and one
  docomatic.ai to-do read from the live install on 25 Oct (240 old addresses asked for), and
  freshlycited.com's lead counts for 19 to 25 Oct (203 lead events, 72 from the script tag and
  131 from its server; 87 with a visitor ID; 4 from an AI assistant; 10 sign-ups won, none with
  a visitor ID; counts only, test events left out), both named with
  the owner's OK; every other figure is marked sample.
  **Checked:** the site build ends "problems: none" and the rubric's machine checks pass on all
  ten; the repo tests pass; every page at 1440 and 390 px in a headless browser (one h1, no
  sideways scroll, no 4xx apart from the tag script only the live server serves, every control
  writes its state to the address); outside links opened and every outside quote checked word
  for word; graded on `_src/pages/RUBRIC.md` by a separate grader after fixes: 94 to 98 of 100,
  and did-my-change-work 89 of 90 until a real change has 14 days (about 8 Nov).

### Website: the home page, pricing and demo rebuilt (group J1); the script-tag page fixed

- **Changed.** The home page: a sample "Daily Log" front page, the pages each AI company
  crawled, fetched and sent clicks to, social networks with every address added up (2.34.0),
  sources ranked by leads or by revenue per currency (never added together), and the second
  count shown as a carbon copy that withholds a day. /pricing/: a seat map of plans by site
  count, trial steps by how the site is served, who holds what when hosted or self-hosted;
  prices still come only from `conf.py` and stay marked proposed. /demo/: a spotlight tour of
  the Overview, the dashboard's own `g` + letter shortcuts, and what the sample is made of.
  **Why:** the old pages repeated folds used elsewhere and did not show the newer features.
  **Who:** readers of skaldanalytics.com. **Do:** nothing. **Checked:** the site build ends
  "problems: none"; the three pages at 1440 and 390 px; graded 85 to 86 by the builder.
- **Fixed.** /docs/setup/script-tag/ said the tag stores nothing in the browser when visitor IDs
  are off. It always keeps the visit's source in the tab's session storage; the page now lists
  what is kept in each case, as the tracking-script guide does. **Checked:** against
  `docs/help/tracking-script.md` and a search of every website page.

### Website: insights, author and the older pages in the new look (groups J2 and K)

- **Changed.** /insights/ and its three notes, the author page, about, story, privacy, contact,
  beta, install, what's new and the 404 are rebuilt, each with its own interactive part, every
  claim checked against the code; /security/, /check/, php2shell and ai-key-thief keep their
  content in the new styling. Fixed on the way: the check now says it makes at most 8 requests by
  default; a release note said Skald "does not block attacks" (it blocks nothing); the about page
  showed the private folder name instead of the public `skald/`; the privacy page's bars had no
  width. **Why:** these were the last pages in the old look, and some lines no longer matched the
  code. **Who:** readers of skaldanalytics.com. **Do:** nothing; the author page keeps an empty
  photo slot for the owner. The install page's pinned download names the current release by a new
  `{{VERSION}}` placeholder (read from `VERSION`), so it no longer goes stale.
  **Checked:** the site build ends "problems: none"; the site and repo tests pass; the 17 pages at
  1440 and 390 px (one h1, no sideways scroll, no console errors, no 4xx apart from the tag
  script that only the live server serves); graded on `_src/pages/RUBRIC.md` at 82 to 87.
- **Fixed.** /check/ said "Updated 22 Oct" while its news list held a 23 Oct advisory; the page,
  its news file and its sitemap date now all say 23 Oct. The short author bio says why Rakesh
  built Skald instead of repeating the page title. The site notes count "2,900+ tests" (3,277 ran
  on 2026-10-25). **Checked:** `test_check_page.py` and the site build.

### Website: Solutions and Integrations pages rebuilt (groups H and I)

- **Changed.** /for/ and its five pages (agencies, SEO teams, SaaS founders, developers, small
  business) and /integrations/ and its eight (API, MCP, Slack, webhooks, Next.js, WordPress,
  Google Search Console, Bing Webmaster Tools), each with its own hero and interactive part built
  from the code: the API's scopes and error reasons, the MCP server's rule order, the alert retry
  times, the data contract's day states, plan site counts with no prices. Claims about other
  products are quoted from their own pages, read 24 October 2026. Removed what had no source:
  "Vercel log drains need Vercel Pro", ChatGPT and Claude Desktop screen claims, "two-minute
  fresh" (the code says 15 minutes); the SEO teams FAQ now says Skald itself blocks nothing.
  `_src/pages/FEATURES.md`: a developer share link lasts 1, 7 or 30 days (7 by default), as
  `share_links.py` has it. **Why:** they shared one template and some claims had no source.
  **Who:** readers of skaldanalytics.com. **Do:** nothing. **Checked:** the site build ends
  "problems: none"; the 15 pages at 1440 and 390 px (one h1, no sideways scroll, no console
  errors, no 4xx); graded on `_src/pages/RUBRIC.md` at 84 to 86 by the builder.

### Recount: Social networks and Direct, likely for the 14 days before their releases (live 2026-10-25)

- **Changed.** On app.skaldanalytics.com every site's last 14 stored days were counted again
  from the raw logs with 2.34.0 (`skald backfill --days 14 --force`), so Traffic › Sources'
  Social network tab and Direct, likely now have those days instead of "Not recorded". **Why:**
  the owner asked how much traffic came from X and LinkedIn; 2.34.0 counted only from its own
  day. **Who:** everyone with a dashboard on that server. **Do:** nothing; a self-hosted install
  can run the same steps (`docs/help/where-visitors-come-from.md`). **Checked:** a backup with its
  restore test first; `skald audit --day` on every recounted day: all 63 stored site-days match
  their second count, none withheld; days before a site's first log line stay not recorded.
### Website: comparisons, Google Analytics alternative and security pages rebuilt (groups F and G, live 2026-10-25)

- **Changed.** The /compare/ hub and its eight comparisons (Google Analytics, Plausible,
  Matomo, PostHog, GoAccess, Cloudflare, Known Agents, Search Console); the hub carries the
  "they see clicks, Skald sees the reads" block. Every claim about another product is quoted
  from its own public pages, read on 24 October 2026, with the source and date beside the
  claim; claims we could not check, and all prices, were left out. /google-analytics-alternative/
  and its cookieless and privacy-friendly pages: the cookieless page now says exactly what the
  optional tag keeps in the browser (the visit's source in the tab's session storage; a random
  ID only when visitor IDs are on), checked against the tag's code, and "nothing goes to a third
  party" now reads "unless you connect a service". /security/scanners/, /security/block-list/,
  /security/stack-advisories/ and /tools/php2shell-check/, built from the code (the fallback-page
  rule, the three block-list formats, the PHP fixed releases and the five advisory answers, the
  CLI's labels and exit codes); the Cloudflare and PHP facts link Cloudflare's and php.net's own
  pages. No page says Skald blocks traffic or detects exploits. **Why:** the owner's rebuild
  plan, approved 2026-10-24. **Who:** readers of skaldanalytics.com. **Do:** nothing.
  **Checked:** the site build ends "problems: none" (77 pages graded); the 16 pages at 1440 and
  390 px (one h1, no sideways scroll, no script errors, no 4xx); graded on `_src/pages/RUBRIC.md`:
  ten at 90/90, six at 82 to 89 with the grader's last fixes applied after grading.
- **Found while grading, not fixed yet:** `docs/help/tracking-script.md` says the tag stores
  nothing in the browser when visitor IDs are off, but the tag keeps the visit's source in the
  tab's session storage; `docs/help/security.md` gives Cloudflare's old menu path for lists. Fixed
  in "Help and privacy notice" above.

### Website: the 11 feature pages rebuilt and graded (group E, live 2026-10-24)

- **Changed.** /features/ and its ten pages (dashboard, real time, alerts, counted twice,
  pages and sources, page groups, visitors and journeys, reports and exports, team and
  access, privacy and retention), each its own design from the code it describes and graded
  on `_src/pages/RUBRIC.md`; the features hub now names revenue on leads (2.32.0). /docs/
  links to /docs/guides/ and /llms.txt, and its FAQ names the guides first. **Why:** the
  owner's rebuild plan, approved 2026-10-24 ("finish all"). **Who:** readers of
  skaldanalytics.com. **Do:** nothing. **Checked:** the site build ends "problems: none"
  (61 pages graded); the 12 pages load at 1440 and 390 px with one h1, no sideways scroll,
  no NaN or "undefined", and no script error (the only failed request is the site's own
  `/traffic-js/skald.js`, which only the live server serves).

### Website: log and set-up pages rebuilt and graded (group D, live 2026-10-24)

- **Changed.** 20 pages, each its own design from the code it describes, graded 81 or more of
  90 on `_src/pages/RUBRIC.md`: the server log analytics hub and how it works; nginx, Apache,
  Caddy, Cloudflare, CloudFront, Fastly and Vercel; /docs/ and its set-up pages (add a site,
  one command, the script tag, Claude Code), which now start with "One line for your AI
  agent"; and /self-host/ with Docker, Coolify, Fly, Kubernetes, Railway and Render. Every
  control writes its state to the address. **Why:** the owner's rebuild plan, approved
  2026-10-24 ("finish all"). **Who:** readers of skaldanalytics.com. **Do:** nothing.
  **Checked:** the site build ends "problems: none"; each page's old links are kept; browser
  checks at 1440 and 390 px, with reduced motion and without JavaScript.

### Website: the Help guides as docs pages, and every page as Markdown for AI agents (live 2026-10-24)

- **Added.** Each guide in `docs/help/` is now a page at `/docs/<guide>/`, with a list of all
  of them at `/docs/guides/`, made by the same parser as the in-app Help, so the website, the
  app and GitHub say the same words. Every page of the site, and every guide, is also Markdown
  (`/features/` is `/features.md`, the home page `/index.md`), and `/llms.txt` lists every
  page and guide with a one-line summary; `/llms-full.txt` holds every guide in one file. Each
  page names its Markdown copy and llms.txt in a `<link rel="alternate">` and in a hidden line
  near the top, which shows on keyboard focus. The footer links "All guides" and "llms.txt".
  New: `_src/docs_guides.py`, `_src/page_markdown.py` (stdlib HTML to Markdown: menus, hidden
  parts and the closing band left out, cards kept as one line each).
  **Why:** AI assistants and coding agents read docs as Markdown; the owner approved
  publishing the guides this way and scoring them with Fern's agent-friendly docs check
  (item 3 of 2026-10-24). **Who:** readers of skaldanalytics.com and the AI tools that fetch
  it. **Do:** nothing. **Checked:** the site build ends "problems: none" (the "firewall"
  rule now lets "a firewall" and "any firewall" through: the guides mean the reader's own);
  `npx afdocs` 0.22.2 on a local copy scores 96 of 100 (the one failing check, content
  negotiation, needs the nginx change at upload); every guide fits at 390 px with no
  sideways scroll; new tests in `tests/test_site_markdown.py`.
  **Live:** uploaded 19:15 UTC with nginx serving `.md` as `text/markdown` and answering
  `Accept: text/markdown` with the page's Markdown (`Vary: Accept`). `afdocs` on the live site:
  99/100. Fern's Agent Score: 98/100, grade A (buildwithfern.com/agent-score/company/skald).

### Website: the main button is a warm orange with white text (live 2026-10-24)

- **What changed:** the main button on every page (`.btn-p`, `.sk-btn-p`) is now `#c84a16`
  with white text, `#b03f12` on hover, from two new colour tokens (`--sk-cta`,
  `--sk-cta-hover`). The owner also approved the first 28 rebuilt pages (A, B, C); from here
  pages ship on the rubric without a review page by page.
- **Why:** the owner asked for every page to be built around its CTA buttons ("very focused CRO
  and CTA buttons"); the main button now stands apart from the page's other colours.
- **Who:** website visitors. **Do:** nothing.
- **Checked:** the site build, "problems: none"; white on `#c84a16` is about 4.7 to 1 (AA);
  the colour and hover read back in a browser at 1440 and 390 wide.

### Website: the 11 AI traffic pages rebuilt and graded (live 2026-10-24)

- **What changed:** the AI crawlers, ChatGPT, Claude, Perplexity, Google AI Mode, AI referrals,
  crawl health, block AI crawlers and llms.txt pages, the AI traffic guide and What is GEO are
  rebuilt, each with its own hero and folds drawn from its own code (classify, bot_verify,
  bot_policy, robots, ai_likely, ai_read, ai_formats, llms_txt, crawl_health, crawler_cost,
  alerts). The robots.txt tester, the llms.txt file maker and the format sorter are JavaScript
  copies of the Python code, checked to give the same answers. All 11 graded on the rubric:
  77-84 before, 86-87 of 90 after.
- **Facts corrected on the way:** Google and Anthropic do publish address lists (Skald simply has
  no check for some of their names); Google-Extended is only a robots.txt line, no request
  carries it; the guide's referrer is the second quoted field, and its command counts requests,
  not visits; "about 60" or "about 40" names is now the 39 in the code. Claims the code does not
  back were removed (most AI Mode clicks lose their referrer, the big crawlers follow
  robots.txt, fakes probe /.env, a reason Gemini makes no fetches, any AI Overview click figure).
- **Why:** the owner: every page unique and deep, and no AI-sounding pages.
- **Who:** site visitors, once deployed. **Do:** nothing. First-hand details wait for the
  owner's OK (listed in RUBRIC.md).
- **Checked:** build "problems: none" with 29 pages graded; each page at 1440 and 390 px with no
  JS errors, 4xx, sideways scroll or raw placeholders; every visible control clicked and kept in
  the URL.

### Website: AI visibility and leads pages rebuilt; every page graded on a rubric (live 2026-10-24)

- **What changed:** the 5 AI visibility pages and the 12 leads and journeys pages are rebuilt
  with their own parts, each from its own code (answers/, conversions/ and its adapters,
  funnels, firsttouch, utm_hygiene, the WordPress plugin, the lead files). A rubric now grades
  every page out of 100 (`_src/pages/RUBRIC.md`: title pays its promise, sourced numbers,
  plain voice, every term explained, no fake proof, SEO basics, the answer in the first 100
  words, one first-hand detail). `_src/rubric.py` runs its machine checks in the build for
  graded pages. The first 18 pages were graded and fixed: 75-82 before, 84-86 of 90 after.
  "More on wordPress" headings now keep the name's capital. Facts corrected on the way:
  Perplexity is sent "en", not "en-GB"; leads count finished bookings and forms, not
  payments; the funnel "Contains" match is written in the funnel's link only.
- **Why:** the owner: every page unique and deep, and no AI-sounding pages.
- **Who:** site visitors, once deployed. **Do:** nothing. First-hand details wait for the
  owner's OK (listed in RUBRIC.md).
- **Checked:** build "problems: none" with 18 pages graded; site tests; each page at 1440 and
  390 px with no errors or sideways scroll.

### Website: every page its own, starting with AI traffic (live 2026-10-24)

- **What changed:** /ai-traffic-analytics/ rebuilt top to bottom: a hero that sorts sample log
  lines live, a drag-to-compare of a script tag against the log, a step-through of one ChatGPT
  question, a crawler check that stamps Verified or Spoofed, a look-back window you drag to
  see a "likely from ChatGPT" visit appear, llms.txt demand and a suggested file, crawler cost
  beside a sitemap grid, and a rule builder that writes Skald's real nginx lines. The tag line
  under the logo is plain and sharp (no italics). A page can now load its own CSS and JS
  (`css`, `js` in page.json; the build dropped them before). `_src/pages/REBUILD.md` tracks
  every page; `_src/pages/LEDGER.md` lists every signature part so none repeats.
- **Why:** the owner: 71 of 90 pages opened on the same log window, and every fold must speak
  to a problem or an outcome, be engaging, and rest on the real code.
- **Who:** site visitors, once deployed. **Do:** nothing.
- **Checked:** build "problems: none"; site tests; all 111 pages at 1440 and 390 px; every
  control on the page tried (window 20 and 8 minutes, the rule builder, the URL keeps each
  choice).

### Website: skaldanalytics.com rebuilt, one page per feature (live 2026-10-24)

- **What changed:** the marketing site has 100 new pages built from `_src/pages/` (a page.json
  and its HTML parts each): the home page, AI traffic (crawlers, live fetches, clicks, cost,
  crawl health, rules), AI visibility, leads and journeys, server log analytics, self-hosting,
  docs, features, comparisons, Google Analytics alternative, security, roles, integrations,
  insights, pricing, demo and the author page. A new dark header with a light menu panel (the
  dark-on-dark menu was hard to read), the tag line under the logo, and a new footer on every
  page, old ones too. The old pages (security, check, install, about, story, privacy, contact,
  beta, what's new, 404) keep their words.
- **Fixed on the way:** the dark button in the orange end band showed no text (owner's
  screenshot); the yearly price switch did nothing; browsers kept old CSS and JS (each link now
  carries a hash of the file); `{{TRIAL}}` and `{{DEMO}}` were left as raw text in some heroes;
  related-card titles lost their capitals ("ai traffic").
- **Why:** the owner asked for every feature to have a page that says what it is, why it
  matters and what to do next, with the same look and motion as the new home page, and each
  page built for search.
- **Who:** visitors of skaldanalytics.com, once it is deployed. **Do:** before deploying, the
  live Skald's render test for skaldanalytics.com must accept `/css/`, `/js/` and `/fonts/`
  as page assets, or real visits to the new pages may count as bots. Prices still show
  "Proposed prices, not final yet" (`PRICES_PROPOSED` in `_src/conf.py`).
- **Checked:** the build ends "problems: none" (one H1, title and description lengths, dead
  links, banned claims); the site's tests (one browser test of the check page's agency mode fails
  now and then, on the last commit too); the full test suite; every sitemap URL opened at 1440 and 390 px wide
  (no sideways scroll, no script errors, no broken assets, every switch and tab has a choice).
  Words checked against the product's own limits (`_src/pages/FEATURES.md`).

## 2.37.0 (2026-10-25)

Ask your AI assistant what to fix: six read-only MCP tools for the to-dos, lost pages, page changes, AI readiness and what changed. Also: the live visitor count readable again, a command reference, docs that match 2.36, and release notes on every GitHub release.

### Upgrade

- Nothing to do. The MCP server lists the new tools by itself; an assistant connected before sees them after it reconnects.

### MCP: six read-only tools for what to fix and whether it worked

- **Added.** The MCP server answers what 2.35's screens show: `what_changed` (Summary's "What
  changed: is it working?": sources and landing pages against the period before, only when both
  periods are whole), `todos` (Insights' to-do list with each to-do's state: to do, marked done
  with its re-check, or not now; `id` gives one to-do's rows), `lost_pages` (Site › Not found:
  old addresses, the closest live page, the nginx or Apache line; the Markdown copies AI asked
  for; the addresses marked fixed), `page_changes` (each marked change and the before/after
  verdict of every measure), `ai_readiness` (Pages AI can't read well, or one page's robots.txt
  per AI crawler, what AI got back, the Markdown copy, the sitemap and the last AI read) and
  `changed_pages` (New and updated pages: are they getting found?). They read todos.json,
  lost_pages.json, page_changes.json, ai_ready.json, page_trends.json, overview.json and
  breakdowns.json as the page does and count nothing again; a figure withheld or not recorded is
  named and null, never 0. The same token rules as every tool: the `mcp` scope, the sites the
  token may read, no address. **Why:** the read-only API already served these files, but an AI
  assistant asked "what should we fix?" or "did my change work?" had no tool for them. **Who:**
  anyone with an MCP token. **Do:** nothing; an assistant sees the new tools on its next
  `tools/list`. **Checked:** `tests/test_mcp_insights.py` (each tool on hand-made files in the
  builders' shapes: compared only over whole periods, the not-measured period, lists that do not
  add up withheld, withheld to-dos and lost pages named, a path with or without its slash,
  robots.txt not known without a copy, a site the caller may not read refused by every new tool);
  the protocol and transport tests list 20 tools; every tool run over a freshly built demo.
- **Docs.** docs/MCP.md, the MCP and API help guides, docs/API.md (every data file the API
  serves, among them todos, lost_pages, page_changes, ai_ready and page_trends, and the Real
  time route), LEADS-REFERENCE.md and the README name the 20 tools.

### GitHub page: 2.36 in the README, 39 screenshots retaken and 2 new; the live visitor count shows full size again

- **Changed.** The public README names 2.36 (one summary mail a day, the HTML sitemap page not a
  page) in What's new and the feature list, and the gallery gains two images: Site › Data quality
  with "Not counted as pages" (`data-quality.png`) and the daily summary mail (`summary-mail.png`,
  the real `summary-mail --dry-run` text of the sample install). 39 older images, most from the
  2.22 demo, were retaken from the current build: Security › Alerts now shows "In the daily
  summary" or "Right away"; Traffic › Sources shows the Social network tab and Direct, likely.
  **Why:** the images showed version 2.22 and screens that have changed since.
- **Changed.** The demo's sample traffic has an HTML sitemap page (`/sitemap/`), walked by
  Googlebot, bingbot, a weekly SEO site audit and now and then a test browser, from a generator of
  its own, so every other figure stays the same and Data quality has something to show.
- **Fixed.** Overview, today: the number of visitors on the site now showed as a small grey dot
  since 2.35.0, because the to-do number's style (`.td-n` in `todos.css`) also matched the live
  count. It is now kept to the to-do cards. **Who:** everyone looking at today's Overview.
  **Do:** nothing.
- **Checked.** `tests/test_demo.py` (the sitemap page is walked and shows in Data quality, never in
  Pages; the rest of the traffic unchanged); the full test suite passes; every new image looked at
  against the README's text, sample data only (RFC 5737 addresses, example.com).

### Docs: a command reference, and every Docker setting

- **Added.** docs/CLI.md lists every command and every argument, written from the command
  parser itself, so it cannot fall behind: a test fails when a command or a flag is added
  without it. The README's command list gained the commands it left out (`summary-mail`,
  `settings`, `ours`, `search`, `reports`, `ai-answers`, `stack`, `views`). docs/INSTALL.md now
  names every environment setting the Docker image reads, among them `SKALD_SCHEDULE_TZ`,
  `SKALD_MAIL_FROM` and `SKALD_CONFIG`, and lists the scheduler's jobs with their times
  (the daily summary at `SKALD_SUMMARY_AT` among them). **Why:** about twenty commands and flags,
  and several Docker settings, were written down nowhere but the code. **Who:** anyone who runs
  Skald. **Do:** nothing. **Checked:** `tests/test_cli_reference.py` (every command and argument
  of the parser is in its section; the file is what the tool writes); each setting checked
  against the entrypoint and the scheduler.

### Docs: the data contracts match 2.36

- **Fixed.** The not-a-page entry `sitemap_page` (2.36) was missing from the Requests feed's
  `not_page` values and from the `site.not_pages_off` setting's list, and the counting-traps
  page still said an HTML sitemap page stays a page. The set-up routes table gained
  `sites/detect`, `sites/tagcheck` and `sites/trylog` (Test a sample: what it takes, what its
  report holds, its limits). The to-do contract gained the helper's `settings/todos` and
  `settings/todo-send` routes. The advisories list's `also_known_as` and `firewall_notes`
  fields are described. The `arw` address key named a "redirects" filter the page does not
  have; it is "slow". The Not found help called the download button "Download the lines"; the
  page says "Download the nginx lines" (or Apache). The comparison's notes on 404s, email alerts
  and chart markers now name Lost pages, the security and sale alerts with the daily summary,
  and marked page changes. **Why:** these docs had fallen behind 2.35 and 2.36. **Who:** anyone who
  reads the files or calls the routes. **Do:** nothing. **Checked:** every field of a freshly
  built demo's data files looked up in its contract; every setting key in the settings
  reference; each route against its code.

### GitHub releases carry their notes

- **Changed.** Every GitHub release page said only "See CHANGELOG.md for what changed." The
  release workflow now writes the version's own changelog section into its release, with a link
  to the full notes; the 58 existing releases (2.0.0 to 2.36.1) were filled the same way, once,
  by hand. **Why:** the owner asked for the release notes on GitHub. **Do:** nothing.
  **Checked:** the workflow's step run on the changelog gives 2.36.1's section; each release
  page read back after the edit.

## 2.36.1 (2026-10-25)

A fix found by the dry run of the first summary mail on the live server.

### Mail links open the site they are about

- **Fixed.** In an install with several sites, a site that sets no `dashboard.url` of its own
  took the first site's, so every link in its mails (the security alerts, the daily summary,
  the daily and weekly reports, alert mails, a to-do sent to a teammate) opened the first
  site's dashboard. Each site now gets the first site's address with its own name in place of
  the first site's last segment (`.../traffic/example.com/` becomes `.../traffic/example.org/`).
  A site with its own `dashboard.url` keeps it; an address that does not end with the first
  site's name is left as it is.
- **Why.** The dry run of the 2.36.0 summary showed every site's links opening the first site.
  The 2.35.0 security mails had the same wrong links.
- **Who.** Installs with more than one site. **Do:** nothing.
- **Checked.** New tests (inherited, own, other shapes, the first site unchanged); the full
  test suite passes; `summary-mail --dry-run` on the live server after the upgrade.

## 2.36.0 (2026-10-25)

One summary mail a day instead of a mail per security item, and the HTML sitemap page out of the page views.

### Upgrade

- Docker: nothing; the scheduler sends the summary at 01:00 (`SKALD_SUMMARY_AT`). Without Docker: add the hourly `summary-mail --after 01:00` cron line (DEPLOY.md section 5).
- Recount the stored days so the sitemap page leaves them: `backfill --days 14 --force`, then `audit --day D --withhold` for each day.

### Counting: an HTML sitemap page is not a page any more

- **Changed.** `/sitemap/`, `/site-map/`, `/html-sitemap/` and `/sitemap.html` joined the
  not-a-page list as `sitemap_page`, ticked by default on every site. Its visits stay in the
  log's requests, in the same group, and show in Site health > Data quality under "Not
  counted as pages"; they leave the page views, readers, landings, exits and journeys.
- **Why.** The owner saw `/sitemap/` among one client site's people's pages: "a user never
  looks at" it. That day's log had 45 requests for it: Googlebot, PetalBot, Amazonbot, an SEO
  site audit, a "research-check" tool and four browser signatures with no referrer. The last
  four were counted as people. 2.35.0 had kept the HTML sitemap page as a page on purpose; this
  reverses that call.
- **Who it affects.** Every site with an HTML sitemap page. A site that wants it counted again
  unticks `sitemap_page` in Settings > Sites > Not pages.
- **What to do.** Nothing. Stored days keep their figures until recounted
  (`backfill --days N --force`); the live server is recounted at deploy.
- **Checked.** Tests on both counting roads (the audit matches the same list by its own code):
  matches, near misses (`/sitemaps-guide/`, `/sitemap/page-2/`, `/my-sitemap/`) and the
  made-up sitemap of 400+ paths, which still matches nothing.

### One summary mail a day per person, at 01:00, instead of one security mail per item

- **Changed.** Each person's security mail now comes by default in a daily summary: one mail
  per person a day at 01:00 in the schedule's time zone, covering every site they get security
  alerts for, with a section per site (only sites with something open): the open security
  items (marked New the first time, then "still open"), the open to-dos from Overview ›
  Insights (less the ones marked done or "not now"), and the set-up problems the doctor finds
  from local files (the daily run, days stored, the access log, the script tag, hooks, crawler
  checks, the disk). At most 10 lines per part and site, then a link to the rest; each line says
  what it is, what to do and links straight to it. No mail when nothing is open; never two the
  same day (each send is recorded, a failed one is retried by the next run). At 01:00 the to-dos
  are the ones the last daily run found; the security items are current from the live runs.
  A new command `summary-mail` (`--dry-run` prints the mails; `--after HH:MM` for an hourly
  cron line); Docker runs it at `SKALD_SUMMARY_AT` (default `01:00`, `off` stops it).
- **Changed.** "Right away" stays as a person's own choice, but one run now sends ONE mail per
  person with every item due on all their sites, never one mail per item. The morning run's
  separate security mail step no longer mails anyone; it only keeps the open items up to date.
  Security › Alerts, "Your security alerts", now offers "In the daily summary" (first, the
  default) or "Right away", and says what each sends.
- **Why:** on 2026-10-25 one person got 44 security mails in a minute: the first run after a
  fix sent every open item, one mail per item and per site, across 6 sites.
- **Who:** everyone on a site's team with security alerts on (owners and admins by default).
  Someone who had saved "Right away" keeps it, now batched.
- **Do:** nothing on Docker (the scheduler runs it). Without Docker, add the hourly
  `summary-mail --after 01:00` cron line (DEPLOY.md section 5; `install.sh` now writes it).
  To keep a mail per run, choose "Right away" on Security › Alerts.
- **Checked:** new tests for one mail per person across several sites and organisations,
  nothing sent when nothing is open, not sent twice the same day, a failed send retried, the
  10-line limit, the doctor lines read without any network call, right away batched into one
  mail, the old daily step mailing nobody, and the scheduler's job time and `off`; the
  existing security alert tests updated; the full test suite passes.

## Older versions

- 2.35.0 and 2.35.1 (25 October 2026): [docs/CHANGELOG-2.35.md](docs/CHANGELOG-2.35.md).
- 2.32.0 to 2.34.1 (24 and 25 October 2026): [docs/CHANGELOG-2.32-2.34.md](docs/CHANGELOG-2.32-2.34.md).
- 2.27.0 to 2.31.1 (22 to 24 October 2026): [docs/CHANGELOG-2.27-2.31.md](docs/CHANGELOG-2.27-2.31.md).
- 2.23.0 to 2.26.0 (22 October 2026): [docs/CHANGELOG-2.23-2.26.md](docs/CHANGELOG-2.23-2.26.md).
- 2.21.0 to 2.22.3 (21 and 22 October 2026): [docs/CHANGELOG-2.21-2.22.md](docs/CHANGELOG-2.21-2.22.md).
- 2.14.0 to 2.20.1 (18 to 21 October 2026): [docs/CHANGELOG-2.14-2.20.md](docs/CHANGELOG-2.14-2.20.md).
- 2.8.0 to 2.13.0 (18 October 2026): [docs/CHANGELOG-2.8-2.13.md](docs/CHANGELOG-2.8-2.13.md).
- 2.7.1 and earlier (8 to 12 October 2026): [docs/CHANGELOG-2.0-2.7.md](docs/CHANGELOG-2.0-2.7.md).
