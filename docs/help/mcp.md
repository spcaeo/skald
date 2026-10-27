# Ask an AI assistant about your traffic (MCP)

Connect Claude, ChatGPT or another AI assistant to Skald, so you can ask about your traffic in plain words. This guide covers the address to use, the token it needs, setup for each assistant, and what it can and cannot see.

## What MCP is

MCP (Model Context Protocol) is a standard way for an AI assistant to use outside tools, such as Skald.

Once connected, you can ask "How did last week compare with the week before?" and the assistant reads the answer from Skald. It does not guess.

## Before you start

You need three things:

- **MCP switched on for your server.** Whoever runs your Skald server turns it on. If it is off, the address below answers "MCP is not switched on here".
- **Team accounts.** MCP works only on servers where people sign in with their own accounts. It is not available on servers with one shared login.
- **A token for the assistant** (the MCP scope). Only an owner or admin can make one.

## Where to find it

Open **Settings > AI > AI assistants** (tab **MCP**), or go straight to [AI assistants](#settings/ai/assistants). Settings opens from the gear at the foot of the sidebar. The palette finds it too: type `mcp`.

The page first shows how it works, in four steps: choose the assistant, make a token, paste the command, test. Then come the **Connect an assistant** button, a few questions you can ask, the MCP address, and **Tokens for assistants**: the tokens already made for assistants.

**Connect an assistant** opens a dialog with **Read the MCP guide** (this guide) at the top, then one question, **Who will do it?**:

- **My AI agent.** Pick Claude Code, Codex, Cursor or another agent that runs commands. Skald writes one line for it. Paste the line into the agent: it takes a read-only token for this site, connects itself to Skald (for Claude Code, `claude mcp add ...`), checks it works, and reports back. The token never shows in the chat. See [Your AI agent, in every set-up dialog](connections.md#your-ai-agent-in-every-set-up-dialog).
- **Me.** One step, **Connect your assistant**, then **Test**. This guide has each part in full.

## The address to use

The MCP address is your dashboard's address, followed by `/traffic-mcp`:

```
https://analytics.example.com/traffic-mcp
```

Copy yours from **Settings > AI > AI assistants > MCP**: the address is on the page, under **Connect an assistant**. The dialog's **Connect your assistant** step has the Claude Code command and the Claude Desktop config too, with your token filled in.

> The address is the same for every site on your server. The token decides which sites the assistant may read.

## Make a token for the assistant

1. Open [AI assistants](#settings/ai/assistants) and press **Connect an assistant**, then **Me**. The dialog has one step, **Connect your assistant**, in three parts.
2. **Choose your assistant**: Claude Code, Claude Desktop, ChatGPT (API) or Other.
3. **Make the token.** Keep the **Name** it suggests, or type one, for example "Claude". Press **Make the token** and copy the token. It is shown only once, right there.
4. **The command or config** for the assistant you chose follows, with the token already in it. Paste it where it says.
5. Press **Next** to **Test** it. The test ends with the next step: what to ask your assistant first.

That token reads the site you are on, and sees no visitor addresses. For an assistant that reads several sites, press **New token** in **Settings > AI > AI assistants > Tokens & links** ([Tokens & links](#settings/ai/assistants?sub=tokens)): tick the **Sites**, and **AI assistant (MCP)** under **What it may do**.

Tick **Reading visitor addresses** there only if you truly need it. With it, the assistant can see visitor addresses in today's AI activity and look a person up (`find_person`: their visits, emails and names).

The token looks like `skald_<id>_<secret>`. In every step below, put your own token where you see `skald_<id>_<secret>`.

See [The read-only API](api.md) and [Connections](connections.md) for more on tokens.

## Connect Claude Code

Run this one command in your terminal:

```
claude mcp add --transport http skald https://analytics.example.com/traffic-mcp \
  --header "Authorization: Bearer skald_<id>_<secret>"
```

Then start Claude Code and type `/mcp` to see that `skald` is connected.

## Connect Claude Desktop

Claude Desktop needs a small helper to send the token, because Skald does not offer a sign-in screen (OAuth) yet. The common helper is `mcp-remote`, which needs Node.js on your computer.

1. In Claude Desktop, open **Settings > Developer** and press **Edit Config**. This opens `claude_desktop_config.json`.
2. Add Skald to it as below, with your own address and token.
3. Save the file and restart Claude Desktop.
4. Start a new chat and check that the Skald tools are listed.

```json
{
  "mcpServers": {
    "skald": {
      "command": "npx",
      "args": ["mcp-remote", "https://analytics.example.com/traffic-mcp",
               "--header", "Authorization:${SKALD_AUTH}"],
      "env": {"SKALD_AUTH": "Bearer skald_<id>_<secret>"}
    }
  }
}
```

> Claude's **Connectors** screen (Add custom connector) asks for a URL and, at most, OAuth details. It has no place for a token, so it cannot connect to Skald yet. Use the config file instead.

If you run the Skald server yourself, you can also connect over SSH without a token. The server docs explain how.

## Connect ChatGPT

Skald does not offer OAuth sign-in yet. ChatGPT can only use Skald where it lets you give the token yourself.

- **ChatGPT app (connectors, developer mode):** these screens ask for OAuth or no sign-in. They cannot send the token, so they cannot connect to Skald yet.
- **OpenAI API:** a developer can add Skald as a remote MCP server: set `server_url` to `https://analytics.example.com/traffic-mcp` and put the token, `skald_<id>_<secret>`, in the MCP tool's `authorization` field. OpenAI's [connectors guide](https://developers.openai.com/api/docs/guides/tools-connectors-mcp) (read 24 October 2026) says to "Provide this token using the `authorization` field of the MCP tool", and its example has the token alone, with no `Bearer` in front. The value is not stored, so send it in every request.

## Other MCP clients

Any MCP client works if it can do both of these:

- connect to a remote server over HTTP (often called "Streamable HTTP");
- send a custom header with every request.

Use the address above and the header `Authorization: Bearer skald_<id>_<secret>`. Skald answers each request with plain JSON and does not keep an event stream open.

## The tools it offers

The assistant chooses these tools itself. Dates are in your site's own time zone. With no dates, a tool uses the last 7 whole days: yesterday and the 6 days before it.

| Tool | What it answers |
| --- | --- |
| `list_sites` | The sites you may read, their views, and the days held |
| `overview` | Visits, pages read, AI fetches, search fetches, 404s, server errors, and the change against the period before |
| `breakdown` | Visits by country, source, campaign, landing page, device, browser, hour, operating system or referrer |
| `top_pages` | The pages people read most, with AI fetches of each |
| `ai_activity` | Which AI assistants and crawlers came, what they fetched, and visits that followed an assistant's link |
| `leads` | Leads from the website's forms, by type and by first source (totals only) |
| `funnel` | A saved funnel, or steps you name, over the last 7 days and today |
| `compare` | Two date ranges side by side, up to 400 days |
| `page_story` | One page since it was published: first Googlebot, first AI crawler, first person, first lead |
| `live_today` | Today so far, from the 2-minute snapshot (partial, never compared) |
| `data_quality` | Per day: whether the log was read whole and passed its checks |
| `site_health` | Open alerts, heartbeat uptime, errors today, late runs, page speed |
| `conversions` | Demos, forms, sign-ups and payments by stage: started, completed, abandoned, won, lost. The completed ones and the leads, by source, first touch, landing page, country, campaign, device or tool |
| `what_changed` | Summary's **What changed: is it working?**: visits by source and by landing page against the period before, with the biggest rise and drop. Only when both periods are whole |
| `todos` | **Overview > Insights**' to-do list: what to fix, its proof, what to do, and whether each is to do, marked done (fixed or not yet) or not now. Give an id for the list behind one to-do |
| `lost_pages` | **Site > Not found**: old addresses still asked for, the closest live page and the nginx or Apache line to copy; also the Markdown copies AI asked for, and the addresses marked fixed |
| `page_changes` | The changes marked with **+ Mark a change** on a page, and for each the days before against the days after: up, down, no clear change or too early to tell |
| `ai_readiness` | **Pages AI can't read well**, worst first; or one page's **AI readiness**: robots.txt for each main AI crawler, errors, the Markdown copy, the sitemap and the last AI read |
| `changed_pages` | Summary's **New and updated pages**: pages changed in the last 30 days, their visits and search visits since, and whether Google fetched them |
| `find_person` | One person by IP address, email, visitor ID or lead: their visits, leads and conversions. Only with **Reading visitor addresses**; each search goes to the audit log |
| `setup_left` | What is left to set up for a site: the site's open set-up lines on [To do](#settings/todo), each with its dialog's address, and the job an AI agent can do for it |
| `setup_line` | Makes the one set-up line for an AI agent, for the jobs you name. Only with **Set-up lines (AI agent)**; see below |
| `fix_todo` | One of **Overview > Insights**' to-dos with every row behind it (not only the 1,000 the page shows) and the steps to fix it in your site's own code or server. Without an id: the to-dos it can fix. See below |
| `mark_todo_done` | After a fix: keeps what the assistant changed (the exact change, the files, the rows left and why) beside the to-do, and with **done** marks it done. Only with **Set-up lines (AI agent)** for that one site |

It also offers a ready prompt, **weekly_report**, which asks the assistant for a short weekly report.

## Finish setting up a site with your AI agent

Your AI assistant can also finish a site's set-up for you. It asks Skald what is left (`setup_left`), makes the set-up line for the jobs it can do (`setup_line`), and then follows that line itself: the same line **Your AI agent** gives in each Set up dialog.

The jobs an AI agent can do: connect the server's log (**logs**), put the script tag on your pages (**script**), send leads from your forms (**lead**), the Next.js line in the web server's log format (**rsc**), find where your pages load their own files (**assets**), read your privacy notice and recommend what Skald keeps (**privacy**), and connect Google Search Console (**search**). The country file and the mail recipient stay with a person.

**The token.** Making a line needs one more permission. Only an owner or admin can give it:

1. Open [Tokens & links](#settings/ai/assistants?sub=tokens) (**Settings > AI > AI assistants > Tokens & links**), then **New token**.
2. Tick **one** site only.
3. Under **What it may do**, tick **AI assistant (MCP)** and **Set-up lines (AI agent)**. That one "can make set-up lines for an AI agent". It reads nothing by itself.
4. Press **Make token**, and connect your assistant with it as above.

Skald refuses this token for more than one site, without **AI assistant (MCP)**, or for someone who is not an owner or admin.

**Example.** Say to your assistant: "finish setting up kiwi.example". It then:

1. asks what is left: "kiwi.example: 5 of 5 needed set-up lines left, and 2 optional", with logs, script, lead and privacy as AI agent jobs, and the mail recipient for you;
2. makes the line for those four jobs: `finish setting up Skald for kiwi.example (...) — read <address>/traffic-kit/llms.txt and use code <code>`, which works once, for 24 hours;
3. follows it: takes its keys into a file (never into the chat), checks what is already done, changes only what is missing, and asks you before any change on your server;
4. asks again what is left. Each line ticks itself once Skald sees it working.

What it recommends for your privacy settings waits for you: press **Apply** in the dialog. The mail line stays yours: its dialog's address is in the answer.

## Fix your to-dos with your assistant

Say to your assistant, in the site's project folder or on its server: "Fix my Skald to-dos". It then:

1. asks which to-dos it can fix (`fix_todo` without an id): old pages to redirect, server errors, Markdown copies AI asks for, the sitemap address, pages people leave;
2. reads one with every row and its steps (`fix_todo` with the id). Rows are page paths and counts, never a visitor's address or email;
3. checks first where your site keeps its redirects or rules (nginx, Apache, Next.js, `vercel.json`, Netlify, WordPress, Cloudflare), changes only what is missing, touches nothing the to-do does not list, asks you before any change on a server, and tests it (`nginx -t`) before a reload;
4. reports it (`mark_todo_done`): the exact change shows beside the to-do on [Overview > Insights](#overview/insights), and **done** marks it done, so Skald checks it on the days after. That changes no figure; **Undo** there is one click.

Reading needs any token for the site. Marking done needs the same token as making a set-up line (above: **AI assistant (MCP)** and **Set-up lines (AI agent)**, one site, made by an owner or admin). Without it, the assistant tells you what it did, and you press **Mark done** yourself. No MCP? Press **Fix this > My AI agent** on the to-do instead: the same work, from one line. See [What to fix](what-to-fix.md).

## Two lines for each site

If you work on each site in its own folder, with its own Claude Code or Codex, connect each one once. Then one sentence sets the site up.

1. Open [Settings › Organisation › Sites](#settings/org/sites) and press **Set up many sites with your AI agent**.
2. On the site's card, press **Two lines (MCP)**, then **Make the token for <site>**. The token is for that one site only: it reads that site and makes set-up lines for it. It is shown once.
3. **Line 1.** Copy it into a terminal in that site's own folder.
   - Claude Code: `claude mcp add --transport http skald <your Skald>/traffic-mcp --header "Authorization: Bearer <token>"`. Claude Code keeps it to that folder, so each site's folder has its own token.
   - Codex: a line that adds a server named after the site (`skald-shop-example-com`) to `~/.codex/config.toml`.
4. **Line 2.** Say to the assistant: `Set up Skald for this site`. It asks Skald what is left, makes its line, and does the jobs, as above.

Do the same for each site. Ten sites can be set up at the same time: each site has its own token and its own line, and one site's line never ends another's.

Never paste the token into a chat message. See or remove it in [Tokens & links](#settings/ai/assistants?sub=tokens).

No MCP? Each site's card also has **Make its line**: one plain line to paste into that site's session. See [Set up many sites](connections.md#set-up-many-sites-with-your-ai-agent).

## Questions to try

- "Which sites can you see in Skald?"
- "How did last week compare with the week before?"
- "Where did our visits come from in the last 30 days?"
- "Which pages did ChatGPT fetch yesterday?"
- "What are our ten most-read pages this month?"
- "Was any day withheld last week, and why?"
- "How is the pricing page doing since it was published?"
- "How many demos were booked last month, and from which sources?"
- "Is the site healthy right now?"
- "What should we fix first this week, and did last week's fixes work?"
- "Which old addresses still get visits, and where should each one redirect?"
- "Did the change I made to the pricing page work?"
- "Can ChatGPT and Claude read our guides page?"
- "Which sources and landing pages rose or fell against the week before?"
- "Write a short weekly report for example.com."
- "What is left to set up for example.com?"

## How honest the answers are

Skald gives the assistant the same rules the dashboard follows:

- Visits are called "visits (an upper bound on people)". A visit count is at most the number of people, never a count of them.
- Totals use whole, checked days only. Withheld, partial and missing days are named by date and left out. They are never counted as zero.
- A figure that was not recorded is null, never 0.
- A change against an earlier period is given only when both periods are whole.

> If the assistant says a day was withheld, that day failed a check. See [FAQ](faq.md) for what that means.

## Safety

- **Read-only.** Every tool only reads, except `setup_line`, which makes a set-up line, and `mark_todo_done`, which keeps a to-do's report and marks it done; both only with a token that has **Set-up lines (AI agent)** for that one site. The assistant cannot change settings or delete data. Each line made and each to-do marked goes to the audit log.
- **Only your sites.** The token reads only your organisation's sites, and only the ones you ticked. Every tool checks this again on each call.
- **No addresses by default.** Without **Reading visitor addresses**, no answer carries a visitor's address, and the assistant cannot look a person up.
- **Turn it off at once.** To cut off an assistant, revoke its token: open **Settings > AI > AI assistants > Tokens & links**, find it under **Your tokens**, press **Revoke**, then **Yes, revoke**. It stops working immediately. The **MCP** tab lists the assistants' tokens too.
- **Tied to the maker.** If the person who made the token leaves the team or stops being an admin, the token stops too.
- **Keep the token secret.** It sits in your assistant's settings. Do not paste it into a chat or a shared file.

## If it does not connect

First press **Test** in the dialog's last step. It says in words what is wrong. Every answer is in [If a connection does not work](troubleshooting-connections.md).

| What you see | What to check |
| --- | --- |
| "MCP is not switched on here" | Ask whoever runs your server to switch MCP on |
| 401, "Unauthorized" | The token is wrong, revoked, or has no MCP scope. Make a new one with **Connect an assistant** |
| "this token is not for that site" | Make the token from that site's page, or tick that site under **New token** |
| 403, "this Origin may not call the MCP server" | You are calling from a web page. Use an assistant app or command line instead |
| 405 | The client tried to open an event stream. Pick the HTTP (Streamable HTTP) transport |

## Related guides

- [Connections](connections.md): the set-up dialogs, Tokens & links, and adding a site.
- [The read-only API](api.md): tokens and scopes in full.
- [Sign-in and team](sign-in-and-team.md): who is an admin.
- [Privacy](privacy.md): what holds visitor addresses.
