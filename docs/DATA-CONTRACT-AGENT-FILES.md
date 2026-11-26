# Agent files: the day kind `agent_files` and agent_files.json (SKALD-56)

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md) (kept apart to hold that file
under 1000 lines); the rules there apply. Built by `agent_files.py`, recounted
by `audit_agent_files.py` (`audit_more.RECOUNTS`); drawn by Traffic › Agent
files (`js/tabs/tr-agentfiles.js`, one section per kind in `agent-files-kind.js` (SKALD-65), sums in `agent-files-sum.js`, a file's
drawer `agent-files-drawer.js`, route key `afile`).

**What it counts.** Every request for a file a site publishes for machines
rather than people, from every group but our own: people, answer engines (by
tier), search engines and bots. `ai_formats` (2.31) counts only the answer
engines' fetches, as one number per tier; this lists the files and every
visitor. Only the path decides (query string cut, letters A-Z made small,
trailing `/` taken off); the status does not, so a 404 for `/llms.txt` is a
request for llms.txt.

| kind | path |
|---|---|
| `okf` | a Markdown file (`.md`, `.mdx`, `.markdown`) with a folder named `okf` on the way: an OKF (Open Knowledge Format) bundle, `/okf/index.md` |
| `markdown` | any other path whose last segment ends `.md`, `.mdx` or `.markdown`: a page's Markdown copy (the not-a-page list's `markdown` entry) |
| `llms_txt` | a last segment `llms.txt` or `llms-full.txt`, at the root or below it |
| `agent_card` | `/.well-known/<name>` or `/.well-known/<name>/...` with name `agent-card.json`, `agent.json`, `agents.json`, `mcp`, `mcp.json`, `ai-plugin.json` or `ai-catalog.json` |
| `robots_txt` | exactly `/robots.txt` |
| `sitemap` | a last segment `sitemap*.xml` or `sitemap*.xml.gz` |

Order of the tests: llms.txt names, robots.txt, sitemaps, `/.well-known/`,
Markdown endings. Who (`who`): `ai_asked` and `ai_training` (an answer engine
by its tier), `search_engines`, `bots`, `people`. A name: the classifier's
name for an answer engine or search engine, the bots list's short name for a
bot (`crawler_cost.name_of`), `"People"` for people.

**Not counted:** a request for the page's own address with
`Accept: text/markdown` (content negotiation). No supported log format keeps
the request's Accept header or the answer's type, so those are page requests.

## The day kind (whole site only; null for a view)

| field | type | meaning |
|---|---|---|
| `kinds` | `{kind: {"requests", "status": {"2xx".."5xx": n}, "who": {who: n}}}` | the kinds with at least one request, in the order above |
| `names` | `{who: {name: {kind: n}}}` | each who's 20 busiest names (`top`; ties by name), the rest one `"(all others)"` entry |
| `files` | `{path: {"kind", "requests", "status": {code: n}, "who": {who: n}, "names": {name: n}, "last"}}` | the 50 busiest paths (`keep`; ties by path); a path is the request's path, first 200 characters, case kept; a longer path, cut there, ends with ` (<kind>)` so that two long paths of different kinds stay apart; `status` by the code the log writes; `names` its 5 busiest and `"(all others)"`; `last` its latest request, UTC, `YYYY-MM-DDTHH:MM:SSZ` |
| `rest` | `{kind: {"files", "requests"}}` | the paths beyond the 50, by kind |
| `folded` | `{"names": {who: n}, "files": n}` | how many names each fold holds, how many paths `rest` holds |

Verify (`agent_files.check`) holds: per kind, `who` and `status` add up to
`requests`; the kind's files plus its `rest` are its requests; per who, its
names over the kinds are what the kinds give that who; per file, `status`,
`who` and `names` add up to its `requests`; no group has more agent-file
requests than requests; a fold exactly when something was folded. Any problem
withholds the day. The audit rebuilds every figure from the raw lines with its
own path rule and compares each kind, name, kept file (its kind, statuses, who,
names, last request) and each kind's rest.

Kept `report.retention_days` like the other per-day detail
(`settings_store.DETAIL_KINDS`). Days collected before SKALD-56 have none: the
tab says "not counted", never 0. A past day can be counted again from a kept
log with `collect --day <day>`.

## agent_files.json

| field | type |
|---|---|
| `days[]` | `{"day","state", "files": {"kinds","names"} plus "files","rest" on the last 30 days, or null}` (180 days; null: counted before this existed) |
| `today` | the live snapshot's day the same way (files included) with `day`, or null |
| `detail_days` | 30: how many days carry the files |
| `keep`, `top` | 50 and 20 |
| `kinds`, `who` | the kinds and who keys, in order |

A page group (view) gets `{"whole_site_only": true}`.

Over a range the tab sums only verified (`ok`) days: kinds, who, statuses and
names over every day, files over the days that kept them (the tab says how many
of the range's days that is), and `rest` per kind. A range that includes today
takes today's blob too.
