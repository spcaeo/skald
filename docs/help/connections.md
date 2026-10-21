# Connections: send, read and connect

Settings > Connections is where a site's visits reach Skald from another server, a script reads your figures, and an AI assistant connects. This guide covers the three set-up dialogs, how to test each one, your tokens, and adding a site step by step.

## Where to find it

Open **Settings > Team & access > Connections**, or go straight to [Connections](#settings/api). Settings opens from the gear at the foot of the sidebar.

The page was called **API & tokens** before. Old links to it still work.

At the top are three cards. Each has a **Set up** button that opens a short dialog with steps. Press **Next** to go on and **Back** to go back.

| Card | What it is for |
| --- | --- |
| Send this site's visits to Skald | A site whose web server is not your Skald server: its log, or its events, must be sent to Skald |
| Read your figures (API) | A script or a spreadsheet that reads your figures as JSON |
| Connect an AI assistant (MCP) | Claude, ChatGPT or another assistant that answers questions about your traffic |

Below the cards is **Your tokens**: every token of your organisation.

### Who can use it

- **Owners and admins** use the dialogs and see the tokens.
- **Viewers** see what each part is for, and the address of the figures while signed in. Tokens and dialogs are for admins.
- **A server with one shared login** has no team accounts. The page says the dialogs need accounts. It keeps the server commands for tokens folded away under one heading. See [The read-only API](api.md), "Servers that use one shared login".

## Send this site's visits to Skald

Use this when the site's web server is not the server Skald runs on. If Skald reads the site's log in place already, you need nothing here.

The dialog has four steps: **Choose how**, **Sending token**, **Install**, **Test**.

### Step 1: Choose how

Step 1 first shows **What Skald found** for this site (see **Skald checks your site**, below), and chooses the way it suggests. **Save the host names and page assets to this site** puts the found host names (added to the ones the site has) and page assets in the site's settings. Then pick where the site runs, or keep the suggestion:

| Choice | When to pick it |
| --- | --- |
| A Linux server with nginx or Apache, with Docker | Recommended. A small container reads the access log and sends new lines. You download a kit and run one command |
| The same, without Docker | The same, as a small system service (systemd). Needs Python 3.9 or newer on the server |
| Cloudflare | Cloudflare serves the site. The Skald Worker sends a record of each request. Any plan works, the free one too |
| Vercel or Netlify | The platform sends its request logs to Skald (a "log drain"). Nothing to install |
| Only the script tag | In-page events only: clicks, forms, scroll. No server log, so no AI crawlers or bots |

A server log is the best source. The script tag alone never sees AI crawlers or bots.

### Step 2: Sending token

A sending token lets the shipper or the platform add log lines to this one site, and nothing else. It cannot read anything.

1. Keep the name it suggests, or change it. The name is what **Your tokens** shows.
2. Press **Make a sending token**.
3. Copy the token. It is shown only this once. The next step fills it in for you.

Already have a sending token for this site? Press **Next**. The steps then show `<token>` where it goes.

The script tag needs no token. That step just says so.

### Step 3: Install

The steps for the way you chose, with the send address filled in. The send address looks like this:

```
https://analytics.example.com/traffic-ingest/example.com
```

Every command has a **Copy** button.

**With Docker, or without Docker (the install kit).** Press **Download the install kit (.zip)**. The zip is named `skald-ship-<site>.zip`. On the web server:

1. Copy the zip to the server and unzip it.
2. Run `sudo bash install.sh`. It shows the web server's log files. Give the access log of your site. Then paste the token when it asks.
3. Open your site once in a browser.
4. Back in Skald, press **Next**, then **Test connection**.

The kit holds `install.sh`, `uninstall.sh`, `check.sh` and `README.txt`. The kit without Docker also holds the shipper itself. The installer only reads the log. It never changes nginx, Apache or the website. `sudo bash install.sh --dry-run` shows what it would do, without changing anything. `sudo bash uninstall.sh` removes only what the installer made.

> The zip holds no token by default. A box, off by default, says **Put the token in the zip (only if you will send the zip privately)**. Tick it only if you send the zip by a private road. Never send a token by email.

If the kit is not offered, the page says why. Each kit also has the same steps by hand, folded under **Without the kit**.

**Cloudflare.** Deploy the Skald Worker, give it the send address and the token (as a secret named `SKALD_TOKEN`), and add your site's route to it. The dialog lists each step. When nothing else has reached Skald for the site yet, Skald reads it as edge records.

**Vercel or Netlify.** In the platform's log drain settings, give the address and the header the dialog shows. Vercel needs a Pro or Enterprise plan; Netlify needs Enterprise.

**Only the script tag.** Your web server passes two addresses on to Skald, and the tag goes in the `<head>` of every page. See [The tracking script](tracking-script.md).

### Step 4: Test

Press **Test connection**. Skald says what it received for the site, or why it refused it. It checks at once, then again every 5 seconds for up to 2 minutes.

| What you see | What it means |
| --- | --- |
| Waiting for the first lines... | Nothing has reached Skald yet. Open your site in a browser and wait a little |
| Connected: 1,240 lines received today, the last at 10:42 (2 min ago). | It works |
| Connected before: the last lines came at ... Nothing today yet. | It worked before. Open the site, then test again |
| Refused at 10:41: the token is not for this site. | Skald refused the lines. The fix is shown under it |
| Lines arrive, but none could be read | The log's format does not match the site's setting |

With a kit, a wrong answer also says: run `sudo bash check.sh` on the web server. Under the answer is a folded table, **Common problems, and the fix**. Every answer and its fix are in [If a connection does not work](troubleshooting-connections.md).

## Read your figures (API)

The dialog has three steps: **Token**, **Use it**, **Test**.

1. **Token.** Keep or change the name, and press **Make the token**. Copy it: it is shown only once. The box **Can also read visitor addresses** is off by default. Turn it on only if a script truly needs the request log and AI activity, which hold visitors' IP addresses.
2. **Use it.** The base address, a curl command with your token in it, and the list of files this site serves. Add a file's name to the base address, for example `overview`.
3. **Test.** Press **Test**. This browser asks for the site's `overview` file with the token, as a script would. "200: it works." means the token reads, and it names the first fields of the answer. Any other answer is said in words, with what to do.

More on the files and the answers: [The read-only API](api.md).

## Connect an AI assistant (MCP)

The dialog has three steps: **Token**, **Connect**, **Test**.

1. **Token.** Make a token for the assistant and copy it. If MCP is not switched on for your server, the dialog says so at the top. You can make the token anyway.
2. **Connect.** The MCP address, the Claude Code command, the Claude Desktop config (it uses `mcp-remote`), and what ChatGPT can and cannot do today. Your token is filled in.
3. **Test.** Press **Test**. This browser starts an MCP session with the token and lists the tools, as an assistant would. "Connected:" with the number of tools means it works.

Each step in full: [Ask an AI assistant about your traffic](mcp.md).

## Your tokens

One table lists every token of your organisation.

| Column | What it shows |
| --- | --- |
| Name | The name given when it was made |
| What it is for | In words, from what it may do: Sending logs, Reading figures, Reading figures and addresses, AI assistant (MCP) |
| Sites | The sites it may use |
| Made | When, and by whom |
| Last used | When it was last used |

To stop a token, press **Revoke**, then **Yes, revoke**. Whatever uses it stops at once. This cannot be undone.

A token is shown only once, when it is made. Skald keeps only a fingerprint of it. If you lose one, revoke it and make a new one.

### Make a token by hand

Open **Make a token by hand** under the table. It is for advanced use: any sites, and any mix of what the token may do.

1. Type a **Name**.
2. Under **Sites**, tick the sites it may use.
3. Under **What it may do**, tick one or more: **Reading figures**, **Reading visitor addresses**, **AI assistant (MCP)**, **Sending logs**.
4. Press **Make token**, copy it, then press **I have copied it**.

The cards above are simpler for one task.

### A quick look while signed in

**Quick look while you are signed in**, folded at the foot of the page, has the address of the figures in this browser, with no token, and the list of files this page serves.

## Add a site, step by step

Owners and admins add a site in five short steps. Open **Settings > Organisation > Add or remove sites** ([Add or remove sites](#settings/sitesadmin)) and press **Add a site, step by step**. The site picker at `/traffic/` has **+ Add a site** too.

1. **Your site.** Type the site's address, as people type it. A whole link works too: `https://www.example.com/pricing` becomes the site `www.example.com`. The page shows the name it will use. Choose the time zone its days are counted in.
2. **Prove it's yours.** Add the DNS TXT record or the meta tag the step shows, then press **Check now**. A new DNS record can take a few minutes to show. Nothing is collected for the site until this is done, but you can go on and install now. When your server asks for no proof, the step says so.
3. **How visits reach Skald.** The same choice as in Connections: Docker, without Docker, Cloudflare, Vercel or Netlify, or only the script tag. The way Skald suggests is chosen already, marked **Recommended for** your site, with the reason under it.
4. **Install.** Make the sending token, then follow the steps and download the kit, as in Connections.
5. **Test and finish.** Press **Test connection**. When lines arrive it says "Done: example.com is receiving visits", with **Open its dashboard**. If not, it shows the fix and the common problems. **Finish later** closes the dialog.

### Skald checks your site

When you type the address in step 1, Skald looks at the site from outside, the way a browser does, and shows **What Skald found**:

| Line | What it says | Read from |
| --- | --- | --- |
| Server | nginx, Apache, LiteSpeed, Caddy or Microsoft IIS, and the system it names (like Ubuntu) | The site's `Server` header |
| Platform | Cloudflare (when its proxy is on), Vercel, Netlify, CloudFront, Fastly, GitHub Pages, or a hosted builder: Shopify, Wix, Squarespace, Webflow | Headers such as `cf-ray`, `x-vercel-id`, `x-nf-request-id`, `x-amz-cf-id` |
| Built with | Next.js, Nuxt, WordPress, Gatsby, Astro, or plain HTML | `X-Powered-By`, and the page's own folders like `/_next/static/` or `/wp-content/` |
| Host names | Both `example.com` and `www.example.com` when they are the same site, and which one sends visitors to the other | Both addresses are asked |

Each line has a tick, or says **could not tell**. Under them: the page assets it suggests for **Settings > This site > Sites > Page assets**, and the way it suggests, with one plain reason. For example: "example.com runs on its own nginx server (Ubuntu), so the log shipper kit is the way."

A Next.js site on its own nginx, Apache or LiteSpeed server also gets one more line: add ` rsc_prefetch=$http_next_router_prefetch` at the end of the site's nginx `log_format` (Apache: ` rsc_prefetch=%{Next-Router-Prefetch}i`), then reload nginx. Without it, a page opened by a click inside the site is not counted, because Next.js loads it without an HTML request. The install kit's `check.sh` says whether the log has it. For a Next.js site this line is part of setting it up, not an extra.

**Is it safe?** Yes. The line only adds one header's value (`1`, or `-` when absent) to what nginx already writes in its own log file. It opens no port, adds no route and gives no one access; nginx escapes an odd value as it does for every other header; and the log already goes to Skald over HTTPS with the site's own token.

### Check a new site end to end

A site is ready when a real visit shows up the way you expect:

1. In a private window, open the site and click two links inside it. Within about 2 minutes, Overview shows the visit and Traffic › Visitors lists it with every page you clicked. On a Next.js site, if only the first page shows, the line above is missing.
2. Do the same on a phone on mobile data, in a new private tab (a tab that is already open shows the page from memory and sends nothing).
3. Overview › Set up this site: every line is ticked, or marked optional on purpose.
4. If the site sends leads: a lead sent with `"test": true` is listed under Left out and not counted.

| What Skald sees | The way it suggests |
| --- | --- |
| nginx, Apache, LiteSpeed or Caddy, nothing in front | A Linux server with Docker (the shipper kit) |
| Cloudflare with its proxy on | Cloudflare (the Skald Worker sees every request, cached pages too) |
| Vercel or Netlify | Vercel or Netlify (its log drain) |
| CloudFront or Fastly in front of nginx or Apache | The shipper kit, on the server behind it. Pages the CDN answers from its cache are not in that log |
| Shopify, Wix, Squarespace, Webflow, GitHub Pages | Only the script tag: Skald cannot read their server log |
| Microsoft IIS | Only the script tag: the kit is for Linux servers |
| Nothing it can tell | Nothing: you choose |

Every line is a suggestion. **Use these** is on at first: the site is added with the found host names and page assets, and step 3 chooses the suggested way. Turn it off to use none of them, or change any of them later: the way in step 3, the host names and page assets in **Settings > Sites**. **Check again** looks once more.

When the site cannot be reached (it is not live yet, or it turns automated visitors away), the card says so plainly. Nothing depends on the check: add the site and choose the way by hand.

How the check behaves:

- It asks only the site's home page, `https://<site>/` and `https://www.<site>/` (or without `www.`), with a `HEAD` request, then reads at most 256 KB of the page when the headers do not say enough. Each request waits at most 6 seconds and follows at most 3 redirects. It sends no cookie, and says it is Skald's site check in its user agent.
- It fetches only public addresses, over http or https on ports 80 and 443. A name that points to a private, local or cloud-metadata address is refused, and so is a redirect to one.
- An admin can ask for about 30 checks an hour, and one address is checked at most 6 times in 10 minutes. The server log keeps only the site's name and the outcome.
- The facts are kept with the set-up's progress, so **Setup: step 3 of 5, continue** shows them again.

### Continue later

Skald saves how far you got, on the server, for each site: the step, the way chosen, what the site check found, and which sending token was made (its id, never the token itself). Closing the dialog or the browser loses nothing.

A site with an unfinished set-up shows a button in **Add or remove sites** and on the site picker:

| Button | What it means |
| --- | --- |
| Setup: step 3 of 5, continue | The set-up stopped at that step. Press it to carry on |
| No visits yet: test the connection | Set-up was finished, but nothing has reached Skald in 24 hours. Press it to open the Test step |

Until the site's first log lines arrive, its own address says so: **example.com is waiting for its first log lines** (with its own name), with the step it reached, the same **Continue setup** (or **Test the connection**) button, and a link to [If a connection does not work](troubleshooting-connections.md). A site removed in Add or remove sites says that it was removed instead: nothing is collected for it, and its data stays until an install admin purges it.

Each new step, way chosen, and finish is written to the audit log.

> If you choose Cloudflare for a new site that has received nothing yet, Skald sets its log format to edge records for you. This is written to the audit log too.

## Share with your developer

Someone else may do the install: your web developer, or whoever runs your server. They need no sign-in. In the send dialog (step Install), in Add a site (step 4) and in the Set up dialogs of the script tag and the lead hook, press **Share with your developer**:

1. Choose how long the link works: 1 day, 7 days (the default) or 30 days.
2. Press **Make the link**. Copy it: it is shown only here. **Send it by mail** opens your mail program with the link in it.
3. Your developer opens the link. It shows only that one task for that one site: the steps with everything filled in, the Copy buttons, the install kit and the **Test** button.

The token or secret is not in the link. Your developer presses **Show the secret** on the page: the secret is made at that moment and shown once. After that the page says it was shown already, and you make a new link if needed. For the lead hook, a new secret replaces the older one for that tool.

The links you made are listed under **Shared links** in Connections, with when they end, whether they were opened and whether the secret was shown. **Revoke** ends a link at once. A token made from a link stays in **Your tokens** (named "Shared link: ..."), where you can revoke it too.

Making, opening, showing and revoking a link are written to the audit log. The page keeps no visitor address and writes no secret to any log.

## Related guides

- [If a connection does not work](troubleshooting-connections.md): every answer of the Test, and its fix.
- [The read-only API](api.md): files, answers and scopes.
- [Ask an AI assistant about your traffic](mcp.md): each assistant in full.
- [The tracking script](tracking-script.md): the tag, and the two addresses it needs.
- [Sign-in and team](sign-in-and-team.md): who is an admin.
