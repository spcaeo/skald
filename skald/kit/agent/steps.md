# Set up Skald for __SITE__: the steps for an AI agent

You are setting up Skald (server-log web analytics) for the website __SITE__. Follow these
steps in order. Do not guess: when a step needs a fact you cannot find in the code or on the
server, ask the user one plain question and wait for the answer.

This page holds no secret. Its links work until __EXPIRES__ (UTC); the keys can be taken once.

## The site

- Site: __SITE__
- Skald page of this site: __DASHBOARD__
- Send address for the site's logs: __INGEST_URL__
- Lead address: __LEAD_URL__
- Script tag: `__TAG__`

What Skald's site check found:

__FOUND__

Which way fits, by that check: __WAY__

## Rules

1. Never print, echo, log or commit a secret (the sending token, the lead secret), and never
   paste one in the chat. Never `cat` the keys file. If you see a secret in the site's code,
   tell the user.
2. Secrets go only in environment variables, the host's secret settings, or the keys file
   (mode 0600, outside the site's repository). Copy a value from the file without showing it:
   `grep '^NAME=' __ENV_FILE__ | cut -d= -f2- | <a command that reads it from its input>`.
3. Never paste the code or the keys anywhere but the commands shown here: not into another
   chat, a ticket, a commit, or any file in the site's repository.
4. Ask the user before any command that changes a server (installing, copying a file to it,
   restarting a service), and before any change to nginx, Apache or another web server's
   settings. Show the command, say what it changes, and wait for a yes.
5. Change only what these steps say. Keep `data-site="__SITE__"` exactly.
6. Take the keys only with curl or wget in a shell, into the file (step 3). Never with a web
   reader or fetch tool: it could put the keys in the chat. Skald refuses that and keeps the
   keys unused.
7. If `sudo` asks for a password you do not have, give the user the exact command to run
   and wait for them to say it is done.
8. If an answer says "Too many tries", wait a minute and try again.

## Step 1. Find out how the site is hosted

Look at the site's repository first:

- `vercel.json`, a `.vercel` folder, or `next.config.*` with a Vercel deploy: **Vercel** (case C).
- `netlify.toml` or a `netlify` folder: **Netlify** (case C).
- `wrangler.toml`, or the user says Cloudflare is in front of the site: **Cloudflare** (case B).
- `Dockerfile`, `docker-compose.yml`, nginx or Apache config files, or a deploy script that
  copies to a server over SSH: **own Linux server** (case A).
- A site builder with no server you can reach (Wix, Squarespace, Webflow and the like):
  **script tag only** (case D).

If the repository and the site check above do not settle it, ask the user: "How is __SITE__
hosted: your own Linux server (with SSH access), Cloudflare, Vercel, Netlify, or something
else?" For case A you need SSH access to the server, or the user runs the commands you give.

Note too, for the report: the site's framework (Next.js, WordPress, Laravel...), and the
paths its own files are served from (scripts, styles, images: `/_next/static/`,
`/wp-content/`, `/assets/`...), each starting with `/`.

## Step 2. Ask the privacy question

Ask the user, in one message, and wait for the answer:

"Skald can keep each visit with the visitor's IP address, so you can look a person up later.
Should it keep visitors' IP addresses? If yes, for how many days? And does your site's privacy
notice cover this? Please send me its link."

Do not change any setting for it. Put the answers in the report (step 8): the user sets them
in Skald, Settings > Data retention > People.

## Step 3. Take the keys, once

In a shell on the machine where you run the commands. The keys can be taken once, so first
check that you have not taken them already:

    grep -qs '^SKALD_INGEST_TOKEN=' __ENV_FILE__.part && mv __ENV_FILE__.part __ENV_FILE__; test -s __ENV_FILE__ && echo "the keys file is there: use it, do not fetch again" || echo "no keys file yet"

If the keys file is there, skip to the end of this step. Else take the keys, in one line. It
puts the file in place only when it holds the keys:

    umask 077 && mkdir -p ~/.config/skald && curl -sS -o __ENV_FILE__.part -w 'HTTP %{http_code}\n' '__KEYS_URL__' && grep -q '^SKALD_INGEST_TOKEN=' __ENV_FILE__.part && mv __ENV_FILE__.part __ENV_FILE__

- **HTTP 200:** the keys are in `__ENV_FILE__`. Do not print it.
  Check the names only: `cut -d= -f1 __ENV_FILE__`. It holds `SKALD_SITE`,
  `SKALD_INGEST_URL`, `SKALD_INGEST_TOKEN`, `SKALD_LEAD_URL`, `SKALD_LEAD_SECRET` (when leads
  were included) and `SKALD_REPORT_KEY` (for step 8).
- **Anything else:** the `.part` file holds only Skald's words, no key. Show them and remove
  it: `cat __ENV_FILE__.part && rm __ENV_FILE__.part`. HTTP 410 means the keys were taken
  already, or the code expired or was cancelled: ask the user to make a new line in Skald
  (__DASHBOARD__, Settings > Add or remove sites) and start again.

If the installer must run on another machine (the web server, over SSH), copy the file there
with the user's yes, and keep it 0600:

    ssh <server> 'umask 077; mkdir -p ~/.config/skald'
    scp -p __ENV_FILE__ <server>:.config/skald/__SITE__.env

## Step 4. Connect the logs (do the one case that fits)

### Case A. Own Linux server

1. On the server, with the user's yes, download the installer (it holds no token):
   `curl -fsSL -o skald-install-__SITE__.sh '__INSTALL_URL__'`
2. Run `sudo bash skald-install-__SITE__.sh --dry-run` and read its output: it says how it
   will run (Docker or systemd) and which access log it found. It changes nothing.
3. If the log is right, run it for real, with the user's yes. The token goes in through the
   environment, never on the command line and never shown:

       ( set -a; . ~/.config/skald/__SITE__.env; set +a
         export SKALD_SHIP_TOKEN="$SKALD_INGEST_TOKEN"
         sudo --preserve-env=SKALD_SHIP_TOKEN bash skald-install-__SITE__.sh --yes )

   If it found the wrong log, add `--log <full path of the site's access log>`.
4. Run `sudo skald-ship-check`. Every line must say OK. Fix each PROBLEM with the fix it shows.
5. **Next.js on its own nginx or Apache only:** without one more log field, pages opened by a
   link inside the site are not counted (only the first page of each visit). Ask the user:
   "Next.js sites need one field added to the web server's log line, so Skald counts the
   pages opened inside the site. It only adds one request header's value to what the log
   already writes: no new port, route or access. May I add it?" With their yes:
   - nginx: back up the file, then end the site's `log_format` with
     ` rsc_prefetch=$http_next_router_prefetch`. Run `sudo nginx -t`; reload
     (`sudo systemctl reload nginx`) only when the test passes.
   - Apache: end the site's `LogFormat` with ` rsc_prefetch=%{Next-Router-Prefetch}i`, run
     `sudo apachectl configtest`, then reload.
   - If the server's nginx also serves other sites, change only this site's log line.
   Without their yes, tell them it is missing and leave it. Put the answer in the report.

### Case B. Cloudflare

The Skald Worker passes every request on unchanged and sends a small record of each to Skald.
It works on every Cloudflare plan.

1. Deploy the Worker: the Deploy to Cloudflare button in `deploy/cloudflare-worker/README.md`
   in Skald's code (ask the user, or whoever runs their Skald, if you do not have it), or by
   hand with Wrangler from that folder.
2. Its address, `SKALD_INGEST_URL`: `__INGEST_URL__`
3. Its token, as the secret `SKALD_TOKEN`, from the keys file, never shown and never in
   `wrangler.toml`:
   `grep '^SKALD_INGEST_TOKEN=' __ENV_FILE__ | cut -d= -f2- | npx wrangler secret put SKALD_TOKEN`,
   then `npx wrangler deploy`.
4. The route: in Cloudflare, the Worker's Settings > Domains & Routes > Add > Route, with
   `__SITE__/*` (and `www.__SITE__/*`). If you cannot reach Cloudflare, give the user these
   steps.

### Case C. Vercel or Netlify

Vercel (Pro or Enterprise) and Netlify (Enterprise) post their request logs to an address.

- Vercel: Team Settings > Drains > Add Drain > Logs. This site's project; sources static, edge
  and lambda; production; sampling 100%. Endpoint `__INGEST_URL__?format=vercel`, JSON or
  NDJSON, header `Authorization: Bearer <SKALD_INGEST_TOKEN>`. Keep Security & Privacy > IP
  Address Visibility on.
- Netlify: the site's log drain, General HTTP endpoint, traffic logs. Endpoint
  `__INGEST_URL__?format=netlify`, header `Authorization: Bearer <SKALD_INGEST_TOKEN>`, JSON or
  NDJSON. Leave "Exclude personally identifiable information" off.

The drain is set in the host's dashboard. If you cannot reach it, give the user these steps,
and tell them the token is `SKALD_INGEST_TOKEN` in `__ENV_FILE__`, for them to open
themselves. Never paste it in the chat.

### Case D. Script tag only

No log is sent. Do step 5; Skald then counts what the page's browser reports (no AI crawlers
or bots: tell the user so).

## Step 5. Add the script tag

Put this line once, in the site's shared `<head>`, so every page has it:

    __TAG__

- Next.js App Router: `app/layout.tsx` (or `.jsx`), inside `<head>`, as a plain `<script>` tag
  (or `next/script` with `strategy="afterInteractive"` and the same `src` and `data-site`).
- Next.js Pages Router: `pages/_document.tsx`, inside `<Head>`.
- WordPress: the theme's `header.php` before `</head>`, or a header-code plugin.
- Plain HTML or another framework: the shared layout or template's `<head>`.

Do not add it twice. Commit it like any other change, with the user's yes, and note where you
put it for the report.

## Step 6. Leads (only if the site has a form that makes leads)

__LEADS__

1. Find where the backend handles the form (an API route, a server action, a form handler).
2. Download the file for the backend's language from `__LEADS_URL__` and read
   `__LEADS_URL__README.md` first. The files: `skald-lead.php`, `skald-lead.cjs` (Node),
   `skald_lead.py`, `skald-leads.zip` (the WordPress plugin, no code). For example:
   `curl -fsSL -o skald-lead.php '__LEADS_URL__skald-lead.php'`. They hold no secret: they
   read `SKALD_LEAD_SECRET` from the environment (WordPress: `wp-config.php`).
3. Call it once, after the lead is saved, as the README says.
4. Put `SKALD_LEAD_SECRET` in the backend's environment (the host's secret settings), from the
   keys file, never in code and never shown. WordPress keeps it in `wp-config.php`: first check
   that git does not track that file (`git ls-files --error-unmatch wp-config.php` must say
   it does not match). If git tracks it, ask the user where the secret should go instead.
5. Send one test lead with `test: true` (the README says how). Skald lists it under Left out
   and does not count it.

## Step 7. Check

1. Open https://__SITE__/ (or ask the user to), then wait two to five minutes.
2. Case A: run `sudo skald-ship-check`. Other cases: ask the user to open __DASHBOARD__ and
   look at Settings > Connections: it says what arrived and when.

## Step 8. Report

1. Tell the user, in short plain sentences: how the site is hosted, which case you did, which
   files you changed (paths), which secret settings you set (names only, never the values),
   the privacy answers, what the checks showed, and anything left for them to do.
2. Send the same to Skald, so the user's set-up page shows it. No secret goes in it. Skald
   takes it only with the report key from the keys file (this needs curl 7.55 or newer). The key goes into curl as a header
   through a pipe (`-H @-`), so it is never on a command line, in a file, or shown. One
   command (leave out a field you do not know; no single quote inside the JSON):

       grep '^SKALD_REPORT_KEY=' __ENV_FILE__ | sed 's/^SKALD_REPORT_KEY=/X-Skald-Report-Key: /' | curl -sS -X POST -H @- -H 'Content-Type: application/json' --data '{"hosting": "own server", "server": "nginx", "log_path": "/var/log/nginx/access.log", "framework": "Next.js", "asset_paths": ["/_next/static/"], "script_tag": "app/layout.tsx", "leads": [{"tool": "contact form", "file": "app/api/contact/route.ts"}], "privacy": {"keep_ips": true, "days": 30, "notice_url": "https://__SITE__/privacy"}, "nextjs_log_field": true, "changed_files": ["app/layout.tsx", "app/api/contact/route.ts"], "left_for_user": ["Set Settings > Data retention > People to 30 days"], "notes": "Anything else, in one or two plain sentences."}' '__REPORT_URL__'

   Skald answers `{"ok": true}`. It keeps only these fields (`notes` at most 1000
   characters, `asset_paths` at most 10), and you can send it again until the code expires.
3. When everything works, ask the user whether to delete `__ENV_FILE__` (and its copy on the
   server): the keys are now kept where they are used.

Help: __HELP__
