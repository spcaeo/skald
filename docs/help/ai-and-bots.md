# AI & bots: what each crawler costs

See which AI assistants, search engines and bots fetch your site, how much work each one makes for your server, and what one of them did in detail. This guide covers the cost table, the detail view, and what each figure means.

## Where to find it

Open **AI & bots**. The table **What each crawler costs** is on two tabs:

- **Crawlers**: AI collecting pages for training or AI search, search engines, and bots and scanners.
- **Assistants**: AI assistants fetching a page because someone asked them a question. Here it is headed **What each assistant costs**.

Pick the period at the top as on any other page: today, yesterday, a number of days, or your own dates.

## What the columns mean

| Column | What it is |
|---|---|
| Name | The name the crawler gives itself. Bots without a known name go by the name in their user agent. Scanner probes are one row, **(scanner probes)**; everything else a scanner asked for that day (its home page, say, between two probes) is another, **scanner (asked for secret or config files)**. A visitor that asked for 5 or more scanner paths your site does not have is **scanner (asked for many missing probe paths)**, and a browser that checked pages with `HEAD` requests is **browser-like link checker (HEAD requests)**. |
| Requests | Every request it made in the period. |
| Bytes sent | How much your server sent it, from the size field of each log line. |
| Mean time | How long your server took per request, on average. |
| p90 time | 9 in 10 of its requests took no longer than this. Shown for a single day only. |
| Errors | The share of its requests that got an error (4xx or 5xx). |
| Distinct paths | How many different addresses on your site it asked for. |
| Re-crawl | Requests per distinct path: 3.0× means it fetched each path three times on average. |
| Last seen | Its last request in the period. |

Select a name to open its detail.

An assistant is called by the name people know it by: **ChatGPT**, not `chatgpt.com`. A bot keeps its own name, because it is one fetcher, not the assistant. A bot that reads a page only when one user asks the assistant about it (`ChatGPT-User`, `Claude-User`, `Perplexity-User`) is marked **user fetcher**.

A person who clicks a link in an AI answer is counted as a person, with the assistant as the source. Skald knows these assistants by the address they send people from (or the tag they put on the link): **ChatGPT**, **Perplexity**, **Claude**, **Gemini**, **Copilot** (copilot.microsoft.com, copilot.com and Bing's chat), **Meta AI**, **DeepSeek** (chat.deepseek.com), **Grok** (grok.com, and Grok inside X at x.com/i/grok; the rest of x.com is X), **Mistral**, **You.com**, **Phind** and **Poe**, and the Android apps of ChatGPT, Perplexity, Claude, Gemini, Copilot, Meta AI, DeepSeek and Grok. An iPhone app sends no address of its own: its visits count only when the link carries the assistant's tag (ChatGPT adds `utm_source=chatgpt.com`); otherwise they are Direct.

**OAI-AdsBot** is OpenAI's crawler that checks the landing pages of ads placed on ChatGPT. It is listed with the AI crawlers when its address is OpenAI's. A request that uses its name to look for secret files (`.env`, keys) is not believed: it stays under bots, as a scanner, unless the address is checked as OpenAI's.

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
- **From an address checked as theirs**: the share of its requests from an address that really belongs to its owner. Requests that use a crawler's name from an address that is not theirs are counted apart, as "claims to be ...". The check needs the owners' published address lists, which the daily run fetches. A Docker install does this by default from this release on; before, no Docker install checked, so earlier days show every request as not checked, and a fake crawler counted as the crawler it named. `doctor` says "crawler checks off" when they are off.
- **Requests per day**, as a chart.
- **Pages it fetched**: the pages it asked for most.
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

**Pages AI can't read well** is on **AI & bots › Assistants**: every page where AI got an error, a 404 or a slow answer, asked for a Markdown copy that does not answer, or that robots.txt shuts them out of, worst first. Filter it by kind with the chips above it. Select a row to open that page's AI readiness. A crawler that robots.txt keeps out of the whole site is said once, above the list.

What AI got back is recorded from this release on. A page group (view) shows it for the whole site only. robots.txt says what a crawler may read; assistants that fetch for one user (ChatGPT-User, Perplexity-User) may not follow it.

## How the figures are checked

Every figure here is counted twice, by two pieces of code written apart: the daily count, and an independent recount from the raw log lines. If the two disagree, the day is withheld until someone finds out why. A withheld day is left out of every total and named at the top of the page.
