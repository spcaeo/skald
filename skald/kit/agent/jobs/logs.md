## Step __N__. Connect the logs

**Check first.** Is the site's log reaching Skald already? Look for any of these:

- on the site's server: `command -v skald-ship-check` finds it, and `sudo skald-ship-check`
  says OK on every line (a `skald-ship` Docker container or systemd service sends the log);
- in Cloudflare: a Skald Worker on the route `__SITE__/*`;
- in Vercel or Netlify: a log drain to `__INGEST_URL__`.

You may also ask the user to look at __DASHBOARD__ (Settings > Collect data > Send logs says when lines
last arrived). If lines arrive, this job is done already: skip to the next step.

### Find out how the site is hosted

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

<!-- if not privacy -->
### Ask the privacy question

Ask the user, in one message, and wait for the answer:

"Skald can keep each visit with the visitor's IP address, so you can look a person up later.
Should it keep visitors' IP addresses? If yes, for how many days? And does your site's privacy
notice cover this? Please send me its link."

Do not change any setting for it. Put the answers in the report (step __STEP_FINISH__): the user sets them
in Skald, Settings > Privacy & retention > People.

<!-- end -->
### Case A. Own Linux server

1. If the installer must run on another machine (the web server, over SSH), copy the keys
   file there with the user's yes, and keep it 0600:

       ssh <server> 'umask 077; mkdir -p ~/.config/skald'
       scp -p __ENV_FILE__ <server>:.config/skald/__SITE__.env

2. On the server, with the user's yes, download the installer (it holds no token):
   `curl -fsSL -o skald-install-__SITE__.sh '__INSTALL_URL__'`
3. Run `sudo bash skald-install-__SITE__.sh --dry-run` and read its output: it says how it
   will run (Docker or systemd) and which access log it found. It changes nothing.
4. If the log is right, run it for real, with the user's yes. The token goes in through the
   environment, never on the command line and never shown:

       ( set -a; . ~/.config/skald/__SITE__.env; set +a
         export SKALD_SHIP_TOKEN="$SKALD_INGEST_TOKEN"
         sudo --preserve-env=SKALD_SHIP_TOKEN bash skald-install-__SITE__.sh --yes )

   If it found the wrong log, add `--log <full path of the site's access log>`.
5. Run `sudo skald-ship-check`. Every line must say OK. Fix each PROBLEM with the fix it shows.
<!-- if rsc -->
6. **Next.js on its own nginx or Apache only:** the log field Next.js needs is step
   __STEP_RSC__.
<!-- else -->
6. **Next.js on its own nginx or Apache only:** without one more log field, pages opened by a
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
<!-- end -->

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

<!-- if script -->
No log is sent. Do step __STEP_SCRIPT__ (the script tag); Skald then counts what the page's
browser reports (no AI crawlers or bots: tell the user so).
<!-- else -->
No log is sent. Skald can count only what the page's browser reports, through the script tag
(no AI crawlers or bots: tell the user so). This line does not ask for the tag: tell the
user, and report this job as `left`.
<!-- end -->

### Check

1. Open https://__SITE__/ (or ask the user to), then wait two to five minutes.
2. Case A: run `sudo skald-ship-check`. Other cases: ask the user to open __DASHBOARD__ and
   look at Settings > Collect data > Send logs: it says what arrived and when.
