# Instructions for an AI coding agent: set up Skald for __SITE__

You are setting up Skald (server-log web analytics) for the website __SITE__. Follow these
steps in order. Do not guess: when a step needs a fact you cannot find in the code or on the
server, ask the user one plain question and wait.

Skald page of this site: __DASHBOARD__
Send address for the site's logs: __INGEST_URL__
Lead address: __LEAD_URL__

__SECRETS__

## Rules

1. Secrets (the sending token, the lead secret) go only in environment variables or the
   host's secret settings (Vercel or Netlify environment variables, Cloudflare secrets, the
   server's environment). Never write them in the site's code, never commit them to git,
   never print them in the chat or in a log. If you see one in the user's code, say so.
2. Read `secrets.env` in this folder only to copy a value into a secret setting; never echo it.
3. Change only what the steps say. Never change nginx, Apache or the site's own pages beyond
   adding the script tag. Never restart a web server without the user's yes.
4. Commands that change a server need the user's yes before you run them.

## Step 1. Find out how the site is hosted

Look at the site's repository first:

- `vercel.json`, a `.vercel` folder, or `next.config.*` with a Vercel deploy: **Vercel** (case C).
- `netlify.toml` or a `netlify` folder: **Netlify** (case C).
- `wrangler.toml`, or the user says Cloudflare is in front of the site: **Cloudflare** (case B).
- `Dockerfile`, `docker-compose.yml`, nginx or Apache config files, or a deploy script that
  copies to a server over SSH: **own Linux server** (case A).

If the repository does not settle it, ask the user: "How is __SITE__ hosted: your own Linux
server (with SSH access), Cloudflare, Vercel, Netlify, or something else?" For case A you
need SSH access to the server, or the user runs the commands you give them.

## Step 2. Connect the logs (do the one case that fits)

### Case A. Own Linux server

1. Copy `logs/install-server.sh` to the server as `skald-install-__SITE__.sh`.
2. Run `sudo bash skald-install-__SITE__.sh --dry-run` and read its output: it says how it
   will run (Docker or systemd) and which access log it found.
3. If the log is right, run `sudo bash skald-install-__SITE__.sh --yes`. If it found the
   wrong log, run it with `--log <full path of the site's access log>` instead. When the
   installer has no token inside (see above), give it the token through the environment,
   never on the command line: `export SKALD_SHIP_TOKEN=<the token>` in the server's shell
   (from `SKALD_INGEST_TOKEN` in `secrets.env`, without printing it), then
   `sudo --preserve-env=SKALD_SHIP_TOKEN bash skald-install-__SITE__.sh --yes`. Or let the
   user paste it when the installer asks.
4. Run `sudo skald-ship-check`. Every line must say OK. Fix each PROBLEM with the fix it shows.

### Case B. Cloudflare

Follow `logs/cloudflare.md`. Put the token in the Worker's secret `SKALD_TOKEN` (with
`npx wrangler secret put SKALD_TOKEN`, or the Cloudflare dashboard), never in `wrangler.toml`.

### Case C. Vercel or Netlify

Follow `logs/vercel-netlify.md`. The drain is set in the host's dashboard; if you cannot
reach it, give the user the exact steps from that file.

## Step 3. Add the script tag

Put the line in `tag/script-tag.html` once, in the site's shared `<head>`, so every page has it:

- Next.js App Router: `app/layout.tsx` (or `.jsx`), inside `<head>`, as a plain `<script>` tag
  (or `next/script` with `strategy="afterInteractive"` and the same `src` and `data-site`).
- Next.js Pages Router: `pages/_document.tsx`, inside `<Head>`.
- WordPress: the theme's `header.php` before `</head>`, or a header-code plugin.
- Plain HTML or another framework: the shared layout or template's `<head>`.

Keep `data-site="__SITE__"` exactly. Do not add it twice. Commit this change like any other.

## Step 4. Leads (only if the site has a form that makes leads)

1. Find where the backend handles the form (an API route, a server action, a form handler).
2. Add the file from `leads/` for the backend's language, as its README says, and call it
   once after the lead is saved. It signs each lead with the lead secret.
3. Put `SKALD_LEAD_URL` and `SKALD_LEAD_SECRET` in the backend's environment variables (the
   host's secret settings), never in code.
4. __LEAD_SECRET_NOTE__

## Step 5. Check, then report

1. Open https://__SITE__/ (or ask the user to), then wait two to five minutes.
2. Case A: run `sudo skald-ship-check`. All other cases: ask the user to open
   __DASHBOARD__ and look at Settings > Collect data > Send logs: it says what arrived and when.
3. Report back to the user, in short plain sentences: how the site is hosted, which case you
   did, which files you changed (paths), which secret settings you set (names only, never the
   values), what the checks showed, and anything left for them to do.

Help: __HELP__
