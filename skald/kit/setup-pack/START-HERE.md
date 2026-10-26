# Set up Skald for __SITE__

Skald counts the visitors of __SITE__ from the web server's own records (its access log), so
it sees people, search engines and AI crawlers that page scripts miss. This folder holds
everything to connect the site; most cases take ten minutes.

Your Skald page: __DASHBOARD__

__SECRETS__

**Using an AI coding agent?** Give it this folder (or the site's code with this folder in it)
and say: *Set up Skald from CLAUDE.md*. It follows the same steps as below.

## 1. Pick your case

Do one of A to D. If you are not sure how the site is hosted, ask whoever runs it.

### A. The site runs on your own Linux server (nginx or Apache)

With or without Docker. On the server, as a user who may use sudo:

```sh
sudo bash skald-install-__SITE__.sh
```

That file is `logs/install-server.sh` in this folder (copy it to the server with `scp`, or
paste its text into a file there). It finds the site's access log by itself, uses Docker when
the server has it and a small service otherwise, and asks only when it cannot tell. Options:
`--log <path>` names the log, `--dry-run` shows what it would do and changes nothing, `--yes`
asks nothing. Running it again is safe. It reads the log only; it never changes nginx, Apache
or the website.

It leaves two commands on the server: `sudo skald-ship-check` (checks everything, changes
nothing) and `sudo skald-ship-uninstall` (removes only what it installed).

### B. Cloudflare is in front of the site

Follow `logs/cloudflare.md`. Use it when Cloudflare serves the site and no server log is sent.

### C. Vercel or Netlify hosts the site

Follow `logs/vercel-netlify.md`: a log drain, nothing to install (Vercel Pro or Enterprise,
Netlify Enterprise). On other plans, use D.

### D. Only the script tag

When none of the above fits (a site builder, shared hosting), put the tag in
`tag/script-tag.html` on every page (see `tag/README.md`). It counts people and their clicks,
but not search engines or AI crawlers.

The tag is also worth adding beside A, B or C: it records clicks, form steps and scroll that a
log cannot see.

## 2. Leads (optional)

When the site has a contact or sign-up form, its backend can tell Skald about each lead, so
Skald shows which pages and sources bring them. The files are in `leads/`, with a README. The
lead address is:

    __LEAD_URL__

__LEAD_SECRET_NOTE__

## 3. Check that it works

1. Open https://__SITE__/ in a normal browser window.
2. Within a few minutes the visit shows on __DASHBOARD__ (Settings > Collect data > Send logs
   says what arrived and when).
3. On your own server: `sudo skald-ship-check`. Every line should say OK. If one says
   PROBLEM, it says the fix under it.

Help: __HELP__

## Keep the keys safe

The sending token and the lead secret work like passwords. Keep them in environment
variables or the host's secret settings, never in the site's code, in git, or in a chat. If
one leaks, make a new one in Skald (Settings > Collect data > Send logs or Settings > Leads & integrations): the
old one stops at once.
