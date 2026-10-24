# Connections: send, read and connect

Settings > Connections is where a site's visits reach Skald from another server, a script reads your figures, and an AI assistant connects. This guide covers the three set-up dialogs, how to test each one, your tokens, and adding a site step by step, by one line to your AI agent or by hand.

## Where to find it

Open **Settings > Team & access > Connections**, or go straight to [Connections](#settings/api). Settings opens from the gear at the foot of the sidebar.

The page was called **API & tokens** before. Old links to it still work.

### Set up your site

For owners and admins, the page starts with **Set up example.com** (your site's name): the same list as on Overview, with every line of the site's set-up, each with its **Set up** button while it is left. Here it is always shown. Once every line is done it shows every tick and **All set**, so you can check the site's set-up at any time. **Hide on Overview** on Overview's copy of the list hides only that copy: this one stays. See [Set up your site](getting-started.md#set-up-your-site) for every line.

The **Lead hook tested** line is ticked only while no hook's last real lead was refused. When one was (say its signature did not match, because the tool signs with an old secret), the line says leads are not arriving, its Set up button opens the lead hook's dialog, and the cause and fix are under **For your server admin**.

### Links to a dialog

Each dialog has its own link, with its step: **Read your figures (API)** at step 2 is `#settings/api?conn=api&step=2`, and the checklist's script tag dialog is `#settings/api?setup=script&step=1`. Copy it from the address bar and send it to another owner or admin: it opens the same dialog, at that step or at the first step that still needs a choice. **Back** closes the dialog; closing it takes it out of the address. Someone who may not use the dialog (a viewer) sees the page with one line: "Not available to your role." The link a **Share with your developer** form makes is never in the address.

At the top are three cards. Each has a **Set up** button that opens a short dialog with steps. Press **Next** to go on and **Back** to go back.

| Card | What it is for |
| --- | --- |
| Send this site's visits to Skald | A site whose web server is not your Skald server: its log, or its events, must be sent to Skald. **Set up with your AI agent** on this card gives you one line for your agent instead (see [Add a site, step by step](connections.md#add-a-site-step-by-step)) |
| Read your figures (API) | A script or a spreadsheet that reads your figures as JSON |
| Connect an AI assistant (MCP) | Claude, ChatGPT or another assistant that answers questions about your traffic |

Below the cards is **Your tokens**: every token of your organisation.

### Who can use it

- **Owners and admins** use the dialogs and see the tokens.
- **Viewers** see what each part is for, and the address of the figures while signed in. Tokens and dialogs are for admins.
- **A server with one shared login** has no team accounts. The page says the dialogs need accounts. It keeps the server commands for tokens folded away under one heading. See [The read-only API](api.md), "Servers that use one shared login".

## Send this site's visits to Skald

Use this when the site's web server is not the server Skald runs on. If Skald reads the site's log in place already, you need nothing here.

The dialog has three steps: **Where it runs**, **Run one command** (or the way's own steps), **Test**. Cloudflare and Vercel or Netlify have a **Sending token** step and an **Install** step in place of **Run one command**; the script tag has **Install** only.

### Step 1: Where it runs

Step 1 first shows **What Skald found** for this site (see **Skald checks your site**, below), and chooses the way it suggests. **Save the host names and page assets to this site** puts the found host names (added to the ones the site has) and page assets in the site's settings. Then pick where the site runs, or keep the suggestion:

| Choice | When to pick it |
| --- | --- |
| My own server (nginx or Apache) | Recommended. With or without Docker. One command on the server |
| Cloudflare | Cloudflare serves the site. The Skald Worker sends a record of each request. Any plan works, the free one too |
| Vercel or Netlify | The platform sends its request logs to Skald (a "log drain"). Nothing to install |
| Only the script tag | In-page events only: clicks, forms, scroll. No server log, so no AI crawlers or bots |

A server log is the best source. The script tag alone never sees AI crawlers or bots.

### Step 2: Run one command

The steps for the way you chose, with the send address and the sending token filled in. You never make the token yourself: Skald makes it when the step opens (a token that can only add log lines to this one site, and cannot read anything). It shows in **Your tokens** as "Sending logs: <site>, <date>". The send address looks like this:

```
https://analytics.example.com/traffic-ingest/example.com
```

Every command has a **Copy** button.

**My own server: one command.** On the web server, run the command the step shows:

```
curl -fsSL https://analytics.example.com/traffic-kit/<code> | sudo bash
```

The link works once, for 24 hours, and holds this site's sending token. The installer finds the site's access log in nginx's or Apache's settings by itself, and asks only when it cannot tell. It uses Docker when the server has it, and a small service with Python 3.9 or newer when not. Running it again is safe. A used or expired link prints "This install link was used or has expired" and changes nothing: press **Make a new command**. Coming back to the step after the command was used makes a new one by itself. Opening the link in a browser (or a mail's link preview) only shows the command; it does not use the link up.

**Download as one file** gives the same installer as one file, `skald-install-<site>.sh`, with the token inside. Run it with `sudo bash skald-install-<site>.sh`. Add `--dry-run` to see what it would do without changing anything, `--log <path>` to name the log yourself, or `--yes` to answer nothing. It leaves two commands on the server: `sudo skald-ship-check` checks everything and changes nothing; `sudo skald-ship-uninstall` removes only what it installed.

**Email it to your server admin** sends the set-up pack (below). **Other ways: by hand with Docker / without Docker** keeps the same steps as plain commands, for a server where you would rather type each one.

The installer only reads the log. It never changes nginx, Apache or the website. The command and the file hold the token: send them only to the site's admin.

### Send set-up to someone: the set-up pack

**Send set-up to someone** (at the top of the site's **Set up** list, and in the logs and leads dialogs) mails one zip, `skald-setup-<site>.zip`, to up to 3 addresses, or downloads it. It holds:

- `START-HERE.md`: every case, step by step (own server, Cloudflare, Vercel or Netlify, only the script tag), then leads, then how to check it works.
- `CLAUDE.md` (and `AGENTS.md`): the same, written for an AI coding agent. Give the folder to Claude Code and say *Set up Skald from CLAUDE.md*. It keeps every key in environment variables, never in code or git.
- `secrets.env`, the installer, the script tag, and the lead files for PHP, Node, Python and WordPress.

**Include the keys** is ticked by default: the pack then holds this site's sending token and its lead secret (the one the site has, or a new one when it has none), so the person can finish without asking you. Treat that mail like a password: anyone with it can send data for this site. Delete it after the set-up. Untick it to send the pack without keys; the files then say where each key goes. Mailing needs mail set up on the server (**Settings > Mail**); without it, download the pack instead.

**Cloudflare.** Deploy the Skald Worker, give it the send address and the token (as a secret named `SKALD_TOKEN`), and add your site's route to it. The dialog lists each step. When nothing else has reached Skald for the site yet, Skald reads it as edge records.

**Vercel or Netlify.** In the platform's log drain settings, give the address and the header the dialog shows. Vercel needs a Pro or Enterprise plan; Netlify needs Enterprise.

**Only the script tag.** The tag goes in the `<head>` of every page; nothing changes on your web server. To serve it from your own domain instead, the step has the lines under **Advanced: serve it from your own domain**. See [The tracking script](tracking-script.md).

### Step 3: Test

The Test starts by itself when the step opens: Skald says what it received for the site, or why it refused it. It checks at once, then again every 5 seconds for up to 2 minutes. **Test connection** checks again.

| What you see | What it means |
| --- | --- |
| Waiting for the first lines... | Nothing has reached Skald yet. Open your site in a browser and wait a little |
| Connected: 1,240 lines received today, the last at 10:42 (2 min ago). | It works |
| Connected before: the last lines came at ... Nothing today yet. | It worked before. Open the site, then test again |
| Refused at 10:41: the token is not for this site. | Skald refused the lines. The fix is shown under it |
| Lines arrive, but none could be read | The log's format does not match the site's setting |

For your own server, a wrong answer also says: run `sudo skald-ship-check` on the web server, which checks each part and names the fix (an older zip kit has `sudo bash check.sh` in its folder instead), and where to see what the shipper says: `sudo docker logs --tail 20 skald-ship` with Docker, or `journalctl -u skald-ship -n 20` without. A set-up saved before 2.30 gets the same advice. Under the answer is a folded table, **Common problems, and the fix**. Every answer and its fix are in [If a connection does not work](troubleshooting-connections.md).

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

The quickest way is to let your AI agent do it. You copy one line from Skald and paste it into your agent. The agent reads Skald's steps, sets up the site, and reports back. You watch each step tick.

1. **Your site.** Type the site's address, as people type it. A whole link works too: `https://www.example.com/pricing` becomes the site `www.example.com`. The page shows the name it will use. Choose the time zone its days are counted in.
2. **Prove it's yours.** Add the DNS TXT record or the meta tag the step shows, then press **Check now**. A new DNS record can take a few minutes to show. Nothing is collected for the site until this is done, but you can go on now. When your server asks for no proof, the step says so.
3. **Your AI agent.** "Which AI agent are you using?" Pick one: **Claude Code**, **Codex**, **Cursor**, **Claude.ai or ChatGPT** (chat only), or **Another agent** (one that can run shell commands). No agent? Press **No AI agent: set it up by hand** (below).
4. **Send this line.** Skald writes one line for your agent, like this:

   ```
   set up Skald for example.com — read https://analytics.example.com/traffic-kit/llms.txt and use code •••••••••••• (works once, 24 hours)
   ```

   The code is hidden until you press **Show code**. Press **Copy** (it turns into a green tick), and paste the line where the step says:

   | Agent | Where to paste the line |
   | --- | --- |
   | Claude Code, Codex | In a terminal in the site's project folder, or on the site's server |
   | Cursor | In the site's project, in the chat, in Agent mode |
   | Another agent | In the site's project folder or on its server. It must be able to run shell commands there |
   | Claude.ai or ChatGPT | A chat in the browser cannot run commands on your server. So this step shows the one command to paste on the server yourself, as in Connections |

   **Make a new line** gives a new code. **Cancel this line** stops it at once. The step says until when the line works. Opened from a link straight at step 4, it asks you to press **Make the line** first, so an old link never ends a line your agent is already using.
5. **Watch it connect.** A list ticks itself while the step is open: your agent read the steps, it took the keys (with the time), it sent its report, and the first log lines arrived. When the agent says it added the script tag or a lead form, Skald also looks for the tag on your home page and waits for a test lead. When the first log lines arrive it says "Done: example.com is receiving visits", with **Open its dashboard**. **Finish later** closes the dialog.

Your agent asks you what it cannot find out alone: how the site is hosted, if the code does not say, and whether to keep visitors' IP addresses, for how many days, and the link to your privacy notice. It asks before it changes a server or your web server's settings.

### Is it safe to paste this into a chat?

The same box is under the line in step 4:

- Yes. The line holds a one-time code, not a password or a key.
- The keys come out once. When your agent takes them, the code can never give them again. A code nobody uses stops after 24 hours.
- Your agent is told to save the keys straight into a locked file and never show them in the chat. Skald gives them only to a command-line download such as curl, and turns away web readers and fetch tools, which could pass them into a chat.
- The keys work for this one site only. The sending key can only send log lines. The lead secret sends leads and can read back this site's lead list (reference, stage, time), never names, emails, addresses or visitor IDs. Neither can open your dashboard or see your visitors.
- Skald keeps only a scrambled copy of the code (a hash), never the code itself, and never writes it to a log.
- Until the keys are taken, treat the line like a house key: paste it only into your own agent. Changed your mind? Press Cancel this line and it stops at once. A new line also cancels an older one whose keys were not taken yet.
- If your site already has a lead secret, the agent gets that same one (unless your Skald keeps it in the server's settings; then the keys hold none). After the set-up you can remove the agent's sending key in Settings > Connections > Your tokens, and make a new lead secret in Settings > Integrations.

Your agent reads Skald's steps with `curl` too, so the code does not pass through a fetch tool. If it tries a web reader or a fetch tool for the keys, Skald refuses it and the keys stay unused. If it fetches the keys twice, the second try never overwrites the keys file it already has. After the keys are taken, the code still opens the steps, the installer and the lead files until it stops: none of them holds a key.

### Your agent took the keys

Step 5 says **Your agent took the keys at 10:42. The code is used up: it cannot give the keys again.** If it was not your agent, press **Cancel this line**, remove the key in **Settings > Connections**, under **Your tokens**, and make a new line.

### What your agent reported

When the agent is done, it sends Skald a short report, and step 5 shows it in plain words. Only the agent that took the keys can send it. If it sends a newer one (say after a fix), step 5 shows that one: how the site is hosted, the web server, the access log, what the site is built with, its page assets, where the script tag went, its lead forms, the privacy answers, the files it changed, and anything **Left for you**.

The report is a suggestion. Skald changes no setting by itself. When the agent found other page assets than the site has, **Use these page assets** saves them. Set the privacy answers yourself, in **Settings > Data retention > People**.

### When the line stops

| What step 4 or 5 says | What to do |
| --- | --- |
| This line ran out. | Nobody took the keys in 24 hours. Press **Make a new line** and send that one |
| Cancelled. This line no longer works. | You cancelled it. Make a new line when you are ready |
| The old line was cancelled. | You made a new line, so the older one stopped. Send the new one |
| This line was made before the page was reloaded, so it is not shown again. | Already sent it? Press **Next** to watch it connect. If not, make a new line, or cancel this one |

### Set it up by hand

On step 3, press **No AI agent: set it up by hand**. Steps 3 to 5 then become these. **Use an AI agent instead** takes you back.

3. **How visits reach Skald.** The same choice as in Connections: my own server (with or without Docker), Cloudflare, Vercel or Netlify, or only the script tag. The way Skald suggests is chosen already, marked **Recommended for** your site, with the reason under it.
4. **Install.** As in Connections: one command for your own server, with the token made for you, or the way's own steps. **Download as one file** and **Email it to your server admin** are there too.
5. **Test and finish.** The Test starts by itself. When lines arrive it says "Done: example.com is receiving visits", with **Open its dashboard**. If not, it shows the fix and the common problems. **Finish later** closes the dialog.

A site you added already can use its AI agent too: in **Settings > Connections**, press **Set up with your AI agent** on the **Send this site's visits to Skald** card. It opens the site's wizard at step 3.

### Skald checks your site

When you type the address in step 1, Skald looks at the site from outside, the way a browser does, and shows **What Skald found**:

| Line | What it says | Read from |
| --- | --- | --- |
| Server | nginx, Apache, LiteSpeed, Caddy or Microsoft IIS, and the system it names (like Ubuntu) | The site's `Server` header |
| Platform | Cloudflare (when its proxy is on), Vercel, Netlify, CloudFront, Fastly, GitHub Pages, or a hosted builder: Shopify, Wix, Squarespace, Webflow | Headers such as `cf-ray`, `x-vercel-id`, `x-nf-request-id`, `x-amz-cf-id` |
| Built with | Next.js, Nuxt, WordPress, Gatsby, Astro, or plain HTML | `X-Powered-By`, and the page's own folders like `/_next/static/` or `/wp-content/` |
| Host names | Both `example.com` and `www.example.com` when they are the same site, and which one sends visitors to the other | Both addresses are asked |

Each line has a tick, or says **could not tell**. Under them: the page assets it suggests for **Settings > This site > Sites > Page assets**, and the way it suggests, with one plain reason. For example: "example.com runs on its own nginx server (Ubuntu), so one command on that server sends its log."

A Next.js site on its own nginx, Apache or LiteSpeed server also gets one more line: add ` rsc_prefetch=$http_next_router_prefetch` at the end of the site's nginx `log_format` (Apache: ` rsc_prefetch=%{Next-Router-Prefetch}i`), then reload nginx. Without it, a page opened by a click inside the site is not counted, because Next.js loads it without an HTML request. `sudo skald-ship-check` on the server says whether the log has it. For a Next.js site this line is part of setting it up, not an extra.

**Is it safe?** Yes. The line only adds one header's value (`1`, or `-` when absent) to what nginx already writes in its own log file. It opens no port, adds no route and gives no one access; nginx escapes an odd value as it does for every other header; and the log already goes to Skald over HTTPS with the site's own token.

### Check a new site end to end

A site is ready when a real visit shows up the way you expect:

1. In a private window, open the site and click two links inside it. Within about 2 minutes, Overview shows the visit and Traffic › Visitors lists it with every page you clicked. On a Next.js site, if only the first page shows, the line above is missing.
2. Do the same on a phone on mobile data, in a new private tab (a tab that is already open shows the page from memory and sends nothing).
3. The site's **Set up** list (on Overview, and always at the top of Settings › Connections): every line is ticked, or marked optional on purpose.
4. If the site sends leads: a lead sent with `"test": true` is listed under Left out and not counted.

| What Skald sees | The way it suggests |
| --- | --- |
| nginx, Apache, LiteSpeed or Caddy, nothing in front | My own server (nginx or Apache): one command on that server |
| Cloudflare with its proxy on | Cloudflare (the Skald Worker sees every request, cached pages too) |
| Vercel or Netlify | Vercel or Netlify (its log drain) |
| CloudFront or Fastly in front of nginx or Apache | My own server: one command on the server behind it. Pages the CDN answers from its cache are not in that log |
| Shopify, Wix, Squarespace, Webflow, GitHub Pages | Only the script tag: Skald cannot read their server log |
| Microsoft IIS | Only the script tag: the one-command install is for Linux servers |
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

The wizard is in the address while it is open: `#settings/sitesadmin?setup=new&step=1` for a new site, `setup=example.com&step=3` for one already started. The agent you chose is there too (`agent=claude-code`, or `agent=hand` for by hand), and in step 5 the line being watched (`link=` and 16 letters and digits, a scrambled copy of the code). The line and its code are never in the address. **Back** closes it.

Until the site's first log lines arrive, its own address says so: **example.com is waiting for its first log lines** (with its own name), with the step it reached, the same **Continue setup** (or **Test the connection**) button, and a link to [If a connection does not work](troubleshooting-connections.md). A site removed in Add or remove sites says that it was removed instead: nothing is collected for it, and its data stays until an install admin purges it.

Each new step, way chosen, and finish is written to the audit log.

> If you choose Cloudflare for a new site that has received nothing yet, Skald sets its log format to edge records for you. This is written to the audit log too.

## Share with your developer

The form is in the address while it is open (`share=1` beside the dialog's own link), so a reload brings it back. The link it makes is never in the address.

Someone else may do the install: your web developer, or whoever runs your server. They need no sign-in. In the send dialog (step **Run one command**, or **Install** for the other ways), in Add a site (step 4) and in the Set up dialogs of the script tag and the lead hook, press **Share with your developer**:

1. Choose how long the link works: 1 day, 7 days (the default) or 30 days.
2. Press **Make the link**. Copy it: it is shown only here. **Send it by mail** opens your mail program with the link in it.
3. Your developer opens the link. It shows only that one task for that one site: the steps with everything filled in, the Copy buttons, the installer to download (for a server, **Download as one file**) and the **Test** button.

The token or secret is not in the link. Your developer presses **Show the secret** on the page: the secret is made at that moment and shown once. After that the page says it was shown already, and you make a new link if needed. For the lead hook, a new secret replaces the older one for that tool.

The links you made are listed under **Shared links** in Connections, with when they end, whether they were opened and whether the secret was shown. **Revoke** ends a link at once. A token made from a link stays in **Your tokens** (named "Shared link: ..."), where you can revoke it too.

Making, opening, showing and revoking a link are written to the audit log. The page keeps no visitor address and writes no secret to any log.

## Related guides

- [If a connection does not work](troubleshooting-connections.md): every answer of the Test, and its fix.
- [The read-only API](api.md): files, answers and scopes.
- [Ask an AI assistant about your traffic](mcp.md): each assistant in full.
- [The tracking script](tracking-script.md): the tag, and the two addresses it needs.
- [Sign-in and team](sign-in-and-team.md): who is an admin.
