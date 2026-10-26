## Step __N__. Find where this site's redirects and server rules live

Every fix below is a redirect, a "gone" answer or one server rule. Before you write any, find
the ONE place this site already keeps them. Look, change nothing yet.

**Check first**, in the site's repository and on its server (what the site check found is
above):

- **nginx:** `sudo nginx -T 2>/dev/null | grep -nE 'server_name|include|return 30[12]|return 410|rewrite'`.
  The site's `server { }` block, or a file it includes (often `redirects.conf` or
  `conf.d/*.conf`).
- **Apache:** `.htaccess` in the web root, or the site's file under `/etc/apache2/sites-enabled/`
  (`apachectl -S` names it). Look for `Redirect`, `RedirectMatch`, `RewriteRule`.
- **Next.js:** `next.config.js` / `.mjs` / `.ts`, `async redirects()`; or `middleware.ts`; or a
  file of old addresses the site already reads.
- **Vercel:** `vercel.json`, `"redirects"`. **Netlify:** a `_redirects` file in the publish folder,
  or `[[redirects]]` in `netlify.toml`.
- **WordPress:** the Redirection plugin (Tools > Redirection; `wp redirection` with WP-CLI),
  Yoast or Rank Math's redirects, or `.htaccess`. Use the one the site already uses.
- **Cloudflare:** Bulk Redirects, Redirect Rules or a Worker (`wrangler.toml` in the
  repository). Those live in Cloudflare's dashboard: write the list for the user to import,
  unless you can change them with the user's own tool and their yes.
- **A static site generator** (Hugo, Jekyll, Astro, Eleventy...): its own redirects setting, or
  the host's (above).

Pick the place the site already uses. Several, or none? Ask the user one question: "Your site
keeps redirects in <A> and <B>. Which one should I add these to?" (or "where would you like
them?"), and wait.

Then, for each row, check whether it is handled already: search that place for the path, and
ask the live site with `curl -sI 'https://__SITE__<path>'` (a `301`/`308` with a `Location`, or a
`410`, means it is done). Leave those as they are and count them as already fixed.
