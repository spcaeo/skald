// Skald recorded journeys: app/api/skald-journey/route.ts (README.md).
// The page's helper (journeys.js) posts one event here. This route drops any address
// the browser sent, adds the visitor's address as this server saw it, signs the event
// and forwards it to Skald. The body is never logged.
import { forward, take } from "./sign.ts";

export const runtime = "nodejs";

// The visitor's address: the first x-forwarded-for hop (set by your own proxy or
// host), else x-real-ip.
function visitorIp(req: Request): string {
  const hop = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  return hop || (req.headers.get("x-real-ip") || "").trim();
}

export async function POST(req: Request): Promise<Response> {
  const got = await take(req);
  if ("refused" in got) return got.refused;
  const event = got.data;
  delete event.ip;
  if (process.env.SKALD_JOURNEY_SEND_IP !== "0") {
    const ip = visitorIp(req);
    if (ip) event.ip = ip;
  }
  return forward(process.env.SKALD_JOURNEY_URL, process.env.SKALD_JOURNEY_SECRET, JSON.stringify(event));
}
