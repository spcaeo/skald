# Skald: every feature

The full list, area by area. The [README](../README.md) has the headlines and the screenshots;
the [changelog](../CHANGELOG.md) says when each one came.

**The dashboard**
- Six sections, with tabs inside: Overview, Traffic, Leads & sales, AI & bots, Security and Site.
  Each answer has one place.
- **Every view has its own link:** the tab, the period, the filters, and the visitor, lead,
  request or dialog that is open. Back closes what you opened. No link ever holds an IP address or
  an email (they become a code only your browser reads back).
- **Copy on every value, open on every URL:** point at a page or URL and two icons copy it or open
  it in a new tab; an address, user agent, email, name or server line gets the copy icon alone.
- **A welcome line** (2.44) on a new person's first load: whose sites they see, where to start and
  where the help is; one press of × and it is gone.
- **Is it working?** (Overview › Summary): the period's exact dates (Include today: one switch), five key
  figures with their change, the sources and landing pages that rose and fell, pages to work on
  (most visits leave at once, no form), and new and updated pages with whether search found them.
- **Insights as a to-do list:** each item with its proof and the full list behind it (old pages
  still asked for, server errors, Markdown copies AI asks for); mark it done, download it, send it
  to the team, and Skald re-checks it with the same measure: did it work? **Check again** (2.43)
  re-runs a to-do's own check at once after a fix (old pages, Markdown copies, the sitemap, server
  errors asked live, politely and capped) and marks it Fixed only when the check bears it out.
- **Did my change work?** Mark the day you changed a page (content, title, a redirect): Skald sets
  the same whole days before and after side by side (visits, leads, search, AI, left at once), with
  Up, Down, No clear change or Too early to tell. A sitemap date offers to track it for you.
- **Back** (2.42): one **← Back to …** link names the view you came from and returns to it;
  browser Back and Forward walk the same steps.
- **Today** (live), **7**, **30** and **90 days**, **More** (Yesterday, All time, Custom) and **Compare**
  in the top bar, on every tab; Compare is on by default (2.42). Leads & sales opens on the last
  7 days, the other sections on today.
- **Real time** (Overview › Real time): visitors active now and in the last 30 minutes, visitors
  minute by minute, requests per minute every 15 seconds (labelled requests, never people), pages
  being read, sources, devices, AI assistants and crawlers now, and the newest visits; both
  recounted by the audit.
- **What visitors are doing now** (Overview › Real time): the newest visitors with their city, source
  and pages in order, `/ → /pricing → /book-a-demo`, the page they are on now marked, following
  the live answer every 15 seconds; point at a row and its city pulses on the map.
- A **world map** of where visitors are: countries shaded by visits today, a bubble or a city dot
  where visitors are active now, a countries table beside it. Natural Earth's public-domain
  outlines drawn in the page; no map service is asked for anything.
- Nothing reads "unknown": a visit with no referrer and no campaign tag is **Direct**, a value the
  log did not have is **Not recorded**. Under Direct, its **likely** cause (payment return,
  in-app browser, shared link), an estimate with its own second count.
- **Overview, today, live:** visitors now and the four tiles against **yesterday at this hour** (a
  figure with its own second count), where today's visitors came from and what converted; the map
  is on Real time.
- **Every table works the same way:** sort any column, filter columns, choose columns, and export
  just the rows and columns you see; all of it in the address. Every row opens its detail.
- **Advanced filters:** rules on any field a visit carries (country, city, source, campaign, AI
  assistant, first came from, pages, time on site, lead, device, browser, new or returning) with
  All or Any and groups, a live count of matching visits, saved as views. A value not recorded
  never matches by chance.
- **Search the dashboard** (Ctrl K); countries as a flag and a three-letter code; dates in the
  site's time zone; a set-up list for a new site; a preview of the daily mail.

**Traffic and audience**
- Five groups that add up to the log, every day, every site.
- Visitors, visits, pages read, countries (with a flag beside each, everywhere), browsers, systems,
  devices, sources, referring sites, UTM campaigns and ad networks (from the click ID, never its value).
- AI assistants' phone apps count as citations; paid social, iOS Google Ads, TikTok and X clicks
  are told apart by their tags and click IDs. Calls under `/api/` are never a page view, nor are machine addresses (WordPress
  REST and feed calls, oEmbed, Markdown copies, the HTML sitemap page; a switch per site).
- A new outside source starts a new visit: someone who opens the site directly and comes back from
  ChatGPT minutes later is two visits, the second from ChatGPT, so an AI assistant's visit is never
  hidden inside an earlier one.
- Anonymous journeys: each visit's pages in order, kept 7 days by default.
- **Traffic › Pages:** sort by Most visits, Rising, Falling, Recently changed or Needs work; pages
  per visit, left at once, AI reads, and each page's change date from your sitemap's `lastmod`.
- **Traffic › Visitors:** the visitor flow, each visit with its city and source, real new and
  returning figures and how engaged visits were (narrowed by the filters when every kept visit
  checks out), each card withheld unless it adds up.
- **Where a returning visitor first came from** (first touch): under a Direct visit, "First came
  from google.com, 3 days ago", linked by the visitor ID, the kept address or the 30-day code,
  never guessed; on Sources, every returning visit by where it first came from, counted twice.
- **One visitor drawer:** every visit of a visitor as a timeline, the time between pages, "12 days
  later" between visits, and a Replay of the journey. Admins and owners, audit-logged.
- **Cities** from a GeoIP city file you give it (`SKALD_CITY_DB`; DB-IP's free city file works):
  a Cities table, the city on each visit, and a dot per active city on the live map. People only.
- **Retention cohorts** (Traffic › Retention): of the visitors first seen in a week, how many came
  back in each week after, split by first source, country, device or landing page.
- **Search Console and Bing** (Traffic › Search): queries, pages, countries, devices, clicks,
  impressions, CTR and position, synced every 6 hours, connected from Settings without a shell, and
  set beside Skald's own visits from search, never forced to match. **2.43:** opportunities
  (shown a lot but rarely clicked, or at positions 8 to 20, each with its page), new and lost
  queries against the period before, and positions over time, each recounted.
- A visit that opens 6 or more pages within 2 seconds is too fast to be a person and counts as a bot.
- People: each visit kept with its IP address and browser (395 days by default), and one search for
  an IP, an email, a lead or a visitor ID that shows that person's visits, leads and conversions
  across days, linked. Admins and owners only, every search in the audit log. Keeping IPs and emails
  is a setting: on for a new install, off on an install upgraded from before 2.4.0.
- Engagement by source and device, returning visitors by source, exit rate per page, and campaign
  tag problems flagged (no medium, an unknown medium, an ad click with no tags, internal tags).
- **Compare**, on by default (2.42): the previous period, the same period last year, or any range up to 12 months,
  leads included. Insights (working, dropped, new, gone), and a page's story: its first Googlebot,
  first AI crawler, first person and first lead.

**AI and machines**
- AI assistants by name and by reason (ChatGPT, Claude, Perplexity, Gemini, Copilot, Meta AI,
  DeepSeek, Grok and more), with the pages each one fetched. The whole list is public:
  [skaldanalytics.com/bots.json](https://skaldanalytics.com/bots.json), built from the code.
- **AI readiness per page:** `robots.txt` for each AI crawler, crawler errors, the sitemap and its
  `lastmod`, the Markdown copy, AI asking for a 404 and the last AI read, each good or needs
  attention with its evidence and the fix; **Pages AI can't read well**, worst first; and AI reads
  per page against the period before, followed to AI visits and leads.
- What the AI read before it sent a visitor: the pages that assistant fetched in the minutes
  before the click, in the visit itself and per assistant (how many of its visits landed on a page
  it had just read). Context, never a count of people.
- **Reads, not requests (2.43):** an assistant fetching a page for someone (ChatGPT, Claude,
  Perplexity, NotebookLM...) counts as one read; its repeats within 30 seconds and the CSS and
  scripts the page loaded fold under it, with requests shown second.
- What AI fetches ask for: pages, `llms.txt`, Markdown, plain text, `robots.txt`, sitemaps or other
  files, for training and for live answers apart.
- What each crawler costs your server: requests, data sent, mean and 90th-percentile response time,
  error share, distinct paths and re-crawls, per assistant, search crawler and bot. Open one for
  its detail: requests by day, pages, statuses, the share from its owner's checked addresses,
  countries, user agents and when it was last seen.
- Google's AI Mode told apart: a click from Google that carries AI Mode's `udm=50` reads
  "google.com (AI Mode)", still under Search engine. Only when Google says so, never guessed.
- AI clicks that lost their referrer, estimated: a direct visit to a page an assistant fetched
  minutes before is shown as "likely" from that assistant, on AI & bots and on Leads & sales.
  Kept apart, never added to any count.
- Block AI crawlers per assistant, or only their training crawlers (AI & bots > Crawler rules),
  applied by the web server (`robots.txt` stays reachable). Skald blocks; it does not charge.
- Your `robots.txt` rules shown beside what each crawler actually fetched.
- **Crawl health:** your sitemap beside what Google, Bing and each AI crawler fetch: coverage,
  sitemap pages never fetched, pages fetched that the sitemap does not list, errors, redirects,
  slow and large answers.
- AI alerts: an assistant starts or stops reading a page; the first visit ever from an
  assistant's answer, a page's first; visits from AI answers against the same weekday's median
  over 6 weeks; a crawler gone silent for 7 days. Whole, checked days only, each recounted.
- A suggested `llms.txt` from the pages people and assistants read most, to copy and publish.
- **AI answers:** what ChatGPT, Perplexity, Gemini and Claude answer to the questions your
  customers ask, asked through their APIs with your own keys, per **tracking profile** (a place
  and a language; daily, weekly or monthly; 1 to 5 tries a question). Whether each answer names
  you, which of your pages it cites, which competitors it names, run by run and as "x of N
  tries"; then **cited → read → sent → leads** for one page, from your own log and lead tools.
  A cost estimate before anything runs and a daily cap; every figure recounted, a run that
  disagrees withheld. A sample of API answers, labelled so, not what every user sees.

**Results**
- One section, **Leads & sales**, one question per tab: Leads, Summary, Sources, Revenue,
  Calendar bookings, Funnels, Events and Find a person.
- **Revenue (2.32):** which sources (AI assistants among them), pages and campaigns made money: net revenue, sales, refunds,
  new customers, renewals and revenue per visitor, per currency, never converted; by source, campaign, page, country or your own
  tags; lifetime value by first source. Stripe's amounts are read; Polar, Dodo, Paddle, Lemon Squeezy, Gumroad or your own server send `value` and `currency` through the lead hook, Zapier, Make or n8n. Counted twice; a day that disagrees is withheld.
- **Leads:** every lead of the period, newest first: when, name and email (owners and admins
  only, where the site keeps them), what they did and its label, its stage now, where it came
  from, the source, first touch, landing page and country; as a list, a board, a timeline or a
  map. One filter row; the count above it is the Leads figure itself. A period with no lead says
  where the leads are, and "Today so far" names today's.
- Summary and Sources count from your lead database or from your tools, never both in one figure.
- Leads and demos booked on the Overview (two tiles, and each day's leads as dots on the main
  chart), and today's as they arrive with Today.
- A Leads column and a lead rate (leads per visitor, from 10 visitors up) on Sources, Pages and
  Places & devices; lead findings in Insights; leads against another period (Compare).
- Leads by first and last source, crossed with the status your team set, and time from first
  visit to lead. Saved funnels counted every day by source and device.
- Conversions from signed webhooks; forms and bookings started but not finished. One Calendly or
  Cal.com account that books for several businesses: keep only your own event types.
- **Leads you can check:** a label on each lead (sales, support); the site's own server marks its
  team's test leads (`"test": true`, or a signed call for leads already sent); a signed, read-only
  call lists what Skald has, so the site can resend any lead it missed.
- Spam, duplicate and test leads, and cancelled, removed and test conversions, each listed in full.
- Outgoing signed webhooks to your CRM, Zapier or Slack, never with a name or email.
- **From your tools (2.43):** Google Analytics 4 (a service-account key, or Skald's Search Console
  key), Vercel Web Analytics, Calendly history (bookings, cancellations, no-shows, how many the
  webhook missed) and Resend (contacts, delivery states), each read with your own key from the
  tool's free API. Shown under "From your tools", labelled "Counted from: <tool>", never added to
  the log's counts; each answer is kept and recounted, a tool that disagrees is withheld, a figure
  a tool did not give says Not given. Alerts when a tool goes quiet, leads or bookings drop, and
  an optional Monday marketing mail. Your AI agent finds the keys in your project and asks before
  sending each one.
- **Recorded journeys (2.43):** your site can send the sessions its visitors agreed to (signed,
  with withdrawal), shown as "Recorded by your site" beside the log's own visits.
- **Every empty page says how to connect it (2.43):** what it needs, what Skald found on your site,
  one Connect button; Leads & tools starts with your next step and links each source to its data.

**Security** (from the same access log)
- **Is anything exposed?** Every scanner probe your server answered with content, set against the
  host's own fallback page by size, with the evidence; "can't tell" when the log has no size.
- **Who is scanning us?** Each scanner by address and user agent: what it looked for (secret
  files, cloud and deploy configs, admin panels, WordPress, PHP), what the server answered, a
  forged referrer or the bare IP, probes per day.
- **Attack attempts:** path traversal and injection, login hammering, bursts, and log signs worth
  a look (gateway errors, `.php` requests, large POST bodies).
- **Fake browsers and scrapers**, by address and network, with the pages they took.
- **Your stack:** the web server, PHP, WordPress and Next.js read from outside once a day, matched
  against the advisories shipped with each release: update needed, or check your version.
- A **block list** to review (nginx `deny` lines, a Cloudflare IP list, a plain list), and
  **alerts** to the people on each site, in one daily summary mail (the default) or right away.
- Optional: a public **"Is my site exposed?"** check your install can answer for any site, with
  the proof for each finding and strict limits on what it fetches.
- Addresses for owners and admins only, where the site keeps them. Skald blocks nothing itself.

**Connecting a site**
- **Settings, by what you came to do** (2.40, simpler in 2.42): **To do** first (what is left for
  the site, the organisation and you), then This site (**Data**, **Leads & tools**, **Site**,
  **Privacy**, **Mail & reports**, **Alerts**), **AI** (AI assistants, AI answers), **Organisation**
  (Sites, People, Audit log) and You; each page fits one screen, and every old link still works.
  Send a site's visits (This site › Data), read your figures or connect an AI assistant
  (AI › AI assistants), each a short dialog with your address and token filled in and a **Test** at
  the end ("Connected: 1,240 lines received, the last at 10:42", or what is wrong and the fix).
- **Skald checks your site** from outside: the web server, any platform in front, the framework,
  the host names and page assets, and suggests the way in. You confirm or change it.
- **Add a site** in two steps you can leave and resume (2.42; five before): **Your site**, then
  **Connect it**, by you, your developer or your AI agent. Pick your agent (Claude Code, Codex,
  Cursor or another) and paste one line: it holds a one-time code that gives the keys once, for
  this site only, then stops; the agent connects the logs, the script tag and the lead file, and
  Skald ticks each step as it happens. Every other set-up job works the same way (2.39): each
  Set up dialog asks one question, **Who will do it? Me, My developer or My AI agent** (2.42), and
  **Finish set-up** makes one line for every open job. The agent checks first and changes only what is missing; what it finds for
  Skald's own settings waits for your **Apply**. Or set it up by hand: one command on the server (or one
  file), with `skald-ship-check` to say what is wrong in plain words; a private link to share the
  steps with your developer.
- **Every set-up says whether it worked** (2.44): beside each line for an AI agent, install
  command, set-up pack, script tag, webhook address, tool key and new token, a pill and one
  sentence update by themselves ("Waiting for your agent: it has not opened the line yet."), with
  a **Test** that checks at once and says the next step. Step 3, Watch it work, shows one status
  line and the next action; the rest is behind Details.
- **Search Console connects by itself** (2.44): Skald connects the property its robot can see,
  says when it is another than the one named, or waits for Google and connects on its own.
  Traffic › Search shows the history arriving ("Getting Google's history: 36 of 70 weeks") with no
  reload.
- **Send set-up to someone:** one zip by mail with every way in, the keys, and a `CLAUDE.md`, so a
  client gives the folder to Claude Code and says "Set up Skald from CLAUDE.md".
- **Leads in one file:** PHP, Node or Python, one function to call; a WordPress plugin with no
  code; or a plain key for Zapier and form tools. The files send the visitor's address, so each
  lead gets its country; Leads & tools warns when the last leads came without one (2.44).
- **Set up this site** on Overview, and always in Settings › To do: each open line one plain
  sentence and a Set up button.
- **Pause, remove or delete a site** (2.40): each site's ⋯ menu in Settings › Organisation ›
  Sites. Pause deletes nothing; Clear data and Delete all data need the site's name typed and
  write an archive first.
- **Keep everything** (2.40): on internal and enterprise sites Skald deletes nothing by itself
  (`SKALD_KEEP_EVERYTHING=1`); elsewhere, names and emails on leads follow the site's own
  People days.
- **Usage mails** (hosted, 2.40): owners and admins get one mail at 80%, 90% and 100% of the
  month's requests, and a banner from 80%, before any line is turned away.
- **Opens fast** (2.41): code and data are compressed, code is cached until the next release, and
  the big lists load only when their tab opens. On a 3,000-page sample over a slow line, a first
  load went from 8.0 s to 1.4 s and a site switch from 7.9 s to 0.4 s.
- **Fix this, with your AI agent** (2.41): each Insights to-do asks who will fix it. Your agent
  gets the full list from Skald with a one-time line (or `fix_todo` over MCP), changes only what
  is missing, asks before any server change and reports back; Skald then checks it worked.
- **One line per site** (2.41): set up ten sites at once, each with its own line, or connect each
  site's Claude Code or Codex session with two lines through MCP. Search Console is an agent job.
- **A simpler dashboard** (2.42): each screen leads with its answer and keeps the rest one click
  away. AI & bots › Assistants went from 5,969 px to 830 px tall, Site › Alerts from 14 cards to
  3, grouped, with a Fix button; every Settings page fits one screen, and Add a site went from 5
  steps to 2.
- **Test a sample** (or `skald try-log <file>` on the server): paste a few lines of a new log and
  see which reader fits, what it could not read and why, and the five groups adding up. Nothing kept.
- **Next.js:** one field in the site's log format and every click inside the site counts as a
  page, never a prefetch.

**Site**
- Health, Alerts, Requests, Not found, Speed and Data quality, as tabs of one section.
- 404s and who met them (people, probes, crawlers), server errors by page, page speed, uptime from
  the heartbeat with every outage.
- **Lost pages:** old addresses people, search engines and AI still ask for, the closest live page
  and how close, and the nginx or Apache line (redirect, or 410 gone) to copy.
- Alerts: site down, logging stopped, 5xx burst, 404 surge, crawler burst, new crawler, traffic
  drop, each switched on or off per site, and a **sale** (or refund) once leads carry money. A failed
  morning run sends one short mail. Any alert can go to **Slack** or any tool, as `alert.opened`.
  Site › Alerts groups what needs you, worst first, with a **Fix** button where one applies (2.42).
- A data-quality panel: unreadable lines, gaps, duplicates, log age, and requests not counted as pages.
- Deploy and change markers on every chart.

**Team, data and agents**
- Accounts: organisations, owner/admin/viewer roles, invites, two-step sign-in, scoped API tokens
  and an audit log. **Settings › Organisation › Organisations (2.43):** every organisation as a card,
  its sites, members, pending invites, keys and audit; limit a member to some sites; hand over
  ownership; archive (pauses its sites, deletes nothing) and restore; an organisation is internal
  (keeps everything) or a client (its sites follow their own retention). Give a partner or client one site by putting it in its own organisation; anyone
  in several sees their sites grouped by organisation. Or a single nginx password, if that is all
  you need.
- Settings in the dashboard: retention windows, what is kept about people, mail, sites, internal
  addresses, integrations (with each road's status), security.
- `skald doctor`: one line per part of the install (daily run, missing days, logs, the hooks, the
  script tag, mail, a newer version, disk), each with its fix.
- Several sites in one install, each with its own settings, page assets and logo (from the site
  itself, an upload, or a letter on a colour; never an outside icon service). After sign-in, a card
  per site with a Live dot and today's visitors, leads and demos booked ("-" when not known yet,
  never 0). Settings and sites can be changed from the shell too (`skald settings`, `skald site`).
- One **Export** that asks **What do you need?**: a PDF of the page, its tables as CSV, a report someone
  gets every month, or JSON; and daily and weekly email reports (refused if the figures do not
  add up).
- **Client reports:** branded reports for an agency's clients, a mail with a PDF attached, weekly,
  monthly or every few days, with your name, colour and logo; verified days only, the sums counted
  twice before a report goes.
- A read-only JSON API and an **MCP server with 29 tools** for Claude, ChatGPT and other AI agents:
  25 read-only; `setup_line` and `mark_todo_done` only with a `setup` token; `add_site` (2.44: add a site
  within the plan) and `send_invites` only with an `add_sites` token (the person search only with
  a token that may read private data).
- In-app Help in plain words with how-to guides, keyboard shortcuts, a command palette, light and
  dark themes, and a phone layout.
- A notice when a new release is out, and one-command upgrades with a backup and a rollback.

**Inputs**
- nginx and Apache logs (combined or extended), Caddy JSON.
- Countries from the log (Cloudflare's country, or nginx's `cc=`), else from a GeoIP file you give
  it (`SKALD_COUNTRY_DB`; DB-IP's free file works); a city file (`SKALD_CITY_DB`) adds cities. Without
  one, Not recorded, never guessed.
- CDN logs: Cloudflare Logpush, CloudFront, Fastly, Akamai DataStream 2. Cached pages count too.
- Vercel and Netlify log drains, and the Skald Worker for Cloudflare on any plan (it posts each
  request after the page has gone out; with your server's log, only cache hits are kept).
- `skald-ship`: one standard-library Python file that sends another server's log to Skald.
- Beacon-only mode for a site with no readable log (people only, since bots run no script).
