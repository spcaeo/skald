# AI & bots: what each crawler costs

See which AI assistants, search engines and bots fetch your site, how much work each one makes for your server, and what one of them did in detail. This guide covers the cost table, the detail view, and what each figure means.

## What Assistants shows first

Open **AI & bots**. **Assistants** opens on the answer:

- Three figures, each with its change against the period before: **Visitors sent by AI**, **Pages AI read for someone** and **AI collecting for training**.
- **Which assistant sent people** and **Which assistant read for someone**: the first five of each, then **Show all (N)**.
- One card for what to fix: "7 pages AI can't read well", what kinds, and **Let AI read the site better**. It asks **Who will do it?**: **Me** (the pages by what to do), **My developer** (a message to send, with a link), or **My AI agent** when Insights has a to-do the agent can fix (Markdown copies, server errors, lost pages): it opens that to-do's **Fix this**. robots.txt and slow pages stay with you or your developer. In the address: `fixit=airead&by=me`. Nothing to fix: one quiet line, and no button.

Everything else is under **Open the details** at the foot: each day's chart, the tables by name, what AI read before it sent a visitor, what they fetch, what each costs, the pages fetched, AI reading changes and the full list of pages AI can't read well. It stays open in the address (`ai_view=open`). **Crawlers** keeps its figures and lists on top; what they fetch, what each costs and the address check are under its own **Open the details** (`crawl_view=open`).

## Reads, not requests

When an assistant fetches a page for someone, it may ask for the page twice in a few seconds, and some then load the page's own style sheets and scripts, as a browser does. That is one **read**, even if the log has four requests. Skald counts:

- **A read**: one assistant, one page. Asking for the same page again within 30 seconds is the same read.
- **A file the page loaded**: a style sheet, script, image or font, or anything that names the page it just read as its referrer. It is never "AI asked". In the requests list it is folded under its page's row: "asked 2 times, with 2 files its page loaded".

**Pages AI read for someone**, **Which assistant read for someone**, the assistants table (its **Reads** column; the column once called Fetches is now **Requests**), the chart per day, Overview's AI card, **AI reads** on Traffic › Pages, **Reads followed by a visit**, AI answers' "From an answer to a lead", the client reports and the daily mail count reads, and show the requests as the second, smaller number. Request figures (status, bytes, cost) still count every request. Days collected before reads were counted say **Reads counted from** and the first day that has them; they never show 0.

## Pages, and files counted apart

A crawler collecting for training does not only fetch pages. It also asks for robots.txt, sitemaps and llms.txt, and often for images, style sheets and scripts on their own, with no page around them. Every one of those is a request in the server's log. So that a page count is a page count:

- **AI collecting for training** (on Assistants, on Crawlers and in Overview's **Who else came**) is **pages fetched**. The other requests are one number beside it: "+ 63 files (robots.txt, sitemaps, llms.txt, images, styles and scripts)".
- **AI collecting for training, by name** on Crawlers has a **Pages** column and a **Files** column. A crawler that only fetched robots.txt or files still has its row, with 0 pages. Share is the share of pages.
- The chart per day on Crawlers counts pages.
- **All AI activity today** lists pages only. Under the list it says how many file fetches it left out. The CSV keeps every row.
- Pages plus files is exactly the requests. **What they fetch** under **Open the details** breaks the files down: robots.txt, sitemaps, llms.txt, Markdown, text and other files.

The address decides, not what the server answered: a request for a page's address that was redirected or not found is still a page. Days counted before 18 October 2026 did not keep pages and files apart. A period that includes one shows **requests**, pages and files together, never a page count of some of the days.

What a read means for each assistant (also behind **?** in its detail):

| Fetcher | It fetches a page when |
|---|---|
| ChatGPT-User | someone asks ChatGPT a question the page answers, or pastes the page's link |
| Claude-User | someone asks Claude about the page, or it looks something up to answer |
| Perplexity-User | someone asks Perplexity a question, or opens one of its sources |
| Gemini-User | someone asks Gemini about the page |
| Google-NotebookLM | someone adds the page as a source to a notebook, or refreshes one |
| MistralAI-User | someone asks Le Chat a question |
| Meta-ExternalFetcher | someone shares the page's link with Meta AI, or asks about it |
| Amzn-User | Alexa answers someone's question |

Gemini opening a page live is not in this table. It fetches with the bare user agent `Google`, through the same Google proxy that Google Sheets (`IMPORTXML`), Apps Script and feed readers use, so a request cannot say which of them sent it. Skald files it under bots as **Google fetch proxy (Gemini, Sheets, Apps Script)**, never as an AI read. Its address is checked by reverse DNS once a day: one that proves not to be Google's is **claims to be Google fetch proxy (...)**. One not checked yet keeps the name.

## Where to find it

The table **What each crawler costs** is on two tabs, under **Open the details**:

- **Crawlers**: AI collecting pages for training or AI search, search engines, and bots and scanners.
- **Assistants**: AI assistants fetching a page because someone asked them a question. Here it is headed **What each assistant costs**.

Pick the period at the top as on any other page: today, yesterday, a number of days, or your own dates.

## What the columns mean

| Column | What it is |
|---|---|
| Name | The name the crawler gives itself. Bots without a known name go by the name in their user agent. Scanner probes are one row, **(scanner probes)**; everything else a scanner asked for that day (its home page, say, between two probes) is another, **scanner (asked for secret or config files)**. A visitor that asked for 5 or more scanner paths your site does not have is **scanner (asked for many missing probe paths)**, and a browser that checked pages or images with `HEAD` requests is **browser-like link checker (HEAD requests)**. |
| Reads | Assistants only: the pages it read for someone (see Reads, not requests, above). |
| Requests | Every request it made in the period. |
| Bytes sent | How much your server sent it, from the size field of each log line. |
| Mean time | How long your server took per request, on average. |
| p90 time | 9 in 10 of its requests took no longer than this. Shown for a single day only. |
| Errors | The share of its requests that got an error (4xx or 5xx). |
| Distinct paths | How many different addresses on your site it asked for. |
| Re-crawl | Requests per distinct path: 3.0× means it fetched each path three times on average. |
| Last seen | Its last request in the period. |

Select a name to open its detail.

An assistant is called by the name people know it by: **ChatGPT**, not `chatgpt.com`. A bot keeps its own name, because it is one fetcher, not the assistant. A bot that reads a page only when one user asks the assistant about it (`ChatGPT-User`, `Claude-User`, `Perplexity-User`, and fetchers whose names do not end in -User, such as `Google-NotebookLM` and `BingPreview`) is marked **user fetcher**. The tag comes from the server's own list of user fetchers, the one that files a fetch under its assistant.

A person who clicks a link in an AI answer is counted as a person, with the assistant as the source. Skald knows these assistants by the address they send people from (or the tag they put on the link): **ChatGPT**, **Perplexity**, **Claude**, **Gemini**, **Copilot** (copilot.microsoft.com, copilot.com and Bing's chat), **Meta AI**, **DeepSeek** (chat.deepseek.com), **Grok** (grok.com, and Grok inside X at x.com/i/grok; the rest of x.com is X), **Mistral**, **You.com**, **Phind** and **Poe**, and the Android apps of ChatGPT, Perplexity, Claude, Gemini, Copilot, Meta AI, DeepSeek and Grok. An iPhone app sends no address of its own: its visits count only when the link carries the assistant's tag (ChatGPT adds `utm_source=chatgpt.com`); otherwise they are Direct.

**OAI-AdsBot** is OpenAI's crawler that checks the landing pages of ads placed on ChatGPT. It is listed with the AI crawlers when its address is OpenAI's. A request that uses its name to look for secret files (`.env`, keys) is not believed: it stays under bots, as a scanner, unless the address is checked as OpenAI's.

**RiverBot** is River's crawler for training and evaluating its AI models. It is listed with the AI crawlers that collect for training. River publishes the addresses it crawls from, so a request that uses the name from any other address is filed under bots, as "claims to be RiverBot". It follows robots.txt, and you can block it in the AI crawler controls under **River**.

## When a figure says "not recorded" or "partial"

Skald only shows what your server log holds. It never fills a gap with zero.

- **Bytes: not recorded.** None of that crawler's log lines had a size. Some log formats and hosting platforms do not write one.
- **Bytes: partial.** Only some lines had a size. The figure is the sum over those lines; hover over it to see how many.
- **Mean time: -** The log does not record how long the server took. nginx does when its log format has `$request_time`. Vercel, Caddy and edge records do not.
- **p90 time** shows only when the period is a single day. A p90 over many days cannot be built from each day's p90, so for longer periods use the mean, or pick one day.

## Figures over several days

For a period of more than one day:

- Requests, bytes and errors are added up over the days.
- The mean time is weighted by request: a busy day counts more than a quiet one.
- Distinct paths are counted per day and added up. A path fetched on two days counts twice. Re-crawl is therefore requests per path within a day.
- Each day keeps its 50 busiest names per group. The rest are one row, **(all others)**.

## The detail view

Select a name in the table, or any crawler name elsewhere on AI & bots. The detail opens on the right. Under **What it costs and what it fetched** you see:

- **Requests, bytes sent, mean server time and errors** for the period.
- **From an address checked as theirs**: the share of its requests from an address that really belongs to its owner. Requests that use a crawler's name from an address that is not theirs are counted apart, as "claims to be ...". The check needs the owners' published address lists, which the daily run fetches. A Docker install does this by default from this release on; before, no Docker install checked, so earlier days show every request as not checked, and a fake crawler counted as the crawler it named. `doctor` says "crawler checks off" when they are off. Claude's fetches for a person (Claude-User) are checked against Anthropic's outbound addresses too, after 2.58.0; up to 2.58.0, those real fetches were counted as "claims to be Claude-User".
- **Requests per day**, as a chart.
- **What it read** (an assistant's user fetcher only): its reads, requests and the files its pages loaded, and the pages it read, each "with N files". **?** says what the assistant is and what a read means.
- **Paths it requested**: the addresses it asked for most, by request, its pages' files included.
- **Status mix**: how the server answered.
- **Countries of its requests**: from the log's country field or the GeoIP file.
- **User agents it sent**: the exact strings, the five most used each day. These are the crawler's own, never a person's. For scanner probes and the rest of a scanner's requests, link previews and browser-like bots the strings are not kept, because they may be a real person's browser.
- **Last seen**.

Pages, countries and user agents are kept for the last 30 days. For an older period the detail says how many of its days have them. No address is ever shown.

## Can AI read a page well? (AI readiness)

Open a page's story (**Traffic › Pages**, then select a page). The block **AI readiness** answers six questions from your server's log and Skald's own copies of your robots.txt and sitemap. No AI is asked anything.

| Line | What it checks |
|---|---|
| robots.txt | Whether each of the main AI crawlers (GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User, PerplexityBot, Perplexity-User, Google-Extended, Applebot-Extended) may read this page. It shows the rule that decides, and the lines to add if you want to let one in. |
| Crawler errors | Server errors, refusals (403, 429...) and slow answers (a second or more) AI got from this page in the last 30 days. Redirects are named but not counted as a problem: the log does not say where a redirect leads. |
| In the sitemap | Whether the page is in your sitemap, and its last-changed date (lastmod). |
| Markdown copy | Whether the Markdown copy AI asked for (`page.md`, `page/index.md`) answered. Some plugins send assistants to a page's `.md` copy; if that copy does not exist, AI gets a 404 instead of your page: "AI asked for the Markdown copy 6 times; it answered 404 each time." |
| AI asking for a 404 | Whether AI asked for this address and got 404 or 410. |
| Last AI read | When an assistant last fetched the page for someone, and how many times in the last 30 days against the 30 before. |

Each line is **Good**, **Needs attention** or **Not known**, with one line of evidence and what to do. "Not known" means Skald does not have what it needs (no copy of robots.txt yet, no sitemap, or the days before this release). It never guesses and never shows a 0 it did not count. Crawler names, status codes and robots.txt lines have a copy button.

**Pages AI can't read well** is on **AI & bots › Assistants**, under **Open the details** (the card above it counts them): every page where AI got an error, a 404 or a slow answer, asked for a Markdown copy that does not answer, or that robots.txt shuts them out of, worst first. Filter it by kind with the chips above it. Select a row to open that page's AI readiness. A crawler that robots.txt keeps out of the whole site is said once, above the list.

What AI got back is recorded from this release on. A page group (view) shows it for the whole site only. robots.txt says what a crawler may read; assistants that fetch for one user (ChatGPT-User, Perplexity-User) may not follow it.

## Who reads the files you made for AI? (Agent files)

Many sites now publish files written for AI agents and tools rather than for people: a Markdown copy of each page (`page.md`, linked from the page's head with `<link rel="alternate" type="text/markdown">`), an OKF bundle (Open Knowledge Format: a folder of Markdown files that indexes the site, `/okf/index.md`), `/llms.txt`, and agent or MCP cards under `/.well-known/`. Open [Traffic › Agent files](#traffic/agentfiles) to see who asks for them.

- **The cards:** requests for all these files, then for each kind: Markdown copies, llms.txt, sitemaps, robots.txt, agent cards, and the OKF bundle (when the site has one). Each card says how many came from AI and how many of its listed files need a look. Select a card to go to that kind's section. "Nobody asked" is an answer too: most llms.txt files are never read.
- **Requests per day** (a period of two days or more) are stacked by who asked: AI assistants (fetching for someone's question), AI crawlers (training and AI search), search engines, other bots and tools, and people.
- **One section per kind of file**, for each kind someone fetched, in this order: Markdown copies, llms.txt, Sitemaps, robots.txt, agent cards, the OKF bundle. Each section shows:
  - **Its figures:** requests and the share from AI, then how many files are listed and how many of them need a look.
  - **Who asked:** each group's share and the busiest names.
  - **Needs a look:** this kind's files that answered an error (an agent asked and got nothing) or sent the agent to another address. A 404 for `/llms.txt` or an agent card means agents look for one and your site has none: publish one, or leave it.
  - **Files:** each file, the page a Markdown copy stands for, its requests, the share from AI, its answers and when it was last fetched. Select a row for the file's own drawer: its answers, who asked, by name and by day. In the address: `afile=/okf/index.md`.
  - robots.txt is usually one file, so its section is one line (requests, answers, last fetched), with a note when it needs a look. When the period reaches back beyond the files kept, or the site answers more than one spelling (`/robots.txt/`), it gets the two tables instead.
- **Copy and Open:** every file's address has both, as page links do. Copy writes the full address (`https://www.example.com/llms.txt`), and Open opens the file in a new tab. An address that is not a path on your site (a logged `http://other.example/...`) gets neither.
- **Who fetches them**, at the bottom: each group's share, then every name with its requests per kind. **Other bots and tools** holds SEO tools, monitors, scripts (curl, Python) and AI tools Skald does not name yet. It also holds browser-like clients that never showed a page: many AI agents fetch with a browser's name.

Only the address decides what a file is, so a request that got a 404 still counts: someone asked for it. An agent can also ask for a page's own address with the header `Accept: text/markdown` and get Markdown back; a server log does not keep that header, so those requests are not counted here. Markdown copies are never page views: Traffic › Pages leaves them out.

Files are listed for the last 30 days: what needs a look and the files' answers cover those days. The requests, the share from AI, the chart and who asked cover the whole range. A section with no file listed says "not listed", not 0. Each day keeps its 50 busiest files and 20 busiest names per group, and sums the rest, so the totals always add up. Agent files are counted from this release on, for the whole site (a page group says so). Every figure has its own second count from the raw log lines.

## How the figures are checked

Every figure here is counted twice, by two pieces of code written apart: the daily count, and an independent recount from the raw log lines. If the two disagree, the day is withheld until someone finds out why. A withheld day is left out of every total and named at the top of the page.
