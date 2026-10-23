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
3. **How visits reach Skald**: Docker shipper, systemd shipper, Cloudflare
   (the Skald Worker), Vercel or Netlify (log drain), or only the script tag.
   Choosing Cloudflare for a dashboard site that has received nothing yet
   sets its format to `edge_json` (audit `site.format`); any other choice sets
   `auto` on the same terms.
4. **Install**: a named sending token (`tokens/create`, scope `ingest`, this
   site only, shown once), the steps for the method with the send address
   and token filled in, and the install kit (below).
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

For a site that exists already, **Settings > Connections > Send this site's
visits to Skald** has the same steps 3 to 5 (choose how, sending token,
install, test).

The first figures appear after the next daily run. On a SaaS install the
plan decides how many sites an organisation may have.

On the server, an install admin can do the same with
`skald site add shop.example.com --org <slug>` and make the token with
`skald token create shipper --scope ingest --site shop.example.com`.
A site from a config file can ship its log too: make an ingest token for it
(Settings > Connections > Send this site's visits to Skald, or Settings > Add
or remove sites > New token) and point its `logs.dir` at `<ingest root>/<site>`.

## One command: the one-file installer and the install link

The shortest way onto a Linux web server is one command the site's admin runs there:

```sh
curl -fsSL https://stats.example.com/traffic-kit/<code> | sudo bash
```

Settings > Connections makes it (`POST <page>/sites/link`): a new sending token for that
one site (named "Sending logs: <site>, <day> (one-command install)", in the audit log as
`token.create`, then `kit.link`) and a link that works **once, for 24 hours**. The link
answers the installer with the token inside to curl or Wget, then never again; a used,
expired or unknown link answers 410 with a two-line script that says so and exits 1 (with
`curl -f` only curl's own error shows). A browser or a mail's link preview gets the words
"Run this on your server: ..." and does not use the link up. Options go after
`bash -s --`: `curl -fsSL <link> | sudo bash -s -- --log /var/log/nginx/x.log`.

The link's store, `kit-links.json` beside the history (0600, expired entries dropped on
each write), keeps only the SHA-256 of the code, the site, the expiry and the token
XORed with a keystream made from the code (HMAC-SHA256): the server's disk never holds a
usable token. `/traffic-kit/` is answered by the beacon helper (`beacon_server.py`,
`skald/kit/link.py`), limited to 10 tries a minute per address, `Cache-Control:
no-store`, `X-Robots-Tag: noindex`, and never logged (nginx: `access_log off`, DEPLOY.md).

The same installer is one file to download: "Download the installer (.sh)",
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
- **What it leaves:** `/usr/local/bin/skald-ship-check` (check.sh, read-only) and
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
store), else a new one when the site has none (audit `hook.secret`). A lead secret that
already exists is never copied out: the pack says how to make a new one (which stops the
old one). Mailed (`sites/packmail`): through the install's mail settings (Settings >
Mail), to up to 3 addresses, subject "Set up Skald for <site>", 10 mails per site an hour.
A mail that does not go takes its new token back (revoked) and its new lead secret.
Audit `kit.pack` and `kit.packmail`: who, the site, how many recipients, keys or not;
never an address or a key.

## The install kit and check.sh

A zip the site's admin runs on their own web server, with no SSH from Skald's
side. Settings > Connections (and step 4 of Add a site) offers it as
"Download the install kit (.zip)" (`POST <page>/sites/kit`); the same zip
comes from the command line:

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

The Docker kit needs the image name: `ingest.kit_image` in the config, else
the `SKALD_KIT_IMAGE` environment variable. The Docker image's entrypoint sets
`SKALD_KIT_IMAGE` to itself at its major version, and `SKALD_KIT_SHIP_PATH` to
the shipper inside it (`ingest.kit_ship_path` overrides it). Without an image
the page offers no Docker kit and says why; without `tools/skald-ship.py`, no
systemd kit (SETTINGS.md).

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
| Cloudflare, CloudFront, Fastly | `cloudflare_json`, `cloudfront_w3c`, `fastly_json` | see CDN-LOGS.md |
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
inside the site are not counted yet") and `check.sh` say so when the log has
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
| POST `sites/setup` | `{name, step?, method?, token_id?, done?}` -> `{setup}`, the wizard's progress |
| POST `sites/add` | as before; `token: false` makes no token (the wizard makes a named one later) |
| POST `sites/share`, GET `sites/shares`, POST `sites/unshare` | "Share with your developer" links (`share_links.py`, `share_api.py`): a private page at `/traffic-auth/setup/<id>` with one task's steps for one site, no sign-in, 1, 7 or 30 days. Only the id's SHA-256 is kept. The sending token is made when the developer presses Show the secret, once, in the name of the admin who made the link |
| GET `sites` | as before; to admins also `kit {docker, systemd, server, why, image, ship_path}`, `api_base`, `mcp_url`, `mcp_enabled`, `beacon_on`, and per site `setup` and `quiet` (set up, and nothing reached Skald for 24 hours) |
