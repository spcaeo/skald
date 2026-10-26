# Getting a site's log into Skald from another server

Skald counts from a web server's access log. When the site runs on the same
server as Skald, it reads the log in place. When it runs somewhere else, a
small program on the site's server, **skald-ship**, sends the log's new
lines to Skald as they are written. Skald checks each line, keeps it in a
log file of its own for that site, and the daily run reads that file like
any other log.

```
site's server                                  Skald's server
/var/log/nginx/access.log                      nginx  /traffic-ingest/<site>  (POST, HTTPS)
      |  tail, batch, gzip                       |
  skald-ship  ---- HTTPS, Bearer token ---->   helper (ingest.py)
                                                 |  check token, check lines
                                               <ingest root>/<site>/access.log  (rotated daily)
                                                 |
                                               skald run-daily  (logs.dir points here)
```

It is **off by default**. An install does not change until its config
switches it on.

## Switching it on (on Skald's server)

1. Accounts must be on (`access.mode: sessions`): the tokens live in
   `accounts.sqlite`.
2. In `config.yml`:

   ```yaml
   ingest:
     enabled: true
     # Where shipped logs are kept. Default: <history folder>/ingest
     # root: /var/lib/skald/ingest
     # The address shippers post to, for the command the dashboard shows.
     # Default: access.base_url.
     # url: https://stats.example.com
     per_minute: 120    # batches a minute per site (burst: 30)
     keep: 14           # days of rotated files kept
     max_mb: 1024       # the most one site's file may hold in a day
     org_daily_mb: 200  # the most an organisation's sites may ship a day, together
     min_free_gb: 5     # refuse every batch (507) below this much free disk
   ```

3. The nginx block for `/traffic-ingest/` (DEPLOY.md, sessions mode), then
   `sudo nginx -t && sudo systemctl reload nginx`, and restart the helper
   (`systemctl restart skald-refresh`).

## Adding a site

In the dashboard: **Settings > Add or remove sites > Add a site, step by step**
(an owner or admin of the organisation; the site picker at `/traffic/` has
"+ Add a site" too). Five steps (`webapp/js/tabs/site-wizard.js`, guide:
docs/help/connections.md):

1. **Your site**: an address such as `https://www.example.com/` becomes the
   site name `www.example.com`, the way the server cleans it; the time zone.
   `POST sites/add` with `token: false` makes the site (format `auto`), owned
   by the organisation, with its log folder under the ingest root, and no
   token yet.
2. **Prove it's yours**: the DNS TXT record or meta tag, with "Check now"
   (`sites/verify`; docs/SAAS.md). When the install asks no proof, the step
   says so.
3. **Your AI agent** ("Which AI agent are you using?", 2.31): Claude Code,
   Codex, Cursor, Claude.ai or ChatGPT (chat only), Another agent, and a
   quieter **No AI agent: set it up by hand**. An agent that can run shell
   commands gets steps 4 and 5 below (method `agent`). A chat-only agent
   cannot run commands on a server, so its step 4 is the server way's one
   command (method `server`). By hand turns steps 3 to 5 into the ones that
   follow ("Use an AI agent instead" turns them back).
4. **Send this line**: the one line for the agent (`sites/agentlink`; "One
   line for your AI agent", below), the code hidden until "Show code", with
   Copy, "Make a new line", "Cancel this line" and "Is it safe to paste this
   into a chat?".
5. **Watch it connect**: a checklist that ticks itself (`sites/agentstatus`
   every 5 s for 15 minutes, then every 30 s): the agent read the steps, took
   the keys (with the time, and what to do if it was not your agent), sent its
   report, the first log lines arrived (the Test below); the script tag and a
   test lead too, when the report says the agent added them. Done is the
   first log lines, as by hand.

By hand, steps 3 to 5 are:

3. **How visits reach Skald**: my own server (nginx or Apache, with or
   without Docker: method `server`; the older `docker` and `systemd` ids, in
   saved progress, old links or the site check, map to it), Cloudflare (the
   Skald Worker), Vercel or Netlify (log drain), or only the script tag.
   Choosing Cloudflare for a dashboard site that has received nothing yet
   sets its format to `edge_json` (audit `site.format`); any other choice sets
   `auto` on the same terms.
4. **Install**: for a server, the one command (`sites/link` makes its
   sending token; below), "Download as one file" and "Email it to your server
   admin" (the set-up pack), with the by-hand ways folded under it. For the
   other ways, a named sending token (`tokens/create`, scope `ingest`, this
   site only, shown once) where the way needs one, and its steps with the send
   address and token filled in.
5. **Test and finish**: `sites/status`, polled every 5 s for up to 2 minutes,
   says what arrived or why it was refused (below). Lines arrived: "Done:
   <site> is receiving visits".

The progress is kept per site in `accounts.sqlite`, table `site_setup`
(`accounts/site_setup.py`): the step reached, the method, whether the domain
was verified at the last save (read from `site_verify`, never from the page),
the sending token's **id** (never its value), and the start, update and done
times. A change of step, method or done is one audit row (`site.setup`). A
site not finished shows "Setup: step 3 of 5, continue" in Settings > Add or
remove sites and on the site picker; a finished one that nothing reached for
24 hours (no batch, no beacon event) shows "No visits yet: test the
connection", which opens step 5.

For a site that exists already, **Settings > Connections** has **Set up with
your AI agent** on the send card: it opens the site's wizard at step 3
(`setup=<site>&step=3`), whatever way was saved. **Send this site's
visits to Skald** has the by-hand steps 3 to 5: where it runs, then for a server
"Run one command" and "Test" (three steps), for Cloudflare or Vercel "Sending
token", "Install" and "Test", for the script tag "Install" and "Test".

The first figures appear after the next daily run. On a SaaS install the
plan decides how many sites an organisation may have.

On the server, an install admin can do the same with
`skald site add shop.example.com --org <slug>` and make the token with
`skald token create shipper --scope ingest --site shop.example.com`.
A site from a config file can ship its log too: make an ingest token for it
(Settings > Connections > Send this site's visits to Skald, or Settings > Add
or remove sites > New token) and point its `logs.dir` at `<ingest root>/<site>`.

## One line for your AI agent

Since 2.31 this is Add a site's first way (`skald/kit/agent.py`, `kit_api.py`,
`webapp/js/tabs/agent-setup.js`, `agent-watch.js`, `agent-words.js`). Skald writes one line,
the admin pastes it into an AI agent that can run shell commands (Claude Code, Codex, Cursor
in Agent mode), and the agent does the set-up and reports back:

```
set up Skald for example.com — read https://stats.example.com/traffic-kit/llms.txt and use code <code> (works once, 24 hours)
```

The address is the install's own (`kit_api.fields(...)["base"]`). The code is 43 URL-safe
characters (`secrets.token_urlsafe(32)`). It is not a key. It lets the agent take the keys
**once**, with curl, straight into a 0600 file. The keys never pass through the chat or the
dashboard page.

**The line.** `POST <page>/sites/agentlink {site, leads: true}` (owner or admin, as
`sites/link`) does four things:

- It makes a new sending token, "Sending logs: <site>, <day> (AI agent set-up)", with scope
  `ingest`, for this one site.
- With leads, it gets the site's lead secret. An existing secret is copied, not replaced
  (audit `hook.secret`, "copied (AI agent set-up)"). With none, one is made ("made (AI agent
  set-up)"). A secret kept in the server's environment is not put in: the steps tell the
  agent to ask whoever runs Skald.
- It makes a report key, so that only the agent that took the keys can send the report.
- It seals all three under a new code for 24 hours. In the same lock it cancels the site's
  older lines whose keys were not taken, and revokes the unused token of an expired one
  (below).

It answers `{line, llms_url, steps_url, expires_at, token_id, link_id, cancelled}`, and never
the token or the secret. `link_id` is the first 16 hex of the code's SHA-256: the only thing
the page puts in the address (`link=`). The page keeps the line in memory only. After a reload
it says the line is not shown again, and offers a new line or Cancel. The audit row is
`kit.agentlink`: the token id, the link id, the lead secret's kind and how many older lines
were cancelled. It never holds the code. 409 when the log endpoint is off.

**The routes,** on the beacon helper under `/traffic-kit/` (`agent.serve`):

| Route | Who | Answer |
| --- | --- | --- |
| `GET /traffic-kit/llms.txt` | anyone | The public guide for an agent (`kit/agent/llms.txt`): what Skald is, its rules, and "read `<base>/traffic-kit/<code>/steps`". No code, no secret, no rate limit. POST: 405 |
| `GET /traffic-kit/<code>` | anyone | To curl or Wget, a script that prints "This code is for an AI agent: read .../steps" and exits 1, so `\| sudo bash` never runs Markdown. Anything else gets the same words as text. It never uses anything up. An install link's code answers as before (`link.answer_code`) |
| `GET /traffic-kit/<code>/steps` | anyone (the guide says: curl) | The site's own steps in Markdown (`kit/agent/steps.md`): the site, the send and lead addresses, the dashboard, what the site check found and which way fits, the script tag, the rules, and the 8 steps (find the hosting, ask the privacy question, take the keys, connect the logs, the tag, leads, check, report). No secret. The first GET sets `opened_at`. It works until the expiry or a cancel, also after the keys are taken. A site check value is cut to 120 characters, put in a code span, and can never look like a placeholder; a page that cannot be made answers 500 in words |
| `GET /traffic-kit/<code>/keys` | curl or Wget only | The keys once, as an env file, each value shell-quoted: `SKALD_SITE`, `SKALD_INGEST_URL`, `SKALD_INGEST_TOKEN`, `SKALD_LEAD_URL`, `SKALD_LEAD_SECRET` when it was included, and `SKALD_REPORT_KEY`. Then the seals are wiped and `keys_at` is set. Again: 410. Any other user agent: 403 "Fetch this with curl in a shell into a file...", and nothing is used up. HEAD: the status only, never used up |
| `GET /traffic-kit/<code>/install.sh` | anyone | The one-file installer without a token. It reads `SKALD_SHIP_TOKEN` from the environment, which the steps fill from the keys file |
| `GET /traffic-kit/<code>/leads/<file>` | anyone | The lead files (`kit/leadfiles.py`: `README.md`, `skald-lead.php`, `skald-lead.cjs`, `skald_lead.py`, `skald-leads.zip`) without a secret. They read `SKALD_LEAD_SECRET` from the environment |
| `POST /traffic-kit/<code>/report` | the agent that took the keys | The agent's report: one JSON object, at most 16 KiB, with a Content-Length (411 without, 413 over, 400 not an object), and the header `X-Skald-Report-Key: <SKALD_REPORT_KEY>`. The steps pipe that header into `curl -H @-` (grep the keys file, sed it into a header), so the key is never on a command line or in a file; an agent run from an allow list may not redirect into a file, so the steps write none. No key, or a wrong one: 403, nothing kept. `{"ok": true}`. It can be sent again until the expiry or a cancel. The latest replaces the earlier one |

**After the keys are taken,** only `/keys` stops (410). `/steps`, `/install.sh`, `/leads/<file>`
and `POST /report` keep answering until the expiry or a cancel, so the agent can finish and
report. None of them holds a secret. The bare code keeps answering its words too.

Every answer has `Cache-Control: no-store` and `X-Robots-Tag: noindex, nofollow`. Every route
but `llms.txt` has its own limit per address (10 a minute, a burst of 5; then 429 "Too
many tries"): the bare code, `steps`, `keys`, `install.sh`, `leads/`, `report` and any other
sub-path each count apart (`agent.ROUTES`), so an agent that reads the steps many times still
has its tries for the keys. An unknown code answers 404 under a sub-path. An expired or cancelled code
answers 410 with words that say to make a new line.

**What is stored.** One entry in `kit-links.json` (0600, beside the history, the same file and
lock as the install links), keyed by the code's SHA-256, with `kind: "agent"`. It holds the
site, `made_at`, `expires_at`, `token_id`, the token, the lead secret and the report key each
XORed with its own HMAC-SHA256 keystream from the code (`sealed`, `sealed_lead`,
`sealed_report`; labels `skald-kit-agent`, `skald-kit-lead`, `skald-kit-report`, never the
install link's, so an older image that does not know agent codes cannot hand the token out
as an install link), the report key's SHA-256 only (`report_key`, to check the report), the
fields (the
addresses and the tag: nothing secret), whether leads were asked for and the lead note, the
site check's facts (`found`), `opened_at`, `keys_at`, `reported_at`, `cancelled_at`, and the
cleaned report, and `token_revoked` once the unused token was revoked. It never holds the
code itself, so the disk never holds a usable key. The file is written only when something
changes: a refused or late report, a second read of the steps or a second try for the keys
leave it as it is. The seals are wiped when the keys are taken, on a cancel, and on the first
write to the file after the expiry, which the daily run makes at the latest (an expired code
gives nothing either way). The entry is kept a
day after the expiry, so the wizard can still say "expired" and show the report. Then it is
dropped. Nothing logs the code: the container's nginx has `access_log off` and
`error_log stderr crit;` for `/traffic-kit/` (an error line holds the request line, so a
refused method, a report over 16 KiB or an upstream failure would otherwise write the code),
the beacon helper logs no request, and the audit holds only the link id.

**The report.** Only these keys are kept, each cleaned (one line, printable) and capped:
`hosting`, `server`, `framework`, `log_path`, `asset_paths` (up to 10, as the
setting allows, each starting with `/`), `script_tag` (where it was added), `leads` (up to 10 `{tool, file}`), `privacy`
(`keep_ips` true or false, `days` 0 to 3650, `notice_url` http or https), `nextjs_log_field`
(true or false), `changed_files` (up to 50), `left_for_user` (up to 20), and `notes` (at most
1000 characters). An unknown key or a wrong kind is dropped. Text shaped like a sending token
or a lead secret becomes `[removed]`. The wizard shows the report in plain words. It changes
no setting by itself: the admin applies what fits. "Use these page assets" saves the report's
`asset_paths` through the usual settings call when they differ from the site's, and the
privacy answers are for the admin to set in Settings > Data retention > People.

**The states** (`POST <page>/sites/agentstatus {site, link_id}`, that site's codes only):

| State | Means |
| --- | --- |
| `waiting` | made, the agent has not read the steps yet |
| `opened` | the agent read the steps (`opened_at`) |
| `keys_taken` | the keys were taken (`keys_at`). This stays after the expiry: the outcome is settled |
| `expired` | 24 hours passed before the keys were taken |
| `cancelled` | ended by Cancel this line, or by a newer line |
| `unknown` | no such code for this site, or dropped a day after the expiry |

It answers `{state, opened_at, keys_at, reported_at, cancelled_at, expires_at, report}`.

**Cancel.** `POST <page>/sites/agentcancel {site, link_id}` ends a line at once: the seals
are wiped and every route answers as for an expired code (410). When the keys were never
taken, its token is revoked too. When they were, the token stays: remove it in Settings >
Connections, under Your tokens. One audit row `kit.agentcancel`. 404 for an unknown line.
**A new line cancels an older unused one:** `sites/agentlink` cancels the site's lines that
are waiting or opened and revokes their unused tokens (`cancelled` says how many; audit "a
new line replaced it"). This runs inside the same lock that writes the new code, and touches
only lines made before it, so two lines made at the same moment never cancel each other. An
expired line's unused token is revoked then too. So a site has one live line at a time.
**Revoking.** A line is marked `token_revoked` only after the revoke succeeded. When it fails
(the accounts file busy, say), the line stays as it was: `sites/agentcancel` and
`sites/agentlink` answer `not_revoked: [token ids]`, the audit row says "could not be
revoked", and it is tried again by the next cancel, line, status or daily run. An expired
line's unused token is revoked as soon as `sites/agentstatus` finds it expired or cancelled,
and the daily run (step `kit tokens`, each site, also a site still waiting for its first
lines) revokes every ended line's unused token, so it goes within a day even when no one opens
the wizard again, before the entry is dropped. A
line whose keys were taken is left as it is: its keys are out already. The wizard makes a line
by itself only when the admin reached step 4 by Next or a tile; step 4 opened from an address
shows a button instead, so an old link cannot cancel the line an agent is working from.

**Why web readers cannot take the keys.** A web reader or fetch tool (a chat's "read this
URL") may pass the page through another model, and so put the keys in a chat history. So
`/keys` answers only a user agent that starts with `curl/` or `wget/`. Anything else gets 403
and uses nothing up, so a mistake costs nothing. The guide tells the agent to fetch the steps
with curl too, so the code is not handed to a fetch tool's provider. The steps first check
that the keys file is not there already, take the keys with
`curl -sS -o $HOME/.config/skald/<site>.env.part` under `umask 077`, and move the file into
place only on HTTP 200: a repeated fetch (its 410 words) can never overwrite good keys. They
check only the names (`cut -d= -f1`) and never print the file. The user-agent check guards
against mistakes. It is not a lock: anyone can send `curl/` as a user agent. The protection is
that the code works once, for 24 hours, and can be cancelled.

**What the keys can do.**

- The sending token has only the `ingest` scope, for this one site. It can add log lines to
  `POST /traffic-ingest/<site>` and nothing else. It cannot read any figure, open the
  dashboard or see a visitor.
- The lead secret only signs this site's leads: `POST /traffic-hooks/<site>/lead`. It also
  signs the site's own read-back of the leads it sent (`GET /traffic-hooks/<site>/leads`:
  refs, stages, times and labels, never a name, email or visitor ID) and the marking of its
  own leads as test (`POST .../leads/test`). It cannot open the dashboard.

After the set-up, the admin can remove the agent's token ("AI agent set-up") in Settings >
Connections > Your tokens, and make a new lead secret in Settings > Integrations.

**What the wizard tells the admin** ("Is it safe to paste this into a chat?",
`agent-words.js` `SAFE`; the help has the same words). Each line holds because of the
behaviour above:

- Yes. The line holds a one-time code, not a password or a key.
- The keys come out once. When your agent takes them, the code can never give them again. A
  code nobody uses stops after 24 hours.
- Your agent is told to save the keys straight into a locked file and never show them in the
  chat. Skald gives them only to a command-line download such as curl, and turns away web
  readers and fetch tools, which could pass them into a chat.
- The keys work for this one site only. The sending key can only send log lines. The lead
  secret sends leads and can read back this site's lead list (reference, stage, time), never
  names, emails, addresses or visitor IDs. Neither can open your dashboard or see your
  visitors.
- Skald keeps only a scrambled copy of the code (a hash), never the code itself, and never
  writes it to a log.
- Until the keys are taken, treat the line like a house key: paste it only into your own agent.
  Changed your mind? Press Cancel this line and it stops at once. A new line also cancels an
  older one whose keys were not taken yet.
- If your site already has a lead secret, the agent gets that same one (unless your Skald keeps
  it in the server's settings; then the keys hold none). After the set-up you can remove the
  agent's sending key in Settings > Connections > Your tokens, and make a new lead secret in
  Settings > Integrations.

**nginx.** `/traffic-kit/` stays GET only, logs nothing, and a nested location lets POST
through for the report alone, with `client_max_body_size 16k` (DEPLOY.md's sample):

```nginx
location ^~ /traffic-kit/ {
    error_log stderr crit;
    access_log off;
    location ~ "^/traffic-kit/[A-Za-z0-9_-]{43}/report$" {
        limit_except POST { deny all; }
        client_max_body_size 16k;
        include snippets/skald-beacon.conf;
    }
    limit_except GET { deny all; }
    include snippets/skald-beacon.conf;
}
```

`docker/nginx.conf` has it. A self-hosted front nginx made from DEPLOY.md's sample before 2.31
must take this block: without the nested location the agent's report is refused (403), and
without `error_log stderr crit;` nginx's error log can hold the code. The helper sends
`no-store` and `noindex` itself.

## One command: the one-file installer and the install link

The shortest way onto a Linux web server is one command the site's admin runs there:

```sh
curl -fsSL https://stats.example.com/traffic-kit/<code> | sudo bash
```

Settings > Connections makes it (`POST <page>/sites/link`): a new sending token for that
one site (named "Sending logs: <site>, <day> (one-command install)", in the audit log as
`token.create`, then `kit.link`) and a link that works **once, for 24 hours**. The link
answers the installer with the token inside to curl or Wget, then never again; a used,
expired or unknown link answers 200 with a two-line script that says so and exits 1 (a 410
would make `curl -f` show only its own error, so `| sudo bash` would never show the
words). A browser or a mail's link preview gets the words "Run this on your server: ..."
and does not use the link up. Options go after
`bash -s --`: `curl -fsSL <link> | sudo bash -s -- --log /var/log/nginx/x.log`.

The link's store, `kit-links.json` beside the history (0600, expired entries dropped on
each write), keeps only the SHA-256 of the code, the site, the expiry and the token
XORed with a keystream made from the code (HMAC-SHA256): the server's disk never holds a
usable token. `/traffic-kit/` is answered by the beacon helper (`beacon_server.py`,
`skald/kit/link.py`), limited to 10 tries a minute per address, `Cache-Control:
no-store`, `X-Robots-Tag: noindex`, and never logged (nginx: `access_log off`, DEPLOY.md).

The same installer is one file to download: "Download as one file",
`POST <page>/sites/kit` with `method: "server"` -> `skald-install-<site>.sh`, the token
inside only when `include_token` is true. From `skald/kit/install-server.sh`,
filled by `kit.one_file`:

- **How it runs:** with Docker when Docker works on the server and the install knows its
  image (`ingest.kit_image`), else as a systemd service with Python 3.9 or newer, the
  shipper inside the file (base64). Neither: it stops and says what to install. A shipper
  installed before keeps its way and its place in the log, so running it again is safe
  (and a shipper of the other way is removed, so only one sends).
- **The log:** found by itself. It reads nginx's settings (`nginx.conf`, `conf.d/`,
  `sites-enabled/`) and Apache's (`sites-enabled/`, `conf.d/`, `httpd.conf`) for the server
  block whose `server_name` / `ServerName` / `ServerAlias` is the site or `www.<site>` and
  takes its `access_log` / `CustomLog` (`${APACHE_LOG_DIR}` and nginx's `$host` are filled
  in). A block with no `access_log` writes the http block's. Several: it asks, from the
  terminal (`/dev/tty`, so it works under `curl | sudo bash`), the biggest first; none: the
  usual places. `--log <path>` names it; `--yes` asks nothing and takes what was found;
  `--dry-run` shows every step and changes nothing.
- **The token:** inside the file when it was made with one (never printed), else
  `SKALD_SHIP_TOKEN`, else asked for, hidden. Kept as the kits keep it: Docker
  `/srv/skald/ship-token` (root:adm, 0640), systemd `/etc/skald-ship/token`
  (root:skald-ship, 0640).
- **What it leaves:** `/usr/local/bin/skald-ship-check` (check.sh below, read-only) and
  `/usr/local/bin/skald-ship-uninstall` (uninstall.sh, which also removes these two), for
  the way it used. It ends with a short "Done" block and the dashboard link.

## The set-up pack: everything in one zip, for a person or an AI agent

Settings > Connections can download or mail `skald-setup-<site>.zip`
(`skald/kit/pack.py`, `skald/kit_api.py`). One folder, `skald-setup-<site>/`:

| File | What it is |
| --- | --- |
| `START-HERE.md` | For a person: what Skald is, then "pick your case" (own Linux server, Cloudflare, Vercel or Netlify, only the script tag), leads, and how to check it works |
| `CLAUDE.md`, `AGENTS.md` | The same for an AI coding agent: find out how the site is hosted, do the matching steps, the tag in the shared `<head>`, leads in the backend, secrets only in environment variables or the host's secret settings (never in code, git or chat), the checks, then report back |
| `secrets.env` | `SKALD_INGEST_URL`, `SKALD_INGEST_TOKEN`, `SKALD_LEAD_URL`, `SKALD_LEAD_SECRET` (mode 0600). Without keys: the two addresses, empty token and secret, and where to get them |
| `logs/install-server.sh` | The one-file installer (the token inside when keys are included) |
| `logs/cloudflare.md`, `logs/vercel-netlify.md` | The Worker's and the log drains' steps with the send address (and the token when included) |
| `tag/script-tag.html`, `tag/README.md` | The script tag and where to put it |
| `leads/` | The lead code per language (`skald/kit/leadfiles.py`), else a README that points to Settings > Integrations. A file name mail filters block (`.js`, `.mjs` and the like) gets `.txt` added |

With `include_secrets`, the pack holds a new sending token ("(set-up pack)") unless the
page gives one, and the lead secret: the one the page just made (checked against the
store), else the one the site has, else a new one (audit `hook.secret`, "put in a set-up
pack" or "made (set-up pack)"). A lead secret kept in the server's environment is not put
in: the pack says to ask whoever runs Skald. Mailed (`sites/packmail`): through the
install's mail settings (Settings > Mail), to up to 3 addresses, subject "Set up Skald for <site>", 10 mails per site an hour.
A mail that does not go takes its new token back (revoked) and its new lead secret.
Audit `kit.pack` and `kit.packmail`: who, the site, how many recipients, keys or not;
never an address or a key.

## The install kit and check.sh

For a server, the page now offers the one command and the one file (above);
both leave `check.sh` on the server as `sudo skald-ship-check`. The older zip
kits remain: from the command line, and under "Other ways: by hand with Docker
/ without Docker" in Settings > Connections and step 4 of Add a site ("Download
the install kit (.zip)", `POST <page>/sites/kit` with method `docker` or
`systemd`). A zip the site's admin runs on their own web server, with no SSH
from Skald's side:

```sh
python3 -m skald.kit --site www.example.com --method docker \
  --url https://stats.example.com/traffic-ingest/www.example.com \
  --image <image> --out skald-ship-www.example.com.zip
```

(`--method systemd` needs no image; `--ship-path`, `--dashboard` and `--help-url`
are optional.) `skald-ship-<site>.zip` holds one folder `skald-ship-<site>/`:

| File | What it does |
| --- | --- |
| `install.sh` | Docker: runs `skald-ship` from the image as a container (128 MB, user 10001, group `adm`, the log mounted read-only, `--from-end`). systemd: installs the shipper, its user and the unit of "Installing the shipper by hand". Lists nginx's or Apache's log files and asks for the site's access log and the token. `--dry-run` shows every command and changes nothing |
| `uninstall.sh` | Removes only what `install.sh` made |
| `check.sh` | Read-only checks, one line each (`✓ OK`, `✗ PROBLEM` with a fix, `? CANNOT TELL`): Docker, the web server, the log and its group `adm`, that the log grows, that www writes to it, the send address (401 without a token means the path works), the token file's owner and mode, the shipper running, its last 20 lines, lines leaving. Ends with a block "Copy this and send it to us": no token, every IP address masked. Exit 0 when all is OK |
| `README.txt` | The steps, what it keeps on the server, how to undo it |
| `skald-ship.py` | systemd kit only: the shipper (`tools/skald-ship.py`) |
| `ship-token` | Only when "Include the access token in the zip" is ticked (the default, when the page holds a token it just made): mode 0600; `install.sh` moves it into place and deletes it. Unticked, no file of the zip holds the token: `install.sh` takes it from a `ship-token` file the admin makes, else `SKALD_SHIP_TOKEN`, else asks for it (not echoed) |

The token goes in only when `include_token` is true and the token is a valid
`ingest` token of that site (else 400); it is never logged or kept by the
helper. Templates: `skald/kit/` (`install-docker.sh`,
`install-systemd.sh`, `uninstall.sh`, `check.sh`, `README-docker.txt`,
`README-systemd.txt`), filled by `skald/kit/__init__.py`.

The Docker kit, and the Docker way of the one file, need the image name:
`ingest.kit_image` in the config, else the `SKALD_KIT_IMAGE` environment
variable. The Docker image's entrypoint sets `SKALD_KIT_IMAGE` to itself at its
major version, and `SKALD_KIT_SHIP_PATH` to the shipper inside it
(`ingest.kit_ship_path` overrides it). Without an image the page offers no
Docker kit and says why, and the one file runs as a systemd service only;
without `tools/skald-ship.py`, no systemd kit and no systemd way in the one
file; with neither, no one file (SETTINGS.md).

## Installing the shipper by hand (Ubuntu or Debian)

skald-ship is one file, `tools/skald-ship.py`, Python 3.9 or newer, nothing
else. On the site's server:

```sh
sudo install -m 0755 skald-ship.py /usr/local/bin/skald-ship
sudo useradd --system --no-create-home --shell /usr/sbin/nologin --groups adm skald-ship
sudo install -d -m 0750 -o root -g skald-ship /etc/skald-ship
sudo sh -c 'umask 027; cat > /etc/skald-ship/token'    # paste the token, then Ctrl-D
sudo chgrp skald-ship /etc/skald-ship/token
```

`adm` is the group that may read `/var/log/nginx` and `/var/log/apache2` on
Debian and Ubuntu.

`/etc/systemd/system/skald-ship.service`:

```ini
[Unit]
Description=Ship the access log to Skald
After=network-online.target
Wants=network-online.target

[Service]
# The user's own group reads the token; its membership of adm reads the log.
User=skald-ship
ExecStart=/usr/local/bin/skald-ship \
    --url https://stats.example.com/traffic-ingest/www.example.com \
    --token-file /etc/skald-ship/token \
    --log /var/log/nginx/access.log \
    --state /var/lib/skald-ship/state.json
Restart=always
RestartSec=5
StateDirectory=skald-ship
StateDirectoryMode=0700
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ReadOnlyPaths=/var/log /etc/skald-ship
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SystemCallFilter=@system-service

[Install]
WantedBy=multi-user.target
```

```sh
sudo systemctl daemon-reload && sudo systemctl enable --now skald-ship
journalctl -u skald-ship -f
```

The options: `--batch-lines` (default 2000), `--interval` (seconds a part
batch may wait, default 10), `--from-end` (first run only: start at the end
of the log instead of its start), `--once` (send what is there, then exit).
The service retries a refused batch for ever. `--once` gives up after 5 failed tries of a
batch, or when the next wait would pass 60 s in all (a 507's `Retry-After: 600` gives up at
once): it exits 1 with one plain line, keeps its state, and sends the same lines at the next
run, so nothing is lost.
The URL must be `https://`; plain `http://` only to 127.0.0.1 or localhost.

## Log formats

The site's log format is chosen when the site is added. Lines in another
format are refused and counted (the shipper's journal says "N rejected").

| Server | Format | Notes |
| --- | --- | --- |
| nginx | `nginx_combined` | nginx's default `combined` log format |
| nginx | `nginx_extended` | Skald's own format with host, time taken and request id (DEPLOY.md) |
| Apache | `apache_combined` | `LogFormat "%h %l %u %t \"%r\" %>s %O \"%{Referer}i\" \"%{User-Agent}i\"" combined` |
| Caddy | `caddy_json` | Caddy's default JSON access log (`log { output file ... }`) |
| Cloudflare, CloudFront, Fastly, Akamai | `cloudflare_json`, `cloudfront_w3c`, `fastly_json`, `akamai_json` | see CDN-LOGS.md |
| Vercel, Netlify (log drains) | `vercel_json`, `netlify_json` | no shipper: the platform posts its own request logs (below, and HOSTING.md) |
| Cloudflare on any plan (the Skald Worker) | `edge_json` | no shipper: the Worker posts one edge record per request (below, and CDN-LOGS.md) |
| any of these | `auto` | each line is read by whichever format reads it |

Ship the log of the server that sees the visitors. Behind a CDN, that is the
CDN's log (CDN-LOGS.md), never both.

### Next.js: pages opened inside the site

On a Next.js App Router site a tap on a link inside the site sends no HTML
request. The browser fetches `GET /path?_rsc=<hash>` and the route's script.
Next.js sends the same URL to *prefetch* links in view, with the request
header `Next-Router-Prefetch`. A plain log cannot tell the two apart, so
Skald counts no `?_rsc=` request as a page view (COUNTING-TRAPS.md trap 10):
only the first page of each visit is seen, and a visit from a tab left open
sends no HTML request at all.

One field at the very end of the line fixes it. Append it inside the
`log_format` quotes (any format above: Skald's extended one, after `rid=`, or
nginx's `combined`):

```nginx
log_format combined_rsc '$remote_addr - $remote_user [$time_local] "$request" '
                        '$status $body_bytes_sent "$http_referer" "$http_user_agent"'
                        ' rsc_prefetch=$http_next_router_prefetch';
```

That is, add ` rsc_prefetch=$http_next_router_prefetch` at the end. Apache's `LogFormat`:
` rsc_prefetch=%{Next-Router-Prefetch}i`. Then `sudo nginx -t` and `sudo systemctl reload nginx`
(Apache: `apachectl configtest`, then reload). Both write `-` when the
header was not sent.

- The token is `rsc_prefetch=`, a field of its own after the user agent;
  the end of the line is the place for it. It works alongside a trailing
  request time, a trailing `"$host"` (before or after it) and `rid=`.
- `-` (or nothing): a navigation, counted as a page view of its path when
  answered 2xx or 304. Any other value (`1`; newer Next.js also sends `2`
  to `4`): a prefetch, never a page view. A POST (a server action) never is.
- An HTML page and a navigation of the same path in one visit, 2 seconds or
  less apart, are one page view (one click that fell back to a full load).
- Lines without the field are read exactly as before; old lines stay as
  they were (a backfill does not change them).
- Caddy's JSON log already holds the request headers: nothing to add. The
  Vercel and Netlify drains and the Skald Worker's edge records carry no
  request headers, so on those a navigation is still not counted.
- What stays unseen: a navigation Next.js answers from its own cache sends
  nothing; a `<Link prefetch={true}>` prefetch is sent without the header
  and counts as a view (the default `<Link>` sends it).

The doctor's "Next.js pages" line, the Overview checklist ("Pages opened
inside the site are not counted yet") and `skald-ship-check` (`check.sh` in a zip kit) say so when the log has
`?_rsc=` lines and none carries the field. Nothing edits nginx for you.

### The request's size (optional, Security)

Security's "Log signs worth a look" can name unusually large POST bodies when the log records
each request's size. In nginx, add at the end of the `log_format`:

```nginx
                        ' request_length=$request_length';
```

then `sudo nginx -t` and `sudo systemctl reload nginx`. `$request_length` is the whole request
(the request line, the headers and the body) in bytes. The token is `request_length=`, a field
of its own after the user agent, like `rsc_prefetch=`; it works beside it, a trailing request
time, `"$host"` and `rid=`. Lines without it are read as before, and Security says the size is
not recorded (never 0). A POST of `security.large_post_bytes` (1,000,000) or more is large.

**Countries.** A shipped line with no country of its own (Caddy, a plain
combined log) gets its address's country from the install's `logs.country_db`
(Docker: `SKALD_COUNTRY_DB`), a GeoIP `.mmdb` file on Skald's server; DB-IP's
free country file works. Every site added from the dashboard uses the same
file. A country the line carries (`cc=`, Cloudflare's) always wins. With no
file set, such lines stay Not recorded (stored as `Unknown`).

## What is sent, and what is kept

- **Sent:** the access log's lines as the server wrote them, in gzip
  batches of at most 2000 lines and 4 MiB, over HTTPS. Nothing else: no
  other file, nothing about the server.
- **Kept:** the lines that parse, appended to `<ingest root>/<site>/access.log`.
  Lines that do not parse are counted and dropped: their content is never
  kept, logged or sent back. Nothing about the sender (address, user agent)
  is kept. The kept file is an access log like the server's own: it holds
  the visitors' addresses, for `ingest.keep` days, readable only by the
  service (0640). The history the daily run builds from it holds no
  address.
  Since 2.4.0 a site may also keep each reader's visit with its address in
  `conversions.sqlite`, for `privacy.keep_days` (395) days: on for a new
  install, off for one upgraded from before 2.4.0 (`privacy.keep_ips`,
  SETTINGS.md).
- **Files:** `access.log` (today, UTC), `access.log.1` (the day before),
  `access.log.2.gz` ... `access.log.<keep>.gz`. The folder also holds
  `.ingest-state.json`: the last batch number per shipper and counts, no
  log content.

## Never a line lost, never one counted twice

- The shipper saves its place (file, inode, offset, last batch number) only
  after Skald answered 2xx. Until then it sends the batch again, waiting
  longer each time (1 s doubling to 5 minutes, with jitter); 429, 503 and
  507 wait for `Retry-After` (at most 10 minutes); 413 splits the batch.
- Every batch is numbered: `X-Skald-Batch: <shipper id>:<seq>`. Skald keeps
  the last number of each shipper; a batch it has already kept is answered
  "duplicate" and not written again. So a batch whose answer was lost on
  the way is kept once.
- Skald writes each batch with a journal: a crash halfway is repaired at
  the next batch (a whole append is kept, a partial one cut off).
- Rotation on the site's server (logrotate's rename): the shipper reads the
  old file to its end, then the new one. If it was stopped across a
  rotation, it finds the old file as `<log>.1` and finishes it first. If
  that file is already compressed (`delaycompress` avoids this), it says so
  in the journal and starts the new file: those lines are lost, and the
  journal says so. `copytruncate` is followed too.
- Rotation on Skald's side is **daily**, never by size alone: the daily run
  looks back one rotation per day, so a file rotated twice a day would put
  lines out of its reach. A day's file that reaches `ingest.max_mb` refuses
  further batches with 429 until midnight UTC; the shipper keeps them and
  sends them then (they are still counted on their own day).

## Security

- **The token** can only add lines to one site. It cannot read anything
  (no `read` scope), and a read token cannot ship. It is stored on Skald's
  side as a hash only, shown once, and revoked in Settings > Connections (Your tokens). A token
  made by a person stops when that person leaves the organisation or stops
  being an admin.
- **One organisation cannot write into another's site:** the token must
  belong to the site's organisation, and name that site. A token for an
  unknown site gets the same answer as one for another organisation's
  site, so it cannot probe which sites exist. tests/test_tenant_isolation.py
  checks this with every other route.
- **Limits:** a body of at most 5 MiB, packed and unpacked (a gzip bomb is
  stopped at 5 MiB), lines of at most 64 KiB, `ingest.per_minute` batches a
  minute per site, nginx's `limit_req` in front. A removed site answers 410.
- **The disk:** an organisation's sites together take at most
  `ingest.org_daily_mb` (200) a UTC day, or its plan's `ingest_daily_mb`
  (docs/SAAS.md). The bytes are counted as each batch is accepted, in
  `<ingest root>/.org-bytes.json` under a lock (a refused or repeated batch
  is not counted); past the cap the batch gets 429 with the seconds to
  midnight UTC. When the ingest root's filesystem has less than
  `ingest.min_free_gb` (5) free, every batch gets 507 (`Retry-After: 600`).
  Either way the shipper keeps the lines and tries again.
- The shipper runs as its own user with read access to the logs only, sends
  over HTTPS with certificate checks, follows no redirects, and never writes
  the token to its journal.

## Quotas

On a SaaS install (`skald/saas/limits.py`), each batch is checked
against the organisation's plan before it is kept (`over_limit`: this
month's requests, sites, members), and adding a site against the plan's
number of sites (`can_add_site`). A read-only plan (cancelled, or unpaid past
the grace days) refuses changes in Settings > Add or remove sites with 402,
and every batch with 402 too (`saas.limits.read_only`).
Over a limit, the batch gets 429 with the reason and `Retry-After: 3600`; the
shipper waits at most 10 minutes (its cap) and tries again, so nothing is lost
while the plan is changed. Without
that module there is no limit.

## What the endpoint notes for the Test

Every answer of `/traffic-ingest/<site>` is noted in one small file per site,
`<history folder>/ingest-status/<site>.json` (`skald/ingest_status.py`),
which the Test of Settings > Connections and of Add a site reads through
`sites/status`:

```json
{"last_batch":   {"at": "2026-10-21T10:42:05Z", "lines": 120, "rejected": 0, "shipper": "a1b2c3"},
 "last_contact": "2026-10-21T10:42:05Z",
 "today":        {"day": "2026-10-21", "lines": 1240},
 "last_refusal": {"at": "2026-10-21T10:41:00Z", "code": 403, "reason": "wrong_site",
                  "words": "The token is not for this site."}}
```

- **Holds:** the time of the last accepted batch with its lines kept and
  refused and the shipper's own id (from `X-Skald-Batch`, or the drain's
  name); the last time any batch was answered 200; today's lines (UTC); the
  last refusal with its HTTP code and a reason word (`REASONS`: `no_token`,
  `bad_token`, `wrong_site`, `not_sending`, `not_verified`, `removed`,
  `not_here`, `rate_limited`, `day_full`, `plan_limit`, `read_only`, `disk`,
  `bad_format`, `bad_batch`, `too_large`, `no_accounts`, `off`, `other`) and
  its plain words.
- **Never holds:** an IP address, a user agent, a token, a log line, or the
  server's own refusal text.
- Written only for a site this install knows (its ingest folder exists, or a
  config names it), and at most one refusal a second per site, so a stream of
  bad posts cannot fill the disk. A duplicate batch is not noted. A write is a
  temp file and a rename under a per-site lock; a failure is swallowed and
  never changes the answer.

## Removing a site

Settings > Add or remove sites > Remove (an owner, typing the site's name).
Processing stops at once: the daily run skips the site and the endpoint
answers 410. Its figures and log files stay. An install admin deletes them
for good with `skald site purge <site> --yes` (take a backup first): the
history rows, the dashboard folder, the state folder, the ingest folder,
its settings and the tokens that read only that site. Stop the shipper on
the site's server too.

The purge also deletes the site's conversions (every conversions.sqlite table
with a `site` column: conversions, journeys, identities, deliveries, webhooks,
outbox, and its outbox cursor), its lines in the hook spool and its secrets
(`hooks/<site>/*`, `outgoing/<site>/*`). The name is then held for 30 days:
`skald site add`, Settings > Add or remove sites and sign-up refuse it, unless an install
admin passes `skald site add <site> --allow-reuse`.

## Log drains: Vercel and Netlify

A site on Vercel or Netlify has no log file and no server for the shipper. Both platforms post
their request logs to an address instead (a "log drain"), to the same endpoint with
`?format=vercel` or `?format=netlify`:

    POST /traffic-ingest/<site>?format=vercel     Authorization: Bearer <ingest token>
    POST /traffic-ingest/<site>?format=netlify    (or, Vercel only, a valid x-vercel-signature)

- The body is the platform's own: a JSON array or NDJSON, gzip or plain. No `X-Skald-Batch`:
  the batch id is the platform and a hash of the body, so a delivery the platform retries is
  kept once.
- Each request record is kept as one JSON line with only the fields Skald reads (time,
  address, host, method, URL, status, referrer, user agent, country, duration, size, request
  id); everything else is dropped before writing. Records that are not requests (Vercel build
  output and function log lines without a `proxy` object, background revalidations; Netlify
  function, edge-function and deploy logs) and requests to Skald's own `/traffic-beacon`,
  `/traffic-js/`, `/traffic-hooks/` are **skipped** and counted; a request without the
  visitor's address or a status is **rejected** and counted.
- The site's `logs.format` must be `vercel_json`, `netlify_json` (matching the drain) or
  `auto`, else 400. A request logged in several records (a function's log lines) is read once,
  by its request id.
- Vercel's signature: `ingest.drains.<site>.vercel_secret_env` (the name of an environment
  variable) or `vercel_secret_file`. Set, every delivery must carry `x-vercel-signature`, the
  HMAC-SHA1 of the raw body with it (401 otherwise, 503 when the secret cannot be read).
  `vercel_verify` makes every answer carry `x-vercel-verify` (HOSTING.md).
- The answer adds `"skipped"`: `{"ok":true,"accepted":N,"rejected":M,"skipped":K,"duplicate":false}`.
  Every other check and answer is the shipper's (table below).
- The audit reads the kept lines with its own reader (`audit_drains.py`).

**Edge records** (`?format=edge`): one request per JSON object, Skald's own format, posted by
the Skald Worker for Cloudflare (`deploy/cloudflare-worker/`) or any edge that sends the same
fields (`ts`, `ip`, `method`, `host`, `path`, `status`, `bytes`, `referer`, `ua`, `cache`,
`id`; CDN-LOGS.md has the table). Bearer token only. The site's format must be `edge_json` or
`auto`. Differences from a drain:

- With `logs.edge_only_cached` (true unless the format is `edge_json`), a record whose `cache`
  is not `HIT` is skipped: the origin's log, shipped to the same site, has that request.
- Each post is the next batch of one sender, `edge`: no `X-Skald-Batch`, no per-post state. A
  record posted twice is dropped when read, by its `id`.
- Its own rate limit per site, `ingest.edge_per_minute` (1200) and `ingest.edge_burst` (300),
  apart from the shipper's. A refused post is lost (the Worker does not retry).

Setup on each platform, and the field lists with their sources: [HOSTING.md](HOSTING.md),
part B. Code: `skald/ingest_drain.py`, `parse_drains.py`.

## The endpoint

`POST /traffic-ingest/<site>`, `Authorization: Bearer <token>`,
`Content-Encoding: gzip` (or none), `X-Skald-Batch: <shipper id>:<seq>`,
the body one log line per line.

| Answer | Meaning |
| --- | --- |
| 200 `{"ok":true,"accepted":N,"rejected":M,"duplicate":false}` | kept |
| 200 `{"ok":true,"duplicate":true,...}` | that batch was kept before; nothing written |
| 400 | no or bad `X-Skald-Batch`, or a broken gzip body |
| 401 | no token, not a token, or a revoked one |
| 403 | a token of another organisation or site, or without the `ingest` scope; or the site waits for its domain to be verified (docs/SAAS.md) |
| 404 | ingest is off, or the site is not processed here |
| 405 | not a POST |
| 402 | the organisation is read-only (saas: cancelled, or unpaid past the grace days) |
| 410 | the site was removed |
| 411 / 413 / 415 | no length / over 5 MiB / an encoding other than gzip |
| 429 | too many batches, the day's file is full, the organisation's bytes for the day are used up, or the plan's limit (`Retry-After`) |
| 503 | accounts are not set up |
| 507 | less than `ingest.min_free_gb` free on the ingest root's disk |

### The helper's set-up routes

Under `<page>/sites/...`, so the nginx route every install already has
(`sites(?:/[a-z]+)?`) reaches them (`skald/connections_api.py`, routed
by `sites_api.py`). Owner or admin only; POSTs need the session's
`X-Skald-CSRF`.

| Method, path | Answer |
| --- | --- |
| GET `sites/status?site=<name>` | `{ok, site, ingest_enabled, send_url, folder, received, last_batch, last_contact, today, last_refusal, verify, beacon, setup, now}` (DATA-CONTRACT.md, "Connections status") |
| POST `sites/kit` | `{site, method: docker\|systemd\|server, include_token?, token?}` -> the zip (`application/zip`, `skald-ship-<site>.zip`), or with `server` the one bash file (`text/x-shellscript`, `skald-install-<site>.sh`); 400 for a token that is not a sending token of that site, or a kit this server cannot build |
| POST `sites/link` | `{site}` -> `{ok, url, command, expires_at, token, token_id}`: a new sending token (shown once) and the one-time install link, `curl -fsSL <url> \| sudo bash`, for 24 hours; 409 when the log endpoint is off |
| POST `sites/pack` | `{site, include_secrets, token?, lead_secret?}` -> `skald-setup-<site>.zip` (`application/zip`); a token made for it is named in `X-Skald-Token-Id` |
| POST `sites/packmail` | `{site, to: [up to 3], include_secrets, token?, lead_secret?, note?}` -> `{ok, sent_to, token_id, lead_secret_made}`; 400 for a bad address, 409 when mail is not set up, 429 after 10 an hour per site, 502 when the mail server refused it |
| POST `sites/agentlink` | `{site, leads: bool = true}` -> `{ok, line, llms_url, steps_url, expires_at, token_id, link_id, cancelled}`: the one line for an AI agent ("One line for your AI agent", above); never the token or the lead secret; the site's older unused lines are cancelled; 409 when the log endpoint is off |
| POST `sites/agentstatus` | `{site, link_id}` -> `{ok, state, opened_at, keys_at, reported_at, cancelled_at, expires_at, report}`: how far the agent got, for that site's line only |
| POST `sites/agentcancel` | `{site, link_id}` -> `{ok, state: "cancelled"}`: the line ends at once; its token is revoked when the keys were never taken; 404 for an unknown line |
| POST `sites/setup` | `{name, step?, method?, token_id?, done?, found?}` -> `{setup}`, the wizard's progress (method `agent` on the AI agent's way); `found`: a site check's facts, kept cleaned |
| POST `sites/detect` | `{address, name?}` -> `{ok, found}`: the site check (how the site is hosted, read from outside by the safe fetcher, with a suggested way and why); 30 checks an hour per admin, 6 per address in 10 minutes (429). With `name`, a site of the organisation with set-up progress, the facts are kept in that progress too |
| POST `sites/tagcheck` | `{site}` -> `{ok, check: {state, words, fix, facts}}`: the script tag's Test when nothing arrived; Skald reads the site's home page and says what is wrong ([BEACON.md](BEACON.md)); limited like `sites/detect` |
| POST `sites/trylog` | `{site, text, format?}` -> `{ok, report}`: Settings > Connections > Test a sample (2.35), the `try-log` dry run on the first 200 pasted lines (at most 256 KB; 413 above) judged with the site's own settings. `report`: `verdict`, `headline`, `lines`, `read`, `unread`, `reasons`, `format` `{asked, picked, sure, ...}`, `other_layouts`, `times`, `hosts` (an IP address or email in a host shown masked), `hosts_wanted`, `no_host`, `more_hosts`, `groups` (the five groups' requests, views, readers), `counted` (`adds_up` and its terms), `pages` (the top 5 people pages, addresses and emails masked), `warnings`, `notes`, `site_name`. Nothing is stored or logged, not the lines, not the report; 60 tests an hour per admin (429) |
| POST `sites/add` | as before; `token: false` makes no token (the wizard makes a named one later) |
| POST `sites/share`, GET `sites/shares`, POST `sites/unshare` | "Share with your developer" links (`share_links.py`, `share_api.py`): a private page at `/traffic-auth/setup/<id>` with one task's steps for one site, no sign-in, 1, 7 or 30 days. Only the id's SHA-256 is kept. The sending token is made when the developer presses Show the secret, once, in the name of the admin who made the link |
| GET `sites` | as before; to admins also `kit {docker, systemd, server, why, image, ship_path}`, `api_base`, `mcp_url`, `mcp_enabled`, `beacon_on`, and per site `setup` and `quiet` (set up, and nothing reached Skald for 24 hours) |
