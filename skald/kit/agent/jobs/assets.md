## Step __N__. Find where the pages load their own files

Skald counts a visit as a person when the browser also loads the page's own files (scripts,
styles, images). It needs to know where this site serves them from.

**Check first.** Skald looks for these paths now: __ASSETS_NOW__. What the site check found
is above ("Its own files are served from"). If the site's pages load their own files from
those paths, this job is done already.

Find the paths:

1. Look at a few of the site's pages as a browser gets them, for example:

       curl -fsSL 'https://__SITE__/' | grep -oE '(src|href)="/[^"/]+/' | sort | uniq -c | sort -rn

2. Read the framework's build settings too. The usual paths: Next.js `/_next/static/`,
   WordPress `/wp-content/` and `/wp-includes/`, Nuxt `/_nuxt/`, Astro `/_astro/`, Vite or
   SvelteKit `/assets/` or `/_app/`, Gatsby `/static/`, a CDN folder such as `/cdn/`.
3. Keep only paths on the site's own address, each starting and ending with `/`, that every
   page loads (scripts and styles first). Not `/api/`, not a page path, not another host.
   At most 10.

Change nothing in Skald or on the site. Put them in the report as `asset_paths` (and the
framework): the user applies them in Skald with one click.
