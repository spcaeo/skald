Skald log shipper for __SITE__ (Docker)
=======================================

If something seems wrong: run `sudo bash check.sh` first, and send us its last block.
It changes nothing, and that block holds no token and no IP address.
Troubleshooting guide: __HELP__

What it does
  A small container (skald-ship) reads the access log of __SITE__ and sends
  new lines to Skald over HTTPS:

    __URL__

  It only reads the log. It never writes to nginx, Apache or the website, and uses at
  most 128 MB of memory. Only new visits are sent, no old log lines.
  The dashboard: __DASHBOARD__

You need
  - sudo on the web server, and Docker (docker --version)
  - outbound HTTPS (port 443) to __HOST__
  - the token. It only allows sending logs for __SITE__.
    If this folder holds a file named ship-token, the token is in this kit:
    install.sh uses it and then deletes that file.
    If not, the token is sent to you separately, never by email; install.sh asks for it.

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

If www and another subdomain write to the same log file
  Give www.__SITE__ its own file first, in its server block (nginx):
    access_log /var/log/nginx/www.__SITE__.access.log <the same format as now>;
  then: sudo nginx -t && sudo systemctl reload nginx
  Apache: a CustomLog line in its VirtualHost, then: sudo apachectl configtest && sudo systemctl reload apache2
  Then run sudo bash install.sh again and give the new file.

What it keeps on this server
  /srv/skald/ship-token   the token (root:adm, 0640)
  /srv/skald/ship.conf    the log file and send address, for check.sh (no token)
  /srv/skald/ship-state   how far it has read

Undo at any time
  sudo bash uninstall.sh      (removes the container, the token and its position; nothing else)
