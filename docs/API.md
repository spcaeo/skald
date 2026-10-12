# Skald read-only API

Every figure the dashboard shows is a JSON file (DATA-CONTRACT.md). The API
serves those files, unchanged, so a script, a spreadsheet or another tool can
read them. It is read-only: nothing can be changed through it.

## Two ways in

| | URL | Who can call it |
| --- | --- | --- |
| With the dashboard login | `GET /traffic/<site>/[<view>/]api/v1/<name>` | anyone with a dashboard login: the nginx password in basic mode, a signed-in session in sessions mode |
| With a token | `GET /traffic-api/v1/<site>/[<view>/]<name>` | a script holding a token, sent as `Authorization: Bearer <token>` |

`<site>` is the site's folder (`example.com`), `<view>` a view's slug
(`us-english`, `canada-french`) or nothing for the whole site, and `<name>`
a data file without `.json`: `overview`, `live`, `visits`, `hourly`,
`breakdowns`, `health`, `bots`, `ours`, `not_found`, `ai_activity`,
`campaigns`, `pages`, `insights`, `requests`, `alerts`, `quality`, `markers`,
`leads`, `cube`, `robots`, `speed`, `funnels`, `page_index`, `events`,
`conversions`, `sites`. `GET .../api/v1/` lists the ones a page really has.

`GET .../api/v1/` (with the password) lists the files a page has:

```json
{"ok": true, "version": "v1", "files": ["ai_activity", "alerts", "bots", "..."], "docs": "docs/API.md"}
```

## Examples

```sh
# With the dashboard login
curl -u morgan https://www.example.com/traffic/example.com/api/v1/overview

# With a token, for a script
curl -H "Authorization: Bearer skald_ab12cd34_..." \
     https://www.example.com/traffic-api/v1/example.com/canada-french/pages
```

## Tokens

There are two kinds, one per access mode.

### Basic mode (`access.mode: basic`, the default)

Made on the server, by an admin, with the tool:

```sh
skald token create "Weekly sheet"                 # all sites, no addresses
skald token create "Ops" --site example.com --private # may also read requests and ai_activity
skald token list
skald token revoke ab12cd34
```

The token is printed once, when it is made; only a SHA-256 of it is kept
(`tokens.json` beside the history, mode 0640). A token without `--private`
cannot read `requests` or `ai_activity`, the two files that hold visitor
addresses, nor look a person up. A token never changes anything.

**A person (2.4.0).** `GET /traffic-api/v1/<site>/people?q=Q` with a private
token (`--private` / `read_private`; `tokens.PRIVATE` holds `people`) answers
what the page's search answers (`people/lookup.py`): for one IP address,
email, visitor ID (`skv_...`) or lead id, every visit kept with the address,
the last 6 hours of requests, the lead database's rows (spam, duplicates and
test too), every conversion (test, cancelled and removed too), the visitor
IDs' journeys, the visits that sent a form within 2 minutes before a lead
(`candidates`, matched by time, not certain), the linked `keys` and the days
withheld. 400 for a value that is none of those. Each call is written to the
audit log (accounts) or `privacy.log` (basic mode) by its kind and a hash
prefix, never the value. A listing, not a figure.

### Sessions mode (`access.mode: sessions`, docs/ACCOUNTS.md)

Tokens belong to an organisation and read only its sites, or the sites named.
Admins make them in Settings > API & tokens, or on the server:

```sh
skald token create "Weekly sheet" --scope read --site example.com
skald token create "Claude" --scope mcp --site example.com        # for the MCP server (MCP.md)
skald token list
skald token revoke ab12cd34
```

| Scope | Lets the token |
| --- | --- |
| `read` | read the data files at `/traffic-api/v1/...` |
| `read_private` | also read `requests` and `ai_activity`, the files with addresses, and look a person up (`people?q=`, MCP `find_person`) |
| `mcp` | use the MCP endpoint `/traffic-mcp` (MCP.md) |
| `ingest` | add log lines to one site at `/traffic-ingest/<site>` (INGEST.md); it reads nothing |

Only a SHA-256 is kept, in `accounts.sqlite`. A token made in the page stops
when the person who made it is disabled, demoted or removed. When the switch
to sessions mode is made, the basic-mode tokens move over as they are and keep
working.

## Answers

| Status | Body | When |
| --- | --- | --- |
| 200 | the file, as DATA-CONTRACT.md describes it | |
| 401 | `{"ok": false, "error": "..."}` | no token, an unknown or revoked one, a token for another site (or another organisation's), a token without the `read` scope, or a private file without `--private` / `read_private` |
| 404 | `{"ok": false, "error": "no such file"}` | the page or file does not exist |

Answers are `application/json`, never cached (`Cache-Control: no-store`).
Files are rewritten every 2 minutes by the live run; `generated_at` in each
says when. A field may be added without notice; one is never renamed or
removed without a new `schema_version` (DATA-CONTRACT.md).

## How it is served

In basic mode nginx keeps the password check for the first form and passes
the request, with the user's name (`X-Skald-User`), to the local helper
(`skald/refresh_server.py`, 127.0.0.1 only). In sessions mode the
helper reads the session cookie itself and never trusts that header. The
token form has no password at nginx; the helper checks the token. The helper
reads files only inside the dashboard's own folder.
