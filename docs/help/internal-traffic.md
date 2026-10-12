# Internal traffic: leave your own visits out

Tell Skald which internet addresses belong to you and your team, so your own visits do not count as visitors. This guide covers adding your address, adding a range by hand, removing one, and what changes in the figures.

## Why your own visits should not count

You and your team open the site all day: to check a page, test a form, or show a client. If those visits counted, your figures would look busier than they are. A new page would seem popular because you opened it ten times.

Skald keeps these visits apart. They are not deleted. They go into their own group, **our own traffic**, so the five groups still add up to everything in the server log. They are never counted as visitors or people.

## Where to find it

Open **Settings > This site > Internal traffic**, or go straight to [Internal traffic](#settings/internal). Settings opens from the gear at the foot of the sidebar.

The page is headed **Our own traffic**. The list of addresses is in the section **Internal addresses**.

## Add your own address

This is the quickest way. Do it once from each place you work: the office, home, a laptop on another network.

1. Open **Settings > This site > Internal traffic**.
2. Under **Internal addresses**, type a label in the box beside **Add my current address**, for example "Office Mac" or "Home".
3. Press **Add my current address**.
4. Check that the new line shows in the list.

Skald adds the internet address your browser is using right now. You do not need to know it or type it.

> Many home connections get a new address from time to time. If your visits start to show up as visitors again, add your current address again, or ask your internet provider for your range and add the range instead.

> On a VPN, the address added is the VPN's. Your visits count as yours only while you use that same VPN.

## Add an address or range by hand

Use this for a teammate who is not on your network, a test machine, or a whole office range.

1. Open **Settings > This site > Internal traffic**.
2. In **Address or range**, type one address, such as `192.0.2.10`, or a range, such as `198.51.100.0/24`.
3. In **Label**, type whose it is, for example "Berlin office".
4. Press **Add address**.

Both the address and the label are needed. A label can be up to 60 characters.

What you can enter:

- one IPv4 address, such as `203.0.113.5`;
- one IPv6 address;
- a range written with a slash, such as `198.51.100.0/24`.

A range may be at most `/16` wide for IPv4 and `/32` for IPv6. Wider ranges are refused, because they would hide real visitors.

> Ask your IT team or internet provider for your office range. Do not guess: a range that is too wide hides real visitors from you.

## Remove an address

1. Open **Settings > This site > Internal traffic**.
2. Find the line in the list and press **Remove**.
3. Press **Yes, remove**, or **Keep it** to change your mind.

From then on, visits from that address count as an ordinary visitor's again.

## The list

Each line shows the **Address or range**, its **Label**, and **Since**: the day it was added.

- The list holds at most 50 entries. When it is full, remove one before you add another.
- Some lines show a lock and the word **locked**. They were set on the server, in its config file, and can only be changed there. Ask whoever runs your server.
- The list applies to every site on your Skald server, not only the one you are looking at.

## What changes in the figures, and from when

An address counts as yours **from the moment you add it**. Nothing is recounted backwards.

- **From now on:** visits from the address go to **our own traffic**, in the live view and in every day collected after that moment.
- **Earlier today:** visits from before you pressed the button stay where they were counted.
- **Past days:** they stay exactly as they were. A past visit from a newly added address stays a visitor.
- **After you remove it:** visits from the address count as visitors again from that moment. Past days keep what they had.

This is on purpose. A day's figures never change after they are stored, so a report you sent last month still matches the dashboard today.

> Add your addresses on your first day with Skald, before you start testing the site. That keeps your early figures clean.

## Our machines and the heartbeat

The same page shows everything Skald counts as your own traffic, not only the addresses in the list:

- **Our own requests**: every request from your own machines and tools together.
- **By machine or tool**: each one by its label, such as the office, your own crawler, browser tests, or the heartbeat. Labels for tools are set on the server.
- **How fast the server answered**: server time per hour for the last whole day.

Uptime from the heartbeat, and every outage, is on [Site > Health](#site/health), under **Is the site up?**:

- **Uptime, from the heartbeat**: the heartbeat is one request every five minutes to your site. If it is answered, the site is up. A red day had a gap of more than 10 minutes or a failed answer: the site was down, or the heartbeat itself stopped.
- **Outages and heartbeat gaps**: each gap, with when it started, when it ended, and how many minutes it lasted.

You see the heartbeat parts only if your server runs a heartbeat.

## Who may change the list

It depends on how people sign in to your server.

| Server type | Who may add or remove | Who may see the list |
| --- | --- | --- |
| Team accounts | An install admin only, because the list applies to every site on the server | Install admins see every entry. Other admins see the entries added on their own sites, but cannot change them |
| One shared login | Admins | Everyone who signs in; viewers cannot change it |

On a server with team accounts, a viewer does not see the addresses at all. The page says the list is for admins, because it holds the addresses of the people who work on the site.

If the buttons are greyed out, hover over one to see why. Ask an install admin to add your address for you. See [Sign-in and team](sign-in-and-team.md) for roles.

## Privacy

Your team's list of addresses is shown only on this page and kept in the server's change log. Like every visitor's address, your team's requests also show, behind sign-in, in the last 6 hours of [Site > Requests](#site/requests). The list itself never appears in the data files, CSV downloads, the API or mail. Every add and remove is logged with who did it and when.

See [Privacy](privacy.md) for more.

## If something goes wrong

| Message | What it means |
| --- | --- |
| "Give it a label first" | Type a label before you press **Add my current address** |
| "Both an address (or range) and a label are needed" | Fill in both boxes |
| "is not an IP address or range" | Check the address for typing mistakes |
| "that range is too wide" | Use a narrower range: at most `/16` for IPv4, `/32` for IPv6 |
| "is already listed" | The address is in the list already, perhaps as a locked line |
| "The list is full" | Remove an entry first; the list holds 50 |
| "your address is not known here" | The server cannot see your address. Add it by hand instead |
| "Only an install admin can change this" | Ask an install admin |

## Related guides

- [Getting started](getting-started.md): the first things to set up.
- [Settings and retention](settings-and-retention.md): the other settings pages.
- [FAQ](faq.md): common questions about the figures.
