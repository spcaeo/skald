# Sign-in and team

How to sign in, keep your account safe with two-step sign-in, and invite your team with the right role.

These pages come with accounts. If your server uses one shared login instead, its users are listed under **Settings > Organisation > People** (tab **Users**), and the server admin manages them.

## Sign in

1. Open your dashboard's address. The sign-in page opens.
2. Type your **Email** and **Password**.
3. Select **Sign in**.

Every password field has a **Show** button at its right edge. Select it to see what you typed, and **Hide** to cover it again. The password is always covered again before the form is sent.

### Keep me signed in

**Keep me signed in** is ticked by default. You then stay signed in for 14 days on that device, counted from your last use. Untick it on a shared computer: you are signed out when the browser closes. The **?** beside it says the same on the sign-in page.

Your organisation can set a shorter session length, in **Settings > Organisation > People > Sign-in rules**. See [Settings and retention](settings-and-retention.md).

### Too many tries

After 5 failed tries for one email address in 15 minutes, each new try waits 30 seconds. You are never locked out for good, so nobody can lock you out by guessing.

## Forgot your password

1. On the sign-in page, select **Forgot password?**.
2. Type the email address you sign in with.
3. Select **Send the link**.
4. Open the mail and follow the link. It works once, for 60 minutes.
5. Type a **New password** twice and select **Save the new password**.

The page says the same words whether or not the address has an account. No mail after a few minutes? Check the spam folder, or ask an admin of your team.

Saving a new password signs out every other session of your account.

> If your server cannot send mail, ask the person who runs the server. They can make a reset link for you.

### Password rules

- At least 12 characters.
- Not your email address.
- Not a common password.

## Two-step sign-in

Two-step sign-in asks for a 6-digit code from an app on your phone, after your password. Any authenticator app works.

### Turn it on

1. Go to **Settings > You > Your account**, or open [Your account](#settings/you/account).
2. Under **Two-step sign-in**, type your password and select **Turn on two-step sign-in**.
3. In your authenticator app, add an account and type the key the page shows. If your app takes an address instead, use the address shown.
4. Type the 6-digit code the app shows, then select **Confirm**.
5. The page shows 10 recovery codes. Select **Copy all** or **Download as text** and keep them somewhere safe.
6. Select **I have saved them**.

The recovery codes are shown only this once. Each one lets you sign in once if you lose your phone.

### Sign in with two-step sign-in

1. Type your email and password as usual.
2. In **Code**, type the 6 digits your app shows now, or one of your recovery codes.

Codes change every 30 seconds. If a code is refused, try the one the app shows now.

### Turn it off

1. Go to [Your account](#settings/you/account).
2. Under **Two-step sign-in**, type your password and select **Turn off**.

If your organisation requires two-step sign-in, the sign-in page asks you to set it up the next time you sign in.

> Lost your phone and your recovery codes? Ask the person who runs the server to turn two-step sign-in off for you.

## Your account

**Settings > You > Your account** changes only your own account. Everyone has this page, viewers too.

- **You**: your name, and the address and role you are signed in with. Select the **Name** row to change it: it opens in a panel with **Save name**.
- **Password**: type your current password and the new one twice, then select **Change password**.
- **Two-step sign-in**: turn it on or off.
- **Where you are signed in**: each browser, when it signed in and when it was last seen.

To end every other session, select **Sign out everywhere else**, then **Yes, sign them out**. Use this if you signed in on a computer you no longer use.

## Roles

A person has one role in each organisation.

| Role | May |
| --- | --- |
| Viewer | See every page of the organisation's sites and the team list. Change their own name, password and two-step sign-in. Changes nothing else. Cannot look a person up, and sees the left-out lists without names, emails or visitor IDs |
| Admin | All of that, plus: invite, remove and change members (not owners), make API tokens, read the audit log and Billing, change the site's settings, and look a person up (the search at the top: visits with their IP address, emails, names) |
| Owner | All of that, plus: make, change or remove owners, set the security rules, remove a site, and handle billing |

An organisation always keeps at least one owner.

Some settings apply to every site on the server, not only yours: the AI crawler rules, saved funnels, the internal-address list, the mail server and the log file paths. Only an **install admin** may change those. This is a flag the server admin gives to a person.

## Several organisations

People are given sites through organisations. By default everyone in an organisation sees all of its sites, with the role they have there; an owner or admin can let an admin or a viewer see only some of them (see [Organisations](organisations.md)). One person can be in several organisations, with a different role in each. On **Settings > Organisation > Organisations** an install admin sees and manages every organisation of the server.

When you are in two or more:

- The site switcher at the top of the sidebar lists your sites under each organisation's name, and so does **All sites**. With one organisation the list is plain, as before.
- Every **Settings > Organisation** page says at its top which organisation it is ("Organisation: Kiwi"), with **Switch** to open the same page for another one.
- **Settings > Organisation > People > Team** shows the team of the organisation that owns the site you have open. Its title names the organisation ("Team of Kiwi"), with the sites it sees ("These people see kiwi.example only.") and links to your other organisations' teams. Inviting someone there adds them to that organisation only.

### Give someone one site only

To let a partner or a client see one site and nothing else, the server admin puts that site in its own organisation, then you invite them there:

1. On the server: `skald org create "Kiwi"`, then `skald site assign kiwi.example --org kiwi`. The site's data, settings and address stay as they were.
2. Still on the server, make yourself a member of the new organisation too (`skald member invite you@example.com --role owner --org kiwi`, then follow the link and select **Join**), or you stop seeing the site.
3. Open the site, go to [People](#settings/org/people) and invite the person with the role they need.

The site's settings and its set-up progress move with it, and so do the tokens that read only that site, such as its log shipper's. A token for several sites, or for all of the old organisation's, stays where it was and no longer reads the moved site: make a new one in the new organisation if you need it.

## Invite people

You must be an admin or owner.

1. Go to **Settings > Organisation > People**, or open [People](#settings/org/people).
2. Under **Invite someone**, type the person's **Email**.
3. Pick a **Role**. Only an owner can invite another owner.
4. Select **Send invite**.

The person gets a mail with a link. It works once, for 7 days. On the invite page they pick a name and a password and select **Create account and join**. If they already have an account with that address, the button reads **Join** and the organisation's name. They keep their own password and sign in with it.

If mail is not set up on your server, the page says "Mail is not set up; send this link yourself." Copy the link and send it to the person yourself. They then choose a new password at their first sign-in, so you never know the password they go on to use.

### Pending invites

Open invites are listed under **Pending invites**, with who sent them and when they expire.

- **Resend** sends a new link and replaces the old one.
- **Cancel** stops the link at once.

### Change a role or remove someone

Under **Members**, each person's email, name, role, last seen and two-step sign-in are listed.

- To change a role, pick a new one in the **Role** list. It saves at once.
- To remove someone, select **Remove**, then **Yes, remove**. Their sessions for this organisation end at once.

You cannot change your own role or remove yourself. Viewers see the team list with every control turned off.

## Sign out

- Select the round **You** button at the foot of the sidebar, then **Sign out**.
- Or, on [Your account](#settings/you/account), select **Sign out of this browser**.

## Related guides

- [Getting started](getting-started.md)
- [Organisations](organisations.md): sites, members, privacy class, archive and restore.
- [Settings and retention](settings-and-retention.md)
- [API](api.md): tokens for scripts.
