# If a connection does not work

What to do when a site's visits do not reach Skald, or a script or an AI assistant cannot connect. This guide covers check.sh, the common problems, and what every answer of a Test means.

## Start with check.sh

If the site sends its log with the install kit (with Docker, or without Docker), run this on the web server first, in the kit's folder:

```
sudo bash check.sh
```

It changes nothing. It checks each part in turn and prints one line for each:

- `✓ OK` when that part works;
- `✗ PROBLEM`, with a `fix:` line under it that says what to do;
- `? CANNOT TELL` when it could not find out.

It checks, in this order: Docker (the Docker kit only), the web server, the access log and who may read it, whether the log is growing, whether www writes to that log, whether Skald's send address can be reached, the saved token file, whether the shipper is running, the shipper's last lines, and whether lines are leaving.

Fix the first problem it names, then run it again.

At the end is a block that starts **Copy this and send it to us**. Send that block to whoever runs your Skald server, or to us. It holds no token, and every IP address in it is masked.

> Lost the kit? Download it again from [Connections](#settings/api) > **Send this site's visits to Skald** > **Install**. `check.sh` is in every kit.

## Common problems

The same table is under the Test in the dialog, folded as **Common problems, and the fix**.

| What you see | Likely cause | Fix |
| --- | --- | --- |
| Refused: the token is wrong or was revoked (401) | The token was mistyped, cut short, or revoked in Your tokens. | Make a new sending token, run sudo bash install.sh again and paste it. |
| Refused: the token is not for this site (403) | The token was made for another site. | Make a sending token from this site's own page. |
| Nothing received: the shipper is not running | The container or service stopped, or install.sh did not finish. | Run sudo bash check.sh from the kit. It says what stopped. Then run sudo bash install.sh again. |
| Nothing received: a firewall | The server may not open HTTPS connections out to Skald. | Allow outbound HTTPS (port 443) to Skald's address. check.sh tests it: a 401 without a token means the path works. |
| Nothing received: the wrong log file | The shipper reads a file the website does not write to. | check.sh shows the file and the server blocks that write to it. Run install.sh again with the right path. |
| Nothing received: the log is not growing | Nobody visited yet, or the site logs somewhere else. | Open the site in a browser, then test again. If the file still does not grow, find its access_log line. |
| Visits from another host name | www and another host share one log file. | Give www its own access_log file (README.txt says how), then run install.sh again. |
| Refused: too many batches (429) | The shipper sent many batches at once, usually right after it started. | Nothing to do. The shipper slows down and sends the rest. |
| Refused: the site is not verified (403) | The site waits for proof that the domain is yours. | Finish step 2 of the site's set-up (Settings > Add or remove sites). |
| Docker is missing | The kit with Docker needs Docker on the web server. | Install Docker, or choose The same, without Docker, and download that kit. |
| Pages opened inside a Next.js site are not counted | The log does not record Next.js's prefetch header, so a click cannot be told from a prefetch. Only the first page of each visit counts. | Add one line to the site's log format (below, "Next.js sites"). check.sh and Overview's checklist say when it is missing. |
| The site check could not reach the site | The site is not live yet, turns automated visitors away, or its name points to a private address, which Skald never fetches. | Choose the way by hand in step 3: nothing else depends on the check. Press Check again once the site is live. |

## Next.js sites: pages opened inside the site

On a Next.js site, a click on a link inside the site loads no new page from your server. The browser asks only for the next page's data, an address that ends in `?_rsc=...`. Next.js asks for the same addresses to get links on screen ready (a prefetch), even when nobody clicks them. A plain log cannot tell the two apart, so Skald counts none of them, and only the first page of each visit shows. Nothing is guessed.

Next.js marks a prefetch with a header. Add one field at the very end of the site's nginx `log_format`, inside its quotes:

```nginx
 rsc_prefetch=$http_next_router_prefetch
```

For Apache, add this to the end of its `LogFormat`:

```apache
 rsc_prefetch=%{Next-Router-Prefetch}i
```

Then check and reload:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

From then on, a page opened inside the site counts as a page view, and a prefetch never does. Lines written before stay as they were. **Set up** on Overview's **Pages opened inside the site are not counted yet** has the same steps, a Copy button, **Share with your developer**, and a Test that waits until lines with the field arrive. Caddy already logs the header: nothing to add. The Vercel and Netlify log drains carry no headers, so there these pages are still not counted.

## What the Test of a log says

In **Send this site's visits to Skald**, step **Test**, and in the last step of **Add a site**, **Test connection** gives one of these answers.

| Answer | What it means |
| --- | --- |
| Waiting for the first lines. Nothing has reached Skald yet. | No batch has arrived. It checks again every 5 seconds for up to 2 minutes. If nothing comes, see Common problems above |
| Connected: N lines received today, the last at 10:42 (2 min ago). | It works |
| Connected before: the last lines came at ... Nothing today yet. | Lines came on an earlier day. Open the site in a browser, then test again |
| Lines arrive, but none could be read | Batches reach Skald, but no line is in a format the site reads. Set the site's log format to Detect it (auto) in Settings > Add or remove sites |
| The log endpoint is switched off on this server. | Ask whoever runs Skald's server to switch the log endpoint on (ingest.enabled) |
| The site is not verified yet, so nothing is collected for it. | Finish step 2 of the site's set-up (prove the domain is yours) |
| Refused at 10:41: ... | Skald refused the last batch. The reason and the fix are in the next table |

Skald notes only the newest refusal for each site, and at most one a second. It never keeps an IP address, a token or a log line for this.

### Why a batch was refused

| Skald says | What to do |
| --- | --- |
| No token was sent. | The shipper sent no token. Run install.sh again and paste the sending token. |
| The token is wrong or was revoked. | The token is wrong or was revoked. Make a new sending token, then run install.sh again and paste it (or put it in the platform's setting). |
| The token is not for this site. | The token was made for another site. Make a sending token for this site. |
| The token is not a sending token (it has no ingest scope). | That token cannot send logs. Make a sending token (Sending logs) for this site. |
| The site is not verified yet, so nothing is collected for it. | Finish step 2 of the site's set-up (prove the domain is yours). Nothing is lost: the shipper keeps the lines. |
| The site was removed. | The site was removed. Stop the shipper (sudo bash uninstall.sh). |
| This server does not process this site. | This Skald does not process the site. Check the site name in the send address. |
| Too many batches at once. The shipper slows down and catches up. | Nothing to do: the shipper waits and sends the lines a little later. |
| Today's limit of log data is used up. The shipper sends the rest later. | Nothing to do: the lines are sent after midnight UTC. Ask for a bigger daily limit if this happens every day. |
| Over the plan's limit. | Choose a bigger plan in Settings > Billing. Nothing is lost. |
| The organisation is read-only (billing). | Settle the bill in Settings > Billing. Nothing is lost. |
| Skald's server is short of disk space. The shipper tries again later. | Ask whoever runs Skald's server to free disk space. Nothing is lost. |
| The site's log format does not match what was sent. | Set the site's log format to Detect it (auto) in Settings > Add or remove sites. |
| The batch was malformed. | Update the shipper: download the kit again and run install.sh. |
| The batch was too large. | Update the shipper: download the kit again and run install.sh. |
| Accounts are not set up on Skald's server. | Ask whoever runs Skald's server: accounts must be on for log sending. |
| The log endpoint is switched off on Skald's server. | Ask whoever runs Skald's server to switch the log endpoint on (ingest.enabled). |
| Refused. | Run check.sh from the kit and send us its last block. |

The shipper keeps every line it could not send and tries again, so a refusal loses nothing once it is fixed. A refused post from the Cloudflare Worker is not sent again.

## What the Test of the script tag says

When you chose **Only the script tag**:

| Answer | What to do |
| --- | --- |
| Connected: N events on a day, the counters last written at ... | It works |
| Connected: a page opened with the tag at ... No event is counted yet. | The tag loads. Events follow when people click, scroll or start a form |
| Waiting for the first event. | Open a page of the site in a normal browser window, with Do Not Track and Global Privacy Control off |
| The script tag is switched off on this server. | Ask whoever runs your Skald server to turn it on |

While nothing has arrived, the Test also looks at your home page and says what it found there:

| What Skald found on your home page | What to do |
| --- | --- |
| The tag is on your page, and its events go to ..., which reaches Skald. | The page is right. Test in a normal browser window without an ad blocker. A browser that opened the site in the last day may still run the older script: empty its cache or use a private window |
| The tag is not on your home page. | Add the line from step 2 to the `<head>` of every page, then publish |
| The tag is not in the HTML ... The page loads Google Tag Manager. | Publish the Tag Manager container, with the tag firing on All Pages |
| The tag is on your page but posts to www.example.com/traffic-beacon, which answers 308. | An older tag or script that posts to your own site. Copy the tag again from step 2, or pass `/traffic-beacon` on to Skald from your server |
| ... its script answers 404. | You serve the tag from your own domain, and your server does not pass `/traffic-js/` on to Skald. Use the tag from step 2, or add the lines in "Advanced: serve it from your own domain" |
| Your page is at ..., which is not one of the site's host names. | Add that host name in Settings > Sites |
| ... Content-Security-Policy does not let it send to ... | Add your Skald server's address to `connect-src` |
| Skald could not open ... | Check the address opens in a browser |

In the browser's developer tools, Network panel, a request to `traffic-beacon` answered 204 or 202 means the tag works. 403 means the page's host is not one of the site's host names. A request to your own site's `/traffic-beacon` answered 308, 404 or 405 means an older tag or script. See [The tracking script](tracking-script.md).

## What the API test says

In **Read your figures (API)**, step **Test**:

| Answer | What to do |
| --- | --- |
| 200: it works. | Nothing. It also names the first fields of the answer |
| 401: the token is wrong, revoked, or not for this site. | Make a new token for reading figures |
| 403: refused. | The token may not read this |
| 404: the file is not there yet. | The figures appear after the first daily run |
| 429: too many requests. | Wait a minute and test again |
| No answer | Skald's address could not be reached from this browser |

More: [The read-only API](api.md), "Errors".

## What the MCP test says

In **Connect an AI assistant (MCP)**, step **Test**:

| Answer | What to do |
| --- | --- |
| Connected: N tools. | It works |
| 401: the token is wrong, revoked, or has no MCP scope. | Make a new token for the AI assistant |
| 403: this browser's address is not allowed to call MCP. | The token may still be fine: try it in your assistant |
| 404: MCP is not switched on here. | Ask whoever runs your Skald server to switch it on: `mcp.enabled` in the config, or `SKALD_MCP=true` on Docker |
| 405: the request was not a POST. | The client must post each request (Streamable HTTP) |
| No answer | Skald's address could not be reached from this browser |

More: [Ask an AI assistant about your traffic](mcp.md), "If it does not connect".

## Still stuck?

- Run `sudo bash check.sh` again and send its last block.
- Say which way you chose (Docker, without Docker, Cloudflare, Vercel or Netlify, or the script tag), and the exact words of the Test's answer.
- Never send the token itself.

## Related guides

- [Connections](connections.md): the dialogs, step by step.
- [The tracking script](tracking-script.md): the tag and its two addresses.
