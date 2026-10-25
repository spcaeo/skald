# Deploying skald on a server

Everything an Ubuntu web server with nginx needs to run the daily system
(history, dashboard, mail). The method behind it is in SOP.md section 7.

## 1. What the server needs

| Need | Detail |
| --- | --- |
| Python | 3.11 or newer (Ubuntu 24.04 ships 3.12; on 22.04 install python3.11). Standard library only - no pip install. PyYAML is used if present, not required. |
| Time zones | the `tzdata` package (present on a standard Ubuntu). `report.timezone` must be a name it knows, e.g. `America/New_York`. |
| Log format | the `nginx_extended` layout from SOP.md section 3 - it carries the host (for `site.hosts`) and the country, from Cloudflare's header or a local GeoIP2 database (`cc=$geoip2_country`). A file that switches format part-way through parses fine. |
| Log retention | logrotate's default `daily` / `rotate 14` is enough. More only helps the first backfill. |
| A user | a system user that can read `/var/log/nginx` (member of `adm`) and write the history and dashboard directories. Not root. |
| Outbound SMTP | to the relay in `mail.host`, port 587 (STARTTLS) or 465 (TLS). |
| Country credit | with a DB-IP Lite (CC BY 4.0) database, set `report.country_credit: IP geolocation by DB-IP` and `report.country_credit_url: https://db-ip.com`. Leave empty for Cloudflare. |

## 2. Paths

| Path | Owner / mode | What |
| --- | --- | --- |
| `/opt/skald/` | root, 0755 | this repository |
| `/etc/skald/config.yml` | root:skald, 0640 | copied from `config.example.yml` and edited |
| `/etc/skald/env` | skald, 0600 | SMTP login, see below |
| `/var/lib/skald/` | skald, 0750 | `history.sqlite` (`history.db`), and `live-<site>.json`, today's live snapshot; the private `live-<site>-ai.json` and `live-<site>-requests.json` (0640, raw addresses); state files `runs.json`, `alerts-state.json`, `markers.log`, `config-hash`, `website-version.json`, `forgotten.json`, `privacy.log`, `failmail-state.json`; with the 2026-10-11 parts, `accounts.sqlite`, `conversions.sqlite` (0640; since 2.4.0 it can hold each visit's address and leads' names and emails, see the README's "What is kept") and `secrets.json` (0600) |
| `/var/lib/skald/ranges/` | skald, 0750 | `bots.ranges_dir`: crawler owners' address lists, hosting networks, `dns.json` |
| `/var/lib/skald/backups/` | skald, 0750 | `backup.dir`: nightly and weekly copies of the history, and of the accounts and conversions files when there are any (0640) |
| `/var/www/skald/` | skald, 0755 | the dashboard (`dashboard.out`): `index.html`, `<site>/index.html` (the web app), `<site>/classic.html` (the plain page), `<site>/<view>/...`, the app's code in `_app/`, and `data/` and `exports/` folders beside each page; all written 0644 |
| `/var/log/skald/` | skald, 0750 | the cron job's own output |

On the server:

```sh
sudo useradd --system --no-create-home --shell /usr/sbin/nologin skald
sudo usermod -aG adm skald
sudo install -d -o root -m 0755 /opt/skald
sudo install -d -o root -g skald -m 0750 /etc/skald
sudo install -d -o skald -m 0750 /var/lib/skald /var/log/skald
sudo install -d -o skald -m 0755 /var/www/skald
```

The server needs no git. Ship the code from your own checkout of this repo.
`git archive HEAD` sends committed files only; anything not committed does
not go. Log in as root here, or as a user whose `sudo` asks no password:

```sh
git archive HEAD | ssh <server> 'sudo tar -x -C /opt/skald'
tools/build-info.sh | ssh <server> 'sudo tee /opt/skald/build.json /var/www/skald/build.json >/dev/null'
```

Back on the server:

```sh
sudo install -o root -g skald -m 0640 /opt/skald/config.example.yml /etc/skald/config.yml
```

In `config.yml` set at least: `site.name`, `site.hosts`, `logs.dir`,
`ours.user_agents`, `report.timezone`, `history.db`, `dashboard.out`,
`dashboard.url`, and the whole `mail:` section.

## 3. The SMTP environment file

The config holds only the NAMES of the variables (`mail.user_env`,
`mail.password_env`). The values go here and nowhere else:

```sh
# /etc/skald/env  - owner skald, mode 0600
export SMTP_USER='account@example.com'
export SMTP_PASSWORD='the-app-password'
```

The names are whatever `mail.user_env` and `mail.password_env` say;
`SMTP_USER` and `SMTP_PASSWORD` are the example config's.

For Gmail: `mail.host: smtp.gmail.com`, `port: 587`, `security: starttls`.
The password is an app password (the account needs 2-step verification),
not the account password, and `mail.from` must be that account or an alias
verified on it - Gmail rewrites any other From.

If a variable the config names is missing, the mail is refused rather than
sent without a login. Leave `user_env` and `password_env` empty only for a
relay that needs no login; with `mail.security: none` (a relay on localhost)
credentials are refused outright.

## 4. First run, by hand

```sh
sudo -u skald sh -c '. /etc/skald/env && cd /opt/skald && \
  ./bin/skald --config /etc/skald/config.yml check && \
  ./bin/skald --config /etc/skald/config.yml backfill --days 14 && \
  ./bin/skald --config /etc/skald/config.yml dashboard && \
  ./bin/skald --config /etc/skald/config.yml mail --daily --dry-run && \
  ./bin/skald --config /etc/skald/config.yml mail --weekly --dry-run'
```

`check` must say `ok`. If it says "nothing parsed", the log format or
`logs.dir` is wrong; fix that before going further. Before the first run, or
when it fails, `./bin/skald try-log /var/log/nginx/access.log` reads a sample and
says which reader fits, which lines fail and why, and what Skald would count
(it stores nothing; docs/INSTALL.md, "Try a log first"). The two dry runs print
the mail without sending it - read them. Then `./bin/skald --config
/etc/skald/config.yml doctor` lists every part, OK or NEEDS ATTENTION
with the fix (docs/INSTALL.md, "Check it"); after a deploy too.

## 5. Cron

`/etc/cron.d/skald`:

```cron
MAILTO=ops@example.com
# Server clock. Pick a time at least an hour after midnight in
# report.timezone: 11:15 UTC is 07:15 in New York in summer, 06:15 in winter.
15 11 * * * skald . /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml run-daily >>/var/log/skald/run.log 2>&1 || /opt/skald/bin/skald --config /etc/skald/config.yml notify-failure --job run-daily --exit $? --log /var/log/skald/run.log >>/var/log/skald/run.log 2>&1
```

When `run-daily` fails (a crash, a step error, a missing mail setting),
`notify-failure` sends one short mail to the daily mail's recipients (the
confirmed ones set on Settings > Mail, else config.yml's `mail.to`), at most
one per 12 hours. A day that is withheld because it does not add up is not a
failure and sends no extra mail. The weekly mail goes out
on the run whose local date (in `report.timezone`) is a Monday.

A heartbeat line in the same file: one small request to your own site
every 5 minutes. It proves the site was up, so a quiet hour is never a gap,
and the "site down" alert works from it. List its agent in
`ours.user_agents` as `{agent: skald-heartbeat, label: heartbeat}` (the label
is `report.heartbeat_label`), or it counts as a visitor:

```cron
*/5 * * * * skald curl -s -o /dev/null -A "skald-heartbeat" https://www.example.com/robots.txt
```

The "Today so far" panel needs one more line in the same file:

```cron
*/2 * * * * skald . /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml live >>/var/log/skald/live.log 2>&1
```

It writes only `live-<site>.json` beside the history and the dashboard
files - never the history, never mail. Its output goes to `live.log` and
never to cron mail; it exits 1 when today's figures do not reconcile (the
panel then says withheld). A run takes about a second on a busy day, so two
runs do not overlap; if the log ever grows enough that they might, wrap it
in `flock -n /var/lib/skald/live.lock`. Both writers replace files
atomically, so the daily run and a live run finishing together are safe.
`live.log` grows by a line every two minutes: add it to logrotate with the
other files in `/var/log/skald/`.

Release 2 adds a nightly backup (any quiet hour; not 11:10-11:30 UTC):

```cron
30 5 * * * skald . /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml backup >>/var/log/skald/backup.log 2>&1 || echo "skald backup failed; see /var/log/skald/backup.log"
```

Release 2.36 adds the daily summary: one mail per person with what to look at on every site
they get security alerts for (security items, to-dos, set-up problems; nothing when nothing is
open, never twice a day). Run it every hour with `--after 01:00`: it sends once the site's
local time (`report.timezone`) is past 01:00, whatever the server clock and summer time do:

```cron
0 * * * * skald . /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml summary-mail --after 01:00 >>/var/log/skald/summary.log 2>&1
```

`summary-mail --dry-run` prints the mails without sending them. Docker runs it by itself at
`SKALD_SUMMARY_AT` (01:00; `off` stops it).

That is all: run-daily runs `verify-bots` first when `bots.ranges_dir`
is set, and the live run checks the alerts and markers itself. Set it: without
`bots.ranges_dir` no crawler claim is checked (a fake Googlebot counts as
Googlebot, a browser from a cloud is not flagged), and `doctor` says "crawler
checks off". The Docker image sets it by default (`SKALD_VERIFY_BOTS`). A first
fetch is about 37 requests (8 MB down, 1.3 MB kept, under a minute); lists
fetched in the last 12 hours are not fetched again, so several sites share one
fetch a morning. The server
needs outbound HTTPS for the lists (Google, Bing, Apple, OpenAI, Perplexity,
Anthropic, DuckDuckGo, stat.ripe.net) and DNS; a failure keeps the last
good copy and never stops a run. List `site-version-check` in
`ours.user_agents` (label "version check") when `markers.version_url` is set:
that is the agent the footer check sends.

Two switches added with the drill-down work: `dashboard.favicons: true`
fetches referring sites' icons (outbound HTTPS to those sites, 3 s each,
never failing a run; `pip install pillow` would make them 32x32 PNGs) and
`mail.weekly_report_attachment: true` attaches the HTML report to the
weekly mail. `skald report --format html|csv-zip --out PATH` needs nothing.

Release 3 on the server: `pagespeed.enabled: true` (run-daily calls Google
after the mails; outbound HTTPS to www.googleapis.com, at most 10 calls a
day), `access.htpasswd` naming the dashboard's nginx password file, and in
nginx (the `/traffic/` block) one more route to the helper for `me`,
`funnels` and `api/v1`, `X-Skald-User $remote_user` passed on every helper
route, and a `/traffic-api/` location without a password for token
requests. The helper (`skald-refresh`) must be restarted after a
deploy that changes it: `systemctl restart skald-refresh`. Roles:
`skald user role <owner> --role admin` writes the first roles file (before
it exists every login is admin); add people with
`skald user add NAME --role viewer` as root.

People (2.4.0): the person search and the left-out lists are helper routes,
`<page>/people` and `<page>/people/*`. In sessions mode the route below has
them. In basic mode, add `people` and `people/[a-z-]+` to the `/traffic/`
block's helper route, with `X-Skald-User $remote_user` (the search is for
`users.json` roles admin and owner; its audit line goes to `privacy.log`).
The token route `/traffic-api/v1/<site>/people?q=` needs no change.

Compare and page lifecycle: history schema 11 (`page_milestones`, upgraded
in place after a `.schema-v10.bak` copy). The nginx route to the helper adds
`api/compare` and `api/page`. `report.pages_meta` points at the website's page
dates (`/etc/skald/pages.json`, root:skald 0640), written at
the website's deploy. After the first deploy run
`skald backfill --days 14 --force` so the days the logs still hold get the
new detail, then `skald audit --day` each of them.

Performance (issue #2, [docs/PERFORMANCE.md](docs/PERFORMANCE.md)): history schema 12,
accounts 5 and conversions 3 add indexes only. Each file is upgraded in place on first open,
in one transaction; nothing to run. The conversions file keeps a `.v2.bak` copy, as its
upgrades always do; the history needs none (no row changes).

People (2.4.0): history schema 13 changes no table. A file upgraded from 12 or older gets one
meta row (`privacy_legacy`), so an upgraded install keeps no address and no lead email until
someone turns `privacy.keep_ips` and `conversions.identity` on; a new install keeps both
(people/policy.py). `conversions.sqlite` schema 4 adds the `test` mark, the kept visits
(`visits`, `visit_days`) and the `removed` rows, after a `.v3.bak` copy. Change the site's
privacy notice before turning them on.

Security (2.21): `conversions.sqlite` schema 8 adds `security_rows` and `security_days` (the
addresses behind Security's rows, written only while `privacy.keep_ips` keeps addresses),
after a `.v7.bak` copy; history gains the day kind `security` (no table change). Days stored
before the upgrade read "not recorded" in Security until `backfill` counts them again from
the raw lines still on the server.

### Deploying a new version

An install made by install.sh from a published release upgrades with `skald upgrade`
instead (backup, migrations, health check, rollback: docs/UPGRADING.md). By hand, as below,
`skald migrate --check` before and `skald migrate` after the code shows the database steps.
run-daily's `updates` step (after the recounts, before `dashboard`) asks GitHub at most once a
day whether a newer release is out; it never stops the run.

Outside 11:10-11:30 UTC (the daily run). Commit first: only committed files
ship. Lines marked "server" run there as root; the others run in your checkout.

```sh
# server: back up the code (rollback copy) and the history
rsync -a --delete /opt/skald/ /opt/skald.prev/
sqlite3 /var/lib/skald/history.sqlite ".backup /var/lib/skald/backups/history-pre-<what>-$(date -u +%Y%m%dT%H%M).sqlite"
# checkout: ship committed files only, then write build.json (name, version, release, commit, time)
git archive HEAD | ssh <server> 'rm -rf /opt/skald && mkdir /opt/skald && tar -x -C /opt/skald'
tools/build-info.sh | ssh <server> 'tee /opt/skald/build.json > /var/www/skald/build.json'
# server: only if a file in systemd/ changed - install the changed unit(s), then reload systemd
cp /opt/skald/systemd/<changed unit> /etc/systemd/system/ && systemctl daemon-reload
# server: restart the helpers so they run the new code (safe every time; leave out any you did not install)
systemctl restart skald-refresh skald-beacon && systemctl is-active skald-refresh skald-beacon
# server: redraw today, recount it by the second road, and record the deploy
sudo -u skald sh -c '. /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml live && ./bin/skald --config /etc/skald/config.yml audit --live'
sudo -u skald /opt/skald/bin/skald --config /etc/skald/config.yml mark-deploy --label "<what>" --detail "<commit>"
```

Take the code backup (the first line) **once per deploy**. If a later step
fails, do not run it again: it would copy the broken code over the good
rollback copy. Fix and carry on from the step that failed, or roll back
(below) first. `refresh_server.py --origin` in the refresh unit names your
own dashboard's origin; edit the copy in `/etc/systemd/system/` before you
start it, and keep that edit when you install a newer unit.

`build.json` is what the dashboard's footer, its printed reports and
exports say is deployed: `{"name","version","release","commit","deployed_at"}`.
It is written from your checkout (the server has no git history): the name
is the repo's `NAME` file (the one place to rename the tool), the version
`VERSION` (semver, raised by hand for a release worth naming), the release
the commit count of HEAD. It sits at the dashboard's root, beside the site
folders, so the app's own copy step (which empties `_app/` of old files)
never removes it; a page reads `../build.json`. Without it the footer is
simply blank.

`mark-deploy` is the deploys log (`markers.log`); the mtime of
`/opt/skald.prev` is not. Roll back with
`rsync -a --delete /opt/skald.prev/ /opt/skald/`, then
`cp /opt/skald/build.json /var/www/skald/build.json` and
restart the helpers.

The `history-pre-*.sqlite` copies a deploy takes are never pruned: the
nightly backup prunes only its own daily and weekly copies. Delete old ones
by hand now and then, keeping the newest few:
`ls -t /var/lib/skald/backups/history-pre-*.sqlite | tail -n +4 | xargs -r rm --`
(keeps three).

### "Refresh now" button (optional)

`dashboard.refresh_button: true` in the config draws a **Refresh now** button on the live panel. It posts to
`<page>/refresh`; nginx (same password) forwards that to `skald/refresh_server.py` on 127.0.0.1:8765,
which runs `live` (about a second) and sends the browser back. Same-origin only, one run per 15 seconds.

```sh
cp systemd/skald-refresh.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now skald-refresh
```

nginx, inside the `/traffic/` location (its Content-Security-Policy in section 6 already has `form-action 'self'`, which the button needs):

```nginx
location ~ ^/traffic/[a-z0-9.-]+/(?:[a-z0-9-]+/)?refresh$ {
  limit_except POST { deny all; }
  proxy_pass http://127.0.0.1:8765;
  proxy_set_header Host $host;
}
```

### Request id in the log

The log line ends with ` rid=$request_id` (32 hex characters, unique per
request). Deploy the code first (it reads lines with and without it), then
change the `log_format` and `nginx -t && systemctl reload nginx`. A line that
repeats an earlier line's request id is the same request written twice: it is
dropped and counted as `duplicates_removed` in quality.json.

### Optional fields at the end of the line (2.18, 2.21)

- **A Next.js site:** append ` rsc_prefetch=$http_next_router_prefetch` (Apache:
  ` rsc_prefetch=%{Next-Router-Prefetch}i`) so a click inside the site counts as a page
  view and a link prefetch never does (COUNTING-TRAPS.md trap 10). Required for every
  Next.js site; without it only the first page of each visit is seen.
- **Security's large POST bodies:** ` request_length=$request_length` lets Security >
  Attack attempts list POST bodies of 1,000,000 bytes or more; without it that line says
  "not recorded".

Both go at the end of the line, beside `rid=`, and both counts read them. The exact lines and
why they are safe: [docs/INGEST.md](docs/INGEST.md), "Log formats".

### AI crawler settings (optional)

The dashboard's crawler rules (AI & bots > Crawler rules; Settings > AI crawlers
before 2.7.0) save a policy (allow, block, or block training only,
per assistant; allow or block per crawler) through the refresh helper into
`/var/lib/skald/bot-policy.json`. Root applies it: a path unit runs
`skald/bot_policy.py apply`, which writes
`/etc/nginx/conf.d/skald-bot-policy.conf` (a `map` giving `$skald_block`),
runs `nginx -t`, reloads, and puts the previous file back if the test fails.
The outcome is in `bot-policy-applied.json` beside it. Without a policy file
everything is allowed.

```sh
cp systemd/skald-bot-policy.service systemd/skald-bot-policy.path /etc/systemd/system/
systemctl daemon-reload
systemctl start skald-bot-policy.service     # writes the all-allow map once
systemctl enable --now skald-bot-policy.path
```

Then, in the site's `location / { }` (never in the dashboard's, the short-link
or relay locations), and only after the map file exists:

```nginx
if ($skald_block) { return 403; }
```

robots.txt is never refused (the map exempts `/robots.txt`), so a blocked
crawler can still read the rules; `GET <page>/bot-policy` also gives the
robots.txt lines matching the policy, as a suggestion to copy by hand. The
403s per crawler are in `bots.json` (`blocked`). nginx route, inside the
`/traffic/` location:

```nginx
location ~ ^/traffic/[a-z0-9.-]+/(?:[a-z0-9-]+/)?bot-policy$ {
  limit_except GET POST { deny all; }
  proxy_pass http://127.0.0.1:8765;
  proxy_set_header Host $host;
  proxy_set_header X-Skald-User $remote_user;   # saving is for admins (access.py)
}
```

### In-page event beacon (optional)

Button clicks, form steps and demo bookings, posted by the site's own pages
to `POST /traffic-beacon` (docs/BEACON.md has the fields, the events and the
website side). A second helper, public but same-origin only:

```sh
cp systemd/skald-beacon.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now skald-beacon     # 127.0.0.1:8766
```

Run it even without the beacon: it is also the receiver of the signed tool hooks
(docs/INTEGRATIONS.md). With no `beacon.origins` it takes hooks only (2.2.2).

Set `beacon.enabled`, `beacon.origins` and `beacon.log` in the config, and
add the nginx `limit_req_zone`, `log_format` and `location = /traffic-beacon`
from docs/BEACON.md to the site's HTTPS server. run-daily then collects,
verifies and audits yesterday's events (step "events", which never stops the
run); the spool is `/var/lib/skald/beacon/` (no addresses, 400 days).

## 6. nginx: serve the dashboard privately

The dashboard is files on disk. Serve `dashboard.out` behind basic auth (or
sessions mode, below), with
headers that keep it out of indexes even if the auth is ever removed. If the
server already has such a location (auth, `X-Robots-Tag`, `no-store`, and no
access logging for it), nothing here needs adding - only `dashboard.url`.
Otherwise:

```sh
sudo apt-get install -y apache2-utils
sudo htpasswd -B -c /etc/nginx/skald.htpasswd <reader-name>
sudo chown root:www-data /etc/nginx/skald.htpasswd
sudo chmod 0640 /etc/nginx/skald.htpasswd
```

Inside the HTTPS `server { }` block that should host it:

```nginx
location /traffic/ {
    alias /var/www/skald/;
    index index.html;
    autoindex off;

    auth_basic           "Traffic";
    auth_basic_user_file /etc/nginx/skald.htpasswd;

    add_header X-Robots-Tag    "noindex, nofollow, noarchive" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header Cache-Control   "private, no-cache" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Content-Security-Policy "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
}
```

The dashboard is a small web app. It loads its own script, styles and data
files from this host only, and nothing from anywhere else, so the policy
allows `'self'` and no other source: `script-src` and `connect-src` for the
app and its data, `img-src data:` for its inline icons, `form-action 'self'`
for the Refresh now and settings forms. Without `script-src 'self'` the page
stays blank. The country credit is a plain link, which the policy does not
block. Then set `dashboard.url` to
`https://www.example.com/traffic/<site.name>/` (your host) - each site's page is in a
directory named after `site.name` - so the mail links to it, and
`sudo nginx -t && sudo systemctl reload nginx`.

If this location is on a host listed in `site.hosts`, give it its own log so
your own dashboard views are not counted as people. Add inside the location:

```nginx
    access_log /var/log/nginx/skald-dashboard.log;
```

A location-level `access_log` replaces the server's for those requests only.

### Sessions mode (accounts)

Instead of one nginx password, people sign in with their own email and
password, in organisations with roles (owner, admin, viewer), with invites,
password resets, optional two-step sign-in, API tokens and an audit log
(docs/ACCOUNTS.md). Basic mode stays the default and changes nothing; the
switch is one config change and one nginx reload, and so is the way back.

**Config keys.**

| Key | What it does |
| --- | --- |
| `access.mode` | `basic` (default: nginx basic auth, users.json) or `sessions`. |
| `access.base_url` | `https://www.example.com`: the start of every link in a mail (invites, resets). Never taken from the request's Host header. |
| `access.accounts` | The accounts file. Default `accounts.sqlite` beside the history (0640, like it). |
| `access.trust_proxy_ip` | Default `true`: believe nginx's `X-Real-IP` on the helper's 127.0.0.1 connection (sign-in limits per address, "add my address"). Set `false` if other local users could reach port 8765 and fake it, or use `refresh.socket`. |
| `refresh.socket` | e.g. `/run/skald/helper.sock`: the helper listens only on this Unix socket (0660), not on 127.0.0.1:8765. |
| `refresh.socket_group` | The socket's group, default `www-data` (nginx's). The service needs that group: uncomment `RuntimeDirectory=`, `RuntimeDirectoryMode=` and `SupplementaryGroups=` in `systemd/skald-refresh.service`. |
| `mcp.enabled` | `true` turns on `POST /traffic-mcp` for agents with a token that has the `mcp` scope (docs/MCP.md). Needs sessions mode. Docker: `SKALD_MCP=true` (2.26). |
| `ingest.enabled` | `true` turns on `POST /traffic-ingest/<site>` for skald-ship (logs from other servers) and Settings > Add or remove sites (docs/INGEST.md). Needs sessions mode. `ingest.root` (default `<history folder>/ingest`), `per_minute`, `burst`, `keep`, `max_mb`, `url`. |

**Set up the accounts** (as the skald user, before switching nginx;
nothing changes for visitors yet):

```sh
sudo -u skald ./bin/skald --config /etc/skald/config.yml \
  accounts init --org "Example Co" --owner-email owner@example.com \
  --map alice=alice@example.com --base-url https://www.example.com
```

It makes the accounts file, the organisation and its owner (also the install
admin), gives the organisation every site, turns each `users.json` name into
an invite (asks for the email on a terminal, or `--map NAME=EMAIL`), moves
`tokens.json` in (the tokens keep working) and prints the owner's
"set your password" link and every invite link (valid 60 minutes and 7
days). An invite link printed but not mailed is "handed": that person picks
a password on the invite page and then chooses a new one at the first
sign-in. `skald accounts status` shows what is there.

**The helper.** Restart it after the config change:
`systemctl restart skald-refresh`. With `refresh.socket`, install the
unit with the three lines uncommented first (`systemctl daemon-reload`).

**nginx.** This is the one authoritative sessions-mode config: every route
either helper answers, and nothing else. `tests/test_nginx_routes.py` reads
the three blocks between the markers below and checks that every path the
code answers (generated from the helpers' own route patterns) reaches the
right helper, so a new route cannot be left out. Change them together.

<!-- skald-nginx-sessions:begin -->

At the http level (a file in `/etc/nginx/conf.d/`, or the top of the site's
file):

```nginx
# ---- http level ----
# The two helpers. With refresh.socket, use the unix line instead of 8765.
upstream skald_helper {
    server 127.0.0.1:8765;          # refresh_server.py: the dashboard's routes, sign-in, API, ingest, MCP
    # server unix:/run/skald/helper.sock;
}
upstream skald_beacon {
    server 127.0.0.1:8766;          # beacon_server.py: /traffic-beacon, /traffic-hooks/, /traffic-js/, /traffic-kit/
}
# Sign-in, forgot-password and sign-up POSTs: 10 a minute per address, a burst
# of 5. (GETs of the pages are not counted: their key is empty.) Behind a CDN,
# set real_ip first so $binary_remote_addr is the visitor's address.
map $request_method $skald_auth_post { POST $binary_remote_addr; default ""; }
limit_req_zone $skald_auth_post zone=skald_auth:10m rate=10r/m;
# Shipped log batches (docs/INGEST.md), per sending address.
limit_req_zone $binary_remote_addr zone=skald_ingest:10m rate=5r/s;
# In-page events (docs/BEACON.md): 60 a minute per address; a log with no address in it.
limit_req_zone $binary_remote_addr zone=skald_beacon:1m rate=60r/m;
log_format skald_beacon '$time_iso8601 $status $upstream_http_x_skald_site';
# Signed hooks from the site and its tools (docs/INTEGRATIONS.md).
limit_req_zone $binary_remote_addr zone=skald_hooks:1m rate=60r/m;
```

Two snippets, the proxy settings every route shares. An empty value means
nginx does not pass the header on, so a browser can never send its own
`X-Skald-User` or `X-Skald-Role` (the helper ignores them in sessions mode
anyway):

```nginx
# ---- /etc/nginx/snippets/skald-helper.conf ----
proxy_pass http://skald_helper;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Skald-User "";
proxy_set_header X-Skald-Role "";
```

```nginx
# ---- /etc/nginx/snippets/skald-beacon.conf ----
proxy_pass http://skald_beacon;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Skald-User "";
proxy_set_header X-Skald-Role "";
```

Inside the HTTPS `server { }` block, in place of the basic-mode `/traffic/`
location (section 6), its helper routes, `/traffic-api/`, and the beacon,
hook and script locations of docs/BEACON.md and docs/INTEGRATIONS.md:

```nginx
# ---- server level ----
# The session check: nginx asks the helper before every /traffic/ request.
# X-Original-URI is the address as the browser sent it; X-Original-Path is
# nginx's own normalised path, which the /traffic/ locations below copy into
# $skald_path ($uri here would be /traffic-auth/check itself). The helper
# refuses an address with %, //, . or .. segments or a backslash, and one
# whose two forms name different sites.
location = /traffic-auth/check {
    internal;
    proxy_pass http://skald_helper/traffic-auth/check;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header Host $host;
    proxy_set_header X-Original-URI $request_uri;
    proxy_set_header X-Original-Path $skald_path;
    proxy_set_header Cookie $http_cookie;
    proxy_set_header X-Skald-User "";
    proxy_set_header X-Skald-Role "";
}

# Sign-in, forgot, reset and invite pages, sign-out: no session needed.
location ^~ /traffic-auth/ {
    access_log off;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    include snippets/skald-helper.conf;
}
location = /traffic-auth/login {
    access_log off;
    limit_req zone=skald_auth burst=5 nodelay;
    limit_req_status 429;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    include snippets/skald-helper.conf;
}
location = /traffic-auth/forgot {
    access_log off;
    limit_req zone=skald_auth burst=5 nodelay;
    limit_req_status 429;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    include snippets/skald-helper.conf;
}
# Self-serve sign-up (saas.signup; 404 while it is off, docs/SAAS.md): limited like sign-in.
location ~ ^/traffic-auth/signup(?:-finish)?$ {
    access_log off;
    limit_req zone=skald_auth burst=5 nodelay;
    limit_req_status 429;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    include snippets/skald-helper.conf;
}

# The dashboard: a session on every request.
location = /traffic { return 301 /traffic/; }
location ^~ /traffic/ {
    set $skald_path $uri;              # repeat in every nested location: `set` is not inherited
    auth_request /traffic-auth/check;
    error_page 401 = @skald_login;     # no session: to the sign-in page; 403: not a member
    alias /var/www/skald/;
    index index.html;
    autoindex off;
    access_log off;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    add_header Cache-Control "private, no-store" always;
    add_header Referrer-Policy "no-referrer" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Content-Security-Policy "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;

    # The site switcher and the sites list: from the helper, with only the
    # caller's own organisations' sites (the static files list every site).
    location ~ ^/traffic/(?:index\.html)?$ {
        set $skald_path $uri;
        include snippets/skald-helper.conf;
    }
    location ~ ^/traffic/(?:[a-z0-9.-]+/data/)?sites\.json$ {
        set $skald_path $uri;
        include snippets/skald-helper.conf;
    }
    # Every per-site route the helper answers, /traffic/<site>/[<view>/]<route>:
    # refresh; me; ours (internal addresses); funnels; bot-policy (crawler
    # settings); api/v1, api/compare, api/page, api/realtime; team, account, tokens, audit
    # (team_api.py); settings and settings/* (settings_api.py); sites and
    # sites/* (sites_api.py); billing and billing/* (saas, 404 while off);
    # integrations and integrations/* (integrations_api.py; integrations/search
    # and integrations/search/* are search/api.py); people and people/*
    # (people/api.py); logo and logo/* (the site's logo, logo_api.py).
    location ~ ^/traffic/[a-z0-9.-]+/(?:[a-z0-9-]+/)?(?:refresh|me|ours(?:/(?:add|remove|add-mine|pause|resume|edit))?|funnels(?:/(?:save|delete))?|bot-policy|api/(?:v1/(?:[a-z_]+)?|compare|page|realtime)|team(?:/[a-z-]+)?|account(?:/[a-z-]+(?:/[a-z]+)?)?|tokens(?:/[a-z]+)?|audit|settings(?:/[a-z-]+)?|sites(?:/[a-z]+)?|billing(?:/[a-z]+)?|integrations(?:/[a-z]+(?:/[a-z]+)?)?|ai-answers(?:/[a-z]+(?:/[a-z]+)?)?|people(?:/[a-z-]+)?|logo(?:/[a-z]+)?)$ {
        limit_except GET POST { deny all; }
        set $skald_path $uri;
        include snippets/skald-helper.conf;
    }
}
location @skald_login { return 302 /traffic-auth/login?next=$request_uri; }

# The read-only API with a bearer token instead of a session (tokens in accounts.sqlite).
location ^~ /traffic-api/ {
    access_log off;
    limit_except GET { deny all; }
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    add_header Cache-Control "no-store" always;
    include snippets/skald-helper.conf;
}

# Log lines from skald-ship on other servers (ingest.enabled: true; a token
# with the ingest scope; docs/INGEST.md). POST only; the helper checks the
# token, the size (5 MiB, packed and unpacked) and every line.
location ^~ /traffic-ingest/ {
    access_log off;
    limit_except POST { deny all; }
    client_max_body_size 6m;
    limit_req zone=skald_ingest burst=20 nodelay;
    limit_req_status 429;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    add_header Cache-Control "no-store" always;
    proxy_read_timeout 60s;
    include snippets/skald-helper.conf;
}

# MCP for agents (mcp.enabled: true; a token with the mcp scope; docs/MCP.md).
location = /traffic-mcp {
    access_log off;
    client_max_body_size 64k;
    add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
    add_header Cache-Control "no-store" always;
    include snippets/skald-helper.conf;
}

# Stripe's billing events (saas.billing: stripe; docs/SAAS.md): to the refresh
# helper. An exact match, so it wins over `^~ /traffic-hooks/` below.
location = /traffic-hooks/_billing/stripe {
    limit_except POST { deny all; }
    client_max_body_size 64k;
    access_log off;
    proxy_read_timeout 10s;
    include snippets/skald-helper.conf;
}

# Signed hooks from the site's server and its tools, POST
# /traffic-hooks/<site>/<tool> (docs/INTEGRATIONS.md): to the beacon helper.
# GET too, for the signed GET /traffic-hooks/<site>/leads (2.18; the helper
# answers 405 to a GET of any other hook).
# X-Forwarded-Proto: some tools sign the public address.
location ^~ /traffic-hooks/ {
    limit_except GET POST { deny all; }
    client_max_body_size 64k;
    limit_req zone=skald_hooks burst=30 nodelay;
    limit_req_status 429;
    access_log off;
    proxy_read_timeout 10s;
    include snippets/skald-beacon.conf;
    proxy_set_header X-Forwarded-Proto $scheme;
}

# In-page events from the site's own pages (docs/BEACON.md): to the beacon
# helper, kept out of the main access log.
location = /traffic-beacon {
    limit_except POST { deny all; }
    limit_req zone=skald_beacon burst=30 nodelay;
    limit_req_status 429;
    client_max_body_size 1k;
    access_log /var/log/nginx/skald-beacon.log skald_beacon;
    add_header Cache-Control "no-store" always;
    add_header X-Robots-Tag "noindex" always;
    include snippets/skald-beacon.conf;
}

# The skald.js tag (docs/INTEGRATIONS.md): to the beacon helper, which serves
# /traffic-js/skald.js only (404 for anything else).
location ^~ /traffic-js/ {
    limit_except GET { deny all; }
    access_log off;
    include snippets/skald-beacon.conf;
}

# One-time install links, `curl -fsSL <base>/traffic-kit/<code> | sudo bash`,
# and the AI agent's codes (llms.txt, <code>/steps, keys, install.sh, leads/;
# docs/INGEST.md): to the beacon helper. The code is a secret: never logged,
# in the access log or the error log (whose lines hold the request line; the
# nested location inherits it). The helper sends no-store and noindex itself.
# GET only, but an agent's report: POST, at most 16 KiB.
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

<!-- skald-nginx-sessions:end -->

Then `sudo nginx -t && sudo systemctl reload nginx`: the site shares the
server, so never reload without the test. Check: `/traffic/` without a
cookie answers 302 to `/traffic-auth/login`; the owner's set-your-password
link works; after signing in, `/traffic/<site>/` loads and
`/traffic/sites.json` lists only that organisation's sites.

**Why each part matters** (the 2026-10-11 security review):

- The check sees the raw address and nginx's normalised path. Without the
  strict parse and the second header, `/traffic/_app/%2e%2e/<other site>/`
  passed the check as "shared app code" and nginx served the other
  organisation's files.
- `limit_req` slows a flood before it reaches the helper. The helper also
  counts each try before checking the password (forty tries sent at once
  get one real check) and runs at most two password checks at a time
  (503 with `Retry-After` when busy), so a flood cannot exhaust memory.
- The helper never believes `X-Skald-User` / `X-Skald-Role` in sessions
  mode: it reads the session cookie itself on every route. A local process
  that can reach 127.0.0.1:8765 still needs a real session. It can claim any
  `X-Real-IP`, though (the sign-in limit per address): `refresh.socket`, or
  `access.trust_proxy_ip: false`, closes that.

**Switching back to basic mode:** set `access.mode: basic` (or remove it),
`systemctl restart skald-refresh`, put the basic-mode nginx file
back (keep a copy before the switch) and `nginx -t && systemctl reload
nginx`. The accounts file stays and is used again on the next switch;
`users.json`, `tokens.json` and the htpasswd file were never changed.

## 7. Backups and upgrades

- `history.sqlite` is the only state that cannot be rebuilt from the logs. Back
  it up with
  `sqlite3 /var/lib/skald/history.sqlite ".backup '/path/backup.sqlite'"`.
  It holds aggregates only, no addresses or user agents. With the 2026-10-11
  parts, `accounts.sqlite` and `conversions.sqlite` are state too (`skald
  backup` copies them); `conversions.sqlite` may hold addresses, names and
  emails (2.4.0, above).
- Upgrade the way "Deploying a new version" (section 5) says: back up, then
  ship the committed code with `git archive HEAD` from your checkout. The
  server has no git, so never `git pull` there. The history carries a
  schema version. Newer code upgrades an older file in place the next time
  it opens it: it copies the file to `history.sqlite.schema-v<N>.bak`, then
  adds the missing columns and the new version in one transaction. Nothing
  is dropped or rewritten, and a failed upgrade changes nothing. Code older
  than the file refuses to read it rather than misreading it.
- Schema 7 (the breakdowns) adds `days.breakdowns`; days collected before
  it show no breakdowns until `backfill --days 14 --force` recollects them
  from the logs that still hold them. `run-daily` now runs `audit` (an
  independent recount of yesterday from the raw log) after collect; a
  mismatch withholds the day and stops the dashboard and mail steps.
- Schema 8 (visits) adds `days.journeys` and the `journeys` table (one
  anonymous row per reader's visit, deleted after `report.journey_days`
  days). Days collected before it show no visit figures; `collect --day D`
  or `backfill --force` fills them in while the logs hold them.
- Schema 9 adds `days.extras`, `day_extras` and `visitor_days`. For
  returning visitors generate a key once and keep it only in the env file:
  `python3 -c "import secrets; print(secrets.token_hex(32))"` into
  `/etc/skald/env` as `export SKALD_VISITOR_KEY='...'`, and
  set `report.env_file: /etc/skald/env`. Losing the key only resets
  "returning" to zero for 30 days; changing it does the same.
- Schema 14 (P1-6) adds the `search_days` table: Search Console and Bing
  figures synced from their APIs (docs/DATA-CONTRACT-SEARCH.md). The first
  open copies the file to `history.sqlite.schema-v13.bak`, then adds the
  table; no row changes. Nothing is synced until a site is connected in
  Settings > Integrations > Search (docs/INTEGRATIONS.md, "Search Console and
  Bing"). The Docker scheduler runs `skald search sync` every 6 hours
  (`SKALD_SEARCH_HOURS`, `SKALD_SEARCH_AT`). Without Docker, add a line to
  `/etc/cron.d/skald` (section 5), clear of the daily run:
  `40 5,11,17,23 * * * skald . /etc/skald/env && cd /opt/skald && ./bin/skald --config /etc/skald/config.yml search sync >>/var/log/skald/search.log 2>&1`.
  Its failures mail once by themselves (no `notify-failure`).
- `ours.file` must be writable by the skald user (the refresh helper
  writes it); `ours.change_log` too.
- Settings > Sites > Views, "Fill past days for the new groups": the refresh
  helper starts `skald --site S views refresh` in the background, as its own
  user, so that user must be able to write `history.sqlite`, the dashboard
  folder and the history's folder (`views-fill.json`, `views-fill.lock`,
  `views-fill.log`) and read the raw logs, as the daily run does. Nothing to
  change on a Docker install or on one where the helper and cron run as the
  skald user; no nginx change (the routes are `settings/views-fill`
  and `settings/views-fill-start`, inside the existing `settings(?:/[a-z-]+)?`).
  docs/SETTINGS.md, "Page groups: filling past days".
- `conversions.sqlite` schema 2 (Phase 4b step 3): the stages `won` and
  `lost`, one name per action (`booking` -> `demo`, `checkout` -> `paid`,
  `form` -> `contact`; a Stripe checkout not yet paid becomes `started`, a
  HubSpot deal won `won`), and the outgoing webhooks' tables. The first
  process that opens the file (the hook helper, a live run) copies it to
  `conversions.sqlite.v1.bak` (0640) and then rebuilds the conversions table
  in one transaction; no row is dropped. With `leads.db` set, every lead
  also becomes a conversion (tool `site`) from the next live run on
  (`conversions.from_leads: false` turns it off). The audit keeps the
  beacon's day counts in `conversions-audit.json` beside the history.
- A column added by an upgrade is empty (NULL, "not recorded") for days
  collected before it existed - never a made-up zero. The dashboard says
  when that applies; `backfill --days 14 --force` re-collects whatever the
  logs still hold.
- Release 2 (2026-10-07) changes no table: its per-day figures are new
  kinds in `day_extras` (`bots`, `quality`, and `audit`, written by the
  audit). Days collected before it show them as null. The counting rules
  changed (COUNTING-TRAPS.md 6-12); `backfill --days 14 --force` recounts
  what the logs still hold and leaves a marker. New config sections:
  `site.legacy_paths`, `bots`, `requests`, `alerts`, `markers`, `leads`,
  `backup` (config.example.yml documents each).
- Backups: `skald backup` (nightly, above), `skald backup --verify` tests the
  newest copy again, `skald backup --pull` prints the scp command that
  fetches the newest copy to another machine. Off-server copies are your
  choice: another server by a nightly rsync, object storage (Backblaze B2
  or S3) with the copy encrypted first (`age` or `gpg`), or a workstation
  pulling nightly with a scheduled job running that scp. The history copies hold the 30-day keyed hashes; the key stays
  in the env file, which is never copied. The conversions copies hold the kept visits with
  their addresses, and leads' names and emails, while a site keeps them: encrypt them too.
