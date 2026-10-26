## Step __N__. The sitemap address crawlers ask for

The to-do "Fix the sitemap address crawlers ask for": search engines or AI crawlers asked for
a sitemap address that answered "not found". The rows: __ROWS__. Each row has `path` (the
address asked for), `search` and `ai` (how often) and `status` (what it answered).

**Check first:** which sitemap does the site have now?

- `curl -s 'https://__SITE__/robots.txt' | grep -i '^sitemap:'`
- `curl -sI 'https://__SITE__/sitemap.xml'`, `.../sitemap_index.xml`, `.../wp-sitemap.xml`
- the code: Next.js `app/sitemap.ts` or `next-sitemap`, WordPress core or Yoast or Rank Math,
  the static site generator's sitemap setting.

Then, for each row:

1. **The site has a sitemap at another address:** a permanent redirect (301) from the row's
   `path` to it, in the place found in step __STEP_WHERE__ (the same syntax as an old page).
2. **The site has no sitemap:** tell the user, and offer to turn on the framework's or the
   CMS's own sitemap at the address asked for. Do it only with their yes.
3. **The address answers now:** leave it, count it as fixed.

If `robots.txt` names no sitemap, or the wrong one, say so in `notes`: it is not on this
to-do's list, so do not change it here unless the user asks.

Then, with the user's yes: test, reload or deploy, and check each row with
`curl -sI 'https://__SITE__<path>'`. The lines you added go in the report as `change`.
