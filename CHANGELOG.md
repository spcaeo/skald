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

## 2.42.0 (2026-10-26)

A simpler dashboard, screen by screen. Each screen shows state and one action; help and method
text sit behind a "?"; every task that has a doer asks one question first, **Who will do it? Me /
My developer / My AI agent**, then shows only that path. Settings has a menu on the left and
opens on To do. Measured at 1440 px on the sample data, before → after: AI & bots › Assistants
5,969 → 830 px; Traffic › Sources 4,653 → 896; Overview › Summary (7 days) 2,584 → 1,393;
Site › Alerts 3,536 → 856 (14 cards → 3, each with Fix); Leads & tools 3,078 → 712 (one screen);
Help 2,238 → 830; Add a site 5 steps → 2; Export 47 controls → 6. Compare is on by default.
Also: "visits active" in Real time no longer misses a visit that ended in the last seconds of the
30 minutes.

### Upgrade

- Nothing to do. Old addresses (Settings pages, `fixby=`, `#sales/revenue?by=`, Add a site's
  `step=3/4/5`, `agent=hand`, `dlg=report`) open their new place.
- Bookmarks of the crumb trail still work; the trail now shows only "← Back to …".

### A simpler dashboard, part 1: the shared pieces

- **Added.** One visual system for every screen (`css/ui.css`, `docs/UI-RULES.md`): one card
  style, five status pills (good, waiting, broken, off, info), one accent colour kept for the one
  main button of a screen, a faint tint of each area's colour behind the top bar, and fixed sizes
  for corners and text. It uses only the colours Skald already had. Why: the owner found screens
  crowded, with many buttons of the same weight and no colour for status (UX audit of 26 Oct).
  Who: everyone, as screens move to it. What to do: nothing. Checked: `tests/test_ui_system.py`
  measures every pill and the main button at 4.5:1 or more in light and dark.
- **Added.** Four shared pieces in `js/ui/`: the "?" that opens a short help with "Read the
  guide" (opens on a press, so phones work; Escape closes it), status pills, folds ("3 done"),
  and the one main button. And "Who will do it? Me / My developer / My AI agent" (`ui/who.js`):
  the first question of a fix or set-up dialog, which then shows only that path, using the agent
  line, the developer link and the steps by hand that already exist. The choice is in the address
  (`by=me|dev|agent`) and remembered per person in this browser. Checked: `tests/js/ui.mjs`.
- **Changed.** Revenue's breakdown in the address is now `rby=` (was `by=`), because `by=` is
  the new "Who will do it?" choice. Old links still open the same breakdown. What to do: nothing.
  Checked: `tests/js/revenue.mjs`, `tests/js/ui.mjs`.

### A simpler dashboard, part 2: Overview, Site › Alerts and the top bar

- **Changed.** Site › Alerts shows one card per kind of alert, the most urgent first, each with a
  pill, instead of one card per alert (the sample: 14 cards became 3; the page went from 3,536 px
  to 856 px at 1440 wide, 7,492 to 1,273 on a phone). **Fix** asks "Who will do it? Me / My
  developer / My AI agent" and shows that path only: the steps (for a possible exposure, the line
  for nginx with a copy icon; for an advisory, its item on Security › Your stack; for a path, its
  recent requests), a message for your developer with a link to the alert, or the AI agent line
  where the kit has the job (logging stopped). In the address: `alfix=<kind>&by=me`. The method
  text is behind the "?"; closed alerts and **Which alerts are on** are one line each
  (`alerts_view=switches` opens the switches). Why: the owner found 14 cards with no button on any
  (UX audit, task 1). Who: everyone with alerts. What to do: nothing.
- **Changed.** The Site badge, the bell and Site › Alerts count the same thing: the kinds that need
  you (urgent or worth a look), so 14 open alerts of 3 kinds show 3, not 14.
- **Changed.** Overview › Summary opens on the figures. The set-up checklist is one line
  ("Set-up: 1 left · Mail recipient confirmed", **Finish set-up**, **Show the list**); in Live mode
  the map, what visitors are doing now and the flow are on Real time only (the flow moved there),
  and the footnote is behind the "?". The live Summary went from 2,942 px to 1,090 px at 1440 wide
  (5,441 to 2,217 on a phone); its figures start at 232 px instead of 498.
- **Changed.** The top bar went from 17 controls to 11: 7, 30 and 90 days stay, Yesterday, All
  time and Custom are under **More** beside them; Refresh (now **Recount today now**), saved views
  and export are in the three-dot menu at every width; Help is in the menu only; one **Search or
  jump to** (Ctrl K) also finds a person for admins, so the separate Find a person box is gone.
- **Changed.** Insights' window buttons count cards, as "Show all N" does (was findings: 31 beside
  29 cards), and the note says "29 cards from 31 findings". Data quality says "Today's log lines so
  far: Good" and names the scheduled jobs that are late, failed or never ran beside it.
- **Changed.** Insights' Fix this uses the same "Who will do it?" step: Me, My developer, My AI
  agent, in that order, the last answer remembered. Its answer is `by=` (mails now link
  `&fix=1&by=agent`); older `fixby=` links still open the same answer, `someone` as My developer.
- Checked: `tests/js/si-alerts.mjs`, `tests/js/ov-setup.mjs`, `tests/js/todos.mjs`,
  `tests/test_ux_overview_alerts.py`; the full suite with and without PyYAML; before and after
  screenshots at 1440x830 and 390x844, light and dark, in `docs/plans/ux-build-shots/`.

### Settings v2: a menu on the left, To do first, one button per page

- **Changed.** Settings is a menu on the left and the page on the right, 13 pages in groups:
  **To do**, **This site** (Data, Leads & tools, Site, Privacy, Mail & reports), **AI** (AI
  assistants, AI answers), **Organisation** (Sites, People, Billing, Audit log) and **You** (Your
  account). The card page (All settings), the Set-up checklist page and Help & docs are gone:
  Help is in the sidebar's foot.
- **Added.** **Settings > To do** (`#settings/todo`, where Settings opens): one list of what
  needs you, most important first: the site's open set-up lines, a site waiting for proof or
  paused, a plan 80% used or more, invites not accepted, two-step sign-in off, tokens unused
  for 90 days. Done lines fold into **N done**. Empty: "Nothing needs you. Everything is set
  up for example.com." **Find a setting** at the top.
- **Changed.** The set-up checklist (To do and Overview) has one title, a correct count
  ("2 left, 1 optional") and one button, **Finish set-up (N left)**. It asks **Who will do it?
  Me / My developer / My AI agent** (`setup=finish&by=me|dev|agent`); each open line is one
  button that asks the same for that line (`setup=finish-<line>`). It replaces **Set up
  everything left with your AI agent**, **Send set-up to someone** and each line's own Set up.
  It is the app's one "Who will do it?" (`js/ui/who.js`, shared with every other dialog that
  asks it): **Me** lists the open lines, each opening its own steps; **My developer** is the
  set-up pack; **My AI agent** shows **What it does** (each job ticked) and the agent tiles,
  and makes the line in the same dialog. It opens on the address's choice, else the one this
  person chose last in this browser.
- **Changed.** Every page has one title with a **?** (what it is for, its guide and docs, on
  demand), one primary button beside the title (Connect a tool, Connect the log, Add a site,
  Invite someone, Connect an assistant...), and rows with a status pill (Working, Waiting, Not
  working, Off). Long lists show 5 and **Show all (N)**. No glyphs in labels: line icons.
- **Changed.** **Leads & tools** has no tabs: each connected tool is a row with its pill; the
  row opens its details in a drawer (`tool=calendly`: address, secret, test event, deliveries,
  Remove). A red line with **Fix** only when something is broken. The tools not connected are
  one quiet line. **Send each lead out** (`tool=webhooks`) and **Search Console & Bing**
  (`tool=search`) are two small rows; **Every check** opens the checks (`tool=checks`).
- **Changed.** The pages that were forms are rows now: **Site** (Names & time, the logo),
  **Internal traffic**, **Privacy**, **Mail** and **Client reports**, **AI answers** (the lists,
  the profiles, the API keys), **Data**'s cards (log file, page assets, not pages, script tag,
  goals), **Sign-in rules**, **Billing**, **Audit log**, **Your account** and **Tokens &
  links**. Each setting is a row with its value in words, where it comes from, and a pill for
  on/off or set/not set; a card nothing in which is yours to change is one **Read-only** line.
  A row opens the card's form in a drawer, with one **Save** that wakes up on a change; the
  drawer's part is in the address (`edit=people`, `edit=report-12`, `edit=profile-p1`,
  `edit=ip-<code>`: an internal address by a code, never the address), so a link or a reload
  opens it and Back closes it. The page's one button sits by its title: **Add an address**,
  **Send a test mail**, **New report**, **New profile**, **New token**, **Download CSV**,
  **Turn on two-step sign-in** (only while it is off). The Audit log's filter is in the address
  (`aact=`). Internal traffic's figures moved behind a fold under the list. Measured at 1440 px
  (lines of text / page height in px, before → after, sample data): Site 38/1358 → 16/712,
  Internal traffic 41/1092 → 7/712, Privacy 36/1334 → 21/771, Client reports 19/796 → 18/712,
  AI answers 20/1085 → 21/712, its API keys 22/712 → 9/712, Your account 38/936 → 16/712; Mail
  16/712 → 20/712 (the values now show instead of a folded form) and Audit log 29 → 36 lines
  (two lines a change instead of a table row) are a little longer, both still one screen.
- **Changed.** Settings draws with the shared pieces (`js/ui/pill.js`, `primary.js`,
  `fold.js`, `help.js`, `who.js`, `css/ui.css`); its own copies of the accent, the pills and the
  "?" are gone from `settings.css`. Pills use the five shared kinds (good, warn, bad, off, info).
- **Changed.** The set-up dialogs (logs, page assets, Next.js pages, the script tag, the lead
  hook, privacy, Search Console) and Connect an AI assistant (MCP) open on the app's one
  "Who will do it?" (`js/ui/who.js` whoStep), in place of "Your AI agent, or by hand?": **Me**
  (the dialog's own steps, from step 2), **My developer** (the set-up in one mail or one zip,
  for logs, page assets, Next.js pages, the script tag and the lead hook) and **My AI agent**
  (the agent tiles, then the line and its watch, as before), in that order, the last answer
  remembered. In the address: `by=me|dev|agent`; an older `agent=hand` link opens Me. Why: one
  question, asked the same way everywhere (the coordinator's review of Settings v2). Who:
  owners and admins setting up a site. What to do: nothing. Checked: `tests/js/agent-jobs.mjs`
  (the answers per job, My developer's pack, Next refused until chosen, by=me and agent=hand,
  Back), `tests/js/setup-checklist.mjs`, `tests/js/connections.mjs`.
- **Added.** **Settings › This site › Alerts** (`#settings/site/alerts`): which alerts are on
  for this site and whether they are mailed. One line on top says where things stand ("16 of 17
  rules are checked with every live run, and mailed…"; off: "Alerts are off, so nothing is
  checked. 16 rules will run when you turn them on", never an "on" count that is not true).
  **Turn alerts on** is the page's one button, beside the title, only while alerts are off.
  All alerts and Mail alerts are two switches; the rules are in folds by area (Site health,
  Traffic, Crawlers & AI, Security, Sales), each "N of M on", a rule one line with its
  threshold behind its "?"; "not watched" on every row is gone; the sale minimum opens in a
  panel (`edit=alertmin`). The page is 712 px tall at 1440 wide and 661 px on a phone, where
  the same switches in one list were 1,450 and 2,720. Site › Alerts' switches fold is now one
  line, **Which alerts are on: N of M**, with a link here; an older `alerts_view=switches` link
  opens this page. Why: the switches are a setting, and Site › Alerts is for the alerts
  themselves (the Overview/Alerts builder's ask; the coordinator's review of the first cut).
  Who: admins and owners. What to do: nothing. Checked: `tests/js/set-alerts.mjs` (the state
  line on and off, the one primary, the folds and pills, one line per rule, a locked rule,
  the drawer), `tests/js/si-alerts.mjs` (the line, its link, the redirect),
  `tests/js/settings-menu.mjs`; screenshots `after3-settings-site-alerts*` in
  `docs/plans/settings-v2-shots/`.
- **Fixed.** The Settings menu cut off its last row at 830 px tall once it had fifteen pages, so
  **You** showed with nothing under it. Its rows are 28 px now (were 32): every row fits with
  room for Billing's. Checked in a browser at 1440x830.
- **Fixed.** Your account's sign-ins card wrote "null" with two to five sessions (a hidden
  "Show all" that was not there).
- **Why.** The owner, 2026-10-26: "This is like card card card... There should be a left
  navigation menu, and then on the right side, the action items"; "this has too many buttons";
  "such long screens... all the information, notes, etc. should be only on demand". The UX
  audit (docs/plans/ux-audit-2026-10-26) set the rules: one primary, a plain question first,
  rows with a pill, help behind a "?".
- **Who / what to do.** Everyone who opens Settings. Nothing to do: every older address opens
  its new home with its parameters (`#settings/home`, `#settings/site/setup`,
  `#settings/site/collect`, `#settings/ai/mcp`, `#settings/org/team`,
  `#settings/site/leads?sub=search` and the rest; the table is in docs/ROUTES.md).
- **Checked.** `tests/js/settings-menu.mjs` (the menu, the frame, the one primary beside the
  title, the old addresses), `tests/js/set-leads.mjs` (rows, pills, the red line and its Fix,
  the drawer and its address), `tests/js/set-parts.mjs` and `tests/js/set-account.mjs` (the
  pages that were forms: rows, pills, one primary, each drawer and its `edit=`, a link opening
  it, a save that updates the rows, an address never in the URL), `tests/js/settings-privacy.mjs`
  and `tests/js/views-fill.mjs` (their forms, now in the drawer), `tests/js/settings-todo.mjs` (every To do source and the
  order), `tests/js/routes.mjs` and `tests/test_routes.py` (old addresses, `setup=finish`,
  `by=`, `tool=`), the checklist and agent tests, before/after screenshots at 1440 and 390 px
  in light and dark (docs/plans/settings-v2-shots/), and the full suite with and without
  PyYAML.

### A simpler dashboard, part 3: AI & bots, Traffic, Leads & sales, Security and Compare

- **Changed.** Compare is on by default (the UX audit's task 5). With 7, 30 or 90 days, Yesterday
  or a custom period, every tab that compares sets the period against the same number of days
  before it, and the bar says "vs previous period"; no click needed (it was 4: period, Compare,
  Previous period, Compare). The address leaves that default out; another choice is written
  (`cmp=year`), and **Turn compare off** writes `cmp=off`, which stays as you move. Today, All
  time and a period that includes today are never compared, as before. A tab that does not
  compare has no Compare button and no "No compare on this tab" line unless a link asked for one.
  Why: the audit found the change against the period before was the figure people looked for
  and four clicks away. Who: everyone. What to do: nothing; links that said `cmp=prev` still open
  the same view. The Overview Summary on 7 days grows (2,584 to 2,728 px at 1440) because each
  tile and "What changed" now show the change.
- **Changed.** The top bar is the mockup's seven groups: the title, the period (Today, live, as
  its first choice; 7, 30, 90 days; More), Compare, Filters, Search, Alerts and More. Today was
  its own "Today · Live" switch; the page group list moved into the Filters panel (at its top),
  and a chosen group shows as a chip under the bar. That is 10 buttons on a tab that compares
  (17 on 2.41.0, 11 after part 2), 9 where Compare does not apply; the period group alone is 5
  of them, as in the mockup. Checked: `tests/test_routes.py` (compare on by default, off kept,
  Today and back), `tests/e2e/modes.mjs`, `topbar.mjs` and `layout.mjs` updated for the new bar.
- **Changed.** AI & bots › Assistants opens on the answer (the UX audit's task 4): three figures
  with their change (Visitors sent by AI, Pages AI read for someone, AI collecting for training),
  which assistant sent people and which read for someone (five each, then **Show all (N)**), and
  one card, "7 pages AI can't read well", with the screen's one primary button, **Let AI read
  the site better**. It asks "Who will do it?": Me (the pages by what to do), My developer (a
  message and a link), or My AI agent when Insights has a to-do the agent already fixes
  (Markdown copies, server errors, lost pages; it opens that to-do's Fix this). No new agent job.
  The day chart, the tables by name, the formats, the costs, the pages fetched, AI reading
  changes and the full list are under **Open the details** (`ai_view=open`). The page went from
  5,969 px to 830 px at 1440 (12,324 to 1,365 on a phone). Crawlers folds what they fetch, the
  costs and the address check the same way (4,139 to 1,819 px). Why: the answer to "which AI
  sent people" was four screens down. Who: everyone. What to do: nothing; every figure is the
  one shown before. In the address: `fixit=airead&by=me`. Checked: `tests/js/phase-c.mjs`,
  `tests/test_ux_sections.py`, before and after shots.
- **Changed.** One place for each control, and a shorter Summary (the UX build's polish).
  **Include today** and **Compare with the period before** were switches on Summary and
  Pages as well as in the top bar; now Compare is only the top bar's menu, and Include today
  is a check item in the period's **More** menu (the button reads "More · today" while it is
  on; still `inc=1`). The period line keeps the dates; what the period means is behind its
  (i). The trail line over each screen ("← Back to … · Overview › Summary › …") is now the
  **← Back to** link alone, and nothing when you came from nowhere; Back and Forward still
  walk every step. **Overview › Summary** keeps the key figures, the chart and What changed
  (5 rows each, then Show all; "About the same" behind its (i)) open, drops the "Key
  figures, each with its change" caption (each tile says its change), and folds the rest (countries, top pages and sources, AI
  assistants, who else came, pages to work on, new pages, server requests, each day) into
  **More for this period** (`ovx_view=open`): 2,728 to 1,393 px at 1440 on the sample data.
  Who: everyone. What to do: nothing. Checked: `tests/js/crumbs.mjs`,
  `tests/test_ux_sections.py`, before and after shots.
- **Changed.** Security, one action per screen (the UX audit's task 9). **Is anything
  exposed?** shows **Fix** in its verdict line only when there is a possible exposure; it asks
  **Who will do it?** (`fixit=exposed`): Me sees the paths by kind with the nginx line to copy,
  My developer gets a message with a link back. **Block list** has **Block them**
  (`fixit=block`) with the steps for nginx, Cloudflare (Settings › Lists, as in Cloudflare's
  guide) and fail2ban; its three downloads stay plain buttons and show only when there is
  something to block. My AI agent is not offered on either: no agent job does this yet, and
  this release adds none. Each host's answers is under **Open the details** (`sxx_view=open`);
  the Block list's long warning is behind the "?", one line of it stays. Who: owners and
  admins (the Block list), everyone (Exposed). What to do: nothing. Checked:
  `tests/test_ux_sections.py`, shots of both screens and the Fix dialog.
- **Fixed (words, not counts).** Two figures that looked like a mismatch now say why they
  differ. On Leads & sales with **7 days**, Leads said 25 and Summary said 19: Leads counts the
  7 days up to today, so far, from every tool (demos booked too); Summary and Sources count
  the 7 whole days up to yesterday from the lead database (sign-ups, contact forms and early
  access, no demos booked). Both are right; neither figure changed. The line under the Leads
  count now names Summary's dates and what it counts, and a note under Summary's figures
  links back to Leads. On Traffic › Retention the period chip said "12 weeks of first visits"
  while the New visitors figure said "the 8 weeks counted": it now says "first seen in 8 of
  the 12 weeks: 4 before what is kept begins (Tue 25 Aug 2026)". Seen in the UX audit (task
  3). Who: everyone. What to do: nothing. Checked: `tests/js/leads-period.mjs`,
  `tests/js/phase-c.mjs`, `tests/test_ux_sections.py`, and the sample data's shots.
- **Changed.** Traffic, answer first (the UX audit's tasks 7 and 8). **Visitors** opens on the
  visits: a **List / Flow** switch kept in the address (`vis_view=flow`), the list's first 12
  rows then **Show all**, the two cards, and **Open the details** (`visx_view=open`) for where
  visits ended, next steps and the engagement tables (4,747 to 2,718 px at 1440). **Sources**
  opens on its grid; its five method notes are behind the "?" beside the title, and the likely
  causes of Direct, where returning visitors first came from and campaigns and referrers are
  under **Open the details** (`srcx_view=open`; 4,653 to 858 px). **Pages** opens on Landing
  pages and their leads (search a page, a row opens its story, `page=`); Pages by publish date,
  the leaderboard and Pages read by people are under **Open the details** (`pgx_view=open`;
  3,639 to 1,254 px). A page's story has one primary button, **Mark a change**; **Compare this
  page** is a plain button. Why: the visit list started under a 1,000 px flow map, and Sources
  repeated the same six sources in 11 sections. Who: everyone. What to do: nothing; every
  figure and table is still there. Checked: `tests/test_ux_sections.py`, before and after shots.
- **Changed.** Insights' **Fix this** writes `by=` in the address too (it wrote `fixby=`), so
  every "Who will do it?" step uses one key. Older links with `fixby=` still open the same answer.
  Who: anyone who copies an Insights link. What to do: nothing. Checked: `tests/js/todos.mjs`.

### A simpler dashboard, part 4: Export, Add a site, the visitor drawer, Help, sign-in and mail

- **Fixed.** "Get the daily mail" waited for good when the install has no mail server: step 3
  said "Waiting for owner@example.com to press the link in their confirm mail" with **Check
  again**, and the mail could never go. Saving the recipients also used up the day's confirm link
  for nothing. Now every step shows one card, "Skald cannot send mail yet", with what is missing in
  plain words and "Who will set it up?": **Me** (install admins: the form in Settings › Mail &
  reports) or **My developer** (a message to send, which names where the settings go and holds no
  secret). The answer is in the address (`setup=mail&step=3&by=dev`). No confirm mail is tried
  without a mail server, and your own address (the one you sign in with) is never asked to
  confirm. Why: the UX audit found the dialog stuck. Who: installs without SMTP settings. What to
  do: nothing; set the mail server when you want mail. Checked: `tests/js/mail-ready.mjs`,
  `tests/test_mail_confirm.py` (no link used up, own address confirmed), the sandbox shots.
- **Changed.** GET and POST `settings` answer `mail_server: {ready, missing}`. The helper for any
  page that shows mail settings is `js/mail-ready.js`.
- **Changed.** Export is one item under the three-dot menu (and in Search, "Export: a PDF, the
  tables as CSV, a report by mail or JSON"). It asks "What do you need?" and shows only that
  path: **A PDF of this page** (this page as on screen; **Change** opens the sections, period,
  page group and filters of the old Report builder), **The tables, as CSV** (each table on its
  own, or all in a ZIP), **A report someone gets every month** (who gets it, filled from your
  last report; how often; this page's part; **Preview**, **Start sending**; owners and admins with
  accounts) and **Everything, for my own tools** (JSON, the API, MCP). Each path has one main
  button, and Export opens on your last choice, so a PDF again is three presses. In the address:
  `dlg=export&kind=pdf|csv|monthly|tools`, `xch=1` while Change is open. Why: four export items,
  a 33-box Report builder and the client reports in Settings did the same job three ways (UX
  audit, task 6). Who: everyone who exports. What to do: nothing; old `dlg=report` links open the
  PDF path with its sections open. Checked: `tests/js/export.mjs` (every path, the address round
  trip, the old link, no mail server), `tests/test_ux_overview_alerts.py`, the sandbox shots.
- **Changed.** Add a site is two steps: **Your site** and **Connect it**. Step 1 takes the
  address, says what Skald found in one line while you type ("Runs on nginx · suggested: one
  command on the server", details folded), shows the time zone in one line with **Change**, and
  asks "Who will connect it?": **Me**, **My developer** or **My AI agent**. Step 2 shows only that
  path: for Me the found way with its one command made at once and the Test below it (**Another
  way** for the others); for My developer the private link; for My AI agent the agent choice, its
  line, and "Skald watches your agent" under the line. The proof step shows only when the server
  asks for one. The site's row says **Finish setting up** in place of "Setup: step 3 of 5,
  continue". In the address: `setup=<site>&step=1|2&by=me|dev|agent`. Why: the old wizard took
  five steps and about 11 presses for a site Skald could read itself (UX audit). Who: owners and
  admins who add sites. What to do: nothing; older links still open (`step=3`, `4` or `5` is
  Connect it, `agent=hand` is Me), and the server still saves its five-step progress. Checked:
  `tests/js/add-site.mjs` (both steps, every path, the address round trip, the old links, the
  proof step only when asked), `tests/js/connections.mjs`, `tests/js/agent-setup.mjs`,
  `tests/js/routes.mjs`, `tests/test_site_setup.py`, the sandbox shots at 1440 and 390 wide.
- **Fixed.** In the send steps, a long install command no longer widens the dialog on a phone
  (the command scrolls inside its box). Seen at 390 px wide in Add a site. Checked: the sandbox
  shot, measured with no part wider than the dialog.
- **Changed.** The visitor drawer starts with the state: one card with pills (**Here now**,
  **Returning** or **First visit**, and how the visits ended), one sentence ("4 visits over 13
  days. First came from reddit.com, 13 days ago.") and one line of facts (place, device and
  browser, first seen), each with a copy icon. How the visits are linked moved behind a **?**.
  The journey draws the newest two visits, then **Show all (N)** (`vall=1` in the address, gone
  when the drawer closes). Leads and conversions, This visit and Every visit as a table are folds.
  Why: the drawer opened on a six-box grid and every visit at once (about 1,900 px tall for a
  visitor with four visits, 295 words). Now about 960 px and 110 words before you open anything.
  Who: everyone who opens a visit or a person. What to do: nothing. Checked:
  `tests/js/visitor-short.mjs` (the state, the pills, the copy icons, Show all and its address
  round trip, the folds, a lead's fold open), `tests/js/visitor-drawer.mjs`, `tests/js/routes.mjs`,
  `tests/test_firsttouch.py`, the sandbox shots at 1440 and 390 wide.
- **Changed.** Help lists the guides in six groups (Start here, Your visitors, Leads and sales,
  AI and bots, Connect and set up, Security and privacy), one line per guide with its summary on
  hover. The search lists the guides that hold every word, each with the sections they are in;
  a section opens the guide there. The search words and the section are in the address
  (`hq=`, `hs=`). A **?** popover can name a guide's section (`guide: "id#section"`), and its
  **Read the guide** opens it there: Export and the visitor drawer do. Why: the index was a wall
  of 29 cards, about 1,450 words and 2,240 px tall, before the search. Now about 150 words and
  one screen at 1440 wide. Who: everyone who opens Help. What to do: nothing; old
  `#help?part=<guide>` links open as before. Checked: `tests/js/help-guides.mjs` (every guide in
  one group; every Help link and "?" in the app names a guide and a section that exist; the
  search and its address round trip; a section link), a browser check (typing keeps the focus;
  a link with `hs=` opens at that section; Back works), the sandbox shots.
- **Changed.** The sign-in and invite pages are shorter. Sign in has no line under its title, and
  the "Keep me signed in" note is behind a **?** beside it. The invite says "As a viewer, for
  teammate@example.com." in one line, and the password rule in one line. Both cards carry the
  dashboard's five traffic colours as a thin line on top, in light and dark. Why: the owner asked
  for less on every screen (38 words on sign in, now 15; the card 460 px tall, now 404). Who:
  everyone who signs in or accepts an invite. What to do: nothing. Checked:
  `tests/test_webapp_auth.py`, `tests/test_saas_pages.py`, `tests/test_auth_api.py`, a browser check
  (the ? opens and closes its words, the box still ticks), the sandbox shots.
- **Fixed.** Settings › Mail with no mail server. Before, saving a recipient said "A confirm
  link was mailed to ..." though no mail could go, and nothing on the page said why. Now the
  card **Skald cannot send mail yet** sits above the recipients, says what is missing and asks
  **Who will set it up?** (Me for an install admin: the Mail server (SMTP) drawer; My developer:
  a message to copy). A saved address is told it gets its link once the mail server is set.
  With a mail server the page is as before. Who: owners and admins of an install with no mail
  server. What to do: nothing. Checked: `tests/js/prefs-mail.mjs`, drawn from real helper
  answers by `tests/test_mail_confirm.py`, with and without a mail server.
- **Changed.** Merged with Settings v2 (branch `ux-int`). Add a site asks who connects it once,
  in step 1, with the shared "Who will do it?" tiles (`ui/who.js`); step 2's agent tiles no
  longer carry a second "Me" (press **Change** to go back). Export's links for your own tools
  open Settings › AI assistants (API, MCP), and the no-mail-server card's **Me** opens the Mail
  server (SMTP) drawer (`#settings/site/mail?edit=smtp`). Why: Settings v2 renamed the pages and
  moved every set-up dialog to the same question. Who: owners and admins. What to do: nothing;
  older links still open. Checked: the node tests of both branches, both full suites.

### Summary and Pages state the period once; the chart's note is behind "?"

The scope line already gave the period's dates, then the period line gave them again, and the
sentence under the figures said a third time what the changes were against. The period line now
only says what the period is compared with, and only when Compare is on; the sentence lost its
"Changes are against …". The by-day chart's two-line explanation is behind a "?" by its title.
Who: everyone. To do: nothing. Checked in the browser on the sample data at 30 days.

### Real time: a visit that ended just under 30 minutes ago counts as active

- **Fixed.** Real time's "active now" (the last 30 minutes) left out a visit whose last request
  came in the first seconds of that window, before the first clock minute the per-minute bars
  show. A live run at 12:00:40 counts from 11:30:40, but its bars start at 11:31, and a visit
  last seen at 11:30:50 was skipped with the bars, so it was missing from the active count and
  from active by country, city, source and device (it was still listed under "What visitors are
  doing now", so the list could be one longer than the count).
- **Why.** `audit --live` on the busiest shipped-log site said now and then "visits active in the
  last 30 minutes: snapshot 14, recount 15", with US 9 vs 10, one city, a source and a device one
  higher too, a different visit each run, every other figure matching (seen 2026-10-24 and after
  the 2.40.0 deploy on 2026-10-26). The recount follows the documented rule, so the snapshot was
  the one wrong. It was not the order of the shipped lines: both roads count a window in time
  order (CLASSIFICATION.md, "Line order"), and shuffled shipped batches give the same visits.
  It happens on any site whose live run does not end on a whole minute; a busy site meets it
  more often.
- **Who / what to do.** Anyone looking at Real time. Nothing to do. No stored figure changes: the
  real-time part is never stored or mailed, and the daily figures were never affected, so no
  recount is needed.
- **Added.** `audit --live --show-active` (docs/CLI.md): both roads' active visits for the
  snapshot, one line each (start, last request, country, city, device, source, pages), the ones
  on one road only marked. Labels and times only, never an address.
- **Checked.** `tests/test_realtime_edge.py`: a live run at 12:00:40 with a visit last seen at
  11:30:50 (failed before the fix: snapshot 1, recount 2, the same pattern as the live runs);
  shuffled shipped batches against the same lines in time order give the same snapshot, real
  time, recount and day; `--show-active` prints no address. The full suite, with and without
  PyYAML.

### Fixed: the phone's bottom bar showed Menu on a second row

On a phone, the bar at the bottom has six sections (Overview, Traffic, Leads, AI & bots, Security,
Site) and Menu, but it was laid out for six items, so Menu wrapped onto a second row under
Overview. It now makes one column per item. Who: everyone on a phone. To do: nothing. Checked in
the browser at 390 px, light and dark: seven items on one row.

## Older versions

- 2.39.0 to 2.41.0 (26 October 2026): [docs/CHANGELOG-2.39-2.41.md](docs/CHANGELOG-2.39-2.41.md).
- 2.36.0 to 2.38.0 (25 and 26 October 2026): [docs/CHANGELOG-2.36-2.38.md](docs/CHANGELOG-2.36-2.38.md).
- 2.35.0 and 2.35.1 (25 October 2026): [docs/CHANGELOG-2.35.md](docs/CHANGELOG-2.35.md).
- 2.32.0 to 2.34.1 (24 and 25 October 2026): [docs/CHANGELOG-2.32-2.34.md](docs/CHANGELOG-2.32-2.34.md).
- 2.27.0 to 2.31.1 (22 to 24 October 2026): [docs/CHANGELOG-2.27-2.31.md](docs/CHANGELOG-2.27-2.31.md).
- 2.23.0 to 2.26.0 (22 October 2026): [docs/CHANGELOG-2.23-2.26.md](docs/CHANGELOG-2.23-2.26.md).
- 2.21.0 to 2.22.3 (21 and 22 October 2026): [docs/CHANGELOG-2.21-2.22.md](docs/CHANGELOG-2.21-2.22.md).
- 2.14.0 to 2.20.1 (18 to 21 October 2026): [docs/CHANGELOG-2.14-2.20.md](docs/CHANGELOG-2.14-2.20.md).
- 2.8.0 to 2.13.0 (18 October 2026): [docs/CHANGELOG-2.8-2.13.md](docs/CHANGELOG-2.8-2.13.md).
- 2.7.1 and earlier (8 to 12 October 2026): [docs/CHANGELOG-2.0-2.7.md](docs/CHANGELOG-2.0-2.7.md).
