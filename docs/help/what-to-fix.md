# What to fix: to-dos and lost pages

Skald lists what to fix on your site this week, worst leak first, each with its proof and the full list behind it. It also finds the old addresses people, search engines and AI still ask for, suggests the closest live page for each, and gives you the server line to copy. Everything comes from your server log; Skald never changes your web server.

## To do now

Open [Overview > Insights](#overview/insights). The to-do list sits above the cards that say what changed. Each to-do has:

- **A title** that says what to do, and a tag (Lost traffic, Broken, AI, Search, Leaving).
- **Proof:** the figure and the days it covers, for example "288 old page addresses answered 'not found' from 21 Oct to 24 Oct".
- **Do:** what fixes it.
- **Skald will check:** the measure Skald re-checks once you mark it done.

A to-do shows only when its figure passes a threshold over the last whole days (up to 30, not today). The kinds:

- **Send old pages somewhere useful:** old page addresses that answered "not found" to people, search engines or AI.
- **Fix the server errors:** 5xx answers, by address.
- **Give AI the Markdown copies it asks for:** AI fetchers asked for the `.md` copy of pages you have.
- **Fix the sitemap address crawlers ask for:** a sitemap file search engines or AI crawlers asked for that is not there.
- **Make a page lead somewhere:** a page many visits started on, where nearly every one left after that page and no form was sent (from the stored visits).

## Fix this: who will do it?

Each to-do has one main button, **Fix this**. It asks one question, **Who will do it?**, and shows only what your answer needs. Above the list, **Fix all (N)** asks the same for every open to-do an AI agent can fix. The address keeps your choice (`fix=1&fixby=agent`, `me` or `someone`), so a link or a reload opens the same dialog.

- **My AI agent** (Claude Code, Codex, Cursor, or another agent that runs commands). Skald makes one line, for example `fix the Skald to-do "Send old pages somewhere useful" for example.com — read <address>/traffic-kit/llms.txt and use code <code> (works once, 24 hours)`. Press **Copy** and paste it into your agent, in the site's project folder or on its server. Your agent then:
  1. fetches every row of the to-do from Skald itself, with curl, into a locked file. Nothing to download, nothing to copy. It gets page paths and counts only, never a visitor's address or email;
  2. checks first: where does your site keep its redirects or rules (nginx, Apache, Next.js, `vercel.json`, Netlify, WordPress, Cloudflare)? What is already there?
  3. changes only what is missing, touches nothing the to-do does not list, asks you before any change on a server, and tests it (`nginx -t`) before a reload;
  4. reports back. The dialog shows each step as it happens, and the agent's report: **Done**, **Partly done** or **Left for you**, the exact change it made (with a copy icon), the files, and the rows it left for you and why.

  A **Done** report marks the to-do done, so Skald starts checking it on the days after. That changes no figure, and **Undo** is one click. The report also shows on the to-do itself.
- **Me.** The exact lines to paste for your web server, from every row (not only the 1,000 the page shows): the redirect lines for old pages, one rule for the Markdown copies, the sitemap line. Skald picks nginx or Apache from what its site check found; switch it if that is wrong. **Copy the lines** or **Download the lines**, and the CSV is a small link under them. When you are done, press **Mark done**.
- **Someone else.** Send it to a member of the site's team: the mail has the to-do, its rows as a CSV and the link that opens it. It needs a mail server (Settings > This site > Mail & reports) and a confirmed teammate; otherwise the dialog says why and gives you the link to copy. Someone who opens the link without rights to the site sees "not available to you".

**Is the line safe to paste into a chat?** Yes. It holds a one-time code, not a password. The code gives your agent a key that can only read the paths and counts of the to-dos in that line, for that one site, and send back what it changed. Everything stops after 24 hours, or at once with **Cancel this line**. The worst a leaked line can do is mark one of those to-dos done, which changes no figure and is undone with one click. Skald never puts a code in a mail.

## What else you can do with a to-do

- **The copy icon by the title** copies the address of this to-do, with its list open. It turns into a green tick.
- **Show the list** opens its rows under it. The address keeps it open, so a link brings the same list back.
- **See it in** goes to the tab that shows it.
- **Mark done** moves it to **Done, and did it work?**. From the next data update, Skald re-checks it on every whole day after the day you marked it, with the same measure: "Fixed: 0 not-found answers since 25 Oct", or "Not yet: 5 not-found answers since 25 Oct". **Undo** puts it back.
- **Not now** folds it away under **Not now**. **Put back** brings it back.
- **Check again** asks now whether it is fixed. See below.

## Check again: is it fixed now?

Made a fix and want to know at once? Press **Check again** on the to-do (it is in **Fix this** too, under **Me**). Skald runs that to-do's own check now and shows the answer in place:

- **Fixed:** "Fixed: all 12 addresses now answer 301 to a live page". The to-do moves to **Done, and did it work?** as **Fixed**. Skald made that mark, not you, so there is no Undo: a later check that finds an address broken again puts the to-do back the way it was.
- **Partly fixed:** "3 of 12 addresses still answer 404". **Show the 3 not fixed** lists them, each with what it answers now. The address keeps that list open (`tdchk=lost-pages`), so a link opens it.
- **Not fixed** or **Could not check** (your site did not answer): nothing changes.
- **Can't check yet:** the to-do comes from visits, not from an address Skald can ask. It is judged on whole days of visits after you mark it done.

How each kind is checked:

| To-do | Check again | Fixed when |
| --- | --- | --- |
| Send old pages somewhere useful | Skald asks each old address | it answers 410, it redirects to a page that answers, or the page is live again. A redirect to another site counts; Skald never follows it there |
| Give AI the Markdown copies | Skald asks each `.md` address | it answers with the copy, or redirects to the page |
| Fix the sitemap address | Skald asks each sitemap address | it answers, or redirects to a sitemap that does |
| Fix the server errors | Skald asks each address once | it answers without a server error. The daily re-check keeps counting the log, since an error can come and go |
| Make a page lead somewhere | not asked | judged on the whole days of visits after you mark it done |

Each check also reads your newest log lines since you marked the to-do done (at most a day back): "In the log since 14:10: none of these addresses answered 404". A fix made after the mark leaves older failures in the log, so the live answer decides.

Skald asks politely: at most 50 addresses a check (**Check the next 50** goes on), one at a time, with a short wait between them and a time limit; with its own user agent (`site-todo-check`), which Skald counts as its own, never as a visitor or a bot; HEAD requests, no cookies, and it reads no page. **Check all again**, above the list, checks every to-do Skald can ask, one after the other, and shows how far it is. A site can have 30 checks an hour, and each to-do one a minute.

When your AI agent reports a to-do done, Skald runs the same check straight away and shows its answer beside the agent's report.

Only owners and admins press **Check again**; a viewer sees the answers. Each check is a row in the audit log ("todo.checked"), without the addresses. A **Fixed** mark is counted twice too: a separate count reads the answers Skald kept and must find every address fixed, or the to-do shows as done, not fixed, with why.

**New to-dos.** A to-do that came onto the list in the last 7 days is new. The page says "N new to-dos your AI agent can fix" above the list, with one button that opens **Fix this > My AI agent**. The summary mail says the same and links to that dialog (never with a code: you make the line when you press). A webhook can say it too: tick `todo.new` under **Outgoing webhooks** in [Leads & integrations](#settings/site/leads). It sends the to-do's title, proof, figures and link, never a code or a row.

Under the done to-dos, **Pages you changed: did it work?** lists every page change marked on [Traffic > Pages](#traffic/pages), with its visits a day before and after and what Skald says. Select one to open the page with that change. See [Did my change work?](getting-started.md#did-my-change-work).

Marks are kept by Skald, so the whole team sees the same list. Only owners and admins can mark, send, or make a line for an AI agent. Without accounts (signing in), the list shows but nothing can be marked or sent; **Fix this > Me** still gives the lines to paste.

## Lost pages

Open [Site > Not found](#site/notfound). At the top, **Old addresses still asked for** covers its own last 30 whole days, not the date range in the top bar. Scanner and hacking paths (`/.env`, `/wp-login.php`) are never listed. Three tabs:

- **Lost pages:** each old page address, most asked for first, with how many times people, search engines and AI asked, the **closest live page** Skald found and how close it is:
  - **Same page:** the same address written another way (a capital letter, a missing slash, `index.html`, a broken link with junk on the end).
  - **Same topic:** most of its words match a live page.
  - **Loose:** only its section is still live. Check it before you use it.
  - **No good match:** nothing close; answer 410 gone.
- **AI asks for Markdown:** the `.md` addresses AI asked for whose page is live, and the other `.md` copies of old pages.
- **After the fix:** each address you marked fixed, with what came for it on the whole days after the mark: not-found answers, and the times it was served as a page. Zero not-found answers after the mark: fixed.

A **410 gone** is your own answer, so it counts as dealt with: an address that answers 410 leaves the lists, and a 410 is never counted as a not-found answer. A **redirect** counts as fixed wherever it goes, to a page on your site or to another site, because it leaves no not-found answer behind. An address you redirected stays on **Lost pages** until its last not-found answer is older than the 30 days shown; the re-check and **After the fix** already say fixed.

## The line to copy

Pick **nginx** or **Apache**. Each row has the line to add: a 301 redirect to the closest live page, or 410 gone. When a redirect is suggested, the 410 line is under it, so you can choose. Point at a line to copy it; the icon turns into a green tick.

```
location = /old-page/ { return 301 /new-page/; }
Redirect 301 /old-page/ /new-page/
```

**Download the nginx lines** (or **Download the Apache lines**) saves every suggested line for your server as one file, with loose matches marked. Check each one before you add it. Once a line is on your server, select **Mark fixed** on its row; the address moves to **After the fix** on the next data update.

## How the figures are checked

Every to-do and every lost-page figure is counted twice: once by the page's own code and once by a separate count straight from the stored days. A figure the two counts disagree on is not shown; the page names what was left out.
