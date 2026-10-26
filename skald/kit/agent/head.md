# Set up Skald for __SITE__: the steps for an AI agent

You are setting up Skald (server-log web analytics) for the website __SITE__. This line asks
you to: __JOB_LIST__. Follow these steps in order. Do not guess: when a step needs a fact you
cannot find in the code or on the server, ask the user one plain question and wait for the
answer.

Change only what is missing. Each job starts with **Check first**: when the job is done
already, say so, leave it as it is, and report it as `already`.

This page holds no secret. Its links work until __EXPIRES__ (UTC); the keys can be taken once.

## The site

- Site: __SITE__
- Skald page of this site: __DASHBOARD__
<!-- if logs -->
- Send address for the site's logs: __INGEST_URL__
<!-- end -->
<!-- if logs|lead -->
- Lead address: __LEAD_URL__
<!-- end -->
<!-- if logs|script -->
- Script tag: `__TAG__`
<!-- end -->
<!-- if mcp -->
- Skald's MCP address: __MCP_URL__
<!-- end -->

What Skald's site check found:

__FOUND__
<!-- if logs -->

Which way fits, by that check: __WAY__
<!-- end -->

## Rules

1. Never print, echo, log or commit a secret (a token, the lead secret, a tool's secret), and
   never paste one in the chat. Never `cat` the keys file. If you see a secret in the site's
   code, tell the user.
2. Secrets go only in environment variables, the host's secret settings, or the keys file
   (mode 0600, outside the site's repository). Copy a value from the file without showing it:
   `grep '^NAME=' __ENV_FILE__ | cut -d= -f2- | <a command that reads it from its input>`.
3. Never paste the code or the keys anywhere but the commands shown here: not into another
   chat, a ticket, a commit, or any file in the site's repository.
4. Ask the user before any command that changes a server (installing, copying a file to it,
   restarting a service), and before any change to nginx, Apache or another web server's
   settings. Show the command, say what it changes, and wait for a yes.
5. Change only what these steps say. Keep `data-site="__SITE__"` exactly.
6. Take the keys only with curl or wget in a shell, into the file (step 1). Never with a web
   reader or fetch tool: it could put the keys in the chat. Skald refuses that and keeps the
   keys unused.
7. If `sudo` asks for a password you do not have, give the user the exact command to run
   and wait for them to say it is done.
8. If an answer says "Too many tries", wait a minute and try again.
9. Never change a setting in Skald itself. Report what you found; the user applies it in
   Skald with one click.
