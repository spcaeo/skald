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

## What you can do with a to-do

- **Show the list** opens its rows under it. The address keeps it open, so a link brings the same list back.
- **Download CSV** saves the rows. A list longer than 1,000 rows says so; the CSV has the first 1,000.
- **Copy link** copies the address of this to-do, with its list open. The button turns into a green tick.
- **Send to team** mails the to-do to a member of the site's team, with its rows as a CSV attached and the link. It shows only when Skald has a mail server (Settings > This site > Mail & reports) and the team has a confirmed member; otherwise the page says why. Someone who opens the link without rights to the site sees "not available to you"; the CSV works for anyone.
- **Open in** goes to the tab that shows it.
- **Mark done** moves it to **Done, and did it work?**. From the next data update, Skald re-checks it on every whole day after the day you marked it, with the same measure: "Fixed: 0 not-found answers since 25 Oct", or "Not yet: 5 not-found answers since 25 Oct". **Undo** puts it back.
- **Not now** folds it away under **Not now**. **Put back** brings it back.

Under the done to-dos, **Pages you changed: did it work?** lists every page change marked on [Traffic > Pages](#traffic/pages), with its visits a day before and after and what Skald says. Select one to open the page with that change. See [Did my change work?](getting-started.md#did-my-change-work).

Marks are kept by Skald, so the whole team sees the same list. Only owners and admins can mark or send. Without accounts (signing in), the list shows but nothing can be marked or sent.

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
