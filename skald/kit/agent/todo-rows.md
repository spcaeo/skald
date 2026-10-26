## Step __N__. Get every row of each to-do

Skald hands you the rows itself: nothing to download from a page, nothing to copy. One
command per to-do, in a shell. The report key from the keys file goes into curl as a header
through a pipe, so it is never on a command line or shown; the rows go into a file only you
can read (mode 0600):

__FETCH__

- **HTTP 200:** the file is a JSON object: `title`, `proof`, `todo`, `check`, `columns` (each
  column's `key` and `label`), `rows` (every row) and `rows_total`. Read it with a small
  script, never by printing thousands of rows into the chat, for example:

      python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["title"], "-", d["rows_total"], "rows"); [print(r) for r in d["rows"][:5]]' __ENV_DIR__/__SITE__.todo-<id>.json

- **Anything else:** the file holds only Skald's words (no data). Show them and remove it.
  HTTP 403 means the report key was not sent: run the command again as it is. HTTP 410 means
  the line ended: ask the user to press Fix this again in Skald.

The rows are page paths and counts, or where visits came from. They never hold a visitor's
address or email; a value that looked like one is shown as `[removed]`: leave that row out
and say so in the report.

Remove these files when you are done (the last step says when).
