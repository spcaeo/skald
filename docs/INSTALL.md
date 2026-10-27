# Installing Skald

Four ways, from quickest to most hands-on. All of them run the same code and
keep the same files: the history (`history.sqlite`), the accounts and the
settings live in one data folder, and everything else can be rebuilt.

To look around first, the [live demo](https://spcaeo.github.io/skald/) is the whole dashboard with
sample data (`tools/demo.py` builds it).

| Way | Best for | Web server |
| --- | --- | --- |
| [1. Docker](#1-docker) | trying it, or one container on any host | its own nginx, on port 8080 |
| [2. Docker Compose](#2-docker-compose) | a server that already runs Docker | next to yours, or Caddy with HTTPS |
| [3. Install script](#3-install-script) | an Ubuntu or Debian web server | yours (nginx, Caddy, Apache) |
| [4. Manual](#4-manual) | full control, other systems | yours |

## What you need

- **A web server's access log**, readable by Skald: nginx or Apache
  (combined format, or the extended one in SOP.md section 3), Caddy JSON, or a
  CDN's log (Cloudflare, CloudFront, Fastly: [CDN-LOGS.md](CDN-LOGS.md)).
  `logs.format: auto` finds which. A site on another server can send its log
  with skald-ship ([INGEST.md](INGEST.md)).
- **Python 3.11 or newer** for ways 3 and 4 (the Docker image has its own).
  The standard library is enough; PyYAML is used when it is there, and
  Pillow, when it is there, turns fetched site icons into small PNGs.
- **HTTPS in front of the dashboard** for signing in. The session cookie is
  `Secure`, so a browser keeps it only over HTTPS, or at `http://localhost`.
- Optional: an SMTP account for the daily and weekly mails. Without it,
  everything works and no mail is sent.

---

## 1. Docker

One container runs everything: nginx on port 8080 (the dashboard and every
Skald route), the two helpers behind it, and a small scheduler (the live
snapshot every 2 minutes, the daily run, the nightly backup). Mount the log
read-only at `/logs`; the data lives in a volume.

```sh
docker run -d --name skald --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v /var/log/nginx:/logs:ro \
  -v skald-data:/var/lib/skald \
  -e SKALD_SITE=example.com \
  -e SKALD_TIMEZONE=America/New_York \
  -e SKALD_BASE_URL=https://stats.example.com \
  ghcr.io/spcaeo/skald:latest
```

`127.0.0.1:` publishes the port on this machine only, the safe default:
reach it from elsewhere through HTTPS in front (recipe A or B below). Leave
it out only when something else already guards the port.

Behind a web server on the same machine (recipe A below), also give
`-e SKALD_TRUSTED_PROXIES=private -e SKALD_REAL_IP_HEADER=X-Real-IP`, so the
sign-in limits and the in-page events see each visitor's address, not the
proxy's (Compose sets both). On a hosting platform, [HOSTING.md](HOSTING.md)
gives the values.

Then make the first owner. It prints a "set your password" link (valid 60
minutes):

```sh
docker exec -it skald skald accounts init \
  --org "Example Co" --owner-email owner@example.com
```

Open `http://localhost:8080/` on the same machine, or the HTTPS address
(see "Put it on the web" below). The dashboard fills within two minutes from
today's log; `docker exec skald skald backfill --days 14` adds the
days the log's rotations still hold.

Then check it: `docker exec skald skald doctor` says, one line per
part, what works and what to fix (below, "Check it").

`skald <command>` in the container runs Skald's command with the
container's config: `check`, `live`, `backup`, `doctor`, `accounts status`,
`user`, `export` and the rest. The step-by-step guide for a first install is
the Help page "Docker: first install in 10 minutes"
(docs/help/docker-first-install.md).

### Settings

Set them as `-e NAME=value` (or in Compose's `.env`). The container writes
its config from them at every start. For anything more, mount your own
config (`config.example.yml` documents every key) at
`/etc/skald/config.yml`; it then wins over these. Keep its paths as
the container has them (`history.db: /var/lib/skald/history.sqlite`,
`dashboard.out: /var/www/skald`, `logs.dir: /logs`).

| Variable | Default | What |
| --- | --- | --- |
| `SKALD_SITE` | `site` | the site's name (a host name, e.g. `example.com`); the dashboard is at `/traffic/<name>/` |
| `SKALD_HOSTS` | (all) | host names the report is about, space or comma separated; empty counts every host in the log |
| `SKALD_TIMEZONE` | `UTC` | the zone a day is cut in |
| `SKALD_BASE_URL` | `http://localhost:8080` | the public address: links in mails, allowed origin |
| `SKALD_LOG_DIR` | `/logs` | the folder the log is read from; with `SKALD_INGEST`, `/var/lib/skald/ingest/<SKALD_SITE>` |
| `SKALD_LOG_FILE` | `access.log` | the log's file name in `/logs` (rotations `.1`, `.2.gz`... are found) |
| `SKALD_LOG_FORMAT` | `auto` | or `nginx_combined`, `nginx_extended`, `caddy_json`, ... |
| `SKALD_ASSET_PREFIXES` | | extra path prefixes that are files, not pages (e.g. `/_next/static/`) |
| `SKALD_COUNTRY_DB` | | a GeoIP `.mmdb` file inside the container (e.g. `/geoip/dbip-country-lite.mmdb`, with `-v /usr/share/GeoIP:/geoip:ro`): a log line with no country of its own (Caddy, a plain combined log) gets its address's country from it, and so does a lead hook's `ip`. DB-IP's free country file works; its credit is shown under the countries. Unset: such lines say Not recorded |
| `SKALD_CITY_DB` | | a GeoIP city `.mmdb` file inside the container (e.g. `/geoip/dbip-city-lite.mmdb`, same mount): DB-IP's free "IP to City Lite" (CC BY 4.0, monthly, about 120 MB; `tools/update-dbip-city.sh` downloads it). Each visit gets its city ("Toronto, Ontario, Canada"), Places & devices gets a Cities table and the real-time map a dot per active city. People only, never bots; a city whose country is not the line's own is not used. Its credit is shown with the countries. Unset: no city is recorded |
| `SKALD_EMAIL` | | who gets the mails (also the sender unless `SKALD_MAIL_FROM`) |
| `SKALD_SMTP_HOST`, `SKALD_SMTP_PORT`, `SKALD_SMTP_SECURITY` | `587`, `starttls` | the mail server; mails stay off without a host (or set it in Settings > Mail) |
| `SMTP_USER`, `SMTP_PASSWORD` | | the SMTP login: environment only, never in a file you commit |
| `SKALD_PUBLIC_CHECK`, `SKALD_PUBLIC_CHECK_ORIGINS`, `SKALD_PUBLIC_CHECK_INFO_URL` | off | `true` switches on the public "Is my site exposed?" check (`POST /traffic-hooks/_public/stack-check`), answered with CORS for the listed origin(s) only; the info URL goes in its User-Agent ([SETTINGS.md](SETTINGS.md), "Public check") |
| `SKALD_BEACON_ORIGINS` | | your site's origin(s), to switch on the script tag and in-page events ([BEACON.md](BEACON.md)). Not needed for webhooks (Calendly, Stripe, the `lead` hook): those work without it since 2.2.2 |
| `SKALD_INGEST` | | `true` takes logs from other servers and log drains ([INGEST.md](INGEST.md)); set `SKALD_LOG_DIR` with it |
| `SKALD_MCP` | off | `true` switches on MCP for AI agents at `POST /traffic-mcp` (`mcp.enabled`; since 2.26). Each agent needs a token with the `mcp` scope: Settings > Connections > Connect an AI assistant, or `docker exec skald skald token create NAME --scope mcp --site example.com` ([MCP.md](MCP.md)). Unset, the path answers 404 |
| `SKALD_VERIFY_BOTS` | on | crawler address checks: the generated config sets `bots.ranges_dir` to `/var/lib/skald/ranges` (made at start), and the daily run fetches the crawler owners' address lists and the hosting networks there first (about 37 requests and 8 MB downloaded, 1.3 MB kept, under a minute; once per 12 hours for all sites). A fake Googlebot or GPTBot is then filed under bots as "claims to be ...", and browsers from hosting networks are flagged. Needs outbound HTTPS and DNS; a failed fetch keeps the last good lists and never stops counting. `off` switches it off (doctor then says OFF). Before this release a Docker install never checked crawlers |
| `SKALD_KIT_IMAGE`, `SKALD_KIT_SHIP_PATH` | this image at its major version; the shipper's path inside it | the image and shipper path a site's shipper runs with Docker: the one command and one file, and the Docker zip kit (Settings > Connections; `ingest.kit_image` in a config wins) |
| `SKALD_KEEP_IPS` | on (new install), off (upgraded from before 2.4.0) | `1` keeps each visit's IP address and browser with its pages for `privacy.keep_days` (395 days), so a person can be looked up; `short` keeps each address with its last part removed (203.0.113.57 as 203.0.113.0; since 2.15.0); `0` keeps none (only the last 6 hours of requests show addresses). Also Settings > Data retention > People. Your privacy notice must say so |
| `SKALD_IDENTITY` | `full` (new install), `anonymous` (upgraded from before 2.4.0) | `full` keeps leads' names and emails with their conversions; `anonymous` keeps neither |
| `SKALD_KEEP_EVERYTHING` | off | `1` (or `true`): keep everything, for an internal or enterprise install. Skald then deletes and clears nothing by itself on any site of the install: no retention window, People days or plan cap removes a row, a file line or a conversions backup (`retention.keep_everything` in [SETTINGS.md](SETTINGS.md#keep-everything)). A person's own deletion request, run by an admin (`forget`, `conversions forget`), still works. The privacy notice wording then says "until you ask us to delete it" |
| `SKALD_DAILY_AT`, `SKALD_BACKUP_AT` | `07:15`, `03:30` | the daily run and the backup, in the site's time zone |
| `SKALD_LIVE_MINUTES` | `2` | the live snapshot's interval |
| `SKALD_JOB_NICE` | `10` | how much lower the scheduled jobs (live, daily, backup...) run than nginx and the helper, 0 to 19; `0` turns it off |
| `SKALD_SEARCH_HOURS`, `SKALD_SEARCH_AT` | `6`, `01:40` | the Search Console and Bing sync: every N hours from that time (0 turns it off; [INTEGRATIONS-SEARCH.md](INTEGRATIONS-SEARCH.md#search-console-and-bing)) |
| `SKALD_TOOLS_HOURS`, `SKALD_TOOLS_AT` | `6`, `02:10` | the sync of the figures from each site's own tools (Google Analytics...): every N hours from that time, at a lower priority than the other jobs (0 turns it off; [TOOLS.md](TOOLS.md)) |
| `SKALD_GSC_KEY_JSON`, `SKALD_GSC_KEY_FILE` | | the Google service-account key for the Search Console sync: the key file's text, or a path to it inside the container (make it 0600). Not needed when the key is uploaded in Settings > Integrations > Search, which keeps it in `secrets.json` beside the history. Environment only, never in a file you commit |
| `SKALD_REPORTS_MINUTES` | `15` | how often the client reports that are due are sent (Settings > Reports); `0` stops them |
| `SKALD_AI_ANSWERS_MINUTES` | `15` | how often the AI answers profiles that are due (or asked to run now) are asked (`ai-answers --due`); `0` stops them |
| `SKALD_SUMMARY_AT` | `01:00` | the daily summary mail (`summary-mail`): one mail per person with what to look at on every site they get security alerts for (security items, to-dos, set-up problems), in the schedule's time zone; `off` stops it |
| `SKALD_SCHEDULER` | `on` | `off` stops the container's own schedule (every job below) |
| `SKALD_SCHEDULE_TZ` | the site's `report.timezone` | the zone the daily times above are in (`SKALD_DAILY_AT`, `SKALD_BACKUP_AT`, `SKALD_SEARCH_AT`, `SKALD_TOOLS_AT`, `SKALD_SUMMARY_AT`); an unknown zone stops the scheduler at start |
| `SKALD_MAIL_FROM` | the first `SKALD_EMAIL` | the sender of every mail |
| `SKALD_CONFIG` | | a config file inside the container to use as it is, instead of a mounted `/etc/skald/config.yml` or the one generated from these variables |
| `SKALD_ORIGIN` | from `SKALD_BASE_URL` | the browser origin(s) the dashboard's buttons are accepted from |
| `SKALD_TRUSTED_PROXIES` | none (Compose: `private`) | the proxy in front, whose word on the visitor's address is believed: ranges such as `10.0.0.0/8`, or `private` (the private ranges). Empty: nobody, right when the container faces the internet. Per platform: [HOSTING.md](HOSTING.md) |
| `SKALD_REAL_IP_HEADER` | `X-Forwarded-For` (Compose: `X-Real-IP`) | the header that proxy puts the visitor's address in; `Fly-Client-IP` on Fly.io |
| `SKALD_PORT` | `8080` | the port inside the container |

The image sets a few more for itself; leave them: `SKALD_APP` (the code,
`/opt/skald`), `SKALD_DATA` (the volume, `/var/lib/skald`), `SKALD_JOB_LOGS`
(each job's log, `/var/log/skald`), and the build's `SKALD_RELEASE` and
`SKALD_COMMIT` (what `skald version` prints).

The container's schedule (`docker/scheduler.py`, cron's lines without a cron daemon; one line
per run in `docker logs skald`, each job's output in `/var/log/skald/<job>.log`): `live`
every `SKALD_LIVE_MINUTES` and once at start; `run-daily` at `SKALD_DAILY_AT` (one
`notify-failure` mail when it fails, at most one per 12 hours); `backup` at `SKALD_BACKUP_AT`;
`reports --due` every `SKALD_REPORTS_MINUTES`; the beacon log's rotation at 00:05; `search sync`
every `SKALD_SEARCH_HOURS` from `SKALD_SEARCH_AT`; `tools sync` every `SKALD_TOOLS_HOURS` from
`SKALD_TOOLS_AT`, at a lower priority still; `ai-answers --due` every
`SKALD_AI_ANSWERS_MINUTES`; and `summary-mail` at `SKALD_SUMMARY_AT`. A job still running when
it is next due is not started twice; a time missed while the container was down is not caught up.

The returning-visitor key is made once, on the first start, into
`/var/lib/skald/env` (0600, in the volume). Keep the volume.

### Why one container

nginx, the two helpers and the scheduler share one data folder and talk over
127.0.0.1, which the helpers insist on. One small supervisor
(`docker/entrypoint.py`, standard library) starts the four, restarts any that
stops and is the health check: the sign-in page must answer through nginx and
the helper, and the scheduler must have ticked in the last 5 minutes. The
nginx config is DEPLOY.md's sessions-mode config, generated from it
(`docker/build-nginx-conf.py`) and checked by the same route tests.

### Upgrade, uninstall

Pin `:2` instead of `:latest` to get every 2.x release and never a breaking one; automatic
updates (a cron line, Watchtower): [UPGRADING.md](UPGRADING.md#docker).

```sh
docker pull ghcr.io/spcaeo/skald:latest
docker rm -f skald
docker run -d --name skald ...           # the same command as before; the volume keeps the data
```

Uninstall: `docker rm -f skald`. The data stays in the volume until
`docker volume rm skald-data`. Copy the backups out first if you want them:
`docker cp skald:/var/lib/skald/backups ./skald-backups`.

---

## 2. Docker Compose

`docker-compose.yml` at the top of the repository runs the same image.

```sh
git clone https://github.com/spcaeo/skald && cd skald
cat > .env <<'EOF'
SKALD_SITE=example.com
SKALD_HOSTS=example.com www.example.com
SKALD_TIMEZONE=America/New_York
SKALD_BASE_URL=https://www.example.com
SKALD_LOGS=/var/log/nginx
EOF
docker compose up -d
docker compose exec skald skald accounts init \
  --org "Example Co" --owner-email owner@example.com
```

`.env` is not committed (it is in `.gitignore`); SMTP_USER and SMTP_PASSWORD
go there too. `docker compose run --rm skald accounts init ...` works as well
when the service is not running.

### Recipe A: next to the web server you already run

By default Skald listens on `127.0.0.1:8080` only (`SKALD_HOST_PORT` changes the port;
`SKALD_BIND=0.0.0.0` opens it to the network: then put HTTPS in front, or, with nothing
in front, set `SKALD_TRUSTED_PROXIES=none`). Your web server keeps
serving the site and sends Skald's paths to it: `/traffic/` (the dashboard)
and `/traffic-auth/`, `/traffic-api/`, `/traffic-ingest/`, `/traffic-mcp`,
`/traffic-hooks/`, `/traffic-beacon`, `/traffic-js/`. It needs no other change.

nginx, inside the site's HTTPS `server { }` block:

```nginx
location ~ ^/traffic(?:$|/|-(?:auth|api|ingest|mcp|hooks|beacon|js)(?:/|$)) {
    access_log off;                       # your own dashboard views are not visitors
    client_max_body_size 6m;              # shipped log batches (INGEST.md)
    proxy_read_timeout 60s;
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

then `sudo nginx -t && sudo systemctl reload nginx`. Skald compresses the
dashboard's files and says how long a browser may keep each (2.41,
[DEPLOY.md](../DEPLOY.md#compression-and-caching-241)); this block passes both
through as they are. Do not add a `Cache-Control` of your own for these paths.
It passes every method as sent: the signed `GET /traffic-hooks/<site>/leads` (2.18, a site's server
checking that Skald has every lead) needs GET as well as POST. If your own
block for `/traffic-hooks/` has `limit_except POST { deny all; }`, make it
`limit_except GET POST { deny all; }`.

Caddy, inside the site's block:

```caddy
@skald path_regexp ^/traffic($|/|-(auth|api|ingest|mcp|hooks|beacon|js)(/|$))
log_skip @skald
handle @skald {
    reverse_proxy 127.0.0.1:8080 {
        header_up X-Real-IP {remote_host}
    }
}
```

Set `SKALD_BASE_URL` to that site's address (`https://www.example.com`). The
nginx inside the container does the rest: the session check on every
dashboard file, the sign-in limits, the security headers.

### Recipe B: all in one, with HTTPS

For a stats address of its own (`stats.example.com`, its DNS pointing at
this server, ports 80 and 443 free):

```sh
cat >> .env <<'EOF'
SKALD_DOMAIN=stats.example.com
SKALD_BASE_URL=https://stats.example.com
EOF
docker compose --profile https up -d
```

This adds Caddy (`docker/Caddyfile`), which gets and renews the certificate
itself and sends everything to Skald. The site's own log still comes from
`SKALD_LOGS` (the web server on this host) or from skald-ship on the site's
server ([INGEST.md](INGEST.md), `SKALD_INGEST=true`).

### Upgrade, uninstall

```sh
docker compose pull && docker compose up -d                 # the published image
git pull && docker compose up -d --build                    # or build from the checkout
docker compose down                                         # stop; the data volume stays
docker compose down -v                                      # stop and delete the data
```

---

## 3. Install script

For Ubuntu 22.04, 24.04, 26.04 and Debian 12 or 13, on the web server itself. It
installs Python 3.11+ (on 22.04 the `python3.11` package) and PyYAML, makes
the `skald` user (in group `adm`, to read the log), puts the code in
`/opt/skald`, writes `/etc/skald/config.yml` from
`config.example.yml`, makes the env file with the visitor key, installs the
systemd units and `/etc/cron.d/skald`, puts the `skald`
command in `/usr/local/bin`, runs a first `check` and `live`, and prints the
lines to add to nginx or Caddy.

The quick way, pinned to a release (`--ref` picks the code it downloads):

```sh
curl -fsSL https://raw.githubusercontent.com/spcaeo/skald/v2.7.0/install.sh | sudo bash -s -- --ref v2.7.0
```

This runs a script from the internet as root. To check what you run first,
take the release's tarball and verify it against the `SHA256SUMS` file that
the release workflow attaches to every release (it lists the tarball and
`install.sh`):

```sh
curl -fsSLO https://github.com/spcaeo/skald/releases/download/v2.7.0/skald-2.7.0.tar.gz
curl -fsSLO https://github.com/spcaeo/skald/releases/download/v2.7.0/SHA256SUMS
sha256sum --ignore-missing -c SHA256SUMS      # must print: skald-2.7.0.tar.gz: OK
tar -xzf skald-2.7.0.tar.gz && cd skald-2.7.0
less install.sh                               # read it
sudo ./install.sh                             # installs from this folder, downloads nothing
```

or from a checkout:

```sh
git clone https://github.com/spcaeo/skald && cd skald && sudo ./install.sh
```

It asks for the site, the log, the time zone and the mail address. Without
questions:

```sh
sudo ./install.sh --site example.com --log /var/log/nginx/access.log \
  --timezone America/New_York --email owner@example.com --non-interactive
```

`./install.sh --help` lists every option (`--hosts`, `--format`, `--origin`,
`--daily-at`, `--source`, `--ref`, `--no-first-run`).

After it:

1. Add the printed `/traffic/` location to the site's nginx (or Caddy)
   block, with an htpasswd file, then `sudo nginx -t && sudo systemctl
   reload nginx`. For accounts (each person signs in with their own email)
   use DEPLOY.md's "Sessions mode" blocks and `accounts init` instead.
2. Mail: fill in the `mail:` section of `/etc/skald/config.yml`, the
   SMTP login in `/etc/skald/env`, and set `mail.daily` and
   `mail.weekly` to `true` (the script leaves them off).
3. `sudo skald backfill --days 14` for the days the logs hold.
4. `sudo skald doctor` (below, "Check it").

The `skald` command runs as the `skald` user with
`/etc/skald/config.yml` and the env file, so call it with `sudo`:
`sudo skald check`, `live`, `run-daily`, `version`, `--help`.

### Upgrade, uninstall

`sudo skald upgrade` installs a newer release with a backup, health checks and a
rollback; update notices and automatic upgrades too: [UPGRADING.md](UPGRADING.md).
Running the script again also works: it replaces the code (the previous copy goes to
`/opt/skald.prev`), reinstalls the units and cron, restarts the
helper, and keeps the config, the env file and the history.

```sh
sudo ./install.sh --uninstall           # units, cron, logrotate, the command go; code, config, data stay
sudo ./install.sh --uninstall --purge   # also /opt, /etc, /var/lib, /var/www and the user
```

Roll back an upgrade: `sudo rsync -a --delete /opt/skald.prev/
/opt/skald/` and `sudo systemctl restart skald-refresh`.

---

## 4. Manual

[DEPLOY.md](../DEPLOY.md) is every step by hand: the paths and owners, the
env file, the first run, the cron lines, the systemd units, nginx in basic
or sessions mode, and upgrading by `git archive`. Use it on another Linux, or
when you want to know exactly what the script does.

Upgrade: DEPLOY.md, "Deploying a new version". Uninstall: stop and remove
the units in `/etc/systemd/system/`, delete `/etc/cron.d/skald`,
then the folders in DEPLOY.md section 2 if the data should go too.

---

## Try a log first: `try-log`

Can Skald read this log, and what would it count? Ask before the next daily run:

```sh
docker exec skald skald try-log /logs/access.log                 # Docker
docker exec skald skald try-log /var/lib/skald/ingest/example.com/access.log --site example.com
sudo skald try-log /var/log/nginx/access.log.2.gz --site example.com  # install.sh
python3 bin/skald try-log export.json --format cloudflare_json   # from the code, no config needed
```

It reads the file's first 500 lines (`--lines N`; plain or gzip) and stores nothing. With
`--format auto` (the default) it tries every reader and keeps the one that reads the most
lines, and says how sure it is. It prints: the lines read and not read, with the main
reasons and up to 3 line numbers each (never a raw line); the first and last time and the
time zone in the lines; the hosts, and whether they are the site's; Skald's five groups for
the sample, which add up to the lines read; the pages people viewed most; and warnings, such
as no referrer (every source would be Direct), no user agent, no host name, an error log
instead of an access log, or page assets that do not match the site's settings. `--site`
judges the lines with that site's settings (hosts, own traffic, page assets, time zone);
`--json` prints the report as JSON. Exit 0: Skald can read it; 1: nothing can be read, or a
daily run would withhold the day; 2: the file cannot be opened.

In the dashboard, **Settings > Connections > Test a sample** does the same on up to 200
pasted lines (owners and admins).

---

## Check it: `doctor`

```sh
sudo skald doctor                    # a server set up with install.sh
docker exec skald skald doctor       # Docker
```

One line per part, `OK`, `NEEDS ATTENTION` (with the fix in plain words) or
`OFF` (not in use), and exit 1 when something needs attention, so a cron or
a monitor can run it:

| Part | What it checks |
| --- | --- |
| Daily run | `run-daily` ran in the last 26 hours and did not fail or stop on a day that does not reconcile (`runs.json`) |
| Days stored | the last 14 days, from the first day stored: none missing, none withheld; else the `backfill --days N` that collects them again |
| Access log | `logs.dir`/`logs.base` there, readable by Skald's user, written in the last day |
| Page assets | a request for `site.asset_prefixes` (default `/_next/static/`; Docker `SKALD_ASSET_PREFIXES`) in the log's last lines: without one, no browser counts as a person |
| Web app | `dashboard.app` on |
| Hook receiver | the beacon helper answers on 127.0.0.1:8766 |
| Hook (each tool) | its secret, and needs a secret / never received / ready / last received N ago, or why the last delivery was refused |
| One lead, two tools | an external ref that arrived from two tools: it counts once per tool |
| Script tag | `beacon.origins`, the helper serving the file, the last event from a page |
| Lead database | `leads.db` readable (when set) |
| Mail | the settings are complete; nothing is sent unless `--send-test` |
| Version | a newer release, read from `updates.json` (the daily run asks GitHub; the doctor never does) |
| Disk | free space where the history lives |

`--json` prints the same list (one object per site); Settings > Integrations
shows the integration lines under **Status**. Every check only reads.

---

## Troubleshooting

| What you see | Why, and what to do |
| --- | --- |
| `nothing parsed` from `check` | Wrong file or format, or no permission. Docker: `docker exec skald ls -l /logs` (the container's user is in group `adm`, gid 4, which reads `/var/log/nginx` on Ubuntu and Debian). Script: `sudo -u skald head -1 /var/log/nginx/access.log`. Then `check --day today`. `try-log <the file>` (above) says which reader fits and why the lines fail. |
| The sign-in page loops back to itself | The browser dropped the `Secure` cookie: use HTTPS (recipe A or B), or `http://localhost:8080` on the same machine. |
| Links in mails say `localhost` | Set `SKALD_BASE_URL` (Docker) or `access.base_url` (config) to the public address. |
| The first daily run "failed" | There is no whole day in the history yet. It sorts itself out the next day, or run `backfill --days 14`. |
| 404 on `/traffic-beacon` or `/traffic-js/` | The script tag is off: set `SKALD_BEACON_ORIGINS` (Docker) or `beacon.origins`. |
| 502 on `/traffic-hooks/…`, `/traffic-beacon` or `/traffic-js/` | Skald before 2.2.2, where the webhook receiver ran only with the script tag on. Upgrade (UPGRADING.md). |
| The dashboard shows a plain page with no menu | Skald before 2.2.1 (Docker) or 2.2.2 (install script). Upgrade; or add `app: true` under `dashboard:` in config.yml. |
| `permission denied` on a bind-mounted folder | The container runs as uid 10001. Started as root (the default) it gives `/var/lib/skald` to that user itself; for other folders, or with `--user`, `sudo chown -R 10001:10001 <folder>`, or use the named volume. |
| Container `unhealthy` | `docker logs skald` and `docker inspect --format '{{json .State.Health}}' skald`. |
| "Too many tries" on sign-in for everyone at once | The proxy in front is not trusted, so every visitor looks like it: set `SKALD_TRUSTED_PROXIES` to its range (the image's `peers` command shows it while you load the dashboard: `docker exec skald python3 /opt/skald/docker/entrypoint.py peers`) and `SKALD_REAL_IP_HEADER` to the header it sends. |
| Mails do not go | `skald mail --daily --dry-run` shows the mail; Settings > Mail sends a test. Without an SMTP host the mails are off on purpose. |
| Ubuntu 22.04's Python 3.11 says `3.11.0rc1` | That is the package Ubuntu ships; it runs Skald. |

Logs: Docker, `docker logs skald` (one line per job) and
`/var/log/skald/*.log` in the container; the script,
`/var/log/skald/` and `journalctl -u skald-refresh`.
