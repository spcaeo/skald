# Accounts (sessions mode)

With `access.mode: sessions`, people sign in to the dashboard with their own
email address and password, instead of one shared nginx password. This page
says who can do what, how people join, and how the parts are kept safe.
Setting it up on a server: [DEPLOY.md](../DEPLOY.md), "Sessions mode
(accounts)".

Basic mode (`access.mode: basic`, the default) is unchanged: nginx asks for
the password, `users.json` holds the roles.

## Organisations, sites and roles

An install holds **organisations**. Each site belongs to exactly one
organisation. A person can be a member of several organisations, with one
role in each:

| Role | Can |
| --- | --- |
| `viewer` | Read every page of the organisation's sites. See the team list. Change their own name, password and two-step sign-in. |
| `admin` | All of that, plus: invite, remove and change members (not owners), API tokens, the audit log, read the internal addresses added on their own sites' pages, and look a person up (2.4.0, below). |
| `owner` | All of that, plus: make, change or remove owners. An organisation always keeps one enabled owner. |

One more flag, **install admin**, is per person, not per organisation. It is
for settings that apply to every site on the server: the AI crawler policy,
the funnels file and the internal-address list (adding or removing an
address, or seeing all of them, including the config file's). The first
owner made by `skald accounts init` is an install admin. The install always
keeps one.

Membership is read on every request: removing a member, or disabling a
person, ends their access at once.

## Private data: looking a person up (2.4.0)

The person search (`GET <page>/people?q=`, the box in the top bar, Ctrl K)
shows addresses, user agents, emails and names. It is for **owners and
admins** of the site's organisation only; a viewer gets 403 and sees no
search box. In basic mode the role is `users.json`'s (`admin` or `owner`).
An API token needs the `read_private` scope (`/traffic-api/v1/<site>/people?q=`,
and the MCP tool `find_person`). Every search writes one audit row, action
`people.search`, target the site, detail the kind of value (ip, email, vid,
lead), a SHA-256 prefix of it and how much was found: never the value
itself. In basic mode the same line goes to `privacy.log` beside the history.

The lists of what the figures leave out (`<page>/people/left-out`,
`<page>/people/conversions?kind=cancelled|removed|test`) are for every
member; names, emails and visitor IDs in them only for owners and admins.
`skald conversions mark-test` writes `conversions.test` or
`conversions.untest` rows (actor `cli`).

## Signing in

- Passwords: at least 12 characters, not the email address, not a common
  password. Stored as scrypt hashes only.
- A session is a random cookie (`skald_session`: HttpOnly, Secure,
  SameSite=Lax), 14 days from its last use. Only its SHA-256 is stored.
  "Sign out everywhere" (Settings > Your account) ends all other sessions.
- Every change the page makes is a same-origin POST that also carries the
  session's `X-Skald-CSRF` value.
- After 5 failed sign-ins for one email or one address in 15 minutes, each
  further try waits 30 seconds (answer 429). There is never a lock-out:
  nobody can lock the owner out by guessing.

## Invites

An admin enters an email and a role (Settings > Team, or `skald member
invite`). The link is valid 7 days and works once. A newer invite for the
same address replaces the older one ("resend"); an admin can cancel it.

- **Mailed link** (SMTP set up): the person picks a name and a password and
  is signed in.
- **Link shown to the admin** (no SMTP, or the mail failed; or printed by the
  CLI without a mail): the admin passes it on by hand. The person picks a
  password on the invite page, but is not signed in, and at the first
  sign-in must choose a new password. So an admin who opened the link "to
  help" does not know the password the person goes on to use. Without mail
  nothing can prove the address belongs to that person: the install trusts
  the admin who passes the link on. Set up mail to remove that trust.
- **The address already has an account:** joining only adds the
  membership. The link never signs anyone in; they sign in with their own
  password.

## Forgotten passwords

"Forgot password?" mails a link valid 60 minutes, used once, at most 3 an
hour per address. The page says the same words whether or not the address
has an account. Using the link sets the new password and ends every
session of that person.

On the server, `skald account reset-link EMAIL` makes a link whenever asked
(not limited to 3 an hour) and writes who made it to the audit log. Without
mail, this is how a person gets back in.

## Two-step sign-in

Optional per person (Settings > Your account): a 6-digit code from any
authenticator app (RFC 6238, 30 seconds), asked after the password. Turning
it on needs the current password, then a code from the app, then shows 10
one-time recovery codes once. Turning it off needs the password.
`skald account totp-off EMAIL` turns it off for someone who lost the phone
and the codes.

## API tokens and scopes

Tokens belong to an organisation and read only its sites (or the sites
named). They look like `skald_<id>_<secret>`; the secret is shown once, only
its hash is kept. Admins make them in Settings > API & tokens, or on the server
with `skald token create NAME --scope ...`.

| Scope | Lets the token |
| --- | --- |
| `read` | Read the data files over `/traffic-api/v1/<site>/<file>` ([API.md](API.md)). |
| `read_private` | Also read the files that hold addresses (`requests`, `ai_activity`), and look a person up (`people?q=`, MCP `find_person`). |
| `mcp` | Use the MCP endpoint `/traffic-mcp` ([MCP.md](MCP.md)). |

A token made in the page records who made it. It works only while that
person is enabled and still an owner or admin of the organisation:
disabling, demoting or removing them stops their tokens at once (checked on
every use). Tokens made on the server (`skald token create`, or moved in
from `tokens.json`) are not tied to a person. Revoking a token stops it for
good.

## The audit log

Every change is one row that is never edited: who (a person or `cli`), what,
to whom, when. Sign-ins and failed sign-ins, invites, role changes,
removals, password and two-step changes, resets, tokens, sites given to an
organisation, person searches (`people.search`) and test marks
(`conversions.test`, `conversions.untest`). No password, token, link or
address is ever written, nor the value a person search looked for. Admins
read their organisation's rows in Settings > Audit log (filter, CSV), or from
`GET /traffic/<site>/settings/audit`; on the server, `sqlite3` on the accounts file.

## Settings in the dashboard

Retention, mail, SMTP, sites and the organisation's security rules are changed under
Settings by admins, install admins and owners: see [SETTINGS.md](SETTINGS.md).

## Command line

For servers without a browser. Run as the skald user with
`./bin/skald --config /etc/skald/config.yml`. Every change is audited
with the actor `cli`.

| Command | Does |
| --- | --- |
| `accounts init --org NAME --owner-email EMAIL [--map NAME=EMAIL] [--base-url URL] [--force]` | First set-up, from basic mode (DEPLOY.md). |
| `accounts status` | Mode, schema, people, install admins, sessions, each organisation's members, invites, tokens and sites. |
| `org list` / `org create NAME` / `org rename SLUG NAME` | Organisations. |
| `member list` / `member invite EMAIL --role R` / `member role EMAIL R` / `member remove EMAIL` | Members of one organisation (`--org SLUG` when there are several). |
| `account reset-link EMAIL` | A set-your-password link, valid 60 minutes. |
| `account disable EMAIL` / `account enable EMAIL` | Stop or allow a person's sign-in (their sessions end). The last owner of an organisation cannot be disabled. |
| `account totp-off EMAIL` | Turn off two-step sign-in. |
| `account install-admin EMAIL on\|off` | The install-admin flag. The last one stays. |
| `site assign SITE --org SLUG` | Which organisation owns a site. |
| `token create NAME [--scope read\|read_private\|mcp ...] [--site S ...] [--org SLUG]` / `token list` / `token revoke ID` | API tokens (`--scope` is repeatable; default `read`). |

`skald user` is still the basic-mode password-file command.

## Security notes

- **Who the helper believes.** In sessions mode the helper reads the session
  cookie itself on every route and never trusts the `X-Skald-User` or
  `X-Skald-Role` headers. Requests without a valid session get 401, a site
  of another organisation 403. Only the sign-in pages, `/traffic-api/`
  (tokens) and `/traffic-mcp` (tokens) work without a session.
- **The nginx check.** nginx asks the helper about every `/traffic/` request
  and passes both the raw address and its own normalised path. The helper
  refuses an address with `%`, an empty segment (`//`), a `.` or `..`
  segment, a backslash or `#`, and one whose two forms name different
  sites. So no encoding trick can make nginx serve another organisation's
  file.
- **The sites list.** `/traffic/sites.json`, each site's `data/sites.json`
  and the switcher page come from the helper, filtered to the caller's
  organisations: one organisation never sees another's site names.
- **Guessing passwords.** Each try is counted before the password is
  checked, in one transaction, so tries sent in parallel cannot slip past
  the limit. At most two password checks run at once (each takes about
  32 MiB); when both stay busy the answer is 503 with `Retry-After`. nginx's
  `limit_req` on the sign-in and forgot-password POSTs slows a flood before
  it reaches the helper. Every check takes the same time: an unknown
  address, a disabled account, an empty password or a broken stored hash
  each cost one scrypt, so timing does not tell whether an account exists.
- **Local callers.** The helper listens on 127.0.0.1:8765 by default. Any
  process on the server can connect there. It cannot fake a session, but it
  can claim any `X-Real-IP` (used for the per-address sign-in limit and
  "add my address"). On a server with other local users, set
  `refresh.socket` (a Unix socket only nginx's group can open) or
  `access.trust_proxy_ip: false`.
- **Links in mails** (and the links `accounts init` / `account invite` /
  `account reset-link` print) start with one address, by one rule for the CLI
  and the helper (`accounts/links.py`): `access.base_url`, else
  `dashboard.base_url`, else the scheme and host of `dashboard.url` (the
  helper: else its first `--origin`). The CLI's `--base-url` overrides them.
  Never the request's Host.
- **What is stored.** `accounts.sqlite` (0640): scrypt password hashes;
  SHA-256 of session cookies, invite and reset links, tokens and recovery
  codes; addresses and limit keys only as keyed hashes. No raw secret.
