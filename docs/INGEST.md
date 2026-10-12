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

It is **off by default**. An install does not change until
its config switches it on.

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

In the dashboard: **Settings > Add or remove sites > Add a site** (an owner
or admin of the organisation). Give the host name (it is also the site's
name), the time zone and the log format. Skald then:

- makes the site, owned by your organisation, with its log folder under the
  ingest root;
- makes an **ingest token** for that one site, and shows it **once**;
- shows the shipper command and the optional `skald.js` tag.

The first figures appear after the next daily run. On a SaaS install the
plan decides how many sites an organisation may have.

On the server, an install admin can do the same with
`skald site add shop.example.com --org <slug>` and make the token with
`skald token create --name shipper --scope ingest --site shop.example.com`.
A site from a config file can ship its log too: make an ingest token for it
(Settings > Add or remove sites > New token) and point its `logs.dir` at
`<ingest root>/<site>`.

## Installing the shipper (Ubuntu or Debian)

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
| any of these | `auto` | each line is read by whichever format reads it |

Ship the log of the server that sees the visitors. Behind a CDN, that is the
CDN's log (CDN-LOGS.md), never both.

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
- **Files:** `access.log` (today, UTC), `access.log.1` (the day before),
  `access.log.2.gz` ... `access.log.<keep>.gz`. The folder also holds
  `.ingest-state.json`: the last batch number per shipper and counts, no
  log content.

## Never a line lost, never one counted twice

- The shipper saves its place (file, inode, offset, last batch number) only
  after Skald answered 2xx. Until then it sends the batch again, waiting
  longer each time (1 s doubling to 5 minutes, with jitter); 429 and 503
  wait for `Retry-After`; 413 splits the batch.
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
  side as a hash only, shown once, and revoked in Settings > API & tokens. A token
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
Over a limit, the batch gets 429 with the reason and the shipper waits an hour
before trying again: nothing is lost while the plan is changed. Without
that module there is no limit.

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
`skald site add`, Settings > Sites and sign-up refuse it, unless an install
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
