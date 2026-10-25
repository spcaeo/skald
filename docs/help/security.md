# Security: scanners, exposures and attack attempts

See who probes your server for files and panels it does not have, whether the server ever handed one of them a real file, what else they tried, and which addresses to block. All of it comes from your server log, the same lines every other figure is counted from.

## Where to find it

Open **Security** in the menu (on a phone: **Menu**, then **Security**). It has seven tabs, each answering one question. The date range in the top bar applies to every tab but Alerts. Press `g` then `y` to jump here.

Security is a view across your traffic, never a group of its own: a scanner's requests stay in **bots**, where they always were, so every other figure is unchanged.

## What counts as a scanner

A **probe** is a request for a path no real site serves, or with an attack string in the address. For example:

- secret files: `/.env`, `/.git/config`, `/.aws/credentials`, private keys;
- cloud and deploy files: Terraform (`.tf`, `.tfstate`), `serverless.yml`, `appspec.yml`, `docker-compose.yml`;
- WordPress: `/wp-login.php`, `/xmlrpc.php`, `/wp-config.php`;
- database dumps and backups: `backup.sql`, `site.zip`;
- admin panels and consoles: `/phpmyadmin/`, `/admin`, `/owa/`, Jenkins, Solr;
- PHP scripts: `/phpinfo.php`, `/config/auth.php`, `/storage/logs/laravel.log`;
- path tricks and injection in the address: `../`, `/etc/passwd`, `${jndi:`, `<script`, `union select`.

A **scanner** is one address with one user agent that made at least one probe that day. All its requests of the day are counted on its row, not only the probes. A site's own old paths (`site.legacy_paths`) are never probes.

## Is anything exposed?

The first tab answers the question that matters most: **did the server hand a scanner a real file?**

At the top, one line says it:

- **Nothing exposed in this period**: every probe answered with a page (a 2xx status) got the host's harmless fallback page, or an empty body.
- **N possible exposures: check these now**: these probes got a page whose size is unlike the host's fallback page. Open each path yourself and see what it returns.
- **Can't tell for N answers**: the log line has no size, so Skald cannot tell a page from a file. It never calls these safe. Add the body size (`$body_bytes_sent` in nginx) to your log format.

### How to read "harmless" (the fallback page)

Many sites answer every path they do not have with the same page:

- a single-page app (React, Vue, Next.js exported) sends its `index.html` for any path;
- a server's default page answers anything sent straight to the server's IP address.

So a scanner asking for `/.env` often gets a **200** with that page, not the file. That is harmless. Skald learns each host's fallback page from the day's own answers: any size that at least three different probe paths of that host were answered with (within 16 bytes). A host can have more than one: the same page sent compressed to most scanners and uncompressed to one that did not ask for compression. A probe answered with such a size is **harmless**; one answered with a size no other probe path got is a **possible exposure**.

A probe that is an ordinary page with an attack in its query string (for example `/?id=1 union select`) asked for no file: its answer is that page. It is listed under **Attack attempts**, with what was answered, never as an exposure.

Each host has its own fallback page, and so does the server's bare IP. The size in the log is the size **sent**, after compression, so the same page can show as two sizes: for example 392 bytes through your site's name (compressed by your CDN) and 404 bytes when asked of the server's IP directly (compressed by the server). Both are harmless.

### What the log can and cannot prove

- The log records the status and the size of each answer. It never records what was in it.
- A **possible exposure** is a reason to look, not proof of a leak: a real page of an unusual size can be one.
- A **harmless** answer is no proof of safety either: a file that happened to be exactly the fallback page's size would look the same. It is very unlikely, not impossible.
- If one file is asked for three different ways and answered each time (`/.env`, `/.env.local`, `/.env.prod` with the same size), Skald could take that size for the fallback page. The table of each host's answers shows the size it used, so you can check.

### What to do about a possible exposure

1. Open the address in your browser. If it shows secrets, keys or settings, it is a leak.
2. Stop the web server from serving such files. In nginx, for dotfiles: `location ~ /\. { deny all; }`; for deploy and backup files, deny their extensions the same way. The tab gives one line of advice for each kind.
3. Rotate every secret the file held: passwords, API keys, tokens. Assume it was read.
4. Check **Who is scanning us?** for the address that got it.

## Your stack

**What runs the site, and does a known flaw apply to it?**

Once a day, in the morning run, Skald opens the site's home page from outside, like any visitor (no cookie, no password), and reads what the server says about itself and what the page says built it:

- the web server and its version (`Server: nginx/1.24.0`, Apache, LiteSpeed);
- PHP and its version (`X-Powered-By: PHP/8.1.2`);
- WordPress (its generator tag, or `/wp-content/` in the page) and so PHP;
- Next.js, and so Node.js;
- **content origins**: another host the page loads WordPress files from, such as a headless WordPress at `wp.` of your site. Skald opens that host's home page once too.

On every WordPress host it asks once for `/wp-login.php` (no password, no redirect followed). If it answers, the tab says **Login page open to the internet**: anyone can try passwords there. Consider an address allow-list or a second factor.

Each site name is read once (`www.` is the same site), at most three names and three origins. The tab says **as of** when it was read.

**A version the server does not show** reads "not shown by the server". Skald never guesses it. Under **For your server admin** the tab gives the command that shows it: `php -v`, `node -v`, `nginx -v`, `apachectl -v`, `wp core version`.

### Advisories

Skald ships a short list of security advisories with each release, from the vendors' own pages (for example PHP's and Node.js's October 2026 security releases). Each is set against what serves the site:

- **Update needed**: the version shown is below the fixed release of its branch.
- **No official fix: upgrade the branch**: the branch gets no fix any more (PHP 8.1 and older; a Node.js branch past its end of life).
- **Check your version**: the product is there, but the server hides its version. The fixed releases are listed; check yours with the command.

Each card says what the flaw is in plain words, what to do, the mitigations from the advisory (folded: they reduce the exposure, they do not make a site safe), and links to the source.

**This tells you what applies to your stack and how to fix it. Skald does not detect or block an exploit of these flaws.**

The list updates when you upgrade Skald. Skald fetches nothing by itself; your server admin can let it fetch the newest list from Skald's public repository once a day with `security.advisories_fetch: true` in the config (off by default).

The stack is checked once a day, in the morning run. To check it now (after an install, or after an upgrade brings a new advisory list), your server admin runs `skald stack`, then `skald dashboard`.

### Public check (optional)

Your server admin can offer the same outside look to anyone, as a page on your own website: a visitor types an address and sees what that site's home page shows, which advisories match, and whether its WordPress login page is open. It is off unless switched on (`security.public_check: true`, or `SKALD_PUBLIC_CHECK=true` in Docker); the settings guide (SETTINGS.md, "Public check") has the details. It reads only public pages, at most eight requests per check, never an address inside a network, and keeps nothing but an hour's answers in memory. Every finding shows its proof: the exact header line or page reference it was read from, the address, and a command to check it yourself, with the list of every request made. What it could not read says "could not check". Like Your stack, it tells what applies; it never tests for the flaw.

## Who is scanning us?

One row per scanner (address and user agent) for the period: when it was first and last seen, how many requests and probes, its country, whether it comes from a hosting or cloud network (when Skald keeps that list), what it looked for, and what your server answered (2xx, 3xx, 4xx, 5xx). Above the table, the probes per day and what they looked for.

Signs on a row:

- **Forged referrer**: it said it came from one of your own pages (or a subdomain, such as `wp.` of your site) but never loaded your site's files. A person clicking a link does load them.
- **Sent to the bare IP**: it asked for your server's IP address instead of your site's name. People and search engines use the name; scanners sweep addresses.
- **Hosting network**: it comes from a cloud or hosting provider, not from a home or office.

Select a row to see its detail: the paths it asked for, and **Open its requests**, which opens **Site › Requests** filtered to that address. The request list keeps only the last few hours of the raw log; older lines of that address have expired from it, and only the counts remain here.

**Addresses.** Only owners and admins see them, and only on a site that keeps addresses (**Settings › Data retention**). A site that keeps them shortened shows networks (`/24` for IPv4, `/48` for IPv6), never one address. Anyone else sees each day's rows without their address. Scanners and addresses are counted per day: one that came back on three days counts three times.

## Attack attempts

What was tried beyond looking around:

- **Path tricks and injection**: an attack string in the address, by kind (path traversal, Log4Shell, script injection, SQL injection, PHP settings).
- **Login and form hammering**: 20 or more POSTs to a login or form path (sign in, password, sign-up, contact...) from one address within 5 minutes.
- **Bursts**: 300 or more requests from one address within 60 seconds. Search engines, AI crawlers and your own traffic are left out.

Each one shows the address (owners and admins), when, how many, and what the server answered. A hammering episode answered with 401 or 403 means your login said no; answered with 200 or 302, check whether a sign-in worked. The thresholds can be changed in the config's `security:` section.

### Log signs worth a look

At the top of Attack attempts, things in the log that stand out from the site's usual day. They are worth a look, never proof of an attack:

- **Gateway errors** (502, 503, 504): PHP workers or an upstream may be crashing. Flagged on a day with at least three times the median of the 14 days before it (7 of them recorded at least) and at least 20; the busiest hour is named.
- **Requests for .php paths**, by the same rule.
- **Large POST bodies**: POSTs of 1,000,000 bytes or more, where the log records each request's size. If it does not, the tab says "not recorded" and gives the nginx line to add (`request_length=$request_length`).

## Fake browsers and scrapers

Requests that said they were a browser but were not a person, which Skald already counts under bots, never as visitors:

- **Never rendered the page**: took pages and never loaded their scripts and styles.
- **Too fast for a person**: six pages or more within two seconds.
- **Browser-like crawler**: fetched robots.txt or a sitemap, as only crawlers do.
- **Claims to be Googlebot** (or GPTBot, Bingbot...): from an address that crawler does not use.

Grouped by address and network, with the pages they took. Named crawlers that are what they say live on **AI & bots › Crawlers**.

## Block list

The worst addresses and networks of the period, ranked by probes, then attack attempts, for owners and admins on a site that keeps addresses. Export them three ways:

- **nginx deny lines**: paste into your `server { }` block, then run `nginx -t` and reload nginx.
- **Cloudflare IP list (CSV)**: in the Cloudflare dashboard go to **Settings › Lists**, select **Create new list** with the IP content type (or **Edit** next to a list you have), then **Add items › Upload CSV**. Then use the list in a WAF rule. These are the steps in Cloudflare's own guide, [Create a list in the dashboard](https://developers.cloudflare.com/waf/tools/lists/create-dashboard/), as of 24 October 2026.
- **Plain list**: one address or network per line, for fail2ban, ipset or a firewall.

**Review before you block.** A shared address (an office, a mobile network, a VPN) or a CDN can carry real visitors too, and a scanner moves to a new address within days. Blocking stops requests; it does not fix a file that should not be served: fix that first.

With shortened addresses the list holds networks only; with addresses not kept there is nothing to block by address, and the tab says so.

## Alerts

Three site alerts, sent the same way as the site's other alerts (the dashboard, the site's alert mail to its confirmed recipients, and your webhooks, Slack included):

- **Possible exposure**: opens at once (the live count runs every two minutes) when a probe is answered with a page unlike the host's fallback page, one alert per host and path.
- **Advisory matches your stack**: after the daily check, one alert per advisory, host and product that needs something done.
- **New scan wave**: the last whole day's probes are at least three times the usual day (the median of the 14 days before, at least 7 of them counted) and at least 200. Off until you switch it on.

The first two are on whenever the site's alerts are on. Switch each on or off on **Site › Alerts**.

### Your own security alerts

On top of the site's alert mail, each person on the site's team chooses their own, under **Your security alerts** on this tab:

- **On or off**, and **right away** or **in the daily mail** (one mail with every new item, after the morning run).
- By default owners and admins get them right away; viewers get none until they turn them on.
- Each mail names the site, what was found, what to do in one line, and a link straight to it on the Security tab (for example `…#threats/exposed?item=x1a2b3c4d5e6`), which opens with that item first.
- Each item is mailed once; a reminder comes only while it stays open, every 3 days (`security.remind_days`).
- Only accounts that were confirmed (the invite link was used) and are not switched off get one. If you are also one of the site's alert mail recipients, an exposure is not mailed twice.
- Every send is written to the organisation's audit log: to whom, which item and how, never what was found.
- Owners and admins can **Send a test security alert** to themselves (three in ten minutes at most).

Your own alerts need sign-in with accounts; on an install without them, the site's alert mail still works.

## What Skald can and cannot detect

- It **can** show who probed the server and what they asked for, what each probe was answered, attack strings and hammering in the log, fake browsers, what runs the site as seen from outside, and which known flaws apply to it.
- It **cannot** see inside a request or an answer (only the address, the size and the status), see what runs behind the page (a database, a plugin's version), tell that an attack succeeded, or block anything itself. Use the block list at your web server or CDN, and update what the advisories name.

## Days before Security

Security is counted from version 2.21 on. Older days show **Not recorded**, never 0. Your server admin can count them again from the raw log with `backfill` for the days the log still holds.

## Every figure is counted twice

Every figure on these tabs is counted a second time, by separate code, from the raw log; a day whose two counts differ is withheld. The addresses kept behind the rows are checked the same way.
