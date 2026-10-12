#!/usr/bin/env bash
# Install Skald on Ubuntu 22.04 / 24.04 / 26.04 or Debian 12.
#
#   curl -fsSL https://raw.githubusercontent.com/spcaeo/skald/main/install.sh | sudo bash
#   git clone https://github.com/spcaeo/skald && cd skald && sudo ./install.sh
#
#   sudo ./install.sh --site example.com --log /var/log/nginx/access.log \
#        --timezone America/New_York --email owner@example.com --non-interactive
#   sudo ./install.sh --uninstall            # units, cron and the command go; code, config, data stay
#   sudo ./install.sh --uninstall --purge    # and the code, config, data and user too
#
# What it does (DEPLOY.md is the same by hand): installs Python 3.11+ (and PyYAML),
# makes the skald user (in group adm, to read the web server's log), puts
# the code in /opt/skald (the previous copy in /opt/skald.prev),
# writes /etc/skald/config.yml from config.example.yml (kept if it is
# there), installs the systemd units and /etc/cron.d/skald, puts the
# `skald` command in /usr/local/bin, runs a first `check` and `live`, and
# prints the web server lines to add. Running it again upgrades the code and
# keeps the config, the env file and the history.
set -euo pipefail

APP=/opt/skald
ETC=/etc/skald
DATA=/var/lib/skald
LOGS=/var/log/skald
WWW=/var/www/skald
SVC_USER=skald
CRON_FILE=/etc/cron.d/skald
LOGROTATE_FILE=/etc/logrotate.d/skald
CMD_FILE=/usr/local/bin/skald
UNIT_DIR=/etc/systemd/system
UNITS=(skald-refresh.service skald-beacon.service skald-bot-policy.service skald-bot-policy.path)
REPO_URL=${SKALD_REPO:-https://github.com/spcaeo/skald}

SITE="" HOSTS="" LOG="" FORMAT="auto" TZONE="" EMAIL="" ORIGIN="" DAILY_AT="07:15"
SOURCE="" REF="main" INTERACTIVE=1 FIRST_RUN=1 UNINSTALL=0 PURGE=0 PY=""

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: install.sh [options]

  --site NAME          the site's name, e.g. example.com (default: this host's name)
  --hosts "A B"        host names the report is about (default: NAME and www.NAME)
  --log PATH           the web server's access log (default: /var/log/nginx/access.log)
  --format FMT         auto, nginx_extended, nginx_combined, apache_combined, caddy_json, ...
  --timezone ZONE      the zone a day is cut in, e.g. America/New_York (default: the server's)
  --email ADDR         who gets the daily and weekly mail
  --origin URL         the dashboard's origin (default: https://NAME)
  --daily-at HH:MM     the daily run, in the site's time zone (default: 07:15)
  --source DIR         install from this checkout (default: the script's own folder,
                       else a download of --ref from the repository)
  --ref REF            branch or tag to download (default: main)
  --non-interactive    ask nothing; take flags and defaults (alias: -y)
  --no-first-run       skip the first check and live
  --uninstall          remove the systemd units, cron and logrotate files and the command
  --purge              with --uninstall: also the code, config, data, dashboard and user
  -h, --help           this text
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --site) SITE=${2:?--site needs a value}; shift 2 ;;
    --hosts) HOSTS=${2:?--hosts needs a value}; shift 2 ;;
    --log) LOG=${2:?--log needs a value}; shift 2 ;;
    --format) FORMAT=${2:?--format needs a value}; shift 2 ;;
    --timezone) TZONE=${2:?--timezone needs a value}; shift 2 ;;
    --email) EMAIL=${2:?--email needs a value}; shift 2 ;;
    --origin) ORIGIN=${2:?--origin needs a value}; shift 2 ;;
    --daily-at) DAILY_AT=${2:?--daily-at needs a value}; shift 2 ;;
    --source) SOURCE=${2:?--source needs a value}; shift 2 ;;
    --ref) REF=${2:?--ref needs a value}; shift 2 ;;
    --non-interactive|-y|--yes) INTERACTIVE=0; shift ;;
    --no-first-run) FIRST_RUN=0; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --purge) PURGE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done

# Questions come from the terminal, also when the script itself arrives on stdin (curl | bash).
ask() {  # ask VAR "question" "default"
  local answer=""
  if [ "$INTERACTIVE" = 1 ] && [ -r /dev/tty ] && { true </dev/tty; } 2>/dev/null; then
    printf '%s [%s]: ' "$2" "$3" >/dev/tty
    IFS= read -r answer </dev/tty || answer=""
  fi
  printf -v "$1" '%s' "${answer:-$3}"
}

systemd_up() { [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; }

need_root() {
  [ "$(id -u)" = 0 ] || die "run as root: sudo $0 $*"
}

check_os() {
  local id="" ver=""
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    id=$(. /etc/os-release && echo "${ID:-}")
    # shellcheck disable=SC1091
    ver=$(. /etc/os-release && echo "${VERSION_ID:-}")
  fi
  case "$id:$ver" in
    ubuntu:22.04|ubuntu:24.04|ubuntu:26.04|debian:12|debian:13) say "system: $id $ver" ;;
    ubuntu:*|debian:*) warn "$id $ver is not one this script was tested on; carrying on" ;;
    *) die "this script is for Ubuntu and Debian (found '${id:-unknown}'); see docs/INSTALL.md for Docker or the manual way" ;;
  esac
}

# ---------------------------------------------------------------- uninstall

uninstall() {
  say "removing the systemd units, cron and logrotate files and $CMD_FILE"
  if systemd_up; then
    for u in "${UNITS[@]}"; do
      systemctl disable --now "$u" >/dev/null 2>&1 || true
    done
  fi
  for u in "${UNITS[@]}"; do rm -f "$UNIT_DIR/$u"; done
  rm -f "$CRON_FILE" "$LOGROTATE_FILE" "$CMD_FILE"
  if systemd_up; then systemctl daemon-reload; fi
  if [ "$PURGE" = 1 ]; then
    local sure="no"
    if [ "$INTERACTIVE" = 1 ]; then
      ask sure "Delete $APP, $ETC, $DATA (the history), $LOGS and $WWW for good? type yes" "no"
    else
      sure=yes
    fi
    [ "$sure" = yes ] || die "nothing deleted; the units and cron are already gone"
    rm -rf "$APP" "$APP.prev" "$APP.new" "$ETC" "$DATA" "$LOGS" "$WWW"
    if id "$SVC_USER" >/dev/null 2>&1; then userdel "$SVC_USER" || true; fi
    say "purged. Remove the web server lines you added for /traffic/ by hand."
  else
    say "kept: $APP (code), $ETC (config, env), $DATA (history, accounts), $WWW (dashboard)."
    say "--uninstall --purge deletes them. Remove the web server lines for /traffic/ by hand."
  fi
}

# ------------------------------------------------------------------ install

pick_python() {
  local c
  for c in python3 python3.14 python3.13 python3.12 python3.11; do
    if command -v "$c" >/dev/null 2>&1 &&
       "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
      PY=$(command -v "$c"); return 0
    fi
  done
  return 1
}

install_packages() {
  say "installing packages (python3, PyYAML, tzdata, cron)"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 python3-yaml tzdata cron ca-certificates curl >/dev/null
  if ! pick_python; then
    # Ubuntu 22.04 ships 3.10; 3.11 is in its universe component.
    say "python3 is older than 3.11: installing python3.11"
    apt-get install -y -qq python3.11 >/dev/null || die "could not install Python 3.11 or newer"
    pick_python || die "Python 3.11 or newer is needed"
  fi
  say "python: $PY ($("$PY" -c 'import platform; print(platform.python_version())'))"
}

make_user_and_dirs() {
  if ! id "$SVC_USER" >/dev/null 2>&1; then
    say "creating the $SVC_USER user"
    useradd --system --no-create-home --home-dir "$DATA" --shell /usr/sbin/nologin "$SVC_USER"
  fi
  usermod -aG adm "$SVC_USER"
  install -d -o root -g root -m 0755 "$APP"
  install -d -o root -g "$SVC_USER" -m 0750 "$ETC"
  install -d -o "$SVC_USER" -g "$SVC_USER" -m 0750 "$DATA" "$LOGS"
  install -d -o "$SVC_USER" -g "$SVC_USER" -m 0755 "$WWW"
}

TMP_SRC=""
cleanup() { if [ -n "$TMP_SRC" ]; then rm -rf "$TMP_SRC"; fi; }
trap cleanup EXIT

find_source() {
  local here=""
  if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  fi
  if [ -n "$SOURCE" ]; then
    [ -f "$SOURCE/skald/cli.py" ] || die "--source $SOURCE: no skald/cli.py there"
    SOURCE=$(cd "$SOURCE" && pwd)
  elif [ -n "$here" ] && [ -f "$here/skald/cli.py" ]; then
    SOURCE=$here
  else
    TMP_SRC=$(mktemp -d)
    say "downloading $REPO_URL ($REF)"
    curl -fsSL "$REPO_URL/archive/$REF.tar.gz" | tar -xz -C "$TMP_SRC" --strip-components=1 \
      || die "could not download $REPO_URL/archive/$REF.tar.gz"
    [ -f "$TMP_SRC/skald/cli.py" ] || die "the download has no skald/cli.py"
    SOURCE=$TMP_SRC
  fi
  say "source: $SOURCE"
}

install_code() {
  if [ "$SOURCE" = "$APP" ]; then
    say "running from $APP itself: code left as it is"
    return
  fi
  say "installing the code in $APP (the previous copy goes to $APP.prev)"
  rm -rf "$APP.new"
  install -d -o root -g root -m 0755 "$APP.new"
  tar -C "$SOURCE" --exclude=.git --exclude=./config.yml --exclude='__pycache__' \
      --exclude='*.sqlite' --exclude='*.pyc' --exclude=./build.json -cf - . \
    | tar -C "$APP.new" --no-same-owner -xf -
  local name version release=0 commit=unknown
  name=$(tr -d '\n' < "$SOURCE/NAME" 2>/dev/null || echo Skald)
  version=$(tr -d '\n' < "$SOURCE/VERSION" 2>/dev/null || echo 0)
  if command -v git >/dev/null 2>&1 && [ -d "$SOURCE/.git" ]; then
    release=$(git -C "$SOURCE" rev-list --count HEAD 2>/dev/null || echo 0)
    commit=$(git -C "$SOURCE" rev-parse --short HEAD 2>/dev/null || echo unknown)
  fi
  printf '{"schema_version":1,"name":"%s","version":"%s","tagline":"","release":%s,"commit":"%s","deployed_at":"%s"}\n' \
    "$name" "$version" "$release" "$commit" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$APP.new/build.json"
  chown -R root:root "$APP.new"
  chmod -R u=rwX,go=rX "$APP.new"
  if [ -d "$APP" ] && [ -n "$(ls -A "$APP")" ]; then
    rm -rf "$APP.prev"
    mv "$APP" "$APP.prev"
  else
    rmdir "$APP" 2>/dev/null || true
  fi
  mv "$APP.new" "$APP"
  install -o "$SVC_USER" -g "$SVC_USER" -m 0644 "$APP/build.json" "$WWW/build.json"
}

default_tz() {
  local z=""
  if command -v timedatectl >/dev/null 2>&1; then z=$(timedatectl show -p Timezone --value 2>/dev/null || true); fi
  if [ -z "$z" ] && [ -r /etc/timezone ]; then z=$(tr -d ' \n' < /etc/timezone); fi
  echo "${z:-UTC}"
}

default_log() {
  local f
  for f in /var/log/nginx/access.log /var/log/apache2/access.log /var/log/caddy/access.log; do
    if [ -e "$f" ]; then echo "$f"; return; fi
  done
  echo /var/log/nginx/access.log
}

write_config() {
  local cfg="$ETC/config.yml"
  if [ -f "$cfg" ]; then
    say "keeping $cfg (delete it and run again to start from config.example.yml)"
    return
  fi
  [ -n "$SITE" ] || ask SITE "Site name (the host people visit)" "$(hostname -f 2>/dev/null || hostname)"
  [ -n "$LOG" ] || ask LOG "The web server's access log" "$(default_log)"
  [ -n "$TZONE" ] || ask TZONE "Time zone a day is cut in" "$(default_tz)"
  [ -n "$EMAIL" ] || ask EMAIL "Email for the daily and weekly mail (empty: none yet)" ""
  SITE=$(printf '%s' "$SITE" | tr '[:upper:]' '[:lower:]')
  printf '%s' "$SITE" | grep -Eq '^[a-z0-9][a-z0-9.-]*$' || die "--site '$SITE': use a host name such as example.com"
  "$PY" -c 'import sys, zoneinfo; zoneinfo.ZoneInfo(sys.argv[1])' "$TZONE" 2>/dev/null \
    || die "--timezone '$TZONE' is not a time zone name (e.g. Europe/Berlin)"
  [ -n "$ORIGIN" ] || ORIGIN="https://$SITE"
  [ -n "$HOSTS" ] || HOSTS="$SITE www.${SITE#www.}"
  say "writing $cfg"
  SITE="$SITE" HOSTS="$HOSTS" LOG="$LOG" FORMAT="$FORMAT" TZONE="$TZONE" EMAIL="$EMAIL" \
  ORIGIN="$ORIGIN" ETC="$ETC" "$PY" - "$APP/config.example.yml" "$cfg.new" <<'PY'
import os, re, sys
src, out = sys.argv[1], sys.argv[2]
e = os.environ
text = open(src).read()
hosts = []
for h in e["HOSTS"].split():
    if h not in hosts:
        hosts.append(h)
log_dir, log_base = os.path.split(e["LOG"])

def sub(pattern, repl, flags=re.M):
    global text
    text, n = re.subn(pattern, lambda m: repl, text, count=1, flags=flags)
    if n != 1:
        sys.exit(f"config.example.yml changed: no line matches {pattern!r}")

sub(r"^  name: example\.com$", f"  name: {e['SITE']}")
sub(r"^    - example\.com\n    - www\.example\.com$", "\n".join(f"    - {h}" for h in hosts))
sub(r"^  dir: /var/log/nginx$", f"  dir: {log_dir}")
sub(r"^  base: access\.log$", f"  base: {log_base}")
sub(r"^  format: auto$", f"  format: {e['FORMAT']}")
sub(r"^  timezone: America/New_York$", f"  timezone: {e['TZONE']}")
sub(r"^  # env_file: (\S+)$", f"  env_file: {e['ETC']}/env")
sub(r"^  url: https://stats\.example\.com/example\.com/$",
    f"  url: {e['ORIGIN'].rstrip('/')}/traffic/{e['SITE']}/")
# The example's views are one site's; a new install starts with "All" only.
sub(r"^  views:\n(?:    - \{.*\}\n)+", "  views: []\n")
if e["EMAIL"]:
    sub(r"^    - owner@example\.com$", f"    - {e['EMAIL']}")
# Mails stay off until the mail section and the env file's SMTP login are set.
sub(r"^  weekly_report_attachment: false$",
    "  weekly_report_attachment: false\n"
    "  # install.sh: off until host, from and the SMTP login (env file) are set.\n"
    "  daily: false\n  weekly: false")
open(out, "w").write(text)
PY
  install -o root -g "$SVC_USER" -m 0640 "$cfg.new" "$cfg"
  rm -f "$cfg.new"
}

write_env() {
  local env="$ETC/env"
  if [ -f "$env" ]; then return; fi
  say "writing $env (0600; the visitor key is made here, on this server)"
  umask 077
  {
    echo "# Secrets for skald: sourced by cron and the helpers. Never commit or share."
    echo "# The SMTP login, under the names config.yml's mail.user_env and mail.password_env give:"
    echo "# export SMTP_USER='...'"
    echo "# export SMTP_PASSWORD='...'"
    echo "export SKALD_VISITOR_KEY='$("$PY" -c 'import secrets; print(secrets.token_hex(32))')'"
  } > "$env"
  umask 022
  chown "$SVC_USER:$SVC_USER" "$env"
  chmod 0600 "$env"
}

install_units() {
  say "installing the systemd units"
  local origin
  origin=${ORIGIN:-$(sed -n 's#^  url: \(https\?://[^/]*\)/.*#\1#p' "$ETC/config.yml" | head -n 1)}
  origin=${origin:-https://www.example.com}
  sed -e "s#/usr/bin/python3 #$PY #g" -e "s#--origin https://www.example.com#--origin $origin#" \
    "$APP/systemd/skald-refresh.service" > "$UNIT_DIR/skald-refresh.service"
  sed -e "s#/usr/bin/python3 #$PY #g" "$APP/systemd/skald-beacon.service" > "$UNIT_DIR/skald-beacon.service"
  sed -e "s#/usr/bin/python3 #$PY #g" "$APP/systemd/skald-bot-policy.service" > "$UNIT_DIR/skald-bot-policy.service"
  install -m 0644 "$APP/systemd/skald-bot-policy.path" "$UNIT_DIR/skald-bot-policy.path"
  chmod 0644 "$UNIT_DIR"/skald-refresh.service "$UNIT_DIR"/skald-beacon.service "$UNIT_DIR"/skald-bot-policy.service
  if ! systemd_up; then
    warn "systemd is not running here: the units are installed but not started"
    return
  fi
  systemctl daemon-reload
  systemctl enable skald-refresh.service >/dev/null 2>&1
  systemctl restart skald-refresh.service
  # The beacon is optional (beacon.enabled, docs/BEACON.md): restarted only if it was switched on.
  if systemctl is-enabled --quiet skald-beacon.service 2>/dev/null; then
    systemctl restart skald-beacon.service
  fi
}

install_cron() {
  local hm cfg="$ETC/config.yml" tz site
  tz=$(sed -n 's/^  timezone: *//p' "$cfg" | head -n 1)
  site=$(sed -n 's/^  name: *//p' "$cfg" | head -n 1)
  # cron runs on the server's clock: the daily time in the site's zone, today, in server time.
  hm=$("$PY" - "$DAILY_AT" "${tz:-UTC}" <<'PY'
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
h, m = (int(x) for x in sys.argv[1].split(":"))
site = datetime.now(ZoneInfo(sys.argv[2])).replace(hour=h, minute=m, second=0, microsecond=0)
local = site.astimezone()
print(f"{local.minute} {local.hour}")
PY
) || die "--daily-at '$DAILY_AT': give HH:MM"
  local run="cd $APP && . $ETC/env &&"
  local ti="$PY $APP/bin/skald --config $cfg"
  say "writing $CRON_FILE (run-daily at $DAILY_AT ${tz:-UTC}, live every 2 minutes, nightly backup)"
  cat > "$CRON_FILE" <<EOF
# skald (install.sh). Server clock. Failures mail the daily recipients (notify-failure).
SHELL=/bin/sh
MAILTO=""
$hm * * * $SVC_USER $run $ti run-daily >>$LOGS/run.log 2>&1 || $ti notify-failure --job run-daily --exit \$? --log $LOGS/run.log >>$LOGS/run.log 2>&1
*/2 * * * * $SVC_USER $run flock -n $DATA/live.lock $ti live >>$LOGS/live.log 2>&1
30 4 * * * $SVC_USER $run $ti backup >>$LOGS/backup.log 2>&1 || $ti notify-failure --job backup --exit \$? --log $LOGS/backup.log >>$LOGS/backup.log 2>&1
# Heartbeat (DEPLOY.md section 5): list {agent: skald-heartbeat, label: heartbeat} in ours.user_agents first.
# */5 * * * * $SVC_USER curl -s -o /dev/null -A "skald-heartbeat" https://${site:-www.example.com}/robots.txt
EOF
  chmod 0644 "$CRON_FILE"
  cat > "$LOGROTATE_FILE" <<EOF
$LOGS/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF
  chmod 0644 "$LOGROTATE_FILE"
}

install_command() {
  say "installing the command $CMD_FILE (sudo $(basename "$CMD_FILE") check, live, run-daily, ...)"
  cat > "$CMD_FILE.new" <<EOF
#!/bin/sh
# The $(basename "$CMD_FILE") command (install.sh): $APP/bin/skald as the $SVC_USER user,
# with $ETC/config.yml and the env file. Run it with sudo.
if [ "\$(id -u)" = 0 ]; then exec runuser -u $SVC_USER -- "\$0" "\$@"; fi
if [ "\$(id -un)" != $SVC_USER ]; then
  echo "run it with sudo: it runs as the $SVC_USER user, who can read the config and the log" >&2
  exit 1
fi
cd $APP || exit 1
if [ -r $ETC/env ]; then . $ETC/env; fi
exec $PY $APP/bin/skald --config $ETC/config.yml "\$@"
EOF
  chmod 0755 "$CMD_FILE.new"
  mv -f "$CMD_FILE.new" "$CMD_FILE"
}

first_run() {
  [ "$FIRST_RUN" = 1 ] || return 0
  say "first run: check (today so far), then live"
  local cmd="cd $APP && . $ETC/env && $PY $APP/bin/skald --config $ETC/config.yml"
  if ! runuser -u "$SVC_USER" -- sh -c "$cmd check --day today"; then
    warn "check did not say ok. Is the log readable and in a known format? Fix $ETC/config.yml (logs:), then run:"
    warn "  sudo -u $SVC_USER sh -c '$cmd check --day today'"
    return 0
  fi
  runuser -u "$SVC_USER" -- sh -c "$cmd live" >/dev/null \
    || warn "live did not finish cleanly; see: sudo -u $SVC_USER sh -c '$cmd live'"
}

print_next_steps() {
  local site
  site=$(sed -n 's/^  name: *//p' "$ETC/config.yml" | head -n 1)
  cat <<EOF

Skald is installed.

  code      $APP            config  $ETC/config.yml   secrets  $ETC/env
  history   $DATA     dashboard  $WWW     logs  $LOGS

Next steps

1. Serve the dashboard. Simplest (one password for everyone), inside your site's
   HTTPS server { } block in nginx:

     location /traffic/ {
         alias $WWW/;
         auth_basic           "Traffic";
         auth_basic_user_file /etc/nginx/skald.htpasswd;  # htpasswd -B -c it
         access_log off;
         add_header X-Robots-Tag "noindex, nofollow, noarchive" always;
         add_header Cache-Control "private, no-cache" always;
         add_header Content-Security-Policy "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'" always;
     }

   Caddy, in your site's block:

     handle_path /traffic/* {
         root * $WWW
         basic_auth { reader <hash from: caddy hash-password> }
         file_server
     }

   Then: sudo nginx -t && sudo systemctl reload nginx   (or: sudo systemctl reload caddy)
   Accounts (each person signs in with their own email) instead of one password:
   DEPLOY.md, "Sessions mode": the nginx blocks, then
     sudo $(basename "$CMD_FILE") accounts init --org "Example Co" --owner-email owner@example.com

2. Mail: set the mail: section in $ETC/config.yml (host, from, to), the SMTP login in
   $ETC/env, and mail.daily / mail.weekly to true.

3. Open https://${site:-<your site>}/traffic/${site:-<site>}/ . The daily run fills the history
   from tomorrow; for the days the logs still hold now:
     sudo $(basename "$CMD_FILE") backfill --days 14

The command: sudo $(basename "$CMD_FILE") check | live | run-daily | version | --help
(it runs $APP/bin/skald as $SVC_USER with $ETC/config.yml).

Upgrade: run this script again. Remove: install.sh --uninstall [--purge]. docs/INSTALL.md has more.
EOF
}

main() {
  need_root "$@"
  if [ "$UNINSTALL" = 1 ]; then
    uninstall
    exit 0
  fi
  [ "$PURGE" = 0 ] || die "--purge goes with --uninstall"
  check_os
  install_packages
  make_user_and_dirs
  find_source
  install_code
  write_config
  write_env
  install_units
  install_cron
  install_command
  first_run
  print_next_steps
}

main "$@"
