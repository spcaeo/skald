# Upgrading Skald

How Skald tells you a newer release is out, how to install it safely, what
happens to the databases, how to go back, and how to let it upgrade itself.

| You installed with | Upgrade with |
| --- | --- |
| The install script (`install.sh`) | `sudo skald upgrade` ([below](#upgrade-an-install-script-install)) |
| Docker or Docker Compose | pull the new image tag ([Docker](#docker)) |
| By hand (DEPLOY.md) | DEPLOY.md, "Deploying a new version", then `skald migrate` |

## Update notices

Once a day Skald asks GitHub for its latest release. It is one HTTPS request to
`https://api.github.com/repos/spcaeo/skald/releases/latest` with one header,
`User-Agent: Skald/<your version>`. Nothing else goes: no site name, no figure,
no visitor address, no install ID. GitHub sees your server's address, as for
any download. The answer is kept in `updates.json` beside the history, so the
mails and the dashboard never ask the network themselves.

When a newer release is out:

- the **daily and weekly mail** show a card: "Skald 2.2.0 is available (you run
  2.1.0)", the first lines of what is new, and a link to the release page;
- the **dashboard** shows the same line to owners and admins (viewers never see
  it). **×** hides it in that browser until the next release;
- `skald updates` prints it; `skald updates --check-now` asks GitHub now.

A **security release** is drawn as important (red) in both places. A release is
a security release when its name has `[security]`, or its notes have
`[security]` or a line `Labels: security`.

When GitHub cannot be reached (no network, a firewall), nothing breaks: the log
says so once, and Skald tries again the next day.

Settings (`config.yml`):

```yaml
updates:
  check: true          # false: never ask GitHub; no notice is shown
  repo: spcaeo/skald   # where the releases are published (a fork, a mirror)
  auto: off            # off, patch or minor: see "Automatic upgrades"
```

The daily run asks (at most once a day) on an installed copy: one with
`build.json` beside the code, which install.sh, the Docker image and a deploy
write. A git checkout never asks by itself.

## Upgrade an install-script install

```sh
sudo skald upgrade --dry-run      # download, check, say what would happen
sudo skald upgrade                # do it (asks first; --yes does not)
sudo skald upgrade --to v2.2.0    # a given release instead of the latest
```

It runs as root because it replaces `/opt/skald`; every command it runs
on your data runs as the `skald` user. The steps:

1. **Refuses** inside the daily run's window, in a Docker container and in a git
   checkout. The window is `report.run_window` (`"HH:MM-HH:MM"` in
   `report.timezone`), else the cron line's run-daily time ±10 minutes.
2. **Picks the release**: the latest, or `--to`. A downgrade is refused. A new
   major version (2.x to 3.0) is refused unless you add `--allow-major`: read its
   notes first, it may need steps by hand.
3. **Downloads** `skald-X.Y.Z.tar.gz` and `SHA256SUMS` from the GitHub release
   and checks the tarball's SHA-256. A mismatch stops it; nothing is changed.
   `--source-url` takes the two files from a mirror instead.
4. **Unpacks** it beside the code. A path outside the folder, a link or a
   different layout stops it.
5. `--dry-run` **stops here**: it shows the new code's `migrate --check` against
   your databases (it only reads them) and what it would do next.
6. Runs the **health checks** with the old code first, so it judges only what
   the new code breaks. Then copies **every database** (history, accounts,
   conversions) into `backups/pre-upgrade-<from>-to-<to>-<time>/` and
   restore-tests each copy. A copy that fails the test stops it.
7. **Swaps the code**: `/opt/skald` becomes `/opt/skald.prev`, the
   new release becomes `/opt/skald`. Then the new code's `migrate`.
8. **Restarts** the helpers (`skald-refresh`, `skald-beacon`) and checks:
   the helper answers, and `live`, `check --day today` and `audit --live` exit 0.
9. **Rolls back** when step 7 or 8 fails: the old code goes back, every database
   is put back from the copy, the helpers restart, and it says what failed.

While it runs, the cron's `live` run waits (it holds `live.lock`). Each outcome
is one line in `upgrades.log` beside the history. A success is also a deploy
marker on the dashboard's charts.

A release that changes the systemd units or the cron lines says so in its
notes. Then also run `install.sh` again (it keeps your config and data).

## Database migrations

Each database has a schema version, and the code knows how to bring an older
file up to date. Opening a file with newer code upgrades it, as it always has.
`migrate` makes that explicit:

```sh
sudo skald migrate --check    # each database, its version, the code's, the steps pending
sudo skald migrate            # a restore-tested copy first, then the upgrade
```

```
history      schema 11 (code 12)  steps pending  /var/lib/skald/history.sqlite
    v12: add index ...
accounts     schema 5 (code 5)  up to date  /var/lib/skald/accounts.sqlite
conversions  schema - (code 3)  not made yet  /var/lib/skald/conversions.sqlite
```

The steps come from each database's own upgrade code; `migrate` never repeats
them. Every upgrade is written to `migrations.json` beside the history: when,
which file, from which version to which. `upgrade` runs `migrate` for you.

**Newer than the code.** Old code never opens a database a newer Skald wrote.
It stops with "accounts file is schema 6, this code understands 5; upgrade
skald before reading it", and `migrate --check` marks the file "NEWER
than this code". Upgrade Skald, or roll back the database too (below).

## Rolling back

`upgrade` rolls back by itself when a check fails. To go back later by hand,
outside the daily run's window:

```sh
sudo systemctl stop skald-refresh skald-beacon
sudo rsync -a --delete /opt/skald.prev/ /opt/skald/
sudo cp /opt/skald/build.json /var/www/skald/build.json
# only if the release migrated a database: put the copies taken before it back
ls /var/lib/skald/backups/pre-upgrade-*/
sudo -u skald cp /var/lib/skald/backups/pre-upgrade-<...>/history.sqlite /var/lib/skald/history.sqlite
sudo rm -f /var/lib/skald/history.sqlite-wal /var/lib/skald/history.sqlite-shm
sudo systemctl start skald-refresh skald-beacon
```

### Rolling back by hand

If a rollback says "ROLLBACK INCOMPLETE", the copies are in the folder it names.
Do the steps above with that folder. What was written after the copy (a live
snapshot, a sign-in) is lost; the history's days are rebuilt by the next run.

## Automatic upgrades

Off by default. install.sh installs `skald-upgrade.timer`: once a day, at
a random minute at least 2 hours from the daily run, it runs
`skald upgrade --auto`. With `updates.auto: off` that is only the daily check.

```yaml
updates:
  auto: patch    # 2.1.0 -> 2.1.1 only: fixes
  # auto: minor  # also 2.1.x -> 2.2.0: new features, never breaking
```

An automatic upgrade does every step above, backup, checks and rollback
included. It never crosses a major version. It mails the result (upgraded, or
rolled back and why) to the daily mail's recipients. See when it runs with
`systemctl list-timers skald-upgrade.timer`; its output goes to
`/var/log/skald/upgrade.log`. Turn the timer off with
`sudo systemctl disable --now skald-upgrade.timer`.

## Docker

An image is never changed in place: `upgrade` in a container says to pull the
new tag. Each release is published as four tags:

| Tag | Follows |
| --- | --- |
| `ghcr.io/spcaeo/skald:2.2.0` | exactly this release |
| `ghcr.io/spcaeo/skald:2.2` | fixes to 2.2 only |
| `ghcr.io/spcaeo/skald:2` | every 2.x release: fixes and features, never a breaking change |
| `ghcr.io/spcaeo/skald:latest` | every release, a new major version too |

Pin **`:2`** for safe updates. Upgrade:

```sh
docker compose pull && docker compose up -d           # Compose
docker pull ghcr.io/spcaeo/skald:2 && docker rm -f skald && docker run -d --name skald ...   # plain Docker
```

The databases are migrated when the new container starts, as above; take a
copy first if you want one (`docker exec skald skald backup`).

**Automatically, with a cron line** on the host (outside the daily run):

```
30 3 * * * root cd /srv/skald && docker compose pull -q && docker compose up -d
```

**Automatically, with Watchtower**: it checks for a newer image of the tag you
run and restarts the container on it. With `--label-enable` it updates only the
containers that opt in with the label `com.centurylinklabs.watchtower.enable=true`;
`--schedule` takes a 6-field cron expression; `--cleanup` removes the old image
([Watchtower's arguments](https://containrrr.dev/watchtower/arguments/)):

```sh
docker run -d --name watchtower -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower --label-enable --cleanup --schedule "0 30 3 * * *"
```

and run Skald with `--label com.centurylinklabs.watchtower.enable=true` on the
`:2` tag. Watchtower does not take a backup or roll back: Skald's nightly
backup (`/var/lib/skald/backups`) is your way back.
