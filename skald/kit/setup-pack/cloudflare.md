# Cloudflare: the Skald Worker for __SITE__

The Skald Worker passes every request on unchanged and, after the answer has gone out, sends
a small record of it to Skald. Use it when Cloudflare serves the site and no server log is
sent. It works on every Cloudflare plan, the free one included.

1. Deploy the Worker: the Deploy to Cloudflare button in `deploy/cloudflare-worker/README.md`
   (in Skald's code; ask whoever runs your Skald if you do not have it), or by hand with
   Wrangler from that folder.
2. Set its two values. The address, `SKALD_INGEST_URL`:

       __INGEST_URL__

   and the token, as a secret named `SKALD_TOKEN`:

       __TOKEN__

3. By hand with Wrangler, the token is set with this command (it asks for the value), then
   deploy:

       npx wrangler secret put SKALD_TOKEN
       npx wrangler deploy

4. Add the site's route: in Cloudflare, open the Worker, then Settings > Domains & Routes >
   Add > Route, with `__SITE__/*` (and `www.__SITE__/*`).
5. Open a page of the site. Within a few minutes it shows on __DASHBOARD__ (Settings >
   Collect data > Send logs says what arrived).

Skald reads this site's records as edge records (log format `edge_json`) when nothing else
has arrived for it yet. If you also send the server's log, keep the format "Detect it": then
only Cloudflare's cache hits are counted from the Worker.

The token works like a password: keep it in the Worker's secret, never in `wrangler.toml` or
in git.
