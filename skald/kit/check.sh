#!/bin/bash
# Skald log shipper for __SITE__: check that it works. It changes nothing.
#
#   sudo bash check.sh
#
# One line per check: "✓ OK" or "✗ PROBLEM" with a fix under it. At the end, a block to copy
# and send us. That block holds no token and no IP address. Exit 0 when all is OK, else 1.
# "! ADVICE" is a change that makes the figures better (a Next.js site whose log does not
# record the prefetch header): it does not count as a problem and never changes the exit.
#
# For tests only; leave these unset on a real server:
#   SKALD_CHECK_ROOT   a folder put in front of every absolute path this script reads
#                      (/srv/skald, /etc/..., /var/lib/..., /var/log/...); when set, the
#                      sudo check is skipped
#   SKALD_CHECK_WAIT   seconds between two reads of the log's size (default 3)
#   SKALD_CHECK_OWNER  the token file's expected owner (default root)
#   SKALD_CHECK_GROUP  the token file's expected group (default adm for Docker,
#                      skald-ship for systemd)
# Works with bash 3.2 and both GNU and BSD tools.
set -u

METHOD="__METHOD__"
SITE="__SITE__"
URL="__URL__"
HOST="__HOST__"
HELP="__HELP__"

R="${SKALD_CHECK_ROOT:-}"
WAIT="${SKALD_CHECK_WAIT:-3}"
case "$WAIT" in ''|*[!0-9]*) WAIT=3 ;; esac
NAME=skald-ship
if [ "$METHOD" = docker ]; then
  CONF=/srv/skald/ship.conf; TOKEN_FILE=/srv/skald/ship-token
  STATE=/srv/skald/ship-state/state.json; GROUP_DEFAULT=adm
  RESTART_CMD="sudo docker restart skald-ship"
else
  CONF=/etc/skald-ship/ship.conf; TOKEN_FILE=/etc/skald-ship/token
  STATE=/var/lib/skald-ship/state.json; GROUP_DEFAULT=skald-ship
  RESTART_CMD="sudo systemctl restart skald-ship"
fi
UNIT=/etc/systemd/system/skald-ship.service
WANT_OWNER="${SKALD_CHECK_OWNER:-root}"
WANT_GROUP="${SKALD_CHECK_GROUP:-$GROUP_DEFAULT}"
YES='✓ OK  '
NO='✗ PROBLEM  '
MAYBE='? CANNOT TELL  '
TIP='! ADVICE  '
# Next.js: the field that records its prefetch header, for nginx and for Apache. Single
# quotes: these are the log_format words, not shell variables.
NEXT_NGINX=' rsc_prefetch=$http_next_router_prefetch'
NEXT_APACHE=' rsc_prefetch=%{Next-Router-Prefetch}i'

PROBLEMS=0
SUMMARY=""
REASONS=""
LOG=""
LOG_GROWING=0
LOG_SIZE="unknown"

p() { printf '%s%s' "$R" "$1"; }          # a path as this script reads it
ok() { printf '%s%s\n' "$YES" "$1"; SUMMARY="${SUMMARY}OK       $1
"; }
problem() {
  printf '%s%s\n  fix: %s\n' "$NO" "$1" "$2"
  PROBLEMS=$((PROBLEMS + 1))
  SUMMARY="${SUMMARY}PROBLEM  $1
"
}
advice() {
  printf '%s%s\n  fix: %s\n' "$TIP" "$1" "$2"
  SUMMARY="${SUMMARY}ADVICE   $1
"
}
unsure() {
  printf '%s%s\n' "$MAYBE" "$1"
  [ -n "${2:-}" ] && printf '  fix: %s\n' "$2"
  SUMMARY="${SUMMARY}UNSURE   $1
"
}
has() { command -v "$1" >/dev/null 2>&1; }
fsize() { stat -c %s "$1" 2>/dev/null || stat -f %z "$1" 2>/dev/null; }
fmtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null; }
fmode() { local m; m="$(stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1" 2>/dev/null)"
          m="000$m"; printf '%s' "${m: -3}"; }
fowner() { stat -c %U "$1" 2>/dev/null || stat -f %Su "$1" 2>/dev/null; }
fgroup() { stat -c %G "$1" 2>/dev/null || stat -f %Sg "$1" 2>/dev/null; }
conf_get() { sed -n "s/^$1=//p" "$(p "$CONF")" 2>/dev/null | head -1; }
minutes_since() { echo $(( ( $(date +%s) - $1 ) / 60 )); }
count() { printf '%s\n' "$SHIP_LINES" | grep -ciE "$1"; }

# Masks every IPv4 and IPv6 address, so nothing printed here can show one.
mask() {
  sed -E -e 's/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/x.x.x.x/g' \
         -e 's/[0-9A-Fa-f]{0,4}::[0-9A-Fa-f:.]*/x:x::x/g' \
         -e 's/([0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}/x:x::x/g'
}

# ---------------------------------------------------------------- 1. Docker
check_docker() {
  [ "$METHOD" = docker ] || return 0
  if ! has docker; then
    problem "Docker is not installed" "install Docker, or ask us for the kit without Docker (systemd)"
  elif docker info >/dev/null 2>&1; then
    ok "Docker is installed and running"
  else
    problem "Docker is installed but not running" "start it: sudo systemctl start docker"
  fi
}

# ---------------------------------------------------------------- 2. web server
check_web() {
  local s
  for s in nginx apache2 httpd; do
    if pgrep -x "$s" >/dev/null 2>&1 \
       || { has systemctl && systemctl is-active --quiet "$s" 2>/dev/null; }; then
      ok "the web server ($s) is running"; return
    fi
  done
  problem "neither nginx nor Apache is running" \
    "start your web server, for example: sudo systemctl start nginx"
}

# ---------------------------------------------------------------- 3. the access log
find_log() {
  LOG="$(conf_get LOG)"
  if [ -z "$LOG" ] && [ "$METHOD" = docker ] && has docker; then
    LOG="$(docker inspect --format '{{range .Args}}{{println .}}{{end}}' "$NAME" 2>/dev/null \
           | awk 'prev == "--log" { print; exit } { prev = $0 }')"
  fi
  if [ -z "$LOG" ] && [ -f "$(p "$UNIT")" ]; then
    LOG="$(tr '\\' ' ' < "$(p "$UNIT")" | tr -s ' \t' '\n\n' \
           | awk 'prev == "--log" { print; exit } { prev = $0 }')"
  fi
}

check_log() {
  find_log
  if [ -z "$LOG" ]; then
    problem "cannot tell which access log the shipper reads" \
      "run sudo bash install.sh again; it asks for the log file"
    return
  fi
  local lp mode grp g o dmode dgrp s1 s2 mt age
  lp="$(p "$LOG")"
  if [ ! -f "$lp" ]; then
    problem "the access log $LOG does not exist" \
      "find the access_log (or CustomLog) line of $SITE (or www.$SITE), then run sudo bash install.sh again with that file"
    return
  fi
  s1="$(fsize "$lp")"; LOG_SIZE="${s1:-unknown} bytes"
  mode="$(fmode "$lp")"; grp="$(fgroup "$lp")"
  g="${mode:1:1}"; o="${mode:2:1}"
  dmode="$(fmode "$(dirname "$lp")")"; dgrp="$(fgroup "$(dirname "$lp")")"
  if ! { [ "$grp" = adm ] && [ $((g & 4)) -ne 0 ]; } && [ $((o & 4)) -eq 0 ]; then
    problem "group adm may not read $LOG (it is $grp, mode $mode)" \
      "sudo chgrp adm $LOG && sudo chmod 640 $LOG, and give logrotate's create line the same group and mode"
  elif ! { [ "$dgrp" = adm ] && [ $(( ${dmode:1:1} & 1 )) -ne 0 ]; } \
       && [ $(( ${dmode:2:1} & 1 )) -eq 0 ]; then
    problem "group adm may not open the folder $(dirname "$LOG")" \
      "sudo chgrp adm $(dirname "$LOG") && sudo chmod g+rx $(dirname "$LOG")"
  else
    ok "the access log $LOG is there and group adm may read it"
  fi
  [ "$WAIT" -gt 0 ] && sleep "$WAIT"
  s2="$(fsize "$lp")"; LOG_SIZE="${s2:-unknown} bytes"
  mt="$(fmtime "$lp")"; age=$(( $(date +%s) - ${mt:-0} ))
  if [ "${s1:-0}" != "${s2:-0}" ] || [ "$age" -le 600 ]; then
    LOG_GROWING=1
    ok "the access log is growing (written in the last 10 minutes)"
  else
    problem "nothing was written to $LOG for $((age / 60)) minutes" \
      "open https://$SITE/ once; if it stays like this, the site writes to another file (see the next line)"
  fi
}

# ---------------------------------------------------------------- 4. www writes to it
# Prints one line per server block: "<host names>|<log files>" ("-" when the block has none).
blocks_nginx() {
  awk '
    { line = $0; sub(/#.*/, "", line); gsub(/"[^"]*"|\047[^\047]*\047/, "\"\"", line) }
    !inb && line ~ /^[ \t]*server[ \t]*\{/ { inb = 1; depth = 0; names = ""; logs = "" }
    inb {
      if (match(line, /server_name[ \t]+[^;]*/)) {
        v = substr(line, RSTART, RLENGTH); sub(/server_name[ \t]+/, "", v); names = names " " v }
      if (match(line, /access_log[ \t]+[^ \t;]+/)) {
        v = substr(line, RSTART, RLENGTH); sub(/access_log[ \t]+/, "", v); logs = logs " " v }
      n = gsub(/\{/, "{", line); depth += n; n = gsub(/\}/, "}", line); depth -= n
      if (depth <= 0) { print tolower(names) "|" (logs == "" ? "-" : logs); inb = 0 }
    }' "$@" 2>/dev/null
}
blocks_apache() {
  awk '
    { line = $0; sub(/^[ \t]*#.*/, "", line); gsub(/"/, "", line)
      gsub(/\$\{APACHE_LOG_DIR\}/, "/var/log/apache2", line) }
    line ~ /^[ \t]*<VirtualHost/ { inb = 1; names = ""; logs = ""; next }
    inb && line ~ /^[ \t]*<\/VirtualHost/ { print tolower(names) "|" (logs == "" ? "-" : logs); inb = 0; next }
    inb && line ~ /^[ \t]*(ServerName|ServerAlias)[ \t]/ { v = line; sub(/^[ \t]*[A-Za-z]+[ \t]+/, "", v); names = names " " v }
    inb && line ~ /^[ \t]*CustomLog[ \t]/ { v = line; sub(/^[ \t]*CustomLog[ \t]+/, "", v); sub(/[ \t].*/, "", v)
      sub(/^logs\//, "/var/log/httpd/", v); logs = logs " " v }
  ' "$@" 2>/dev/null
}
conf_files() {   # $1 = file name pattern for folders, $2.. folders or files; prints the files
  local f pat="$1"; shift
  for f in "$@"; do
    if [ -d "$f" ]; then find "$f" -maxdepth 1 \( -type f -o -type l \) -name "$pat" 2>/dev/null
    elif [ -f "$f" ]; then echo "$f"; fi
  done
}

check_www() {
  [ -n "$LOG" ] || { unsure "which file $SITE writes to (the log file is not known)"; return; }
  local files blocks default line names logs l mine="" others="" named=0
  files="$(conf_files '*' "$(p /etc/nginx/nginx.conf)" "$(p /etc/nginx/sites-enabled)"
           conf_files '*.conf' "$(p /etc/nginx/conf.d)")"
  blocks=""
  if [ -n "$files" ]; then
    default="$(sed 's/#.*//' "$(p /etc/nginx/nginx.conf)" 2>/dev/null \
               | awk '/^[ \t]*server[ \t]*\{/ { exit } /access_log[ \t]/ { sub(/.*access_log[ \t]+/, ""); sub(/[ \t;].*/, ""); print; exit }')"
    [ -n "$default" ] || default=/var/log/nginx/access.log
    blocks="$(IFS='
'; blocks_nginx $files | sed "s#|-\$#| $default#")"
  fi
  files="$(conf_files '*.conf' "$(p /etc/apache2/sites-enabled)" "$(p /etc/httpd/conf.d)" "$(p /etc/httpd/conf/httpd.conf)")"
  if [ -n "$files" ]; then
    default=/var/log/apache2/other_vhosts_access.log
    [ -d "$(p /etc/httpd)" ] && default=/var/log/httpd/access_log
    blocks="$blocks
$(IFS='
'; blocks_apache $files | sed "s#|-\$#| $default#")"
  fi
  if [ -z "$(printf '%s' "$blocks" | tr -d '[:space:]')" ]; then
    unsure "cannot read the nginx or Apache settings, so cannot tell which file $SITE writes to"
    return
  fi
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    names=" $(printf '%s' "${line%%|*}" | tr -s ' \t' '  ') "
    logs=" ${line#*|} "
    case "$names" in
      *" www.$SITE "*|*" $SITE "*|*" .$SITE "*|*" *.$SITE "*)
        named=1
        case "$logs" in *" $LOG "*) mine="yes" ;; *) [ -n "$mine" ] || mine="no:${logs}" ;; esac
        ;;
      *)
        case "$logs" in *" $LOG "*)
          others="$others${names% }" ;;
        esac
        ;;
    esac
  done <<EOF
$blocks
EOF
  if [ "$named" = 0 ]; then
    unsure "no nginx or Apache server block names www.$SITE, so cannot tell which file it writes to" \
      "check that www.$SITE has its own server block with an access_log line"
  elif [ "$mine" = yes ]; then
    ok "www.$SITE writes to $LOG"
  else
    l="$(printf '%s' "${mine#no:}" | awk '{ print $1 }')"
    problem "www.$SITE writes to $l, not to $LOG" \
      "run sudo bash install.sh again and give $l as the log file"
  fi
  others="$(echo "$others" | tr ' ' '\n' | grep . | sort -u | tr '\n' ' ' | sed 's/ $//')"
  if [ -n "$others" ]; then
    others=" $others"
    problem "$LOG is shared with other host names:$others" \
      "give www.$SITE its own log file; README.txt says how"
  fi
}

# ---------------------------------------------------------------- 4b. Next.js pages
# A Next.js site (?_rsc= in the log's last lines): does each line record Next.js's prefetch
# header? Without it, a page opened by a click inside the site is not counted. Says nothing
# for any other site. Reads only: never edits nginx or Apache.
check_nextjs() {
  local lp tail files
  [ -n "$LOG" ] || return
  lp="$(p "$LOG")"
  [ -f "$lp" ] || return
  tail="$(tail -n 5000 "$lp" 2>/dev/null)"
  printf '%s\n' "$tail" | grep -q '_rsc=' || return
  if printf '%s\n' "$tail" | grep -q ' rsc_prefetch='; then
    ok "pages opened inside this Next.js site are counted: the log records its prefetch header"
    return
  fi
  files="$(conf_files '*' "$(p /etc/nginx/nginx.conf)" "$(p /etc/nginx/sites-enabled)"
           conf_files '*.conf' "$(p /etc/nginx/conf.d)" "$(p /etc/apache2/apache2.conf)" \
             "$(p /etc/apache2/conf-enabled)" "$(p /etc/apache2/sites-enabled)" \
             "$(p /etc/httpd/conf.d)" "$(p /etc/httpd/conf/httpd.conf)")"
  if [ -n "$files" ] && (IFS='
'; grep -isE '^[^#]*(log_format|LogFormat).*rsc_prefetch=' $files) >/dev/null 2>&1; then
    advice "the log_format has rsc_prefetch= but the log does not show it yet" \
      "sudo nginx -t && sudo systemctl reload nginx (Apache: sudo apachectl configtest && sudo systemctl reload apache2), then open a page and click a link inside the site"
    return
  fi
  advice "pages opened inside this Next.js site are not counted: the log does not record Next.js's prefetch header, so a click cannot be told from a prefetch" \
    "append${NEXT_NGINX} at the end of the site's nginx log_format (Apache LogFormat:${NEXT_APACHE}), then sudo nginx -t && sudo systemctl reload nginx. This script never edits nginx."
}

# ---------------------------------------------------------------- 5. outbound HTTPS
check_https() {
  local code="" rc=0
  if has curl; then
    code="$(curl -s -o /dev/null -w '%{http_code}' -X POST --max-time 15 \
            -H 'Content-Type: text/plain' -H 'X-Skald-Check: 1' --data '' "$URL" 2>/dev/null)"; rc=$?
  elif has python3; then
    code="$(python3 - "$URL" 2>/dev/null <<'PY'
import socket, ssl, sys, urllib.error, urllib.request
class Stay(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kw):
        return None
try:
    got = urllib.request.build_opener(Stay).open(
        urllib.request.Request(sys.argv[1], data=b"", method="POST",
                               headers={"X-Skald-Check": "1"}), timeout=15)
    print(got.status)
except urllib.error.HTTPError as why:
    print(why.code)
except urllib.error.URLError as why:
    r = why.reason
    print("tls" if isinstance(r, ssl.SSLError) else "dns" if isinstance(r, socket.gaierror)
          else "timeout" if isinstance(r, socket.timeout) else "connect")
except socket.timeout:
    print("timeout")
except Exception:
    print("other")
PY
)"
    case "$code" in tls) rc=60 ;; dns) rc=6 ;; timeout) rc=28 ;; connect) rc=7 ;; other) rc=1 ;; esac
    [ "$rc" = 0 ] || code=000
  else
    problem "cannot test the connection: neither curl nor python3 is here" \
      "install curl (sudo apt-get install curl) and run this again"
    return
  fi
  local fw="allow outbound HTTPS (port 443) from this server to $HOST in its firewall"
  if [ "$rc" != 0 ] || [ -z "$code" ] || [ "$code" = 000 ]; then
    case "$rc" in
      5|6) problem "this server cannot find $HOST (name lookup failed)" \
             "check this server's DNS settings; the name $HOST must resolve" ;;
      7) problem "this server cannot connect to $HOST on port 443" "$fw" ;;
      28) problem "no answer from $HOST within 15 seconds" "$fw" ;;
      35|51|53|54|58|59|60|77|80|83|90|91)
         problem "the HTTPS certificate check for $HOST failed" \
           "update the CA certificates (sudo apt-get install --reinstall ca-certificates) and check the clock (timedatectl)" ;;
      *) problem "could not reach $HOST (error $rc)" "$fw" ;;
    esac
    return
  fi
  case "$code" in
    401) ok "the send address answers (401 without a token is expected)" ;;
    403) problem "the send address refuses this server (HTTP 403)" \
           "a firewall or proxy between this server and $HOST may block it; send us the block below" ;;
    404) problem "the send address is not found (HTTP 404)" \
           "send us the block below; we check the address for $SITE" ;;
    405) problem "the send address does not take POST requests (HTTP 405)" \
           "a proxy on the way out may change the request; send us the block below" ;;
    3??) problem "the send address redirects (HTTP $code); the shipper does not follow redirects" \
           "a proxy on the way out may rewrite HTTPS; send us the block below" ;;
    2??) problem "the send address answered $code without a token; it should say 401" \
           "send us the block below" ;;
    5??) problem "Skald answered with a server error (HTTP $code)" \
           "wait a few minutes and run this again; if it stays, send us the block below" ;;
    *) problem "the send address answered HTTP $code" "send us the block below" ;;
  esac
}

# ---------------------------------------------------------------- 6. the token file
check_token() {
  local tp own grp mode len lines
  tp="$(p "$TOKEN_FILE")"
  if [ ! -s "$tp" ]; then
    problem "no token is saved in $TOKEN_FILE" "run sudo bash install.sh and paste the token"
    return
  fi
  own="$(fowner "$tp")"; grp="$(fgroup "$tp")"; mode="$(fmode "$tp")"
  len="$(tr -d '\r\n' < "$tp" | wc -c | tr -d ' ')"
  lines="$(grep -c . "$tp" 2>/dev/null)"
  if [ "$own" != "$WANT_OWNER" ] || [ "$grp" != "$WANT_GROUP" ] || [ "$mode" != 640 ]; then
    problem "the token file $TOKEN_FILE is $own:$grp $mode; it should be $WANT_OWNER:$WANT_GROUP 640" \
      "sudo chown $WANT_OWNER:$WANT_GROUP $TOKEN_FILE && sudo chmod 640 $TOKEN_FILE"
  elif [ "${lines:-0}" -gt 1 ] || tr -d '\n' < "$tp" | grep -q '[[:space:]]'; then
    problem "the token file holds spaces or more than one line" \
      "run sudo bash install.sh again and paste the token once, as one line"
  elif [ "$len" -lt 20 ]; then
    problem "the token is too short ($len characters)" \
      "run sudo bash install.sh again and paste the whole token"
  else
    ok "the token file is $own:$grp 640, one line of $len characters"
  fi
}

# ---------------------------------------------------------------- 7. the shipper
check_shipper() {
  local st status restarting count active n
  if [ "$METHOD" = docker ]; then
    has docker || { problem "cannot look at the shipper: Docker is not here" "install Docker first"; return; }
    st="$(docker inspect --format '{{.State.Status}} {{.State.Restarting}} {{.RestartCount}}' "$NAME" 2>/dev/null)"
    if [ -z "$st" ]; then
      problem "there is no skald-ship container" "run sudo bash install.sh"; return
    fi
    status="${st%% *}"; restarting="$(echo "$st" | awk '{ print $2 }')"; count="$(echo "$st" | awk '{ print $3 }')"
    case "$count" in ''|*[!0-9]*) count=0 ;; esac
    if [ "$restarting" = true ] || [ "$status" = restarting ] || [ "$count" -ge 3 ]; then
      problem "skald-ship keeps restarting ($count restarts)" \
        "see the shipper's reasons below; if the token is wrong, run sudo bash install.sh again"
    elif [ "$status" != running ]; then
      problem "skald-ship is $status, not running" \
        "start it: sudo docker start skald-ship; if it stops again, see the reasons below"
    else
      ok "skald-ship is running ($count restarts)"
    fi
  else
    has systemctl || { problem "this server has no systemctl" "ask us for the Docker kit"; return; }
    if [ ! -f "$(p "$UNIT")" ]; then
      problem "the skald-ship service is not installed" "run sudo bash install.sh"; return
    fi
    active="$(systemctl is-active skald-ship 2>/dev/null)"
    n="$(systemctl show -p NRestarts skald-ship 2>/dev/null | sed 's/^NRestarts=//')"
    case "$n" in ''|*[!0-9]*) n=0 ;; esac
    if [ "$n" -ge 3 ] || [ "$active" = activating ]; then
      problem "skald-ship keeps restarting ($n restarts)" \
        "see the shipper's reasons below; if the token is wrong, run sudo bash install.sh again"
    elif [ "$active" != active ]; then
      problem "skald-ship is ${active:-not running}" \
        "start it: sudo systemctl start skald-ship; if it stops again, see the reasons below"
    else
      ok "skald-ship is running ($n restarts)"
    fi
  fi
}

# ---------------------------------------------------------------- 8. what the shipper says
reason() {   # $1 = count, $2 = short reason for the summary, $3 = what, $4 = fix ("" = no problem)
  [ "${1:-0}" -gt 0 ] || return 0
  REASONS="${REASONS}shipper: $2 (x$1)
"
  if [ -n "$4" ]; then
    problem "shipper: $3 (in $1 of its last 20 lines)" "$4"
  else
    ok "shipper: $3 (in $1 of its last 20 lines)"
  fi
}

check_said() {
  SHIP_LINES=""
  if [ "$METHOD" = docker ]; then
    has docker && SHIP_LINES="$(docker logs --tail 20 "$NAME" 2>&1)"
  else
    has journalctl && SHIP_LINES="$(journalctl -u skald-ship -n 20 -o cat 2>/dev/null)"
  fi
  if [ -z "$(printf '%s' "$SHIP_LINES" | tr -d '[:space:]')" ]; then
    ok "the shipper has said nothing yet (it speaks when it sends a batch)"; return
  fi
  local before=$PROBLEMS sent rejected
  local again="make a new sending token in the site's Connections page, run sudo bash install.sh again and paste it"
  reason "$(count 'HTTP 401')" "401 wrong or revoked token" \
    "the token is wrong or was revoked (HTTP 401)" "$again"
  reason "$(count 'HTTP 403 .*not for that site')" "403 token for another site" \
    "the token is for another site (HTTP 403)" "make a sending token for $SITE in Connections, then run sudo bash install.sh again"
  reason "$(count 'HTTP 403 .*scope')" "403 not a sending token" \
    "the token is not a sending (ingest) token (HTTP 403)" "make a token with the sending scope in Connections, then run sudo bash install.sh again"
  reason "$(count 'HTTP 403 .*verified')" "403 site not verified yet" \
    "$SITE is waiting for its domain to be verified (HTTP 403)" "finish step 2 of the site's set-up; the shipper keeps the lines until then"
  reason "$(printf '%s\n' "$SHIP_LINES" | grep -E 'HTTP 403' | grep -viE 'not for that site|scope|verified' | grep -c .)" \
    "403 other" "something refused the shipper (HTTP 403)" "send us the block below"
  reason "$(count 'HTTP 404')" "404 site not taken here" \
    "Skald does not take logs for $SITE at this address (HTTP 404)" "send us the block below"
  reason "$(count 'HTTP 410')" "410 site removed" \
    "$SITE was removed from Skald (HTTP 410)" "stop the shipper with sudo bash uninstall.sh, or ask us if this is a mistake"
  reason "$(count 'HTTP 429 .*slow down')" "429 slowed down" \
    "Skald asked it to slow down (HTTP 429); nothing to do, it catches up" ""
  reason "$(printf '%s\n' "$SHIP_LINES" | grep -E 'HTTP 429' | grep -vi 'slow down' | grep -c .)" \
    "429 day or plan limit" "the day's or the plan's limit for log lines is used up (HTTP 429)" \
    "nothing is lost: the shipper sends the lines later; to raise the limit, see your plan"
  reason "$(count 'HTTP 5[0-9][0-9]')" "5xx server busy" \
    "Skald was busy or short of disk for a moment (HTTP 5xx); nothing to do if it passes" ""
  reason "$(count 'network error|refused|timed out')" "cannot reach $HOST" \
    "it cannot reach $HOST" "allow outbound HTTPS (port 443) from this server to $HOST"
  reason "$(count 'PermissionError|Permission denied')" "may not read the log" \
    "it may not read the log file" "let group adm read the log (see the access log line above)"
  reason "$(count 'waiting for .* to exist')" "log file missing" \
    "it waits for the log file to exist" "run sudo bash install.sh again with the right log file"
  rejected="$(printf '%s\n' "$SHIP_LINES" | sed -n 's/.*sent batch [0-9]*: .* \([0-9][0-9]*\) rejected.*/\1/p' \
              | awk '{ s += $1 } END { print s + 0 }')"
  if [ "${rejected:-0}" -gt 0 ]; then
    REASONS="${REASONS}shipper: $rejected lines rejected (log format)
"
    problem "shipper: $rejected lines were in a log format Skald does not read" \
      "set the site's log format to auto (Settings > Sites), or send us the log_format line"
  fi
  sent="$(count 'sent batch')"
  if [ "$PROBLEMS" = "$before" ]; then
    ok "the shipper's last 20 lines show no refusals (batches sent: $sent)"
  fi
}

# ---------------------------------------------------------------- 9. lines leave
check_state() {
  local sp mt age
  sp="$(p "$STATE")"
  if [ ! -f "$sp" ]; then
    if [ "$LOG_GROWING" = 1 ]; then
      problem "the log grows but the shipper has sent nothing yet (no position saved)" \
        "see the shipper's reasons above; if there are none, open https://www.$SITE/ and run this again in a minute"
    else
      ok "nothing sent yet, but the log did not grow either"
    fi
    return
  fi
  mt="$(fmtime "$sp")"; age=$(( $(date +%s) - ${mt:-0} ))
  if [ "$age" -le 600 ]; then
    ok "lines are leaving: the shipper sent some in the last 10 minutes"
  elif [ "$LOG_GROWING" = 1 ]; then
    problem "the log grows but no lines have left for $((age / 60)) minutes" \
      "see the shipper's reasons above; if there are none, restart it: $RESTART_CMD"
  else
    ok "nothing new to send: the log did not grow, last sent $((age / 60)) minutes ago"
  fi
}

main() {
  if [ -z "$R" ] && [ "$(id -u)" != 0 ]; then
    echo "run it with sudo: sudo bash check.sh"; return 1
  fi
  case "$METHOD" in docker|systemd) ;; *) echo "this copy does not say how the shipper was installed; download the kit again"; return 1 ;; esac
  echo "Checking the Skald shipper for $SITE ($METHOD). This changes nothing."
  echo
  check_docker
  check_web
  check_log
  check_www
  check_nextjs
  check_https
  check_token
  check_shipper
  check_said
  check_state
  echo
  if [ "$PROBLEMS" = 0 ]; then echo "All OK."
  else echo "$PROBLEMS problem(s). Fix the first one, then run this again. Help: $HELP"; fi
  echo
  echo "Copy this and send it to us:"
  echo "-----"
  echo "Skald shipper check, $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo "method: $METHOD"
  echo "site: $SITE"
  echo "send to: $HOST"
  echo "log: ${LOG:-unknown} (${LOG_SIZE})"
  printf '%s' "$SUMMARY"
  printf '%s' "$REASONS"
  echo "-----"
  [ "$PROBLEMS" = 0 ]
}

main "$@" 2>&1 | mask
exit "${PIPESTATUS[0]}"
