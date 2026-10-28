# Connect: "has it arrived yet?" and Search Console's own connect (Unreleased)

Part of [DATA-CONTRACT.md](../DATA-CONTRACT.md); the rules there apply. Code:
`skald/connect_check.py` (the route), `skald/search/auto.py` (Search Console
connects by itself), `webapp/js/ui/live.js` and `webapp/js/live-words.js` (the page side).
Not a data file and not a figure: it reads what the endpoint, the hooks, the syncs and the
agent lines already keep.

## POST `<page>/sites/arrived` (helper API)

One answer for every place where Skald gives someone something to do: a line for an AI agent,
an install command, a script tag, a share page, a webhook address, a tool key, a token. Owner
or admin of the site's organisation (403 otherwise, 404 for another organisation's site);
same-origin and `X-Skald-CSRF` like every POST of `sites_api.py`. nginx: no change, the
existing `sites(?:/[a-z]+)?` location passes it.

Body `{"site", "what", "press"?}`. `what`:

| what | means |
|---|---|
| `logs` | the access log, any road (`setup_live` facts and verdict) |
| `agent:<link id>` | an agent line: opened, keys taken, reported; and the first data when its jobs include the logs |
| `hook:<tool>` | a tool's webhook (`lead`, `json`, `calendly`, `calcom`, `stripe`, `typeform`, `hubspot`) |
| `tag` | the script tag's events |
| `search` | Search Console and Bing: the saved property, the sync, and `auto` below |
| `tool:<id>` | one of your tools (`ga4`, `vercel`, `calendly`, `resend`) |
| `share:<ref>` | a "Share with your developer" page: opened, secret taken, then what its task brings |
| `journeys` | recorded journeys: sessions received |
| `token:<id>` | an API or MCP token: used yet |

Answer:

```json
{"ok": true, "test": {"verdict": "wait", "head": "Waiting for your agent: it has not opened the line yet.",
  "says": "...", "fix": "Paste the line into Claude Code or Codex ...",
  "steps": [{"id": "opened", "done": false, "words": "Your agent opened the line"}],
  "tech": "...", "at": "2026-10-27T17:56:00Z", "final": false}}
```

- `verdict`: `ok` (working), `wait` (nothing yet), `bad` (something to fix). `head` is the one
  plain sentence; `fix` the next thing to do; `tech` the technical words (behind Details).
- `steps`: the agent's or developer's progress where Skald knows it, each `{id, words, done}`;
  an empty list otherwise.
- `final`: nothing more can change (a cancelled or expired line, an unknown line): the page
  stops asking.
- A plain call is free and is what the page polls (every 5 s for 3 minutes, then every 30 s,
  never while the tab is hidden). `press: true` is the Test or Check now button: counted per
  person, `setup_live.CHECK_PER_HOUR` (60) an hour, then 429 "Too many checks. Try again in a
  few minutes."; it runs the fuller check where one exists (the log's own check; Search
  Console asks Google again).
- 400 for an unknown `what`.

## Search Console connects by itself: the `auto` part

The site's search state file (`<history folder>/search/<site>.json`, beside `google` and
`bing`) gains `auto` when Skald was asked to connect a property (an agent's report naming
`search.google_property`, Check now, or Connect on Search Console & Bing):

| field | meaning |
|---|---|
| `property` | the property asked for |
| `by` | who asked: `ai-agent`, or the person's user id |
| `since`, `last_try` | when it was asked, when Skald last asked Google |
| `state` | `waiting` (Google does not show the robot on a property of the site yet), `connected`, `gave_up` (after 7 days), `no_key` (no robot key on the install), `failed` |
| `words` | the plain sentence the pages show |
| `note` | when Skald used another property than the one asked, why ("Your agent named sc-domain:example.com, but Skald's robot is on https://example.com/: Skald uses that one.") |
| `source`, `connected_at` | the property connected and when |

Skald asks Google which properties its robot can see (the same listing as
`integrations/search/properties`), takes the one that covers the site's hosts (a domain
property first), saves it, and starts the 16-month history. While `waiting`, it asks again at
most once a minute: from the live run, from every page that shows it, and on Check now.

Answers that carry it:

- `GET integrations/search?site=` adds `auto` (the part above, or null).
- `POST integrations/search/connect` (Search Console) answers `{"waiting": true, "words",
  "started": false}` when Google does not show the robot yet (Skald keeps checking), and
  `note` when it connected another property than the one picked.
- The agent's report (`/traffic-kit/<code>/report`) answers `search: {state, words, note,
  source}` when the line has the search job and the report names a property, so the agent
  tells the person what Skald sees, never "go to Settings and press Connect".
