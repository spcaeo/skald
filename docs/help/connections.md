# Connections: send, read and connect

How a site's visits reach Skald from another server, how a script reads your figures, and how an AI assistant connects. This guide covers the site's set-up lines on To do, the three set-up dialogs, how to test each one, your tokens, and adding a site step by step, by one line to your AI agent or by hand.

## Where to find it

These were one page, Connections (and API & tokens before that). Each part now has its own place in Settings. Settings opens from the gear at the foot of the sidebar.

| Part | Where it is | Link |
| --- | --- | --- |
| What is left on the site's set-up, and **Finish set-up** | Settings > To do | [To do](#settings/todo) |
| **Send this site's visits to Skald** and **Set up with your AI agent** | Settings > This site > Data > Send logs | [Send logs](#settings/site/data) |
| **Test a sample** | Settings > This site > Data > Test a sample | [Test a sample](#settings/site/data?sub=sample) |
| **Read your figures (API)** | Settings > AI > AI assistants > API | [API](#settings/ai/assistants?sub=api) |
| **Connect an AI assistant (MCP)** | Settings > AI > AI assistants > MCP | [MCP](#settings/ai/assistants) |
| **Your tokens**, **New token** and **Shared links** | Settings > AI > AI assistants > Tokens & links | [Tokens & links](#settings/ai/assistants?sub=tokens) |
| **Add a site** (two steps) | Settings > Organisation > Sites | [Sites](#settings/org/sites) |

Old links to Connections, API & tokens or the 2.40 pages still work. Each opens the page its part is on now: a link to the MCP dialog opens AI assistants, a link to the send dialog opens Send logs, and so on.

### Set up your site

For owners and admins, **Settings > To do** (also what Settings opens) lists what needs you now: the site's open set-up lines, and other things such as a site waiting for proof, a plan nearly used up, or an invite not accepted. Each row is one sentence and one button. Done lines fold into **N done**. When nothing is left it says "Nothing needs you. Everything is set up for example.com." The same set-up lines show on Overview; **Hide on Overview** hides only that copy. See [Set up your site](getting-started.md#set-up-your-site) for every line.

**Finish set-up (N left)** opens one dialog that asks **Who will do it?**:

- **Me**: the open lines, numbered. Press one to open its own steps.
- **My developer**: send it to a teammate or your server admin (see [Send set-up to someone](connections.md#send-set-up-to-someone-the-set-up-pack)).
- **My AI agent**: **What it does** (every job it can do, ticked; untick one to leave it out), then pick your agent: Skald makes one line for it in the same dialog and watches it work. See [Your AI agent, in every set-up dialog](connections.md#your-ai-agent-in-every-set-up-dialog).

The answers are always in this order: Me, My developer, My AI agent. Skald remembers your last answer in this browser and opens on it next time. A choice shows only when it fits: **My AI agent** when a line is a job your agent can do, **My developer** when a line needs work on a server or on the site. Each open line is a button as a whole: it opens the same dialog for that line only.

The **Lead hook tested** line is ticked only while no hook's last real lead was refused. When one was (say its signature did not match, because the tool signs with an old secret), the line says leads are not arriving, and opens the lead hook's dialog. The cause and fix are in it.

### Links to a dialog

Each dialog has its own link, with its step: **Read your figures (API)** at step 2 is `#settings/ai/assistants?sub=api&conn=api&step=2`, and the To do page's script tag dialog is `#settings/todo?setup=script&step=1`. **Finish set-up** is `#settings/todo?setup=finish` (one line's: `setup=finish-script`), with who does it once chosen: `by=me`, `by=dev` or `by=agent`. Copy it from the address bar and send it to another owner or admin: it opens the same dialog, at that step or at the first step that still needs a choice. The way you chose is in the link too: `agent=claude-code` (or `agent=hand` for by hand), and, while your agent works, `link=` and the line's 16 letters and digits (never the line or its code). **Back** closes the dialog; closing it takes it out of the address. Someone who may not use the dialog (a viewer) sees the page with one line: "Not available to your role." The link a **Share with your developer** form makes is never in the address.

There are three set-up dialogs, each on its own page. Each is a short dialog with steps. Press **Next** to go on and **Back** to go back.

| Dialog | Where | What it is for |
| --- | --- | --- |
| Send this site's visits to Skald | Data > Send logs | A site whose web server is not your Skald server: its log, or its events, must be sent to Skald. **Set up with your AI agent** gives you one line for your agent instead (see [Add a site, step by step](connections.md#add-a-site-step-by-step)). **Test a sample** (its own tab) checks that Skald can read a log before you send it (see [Test a sample of a log](connections.md#test-a-sample-of-a-log)) |
| Read your figures (API) | AI > AI assistants > API | A script or a spreadsheet that reads your figures as JSON |
| Connect an AI assistant (MCP) | AI > AI assistants > MCP | Claude, ChatGPT or another assistant that answers questions about your traffic |

**Your tokens**, every token of your organisation, is on **Settings > AI > AI assistants > Tokens & links**.

### Who can use it

- **Owners and admins** use the dialogs and see the tokens.
- **Viewers** see what each part is for, and the address of the figures while signed in. Tokens and dialogs are for admins.
- **A server with one shared login** has no team accounts. The pages say the dialogs need accounts. The **API** tab keeps the server commands for tokens folded away under one heading. See [The read-only API](api.md), "Servers that use one shared login".

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

**My developer**, in **Finish set-up** on **Settings > To do** (and in the logs and leads dialogs), mails one zip, `skald-setup-<site>.zip`, to up to 3 addresses, or downloads it. It holds:

- `START-HERE.md`: every case, step by step (own server, Cloudflare, Vercel or Netlify, only the script tag), then leads, then how to check it works.
- `CLAUDE.md` (and `AGENTS.md`): the same, written for an AI coding agent. Give the folder to Claude Code and say *Set up Skald from CLAUDE.md*. It keeps every key in environment variables, never in code or git.
- `secrets.env`, the installer, the script tag, and the lead files for PHP, Node, Python and WordPress.

**Include the keys** is ticked by default: the pack then holds this site's sending token and its lead secret (the one the site has, or a new one when it has none), so the person can finish without asking you. Treat that mail like a password: anyone with it can send data for this site. Delete it after the set-up. Untick it to send the pack without keys; the files then say where each key goes. Mailing needs mail set up on the server (**Settings > This site > Mail & reports**); without it, download the pack instead.

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
| Lines arrive, but none could be read | The log's format does not match the site's setting. [Test a sample](connections.md#test-a-sample-of-a-log) says which format the lines are in |

For your own server, a wrong answer also says: run `sudo skald-ship-check` on the web server, which checks each part and names the fix (an older zip kit has `sudo bash check.sh` in its folder instead), and where to see what the shipper says: `sudo docker logs --tail 20 skald-ship` with Docker, or `journalctl -u skald-ship -n 20` without. A set-up saved before 2.30 gets the same advice. Under the answer is a folded table, **Common problems, and the fix**. Every answer and its fix are in [If a connection does not work](troubleshooting-connections.md).

## Test a sample of a log

Can Skald read this log, and what would it count? **Test a sample**, in **Settings > This site > Data > Test a sample**, tells you now, not after the next daily run. It is for owners and admins.

1. Paste up to 200 lines of the log: the first lines of your web server's access log (nginx, Apache, Caddy), or of an export from Cloudflare, CloudFront, Fastly, Akamai, Vercel or Netlify.
2. Leave **Format** on **Detect it (auto)**, or choose the one you expect.
3. Press **Next**. Skald reads the lines with the same readers and the same rules as the daily run, with this site's settings. Nothing is stored.

The report says:

| Part | What it tells you |
| --- | --- |
| Format | The reader Skald picked, how sure it is, and how many lines each reader could read |
| Lines | How many lines it read, and the ones it could not, with the main reasons and up to 3 line numbers each. A line itself is never shown |
| Times | The first and last time in the lines, and the time zone they are written in |
| Hosts | The host names in the lines, and whether each is one of this site's |
| Skald's five groups | Real people, answer engines, search engines, bots and scanners, and your own traffic, for these lines. They add up to the lines read |
| Pages | The pages people viewed most |
| Warnings | What to fix before you send the log |

The warnings, and what to do:

| Warning | What to do |
| --- | --- |
| This looks like an error log | Use the access log, often `access.log` in the same folder |
| No line has a referrer | Every visit's source would be Direct. Add the Referer header to the log format |
| No line has a user agent | Skald cannot tell people from bots. Add the User-Agent header to the log format |
| No line carries a host name | Fine when the server serves one site. Otherwise add `$host` to the log format |
| Lines for `www.` are not one of the site's hosts | Add the host name in Settings > This site > Site > Names & time, or those lines are counted apart |
| This site is set to read another format | Set the site's log format to Detect it (auto) |
| No asset request is under the site's page assets | Set the site's page assets, or people show as bots |
| More than 1% of the lines cannot be read | A daily run would hold the day back. The reasons above say why |

The pasted lines stay in your browser and are sent once for the test. They are not kept, and they never go in the page address. The tab's link is `#settings/site/data?sub=sample`. A link never holds the lines: it opens the empty box.

On the server, the same test reads a whole file: `docker exec skald skald try-log /var/lib/skald/ingest/example.com/access.log --site example.com` (Docker), or `skald try-log <the log file>`. It reads the first 500 lines (`--lines` for more), plain or gzip.

## Read your figures (API)

On **Settings > AI > AI assistants**, tab **API**, press **Set up the API**. The dialog has three steps: **How it works**, **Token**, **Test**.

1. **How it works.** The base address and the list of files this site serves. Add a file's name to the base address, for example `overview`.
2. **Token.** Keep or change the name, and press **Make the token**. Copy it: it is shown only once. The curl command right under it has your token in it. The box **Can also read visitor addresses** is off by default. Turn it on only if a script truly needs the request log and AI activity, which hold visitors' IP addresses.
3. **Test.** Press **Test**. This browser asks for the site's `overview` file with the token, as a script would. "200: it works." means the token reads, and it names the first fields of the answer. Any other answer is said in words, with what to do. The test names the next step.

More on the files and the answers: [The read-only API](api.md).

## Connect an AI assistant (MCP)

On **Settings > AI > AI assistants**, tab **MCP**, the page shows how it works first, in four steps: choose the assistant, make a token, paste the command, test. Then press **Connect an assistant**. **Read the MCP guide**, at the top of the dialog, opens the full guide in a new tab. The dialog starts with **Who will do it?**: **Me** or **My AI agent**. Pick your agent (Claude Code, Codex, Cursor or another) and Skald writes one line for it: the agent connects itself to Skald with a read-only token for this site, and reports back. See [Your AI agent, in every set-up dialog](connections.md#your-ai-agent-in-every-set-up-dialog).

With **Me**, two steps follow: **Connect your assistant**, then **Test**.

1. **Connect your assistant**, in three parts. First choose your assistant: Claude Code, Claude Desktop, ChatGPT (API) or Other. Then make the token and copy it: it is shown once, right there. Then the command or config for that assistant, with the token already in it: the Claude Code command, the Claude Desktop config (it uses `mcp-remote`), or for ChatGPT what it can and cannot do today. If MCP is not switched on for your server, the dialog says so at the top. You can make the token anyway.
2. **Test.** Press **Test**. This browser starts an MCP session with the token and lists the tools, as an assistant would. "Connected:" with the number of tools means it works. The test then names the next step: what to ask your assistant first.

Each step in full: [Ask an AI assistant about your traffic](mcp.md).

## Your tokens

**Settings > AI > AI assistants > Tokens & links** ([Tokens & links](#settings/ai/assistants?sub=tokens)) lists every token of your organisation in one table. The **MCP** tab lists the assistants' tokens too.

| Column | What it shows |
| --- | --- |
| Name | The name given when it was made |
| What it is for | In words, from what it may do: Sending logs, Reading figures, Reading figures and addresses, AI assistant (MCP) |
| Sites | The sites it may use |
| Made | When, and by whom |
| Last used | When it was last used |

To stop a token, press **Revoke**, then **Yes, revoke**. Whatever uses it stops at once. This cannot be undone.

A token is shown only once, when it is made. Skald keeps only a fingerprint of it. If you lose one, revoke it and make a new one.

### New token

Press **New token**, the button beside the page title. It is for advanced use: any sites, and any mix of what the token may do.

1. Type a **Name**.
2. Under **Sites**, tick the sites it may use.
3. Under **What it may do**, tick one or more: **Reading figures**, **Reading visitor addresses**, **AI assistant (MCP)**, **Sending logs**.
4. Press **Make token**, copy it, then press **I have copied it**.

The set-up dialogs are simpler for one task.

### A quick look while signed in

**Quick look while you are signed in**, on **Settings > AI > AI assistants > API**, has the address of the figures in this browser, with no token, and the list of files this page serves.

## Add a site, step by step

Owners and admins add a site in two short steps. Open **Settings > Organisation > Sites** ([Sites](#settings/org/sites)) and press **Add a site**. The site picker at `/traffic/` has **+ Add a site** too.

1. **Your site.** Type the site's address, as people type it. A whole link works too: `https://www.example.com/pricing` becomes the site `www.example.com`. While you type, Skald looks at the site and says what it found in one line, for example **Runs on nginx · suggested: one command on the server**. The details are behind **What Skald found**. The time zone is your browser's (or the one Skald found); press **Change** to type another. Then answer **Who will connect it?**:
   - **Me**: Skald gives the steps and waits for the first visits.
   - **My developer**: Skald makes a private link with the steps, to send them.
   - **My AI agent**: one line for Claude Code, Codex or Cursor. You watch it work.

   Skald remembers your answer for the next site. Press **Next**: the site is added.
2. **Connect it.** Only the path you chose, with **Who connects it: Me. Change** at the top.
   - **Me**: the way Skald found is chosen (**Another way** shows the others, the found one marked **Recommended for** your site). For your own server the one command is made at once, with its token. Under it, Skald waits for the first visits by itself.
   - **My developer**: **Share with your developer** (see [Share with your developer](connections.md#share-with-your-developer)), and the same wait.
   - **My AI agent**: pick **Claude Code**, **Codex**, **Cursor**, **Claude.ai or ChatGPT** (chat only) or **Another agent**. Skald writes one line for your agent, and **Skald watches your agent** under it (below). To set it up yourself instead, press **Change** and choose **Me**.

When your server asks for proof that the domain is yours, a **Prove it's yours** step comes between the two: add the DNS TXT record or the meta tag it shows, then press **Check now**. You can go on without waiting. When no proof is needed, there is no such step.

When the first log lines arrive it says "Done: example.com is receiving visits", with **Open its dashboard**. **Finish later** closes the dialog; nothing is lost.

### The line for your AI agent

The line looks like this:

```
set up Skald for example.com — read https://analytics.example.com/traffic-kit/llms.txt and use code •••••••••••• (works once, 24 hours)
```

The code is hidden until you press **Show code**. Press **Copy** (it turns into a green tick), and paste the line where the step says:

| Agent | Where to paste the line |
| --- | --- |
| Claude Code, Codex | In a terminal in the site's project folder, or on the site's server |
| Cursor | In the site's project, in the chat, in Agent mode |
| Another agent | In the site's project folder or on its server. It must be able to run shell commands there |
| Claude.ai or ChatGPT | A chat in the browser cannot run commands on your server. So the step shows the one command to paste on the server yourself, as in Send logs |

**Make a new line** gives a new code. **Cancel this line** stops it at once. The step says until when the line works. Opened from a link, it asks you to press **Make the line** first, so an old link never ends a line your agent is already using.

**Skald watches your agent** ticks itself while the dialog is open: your agent read the steps, it took the keys (with the time), it sent its report, and the first log lines arrived. When the agent says it added the script tag or a lead form, Skald also looks for the tag on your home page and waits for a test lead.

Your agent asks you what it cannot find out alone: how the site is hosted, if the code does not say, and whether to keep visitors' IP addresses, for how many days, and the link to your privacy notice. It asks before it changes a server or your web server's settings.

### Is it safe to paste this into a chat?

The same box is under the line:

- Yes. The line holds a one-time code, not a password or a key.
- The keys come out once. When your agent takes them, the code can never give them again. A code nobody uses stops after 24 hours.
- Your agent is told to save the keys straight into a locked file and never show them in the chat. Skald gives them only to a command-line download such as curl, and turns away web readers and fetch tools, which could pass them into a chat.
- The keys work for this one site only. The sending key can only send log lines. The lead secret sends leads and can read back this site's lead list (reference, stage, time), never names, emails, addresses or visitor IDs. Neither can open your dashboard or see your visitors.
- Skald keeps only a scrambled copy of the code (a hash), never the code itself, and never writes it to a log.
- Until the keys are taken, treat the line like a house key: paste it only into your own agent. Changed your mind? Press Cancel this line and it stops at once. A new line also cancels an older one whose keys were not taken yet.
- If your site already has a lead secret, the agent gets that same one (unless your Skald keeps it in the server's settings; then the keys hold none). After the set-up you can remove the agent's sending key in Settings > AI > AI assistants > Tokens & links, under Your tokens, and make a new lead secret in Settings > This site > Leads & tools, tab Incoming hooks.

Your agent reads Skald's steps with `curl` too, so the code does not pass through a fetch tool. If it tries a web reader or a fetch tool for the keys, Skald refuses it and the keys stay unused. If it fetches the keys twice, the second try never overwrites the keys file it already has. After the keys are taken, the code still opens the steps, the installer and the lead files until it stops: none of them holds a key.

### Your agent took the keys

The watch says **Your agent took the keys at 10:42. The code is used up: it cannot give the keys again.** If it was not your agent, press **Cancel this line**, remove the key in **Settings > AI > AI assistants > Tokens & links**, under **Your tokens**, and make a new line.

### What your agent reported

When the agent is done, it sends Skald a short report, and the watch shows it in plain words. Only the agent that took the keys can send it. If it sends a newer one (say after a fix), the watch shows that one: how the site is hosted, the web server, the access log, what the site is built with, its page assets, where the script tag went, its lead forms, the privacy answers, the files it changed, and anything **Left for you**.

The report is a suggestion. Skald changes no setting by itself. Under it, **What your agent recommends** shows what the report suggests for Skald's own settings, each with **Apply**:

- **Page assets.** When the agent found other folders than the site has, Apply saves them, as **Count visits as people** does.
- **IP addresses.** When the agent read your privacy notice, Apply saves its choice (keep IP addresses, and for how many days, or keep none), as **Choose what is kept** does, then shows the wording for your notice.

Nothing is applied until you press Apply. The report also lists each job (done, already there, skipped, or left for you), and for leads each tool whose hook the agent set or left for you.

### When the line stops

| What Connect it says | What to do |
| --- | --- |
| This line ran out. | Nobody took the keys in 24 hours. Press **Make a new line** and send that one |
| Cancelled. This line no longer works. | You cancelled it. Make a new line when you are ready |
| The old line was cancelled. | You made a new line, so the older one stopped. Send the new one |
| The line was made before this page was reloaded, so it is not shown again. | Already sent it? Skald keeps watching it. If not, press **Make a new line**, or cancel this one |

### Set it up by hand

Choose **Me** in step 1 (or press **Change** in step 2 and choose it). The ways are the same as in Send logs: my own server (with or without Docker), Cloudflare, Vercel or Netlify, or only the script tag. **Download as one file** and **Email it to your server admin** are there too. If nothing arrives, the step shows the fix and the common problems (fold **Not connected yet?**).

A site you added already can use its AI agent too: in **Settings > This site > Data > Send logs**, or on **Settings > To do** with **Finish set-up**, the dialog asks **Who will do it?**: pick **My AI agent**.

### Your AI agent, in every set-up dialog

Every **Set up** dialog your agent can do starts with the app's one question, **Who will do it?**, with **Me**, **My developer** and **My AI agent** in that order (the answer you gave last is chosen already). These are: logs arriving, visits count as people (page assets), pages opened inside a Next.js site, the script tag, the lead hook, the privacy choice, and **Connect an AI assistant (MCP)**. Countries and mail stay by hand: a country file goes on Skald's own server, and each mail recipient confirms their own address.

- **My AI agent.** Pick Claude Code, Codex, Cursor or another agent that runs commands. (A chat in the browser cannot change your site, so it is not offered here.) Skald writes one line for that job, like `finish setting up Skald for example.com (add the script tag) — read https://<your Skald>/traffic-kit/llms.txt and use code <code>`. Paste it into your agent. The agent first checks what is already done, changes only what is missing, and asks you before any server change. Then **Watch your agent work** ticks each step, shows its report, and ends with **Done** when the report arrives (or, for logs, when the first log lines arrive).
- **My developer.** For logs, page assets, Next.js pages, the script tag and the lead hook: the set-up in one mail or one zip, as in **Finish set-up**. Not offered for privacy or MCP: those are yours to choose.
- **Me.** The dialog's own steps, as before, from step 2. **Back** on its first step returns to the question.

The answer is in the address as `by=me`, `by=dev` or `by=agent`; an older link with `agent=hand` opens **Me**.

The line works once, for 24 hours, as in [Add a site](connections.md#add-a-site-step-by-step). A site has one live line: a new one ends an older one whose keys were not taken.

**Finish set-up** on **Settings > To do**, with **My AI agent**, makes one line for every open line your agent can do. Its link is `setup=all`, with the jobs (`jobs=logs.script.lead`).

Your agent's recommendations for Skald's settings (page assets, IP addresses) wait for your **Apply**: see [What your agent reported](connections.md#what-your-agent-reported).

The jobs, and what your agent gets for each:

| Job | What your agent does | What it gets |
| --- | --- | --- |
| Connect the logs | Connects your server's log, as in Add a site | A sending key for this site |
| Add the script tag | Puts the tag once in your site's shared `<head>` | Nothing |
| Leads and tool webhooks | Calls Skald from your own forms, and connects Calendly, Cal.com, Typeform, Stripe, HubSpot or Zapier when your site uses them | The lead secret; a secret for each tool it connects |
| Add the Next.js log field | Adds one field to nginx's or Apache's log line, so pages opened inside a Next.js site count | Nothing |
| Find the page assets | Finds where your pages load their own files | Nothing |
| Check the privacy settings | Reads your privacy notice and suggests what Skald keeps | Nothing |
| Connect Google Search Console | Finds your Search Console property, makes Skald a robot account with gcloud if you agree and Skald has none, and tells you the one click left | Nothing; the robot's key goes from a file straight to Skald |
| Connect the AI assistant (MCP) | Connects your assistant to Skald, so you can ask about your traffic | A read-only key for this site's figures |

Your agent first checks whether each job is done already, and changes only what is missing. It asks you before it changes a server, your web server or your site. It never changes a setting in Skald: the page assets and the privacy answers it finds are shown to you, and **Apply** saves them.

For a booking, form or payment tool, your agent connects the tool itself only when it can reach the tool (its API, command line or MCP server, with a key you gave it). The tool's secret then goes from Skald straight into a locked file, or from the tool straight to Skald, never through the chat. A tool it cannot reach is left for you, with the clicks and the address filled in: you make or paste its secret in **Settings > This site > Leads & tools** (tab **Incoming hooks**) yourself. If Skald has a secret for a tool already, your agent leaves it, unless you say to replace it.

When a line stops before its keys are taken, every key it made is removed again.

**Google Search Console.** One Search Console key serves every site in this Skald, so only whoever runs Skald (an install admin) may set it. If that is you and Skald has no key yet, your agent can make a robot account in your Google Cloud project with `gcloud`, if you agree, and send its key file straight to Skald from the file, never through the chat. If Skald has a key already, it is kept. One click is always yours: in Search Console, **Settings > Users and permissions > Add user**, the robot's address, **Restricted**. Then **Apply** in the report connects the property. Bing has no way to make a key from a command: copy the API key from Bing Webmaster Tools (**Settings > API access**) into [Leads & tools › Search Console & Bing](#settings/site/leads?sub=search) yourself. That tab also has **Let your AI agent do it**.

### Set up many sites with your AI agent

Work on several sites? Each one gets its own line. Open [Settings › Organisation › Sites](#settings/org/sites) and press **Set up many sites with your AI agent**. You see every site of your organisation, with what is left on each.

- **Make its line** makes that site's line, for the jobs left on it. **Make a line for each site** makes one separate line per site in one go.
- **Show its line** shows the line to copy into the AI agent working on that site, and **Watch its agent work** ticks its steps.
- **Two lines (MCP)** makes a token for that one site and shows the two lines: connect the assistant, then `Set up Skald for this site`. See [Two lines for each site](mcp.md#two-lines-for-each-site).
- **Add several sites** takes several names at once (one per line, up to 25). Each is added as **Add a site** adds it, with the same checks and your plan's limit, and then shows in the list with its own line to make. A site that must prove its domain first shows that, with no line yet.

The lines never end each other, so ten sessions can set up ten sites at the same time. Each site keeps one live line: a new line for a site ends that site's older line whose keys were not taken. Its link is `lines=all`, or `lines=site.<site>` for one site's line; the line and its code are never in the link.

### Skald checks your site

When you type the address in step 1, Skald looks at the site from outside, the way a browser does, and shows **What Skald found**:

| Line | What it says | Read from |
| --- | --- | --- |
| Server | nginx, Apache, LiteSpeed, Caddy or Microsoft IIS, and the system it names (like Ubuntu) | The site's `Server` header |
| Platform | Cloudflare (when its proxy is on), Vercel, Netlify, CloudFront, Fastly, GitHub Pages, or a hosted builder: Shopify, Wix, Squarespace, Webflow | Headers such as `cf-ray`, `x-vercel-id`, `x-nf-request-id`, `x-amz-cf-id` |
| Built with | Next.js, Nuxt, WordPress, Gatsby, Astro, or plain HTML | `X-Powered-By`, and the page's own folders like `/_next/static/` or `/wp-content/` |
| Host names | Both `example.com` and `www.example.com` when they are the same site, and which one sends visitors to the other | Both addresses are asked |

Each line has a tick, or says **could not tell**. Under them: the page assets it suggests for **Settings > This site > Data > What counts**, and the way it suggests, with one plain reason. For example: "example.com runs on its own nginx server (Ubuntu), so one command on that server sends its log."

A Next.js site on its own nginx, Apache or LiteSpeed server also gets one more line: add ` rsc_prefetch=$http_next_router_prefetch` at the end of the site's nginx `log_format` (Apache: ` rsc_prefetch=%{Next-Router-Prefetch}i`), then reload nginx. Without it, a page opened by a click inside the site is not counted, because Next.js loads it without an HTML request. `sudo skald-ship-check` on the server says whether the log has it. For a Next.js site this line is part of setting it up, not an extra.

**Is it safe?** Yes. The line only adds one header's value (`1`, or `-` when absent) to what nginx already writes in its own log file. It opens no port, adds no route and gives no one access; nginx escapes an odd value as it does for every other header; and the log already goes to Skald over HTTPS with the site's own token.

### Check a new site end to end

A site is ready when a real visit shows up the way you expect:

1. In a private window, open the site and click two links inside it. Within about 2 minutes, Overview shows the visit and Traffic › Visitors lists it with every page you clicked. On a Next.js site, if only the first page shows, the line above is missing.
2. Do the same on a phone on mobile data, in a new private tab (a tab that is already open shows the page from memory and sends nothing).
3. **Settings > To do** lists nothing left for the site (and Overview's **Set up** list is ticked), or only lines marked optional on purpose.
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

Every line is a suggestion. **Use these** is on at first: the site is added with the found host names and page assets, and **Connect it** chooses the suggested way. Turn it off to use none of them, or change any of them later: the way in **Connect it** (**Another way**), the host names in **Settings > This site > Site > Names & time**, and the page assets in **Data > What counts**. **Check again** looks once more.

When the site cannot be reached (it is not live yet, or it turns automated visitors away), the card says so plainly. Nothing depends on the check: add the site and choose the way by hand.

How the check behaves:

- It asks only the site's home page, `https://<site>/` and `https://www.<site>/` (or without `www.`), with a `HEAD` request, then reads at most 256 KB of the page when the headers do not say enough. Each request waits at most 6 seconds and follows at most 3 redirects. It sends no cookie, and says it is Skald's site check in its user agent.
- It fetches only public addresses, over http or https on ports 80 and 443. A name that points to a private, local or cloud-metadata address is refused, and so is a redirect to one.
- An admin can ask for about 30 checks an hour, and one address is checked at most 6 times in 10 minutes. The server log keeps only the site's name and the outcome.
- The facts are kept with the set-up's progress, so **Finish setting up** shows them again.

### Continue later

Skald saves how far you got, on the server, for each site: the step, the way chosen, what the site check found, and which sending token was made (its id, never the token itself). Closing the dialog or the browser loses nothing.

A site with an unfinished set-up shows a button in **Settings > Organisation > Sites** and on the site picker:

| Button | What it means |
| --- | --- |
| Finish setting up | The set-up was not finished. Press it to carry on where it stopped, in the site's own organisation |
| No visits yet: test the connection | Set-up was finished, but nothing has reached Skald in 24 hours. Press it to open the Test step |

The wizard is in the address while it is open: `#settings/org/sites?setup=new&step=1` for a new site, `setup=example.com&step=2` for one already started. A link with no `step` opens the step the set-up reached. Who connects it is there too (`by=me`, `by=dev` or `by=agent`), the agent you chose (`agent=claude-code`), and the line being watched (`link=` and 16 letters and digits, a scrambled copy of the code). The line and its code are never in the address. Older links still open: `step=3`, `4` or `5` is **Connect it**, and `agent=hand` is **Me**. Closing the dialog takes these keys away.

Until the site's first log lines arrive, its own address says so: **example.com is waiting for its first log lines** (with its own name), with the step it reached, the same **Continue setup** (or **Test the connection**) button, and a link to [If a connection does not work](troubleshooting-connections.md). A site removed in Settings › Organisation › Sites says that it was removed instead: nothing is collected for it, and its data stays until an owner restores it or deletes its data (Settings and retention, "Pause, remove or delete a site").

Each new step, way chosen, and finish is written to the audit log.

> If you choose Cloudflare for a new site that has received nothing yet, Skald sets its log format to edge records for you. This is written to the audit log too.

## Share with your developer

The form is in the address while it is open (`share=1` beside the dialog's own link), so a reload brings it back. The link it makes is never in the address.

Someone else may do the install: your web developer, or whoever runs your server. They need no sign-in. In the send dialog (step **Run one command**, or **Install** for the other ways), in Add a site (**Connect it**, My developer) and in the Set up dialogs of the script tag and the lead hook, press **Share with your developer**:

1. Choose how long the link works: 1 day, 7 days (the default) or 30 days.
2. Press **Make the link**. Copy it: it is shown only here. **Send it by mail** opens your mail program with the link in it.
3. Your developer opens the link. It shows only that one task for that one site: the steps with everything filled in, the Copy buttons, the installer to download (for a server, **Download as one file**) and the **Test** button.

The token or secret is not in the link. Your developer presses **Show the secret** on the page: the secret is made at that moment and shown once. After that the page says it was shown already, and you make a new link if needed. For the lead hook, a new secret replaces the older one for that tool.

The links you made are listed under **Shared links** in **Settings > AI > AI assistants > Tokens & links**, with when they end, whether they were opened and whether the secret was shown. **Revoke** ends a link at once. A token made from a link stays in **Your tokens** (named "Shared link: ..."), where you can revoke it too.

Making, opening, showing and revoking a link are written to the audit log. The page keeps no visitor address and writes no secret to any log.

## Related guides

- [If a connection does not work](troubleshooting-connections.md): every answer of the Test, and its fix.
- [The read-only API](api.md): files, answers and scopes.
- [Ask an AI assistant about your traffic](mcp.md): each assistant in full.
- [The tracking script](tracking-script.md): the tag, and the two addresses it needs.
- [Sign-in and team](sign-in-and-team.md): who is an admin.
