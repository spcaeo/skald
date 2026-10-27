# Organisations

Manage every organisation in one place: its sites, members, invites, keys and audit log, which sites each person sees, its privacy class, and archive or restore it without deleting anything.

This page comes with accounts. Open it at **Settings > Organisation > Organisations**, or [here](#settings/org/orgs).

## What you see

Each organisation is a card. The card shows:

- its name, and **This site's** on the organisation of the site you have open
- its state: **Active**, or **Archived**
- its privacy class: **Internal** or **Client** (see Privacy class, below)
- how many sites and members it has, and, on a hosted Skald that sells plans, its plan (**none** when it has none; elsewhere no plan is shown, and the privacy pill alone says Internal or Client)
- the names of its sites, and the day it was made

An install admin sees every organisation of the server. Anyone else sees the organisations they belong to, with only the sites they may see.

Type in the search box to find an organisation by its name or by one of its sites. Choose an order next to it: by name, by sites, by members, newest or oldest. Archived organisations always come last. The search and the order stay in the page's address, so a copied link opens the same list.

## One organisation

Select a card. Its details open in a drawer, with tabs:

- **Overview**: its sites and members, the requests of the last 7 days and the last day with data. A figure Skald did not record says **Not recorded**, never 0. The requests are shown only when two separate counts agree.
- **Sites**: each site, with a link to its dashboard. **Move a site here** brings a site from another organisation you manage. **Add a site** opens Add a site with this organisation chosen.
- **Members**: each member's role and the sites they see. Invite someone, change a role, remove someone, transfer ownership, or leave.
- **Pending invites**: resend or cancel an invite.
- **Settings**: the name, the privacy class, whether two-step sign-in is required, and whether the daily mail is on by default.
- **Keys**: the organisation's API and MCP tokens. Revoke one here; make new ones under **Settings > AI assistants > Tokens & links**.
- **Audit**: every change to the organisation, newest first.

The open organisation and its tab are in the page's address (for example `#settings/org/orgs?org=3&otab=members`), so you can copy the link and send it. The address names the organisation by its number, never by its name, and never holds an email. A link to an organisation you are not in says it is not available to you.

Owners and admins change things; viewers only look. Only an owner changes the sign-in rule, makes another owner or archives the organisation. Only an install admin makes an organisation or changes its privacy class.

## Make an organisation

An install admin selects **New organisation**, then:

1. Types its **Name**.
2. Chooses its **Privacy class**: **Internal** (the usual) or **Client**.
3. Chooses its **First owner**: **You**, or **Someone else** with their email. Someone else gets an invite by mail, or a link for you to pass on when mail is not set up.
4. Optionally ticks the sites to move in. This works only when you are the first owner, or the first owner already has an account.
5. Selects **Make the organisation**.

## Which sites each person sees

By default each member sees every site of the organisation. You can let an admin or a viewer see only some of them:

1. Open the organisation, then **Members**.
2. Next to the person, select **Change**.
3. Untick **Every site**, tick the sites they may see, then **Save**.

You can also choose the sites when you invite someone. The choice counts everywhere: the dashboard and its site switcher, a link typed by hand, the API and MCP tokens they make, and the mails. A token they made before the change stops reading the sites they no longer see.

An owner always sees every site. An admin cannot change their own sites; another admin or an owner does it.

## Ownership

An organisation always keeps one owner. So:

- the last owner cannot be removed, made an admin or a viewer, or leave
- **Transfer ownership** (Members tab) makes another member an owner and you an admin

## Privacy class

Each organisation is **Internal** or **Client**. An install admin sets it.

- **Internal**: when the server keeps everything (internal and enterprise installs), nothing on these sites is deleted by itself. This is the default, so nothing changes for an organisation until someone changes it.
- **Client**: these sites follow their own **Privacy** settings, even when the server keeps everything. Old detail is removed at the end of each window, as the settings say.

The site's **Settings > Privacy** page and the server's `skald doctor` both say which rule applies to the site. See [Settings and retention](settings-and-retention.md).

## Archive and restore

**Archive** pauses the organisation: each of its sites stops collecting. Its members, settings, keys and every figure stay. Nothing is deleted. The days while it is archived say **Not recorded**, never 0.

**Restore** starts collecting again from the next run. A site someone paused by hand before stays paused.

Both ask before they act, and both are in the audit log. Only an owner archives or restores. Deleting a site's data is a separate action on **Settings > Organisation > Sites**, behind its own confirm.

## On the server

The same actions exist as commands:

- `skald org show <org>`: its sites, members and rules
- `skald org archive <org>` and `skald org restore <org>`
- `skald org privacy <org> internal|client`
- `skald org transfer <org> <email>`
- `skald member sites <email> <site>...` (or `--all`)

## Related guides

- [Sign-in and team](sign-in-and-team.md): roles and invites.
- [Settings and retention](settings-and-retention.md): what each window keeps.
- [API](api.md): tokens for scripts.
