// Skald edge Worker: counts the pages Cloudflare serves from its cache.
//
// A page served from Cloudflare's cache never reaches your server, so your
// server's log never sees it. Cloudflare's own request log (Logpush, HTTP
// requests) is not on every plan. This Worker works on any plan: it passes
// every request on unchanged, and after the answer has gone out it posts one
// small record of the request to Skald (POST <SKALD_INGEST_URL>?format=edge).
//
// It never changes, blocks or delays the response:
//   - the response is returned as soon as Cloudflare has it; the post to
//     Skald runs in ctx.waitUntil, after it;
//   - a failed post is dropped silently (no retry, nothing logged);
//   - if this code throws, ctx.passThroughOnException() sends the request on
//     as if the Worker were not there.
//
// Settings (wrangler.toml [vars], or the dashboard; secrets with
// `wrangler secret put`):
//   SKALD_TOKEN             secret: an ingest token for this site (required)
//   SKALD_INGEST_URL        https://stats.example.com/traffic-ingest/example.com
//                           (required; ?format=edge is added)
//   SKALD_CACHE_HITS_ONLY   "true": send only cf-cache-status HIT. Skald drops
//                           the others anyway when it also reads your server's
//                           log; this saves the posts. Default: send all.
//   SKALD_SKIP_EXTENSIONS   e.g. "css,js,png,jpg,svg,woff2": do not send those.
//                           Default: send all (Skald sorts pages from assets).
//   SKALD_SAMPLE            a share between 0 and 1. Default 1 (every request).
//                           Skald does NOT scale sampled figures up: below 1,
//                           every figure is that share of the real one.
//
// Never sent: Skald's own paths (/traffic*). What a record holds is what a
// web server's access log line holds, plus the cache status and Cloudflare's
// request id (CF-Ray): time, address, method, host, path and query, status,
// bytes, referrer, user agent.
// Docs: docs/CDN-LOGS.md and docs/HOSTING.md ("Cloudflare on any plan").

export default {
  async fetch(request, env, ctx) {
    ctx.passThroughOnException();
    const started = Date.now();
    const response = await fetch(request);
    try {
      const record = edgeRecord(request, response, env, started);
      if (record) ctx.waitUntil(send(record, env));
    } catch (_) {
      // Counting must never break the page.
    }
    return response;
  },
};

function on(value) {
  return ["true", "1", "yes", "on"].includes(String(value || "").trim().toLowerCase());
}

function share(value) {
  if (value === undefined || value === null || String(value).trim() === "") return 1;
  const n = Number(value);
  return Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : 1;
}

function extensions(value) {
  return new Set(String(value || "").split(",")
    .map((x) => x.trim().replace(/^\./, "").toLowerCase()).filter(Boolean));
}

function edgeRecord(request, response, env, started) {
  if (!env.SKALD_INGEST_URL || !env.SKALD_TOKEN) return null;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/traffic")) return null;
  const skip = extensions(env.SKALD_SKIP_EXTENSIONS);
  if (skip.size) {
    const ext = /\.([A-Za-z0-9]+)$/.exec(url.pathname);
    if (ext && skip.has(ext[1].toLowerCase())) return null;
  }
  const cache = response.headers.get("cf-cache-status") || "";
  if (on(env.SKALD_CACHE_HITS_ONLY) && cache.toUpperCase() !== "HIT") return null;
  const rate = share(env.SKALD_SAMPLE);
  if (rate < 1 && !(Math.random() < rate)) return null;
  const length = response.headers.get("content-length");
  return {
    ts: new Date(started).toISOString(),
    ip: request.headers.get("cf-connecting-ip") || "",
    method: request.method,
    host: url.hostname,
    path: url.pathname + url.search,
    status: response.status,
    bytes: length !== null && /^\d+$/.test(length) ? Number(length) : null,
    referer: request.headers.get("referer") || "",
    ua: request.headers.get("user-agent") || "",
    cache,
    id: request.headers.get("cf-ray") || crypto.randomUUID(),
  };
}

function send(record, env) {
  const target = new URL(env.SKALD_INGEST_URL);
  target.searchParams.set("format", "edge");
  return fetch(target.toString(), {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.SKALD_TOKEN}`,
      "content-type": "application/json",
    },
    body: JSON.stringify(record),
  }).then((answer) => {
    if (answer.body) return answer.body.cancel().catch(() => {});
    return undefined;
  }).catch(() => {});
}
