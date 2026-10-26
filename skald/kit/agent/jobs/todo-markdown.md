## Step __N__. Markdown copies AI asks for: one rule

The to-do "Give AI the Markdown copies it asks for": AI fetchers asked for `<page>.md`
addresses of pages the site has, and got "not found". The rows: __ROWS__. Each row has `path`
(the `.md` address asked for), `ai` (how often) and `page` (the live page it copies).

**Check first** (step __STEP_WHERE__): does the site already serve `.md` copies for some pages
(a real file, a route such as `app/[...slug]/route.ts`, a plugin)? Then this is a gap in that
rule, not a missing rule: fix the gap only. Does any real `.md` file on the site have to keep
working (a `README.md`, docs)? The rule must leave real files alone.

Ask the user once which they want, and say the first is the quick one:

1. **Redirect** each `.md` address to its page: one server rule, real `.md` files left alone.
   - nginx: `location ~ \.md$ { try_files $uri @skald_md; }` and
     `location @skald_md { rewrite ^(.+)\.md$ $1/ permanent; }` (`$1/` when the site's pages end
     in `/`; `$1` when they do not: compare a few rows' `path` and `page`)
   - Apache (`.htaccess` or the site's file): `RewriteEngine On`,
     `RewriteCond %{REQUEST_FILENAME} !-f`, `RewriteRule ^(.+)\.md$ /$1/ [R=301,L]`
   - Next.js, Vercel, Netlify: one pattern redirect, `/:path*.md` to `/:path*/` (check the
     framework's pattern syntax), permanent.
   - Rows whose `page` does not follow the pattern: one line each, as for old pages.
2. **Serve real Markdown copies**: more work, better for AI readers. Only when the site's code
   makes it simple (a static site generator that can write `.md`, a CMS with the text as
   Markdown). Show the user the plan before you write it.

Then, with the user's yes: test, reload or deploy, and check two rows:
`curl -sI 'https://__SITE__<path>'` answers 301 to the page (or 200 with Markdown). The rule
you added goes in the report as `change`.
