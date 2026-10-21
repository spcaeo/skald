#!/bin/bash
# Skald log shipper for __SITE__: install it on this web server as a systemd service (no Docker).
# Sends new lines of one access log to __HOST__ over HTTPS.
# Reads the log only; never touches nginx, Apache or the website. Needs Python 3.9 or newer.
#
#   sudo bash install.sh            ask for the log file and the token, then start
#   sudo bash install.sh --dry-run  show what would run, change nothing
#
# It installs skald-ship.py (next to this script) as /usr/local/bin/skald-ship, a system user
# skald-ship in group adm (adm may read the web server's logs), /etc/skald-ship/token
# (root:skald-ship, 0640) and /etc/systemd/system/skald-ship.service.
# The token is never in this file. If a file named ship-token sits next to this script, it is
# used and then deleted; otherwise it is pasted when asked. check.sh reads
# /etc/skald-ship/ship.conf (no token).
set -euo pipefail

SITE="__SITE__"
URL="__URL__"
HOST="__HOST__"
DASHBOARD="__DASHBOARD__"
HELP="__HELP__"
HERE="$(cd "$(dirname "$0")" && pwd)"
BIN=/usr/local/bin/skald-ship
CONF=/etc/skald-ship
UNIT=/etc/systemd/system/skald-ship.service
USER_NAME=skald-ship
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

say() { printf '\n== %s\n' "$*"; }
run() { if [ "$DRY" = 1 ]; then printf '   would run: %s\n' "$*" >&2; else "$@"; fi; }
stop() { printf '\nStopped: %s\n' "$*" >&2; exit 1; }

case "$SITE" in *[!a-z0-9.-]*|"") stop "this copy has no site name; download the kit again" ;; esac
[ "$DRY" = 1 ] || [ "$(id -u)" = 0 ] || stop "run it with sudo: sudo bash install.sh"
[ -f "$HERE/skald-ship.py" ] || stop "skald-ship.py is missing from this folder; unpack the whole kit again"
command -v systemctl >/dev/null 2>&1 || stop "this server has no systemd. Ask us for the Docker kit instead."
command -v python3 >/dev/null 2>&1 || stop "Python 3 is not installed. skald-ship needs Python 3.9 or newer (or ask us for the Docker kit)."
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo unknown)"
  stop "skald-ship needs Python 3.9 or newer; this server has Python $PYV. Ask us for the Docker kit instead."
fi
[ "$DRY" = 1 ] && echo "Dry run: nothing is changed."

say "1. The access log of ${SITE}"
echo "nginx or Apache writes these access logs (file, then the host-name lines of its settings):"
grep -rnE "access_log|server_name|CustomLog|ServerName|ServerAlias" \
  /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ /etc/apache2/sites-enabled/ /etc/httpd/conf.d/ 2>/dev/null \
  | grep -vE ':[[:space:]]*#' | sed 's/^/   /' | head -40 || true
GUESS=""
for f in "/var/log/nginx/www.${SITE}.access.log" "/var/log/nginx/${SITE}.access.log" \
         "/var/log/nginx/access.log" "/var/log/apache2/access.log" "/var/log/httpd/access_log"; do
  if [ -f "$f" ]; then GUESS="$f"; break; fi
done
LOG=""
read -r -p "Full path of the access log for ${SITE} [${GUESS}]: " LOG || true
LOG="${LOG:-$GUESS}"
[ -n "$LOG" ] || stop "no log file given"
case "$LOG" in /*) ;; *) stop "give the full path, starting with /" ;; esac
case "$LOG" in *[[:space:]]*) stop "the path has a space in it; give the log a name without spaces" ;; esac
[ -f "$LOG" ] || stop "$LOG does not exist"
echo "   using $LOG ($(wc -l < "$LOG" | tr -d ' ') lines now; only new lines will be sent)"

say "2. The program and its user"
run install -m 0755 "$HERE/skald-ship.py" "$BIN"
if id "$USER_NAME" >/dev/null 2>&1; then
  echo "   the user $USER_NAME is there already; it is put in group adm"
  run usermod -a -G adm "$USER_NAME"
else
  NOLOGIN="$(command -v nologin 2>/dev/null || echo /usr/sbin/nologin)"
  run useradd --system --no-create-home --shell "$NOLOGIN" --groups adm "$USER_NAME"
fi
run install -d -m 0750 -o root -g "$USER_NAME" "$CONF"

say "3. The token"
save_token() {   # $1 = the token; never printed
  if [ "$DRY" = 1 ]; then echo "   would save the token to $CONF/token (root:$USER_NAME, 0640)"; return; fi
  (umask 027; printf '%s\n' "$1" > "$CONF/token")
  chgrp "$USER_NAME" "$CONF/token"
  echo "   token saved to $CONF/token (root:$USER_NAME, 0640)"
}
if [ -s "$HERE/ship-token" ]; then
  echo "   this kit holds the token (the file ship-token); it is used, not shown"
  TOKEN="$(tr -d '[:space:]' < "$HERE/ship-token")"
  [ "${#TOKEN}" -ge 20 ] || stop "the file ship-token in this kit does not hold a token (too short)"
  save_token "$TOKEN"
  unset TOKEN
  if [ "$DRY" = 1 ]; then echo "   would delete the kit's copy: $HERE/ship-token"
  else rm -f "$HERE/ship-token"; echo "   the kit's copy ($HERE/ship-token) is deleted"; fi
else
  KEEP=n
  if [ -s "$CONF/token" ]; then
    read -r -p "A token is already saved. Keep it? [Y/n]: " KEEP || true
    KEEP="${KEEP:-Y}"
  fi
  if [ "$KEEP" = n ] || [ "$KEEP" = N ]; then
    echo "   The token is sent to you separately. It is not shown as you paste it."
    TOKEN=""
    read -r -s -p "Paste the token, then press Enter: " TOKEN || true; echo
    TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]')"
    [ "${#TOKEN}" -ge 20 ] || stop "that does not look like a token (too short)"
    save_token "$TOKEN"
    unset TOKEN
  fi
fi
if [ "$DRY" = 1 ]; then echo "   would write $CONF/ship.conf (the log file and send address, no token) for check.sh"
else
  (umask 027; printf 'METHOD=systemd\nLOG=%s\nURL=%s\nSITE=%s\n' "$LOG" "$URL" "$SITE" > "$CONF/ship.conf")
  chgrp "$USER_NAME" "$CONF/ship.conf"; chmod 0640 "$CONF/ship.conf"
fi

say "4. The service"
HOME_RULE=true
case "$LOG" in /home/*|/root/*) HOME_RULE=read-only ;; esac
unit_text() {
cat <<EOF
[Unit]
Description=Ship the access log to Skald
After=network-online.target
Wants=network-online.target

[Service]
# The user's own group reads the token; its membership of adm reads the log.
User=$USER_NAME
ExecStart=$BIN \\
    --url $URL \\
    --token-file $CONF/token \\
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
ReadOnlyPaths=/var/log $CONF
CapabilityBoundingSet=
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SystemCallFilter=@system-service

[Install]
WantedBy=multi-user.target
EOF
}
if [ "$DRY" = 1 ]; then
  echo "   would write $UNIT:"
  unit_text | sed 's/^/      /'
else
  unit_text > "$UNIT"
  chmod 0644 "$UNIT"
  echo "   wrote $UNIT"
fi
run systemctl daemon-reload
run systemctl enable --now skald-ship
run systemctl restart skald-ship

say "5. Check"
if [ "$DRY" = 1 ]; then echo "   would wait 20 s and show: journalctl -u skald-ship -n 20 -o cat"; exit 0; fi
echo "   waiting 20 seconds for the first batch..."
sleep 20
journalctl -u skald-ship -n 20 -o cat 2>&1 | sed 's/^/   /'
cat <<EOF

Done. Now please:
  1. Open https://${SITE}/ once in a browser.
  2. Within a few minutes the visit shows on ${DASHBOARD}
If something seems wrong: sudo bash check.sh  (it changes nothing; send us its last block)
Lines with "401" or "403" above mean the token is wrong: run this again and paste a new one.
It needs outbound HTTPS (port 443) to ${HOST}.
Help: ${HELP}
Undo at any time: sudo bash uninstall.sh
EOF
