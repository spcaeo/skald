# Changelog

All notable changes to Skald. Dates are UTC. Versions follow [Semantic Versioning](https://semver.org).

## Unreleased

Everything under Unreleased is live on skaldanalytics.com, except the entries marked "not live yet" or "not released yet": the first two website entries since 26 Oct 2026, 18:03 UTC, the rest since 11:44 UTC (the website only; no new Skald version).

### Website: the MCP pages say 22 tools; What's new has 2.39

- **Changed.** The MCP page, the features page, the developers pages, /for/ and the Searchable
  comparison say the MCP server has 22 tools: 21 read-only, and `setup_line`, which makes a
  set-up line only with a token that has the `setup` scope. The MCP page lists `setup_left` and
  `setup_line`, and no longer lists six tools twice (what_changed to changed_pages were in its
  tool list two times). What's new has 2.39. **Why:** 2.39.0 added the two tools. **Who:**
  readers of skaldanalytics.com. **Do:** nothing. **Checked:** the build says "problems: none".

### Website: a JetOctopus comparison page; /compare/ lists 14 tools

Not live yet: built and committed, waiting for the owner's go to upload the website.

- **Added.** /compare/jetoctopus/: Skald beside JetOctopus, a technical SEO platform that crawls
  large sites and reads their server logs for Googlebot and AI crawlers. Eleven questions
  answered side by side, each JetOctopus answer linked to its own page (how it gets the log,
  which lines it keeps, how it checks a Googlebot is real, how fresh, what pages exist, people,
  search data, MCP, alerts, cost); an echo sounder hero (seven sample pages by crawl depth
  beside the same pages as Skald reads them) and a postage meter that feeds ten sample lines
  through each tool's monthly "log lines" quota (theirs meters checked search bot HTML pages,
  2 of 10; Skald counts all 10). It says where JetOctopus does more (its own crawler with
  JavaScript rendering, Search Console and GA4 joined per page, an MCP server that can start
  crawls, unlimited seats) and how to run both. Prices only as listed on jetoctopus.com/pricing
  on 26 Oct 2026, with that date. **Changed.** /compare/ lists JetOctopus (picker, glance table,
  the hero's server-log column) and now says 14 tools; the GoAccess and crawl health pages link
  to the new page; docs/COMPARISON.md has a JetOctopus entry under "Also checked" with sources,
  and the public README's "Who should use what" names it for crawling and technical SEO. A
  private gap note (docs/marketing/) records what it does that Skald does not, its prices and
  what to re-read. **Why:** the owner asked to add JetOctopus to the tracked competitors; it is
  the nearest one so far, since it reads the same logs Skald reads. **Who:** readers of
  skaldanalytics.com and of the README. **Do:** nothing. **Checked:** every JetOctopus claim read
  on its own site, docs, pricing page (rendered in a browser, both tabs and both billing
  periods) and FAQ on 26 Oct 2026, paraphrased, no quote of 15 words or more; where its pages
  disagree (Shopify logs, the trial's demo call, log-line limits) the page follows the current
  pricing page and the gap note marks the rest "?"; every Skald claim matched to the code (nine
  owners' crawlers checked, sitemap daily and robots.txt hourly, Search Console every 6 hours,
  20 read-only MCP tools, the hosted plans); a separate grader scored the page 83/90 and its
  fixes were applied (MCP pause wording, GA4 wording, terms explained); the build ends
  "problems: none"; the unit tests pass; /compare/, /compare/jetoctopus/, /compare/goaccess/ and
  the crawl health page at 390 and 1440 px show no sideways scroll; all 19 outside links answer
  200 after redirects.

### Website: hosted prices are final, and each plan says its limits

- **Changed.** /pricing/ no longer says the prices are proposed ($9 Starter, $49 Team, $149
  Agency, 20% off yearly: the owner's prices, now final). Each plan lists its limits: requests a
  month shared by its sites (1 million, 5 million, 20 million), team members (3, 10, unlimited)
  and days of detail kept (400, 400, 800). Enterprise is more than 25 sites or 20 million
  requests a month; it used to say "about 1 million visits", a unit Skald does not measure. Going
  over never stops the counting or drops a line; after two months over in a row we ask the
  customer to move up. The integrations, MCP, API, Slack, "for" and agencies pages dropped
  "as proposed until launch". Why: the owner set the prices live and asked for limits in the
  style of telltale.bot's plans, after a gap analysis (kept privately). Who it affects: anyone
  reading the pricing page; nobody pays yet (trials are set up by a person). What to do:
  nothing. **Checked:** the limits are the ones the hosted plan settings carry (sites, requests a
  month, members, days kept); the build says "problems: none"; the page at 1440 and 390 px.

### Website: the author page has Rakesh's photo and profiles; contact says 2 working days and offers a call

- **Changed.** /author/rakesh-patel/ shows his photo (the headshot from his Space-O author page),
  his role as founder and CEO of Space-O Technologies since 2010, 28+ years in IT, his two books,
  and links to his LinkedIn, X, Facebook and rakeshpatel.co (from that site's footer); its
  `Person` data now carries the photo and those profiles (`sameAs`). Why: the page showed only
  initials, and search engines had no profile to tie the notes to. **Added.** /contact/ and the
  author page offer a Zoom call with Rakesh (his Calendly, US Eastern), and /contact/ says replies
  come within 2 working days (the owner's promise). Who it affects: readers of
  skaldanalytics.com. What to do: nothing. **Checked:** every new link answers 200; both pages at
  390 and 1440 px with no sideways scroll; the build says "problems: none".

### Website: five new comparison pages for AI visibility tools; /compare/ lists 13 tools

- **Added.** Five pages: /compare/searchable/, /compare/profound/, /compare/peec-ai/,
  /compare/otterly/ and /compare/promptwatch/. Each takes a reader's questions one by one (how
  the tool gets AI answers, which crawlers it keeps, how it checks a crawler is real, what
  follows the click, what it costs), with the tool's answer quoted from its own page or docs
  and linked, and Skald's answer beside it. Each says where the other tool does more than
  Skald, and how to use both. Prices are shown only as listed on the tool's own pricing page
  on 26 Oct 2026, with that date and the link. **Changed.** /compare/ now lists 13 tools
  (the five new ones as AI visibility tools, beside the eight it had), the eight older
  comparison pages link "every comparison", and docs/COMPARISON.md and the public README name
  the five as hosted AI visibility services. **Why:** the home page names Profound and Peec AI
  with no page of their own, and people ask how Skald differs from these tools. **Who:**
  readers of skaldanalytics.com and of the README. **Do:** nothing. **Checked:** every claim
  about each tool was read again on its own site and docs on 26 Oct 2026, and wording the
  pages did not support was cut or reworded (an Otterly quote corrected, "signed" dropped from
  forms, which Skald does not sign); every Skald claim was matched to the code or docs (40 AI
  crawler names, nine owners' crawlers checked by address, 50 questions with 1 to 5 tries,
  180 days kept, 20 read-only MCP tools); the build ends "problems: none"; the unit tests
  pass; the six pages at 390 and 1440 px show no sideways scroll and no console error other
  than the site's own script, which only the live server serves; all 65 outside links answer
  200 after redirects. The rubric grades in `_src/pages/RUBRIC.md` were not redone after the
  rewording. **Second audit (same day, by a separate session):** Searchable's rendered pricing
  page lists ten engines with Claude and Meta Muse as paid add-ons, agency plans (Launch $250,
  Growth $400, Enterprise Agencies from $999) and unlimited projects only from Enterprise, so
  the page, hub and COMPARISON.md now say so; Profound's agency workspace add-on ($399 a month)
  added and Amazon moved out of its "Partially Verified" examples (its docs list Amazon as
  fully verified); quotes over 15 words shortened (Searchable, Peec AI, hub); Promptwatch's
  address check limited to providers that publish ranges; Skald's prompt limit is 50
  questions per tracking profile (up to 10), its address check named as nine owners wherever a
  line said "where the owner publishes", its AI readiness check acknowledged on the Otterly
  page, AI Mode clicks named only when udm=50 is present; repeated sentences between pages
  reworded; three FAQ answers now lead with the answer.

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

## 2.40.0 (2026-10-26)

Settings is rebuilt around what you came to do: a menu in five groups (This site, AI & API, Organisation, You, Help & docs), a page per task, and Help and Docs under every title; every old address still works. Each site has a menu to pause, remove, clear or delete it, with an archive written first. Hosted plans mail owners and admins at 80%, 90% and 100% of the month's requests. A site can keep everything: on internal and enterprise sites Skald deletes nothing by itself. Leads' names and emails follow the site's own People days on every other site.

### Upgrade

- **Read this before you upgrade if you set People days and want nothing cleared.** The first
  run on 2.40.0 clears the names and emails of leads older than a site's People days (the Fixed
  entry below). To keep everything, add `SKALD_KEEP_EVERYTHING=1` to the container's env file
  (or `retention.keep_everything: true` in config.yml) **before** the new container starts.
  A site with no People days set changes nothing.
- Bookmarks and links to old Settings addresses (`#settings/api`, `#settings/sitesadmin` and the
  rest) keep working: they open the new page, with their dialog.

### Settings: a menu by what you came to do, a page per task, Help and Docs on every page

- **Changed.** Settings has a menu of its own, in five groups: **This site** (Set-up checklist,
  Collect data, Site details, Leads & integrations, Internal traffic, Privacy & retention, Mail &
  reports, AI answers), **AI & API** (AI assistant (MCP), Read figures (API), Tokens & links),
  **Organisation** (Sites, Team, Users, Sign-in rules, Audit log, Billing & usage), **You** (Your
  account) and **Help & docs**. `#settings` opens **All settings**: the common tasks in plain
  words ("Connect an AI assistant", "Add, pause or delete a site", "Revoke a token") and every
  page with one line on what it is for. On a phone each page starts with a **Settings page**
  select, so the menu is one tap away. Long pages have tabs (Collect data: Send logs, Script tag
  & goals, What counts; Leads & integrations; Mail & reports; AI answers), each with its own
  address (`sub=`). The old Connections page is split by task: sending logs is under Collect
  data, MCP and the API have pages of their own, and every token and shared link is under Tokens
  & links.
- **Changed.** The MCP and API pages say how it works first, as four numbered steps, then one
  button. In the MCP dialog, by hand, one step holds it all in order: choose your assistant
  (Claude Code, Claude Desktop, ChatGPT through the API, other), make its token right there, then
  the command or config with the token already in it. The API dialog shows the curl command
  under the token it made. Each Test names the next step. The assistant chosen is in the address
  (`asst=`); the token never is.
- **Added.** Every settings page and tab has **Help** (its guide in the app) and **Docs** (the
  same guide on skaldanalytics.com/docs/, in a new tab, with the copy and open icons) under its
  title, and a **Next step** at its foot. A **Help & docs** page lists every guide, the public
  docs, the MCP and API pages, What's new and the contact page. Ctrl K (Cmd K) finds MCP, API,
  tokens, sites and Help & docs by those words.
- **Why.** The owner (26 Oct 2026): "every option in settings ... is super confusing and also
  not as per user flows ... the token was above the steps ... i could not find where the mcp
  was in ... the help and documents are not easy to access". The pages were a flat list of 15
  named by what they held, not by what people came to do.
- **Who.** Everyone who opens Settings. Nothing changes in what each setting does or who may
  change it.
- **Do.** Nothing. Every old address still works and opens the new page with its parameters:
  `#settings/api?conn=mcp` opens AI assistant (MCP) with its dialog, `#settings/sitesadmin?setup=new`
  Sites with the wizard, `#settings/account` Your account, and so on (docs/ROUTES.md lists
  them all). Links in mails sent before still land.
- **Checked.** A new node test (tests/js/settings-menu.mjs): the groups and their order, every
  page drawn with Help and Docs (copy and open icons), one title, the phone's select, Next step,
  each tab in the address, every old address opening its new home with its parameters. The
  connection, route and agent tests walk the new pages and the reordered MCP dialog (choose,
  token, command, then Test; the assistant in the address and gone on close). The help guides,
  mails, kit files and CLI words name the new pages. Screenshots before and after at 1440 and
  390 px, light and dark (docs/plans/settings-shots/), with no sideways scroll at 390 px. The
  full suite passes.

### Hosted plans: a mail at 80%, 90% and 100% of the month's requests

- **Added.** When an organisation's requests this month reach 80%, 90% and 100% of its plan's
  `requests_month`, its owners and admins get one mail each: "X of the Y requests its plan
  allows this month (Z%)", the day the count starts again, what happens past the limit (new log
  lines turned away; Skald's shipper keeps them and sends them again, a Cloudflare Worker's are
  lost) and an **Open Billing** button to Settings > Billing on that organisation's own
  dashboard. One mail per mark and month, never twice: each mark is written before the send
  (decision D93's rule), so a restart, a recount or a second run repeats nothing. A jump past
  two marks sends one mail, for the higher; a bigger plan in the month starts from its own marks
  not yet passed. From 80%, owners and admins also see a banner on every page with a link to
  `#settings/billing`; viewers see nothing. Settings > Billing shows the month's requests as a
  bar with the 80, 90 and 100 marks, and admins may now read Billing (only owners choose a plan
  or change the payment). Each alert is one `billing.usage_alert` row in the audit log, with the
  mark and the counts, never an address. `/me`'s plan usage gains `percent`, `mark` and
  `resets_on`. The check runs after every live run and run-daily, at most once per organisation
  every 5 minutes (run-daily always), never inside an ingest request. `saas.usage_alerts: false`
  switches the mails and the banner off.
- **Why.** The owner: "we also send alerts to upgrade your plan when you reach 80%, 90%, 100% so
  that your data is not lost". Past the limit the ingest answers 429, and nobody was warned
  before; a Cloudflare Worker's lines are lost then.
- **Who.** Hosted Skald (saas on) only: owners and admins of an organisation whose plan has a
  `requests_month`. Self-hosted installs (saas off) see no change, and no table is made.
- **Do.** Nothing: on by default with saas, through the install's own mail settings.
  `saas.usage_alerts: false` turns it off.
- **Checked.** New tests: each mark once, a jump past two, a new month, a bigger plan and one a
  little bigger, back to the old plan, a restart, a recount down and up, a failed send, saas
  off, the switch, no plan or no `requests_month`, unknown or withheld usage, viewers and
  unconfirmed or disabled accounts never mailed, the link on each organisation's own dashboard,
  one check per 5 minutes; over real HTTP, /me's new fields and Billing for an admin (read
  only); and the banner and bar drawn in node from those answers (tests/js/billing-usage.mjs).
  The full suite passes.

### Added: keep everything, for internal and enterprise sites

- **Added.** A site can keep everything: Skald then deletes and clears nothing by itself on it.
  It applies when the install says so (`retention.keep_everything: true`, Docker
  `SKALD_KEEP_EVERYTHING=1`), or, on a server that sells plans, when the site's organisation
  has no plan (the server's own) or its plan says `keep_everything: true` (Enterprise). Every
  automatic delete skips such a site: the history's journeys, returning-visitor codes, detail
  and AI fetches; visits with addresses and Security's scanner rows (by days, and when
  addresses are turned off or shortened); leads, removed rows, lead journeys, identities,
  deliveries, replay hashes and payment links; the hook spool; the People-days clearing of
  names and emails (the entry below); the outgoing webhooks' outbox; in-page event counts and
  the beacon spool; AI answers runs; closed alerts; the conversions file's backup copies;
  and the shipped raw logs, whose days past 14 move to the site's `archive/` folder instead of
  being deleted (about 11 MB a day for every site on our server). A person's own deletion request (`forget`, `conversions forget`), run by an admin,
  still works. Settings > Data retention and its People card say "Kept: nothing is deleted
  (internal or enterprise).", a shorter window's preview says nothing is removed, the privacy
  notice wording says "until you ask us to delete it", and `ti.py doctor` shows "Keep
  everything: on". **Why:** the owner's rule of 2026-10-26: "all our projects that we have on
  live are internal and enterprise, nothing gets deleted on that". **Who:** our server (every
  site on it, once `SKALD_KEEP_EVERYTHING=1` is in its env file) and Enterprise plans; a
  customer plan's sites and every other install are pruned as before. **Do:** on our server,
  add `SKALD_KEEP_EVERYTHING=1` to the env file at the upgrade that ships this, before the
  container starts, so the People-days sweep below never runs there; give an Enterprise plan
  `keep_everything: true`. The history's own backups (copies, not data) still rotate. **Checked:** `tests/test_keep_everything.py`: every prune of the daily
  run on a keep-everything install leaves every table row and every file byte for byte as it
  was; the same install with the rule off is pruned; hosted, a site with no plan and an
  Enterprise site are untouched while a customer plan's site is pruned; the outbox, closed
  alerts, AI answers, conversions backups and the People-days sweep each kept and, with the
  rule off, cleared; `tests/test_ingest.py`: a raw log past its 14 days lands in `archive/`,
  whole, outside run-daily's files; the notice, the env var and the plan flag.

### Fixed: leads' names and emails kept past the site's own promise

- **Fixed.** A site sets in Settings > Data retention > People how many days it keeps what
  names a person (**Visits with addresses**, `privacy.keep_days`). That number covered only the
  visits with IP addresses. A lead's name and email lived as long as the lead: 400 days, or for
  good. Now, when a site has set its People days and they are shorter than the leads, a name
  and email are kept that many days. Then they are cleared from every place Skald keeps them:
  the lead's identity, the leads a sync removed, the copy of each hook message, and the copies
  a schema upgrade keeps (`conversions/people_days.py`). The lead stays, counted, without them.
  If the same person sent a newer form, the newer lead keeps the email; the older leads lose
  it. A start and its finish within the abandonment window stay linked, so no lead ever
  becomes "abandoned". The privacy notice wording now says it: "We keep them for 180 days.
  After that we keep the form or booking without your name and email, ...". **Why:** the
  2026-10-26 security review: docomatic.ai promises 180 days, and its emails were kept for
  good. **Who:** sites that keep names and emails and set People days shorter than their
  leads. A site that never set People days keeps today's rule: the code's 395 is not a
  promise. A site that keeps everything (the entry above) is never cleared: on our server,
  where docomatic.ai promises 180 days and two more sites 365, nothing is cleared once
  `SKALD_KEEP_EVERYTHING=1` is set.
  **Do:** nothing. The first live run after the upgrade clears what is already past the
  promise, then the nightly run each day. Each site's counts go to the run's output,
  `privacy.log` and the audit log (`privacy.cleared`), never a name or an email. A site whose
  notice promises a number of days should set it under People. **Checked:**
  `tests/test_people_days.py` (old rows lose name and email, young keep them; a person with a
  new and an old lead; a start chained to its finish across the edge; removed rows, spool lines
  and upgrade copies; no change without a shorter promise; once after the upgrade; the
  command's counts never show an email). `conversions.json` for April and today, the second
  count included, and the abandoned starts are the same before and after; with the chain
  turned off the test sees a lead turn "abandoned", so the check is real.

### Pause, remove, clear or delete a site from the dashboard

- **Added.** Each site in Settings > Add or remove sites has a ⋯ menu: **Pause** and
  **Resume** (an owner or an admin), **Remove** and **Restore**, **Clear data** and **Delete
  all data** (an owner). Each opens a dialog that says what happens, what stays and how to
  undo it; the dialog is in the address (`sact=<act>.<site>`). Pause comes first and deletes
  nothing: the log endpoint answers 503 with Retry-After, so the shipper keeps its lines, and
  the daily and live runs skip the site; the site shows "Paused since". Resume says how many
  days were missed and whether the log can still fill them (a shipper kept its lines, a log
  drain did not, a local log holds days from a date). Removed sites are listed apart, with
  Restore. Clear data and Delete all data need the site's name typed and a box ticked; before
  deleting anything they write one archive of everything that goes into the install's backups
  folder, kept 30 days, and show its path. Clear data keeps the site, its settings and its
  tokens; the days before it read Not recorded and are never counted again. Delete all data
  also deletes settings, set-up links and the logo, and revokes the site's tokens; a site from
  the server's config file keeps its config entry and becomes Removed. All of this works for
  config-file sites too (the install's main site can only be paused). One audit row per
  action (the site, who, the archive's name). New commands: `ti.py site pause|resume|restore|
  clear`; `site remove` and `site purge` now work on config-file sites and `purge` on an
  active site, both still with `--yes`. **Fixed.** A purge left the site's page-group rows
  (`<site>::<view>`) in the history, its AI answers, its security items, its set-up links and
  its Search sync state; it now takes every one (`site_data.py` lists each store).
  **Why:** the owner found no way to delete a website he had added, or to clear its data.
  **Who:** owners and admins of every install. **Do:** nothing. **Checked:**
  tests/test_site_lifecycle.py (pause stops ingest and the runs, resume restarts them, remove
  and restore, purge writes the archive then empties every store, clear keeps settings and
  tokens, roles, the typed name and the tick, config-file sites, audit rows, paused and cleared
  days read Not recorded), tests/js/site-actions.mjs (the menu per role, the dialog's words,
  the address, nothing posted until the name is typed and the box ticked), and the full suite.

## 2.39.0 (2026-10-26)

Your AI agent can now do every set-up job, not only a new site's. Each Set up dialog asks **Your AI agent, or by hand?**, the set-up list offers **Set up everything left with your AI agent**, and your assistant can ask Skald over MCP what is left and make the line itself. Also: the agent's findings for Skald's own settings wait for your **Apply**; a tie in a list's "(all others)" cut no longer withholds a day; a quiet site no longer shows a false "no page assets".

### Upgrade

- Nothing to do on the Docker image. A self-hosted install with its **own front nginx that allows only GET** under `/traffic-kit/` must also allow POST to `.../hooksecret`, as it already does for `.../report` (DEPLOY.md, the regex `(report|hooksecret)`). A front nginx that only proxies needs nothing.

### Your AI agent, in every set-up job

- **Added.** The one line for an AI agent works for each set-up job of a site already in Skald:
  connect the logs, add the script tag, leads and tool webhooks, the Next.js log field, find the
  page assets, check the privacy settings, and connect the AI assistant (MCP). Every Set up
  dialog an agent can do (logs, page assets, Next.js pages, script tag, lead hook, privacy, and
  Connect an AI assistant) opens on **Your AI agent, or by hand?**; by hand is the old dialog,
  one step later. Countries and mail stay by hand. **Why:** the owner pointed out that the lead
  set-up (`?setup=lead`) walked a person through by hand while Add a site did it all through one
  line. **Who:** owners and admins. **Do:** nothing. **Checked:** `tests/js/agent-jobs.mjs` and the
  checklist and connections tests; the default Add a site line, keys and steps are byte for byte
  as before.
- **Added.** **Set up everything left with your AI agent** at the top of a site's Set up list,
  when two or more open lines are agent jobs: one line for all of them. Its address is
  `setup=all&jobs=...`. **Checked:** `agent-jobs.mjs` (jobs in order, the address round trip).
- **Changed.** A line makes only the keys its jobs need: a sending token only with logs, the lead
  secret only with leads, a read-only token for that one site only with MCP. Cancelling, expiry
  or a new line revokes every token the line made. **Checked:** endpoint tests on cancel, expiry,
  a revoke that failed once, and the daily run.
- **Changed.** The agent's steps give each job its own section, each starting with **Check
  first**: the agent leaves done work alone, changes only what is missing, and asks before any
  server or web-server change. Keys still go only into a 0600 file through curl or wget.
- **Added.** `POST /traffic-kit/<code>/hooksecret` lets the agent set a booking, form or payment
  tool's webhook secret (Calendly, Cal.com, Typeform, Stripe, HubSpot, Zapier) without the
  secret passing through the chat: Skald makes one and hands it once into a file, or takes the
  tool's own from stdin. A tool that has a secret already is left alone unless replacing is
  asked. Audited, never logged. **Checked:** tests run the steps' own commands with bash and curl.
- **Added.** The agent's report says which jobs it did ("done", "already there", "skipped",
  "left for you") and which tool hooks it set. Page assets and privacy show as recommendations
  with **Apply**, which makes the same save as the by-hand dialogs. **Why:** a leaked code must
  never change what Skald keeps; Skald changes its own settings only on your press. **Checked:**
  nothing is saved before the press; the exact save bodies after.
- **Changed.** Connect an AI assistant (MCP) has **Read the MCP guide** at the top. **Why:** the
  owner found no documentation link there.

### MCP: what is left to set up, and the line to do it

- **Added.** `setup_left`: a site's open set-up lines, each with the job an agent can do and
  its dialog's address. Worked out on the server (`setup_items.py`), held to the page's own
  checklist by a test that runs both on 22 sets of answers.
- **Added.** `setup_line`: makes the same one-time line as the dashboard's **Your AI agent**, for
  the jobs given, audited (never the code). It needs a token with the new permission
  **Set-up lines (AI agent)** (scope `setup`): only an owner or admin may make it, for exactly
  one site, together with AI assistant (MCP); it reads nothing by itself, and stops if its maker
  is demoted. **Do:** make such a token only if you want your assistant to start set-ups.
  **Checked:** `tests/test_mcp_setup.py` (every refusal, the audit row, a real line end to end).
- **Fixed.** The MCP server reads each site's own config for set-up answers, not the main
  site's.

### Fixed: a tie at the "(all others)" cut withheld a live panel

- **Fixed.** A list that ends in "(all others)" keeps the pages with the most visits. When
  several pages had the same count at the cut, it kept whichever it had counted first. The
  visits and the readers count in a different order, so the two lists could keep different
  pages, the check "visits by entries match readers by landing" failed, and the figures were
  withheld. Now, at an equal count, the first by name is kept, whatever order the lines came in
  (`dimensions.fold`; rule added to DATA-CONTRACT.md, Counters). **Why:** one site's live panel
  was withheld on 26 Oct (19 landing pages with one reader each, the cut inside them). **Who:**
  every site; a day or live panel could be withheld. **Do:** nothing: no stored day was withheld
  for this, nothing needs recounting. **Checked:** `tests/test_landing_ties.py` rebuilds the case
  (failed before, passes now); the day's real lines, read on the server without writing, verify
  clean with the new rule; the audit road does not fold and is unchanged.

### Fixed: a quiet site's "no page assets" false alarm

- **Fixed.** The doctor's Page assets line read only the log's last 512 KB. On a quiet site
  those can all be crawler lines, so it said "no request for /_next/static/" while people loaded
  the pages all day, and the set-up checklist offered a wrong to-do ("none counts as a person
  yet"). With nothing in the tail it now reads further back, the live file and its first
  rotation, 64 MB at most, and says "seen in the log (not in its last lines: a quiet spell)"
  (`doctor.py`). **Why:** docomatic.ai showed the false alarm. **Who:** quiet sites with the
  page-assets rule. **Do:** nothing. **Checked:** `tests/test_doctor.py` (an asset request before
  512 KB of other lines is found; the 64 MB cap holds).

## 2.38.0 (2026-10-26)

In two organisations? The site switcher, All sites and the Team page now say which organisation each site and each team belongs to. Also: a 410 gone counts as handled and a redirect anywhere as fixed; the Setup button on All sites is bright and continues at the step you reached; moving a site to another organisation takes its settings, set-up progress and own tokens along; and visitor IDs off now keeps no ID from a booking, form or payment tool's webhook either.

### Upgrade

- Nothing to do.

### Sites and teams grouped by organisation

- **Added.** For a person in two or more organisations, the sidebar's site switcher lists the
  sites under each organisation's name, and **All sites** groups its cards the same way, each
  heading with its number of sites. A person in one organisation sees the plain list as before.
  `sites.json` from the helper names each site's `org` only then (`helper_sessions.org_names`;
  `access.session_caller` gives the caller's organisations). **Why:** the owner gave a business
  partner one site in its own organisation and, being in both, could not tell from the dashboard
  which team was which. **Who:** anyone in more than one organisation. **Do:** nothing.
  **Checked:** `tests/test_org_grouping.py` (one organisation: no names, no headings; two: each
  site named, two headed groups in order, and the other organisation's own owner sees nothing of
  the first; "Other sites" last); a sandbox with two organisations in a browser, desktop and
  390 px wide (no sideways scroll).
- **Changed.** **Settings > Team** is titled with the organisation ("Team of Kiwi"), says which
  sites the team sees ("These people see kiwi.example only.") and links to your other
  organisations' teams. The team answer adds `sites` and `others` (`team_api.py`). **Checked:**
  `tests/test_team_api.py` (the sites, and the other team seen from both sides).
- **Docs.** The help's Sign-in and team guide has "Several organisations" and "Give someone one
  site only"; docs/ACCOUNTS.md and docs/CLI.md say what `site assign` does with tokens.

### A 410 gone counts as handled; a redirect anywhere counts as fixed

- **Changed.** Site > Not found and the to-dos counted a 410 as "not found", like a 404, so an
  address answered "410 gone" on purpose (the to-do's own advice) kept coming back as lost
  traffic. Now only a 404 is an ask: a 410 is counted in the address's answers only, and an
  address that answered 410 on or after the last day it answered 404 is handled and leaves the
  lost pages and the sitemap addresses. The re-check of a done to-do and **After the fix** count
  404s only, so a redirect, to the site or to another one, counts as fixed. Both roads changed
  apart (`lost_pages.py`, `audit_todos.py`). **Why:** one site sent 64 old pages to another
  site, 8 to its own pages and answered 410 for 80 on 26 Oct; the 410s would have stayed "lost".
  **Who:** every site with Site > Not found. **Do:** nothing; an address you redirected stays on
  Lost pages until its last 404 is older than the 30-day window, while its re-check already says
  fixed. **Checked:** `tests/test_todos.py` (a 404 then a 410: handled; a 410 then a 404: lost,
  with the 404s only; 410 only: never listed; a sitemap address answering 410: no to-do; the
  re-check after the mark counts only the address still answering 404; a redirected address
  marked fixed says fixed; the second count agrees); the tests fail on the old code.

### Fixed: moving a site took its log shipper's access away

- **Fixed.** A token reads only its own organisation's sites, so `skald site assign` to another
  organisation cut off the tokens made for that site alone, such as its log shipper. They now
  move with the site, each with a `token.move` audit row; a token for several sites, or for all
  of the old organisation's, stays (`accounts/orgs.py`). **Why:** on skaldanalytics.com,
  kiwiform.com was moved to its own organisation on 26 Oct and its log token stopped working
  until it was moved by hand. **Who:** anyone moving a site between organisations. **Do:**
  nothing. **Checked:** `tests/test_accounts_orgs.py` (the site's own token works after the move,
  a two-site token and an all-sites token do not read the moved site, the same organisation
  again moves nothing); the test fails on the old code.
- **Fixed.** The move also left the site's settings and its set-up progress in the old
  organisation. The old organisation's Settings > Add or remove sites still listed the site, and
  its wizard said "Your progress was not saved: There is no such site in this organisation". Both
  now move with the site, each with a `site.move` audit row. They move even when the site is
  already in that organisation, so running `skald site assign` again mends a site moved before
  2.38.0 (`accounts/orgs.py`). **Who:** anyone who moved a site made from the dashboard. **Do:**
  for a site moved before 2.38.0, run `skald site assign SITE --org SLUG` once more. **Checked:**
  `tests/test_accounts_orgs.py` (settings and progress listed and saved in the new organisation,
  refused in the old one; a move made the old way mended by assigning again).

### Fixed: the site picker's Setup button started over at step 1

- **Fixed.** **Setup: step 4 of 5, continue** under a site's card on All sites opened the wizard
  at step 1, not the step reached. It also opened the wizard inside the first site you administer,
  so a site of another organisation could not save its progress. Now the button opens the wizard
  at the saved step, inside the site's own dashboard or another dashboard of its organisation. With
  no dashboard of that organisation drawn yet, there is no button; the card leads to the site's
  waiting page (`helper_sessions.py`, `setup_page.app_for`, `js/tabs/sitesadmin.js`
  `openSiteKey`). **Why:** the owner pressed it for kiwiform.com on 26 Oct and was sent to step 1
  with "Your progress was not saved". **Who:** owners and admins with a set-up left half way.
  **Do:** nothing. **Checked:** `tests/test_site_setup.py` (the link names the site's own
  dashboard, never another organisation's, and the wizard saves there); `tests/js/connections.mjs`
  (a link with no step opens the saved step 3).
- **Changed.** The button is now bright blue with an arrow, so it reads as the next thing to do,
  not as a grey note under the card. **Checked:** a sample page in a browser, light and dark.

### Privacy: visitor IDs off now means no ID in a tool's webhook either

- **Fixed.** With a site's visitor IDs off, the hook receiver dropped the `vid` key, but a tool's
  own field for the ID was still written to the hook spool, which is kept 400 days: Typeform's
  `hidden.skv`, Cal.com's `metadata.skv` or `utm_content`, Calendly's `tracking.utm_content`,
  Stripe's `client_reference_id` and HubSpot's `skv` property. The store row was right (no ID);
  the spool line was not. Now every value that is a Skald ID goes, at any depth, and so does a
  Skald ID inside a longer text, such as a landing address's `?skv=`
  (`conversions/hooks.py`, `without_vid`). **Why:** found in the security review of
  26 Oct 2026; visitor IDs off is a promise that no ID is kept. **Who:** a self-hosted install
  with visitor IDs off that takes Typeform, Cal.com, Calendly, Stripe or HubSpot webhooks.
  **Do:** nothing after upgrading; spool lines written before it keep what they had until the
  spool drops them. **Checked:** `tests/test_conversions_hooks.py` posts each tool's sample with
  IDs off (no `skv_` in the spool, no ID in the store) and a lead whose landing address carries
  one; the new tests fail on the old code. With IDs on, Stripe's reference still reaches the
  store. Live (skaldanalytics.com, 26 Oct, counts only): the spool has lines from `lead` hooks
  only; the sites with IDs off have 0 lines holding an ID, so nothing kept there needs
  cleaning.

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
