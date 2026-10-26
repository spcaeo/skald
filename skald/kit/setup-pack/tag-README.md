# The script tag for __SITE__

`script-tag.html` holds one line:

    __TAG__

Put it once in the `<head>` that every page of the site shares:

- Next.js App Router: `app/layout.tsx` (or `.jsx`), inside `<head>`.
- Next.js Pages Router: `pages/_document.tsx`, inside `<Head>`.
- WordPress: the theme's `header.php` before `</head>`, or a header-code plugin.
- A site builder: its "custom code in head" setting.
- Plain HTML: the `<head>` of every page, or the shared template.

Keep `data-site="__SITE__"` exactly, and add the tag only once.

The tag counts what a log cannot see: clicks, form steps, scroll and booking embeds. It never
sees AI crawlers or bots, so a server log is still the best source (`../logs/`). Nothing
changes on your web server: the page loads the script from Skald and sends its events there.
The page's host name must be one of the site's host names in Skald (Settings > Site details).

Check: open a page in a normal browser window (Do Not Track off). Within a few minutes it
shows on __DASHBOARD__.
