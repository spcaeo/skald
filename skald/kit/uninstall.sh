#!/bin/bash
# Remove the Skald log shipper for __SITE__. nginx, Apache and the website are not touched.
#   sudo bash uninstall.sh
# Docker: removes the skald-ship container, /srv/skald/ship-token, ship.conf and ship-state;
#   nothing else in /srv/skald (the folder goes only when it is left empty).
# systemd: stops and removes the skald-ship service, /usr/local/bin/skald-ship,
#   /etc/skald-ship (token and settings), /var/lib/skald-ship (its position) and the
#   skald-ship system user, which install.sh made for it alone.
set -uo pipefail
METHOD="__METHOD__"
[ "$(id -u)" = 0 ] || { echo "run it with sudo: sudo bash uninstall.sh" >&2; exit 1; }

case "$METHOD" in
  docker)
    docker rm -f skald-ship >/dev/null 2>&1 && echo "skald-ship removed" || echo "no skald-ship container"
    rm -f /srv/skald/ship-token /srv/skald/ship.conf && rm -rf /srv/skald/ship-state \
      && echo "token, settings and position removed"
    rmdir /srv/skald 2>/dev/null && echo "/srv/skald removed (it was empty)" || true
    ;;
  systemd)
    if [ -f /etc/systemd/system/skald-ship.service ]; then
      systemctl disable --now skald-ship >/dev/null 2>&1 || true
      rm -f /etc/systemd/system/skald-ship.service
      systemctl daemon-reload || true
      echo "skald-ship service stopped and removed"
    else
      echo "no skald-ship service"
    fi
    rm -f /usr/local/bin/skald-ship && echo "/usr/local/bin/skald-ship removed"
    rm -rf /etc/skald-ship /var/lib/skald-ship && echo "token, settings and position removed"
    if id skald-ship >/dev/null 2>&1; then
      userdel skald-ship 2>/dev/null && echo "the skald-ship user removed" \
        || echo "the skald-ship user could not be removed; it can stay, it has no login"
    fi
    ;;
  *)
    echo "this copy does not say how the shipper was installed; download the kit again" >&2
    exit 1
    ;;
esac
echo "Done. Nothing else was changed."
