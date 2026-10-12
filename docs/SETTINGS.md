# Settings in the dashboard

With accounts (`access.mode: sessions`, [ACCOUNTS.md](ACCOUNTS.md)), admins change some settings
from the dashboard instead of editing `config.yml` on the server. In basic mode none of this
exists: the pages are hidden, the routes answer 404, and `config.yml` is the only source.

Code: `skald/settings_store.py` (the keys, checks and merged view),
`skald/settings_api.py` (the routes), `webapp/js/tabs/prefs.js` and `auditlog.js` (the pages).

## Where a value comes from

A setting is read in this order. The first one found wins:

1. the site's row in the `settings` table of `accounts.sqlite` (scope `site:<name>`)
2. the organisation's row (scope `org:<id>`)
3. the install's row (scope `install`)
4. `config.yml` (the site's own file in a multi-site install)
5. the default

`settings_store.effective(config, site)` gives the merged values. The daily run, `live`, the
mails, backups, beacon pruning and the returning-visitor window all read them: `cli.Context`
lays the rows over its config once (`settings_store.apply`). With no `accounts.sqlite`, or no
rows, nothing changes: the config is used exactly as read.

The rows also apply if the install goes back to basic mode, so a longer window set in the page
is not cut back by surprise. To drop a row, clear the field on the page (or delete the row).

## Locks

`config.yml` can lock keys. A locked key ignores every row; the page shows it read-only, with
the reason, and a save is refused:

```yaml
settings:
  locked: [report.retention_days, mail.smtp.host]
```

## The keys

"Admin" means an owner or admin of the site's organisation. "Install admin" is the flag on a
user (`skald accounts`); it is for settings that apply to every site of the install.

| Key | Page | Values | Who may change it | Saved for | config.yml place |
| --- | --- | --- | --- | --- | --- |
| `report.retention_days` | Data retention | 30-3650 (400) | admin | site | `report.retention_days` |
| `report.journey_days` | Data retention | 1-90 (7) | admin | site | `report.journey_days` |
| `visitors.repeat_days` | Data retention | 1-90 (30) | admin | site | `visitors.repeat_days` |
| `beacon.keep_days` | Data retention | 30-3650 (400) | admin | site | `beacon.keep_days` |
| `backup.daily` | Data retention | 1-60 (14) | install admin | install | `backup.daily` |
| `backup.weekly` | Data retention | 0-52 (8) | install admin | install | `backup.weekly` |
| `mail.daily` | Mail | on / off (on) | admin | site | `mail.daily` |
| `mail.weekly` | Mail | on / off (on) | admin | site | `mail.weekly` |
| `mail.to` | Mail | 1-20 addresses, each confirmed (below) | admin | site | `mail.to` |
| `mail.from_name` | Mail | letters, digits, spaces and . - ', 40 at most | admin | site | `mail.from_name` |
| `mail.from` | Mail | one email address: the sender of every mail | install admin | install | `mail.from` |
| `mail.smtp.host` | Mail | host name | install admin | install | `mail.host` |
| `mail.smtp.port` | Mail | 1-65535 (587) | install admin | install | `mail.port` |
| `mail.smtp.security` | Mail | starttls, ssl, none | install admin | install | `mail.security` |
| `mail.smtp.user` | Mail | text | install admin | install | `mail.user` (else `mail.user_env`) |
| `mail.smtp.password` | Mail | secret, write-only | install admin | secrets.json | env var `mail.password_env`, else `SKALD_SMTP_PASSWORD` |
| `pagespeed.api_key` | Mail | secret, write-only | install admin | secrets.json | env var `PSI_API_KEY` |
| `sites.hosts` | Sites | 1-50 host names | admin | site | `site.hosts` |
| `sites.views` | Sites | up to 20 views | admin | site | `dashboard.views` |
| `sites.timezone` | Sites | an IANA zone (UTC) | admin | site | `report.timezone` |
| `sites.log_dir` | Sites | absolute path | install admin | site | `logs.dir` |
| `sites.log_base` | Sites | a file name | install admin | site | `logs.base` |
| `beacon.goals` | Sites (Goals) | up to 10 event names of `beacon.EVENTS` or `page_view`; `[]` is no goal ([]) | admin | site | `beacon.goals` |
| `security.require_totp` | Security | on / off (off) | owner | organisation | none |
| `security.session_days` | Security | 1-90 (14) | owner | organisation | none |

A viewer sees every page read-only, with the reason. Install-only values (SMTP server and user,
log paths) are shown to install admins only.

Totals, page milestones and every stored day's figures are kept forever. They are not a setting.

`beacon.goals` (Settings > Sites > Goals): the page lists every event the site may name, the
ones it has counted (`event_counts` in the history, read-only) first and the others under
"Not counted yet". Saving checks each name against the events the beacon takes, keeps each
once, at most 10. The daily run and `live` read the merged list (`settings_store.apply`), so
events.json `goals` follows it from the next run, for every stored day; the Events page links
to it ("Edit goals"). A dashboard site inherits no goals from the install's config.

A test mail with no sender address, or no SMTP server, is refused with a plain sentence
("Set the sender address first ..."), not with config key names.

## A plan's retention cap

With saas on (docs/SAAS.md), a plan's `retention_days_max` caps the retention keys (detail
days, journeys, returning-visitor matching, in-page events; never below a key's own floor).
The value shown and used is the smaller of the setting and the cap: a site row of 400 on a
plan capped at 90 reads 90, marked `capped: true` with the saved value as `set_value`, and the
page says "Capped by your plan". The input's top is the cap, and a save above it is refused.
The daily run's pruning uses the capped value too (`settings_store.apply`, `prune_plan`), so a
smaller plan keeps fewer days from its next run.

## A shorter window

Making a retention window (or the number of backups) smaller removes stored data. So:

- the page shows what will go: `GET settings/retention-preview?key=&value=` counts the stored
  rows and days (and beacon or backup files) the new value removes;
- the save is refused (409, `needs_confirm`) until the site's name is typed (`"confirm": "<site>"`);
- nothing is removed at once. Removal happens at the next daily run (`cli.prune_kept`), and
  each site is pruned by its own window: a site with a longer window keeps its rows when
  another site's run prunes.

A changed returning-visitor window also changes who counts as returning and who counts as a
reader from an earlier day (rendering rule 9). The audit reads the same window, so the two
counts still agree.

## Secrets

The SMTP password and the PageSpeed key are write-only. They go to `secrets.json` beside the
history (`skald/conversions/secrets_store.py`, shared with the hook secrets): mode 0600,
written atomically, given the folder's owner. They never go into `accounts.sqlite`, a backup of
the history, an audit row or an API answer. The page only gets `{"set": true|false}` (and
`"env": true` when the environment sets it).

An environment variable of the same name always wins, so `/etc/skald/env` keeps working.
A `secrets.json` that others can read is refused, not used.

## Security settings

- **Session length** (`security.session_days`): nginx's session check ends a session older than
  this (401: sign in again).
- **Require two-step sign-in** (`security.require_totp`): a member without it is sent back to the
  sign-in page, which sets it up (secret, then a code; recovery codes shown once). An owner can
  turn it on only after turning it on for their own account.

## Mail recipients confirm first

The install's SMTP server sends for every organisation, so an address typed in `mail.to`
gets nothing but one confirm mail until its owner follows the link in it
(`skald/mail_confirm.py`):

- Saving `mail.to` mails a link to each address that has not confirmed, at most one mail per
  address per day (whichever organisation asks). The save's answer, and `GET settings`, list
  them as `mail_waiting`.
- The link opens `/traffic-auth/mail-confirm?t=...`, a page with one button; the button
  confirms the address for that organisation. A link works once, for 7 days.
- The daily and weekly mails and alerts go only to confirmed addresses (`settings_store.apply`
  drops the others). With none confirmed, the mail is withheld, not failed. Addresses in
  config.yml's own `mail.to` count as confirmed.
- The failure mail (`notify-failure`, failmail.py) goes to the same confirmed list: it tries
  `settings_store.apply` for the install's own site, and falls back to config.yml's mail
  settings when the package will not import or accounts.sqlite cannot be read (said in
  `run.log`). With none of the page's recipients confirmed it uses config.yml's `mail.to`,
  so a failure is never mailed to nobody.
- Only an HMAC of the address is kept (table `mail_confirms` in accounts.sqlite).
- `mail.from_name` and organisation names in invite subjects are cut to letters, digits,
  spaces and `. - '`, 40 characters, when sent too.

## Routes

All on the refresh helper, behind nginx's session check, JSON answers. POSTs need the same
origin and the session's `X-Skald-CSRF` value.

| Method, path | Who | Answer |
| --- | --- | --- |
| GET `<page>/settings` | every member | `{settings: {key: {value, source, locked, editable, reason, ...}}}`; secrets `{set, env}` |
| POST `<page>/settings/save` | per key | `{key: value, ..., confirm?}`; null clears a row. All keys are checked before any is saved. |
| GET `<page>/settings/retention-preview?key=&value=` | admin | `{shrinks, rows, days, first, last, files}` |
| POST `<page>/settings/test-mail` | admin | `{to}`: the caller's own address or a confirmed recipient (403 otherwise); 3 per 10 minutes per user (429 after) |
| GET `<page>/settings/audit?action=&limit=&format=csv` | admin | `{entries, actions}` or a CSV file; install admins see every organisation |
| GET `<page>/sites` | every member | the organisation's sites: config file or dashboard, active or removed, log received |
| POST `<page>/sites/add` | admin | `{host, timezone?, format?}` -> the site, an ingest token (shown once), the shipper command, the tag. Needs `ingest.enabled` (docs/INGEST.md) |
| POST `<page>/sites/token` | admin | `{name}`: a new ingest token for one of the organisation's sites |
| POST `<page>/sites/remove` | owner | `{name, confirm: name}`: a dashboard site stops being processed; data kept until `skald site purge` |
| POST `<page>/sites/verify` | admin | `{name}`: looks for the site's `skald-verify` token (DNS TXT or the home page's meta tag); 10 checks an hour per site |

Sites added in Settings > Add or remove sites live in accounts.sqlite (`site_config`), not in
config files; their host names, views, time zone and log paths are then changed on the Sites
page like any other site's. With saas on, a new site waits for its domain to be verified
(docs/SAAS.md, "Domain verification"): the list shows its token and a Verify button, and
nothing is collected for it until then.

A site added there, or by sign-up, has a page at once: a small "Getting ready" page in its
folder of the dashboard's output (only when none is there), then its first build on a thread
(`skald --site <site> dashboard`, `skald/first_page.py`). Its address never answers
nginx's 404 while it waits for the next run.

## Internal addresses

Addresses added on the "Our own traffic" page are kept in `ours.file`; when config.yml does not
set it, in `ours.json` beside the history, like the other state files. The runs, the classifier
and the audit's own reading all find it there. Only when the server knows neither (no history
folder resolved) does the page hide its add form, with the reason, instead of offering it.

## The audit log

Every change writes a row: action `setting.change`, the key, and `<scope>: <old> -> <new>`.
A secret writes only `set` or `cleared`. Test mails write `mail.test` with the outcome.
