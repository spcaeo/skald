# Settings in the dashboard

With accounts (`access.mode: sessions`, [ACCOUNTS.md](ACCOUNTS.md)), admins change some settings
from the dashboard instead of editing `config.yml` on the server. In basic mode none of this
exists: the pages are hidden, the routes answer 404, and `config.yml` is the only source.

Code: `skald/settings_store.py` (the keys, checks and merged view),
`skald/settings_api.py` (the routes), `skald/webapp/js/tabs/prefs.js` and `auditlog.js`
(the pages).

## Where a value comes from

A setting is read in this order. The first one found wins:

1. the site's row in the `settings` table of `accounts.sqlite` (scope `site:<name>`)
2. the organisation's row (scope `org:<id>`)
3. the install's row (scope `install`)
4. `config.yml` (the site's own file in a multi-site install)
5. the default (source `upgrade` for the two privacy keys below on an install upgraded from
   before 2.4.0)

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
| `privacy.keep_ips` | Data retention > People | full / short / off (full); true and false read as full and off | admin | site | `privacy.keep_ips` |
| `privacy.keep_days` | Data retention > People | 1-3650 (395) | admin | site | `privacy.keep_days` |
| `conversions.identity` | Data retention > People | full / anonymous (full) | admin | site | `conversions.identity` |
| `conversions.retention_days` | Data retention > Leads | 1-3650, or 0 / `forever`: kept for good (400) | admin | site | `conversions.retention_days` |
| `journeys.vid_days` | Data retention > Leads | 1-400 (30) | admin | site | `journeys.vid_days` |
| `conversions.click_ids` | Data retention > Leads | on / off (off): keep a lead's ad click ID (gclid, gbraid, wbraid, msclkid, fbclid, li_fat_id, ttclid, twclid) with it (2.45, `conversions/fill.py`); off deletes the ones kept at the next run | admin | site | `conversions.click_ids` |
| `backup.daily` | Data retention | 1-60 (14) | install admin | install | `backup.daily` |
| `backup.weekly` | Data retention | 0-52 (8) | install admin | install | `backup.weekly` |
| `mail.daily` | Mail | on / off (on) | admin | site | `mail.daily` |
| `mail.weekly` | Mail | on / off (on) | admin | site | `mail.weekly` |
| `mail.marketing` | Mail | on / off (off): the Monday marketing mail (mail_marketing.py): last week's visitors, pages read, leads and sources from the log, then each connected tool's headline figures under "Counted from: <tool>", never added to Skald's; refused, like the weekly mail, when the week is not whole | admin | site | `mail.marketing` |
| `mail.to` | Mail | 1-20 addresses, each confirmed (below) | admin | site | `mail.to` |
| `mail.from_name` | Mail | letters, digits, spaces and . - ', 40 at most | admin | site | `mail.from_name` |
| `mail.from` | Mail | one email address: the sender of every mail | install admin | install | `mail.from` |
| `mail.smtp.host` | Mail | host name | install admin | install | `mail.host` |
| `mail.smtp.port` | Mail | 1-65535 (587) | install admin | install | `mail.port` |
| `mail.smtp.security` | Mail | starttls, ssl, none | install admin | install | `mail.security` |
| `mail.smtp.user` | Mail | text | install admin | install | `mail.user` (else `mail.user_env`) |
| `mail.smtp.password` | Mail | secret, write-only | install admin | secrets.json | env var `mail.password_env`, else `SKALD_SMTP_PASSWORD` |
| `pagespeed.api_key` | Mail | secret, write-only | install admin | secrets.json | env var `PSI_API_KEY` |
| `search.google_property` | Integrations > Search | a Search Console property that covers the site's hosts (`sc-domain:example.com` or a URL prefix) | admin | site | `search_console.property` |
| `search.bing_site` | Integrations > Search | the site's URL in Bing Webmaster Tools, covering its hosts | admin | site | `bing.site_url` |
| `search.bing_api_key` | Integrations > Search | secret, write-only | install admin | secrets.json | env var `BING_WEBMASTER_API_KEY` |
| `ai_answers.openai_key`, `ai_answers.perplexity_key`, `ai_answers.gemini_key`, `ai_answers.anthropic_key` | Integrations | secret, write-only | install admin | secrets.json | env vars `SKALD_OPENAI_API_KEY`, `SKALD_PERPLEXITY_API_KEY`, `SKALD_GEMINI_API_KEY`, `SKALD_ANTHROPIC_API_KEY` (AI answers, docs/AI-ANSWERS.md) |
| `brand.agency_name` | Reports (Agency branding) | text, 60 at most | admin | organisation | (none) |
| `brand.color` | Reports (Agency branding) | a colour `#rrggbb` (none: Skald's ink) | admin | organisation | (none) |
| `sites.hosts` | Sites | 1-50 host names | admin | site | `site.hosts` |
| `sites.views` | Sites | up to 20 views (page groups; "Page groups: filling past days" below) | admin | site | `dashboard.views` |
| `sites.timezone` | Sites | an IANA zone (UTC) | admin | site | `report.timezone` |
| `sites.log_dir` | Sites | absolute path | install admin | site | `logs.dir` |
| `sites.log_base` | Sites | a file name | install admin | site | `logs.base` |
| `site.asset_prefixes` | Sites (Page assets) | 1-10 path prefixes, each starting with `/`, not `/` alone (`/_next/static/`) | admin | site | `site.asset_prefixes` |
| `site.require_rendering` | Sites (Page assets) | true / false (true) | admin | site | `site.require_rendering` |
| `site.not_pages_off` | Sites (Not pages) | entries of the not-a-page list counted as pages again: `markdown`, `wp_rest`, `wp_files`, `feeds`, `oembed`, `trackback`, `author_number`, `reply_to_comment`, `sitemap_page` (none) | admin | site | `site.not_pages_off` |
| `site.not_pages_extra` | Sites (Not pages) | up to 20 of the site's own: `/path`, `/prefix*` or `?key`, not `/` alone (none) | admin | site | `site.not_pages_extra` |
| `site.script_posts` | What counts (Not forms) | up to 20 POST paths the site's own pages send by themselves, not forms: `/path` or `/prefix*`, not `/` alone (none) | admin | site | `site.script_posts` |
| `site.logo.source` | Sites (Logo) | auto, upload, letter (auto) | admin | site | `site.logo_source` |
| `site.logo.color` | Sites (Logo) | `#1d4ed8`, `#0f766e`, `#9a6400`, `#17212b` (one picked from the name) | admin | site | `site.logo_color` |
| `beacon.visitor_ids` | Sites (Script tag) | true / false (false) | admin | site | `beacon.visitor_ids` |
| `beacon.share_subdomains` | Sites (Script tag) | true / false (false) | admin | site | `beacon.share_subdomains` |
| `beacon.goals` | Sites (Goals) | up to 10 event names of `beacon.EVENTS` or `page_view`; `[]` is no goal ([]) | admin | site | `beacon.goals` |
| `hooks.calendly.event_types` | Integrations (Calendly) | up to 50 event-type URIs, uuids or booking-page slugs; `[]` keeps every event ([]) | admin | site | `hooks.calendly_event_types` (or nested `hooks.calendly.event_types`) |
| `hooks.calcom.event_types` | Integrations (Cal.com) | up to 50 event-type ids or slugs; `[]` keeps every event ([]) | admin | site | `hooks.calcom_event_types` (or nested `hooks.calcom.event_types`) |
| `alerts.enabled` | Site > Alerts | on / off (off) | admin | site | `alerts.enabled` |
| `alerts.mail` | Site > Alerts | on / off (on) | admin | site | `alerts.mail` |
| `alerts.<rule>` | Site > Alerts | on / off (on), one per rule: `site_down`, `logging_stopped`, `server_errors`, `not_found_surge`, `crawler_burst`, `new_crawler`, `traffic_drop`, `ai_started_reading`, `ai_stopped_reading`, `ai_sending_people`, `first_citation`, `first_cited_page`, `cited_visits`, `crawler_silent`, `security_exposure`, `stack_advisory`, `tool_stopped`, `leads_drop`, `bookings_drop`; off by default: `scan_wave`, `sale`, `sale_refund`, `ga4_log_gap`. Thresholds in config.yml only: `alerts.leads_drop_percent` (50), `alerts.leads_drop_minimum` (5), `alerts.bookings_drop_percent` (50), `alerts.bookings_drop_minimum` (5), `alerts.ga4_gap_factor` (2) | admin | site | `alerts.<rule>` (the AI three also nested `alerts.ai.<rule without ai_>`) |
| `alerts.sale_minimum` | Site > Alerts (under Sale) | the least amount per currency that makes a sale alert, as text: `USD 100, EUR 90.50` (stored by currency, each with its decimals: `EUR 90.50, USD 100.00`); at most 10 currencies; a currency not listed alerts at any amount; empty: any amount (none) | admin | site | `alerts.sale_minimum` (the same text, or a map `{USD: 100}`) |
| `security.require_totp` | Security | on / off (off) | owner | organisation | none |
| `security.session_days` | Security | 1-90 (14) | owner | organisation | none |

A viewer sees every page read-only, with the reason. Install-only values (SMTP server and user,
log paths) are shown to install admins only.

Totals, page milestones and every stored day's figures are kept forever. They are not a setting.

`hooks.calendly.event_types` and `hooks.calcom.event_types` (Settings > Integrations, the
tool's box; saved by `POST integrations/hooks/types`): the hook receiver reads them for each
delivery (`conversions/event_types.py`), so a change counts from the next delivery. Another
event type is answered 200 and not kept; docs/INTEGRATIONS.md, "Calendly".

`beacon.goals` (Settings > Sites > Goals): the page lists every event the site may name, the
ones it has counted (`event_counts` in the history, read-only) first and the others under
"Not counted yet". Saving checks each name against the events the beacon takes, keeps each
once, at most 10. The daily run and `live` read the merged list (`settings_store.apply`), so
events.json `goals` follows it from the next run, for every stored day; Leads & sales > Events links
to it ("Edit goals"). A dashboard site inherits no goals from the install's config.

`beacon.visitor_ids` (2.9.0): whether the script tag keeps an anonymous visitor ID for this site
(docs/BEACON.md, "Visitor IDs"). Saved for one site only; another site keeps its own value. The
beacon helper reads it again within a minute, and serves `skald.js` with the value of the site
whose page loads it. Settings > Sites > Script tag has the switch; Settings > Integrations says
whether it is on from the same merged value.
Turn it on only when the site's privacy notice says so, and let a consent banner gate the tag.

`beacon.share_subdomains` (2.27): share the visitor ID across the site's subdomains (a
first-party cookie `skald_vid`), as `data-share-subdomains="true"` on the tag does, with the
tag unchanged: an admin can switch sharing on in Skald instead of the tag, for a site whose
developer cannot edit it. The beacon helper reads it within a minute and says it in its answer
to a page view (`X-Skald-Sh`); each browser keeps that answer a day (docs/BEACON.md, "Sharing
the ID across subdomains"). It needs `beacon.visitor_ids` on. Settings > Integrations and the
privacy notice treat it as the attribute.

`site.asset_prefixes` and `site.require_rendering` (Settings > Sites > Page assets): a visit
counts as people only when its browser also fetched one of the page's own assets
(CLASSIFICATION.md, rendering.py). A dashboard site takes nothing of the first site's `site:`
section, so without a row it looks for `/_next/static/` (Next.js). A WordPress site saves
`/wp-content/` and `/wp-includes/`; many static sites `/assets/` or `/static/`. Off is only for
a site whose assets come from a CDN host this log never sees. `settings_store.apply` writes the
row into `config["site"]`, where the first pass (`rendering.py`), its recount
(`audit_rendered.py`) and the doctor's "Page assets" line read it, so both roads count with the
same paths. A change counts from the next run; `backfill --days N --force` recounts stored days.

`site.not_pages_off` and `site.not_pages_extra` (Settings > Sites > Not pages, 2.35): the
not-a-page list (`not_pages.py`, CLASSIFICATION.md "What decides a page view") applies to
every site from code, so a dashboard site has it without a row. A request on it is no page
view; it stays a request in its group. The first key names the entries the site counts as
pages again (a site that serves a real `/feed/` page unticks `feeds`); the second adds the
site's own addresses (`/status`, `/preview/*`, `?preview`), compared in any case.
`settings_store.apply` writes both into `config["site"]`, where `parse.read` (through
`not_pages.from_config`) and the audit (`audit_not_pages.Marker`) read them. A value that does
not check out counts as unset on both roads. From the next run; `backfill --days N --force`
recounts stored days.

`site.script_posts` (Settings > Data > What counts > Not forms): POST paths that are no form
(`form_names.py`). A visit "sent a form" for any POST except Skald's own endpoints, a POST
answered 204 with no body, a path on `form_names.SCRIPT_POSTS` (page-script beacons such as
`/api/events`), a POST the site refused (`form_names.REFUSED`: 301, 307, 308, 404, 405, 410,
444, 501; since 2.45.1) and the paths here. `settings_store.apply` writes it into `config["site"]`,
where `parse.read` (through `not_pages.from_config`, `Rules.posts`) and the audit
(`audit_visits.NotForm`) read it; a value that does not check out counts as unset on both roads.
The answer of `GET settings` carries `defaults` (the shared list) and `suggested`
(`form_names.suggest`: a path sent, answered 2xx, by half the visits that sent a POST and a
fifth of all visits, on 3 of the last 14 stored days); nothing is added without a person's
save. From the next run; `backfill --days N --force` recounts stored days.

A test mail with no sender address, or no SMTP server, is refused with a plain sentence
("Set the sender address first ..."), not with config key names.

## A plan's retention cap

With saas on (docs/SAAS.md), a plan's `retention_days_max` caps the retention keys (detail
days, journeys, returning-visitor matching, in-page events; never below a key's own floor).
The value shown and used is the smaller of the setting and the cap: a site row of 400 on a
plan capped at 90 reads 90, marked `capped: true` with the saved value as `set_value`, and the
page says "Capped by your plan". The input's top is the cap, and a save above it is refused.
The daily run's pruning uses the capped value too (`settings_store.apply`, `prune_plan`), so a
smaller plan keeps fewer days from its next run. A plan with `keep_everything: true` has no
pruning at all ([Keep everything](#keep-everything)).

## Keep everything

The owner's rule (2026-10-26) for internal and enterprise installs: nothing is deleted. A site
keeps everything (`skald/keep_everything.py`) when

- **the install says so**: `retention.keep_everything: true` in `config.yml` (Docker:
  `SKALD_KEEP_EVERYTHING=1`). Every site of the install keeps everything. This is how a
  server that sells no plans (saas off) turns it on.
- **hosted (saas on)**: the site's organisation has no plan (the install's own: internal), or
  its plan says `keep_everything: true` in `saas.plans` (Enterprise):

  ```yaml
  saas:
    plans:
      pro: {sites: 5, retention_days_max: 400, label: "Pro"}
      enterprise: {keep_everything: true, label: "Enterprise"}
  ```

  A site no organisation holds is the install's own. A customer plan's sites are pruned as
  before.

**The organisation rule** (accounts schema 6, 2.43.0): each organisation has a privacy class,
`internal` (the default) or `client`, set by an install admin (Settings › Organisation ›
Organisations › Settings, `skald org privacy SLUG internal|client`, or
`accounts.orgs.set_privacy_class(db, org_id, cls, actor)`; audited `org.privacy`).

- `internal`: the rules above, unchanged. Every organisation starts here, so nothing changes on
  an install until someone makes one a client.
- `client`: the organisation's sites follow their own retention settings even when the install
  keeps everything. Only a hosted plan with `keep_everything: true` still keeps them.

Every decision goes through the one keeper (`Keeper(config, live_dir)` or `of(ctx)`), which asks
the rule first; `Keeper.install` is the install's switch, and `Keeper.all` ("every site keeps
everything", the shortcut some paths take to open nothing) is true only when no organisation is a
client. Any doubt (no accounts file, one that cannot be read) counts as internal: everything is
kept. `tests/test_privacy_class.py` runs every path of the table below against a client's site
and checks it clears what an install without the rule clears, and that no module decides from
`install_on` alone.

On such a site no automatic deletion or clearing of any kind runs, whatever a retention window,
the People days or a plan's cap says. Each path below asks the keeper first:

| Path | Code | On a keep-everything site |
|---|---|---|
| Anonymous journeys past `report.journey_days` | `prune.prune_kept`, `store_visits.prune_sites` | kept (the site and its views) |
| Returning-visitor hashes past `visitors.repeat_days` | `visitors.prune` | kept |
| Per-page and per-visit detail past `report.retention_days`, and the AI fetches past 180 days | `History.prune_extras` | kept |
| Visits with addresses past `privacy.keep_days`; every visit when `keep_ips` turns off; the shortening when it turns `short` | `people/visits.prune` | kept, unchanged |
| Security's scanner rows (the same three) | `security_kept.prune` | kept, unchanged |
| Leads, removed rows and lead journeys past `conversions.retention_days`; journeys of an ID with no lead past `journeys.vid_days`; identities nothing points to; deliveries (90 days), replay hashes and payment links | `conversions/store.prune` | kept |
| Recorded journeys (2.43) past `journeys.vid_days`; their addresses and emails past the People days | `recorded/store.prune` | kept, unchanged (docs/JOURNEYS.md) |
| The hook spool's lines | `conversions/spool.prune` | kept (with every site kept, no file is opened) |
| Names and emails past the People days, in leads, removed rows, the spool and the upgrade copies | `conversions/people_days.run` | kept |
| Names and emails past the People days in your tools' stored answers (Calendly invitees, Resend contacts and recipients), even a tool that stopped answering; the figures stay | `yourtools/people_days.run` (from the daily prune) | kept |
| The outgoing webhooks' outbox past 30 days | `conversions/outgoing.prune` | kept |
| In-page event counts past `beacon.keep_days` | `events.collect` | kept |
| The beacon spool files | `beacon.prune` (from `events.daily`) | kept while any site of the install keeps everything (the spool holds every site's lines) |
| AI answers runs past their profile's days | `answers/run.run_site` | kept |
| Closed alerts after 30 days | `alerts.apply` | kept |
| Daily and weekly copies of the conversions file | `backup.make` (from `skald backup`) | kept while any site keeps everything (one file holds every site's leads) |
| Shipped raw logs past `ingest.keep` days (14) | `ingest_log.Writer.rotate` | moved to `<site>/archive/access.log.<UTC day>.gz` instead of deleted, outside run-daily's window (owner, 2026-10-26: about 11 MB a day for every live site) |

Still as before, because they are not stored data about a person or a figure: the history's own
daily and weekly backups (`backup.daily`, `backup.weekly`: one copy a day of a large file), the live files rewritten every
run (the Requests list's 6 hours, today's AI activity), caches, signed-in sessions, sign-in
attempts, invites and sign-ups, and the temporary files of an upgrade.

A person's own deletion request still works: `skald forget` and `skald conversions forget`,
run by an admin by hand, delete what is kept about that person. So does a visitor's withdrawal
of consent sent by the site for recorded journeys (`POST .../journey/withdraw`): it deletes that
visitor's recorded events. Removing a site with `sites remove` is also by hand.

What a site owner sees: Settings > Data retention says "Kept: nothing is deleted (internal or
enterprise)." above the cards and on the People card, and a shorter window's preview says it
removes nothing; the privacy notice wording says each thing is kept "until you ask us to delete
it"; `skald doctor` shows one line, "Keep everything: on", with the rule that decides it
("Rule: Kiwi is an internal organisation..."), or "off: Kiwi is a client organisation..." for a
client's site on an install that keeps everything. `GET settings` returns
`keep_everything: {on, why, words, rule}` (`why`: `install`, `no plan` or `plan <name>`; `rule`:
`{class, org, words}`), the Privacy page says the rule's words, and the retention preview answers
`kept: true, shrinks: false` with the words.

## A plan's usage alerts (config only)

`saas.usage_alerts` (on by default when saas is on; `false` turns it off) mails an
organisation's owners and admins once when this month's requests reach 80, 90 and 100 % of its
plan's `requests_month`, and shows them a banner on every page from 80 %. Off, the mails and
the banner stop; Settings > Billing still shows the bar. It is a config key, not a dashboard
setting: the install's operator decides it for every organisation. Self-hosted installs (saas
off) have neither. What is sent, when and to whom: docs/SAAS.md, "Usage alerts".

## People: keeping IPs and emails (2.4.0)

`privacy.keep_ips` keeps each visit with its IP address and user agent (`people/visits.py`,
tables `visits` and `visit_days` in `conversions.sqlite`), for `privacy.keep_days` days.
`conversions.identity: full` keeps a lead's name and email with its conversions. Turning
`keep_ips` off deletes the site's kept visits at the next nightly run (`people.visits.prune_kept`).

**The People days cover names and emails too (after 2.38.0).** When a site set
`privacy.keep_days` (its own or its organisation's row, the install's row, config.yml or a
plan's cap; `settings_store.promised`, the plan's `set`) and it is shorter than
`conversions.retention_days` (any number is shorter than 0, kept for good), a lead's name and
email are kept that many days. Then the nightly prune clears them from every copy: the
identity (blanked, or its older rows moved to a blank one when the person also has a younger
lead), the rows a sync removed, the hook spool's lines and the schema-upgrade copies
(`conversions/people_days.py`, DATA-CONTRACT-PEOPLE.md). The lead stays and keeps counting;
every figure and the second count are unchanged. The first live run after the upgrade clears
the rows already past it. A site that set no People days (the code's 395 is not a promise) or
longer ones keeps the old rule: names and emails go with the lead. The privacy notice's
wording says it (`name_days` in `uses`): "We keep them for 180 days. After that we keep the form
or booking without your name and email, for 400 days" (or "until you ask us to delete it").
Making `privacy.keep_days` smaller is confirmed like any shorter window; the preview counts
the kept visits only.

**Three values (2.15.0).** `full` keeps the whole address, `short` keeps it shortened, `off`
keeps none. `true` and `false` (config.yml, settings rows saved before 2.15.0, the CLI) still
read as `full` and `off`, and the page shows them so (`policy.mode_of`); a row is saved as
the word. The shortening rule (`people/policy.shorten`): an IPv4 address's last octet is
zeroed (203.0.113.57 as 203.0.113.0), an IPv6 address keeps its first 48 bits
(2001:db8:85a3:8d3:: as 2001:db8:85a3::), an IPv4-mapped IPv6 address is IPv4, and a value
that is not an address is kept as it is. The country and city are looked up from the full
address first; bot sorting, internal traffic and every total read the raw log, unchanged.
Switching full to short shortens the rows already kept at the next nightly run, as off
deletes them then (a save never removes data by itself). Short to full keeps the old rows
shortened; only new rows are full. The page says both under the choice. The person search
finds a full address's visits by its shortened form and says one shortened address can be
several people; the visitor drawer calls the link by a shortened address weaker. The
second count shortens by its own code (DATA-CONTRACT-PEOPLE.md, "Second count").

**Wording for your privacy notice (2.15.0).** Under the People card, a card shows a short
text a site owner can paste into their privacy page, with a Copy button and the line "A
starting point, not legal advice. Your notice must match your own situation."
`people/notice.py` makes it on the server, from the merged settings, by the same functions
that decide what is kept (`policy.ip_mode`, `policy.keep_days`, `policy.identity_full`,
`events.enabled`, `beacon.visitor_ids`): the log is read and sets no cookie; IP addresses
kept in full, shortened (the rule in plain words) or not, and for how long; names and emails
kept or not; with the script tag on, visitor IDs (local storage, and the shared cookie: a
plain line with `beacon.share_subdomains` on, else a marked line), Do Not Track and Global Privacy Control, and the wait for consent (a marked
line: the tag attribute is not seen by the server); how to ask for deletion. What the
server cannot know is a placeholder in [square brackets]: the site's contact, how long its
web server keeps logs. `notice` in the answer: `{intro, items, text, placeholders, note,
uses}`, `uses` naming the values it was made from. Since 2.29 it also says how long a lead's
name and email, and the pages read with its visitor ID, are kept (`lead_days`, `vid_days` in
`uses`): "until you ask us to delete them" when `conversions.retention_days` is 0.

**Leads: how long they are kept (2.29).** The card **Leads** holds two keys, per site:

- `conversions.retention_days` (400): the conversions, the rows a sync removed, the journeys
  of IDs that converted, the identities they point to and the hook spool's lines (their names
  and emails only for the People days when the site set those shorter, above). `0` (or
  the word `forever`) keeps them for good: `conversions/store.prune` never deletes them and
  `spool.prune` keeps the site's lines. The page shows it as two choices, "Kept for good" or
  N days (`forever` in the answer). The delivery log keeps its own 90 days, the replay hashes
  their 30. `conversions forget` (and `skald forget`) still deletes one person whatever is
  set. A plan cap (saas) treats 0 as longer than any cap.
- `journeys.vid_days` (30, 1-400): the page views of an ID with no conversion. Once the ID
  converts, its pages are kept with the conversion, as long as it.

Each site is pruned by its own values (`prune_plan`); a spool day file holding lines of sites
with different windows is written again with only the lines still kept. A shorter window is
confirmed like the others; any number of days is shorter than 0. The second count of beacon
conversions keeps its own day counts (`conversions-audit.json`) for as long as the
conversions, so a day older than `beacon.keep_days` is still checked against the count made
while the beacon spool held it.

**The upgrade rule.** When neither the page nor `config.yml` sets them, a new install reads
`keep_ips: full` and `identity: full`. An install whose history predates 2.4.0 reads `off` and
`anonymous` (`people/policy.py`): history schema 13 writes the meta row `privacy_legacy` when it
upgrades an older file, and a file still at schema 12 or older counts the same. The page then
shows source `upgrade` ("kept off by the upgrade to 2.4.0", `settings_store.LEGACY_DEFAULTS`).
Docker: `SKALD_KEEP_IPS=1|0|short` and `SKALD_IDENTITY=full|anonymous` write the config keys. Turn them on
only when the site's privacy notice says so.

## A shorter window

Making a retention window (or the number of backups) smaller removes stored data. So:

- the page shows what will go: `GET settings/retention-preview?key=&value=` counts the stored
  rows and days (and beacon or backup files; for `privacy.keep_days` the kept visits; for
  `conversions.retention_days` the conversions, removed rows and journeys; for
  `journeys.vid_days` the page views of IDs with no conversion) the new value removes. A
  `forever` key's 0 keeps the most: any number of days after it is smaller;
- the save is refused (409, `needs_confirm`) until the site's name is typed (`"confirm": "<site>"`);
- nothing is removed at once. Removal happens at the next daily run (`cli.prune_kept`), and
  each site is pruned by its own window: a site with a longer window keeps its rows when
  another site's run prunes.

A changed returning-visitor window also changes who counts as returning and who counts as a
reader from an earlier day (rendering rule 9). The audit reads the same window, so the two
counts still agree.

## Page groups: filling past days

`sites.views` (Settings > Sites > Views) holds the site's page groups, one per line on the
page: `name | path prefix | prefixes to leave out` (several separated by spaces). For example
`Blog | /blog/`, or `Canada | /ca/ | /ca/fr/`. The prefix is matched against the path only,
case-sensitive; `/ca/` also takes the bare `/ca`; no prefix means every path. A group's days
are stored beside the site's under `<site>::<slug>` (the slug is the name in lower case,
spaces as `-`, which is also its folder and its address in the "All pages" menu).

A group is counted from the next run. Its earlier days are **not recorded for this group**
(the page says so, never 0) until they are counted again from the raw log, which holds only
the days the server keeps (14 on a Debian or Ubuntu logrotate default). So:

- A save that adds a group, or changes a group's rule, answers
  `views: {changed: [{slug, name}], removed: [...], can_fill, reach, fill}`. A renamed group
  is a new one. `reach` is `views_fill.reach`: `{days, first, last, kept_days, oldest_line}`,
  the whole days from the oldest line of the oldest rotation to yesterday (a first day is
  whole when its oldest line is within `report.coverage_gap_minutes`, 60, of midnight).
- The page's tick box under Views, **Fill past days for the new groups**, is ticked by
  default: the page then posts `settings/views-fill-start` with the changed groups at once.
  Unticked, it offers the same with a button.
- The fill runs in the background on the server as `skald --site S views refresh --days N
  --view SLUG ...` (`cli_views.py`, `views_fill.py`), N = `reach.days`. For each day, oldest
  first, it counts the day once with the same pass and rules as `collect`, stores each chosen
  group's day with its own check, then recounts each group by the audit's own road
  (`audit_views.py`: requests, requests by group, people's visits and readers, responses by
  status class) and withholds a day that does not match. The site's own days are not touched.
  Then it draws the dashboard. A day with no line in the log stays not recorded.
- One fill at a time per install (`views-fill.lock`, an flock beside the history). Progress is
  in `views-fill.json` there: `state` (queued, running, done, failed), `days`, `done`,
  `filled`, `withheld`, `empty`, `current`, `first`, `last`, `problems`. A queued or running
  fill whose process is gone reads as failed. The page reads it every 2 seconds: "Filling 9
  days… 4 of 9", then "Done: 9 days filled, all audited", and below it "Days before 13 Oct
  can't be filled: the raw log is kept 10 days."
- A removed group needs no recount: it leaves the menu; its stored days stay in the history.
- Owners and admins only (or an install admin); same-origin and the CSRF header; audit
  `views.fill` with the days and groups; a `backfill` marker when it ends.

From the shell (Docker: `docker exec skald skald --site example.com views refresh`):

```sh
skald --site example.com views list                    # each group, its rule, its first day
skald --site example.com views refresh                 # every whole day the raw log holds
skald --site example.com views refresh --days 5 --view blog
```

Exit 0 every day filled and audited, 1 a day withheld or nothing to fill, 2 no such group,
3 another fill is running. `backfill --days N --force` still recounts the site and every
group, as before.

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

## Security thresholds (config only, 2.21)

The config's `security:` section sets the rules of the Security section
(skald/security_names.py, docs/DATA-CONTRACT-SECURITY.md); each is kept
within a sane range:

```yaml
security:
  shell_paths: 3        # "Is anything exposed?": paths that must share a size to call it the host's fallback page
  tolerance: 16         # bytes either side of that size
  login_posts: 20       # login and form hammering: POSTs to a login or form path from one address...
  login_seconds: 300    # ...within this many seconds
  burst_requests: 300   # a burst: requests from one address...
  burst_seconds: 60     # ...within this many seconds
  large_post_bytes: 1000000   # log signs: a POST this large or larger (needs request_length= in the log)
```

Your stack (2.21) is read once a day by the morning run: `security.stack_check: false`
turns it off. `security.advisories_fetch: true` (off by default) lets the morning run fetch
the newest advisories list from Skald's public repository; without it the list changes only
with a Skald release, and nothing is fetched.

### Public check (optional, 2.22)

A public "Is my site exposed?" check for a marketing page: anyone types an address and gets
what that site's home page shows (server, PHP, WordPress, Next.js and Node.js, with versions
or "not shown by the server"), the shipped advisories that match, and whether
`/wp-login.php` is open. Off by default; nothing about it runs until it is switched on.

```yaml
security:
  public_check: true                    # Docker: SKALD_PUBLIC_CHECK=true
  public_check_origins: ["https://www.example.com"]   # SKALD_PUBLIC_CHECK_ORIGINS
  public_check_info_url: "https://www.example.com/check/"   # SKALD_PUBLIC_CHECK_INFO_URL
  public_check_per_hour: 10             # checks an hour from one address
  public_check_global_per_hour: 300     # checks that fetch, an hour, from everyone
```

- **Endpoint:** `POST /traffic-hooks/_public/stack-check` on the beacon helper, body
  `{"url": "https://example.com"}`; answers JSON (`products`, `cards`, `hosts`, `reached`,
  `error`, `checked_at`, `cached`). 400 with plain words when the address is not checked, 403
  for a page of another origin, 429 at a limit (with `Retry-After`), 503 when 4 checks are
  already running. Each error says its `kind`: `address` (not a website address at all),
  `refused` (an IP, an inside name: its words say which), `rate` (with `limit`, `retry_in`
  seconds and `retry_at`, the UTC time one more check is allowed), `busy` (everyone's limit or
  too many at once), `failed`. A site that could not be read is a 200 with `reached: false`,
  `reason` (`unreachable`, `blocked` by its firewall, or `error`) and `error` in plain words
  ("no answer in 5 seconds", "the name doesn't exist", "its certificate is invalid"). With `"cached_only": true` it answers only a check made in the last hour
  (404 otherwise) and never fetches: a page's "send this report" reads its findings back this
  way, so a report carries only what this check found. Every 200 answer to a check also says
  this sender's `limit`, how many checks are `left` this hour (after this one), and `next_at`
  (the UTC time the oldest counted check stops counting). `{"quota": true}` (no `url`) answers
  just those three and counts nothing: a page's multi-site mode asks before it starts. The
  same finding on two hosts of one site (the same exact server version on `www.` and `wp.`) is
  one card listing both hosts, with each host's evidence. Off, the path is an unknown hook. Put it behind your marketing site's own
  name (an nginx `location` that proxies to it) so the page calls it same-origin.
- **Origins:** a browser's `Origin`, when sent, must be one of `public_check_origins`; only
  that origin gets CORS headers. A request with no `Origin` (curl) is allowed and rate-limited.
- **What it fetches,** in this order while the limit allows: `https://<host>/` (or `http://`
  when typed so) and its redirects (at most 3); when the site is WordPress, its `/wp-login.php`
  followed to its final page (at most 5 redirects), `/xmlrpc.php` and `/readme.html` (one GET
  each); then one content origin within the site's own domain (`wp.example.com` for
  `example.com`, the host the page loads most `/wp-content/` files from): its `/wp-login.php`
  and redirects, its `/wp-json/` (HEAD) and its home page (HEAD). At most 8 requests, 5 seconds
  and 512 KB each, 9 seconds in all; what the limit leaves out is listed as not fetched. GET and
  HEAD only, no cookie, no credentials, no form, never a secret file or a user list,
  User-Agent `SkaldStackCheck/1.0 (+<public_check_info_url>)`.
- **What it detects** (`skald/stack_public_detect.py`, each with its evidence): WordPress,
  WooCommerce, Drupal, Joomla, Magento, Laravel, Statamic, Symfony, CodeIgniter, PrestaShop,
  OpenCart, Craft, TYPO3 and plain PHP; Shopify, Wix, Squarespace, Webflow, HubSpot,
  WordPress.com and WordPress VIP (they patch for you); Next.js, Nuxt, Gatsby, Remix,
  SvelteKit, Astro, Hugo, Angular Universal, Express, Ghost; Vercel and Netlify (they run
  Node.js for you); nginx, Apache, LiteSpeed, OpenResty, IIS, Caddy; Cloudflare, Fastly,
  Akamai, CloudFront, Sucuri. Extras: security headers, the certificate's end (from the
  handshake made), XML-RPC on, readme.html's version. `tools/verify-public-check.py` checks it
  on real sites whose stack is public (`tools/public-check-truth.json`).
- **Proof, or "could not check":** every card carries what was seen, exactly as received (the
  header line, the generator tag, the page's references with a count and the first examples),
  the URL it was read from, what it means, why an advisory matched (product, version or
  "version not shown", host) and `curl` commands to check it yourself; the answer lists every
  request (method, URL, status, size, redirect, error), its time and the User-Agent. A home page
  that is not a 2xx, or a bot challenge, is "could not check" with nothing read from it. When a
  firewall stopped the check (a challenge such as Cloudflare's `cf-mitigated: challenge` or AWS
  WAF's, 401, 403, 429, or a firewall's own 503 denial page; a 503 alone is a site that is down)
  the answer has `reason: "blocked"`, a `summary` that says it is not a problem with the site, a
  `block` (`kind`: `challenge`, `denied` or `password`; `status`; `firewalls` named by their own
  headers or page: Cloudflare, Sucuri, Akamai, AWS WAF, CloudFront, Imperva, Fastly, Wordfence;
  `commands` to run by hand: the headers with curl, `php -v`), a card with that proof, and counts
  of 0. The check never changes its User-Agent or works around a challenge. The summary of a
  site read names the platform or language first, then the web server, the host and the CDN:
  "Your site runs PHP (version hidden) on nginx, behind CloudFront." "Update
  needed" only for a version the server showed; otherwise "check your version". The login page
  is "open" only when it ends in WordPress's login form; a redirect elsewhere, a page without
  the form, 401, 403, 404 or 410 is "hidden (good)"; anything else is "could not check". A web
  server showing its exact version that no advisory names gets a tip to hide it, never a flaw.
- **Never fetched:** an IP address in any form (`127.0.0.1`, `[::ffff:127.0.0.1]`,
  `2130706433`, `0x7f.1`, `127.1`), ports other than 80 and 443, `user:password@`, names that
  only work inside a network (`localhost`, `*.local`, `*.internal`, `*.lan`, `*.home.arpa`...),
  and any name with even one address that is loopback, private, link-local, CGNAT, multicast,
  reserved or a cloud metadata address (IPv4 and IPv6, IPv4 inside IPv6 too). The name is
  resolved once per request and the connection goes to that address, with the name as Host
  and TLS name, so it cannot be rebound; every redirect is checked again the same way.
- **Kept:** nothing written. Each answer is cached in memory for an hour (5 minutes when the
  site did not answer); the limits are in memory. The address typed is never logged; once an
  hour the helper writes one line of counts to stderr.

Each person's own security mail (Security > Alerts, "Your security alerts") goes in the
daily summary by default (`skald summary-mail`, 01:00, `SKALD_SUMMARY_AT`; one mail per person
for all their sites), or right away as one mail per run; it reminds while an item stays open
every `security.remind_days` (3) days.

Its alerts are switched on Site > Alerts like the others: `alerts.security_exposure` and
`alerts.stack_advisory` (on by default: they follow the site's alerts) and `alerts.scan_wave`
(off by default; the
config's `scan_wave_factor` 3, `scan_wave_days` 14, `scan_wave_min_days` 7 and
`scan_wave_minimum` 200 set its rule).

## Sale alerts

`alerts.sale` (a lead gained a counted sale value) and `alerts.sale_refund` (a counted refund
took money back from one) are off by default and follow the site's `alerts.enabled` and
`alerts.mail` like every rule (skald/alerts_sales.py). What counts is the Revenue
tab's rule (conversions_revenue.Book): never a test-marked lead, never before the site's
`revenue_since`. `alerts.sale_minimum` holds back a sale under its currency's minimum, and a
refund on such a sale; currencies are never converted, so each has its own. An alert goes for
a sale or refund Skald received after the switch was turned on and made in the last 72 hours,
once (kept by a hashed key in the alert state; docs/DATA-CONTRACT-ALERTS.md). The message
has the site, the amount as the dashboard shows it, the stage, the tool, the lead's source,
first touch, campaign, landing page (no query string) and label, new customer or renewal, and
the time; never a name, email, address, visitor ID, `customer_ref` or the tool's own id.

## Mail recipients confirm first

The install's SMTP server sends for every organisation, so an address typed in `mail.to`
gets nothing but one confirm mail until its owner follows the link in it
(`skald/mail_confirm.py`):

- Saving `mail.to` mails a link to each address that has not confirmed, at most one mail per
  address per day (whichever organisation asks). The save's answer, and `GET settings`, list
  them as `mail_waiting`.
- The link opens `/traffic-auth/mail-confirm?t=...`, a page with one button; the button
  confirms the address for that organisation. A link works once, for 7 days.
- Alerts' switches (`alerts.enabled`, `alerts.mail`, each rule) are saved per site from
  Site > Alerts (the table above; `apply` lays them over config.yml's `alerts` section, so
  the live run reads them on its next pass); their thresholds stay in config.yml
  (config.example.yml; the citation and crawler alerts: alerts_history.py). To send
  alerts to Slack or another tool, an admin adds an outgoing webhook for the event
  `alert.opened` on Settings > Integrations: one site, https only, signed with the webhook's
  own secret, which is kept in secrets.json (key `outgoing/<site>/<id>`), never in the
  `settings` table, and shown once. A `hooks.slack.com` address gets Slack's `{"text"}` shape.
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

## From the shell

An install admin at the server can read and save the same rows without the page
(`skald/settings_cli.py`; Docker: `docker exec skald skald settings ...`):

```sh
skald settings list-keys                          # every key: kind, scope, who, default
skald settings get example.com                    # each value and where it comes from
skald settings get example.com privacy.keep_days
skald settings set example.com beacon.visitor_ids true
skald settings set example.com beacon.share_subdomains true    # no tag change needed
skald settings set example.com site.asset_prefixes '["/wp-content/", "/wp-includes/"]'
skald settings set example.com conversions.identity anonymous
skald settings set example.com privacy.keep_days 180 --yes     # smaller: removes data
skald settings set example.com conversions.retention_days forever   # leads kept for good (or 0)
skald settings set example.com journeys.vid_days 400            # pages before a sign-up
skald settings set example.com beacon.visitor_ids null         # clear the row
```

The value is JSON (a word that is not JSON is taken as text). It is checked like the page's
(`settings_store.validate`), saved where the page saves it (`scope_for`), and audited as
`setting.change` by `cli`. Refused: a locked key, a secret (it would sit in the shell history:
use the page or the environment), an unknown site or key. A smaller retention window needs
`--yes`. Recipients saved this way get no confirm mail and receive nothing until they confirm:
add them on the Mail page.

## Routes

All on the refresh helper, behind nginx's session check, JSON answers. POSTs need the same
origin and the session's `X-Skald-CSRF` value.

| Method, path | Who | Answer |
| --- | --- | --- |
| GET `<page>/settings` | every member | `{settings: {key: {value, source, locked, editable, reason, ...}}, notice}`; secrets `{set, env}`. `notice` (2.15.0): the privacy-notice wording, below |
| POST `<page>/settings/save` | per key | `{key: value, ..., confirm?}`; null clears a row. All keys are checked before any is saved. The answer carries `settings` and `notice` again, made from the saved values; a save of `sites.views` also `views: {changed, removed, can_fill, reach, fill}` (below) |
| GET `<page>/settings/retention-preview?key=&value=` | admin | `{shrinks, rows, days, first, last, files}` |
| GET `<page>/settings/mail-preview?kind=daily\|weekly` | admin | `{kind, subject, html}`: the mail as it would go now, built by `mailer.build` from the verified history and never sent; no SMTP login is read (`mail_preview.py`). 409 with the run's words when the history cannot give it yet |
| POST `<page>/settings/test-mail` | admin | `{to}`: the caller's own address or a confirmed recipient (403 otherwise); 3 per 10 minutes per user (429 after) |
| GET `<page>/settings/reports` | admin | the site's client reports (each with `next`, the period it will cover, `confirmed`, `waiting`, `last_send`) and the organisation's branding (`client_reports_api.py`) |
| POST `<page>/settings/report-save` | admin | `{id?, name, recipients, schedule: {kind: weekly\|monthly\|custom, weekday, day, every, start, at}, period, sections, notes, footer, agency_logo, paused}`; a recipient not confirmed gets the confirm mail |
| POST `<page>/settings/report-delete` | admin | `{id}`; its send history goes with it |
| POST `<page>/settings/report-preview` | admin | `{id}` or unsaved settings -> `{subject, html, coverage, waiting, file}`; never sent. 409 when the period cannot be reported (no verified day, figures that do not reconcile) |
| POST `<page>/settings/report-pdf` | admin | the same, as `application/pdf` |
| POST `<page>/settings/report-send` | admin | `{id}`: send now to the confirmed recipients; 3 per 10 minutes per user (429 after); recorded |
| GET `<page>/settings/report-log?id=` | admin | `{sends}`: when, started by, period, addresses, ok, detail |
| GET, POST `<page>/settings/agency-logo` | admin | the organisation's logo (404: none); POST `{data: base64}` (PNG or JPEG, 256 KB at most) or `{data: null}` to remove |
| GET `<page>/settings/audit?action=&limit=&format=csv` | admin | `{entries, actions}` or a CSV file; install admins see every organisation |
| GET `<page>/settings/views-fill` | admin | `{fill, reach, views}`: the page-group fill's state for this site (another organisation's site only `{state: "busy"}`), the days the raw log holds. Below, "Page groups: filling past days" |
| POST `<page>/settings/views-fill-start` | admin | `{views?: [slug]}` (default every view of the site) -> `{fill, reach}`; starts `skald --site S views refresh --days N --view ...` in the background. 409 while a fill runs on the install, or when the raw log holds no whole day; audit `views.fill` |
| GET `<page>/sites` | every member | the organisation's sites: config file or dashboard, `status` active, paused or removed (`paused_at`, `removed_at`, `cleared_at`, `main`), log received. To admins also `kit {docker, systemd, why, image, ship_path}`, `api_base`, `mcp_url`, `mcp_enabled`, `beacon_on`, and per site `setup` and `quiet` (below) |
| POST `<page>/sites/add` | admin | `{host, timezone?, format?, token?}` -> the site, an ingest token (shown once), the shipper command, the tag. `token: false` makes no token (the Add a site wizard makes a named one later). Needs `ingest.enabled` (docs/INGEST.md) |
| POST `<page>/sites/token` | admin | `{name}`: a new ingest token for one of the organisation's sites |
| POST `<page>/sites/pause`, `<page>/sites/resume` | admin | `{name}`: stop collecting and counting a site (any site: dashboard or config file), or start again. Paused: ingest answers 503 with Retry-After 3600 (the shipper keeps its lines), live and run-daily skip it, everything is kept. Resume answers `{days, first, last, words}`: the whole days the pause missed and whether the log can still fill them. Audit `site.pause`, `site.resume`; 20 changes an hour per site (429) (`site_actions_api.py`, `site_lifecycle.py`) |
| POST `<page>/sites/remove`, `<page>/sites/restore` | owner | remove: `{name, confirm: name}`: stop processing and hide the site (ingest 410); its data is kept. Restore: `{name}`: undo it. Works for a config-file site too (its entry stays in the config). Audit `site.remove`, `site.restore` |
| POST `<page>/sites/clear` | owner | `{name, confirm: name, understood: true}` -> `{archive, archive_name, deleted}`: one archive of the site's collected data in the backups folder (kept 30 days), then that data deleted (history, the shipped log, conversions and leads, AI answer runs, the state folder); settings, tokens, webhooks, funnels kept; days before the clear are never collected again. 3 clears or deletes an hour per organisation. Audit `site.clear` with the archive's name |
| POST `<page>/sites/purge` | owner | `{name, confirm: name, understood: true}` -> `{archive, archive_name, deleted, tokens_revoked, status}`: "Delete all data": the archive, then every store of the site (`site_data.py` lists them), its tokens revoked. `status: "deleted"`: a dashboard site is gone (its name held 30 days); `"removed"`: a config-file site keeps its entry, removed, with no data. Audit `site.purge` with the archive's name |
| | | The install's main site (the config file's own) answers 400 to remove, restore, clear and purge; it can only be paused |
| POST `<page>/sites/verify` | admin | `{name}`: looks for the site's `skald-verify` token (DNS TXT or the home page's meta tag); 10 checks an hour per site |
| GET `<page>/sites/status?site=<name>` | admin | what has reached Skald for the site, for the Test in Settings > Connections (DATA-CONTRACT.md, "Connections status") |
| POST `<page>/sites/kit` | admin | `{site, method: server\|docker\|systemd, include_token?, token?}` -> for `server`, the one-file installer `skald-install-<site>.sh`, `text/x-shellscript` (docs/INGEST.md, "One command: the one-file installer and the install link"); for `docker` or `systemd`, the zip kit, `application/zip` (docs/INGEST.md, "The install kit and check.sh"). The token goes in only with `include_token: true` and a valid sending token of that site; else 400 |
| POST `<page>/sites/link` | admin | `{site}` -> `{ok, url, command, expires_at, token, token_id}`: a new sending token (shown once) and the one-time install command, `curl -fsSL <url> \| sudo bash`, for 24 hours (`kit_api.py`, `kit/link.py`; docs/INGEST.md). 409 when the log endpoint is off |
| POST `<page>/sites/pack`, `<page>/sites/packmail` | admin | the set-up pack, `skald-setup-<site>.zip`, downloaded or mailed to up to 3 addresses (`kit_api.py`, `kit/pack.py`; docs/INGEST.md, "The set-up pack") |
| POST `<page>/sites/setup` | admin | `{name, step?, method?, token_id?, done?}` -> `{setup}`: the Add a site wizard's progress (`accounts/site_setup.py`; audit `site.setup`). A method chosen for a dashboard site that has received nothing sets its format (`cloudflare`: `edge_json`, else `auto`; audit `site.format`) |
| POST `<page>/sites/share` | admin | `{site, task: send\|script\|hook, method?, days: 1\|7\|30}` -> `{link, ref, expires_at, ...}`: a "Share with your developer" link, shown once (`share_links.py`; audit `share.create`) |
| GET `<page>/sites/shares` | admin | `{shares: [{ref, site, task, method, created_at, expires_at, state, views, viewed_at, revealed_at}]}` |
| POST `<page>/sites/unshare` | admin | `{ref}`: revoke a link (audit `share.revoke`) |
| GET `/traffic-auth/setup/<id>` and `/info`, `/status`; POST `/reveal`, `/kit`, `/test` | anyone with the link | the shared page (`share_api.py`, `share_page.py`): one task for one site; the secret made and shown once (`share.reveal`); every view `share.view`; rate-limited per caller in memory; 410 once expired or revoked |
| GET `<page>/logo` | every member | the logo as an image (`?src=fetched\|upload` for one stored file); 404 while the site shows its letter. Also in basic mode |
| GET `<page>/logo/state` | every member | `{source, color, colors, letter, logo, found, checked_at, next_check, error, upload, hosts, editable, reason}` |
| POST `<page>/logo/upload` | admin | `{data: base64, name}`: PNG, ICO or a safe SVG, square, at least 64 x 64, at most 256 KB; sets `site.logo.source` to `upload` |
| POST `<page>/logo/check` | admin | asks the site for its icon now; once a minute per site (429 after) |

`sites/status`, `sites/kit` and `sites/setup` are `skald/connections_api.py`
(`sites/link`, `sites/pack` and `sites/packmail` are `skald/kit_api.py`); they sit under
`sites/` so the nginx route every install already has reaches them. `setup` in the `sites`
answer is the site's wizard row (or absent); `quiet` is true for a site whose set-up is done
and that nothing (no batch, no script-tag event) reached for 24 hours.

## The install kit's image (config only)

Settings > Connections offers the one command and the one file for a server, and the zip
kits by hand (docs/INGEST.md). Two keys say what the shipper runs with Docker: the Docker
way of the one command and one file, and the Docker kit. They are read from `config.yml` or
the environment only; no page changes them.

| Key | Values | Environment variable | Default |
| --- | --- | --- | --- |
| `ingest.kit_image` | a Docker image name, like `ghcr.io/<owner>/<image>:2` | `SKALD_KIT_IMAGE` | none: the page offers no Docker kit and says why, and the one file runs as a systemd service only |
| `ingest.kit_ship_path` | the shipper's path inside that image | `SKALD_KIT_SHIP_PATH` | `/opt/skald/tools/skald-ship.py` (the Docker image: its own app folder) |

The config key wins over the variable. The Docker image's entrypoint sets both variables
(`kit_defaults` in `docker/entrypoint.py`): the image itself at its major version, and the
shipper inside it, unless the environment already names them. The kit without Docker
(systemd) needs no image, only `tools/skald-ship.py` on the server.

## Sites added in the dashboard

Sites added in Settings > Add or remove sites live in accounts.sqlite (`site_config`), not in
config files; their host names, views, time zone and log paths are then changed on the Sites
page like any other site's. With saas on, a new site waits for its domain to be verified
(docs/SAAS.md, "Domain verification"): the list shows its token and a Verify button, and
nothing is collected for it until then.

A site added there, or by sign-up, has a page at once: a small "Getting ready" page in its
folder of the dashboard's output (only when none is there), then its first build on a thread
(`skald --site <site> dashboard`, `skald/first_page.py`). Its address never answers
nginx's 404 while it waits for the next run.

After that, every dashboard write (`skald dashboard`, every live run) gives each known site with
no page of its own a page saying why (`skald/setup_page.py`, 2.20.1): a site still
waiting for its first log lines (the wizard step it reached, **Continue setup** or **Test the
connection**, the troubleshooting guide, a reload each minute), or a removed site (removed on
that day, nothing collected, its data kept until purged; no setup button). That covers a
folder lost when the container is made again, and a removed site still listed for its
organisation. The page is written only where there is no page or where the page is this one,
behind the same sign-in as the dashboard, and the site's own run draws its dashboard over it.
The picker no longer offers "Setup: step N of 5, continue" for a removed site.

## Client reports (2.13)

Settings > Reports (`skald/client_reports*.py`, `client_report_*.py`, `pdf_writer.py`;
the guide is docs/help/client-reports.md). An admin makes, per site, reports for the site's
clients: a name, recipients, a schedule (weekly on a weekday, monthly on day N - a shorter
month's last day - or every N days from a date, at HH:MM in the site's time zone), a period
(last week Monday to Sunday, last month, month to date; on the 1st, month to date is the whole
month before), sections (summary, sources, pages, countries and cities, AI and bots, leads,
Search Console, notes), notes,
a footer line, the agency logo on or off, and paused. The Search Console section reads the
synced `search_days` (Settings > Integrations > Search, history schema 14): the period's final
days summed (clicks, impressions, CTR, position, top 10 queries and pages), provisional days
and days not synced yet listed by date and never counted; Search Console's days are Pacific
Time. A site with no property says so, and the box is greyed in the form.

- **Recipients confirm first**, by the rule below ("Mail recipients confirm first"): saving a
  report mails each new address its confirm link; a send goes to confirmed addresses only and
  says how many it left out.
- **Figures** are read from verified history only (`client_report_data.py`): a withheld,
  partial or missing day is listed by date, drawn as a pale stub in the chart and never
  counted; the sums must pass `verify.check` and the second count of
  `audit_client_reports.py` (the history file read again with its own SQL), or the report is
  refused, not sent smaller. A change against the period before is shown only when both are
  whole. Leads come from the site's lead database (`leads.db`), every day of the period.
- **Format**: an HTML mail (the daily mail's layout) with the same report as a PDF attached.
  The PDF is drawn by `pdf_writer.py`, standard library only (no browser in the image):
  Helvetica text, tables, bars; PNG and JPEG logos.
- **Branding**: the organisation's `brand.agency_name` (header, and the mail's From name; the
  address stays the install's `mail.from`), `brand.color` (the header band; its text is white
  or ink, whichever reads) and its logo, a PNG or JPEG kept in
  `<history folder>/logos/org-<id>/agency.<png|jpg>`. The site's own logo is the one Settings >
  Sites shows (an SVG or bitmap icon gives way to the letter).
- **Sending**: the container's scheduler runs `skald reports --due` every
  `SKALD_REPORTS_MINUTES` (15). A report goes once per scheduled day, from its time on; one
  whose period's last day is not stored yet waits for the morning run until 18:00, then goes
  with that day listed as not recorded. A failed send is tried once more 30 minutes later; a
  time missed by more than two days is not caught up, and neither is one that came before the
  report was made. Outside Docker, add `*/15 * * * * ... skald reports --due` to cron.
- **Records**: every try is a row in `client_report_sends` (accounts.sqlite, beside
  `client_reports`; DATA-CONTRACT-REPORTS.md): when, started by (the schedule or the person), the
  period, the addresses it went to, ok, the words. Saves, deletes, hand sends and logo changes
  are also in the audit log (`report.save`, `report.delete`, `report.send`, `brand.logo`).
- **Organisations**: every read and write names the site's organisation and the site; a
  report of a site that moved to another organisation is not sent.

`skald reports --list`, `--send ID`, `--pdf ID --out FILE` do the same from the shell.

## AI answers (2.14)

Settings > AI answers (`skald/answers/api.py`; every detail in docs/AI-ANSWERS.md). Not
settings_store keys: the site's lists and its tracking profiles live in `ai_answers.sqlite`
beside the history, filed by site, and every profile version is kept. Only the four API keys
are settings_store rows (above, Settings > Integrations, install admins, write-only).

- **The site's lists**: the questions buyers ask (at most 50), the brand terms, the
  competitors, and how many days answers are kept (30 to 3650, default 400). A profile with no
  list of its own asks with these.
- **Tracking profiles** (at most 10 a site): a name; a place (city, region, ISO country,
  optional latitude, longitude and time zone) and a language (BCP-47); its own questions, brand
  terms and competitors, or the site's; the assistants to ask; daily, weekly or monthly; 1 to 5
  tries a question; a daily cap in US dollars. Duplicate, pause, resume, Run now and delete.
  Nothing is erased: an edit is a new version (each run keeps the one it asked with), a pause
  is kept as a [from, to] pair, a deleted profile leaves the list and its results stay until
  the days kept pass.
- **Who**: every member reads; a site's admins and owners and install admins change, and each
  change is in the audit log. An organisation whose plan is locked reads only. Basic mode: the
  page says to use the API on the server (every route answers 404).
- **Asking**: the container's scheduler runs `skald ai-answers --due` every
  `SKALD_AI_ANSWERS_MINUTES` (15; 0 stops it): the profiles that are due (from 06:00 in the
  site's zone) or asked to run now. Outside Docker, add `*/15 * * * * ... skald ai-answers
  --due` to cron.

| Method, path | Who | Answer |
| --- | --- | --- |
| GET `<page>/ai-answers` | every member | `{site, lists, profiles, keys, editable, providers}`: which keys are set (never a key), each assistant's model, price and how it is told the place, each profile's estimate |
| GET `<page>/ai-answers/answer?id=` | every member | one stored answer in full: the question as sent, the text, the cited URLs |
| POST `<page>/ai-answers/lists` | admin | `{questions, brands, competitors, keep_days}` |
| POST `<page>/ai-answers/profiles/save` | admin | `{id?, ...profile}`: a new profile, or a new version of one |
| POST `<page>/ai-answers/profiles/duplicate`, `pause`, `resume`, `delete`, `run` | admin | `{id}`; delete leaves the list and keeps the results; run asks at the next 15-minute tick |

## The site's logo (2.6.0)

Settings > Sites > Logo (`skald/site_logos.py`, `logo_api.py`). The logo shows on the
site picker (`/traffic/`), in the sidebar's site button, in the site switcher and on the
browser tab (the site's icon with a small Skald badge, drawn in the page).

- **auto** (the default): Skald asks the site itself, never an outside icon service. The home
  page's `<link rel="apple-touch-icon">` (largest first), then `<link rel="icon">`, then
  `/apple-touch-icon.png`, then `/favicon.ico`. Only the site's own host names (`site.hosts`,
  and the site's name when it is a host name; IP addresses and example or local names are never
  asked), https only, never a name that resolves to a private, loopback or link-local address
  (the connection goes to the address that was checked). At most 3 redirects, each to one of the
  same hosts; 6 seconds a request, 20 for the whole check; 512 KB of the home page, 256 KB of an
  image. The Content-Type must say `image/` and the first bytes must agree (PNG, ICO, GIF, JPEG,
  WebP, or an SVG that passes the check below). Asked the moment the site is added (2.25:
  Settings > Sites, the Add a site wizard, sign-up and `skald site add`; on the new site's
  first-page thread, never holding up the add, a failure only noted), and `sites.json` is
  rewritten so the switcher shows it at once. Asked again by the daily run once a week (after
  a failed check, the next day), by the site picker for a site still showing its letter (at
  most once a day, on a thread), at once with **Check the site again now** (at most once a
  minute), or on the server with `skald logo --check`.
- **upload**: PNG, ICO or SVG, square (within 10%), at least 64 x 64 (an SVG scales), at most
  256 KB, by owners and admins.
- **letter**: the site's first letter on one of four colours. Also what every place shows while
  there is no logo, or when the image cannot load.

**SVG.** The standard library cannot turn an SVG into a PNG, so a risky SVG is refused rather
than cleaned: a DOCTYPE or entity, a processing instruction, an element outside SVG's namespace
(editors' notes in `<metadata>` excepted), `<script>`, `<foreignObject>`, animation, `<a>`, an
`on...` attribute, a link that is not `#...` inside the file, or `url(...)`, `@import`,
`javascript:` or `data:` pointing elsewhere. Every logo is served by the helper with the
Content-Type of its stored type, `X-Content-Type-Options: nosniff`, and
`Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox`; the pages show
it only in `<img>`, where no script runs.

Files: `<history folder>/logos/<site>/fetched.<ext>`, `upload.<ext>` and `state.json` (when the
site was asked, the URL the icon came from, why not). Not in the backups: an uploaded logo is
uploaded again after a restore, a fetched one is fetched again.

Audit: saving the choice or the colour writes `setting.change`; an upload writes `logo.upload`
(type, size, bytes, a hash prefix) and the source change; a check writes `logo.check` (found, or
why not).

## Internal addresses

Addresses added on the "Our own traffic" page are kept in `ours.file`; when config.yml does not
set it, in `ours.json` beside the history, like the other state files. The runs, the classifier
and the audit's own reading all find it there. Only when the server knows neither (no history
folder resolved) does the page hide its add form, with the reason, instead of offering it.

Each page-added entry is **Active** or **Paused** (2026-10-18): a switch on the page,
`POST <page>/ours/pause|resume`, or `skald ours pause|resume LABEL|ADDRESS` (in Docker
`docker exec skald skald ours ...`). A pause stops the entry applying from that moment, so the
team's visits count as visitors while they test; resuming applies it again from that moment.
The pauses stay on the entry (`paused`: `[[from, to-or-null], ...]`), so a day re-collected later
gives the same figures. **Edit** (label and/or address) ends the old entry now and starts a new
one now; **Delete** marks the entry `removed_at` and keeps it in the file. Neither changes a
day before it, on the main road or in the audit. Entries from config.yml always apply and
cannot be paused, edited or deleted on the page. Who may do this: the same people who may add
(an install admin with accounts; an admin with one shared login). `skald ours list` shows
entries by label only, never the address.

## The audit log

Every change writes a row: action `setting.change`, the key, and `<scope>: <old> -> <new>`.
A secret writes only `set` or `cleared`. Test mails write `mail.test` with the outcome.
