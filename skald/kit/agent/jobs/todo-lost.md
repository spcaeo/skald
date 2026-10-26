## Step __N__. Old page addresses: redirect each one, or answer "gone"

The to-do "Send old pages somewhere useful": people, search engines and AI still ask for old
page addresses that now answer "not found". The rows: __ROWS__. Each row has `path` (the old
address), `people`, `search` and `ai` (how often each asked), `target` (the closest live page
Skald found, or none) and `match`: `exact` (the same page, moved), `likely` (the same topic),
`guess` (a loose match: its section) or `none`.

**Check first** (step __STEP_WHERE__): the rows already redirected or gone are left as they are.

Then sort the rest into three groups, most asked first:

1. **`exact` and `likely` with a target:** a permanent redirect (301) to the target. First check
   the target answers 200: `curl -s -o /dev/null -w '%{http_code}\n' 'https://__SITE__<target>'`.
   A target that does not answer 200 moves to group 3.
2. **`guess`:** show the user these rows and their suggested section in one short table, and ask
   once: "Redirect these to the section shown, answer 'gone' (410), or leave them?" Do what
   they say, row by row if they pick rows.
3. **`none`** (no close live page) and targets that failed: ask the user once, with the list:
   "Nothing on the site is close to these. May I answer 'gone' (410) for them? Or name a page
   for any of them." A 410 only for the rows they agree are gone. Never send them to the home
   page unless the user asks for that.

Write the lines in the syntax of the place you found (one line per row; keep the path exactly
as the row has it, with or without its last `/`):

- nginx: `location = /old/ { return 301 /new/; }` and `location = /old/ { return 410; }`
- Apache: `Redirect 301 /old/ /new/` and `Redirect gone /old/`
- Next.js `redirects()`: `{ source: '/old/', destination: '/new/', permanent: true }` (Next.js
  redirects cannot answer 410: put the gone rows in `left` and say why, or use the site's
  middleware if it already has one)
- `vercel.json`: `{ "source": "/old/", "destination": "/new/", "permanent": true }`
- Netlify `_redirects`: `/old/  /new/  301` and `/old/  /404.html  410`
- WordPress Redirection: one redirect per row (301), or "410 gone" as its action
- Cloudflare Bulk Redirects: a CSV of `source,target,301` for the user to import

A path with a space, a quote, a `;` or other characters the place cannot take as they are:
leave it out, put it in `left` with "needs a hand-written rule".

Then, with the user's yes: test (`nginx -t` or the equivalent), reload or deploy, and check a
few rows with `curl -sI 'https://__SITE__<path>'`: the status and the `Location` must be what
you wrote. Keep the exact lines you added: they go in the report as `change`.
