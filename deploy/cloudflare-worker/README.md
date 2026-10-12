# The Skald Worker: Cloudflare on any plan

A page Cloudflare serves from its cache never reaches your server, so your server's log never
sees it. Cloudflare's own request log (Logpush, dataset HTTP requests) is not on every plan:
"Dataset availability depends on the Cloudflare products on your account"
(<https://developers.cloudflare.com/logs/logpush/>). This Worker works on any plan, the free
one included.

It passes every request on unchanged. After the response has gone out, it posts one small
record of the request to Skald. It never changes, blocks or delays the response, and a failed
post is dropped without a retry.

Files:

- `skald-edge.js`: the Worker.
- `wrangler.toml.example`: a config to copy.
- `../netlify-edge-function/skald-edge.js`: the same idea as a Netlify Edge Function
  (an example, not tested on Netlify).

## Set it up

1. **In Skald:** turn on ingest, make the site, and make an ingest token for it
   (docs/INGEST.md). Pick the log format:
   - `edge_json` when these records are the site's only log (no server log reaches Skald);
   - `auto` when Skald also reads your server's log. Then Skald keeps only the cache hits
     from the Worker (below).
2. **Install Wrangler** (Cloudflare's command-line tool) and sign in: `npx wrangler login`.
3. Copy `wrangler.toml.example` to `wrangler.toml`. Set the routes to your site's hosts and
   `SKALD_INGEST_URL` to `https://<your Skald>/traffic-ingest/<site>`.
4. Store the token as a secret, never in `wrangler.toml`:

   ```sh
   npx wrangler secret put SKALD_TOKEN
   ```

5. Deploy: `npx wrangler deploy`. Open a page of the site; the record shows in Skald's live
   panel within minutes.

Settings:

| Name | Default | What it does |
| --- | --- | --- |
| `SKALD_TOKEN` (secret) | none | the site's ingest token. Without it nothing is sent |
| `SKALD_INGEST_URL` | none | `https://<your Skald>/traffic-ingest/<site>`; `?format=edge` is added |
| `SKALD_CACHE_HITS_ONLY` | off | `true`: send only `cf-cache-status: HIT`. Saves the posts Skald would drop when it also reads your server's log |
| `SKALD_SKIP_EXTENSIONS` | none | e.g. `css,js,png,woff2`: do not send those. Skald tells pages from assets itself |
| `SKALD_SAMPLE` | `1` | the share of requests sent. Skald does **not** scale sampled figures up |

Skald's own paths (`/traffic...`) are never sent.

## Never count a request twice

A request Cloudflare passed on to your server (cache status MISS, EXPIRED, BYPASS, DYNAMIC,
REVALIDATED, UPDATING; STALE or none too, to be safe) is in your server's log as well. When the
site reads both, Skald keeps only the Worker's records with cache status **HIT**; the server's
log has the rest. That is the site setting `logs.edge_only_cached`: true unless the site's format
is `edge_json`. Set it yourself in the site's config to override.

Both logs must reach the same site folder: ship the server's log with `skald-ship` to the same
`/traffic-ingest/<site>` (docs/INGEST.md), so Skald reads the two together.

## What it costs

Each request through the Worker is a Worker request on your Cloudflare bill or free allowance;
the post to Skald is a subrequest. Cloudflare's pricing page says how many requests each plan
includes and that subrequests are not billed: <https://developers.cloudflare.com/workers/platform/pricing/>.

On Skald's side, each record is one post. A site's edge posts have their own rate limit,
`ingest.edge_per_minute` (default 1200) and `ingest.edge_burst` (300). A post over the limit
is refused, and the Worker drops it: that request is not counted. Set the limit above your
busiest minute.

## Privacy

A record holds what a web server's access log line holds, and no more: time, the visitor's
address (`CF-Connecting-IP`), method, host, path and query, status, bytes, referrer and user
agent; plus the cache status and Cloudflare's request id (`CF-Ray`). No cookies, no other
headers, no body. Skald drops any other field a sender adds before writing.

## Sources

Checked on 2026-10-12.

- `ctx.waitUntil` and `ctx.passThroughOnException`:
  <https://developers.cloudflare.com/workers/runtime-apis/context/>
- `cf-cache-status` values: <https://developers.cloudflare.com/cache/concepts/cache-responses/>
- Workers pricing: <https://developers.cloudflare.com/workers/platform/pricing/>
- Logpush availability: <https://developers.cloudflare.com/logs/logpush/>
- Netlify Edge Functions (`context.next`, `context.waitUntil`, `context.ip`):
  <https://docs.netlify.com/build/edge-functions/api/>
