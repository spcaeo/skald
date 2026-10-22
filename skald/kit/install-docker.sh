#!/bin/bash
# Skald log shipper for __SITE__: install it on this web server (Docker).
# Sends new lines of one access log to __HOST__ over HTTPS.
# Reads the log only; never touches nginx, Apache or the website. 128 MB of memory at most.
#
#   sudo bash install.sh            ask for the log file and the token, then start
#   sudo bash install.sh --dry-run  show what would run, change nothing
#
# The token is never in this file. It comes from, in this order: a file named ship-token
# next to this script (in the kit, or made by the admin; used, then deleted), the
# environment variable SKALD_SHIP_TOKEN, or pasted when asked. Either way it is kept in
# /srv/skald/ship-token (root:adm, 0640). check.sh reads /srv/skald/ship.conf (no token).
set -euo pipefail

SITE="__SITE__"
URL="__URL__"
HOST="__HOST__"
IMAGE="__IMAGE__"
SHIP_PATH="__SHIP_PATH__"
DASHBOARD="__DASHBOARD__"
HELP="__HELP__"
HERE="$(cd "$(dirname "$0")" && pwd)"
BASE=/srv/skald
NAME=skald-ship
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1

say() { printf '\n== %s\n' "$*"; }
run() { if [ "$DRY" = 1 ]; then printf '   would run: %s\n' "$*" >&2; else "$@"; fi; }
stop() { printf '\nStopped: %s\n' "$*" >&2; exit 1; }

case "$SITE" in *[!a-z0-9.-]*|"") stop "this copy has no site name; download the kit again" ;; esac
[ "$DRY" = 1 ] || [ "$(id -u)" = 0 ] || stop "run it with sudo: sudo bash install.sh"
command -v docker >/dev/null 2>&1 || stop "Docker is not installed. Ask us for the kit without Docker (systemd)."
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
[ -f "$LOG" ] || stop "$LOG does not exist"
LOGDIR="$(dirname "$LOG")"
echo "   using $LOG ($(wc -l < "$LOG" | tr -d ' ') lines now; only new lines will be sent)"

say "2. The token"
save_token() {   # $1 = the token; never printed
  if [ "$DRY" = 1 ]; then echo "   would save the token to $BASE/ship-token (root:adm, 0640)"; return; fi
  (umask 027; printf '%s\n' "$1" > "$BASE/ship-token")
  chgrp adm "$BASE/ship-token"
  echo "   token saved to $BASE/ship-token (root:adm, 0640)"
}
run install -d -m 0750 -o root -g adm "$BASE"
run install -d -m 0700 -o 10001 -g 4 "$BASE/ship-state"
if [ -s "$HERE/ship-token" ]; then
  echo "   this kit holds the token (the file ship-token); it is used, not shown"
  TOKEN="$(tr -d '[:space:]' < "$HERE/ship-token")"
  [ "${#TOKEN}" -ge 20 ] || stop "the file ship-token in this kit does not hold a token (too short)"
  save_token "$TOKEN"
  unset TOKEN
  if [ "$DRY" = 1 ]; then echo "   would delete the kit's copy: $HERE/ship-token"
  else rm -f "$HERE/ship-token"; echo "   the kit's copy ($HERE/ship-token) is deleted"; fi
elif [ -n "${SKALD_SHIP_TOKEN:-}" ]; then
  echo "   the token is in SKALD_SHIP_TOKEN; it is used, not shown"
  TOKEN="$(printf '%s' "$SKALD_SHIP_TOKEN" | tr -d '[:space:]')"
  [ "${#TOKEN}" -ge 20 ] || stop "SKALD_SHIP_TOKEN does not hold a token (too short)"
  save_token "$TOKEN"
  unset TOKEN SKALD_SHIP_TOKEN
else
  KEEP=n
  if [ -s "$BASE/ship-token" ]; then
    read -r -p "A token is already saved. Keep it? [Y/n]: " KEEP || true
    KEEP="${KEEP:-Y}"
  fi
  if [ "$KEEP" = n ] || [ "$KEEP" = N ]; then
    echo "   This kit has no token: it was sent to you separately. It is not shown as you paste it."
    TOKEN=""
    read -r -s -p "Paste the token, then press Enter: " TOKEN || true; echo
    TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]')"
    [ -n "$TOKEN" ] || stop "no token given. Paste it when asked, or see README.txt (a file named ship-token next to install.sh, or SKALD_SHIP_TOKEN)"
    [ "${#TOKEN}" -ge 20 ] || stop "that does not look like a token (too short)"
    save_token "$TOKEN"
    unset TOKEN
  fi
fi
if [ "$DRY" = 1 ]; then echo "   would write $BASE/ship.conf (the log file and send address, no token) for check.sh"
else
  (umask 027; printf 'METHOD=docker\nLOG=%s\nURL=%s\nSITE=%s\n' "$LOG" "$URL" "$SITE" > "$BASE/ship.conf")
  chgrp adm "$BASE/ship.conf"; chmod 0640 "$BASE/ship.conf"
fi

say "3. Start the shipper"
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx "$NAME"; then
  echo "   an older $NAME is there; it is replaced (its position is kept in $BASE/ship-state)"
  run docker rm -f "$NAME" >/dev/null
fi
run docker pull -q "$IMAGE" >/dev/null
run docker run -d --name "$NAME" --restart unless-stopped --memory 128m \
  --user 10001:4 --no-healthcheck --entrypoint python3 \
  -v "$LOGDIR:$LOGDIR:ro" \
  -v "$BASE/ship-token:/run/skald-ship/token:ro" \
  -v "$BASE/ship-state:/state" \
  "$IMAGE" "$SHIP_PATH" \
  --url "$URL" --token-file /run/skald-ship/token \
  --log "$LOG" --state /state/state.json --from-end >/dev/null

say "4. Check"
if [ "$DRY" = 1 ]; then echo "   would wait 20 s and show: docker logs --tail 20 $NAME"; exit 0; fi
echo "   waiting 20 seconds for the first batch..."
sleep 20
docker logs --tail 20 "$NAME" 2>&1 | sed 's/^/   /'
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
