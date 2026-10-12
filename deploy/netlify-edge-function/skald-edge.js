// EXAMPLE, not tested on Netlify. A Netlify Edge Function that posts one
// Skald edge record per request, after the response, without delaying it.
// For a Netlify site without Log Drains (an Enterprise feature). Put it at
// netlify/edge-functions/skald-edge.js. The full Worker for Cloudflare, with
// every option, is deploy/cloudflare-worker/skald-edge.js.
//
// Netlify's docs (https://docs.netlify.com/build/edge-functions/api/):
//   context.next()      "returns a Promise containing the Response from the
//                       origin", so the record can carry the status;
//   context.waitUntil() extends the function "without blocking the response
//                       to the client from being sent";
//   context.ip          "the client IP address".
// Environment variables (site settings): SKALD_TOKEN, SKALD_INGEST_URL.
// Netlify serves the site itself, so there is no other log to double-count:
// make the Skald site with log format edge_json.

export default async (request, context) => {
  const started = Date.now();
  const response = await context.next();
  try {
    const target = Netlify.env.get("SKALD_INGEST_URL");
    const token = Netlify.env.get("SKALD_TOKEN");
    const url = new URL(request.url);
    if (target && token && !url.pathname.startsWith("/traffic")) {
      const length = response.headers.get("content-length");
      const record = {
        ts: new Date(started).toISOString(),
        ip: context.ip || "",
        method: request.method,
        host: url.hostname,
        path: url.pathname + url.search,
        status: response.status,
        bytes: length !== null && /^\d+$/.test(length) ? Number(length) : null,
        referer: request.headers.get("referer") || "",
        ua: request.headers.get("user-agent") || "",
        id: context.requestId || crypto.randomUUID(),
      };
      const to = new URL(target);
      to.searchParams.set("format", "edge");
      context.waitUntil(fetch(to.toString(), {
        method: "POST",
        headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
        body: JSON.stringify(record),
      }).catch(() => {}));
    }
  } catch (_) {
    // Counting must never break the page.
  }
  return response;
};

export const config = { path: "/*", excludedPath: ["/traffic-*"] };
