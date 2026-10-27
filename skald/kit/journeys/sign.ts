// Skald recorded journeys: the part both relay routes share (README.md).
// Checks a request from the site's own page, signs a body with the site's journey
// secret and forwards it to Skald. The secret stays on this server: never in the page,
// never in a log, never in an answer.
import { createHmac } from "node:crypto";

export const MAX_BODY = 16 * 1024;
const TIMEOUT_MS = 5000;
// What Skald's answer may pass on to the page: no more.
const PASSED = ["ok", "error", "field", "duplicate", "ignored", "removed"];

export type Taken = { data: Record<string, unknown> } | { refused: Response };

export function answer(status: number, body: Record<string, unknown>, more: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...more },
  });
}

// X-Skald-Timestamp (unix seconds) and X-Skald-Signature: hex HMAC-SHA256 of
// timestamp + "." + body, the exact bytes that are sent.
export function signHeaders(secret: string, body: string, now: number = Date.now()): Record<string, string> {
  const timestamp = String(Math.floor(now / 1000));
  const signature = createHmac("sha256", secret).update(timestamp + "." + body).digest("hex");
  return { "X-Skald-Timestamp": timestamp, "X-Skald-Signature": signature };
}

// The site's own origin: SKALD_SITE_ORIGIN when set (behind a proxy the request's
// own URL may say localhost), else the request URL's origin.
function siteOrigin(req: Request): string {
  const set = (process.env.SKALD_SITE_ORIGIN || "").trim().replace(/\/+$/, "");
  return set || new URL(req.url).origin;
}

// The page's JSON object, or the answer that refuses it.
export async function take(req: Request): Promise<Taken> {
  if (req.headers.get("origin") !== siteOrigin(req)) {
    return { refused: answer(403, { error: "only this site's own pages may send" }) };
  }
  const type = (req.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();
  if (type !== "application/json") {
    return { refused: answer(415, { error: "send application/json" }) };
  }
  if (Number(req.headers.get("content-length") || 0) > MAX_BODY) {
    return { refused: answer(413, { error: "too big" }) };
  }
  const raw = await req.arrayBuffer();
  if (raw.byteLength > MAX_BODY) {
    return { refused: answer(413, { error: "too big" }) };
  }
  let data: unknown;
  try {
    data = JSON.parse(new TextDecoder().decode(raw));
  } catch {
    return { refused: answer(400, { error: "not JSON" }) };
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { refused: answer(400, { error: "send one JSON object" }) };
  }
  return { data: data as Record<string, unknown> };
}

// Sign the body and send it to Skald; answer the page with Skald's status and a
// few of its words. Missing settings: 503, so the page's helper may try again.
export async function forward(url: string | undefined, secret: string | undefined, body: string): Promise<Response> {
  if (!url || !secret) {
    return answer(503, { error: "Skald journeys are not set up on this server" });
  }
  let got: Response;
  try {
    got = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...signHeaders(secret, body) },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    return answer(504, { error: "Skald did not answer" });
  }
  let said: Record<string, unknown> = {};
  try {
    said = await got.json();
  } catch {
    said = {};
  }
  const out: Record<string, unknown> = { ok: got.ok };
  for (const key of PASSED) {
    if (key !== "ok" && said && said[key] !== undefined) out[key] = said[key];
  }
  const wait = got.headers.get("retry-after");
  return answer(got.status, out, wait ? { "Retry-After": wait } : {});
}
