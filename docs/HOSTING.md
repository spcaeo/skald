# Hosting Skald

Two questions, answered apart:

- **A. Where Skald runs.** Skald is a long-running program with a disk. It keeps its history
  in SQLite, runs its own schedule (the live panel every 2 minutes, the daily run, the backup)
  and serves the dashboard. It needs one machine or one container that stays up, and a
  persistent disk. **It cannot run on Vercel, Netlify or Cloudflare Workers functions**: they
  stop between requests and keep no disk.
- **B. Where your site runs.** That can be anywhere. Skald needs to see the site's requests:
  from a web server's access log, a CDN's log, or a host's log drain. The part B table says
  which one fits your host, and what you lose when there is no log at all.

You can mix them: Skald on a small VPS or on Fly.io, measuring a site on Vercel.

## What every option needs

| | |
| --- | --- |
| Image | `ghcr.io/spcaeo/skald:latest` (or build `docker/Dockerfile` from this repository) |
| Port | `8080` (nginx inside the container; the dashboard is at `/traffic/`) |
| Disk | a persistent volume at `/var/lib/skald`: history, accounts, settings, backups, shipped logs. Lose it and you lose everything. |
| Instances | **exactly one.** SQLite on one disk; never scale out, never run two copies on one volume |
| HTTPS | required for sign-in (the session cookie is `Secure`). Every platform below gives you HTTPS; on your own server use the bundled Caddy or your web server |
| Health check | `GET /traffic-auth/login` answers 200 |
| Settings | `SKALD_SITE` (your site's host name), `SKALD_HOSTS` (the host names to count), `SKALD_BASE_URL` (Skald's own `https://` address), `SKALD_TIMEZONE`, `SKALD_EMAIL` and `SMTP_*` for mail. [INSTALL.md](INSTALL.md) lists them all |
| First owner | `skald accounts init --org "Example Co" --owner-email owner@example.com` inside the container. It prints a link to set the password |

**When Skald has no log on its own disk** (every platform below except your own server), the
site's lines arrive by POST: from the shipper on your web server, or from a host's log drain.
Turn that on with two more settings:

```sh
SKALD_INGEST=true
SKALD_LOG_DIR=/var/lib/skald/ingest/example.com     # /var/lib/skald/ingest/<SKALD_SITE>
```

Then make an ingest token for the site, in the dashboard (**Settings > Add or remove sites >
New token**) or inside the container:

```sh
skald token create my-drain --scope ingest --site example.com
```

The token is shown once. Part B says where it goes.

**Disk ownership.** Skald runs as user 10001, not root. Some platforms (Railway, Fly.io,
Render) mount a new disk owned by root, so the container starts as root only long enough to give
`/var/lib/skald` to user 10001, then drops to that user before it runs anything. Docker's named
volumes and Kubernetes (with `fsGroup` and `runAsUser: 10001`) need no handing over; the
container then starts as 10001 and changes nothing.

**The visitor's address.** Every platform below puts a proxy in front of Skald, so the
connection comes from the proxy, not the visitor. Until you tell Skald which proxy to believe,
every visitor has the proxy's address: one sign-in limit for everyone, and the in-page events
and returning visitors run together. Two settings fix it:

```sh
SKALD_TRUSTED_PROXIES=10.0.0.0/8          # the proxy's own range(s), comma separated, or `private`
SKALD_REAL_IP_HEADER=X-Forwarded-For      # the header it puts the visitor's address in (the default)
```

nginx in the container then takes the visitor's address from that header, but only on a
connection from those ranges, and walks the header from the right past every trusted hop, so
an address a visitor writes into the header themselves is never taken. Empty (the default)
believes nobody: right when the container faces the internet directly.

| Platform | What its proxy sends | `SKALD_TRUSTED_PROXIES` | `SKALD_REAL_IP_HEADER` |
| --- | --- | --- | --- |
| Docker Compose (recipes A and B) | your web server or the bundled Caddy sends `X-Real-IP` | `private` (set in `docker-compose.yml`) | `X-Real-IP` (set there too) |
| Fly.io | `Fly-Client-IP`, the visitor's address as Fly's proxy saw it ([request headers](https://fly.io/docs/networking/request-headers/)) | `private` (set in `deploy/fly.toml`) | `Fly-Client-IP` |
| Kubernetes, ingress-nginx | `X-Forwarded-For`, filled from what it sees unless `use-forwarded-headers` is on ([ConfigMap](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/configmap/)) | your cluster's pod range (`kubectl get nodes -o jsonpath='{.items[*].spec.podCIDR}'`); `deploy/kubernetes.yaml` has `10.0.0.0/8` | `X-Forwarded-For` |
| Railway | `X-Forwarded-For` and `X-Real-IP`; Railway's docs say neither which nor from where | **not published**: find it with `peers` (below) | `X-Forwarded-For` |
| Render | `X-Forwarded-For`, appended to (Render's docs say nothing) | **not published**: find it with `peers` (below) | `X-Forwarded-For` |

Fly.io's docs name the header but not the address its proxy connects from; `private` covers its
private networks (`172.16.0.0/12` and `fdaa::/16`, inside `fc00::/7`). Other apps in your own Fly
organisation can reach the Machine from those networks too, and could claim an address.

**When a platform does not publish its ranges (Railway, Render), find them yourself:**

1. Leave `SKALD_TRUSTED_PROXIES` empty. Open the dashboard, and while it loads, run in the
   service's shell: `python3 /opt/skald/docker/entrypoint.py peers`. It prints the addresses
   connected to port 8080: the platform's proxy, not you.
2. Set `SKALD_TRUSTED_PROXIES` to the smallest private range that holds them (for example
   `10.0.0.0/8` for `10.x.x.x`, `100.64.0.0/10` for `100.64.x.x` to `100.127.x.x`), and redeploy.
3. Check: on the **Our own traffic** page, **Internal addresses > Add my current address** must show *your* public
   address (the one a "what is my IP" page shows). Remove the entry after. If it shows another
   public address on every try (a CDN in front of the platform's proxy, as some Railway and Render
   users report), the platform puts that hop in the header too: leave `SKALD_TRUSTED_PROXIES`
   empty again and ask the platform's support which header holds the visitor's address.

Never trust `0.0.0.0/0` (Skald refuses it): every visitor could then claim any address. And a
range the platform does not own is not safe just because `peers` showed it once: proxies move.
Check again after the platform announces network changes.

**Free tiers.** Most platforms have a free or trial tier, and most of those have **no
persistent disk** or stop the app when idle. Skald on such a tier loses its history on every
restart and misses its schedule. Check the platform's own pricing page before you choose; this
guide makes no claims about prices.

---

## A. Where Skald runs

| Option | Persistence | Best for |
| --- | --- | --- |
| [Docker on a VPS](#docker-on-a-vps-digitalocean-hetzner-lightsail-any-ubuntu) | a Docker volume | most people; also reads the server's own log |
| [Plain Ubuntu with install.sh](#a-plain-ubuntu-or-debian-server-installsh) | `/var/lib/skald` | a server you already run nginx on |
| [Railway](#railway) | a Railway volume | no server to manage |
| [Render](#render) | a Render disk | no server to manage; one-click Blueprint |
| [Fly.io](#flyio) | a Fly volume | no server to manage; close to your visitors |
| [Coolify, CapRover, Dokku](#coolify-caprover-dokku) | the platform's persistent storage | your own PaaS on your own server |
| [Kubernetes](#kubernetes-optional) | a PersistentVolumeClaim | teams that already run a cluster |

### Docker on a VPS (DigitalOcean, Hetzner, Lightsail, any Ubuntu)

Any small Linux server works: a DigitalOcean Droplet, a Hetzner Cloud server, an AWS Lightsail
instance, or your own. One vCPU and 1 GB of memory is enough for most sites.

1. **Create the server** with Ubuntu 24.04 (or Debian 12). Open ports 22, 80 and 443 in its
   firewall.
2. **Point a name at it.** At your DNS provider, add an `A` record (and `AAAA` for IPv6):
   `stats.example.com` → the server's address. Wait until `dig +short stats.example.com`
   shows it.
3. **Install Docker** with Docker's own instructions:
   <https://docs.docker.com/engine/install/ubuntu/>.
4. **Start Skald with automatic HTTPS:**

   ```sh
   git clone https://github.com/spcaeo/skald && cd skald
   cat > .env <<'ENV'
   SKALD_SITE=example.com
   SKALD_HOSTS=example.com www.example.com
   SKALD_BASE_URL=https://stats.example.com
   SKALD_DOMAIN=stats.example.com
   SKALD_TIMEZONE=America/New_York
   ENV
   docker compose --profile https up -d
   docker compose exec skald skald accounts init --org "Example Co" --owner-email owner@example.com
   ```

   The bundled Caddy gets the certificate for `SKALD_DOMAIN` by itself.
5. **Open the link** the last command printed, set a password, sign in at
   `https://stats.example.com/traffic/`.

**If the site runs on this same server**, Skald reads its log directly: `docker-compose.yml`
mounts `/var/log/nginx` read-only (change `SKALD_LOGS` for another folder). Nothing else to do.

**If the site runs elsewhere**, add `SKALD_INGEST: "true"` and
`SKALD_LOG_DIR: /var/lib/skald/ingest/example.com` under `environment:` in
`docker-compose.yml`, run `docker compose up -d` again, and follow part B for your host.

**Backups.** Skald backs up its own history into the volume every night
(`/var/lib/skald/backups`). Copy them off the server too: your provider's server snapshots, or
a nightly `docker compose cp skald:/var/lib/skald/backups ./skald-backups` and a copy of that
folder elsewhere.

### A plain Ubuntu or Debian server (install.sh)

No Docker: Skald runs as a system user with systemd and cron, beside the nginx you already
have.

```sh
curl -fsSL https://raw.githubusercontent.com/spcaeo/skald/main/install.sh | sudo bash
# or, to answer nothing:
sudo ./install.sh --site example.com --log /var/log/nginx/access.log \
     --timezone America/New_York --email owner@example.com --non-interactive
```

It installs the code in `/opt/skald`, the config in `/etc/skald/config.yml`, the data in
`/var/lib/skald`, and prints the nginx lines to add (the `/traffic/` locations, served over the
HTTPS you already have). DNS and TLS are your existing site's: Skald lives under `/traffic/` on
the same name, or on a `stats.` name you add to nginx and to your certificate (for example with
`certbot --nginx -d stats.example.com`). [INSTALL.md](INSTALL.md) has the details.

### Railway

Railway runs the image as a service with a volume. Docs: <https://docs.railway.com/>.

1. **New project > Deploy a Docker image**: `ghcr.io/spcaeo/skald:latest`. (Or **Deploy from
   GitHub repo** with your fork: Railway builds `docker/Dockerfile`. `deploy/railway.json` sets
   the Dockerfile path and the health check; Railway reads `railway.json` from the repository
   root, so copy it there in your fork, or set the same values in the service's settings.)
2. **Add a volume** to the service (right-click the service, or the command palette) with the
   mount path `/var/lib/skald`. A service with a volume runs one replica and redeploys with a
   short stop.
3. **Variables:** `SKALD_SITE`, `SKALD_HOSTS`, `SKALD_TIMEZONE`, `SKALD_INGEST=true`,
   `SKALD_LOG_DIR=/var/lib/skald/ingest/<your site>`, and `PORT=8080`.
   Railway mounts volumes for root; Skald hands the volume to its own user at the first start,
   so `RAILWAY_RUN_UID=0` is **not** needed (it would run everything as root).
4. **Settings > Networking > Generate Domain** (or add your own domain and the `CNAME` record
   Railway shows). Put that `https://` address in `SKALD_BASE_URL`.
5. **The first owner:** open the service's shell (`railway ssh`, or the dashboard) and run
   `skald accounts init --org "Example Co" --owner-email owner@example.com`.
6. **The visitor's address:** Railway does not publish its proxies' ranges. Find them with
   `peers` and set `SKALD_TRUSTED_PROXIES` (see "The visitor's address" above).

A one-click "Deploy on Railway" button needs a template published from Railway's dashboard by
the project's owner; until there is one, use the steps above.

Railway lists volume sizes per plan on its volumes page. The trial tier's volume is small;
see <https://railway.com/pricing>.

### Render

Render runs the image as a web service with a persistent disk. **A disk needs a paid instance
type**; free instances have no disk and lose the history at every restart
(<https://render.com/docs/disks>).

**One click:** the button reads the Blueprint and asks for the settings it cannot guess.

```markdown
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/spcaeo/skald)
```

**By hand:** **New > Blueprint** and pick your fork: Render reads `render.yaml` at its root
(`deploy/render.yaml` is the same file). It makes:

- a web service from `ghcr.io/spcaeo/skald:latest`, port 8080, health check
  `/traffic-auth/login`;
- a 5 GB disk at `/var/lib/skald` (grow it later; it cannot shrink);
- the settings, asking you for `SKALD_SITE`, `SKALD_HOSTS`, `SKALD_BASE_URL` and
  `SKALD_LOG_DIR` (`/var/lib/skald/ingest/<your site>`).

Then:

1. **Domain:** the service gets an `onrender.com` address. For your own, **Settings > Custom
   Domains**, then the `CNAME` record Render shows at your DNS provider. Render issues the
   certificate. Put the final `https://` address in `SKALD_BASE_URL`.
2. **The first owner:** the service's **Shell** tab, then
   `skald accounts init --org "Example Co" --owner-email owner@example.com`.
3. **The visitor's address:** Render does not publish its proxies' ranges. Find them with
   `peers` and set `SKALD_TRUSTED_PROXIES` (see "The visitor's address" above).

Render's docs do not say who owns a new disk; either way the container hands it to its own user
at the first start.

With a disk, Render stops the old instance before it starts the new one, so a deploy has a few
seconds of downtime, and the service cannot scale past one instance. Both are fine for Skald.

### Fly.io

Fly runs the image on one Machine with a volume. Docs: <https://fly.io/docs/>.
`deploy/fly.toml` is ready to edit.

1. Install `flyctl` and sign in (<https://fly.io/docs/flyctl/install/>).
2. Edit `deploy/fly.toml`: `app` (a name of your own), `primary_region`, and the `SKALD_*`
   values under `[env]`.
3. Create the app and its volume, in the same region, then deploy:

   ```sh
   fly apps create skald-example
   fly volumes create skald_data --size 3 --region fra -a skald-example
   fly deploy -c deploy/fly.toml
   ```

4. **Disk ownership:** a new Fly volume belongs to root; the container hands it to its own
   user at the first start (the log says so once). `fly.toml` also sets the visitor's address
   (`Fly-Client-IP`, see "The visitor's address" above).
5. **The first owner:**
   `fly ssh console -a skald-example -C "skald accounts init --org 'Example Co' --owner-email owner@example.com"`.
6. **Domain:** the app answers at `https://<app>.fly.dev`. For your own name:
   `fly certs add stats.example.com -a skald-example`, then the `A`/`AAAA` (or `CNAME`)
   records it prints. Put the final address in `SKALD_BASE_URL` and deploy again.

`fly.toml` keeps the Machine running (`auto_stop_machines = "off"`, `min_machines_running = 1`):
a stopped Machine misses the schedule. A volume belongs to one Machine; never
`fly scale count 2`. Take volume snapshots with `fly volumes snapshots` as well as Skald's own
backups.

### Coolify, CapRover, Dokku

These run on your own server, like the VPS option, with a web panel or a `git push`.

**Coolify** (<https://coolify.io/docs/>): **New resource > Docker Compose**, from your fork's
`docker-compose.yml` (drop the `caddy` service: Coolify gives you HTTPS), or **Docker Image**
`ghcr.io/spcaeo/skald:latest`. Add **Persistent Storage** at `/var/lib/skald`, set the port to
8080, the domain to `https://stats.example.com`, and the `SKALD_*` variables. Run the first
owner command from the resource's **Terminal**.

**CapRover** (<https://caprover.com/docs/>): create an app with **Has Persistent Data**, add a
persistent directory with the path in app `/var/lib/skald`, set **Container HTTP Port** to
8080, add the environment variables, then **Deployment > Deploy via ImageName**:
`ghcr.io/spcaeo/skald:latest`. Turn on HTTPS for the app's domain. If the folder is not
writable by user 10001, `chown 10001:10001` its host directory once.

**Dokku** (<https://dokku.com/docs/>):

```sh
dokku apps:create skald
dokku storage:ensure-directory skald
sudo chown 10001:10001 /var/lib/dokku/data/storage/skald
dokku storage:mount skald /var/lib/dokku/data/storage/skald:/var/lib/skald
dokku config:set skald SKALD_SITE=example.com SKALD_HOSTS="example.com www.example.com" \
  SKALD_BASE_URL=https://stats.example.com SKALD_TIMEZONE=UTC
dokku domains:set skald stats.example.com
dokku ports:set skald http:80:8080
dokku git:from-image skald ghcr.io/spcaeo/skald:latest
dokku letsencrypt:enable skald          # with the dokku-letsencrypt plugin
dokku enter skald web skald accounts init --org "Example Co" --owner-email owner@example.com
```

On all three, the web server's own log can be mounted read-only at `/logs` when the site runs
on the same server (`/var/log/nginx:/logs:ro`), as with plain Docker.

### Kubernetes (optional)

`deploy/kubernetes.yaml` is a minimal example: a 5 GiB PersistentVolumeClaim, a Deployment with
**one replica** and the `Recreate` strategy (the old pod stops before the new one starts), a
security context whose `fsGroup: 10001` makes the volume writable, and a Service on port 80.

```sh
kubectl create namespace skald
kubectl -n skald apply -f deploy/kubernetes.yaml
kubectl -n skald exec deploy/skald -- skald accounts init --org "Example Co" --owner-email owner@example.com
```

Add an Ingress for `stats.example.com` with your controller and certificate manager, and set
`SKALD_TRUSTED_PROXIES` to the controller's pod network so Skald sees visitors' addresses, not
the controller's (see "The visitor's address" above). With a cloud load balancer in front of the
controller, set the controller's Service to `externalTrafficPolicy: Local` (or turn on its
PROXY protocol), or the controller itself sees only node addresses. Never raise `replicas` above 1.

---

## B. Where your site runs, and how Skald gets its data

| Your site runs on | How Skald gets the requests | AI crawlers seen? | Setup |
| --- | --- | --- | --- |
| Your own server (nginx, Apache, Caddy) | the access log | **yes** | [below](#your-own-server-nginx-apache-caddy) |
| Vercel | a Log Drain to Skald, plus `skald.js` if you like | **yes** | [below](#vercel) |
| Netlify | a Log Drain to Skald, plus `skald.js` if you like | **yes** | [below](#netlify) |
| Cloudflare (in front of any host, or Pages) | Logpush to R2 or S3, read as a CDN log | **yes** | [below](#cloudflare) |
| AWS CloudFront | standard logs in S3, read as a CDN log | **yes** | [below](#aws-cloudfront) |
| Fastly | a JSON logging endpoint | **yes** | [below](#fastly) |
| WordPress | the server's log; `skald.js` without a plugin | yes, with the log | [below](#wordpress) |
| Shopify, Webflow, Squarespace | `skald.js` (needs a proxy) and webhooks only | **no** | [below](#shopify-webflow-squarespace) |

**Why the log matters.** AI crawlers (GPTBot, ClaudeBot, PerplexityBot), search crawlers and
most bots do not run JavaScript. Only a log of every request shows them. A script in the page
sees people only.

**Never read the same request twice.** Behind a CDN, read the CDN's log, not the origin's as
well: a cache miss is in both.

### Your own server (nginx, Apache, Caddy)

- **Skald on the same server:** it reads the log in place. With Docker, mount the log folder
  read-only at `/logs` (`-v /var/log/nginx:/logs:ro`); with `install.sh`, give `--log`. Skald
  reads nginx's and Apache's `combined` format, its own extended nginx format (adds the host,
  the time taken and a request id) and Caddy's JSON log. Set `SKALD_LOG_FORMAT` or leave `auto`.
- **Skald on another machine:** run **skald-ship** on the web server. It tails the log and
  posts new lines to `https://stats.example.com/traffic-ingest/<site>` with an ingest token.
  [INGEST.md](INGEST.md) has the systemd unit.

### Vercel

Vercel keeps its request logs to itself, but it can post them to an address you give it: a
**Log Drain**. Skald takes Vercel's drain format directly. Drains are a Vercel Pro and
Enterprise feature (<https://vercel.com/docs/drains/using-drains>).

1. **In Skald:** turn on ingest (`SKALD_INGEST=true`), make the site with the log format
   **`vercel_json`** (or `auto`), and make an ingest token for it (above).
2. **In Vercel:** **Team Settings > Drains > Add Drain > Logs**.
   - Projects: your site's project. **Sources:** `static`, `edge`, `lambda` (also `external`
     and `redirect` if you use rewrites or redirects to other domains). Leave out `build`;
     Skald skips it anyway. **Environments:** `production`.
   - **Sampling:** 100% (no rules). A sample would undercount every figure.
   - **Destination: Custom endpoint.** URL:
     `https://stats.example.com/traffic-ingest/example.com?format=vercel`
   - **Format:** JSON or NDJSON; both work.
   - **Custom headers:** `Authorization: Bearer <the ingest token>`.
   - **Signature Verification Secret:** optional, below.
3. **Create the drain.** Vercel tests the endpoint; Skald answers 200. Records for host
   names outside `SKALD_HOSTS` (a test's sample records, say) are kept but never counted. The first figures appear in the
   live panel within minutes, and in the daily figures after the next daily run.
4. **Keep "IP addresses" visible** (Team Settings > Security & Privacy > IP Address
   Visibility). Without the visitor's address Skald cannot tell people apart, so it refuses
   those requests and counts them as rejected.

What Skald keeps from each request: the time, the visitor's address, the host, method, path
and query, status, referrer, user agent, response size and the request id. Everything else in
the record (deployment and project ids, JA3/JA4 fingerprints, messages, firewall details) is
dropped before anything is written. A Vercel record has no country, so the country cards stay
empty. Function output, build logs and background revalidations are not requests: Skald skips
them. A request whose function wrote several log lines is counted once.

**The signature (optional).** Vercel signs each delivery: `x-vercel-signature` is the
HMAC-SHA1 of the body with the drain's secret (<https://vercel.com/docs/drains/security>). To
require it, put the secret in an environment variable on Skald's side and name it in the
config (mount your own `/etc/skald/config.yml`):

```yaml
ingest:
  enabled: true
  drains:
    example.com:
      vercel_secret_env: SKALD_VERCEL_DRAIN_SECRET   # the variable's name, not the secret
```

Then a delivery with a wrong or missing signature is refused (401), even with a token, and a
signed delivery is accepted without one. `vercel_secret_file: /etc/skald/vercel-drain.secret` works instead of the
variable. If Vercel asks for an `x-vercel-verify` answer header when you create the drain, add
`vercel_verify: <the value Vercel shows>` beside it.

**skald.js on Vercel (optional).** The script adds what a log cannot see: forms, clicks,
scroll depth, booking embeds. It posts to the site's own address, so let Vercel pass two paths
to Skald with rewrites in `vercel.json`:

```json
{
  "rewrites": [
    { "source": "/traffic-beacon", "destination": "https://stats.example.com/traffic-beacon" },
    { "source": "/traffic-js/:path*", "destination": "https://stats.example.com/traffic-js/:path*" }
  ]
}
```

Add `https://www.example.com` to `SKALD_BEACON_ORIGINS`, and the tag to every page:

```html
<script src="/traffic-js/skald.js" data-site="example.com" defer></script>
```

Skald leaves those two paths out of the drain's figures, as nginx does on a server.

### Netlify

Netlify's **Log Drains** post the site's traffic logs to an address you give it. They are a
Netlify Enterprise feature (<https://docs.netlify.com/manage/monitoring/log-drains/>).

1. **In Skald:** turn on ingest, make the site with the log format **`netlify_json`** (or
   `auto`), and make an ingest token for it.
2. **In Netlify:** open the site's log drain settings (Netlify's guide above shows where), and
   choose the service **General HTTP endpoint**.
   - **Log types:** traffic logs. (Function, edge function and deploy logs are skipped.)
   - **Endpoint:** `https://stats.example.com/traffic-ingest/example.com?format=netlify`
   - **Authorization header:** `Bearer <the ingest token>`.
   - **Log Drain Format:** JSON or NDJSON; both work.
   - **Leave "Exclude personally identifiable information" off.** It drops the visitor's
     address and user agent, and without them Skald cannot tell people from crawlers; it
     refuses such records and counts them as rejected.

Skald keeps the time, address, host, method, path and query, status, referrer, user agent,
country, duration, response size and request id, and drops the rest (account, site and deploy
ids, content type, request size, firewall details). Netlify gives a country, so the country
cards work.

**skald.js on Netlify (optional):** proxy the two paths in `_redirects` (status 200 is a
rewrite), then add the tag as for Vercel:

```text
/traffic-beacon   https://stats.example.com/traffic-beacon    200
/traffic-js/*     https://stats.example.com/traffic-js/:splat 200
```

### Cloudflare

When Cloudflare is in front of your site (any host behind it, or Cloudflare Pages on your own
domain), its log sees every request, cache hits included. Skald reads Cloudflare **Logpush**
records for the `http_requests` dataset. Check which Cloudflare plans include Logpush on their
site (<https://developers.cloudflare.com/logs/logpush/>).

1. Create a Logpush job for the zone, dataset **HTTP requests**, to **R2** or **Amazon S3**,
   with the fields listed in [CDN-LOGS.md](CDN-LOGS.md).
2. On the server Skald runs on, sync the bucket every 15 minutes and append new files to one
   log (the script is in [CDN-LOGS.md](CDN-LOGS.md)), then point Skald at it with log format
   `cloudflare_json`. If Skald runs on a platform, run the same script on any machine and post
   the lines with skald-ship.

Read the Cloudflare log only, never the origin's log as well.

### AWS CloudFront

Turn on **standard logging** to S3 for the distribution, sync the bucket, and point Skald at
the appended log with format `cloudfront_w3c`. [CDN-LOGS.md](CDN-LOGS.md) has every step.
CloudFront's standard logs have no country.

### Fastly

Create an S3 or SFTP logging endpoint with the JSON format given in
[CDN-LOGS.md](CDN-LOGS.md), and read it with format `fastly_json`.

### WordPress

- **WordPress on a server you run** (a VPS, or any host that gives you the access log): read
  the web server's log, as for [your own server](#your-own-server-nginx-apache-caddy). That
  sees AI crawlers and bots too.
- **skald.js without a plugin:** add the tag to the theme's `<head>` (a child theme's
  `header.php`, or your theme's "header scripts" setting) and proxy `/traffic-beacon` and
  `/traffic-js/` to Skald in the web server, as [INTEGRATIONS.md](INTEGRATIONS.md) shows for
  nginx.
- **Managed WordPress without log access:** use Cloudflare in front and read its log, or
  `skald.js` alone (below, what that loses).

See also: the **Third Audience** WordPress plugin, by the same author.

### Shopify, Webflow, Squarespace

These platforms give you **no server log** and no log drain, and they do not let you proxy a
path to another server. What remains:

- **Webhooks** (server to server, no proxy needed): Stripe, Calendly, Cal.com, HubSpot and
  Typeform post to `https://stats.example.com/traffic-hooks/<site>/<tool>`.
  [INTEGRATIONS.md](INTEGRATIONS.md) has each one.
- **skald.js**, only if a proxy you control sits in front of the domain (for example Cloudflare
  with a route that sends `/traffic-beacon` and `/traffic-js/*` to Skald). Skald refuses
  beacons from another site's address by design, so the script cannot post straight to
  `stats.example.com`.

**What you lose without a log:** AI crawlers, search crawlers and bots are **not seen at all**:
they do not run scripts. Citations from answer engines are seen only when the visitor's browser
runs the script and keeps the referrer. People who block scripts are not counted. The audit
against the log, the five groups and the bounds against page views do not apply; the figures
are the script's events only. If your plan allows Cloudflare in front of the store's domain,
its log brings most of this back.

---

## Sources

Checked on 2026-10-11.

- Vercel Log Drains fields and formats: <https://vercel.com/docs/drains/reference/logs>
- Vercel drains setup (custom endpoint, headers, plans): <https://vercel.com/docs/drains/using-drains>
- Vercel drain signature: <https://vercel.com/docs/drains/security>
- Netlify Log Drains (traffic log fields, general HTTP endpoint): <https://docs.netlify.com/manage/monitoring/log-drains/>
- Render Blueprints: <https://render.com/docs/blueprint-spec>; disks: <https://render.com/docs/disks>; the Deploy button: <https://render.com/docs/deploy-to-render>
- Railway config as code: <https://docs.railway.com/reference/config-as-code>; volumes: <https://docs.railway.com/reference/volumes>
- Fly.io configuration: <https://fly.io/docs/reference/configuration/>; request headers
  (`Fly-Client-IP`, `X-Forwarded-For`): <https://fly.io/docs/networking/request-headers/>
- ingress-nginx ConfigMap (`use-forwarded-headers`, `compute-full-forwarded-for`):
  <https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/configmap/>
- Railway's and Render's docs name no proxy ranges and no client-address header (checked
  2026-10-11: <https://docs.railway.com/reference/public-networking>,
  <https://render.com/docs/web-services>); their community forums disagree, hence `peers`.
- Cloudflare Logpush: <https://developers.cloudflare.com/logs/logpush/>
