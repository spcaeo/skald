# Integrations: search engines and AI answers

The search figures Skald syncs from Google Search Console and Bing Webmaster Tools, and
the AI answers it checks. Moved out of [INTEGRATIONS.md](INTEGRATIONS.md) (incoming hooks)
in 2.30 to keep each file under 1000 lines.

## Search Console and Bing

The log cannot see a search: no query, no impression, no position. Only the
search engine has them. Skald **syncs** them from Google Search Console and
Bing Webmaster Tools by their APIs, per site and day, into history (table
`search_days`), and shows them on **Traffic › Search** beside its own visits.
They are the engines' figures, never Skald's: they are never added to a
Skald figure. Code: `skald/search/` (ROADMAP P1-6). Data:
DATA-CONTRACT.md, "search.json".

### Connect Search Console (once per install)

An install admin does this once. The same robot serves every site.

1. In [Google Cloud console](https://console.cloud.google.com/), make a project
   (or pick one).
2. In APIs & Services › Library, find **Google Search Console API** and choose
   **Enable**.
3. In IAM & Admin › Service accounts, choose **Create service account**. Give it
   a name such as `skald-search`. It needs no role in the project.
4. Open it, then Keys › Add key › Create new key › **JSON**. Your browser
   downloads a `.json` file. Keep it safe: it is the robot's password.
5. In Skald, **Settings › Integrations › Search › Upload service account key**,
   pick the file. Skald checks it (a `service_account` key with a readable
   RSA key), keeps it 0600 in `secrets.json` beside the history, and from
   then on shows only the robot's email, with a Copy button. **Remove** takes
   it out.

### Connect a site to Search Console

A site admin does this for each site, in **Settings › Integrations › Search**.

1. **Give the robot access.** Copy the robot's email. In Search Console ›
   Settings › Users and permissions (<https://search.google.com/search-console/users>),
   choose Add user, paste the email, set **Restricted**, choose Add.
   Restricted can only read; it cannot change anything.
   A client's site: the client does this in their own Search Console. The
   **Copy text to send** button gives a short message with these steps.
2. **Find my properties.** Skald asks Google which properties the robot can
   see and lists the ones that cover this site's host names (a Domain
   property `sc-domain:example.com`, or a URL-prefix property
   `https://www.example.com/`). Pick one. A property that does not cover the
   site's hosts is refused: one robot serves every site of the install.
3. **Test connection.** Skald reads the last 3 days and shows "OK: N rows,
   clicks X". Nothing is stored.
4. **Connect.** Choose how much history to fetch first: none, 3 months or
   16 months (all that Search Console keeps). The backfill runs in the
   background, with its progress on the page. Then the normal syncs take over.

**Disconnect** stops the syncs. What was synced stays in history.

**Skald connects by itself (Unreleased).** On Connect, on Check now, and when an AI agent's
report names a property, Skald asks Google which properties its robot sees and connects the
one that covers the site (a domain property first). If the robot is on another property than
the one named (a URL-prefix `https://example.com/` instead of `sc-domain:example.com`), Skald
uses that one and says so in one line. If Google shows none yet, the page says "Waiting for
Google: Skald's robot address is not on a example.com property yet." and Skald keeps asking,
at most once a minute, for 7 days; once it appears, Skald connects and starts the 16-month
history with nobody pressing anything. Traffic › Search follows this by itself, without a
reload. Contract: [DATA-CONTRACT-CONNECT.md](DATA-CONTRACT-CONNECT.md).

### Connect Bing Webmaster Tools

1. In Bing Webmaster Tools, Settings › API access › **API key**, make a key.
2. An install admin types it in **Settings › Integrations › Search › Bing API
   key**. It is kept 0600 in `secrets.json`; the page shows only its last 4
   characters.
3. Per site: **Find my sites** lists the sites the key's account holds that
   cover this site's hosts. Pick one, **Test connection**, **Connect**. Bing
   gives all it keeps in one answer, so there is no backfill choice.

### From the server instead

The page is the easy road. On a server without accounts, or to keep the
key out of `secrets.json`, set it in the environment. **The environment wins**
over an uploaded key.

| What | Where (first found wins) |
| --- | --- |
| Search Console key | `SKALD_GSC_KEY_JSON` (the file's text), else `SKALD_GSC_KEY_FILE` or `search_console.key_file` in config.yml (a path; make it 0600), else `secrets.json` key `SKALD_GSC_KEY_JSON` |
| Bing API key | `BING_WEBMASTER_API_KEY`, else `secrets.json` under the same name |
| A site's property | `search_console.property` in the site's config, or the setting `search.google_property` (`skald settings set`) |
| A site's Bing site | `bing.site_url`, or the setting `search.bing_site` |

Commands (each site in turn; `--site NAME` for one; `import` is the same as `sync`):

```sh
./bin/skald --config config.yml search-console sync [--days N] [--backfill-months 3|16]
./bin/skald --config config.yml search-console status
./bin/skald --config config.yml bing sync|status [--days N]
./bin/skald --config config.yml search sync        # both, what the scheduler runs
```

`--days N` fetches the last N days again (default 4); for Bing it keeps only
the last N days Bing returns.

### How the sync runs

- **By itself, every 6 hours.** The Docker scheduler runs `search sync` at
  01:40, 07:40, 13:40 and 19:40 in the site's time zone, clear of the daily
  run (`SKALD_SEARCH_HOURS`, `SKALD_SEARCH_AT`; 0 hours turns it off). One site
  after another. A site with nothing connected is skipped at once.
- **One at a time.** Each site has a lock. The scheduler's sync, **Sync now**
  and a backfill of the same site never overlap; the second one says
  "already syncing" and stops. Sync now is for admins, at most once in 10
  minutes per site.
- **The newest day, and the last days again.** Search Console's figures
  arrive about 2 to 3 days late and change for a while after. Each sync finds
  the newest day Google has, then fetches again from the earliest of: the
  day after the newest stored day, the 4 days before the newest day, and any
  stored day still provisional. Those days are replaced.
- **Final or provisional.** Google says where its data stops being final
  (`first_incomplete_date`). Days after it are stored as **provisional** and
  shown so; the next sync fetches them again. Bing's days are final after 10
  days.
- **Pacific days.** Search Console's days are Pacific Time, as Google gives
  them. Skald does not re-cut them into the site's time zone.
- **16 months.** Search Console keeps 16 months. Nothing older is asked for.
- **Row limits.** Google gives at most 25,000 rows a page. Skald pages
  through them (`startRow`), 7 days at a time. Google says it returns the
  top rows, not always all of them.
- **Retries.** A 429, a 5xx or a dropped connection is tried again after 1,
  2, 4 and 8 seconds (or what Retry-After asks). A wrong key or a missing
  permission is not retried.
- **Errors in plain words.** A failure (say, the robot was removed in Search
  Console) shows on Settings › Integrations and on the Search tab, with what
  to do. The first failure of a run of failures sends **one mail** to the
  site's mail recipients. No more mails until it works again and then fails.
- **Status.** "Last synced HH:MM · next ~HH:MM", days stored, the newest day,
  how many are provisional, and the backfill's progress.

### What is synced

Search Console, web results (`type: web`), per day:

| Kind | Rows |
| --- | --- |
| total | clicks, impressions, CTR, position for the property |
| query | the top 500 queries |
| page | the top 300 pages (Google counts pages by page, so this table has its own total) |
| country | the top 250 countries (Google's alpha-3 codes) |
| device | desktop, mobile, tablet |
| search appearance | the top 100, under Google's own names |

Each table keeps "(all others)" for the rows past the top, and what Google
counts but does not give by that dimension (Search Console leaves
anonymised queries out of the query table, not out of the total). So rows +
"(all others)" + not attributed = the day's total, always.

**AI Overviews and AI Mode.** The Search Analytics API reference names no
AI Overview or AI Mode figure (checked 2026-10-18). Skald does not invent
one. If Google adds a search appearance value for them, it shows in the
search appearance table under Google's own name.

Bing: clicks and impressions per day (`GetRankAndTrafficStats`), and the top
queries and pages (`GetQueryStats`, `GetPageStats`) with their average
position. Bing updates these weekly and gives only top rows with no total
beside them, so a Bing table is what Bing returned, never the whole site.
Bing's AI Performance report (Copilot citations) had no documented API
method on 2026-10-18, so it is not synced.

### How Skald signs in to Google

The standard library has no RSA. `search/rsa.py` signs in pure Python: it
reads the key's PKCS#8 block with a small ASN.1 reader, and signs with
RSASSA-PKCS1-v1_5 and SHA-256 (RS256). Skald makes a JWT (issuer: the robot's
email; scope: `webmasters.readonly`; one hour), signs it, and trades it at
`https://oauth2.googleapis.com/token` for an access token (the OAuth 2.0 JWT
bearer grant), kept in memory until a minute before it ends. The token
address is always Google's: a key file that names another is refused. The
scope is read-only: Skald can never change anything in Search Console. The
key is never printed or logged; errors are scrubbed of keys and tokens.

### The second road, and the cross-check

Search figures come from the engine, like a booking from a hook or a lead
from the CMS. The audit cannot recount them from the log. So, as with
hooks and leads, it checks what Skald kept against the source, by its own
code (`audit_search.py`, in run-daily's recounts):

1. Every stored table of the last 40 days is added up again by SQL
   (SQLite's `json_each`): rows + "(all others)" + not attributed must equal
   the total, for clicks and impressions.
2. Search Console's query, country, device and search appearance tables must
   carry the day's total.
3. One figure is asked of the engine again: the newest final day's clicks
   and impressions. An engine that cannot be reached is noted, not a
   mismatch; a figure that differs is.

The sync itself reads back every day it writes: if what is stored is not
what the engine gave, nothing is kept and the sync fails. A mismatch in the
audit ends run-daily "withheld", and the Search tab says what the second road
found.

**The cross-check is a comparison, never a check.** The Search tab puts
Search Console's clicks beside Skald's people from Google search, per day
and per landing page, over the last 28 final days (`search_landing`, Skald's
own figure, with its own second count in `audit_search_landing.py`). They
count different things and are never forced to match: a click is not a
visit, some apps send no referrer, Pacific days are not the site's days. The
tab says so beside the figures, and flags a sudden change in the ratio:
that is usually a tracking break.

## AI answers

What ChatGPT, Perplexity, Gemini and Claude say when asked the questions buyers ask, joined
with what the same assistant read on the site and the visitors and leads it sent. In short:
one key per assistant (Settings › Integrations, write-only, 0600 in `secrets.json`; the
environment's `SKALD_OPENAI_API_KEY`, `SKALD_PERPLEXITY_API_KEY`, `SKALD_GEMINI_API_KEY`,
`SKALD_ANTHROPIC_API_KEY` win; never printed or logged); nothing is asked until a site admin
makes a tracking profile (Settings › AI answers); every answer costs on your provider account,
estimated before it runs, with a daily cap in US dollars per profile; the questions go to the
providers you choose, under their terms, nothing about visitors; answers kept 400 days
(`keep_days`). Every detail: [docs/AI-ANSWERS.md](AI-ANSWERS.md).
