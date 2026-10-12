# llms_txt.json: a suggested /llms.txt

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply. Built by `llms_txt.py` for the site
and each view, on every dashboard update. **Skald never writes it to the
website**: the owner checks it and publishes it at `/llms.txt` if they want.

The format is llms.txt (<https://llmstxt.org>, checked 2026-10-12): an H1 with
the site's name, a blockquote summary, then H2 sections of
`- [name](url)` links with an optional `: notes`; a section named
`Optional` holds links an assistant may skip.

**What is ranked.** The last 90 whole days (yesterday back), recorded days
only (`ok`): partial, withheld and missing days are left out and named. Each
page's people's page views plus AI assistants' fetches made for someone's
question (`views` + `ai_asked` of the per-page blob, day kind `pages`, both
recounted per page by `audit_extras.py`). Training crawls and search crawls
do not rank a page. `/x` and `/x/` are one page; the spelling read most is
linked. **No figure is published**: the file is a list of links, and the
ranking is the only use of the figures, so it needs no second count of its own.

**What is left out.** A page is a 2xx document (no assets, redirects or 404s
reach the per-page blob). Also left out: Skald's own paths (`/traffic...`)
and private ones (sign-in, account, cart, checkout, search, admin, API and
the like: `llms_txt.PRIVATE`, by first path segment); paths robots.txt
disallows for `User-agent: *` (the copy `robots.py` fetched); pages the old-URL
map (`report.redirect_map`) redirects or calls gone; pages that answered
404 or 410 after they were last served; paths of 70 characters or more
(history keeps 70, so they may be cut short) unless the page list names
them; pages nobody read. With the website's page list (`report.pages_meta`)
only the pages it lists are kept.

**Titles and summary.** A page's title and note are `title` and `description`
from the page list; without one, the path is the link's name. The H1 is the
site's name. The summary is the home page's `description` when the list has
one, otherwise a line asking the owner to write it.

**Sections.** The first 30 pages (`LIMIT`) are grouped by top-level section:
`/blog/...` under "Blog", with a locale prefix the page list names skipped
("Blog (fr)"); a page with no section is under "Main pages". Sections come in
the order of their best page. The next 20 (`OPTIONAL`) are under "Optional".

| field | type |
|---|---|
| `ok` | `true` when there is a file to suggest |
| `why` | string or null: why there is none (no recorded day; no page left) |
| `period` | `{"first","last","days": 90,"counted": recorded days,"left_out": [{"day","state"}]}` (days before history starts are not listed) |
| `ranked_by` | the ranking, in words |
| `titles` | `"website"` (from the page list) or `"paths"` |
| `base_url` | `https://` and the site's `www.` host if it has one, else its first host |
| `pages[]` | `{"path","url","title" (or null),"note" (or null),"section" (null for an optional page),"optional": bool}`, best first |
| `left_out_paths` | how many paths (not requests) were left out, by reason: `{"private","cut_short","robots_txt","redirected_or_gone","not_in_page_list","not_read": int}` |
| `text` | the llms.txt itself, or null |

Also: `skald llms-txt [--site X] [--out FILE]` prints it (or writes FILE),
with the period and left-out days on stderr; the MCP resource
`skald://sites/<site>/llms.txt` returns `text`.
