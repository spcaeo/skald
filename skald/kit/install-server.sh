#!/bin/bash
# Skald log shipper for __SITE__: one file that installs it on this web server.
# Sends new lines of the site's access log to __HOST__ over HTTPS.
# Reads the log only; never touches nginx, Apache or the website.
#
#   curl -fsSL <install link> | sudo bash             the one-command install
#   sudo bash skald-install-__SITE__.sh                  this file, downloaded
#   sudo bash skald-install-__SITE__.sh --dry-run        show what would run, change nothing
#
# Options (piped: curl -fsSL <link> | sudo bash -s -- --log /var/log/nginx/x.log):
#   --log <path>   the site's access log. Without it, the log is found in nginx's or
#                  Apache's settings (the server block that answers for the site)
#   --yes          ask nothing: take what was found
#   --dry-run      show every step, change nothing
#
# The shipper runs with Docker when Docker works here and this file names the image;
# else as a systemd service with Python 3.9 or newer (the shipper is inside this file).
# A shipper installed before keeps its way and its place in the log: running this again
# is safe. The token is inside this file when it was made with one (it is never shown),
# else in SKALD_SHIP_TOKEN, else it is asked for (hidden). It is kept as the kits keep it:
#   Docker   /srv/skald/ship-token      root:adm, 0640
#   systemd  /etc/skald-ship/token      root:skald-ship, 0640
# It leaves two commands: sudo skald-ship-check (changes nothing) and
# sudo skald-ship-uninstall (removes only what this made).
#
# For tests only; leave these unset on a real server:
#   SKALD_INSTALL_ROOT  a folder put in front of the web server's settings and logs it reads
#   SKALD_TTY           where answers are read from (default /dev/tty)
set -euo pipefail

SITE="__SITE__"
URL="__URL__"
HOST="__HOST__"
IMAGE="__IMAGE__"
SHIP_PATH="__SHIP_PATH__"
DASHBOARD="__DASHBOARD__"
HELP="__HELP__"
KIT_TOKEN='__TOKEN__'
R="${SKALD_INSTALL_ROOT:-}"
TTY="${SKALD_TTY:-/dev/tty}"
CHECK_BIN=/usr/local/bin/skald-ship-check
UNDO_BIN=/usr/local/bin/skald-ship-uninstall
NAME=skald-ship
DRY=0
YES=0
LOG=""
ASK=0

say() { printf '\n== %s\n' "$*"; }
run() { if [ "$DRY" = 1 ]; then printf '   would run: %s\n' "$*" >&2; else "$@"; fi; }
stop() { printf '\nStopped: %s\n' "$*" >&2; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }
fsize() { stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null || echo 0; }

# One answer from the person at the keyboard (the terminal, not the pipe the script
# arrives on). $1 the question, $2 the answer when nobody can be asked. Sets ANSWER.
ask() {
  ANSWER=""
  if [ "$ASK" = 1 ]; then read -r -u 3 -p "$1" ANSWER || true; fi
  ANSWER="${ANSWER:-${2:-}}"
}

# ------------------------------------------------------------- the embedded files

shipper_b64() {
cat <<'SKALD_SHIPPER_EOF'
__SHIPPER_B64__
SKALD_SHIPPER_EOF
}

check_text() {
cat <<'SKALD_CHECK_EOF'
__CHECK_SCRIPT__
SKALD_CHECK_EOF
}

uninstall_text() {
cat <<'SKALD_UNINSTALL_EOF'
__UNINSTALL_SCRIPT__
SKALD_UNINSTALL_EOF
}

# ------------------------------------------------------------- finding the log

# The access_log files of nginx's server blocks whose server_name is the site,
# www.<site> or .<site>; a block with none writes the http block's (or nginx's own).
nginx_logs() {
  local files=() f
  for f in "$R"/etc/nginx/nginx.conf "$R"/etc/nginx/conf.d/*.conf "$R"/etc/nginx/sites-enabled/*; do
    [ -f "$f" ] && files+=("$f")
  done
  [ "${#files[@]}" -gt 0 ] || return 0
  awk -v site="$SITE" -v sq="'" '
    function emit(   m, j, a, hit) {
      m = split(names, a, " ")
      for (j = 1; j <= m; j++)
        if (a[j] == site || a[j] == "www." site || a[j] == "." site || a[j] == "*." site) hit = 1
      if (!hit) return
      if (logs == "") { out[++k] = "DEFAULT"; return }
      m = split(logs, a, " ")
      for (j = 1; j <= m; j++) out[++k] = a[j]
    }
    FNR == 1 { depth = 0; sdepth = 0; n = 0 }
    {
      line = $0
      sub(/#.*/, "", line)
      gsub(/[{]/, " { ", line); gsub(/[}]/, " } ", line); gsub(/;/, " ; ", line)
      c = split(line, t, /[ \t]+/)
      for (i = 1; i <= c; i++) {
        w = t[i]
        if (w == "") continue
        if (w == "{") {
          if (n >= 1 && st[1] == "server" && sdepth == 0) { sdepth = depth + 1; names = ""; logs = "" }
          depth++; n = 0; continue
        }
        if (w == "}") {
          if (sdepth > 0 && depth == sdepth) { emit(); sdepth = 0 }
          depth--; n = 0; continue
        }
        if (w == ";") {
          if (n >= 2 && st[1] == "server_name" && sdepth > 0 && depth == sdepth)
            for (j = 2; j <= n; j++) names = names " " tolower(st[j])
          if (n >= 2 && st[1] == "access_log") {
            p = st[2]; gsub(/"/, "", p); gsub(sq, "", p)
            if (sdepth > 0 && depth == sdepth) logs = logs " " p
            else if (sdepth == 0) http = p
          }
          n = 0; continue
        }
        st[++n] = w
      }
    }
    END {
      for (j = 1; j <= k; j++) {
        p = out[j]
        if (p == "DEFAULT") p = (http != "" ? http : "/var/log/nginx/access.log")
        print p
      }
    }' "${files[@]}" 2>/dev/null || true
}

# The CustomLog (or TransferLog) files of Apache's <VirtualHost> blocks whose
# ServerName or ServerAlias is the site, www.<site> or *.<site>.
apache_logs() {
  local files=() f
  for f in "$R"/etc/apache2/sites-enabled/* "$R"/etc/httpd/conf.d/*.conf "$R"/etc/httpd/conf/httpd.conf; do
    [ -f "$f" ] && files+=("$f")
  done
  [ "${#files[@]}" -gt 0 ] || return 0
  awk -v site="$SITE" '
    function emit(   m, j, a, hit) {
      m = split(names, a, " ")
      for (j = 1; j <= m; j++) {
        sub(/:[0-9]+$/, "", a[j])
        if (a[j] == site || a[j] == "www." site || a[j] == "*." site) hit = 1
      }
      if (!hit) return
      m = split(logs, a, " ")
      for (j = 1; j <= m; j++) print a[j]
    }
    FNR == 1 { inv = 0 }
    {
      line = $0
      sub(/^[ \t]+/, "", line)
      if (line ~ /^#/) next
      low = tolower(line)
      if (low ~ /^<virtualhost/) { inv = 1; names = ""; logs = ""; next }
      if (low ~ /^<\/virtualhost/) { if (inv) emit(); inv = 0; next }
      if (!inv) next
      if (low ~ /^(servername|serveralias)[ \t]/) {
        c = split(low, t, /[ \t]+/)
        for (j = 2; j <= c; j++) names = names " " t[j]
      }
      if (low ~ /^(customlog|transferlog)[ \t]/) {
        split(line, t, /[ \t]+/); p = t[2]; gsub(/"/, "", p)
        if (p !~ /^\|/) logs = logs " " p
      }
    }' "${files[@]}" 2>/dev/null || true
}

# Each found path as a file on this server: Apache's ${APACHE_LOG_DIR} and httpd's
# relative paths made whole, nginx's $host tried as the site and www.<site>.
log_files() {
  local p q name ald=/var/log/apache2
  { nginx_logs; apache_logs; } | while IFS= read -r p; do
    case "$p" in off|syslog:*|"") continue ;; esac
    p="${p//'${APACHE_LOG_DIR}'/$ald}"
    case "$p" in /*) ;; *) p="/etc/httpd/$p" ;; esac
    case "$p" in
      *'$'*)
        for name in "$SITE" "www.$SITE"; do
          q="${p//'${host}'/$name}"; q="${q//'$host'/$name}"; q="${q//'$server_name'/$name}"
          case "$q" in *'$'*) ;; *) [ -f "$R$q" ] && printf '%s\n' "$R$q" ;; esac
        done ;;
      *) [ -f "$R$p" ] && printf '%s\n' "$R$p" ;;
    esac
  done | awk '!seen[$0]++'
}

pick_log() {
  local found=() f n i best=1 size top=-1
  if [ -n "$LOG" ]; then echo "   the log given with --log: $LOG"; return; fi
  while IFS= read -r f; do found+=("$f"); done < <(log_files)
  n="${#found[@]}"
  if [ "$n" = 1 ]; then
    LOG="${found[0]}"
    echo "   found in the web server's settings: $LOG"
    return
  fi
  if [ "$n" -gt 1 ]; then
    echo "   the web server's settings name $n access logs for ${SITE}:"
    for ((i = 1; i <= n; i++)); do
      size="$(fsize "${found[$((i - 1))]}")"
      printf '   %s) %s (%s bytes)\n' "$i" "${found[$((i - 1))]}" "$size"
      if [ "$size" -gt "$top" ]; then top="$size"; best="$i"; fi
    done
    ask "Which one is the site's access log? [${best}]: " "$best"
    case "$ANSWER" in /*) LOG="$ANSWER" ;;
      *[!0-9]*|"") stop "answer with a number from the list, or a full path" ;;
      *) [ "$ANSWER" -ge 1 ] && [ "$ANSWER" -le "$n" ] || stop "answer with a number from 1 to $n"
         LOG="${found[$((ANSWER - 1))]}" ;;
    esac
    [ "$ASK" = 1 ] || echo "   took the biggest: $LOG (to use another: run this again with --log <path>)"
    return
  fi
  local guess=""
  for f in "/var/log/nginx/www.${SITE}.access.log" "/var/log/nginx/${SITE}.access.log" \
           "/var/log/nginx/access.log" "/var/log/apache2/access.log" "/var/log/httpd/access_log"; do
    if [ -f "$R$f" ]; then guess="$R$f"; break; fi
  done
  echo "   no server block of nginx or Apache names ${SITE}."
  if [ -z "$guess" ] && [ "$ASK" = 0 ]; then
    stop "the access log of ${SITE} was not found. Run this again with --log <full path of the log>"
  fi
  ask "Full path of the access log for ${SITE} [${guess}]: " "$guess"
  LOG="$ANSWER"
  [ "$ASK" = 1 ] || echo "   took the usual place: $LOG (to use another: run this again with --log <path>)"
}

# ------------------------------------------------------------- the two ways

python_ok() {
  has python3 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null
}
docker_ok() { [ -n "$IMAGE" ] && [ -n "$SHIP_PATH" ] && has docker && docker info >/dev/null 2>&1; }
systemd_ok() { [ "$(shipper_b64 | wc -c)" -gt 100 ] && has systemctl && python_ok; }
had_docker() { has docker && docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$NAME"; }
had_systemd() { [ -f /etc/systemd/system/skald-ship.service ]; }

choose_method() {
  if had_systemd && systemd_ok; then METHOD=systemd; WHY="installed this way before"
  elif had_docker && docker_ok; then METHOD=docker; WHY="installed this way before"
  elif docker_ok; then METHOD=docker; WHY="Docker works here"
  elif systemd_ok; then METHOD=systemd; WHY="no Docker; Python $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])') and systemd are here"
  else
    local need="Python 3.9 or newer with systemd"
    [ -n "$IMAGE" ] && need="Docker (https://docs.docker.com/engine/install/), or $need"
    has python3 && ! python_ok && need="$need (this server has an older Python)"
    stop "this server can run the shipper in no way it knows. Install $need, then run this again."
  fi
}

save_token() {   # $1 = the token, $2 = the file, $3 = its group; never printed
  if [ "$DRY" = 1 ]; then echo "   would save the token to $2 (root:$3, 0640)"; return; fi
  (umask 027; printf '%s\n' "$1" > "$2")
  chgrp "$3" "$2"
  echo "   token saved to $2 (root:$3, 0640)"
}

token_step() {   # $1 = the token file, $2 = its group
  local token=""
  if [ -n "$KIT_TOKEN" ]; then
    echo "   this file holds the token; it is used, not shown"
    token="$KIT_TOKEN"
  elif [ -n "${SKALD_SHIP_TOKEN:-}" ]; then
    echo "   the token is in SKALD_SHIP_TOKEN; it is used, not shown"
    token="$(printf '%s' "$SKALD_SHIP_TOKEN" | tr -d '[:space:]')"
    unset SKALD_SHIP_TOKEN
  else
    if [ -s "$1" ]; then
      ask "A token is already saved. Keep it? [Y/n]: " Y
      case "$ANSWER" in n|N|no|No) ;; *) echo "   the saved token is kept"; return ;; esac
    fi
    [ "$ASK" = 1 ] || stop "no token. Run it with SKALD_SHIP_TOKEN set (sudo SKALD_SHIP_TOKEN=... bash), or where it can ask you"
    echo "   It is not shown as you paste it."
    read -r -s -u 3 -p "Paste the sending token, then press Enter: " token || true; echo
    token="$(printf '%s' "$token" | tr -d '[:space:]')"
    [ -n "$token" ] || stop "no token given"
  fi
  case "$token" in skald_*) ;; *) stop "that is not a Skald sending token (it starts with skald_)" ;; esac
  [ "${#token}" -ge 20 ] || stop "that does not look like a token (too short)"
  save_token "$token" "$1" "$2"
}

write_tools() {   # skald-ship-check and skald-ship-uninstall, for the way used
  if [ "$DRY" = 1 ]; then
    echo "   would write $CHECK_BIN and $UNDO_BIN (0755)"
    return
  fi
  check_text | sed "s/@@METHOD@@/$METHOD/" > "$CHECK_BIN"
  uninstall_text | sed "s/@@METHOD@@/$METHOD/" > "$UNDO_BIN"
  chmod 0755 "$CHECK_BIN" "$UNDO_BIN"
  echo "   wrote $CHECK_BIN and $UNDO_BIN"
}

write_conf() {   # $1 = the settings file, $2 = its group (no token in it)
  if [ "$DRY" = 1 ]; then echo "   would write $1 (the log file and send address, no token)"; return; fi
  (umask 027; printf 'METHOD=%s\nLOG=%s\nURL=%s\nSITE=%s\n' "$METHOD" "$LOG" "$URL" "$SITE" > "$1")
  chgrp "$2" "$1"; chmod 0640 "$1"
}

install_docker() {
  local base=/srv/skald logdir
  logdir="$(dirname "$LOG")"
  if had_systemd; then
    echo "   the systemd shipper is stopped and removed, so only one sends"
    run systemctl disable --now skald-ship
    run rm -f /etc/systemd/system/skald-ship.service
  fi
  say "3. The token"
  run install -d -m 0750 -o root -g adm "$base"
  run install -d -m 0700 -o 10001 -g 4 "$base/ship-state"
  token_step "$base/ship-token" adm
  write_conf "$base/ship.conf" adm
  say "4. Start the shipper (Docker)"
  if had_docker; then
    echo "   the old $NAME is replaced (its place in the log is kept in $base/ship-state)"
    run docker rm -f "$NAME" >/dev/null
  fi
  run docker pull -q "$IMAGE" >/dev/null
  run docker run -d --name "$NAME" --restart unless-stopped --memory 128m \
    --user 10001:4 --no-healthcheck --entrypoint python3 \
    -v "$logdir:$logdir:ro" \
    -v "$base/ship-token:/run/skald-ship/token:ro" \
    -v "$base/ship-state:/state" \
    "$IMAGE" "$SHIP_PATH" \
    --url "$URL" --token-file /run/skald-ship/token \
    --log "$LOG" --state /state/state.json --from-end >/dev/null
  write_tools
  SHOW_LOG="docker logs --tail 20 $NAME"
}

unit_text() {
cat <<EOF
[Unit]
Description=Ship the access log to Skald
After=network-online.target
Wants=network-online.target

[Service]
# The user's own group reads the token; its membership of adm reads the log.
User=skald-ship
ExecStart=/usr/local/bin/skald-ship \\
    --url $URL \\
    --token-file /etc/skald-ship/token \\
    --log $LOG \\
    --state /var/lib/skald-ship/state.json \\
    --from-end
Restart=always
RestartSec=5
StateDirectory=skald-ship
StateDirectoryMode=0700
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=$HOME_RULE
PrivateTmp=true
PrivateDevices=true
ReadOnlyPaths=/var/log /etc/skald-ship
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SystemCallFilter=@system-service

[Install]
WantedBy=multi-user.target
EOF
}

install_systemd() {
  local conf=/etc/skald-ship unit=/etc/systemd/system/skald-ship.service tmp nologin
  case "$LOG" in *[[:space:]]*) stop "the log's path has a space in it; give the log a name without spaces" ;; esac
  if had_docker; then
    echo "   the Docker shipper is removed, so only one sends"
    run docker rm -f "$NAME" >/dev/null
  fi
  say "3. The program and its user"
  tmp="$(mktemp)"
  if ! { shipper_b64 | base64 -d > "$tmp" 2>/dev/null || shipper_b64 | python3 -c \
         'import base64, sys; sys.stdout.buffer.write(base64.b64decode(sys.stdin.read()))' > "$tmp"; }; then
    rm -f "$tmp"; stop "the shipper inside this file could not be unpacked; download it again"
  fi
  python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$tmp" 2>/dev/null \
    || { rm -f "$tmp"; stop "the shipper inside this file is damaged; download it again"; }
  run install -m 0755 "$tmp" /usr/local/bin/skald-ship
  rm -f "$tmp"
  if id skald-ship >/dev/null 2>&1; then
    echo "   the user skald-ship is there already; it is put in group adm"
    run usermod -a -G adm skald-ship
  else
    nologin="$(command -v nologin 2>/dev/null || echo /usr/sbin/nologin)"
    run useradd --system --no-create-home --shell "$nologin" --groups adm skald-ship
  fi
  run install -d -m 0750 -o root -g skald-ship "$conf"
  say "4. The token"
  token_step "$conf/token" skald-ship
  write_conf "$conf/ship.conf" skald-ship
  say "5. The service"
  HOME_RULE=true
  case "$LOG" in /home/*|/root/*) HOME_RULE=read-only ;; esac
  if [ "$DRY" = 1 ]; then
    echo "   would write $unit:"
    unit_text | sed 's/^/      /'
  else
    unit_text > "$unit"
    chmod 0644 "$unit"
    echo "   wrote $unit (the old one, if any, is replaced; its place in the log is kept)"
  fi
  run systemctl daemon-reload
  run systemctl enable --now skald-ship
  run systemctl restart skald-ship
  write_tools
  SHOW_LOG="journalctl -u skald-ship -n 20 -o cat"
}

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --dry-run) DRY=1 ;;
      --yes|-y) YES=1 ;;
      --log) [ $# -ge 2 ] || stop "--log needs the full path of the access log"; LOG="$2"; shift ;;
      --log=*) LOG="${1#--log=}" ;;
      -h|--help)
        echo "Installs the Skald log shipper for ${SITE}. Options: --log <path>, --yes, --dry-run."
        echo "Help: ${HELP}"; exit 0 ;;
      *) stop "unknown option $1 (the options are --log <path>, --yes and --dry-run)" ;;
    esac
    shift
  done
  case "$SITE" in *[!a-z0-9.-]*|"") stop "this copy has no site name; download it again" ;; esac
  [ "$DRY" = 1 ] || [ "$(id -u)" = 0 ] || stop "run it with sudo (curl -fsSL <link> | sudo bash, or sudo bash this-file)"
  if [ "$YES" = 0 ] && ( exec 3<"$TTY" ) 2>/dev/null; then exec 3<"$TTY"; ASK=1; fi
  [ "$DRY" = 1 ] && echo "Dry run: nothing is changed."
  echo "Skald: installing the log shipper for ${SITE}."

  say "1. How it runs here"
  METHOD=""; WHY=""
  choose_method
  echo "   with ${METHOD} (${WHY})"

  say "2. The access log of ${SITE}"
  pick_log
  [ -n "$LOG" ] || stop "no log file given"
  case "$LOG" in /*) ;; *) stop "give the full path, starting with /" ;; esac
  [ -f "$LOG" ] || stop "$LOG does not exist"
  echo "   using $LOG ($(wc -l < "$LOG" | tr -d ' ') lines now; only new lines will be sent)"

  SHOW_LOG=""
  if [ "$METHOD" = docker ]; then install_docker; else install_systemd; fi

  say "Check"
  if [ "$DRY" = 1 ]; then echo "   would wait 20 s and show: $SHOW_LOG"; exit 0; fi
  echo "   waiting 20 seconds for the first batch..."
  sleep 20
  $SHOW_LOG 2>&1 | tail -n 20 | sed 's/^/   /' || true
  cat <<EOF

Done. The shipper for ${SITE} runs with ${METHOD} and sends to ${HOST}.
  1. Open https://${SITE}/ once in a browser.
  2. Within a few minutes the visit shows on ${DASHBOARD}
Lines with "401" or "403" above mean the token is wrong: run this again with a new one.
If something seems wrong: sudo skald-ship-check  (it changes nothing; send us its last block)
Undo at any time: sudo skald-ship-uninstall
Help: ${HELP}
EOF
}

main "$@"
