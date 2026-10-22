Skald log shipper for __SITE__ (systemd, no Docker)
===================================================

If something seems wrong: run `sudo bash check.sh` first, and send us its last block.
It changes nothing, and that block holds no token and no IP address.
Troubleshooting guide: __HELP__

What it does
  A small service (skald-ship, one Python file) reads the access log of __SITE__
  and sends new lines to Skald over HTTPS:

    __URL__

  It only reads the log. It never writes to nginx, Apache or the website.
  Only new visits are sent, no old log lines.
  The dashboard: __DASHBOARD__

You need
  - sudo on the web server, with systemd (Ubuntu or Debian)
  - Python 3.9 or newer (python3 --version). Older? Ask us for the Docker kit.
  - outbound HTTPS (port 443) to __HOST__
  - the token. It only allows sending logs for __SITE__.
    If this folder holds a file named ship-token, the token is in this kit:
    install.sh uses it and then deletes that file. Nothing else to do.
    If not, the token was sent to you separately (never by email). Give it to
    install.sh in one of three ways (see "If the token is not in this kit" below).

Steps (about 5 minutes)
  1. Copy this folder to the server and go into it:
       scp -r skald-ship-__SITE__ <server>:~/   then   cd ~/skald-ship-__SITE__
  2. Optional, to see what it will do without changing anything:
       sudo bash install.sh --dry-run
  3. Run it:
       sudo bash install.sh
     It lists the access log and host-name lines of nginx or Apache. Give the full path
     of the access log of the __SITE__ (or www.__SITE__) server block (for example
     /var/log/nginx/__SITE__.access.log). Then paste the token when asked (if it is
     not in this kit). It is not shown as you paste it.
  4. It shows the shipper's first lines. Open https://__SITE__/ once; within a few
     minutes the visit shows on the dashboard.
  5. To check everything at any time:
       sudo bash check.sh
     Its own lines: journalctl -u skald-ship -n 20 -o cat

If the token is not in this kit
  The zip was made without the token, so the token was sent to you another way.
  install.sh takes it in this order:
    1. A file named ship-token in this folder. Make it yourself, then run install.sh
       (it uses the file and deletes it):
         nano ship-token          paste the token, save, exit
         chmod 600 ship-token
    2. The environment variable SKALD_SHIP_TOKEN. Typed without echo, so it is not
       kept in the shell history:
         read -rs SKALD_SHIP_TOKEN && export SKALD_SHIP_TOKEN
         sudo --preserve-env=SKALD_SHIP_TOKEN bash install.sh
    3. Pasted when install.sh asks for it (the easiest). It is not shown as you paste.
  A token already saved on this server by an earlier run is kept unless you say no.

If www and another subdomain write to the same log file
  Give www.__SITE__ its own file first, in its server block (nginx):
    access_log /var/log/nginx/www.__SITE__.access.log <the same format as now>;
  then: sudo nginx -t && sudo systemctl reload nginx
  Apache: a CustomLog line in its VirtualHost, then: sudo apachectl configtest && sudo systemctl reload apache2
  Then run sudo bash install.sh again and give the new file.

If __SITE__ is a Next.js site
  A click inside a Next.js site loads no HTML page, only a ?_rsc= request, and Next.js
  sends the same request to prefetch the links in view. Skald tells them apart only
  when the log records Next.js's prefetch header. Add this at the end of the site's
  nginx log_format (before the closing quote and semicolon):
    rsc_prefetch=$http_next_router_prefetch
  Apache, at the end of its LogFormat:
    rsc_prefetch=%{Next-Router-Prefetch}i
  then: sudo nginx -t && sudo systemctl reload nginx
  (Apache: sudo apachectl configtest && sudo systemctl reload apache2)
  check.sh says whether the log has it. Neither script ever edits nginx or Apache.
  It is safe: it only adds one header's value (1, or - when absent) to what nginx already
  writes in its own log. No port, no route, no access changes.

What it puts on this server
  /usr/local/bin/skald-ship               the shipper (skald-ship.py from this kit)
  the skald-ship system user              in group adm, which may read the web server's logs
  /etc/skald-ship/token                   the token (root:skald-ship, 0640)
  /etc/skald-ship/ship.conf               the log file and send address, for check.sh (no token)
  /etc/systemd/system/skald-ship.service  the service
  /var/lib/skald-ship                     how far it has read

Undo at any time
  sudo bash uninstall.sh      (removes all of the above; nothing else)
