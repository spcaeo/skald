## Step __N__. Add the script tag

**Check first.** Is the tag on the site already? Search the site's code and its live home
page:

    grep -rIl --exclude-dir=node_modules --exclude-dir=.git 'traffic-js/skald.js' .
    curl -fsSL 'https://__SITE__/' | grep -c 'traffic-js/skald.js'

If the shared `<head>` holds it once, with `data-site="__SITE__"`, this job is done already:
skip to the next step. If it is there twice, or with another `data-site`, fix only that.

Put this line once, in the site's shared `<head>`, so every page has it:

    __TAG__

- Next.js App Router: `app/layout.tsx` (or `.jsx`), inside `<head>`, as a plain `<script>` tag
  (or `next/script` with `strategy="afterInteractive"` and the same `src` and `data-site`).
- Next.js Pages Router: `pages/_document.tsx`, inside `<Head>`.
- WordPress: the theme's `header.php` before `</head>`, or a header-code plugin.
- Plain HTML or another framework: the shared layout or template's `<head>`.

Do not add it twice. Commit it like any other change, with the user's yes, and note where you
put it for the report. Once it is deployed, the second command above counts 1.
