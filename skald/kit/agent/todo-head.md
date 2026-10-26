# Fix Skald's to-dos for __SITE__: the steps for an AI agent

Skald (server-log web analytics) found problems on the website __SITE__ and the user asked you
to fix them. This line carries __COUNT__:

__TODO_LIST__

Follow these steps in order. Skald gives you every row of each to-do (step __STEP_ROWS__): work
from that file, never from a list you guess. When a step needs a fact you cannot find in the
code or on the server, ask the user one plain question and wait for the answer.

This page holds no secret. Its links work until __EXPIRES__ (UTC); the keys can be taken once.

## The site

- Site: __SITE__
- Skald page of this site: __DASHBOARD__
- The to-dos in Skald: __INSIGHTS__

What Skald's site check found:

__FOUND__

## Rules

1. **Look before you change.** Each job starts with **Check first**: find where this site keeps
   what you would change, and what is there already. Change only what is missing. A row that
   is fixed already is reported as fixed, not changed again.
2. **Never touch what the to-do does not list.** Only the rows Skald gives you, only the files
   that hold them. No clean-up, no refactor, no other redirect, no other page.
3. **Ask before any server or web-server change**: nginx, Apache, a CDN or host setting, a
   restart, a deploy. Show the exact lines and where they go, say what they change, and wait
   for a yes. Test the settings before any reload: `nginx -t`, `apachectl configtest`, or the
   host's own check. Never reload when the test fails.
4. A change in the site's own repository (a redirects file, `next.config.js`, `vercel.json`,
   `_redirects`, `.htaccess`, a page) is made as a normal change the user can review: on a new
   branch when the repository uses them, with a plain commit message. Do not push or deploy
   without the user's yes.
5. Never print, echo, log or commit a secret, and never paste one in the chat. Never `cat` the
   keys file. Never paste the code or the keys anywhere but the commands shown here.
6. Take the keys only with curl or wget in a shell, into the file (step 1). Never with a web
   reader or fetch tool.
7. Never change a setting in Skald itself. Report what you did (the last step); Skald marks a
   to-do done only from your report, and re-checks it on the days after.
8. If an answer says "Too many tries", wait a minute and try again.
