# AI readiness per page: the day kind `ai_status` and `ai_ready.json` (2.35)

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file under
1000 lines); the rules there apply. **Can AI crawlers and assistants read a page
well?** Skald answers from the server's log and its own copies of robots.txt and
the sitemap only. It asks no AI anything and makes no paid call.

Where it shows:

- **Traffic › Pages › a page's story: "AI readiness"**, six lines, each with a state
  (good, needs attention, not known), one line of evidence and what to do
  (`js/ai-ready.js` works them out, `js/tabs/aiready.js` draws them). The address
  `psec=ai` opens the story at this block (docs/ROUTES.md).
- **AI & bots › Assistants: "Pages AI can't read well"**, the site's worst pages
  first, with a filter in the address (`arw`). A row opens the page's story at its
  AI readiness.

## Day kind `ai_status` (what AI got back, by address)

Built by `ai_status.py` on every collected day, for the whole site only (a view's
tally keeps none). Every request of an answer engine (classify.py's names, both
tiers: "asked", a fetch made for someone's question, and "training"), by path (no
query string, first 200 characters) and crawler name:

| field | type |
|---|---|
| `answers` | `{path: {name: {status: n}}}`: every request answered with a status other than 200 and 304 (a redirect, a 404, a 403, a 5xx...), and every request for a Markdown copy (the path, trailing "/" aside, ends `.md`, `.mdx` or `.markdown`: `not_pages.RULES["markdown"]`), whatever it was answered. The status as the log writes it |
| `slow` | `{path: {name: n}}`: requests the server took `slow_ms` (1,000) ms or more to answer, whatever the status |
| `plain` | `{name: n}`: the rest (a 200 or 304 for an address that is no Markdown copy), by name only, so the blob stays small |
| `timed` | `{name: n}`: requests whose line records the server's time. `slow` is measured on those only; a log without the time has `timed` 0, and slow is not recorded (the page says so) |
| `slow_ms`, `keep` | the threshold and the number of paths kept a day (1,000) |
| `folded` | `{"answers": n, "slow": n}`: how many paths were summed into `"(all others)"` (0: every path is listed) |

`answers` and `slow` keep their `keep` paths with the most requests (ties by path)
and sum the rest into one `"(all others)"` path per name. So every sum holds: per
name, answers plus plain are that name's requests (the day's engine counts); per
name, slow <= timed <= requests. `verify.py` checks those sums before a day is
stored. On example.net's real log (2026-10-21 to 25) a day listed 394 to 573 paths
and took 30 to 43 KB; nothing was folded at 1,000.

**Second count:** `audit_ai_status.py` (`audit_more.RECOUNTS`) counts the raw lines
again with its own reading of the path, the copy ending and the status, and compares
every kept path status by status and name by name, the folded rest, the plain
requests and the timed lines.

**Before 2.35** no day has `ai_status`. Those days are "not recorded" (never 0): the
lines say what AI got back is not recorded yet. A recount or backfill of a day whose
raw log is still kept fills it in.

## ai_ready.json

Built by `ai_ready.py` on every dashboard update (`data_more.FILES`). A view (page
group) gets `{"whole_site_only": true}` and the page says to choose All pages.

| field | type |
|---|---|
| `crawlers` | `[[token, role]]`: the 9 main AI crawlers checked: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, Claude-User, PerplexityBot, Perplexity-User, Google-Extended, Applebot-Extended; role `training`, `search` or `asked` |
| `robots` | `{url, fetched_at, ok, error, missing, crawlers}` from the copy `robots.py` keeps. `crawlers`: `{token: {"agents": [the User-agent lines that apply], "rules": [[allow or disallow, pattern]], "root": may it fetch "/"}}`, or null when Skald has no copy (the lines say "not known", never a guess). `missing`: no copy and the last try was answered with a 4xx other than 429, so the site has no robots.txt and every crawler may read every page (RFC 9309: an unreachable robots.txt in the 4xx range means no rules) |
| `sitemap` | `{enabled, day, fetched_at, count, pages}`: the list `sitemap.py` keeps for today; `pages` `{page: its lastmod or null}`, null when no list is kept |
| `window` | `{days: 30, first, last, of, recorded, since, folded}`: the last 30 days to yesterday; `of` days with figures (whole or partial), `recorded` of them with `ai_status`, `since` the first of those, `folded` the days that summed some addresses |
| `pages` | `{page: {"self": {name: {status: n}}, "slow": {name: n}, "copies": {path: {name: {status: n}}}}}` over the window |
| `attention` | `{"total": n, "rows": [...]}`: the pages AI cannot read well, worst first, at most 100 rows |

**A page** is its path cut at "?" and "#", with a "/" added unless it ends with one
(as page_trends.json). A Markdown copy belongs to the page it copies: `/a/b.md`,
`/a/b/index.md` and `/a/b/.md` are `/a/b/`'s; `/index.md` and `/.md` are `/`'s.
Only addresses shaped like a page count: a Markdown copy, or an address
`ai_formats.format_of` calls a page (also with a closing "/" taken off, so
`/sitemap_index.xml/` is not one), with no part starting with "." (`/.env`,
`/.git/`), that the not-a-page list (`not_pages.py`) does not name. Files, feeds,
APIs, sitemaps, llms.txt and image resizers are left out.

**robots.txt is read the RFC 9309 way** (`robots_match.py`; the page has a twin,
`js/robots-match.js`): a crawler's rules are every group naming its product token
(any case), else every `*` group's; the longest matching rule wins and an Allow wins
a tie; `*` matches anything and a final `$` the end; paths and patterns are compared
with percent-encoding made the same. Python's `urllib.robotparser` takes the first
match, which is not the standard, so it is not used. A crawler that robots.txt keeps
out of the whole site is said once, on the list's top, not on every page.

**A row** (`attention.rows[]`): `{path, listed, copy_errors, copy_404, not_found,
server_errors, blocked, robots, redirects, slow, by}`.

- `copy_errors`: a Markdown copy answered AI with anything but 2xx or 304;
  `copy_404` of them 404 or 410.
- `not_found`: the page answered AI 404 or 410. `server_errors`: 5xx.
  `blocked`: another 4xx (401, 403, 429...).
- `robots`: the main crawlers its path shuts out while they may fetch "/".
- `slow`: answers of a second or more.
- `redirects`: 3xx but 304. **Said, not a need**: the log does not say where a
  redirect leads, and a site that sends AI to each page's Markdown copy on purpose
  redirects every page. A page with only redirects is not listed; its errors line
  says "good" and names the redirects.
- `listed`: the page is in the sitemap (null: no list kept). `by`: the crawler names.

A page with at least one need is listed. Worst first: the four answer counts
together, then the crawlers shut out, then slow answers, then redirects, then the
path. A sitemap page no AI asked for is listed for robots.txt only.

**The six lines** (`js/ai-ready.js readiness`):

| line | good | needs attention | not known |
|---|---|---|---|
| robots.txt | all 9 may read this path | a crawler is kept out (the rule and its group shown, an `Allow:` snippet to copy) | no copy of robots.txt |
| Crawler errors | no error or slow answer (redirects named) | 5xx, another 4xx, slow answers | not recorded, or a day summed addresses and nothing was found |
| In the sitemap | listed, with its lastmod | not in the sitemap | the sitemap is not read, or no list kept |
| Markdown copy | every copy asked for answered 2xx or 304 | a copy answered anything else ("AI asked for the Markdown copy 6 times; it answered 404 each time") | AI asked for no copy (so Skald cannot tell if one exists), or not recorded |
| AI asking for a 404 | no 404 or 410 | the page answered 404 or 410 | not recorded, or summed |
| Last AI read | an assistant fetched it for someone in the last 30 days (page_trends.json's `fetches`, L1, not counted again) | none did | page_trends.json has no fetches |

**Second count:** `audit_ai_ready.py` (`audit_more.DAILY`). It shares only the name
lists (the 9 crawlers, the Markdown endings) and works the whole file out again from
what is stored, with its own code: its own SQL over the stored `ai_status` days, its
own robots.txt reading (regular expressions, its own grouping and percent rules), its
own sitemap reading (the list file must hash to its name), its own page shape
(`audit_ai_formats.kind_of`, `audit_not_pages.Marker`), its own needs and order. A
600-case random test holds `js/robots-match.js` to `robots_match.py`, and a
1,000-case one holds `robots_match.py` to the audit's reading.

## Not covered

- Where a redirect leads: nginx's log has no Location header.
- Whether ChatGPT-User or Perplexity-User obey robots.txt: the line says what the file
  allows, not what each assistant does.
- Days before 2.35 (no `ai_status`), unless a recount or backfill fills them from a
  raw log still kept.
- Views (page groups): the whole site only.

## Feeding the to-do list later

`attention.rows` is made to feed Insights' to-do list without a new count: one item
per row, its title from `needWords(row)`, its action from `needAction(row)`, and its
link `#traffic/pages?page=<path>&psec=ai`. A whole-site robots.txt block
(`wholeSite(file)`) is one item of its own. An item is done when its row leaves the
list on a later update.
