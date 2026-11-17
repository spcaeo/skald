"""How much of a page's path is kept: the numbers both roads share (#71).

Every figure keyed by a page (pages read, landing pages, 404s, slow pages,
journeys, the pages an assistant fetched, live and Right now) keeps the
path without its query, cut to PATH_CHARS characters. Both counting roads
cut at the same place, so a day's two counts compare page by page.

Before #71, every one of them kept only the first OLD_PATH_CHARS
characters. A longer address was stored cut short with no sign of it:
the dashboard drew `/blog/5-must-have-features-of-...-for-trash-va` as
the page and opened it, a 404, and two pages that differ only after the
70th character were counted as one row.

  PATH_CHARS      kept from now on. Real pages are well under it; a path
                  that is longer (a scanner's probe, mostly) is still cut,
                  at this length.
  OLD_PATH_CHARS  what days counted before #71 kept. A path stored at
                  exactly this length may be a longer address cut short:
                  the dashboard marks it (pathnames.js) and opens nothing,
                  until those days are counted again from the raw log
                  (`backfill --force`) where the log still holds them.

The JavaScript keeps the same numbers in webapp/js/pathnames.js; a test
holds the two equal. Each module cuts by its own code; only these numbers
are shared.
"""

PATH_CHARS = 512
OLD_PATH_CHARS = 70
