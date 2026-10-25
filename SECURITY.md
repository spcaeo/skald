# Security policy

Skald reads your web server's access log, which holds visitors' addresses. We treat that as
personal data. Since 2.4.0 a site can keep each visit with its address, and leads' names and
emails, so its admins can follow a person across days. That is a switch, with a time limit, behind
sign-in, for admins and owners only, and every search is written to the audit log.

## Supported versions

| Version | Supported |
| --- | --- |
| The newest 2.x minor release (the top version in [CHANGELOG.md](CHANGELOG.md)) | ✓ Security fixes |
| Older 2.x minor releases | ✗ Please upgrade (`skald upgrade`, or the `:2` Docker tag) |
| 1.x | ✗ Please upgrade to 2.x |

Fixes go into the newest minor release. `skald version` says which one you run. Upgrading keeps your history: newer code upgrades the
history file in place, after copying it to `history.sqlite.schema-v<N>.bak`.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

- Use GitHub's private report: the **Security** tab of this repository, then **Report a
  vulnerability**.
- Or use the contact form at **https://skaldanalytics.com/contact/?topic=security** (topic
  "Security"). Do not send exploit details in that first message; we will reply with a private
  channel.

Please include the version (`skald version`), the mode (`basic` or `sessions`), what you did, what
happened, and what you expected. Never send real visitor addresses or secrets: use RFC 5737
addresses (`192.0.2.x`) and `example.com`.

What to expect:

- A first reply within **3 working days**.
- An assessment and a plan within **10 working days**.
- A fix and an advisory as soon as it is ready. We credit reporters who want credit.

Please give us a reasonable time to fix a problem before you disclose it. We will not take legal
action against good-faith research that respects users' privacy, avoids harm to data and service,
and stays within this policy.

## What Skald stores, and what it never stores

| What | Where | How long |
| --- | --- | --- |
| Raw IP addresses | Your web server's own access log | Your log rotation (14 days on the reference setup) |
| Raw IP addresses | The private request log, Site > Requests (behind sign-in) | Its 6-hour window |
| Raw IP addresses | Today's AI activity, the internal-address list | Today only; the list until removed |
| Keyed visitor hashes (HMAC-SHA256 with a server secret) | History | 30 days by default (1 to 90 in Settings) |
| Anonymous journeys (no address, no user agent, no key) | History | 7 days by default |
| Per-visit and per-page detail by labels | History | 400 days by default |
| Totals and labels | History, data files, CSV, mail | For good |
| Conversions: action, stage, time, tool, reference, source, campaign, landing page, country, device | `conversions.sqlite` | 400 days by default |
| Each visit with its IP address, user agent, times, pages in order, source, referrer, country, device (only while `privacy.keep_ips` is on) | `conversions.sqlite` (`visits`) | 395 days by default (`privacy.keep_days`) |
| Leads' names and emails (only while `conversions.identity` is `full`) | `conversions.sqlite` (`identities`) | As long as their conversions |
| Password hashes (scrypt), session hashes (SHA-256), token hashes | `accounts.sqlite` | Until removed or revoked |
| Webhook and SMTP secrets typed in the dashboard | `secrets.json`, mode 0600 | Until replaced |
| Backups of the history (hold the 30-day hashes, never the key), and of `accounts.sqlite` and `conversions.sqlite` (hold the kept visits with addresses, and leads' names and emails, while those are kept) | `/var/lib/skald/backups/` | 14 daily, 8 weekly |

**Never stored in history** (`history.sqlite`): a visitor's address, a person's user agent, a name, an email, a phone
number, a form field's value, the text a visitor copied, or the visit-grouping key (made fresh for
each run, held in memory only).

**Never written to the audit log:** a password, a token, a reset or invite link, or an address.

**Keeping IPs and emails is a switch.** A new install keeps each visit with its address
(`privacy.keep_ips`) and leads' names and emails (`conversions.identity: full`). An install upgraded
from before 2.4.0 keeps neither until someone turns them on: its privacy notice may still promise
otherwise. Change the notice first. Before a webhook is written, Skald drops addresses, browser
strings, phone numbers, form answers, free text and cancel or reschedule links; a name and email
only when the site keeps them. Outgoing webhooks never carry a name or an email. Looking a person
up is for admins and owners (and API tokens with `read_private`); each search is written to the
audit log by its kind and a hash, never the value.

**Deletion requests.** `skald forget --ip 192.0.2.7` (try `--dry-run` first) removes the address
from every private file, deletes its hashes and its kept visits, and keeps it hidden for 15 days,
longer than the log holds it. `skald forget --email A` (or `--vid ID`, `--lead REF`) deletes that
person's conversions, removed rows, name and email. The web server's own log is yours to scrub; [docs/help/privacy.md](docs/help/privacy.md)
shows how.

## How the code protects you

- **Sign-in (sessions mode).** Passwords of at least 12 characters, not common, not the email,
  stored as scrypt hashes. A random session cookie (`HttpOnly`, `Secure`, `SameSite=Lax`), 14 days
  from last use; only its SHA-256 is stored. Every change is a same-origin POST with a CSRF value.
  "Sign out everywhere" ends all other sessions.
- **Guessing is slowed, never locked out.** After 5 failed sign-ins for one email or address in 15
  minutes, each try waits 30 seconds. Nobody can lock an owner out. The helper runs at most two
  password checks at a time, so a flood cannot exhaust memory.
- **Two-step sign-in** with any authenticator app (RFC 6238), 10 one-time recovery codes. An owner
  can require it for the organisation.
- **Membership is checked on every request.** Removing a member or disabling a person ends access
  at once. A token made in the page stops when its maker is disabled or demoted.
- **Scoped tokens** (`read`, `read_private`, `mcp`, `ingest`), shown once, stored as hashes. Without
  `read_private`, no API or MCP answer carries an address.
- **Strict path checks.** The helper sees the raw address and nginx's normalised path; a path that
  tries to step into another organisation's site is refused.
- **Signed webhooks.** Each tool's own signature is checked on the raw body; repeats change
  nothing. Outgoing webhooks are signed, HTTPS only, and never sent to a private address.
- **Domain proof.** A site added in the dashboard or by sign-up proves its domain (DNS TXT or a
  meta tag) before Skald collects for it. A mail recipient typed in the page confirms by a link
  first, so nobody can use your server's mail to reach strangers.
- **The dashboard** loads no third-party script, font or image, and is served with a strict
  Content-Security-Policy (`default-src 'none'; script-src 'self'; frame-ancestors 'none'`),
  `noindex` and `no-referrer`.
- **The script tag** never sends a field's value, honours Do Not Track and Global Privacy Control,
  and sets no cookie by default.
- **Exports are safe in spreadsheets.** A cell a spreadsheet would run as a formula is prefixed with
  an apostrophe.

### Security reviews

Two security reviews were carried out on the 2.0 platform code before release, covering sign-in and
sessions, nginx's sign-in check, rate limits, sites, mail, webhooks and log intake. Their fixes are
in 2.0.0. Examples: an encoded `..` path that could reach another organisation's files is now
refused; sign-in floods are counted before the password check; new sites must prove their domain.

## Hardening checklist

For a production install. [docs/INSTALL.md](docs/INSTALL.md) has the exact files.

- [ ] **Use sessions mode** (`access.mode: sessions`) so each person has their own account, role
      and audit trail. Basic mode (one nginx password) is fine for a single owner.
- [ ] **Serve the dashboard only over TLS.** The session cookie is `Secure`, so sign-in works over
      plain HTTP only at `localhost`. With Docker, use your host's nginx or Caddy, or
      `docker compose --profile https up -d` with `SKALD_DOMAIN` set (Caddy, automatic HTTPS).
- [ ] **Do not publish port 8080 to the internet.** Bind it to `127.0.0.1` and let the HTTPS proxy
      reach it.
- [ ] **Put nginx in front** with the sign-in check (`auth_request`) on every dashboard path, and
      always run `nginx -t` before a reload.
- [ ] **Turn on the rate limits** (`limit_req_zone`) for sign-in, webhooks, the beacon and log
      intake, as in the install guide.
- [ ] **Bind the helpers to a Unix socket** (`refresh.socket`, mode 0660, group `www-data`) instead
      of `127.0.0.1:8765`, or set `access.trust_proxy_ip: false`, if other local users could reach
      the port.
- [ ] **Lock down secrets.** `/etc/skald/env` owned by the `skald` user, mode 0600;
      `/etc/skald/config.yml` root:skald 0640; `/var/lib/skald` 0750; `secrets.json` 0600. Never
      commit any of them.
- [ ] **Generate the visitor key once** (`python3 -c "import secrets; print(secrets.token_hex(32))"`)
      and keep it only in the env file. It is never copied into a backup.
- [ ] **Require two-step sign-in** for owners and admins.
- [ ] **Keep MCP and the API read-only tokens narrow:** one site, no `read_private` unless you need
      addresses.
- [ ] **Back up** `history.sqlite`, `accounts.sqlite` and `conversions.sqlite`. `skald backup` makes
      restore-tested nightly copies of all three; encrypt any copy you move off the server (`age` or
      `gpg`).
- [ ] **Keep logs short.** Rotate the access log at 14 days or less; Skald needs only the days it has
      not yet collected.
- [ ] **Switch on only what you use.** MCP, visitor IDs, log intake and the hosted layer are each
      off until the config turns them on; a webhook works only once it has a secret. Accounts are
      off in a plain install and on in the Docker image. Keeping IPs and leads' emails is **on** for
      a new install: if you do not need it, set `privacy.keep_ips: false` and
      `conversions.identity: anonymous` (or Settings > Data retention > People).
- [ ] **Run the Docker image** with the log mounted read-only (`:ro`), as the quick start shows.

## Scope

In scope: the code in this repository, the Docker image `ghcr.io/spcaeo/skald`, and the install
script. Out of scope: your web server's own configuration, third-party services that send webhooks,
and social-engineering or physical attacks.
