# Docker: first install in 10 minutes

From nothing to a working dashboard on a server that already runs your website with nginx: run the container, sign in, fill the last 14 days, check it with the doctor, then add the script tag and hooks.

## 1. Run it (2 minutes)

```
docker run -d --name skald --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v /var/log/nginx:/logs:ro \
  -v skald-data:/var/lib/skald \
  -e SKALD_SITE=example.com \
  -e SKALD_HOSTS="example.com www.example.com" \
  -e SKALD_TIMEZONE=America/New_York \
  -e SKALD_BASE_URL=https://www.example.com \
  -e SKALD_TRUSTED_PROXIES=private -e SKALD_REAL_IP_HEADER=X-Real-IP \
  ghcr.io/spcaeo/skald:2
```

- `127.0.0.1:` publishes the port on this machine only. nginx in front gives it to the world. Keep the same line in every later `docker run`.
- `/var/log/nginx` is read-only: Skald reads the log, never changes it.
- `skald-data` holds everything Skald keeps. It must be mounted at `/var/lib/skald`, where the image keeps its data. Keep the volume.
- `:2` follows every 2.x release and never a breaking one.
- Not a Next.js site? Add `-e SKALD_ASSET_PREFIXES="/wp-content/ /wp-includes/"` (WordPress), or the folder your pages load their scripts and styles from. A visit counts as people only when its browser fetched one.
- The last line is for nginx on the same machine. It lets Skald see each visitor's address, not nginx's.
- Countries: nginx's stock log has no country. To get one, give Skald a GeoIP country file. DB-IP's free country file works. Keep it on the host, for example in `/usr/share/GeoIP`, and add `-v /usr/share/GeoIP:/geoip:ro -e SKALD_COUNTRY_DB=/geoip/dbip-country-lite.mmdb`. Each visit then gets its address's country, and so does a lead your backend sends with an address. Refresh the file on the host once a month (your updater or a cron job that downloads DB-IP's new file). Skald reads the new file by itself, no restart. DB-IP's credit is shown under the countries. Without a file, countries say Not recorded. A country your log already carries (Cloudflare's, or nginx's own `cc=`) always wins.
- A new install keeps each visit with its IP address, and each lead's name and email, so admins can look a person up. To keep neither, add `-e SKALD_KEEP_IPS=0 -e SKALD_IDENTITY=anonymous`. Admins can change both later in **Settings > Data retention > People**. See [Privacy](privacy.md).

## 2. Put it on the web (2 minutes)

In your site's HTTPS `server { }` block, before `location /`:

```
location ^~ /traffic {
    access_log off;
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    client_max_body_size 6m;
}
```

Then check and reload. Careful: your website shares this nginx, so never reload without the check.

```
sudo nginx -t && sudo systemctl reload nginx
```

## 3. Sign in (1 minute)

```
docker exec -it skald skald accounts init --org "Example Co" --owner-email owner@example.com
```

It prints a "set your password" link, valid 60 minutes. Open it, set a password, and you are in at `https://www.example.com/traffic/`. See [Sign-in and team](sign-in-and-team.md) to invite others.

## 4. Fill the last 14 days (2 minutes)

```
docker exec skald skald backfill --days 14
```

It stores each day the log's rotations still hold. Today fills by itself within two minutes.

## 5. Ask the doctor (1 minute)

```
docker exec skald skald doctor
```

One line per part, each OK, NEEDS ATTENTION or OFF, and the fix in plain words:

| Line | Checks |
| --- | --- |
| Daily run | It ran in the last day, and did not fail |
| Days stored | None of the last 14 days is missing or withheld; if some are, the backfill command |
| Access log | The log is there, readable, and written today |
| Page assets | A browser fetched your page assets: without them nobody counts as a person |
| Web app | The dashboard has its menu |
| Hook receiver | The part that takes hooks and the script tag answers |
| Hook ... | Each hook: its secret, and its last delivery |
| One lead, two tools | The same lead arrived through two tools (two hooks, or a hook and the lead database), so it counts twice |
| Script tag | Its origins, and the last event from a page |
| Lead database | The website's lead database can be read, when one is set |
| Mail | The mail settings are complete |
| Version | A newer release, from the last daily check (it never goes online itself) |
| Disk | Free space where Skald keeps its data |

OFF is a part you have not turned on. It exits 1 when anything needs attention, so a script can watch it. `--json` prints the same list as JSON. `--send-test` also sends one test mail to the recipients.

The daily run happens at 07:15 in the site's time zone. Before the first one, "Daily run: has never run here" is expected.

## 6. Add the script tag (2 minutes)

The tag gives form steps, clicks and booking widgets. Start the container again with your site's origin:

```
docker rm -f skald
docker run ... -e SKALD_BEACON_ORIGINS=https://www.example.com ...    # the same command, plus this line
```

Then copy the tag from **Settings > Integrations** into every page's head. See [Tracking script](tracking-script.md).

Only the first site needs `SKALD_BEACON_ORIGINS`. A site you add later from the dashboard takes events from its own **Host names** (**Settings > This site > Sites**). Its page assets are its own too: a site that is not Next.js sets them in **Settings > This site > Sites > Page assets** (`SKALD_ASSET_PREFIXES` is for the first site only). See [Tracking script](tracking-script.md), "More than one site".

## 7. Add hooks

**Settings > Integrations > Make secret** for each tool, or on the server:

```
docker exec skald skald hooks secret example.com lead
```

Then: [Send leads from your backend](leads-from-your-backend.md), [Demo bookings](demo-bookings.md), and [Webhooks](webhooks.md) for the other tools. Not sure which? [Pick your road](pick-your-road.md).

## Upgrade

```
docker pull ghcr.io/spcaeo/skald:2
docker rm -f skald
docker run ...        # the same command as before
```

The volume keeps all data. Not during the daily run.

## When something is wrong

| You see | Why | Fix |
| --- | --- | --- |
| A plain page with no menu | An old image | Pull the new image; the doctor's **Web app** line says so |
| "nothing parsed" | The log is not mounted, or not readable | `docker exec skald ls -l /logs`; the container's user is in group `adm` (gid 4), which reads `/var/log/nginx` on Ubuntu and Debian |
| No person counted | No page asset seen | Set `SKALD_ASSET_PREFIXES` (the first site) or **Settings > Sites > Page assets** (a site added later); the doctor's **Page assets** line says which |
| A hook answers 404 | The hook has no secret | Make its secret |
| A hook answers 502 | An image older than 2.2.2 | Pull the new image |
| "Too many tries" on sign-in for everyone | The proxy in front is not trusted | Set `SKALD_TRUSTED_PROXIES` and `SKALD_REAL_IP_HEADER` |

`docker logs skald` shows one line per job.
